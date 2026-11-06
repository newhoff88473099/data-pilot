import pytest

from datapilot import metrics
from datapilot.utils import formatar_brl, formatar_inteiro, formatar_pct


def test_metricas_basicas_so_contam_concluidos(df_exemplo):
    assert metrics.receita_total(df_exemplo) == 650.0
    assert metrics.total_pedidos(df_exemplo) == 4
    assert metrics.ticket_medio(df_exemplo) == 162.5
    assert metrics.clientes_unicos(df_exemplo) == 2


def test_taxa_de_cancelamento_olha_todos_os_pedidos(df_exemplo):
    assert metrics.taxa_cancelamento(df_exemplo) == pytest.approx(16.67)


def test_filtro_de_categoria_ignora_caixa_e_acento(df_exemplo):
    assert metrics.receita_total(df_exemplo, categoria="Casa") == 600.0
    assert metrics.receita_total(df_exemplo, categoria="CASA") == 600.0
    assert metrics.total_pedidos(df_exemplo, categoria="casa") == 3
    assert metrics.ticket_medio(df_exemplo, categoria="Casa") == 200.0
    assert metrics.receita_total(df_exemplo, categoria="Todas") == 650.0


def test_filtro_de_periodo_e_inclusivo(df_exemplo):
    assert metrics.receita_total(df_exemplo, inicio="2025-02-01", fim="2025-02-28") == 100.0
    assert metrics.receita_total(df_exemplo, inicio="2025-01-10", fim="2025-01-10") == 200.0
    assert metrics.total_pedidos(df_exemplo, inicio="2026-01-01") == 0


def test_filtro_vazio_nao_quebra(df_exemplo):
    assert metrics.ticket_medio(df_exemplo, inicio="2026-01-01") == 0.0
    assert metrics.receita_media_por_cliente(df_exemplo, inicio="2026-01-01") == 0.0
    assert metrics.taxa_cancelamento(df_exemplo, inicio="2026-01-01") == 0.0
    assert metrics.receita_por_mes(df_exemplo, inicio="2026-01-01") == []


def test_data_em_formato_errado_levanta_erro(df_exemplo):
    with pytest.raises(ValueError):
        metrics.receita_total(df_exemplo, inicio="10/01/2025")


def test_receita_media_por_cliente(df_exemplo):
    assert metrics.receita_media_por_cliente(df_exemplo) == 325.0


def test_receita_por_mes_preenche_meses_sem_venda(df_exemplo):
    meses = metrics.receita_por_mes(df_exemplo)
    assert meses == [
        {"mes": "2025-01", "receita": 250.0},
        {"mes": "2025-02", "receita": 100.0},
        {"mes": "2025-03", "receita": 0.0},
        {"mes": "2025-04", "receita": 300.0},
    ]


def test_top_cidades_ordena_por_receita(df_exemplo):
    assert metrics.top_cidades(df_exemplo, n=5) == [
        {"cidade": "Curitiba", "receita": 550.0},
        {"cidade": "São Paulo", "receita": 100.0},
    ]
    assert len(metrics.top_cidades(df_exemplo, n=1)) == 1


def test_listar_categorias_e_periodo(df_exemplo):
    assert metrics.listar_categorias(df_exemplo) == ["Casa", "Moda"]
    assert metrics.periodo_dos_dados(df_exemplo) == ("2025-01-10", "2025-04-15")


def test_formatacao_brasileira():
    assert formatar_brl(1234.5) == "R$ 1.234,50"
    assert formatar_brl(0) == "R$ 0,00"
    assert formatar_brl(1234567.891) == "R$ 1.234.567,89"
    assert formatar_inteiro(1473) == "1.473"
    assert formatar_pct(9.31) == "9,3%"
