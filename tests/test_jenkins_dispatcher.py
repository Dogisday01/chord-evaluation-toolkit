"""Durable dispatch behavior tested against real local Git repositories."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "jenkins_dispatcher.py"
spec = importlib.util.spec_from_file_location("jenkins_dispatcher", SCRIPT)
dispatcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatcher)


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def commit(repo, text):
    (repo / "file.txt").write_text(text, encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", text)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repositories(tmp_path):
    remote = tmp_path / "remote"
    remote.mkdir()
    git(remote, "init", "-b", "main")
    git(remote, "config", "user.name", "Test")
    git(remote, "config", "user.email", "test@example.invalid")
    first = commit(remote, "initial")
    clone = tmp_path / "clone"
    subprocess.check_call(["git", "clone", "-q", str(remote), str(clone)])
    return remote, clone, tmp_path / "state.json", first


def test_initial_head_then_every_commit_in_order(repositories):
    remote, repo, state, first = repositories
    dispatcher.poll(repo, state, "main")
    assert dispatcher.next_commit(state) == first
    dispatcher.complete(state, first, "SUCCESS")
    commits = [commit(remote, str(index)) for index in range(3)]
    dispatcher.poll(repo, state, "main")
    assert json.loads(state.read_text())["pending"] == commits
    dispatcher.complete(state, commits[0], "FAILURE")
    assert dispatcher.next_commit(state) == commits[1]
    dispatcher.poll(repo, state, "main")  # A restarted process does not duplicate pending work.
    dispatcher.complete(state, commits[1], "SUCCESS")
    dispatcher.complete(state, commits[2], "SUCCESS")
    assert dispatcher.next_commit(state) == ""
    assert [item["result"] for item in json.loads(state.read_text())["completed"]] == [
        "SUCCESS",
        "FAILURE",
        "SUCCESS",
        "SUCCESS",
    ]


def test_force_push_fails_without_overwriting_state(repositories):
    remote, repo, state, first = repositories
    dispatcher.poll(repo, state, "main")
    commit(remote, "second")
    dispatcher.poll(repo, state, "main")
    original = state.read_bytes()
    git(remote, "reset", "--hard", first)
    commit(remote, "replacement")
    with pytest.raises(ValueError, match="ancestry"):
        dispatcher.poll(repo, state, "main")
    assert state.read_bytes() == original


@pytest.mark.parametrize("contents", ["not json", "[]", "{}", '{"version": true}'])
def test_invalid_state_is_preserved(tmp_path, contents):
    state = tmp_path / "state.json"
    state.write_text(contents)
    with pytest.raises(ValueError, match="state"):
        dispatcher.next_commit(state)
    assert state.read_text() == contents


def test_invalid_completion_and_branch_are_rejected(repositories):
    _, repo, state, first = repositories
    for branch in ["", "-main", "main;echo", "../main", "main..bad"]:
        with pytest.raises(ValueError, match="branch"):
            dispatcher.poll(repo, state, branch)
    dispatcher.poll(repo, state, "main")
    original = state.read_bytes()
    for sha, result in [("bad", "SUCCESS"), ("a" * 40, "SUCCESS"), (first, "bad")]:
        with pytest.raises(ValueError):
            dispatcher.complete(state, sha, result)
    with pytest.raises(ValueError, match="branch"):
        dispatcher.poll(repo, state, "demo")
    assert state.read_bytes() == original


def test_failed_atomic_replace_preserves_state(repositories, monkeypatch):
    _, repo, state, first = repositories
    dispatcher.poll(repo, state, "main")
    original = state.read_bytes()

    def fail(*args):
        raise OSError("simulated disk error")

    monkeypatch.setattr(dispatcher.os, "replace", fail)
    with pytest.raises(OSError, match="disk"):
        dispatcher.complete(state, first, "SUCCESS")
    assert state.read_bytes() == original
    assert list(state.parent.glob(".state.json.*")) == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("cursor", "invalid"),
        ("pending", ["bad"]),
        ("pending", "bad"),
        ("completed", "bad"),
        ("completed", [{"sha": "a" * 40, "result": "invalid"}]),
        ("branch", None),
        ("version", 2),
        ("completed", [None]),
    ],
)
def test_schema_field_validation(repositories, field, value):
    _, repo, state, _ = repositories
    dispatcher.poll(repo, state, "main")
    data = json.loads(state.read_text())
    state.write_text(json.dumps({**data, field: value}))
    with pytest.raises(ValueError, match="state"):
        dispatcher.next_commit(state)


def test_duplicates_and_unknown_cursor_are_rejected(repositories):
    _, repo, state, first = repositories
    dispatcher.poll(repo, state, "main")
    data = json.loads(state.read_text())
    for change in [{"pending": [first, first]}, {"cursor": "a" * 40}]:
        state.write_text(json.dumps({**data, **change}))
        with pytest.raises(ValueError, match="state"):
            dispatcher.next_commit(state)


def test_cli_and_missing_branch_failure(repositories, capsys):
    _, repo, state, first = repositories
    prefix = ["--state", str(state)]
    assert dispatcher.main(prefix + ["poll", "--repo", str(repo), "--branch", "main"]) == 0
    assert dispatcher.main(prefix + ["next"]) == 0
    assert capsys.readouterr().out.strip() == first
    assert dispatcher.main(prefix + ["complete", "--sha", first, "--result", "FAILURE"]) == 0
    assert dispatcher.main(prefix + ["next"]) == 0
    assert capsys.readouterr().out.strip() == ""
    assert dispatcher.main(prefix + ["complete", "--sha", first, "--result", "SUCCESS"]) == 1
    assert "first pending" in capsys.readouterr().err
    fresh_state = state.parent / "missing.json"
    assert (
        dispatcher.main(
            ["--state", str(fresh_state), "poll", "--repo", str(repo), "--branch", "missing"]
        )
        == 1
    )
    assert "Git fetch failed" in capsys.readouterr().err
    assert not fresh_state.exists()


def test_missing_cursor_and_restart_in_another_process(repositories):
    _, repo, state, first = repositories
    dispatcher.poll(repo, state, "main")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--state", str(state), "next"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == first
    data = json.loads(state.read_text())
    absent = "a" * 40
    state.write_text(json.dumps({**data, "cursor": absent, "pending": [absent]}))
    original = state.read_bytes()
    with pytest.raises(ValueError, match="ancestry"):
        dispatcher.poll(repo, state, "main")
    assert state.read_bytes() == original


def test_large_queue_and_invalid_types(tmp_path):
    shas = [f"{index:040x}" for index in range(10001)]
    state = tmp_path / "large.json"
    dispatcher.write_state(
        state,
        {"version": 1, "branch": "main", "cursor": shas[-1], "pending": shas, "completed": []},
    )
    dispatcher.complete(state, shas[0], "SUCCESS")
    assert dispatcher.next_commit(state) == shas[1]
    for branch in [None, 1, [], "🔥", "'", "a//b", "a/", "a/.b", "a.lock"]:
        with pytest.raises(ValueError, match="branch"):
            dispatcher.validate_branch(branch)
    for sha, result in [(None, "SUCCESS"), (shas[1], []), (shas[1], None)]:
        with pytest.raises(ValueError):
            dispatcher.complete(state, sha, result)
