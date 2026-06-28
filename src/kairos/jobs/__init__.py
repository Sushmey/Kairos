"""Background job dispatch (local or Celery)."""

from kairos.jobs.dispatch import dispatch_prep_job

__all__ = ["dispatch_prep_job"]
