#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
api_dir="$repo_root/services/api"
web_dir="$repo_root/apps/web"
api_venv="$api_dir/.venv"

if [[ ! -x "$api_venv/bin/python" ]]; then
  echo "API virtual environment not found at $api_venv." >&2
  echo "Create it and install development dependencies:" >&2
  echo "  cd services/api && python -m venv .venv && .venv/bin/pip install -e '.[dev]'" >&2
  exit 1
fi

if [[ ! -d "$web_dir/node_modules" ]]; then
  echo "Web dependencies are not installed." >&2
  echo "Run: npm ci --prefix apps/web" >&2
  exit 1
fi

echo "==> API: Ruff"
(
  cd "$api_dir"
  # Activating the environment is important for Pyright import resolution.
  source "$api_venv/bin/activate"
  ruff check app tests

  echo "==> API: Pyright"
  pyright app

  echo "==> API: Pytest"
  pytest
)

echo "==> Web: ESLint"
npm --prefix "$web_dir" run lint

echo "==> Web: TypeScript"
npm --prefix "$web_dir" run typecheck

echo "==> Web: Vitest"
npm --prefix "$web_dir" test

echo "==> Web: production build"
npm --prefix "$web_dir" run build

if command -v docker >/dev/null 2>&1; then
  echo "==> Compose: configuration"
  docker compose --project-directory "$repo_root" config --quiet
else
  echo "==> Compose: skipped (Docker CLI is not installed)"
fi

echo "Quant Labs verification passed."
