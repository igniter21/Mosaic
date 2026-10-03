#!/usr/bin/env python3
"""Evaluate Mosaic Context OS retrieval against a small JSONL fixture.

Each line should look like:
{"query":"...", "expected_memory_ids":["id1","id2"]}

Usage:
  python scripts/benchmark_retrieval.py fixture.jsonl --base-url http://127.0.0.1:8000/api/v1
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen


def post(url: str, payload: dict) -> dict:
    req = Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.fixture.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise SystemExit("Fixture is empty.")

    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    for row in rows:
        result = post(f"{args.base_url}/context/ask", {"query": row["query"], "limit": 10})
        returned = [item["id"] for item in result.get("memories", [])]
        expected = set(row.get("expected_memory_ids", []))
        if not expected:
            continue
        hits = [memory_id for memory_id in returned if memory_id in expected]
        recalls.append(len(hits) / len(expected))
        reciprocal_ranks.append(1.0 / (returned.index(hits[0]) + 1) if hits else 0.0)

    if not recalls:
        raise SystemExit("No rows with expected_memory_ids were found.")
    print(json.dumps({
        "queries_evaluated": len(recalls),
        "recall_at_10": round(sum(recalls) / len(recalls), 4),
        "mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4),
    }, indent=2))


if __name__ == "__main__":
    main()
