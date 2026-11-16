"""Application provider policy and startup diagnostics, never per-frame work."""
from dataclasses import dataclass


def usable_execution_provider_rows() -> list:
    """The skellytracker `PackStatus` rows of the EPs usable on this host now, a built-in EP or an installed
    EP pack, in skellytracker's order. It loads no library."""
    from skellytracker.core import eps
    from skellytracker.core.eps.records import USABLE_STATES
    return [row for row in eps.status().eps if row.state in USABLE_STATES]


def usable_execution_providers() -> list[str]:
    """The keys of `usable_execution_provider_rows`."""
    return [row.key for row in usable_execution_provider_rows()]


@dataclass(frozen=True)
class ModelProviderStatus:
    """The EP key that a run gave to one model: `model_name` is the model's catalog key."""

    model_name: str
    requested_provider: str | None
    applied_providers: tuple[str, ...]
