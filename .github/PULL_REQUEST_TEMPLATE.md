> Base branch check: feature PRs target `pre-prod`. Only promotion PRs (pre-prod → main) target `main`.

## Ticket
Closes #<!-- board ticket number -->

## What changed
<!-- 2-3 sentences: what and why -->

## How to test
<!-- exact steps a reviewer runs: endpoints to curl, screens to click -->

## Screenshots
<!-- required for UI changes; delete section otherwise -->

## Checklist
- [ ] Branch named `your-name/feature-name`, based on fresh `pre-prod`
- [ ] Runs locally (server boots, flow works end-to-end)
- [ ] Matches the spec (API contract shapes / wireframe) where applicable
- [ ] All acceptance criteria on the ticket pass
- [ ] No secrets, `.env` files, or leftover debug prints
- [ ] Ticket moved to **In Review** on the board
