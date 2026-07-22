function contentGeneration(response2, slideIdAndPosition) {
  var jsonData = response2;
  console.log("jsonData = ", jsonData.sections);
  var slideIdsAndPositions = slideIdAndPosition;
  var presentation = SlidesApp.getActivePresentation();

  var sectionKeys = Object.keys(slideIdsAndPositions).sort(function(a, b) {
    if (a === "title") return -1;
    if (b === "title") return 1;
    if (a === "agenda") {
      if (b === "title") return 1;
      return -1;
    }
    if (b === "agenda") {
      if (a === "title") return -1;
      return 1;
    }
    if (a === "thank_you") return 1;
    if (b === "thank_you") return -1;
    
    var numA = parseFloat(a.replace("divider_", "")) - (a.startsWith("divider_") ? 0.1 : 0);
    var numB = parseFloat(b.replace("divider_", "")) - (b.startsWith("divider_") ? 0.1 : 0);
    return numA - numB;
  });

  var contentPosition; // Tracker for the last inserted slide position

  for (var i = 0; i < sectionKeys.length; i++) {
    var sectionKey = sectionKeys[i];
    var targetContentKey = sectionKey;
    if (sectionKey.startsWith("divider_")) {
      targetContentKey = sectionKey.replace("divider_", "");
    }
    // Move suggestion slides if this is the content section (not the divider)
    if (!sectionKey.startsWith("divider_")) {
      var suggestionIds = (slideIdsAndPositions[sectionKey] && slideIdsAndPositions[sectionKey].ids) ? slideIdsAndPositions[sectionKey].ids : [];
      for (var sIdx = 0; sIdx < suggestionIds.length; sIdx++) {
        var sugId = suggestionIds[sIdx];
        if (sugId) {
          var sugSlide = presentation.getSlideById(sugId);
          if (sugSlide) {
            var targetIndex = (contentPosition !== undefined ? contentPosition : 0);
            sugSlide.move(targetIndex);
            contentPosition = targetIndex + 1;
            console.log("Moved suggestion slide " + sugId + " to index " + targetIndex + ". Updated contentPosition to: " + contentPosition);
          }
        }
      }
    }

    // Check if we have generated slides for this section
    if (jsonData.sections && jsonData.sections.hasOwnProperty(sectionKey)) {
      var sectionData = jsonData.sections[sectionKey];
      var slideKeys = Object.keys(sectionData.slides).sort(function(a, b) {
        return parseInt(a) - parseInt(b);
      });

      for (var k = 0; k < slideKeys.length; k++) {
        var slidekey = slideKeys[k];
        var slideData = sectionData.slides[slidekey];
        var tempUrl = slideData.temp_url;

        var presId = extractPresentationId(tempUrl);
        var sourcePresentation = SlidesApp.openById(presId);
        var sourceSlideId = extractSlideId(tempUrl);
        var sourceSlide = sourcePresentation.getSlideById(sourceSlideId);

        var currentContentPosition = (contentPosition !== undefined ? contentPosition : 1);

        var newSlide;
        var contentCopiedSlideId;

        try {
          newSlide = presentation.insertSlide(currentContentPosition, sourceSlide);
          contentCopiedSlideId = newSlide.getObjectId();
          mappingSourceAndCopiedSlideId[contentCopiedSlideId] = sourceSlideId;

          // Replace placeholders
          if (slideData.placeholders) {
            var placeholders = slideData.placeholders;
            for (var placeholder in placeholders) {
              if (placeholders.hasOwnProperty(placeholder)) {
                newSlide.replaceAllText("{{" + placeholder + "}}", placeholders[placeholder]);
              }
            }
          }

          // Set speaker notes
          setSpeakerNotes(newSlide, slideData);

        } catch (e) {
          console.log("Error in slide insertion at position " + currentContentPosition + ": " + e.stack);
          if (e.message.includes("The insertion index")) {
            try {
              console.log("Fallback: Appending slide instead.");
              newSlide = presentation.appendSlide(sourceSlide);
              contentCopiedSlideId = newSlide.getObjectId();
              mappingSourceAndCopiedSlideId[contentCopiedSlideId] = sourceSlideId;

              if (slideData.placeholders) {
                var placeholders = slideData.placeholders;
                for (var placeholder in placeholders) {
                  if (placeholders.hasOwnProperty(placeholder)) {
                    newSlide.replaceAllText("{{" + placeholder + "}}", placeholders[placeholder]);
                  }
                }
              }
              setSpeakerNotes(newSlide, slideData);
            } catch (appendError) {
              console.log("Fallback append failed: " + appendError.stack);
            }
          }
        }

        // Update contentPosition if insertion was successful
        if (contentCopiedSlideId) {
          var updatedSlides = presentation.getSlides();
          var position = updatedSlides.findIndex(function(slide) {
            return slide.getObjectId() === contentCopiedSlideId;
          }) + 1;
          contentPosition = position;
          console.log("Updated contentPosition to: ", contentPosition);
        }
      }
    }
  }
}

function setSpeakerNotes(slide, slideData) {
  var notesText = "";
  if (slideData.speaker_notes) {
    notesText = slideData.speaker_notes;
  } else if (slideData.sources && slideData.sources.length > 0) {
    var urls = [];
    for (var m = 0; m < slideData.sources.length; m++) {
      if (slideData.sources[m].url) {
        urls.push(slideData.sources[m].url);
      }
    }
    notesText = urls.join("\n");
  }

  if (notesText) {
    slide.getNotesPage().getSpeakerNotesShape().getText().setText(notesText)
      .getTextStyle().setFontFamily("Google Sans").setFontSize(12);
  }
}

function extractSlideId(url) {
  var matches = url.match(/#slide=id.(.+)/);
  if (matches && matches.length > 1) {
    return matches[1];
  } else {
    throw new Error("`Invalid Presentation Url`");
  }
}

function removeDuplicateSlides() {
  var presentation = SlidesApp.getActivePresentation();
  var slides = presentation.getSlides();
  var seenFingerprints = {};
  var seenSourceIds = {};
  var slidesToRemove = [];

  for (var i = 0; i < slides.length; i++) {
    var slide = slides[i];
    
    // Skip the user inputs slide (first slide)
    if (i === 0) continue;
    
    var slideId = slide.getObjectId();
    var sourceId = mappingSourceAndCopiedSlideId[slideId];
    var fingerprint = getSlideTextFingerprint(slide);
    
    // Get slide title if it exists
    var titleText = "";
    try {
      var titleShape = slide.getPlaceholder(SlidesApp.PlaceholderType.TITLE);
      if (titleShape) {
        titleText = titleShape.asShape().getText().asString().trim();
      }
    } catch(e) {
      // Slide might not have a title placeholder
    }

    var isDuplicate = false;

    // 1. Check by exact text fingerprint
    if (fingerprint.replace(/\|/g, "").trim().length > 0) {
      if (seenFingerprints.hasOwnProperty(fingerprint)) {
        isDuplicate = true;
        console.log("Duplicate detected by text fingerprint. Removing. Title: " + titleText);
      } else {
        seenFingerprints[fingerprint] = true;
      }
    }

    // 2. Check by source ID + Title
    if (!isDuplicate && sourceId) {
      if (seenSourceIds.hasOwnProperty(sourceId)) {
        var existingInfo = seenSourceIds[sourceId];
        if (existingInfo.title === titleText && titleText.length > 0) {
          isDuplicate = true;
          console.log("Duplicate detected by Source ID and Title. Removing. Title: " + titleText + " (Source ID: " + sourceId + ")");
        }
      } else {
        seenSourceIds[sourceId] = { title: titleText };
      }
    }

    if (isDuplicate) {
      slidesToRemove.push(slide);
    }
  }

  // Remove slides from last to first
  for (var j = slidesToRemove.length - 1; j >= 0; j--) {
    try {
      slidesToRemove[j].remove();
    } catch (removeErr) {
      console.log("Failed to remove duplicate slide: " + removeErr.toString());
    }
  }
}

function getSlideTextFingerprint(slide) {
  var text = "";
  var elements = slide.getPageElements();
  for (var i = 0; i < elements.length; i++) {
    var element = elements[i];
    try {
      if (element.getPageElementType() === SlidesApp.PageElementType.SHAPE) {
        text += element.asShape().getText().asString().trim() + " | ";
      } else if (element.getPageElementType() === SlidesApp.PageElementType.TABLE) {
        var table = element.asTable();
        for (var r = 0; r < table.getNumRows(); r++) {
          for (var c = 0; c < table.getNumColumns(); c++) {
            text += table.getCell(r, c).getText().asString().trim() + " | ";
          }
        }
      }
    } catch(e) {
      // Ignore reading errors
    }
  }
  return text;
}