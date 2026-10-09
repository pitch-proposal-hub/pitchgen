function contentGeneration(response2, slideIdAndPosition, presentationId) {
  var jsonData = response2 || {};
  console.log('jsonData = ', jsonData.sections);
  var slideIdsAndPositions = slideIdAndPosition || {};
  var presentation = getCachedPresentation(presentationId) ||
      SlidesApp.openById(presentationId);

  // Dynamically rename the presentation to: [PitchGen] Account | Strategic
  // Theme (Month Year)
  try {
    var rawCust =
        (jsonData &&
         (jsonData.customer_name || jsonData.account_name ||
          (jsonData.context &&
           (jsonData.context.customer_name || jsonData.context.customer)) ||
          (jsonData.outline &&
           (jsonData.outline.customer_name || jsonData.outline.customer)))) ||
        '';
    if (rawCust === '-' || rawCust.toLowerCase() === 'generic') rawCust = '';

    var rawTheme =
        (jsonData &&
         (jsonData.deck_theme || jsonData.strategic_theme ||
          (jsonData.outline &&
           (jsonData.outline.title || jsonData.outline.deck_theme)) ||
          jsonData.primary_play || jsonData.sales_play ||
          (jsonData.context &&
           (jsonData.context.salesPlay || jsonData.context.industry)) ||
          jsonData.industry)) ||
        'Strategic Transformation';

    if (jsonData && jsonData.sections && jsonData.sections.title &&
        jsonData.sections.title.slides) {
      var titleSlide = jsonData.sections.title.slides['1'] ||
          jsonData.sections.title.slides['0'];
      if (titleSlide && titleSlide.placeholders) {
        var candHdr = titleSlide.placeholders['{{TITLE}}'] ||
            titleSlide.placeholders['title'] ||
            titleSlide.placeholders['Title'];
        if (candHdr) {
          var slideHdr = String(candHdr).replace(/^[0-9\.\-\s]+/, '').trim();
          if (slideHdr && slideHdr.length > 5) {
            rawTheme = slideHdr;
          }
        }
      }
    }

    // Clean rawTheme if it starts with redundant "Pitch Deck for [Account]"
    if (rawCust) {
      var escapedCust = rawCust.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
      rawTheme = rawTheme.replace(
          new RegExp('^Pitch Deck for ' + escapedCust + '[:\\s\\-]*', 'i'), '');
      rawTheme = rawTheme.replace(
          new RegExp('^' + escapedCust + '[:\\s\\-]*', 'i'), '');
    }
    if (!rawTheme || rawTheme.trim() === '') {
      rawTheme = 'Strategic Transformation';
    }

    if (rawTheme.length > 55) {
      rawTheme = rawTheme.substring(0, 52) + '...';
    }

    var now = new Date();
    var monthNames = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct',
      'Nov', 'Dec'
    ];
    var dateStr = monthNames[now.getMonth()] + ' ' + now.getFullYear();

    var formattedTitle = '';
    if (rawCust) {
      formattedTitle =
          '[PitchGen] ' + rawCust + ' | ' + rawTheme + ' (' + dateStr + ')';
    } else {
      formattedTitle = '[PitchGen] ' + rawTheme + ' (' + dateStr + ')';
    }
    presentation.setName(formattedTitle);
    try {
      DriveApp.getFileById(presentation.getId()).setName(formattedTitle);
    } catch (dErr) {
      console.log('DriveApp setName fallback: ' + dErr);
    }
    console.log('Renamed presentation to: ' + formattedTitle);
  } catch (e) {
    console.log('Could not rename presentation: ' + e.toString());
  }

  // Union all section keys from BOTH slideIdsAndPositions and jsonData.sections
  var allKeysMap = {};
  for (var k in slideIdsAndPositions) {
    if (slideIdsAndPositions.hasOwnProperty(k)) allKeysMap[k] = true;
  }
  if (jsonData && jsonData.sections) {
    for (var k in jsonData.sections) {
      if (jsonData.sections.hasOwnProperty(k)) allKeysMap[k] = true;
    }
  }

  function getSectionSortOrder(key) {
    if (!key) return 999;
    if (key === 'title') return 0;
    if (key === 'agenda') return 0.5;
    if (key === 'thank_you') return 9999;
    if (typeof key === 'string' && key.indexOf('divider_') === 0) {
      var divNum = parseFloat(key.replace('divider_', '')) || 0;
      return divNum -
          0.1;  // E.g., divider_1 is 0.9 (comes before section 1 at 1.0)
    }
    return parseFloat(key) || 999;
  }

  var sectionKeys = Object.keys(allKeysMap).sort(function(a, b) {
    return getSectionSortOrder(a) - getSectionSortOrder(b);
  });

  var contentPosition = 0;  // Tracker for the sequential slide position

  for (var i = 0; i < sectionKeys.length; i++) {
    var sectionKey = sectionKeys[i];

    // 1. Insert generated slides for this section first (Title at 0, Agenda at
    // 1, Dividers/Gap slides)
    if (jsonData.sections && jsonData.sections.hasOwnProperty(sectionKey)) {
      var sectionData = jsonData.sections[sectionKey];
      var slideKeys =
          Object.keys(sectionData.slides || {}).sort(function(a, b) {
            return parseInt(a) - parseInt(b);
          });

      for (var k = 0; k < slideKeys.length; k++) {
        var slidekey = slideKeys[k];
        var slideData = sectionData.slides[slidekey];
        var tempUrl = slideData ? slideData.temp_url : null;
        if (!tempUrl) {
          console.log(
              'Skipping slide without temp_url at section ' + sectionKey +
              ', key ' + slidekey);
          continue;
        }

        var presId = extractPresentationId(tempUrl);
        if (!presId) {
          console.log(
              'Could not extract presentation ID from tempUrl: ' + tempUrl);
          continue;
        }
        var sourcePresentation = getCachedPresentation(presId) || (function() {
                                   try {
                                     return SlidesApp.openById(presId);
                                   } catch (e) {
                                     return null;
                                   }
                                 })();
        if (!sourcePresentation) {
          console.log('Failed to open source presentation ' + presId);
          continue;
        }

        var sourceSlideId = extractSlideId(tempUrl);
        if (sourceSlideId) {
          sourceSlideId = sourceSlideId.replace(/[^a-zA-Z0-9_-]/g, '');
        }
        if (!sourceSlideId) {
          console.log('Could not extract slide ID from tempUrl: ' + tempUrl);
          continue;
        }
        var sourceSlide = sourcePresentation.getSlideById(sourceSlideId);
        if (!sourceSlide) {
          console.log(
              'Source slide ' + sourceSlideId + ' not found in presentation ' +
              presId + ', attempting first slide fallback');
          var allSrcSlides = sourcePresentation.getSlides();
          if (allSrcSlides && allSrcSlides.length > 0) {
            sourceSlide = allSrcSlides[0];
          }
        }
        if (!sourceSlide) {
          console.log(
              'Could not locate valid slide in source presentation ' + presId);
          continue;
        }

        var maxInsertIdx = presentation.getSlides().length;
        var targetInsertIndex = Math.min(contentPosition, maxInsertIdx);
        var newSlide;
        var contentCopiedSlideId;

        try {
          newSlide = presentation.insertSlide(targetInsertIndex, sourceSlide);
          contentCopiedSlideId = newSlide.getObjectId();
          mappingSourceAndCopiedSlideId[contentCopiedSlideId] = sourceSlideId;

          // Replace placeholders robustly
          if (slideData.placeholders) {
            replacePlaceholdersRobustly(newSlide, slideData.placeholders);
          }

          // Shrink text to fit shape bounding box
          applyAutofitToSlideShapes(newSlide);

          // Set speaker notes
          setSpeakerNotes(newSlide, slideData);
          contentPosition = targetInsertIndex + 1;
          console.log(
              'Inserted generated slide for section ' + sectionKey +
              ' at index ' + targetInsertIndex +
              '. contentPosition now: ' + contentPosition);

        } catch (e) {
          console.log(
              'Error in slide insertion at position ' + targetInsertIndex +
              ': ' + e.stack);
          try {
            console.log('Fallback: Appending slide instead.');
            newSlide = presentation.appendSlide(sourceSlide);
            contentCopiedSlideId = newSlide.getObjectId();
            mappingSourceAndCopiedSlideId[contentCopiedSlideId] = sourceSlideId;

            if (slideData.placeholders) {
              replacePlaceholdersRobustly(newSlide, slideData.placeholders);
            }
            applyAutofitToSlideShapes(newSlide);
            setSpeakerNotes(newSlide, slideData);
            contentPosition = presentation.getSlides().length;
          } catch (appendError) {
            console.log('Fallback append failed: ' + appendError.stack);
          }
        }
      }
    }

    // 2. Move reusable suggestion slides for this section directly after
    var suggestionIds = (slideIdsAndPositions[sectionKey] &&
                         slideIdsAndPositions[sectionKey].ids) ?
        slideIdsAndPositions[sectionKey].ids :
        [];
    for (var sIdx = 0; sIdx < suggestionIds.length; sIdx++) {
      var sugId = suggestionIds[sIdx];
      if (sugId) {
        var sugSlide = presentation.getSlideById(sugId);
        if (sugSlide) {
          var maxMoveIdx = Math.max(0, presentation.getSlides().length - 1);
          var targetIndex = Math.min(contentPosition, maxMoveIdx);
          sugSlide.move(targetIndex);
          contentPosition = targetIndex + 1;
          console.log(
              'Moved suggestion slide ' + sugId + ' to index ' + targetIndex +
              '. Updated contentPosition to: ' + contentPosition);
        }
      }
    }
  }

  // 3. Global customer name & customer logo replacement across all slides in the deck
  if (rawCust) {
    try {
      presentation.replaceAllText('{{CUSTOMER_NAME}}', rawCust, false);
      presentation.replaceAllText('{{customer_name}}', rawCust, false);
      presentation.replaceAllText('{{CUSTOMER}}', rawCust, false);
      presentation.replaceAllText('{{customer}}', rawCust, false);
      presentation.replaceAllText('{{Customer}}', rawCust, false);
      presentation.replaceAllText('{{Customer Name}}', rawCust, false);
      presentation.replaceAllText('[Customer]', rawCust, false);
      presentation.replaceAllText('[Customer Name]', rawCust, false);
      presentation.replaceAllText('<Customer>', rawCust, false);
      presentation.replaceAllText('<Customer Name>', rawCust, false);
      console.log('Global customer name replacement completed for: ' + rawCust);
    } catch (custErr) {
      console.log('Error in global customer replacement: ' + custErr);
    }
  }

  var custLogoUrl = (typeof jsonData !== 'undefined' && jsonData && jsonData.customer_logo_url) ? String(jsonData.customer_logo_url).trim() : '';
  if (custLogoUrl) {
    try {
      var logoResp = UrlFetchApp.fetch(custLogoUrl, {muteHttpExceptions: true});
      if (logoResp.getResponseCode() === 200) {
        var logoBlob = logoResp.getBlob();
        var replacedCount = 0;
        replacedCount += presentation.replaceAllShapesWithImage('{{CUSTOMER_LOGO}}', logoBlob, true);
        replacedCount += presentation.replaceAllShapesWithImage('{{LOGO}}', logoBlob, true);
        replacedCount += presentation.replaceAllShapesWithImage('[CUSTOMER_LOGO]', logoBlob, true);

        if (replacedCount === 0) {
          var deckSlides = presentation.getSlides();
          if (deckSlides.length > 0) {
            var titleSlideIdx = 0;
            if (deckSlides.length > 1) {
              var s0Shapes = deckSlides[0].getShapes();
              var s0Text = '';
              for (var si = 0; si < s0Shapes.length; si++) {
                try { s0Text += ' ' + s0Shapes[si].getText().asString().toLowerCase(); } catch (e) {}
              }
              if (s0Text.indexOf('internal context') !== -1 || s0Text.indexOf('remove this slide') !== -1) {
                titleSlideIdx = 1;
              }
            }
            deckSlides[titleSlideIdx].insertImage(logoBlob, 618.0, 24.2, 30.2, 30.2);
          }
        }
        console.log('Inserted customer logo from: ' + custLogoUrl);
      }
    } catch (logoErr) {
      console.log('Error inserting customer logo: ' + logoErr);
    }
  }
}

function setSpeakerNotes(slide, slideData) {
  var notesText = '';
  if (slideData.speaker_notes) {
    notesText = slideData.speaker_notes;
  } else if (slideData.sources && slideData.sources.length > 0) {
    var urls = [];
    for (var m = 0; m < slideData.sources.length; m++) {
      if (slideData.sources[m].url) {
        urls.push(slideData.sources[m].url);
      }
    }
    notesText = urls.join('\n');
  }

  if (notesText) {
    // Sanitize markdown fences and internal taxonomy headers
    notesText = notesText.replace(/```markdown\s*/gi, '')
                    .replace(/```\s*$/g, '')
                    .trim();
    notesText = notesText.replace(/^Slide\s*(x|\d+)\s*:\s*[^\n]*\n?/gim, '');
    notesText =
        notesText.replace(/^Framework\s*Section\s*:\s*[^\n]*\n?/gim, '').trim();

    slide.getNotesPage()
        .getSpeakerNotesShape()
        .getText()
        .setText(notesText)
        .getTextStyle()
        .setFontFamily('Google Sans')
        .setFontSize(12);
  }
}

function extractSlideId(url) {
  if (!url) return null;
  var matches = url.match(/#slide=id.(.+)/);
  if (matches && matches.length > 1) {
    return matches[1];
  } else {
    return null;
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
    var titleText = '';
    try {
      var titleShape = slide.getPlaceholder(SlidesApp.PlaceholderType.TITLE);
      if (titleShape) {
        titleText = titleShape.asShape().getText().asString().trim();
      }
    } catch (e) {
      // Slide might not have a title placeholder
    }

    var isDuplicate = false;

    // 1. Check by exact text fingerprint
    if (fingerprint.replace(/\|/g, '').trim().length > 0) {
      if (seenFingerprints.hasOwnProperty(fingerprint)) {
        isDuplicate = true;
        console.log(
            'Duplicate detected by text fingerprint. Removing. Title: ' +
            titleText);
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
          console.log(
              'Duplicate detected by Source ID and Title. Removing. Title: ' +
              titleText + ' (Source ID: ' + sourceId + ')');
        }
      } else {
        seenSourceIds[sourceId] = {title: titleText};
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
      console.log('Failed to remove duplicate slide: ' + removeErr.toString());
    }
  }
}

function getSlideTextFingerprint(slide) {
  var text = '';
  var elements = slide.getPageElements();
  for (var i = 0; i < elements.length; i++) {
    var element = elements[i];
    try {
      if (element.getPageElementType() === SlidesApp.PageElementType.SHAPE) {
        text += element.asShape().getText().asString().trim() + ' | ';
      } else if (
          element.getPageElementType() === SlidesApp.PageElementType.TABLE) {
        var table = element.asTable();
        for (var r = 0; r < table.getNumRows(); r++) {
          for (var c = 0; c < table.getNumColumns(); c++) {
            text += table.getCell(r, c).getText().asString().trim() + ' | ';
          }
        }
      }
    } catch (e) {
      // Ignore reading errors
    }
  }
  return text;
}

/**
 * Robustly replaces placeholder keys in a slide across double braces, single
 * braces, bracket formats, and direct shape text matches.
 */
function replacePlaceholdersRobustly(newSlide, placeholders) {
  if (!newSlide || !placeholders || typeof placeholders !== 'object') return;

  for (var placeholder in placeholders) {
    if (placeholders.hasOwnProperty(placeholder)) {
      var val = placeholders[placeholder] || '';
      // 1. Standard double curly braces {{key}}
      newSlide.replaceAllText('{{' + placeholder + '}}', val);
      // 2. Single curly braces {key}
      newSlide.replaceAllText('{' + placeholder + '}', val);
      // 3. Square brackets [key]
      newSlide.replaceAllText('[' + placeholder + ']', val);
      // 4. Case variants
      newSlide.replaceAllText('{{' + placeholder.toLowerCase() + '}}', val);
      newSlide.replaceAllText('{{' + placeholder.toUpperCase() + '}}', val);
    }
  }

  // Fallback: check all shapes on the slide to replace any unmatched template
  // placeholder labels
  try {
    var pageElements = newSlide.getPageElements();
    for (var i = 0; i < pageElements.length; i++) {
      var elem = pageElements[i];
      if (elem.getPageElementType() === SlidesApp.PageElementType.SHAPE) {
        var shape = elem.asShape();
        var txt = shape.getText().asString().trim();
        if (!txt) continue;

        for (var ph in placeholders) {
          if (placeholders.hasOwnProperty(ph)) {
            var v = placeholders[ph] || '';
            var phLower = ph.toLowerCase();
            var txtLower = txt.toLowerCase();
            if (txtLower === phLower || txtLower === ('{{' + phLower + '}}') ||
                txtLower === ('{' + phLower + '}') ||
                txtLower === ('[' + phLower + ']') ||
                (phLower === 'header1' &&
                 (txtLower === 'header 1' || txtLower === 'title 1')) ||
                (phLower === 'header2' &&
                 (txtLower === 'header 2' || txtLower === 'title 2')) ||
                (phLower === 'header3' &&
                 (txtLower === 'header 3' || txtLower === 'title 3')) ||
                (phLower === 'header1_content' &&
                 (txtLower === 'description 1' || txtLower === 'content 1')) ||
                (phLower === 'header2_content' &&
                 (txtLower === 'description 2' || txtLower === 'content 2')) ||
                (phLower === 'header3_content' &&
                 (txtLower === 'description 3' || txtLower === 'content 3')) ||
                (phLower === 'item1' && txtLower === 'item 1') ||
                (phLower === 'item2' && txtLower === 'item 2') ||
                (phLower === 'item3' && txtLower === 'item 3')) {
              shape.getText().setText(v);
            }
          }
        }
      }
    }
  } catch (e) {
    console.log('Warning in replacePlaceholdersRobustly shape scan: ' + e);
  }
}

/**
 * Automatically sets text autofit on shapes to shrink text on overflow.
 */
function applyAutofitToSlideShapes(slide) {
  if (!slide) return;
  try {
    var elements = slide.getPageElements();
    for (var i = 0; i < elements.length; i++) {
      var elem = elements[i];
      if (elem.getPageElementType() === SlidesApp.PageElementType.SHAPE) {
        var shape = elem.asShape();
        try {
          if (shape.getText() && shape.getText().getAutofit) {
            shape.getText().getAutofit().setAutofitType(
                SlidesApp.AutofitType.SHRINK_TEXT_ON_OVERFLOW);
          }
        } catch (autofitErr) {
          // Shape does not support autofit or already configured
        }
      }
    }
  } catch (e) {
    console.log('Warning in applyAutofitToSlideShapes: ' + e);
  }
}
