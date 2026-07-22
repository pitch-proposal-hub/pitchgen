function apiCall(business_context,selectedAudiences,industry,selectedSolutions,customer_name,region,selectedProducts,er_number,requestType,selectedSalesPlay, fileId, fileType, contextFileUrl, contextFileMimeType) {
  
  // Fetch Drive file context if attached
  if (fileId && fileType) {
    try {
      var fileContent = getDriveFileTextContext(fileId, fileType);
      if (fileContent && fileContent !== "Error extracting text content.") {
        business_context += "\n\n### Additional Context from Google Drive File ###\n" + fileContent;
        console.log("Appended Drive file context to business_context");
      }
    } catch (e) {
      console.log("Error fetching Drive file context: " + e.toString());
    }
  }

  var presentationId = SlidesApp.getActivePresentation().getId();
  var userLdap = Session.getActiveUser().getEmail();
  console.log("userLdap : ",userLdap);
  var solutions = "";

  for(var i=0; i<selectedSolutions.length; i++)
  {
    solutions = solutions + selectedSolutions[i].toString()+",";    
  }
  solutions = solutions.substring(0, solutions.length - 1);

  // audience Multiselect-------------------
   var audiences = "";
   for(var i=0; i<selectedAudiences.length; i++)
   {
     audiences = audiences + selectedAudiences[i].toString()+",";    
   }
   audiences = audiences.substring(0, audiences.length - 1);
  
  // product Multiselect-------------------
   var products = "";
   for(var i=0; i<selectedProducts.length; i++)
   {
     products = products + selectedProducts[i].toString()+",";    
   }
   products = products.substring(0, products.length - 1);

   var salesPlay = "";
   for(var i=0; i<selectedSalesPlay.length; i++)
   {
     salesPlay = salesPlay + selectedSalesPlay[i].toString()+",";    
   }
   salesPlay = salesPlay.substring(0, salesPlay.length - 1);
  
  console.log(solutions);
  console.log(audiences);
  console.log(products);
  console.log(salesPlay);
  
  var apiUrl = getAgendasApiUrl ;
  var data = {
  "er_number": er_number,
  "customer_name": customer_name,
  "audience": audiences,
  "industry": industry,
  "business_context": business_context,
  "region" : region,
  "user_ldap": userLdap,
  "request_type": requestType,
  "presentation_id": presentationId,
  "salesPlay": salesPlay,
  "context_file_url": contextFileUrl,
  "context_file_mime_type": contextFileMimeType
  };
  console.log("Payload : ",JSON.stringify(data));
  const agentpayload = {
    "class_method": "async_stream_query",
    "input": {
    // "session_id": sessionId,
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
   "payload": JSON.stringify(agentpayload),
   "muteHttpExceptions": true
  };
  
  // var saveERData = {
  //   "presentation_id": presentationId,
  //   "er_number" : er_number,
  //   "requested_by" : userLdap
  // }
  // var saveEROptions = {
  //   method: "post",
  //   contentType: "application/json",
  //   payload: JSON.stringify(saveERData)
  // };
  console.log("Payload : ",options);
  
   try {
    var response = UrlFetchApp.fetch(apiUrl,options);
    //var responseCode = response.getResponseCode();
    var responseData = response.getContentText();
    console.log("responseData : ",responseData);
    var resOut = extractProposalData(responseData,"create_proposal_outline");
    //var resOut = JSON.parse(responseData);
    console.log("resOut : ",resOut);
    
    // Support both the wrapped {"Status": "True", "data": {...}} and unwrapped GlobalState formats
    var stateData = null;
    if (resOut) {
      if (resOut.Status === "True") {
        stateData = resOut.data;
      } else if (resOut.agendas) {
        stateData = resOut;
      }
    }

    if(stateData && stateData.agendas)
    {
      // var erResponse = UrlFetchApp.fetch(saveErNumber,saveEROptions);
      // var erResponseData = erResponse.getContentText();
      // var erResOut = JSON.parse(erResponseData);
      // console.log(erResOut);
      // if(erResOut.status=="True")
      // {
        var identityToken = ScriptApp.getIdentityToken();
        var databaseData = {
          "er_number": er_number,
          "customer_name": customer_name,
          "audience": audiences,
          "industry": industry,
          "business_context": business_context,
          "region" : region,
          "user_ldap": userLdap,
          "request_type": requestType,
          "presentation_id": presentationId,
          "salesPlay": salesPlay,
          "filename" : resOut.data.filename
        }
        var databaseOptions = {
          method: "post",
          contentType: "application/json",
        "headers": {
          "Authorization": "Bearer " + identityToken
        },
        "payload": JSON.stringify(databaseData)
        };
        console.log("Database Payload : ",databaseOptions);


        var userSaveResponse = UrlFetchApp.fetch(saveUserInput,databaseOptions);
        var jsoneUserSaveResponse = JSON.parse(userSaveResponse.getContentText());
        console.log("userSaveResponse : ",jsoneUserSaveResponse);
        stateData.context.user_input_id = jsoneUserSaveResponse.user_input_id;

        var titles = stateData.agendas;

        var returnData = {};
        returnData.status = true;
        returnData.titles = titles;
        returnData.resOut = JSON.stringify(stateData);
        returnData.data = JSON.stringify(data);
        return returnData;
      // }
      // else
      // {
      //   throw new Error(erResOut.message);
      // }
    }
    else
    {
      throw new Error(resOut.message);
    }
   } catch (error) {
    console.log("Error in Api call : ",error.stack);
    var returnData = {};
    returnData.status = false;
    returnData.message = "Something went wrong";

    return returnData;
   }

}

function extractTitlesFromResponse(jsonResponse){
  var data = JSON.parse(jsonResponse);
  var titles = [];
  for(var sectionNum in data){
    var section = data[sectionNum];
    var title = section["title"];
    titles.push(title);
  }
  // titles.sort(function(a,b){
  //   return parseInt(a.substring(0,a.indexOf(":"))) - parseInt(b.substring(0, b.indexOf(":")));
  // });
  return titles;
}

function apiCall2(data,resOut,agendaArr,deleteAgendaId,deleteAgenda){
  totalCopiedSuggestionSlide = 0;
  totalBlankSuggestionFound = 0;
  totalFailedSuggestionSlide = 0;
  var userLdap = Session.getActiveUser().getEmail();
  console.log("userLdap : ",userLdap);
  var presentation = SlidesApp.getActivePresentation();
  //------------Removing the slides which already present in the Current Deck
    
  if(presentation.getSlides().length>0){
    for(i=presentation.getSlides().length-1;i>=0;i--){
    presentation.getSlides()[i].remove();
    }
  }

  data = JSON.parse(data);
  resOut = JSON.parse(resOut);
  resOut.agendas = agendaArr;
  console.log("resOut : ",resOut);

  var context = resOut.context || {};
  var audienceArr = context.audience || resOut.audience || [];
  var productArr = context.product || resOut.product || [];
  var solutionArr = context.solution || resOut.solution || [];
  var salesPlayArr = context.salesPlay || resOut.salesPlay || [];

  if (typeof audienceArr === 'string') audienceArr = audienceArr.split(',').map(s => s.trim());
  if (typeof productArr === 'string') productArr = productArr.split(',').map(s => s.trim());
  if (typeof solutionArr === 'string') solutionArr = solutionArr.split(',').map(s => s.trim());
  if (typeof salesPlayArr === 'string') salesPlayArr = salesPlayArr.split(',').map(s => s.trim());

  var audience = '';
  var product = '';
  var solution = '';
  var salesPlay = '';
  for(i=0;i<audienceArr.length;i++){
    audience = audience + audienceArr[i] + ',';
  }
  if (audience.length > 0) audience = audience.substring(0,audience.length-1);
  
  for(i=0;i<productArr.length;i++){
    product = product + productArr[i] + ',';
  }
  if (product.length > 0) product = product.substring(0,product.length-1);
  
  for(i=0;i<solutionArr.length;i++){
    solution = solution + solutionArr[i] + ',';
  }
  if (solution.length > 0) solution = solution.substring(0,solution.length-1);
  
  for(i=0;i<salesPlayArr.length;i++){
    salesPlay = salesPlay + salesPlayArr[i] + ',';
  }
  if (salesPlay.length > 0) salesPlay = salesPlay.substring(0,salesPlay.length-1);

  if (resOut.context) {
    resOut.context.audience = audienceArr;
    resOut.context.product = productArr;
    resOut.context.solution = solutionArr;
    resOut.context.salesPlay = salesPlayArr;
  }
  resOut.audience = audience;
  resOut.solution = solution;
  resOut.product = product;
  resOut.salesPlay = salesPlay;
  delete resOut.filename;
  
  var userInputId = context.user_input_id || resOut.user_input_id || "";
  var erNum = context.er_number || resOut.er_number || "";
  erNum = erNum.toString();
  
  var custName = context.customer_name || resOut.customer_name || "";
  custName = custName.toString();
  if (resOut.context) {
    resOut.context.customer_name = custName;
  } else {
    resOut.customer_name = custName;
  }
  console.log("custName : ",custName);
  
  var indus = context.industry || resOut.industry || "";
  indus = indus.toString();
  if (resOut.context) {
    resOut.context.industry = indus;
  } else {
    resOut.industry = indus;
  }
  console.log("Indus : ",indus);
  
  var business = context.business_context || resOut.business_context || "";
  business = business.toString();

  var payload = JSON.stringify(resOut);
  console.log("payload : ",payload);
  // var payload = JSON.stringify(resOut);
  // var payload2 = JSON.parse(payload);
  // delete payload2.filename;
  

  var apiUrl = getReuseArchApiUrl;
  const agentpayload = {
    "class_method": "async_stream_query",
    "input": {
    "user_id":userLdap,
    "message": payload
    }
  };
  var options = {
    method: "post",
    contentType: "application/json",
   "headers": {
     "Authorization": "Bearer " + ScriptApp.getOAuthToken()
   },
   "payload": JSON.stringify(agentpayload),
   "muteHttpExceptions": true
  };

   try {
    //==============UserSlide and File naming code starts
    var userInputs = {
    "er_number": erNum,
    "customer_name": custName,
    "audience": audience,
    "industry": indus,
    "solution": solution,
    "product": product,
    "business_context": business,
    "user_ldap": userLdap,
    "salesPlay": salesPlay
    };
    responseObject.userInputs = userInputs ;
    console.log("userInputs : ",userInputs);
    var format = "yyyy/MM/dd";
    var formattedDate = Utilities.formatDate(new Date(),"GMT",format);
    console.log("date&time : ",formattedDate);
    var presentation = SlidesApp.getActivePresentation();
    if(custName == ""){
    var presentation_name = "PitchGen_"+erNum+"_"+formattedDate;
    }else{
    var presentation_name = "PitchGen_"+erNum+"_"+custName+"_"+formattedDate;
    }
    presentation.setName(presentation_name);
 
    var template = SlidesApp.openByUrl(userSlideTemplateUrl);
    var userSlideTemp = template.getSlides()[1];

    //------------Changing the value of userinputs to '-' if its empty
    for(var key in userInputs){
    if(userInputs[key].trim() === ''){
      userInputs[key] = '-';
    }
    }
    var userSlide = presentation.insertSlide(0,userSlideTemp);
    mappingSourceAndCopiedSlideId[userSlide.getObjectId()] = userSlideTemp.getObjectId();
   // var userSlide = presentation.getSlides()[0];
    //------------Replacing the placeholders with value of Userinputs
    for(var key in userInputs){
      userSlide.replaceAllText("{{"+key+"}}",userInputs[key]);
    }
    userSlide.setSkipped(true);

    var presentationUrl = presentation.getUrl();
    responseObject.generatedDeckUrl = presentationUrl; //Saving the Deck url in response objects and saving in spreadsheet
    var hyperLinkUrl = feedbackUrl; //+ "&entry.1213895865=" + userLdap + "&entry.1449468976=" + erNum + "&entry.2034782325=" + presentationUrl;
    console.log("hyperLinkUrl : ",hyperLinkUrl);
    var elements = userSlide.getPageElements();
    var linkSet = false;
    for (var i = 0; i < elements.length; i++) {
      if (elements[i].getPageElementType() === SlidesApp.PageElementType.SHAPE) {
        var shape = elements[i].asShape();
        if (shape.getText().asString().toLowerCase().indexOf("feedback") !== -1) {
          shape.getText().getTextStyle().setLinkUrl(hyperLinkUrl).setForegroundColor("#4285f4");
          console.log("Found and set feedback link on shape at index " + i);
          linkSet = true;
          break;
        }
      }
    }
    if (!linkSet) {
      console.log("Warning: Could not find 'feedback' shape on User Slide to set link.");
    }

    //===============UserSlide code ended

     var response = UrlFetchApp.fetch(apiUrl,options);
     var responseCode = response.getResponseCode();
     var responseData = response.getContentText();
     //var responseData = dummyReusableAPI;
     console.log("Response String : ",response.toString());
     console.log("responseData : ",responseData);
     var extractedData = extractProposalData(responseData,"slide_generator_skill");
     console.log("Extracted Data :",extractedData);
      var reusableArchFile = extractedData.find(function(item) {
        return 'architectural_filename' in item;
      });
      var contentGenFile = extractedData.find(function(item) {
        return 'outputs_filename' in item;
      });
      // If found, extract the filename; otherwise, set to null
      var reusableArchFilename = reusableArchFile ? reusableArchFile.architectural_filename : null;
      var contentGenFilename = contentGenFile ? contentGenFile.outputs_filename : null;

      console.log("Reusable Filename :", reusableArchFilename);
      console.log("ContentGen Filename :", contentGenFilename);
      var bucketName = templateJsonBucketName || "YOUR_TEMPLATE_JSON_BUCKET";
     var reusableArchFinalData = readFileFromGCS(bucketName,reusableArchFilename);
     console.log("reusableArchFinalData : ",reusableArchFinalData);
     var resOut = JSON.parse(reusableArchFinalData);
     console.log("responseData : ",responseData);
     console.log("resOut : ",resOut);
     responseObject.reusableSlideResponse = resOut;
     var reuseSlideIdAndPosition = copySlidesFromSuggestions(resOut);
     unskip();

     var returnData = {};
     returnData.status = true;
     returnData.contentGenFilename = contentGenFilename;
     returnData.reuseSlideIdAndPosition = reuseSlideIdAndPosition;
     returnData.userInputId = userInputId;

     var dbCount = {};
     dbCount.totalCopiedSuggestionSlide = totalCopiedSuggestionSlide;
     dbCount.totalBlankSuggestionFound = totalBlankSuggestionFound;
     dbCount.totalFailedSuggestionSlide = totalFailedSuggestionSlide;

     returnData.dbCount = dbCount;
     returnData.erNumber = erNum;

     console.log("response Object : ",responseObject);
     console.log("mappingSourceAndCopiedSlideId : ", mappingSourceAndCopiedSlideId);
     console.log("mappingSourceAndCopiedSlideId Length : ",Object.keys(mappingSourceAndCopiedSlideId).length);
     console.log("Total copied Slides : ",totalCopiedSuggestionSlide);
     console.log("Total blank Slides : ",totalBlankSuggestionFound);
     console.log("Total failed Slides : ",totalFailedSuggestionSlide);

     return returnData;
   } 
   catch (error) {
    
    const recipientEmail = Session.getActiveUser().getEmail();
    const subject = "Failure!! Your PitchGen Deck has failed.";
    const ldap = recipientEmail.split('@')[0];
    sendDeckEmailFailure(recipientEmail,subject,ldap);

    console.log("Error in apicall 2 : ",error.stack);
    var returnData = {};
    let errorString = error.toString();
    let jsonString = errorString.substring(errorString.indexOf('{'), errorString.lastIndexOf('}') + 1);
    let errorObject = JSON.parse(jsonString);

    returnData.status = false;
    returnData.message = errorObject.error

    return returnData;
   }
}
function processGeneratedContent(contentGenFilename, reuseSlideIdAndPosition, userInputId, agendaCount, dbCount, erNumber) {
  try {
    console.log("Opportunity Id : ", erNumber);
    var bucketName = templateJsonBucketName || "YOUR_TEMPLATE_JSON_BUCKET";
    var contentGenFinalData = readFileFromGCS(bucketName, contentGenFilename);
    console.log("contentGenFinalData : ", contentGenFinalData);
    var resOut2 = JSON.parse(contentGenFinalData);

    // Check if it is the final version (has sections)
    if (!resOut2.sections) {
      console.log("File exists but is not the final version yet (missing 'sections'). Pending...");
      return { status: "pending" };
    }

    responseObject.contentGenSlide = resOut2;
    responseObject.filename = contentGenFilename;
    responseObject.userInputId = userInputId;

    contentGeneration(resOut2, reuseSlideIdAndPosition);
    removeEmptyPlaceholders();

    // DB Logging
    try {
      var totalTempUrl = totalGeneratedSlidesFromModelJS(resOut2, "temp_url");
      var contentgeneratedslides = totalTempUrl - agendaCount - 3;
      if (contentgeneratedslides < 0) contentgeneratedslides = 0;

      var identityToken = ScriptApp.getIdentityToken();
      var saveSuccessCopiedSlideData = {
        "copied_reusable_count": (dbCount.totalCopiedSuggestionSlide + dbCount.totalBlankSuggestionFound + dbCount.totalFailedSuggestionSlide),
        "contentgeneratedslides": contentgeneratedslides,
        "totalTempUrl": totalTempUrl,
        "user_input_id": userInputId
      };
      
      var saveSuccessCopiedSlideOptions = {
        method: "post",
        contentType: "application/json",
        "headers": {
          "Authorization": "Bearer " + identityToken
        },
        "payload": JSON.stringify(saveSuccessCopiedSlideData)
      };
      console.log("saveSuccessCopiedSlideData Payload :", saveSuccessCopiedSlideOptions);
      var responseCopiedSlide = UrlFetchApp.fetch(updateCountsOfCopiedSuggestionSlide,saveSuccessCopiedSlideOptions);
      console.log("Response of responseCopiedSlide : ",responseCopiedSlide.getContentText());
      
      const deckTitle = resOut2.sections.title.slides["1"].placeholders.title;
      const recipientEmail = Session.getActiveUser().getEmail();
      const subject = "Success!! Your PitchGen Deck - "+deckTitle+" is Ready.";
      const deckUrl = SlidesApp.getActivePresentation().getUrl();
      const ldap = recipientEmail.split('@')[0];
      sendDeckEmailSuccess(recipientEmail,subject,deckUrl,ldap);
    } catch(e) {
      console.log("Error in DB logging inside processGeneratedContent: ", e.stack);
    }

    return { status: true };
  } catch (error) {

    const recipientEmail = Session.getActiveUser().getEmail();
    const subject = "Failure!! Your PitchGen Deck has failed.";
    const ldap = recipientEmail.split('@')[0];
    sendDeckEmailFailure(recipientEmail,subject,ldap);

    console.log("Error in processGeneratedContent: ", error.stack);
    return { status: false, error: error.toString() };
  }
}

function checkFileExists(bucketName, fileName) {
  const encodedFileName = encodeURIComponent(fileName);
  const url = `https://storage.googleapis.com/storage/v1/b/${bucketName}/o/${encodedFileName}`;
  const token = ScriptApp.getOAuthToken();
  const options = {
    method: 'get',
    headers: {
      Authorization: 'Bearer ' + token
    },
    muteHttpExceptions: true
  };
  console.log("Payload : ",options);
  try {
    const response = UrlFetchApp.fetch(url, options);
    console.log(response.getContentText());
    console.log("Status : ",response.getResponseCode());
    return response.getResponseCode() === 200;
  } catch (error) {
    console.log("Error checking file existence: " + error.toString());
    return false;
  }
}

function totalGeneratedSlidesFromModelJS(data, keyToFind) {
  var totalGeneratedSlides = 0;
  if (typeof data === 'string') {
    try {
      data = JSON.parse(data);
    } catch (e) {
      return 0;
    }
  }
  if (data && typeof data === 'object') {
    if (Array.isArray(data)) {
      for (var i = 0; i < data.length; i++) {
        totalGeneratedSlides += totalGeneratedSlidesFromModelJS(data[i], keyToFind);
      }
    } else {
      for (var key in data) {
        if (key === keyToFind) {
          totalGeneratedSlides += 1;
        }
        totalGeneratedSlides += totalGeneratedSlidesFromModelJS(data[key], keyToFind);
      }
    }
  }
  return totalGeneratedSlides;
}
function unskip(){
  var presentation1 = SlidesApp.getActivePresentation();
  var slides = presentation1.getSlides();
  console.log("slides length : ",slides.length);
  for(i=1;i<slides.length;i++){
    var skippedSlide = presentation1.getSlides()[i];
    skippedSlide.setSkipped(false);
  }
  console.log("unskipped");
}

function getDriveURLAPI(user_input_id,filename)
{
  var apiUrl = getDriveUrlApiUrl; 
  var data = {
    "deck_drive_url": null,
    "user_input_id": user_input_id,
    "filename": filename
  };
  console.log("Payload for getdriveurl: ",data);
  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(data)
  };
  try{
    var response = UrlFetchApp.fetch(apiUrl,options);
    var responseData = response.getContentText();
    console.log("getDriveUrlApi Response : ",responseData);
  }
  catch(e)
  {
    console.log("Copy Spreadsheet API Error : ",e.stack);
  }
}



//--------- Function to remove the empty placeholders from Generated Pitch
function removeEmptyPlaceholders() {
  try{
  var pres = SlidesApp.getActivePresentation();
  var placeholdersArr = ["subtitle",
  "subheader1",
  "subheader2",
  "subheader3",
  "subheader4",
  "subheader5",
  "subheader6",
  "header",
  "title",
  "item1_content","item2_content","item3_content","item4_content","item5_content","item6_content", "item7_content",
  "text",
  "item1","item2", "item3", "item4", "item5", "item6", "item7", "item8","item9","item10",
  "text1","text2",
  "sub_item_1","sub_item_2","sub_item_3",
  "sub_item_1_content","sub_item_2_content","sub_item_3_content",
  "num",
  "agenda1","agenda2","agenda3","agenda4","agenda5","agenda6","agenda7","agenda8","agenda9","agenda10",
  "header1","header2","header3","header4","header5","header6","header7","header8",
  "header1_content1","header1_content2","header1_content3","header1_content4",
  "header2_content1","header2_content2","header2_content3","header2_content4",
  "header3_content1","header3_content2","header3_content3","header3_content4",
  "header4_content1","header4_content2","header4_content3","header4_content4",
  "header5_content1","header5_content2","header5_content3","header5_content4",
  "header6_content1","header6_content2","header6_content3","header6_content4",
  "header1_content","header2_content","header3_content","header4_content","header5_content","header6_content","header7_content","header8_content","header9_content","header10_content",
  "header1_subheader1","header1_subheader2","header1_subheader3","header1_subheader4","header1_subheader5","header1_subheader6","header1_subheader7","header1_subheader8","header1_subheader9",
  "header1_subheader1_content","header1_subheader2_content","header1_subheader3_content","header1_subheader4_content","header1_subheader5_content","header1_subheader6_content","header1_subheader7_content","header1_subheader8_content","header1_subheader9_content",'header1_subheader10_content',
  "header2_subheader1","header2_subheader2",'header2_subheader3',"header2_subheader4",
  "header2_subheader1_content","header2_subheader2_content","header2_subheader3_content","header2_subheader4_content","header2_subheader5_content","header2_subheader6_content",
  "subheader1_content1","subheader1_content2","subheader1_content3","subheader1_content4","subheader1_content5","subheader1_content6","subheader1_content7","subheader1_content8",
  "subheader2_content1","subheader2_content2","subheader2_content3","subheader2_content4","subheader2_content5","subheader2_content6","subheader2_content7","subheader2_content8",
  "subheader3_content1","subheader3_content2","subheader3_content3","subheader3_content4","subheader3_content5","subheader3_content6","subheader3_content7","subheader3_content8"];
  for(i=0;i<placeholdersArr.length;i++){ 
  pres.replaceAllText("{{"+placeholdersArr[i]+"}}","");
  }
  console.log("Placeholders removed");
  }catch(e){
    console.log("remove placeholders error : ",e.stack);
  }
}
function sendDeckEmailSuccess(recipientEmail,subject,deckUrl,name) {
  const plainTextBody = 
    `Dear ${name},
      Great news! The deck generation process you initiated on PitchGen is now complete.
      Your customized presentation is ready for review and download. You can access it directly via the link below:
      👉 View Your PitchGen Deck: ${deckUrl}

      Next Steps:
      - Review: Check the slides to ensure all information aligns with your goals.
      - Edit: If you need to make any tweaks, you can re-run or edit sections directly within PitchGen.
      - Share: Use the link above to share the presentation with your team or stakeholders.

      Thank you for using PitchGen. If you have any feedback, please reach out to us directly at: YOUR_SUPPORT_EMAIL or if you have any issues, please contact support.

      Best regards,
      The PitchHub Team

      Please note: This is an automated notification. If you did not request this deck, please contact our support team immediately.`;

  const htmlBody = `
    <div style="font-family: Arial, sans-serif; color: #333333; line-height: 1.6;">
      <p>Dear ${name},</p>
      
      <p>Great news! The deck generation process you initiated on PitchGen is now complete.<br>
      Your customized presentation is ready for review and download. You can access it directly via the link below:<br>
      👉 <a href="${deckUrl}" style="color: #1a73e8; text-decoration: none; font-weight: bold;">View Your PitchGen Deck</a></p>
      
      <p><strong>Next Steps:</strong></p>
      <ul style="margin-top: 0;">
        <li><strong>Review:</strong> Check the slides to ensure all information aligns with your goals.</li>
        <li><strong>Edit:</strong> If you need to make any tweaks, you can re-run or edit sections directly within PitchGen.</li>
        <li><strong>Share:</strong> Use the link above to share the presentation with your team or stakeholders.</li>
      </ul>
      
      <p>Thank you for using PitchGen. If you have any feedback, please reach out to us directly at: <a href="mailto:YOUR_SUPPORT_EMAIL">YOUR_SUPPORT_EMAIL</a> or if you have any issues, please contact support.</p>
      
      <p>Best regards,<br>
      <strong>The PitchHub Team</strong></p>
      
      <hr style="border: none; border-top: 1px solid #eeeeee; margin-top: 20px;">
      <p style="font-size: 12px; color: #777777;">
        <em>Please note: This is an automated notification. If you did not request this deck, please contact our support team immediately.</em>
      </p>
    </div>
  `;

  MailApp.sendEmail(recipientEmail, subject, plainTextBody, {
    htmlBody: htmlBody
  });
}

function sendDeckEmailFailure(recipientEmail,subject,name) {  
  const plainTextBody = 
    `Dear ${name},

    The deck generation process you initiated on PitchGen has failed. Can you please try to rerun the process?

    Apologies for any inconvenience caused due to the above.

    Thank you for using PitchGen. If you have any feedback, please reach out to us directly at: YOUR_SUPPORT_EMAIL or if you have any issues, please contact support.

    Best regards,
    The PitchHub Team

    Please note: This is an automated notification. If you did not request this deck, please contact our support team immediately.`;

  const htmlBody = `
    <div style="font-family: Arial, sans-serif; color: #333333; line-height: 1.6;">
      <p>Dear ${name},</p>
      
      <p>The deck generation process you initiated on PitchGen has failed. Can you please try to rerun the process?</p>

      <p>Apologies for any inconvenience caused due to the above.</p>
      
      <p>Thank you for using PitchGen. If you have any feedback, please reach out to us directly at: <a href="mailto:YOUR_SUPPORT_EMAIL">YOUR_SUPPORT_EMAIL</a> or if you have any issues, please contact support.</p>
      
      <p>Best regards,<br>
      <strong>The PitchHub Team</strong></p>
      
      <hr style="border: none; border-top: 1px solid #eeeeee; margin-top: 20px;">
      <p style="font-size: 12px; color: #777777;">
        <em>Please note: This is an automated notification. If you did not request this deck, please contact our support team immediately.</em>
      </p>
    </div>
  `;

  MailApp.sendEmail(recipientEmail, subject, plainTextBody, {
    htmlBody: htmlBody
  });
}