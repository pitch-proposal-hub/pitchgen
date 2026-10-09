# 📖 Integration Guide: A2UI Agent in Gemini Enterprise

This guide details the exact steps to deploy and register a custom agent with
**A2UI** support in **Gemini Enterprise (GE)**, avoiding the authentication
loops and deployment errors encountered previously.

--------------------------------------------------------------------------------

## 🛠️ Phase 1: Code and Environment Preparation

1.  **Obtain the Code:**

    *   Clone or download the repository/base code of the agent:
        [a2ui-seed-agent](https://github.com/cloud-ai-transformation-team/a2ui-seed-agent/tree/main).
    *   If the repository is on Drive, ensure it is unzipped and accessible in
        your working environment.

2.  **Assistant Access (Optional but recommended):**

    *   For Jetski (or another agent) to read and analyze the repository, ensure
        that the **MCP (Model Context Protocol) for Workspace** is active and
        has access to the folder in Drive.

--------------------------------------------------------------------------------

## 🔑 Phase 2: GCP Credentials Configuration

1.  Go to the **Google Cloud Console (GCP) ➔ APIs & Services ➔ Credentials**.
2.  **Create an OAuth 2.0 Client:**
    *   Application type: **Web application**.
    *   Name: `GE Integration Client` (or similar).
3.  **🔴 CRITICAL Redirect Configuration (Redirect URIs):** You must add
    **exactly** the following URIs in the "Authorized redirect URIs" section:
    *   `https://vertexaisearch.cloud.google.com/static/oauth/oauth.html`
    *   `https://vertexaisearch.cloud.google.com/oauth-redirect`
4.  **Save** and copy the **Client ID** and **Client Secret**.

--------------------------------------------------------------------------------

## 🚀 Phase 3: Deployment to Cloud Run

The agent must be running on a service accessible by GE.

1.  **Key Environment Variables:** When deploying to Cloud Run, ensure you
    configure the following variables:

    *   `GOOGLE_GENAI_USE_VERTEXAI="TRUE"` 👈 *Avoids "No API key provided"
        errors when using the SDK.*
    *   `GOOGLE_CLOUD_PROJECT="your-project-id"`
    *   `GOOGLE_CLOUD_LOCATION="your-region"` (e.g., `us-central1`)

2.  **Invocation Permissions (IAM):** GE needs permission to talk to your Cloud
    Run service.

    *   Add the **`roles/run.invoker`** role to your project's Discovery Engine
        service account:
        *   Format:
            `service-<PROJECT_NUMBER>@gcp-sa-discoveryengine.iam.gserviceaccount.com`

--------------------------------------------------------------------------------

## 📝 Phase 4: Agent Registration in Gemini Enterprise

1.  Go to the **Gemini Enterprise Console ➔ Agents ➔ Add Agent**.
2.  **Step 1: Import Agent (Agent Card JSON):**

    *   Paste the JSON describing your agent. Ensure the `preferredTransport`
        field matches what your server implements (e.g., `JSONRPC` or
        `HTTP+JSON`).

3.  **Step 2: Agent Authorization 🔴 EXTREMELY IMPORTANT 🔴:** Fill in the fields
    with extreme care:

    *   **Client ID:** The one obtained in Phase 2.
    *   **Client Secret:** The one obtained in Phase 2.
    *   **Authorization URL:** Must include specific parameters for Google
        OAuth. Use this **exact** structure:

        ```text
        https://accounts.google.com/o/oauth2/v2/auth?access_type=offline&prompt=consent&scope=https://www.googleapis.com/auth/cloud-platform
        ```

        *   *(Explanation: `access_type=offline` generates the refresh token,
            `prompt=consent` forces the permission screen).*
    *   **Token URL:** `https://oauth2.googleapis.com/token`
    *   **Scopes:** `https://www.googleapis.com/auth/cloud-platform`

4.  **Step 3:** Skip if you don't require additional Tool Authorizations at this
    moment.

--------------------------------------------------------------------------------

## 💡 Phase 5: A2UI Data Packaging (Backend)

For GE to render the UI, your backend **MUST** package the response correctly.

1.  The response containing the A2UI JSON must be a **`DataPart`** (in A2A
    terms).
2.  **The Metadata is CRITICAL:** The DataPart must have the following MIME
    Type:

    ```python
    metadata={"mimeType": "application/json+a2ui"}
    ```

    *If it does not have this exact metadata, GE will treat it as plain text or
    generic JSON and will NOT render the card.*

--------------------------------------------------------------------------------

## 🔍 Troubleshooting Common Issues

*   **Error 403 on `widgetStoreUserAuthorization`:**
    *   Cause: **Invalid Client Secret** or copied incorrectly in the agent
        configuration in GE.
    *   Cause 2: Missing `access_type=offline` parameters in the Authorization
        URL.
*   **The agent responds with text but does not show the card:**
    *   Verify that the Backend is injecting the MIME type
        `application/json+a2ui`.
    *   Verify that the A2UI JSON is valid according to the component catalog.
*   **Error "No API key was provided":**
    *   Ensure the `GOOGLE_GENAI_USE_VERTEXAI=TRUE` variable is active in Cloud
        Run.
