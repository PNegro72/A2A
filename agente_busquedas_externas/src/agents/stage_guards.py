"""Loud-failure guards for the sourcing pipeline stages.

ADK's ``output_key`` silently no-ops when an agent emits no text, so a stage
that fails leaves its state key *absent* and every downstream stage degrades
quietly — the observed symptom was a 200 OK carrying an empty shortlist. These
guards turn that into an explicit error naming the stage and the key, and they
log what each stage handed over so the hand-off is auditable in the run log.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from google.adk.agents.callback_context import CallbackContext

logger = logging.getLogger("google_adk." + __name__)


class PipelineStageError(RuntimeError):
    """A pipeline stage produced no usable output."""


def _is_present(value: Any) -> bool:
    """Whether a state value counts as "the stage actually wrote something"."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list, tuple, set)):
        return bool(value)
    return True


def _coerce_container(value: Any) -> Any:
    """Return ``value`` as a dict/list, parsing JSON text when needed."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


# The keys the pipeline's wire schemas use to wrap their collections.
_COLLECTION_KEYS = ("leads", "identities", "candidates")


def count_items(value: Any, *keys: str) -> int:
    """Count the items a stage produced.

    Handles both shapes a state value can take: the dict ADK stores when the
    agent has an ``output_schema``, and the raw JSON text it stores otherwise.
    """
    container = _coerce_container(value)
    if isinstance(container, list):
        return len(container)
    if isinstance(container, dict):
        for key in keys or _COLLECTION_KEYS:
            inner = container.get(key)
            if isinstance(inner, list):
                return len(inner)
        return len(container)
    return 0


def require_output(stage: str, key: str) -> Callable[[CallbackContext], None]:
    """Build an ``after_agent_callback`` asserting the stage wrote ``key``."""

    def _guard(callback_context: CallbackContext) -> None:
        value = callback_context.state.get(key)
        if not _is_present(value):
            raise PipelineStageError(
                f"stage '{stage}' produced no output: state['{key}'] is "
                f"{'absent' if value is None else 'empty'}. The stage either "
                "returned no text or its model call failed; refusing to "
                "continue with a silently incomplete pipeline."
            )
        logger.info(
            "[stage-guard] %s -> state['%s'] ok (%d item(s), %d chars)",
            stage,
            key,
            count_items(value),
            len(value if isinstance(value, str) else json.dumps(value, default=str)),
        )

    return _guard


def require_any_items(stage: str, *keys: str) -> Callable[[CallbackContext], None]:
    """Build a ``before_agent_callback`` asserting the stage has input to work on.

    Reaching the merge/scoring/reporting stages with zero items everywhere means
    every upstream source failed, which must surface as an error rather than as
    an empty shortlist that reads like "no matching candidates".
    """

    def _guard(callback_context: CallbackContext) -> None:
        counts = {key: count_items(callback_context.state.get(key)) for key in keys}
        logger.info("[stage-guard] %s <- input counts %s", stage, counts)
        if not any(counts.values()):
            raise PipelineStageError(
                f"stage '{stage}' has nothing to work with: {counts}. "
                "Every upstream source returned nothing — check the source "
                "agents' logs before trusting an empty shortlist."
            )

    return _guard
