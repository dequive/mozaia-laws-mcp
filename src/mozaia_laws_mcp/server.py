"""mozaia-laws-mcp — MCP server para acesso à biblioteca de legislação moçambicana.

Ferramentas expostas:
  search_laws           — pesquisa paginada de diplomas por título, domínio ou ano
  search_semantic       — pesquisa semântica BM25+pgvector em linguagem natural
  get_law_status        — estado de vigência + citador de um diploma
  get_law_relationships — grafo normativo: o que a lei revoga, altera e referencia
  get_article           — texto actual de um artigo + citador
  get_article_at_date   — texto do artigo em vigor numa data histórica
  list_amendments       — histórico completo de versões de um artigo
  cite                  — resolve citação PT em lei + artigo

Configuração (variáveis de ambiente):
  MOZAIA_API_KEY    — sk-mozaia-<64hex>  (obrigatório)
  MOZAIA_BASE_URL   — https://api.mozaia.mz  (default)

Uso com Claude Desktop (claude_desktop_config.json):
  {
    "mcpServers": {
      "mozaia-laws": {
        "command": "mozaia-laws-mcp",
        "env": {
          "MOZAIA_API_KEY": "sk-mozaia-...",
          "MOZAIA_BASE_URL": "https://api.mozaia.mz"
        }
      }
    }
  }

Uso com uvx (sem instalar):
  uvx mozaia-laws-mcp
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

import httpx

try:
    import mcp.server.stdio
    import mcp.types as types
    from mcp.server import Server
except ImportError:
    print(
        "Erro: o package 'mcp' não está instalado.\n"
        "Instalar: pip install mcp httpx\n"
        "ou: uvx mozaia-laws-mcp",
        file=sys.stderr,
    )
    sys.exit(1)

# ── Configuração ──────────────────────────────────────────────────────────────

_API_KEY = os.environ.get("MOZAIA_API_KEY", "")
_BASE_URL = os.environ.get("MOZAIA_BASE_URL", "https://api.mozaia.mz").rstrip("/")
_TIMEOUT = float(os.environ.get("MOZAIA_TIMEOUT", "30"))

server = Server("mozaia-laws")


def _client() -> httpx.AsyncClient:
    if not _API_KEY:
        raise RuntimeError(
            "Variável de ambiente MOZAIA_API_KEY não definida. "
            "Obter uma key em https://mozaia.mz/developers"
        )
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={"X-API-Key": _API_KEY, "Content-Type": "application/json"},
        timeout=_TIMEOUT,
    )


async def _call(method: str, path: str, **kwargs: Any) -> dict:
    async with _client() as client:
        resp = await client.request(method, path, **kwargs)
    if resp.status_code == 401:
        raise RuntimeError("API key inválida ou expirada.")
    if resp.status_code == 402:
        raise RuntimeError("Quota mensal esgotada. Contactar suporte.")
    if resp.status_code == 404:
        return {"error": "not_found", "detail": resp.json().get("detail", "Não encontrado.")}
    if resp.status_code == 422:
        return {"error": "invalid_input", "detail": resp.json().get("detail", "Input inválido.")}
    resp.raise_for_status()
    return resp.json()


# ── Tool definitions ──────────────────────────────────────────────────────────

_TOOLS = [
    types.Tool(
        name="search_semantic",
        description=(
            "Pesquisa artigos de legislação moçambicana usando linguagem natural — BM25 + pgvector. "
            "Usar quando o utilizador faz uma pergunta jurídica como 'qual é o prazo de aviso prévio?' "
            "ou 'o que diz a lei sobre despedimento sem justa causa?'. "
            "Devolve artigos relevantes com excerto, citação canónica e score de relevância."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "q": {
                    "type": "string",
                    "description": "Questão jurídica em linguagem natural, ex: 'prazo de aviso prévio no contrato de trabalho'.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Número de resultados (máx 50, default 10).",
                    "default": 10,
                },
            },
            "required": ["q"],
        },
    ),
    types.Tool(
        name="search_laws",
        description=(
            "Pesquisa diplomas na base de dados de legislação moçambicana. "
            "Usar quando o utilizador menciona uma lei por nome ou tema mas não se conhece o law_id. "
            "Devolve lista paginada com law_id, título, tipo, estado e domínio jurídico. "
            "O law_id obtido aqui pode ser passado para get_law_status ou get_article."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "q": {
                    "type": "string",
                    "description": "Texto livre: título, número (ex: '3/2022') ou law_id parcial.",
                },
                "domain": {
                    "type": "string",
                    "description": "Domínio jurídico canónico, ex: 'labour_law', 'tax_law', 'family_law'.",
                },
                "instrument_type": {
                    "type": "string",
                    "description": "Tipo de instrumento: 'lei', 'decreto', 'codigo', 'regulamento'.",
                },
                "year": {
                    "type": "integer",
                    "description": "Ano de publicação, ex: 2022.",
                },
                "page": {
                    "type": "integer",
                    "description": "Página (começa em 1).",
                    "default": 1,
                },
                "page_size": {
                    "type": "integer",
                    "description": "Resultados por página (máx 50).",
                    "default": 20,
                },
            },
            "required": [],
        },
    ),
    types.Tool(
        name="get_law_relationships",
        description=(
            "Devolve o grafo normativo de um diploma: o que revoga, altera, suspende, remete e implementa, "
            "e quais diplomas posteriores o afectam. "
            "Usar para navegar a cadeia normativa antes de citar uma lei — "
            "garante que o diploma não foi revogado por um instrumento posterior não directamente referenciado."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "law_id": {
                    "type": "string",
                    "description": "Identificador canónico do diploma, ex: 'lei_trabalho_2023'.",
                },
                "relation_type": {
                    "type": "string",
                    "description": "Filtrar por tipo: amends, revokes, supersedes, references, complements, conflicts, implements, suspends, exceptions.",
                },
            },
            "required": ["law_id"],
        },
    ),
    types.Tool(
        name="get_law_status",
        description=(
            "Devolve o estado de vigência de um diploma moçambicano: "
            "se está em vigor, revogado ou substituído, o citador de autoridade, "
            "e metadados (tipo, número, ano, domínio jurídico). "
            "Usar para verificar se uma lei ainda está em vigor antes de a citar."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "law_id": {
                    "type": "string",
                    "description": (
                        "Identificador canónico do diploma, ex: 'lei_trabalho_2023', "
                        "'constituicao_2004', 'codigo_civil_1966'."
                    ),
                }
            },
            "required": ["law_id"],
        },
    ),
    types.Tool(
        name="get_article",
        description=(
            "Devolve o texto completo e actual de um artigo de legislação moçambicana, "
            "incluindo indicação se foi alterado ou revogado e o citador de autoridade. "
            "Usar para obter o texto exacto antes de citar ou analisar uma norma."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "law_id": {
                    "type": "string",
                    "description": "Identificador canónico do diploma, ex: 'lei_trabalho_2023'.",
                },
                "article_number": {
                    "type": "string",
                    "description": "Número do artigo, ex: '15', '70', '102'.",
                },
            },
            "required": ["law_id", "article_number"],
        },
    ),
    types.Tool(
        name="get_article_at_date",
        description=(
            "Devolve o texto de um artigo tal como estava em vigor numa data histórica. "
            "Útil para análise de factos passados, retroactividade e conflitos temporais de normas. "
            "Se a versão exacta não existir, devolve a versão mais próxima com justificação."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "law_id": {
                    "type": "string",
                    "description": "Identificador canónico do diploma.",
                },
                "article_number": {
                    "type": "string",
                    "description": "Número do artigo, ex: '15'.",
                },
                "as_of": {
                    "type": "string",
                    "description": "Data em formato ISO 8601, ex: '2021-03-15'.",
                },
            },
            "required": ["law_id", "article_number", "as_of"],
        },
    ),
    types.Tool(
        name="list_amendments",
        description=(
            "Devolve o histórico completo de versões de um artigo — "
            "todas as redacções desde a publicação original até ao texto actual, "
            "com indicação da lei que introduziu cada alteração e data de vigência. "
            "Usar para due diligence, análise de retroactividade e conflitos temporais de normas."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "law_id": {
                    "type": "string",
                    "description": "Identificador canónico do diploma.",
                },
                "article_number": {
                    "type": "string",
                    "description": "Número do artigo, ex: '70'.",
                },
            },
            "required": ["law_id", "article_number"],
        },
    ),
    types.Tool(
        name="cite",
        description=(
            "Resolve uma citação jurídica em português para o diploma e artigo correspondentes "
            "na base de dados moçambicana. "
            "Aceita formatos como 'Lei n.º 3/2022, artigo 15.º', 'Decreto-Lei n.º 1/2020', "
            "'Constituição da República, artigo 70.º'. "
            "Usar quando o utilizador menciona uma lei por referência textual e é preciso "
            "obter os dados estruturados antes de consultar get_article."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "citation": {
                    "type": "string",
                    "description": (
                        "Citação jurídica em português, ex: 'Lei n.º 3/2022, artigo 15.º' "
                        "ou 'art. 70 da Constituição'."
                    ),
                }
            },
            "required": ["citation"],
        },
    ),
]


# ── Handlers ──────────────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return _TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        result = await _dispatch(name, arguments)
    except RuntimeError as exc:
        return [types.TextContent(type="text", text=f"Erro: {exc}")]
    except httpx.HTTPStatusError as exc:
        return [types.TextContent(type="text", text=f"Erro HTTP {exc.response.status_code}: {exc.response.text[:300]}")]
    except httpx.TimeoutException:
        return [types.TextContent(type="text", text="Timeout ao contactar a API Mozaia. Tente novamente.")]

    return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def _dispatch(name: str, args: dict) -> dict:
    if name == "search_semantic":
        params = {"q": args["q"]}
        if args.get("top_k") is not None:
            params["top_k"] = args["top_k"]
        return await _call("GET", "/v1/intelligence/search", params=params)

    if name == "get_law_relationships":
        law_id = args["law_id"]
        params = {}
        if args.get("relation_type"):
            params["relation_type"] = args["relation_type"]
        return await _call("GET", f"/v1/intelligence/laws/{law_id}/relationships", params=params or None)

    if name == "list_amendments":
        law_id = args["law_id"]
        article_number = args["article_number"]
        return await _call("GET", f"/v1/intelligence/articles/{law_id}/{article_number}/amendments")

    if name == "search_laws":
        params = {k: v for k, v in {
            "q":               args.get("q"),
            "domain":          args.get("domain"),
            "instrument_type": args.get("instrument_type"),
            "year":            args.get("year"),
            "page":            args.get("page", 1),
            "page_size":       args.get("page_size", 20),
        }.items() if v is not None}
        return await _call("GET", "/v1/intelligence/laws", params=params)

    if name == "get_law_status":
        return await _call("GET", f"/v1/intelligence/laws/{args['law_id']}/status")

    if name == "get_article":
        return await _call("GET", f"/v1/intelligence/articles/{args['law_id']}/{args['article_number']}")

    if name == "get_article_at_date":
        return await _call(
            "GET",
            f"/v1/intelligence/articles/{args['law_id']}/{args['article_number']}/at/{args['as_of']}",
        )

    if name == "cite":
        return await _call("POST", "/v1/intelligence/cite", json={"citation": args["citation"]})

    raise ValueError(f"Ferramenta desconhecida: {name!r}")


# ── Entrypoint ────────────────────────────────────────────────────────────────

async def _amain() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
