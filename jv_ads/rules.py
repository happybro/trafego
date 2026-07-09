"""Regras objetivas de análise do JV Ads.

Cada regra é uma função pura: recebe os dados da conta e os limiares
configurados e devolve recomendações. Nenhuma recomendação sai daqui
sem o motivo explicado com os números que a justificam.

Princípio: com amostra insuficiente a regra fica calada — recomendar
sobre ruído custa dinheiro.
"""
from __future__ import annotations

from .config import AnaliseConfig
from .models import AccountData, CampaignStats, Recommendation


def _fmt(valor: float) -> str:
    """Formata um valor em reais no padrão brasileiro."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def analisar(dados: AccountData, cfg: AnaliseConfig) -> list[Recommendation]:
    """Executa todas as regras e devolve as recomendações ordenadas:
    ações de corte de desperdício primeiro, depois oportunidades,
    depois avisos e por fim as campanhas saudáveis."""
    recs: list[Recommendation] = []
    recs += regra_palavra_sem_conversao(dados, cfg)
    recs += regra_termo_desperdicio(dados, cfg)
    recs += regra_orcamento_limitado(dados, cfg)
    recs += regra_campanha_sem_retorno(dados, cfg)
    recs += regra_campanha_saudavel(dados, cfg)

    ordem = {"PAUSAR_PALAVRA": 0, "NEGATIVAR_TERMO": 1, "AUMENTAR_ORCAMENTO": 2,
             "REVISAR": 3, "NAO_ALTERAR": 4}
    recs.sort(key=lambda r: ordem.get(r.tipo, 9))
    return recs


def _cpa_medio_conta(campanhas: list[CampaignStats]) -> float | None:
    """CPA médio da conta no período (custo total / conversões totais)."""
    custo = sum(c.custo for c in campanhas)
    conv = sum(c.conversoes for c in campanhas)
    return custo / conv if conv > 0 else None


def regra_palavra_sem_conversao(dados: AccountData, cfg: AnaliseConfig) -> list[Recommendation]:
    """Palavra que já gastou acima do limiar no período e nunca converteu → pausar."""
    recs = []
    for kw in dados.palavras:
        if kw.custo >= cfg.custo_minimo_pausar_palavra and kw.conversoes == 0:
            recs.append(Recommendation(
                tipo="PAUSAR_PALAVRA",
                titulo=f'Pausar palavra "{kw.texto}" ({kw.campaign_nome})',
                motivo=(
                    f'A palavra "{kw.texto}" gastou {_fmt(kw.custo)} nos últimos '
                    f"{dados.periodo_dias} dias ({kw.cliques} cliques, "
                    f"{kw.impressoes} impressões) e não gerou nenhuma conversão. "
                    f"Pausar corta esse gasto sem perder clientes. "
                    f"A pausa é reversível a qualquer momento."
                ),
                acao={
                    "tipo": "PAUSAR_PALAVRA",
                    "ad_group_id": kw.ad_group_id,
                    "criterion_id": kw.criterion_id,
                    "texto": kw.texto,
                },
            ))
    return recs


def regra_termo_desperdicio(dados: AccountData, cfg: AnaliseConfig) -> list[Recommendation]:
    """Termo de pesquisa que gasta sem converter → adicionar como negativa exata.

    Exige amostra mínima de cliques: um termo com 2 cliques caros ainda
    não provou que é ruim.
    """
    # Termos que já são palavras-chave da conta não devem ser negativados por engano.
    palavras_ativas = {kw.texto.lower() for kw in dados.palavras}
    recs = []
    for t in dados.termos:
        if (
            t.custo >= cfg.custo_minimo_negativar_termo
            and t.conversoes == 0
            and t.cliques >= cfg.cliques_minimos_termo
            and t.termo.lower() not in palavras_ativas
        ):
            recs.append(Recommendation(
                tipo="NEGATIVAR_TERMO",
                titulo=f'Adicionar negativa "{t.termo}" ({t.campaign_nome})',
                motivo=(
                    f'O termo pesquisado "{t.termo}" custou {_fmt(t.custo)} '
                    f"({t.cliques} cliques) nos últimos {dados.periodo_dias} dias "
                    f"sem gerar conversão. Adicionar como palavra negativa "
                    f"(correspondência exata) impede novos gastos com essa busca."
                ),
                acao={
                    "tipo": "NEGATIVAR_TERMO",
                    "campaign_id": t.campaign_id,
                    "texto": t.termo,
                },
            ))
    return recs


def regra_orcamento_limitado(dados: AccountData, cfg: AnaliseConfig) -> list[Recommendation]:
    """Campanha que converte com CPA bom mas perde impressões por orçamento → aumentar.

    Só recomenda quando a campanha comprovadamente converte melhor (ou igual)
    que a média da conta — aumentar orçamento de campanha ruim é acelerar o prejuízo.
    Orçamentos compartilhados são ignorados por segurança (afetariam outras campanhas).
    """
    cpa_conta = _cpa_medio_conta(dados.campanhas)
    recs = []
    for c in dados.campanhas:
        if (
            c.perda_impressao_orcamento >= cfg.perda_orcamento_minima
            and c.conversoes > 0
            and c.cpa is not None
            and (cpa_conta is None or c.cpa <= cpa_conta)
            and not c.orcamento_compartilhado
        ):
            novo = round(c.orcamento_diario * (1 + cfg.aumento_orcamento_pct / 100), 2)
            recs.append(Recommendation(
                tipo="AUMENTAR_ORCAMENTO",
                titulo=f'Aumentar orçamento da campanha "{c.nome}"',
                motivo=(
                    f'A campanha "{c.nome}" perdeu '
                    f"{c.perda_impressao_orcamento * 100:.0f}% das impressões por "
                    f"orçamento insuficiente, mesmo convertendo bem: "
                    f"{c.conversoes:.0f} conversões a {_fmt(c.cpa)} cada "
                    f"(média da conta: {_fmt(cpa_conta) if cpa_conta else 'n/d'}). "
                    f"Sugerido subir o orçamento diário de {_fmt(c.orcamento_diario)} "
                    f"para {_fmt(novo)} (+{cfg.aumento_orcamento_pct:.0f}%)."
                ),
                acao={
                    "tipo": "AUMENTAR_ORCAMENTO",
                    "budget_resource_name": c.orcamento_resource_name,
                    "novo_valor": novo,
                    "campanha": c.nome,
                },
            ))
    return recs


def regra_campanha_sem_retorno(dados: AccountData, cfg: AnaliseConfig) -> list[Recommendation]:
    """Campanha com gasto relevante e zero conversões → alerta para revisão manual.

    Pausar uma campanha inteira é decisão grande demais para um clique:
    o MVP alerta e explica, mas não oferece ação automática.
    """
    recs = []
    for c in dados.campanhas:
        if c.custo >= cfg.custo_minimo_revisar_campanha and c.conversoes == 0:
            recs.append(Recommendation(
                tipo="REVISAR",
                titulo=f'Revisar campanha "{c.nome}" — gasto sem retorno',
                motivo=(
                    f'A campanha "{c.nome}" gastou {_fmt(c.custo)} nos últimos '
                    f"{dados.periodo_dias} dias ({c.cliques} cliques) sem registrar "
                    f"nenhuma conversão. Antes de pausar, verifique se o "
                    f"acompanhamento de conversões está funcionando — pode ser "
                    f"problema de medição, não de campanha."
                ),
            ))
    return recs


def regra_campanha_saudavel(dados: AccountData, cfg: AnaliseConfig) -> list[Recommendation]:
    """Campanha convertendo com CPA igual ou melhor que a média → não mexer."""
    cpa_conta = _cpa_medio_conta(dados.campanhas)
    if cpa_conta is None:
        return []
    recs = []
    for c in dados.campanhas:
        if c.conversoes > 0 and c.cpa is not None and c.cpa <= cpa_conta:
            recs.append(Recommendation(
                tipo="NAO_ALTERAR",
                titulo=f'Não alterar a campanha "{c.nome}"',
                motivo=(
                    f'A campanha "{c.nome}" está saudável: {c.conversoes:.0f} '
                    f"conversões a {_fmt(c.cpa)} cada, igual ou abaixo da média "
                    f"da conta ({_fmt(cpa_conta)}). Mexer agora só adiciona risco."
                ),
            ))
    return recs
