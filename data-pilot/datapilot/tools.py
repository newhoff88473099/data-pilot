"""Etapa 5: ferramentas que o modelo pode chamar.

Cada função de `metrics.py` vira uma ferramenta com nome, descrição e
parâmetros (formato de "function calling" aceito pelo OpenRouter).
O modelo só ESCOLHE qual ferramenta chamar; quem calcula é o Python.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable

import pandas as pd

from . import metrics
from .utils import chave, formatar_brl, formatar_inteiro, formatar_pct

# ---------------------------------------------------------------- schemas ---

PARAMS_FILTRO = {
    "categoria": {
        "type": "string",
        "description": "Categoria a filtrar (ex.: Eletrônicos). Omita para considerar todas.",
    },
    "data_inicio": {
        "type": "string",
        "description": "Data inicial inclusiva, formato AAAA-MM-DD. Opcional.",
    },
    "data_fim": {
        "type": "string",
        "description": "Data final inclusiva, formato AAAA-MM-DD. Opcional.",
    },
}


def _spec(nome: str, descricao: str, filtros: bool = True, extra: dict | None = None) -> dict:
    propriedades: dict[str, Any] = {}
    if filtros:
        propriedades.update(PARAMS_FILTRO)
    propriedades.update(extra or {})
    return {
        "type": "function",
        "function": {
            "name": nome,
            "description": descricao,
            "parameters": {"type": "object", "properties": propriedades, "required": []},
        },
    }


TOOL_SPECS: list[dict] = [
    _spec(
        "receita_total",
        "Receita total em reais (soma dos pedidos concluídos). "
        "Aceita filtro por categoria e por período.",
    ),
    _spec(
        "total_pedidos",
        "Quantidade de pedidos concluídos. Aceita filtro por categoria e por período.",
    ),
    _spec(
        "ticket_medio",
        "Ticket médio em reais: receita total dividida pelo número de pedidos concluídos. "
        "Aceita filtro por categoria e por período.",
    ),
    _spec(
        "clientes_unicos",
        "Número de clientes distintos com pedidos concluídos. "
        "Aceita filtro por categoria e por período.",
    ),
    _spec(
        "taxa_cancelamento",
        "Percentual de pedidos cancelados sobre todos os pedidos (de qualquer status). "
        "Aceita filtro por categoria e por período.",
    ),
    _spec(
        "receita_media_por_cliente",
        "Receita média por cliente em reais: receita total dividida pelos clientes únicos. "
        "Aceita filtro por categoria e por período.",
    ),
    _spec(
        "receita_por_mes",
        "Receita em reais mês a mês (pedidos concluídos). "
        "Aceita filtro por categoria e por período.",
    ),
    _spec(
        "top_cidades",
        "Ranking das cidades que mais vendem, por receita em reais. "
        "Aceita filtro por categoria e por período.",
        extra={
            "n": {
                "type": "integer",
                "description": "Quantas cidades listar (de 1 a 20). Padrão: 5.",
            }
        },
    ),
    _spec(
        "listar_categorias",
        "Lista as categorias de produto existentes nos dados.",
        filtros=False,
    ),
]

# --------------------------------------------------------------- handlers ---
# Cada handler recebe (df, filtros, args) e devolve só o "miolo" do resultado.
# `filtros` já vem validado, com as chaves categoria / inicio / fim.


def _h_receita_total(df, f, args):
    valor = metrics.receita_total(df, **f)
    return {"valor": valor, "valor_formatado": formatar_brl(valor)}


def _h_total_pedidos(df, f, args):
    valor = metrics.total_pedidos(df, **f)
    return {"valor": valor, "valor_formatado": formatar_inteiro(valor)}


def _h_ticket_medio(df, f, args):
    valor = metrics.ticket_medio(df, **f)
    return {"valor": valor, "valor_formatado": formatar_brl(valor)}


def _h_clientes_unicos(df, f, args):
    valor = metrics.clientes_unicos(df, **f)
    return {"valor": valor, "valor_formatado": formatar_inteiro(valor)}


def _h_taxa_cancelamento(df, f, args):
    valor = metrics.taxa_cancelamento(df, **f)
    return {"valor": valor, "valor_formatado": formatar_pct(valor)}


def _h_receita_media_por_cliente(df, f, args):
    valor = metrics.receita_media_por_cliente(df, **f)
    return {"valor": valor, "valor_formatado": formatar_brl(valor)}


def _h_receita_por_mes(df, f, args):
    meses = metrics.receita_por_mes(df, **f)
    return {
        "meses": [
            {**m, "receita_formatada": formatar_brl(m["receita"])} for m in meses
        ]
    }


def _h_top_cidades(df, f, args):
    try:
        n = int(args.get("n", 5))
    except (TypeError, ValueError):
        n = 5
    n = max(1, min(n, 20))
    cidades = metrics.top_cidades(df, n=n, **f)
    return {
        "cidades": [
            {**c, "receita_formatada": formatar_brl(c["receita"])} for c in cidades
        ]
    }


HANDLERS: dict[str, Callable] = {
    "receita_total": _h_receita_total,
    "total_pedidos": _h_total_pedidos,
    "ticket_medio": _h_ticket_medio,
    "clientes_unicos": _h_clientes_unicos,
    "taxa_cancelamento": _h_taxa_cancelamento,
    "receita_media_por_cliente": _h_receita_media_por_cliente,
    "receita_por_mes": _h_receita_por_mes,
    "top_cidades": _h_top_cidades,
}

OBSERVACAO = (
    "Receita, pedidos, ticket médio e clientes consideram apenas pedidos concluídos; "
    "a taxa de cancelamento considera todos os pedidos."
)

# -------------------------------------------------------------- execução ---


def _ler_argumentos(argumentos: Any) -> dict:
    """O modelo manda os argumentos como texto JSON (às vezes vazio ou quebrado)."""
    if argumentos is None:
        return {}
    if isinstance(argumentos, dict):
        return argumentos
    texto = str(argumentos).strip()
    if not texto:
        return {}
    try:
        lido = json.loads(texto)
    except json.JSONDecodeError as erro:
        raise ValueError(f"Argumentos não são um JSON válido: {erro.msg}") from erro
    if not isinstance(lido, dict):
        raise ValueError("Os argumentos da ferramenta precisam ser um objeto JSON.")
    return lido


def _validar_data(valor: str, nome: str) -> str:
    try:
        datetime.strptime(str(valor), "%Y-%m-%d")
    except ValueError as erro:
        raise ValueError(f"{nome} inválida: use o formato AAAA-MM-DD (recebi '{valor}').") from erro
    return str(valor)


def execute_tool(nome: str, argumentos: Any, df: pd.DataFrame) -> dict:
    """Executa a ferramenta pedida pelo modelo, pelo nome.

    Nunca levanta exceção: erros voltam como {"erro": ...} para o modelo
    poder explicar o problema (ou tentar de novo) em vez de quebrar o app.
    """
    try:
        args = _ler_argumentos(argumentos)
    except ValueError as erro:
        return {"erro": str(erro)}

    if nome == "listar_categorias":
        return {"metrica": nome, "categorias": metrics.listar_categorias(df)}

    handler = HANDLERS.get(nome)
    if handler is None:
        return {
            "erro": f"Ferramenta desconhecida: '{nome}'.",
            "ferramentas_disponiveis": [*HANDLERS, "listar_categorias"],
        }

    # Filtros (parâmetros desconhecidos que o modelo inventar são ignorados).
    categoria = args.get("categoria")
    if categoria in (None, ""):
        categoria = None
    elif chave(categoria) in metrics.TODAS:
        categoria = None
    else:
        categorias = metrics.listar_categorias(df)
        if chave(categoria) not in {chave(c) for c in categorias}:
            return {
                "erro": f"Categoria '{categoria}' não encontrada.",
                "categorias_disponiveis": categorias,
            }
    try:
        inicio = _validar_data(args["data_inicio"], "data_inicio") if args.get("data_inicio") else None
        fim = _validar_data(args["data_fim"], "data_fim") if args.get("data_fim") else None
    except ValueError as erro:
        return {"erro": str(erro)}
    if inicio and fim and inicio > fim:
        return {"erro": "data_inicio não pode ser posterior a data_fim."}

    filtros = {"categoria": categoria, "inicio": inicio, "fim": fim}
    exibicao = {k: v for k, v in filtros.items() if v}

    try:
        miolo = handler(df, filtros, args)
    except Exception as erro:  # noqa: BLE001 - devolvemos o erro ao modelo
        return {"erro": f"Falha ao executar '{nome}': {erro}"}

    return {"metrica": nome, "filtros": exibicao, **miolo, "observacao": OBSERVACAO}
