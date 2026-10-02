"""Explicit local document metadata collector for Mosaic Memory.

The collector reads file names and filesystem metadata only.  It never opens or
uploads document contents.  Each named path is treated as an explicit opt-in.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

DEFAULT_EXTENSIONS = {".doc", ".docx", ".md", ".odt", ".pdf", ".pptx", ".rtf", ".txt", ".xlsx"}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="Files or directories to collect explicitly")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="Local Mosaic API base URL")
    parser.add_argument("--recursive", action="store_true", help="Include supported files below explicitly named directories")
    parser.add_argument("--dry-run", action="store_true", help="Print events without sending them")
    return parser.parse_args()


def documents_for_path(path: Path, recursive: bool) -> Iterator[Path]:
    if path.is_file():
        if path.suffix.lower() in DEFAULT_EXTENSIONS:
            yield path
        return

    if path.is_dir():
        children = path.rglob("*") if recursive else path.iterdir()
        for child in children:
            if child.is_file() and child.suffix.lower() in DEFAULT_EXTENSIONS:
                yield child
        return

    print(f"Skipping missing path: {path}", file=sys.stderr)


def event_for_document(path: Path) -> dict[str, object]:
    details = path.stat()
    return {
        "event_id": str(uuid4()),
        "occurred_at": datetime.now(UTC).isoformat(),
        "source": "document",
        "event_type": "document_indexed",
        "title": path.name,
        "payload": {
            "extension": path.suffix.lower(),
            "size_bytes": details.st_size,
            "modified_at": datetime.fromtimestamp(
                details.st_mtime,
                UTC,
            ).isoformat(),
        },
        "privacy_level": "normal",
        "retention_class": "short_term",
    }


def submit_event(api_url: str, event: dict[str, object]) -> None:
    request = Request(
        f"{api_url.rstrip('/')}/api/v1/events",
        data=json.dumps(event).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        if response.status != 201:
            raise RuntimeError(f"Mosaic API returned status {response.status}")


def main() -> int:
    arguments = parse_arguments()
    collected = 0

    for named_path in arguments.paths:
        for document in documents_for_path(named_path, arguments.recursive):
            event = event_for_document(document)
            if arguments.dry_run:
                print(json.dumps(event, indent=2))
                collected += 1
                continue

            try:
                submit_event(arguments.api_url, event)
            except HTTPError as error:
                detail = error.read().decode(errors="replace")
                print(f"Could not collect {document.name}: {error.code} {detail}", file=sys.stderr)
                return 1
            except (URLError, TimeoutError, RuntimeError) as error:
                print(f"Could not collect {document.name}: {error}", file=sys.stderr)
                return 1
            collected += 1

    print(f"Collected metadata for {collected} document(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
