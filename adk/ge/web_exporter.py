#!/usr/bin/env python3
"""Self-Service Web Exporter for PitchGen:

A Python web server that runs a secure browser-based OAuth 2.0 flow
to authorize the user and call the Apps Script Rendering API
to generate Google Slides presentations from GCS data.
"""

import http.server
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import requests

# Read OAuth client credentials from environment
CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI", "http://localhost:8080/oauth2callback"
)

# Apps Script Web App URL (can be overridden by env var)
RENDER_API_URL = os.environ.get(
    "RENDER_API_URL",
    "https://script.google.com/macros/s/YOUR_APPS_SCRIPT_DEPLOYMENT_ID/exec",
)
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "your-pitchgen-content-bucket")

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>PitchGen Slide Exporter</title>
    <style>
        body { font-family: 'Roboto', sans-serif; background-color: #f8f9fa; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .card { background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); text-align: center; max-width: 450px; width: 100%; }
        h1 { color: #1a73e8; margin-bottom: 8px; font-size: 24px; }
        p { color: #5f6368; font-size: 14px; margin-bottom: 24px; line-height: 1.5; }
        .btn { background-color: #1a73e8; color: white; border: none; padding: 12px 24px; font-size: 16px; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; transition: background 0.2s; }
        .btn:hover { background-color: #1557b0; }
        .error { color: #d93025; background-color: #fce8e6; padding: 12px; border-radius: 4px; font-size: 13px; margin-bottom: 20px; text-align: left; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Exporting Slides...</h1>
        <p>We are calling the PitchGen rendering engine to compile your Google Slides presentation.</p>
        <div id="loader" style="margin: 20px 0; font-size: 14px; color: #1a73e8;">Processing, please wait...</div>
    </div>
</body>
</html>
"""


class OAuthExportHandler(http.server.BaseHTTPRequestHandler):

  def log_message(self, format, *args):
    sys.stdout.write(
        "%s - - [%s] %s\n"
        % (self.address_string(), self.log_date_time_string(), format % args)
    )

  def _get_cookie(self, name):
    cookies = self.headers.get("Cookie")
    if cookies:
      matches = re.findall(r"(?:^|; ?)" + name + r"=([^;]*)", cookies)
      if matches:
        return urllib.parse.unquote(matches[0])
    return None

  def do_GET(self):
    host = self.headers.get("Host", "localhost:8080")
    global REDIRECT_URI
    if "localhost" not in host:
      REDIRECT_URI = f"https://{host}/oauth2callback"

    parsed_url = urllib.parse.urlparse(self.path)
    params = urllib.parse.parse_qs(parsed_url.query)
    path = parsed_url.path

    if path == "/":
      self.send_response(200)
      self.send_header("Content-Type", "text/html")
      self.end_headers()
      self.wfile.write(HTML_TEMPLATE.encode())

    elif path == "/export":
      outputs_filename = params.get("outputs_filename", [""])[0]
      architectural_filename = params.get("architectural_filename", [""])[0]
      customer_name = params.get("customer_name", [""])[0]
      er_number = params.get("er_number", [""])[0]
      user_ldap = params.get("user_ldap", [""])[0]

      if not outputs_filename or not architectural_filename:
        self._send_error(
            "Missing required parameters: 'outputs_filename' and"
            " 'architectural_filename' must be provided."
        )
        return

      access_token = self._get_cookie("user_access_token")
      if not access_token:
        if not CLIENT_ID or not CLIENT_SECRET:
          self._send_credentials_missing_page()
          return

        state_data = {
            "o": outputs_filename,
            "a": architectural_filename,
            "c": customer_name,
            "e": er_number,
            "u": user_ldap,
        }
        state_str = urllib.parse.quote(json.dumps(state_data))

        auth_url = (
            "https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={CLIENT_ID}&"
            f"redirect_uri={urllib.parse.quote(REDIRECT_URI)}&"
            "response_type=code&"
            "scope=https://www.googleapis.com/auth/presentations+https://www.googleapis.com/auth/drive&"
            f"state={state_str}&"
            "access_type=online&"
            "prompt=consent"
        )
        self.send_response(302)
        self.send_header("Location", auth_url)
        self.end_headers()
        return

      self._execute_export(
          outputs_filename,
          architectural_filename,
          customer_name,
          er_number,
          user_ldap,
          access_token,
      )

    elif path == "/oauth2callback":
      code = params.get("code", [""])[0]
      state_str = params.get("state", [""])[0]

      if not code:
        self._send_error("OAuth Callback failed: missing authorization code.")
        return

      token_url = "https://oauth2.googleapis.com/token"
      data = urllib.parse.urlencode({
          "code": code,
          "client_id": CLIENT_ID,
          "client_secret": CLIENT_SECRET,
          "redirect_uri": REDIRECT_URI,
          "grant_type": "authorization_code",
      }).encode("utf-8")

      try:
        req = urllib.request.Request(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req) as response:
          res_data = json.loads(response.read().decode())
          access_token = res_data.get("access_token")

          if not access_token:
            self._send_error("Failed to retrieve access token.")
            return

          state_data = json.loads(urllib.parse.unquote(state_str))
          redirect_params = urllib.parse.urlencode({
              "outputs_filename": state_data["o"],
              "architectural_filename": state_data["a"],
              "customer_name": state_data["c"],
              "er_number": state_data["e"],
              "user_ldap": state_data["u"],
          })

          self.send_response(302)
          self.send_header(
              "Set-Cookie",
              f"user_access_token={urllib.parse.quote(access_token)}; Path=/;"
              " HttpOnly; Max-Age=3600",
          )
          self.send_header("Location", f"/export?{redirect_params}")
          self.end_headers()
      except Exception as e:
        self._send_error(f"Token exchange failed: {e}")

    else:
      self.send_response(404)
      self.end_headers()

  def _execute_export(
      self,
      outputs_filename: str,
      architectural_filename: str,
      customer_name: str,
      er_number: str,
      user_ldap: str,
      access_token: str,
  ):
    gsurl_outputs = f"gs://{GCS_BUCKET_NAME}/{outputs_filename}"
    gsurl_architectural = f"gs://{GCS_BUCKET_NAME}/{architectural_filename}"

    data_payload = {
        "gsurl_outputs": gsurl_outputs,
        "gsurl_architectural": gsurl_architectural,
        "outputs_filename": outputs_filename,
        "architectural_filename": architectural_filename,
        "user_ldap": user_ldap,
        "customer_name": customer_name,
        "er_number": er_number,
        "audience": "",
        "salesPlay": "",
        "industry": "",
        "business_context": "",
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
      print(
          f"[Exporter] Calling Apps Script rendering API: {RENDER_API_URL}..."
      )
      response = requests.post(
          RENDER_API_URL,
          json=data_payload,
          headers=headers,
          allow_redirects=True,
      )
      print(f"[Exporter] Response status: {response.status_code}")

      if response.status_code in [401, 403]:
        # Token might be expired, clear cookie and retry auth
        print(
            "[Exporter] Auth error from Apps Script, clearing token and"
            " retrying OAuth..."
        )
        redirect_params = urllib.parse.urlencode({
            "outputs_filename": outputs_filename,
            "architectural_filename": architectural_filename,
            "customer_name": customer_name,
            "er_number": er_number,
            "user_ldap": user_ldap,
        })
        self.send_response(302)
        self.send_header("Set-Cookie", "user_access_token=; Path=/; Max-Age=0")
        self.send_header("Location", f"/export?{redirect_params}")
        self.end_headers()
        return

      if response.status_code == 200:
        try:
          res_json = response.json()
          deck_url = (
              res_json.get("deck_url")
              or res_json.get("presentation_url")
              or res_json.get("url")
          )
        except Exception:
          deck_url = response.text.strip()

        if deck_url and deck_url.startswith("http"):
          print(f"[Exporter] Redirecting user to deck: {deck_url}")
          self.send_response(302)
          self.send_header("Location", deck_url)
          self.end_headers()
        else:
          self._send_error(
              f"Invalid response from rendering API: {response.text}"
          )
      else:
        self._send_error(
            f"Rendering API failed with status {response.status_code}:"
            f" {response.text}"
        )
    except Exception as e:
      self._send_error(f"Failed to call rendering API: {e}")

  def _send_error(self, message: str):
    self.send_response(200)
    self.send_header("Content-Type", "text/html")
    self.end_headers()
    error_html = f"""<!DOCTYPE html>
        <html>
        <head><title>Exporter Error</title><style>body {{ font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #f8f9fa; }} .card {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); max-width: 500px; }} h1 {{ color: #d93025; }} p {{ color: #5f6368; line-height: 1.5; }}</style></head>
        <body><div class="card"><h1>Export Failed</h1><p>{message}</p><p><a href="/" style="color: #1a73e8;">Back to Home</a></p></div></body>
        </html>"""
    self.wfile.write(error_html.encode())

  def _send_credentials_missing_page(self):
    self.send_response(200)
    self.send_header("Content-Type", "text/html")
    self.end_headers()
    guide_html = """<!DOCTYPE html>
        <html>
        <head><title>OAuth Setup Required</title><style>body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #f8f9fa; margin: 0; } .card { background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); max-width: 600px; line-height: 1.6; } h1 { color: #1a73e8; margin-top: 0; } code { background: #f1f3f4; padding: 2px 6px; border-radius: 4px; font-family: monospace; } pre { background: #f1f3f4; padding: 12px; border-radius: 4px; overflow-x: auto; font-family: monospace; }</style></head>
        <body>
            <div class="card">
                <h1>OAuth Credentials Setup Required</h1>
                <p>To enable slide export, you must configure Google OAuth Client credentials for your project.</p>
                <ol>
                    <li>Go to the GCP Credentials Console.</li>
                    <li>Create OAuth client ID (Web application).</li>
                    <li>Add the redirect URI: <pre>http://localhost:8080/oauth2callback</pre> (or your Cloud Run URL equivalent).</li>
                    <li>Set environment variables:</li>
                </ol>
                <pre>export GOOGLE_CLIENT_ID="your_client_id"<br>export GOOGLE_CLIENT_SECRET="your_client_secret"<br>python3 web_exporter.py</pre>
            </div>
        </body>
        </html>"""
    self.wfile.write(guide_html.encode())


def run_server():
  port = int(os.environ.get("PORT", 8080))
  server = http.server.HTTPServer(("0.0.0.0", port), OAuthExportHandler)
  print("=" * 80)
  print(f"🚀 PITCHGEN SELF-SERVICE WEB EXPORTER RUNNING ON PORT {port}")
  print(f"   OAuth Redirect URI Configured: {REDIRECT_URI}")
  print(f"   Apps Script Target URL: {RENDER_API_URL}")
  if not CLIENT_ID or not CLIENT_SECRET:
    print(
        "\n   [!] WARNING: GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET environment"
        " variables are missing."
    )
  print("=" * 80)
  try:
    server.serve_forever()
  except KeyboardInterrupt:
    print("\n[*] Shutting down web exporter server...")
    server.server_close()


if __name__ == "__main__":
  run_server()
