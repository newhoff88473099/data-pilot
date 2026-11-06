"""Etapa 4: o chat.

Fluxo: pergunta -> modelo escolhe uma ferramenta -> o Python executa ->
o resultado volta ao modelo -> ele explica em português. A IA nunca calcula.

O modelo é acessado pelo OpenRouter (API compatível com a da OpenAI).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field

import openai
from dotenv import load_dotenv
from openai import OpenAI

from . import metrics
from .config import DEFAULT_MODEL, OPENROUTER_BASE_URL, ROOT
from .tools import TOOL_SPECS, execute_tool

MAX_TENTATIVAS = 2  # modelos gratuitos falham de vez em quando
ESPERA_S = 1.5
HISTORICO_MAX = 6  # mensagens anteriores enviadas ao modelo

SYSTEM_PROMPT = """Você é o assistente do Data Pilot, um painel de vendas.

Regras:
1. Responda sempre em português do Brasil.
2. Para qualquer pergunta que envolva números, chame uma das ferramentas disponíveis. \
Nunca calcule, estime ou invente valores.
3. Copie os valores formatados que a ferramenta devolveu (campos "*_formatado"/"*_formatada") exatamente como vieram.
4. Se nenhuma ferramenta responde à pergunta, diga isso com clareza e liste o que você consegue responder.
5. Quando houver filtro de categoria ou período, mencione-o na resposta.
6. Se a ferramenta devolver um erro, explique o problema com simplicidade.
7. Seja breve: 1 a 3 frases, ou uma lista curta quando houver vários itens.
"""


class ChatError(Exception):
    """Erro de chat com mensagem pronta para mostrar ao usuário."""


@dataclass
class ChatResult:
    texto: str
    ferramentas: list[dict] = field(default_factory=list)


def carregar_env() -> None:
    """Lê o `.env` da raiz do projeto (sem sobrescrever variáveis já definidas)."""
    load_dotenv(ROOT / ".env")


def api_key_configurada() -> bool:
    carregar_env()
    return bool(os.getenv("OPENROUTER_API_KEY", "").strip())


def modelo_configurado() -> str:
    carregar_env()
    return os.getenv("OPENROUTER_MODEL", "").strip() or DEFAULT_MODEL


def get_client() -> OpenAI:
    carregar_env()
    chave_api = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not chave_api:
        raise ChatError(
            "Chave do OpenRouter não encontrada. Copie `.env.example` para `.env` "
            "e preencha OPENROUTER_API_KEY."
        )
    return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=chave_api, timeout=60, max_retries=0)


def montar_system_prompt(df) -> str:
    inicio, fim = metrics.periodo_dos_dados(df)
    return f"{SYSTEM_PROMPT}\nOs dados cobrem de {inicio} até {fim}."


def _chamar_modelo(client, model: str, mensagens: list[dict]):
    """Uma chamada ao modelo, com uma nova tentativa para falhas passageiras."""
    for tentativa in range(MAX_TENTATIVAS):
        try:
            resposta = client.chat.completions.create(
                model=model,
                messages=mensagens,
                tools=TOOL_SPECS,
                tool_choice="auto",
                temperature=0,
            )
            if not resposta.choices:
                raise ChatError("O modelo devolveu uma resposta vazia. Tente de novo.")
            return resposta.choices[0].message
        except openai.AuthenticationError as erro:
            raise ChatError("A chave do OpenRouter foi recusada. Confira o valor no `.env`.") from erro
        except (
            openai.RateLimitError,
            openai.APIConnectionError,  # inclui timeout
            openai.InternalServerError,
        ):
            if tentativa + 1 < MAX_TENTATIVAS:
                time.sleep(ESPERA_S * (tentativa + 1))
        except openai.APIStatusError as erro:
            raise ChatError(
                f"A API respondeu com erro {erro.status_code}. Se você trocou de modelo, "
                "confira no OpenRouter se ele suporta chamada de ferramentas."
            ) from erro
    raise ChatError(
        "O modelo gratuito está indisponível ou no limite de uso agora. "
        "Aguarde alguns segundos e tente de novo."
    )


def _argumentos_para_exibicao(argumentos) -> object:
    try:
        return json.loads(argumentos) if argumentos else {}
    except (TypeError, json.JSONDecodeError):
        return argumentos


def answer(
    pergunta: str,
    df,
    historico: list[dict] | None = None,
    client=None,
    model: str | None = None,
    max_passos: int = 5,
) -> ChatResult:
    """Responde uma pergunta usando as ferramentas sobre o DataFrame `df`."""
    client = client or get_client()
    model = model or modelo_configurado()

    mensagens: list[dict] = [{"role": "system", "content": montar_system_prompt(df)}]
    for anterior in (historico or [])[-HISTORICO_MAX:]:
        if anterior.get("role") in ("user", "assistant") and anterior.get("content"):
            mensagens.append({"role": anterior["role"], "content": anterior["content"]})
    mensagens.append({"role": "user", "content": pergunta})

    usadas: list[dict] = []
    for _ in range(max_passos):
        msg = _chamar_modelo(client, model, mensagens)
        chamadas = getattr(msg, "tool_calls", None) or []

        if not chamadas:
            texto = (getattr(msg, "content", None) or "").strip()
            if not texto:
                raise ChatError("O modelo não devolveu texto. Tente reformular a pergunta.")
            return ChatResult(texto=texto, ferramentas=usadas)

        mensagens.append(
            {
                "role": "assistant",
                "content": getattr(msg, "content", None) or "",
                "tool_calls": [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.function.name, "arguments": c.function.arguments or "{}"},
                    }
                    for c in chamadas
                ],
            }
        )
        for chamada in chamadas:
            nome = chamada.function.name
            resultado = execute_tool(nome, chamada.function.arguments, df)
            usadas.append(
                {
                    "nome": nome,
                    "argumentos": _argumentos_para_exibicao(chamada.function.arguments),
                    "resultado": resultado,
                }
            )
            mensagens.append(
                {
                    "role": "tool",
                    "tool_call_id": chamada.id,
                    "content": json.dumps(resultado, ensure_ascii=False),
                }
            )

    return ChatResult(
        texto="Não consegui concluir a resposta em poucos passos. Tente uma pergunta mais direta.",
        ferramentas=usadas,
    )
