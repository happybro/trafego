"""Interface de terminal do JV Ads (Rich).

Camada de apresentação. A tela inicial é o MODO EMPRESÁRIO: decisões,
não métricas. Toda mutação passa por confirmação explícita mostrando
o que será alterado, por quê e o impacto esperado. Quando o usuário
recusa, o motivo é salvo e respeitado nas próximas análises.
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
    "AUMENTAR_ORCAMENTO": ("📈", "green"),
    "REVISAR": ("⚠", "yellow"),
    "NAO_ALTERAR": ("✓", "cyan"),
}


def _fmt(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt0(valor: float) -> str:
    return f"R$ {valor:,.0f}".replace(",", ".")


# ------------------------------------------------------------ modo empresário

def tela_empresario(dados: AccountData, recs: list[Recommendation], demo: bool) -> None:
    """Tela inicial: o que fazer hoje e quanto isso vale. Sem mar de métricas."""
    titulo = "[bold]J V   A D S[/bold]"
    if demo:
        titulo += "   [yellow](MODO DEMO — dados fictícios)[/yellow]"
    console.print(Panel(titulo, style="bold blue", subtitle=(
        f"{dados.info.nome} · gasto hoje {_fmt(dados.hoje.custo)} · "
        f"{dados.hoje.cliques} cliques · {dados.hoje.conversoes:.0f} conversões"
    )))

    pausas = [r for r in recs if r.tipo == "PAUSAR_PALAVRA" and r.aplicavel]
    negativas = [r for r in recs if r.tipo == "NEGATIVAR_TERMO" and r.aplicavel]
    orcamentos = [r for r in recs if r.tipo == "AUMENTAR_ORCAMENTO" and r.aplicavel]
    revisar = [r for r in recs if r.tipo == "REVISAR"]
    saudaveis = [r for r in recs if r.tipo == "NAO_ALTERAR"]
    recusadas = [r for r in recs if r.recusa_anterior]

    linhas: list[str] = ["[bold]Hoje faça apenas isso:[/bold]\n"]

    cortes = pausas + negativas
    if cortes:
        economia = sum(r.impacto_mensal for r in cortes)
        acoes = []
        if pausas:
            acoes.append(f"pausar {len(pausas)} palavra(s)")
        if negativas:
            acoes.append(f"negativar {len(negativas)} termo(s)")
        linhas.append(f"✅ [bold]Cortar desperdício:[/bold] {' e '.join(acoes)}")
        linhas.append(f"   Economia estimada: [bold green]{_fmt0(economia)}/mês[/bold green]")
        pior = max(cortes, key=lambda r: r.impacto_mensal)
        linhas.append(f"   Maior ralo: {pior.titulo}  [dim]{pior.estrelas}[/dim]\n")

    for r in orcamentos:
        linhas.append(f"📈 [bold]{r.titulo}[/bold]")
        sufixo = "/mês" if r.impacto_unidade == "R$" else " conversões/mês"
        valor = _fmt0(r.impacto_mensal) if r.impacto_unidade == "R$" else f"+{r.impacto_mensal:.1f}"
        rotulo = "Lucro potencial" if r.impacto_unidade == "R$" else "Retorno estimado"
        linhas.append(f"   {rotulo}: [bold green]+{valor.lstrip('+')}{sufixo}[/bold green]"
                      f"  [dim]{r.estrelas}[/dim]\n")

    for r in revisar:
        linhas.append(f"⚠ [bold]{r.titulo}[/bold]  [dim]{r.estrelas}[/dim]\n")

    for r in saudaveis[:2]:
        nome = r.titulo.replace("Não alterar a campanha ", "")
        linhas.append(f"❌ [bold]Não altere[/bold] {nome}")
        linhas.append("   Motivo: está performando acima da média.\n")

    if recusadas:
        linhas.append(f"[dim]{len(recusadas)} recomendação(ões) omitida(s) porque você "
                      f"recusou recentemente (veja na análise detalhada).[/dim]")

    if not cortes and not orcamentos and not revisar:
        linhas.append("[green]Nada a alterar hoje. A conta está dentro das regras — "
                      "mexer agora seria risco sem retorno.[/green]")

    console.print(Panel("\n".join(linhas), border_style="blue"))


# --------------------------------------------------------- análise detalhada

def mostrar_recomendacoes(recs: list[Recommendation]) -> None:
    """Lista completa, com confiança e impacto de cada recomendação."""
    console.print(Panel("[bold]Análise detalhada — o que devo alterar hoje[/bold]",
                        style="bold"))
    if not recs:
        console.print("[green]Nenhuma recomendação nas regras atuais.[/green]\n")
        return
    for i, rec in enumerate(recs, 1):
        icone, cor = ICONES.get(rec.tipo, ("•", "white"))
        console.print(f"[{cor}]{icone}[/{cor}] [bold]{i}. {rec.titulo}[/bold]  "
                      f"[cyan]{rec.estrelas}[/cyan]")
        if rec.impacto_texto:
            console.print(f"   [green]{rec.impacto_texto}[/green]")
        console.print(f"   [dim]{rec.motivo}[/dim]")
        if rec.recusa_anterior:
            console.print(f"   [yellow]Você recusou esta ação recentemente "
                          f'(motivo: "{rec.recusa_anterior}") — não será oferecida.[/yellow]')
        console.print()


# ------------------------------------------------------------------ ranking

def mostrar_prioridades(dados: AccountData, recs: list[Recommendation]) -> None:
    """Onde atacar primeiro, ordenado por impacto financeiro."""
    desperdicios = sorted(
        [r for r in recs if r.impacto_tipo == "economia"],
        key=lambda r: -r.impacto_mensal)
    oportunidades = sorted(
        [r for r in recs if r.impacto_tipo == "lucro"],
        key=lambda r: -(r.impacto_mensal if r.impacto_unidade == "R$" else 0))

    if desperdicios:
        t = Table(title="TOP Desperdícios (ataque primeiro)", border_style="red")
        t.add_column("#"); t.add_column("Ação"); t.add_column("Economia/mês",
                                                              justify="right")
        t.add_column("Confiança")
        for i, r in enumerate(desperdicios[:5], 1):
            t.add_row(str(i), r.titulo, _fmt0(r.impacto_mensal), r.estrelas)
        console.print(t)

    if oportunidades:
        t = Table(title="TOP Oportunidades", border_style="green")
        t.add_column("#"); t.add_column("Ação"); t.add_column("Retorno/mês",
                                                              justify="right")
        t.add_column("Confiança")
        for i, r in enumerate(oportunidades[:5], 1):
            valor = (_fmt0(r.impacto_mensal) if r.impacto_unidade == "R$"
                     else f"+{r.impacto_mensal:.1f} conv")
            t.add_row(str(i), r.titulo, valor, r.estrelas)
        console.print(t)

    com_conv = [c for c in dados.campanhas if c.conversoes > 0]
    if com_conv:
        t = Table(title="TOP Campanhas (por conversões e CPA)", border_style="blue")
        t.add_column("Campanha"); t.add_column("Conversões", justify="right")
        t.add_column("CPA", justify="right"); t.add_column("Custo", justify="right")
        for c in sorted(com_conv, key=lambda c: (-c.conversoes, c.cpa or 0))[:5]:
            t.add_row(c.nome, f"{c.conversoes:.0f}", _fmt(c.cpa), _fmt(c.custo))
        console.print(t)

    kw_conv = [k for k in dados.palavras if k.conversoes > 0]
    if kw_conv:
        t = Table(title="TOP Palavras (as que trazem clientes)", border_style="blue")
        t.add_column("Palavra"); t.add_column("Conversões", justify="right")
        t.add_column("CPA", justify="right"); t.add_column("Custo", justify="right")
        for k in sorted(kw_conv, key=lambda k: -k.conversoes)[:5]:
            t.add_row(k.texto, f"{k.conversoes:.0f}",
                      _fmt(k.custo / k.conversoes), _fmt(k.custo))
        console.print(t)
    console.print()


# ------------------------------------------------------------------- aplicar

def aplicar_alteracoes(recs: list[Recommendation], provider, demo: bool) -> None:
    """Aplica recomendações UMA A UMA: o quê, por quê, impacto → confirmação.

    Recusas são registradas com o motivo e respeitadas nas próximas análises.
    """
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
        console.print(f"\n[bold]O que será alterado:[/bold] {rec.titulo}")
        console.print(f"[bold]Por quê:[/bold] [dim]{rec.motivo}[/dim]")
        if rec.impacto_texto:
            console.print(f"[bold]Impacto esperado:[/bold] [green]{rec.impacto_texto}[/green]")
        console.print(f"[bold]Confiança:[/bold] [cyan]{rec.estrelas}[/cyan]")
        resposta = Prompt.ask(
            "Aplicar esta alteração? [bold](s/n)[/bold]",
            choices=["s", "n"], default="n", show_choices=False,
        )
        if resposta != "s":
            motivo = Prompt.ask("Qual o motivo? (Enter para pular)", default="")
            db.registrar_recusa(rec.chave, rec.titulo, motivo)
            console.print("[dim]Anotado — não vou insistir nesta recomendação "
                          "pelos próximos 30 dias.[/dim]")
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


# ------------------------------------------------------------ diário e histórico

def registrar_diario(recs: list[Recommendation]) -> None:
    """Resumo automático da análise de hoje, salvo no banco."""
    desperdicios = [r for r in recs if r.impacto_tipo == "economia"]
    oportunidades = [r for r in recs if r.impacto_tipo == "lucro"]
    saudaveis = [r for r in recs if r.tipo == "NAO_ALTERAR"]
    maior = max(desperdicios, key=lambda r: r.impacto_mensal).titulo if desperdicios else ""
    melhor = (saudaveis[0].titulo.replace("Não alterar a campanha ", "").strip('"')
              if saudaveis else "")
    db.registrar_diario(
        desperdicios=len(desperdicios),
        oportunidades=len(oportunidades),
        economia_estimada=sum(r.impacto_mensal for r in desperdicios),
        maior_problema=maior,
        melhor_campanha=melhor,
    )


def mostrar_diario() -> None:
    """Consulta do diário: um resumo por dia analisado."""
    dias = db.listar_diario()
    if not dias:
        console.print("[dim]Nenhuma análise registrada ainda.[/dim]\n")
        return
    for data, desp, oport, economia, maior, melhor in dias:
        corpo = [f"Encontrei [bold]{desp} desperdício(s)[/bold] e "
                 f"[bold]{oport} oportunidade(s)[/bold].",
                 f"Economia estimada: [green]{_fmt0(economia)}/mês[/green]"]
        if maior:
            corpo.append(f"Maior problema: {maior}")
        if melhor:
            corpo.append(f"Melhor campanha: {melhor}")
        console.print(Panel("\n".join(corpo), title=f"[bold]{data}[/bold]",
                            border_style="blue"))
    console.print()


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
        "[bold][1][/bold] Aplicar  [bold][2][/bold] Análise detalhada  "
        "[bold][3][/bold] Prioridades  [bold][4][/bold] Diário  "
        "[bold][5][/bold] Histórico  [bold][6][/bold] Atualizar  [bold][0][/bold] Sair",
        choices=["0", "1", "2", "3", "4", "5", "6"],
        default="0",
    )
