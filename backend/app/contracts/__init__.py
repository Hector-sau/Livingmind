"""Data contracts: the single source of truth for API shapes.

Front-end TypeScript types are generated from these models
(backend/scripts/export_openapi.py -> packages/api-client). Do not hand-edit generated files.
"""

from app.contracts.models import *  # noqa: F401,F403
