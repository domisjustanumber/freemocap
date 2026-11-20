"""Install and remove of a Windows ML EP (F15 step 5, F16): start one, and cancel a running install.

The running job and how it ended ride `certification.pack_run` and `certification.last_pack_result` of `app_state`;
the EP's new state comes from skellytracker's status, read again when the job ends. A refusal answers this request
with the current reason; nothing is queued.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from freemocap.core.streaming.message_model import EpPackRun
from freemocap.system.certify.quick_check import StartRefused

ep_pack_router = APIRouter(prefix="/certify", tags=["Certification"])


class EpPackRequest(BaseModel):
    execution_provider: str = Field(description="skellytracker's key of a Windows ML EP of this host.")


class EpPackRunState(BaseModel):
    """The running install or remove, as `certification.pack_run` of `app_state` carries it."""
    action: str
    execution_provider: str
    phase: str | None
    fraction: float | None

    @classmethod
    def of(cls, run: EpPackRun) -> "EpPackRunState":
        return cls(action=run.action, execution_provider=run.execution_provider, phase=run.phase, fraction=run.fraction)


class EpPackCancel(BaseModel):
    run: EpPackRunState | None = Field(description="The job that was asked to stop; null when none was running.")


def _refused(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _start(action: str, key: str) -> EpPackRunState:
    from freemocap.app.freemocap_application import get_freemocap_app
    app = get_freemocap_app()
    try:
        return EpPackRunState.of(app.ep_packs.start(action, key, app.pipeline_holds))
    except StartRefused as error:
        raise HTTPException(status_code=error.status, detail=error.detail) from None


def _windows_ml_row(key: str):
    from freemocap.system.certify.ep_packs import windows_ml_row
    row = windows_ml_row(key)
    if row is None:
        raise _refused(400, "not-windows-ml", f"{key} is not an EP of the Windows ML catalog on this system.")
    return row


@ep_pack_router.post("/ep_pack/install", status_code=202, responses={
    400: {"description": "`not-windows-ml`"},
    409: {"description": "`cannot-install` (the EP is not missing, or skellytracker refuses it, for example a field-test "
                         "EP with no opt-in), `pipelines-running` (with `gpu_held_by`: any work), `quick-check-running`, "
                         "or `ep-pack-running`"}})
def install_ep_pack(request: EpPackRequest) -> EpPackRunState:
    """Install the Windows ML package of one EP that is not installed; Windows may download it.

    Refused while any work runs, a quick check runs, or another install or remove runs; while it runs every other start
    is refused. Follow it in `app_state.certification.pack_run`; cancel it with `DELETE /certify/ep_pack`."""
    from skellytracker.core import eps
    from skellytracker.core.errors import EpRequestError, EpUnavailableError
    key = request.execution_provider
    row = _windows_ml_row(key)
    # Only a missing package: an install over a present one would record it as `was_present`, and Remove would then
    # never take away what this app added.
    if row.state != "not_installed":
        raise _refused(409, "cannot-install", f"{row.label} is {row.state.replace('_', ' ')} here; install only adds a "
                                              "missing package.")
    try:
        eps.plan_install([key])  # the same refusals the install would give, before anything starts
    except (EpRequestError, EpUnavailableError) as error:
        raise _refused(409, "cannot-install", str(error)) from None
    return _start("install", key)


@ep_pack_router.post("/ep_pack/remove", status_code=202, responses={
    400: {"description": "`not-windows-ml`"},
    409: {"description": "`pipelines-running` (with `gpu_held_by`: any work), `quick-check-running`, or `ep-pack-running`"}})
def remove_ep_pack(request: EpPackRequest) -> EpPackRunState:
    """Remove the Windows ML package of one EP that this app installed; a package that was on the machine before stays.

    Refused like an install. How it ended shows in `app_state.certification.last_pack_result`."""
    _windows_ml_row(request.execution_provider)
    return _start("remove", request.execution_provider)


@ep_pack_router.delete("/ep_pack")
def cancel_ep_pack() -> EpPackCancel:
    """Ask a running install to stop; Windows ML stops it when it can, and a remove runs to its end."""
    from freemocap.app.freemocap_application import get_freemocap_app
    run = get_freemocap_app().ep_packs.cancel()
    return EpPackCancel(run=None if run is None else EpPackRunState.of(run))
