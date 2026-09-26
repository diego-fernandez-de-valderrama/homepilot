"""Semantic input guardrail and deterministic output checks around the existing HomePilot agent.

Input: Gemini embeddings of the user message compared (cosine, locally) with cached embeddings of
semantic prototypes per category. Wiring/mains instructions, off-topic requests and prompt injection
are answered with a deterministic reply before the generative model is called.
Output: the final model answer is checked against the catalog (electrical instructions, unknown
products, unsupported compatibility claims, prompt leaks, off-topic drift) and replaced by a safe
fallback when a critical check fails. Both hook into the agent through ADK callbacks.
"""
