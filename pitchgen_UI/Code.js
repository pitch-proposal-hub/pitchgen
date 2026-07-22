function onOpen(e){
  var menu = SlidesApp.getUi().createAddonMenu();
  //var menu = SlidesApp.getUi().createMenu('PitchGen Menu');

  menu.addItem('Generate a New Pitch', 'showpopup')
  .addItem('Edit my Presentation','showSidebar')
  .addItem('User Feedback', 'userFeedback')
  .addItem('User Guide', 'userGuide')
  .addToUi(); 
}

function onInstall(e) {
  onOpen(e);
}
function showpopup() {
  const bucketName = PropertiesService.getScriptProperties().getProperty('BUCKET_NAME');
  const template = HtmlService.createTemplateFromFile('userInputPopup');
  template.bucketName = bucketName;  
  var htmlOutput = template.evaluate()
      .setTitle('Screen1')
      .setHeight(423)
      .setWidth(1000);
  SlidesApp.getUi().showModalDialog(htmlOutput, ' ');
}
function showSidebar(){
  const bucketName = PropertiesService.getScriptProperties().getProperty('BUCKET_NAME');
  const template = HtmlService.createTemplateFromFile('sideBar');
  template.bucketName = bucketName;
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
  "region": region,
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
      //var resOut = JSON.parse(response);
      if(resOut.Status=="True")
      {
        copySlideBetweenPresentations(position,resOut);

        var addGenerateSaveResponse = UrlFetchApp.fetch(saveEditAction,saveAddGenerateOptions);
        console.log("addGenerateSaveResponse : ",addGenerateSaveResponse.getContentText());

        // var erResponse = UrlFetchApp.fetch(saveErNumber,saveEROptions);
        // var erResponseData = erResponse.getContentText();
        // var erResOut = JSON.parse(erResponseData);
        // console.log("erResOut : ",erResOut);
        // if(erResOut.status!="True")
        // {
        //   returnData.status = false;
        //   returnData.error = "Something went wrong";
        // }
      }
      else
      {
        returnData.status = false;
        returnData.error = "Something went wrong";
      }
  }
  catch(e)
  {
    console.log("Error in Add Slide : ",e.stack);
    let errorString = e.toString();
    let jsonString = errorString.substring(errorString.indexOf('{'), errorString.lastIndexOf('}') + 1);
    jsonString = JSON.parse(jsonString);
    returnData.status = false;
    returnData.error = jsonString.error;
    
    return returnData;
  }
  returnData.status = true;
  return returnData;
}



function reshuffleSlideAPI(sheetId,spreadSheetId,desiredOutputCriteria,slideLayout,slideCategory,erId,toggleThemeLayout,language)
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
    var togglePayload = reshuffleToggleOffPayload(slideId,erId,desiredOutputCriteria);
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
    
    if(toggleResOut.message='Success')
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
          var identityToken = ScriptApp.getIdentityToken();
          var saveSlideTransformOptions = {
            method: "post",
            contentType: "application/json",
            "headers": {
              "Authorization": "Bearer " + identityToken
            },
            "payload": JSON.stringify(saveSlideTransformData)
          };
          console.log("Database Payload : ",saveSlideTransformOptions);

          var slideTransformSaveResponse = UrlFetchApp.fetch(saveEditAction,saveSlideTransformOptions);
          console.log("slideTransformSaveResponse : ",slideTransformSaveResponse.getContentText());

          // var erResponse = UrlFetchApp.fetch(saveErNumber,saveEROptions);       //Save ER ID
          // var erResponseData = erResponse.getContentText();
          // var erResOut = JSON.parse(erResponseData);
          // console.log("erResOut : ",erResOut);
          // if(erResOut.status!="True")
          // {
          //   returnData.status = false;
          //   returnData.error = "Something went wrong";
          //   console.log("Failed to save ER ID in Transform Slide");
          //   return returnData;
          // }
        }
        console.log("********************SUCCESS********************");
      // }
      // else
      // {
      //   returnData.status = false;
      // }
    }
    else
    {
      returnData.status = false;
    }
  }
  catch(e)
  {
    console.log("Error in Reshuffle Slide : ",e.stack);
    let errorString = e.toString();
    let jsonString = errorString.substring(errorString.indexOf('{'), errorString.lastIndexOf('}') + 1);
    jsonString = JSON.parse(jsonString);
    returnData.status = false;
    returnData.error = jsonString.error;
    
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
function reshuffleInsertSlideToggleOn(resOut) {
    
  try
  {  
    var response = JSON.parse(resOut.content);
    var data = response.data;
    var presentation = SlidesApp.getActivePresentation();
    var slide = presentation.getSlideById(response.slideId);

    for(var i=0 ; i<data.length; i++)
    {
      const pageElement = slide.getPageElementById(data[i].shapeId);
      pageElement.asShape().getText().setText(data[i].text);
    }

    return true;
  }
  catch(e)
  {
    return false;
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
  var html = HtmlService.createHtmlOutput('<script>window.open("' + (userSlideTemplateUrl || "YOUR_USER_GUIDE_URL") + '", "_blank");google.script.host.close();</script></html>')
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
      return `https://storage.googleapis.com/${BUCKET_NAME}/${result.name}`;
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

function reshuffleToggleOffPayload(slideId,erId,desiredOutputCriteria) {
  var presentation = SlidesApp.getActivePresentation();
  var userLdap = Session.getActiveUser().getEmail();
  var slide = presentation.getSlideById(slideId);  
  var shapes = slide.getShapes();
  var output = {};
  var contentArr = [];
  output.toggle = true, 
  output.presentation_id = presentation.getId();
  output.slideId = slideId;
  output.output_criteria = desiredOutputCriteria; 
  output.er_number = erId;
  output.action = "transform";
  output.user_ldap = userLdap;

  shapes.forEach(function(shape) {
      var contentData = {};
      var text = shape.getText().asString();      
      if (text.trim() !== "") {
        contentData.shapeId = shape.getObjectId();
        contentData.text = text.trim();
        contentData.charCount = text.trim().length;
        contentData.bold = shape.getText().getTextStyle().isBold();
        contentData.fontSize = shape.getText().getTextStyle().getFontSize();
        contentArr.push(contentData);
      }
  });

  output.data = contentArr;

  return output;
}

function saveSalesPlay(savePlayData)
{
  console.log("saveSalesPlay call");
  var presentation = SlidesApp.getActivePresentation();
  var ldap = Session.getActiveUser().getEmail();
  var data = {
    "business_context": savePlayData.business_context,
    "industry": savePlayData.selectedIndustry,
    "solution": savePlayData.solution,
    "customer_name": savePlayData.customerName,
    "er_number": savePlayData.erNumber,
    "region" : savePlayData.region,
    "product" : savePlayData.product,
    "audience" : savePlayData.audience,
    "salesPlay" : savePlayData.salesPlayName,
    "presentation_id" : presentation.getId(),
    "user_ldap" : ldap,
    "request_type" : "Salesplay"   
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
  // 1. Replace these with your actual bucket and file names
  
  // 2. Encode the file name properly for the URL
  const encodedFileName = encodeURIComponent(fileName);
  const url = `https://storage.googleapis.com/storage/v1/b/${bucketName}/o/${encodedFileName}?alt=media`;
  
  // 3. Fetch the OAuth token of the user running the script
  // Note: The script must have the necessary IAM permissions to access the bucket.
  const token = ScriptApp.getOAuthToken();
  
  const options = {
    method: 'get',
    headers: {
      Authorization: 'Bearer ' + token
    },
    muteHttpExceptions: true
  };
  
  try {
    // 4. Make the API request
    const response = UrlFetchApp.fetch(url, options);
    const responseCode = response.getResponseCode();
    
    if (responseCode === 200) {
      const fileContent = response.getContentText();
      Logger.log('File content successfully retrieved:');
      return fileContent;
    } else {
      Logger.log(`Error: Received status code ${responseCode}`);
      Logger.log(response.getContentText());
      throw new Error(`Failed to fetch file. Status: ${responseCode}`);
    }
    
  } catch (error) {
    Logger.log('Exception caught: ' + error.toString());
  }
}
function extractProposalData(rawResponseText,parameterName) {
  const lines = rawResponseText.trim().split('\n');
  for (let line of lines) {
    if (!line) continue;

    try {
      const parsedLine = JSON.parse(line);

      // 3. Safely navigate the JSON path looking for a function_response
      const parts = parsedLine?.content?.parts;
      if (parts && parts.length > 0) {
        const functionResponse = parts[0]?.function_response;

        // 4. Check if this is the exact tool that generated your outline
        if (functionResponse && functionResponse.name === parameterName) {
          
          // 5. Extract the stringified JSON result and parse it into a real object
          const resultString = functionResponse.response.result;
          const finalDataObject = JSON.parse(resultString);

          // This returns the exact { Status: 'True', data: {...} } object you want!
          return finalDataObject; 
        }

        // Fallback: Check if the text part itself contains the JSON payload directly (from agent interceptor)
        const textPart = parts[0]?.text;
        if (textPart) {
          try {
            const finalDataObject = JSON.parse(textPart);
            if (finalDataObject && typeof finalDataObject === 'object') {
              return finalDataObject;
            }
          } catch (jsonErr) {
            // Not a valid JSON in text, continue
          }
        }
      }
    } catch (e) {
      console.error("Skipping a line that couldn't be parsed: ", e.message);
    }
  }

  // If the loop finishes and didn't find the data, return null
  console.error("Could not find "+parameterName+" data in the agent response.");
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

// function uploadFileToGCS(base64Data, filename, mimeType) {
//   var apiUrl = serviceUrl + "uploadFile";
//   var payload = {
//     "filename": filename,
//     "base64_data": base64Data,
//     "mime_type": mimeType
//   };
//   var options = {
//     "method": "post",
//     "contentType": "application/json",
//     "payload": JSON.stringify(payload)
//   };
//   console.log("Payload : ",payload);

//   var returnData = {};
//   try {
//     var response = UrlFetchApp.fetch(apiUrl, options);
//     var resOut = JSON.parse(response.getContentText());
//     console.log("Upload File Response: ", resOut);

//     if (resOut.status == "success") {
//       returnData.status = true;
//       returnData.gcsUrl = resOut.gcs_url;
//       returnData.mimeType = resOut.mime_type;
//     } else {
//       returnData.status = false;
//       returnData.error = "Failed to upload file";
//     }
//   } catch (e) {
//     console.log("Error in uploadFileToGCS: ", e.stack);
//     returnData.status = false;
//     returnData.error = e.toString();
//   }
//   return returnData;
// }

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

    // Handle plain text directly without GDrive conversion
    if (mimeType === "text/plain" || mimeType === "text/csv" || mimeType === "text/html" || mimeType === "application/json") {
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
    }

    if (!targetMimeType) {
      returnData.status = false;
      returnData.error = "Unsupported document format for parsing.";
      return returnData;
    }

    var resource = {
      title: "Temp_PitchGen_" + filename,
      mimeType: targetMimeType
    };
    var mediaData = Utilities.newBlob(Utilities.base64Decode(base64Data), mimeType);

    var file = Drive.Files.insert(resource, mediaData, {convert: true});
    console.log("Uploaded temp file for conversion: ", file.id);

    if (docType === "doc") {
      var doc = DocumentApp.openById(file.id);
      text = doc.getBody().getText();
    } else if (docType === "slide") {
      text = getDriveFileTextContext(file.id, 'application/vnd.google-apps.presentation');
    } else if (docType === "sheet") {
      var ss = SpreadsheetApp.openById(file.id);
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

    Drive.Files.remove(file.id);
    console.log("Deleted temp file from Drive: ", file.id);

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

function getPickerConfig() {
  var props = PropertiesService.getScriptProperties();
  return {
    developerKey: props.getProperty("DEVELOPER_KEY") || "",
    appId: props.getProperty("GCP_PROJECT_NUMBER") || props.getProperty("APP_ID") || ""
  };
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