// ==========================================
// ENVIRONMENT CONFIGURATION
// ==========================================

// Change this variable to switch environments: "DEV", "QA", "UAT", "PROD"
var environment = "PROD";

var ENVIRONMENTS = {
  DEV: {
    feedbackUrl: "YOUR_DEV_FEEDBACK_FORM_URL",
    serviceUrl: "https://YOUR_DEV_SERVICE_URL/",
    templateBucketName: 'YOUR_DEV_TEMPLATE_BUCKET',
    templateJsonBucketName: 'YOUR_DEV_TEMPLATE_JSON_BUCKET',
    databaseUrl: 'https://YOUR_DEV_DATABASE_URL/',
    projectId: 'YOUR_DEV_PROJECT_ID',
    reasoningEngines: {
      addSlide: 'YOUR_DEV_REASONING_ENGINE_ID',
      reshuffle: 'YOUR_DEV_REASONING_ENGINE_ID',
      getAgendas: 'YOUR_DEV_REASONING_ENGINE_ID',
      getReuseArch: 'YOUR_DEV_REASONING_ENGINE_ID',
      translate: 'YOUR_DEV_REASONING_ENGINE_ID',
      searchSlide: 'YOUR_DEV_REASONING_ENGINE_ID',
      nanoBanana: 'YOUR_DEV_REASONING_ENGINE_ID'
    }
  },
  QA: {
    feedbackUrl: "YOUR_QA_FEEDBACK_FORM_URL",
    serviceUrl: "https://YOUR_QA_SERVICE_URL/",
    templateBucketName: 'YOUR_QA_TEMPLATE_BUCKET',
    templateJsonBucketName: 'YOUR_QA_TEMPLATE_JSON_BUCKET',
    databaseUrl: 'https://YOUR_QA_DATABASE_URL/',
    projectId: 'YOUR_QA_PROJECT_ID',
    reasoningEngines: {} // Fallback to serviceUrl endpoints
  },
  UAT: {
    feedbackUrl: "YOUR_UAT_FEEDBACK_FORM_URL",
    serviceUrl: "https://YOUR_UAT_SERVICE_URL/",
    templateBucketName: 'YOUR_UAT_TEMPLATE_BUCKET',
    templateJsonBucketName: 'YOUR_UAT_TEMPLATE_JSON_BUCKET',
    databaseUrl: 'https://YOUR_UAT_DATABASE_URL/',
    projectId: 'YOUR_UAT_PROJECT_ID',
    reasoningEngines: {
      addSlide: 'YOUR_UAT_REASONING_ENGINE_ID',
      reshuffle: 'YOUR_UAT_REASONING_ENGINE_ID',
      getAgendas: 'YOUR_UAT_REASONING_ENGINE_ID',
      getReuseArch: 'YOUR_UAT_REASONING_ENGINE_ID',
      translate: 'YOUR_UAT_REASONING_ENGINE_ID',
      searchSlide: 'YOUR_UAT_REASONING_ENGINE_ID',
      nanoBanana: 'YOUR_UAT_REASONING_ENGINE_ID'
    } // Fallback to serviceUrl endpoints
  },
  PROD: {
    feedbackUrl: "YOUR_PROD_FEEDBACK_FORM_URL",
    serviceUrl: "https://YOUR_PROD_SERVICE_URL/",
    templateBucketName: 'YOUR_PROD_TEMPLATE_BUCKET',
    templateJsonBucketName: 'YOUR_PROD_TEMPLATE_JSON_BUCKET',
    databaseUrl: 'https://YOUR_PROD_DATABASE_URL/',
    projectId: 'YOUR_PROD_PROJECT_ID',
    reasoningEngines: {
      addSlide: 'YOUR_PROD_REASONING_ENGINE_ID',
      reshuffle: 'YOUR_PROD_REASONING_ENGINE_ID',
      getAgendas: 'YOUR_PROD_REASONING_ENGINE_ID',
      getReuseArch: 'YOUR_PROD_REASONING_ENGINE_ID',
      translate: 'YOUR_PROD_REASONING_ENGINE_ID',
      searchSlide: 'YOUR_PROD_REASONING_ENGINE_ID',
      nanoBanana: 'YOUR_PROD_REASONING_ENGINE_ID'
    } // Fallback to serviceUrl endpoints
  }
};

// Get active configuration
var activeConfig = ENVIRONMENTS[environment] || ENVIRONMENTS.DEV;

// Export global variables for backward compatibility
var feedbackUrl = activeConfig.feedbackUrl;
var serviceUrl = activeConfig.serviceUrl;
var templateBucketName = activeConfig.templateBucketName;
var projectId = activeConfig.projectId;
var engines = activeConfig.reasoningEngines || {};
var templateJsonBucketName = activeConfig.templateJsonBucketName;

// Helper to construct Reasoning Engine URLs
function getReasoningEngineUrl(projId, engineId, streamType) {
  if (!projId || !engineId || engineId.indexOf("YOUR_") === 0) {
    return "";
  }
  var url = "https://us-central1-aiplatform.googleapis.com/v1/projects/" + projId + "/locations/us-central1/reasoningEngines/" + engineId + ":streamQuery";
  if (streamType === "sse") {
    url += "?alt=sse";
  }
  return url;
}

// API Links for code.gs file
var addSlideApiUrl = getReasoningEngineUrl(projectId, engines.addSlide, "sse") || (serviceUrl + "addSlide");
var reshuffleApiUrl = getReasoningEngineUrl(projectId, engines.reshuffle, "sse") || (serviceUrl + "reshuffle");
var getReshuffleApiUrl = serviceUrl + "getReshuffle";

// API Links for restApi.gs file
var getAgendasApiUrl = getReasoningEngineUrl(projectId, engines.getAgendas, "none") || (serviceUrl + "getAgendas");
var getReuseArchApiUrl = getReasoningEngineUrl(projectId, engines.getReuseArch, "sse") || (serviceUrl + "getReuseArch");
var getContentsApiUrl = serviceUrl + "getContents";
var getDriveUrlApiUrl = serviceUrl + "getdriveurl";
var translateApiUrl = getReasoningEngineUrl(projectId, engines.translate, "sse") || (serviceUrl + "translate");
var getTranslateData = serviceUrl + "getTranslateData";

// API Links for feedbackForm.gs file
var getFeedbackDataApiUrl = serviceUrl + "getFeedbackData";
var saveFeedbackApiUrl = serviceUrl + "saveFeedback";

var promptsApiUrl = serviceUrl + "prompts";                 //Loading prompts on first popup
var saveErNumber = serviceUrl + "saveErNumber";             //Saving ER Id
var getErNumber = serviceUrl + "getErNumber";               //Fetching ER Id

var salesPlayLoadApiUrl = serviceUrl + "salesPlayLoad";
var salesPlayApiUrl = serviceUrl + "salesPlay";
var salesPlayContent = serviceUrl + "salesPlayContents";
var salesPlaySave = serviceUrl + "saveSalesPlay";

var uploadTemplate = serviceUrl + "uploadTemplate";         //Uploading side bar template into the bucket
var readTemplate = serviceUrl + "readTemplate";             //Fetching the template image url

var getSalesPlay = serviceUrl + "getSalesPlay";

//var saveSearchAPI = serviceUrl + "saveSearch";

var searchSlideApiURL = getReasoningEngineUrl(projectId, engines.searchSlide, "sse") || (serviceUrl + "searchSlide");

var nanoBanana_imageGen = getReasoningEngineUrl(projectId, engines.nanoBanana, "sse") || (serviceUrl + "nanoBanana_imageGen");
var nanoBanana_imageTrans = getReasoningEngineUrl(projectId, engines.nanoBanana, "sse") || (serviceUrl + "nanoBanana_imageTrans");

var saveUserInput = activeConfig.databaseUrl + "saveUserInput";
var saveEditAction = activeConfig.databaseUrl + "saveEditAction";
var updateCountsOfCopiedSuggestionSlide = activeConfig.databaseUrl + "updateCounts";

// Variables for all the environments
var supportText = `For any technical support, please send an email to "YOUR_SUPPORT_EMAIL"`;
var userSlideTemplateUrl = "YOUR_SLIDE_TEMPLATE_URL";
var deprecatedSlide = "YOUR_DEPRECATED_SLIDE_URL";

var responseObject = {};
var contentGenCount = 0;
var languageTranslationCount = 0;
var mappingSourceAndCopiedSlideId = {};
var salesPlaySlidesPercentage = 0.5;
var salesPlayContentApiCallCount = 0;
var totalCopiedSuggestionSlide = 0;
var totalBlankSuggestionFound = 0;
var totalFailedSuggestionSlide = 0;

var sidebarTemplate = []; // Add customer Google Presentation IDs here for sidebar templates
var templateFolderName = 'UI/templates/';
var sideBarImageUploadFolderName = 'UI/sidebarImageUpload';
var sidebarTemplateJsonFileName = 'template/latest_template_data.json'; 
// Securely retrieved at runtime from Script Properties to avoid version control leaks
// developerKey removed from global scope to prevent AuthMode.NONE errors on load.
// It is now fetched dynamically in Code.gs getDeveloperKey().