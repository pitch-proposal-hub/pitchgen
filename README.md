# PitchGen External

This repository contains the full end-to-end PitchGen solution, composed of the **PitchGen Multi-Agent Python Backend** built on Google ADK 2.0 and the **PitchGen Apps Script Web UI** for Google Slides integration.

## Repository Overview

```
pitchgen_external/
├── README.md                            # Project overview & quickstart guide
├── technical_documentation.md           # Technical architecture & function documentation
│
├── pitchgen_UI/                         # Google Apps Script & Web UI Frontend
│   ├── .clasp.json                      # clasp configuration file
│   ├── appsscript.json                  # Apps Script manifest and OAuth scopes
│   ├── configuration.js                 # Environment URLs, bucket names & project IDs
│   ├── Code.js                          # Main Apps Script server-side functions
│   ├── restAPI.js                       # External REST API endpoints & email dispatch
│   ├── contentGen.js                    # Content generation handler
│   ├── copySlide.js                     # Slide cloning utility
│   ├── feedbackForm.js                  # User feedback handler
│   ├── translation.js                   # Language translation handler
│   ├── pickerDialog.html                # Google Drive Picker dialog
│   ├── sideBar.html                     # Main Google Slides sidebar UI
│   └── userInputPopup.html              # Customization modal dialog UI
│
└── pitchgen_adk/                        # PitchGen Multi-Agent (ADK 2.0 Python Backend)
    ├── BUILD                            # Blaze build rules for libraries & test binaries
    ├── main.py                          # Root ADK 2.0 Web Agent definition (API Router)
    ├── run_adk.py                       # ADK runner script
    ├── function_map.md                  # Interface maps between front-end & back-end
    ├── agents-cli-manifest.yaml         # ADK CLI deployment manifest
    ├── pyproject.toml / requirements.txt# Python dependencies & environment configs
    │
    ├── src/                             # Core Agent Source Code
    │   ├── agent.py                     # Primary ADK agent router & tool functions
    │   ├── config_loader.py             # Configuration & Secret Manager loader
    │   ├── enterprise_agent.py          # Enterprise agent logic
    │   ├── agents/                      # Specialist Agents (Retrieval, Slide Engineering, Visuals, etc.)
    │   ├── workflows/                   # Procedural Workflows (Synthesis, Layout, Reshuffle, Translation)
    │   └── orchestrators/               # Multi-Agent Coordination Logic (Creative & Narrative)
    │
    ├── pitchgen_automation/             # Automation skills & standalone scripts
    └── tests/                           # Unit and Integration Test Suite
```

## Setup & Execution

### 1. PitchGen ADK Python Backend (`pitchgen_adk/`)

#### Prerequisites & Installation

Navigate into the `pitchgen_adk` folder:
```bash
cd pitchgen_adk
```

Install dependencies using `uv` or `pip`:
```bash
uv sync
```
or
```bash
pip install -r requirements.txt
```

Configure environment variables:
```bash
export GOOGLE_CLOUD_PROJECT="<YOUR_GCP_PROJECT_ID>"
export GCP_LOCATION="us-central1"
```

#### Run Unit & Integration Tests

Execute unit tests:
```bash
uv run pytest tests/
```

#### Run E2E Integration Runners

```bash
# E2E Orchestrator Workflow pipeline:
uv run python tests/test_agent_workflow.py

# E2E Sidebar search integration test:
uv run python tests/test_sidebar_integration.py
```

---

### 2. PitchGen Web UI (`pitchgen_UI/`)

The Google Apps Script frontend files located in `pitchgen_UI/` are deployed using [`clasp`](https://github.com/google/clasp).

1. Configure script ID in `pitchgen_UI/.clasp.json`:
   ```json
   {
     "scriptId": "YOUR_SCRIPT_ID"
   }
   ```
2. Configure environment endpoints in `pitchgen_UI/configuration.js`.
3. Push files to Apps Script:
   ```bash
   cd pitchgen_UI
   clasp push
   ```

