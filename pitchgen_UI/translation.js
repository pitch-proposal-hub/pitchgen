function createJsonRequestForSlideTextFormatting(targetLanguage , isFullDeck, opportunityId) {
  try{
    console.log("User Id : ",Session.getActiveUser().getEmail());
    var userLdap = Session.getActiveUser().getEmail();
    var returnData = {};
    const presentation = SlidesApp.getActivePresentation();
    const presentationId = presentation.getId();
    var slides = [];
    if (isFullDeck == false) {

      var pageRange = presentation.getSelection().getPageRange();
      if(!pageRange)
      {
        returnData.status = false;
        returnData.flag = "NO_FILE_SELECTED";
        return returnData;
      }
      var totalSelectedPages = pageRange.getPages();

    // Convert Page objects to Slide objects
      for (var i = 0; i < totalSelectedPages.length; i++) {
        var page = totalSelectedPages[i];
        if (page.getPageType() === SlidesApp.PageType.SLIDE) {
          slides.push(page.asSlide()); // Convert to Slide
        }
      }
    } else if (isFullDeck == true) {
      slides = presentation.getSlides(); // Get all slides
    }

    const slideData = {};

    for (let i = 0; i < slides.length; i++) {
      const slide = slides[i];
      const slideId = slide.getObjectId();
      console.log("Slide Id : ",slideId);
      const slideShapeData = {};
      const slideTableData = {};

      // Initialize counters for shapes and tables
      let shapeCounter = 0;
      var tableCellPosition = "";
      // Get all page elements on the slide
      const elements = slide.getPageElements();

      for (let j = 0; j < elements.length; j++) {
        const element = elements[j];

        // Check if the element is a shape
        if (element.getPageElementType() === SlidesApp.PageElementType.SHAPE) {
          if(element.asShape().getText().asString().trim() !== ""){
            const shape = element.asShape();
            const shapeId = shape.getObjectId();
            const shapeCellData = {}; // Store text segments for the shape

            const textRange = shape.getText();
            if (textRange && textRange.getLength() > 0) {
              let currentSegment = {
                Text: "",
                style: {}
              };

              for (let k = 0; k < textRange.getLength(); k++) {
                const charRange = textRange.getRange(k, k + 1);
                const charStyle = charRange.getTextStyle();
                const char = charRange.asString();

                var rgbColor = null;
                var color = charStyle.getForegroundColor(); // Get text color
                
                if(color)
                {
                  var colorType = color.getColorType();
                  if (colorType == SlidesApp.ColorType.RGB) {
                    rgbColor = color.asRgbColor().asHexString(); // Get color as hex
                  } 
                }

                const newStyle = {
                  Bold: charStyle.isBold(),
                  Italic: charStyle.isItalic(),
                  Underline: charStyle.isUnderline(),
                  FontSize: charStyle.getFontSize(),
                  FontStyle: charStyle.getFontFamily(),
                  LinkUrl: charStyle.getLink() ? charStyle.getLink().getUrl() : null,
                  FontColor: rgbColor
                };

                if (JSON.stringify(newStyle) !== JSON.stringify(currentSegment.style) && currentSegment.Text !== "") {
                  // Store the previous segment with a numbered key
                  shapeCellData[shapeCounter] = {
                    Text: currentSegment.Text,
                    ...currentSegment.style
                  };
                  shapeCounter++;
                  currentSegment = {
                    Text: "",
                    style: newStyle
                  };
                }

                currentSegment.Text += char;
                currentSegment.style = newStyle;
              }

              // Add the last segment, trimming only if it has a newline character
              if (currentSegment.Text) {
                let trimmedText = currentSegment.Text.endsWith('\n') ? currentSegment.Text.slice(0, -1) : currentSegment.Text;

                if (trimmedText !== "") {
                    shapeCellData[shapeCounter] = {
                      Text: trimmedText,
                      ...currentSegment.style
                    };
                    shapeCounter++;
                }
              }
              shapeCounter = 0;
            }

            if (Object.keys(shapeCellData).length > 0) {
              slideShapeData[shapeId] = shapeCellData;
            }
          }
        }

        // Check if the element is a table
        if (element.getPageElementType() === SlidesApp.PageElementType.TABLE) {
          const table = element.asTable();
          const tableId = table.getObjectId();
          const numRows = table.getNumRows();
          const numCols = table.getNumColumns();
          const tableCellData = {}; // Store text segments for the table

          for (let row = 0; row < numRows; row++) {
            for (let col = 0; col < numCols; col++) {
              tableCellPosition = row + "_" + col;
              const cell = table.getCell(row, col);
              if(cell.getMergeState() == SlidesApp.CellMergeState.MERGED){
                continue;
              }
              const textRange = cell.getText();
              const cellSegmentData = {};

              if (textRange && textRange.getLength() > 0) {
                let currentSegment = {
                  Text: "",
                  style: {}
                };
                let segmentIndex = 0;

                for (let k = 0; k < textRange.getLength(); k++) {
                  const charRange = textRange.getRange(k, k + 1);
                  const charStyle = charRange.getTextStyle();
                  const char = charRange.asString();

                  const newStyle = {
                    Bold: charStyle.isBold(),
                    Italic: charStyle.isItalic(),
                    Underline: charStyle.isUnderline(),
                    FontSize: charStyle.getFontSize(),
                    FontStyle: charStyle.getFontFamily(),
                    LinkUrl: charStyle.getLink() ? charStyle.getLink().getUrl() : null,
                  };

                  if (JSON.stringify(newStyle) !== JSON.stringify(currentSegment.style) && currentSegment.Text !== "") {
                    // Store the previous segment with a numbered key
                    cellSegmentData[segmentIndex] = {
                      Text: currentSegment.Text,
                      ...currentSegment.style
                    };
                    segmentIndex++;
                    currentSegment = {
                      Text: "",
                      style: newStyle
                    };
                  }

                  currentSegment.Text += char;
                  currentSegment.style = newStyle;
                }

                // Add the last segment, trimming only if it has a newline character
                if (currentSegment.Text) {
                  cellSegmentData[segmentIndex] = {
                    Text: currentSegment.Text.endsWith('\n') ? currentSegment.Text.slice(0, -1) : currentSegment.Text,
                    ...currentSegment.style
                  };
                }
              }
              if (Object.keys(cellSegmentData).length > 0) {
                tableCellData[tableCellPosition] = cellSegmentData;
              }
            }
          }

          if (Object.keys(tableCellData).length > 0) {
            slideTableData[tableId] = tableCellData;
          }
        }
      }

      var notesText = "";
      try {
        var notesPage = slide.getNotesPage();
        if (notesPage) {
          var notesShape = notesPage.getSpeakerNotesShape();
          if (notesShape && notesShape.getText()) {
            notesText = notesShape.getText().asString().trim();
          }
        }
      } catch(e) {}

      slideData[slideId] = {
        shapes: slideShapeData,
        tables: slideTableData,
        speaker_notes: notesText
      };
    }

    const jsonData = {
      "presentationId" : presentationId,
      "targetLanguage": targetLanguage,
      "isFullDeckTranslation": isFullDeck,
      [presentationId]: slideData,
      "action": "translate",
      "user_ldap": userLdap
    };
    Logger.log(JSON.stringify(jsonData, null, 2));
    var jsonString = JSON.stringify(jsonData, null, 2);
    var apiUrl = translateApiUrl;
    // var options = {
    //   method: "post",
    //   contentType: "application/json",
    //   payload: jsonString
    // };
    const payload = {
      "class_method": "async_stream_query",
      "input": {
      "user_id":userLdap,
      "message": jsonString
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

    var response = UrlFetchApp.fetch(apiUrl,options);
    var responseData = response.getContentText();
    console.log("Response Data : ",responseData);
    var resOut = extractProposalData(responseData,'process_json_payload');
    console.log("ResOut : ",resOut);
    var gcsRegex = /(?:gs:\/\/|storage\.googleapis\.com\/)([^\/\s]+)\/(.+)$/;
    var match = resOut.data.response.match(gcsRegex);
    var bucketName = match[1];
    var fileName = match[2];
    console.log("Bucket Name : ",bucketName);
    console.log("File Name : ",fileName);
    var translationFinalData = readFileFromGCS(bucketName,fileName);
    console.log("translationFinalData : ",translationFinalData);
    //returnData = translationReCall(translationFinalData);
    translationFromModal(translationFinalData);
    
    var identityToken = ScriptApp.getIdentityToken();
    var saveTranslateData = {
      "opportunity_id" : opportunityId,
      "presentationId" : presentationId,
      "targetLanguage": targetLanguage,
      "isFullDeckTranslation": isFullDeck,
      "action": "translate",
      "user_ldap": userLdap
    };
    var saveTranslateOptions = {
      method: "post",
      contentType: "application/json",
      "headers": {
        "Authorization": "Bearer " + identityToken
      },
      "payload": JSON.stringify(saveTranslateData)
    };
    console.log("Database Payload : ",saveTranslateOptions);

    var translateSaveResponse = UrlFetchApp.fetch(saveEditAction,saveTranslateOptions);
    console.log("translateSaveResponse : ",translateSaveResponse.getContentText());

    returnData.status = true;
    returnData.message = "Success";

    return returnData;
  } 
  catch (error) {
    returnData.status = false;
    returnData.flag = "OTHER";
    console.log("Error in Translation : ",error.stack); 
    
    if(responseData != undefined && JSON.parse(responseData).message != "" && JSON.parse(responseData).message != "Success")
    {
      returnData.message = JSON.parse(responseData).message;
    }
    else
    {
      returnData.message = "Unable to process your request. Please try after sometime.";
    }
    
    return returnData;
  }
}

function translationFromModal(modelResponse) {
  var response = JSON.parse(modelResponse);
  console.log("Translation API Response : ",response);
  var presentation = SlidesApp.getActivePresentation();
  
  var objPresentationID = Object.keys(response)[3];      // presentation id (fourth key)
  var presentationData = response[objPresentationID];    // Get the data for the whole presentation
  // Iterate through all slide IDs in the JSON
  var slideIds = Object.keys(presentationData);
  for (var slideIndex = 0; slideIndex < slideIds.length; slideIndex++) {
    var slideId = slideIds[slideIndex];
    var slide = presentation.getSlideById(slideId);

    if (!slide) {
      Logger.log("Slide with ID " + slideId + " not found. Skipping.");
      continue; // Skip to the next slide
    }

    var slideData = presentationData[slideId];

    // Process Shapes on the current slide
    if (slideData.shapes) {
      var objShapeId = Object.keys(slideData.shapes);
      for (var shapeIndex = 0; shapeIndex < objShapeId.length; shapeIndex++) {
        var shapeId = objShapeId[shapeIndex];
        var shape = slide.getPageElementById(shapeId);

        if (!shape || shape.getPageElementType() !== SlidesApp.PageElementType.SHAPE) {
          Logger.log("Shape with ID " + shapeId + " not found or is not a shape on slide " + slideId + ". Skipping.");
          continue;
        }

        var textRange = shape.asShape().getText();
        textRange.clear();
        var segmentKeys = Object.keys(slideData.shapes[shapeId]);

        for (var segmentIndex = 0; segmentIndex < segmentKeys.length; segmentIndex++) {
          var segmentKey = segmentKeys[segmentIndex];
          var segmentData = slideData.shapes[shapeId][segmentKey];

          if(segmentData.Text === "\n" || segmentData.Text.trim() != "")
          {
            if(segmentData.Text === "\u000b" || segmentData.Text.includes("\u000b")){
              segmentData.Text = segmentData.Text.replace("\u000b","\n");
            }
            var shapeText = textRange.appendText(segmentData.Text);

            if(shapeText.asString().trim() !== ""){
              var textStyle = shapeText.getTextStyle();
              textStyle
                .setBold(segmentData.Bold || false)
                .setItalic(segmentData.Italic || false)
                .setUnderline(segmentData.Underline || false)
                .setFontFamily(segmentData.FontStyle)
                .setFontSize(segmentData.FontSize);
              if(segmentData.FontColor != null)
              {
                textStyle.setForegroundColor(segmentData.FontColor);  
              }
              if (segmentData.LinkUrl) {
                textStyle.setLinkUrl(segmentData.LinkUrl);
              }
            }
          }
        }
      }
    }

    // Process Tables on the current slide
    if (slideData.tables) {
      var objTableId = Object.keys(slideData.tables);
      for (var tableIndex = 0; tableIndex < objTableId.length; tableIndex++) {
        var tableId = objTableId[tableIndex];
        var tableElement = slide.getPageElementById(tableId);

        if (!tableElement || tableElement.getPageElementType() !== SlidesApp.PageElementType.TABLE) {
          Logger.log("Table with ID " + tableId + " not found or is not a table on slide " + slideId + ". Skipping.");
          continue;
        }

        var table = tableElement.asTable();
        var cellPositions = Object.keys(slideData.tables[tableId]);

        for (var cellIndex = 0; cellIndex < cellPositions.length; cellIndex++) {
          var cellPosition = cellPositions[cellIndex];
          var rowCol = cellPosition.split("_");
          var cell = table.getCell(rowCol[0], rowCol[1]);
          if(cell.getMergeState() == SlidesApp.CellMergeState.MERGED){
            continue;
          }
          var cellTextRange = cell.getText();
          cellTextRange.clear();

          var cellSegments = Object.keys(slideData.tables[tableId][cellPosition]);

          for (var segmentIndex = 0; segmentIndex < cellSegments.length; segmentIndex++) {
            var segmentData =
              slideData.tables[tableId][cellPosition][cellSegments[segmentIndex]];

            if( segmentData.Text === "\n" || segmentData.Text.trim() != "" )
            {
              if(segmentData.Text === "\u000b" || segmentData.Text.includes("\u000b")){
                segmentData.Text = segmentData.Text.replace("\u000b","\n");
              }
              
              var segmentText = cellTextRange.appendText(segmentData.Text);
              if(segmentText.asString().trim() !== ""){
                var textStyle = segmentText.getTextStyle();

                textStyle
                  .setBold(segmentData.Bold || false)
                  .setItalic(segmentData.Italic || false)
                  .setUnderline(segmentData.Underline || false)
                  .setFontFamily(segmentData.FontStyle)
                  .setFontSize(segmentData.FontSize);

                if (segmentData.LinkUrl) {
                  textStyle.setLinkUrl(segmentData.LinkUrl);
                }
              }
            }
          }
        }
      }
    }
  }

  Logger.log("Formatted text appended successfully to all slides.");
}

function unGroupedShapesInSlides(presentation){
  console.log("ungrouping");
  var slides = presentation.getSlides();
  var groupCount = 0;

  slides.forEach(function(slide) {
    var pageElements = slide.getPageElements();
    
    pageElements.forEach(function(element) {
      if (element.getPageElementType() === SlidesApp.PageElementType.GROUP) {
        groupCount++;
        element.asGroup().ungroup();
      }
    });
  });
  
  if(groupCount>0)
  {
    unGroupedShapesInSlides(presentation);
  }
}

function translationReCall(responseData)        //Unused method
{
  languageTranslationCount = languageTranslationCount + 1;
  try
  {
    var returnData = {};
    
    var message = JSON.parse(responseData).message;
    if(message == "Success")
    {
      var filename = JSON.parse(responseData).data.response;
      var apiUrl = getTranslateData;
      var data = {
        "filename": filename
      };
      var options = {
        method: "post",
        contentType: "application/json",
        payload: JSON.stringify(data)
      };

      var response = UrlFetchApp.fetch(apiUrl,options);
      var translateResponseData = response.getContentText();
      var resData = JSON.parse(translateResponseData);
      if(resData.status=="success")
      {
        translationFromModal(resData.content);

        returnData.status = true;
        returnData.message = "Success";

        return returnData;
      }
    }
    else
    {
      returnData.message = message;
    }

    returnData.status = false; 
    return returnData;
  }
  catch(error)
  {
    console.log(error);
    if (error.message.includes('Timeout')) {
      if(languageTranslationCount > 1)
      {
        console.log("TimeOut (12 mins)");
      }
      else
      {
        // Trigger the next task if the error is a timeout
        console.log("translate recall");
        translationReCall(responseData) //retrying again if the api gets timed out
      }
    }
  }
}
