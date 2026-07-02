# TODO: Google Gemini client for POST /api/summaries/draft.
# Expected functions:
#   - draft_summary(transcript, answers) -> DraftOut
#     Sends the transcript + prior answers to Gemini, requests structured JSON
#     matching schemas.summary.DraftOut, returns either clarifying questions or
#     a finished summaryText.
# Reads GEMINI_API_KEY from settings.

import google.generativeai as genai
