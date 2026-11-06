"""Data Pilot: painel de vendas que também conversa.

Rode com:  streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from datapilot import chat, metrics
from datapilot.data_prep import carregar_dados
from datapilot.utils import formatar_brl, formatar_inteiro, formatar_pct

COR = "#4F46E5"
PAGINAS = ["Painel", "Conversa com os dados"]
EXEMPLOS = [
    "Qual foi a receita total?",
    "Qual o ticket médio de Eletrônicos?",
    "Quais as 5 cidades que mais vendem?",
    "Qual a taxa de cancelamento em 2026?",
]

st.set_page_config(page_title="Data Pilot", page_icon="📊", layout="wide")


@st.cache_data(show_spinner="Carregando os dados...")
def carregar() -> pd.DataFrame:
    return carregar_dados()


# ------------------------------------------------------------------ painel ---


MESES_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _rotulo_mes(periodo: str) -> str:
    """'2025-03' -> 'mar/25' (sem depender do idioma do navegador)."""
    ano, mes = periodo.split("-")
    return f"{MESES_PT[int(mes) - 1]}/{ano[2:]}"


def _grafico_mensal(df: pd.DataFrame, categoria: str):
    tabela = metrics.receita_por_mes_df(df, categoria=categoria)
    tabela["rotulo"] = tabela["mes"].map(_rotulo_mes)
    fig = px.bar(tabela, x="rotulo", y="receita", labels={"rotulo": "Mês", "receita": "Receita (R$)"})
    fig.update_traces(marker_color=COR, hovertemplate="%{x}<br>R$ %{y:,.2f}<extra></extra>")
    fig.update_xaxes(type="category")  # evita o Plotly tratar o texto como data
    fig.update_layout(separators=",.", margin=dict(t=10, b=10), yaxis_tickprefix="R$ ")
    return fig


def _grafico_cidades(df: pd.DataFrame, categoria: str):
    tabela = metrics.top_cidades_df(df, n=5, categoria=categoria).sort_values("receita")
    fig = px.bar(
        tabela,
        x="receita",
        y="cidade",
        orientation="h",
        labels={"cidade": "", "receita": "Receita (R$)"},
    )
    fig.update_traces(
        marker_color=COR,
        text=[formatar_brl(v) for v in tabela["receita"]],
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{y}<br>R$ %{x:,.2f}<extra></extra>",
    )
    fig.update_xaxes(range=[0, float(tabela["receita"].max() or 1) * 1.35], showticklabels=False)
    fig.update_layout(separators=",.", margin=dict(t=10, b=10, r=10))
    return fig


def pagina_painel(df: pd.DataFrame) -> None:
    st.title("📊 Painel de vendas")

    categorias = ["Todas", *metrics.listar_categorias(df)]
    categoria = st.selectbox("Categoria", categorias, key="filtro_categoria")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Receita total", formatar_brl(metrics.receita_total(df, categoria)))
    col2.metric("Pedidos", formatar_inteiro(metrics.total_pedidos(df, categoria)))
    col3.metric("Ticket médio", formatar_brl(metrics.ticket_medio(df, categoria)))
    col4.metric("Taxa de cancelamento", formatar_pct(metrics.taxa_cancelamento(df, categoria)))

    col5, col6, _, _ = st.columns(4)
    col5.metric("Clientes únicos", formatar_inteiro(metrics.clientes_unicos(df, categoria)))
    col6.metric(
        "Receita média por cliente", formatar_brl(metrics.receita_media_por_cliente(df, categoria))
    )

    st.caption("Receita, pedidos, ticket médio e clientes consideram só pedidos concluídos.")

    esquerda, direita = st.columns([3, 2])
    with esquerda:
        st.subheader("Receita por mês")
        st.plotly_chart(_grafico_mensal(df, categoria), width="stretch")
    with direita:
        st.subheader("Top 5 cidades")
        st.plotly_chart(_grafico_cidades(df, categoria), width="stretch")


# -------------------------------------------------------------------- chat ---


def _escapar(texto: str) -> str:
    """O Streamlit trata $...$ como fórmula; 'R$ 10 ... R$ 20' quebraria."""
    return texto.replace("$", "\\$")


def _conteudo_mensagem(msg: dict) -> None:
    st.markdown(_escapar(msg["content"]))
    if msg["role"] != "assistant" or msg.get("erro"):
        return
    ferramentas = msg.get("ferramentas", [])
    if ferramentas:
        with st.expander(f"🔧 Ferramentas usadas ({len(ferramentas)})"):
            for item in ferramentas:
                st.markdown(f"**{item['nome']}**")
                st.json({"argumentos": item["argumentos"], "resultado": item["resultado"]}, expanded=False)
    else:
        st.caption("Nenhuma ferramenta foi chamada; confirme os números no painel.")


def _mostrar_mensagem(msg: dict) -> None:
    with st.chat_message(msg["role"]):
        _conteudo_mensagem(msg)


def pagina_chat(df: pd.DataFrame) -> None:
    st.title("💬 Converse com os dados")
    st.caption(
        "Pergunte em português. O modelo escolhe uma ferramenta, o Python calcula "
        "e a IA só explica o resultado."
    )

    pronto = chat.api_key_configurada()
    if not pronto:
        st.warning(
            "Chave do OpenRouter não encontrada. Copie `.env.example` para `.env`, "
            "preencha `OPENROUTER_API_KEY` e reinicie o app."
        )

    mensagens = st.session_state.setdefault("messages", [])
    for msg in mensagens:
        _mostrar_mensagem(msg)

    espaco_exemplos = st.empty()
    if not mensagens:
        with espaco_exemplos.container():
            st.write("Tente uma destas perguntas:")
            colunas = st.columns(2)
            for i, exemplo in enumerate(EXEMPLOS):
                if colunas[i % 2].button(
                    exemplo, key=f"exemplo_{i}", disabled=not pronto, width="stretch"
                ):
                    st.session_state["pergunta_pendente"] = exemplo

    pergunta = st.chat_input("Pergunte algo sobre as vendas...", disabled=not pronto)
    if not pergunta:
        pergunta = st.session_state.pop("pergunta_pendente", None)
    if not pergunta:
        return
    espaco_exemplos.empty()  # a conversa começou: some com os exemplos

    historico = [m for m in mensagens if not m.get("erro")]
    mensagens.append({"role": "user", "content": pergunta})
    _mostrar_mensagem(mensagens[-1])

    with st.chat_message("assistant"):
        with st.spinner("Consultando os dados..."):
            try:
                resultado = chat.answer(pergunta, df, historico=historico)
                resposta = {
                    "role": "assistant",
                    "content": resultado.texto,
                    "ferramentas": resultado.ferramentas,
                }
            except chat.ChatError as erro:
                resposta = {"role": "assistant", "content": f"⚠️ {erro}", "erro": True}
        _conteudo_mensagem(resposta)
    mensagens.append(resposta)


# --------------------------------------------------------------------- app ---


def main() -> None:
    try:
        df = carregar()
    except FileNotFoundError as erro:
        st.error(str(erro))
        st.stop()

    with st.sidebar:
        st.header("Data Pilot")
        pagina = st.radio("Menu", PAGINAS, key="menu")
        inicio, fim = metrics.periodo_dos_dados(df)
        st.caption(f"Dados de {inicio} a {fim}")
        if pagina == PAGINAS[1] and st.session_state.get("messages"):
            if st.button("Limpar conversa"):
                st.session_state["messages"] = []
                st.rerun()

    if pagina == PAGINAS[0]:
        pagina_painel(df)
    else:
        pagina_chat(df)


main()
