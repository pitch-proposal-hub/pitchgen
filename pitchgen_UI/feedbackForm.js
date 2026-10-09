var spreadsheetMap = new Map();
spreadsheetMap.set("UAT","YOUR_FEEDBACK_SPREADSHEET_ID_UAT_0000001");
spreadsheetMap.set("QA","YOUR_FEEDBACK_SPREADSHEET_ID_QA_00000001");
spreadsheetMap.set("PROD","YOUR_FEEDBACK_SPREADSHEET_ID_DEV_0000001");
spreadsheetMap.set("DEV","YOUR_FEEDBACK_SPREADSHEET_ID_PROD_000001");
spreadsheetMap.set("DEMO","YOUR_FEEDBACK_SPREADSHEET_ID_STAGE_00001");

var spreadsheetId;
var sheetName = "Form Responses 1";
var backupSheetName = "Backup";

function userFeedbackData() {
  spreadsheetId = spreadsheetMap.get(environment);
  var apiUrl = getFeedbackDataApiUrl;
  var response = UrlFetchApp.fetch(apiUrl);

  updateID();
  saveFeedbackResponses(response.toString());
}

function saveFeedbackResponses(masterTable){

  masterTable = JSON.parse(masterTable);
  var masterTableMap = new Map();
  var columnArray = [];
  var commonColumnArray = ["ID","Status","Timestamp","Email Address","ER Number","Deck URL","Select the feature for which you want to share the feedback"];
  var swapColumnValue = "Share overall feedback on your experience of creating pitch deck through Pitch Gen";
  var swapColumn = "Share your feedback on Transform slide feature";
  for(var m=0; m<masterTable.length; m++)
  {
    var parameterColumnName = masterTable[m].category;
    var detailsColumnName = masterTable[m].details;
    var columnName;

    if(parameterColumnName.trim()=="")
    {
      columnName = detailsColumnName;  
    }
    else
    {
      columnName = "["+parameterColumnName+"] "+detailsColumnName;
    }

    if(masterTable[m].feedback_id != -1)      
    {
      columnArray.push(columnName);
      masterTableMap.set(columnName,masterTable[m].feedback_id);
    }
  }

  var spreadsheet = SpreadsheetApp.openById(spreadsheetId);
  var sheet = spreadsheet.getSheetByName(sheetName);
  var statusIndex = sheet.getDataRange().getValues()[0].indexOf('Status');
  var timestampIndex = sheet.getDataRange().getValues()[0].indexOf('Timestamp');
  var sheetData = sheet.getDataRange().getValues();
  var returnData = [];
  
  for(var i=1; i<sheetData.length; i++)
  {
    var commonFields = {};
    var finalData = [];
    var status = sheetData[i][statusIndex];
    if(status.trim()=="")
    {
      for(var j=0; j<commonColumnArray.length; j++)
      {
        var index = sheet.getDataRange().getValues()[0].indexOf(commonColumnArray[j]);
        if(index==timestampIndex)
        {
          commonFields[commonColumnArray[j]] = formatDateToYYYYMMDDHH(sheetData[i][index]);
        }
        else
        {
          commonFields[commonColumnArray[j]] = sheetData[i][index];
        }
      }
      for(var j=0; j<columnArray.length; j++)
      {
        var data = {};
        var index = sheet.getDataRange().getValues()[0].indexOf(columnArray[j]);
        var nextColumn = sheet.getDataRange().getValues()[0][index+1];

        if(sheetData[i][index]!="" || (sheetData[i][index+1]!= undefined && sheetData[i][index+1]!="" && nextColumn=="Feedback"))
        {
          data["feedbackId"] = masterTableMap.get(columnArray[j]);
          data["rating"] = sheetData[i][index];
          if(nextColumn=="Feedback")
          {
            data["feedback"] = sheetData[i][index+1];
          }
          else
          {
            data["feedback"] = "";
          }

          if(swapColumnValue==columnArray[j] || swapColumn==columnArray[j])
          {
            data["rating"] = "";
            data["feedback"] = sheetData[i][index];
          }

          finalData.push(data);
        }
      }
      if(finalData.length==0)
      {
        var noFeedbackData = {};
        
        noFeedbackData["feedbackId"] = -1;
        noFeedbackData["rating"] = "";
        noFeedbackData["feedback"] = "";
        
        finalData.push(noFeedbackData);
      }
  
      commonFields.feedback = finalData;
      returnData.push(commonFields);
    }
  }
  console.log(JSON.stringify(returnData));
  if(returnData.length>0)
  {
    var apiUrl = saveFeedbackApiUrl;
    var options = {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(returnData)
    };
    var response = UrlFetchApp.fetch(apiUrl,options);
    console.log("response : ",response.getContentText());
    response = JSON.parse(response.toString());
    var ids = response.Saved;
    ids = ids.split(',');

    for(var i=0; i<ids.length; i++)
    {
      var row = parseInt(ids[i].trim().substring(2));
      sheet.getRange((row+1),(statusIndex+1)).setValue("Updated");
    }
  }
}

function updateID() {
  var spreadsheet = SpreadsheetApp.openById(spreadsheetId);
  var sheet = spreadsheet.getSheetByName(sheetName);
  var column = sheet.getLastColumn();
  var row = sheet.getLastRow();
  var idIndex = sheet.getDataRange().getValues()[0].indexOf('ID');
  var timestampIndex = sheet.getDataRange().getValues()[0].indexOf('Timestamp');
  var sheetData = sheet.getRange(2,1,row,column).getValues();

  for(var i=0; i<sheetData.length; i++)
  {
    if(sheetData[i][idIndex]=="" && sheetData[i][timestampIndex]!="")
    {
      sheet.getRange((i+2),(idIndex+1)).setValue("ID"+(i+1));
    }
  }
}

function clearFeedbackData() {
  spreadsheetId = spreadsheetMap.get(environment);
  var spreadsheet = SpreadsheetApp.openById(spreadsheetId)
  var sheet = spreadsheet.getSheetByName(sheetName); 
  var backupSheet = spreadsheet.getSheetByName(backupSheetName);  
  var row = sheet.getLastRow();
  var column = sheet.getLastColumn();
  var sheetData = sheet.getRange(2,1,row,column).getValues();
  var statusIndex = sheet.getDataRange().getValues()[0].indexOf('Status');
  var timestampIndex = sheet.getDataRange().getValues()[0].indexOf('Timestamp');

  for(var i=0; i<sheetData.length; i++)
  {
    var status = sheetData[i][statusIndex];
    var timestamp = sheetData[i][timestampIndex];

    if(status=="" && timestamp!="")
    {
      backupSheet.appendRow(sheetData[i]);
    }
  }

  sheet.deleteRows(2,row);
}

function formatDateToYYYYMMDDHH(date) {

  var formSubmissionDate = new Date(date);
  var formattedDate = Utilities.formatDate(formSubmissionDate,"GMT","yyyy-MM-dd HH:mm:ss");

  return formattedDate;
}
