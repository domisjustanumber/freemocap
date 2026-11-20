"""The quick check of one EP on one GPU (F9) and the start check of every package (decisions 13 to 17): their plans,
starts and cancel.

The running check, its progress and every EP's state ride the `certification` field of `app_state`. A refusal answers
this request with the current reason (other work runs, a check runs, the EP cannot run here); nothing is queued.
`admitted` is the route side of the busy rule for the starts that have no admission point in the application.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.streaming.message_model import CertificationPair, CertificationRun
from freemocap.system.certify.quick_check import StartRefused

quick_check_router = APIRouter(prefix="/certify", tags=["Certification"])

_DEFAULTS = CameraNodeConfig()


def _admission(kind_of):
    def dependency(request: Request):
        from freemocap.app.freemocap_application import get_freemocap_app
        kind = kind_of(request)
        try:
            checks = None if kind is None else get_freemocap_app().quick_checks
        except RuntimeError:  # no application, so no quick check (routers served on their own, as in tests)
            checks = None
        if checks is None:
            yield
            return
        try:
            claim = checks.claim(kind)
        except StartRefused as error:
            raise HTTPException(status_code=error.status, detail=error.detail) from None
        try:
            yield
        finally:
            checks.release(claim)
    return Depends(dependency)


def admitted(kind: str):
    """A route dependency: refuse this start of work with `quick-check-running` while a check runs, else hold its
    claim for the request so a check admitted meanwhile is refused (H1, H2)."""
    return _admission(lambda request: kind)


# The skellycam routes that start work; closing, stopping, pausing and detecting stay allowed.
_CAMERA_STARTS = {"/camera/group/apply": "cameras", "/camera/group/all/record/start": "recording"}
camera_starts_admitted = _admission(lambda request: next(
    (kind for path, kind in _CAMERA_STARTS.items() if request.url.path.endswith(path)), None))


class QuickCheckPlan(BaseModel):
    """skellytracker's `certify_plan("quick")` for one EP on one GPU."""
    seconds_estimate: int = Field(description="A one-off upper estimate of the whole check, in seconds.")
    downloads: list[dict]
    checks: list[str] = Field(description="skellytracker's name of each EP check.")
    not_run: dict[str, str] = Field(description="The EP checks that cannot run, with skellytracker's reason code.")


class QuickCheckRequest(BaseModel):
    execution_provider: str = Field(description="skellytracker's EP key.")
    device_key: str = Field(description="skellytracker's device key of the GPU (the Device row's choice).")
    detector_type: Literal["rtmpose", "mediapipe"] = _DEFAULTS.detector_type
    rtmpose_model_name: Literal["rtmw-x-l_256x192", "rtmw-x-l_384x288", "rtmw-l-m_256x192"] = _DEFAULTS.rtmpose_model_name


class QuickCheckPairState(BaseModel):
    execution_provider: str
    device_key: str | None


class QuickCheckRunState(BaseModel):
    """The running check, as the `certification.run` field of `app_state` carries it."""
    level: str
    items: list[QuickCheckPairState]
    state: str
    done: int
    total: int | None
    seconds_estimate: int | None

    @classmethod
    def of(cls, run: CertificationRun) -> "QuickCheckRunState":
        return cls(level=run.level, items=[QuickCheckPairState(execution_provider=item.execution_provider,
                                                               device_key=item.device_key) for item in run.items],
                   state=run.state, done=run.done, total=run.total, seconds_estimate=run.seconds_estimate)


class QuickCheckCancel(BaseModel):
    run: QuickCheckRunState | None = Field(description="The check that was asked to stop; null when none was running.")


def _plan(execution_provider: str, device_key: str) -> dict:
    import skellytracker
    from skellytracker.core.errors import EpRequestError
    try:
        return skellytracker.certify_plan("quick", execution_providers=[execution_provider], device=device_key)
    except EpRequestError as error:  # an unknown or reserved EP key, or a device key that is not a GPU of this host
        raise HTTPException(status_code=400, detail={"code": "unknown-ep-or-device", "message": str(error)}) from None


@quick_check_router.get("/quick_check/plan")
def get_quick_check_plan(execution_provider: str, device_key: str) -> QuickCheckPlan:
    """What the quick check of one EP on one GPU would run, its estimate, and why a part cannot run here."""
    plan = _plan(execution_provider, device_key)
    details = plan.get("details") or {}
    return QuickCheckPlan(seconds_estimate=plan["seconds_estimate"], downloads=plan["downloads"],
                          checks=details.get("checks", []), not_run=details.get("not_run", {}))


@quick_check_router.post("/quick_check", status_code=202, responses={
    400: {"description": "`unknown-ep-or-device`"},
    409: {"description": "`pipelines-running` (with `gpu_held_by`: any work, not only pipelines), "
                         "`quick-check-running`, or `cannot-run` (with skellytracker's `reason_code`)"}})
def start_quick_check(request: QuickCheckRequest) -> QuickCheckRunState:
    """Start the quick check of one EP on one GPU with the person's detector pipeline, in a child process.

    Refused while other work runs (a pipeline, recording, connected cameras, a sync or export job) or another check
    runs; follow it in `app_state.certification.run`. When it ends, `certification.items` shows skellytracker's
    stored result and `certification.last_result` how it ended."""
    from freemocap.app.freemocap_application import get_freemocap_app
    plan = _plan(request.execution_provider, request.device_key)
    not_run = (plan.get("details") or {}).get("not_run") or {}
    if not_run:
        reason_code = next(iter(not_run.values()))
        raise HTTPException(status_code=409, detail={
            "code": "cannot-run", "reason_code": reason_code,
            "message": f"The quick check of {request.execution_provider} on {request.device_key} cannot run here: "
                       f"{reason_code}."})
    app = get_freemocap_app()
    try:
        run = app.quick_checks.start(
            pair=CertificationPair(request.execution_provider, request.device_key), detector_type=request.detector_type,
            rtmpose_model_name=request.rtmpose_model_name, seconds_estimate=plan.get("seconds_estimate"),
            holds=app.pipeline_holds)
    except StartRefused as error:
        raise HTTPException(status_code=error.status, detail=error.detail) from None
    return QuickCheckRunState.of(run)


@quick_check_router.delete("/quick_check")
def cancel_quick_check() -> QuickCheckCancel:
    """Stop the running check; it ends within about a second, its report says `cancelled`, and the stored result of
    the EP does not change."""
    from freemocap.app.freemocap_application import get_freemocap_app
    run = get_freemocap_app().quick_checks.cancel()
    return QuickCheckCancel(run=None if run is None else QuickCheckRunState.of(run))


class PackagePlan(BaseModel):
    """One package's `certify_plan("quick")`, as the start check runs it."""
    package: str
    seconds_estimate: int = Field(description="A one-off upper estimate of the package's checks, in seconds.")
    downloads: list[dict]
    system_changes: list[str]
    checks: list[str] = Field(description="The checks it runs: freemocap's check names, skellytracker's EP check names.")


class StartCheckPlan(BaseModel):
    packages: list[PackagePlan] = Field(description="freemocap's own checks, then skellytracker's (skellycam's are not built).")


def _start_plans() -> list[PackagePlan]:
    import skellytracker
    from freemocap.system.certify.own_checks import certify_plan
    return [PackagePlan(package=plan["package"], seconds_estimate=plan["seconds_estimate"], downloads=plan["downloads"],
                        system_changes=plan.get("system_changes", []), checks=(plan.get("details") or {}).get("checks", []))
            for plan in (certify_plan("quick"), skellytracker.certify_plan("quick"))]


@quick_check_router.get("/start_check/plan")
def get_start_check_plan() -> StartCheckPlan:
    """What the start check runs on this machine: each package's checks, estimate, downloads and changes."""
    return StartCheckPlan(packages=_start_plans())


class StartCheckRequest(BaseModel):
    blender_exe_path: str | None = Field(alias="blenderExePath", default=None, description="The Blender path chosen in "
                                         "Blender settings; null uses freemocap's best guess.")


@quick_check_router.post("/start_check", status_code=202, responses={
    409: {"description": "`pipelines-running` (with `gpu_held_by`: any work, not only pipelines) or `quick-check-running`"}})
def start_start_check(request: Request, body: StartCheckRequest | None = None) -> QuickCheckRunState:
    """Start the quick check of this machine: freemocap's own checks, then skellytracker's quick check of every GPU EP
    with no reviewed row (field-test EPs included), in a child process. Refused like a quick check; stop it with
    `DELETE /certify/quick_check`. Follow it in `app_state.certification.run` (no `items`); `start_results` says how it
    ended, and `start_required` turns false once it ended other than by a cancel."""
    from freemocap.app.freemocap_application import get_freemocap_app
    seconds = sum(plan.seconds_estimate for plan in _start_plans())
    client = request.client.host if request.client else None
    app = get_freemocap_app()
    try:
        run = app.quick_checks.start(pair=None, detector_type=_DEFAULTS.detector_type, rtmpose_model_name=None,
                                     seconds_estimate=seconds, holds=app.pipeline_holds,
                                     blender_exe_path=body.blender_exe_path if body else None,
                                     ui_remote=None if client is None else client not in ("127.0.0.1", "::1", "localhost"))
    except StartRefused as error:
        raise HTTPException(status_code=error.status, detail=error.detail) from None
    return QuickCheckRunState.of(run)
