from pathlib import Path

import pytest

from scripts.export_openapi import TARGET, render


def test_frontend_openapi_is_up_to_date():
    if not TARGET.exists():
        pytest.skip("frontend not checked out next to backend")
    assert TARGET.read_text(encoding="utf-8") == render(), (
        "API changed: run `python scripts/export_openapi.py` in backend/ and "
        "`npm run gen:api` in frontend/, then commit both files."
    )


def test_target_path_points_into_frontend():
    assert Path(TARGET).parts[-3:] == ("src", "api", "openapi.json")
