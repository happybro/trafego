"""JV Ads — ponto de entrada.

Fluxo: conectar → baixar dados → analisar com regras adaptativas →
modo empresário (decisões, não métricas) → aplicar só com confirmação.
Cada análise grava automaticamente o resumo do dia no diário.
"""
from rich.console import Console

from . import db, rules, ui
from .config import load_config

console = Console()


def _criar_provider(cfg):
    if cfg.demo:
        from .demo import DemoProvider
        return DemoProvider(cfg)
    from .ads_api import GoogleAdsProvider
    return GoogleAdsProvider(cfg)


def _carregar(provider):
    with console.status("Baixando dados da conta..."):
        return provider.fetch_account_data()


def _analisar(dados, cfg):
    recs = rules.analisar(
        dados, cfg.analise, cfg.negocio,
        recusas=db.recusas_recentes(cfg.analise.dias_lembrar_recusa),
    )
    ui.registrar_diario(recs)  # diário automático a cada análise
    return recs


def run() -> None:
    cfg = load_config()
    if cfg.demo:
        console.print(
            "[yellow]Modo demo ativo[/yellow] — sem credenciais configuradas "
            "(ou demo forçado). Veja o README para conectar sua conta.\n"
        )

    try:
        provider = _criar_provider(cfg)
        dados = _carregar(provider)
    except Exception as exc:  # noqa: BLE001 — falha de conexão/credencial explicada ao usuário
        console.print(f"[red]Erro ao conectar na conta: {exc}[/red]")
        console.print("Confira o google-ads.yaml e o config.yaml (veja o README).")
        raise SystemExit(1) from exc

    recs = _analisar(dados, cfg)

    while True:
        ui.tela_empresario(dados, recs, cfg.demo)
        escolha = ui.menu()
        if escolha == "1":
            ui.aplicar_alteracoes(recs, provider, cfg.demo)
            # Recarrega para refletir o que acabou de mudar na conta.
            dados = _carregar(provider)
            recs = _analisar(dados, cfg)
        elif escolha == "2":
            ui.mostrar_recomendacoes(recs)
        elif escolha == "3":
            ui.mostrar_prioridades(dados, recs)
        elif escolha == "4":
            ui.mostrar_diario()
        elif escolha == "5":
            ui.mostrar_historico()
        elif escolha == "6":
            dados = _carregar(provider)
            recs = _analisar(dados, cfg)
        else:
            console.print("Até logo!")
            break


if __name__ == "__main__":
    run()
