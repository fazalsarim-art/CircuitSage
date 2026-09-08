"""Shared test configuration.

Set safe placeholder environment values so ``Settings`` construction (which happens at
import time in ``app.main``) never depends on a local ``.env`` file being present.
"""

import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://circuitsage:change_me@localhost:5432/circuitsage"
)
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-at-least-32-chars")
os.environ.setdefault("APP_VERSION", "0.1.0")
