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

## AI Enrichment

Cloud AI extraction is opt-in. With the default `AI_ENRICHMENT_MODE=local`, the
vault importer uses deterministic local semantic rules and never sends source
text outside the machine. Set `AI_ENRICHMENT_MODE=auto` only after adding at
least one provider key and confirming that imported sources may be processed by
that provider.

| Variable | Purpose |
| --- | --- |
| `AI_ENRICHMENT_MODE` | `local`, `auto`, or `off`. `auto` routes imports through configured providers. |
| `AI_PROVIDER_ORDER` | Comma-separated provider priority list. Defaults to `openrouter,groq,gemini,cerebras`. |
| `AI_REQUEST_TIMEOUT_SECONDS` | Per-provider extraction timeout before trying the next configured provider. |
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` | OpenRouter chat-completions provider slot. |
| `GROQ_API_KEY` / `GROQ_MODEL` | Groq OpenAI-compatible chat-completions provider slot. |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Google Gemini Interactions API provider slot. |
| `CEREBRAS_API_KEY` / `CEREBRAS_MODEL` | Cerebras OpenAI-compatible chat-completions provider slot. |

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
| `OLLAMA_BASE_URL` | Ollama server base URL when `EMBEDDING_PROVIDER=ollama`. |
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
| `OPENAI_API_KEY` | Future cloud LLM provider key. |
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
- Cloud LLM use must require explicit consent before sending private vault data outside the local machine.
