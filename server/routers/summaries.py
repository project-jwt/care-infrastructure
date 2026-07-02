# TODO: implement per spec §Summaries (Primary only)
#   - POST   /api/summaries/draft       -> AI draft or clarifying questions (no DB write)
#                                          uses core.ai.draft_summary(...)
#   - POST   /api/summaries             -> save a finalized summary
#   - GET    /api/summaries             -> list current user's summaries, newest first
#   - GET    /api/summaries/:id         -> one summary owned by current user
#   - PATCH  /api/summaries/:id         -> edit summaryText
#   - DELETE /api/summaries/:id         -> delete
#   - POST   /api/summaries/:id/send    -> email to trusted contacts, record sends
#                                          uses core.email.send_summary_email(...)

from fastapi import APIRouter

# router = APIRouter(prefix="/summaries", tags=["summaries"])
