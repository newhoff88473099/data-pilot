import pandas as pd

from datapilot.data_prep import clean_sales, load_clean, normalizar_status, parse_datas, prepare, titulo_pt


def _bruto() -> pd.DataFrame:
    linhas = [
        # ok, data ISO, status com acento e espaços
        ("P1", "2025-03-04", "C1", " curitiba ", "ELETRÔNICOS", "Fone", "2", "189.90", " CONCLUÍDO "),
        # mesma data em formato brasileiro; sem acento
        ("P2", "04/03/2025", "C2", "rio de janeiro", "casa", "Panela", "1", "100.00", "concluido"),
        # duplicado de P1 (outra grafia)
        ("P1", "2025-03-04", "C1", "Curitiba", "Eletrônicos", "Fone", "2", "189.90", "Concluido"),
        # data impossível
        ("P3", "31/02/2025", "C3", "Recife", "Moda", "Tênis", "1", "300.00", "pendente"),
        # quantidade negativa
        ("P4", "2025-03-05", "C4", "Recife", "Moda", "Tênis", "-1", "300.00", "cancelado"),
        # status desconhecido
        ("P5", "2025-03-05", "C5", "Recife", "Moda", "Tênis", "1", "300.00", "devolvido"),
        # campo vazio
        ("P6", "2025-03-05", "", "Recife", "Moda", "Tênis", "1", "300.00", "pendente"),
    ]
    return pd.DataFrame(
        linhas,
        columns=["order_id", "order_date", "customer_id", "city", "category",
                 "product", "quantity", "unit_price", "status"],
    )


def test_normalizar_status_ignora_acento_caixa_e_espacos():
    assert normalizar_status(" CONCLUÍDO ") == "concluído"
    assert normalizar_status("Cancelado") == "cancelado"
    assert normalizar_status("PENDENTE") == "pendente"
    assert normalizar_status("devolvido") is None


def test_titulo_pt_mantem_particulas_minusculas():
    assert titulo_pt("rio de janeiro") == "Rio de Janeiro"
    assert titulo_pt("ELETRÔNICOS") == "Eletrônicos"


def test_parse_datas_aceita_dois_formatos():
    datas = parse_datas(pd.Series(["2025-03-04", "04/03/2025", "31/02/2025", "lixo"]))
    assert datas.iloc[0] == pd.Timestamp("2025-03-04")
    assert datas.iloc[1] == pd.Timestamp("2025-03-04")  # dia/mês, não mês/dia
    assert datas.iloc[2:].isna().all()


def test_clean_sales_aplica_todas_as_regras():
    limpo, stats = clean_sales(_bruto())

    assert list(limpo["order_id"]) == ["P1", "P2"]
    assert set(limpo["status"]) == {"concluído"}
    assert list(limpo["city"]) == ["Curitiba", "Rio de Janeiro"]
    assert list(limpo["category"]) == ["Eletrônicos", "Casa"]
    assert limpo["revenue"].tolist() == [379.8, 100.0]
    assert stats["linhas_brutas"] == 7
    assert stats["duplicados_removidos"] == 1
    assert stats["datas_invalidas_removidas"] == 1
    assert stats["valores_invalidos_removidos"] == 1
    assert stats["status_invalido_removidos"] == 1
    assert stats["campos_vazios_removidos"] == 1
    assert stats["linhas_finais"] == 2


def test_csv_limpo_usa_ponto_e_virgula_e_virgula_decimal(tmp_path):
    bruto = tmp_path / "sales.csv"
    saida = tmp_path / "limpo.csv"
    _bruto().to_csv(bruto, index=False)

    limpo, _ = prepare(bruto, saida)
    texto = saida.read_text(encoding="utf-8-sig")

    assert texto.splitlines()[0].count(";") == 9
    assert "189,9" in texto and "189.9" not in texto

    relido = load_clean(saida)
    assert pd.api.types.is_datetime64_any_dtype(relido["order_date"])
    assert relido["revenue"].tolist() == limpo["revenue"].tolist()
    assert relido["unit_price"].dtype.kind == "f"
