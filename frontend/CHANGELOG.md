# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Task recipe validation ensuring test commands are present and source paths remain within the workspace (see spec 0001).
- Baseline stage runner executing the test command twice in an isolated sandbox to verify clean passes and collection stability (see spec 0001).
- Deterministic in memory sandbox and model fake adapters with configurable presets for offline testing (see spec 0001).
- Early and mid execution cancellation support across baseline checks via host ports (see spec 0001).
