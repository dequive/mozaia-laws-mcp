# mozaia-laws-mcp

**MCP server for the Mozambican law library** — give any AI agent real-time access to Mozambican legislation: current text, historical versions, validity status, and citation resolution.

Built on the [Mozaia](https://mozaia.mz) legal intelligence platform. Covers 42 legal domains, 225+ instruments from the *Boletim da República*, with authoritative citators and temporal versioning.

---

## Quick start

```bash
# Install
pip install mozaia-laws-mcp

# Or run without installing (requires uvx)
uvx mozaia-laws-mcp
```

Get an API key at **[mozaia.mz/developers](https://mozaia.mz/developers)** (free tier available).

---

## Installation

### pip / uv

```bash
pip install mozaia-laws-mcp
uv add mozaia-laws-mcp
```

### Claude Desktop

Add to `claude_desktop_config.json`
(`~/Library/Application Support/Claude/` on macOS, `%APPDATA%\Claude\` on Windows):

```json
{
  "mcpServers": {
    "mozaia-laws": {
      "command": "mozaia-laws-mcp",
      "env": {
        "MOZAIA_API_KEY": "sk-mozaia-your-key-here",
        "MOZAIA_BASE_URL": "https://api.mozaia.mz"
      }
    }
  }
}
```

### Cursor / VS Code (Copilot)

```json
{
  "mcp": {
    "servers": {
      "mozaia-laws": {
        "command": "mozaia-laws-mcp",
        "env": {
          "MOZAIA_API_KEY": "sk-mozaia-your-key-here"
        }
      }
    }
  }
}
```

### uvx (no install)

```json
{
  "mcpServers": {
    "mozaia-laws": {
      "command": "uvx",
      "args": ["mozaia-laws-mcp"],
      "env": {
        "MOZAIA_API_KEY": "sk-mozaia-your-key-here"
      }
    }
  }
}
```

---

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `MOZAIA_API_KEY` | Yes | — | API key (`sk-mozaia-<hex>`). Get one at mozaia.mz/developers |
| `MOZAIA_BASE_URL` | No | `https://api.mozaia.mz` | Override for on-premise or staging |
| `MOZAIA_TIMEOUT` | No | `30` | HTTP timeout in seconds |

---

## Tools

### `search_semantic` — natural language search over articles

The primary search tool. Use it when the user asks a legal question in plain language.

**Inputs:**

| Field | Type | Required | Description |
|---|---|---|---|
| `q` | string | Yes | Legal question in natural language |
| `top_k` | integer | No | Number of results, max 50 (default: 10) |

**Example:**
```
search_semantic(q="qual é o prazo de aviso prévio no contrato de trabalho?")
search_semantic(q="indemnização por despedimento sem justa causa", top_k=5)
```

**Returns:** ranked article list with excerpt, canonical citation, relevance score, and hit type.

---

### `get_law_relationships` — normative graph

Reveals the full normative chain: what a diploma revokes, amends, implements, and which later instruments affect it. Use before citing a law to ensure it hasn't been superseded by a downstream instrument.

**Inputs:**

| Field | Type | Required | Description |
|---|---|---|---|
| `law_id` | string | Yes | Canonical diploma identifier |
| `relation_type` | string | No | Filter: `amends`, `revokes`, `supersedes`, `references`, `complements`, `conflicts`, `implements`, `suspends`, `exceptions` |

**Example:**
```
get_law_relationships(law_id="lei_trabalho_2007")
get_law_relationships(law_id="lei_trabalho_2007", relation_type="revokes")
```

**Returns:** outgoing and incoming relationships with peer `law_id`, effective date, and confidence score.

---

### `list_amendments` — article version history

Returns every version of an article since original publication, with the amending law and date of each change. Essential for retroactivity analysis and past-fact disputes.

**Inputs:**

| Field | Type | Required | Description |
|---|---|---|---|
| `law_id` | string | Yes | Diploma identifier |
| `article_number` | string | Yes | Article number, e.g. `"70"` |

**Example:**
```
list_amendments(law_id="lei_trabalho_2023", article_number="128")
```

**Returns:** chronological list of versions — text, version label, amending law, validity range, and `is_current` flag.

---

### `search_laws` — find a diploma by name or topic

Use this first when you know a law by name or subject but not its `law_id`.

**Inputs:**

| Field | Type | Required | Description |
|---|---|---|---|
| `q` | string | No | Free text: title, number (`3/2022`), or partial `law_id` |
| `domain` | string | No | Canonical legal domain, e.g. `labour_law`, `tax_law`, `family_law` |
| `instrument_type` | string | No | `lei`, `decreto`, `codigo`, `regulamento` |
| `year` | integer | No | Publication year, e.g. `2022` |
| `page` | integer | No | Page number (default: 1) |
| `page_size` | integer | No | Results per page, max 50 (default: 20) |

**Example:**
```
search_laws(q="trabalho", domain="labour_law", year=2023)
```

**Returns:** paginated list with `law_id`, title, type, status, legal domain, and quota balance.

---

### `get_law_status` — check if a diploma is in force

**Inputs:**

| Field | Type | Required | Description |
|---|---|---|---|
| `law_id` | string | Yes | Canonical identifier, e.g. `lei_trabalho_2023`, `constituicao_2004` |

**Example:**
```
get_law_status(law_id="lei_trabalho_2023")
```

**Returns:** validity status (`active` / `revoked` / `superseded`), `revoked_by_law_id` when applicable, full citator badge, and publication metadata.

---

### `get_article` — current text of an article

**Inputs:**

| Field | Type | Required | Description |
|---|---|---|---|
| `law_id` | string | Yes | Diploma identifier |
| `article_number` | string | Yes | Article number, e.g. `"15"`, `"70"`, `"102"` |

**Example:**
```
get_article(law_id="lei_trabalho_2023", article_number="70")
```

**Returns:** full article text, amendment/revocation status, and citator with Boletim da República reference.

---

### `get_article_at_date` — historical version of an article

Retrieves the exact text that was in force on a given past date. Essential for retroactivity analysis, past-fact disputes, and temporal conflicts between norms.

**Inputs:**

| Field | Type | Required | Description |
|---|---|---|---|
| `law_id` | string | Yes | Diploma identifier |
| `article_number` | string | Yes | Article number |
| `as_of` | string | Yes | ISO 8601 date, e.g. `"2021-03-15"` |

**Example:**
```
get_article_at_date(law_id="codigo_civil_1966", article_number="217", as_of="2019-06-01")
```

**Returns:** article text at the requested date, version number, validity range, `is_current` flag, and `temporal_alert` if the norm changed shortly before or after.

---

### `cite` — resolve a Portuguese legal citation

Parses a free-text Portuguese citation and resolves it to a structured `law_id` + article record.

**Inputs:**

| Field | Type | Required | Description |
|---|---|---|---|
| `citation` | string | Yes | Citation string in Portuguese |

**Accepted formats:**
- `"Lei n.º 3/2022, artigo 15.º"`
- `"Decreto-Lei n.º 1/2020"`
- `"Constituição da República, artigo 70.º"`
- `"art. 102 do Código Civil"`

**Example:**
```
cite(citation="Lei n.º 3/2022, artigo 15.º")
```

**Returns:** `parsed_law_number`, `parsed_article_number`, `resolved_law`, `resolved_article`, `confidence` score (0–1), and `unresolved_reason` when the diploma is not in the database.

---

## Typical agent workflow

```
1. cite("Lei n.º 23/2007, artigo 128.º")
   → law_id: "lei_trabalho_2007", article: "128", confidence: 0.97

2. get_law_status(law_id="lei_trabalho_2007")
   → status: "revoked", revoked_by: "lei_trabalho_2023"

3. get_article(law_id="lei_trabalho_2023", article_number="128")
   → current text + citator

4. (if analysing a past case)
   get_article_at_date(law_id="lei_trabalho_2007", article_number="128", as_of="2018-01-01")
   → text that was in force in 2018
```

---

## Error handling

| HTTP | MCP response |
|---|---|
| `401` | `"Erro: API key inválida ou expirada."` |
| `402` | `"Erro: Quota mensal esgotada. Contactar suporte."` |
| `404` | `{"error": "not_found", "detail": "..."}` |
| `422` | `{"error": "invalid_input", "detail": "..."}` |
| timeout | `"Timeout ao contactar a API Mozaia. Tente novamente."` |

---

## Pricing

| Tier | Credits/month | Price | Best for |
|---|---|---|---|
| Community | 1 000 | Free | Evaluation, personal projects |
| Institutional | 10 000 | — | Legal firms, NGOs, universities |
| Commercial | 50 000 | — | SaaS products, fintechs |
| Strategic | 500 000 | — | Platforms, enterprise integrations |

1 credit = 1 API call. Credits reset on the 1st of each month.
Get a key and upgrade at **[mozaia.mz/developers](https://mozaia.mz/developers)**.

---

## Legal domains supported

`labour_law` · `tax_law` · `family_law` · `commercial_law` · `criminal_law` · `civil_law` · `administrative_law` · `constitutional_law` · `environmental_law` · `land_law` · `mining_law` · `consumer_law` · and 30 more.

Full list: `search_laws(domain=<domain>)` returns an empty list with a `422` if the domain is invalid.

---

## Requirements

- Python 3.11+
- Network access to `api.mozaia.mz` (or your configured `MOZAIA_BASE_URL`)
- A valid `MOZAIA_API_KEY`

---

## License

MIT — see [LICENSE](LICENSE).

Data provided through this MCP server is subject to the [Mozaia Terms of Service](https://mozaia.mz/terms).
