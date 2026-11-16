"""The EP rows of skellytracker for the application, never per-frame work."""


def execution_provider_rows() -> list:
    """The skellytracker `PackStatus` row of each EP of this host, in skellytracker's order. It loads no library."""
    from skellytracker.core import eps
    return list(eps.status().eps)


def usable_execution_providers() -> list[str]:
    """The keys of the EPs that skellytracker says are usable on this host now."""
    return [row.key for row in execution_provider_rows() if row.usable]


def suggested_execution_provider(saved_key: str) -> str | None:
    """The EP key to use for a key saved by FreeMoCap before skellytracker 2, as skellytracker suggests it on this
    host; None means Auto. freemocap calls it only for a legacy settings file and holds no key list."""
    from skellytracker.core.eps import suggest_execution_provider
    return suggest_execution_provider(saved_key)
