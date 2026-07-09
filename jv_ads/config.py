"""Carregamento de configuração do JV Ads.

Dois arquivos, ambos fora do controle de versão:
  - google-ads.yaml : credenciais da API (formato padrão da biblioteca google-ads)
  - config.yaml     : ID da conta e parâmetros de análise
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.yaml"
GOOGLE_ADS_YAML = BASE_DIR / "google-ads.yaml"


@dataclass
class AnaliseConfig:
    """Parâmetros das regras adaptativas.

    Não há valores fixos em reais: os limiares derivam do CPA médio da
    própria conta. Aqui ficam apenas os parâmetros de sensibilidade.
    """
    periodo_dias: int = 30
    confianca_minima: float = 0.75       # só recomendar corte com ≥ 75% de confiança
    perda_orcamento_minima: float = 0.10 # fração de impressões perdidas por orçamento
    aumento_orcamento_pct: float = 20.0  # % de aumento de orçamento sugerido
    dias_lembrar_recusa: int = 30        # por quantos dias respeitar um "não quero"


@dataclass
class NegocioConfig:
    """Dados do negócio que a API do Google não conhece.

    valor_por_conversao: quanto vale, em média, uma conversão para a
    empresa (em R$ de lucro bruto). Opcional — sem ele, o impacto de
    oportunidades é mostrado em conversões/mês, nunca em reais inventados.
    """
    valor_por_conversao: float = 0.0


@dataclass
class AppConfig:
    customer_id: str = ""
    demo: bool = False
    analise: AnaliseConfig = field(default_factory=AnaliseConfig)
    negocio: NegocioConfig = field(default_factory=NegocioConfig)

    @property
    def customer_id_digits(self) -> str:
        return self.customer_id.replace("-", "").replace(" ", "")


def load_config() -> AppConfig:
    """Lê config.yaml se existir; cai para o modo demo quando não há credenciais."""
    cfg = AppConfig()

    if CONFIG_PATH.exists():
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        cfg.customer_id = str(raw.get("customer_id", "") or "")
        cfg.demo = bool(raw.get("demo", False))
        for chave, valor in (raw.get("analise") or {}).items():
            if hasattr(cfg.analise, chave):
                setattr(cfg.analise, chave, type(getattr(cfg.analise, chave))(valor))
        for chave, valor in (raw.get("negocio") or {}).items():
            if hasattr(cfg.negocio, chave):
                setattr(cfg.negocio, chave, type(getattr(cfg.negocio, chave))(valor))

    if os.environ.get("JV_ADS_DEMO") == "1":
        cfg.demo = True

    # Sem credenciais ou sem conta configurada não há como conectar: modo demo.
    if not cfg.demo and (not GOOGLE_ADS_YAML.exists() or not cfg.customer_id):
        cfg.demo = True

    return cfg
