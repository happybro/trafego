"""Modo demonstração do JV Ads.

Dados fictícios (inspirados numa loja de pneus para caminhão) que
exercitam todas as regras de análise. Permite conhecer o programa
inteiro antes de configurar as credenciais do Google Ads.
"""
from .models import (
    AccountData,
    AccountInfo,
    CampaignStats,
    KeywordStats,
    SearchTermStats,
    TodayMetrics,
)


class DemoProvider:
    """Provedor fictício: mesma interface do GoogleAdsProvider, sem rede."""

    def __init__(self, config):
        self.config = config

    def fetch_account_data(self) -> AccountData:
        campanhas = [
            CampaignStats(
                campaign_id=1, nome="Pneus para Caminhão", status="ENABLED",
                custo=1840.00, cliques=612, impressoes=14200,
                conversoes=46, valor_conversoes=0.0,
                orcamento_diario=60.00,
                orcamento_resource_name="customers/000/campaignBudgets/1",
                orcamento_compartilhado=False,
                perda_impressao_orcamento=0.28,
            ),
            CampaignStats(
                campaign_id=2, nome="Socorro de Pneu 24h", status="ENABLED",
                custo=920.00, cliques=305, impressoes=8100,
                conversoes=18, valor_conversoes=0.0,
                orcamento_diario=40.00,
                orcamento_resource_name="customers/000/campaignBudgets/2",
                orcamento_compartilhado=False,
                perda_impressao_orcamento=0.04,
            ),
            CampaignStats(
                campaign_id=3, nome="Institucional / Marca", status="ENABLED",
                custo=310.00, cliques=190, impressoes=9600,
                conversoes=0, valor_conversoes=0.0,
                orcamento_diario=15.00,
                orcamento_resource_name="customers/000/campaignBudgets/3",
                orcamento_compartilhado=False,
                perda_impressao_orcamento=0.0,
            ),
        ]
        palavras = [
            KeywordStats(1, "Pneus para Caminhão", 11, "Pneu 295", 101,
                         "pneu 295/80 caminhão", "PHRASE", "ENABLED",
                         custo=520.00, cliques=180, impressoes=3900,
                         conversoes=21, quality_score=8),
            KeywordStats(1, "Pneus para Caminhão", 11, "Pneu 295", 102,
                         "pneu de caminhão barato", "BROAD", "ENABLED",
                         custo=87.50, cliques=64, impressoes=2900,
                         conversoes=0, quality_score=4),
            KeywordStats(2, "Socorro de Pneu 24h", 21, "Socorro", 201,
                         "borracharia 24 horas caminhão", "PHRASE", "ENABLED",
                         custo=310.00, cliques=95, impressoes=2100,
                         conversoes=11, quality_score=9),
            KeywordStats(2, "Socorro de Pneu 24h", 21, "Socorro", 202,
                         "pneu remold caminhão", "BROAD", "ENABLED",
                         custo=41.00, cliques=12, impressoes=800,
                         conversoes=0, quality_score=5),
        ]
        termos = [
            SearchTermStats(1, "Pneus para Caminhão",
                            "pneu de bicicleta aro 29", custo=63.00,
                            cliques=38, conversoes=0),
            SearchTermStats(1, "Pneus para Caminhão",
                            "pneu 295/80 preço", custo=140.00,
                            cliques=52, conversoes=9),
            SearchTermStats(2, "Socorro de Pneu 24h",
                            "vaga de emprego borracheiro", custo=34.50,
                            cliques=17, conversoes=0),
        ]
        return AccountData(
            info=AccountInfo("000-000-0000", "JV Truck Pneus (DEMO)", "BRL",
                             "America/Sao_Paulo"),
            hoje=TodayMetrics(custo=94.30, cliques=41, impressoes=880,
                              conversoes=3),
            campanhas=campanhas,
            palavras=palavras,
            termos=termos,
            periodo_dias=self.config.analise.periodo_dias,
        )

    # Mutações simuladas — nada é alterado em lugar nenhum.

    def pause_keyword(self, ad_group_id: int, criterion_id: int) -> str:
        return f"[demo] palavra {criterion_id} pausada (simulação)"

    def add_negative_keyword(self, campaign_id: int, texto: str) -> str:
        return f'[demo] negativa "{texto}" adicionada (simulação)'

    def update_budget(self, budget_resource_name: str, novo_valor_reais: float) -> str:
        return f"[demo] orçamento alterado para R$ {novo_valor_reais:.2f} (simulação)"
