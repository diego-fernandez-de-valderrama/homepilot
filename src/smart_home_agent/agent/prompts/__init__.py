"""System instruction of the HomePilot agent: static rules, the memory rules and the per-turn instruction provider."""

from smart_home_agent.agent.prompts.base_instruction import BASE_INSTRUCTION
from smart_home_agent.agent.prompts.instruction import build_instruction
from smart_home_agent.agent.prompts.memory_instruction import MEMORY_INSTRUCTION

__all__ = ["BASE_INSTRUCTION", "MEMORY_INSTRUCTION", "build_instruction"]
