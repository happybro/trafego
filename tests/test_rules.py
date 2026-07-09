"""Testes das regras de análise do JV Ads.

Cada teste prova duas coisas: a regra dispara quando deve E fica
calada quando a amostra é insuficiente. Rodar com:

    python -m tests.test_rules      (ou pytest)
"""
from jv_ads.config import AnaliseConfig
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


def _dados(campanhas=(), palavras=(), termos=()):
    return AccountData(
        info=AccountInfo("000", "Teste"),
        hoje=TodayMetrics(),
        campanhas=list(campanhas),
        palavras=list(palavras),
        termos=list(termos),
        periodo_dias=30,
    )


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


def test_palavra_sem_conversao_dispara():
    dados = _dados(palavras=[_palavra(custo=80.0, cliques=40, conversoes=0)])
    recs = rules.regra_palavra_sem_conversao(dados, CFG)
    assert len(recs) == 1
    assert recs[0].tipo == "PAUSAR_PALAVRA"
    assert recs[0].aplicavel
    assert "80,00" in recs[0].motivo  # o motivo cita o gasto


def test_palavra_abaixo_do_limiar_fica_calada():
    dados = _dados(palavras=[_palavra(custo=20.0, cliques=15, conversoes=0)])
    assert rules.regra_palavra_sem_conversao(dados, CFG) == []


def test_palavra_com_conversao_nao_e_pausada():
    dados = _dados(palavras=[_palavra(custo=300.0, cliques=90, conversoes=5)])
    assert rules.regra_palavra_sem_conversao(dados, CFG) == []


def test_termo_desperdicio_dispara():
    termo = SearchTermStats(1, "Campanha", "pneu de bicicleta",
                            custo=45.0, cliques=20, conversoes=0)
    recs = rules.regra_termo_desperdicio(_dados(termos=[termo]), CFG)
    assert len(recs) == 1
    assert recs[0].tipo == "NEGATIVAR_TERMO"
    assert recs[0].acao["texto"] == "pneu de bicicleta"


def test_termo_com_poucos_cliques_fica_calado():
    termo = SearchTermStats(1, "Campanha", "pneu de bicicleta",
                            custo=45.0, cliques=2, conversoes=0)
    assert rules.regra_termo_desperdicio(_dados(termos=[termo]), CFG) == []


def test_termo_que_e_palavra_ativa_nao_e_negativado():
    termo = SearchTermStats(1, "Campanha", "pneu caminhão",
                            custo=90.0, cliques=30, conversoes=0)
    palavra = _palavra(texto="pneu caminhão")
    assert rules.regra_termo_desperdicio(
        _dados(palavras=[palavra], termos=[termo]), CFG) == []


def test_orcamento_limitado_dispara_para_campanha_boa():
    boa = _campanha(campaign_id=1, nome="Boa", custo=400.0, conversoes=20,
                    perda_impressao_orcamento=0.30)
    ruim = _campanha(campaign_id=2, nome="Ruim", custo=400.0, conversoes=4)
    recs = rules.regra_orcamento_limitado(_dados(campanhas=[boa, ruim]), CFG)
    assert len(recs) == 1
    assert recs[0].acao["novo_valor"] == 60.0  # 50 + 20%


def test_orcamento_compartilhado_e_ignorado():
    c = _campanha(conversoes=20, perda_impressao_orcamento=0.30,
                  orcamento_compartilhado=True)
    assert rules.regra_orcamento_limitado(_dados(campanhas=[c]), CFG) == []


def test_campanha_ruim_nao_recebe_mais_orcamento():
    boa = _campanha(campaign_id=1, nome="Boa", custo=100.0, conversoes=20)
    ruim = _campanha(campaign_id=2, nome="Ruim", custo=400.0, conversoes=2,
                     perda_impressao_orcamento=0.30)
    assert rules.regra_orcamento_limitado(_dados(campanhas=[boa, ruim]), CFG) == []


def test_campanha_sem_retorno_gera_alerta_sem_acao():
    c = _campanha(custo=200.0, conversoes=0)
    recs = rules.regra_campanha_sem_retorno(_dados(campanhas=[c]), CFG)
    assert len(recs) == 1
    assert recs[0].tipo == "REVISAR"
    assert not recs[0].aplicavel  # alerta, nunca ação automática


def test_campanha_saudavel_recomenda_nao_mexer():
    boa = _campanha(campaign_id=1, nome="Boa", custo=100.0, conversoes=20)
    ruim = _campanha(campaign_id=2, nome="Ruim", custo=400.0, conversoes=2)
    recs = rules.regra_campanha_saudavel(_dados(campanhas=[boa, ruim]), CFG)
    assert [r.titulo for r in recs] == ['Não alterar a campanha "Boa"']


def test_analisar_ordena_desperdicio_primeiro():
    dados = _dados(
        campanhas=[_campanha(conversoes=20, perda_impressao_orcamento=0.30)],
        palavras=[_palavra(custo=80.0, cliques=40, conversoes=0)],
    )
    recs = rules.analisar(dados, CFG)
    tipos = [r.tipo for r in recs]
    assert tipos.index("PAUSAR_PALAVRA") < tipos.index("AUMENTAR_ORCAMENTO")


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
