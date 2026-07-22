# PitchGen: Technical Architecture & Function Documentation

## 1. Architectural Overview

The **PitchGen** solution is structured into a two-tier architecture comprising the **Google Apps Script Frontend (`pitchgen_UI/`)** and the **Multi-Agent Python Backend (`pitchgen_adk/`)** built on the **Google ADK (Agent Development Kit)** framework.

```
+-----------------------------------------------------------------------+
|                          PitchGen Solution                            |
+-----------------------------------------------------------------------+
|  Frontend UI (pitchgen_UI/)         |  Multi-Agent Backend (pitchgen_adk/) |
|  - Google Slides Add-on             |  - ADK 2.0 Web Agent (src/agent.py)  |
|  - Sidebar & Modal Dialogs          |  - Narrative & Creative Orchestrators|
|  - Clasp & Apps Script Services     |  - Vertex AI Search & Gemini Models  |
+-----------------------------------------------------------------------+
```

### Hierarchy & Component Roles
- **Frontend UI (`pitchgen_UI/`)**: Implements Google Slides sidebar controls, customization popup dialogs, and Google Drive picker integration. Transmits requests to backend Cloud Run / App Engine endpoints via REST APIs (`restAPI.js`, `Code.js`).
- **Backend Agent Ecosystem (`pitchgen_adk/`)**:
  - **Orchestrators**: High-level managers that coordinate entire generation phases (`NarrativeOrchestrator` vs. `CreativeOrchestrator`).
  - **Agents**: Specialist entities responsible for distinct tasks (`RetrievalAgent`, `SlideEngineeringAgent`, `VisualAgent`, `SidebarAgent`).
  - **Workflows**: Procedural logic classes that perform API calls, GenAI synthesis, semantic retrieval, translation, and layout transformation.
  - **ADK Integration (`src/agent.py`)**: Exposes agent tools to the Web UI for interactive slide generation, search, translation, and refinement.

---

## 2. State & Configuration Management

### Backend Configuration (`pitchgen_adk/src/config_loader.py`)
- **`load_config(file_path)`**: Reads `src/config/config.ini` to initialize Vertex AI project settings, Gemini model versions, and datastore aliases required for search and retrieval. Resolves secrets securely via Secret Manager with fallback handling.

### State Tracking (`pitchgen_adk/src/state.py`)
- **`GlobalState` Class**: Pass-through data structure maintaining conversation context across agents:
    - `context`: Stores customer metadata, target industry, and user requirements.
    - `outline/agendas`: Contains presentation structure blueprints.
    - `reusable_slides`: List of pre-existing slides retrieved from repositories.
    - `generated_content`: Synthesized text for missing content gaps.
    - `final_deck_structure`: Mappings of content to slide placeholders.

### Database Integration (`pitchgen_adk/src/db/connection.py` & `pitchgen_adk/src/db/db_controller.py`)
- **`DBController`**: Handles SQL operations for logging user inputs, request outlines, model outputs, slide copy actions, translation/reshuffle events, and feedback entries.

---

## 3. End-to-End Workflow

Execution flows from user actions in `pitchgen_UI/` to backend agent orchestrators in `pitchgen_adk/`:

```
[pitchgen_UI Modal/Sidebar] ---> REST API Call ---> [pitchgen_adk/src/agent.py]
                                                          │
                                         ┌────────────────┴────────────────┐
                                         ▼                                 ▼
                             Phase 1: Narrative               Phase 2: Creative
                            (NarrativeOrchestrator)          (CreativeOrchestrator)
```

### Phase 1: Narrative Orchestration
**Managed by: `NarrativeOrchestrator` (`main.py`) or `create_proposal_outline` tool (`src/agent.py`)**

#### 1.1 Agenda & Outline Generation (`AgendaAgent`)
- **`OutlineWorkflow.execute()`**:
    * Fetches customer context and queries **Vertex AI Search (Discovery Engine)** for web intelligence.
    * Synthesizes a structured presentation outline using Gemini (`gemini-2.5-flash`).
- **`AgendaWorkflow.execute()`**:
    * Expands the high-level outline into detailed slide-by-slide agendas.
- **DB Logging**: Saves user context and outline structures to the tracking database.

---

### Phase 2: Creative Orchestration
**Managed by: `CreativeOrchestrator` (`main.py`) or `slide_generator_skill` tool (`src/agent.py`)**

#### 2.1 Asset Discovery (`RetrievalAgent`)
- **`SlideSearchWorkflow.execute()`**:
    * Queries internal datastores for matching reusable slides.
- **`SemanticScoringWorkflow.execute()`**:
    * Computes vector embeddings using `text-embedding-004` and applies cosine similarity scoring (threshold >= 0.7).
- **Dynamic Slide Clusters**:
    * Groups anchor slides and retrieves sibling slides from the same deck to preserve design consistency.

#### 2.2 Content Engineering & Customization (`SlideEngineeringAgent`)
- **Gap-Based Synthesis (`ContentSynthesisWorkflow.execute()`)**:
    * Evaluates coverage of agenda sub-points against retrieved assets.
    * Generates net-new content via Gemini *only* for sub-points lacking reusable slide coverage.
- **Customization (`ReusableSlideCustomizerWorkflow.execute()`)**:
    * Personalizes retrieved slide text for target accounts.
- **Template Mapping (`TemplateMapperWorkflow.execute()`)**:
    * Maps text into Google Slides placeholder slots with visual layout deduplication.

#### 2.3 Visual Assets (`VisualAgent`)
- **`VisualSynthesisWorkflow.execute()`**:
    * Generates contextual business images using **Google Imagen** on Vertex AI when visual assets are requested.

---

## 4. Advanced Features & Payload Services

Exposed via `pitchgen_adk/src/agent.py` and connected to `pitchgen_UI/restAPI.js`:

- **Layout Reshuffling**: Transforms slide layout coordinates using `LayoutTransformerWorkflow`.
- **Text Polishing**: Refines slide text length and tone via `TextTransformerWorkflow`.
- **In-Memory & Package Translation**: Translates presentation decks using `TranslationEngineWorkflow` / `TranslationWorkflow`.
- **Sales Play Processing**: Automates personalized Sales Play slide content and GCS template mapping.
- **Sidebar Search & Generation**: Handles live slide search (`sidebar_search`) and multimodal screenshot-to-slide generation (`sidebar_generate`).

---

## 5. Key Technologies
- **Frontend**: Google Apps Script (V8 Runtime), HTML5, JavaScript, Bootstrap, Clasp.
- **Backend Orchestration**: Google ADK (Agent Development Kit 2.0), Python 3.11+.
- **Generative AI Models**: Google Gemini 2.5 Flash, Gemini 3.5 Flash, Google Imagen.
- **Embeddings & Search**: Vertex AI `text-embedding-004`, Vertex AI Search (Discovery Engine).
- **Security & Storage**: Google Secret Manager, Google Cloud Storage.

---
*Documented: July 2026*
