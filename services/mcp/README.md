# Quant Labs MCP Server (read-only)

Exposes the trading memory (vault search, graph, claims, grounded Q&A) as MCP
tools so Claude and other assistants can answer over your own trading data —
with citations and trust scores, never fabricated. All tools are read-only.

## Tools

- `search_memory(query, limit)` — hybrid semantic + keyword search over sources
- `ask_research(question)` — grounded answer with citations + trust score
- `get_entity(name)` — find graph entities by name
- `get_neighborhood(name, depth)` — expand the graph around an entity
- `list_conflicts(status)` — claims where two sources disagree

## Run

```bash
cd services/mcp
pip install mcp
PYTHONPATH=../api python -m app.server
```

It runs in-process against the same database the API uses (single-user demo
identity). Register it with your assistant as a stdio MCP server.
