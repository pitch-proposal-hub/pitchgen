# PitchGen External Solution Accelerator

PitchGen is an AI-powered solution accelerator designed to automate, streamline, and customize slides presentation pipelines. By leveraging Generative AI (Gemini models), **Google Agent Development Kit (ADK)**, and semantic RAG slide search indexes, PitchGen dynamically drafts professional outlines, structures tailored agendas, and retrieves reusable slide templates matching the target business context.

This repository is a decoupled, sanitized version of the PitchGen project, prepared for **external deployment** inside standard GCP cloud environments or local setups.

---

## 1. Repository Structure

```
PitchGen-external/
├── README.md                  <-- This Setup Guide
├── PitchGen-UI/               <-- Google Apps Script Sidebar client files
│   ├── Code.gs
│   ├── userInputPopup.html
│   └── ...
├── PitchGen-backend/          <-- Python Flask API Gateway
│   ├── main.py
│   ├── config.py
│   ├── connection.py
│   └── .env.template
└── PitchGen-model/            <-- Python FastAPI ADK Agent Service
    ├── main.py
    ├── adk_agent.py
    └── config/
        └── config.ini.template
```

---

## 2. Setup and Deployment Guide

### Step 2.1: Provision the Database (MySQL)
PitchGen uses a MySQL database to persist session parameters, outlines, feature metrics, and feedback logs. 

Connect to your MySQL server and execute the following DDL statements to bootstrap the tables:

```sql
-- 1. Users Table
CREATE TABLE IF NOT EXISTS user_details (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    user_ldap VARCHAR(100) UNIQUE NOT NULL
);

-- 2. Presentation Requests Table
CREATE TABLE IF NOT EXISTS users_input (
    user_request_id INT AUTO_INCREMENT PRIMARY KEY,
    requested_by VARCHAR(300),
    request_type VARCHAR(300),
    presentation_id VARCHAR(300),
    audience VARCHAR(5000),
    industry VARCHAR(5000),
    solution VARCHAR(5000),
    customer_name VARCHAR(5000),
    region VARCHAR(100),
    product VARCHAR(300),
    er_number VARCHAR(100), -- Acts as standard Opportunity ID
    user_id INT,
    business_context VARCHAR(5000),
    user_input_id VARCHAR(300) NOT NULL,
    model_generated_outlines_url VARCHAR(5000),
    sales_play VARCHAR(300),
    content_gen_slides INT,
    reusable_slides INT,
    total_slides INT,
    FOREIGN KEY (user_id) REFERENCES user_details(user_id)
);

-- 3. Generated Outlines Table
CREATE TABLE IF NOT EXISTS user_outline (
    id INT AUTO_INCREMENT PRIMARY KEY,
    request_id INT,
    outline TEXT,
    sequence INT,
    FOREIGN KEY (request_id) REFERENCES users_input(user_request_id)
);

-- 4. Slide Assets Path Logs
CREATE TABLE IF NOT EXISTS model_response (
    response_id INT AUTO_INCREMENT PRIMARY KEY,
    request_id INT,
    deck_drive_url VARCHAR(5000),
    generated_content_url VARCHAR(5000),
    architectural_url VARCHAR(5000),
    FOREIGN KEY (request_id) REFERENCES users_input(user_request_id)
);

-- 5. Presentation Copy Queue Table
CREATE TABLE IF NOT EXISTS copy_drive (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_ldap VARCHAR(300),
    status VARCHAR(300),
    user_input_id VARCHAR(300),
    filename VARCHAR(300),
    deckId VARCHAR(300),
    folder VARCHAR(300),
    created_date DATETIME
);

-- 6. Feature Logging Table
CREATE TABLE IF NOT EXISTS feature_usage_log (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    presentation_id VARCHAR(300),
    er_number VARCHAR(100),
    requested_by VARCHAR(100),
    request_type VARCHAR(300),
    user_id INT,
    action VARCHAR(300),
    payload JSON,
    FOREIGN KEY (user_id) REFERENCES user_details(user_id)
);
```

### Step 2.2: Configure and Run the Backend (`PitchGen-backend`)
1.  Navigate to the backend directory:
    ```bash
    cd PitchGen-backend
    ```
2.  Create your environment file from the template:
    ```bash
    cp .env.template .env
    ```
3.  Fill in the `.env` parameters (database connection URI `DATABASE_URL`, your target Google Cloud Project IDs, GCS Storage Buckets, and Model Endpoint URL).
4.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
5.  Start the server:
    ```bash
    python3 main.py
    ```

### Step 2.3: Configure and Run the Model Service (`PitchGen-model`)
1.  Navigate to the model directory:
    ```bash
    cd PitchGen-model
    ```
2.  Create your configuration file from the template:
    ```bash
    cp config/config.ini.template config/config.ini
    ```
3.  Provide your specific GCP Project parameters, regional location, and targeted Gemini model versions (e.g., `gemini-2.5-pro`).
4.  **Slide Search RAG Setup**: 
    Ensure you index your reusable slide assets in a BigQuery table matching the structure below, and export the table environment variables:
    *   `export BQ_PROJECT_ID="your-gcp-project-id"`
    *   `export BQ_DATASET_TABLE="your_dataset.your_slide_indexing_table"`
    
    The BigQuery index table must contain these columns:
    *   `presentation_id` (STRING)
    *   `slide_id` (STRING)
    *   `text_content` (STRING)
    *   `gcs_asset_url` (STRING)
5.  Install dependencies (which includes the open-source `google-adk` package):
    ```bash
    pip install -r requirements.txt
    ```
6.  Run the service:
    ```bash
    gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app -b 0.0.0.0:8000
    ```

### Step 2.4: Deploy Google Apps Script client (`PitchGen-UI`)
1.  Open Google Slides and create a blank presentation.
2.  Navigate to **Extensions > Apps Script**.
3.  Copy all `.gs` and `.html` files from the `PitchGen-UI` directory into the Apps Script editor.
4.  Configure the REST API target address in `configuration.gs` or `restAPI.gs` to point to your running Flask `PitchGen-backend` endpoint URL.
5.  Click **Run** to authenticate the scripts and link the custom sidebar UI directly into your slides!

### Step 2.5: Generalizing LLM Prompt Templates
All dynamic RAG extraction and outline structuring scripts in `PitchGen-model/prompt_templates/` are fully parameterized with generic token placeholders:
*   The system instructions refer generically to the target target **`[Cloud Provider]`** rather than hardcoding GCP or Google.
*   **Important**: The valid values catalogs for `solutions` and `products` inside `prompt_templates/searchEntities.txt` and `prompt_templates/contextEntities.txt` contain placeholders for Google Cloud's product portfolios. To tailor this tool for another target organization (e.g. AWS, Azure, or SaaS suites), simply overwrite these arrays inside the raw text prompt files with your own target product lists to allow precise AI metadata extraction.

### Step 2.6: Map Your Presentation Layout Decks
PitchGen generates presentation slides by cloning pre-styled layouts from master presentation decks. These templates mapping coordinates are defined inside `PitchGen-model/config/mapping.json`.
1. Create your own styled master templates in Google Slides (for Titles, Agendas, Section Dividers, and Thank-you slides).
2. Overwrite the `"deckId"` values inside `mapping.json` with your own Google Slides presentation IDs (replacing placeholders like `your-title-master-presentation-deck-id`).
3. Ensure you define the correct layout slide ID mappings (e.g. `"1": "your_slide_id_here"`) to tell the backend which slide index to copy for each design category.

