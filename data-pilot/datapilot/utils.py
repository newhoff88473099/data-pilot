"""Funções pequenas de texto e formatação (padrão brasileiro)."""

from __future__ import annotations

import unicodedata


def sem_acento(texto: object) -> str:
    """Remove acentos: 'Eletrônicos' -> 'Eletronicos'."""
    decomposto = unicodedata.normalize("NFD", str(texto))
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


def chave(texto: object) -> str:
    """Chave de comparação: sem acento, sem espaços nas pontas, minúscula."""
    return sem_acento(texto).strip().lower()


def formatar_brl(valor: float) -> str:
    """1234.5 -> 'R$ 1.234,50'."""
    texto = f"{float(valor):,.2f}"
    return "R$ " + texto.replace(",", "#").replace(".", ",").replace("#", ".")


def formatar_inteiro(valor: float) -> str:
    """1234 -> '1.234'."""
    return f"{int(valor):,}".replace(",", ".")


def formatar_pct(valor: float) -> str:
    """16.667 -> '16,7%'."""
    return f"{float(valor):.1f}".replace(".", ",") + "%"
