# Environment Variables

The source of truth for local environment defaults is [../.env.example](../.env.example). Copy it to `.env` for local development and never commit real secrets.

## Local App

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | Runtime environment label. Defaults to `local`. |
| `API_HOST` | FastAPI bind host inside Docker/local runtime. |
| `API_PORT` | FastAPI port. Defaults to `8000`. |
| `WEB_PORT` | Next.js web port. Defaults to `3000`. |
| `NEXT_PUBLIC_API_URL` | Browser-visible API base URL used by the web app. |

## AI Answers And Enrichment

Research answer synthesis and import enrichment have separate controls.
`RESEARCH_WRITER_MODE=auto` sends the question and its selected trade/source
evidence to the first configured chat provider, then validates all returned
citations. A `429` response places that provider in a temporary cooldown and
immediately tries the next configured provider. Ollama can be the final,
keyless local model; if every model is unavailable, the deterministic grounded
writer remains the last fallback. Set research mode to `local` to bypass all
chat models.

Vault import extraction remains opt-in. With `AI_ENRICHMENT_MODE=local`, the
importer uses deterministic local semantic rules and does not send source text
to a cloud provider. Set it to `auto` only after confirming imported sources
may be processed by that provider.

| Variable | Purpose |
| --- | --- |
| `AI_ENRICHMENT_MODE` | `local`, `auto`, or `off`. `auto` routes imports through configured providers. |
| `RESEARCH_WRITER_MODE` | `auto` (default) uses a configured provider with a validated local fallback; `local` never sends research evidence to cloud AI. |
| `AI_PROVIDER_ORDER` | Comma-separated failover priority. Defaults to `gemini,groq,openrouter,cerebras,ollama,openai` (free tiers/local before paid OpenAI). |
| `AI_REQUEST_TIMEOUT_SECONDS` | Per-provider timeout before trying the next configured provider. |
| `AI_RATE_LIMIT_COOLDOWN_SECONDS` | Minimum time to skip a provider after HTTP 429; a longer `Retry-After` header wins. |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | OpenAI Responses API provider slot. Default model: `gpt-5.6`. |
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` | OpenRouter provider slot; defaults to its zero-cost `openrouter/free` model router. |
| `GROQ_API_KEY` / `GROQ_MODEL` | Groq OpenAI-compatible chat-completions provider slot. |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Google Gemini Interactions API provider slot. |
| `CEREBRAS_API_KEY` / `CEREBRAS_MODEL` | Cerebras OpenAI-compatible chat-completions provider slot. |
| `OLLAMA_CHAT_ENABLED` / `OLLAMA_CHAT_MODEL` | Enable keyless local chat through Ollama; default model `qwen3:4b`. |
| `OLLAMA_BASE_URL` | Ollama API base URL. Use `http://host.docker.internal:11434` from Docker Desktop. |
| `OLLAMA_REQUEST_TIMEOUT_SECONDS` | Local-model allowance for cold loading and generation; defaults to `120`. |

## Memory & Retrieval

Embeddings power semantic search, entity resolution, claim dedupe, and conflict
detection. The default `local` provider is deterministic and needs no network,
so the whole research stack runs offline; `ollama` and `openai` are opt-in for
true neural embeddings.

| Variable | Purpose |
| --- | --- |
| `EMBEDDING_PROVIDER` | `local` (default, dependency-free), `ollama`, or `openai`. |
| `EMBEDDING_MODEL` | Model name for the chosen provider (e.g. `nomic-embed-text`). |
| `EMBEDDING_DIM` | Embedding dimension. Must match the provider **and** the `vector()` column in the migrations (default `768`). Changing it needs a follow-up migration. |
| `ENTITY_MATCH_THRESHOLD` | Cosine ≥ this → two node labels are the same entity (default `0.88`). |
| `ENTITY_REVIEW_THRESHOLD` | Cosine in `[review, match)` → flagged possible duplicate (default `0.80`). |
| `CONFLICT_SIM_THRESHOLD` | Claim-embedding cosine ≥ this with opposing polarity → conflict (default `0.85`). |
| `RESEARCH_MAX_SUBQUERIES` | Budget cap for multi-step research (default `4`). |

## Persistence And Infrastructure

| Variable | Purpose |
| --- | --- |
| `POSTGRES_DB` | Local Postgres database name. |
| `POSTGRES_USER` | Local Postgres username. |
| `POSTGRES_PASSWORD` | Local development password. Replace for any shared environment. |
| `DATABASE_URL` | SQLAlchemy database URL used by the API. |
| `REDIS_URL` | Redis queue/cache URL. |
| `MINIO_ENDPOINT` | Local object storage endpoint. |
| `MINIO_ROOT_USER` | Local MinIO username. |
| `MINIO_ROOT_PASSWORD` | Local MinIO password. |
| `MINIO_BUCKET` | Bucket for vault uploads and generated reports. |

## Optional Later Integrations

These should stay empty until the related adapter is implemented and documented in [setup-requests.md](setup-requests.md).

| Variable | Purpose |
| --- | --- |
| `ANTHROPIC_API_KEY` | Future cloud LLM provider key. |
| `ALPACA_API_KEY` | Future Alpaca paper-trading adapter key. |
| `ALPACA_SECRET_KEY` | Future Alpaca paper-trading adapter secret. |
| `ALPACA_BASE_URL` | Alpaca paper endpoint. |
| `ALPHA_VANTAGE_API_KEY` | Future market-data provider key. |
| `FRED_API_KEY` | Future macro-data provider key. |
| `TWELVE_DATA_API_KEY` | Future market-data provider key. |
| `FMP_API_KEY` | Future Financial Modeling Prep provider key. |
| `COINGECKO_API_KEY` | Future crypto-data provider key. |

## Security Notes

- Do not commit `.env`.
- Do not paste real trading, broker, LLM, or provider credentials into docs.
- Treat paper-trading keys as secrets.
- Cloud research synthesis sends only the question and retrieved evidence packet; use `RESEARCH_WRITER_MODE=local` when that data must remain local.
- Cloud import enrichment remains separately opt-in through `AI_ENRICHMENT_MODE=auto`.
