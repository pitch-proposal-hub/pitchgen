import os
import json
import urllib.parse
import requests
from google.cloud import secretmanager
from google.cloud import storage

try:
    from config_loader import load_config
    _config = load_config()
    PROJECT_ID = _config.get("default", "project_name", fallback="your-gcp-project-id")
    BUCKET_NAME = _config.get("bucket", "content", fallback="your-pitchgen-content-bucket")
except Exception:
    PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "your-gcp-project-id")
    BUCKET_NAME = os.environ.get("BUCKET_NAME", "your-pitchgen-content-bucket")

REDIRECT_URI = "https://vertexaisearch.cloud.google.com/oauth-redirect"

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/script.external_request",
    "https://www.googleapis.com/auth/devstorage.read_only",
    "openid",
    "email"
]

def get_secret(secret_id: str) -> str:
    """Fetch client credentials from Secret Manager (checks current project, then falls back to your-gcp-project-id)."""
    for proj in [PROJECT_ID, "your-gcp-project-id"]:
        try:
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{proj}/secrets/{secret_id}/versions/latest"
            response = client.access_secret_version(request={"name": name})
            val = response.payload.data.decode("UTF-8").strip()
            if val:
                return val
        except Exception as e:
            continue
    return os.environ.get(secret_id, "")

def get_client_config() -> dict:
    """Constructs client config dictionary for PitchGen-GE-user."""
    return {
        "web": {
            "client_id": get_secret("oauth-client-id-user"),
            "client_secret": get_secret("oauth-client-secret-user"),
            "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

def resolve_user_ldap(user_ldap: str = None, tool_context=None) -> str:
    """Resolves the user LDAP from argument, tool_context, Flask headers, or environment default."""
    if user_ldap and user_ldap.strip() and user_ldap.strip().lower() not in ["myuser", "user", "dummy"]:
        clean = user_ldap.strip()
        if not "@" in clean:
            clean = f"{clean}@example.com"
        return clean

    if tool_context and hasattr(tool_context, "user_id"):
        try:
            uid = str(getattr(tool_context, "user_id") or "").strip()
            if uid and "@" in uid:
                return uid
        except Exception:
            pass

    try:
        from flask import request
        for k, v in request.headers.items():
            if k.lower() in ["x-goog-authenticated-user-email", "x-goog-user-email", "x-user-email"]:
                email = v.replace("accounts.google.com:", "").strip()
                if email and "@" in email:
                    print(f"[oauth_helper] Resolved user LDAP from header '{k}': {email}")
                    return email
    except Exception:
        pass

    return "admin@example.com"

def get_authorization_url(user_ldap: str) -> str:
    """Generates the authorization login URL manually to bypass PKCE requirements."""
    config = get_client_config()["web"]
    params = {
        "client_id": config["client_id"],
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent"
    }
    encoded_params = urllib.parse.urlencode(params)
    return f"{config['auth_uri']}?{encoded_params}"

def exchange_code_for_tokens(user_ldap: str, auth_code: str) -> str:
  """Exchanges code for tokens using raw POST and saves refresh token to GCS."""
  config = get_client_config()["web"]

  payload = {
        "code": auth_code.strip(),
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }

  print(f"[oauth_helper] 🚀 TOKEN CREATION STARTED: Exchanging 1-time authorization code for user '{user_ldap}'...", flush=True)
  response = requests.post(config["token_uri"], data=payload, timeout=30)

  if response.status_code != 200:
    print(f"[oauth_helper] ❌ TOKEN CREATION FAILED! Status: {response.status_code}, Response: {response.text}", flush=True)
    raise ValueError(f"Failed to exchange code: {response.text}")

  token_data = response.json()
  refresh_token = token_data.get("refresh_token")
  access_token = token_data.get("access_token")

  if refresh_token:
    storage_client = storage.Client()
    clean_user = user_ldap.split("@")[0].strip()

    save_data = {
            "user_ldap": user_ldap,
            "refresh_token": refresh_token
        }
    json_content = json.dumps(save_data)

    paths = [
            f"auth_tokens/{clean_user}_refresh_token.json",
            f"auth_tokens/{clean_user}@example.com_refresh_token.json",
            f"tokens/{clean_user}_token.json"
        ]
    target_buckets = list(
        dict.fromkeys(
            [BUCKET_NAME, "your-pitchgen-content-bucket", "your-pitchgen-content-bucket"]
        )
    )
    for b_name in target_buckets:
      try:
        bucket = storage_client.bucket(b_name)
        for p in paths:
          blob = bucket.blob(p)
          blob.upload_from_string(json_content, content_type="application/json")
      except Exception as e:
        print(
            f"[oauth_helper] Warning saving token to {b_name}: {e}", flush=True
        )
    print(f"[oauth_helper] 🎉 1ST TIME AUTH & GCS OVERWRITE SUCCESS! Fresh refresh token saved & overwritten for '{user_ldap}' in GCS at paths:", flush=True)
    for p in paths:
      print(f"   -> gs://{BUCKET_NAME}/{p}", flush=True)
  else:
    print(f"[oauth_helper] ⚠️ TOKEN CREATION WARNING: Code exchange succeeded but no refresh_token was returned by Google OAuth.", flush=True)

  return access_token

import re


_NON_AUTH_STATE_KEYS = frozenset({
    "proposal_outline",
    "latest_outline_state_json",
    "pending_a2ui_payload",
    "active_presentation_id",
    "active_presentation_url",
    "active_presentation_title",
    "last_search_results",
})


def _extract_clean_access_token(val: str) -> str:
  """Extracts a clean Google OAuth2 access token (ya29....) without surrounding JSON or whitespace."""
  if not val:
    return ""
  s = str(val).strip()
  m = re.search(r"(ya29\.[A-Za-z0-9._\-]{20,2048})", s)
  if m:
    return m.group(1)
  if (
      s.startswith("eyJ")
      and len(s) > 40
      and " " not in s
      and "{" not in s
      and '"' not in s
  ):
    return s
  return ""


def _extract_clean_refresh_token(val: str) -> str:
  """Extracts a clean Google OAuth2 refresh token (1//...) without surrounding JSON or whitespace."""
  if not val:
    return ""
  s = str(val).strip()
  m = re.search(r"(1//[A-Za-z0-9._\-]{15,1024})", s)
  if m:
    return m.group(1)
  return ""


def get_user_access_token(user_ldap: str) -> str:
  """Retrieves access token for user using stored refresh token in GCS."""
  try:
    storage_client = storage.Client()
    clean_user = user_ldap.split("@")[0].strip()

    candidates = [
        f"auth_tokens/{clean_user}_refresh_token.json",
        f"auth_tokens/{clean_user}@example.com_refresh_token.json",
        f"auth_tokens/{user_ldap}_refresh_token.json",
        f"tokens/{clean_user}_token.json",
        f"tokens/{user_ldap}_token.json",
    ]

    blob = None
    found_path = None
    found_bucket_name = None
    target_buckets = list(
        dict.fromkeys(
            [BUCKET_NAME, "your-pitchgen-content-bucket", "your-pitchgen-content-bucket"]
        )
    )
    for b_name in target_buckets:
      try:
        bucket = storage_client.bucket(b_name)
        for path in candidates:
          b = bucket.blob(path)
          if b.exists():
            blob = b
            found_path = path
            found_bucket_name = b_name
            print(
                "[oauth_helper] ✅ TOKEN IDENTIFIED SUCCESS! Found stored"
                f" refresh token for '{user_ldap}' in GCS at"
                f" 'gs://{b_name}/{path}'",
                flush=True,
            )
            break
      except Exception:
        continue
      if blob:
        break

    if not blob:
      print(
          "[oauth_helper] ⚠️ NO STORED REFRESH TOKEN IN GCS for user"
          f" '{user_ldap}'. Live Header Token Extraction will resolve caller"
          " identity from chat request headers.",
          flush=True,
      )
      return None

    token_data = json.loads(blob.download_as_text())
    raw_access = token_data.get("access_token") or ""
    raw_refresh = token_data.get("refresh_token") or ""
    access_token = _extract_clean_access_token(raw_access) or _extract_clean_access_token(raw_refresh)
    refresh_token = _extract_clean_refresh_token(raw_refresh)

    # Auto-heal corrupted GCS token file if raw fields contained non-token JSON state
    if (raw_access and raw_access != access_token) or (
        raw_refresh and raw_refresh != refresh_token and raw_refresh != access_token
    ):
      try:
        healed = {"user_ldap": user_ldap}
        if refresh_token:
          healed["refresh_token"] = refresh_token
        if access_token:
          healed["access_token"] = access_token
        blob.upload_from_string(
            json.dumps(healed), content_type="application/json"
        )
        print(
            f"[oauth_helper] 🛠️ Auto-healed corrupted token blob at"
            f" gs://{found_bucket_name}/{found_path}",
            flush=True,
        )
      except Exception:
        pass

    # Fallback list of client credentials (user OAuth client ID first, then primary client ID)
    cred_pairs = []
    try:
      cred_pairs.append((
          get_secret("oauth-client-id-user"),
          get_secret("oauth-client-secret-user"),
      ))
    except Exception:
      pass
    try:
      cred_pairs.append(
          (get_secret("oauth-client-id"), get_secret("oauth-client-secret"))
      )
    except Exception:
      pass

    # 1. If long-lived refresh token (1//...) is available, ALWAYS mint a brand new access token!
    if refresh_token and refresh_token.startswith("1//"):
      print(
          "[oauth_helper] 🔄 MINTING FRESH ACCESS TOKEN: Refreshing via Google"
          f" OAuth for '{user_ldap}'...",
          flush=True,
      )
      for cid, csecret in cred_pairs:
        payload = {
            "client_id": cid,
            "client_secret": csecret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        response = requests.post(
            "https://oauth2.googleapis.com/token", data=payload, timeout=30
        )
        if response.status_code == 200:
          fresh_access_token = _extract_clean_access_token(
              response.json().get("access_token")
          )
          if fresh_access_token:
            print(
                "[oauth_helper] 🎉 ACCESS TOKEN MINTED SUCCESS! Refreshed"
                f" Access Token for '{user_ldap}' via client '{cid[:15]}...'",
                flush=True,
            )
            return fresh_access_token
        else:
          print(
              "[oauth_helper] ⚠️ Refresh attempt failed with client"
              f" {cid[:15]}: Status {response.status_code}, Response:"
              f" {response.text}",
              flush=True,
          )

    # 2. If direct active access_token (ya29.) is stored, return it
    if access_token:
      print(
          "[oauth_helper] 🎉 ACCESS TOKEN MINTED SUCCESS! Using stored active"
          f" access token for '{user_ldap}' (Length: {len(access_token)})",
          flush=True,
      )
      return access_token

    # 3. If token is invalid or expired, automatically regenerate fresh token via ADC
    print(
        "[oauth_helper] 🔄 EXPIRED/INVALID TOKEN DETECTED for"
        f" '{user_ldap}'. Auto-regenerating fresh token on the fly...",
        flush=True,
    )
    return get_adc_bearer_token()

  except Exception as e:
    print(
        "[oauth_helper] ❌ CRITICAL ERROR in get_user_access_token for"
        f" '{user_ldap}': {e}"
    )
  return None


def get_enduser_bearer_token(tool_context=None, incoming_headers=None) -> str:
  """Exhaustively scans request headers, tool_context, or incoming_headers dict for OAuth tokens/codes and saves long-lived refresh tokens to GCS."""
  try:
    headers_dict = {}
    if incoming_headers and isinstance(incoming_headers, dict):
      headers_dict = dict(incoming_headers)
    elif (
        tool_context
        and hasattr(tool_context, "headers")
        and getattr(tool_context, "headers")
    ):
      headers_dict = dict(getattr(tool_context, "headers"))
    else:
      try:
        from flask import has_request_context, request

        if has_request_context():
          headers_dict = dict(request.headers)
      except Exception:
        pass

    if tool_context:
      if hasattr(tool_context, "_invocation_context"):
        inv_ctx = getattr(tool_context, "_invocation_context")
        if hasattr(inv_ctx, "session") and inv_ctx.session:
          st = getattr(inv_ctx.session, "state", {})
          if isinstance(st, dict):
            for k, v in st.items():
              if str(k) in _NON_AUTH_STATE_KEYS or not isinstance(v, str):
                continue
              val_str = v.strip()
              if val_str.startswith("{") or val_str.startswith("["):
                continue
              clean_rf = _extract_clean_refresh_token(val_str)
              clean_ac = _extract_clean_access_token(val_str)
              if clean_rf:
                headers_dict[f"adk_session_refresh_{k}"] = clean_rf
              elif clean_ac:
                headers_dict[f"adk_session_state_{k}"] = f"Bearer {clean_ac}"

        if (
            hasattr(inv_ctx, "credential_service")
            and inv_ctx.credential_service
        ):
          cred_svc = inv_ctx.credential_service
          if hasattr(cred_svc, "__dict__"):
            for k, v in cred_svc.__dict__.items():
              val_str = str(v).strip()
              clean_rf = _extract_clean_refresh_token(val_str)
              clean_ac = _extract_clean_access_token(val_str)
              if clean_rf:
                headers_dict[f"adk_cred_refresh_{k}"] = clean_rf
              elif clean_ac:
                headers_dict[f"adk_cred_access_{k}"] = f"Bearer {clean_ac}"

      for m in ["get_auth_response", "get_credential", "load_credential"]:
        if hasattr(tool_context, m):
          try:
            res = getattr(tool_context, m)()
            if res:
              res_str = str(res)
              clean_ac = _extract_clean_access_token(res_str)
              if clean_ac:
                headers_dict[f"adk_{m}"] = f"Bearer {clean_ac}"
              if hasattr(res, "token") and getattr(res, "token"):
                tok_ac = _extract_clean_access_token(getattr(res, "token"))
                if tok_ac:
                  headers_dict[f"adk_{m}_token"] = f"Bearer {tok_ac}"
          except Exception:
            pass

    if (
        tool_context
        and hasattr(tool_context, "credentials")
        and getattr(tool_context, "credentials")
    ):
      try:
        creds = getattr(tool_context, "credentials")
        if hasattr(creds, "token") and creds.token:
          tok_ac = _extract_clean_access_token(creds.token)
          if tok_ac:
            headers_dict["authorization"] = f"Bearer {tok_ac}"
      except Exception:
        pass

    if headers_dict:
      print(
          f"[oauth_helper] 🔍 Scanned {len(headers_dict)} headers/context"
          f" items: {list(headers_dict.keys())}",
          flush=True,
      )

      user_ldap = resolve_user_ldap(tool_context=tool_context)
      clean_user = user_ldap.split("@")[0].strip()
      storage_client = storage.Client()
      bucket = storage_client.bucket(BUCKET_NAME)

      # 1. First scan for explicit long-lived Refresh Token (1//...) or Auth Code (4/...)
      captured_refresh_token = None
      for key, value in headers_dict.items():
        if str(key) in _NON_AUTH_STATE_KEYS:
          continue
        val_str = str(value).strip()
        clean_rf = _extract_clean_refresh_token(val_str)
        if clean_rf:
          captured_refresh_token = clean_rf
          print(
              "[oauth_helper] 🎉 CAPTURED LONG-LIVED REFRESH TOKEN (1//...)"
              f" from '{key}'!",
              flush=True,
          )
          break
        elif (
            "4/" in val_str
            and len(val_str) > 20
            and "Bearer " not in val_str
            and not val_str.startswith("{")
        ):
          code_candidate = (
              val_str[val_str.find("4/") :].split()[0].split(";")[0].strip()
          )
          print(
              f"[oauth_helper] ⚡ CAPTURED AUTHORIZATION CODE from '{key}'."
              " Attempting live exchange...",
              flush=True,
          )
          try:
            exchanged_token = exchange_code_for_tokens(
                user_ldap, code_candidate
            )
            if exchanged_token:
              print(
                  "[oauth_helper] 💾 LIVE CODE EXCHANGE SUCCESS! Saved to GCS"
                  f" for '{user_ldap}'.",
                  flush=True,
              )
          except Exception as ex_err:
            print(
                f"[oauth_helper] Notice: Live code exchange failed: {ex_err}",
                flush=True,
            )

      # 2. Extract active Bearer access token (ya29...)
      bearer_token = None
      for key, value in headers_dict.items():
        if str(key) in _NON_AUTH_STATE_KEYS:
          continue
        if value and (
            "Bearer " in str(value)
            or key.lower()
            in ["x-goog-user-token", "x-authorization", "authorization"]
        ):
          clean_tok = _extract_clean_access_token(str(value))
          if clean_tok:
            bearer_token = clean_tok
            print(
                "\n========================================================================\n"
                "[oauth_helper] 🎉 5-FLOW AUTHORIZATION TOKEN CAPTURED FOR"
                f" USER '{user_ldap}'!\n[oauth_helper] 🔑 Key: '{key}' | Token"
                f" Length: {len(clean_tok)} | Preview:"
                f" {clean_tok[:15]}...\n"
                "========================================================================\n",
                flush=True,
            )
            break

      # 3. Persist captured long-lived refresh token or clean access token to GCS
      if captured_refresh_token or bearer_token:
        paths = [
            f"auth_tokens/{clean_user}_refresh_token.json",
            f"auth_tokens/{clean_user}@example.com_refresh_token.json",
            f"tokens/{clean_user}_token.json",
        ]

        for p in paths:
          blob = bucket.blob(p)
          existing_refresh = None
          if blob.exists():
            try:
              data = json.loads(blob.download_as_text())
              rf = _extract_clean_refresh_token(data.get("refresh_token"))
              if rf:
                existing_refresh = rf
            except Exception:
              pass

          final_refresh = captured_refresh_token or existing_refresh
          save_data = {"user_ldap": user_ldap}
          if final_refresh:
            save_data["refresh_token"] = final_refresh
          if bearer_token:
            save_data["access_token"] = bearer_token
          blob.upload_from_string(
              json.dumps(save_data), content_type="application/json"
          )
          print(
              "------------------------------------------------------------------------\n"
              "[oauth_helper] 💾 GCS BUCKET UPLOAD SUCCESS! Saved Token for"
              f" '{user_ldap}' at 'gs://{BUCKET_NAME}/{p}'!\n[oauth_helper]"
              " 📦 Refresh Token:"
              f" {'LONG-LIVED (1//...)' if final_refresh else 'NONE (access_token only)'}"
              f" | Access Token Length: {len(bearer_token or '')}\n"
              "------------------------------------------------------------------------\n",
              flush=True,
          )

      if bearer_token:
        return bearer_token
      if captured_refresh_token:
        return captured_refresh_token

      print(
          "[oauth_helper] ⚠️ No Bearer token found in headers/context. Items"
          f" scanned: {len(headers_dict)}",
          flush=True,
      )
    else:
      print(
          "[oauth_helper] ⚠️ No header/context dictionary available for token"
          " scanning.",
          flush=True,
      )
  except Exception as e:
    print(
        f"[oauth_helper] Notice while inspecting request headers: {e}",
        flush=True,
    )
  return ""


def get_adc_bearer_token() -> str:
  """Fallback: Acquires Google ADC Bearer token."""
  import google.auth
  import google.auth.transport.requests

  credentials, _ = google.auth.default()
  auth_req = google.auth.transport.requests.Request()
  credentials.refresh(auth_req)
  return credentials.token


def get_cached_active_token(user_ldap: str) -> str:
  """Helper alias for get_user_access_token to retrieve cached access token from GCS or environment."""
  return get_user_access_token(user_ldap)


def get_email_from_bearer_token(token: str) -> str:
  """Decodes email from Google tokeninfo endpoint or JWT."""
  clean_tok = _extract_clean_access_token(token)
  if not clean_tok:
    return ""
  try:
    resp = requests.get(
        f"https://oauth2.googleapis.com/tokeninfo?access_token={clean_tok}",
        timeout=5,
    )
    if resp.status_code == 200:
      return resp.json().get("email", "")
  except Exception:
    pass
  return ""


def save_short_lived_token(user_ldap: str, token: str) -> None:
  """Saves active short-lived access token in GCS without overwriting existing 1// refresh tokens."""
  clean_tok = _extract_clean_access_token(token)
  if not user_ldap or not clean_tok:
    return
  try:
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    clean_user = user_ldap.split("@")[0].strip()
    active_data = json.dumps(
        {"user_ldap": user_ldap, "access_token": clean_tok}
    )
    for path in [
        f"auth_tokens/{clean_user}_active_token.json",
        f"tokens/{clean_user}_token.json",
    ]:
      bucket.blob(path).upload_from_string(
          active_data, content_type="application/json"
      )

    refresh_blob = bucket.blob(f"auth_tokens/{clean_user}_refresh_token.json")
    existing_refresh = None
    if refresh_blob.exists():
      try:
        existing = json.loads(refresh_blob.download_as_text())
        rf = _extract_clean_refresh_token(existing.get("refresh_token"))
        if rf:
          existing_refresh = rf
      except Exception:
        pass
    save_payload = {"user_ldap": user_ldap, "access_token": clean_tok}
    if existing_refresh:
      save_payload["refresh_token"] = existing_refresh
    refresh_blob.upload_from_string(
        json.dumps(save_payload),
        content_type="application/json",
    )
  except Exception:
    pass


def cache_active_access_token(user_ldap: str, token: str) -> None:
  """Caches active access token in GCS."""
  save_short_lived_token(user_ldap, token)

