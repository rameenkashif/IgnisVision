"""Write the OpenAPI schema the frontend's typed client is generated from.

    python scripts/export_openapi.py            # writes ../frontend/src/api/openapi.json
    cd ../frontend && npm run gen:api           # regenerates src/api/schema.d.ts
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

TARGET = Path(__file__).resolve().parents[2] / "frontend" / "src" / "api" / "openapi.json"


def render() -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    TARGET.write_text(render(), encoding="utf-8")
    print(f"wrote {TARGET}")
