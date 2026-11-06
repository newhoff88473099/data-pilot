"""Fixtures compartilhadas pelos testes."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def df_exemplo() -> pd.DataFrame:
    """Seis pedidos pequenos, com resultados calculados à mão.

    Concluídos: 1, 2, 3 e 5  -> receita 650,00 | 4 pedidos | clientes C1 e C2
    Cancelado: 4  | Pendente: 6
    """
    linhas = [
        # id, data, cliente, cidade, categoria, produto, qtd, preço, status
        ("P1", "2025-01-10", "C1", "Curitiba", "Casa", "A", 2, 100.0, "concluído"),  # 200
        ("P2", "2025-01-20", "C2", "Curitiba", "Moda", "B", 1, 50.0, "concluído"),  # 50
        ("P3", "2025-02-05", "C1", "São Paulo", "Casa", "A", 1, 100.0, "concluído"),  # 100
        ("P4", "2025-02-10", "C3", "São Paulo", "Moda", "B", 3, 50.0, "cancelado"),
        ("P5", "2025-04-01", "C2", "Curitiba", "Casa", "A", 1, 300.0, "concluído"),  # 300
        ("P6", "2025-04-15", "C4", "Recife", "Moda", "B", 2, 25.0, "pendente"),
    ]
    df = pd.DataFrame(
        linhas,
        columns=["order_id", "order_date", "customer_id", "city", "category",
                 "product", "quantity", "unit_price", "status"],
    )
    df["order_date"] = pd.to_datetime(df["order_date"])
    df["revenue"] = df["quantity"] * df["unit_price"]
    return df
