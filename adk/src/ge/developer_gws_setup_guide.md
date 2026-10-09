# Developer Guide: Setting up Google Workspace (GWS) Export for Gemini Enterprise Agents

> This guide outlines the step-by-step instructions to set up the browser-based,
> self-service Google Docs export integration from scratch in a new Google Cloud
> project.

--------------------------------------------------------------------------------

## Why this architecture?

Vertex AI Reasoning Engine service accounts are blocked by security policies
from writing directly to the `google.com` corporate Workspace domain (returning
a `403 Forbidden` error).

To bypass this, we use a **Browser-Based OAuth 2.0 Exporter**. When a user
clicks "Export" in the Chat UI, they run a secure 1-click Google login in their
browser. The web app uses *their* authorized user identity (which is internal
and has full write access) to create and compile the Google Doc, and redirects
them straight to the document.

--------------------------------------------------------------------------------

## Step 1: Enable Workspace APIs

You must enable the Google Drive and Google Docs APIs in your Google Cloud
project:

1.  Go to the
    [Google Cloud Console API Library](https://console.cloud.google.com/apis/library).
2.  Search for and enable:
    *   **Google Docs API**
    *   **Google Drive API**

--------------------------------------------------------------------------------

## Step 2: Configure the OAuth Consent Screen

Before creating client credentials, you must configure how the Google login
screen looks:

1.  Go to the
    [OAuth Consent Screen Console](https://console.cloud.google.com/apis/auth/consent).
2.  Select **Internal** (this restricts access to `@example.com` users only) and
    click **Create**.
3.  Fill in the required fields:
    *   **App name:** `PitchHub Exporter`
    *   **User support email:** Your `@example.com` email
    *   **Developer contact information:** Your `@example.com` email
4.  Click **Save and Continue** (no special scopes are required here, as we
    request them dynamically in the code).

--------------------------------------------------------------------------------

## Step 3: Create OAuth 2.0 Credentials

To get your Client ID and Client Secret:

1.  Go to the
    [GCP Credentials Console](https://console.cloud.google.com/apis/credentials).
2.  Click **`+ Create Credentials`** at the top and select **`OAuth client
    ID`**.
3.  Set **Application type** to **`Web application`**.
4.  Set the **Name** (e.g., `PitchHub Exporter`).
5.  Under **Authorized redirect URIs**, click **`+ ADD URI`** and add:
    *   **For local development:** `http://localhost:8080/oauth2callback`
    *   **For production (Cloud Run):**
        `https://<your-cloud-run-service-url>/oauth2callback`
6.  Click **`Create`**.
7.  In the popup, copy:
    *   **Client ID**
    *   **Client Secret** (Treat this securely like a password!)

--------------------------------------------------------------------------------

## Step 4: Run or Deploy the Web Exporter

The web exporter is a lightweight, dependency-free Python server
([web_exporter.py](file:///google/src/cloud/danteguevara/CloudtopDante/enterprise_workspace/experimental/users/danteguevara/proposal_agent/web_exporter.py))
that handles the OAuth flow, downloads drafts from GCS, and writes to Google
Docs.

### Option A: Running Locally (For Development)

Run the server using your Python environment:

```bash
export GOOGLE_CLIENT_ID="your_copied_client_id"
export GOOGLE_CLIENT_SECRET="your_copied_client_secret"

python3 web_exporter.py
```

*The server will start listening on `http://localhost:8080`.*

### Option B: Deploying to Cloud Run (For Production)

Deploy it as a serverless container to Cloud Run:

```bash
gcloud run deploy pitchhub-exporter \
  --source . \
  --env-vars GOOGLE_CLIENT_ID="your_client_id",GOOGLE_CLIENT_SECRET="your_client_secret" \
  --allow-unauthenticated \
  --region us-central1
```

--------------------------------------------------------------------------------

## Step 5: Configure the Reasoning Engine

When deploying your Vertex AI Reasoning Engine (using `deploy.py`), ensure you
set the `PITCHHUB_EXPORTER_URL` environment variable to point to your exporter:

*   **If testing locally:** `export
    PITCHHUB_EXPORTER_URL="http://localhost:8080"`
*   **If in production:** `export
    PITCHHUB_EXPORTER_URL="https://<your-cloud-run-service-url>"`

This tells the Orchestrator where to redirect the user when they click the
"Export" link in the Chat UI.
