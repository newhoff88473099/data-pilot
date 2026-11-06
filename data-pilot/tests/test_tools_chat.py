import json
from types import SimpleNamespace

import openai
import pytest

try:  # o SDK novo da OpenAI usa httpx2; as versões anteriores usam httpx
    import httpx2 as httpx
except ImportError:  # pragma: no cover
    import httpx

from datapilot import chat, metrics
from datapilot.tools import TOOL_SPECS, execute_tool

# ------------------------------------------------------------- ferramentas ---


def test_todo_schema_tem_nome_descricao_e_parametros():
    nomes = []
    for spec in TOOL_SPECS:
        fn = spec["function"]
        nomes.append(fn["name"])
        assert spec["type"] == "function"
        assert fn["description"]
        assert fn["parameters"]["type"] == "object"
    assert len(nomes) == len(set(nomes))
    assert {"receita_total", "top_cidades", "listar_categorias"} <= set(nomes)


def test_todo_schema_corresponde_a_uma_ferramenta_executavel(df_exemplo):
    for spec in TOOL_SPECS:
        resultado = execute_tool(spec["function"]["name"], "{}", df_exemplo)
        assert "erro" not in resultado, spec["function"]["name"]


def test_execute_tool_bate_com_metrics(df_exemplo):
    r = execute_tool("receita_total", '{"categoria": "casa"}', df_exemplo)
    assert r["valor"] == metrics.receita_total(df_exemplo, "Casa") == 600.0
    assert r["valor_formatado"] == "R$ 600,00"
    assert r["filtros"] == {"categoria": "casa"}

    r = execute_tool("total_pedidos", {"data_inicio": "2025-02-01", "data_fim": "2025-02-28"}, df_exemplo)
    assert r["valor"] == 1

    r = execute_tool("taxa_cancelamento", None, df_exemplo)
    assert r["valor_formatado"] == "16,7%"


def test_top_cidades_aceita_parametro_n_e_limita(df_exemplo):
    r = execute_tool("top_cidades", '{"n": 1}', df_exemplo)
    assert [c["cidade"] for c in r["cidades"]] == ["Curitiba"]
    assert r["cidades"][0]["receita_formatada"] == "R$ 550,00"
    assert len(execute_tool("top_cidades", '{"n": "abc"}', df_exemplo)["cidades"]) == 2
    assert len(execute_tool("top_cidades", '{"n": -4}', df_exemplo)["cidades"]) == 1


def test_erros_voltam_como_dados_e_nao_como_excecao(df_exemplo):
    assert "desconhecida" in execute_tool("inventada", "{}", df_exemplo)["erro"]
    assert "JSON" in execute_tool("receita_total", "{quebrado", df_exemplo)["erro"]
    assert "objeto JSON" in execute_tool("receita_total", "[1, 2]", df_exemplo)["erro"]

    r = execute_tool("receita_total", '{"categoria": "Pets"}', df_exemplo)
    assert "não encontrada" in r["erro"] and r["categorias_disponiveis"] == ["Casa", "Moda"]

    assert "AAAA-MM-DD" in execute_tool("receita_total", '{"data_inicio": "10/01/2025"}', df_exemplo)["erro"]
    assert "posterior" in execute_tool(
        "receita_total", '{"data_inicio": "2025-03-01", "data_fim": "2025-01-01"}', df_exemplo
    )["erro"]


def test_parametros_inventados_sao_ignorados(df_exemplo):
    r = execute_tool("receita_total", '{"cor_favorita": "azul"}', df_exemplo)
    assert r["valor"] == 650.0


# --------------------------------------------------------- cliente falso ---


def _resposta(texto=None, chamadas=None):
    msg = SimpleNamespace(content=texto, tool_calls=chamadas)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def _chamada(id_, nome, args):
    return SimpleNamespace(id=id_, function=SimpleNamespace(name=nome, arguments=json.dumps(args)))


class ClienteFalso:
    """Imita `client.chat.completions.create`, devolvendo respostas roteirizadas."""

    def __init__(self, roteiro):
        self._roteiro = list(roteiro)
        self.chamadas = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        # Copia profunda: a lista de mensagens continua sendo alterada depois.
        self.chamadas.append(json.loads(json.dumps(kwargs, default=str)))
        item = self._roteiro.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _erro_conexao():
    return openai.APIConnectionError(request=httpx.Request("POST", "https://exemplo.test"))


# -------------------------------------------------------------------- chat ---


def test_modelo_escolhe_ferramenta_e_python_calcula(df_exemplo):
    cliente = ClienteFalso([
        _resposta(chamadas=[_chamada("t1", "receita_total", {"categoria": "Casa"})]),
        _resposta("A receita de Casa foi R$ 600,00."),
    ])
    resultado = chat.answer("Qual a receita de Casa?", df_exemplo, client=cliente, model="m")

    assert resultado.texto == "A receita de Casa foi R$ 600,00."
    assert len(resultado.ferramentas) == 1
    usada = resultado.ferramentas[0]
    assert usada["nome"] == "receita_total"
    assert usada["argumentos"] == {"categoria": "Casa"}
    assert usada["resultado"]["valor"] == 600.0  # calculado pelo Python

    # A 1ª chamada leva as ferramentas; a 2ª devolve o resultado ao modelo.
    primeira, segunda = cliente.chamadas
    assert len(primeira["tools"]) == len(TOOL_SPECS)
    assert primeira["messages"][0]["role"] == "system"
    assert "2025-01-10" in primeira["messages"][0]["content"]  # período dos dados
    papeis = [m["role"] for m in segunda["messages"]]
    assert papeis == ["system", "user", "assistant", "tool"]
    assert segunda["messages"][-1]["tool_call_id"] == "t1"
    assert json.loads(segunda["messages"][-1]["content"])["valor"] == 600.0


def test_resposta_direta_sem_ferramenta(df_exemplo):
    cliente = ClienteFalso([_resposta("Posso responder perguntas sobre receita e pedidos.")])
    resultado = chat.answer("Oi!", df_exemplo, client=cliente, model="m")
    assert resultado.ferramentas == []
    assert "receita" in resultado.texto


def test_historico_e_enviado_e_filtrado(df_exemplo):
    cliente = ClienteFalso([_resposta("ok")])
    historico = [
        {"role": "user", "content": "Pergunta antiga"},
        {"role": "assistant", "content": "Resposta antiga", "ferramentas": []},
        {"role": "system", "content": "não deve passar"},
    ]
    chat.answer("Nova", df_exemplo, historico=historico, client=cliente, model="m")
    papeis = [m["role"] for m in cliente.chamadas[0]["messages"]]
    assert papeis == ["system", "user", "assistant", "user"]


def test_ferramenta_com_erro_volta_ao_modelo(df_exemplo):
    cliente = ClienteFalso([
        _resposta(chamadas=[_chamada("t1", "receita_total", {"categoria": "Pets"})]),
        _resposta("Não existe a categoria Pets."),
    ])
    resultado = chat.answer("Receita de Pets?", df_exemplo, client=cliente, model="m")
    assert "erro" in resultado.ferramentas[0]["resultado"]
    assert "Pets" in resultado.texto


def test_limite_de_passos_evita_laco_infinito(df_exemplo):
    cliente = ClienteFalso([
        _resposta(chamadas=[_chamada(f"t{i}", "receita_total", {})]) for i in range(3)
    ])
    resultado = chat.answer("?", df_exemplo, client=cliente, model="m", max_passos=3)
    assert "Não consegui" in resultado.texto
    assert len(resultado.ferramentas) == 3


def test_falha_passageira_tenta_de_novo(df_exemplo, monkeypatch):
    monkeypatch.setattr(chat, "ESPERA_S", 0)
    cliente = ClienteFalso([_erro_conexao(), _resposta("Funcionou na 2ª tentativa.")])
    resultado = chat.answer("?", df_exemplo, client=cliente, model="m")
    assert resultado.texto == "Funcionou na 2ª tentativa."
    assert len(cliente.chamadas) == 2


def test_falha_persistente_vira_mensagem_amigavel(df_exemplo, monkeypatch):
    monkeypatch.setattr(chat, "ESPERA_S", 0)
    cliente = ClienteFalso([_erro_conexao(), _erro_conexao()])
    with pytest.raises(chat.ChatError, match="indisponível"):
        chat.answer("?", df_exemplo, client=cliente, model="m")


def test_chave_recusada_nao_tenta_de_novo(df_exemplo):
    resposta_http = httpx.Response(401, request=httpx.Request("POST", "https://exemplo.test"))
    erro = openai.AuthenticationError("invalid key", response=resposta_http, body=None)
    cliente = ClienteFalso([erro, _resposta("não deveria chegar aqui")])
    with pytest.raises(chat.ChatError, match="chave"):
        chat.answer("?", df_exemplo, client=cliente, model="m")
    assert len(cliente.chamadas) == 1


def test_modelo_sem_suporte_a_ferramentas_da_dica(df_exemplo):
    resposta_http = httpx.Response(404, request=httpx.Request("POST", "https://exemplo.test"))
    erro = openai.NotFoundError("no tool support", response=resposta_http, body=None)
    cliente = ClienteFalso([erro])
    with pytest.raises(chat.ChatError, match="suporta chamada de ferramentas"):
        chat.answer("?", df_exemplo, client=cliente, model="m")


def test_resposta_vazia_gera_erro(df_exemplo):
    with pytest.raises(chat.ChatError):
        chat.answer("?", df_exemplo, client=ClienteFalso([_resposta("")]), model="m")


def test_config_le_variaveis_de_ambiente(monkeypatch):
    monkeypatch.setattr(chat, "carregar_env", lambda: None)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    assert chat.api_key_configurada() is False
    assert chat.modelo_configurado() == "openrouter/free"
    with pytest.raises(chat.ChatError):
        chat.get_client()

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-teste")
    monkeypatch.setenv("OPENROUTER_MODEL", "algum/modelo:free")
    assert chat.api_key_configurada() is True
    assert chat.modelo_configurado() == "algum/modelo:free"
    assert str(chat.get_client().base_url).startswith("https://openrouter.ai/api/v1")
