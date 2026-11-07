# Data Pilot

Um painel de vendas em Python que também conversa: você pergunta em português e um agente de IA responde com as métricas que **o seu código calculou**.

## O que o Data Pilot faz

O app tem dois menus:

- **Painel**: receita total, pedidos, ticket médio, taxa de cancelamento, clientes únicos, receita média por cliente, receita por mês e as 5 cidades que mais vendem, tudo filtrável por categoria.
- **Conversa com os dados**: você escreve uma pergunta ("qual o ticket médio de Eletrônicos em 2026?") e o modelo **escolhe sozinho qual função chamar** para respondê-la.

### A regra que segura tudo: o Python calcula, a IA só explica

```
pergunta ──► modelo escolhe uma ferramenta ──► o Python executa a função (pandas)
                                                        │
resposta em português ◄── modelo explica o resultado ◄──┘
```

O modelo nunca recebe a tabela de vendas e nunca faz conta: ele só vê o resultado das funções. Por isso um modelo gratuito serve, e o número do chat é o mesmo do painel (as duas telas usam as mesmas funções de `datapilot/metrics.py`). Em cada resposta, a interface mostra quais ferramentas foram chamadas, com argumentos e resultado, para você conferir.

## De onde vêm os dados

Os dados são **sintéticos** (fictícios): `scripts/generate_sample_data.py` gera o `data/sales.csv` com semente fixa, então o resultado é reproduzível. O arquivo é propositalmente "sujo", para a etapa de limpeza ter o que fazer.

A limpeza (`datapilot/data_prep.py`, feita com pandas) transforma o `data/sales.csv` em `data/sales_clean.csv`:

| Problema no arquivo bruto | Tratamento |
| --- | --- |
| Datas em `AAAA-MM-DD` e `DD/MM/AAAA` | Convertidas para data; datas impossíveis (31/02) removidas |
| Status com caixa, acento e espaços (`" Concluido "`, `CONCLUÍDO`) | Padronizados em `concluído`, `cancelado` e `pendente` |
| Cidades e categorias com caixa misturada | Padronizadas (`rio de janeiro` → `Rio de Janeiro`) |
| Pedidos duplicados | Removidos pelo `order_id`, depois da padronização |
| Quantidade ou preço inválidos | Linhas removidas |
| Sem coluna de receita | Criada: `revenue = quantity × unit_price` |

Com os dados de exemplo: 1.872 linhas brutas viram 1.793 pedidos (71 duplicados, 5 datas inválidas e 3 valores inválidos removidos). O arquivo limpo usa `;` como separador e vírgula como decimal, e é lido com os mesmos parâmetros. Para trocar os dados, use um CSV com as mesmas colunas de `data/sales.csv`.

## Como instalar e rodar

Precisa de Python 3.10 ou superior. Testado com Python 3.13, pandas 3.0, Streamlit 1.67 e openai 3.46.

```bash
git clone https://github.com/GuiHoffmannDev/data-pilot.git
cd data-pilot

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # Windows: copy .env.example .env
```

Para ligar o chat:

1. Crie uma conta no [OpenRouter](https://openrouter.ai) e gere uma chave em <https://openrouter.ai/keys>.
2. Abra o `.env` e cole a chave em `OPENROUTER_API_KEY`.
3. Deixe `OPENROUTER_MODEL=openrouter/free` (modelo gratuito) ou troque por outro que suporte chamada de ferramentas.

Depois, rode o app (**com `streamlit run`**, não como um script Python comum):

```bash
streamlit run app.py
```

O painel funciona mesmo sem chave; só o menu de conversa precisa dela. Se o `data/sales_clean.csv` não existir, o app o gera a partir do `data/sales.csv` na primeira execução.

Para regenerar os dados do zero:

```bash
python scripts/generate_sample_data.py   # cria data/sales.csv
python -m datapilot.data_prep            # cria data/sales_clean.csv e mostra o relatório da limpeza
```

## Ferramentas que o modelo pode chamar

Cada função de `datapilot/metrics.py` é descrita em `datapilot/tools.py` com nome, descrição e parâmetros. O modelo recebe essa lista e o app executa, pelo nome, a que ele pedir.

| Ferramenta | O que devolve |
| --- | --- |
| `receita_total` | Receita (R$) dos pedidos concluídos |
| `total_pedidos` | Quantidade de pedidos concluídos |
| `ticket_medio` | Receita dividida pelos pedidos concluídos |
| `clientes_unicos` | Clientes distintos com pedido concluído |
| `taxa_cancelamento` | % de pedidos cancelados sobre todos os pedidos |
| `receita_media_por_cliente` | Receita dividida pelos clientes únicos |
| `receita_por_mes` | Receita mês a mês |
| `top_cidades` | Ranking das cidades por receita (parâmetro extra `n`) |
| `listar_categorias` | Categorias existentes nos dados |

Todas (menos `listar_categorias`) aceitam os parâmetros opcionais `categoria`, `data_inicio` e `data_fim` (`AAAA-MM-DD`, inclusivos). Receita, pedidos, ticket médio e clientes consideram só pedidos **concluídos**.

Se o modelo pedir algo inválido (categoria inexistente, data mal escrita, ferramenta que não existe), a função devolve um erro em vez de quebrar o app, e o modelo explica o problema.

## Melhorias escolhidas

Implementei as três ideias de evolução:

1. **Métrica nova**: receita média por cliente (`receita_media_por_cliente`, também no painel).
2. **Gráfico novo**: as 5 cidades que mais vendem (`top_cidades_df`, no painel e como ferramenta).
3. **Intenção nova com parâmetro**: filtro por período (`data_inicio` e `data_fim`) em todas as ferramentas, por exemplo "qual a taxa de cancelamento em 2026?".

## Estrutura do projeto

```
data-pilot/
├── app.py                          # app Streamlit (painel + chat)
├── datapilot/
│   ├── config.py                   # caminhos e constantes
│   ├── data_prep.py                # limpeza com pandas
│   ├── metrics.py                  # uma função por pergunta de negócio
│   ├── tools.py                    # ferramentas para o modelo + execução pelo nome
│   ├── chat.py                     # chat com o OpenRouter
│   └── utils.py                    # formatação em reais e utilitários de texto
├── scripts/generate_sample_data.py # gera o sales.csv sintético
├── data/
│   ├── sales.csv                   # dados brutos (sintéticos)
│   └── sales_clean.csv            # dados limpos
├── docs/painel.png                 # print do painel
├── tests/                          # testes automatizados
├── requirements.txt
├── .env.example                    # modelo do .env (o .env real não é versionado)
└── .gitignore
```

## Testes

```bash
pytest
```

Os testes cobrem a limpeza dos dados, as métricas (com valores calculados à mão), as ferramentas, o laço do chat (com um cliente de IA simulado, sem rede) e o app Streamlit de ponta a ponta, incluindo a checagem de que o número devolvido pela ferramenta é igual ao do painel.

## Limitações

- O modelo gratuito tem limite de uso e velocidade variável: às vezes uma resposta falha. O app tenta de novo uma vez e, se continuar falhando, mostra uma mensagem em vez de quebrar.
- Se trocar de modelo, confira no OpenRouter se ele suporta chamada de ferramentas; sem isso o chat não consegue chamar as funções.
- Um modelo pode, em tese, responder sem chamar ferramenta. O app avisa quando isso acontece ("Nenhuma ferramenta foi chamada") para você conferir o número no painel.
- Os dados são fictícios, feitos para demonstração.
