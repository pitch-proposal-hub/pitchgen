function onOpen(){
  SlidesApp.getUi().createMenu('Pitch Gen Menu')
  .addItem('Generate a New Pitch', 'showpopup')
  .addItem('Edit my Presentation','showSidebar')
  // .addItem('Report an Issue', 'showMyHelp')
  .addItem('User Feedback', 'userFeedback')
  .addItem('User Guide', 'userGuide')
  .addToUi(); 
}
function showpopup() {
  var htmlOutput = HtmlService.createHtmlOutputFromFile('userInputPopup').setTitle('Screen1').setHeight(423).setWidth(1000);
  SlidesApp.getUi().showModalDialog(htmlOutput, ' ');
}

function showSidebar(){
  var ui = HtmlService.createHtmlOutputFromFile('sideBar').setTitle('PitchGen');
  ui.setHeight(200); //.setWidth(50);
  SlidesApp.getUi().showSidebar(ui);
}

function showMyHelp() {                                 //Deprecated for now
  var html =  '<div>'+'<p>'+supportText+'</p>' +        //SupportText In Configuration file
               '</div>';
  var ui = SlidesApp.getUi();
  ui.showModalDialog(HtmlService.createHtmlOutput(html).setHeight(100).setWidth(500), 'PitchGen Help');
}

function addSlideAPI(selectedCategory,sheetId,deckId,slideTitle,slideContent,slideLayout,slideCategory,audience,solution,product,customerName,industry,region,erIdGenerate)
{
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
  const imageURL = Slides.Presentations.Pages.getThumbnail(id, firstSlide, {"thumbnailProperties.mimeType": "PNG"}).contentUrl;
  var thumbnailBlob = UrlFetchApp.fetch(imageURL).getBlob();
  var base64Data = Utilities.base64Encode(thumbnailBlob.getBytes());
  var userLdap = Session.getActiveUser().getEmail();
  var apiUrl = addSlideApiUrl ;
  var data = {
  "audience": audience,
  "industry": industry,
  "solution": solution,
  "product": product,
  "region": region,
  "customer_name": customerName,
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
  "slide_image_url" : base64Data
  };
  console.log("Payload",data);
  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(data)
  };
  var saveERData = {
    "presentation_id": id,
    "er_number" : erIdGenerate,
    "requested_by" : userLdap
  }
  var saveEROptions = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(saveERData)
  };
  var returnData = {};
  try{
      var response = UrlFetchApp.fetch(apiUrl,options);
      console.log("AddSlide Response : ",response.getContentText());
      var resOut = JSON.parse(response);
      if(resOut.Status=="True")
      {
        copySlideBetweenPresentations(position,response);

        var erResponse = UrlFetchApp.fetch(saveErNumber,saveEROptions);
        var erResponseData = erResponse.getContentText();
        var erResOut = JSON.parse(erResponseData);
        console.log("erResOut : ",erResOut);
        if(erResOut.status!="True")
        {
          returnData.status = false;
          returnData.error = "Something went wrong";
        }
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

function triggerNanoBananaAPI(prompt, styleImage) {
  var userLdap = Session.getActiveUser().getEmail();
  var apiUrl = infographicGenUrl;
  var data = {
    "prompt": prompt,
    "user_ldap": userLdap,
    "style_image": styleImage
  };
  
  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(data)
  };

  var returnData = {};
  try {
    var response = UrlFetchApp.fetch(apiUrl, options);
    var resOut = JSON.parse(response.getContentText());
    
    if (resOut.Status == "True" || resOut.status == true) {
      var imageUrl = resOut.data ? (resOut.data.image_url || resOut.data.response) : resOut.image_url;
      
      if (!imageUrl) {
         throw new Error("No image URL returned from backend");
      }

      var imageBlob = UrlFetchApp.fetch(imageUrl).getBlob();
      
      var presentation = SlidesApp.getActivePresentation();
      var slide = presentation.appendSlide(SlidesApp.PredefinedLayout.BLANK);
      slide.insertImage(imageBlob);
      
      returnData.status = true;
    } else {
      returnData.status = false;
      returnData.error = resOut.message || "Model failed to generate image";
    }
  } catch (e) {
    console.log("Error in triggerNanoBananaAPI: ", e.stack);
    returnData.status = false;
    returnData.error = e.toString();
  }
  return returnData;
}



function reshuffleSlideAPI(sheetId,spreadSheetId,desiredOutputCriteria,slideLayout,slideCategory,erId,toggleThemeLayout)
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
  const imageURL = Slides.Presentations.Pages.getThumbnail(id, slideId, {"thumbnailProperties.mimeType": "PNG"}).contentUrl;
  var thumbnailBlob = UrlFetchApp.fetch(imageURL).getBlob();
  var base64Data = Utilities.base64Encode(thumbnailBlob.getBytes());
  var userLdap = Session.getActiveUser().getEmail();
  var apiUrl = reshuffleApiUrl ;
  var data = {
  "toggle": false,
  "slide_layout": slideLayout,
  "slide_category": slideCategory,
  "slide_id": sheetId,
  "deck_id": spreadSheetId,
  "output_criteria" : desiredOutputCriteria,
  "action" : "transform",
  "er_number" : erId,
  "user_ldap" : userLdap,
  "presentation_id" : id,
  "slide_image_url" : base64Data
  };
  var options;
  if(toggleThemeLayout==false)
  {
    options = {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(data)
    };
    console.log("Payload : ",data);
  }
  else
  {
    var togglePayload = reshuffleToggleOffPayload(slideId,erId,desiredOutputCriteria);
    options = {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(togglePayload)
    };
    console.log("Payload : ",togglePayload);
  }
  var saveERData = {
    "presentation_id": id,
    "er_number" : erId,
    "requested_by" : userLdap
  }
  var saveEROptions = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(saveERData)
  };
  var returnData = {};
  try
  {
    var response = UrlFetchApp.fetch(apiUrl,options);                 //Return filename
    var toggleResOut = JSON.parse(response.getContentText());
    
    console.log("Filename Response : ",toggleResOut);
    
    if(toggleResOut.message='Success')
    {
      var payloadData = {
        "filename": toggleResOut.data.response
      };
      var finalOptions = {
        method: "post",
        contentType: "application/json",
        payload: JSON.stringify(payloadData)
      };
      console.log(finalOptions);
      var finalResponse = UrlFetchApp.fetch(getReshuffleApiUrl,finalOptions);             //Return actual content
      var finalResOut = JSON.parse(finalResponse.getContentText());
      console.log("finalResout : ",finalResOut);
      if(finalResOut.status=='success')
      {
        if(toggleThemeLayout==false)
        {
          returnData.status = reshuffleInsertSlideToggleOff(position,sheetId,spreadSheetId,finalResOut);
        }
        else
        {
          returnData.status = reshuffleInsertSlideToggleOn(finalResOut);
        }
        if(returnData.status==true)
        {
          var erResponse = UrlFetchApp.fetch(saveErNumber,saveEROptions);       //Save ER ID
          var erResponseData = erResponse.getContentText();
          var erResOut = JSON.parse(erResponseData);
          console.log("erResOut : ",erResOut);
          if(erResOut.status!="True")
          {
            returnData.status = false;
            returnData.error = "Something went wrong";
            console.log("Failed to save ER ID in Transform Slide");
            return returnData;
          }
        }
        console.log("********************SUCCESS********************");
      }
      else
      {
        returnData.status = false;
      }
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

  var response = JSON.parse(response).data;
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
    SlidesApp.getActivePresentation().getSlides()[position-1].remove();
    var newSlide = SlidesApp.getActivePresentation().insertSlide(position-1,sourceSlide);
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
  var html = HtmlService.createHtmlOutput('<script>window.open("' + userSlideTemplateUrl + '", "_blank");google.script.host.close();</script></html>')
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

function readTemplateSlides()
{
  var returnObj = {};
  var options = {
    method: "get",
    contentType: "application/json"
  };
  try{
    var response = UrlFetchApp.fetch(readTemplate,options);
    var responseData = response.getContentText();
    var resOut = JSON.parse(responseData);

    console.log("Response :",resOut);
    if(resOut.status=="success")
    {
      returnObj.status = true;
      returnObj.response = resOut;

      return returnObj;
    }
    else
    {
      console.log("Failed");
      returnObj.status = false;
      return returnObj;
    }
  }
  catch(e)
  {
    console.log(e.stack);
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
  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(returnObj)
  };
  try{
    var response = UrlFetchApp.fetch(uploadTemplate,options);
    var responseData = response.getContentText();
    var resOut = JSON.parse(responseData);

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

/**
 * Lists Google Docs and Slides from Drive.
 * @param {string} query - Optional search query to filter files by name.
 * @return {Array} List of files with id, title, and mimeType.
 */
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

/**
 * Extracts text content from a Google Doc or Slide.
 * @param {string} fileId - The ID of the Drive file.
 * @param {string} mimeType - The mimeType of the file.
 * @return {string} Extracted text content.
 */
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