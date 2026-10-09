flowchart TD
    F["K0 · You + C<br/>Freeze contracts, config and fixtures<br/>Pass checks → foundation-ready"]

    F --> A["A · Frontend<br/>Build against mock API"]
    F --> B["B · Backend + D1<br/>Build with FakeEngine and local D1"]
    F --> C["C · Repair engine<br/>Build with FakeHost and fake providers"]
    F --> D["D · Optional evaluation<br/>Build offline tooling"]

    A --> AG["A handoff<br/>UI checks pass → submit PR"]
    B --> BG["B handoff<br/>API + local D1 checks pass → submit PR"]
    C --> CG["C handoff<br/>Engine + verifier checks pass → submit PR"]

    AG --> I["K2 · Lead + A/B/C<br/>Merge and connect components<br/>Full offline E2E checks"]
    BG --> I
    CG --> I

    I --> DB["K3 · You + B<br/>Connect remote Cloudflare D1<br/>Verify persistence and concurrency"]
    DB --> L["K4 · You + C<br/>Enable capped real provider calls<br/>Verify live E2E repair"]

    D --> E["K5 · D or lead<br/>Real evaluation, deployment and video"]
    L --> E
    E --> DONE["Complete connected application"]

    I -. "Failure: owner fixes + adds regression" .-> I
    DB -. "Failure: B fixes + reruns checks" .-> DB
    L -. "Failure: offline regression first<br/>then operator-controlled live recheck" .-> L