// PitchGen External UI Configuration Script

var environment = "PRODUCTION";
var feedbackUrl = "https://docs.google.com/forms/d/e/your-feedback-form-id/viewform";

// API Links pointing to your deployed PitchGen-backend endpoint
var serviceUrl = "https://your-pitchgen-backend-service-url.com/";

var templateBucketName = "your-template-bucket-name";

var addSlideApiUrl = serviceUrl + "addSlide";
var infographicGenUrl = serviceUrl + "infographicGen";
var reshuffleApiUrl = serviceUrl + "reshuffle";
var getReshuffleApiUrl = serviceUrl + "getReshuffle";

// API Links for restApi.gs file
var getAgendasApiUrl = serviceUrl + "getAgendas";
var getReuseArchApiUrl = serviceUrl + "getReuseArch";
var getContentsApiUrl = serviceUrl + "getContents";

var getDriveUrlApiUrl = serviceUrl + "getdriveurl";
var translateApiUrl = serviceUrl + "translate";
var getTranslateData = serviceUrl + "getTranslateData";

// API Links for feedbackForm.gs file
var getFeedbackDataApiUrl = serviceUrl + "getFeedbackData";
var saveFeedbackApiUrl = serviceUrl + "saveFeedback";

var promptsApiUrl = serviceUrl + "prompts";                 // Loading prompts on first popup
var saveErNumber = serviceUrl + "saveErNumber";             // Saving Opportunity ID
var getErNumber = serviceUrl + "getErNumber";               // Fetching Opportunity ID

var salesPlayLoadApiUrl = serviceUrl + "salesPlayLoad";
var salesPlayApiUrl = serviceUrl + "salesPlay";
var salesPlayContent = serviceUrl + "salesPlayContents";
var salesPlaySave = serviceUrl + "saveSalesPlay";

var uploadTemplate = serviceUrl + "uploadTemplate";         // Uploading sidebar template into the bucket
var readTemplate = serviceUrl + "readTemplate";             // Fetching the template image url

var getSalesPlay = serviceUrl + "getSalesPlay";

var saveSearchAPI = serviceUrl + "saveSearch";
var updateCountsOfCopiedSuggestionSlide = serviceUrl + "updateCounts";

// Variables for all the environments
var supportText = `For any technical support, please send an email to "your-support-email@domain.com"`;
var userSlideTemplateUrl = "https://docs.google.com/presentation/d/your-user-slide-template-deck-id/edit?usp=sharing";
var deprecatedSlide = "https://docs.google.com/presentation/d/your-deprecated-slide-deck-id/edit?usp=sharing";

var responseObject = {};
var contentGenCount = 0;
var languageTranslationCount = 0;
var mappingSourceAndCopiedSlideId = {};
var salesPlaySlidesPercentage = 0.5;
var salesPlayContentApiCallCount = 0;
var totalCopiedSuggestionSlide = 0;
var totalBlankSuggestionFound = 0;
var totalFailedSuggestionSlide = 0;

// Array of master presentation template slide IDs in Google Drive
var sidebarTemplate = [
  "your-slide-template-id-1",
  "your-slide-template-id-2",
  "your-slide-template-id-3"
];
var templateFolderName = "UI/templates/";