# TODO: Pydantic models for §Summaries.
# Expected:
#   - DraftIn         ( transcript, answers=[] )
#   - DraftOut        ( needsClarification, questions?, summaryText? )
#   - SummaryCreate   ( transcript?, summaryText )
#   - SummaryOut      ( id, transcript?, summaryText, createdAt, updatedAt )
#   - SummaryUpdate   ( summaryText )
#   - SendIn          ( contactIds: list[int] )
#   - SendOut         ( summaryId, sentTo: [ { contactId, sentAt } ] )

from pydantic import BaseModel
