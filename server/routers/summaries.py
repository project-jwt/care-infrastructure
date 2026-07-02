# TODO: implement per spec §Summaries (Primary only)
#   - POST   /api/summaries/draft       -> AI draft or clarifying questions (no DB write)
#   - POST   /api/summaries             -> save a finalized summary
#   - GET    /api/summaries             -> list current user's summaries, newest first
#   - GET    /api/summaries/:id         -> one summary owned by current user
#   - PATCH  /api/summaries/:id         -> edit summaryText
#   - DELETE /api/summaries/:id         -> delete
#   - POST   /api/summaries/:id/send    -> email to trusted contacts, record sends

from fastapi import APIRouter

# router = APIRouter(prefix="/summaries", tags=["summaries"])
