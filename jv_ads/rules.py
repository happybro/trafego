"""Regras adaptativas de análise do JV Ads.

Nenhum limiar fixo em reais: a referência é o CPA médio da própria conta
(quanto a conta paga, em média, por uma conversão). A lógica central:

    Se uma palavra/termo gastou o suficiente para ter comprado λ
    conversões pela média da conta e trouxe ZERO, a chance de isso
    ser azar é e^-λ (Poisson). O complemento é a CONFIANÇA de que
    o gasto é desperdício de verdade.

Assim o limiar se adapta sozinho a contas grandes ou pequenas, e a
confiança sai do mesmo cálculo — sem números mágicos.

Todo impacto financeiro é estimativa honesta: economias usam o gasto
real medido; lucro em R$ só aparece quando existe valor de conversão
(da conta ou do config); caso contrário o impacto é dito em conversões.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .config import AnaliseConfig, NegocioConfig
from .models import AccountData, CampaignStats, Recommendation


def _fmt(valor: float) -> str:
    """Formata um valor em reais no padrão brasileiro."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@dataclass
class Contexto:
    """Referências extraídas da própria conta — a base das regras adaptativas."""
    cpa_medio: float | None          # custo médio por conversão da conta no período
    valor_por_conversao: float | None  # R$ por conversão (config ou medido na conta)
    fator_mensal: float              # converte o período analisado para /mês
    cpa_por_campanha: dict           # campaign_id -> CPA da campanha (quando converte)


def montar_contexto(dados: AccountData, negocio: NegocioConfig) -> Contexto:
    custo_total = sum(c.custo for c in dados.campanhas)
    conv_total = sum(c.conversoes for c in dados.campanhas)
    valor_total = sum(c.valor_conversoes for c in dados.campanhas)

    cpa_medio = custo_total / conv_total if conv_total > 0 else None

    # Prioridade do valor por conversão: o que o dono informou > o que a conta mede.
    if negocio.valor_por_conversao > 0:
        valor_conv = negocio.valor_por_conversao
    elif conv_total > 0 and valor_total > 0:
        valor_conv = valor_total / conv_total
    else:
        valor_conv = None

    return Contexto(
        cpa_medio=cpa_medio,
        valor_por_conversao=valor_conv,
        fator_mensal=30 / dados.periodo_dias,
        cpa_por_campanha={c.campaign_id: c.cpa for c in dados.campanhas if c.cpa},
    )


def confianca_desperdicio(custo: float, cliques: int, cpa_ref: float) -> float:
    """Confiança (0–1) de que um gasto sem conversão é desperdício real.

    lam = conversões que esse gasto teria comprado pela média da conta.
    P(zero conversões por azar) = e^-lam  →  confiança = 1 - e^-lam.
    O fator de amostra reduz a confiança quando há pouquíssimos cliques
    (poucos cliques caros ainda não provam um padrão).
    """
    lam = custo / cpa_ref
    prob = 1 - math.exp(-lam)
    fator_amostra = cliques / (cliques + 3)
    return prob * fator_amostra


def analisar(dados: AccountData, cfg: AnaliseConfig,
             negocio: NegocioConfig | None = None,
             recusas: dict | None = None) -> list[Recommendation]:
    """Executa todas as regras e devolve recomendações ordenadas por impacto.

    `recusas` (chave -> motivo) são recomendações que o usuário rejeitou
    recentemente: continuam visíveis como nota, mas nunca como ação.
    """
    negocio = negocio or NegocioConfig()
    ctx = montar_contexto(dados, negocio)
    recs: list[Recommendation] = []

    recs += regra_conta_sem_rastreamento(dados, ctx)
    recs += regra_palavra_sem_conversao(dados, cfg, ctx)
    recs += regra_termo_desperdicio(dados, cfg, ctx)
    recs += regra_orcamento_limitado(dados, cfg, ctx)
    recs += regra_campanha_sem_retorno(dados, cfg, ctx)
    recs += regra_campanha_saudavel(dados, ctx)

    # Coerência: campanha com oportunidade de orçamento não pode, ao mesmo
    # tempo, receber "não alterar".
    com_oportunidade = {r.chave.split(":")[1] for r in recs
                        if r.tipo == "AUMENTAR_ORCAMENTO"}
    recs = [r for r in recs if not (
        r.tipo == "NAO_ALTERAR" and r.chave.split(":")[1] in com_oportunidade)]

    # Aprendizado com o usuário: recusa recente vira nota, não ação.
    for rec in recs:
        if recusas and rec.chave in recusas:
            rec.recusa_anterior = recusas[rec.chave]

    # Maior impacto financeiro primeiro; informativos por último.
    ordem_tipo = {"PAUSAR_PALAVRA": 0, "NEGATIVAR_TERMO": 0, "AUMENTAR_ORCAMENTO": 0,
                  "REVISAR": 1, "NAO_ALTERAR": 2}
    recs.sort(key=lambda r: (ordem_tipo.get(r.tipo, 9),
                             -(r.impacto_mensal if r.impacto_unidade == "R$" else 0),
                             -r.confianca))
    return recs


def regra_conta_sem_rastreamento(dados: AccountData, ctx: Contexto) -> list[Recommendation]:
    """Conta gastando sem NENHUMA conversão registrada → problema de medição.

    Sem referência de conversão, nenhuma regra de corte roda: cortar às
    cegas pode matar exatamente o que traz clientes.
    """
    custo_total = sum(c.custo for c in dados.campanhas)
    if ctx.cpa_medio is not None or custo_total == 0:
        return []
    return [Recommendation(
        tipo="REVISAR",
        chave="REVISAR:rastreamento",
        titulo="Verificar o acompanhamento de conversões da conta",
        motivo=(
            f"A conta gastou {_fmt(custo_total)} nos últimos {dados.periodo_dias} "
            f"dias sem registrar NENHUMA conversão. O mais provável é que o "
            f"rastreamento de conversões esteja quebrado ou não configurado. "
            f"Enquanto isso não for resolvido, o JV Ads não recomenda cortes: "
            f"sem saber o que converte, pausar às cegas pode eliminar o que "
            f"traz clientes."
        ),
        confianca=0.95,
    )]


def regra_palavra_sem_conversao(dados: AccountData, cfg: AnaliseConfig,
                                ctx: Contexto) -> list[Recommendation]:
    """Palavra com gasto ≥ referência da conta e zero conversões → pausar."""
    if ctx.cpa_medio is None:
        return []
    recs = []
    for kw in dados.palavras:
        if kw.conversoes > 0 or kw.custo == 0:
            continue
        conf = confianca_desperdicio(kw.custo, kw.cliques, ctx.cpa_medio)
        if conf < cfg.confianca_minima:
            continue
        lam = kw.custo / ctx.cpa_medio
        economia = kw.custo * ctx.fator_mensal
        recs.append(Recommendation(
            tipo="PAUSAR_PALAVRA",
            chave=f"PAUSAR_PALAVRA:{kw.criterion_id}",
            titulo=f'Pausar palavra "{kw.texto}" ({kw.campaign_nome})',
            motivo=(
                f'"{kw.texto}" gastou {_fmt(kw.custo)} em {dados.periodo_dias} dias '
                f"({kw.cliques} cliques) — o suficiente para {lam:.1f} conversões "
                f"pela média da conta (CPA {_fmt(ctx.cpa_medio)}) — e trouxe zero. "
                f"A chance de isso ser só azar é {(1 - conf) * 100:.0f}%. "
                f"A pausa é reversível a qualquer momento."
            ),
            acao={"tipo": "PAUSAR_PALAVRA", "ad_group_id": kw.ad_group_id,
                  "criterion_id": kw.criterion_id, "texto": kw.texto},
            confianca=conf,
            impacto_mensal=round(economia),
            impacto_tipo="economia",
        ))
    return recs


def regra_termo_desperdicio(dados: AccountData, cfg: AnaliseConfig,
                            ctx: Contexto) -> list[Recommendation]:
    """Termo de pesquisa gastando sem converter → negativa exata na campanha."""
    if ctx.cpa_medio is None:
        return []
    palavras_ativas = {kw.texto.lower() for kw in dados.palavras}
    recs = []
    for t in dados.termos:
        if t.conversoes > 0 or t.custo == 0 or t.termo.lower() in palavras_ativas:
            continue
        # Referência: CPA da própria campanha quando ela converte; senão, da conta.
        cpa_ref = ctx.cpa_por_campanha.get(t.campaign_id, ctx.cpa_medio)
        conf = confianca_desperdicio(t.custo, t.cliques, cpa_ref)
        if conf < cfg.confianca_minima:
            continue
        economia = t.custo * ctx.fator_mensal
        recs.append(Recommendation(
            tipo="NEGATIVAR_TERMO",
            chave=f"NEGATIVAR_TERMO:{t.campaign_id}:{t.termo}",
            titulo=f'Adicionar negativa "{t.termo}" ({t.campaign_nome})',
            motivo=(
                f'A busca "{t.termo}" custou {_fmt(t.custo)} ({t.cliques} cliques) '
                f"em {dados.periodo_dias} dias sem nenhuma conversão — a campanha "
                f"converte em média a {_fmt(cpa_ref)}. A chance de ser azar é "
                f"{(1 - conf) * 100:.0f}%. A negativa exata bloqueia só essa busca, "
                f"sem afetar variações legítimas."
            ),
            acao={"tipo": "NEGATIVAR_TERMO", "campaign_id": t.campaign_id,
                  "texto": t.termo},
            confianca=conf,
            impacto_mensal=round(economia),
            impacto_tipo="economia",
        ))
    return recs


def regra_orcamento_limitado(dados: AccountData, cfg: AnaliseConfig,
                             ctx: Contexto) -> list[Recommendation]:
    """Campanha boa perdendo impressões por orçamento → aumentar orçamento.

    Só dispara quando a campanha converte com CPA igual ou melhor que a
    média da conta. A confiança cresce com o número de conversões (mais
    evidência de que o desempenho é real, não sorte).
    """
    recs = []
    for c in dados.campanhas:
        if (
            c.perda_impressao_orcamento < cfg.perda_orcamento_minima
            or c.conversoes <= 0 or c.cpa is None
            or (ctx.cpa_medio is not None and c.cpa > ctx.cpa_medio)
            or c.orcamento_compartilhado
        ):
            continue
        conf = min(0.95, c.conversoes / (c.conversoes + 8))
        novo = round(c.orcamento_diario * (1 + cfg.aumento_orcamento_pct / 100), 2)
        gasto_extra_mes = (novo - c.orcamento_diario) * 30
        conv_extras_mes = gasto_extra_mes / c.cpa

        if ctx.valor_por_conversao:
            lucro = conv_extras_mes * ctx.valor_por_conversao - gasto_extra_mes
            if lucro <= 0:
                continue  # se o retorno não cobre o gasto extra, não recomendar
            impacto, unidade = round(lucro), "R$"
            frase_impacto = (f"≈ {conv_extras_mes:.1f} conversões a mais/mês, "
                             f"valendo {_fmt(conv_extras_mes * ctx.valor_por_conversao)} "
                             f"contra {_fmt(gasto_extra_mes)} de investimento extra")
        else:
            impacto, unidade = round(conv_extras_mes, 1), "conv"
            frase_impacto = (f"≈ {conv_extras_mes:.1f} conversões a mais/mês por "
                             f"+{_fmt(gasto_extra_mes)}/mês de investimento "
                             f"(configure valor_por_conversao para ver em R$)")

        recs.append(Recommendation(
            tipo="AUMENTAR_ORCAMENTO",
            chave=f"AUMENTAR_ORCAMENTO:{c.campaign_id}",
            titulo=f'Aumentar orçamento da campanha "{c.nome}"',
            motivo=(
                f'"{c.nome}" perdeu {c.perda_impressao_orcamento * 100:.0f}% das '
                f"impressões por orçamento insuficiente, convertendo a "
                f"{_fmt(c.cpa)} ({c.conversoes:.0f} conversões — CPA "
                f"{'melhor que' if ctx.cpa_medio and c.cpa < ctx.cpa_medio else 'na'} "
                f"média da conta). Subir o orçamento de {_fmt(c.orcamento_diario)} "
                f"para {_fmt(novo)}/dia (+{cfg.aumento_orcamento_pct:.0f}%): "
                f"{frase_impacto}."
            ),
            acao={"tipo": "AUMENTAR_ORCAMENTO",
                  "budget_resource_name": c.orcamento_resource_name,
                  "novo_valor": novo, "campanha": c.nome},
            confianca=conf,
            impacto_mensal=impacto,
            impacto_tipo="lucro",
            impacto_unidade=unidade,
        ))
    return recs


def regra_campanha_sem_retorno(dados: AccountData, cfg: AnaliseConfig,
                               ctx: Contexto) -> list[Recommendation]:
    """Campanha com gasto relevante (vs. CPA da conta) e zero conversões → revisar.

    Alerta apenas: pausar campanha inteira nunca é ação de um clique.
    """
    if ctx.cpa_medio is None:
        return []
    recs = []
    for c in dados.campanhas:
        if c.conversoes > 0 or c.custo == 0:
            continue
        conf = confianca_desperdicio(c.custo, c.cliques, ctx.cpa_medio)
        if conf < cfg.confianca_minima:
            continue
        lam = c.custo / ctx.cpa_medio
        recs.append(Recommendation(
            tipo="REVISAR",
            chave=f"REVISAR:campanha:{c.campaign_id}",
            titulo=f'Revisar campanha "{c.nome}" — gasto sem retorno',
            motivo=(
                f'"{c.nome}" gastou {_fmt(c.custo)} em {dados.periodo_dias} dias — '
                f"equivalente a {lam:.1f} conversões pela média da conta — e não "
                f"registrou nenhuma. Antes de pausar, verifique se o rastreamento "
                f"de conversões cobre esta campanha; pode ser medição, não a campanha. "
                f"Se pausada, a economia seria de {_fmt(c.custo * ctx.fator_mensal)}/mês."
            ),
            confianca=conf,
            impacto_mensal=round(c.custo * ctx.fator_mensal),
            impacto_tipo="economia",
        ))
    return recs


def regra_campanha_saudavel(dados: AccountData, ctx: Contexto) -> list[Recommendation]:
    """Campanha convertendo com CPA igual ou melhor que a média → não mexer."""
    if ctx.cpa_medio is None:
        return []
    recs = []
    for c in dados.campanhas:
        if c.conversoes > 0 and c.cpa is not None and c.cpa <= ctx.cpa_medio:
            conf = min(0.95, c.conversoes / (c.conversoes + 5))
            recs.append(Recommendation(
                tipo="NAO_ALTERAR",
                chave=f"NAO_ALTERAR:{c.campaign_id}",
                titulo=f'Não alterar a campanha "{c.nome}"',
                motivo=(
                    f'"{c.nome}" está performando acima da média: {c.conversoes:.0f} '
                    f"conversões a {_fmt(c.cpa)} cada (média da conta: "
                    f"{_fmt(ctx.cpa_medio)}). Mexer agora só adiciona risco."
                ),
                confianca=conf,
            ))
    return recs
