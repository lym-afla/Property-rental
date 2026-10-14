import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_backend_and_frontend_versions_match():
    backend = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    frontend = json.loads((ROOT / "frontend" / "package.json").read_text())["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", backend)
    assert backend == frontend


def test_changelog_top_entry_is_current_version():
    backend = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    first_entry = re.search(r"^## (\S+)", (ROOT / "CHANGELOG.md").read_text(), re.M)
    assert first_entry and first_entry.group(1) == backend
