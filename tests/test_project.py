import shutil
from pathlib import Path

import pytest
import yaml

from conftest import EXAMPLES, git
from openkb import project
from openkb.cli import main


def test_example_context_is_up_to_date(examples):
    project.sync(examples / "project")
    for name in ("context.md", "kbs.lock"):
        generated = (examples / "project/.openkb" / name).read_text()
        assert generated == (EXAMPLES / "project/.openkb" / name).read_text(), f"run `openkb sync --project examples/project` ({name})"


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    """A git repository holding the awesome-can-bus KB."""
    repo = tmp_path / "remote"
    shutil.copytree(EXAMPLES / "awesome-can-bus", repo)
    git("init", "-q", "-b", "main", cwd=repo)
    git("add", ".", cwd=repo)
    git("commit", "-qm", "init", cwd=repo)
    return repo


def test_add_and_sync_git(tmp_path, remote):
    proj = tmp_path / "proj"
    proj.mkdir()
    assert main(["add", remote.as_uri(), "--project", str(proj), "--use", "for CAN work"]) == 0

    data = yaml.safe_load((proj / ".openkb/kbs.yaml").read_text())
    assert data["kbs"] == [{"id": "awesome-can-bus", "source": remote.as_uri(), "use": "for CAN work"}]
    lock = yaml.safe_load((proj / ".openkb/kbs.lock").read_text())
    first = lock["kbs"]["awesome-can-bus"]["commit"]
    assert first == git("rev-parse", "HEAD", cwd=remote)
    context = (proj / ".openkb/context.md").read_text()
    assert "- Index: .openkb/cache/awesome-can-bus/index.md" in context
    assert "- Use: for CAN work" in context
    assert (proj / ".openkb/.gitignore").read_text() == "cache/\n"
    assert not any(p.name.startswith(".tmp-") for p in (proj / ".openkb/cache").iterdir())

    # A new upstream commit is picked up by sync, but not by sync --locked.
    (remote / "log.md").write_text((remote / "log.md").read_text() + "\nmore\n")
    git("commit", "-qam", "more", cwd=remote)
    project.sync(proj)
    second = yaml.safe_load((proj / ".openkb/kbs.lock").read_text())["kbs"]["awesome-can-bus"]["commit"]
    assert second != first
    (proj / ".openkb/kbs.lock").write_text(yaml.safe_dump({"openkb": "0.1", "kbs": {"awesome-can-bus": {"commit": first}}}))
    project.sync(proj, locked=True)
    assert git("rev-parse", "HEAD", cwd=proj / ".openkb/cache/awesome-can-bus") == first


def test_add_local_reads_id(tmp_path, examples):
    proj = examples / "fresh"
    proj.mkdir()
    entry = project.add(proj, "../openkb-design")
    assert entry == {"id": "openkb-design", "source": "../openkb-design"}
    with pytest.raises(project.ProjectError, match="already connected"):
        project.add(proj, "../openkb-design")


def test_id_mismatch(tmp_path, remote):
    proj = tmp_path / "proj"
    project.add(proj, remote.as_uri(), id="wrong")
    with pytest.raises(project.ProjectError, match="own id is 'awesome-can-bus'"):
        project.sync(proj)


def test_offline_without_cache(tmp_path, remote):
    proj = tmp_path / "proj"
    project.add(proj, remote.as_uri(), id="awesome-can-bus")
    with pytest.raises(project.ProjectError, match="not in cache"):
        project.sync(proj, offline=True)


def test_git_url():
    assert project.git_url("github:hexsecs/kb") == "https://github.com/hexsecs/kb.git"
    assert project.git_url("git@github.com:a/b.git") == "git@github.com:a/b.git"
    assert project.git_url("../local") is None
