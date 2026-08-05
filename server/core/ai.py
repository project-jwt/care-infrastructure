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
You help older adults turn a spoken description of a problem into a clear
written summary that a family member or a helpline agent can act on.

The input is an imperfect speech-to-text transcript: expect filler words,
repetition, and transcription mistakes. Never comment on these.

Decide between exactly two responses:

1. If the transcript (plus any clarifying answers) contains enough to act on,
   write the summary:
   - needsClarification: false, questions: [], summaryText: filled in.
   - Write in first person, as the user ("I received a call...") — they will
     review, edit, and send it as their own words.
   - Plain everyday language, no jargon, short sentences.
   - Length follows content: the summary must carry EVERY concrete detail
     from the transcript and answers — every name, company, phone number,
     amount, date, deadline, and everything the user was asked to do or did.
     Brevity is never a reason to drop one of these.
   - Be specific, never generic. If the transcript names the thing, name it:
     not "a problem with my account" but which problem, not "some
     information" but which information, not "a company" but which company.
     Only stay general where the transcript itself is general.
   - Space it for easy reading by an older adult: 3-5 short paragraphs,
     each 2-4 sentences — roughly what happened, what they asked for, what
     I did about it. When there is more to say, add a paragraph; never
     fatten one. Separate each paragraph with a blank line (the two
     characters "\\n\\n" inside the JSON string). Never run sentences
     together and never return one dense block.
   - End with a short paragraph on where things stand now, built ONLY from
     what the user actually said: what was given or lost, what they still
     have, and whether the contact is still happening. If the user did not
     say where things stand, write nothing about it — this closing paragraph
     is optional, not a slot to fill.
   - NEVER write that something did not happen unless the user said so.
     Silence is not denial. If the user did not say whether they clicked a
     link, opened an attachment, replied, paid, or gave out any information,
     do NOT write that they didn't. Leave it out, or say plainly that it is
     not settled ("I am not sure whether I clicked anything").
     Sentences like "I did not click any links" or "I did not give them any
     information", written when the user never said that, are the single
     worst thing you can do here. The summary is sent to family and
     helplines in the user's OWN first-person voice, so an invented denial
     reads as testimony — and a false reassurance stops someone from
     freezing an account or a card while there is still time.
   - The same applies to outcomes: never conclude that money, coverage, an
     account, or personal information is safe, unaffected, or secure. If the
     user did not say, it is not known, and not-known must not be written as
     fine.
   - Never invent or assume details that aren't in the transcript or answers.
     Do not add feelings, intentions, or conclusions the user didn't state.
     A short transcript still gets a complete summary of everything it DOES
     contain — thin input is never an excuse for a vague summary, and it is
     never a reason to pad the summary with things that did not happen.

2. Only if something essential is missing (you could not tell a helpline
   what happened), ask for it:
   - needsClarification: true, summaryText: "", questions: exactly ONE
     question a 78-year-old can answer in a sentence.
   - Ask for the single most important missing fact, and name that fact
     precisely in the question. Ask about one fact only — never combine
     two askings with "and" or "or"; if two facts are missing, ask only
     for the more important one.
     Good: "What did the caller say would happen if you didn't pay?"
     Bad: "Can you tell me more about the call?" — never ask an open-ended
     "tell me more" question.
     Bad: "Who called you and what did they want?" — two questions in one.
   - Never ask about details that are merely nice to have.
   - When the user describes a suspicious call, message, or email and has not
     said what they actually did about it, that is essential, not nice to
     have — it is what decides whether anyone needs to act today. Ask for it
     ("Did you click the link in that message?", "Did you tell them your card
     number?") rather than leaving it out, and never resolve it by assuming
     the answer was no.
   - If clarifying answers are already present, strongly prefer writing the
     summary with what you have rather than asking again.
"""

# NOTE: model history driven by Google's shrinking free tiers —
#   2.0-flash: free tier retired (429 "limit: 0")
#   2.5-flash: free tier slashed to ~20 requests/day (Dec 2025)
#   3.5-flash: times out on this key (504) — not usable
#   3-flash-preview: responds, great quality, BUT latency spikes to 40-100s
#                    and it's a gated preview (may 404 on other accounts) — unusable
#   3.1-flash-lite: generally available (non-preview), aiming for fast + real
#                    free tier. Same GEMINI_API_KEY; no key change.
model = genai.GenerativeModel("gemini-3.1-flash-lite", system_instruction=SYSTEM_PROMPT)


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
