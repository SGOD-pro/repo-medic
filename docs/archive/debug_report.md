## /debug complete · K0 foundation repaired and verified

**Root cause: the project scope moved to a new folder leaving broken links behind, the test scripts lacked strict failure modes, the environment file was missing from ignore rules, and the package manager configuration prevented simple execution. Fixed by updating the phase document links to the new scope files, appending team ownership rules to the agents guide, making the makefile and test scripts fail on errors while switching to the uv package manager, adding the environment file to the root ignore list, and removing the build system block from the backend configuration so scripts run cleanly.**

Next: /test   (add real unit tests since the current test commands run zero tests and pass)
Heads up: the backend tests folder does not exist yet and the frontend test script is a placeholder that exits cleanly. You may want to add initial tests before building features.
