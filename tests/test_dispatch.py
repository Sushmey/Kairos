"""Tests for job dispatch."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kairos.jobs.dispatch import dispatch_prep_job


@pytest.mark.asyncio
async def test_dispatch_prep_job_local(monkeypatch):
    monkeypatch.setattr("kairos.config.settings.job_backend", "local")
    tasks = MagicMock()
    result = await dispatch_prep_job("job-1", {"sync": False}, background_tasks=tasks)
    assert result == "local"
    tasks.add_task.assert_called_once()
    call_args = tasks.add_task.call_args
    assert call_args[0][1] == "job-1"
    assert call_args[0][2] == {"sync": False}


@pytest.mark.asyncio
async def test_dispatch_prep_job_local_requires_background_tasks(monkeypatch):
    monkeypatch.setattr("kairos.config.settings.job_backend", "local")
    with pytest.raises(ValueError, match="background_tasks"):
        await dispatch_prep_job("job-1", {})
