"""Testa o app Streamlit de ponta a ponta (sem rede, com o modelo falso)."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from datapilot import chat, metrics
from datapilot.data_prep import load_clean
from datapilot.utils import formatar_brl, formatar_inteiro, formatar_pct

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture(scope="module")
def df_real():
    return load_clean()


def _app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=60)


def _cards(at) -> dict:
    return {m.label: m.value for m in at.metric}


def test_painel_mostra_cards_iguais_as_metricas(df_real):
    at = _app().run()
    assert not at.exception
    cards = _cards(at)
    assert cards["Receita total"] == formatar_brl(metrics.receita_total(df_real))
    assert cards["Pedidos"] == formatar_inteiro(metrics.total_pedidos(df_real))
    assert cards["Ticket médio"] == formatar_brl(metrics.ticket_medio(df_real))
    assert cards["Taxa de cancelamento"] == formatar_pct(metrics.taxa_cancelamento(df_real))


def test_filtro_de_categoria_atualiza_os_cards(df_real):
    at = _app().run()
    at.selectbox(key="filtro_categoria").select("Eletrônicos").run()
    assert not at.exception
    cards = _cards(at)
    assert cards["Receita total"] == formatar_brl(metrics.receita_total(df_real, "Eletrônicos"))
    assert cards["Receita total"] != formatar_brl(metrics.receita_total(df_real))


def test_chat_sem_chave_avisa_e_desabilita(monkeypatch):
    monkeypatch.setattr(chat, "carregar_env", lambda: None)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    at = _app().run()
    at.sidebar.radio[0].set_value("Conversa com os dados").run()
    assert not at.exception
    assert any("OPENROUTER_API_KEY" in w.value for w in at.warning)
    assert at.chat_input[0].disabled


def test_chat_numero_da_ferramenta_bate_com_o_painel(monkeypatch, df_real):
    monkeypatch.setattr(chat, "carregar_env", lambda: None)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-teste")

    esperado = metrics.receita_total(df_real, "Eletrônicos")
    roteiro = [
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=None,
            tool_calls=[SimpleNamespace(id="t1", function=SimpleNamespace(
                name="receita_total", arguments='{"categoria": "Eletrônicos"}'))],
        ))]),
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=f"Eletrônicos faturou {formatar_brl(esperado)}.", tool_calls=None))]),
    ]
    cliente = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kw: roteiro.pop(0))))
    monkeypatch.setattr(chat, "get_client", lambda: cliente)

    at = _app().run()
    at.sidebar.radio[0].set_value("Conversa com os dados").run()
    at.chat_input[0].set_value("Quanto faturou Eletrônicos?").run()

    assert not at.exception
    mensagens = at.session_state["messages"]
    assert [m["role"] for m in mensagens] == ["user", "assistant"]
    usada = mensagens[-1]["ferramentas"][0]
    assert usada["nome"] == "receita_total"
    assert usada["resultado"]["valor"] == esperado
    assert formatar_brl(esperado) in mensagens[-1]["content"]

    # E o painel, filtrado pela mesma categoria, mostra o mesmo número.
    at.sidebar.radio[0].set_value("Painel").run()
    at.selectbox(key="filtro_categoria").select("Eletrônicos").run()
    assert _cards(at)["Receita total"] == formatar_brl(esperado)


def test_erro_do_modelo_aparece_sem_derrubar_o_app(monkeypatch):
    monkeypatch.setattr(chat, "carregar_env", lambda: None)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-teste")

    def falha(*args, **kwargs):
        raise chat.ChatError("O modelo gratuito está indisponível.")

    monkeypatch.setattr(chat, "answer", falha)
    at = _app().run()
    at.sidebar.radio[0].set_value("Conversa com os dados").run()
    at.chat_input[0].set_value("Oi").run()

    assert not at.exception
    assert at.session_state["messages"][-1]["erro"] is True
