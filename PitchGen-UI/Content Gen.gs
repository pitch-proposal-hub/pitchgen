function contentGeneration(response2,slideIdAndPosition) {
var jsonData = response2;
console.log("jsonData = ",jsonData.sections);
var slideIdsAndPositions = slideIdAndPosition;

var sectionNo1;
var sectionNo2;
var sectionData;
var slidekey;
var slideData;
var tempUrl;
var placeholders;
var value;
var contentPosition;
var reuseLastSlideId;
var reuseLastSlidePosition;
var presentation = SlidesApp.getActivePresentation();
var contentCopiedSlideId;
var slideCount;
var currentContentPosition;
var sectionCount = Object.keys(slideIdsAndPositions).length;
var sectionCount2 = Object.keys(jsonData.sections).length;
for (var i = 0; i < sectionCount; i++) {
  sectionNo1 = Object.keys(slideIdsAndPositions)[i];
  reuseLastSlideId = slideIdsAndPositions[sectionNo1].id;
  for (var j = 0; j < 1; j++) {
    sectionNo2 = Object.keys(jsonData.sections)[j];
    console.log("sectionNo2 : j : ",sectionNo2);
    sectionData = jsonData.sections[sectionNo2];
    
    if (sectionNo2 == 0 && sectionNo1 == 1) {
      slideCount = Object.keys(sectionData.slides).length;
      for (var k = 0; k < slideCount; k++) {
        slidekey = Object.keys(sectionData.slides)[k];
        slideData = sectionData.slides[slidekey];
        tempUrl = slideData.temp_url;
        
        var sourcePresentation = SlidesApp.openByUrl(tempUrl);
        var sourceSlideId = extractSlideId(tempUrl);
        var sourceSlide = sourcePresentation.getSlideById(sourceSlideId);
        
        console.log("slidekey : ", slidekey);
        
        try{
        var newSlide = presentation.insertSlide(slidekey, sourceSlide);
        // Replace placeholders with actual values
        if(slideData.placeholders){
        placeholders = slideData.placeholders;
        var placeholderCount = Object.keys(placeholders).length;
        for (var l = 0; l < placeholderCount; l++) {
          var placeholder = Object.keys(placeholders)[l];
          value = placeholders[placeholder];
          newSlide.replaceAllText("{{" + placeholder + "}}", value);
        }
        }
        var contentCopiedSlideId0 = newSlide.getObjectId();
        console.log("contentCopiedSlideId0 : ", contentCopiedSlideId0);
        mappingSourceAndCopiedSlideId[contentCopiedSlideId0] = sourceSlideId;
        if (slideData.sources) {
        var text = [];
        if(slideData.sources.length == 0){
          console.log("Source links are empty");
        }
        else{
        for (var m = 0; m < slideData.sources.length; m++) {
          var source = slideData.sources[m];
          text.push(source.url);
          //console.log("URL from sources key: ", source.url);
        }
        var speakerNotes = text.join("\n");
        presentation.getSlideById(contentCopiedSlideId0).getNotesPage().getSpeakerNotesShape().getText().setText(speakerNotes).getTextStyle().setFontFamily("Google Sans").setFontSize(12);
        }
        }
          if(slideData.speaker_notes)
          {
            presentation.getSlideById(contentCopiedSlideId0).getNotesPage().getSpeakerNotesShape().getText().setText(slideData.speaker_notes).getTextStyle().setFontFamily("Google Sans").setFontSize(12);
          }
        }catch(e){
        console.log("Error in slide Insertion and placeholder  : ",e.stack);

        }
        }
        var slides = presentation.getSlides();
        var slideId = contentCopiedSlideId0;
        var position = slides.findIndex(function(slide) {
        return slide.getObjectId() === slideId;
        }) + 1;
      contentPosition = position;
      console.log("contentPosition0 'last' : ", contentPosition);
    } 
  }
  var slides = presentation.getSlides();
      var reuseSlideId = reuseLastSlideId;
      var reuseSlidePosition = slides.findIndex(function(slide) {
        return slide.getObjectId() === reuseSlideId;
      }) + 1;
      reuseLastSlidePosition = reuseSlidePosition;
      console.log("reuseLastSlidePosition : " + reuseLastSlidePosition + " , id : " + reuseSlideId);
  for (var j = 1; j < sectionCount2; j++) {
    sectionNo2 = Object.keys(jsonData.sections)[j];
    console.log("sectionNo2 : j : ",sectionNo2);
    sectionData = jsonData.sections[sectionNo2];
    
    if (sectionNo2 == sectionNo1) {
      console.log("sectionNo2 : ",sectionNo2);
      slideCount = Object.keys(sectionData.slides).length;
      for (var k = 0; k < slideCount; k++) {
        slidekey = Object.keys(sectionData.slides)[k];
        slideData = sectionData.slides[slidekey];
        tempUrl = slideData.temp_url;

        
      var sourcePresentation = SlidesApp.openByUrl(tempUrl);
      var sourceSlideId = extractSlideId(tempUrl);
      var sourceSlide = sourcePresentation.getSlideById(sourceSlideId);
      if(reuseLastSlidePosition == 0){
      console.log("before added ' k ' currentContentPosition : ",contentPosition + 1);
      console.log("k : ",k);
      console.log("slidekey : ", slidekey);
      currentContentPosition = contentPosition + k; 
      console.log("after added ' k ' currentContentPosition : ",currentContentPosition + 1);
      }
      else{
      currentContentPosition = reuseLastSlidePosition + k ;
      console.log("reusable position : ",currentContentPosition + 1);
      }
      
      
      
      // Replace placeholders with actual values
      try{
      var newSlide = presentation.insertSlide(currentContentPosition, sourceSlide);
      if(slideData.placeholders){
      placeholders = slideData.placeholders;
      var placeholderCount = Object.keys(placeholders).length;
      for (var l = 0; l < placeholderCount; l++) {
        var placeholder = Object.keys(placeholders)[l];
        value = placeholders[placeholder];
        newSlide.replaceAllText("{{" + placeholder + "}}", value);
      }
      }
      contentCopiedSlideId = newSlide.getObjectId();
      console.log("contentCopiedSlideId : ", contentCopiedSlideId);
      mappingSourceAndCopiedSlideId[contentCopiedSlideId] = sourceSlideId;
      if (slideData.sources) {
        var text = [];
        if(slideData.sources.length == 0){
          console.log("Source links are empty");
        }
        else{
        for (var m = 0; m < slideData.sources.length; m++) {
          var source = slideData.sources[m];
          text.push(source.url);
         // console.log("URL from sources key: ", source.url);
        }
        var speakerNotes = text.join("\n");
        presentation.getSlideById(contentCopiedSlideId).getNotesPage().getSpeakerNotesShape().getText().setText(speakerNotes).getTextStyle().setFontFamily("Google Sans").setFontSize(12);
        }
      }
        if(slideData.speaker_notes)
        {
          presentation.getSlideById(contentCopiedSlideId).getNotesPage().getSpeakerNotesShape().getText().setText(slideData.speaker_notes).getTextStyle().setFontFamily("Google Sans").setFontSize(12);
        }
      }catch(e){
        console.log("Error in Placeholder : ",e.stack);
        if(e.message.includes("The insertion index")){
        var newSlide = presentation.appendSlide(sourceSlide);
        if(slideData.placeholders){
        placeholders = slideData.placeholders;
        var placeholderCount = Object.keys(placeholders).length;
        for (var l = 0; l < placeholderCount; l++) {
        var placeholder = Object.keys(placeholders)[l];
        value = placeholders[placeholder];
        newSlide.replaceAllText("{{" + placeholder + "}}", value);
        }
        }
        contentCopiedSlideId = newSlide.getObjectId();
        console.log("contentCopiedSlideId : ", contentCopiedSlideId);
        mappingSourceAndCopiedSlideId[contentCopiedSlideId] = sourceSlide.getObjectId();
        if (slideData.sources) {
        var text = [];
        if(slideData.sources.length == 0){
          console.log("Source links are empty");
        }
        else{
        for (var m = 0; m < slideData.sources.length; m++) {
          var source = slideData.sources[m];
          text.push(source.url);
          //console.log("URL from sources key: ", source.url);
        }
        var speakerNotes = text.join("\n");
        presentation.getSlideById(contentCopiedSlideId).getNotesPage().getSpeakerNotesShape().getText().setText(speakerNotes).getTextStyle().setFontFamily("Google Sans").setFontSize(12);
        }
        }
          if(slideData.speaker_notes)
          {
            presentation.getSlideById(contentCopiedSlideId).getNotesPage().getSpeakerNotesShape().getText().setText(slideData.speaker_notes).getTextStyle().setFontFamily("Google Sans").setFontSize(12);
          }
        }
      }
      
    }
    var slides = presentation.getSlides();
    var slideId = contentCopiedSlideId;
    var position = slides.findIndex(function(slide) {
      return slide.getObjectId() === slideId;
    }) + 1;
    contentPosition = position;
    //contentPosition = slidePosition(contentCopiedSlideId);
    console.log("contentPosition 'last' : ", contentPosition);
    }
    else{
    console.log(sectionNo1," : ",sectionNo2);
    }
  }
}
}


function extractSlideId(url){
  var matches = url.match(/#slide=id.(.+)/);
  if(matches && matches.length > 1){
    return matches[1];
  }else{
    throw new Error("`Invalid Presentation Url`");
  }
}