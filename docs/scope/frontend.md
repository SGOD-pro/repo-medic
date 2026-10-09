# Frontend (Package A)

## Slice A: Frontend implementation

### 1. Task screens · needs a decision
Initial UI for task selection, using the mock HTTP transport.
**Done when:** A user can select a curated task and start it via the mock API.
- [ ] Design it (spec): `/architect task screens`

### 2. Run progress and results · needs a decision
UI to show the repair stages, candidates, and final downloaded patch/evidence.
**Done when:** The UI correctly renders progress stages and results from the mock API.
- [ ] Design it (spec): `/architect run progress and results`

### 3. History and reload · needs a decision
View past runs and reload run state.
**Done when:** A user can view history and reload an ongoing run.
- [ ] Design it (spec): `/architect history and reload`

### 4. Cancel, reconnect, and errors · needs a decision
Handle connection loss, explicit cancellation, and backend errors safely.
**Done when:** Reconnecting resumes SSE, cancellation stops the run, and errors are readable.
- [ ] Design it (spec): `/architect cancel reconnect errors`
