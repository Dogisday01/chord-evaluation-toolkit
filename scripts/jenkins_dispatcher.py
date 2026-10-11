"""Queue every remote commit durably; Jenkins serializes access to the state file.

The first poll queues the current HEAD. Later polls require an unbroken ancestry.
Completion includes failed/aborted builds so a red revision cannot block the next.
An interrupted dispatch remains pending and is retried (at-least-once delivery).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{40}")
BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./-]*")
RESULTS = {"SUCCESS", "FAILURE", "UNSTABLE", "ABORTED", "NOT_BUILT"}


def valid_sha(value: object) -> bool:
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def validate_branch(branch: str) -> None:
    if (
        not isinstance(branch, str)
        or not BRANCH.fullmatch(branch)
        or ".." in branch
        or "//" in branch
        or branch.endswith(("/", ".", ".lock"))
        or "/." in branch
    ):
        raise ValueError("Invalid branch name")


def read_state(path: Path) -> dict:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or set(state) != {
            "version",
            "branch",
            "cursor",
            "pending",
            "completed",
        }:
            raise ValueError()
        if type(state["version"]) is not int or state["version"] != 1:
            raise ValueError()
        validate_branch(state["branch"])
        if not valid_sha(state["cursor"]) or not isinstance(state["pending"], list):
            raise ValueError()
        if not isinstance(state["completed"], list):
            raise ValueError()
        completed = state["completed"]
        if any(
            not isinstance(item, dict)
            or set(item) != {"sha", "result"}
            or not valid_sha(item["sha"])
            or item["result"] not in RESULTS
            for item in completed
        ):
            raise ValueError()
        shas = state["pending"] + [item["sha"] for item in completed]
        if any(not valid_sha(sha) for sha in shas) or len(set(shas)) != len(shas):
            raise ValueError()
        if state["cursor"] not in shas:
            raise ValueError()
        return state
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("Invalid dispatcher state; restore or reset it explicitly") from exc


def write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(state, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        # Do not echo Git stderr: a remote URL may contain credentials.
        raise ValueError(f"Git {args[0]} failed (exit {result.returncode})")
    return result.stdout.strip()


def poll(repo: Path, path: Path, branch: str) -> None:
    validate_branch(branch)
    state = read_state(path) if path.exists() else None
    if state is not None and state["branch"] != branch:
        raise ValueError("State branch differs; use a separate state file for each branch")
    reference = f"refs/remotes/origin/{branch}"
    git(repo, "fetch", "origin", f"+refs/heads/{branch}:{reference}")
    head = git(repo, "rev-parse", "--verify", reference)
    if not valid_sha(head):
        raise ValueError("Remote HEAD is not a supported full commit SHA")
    if state is None:
        state = {"version": 1, "branch": branch, "cursor": head, "pending": [head], "completed": []}
    else:
        try:
            git(repo, "merge-base", "--is-ancestor", state["cursor"], head)
        except ValueError as exc:
            raise ValueError(
                "Remote ancestry changed or cursor is missing; reset explicitly"
            ) from exc
        commits = git(
            repo, "rev-list", "--reverse", "--topo-order", f"{state['cursor']}..{head}"
        ).splitlines()
        if any(not valid_sha(sha) for sha in commits):
            raise ValueError("Git returned an invalid commit SHA")
        state = {**state, "cursor": head, "pending": state["pending"] + commits}
    write_state(path, state)


def next_commit(path: Path) -> str:
    pending = read_state(path)["pending"]
    return pending[0] if pending else ""


def complete(path: Path, sha: str, result: str) -> None:
    if not valid_sha(sha) or not isinstance(result, str) or result not in RESULTS:
        raise ValueError("Invalid commit SHA or build result")
    state = read_state(path)
    if not state["pending"] or state["pending"][0] != sha:
        raise ValueError("Only the first pending commit can be completed")
    write_state(
        path,
        {
            **state,
            "pending": state["pending"][1:],
            "completed": state["completed"] + [{"sha": sha, "result": result}],
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("poll")
    fetch.add_argument("--repo", type=Path, required=True)
    fetch.add_argument("--branch", required=True)
    commands.add_parser("next")
    done = commands.add_parser("complete")
    done.add_argument("--sha", required=True)
    done.add_argument("--result", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "poll":
            poll(args.repo, args.state, args.branch)
        elif args.command == "next":
            print(next_commit(args.state))
        else:
            complete(args.state, args.sha, args.result)
    except (ValueError, OSError) as exc:
        print(f"Dispatcher error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
