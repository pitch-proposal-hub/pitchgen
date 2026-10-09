/**
 * PitchGen Google Slides Add-on Configuration
 *
 * Configure your Google Cloud Project, Vertex AI Agent Engine (Reasoning Engine),
 * Cloud Run / App Engine backend URL, and Google Cloud Storage buckets below.
 */
var ENVIRONMENT = "PROD";

var CONFIG = {
  DEV: {
    PROJECT_ID: "your-gcp-project-id-dev",
    PROJECT_NUMBER: "000000000000",
    REGION: "us-central1",
    REASONING_ENGINE_ID: "YOUR_DEV_REASONING_ENGINE_ID",
    BACKEND_URL: "https://your-dev-backend-service.a.run.app",
    GCS_BUCKET_CONTENT: "your-pitchgen-content-bucket-dev",
    SUPPORT_EMAIL: "pitchgen-support@example.com",
    TEMPLATE_DECK_IDS: {
      CONTEXT: "TEMPLATE_DECK_CONTEXT_V1_PLACEHOLDER_001",
      TITLE: "TEMPLATE_DECK_TITLE_V1_PLACEHOLDER_00001",
      AGENDA: "TEMPLATE_DECK_AGENDA_V1_PLACEHOLDER_0001",
      DIVIDER: "TEMPLATE_DECK_DIVIDER_V1_PLACEHOLDER_001",
      THANK_YOU: "TEMPLATE_DECK_THANKYOU_V1_PLACEHOLDER_01"
    }
  },
  QA: {
    PROJECT_ID: "your-gcp-project-id-qa",
    PROJECT_NUMBER: "000000000000",
    REGION: "us-central1",
    REASONING_ENGINE_ID: "YOUR_QA_REASONING_ENGINE_ID",
    BACKEND_URL: "https://your-qa-backend-service.a.run.app",
    GCS_BUCKET_CONTENT: "your-pitchgen-content-bucket-qa",
    SUPPORT_EMAIL: "pitchgen-support@example.com",
    TEMPLATE_DECK_IDS: {
      CONTEXT: "TEMPLATE_DECK_CONTEXT_V1_PLACEHOLDER_001",
      TITLE: "TEMPLATE_DECK_TITLE_V1_PLACEHOLDER_00001",
      AGENDA: "TEMPLATE_DECK_AGENDA_V1_PLACEHOLDER_0001",
      DIVIDER: "TEMPLATE_DECK_DIVIDER_V1_PLACEHOLDER_001",
      THANK_YOU: "TEMPLATE_DECK_THANKYOU_V1_PLACEHOLDER_01"
    }
  },
  PROD: {
    PROJECT_ID: "your-gcp-project-id",
    PROJECT_NUMBER: "000000000000",
    REGION: "us-central1",
    REASONING_ENGINE_ID: "YOUR_REASONING_ENGINE_ID",
    BACKEND_URL: "https://your-prod-backend-service.a.run.app",
    GCS_BUCKET_CONTENT: "your-pitchgen-content-bucket",
    SUPPORT_EMAIL: "pitchgen-support@example.com",
    TEMPLATE_DECK_IDS: {
      CONTEXT: "TEMPLATE_DECK_CONTEXT_V1_PLACEHOLDER_001",
      TITLE: "TEMPLATE_DECK_TITLE_V1_PLACEHOLDER_00001",
      AGENDA: "TEMPLATE_DECK_AGENDA_V1_PLACEHOLDER_0001",
      DIVIDER: "TEMPLATE_DECK_DIVIDER_V1_PLACEHOLDER_001",
      THANK_YOU: "TEMPLATE_DECK_THANKYOU_V1_PLACEHOLDER_01"
    }
  }
};

function getActiveConfig() {
  return CONFIG[ENVIRONMENT] || CONFIG.PROD;
}
