"""Arq worker entrypoint: kairos worker | kairos-worker"""

from __future__ import annotations

import sys


def main() -> None:
    try:
        from arq.worker import run_worker

        from kairos.jobs.arq_settings import WorkerSettings
    except ImportError:
        print("Install queue extras: uv sync --extra queue", file=sys.stderr)
        raise SystemExit(1) from None

    run_worker(WorkerSettings)
