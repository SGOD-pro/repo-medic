# Frontend (Package A)

## Slice A: Frontend implementation

### 1. Task screens · done
Task selection UI using curated tasks and search modes.
**Done when:** A user can select a curated task and start it via the API.
- [x] Curated task selector with branch refine and sequential options
- [x] Validated against schema fixtures and offline smoke tests

### 2. Run progress and results · done
UI displaying repair stages, candidate execution matrix, and downloaded patch or evidence.
**Done when:** The UI correctly renders progress stages and results from the API.
- [x] Unified change manifest and live pipeline status
- [x] Addressable download by artifact id
- [x] Truthful offline, mock, replay, and live labeling

### 3. History and reload · done
View past runs and reload run state.
**Done when:** A user can view history and reload an ongoing run.
- [x] Zustand run history drawer with persistence
- [x] Smart routing on URL search parameters and selected history items
- [x] Active run recovery without unconditional success overrides

### 4. Cancel, reconnect, and errors · done
Handle connection loss, explicit cancellation, and backend errors safely.
**Done when:** Reconnecting resumes SSE, cancellation stops the run, and errors are readable.
- [x] StreamManager with exponential backoff and Last Event ID resumption
- [x] Sequence deduplication and RunSummary recovery on terminal events
- [x] User initiated cancellation handling
