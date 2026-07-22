function copySlidesFromSuggestions(response) {
  var stringify = JSON.stringify(response);
  var json = JSON.parse(stringify);
  console.log(json);
  //var jsonData = json[0];
  var jsonData = json;
  var presentation = SlidesApp.getActivePresentation();
  var slideIdsAndPositions = {};
  
  for (var section in jsonData) {
    if (jsonData.hasOwnProperty(section)) {
      var sectionData = jsonData[section];
      var suggestions = sectionData.suggestions;
      if (suggestions.length > 0) {
        var totalFailedSlides = 0;
        for (var i = 0; i < suggestions.length; i++) {
          var values = suggestions[i].values;
        for(var j = 0; j < values.length; j++){
          var slideUrl = suggestions[i].values[j];
          console.log("i : ",i);
          console.log("j : ",j);
          try{
          var presId = extractPresentationId(slideUrl);
          var sourcePresentation = SlidesApp.openById(presId);
          console.log("Source slide Url : ",slideUrl);
          var sourceSlideId = extractSlideId(slideUrl);
          console.log("sourceSlideId : ",sourceSlideId);
          var sourceSlide = sourcePresentation.getSlideById(sourceSlideId);
          var copiedSlide = presentation.appendSlide(sourceSlide);
          var copiedSlideId = copiedSlide.getObjectId();
          console.log("copiedSlideId : ",copiedSlideId);
          mappingSourceAndCopiedSlideId[copiedSlideId] = sourceSlideId;
          if (!slideIdsAndPositions[section]) {
            slideIdsAndPositions[section] = { ids: [] };
          }
          slideIdsAndPositions[section].ids.push(copiedSlideId);
          if (suggestions[i].hasOwnProperty('is_golden')) {
          var notes = suggestions[i].name + " ("+ formatDate(suggestions[i].date)+")";
          presentation.getSlideById(copiedSlideId).getNotesPage().getSpeakerNotesShape().getText().setText(notes).getTextStyle().setFontFamily("Google Sans").setBold(true).setFontSize(14).setLinkUrl(slideUrl);
          }
          else{
            console.log("Customer Reference Slide");
          }
          totalCopiedSuggestionSlide = totalCopiedSuggestionSlide + 1;
          }
          catch(error){
          totalFailedSlides = totalFailedSlides + 1;
          console.log("Error in copySlidesFromSuggestions : ",error.stack);
          if(suggestions.length == 1){
            slideIdsAndPositions[section] = { ids: [] };
          }
          if(suggestions.length==totalFailedSlides)
          {
            slideIdsAndPositions[section] = { ids: [] };
          }
          }
          }
        }
      } else {
        slideIdsAndPositions[section] = { ids: [] };
      }
    }
  }
  
  // Backfill any missing standard keys to ensure they are processed by contentGeneration
  var standardKeys = ["title", "agenda", "thank_you"];
  for (var k = 1; k <= 10; k++) {
    standardKeys.push(k.toString());
    standardKeys.push("divider_" + k);
  }
  for (var idx = 0; idx < standardKeys.length; idx++) {
    var key = standardKeys[idx];
    if (!slideIdsAndPositions.hasOwnProperty(key)) {
      slideIdsAndPositions[key] = { ids: [] };
    }
  }

  console.log("slideIdsAndPositions : ",slideIdsAndPositions);

  return slideIdsAndPositions;
  //content4(slideIdsAndPositions);
}

function extractPresentationId(url) {
  var match = url.match(/\/d\/([a-zA-Z0-9-_]+)/);
  return match ? match[1] : null;
}

function extractSlideId(url){
  var matches = url.match(/#slide=id.(.+)/);
  if(matches && matches.length > 1){
    return matches[1];
  }else{
    throw new Error("`Invalid Presentation Url`");
  }
}
function formatDate(dateStr){

  var date = new Date(dateStr);
  var monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  var day = date.getDate();
  var month = monthNames[date.getMonth()];
  var year = date.getFullYear();
  var dayWithSuffix = day + getSuffix(day);
  console.log(dayWithSuffix + " " + month + " " + year);
  return dayWithSuffix + " " + month + " " + year;
}

function getSuffix(day){
  if(day > 3 && day < 21) return "th";
  switch(day % 10){
    case 1: return "st";
    case 2: return "nd";
    case 3: return "rd";
    default: return "th";
  }
}


function searchSlide(searchContentInput, repository)
{
  var strictSearch = false;
  var firstChar = searchContentInput.charAt(0);
  var lastChar = searchContentInput.charAt(searchContentInput.length - 1);
  var hasSingleQuote = (firstChar === "'" && lastChar === "'");
  var hasDoubleQuote = (firstChar === '"' && lastChar === '"');
  var userLdap = Session.getActiveUser().getEmail();

  if(hasSingleQuote || hasDoubleQuote)
  {
    strictSearch = true;
  }
  var returnData = {};
  //var apiUrl = serviceUrl+"searchSlide";
  var apiUrl = searchSlideApiURL;
  var data = {
    "search_query": searchContentInput,
    "strict_search": strictSearch,
    "user_ldap" : userLdap,
    "repository": repository
  };
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
  // console.log("Search Slide Request : ",data);
  // var options = {
  //   method: "post",
  //   contentType: "application/json",
  //   payload: JSON.stringify(data)
  // };
  try
  {
    var response = UrlFetchApp.fetch(apiUrl,options);
    var responseData = response.getContentText();
    console.log("ResponseData : ",responseData);
    var resOut = extractProposalData(responseData,"sidebar_search");
    //var resOut = JSON.parse(responseData);
    console.log("ResOut : ",resOut);
    
    if (resOut && resOut.error) {
      returnData.status = false;
      returnData.flag = "ERROR";
      returnData.message = resOut.error;
      return returnData;
    }
    
    var slidesUrl = [];
    var searchResults = resOut ? resOut.search_results : null;
    if (!searchResults) {
      returnData.status = false;
      returnData.flag = "NO_RESULT";
      returnData.message = "No search results returned.";
      return returnData;
    }

    slidesUrl = generateImageURL(searchResults);

    returnData.status = true;
    returnData.image = slidesUrl;

      console.log("Total Request : "+searchResults.length+" Generated Thumbnail : "+slidesUrl.length);
      console.log(returnData);

    //}
    
    return returnData;
    
  }
  catch(error)
  {
    console.log(error.stack);
    returnData.status = false;
    returnData.flag = "OTHER";
    returnData.message = "Error !";
    return returnData;
  }
}

function generateImageURL(searchResults)
{
  var slidesUrl = [];
  var slidesObj = {};

  for(var i=0; i<searchResults.length; i++)
  {
    try
    {
      slidesObj = {};
      const url = Slides.Presentations.Pages.getThumbnail(searchResults[i].deckId, searchResults[i].slideId, {"thumbnailProperties.mimeType": "PNG"}).contentUrl;
      
      slidesObj.date = searchResults[i].date;
      slidesObj.name = searchResults[i].name;
      slidesObj.slideId = searchResults[i].slideId;
      slidesObj.deckId = searchResults[i].deckId;
      slidesObj.slideURL = searchResults[i].slideURL;
      slidesObj.url = url;
      slidesUrl.push(slidesObj);    
    }
    catch(error)
    {
      if(error.name=="GoogleJsonResponseException")
      {
        console.log(error.name+" : Recursive call to the function once again for creating the thumbnails");
        var totalExecute = 5;
        var thumbnailUrl = recursiveGenerateImageURL(searchResults[i].deckId, searchResults[i].slideId, totalExecute);
        if(thumbnailUrl != null)
        {
          slidesObj = {};
          slidesObj.date = searchResults[i].date;
          slidesObj.name = searchResults[i].name;
          slidesObj.slideId = searchResults[i].slideId;
          slidesObj.deckId = searchResults[i].deckId;
          slidesObj.slideURL = searchResults[i].slideURL;
          slidesObj.url = thumbnailUrl;
          slidesUrl.push(slidesObj);
        }
      }
      else
      {
        console.log(error.stack);
      }
      continue;
    }
  }
  return slidesUrl;
}
function recursiveGenerateImageURL(deckId, slideId, totalExecute)
{
  var url = null;

  try{
    if(totalExecute>0)
    {
      url = Slides.Presentations.Pages.getThumbnail(deckId, slideId, {"thumbnailProperties.mimeType": "PNG"}).contentUrl;
    }
    else
    {
      return url;
    }
  }
  catch(error)
  {
    recursiveGenerateImageURL(deckId, slideId, (totalExecute-1))
  }

  return url;
}


function searchSlideInsertion(resData){
  var searchContentInput = resData.searchInput;
  var strictSearch = false;
  var firstChar = searchContentInput.charAt(0);
  var lastChar = searchContentInput.charAt(searchContentInput.length - 1);
  var hasSingleQuote = (firstChar === "'" && lastChar === "'");
  var hasDoubleQuote = (firstChar === '"' && lastChar === '"');
  var userLdap = Session.getActiveUser().getEmail();

  if(hasSingleQuote || hasDoubleQuote)
  {
    strictSearch = true;
  }

  var presentationId = SlidesApp.getActivePresentation().getId();
  var userLdap = Session.getActiveUser().getEmail();
  // var saveOpportunityData = {
  //   "presentation_id": presentationId,
  //   "opportunityId" : resData.erId,
  //   "requested_by" : userLdap
  // }
  // var saveEROptions = {
  //   method: "post",
  //   contentType: "application/json",
  //   payload: JSON.stringify(saveOpportunityData)
  // };
  var identityToken = ScriptApp.getIdentityToken();
  var saveSearchData = {
    "content": searchContentInput,
    "strict_search": strictSearch,
    "action" : "add_search",
    "opportunity_id" : resData.erId,
    "user_ldap" : userLdap,
    "presentation_id" : presentationId
  };
  var saveSearchOptions = {
    method: "post",
    contentType: "application/json",
    "headers": {
      "Authorization": "Bearer " + identityToken
    },
    "payload": JSON.stringify(saveSearchData)
  };
  console.log("Database Payload : ",saveSearchOptions);
  try{  
    var currentSlideId = SlidesApp.getActivePresentation().getSelection().getCurrentPage().getObjectId();
    var allSlides = SlidesApp.getActivePresentation().getSlides();
    var presentation = SlidesApp.getActivePresentation();
    var position = 0;
    for (var j = 0; j < allSlides.length; j++) 
    {
      var slide = allSlides[j];
      if (slide.getObjectId() === currentSlideId) {
        position = (j + 1); 
        break;
      }
    }

    var deckUrl = resData.slideUrl;
    var deckId = resData.deckId;
    console.log("Source slide Url : ",deckId);
    var sourcePresentation = SlidesApp.openById(deckId);
    var sourceSlideId = resData.slideId;
    var sourceSlide = sourcePresentation.getSlideById(sourceSlideId);
    var copiedSlide = presentation.insertSlide(position,sourceSlide);
    copiedSlide.setSkipped(false);
    var copiedSlideId = copiedSlide.getObjectId();
    console.log("copiedSlideId : ",copiedSlideId);
    var notes = resData.name + " ("+ formatDate(resData.date)+")";
    presentation.getSlideById(copiedSlideId).getNotesPage().getSpeakerNotesShape().getText().setText(notes).getTextStyle().setFontFamily("Google Sans").setBold(true).setFontSize(14).setLinkUrl(deckUrl);

    var searchResponse = UrlFetchApp.fetch(saveEditAction,saveSearchOptions);
    var searchResponseData = searchResponse.getContentText();
    var searchResOut = JSON.parse(searchResponseData);
    console.log("saveSearchResponseData : ",searchResOut);
    if(searchResOut.status=='True')
    {
      return true;
    }
    else
    {
      return false;
    }
  }catch(e){
    console.log("Error in searchSlideInsertion function : ",e.stack);
    return false;

  }

}
