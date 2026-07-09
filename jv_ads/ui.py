"""Interface de terminal do JV Ads (Rich).

Camada de apresentação: mostra o painel, lista recomendações e conduz
a aplicação das alterações. Toda mutação passa por confirmação explícita
do usuário, uma a uma — sem exceção.
"""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from . import db
from .models import AccountData, Recommendation

console = Console()

ICONES = {
    "PAUSAR_PALAVRA": ("✂", "red"),
    "NEGATIVAR_TERMO": ("⛔", "red"),
    "AUMENTAR_ORCAMENTO": ("▲", "green"),
    "REVISAR": ("⚠", "yellow"),
    "NAO_ALTERAR": ("✓", "cyan"),
}


def _fmt(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def mostrar_dashboard(dados: AccountData, recs: list[Recommendation], demo: bool) -> None:
    """Tela inicial: conta conectada, números de hoje e total de recomendações."""
    titulo = "[bold]JV Ads[/bold] — Análise de Google Ads"
    if demo:
        titulo += "  [yellow](MODO DEMO — dados fictícios)[/yellow]"
    console.print(Panel(titulo, style="bold blue"))

    resumo = Table(show_header=False, box=None, padding=(0, 2))
    resumo.add_row("[bold]Conta conectada[/bold]",
                   f"{dados.info.nome}  ({dados.info.customer_id})")
    resumo.add_row("[bold]Gasto hoje[/bold]", _fmt(dados.hoje.custo))
    resumo.add_row("[bold]Cliques hoje[/bold]", str(dados.hoje.cliques))
    resumo.add_row("[bold]Conversões hoje[/bold]", f"{dados.hoje.conversoes:.0f}")
    resumo.add_row("[bold]Custo (últimos "
                   f"{dados.periodo_dias} dias)[/bold]",
                   _fmt(sum(c.custo for c in dados.campanhas)))
    aplicaveis = sum(1 for r in recs if r.aplicavel)
    resumo.add_row("[bold]Recomendações[/bold]",
                   f"{len(recs)} ({aplicaveis} aplicáveis com sua confirmação)")
    console.print(Panel(resumo, title="Resumo", border_style="blue"))
    console.print(
        "[dim]Números de hoje são parciais — o Google atualiza ao longo do dia. "
        "A análise usa os últimos "
        f"{dados.periodo_dias} dias completos.[/dim]\n"
    )


def mostrar_recomendacoes(recs: list[Recommendation]) -> None:
    """Lista 'O que devo alterar hoje', com o motivo de cada item."""
    console.print(Panel("[bold]O que devo alterar hoje[/bold]", style="bold"))
    if not recs:
        console.print("[green]Nada a alterar hoje. Conta sem alertas nas regras atuais.[/green]\n")
        return
    for i, rec in enumerate(recs, 1):
        icone, cor = ICONES.get(rec.tipo, ("•", "white"))
        console.print(f"[{cor}]{icone}[/{cor}] [bold]{i}. {rec.titulo}[/bold]")
        console.print(f"   [dim]{rec.motivo}[/dim]\n")


def aplicar_alteracoes(recs: list[Recommendation], provider, demo: bool) -> None:
    """Aplica as recomendações acionáveis, confirmando UMA A UMA com o usuário."""
    aplicaveis = [r for r in recs if r.aplicavel]
    if not aplicaveis:
        console.print("[yellow]Nenhuma recomendação aplicável no momento.[/yellow]\n")
        return

    console.print(Panel(
        f"[bold]{len(aplicaveis)} alteração(ões) disponível(is).[/bold]\n"
        "Cada uma será confirmada individualmente. Nada é alterado sem o seu SIM.",
        border_style="yellow",
    ))

    aplicadas = 0
    for rec in aplicaveis:
        console.print(f"\n[bold]{rec.titulo}[/bold]")
        console.print(f"[dim]{rec.motivo}[/dim]")
        resposta = Prompt.ask(
            "Aplicar esta alteração? [bold](s/n)[/bold]",
            choices=["s", "n"], default="n", show_choices=False,
        )
        if resposta != "s":
            console.print("[dim]Pulado.[/dim]")
            continue
        try:
            resultado = _executar(rec.acao, provider)
            db.registrar_acao(rec.tipo, rec.titulo, rec.motivo, resultado)
            aplicadas += 1
            console.print(f"[green]✓ Aplicado.[/green] [dim]{resultado}[/dim]")
        except Exception as exc:  # noqa: BLE001 — erro da API vai para a tela e para o log
            db.registrar_acao(rec.tipo, rec.titulo, rec.motivo, f"ERRO: {exc}")
            console.print(f"[red]✗ Falhou: {exc}[/red]")

    console.print(f"\n[bold]{aplicadas} alteração(ões) aplicada(s).[/bold]")
    if demo and aplicadas:
        console.print("[yellow]Modo demo: nenhuma conta real foi modificada.[/yellow]")
    console.print()


def _executar(acao: dict, provider) -> str:
    """Traduz a ação da recomendação na chamada correspondente do provedor."""
    if acao["tipo"] == "PAUSAR_PALAVRA":
        return provider.pause_keyword(acao["ad_group_id"], acao["criterion_id"])
    if acao["tipo"] == "NEGATIVAR_TERMO":
        return provider.add_negative_keyword(acao["campaign_id"], acao["texto"])
    if acao["tipo"] == "AUMENTAR_ORCAMENTO":
        return provider.update_budget(acao["budget_resource_name"], acao["novo_valor"])
    raise ValueError(f"Ação desconhecida: {acao['tipo']}")


def mostrar_historico() -> None:
    """Ações já aplicadas pelo JV Ads (registro local)."""
    acoes = db.listar_acoes()
    if not acoes:
        console.print("[dim]Nenhuma ação aplicada até agora.[/dim]\n")
        return
    tabela = Table(title="Ações aplicadas", border_style="blue")
    tabela.add_column("Quando")
    tabela.add_column("Tipo")
    tabela.add_column("Alvo")
    tabela.add_column("Resultado")
    for data_hora, tipo, alvo, resultado in acoes:
        tabela.add_row(data_hora, tipo, alvo, resultado or "")
    console.print(tabela)
    console.print()


def menu() -> str:
    return Prompt.ask(
        "[bold][1][/bold] Aplicar alterações  "
        "[bold][2][/bold] Atualizar análise  "
        "[bold][3][/bold] Histórico  "
        "[bold][0][/bold] Sair",
        choices=["0", "1", "2", "3"],
        default="0",
    )
