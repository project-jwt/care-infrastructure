# core/ai.py — Gemini client + draft_summary for POST /api/summaries/draft
#
# The AI is a QUIET TOOL here (spec: "AI in the background, not a companion"):
# one function in, one structured result out. No chat history, no persona —
# the conversation state (prior answers) lives in the request, not on a server.
#
# Two reliability techniques worth knowing:
#   1. system_instruction — the product rules ride along with EVERY request.
#      Prompt = product design: the one-question rule, the plain-language
#      rule, and "never invent details" are all enforced in prose below.
#   2. response_schema — Gemini is CONSTRAINED to emit JSON matching our
#      shape. No ```json fences, no chatty preamble, no parse-and-pray.

import typing

import google.generativeai as genai

from config import settings
from schemas.summary import ClarifyingAnswer, DraftOut

genai.configure(api_key=settings.gemini_api_key)


# What Gemini must return, as a TypedDict (the SDK's schema format).
# All three keys always present; "empty" values signal which mode we're in.
# Mapped to the API's DraftOut (None-able summaryText) before returning.
class _DraftSchema(typing.TypedDict):
    needsClarification: bool
    questions: list[str]
    summaryText: str


SYSTEM_PROMPT = """\
You help older adults turn a spoken description of a problem into a short,
clear written summary that a family member or a helpline agent can act on.

The input is an imperfect speech-to-text transcript: expect filler words,
repetition, and transcription mistakes. Never comment on these.

Decide between exactly two responses:

1. If the transcript (plus any clarifying answers) contains enough to act on,
   write the summary:
   - needsClarification: false, questions: [], summaryText: filled in.
   - Write in first person, as the user ("I received a call...") — they will
     review, edit, and send it as their own words.
   - 3 to 6 short sentences, plain everyday language, no jargon.
   - Space it for easy reading by an older adult: 2-3 short paragraphs —
     what happened, what they asked for, what I did about it. Separate each
     paragraph with a blank line (the two characters "\\n\\n" inside the JSON
     string). Never run sentences together and never return one dense block.
   - Keep every concrete detail: names, phone numbers, amounts, dates,
     what was asked for, what the user did or didn't do.
   - Never invent or assume details that aren't in the transcript or answers.
     Do not add feelings, intentions, or conclusions the user didn't state —
     if the transcript is short, the summary is simply short.

2. Only if something essential is missing (you could not tell a helpline
   what happened), ask for it:
   - needsClarification: true, summaryText: "", questions: exactly ONE short,
     concrete question a 78-year-old can answer in a sentence.
   - Never ask about details that are merely nice to have.
   - If clarifying answers are already present, strongly prefer writing the
     summary with what you have rather than asking again.
"""

# NOTE: the spec named gemini-2.0-flash, but its free tier was retired
# (429 with "limit: 0") — 2.5-flash is the current free-tier flash model.
model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=SYSTEM_PROMPT)


async def draft_summary(transcript: str, answers: list[ClarifyingAnswer]) -> DraftOut:
    """One stateless draft round: transcript + answers so far -> DraftOut.

    Raises on network/quota errors — the router translates those to a 502.
    """
    parts = [f"Transcript:\n{transcript}"]
    if answers:
        qa = "\n".join(f"Q: {a.question}\nA: {a.answer}" for a in answers)
        parts.append(f"Clarifying answers so far:\n{qa}")

    response = await model.generate_content_async(
        "\n\n".join(parts),
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=_DraftSchema,
        ),
    )

    # Guaranteed-shape JSON in, our API shape out.
    draft = DraftOut.model_validate_json(response.text)
    if not draft.needs_clarification and not draft.summary_text:
        # Belt-and-suspenders: a summary round must actually contain one.
        raise ValueError("Gemini returned neither questions nor a summary")
    if not draft.summary_text:
        # Gemini's schema requires all keys, so clarification rounds carry
        # summaryText: "" — normalize to null so clients can just check
        # `summaryText !== null` without also knowing about "".
        draft.summary_text = None
    return draft
