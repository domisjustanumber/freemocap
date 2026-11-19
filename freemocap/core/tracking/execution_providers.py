"""The EP rows of skellytracker for the application, never per-frame work."""


def execution_provider_status():
    """skellytracker's `EpStatus` of this host: its EP rows and its recommendations. It loads no library."""
    from skellytracker.core import eps
    return eps.status()


def execution_provider_rows() -> list:
    """The skellytracker `PackStatus` row of each EP of this host, in skellytracker's order. It loads no library."""
    return list(execution_provider_status().eps)


def usable_execution_providers() -> list[str]:
    """The keys of the EPs that skellytracker says are usable on this host now: on one GPU or more by its per-GPU
    flags `checks[n].usable`, which read the quick checks; an EP with no GPU check (cpu) by its own `usable`."""
    return [row.key for row in execution_provider_rows()
            if row.usable and (not row.checks or any(check.usable for check in row.checks))]


def suggested_execution_provider(saved_key: str) -> str | None:
    """The EP key to use for a key saved by FreeMoCap before skellytracker 2, as skellytracker suggests it on this
    host; None means Auto. freemocap calls it only for a legacy settings file and holds no key list."""
    from skellytracker.core.eps import suggest_execution_provider
    return suggest_execution_provider(saved_key)
