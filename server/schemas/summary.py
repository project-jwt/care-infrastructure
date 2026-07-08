# schemas/summary.py — request/response shapes for §Summaries (Primary only)
#
# TODO (built with the save/send endpoints, not the AI draft step):
#   - SummaryCreate   ( transcript?, summaryText )
#   - SummaryOut      ( id, transcript?, summaryText, createdAt, updatedAt )
#   - SummaryUpdate   ( summaryText )
#   - SendIn          ( contactIds: list[int] )
#   - SendOut         ( summaryId, sentTo: [ { contactId, sentAt } ] )

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
