"""Deterministic task IDs for pipeline timing events."""

CLOCK_DOMAIN_PERF_COUNTER = "perf_counter"


def batch_task_id(
        *,
        frame_number: int,
        node_kind: str,
        stage: str,
) -> str:
    return f"{frame_number}:batch:{node_kind}:{stage}"


def camera_task_id(
        *,
        frame_number: int,
        camera_id: str,
        node_kind: str,
        stage: str,
) -> str:
    return f"{frame_number}:{camera_id}:{node_kind}:{stage}"
