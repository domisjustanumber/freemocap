"""Application provider policy and startup diagnostics, never per-frame work."""
from dataclasses import dataclass
from typing import Annotated, Literal, get_args

from pydantic import BeforeValidator

ExecutionProviderName = Literal["cpu", "coreml", "cuda", "trt-rtx"]
"""The EP keys of skellytracker 2.0. DirectML and the classic TensorRT are not in v2."""
EXECUTION_PROVIDERS: tuple[str, ...] = get_args(ExecutionProviderName)
REMOVED_PROVIDERS = ("trt", "directml")
RequestedExecutionProvider = Annotated[
    ExecutionProviderName | None, BeforeValidator(lambda value: None if value in REMOVED_PROVIDERS else value)]
"""A saved choice; None is Auto. A saved v1 choice that v2 does not have reads as Auto."""


def usable_execution_providers() -> list[str]:
    """The v2 EP keys usable on this host now: a built-in EP or an installed EP pack. It loads no library."""
    from skellytracker.core import eps
    from skellytracker.core.eps.records import USABLE_STATES
    return [row.key for row in eps.status().eps if row.key in EXECUTION_PROVIDERS and row.state in USABLE_STATES]


@dataclass(frozen=True)
class ModelProviderStatus:
    """The EP key that a run gave to one model: `model_name` is the model's catalog key."""

    model_name: str
    requested_provider: str | None
    applied_providers: tuple[str, ...]
