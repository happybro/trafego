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
    """Limiares das regras. Todos configuráveis no config.yaml."""
    periodo_dias: int = 30
    custo_minimo_pausar_palavra: float = 50.0   # R$ gastos sem conversão para sugerir pausa
    custo_minimo_negativar_termo: float = 30.0  # R$ gastos por termo sem conversão
    cliques_minimos_termo: int = 5              # amostra mínima para negativar termo
    perda_orcamento_minima: float = 0.10        # 10% de impressões perdidas por orçamento
    aumento_orcamento_pct: float = 20.0         # % de aumento sugerido
    custo_minimo_revisar_campanha: float = 150.0


@dataclass
class AppConfig:
    customer_id: str = ""
    demo: bool = False
    analise: AnaliseConfig = field(default_factory=AnaliseConfig)

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

    if os.environ.get("JV_ADS_DEMO") == "1":
        cfg.demo = True

    # Sem credenciais ou sem conta configurada não há como conectar: modo demo.
    if not cfg.demo and (not GOOGLE_ADS_YAML.exists() or not cfg.customer_id):
        cfg.demo = True

    return cfg
