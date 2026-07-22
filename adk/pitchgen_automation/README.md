# PitchGen-Automation (ADK 2.0)

This project provides an automated, multi-agent system for generating pitch deck
outlines using Google ADK 2.0 and Gemini 2.5 Flash Lite.

## 1. Setup Instructions

### Prerequisites

*   **Python 3.10+**
*   **Enterprise Cloud Project**: Ensure Vertex AI API is enabled.
*   **ADK 2.0 CLI**: Installed via `pip install google-adk`.

### Installation

1.  Clone this repository or extract the zip file.
2.  Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

## 2. Authentication

Ensure you are authenticated with Enterprise Cloud and have the correct project set:

```bash
gcloud auth application-default login
gcloud config set project [YOUR_PROJECT_ID]
```

*Note: The current configuration is hardcoded to use `<YOUR_GCP_PROJECT_ID>` in
`src/skills.py`. If you are using a different project, update the
`vertexai.init` call.*

## 3. Running the Agent

### Command Line Interface (CLI)

Interact with the agent directly in your terminal:

```bash
adk run . "Generate a pitch deck outline for [CUSTOMER] interested in [SOLUTION]."
```

### Web User Interface (Web UI)

Launch the graphical interface (especially useful for visual debugging):

```bash
# For local machine:
adk web --port 8080 .

# For Cloud Shell:
adk web --allow_origins "regex:https://.*\.cloudshell\.dev" --port 8080 .
```

## 4. Architecture

*   **`agent.py`**: Defines the multi-agent graph (Orchestrator and Specialist
    Agents).
*   **`src/skills.py`**: Contains the business logic and LLM tool calling.
*   **`prompt_templates/`**: Centralized templates for entity extraction and
    outline generation.
*   **`config/`**: JSON mappings for industries and solutions.
