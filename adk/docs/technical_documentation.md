# PitchGen-ADK2.0: Technical Architecture & Function Documentation

## 1. Architectural Overview
The **PitchGen-ADK2.0** project is a modular, agentic ecosystem designed to automate the creation of sales pitch decks. It follows a **Coordinator-Agent-Skill** hierarchy, ensuring scalability, clear separation of concerns, and seamless integration with the Google ADK (Agent Development Kit) framework for Web UI execution.

### Hierarchy
-   **Orchestrators**: High-level managers that coordinate the sequence of entire phases (Narrative vs. Creative).
-   **Agents**: Specialist entities responsible for specific sub-tasks (e.g., Retrieval, Slide Engineering, Visuals).
-   **Skills**: The atomic units of logic that perform API calls, GenAI synthesis, and data processing.
-   **ADK Integration (`agent.py`)**: Bridges the core orchestration logic to the ADK Web UI, exposing a rich set of tools for interactive slide generation, translation, and refinement.

---

## 2. State & Configuration Management

### `config_loader.py`
-   **`load_config(file_path)`**: Initializes the application environment by reading `config/config.ini`. It loads Vertex AI project IDs, Gemini model versions, and datastore aliases required for connectivity.

### `state.py`
-   **`GlobalState` Class**: The centralized "source of truth" passed between all components.
    -   `context`: Stores user inputs (customer name, industry, etc.) and session metadata.
    -   `outline/agendas`: Stores the structural blueprint of the presentation.
    -   `reusable_slides`: List of pre-existing slides fetched from company repositories, grouped by agenda.
    -   `generated_content`: New text synthesized by LLMs for content gaps.
    -   `final_deck_structure`: The finalized mapping of content to slide placeholders.

### Database Integration (`db/connection.py` & `db/db_controller.py`)
-   **`DBController`**: Manages connectivity and operations with a SQL database to log user inputs, request outlines, model responses, copy actions, translation/reshuffle features, ER numbers, and user feedback.

---

## 3. End-to-End Workflow (`main.py` / `agent.py`)

The application lifecycle is split into two primary phases, triggered either via CLI (`main.py`) or via ADK tools (`agent.py`):

### Phase 1: Narrative Orchestration
**Managed by: `NarrativeOrchestrator` (CLI) or `create_proposal_outline` tool (Web UI)**

#### 1.1 Agenda & Outline Generation (`AgendaAgent`)
-   **`OutlineWorkflow.execute()`**:
    *   Fetches the website datastore ID from config.
    *   Performs a web search via **Vertex AI Search (Discovery Engine)** to gather external context about the customer.
    *   Uses Gemini (`gemini-2.5-flash`) to synthesize a logical presentation outline.
-   **`AgendaWorkflow.execute()`**:
    *   Expands the high-level outline into detailed, slide-by-slide descriptions (Agendas) in a structured JSON format.
-   **DB Logging**: Logs the user input and the generated outline items to the database for tracking.

---

### Phase 2: Creative Orchestration
**Managed by: `CreativeOrchestrator` (CLI) or `slide_generator_skill` tool (Web UI)**

#### 2.1 Asset Discovery (`RetrievalAgent`)
-   **`SlideSearchWorkflow.execute()`**:
    *   Queries internal datastores (Discovery Engine) for existing slides matching the agenda titles.
-   **`SemanticScoringWorkflow.execute()`**:
    *   Converts agenda queries and retrieved slide descriptions into vectors using `text-embedding-004`.
    *   Calculates **Cosine Similarity** to filter and rank the most relevant assets.
-   **Dynamic Slide Clusters**:
    *   Filters slide suggestions with a similarity score >= 0.7 as "anchors".
    *   Dynamically retrieves "sibling" slides belonging to the same `deckId` as the anchors to maintain visual and contextual consistency.
    *   **Fallback**: Fetches at least 3 slide suggestions from the database if search results are limited.

#### 2.2 Content Engineering & Customization (`SlideEngineeringAgent`)
-   **Semantic Coverage Check & Gap-Based Generation (`ContentSynthesisWorkflow.execute()`)**:
    *   Checks semantic coverage of each agenda sub-point against the retrieved reusable slides using cosine similarity (threshold: 0.7).
    *   **Gap-Based Generation**: Generates net-new slide content using Gemini (`gemini-2.5-flash`) *only* as a last resort for sub-points that are NOT covered by reusable slides.
-   **Dynamic Reusable Slide Customizer (`ReusableSlideCustomizerWorkflow.execute()`)**:
    *   Dynamically tailors the retrieved reusable slides based on the specific customer context and active GTM skills to ensure personalization.
-   **Template Mapping (`TemplateMapperWorkflow.execute()`)**:
    *   Maps synthesized text into specific Google Slides layout placeholders (e.g., "Title", "Body") using prompt templates. Includes visual deduplication to prevent repeating layouts.

#### 2.3 Visual Assets (`VisualAgent`)
-   **`VisualSynthesisWorkflow.execute()`**:
    *   If `visuals_requested` is true, generates professional business imagery using **Google Imagen** on Vertex AI.
-   **DB Logging**: Logs total slide counts, copy drive actions for reusable slides, and the final model response.

---

## 4. Advanced Features & Payload Services

To support the ADK Web UI and event-driven integration, the ecosystem provides direct payload processing services (both via GCS files and in-memory JSON).

### 4.1 Direct Payload Processing (`SlideEngineeringAgent.run_payload`)
Exposes interfaces for real-time slide manipulation:
-   **Layout Reshuffling**: Transforms slide layout using `LayoutTransformerWorkflow` and `SlideAssemblyWorkflow` when requested (e.g., to change a slide's visual style).
-   **Text Polishing/Transformation**: Enhances text clarity and tone based on output criteria using `TextTransformerWorkflow`.
-   **In-Memory Translation**: Translates full presentation structures into target languages (e.g., German) using `TranslationEngineWorkflow`.

### 4.2 Translation Services (`TranslationWorkflow`)
-   Processes GCS-based packages to translate full presentation slides asynchronously, logging the action to the database.

### 4.3 Reshuffle Services (`ReshuffleWorkflow`)
-   Processes GCS-based packages to reshuffle slide layouts and revise content, logging the action to the database.

### 4.4 Sales Play Processing (`SalesPlayWorkflow`)
-   Automates the customized copy generation and research grounding for specific **Sales Plays**, linking them to GCS templates.

### 4.5 Sidebar Integration (`SidebarAgent`)
The sidebar features are implemented by the class `SidebarAgent` inheriting from `BaseAgent` and exposed as standard ADK tools:
-   **`sidebar_search`**: Searches for reusable slides with optional strict tag-based filtering. It runs the `SidebarSlideSearchWorkflow`.
-   **`sidebar_generate`**: Generates a net-new slide from text instructions or extracts structured context from a slide screenshot (supporting GCS URI or Base64 inputs) using the `SidebarAddSlidesWorkflow` and `SidebarNewContentGenWorkflow`.

---

## 5. Key Technologies
-   **Orchestration**: Custom Python class-based graph logic & **Google ADK** for Web Agent deployment.
-   **LLMs**: Google Gemini 2.5 Flash & Gemini 3.5 Flash (for Web Agent).
-   **Embeddings**: Vertex AI `text-embedding-004`.
-   **Search**: Vertex AI Search & Conversation (Discovery Engine).
-   **Security**: Google Cloud Secret Manager.
-   **Database**: SQL Database via centralized `DBController`.
-   **State**: Persistent `GlobalState` JSON serialization.

---

## 6. Challenges & Resolutions (Migration Fixes)

During the migration from the legacy `PitchGen-model` to the ADK 2.0 version, several critical issues were resolved:

| Challenge | Resolution |
| :--- | :--- |
| **Project Identity** | Updated `config.ini` to point to the active project `pitch-genie` and configured gcloud quota project for Discovery Engine API. |
| **Secret Manager Permissions** | Encountered 403 errors when accessing Secret Manager. Resolved by bypassing the secret lookup for datastore IDs and placing the actual IDs directly into the `config.ini` as a reliable source of truth. |
| **Datastore Discovery** | Performed manual discovery of Discovery Engine datastores using Python scripts to map legacy aliases (like `text_website_datastore`) to actual active IDs (like `web-search-001_1712062033444`). |
| **ADK Patterns** | Refactored the `RetrievalAgent` to iterate through all configured reusable datastores instead of using hardcoded placeholders, ensuring comprehensive asset discovery. |
| **JSON Serialization** | Fixed a `TypeError` where Discovery Engine's `RepeatedComposite` objects could not be serialized. Updated `SlideSearchSkill` to use `google.protobuf.json_format` for proper dictionary conversion. |
| **Interaction Model** | Enhanced `main.py` with a robust CLI that handles both interactive terminal `input()` and non-interactive automated execution via `sys.stdin.isatty()` checks. |

---
*Documented on: Monday, June 1, 2026*
