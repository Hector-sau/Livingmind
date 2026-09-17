"""Write the OpenAPI document generated from the Pydantic contracts.

Usage (from repo root): backend/.venv/bin/python backend/scripts/export_openapi.py
"""

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.main import create_app  # noqa: E402

OUT = BACKEND.parent / "packages" / "api-client" / "openapi.json"


def main() -> None:
    spec = create_app().openapi()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(BACKEND.parent)}")


if __name__ == "__main__":
    main()
