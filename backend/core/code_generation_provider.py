from __future__ import annotations

from core import code_gen as legacy_code_gen
from core.provider_router import call_llm as routed_call_llm

# Rebind the provider hook once at module import so legacy generator logic uses
# the provider router without changing the protected connector-template source.
legacy_code_gen.call_provider_llm = routed_call_llm


def generate_agent_definition(gap_info):
    return legacy_code_gen.generate_agent_definition(gap_info)


def generate_connector(gap_info, language: str = "python"):
    return legacy_code_gen.generate_connector(gap_info, language=language)
