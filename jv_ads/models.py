"""Modelos de dados do JV Ads.

Estruturas simples (dataclasses) que circulam entre a API, as regras
de análise e a interface. Nenhuma dependência do Google Ads aqui.
"""
from dataclasses import dataclass, field
from typing import Optional


def brl(micros: int) -> float:
    """Converte micros (unidade da API do Google Ads) para reais."""
    return micros / 1_000_000


@dataclass
class AccountInfo:
    customer_id: str
    nome: str
    moeda: str = "BRL"
    fuso: str = "America/Sao_Paulo"


@dataclass
class TodayMetrics:
    """Métricas do dia corrente (parciais — o Google atualiza ao longo do dia)."""
    custo: float = 0.0
    cliques: int = 0
    impressoes: int = 0
    conversoes: float = 0.0


@dataclass
class CampaignStats:
    """Métricas agregadas de uma campanha no período de análise."""
    campaign_id: int
    nome: str
    status: str
    custo: float
    cliques: int
    impressoes: int
    conversoes: float
    valor_conversoes: float
    orcamento_diario: float
    orcamento_resource_name: str
    orcamento_compartilhado: bool
    perda_impressao_orcamento: float  # 0.0 a 1.0 (parcela de impressões perdidas por orçamento)

    @property
    def cpa(self) -> Optional[float]:
        """Custo por conversão. None quando não há conversões."""
        return self.custo / self.conversoes if self.conversoes > 0 else None


@dataclass
class KeywordStats:
    """Métricas agregadas de uma palavra-chave no período de análise."""
    campaign_id: int
    campaign_nome: str
    ad_group_id: int
    ad_group_nome: str
    criterion_id: int
    texto: str
    match_type: str
    status: str
    custo: float
    cliques: int
    impressoes: int
    conversoes: float
    quality_score: Optional[int] = None


@dataclass
class SearchTermStats:
    """Métricas agregadas de um termo de pesquisa no período de análise."""
    campaign_id: int
    campaign_nome: str
    termo: str
    custo: float
    cliques: int
    conversoes: float


@dataclass
class Recommendation:
    """Uma recomendação gerada pelas regras de análise.

    `acao` descreve a mutação a executar quando o usuário confirmar.
    Quando `acao` é None a recomendação é apenas informativa
    (ex.: "não alterar", "revisar manualmente").
    """
    tipo: str          # PAUSAR_PALAVRA | NEGATIVAR_TERMO | AUMENTAR_ORCAMENTO | NAO_ALTERAR | REVISAR
    titulo: str        # frase curta exibida na lista
    motivo: str        # explicação com os dados que justificam
    acao: Optional[dict] = None

    @property
    def aplicavel(self) -> bool:
        return self.acao is not None


@dataclass
class AccountData:
    """Tudo que a análise precisa, já carregado da conta."""
    info: AccountInfo
    hoje: TodayMetrics
    campanhas: list = field(default_factory=list)      # list[CampaignStats]
    palavras: list = field(default_factory=list)       # list[KeywordStats]
    termos: list = field(default_factory=list)         # list[SearchTermStats]
    periodo_dias: int = 30
