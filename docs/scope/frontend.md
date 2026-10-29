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

### 5. Safe product slice · done
Home navigation, custom repository validation with disabled execution gate, truthful presentation, and supported demo policy.
spec: ../specs/0009-first-safe-product-slice.md
**Done when:** Users can navigate saved demo runs, configure and validate custom repositories with disabled execution gate, inspect truthful terminal run results, and choose supported demo tasks without acceptance fixtures.
- [x] Home page with links to saved demo and custom configuration flow
- [x] Custom repository form collecting URL, commit SHA, dependency, versions, pytest args, paths, failure string
- [x] Shared contract validation and server side disabled execution gate
- [x] Truthful terminal run presentation without fabricated claims
- [x] Supported demo policy hiding acceptance and example tasks
- [x] Local tests and Playwright browser coverage

