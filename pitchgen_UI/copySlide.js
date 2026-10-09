function copySlidesFromSuggestions(response,presentationId) {
  var stringify = JSON.stringify(response);
  var json = JSON.parse(stringify);
  console.log(json);
  //var jsonData = json[0];
  var jsonData = json;
  var presentation = SlidesApp.openById(presentationId);
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
          try {
            var presId = extractPresentationId(slideUrl);
            var sourcePresentation = getCachedPresentation(presId);
          if (!sourcePresentation) {
            console.warn("Could not open source presentation: " + presId);
            continue;
          }
          console.log("Source slide Url : ",slideUrl);
          var sourceSlideId = extractSlideId(slideUrl);
          console.log("sourceSlideId : ",sourceSlideId);
          var sourceSlide = sourcePresentation.getSlideById(sourceSlideId);
          if (!sourceSlide) {
            console.warn(
                'Could not find source slide by ID: ' + sourceSlideId +
                ' in presentation: ' + presId +
                '. Using O(1) positional fallback.');
            var allSlides = sourcePresentation.getSlides();
            if (allSlides && allSlides.length > 0) {
              // Positional fallback if available (O(1) without scanning all
              // shapes/notes across 100+ slides)
              if (suggestions[i].slide_index != null) {
                var sIdx = parseInt(suggestions[i].slide_index, 10);
                if (!isNaN(sIdx) && sIdx >= 0 && sIdx < allSlides.length) {
                  sourceSlide = allSlides[sIdx];
                  console.log("Found source slide fallback by slide_index: " + sIdx);
                }
              }
              if (!sourceSlide) {
                var fallbackIdx = allSlides.length > 1 ? Math.min(j + 1, allSlides.length - 1) : 0;
                sourceSlide = allSlides[fallbackIdx];
                console.warn("Using fallback slide at index " + fallbackIdx + " in presentation: " + presId);
              }
            }
          }
          if (!sourceSlide) {
            console.warn("Could not find any source slide in presentation: " + presId);
            continue;
          }
          var copiedSlide;
          try {
            copiedSlide = presentation.appendSlide(sourceSlide, SlidesApp.SlideLinkingMode.LINKED);
          } catch (linkErr) {
            console.log("Could not link slide, falling back to unlinked copy: " + linkErr);
            copiedSlide = presentation.appendSlide(sourceSlide);
          }
          var copiedSlideId = copiedSlide.getObjectId();
          console.log("copiedSlideId : ",copiedSlideId);
          mappingSourceAndCopiedSlideId[copiedSlideId] = sourceSlide.getObjectId();

          // Reusable slides are copied cleanly as-is.
          // Full-deck text transformation runs post-assembly across all slides.

          if (!slideIdsAndPositions[section]) {
            slideIdsAndPositions[section] = { ids: [] };
          }
          slideIdsAndPositions[section].ids.push(copiedSlideId);
          // Include source slide link and preserve original speaker notes
          try {
            var notesShape = copiedSlide.getNotesPage().getSpeakerNotesShape();
            var origNotes = "";
            try {
              origNotes = sourceSlide.getNotesPage().getSpeakerNotesShape().getText().asString().trim();
            } catch (e) {}

            var slideLabel = suggestions[i].name || suggestions[i].original_title || "Original Reusable Slide";
            var dateStr = (suggestions[i].date && suggestions[i].date.length > 3) ? (" (" + formatDate(suggestions[i].date) + ")") : "";
            var linkHeader = "🔗 Source Slide: " + slideLabel + dateStr + "\n" + slideUrl;

            var fullNotes = linkHeader;
            if (origNotes && origNotes !== slideLabel) {
              fullNotes += "\n\n--- Original Speaker Notes ---\n" + origNotes;
            }

            var textRange = notesShape.getText();
            textRange.setText(fullNotes);
            textRange.getTextStyle().setFontFamily("Google Sans").setFontSize(11);
          } catch (notesErr) {
            console.log("Warning: could not attach speaker notes to copied slide: " + notesErr);
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
    "repository": repository,
    "slide_job": repository
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

  for(var i=0; i<searchResults.length; i++)
  {
    var item = searchResults[i];
    var deckId = item.deckId;
    if (Array.isArray(deckId)) {
      deckId = deckId[0];
    }
    var slideId = item.slideId;
    if (Array.isArray(slideId)) {
      slideId = slideId[0];
    }

    if (!deckId || !slideId) {
      continue;
    }

    var slideURL = item.slideURL || ("https://docs.google.com/presentation/d/" + deckId + "/edit#slide=id." + slideId);

    try
    {
      const url = Slides.Presentations.Pages.getThumbnail(deckId, slideId, {"thumbnailProperties.mimeType": "PNG"}).contentUrl;
      
      slidesUrl.push({
        date: item.date || "",
        name: item.name || "Reusable Slide",
        slideId: slideId,
        deckId: deckId,
        slideURL: slideURL,
        url: url
      });
    }
    catch(error)
    {
      console.log("Thumbnail generation failed for deck " + deckId + ", slide " + slideId + ": " + error);
      var thumbnailUrl = recursiveGenerateImageURL(deckId, slideId, 3);
      if(thumbnailUrl != null)
      {
        slidesUrl.push({
          date: item.date || "",
          name: item.name || "Reusable Slide",
          slideId: slideId,
          deckId: deckId,
          slideURL: slideURL,
          url: thumbnailUrl
        });
      }
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
    //To get the current position from deck
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
    //To add Speaker Note 
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

/**
 * Deprecated: Replaced by post-assembly transformFullDeckText().
 * If invoked as fallback, updates only the title shape without corrupting body shapes.
 */
function customizeCopiedSlideShapes(copiedSlide, suggestion) {
  if (!suggestion || !copiedSlide) return;

  var isCustRef = suggestion.is_cust_ref || (suggestion._source_datastore_key === 'cust_ref') || suggestion.is_proof_point;
  if (isCustRef) {
    return;
  }

  var custTitle = suggestion.customized_title;
  var origTitle = suggestion.original_title || suggestion.name;

  // 1. Update Title Shape safely if provided
  if (custTitle) {
    if (/^Partnering with /i.test(custTitle) || /^Working with /i.test(custTitle)) {
      if (origTitle && (/build together/i.test(origTitle) || /next steps/i.test(origTitle) || /path forward/i.test(origTitle))) {
        custTitle = origTitle;
      } else {
        custTitle = custTitle.replace(/^Partnering with /i, "Accelerating ").replace(/^Working with /i, "Empowering ");
      }
    }

    var shapes = copiedSlide.getShapes();
    var titleShape = null;

    for (var s = 0; s < shapes.length; s++) {
      var shape = shapes[s];
      var pType = shape.getPlaceholderType();
      var text = shape.getText().asString().trim();

      if (pType === SlidesApp.PlaceholderType.TITLE || pType === SlidesApp.PlaceholderType.CENTERED_TITLE) {
        titleShape = shape;
        break;
      } else if (!titleShape && (s === 0 || text.length > 20) && origTitle && text.includes(origTitle.substring(0, 15))) {
        titleShape = shape;
        break;
      }
    }

    if (titleShape) {
      titleShape.getText().setText(custTitle);
    } else if (origTitle) {
      try {
        copiedSlide.replaceAllText(origTitle, custTitle);
      } catch (e) {}
    }
  }

  // NOTE: Body shapes are preserved intact to avoid destroying card layout/typography.
  // Full deck text transformation is executed post-assembly via transformFullDeckText().
}

