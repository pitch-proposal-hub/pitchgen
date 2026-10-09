// Global Configuration
var userSlideTemplateId = "SAMPLE_PRESENTATION_ID_PLACEHOLDER_00003";
if (typeof reuseAndContentJSONBucketName === 'undefined' ||
    !reuseAndContentJSONBucketName) {
  var reuseAndContentJSONBucketName = 'your-pitchgen-content-bucket';
}

/**
 * Resolves user identity seamlessly, treating LDAP and userEmail as interchangeable.
 * Returns { ldap: "username", email: "username@example.com" }
 */
function resolveUserIdentity(rawInput) {
  var user = (rawInput || "").toString().trim();
  if (!user) {
    user = Session.getActiveUser().getEmail() || "unknown_user";
  }
  var ldap = user.includes("@") ? user.split("@")[0].toLowerCase().trim() : user.toLowerCase().trim();
  var email = user.includes("@") ? user.trim() : (ldap + "@example.com");
  return { ldap: ldap, email: email };
}

/**
 * 1. GET Handler (doGet)
 * Triggered when a user logs in and consents via Google OAuth.
 * Automatically exchanges authorization code for tokens, saves refresh_token to GCS,
 * and renders a clean success page without requiring manual code copy-pasting.
 */
function doGet(e) {
  var code = e && e.parameter ? e.parameter.code : null;
  var rawUser = (e && e.parameter ? e.parameter.state : null) || (e && e.parameter ? (e.parameter.userEmail || e.parameter.user_ldap) : null);

  if (code) {
    try {
      var user = resolveUserIdentity(rawUser);
      var userLdap = user.ldap;
      var userEmail = user.email;

      // 1. Fetch OAuth client credentials (from Script Properties or Secret Manager)
      var clientCreds = getOAuthClientCredentials();
      
      // 2. Exchange code for tokens
      var tokenUrl = "https://oauth2.googleapis.com/token";
      var payload = {
        code: code.trim(),
        client_id: clientCreds.clientId,
        client_secret: clientCreds.clientSecret,
        redirect_uri: ScriptApp.getService().getUrl(),
        grant_type: "authorization_code"
      };

      var tokenResponse = UrlFetchApp.fetch(tokenUrl, {
        method: "post",
        payload: payload,
        muteHttpExceptions: true
      });

      var tokenData = JSON.parse(tokenResponse.getContentText());
      console.log("Token exchange response status: " + tokenResponse.getResponseCode());

      if (tokenData.refresh_token) {
        // 3. Save refresh token to GCS bucket: auth_tokens/{userLdap}_refresh_token.json
        saveRefreshTokenToGCS(userLdap, tokenData.refresh_token);
        console.log("Saved refresh token to GCS for user: " + userLdap);
      } else if (tokenData.access_token) {
        // Also cache active access token if refresh token wasn't returned
        saveActiveAccessTokenToGCS(userLdap, tokenData.access_token);
        console.log("Cached active access token to GCS for user: " + userLdap);
      } else {
        console.warn("No refresh_token or access_token in exchange response: " + tokenResponse.getContentText());
      }

      // 4. Render a modern, professional Google-styled success page
      var successHtml = '<!DOCTYPE html><html><head><meta charset="utf-8">' +
        '<title>PitchGen Authorization Successful</title>' +
        '<link href="https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;700&display=swap" rel="stylesheet">' +
        '<style>' +
        '  body { font-family: "Google Sans", Roboto, Arial, sans-serif; background-color: #f8f9fa; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }' +
        '  .card { background: white; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); padding: 40px 32px; max-width: 440px; text-align: center; border: 1px solid #dadce0; }' +
        '  .icon { width: 56px; height: 56px; background: #e8f0fe; color: #1a73e8; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 28px; margin: 0 auto 20px auto; }' +
        '  h2 { color: #202124; font-size: 22px; margin: 0 0 12px 0; font-weight: 500; }' +
        '  p { color: #5f6368; font-size: 14px; line-height: 1.5; margin: 0 0 24px 0; }' +
        '  .user-badge { display: inline-block; background: #f1f3f4; color: #3c4043; font-weight: 500; padding: 6px 14px; border-radius: 12px; font-size: 13px; margin-bottom: 20px; }' +
        '  .btn { display: inline-block; background: #1a73e8; color: white; padding: 10px 24px; border-radius: 8px; font-size: 14px; font-weight: 500; text-decoration: none; cursor: pointer; border: none; }' +
        '</style></head><body>' +
        '<div class="card">' +
        '  <div class="icon">✓</div>' +
        '  <h2>Authorization Successful</h2>' +
        '  <div class="user-badge">' + userLdap + '@example.com</div>' +
        '  <p>PitchGen is now authorized to create presentations in your Google Drive. You can safely close this window and return to Gemini Enterprise.</p>' +
        '  <button class="btn" onclick="window.close()">Close Window</button>' +
        '</div>' +
        '</body></html>';
      return HtmlService.createHtmlOutput(successHtml);

    } catch (err) {
      console.error("Error during automated OAuth code exchange: " + err.message);
      var errHtml = '<html><body style="font-family: Google Sans, sans-serif; padding: 30px; text-align: center;">' +
        '<h2 style="color: #d93025;">Authorization Error</h2>' +
        '<p style="color: #5f6368;">' + err.message + '</p>' +
        '</body></html>';
      return HtmlService.createHtmlOutput(errHtml);
    }
  }

  return HtmlService.createHtmlOutput("<h2>PitchGen Apps Script Active</h2>");
}

/**
 * Saves the refresh token to Cloud Storage bucket: your-pitchgen-content-bucket
 */
function saveRefreshTokenToGCS(userLdap, refreshToken) {
  var bucketName = reuseAndContentJSONBucketName || "your-pitchgen-content-bucket";
  var fileName = "auth_tokens/" + userLdap + "_refresh_token.json";
  var uploadData = { refresh_token: refreshToken };
  uploadSidebarTemplateJsonFileInGcs(bucketName, fileName, uploadData);
}

/**
 * Saves active access token to Cloud Storage bucket: your-pitchgen-content-bucket
 */
function saveActiveAccessTokenToGCS(userLdap, accessToken) {
  var bucketName = reuseAndContentJSONBucketName || "your-pitchgen-content-bucket";
  var fileName = "auth_tokens/" + userLdap + "_active_token.json";
  var uploadData = { access_token: accessToken };
  uploadSidebarTemplateJsonFileInGcs(bucketName, fileName, uploadData);
}

/**
 * Retrieves OAuth client ID and Secret from Script Properties or Secret Manager
 */
function getOAuthClientCredentials() {
  var scriptProps = PropertiesService.getScriptProperties();
  var clientId = scriptProps.getProperty("CLIENT_ID") || scriptProps.getProperty("OAUTH_CLIENT_ID");
  var clientSecret = scriptProps.getProperty("CLIENT_SECRET") || scriptProps.getProperty("OAUTH_CLIENT_SECRET");

  if (clientId && clientSecret) {
    return { clientId: clientId, clientSecret: clientSecret };
  }

  // Fallback: Fetch directly from Secret Manager using Apps Script OAuth Token
  try {
    var token = ScriptApp.getOAuthToken();
    var projId = projectId || "your-gcp-project-id";
    
    if (!clientId) {
      var idUrl = "https://secretmanager.googleapis.com/v1/projects/" + projId + "/secrets/oauth-client-id/versions/latest:access";
      var idRes = UrlFetchApp.fetch(idUrl, { headers: { Authorization: "Bearer " + token }, muteHttpExceptions: true });
      if (idRes.getResponseCode() === 200) {
        var idPayload = JSON.parse(idRes.getContentText());
        clientId = Utilities.newBlob(Utilities.base64Decode(idPayload.payload.data)).getDataAsString().trim();
      }
    }

    if (!clientSecret) {
      var secUrl = "https://secretmanager.googleapis.com/v1/projects/" + projId + "/secrets/oauth-client-secret/versions/latest:access";
      var secRes = UrlFetchApp.fetch(secUrl, { headers: { Authorization: "Bearer " + token }, muteHttpExceptions: true });
      if (secRes.getResponseCode() === 200) {
        var secPayload = JSON.parse(secRes.getContentText());
        clientSecret = Utilities.newBlob(Utilities.base64Decode(secPayload.payload.data)).getDataAsString().trim();
      }
    }
  } catch (secErr) {
    console.warn("Could not fetch secrets from Secret Manager: " + secErr.message);
  }

  return { clientId: clientId || "", clientSecret: clientSecret || "" };
}

/**
 * 2. POST Handler (doPost)
 * Triggered by the Python agent. Parses the GCS file details.
 */
function doPost(e) {
  var payload = JSON.parse(e.postData.contents);
  var action = payload.action;

  if (action === "extract_deck_text") {
    return extractDeckTextHeadless(payload);
  } else if (action === "apply_translation") {
    return applyTranslationHeadless(payload);
  } else if (action === "apply_transform" || action === "transform") {
    return applyTransformHeadless(payload);
  } else if (action === "relink_slides") {
    return relinkReusableSlidesHeadless(payload);
  } else if (action === "check_links") {
    return checkSlideLinksHeadless(payload);
  } else {
    var returnData = reuseArchOrContentGen(payload);
    console.log(returnData.getContent());
    return returnData;
  }
}

/**
 * Checks SlideLinkingMode status for all slides in a presentation
 */
function checkSlideLinksHeadless(payload) {
  try {
    var presentationId = payload.presentationId || payload.presentation_id;
    var presentation = SlidesApp.openById(presentationId);
    var slides = presentation.getSlides();
    var info = [];
    for (var i = 0; i < slides.length; i++) {
      var s = slides[i];
      var mode = "";
      var srcPres = "";
      var srcSlide = "";
      try { mode = String(s.getSlideLinkingMode()); } catch (e) {}
      try { srcPres = String(s.getSourcePresentationId() || ""); } catch (e) {}
      try { srcSlide = String(s.getSourceSlideObjectId() || ""); } catch (e) {}
      info.push({
        index: i + 1,
        slideId: s.getObjectId(),
        linkingMode: mode,
        sourcePresId: srcPres,
        sourceSlideId: srcSlide
      });
    }
    return ContentService.createTextOutput(JSON.stringify({
      status: 200,
      slides: info
    })).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      status: 500,
      error: err.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Replaces unlinked reusable slides with SlidesApp.SlideLinkingMode.LINKED slides in-place
 */
function relinkReusableSlidesHeadless(payload) {
  try {
    var presentationId = payload.presentationId || payload.presentation_id;
    var presentation = SlidesApp.openById(presentationId);
    var items = payload.slides || [];
    var relinked = [];
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var sourcePres = getCachedPresentation(item.sourcePresId);
      if (!sourcePres) continue;
      var sourceSlide = sourcePres.getSlideById(item.sourceSlideId);
      if (!sourceSlide) {
        var srcSlides = sourcePres.getSlides();
        var fbTitle = (item.fallbackTitle || "").trim().toLowerCase();
        if (fbTitle && srcSlides) {
          for (var si = 0; si < srcSlides.length; si++) {
            var spList = srcSlides[si].getShapes();
            for (var sp = 0; sp < spList.length; sp++) {
              try {
                var txt = spList[sp].getText().asString().toLowerCase();
                if (txt.indexOf(fbTitle) !== -1 || (fbTitle.length > 10 && txt.indexOf(fbTitle.substring(0, 15)) !== -1)) {
                  sourceSlide = srcSlides[si];
                  break;
                }
              } catch (e) {}
            }
            if (sourceSlide) break;
          }
        }
        if (!sourceSlide && srcSlides && srcSlides.length > 0) {
          sourceSlide = srcSlides[0];
        }
      }
      if (!sourceSlide) continue;
      var oldSlide = item.oldSlideId ? presentation.getSlideById(item.oldSlideId) : null;
      var oldIdx = -1;
      if (oldSlide) {
        var allSlides = presentation.getSlides();
        for (var k = 0; k < allSlides.length; k++) {
          if (allSlides[k].getObjectId() === item.oldSlideId) {
            oldIdx = k;
            break;
          }
        }
      }
      var prevNotes = "";
      var linkedSlide = null;
      if (oldSlide && oldIdx !== -1) {
        try {
          prevNotes = oldSlide.getNotesPage().getSpeakerNotesShape().getText().asString().trim();
        } catch (e) {}
        linkedSlide = presentation.insertSlide(oldIdx, sourceSlide, SlidesApp.SlideLinkingMode.LINKED);
        oldSlide.remove();
      } else {
        linkedSlide = presentation.appendSlide(sourceSlide, SlidesApp.SlideLinkingMode.LINKED);
      }
      try {
        var notesShape = linkedSlide.getNotesPage().getSpeakerNotesShape();
        var origNotes = prevNotes;
        if (!origNotes) {
          try {
            origNotes = sourceSlide.getNotesPage().getSpeakerNotesShape().getText().asString().trim();
          } catch (e) {}
        }
        var fullNotes = origNotes;
        if (item.slideUrl && fullNotes.indexOf("🔗 Source Slide:") === -1) {
          var sLabel = item.slideLabel || item.fallbackTitle || "Original Reusable Slide";
          var linkHdr = "🔗 Source Slide: " + sLabel + "\n" + item.slideUrl;
          fullNotes = (origNotes && origNotes !== sLabel) ? (linkHdr + "\n\n--- Original Speaker Notes ---\n" + origNotes) : linkHdr;
        }
        if (fullNotes) {
          var tr = notesShape.getText();
          tr.setText(fullNotes);
          tr.getTextStyle().setFontFamily("Google Sans").setFontSize(11);
        }
      } catch (nErr) {}
      var mode = "";
      var srcPresId = "";
      var srcSlideId = "";
      try { mode = String(linkedSlide.getSlideLinkingMode()); } catch (e) {}
      try { srcPresId = String(linkedSlide.getSourcePresentationId() || ""); } catch (e) {}
      try { srcSlideId = String(linkedSlide.getSourceSlideObjectId() || ""); } catch (e) {}
      relinked.push({
        oldSlideId: item.oldSlideId,
        newSlideId: linkedSlide.getObjectId(),
        linkingMode: mode,
        sourcePresId: srcPresId,
        sourceSlideId: srcSlideId
      });
    }
    return ContentService.createTextOutput(JSON.stringify({
      status: 200,
      relinked: relinked
    })).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      status: 500,
      error: err.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Headless Transform Application for Gemini Enterprise
 */
function applyTransformHeadless(payload) {
  try {
    var presentationId = payload.presentationId || payload.presentation_id;
    var bucketName = payload.bucketName || reuseAndContentJSONBucketName;
    var responseFileName = payload.response_gcs_filename || payload.json_filename;

    let presentation;
    try {
      presentation = SlidesApp.openById(presentationId);
    } catch (e) {
      presentation = SlidesApp.openById(presentationId);
    }

    var transformData = null;
    if (responseFileName) {
      var transformJsonStr = readFileFromGCS(bucketName, responseFileName);
      transformData = JSON.parse(transformJsonStr);
    } else if (payload.data) {
      transformData = payload;
    }

    if (!transformData) {
      throw new Error("No transform data provided in payload or GCS file.");
    }

    // 1. Check if the entire payload or slide is marked as skipped
    if (transformData.action === "skipped" || transformData.skip === true || transformData._skip_mutation === true) {
      console.log("Transform payload marked as skipped (0% Immutable Proof Point). Preserving slide without mutations.");
      return ContentService.createTextOutput(JSON.stringify({
        status: 200,
        action: "skipped",
        message: "Proof_Points / Customer Reference slides are immutable. No shapes were modified.",
        deckURL: presentation.getUrl(),
        presentationId: presentationId
      })).setMimeType(ContentService.MimeType.JSON);
    }

    transformPresentationHeadless(transformData, presentation);

    return ContentService.createTextOutput(JSON.stringify({
      status: 200,
      message: "Transformation successfully applied preserving typography!",
      deckURL: presentation.getUrl(),
      presentationId: presentationId
    })).setMimeType(ContentService.MimeType.JSON);
  } catch (error) {
    console.log("Error in applyTransformHeadless: ", error.stack);
    return ContentService.createTextOutput(JSON.stringify({
      status: 500,
      error: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Applies transform text data to presentation slides while strictly preserving formatting
 */
function transformPresentationHeadless(transformData, presentation) {
  var objPresId = transformData.presentationId || transformData.presentation_id || Object.keys(transformData)[0];
  var presentationData = transformData[objPresId] || (transformData.data && transformData.data[objPresId] ? transformData.data[objPresId] : null);

  if (presentationData && typeof presentationData === "object" && !Array.isArray(presentationData)) {
    var slideIds = Object.keys(presentationData);
    for (var i = 0; i < slideIds.length; i++) {
      var slideId = slideIds[i];
      var slideUpdate = presentationData[slideId];
      if (!slideUpdate) continue;

      if (slideUpdate.action === "skipped" || slideUpdate.skip === true || slideUpdate._skip_mutation === true) {
        console.log("Skipping slide " + slideId + " (0% Immutable Proof Point)");
        continue;
      }

      var slide = presentation.getSlideById(slideId);
      if (!slide) continue;

      applyTransformedSlideText(slide, slideUpdate);
    }
    return;
  }

  var singleDataList = Array.isArray(transformData.data) ? transformData.data : (Array.isArray(transformData) ? transformData : null);
  if (singleDataList) {
    var slideId = transformData.slide_id || transformData.slideId;
    var targetSlide = slideId ? presentation.getSlideById(slideId) : presentation.getSlides()[0];
    if (targetSlide) {
      applyTransformedSlideText(targetSlide, { data: singleDataList });
    }
  }
}

/**
 * Updates all text shapes on a slide with strict paragraph-preserving styles
 */
function applyTransformedSlideText(slide, slideUpdateData) {
  if (slideUpdateData.action === "skipped" || slideUpdateData.skip === true || slideUpdateData._skip_mutation === true) {
    console.log("Slide is skipped -> No shapes modified.");
    return;
  }

  var shapes = slide.getShapes();
  var updates = slideUpdateData.data || [];

  for (var i = 0; i < shapes.length; i++) {
    var shape = shapes[i];
    var updateItem = (i < updates.length) ? updates[i] : null;
    if (!updateItem) continue;

    var newText = (typeof updateItem === "string" ? updateItem : updateItem.text || "").trim();
    if (!newText) continue;

    var currentText = shape.getText().asString().trim();

    // Zero-Mutation Guard: If text is identical, NEVER mutate shape!
    if (newText === currentText) {
      console.log("Shape " + i + " text unchanged -> Preserving existing formatting intact.");
      continue;
    }

    updateShapePreservingParagraphStyles(shape, newText);
  }
}

/**
 * Updates text in a multi-paragraph shape while strictly preserving 
 * individual paragraph font sizes, weights, and colors.
 */
function updateShapePreservingParagraphStyles(shape, transformedFullText) {
  var textRange = shape.getText();
  var origParagraphs = textRange.getParagraphs();
  if (!origParagraphs || origParagraphs.length === 0) {
    textRange.setText(transformedFullText);
    return;
  }

  // Snapshot style and content per paragraph
  var styleSnapshots = [];
  var origTexts = [];
  for (var i = 0; i < origParagraphs.length; i++) {
    var pRange = origParagraphs[i].getRange();
    var pStyle = pRange.getTextStyle();
    var fgColor = null;
    try {
      var colorObj = pStyle.getForegroundColor();
      if (colorObj && colorObj.getColorType() === SlidesApp.ColorType.RGB) {
        fgColor = colorObj.asRgbColor().asHexString();
      }
    } catch (e) {}

    origTexts.push(pRange.asString().trim());
    styleSnapshots.push({
      fontSize: pStyle.getFontSize(),
      bold: pStyle.isBold(),
      italic: pStyle.isItalic(),
      underline: pStyle.isUnderline(),
      fontFamily: pStyle.getFontFamily(),
      foregroundColor: fgColor
    });
  }

  var textToSet = transformedFullText;
  // If original shape had a distinct Bold Header (P0) and Regular Body (P1+):
  if (origParagraphs.length > 1 && styleSnapshots[0].bold && styleSnapshots.length > 1 && !styleSnapshots[1].bold) {
    var origHeader = origTexts[0];
    if (origHeader && !textToSet.toLowerCase().startsWith(origHeader.toLowerCase())) {
      var colonIdx = textToSet.indexOf(':');
      if (colonIdx > 0 && colonIdx < 35) {
        var headerPart = textToSet.substring(0, colonIdx).trim();
        var bodyPart = textToSet.substring(colonIdx + 1).trim();
        textToSet = headerPart + "\n" + bodyPart;
      } else {
        textToSet = origHeader + "\n" + textToSet;
      }
    }
  }

  // Set the new text
  textRange.setText(textToSet);

  // Re-apply styles per paragraph
  var newParagraphs = shape.getText().getParagraphs();
  for (var j = 0; j < newParagraphs.length; j++) {
    var style = (j < styleSnapshots.length) 
      ? styleSnapshots[j] 
      : styleSnapshots[styleSnapshots.length - 1];

    if (!style) continue;
    var range = newParagraphs[j].getRange().getTextStyle();
    if (style.fontSize) range.setFontSize(style.fontSize);
    if (style.bold !== undefined && style.bold !== null) range.setBold(style.bold);
    if (style.italic !== undefined && style.italic !== null) range.setItalic(style.italic);
    if (style.underline !== undefined && style.underline !== null) range.setUnderline(style.underline);
    if (style.fontFamily) range.setFontFamily(style.fontFamily);
    if (style.foregroundColor) {
      try {
        range.setForegroundColor(style.foregroundColor);
      } catch (e) {}
    }
  }
}

/**
 * 3. Core Presentation Assembly Logic
 */
function reuseArchOrContentGen(payload) {
  // Extract filenames from GCS URLs passed by Python
  var reusableArchFilename = extractFilename(payload.architectural_filename);
  var contentGenFilename = extractFilename(payload.outputs_filename);
  
  // Resolve user identity: handles userEmail, user_ldap, user interchangeably
  var rawUser = payload.userEmail || payload.user_email || payload.user_ldap || payload.user;
  var user = resolveUserIdentity(rawUser);
  var userLdap = user.ldap;
  var userEmail = user.email;
  
  var format = "yyyy/MM/dd";
  var formattedDate = Utilities.formatDate(new Date(), "GMT", format);
  var presentation_name = "PitchGen_" + formattedDate;
  
  var existingPresId = payload.presentationId || payload.presentation_id || "";
  const presentation = existingPresId ? SlidesApp.openById(existingPresId) : SlidesApp.create(presentation_name);
  const originalSlides = presentation.getSlides();
  const presentationId = presentation.getId();
  
  // Share presentation with the requesting user (as Editor)
  // Wrapped in a try/catch to prevent invalid/test emails from crashing execution
  try {
    presentation.addEditor(userEmail);
    console.log("Shared presentation with userEmail: " + userEmail + " (LDAP: " + userLdap + ")");
  } catch (err) {
    console.warn("Warning: Could not share presentation with " + userEmail + ". Error: " + err.message);
  }
  
  // Preserve existing populated Slide 0 (Internal Context) if present; otherwise insert from template
  var hasPopulatedSlide0 = false;
  if (originalSlides.length > 0) {
    try {
      var s0Text = "";
      var s0Shapes = originalSlides[0].getShapes();
      for (var si = 0; si < s0Shapes.length; si++) {
        s0Text += s0Shapes[si].getText().asString() + " ";
      }
      if (s0Text.toLowerCase().indexOf("internal context") !== -1 && s0Text.indexOf("{{user_ldap}}") === -1) {
        hasPopulatedSlide0 = true;
      }
    } catch (e) {}
  }
  if (hasPopulatedSlide0) {
    for (let i = 1; i < originalSlides.length; i++) {
      try { originalSlides[i].remove(); } catch (e) {}
    }
  } else {
    var template = SlidesApp.openById(userSlideTemplateId);
    var userSlideTemp = template.getSlides()[1];
    var userSlide = presentation.insertSlide(0, userSlideTemp);
    for (let i = 0; i < originalSlides.length; i++) {
      try { originalSlides[i].remove(); } catch (e) {}
    }
  }

  console.log("Reusable Filename :", reusableArchFilename);
  console.log("ContentGen Filename :", contentGenFilename);

  var bucketName = payload.bucket_name || payload.bucketName ||
      reuseAndContentJSONBucketName;
  var reusableArchFinalData = readFileFromGCS(bucketName, reusableArchFilename);
  var resOut = JSON.parse(reusableArchFinalData);
  console.log("reusableArchFinalData : ", resOut);
  
  var reuseSlideIdAndPosition = copySlidesFromSuggestions(resOut, presentationId);
  unskip(presentationId);

  var contentGenFinalData = readFileFromGCS(bucketName, contentGenFilename);
  console.log("contentGenFinalData : ", contentGenFinalData);
  var resOut2 = JSON.parse(contentGenFinalData);

  contentGeneration(resOut2, reuseSlideIdAndPosition, presentationId);
  removeEmptyPlaceholders(presentationId);

  // Execute unified full-deck text transformation post-assembly unless handled by Python post-processor
  if (!payload.skip_inline_transform) {
    try {
      var outCtx = (resOut2 && resOut2.context) || {};
      var contextData = {
        customer_name: payload.customer_name || payload.customerName ||
            (payload.context && payload.context.customer_name) ||
            resOut2.customer_name || outCtx.customer_name || '',
        industry: payload.industry ||
            (payload.context && payload.context.industry) || outCtx.industry ||
            '',
        solution: payload.solution ||
            (payload.context && payload.context.solution) || outCtx.solution ||
            '',
        product: payload.product ||
            (payload.context && payload.context.product) || outCtx.product || '',
        audience: payload.audience ||
            (payload.context && payload.context.audience) || outCtx.audience ||
            '',
        salesPlay: payload.salesPlay ||
            (payload.context && payload.context.salesPlay) || outCtx.salesPlay ||
            ''
      };
      transformFullDeckText(
          presentation, contextData,
          payload.er_number || payload.erNumber || outCtx.er_number || '',
          reuseSlideIdAndPosition);
    } catch (transformErr) {
      console.warn("Notice: full deck post-assembly transform error: " + transformErr);
    }
  }

  return ContentService.createTextOutput(JSON.stringify({
    status: 200,
    message: "The Reusable method was successfully executed!",
    deckURL: presentation.getUrl()
  })).setMimeType(ContentService.MimeType.JSON);
}

/**
 * Helper utility to extract the file name from a GCS path
 */
function extractFilename(gcsUrl) {
  if (!gcsUrl) return "";
  return gcsUrl.substring(gcsUrl.lastIndexOf("/") + 1);
}
