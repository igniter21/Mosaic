#!/usr/bin/env python3
"""Collect git metadata into Mosaic without reading source-code contents."""

from __future__ import annotations

import argparse
import json
import subprocess
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


API = "http://127.0.0.1:8000/api/v1/events"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def post_event(event: dict, api: str) -> None:
    body = json.dumps(event).encode("utf-8")
    request = urllib.request.Request(
        api,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status >= 300:
                raise RuntimeError(f"Mosaic rejected event: HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(
            f"Mosaic rejected event: HTTP {exc.code} — {body}"
        ) from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", nargs="?", default=".")
    parser.add_argument("--api", default=API)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    # Walk up to find the nearest git root (like git itself does).
    if not (repo / ".git").exists():
        for parent in repo.parents:
            if (parent / ".git").exists():
                repo = parent
                break
        else:
            print(f"Error: '{repo}' (and its parents) is not inside a git repository.")
            print("Usage: python collect_git.py <path-to-your-local-git-repo>")
            raise SystemExit(1)
    remote = ""
    try:
        remote = git(repo, "config", "--get", "remote.origin.url")
    except subprocess.CalledProcessError:
        pass
    repository_name = repo.name
    try:
        branch = git(repo, "branch", "--show-current") or "detached"
    except subprocess.CalledProcessError:
        branch = "detached"
    commits = git(
        repo,
        "log",
        f"-n{args.limit}",
        "--date=iso-strict",
        "--format=%H%x1f%ad%x1f%s",
    ).splitlines()

    for line in commits:
        sha, occurred_at, message = line.split("\x1f", 2)
        files_raw = git(repo, "show", "--format=", "--name-only", sha)
        files = [item for item in files_raw.splitlines() if item.strip()][:30]
        event = {
            "event_id": str(uuid4()),
            "occurred_at": occurred_at,
            "source": "git",
            "event_type": "commit",
            "title": message[:500],
            "payload": {
                "commit_hash": sha,
                "branch": branch,
                "message": message[:1000],
                "changed_files": files,
                "repository_name": repository_name,
                "repository": remote[:500],
                "workspace_name": repository_name,
                "collected_at": datetime.now(UTC).isoformat(),
            },
            "privacy_level": "normal",
            "retention_class": "short_term",
        }
        try:
            post_event(event, args.api)
            print(f"sent {sha[:8]} {message}")
        except RuntimeError as exc:
            print(f"SKIP {sha[:8]} {message}  — {exc}")


if __name__ == "__main__":
    main()
