import os
import tempfile

# Point the app at an isolated SQLite database before any app module (and its
# engine) is imported, so the test suite never touches the dev database.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp.name}")
os.environ["AI_ENRICHMENT_MODE"] = "local"
