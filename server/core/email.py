# TODO: Resend client for POST /api/summaries/:id/send.
# Expected functions:
#   - send_summary_email(to_email, summary_text, from_name=None) -> None
#     Sends the summary as an email to a trusted contact. Uses onboarding@resend.dev
#     as the sender until a domain is verified.
# Reads RESEND_API_KEY from settings.

import resend
