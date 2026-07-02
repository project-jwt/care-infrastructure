// TODO: adapters for spec §Summaries (primary only).
// Functions to export:
//   - draftSummary({ transcript, answers })   -> POST /api/summaries/draft
//   - saveSummary({ transcript, summaryText })-> POST /api/summaries
//   - listSummaries()                         -> GET  /api/summaries
//   - getSummary(id)                          -> GET  /api/summaries/:id
//   - updateSummary(id, summaryText)          -> PATCH /api/summaries/:id
//   - deleteSummary(id)                       -> DELETE /api/summaries/:id
//   - sendSummary(id, contactIds)             -> POST /api/summaries/:id/send
