"""Etapa 2: métricas de negócio.

Uma função por pergunta de negócio. Receita, pedidos, ticket médio e clientes
consideram sempre pedidos CONCLUÍDOS. A taxa de cancelamento olha para todos
os pedidos (qualquer status) dentro do filtro.

Todas as funções aceitam os mesmos filtros opcionais:
    categoria: nome da categoria (sem diferenciar maiúsculas/acentos) ou "Todas"
    inicio, fim: datas inclusivas no formato AAAA-MM-DD
"""

from __future__ import annotations

import pandas as pd

from .config import STATUS_CANCELADO, STATUS_CONCLUIDO
from .utils import chave

TODAS = {"", "todas", "todos"}


def _data(valor: object) -> pd.Timestamp | None:
    """Converte AAAA-MM-DD em Timestamp. Formato inválido levanta ValueError."""
    if valor is None or valor == "":
        return None
    return pd.to_datetime(valor, format="%Y-%m-%d")


def filtrar(
    df: pd.DataFrame,
    categoria: str | None = None,
    inicio: str | None = None,
    fim: str | None = None,
    status: str | None = None,
) -> pd.DataFrame:
    """Aplica os filtros comuns a todas as métricas."""
    dados = df
    if status is not None:
        dados = dados[dados["status"] == status]
    if categoria and chave(categoria) not in TODAS:
        dados = dados[dados["category"].map(chave) == chave(categoria)]
    data_inicio, data_fim = _data(inicio), _data(fim)
    if data_inicio is not None:
        dados = dados[dados["order_date"] >= data_inicio]
    if data_fim is not None:
        dados = dados[dados["order_date"] <= data_fim]
    return dados


def concluidos(df, categoria=None, inicio=None, fim=None) -> pd.DataFrame:
    return filtrar(df, categoria, inicio, fim, status=STATUS_CONCLUIDO)


def receita_total(df, categoria=None, inicio=None, fim=None) -> float:
    """Soma da receita dos pedidos concluídos."""
    return round(float(concluidos(df, categoria, inicio, fim)["revenue"].sum()), 2)


def total_pedidos(df, categoria=None, inicio=None, fim=None) -> int:
    """Quantidade de pedidos concluídos."""
    return int(concluidos(df, categoria, inicio, fim)["order_id"].nunique())


def ticket_medio(df, categoria=None, inicio=None, fim=None) -> float:
    """Receita dividida pelo número de pedidos concluídos."""
    pedidos = total_pedidos(df, categoria, inicio, fim)
    if pedidos == 0:
        return 0.0
    return round(receita_total(df, categoria, inicio, fim) / pedidos, 2)


def clientes_unicos(df, categoria=None, inicio=None, fim=None) -> int:
    """Clientes distintos com ao menos um pedido concluído."""
    return int(concluidos(df, categoria, inicio, fim)["customer_id"].nunique())


def taxa_cancelamento(df, categoria=None, inicio=None, fim=None) -> float:
    """Percentual de pedidos cancelados sobre todos os pedidos do filtro."""
    base = filtrar(df, categoria, inicio, fim)
    if base.empty:
        return 0.0
    cancelados = int((base["status"] == STATUS_CANCELADO).sum())
    return round(100 * cancelados / len(base), 2)


def receita_media_por_cliente(df, categoria=None, inicio=None, fim=None) -> float:
    """Melhoria 1: receita dividida pelos clientes únicos."""
    clientes = clientes_unicos(df, categoria, inicio, fim)
    if clientes == 0:
        return 0.0
    return round(receita_total(df, categoria, inicio, fim) / clientes, 2)


def receita_por_mes_df(df, categoria=None, inicio=None, fim=None) -> pd.DataFrame:
    """Receita mês a mês (meses sem venda aparecem com 0)."""
    dados = concluidos(df, categoria, inicio, fim)
    if dados.empty:
        return pd.DataFrame(
            {"mes": pd.Series(dtype=str), "receita": pd.Series(dtype=float)}
        )
    mensal = dados.groupby(dados["order_date"].dt.to_period("M"))["revenue"].sum()
    meses = pd.period_range(mensal.index.min(), mensal.index.max(), freq="M")
    mensal = mensal.reindex(meses, fill_value=0.0)
    return pd.DataFrame(
        {"mes": [str(m) for m in meses], "receita": mensal.round(2).to_numpy()}
    )


def receita_por_mes(df, categoria=None, inicio=None, fim=None) -> list[dict]:
    tabela = receita_por_mes_df(df, categoria, inicio, fim)
    return [
        {"mes": linha.mes, "receita": float(linha.receita)}
        for linha in tabela.itertuples(index=False)
    ]


def top_cidades_df(df, n: int = 5, categoria=None, inicio=None, fim=None) -> pd.DataFrame:
    """Melhoria 2: as N cidades que mais vendem."""
    dados = concluidos(df, categoria, inicio, fim)
    ranking = (
        dados.groupby("city", as_index=False)["revenue"]
        .sum()
        .rename(columns={"city": "cidade", "revenue": "receita"})
        .sort_values(["receita", "cidade"], ascending=[False, True])
        .head(n)
        .reset_index(drop=True)
    )
    ranking["receita"] = ranking["receita"].round(2)
    return ranking


def top_cidades(df, n: int = 5, categoria=None, inicio=None, fim=None) -> list[dict]:
    ranking = top_cidades_df(df, n, categoria, inicio, fim)
    return [
        {"cidade": linha.cidade, "receita": float(linha.receita)}
        for linha in ranking.itertuples(index=False)
    ]


def listar_categorias(df) -> list[str]:
    return sorted(str(c) for c in df["category"].unique())


def periodo_dos_dados(df) -> tuple[str, str]:
    """Primeira e última data do arquivo, como AAAA-MM-DD."""
    return (
        df["order_date"].min().strftime("%Y-%m-%d"),
        df["order_date"].max().strftime("%Y-%m-%d"),
    )
