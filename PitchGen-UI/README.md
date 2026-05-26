# PitchGen Frontend UI (Google Apps Script)

This component constitutes the presentation tier of the PitchGen Solution Accelerator. Embedded as a **Google Slides Editor Add-on**, this codebase renders standard sidebar widgets using Apps Script (`.gs`) functions and interactive HTML (`.html`) views.

---

## 1. Deployment Guide

### 1.1. Create an Apps Script Project
1.  Open **Google Slides** and create a new presentation (or open your master layout deck).
2.  Navigate to **Extensions > Apps Script**.
3.  Click the project name (e.g., `Untitled project`) and rename it to **PitchGen UI**.

### 1.2. Copy Frontend Files
For each file in this `PitchGen-UI` folder:
1.  If it is a `.gs` file (e.g. `Code.gs`), click **+** next to Files, choose **Script**, name the file matching the script name (excluding `.gs`), and paste the contents.
2.  If it is an `.html` file (e.g. `userInputPopup.html`), click **+**, choose **HTML**, name it matching the HTML page name, and paste the contents.

---

## 2. Configuration

### 2.1. Connect to the Backend Gateway
To route AI requests to the model service, the Apps Script client must call your deployed Flask backend.
1.  Open `restAPI.gs` or `configuration.gs` in the editor.
2.  Expose your Flask backend URL (e.g., `https://your-backend-gateway-address.appspot.com/`) in the REST API handler coordinates.

---

## 3. Ingestion and Running

1.  Inside the Apps Script editor, select the `onOpen` function in the dropdown toolbar and click **Run** to authorize the scopes (Google Drive, Google Slides, UrlFetchApp).
2.  Return to your Google Slides deck. You will notice a custom **PitchGen** menu in the toolbar.
3.  Click **PitchGen > Open Sidebar** to launch the customizable pitch configuration form!
