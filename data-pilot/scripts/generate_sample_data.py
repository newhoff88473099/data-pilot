"""Gera o `data/sales.csv`: vendas sintéticas e propositalmente "sujas".

Os dados são fictícios (semente fixa, então o resultado é reproduzível).
A sujeira é de propósito, para a etapa de limpeza ter o que fazer:
datas em dois formatos, status com variações, textos com espaços e caixa
misturada, pedidos duplicados e algumas linhas inválidas.

Uso:
    python scripts/generate_sample_data.py
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
N_PEDIDOS = 1800
INICIO = date(2025, 1, 1)
FIM = date(2026, 10, 31)
SAIDA = Path(__file__).resolve().parent.parent / "data" / "sales.csv"

CATALOGO = {
    "Eletrônicos": [
        ("Fone Bluetooth", 189.90),
        ("Smartwatch", 459.00),
        ("Carregador Turbo", 79.90),
        ("Caixa de Som", 249.00),
    ],
    "Casa": [
        ("Air Fryer", 399.00),
        ("Jogo de Panelas", 289.90),
        ("Aspirador Robô", 899.00),
        ("Cafeteira", 229.00),
    ],
    "Moda": [
        ("Tênis Esportivo", 329.90),
        ("Camiseta Básica", 59.90),
        ("Jaqueta Jeans", 249.90),
        ("Mochila", 149.90),
    ],
    "Esportes": [
        ("Bicicleta Ergométrica", 1299.00),
        ("Kit de Halteres", 199.90),
        ("Tapete de Yoga", 89.90),
        ("Garrafa Térmica", 69.90),
    ],
    "Livros": [
        ("Romance Best-seller", 49.90),
        ("Livro de Finanças", 69.90),
        ("Guia de Python", 89.90),
        ("Box de Fantasia", 159.90),
    ],
}
PESO_CATEGORIAS = [28, 24, 22, 14, 12]

CIDADES = [
    "Curitiba",
    "São Paulo",
    "Rio de Janeiro",
    "Belo Horizonte",
    "Porto Alegre",
    "Recife",
    "Salvador",
    "Florianópolis",
    "Brasília",
    "Fortaleza",
]
PESO_CIDADES = [18, 22, 14, 10, 8, 6, 7, 6, 5, 4]

# Sazonalidade: novembro e dezembro vendem mais.
PESO_MES = {1: 1.1, 2: 0.9, 3: 1.0, 4: 1.0, 5: 1.2, 6: 1.0,
            7: 0.9, 8: 0.9, 9: 1.0, 10: 1.1, 11: 1.7, 12: 1.9}

VARIANTES_STATUS = {
    "concluído": ["Concluído", "concluido", "CONCLUÍDO", " Concluido ", "concluído"],
    "cancelado": ["Cancelado", "cancelado", "CANCELADO", "cancelado "],
    "pendente": ["Pendente", "pendente", "PENDENTE"],
}

COLUNAS = ["order_id", "order_date", "customer_id", "city", "category",
           "product", "quantity", "unit_price", "status"]


def suja_texto(texto: str, rng: random.Random, prob: float) -> str:
    """Com probabilidade `prob`, bagunça a caixa ou põe espaços sobrando."""
    if rng.random() >= prob:
        return texto
    return rng.choice([texto.lower(), texto.upper(), f" {texto} ", f"{texto} "])


def main() -> None:
    rng = random.Random(SEED)

    dias = [INICIO + timedelta(days=i) for i in range((FIM - INICIO).days + 1)]
    pesos_dias = [PESO_MES[d.month] for d in dias]
    datas = sorted(rng.choices(dias, weights=pesos_dias, k=N_PEDIDOS))

    categorias = list(CATALOGO)
    clientes = [f"C{n:04d}" for n in range(1, 451)]

    linhas = []
    for i, dia in enumerate(datas, start=1):
        categoria = rng.choices(categorias, weights=PESO_CATEGORIAS)[0]
        produto, preco_base = rng.choice(CATALOGO[categoria])
        quantidade = rng.choices([1, 2, 3, 4], weights=[60, 25, 10, 5])[0]
        preco = round(preco_base * rng.uniform(0.95, 1.05), 2)
        status = rng.choices(list(VARIANTES_STATUS), weights=[82, 10, 8])[0]

        data_txt = dia.strftime("%d/%m/%Y") if rng.random() < 0.30 else dia.isoformat()
        linhas.append({
            "order_id": f"PED-{i:05d}",
            "order_date": data_txt,
            "customer_id": rng.choice(clientes),
            "city": suja_texto(rng.choices(CIDADES, weights=PESO_CIDADES)[0], rng, 0.08),
            "category": suja_texto(categoria, rng, 0.06),
            "product": produto,
            "quantity": quantidade,
            "unit_price": f"{preco:.2f}",
            "status": rng.choice(VARIANTES_STATUS[status]),
        })

    # Pedidos duplicados (cópias do mesmo pedido, às vezes com status "diferente").
    for linha in rng.sample(linhas, k=int(N_PEDIDOS * 0.04)):
        copia = dict(linha)
        copia["status"] = f" {linha['status'].strip()} "
        linhas.append(copia)

    # Linhas inválidas: datas impossíveis e quantidades negativas.
    for linha in rng.sample(linhas, k=5):
        linha["order_date"] = "31/02/2025"
    for linha in rng.sample(linhas, k=3):
        linha["quantity"] = -1

    rng.shuffle(linhas)

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with SAIDA.open("w", newline="", encoding="utf-8") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=COLUNAS)
        writer.writeheader()
        writer.writerows(linhas)

    print(f"{len(linhas)} linhas gravadas em {SAIDA}")


if __name__ == "__main__":
    main()
