# Root conftest: keep bare `pytest` runs hermetic. The delivered retrieval config defaults to a
# real (network-backed) embedding provider; tests must run with no key, so pin the offline
# deterministic backend unless a test overrides RAGSERVE_EMBEDDING_PROVIDER itself.
import os

os.environ.setdefault("RAGSERVE_EMBEDDING_PROVIDER", "deterministic")
