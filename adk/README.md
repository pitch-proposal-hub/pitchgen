# PitchGen Solution Accelerator

**PitchGen** is an enterprise multi-agent AI solution accelerator built on the **Google Agent Development Kit (ADK)**, **Gemini 3.x**, **Vertex AI Search**, and **Google Slides**. It automates the end-to-end creation, customization, visual restyling, and localization of executive-ready Google Slides presentations.

---

## Key Capabilities & 8 Core Workflows

1. **Full Deck Generation (`generate_pitch`)**:
   - **Phase 1 (Interactive Outline & Story Arc)**: Synthesizes a structured **Customer Value Initiative (CVI)** narrative outline grounded in live web research, industry value drivers, and your Vertex AI Search slide repositories.
   - **Phase 2 (Hybrid Slide Assembly & Bespoke Synthesis)**: Combines reusable slides from your organization's foundation decks, **0% immutable** verified Customer Case Studies (`Proof_Points`), and **Bespoke Context-v1 (`T1`–`T28`)** layouts with algebraic text-height validation and tripartite executive speaker notes.
2. **Semantic Slide Library Search (`search_slide`)**:
   - Searches across your organization's Sales Play and Customer Reference slide datastores in Vertex AI Search with live Google Slides thumbnail previews and 1-click slide insertion.
3. **Single Slide Synthesis (`generate_slide`)**:
   - Synthesizes a new bespoke slide mapped to your brand layout templates (`Context-v1`, `Google Cloud AI`, `Google Cloudstyle`).
4. **Slide Layout Reshuffle (`transform_slide`)**:
   - Vision-powered layout transformation that extracts content from an existing slide image and maps it cleanly into a new target slide layout.
5. **Account-Specific Text Customization (`transform_text`)**:
   - Customizes an entire presentation or selected slides in-place for a target customer while enforcing **Slide Job Customization Governance** (`0% IMMUTABLE` on customer case studies and cited analyst stats, `35-50%` on architecture diagrams, and `80-100%` on solution/value slides) plus automated **Gemini Omni 1.1 Flash** video-to-video customization of animated UI demo GIFs.
6. **In-Place Deck Translation (`translate`)**:
   - Translates an entire Google Slides presentation or selected slides into 20+ languages while preserving visual hierarchy, typography, and layout geometry.
7. **AI Visual & Diagram Generation (`generate_nanobanana`)**:
   - Generates boardroom-ready 3D isometric illustrations, editorial photography, and technical architecture visuals using `gemini-3.1-flash-image` / `gemini-3-pro-image`.
8. **AI Visual Restyling (`transform_nanobanana`)**:
   - Restyles or edits existing slide visuals in-place using multimodal image-to-image synthesis.

---

## Repository Structure

```text
pitchgen/
├── README.md                        # Solution Accelerator overview & quickstart
├── technical_documentation.md       # Architecture, configuration & deployment guide
├── adk/                             # Python ADK Multi-Agent Backend & A2UI Server
│   ├── pyproject.toml               # Dependencies & pytest configuration
│   ├── agents-cli-manifest.yaml     # ADK CLI manifest
│   ├── agents-enterprise-manifest.yaml
│   ├── src/
│   │   ├── agent.py                 # Primary ADK root_agent & 8 workflow tools
│   │   ├── enterprise_agent.py      # Enterprise ADK agent wrapper
│   │   ├── agent_runtime_app.py     # Vertex AI Agent Engine runtime entrypoint
│   │   ├── agents/                  # Specialized sub-agents, workflows & GTM skills
│   │   ├── ge/                      # A2UI v0.9 & Google Slides Canvas integration
│   │   ├── orchestrators/           # Creative & slide assembly orchestrators
│   │   ├── pitchgen_utils/          # Algebraic layout, logo, image/GIF & GCS utilities
│   │   ├── services/                # Deck generation, transformation & translation services
│   │   ├── config/                  # config.ini, mapping.json, sales_plays.json
│   │   ├── prompt_templates/        # LLM prompt templates & layout JSON schemas
│   │   └── templates_metadata/      # Slide template placeholder coordinate maps
│   └── tests/
│       └── unit/                    # Unit test suite & automated sanitization audit
└── pitchgen_UI/                     # Google Slides Add-on Frontend (Google Apps Script)
    ├── appsscript.json              # Add-on manifest & OAuth scopes
    ├── configuration.js             # Environment configuration (Project, Bucket, Endpoints)
    ├── Code.js                      # Slides Add-on lifecycle & menu handlers
    ├── geminiEnterprise.js          # Vertex AI Agent Engine & A2UI bridge
    ├── restAPI.js                   # Backend REST & GCS integration
    ├── sideBar.html                 # Add-on sidebar interface
    └── userInputPopup.html          # Deck generation intake modal
```

---

## Quickstart

### 1. Prerequisites
- **Python 3.11+** and [`uv`](https://docs.astral.sh/uv/) (or `pip`)
- A **Google Cloud Project** with the following APIs enabled:
  - Vertex AI API (`aiplatform.googleapis.com`)
  - Vertex AI Search / Discovery Engine API (`discoveryengine.googleapis.com`)
  - Cloud Storage API (`storage.googleapis.com`)
  - Secret Manager API (`secretmanager.googleapis.com`)
  - Google Slides API (`slides.googleapis.com`) & Google Drive API (`drive.googleapis.com`)
- [`clasp`](https://github.com/google/clasp) for deploying the Google Slides Add-on (`pitchgen_UI/`).

### 2. Configure Your Environment
1. Update [`adk/src/config/config.ini`](adk/src/config/config.ini) with your Google Cloud Project ID, GCS bucket names, Vertex AI Search datastore IDs, and deployed Google Apps Script Web App URL.
2. Update [`adk/src/config/mapping.json`](adk/src/config/mapping.json) and `adk/src/templates_metadata/*.txt` with the Google Slides Presentation IDs of your organization's master template decks.
3. Update [`pitchgen_UI/configuration.js`](pitchgen_UI/configuration.js) and [`pitchgen_UI/.clasp.json`](pitchgen_UI/.clasp.json) with your GCP project, Reasoning Engine ID, and Apps Script `scriptId`.

### 3. Run Unit Tests & Sanitization Audit
```bash
cd adk
pytest tests/unit
```

### 4. Run Locally or Deploy to Vertex AI Agent Engine
```bash
cd adk
# Interactive local playground
agents-cli playground

# Deploy to Vertex AI Agent Engine
agents-cli deploy
```

See [`technical_documentation.md`](technical_documentation.md) for detailed architecture diagrams, datastore schema specifications, and step-by-step deployment instructions.
