"""Hand-in of certify reports: the list, the exact file, "send" through the relay and "opened" for the issue form.

Each answer describes the current state on this backend host. Nothing here sends without the person's "send".
"""

import hashlib
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from freemocap.system.certify import relay
from freemocap.system.certify.relay import HandInError
from freemocap.system.certify.report_file import ReportFileError

certify_router = APIRouter(prefix="/certify", tags=["Certification"])

ERROR_STATUS = {"file-changed": 409, "relay-off": 409}  # every other refusal is 422


class HandInReport(BaseModel):
    """One report of the hand-in list (freemocap's own or skellytracker's), in every state."""
    report_id: str
    package: str = Field(description="The package whose certify() made the report: `freemocap` or `skellytracker`.")
    kind: str | None
    created_utc: str | None
    has_failure: bool
    evidence_valid: bool
    incomplete: bool = Field(description="The run did not end: the report's evidence reasons hold `cancelled` or "
                             "`interrupted`, as the report file's header says.")
    state: Literal["pending", "opened", "covered"]
    reference: str | None = Field(description="The issue address, only when it is an issue of the relay's repository.")


class RelayError(BaseModel):
    """The relay's error, or `network`, `bad-response` or `too-large` from this backend."""
    status: int | None
    error: str
    retry: bool
    detail: str | None = Field(description="Plain text from the relay: show it as text, never as markup.")


class OutboxEntry(BaseModel):
    """A file the person chose to send that the relay has not accepted yet."""
    sha256: str
    file_name: str
    report_ids: list[str]
    failed_attempts: int
    last_error: RelayError | None
    retry_pending: bool = Field(description="Sent again at the next backend start.")
    offer_issue_form: bool = Field(description="The relay refused it for good, or the first send and 3 retries failed.")


class HandInList(BaseModel):
    relay_enabled: bool
    reports: list[HandInReport]
    outbox: list[OutboxEntry]


class HandInSelection(BaseModel):
    report_ids: list[str] = Field(min_length=1)
    note: str | None = Field(default=None, description="The person's note; paths and this host's names are removed.")


class ReportIds(BaseModel):
    report_ids: list[str] = Field(min_length=1)


class AcceptedHandIn(HandInSelection):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$", description="The SHA-256 of the file the person viewed.")


class ReportFile(BaseModel):
    file_name: str
    sha256: str
    size_bytes: int
    fits_relay: bool
    content: str


class SendOutcome(BaseModel):
    state: Literal["covered", "kept", "refused"]
    issue_url: str | None
    issue_number: int | None
    duplicate: bool
    error: RelayError | None
    offer_issue_form: bool


def _refused(error: HandInError | ReportFileError) -> HTTPException:
    return HTTPException(status_code=ERROR_STATUS.get(error.code, 422), detail={"code": error.code, "detail": error.detail})


@certify_router.get("/hand_in")
def get_hand_in() -> HandInList:
    """Every certify report on this host with its hand-in state, the files waiting in the outbox, and whether the
    relay is on (when it is off, only the issue form is offered)."""
    return HandInList(
        relay_enabled=bool(relay.relay_url()),
        reports=[HandInReport(**{**row, "reference": relay.issue_url_or_none(row.get("reference")),
                                 "incomplete": relay.report_incomplete(row["report_id"])})
                 for row in relay.hand_in_reports(include_handed_in=True)],
        outbox=[OutboxEntry(**entry) for entry in relay.outbox_entries()])


@certify_router.post("/hand_in/file")
def get_hand_in_file(selection: HandInSelection) -> ReportFile:
    """The exact report file that "send" or the issue form hands in for these reports and this note."""
    try:
        name, body = relay.report_file_for(selection.report_ids, selection.note)
    except (HandInError, ReportFileError) as error:
        raise _refused(error) from None
    return ReportFile(file_name=name, sha256=hashlib.sha256(body).hexdigest(), size_bytes=len(body),
                      fits_relay=len(body) <= relay.RELAY_MAX_BYTES, content=body.decode("utf-8"))


@certify_router.post("/hand_in/send")
def send_hand_in(accepted: AcceptedHandIn) -> SendOutcome:
    """The person's "send" of the file they viewed: it is kept in the outbox, then sent to the relay."""
    try:
        return SendOutcome(**relay.send_report(accepted.report_ids, accepted.note, accepted.sha256))
    except (HandInError, ReportFileError) as error:
        raise _refused(error) from None


@certify_router.post("/hand_in/opened")
def mark_hand_in_opened(accepted: AcceptedHandIn) -> HandInList:
    """The person saved the file they viewed and opened the issue form: its reports count as handed in."""
    try:
        relay.mark_opened(accepted.report_ids, accepted.note, accepted.sha256)
    except (HandInError, ReportFileError) as error:
        raise _refused(error) from None
    return get_hand_in()


@certify_router.post("/hand_in/not_sent")
def mark_hand_in_not_sent(selection: ReportIds) -> HandInList:
    """"Not sent": these reports are pending again (also when opened or covered, which clears the issue address)
    and any kept outbox file that holds them, waiting to retry or not, is deleted."""
    try:
        relay.mark_not_sent(selection.report_ids)
    except HandInError as error:
        raise _refused(error) from None
    return get_hand_in()
