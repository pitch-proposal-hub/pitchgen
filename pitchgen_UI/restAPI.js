function fetchWithRetry(url, options, maxRetries) {
  maxRetries = maxRetries || 3;
  for (var attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      var response = UrlFetchApp.fetch(url, options);
      var code = response.getResponseCode();
      var text = response.getContentText();
      
      var isUnavailable = (code === 503 || code === 429 || code === 500);
      if (!isUnavailable && text && (text.indexOf('"code": 503') !== -1 || text.indexOf('"status": "UNAVAILABLE"') !== -1)) {
        isUnavailable = true;
      }
      
      if (isUnavailable && attempt < maxRetries) {
        console.log("Service temporarily busy (attempt " + attempt + "/" + maxRetries + "). Retrying in 2s...");
        Utilities.sleep(2000 * attempt);
        continue;
      }
      return response;
    } catch (e) {
      if (attempt < maxRetries) {
        console.log("Fetch exception (attempt " + attempt + "/" + maxRetries + "): " + e + ". Retrying...");
        Utilities.sleep(2000 * attempt);
        continue;
      }
      throw e;
    }
  }
}

function apiCall(
    business_context, selectedAudiences, industry, selectedSolutions,
    customer_name, sales_stage, selectedProducts, er_number, requestType,
    selectedSalesPlay, fileId, fileType, contextFileUrl, contextFileMimeType,
    deck_length) {
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

  var stageMap = {
    'S0': 'Qualify (S0)',
    'S1': 'Position & Build (S1)',
    'S2': 'Tech Solutioning (S2)',
    'S3': 'Propose & Negotiate (S3)',
    'S4': 'Mobilize & Deliver (S4)'
  };
  var winCycleMap = {
    'S0': 'WC0: Qualify (S0)',
    'S1': 'WC1: Position & Build (S1)',
    'S2': 'WC2: Tech Solutioning (S2)',
    'S3': 'WC3: Propose & Negotiate (S3)',
    'S4': 'WC4: Mobilize & Deliver (S4)'
  };
  var stageKey = sales_stage || 'S1';
  var resolvedSalesStage = stageMap[stageKey] || stageKey;
  var resolvedWinCycle =
      winCycleMap[stageKey] || ('WC1: ' + resolvedSalesStage);

  var apiUrl = getAgendasApiUrl ;
  var data = {
    'er_number': er_number,
    'customer_name': customer_name,
    'audience': audiences,
    'industry': industry,
    'business_context': business_context,
    'sales_stage': resolvedSalesStage,
    'win_cycle': resolvedWinCycle,
    'solutions': solutions,
    'products': products,
    'user_ldap': userLdap,
    'request_type': requestType,
    'presentation_id': presentationId,
    'salesPlay': salesPlay,
    'context_file_url': contextFileUrl,
    'context_file_mime_type': contextFileMimeType,
    'deck_length': deck_length || 'Standard'
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
  
  console.log("Payload : ",options);
  
   try {
    var response = fetchWithRetry(apiUrl, options, 3);
    var responseData = response.getContentText();
    console.log("responseData : ",responseData);
    var resOut = extractProposalData(responseData,"create_proposal_outline");
    console.log("resOut : ",resOut);
    
    // Support wrapped, nested, and unwrapped GlobalState outline formats
    var stateData = null;
    if (resOut) {
      if (resOut.agendas) {
        stateData = resOut;
      } else if (resOut.data && resOut.data.agendas) {
        stateData = resOut.data;
      } else if (resOut.Status === "True" && resOut.data) {
        stateData = resOut.data;
      } else if (resOut.data) {
        stateData = resOut.data;
      } else {
        stateData = resOut;
      }
    }

    if(stateData && (stateData.agendas || stateData.titles || stateData.outline))
    {
      // var erResponse = UrlFetchApp.fetch(saveErNumber,saveEROptions);
      // var erResponseData = erResponse.getContentText();
      // var erResOut = JSON.parse(erResponseData);
      // console.log(erResOut);
      // if(erResOut.status=="True")
      // {
        try {
          var identityToken = ScriptApp.getIdentityToken();
          var databaseData = {
            'er_number': er_number,
            'customer_name': customer_name,
            'audience': audiences,
            'industry': industry,
            'business_context': business_context,
            'sales_stage': resolvedSalesStage,
            'win_cycle': resolvedWinCycle,
            'user_ldap': userLdap,
            'request_type': requestType,
            'presentation_id': presentationId,
            'salesPlay': salesPlay,
            'filename':
                (resOut.data && resOut.data.filename) || resOut.filename || ''
          };
          var databaseOptions = {
            method: "post",
            contentType: "application/json",
            "headers": {
              "Authorization": "Bearer " + identityToken
            },
            "payload": JSON.stringify(databaseData),
            "muteHttpExceptions": true
          };
          console.log("Database Payload : ", databaseOptions);

          var userSaveResponse = UrlFetchApp.fetch(saveUserInput, databaseOptions);
          var userSaveText = userSaveResponse.getContentText();
          if (userSaveText && !userSaveText.trim().startsWith("<")) {
            var jsoneUserSaveResponse = JSON.parse(userSaveText);
            console.log("userSaveResponse : ", jsoneUserSaveResponse);
            if (jsoneUserSaveResponse && jsoneUserSaveResponse.user_input_id && stateData.context) {
              stateData.context.user_input_id = jsoneUserSaveResponse.user_input_id;
            }
          }
        } catch(dbErr) {
          console.log("Warning: Database user input logging skipped: " + dbErr);
        }

        var titles = stateData.agendas || stateData.titles || {};
        if (Array.isArray(titles)) {
          var normalizedTitles = {};
          titles.forEach(function(item, idx) {
            if (typeof item === 'object' && item !== null) {
              normalizedTitles[String(idx + 1)] = {
                title: item.title || item.name || ("Agenda " + (idx + 1)),
                parts: Array.isArray(item.parts) ? item.parts : [],
                cust_ref: item.cust_ref || "false"
              };
            } else {
              normalizedTitles[String(idx + 1)] = {
                title: String(item),
                parts: [],
                cust_ref: "false"
              };
            }
          });
          titles = normalizedTitles;
        } else if (typeof titles === 'object' && titles !== null) {
          for (var k in titles) {
            if (typeof titles[k] === 'string') {
              titles[k] = {
                title: titles[k],
                parts: [],
                cust_ref: "false"
              };
            } else if (typeof titles[k] === 'object' && titles[k] !== null) {
              if (!Array.isArray(titles[k].parts)) {
                titles[k].parts = [];
              }
            }
          }
        }

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
      var errMsg = (resOut && (resOut.error || resOut.message)) || "Reasoning Engine outline service temporarily busy. Please retry.";
      throw new Error(errMsg);
    }
   } catch (error) {
    console.log("Error in Api call : ",error.stack);
    var returnData = {};
    returnData.status = false;
    returnData.message = (error && error.message) || "Something went wrong";

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

function apiCall2(data,resOut,agendaArr,deleteAgendaId,deleteAgenda,strategy){
  totalCopiedSuggestionSlide = 0;
  totalBlankSuggestionFound = 0;
  totalFailedSuggestionSlide = 0;
  var userLdap = Session.getActiveUser().getEmail();
  console.log("userLdap : ",userLdap);
  var presentation = SlidesApp.getActivePresentation();

  try {
    if (typeof data === "string" && data) {
      try { data = JSON.parse(data); } catch(e) { data = {}; }
    } else if (!data) {
      data = {};
    }
    if (typeof resOut === "string" && resOut) {
      try { resOut = JSON.parse(resOut); } catch(e) { resOut = {}; }
    } else if (!resOut) {
      resOut = {};
    }
    resOut.agendas = agendaArr;
    resOut.deck_strategy = strategy || "smart_hybrid";
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
    for(var i=0;i<audienceArr.length;i++){
      audience = audience + audienceArr[i] + ',';
    }
    if (audience.length > 0) audience = audience.substring(0,audience.length-1);
    
    for(var i=0;i<productArr.length;i++){
      product = product + productArr[i] + ',';
    }
    if (product.length > 0) product = product.substring(0,product.length-1);
    
    for(var i=0;i<solutionArr.length;i++){
      solution = solution + solutionArr[i] + ',';
    }
    if (solution.length > 0) solution = solution.substring(0,solution.length-1);
    
    for(var i=0;i<salesPlayArr.length;i++){
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

    var apiUrl = getReuseArchApiUrl;
    const agentpayload = {
      "class_method": "async_stream_query",
      "input": {
        "user_id": userLdap,
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

    //============== UserSlide Insertion FIRST, then clean old slides ==============
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
    responseObject.userInputs = userInputs;
    console.log("userInputs : ", userInputs);
    var formatPresentationName = function(account, strategicTheme) {
      var rawAccount = (account && account.trim() !== '' && account.trim() !== '-') ? account.trim() : 'Google Cloud';
      var rawTheme = (strategicTheme && strategicTheme.trim() !== '' && strategicTheme.trim() !== '-') ? strategicTheme.trim() : (salesPlay || solution || 'Executive Pitch');
      var date = new Date();
      var monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      var monthYear = monthNames[date.getMonth()] + " " + date.getFullYear();
      return "[PitchGen] " + rawAccount + " | " + rawTheme + " (" + monthYear + ")";
    };
    var presentation_name = formatPresentationName(custName, salesPlay || solution || indus);
    presentation.setName(presentation_name);
    try {
      DriveApp.getFileById(presentation.getId()).setName(presentation_name);
    } catch(dErr) {
      console.log("DriveApp setName fallback: " + dErr);
    }

    var userSlideInserted = false;
    try {
      var template = SlidesApp.openByUrl(userSlideTemplateUrl);
      var userSlideTemp = template.getSlides()[1];

      for(var key in userInputs){
        if (typeof userInputs[key] === 'string') {
          if (userInputs[key].trim() === '') {
            userInputs[key] = '-';
          }
        } else if (Array.isArray(userInputs[key])) {
          userInputs[key] = userInputs[key].length > 0 ? userInputs[key].join(', ') : '-';
        } else if (!userInputs[key]) {
          userInputs[key] = '-';
        } else {
          userInputs[key] = String(userInputs[key]);
        }
      }
      var userSlide = presentation.insertSlide(0, userSlideTemp);
      userSlideInserted = true;
      mappingSourceAndCopiedSlideId[userSlide.getObjectId()] = userSlideTemp.getObjectId();
      for(var key in userInputs){
        userSlide.replaceAllText("{{"+key+"}}", userInputs[key]);
      }
      userSlide.setSkipped(true);

      var presentationUrl = presentation.getUrl();
      responseObject.generatedDeckUrl = presentationUrl;
      var hyperLinkUrl = feedbackUrl;
      console.log("hyperLinkUrl : ", hyperLinkUrl);
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
    } catch (userSlideErr) {
      console.log("Warning: UserSlide insertion skipped: " + userSlideErr);
    }

    // Now safely remove previous pre-existing slides (leaving userSlide at index 0)
    try {
      var allSlides = presentation.getSlides();
      var startIndex = userSlideInserted ? 1 : 1; // If userSlide inserted, keep index 0
      if (allSlides.length > startIndex) {
        for (var i = allSlides.length - 1; i >= startIndex; i--) {
          allSlides[i].remove();
        }
      }
    } catch (cleanupErr) {
      console.log("Warning: Pre-existing slide cleanup skipped: " + cleanupErr);
    }

    //===============UserSlide code ended

     var response = fetchWithRetry(apiUrl, options, 3);
     var responseCode = response.getResponseCode();
     var responseData = response.getContentText();
     //var responseData = dummyReusableAPI;
     console.log("Response String : ",response.toString());
     console.log("responseData : ",responseData);
     var extractedData = extractProposalData(responseData,"slide_generator_skill");
     console.log("Extracted Data :",extractedData);
     if (!Array.isArray(extractedData) && typeof extractedData === 'object' && extractedData !== null) {
       var archName = extractedData.architectural_filename || (extractedData.data && extractedData.data.architectural_filename) || null;
       var outName = extractedData.outputs_filename || (extractedData.data && extractedData.data.outputs_filename) || null;
       extractedData = [
         {"architectural_filename": archName},
         {"outputs_filename": outName},
         {"agenda": 0}
       ];
     }
     var reusableArchFile = Array.isArray(extractedData) ? extractedData.find(function(item) {
       return 'architectural_filename' in item;
     }) : null;
     var contentGenFile = Array.isArray(extractedData) ? extractedData.find(function(item) {
       return 'outputs_filename' in item;
     }) : null;
     // If found, extract the filename; otherwise, set to null
     var reusableArchFilename = reusableArchFile ? reusableArchFile.architectural_filename : null;
     var contentGenFilename = contentGenFile ? contentGenFile.outputs_filename : null;

      console.log("Reusable Filename :", reusableArchFilename);
      console.log("ContentGen Filename :", contentGenFilename);

      if (!reusableArchFilename || !contentGenFilename) {
        console.log("Error: Missing architectural or content generation filename in response:", responseData);
        var returnData = {};
        returnData.status = false;
        returnData.message = (extractedData && extractedData.error) || "Slide generation is currently busy. Please try again.";
        return returnData;
      }

      var bucketName = reuseAndContentJSONBucketName;
      var reusableArchFinalData = readFileFromGCS(bucketName, reusableArchFilename);
      console.log("reusableArchFinalData : ", reusableArchFinalData);
      var resOut = {};
      try {
        if (reusableArchFinalData) {
          resOut = JSON.parse(reusableArchFinalData);
        }
      } catch (parseErr) {
        console.log("Warning: Could not parse reusableArchFinalData: " + parseErr);
      }
      console.log("responseData : ", responseData);
      console.log("resOut : ", resOut);
      responseObject.reusableSlideResponse = resOut;
      var reuseSlideIdAndPosition = {};
      try {
        reuseSlideIdAndPosition = copySlidesFromSuggestions(resOut, presentation.getId());
      } catch (copyErr) {
        console.log("Warning: copySlidesFromSuggestions failed: " + copyErr);
      }
      try {
        unskip(presentation.getId());
      } catch (unskipErr) {}

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
     try {
       const recipientEmail = Session.getActiveUser().getEmail();
       const subject = "[PitchGen] Unable to generate your presentation";
       const ldap = recipientEmail.split('@')[0];
       sendDeckEmailFailure(recipientEmail,subject,ldap);
     } catch (mailErr) {}

     console.log("Error in apicall 2 : ", error ? (error.stack || error.toString()) : "Unknown error");
     var returnData = {};
     var errMsg = error ? error.toString() : "Something went wrong";
     try {
       let errorString = error.toString();
       let jsonString = errorString.substring(errorString.indexOf('{'), errorString.lastIndexOf('}') + 1);
       if (jsonString) {
         let errorObject = JSON.parse(jsonString);
         errMsg = errorObject.error || errorObject.message || errMsg;
       }
     } catch (parseErr) {}

     returnData.status = false;
     returnData.message = errMsg;

     return returnData;
   }
}
function processGeneratedContent(contentGenFilename, reuseSlideIdAndPosition, userInputId, agendaCount, dbCount, erNumber) {
  try {
    console.log("Opportunity Id : ", erNumber);
    var presentation = SlidesApp.getActivePresentation();
    var bucketName = reuseAndContentJSONBucketName;
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

    contentGeneration(resOut2, reuseSlideIdAndPosition, presentation.getId());
    removeEmptyPlaceholders(presentation.getId());

    // Execute unified full-deck text transformation post-assembly
    try {
      transformFullDeckText(
          presentation, responseObject.userInputs || {}, erNumber,
          reuseSlideIdAndPosition);
    } catch (transformErr) {
      console.warn("Notice: full deck post-assembly transform error: " + transformErr);
    }

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
      
      var deckTitle = "PitchGen Presentation";
      try {
        if (resOut2 && resOut2.sections && resOut2.sections.title && resOut2.sections.title.slides && resOut2.sections.title.slides["1"] && resOut2.sections.title.slides["1"].placeholders && resOut2.sections.title.slides["1"].placeholders.title) {
          deckTitle = resOut2.sections.title.slides["1"].placeholders.title;
        } else if (responseObject.userInputs && responseObject.userInputs.customer_name) {
          deckTitle = "PitchGen Proposal for " + responseObject.userInputs.customer_name;
        }
      } catch (titleErr) {}

      const recipientEmail = Session.getActiveUser().getEmail();
      const subject = "[PitchGen] Your presentation is ready: " + deckTitle;
      const deckUrl = SlidesApp.getActivePresentation().getUrl();
      const ldap = recipientEmail.split('@')[0];
      sendDeckEmailSuccess(recipientEmail,subject,deckUrl,ldap);
    } catch(e) {
      console.log("Error in DB logging inside processGeneratedContent: ", e.stack);
    }

    return { status: true };
  } catch (error) {

    const recipientEmail = Session.getActiveUser().getEmail();
    const subject = "[PitchGen] Unable to generate your presentation";
    const ldap = recipientEmail.split('@')[0];
    sendDeckEmailFailure(recipientEmail,subject,ldap);

    console.log("Error in processGeneratedContent: ", error.stack);
    return { status: false, error: error.toString() };
  }
}

function checkFileExists(bucketName, fileName) {
  if (!fileName) {
    fileName = bucketName;
    bucketName = reuseAndContentJSONBucketName;
  }
  if (!fileName) return false;

  var candidateBuckets = [bucketName, reuseAndContentJSONBucketName, 'your-pitchgen-content-bucket', 'your-pitchgen-content-bucket', 'your-pitchgen-content-bucket'];
  var seenBuckets = {};
  var token = ScriptApp.getOAuthToken();
  var encodedFileName = encodeURIComponent(fileName);

  for (var b = 0; b < candidateBuckets.length; b++) {
    var currentBucket = candidateBuckets[b];
    if (!currentBucket || seenBuckets[currentBucket]) continue;
    seenBuckets[currentBucket] = true;

    var url = "https://storage.googleapis.com/storage/v1/b/" + currentBucket + "/o/" + encodedFileName;
    var options = {
      method: 'get',
      headers: {
        Authorization: 'Bearer ' + token
      },
      muteHttpExceptions: true
    };

    try {
      console.log("Checking GCS file existence at: " + url);
      var response = UrlFetchApp.fetch(url, options);
      var code = response.getResponseCode();
      console.log("Status for " + currentBucket + ": " + code);
      if (code === 200) {
        return true;
      }
    } catch (error) {
      console.log("Error checking file existence in " + currentBucket + ": " + error.toString());
    }
  }

  return false;
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
function unskip(presentationId){
  var presentation1 = SlidesApp.openById(presentationId);
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
function removeEmptyPlaceholders(presentationId) {
  try {
    var placeholdersArr = [
      'subtitle',
      'subheader1',
      'subheader2',
      'subheader3',
      'subheader4',
      'subheader5',
      'subheader6',
      'header',
      'title',
      'item1_content',
      'item2_content',
      'item3_content',
      'item4_content',
      'item5_content',
      'item6_content',
      'item7_content',
      'text',
      'item1',
      'item2',
      'item3',
      'item4',
      'item5',
      'item6',
      'item7',
      'item8',
      'item9',
      'item10',
      'text1',
      'text2',
      'sub_item_1',
      'sub_item_2',
      'sub_item_3',
      'sub_item_1_content',
      'sub_item_2_content',
      'sub_item_3_content',
      'num',
      'agenda1',
      'agenda2',
      'agenda3',
      'agenda4',
      'agenda5',
      'agenda6',
      'agenda7',
      'agenda8',
      'agenda9',
      'agenda10',
      'header1',
      'header2',
      'header3',
      'header4',
      'header5',
      'header6',
      'header7',
      'header8',
      'header1_content1',
      'header1_content2',
      'header1_content3',
      'header1_content4',
      'header2_content1',
      'header2_content2',
      'header2_content3',
      'header2_content4',
      'header3_content1',
      'header3_content2',
      'header3_content3',
      'header3_content4',
      'header4_content1',
      'header4_content2',
      'header4_content3',
      'header4_content4',
      'header5_content1',
      'header5_content2',
      'header5_content3',
      'header5_content4',
      'header6_content1',
      'header6_content2',
      'header6_content3',
      'header6_content4',
      'header1_content',
      'header2_content',
      'header3_content',
      'header4_content',
      'header5_content',
      'header6_content',
      'header7_content',
      'header8_content',
      'header9_content',
      'header10_content',
      'header1_subheader1',
      'header1_subheader2',
      'header1_subheader3',
      'header1_subheader4',
      'header1_subheader5',
      'header1_subheader6',
      'header1_subheader7',
      'header1_subheader8',
      'header1_subheader9',
      'header1_subheader1_content',
      'header1_subheader2_content',
      'header1_subheader3_content',
      'header1_subheader4_content',
      'header1_subheader5_content',
      'header1_subheader6_content',
      'header1_subheader7_content',
      'header1_subheader8_content',
      'header1_subheader9_content',
      'header1_subheader10_content',
      'header2_subheader1',
      'header2_subheader2',
      'header2_subheader3',
      'header2_subheader4',
      'header2_subheader1_content',
      'header2_subheader2_content',
      'header2_subheader3_content',
      'header2_subheader4_content',
      'header2_subheader5_content',
      'header2_subheader6_content',
      'subheader1_content1',
      'subheader1_content2',
      'subheader1_content3',
      'subheader1_content4',
      'subheader1_content5',
      'subheader1_content6',
      'subheader1_content7',
      'subheader1_content8',
      'subheader2_content1',
      'subheader2_content2',
      'subheader2_content3',
      'subheader2_content4',
      'subheader2_content5',
      'subheader2_content6',
      'subheader2_content7',
      'subheader2_content8',
      'subheader3_content1',
      'subheader3_content2',
      'subheader3_content3',
      'subheader3_content4',
      'subheader3_content5',
      'subheader3_content6',
      'subheader3_content7',
      'subheader3_content8'
    ];

    var batchRequests = [];
    for (var i = 0; i < placeholdersArr.length; i++) {
      batchRequests.push({
        replaceAllText: {
          containsText:
              {text: '{{' + placeholdersArr[i] + '}}', matchCase: false},
          replaceText: ''
        }
      });
    }

    if (typeof executeBatchedSlideReplacements === 'function') {
      executeBatchedSlideReplacements(presentationId, batchRequests);
    } else if (typeof Slides !== 'undefined' && Slides.Presentations) {
      Slides.Presentations.batchUpdate(
          {requests: batchRequests}, presentationId);
    } else {
      var pres = SlidesApp.openById(presentationId);
      for (var j = 0; j < placeholdersArr.length; j++) {
        pres.replaceAllText('{{' + placeholdersArr[j] + '}}', '');
      }
    }
    console.log(
        'Placeholders removed via batchUpdate (' + batchRequests.length +
        ' tokens)');
  } catch (e) {
    console.log('remove placeholders error : ', e.stack || e);
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

      Thank you for using PitchGen. If you have any feedback, please reach out to us directly at: pitchgen-support@example.com or you have any issues, please raise a bug at PitchGen Bug.

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
      
      <p>Thank you for using PitchGen. If you have any feedback, please reach out to us directly at: <a href="mailto:pitchgen-support@example.com">pitchgen-support@example.com</a> or if you have any issues, please raise a bug at <a href="https://buganizer.corp.google.com/issues/new?component=1874967&template=2181556">PitchGen Bug</a>.</p>
      
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

    Thank you for using PitchGen. If you have any feedback, please reach out to us directly at: pitchgen-support@example.com or if you have any issues, please raise a bug at PitchGen Bug.

    Best regards,
    The PitchHub Team

    Please note: This is an automated notification. If you did not request this deck, please contact our support team immediately.`;

  const htmlBody = `
    <div style="font-family: Arial, sans-serif; color: #333333; line-height: 1.6;">
      <p>Dear ${name},</p>
      
      <p>The deck generation process you initiated on PitchGen has failed. Can you please try to rerun the process?</p>

      <p>Apologies for any inconvenience caused due to the above.</p>
      
      <p>Thank you for using PitchGen. If you have any feedback, please reach out to us directly at: <a href="mailto:pitchgen-support@example.com">pitchgen-support@example.com</a> or if you have any issues, please raise a bug at <a href="https://buganizer.corp.google.com/issues/new?component=1874967&template=2181556" style="color: #1a73e8; text-decoration: none; font-weight: bold;">PitchGen Bug</a>.</p>
      
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
