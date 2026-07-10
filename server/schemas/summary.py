# schemas/summary.py — request/response shapes for §Summaries (Primary only)
# and §Contact Dashboard's received-summary items (Contact only).

from datetime import datetime

from pydantic import Field

from schemas.base import CamelModel


class ClarifyingAnswer(CamelModel):
    """One question-and-answer pair from a previous draft round."""

    question: str  # the question the AI asked
    answer: str    # what the user said back


class DraftIn(CamelModel):
    """POST /api/summaries/draft body: { transcript, answers=[] }

    The clarifying loop is STATELESS: each round the client resends the
    original transcript plus ALL answers so far. Nothing about the
    conversation is stored server-side until the user saves the summary.
    """

    transcript: str = Field(min_length=1)  # the speech-to-text output; required
    answers: list[ClarifyingAnswer] = []   # empty on the first round


class DraftOut(CamelModel):
    """Draft response — EITHER of two shapes (spec §Summaries):
      needs more detail: { needsClarification: true,  questions: ["..."] }
      summary ready:     { needsClarification: false, summaryText: "..." }
    """

    needs_clarification: bool
    questions: list[str] = []        # only populated when clarification is needed
    summary_text: str | None = None  # only populated when the summary is ready


class SummaryCreate(CamelModel):
    """POST /api/summaries body: { transcript?, summaryText }
    transcript is optional (spec) — the frontend may discard the raw speech."""

    transcript: str | None = None
    summary_text: str = Field(min_length=1)


class SummaryUpdate(CamelModel):
    """PATCH /api/summaries/:id body: { summaryText } — required, the only
    editable field."""

    summary_text: str = Field(min_length=1)


class SummaryOut(CamelModel):
    """Detail response (POST /summaries, GET/PATCH /summaries/:id):
    { id, transcript, summaryText, createdAt, updatedAt }"""

    id: int
    transcript: str | None
    summary_text: str
    created_at: datetime
    updated_at: datetime


class SummaryListOut(CamelModel):
    """List-item response for GET /api/summaries — the spec's list shape has
    NO transcript: { id, summaryText, createdAt, updatedAt }. Same allowlist
    trick as UserOut dropping password_hash: no field, can't appear."""

    id: int
    summary_text: str
    created_at: datetime
    updated_at: datetime


class SendIn(CamelModel):
    """POST /api/summaries/:id/send body: { contactIds: [1, 2] }
    min_length=1 — sending to nobody is a validation error (422), not a
    silent no-op."""

    contact_ids: list[int] = Field(min_length=1)


class SentTo(CamelModel):
    """One delivery inside SendOut: { contactId, sentAt } — built from the
    summary_recipients rows record_send returns."""

    contact_id: int
    sent_at: datetime


class SendOut(CamelModel):
    """POST /api/summaries/:id/send response:
    { summaryId, sentTo: [ { contactId, sentAt } ] }"""

    summary_id: int
    sent_to: list[SentTo]


class SummarySender(CamelModel):
    """The `from` object on a received summary: { id, fullName } — the
    primary user who sent it, and nothing more (no email, no role)."""

    id: int
    full_name: str


class ReceivedSummaryOut(CamelModel):
    """List-item response for GET /api/received-summaries:
    { summaryId, summaryText, sentAt, from: { id, fullName } }

    `from` is a Python keyword, so the field is from_ with an explicit alias
    (to_camel would produce "from_", not "from"). CamelModel's
    populate_by_name lets the router construct it as from_=..., and FastAPI
    serializes by alias, so the JSON key comes out as plain "from"."""

    summary_id: int
    summary_text: str
    sent_at: datetime
    from_: SummarySender = Field(alias="from")
