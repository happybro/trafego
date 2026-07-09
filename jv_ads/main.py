"""JV Ads — ponto de entrada.

Fluxo: conectar → baixar dados → analisar com regras objetivas →
mostrar o que alterar hoje → aplicar (só com confirmação).
"""
from rich.console import Console

from . import rules, ui
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

    recs = rules.analisar(dados, cfg.analise)

    while True:
        ui.mostrar_dashboard(dados, recs, cfg.demo)
        ui.mostrar_recomendacoes(recs)
        escolha = ui.menu()
        if escolha == "1":
            ui.aplicar_alteracoes(recs, provider, cfg.demo)
            # Recarrega para refletir o que acabou de mudar na conta.
            dados = _carregar(provider)
            recs = rules.analisar(dados, cfg.analise)
        elif escolha == "2":
            dados = _carregar(provider)
            recs = rules.analisar(dados, cfg.analise)
        elif escolha == "3":
            ui.mostrar_historico()
        else:
            console.print("Até logo!")
            break


if __name__ == "__main__":
    run()
