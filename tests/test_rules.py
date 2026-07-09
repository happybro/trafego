"""Testes das regras adaptativas do JV Ads.

Cada teste prova duas coisas: a regra dispara quando os dados justificam
E fica calada quando a evidência é fraca. Rodar com:

    python -m tests.test_rules      (ou pytest)
"""
from jv_ads.config import AnaliseConfig, NegocioConfig
from jv_ads.models import (
    AccountData,
    AccountInfo,
    CampaignStats,
    KeywordStats,
    SearchTermStats,
    TodayMetrics,
)
from jv_ads import rules

CFG = AnaliseConfig()

# Campanha-base: dá contexto à conta (CPA médio = 500/10 = R$ 50).
def _campanha(**kw):
    base = dict(
        campaign_id=1, nome="Campanha", status="ENABLED",
        custo=500.0, cliques=100, impressoes=1000,
        conversoes=10, valor_conversoes=0.0,
        orcamento_diario=50.0,
        orcamento_resource_name="customers/000/campaignBudgets/1",
        orcamento_compartilhado=False,
        perda_impressao_orcamento=0.0,
    )
    base.update(kw)
    return CampaignStats(**base)


def _palavra(**kw):
    base = dict(
        campaign_id=1, campaign_nome="Campanha", ad_group_id=1,
        ad_group_nome="Grupo", criterion_id=1, texto="pneu caminhão",
        match_type="PHRASE", status="ENABLED",
        custo=0.0, cliques=0, impressoes=0, conversoes=0.0,
    )
    base.update(kw)
    return KeywordStats(**base)


def _dados(campanhas=None, palavras=(), termos=()):
    if campanhas is None:
        campanhas = [_campanha()]
    return AccountData(
        info=AccountInfo("000", "Teste"),
        hoje=TodayMetrics(),
        campanhas=list(campanhas),
        palavras=list(palavras),
        termos=list(termos),
        periodo_dias=30,
    )


def _analisar(dados, negocio=None, recusas=None):
    return rules.analisar(dados, CFG, negocio, recusas)


# ------------------------------------------------------- limiares adaptativos

def test_palavra_gasto_alto_sem_conversao_dispara():
    # Gastou 2x o CPA da conta (R$100 vs CPA R$50) com boa amostra.
    dados = _dados(palavras=[_palavra(custo=100.0, cliques=40)])
    recs = [r for r in _analisar(dados) if r.tipo == "PAUSAR_PALAVRA"]
    assert len(recs) == 1
    assert recs[0].aplicavel
    assert recs[0].confianca >= CFG.confianca_minima
    assert recs[0].impacto_mensal == 100  # período de 30 dias → economia = gasto
    assert recs[0].impacto_tipo == "economia"
    assert "CPA" in recs[0].motivo  # justificativa cita a referência da conta


def test_limiar_se_adapta_ao_cpa_da_conta():
    # Mesmos R$100 gastos, mas numa conta com CPA de R$200: evidência fraca.
    campanha_cara = _campanha(custo=2000.0, conversoes=10)  # CPA = 200
    dados = _dados(campanhas=[campanha_cara],
                   palavras=[_palavra(custo=100.0, cliques=40)])
    assert [r for r in _analisar(dados) if r.tipo == "PAUSAR_PALAVRA"] == []


def test_poucos_cliques_derrubam_a_confianca():
    # Gasto alto mas só 2 cliques: amostra pequena demais para agir.
    dados = _dados(palavras=[_palavra(custo=100.0, cliques=2)])
    assert [r for r in _analisar(dados) if r.tipo == "PAUSAR_PALAVRA"] == []


def test_palavra_com_conversao_nunca_e_pausada():
    dados = _dados(palavras=[_palavra(custo=400.0, cliques=90, conversoes=5)])
    assert [r for r in _analisar(dados) if r.tipo == "PAUSAR_PALAVRA"] == []


def test_conta_sem_conversao_bloqueia_cortes_e_alerta_rastreamento():
    # Conta inteira sem conversão: provável rastreamento quebrado.
    dados = _dados(campanhas=[_campanha(conversoes=0)],
                   palavras=[_palavra(custo=300.0, cliques=80)])
    recs = _analisar(dados)
    assert [r for r in recs if r.tipo == "PAUSAR_PALAVRA"] == []
    alerta = [r for r in recs if r.chave == "REVISAR:rastreamento"]
    assert len(alerta) == 1 and "rastreamento" in alerta[0].motivo


# ----------------------------------------------------------------- termos

def test_termo_desperdicio_dispara_com_evidencia():
    termo = SearchTermStats(1, "Campanha", "pneu de bicicleta",
                            custo=120.0, cliques=30, conversoes=0)
    recs = [r for r in _analisar(_dados(termos=[termo]))
            if r.tipo == "NEGATIVAR_TERMO"]
    assert len(recs) == 1
    assert recs[0].acao["texto"] == "pneu de bicicleta"
    assert recs[0].impacto_mensal == 120


def test_termo_que_e_palavra_ativa_nao_e_negativado():
    termo = SearchTermStats(1, "Campanha", "pneu caminhão",
                            custo=200.0, cliques=50, conversoes=0)
    dados = _dados(palavras=[_palavra(texto="pneu caminhão", conversoes=3,
                                      custo=50.0, cliques=20)],
                   termos=[termo])
    assert [r for r in _analisar(dados) if r.tipo == "NEGATIVAR_TERMO"] == []


# ---------------------------------------------------------------- orçamento

def test_orcamento_limitado_dispara_para_campanha_boa():
    boa = _campanha(campaign_id=1, nome="Boa", custo=500.0, conversoes=20,
                    perda_impressao_orcamento=0.30)   # CPA 25
    ruim = _campanha(campaign_id=2, nome="Ruim", custo=500.0, conversoes=5)  # CPA 100
    recs = [r for r in _analisar(_dados(campanhas=[boa, ruim]))
            if r.tipo == "AUMENTAR_ORCAMENTO"]
    assert len(recs) == 1
    assert recs[0].acao["novo_valor"] == 60.0        # 50 + 20%
    assert recs[0].impacto_unidade == "conv"         # sem valor_por_conversao → conversões
    assert recs[0].impacto_mensal == 12.0            # R$300 extras / CPA 25


def test_orcamento_com_valor_de_conversao_vira_lucro_em_reais():
    boa = _campanha(conversoes=20, custo=500.0, perda_impressao_orcamento=0.30)
    recs = [r for r in _analisar(_dados(campanhas=[boa]),
                                 negocio=NegocioConfig(valor_por_conversao=100.0))
            if r.tipo == "AUMENTAR_ORCAMENTO"]
    assert recs[0].impacto_unidade == "R$"
    assert recs[0].impacto_mensal == 900  # 12 conv × R$100 − R$300 extras


def test_orcamento_nao_recomendado_quando_retorno_nao_cobre_custo():
    boa = _campanha(conversoes=20, custo=500.0, perda_impressao_orcamento=0.30)
    recs = [r for r in _analisar(_dados(campanhas=[boa]),
                                 negocio=NegocioConfig(valor_por_conversao=20.0))
            if r.tipo == "AUMENTAR_ORCAMENTO"]
    assert recs == []  # 12 conv × R$20 = R$240 < R$300 de gasto extra


def test_orcamento_compartilhado_e_ignorado():
    c = _campanha(conversoes=20, perda_impressao_orcamento=0.30,
                  orcamento_compartilhado=True)
    assert [r for r in _analisar(_dados(campanhas=[c]))
            if r.tipo == "AUMENTAR_ORCAMENTO"] == []


def test_campanha_ruim_nao_recebe_mais_orcamento():
    boa = _campanha(campaign_id=1, custo=100.0, conversoes=20)
    ruim = _campanha(campaign_id=2, nome="Ruim", custo=400.0, conversoes=2,
                     perda_impressao_orcamento=0.30)
    assert [r for r in _analisar(_dados(campanhas=[boa, ruim]))
            if r.tipo == "AUMENTAR_ORCAMENTO"] == []


# ------------------------------------------------------- informativos e ordem

def test_campanha_sem_retorno_gera_alerta_sem_acao():
    boa = _campanha(campaign_id=1)
    ruim = _campanha(campaign_id=2, nome="Ruim", custo=300.0, cliques=80,
                     conversoes=0)
    recs = [r for r in _analisar(_dados(campanhas=[boa, ruim]))
            if r.tipo == "REVISAR"]
    assert len(recs) == 1
    assert not recs[0].aplicavel


def test_campanha_saudavel_recomenda_nao_mexer():
    boa = _campanha(campaign_id=1, nome="Boa", custo=100.0, conversoes=20)
    ruim = _campanha(campaign_id=2, nome="Ruim", custo=400.0, conversoes=2)
    recs = [r for r in _analisar(_dados(campanhas=[boa, ruim]))
            if r.tipo == "NAO_ALTERAR"]
    assert [r.titulo for r in recs] == ['Não alterar a campanha "Boa"']


def test_campanha_com_oportunidade_nao_recebe_nao_alterar():
    boa = _campanha(conversoes=20, custo=500.0, perda_impressao_orcamento=0.30)
    recs = _analisar(_dados(campanhas=[boa]))
    tipos = {r.tipo for r in recs}
    assert "AUMENTAR_ORCAMENTO" in tipos and "NAO_ALTERAR" not in tipos


def test_ordenacao_por_impacto_financeiro():
    dados = _dados(palavras=[
        _palavra(criterion_id=1, texto="menor", custo=110.0, cliques=40),
        _palavra(criterion_id=2, texto="maior", custo=250.0, cliques=60),
    ])
    recs = [r for r in _analisar(dados) if r.tipo == "PAUSAR_PALAVRA"]
    assert [r.acao["texto"] for r in recs] == ["maior", "menor"]


# --------------------------------------------------- aprendizado com o usuário

def test_recusa_recente_vira_nota_e_bloqueia_acao():
    dados = _dados(palavras=[_palavra(criterion_id=7, custo=100.0, cliques=40)])
    recs = _analisar(dados, recusas={"PAUSAR_PALAVRA:7": "palavra da marca"})
    rec = [r for r in recs if r.tipo == "PAUSAR_PALAVRA"][0]
    assert rec.recusa_anterior == "palavra da marca"
    assert not rec.aplicavel


# ------------------------------------------------------------- confiança

def test_confianca_cresce_com_gasto():
    baixa = rules.confianca_desperdicio(custo=60, cliques=40, cpa_ref=50)
    alta = rules.confianca_desperdicio(custo=300, cliques=40, cpa_ref=50)
    assert alta > baixa


def test_estrelas_formatadas():
    from jv_ads.models import Recommendation
    rec = Recommendation(tipo="X", titulo="t", motivo="m", confianca=0.82)
    assert rec.estrelas == "★★★★☆ 82%"


def _rodar_todos():
    import sys
    modulo = sys.modules[__name__]
    testes = [v for k, v in vars(modulo).items() if k.startswith("test_")]
    for t in testes:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(testes)} testes passaram.")


if __name__ == "__main__":
    _rodar_todos()
