"""Antigravity LocalAgentConfig factory for Kairos."""

from google.antigravity import CapabilitiesConfig, LocalAgentConfig
from google.antigravity.hooks import policy

from kairos.agent.hooks import OBSERVABILITY_HOOKS
from kairos.agent.prompts import SYSTEM_INSTRUCTIONS
from kairos.agent.tools import ALL_TOOLS
from kairos.config import settings
from kairos.models.schemas import SurfaceDecision


def build_agent_config() -> LocalAgentConfig:
    """Build a read-only Kairos agent: custom tools only, no filesystem/shell."""
    return LocalAgentConfig(
        system_instructions=SYSTEM_INSTRUCTIONS,
        model=settings.gemini_model,
        api_key=settings.gemini_api_key,
        tools=ALL_TOOLS,
        hooks=OBSERVABILITY_HOOKS,
        policies=[
            policy.allow_all(),
        ],
        capabilities=CapabilitiesConfig(
            # Disable Antigravity builtins — Kairos tools talk to Mongo/calendar/notifier
            enabled_tools=[],
        ),
        response_schema=SurfaceDecision,
    )
