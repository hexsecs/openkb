import shutil
import subprocess
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture
def examples(tmp_path: Path) -> Path:
    """A writable copy of the examples directory."""
    dest = tmp_path / "examples"
    shutil.copytree(EXAMPLES, dest)
    return dest


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def page(title: str, summary: str = "A page.", body: str = "", **extra: str) -> str:
    fields = "".join(f"{k}: {v}\n" for k, v in extra.items())
    return f"---\ntitle: {title}\nsummary: {summary}\ntype: concept\nupdated: 2026-10-31\n{fields}---\n{body}\n"


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()
