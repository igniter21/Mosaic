#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
backend_src = REPO / "backend" / "src"
sys.path.insert(0, str(backend_src))

from mosaic_memory_api.db import models  # noqa: F401,E402
from mosaic_memory_api.db import context_models, semantic_models  # noqa: F401,E402
from mosaic_memory_api.db.base import Base  # noqa: E402
from mosaic_memory_api.db.session import SessionLocal, engine  # noqa: E402
from mosaic_memory_api.services.lifecycle_service import preview_lifecycle, run_lifecycle  # noqa: E402

Base.metadata.create_all(bind=engine)

with SessionLocal() as db:
    if "--execute" in sys.argv:
        result = run_lifecycle(db, True)
        print(result.model_dump_json(indent=2))
    else:
        result = preview_lifecycle(db)
        print(result.model_dump_json(indent=2))
