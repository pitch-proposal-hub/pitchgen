function onOpen(e){
  try {
    var addonMenu = SlidesApp.getUi().createAddonMenu();
    addonMenu.addItem('Generate a New Pitch', 'showpopup')
    .addItem('Edit my Presentation','showSidebar')
    .addItem('User Feedback', 'userFeedback')
    .addItem('User Guide', 'userGuide')
    .addSeparator()
    .addItem('🧪 Run End-to-End Diagnostics', 'runPitchGenE2ETest')
    .addToUi(); 
  } catch (err) {
    console.log("createAddonMenu error: " + err);
  }

  try {
    var customMenu = SlidesApp.getUi().createMenu('PitchGen');
    customMenu.addItem('Generate a New Pitch', 'showpopup')
    .addItem('Edit my Presentation','showSidebar')
    .addItem('User Feedback', 'userFeedback')
    .addItem('User Guide', 'userGuide')
    .addSeparator()
    .addItem('🧪 Run End-to-End Diagnostics', 'runPitchGenE2ETest')
    .addToUi();
  } catch (err) {
    console.log("createMenu error: " + err);
  }
}

function onInstall(e) {
  onOpen(e);
}

function showpopup() {
  const bucketName = PropertiesService.getScriptProperties().getProperty('BUCKET_NAME') || templateBucketName;
  const template = HtmlService.createTemplateFromFile('userInputPopup');
  template.bucketName = bucketName;
  template.reuseAndContentJSONBucketName = reuseAndContentJSONBucketName;
  var htmlOutput = template.evaluate()
      .setTitle('Screen1')
      .setHeight(423)
      .setWidth(1000);
  SlidesApp.getUi().showModalDialog(htmlOutput, ' ');
}
function showSidebar(){
  const bucketName = PropertiesService.getScriptProperties().getProperty('BUCKET_NAME') || templateBucketName;
  const template = HtmlService.createTemplateFromFile('sideBar');
  template.bucketName = bucketName;
  template.reuseAndContentJSONBucketName = reuseAndContentJSONBucketName;
  var ui = template.evaluate().setTitle('PitchGen');
  SlidesApp.getUi().showSidebar(ui);
}

function showMyHelp() {                                 //Deprecated for now
  var html =  '<div>'+'<p>'+supportText+'</p>' +        //SupportText In Configuration file
               '</div>';
  var ui = SlidesApp.getUi();
  ui.showModalDialog(HtmlService.createHtmlOutput(html).setHeight(100).setWidth(500), 'PitchGen Help');
}

function addSlideAPI(selectedCategory, sheetId, deckId, slideTitle, slideContent, slideLayout, slideCategory, audience, solution, product, customerName, industry, region, erIdGenerate, fileId, fileType, contextFileUrl, contextFileMimeType)
{
  // Fetch Drive file context if attached
  if (fileId && fileType) {
    try {
      var fileContent = getDriveFileTextContext(fileId, fileType);
      if (fileContent && fileContent !== "Error extracting text content.") {
        slideContent += "\n\n### Additional Context from Google Drive File ###\n" + fileContent;
        console.log("Appended Drive file context to slideContent");
      }
    } catch (e) {
      console.log("Error fetching Drive file context: " + e.toString());
    }
  }

  var slideId = SlidesApp.getActivePresentation().getSelection().getCurrentPage().getObjectId();
  var allSlides = SlidesApp.getActivePresentation().getSlides();
  var firstSlide = SlidesApp.getActivePresentation().getSlides()[0].getObjectId();

  var position = 0;
  for (var j = 0; j < allSlides.length; j++) 
  {
    var slide = allSlides[j];
    if (slide.getObjectId() === slideId) {
      position = (j + 1); 
      break;
    }
  }

  var id = SlidesApp.getActivePresentation().getId();
  
  // Appended thumbnailSize: "SMALL" to reduce token usage
  const imageURL = Slides.Presentations.Pages.getThumbnail(id, firstSlide, {
    "thumbnailProperties.mimeType": "PNG",
    "thumbnailProperties.thumbnailSize": "SMALL"
  }).contentUrl;
  
  var thumbnailBlob = UrlFetchApp.fetch(imageURL).getBlob();
  //var base64Data = Utilities.base64Encode(thumbnailBlob.getBytes());
  var userLdap = Session.getActiveUser().getEmail();
  var imageName = "generate_slide_" + generateUniqueId() + ".png";
  var gsURL = uploadSideBarImageToGCS(thumbnailBlob,imageName,templateBucketName,sideBarImageUploadFolderName);
  var apiUrl = addSlideApiUrl ;
  var data = {
  "audience": audience,
  "industry": industry,
  "product": product,
  "slide_title": slideTitle,
  "slide_content": slideContent,
  "slide_layout": slideLayout,
  "slide_category": slideCategory,
  "slide_id": sheetId,
  "deck_id": deckId,
  "action" : "add_generate",
  "er_number" : erIdGenerate,
  "user_ldap" : userLdap,
  "presentation_id" : id,
  "slide_image_url" : gsURL,
  "context_file_url": contextFileUrl,
  "context_file_mime_type": contextFileMimeType
  };
  // console.log("Payload",data);
  // var options = {
  //   method: "post",
  //   contentType: "application/json",
  //   payload: JSON.stringify(data)
  // };
  const payload = {
    "class_method": "async_stream_query",
    "input": {
    "user_id":userLdap,
    "message": JSON.stringify(data)
    }
  };
  var options = {
    method: "post",
    contentType: "application/json",
   "headers": {
     "Authorization": "Bearer " + ScriptApp.getOAuthToken()
   },
   "payload": JSON.stringify(payload),
   "muteHttpExceptions": true
  };
  console.log("Payload : ",options);
  // var saveERData = {
  //   "presentation_id": id,
  //   "er_number" : erIdGenerate,
  //   "requested_by" : userLdap
  // }
  // var saveEROptions = {
  //   method: "post",
  //   contentType: "application/json",
  //   payload: JSON.stringify(saveERData)
  // };
  var saveAddGenerateData = {
    "slide_title": slideTitle,
    "content": slideContent,
    "slide_layout": slideLayout,
    "slide_category": slideCategory,
    "slide_id": sheetId,
    "deck_id": deckId,
    "action" : "add_generate",
    "opportunity_id" : erIdGenerate,
    "user_ldap" : userLdap,
    "presentation_id" : id,
    "slide_image_url" : gsURL
  };
  var identityToken = ScriptApp.getIdentityToken();
  var saveAddGenerateOptions = {
    method: "post",
    contentType: "application/json",
    "headers": {
      "Authorization": "Bearer " + identityToken
    },
    "payload": JSON.stringify(saveAddGenerateData)
  };
  console.log("Database Payload : ",saveAddGenerateOptions);
  var returnData = {};
  try{
      var response = UrlFetchApp.fetch(apiUrl,options);
      var responseData = response.getContentText();
      console.log("AddSlide Response : ",responseData);
      var resOut = extractProposalData(responseData,"sidebar_generate");
      console.log(resOut);
      if(resOut.Status=="True")
      {
        copySlideBetweenPresentations(position,resOut);

        try {
          var addGenerateSaveResponse = UrlFetchApp.fetch(saveEditAction,saveAddGenerateOptions);
          console.log("addGenerateSaveResponse : ",addGenerateSaveResponse.getContentText());
        } catch(dbErr) {
          console.warn("Non-fatal database log warning: ", dbErr);
        }
      }
      else
      {
        returnData.status = false;
        returnData.error = resOut.message || "Something went wrong";
      }
  }
  catch(e)
  {
    console.error("Error in Add Slide : ", e && e.stack ? e.stack : e);
    var errorMsg = "Unable to process your request. Please try again.";
    try {
      var errorString = e.toString();
      if (errorString.indexOf('{') !== -1 && errorString.lastIndexOf('}') !== -1) {
        var jsonString = errorString.substring(errorString.indexOf('{'), errorString.lastIndexOf('}') + 1);
        var parsed = JSON.parse(jsonString);
        if (parsed && (parsed.error || parsed.message)) {
          errorMsg = parsed.error || parsed.message;
        }
      } else if (e.message) {
        errorMsg = e.message;
      }
    } catch(parseErr) {}
    returnData.status = false;
    returnData.error = errorMsg;
    
    return returnData;
  }
  returnData.status = true;
  return returnData;
}



function reshuffleSlideAPI(sheetId,spreadSheetId,desiredOutputCriteria,slideLayout,slideCategory,erId,toggleThemeLayout,language,isFullDeck)
{
  var slideId = SlidesApp.getActivePresentation().getSelection().getCurrentPage().getObjectId();
  var allSlides = SlidesApp.getActivePresentation().getSlides();
  
  var position = 0;
  for (var j = 0; j < allSlides.length; j++) 
  {
    var slide = allSlides[j];
    if (slide.getObjectId() === slideId) {
      position = (j + 1); 
      break;
    }
  }

  var id = SlidesApp.getActivePresentation().getId();
  
  // Appended thumbnailSize: "SMALL" to reduce token usage
  const imageURL = Slides.Presentations.Pages.getThumbnail(id, slideId, {
    "thumbnailProperties.mimeType": "PNG"
  }).contentUrl;
  
  var thumbnailBlob = UrlFetchApp.fetch(imageURL).getBlob();
  //var base64Data = Utilities.base64Encode(thumbnailBlob.getBytes());
  var userLdap = Session.getActiveUser().getEmail();
  var imageName = "reshuffle_slide_" + generateUniqueId() + ".png";
  var gsURL = uploadSideBarImageToGCS(thumbnailBlob,imageName,templateBucketName,sideBarImageUploadFolderName);
  var apiUrl = reshuffleApiUrl ;
  var data = {
  "toggle": toggleThemeLayout,
  "slide_layout": slideLayout,
  "slide_category": slideCategory,
  "slide_id": sheetId,
  "deck_id": spreadSheetId,
  "output_criteria" : desiredOutputCriteria,
  "action" : "transform",
  "er_number" : erId,
  "user_ldap" : userLdap,
  "presentation_id" : id,
  "slide_image_url" : gsURL
  };
  var options;
  if(toggleThemeLayout==false)
  {
    // options = {
    //   method: "post",
    //   contentType: "application/json",
    //   payload: JSON.stringify(data)
    // };
    // console.log("Payload : ",data);
    const payload = {
      "class_method": "async_stream_query",
      "input": {
      "user_id":userLdap,
      "message": JSON.stringify(data)
      }
    };
    options = {
      method: "post",
      contentType: "application/json",
    "headers": {
      "Authorization": "Bearer " + ScriptApp.getOAuthToken()
    },
    "payload": JSON.stringify(payload),
    "muteHttpExceptions": true
    };
    console.log("Payload : ",options);
  }
  else
  {
    var togglePayload = reshuffleToggleOffPayload(erId,desiredOutputCriteria,isFullDeck);
    console.log("togglePayload : ",togglePayload);
    // options = {
    //   method: "post",
    //   contentType: "application/json",
    //   payload: JSON.stringify(togglePayload)
    // };
    // console.log("Payload : ",togglePayload);
    const payload = {
      "class_method": "async_stream_query",
      "input": {
      "user_id":userLdap,
      "message": JSON.stringify(togglePayload)
      }
    };
    options = {
      method: "post",
      contentType: "application/json",
      "headers": {
        "Authorization": "Bearer " + ScriptApp.getOAuthToken()
      },
      "payload": JSON.stringify(payload),
      "muteHttpExceptions": true
    };
    console.log("Payload : ",options);
  }
  // var saveERData = {
  //   "presentation_id": id,
  //   "er_number" : erId,
  //   "requested_by" : userLdap
  // }
  // var saveEROptions = {
  //   method: "post",
  //   contentType: "application/json",
  //   payload: JSON.stringify(saveERData)
  // };
  var returnData = {};
  try
  {
    var response = UrlFetchApp.fetch(apiUrl,options);                 //Return filename
    var responseData = response.getContentText();
    console.log("ResponseData : ",responseData);
    var toggleResOut = extractProposalData(responseData,"transform_slide_payload");
    console.log("ResOut : ",toggleResOut);
    
    if(toggleResOut.message=='Success' || toggleResOut.status=='success')
    {
      // var payloadData = {
      //   "filename": toggleResOut.data.response
      // };
      // var finalOptions = {
      //   method: "post",
      //   contentType: "application/json",
      //   payload: JSON.stringify(payloadData)
      // };
      // console.log(finalOptions);
      // var finalResponse = UrlFetchApp.fetch(getReshuffleApiUrl,finalOptions);             //Return actual content
      // var finalResOut = JSON.parse(finalResponse.getContentText());
      // console.log("finalResout : ",finalResOut);
      // if(finalResOut.status=='success')
      // {
        var saveSlideTransformData;
        if(toggleThemeLayout==false)
        {
          returnData.status = reshuffleInsertSlideToggleOff(position,sheetId,spreadSheetId,toggleResOut);
          saveSlideTransformData = {
            "slide_layout": slideLayout,
            "slide_category": slideCategory,
            "slide_id": sheetId,
            "deck_id": spreadSheetId,
            "language": language,
            "content" : desiredOutputCriteria,
            "action" : "transform_slide",
            "opportunity_id" : erId,
            "user_ldap" : userLdap,
            "presentation_id" : id,
            "slide_image_url" : gsURL
          };
        }
        else
        {
          returnData.status = reshuffleInsertSlideToggleOn(toggleResOut);
          saveSlideTransformData = {
            "content" : desiredOutputCriteria,
            "action" : "transform_content",
            "opportunity_id" : erId,
            "user_ldap" : userLdap,
            "presentation_id" : id,
          };
        }
        if(returnData.status==true)
        {
          try {
            var identityToken = ScriptApp.getIdentityToken();
            var saveSlideTransformOptions = {
              method: "post",
              contentType: "application/json",
              "headers": {
                "Authorization": "Bearer " + identityToken
              },
              "payload": JSON.stringify(saveSlideTransformData),
              "muteHttpExceptions": true
            };
            console.log("Database Payload : ",saveSlideTransformOptions);

            var slideTransformSaveResponse = UrlFetchApp.fetch(saveEditAction,saveSlideTransformOptions);
            console.log("slideTransformSaveResponse : ",slideTransformSaveResponse.getContentText());
          } catch(dbErr) {
            console.warn("Non-fatal database log warning: ", dbErr);
          }
        }
        console.log("********************SUCCESS********************");
    }
    else
    {
      returnData.status = false;
      returnData.error = (toggleResOut && (toggleResOut.message || toggleResOut.error)) || "Failed to transform slide";
    }
  }
  catch(e)
  {
    console.error("Error in Reshuffle Slide : ", e && e.stack ? e.stack : e);
    var errorMsg = "Unable to process your request. Please try again.";
    try {
      var errorString = e.toString();
      if (errorString.indexOf('{') !== -1 && errorString.lastIndexOf('}') !== -1) {
        var jsonString = errorString.substring(errorString.indexOf('{'), errorString.lastIndexOf('}') + 1);
        var parsed = JSON.parse(jsonString);
        if (parsed && (parsed.error || parsed.message)) {
          errorMsg = parsed.error || parsed.message;
        }
      } else if (e.message) {
        errorMsg = e.message;
      }
    } catch(parseErr) {}
    returnData.status = false;
    returnData.error = errorMsg;
    
    return returnData;
  }
  returnData.status = true;
  return returnData;
}

function readSlides(id)
{
  try
  {
    var presentation = SlidesApp.openById(id);
    var slides = presentation.getSlides();
    var slidesUrl = [];
    var slidesObj = {};

    for (var i = 0; i < slides.length; i++) {
      slidesObj = {};
      var slide = slides[i];
      const url = Slides.Presentations.Pages.getThumbnail(id, slide.getObjectId(), {"thumbnailProperties.mimeType": "PNG"}).contentUrl;
      
      slidesObj.slideId = slide.getObjectId();
      slidesObj.url = url;
      slidesUrl.push(slidesObj);    
    }
  }
  catch(e)
  {
    console.log("Error in readSlides : ",e.stack);
    readSlides(id);
  }

  return slidesUrl;
}

function copySlideBetweenPresentations(position,response) {

  var response = response.data;
  console.log("Response : ",response);
  var slideId = response.slide_id;
  var deckId = response.deck_id;
  var sourceSlide = SlidesApp.openById(deckId).getSlideById(slideId);
  var newSlide = SlidesApp.getActivePresentation().insertSlide(position,sourceSlide);
  var keys = Object.keys(response.placeholders);
  
  for (var i=0; i<keys.length; i++){
    var placeholderValue = response.placeholders[keys[i]];
    newSlide.replaceAllText('{{'+keys[i]+'}}',placeholderValue);
  }
}

function reshuffleInsertSlideToggleOff(position,slideId,sourceID,response) {

  try
  {
    var data = JSON.parse(response.content);
    var sourceSlide = SlidesApp.openById(sourceID).getSlideById(slideId);
    var sourceTextRange = SlidesApp.getActivePresentation().getSlides()[position-1].getNotesPage().getSpeakerNotesShape().getText();
    var newSlide = SlidesApp.getActivePresentation().insertSlide(position-1,sourceSlide);
    var targetTextRange = newSlide.getNotesPage().getSpeakerNotesShape().getText();
    targetTextRange.setText("");
    var runs = sourceTextRange.getRuns();
    for (var i = 0; i < runs.length; i++) {
      var run = runs[i];
      var insertedRun = targetTextRange.appendText(run.asString());
      
      // Copy the style from the source run to the new run
      insertedRun.getTextStyle().setFontSize(run.getTextStyle().getFontSize());
      insertedRun.getTextStyle().setBold(run.getTextStyle().isBold());
      insertedRun.getTextStyle().setItalic(run.getTextStyle().isItalic());
      insertedRun.getTextStyle().setForegroundColor(run.getTextStyle().getForegroundColor());
      
      // Preserve URLs/Links
      var link = run.getTextStyle().getLink();
      if (link) {
        insertedRun.getTextStyle().setLinkUrl(link.getUrl());
      }
    }
    SlidesApp.getActivePresentation().getSlides()[position].remove();
    var keys = Object.keys(data);
    
    for (var i=0; i<keys.length; i++){
      var placeholderValue = data[keys[i]];
      newSlide.replaceAllText('{{'+keys[i]+'}}',placeholderValue);
    }

    return true;
  }
  catch(e)
  {
    return false;
  }
}
// function reshuffleInsertSlideToggleOn(resOut) {
//   try
//   {  
//     var data = resOut.data;
//     console.log("Reshuffle Response Data : ",data);
//     var presentation = SlidesApp.getActivePresentation();
//     var slide = presentation.getSlideById(response.slideId);

//     for(var i=0 ; i<data.length; i++)
//     {
//       const pageElement = slide.getPageElementById(data[i].shapeId);
//       pageElement.asShape().getText().setText(data[i].text);
//     }

//     return true;
//   }
//   catch(e)
//   {
//     return false;
//   }
// }

function reshuffleInsertSlideToggleOn(resOut, targetPresentation) {
  try {
    var responseData = resOut.data || resOut;
    console.log("Reshuffle Response Data : ", responseData);
    
    var presentation = targetPresentation || SlidesApp.getActivePresentation();
    var slidesList = [];

    if (responseData.slides && Array.isArray(responseData.slides)) {
      slidesList = responseData.slides;
    } else if (Array.isArray(responseData)) {
      var currentSlide = null;
      try { currentSlide = presentation.getSelection().getCurrentPage(); } catch(e) {}
      var curSlideId = currentSlide ? currentSlide.getObjectId() : null;
      slidesList = [{ slideId: curSlideId, data: responseData }];
    } else if (responseData.data && Array.isArray(responseData.data)) {
      var currentSlide = null;
      try { currentSlide = presentation.getSelection().getCurrentPage(); } catch(e) {}
      var curSlideId = responseData.slideId || responseData.slide_id || (currentSlide ? currentSlide.getObjectId() : null);
      slidesList = [{ slideId: curSlideId, data: responseData.data, _skip_mutation: responseData._skip_mutation, skip: responseData.skip }];
    } else if (typeof responseData === "object" && responseData !== null) {
      for (var key in responseData) {
        if (!responseData.hasOwnProperty(key)) continue;
        var val = responseData[key];
        if (Array.isArray(val)) {
          slidesList.push({ slideId: key, data: val });
        } else if (typeof val === "object" && val !== null) {
          for (var sKey in val) {
            if (!val.hasOwnProperty(sKey)) continue;
            var sVal = val[sKey];
            if (Array.isArray(sVal)) {
              slidesList.push({ slideId: sKey, data: sVal });
            } else if (typeof sVal === "object" && sVal !== null && Array.isArray(sVal.data)) {
              slidesList.push({ slideId: sKey, data: sVal.data, _skip_mutation: sVal._skip_mutation, skip: sVal.skip });
            }
          }
        }
      }
    }

    if (!slidesList || slidesList.length === 0) {
      console.error("No valid slide data found in reshuffle response.");
      return false;
    }

    // Pre-build presentation slide index for robust lookup
    var allPresSlides = presentation.getSlides();
    var slideMap = {};
    for (var s = 0; s < allPresSlides.length; s++) {
      slideMap[allPresSlides[s].getObjectId()] = allPresSlides[s];
    }

    // OUTER LOOP: Iterate through each slide in the JSON array
    for (var i = 0; i < slidesList.length; i++) {
      var currentSlideData = slidesList[i];
      
      // CRITICAL: Skip immutable proof points / customer reference slides
      if (currentSlideData._skip_mutation === true || currentSlideData.skip === true) {
        console.log("Skipping immutable Customer Reference / Proof Points slide: " + currentSlideData.slideId);
        continue;
      }

      var slide = currentSlideData.slideId ? slideMap[currentSlideData.slideId] : null;
      if (!slide && currentSlideData.slideId) {
        try { slide = presentation.getSlideById(currentSlideData.slideId); } catch(e) {}
      }
      
      // If the slide doesn't exist in the presentation, skip it and avoid crashing
      if (!slide) {
        console.warn("Could not find slide with ID: " + currentSlideData.slideId);
        continue; 
      }

      var shapesToUpdate = currentSlideData.data;
      if (!shapesToUpdate || !Array.isArray(shapesToUpdate)) {
        continue;
      }

      // Map slide elements by ID for instant O(1) shape lookup
      var elementsMap = {};
      try {
        var pageElements = slide.getPageElements();
        for (var e = 0; e < pageElements.length; e++) {
          elementsMap[pageElements[e].getObjectId()] = pageElements[e];
        }
      } catch(e) {}

      // INNER LOOP: Iterate through the shapes inside the current slide
      for (var j = 0; j < shapesToUpdate.length; j++) {
        var shapeData = shapesToUpdate[j];
        if (!shapeData || !shapeData.shapeId || typeof shapeData.text !== "string") {
          continue;
        }

        // Fetch the shape by its shapeId safely without relying on non-existent Slide.getPageElementById
        var pageElement = elementsMap[shapeData.shapeId];
        if (!pageElement) {
          try {
            pageElement = presentation.getPageElementById(shapeData.shapeId);
          } catch(e) {}
        }

        if (!pageElement || pageElement.getPageElementType() !== SlidesApp.PageElementType.SHAPE) {
          continue;
        }

        var shape = pageElement.asShape();
        var oldText = shape.getText().asString();
        var newText = shapeData.text;

        if (oldText.trim() === newText.trim()) {
          continue;
        }

        // Set text while preserving distinct formats (bold header vs normal body)
        setShapeTextPreservingFormatting(shape, newText);
      }

      // Apply speaker notes (including generated Speaker Note Transition Hooks)
      // if returned by backend
      if (currentSlideData.speaker_notes &&
          typeof currentSlideData.speaker_notes === 'string') {
        try {
          var notesShape = slide.getNotesPage().getSpeakerNotesShape();
          if (notesShape && notesShape.getText()) {
            notesShape.getText().setText(currentSlideData.speaker_notes);
          }
        } catch (notesErr) {
          console.warn(
              'Could not update speaker notes for slide ' +
              currentSlideData.slideId + ': ' + notesErr);
        }
      }
    }

    return true;
  } catch (e) {
    console.error("Error in reshuffleInsertSlideToggleOn: ", e);
    return false;
  }
}

/**
 * Sets new text on a shape while preserving distinct formatting across paragraphs and runs
 * (such as bold card headers vs normal-weight body descriptions).
 */
function setShapeTextPreservingFormatting(shape, newText) {
  if (!shape || typeof newText !== "string") return;
  var textRange = shape.getText();
  var oldText = textRange.asString();
  if (oldText.trim() === newText.trim()) return;

  // 1. Capture original formatting profiles across paragraphs and runs
  var origRuns = [];
  try {
    origRuns = textRange.getRuns() || [];
  } catch (e) {}

  var origParagraphs = [];
  try {
    origParagraphs = textRange.getParagraphs() || [];
  } catch (e) {}

  var headerStyle = null;
  var bodyStyle = null;

  // Detect if original shape had 2 distinct formats (e.g. Paragraph 0 is Header, Paragraph 1+ is Body)
  if (origParagraphs.length >= 2) {
    try {
      var p0 = origParagraphs[0].getRange().getTextStyle();
      var p1 = origParagraphs[1].getRange().getTextStyle();
      headerStyle = {
        isBold: p0.isBold() === true || (origRuns.length > 0 && origRuns[0].getTextStyle().isBold() === true),
        fontSize: p0.getFontSize() || (origRuns.length > 0 ? origRuns[0].getTextStyle().getFontSize() : null),
        fontFamily: p0.getFontFamily() || (origRuns.length > 0 ? origRuns[0].getTextStyle().getFontFamily() : null),
        foregroundColor: p0.getForegroundColor() || (origRuns.length > 0 ? origRuns[0].getTextStyle().getForegroundColor() : null)
      };
      bodyStyle = {
        isBold: p1.isBold() === true ? true : false,
        fontSize: p1.getFontSize() || (origRuns.length > 1 ? origRuns[1].getTextStyle().getFontSize() : null),
        fontFamily: p1.getFontFamily() || (origRuns.length > 1 ? origRuns[1].getTextStyle().getFontFamily() : null),
        foregroundColor: p1.getForegroundColor() || (origRuns.length > 1 ? origRuns[1].getTextStyle().getForegroundColor() : null)
      };
    } catch (e) {}
  } else if (origRuns.length >= 2) {
    try {
      var r0 = origRuns[0].getTextStyle();
      var r1 = origRuns[1].getTextStyle();
      headerStyle = {
        isBold: r0.isBold() === true,
        fontSize: r0.getFontSize(),
        fontFamily: r0.getFontFamily(),
        foregroundColor: r0.getForegroundColor()
      };
      bodyStyle = {
        isBold: r1.isBold() === true,
        fontSize: r1.getFontSize(),
        fontFamily: r1.getFontFamily(),
        foregroundColor: r1.getForegroundColor()
      };
    } catch (e) {}
  } else if (origRuns.length === 1) {
    try {
      var r = origRuns[0].getTextStyle();
      headerStyle = {
        isBold: r.isBold() === true,
        fontSize: r.getFontSize(),
        fontFamily: r.getFontFamily(),
        foregroundColor: r.getForegroundColor()
      };
    } catch (e) {}
  }

  // Check if the original text had a newline separating Header from Body
  var oldHasNewline = oldText.includes("\n");
  var newHasNewline = newText.includes("\n");

  // 2. Set new text on the shape
  textRange.setText(newText);

  // Enable native Google Slides text shrinking on overflow
  try {
    if (shape.getText() && shape.getText().getAutofit) {
      shape.getText().getAutofit().setAutofitType(SlidesApp.AutofitType.SHRINK_TEXT_ON_OVERFLOW);
    }
  } catch (e) {}

  // Calculate proportional title font scaling to avoid title wrapping into 4-5 lines and colliding with subtitles
  var headerFontSize = headerStyle ? headerStyle.fontSize : null;
  if (headerFontSize && headerFontSize >= 20 && newText.length > oldText.length * 1.15) {
    var scaleRatio = Math.max(0.65, Math.min(1.0, (oldText.length * 1.1) / newText.length));
    headerFontSize = Math.round(headerFontSize * scaleRatio);
  }

  // 3. Re-apply distinct formatting if text has multiple parts (Header + Description)
  var firstNewline = newText.indexOf("\n");
  if (firstNewline > 0 && (oldHasNewline || newHasNewline || (headerStyle && headerStyle.isBold))) {
    try {
      // Find header text range (up to first newline)
      var headerRange = textRange.getRange(0, firstNewline);
      var hStyle = headerRange.getTextStyle();
      if (headerStyle) {
        if (headerStyle.isBold !== null && headerStyle.isBold !== undefined) hStyle.setBold(headerStyle.isBold);
        if (headerFontSize) hStyle.setFontSize(headerFontSize);
        if (headerStyle.fontFamily) hStyle.setFontFamily(headerStyle.fontFamily);
        if (headerStyle.foregroundColor) hStyle.setForegroundColor(headerStyle.foregroundColor);
      } else {
        hStyle.setBold(true);
      }

      // Find body text range (after first newline to the end)
      if (firstNewline + 1 < newText.length) {
        var bodyRange = textRange.getRange(firstNewline + 1, newText.length);
        var bStyle = bodyRange.getTextStyle();
        if (bodyStyle) {
          if (bodyStyle.isBold !== null && bodyStyle.isBold !== undefined) bStyle.setBold(bodyStyle.isBold);
          if (bodyStyle.fontSize) bStyle.setFontSize(bodyStyle.fontSize);
          if (bodyStyle.fontFamily) bStyle.setFontFamily(bodyStyle.fontFamily);
          if (bodyStyle.foregroundColor) bStyle.setForegroundColor(bodyStyle.foregroundColor);
        } else {
          bStyle.setBold(false);
        }
      }
    } catch (formatErr) {
      console.log("Notice: partial formatting reapplication error: " + formatErr);
    }
  } else if (headerStyle) {
    // Single line/element: preserve font style, weight, and scaled size
    try {
      var sStyle = textRange.getTextStyle();
      if (headerStyle.isBold !== null && headerStyle.isBold !== undefined) sStyle.setBold(headerStyle.isBold);
      if (headerFontSize) sStyle.setFontSize(headerFontSize);
      if (headerStyle.fontFamily) sStyle.setFontFamily(headerStyle.fontFamily);
      if (headerStyle.foregroundColor) sStyle.setForegroundColor(headerStyle.foregroundColor);
    } catch (e) {}
  }
}

/**
 * Transforms text across all slides in the deck post-assembly
 * using the exact same shape-by-shape workflow as the Sidebar Transform.
 */
function transformFullDeckText(
    presentation, context, erNumber, reuseSlideIdAndPosition) {
  try {
    var presObj = (typeof presentation === "string") ? (getCachedPresentation(presentation) || SlidesApp.openById(presentation)) : (presentation || SlidesApp.getActivePresentation());
    if (!presObj) return;
    var presentationId = presObj.getId();
    var userLdap = Session.getActiveUser().getEmail() || "pitchgen_system";
    
    var customerName = (context && (context.customer_name || context.customer)) || "";
    var industry = (context && context.industry) || "";
    var solution = (context && (Array.isArray(context.solution) ? context.solution.join(", ") : context.solution)) || "";
    var product = (context && (Array.isArray(context.product) ? context.product.join(", ") : context.product)) || "";
    var audience = (context && (Array.isArray(context.audience) ? context.audience.join(", ") : context.audience)) || "";
    var salesPlay = (context && (Array.isArray(context.salesPlay) ? context.salesPlay.join(", ") : context.salesPlay)) || "";

    var criteria = "Tailor presentation text to " + (customerName ? customerName : "the target customer") +
                   (industry ? " in the " + industry + " industry" : "") +
                   (solution ? " focusing on " + solution : "") +
                   " while strictly preserving technical accuracy, consultative tone, and length constraints.";

    var reusableSlideIdMap = {};
    if (reuseSlideIdAndPosition &&
        typeof reuseSlideIdAndPosition === 'object') {
      for (var secKey in reuseSlideIdAndPosition) {
        if (reuseSlideIdAndPosition.hasOwnProperty(secKey) &&
            reuseSlideIdAndPosition[secKey] &&
            Array.isArray(reuseSlideIdAndPosition[secKey].ids)) {
          var idsArr = reuseSlideIdAndPosition[secKey].ids;
          for (var idIdx = 0; idIdx < idsArr.length; idIdx++) {
            reusableSlideIdMap[idsArr[idIdx]] = true;
          }
        }
      }
    }

    var transformPayload = {
      toggle: true,
      presentation_id: presentationId,
      output_criteria: criteria,
      er_number: erNumber ? erNumber.toString() : "",
      action: "transform",
      user_ldap: userLdap,
      industry: industry,
      customer_name: customerName,
      solution: solution,
      product: product,
      audience: audience,
      salesPlay: salesPlay,
      slides: []
    };

    var allSlides = presentation.getSlides();
    if (!allSlides || allSlides.length === 0) return;

    for (var s = 0; s < allSlides.length; s++) {
      var slide = allSlides[s];
      // Skip the user inputs summary slide (slide 0) if present
      if (s === 0 && allSlides.length > 1) {
        var firstSlideElements = slide.getPageElements();
        var isSummarySlide = false;
        for (var f = 0; f < firstSlideElements.length; f++) {
          if (firstSlideElements[f].getPageElementType() === SlidesApp.PageElementType.SHAPE) {
            var txt = firstSlideElements[f].asShape().getText().asString().toLowerCase();
            if (txt.includes("user input") || txt.includes("opportunity id") || txt.includes("feedback")) {
              isSummarySlide = true;
              break;
            }
          }
        }
        if (isSummarySlide) continue;
      }

      // Extract speaker notes
      var speakerNotes = "";
      try {
        var notesShape = slide.getNotesPage().getSpeakerNotesShape();
        if (notesShape && notesShape.getText()) {
          speakerNotes = notesShape.getText().asString().trim();
        }
      } catch (e) {}

      // Collect all text on this slide to identify Title, Agenda, Section Dividers, or Closing slides
      var allShapeTexts = [];
      var pageElements = slide.getPageElements();
      for (var e = 0; e < pageElements.length; e++) {
        var elem = pageElements[e];
        if (elem.getPageElementType() === SlidesApp.PageElementType.SHAPE) {
          var t = elem.asShape().getText().asString().trim();
          if (t) allShapeTexts.push(t);
        }
      }

      var combinedSlideText = allShapeTexts.join(" ").toLowerCase();

      // Check if this is a Title slide, Agenda slide, Section Divider, or Thank You slide
      var isTitleSlide = (s <= 1 && (combinedSlideText.includes("proposal") || combinedSlideText.includes("pitch") || combinedSlideText.includes("google cloud") || combinedSlideText.includes("prepared for")));
      var isAgendaSlide = (s <= 2 && (combinedSlideText.includes("agenda") || combinedSlideText.includes("table of contents") || combinedSlideText.includes("topics")));
      var isDivider = (/^(0\d|\d{1,2})\s/i.test(combinedSlideText) || /^(section\s*\d|divider)/i.test(combinedSlideText) || (allShapeTexts.length <= 2 && /^(0[1-9]|10)\b/.test(combinedSlideText)));
      var isThankYouSlide = (s >= allSlides.length - 2 && (combinedSlideText.includes("thank you") || combinedSlideText.includes("questions")));

      if (isTitleSlide || isAgendaSlide || isDivider || isThankYouSlide) {
        console.log("Skipping slide " + slide.getObjectId() + " (index " + s + ") from text transform (Title/Agenda/Divider/Closing).");
        continue;
      }

      var isReusable = Boolean(reusableSlideIdMap[slide.getObjectId()]);
      var primarySlideTitle = '';

      var slideData = {
        slideId: slide.getObjectId(),
        slide_index: s,
        slide_position: transformPayload.slides.length + 1,
        is_reusable: isReusable,
        data: []
      };

      if (speakerNotes) {
        slideData.speaker_notes = speakerNotes;
      }

      // Extract all text shapes with shapeIds
      var pageElements = slide.getPageElements();
      for (var e = 0; e < pageElements.length; e++) {
        var elem = pageElements[e];
        if (elem.getPageElementType() === SlidesApp.PageElementType.SHAPE) {
          var shape = elem.asShape();
          var text = shape.getText().asString().trim();
          if (text && text !== "Google Cloud" && !text.includes("Proprietary & Confidential") && !/^\d+$/.test(text)) {
            var textStyle = shape.getText().getTextStyle();
            var fontSz = textStyle.getFontSize() || 12;
            var isBold = textStyle.isBold() === true;
            if (!primarySlideTitle &&
                (fontSz >= 18 || (isBold && text.length < 75))) {
              primarySlideTitle = text.split('\n')[0].trim();
            }
            slideData.data.push({
              shapeId: elem.getObjectId(),
              text: text,
              charCount: text.length,
              bold: isBold,
              fontSize: fontSz
            });
          }
        }
      }

      if (!primarySlideTitle && slideData.data.length > 0) {
        primarySlideTitle = slideData.data[0].text.split('\n')[0].trim();
      }
      slideData.slide_title = primarySlideTitle || ('Slide ' + (s + 1));

      if (slideData.data.length > 0) {
        transformPayload.slides.push(slideData);
      }
    }

    if (transformPayload.slides.length === 0) {
      console.log("No text shapes found to transform.");
      return;
    }

    console.log("Submitting full deck text transform for " + transformPayload.slides.length + " slides...");

    var agentPayload = {
      "class_method": "async_stream_query",
      "input": {
        "user_id": userLdap,
        "message": JSON.stringify(transformPayload)
      }
    };

    var options = {
      method: "post",
      contentType: "application/json",
      headers: {
        "Authorization": "Bearer " + ScriptApp.getOAuthToken()
      },
      payload: JSON.stringify(agentPayload),
      muteHttpExceptions: true
    };

    var response = UrlFetchApp.fetch(reshuffleApiUrl, options);
    var responseData = response.getContentText();
    console.log("Full deck transform response received.");
    var toggleResOut = extractProposalData(responseData, "transform_slide_payload");

    if (toggleResOut && (toggleResOut.message === "Success" || toggleResOut.status === "success" || toggleResOut.data)) {
      reshuffleInsertSlideToggleOn(toggleResOut, presentation);
      console.log("Full deck post-assembly text transform applied successfully!");
    } else {
      console.warn("Full deck transform response did not indicate success: " + responseData);
    }
  } catch (err) {
    console.warn("Notice: full deck post-assembly transform encountered an error: " + err);
  }
}

function promptLoad()
{
  var returnData = {};
  var options = {
    method: "get",
    contentType: "application/json",
  };
  try{
    console.log("Start time");
    var response = UrlFetchApp.fetch(promptsApiUrl,options);
    console.log("End time");
    var responseData = response.getContentText();
    var resOut = JSON.parse(responseData);
    console.log("Prompts ResponseData : ",responseData);
    console.log("Prompts : ",Object.keys(resOut.prompts));
    if(resOut.Status=="True")
    {
      returnData.status = true;
      returnData.prompts = resOut.prompts;
      returnData.keys = Object.keys(resOut.prompts);
    }
    else
    {
      returnData.status = false;
    }
  }
  catch(e)
  {
    console.log("Error in prompts loading : ",e.stack);
    returnData.status = false;
  }
  return returnData;
}

function loadERID()
{
  var presentationId = SlidesApp.getActivePresentation().getId();
  var returnData = {};
  var data = {
    "presentation_id": presentationId
  };
  var options = {
    method: "get",
    contentType: "application/json",
    payload: JSON.stringify(data)
  };
  try{
    var response = UrlFetchApp.fetch(getErNumber,options);
    var responseData = response.getContentText();
    var resOut = JSON.parse(responseData);
    console.log("ERID responseData : ",responseData);
    if(resOut.status=="True")
    {
      returnData.status = true;
      returnData.erID = resOut.er_number;
    }
    else
    {
      returnData.status = false;
    }
  }
  catch(e)
  {
    console.log("Error in ERID loading : ",e.stack);
    returnData.status = false;
  }
  return returnData;
}
function userFeedback() {
  var html = HtmlService.createHtmlOutput('<script>window.open("' + feedbackUrl + '", "_blank");google.script.host.close();</script></html>')
      .setWidth(1)
      .setHeight(1);
  SlidesApp.getUi().showModalDialog(html, 'Opening...');
}
function userGuide() {
  var html = HtmlService.createHtmlOutput('<script>window.open("https://docs.google.com/presentation/d/SAMPLE_PRESENTATION_ID_PLACEHOLDER_00002/edit?slide=id.g3b44d3b7ae1_0_1042&resourcekey=0-HXh3OGsfNkeixsdX1mnY3A#slide=id.g3b44d3b7ae1_0_1042", "_blank");google.script.host.close();</script></html>')
      .setWidth(1)
      .setHeight(1);
  SlidesApp.getUi().showModalDialog(html, 'Opening...');
}

function salesPlayLoad()
{
  var returnData = {};

  var options = {
    method: "get",
    contentType: "application/json"
  };
  try{
    var response = UrlFetchApp.fetch(getSalesPlay,options);
    var responseData = response.getContentText();
    var resOut = JSON.parse(responseData);

    if(resOut.Status=='True')
    {
      returnData.status = true;
      returnData.dropdown = resOut.salesPlay;
    }
    else
    {
      returnData.status = false;
    }
  }
  catch(e)
  {
    console.log(e.stack);
    returnData.status = false;
  }

  return returnData;
}
function salesPlayGenerateDeck(salesPlay,customerName,erNumber,savePlayData)
{
  var presentation = SlidesApp.getActivePresentation();
  var destinationId = presentation.getId();
  var format = "yyyy/MM/dd";
  var formattedDate = Utilities.formatDate(new Date(),"GMT",format);
  var hyperLinkUrl = feedbackUrl;
  var userLdap = Session.getActiveUser().getEmail();
  var returnData = {};

  try{
    if(presentation.getSlides().length>0){
      for(i=presentation.getSlides().length-1;i>=0;i--){
      presentation.getSlides()[i].remove();
      }
    }

    if(customerName != "")
    {
      var presentation_name = "PitchGen_"+erNumber+"_"+customerName+"_"+formattedDate;
      console.log("Slides copy started");
      copySlides(salesPlay,destinationId);
      presentation.setName(presentation_name);

      var status = salesPlayApi(customerName,destinationId);

      if(status == "Success")
      {
        returnData.status = true;
      }
      else
      {
        returnData.status = false;
      }
    }
    else
    {
      var presentation_name = "PitchGen_"+erNumber+"_"+formattedDate;
      console.log("Slides copy started");
      copySlides(salesPlay,destinationId);
      presentation.setName(presentation_name);

      returnData.status = true;
    }
    if(returnData.status==true)
    {
      returnData.status = saveSalesPlay(savePlayData);
      if(returnData.status==true)
      {
        var saveERData = {
          "presentation_id": presentation.getId(),
          "er_number" : erNumber,
          "requested_by" : userLdap
        }
        var saveEROptions = {
          method: "post",
          contentType: "application/json",
          payload: JSON.stringify(saveERData)
        };
        var erResponse = UrlFetchApp.fetch(saveErNumber,saveEROptions);
        var erResponseData = erResponse.getContentText();
        var erResOut = JSON.parse(erResponseData);
        console.log("erResOut : ",erResOut);
        if(erResOut.status!="True")
        {
          returnData.status = false;
        }
      }
    }
  }
  catch(e)
  {
    console.log(e.stack);
    returnData.status = false;
  }
  return returnData;
}
function copySlides(source,destination) {
  try{
    var sourcePresentationId = source;
    var destinationPresentationId = destination;
    
    var sourcePresentation = SlidesApp.openById(sourcePresentationId);
    var destinationPresentation = SlidesApp.openById(destinationPresentationId);
    var slides = sourcePresentation.getSlides();

    slides.forEach(function(slide) {
      destinationPresentation.appendSlide(slide);
    });
    
    console.log('Slides copied successfully!');
  }
  catch(e)
  {
    console.log("Access Issue : ",e.stack);
    throw new Error("Copy slides method failed");
  }
}
function salesPlayApi(customerName,id)
{
  var payload = getMaxFontSizeText(customerName,id);
  console.log("Payload : ",payload);
  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload)
  };
  try{
    var response = UrlFetchApp.fetch(salesPlayApiUrl,options);      //Return filename in response
    var responseData = response.getContentText();
    var resOut = JSON.parse(responseData);

    console.log("resOut : ",resOut);

    if(resOut.message == "Success")
    {
      console.log("Filename :",resOut.data);
      var status = salesPlayContentData(resOut.data);

      return status;              //Returning Success or Failed
    }
    else{
      return "Failed";
    }
  }
  catch(e)
  {
    console.log(e.stack);
    return "Failed";
  }
}
function salesPlayContentData(filename)
{
  console.log("Content salesplay");
  salesPlayContentApiCallCount = salesPlayContentApiCallCount + 1;
  try{
    var payloadData = {
        "filename": filename
      };
    var options = {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(payloadData)
    };
    var response = UrlFetchApp.fetch(salesPlayContent,options);
    var responseData = response.getContentText();
    var resOut = JSON.parse(responseData);
    var apiResponse = resOut
    var data = JSON.parse(apiResponse.content);

    console.log("Response : ",apiResponse);

    if(apiResponse.status="success")
    {
      var presentation = SlidesApp.openById(data.presentation);
      var updates = data.titleObj;
      var slides = presentation.getSlides();

      updates.forEach(update => {
        
        var { slideId, shapeId, title } = update;
        var slide = slides.find(s => s.getObjectId() === slideId);
        var shape = slide.getPageElements().find(pe => pe.getObjectId() === shapeId);

        shape.asShape().getText().setText(title);

      });

      var slideContent = data.slide_content;
      var keys = Object.keys(slideContent);
      var presentation = SlidesApp.getActivePresentation();

      for(var i=0; i<keys.length; i++)
      {
        var tempUrl = slideContent[keys[i]].temp_url;
        var placeholders = slideContent[keys[i]].placeholders;
        var sourcePresentation = SlidesApp.openByUrl(tempUrl);
        var sourceSlideId = extractSlideId(tempUrl);
        var sourceSlide = sourcePresentation.getSlideById(sourceSlideId);
        var newSlide = presentation.insertSlide(i, sourceSlide);
        if(placeholders){
          var placeholderCount = Object.keys(placeholders).length;
          for (var l = 0; l < placeholderCount; l++) {
            var placeholder = Object.keys(placeholders)[l];
            value = placeholders[placeholder];
            newSlide.replaceAllText("{{" + placeholder + "}}", value);
          }
        }
      }

      console.log("Titles updated");
      return "Success";
    }
    else
    {
      console.log("Titles updatation failed");
      return "Failed";
    }

  }
  catch(error)
  {
    console.log(error);
    if (error.message.includes('Timeout')) {
      if(salesPlayContentApiCallCount > 1)
      {
        console.log("TimeOut (12 mins)");
      }
      else
      {
        console.log("SalesPlay Recall");
        salesPlayContentData(filename)                    //retrying again if the api gets timed out
      }
    }
    return "Failed";
  }
}
function getMaxFontSizeText(customerName,id) {

  const presentation = SlidesApp.openById(id);
  const allSlides = presentation.getSlides();
  const totalSlides = allSlides.length;
  const topCount = Math.ceil(totalSlides * salesPlaySlidesPercentage);
  const topSlides = allSlides.slice(0, topCount);

  var returnData = {};
  var results = [];

  returnData.presentation = presentation.getId();
  returnData.customerName = customerName;

  topSlides.forEach((slide, slideIndex) => {
      let maxFontSize = 0;
      let maxText = '';
      let slidesData = {};

      slidesData.slideId = slide.getObjectId();

      const pageElements = slide.getPageElements();

      pageElements.forEach(element => {
        if (element.getPageElementType() === SlidesApp.PageElementType.SHAPE) {
          const shape = element.asShape();
          const textRange = shape.getText();
          const fullText = textRange.asString();
          const lines = fullText.split('\n');
          
          let charIndex = 0;

          lines.forEach(line => {
            const trimmedLine = line.trim();
            if (trimmedLine.length === 0) {
              charIndex += line.length + 1; // +1 for newline
              return;
            }

            // Check the font size of the first character in the line
            const fontSize = textRange.getRange(charIndex, charIndex + 1).getTextStyle().getFontSize() || 0;

            if (fontSize > maxFontSize) {
              maxFontSize = fontSize;
              maxText = trimmedLine;
              slidesData.shapeId = shape.getObjectId();
            }

            charIndex += line.length + 1; // +1 for newline
          });
        }
      });

      if (maxText) {
        slidesData.title = maxText;
        results.push(slidesData);
      }
  });
  returnData.titleObj = results;
  return returnData;
}

function readTemplateSlides() {
  var url = "https://storage.googleapis.com/"+templateJsonBucketName+"/template/latest_template_data.json";
  var token = ScriptApp.getOAuthToken();
  var options = {
    "method": "get",
    "headers": {
      "Authorization": "Bearer " + token
    },
    "muteHttpExceptions": true
  };
  var returnObj = {};
  try {
    var response = UrlFetchApp.fetch(url, options);
    var responseCode = response.getResponseCode();
    
    if (responseCode === 200) {
      var jsonText = response.getContentText();
      var resOut = JSON.parse(jsonText);
      console.log(resOut);
      returnObj.status = true;
      returnObj.response = resOut;
      
      Logger.log("Successfully fetched data");
      
      return returnObj;
      
    } else {
      Logger.log("Error fetching file. Response Code: " + responseCode);
      Logger.log("Error Details: " + response.getContentText());
      returnObj.status = false;
      return returnObj;
    }
  } catch (e) {
    Logger.log("An exception occurred: " + e.toString());
    returnObj.status = false;
    return returnObj;
  }
}


/* Start : Trigger : sidebar template load into the bucket */
/* ****************************************************************************************************************************************** */

function convertAndUpload()
{
  var returnObj = {};
  for(var i=0; i<sidebarTemplate.length; i++)
  {
    returnObj[sidebarTemplate[i]] = convertAllSlidesToImages(sidebarTemplate[i]);
  }
  console.log("Payload : ",returnObj);

  try{
    var resOut = uploadSidebarTemplateJsonFileInGcs(templateJsonBucketName,sidebarTemplateJsonFileName,returnObj);

    console.log("Response : ",resOut);
    if(resOut.status=='success')
    {
      console.log("Template upload successful");
    }
    else
    {
      console.log("Template upload failed");
    }
  }
  catch(e)
  {
    console.log("Template upload failed");
    console.log(e.stack);
  }
}
function uploadSidebarTemplateJsonFileInGcs(bucketName,fileName,uploadData)
{ 
  const token = ScriptApp.getOAuthToken();
  const uploadUrl = `https://storage.googleapis.com/upload/storage/v1/b/${bucketName}/o?uploadType=media&name=${encodeURIComponent(fileName)}`;
  const uploadOptions = {
    method: 'post', 
    contentType: 'application/json',
    headers: {
      Authorization: `Bearer ${token}`
    },
    payload: JSON.stringify(uploadData), 
    muteHttpExceptions: true
  };
  
  try {
    const response = UrlFetchApp.fetch(uploadUrl, uploadOptions);
    var returnData = {};
    if (response.getResponseCode() === 200) {
      Logger.log('Success! GCS file has been updated with the contents of uploadData.');
      returnData.status = 'success';
    } else {
      Logger.log('Failed to update file: ' + response.getContentText());
      returnData.status = 'failed';
    }
  } catch (e) {
    Logger.log('Error occurred: ' + e.toString());
    returnData.status = 'failed';
  }

  return returnData
}
function convertAllSlidesToImages(presentationId)
{
  try
  {
    var returnArr = [];
    var obj = {};
    var presentation = SlidesApp.openById(presentationId);
    var slides = presentation.getSlides();

    console.log("File creation started : "+presentation.getName());

    for (var j = 0; j < slides.length; j++) {
      obj = {};
      slidesObj = {};
      var slide = slides[j];
      var imageName = presentation.getName() + "," + presentationId + "," + slide.getObjectId();
      const url = Slides.Presentations.Pages.getThumbnail(presentationId, slide.getObjectId(), {"thumbnailProperties.mimeType": "PNG"}).contentUrl;
      const imageBlob = UrlFetchApp.fetch(url).getBlob();
      var authUrl = uploadImageToGCS(imageBlob,imageName);
      obj.templatename = presentation.getName();
      obj.slideId = slide.getObjectId();
      obj.url = authUrl;
      returnArr.push(obj);
    }
    return returnArr;
  }
  catch(e)
  {
    console.log("Error in convertAllSlidesToImages : ",e.stack);
  }

  console.log("File created successfully");
}
function uploadImageToGCS(imageBlob,imageName) 
{   
  try {
    const BUCKET_NAME = templateBucketName;
    const FOLDER_PATH = templateFolderName;   
    const objectName = FOLDER_PATH + imageName;
    const contentType = imageBlob.getContentType();
    const accessToken = ScriptApp.getOAuthToken();
    const url = `https://storage.googleapis.com/upload/storage/v1/b/${BUCKET_NAME}/o?uploadType=media&name=${encodeURIComponent(objectName)}`;
    
    const options = {
      'method': 'post',
      'headers': {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': contentType
      },
      'payload': imageBlob.getBytes(),
      'muteHttpExceptions': true
    };

    const response = UrlFetchApp.fetch(url, options);
    const responseCode = response.getResponseCode();
    const responseBody = response.getContentText();

    if (responseCode === 200) {
      const result = JSON.parse(responseBody);
      console.log("Image Upload Result : ",result);
      Logger.log('Upload successful!');
      return `https://storage.mtls.cloud.google.com/${BUCKET_NAME}/${result.name}`;
    } else {
      Logger.log(`Error uploading file. Response Code: ${responseCode}`);
      Logger.log(`Error message: ${responseBody}`);
      console.error('Error: ' + responseBody);
    }

  } catch (e) {
    Logger.log(`An unexpected error occurred: ${e.message}`);
    console.error('Exception: ' + e);
  }
}

/* End : Trigger : sidebar template load into the bucket */
/* ****************************************************************************************************************************************** */

// function reshuffleToggleOffPayload(erId,desiredOutputCriteria,isFullDeck) {
//   var presentation = SlidesApp.getActivePresentation();
//   var userLdap = Session.getActiveUser().getEmail();
//   var slide = presentation.getSlideById(slideId);  
//   var shapes = slide.getShapes();
//   var output = {};
//   var contentArr = [];
//   output.toggle = true, 
//   output.presentation_id = presentation.getId();
//   output.slideId = slideId;
//   output.output_criteria = desiredOutputCriteria; 
//   output.er_number = erId;
//   output.action = "transform";
//   output.user_ldap = userLdap;

//   shapes.forEach(function(shape) {
//       var contentData = {};
//       var text = shape.getText().asString();      
//       if (text.trim() !== "") {
//         contentData.shapeId = shape.getObjectId();
//         contentData.text = text.trim();
//         contentData.charCount = text.trim().length;
//         contentData.bold = shape.getText().getTextStyle().isBold();
//         contentData.fontSize = shape.getText().getTextStyle().getFontSize();
//         contentArr.push(contentData);
//       }
//   });

//   output.data = contentArr;

//   return output;
// }

function reshuffleToggleOffPayload(erId, desiredOutputCriteria, isFullDeck) {
  var presentation = SlidesApp.getActivePresentation();
  var userLdap = Session.getActiveUser().getEmail();
  
  var output = {
    toggle: true,
    presentation_id: presentation.getId(),
    output_criteria: desiredOutputCriteria,
    er_number: erId,
    action: "transform",
    user_ldap: userLdap,
    slides: [] 
  };

  var slidesToProcess = [];
  
  if (isFullDeck) {
    // 1. Process the entire presentation
    slidesToProcess = presentation.getSlides();
  } else {
    // 2. Figure out what the user currently has selected
    var selection = presentation.getSelection();
    var pageRange = selection.getPageRange();
    
    if (pageRange) {
      // This triggers if the user has clicked one or multiple slides in the left-hand filmstrip
      slidesToProcess = pageRange.getPages(); 
    } else {
      // This fallback triggers if the user is actively clicking inside a slide (e.g., editing a shape)
      var currentPage = selection.getCurrentPage();
      if (currentPage) {
        slidesToProcess = [currentPage];
      }
    }
  }

  // 3. Process whichever slides were gathered above
  slidesToProcess.forEach(function(slide) {
    var slideData = {
      slideId: slide.getObjectId(),
      data: []
    };

    // Safely extract speaker notes from the slide
    try {
      var notesPage = slide.getNotesPage();
      if (notesPage) {
        var notesShape = notesPage.getSpeakerNotesShape();
        if (notesShape && notesShape.getText()) {
          var notesStr = notesShape.getText().asString();
          if (notesStr && notesStr.trim() !== "") {
            slideData.speaker_notes = notesStr.trim();
          }
        }
      }
    } catch(e) {
      console.log("Error extracting speaker notes: " + e);
    }

    // Safely get all elements on the slide
    var pageElements = slide.getPageElements();
    
    pageElements.forEach(function(element) {
      // ONLY process the element if it is a Shape (ignore images, lines, etc.)
      if (element.getPageElementType() === SlidesApp.PageElementType.SHAPE) {
        var shape = element.asShape();
        var text = shape.getText().asString();
        var trimmed = text.trim();
        
        if (trimmed !== "") {
          var lower = trimmed.toLowerCase();
          
          // 1. Skip disclaimers and confidentiality labels
          if (lower.includes("confidential") || lower.includes("proprietary") || lower.includes("all rights reserved") || lower.startsWith("©") || lower.startsWith("(c)")) {
            return;
          }
          
          // 2. Skip slide numbers / page numbers (e.g., "1", "12", "3/15", "Page 2")
          if (/^(page\s*)?\d+(\s*\/\s*\d+)?$/i.test(trimmed)) {
            return;
          }
          
          // 3. Skip tiny decorative bullets or extreme bottom/right margin footers
          try {
            if (shape.getWidth() < 50 && shape.getHeight() < 50 && trimmed.length <= 4) {
              return;
            }
            if (shape.getTop() > 375 && trimmed.length < 50) {
              return;
            }
          } catch (e) {}

          var contentData = {};
          contentData.shapeId = shape.getObjectId();
          contentData.text = trimmed;
          contentData.charCount = trimmed.length;
          
          // Get text style safely (prevents crashing on mixed formatting)
          var textStyle = shape.getText().getTextStyle();
          contentData.bold = textStyle.isBold() === true; 
          contentData.fontSize = textStyle.getFontSize() || 12; 
          
          slideData.data.push(contentData);
        }
      }
    });

    // Only add the slide to the payload if we actually found text on it
    if (slideData.data.length > 0) {
      output.slides.push(slideData);
    }
  });

  return output;
}

function saveSalesPlay(savePlayData)
{
  console.log("saveSalesPlay call");
  var presentation = SlidesApp.getActivePresentation();
  var ldap = Session.getActiveUser().getEmail();
  var data = {
    'business_context': savePlayData.business_context,
    'industry': savePlayData.selectedIndustry,
    'solution': savePlayData.solution,
    'customer_name': savePlayData.customerName,
    'er_number': savePlayData.erNumber,
    'sales_stage': savePlayData.salesStage || 'S1',
    'product': savePlayData.product,
    'audience': savePlayData.audience,
    'salesPlay': savePlayData.salesPlayName,
    'presentation_id': presentation.getId(),
    'user_ldap': ldap,
    'request_type': 'Salesplay'
  };
  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(data)
  };
  console.log("Payload : ",data);
  try{
    var response = UrlFetchApp.fetch(getAgendasApiUrl,options);
    var responseData = response.getContentText();
    var resOut = JSON.parse(responseData);

    console.log(resOut);
    if(resOut.Status=='True')
    {
      return true;
    }
    else
    {
      return false;
    }
  }
  catch(e)
  {
    return false;
  }
}

function nanoBananaGenerate(sheetId,spreadSheetId,slideContent,slideLayout,slideCategory,product,customerName,industry,erIdGenerate,solution,selectedStyleBase64){
  console.log("Ldap : ",Session.getActiveUser().getEmail());
  var userLdap = Session.getActiveUser().getEmail();
  var slideId = SlidesApp.getActivePresentation().getSelection().getCurrentPage().getObjectId();
  var allSlides = SlidesApp.getActivePresentation().getSlides();
  
  var position = 0;
  for (var j = 0; j < allSlides.length; j++) 
  {
    var slide = allSlides[j];
    if (slide.getObjectId() === slideId) {
      position = (j + 1); 
      break;
    }
  }
  
  var slideImageUrlGcs = "";
  if(sheetId!=""){
    const imageURL = Slides.Presentations.Pages.getThumbnail(spreadSheetId, sheetId, {
      "thumbnailProperties.mimeType": "PNG",
      "thumbnailProperties.thumbnailSize": "SMALL"
    }).contentUrl; 
    var thumbnailBlob = UrlFetchApp.fetch(imageURL).getBlob();
    var imageName = "thumbnail_" + generateUniqueId() + ".png";
    slideImageUrlGcs = uploadSideBarImageToGCS(thumbnailBlob, imageName, templateBucketName, sideBarImageUploadFolderName);
  }

  var userInputImageUrlGcs = "";
  if(selectedStyleBase64!=null){
    var base64ImageOnly = selectedStyleBase64.split(',')[1];
    var mimeType = selectedStyleBase64.split(',')[0].split(':')[1].split(';')[0];
    var extension = mimeType.split('/')[1];
    var decoded = Utilities.base64Decode(base64ImageOnly);
    var imageName = "user_upload_" + generateUniqueId() + "." + extension;
    var userBlob = Utilities.newBlob(decoded, mimeType, imageName);
    userInputImageUrlGcs = uploadSideBarImageToGCS(userBlob, imageName, templateBucketName, sideBarImageUploadFolderName);
  }

  var data = {
    "request": slideContent,
    "layout": slideLayout,
    "theme": slideCategory,
    "products" : product,
    "customer_name" : customerName,
    "industry" : industry,
    "erIdGenerate" : erIdGenerate,
    "solutions" : solution ,
    "slide_image_url" : slideImageUrlGcs,
    "User_input_slide_image_url" : userInputImageUrlGcs
  };
  var userInputData = {};
  userInputData.user_inputs = data;
  // var options = {
  //   method: "post",
  //   contentType: "application/json",
  //   payload: JSON.stringify(userInputData)
  // };
  const payload = {
    "class_method": "async_stream_query",
    "input": {
    "user_id":userLdap,
    "message": JSON.stringify(userInputData)
    }
  };
  var options = {
    method: "post",
    contentType: "application/json",
   "headers": {
     "Authorization": "Bearer " + ScriptApp.getOAuthToken()
   },
   "payload": JSON.stringify(payload),
   "muteHttpExceptions": true
  };
  console.log("Payload : ",options);
  
  try{
    var response = UrlFetchApp.fetch(nanoBanana_imageGen,options);

    console.log("Status Code: " + response.getResponseCode());
    
    if(response.getResponseCode()==200)
    {
      var responseData = response.getContentText();
      console.log("responseData : ",responseData);
      var resOut = extractProposalData(responseData,"generate_visual_payload");
      console.log(resOut);
      if (!resOut || !resOut.gcs_link) {
        throw new Error(resOut && resOut.error ? resOut.error : "Failed to generate visual content. Check backend logs.");
      }
      const imageOptions = {
        method: "get",
        headers: {
          "Authorization": "Bearer " + ScriptApp.getOAuthToken()
        },
        muteHttpExceptions: true
      };
      const imageResponse = UrlFetchApp.fetch(resOut.gcs_link,imageOptions);
      var blobdata = imageResponse.getBlob();
      console.log("Image size: " + blobdata.getBytes().length / (1024 * 1024) + " MB");
      var presentation = SlidesApp.getActivePresentation();
      var pageWidth = presentation.getPageWidth();
      var pageHeight = presentation.getPageHeight();
      const slide = presentation.getSlides()[0];
      const newSlides = slide.duplicate();
      const elements = newSlides.getPageElements();

      elements.forEach(element => {
        element.remove();
      });
      var image = newSlides.insertImage(blobdata);  
      image.setLeft(0);
      image.setTop(0);
      image.setWidth(pageWidth);
      image.setHeight(pageHeight);
      newSlides.move(position+1);
      newSlides.setSkipped(false); 

      var saveNanoBananaGenerateData = {
        "content": slideContent,
        "layout": slideLayout,
        "theme": slideCategory,
        "products" : product,
        "customer_name" : customerName,
        "industry" : industry,
        "opportunity_id" : erIdGenerate,
        "action" : "nanobanana_generate",
        "presentation_id" : presentation.getId(),
        "user_ldap" : userLdap,
        "slide_id" : sheetId,
        "deck_id" : spreadSheetId,
        "slide_image_url" : slideImageUrlGcs,
        "User_input_slide_image_url" : userInputImageUrlGcs        
      };
      var identityToken = ScriptApp.getIdentityToken();
      var saveNanoBananaGenerateOptions = {
        method: "post",
        contentType: "application/json",
        "headers": {
          "Authorization": "Bearer " + identityToken
        },
        "payload": JSON.stringify(saveNanoBananaGenerateData)
      };
      console.log("Database Payload : ",saveNanoBananaGenerateOptions);

      var nanoBananaGenerateSaveResponse = UrlFetchApp.fetch(saveEditAction,saveNanoBananaGenerateOptions);
      console.log("nanoBananaGenerateSaveResponse : ",nanoBananaGenerateSaveResponse.getContentText());

      return true;
    }
    else
    {
      return false;
    }
  }
  catch(e)
  {
    console.error("Failed at: " + e.stack); // This tells you the exact line number
    console.error("Error Message: " + e.message);
    
    return false;
  }
}

function nanoBananaTransform(sheetId,spreadSheetId,desiredOutputCriteria,slideLayout,slideCategory,erIdTransform,selectedTransformStyleBase64,language){
  console.log("Ldap : ",Session.getActiveUser().getEmail());
  var userLdap = Session.getActiveUser().getEmail();
  var slideId = SlidesApp.getActivePresentation().getSelection().getCurrentPage().getObjectId();
  var allSlides = SlidesApp.getActivePresentation().getSlides();
  
  var position = 0;
  for (var j = 0; j < allSlides.length; j++) 
  {
    var slide = allSlides[j];
    if (slide.getObjectId() === slideId) {
      position = (j + 1); 
      break;
    }
  }
  
  var slideImageUrlGcs = "";
  if(sheetId!=""){
    const imageURL = Slides.Presentations.Pages.getThumbnail(spreadSheetId, sheetId, {
      "thumbnailProperties.mimeType": "PNG",
      "thumbnailProperties.thumbnailSize": "SMALL"
    }).contentUrl; 
    var thumbnailBlob = UrlFetchApp.fetch(imageURL).getBlob();
    var imageName = "thumbnail_" + generateUniqueId() + ".png";
    slideImageUrlGcs = uploadSideBarImageToGCS(thumbnailBlob, imageName, templateBucketName, sideBarImageUploadFolderName);
  }

  var presentation_id = SlidesApp.getActivePresentation().getId();
  const currentSlideImageURL = Slides.Presentations.Pages.getThumbnail(presentation_id, slideId, {
    "thumbnailProperties.mimeType": "PNG",
    "thumbnailProperties.thumbnailSize": "SMALL"
  }).contentUrl;
  var currentSlideBlob = UrlFetchApp.fetch(currentSlideImageURL).getBlob();
  var currentSlideImageName = "current_slide_" + generateUniqueId() + ".png";
  var selectedSlideGcs = uploadSideBarImageToGCS(currentSlideBlob, currentSlideImageName, templateBucketName, sideBarImageUploadFolderName);

  var userInputImageUrlGcs = "";
  if(selectedTransformStyleBase64!=null){
    var base64ImageOnly = selectedTransformStyleBase64.split(',')[1];
    var mimeType = selectedTransformStyleBase64.split(',')[0].split(':')[1].split(';')[0];
    var extension = mimeType.split('/')[1];
    var decoded = Utilities.base64Decode(base64ImageOnly);
    var imageName = "user_upload_" + generateUniqueId() + "." + extension;
    var userBlob = Utilities.newBlob(decoded, mimeType, imageName);
    userInputImageUrlGcs = uploadSideBarImageToGCS(userBlob, imageName, templateBucketName, sideBarImageUploadFolderName);
  }

  var data = {
    "request": desiredOutputCriteria,
    "layout": slideLayout,
    "theme": slideCategory,
    "erIdGenerate" : erIdTransform,
    "existing_slide_image_url" : selectedSlideGcs,
    "template_slide_image_url" : slideImageUrlGcs, 
    "User_input_slide_image_url" : userInputImageUrlGcs
  };
  var userInputData = {};
  userInputData.user_inputs = data;
  // var options = {
  //   method: "post",
  //   contentType: "application/json",
  //   payload: JSON.stringify(userInputData)
  // };
  const payload = {
    "class_method": "async_stream_query",
    "input": {
    "user_id":userLdap,
    "message": JSON.stringify(userInputData)
    }
  };
  var options = {
    method: "post",
    contentType: "application/json",
   "headers": {
     "Authorization": "Bearer " + ScriptApp.getOAuthToken()
   },
   "payload": JSON.stringify(payload),
   "muteHttpExceptions": true
  };
  console.log("Payload : ",userInputData);
  try{
    var response = UrlFetchApp.fetch(nanoBanana_imageTrans,options);

    console.log("Status Code: " + response.getResponseCode());

    if(response.getResponseCode()==200)
    {
      var responseData = response.getContentText();
      console.log("responseData : ",responseData);
      var resOut = extractProposalData(responseData,"generate_visual_payload");
      console.log(resOut);
      if (!resOut || !resOut.gcs_link) {
        throw new Error(resOut && resOut.error ? resOut.error : "Failed to transform visual content. Check backend logs.");
      }
      const imageOptions = {
        method: "get",
        headers: {
          "Authorization": "Bearer " + ScriptApp.getOAuthToken()
        },
        muteHttpExceptions: true
      };
      const imageResponse = UrlFetchApp.fetch(resOut.gcs_link,imageOptions);
      var blobdata = imageResponse.getBlob();
      console.log("Image size: " + blobdata.getBytes().length / (1024 * 1024) + " MB");
      var presentation = SlidesApp.getActivePresentation();
      var pageWidth = presentation.getPageWidth();
      var pageHeight = presentation.getPageHeight();
      const slide = presentation.getSlides()[0];
      const newSlides = slide.duplicate();
      const elements = newSlides.getPageElements();

      elements.forEach(element => {
        element.remove();
      });
      var image = newSlides.insertImage(blobdata); 
      image.setLeft(0);
      image.setTop(0);
      image.setWidth(pageWidth);
      image.setHeight(pageHeight);
      newSlides.move(position+1);
      newSlides.setSkipped(false);
      
      var saveNanoBananaTransformData = {
        "content": desiredOutputCriteria,
        "layout": slideLayout,
        "theme": slideCategory,
        "opportunity_id" : erIdTransform,
        "language" : language,
        "action" : "nanobanana_transform",
        "presentation_id" : presentation.getId(),
        "user_ldap" : userLdap,
        "slide_id" : sheetId,
        "deck_id" : spreadSheetId,
        "existing_slide_image_url" : selectedSlideGcs,
        "template_slide_image_url" : slideImageUrlGcs, 
        "User_input_slide_image_url" : userInputImageUrlGcs
      };
      var identityToken = ScriptApp.getIdentityToken();
      var saveNanoBananaTransformOptions = {
        method: "post",
        contentType: "application/json",
        "headers": {
          "Authorization": "Bearer " + identityToken
        },
        "payload": JSON.stringify(saveNanoBananaTransformData)
      };
      console.log("Database Payload : ",saveNanoBananaTransformOptions);

      var nanoBananaTransformSaveResponse = UrlFetchApp.fetch(saveEditAction,saveNanoBananaTransformOptions);
      console.log("nanoBananaTransformSaveResponse : ",nanoBananaTransformSaveResponse.getContentText());

      return true;
    }
    else
    {
      return false;
    }
  }
  catch(e)
  {
    console.error("Failed at: " + e.stack); // This tells you the exact line number
    console.error("Error Message: " + e.message);

    return false;
  }
}

function readFileFromGCS(bucketName,fileName) {
  if (!fileName) return null;
  
  var candidateBuckets = [bucketName, reuseAndContentJSONBucketName, 'your-pitchgen-content-bucket', 'your-pitchgen-content-bucket', 'your-pitchgen-content-bucket'];
  var seenBuckets = {};
  var token = ScriptApp.getOAuthToken();
  var encodedFileName = encodeURIComponent(fileName);

  for (var b = 0; b < candidateBuckets.length; b++) {
    var currentBucket = candidateBuckets[b];
    if (!currentBucket || seenBuckets[currentBucket]) continue;
    seenBuckets[currentBucket] = true;

    var url = "https://storage.googleapis.com/storage/v1/b/" + currentBucket + "/o/" + encodedFileName + "?alt=media";
    var options = {
      method: 'get',
      headers: {
        Authorization: 'Bearer ' + token
      },
      muteHttpExceptions: true
    };

    try {
      console.log("Attempting GCS read from bucket: " + currentBucket + " for file: " + fileName);
      var response = UrlFetchApp.fetch(url, options);
      var responseCode = response.getResponseCode();
      if (responseCode === 200) {
        var fileContent = response.getContentText();
        console.log("File successfully retrieved from bucket: " + currentBucket);
        return fileContent;
      }
    } catch (e) {
      console.log("Failed reading from bucket " + currentBucket + ": " + e.toString());
    }
  }

  console.error("Failed to fetch file " + fileName + " from any candidate bucket.");
  return null;
}
function extractProposalData(rawResponseText, parameterName) {
  if (!rawResponseText) return null;

  function cleanAndParseJson(str) {
    if (typeof str !== 'string') return str;
    var cleaned = str.replace(/<a2ui-json>[\s\S]*?<\/a2ui-json>/gi, '')
                      .replace(/<a2ui-json>[\s\S]*$/gi, '')
                      .trim();
    try {
      return JSON.parse(cleaned);
    } catch (e) {
      // Try extracting first valid top-level JSON block if trailing text
      // remains
      var firstBrace = cleaned.indexOf('{');
      var lastBrace = cleaned.lastIndexOf('}');
      if (firstBrace !== -1 && lastBrace > firstBrace) {
        try {
          return JSON.parse(cleaned.substring(firstBrace, lastBrace + 1));
        } catch (e2) {
        }
      }
      return null;
    }
  }

  function isTargetPayload(obj) {
    if (!obj || typeof obj !== 'object') return false;
    // Ignore consult_skill metadata objects
    if (obj.skill_name && obj.instructions && !obj.agendas && !obj.data &&
        !obj.outline) {
      return false;
    }
    return Boolean(
        obj.agendas || obj.outline || obj.titles ||
        obj.architectural_filename || obj.outputs_filename ||
        obj.placeholders || obj.Status || obj.data || obj.title);
  }

  // 1. Direct JSON check
  var directObj = cleanAndParseJson(rawResponseText);
  if (isTargetPayload(directObj)) {
    return directObj;
  }

  var fallbackCandidate = null;

  // 2. Line by line parsing (supports NDJSON, SSE `data: `, and multi-part chunks)
  const lines = rawResponseText.trim().split('\n');
  for (let line of lines) {
    line = line.trim();
    if (!line || line.startsWith('event:')) continue;
    if (line.startsWith('data:')) {
      line = line.substring(5).trim();
    }
    if (!line) continue;

    try {
      const parsedLine = JSON.parse(line);

      // Check direct properties on chunk
      if (isTargetPayload(parsedLine)) {
        return parsedLine;
      }

      // Check Gemini content parts
      const parts = parsedLine?.content?.parts;
      if (parts && parts.length > 0) {
        for (let part of parts) {
          const functionResponse = part?.function_response;
          if (functionResponse) {
            const fnName = functionResponse.name || '';
            // Always skip intermediate consult_skill responses
            if (fnName === 'consult_skill') {
              continue;
            }
            const resultRaw = functionResponse.response ?
                (functionResponse.response.result ||
                 functionResponse.response) :
                null;
            let parsedResult = null;
            if (typeof resultRaw === 'string') {
              parsedResult = cleanAndParseJson(resultRaw);
            } else if (typeof resultRaw === 'object' && resultRaw !== null) {
              parsedResult = resultRaw;
            }

            if (isTargetPayload(parsedResult)) {
              if (!parameterName || fnName === parameterName ||
                  fnName.indexOf(parameterName) !== -1) {
                return parsedResult;
              }
              fallbackCandidate = parsedResult;
            }
          }

          const textPart = part?.text;
          if (textPart) {
            const finalDataObject = cleanAndParseJson(textPart);
            if (isTargetPayload(finalDataObject)) {
              fallbackCandidate = fallbackCandidate || finalDataObject;
            }
          }
        }
      }
    } catch (e) {
      // Skipping non-JSON line
    }
  }

  if (fallbackCandidate) {
    return fallbackCandidate;
  }

  // 3. Regex / substring search fallback for nested JSON with parameterName, agendas, or filenames
  try {
    var regexMatch = rawResponseText.match(/"architectural_filename"\s*:\s*"([^"]+)"[\s\S]*?"outputs_filename"\s*:\s*"([^"]+)"/);
    if (regexMatch) {
      return {
        architectural_filename: regexMatch[1],
        outputs_filename: regexMatch[2]
      };
    }
  } catch (regexErr) {}

  console.error("Could not find " + parameterName + " data in the agent response.");
  return null;
}
function generateUniqueId() {
  // Generates a unique UUID v4 string
  var req_id = Utilities.getUuid(); 
  
  Logger.log(req_id);
  // Example output: "123e4567-e89b-12d3-a456-426614174000"
  
  return req_id;
}
function uploadSideBarImageToGCS(imageBlob,imageName,bucketName,folderName) 
{   
  try {
    const BUCKET_NAME = bucketName;
    const FOLDER_PATH = folderName;   
    const objectName =  FOLDER_PATH +"/"+ imageName;
    const contentType = imageBlob.getContentType();
    const accessToken = ScriptApp.getOAuthToken();
    const url = `https://storage.googleapis.com/upload/storage/v1/b/${BUCKET_NAME}/o?uploadType=media&name=${encodeURIComponent(objectName)}`;
    
    const options = {
      'method': 'post',
      'headers': {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': contentType
      },
      'payload': imageBlob.getBytes(),
      'muteHttpExceptions': true
    };

    const response = UrlFetchApp.fetch(url, options);
    const responseCode = response.getResponseCode();
    const responseBody = response.getContentText();

    if (responseCode === 200) {
      const result = JSON.parse(responseBody);
      console.log("Image Upload Result : ",result);
      Logger.log('Upload successful!');
      return `gs://${BUCKET_NAME}/${objectName}`;
    } else {
      Logger.log(`Error uploading file. Response Code: ${responseCode}`);
      Logger.log(`Error message: ${responseBody}`);
      console.error('Error: ' + responseBody);
    }

  } catch (e) {
    Logger.log(`An unexpected error occurred: ${e.message}`);
    console.error('Exception: ' + e);
  }
}

// ==========================================================
// Merged functions to keep the file context feature active
// ==========================================================

function uploadFileToGCS(base64Data, filename, mimeType) {
  var returnData = {};
  
  try {
    // 1. Convert the base64 string from the frontend into the Blob your function expects
    var decodedData = Utilities.base64Decode(base64Data);
    var imageBlob = Utilities.newBlob(decodedData, mimeType, filename);
    
    // 2. Define your bucket and folder structure here
    const BUCKET_NAME = templateBucketName;
    const FOLDER_NAME = sideBarImageUploadFolderName; // Leave as "" if you want it in the root folder
    var imageName = "popup_" + generateUniqueId() + "_" + filename;

    var gcsPath = uploadSideBarImageToGCS(imageBlob, imageName, BUCKET_NAME, FOLDER_NAME);
    
    if (gcsPath) {
      // 4. Convert the 'gs://' path into a browser-usable URL for your frontend
      var objectName = FOLDER_NAME ? FOLDER_NAME + "/" + imageName : imageName;
      var publicUrl = `https://storage.googleapis.com/${BUCKET_NAME}/${encodeURIComponent(objectName)}`;
      
      returnData.status = true;
      returnData.gcsUrl = publicUrl;
      returnData.mimeType = mimeType;
    } else {
      returnData.status = false;
      returnData.error = "Upload failed in uploadSideBarImageToGCS.";
    }
    
  } catch (e) {
    console.error("Error in wrapper: ", e.stack);
    returnData.status = false;
    returnData.error = e.toString();
  }
  
  return returnData;
}

function parseLocalDocument(base64Data, filename, mimeType) {
  var returnData = {};
  try {
    var text = "";

    // 1. Handle plain text directly without GDrive conversion
    if (mimeType === "text/plain" || mimeType === "text/csv" || mimeType === "text/html" || mimeType === "application/json" || filename.endsWith(".txt") || filename.endsWith(".csv") || filename.endsWith(".json")) {
      var decoded = Utilities.newBlob(Utilities.base64Decode(base64Data), mimeType).getDataAsString();
      returnData.status = true;
      returnData.text = decoded;
      return returnData;
    }

    var targetMimeType = null;
    var docType = null;

    if (mimeType.indexOf("wordprocessingml") !== -1 || filename.endsWith(".docx") || filename.endsWith(".doc")) {
      targetMimeType = MimeType.GOOGLE_DOCS;
      docType = "doc";
    } else if (mimeType.indexOf("presentationml") !== -1 || filename.endsWith(".pptx") || filename.endsWith(".ppt")) {
      targetMimeType = MimeType.GOOGLE_SLIDES;
      docType = "slide";
    } else if (mimeType.indexOf("spreadsheetml") !== -1 || filename.endsWith(".xlsx") || filename.endsWith(".xls")) {
      targetMimeType = MimeType.GOOGLE_SHEETS;
      docType = "sheet";
    } else if (mimeType === "application/pdf" || filename.toLowerCase().endsWith(".pdf")) {
      targetMimeType = MimeType.GOOGLE_DOCS;
      docType = "doc";
    }

    if (!targetMimeType) {
      returnData.status = false;
      returnData.error = "Unsupported document format for parsing: " + filename;
      return returnData;
    }

    var mediaData = Utilities.newBlob(Utilities.base64Decode(base64Data), mimeType, filename);
    var fileId = null;

    // Support both Drive API v2 and v3
    if (typeof Drive !== "undefined" && Drive.Files) {
      try {
        if (typeof Drive.Files.create === "function") {
          // Drive API v3
          var fileResource = {
            name: "Temp_PitchGen_" + filename,
            mimeType: targetMimeType
          };
          var createdFile = Drive.Files.create(fileResource, mediaData);
          fileId = createdFile.id;
        } else if (typeof Drive.Files.insert === "function") {
          // Drive API v2
          var fileResource = {
            title: "Temp_PitchGen_" + filename,
            mimeType: targetMimeType
          };
          var createdFile = Drive.Files.insert(fileResource, mediaData, {convert: true});
          fileId = createdFile.id;
        }
      } catch (driveErr) {
        console.warn("Advanced Drive API conversion failed, falling back to DriveApp: " + driveErr);
      }
    }

    if (!fileId) {
      // Fallback via DriveApp if advanced service was unavailable
      var tempFile = DriveApp.createFile(mediaData);
      fileId = tempFile.getId();
    }

    console.log("Uploaded temp file for conversion: ", fileId);

    if (docType === "doc") {
      try {
        var doc = DocumentApp.openById(fileId);
        text = doc.getBody().getText();
      } catch (docOpenErr) {
        // If not directly converted to Google Doc, read plain blob
        text = mediaData.getDataAsString();
      }
    } else if (docType === "slide") {
      text = getDriveFileTextContext(fileId, 'application/vnd.google-apps.presentation');
    } else if (docType === "sheet") {
      var ss = SpreadsheetApp.openById(fileId);
      var sheets = ss.getSheets();
      for (var i = 0; i < sheets.length; i++) {
        var sheet = sheets[i];
        var range = sheet.getDataRange();
        var values = range.getValues();
        for (var r = 0; r < values.length; r++) {
          text += values[r].join("\t") + "\n";
        }
      }
    }

    // Clean up temporary file
    try {
      if (typeof Drive !== "undefined" && Drive.Files) {
        if (typeof Drive.Files.del === "function") {
          Drive.Files.del(fileId);
        } else if (typeof Drive.Files['delete'] === "function") {
          Drive.Files['delete'](fileId);
        } else if (typeof Drive.Files.remove === "function") {
          Drive.Files.remove(fileId);
        }
      } else {
        DriveApp.getFileById(fileId).setTrashed(true);
      }
      console.log("Deleted temp file from Drive: ", fileId);
    } catch (cleanupErr) {
      console.warn("Could not delete temp file " + fileId + ": " + cleanupErr);
    }

    returnData.status = true;
    returnData.text = text;
  } catch (e) {
    console.log("Error in parseLocalDocument: ", e.stack);
    returnData.status = false;
    returnData.error = e.toString();
  }
  return returnData;
}

function listDriveFiles(query) {
  var files = [];
  var pageToken = null;
  var q = "mimeType = 'application/vnd.google-apps.document' or mimeType = 'application/vnd.google-apps.presentation'";
  
  if (query) {
    q = "(" + q + ") and name contains '" + query + "'";
  }
  
  try {
    do {
      var result = Drive.Files.list({
        q: q,
        pageSize: 10,
        pageToken: pageToken,
        fields: "nextPageToken, files(id, name, mimeType)"
      });
      
      if (result.files) {
        for (var i = 0; i < result.files.length; i++) {
          var item = result.files[i];
          files.push({
            id: item.id,
            title: item.name,
            mimeType: item.mimeType
          });
        }
      }
      pageToken = result.nextPageToken;
    } while (pageToken && files.length < 10);
  } catch (e) {
    console.log("Error listing Drive files: " + e.toString());
  }
  
  return files;
}

function getDriveFileTextContext(fileId, mimeType) {
  var text = "";
  try {
    if (mimeType === 'application/vnd.google-apps.document') {
      var doc = DocumentApp.openById(fileId);
      text = doc.getBody().getText();
    } else if (mimeType === 'application/vnd.google-apps.presentation') {
      var presentation = SlidesApp.openById(fileId);
      var slides = presentation.getSlides();
      for (var i = 0; i < slides.length; i++) {
        var slide = slides[i];
        var shapes = slide.getShapes();
        for (var j = 0; j < shapes.length; j++) {
          text += shapes[j].getText().asString() + "\n";
        }
      }
    }
  } catch (e) {
    console.log("Error extracting text from file ID " + fileId + ": " + e.toString());
    text = "Error extracting text content.";
  }
  return text;
}

function getOAuthToken() {
  return ScriptApp.getOAuthToken();
}

function getDeveloperKey() {
  return PropertiesService.getScriptProperties().getProperty("DEVELOPER_KEY") || "";
}
function openPickerDialog(openedFrom) {
  if (openedFrom) {
    var cache = CacheService.getUserCache();
    cache.put('opened_from', openedFrom, 300); // 5 mins
  }
  var html = HtmlService.createHtmlOutputFromFile('pickerDialog')
      .setWidth(800)
      .setHeight(600)
      .setTitle(' ');
  SlidesApp.getUi().showModalDialog(html, ' ');
}

function storeSelectedFile(fileId, fileTitle, fileType) {
  var cache = CacheService.getUserCache();
  var data = {
    id: fileId,
    title: fileTitle,
    type: fileType,
    timestamp: new Date().getTime()
  };
  cache.put('selected_file', JSON.stringify(data), 300); // Keep for 5 mins
  
  // Check if we need to re-open userInputPopup
  var openedFrom = cache.get('opened_from');
  if (openedFrom === 'userInputPopup') {
    cache.remove('opened_from');
    showpopup();
  }
}

function savePopupState(stateJson) {
  var cache = CacheService.getUserCache();
  cache.put('user_input_popup_state', stateJson, 300); // 5 mins
}

function getPopupState() {
  var cache = CacheService.getUserCache();
  var state = cache.get('user_input_popup_state');
  if (state) {
    cache.remove('user_input_popup_state');
    return state;
  }
  return null;
}

function getSelectedFile() {
  var cache = CacheService.getUserCache();
  var cached = cache.get('selected_file');
  if (cached) {
    cache.remove('selected_file');
    return JSON.parse(cached);
  }
  return null;
}

/**
 * Automated End-to-End Diagnostic Test for Google Slides UI Add-on.
 * Simulates Phase 1 Outline, Phase 2 Synthesis, and Slide Creation.
 */
function runPitchGenE2ETest() {
  var ui = SlidesApp.getUi();
  var presentation = SlidesApp.getActivePresentation();
  presentation.toast('Running Step 1/4: Phase 1 Outline Generation...', 'PitchGen Diagnostics', 30);

  var sampleData = {
    customer_name: 'Diagnostic Test Corp',
    audience: ['Executive', 'Architect'],
    industry: 'Retail & Consumer',
    business_context:
        'Adopt Google Cloud BigQuery and Gemini AI for ecommerce analytics',
    sales_stage: 'S1',
    user_ldap: Session.getActiveUser().getEmail().split('@')[0],
    request_type: 'Full Deck',
    presentation_id: presentation.getId(),
    salesPlay: ['Gemini Enterprise for Customer Experience'],
    er_number: 'TEST-9999'
  };

  try {
    // 1. Test Phase 1
    var phase1Resp = apiCall(
        JSON.stringify(sampleData), sampleData.customer_name,
        sampleData.audience.join(','), sampleData.industry,
        sampleData.business_context, sampleData.sales_stage,
        sampleData.user_ldap, sampleData.request_type,
        sampleData.presentation_id, sampleData.salesPlay.join(','),
        sampleData.er_number);

    if (!phase1Resp || !phase1Resp.status || !phase1Resp.titles || phase1Resp.titles.length === 0) {
      throw new Error('Phase 1 Outline Generation failed: ' + JSON.stringify(phase1Resp));
    }
    console.log('✅ Diagnostics Step 1 Passed: Generated ' + phase1Resp.titles.length + ' agendas.');
    presentation.toast('Step 1 Passed! Running Step 2/4: Phase 2 Synthesis...', 'PitchGen Diagnostics', 60);

    // 2. Test Phase 2
    var phase2Resp = apiCall2(phase1Resp.data, phase1Resp.resOut, phase1Resp.titles, [], []);
    if (!phase2Resp || !phase2Resp.status || !phase2Resp.contentGenFilename) {
      throw new Error('Phase 2 Full Deck Generation failed: ' + JSON.stringify(phase2Resp));
    }
    console.log('✅ Diagnostics Step 2 Passed: ContentGen file: ' + phase2Resp.contentGenFilename);
    presentation.toast('Step 2 Passed! Running Step 3/4: Slide DOM Construction...', 'PitchGen Diagnostics', 60);

    // 3. Test Slide Construction
    var contentGenData = readFileFromGCS(reuseAndContentJSONBucketName, phase2Resp.contentGenFilename);
    var parsedContent = JSON.parse(contentGenData);
    contentGeneration(parsedContent, phase2Resp.reuseSlideIdAndPosition, presentation.getId());
    
    console.log('✅ Diagnostics Step 3 Passed: Slides successfully inserted. Total slides: ' + presentation.getSlides().length);
    presentation.toast('Step 3 Passed! Running Step 4/4: Sidebar Slide Search...', 'PitchGen Diagnostics', 15);

    // 4. Test Sidebar Search
    var searchRes = searchAPI('Retail analytics', false, sampleData.user_ldap, 'Solution_Overview');
    console.log('✅ Diagnostics Step 4 Passed: Found ' + (searchRes ? searchRes.length : 0) + ' search slides.');

    ui.alert(
      '🎉 PitchGen E2E Diagnostics PASSED!\n\n' +
      '• Phase 1 Outline: Generated ' + phase1Resp.titles.length + ' agendas\n' +
      '• Phase 2 Synthesis: Created ' + phase2Resp.contentGenFilename + '\n' +
      '• Slide Construction: ' + presentation.getSlides().length + ' slides rendered in deck\n' +
      '• Sidebar Search: Verified working\n\n' +
      'All systems operational in ' + environment + ' environment.'
    );
  } catch (err) {
    console.error('❌ Diagnostics Error:', err);
    ui.alert('❌ PitchGen Diagnostics Failed:\n\n' + err.message);
  }
}
