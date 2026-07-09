"""Integração com a Google Ads API.

Todo o acoplamento com a biblioteca google-ads vive neste arquivo:
consultas GAQL de leitura e as três mutações suportadas pelo MVP
(pausar palavra, adicionar negativa, aumentar orçamento).
"""
from __future__ import annotations

from datetime import date, timedelta

from .config import AppConfig, GOOGLE_ADS_YAML
from .models import (
    AccountData,
    AccountInfo,
    CampaignStats,
    KeywordStats,
    SearchTermStats,
    TodayMetrics,
    brl,
)


class GoogleAdsProvider:
    """Provedor real: fala com a conta via Google Ads API."""

    def __init__(self, config: AppConfig):
        # Import tardio para o modo demo funcionar sem a biblioteca instalada.
        from google.ads.googleads.client import GoogleAdsClient

        self.config = config
        self.customer_id = config.customer_id_digits
        self.client = GoogleAdsClient.load_from_storage(str(GOOGLE_ADS_YAML))
        self.service = self.client.get_service("GoogleAdsService")

    # ------------------------------------------------------------------ leitura

    def _search(self, query: str):
        return self.service.search(customer_id=self.customer_id, query=query)

    @staticmethod
    def _periodo(dias: int) -> str:
        """Janela de análise: últimos N dias completos, excluindo hoje.

        Os dados do dia corrente são parciais e mudariam a análise a cada hora.
        """
        fim = date.today() - timedelta(days=1)
        inicio = fim - timedelta(days=dias - 1)
        return f"segments.date BETWEEN '{inicio:%Y-%m-%d}' AND '{fim:%Y-%m-%d}'"

    def fetch_account_data(self) -> AccountData:
        """Baixa tudo que a análise precisa em quatro consultas."""
        dias = self.config.analise.periodo_dias
        return AccountData(
            info=self._account_info(),
            hoje=self._today_metrics(),
            campanhas=self._campaigns(dias),
            palavras=self._keywords(dias),
            termos=self._search_terms(dias),
            periodo_dias=dias,
        )

    def _account_info(self) -> AccountInfo:
        row = next(iter(self._search(
            "SELECT customer.id, customer.descriptive_name, "
            "customer.currency_code, customer.time_zone FROM customer"
        )))
        c = row.customer
        return AccountInfo(
            customer_id=str(c.id),
            nome=c.descriptive_name or f"Conta {c.id}",
            moeda=c.currency_code,
            fuso=c.time_zone,
        )

    def _today_metrics(self) -> TodayMetrics:
        m = TodayMetrics()
        for row in self._search(
            "SELECT metrics.cost_micros, metrics.clicks, metrics.impressions, "
            "metrics.conversions FROM customer WHERE segments.date DURING TODAY"
        ):
            m.custo += brl(row.metrics.cost_micros)
            m.cliques += row.metrics.clicks
            m.impressoes += row.metrics.impressions
            m.conversoes += row.metrics.conversions
        return m

    def _campaigns(self, dias: int) -> list[CampaignStats]:
        query = f"""
            SELECT campaign.id, campaign.name, campaign.status,
                   campaign_budget.amount_micros, campaign_budget.explicitly_shared,
                   campaign_budget.resource_name,
                   metrics.cost_micros, metrics.clicks, metrics.impressions,
                   metrics.conversions, metrics.conversions_value,
                   metrics.search_budget_lost_impression_share
            FROM campaign
            WHERE {self._periodo(dias)}
              AND campaign.status = 'ENABLED'
        """
        out = []
        for row in self._search(query):
            out.append(CampaignStats(
                campaign_id=row.campaign.id,
                nome=row.campaign.name,
                status=row.campaign.status.name,
                custo=brl(row.metrics.cost_micros),
                cliques=row.metrics.clicks,
                impressoes=row.metrics.impressions,
                conversoes=row.metrics.conversions,
                valor_conversoes=row.metrics.conversions_value,
                orcamento_diario=brl(row.campaign_budget.amount_micros),
                orcamento_resource_name=row.campaign_budget.resource_name,
                orcamento_compartilhado=row.campaign_budget.explicitly_shared,
                perda_impressao_orcamento=row.metrics.search_budget_lost_impression_share or 0.0,
            ))
        return out

    def _keywords(self, dias: int) -> list[KeywordStats]:
        query = f"""
            SELECT campaign.id, campaign.name, ad_group.id, ad_group.name,
                   ad_group_criterion.criterion_id, ad_group_criterion.keyword.text,
                   ad_group_criterion.keyword.match_type, ad_group_criterion.status,
                   ad_group_criterion.quality_info.quality_score,
                   metrics.cost_micros, metrics.clicks, metrics.impressions,
                   metrics.conversions
            FROM keyword_view
            WHERE {self._periodo(dias)}
              AND ad_group_criterion.status = 'ENABLED'
              AND campaign.status = 'ENABLED'
        """
        out = []
        for row in self._search(query):
            qs = row.ad_group_criterion.quality_info.quality_score
            out.append(KeywordStats(
                campaign_id=row.campaign.id,
                campaign_nome=row.campaign.name,
                ad_group_id=row.ad_group.id,
                ad_group_nome=row.ad_group.name,
                criterion_id=row.ad_group_criterion.criterion_id,
                texto=row.ad_group_criterion.keyword.text,
                match_type=row.ad_group_criterion.keyword.match_type.name,
                status=row.ad_group_criterion.status.name,
                custo=brl(row.metrics.cost_micros),
                cliques=row.metrics.clicks,
                impressoes=row.metrics.impressions,
                conversoes=row.metrics.conversions,
                quality_score=qs if qs else None,
            ))
        return out

    def _search_terms(self, dias: int) -> list[SearchTermStats]:
        query = f"""
            SELECT campaign.id, campaign.name, search_term_view.search_term,
                   metrics.cost_micros, metrics.clicks, metrics.conversions
            FROM search_term_view
            WHERE {self._periodo(dias)}
              AND campaign.status = 'ENABLED'
        """
        out = []
        for row in self._search(query):
            out.append(SearchTermStats(
                campaign_id=row.campaign.id,
                campaign_nome=row.campaign.name,
                termo=row.search_term_view.search_term,
                custo=brl(row.metrics.cost_micros),
                cliques=row.metrics.clicks,
                conversoes=row.metrics.conversions,
            ))
        return out

    # ---------------------------------------------------------------- mutações

    def pause_keyword(self, ad_group_id: int, criterion_id: int) -> str:
        """Pausa uma palavra-chave (status PAUSED — reversível no Google Ads)."""
        from google.api_core import protobuf_helpers

        svc = self.client.get_service("AdGroupCriterionService")
        op = self.client.get_type("AdGroupCriterionOperation")
        crit = op.update
        crit.resource_name = svc.ad_group_criterion_path(
            self.customer_id, ad_group_id, criterion_id
        )
        crit.status = self.client.enums.AdGroupCriterionStatusEnum.PAUSED
        self.client.copy_from(
            op.update_mask, protobuf_helpers.field_mask(None, crit._pb)
        )
        resp = svc.mutate_ad_group_criteria(
            customer_id=self.customer_id, operations=[op]
        )
        return resp.results[0].resource_name

    def add_negative_keyword(self, campaign_id: int, texto: str) -> str:
        """Adiciona palavra negativa (correspondência exata) no nível da campanha."""
        svc = self.client.get_service("CampaignCriterionService")
        op = self.client.get_type("CampaignCriterionOperation")
        crit = op.create
        crit.campaign = self.client.get_service("CampaignService").campaign_path(
            self.customer_id, campaign_id
        )
        crit.negative = True
        crit.keyword.text = texto
        crit.keyword.match_type = self.client.enums.KeywordMatchTypeEnum.EXACT
        resp = svc.mutate_campaign_criteria(
            customer_id=self.customer_id, operations=[op]
        )
        return resp.results[0].resource_name

    def update_budget(self, budget_resource_name: str, novo_valor_reais: float) -> str:
        """Altera o orçamento diário de uma campanha (valor em reais)."""
        from google.api_core import protobuf_helpers

        svc = self.client.get_service("CampaignBudgetService")
        op = self.client.get_type("CampaignBudgetOperation")
        budget = op.update
        budget.resource_name = budget_resource_name
        budget.amount_micros = int(round(novo_valor_reais * 1_000_000))
        self.client.copy_from(
            op.update_mask, protobuf_helpers.field_mask(None, budget._pb)
        )
        resp = svc.mutate_campaign_budgets(
            customer_id=self.customer_id, operations=[op]
        )
        return resp.results[0].resource_name
