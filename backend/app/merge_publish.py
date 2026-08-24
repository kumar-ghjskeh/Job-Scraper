"""Merge the currently-published snapshot into the one this run produced.

Used by the publish step so two overlapping scrape runs union rather than
clobber. See snapshot.merge_snapshot_files for why a plain overwrite is unsafe.

    python -m backend.app.merge_publish <remote_jobs.json> [remote_details.json]
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from .snapshot import merge_snapshot_files

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

if __name__ == "__main__":
    data_dir = Path(os.getenv("DATA_DIR", "frontend/public/data"))
    remote_jobs = sys.argv[1]
    remote_details = sys.argv[2] if len(sys.argv) > 2 else None
    merge_snapshot_files(remote_jobs, data_dir / "jobs.json",
                         remote_details, data_dir / "details.json")
