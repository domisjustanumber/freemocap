"""Application provider policy and startup diagnostics, never per-frame work."""
from dataclasses import dataclass


def usable_execution_providers() -> list[str]:
    """The EP keys usable on this host now: a built-in EP or an installed EP pack. It loads no library."""
    from skellytracker.core import eps
    from skellytracker.core.eps.records import USABLE_STATES
    return [row.key for row in eps.status().eps if row.state in USABLE_STATES]


@dataclass(frozen=True)
class ModelProviderStatus:
    """The EP key that a run gave to one model: `model_name` is the model's catalog key."""

    model_name: str
    requested_provider: str | None
    applied_providers: tuple[str, ...]
