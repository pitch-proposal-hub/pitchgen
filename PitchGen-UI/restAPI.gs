function apiCall(business_context,selectedAudiences,industry,selectedSolutions,customer_name,region,selectedProducts,er_number,requestType, fileId, fileType) {
  
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
  
  console.log(solutions);
  console.log(audiences);
  console.log(products);
  
  var apiUrl = getAgendasApiUrl ;
  var data = {
  "er_number": er_number,
  "customer_name": customer_name,
  "audience": audiences,
  "industry": industry,
  "solution": solutions,
  "product": products,
  "business_context": business_context,
  "region" : region,
  "user_ldap": userLdap,
  "request_type": requestType,
  "presentation_id": presentationId
  };
  console.log("Payload : ",JSON.stringify(data));
  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(data)
  };
  var saveERData = {
    "presentation_id": presentationId,
    "er_number" : er_number,
    "requested_by" : userLdap
  }
  var saveEROptions = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(saveERData)
  };
   try {
    var response = UrlFetchApp.fetch(apiUrl,options);
    var responseCode = response.getResponseCode();
    var responseData = response.getContentText();
    var resOut = JSON.parse(responseData);
    console.log("resOut : ",resOut)
    if(resOut.Status=="True")
    {
      var erResponse = UrlFetchApp.fetch(saveErNumber,saveEROptions);
      var erResponseData = erResponse.getContentText();
      var erResOut = JSON.parse(erResponseData);
      console.log(erResOut);
      if(erResOut.status=="True")
      {
        var titles = resOut.data.agendas;

        var returnData = {};
        returnData.status = true;
        returnData.titles = titles;
        returnData.resOut = JSON.stringify(resOut.data);
        returnData.data = JSON.stringify(data);
        return returnData;
      }
      else
      {
        throw new Error(erResOut.message);
      }
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
  var audienceArr = resOut.audience;
  var productArr = resOut.product;
  var solutionArr = resOut.solution;
  var audience = '';
  var product = '';
  var solution = '';
  for(i=0;i<audienceArr.length;i++){
    audience = audience + audienceArr[i] + ',';
  }
  audience = audience.substring(0,audience.length-1);
  for(i=0;i<productArr.length;i++){
    product = product + productArr[i] + ',';
  }
  product = product.substring(0,product.length-1);
  for(i=0;i<solutionArr.length;i++){
    solution = solution + solutionArr[i] + ',';
  }
  solution = solution.substring(0,solution.length-1);
  resOut.audience = audience;
  resOut.solution = solution;
  resOut.product = product;
  delete resOut.filename;
  var userInputId = resOut.user_input_id;
  
  var erNum = resOut.er_number;
  erNum = erNum.toString();
  var custName ;
  if (resOut.customer_name === null) {
    console.log("inside if");
    custName = "";
    resOut.customer_name = "";

  }else{
    console.log("inside else");
    custName = resOut.customer_name;
    custName = custName.toString();
  }
  console.log("custName : ",custName);
  var indus;
  if (resOut.industry === null) {
    console.log("inside if");
    indus = "";
    resOut.industry = "";
  }else{
    console.log("inside else");
    indus = resOut.industry;
    indus = indus.toString();
  }
  console.log("Indus : ",indus);
  // var indus = resOut.industry;
  // indus = indus.toString();
  var business = resOut.business_context;
  business = business.toString();

  var payload = JSON.stringify(resOut);
  console.log("payload : ",payload);
  // var payload = JSON.stringify(resOut);
  // var payload2 = JSON.parse(payload);
  // delete payload2.filename;
  

  var apiUrl = getReuseArchApiUrl;
  var options = {
    method: "post",
    contentType: "application/json",
    payload: payload
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
    "user_ldap": userLdap
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
    var pageElement = userSlide.getPageElements()[5].asShape().getText().getTextStyle().setLinkUrl(hyperLinkUrl).setForegroundColor("#4285f4");

    //===============UserSlide code ended

     var response = UrlFetchApp.fetch(apiUrl,options);
     var responseCode = response.getResponseCode();
     var responseData = response.getContentText();
     var resOut = JSON.parse(responseData);
     console.log("responseData : ",responseData);
     console.log("resOut : ",resOut);
     responseObject.reusableSlideResponse = resOut[0];
     var reuseSlideIdAndPosition = copySlidesFromSuggestions(resOut[0]);
     unskip();
     contGenApi(responseData,userInputId,reuseSlideIdAndPosition);

     var jsonParse = JSON.parse(responseData);
     var filename = jsonParse[1].filename;
     getDriveURLAPI(userInputId,filename);

    var saveSuccessCopiedSlideData = {
      "copied_reusable_count": (totalCopiedSuggestionSlide+totalBlankSuggestionFound+totalFailedSuggestionSlide),
      "contentgeneratedslides" : responseObject.contentGenSlide.contentgeneratedslides,
      "totalTempUrl" : responseObject.contentGenSlide.totalTempUrl,
      "user_input_id" : userInputId
    }
    var saveSuccessCopiedSlideOptions = {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(saveSuccessCopiedSlideData)
    };
    console.log("saveSuccessCopiedSlideData Payload :",saveSuccessCopiedSlideData);
    var responseCopiedSlide = UrlFetchApp.fetch(updateCountsOfCopiedSuggestionSlide,saveSuccessCopiedSlideOptions);
    var resOutCopiedSlide = JSON.parse(responseCopiedSlide.getContentText());
    console.log("resOutCopiedSlide : ",resOutCopiedSlide);

     console.log("response Object : ",responseObject);
     console.log("mappingSourceAndCopiedSlideId : ", mappingSourceAndCopiedSlideId);
     console.log("mappingSourceAndCopiedSlideId Length : ",Object.keys(mappingSourceAndCopiedSlideId).length);
     console.log("Total copied Slides : ",totalCopiedSuggestionSlide);
     console.log("Total blank Slides : ",totalBlankSuggestionFound);
     console.log("Total failed Slides : ",totalFailedSuggestionSlide);
     var returnData = {};
     returnData.status = true;
     return returnData;
   } 
   catch (error) {
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
function contGenApi(responseData,userInputId,reuseSlideIdAndPosition){
  contentGenCount = contentGenCount + 1; //for retry functionality
  var jsonParse = JSON.parse(responseData);
  console.log("jsonParse : ",jsonParse);
  var filename = jsonParse[1].filename;
  var agenda = jsonParse[2].agenda;
  var reusableslide = jsonParse[3].reusableslide;
  console.log("json parse : ",jsonParse);
  console.log("fileName : ",filename);
  try {
  var apiUrl2 = getContentsApiUrl; 
  data2 = {
    "filename" : filename,
    "agenda" : agenda
  };
  var options2 = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(data2)
  };
  var response2 = UrlFetchApp.fetch(apiUrl2, options2);
  var responseCode2 = response2.getResponseCode();
  var responseData2 = response2.getContentText();
  var resOut2 = JSON.parse(responseData2);

  console.log("resOut2 : ",resOut2);
  
  var cont = resOut2.content;
  console.log("content ",cont);
  var jsonContent = cont;
  console.log("jsonContent : ",jsonContent);
  responseObject.contentGenSlide = jsonContent;
  responseObject.filename = filename;
  responseObject.userInputId = userInputId;

  contentGeneration(jsonContent,reuseSlideIdAndPosition);
  removeEmptyPlaceholders();

  }catch(error){
    console.log('Error occurred during ContGen API call:', error.stack);
    if (error.message.includes('Timeout')) {
      if(contentGenCount > 2){
        console.log("TimeOut (18 mins)");
      }else{
      // Trigger the next task if the error is a timeout
      contGenApi(responseData,userInputId,reuseSlideIdAndPosition); //retrying again if the api gets timed out
      }
    }
  }
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
