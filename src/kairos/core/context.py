"""Read live headspace context."""

from kairos.models.schemas import ContextSnapshot
from kairos.observability.bus import event_bus


def read_context() -> ContextSnapshot:
    """Return the live headspace vector. Stub until calendar/location sensor is wired."""
    # TODO: wire Google Calendar poller + location toggle
    ctx = ContextSnapshot(
        calendar_gap_minutes=90,
        meeting_density_today=0.3,
        location_type="cafe",
        surfaces_today=1,
    )
    event_bus.emit("context", "Read current headspace", context=ctx.model_dump())
    return ctx
