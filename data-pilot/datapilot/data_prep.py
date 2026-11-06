"""Etapa 1: preparar o dado.

Lê o `sales.csv` bruto, converte datas, padroniza o status, remove duplicados
e cria a coluna de receita. O resultado é salvo em `sales_clean.csv` com ";"
como separador e vírgula como decimal, e lido do mesmo jeito.

Uso:
    python -m datapilot.data_prep
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .config import (
    CLEAN_CSV,
    CSV_DECIMAL,
    CSV_ENCODING,
    CSV_SEP,
    RAW_CSV,
    STATUS_CANCELADO,
    STATUS_CONCLUIDO,
    STATUS_PENDENTE,
)
from .utils import chave

COLUNAS = [
    "order_id",
    "order_date",
    "customer_id",
    "city",
    "category",
    "product",
    "quantity",
    "unit_price",
    "status",
]
COLUNAS_TEXTO = ["order_id", "customer_id", "city", "category", "product", "status"]

MAPA_STATUS = {
    "concluido": STATUS_CONCLUIDO,
    "cancelado": STATUS_CANCELADO,
    "pendente": STATUS_PENDENTE,
}
PARTICULAS = {"de", "da", "do", "dos", "das", "e"}


def _limpar_texto(valor: object) -> str | None:
    """Tira espaços sobrando; vazio vira None."""
    if valor is None or valor is pd.NA:
        return None
    if isinstance(valor, float) and pd.isna(valor):
        return None
    texto = " ".join(str(valor).split())
    return texto or None


def titulo_pt(texto: str) -> str:
    """'rio de janeiro' -> 'Rio de Janeiro'; 'ELETRÔNICOS' -> 'Eletrônicos'."""
    palavras = texto.lower().split()
    return " ".join(
        p if (i > 0 and p in PARTICULAS) else p.capitalize() for i, p in enumerate(palavras)
    )


def normalizar_status(valor: object) -> str | None:
    """' CONCLUÍDO ' -> 'concluído'. Status desconhecido vira None."""
    if valor is None:
        return None
    return MAPA_STATUS.get(chave(valor))


def parse_datas(serie: pd.Series) -> pd.Series:
    """Aceita AAAA-MM-DD e DD/MM/AAAA. O que não casar vira NaT."""
    texto = serie.astype(str).str.strip()
    iso = pd.to_datetime(texto, format="%Y-%m-%d", errors="coerce")
    br = pd.to_datetime(texto, format="%d/%m/%Y", errors="coerce")
    return iso.fillna(br)


def clean_sales(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Limpa o DataFrame bruto. Devolve (dados limpos, relatório da limpeza)."""
    faltando = [c for c in COLUNAS if c not in raw.columns]
    if faltando:
        raise ValueError(f"Colunas ausentes no CSV bruto: {', '.join(faltando)}")

    df = raw[COLUNAS].copy()
    stats: dict[str, int] = {"linhas_brutas": len(df)}

    # 1) Texto: espaços sobrando e vazios.
    for col in COLUNAS_TEXTO:
        df[col] = df[col].map(_limpar_texto)
    antes = len(df)
    df = df.dropna(subset=COLUNAS_TEXTO).copy()
    stats["campos_vazios_removidos"] = antes - len(df)

    # 2) Padronização de texto e status.
    df["city"] = df["city"].map(titulo_pt)
    df["category"] = df["category"].map(titulo_pt)
    df["status"] = df["status"].map(normalizar_status)
    antes = len(df)
    df = df[df["status"].notna()].copy()
    stats["status_invalido_removidos"] = antes - len(df)

    # 3) Datas.
    df["order_date"] = parse_datas(df["order_date"])
    antes = len(df)
    df = df[df["order_date"].notna()].copy()
    stats["datas_invalidas_removidas"] = antes - len(df)

    # 4) Números (quantidade e preço precisam ser positivos).
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    antes = len(df)
    df = df[(df["quantity"] > 0) & (df["unit_price"] > 0)].copy()
    stats["valores_invalidos_removidos"] = antes - len(df)

    # 5) Duplicados: depois de padronizar, o mesmo pedido vira a mesma linha.
    antes = len(df)
    df = df.drop_duplicates(subset="order_id", keep="first").copy()
    stats["duplicados_removidos"] = antes - len(df)

    # 6) Receita da linha.
    df["quantity"] = df["quantity"].astype(int)
    df["revenue"] = (df["quantity"] * df["unit_price"]).round(2)

    df = df.sort_values(["order_date", "order_id"]).reset_index(drop=True)
    stats["linhas_finais"] = len(df)
    return df, stats


def prepare(
    raw_path: Path = RAW_CSV, out_path: Path = CLEAN_CSV
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Lê o CSV bruto, limpa e salva o CSV limpo."""
    raw = pd.read_csv(raw_path, dtype=str, encoding="utf-8-sig")
    limpo, stats = clean_sales(raw)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    limpo.to_csv(
        out_path,
        sep=CSV_SEP,
        decimal=CSV_DECIMAL,
        encoding=CSV_ENCODING,
        index=False,
        date_format="%Y-%m-%d",
    )
    return limpo, stats


def load_clean(path: Path = CLEAN_CSV) -> pd.DataFrame:
    """Lê o CSV limpo com os mesmos parâmetros usados para salvar."""
    return pd.read_csv(
        path,
        sep=CSV_SEP,
        decimal=CSV_DECIMAL,
        encoding=CSV_ENCODING,
        parse_dates=["order_date"],
    )


def carregar_dados() -> pd.DataFrame:
    """Carrega o CSV limpo; se ele não existir, gera a partir do bruto."""
    if not CLEAN_CSV.exists():
        if not RAW_CSV.exists():
            raise FileNotFoundError(
                f"Não encontrei {RAW_CSV}. Gere os dados com "
                "`python scripts/generate_sample_data.py`."
            )
        prepare()
    return load_clean()


def main() -> None:
    parser = argparse.ArgumentParser(description="Limpa o sales.csv do Data Pilot.")
    parser.add_argument("--raw", type=Path, default=RAW_CSV, help="CSV bruto de entrada")
    parser.add_argument("--out", type=Path, default=CLEAN_CSV, help="CSV limpo de saída")
    args = parser.parse_args()

    _, stats = prepare(args.raw, args.out)
    print(f"Arquivo limpo salvo em {args.out}")
    for nome, valor in stats.items():
        print(f"  {nome.replace('_', ' '):<32} {valor:>6}")


if __name__ == "__main__":
    main()
