import ast
import json
import math
import os
import re
import sys
import uuid

# Ensure the current directory and parent directory are in sys.path immediately
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
  sys.path.insert(0, _current_dir)
_parent_dir = os.path.dirname(_current_dir)
if _parent_dir not in sys.path:
  sys.path.insert(0, _parent_dir)

os.environ["GOOGLE_API_USE_CLIENT_CERTIFICATE"] = "false"

try:
  import urllib3.contrib.pyopenssl

  urllib3.contrib.pyopenssl.extract_from_urllib3()
  urllib3.contrib.pyopenssl.inject_into_urllib3 = lambda: None
except Exception:
  pass

from google.cloud import storage

from typing import Any, Dict, List, Optional, Tuple
from google.adk.tools.tool_context import ToolContext
from google.adk.auth.auth_credential import AuthCredential
from google.adk.auth.auth_tool import AuthConfig
from google.adk.auth.credential_manager import CredentialManager
GcpAuthProvider = None
GcpAuthProviderScheme = None
HAS_AGENT_IDENTITY = False
try:
  from google.adk.integrations.agent_identity.gcp_auth_provider import GcpAuthProvider
  from google.adk.integrations.agent_identity.gcp_auth_provider_scheme import GcpAuthProviderScheme
  HAS_AGENT_IDENTITY = True
except ImportError as e:
  print(f"[PitchGen] Agent Identity not available: {e}", file=sys.stderr)

from google.adk.tools.base_authenticated_tool import BaseAuthenticatedTool
from google.adk.tools.base_tool import BaseTool
from google.adk.auth.auth_handler import AuthHandler
from google.genai import types
from agents.gtm_skills import GTMSkills

# Register GcpAuthProvider for ADK to handle GcpAuthProviderScheme
if HAS_AGENT_IDENTITY:
  try:
    CredentialManager.register_auth_provider(GcpAuthProvider())
    print("[PitchGen] Registered GcpAuthProvider.", file=sys.stderr)
  except ValueError as e:
    print(f"[PitchGen] GcpAuthProvider registration status: {e}", file=sys.stderr)

# Remove any API keys from the environment to prevent the google-genai SDK
# from using them instead of standard Google Cloud IAM/ADC credentials.
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("GOOGLE_API_KEY", None)
os.environ.pop("API_KEY", None)

from google.adk.agents.llm_agent import Agent
from config_loader import load_config
from orchestrators.narrative_orchestrator import NarrativeOrchestrator
from orchestrators.creative_orchestrator import CreativeOrchestrator
from state import GlobalState
from agents.agenda_agent import AgendaAgent
from agents.retrieval_agent import RetrievalAgent


def robust_json_loads(s: Any) -> dict:
  if isinstance(s, dict):
    return s
  if not isinstance(s, str):
    return {}
  s = s.strip()
  # 1. Fix missing closing braces
  open_braces = s.count("{")
  close_braces = s.count("}")
  if open_braces > close_braces:
    s += "}" * (open_braces - close_braces)

  # 2. Try standard json loads first
  try:
    return json.loads(s)
  except Exception:
    pass

  # 3. Try ast.literal_eval after quoting unquoted keys
  try:
    temp = s
    # Quote unquoted keys (e.g. { user_inputs: -> { 'user_inputs': )
    temp = re.sub(r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)", r"\1'\2'\3", temp)
    return ast.literal_eval(temp)
  except Exception as e:
    try:
      # Fallback: replace single quotes with double quotes and quote keys
      fallback_str = s.replace("'", '"')
      fallback_str = re.sub(
          r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)", r'\1"\2"\3', fallback_str
      )
      return json.loads(fallback_str)
    except Exception:
      raise e


def resolve_target_language(target_lang_input: str) -> tuple[str, str]:
  """Resolves natural language input or ISO code to (Language Name, ISO Code)."""
  if not target_lang_input:
    return ("German", "de")

  translate_config_path = os.path.join(
      os.path.dirname(os.path.abspath(__file__)), "config", "translate.json"
  )
  code_to_lang, lang_to_code = {}, {}
  if os.path.exists(translate_config_path):
    try:
      with open(translate_config_path, "r") as f:
        data = json.load(f)
        code_to_lang = data.get("codeToLang", {})
        raw_lang_to_code = data.get("langToCode", {})
        lang_to_code = {k.lower(): v for k, v in raw_lang_to_code.items()}
    except Exception:
      pass

  if not code_to_lang:
    code_to_lang = {
        "de": "German", "es": "Spanish", "fr": "French", "id": "Indonesian",
        "it": "Italian", "pt": "Portuguese", "ja": "Japanese", "ko": "Korean",
        "zh-TW": "Chinese (Traditional)", "zh-CN": "Chinese (Simplified)",
        "da": "Danish", "nl": "Dutch", "fi": "Finnish", "el": "Greek",
        "pl": "Polish", "sv": "Swedish", "th": "Thai", "en": "English"
    }
    lang_to_code = {v.lower(): k for k, v in code_to_lang.items()}

  clean_input = target_lang_input.strip()
  lower_input = clean_input.lower()
  norm_input = re.sub(r'[^a-z0-9]', '', lower_input)

  code_to_lang_lower = {k.lower(): (v, k) for k, v in code_to_lang.items()}
  if lower_input in code_to_lang_lower:
    lang_name, orig_code = code_to_lang_lower[lower_input]
    return (lang_name, orig_code)

  if lower_input in lang_to_code:
    code = lang_to_code[lower_input]
    return (code_to_lang.get(code, clean_input.title()), code)

  for k, v in lang_to_code.items():
    if k in lower_input or lower_input in k:
      return (code_to_lang.get(v, k.title()), v)

  # Aliases for Chinese Simplified
  if "simplified" in lower_input or norm_input in ["zhcn", "zhhans", "simplifiedchinese", "mandarinsimplified"]:
    return ("Chinese (Simplified)", "zh-CN")

  # Aliases for Chinese Traditional
  if "traditional" in lower_input or norm_input in ["zhtw", "zhhant", "traditionalchinese", "cantonese"]:
    return ("Chinese (Traditional)", "zh-TW")

  if norm_input in ["spanish", "espanol", "espanolcastellano", "castellano", "es"]:
    return ("Spanish", "es")
  if norm_input in ["german", "deutsch", "de"]:
    return ("German", "de")
  if norm_input in ["french", "francais", "fr"]:
    return ("French", "fr")
  if norm_input in ["japanese", "nihongo", "ja", "jp"]:
    return ("Japanese", "ja")
  if norm_input in ["portuguese", "portugues", "pt"]:
    return ("Portuguese", "pt")
  if norm_input in ["italian", "italiano", "it"]:
    return ("Italian", "it")
  if norm_input in ["korean", "hangul", "ko"]:
    return ("Korean", "ko")

  return (clean_input.title(), "en")


def _is_valid_raw_presentation_id(candidate: str) -> bool:
  """Returns True if candidate looks like a valid Google Drive/Slides file ID (25-60 chars, mixed case/digits, not a snake_case tool or placeholder name)."""
  if not candidate:
    return False
  clean = candidate.strip()
  if clean.startswith("pitchgen-deck-"):
    clean = clean[len("pitchgen-deck-") :].strip()
  if not re.match(r"^[a-zA-Z0-9_-]{25,60}$", clean):
    return False
  if re.match(r"^[a-z_-]+$", clean):
    return False
  if clean.lower().startswith((
      "start_of_user_uploaded",
      "end_of_user_uploaded",
      "enterprise_",
      "pitchgen_",
  )):
    return False
  return True


def extract_presentation_id(prompt_text: str, tool_context=None) -> str:
  """Extracts Presentation ID from URLs, raw ID strings, session state, or Drive attachments without matching snake_case tool names."""
  text_str = str(prompt_text or "").strip()
  if text_str.startswith("pitchgen-deck-"):
    text_str = text_str[len("pitchgen-deck-") :].strip()

  if text_str:
    slides_url_match = re.search(
        r"docs\.google\.com/presentation/d/([a-zA-Z0-9_-]{20,60})", text_str
    )
    if slides_url_match:
      return slides_url_match.group(1).strip()

    drive_url_match = re.search(
        r"drive\.google\.com/(?:file/d/|open\?id=)([a-zA-Z0-9_-]{20,60})",
        text_str,
    )
    if drive_url_match:
      return drive_url_match.group(1).strip()

    for m in re.finditer(r"\b([a-zA-Z0-9_-]{25,60})\b", text_str):
      cand = m.group(1).strip()
      if _is_valid_raw_presentation_id(cand):
        return (
            cand[len("pitchgen-deck-") :].strip()
            if cand.startswith("pitchgen-deck-")
            else cand
        )

  if tool_context:
    state_obj = getattr(tool_context, "state", None)
    if state_obj is not None and hasattr(state_obj, "get"):
      for state_key in ("presentation_id", "deck_url", "canvas_artifact"):
        s_val = str(state_obj.get(state_key) or "").strip()
        if s_val:
          s_id = extract_presentation_id(s_val, None)
          if s_id:
            return s_id

    user_content = getattr(tool_context, "user_content", None)
    if user_content:
      parts = getattr(user_content, "parts", []) or []
      for p in parts:
        file_data = getattr(p, "file_data", None)
        file_uri = (
            str(getattr(file_data, "file_uri", "") or "") if file_data else ""
        )
        uri_str = str(
            getattr(p, "uri", "") or getattr(p, "gcs_uri", "") or file_uri or ""
        )
        if uri_str:
          u_id = extract_presentation_id(uri_str, None)
          if u_id:
            return u_id
        p_text = str(getattr(p, "text", "") or "")
        if (
            "docs.google.com/presentation/d/" in p_text
            and "#slide=id." not in p_text
        ):
          u_id = extract_presentation_id(p_text, None)
          if u_id:
            return u_id

  return ""


def execute_gcs_translation(payload: dict) -> dict:
  print("[PitchGenSkills] Starting GCS-based slide translation...")
  config = load_config()
  project_id = config["default"].get("project_name", "your-gcp-project-id")
  presentation_id = payload.get("presentationId") or payload.get("presentation_id")
  if not presentation_id:
    for k in payload.keys():
      if k not in [
          "presentationId",
          "presentation_id",
          "targetLanguage",
          "isFullDeckTranslation",
          "action",
          "user_ldap",
      ]:
        presentation_id = k
        break
  if not presentation_id:
    presentation_id = "unknown"

  unique_id = str(uuid.uuid4())
  request_bucket_name = config.get(
      "bucket", "translation", fallback=f"translation-uploads-{project_id.replace('pitch-gen-', '')}"
  )
  request_blob_name = f"{presentation_id}_{unique_id}_Request.json"
  request_gcs_url = f"gs://{request_bucket_name}/{request_blob_name}"

  print(
      "[PitchGenSkills] Uploading request payload to GCS URL:"
      f" {request_gcs_url}..."
  )
  storage_client = storage.Client(project=project_id)
  req_bucket = storage_client.bucket(request_bucket_name)
  req_blob = req_bucket.blob(request_blob_name)
  req_blob.upload_from_string(
      json.dumps(payload, indent=2), content_type="application/json"
  )

  print("[PitchGenSkills] Executing TranslationWorkflow...")
  from agents.workflows.translation_workflow import TranslationWorkflow

  skill = TranslationWorkflow(config)
  response_gcs_url = skill.execute(request_gcs_url)
  print(
      f"[PitchGenSkills] Translation complete. Response URL: {response_gcs_url}"
  )

  return {
      "data": {"request": request_gcs_url, "response": response_gcs_url},
      "message": "Success",
  }


def dispatch_payload(payload_json: str, default_action: str = None, client_source: str = "") -> str:
  print(
      "[PitchGenSkills] Dispatching payload"
      f" (default_action={default_action}, client_source={client_source})..."
  )
  try:
    payload = robust_json_loads(payload_json)
  except Exception as e:
    return json.dumps({"error": f"Failed to parse JSON payload: {str(e)}"})

  if isinstance(payload, dict) and "input" in payload and isinstance(payload["input"], dict):
    inp = payload["input"]
    msg_obj = inp.get("message") or inp.get("Message")
    if msg_obj:
      if isinstance(msg_obj, dict):
        payload = msg_obj
      elif isinstance(msg_obj, str):
        try:
          payload = robust_json_loads(msg_obj)
        except Exception:
          pass

  # 1. Check if it's a Slide Search request
  if "search_query" in payload:
    print("[PitchGenSkills] Routed to sidebar_search")
    slide_job = payload.get("slide_job", payload.get("repository", ""))
    return PitchGenSkills.sidebar_search(
        search_query=payload.get("search_query"),
        strict_search=payload.get("strict_search", False),
        user_ldap=payload.get("user_ldap", ""),
        slide_job=slide_job,
    )

  # 2. Check if it's a Sidebar Generate request
  if "slide_content" in payload or payload.get("action") == "add_generate":
    print("[PitchGenSkills] Routed to sidebar_generate")
    return PitchGenSkills.sidebar_generate(
        slide_content=payload.get("slide_content", payload.get("slide_content","")),
        slide_title=payload.get("slide_title", ""),
        slide_layout=payload.get("slide_layout", ""),
        slide_category=payload.get("slide_category", ""),
        deck_id=payload.get("deck_id", ""),
        slide_id=payload.get("slide_id", ""),
        audience=payload.get("audience", ""),
        industry=payload.get("industry", ""),
        product=payload.get("product", ""),
        region=payload.get("region", "GLOBAL"),
        action=payload.get("action", "add_generate"),
        er_number=payload.get("er_number", "21212"),
        user_ldap=payload.get("user_ldap", ""),
        presentation_id=payload.get("presentation_id", ""),
        slide_image_url=payload.get("slide_image_url", ""),
    )

  # 3. Check if it's a Visual Generation / Transformation request
  if "user_inputs" in payload or "existing_slide_image_url" in payload:
    print("[PitchGenSkills] Routed to generate_visual_payload")
    try:
      from agents.visual_agent import VisualAgent

      config = load_config()
      agent = VisualAgent(config)
      result = agent.run_payload(payload)
      return json.dumps(result)
    except Exception as e:
      return json.dumps({"error": str(e)})

  # Check if it's a Phase 2 Slide Generator request
  if "agendas" in payload:
    print("[PitchGenSkills] Routed to slide_generator_skill")
    return PitchGenSkills.slide_generator_skill(payload_json, client_source=client_source)

  # 4. Check if it's an Outline / Agenda generation request
  if "business_context" in payload:
    print("[PitchGenSkills] Routed to create_proposal_outline")
    sol = payload.get("solution") or payload.get("solutions") or ""
    if isinstance(sol, list):
      sol = ", ".join(sol)
    aud = payload.get("audience") or ""
    if isinstance(aud, list):
      aud = ", ".join(aud)
    prod = payload.get("product") or ""
    if isinstance(prod, list):
      prod = ", ".join(prod)
    sales_play = payload.get("salesPlay") or ""
    if isinstance(sales_play, list):
      sales_play = " | ".join(
          str(p).strip() for p in sales_play if str(p).strip()
      )
    sec_sp = payload.get("secondary_sales_play") or ""
    if isinstance(sec_sp, list):
      sec_sp = " | ".join(str(p).strip() for p in sec_sp if str(p).strip())
    if (
        sec_sp
        and str(sec_sp).strip()
        and str(sec_sp).strip() not in str(sales_play)
    ):
      sales_play = (
          f"{sales_play} | {sec_sp.strip()}"
          if sales_play
          else str(sec_sp).strip()
      )

    return PitchGenSkills.create_proposal_outline(
        customer_name=payload.get("customer_name", ""),
        business_context=payload.get("business_context", ""),
        industry=payload.get("industry", ""),
        solution=sol,
        user_ldap=payload.get("user_ldap", ""),
        er_number=payload.get("er_number") or payload.get("erIdGenerate") or "",
        audience=aud,
        region=payload.get("region", ""),
        product=prod,
        request_type=payload.get("request_type", ""),
        presentation_id=payload.get("presentation_id", ""),
        salesPlay=sales_play,
        user_input_id=payload.get("user_input_id", ""),
        sub_industry=payload.get("sub_industry", ""),
        sales_stage=payload.get("sales_stage") or payload.get("salesStage") or "",
        win_cycle=payload.get("win_cycle") or payload.get("winCycle") or "",
        segment=payload.get("segment") or "",
    )

  action = payload.get("action") or payload.get("Action") or default_action
  action_str = str(action).lower() if action else ""

  # 1. Transform Routing (All transform-related actions)
  if action_str == "transform" or action_str in ["transform_text", "transform_slide"]:
    print("[PitchGenSkills] Routed to transform_slide_payload")
    try:
      from agents.slide_engineering_agent import SlideEngineeringAgent

      config = load_config()
      agent = SlideEngineeringAgent(config)
      payload["action"] = "transform"
      result = agent.run_payload(payload)
      return json.dumps(result)
    except Exception as e:
      return json.dumps({"error": str(e)})

  # 2. GCS Slide Translation Flow
  if action_str == "translate" or "targetLanguage" in payload or "presentationId" in payload or "presentation_id" in payload:
    print("[PitchGenSkills] Routed to GCS slide translation flow")
    try:
      res = execute_gcs_translation(payload)
      return json.dumps(res)
    except Exception as e:
      return json.dumps({"error": str(e)})

  return json.dumps({
      "error": f"Unknown payload format or action. Keys: {list(payload.keys())}"
  })

def extract_session_user_email_and_ldap(
    tool_context=None, fallback_ldap: str = ""
) -> tuple[str, str]:
  """Extracts userEmail and derived user_ldap directly from Gemini Enterprise session/tool_context."""
  if tool_context is None:
    return "", fallback_ldap

  # 0. Primary resolution via GE OAuth token exchange and session state
  try:
    from pitchgen_utils.a2ui_util import resolve_ge_user_identity  # pylint: disable=g-import-not-at-top

    email, ldap = resolve_ge_user_identity(
        tool_context=tool_context, fallback_ldap=fallback_ldap
    )
    if email and ldap:
      print(
          f"[PitchGenSkills] Resolved userEmail='{email}' ->"
          f" user_ldap='{ldap}' from Gemini Enterprise session."
      )
      return email, ldap
  except Exception as e:
    print(
        f"[PitchGenSkills] GE identity resolution notice: {e}", file=sys.stderr
    )

  candidates = []

  # 1. Direct attributes on tool_context
  for attr in ["user_id", "user_email", "userEmail", "email"]:
    val = getattr(tool_context, attr, None)
    if val and isinstance(val, str) and "@" in val:
      candidates.append(val.strip())

  # 2. _invocation_context attributes and session
  inv_ctx = getattr(tool_context, "_invocation_context", None) or getattr(
      tool_context, "invocation_context", None
  )
  if inv_ctx:
    for attr in ["user_id", "user_email", "userEmail", "email", "user"]:
      val = getattr(inv_ctx, attr, None)
      if val and isinstance(val, str) and "@" in val:
        candidates.append(val.strip())

    session = getattr(inv_ctx, "session", None) or getattr(
        inv_ctx, "_session", None
    )
    if session:
      for attr in ["user_email", "userEmail", "user_id", "email"]:
        val = getattr(session, attr, None)
        if val and isinstance(val, str) and "@" in val:
          candidates.append(val.strip())
      if isinstance(session, dict):
        val = (
            session.get("userEmail")
            or session.get("user_email")
            or session.get("user_id")
        )
        if val and isinstance(val, str) and "@" in val:
          candidates.append(val.strip())

  # 3. Direct session on tool_context
  session_obj = getattr(tool_context, "session", None) or getattr(
      tool_context, "_session", None
  )
  if session_obj:
    for attr in ["user_email", "userEmail", "user_id", "email"]:
      val = getattr(session_obj, attr, None)
      if val and isinstance(val, str) and "@" in val:
        candidates.append(val.strip())
    if isinstance(session_obj, dict):
      val = (
          session_obj.get("userEmail")
          or session_obj.get("user_email")
          or session_obj.get("user_id")
      )
      if val and isinstance(val, str) and "@" in val:
        candidates.append(val.strip())

  if candidates:
    email = candidates[0]
    ldap = email.split("@")[0].lower().strip()
    print(
        f"[PitchGenSkills] Silently resolved userEmail='{email}' ->"
        f" user_ldap='{ldap}' from Gemini Enterprise session."
    )
    return email, ldap

  return "", fallback_ldap


import requests


class AuthPreservingSession(requests.Session):
  """Preserves Authorization Bearer header across Apps Script 302 redirects (script.google.com -> script.googleusercontent.com)."""

  def rebuild_auth(self, prepared_request, response):
    if "Authorization" in response.request.headers:
      prepared_request.headers["Authorization"] = response.request.headers[
          "Authorization"
      ]


def _post_with_auth_preserving_session(
    url: str, headers: dict, json_payload: dict, timeout: int = 300
):
  """Executes POST using AuthPreservingSession in production while supporting unittest.mock patches on requests.post."""
  if headers and "Authorization" in headers and "/a/macros/google.com/s/" in str(url):
    url = str(url).replace("/a/macros/google.com/s/", "/macros/s/")
  safe_payload = json.loads(
      json.dumps(
          json_payload,
          default=lambda o: list(o) if isinstance(o, set) else str(o),
      )
  )
  if (
      hasattr(requests.post, "_mock_name")
      or "Mock" in type(requests.post).__name__
  ):
    return requests.post(
        url,
        headers=headers,
        json=safe_payload,
        allow_redirects=True,
        timeout=timeout,
    )
  session = AuthPreservingSession()
  return session.post(
      url,
      headers=headers,
      json=safe_payload,
      allow_redirects=True,
      timeout=timeout,
  )


def _build_apps_script_candidate_tokens(
    clean_ldap: str,
    user_oauth_token: str = None,
    tool_context=None,
) -> list[tuple[str, str]]:
  """Builds the 4-tier candidate token waterfall combining origin/GE and multi-user service-owner fallback:

  1. Short-lived end-user OAuth token (explicit user_oauth_token or ADK
  tool_context / request header extraction)
  2. Long-lived user refresh token stored in GCS (get_user_access_token)
  3. PitchGen service-owner token ('seller_user') for 1st-time users without Apps
  Script consent or bucket ACLs
  4. Vertex AI Service Account ADC bearer token (get_adc_bearer_token from
  origin/GE)
  """
  from oauth_helper import (
      get_adc_bearer_token,
      get_cached_active_token,
      get_enduser_bearer_token,
      get_user_access_token,
  )

  candidate_tokens: list[tuple[str, str]] = []
  seen_tokens: set[str] = set()

  def _add_candidate(label: str, tok: str | None):
    if (
        tok
        and isinstance(tok, str)
        and tok.strip()
        and tok.strip() not in seen_tokens
    ):
      seen_tokens.add(tok.strip())
      candidate_tokens.append((label, tok.strip()))

  # Tier 1: Live end-user bearer token (argument or ADK tool_context / headers)
  _add_candidate("user_short_lived", user_oauth_token)
  try:
    _add_candidate(
        "user_header", get_enduser_bearer_token(tool_context=tool_context)
    )
  except Exception:
    pass

  # Tier 2: Long-lived user refresh token in GCS
  if clean_ldap:
    try:
      _add_candidate(
          "user_gcs",
          get_user_access_token(clean_ldap)
          or get_cached_active_token(clean_ldap),
      )
    except Exception:
      pass

  # Tier 3: PitchGen Service-Owner token ('seller_user') for 1st-time / non-owner users
  service_owner_ldap = os.environ.get("PITCHGEN_SERVICE_OWNER_LDAP", "seller_user")
  if clean_ldap != service_owner_ldap:
    try:
      _add_candidate(
          "service_owner",
          get_user_access_token(service_owner_ldap)
          or get_cached_active_token(service_owner_ldap),
      )
    except Exception:
      pass

  # Tier 4: Vertex AI Reasoning Engine ADC token (from origin/GE)
  try:
    _add_candidate("adc", get_adc_bearer_token())
  except Exception:
    pass

  return candidate_tokens


def execute_apps_script_request(
    payload: dict,
    user_ldap: str,
    user_oauth_token: str = None,
    tool_context=None,
) -> dict:
  """Calls the Google Apps Script Web App using AuthPreservingSession and the 4-tier token waterfall."""
  from oauth_helper import get_authorization_url

  clean_ldap = user_ldap.split("@")[0].lower().strip() if user_ldap else ""
  if clean_ldap in ("unknown", "unknown_user", "user", "none"):
    clean_ldap = ""

  candidate_tokens = _build_apps_script_candidate_tokens(
      clean_ldap=clean_ldap,
      user_oauth_token=user_oauth_token,
      tool_context=tool_context,
  )

  if not candidate_tokens:
    auth_url = get_authorization_url(clean_ldap or "unknown")
    print(
        f"[PitchGenSkills] User {clean_ldap} is unauthorized. Returning login"
        " URL.",
        flush=True,
    )
    return {
        "status": "auth_required",
        "auth_url": auth_url,
        "message": (
            f"Please authorize PitchGen to access presentations in your Google Drive by clicking this link: {auth_url}\n\n"
            "Once authorized, simply say 'continue' or repeat your request."
        ),
    }

  try:
    config = load_config()
    url = config.get(
        "default",
        "render_api_url",
        fallback="https://script.google.com/macros/s/YOUR_APPS_SCRIPT_DEPLOYMENT_ID/exec",
    )
  except Exception:
    url = "https://script.google.com/macros/s/YOUR_APPS_SCRIPT_DEPLOYMENT_ID/exec"

  action_val = str((payload or {}).get("action") or "").strip()
  url_pool = [
      url,
      "https://script.google.com/macros/s/YOUR_APPS_SCRIPT_DEPLOYMENT_ID/exec",
  ]
  if not action_val:
    url_pool.append(
        "https://script.google.com/macros/s/YOUR_APPS_SCRIPT_DEPLOYMENT_ID/exec"
    )
  candidate_urls = []
  for u in url_pool:
    if u and u not in candidate_urls:
      candidate_urls.append(u)

  service_owner_ldap = os.environ.get("PITCHGEN_SERVICE_OWNER_LDAP", "seller_user")
  effective_ldap = clean_ldap or service_owner_ldap
  user_email = f"{effective_ldap}@example.com"

  req_payload = dict(payload)
  req_payload["user_ldap"] = effective_ldap
  req_payload["userEmail"] = user_email
  req_payload["user_email"] = user_email

  last_err_dict = {"status": "error", "error": "Apps Script request failed"}
  for target_url in candidate_urls:
    for token_source, token in candidate_tokens:
      headers = {
          "Authorization": f"Bearer {token}",
          "Content-Type": "application/json",
      }
      try:
        print(
            f"[PitchGenSkills] Executing Apps Script POST call to URL {target_url}"
            f" (auth={token_source})...",
            flush=True,
        )
        response = _post_with_auth_preserving_session(
            target_url, headers=headers, json_payload=req_payload, timeout=300
        )

        if (
            response.status_code == 200
            and not response.text.strip().startswith("<!DOCTYPE html>")
            and not response.text.strip().startswith("<html")
        ):
          print(
              f"Success! Response from Apps Script (auth={token_source}):",
              response.text[:300],
              flush=True,
          )
          try:
            resp_data = response.json()
            if (
                isinstance(resp_data, dict)
                and resp_data.get("error")
                and not resp_data.get("deckURL")
                and not resp_data.get("data")
            ):
              last_err_dict = resp_data
              continue
            if isinstance(resp_data, dict) and "deckURL" in resp_data:
              raw_u = resp_data["deckURL"]
              m_id = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", str(raw_u))
              if m_id:
                resp_data["deckURL"] = (
                    f"https://docs.google.com/presentation/d/{m_id.group(1)}/edit"
                )
            return resp_data
          except Exception:
            return {
                "status": 200,
                "deckURL": response.text.strip(),
                "raw_text": response.text.strip(),
            }
        else:
          print(
              f"Error {response.status_code} calling Apps Script"
              f" (auth={token_source}): {response.text[:200]}",
              flush=True,
          )
          last_err_dict = {
              "status": response.status_code,
              "error": f"Apps Script returned status {response.status_code}",
          }
      except Exception as e:
        print(
            "[PitchGenSkills] HTTP error calling Apps Script"
            f" (auth={token_source}): {e}",
            flush=True,
        )
        last_err_dict = {
            "status": "error",
            "error": f"Failed to connect to Apps Script: {str(e)}",
        }

  return last_err_dict


def format_pitchgen_deck_title(outputs_data: dict | None) -> str:
  """Formats the presentation title to match the Google Slides UI Extension ([PitchGen] Account | Strategic Theme (Mon YYYY))."""
  import datetime

  json_data = outputs_data or {}
  context = (
      json_data.get("context")
      if isinstance(json_data.get("context"), dict)
      else {}
  )
  outline = (
      json_data.get("outline")
      if isinstance(json_data.get("outline"), dict)
      else {}
  )

  raw_cust = str(
      json_data.get("customer_name")
      or json_data.get("account_name")
      or context.get("customer_name")
      or context.get("customer")
      or outline.get("customer_name")
      or outline.get("customer")
      or ""
  ).strip()
  if raw_cust in ("-", "generic", "Generic"):
    raw_cust = ""

  raw_theme = str(
      json_data.get("deck_theme")
      or json_data.get("strategic_theme")
      or outline.get("title")
      or outline.get("deck_theme")
      or json_data.get("primary_play")
      or json_data.get("sales_play")
      or context.get("salesPlay")
      or context.get("industry")
      or json_data.get("industry")
      or "Strategic Transformation"
  ).strip()

  sections = (
      json_data.get("sections")
      if isinstance(json_data.get("sections"), dict)
      else {}
  )
  title_sec = (
      sections.get("title") if isinstance(sections.get("title"), dict) else {}
  )
  title_slides = (
      title_sec.get("slides")
      if isinstance(title_sec.get("slides"), dict)
      else {}
  )
  title_slide = title_slides.get("1") or title_slides.get("0") or {}
  placeholders = (
      title_slide.get("placeholders")
      if isinstance(title_slide.get("placeholders"), dict)
      else {}
  )
  cand_hdr = (
      placeholders.get("{{TITLE}}")
      or placeholders.get("title")
      or placeholders.get("Title")
      or ""
  )
  if cand_hdr:
    slide_hdr = re.sub(r"^[0-9.\-\s]+", "", str(cand_hdr)).strip()
    if len(slide_hdr) > 5:
      raw_theme = slide_hdr

  if raw_cust:
    raw_theme = re.sub(
        rf"^Pitch Deck for {re.escape(raw_cust)}[:\s\-]*",
        "",
        raw_theme,
        flags=re.IGNORECASE,
    ).strip()
    raw_theme = re.sub(
        rf"^{re.escape(raw_cust)}[:\s\-]*",
        "",
        raw_theme,
        flags=re.IGNORECASE,
    ).strip()

  if not raw_theme:
    raw_theme = "Strategic Transformation"

  if len(raw_theme) > 55:
    raw_theme = raw_theme[:52].rstrip() + "..."

  date_str = datetime.datetime.now().strftime("%b %Y")
  if raw_cust:
    return f"[PitchGen] {raw_cust} | {raw_theme} ({date_str})"
  return f"[PitchGen] {raw_theme} ({date_str})"


def _format_reusable_slide_date(date_str: str) -> str:
  """Formats a reusable slide date string matching copySlide.js formatDate."""
  if not date_str or len(str(date_str).strip()) <= 3:
    return ""
  import datetime

  s = str(date_str).strip()
  for fmt in (
      "%Y-%m-%d",
      "%Y/%m/%d",
      "%Y-%m-%dT%H:%M:%S",
      "%Y-%m-%dT%H:%M:%SZ",
      "%m/%d/%Y",
  ):
    try:
      dt = datetime.datetime.strptime(s[:19], fmt)
      day = dt.day
      suffix = (
          "th"
          if 4 <= day <= 20
          else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
      )
      return f" ({day}{suffix} {dt.strftime('%b %Y')})"
    except Exception:
      continue
  return f" ({s})"


def post_process_assembled_presentation(
    presentation_id: str,
    token: str,
    outputs_data: dict | None = None,
    reusable_slides: dict | None = None,
    config=None,
    user_ldap: str = "",
) -> str:
  """Applies full UI Extension parity to an assembled presentation via Google Drive & Slides REST APIs:

  1. Renames the presentation to '[PitchGen] <Account> | <Strategic Theme> (<Mon
  YYYY>)'.
  1b. Grants Editor ('writer') permission on the presentation in Google Drive to
  user_ldap@example.com.
  2. Attaches '🔗 Source Slide: <Title> (<Date>)\\n<slideUrl>' (with clickable
  hyperlink) to reusable slides' speaker notes.
  3. Runs TextTransformerWorkflow.execute_deck_holistic across the assembled
  presentation and updates reusable slide shapes while preserving paragraph
  formatting.
  """
  import requests

  formatted_title = format_pitchgen_deck_title(outputs_data)
  if not presentation_id or not token:
    return formatted_title

  headers = {
      "Authorization": f"Bearer {token}",
      "Content-Type": "application/json",
  }

  # 1. Rename presentation in Google Drive to match UI Extension (ContentGen.js)
  try:
    drive_url = f"https://www.googleapis.com/drive/v3/files/{presentation_id}?supportsAllDrives=true"
    r_drive = requests.patch(
        drive_url, headers=headers, json={"name": formatted_title}, timeout=30
    )
    if r_drive.status_code == 200:
      print(
          f"[PitchGenSkills] Renamed presentation {presentation_id} to:"
          f" {formatted_title}",
          flush=True,
      )
    else:
      print(
          "[PitchGenSkills] Warning: Drive rename returned"
          f" {r_drive.status_code}: {r_drive.text[:200]}",
          flush=True,
      )
  except Exception as rename_err:
    print(
        "[PitchGenSkills] Warning: Failed to rename presentation"
        f" {presentation_id}: {rename_err}",
        flush=True,
    )

  # 1b. Ensure requesting user (e.g. admin@example.com) receives Drive Ownership (or Editor fallback) when deck was created via service_owner fallback token
  ctx_ldap = (
      user_ldap
      or ((outputs_data or {}).get("context") or {}).get("user_ldap")
      or ""
  )
  clean_target_ldap = (
      str(ctx_ldap).split("@")[0].lower().strip() if ctx_ldap else ""
  )
  if clean_target_ldap and clean_target_ldap not in (
      "unknown",
      "unknown_user",
      "user",
      "none",
  ):
    target_email = f"{clean_target_ldap}@example.com"
    try:
      transferred_owner = False
      if clean_target_ldap != "seller_user":
        owner_perm_url = (
            f"https://www.googleapis.com/drive/v3/files/{presentation_id}/permissions"
            "?supportsAllDrives=true&transferOwnership=true"
        )
        r_own = requests.post(
            owner_perm_url,
            headers=headers,
            json={
                "role": "owner",
                "type": "user",
                "emailAddress": target_email,
            },
            timeout=20,
        )
        if r_own.status_code in (200, 201):
          transferred_owner = True
          print(
              "[PitchGenSkills] Transferred Drive Ownership of"
              f" {presentation_id} to {target_email}",
              flush=True,
          )
      if not transferred_owner:
        perm_url = (
            f"https://www.googleapis.com/drive/v3/files/{presentation_id}/permissions"
            "?supportsAllDrives=true&sendNotificationEmail=false"
        )
        r_perm = requests.post(
            perm_url,
            headers=headers,
            json={
                "role": "writer",
                "type": "user",
                "emailAddress": target_email,
            },
            timeout=20,
        )
        if r_perm.status_code in (200, 201):
          print(
              "[PitchGenSkills] Granted Drive Editor access on"
              f" {presentation_id} to {target_email}",
              flush=True,
          )
    except Exception as perm_err:
      print(
          "[PitchGenSkills] Warning: Drive permission share notice for"
          f" {target_email}: {perm_err}",
          flush=True,
      )

  # 2. Fetch assembled presentation via Google Slides API
  try:
    slides_api_url = (
        f"https://slides.googleapis.com/v1/presentations/{presentation_id}"
    )
    r_pres = requests.get(slides_api_url, headers=headers, timeout=45)
    if r_pres.status_code != 200:
      print(
          f"[PitchGenSkills] Warning: Slides GET returned {r_pres.status_code}:"
          f" {r_pres.text[:200]}",
          flush=True,
      )
      return formatted_title
    pres_data = r_pres.json()
  except Exception as fetch_err:
    print(
        "[PitchGenSkills] Warning: Failed to fetch presentation"
        f" {presentation_id}: {fetch_err}"
    )
    return formatted_title

  slides = pres_data.get("slides", [])
  if not slides:
    return formatted_title

  if config is None:
    config = load_config()
  ctx = (
      (outputs_data or {}).get("context")
      if isinstance((outputs_data or {}).get("context"), dict)
      else {}
  )
  cust_name = (
      (outputs_data or {}).get("customer_name")
      or ctx.get("customer_name")
      or ""
  ).strip()
  c_name = cust_name
  ind_name = (ctx.get("industry") or "").strip()

  # Build ordered list of reusable slide suggestions matching copySlidesFromSuggestions section order
  def _sec_sort_key(k: str) -> float:
    ks = str(k).strip()
    if ks == "title":
      return 0.0
    if ks == "agenda":
      return 0.5
    if ks == "thank_you":
      return 9999.0
    if ks.startswith("divider_"):
      try:
        return float(ks.replace("divider_", "")) - 0.1
      except Exception:
        return 998.0
    try:
      return float(ks)
    except Exception:
      return 999.0

  ordered_reusable_sugs = []
  if isinstance(reusable_slides, dict):
    for sec_key in sorted(reusable_slides.keys(), key=_sec_sort_key):
      sec_obj = reusable_slides.get(sec_key)
      sugs = sec_obj.get("suggestions", []) if isinstance(sec_obj, dict) else []
      for sug in sugs:
        if not isinstance(sug, dict):
          continue
        vals = sug.get("values") or []
        orig_txt_parts = [
            str(sug.get("name") or ""),
            str(sug.get("original_title") or ""),
            str(sug.get("title") or ""),
            str(sug.get("original_content") or ""),
            str(sug.get("content") or ""),
            str(sug.get("text") or ""),
            str(sug.get("slide_summary") or ""),
        ]
        orig_txt_combined = " ".join(p.strip() for p in orig_txt_parts if p and p.strip()).lower()
        for val_url in vals:
          if val_url and isinstance(val_url, str):
            ordered_reusable_sugs.append({
                "section": sec_key,
                "slide_url": val_url.strip(),
                "slide_label": (
                    str(
                        sug.get("name")
                        or sug.get("original_title")
                        or "Original Reusable Slide"
                    ).strip()
                ),
                "original_text": orig_txt_combined,
                "date_str": _format_reusable_slide_date(sug.get("date") or ""),
                "is_proof_point": bool(
                    sug.get("_source_datastore_key") == "cust_ref"
                    or sug.get("is_cust_ref")
                    or sug.get("is_proof_point")
                ),
            })

  def _extract_raw_slide_notes(sl_item: dict) -> str:
    notes_page = sl_item.get("slideProperties", {}).get("notesPage", {})
    notes_sh_id = (
        notes_page.get("notesProperties", {}).get("speakerNotesObjectId", "")
    )
    parts = []
    for npe in notes_page.get("pageElements", []):
      if notes_sh_id and npe.get("objectId") != notes_sh_id:
        continue
      for te in npe.get("shape", {}).get("text", {}).get("textElements", []):
        if "textRun" in te:
          parts.append(te["textRun"].get("content", ""))
    return "".join(parts).strip()

  # Pre-scan all slides' speaker notes to reserve any suggestion explicitly linked by URL
  reserved_sug_by_slide_id: dict[str, int] = {}
  all_reserved_sug_indices: set[int] = set()
  for sl_pre in slides:
    sl_pre_id = sl_pre.get("objectId", "")
    n_pre = _extract_raw_slide_notes(sl_pre)
    if not sl_pre_id or not n_pre:
      continue
    for idx_u, su in enumerate(ordered_reusable_sugs):
      if idx_u in all_reserved_sug_indices:
        continue
      s_url = str(su.get("slide_url") or "").strip()
      if s_url and s_url in n_pre:
        reserved_sug_by_slide_id[sl_pre_id] = idx_u
        all_reserved_sug_indices.add(idx_u)
        break

  def _match_reusable_sug_item(
      comb_low: str,
      notes_str: str,
      sugs_list: list,
      used_indices: set,
      cursor_idx: int,
      sec_hint: str = "",
      slide_obj_id: str = "",
  ) -> tuple[dict | None, int]:
    if not sugs_list:
      return None, cursor_idx
    if slide_obj_id and slide_obj_id in reserved_sug_by_slide_id:
      r_idx = reserved_sug_by_slide_id[slide_obj_id]
      if 0 <= r_idx < len(sugs_list):
        used_indices.add(r_idx)
        return sugs_list[r_idx], max(cursor_idx, r_idx + 1)
    # 1. Exact URL or slide_id match in speaker notes (written by copySlide.js)
    if notes_str:
      for idx_u, su in enumerate(sugs_list):
        if idx_u in used_indices:
          continue
        s_url = str(su.get("slide_url") or "").strip()
        if s_url and s_url in notes_str:
          used_indices.add(idx_u)
          return su, max(cursor_idx, idx_u + 1)
      for idx_u, su in enumerate(sugs_list):
        s_url = str(su.get("slide_url") or "").strip()
        if s_url and s_url in notes_str:
          used_indices.add(idx_u)
          return su, max(cursor_idx, idx_u + 1)

    # Never match an empty/blank slide via token overlap or cursor fallback
    if not (comb_low or "").strip():
      return None, cursor_idx

    # 2. Content/title token overlap match among unused suggestions
    slide_tokens = {
        w for w in re.findall(r"[a-z0-9]{4,}", comb_low or "")
        if w not in {"google", "cloud", "with", "from", "that", "this", "your", "proprietary", "confidential"}
    }
    best_idx = None
    best_score = 0.0
    for idx_u, su in enumerate(sugs_list):
      if idx_u in used_indices or idx_u in all_reserved_sug_indices:
        continue
      su_label_low = str(su.get("slide_label") or "").lower()
      su_txt_low = str(su.get("original_text") or su_label_low).lower()
      su_tokens = {
          w for w in re.findall(r"[a-z0-9]{4,}", su_txt_low)
          if w not in {"google", "cloud", "with", "from", "that", "this", "your", "proprietary", "confidential"}
      }
      overlap = len(slide_tokens & su_tokens) if (slide_tokens and su_tokens) else 0
      score = float(overlap)
      if su_label_low and len(su_label_low) >= 6 and su_label_low in (comb_low or ""):
        score += 6.0
      if sec_hint and str(su.get("section") or "") == str(sec_hint):
        score += 0.5
      if score > best_score:
        best_score = score
        best_idx = idx_u

    if best_idx is not None and best_score >= 2.5:
      used_indices.add(best_idx)
      return sugs_list[best_idx], max(cursor_idx, best_idx + 1)

    # 3. Sequential cursor fallback across unused, unreserved suggestions
    for idx_u in range(cursor_idx, len(sugs_list)):
      if idx_u not in used_indices and idx_u not in all_reserved_sug_indices:
        used_indices.add(idx_u)
        return sugs_list[idx_u], idx_u + 1
    for idx_u in range(len(sugs_list)):
      if idx_u not in used_indices and idx_u not in all_reserved_sug_indices:
        used_indices.add(idx_u)
        return sugs_list[idx_u], cursor_idx
    return None, cursor_idx

  # Collect known Phase 2 generated slide titles and section mapping from outputs_data["sections"]
  known_generated_titles = set()
  known_generated_title_to_sec = {}
  known_generated_title_to_ph = {}
  slide_id_to_agenda_sec: dict[str, str] = {}
  sections_dict = (
      (outputs_data or {}).get("sections")
      if isinstance((outputs_data or {}).get("sections"), dict)
      else {}
  )
  agendas_lookup_dict = (
      (outputs_data or {}).get("agendas")
      if isinstance((outputs_data or {}).get("agendas"), dict)
      else (ctx.get("agendas") if isinstance(ctx.get("agendas"), dict) else {})
  )
  ordered_sec_keys = [
      str(sk)
      for sk in sorted(sections_dict.keys(), key=_sec_sort_key)
      if str(sk) not in ("title", "agenda", "thank_you")
      and not str(sk).startswith("divider_")
  ]
  bespoke_title_to_sec: list[tuple[str, str]] = []
  ordered_bespoke_sec_queue: list[str] = []
  for sec_k in ordered_sec_keys:
    sec_v = sections_dict.get(sec_k)
    sec_slides = sec_v.get("slides", {}) if isinstance(sec_v, dict) else {}
    for _, sl_obj in sec_slides.items():
      if isinstance(sl_obj, dict):
        ph = sl_obj.get("placeholders") or {}
        raw_b_title = str(
            ph.get("title") or ph.get("{{TITLE}}") or ph.get("Title") or ""
        ).strip()
        if len(raw_b_title) >= 6:
          bespoke_title_to_sec.append((raw_b_title.lower(), str(sec_k)))
        ordered_bespoke_sec_queue.append(str(sec_k))
        for tk, raw_tv in ph.items():
          tv = str(raw_tv or "").strip()
          min_len = 6 if str(tk) in ("title", "{{TITLE}}", "Title", "header1", "subtitle", "header", "subheader1", "item1", "text1") else 12
          if len(tv) >= min_len:
            tv_low = tv.lower()
            known_generated_titles.add(tv_low)
            if (
                str(tk) in ("title", "{{TITLE}}", "Title")
                or tv_low not in known_generated_title_to_sec
            ):
              known_generated_title_to_sec[tv_low] = str(sec_k)
            known_generated_title_to_ph[tv_low] = ph

  # Enforce CVI Framework Slide Order BEFORE holistic text transformation
  # (Within each section: Section Divider -> Bespoke Thesis Opener [B_1] -> CVI-Ordered Reusable Slides [R_1..R_m] -> Bespoke Synthesis/Implication [B_2+])
  def _flatten_page_elements(elems: list) -> list:
    out = []
    for el in elems or []:
      if not isinstance(el, dict):
        continue
      grp = el.get("elementGroup")
      if isinstance(grp, dict) and grp.get("children"):
        out.extend(_flatten_page_elements(grp.get("children", [])))
      else:
        out.append(el)
    return out

  def _extract_raw_slide_texts(sl_item: dict) -> list:
    res = []
    for pe in _flatten_page_elements(sl_item.get("pageElements", [])):
      sh = pe.get("shape")
      if not sh:
        continue
      txt = "".join(
          te.get("textRun", {}).get("content", "")
          for te in sh.get("text", {}).get("textElements", [])
          if te.get("textRun")
      ).strip()
      if txt:
        res.append(re.sub(r"\s+", " ", txt))
    return res

  def _is_thank_you_text(texts_list: list) -> bool:
    non_footer = [
        t.strip()
        for t in texts_list or []
        if t
        and t.strip()
        and "proprietary & confidential" not in t.lower()
        and not t.strip().isdigit()
    ]
    if not non_footer:
      return False
    nf_low = " ".join(non_footer).lower().strip(" .!?:;-")
    if nf_low in (
        "thank you",
        "thank you.",
        "thank you!",
        "you thank",
        "thanks",
        "questions",
        "questions?",
        "q&a",
        "q & a",
    ):
      return True
    nf_words = set(re.findall(r"[a-z&]+", nf_low))
    if "thank" in nf_words and "you" in nf_words and len(nf_low) <= 45:
      return True
    if (
        nf_words
        and nf_words <= {"thank", "you", "thanks", "questions", "q&a", "q", "a"}
        and len(nf_low) <= 45
    ):
      return True
    return False

  # Delete any completely empty default blank slide (e.g. SLIDES_API..._0 at index 0 or end),
  # trailing 'Internal Context - Remove this slide' debug slide, near-duplicate content slides,
  # or fallback bespoke slides in cloudhub strategy when >=3 reusable slides are already present.
  if len(slides) > 1:
    deck_strat_low = (
        str(
            ctx.get("deck_strategy")
            or (outputs_data or {}).get("deck_strategy")
            or ""
        )
        .strip()
        .lower()
    )
    reusable_slide_count = sum(
        1
        for sl_chk in slides
        if "🔗 Source Slide:" in _extract_raw_slide_notes(sl_chk)
    )
    non_blank_slides = []
    blank_del_reqs = []
    seen_slide_token_sets: list[tuple[int, set[str]]] = []
    for idx_b, sl_b in enumerate(slides):
      b_texts = _extract_raw_slide_texts(sl_b)
      b_comb_low = " ".join(b_texts).lower()
      b_notes = _extract_raw_slide_notes(sl_b)
      b_is_reusable = "🔗 Source Slide:" in b_notes
      b_has_visual = any(
          "image" in pe
          or "table" in pe
          or "sheetsChart" in pe
          or "video" in pe
          or "elementGroup" in pe
          for pe in sl_b.get("pageElements", [])
      )
      is_trailing_internal_debug = idx_b > 0 and any(
          kw in b_comb_low
          for kw in (
              "internal context",
              "remove this slide",
              "{{user_ldap}}",
              "{{er_number}}",
              "opportunity id",
          )
      )
      b_tokens = {
          w
          for w in re.findall(r"[a-z0-9]{4,}", b_comb_low)
          if w not in {"google", "cloud", "proprietary", "confidential"}
      }
      is_near_dup_slide = False
      if idx_b >= 2 and len(b_tokens) >= 8:
        for prev_idx, prev_tokens in seen_slide_token_sets:
          overlap_ratio = len(b_tokens & prev_tokens) / max(
              1, min(len(b_tokens), len(prev_tokens))
          )
          if overlap_ratio >= 0.88:
            is_near_dup_slide = True
            print(
                "[PitchGenSkills] Removing near-duplicate slide at index"
                f" {idx_b + 1} (overlap={overlap_ratio:.2f} with slide"
                f" {prev_idx + 1})"
            )
            break
      is_closing_ty = _is_thank_you_text(b_texts) and not b_is_reusable
      is_imported_reusable_ty = _is_thank_you_text(b_texts) and b_is_reusable
      is_agenda_sl = idx_b <= 2 and (
          "agenda" in b_comb_low or "table of contents" in b_comb_low
      )
      is_cloudhub_fallback_bespoke = (
          deck_strat_low == "cloudhub"
          and reusable_slide_count >= 3
          and idx_b >= 1
          and not b_is_reusable
          and not is_closing_ty
          and not is_agenda_sl
          and (idx_b >= 2 or "proposal" not in b_comb_low)
      )
      if (
          is_trailing_internal_debug
          or is_near_dup_slide
          or is_imported_reusable_ty
          or is_cloudhub_fallback_bespoke
          or (
              not b_texts
              and not b_is_reusable
              and not b_has_visual
              and len(sl_b.get("pageElements", [])) <= 2
          )
      ):
        b_sid = sl_b.get("objectId", "")
        if b_sid:
          print(
              "[PitchGenSkills] Removing blank/debug/dup/cloudhub-bespoke"
              f" slide {b_sid} at index {idx_b + 1} before CVI sorting"
          )
          blank_del_reqs.append({"deleteObject": {"objectId": b_sid}})
        continue
      if idx_b >= 1 and len(b_tokens) >= 8:
        seen_slide_token_sets.append((idx_b, b_tokens))
      non_blank_slides.append(sl_b)
    if blank_del_reqs and non_blank_slides:
      try:
        r_bdel = requests.post(
            f"https://slides.googleapis.com/v1/presentations/{presentation_id}:batchUpdate",
            headers=headers,
            json={"requests": blank_del_reqs},
            timeout=25,
        )
        if r_bdel.status_code == 200:
          slides = non_blank_slides
      except Exception as bdel_err:
        print(
            "[PitchGenSkills] Warning: Blank slide pre-delete error:"
            f" {bdel_err}"
        )

  if slides and ordered_sec_keys and ordered_reusable_sugs:
    prefix_slides = []
    suffix_slides = []
    sec_buckets = {
        sk: {"dividers": [], "bespoke": [], "reusable": []}
        for sk in ordered_sec_keys
    }
    extra_sec_keys = []
    re_sort_cursor = 0
    re_sort_used_indices: set[int] = set()
    last_seen_sec_k = ordered_sec_keys[0]

    for idx_s, sl_item in enumerate(slides):
      raw_t_list = _extract_raw_slide_texts(sl_item)
      comb_low = " ".join(raw_t_list).lower()
      raw_notes_str = _extract_raw_slide_notes(sl_item)
      has_source_slide_note = "🔗 Source Slide:" in raw_notes_str or any(
          str(su.get("slide_url") or "") in raw_notes_str
          for su in ordered_reusable_sugs
          if su.get("slide_url")
      )

      is_s0_internal = any(
          kw in comb_low
          for kw in (
              "internal context",
              "remove this slide",
              "user input",
              "opportunity id",
              "{{user_ldap}}",
              "{{er_number}}",
          )
      )
      is_s_title = idx_s <= 1 and (
          idx_s == 0
          or "proposal" in comb_low
          or "pitch" in comb_low
          or "prepared for" in comb_low
          or (
              outputs_data
              and str(outputs_data.get("deck_theme") or "").lower() in comb_low
          )
      )
      is_s_agenda = idx_s <= 2 and (
          "agenda" in comb_low
          or "table of contents" in comb_low
          or (
              idx_s == 1
              and not is_s_title
              and not _is_thank_you_text(raw_t_list)
          )
      )
      is_s_thank_you = (
          not has_source_slide_note and _is_thank_you_text(raw_t_list)
      ) or (
          idx_s >= len(slides) - 2
          and (
              _is_thank_you_text(raw_t_list)
              or (
                  idx_s == len(slides) - 1
                  and not raw_t_list
                  and len(sl_item.get("pageElements", [])) <= 4
              )
          )
      )

      if is_s0_internal or is_s_title or is_s_agenda:
        prefix_slides.append(sl_item)
        continue
      if is_s_thank_you:
        suffix_slides.append(sl_item)
        continue

      is_s_divider = bool(
          not has_source_slide_note
          and len(raw_t_list) <= 3
          and (
              re.match(r"^(0\d|\d{1,2})\s", comb_low)
              or re.match(r"^(section\s*\d|divider)", comb_low)
              or re.match(r"^(0[1-9]|10)\b", comb_low)
          )
      )
      if is_s_divider:
        m_div = re.match(r"^0?([1-9]\d?)\b", comb_low)
        div_sec = str(m_div.group(1)) if m_div else last_seen_sec_k
        if div_sec not in sec_buckets:
          sec_buckets[div_sec] = {"dividers": [], "bespoke": [], "reusable": []}
          extra_sec_keys.append(div_sec)
        sec_buckets[div_sec]["dividers"].append(sl_item)
        last_seen_sec_k = div_sec
        continue

      matched_b_sec = None
      if not has_source_slide_note:
        for b_ttl, b_sec in bespoke_title_to_sec:
          if b_ttl and (b_ttl in comb_low or comb_low.startswith(b_ttl[:30])):
            matched_b_sec = b_sec
            break
        if matched_b_sec is None and ordered_bespoke_sec_queue:
          matched_b_sec = ordered_bespoke_sec_queue.pop(0)
        else:
          for idx_q, q_sec in enumerate(ordered_bespoke_sec_queue):
            if q_sec == matched_b_sec:
              ordered_bespoke_sec_queue.pop(idx_q)
              break
        if matched_b_sec is None:
          for gt, g_sec in known_generated_title_to_sec.items():
            if gt and (gt in comb_low or comb_low.startswith(gt[:30])):
              matched_b_sec = g_sec
              break
        if matched_b_sec is None:
          matched_b_sec = last_seen_sec_k

      if matched_b_sec is not None:
        if matched_b_sec not in sec_buckets:
          sec_buckets[matched_b_sec] = {
              "dividers": [],
              "bespoke": [],
              "reusable": [],
          }
          extra_sec_keys.append(matched_b_sec)
        sec_buckets[matched_b_sec]["bespoke"].append(sl_item)
        last_seen_sec_k = matched_b_sec
      else:
        sug_item, re_sort_cursor = _match_reusable_sug_item(
            comb_low,
            raw_notes_str,
            ordered_reusable_sugs,
            re_sort_used_indices,
            re_sort_cursor,
            sec_hint=last_seen_sec_k,
            slide_obj_id=sl_item.get("objectId", ""),
        )
        r_sec = str((sug_item or {}).get("section") or last_seen_sec_k)
        if r_sec not in sec_buckets:
          sec_buckets[r_sec] = {"dividers": [], "bespoke": [], "reusable": []}
          extra_sec_keys.append(r_sec)
        sec_buckets[r_sec]["reusable"].append((sl_item, sug_item))
        last_seen_sec_k = r_sec

    # Ensure every reusable slide has native Google Slides SlideLinkingMode.LINKED
    # (If the legacy fallback Apps Script created the deck without linking, relink them in-place now)
    unlinked_relink_items = []
    for sk_chk in sec_buckets:
      for sl_obj_chk, sug_chk in sec_buckets[sk_chk].get("reusable", []):
        if not isinstance(sl_obj_chk, dict) or not isinstance(sug_chk, dict):
          continue
        s_url_chk = str(sug_chk.get("slide_url") or "").strip()
        if not s_url_chk:
          continue
        n_str_chk = _extract_raw_slide_notes(sl_obj_chk)
        if "🔗 Source Slide:" not in n_str_chk:
          m_p = re.search(r"/presentation/d/([a-zA-Z0-9_-]+)", s_url_chk)
          m_s = re.search(r"slide=id\.([a-zA-Z0-9_-]+)", s_url_chk)
          if m_p:
            unlinked_relink_items.append({
                "oldSlideId": sl_obj_chk.get("objectId", ""),
                "sourcePresId": m_p.group(1),
                "sourceSlideId": m_s.group(1) if m_s else "",
                "slideUrl": s_url_chk,
                "slideLabel": str(sug_chk.get("slide_label") or "Original Reusable Slide"),
                "fallbackTitle": str(sug_chk.get("slide_label") or ""),
            })
    if unlinked_relink_items:
      try:
        print(
            f"[PitchGenSkills] Auto-relinking {len(unlinked_relink_items)} reusable slides"
            f" with SlideLinkingMode.LINKED on {presentation_id}...",
            flush=True,
        )
        relink_resp = execute_apps_script_request(
            payload={
                "action": "relink_slides",
                "presentationId": presentation_id,
                "slides": unlinked_relink_items,
            },
            user_ldap=user_ldap,
            user_oauth_token=token,
        )
        relinked_list = (
            relink_resp.get("relinked", [])
            if isinstance(relink_resp, dict)
            else []
        )
        if relinked_list:
          old_to_new_id = {
              str(r_it.get("oldSlideId")): str(r_it.get("newSlideId"))
              for r_it in relinked_list
              if isinstance(r_it, dict)
              and r_it.get("oldSlideId")
              and r_it.get("newSlideId")
          }
          r_refetch = requests.get(
              f"https://slides.googleapis.com/v1/presentations/{presentation_id}",
              headers=headers,
              timeout=30,
          )
          if r_refetch.status_code == 200:
            refetched_pres = r_refetch.json()
            refetched_slides = refetched_pres.get("slides", [])
            slide_by_id = {
                s.get("objectId"): s
                for s in refetched_slides
                if s.get("objectId")
            }
            slides = refetched_slides
            for sk_chk in sec_buckets:
              new_r_pairs = []
              for sl_obj_chk, sug_chk in sec_buckets[sk_chk].get("reusable", []):
                old_sid = sl_obj_chk.get("objectId", "")
                new_sid = old_to_new_id.get(old_sid, old_sid)
                new_r_pairs.append((slide_by_id.get(new_sid, sl_obj_chk), sug_chk))
              sec_buckets[sk_chk]["reusable"] = new_r_pairs
            print(
                f"[PitchGenSkills] Relinked {len(old_to_new_id)} reusable slides"
                " with SlideLinkingMode.LINKED!",
                flush=True,
            )
      except Exception as relink_err:
        print(
            f"[PitchGenSkills] Warning: Auto-relink reusable slides skipped: {relink_err}",
            flush=True,
        )

    all_sec_order = ordered_sec_keys + [
        k
        for k in sorted(extra_sec_keys, key=_sec_sort_key)
        if k not in ordered_sec_keys
    ]
    reordered_slides = list(prefix_slides)
    reordered_reusable_sugs = []
    for sk in all_sec_order:
      bucket = sec_buckets.get(sk) or {}
      div_list = bucket.get("dividers") or []
      b_list = bucket.get("bespoke") or []
      r_pairs = bucket.get("reusable") or []
      r_slide_objs = [rp[0] for rp in r_pairs]
      for sl_s in div_list + b_list + r_slide_objs:
        if isinstance(sl_s, dict) and sl_s.get("objectId"):
          slide_id_to_agenda_sec[str(sl_s.get("objectId"))] = str(sk)
      for rp in r_pairs:
        if rp[1] is not None:
          reordered_reusable_sugs.append(rp[1])
      # CVI Intra-Section Order:
      # 1. Divider (if any)
      # 2. Bespoke Slide 1 (b_list[:1]) — Customer-specific CVI thesis opener for the section
      # 3. Reusable Slides (r_slide_objs) — CVI-sorted L100 -> L200 product/architecture/proof slides
      # 4. Bespoke Slide 2+ (b_list[1:]) — Business Implication / synthesis bridge to next CVI stage
      reordered_slides.extend(div_list + b_list[:1] + r_slide_objs + b_list[1:])
    reordered_slides.extend(suffix_slides)

    orig_ids = [s.get("objectId") for s in slides if s.get("objectId")]
    new_ids = [s.get("objectId") for s in reordered_slides if s.get("objectId")]
    if (
        len(reordered_slides) == len(slides)
        and len(new_ids) == len(orig_ids)
        and new_ids != orig_ids
    ):
      reorder_reqs = [
          {
              "updateSlidesPosition": {
                  "slideObjectIds": [sid],
                  "insertionIndex": 0,
              }
          }
          for sid in reversed(new_ids)
      ]
      try:
        r_reord = requests.post(
            f"https://slides.googleapis.com/v1/presentations/{presentation_id}:batchUpdate",
            headers=headers,
            json={"requests": reorder_reqs},
            timeout=45,
        )
        if r_reord.status_code == 200:
          print(
              f"[PitchGenSkills] Reordered {len(new_ids)} slides into CVI"
              " Framework sequence BEFORE holistic text transformation on"
              f" {presentation_id}!",
              flush=True,
          )
          slides = reordered_slides
          if len(reordered_reusable_sugs) == len(ordered_reusable_sugs):
            ordered_reusable_sugs = reordered_reusable_sugs
        else:
          print(
              "[PitchGenSkills] Warning: CVI slide reorder batchUpdate"
              f" returned {r_reord.status_code}: {r_reord.text[:250]}",
              flush=True,
          )
      except Exception as reord_err:
        print(
            f"[PitchGenSkills] Warning: CVI slide reorder failed: {reord_err}",
            flush=True,
        )

  # Universal Content-Based CVI Narrative Progression Enforcer:
  # Runs on EVERY deck (including bespoke_custom, cloudhub, smart_hybrid, and in-place repairs)
  # to guarantee strict monotonic CVI ordering:
  # Cover -> Agenda -> Context/Current State -> Vision/Solution/Architecture -> Proof Points/Customer Reference -> Path to Prod/Next Steps -> Closing Thank You
  if len(slides) >= 4:

    def _universal_cvi_stage_rank(
        sl_item: dict,
        idx_s: int,
        total_n: int,
        notes_override: str = "",
        title_override: str = "",
    ) -> int:
      t_list = [
          t.strip()
          for t in _extract_raw_slide_texts(sl_item)
          if t and t.strip()
      ]
      c_low = " ".join(t_list).lower()
      sid_lookup = str(sl_item.get("objectId") or "")
      sug_meta = (
          suggestions_lookup.get(sid_lookup)
          if isinstance(locals().get("suggestions_lookup"), dict)
          else None
      )
      if not sug_meta and isinstance(
          locals().get("slide_notes_metadata"), dict
      ):
        n_meta_item = slide_notes_metadata.get(sid_lookup)
        if isinstance(n_meta_item, dict) and n_meta_item.get("new_notes"):
          notes_override = notes_override or str(n_meta_item["new_notes"])
      sug_desc_low = ""
      sug_job_low = ""
      if isinstance(sug_meta, dict):
        sug_desc_low = (
            f"{sug_meta.get('name', '')} {sug_meta.get('original_title', '')}"
            f" {sug_meta.get('original_content', '')}"
            f" {sug_meta.get('speaker_notes', '')}"
        ).lower()
        sug_job_low = str(sug_meta.get("slide_job") or "").strip().lower()
      n_low = (
          f"{notes_override or _extract_raw_slide_notes(sl_item)}"
          f" {sug_desc_low}"
      ).lower()
      first_line = t_list[0].lower() if t_list else ""
      best_t = title_override.lower().strip() if title_override else ""
      best_fs = 0.0
      if not best_t:
        for pe_t in _flatten_page_elements(sl_item.get("pageElements", [])):
          sh_t = pe_t.get("shape") or {}
          t_runs = (sh_t.get("text") or {}).get("textElements", [])
          raw_sh_t = "".join(
              (te.get("textRun") or {}).get("content", "") for te in t_runs
          ).strip()
          if not raw_sh_t:
            continue
          max_sh_fs = 0.0
          for te in t_runs:
            tr = te.get("textRun") or {}
            if tr.get("content", "").strip():
              fs_obj = (tr.get("style") or {}).get("fontSize") or {}
              mag = float(fs_obj.get("magnitude") or 0.0)
              if fs_obj.get("unit") == "EMU":
                mag /= 12700.0
              if mag > max_sh_fs:
                max_sh_fs = mag
          if max_sh_fs > best_fs:
            best_fs = max_sh_fs
            best_t = raw_sh_t.split("\n")[0].strip().lower()
      head_sig = f"{best_t} {first_line}".strip()
      full_sig = f"{c_low} {n_low}"
      src_line_low = ""
      for nl_line in n_low.splitlines():
        if "source slide:" in nl_line:
          src_line_low = nl_line
          break

      if any(
          kw in c_low
          for kw in (
              "internal context",
              "remove this slide",
              "user input",
              "opportunity id",
              "{{user_ldap}}",
              "{{er_number}}",
          )
      ):
        return 0

      if idx_s == 0 or (
          idx_s == 1
          and any(
              kw
              in _extract_raw_slide_notes(slides[0]).lower()
              + " ".join(_extract_raw_slide_texts(slides[0])).lower()
              for kw in (
                  "internal context",
                  "remove this slide",
                  "opportunity id",
              )
          )
      ):
        return 1

      if idx_s <= 2 and (
          "agenda" in head_sig
          or "table of contents" in head_sig
          or (
              "01" in c_low
              and "02" in c_low
              and "03" in c_low
              and not n_low.strip()
          )
      ):
        return 2

      if _is_thank_you_text(t_list) or (idx_s == total_n - 1 and not t_list):
        return 99

      # Stage 80: Explicit Path to Production / Next Steps / Commercials (CVI Stage: Realization -> 80)
      if (
          any(
              kw in head_sig
              for kw in (
                  "let's get started",
                  "lets get started",
                  "next steps",
                  "path to production",
                  "recommended next steps",
                  "implementation roadmap",
                  "joint execution plan",
                  "phased rollout",
                  "getting started",
                  "commercial framework",
                  "discovery workshop",
                  "discovery roadmap",
                  "joint discovery",
                  "joint agentic",
                  "joint value discovery",
                  "day charter",
                  "four-week",
                  "4-week",
                  "pilot charter",
                  "pilot roadmap",
                  "chartering a",
              )
          )
          or (
              "step 1" in c_low
              and "step 2" in c_low
              and "step 3" in c_low
              and any(
                  k in c_low
                  for k in (
                      "workshop",
                      "pilot",
                      "kickoff",
                      "cadence",
                      "poc",
                      "production",
                      "roadmap",
                      "mobilize",
                      "validate",
                  )
              )
          )
          or ("production launch" in c_low and "pilot" in c_low)
          or ("phase 1" in c_low and "phase 2" in c_low)
          or (
              "foundation" in c_low
              and "pilot" in c_low
              and "production" in c_low
              and "🔗 source slide:" not in n_low
          )
          or sug_job_low in ("path_to_prod", "commercials")
      ):
        return 80

      # Stage 68: Explicit Customer Proof Points / Customer References (CVI Stage: Proof_Points -> 68)
      is_cr_slide = (
          "source slide:" in n_low
          or "docs.google.com/presentation/d/" in n_low
          or bool(sug_meta and sug_meta.get("is_proof_point"))
      ) and (
          any(
              mk in full_sig
              for mk in (
                  "customer reference",
                  "proof_points",
                  "case study",
                  "https://your-sales-portal.example.com/customer-references",
                  "https://your-sales-portal.example.com/customer-references",
                  "exec summary:",
                  "customer story",
                  "applicable product(s):",
              )
          )
          or sug_job_low == "proof_points"
      )
      if is_cr_slide:
        return 68

      # Stage 10: Macro Market Trends & Cited Industry Research Shifts (CVI Stage: Market_Trends -> 10)
      has_research_citation = bool(
          "sources:" in c_low
          or "source:" in c_low
          or re.search(
              r"\([1-4]\)\s*(emarketer|nielsen|pwc|gartner|forrester|idc|mckinsey|ampere|harvard|statista|deloitte)",
              c_low,
          )
      )
      if (
          has_research_citation
          or any(
              kw in head_sig
              for kw in (
                  "beginning of a fundamental shift",
                  "rapidly changing the",
                  "changing the retail landscape",
                  "changing the industry landscape",
                  "market trends",
                  "industry trends",
                  "macro shift",
                  "industry landscape",
              )
          )
          or any(
              kw in src_line_low
              for kw in (
                  "quantifying the surge",
                  "adoption and impact of generative ai",
                  "economic impact of ai in retail",
                  "market trend",
              )
          )
          or sug_job_low == "market_trends"
      ):
        return 10

      # Stage 15: Current State / Data Foundation Imperative / Industry Focus Areas (CVI Stage: Context -> 15)
      if (
          any(
              kw in head_sig
              for kw in (
                  "current state",
                  "today's reality",
                  "industry challenges",
                  "key challenges",
                  "navigating ",
                  "overcoming legacy ",
                  "eliminating legacy ",
                  "breaking down ",
                  "the cost of inaction",
                  "strategic initiative",
                  "strategic footprint",
                  "technology footprint",
                  "tech footprint",
                  "customer research",
                  "digital retail initiatives",
                  "aligning with ",
                  "our vision for",
                  "partnership vision",
                  "vision for ",
                  "operational bottleneck",
                  "operational friction",
                  "resolving operational",
                  "evolving ",
                  "targeting high-roi",
                  "bottleneck",
                  "re-evaluating data foundations",
                  "modernizing data foundations",
                  "evaluating data foundations",
                  "focus areas for ",
                  "imperative for ",
                  "why retailers must ",
                  "why enterprises must ",
              )
          )
          or any(
              mk in full_sig
              for mk in (
                  "[cvi: context]",
                  "cvi_cluster: context",
                  "slide_job: current_state",
                  "slide_job: market_trends",
                  (
                      "necessity for retailers to re-evaluate their data"
                      " foundations"
                  ),
                  "necessity for enterprises to re-evaluate",
                  "re-evaluate their data foundations",
                  "outlines focus areas for retail leaders",
                  "outlines focus areas for ",
                  "drive sustainable and efficient operations",
                  "challenge of application sprawl",
                  "problem of context fragmentation",
                  "data silos and disconnected",
              )
          )
          or sug_job_low == "current_state"
      ):
        return 15

      # Stage 24: Future State Vision / Paradigm Shift (Reactive -> Proactive / Traditional -> Agentic) (CVI Stage: Vision -> 24)
      if any(
          kw in full_sig
          for kw in (
              "moving from reactive to proactive",
              "from reactive to proactive",
              "reactive and isolated",
              "proactive and unified",
              "transformative shift",
              "paradigm shift",
              "evolution of workplace",
              "traditional search",
              "from keywords to conversations",
              "art of the possible",
          )
      ):
        return 24

      # Stage 30: Why Google Cloud / Unified Platform Positioning (CVI Stage: Why_Google_Cloud / Vision -> 30)
      if (
          any(
              kw in head_sig
              for kw in (
                  "why google cloud",
                  "uniquely positioned",
                  "google cloud delivers",
                  "only provider",
                  "one google",
                  "strategic partnership",
                  "introducing gemini enterprise",
                  "overview of gemini enterprise",
              )
          )
          or any(
              kw in src_line_low
              for kw in (
                  "overview of gemini enterprise",
                  "front door",
                  "central nervous system",
                  "key differentiators of",
              )
          )
          or sug_job_low
          in ("why_google_cloud", "strategic_partnership", "vision")
      ):
        return 30

      # Stage 56: Architecture Stack / Security / Governance / Sovereign Cloud (CVI Stage: Architecture -> 56)
      norm_sig = re.sub(r"\s+", " ", full_sig)
      if (
          any(
              kw in norm_sig
              for kw in (
                  "agentic data cloud",
                  "agentic stack for action",
                  "your agentic stack",
                  "agent architecture stack",
                  "architectural overview",
                  "architecture diagram",
                  "security architecture",
                  "defense in depth",
                  "layered architecture",
                  "layered defense",
                  "ai hypercomputer",
                  "borderless lakehouse",
                  "knowledge catalog",
                  "model armor",
                  "sovereign cloud",
                  "proactive defense",
                  "two enterprise security features",
                  "enterprise grade compliance",
                  "trusted, resilient platform",
              )
          )
          or sum(
              1
              for m in (
                  "agents & applications",
                  "ai platform",
                  "model garden",
                  "agent engine",
                  "alloydb",
                  "spanner",
                  "analytical systems",
                  "operational systems",
              )
              if m in norm_sig
          )
          >= 2
          or sug_job_low == "architecture"
      ):
        return 56

      # Stage 62: Business Value / Quantified ROI / Economic Impact (CVI Stage: Business_Value -> 62)
      if (
          any(
              kw in head_sig
              for kw in (
                  "business value",
                  "economic impact",
                  "quantified impact",
                  "measurable roi",
                  "total cost of ownership",
                  "value realization",
              )
          )
          or sug_job_low == "business_value"
      ):
        return 62

      # Stage 38: High-level Solution Overview / Platform Capabilities (CVI Stage: Solution_Overview -> 38)
      if any(
          kw in src_line_low
          for kw in (
              "boost productivity in the flow of work",
              "teams and ai agents collaborating",
              "shared context between",
              "core capabilities",
              "platform capabilities",
              "empowers employees",
          )
      ):
        return 38

      # Default Stage 46: Solution Deep-Dive & Functional Use-Case Workflows (CVI Stage: Solution -> 46)
      return 46

    def _agenda_aware_cvi_sort_key(pair):
      orig_i, sl_obj = pair
      cvi_r = _universal_cvi_stage_rank(sl_obj, orig_i, len(slides))
      if cvi_r <= 2 or cvi_r >= 80:
        return (cvi_r, 0.0, cvi_r, orig_i)
      sid = str(sl_obj.get("objectId") or "")
      sec_k = slide_id_to_agenda_sec.get(sid)
      if sec_k is not None and str(sec_k).strip():
        try:
          sec_num = float(sec_k)
        except Exception:
          sec_num = 50.0
        if cvi_r == 65 and sec_num <= 1.5 and len(agendas_lookup_dict) >= 3:
          sec_num = max(sec_num, float(len(agendas_lookup_dict) - 1))
        return (10, sec_num, cvi_r, orig_i)
      return (10, 50.0, cvi_r, orig_i)

    indexed_slides = list(enumerate(slides))
    sorted_indexed = sorted(
        indexed_slides,
        key=_agenda_aware_cvi_sort_key,
    )
    univ_reordered = [pair[1] for pair in sorted_indexed]
    orig_u_ids = [s.get("objectId") for s in slides if s.get("objectId")]
    new_u_ids = [s.get("objectId") for s in univ_reordered if s.get("objectId")]
    if len(new_u_ids) == len(orig_u_ids) and new_u_ids != orig_u_ids:
      u_reorder_reqs = [
          {
              "updateSlidesPosition": {
                  "slideObjectIds": [sid],
                  "insertionIndex": 0,
              }
          }
          for sid in reversed(new_u_ids)
      ]
      try:
        r_ureord = requests.post(
            f"https://slides.googleapis.com/v1/presentations/{presentation_id}:batchUpdate",
            headers=headers,
            json={"requests": u_reorder_reqs},
            timeout=45,
        )
        if r_ureord.status_code == 200:
          print(
              "[PitchGenSkills] Universal CVI Sorter reordered"
              f" {len(new_u_ids)} slides into monotonic CVI sequence on"
              f" {presentation_id}!",
              flush=True,
          )
          slides = univ_reordered
      except Exception as u_err:
        print(
            f"[PitchGenSkills] Warning: Universal CVI sort notice: {u_err}",
            flush=True,
        )

  from pitchgen_utils.image_util import _element_bbox_pt

  # Inspect slides in presentation and build transform payload + speaker notes metadata
  requests_batch = []
  transform_slides = []
  sec_slide_counters: dict[str, int] = {}
  slide_shape_metadata = (
      {}
  )  # shapeId -> {"old_text": str, "paragraphs": list, ...}
  slide_notes_metadata = (
      {}
  )  # slideId -> {"notes_shape_id": str, "old_notes": str, "source_url": str, "link_header": str}
  reusable_cursor = 0
  used_reusable_sug_indices: set[int] = set()

  def _flatten_page_elements(elems: list) -> list:
    out = []
    for el in elems or []:
      if not isinstance(el, dict):
        continue
      grp = el.get("elementGroup")
      if isinstance(grp, dict) and grp.get("children"):
        out.extend(_flatten_page_elements(grp.get("children", [])))
      else:
        out.append(el)
    return out

  for s_idx, slide in enumerate(slides):
    slide_id = slide.get("objectId", "")
    if not slide_id:
      continue

    flat_page_elements = _flatten_page_elements(slide.get("pageElements", []))

    # Pre-collect bounding boxes of all substantive pageElements on this slide to compute vertical clearance_pt
    # and identify unfilled background card rectangles (ROUND_RECTANGLE / RECTANGLE) that enclose shorter text boxes.
    slide_elem_bboxes = []
    slide_card_bg_bboxes = []
    for pe_b in flat_page_elements:
      pe_id = pe_b.get("objectId", "")
      bx, by, bw, bh, _ = _element_bbox_pt(pe_b)
      if bw <= 0 or bh <= 0:
        continue
      if by >= 402.0 or bx >= 718.0 or (by + bh) <= 2.0 or (bx + bw) <= 2.0:
        continue
      sh_b = pe_b.get("shape") or {}
      sh_b_type = str(sh_b.get("shapeType") or "").upper()
      sh_b_has_text = any(
          bool((te_b.get("textRun") or {}).get("content", "").strip())
          for te_b in (sh_b.get("text") or {}).get("textElements", [])
      )
      if (
          "RECTANGLE" in sh_b_type
          and not sh_b_has_text
          and 80.0 <= bw <= 660.0
          and 65.0 <= bh <= 340.0
      ):
        slide_card_bg_bboxes.append((pe_id, bx, by, bw, bh))
      # Ignore full-slide backgrounds, thin divider lines, and tiny decorative icons when calculating text clearance
      if (bw >= 650.0 and bh >= 360.0) or bw < 35.0 or bh <= 14.0:
        continue
      slide_elem_bboxes.append((pe_id, bx, by, bw, bh))

    # Extract shape texts and styles
    shape_items = []
    all_slide_texts = []
    for pe in flat_page_elements:
      sh = pe.get("shape")
      if not sh:
        continue
      sh_id = pe.get("objectId", "")
      text_elems = sh.get("text", {}).get("textElements", [])
      if not text_elems:
        continue

      x_pt, y_pt, w_pt, h_pt, _ = _element_bbox_pt(pe)
      # Skip off-canvas scratch shapes (e.g. y >= 402pt below the 405pt slide canvas or x >= 718pt right of 720pt canvas)
      if (w_pt > 0 or h_pt > 0) and (
          y_pt >= 402.0
          or x_pt >= 718.0
          or (y_pt + h_pt) <= 2.0
          or (x_pt + w_pt) <= 2.0
      ):
        continue
      placeholder_type = str(
          sh.get("placeholder", {}).get("type") or ""
      ).upper()

      full_raw = ""
      first_font_size = 12.0
      min_body_font_size = None
      first_bold = False
      found_first_run = False
      paragraphs_meta = []
      cur_para_text = ""
      cur_para_style = None
      cur_para_runs = []
      cur_para_bullet = None
      cur_para_all_bold = True
      cur_para_has_non_ws = False

      def _finalize_para_meta(
          p_txt, p_style, p_runs, p_bullet, has_non_ws, all_bold
      ):
        base_style = dict(p_style or {})
        lead_style = None
        lead_word_count = 0
        if len(p_runs) >= 2:
          r0_txt, r0_st = p_runs[0]
          rest_txt = "".join(rt for rt, _ in p_runs[1:]).strip()
          r0_words = r0_txt.strip().split()
          r_last_st = p_runs[-1][1]
          if (
              1 <= len(r0_words) <= 5
              and len(rest_txt) > len(r0_txt.strip())
              and (
                  bool(r0_st.get("bold")) != bool(r_last_st.get("bold"))
                  or r0_st.get("foregroundColor")
                  != r_last_st.get("foregroundColor")
                  or r0_st.get("weightedFontFamily")
                  != r_last_st.get("weightedFontFamily")
              )
          ):
            lead_style = dict(r0_st)
            lead_word_count = len(r0_words)
            base_style = dict(r_last_st)
        return {
            "text": p_txt,
            "style": base_style,
            "lead_style": lead_style,
            "lead_word_count": lead_word_count,
            "has_bullet": bool(p_bullet),
            "bullet_glyph": (
                (p_bullet or {}).get("glyph", "")
                if isinstance(p_bullet, dict)
                else ""
            ),
            "is_bold_header": bool(
                has_non_ws
                and all_bold
                and (p_style or {}).get("bold")
                and len(p_txt.strip()) <= 45
                and not p_bullet
            ),
        }

      for te in text_elems:
        pm = te.get("paragraphMarker")
        if pm is not None:
          cur_para_bullet = pm.get("bullet")
        tr = te.get("textRun")
        if not tr:
          continue
        content = tr.get("content", "")
        style = tr.get("style", {})
        full_raw += content

        is_pure_section_num_run = bool(
            re.match(r"^\s*(?:0[1-9]|[1-9]\d?)[\.\:\-\s\x0b]*$", content)
        )
        run_style_snap = {
            "fontSize": style.get("fontSize"),
            "bold": style.get("bold"),
            "italic": style.get("italic"),
            "underline": style.get("underline"),
            "fontFamily": style.get("fontFamily"),
            "weightedFontFamily": style.get("weightedFontFamily"),
            "foregroundColor": style.get("foregroundColor"),
        }
        if content.strip() and not is_pure_section_num_run:
          cur_para_has_non_ws = True
          cur_para_runs.append((content, run_style_snap))
          if not bool(style.get("bold", False)):
            cur_para_all_bold = False
          fs_mag = style.get("fontSize", {}).get("magnitude")
          if not found_first_run:
            found_first_run = True
            if fs_mag:
              first_font_size = float(fs_mag)
            wff_weight = int(
                ((style.get("weightedFontFamily") or {}).get("weight") or 400)
            )
            first_bold = bool(style.get("bold", False) or wff_weight >= 500)
          elif fs_mag and len(content.strip()) >= 8:
            cand_b_fs = float(fs_mag)
            if min_body_font_size is None or cand_b_fs < min_body_font_size:
              min_body_font_size = cand_b_fs

        if (cur_para_style is None or cur_para_style.get("_from_sec_num")) and content.strip():
          cur_para_style = dict(run_style_snap)
          cur_para_style["_from_sec_num"] = is_pure_section_num_run
        cur_para_text += content
        if "\n" in content:
          if cur_para_style:
            cur_para_style.pop("_from_sec_num", None)
          p_txt = cur_para_text.rstrip("\n")
          if p_txt.strip():
            paragraphs_meta.append(
                _finalize_para_meta(
                    p_txt,
                    cur_para_style,
                    cur_para_runs,
                    cur_para_bullet,
                    cur_para_has_non_ws,
                    cur_para_all_bold,
                )
            )
          cur_para_text = ""
          cur_para_style = None
          cur_para_runs = []
          cur_para_bullet = None
          cur_para_all_bold = True
          cur_para_has_non_ws = False

      if cur_para_text.strip():
        if cur_para_style:
          cur_para_style.pop("_from_sec_num", None)
        p_txt = cur_para_text.rstrip("\n")
        paragraphs_meta.append(
            _finalize_para_meta(
                p_txt,
                cur_para_style,
                cur_para_runs,
                cur_para_bullet,
                cur_para_has_non_ws,
                cur_para_all_bold,
            )
        )

      clean_t = re.sub(r"\n\s*\n+", "\n", full_raw.strip())
      if not clean_t:
        continue

      # Auto-delete legacy standalone "app" or "GE" micro-badge shapes next to Gemini Enterprise logo lockup (Enterprise-Brand-Unification)
      if (
          clean_t.strip().lower() in ("app", "ge")
          and w_pt <= 115.0
          and h_pt <= 45.0
      ):
        print(
            "[PitchGenSkills] Removing legacy lockup badge shape"
            f" {sh_id} ('{clean_t.strip()}') on slide {slide_id}"
        )
        requests_batch.append({"deleteObject": {"objectId": sh_id}})
        continue

      shape_has_bullets = any(p.get("has_bullet") for p in paragraphs_meta)
      # Inherited layout font size fallback for top TITLE / CENTERED_TITLE placeholders
      if (
          placeholder_type in ("TITLE", "CENTERED_TITLE")
          and y_pt < 75.0
          and not shape_has_bullets
          and first_font_size <= 14.0
      ):
        first_font_size = 28.0
        if paragraphs_meta and not paragraphs_meta[0]["style"].get("fontSize"):
          paragraphs_meta[0]["style"]["fontSize"] = {
              "magnitude": 28,
              "unit": "PT",
          }

      # Compute vertical clearance_pt to the nearest overlapping element below this shape
      clearance_pt = None
      if w_pt > 0 and h_pt > 0:
        min_dy = None
        for other_id, ox, oy, ow, oh in slide_elem_bboxes:
          if other_id == sh_id:
            continue
          if oy <= y_pt + 12.0:
            continue
          horiz_overlap = min(x_pt + w_pt, ox + ow) - max(x_pt, ox)
          if horiz_overlap >= 0.25 * min(w_pt, ow):
            dy = oy - y_pt
            if min_dy is None or dy < min_dy:
              min_dy = dy
        clearance_pt = min_dy

        # If this text box sits inside a taller unfilled card background rectangle
        # or an open multi-column layout column, expand h_pt to the effective vertical card height
        # (matching DeckPerfectionInspector._resolve_effective_box_height_pt).
        orig_h_pt = h_pt
        cx_mid = x_pt + w_pt / 2.0
        for _, cx, cy, cw, ch in slide_card_bg_bboxes:
          if (
              cx - 15.0 <= cx_mid <= cx + cw + 15.0
              and cy - 15.0 <= y_pt <= cy + ch
          ):
            card_avail_h = (cy + ch) - y_pt - 8.0
            if card_avail_h > h_pt:
              h_pt = round(card_avail_h, 1)
        if h_pt <= orig_h_pt + 5.0 and 55.0 <= y_pt <= 315.0 and w_pt >= 95.0:
          min_next_text_y = 352.0
          for pe_o in flat_page_elements:
            sh_o = pe_o.get("shape")
            if not sh_o:
              continue
            o_txt = "".join(
                (te_o.get("textRun") or {}).get("content", "")
                for te_o in (sh_o.get("text") or {}).get("textElements", [])
            ).strip()
            if (
                not o_txt
                or "proprietary & confidential" in o_txt.lower()
                or o_txt.isdigit()
            ):
              continue
            ox, oy, ow, _ = _element_bbox_pt(pe_o)[:4]
            if abs(ox - x_pt) <= 5.0 and abs(oy - y_pt) <= 5.0:
              continue
            horiz_ov = min(x_pt + w_pt, ox + ow) - max(x_pt, ox)
            if horiz_ov >= 0.3 * min(w_pt, ow) and oy > y_pt + 18.0:
              if oy < min_next_text_y:
                min_next_text_y = oy
          open_col_h = min(195.0, min_next_text_y - y_pt - 8.0)
          if open_col_h > h_pt:
            h_pt = round(open_col_h, 1)

      all_slide_texts.append(clean_t)

      # For multi-line card shapes (e.g. 28pt "Step 1" + 10pt body, or 14pt header + 10pt body),
      # use min_body_font_size for algebraic character budgeting so body text is never mis-budgeted as 28pt/14pt
      effective_budget_fs = (
          min_body_font_size
          if (
              "\n" in clean_t
              and min_body_font_size is not None
              and min_body_font_size < first_font_size
          )
          else first_font_size
      )

      if (
          clean_t != "Google Cloud"
          and "Proprietary & Confidential" not in clean_t
          and not re.match(r"^\d+$", clean_t)
      ):
        # Ensure tall bespoke multi-column cards (h_pt >= 165pt, 100 <= w_pt <= 330pt, body fontSize <= 14.5pt) meet the >=105 char minimum density floor
        if (
            "🔗 Source Slide:" not in _extract_raw_slide_notes(slide)
            and h_pt >= 165.0
            and 100.0 <= w_pt <= 330.0
            and (first_font_size is None or float(first_font_size) <= 14.5)
            and "\n" not in clean_t
            and 35 <= len(clean_t) < 106
            and not clean_t.endswith(":")
        ):
          cust_label = c_name or "the enterprise"
          suffix_clause = f" across {cust_label}'s production workflows."
          if cust_label.lower() in clean_t.lower():
            suffix_clause = " with governed, production-grade reliability."
          expanded_t = clean_t.rstrip(".") + suffix_clause
          if len(expanded_t) < 108:
            expanded_t = expanded_t.rstrip(".") + " at enterprise scale."
          if len(expanded_t) < 108:
            expanded_t = expanded_t.rstrip(".") + " with unified observability."
          requests_batch.append(
              {
                  "deleteText": {
                      "objectId": sh_id,
                      "textRange": {"type": "ALL"},
                  }
              }
          )
          requests_batch.append({
              "insertText": {
                  "objectId": sh_id,
                  "insertionIndex": 0,
                  "text": expanded_t,
              }
          })
          clean_t = expanded_t
        raw_sz_w = (pe.get("size") or {}).get("width") or {}
        raw_xf = pe.get("transform") or {}
        slide_shape_metadata[sh_id] = {
            "old_text": clean_t,
            "paragraphs": paragraphs_meta,
            "x_pt": x_pt,
            "y_pt": y_pt,
            "width_pt": w_pt,
            "height_pt": h_pt,
            "clearance_pt": clearance_pt,
            "has_bullets": shape_has_bullets,
            "placeholder_type": placeholder_type,
            "header_font_size": first_font_size,
        }
        shape_items.append({
            "shapeId": sh_id,
            "text": clean_t,
            "charCount": len(clean_t),
            "bold": first_bold,
            "fontSize": effective_budget_fs,
            "headerFontSize": first_font_size,
            "x_pt": x_pt,
            "y_pt": y_pt,
            "width_pt": w_pt,
            "height_pt": h_pt,
            "clearance_pt": clearance_pt,
            "has_bullets": shape_has_bullets,
            "placeholder_type": placeholder_type,
            "raw_size_w": raw_sz_w,
            "raw_transform": raw_xf,
        })

    # Extract speaker notes shape & existing notes text
    notes_page = slide.get("slideProperties", {}).get("notesPage", {})
    notes_shape_id = notes_page.get("notesProperties", {}).get(
        "speakerNotesObjectId", ""
    )
    orig_notes_raw = ""
    if notes_shape_id:
      for pe in notes_page.get("pageElements", []):
        if pe.get("objectId") == notes_shape_id:
          for te in pe.get("shape", {}).get("text", {}).get("textElements", []):
            tr = te.get("textRun")
            if tr:
              orig_notes_raw += tr.get("content", "")
    orig_notes = orig_notes_raw.strip()

    combined_lower = " ".join(all_slide_texts).lower()

    # Populate any remaining {{...}} placeholders on any Internal Context / User Input Summary slide before skipping it
    if any(
        kw in combined_lower
        for kw in (
            "internal context",
            "remove this slide",
            "user input",
            "opportunity id",
            "{{user_ldap}}",
            "{{er_number}}",
        )
    ):
      ctx_s0 = (
          (outputs_data or {}).get("context")
          if isinstance((outputs_data or {}).get("context"), dict)
          else {}
      )
      def _fmt_ctx_val(val, default_str="N/A"):
        if isinstance(val, list):
          cleaned = [str(x).strip() for x in val if str(x).strip()]
          return ", ".join(cleaned) if cleaned else default_str
        s_val = str(val or "").strip()
        return s_val if s_val else default_str

      s0_replacements = {
          "{{user_ldap}}": _fmt_ctx_val(ctx_s0.get("user_ldap") or (outputs_data or {}).get("user_ldap"), "seller_user"),
          "{{er_number}}": _fmt_ctx_val(ctx_s0.get("er_number") or (outputs_data or {}).get("er_number"), "N/A"),
          "{{customer_name}}": _fmt_ctx_val(ctx_s0.get("customer_name") or (outputs_data or {}).get("customer_name"), "Customer"),
          "{{audience}}": _fmt_ctx_val(ctx_s0.get("audience") or ctx_s0.get("target_audience"), "Executive & Technical Leadership"),
          "{{industry}}": _fmt_ctx_val(ctx_s0.get("industry") or ctx_s0.get("closest_industry"), "Enterprise"),
          "{{salesPlay}}": _fmt_ctx_val(ctx_s0.get("salesPlay") or ctx_s0.get("sales_plays") or ctx_s0.get("sales_play"), "Google Cloud AI"),
          "{{business_context}}": _fmt_ctx_val(ctx_s0.get("business_context") or ctx_s0.get("user_prompt") or ctx_s0.get("prompt"), "Strategic Google Cloud AI Proposal"),
      }
      for ph_key, ph_val in s0_replacements.items():
        if ph_key.lower() in combined_lower:
          requests_batch.append({
              "replaceAllText": {
                  "pageObjectIds": [slide_id],
                  "containsText": {"text": ph_key, "matchCase": False},
                  "replaceText": ph_val,
              }
          })
      continue

    # Identify Agenda slide and Cover (Title) slide deterministically whether Slide 0 is a Context slide or the Cover slide
    is_agenda_slide = s_idx <= 2 and (
        "agenda" in combined_lower
        or "table of contents" in combined_lower
        or (
            s_idx == 2
            and any(re.match(r"^0[1-6]$", t.strip()) for t in all_slide_texts)
        )
    )
    is_title_slide = (
        s_idx <= 1
        and not is_agenda_slide
        and "🔗 Source Slide:" not in orig_notes
        and (
            s_idx == 0
            or s_idx == 1
            or "proposal" in combined_lower
            or "pitch" in combined_lower
            or "prepared for" in combined_lower
            or (
                outputs_data
                and str(outputs_data.get("deck_theme") or "").lower()
                in combined_lower
            )
        )
    )
    # Always keep Cover Slide primary title font size at 68pt and normalize rigid colon/Google Cloud cover titles so they wrap cleanly in 2-3 lines inside the 380pt left column
    if is_title_slide and shape_items:
      from agents.workflows.outline_workflow import OutlineWorkflow

      max_cov_fs = max(
          float(s.get("headerFontSize") or s.get("fontSize") or 12.0)
          for s in shape_items
      )
      for cov_sh in shape_items:
        cov_fs = float(
            cov_sh.get("headerFontSize") or cov_sh.get("fontSize") or 12.0
        )
        cov_w = float(cov_sh.get("width_pt") or 0.0)
        cov_txt = str(cov_sh.get("text") or "").strip()
        is_primary_cov_title = (
            cov_fs >= 28.0
            or cov_sh.get("placeholder_type") in ("TITLE", "CENTERED_TITLE")
            or (
                cov_fs >= max_cov_fs
                and len(cov_txt) >= 8
                and float(cov_sh.get("y_pt") or 0.0) <= 220.0
            )
        )
        if is_primary_cov_title and len(cov_txt) >= 6:
          norm_cov_txt = OutlineWorkflow.normalize_modern_cover_title(
              cov_txt,
              customer_name=c_name,
              customer_research=str(
                  (outputs_data or {}).get("customer_research") or ""
              ),
              sales_plays=(outputs_data or {}).get("required_sales_plays")
              or (outputs_data or {}).get("sales_plays"),
              industry=ind_name,
          )
          if norm_cov_txt and norm_cov_txt != cov_txt:
            cov_sh["text"] = norm_cov_txt
            cov_txt = norm_cov_txt
            requests_batch.append({
                "deleteText": {
                    "objectId": cov_sh["shapeId"],
                    "textRange": {"type": "ALL"},
                }
            })
            requests_batch.append({
                "insertText": {
                    "objectId": cov_sh["shapeId"],
                    "insertionIndex": 0,
                    "text": norm_cov_txt,
                }
            })
          target_cov_fs = 68.0
          cov_sh["fontSize"] = target_cov_fs
          cov_sh["headerFontSize"] = target_cov_fs
          requests_batch.append({
              "updateTextStyle": {
                  "objectId": cov_sh["shapeId"],
                  "textRange": {"type": "ALL"},
                  "style": {
                      "fontSize": {"magnitude": target_cov_fs, "unit": "PT"},
                      "fontFamily": "Google Sans",
                      "foregroundColor": {
                          "opaqueColor": {
                              "rgbColor": {
                                  "red": 1.0,
                                  "green": 1.0,
                                  "blue": 1.0,
                              }
                          }
                      },
                  },
                  "fields": "fontSize,fontFamily,foregroundColor",
              }
          })
          # If a wide Cover Slide title box (e.g. 482pt wide) extends past x=400pt into the right-side hero image, narrow it to 380pt
          if cov_w > 395.0:
            raw_sz_w = cov_sh.get("raw_size_w") or {}
            raw_xf = cov_sh.get("raw_transform") or {}
            w_mag = float(raw_sz_w.get("magnitude") or 0.0)
            w_unit = str(raw_sz_w.get("unit") or "EMU")
            base_w_pt = (w_mag / 12700.0) if w_unit == "EMU" else w_mag
            if base_w_pt > 10.0 and raw_xf:
              new_scale_x = round(380.0 / base_w_pt, 4)
              requests_batch.append({
                  "updatePageElementTransform": {
                      "objectId": cov_sh["shapeId"],
                      "applyMode": "ABSOLUTE",
                      "transform": {
                          "scaleX": new_scale_x,
                          "scaleY": raw_xf.get("scaleY", 1.0),
                          "shearX": raw_xf.get("shearX", 0.0),
                          "shearY": raw_xf.get("shearY", 0.0),
                          "translateX": raw_xf.get("translateX", 0.0),
                          "translateY": raw_xf.get("translateY", 0.0),
                          "unit": raw_xf.get("unit", "EMU"),
                      },
                  }
              })
    # Check if this slide has an existing reusable source note
    has_existing_source_note = "🔗 Source Slide:" in orig_notes or any(
        str(su.get("slide_url") or "") in orig_notes
        for su in ordered_reusable_sugs
        if su.get("slide_url")
    )
    is_divider = bool(
        len(all_slide_texts) <= 3
        and (
            re.match(r"^(0\d|\d{1,2})\s", combined_lower)
            or re.match(r"^(section\s*\d|divider)", combined_lower)
            or re.match(r"^(0[1-9]|10)\b", combined_lower)
        )
    )
    is_thank_you = (
        not has_existing_source_note and _is_thank_you_text(all_slide_texts)
    ) or (
        s_idx >= len(slides) - 2
        and (
            _is_thank_you_text(all_slide_texts)
            or "thank you" in combined_lower
            or "questions" in combined_lower
        )
    )
    # Delete completely empty trailing slide (e.g. blank Slide 24 left over from template)
    if (
        s_idx == len(slides) - 1
        and not all_slide_texts
        and len(slide.get("pageElements", [])) <= 2
    ):
      print(
          f"[PitchGenSkills] Removing empty trailing blank slide {slide_id} at"
          f" index {s_idx + 1}"
      )
      requests_batch.append({"deleteObject": {"objectId": slide_id}})
      continue
    if is_agenda_slide or is_divider or is_thank_you:
      continue

    matched_gen_ph = None
    if not has_existing_source_note:
      for gt in known_generated_titles:
        if gt and (gt in combined_lower or combined_lower.startswith(gt[:30])):
          matched_gen_ph = known_generated_title_to_ph.get(gt) or {}
          break
    is_generated_slide = matched_gen_ph is not None
    is_reusable = not is_generated_slide and not is_title_slide

    # Auto-repair any malformed single-brace placeholders (e.g. {{header1} on T44) left unreplaced by Apps Script
    if is_generated_slide and matched_gen_ph and "{{" in combined_lower:
      for ph_k, ph_v in matched_gen_ph.items():
        clean_k = str(ph_k).strip("{} ")
        val_str = str(ph_v or "").strip()
        if not clean_k or not val_str:
          continue
        for cand_tag in (f"{{{{{clean_k}}}}}", f"{{{{{clean_k}}}"):
          if cand_tag.lower() in combined_lower:
            requests_batch.append({
                "replaceAllText": {
                    "pageObjectIds": [slide_id],
                    "containsText": {"text": cand_tag, "matchCase": False},
                    "replaceText": val_str,
                }
            })

    # Auto-repair T25 duplicate {{header1_content}} template typo where column 2 received header1_content instead of header2_content
    if is_generated_slide and matched_gen_ph:
      h1_c = str(matched_gen_ph.get("header1_content") or "").strip()
      h2_c = str(matched_gen_ph.get("header2_content") or "").strip()
      if h1_c and h2_c and h1_c != h2_c:
        dup_shapes = sorted(
            [sh for sh in shape_items if sh.get("text", "").strip() == h1_c],
            key=lambda s: float(s.get("x_pt") or 0.0),
        )
        if len(dup_shapes) >= 2:
          dup_sh_id = dup_shapes[1]["shapeId"]
          requests_batch.append({
              "deleteText": {
                  "objectId": dup_sh_id,
                  "textRange": {"type": "ALL"},
              }
          })
          requests_batch.append({
              "insertText": {
                  "objectId": dup_sh_id,
                  "insertionIndex": 0,
                  "text": h2_c,
              }
          })
          dup_shapes[1]["text"] = h2_c
          if dup_sh_id in slide_shape_metadata:
            slide_shape_metadata[dup_sh_id]["old_text"] = h2_c

    matched_sug = None
    if is_reusable and ordered_reusable_sugs:
      matched_sug, reusable_cursor = _match_reusable_sug_item(
          combined_lower,
          orig_notes,
          ordered_reusable_sugs,
          used_reusable_sug_indices,
          reusable_cursor,
          slide_obj_id=slide_id,
      )

    # Build speaker notes with 🔗 Source Slide link header for reusable slides (matching copySlide.js:121-132)
    effective_notes = orig_notes
    source_url = ""
    link_header = ""
    if not is_title_slide and matched_sug and matched_sug.get("slide_url"):
      source_url = matched_sug["slide_url"]
      s_label = matched_sug.get("slide_label") or "Original Reusable Slide"
      d_str = matched_sug.get("date_str") or ""
      is_cr_sug = bool(
          matched_sug.get("is_proof_point")
          or matched_sug.get("is_cust_ref")
          or str(matched_sug.get("slide_job") or "").lower() == "proof_points"
      )
      cr_tag = (
          " [Customer Reference / Proof_Points]"
          if is_cr_sug and "customer reference" not in s_label.lower()
          else ""
      )
      link_header = f"🔗 Source Slide: {s_label}{cr_tag}{d_str}\n{source_url}"
      if "🔗 Source Slide:" not in effective_notes:
        if effective_notes and effective_notes != s_label:
          effective_notes = (
              f"{link_header}\n\n--- Original Speaker Notes"
              f" ---\n{effective_notes}"
          )
        else:
          effective_notes = link_header
    # Always ensure source_url matches the URL actually present inside effective_notes if 🔗 Source Slide is already written
    if (
        not is_title_slide
        and "🔗 Source Slide:" in effective_notes
        and (not source_url or source_url not in effective_notes)
    ):
      m_src_u = re.search(r"https://docs\.google\.com/presentation/d/[^\s\n]+", effective_notes)
      if m_src_u:
        source_url = m_src_u.group(0).strip()

    if not is_title_slide:
      slide_notes_metadata[slide_id] = {
          "notes_shape_id": notes_shape_id,
          "old_notes": orig_notes_raw.rstrip("\n"),
          "new_notes": effective_notes,
          "source_url": source_url,
          "link_header": link_header,
      }

    if not shape_items:
      continue

    # 1. Detect true standalone Title / Section Divider / Thank You cards brought in as reusable slides
    #    WITHOUT ever excluding valid visual/diagram/GIF/table slides that happen to have only a title + subtitle.
    non_footer_shapes = [
        sh for sh in shape_items
        if "proprietary & confidential" not in sh["text"].lower()
        and not sh["text"].strip().isdigit()
    ]
    total_non_footer_chars = sum(len(sh["text"].strip()) for sh in non_footer_shapes)
    non_footer_combined_lower = " ".join(
        sh["text"].strip().lower() for sh in non_footer_shapes
    ).strip(" .!?:;-")
    # Unconditionally remove any imported mid-deck "Thank you" or "Q&A" slide even if it has a decorative background image
    if is_reusable and _is_thank_you_text(
        [sh["text"] for sh in non_footer_shapes]
    ):
      print(
          "[PitchGenSkills] Removing imported mid-deck Thank You / Q&A slide"
          f" {slide_id} at index {s_idx + 1}"
          f" (texts={[sh['text'] for sh in non_footer_shapes]})"
      )
      requests_batch.append({"deleteObject": {"objectId": slide_id}})
      continue
    slide_layout_id = slide.get("slideProperties", {}).get("layoutObjectId", "")
    layout_meta = presentation_layouts.get(slide_layout_id, {}) if isinstance(locals().get("presentation_layouts"), dict) else {}
    layout_label = (
        f"{layout_meta.get('name', '')} {layout_meta.get('displayName', '')}".lower()
    )
    is_title_or_divider_layout = any(
        kw in layout_label
        for kw in ("title card", "section header", "section_header", "section divider", "chapter")
    )
    # Check if the slide has ANY substantive non-text visual content (tables, charts, videos, groups, or content/GIF images)
    has_substantive_visual_or_table = False
    for pe in slide.get("pageElements", []):
      if "table" in pe or "sheetsChart" in pe or "video" in pe or "elementGroup" in pe:
        has_substantive_visual_or_table = True
        break
      if "image" in pe:
        from pitchgen_utils.image_util import _element_bbox_pt, is_gif_or_animated_bytes
        img_url = str(pe["image"].get("contentUrl") or pe["image"].get("sourceUrl") or "")
        _, _, w_pt, h_pt, _ = _element_bbox_pt(pe)
        is_full_bg = (w_pt >= 650.0 and h_pt >= 360.0)
        is_small_badge = (w_pt < 140.0 and h_pt < 90.0)
        if is_gif_or_animated_bytes(url=img_url) or (not is_full_bg and not is_small_badge and w_pt >= 140.0 and h_pt >= 90.0):
          has_substantive_visual_or_table = True
          break

    has_only_large_display_text = all(
        (sh.get("font_size") or 24.0) >= 18.0 and not sh.get("has_bullets")
        for sh in non_footer_shapes
    )
    if (
        is_reusable
        and len(non_footer_shapes) <= 2
        and total_non_footer_chars < 120
        and not has_substantive_visual_or_table
        and (is_title_or_divider_layout or has_only_large_display_text)
    ):
      print(
          f"[PitchGenSkills] Removing standalone reusable Title/Divider card {slide_id} at index {s_idx + 1} "
          f"(layout='{layout_label.strip()}', texts={[sh['text'] for sh in non_footer_shapes]})"
      )
      requests_batch.append({"deleteObject": {"objectId": slide_id}})
      continue

    primary_title = shape_items[0]["text"].split("\n")[0].strip()
    is_proof_point = bool(
        (matched_sug and matched_sug.get("is_proof_point"))
        or "exec summary:" in orig_notes.lower()
        or "applicable product(s):" in combined_lower
    )

    # 2. Protect reusable slides that contain cited statistics/sources so research claims are never made inaccurate
    is_cited_stats_slide = bool(
        is_reusable
        and (
            "sources:" in combined_lower
            or "source:" in combined_lower
            or re.search(r"\([1-4]\)\s*(emarketer|nielsen|pwc|gartner|forrester|idc|mckinsey|ampere)", combined_lower)
        )
    )

    # 3. Protect reusable slides that cover Google Cloud architecture stacks and official product names
    # Normalize all newlines/tabs to single spaces so multi-line titles like "Google’s\nAgentic\nData Cloud" match reliably
    norm_arch_text = re.sub(
        r"\s+",
        " ",
        f"{combined_lower} {(orig_notes or '').lower()}"
        f" {(effective_notes or '').lower()}",
    )
    strong_arch_markers = (
        "agentic data cloud",
        "agentic stack for action",
        "your agentic stack",
        "agent architecture stack",
        "architectural overview",
        "architecture diagram",
        "layered architecture",
        "layered defense",
        "ai hypercomputer",
        "borderless lakehouse",
        "knowledge catalog",
        "gemini-infused",
    )
    arch_product_markers = (
        "agentic defense",
        "research & frontier multimodal models",
        "agents & applications",
        "agents & apps",
        "ai platform",
        "agentic-first",
        "ai-powered data",
        "analytical systems",
        "operational systems",
        "adk, agent engine",
        "agent engine",
        "model garden",
        "agent gateway",
        "alloydb",
        "spanner",
    )
    is_architecture_product_slide = bool(
        is_reusable
        and not is_title_slide
        and (
            any(m in norm_arch_text for m in strong_arch_markers)
            or sum(1 for m in arch_product_markers if m in norm_arch_text) >= 2
        )
    )

    from pitchgen_utils.image_util import extract_customizable_slide_pictures

    slide_pictures = extract_customizable_slide_pictures(
        slide,
        slide_index=s_idx,
        is_cust_ref_slide=bool(is_proof_point or is_architecture_product_slide),
    )

    if is_title_slide and not slide_pictures:
      continue

    resolved_sec_k = slide_id_to_agenda_sec.get(slide_id) or (
        str(matched_sug.get("section"))
        if isinstance(matched_sug, dict) and matched_sug.get("section")
        else ""
    )
    ag_meta = (
        agendas_lookup_dict.get(str(resolved_sec_k))
        if resolved_sec_k
        and isinstance(agendas_lookup_dict.get(str(resolved_sec_k)), dict)
        else {}
    )
    ag_sec_title = str((ag_meta or {}).get("title") or "").strip()
    ag_sec_parts = (
        list((ag_meta or {}).get("parts") or [])
        if isinstance((ag_meta or {}).get("parts"), list)
        else []
    )
    sec_key_str = str(resolved_sec_k or "")
    assigned_subtopic = ""
    if sec_key_str and ag_sec_parts:
      s_off = sec_slide_counters.get(sec_key_str, 0)
      assigned_subtopic = str(
          ag_sec_parts[min(s_off, len(ag_sec_parts) - 1)]
      ).strip()
      sec_slide_counters[sec_key_str] = s_off + 1

    slide_cvi_stage = 46
    try:
      if "_universal_cvi_stage_rank" in locals():
        slide_cvi_stage = _universal_cvi_stage_rank(
            slide,
            s_idx,
            len(slides),
            notes_override=effective_notes,
            title_override=primary_title,
        )
    except Exception:
      pass

    transform_slides.append({
        "slideId": slide_id,
        "slide_index": s_idx,
        "slide_position": len(transform_slides) + 1,
        "slide_title": primary_title or f"Slide {s_idx + 1}",
        "cvi_stage": slide_cvi_stage,
        "agenda_section_index": sec_key_str,
        "agenda_section_title": ag_sec_title,
        "assigned_agenda_subtopic": assigned_subtopic,
        "agenda_section_parts": ag_sec_parts,
        "is_reusable": is_reusable,
        "is_proof_point": is_proof_point,
        "is_cited_stats_slide": is_cited_stats_slide,
        "is_architecture_product_slide": is_architecture_product_slide,
        "is_title_slide": is_title_slide,
        "_skip_mutation": bool(
            is_proof_point or is_cited_stats_slide or is_title_slide
        ),
        "speaker_notes": effective_notes,
        "data": shape_items,
        "slide_pictures": slide_pictures,
    })

  # Resolve customer context & customer logo (Google-only endpoints -> gs://your-pitchgen-content-bucket/customer_logos/)
  if config is None:
    config = load_config()
  ctx = (
      (outputs_data or {}).get("context")
      if isinstance((outputs_data or {}).get("context"), dict)
      else {}
  )
  cust_name = (
      (outputs_data or {}).get("customer_name")
      or ctx.get("customer_name")
      or ""
  ).strip()
  ind_name = (ctx.get("industry") or "").strip()

  customer_logo_url = str((outputs_data or {}).get("customer_logo_url") or "").strip()
  if not customer_logo_url and cust_name and cust_name.lower() not in ("the target customer", "the customer", "-", "none"):
    try:
      from pitchgen_utils.logo_util import resolve_customer_logo
      customer_logo_url = resolve_customer_logo(
          cust_name,
          customer_info=str(ctx.get("customer_research") or ""),
          config=config,
      )
      if customer_logo_url and isinstance(outputs_data, dict):
        outputs_data["customer_logo_url"] = customer_logo_url
    except Exception as logo_err:
      print(f"[PitchGenSkills] Warning: Customer logo resolution skipped: {logo_err}")

  # 3. STAGE 1 (Immediate Fault-Isolated Commit): Commit Customer Cover Logo, Structural Repairs, and Baseline 🔗 Source Slide Speaker Notes immediately
  logo_batch_requests = []
  if customer_logo_url:
    for placeholder_tag in ("{{CUSTOMER_LOGO}}", "{{LOGO}}", "[CUSTOMER_LOGO]"):
      logo_batch_requests.append({
          "replaceAllShapesWithImage": {
              "imageUrl": customer_logo_url,
              "replaceMethod": "CENTER_INSIDE",
              "containsText": {
                  "text": placeholder_tag,
                  "matchCase": False,
              },
          }
      })

    # Determine Title/Cover slide (Slide 0, or Slide 1 if Slide 0 is the internal context summary slide)
    title_slide_idx = 0
    if len(slides) > 1:
      s0_text = " ".join(
          te.get("textRun", {}).get("content", "")
          for pe in slides[0].get("pageElements", [])
          for te in pe.get("shape", {}).get("text", {}).get("textElements", [])
      ).lower()
      if any(k in s0_text for k in ("internal context", "remove this slide", "user input", "opportunity id")):
        title_slide_idx = 1

    if title_slide_idx < len(slides):
      title_slide_obj = slides[title_slide_idx]
      title_slide_id = title_slide_obj.get("objectId", "")
      title_slide_raw = " ".join(
          te.get("textRun", {}).get("content", "")
          for pe in title_slide_obj.get("pageElements", [])
          for te in pe.get("shape", {}).get("text", {}).get("textElements", [])
      )
      has_logo_placeholder = any(
          tag.lower() in title_slide_raw.lower()
          for tag in ("{{customer_logo}}", "{{logo}}", "[customer_logo]")
      )
      already_has_customer_logo_badge = False
      existing_untagged_logo_id = ""
      for pe_chk in title_slide_obj.get("pageElements", []):
        if "image" in pe_chk:
          tx_c, ty_c, w_c, h_c, _ = _element_bbox_pt(pe_chk)
          if 595.0 <= tx_c <= 640.0 and 10.0 <= ty_c <= 45.0 and w_c <= 65.0 and h_c <= 65.0:
            alt_title = str(pe_chk.get("title") or "").strip()
            if alt_title.startswith("PitchGen-CustomerLogo:"):
              already_has_customer_logo_badge = True
            else:
              existing_untagged_logo_id = pe_chk.get("objectId", "")
            break
      if existing_untagged_logo_id:
        logo_batch_requests.append({
            "replaceImage": {
                "imageObjectId": existing_untagged_logo_id,
                "url": customer_logo_url,
                "imageReplaceMethod": "CENTER_INSIDE",
            }
        })
        logo_batch_requests.append({
            "updatePageElementAltText": {
                "objectId": existing_untagged_logo_id,
                "title": f"PitchGen-CustomerLogo:{cust_name}",
                "description": f"Official customer logo badge for {cust_name}",
            }
        })
      elif (
          title_slide_id
          and not has_logo_placeholder
          and not already_has_customer_logo_badge
      ):
        emu_per_pt = 12700
        safe_s_id = re.sub(r"[^a-zA-Z0-9_]", "", title_slide_id)[:20] or "s0"
        logo_obj_id = f"pg_cust_logo_{safe_s_id}_{uuid.uuid4().hex[:6]}"
        logo_batch_requests.append({
            "createImage": {
                "objectId": logo_obj_id,
                "url": customer_logo_url,
                "elementProperties": {
                    "pageObjectId": title_slide_id,
                    "size": {
                        "width": {
                            "magnitude": int(30.2 * emu_per_pt),
                            "unit": "EMU",
                        },
                        "height": {
                            "magnitude": int(30.2 * emu_per_pt),
                            "unit": "EMU",
                        },
                    },
                    "transform": {
                        "scaleX": 1.0,
                        "scaleY": 1.0,
                        "translateX": int(618.0 * emu_per_pt),
                        "translateY": int(24.2 * emu_per_pt),
                        "unit": "EMU",
                    },
                },
            }
        })
        logo_batch_requests.append({
            "updatePageElementAltText": {
                "objectId": logo_obj_id,
                "title": f"PitchGen-CustomerLogo:{cust_name}",
                "description": f"Official customer logo badge for {cust_name}",
            }
        })

  for l_req in logo_batch_requests:
    try:
      r_logo = requests.post(
          f"https://slides.googleapis.com/v1/presentations/{presentation_id}:batchUpdate",
          headers=headers,
          json={"requests": [l_req]},
          timeout=25,
      )
      if r_logo.status_code == 200:
        print(f"[PitchGenSkills] Stage 1: Committed customer logo ({list(l_req.keys())[0]}) to {presentation_id}!")
    except Exception as logo_b_err:
      print(f"[PitchGenSkills] Warning: Stage 1 customer logo commit error: {logo_b_err}")

  early_stage1_requests = list(requests_batch)
  requests_batch = []
  for s_id, n_meta in slide_notes_metadata.items():
    notes_id = n_meta.get("notes_shape_id")
    new_notes = (n_meta.get("new_notes") or "").strip()
    old_notes = (n_meta.get("old_notes") or "").strip()
    source_url = n_meta.get("source_url") or ""
    if not notes_id or not new_notes:
      continue
    if new_notes != old_notes:
      if old_notes:
        early_stage1_requests.append({
            "deleteText": {
                "objectId": notes_id,
                "textRange": {"type": "ALL"},
            }
        })
      early_stage1_requests.append({
          "insertText": {
              "objectId": notes_id,
              "insertionIndex": 0,
              "text": new_notes,
          }
      })
      early_stage1_requests.append({
          "updateTextStyle": {
              "objectId": notes_id,
              "textRange": {"type": "ALL"},
              "style": {
                  "fontFamily": "Google Sans",
                  "fontSize": {"magnitude": 11, "unit": "PT"},
              },
              "fields": "fontFamily,fontSize",
          }
      })
    if source_url and source_url in new_notes:
      url_start = new_notes.find(source_url)
      url_end = url_start + len(source_url)
      early_stage1_requests.append({
          "updateTextStyle": {
              "objectId": notes_id,
              "textRange": {
                  "type": "FIXED_RANGE",
                  "startIndex": url_start,
                  "endIndex": url_end,
              },
              "style": {
                  "link": {"url": source_url},
                  "underline": True,
              },
              "fields": "link,underline",
          }
      })

  if early_stage1_requests:
    try:
      r_s1 = requests.post(
          f"https://slides.googleapis.com/v1/presentations/{presentation_id}:batchUpdate",
          headers=headers,
          json={"requests": early_stage1_requests},
          timeout=35,
      )
      if r_s1.status_code == 200:
        print(
            f"[PitchGenSkills] Stage 1: Committed {len(early_stage1_requests)}"
            f" structural & 🔗 Source Slide speaker note operations to {presentation_id}!"
        )
        for n_meta in slide_notes_metadata.values():
          if n_meta.get("new_notes"):
            n_meta["old_notes"] = (n_meta.get("new_notes") or "").strip()
    except Exception as s1_err:
      print(f"[PitchGenSkills] Warning: Stage 1 batchUpdate error: {s1_err}")

  # 4. STAGE 2 (Concurrent AI Pass): Run TextTransformerWorkflow.execute_deck_holistic (ThinkingLevel.MEDIUM) IN PARALLEL with Hero Visual Customization
  visual_batch_requests = []
  batch_requests = []

  pic_tasks = []
  if cust_name and transform_slides:
    cover_pic_tasks = []
    content_pic_candidates = []
    for t_slide in transform_slides:
      if not isinstance(t_slide, dict):
        continue
      if (
          t_slide.get("is_proof_point")
          or t_slide.get("is_architecture_product_slide")
      ):
        continue
      s_pics = t_slide.get("slide_pictures") or []
      if not s_pics:
        continue
      slide_txt_ctx = " | ".join(
          str(d.get("text") or "").strip()
          for d in (t_slide.get("data") or [])
          if isinstance(d, dict) and d.get("text")
      )
      if t_slide.get("is_title_slide"):
        for p_info in s_pics:
          area_pt2 = float(p_info.get("width_pt") or 0.0) * float(
              p_info.get("height_pt") or 0.0
          )
          cover_pic_tasks.append((area_pt2, p_info, slide_txt_ctx))
      else:
        # Collect up to 5 candidates per content slide in size order so an animated GIF or hollow bezel never blocks static hero visuals on the same slide
        sorted_s_pics = sorted(
            s_pics,
            key=lambda p: float(p.get("width_pt") or 0.0)
            * float(p.get("height_pt") or 0.0),
            reverse=True,
        )[:5]
        best_area = float(sorted_s_pics[0].get("width_pt") or 0.0) * float(
            sorted_s_pics[0].get("height_pt") or 0.0
        )
        content_pic_candidates.append((best_area, sorted_s_pics, slide_txt_ctx))

    cover_pic_tasks.sort(key=lambda x: x[0], reverse=True)
    content_pic_candidates.sort(key=lambda x: x[0], reverse=True)
    # Round-robin across content slides (primary candidate per slide first, then secondary/grid candidates)
    rr_content_tuples = []
    for slot_idx in range(5):
      for _, s_pic_list, s_ctx in content_pic_candidates:
        if slot_idx < len(s_pic_list):
          p_cand = s_pic_list[slot_idx]
          c_area = float(p_cand.get("width_pt") or 0.0) * float(
              p_cand.get("height_pt") or 0.0
          )
          rr_content_tuples.append((c_area, p_cand, s_ctx))
    selected_pic_tuples = cover_pic_tasks[:1] + rr_content_tuples[:24]
    pic_tasks = [(p_inf, s_ctx) for _, p_inf, s_ctx in selected_pic_tuples]

  import concurrent.futures

  def _run_holistic_text():
    if not transform_slides:
      return transform_slides
    from agents.workflows.text_transformer_workflow import TextTransformerWorkflow

    effective_cust = cust_name or "the target customer"
    effective_ind = ind_name or "their industry"
    outline_obj = (
        (outputs_data or {}).get("outline")
        if isinstance((outputs_data or {}).get("outline"), dict)
        else {}
    )
    specific_objective = str(
        (outputs_data or {}).get("criteria")
        or (outputs_data or {}).get("user_prompt")
        or (outputs_data or {}).get("query")
        or ctx.get("user_prompt")
        or ctx.get("use_case")
        or ctx.get("business_problem")
        or ctx.get("pitch_goal")
        or ctx.get("solution")
        or ctx.get("additional_context")
        or (outputs_data or {}).get("deck_theme")
        or outline_obj.get("title")
        or ""
    ).strip()
    ag_summary_parts = []
    if agendas_lookup_dict:
      for _, ag_v in agendas_lookup_dict.items():
        if isinstance(ag_v, dict) and ag_v.get("title"):
          pts = ", ".join(str(p) for p in (ag_v.get("parts") or [])[:3])
          ag_summary_parts.append(
              f"{ag_v['title']}" + (f" ({pts})" if pts else "")
          )
    agenda_focus_str = "; ".join(ag_summary_parts)
    if (
        specific_objective
        and agenda_focus_str
        and agenda_focus_str not in specific_objective
    ):
      full_focus = (
          f"{specific_objective} | Key Initiative Pillars: {agenda_focus_str}"
      )
    else:
      full_focus = specific_objective or agenda_focus_str

    if (
        full_focus
        and isinstance(ctx, dict)
        and not ctx.get("specific_use_case")
    ):
      ctx["specific_use_case"] = full_focus

    criteria = (
        f"Tailor presentation text to {effective_cust} in the {effective_ind}"
        " industry."
        + (
            " PRIMARY CUSTOMER INITIATIVE & USE CASE (MUST ANCHOR EVERY"
            f" SLIDE'S HEADLINE, SUB-CARD HEADERS, AND BULLETS): {full_focus}."
            if full_focus
            else ""
        )
        + " Deeply re-anchor all value propositions, sub-card headers, domain"
        " workflows, and executive narrative flow to this specific customer"
        " initiative (never perform shallow 1-word noun swaps) while"
        " preserving structural density and bounding box character limits."
    )
    wf = TextTransformerWorkflow(config)
    return wf.execute_deck_holistic(
        transform_slides,
        criteria=criteria,
        context=ctx,
    )

  def _run_pic_task(task_tuple):
    from pitchgen_utils.image_util import customize_slide_picture_for_customer

    p_inf, s_ctx = task_tuple
    return customize_slide_picture_for_customer(
        pic_info=p_inf,
        slide_text_context=s_ctx,
        customer_name=cust_name,
        industry=ind_name,
        customer_logo_url=customer_logo_url,
        config=config,
    )

  with concurrent.futures.ThreadPoolExecutor(
      max_workers=1 + min(8, max(1, len(pic_tasks)))
  ) as stage2_exec:
    text_future = stage2_exec.submit(_run_holistic_text) if transform_slides else None
    pic_futures = [stage2_exec.submit(_run_pic_task, pt) for pt in pic_tasks]

    if text_future is not None:
      try:
        transformed_list = text_future.result()
        for t_slide in transformed_list or []:
          if not isinstance(t_slide, dict):
            continue
          t_sid = t_slide.get("slideId") or t_slide.get("slide_id")
          if (
              t_sid
              and t_sid in slide_notes_metadata
              and t_slide.get("speaker_notes")
          ):
            slide_notes_metadata[t_sid]["new_notes"] = str(
                t_slide["speaker_notes"]
            ).strip()
        transform_slides = transformed_list or transform_slides
      except Exception as tf_err:
        print(
            "[PitchGenSkills] Warning: Post-assembly execute_deck_holistic"
            f" error: {tf_err}"
        )

    for pf in pic_futures:
      try:
        req_item = pf.result()
        if isinstance(req_item, dict) and "replaceImage" in req_item:
          visual_batch_requests.append(
              {"replaceImage": req_item["replaceImage"]}
          )
          if isinstance(req_item.get("_reset_crop_request"), dict):
            visual_batch_requests.append(req_item["_reset_crop_request"])
          if isinstance(req_item.get("_alt_text_request"), dict):
            visual_batch_requests.append(req_item["_alt_text_request"])
      except Exception as pf_err:
        print(f"[PitchGenSkills] Warning: In-slide visual customization task error: {pf_err}")

  def _estimate_wrapped_lines(
      text_str: str, width_pt: float | None, fs: float
  ) -> int:
    if not text_str or not width_pt or float(width_pt) <= 0 or fs <= 0:
      return 1
    usable_w = max(60.0, float(width_pt) - 12.0)
    char_w = fs * 0.54
    total_lines = 0
    for para in text_str.split("\n"):
      words = para.split()
      if not words:
        total_lines += 1
        continue
      lines_in_para = 1
      cur_w = 0.0
      for w in words:
        w_width = len(w) * char_w
        space_w = char_w * 0.6 if cur_w > 0 else 0.0
        if cur_w > 0 and (cur_w + space_w + w_width) > usable_w:
          lines_in_para += 1
          cur_w = w_width
        else:
          cur_w += space_w + w_width
      total_lines += lines_in_para
    return max(1, total_lines)

  def _auto_fit_title_font_size(
      text_str: str,
      width_pt: float | None,
      clearance_pt: float | None,
      orig_fs: float,
      max_lines: int = 2,
  ) -> float:
    if not text_str or orig_fs < 20.0:
      return orig_fs
    if orig_fs >= 48.0:
      return 68.0
    w_val = float(width_pt) if (width_pt and float(width_pt) > 0) else 600.0
    c_val = (
        float(clearance_pt)
        if (clearance_pt and float(clearance_pt) > 0)
        else None
    )
    effective_max_lines = (
        4
        if w_val < 300.0
        else (max(max_lines, 3) if w_val < 460.0 else max_lines)
    )
    for cand_fs in (orig_fs, 30.0, 28.0, 26.0, 24.0):
      if cand_fs > orig_fs:
        continue
      est_lines = _estimate_wrapped_lines(text_str, w_val, cand_fs)
      line_budget = (
          effective_max_lines if cand_fs > 24.0 else max(effective_max_lines, 3)
      )
      fits_lines = est_lines <= line_budget
      fits_clearance = (
          True
          if c_val is None
          else (est_lines * cand_fs * 1.25 <= max(32.0, c_val - 6.0))
      )
      if fits_lines and fits_clearance:
        return cand_fs
    return 24.0

  def _auto_fit_card_body_font_size(
      text_str: str,
      width_pt: float | None,
      height_pt: float | None,
      clearance_pt: float | None,
      orig_fs: float,
      header_height_pt: float = 0.0,
      min_fs: float = 9.5,
  ) -> float:
    """Enforces the Pre-Batch Algebraic Text-Height Gate (H_req <= H_card) by stepping down body fontSize when wrapped lines exceed the physical card height."""
    if not text_str or not width_pt or float(width_pt) <= 0:
      return orig_fs
    eff_h = None
    if height_pt and float(height_pt) > 0:
      eff_h = float(height_pt)
    if clearance_pt and float(clearance_pt) > 0:
      eff_h = (
          min(eff_h, float(clearance_pt))
          if eff_h is not None
          else float(clearance_pt)
      )
    if eff_h is None or eff_h <= 18.0:
      return orig_fs

    w_val = float(width_pt)
    cand_fs = float(orig_fs)
    while cand_fs >= min_fs:
      est_lines = _estimate_wrapped_lines(text_str, w_val, cand_fs)
      req_h = 12.0 + float(header_height_pt) + (est_lines * cand_fs * 1.25)
      if req_h <= eff_h:
        return round(cand_fs, 1)
      cand_fs -= 0.5
    return min_fs

  # 4a. Shape text replacements & geometry auto-fitting (reusable + bespoke slides)
  for t_slide in transform_slides:
    if not isinstance(t_slide, dict):
      continue
    if t_slide.get("_skip_mutation") or t_slide.get("skip"):
      continue
    is_reusable_slide = bool(t_slide.get("is_reusable", True))
    for sh_data in t_slide.get("data", []):
      if not isinstance(sh_data, dict):
        continue
      sh_id = sh_data.get("shapeId") or sh_data.get("shape_id")
      new_text = str(sh_data.get("text") or "").strip()
      if not sh_id or not new_text or sh_id not in slide_shape_metadata:
        continue
      meta = slide_shape_metadata[sh_id]
      old_text = meta["old_text"].strip()
      paras = list(meta.get("paragraphs") or [])
      sh_fs = float(sh_data.get("fontSize") or 12.0)
      sh_w_pt = float(meta.get("width_pt") or 0.0)
      sh_h_pt = float(meta.get("height_pt") or 0.0)
      sh_c_pt = meta.get("clearance_pt")

      if not is_reusable_slide:
        # Bespoke synthesized slide:
        x_val = float(meta.get("x_pt") or 0.0)
        y_val = float(meta.get("y_pt") or 0.0)
        w_val = float(sh_w_pt) if (sh_w_pt and float(sh_w_pt) > 0) else 180.0
        h_val = float(meta.get("height_pt") or 100.0)

        # 1) Auto-fit 24-34pt action titles (never shrinking below 24pt) and upgrade 12-20pt template titles to 24pt
        is_primary_slide_title = (
            not meta.get("has_bullets")
            and len(paras) == 1
            and (
                sh_fs >= 24.0
                or (
                    x_val <= 60.0
                    and y_val <= 58.0
                    and w_val >= 210.0
                    and 12 <= len(old_text) <= 95
                )
                or (
                    x_val <= 60.0
                    and 58.0 < y_val <= 115.0
                    and 205.0 <= w_val <= 265.0
                    and sh_fs >= 18.0
                    and 12 <= len(old_text) <= 95
                )
            )
        )
        if is_primary_slide_title:
          base_title_fs = max(sh_fs, 24.0)
          fitted_fs = _auto_fit_title_font_size(
              old_text, sh_w_pt, sh_c_pt, base_title_fs, max_lines=2
          )
          batch_requests.append({
              "updateTextStyle": {
                  "objectId": sh_id,
                  "textRange": {"type": "ALL"},
                  "style": {
                      "fontSize": {"magnitude": fitted_fs, "unit": "PT"},
                      "bold": False,
                      "weightedFontFamily": {
                          "fontFamily": "Google Sans",
                          "weight": 500,
                      },
                  },
                  "fields": "fontSize,bold,weightedFontFamily",
              }
          })
          continue

        # 2) Combined Header + Body multi-paragraph shapes (e.g. T4, T7, T12, T13, T15, T16, T17, T18, T19, T21, T29, T31, T33, T34, T39, T59)
        if len(paras) >= 2 and sh_fs < 20.0:
          hdr_text = str(paras[0].get("text") or "").strip()
          body_paras = paras[1:]
          body_text = "\n".join(
              str(p.get("text") or "").strip()
              for p in body_paras
              if str(p.get("text") or "").strip()
          ).strip()
          if len(hdr_text) <= 58 and body_text:
            body_orig_fs = 0.0
            if isinstance(body_paras[-1].get("style"), dict):
              body_orig_fs = float(
                  (body_paras[-1]["style"].get("fontSize") or {}).get(
                      "magnitude"
                  )
                  or 0.0
              )
            max_hdr_chars = 58
            if w_val <= 130.0:
              target_body_fs = (
                  body_orig_fs
                  if 7.5 <= body_orig_fs <= 9.5
                  else 10.0
              )
              max_body_chars = 135 if h_val >= 135.0 else 105
              max_hdr_chars = 26
            elif w_val <= 172.0:
              target_body_fs = 11.0
              max_body_chars = 172 if h_val >= 135.0 else 135
              max_hdr_chars = 28
            elif w_val <= 235.0:
              target_body_fs = 12.0 if len(body_text) <= 165 else 11.5
              max_body_chars = 175
            else:
              target_body_fs = 12.0
              max_body_chars = 230

            # Pre-Batch Algebraic Text-Height Gate (H_req <= H_card)
            hdr_est_h = (
                max(1, _estimate_wrapped_lines(hdr_text, w_val, sh_fs))
                * sh_fs
                * 1.25
            )
            target_body_fs = _auto_fit_card_body_font_size(
                body_text,
                w_val,
                h_val,
                sh_c_pt,
                target_body_fs,
                header_height_pt=hdr_est_h,
                min_fs=min(8.5, target_body_fs),
            )
            try:
              from agents.workflows.text_transformer_workflow import TextTransformerWorkflow

              alg_body_cap = (
                  TextTransformerWorkflow.compute_algebraic_char_capacity(
                      width_pt=w_val,
                      height_pt=h_val,
                      font_size=min(target_body_fs, 9.0),
                      header_height_pt=hdr_est_h,
                  )
              )
              floor_body_cap = (
                  130 if (h_val >= 165.0 and 105.0 <= w_val <= 255.0) else 75
              )
              max_body_chars = min(
                  max_body_chars, max(floor_body_cap, alg_body_cap)
              )
            except Exception:
              pass

            for bp in body_paras:
              if isinstance(bp.get("style"), dict):
                bp["style"]["fontSize"] = {
                    "magnitude": target_body_fs,
                    "unit": "PT",
                }

            if len(body_text) > max_body_chars or len(hdr_text) > max_hdr_chars:
              try:
                from agents.workflows.text_transformer_workflow import TextTransformerWorkflow

                trim_wf = locals().get("workflow") or TextTransformerWorkflow(
                    config
                )
                trimmed_hdr = (
                    trim_wf._trim_to_char_limit(
                        hdr_text, max_hdr_chars, is_title_or_header=True
                    )
                    if len(hdr_text) > max_hdr_chars
                    else hdr_text
                )
                trimmed_body = (
                    trim_wf._trim_to_char_limit(
                        body_text, max_body_chars - 5, is_title_or_header=False
                    )
                    if len(body_text) > max_body_chars
                    else body_text
                )
                new_text = f"{trimmed_hdr}\n{trimmed_body}"
              except Exception:
                continue
            elif (
                meta.get("is_generated_slide")
                and h_val >= 165.0
                and 105.0 <= w_val <= 255.0
                and 35 <= len(old_text) < 106
            ):
              c_short = (c_name or "Enterprise").strip()
              pad_clause = (
                  " Built on Gemini Enterprise with unified data governance"
                  f" and real-time grounding across {c_short} workflows."
              )
              expanded_body = (
                  body_text.rstrip(".") + "." + pad_clause
                  if not body_text.endswith(".")
                  else body_text + pad_clause
              )
              if len(hdr_text) + 1 + len(expanded_body) > 215:
                expanded_body = (
                    expanded_body[: max(90, 210 - len(hdr_text))]
                    .rsplit(" ", 1)[0]
                    .rstrip(".,;:")
                    + "."
                )
              new_text = f"{hdr_text}\n{expanded_body}"
            else:
              # Even when length fits, normalize body paragraph font size (e.g. 10-11pt -> 12pt on 3-col T7, 12pt -> 11pt on 4-col T12, 10pt -> 11pt on T59)
              if body_orig_fs > 0 and abs(body_orig_fs - target_body_fs) >= 0.4:
                body_start_idx = len(hdr_text) + 1
                if body_start_idx < len(old_text):
                  batch_requests.append({
                      "updateTextStyle": {
                          "objectId": sh_id,
                          "textRange": {
                              "type": "FIXED_RANGE",
                              "startIndex": body_start_idx,
                              "endIndex": len(old_text),
                          },
                          "style": {
                              "fontSize": {
                                  "magnitude": target_body_fs,
                                  "unit": "PT",
                              }
                          },
                          "fields": "fontSize",
                      }
                  })
              continue
          else:
            continue

        # 3) Single-paragraph standalone card body shapes (e.g. T2, T3, T6, T16, T20, T23, T24, T27, T32, T35, T36, T42, T55, circle_charts, timeline)
        elif (
            sh_fs <= 13.5
            and len(old_text) >= 32
            and y_val < 355.0
            and not re.match(r"^(?:sources?:|\([1-4]\))", old_text.lower())
        ):
          if w_val >= 225.0:
            target_body_fs = 12.0 if len(old_text) <= 165 else 11.5
            max_body_chars = 185
          elif w_val >= 175.0:
            target_body_fs = (
                12.0 if (h_val >= 90.0 and len(old_text) <= 165) else 11.5
            )
            max_body_chars = 172 if h_val >= 135.0 else 165
          elif w_val >= 135.0:
            target_body_fs = 11.0
            max_body_chars = 172 if h_val >= 135.0 else 135
          else:
            target_body_fs = 10.5
            max_body_chars = 135 if h_val >= 135.0 else 115

          # Pre-Batch Algebraic Text-Height Gate (H_req <= H_card)
          target_body_fs = _auto_fit_card_body_font_size(
              old_text, w_val, h_val, sh_c_pt, target_body_fs, min_fs=8.5
          )
          try:
            from agents.workflows.text_transformer_workflow import TextTransformerWorkflow

            alg_body_cap = (
                TextTransformerWorkflow.compute_algebraic_char_capacity(
                    width_pt=w_val,
                    height_pt=h_val,
                    font_size=min(target_body_fs, 9.0),
                )
            )
            floor_body_cap = (
                130 if (h_val >= 165.0 and 105.0 <= w_val <= 255.0) else 75
            )
            max_body_chars = min(
                max_body_chars, max(floor_body_cap, alg_body_cap)
            )
          except Exception:
            pass

          if paras and isinstance(paras[-1].get("style"), dict):
            paras[-1]["style"]["fontSize"] = {
                "magnitude": target_body_fs,
                "unit": "PT",
            }

          if len(old_text) > max_body_chars:
            try:
              from agents.workflows.text_transformer_workflow import TextTransformerWorkflow

              trim_wf = locals().get("workflow") or TextTransformerWorkflow(
                  config
              )
              new_text = trim_wf._trim_to_char_limit(
                  old_text, max_body_chars - 5, is_title_or_header=False
              )
            except Exception:
              continue
          elif (
              meta.get("is_generated_slide")
              and h_val >= 165.0
              and 105.0 <= w_val <= 255.0
              and 35 <= len(old_text) < 106
          ):
            c_short = (c_name or "Enterprise").strip()
            pad_clause = (
                " Built on Gemini Enterprise with unified data governance and"
                f" real-time grounding across {c_short} workflows."
            )
            expanded_txt = (
                old_text.rstrip(".") + "." + pad_clause
                if not old_text.endswith(".")
                else old_text + pad_clause
            )
            if len(expanded_txt) > 215:
              expanded_txt = (
                  expanded_txt[:205].rsplit(" ", 1)[0].rstrip(".,;:") + "."
              )
            new_text = expanded_txt
          else:
            # Upgrade tiny template body font sizes (e.g. 7pt-10pt -> 10.5-12pt on T2/T20/T23/T36/circle_charts/timeline) or scale down if H_req > H_card
            if abs(sh_fs - target_body_fs) >= 0.4:
              batch_requests.append({
                  "updateTextStyle": {
                      "objectId": sh_id,
                      "textRange": {"type": "ALL"},
                      "style": {
                          "fontSize": {
                              "magnitude": target_body_fs,
                              "unit": "PT",
                          }
                      },
                      "fields": "fontSize",
                  }
              })
            continue
        else:
          continue

      # Always strip leading section numbers (e.g. "02\n", "01 Create...", "04 Maximizing...") from title/header shapes (fontSize >= 18)
      sh_hdr_fs = float(meta.get("header_font_size") or sh_fs)
      if sh_hdr_fs >= 18.0 or sh_fs >= 18.0:
        if len(paras) >= 2 and re.match(
            r"^\s*(?:0[1-9]|[1-9]\d?|section\s*\d+|part\s*\d+)[\.\:\-]?\s*$",
            str(paras[0].get("text") or "").strip(),
            re.IGNORECASE,
        ):
          paras = paras[1:]
        t_lines = new_text.split("\n")
        if len(t_lines) >= 2 and re.match(
            r"^\s*(?:0[1-9]|[1-9]\d?|section\s*\d+|part\s*\d+)[\.\:\-]?\s*$",
            t_lines[0],
            re.IGNORECASE,
        ):
          t_lines = t_lines[1:]
        if t_lines:
          t_lines[0] = re.sub(
              r"^\s*(?:0[1-9]|section\s*\d+|part\s*\d+)(?:[\.\:\-\s]+)",
              "",
              t_lines[0].strip(),
              flags=re.IGNORECASE,
          ).strip()
        new_text = "\n".join(t_lines).strip()

      # Ensure bespoke tall-card shapes transformed by TextTransformerWorkflow also satisfy the >=105 char density floor
      if (
          meta.get("is_generated_slide")
          and sh_h_pt >= 165.0
          and 105.0 <= sh_w_pt <= 255.0
          and sh_fs <= 14.5
          and 35 <= len(new_text) < 106
      ):
        c_short = (c_name or "Enterprise").strip()
        pad_clause = (
            " Built on Gemini Enterprise with unified data governance and"
            f" real-time grounding across {c_short} workflows."
        )
        new_text = (
            new_text.rstrip(".") + "." + pad_clause
            if not new_text.endswith(".")
            else new_text + pad_clause
        )
        if len(new_text) > 215:
          new_text = new_text[:205].rsplit(" ", 1)[0].rstrip(".,;:") + "."

      if not old_text or old_text == new_text:
        # Even if text did not change, auto-fit reusable title or body font size if it overflows its bounding box/clearance
        if sh_fs >= 20.0 and not meta.get("has_bullets"):
          fitted_fs = _auto_fit_title_font_size(
              old_text, sh_w_pt, sh_c_pt, sh_fs, max_lines=2
          )
          if fitted_fs < sh_fs:
            batch_requests.append({
                "updateTextStyle": {
                    "objectId": sh_id,
                    "textRange": {"type": "ALL"},
                    "style": {
                        "fontSize": {"magnitude": fitted_fs, "unit": "PT"}
                    },
                    "fields": "fontSize",
                }
            })
        elif (
            old_text
            and 8.5 <= sh_fs <= 16.0
            and sh_w_pt > 0
            and sh_h_pt > 0
            and len(old_text) >= 28
        ):
          fitted_body_fs = _auto_fit_card_body_font_size(
              old_text, sh_w_pt, sh_h_pt, sh_c_pt, sh_fs, min_fs=8.5
          )
          if fitted_body_fs < sh_fs - 0.3:
            batch_requests.append({
                "updateTextStyle": {
                    "objectId": sh_id,
                    "textRange": {"type": "ALL"},
                    "style": {
                        "fontSize": {"magnitude": fitted_body_fs, "unit": "PT"}
                    },
                    "fields": "fontSize",
                }
            })
        continue

      # Preserve Header + Body newline structure ONLY if original P0 was a true short bold header (not a paragraph starting with 1 bold word)
      if (
          len(paras) > 1
          and paras[0].get("is_bold_header")
          and not paras[1].get("is_bold_header")
          and "\n" not in new_text
      ):
        colon_idx = new_text.find(":")
        if 0 < colon_idx < 40:
          new_text = (
              new_text[:colon_idx].strip()
              + "\n"
              + new_text[colon_idx + 1 :].strip()
          )
        elif (
            len(new_text.strip()) <= 65
            and paras[1].get("text")
            and len(paras[1]["text"].strip()) >= 35
        ):
          # LLM returned only a new short header and dropped the body paragraph; keep new_text as P0 and preserve P1 body
          p1_body = paras[1]["text"].strip()
          new_text = new_text.strip() + "\n" + p1_body
        elif paras[0].get("text") and len(paras[0]["text"].strip()) <= 45:
          new_text = paras[0]["text"].strip() + "\n" + new_text

      batch_requests.append(
          {
              "deleteText": {
                  "objectId": sh_id,
                  "textRange": {"type": "ALL"},
              }
          }
      )
      batch_requests.append({
          "insertText": {
              "objectId": sh_id,
              "insertionIndex": 0,
              "text": new_text,
          }
      })

      new_paras = new_text.split("\n")
      has_unbulleted_header = bool(
          paras
          and not paras[0].get("has_bullet")
          and any(p.get("has_bullet") for p in paras[1:])
      )

      # Re-apply paragraph bullets and styles (weightedFontFamily, bold, fontSize, foregroundColor) per non-empty paragraph
      char_offset = 0
      non_empty_p_idx = 0
      for p_i, p_str in enumerate(new_paras):
        p_len = len(p_str)
        if p_len > 0 and paras:
          para_meta = (
              paras[non_empty_p_idx]
              if non_empty_p_idx < len(paras)
              else paras[-1]
          )
          non_empty_p_idx += 1

          if has_unbulleted_header and para_meta.get("has_bullet"):
            b_glyph = para_meta.get("bullet_glyph") or ""
            preset = (
                "BULLET_ARROW_DIAMOND_DISC"
                if b_glyph in ("➔", "➢", "➤", "→")
                else "BULLET_DISC_CIRCLE_SQUARE"
            )
            batch_requests.append({
                "createParagraphBullets": {
                    "objectId": sh_id,
                    "textRange": {
                        "type": "FIXED_RANGE",
                        "startIndex": char_offset,
                        "endIndex": char_offset + p_len,
                    },
                    "bulletPreset": preset,
                }
            })
          elif has_unbulleted_header and not para_meta.get("has_bullet"):
            batch_requests.append({
                "updateParagraphStyle": {
                    "objectId": sh_id,
                    "textRange": {
                        "type": "FIXED_RANGE",
                        "startIndex": char_offset,
                        "endIndex": char_offset + p_len,
                    },
                    "style": {
                        "indentStart": {"magnitude": 0, "unit": "PT"},
                        "indentFirstLine": {"magnitude": 0, "unit": "PT"},
                    },
                    "fields": "indentStart,indentFirstLine",
                }
            })

          style_snap = para_meta.get("style") or {}
          style_update = {}
          fields = []
          fs_val = 0.0
          if style_snap.get("fontSize"):
            style_update["fontSize"] = style_snap["fontSize"]
            fields.append("fontSize")
            try:
              fs_val = float(style_snap["fontSize"].get("magnitude") or 0.0)
            except Exception:
              fs_val = 0.0
          elif p_i == 0 and sh_fs >= 20.0:
            fs_val = sh_fs
            style_update["fontSize"] = {"magnitude": sh_fs, "unit": "PT"}
            fields.append("fontSize")

          if (
              p_i == 0
              and fs_val >= 20.0
              and len(new_paras) == 1
              and not meta.get("has_bullets")
          ):
            fitted_fs = _auto_fit_title_font_size(
                p_str, sh_w_pt, sh_c_pt, fs_val, max_lines=2
            )
            if fitted_fs != fs_val:
              fs_val = fitted_fs
              style_update["fontSize"] = {"magnitude": fitted_fs, "unit": "PT"}
              if "fontSize" not in fields:
                fields.append("fontSize")
          elif (
              8.5 <= fs_val <= 16.0
              and sh_w_pt > 0
              and sh_h_pt > 0
              and len(new_text) >= 28
              and not para_meta.get("is_bold_header")
          ):
            hdr_h_est = 0.0
            if len(new_paras) > 1 and paras[0].get("is_bold_header"):
              hdr_fs = float(
                  ((paras[0].get("style") or {}).get("fontSize") or {}).get(
                      "magnitude"
                  )
                  or fs_val
              )
              hdr_h_est = (
                  max(1, _estimate_wrapped_lines(new_paras[0], sh_w_pt, hdr_fs))
                  * hdr_fs
                  * 1.25
              )
            body_for_fit = (
                "\n".join(new_paras[1:])
                if (len(new_paras) > 1 and paras[0].get("is_bold_header"))
                else new_text
            )
            fitted_body_fs = _auto_fit_card_body_font_size(
                body_for_fit,
                sh_w_pt,
                sh_h_pt,
                sh_c_pt,
                fs_val,
                header_height_pt=hdr_h_est,
                min_fs=8.5,
            )
            if fitted_body_fs < fs_val:
              fs_val = fitted_body_fs
              style_update["fontSize"] = {
                  "magnitude": fitted_body_fs,
                  "unit": "PT",
              }
              if "fontSize" not in fields:
                fields.append("fontSize")

          if style_snap.get("bold") is not None:
            style_update["bold"] = bool(style_snap["bold"])
            fields.append("bold")
          if style_snap.get("italic") is not None:
            style_update["italic"] = bool(style_snap["italic"])
            fields.append("italic")

          # Preserve weightedFontFamily (e.g. Google Sans Medium weight=500) so Slides API does not downgrade titles to Regular (400)
          wff = style_snap.get("weightedFontFamily")
          ff = style_snap.get("fontFamily") or (wff.get("fontFamily") if isinstance(wff, dict) else None)
          if isinstance(wff, dict) and wff.get("fontFamily"):
            w_copy = dict(wff)
            if p_i == 0 and fs_val >= 18.0 and int(w_copy.get("weight") or 400) < 500:
              w_copy["weight"] = 500
            style_update["weightedFontFamily"] = w_copy
            fields.append("weightedFontFamily")
          elif ff:
            if p_i == 0 and fs_val >= 18.0 and "google sans" in str(ff).lower():
              style_update["weightedFontFamily"] = {
                  "fontFamily": str(ff),
                  "weight": 700 if style_snap.get("bold") else 500,
              }
              fields.append("weightedFontFamily")
            else:
              style_update["fontFamily"] = ff
              fields.append("fontFamily")

          if style_snap.get("foregroundColor"):
            style_update["foregroundColor"] = style_snap["foregroundColor"]
            fields.append("foregroundColor")
          if fields:
            batch_requests.append({
                "updateTextStyle": {
                    "objectId": sh_id,
                    "textRange": {
                        "type": "FIXED_RANGE",
                        "startIndex": char_offset,
                        "endIndex": char_offset + p_len,
                    },
                    "style": style_update,
                    "fields": ",".join(fields),
                }
            })

          # If the original paragraph had a distinct bold/colored lead-in phrase (e.g. first 1-5 words), apply lead_style to those leading words
          lead_snap = para_meta.get("lead_style")
          lead_wc = int(para_meta.get("lead_word_count") or 0)
          if isinstance(lead_snap, dict) and lead_wc > 0:
            p_words = p_str.split()
            if len(p_words) > lead_wc:
              lead_phrase = " ".join(p_words[:lead_wc])
              lead_len = len(lead_phrase)
              lead_upd = {}
              lead_flds = []
              if lead_snap.get("bold") is not None:
                lead_upd["bold"] = bool(lead_snap["bold"])
                lead_flds.append("bold")
              if lead_snap.get("weightedFontFamily"):
                lead_upd["weightedFontFamily"] = lead_snap["weightedFontFamily"]
                lead_flds.append("weightedFontFamily")
              if lead_snap.get("foregroundColor"):
                lead_upd["foregroundColor"] = lead_snap["foregroundColor"]
                lead_flds.append("foregroundColor")
              if lead_flds and 0 < lead_len < p_len:
                batch_requests.append({
                    "updateTextStyle": {
                        "objectId": sh_id,
                        "textRange": {
                            "type": "FIXED_RANGE",
                            "startIndex": char_offset,
                            "endIndex": char_offset + lead_len,
                        },
                        "style": lead_upd,
                        "fields": ",".join(lead_flds),
                    }
                })
        char_offset += p_len + 1

  # 4b. Speaker notes updates (including 🔗 Source Slide clickable hyperlink + Transition Hooks)
  cr_slide_ids = {
      t_sl.get("slideId")
      for t_sl in transform_slides or []
      if isinstance(t_sl, dict) and t_sl.get("is_proof_point")
  }
  for s_id, n_meta in slide_notes_metadata.items():
    notes_id = n_meta.get("notes_shape_id")
    new_notes = (n_meta.get("new_notes") or "").strip()
    old_notes = (n_meta.get("old_notes") or "").strip()
    source_url = n_meta.get("source_url") or ""
    if not notes_id or not new_notes:
      continue

    if s_id not in cr_slide_ids:
      new_notes = re.sub(
          r"(?i)\b(?:the\s+)?Gemini\s+Enterprise\s+app(?:lication)?,\s*built\s+on\s+(?:the\s+)?(?:Gemini\s+Enterprise\s+)?Agent\s+Platform\b",
          "Gemini Enterprise",
          new_notes,
      )
      new_notes = re.sub(
          r"(?i),\s*built\s+on\s+(?:the\s+)?(?:Gemini\s+Enterprise\s+)?Agent\s+Platform\b",
          "",
          new_notes,
      )
      new_notes = re.sub(
          r"(?i)\bGemini Enterprise Agent Platform\b",
          "Gemini Enterprise",
          new_notes,
      )
      new_notes = re.sub(
          r"(?i)\b(?:the\s+)?Agent\s+Platform\b",
          "Gemini Enterprise",
          new_notes,
      )
      new_notes = re.sub(
          r"(?i)\bGemini Enterprise platform\b", "Gemini Enterprise", new_notes
      )
      new_notes = re.sub(
          r"(?i)\bGemini Enterprise app\b",
          "Gemini Enterprise on web",
          new_notes,
      )
      new_notes = re.sub(
          r"(?i)\bthe GE app\b", "Gemini Enterprise on web", new_notes
      )
      new_notes = re.sub(r"\bGEAP\b", "Gemini Enterprise", new_notes)
      new_notes = re.sub(r"(?i)\bVertex AI\b", "Google Cloud AI", new_notes)
      new_notes = re.sub(
          r"(?i)\bpowered by Gemini\b(?!\s+Enterprise)",
          "powered by Gemini Enterprise",
          new_notes,
      )

    if new_notes != old_notes:
      if old_notes:
        batch_requests.append(
            {
                "deleteText": {
                    "objectId": notes_id,
                    "textRange": {"type": "ALL"},
                }
            }
        )
      batch_requests.append({
          "insertText": {
              "objectId": notes_id,
              "insertionIndex": 0,
              "text": new_notes,
          }
      })
      batch_requests.append({
          "updateTextStyle": {
              "objectId": notes_id,
              "textRange": {"type": "ALL"},
              "style": {
                  "fontFamily": "Google Sans",
                  "fontSize": {"magnitude": 11, "unit": "PT"},
              },
              "fields": "fontFamily,fontSize",
          }
      })
    # Make the original source slide URL a clickable hyperlink in Speaker Notes!
    if source_url and source_url in new_notes:
      url_start = new_notes.find(source_url)
      url_end = url_start + len(source_url)
      batch_requests.append({
          "updateTextStyle": {
              "objectId": notes_id,
              "textRange": {
                  "type": "FIXED_RANGE",
                  "startIndex": url_start,
                  "endIndex": url_end,
              },
              "style": {
                  "link": {"url": source_url},
                  "underline": True,
              },
              "fields": "link,underline",
          }
      })

  # Final Enterprise-Brand-Unification sweep across all non-Customer-Reference slide pages
  non_cr_page_ids = [
      s.get("objectId")
      for s in slides or []
      if isinstance(s, dict)
      and s.get("objectId")
      and s.get("objectId") not in cr_slide_ids
  ]
  if non_cr_page_ids:
    for bad_term, good_term in (
        ("Gemini Enterprise Agent Platform", "Gemini platform"),
        ("Gemini Enterprise platform", "Gemini platform"),
        ("Gemini Platform", "Gemini platform"),
        ("Gemini Enterprise app", "Gemini"),
        ("the GE app", "Gemini"),
        ("GEAP", "Gemini platform"),
        ("GECX", "Gemini for customer experience"),
        ("Sobi", "Gemini"),
        (
            "Gemini Enterprise for Financial Services",
            "Gemini for financial services",
        ),
        ("Gemini Enterprise for Legal", "Gemini for legal"),
        ("Gemini Enterprise for CX", "Gemini for customer experience"),
        (
            "Gemini Enterprise for Customer Experience",
            "Gemini for customer experience",
        ),
        ("Gemini Enterprise for Healthcare", "Gemini for healthcare"),
        ("Gemini Enterprise for Life Sciences", "Gemini for life sciences"),
        (
            "Gemini Enterprise for Government Services",
            "Gemini for government services",
        ),
        ("Gemini Enterprise for Retail", "Gemini for retail"),
        ("Gemini Enterprise for Marketing", "Gemini for marketing"),
        ("Antigravity in Gemini Enterprise", "Antigravity in Gemini platform"),
        (
            "Model Garden in Gemini Enterprise",
            "Model Garden in Gemini platform",
        ),
        (
            "agent runtime in Gemini Enterprise",
            "agent runtime in Gemini platform",
        ),
        ("Vertex AI", "Gemini platform"),
        ("powered by Gemini.", "Built with Gemini."),
        ("powered by Gemini,", "Built with Gemini,"),
        ("powered by Gemini ", "Built with Gemini "),
        ("Powered by Gemini", "Built with Gemini"),
        (
            "powered by Gemini Enterprise Enterprise",
            "powered by Gemini Enterprise",
        ),
    ):
      batch_requests.append({
          "replaceAllText": {
              "pageObjectIds": non_cr_page_ids,
              "containsText": {"text": bad_term, "matchCase": False},
              "replaceText": good_term,
          }
      })

    # Deterministic Cymbal white-label placeholder brand sweep across all non-Customer-Reference slide pages
    clean_cust = str(
        locals().get("customer_name")
        or locals().get("cust_name")
        or locals().get("c_name")
        or ""
    ).strip()
    if clean_cust and clean_cust.lower() not in (
        "-",
        "none",
        "null",
        "cymbal",
        "the target enterprise",
    ):
      cust_slug = re.sub(r"[^a-z0-9]", "", clean_cust.lower()) or "enterprise"
      for cym_bad, cym_good in (
          ("cymbal.com", f"{cust_slug}.com"),
          ("@cymbal", f"@{cust_slug}"),
          ("Cymbal Superstore", clean_cust),
          ("Cymbal Shops", clean_cust),
          ("Cymbal Direct", clean_cust),
          ("Cymbal FinTech", clean_cust),
          ("Cymbal's", f"{clean_cust}'s"),
          ("Cymbal’s", f"{clean_cust}’s"),
          ("Cymbal", clean_cust),
      ):
        batch_requests.append({
            "replaceAllText": {
                "pageObjectIds": non_cr_page_ids,
                "containsText": {"text": cym_bad, "matchCase": False},
                "replaceText": cym_good,
            }
        })

  if batch_requests:
    try:
      r_batch = requests.post(
          f"https://slides.googleapis.com/v1/presentations/{presentation_id}:batchUpdate",
          headers=headers,
          json={"requests": batch_requests},
          timeout=60,
      )
      if r_batch.status_code == 200:
        print(
            f"[PitchGenSkills] Applied {len(batch_requests)} post-assembly"
            " Slides text/style batchUpdate operations to"
            f" {presentation_id}!"
        )
      else:
        print(
            "[PitchGenSkills] Warning: Slides text batchUpdate returned"
            f" {r_batch.status_code}: {r_batch.text[:300]}"
        )
    except Exception as batch_err:
      print(
          "[PitchGenSkills] Warning: Slides text batchUpdate failed:"
          f" {batch_err}"
      )

  if visual_batch_requests:
    for v_req in visual_batch_requests:
      try:
        r_vis = requests.post(
            f"https://slides.googleapis.com/v1/presentations/{presentation_id}:batchUpdate",
            headers=headers,
            json={"requests": [v_req]},
            timeout=30,
        )
        if r_vis.status_code == 200:
          print(
              "[PitchGenSkills] Applied visual batchUpdate"
              f" ({list(v_req.keys())[0]}) to {presentation_id}!"
          )
        else:
          print(
              "[PitchGenSkills] Warning: Visual batchUpdate"
              f" ({list(v_req.keys())[0]}) returned {r_vis.status_code}:"
              f" {r_vis.text[:250]}"
          )
      except Exception as vis_err:
        print(f"[PitchGenSkills] Warning: Visual batchUpdate error: {vis_err}")
    try:
      from pitchgen_utils.image_util import cleanup_temp_drive_docs

      cleanup_temp_drive_docs(oauth_token=token)
    except Exception:
      pass

  # Post-Stage-2 CVI Order Verification Pass: ensure any slide whose title or CR notes were updated in Stage 1/2 remains in strict monotonic CVI order
  try:
    r_verify = requests.get(
        f"https://slides.googleapis.com/v1/presentations/{presentation_id}",
        headers=headers,
        timeout=30,
    )
    if r_verify.status_code == 200:
      v_slides = r_verify.json().get("slides", [])
      if len(v_slides) >= 4:

        def _post_stage2_sort_key(pair):
          idx_v, s_v = pair
          cvi_r = _universal_cvi_stage_rank(s_v, idx_v, len(v_slides))
          if cvi_r <= 2 or cvi_r >= 80:
            return (cvi_r, 0.0, cvi_r, idx_v)
          sid_v = str(s_v.get("objectId") or "")
          sec_k_v = slide_id_to_agenda_sec.get(sid_v)
          if sec_k_v is not None and str(sec_k_v).strip():
            try:
              sec_num_v = float(sec_k_v)
            except Exception:
              sec_num_v = 50.0
            if (
                cvi_r == 65
                and sec_num_v <= 1.5
                and len(agendas_lookup_dict) >= 3
            ):
              sec_num_v = max(sec_num_v, float(len(agendas_lookup_dict) - 1))
            return (10, sec_num_v, cvi_r, idx_v)
          return (10, 50.0, cvi_r, idx_v)

        v_sorted = [
            p[1]
            for p in sorted(
                list(enumerate(v_slides)),
                key=_post_stage2_sort_key,
            )
        ]
        orig_v_ids = [s.get("objectId") for s in v_slides if s.get("objectId")]
        new_v_ids = [s.get("objectId") for s in v_sorted if s.get("objectId")]
        if len(new_v_ids) == len(orig_v_ids) and new_v_ids != orig_v_ids:
          v_reorders = [
              {
                  "updateSlidesPosition": {
                      "slideObjectIds": [sid],
                      "insertionIndex": 0,
                  }
              }
              for sid in reversed(new_v_ids)
          ]
          requests.post(
              f"https://slides.googleapis.com/v1/presentations/{presentation_id}:batchUpdate",
              headers=headers,
              json={"requests": v_reorders},
              timeout=30,
          )
          print(
              "[PitchGenSkills] Applied post-Stage-2 CVI monotonic order"
              f" verification ({len(v_reorders)} slides) to"
              f" {presentation_id}!"
          )
  except Exception as v_err:
    print(f"[PitchGenSkills] Post-Stage-2 CVI verification warning: {v_err}")

  return formatted_title


def _resolve_live_reusable_slide_ids(
    reusable_slides: dict | None,
    user_ldap: str = "",
    user_oauth_token: str = "",
    agendas: dict | None = None,
    context: dict | None = None,
) -> dict:
  """Verifies each reusable slide's slide_id against the live Google Slides presentation and resolves refreshed objectIds by matching slide text, speaker notes, and core topics."""
  if not isinstance(reusable_slides, dict) or not reusable_slides:
    return reusable_slides or {}

  clean_ldap = (
      user_ldap.split("@")[0].lower().strip() if user_ldap else "seller_user"
  )
  cand_tokens = _build_apps_script_candidate_tokens(
      clean_ldap=clean_ldap, user_oauth_token=user_oauth_token
  )
  if not cand_tokens:
    return reusable_slides

  # Collect unique source deck IDs
  deck_ids = set()
  for sec_data in reusable_slides.values():
    if not isinstance(sec_data, dict):
      continue
    for sug in sec_data.get("suggestions", []) or []:
      if not isinstance(sug, dict):
        continue
      d_id = sug.get("deck_id") or sug.get("deckId")
      if not d_id and sug.get("values"):
        m_d = re.search(
            r"/presentation/d/([a-zA-Z0-9_-]+)", str(sug["values"][0])
        )
        if m_d:
          d_id = m_d.group(1)
          sug["deck_id"] = d_id
      if d_id:
        deck_ids.add(d_id)

  if not deck_ids:
    return reusable_slides

  stop_words = {
      "the",
      "and",
      "for",
      "with",
      "from",
      "that",
      "this",
      "your",
      "slide",
      "presents",
      "illustrates",
      "overview",
      "google",
      "cloud",
      "enterprise",
      "how",
      "can",
      "into",
      "across",
      "using",
      "provides",
      "outlines",
      "shows",
  }

  from pitchgen_utils.image_util import _element_bbox_pt

  def _flatten_live_elems(elems: list) -> list:
    out = []
    for el_item in elems or []:
      if not isinstance(el_item, dict):
        continue
      grp = el_item.get("elementGroup")
      if isinstance(grp, dict) and grp.get("children"):
        out.extend(_flatten_live_elems(grp.get("children", [])))
      else:
        out.append(el_item)
    return out

  deck_live_cache = {}
  for d_id in deck_ids:
    pres_json = None
    for _, tok in cand_tokens:
      if not tok:
        continue
      try:
        r = requests.get(
            f"https://slides.googleapis.com/v1/presentations/{d_id}",
            headers={"Authorization": f"Bearer {tok}"},
            timeout=20,
        )
        if r.status_code == 200:
          pres_json = r.json()
          break
      except Exception:
        continue
    if not pres_json:
      continue

    raw_slides = pres_json.get("slides", [])
    live_id_set = {s.get("objectId") for s in raw_slides if s.get("objectId")}
    candidates = []
    for idx, ls in enumerate(raw_slides):
      oid = ls.get("objectId")
      if not oid:
        continue
      texts = []
      visual_count = 0
      off_canvas_shapes = 0
      for el in _flatten_live_elems(ls.get("pageElements", [])):
        ex_pt, ey_pt, ew_pt, eh_pt, _ = _element_bbox_pt(el)
        if (ew_pt > 0 or eh_pt > 0) and (
            ey_pt >= 402.0
            or ex_pt >= 718.0
            or (ey_pt + eh_pt) <= 2.0
            or (ex_pt + ew_pt) <= 2.0
        ):
          if "shape" in el:
            off_canvas_shapes += 1
          continue
        if (
            "image" in el
            or "table" in el
            or "elementGroup" in el
            or "video" in el
        ):
          visual_count += 1
        for te in el.get("shape", {}).get("text", {}).get("textElements", []):
          c = te.get("textRun", {}).get("content", "").strip()
          if c:
            texts.append(c)
        for row in el.get("table", {}).get("tableRows", []):
          for cell in row.get("tableCells", []):
            for te in cell.get("text", {}).get("textElements", []):
              c = te.get("textRun", {}).get("content", "").strip()
              if c:
                texts.append(c)
      notes_parts = []
      for el in (
          ls.get("slideProperties", {})
          .get("notesPage", {})
          .get("pageElements", [])
      ):
        for te in el.get("shape", {}).get("text", {}).get("textElements", []):
          c = te.get("textRun", {}).get("content", "").strip()
          if c:
            notes_parts.append(c)
      text_str = " ".join(texts)
      notes_str = " ".join(notes_parts)
      comb_low = f"{text_str} {notes_str}".lower()
      text_low = text_str.lower()

      # Disqualify unfinished/broken slides that have >= 3 off-canvas scratch shapes and sparse on-canvas text (e.g. g3d3ec39e5d1_0_17561)
      if off_canvas_shapes >= 3 and len(text_str) < 160:
        live_id_set.discard(oid)
        continue

      # Filter out internal context / cover / thank you / divider slides
      if idx == 0 and any(
          k in comb_low
          for k in (
              "internal context",
              "nda only",
              "do not distribute",
              "before you present",
          )
      ):
        continue
      if idx <= 1 and len(text_str) < 120:
        continue
      if (
          any(
              k in text_low
              for k in ("thank you", "questions?", "q & a", "appendix")
          )
          and len(text_str) < 80
      ):
        continue
      if len(text_str) < 40 and visual_count == 0:
        continue

      is_live_cust_ref = oid.startswith("g3d82a1a6d9f_3536_") or any(
          k in comb_low
          for k in (
              "customer_reference_library",
              "https://your-sales-portal.example.com/customer-references",
              "exec summary:",
              "customer reference slide",
              "customer success slide",
          )
      )
      tokens = {
          w
          for w in re.findall(r"[a-z0-9]{3,}", comb_low)
          if w not in stop_words
      }
      candidates.append({
          "idx": idx,
          "id": oid,
          "text": text_str,
          "notes": notes_str,
          "comb_low": comb_low,
          "tokens": tokens,
          "is_cust_ref": is_live_cust_ref,
      })

    deck_live_cache[d_id] = {
        "live_id_set": live_id_set,
        "candidates": candidates,
        "used_ids": set(),
    }

  def _sec_order_key(k: str) -> float:
    try:
      return float(k)
    except Exception:
      return 999.0

  global_used_live_token_sets: list[set[str]] = []

  def _is_live_text_duplicate(cand_toks: set[str]) -> bool:
    if not cand_toks or len(cand_toks) < 4:
      return False
    for prev_toks in global_used_live_token_sets:
      if not prev_toks:
        continue
      overlap = len(cand_toks & prev_toks) / max(
          1, min(len(cand_toks), len(prev_toks))
      )
      if overlap >= 0.78:
        return True
    return False

  # Resolve any stale slide_id (and deduplicate cross-deck identical slides) in section order
  for sec_key in sorted(reusable_slides.keys(), key=_sec_order_key):
    sec_data = reusable_slides.get(sec_key)
    if not isinstance(sec_data, dict):
      continue
    kept_sugs = []
    for sug in sec_data.get("suggestions", []) or []:
      if not isinstance(sug, dict):
        continue
      d_id = sug.get("deck_id") or sug.get("deckId")
      s_id = sug.get("slide_id") or sug.get("slideId")
      if not d_id or d_id not in deck_live_cache:
        kept_sugs.append(sug)
        continue
      cache_entry = deck_live_cache[d_id]

      # If s_id already exists in the live deck, check whether its live text is a cross-deck duplicate
      if (
          s_id in cache_entry["live_id_set"]
          and s_id not in cache_entry["used_ids"]
      ):
        live_cand = next(
            (c for c in cache_entry["candidates"] if c["id"] == s_id), None
        )
        if live_cand and not _is_live_text_duplicate(live_cand["tokens"]):
          cache_entry["used_ids"].add(s_id)
          global_used_live_token_sets.append(live_cand["tokens"])
          sug["_live_idx"] = live_cand["idx"]
          sug["_live_text"] = live_cand["text"]
          sug["_live_notes"] = live_cand["notes"]
          sug["_live_is_cust_ref"] = live_cand["is_cust_ref"]
          kept_sugs.append(sug)
          continue

      is_sug_cr = (
          sug.get("_source_datastore_key")
          in ("cust_ref", "customer_references", "case_studies")
          or sug.get("is_cust_ref")
          or sug.get("is_proof_point")
          or sug.get("slide_job") == "Proof_Points"
      )
      sug_notes = str(sug.get("speaker_notes") or "").strip().lower()
      sug_topics = [
          str(t).strip().lower()
          for t in sug.get("core_topics") or []
          if str(t).strip()
      ]
      sug_comb = (
          f"{sug.get('name', '')} {sug.get('original_title', '')}"
          f" {sug.get('original_content', '')} {sug_notes}"
          f" {' '.join(sug_topics)}"
      ).lower()
      sug_tokens = {
          w
          for w in re.findall(r"[a-z0-9]{3,}", sug_comb)
          if w not in stop_words
      }

      best_cand = None
      best_score = -1.0
      for cand in cache_entry["candidates"]:
        if cand["id"] in cache_entry["used_ids"]:
          continue
        if not is_sug_cr and cand["is_cust_ref"]:
          continue
        if _is_live_text_duplicate(cand["tokens"]):
          continue
        score = 2.0 * len(sug_tokens & cand["tokens"])
        for top in sug_topics:
          if len(top) >= 3 and top in cand["comb_low"]:
            score += 5.0
        if len(sug_notes) >= 35 and sug_notes[:45] in cand["notes"].lower():
          score += 25.0
        if score > best_score:
          best_score = score
          best_cand = cand

      if best_cand and best_score >= 10.0:
        new_sid = best_cand["id"]
        cache_entry["used_ids"].add(new_sid)
        global_used_live_token_sets.append(best_cand["tokens"])
        sug["slide_id"] = new_sid
        sug["values"] = [
            f"https://docs.google.com/presentation/d/{d_id}/edit?#slide=id.{new_sid}"
        ]
        if best_cand.get("text"):
          sug["original_content"] = best_cand["text"]
        if best_cand.get("notes"):
          sug["speaker_notes"] = best_cand["notes"]
        sug["_live_idx"] = best_cand["idx"]
        sug["_live_text"] = best_cand["text"]
        sug["_live_notes"] = best_cand["notes"]
        sug["_live_is_cust_ref"] = best_cand["is_cust_ref"]
        kept_sugs.append(sug)
        print(
            f"[PitchGenSkills] Resolved refreshed slide_id in deck '{d_id}':"
            f" '{s_id}' -> '{new_sid}' (score={best_score:.1f},"
            f" slide='{best_cand['text'][:65]}')"
        )
      else:
        print(
            "[PitchGenSkills] Dropped duplicate or unresolved slide_id"
            f" '{s_id}' in deck '{d_id}' (best_score={best_score:.1f})"
        )
    sec_data["suggestions"] = kept_sugs

  # Enforce Live CVI Framework Routing & Progression Order across all sections before deck assembly
  ordered_sec_keys = [
      k
      for k in sorted(reusable_slides.keys(), key=_sec_order_key)
      if isinstance(reusable_slides.get(k), dict)
  ]
  if len(ordered_sec_keys) >= 2:
    agendas_dict = agendas if isinstance(agendas, dict) else {}
    req_strategy = (
        str((context or {}).get("deck_strategy") or "").lower().strip()
    )
    is_smart_hybrid = req_strategy in ("", "smart_hybrid")
    is_s0_smart_hybrid = is_smart_hybrid and (
        bool((context or {}).get("is_s0_customer_discovery"))
        or str(
            (context or {}).get("win_cycle")
            or (context or {}).get("sales_stage")
            or ""
        )
        .strip()
        .upper()
        == "S0"
    )
    bespoke_reserved_sec_keys: set[str] = set()
    if is_smart_hybrid:
      for sk in ordered_sec_keys:
        a_obj = (
            agendas_dict.get(sk)
            if isinstance(agendas_dict.get(sk), dict)
            else {}
        )
        t_low = str(a_obj.get("title", "")).lower()
        t_comb = (
            f"{t_low}"
            f" {' '.join(str(p) for p in (a_obj.get('parts') or []))}".lower()
        )
        is_proof_sec = any(
            kw in t_low
            for kw in (
                "customer success",
                "case stud",
                "proof point",
                "customer reference",
                "peer outcome",
            )
        )
        if not is_proof_sec and (
            bool(a_obj.get("bespoke_research_focus"))
            or any(
                kw in t_comb
                for kw in (
                    "discovery question",
                    "executive question",
                    "prioritized question",
                    "opportunity hypothes",
                    "opportunity matrix",
                    "technology footprint",
                    "tech footprint",
                    "current footprint",
                    "customer research",
                )
            )
        ):
          bespoke_reserved_sec_keys.add(sk)

    non_reserved_sec_keys = [
        sk for sk in ordered_sec_keys if sk not in bespoke_reserved_sec_keys
    ] or list(ordered_sec_keys)
    first_reusable_sec_key = non_reserved_sec_keys[0]

    # 1. Only recover a generic "11+ apps" Current_State slide when strategy is explicitly 'cloudhub' and Section 1 has no slides
    first_sec_sugs = (
        reusable_slides[first_reusable_sec_key].get("suggestions") or []
    )
    if (
        req_strategy == "cloudhub"
        and first_reusable_sec_key == ordered_sec_keys[0]
        and not first_sec_sugs
        and deck_live_cache
    ):
      for d_id, cache_entry in deck_live_cache.items():
        found_cs = None
        for cand in cache_entry["candidates"]:
          if cand["id"] in cache_entry["used_ids"] or cand["is_cust_ref"]:
            continue
          if _is_live_text_duplicate(cand["tokens"]):
            continue
          t_low = cand["text"].lower()
          if any(
              kw in t_low
              for kw in (
                  "11+ apps",
                  "application sprawl",
                  "fragmented",
                  "switching between",
                  "context switching",
                  "information overload",
                  "siloed",
              )
          ):
            found_cs = cand
            break
        if found_cs:
          cs_sid = found_cs["id"]
          cache_entry["used_ids"].add(cs_sid)
          global_used_live_token_sets.append(found_cs["tokens"])
          cs_sug = {
              "name": found_cs["text"][:80].strip(),
              "original_title": found_cs["text"].split("\n")[0][:80].strip(),
              "original_content": found_cs["text"],
              "speaker_notes": found_cs["notes"],
              "deck_id": d_id,
              "slide_id": cs_sid,
              "slide_job": "Current_State",
              "cvi_cluster": "Context",
              "values": [
                  f"https://docs.google.com/presentation/d/{d_id}/edit?#slide=id.{cs_sid}"
              ],
              "_live_idx": found_cs["idx"],
              "_live_text": found_cs["text"],
              "_live_notes": found_cs["notes"],
              "_live_is_cust_ref": False,
          }
          first_sec_sugs.append(cs_sug)
          reusable_slides[first_reusable_sec_key][
              "suggestions"
          ] = first_sec_sugs
          print(
              f"[PitchGenSkills] Recovered live Current_State slide '{cs_sid}'"
              f" from foundation deck '{d_id}' for Section"
              f" {first_reusable_sec_key}: '{found_cs['text'][:65]}'"
          )
          break

    # 2. Classify each resolved live slide into its true CVI Stage Rank using its actual live text
    def _compute_live_cvi_rank(sug_obj: dict) -> tuple[int, int]:
      l_text = str(
          sug_obj.get("_live_text")
          or sug_obj.get("original_content")
          or sug_obj.get("name")
          or ""
      ).lower()
      l_idx = int(sug_obj.get("_live_idx", 50))
      is_cr = bool(
          sug_obj.get("_live_is_cust_ref")
          or sug_obj.get("is_cust_ref")
          or sug_obj.get("is_proof_point")
      )

      # Stage 85: Realization — Next Steps / 3-Step Pilot Call to Action
      if any(
          kw in l_text
          for kw in (
              "waiting is no longer an option",
              "waiting is no  longer an option",
              "let's get started",
              "let’s get started",
              "identify a use case",
              "identify a high-impact use case",
              "launch a pilot",
              "scale with confidence",
          )
      ):
        return (85, l_idx)

      # Stage 75: Realization — Commercials / Edition Pricing & Packaging
      if any(
          kw in l_text
          for kw in (
              "edition pricing",
              "gemini enterprise edition",
              "how you consume is dependent",
              "pricing",
              "commercial model",
          )
      ):
        return (75, l_idx)

      # Stage 65: 04c Business Value & Customer Proof Points
      if is_cr:
        return (65, l_idx)

      # Stage 10: 01 Current State / 02 Business Implication (Tool Sprawl & Fragmentation)
      if any(
          kw in l_text
          for kw in (
              "11+ apps",
              "application sprawl",
              "switching between",
              "context switching",
              "information overload",
              "this limits the potential",
              "siloed",
              "disconnected",
          )
      ):
        return (10, l_idx)

      # Stage 20: 03 Future State / Vision (Shift from Passive AI to Agentic Transformation & High-Level Vision)
      if any(
          kw in l_text
          for kw in (
              "era of passive ai is over",
              "agentic transformation has arrived",
              "bring the best of google ai to every employee",
              "evolution of workplace",
              "shift from passive",
          )
      ):
        return (20, l_idx)

      # Stage 50-58: 04b Differentiation, Architecture, Security & Governance
      if any(
          kw in l_text
          for kw in (
              "trusted, resilient platform",
              "enterprise grade compliance",
              "security and sovereignty",
          )
      ):
        return (50, l_idx)
      if any(
          kw in l_text
          for kw in (
              "governance controls",
              "centralized control guarantees",
              "model armor",
              "prompt injection",
              "data loss prevention",
          )
      ):
        return (52, l_idx)
      if any(
          kw in l_text
          for kw in (
              "ai platform",
              "next step: schedule a technical deep dive",
              "only provider to offer first-party solutions",
              "research and frontier models",
              "agentic data cloud",
              "agentic d ata c loud",
              "agentic defense",
              "agentic d efense",
          )
      ):
        return (56, l_idx)

      # Stage 24: 03 Vision / 04a Bridge (Shared Context / Value Drivers)
      if l_idx <= 5 or any(
          kw in l_text
          for kw in (
              "shared context",
              "seamless integration",
              "unlocking",
          )
      ):
        return (24, l_idx)

      # Stage 32-42: 04a The Solution (Front Door, Orchestration, Pre-Built & Long-Running Agents, Flow of Work, Platform Capabilities)
      if any(
          kw in l_text
          for kw in (
              "one front door",
              "create and orchestrate agents",
              "bring ai into the flow of work",
              "pre-built google cloud agents",
              "deep research",
          )
      ):
        return (32, l_idx)
      if any(
          kw in l_text
          for kw in (
              "long-running agents",
              "individual productivity",
              "deal desk agent",
              "agent designer",
              "applications and solutions",
              "agentic canvas",
          )
      ):
        return (38, l_idx)

      return (35, l_idx)

    # Collect all resolved suggestions and route each to its matching CVI section
    n_secs = len(ordered_sec_keys)
    last_sec_obj = agendas_dict.get(ordered_sec_keys[-1]) if n_secs >= 1 else {}
    last_sec_title_low = (
        f"{(last_sec_obj or {}).get('title', '')}"
        f" {' '.join((last_sec_obj or {}).get('parts') or [])}".lower()
        if isinstance(last_sec_obj, dict)
        else ""
    )
    last_sec_wants_pricing = any(
        kw in last_sec_title_low
        for kw in ("pricing", "commercial", "licensing", "packaging", "edition")
    )
    last_sec_is_workshop_or_next_steps = any(
        kw in last_sec_title_low
        for kw in (
            "workshop",
            "next step",
            "roadmap",
            "charter",
            "sprint",
            "pilot",
            "action plan",
        )
    )

    all_resolved = []
    for sk in ordered_sec_keys:
      if sk in bespoke_reserved_sec_keys:
        continue
      for sug_obj in reusable_slides[sk].get("suggestions") or []:
        rank_tuple = _compute_live_cvi_rank(sug_obj)
        # Never inject Commercials / seat-pricing slides (stage 75) when S0 discovery or when closing agenda is a Workshop / Next Steps section
        if (
            rank_tuple[0] == 75
            and not last_sec_wants_pricing
            and (is_s0_smart_hybrid or last_sec_is_workshop_or_next_steps)
        ):
          continue
        # In smart_hybrid, filter out title-only "11+ apps" graphic slides that have no customizable body text
        if (
            is_smart_hybrid
            and rank_tuple[0] == 10
            and "11+ apps"
            in str(
                sug_obj.get("_live_text")
                or sug_obj.get("original_content")
                or ""
            ).lower()
        ):
          continue
        sug_obj["_live_cvi_rank"] = rank_tuple
        all_resolved.append((rank_tuple, sk, sug_obj))

    # Recover closing 3-step Path_to_Prod ("Let's get started") slide ONLY when closing section is NOT reserved for bespoke customer synthesis
    if (
        req_strategy != "bespoke_custom"
        and ordered_sec_keys[-1] not in bespoke_reserved_sec_keys
        and not any(r[0][0] >= 80 for r in all_resolved)
        and deck_live_cache
    ):
      for d_id, cache_entry in deck_live_cache.items():
        found_ptp = None
        for cand in cache_entry["candidates"]:
          if cand["id"] in cache_entry["used_ids"] or cand["is_cust_ref"]:
            continue
          if _is_live_text_duplicate(cand["tokens"]):
            continue
          t_low = cand["text"].lower()
          if any(
              kw in t_low
              for kw in (
                  "waiting is no longer an option",
                  "waiting is no  longer an option",
                  "let's get started",
                  "let’s get started",
                  "identify a use case",
                  "identify a high-impact use case",
                  "launch a pilot",
              )
          ):
            found_ptp = cand
            break
        if found_ptp:
          ptp_sid = found_ptp["id"]
          cache_entry["used_ids"].add(ptp_sid)
          global_used_live_token_sets.append(found_ptp["tokens"])
          ptp_rank = (85, found_ptp["idx"])
          ptp_sug = {
              "name": found_ptp["text"][:80].strip(),
              "original_title": found_ptp["text"].split("\n")[0][:80].strip(),
              "original_content": found_ptp["text"],
              "speaker_notes": found_ptp["notes"],
              "deck_id": d_id,
              "slide_id": ptp_sid,
              "slide_job": "Path_to_Prod",
              "cvi_cluster": "Realization",
              "values": [
                  f"https://docs.google.com/presentation/d/{d_id}/edit?#slide=id.{ptp_sid}"
              ],
              "_live_idx": found_ptp["idx"],
              "_live_text": found_ptp["text"],
              "_live_notes": found_ptp["notes"],
              "_live_is_cust_ref": False,
              "_live_cvi_rank": ptp_rank,
          }
          all_resolved.append((ptp_rank, non_reserved_sec_keys[-1], ptp_sug))
          print(
              f"[PitchGenSkills] Recovered live Path_to_Prod slide '{ptp_sid}'"
              f" from foundation deck '{d_id}' for closing section"
              f" {non_reserved_sec_keys[-1]}: '{found_ptp['text'][:65]}'"
          )
          break

    routed_by_sec = {sk: [] for sk in ordered_sec_keys}
    last_sec_has_cust_success = any(
        kw in last_sec_title_low
        for kw in (
            "customer success",
            "case stud",
            "proof point",
            "customer reference",
            "customer impact",
            "proven",
        )
    )

    for (cvi_stage, _), orig_sk, sug_obj in all_resolved:
      if cvi_stage >= 75:
        target_sk = non_reserved_sec_keys[-1]
      elif cvi_stage == 65:
        # Customer References / Proof_Points: keep in orig_sk if orig_sk is a Customer Success section (including Section 5),
        # otherwise route to penultimate non-reserved section if misplaced in Opening (0) or pure Closing Next Steps (-1)
        if orig_sk == ordered_sec_keys[0] and n_secs >= 3:
          target_sk = (
              ordered_sec_keys[-1]
              if last_sec_has_cust_success
              else ordered_sec_keys[max(1, n_secs - 2)]
          )
        elif (
            orig_sk == ordered_sec_keys[-1]
            and n_secs >= 3
            and not last_sec_has_cust_success
        ):
          target_sk = ordered_sec_keys[max(1, n_secs - 2)]
        else:
          target_sk = (
              orig_sk
              if orig_sk in routed_by_sec
              else (
                  ordered_sec_keys[-1]
                  if last_sec_has_cust_success
                  else ordered_sec_keys[max(0, n_secs - 2)]
              )
          )
      else:
        # Always preserve the Agenda section RetrievalAgent semantically matched (orig_sk) so slides match their Agenda section!
        target_sk = (
            orig_sk if orig_sk in routed_by_sec else first_reusable_sec_key
        )
      if target_sk in bespoke_reserved_sec_keys:
        target_sk = (
            non_reserved_sec_keys[max(0, len(non_reserved_sec_keys) - 2)]
            if cvi_stage >= 20 and len(non_reserved_sec_keys) >= 2
            else first_reusable_sec_key
        )
      routed_by_sec[target_sk].append(sug_obj)

    # Enforce per-section and deck-wide reusable slide budget when agendas specify slide_count
    # so a Standard (8-12 slides) deck never balloons to 20+ slides, while preserving overflow slides
    # if total resolved slides would otherwise fall below the deck's minimum slide count budget
    sec_budgets = {}
    for sk in ordered_sec_keys:
      if sk in bespoke_reserved_sec_keys:
        sec_budgets[sk] = 0
        continue
      a_obj = (
          agendas_dict.get(sk) if isinstance(agendas_dict.get(sk), dict) else {}
      )
      raw_sc = a_obj.get("slide_count") or a_obj.get("slides")
      if raw_sc is not None:
        try:
          sec_budgets[sk] = max(1, int(raw_sc))
        except Exception:
          pass
      # In S0 smart_hybrid mode, reserve 1 slot in the closing Workshop/Next Steps section for a bespoke Joint Discovery Workshop slide
      if (
          is_s0_smart_hybrid
          and sk == ordered_sec_keys[-1]
          and sec_budgets.get(sk, 0) >= 2
      ):
        sec_budgets[sk] = sec_budgets[sk] - 1

    total_budget = sum(sec_budgets.values()) if sec_budgets else 0
    total_routed = sum(len(routed_by_sec[sk]) for sk in ordered_sec_keys)
    overflow_pool = []

    for sk in ordered_sec_keys:
      sec_list = routed_by_sec[sk]
      sec_list.sort(key=lambda s: s.get("_live_cvi_rank", (50, 50)))
      if (
          sk in sec_budgets
          and len(sec_list) > sec_budgets[sk]
          and total_routed > total_budget
      ):
        cap_n = sec_budgets[sk]
        if cap_n <= 0:
          overflow_pool.extend((sk, s) for s in sec_list)
          sec_list = []
        else:
          # If this section has both a Customer Reference (65) and a Path_to_Prod (>=75), allow at most cap_n + 1 (max 3)
          has_cr_and_ptp = any(
              s.get("_live_cvi_rank", (50, 50))[0] == 65 for s in sec_list
          ) and any(
              s.get("_live_cvi_rank", (50, 50))[0] >= 75 for s in sec_list
          )
          eff_cap = min(len(sec_list), cap_n + (1 if has_cr_and_ptp else 0))
          # Preserve source-deck diversity (distinct sales plays/anchor decks) + CVI stage diversity when trimming
          if eff_cap < len(sec_list):
            if eff_cap == 1:
              kept = [sec_list[0]]
              overflow_pool.extend((sk, s) for s in sec_list[1:])
            else:
              kept = []
              kept_ids = set()
              seen_decks = set()
              # Pass 1: pick highest-ranked slide from each distinct source deck_id
              for s in sec_list:
                d_key = str(s.get("deck_id") or "")
                if d_key and d_key not in seen_decks and len(kept) < eff_cap:
                  seen_decks.add(d_key)
                  kept.append(s)
                  kept_ids.add(id(s))
              # Pass 2: if still under eff_cap, include last CVI stage (e.g. proof point / architecture) then fill in order
              if len(kept) < eff_cap and id(sec_list[-1]) not in kept_ids:
                kept.append(sec_list[-1])
                kept_ids.add(id(sec_list[-1]))
              for s in sec_list:
                if len(kept) >= eff_cap:
                  break
                if id(s) not in kept_ids:
                  kept.append(s)
                  kept_ids.add(id(s))
              kept.sort(key=lambda s: s.get("_live_cvi_rank", (50, 50)))
              overflow_pool.extend(
                  (sk, s) for s in sec_list if id(s) not in kept_ids
              )
            sec_list = kept
      routed_by_sec[sk] = sec_list

    # Multi-Sales-Play Anchor Guarantee: if per-section trimming (e.g. eff_cap=1) pushed a required solution_anchor deck into overflow_pool so it has 0 slides across routed_by_sec, restore 1 slide for that anchor deck
    req_sol_anchor_ids = [
        str(a.get("deck_id") or "").strip()
        for a in (context or {}).get("solution_anchors") or []
        if isinstance(a, dict) and str(a.get("deck_id") or "").strip()
    ]
    if len(req_sol_anchor_ids) > 1 and overflow_pool:
      represented_decks = {
          str(s.get("presentation_id") or "").strip()
          for sk_k in ordered_sec_keys
          for s in routed_by_sec.get(sk_k, [])
      }
      for req_d_id in req_sol_anchor_ids:
        if req_d_id not in represented_decks:
          for ov_idx, (ov_sk, ov_sug) in enumerate(overflow_pool):
            if str(ov_sug.get("presentation_id") or "").strip() == req_d_id:
              overflow_pool.pop(ov_idx)
              target_sk = (
                  first_reusable_sec_key
                  if ov_sk in bespoke_reserved_sec_keys
                  else ov_sk
              )
              routed_by_sec[target_sk].append(ov_sug)
              routed_by_sec[target_sk].sort(
                  key=lambda s: s.get("_live_cvi_rank", (50, 50))
              )
              represented_decks.add(req_d_id)
              break

    # If per-section trimming dropped total slides below total_budget in cloudhub mode (e.g. Comprehensive cloudhub needing >=14 content slides), restore from overflow_pool or deck_live_cache
    min_target_slides = (
        max(2, int(math.ceil(total_budget * 0.55)))
        if is_smart_hybrid
        else (max(14, total_budget) if total_budget >= 14 else total_budget)
    )
    cur_total_kept = sum(len(routed_by_sec[sk]) for sk in ordered_sec_keys)
    while cur_total_kept < min_target_slides and overflow_pool:
      ov_sk, ov_sug = overflow_pool.pop(0)
      if ov_sk in bespoke_reserved_sec_keys:
        ov_sk = first_reusable_sec_key
      routed_by_sec[ov_sk].append(ov_sug)
      cur_total_kept += 1

    if (
        cur_total_kept < min_target_slides
        and req_strategy in ("", "cloudhub")
        and deck_live_cache
        and ordered_sec_keys
    ):
      mid_sk = ordered_sec_keys[min(2, len(ordered_sec_keys) - 1)]
      for d_id, cache_entry in deck_live_cache.items():
        if cur_total_kept >= min_target_slides:
          break
        for cand in cache_entry["candidates"]:
          if cur_total_kept >= min_target_slides:
            break
          if cand["id"] in cache_entry["used_ids"]:
            continue
          if _is_live_text_duplicate(cand["tokens"]):
            continue
          cache_entry["used_ids"].add(cand["id"])
          global_used_live_token_sets.append(cand["tokens"])
          fill_sug = {
              "name": cand["text"][:80].strip(),
              "original_title": cand["text"].split("\n")[0][:80].strip(),
              "original_content": cand["text"],
              "speaker_notes": cand["notes"],
              "deck_id": d_id,
              "slide_id": cand["id"],
              "is_proof_point": cand["is_cust_ref"],
              "is_cust_ref": cand["is_cust_ref"],
              "values": [
                  f"https://docs.google.com/presentation/d/{d_id}/edit?#slide=id.{cand['id']}"
              ],
              "_live_idx": cand["idx"],
              "_live_text": cand["text"],
              "_live_notes": cand["notes"],
              "_live_is_cust_ref": cand["is_cust_ref"],
          }
          fill_sug["_live_cvi_rank"] = _compute_live_cvi_rank(fill_sug)
          routed_by_sec[mid_sk].append(fill_sug)
          cur_total_kept += 1

    for sk in ordered_sec_keys:
      sec_list = routed_by_sec[sk]
      sec_list.sort(key=lambda s: s.get("_live_cvi_rank", (50, 50)))
      for s in sec_list:
        s.pop("_live_idx", None)
        s.pop("_live_text", None)
        s.pop("_live_notes", None)
        s.pop("_live_is_cust_ref", None)
        s.pop("_live_cvi_rank", None)
      reusable_slides[sk]["suggestions"] = sec_list

  return reusable_slides


def call_apps_script_to_create_deck(
    outputs_gcs_url: str,
    architectural_gcs_url: str,
    user_ldap: str,
    user_oauth_token: str = None,
    outputs_data: dict | None = None,
    reusable_slides: dict | None = None,
    tool_context=None,
) -> str:
  """Calls the Google Apps Script Web App using AuthPreservingSession and the 4-tier token waterfall, then runs post_process_assembled_presentation and shares the deck with user_ldap@example.com."""
  from oauth_helper import get_authorization_url

  clean_ldap = user_ldap.split("@")[0].lower().strip() if user_ldap else ""
  if clean_ldap in ("unknown", "unknown_user", "user", "none"):
    clean_ldap = ""

  candidate_tokens = _build_apps_script_candidate_tokens(
      clean_ldap=clean_ldap,
      user_oauth_token=user_oauth_token,
      tool_context=tool_context,
  )

  # 2. If still no token at all, prompt user to authorize in chat
  if not candidate_tokens:
    try:
      auth_url = get_authorization_url(clean_ldap or "unknown")
    except Exception as e:
      print(
          f"[PitchGenSkills] Warning: Could not get authorization URL: {e}",
          flush=True,
      )
      auth_url = ""
    print(
        f"[PitchGenSkills] User {clean_ldap} is unauthorized and no service"
        " token available. Returning login URL.",
        flush=True,
    )
    if auth_url:
      return (
          f"Please authorize PitchGen to create presentations in your Google Drive by clicking this link: {auth_url}\n\n"
          "Once authorized, simply say 'continue' or 'generate deck' to create your presentation."
      )
    return ""

  # 3. Invoke Apps Script POST via AuthPreservingSession (preserves Authorization across 302 redirect)
  config = None
  try:
    config = load_config()
    url = config.get(
        "default",
        "render_api_url",
        fallback="https://script.google.com/macros/s/YOUR_APPS_SCRIPT_DEPLOYMENT_ID/exec",
    )
  except Exception:
    url = "https://script.google.com/macros/s/YOUR_APPS_SCRIPT_DEPLOYMENT_ID/exec"

  candidate_urls = []
  for u in [
      "https://script.google.com/macros/s/YOUR_APPS_SCRIPT_DEPLOYMENT_ID/exec",
      url,
      "https://script.google.com/macros/s/YOUR_APPS_SCRIPT_DEPLOYMENT_ID/exec",
  ]:
    if u and u not in candidate_urls:
      candidate_urls.append(u)

  # Deduplicate candidate_tokens by actual token value so user_short_lived and user_gcs
  # never make duplicate calls with the identical OAuth access token.
  deduped_tokens = []
  seen_token_vals = set()
  for t_src, t_val in candidate_tokens:
    if t_val and t_val not in seen_token_vals:
      seen_token_vals.add(t_val)
      deduped_tokens.append((t_src, t_val))

  service_owner_ldap = os.environ.get("PITCHGEN_SERVICE_OWNER_LDAP", "seller_user")
  effective_ldap = clean_ldap or service_owner_ldap
  user_email = f"{effective_ldap}@example.com"
  ctx = (
      (outputs_data or {}).get("context")
      if isinstance((outputs_data or {}).get("context"), dict)
      else {}
  )

  payload = {
      "outputs_filename": outputs_gcs_url,
      "architectural_filename": architectural_gcs_url,
      "user_ldap": effective_ldap,
      "userEmail": user_email,
      "user_email": user_email,
      "customer_name": (
          (outputs_data or {}).get("customer_name")
          or ctx.get("customer_name")
          or ""
      ),
      "deck_theme": (outputs_data or {}).get("deck_theme") or "",
      "context": ctx,
      "skip_inline_transform": True,
  }

  last_error = ""
  for target_url in candidate_urls:
    for token_source, token in deduped_tokens:
      headers = {
          "Authorization": f"Bearer {token}",
          "Content-Type": "application/json",
      }
      try:
        print(
            f"[PitchGenSkills] Executing Apps Script POST call to URL {target_url} for"
            f" user {effective_ldap} (auth={token_source})...",
            flush=True,
        )
        response = _post_with_auth_preserving_session(
            target_url, headers=headers, json_payload=payload, timeout=125
        )

        if (
            response.status_code == 200
            and not response.text.strip().startswith("<!DOCTYPE html>")
            and not response.text.strip().startswith("<html")
        ):
          print(
              "[PitchGenSkills] Success! Response from Apps Script"
              f" (auth={token_source}): {response.text[:300]}",
              flush=True,
          )
          final_deck_url = response.text.strip()
          try:
            resp_json = response.json()
            if (
                isinstance(resp_json, dict)
                and resp_json.get("error")
                and not resp_json.get("deckURL")
            ):
              last_error = (
                  f"Apps Script error ({token_source}): {resp_json.get('error')}"
              )
              print(f"[PitchGenSkills] Warning: {last_error}", flush=True)
              continue
            if isinstance(resp_json, dict) and "deckURL" in resp_json:
              raw_u = str(resp_json["deckURL"])
              m_id = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", raw_u)
              if m_id:
                final_deck_url = (
                    f"https://docs.google.com/presentation/d/{m_id.group(1)}/edit"
                )
              else:
                final_deck_url = raw_u
          except Exception as parse_err:
            print(
                "[PitchGenSkills] Warning: Failed to parse Apps Script response"
                f" as JSON: {parse_err}",
                flush=True,
            )

          # Extract presentation_id and run full UI Extension post-assembly parity pass + Drive sharing
          m_pres = re.search(r"/presentation/d/([a-zA-Z0-9_-]+)", final_deck_url)
          if m_pres:
            pres_id = m_pres.group(1)
            try:
              post_process_assembled_presentation(
                  presentation_id=pres_id,
                  token=token,
                  outputs_data=outputs_data,
                  reusable_slides=reusable_slides,
                  config=config,
                  user_ldap=effective_ldap,
              )
            except Exception as post_err:
              print(
                  "[PitchGenSkills] Warning: Post-assembly parity pass error:"
                  f" {post_err}",
                  flush=True,
              )

          return final_deck_url
        else:
          last_error = (
              f"Error {response.status_code} calling Apps Script"
              f" (auth={token_source}): {response.text[:200]}"
          )
          print(f"[PitchGenSkills] {last_error}", flush=True)
      except Exception as e:
        last_error = f"HTTP error calling Apps Script (auth={token_source}): {e}"
        print(f"[PitchGenSkills] {last_error}", flush=True)
        # If the Apps Script endpoint itself timed out (ReadTimeout), do NOT retry the same
        # slow endpoint with another token — immediately fall back to the next candidate_url!
        if "timed out" in str(e).lower() or "timeout" in str(e).lower():
          print(
              f"[PitchGenSkills] Endpoint {target_url} timed out; breaking"
              " token loop to try next endpoint immediately.",
              flush=True,
          )
          break

  return f"Error: {last_error}"


class PitchGenSkills:

  @staticmethod
  def submit_authorization_code(user_ldap: str, auth_code: str) -> str:
    """Exchange the user's pasted auth code for a refresh token and save it."""
    from oauth_helper import exchange_code_for_tokens
    import traceback
    try:
      exchange_code_for_tokens(user_ldap.strip(), auth_code.strip())
      return (
          "Success! You have successfully authorized the agent. Please try"
          " generating your presentation deck again."
      )
    except Exception as e:
      print(f"[PitchGenSkills] Token exchange failed for {user_ldap}:")
      traceback.print_exc()
      return f"Error: Authorization failed: {str(e)}"

  @staticmethod
  def create_proposal_outline(
      business_context: str,
      customer_name: str = "",
      industry: str = "",
      solution: str = "",
      user_ldap: str = "",
      user_oauth_token: str = "",
      er_number: str = "",
      audience: str = "",
      region: str = "",
      product: str = "",
      request_type: str = "",
      presentation_id: str = "",
      salesPlay: str = "",
      user_input_id: str = "",
      sub_industry: str = "",
      sales_stage: str = "",
      win_cycle: str = "",
      segment: str = "",
      deck_strategy: str = "smart_hybrid",
      tool_context=None,
      presentation_archetype: str = "",
  ) -> str:
    """Phase 1: Generates the initial outline and agendas based on customer context.

    Args:
        business_context: The business context or goal for the pitch.
        customer_name: The name of the target customer (e.g., 'Acme Corp').
        industry: The industry of the customer.
        solution: The proposed solutions or products, separated by commas.
        user_ldap: LDAP of the user.
        user_oauth_token: OAuth token passed by the platform context.
        er_number: Opportunity ER number.
        audience: Target audience list, comma separated.
        region: Target region.
        product: Specific Google products list, comma separated.
        request_type: Request type (e.g., 'Full Deck').
        presentation_id: Active Slides Presentation ID.
        salesPlay: Name of the Sales Play if applicable.
        user_input_id: Unique generated session ID.
        sub_industry: Sub-industry name if applicable.
        tool_context: ADK ToolContext object providing user credentials.

    Returns:
        A serialized GlobalState JSON string containing outline and agendas.
    """
    business_context_str = str(business_context).strip()
    if business_context_str.startswith("{"):
      return dispatch_payload(business_context_str)

    # Diagnostic dump and extraction from tool_context
    if tool_context is not None:
      print(f"[PitchGenSkills] tool_context type: {type(tool_context)}")
      try:
        session_email, resolved_ldap = extract_session_user_email_and_ldap(
            tool_context, fallback_ldap=user_ldap
        )
        if resolved_ldap:
          user_ldap = resolved_ldap
          try:
            from oauth_helper import get_user_access_token
            silent_token = get_user_access_token(user_ldap)
            if silent_token:
              user_oauth_token = silent_token
              print(
                  f"[PitchGenSkills] Successfully resolved silent access token"
                  f" from GCS for {user_ldap}"
              )
          except Exception as gcs_err:
            print(f"[PitchGenSkills] Warning: GCS silent token check: {gcs_err}")

        # Inspect InvocationContext & CredentialService
        try:
          inv_ctx = getattr(tool_context, "_invocation_context", None)
          if inv_ctx:
            cred_by_key = getattr(inv_ctx, "credential_by_key", {})
            if cred_by_key:
              for k, cred_val in cred_by_key.items():
                if hasattr(cred_val, "access_token") and cred_val.access_token:
                  user_oauth_token = cred_val.access_token
                  print(f"[PitchGenSkills] Resolved user_oauth_token from credential_by_key[{k}]!")
                  break
                elif hasattr(cred_val, "token") and cred_val.token:
                  user_oauth_token = cred_val.token
                  print(f"[PitchGenSkills] Resolved user_oauth_token from credential_by_key[{k}]!")
                  break
        except Exception as debug_err:
          print(f"[PitchGenSkills] INSPECT Error: {debug_err}")

        # Native ADK 2.0 SSO Credential Resolution (scanning v50 down to v1)
        try:
          from google.adk.auth.auth_handler import AuthConfig
          from fastapi.openapi.models import HTTPBearer
          dummy_scheme = HTTPBearer()
          config = load_config()
          project_number = config["company"].get("project_number", "000000000000")
          location = "us"
          auth_configs_to_try = [
              "pitchgen-sso-auth-v21",
              f"projects/{project_number}/locations/{location}/authorizations/pitchgen-sso-auth-v21",
          ]

          if hasattr(tool_context, "load_credential"):
            import inspect
            load_cred_fn = getattr(tool_context, "load_credential")
            for auth_path in auth_configs_to_try:
              try:
                auth_config_obj = AuthConfig(auth_scheme=dummy_scheme, credential_key=auth_path)
                if inspect.iscoroutinefunction(load_cred_fn):
                  import asyncio
                  try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                      cred = None
                    else:
                      cred = asyncio.run(load_cred_fn(auth_config_obj))
                  except Exception:
                    cred = None
                else:
                  cred = load_cred_fn(auth_config_obj)
                if cred:
                  print(f"[PitchGenSkills] Successfully loaded native credential via load_credential({auth_path})")
                  if hasattr(cred, "access_token") and cred.access_token:
                    user_oauth_token = cred.access_token
                    break
                  elif hasattr(cred, "token") and cred.token:
                    user_oauth_token = cred.token
                    break
              except Exception:
                pass

          # Do NOT call tool_context.request_credential() in Phase 1 (create_proposal_outline):
          # Phase 1 only uses Vertex AI Gemini, DiscoveryEngine, and GCS via ADC. Calling
          # request_credential() sets tool_context.actions.requested_auth_configs, which forces ADK
          # to abort the turn immediately after the tool call without running the model or A2UI callback.
        except Exception as auth_handler_err:
          print(f"[PitchGenSkills] Auth handler error: {auth_handler_err}")

        if user_oauth_token and user_ldap:
          from oauth_helper import cache_active_access_token
          cache_active_access_token(user_ldap, user_oauth_token)
      except Exception as e:
        print(f"[PitchGenSkills] Error reading tool_context: {e}")

    # Silently resolve user_ldap from Bearer token if present
    if user_oauth_token and user_oauth_token.strip() != "":
      from oauth_helper import get_email_from_bearer_token, cache_active_access_token
      resolved_email = get_email_from_bearer_token(user_oauth_token)
      if resolved_email:
        user_ldap = resolved_email.split("@")[0]
        print(
            f"[PitchGenSkills] Silently resolved user_ldap to '{user_ldap}' in Phase 1."
        )
        cache_active_access_token(user_ldap, user_oauth_token)

    print(
        "[PitchGenSkills] Generating outline for customer:"
        f" '{customer_name}'..."
    )
    config = load_config()

    if not user_input_id or user_input_id == "":
      user_input_id = str(uuid.uuid4())

    solution_list = (
        [s.strip() for s in solution.split(",") if s.strip()]
        if solution
        else []
    )

    from agents.skill_loader import split_sales_plays_safely

    sales_play_list = split_sales_plays_safely(salesPlay)

    raw_stage = str(win_cycle or sales_stage or "").strip().upper()
    canonical_win_cycle = "S1"
    if raw_stage in ["S0", "S1", "S2", "S3", "S4"]:
      canonical_win_cycle = raw_stage
    elif "S0" in raw_stage or "QUALIFY" in raw_stage:
      canonical_win_cycle = "S0"
    elif "S2" in raw_stage or "TECH" in raw_stage:
      canonical_win_cycle = "S2"
    elif "S3" in raw_stage or "PROPOSE" in raw_stage:
      canonical_win_cycle = "S3"
    elif "S4" in raw_stage or "MOBILIZE" in raw_stage:
      canonical_win_cycle = "S4"
    elif "S1" in raw_stage or "POSITION" in raw_stage:
      canonical_win_cycle = "S1"

    aud_list = (
        [
            a.strip()
            for a in re.split(r",\s*(?![^()]*\))", str(audience))
            if a.strip()
        ]
        if audience
        else []
    )
    resolved_segment = str(segment or "").strip()
    if not resolved_segment:
      for a in aud_list:
        a_low = str(a).strip().lower()
        if a_low in ["corporate", "smb", "startups", "enterprise", "strategic"]:
          resolved_segment = a_low.capitalize()
          break

    # Extract any existing customer research from previous outline state if refining
    existing_customer_research = ""
    try:
      if (
          tool_context
          and hasattr(tool_context, "state")
          and tool_context.state is not None
      ):
        prev_outline_str = tool_context.state.get("proposal_outline")
        if prev_outline_str and isinstance(prev_outline_str, str):
          prev_json = json.loads(prev_outline_str)
          prev_ctx = (prev_json.get("data", prev_json) or {}).get(
              "context", {}
          ) or {}
          prev_cust = str(prev_ctx.get("customer_name", "")).strip().lower()
          if (
              prev_cust
              and customer_name
              and prev_cust == customer_name.strip().lower()
          ):
            prev_res = prev_ctx.get("customer_research")
            if prev_res and isinstance(prev_res, str) and len(prev_res) >= 150:
              existing_customer_research = prev_res
    except Exception:
      pass

    initial_context = {
        "customer_name": customer_name,
        "business_context": business_context,
        "industry": industry,
        "sub_industry": sub_industry,
        "solution": solution_list,
        "visuals_requested": True,
        "customer_research": existing_customer_research,
        # Store DB fields in context so they propagate to Phase 2
        "user_ldap": user_ldap,
        "user_oauth_token": user_oauth_token,
        "er_number": er_number,
        "audience": aud_list,
        "region": (
            region
            if region and region not in ["S0", "S1", "S2", "S3", "S4"]
            else ""
        ),
        "sales_stage": canonical_win_cycle,
        "win_cycle": canonical_win_cycle,
        "segment": resolved_segment,
        "product": product.split(",") if product else [],
        "request_type": request_type,
        "deck_length": request_type or "Standard",
        "deck_strategy": deck_strategy or "smart_hybrid",
        "presentation_id": presentation_id,
        "salesPlay": sales_play_list,
        "user_input_id": user_input_id,
        "presentation_archetype": str(presentation_archetype or "").strip(),
    }

    try:
      state = GlobalState()
      state.context = initial_context
      agenda_agent = AgendaAgent(config)
      state = agenda_agent.run(state)

      # Generate GCS URL for outline
      bucket_name = config.get("bucket", "content")
      import datetime

      timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
      if er_number:
        filename_str = f"outline_{er_number}_{timestamp}.json"
      else:
        filename_str = f"outline_no_er_{user_input_id}_{timestamp}.json"
      gcs_url = f"gs://{bucket_name}/{filename_str}"

      # Write raw outline JSON to GCS
      try:
        from pitchgen_utils.gcs_util import write_gcs_file

        write_gcs_file(gcs_url, state.to_json())
        print(
            f"[PitchGenSkills] Successfully uploaded outline to GCS: {gcs_url}"
        )
      except Exception as gcse:
        print(
            f"[PitchGenSkills] Warning: Failed to upload outline to GCS: {gcse}"
        )

      # Wrap response in expected format
      state_dict = json.loads(state.to_json())
      state_dict["filename"] = gcs_url
      wrapped_response = {
          "Status": "True",
          "data": state_dict,
          "message": "Success",
      }
      return json.dumps(wrapped_response, indent=2)
    except Exception as e:
      import traceback
      print(f"[PitchGenSkills] Error in create_proposal_outline: {e}")
      traceback.print_exc()
      return json.dumps({"error": str(e)})

  @staticmethod
  def slide_generator_skill(
      state_json: str, client_source: str = "", credential = None, tool_context = None
  ) -> str:
    """Phase 2: Generates the final deck structure (content synthesis & slide mapping)

    based on the provided (and potentially refined) GlobalState.

    Args:
        state_json: Serialized GlobalState JSON string, containing potentially
          modified agendas.
        client_source: Optional source identifier (e.g. 'gemini_enterprise') to
          trigger UI rendering API.
        credential: Optional credential object.
        tool_context: ADK ToolContext object providing user credentials.

    Returns:
        A serialized GlobalState JSON string with final deck structure.
    """
    state_json_str = str(state_json).strip()
    if state_json_str.startswith("{"):
      try:
        payload = robust_json_loads(state_json_str)
        if (
            "context" not in payload
            and "agendas" not in payload
            and (
                "search_query" in payload
                or "user_inputs" in payload
                or "existing_slide_image_url" in payload
                or "business_context" in payload
            )
        ):
          return dispatch_payload(state_json_str)
      except Exception:
        pass

    context_user_ldap = None
    context_user_token = None

    # Extract native credentials from tool_context in Phase 2
    if tool_context is not None:
      print(f"[PitchGenSkills] [Phase 2] tool_context type: {type(tool_context)}")
      try:
        session_email, resolved_ldap = extract_session_user_email_and_ldap(
            tool_context
        )
        if resolved_ldap:
          context_user_ldap = resolved_ldap

        try:
          inv_ctx = getattr(tool_context, "_invocation_context", None)
          if inv_ctx:
            cred_by_key = getattr(inv_ctx, "credential_by_key", {})
            if cred_by_key:
              for k, cred_val in cred_by_key.items():
                if hasattr(cred_val, "access_token") and cred_val.access_token:
                  context_user_token = cred_val.access_token
                  print(f"[PitchGenSkills] [Phase 2] Resolved context_user_token from credential_by_key[{k}]!")
                  break
                elif hasattr(cred_val, "token") and cred_val.token:
                  context_user_token = cred_val.token
                  print(f"[PitchGenSkills] [Phase 2] Resolved context_user_token from credential_by_key[{k}]!")
                  break
        except Exception as debug_err:
          print(f"[PitchGenSkills] [Phase 2] INSPECT Error: {debug_err}")
      except Exception as e:
        print(f"[PitchGenSkills] [Phase 2] Error reading tool_context: {e}")

    print("[PitchGenSkills] Generating final deck from state...")
    config = load_config()

    try:
      state = GlobalState.from_json(state_json_str)
      retrieval_agent = RetrievalAgent(config)
      state = retrieval_agent.run(state)

      # --- 1. Silently resolve user_ldap and user_oauth_token BEFORE CreativeOrchestrator ---
      user_ldap = context_user_ldap or state.context.get("user_ldap", "")
      user_oauth_token = context_user_token or state.context.get(
          "user_oauth_token", ""
      )

      if not user_oauth_token and credential:
        if hasattr(credential, "http") and credential.http and hasattr(credential.http, "credentials"):
          user_oauth_token = getattr(credential.http.credentials, "token", "")
        elif hasattr(credential, "oauth2") and credential.oauth2:
          user_oauth_token = getattr(credential.oauth2, "access_token", "")

      if user_oauth_token and str(user_oauth_token).strip() != "":
        from oauth_helper import get_email_from_bearer_token, cache_active_access_token

        resolved_email = get_email_from_bearer_token(user_oauth_token)
        if resolved_email:
          user_ldap = resolved_email.split("@")[0]
          print(
              "[PitchGenSkills] Silently resolved user_ldap to"
              f" '{user_ldap}' from active session token.",
              flush=True,
          )
          state.context["user_ldap"] = user_ldap
          cache_active_access_token(user_ldap, user_oauth_token)

      if not user_ldap or not str(user_ldap).strip():
        raw_ldap = (
            os.environ.get("X-Goog-Authenticated-User-Email", "")
            or os.environ.get("X-Appengine-User-Email", "")
            or os.environ.get("USER", "")
            or os.environ.get("LOGNAME", "")
        )
        user_ldap = (
            raw_ldap.split("@")[0].strip()
            if "@" in raw_ldap
            else raw_ldap.strip()
        )
        state.context["user_ldap"] = user_ldap

      # If user_oauth_token is still missing in Phase 2, try to retrieve cached active token or refresh token from GCS
      if (not user_oauth_token or str(user_oauth_token).strip() == "") and user_ldap:
        try:
          from oauth_helper import get_cached_active_token, get_user_access_token
          cached_tok = get_cached_active_token(user_ldap)
          if cached_tok:
            user_oauth_token = cached_tok
            print(
                "[PitchGenSkills] Successfully retrieved cached active token"
                f" from GCS for {user_ldap}",
                flush=True,
            )
          else:
            ref_tok = get_user_access_token(user_ldap)
            if ref_tok:
              user_oauth_token = ref_tok
              print(
                  "[PitchGenSkills] Successfully retrieved token from GCS"
                  f" refresh token for {user_ldap}",
                  flush=True,
              )
        except Exception as gcs_tok_err:
          print(
              "[PitchGenSkills] Warning: Failed to retrieve cached token for"
              f" Phase 2: {gcs_tok_err}",
              flush=True,
          )

      # Verify, resolve, deduplicate, and CVI-route live reusable slide_ids BEFORE CreativeOrchestrator
      try:
        from agents.workflows.agenda_workflow import AgendaWorkflow

        if state.agendas and isinstance(state.context, dict):
          req_deck_len = str(
              state.context.get("deck_length")
              or state.context.get("request_type")
              or "Standard"
          )
          state.agendas = AgendaWorkflow.reconcile_agendas_with_deck_length(
              state.agendas, deck_length=req_deck_len
          )
        state.reusable_slides = _resolve_live_reusable_slide_ids(
            state.reusable_slides or {},
            user_ldap=user_ldap,
            user_oauth_token=user_oauth_token,
            agendas=state.agendas,
            context=state.context,
        )
      except Exception as res_err:
        print(
            "[PitchGenSkills] Warning: Live slide_id resolution error:"
            f" {res_err}",
            flush=True,
        )

      creative_orch = CreativeOrchestrator(config)
      try:
        final_state = creative_orch.run(state)
      except Exception as orch_err:  # pylint: disable=broad-exception-caught
        print(
            "[PitchGenSkills] Warning: CreativeOrchestrator encountered an"
            f" error ({orch_err}); assembling presentation from verified"
            " reusable and structural slides.",
            flush=True,
        )
        final_state = state
        if not getattr(final_state, "final_deck_structure", None):
          from agents.slide_engineering_agent import get_final_content
          from agents.workflows.outline_workflow import OutlineWorkflow

          class _FallbackTitleView:

            def __init__(self, t):
              self.title = t

          fb_title = OutlineWorkflow.normalize_modern_cover_title(
              (getattr(final_state, "outline", None) or {}).get("title", ""),
              customer_name=str(
                  (getattr(final_state, "context", None) or {}).get(
                      "customer_name", ""
                  )
              ),
          )
          fb_struct = get_final_content(
              item=_FallbackTitleView(fb_title),
              place_holders={},
              agendas=getattr(final_state, "agendas", {}) or {},
              reusable_slides=getattr(final_state, "reusable_slides", {}) or {},
              sources=getattr(final_state, "sources", {}) or {},
          )
          final_state.final_deck_structure = fb_struct.get("sections", {})

      # Generate GCS Filenames & URLs
      bucket_name = config.get("bucket", "content")
      import datetime

      timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
      er_number = final_state.context.get("er_number") or ""
      file_prefix = er_number or user_ldap or "pitchgen"

      outputs_filename = f"{file_prefix}_{timestamp}.json"
      architectural_filename = f"architectural_{file_prefix}_{timestamp}.json"

      gsurl_outputs = f"gs://{bucket_name}/{outputs_filename}"
      gsurl_architectural = f"gs://{bucket_name}/{architectural_filename}"

      # Prepare outputs_data structure for both GCS upload and post-assembly naming/transformation
      resolved_cust_name = (
          getattr(final_state, "customer_name", "")
          or (
              final_state.context.get("customer_name", "")
              if hasattr(final_state, "context") and final_state.context
              else ""
          )
      )
      resolved_ctx = getattr(final_state, "context", {}) or {}
      pre_resolved_logo_url = ""
      if resolved_cust_name and str(resolved_cust_name).strip().lower() not in (
          "the target customer",
          "the customer",
          "-",
          "none",
      ):
        try:
          from pitchgen_utils.logo_util import resolve_customer_logo
          pre_resolved_logo_url = resolve_customer_logo(
              str(resolved_cust_name).strip(),
              customer_info=str(resolved_ctx.get("customer_research") or ""),
              config=config,
          )
        except Exception as pre_logo_err:
          print(
              "[PitchGenSkills] Notice: Pre-upload customer logo resolution"
              f" skipped: {pre_logo_err}",
              flush=True,
          )

      outputs_data = {
          "sections": final_state.final_deck_structure or {},
          "customer_name": resolved_cust_name,
          "account_name": resolved_cust_name,
          "customer_logo_url": pre_resolved_logo_url,
          "deck_theme": (
              (getattr(final_state, "outline", None) or {}).get("title", "")
              or (getattr(final_state, "outline", None) or {}).get(
                  "deck_theme", ""
              )
          ),
          "context": resolved_ctx,
          "outline": getattr(final_state, "outline", {}) or {},
          "agendas": getattr(final_state, "agendas", {}) or {},
      }
      formatted_deck_title = format_pitchgen_deck_title(outputs_data)

      # Write files to GCS
      try:
        from pitchgen_utils.gcs_util import write_gcs_file

        # Upload architectural data (reusable slides suggestions)
        write_gcs_file(
            gsurl_architectural, json.dumps(final_state.reusable_slides or {})
        )
        # Upload outputs data (generated sections and metadata for UI presentation naming)
        write_gcs_file(gsurl_outputs, json.dumps(outputs_data))
        print(
            "[PitchGenSkills] Successfully uploaded architectural and outputs"
            " to GCS.",
            flush=True,
        )
      except Exception as gcse:
        print(
            "[PitchGenSkills] Warning: Failed to upload Phase 2 outputs to"
            f" GCS: {gcse}",
            flush=True,
        )

      deck_url = ""
      presentation_id = ""
      render_api_error = ""

      # Always invoke server-side Apps Script Web App for Gemini Enterprise chat requests
      # (call_apps_script_to_create_deck automatically falls back to the service owner token if the user lacks Apps Script/GCS ACLs)
      if client_source == "gemini_enterprise":
        deck_url = call_apps_script_to_create_deck(
            outputs_gcs_url=gsurl_outputs,
            architectural_gcs_url=gsurl_architectural,
            user_ldap=user_ldap,
            user_oauth_token=user_oauth_token,
            outputs_data=outputs_data,
            reusable_slides=final_state.reusable_slides or {},
        )

        exporter_url = os.environ.get("PITCHHUB_EXPORTER_URL")
        if exporter_url and (not deck_url or deck_url.startswith("Error")):
          import urllib.parse

          params = urllib.parse.urlencode({
              "outputs_filename": outputs_filename,
              "architectural_filename": architectural_filename,
              "customer_name": final_state.context.get("customer_name", ""),
              "er_number": er_number,
              "user_ldap": user_ldap,
          })
          deck_url = f"{exporter_url}/export?{params}"
          print(
              "[PitchGenSkills] Exporter URL configured. Returning deck_url:"
              f" {deck_url}"
          )

      if (
          deck_url
          and not str(deck_url).startswith("Please authorize")
          and not str(deck_url).startswith("Error")
      ):
        presentation_id = extract_presentation_id(str(deck_url), None)
        if (
            presentation_id
            and tool_context is not None
            and hasattr(tool_context, "state")
            and tool_context.state is not None
        ):
          try:
            tool_context.state["presentation_id"] = presentation_id
            tool_context.state["deck_url"] = (
                f"https://docs.google.com/presentation/d/{presentation_id}/edit"
            )
          except Exception:
            pass

      # Return the expected array format for Apps Script and UI clients
      wrapped_response = [
          {"architectural_filename": architectural_filename},
          {"outputs_filename": outputs_filename},
          {"agenda": 0},
          {"gsurl_architectural": gsurl_architectural},
          {"gsurl_outputs": gsurl_outputs},
          {"deck_title": formatted_deck_title},
      ]
      if deck_url and not str(deck_url).startswith("Please authorize") and not str(deck_url).startswith("Error"):
        wrapped_response.append({"deck_url": deck_url})
      if presentation_id:
        wrapped_response.append({"presentation_id": presentation_id})
      return json.dumps(wrapped_response, indent=2)
    except Exception as e:
      import traceback
      print(f"[PitchGenSkills] Error in slide_generator_skill: {e}")
      traceback.print_exc()
      return json.dumps({"error": str(e)})

  @staticmethod
  def consult_skill(skill_name: str) -> str:
    """Consults an authoritative PitchGen domain skill guideline to inform presentation creation and reasoning.

    Available skills include: 'cvi_framework', 'slide_job', 'sales_play_selection',
    'product_knowledge', 'slide_tone', 'executive_persona', 'win_cycle', 'google_brand',
    'speaker_notes', 'nano_banana_slide', 'segment_targeting', 'value_narrative_styling',
    'use_case_context', 'industry_verticals'.

    Args:
        skill_name: The name of the domain skill to load and inspect.

    Returns:
        JSON string containing the status and markdown instructions of the skill.
    """
    clean_name = str(skill_name).strip().lower().replace(" ", "_").replace("-", "_")
    from agents.skill_loader import load_skill_instructions

    instructions = load_skill_instructions(clean_name)
    if instructions:
      print(f"[PitchGenSkills] Consulted skill '{clean_name}'.")
      return json.dumps({
          "status": "success",
          "skill_name": clean_name,
          "instructions": instructions,
      }, indent=2)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    skills_dir = os.path.join(current_dir, "agents", "skills")
    available = []
    if os.path.exists(skills_dir):
      available = [
          d for d in os.listdir(skills_dir)
          if os.path.isdir(os.path.join(skills_dir, d))
      ]

    return json.dumps({
        "status": "not_found",
        "message": f"Skill '{skill_name}' not found.",
        "available_skills": sorted(available),
    }, indent=2)

  @staticmethod
  def enterprise_slide_generator_skill(
      state_json: str, tool_context=None
  ) -> str:
    """Phase 2 execution specifically for Gemini Enterprise.

    Generates final deck structure and triggers the UI-side rendering API
    to return a clickable Google Slides presentation link.
    """
    return PitchGenSkills.slide_generator_skill(
        state_json=state_json,
        client_source="gemini_enterprise",
        tool_context=tool_context,
    )

  @staticmethod
  def _resolve_active_presentation_and_context(
      presentation_url_or_id: str = "",
      tool_context=None,
  ) -> tuple[str, Dict[str, Any]]:
    """Resolves active presentation_id and account context from arguments, session state, or GCS workspace cache."""
    session_ctx: Dict[str, Any] = {}
    state_obj = (
        getattr(tool_context, "state", None)
        if tool_context is not None
        else None
    )
    if state_obj is not None and hasattr(state_obj, "get"):
      for k in (
          "presentation_id",
          "deck_url",
          "canvas_artifact",
          "customer_name",
          "industry",
          "salesPlay",
          "subPlay",
          "er_number",
          "customer_research",
          "latest_outline_state_json",
      ):
        val = state_obj.get(k)
        if val:
          session_ctx[k] = val
      raw_outline = session_ctx.get("latest_outline_state_json")
      if isinstance(raw_outline, str) and raw_outline.strip():
        try:
          parsed_outline = json.loads(raw_outline)
          if isinstance(parsed_outline, dict):
            inner_outline = parsed_outline.get("data", parsed_outline)
            ctx_outline = (
                inner_outline.get("context", inner_outline)
                if isinstance(inner_outline, dict)
                else {}
            )
            for k in (
                "customer_name",
                "industry",
                "salesPlay",
                "subPlay",
                "customer_research",
            ):
              if (
                  not session_ctx.get(k)
                  and isinstance(ctx_outline, dict)
                  and ctx_outline.get(k)
              ):
                session_ctx[k] = ctx_outline.get(k)
            if (
                not session_ctx.get("customer_research")
                and isinstance(inner_outline, dict)
                and inner_outline.get("customer_research")
            ):
              session_ctx["customer_research"] = inner_outline.get(
                  "customer_research"
              )
        except Exception:
          pass

    raw_arg = (presentation_url_or_id or "").strip()
    raw_lower = raw_arg.lower()
    explicit_active_keyword = raw_lower in (
        "active",
        "current",
        "current_deck",
        "active_deck",
        "this_deck",
        "canvas",
        "iframe",
    )
    if explicit_active_keyword or raw_lower in ("", "none", "null", "default"):
      raw_arg = ""

    pres_id = extract_presentation_id(raw_arg, None) if raw_arg else ""
    if not pres_id:
      for k in ("presentation_id", "deck_url", "canvas_artifact"):
        cand_val = str(session_ctx.get(k) or "").strip()
        if cand_val:
          pres_id = extract_presentation_id(cand_val, None)
          if pres_id:
            break
    if not pres_id and tool_context is not None:
      pres_id = extract_presentation_id("", tool_context)

    session_has_active_work = bool(
        pres_id
        or session_ctx.get("customer_name")
        or session_ctx.get("latest_outline_state_json")
        or (
            state_obj is not None
            and hasattr(state_obj, "get")
            and (
                state_obj.get("deck_generated")
                or state_obj.get("outline_generated")
                or state_obj.get("proposal_outline")
            )
        )
    )

    if (explicit_active_keyword or session_has_active_work) and (
        not pres_id or not session_ctx.get("customer_name")
    ):
      try:
        from google.cloud import storage

        cfg = load_config()
        b_name = cfg.get(
            "bucket", "content", fallback="your-pitchgen-content-bucket"
        )
        p_id = cfg.get("default", "project_name", fallback="your-gcp-project-id")
        client = storage.Client(project=p_id)
        blob = client.bucket(b_name).blob(
            "ge_sessions/_latest_workspace_state.json"
        )
        if blob.exists():
          ws_data = json.loads(blob.download_as_text())
          if isinstance(ws_data, dict):
            if not pres_id and ws_data.get("_latest_deck_id_"):
              pres_id = extract_presentation_id(
                  str(ws_data["_latest_deck_id_"]), None
              )
            if not session_ctx.get("customer_name") and ws_data.get(
                "_latest_customer_name_"
            ):
              session_ctx["customer_name"] = ws_data["_latest_customer_name_"]
            if not session_ctx.get("industry") and ws_data.get(
                "_latest_industry_"
            ):
              session_ctx["industry"] = ws_data["_latest_industry_"]
            if not session_ctx.get("salesPlay") and ws_data.get(
                "_latest_sales_play_"
            ):
              session_ctx["salesPlay"] = ws_data["_latest_sales_play_"]
      except Exception:
        pass

    if pres_id and state_obj is not None and hasattr(state_obj, "__setitem__"):
      try:
        state_obj["presentation_id"] = pres_id
        state_obj["deck_url"] = (
            f"https://docs.google.com/presentation/d/{pres_id}/edit"
        )
      except Exception:
        pass

    return pres_id, session_ctx

  @staticmethod
  def _transform_presentation_slides_via_rest_api(
      presentation_id: str,
      customization_criteria: str,
      target_slide_indices: str = "",
      customer_name: str = "",
      industry: str = "",
      audience: str = "",
      sales_play: str = "",
      target_language: str = "",
      customer_research: str = "",
      candidate_tokens: Optional[List[Tuple[str, str]]] = None,
  ) -> Dict[str, Any]:
    """Transforms or translates slide text shapes in-place via Google Slides REST API + TextTransformerWorkflow while preserving paragraph bullets, lead_style, and title geometry."""
    if not presentation_id or not candidate_tokens:
      return {"status": "skipped", "reason": "no_presentation_or_tokens"}

    import requests as req_lib
    from config_loader import load_config
    from agents.workflows.text_transformer_workflow import TextTransformerWorkflow
    from pitchgen_utils.image_util import _element_bbox_pt

    selected_indices: set[int] = set()
    raw_idx_str = (target_slide_indices or "").strip()
    if raw_idx_str and raw_idx_str.lower() not in (
        "all",
        "full_deck",
        "entire_deck",
        "*",
    ):
      for part in raw_idx_str.split(","):
        part = part.strip()
        if not part:
          continue
        if "-" in part:
          bounds = part.split("-", 1)
          if bounds[0].strip().isdigit() and bounds[1].strip().isdigit():
            for n in range(int(bounds[0].strip()), int(bounds[1].strip()) + 1):
              selected_indices.add(n)
        elif part.isdigit():
          selected_indices.add(int(part))

    working_token = ""
    pres_data = None
    for _, tok in candidate_tokens:
      if not tok:
        continue
      try:
        resp = req_lib.get(
            f"https://slides.googleapis.com/v1/presentations/{presentation_id}",
            headers={"Authorization": f"Bearer {tok}"},
            timeout=20,
        )
        if resp.status_code == 200:
          pres_data = resp.json()
          working_token = tok
          break
      except Exception:
        continue

    if not pres_data or not working_token:
      return {"status": "skipped", "reason": "slides_get_unavailable"}

    slides_list = pres_data.get("slides", [])
    slides_payload = []
    element_text_map: Dict[str, Dict[str, Any]] = {}
    notes_shape_map: Dict[str, Tuple[str, str]] = {}

    # Pre-extract slide titles across the full presentation so single-slide transforms
    # still receive accurate prev_slide_context, next_slide_context, and is_final_slide_in_deck
    slide_title_by_num: Dict[int, str] = {}
    for _i0, _sl_obj in enumerate(slides_list):
      _s_num = _i0 + 1
      _best_t = ""
      _best_fs = -1.0
      for _pe in _sl_obj.get("pageElements") or []:
        _sh = _pe.get("shape") or {}
        _tes = (_sh.get("text") or {}).get("textElements") or []
        _txt = "".join(
            (_te.get("textRun") or {}).get("content", "") for _te in _tes
        ).strip()
        if (
            not _txt
            or len(_txt) < 4
            or _txt == "Google Cloud"
            or "Proprietary & Confidential" in _txt
            or _txt.isdigit()
        ):
          continue
        _fs = 0.0
        for _te in _tes:
          _mag = (
              ((_te.get("textRun") or {}).get("style") or {}).get("fontSize")
              or {}
          ).get("magnitude")
          if _mag:
            _fs = float(_mag)
            break
        _p_type = str((_sh.get("placeholder") or {}).get("type") or "")
        if _p_type in ("TITLE", "CENTERED_TITLE") and _fs < 18.0:
          _fs = 24.0
        if _fs > _best_fs:
          _best_fs = _fs
          _best_t = _txt.split("\n")[0].strip()[:90]
      slide_title_by_num[_s_num] = _best_t or f"Slide {_s_num}"

    for idx_0, slide_obj in enumerate(slides_list):
      slide_num = idx_0 + 1
      if selected_indices and slide_num not in selected_indices:
        continue
      slide_id = slide_obj.get("objectId", f"slide_{slide_num}")

      # Extract speaker notes shape and text if present
      notes_page = (slide_obj.get("slideProperties") or {}).get(
          "notesPage"
      ) or {}
      notes_shape_id = (notes_page.get("notesProperties") or {}).get(
          "speakerNotesObjectId"
      ) or ""
      orig_notes = ""
      for n_pe in notes_page.get("pageElements") or []:
        n_id = n_pe.get("objectId", "")
        n_sh = n_pe.get("shape") or {}
        n_type = (n_sh.get("placeholder") or {}).get("type", "")
        if (notes_shape_id and n_id == notes_shape_id) or (
            not notes_shape_id and n_type == "BODY"
        ):
          if not notes_shape_id:
            notes_shape_id = n_id
          t_elems = (n_sh.get("text") or {}).get("textElements") or []
          orig_notes = "".join(
              (te.get("textRun") or {}).get("content", "") for te in t_elems
          ).strip()
          break
      if notes_shape_id:
        notes_shape_map[slide_id] = (notes_shape_id, orig_notes)

      # Flatten top-level and grouped pageElements and pre-compute bounding boxes + background card containers
      def _iter_slide_elements(pe_list):
        out = []
        for item in pe_list or []:
          if not isinstance(item, dict):
            continue
          grp = item.get("elementGroup")
          if isinstance(grp, dict) and grp.get("children"):
            out.extend(_iter_slide_elements(grp.get("children")))
          else:
            out.append(item)
        return out

      flat_page_elems = _iter_slide_elements(slide_obj.get("pageElements", []))
      slide_elem_bboxes = []
      slide_card_bg_bboxes = []
      for pe_box in flat_page_elems:
        pe_id = pe_box.get("objectId", "")
        if not pe_id:
          continue
        bx, by, bw, bh, _ = _element_bbox_pt(pe_box)
        # Ignore thin horizontal decorative divider lines (bh <= 14pt) so they don't clamp title clearance_pt
        if bw > 15.0 and bh > 14.0 and not (bw >= 680.0 and bh >= 360.0):
          slide_elem_bboxes.append((pe_id, bx, by, bw, bh))
          pe_sh = pe_box.get("shape") or {}
          pe_t_elems = (pe_sh.get("text") or {}).get("textElements") or []
          has_pe_text = any(
              (te.get("textRun") or {}).get("content", "").strip()
              for te in pe_t_elems
          )
          if (
              not has_pe_text
              and 80.0 <= bw <= 660.0
              and 65.0 <= bh <= 340.0
          ):
            slide_card_bg_bboxes.append((pe_id, bx, by, bw, bh))

      elements_for_workflow = []
      all_slide_texts = []
      for el in flat_page_elems:
        el_id = el.get("objectId", "")
        shape = el.get("shape") or {}
        text_content = shape.get("text") or {}
        text_elements = text_content.get("textElements") or []
        if not el_id or not text_elements:
          continue

        paragraphs_meta = []
        current_para_runs = []
        current_bullet_info = None
        first_bold = False
        first_font_weight = 400
        first_font_size = None
        shape_has_bullets = False

        for te in text_elements:
          if "paragraphMarker" in te:
            pm = te["paragraphMarker"]
            b_obj = pm.get("bullet")
            if b_obj:
              shape_has_bullets = True
              current_bullet_info = {
                  "has_bullet": True,
                  "glyph": str(b_obj.get("glyph") or ""),
                  "nesting_level": int(b_obj.get("nestingLevel") or 0),
              }
            else:
              current_bullet_info = {
                  "has_bullet": False,
                  "glyph": "",
                  "nesting_level": 0,
              }
          tr = te.get("textRun")
          if not tr:
            continue
          content_piece = tr.get("content", "")
          st = tr.get("style", {})
          current_para_runs.append((content_piece, st))
          if content_piece.endswith("\n"):
            p_raw = "".join(r[0] for r in current_para_runs)
            p_clean = p_raw.rstrip("\n")
            if p_clean.strip():
              non_ws_runs = [
                  (r_txt, r_st)
                  for r_txt, r_st in current_para_runs
                  if r_txt.strip()
              ]
              first_run_txt, first_run_st = (
                  non_ws_runs[0] if non_ws_runs else ("", {})
              )
              body_run_st = first_run_st
              lead_style = None
              lead_word_count = 0
              first_fs_mag = float(
                  (first_run_st.get("fontSize") or {}).get("magnitude") or 0.0
              )
              if len(non_ws_runs) >= 2 and (
                  first_fs_mag == 0.0 or first_fs_mag < 18.0
              ):
                second_run_st = non_ws_runs[1][1]
                first_wff = (first_run_st.get("weightedFontFamily") or {}).get(
                    "weight", 400
                )
                second_wff = (
                    second_run_st.get("weightedFontFamily") or {}
                ).get("weight", 400)
                first_is_heavy = (
                    bool(first_run_st.get("bold"))
                    or int(first_wff or 400) >= 500
                )
                second_is_heavy = (
                    bool(second_run_st.get("bold"))
                    or int(second_wff or 400) >= 500
                )
                first_fg = first_run_st.get("foregroundColor")
                second_fg = second_run_st.get("foregroundColor")
                if (first_is_heavy and not second_is_heavy) or (
                    first_fg and second_fg and first_fg != second_fg
                ):
                  lead_words = first_run_txt.strip().split()
                  if 1 <= len(lead_words) <= 5 and len(p_clean.split()) > len(
                      lead_words
                  ):
                    lead_style = first_run_st
                    lead_word_count = len(lead_words)
                    body_run_st = second_run_st
              p_style = {}
              for k_st in (
                  "fontSize",
                  "bold",
                  "italic",
                  "fontFamily",
                  "weightedFontFamily",
                  "foregroundColor",
              ):
                if k_st in body_run_st:
                  p_style[k_st] = body_run_st[k_st]
                elif k_st in first_run_st and k_st in (
                    "fontSize",
                    "fontFamily",
                ):
                  p_style[k_st] = first_run_st[k_st]
              p_wff_weight = int(
                  ((p_style.get("weightedFontFamily") or {}).get("weight") or 400)
              )
              if first_font_size is None and "fontSize" in p_style:
                first_font_size = p_style["fontSize"].get("magnitude")
                first_font_weight = p_wff_weight
                first_bold = bool(
                    p_style.get("bold", False) or first_font_weight >= 500
                )
              b_meta = current_bullet_info or {
                  "has_bullet": False,
                  "glyph": "",
                  "nesting_level": 0,
              }
              paragraphs_meta.append({
                  "text": p_clean,
                  "style": p_style,
                  "lead_style": lead_style,
                  "lead_word_count": lead_word_count,
                  "is_bold_header": bool(
                      (p_style.get("bold", False) or p_wff_weight >= 500)
                      and lead_style is None
                      and len(p_clean.strip()) <= 55
                  ),
                  "has_bullet": bool(b_meta.get("has_bullet")),
                  "bullet_glyph": str(b_meta.get("glyph") or ""),
              })
            current_para_runs = []
            current_bullet_info = None

        raw_text = "\n".join(p["text"] for p in paragraphs_meta).strip()
        if not raw_text or len(raw_text) < 3:
          continue
        if (
            raw_text == "Google Cloud"
            or "Proprietary & Confidential" in raw_text
            or re.match(r"^\d+$", raw_text)
        ):
          continue

        x_pt, y_pt, w_pt, h_pt, _ = _element_bbox_pt(el)
        placeholder_type = str(
            (shape.get("placeholder") or {}).get("type") or ""
        ).strip()
        if first_font_size is None and (
            placeholder_type in ("TITLE", "CENTERED_TITLE")
            or (y_pt < 95.0 and w_pt >= 350.0 and h_pt <= 85.0)
        ):
          first_font_size = 28.0
          if paragraphs_meta and not paragraphs_meta[0]["style"].get(
              "fontSize"
          ):
            paragraphs_meta[0]["style"]["fontSize"] = {
                "magnitude": 28,
                "unit": "PT",
            }

        eff_h_pt = h_pt
        clearance_pt = None
        if w_pt > 0 and h_pt > 0:
          min_dy = None
          for other_id, ox, oy, ow, oh in slide_elem_bboxes:
            if other_id == el_id or oy <= y_pt + 12.0:
              continue
            horiz_overlap = min(x_pt + w_pt, ox + ow) - max(x_pt, ox)
            if horiz_overlap >= 0.25 * min(w_pt, ow):
              dy = oy - y_pt
              if min_dy is None or dy < min_dy:
                min_dy = dy
          clearance_pt = min_dy
          orig_h_pt = eff_h_pt
          cx_mid = x_pt + w_pt / 2.0
          for _, cbx, cby, cbw, cbh in slide_card_bg_bboxes:
            if (
                cbx - 15.0 <= cx_mid <= cbx + cbw + 15.0
                and cby - 15.0 <= y_pt <= cby + cbh
            ):
              interior_card_h = max(0.0, (cby + cbh) - y_pt - 8.0)
              if interior_card_h > eff_h_pt:
                eff_h_pt = round(interior_card_h, 1)
          if (
              eff_h_pt <= orig_h_pt + 5.0
              and 55.0 <= y_pt <= 315.0
              and w_pt >= 95.0
          ):
            min_next_text_y = 352.0
            for pe_o in flat_page_elems:
              sh_o = pe_o.get("shape")
              if not sh_o:
                continue
              o_txt = "".join(
                  (te_o.get("textRun") or {}).get("content", "")
                  for te_o in (sh_o.get("text") or {}).get("textElements", [])
              ).strip()
              if (
                  not o_txt
                  or "proprietary & confidential" in o_txt.lower()
                  or o_txt.isdigit()
              ):
                continue
              ox, oy, ow, _ = _element_bbox_pt(pe_o)[:4]
              if abs(ox - x_pt) <= 5.0 and abs(oy - y_pt) <= 5.0:
                continue
              horiz_ov = min(x_pt + w_pt, ox + ow) - max(x_pt, ox)
              if horiz_ov >= 0.3 * min(w_pt, ow) and oy > y_pt + 18.0:
                if oy < min_next_text_y:
                  min_next_text_y = oy
            open_col_h = min(195.0, min_next_text_y - y_pt - 8.0)
            if open_col_h > eff_h_pt:
              eff_h_pt = round(open_col_h, 1)

        all_slide_texts.append(raw_text)
        shape_rep_font_size = first_font_size
        shape_rep_bold = first_bold
        if len(paragraphs_meta) > 1:
          body_para_fs = [
              float(p["style"]["fontSize"]["magnitude"])
              for p in paragraphs_meta[1:]
              if isinstance((p.get("style") or {}).get("fontSize"), dict)
              and p["style"]["fontSize"].get("magnitude")
          ]
          if body_para_fs:
            shape_rep_font_size = min(body_para_fs)
            shape_rep_bold = False
        elements_for_workflow.append({
            "shapeId": el_id,
            "elementId": el_id,
            "text": raw_text,
            "charCount": len(raw_text),
            "bold": shape_rep_bold,
            "fontWeight": first_font_weight,
            "fontSize": shape_rep_font_size,
            "x_pt": x_pt,
            "y_pt": y_pt,
            "width_pt": w_pt,
            "height_pt": eff_h_pt,
            "clearance_pt": clearance_pt,
            "has_bullets": shape_has_bullets,
            "placeholder_type": placeholder_type,
        })
        element_text_map[f"{slide_id}:{el_id}"] = {
            "raw_text": raw_text,
            "paragraphs": paragraphs_meta,
            "fontSize": shape_rep_font_size,
            "width_pt": w_pt,
            "height_pt": eff_h_pt,
            "clearance_pt": clearance_pt,
            "has_bullets": shape_has_bullets,
        }

      if elements_for_workflow:
        combined_lower = " ".join(all_slide_texts).lower()
        # When transforming the full deck (no explicit slide indices), skip Slide 0 internal summary, Agenda, and Thank You slides
        if not selected_indices and not target_language:
          if idx_0 == 0 and (
              "internal context" in combined_lower
              or "remove this slide" in combined_lower
          ):
            continue
          if idx_0 <= 2 and (
              "agenda" in combined_lower
              or "table of contents" in combined_lower
          ):
            continue
          if idx_0 >= len(slides_list) - 2 and (
              "thank you" in combined_lower or "questions" in combined_lower
          ):
            continue
        prev_ctx = (
            f"Slide {slide_num - 1} ({slide_title_by_num.get(slide_num - 1, '')})"
            if slide_num > 1
            else "Start of presentation"
        )
        next_ctx = (
            f"Slide {slide_num + 1} ({slide_title_by_num.get(slide_num + 1, '')})"
            if slide_num < len(slides_list)
            else "End of presentation (Executive Summary & Next Steps)"
        )
        slides_payload.append({
            "slideIndex": slide_num,
            "slideId": slide_id,
            "slideJob": "Solution_Overview",
            "is_reusable": True,
            "speaker_notes": orig_notes,
            "prev_slide_context": prev_ctx,
            "next_slide_context": next_ctx,
            "is_final_slide_in_deck": slide_num == len(slides_list),
            "data": elements_for_workflow,
            "elements": elements_for_workflow,
        })

    if not slides_payload:
      return {"status": "skipped", "reason": "no_text_elements_found"}

    config = load_config()
    workflow = TextTransformerWorkflow(config)
    effective_criteria = customization_criteria
    if target_language:
      effective_criteria = (
          f"Translate all slide text accurately into {target_language} while "
          "strictly preserving executive Google Cloud GTM tone, product names, "
          "metrics, and character length budgets."
      )
    transformed_slides = workflow.execute_deck_holistic(
        slides_list=slides_payload,
        criteria=effective_criteria,
        context={
            "customer_name": customer_name,
            "industry": industry,
            "audience": audience,
            "salesPlay": sales_play,
            "customer_research": customer_research,
        },
    )

    def _est_lines(text_str: str, width_pt: float | None, fs: float) -> int:
      if not text_str or not width_pt or float(width_pt) <= 0 or fs <= 0:
        return 1
      usable_w = max(60.0, float(width_pt) - 12.0)
      char_w = fs * 0.50
      total_l = 0
      for para in text_str.split("\n"):
        words = para.split()
        if not words:
          total_l += 1
          continue
        l_in_p = 1
        cur_w = 0.0
        for w in words:
          w_w = len(w) * char_w
          sp_w = char_w * 0.6 if cur_w > 0 else 0.0
          if cur_w > 0 and (cur_w + sp_w + w_w) > usable_w:
            l_in_p += 1
            cur_w = w_w
          else:
            cur_w += sp_w + w_w
        total_l += l_in_p
      return max(1, total_l)

    def _fit_title_fs(
        text_str: str,
        width_pt: float | None,
        clearance_pt: float | None,
        orig_fs: float,
    ) -> float:
      if not text_str or orig_fs < 20.0:
        return orig_fs
      if orig_fs >= 48.0:
        return 68.0
      w_val = float(width_pt) if (width_pt and float(width_pt) > 0) else 600.0
      c_val = (
          float(clearance_pt)
          if (clearance_pt and float(clearance_pt) > 0)
          else None
      )
      max_l = 4 if w_val < 300.0 else (3 if w_val < 460.0 else 2)
      for cand_fs in (orig_fs, 30.0, 28.0, 26.0, 24.0):
        if cand_fs > orig_fs:
          continue
        est_l = _est_lines(text_str, w_val, cand_fs)
        line_b = max_l if cand_fs > 24.0 else max(max_l, 3)
        fits_l = est_l <= line_b
        fits_c = (
            True
            if c_val is None
            else (est_l * cand_fs * 1.25 <= max(32.0, c_val - 6.0))
        )
        if fits_l and fits_c:
          return cand_fs
      return 24.0

    batch_requests = []
    modified_slides_count = 0
    modified_elements_count = 0

    for t_slide in transformed_slides or []:
      s_id = t_slide.get("slideId", "")
      slide_changed = False
      for el in t_slide.get("data") or t_slide.get("elements") or []:
        el_id = el.get("shapeId") or el.get("elementId") or ""
        new_text = (el.get("text") or "").strip()
        orig_info = element_text_map.get(f"{s_id}:{el_id}")
        if not el_id or not new_text or not orig_info:
          continue
        if new_text == orig_info["raw_text"]:
          continue
        slide_changed = True
        modified_elements_count += 1
        paras = list(orig_info.get("paragraphs") or [])
        sh_fs = float(orig_info.get("fontSize") or 12.0)
        sh_w_pt = orig_info.get("width_pt")
        sh_h_pt = orig_info.get("height_pt")
        sh_c_pt = orig_info.get("clearance_pt")

        if (
            len(paras) >= 2
            and paras[0].get("is_bold_header")
            and not paras[0].get("has_bullet")
            and "\n" not in new_text
        ):
          if ":" in new_text and len(new_text.split(":", 1)[0].strip()) <= 45:
            hdr_part, body_part = new_text.split(":", 1)
            if hdr_part.strip() and body_part.strip():
              new_text = f"{hdr_part.strip()}\n{body_part.strip()}"

        batch_requests.append(
            {
                "deleteText": {
                    "objectId": el_id,
                    "textRange": {"type": "ALL"},
                }
            }
        )
        batch_requests.append({
            "insertText": {
                "objectId": el_id,
                "insertionIndex": 0,
                "text": new_text,
            }
        })

        new_paras = new_text.split("\n")
        has_unbulleted_header = bool(
            paras
            and not paras[0].get("has_bullet")
            and any(p.get("has_bullet") for p in paras[1:])
        )
        char_offset = 0
        non_empty_p_idx = 0
        for p_i, p_str in enumerate(new_paras):
          p_len = len(p_str)
          if p_len > 0 and paras:
            if len(paras) > 1 and len(new_paras) == 1 and len(p_str) > 65:
              para_meta = paras[-1]
            else:
              para_meta = (
                  paras[non_empty_p_idx]
                  if non_empty_p_idx < len(paras)
                  else paras[-1]
              )
            non_empty_p_idx += 1
            if has_unbulleted_header and para_meta.get("has_bullet"):
              b_glyph = para_meta.get("bullet_glyph") or ""
              preset = (
                  "BULLET_ARROW_DIAMOND_DISC"
                  if b_glyph in ("➔", "➢", "➤", "→")
                  else "BULLET_DISC_CIRCLE_SQUARE"
              )
              batch_requests.append({
                  "createParagraphBullets": {
                      "objectId": el_id,
                      "textRange": {
                          "type": "FIXED_RANGE",
                          "startIndex": char_offset,
                          "endIndex": char_offset + p_len,
                      },
                      "bulletPreset": preset,
                  }
              })
            elif has_unbulleted_header and not para_meta.get("has_bullet"):
              batch_requests.append({
                  "updateParagraphStyle": {
                      "objectId": el_id,
                      "textRange": {
                          "type": "FIXED_RANGE",
                          "startIndex": char_offset,
                          "endIndex": char_offset + p_len,
                      },
                      "style": {
                          "indentStart": {"magnitude": 0, "unit": "PT"},
                          "indentFirstLine": {"magnitude": 0, "unit": "PT"},
                      },
                      "fields": "indentStart,indentFirstLine",
                  }
              })

            style_snap = para_meta.get("style") or {}
            style_update = {}
            fields = []
            fs_val = 0.0
            if style_snap.get("fontSize"):
              style_update["fontSize"] = style_snap["fontSize"]
              fields.append("fontSize")
              try:
                fs_val = float(style_snap["fontSize"].get("magnitude") or 0.0)
              except Exception:
                fs_val = 0.0
            elif p_i == 0 and sh_fs >= 20.0:
              fs_val = sh_fs
              style_update["fontSize"] = {"magnitude": sh_fs, "unit": "PT"}
              fields.append("fontSize")

            # Standardize spacious horizontal card body typography to 11.0pt so multi-card rows stay visually uniform
            if (
                len(new_paras) == 1
                and not orig_info.get("has_bullets")
                and float(sh_w_pt or 0.0) >= 220.0
                and float(sh_h_pt or 0.0) >= 48.0
                and 10.0 <= fs_val <= 12.5
                and len(p_str) >= 85
            ):
              fs_val = 11.0
              style_update["fontSize"] = {"magnitude": 11.0, "unit": "PT"}
              if "fontSize" not in fields:
                fields.append("fontSize")

            is_primary_slide_title = (
                p_i == 0
                and fs_val >= 18.0
                and len(new_paras) == 1
                and len(paras) <= 1
                and not orig_info.get("has_bullets")
            )
            if is_primary_slide_title and fs_val >= 20.0:
              fitted_fs = _fit_title_fs(p_str, sh_w_pt, sh_c_pt, fs_val)
              if fitted_fs != fs_val:
                fs_val = fitted_fs
                style_update["fontSize"] = {
                    "magnitude": fitted_fs,
                    "unit": "PT",
                }
                if "fontSize" not in fields:
                  fields.append("fontSize")

            if is_primary_slide_title:
              # Standardize primary slide titles to Google Sans Medium (weight 500, bold=False) to match Deck Generation 100%
              style_update["bold"] = False
              fields.append("bold")
              if style_snap.get("italic") is not None:
                style_update["italic"] = bool(style_snap["italic"])
                fields.append("italic")
              style_update["weightedFontFamily"] = {
                  "fontFamily": "Google Sans",
                  "weight": 500,
              }
              fields.append("weightedFontFamily")
            else:
              if style_snap.get("bold") is not None:
                style_update["bold"] = bool(style_snap["bold"])
                fields.append("bold")
              if style_snap.get("italic") is not None:
                style_update["italic"] = bool(style_snap["italic"])
                fields.append("italic")

              wff = style_snap.get("weightedFontFamily")
              ff = style_snap.get("fontFamily") or (
                  wff.get("fontFamily") if isinstance(wff, dict) else None
              )
              if isinstance(wff, dict) and wff.get("fontFamily"):
                style_update["weightedFontFamily"] = dict(wff)
                fields.append("weightedFontFamily")
              elif ff:
                style_update["fontFamily"] = ff
                fields.append("fontFamily")

            if style_snap.get("foregroundColor"):
              style_update["foregroundColor"] = style_snap["foregroundColor"]
              fields.append("foregroundColor")
            if fields:
              batch_requests.append({
                  "updateTextStyle": {
                      "objectId": el_id,
                      "textRange": {
                          "type": "FIXED_RANGE",
                          "startIndex": char_offset,
                          "endIndex": char_offset + p_len,
                      },
                      "style": style_update,
                      "fields": ",".join(fields),
                  }
              })

            lead_snap = para_meta.get("lead_style")
            lead_wc = int(para_meta.get("lead_word_count") or 0)
            if (
                not is_primary_slide_title
                and isinstance(lead_snap, dict)
                and lead_wc > 0
            ):
              p_words = p_str.split()
              if len(p_words) > lead_wc:
                lead_phrase = " ".join(p_words[:lead_wc])
                lead_len = len(lead_phrase)
                lead_upd = {}
                lead_flds = []
                if lead_snap.get("bold") is not None:
                  lead_upd["bold"] = bool(lead_snap["bold"])
                  lead_flds.append("bold")
                if lead_snap.get("weightedFontFamily"):
                  lead_upd["weightedFontFamily"] = lead_snap[
                      "weightedFontFamily"
                  ]
                  lead_flds.append("weightedFontFamily")
                if lead_snap.get("foregroundColor"):
                  lead_upd["foregroundColor"] = lead_snap["foregroundColor"]
                  lead_flds.append("foregroundColor")
                if lead_flds and 0 < lead_len < p_len:
                  batch_requests.append({
                      "updateTextStyle": {
                          "objectId": el_id,
                          "textRange": {
                              "type": "FIXED_RANGE",
                              "startIndex": char_offset,
                              "endIndex": char_offset + lead_len,
                          },
                          "style": lead_upd,
                          "fields": ",".join(lead_flds),
                      }
                  })
          char_offset += p_len + 1

      # Also update speaker notes on the transformed slide if new speaker notes were generated
      new_notes = str(t_slide.get("transformed_speaker_notes") or "").strip()
      t_hook = str(t_slide.get("transition_hook") or "").strip()
      notes_info = notes_shape_map.get(s_id)
      if new_notes and notes_info:
        n_sh_id, prev_notes = notes_info
        source_header = ""
        source_url = ""
        for prev_line in (prev_notes or "").split("\n"):
          if prev_line.strip().startswith("🔗 Source Slide:"):
            source_header = prev_line.strip()
            m_url = re.search(r"(https://docs\.google\.com/presentation/d/[^\s|]+)", source_header)
            if m_url:
              source_url = m_url.group(1)
            break
        final_notes_parts = []
        if source_header and "🔗 Source Slide:" not in new_notes:
          final_notes_parts.append(source_header)
        final_notes_parts.append(new_notes)
        if (
            t_hook
            and "Transition to next slide" not in new_notes
            and "Executive Takeaway" not in new_notes
        ):
          if t_hook.startswith(
              "🔗 Transition to next slide:"
          ) or t_hook.startswith("🎯 Executive Takeaway:"):
            final_notes_parts.append(t_hook)
          else:
            final_notes_parts.append(f"🔗 Transition to next slide: {t_hook}")
        final_notes_text = "\n\n".join(final_notes_parts).strip()
        if final_notes_text and final_notes_text != prev_notes:
          if prev_notes:
            batch_requests.append({
                "deleteText": {
                    "objectId": n_sh_id,
                    "textRange": {"type": "ALL"},
                }
            })
          batch_requests.append({
              "insertText": {
                  "objectId": n_sh_id,
                  "insertionIndex": 0,
                  "text": final_notes_text,
              }
          })
          if source_url and source_url in final_notes_text:
            url_start = final_notes_text.find(source_url)
            batch_requests.append({
                "updateTextStyle": {
                    "objectId": n_sh_id,
                    "textRange": {
                        "type": "FIXED_RANGE",
                        "startIndex": url_start,
                        "endIndex": url_start + len(source_url),
                    },
                    "style": {"link": {"url": source_url}},
                    "fields": "link",
                }
            })
          slide_changed = True

      if slide_changed:
        modified_slides_count += 1

    # Deterministic Cymbal white-label placeholder brand sweep across targeted non-reference slides
    clean_cust = str(customer_name or "").strip()
    target_page_ids = [
        str(
            ts.get("slideId") or ts.get("slide_id") or ts.get("id") or ""
        ).strip()
        for ts in transformed_slides
        if isinstance(ts, dict)
        and not bool(
            ts.get("is_proof_point")
            or ts.get("is_cust_ref")
            or ts.get("_source_datastore_key") == "cust_ref"
        )
        and str(
            ts.get("slideId") or ts.get("slide_id") or ts.get("id") or ""
        ).strip()
        in slide_obj_map
    ]
    if (
        clean_cust
        and clean_cust.lower()
        not in ("-", "none", "null", "cymbal", "the target enterprise")
        and target_page_ids
    ):
      cust_slug = re.sub(r"[^a-z0-9]", "", clean_cust.lower()) or "enterprise"
      for cym_bad, cym_good in (
          ("cymbal.com", f"{cust_slug}.com"),
          ("@cymbal", f"@{cust_slug}"),
          ("Cymbal Superstore", clean_cust),
          ("Cymbal Shops", clean_cust),
          ("Cymbal Direct", clean_cust),
          ("Cymbal FinTech", clean_cust),
          ("Cymbal's", f"{clean_cust}'s"),
          ("Cymbal’s", f"{clean_cust}’s"),
          ("Cymbal", clean_cust),
      ):
        batch_requests.append({
            "replaceAllText": {
                "pageObjectIds": target_page_ids,
                "containsText": {"text": cym_bad, "matchCase": False},
                "replaceText": cym_good,
            }
        })

    if not batch_requests:
      return {
          "status": "success",
          "slides_modified": 0,
          "elements_modified": 0,
      }

    upd_resp = req_lib.post(
        f"https://slides.googleapis.com/v1/presentations/{presentation_id}:batchUpdate",
        headers={
            "Authorization": f"Bearer {working_token}",
            "Content-Type": "application/json",
        },
        json={"requests": batch_requests},
        timeout=30,
    )
    if upd_resp.status_code == 200:
      return {
          "status": "success",
          "slides_modified": modified_slides_count,
          "elements_modified": modified_elements_count,
      }
    return {
        "status": "error",
        "http_status": upd_resp.status_code,
        "error": upd_resp.text[:300],
    }

  @staticmethod
  def enterprise_search_slides_skill(
      search_query: str,
      slide_job: str = "",
      strict_search: bool = False,
      tool_context=None,
  ) -> str:
    """Searches the PitchGen slide repository and customer reference library for reusable slides, customer proof points, case studies, and architecture diagrams.

    Args:
        search_query: Search query terms, customer names, products, or topics
          (e.g., 'Retail AI Case Studies', 'BigQuery Modernization', 'additional
          customer references').
        slide_job: Optional Slide Job ENUM filter to retrieve slides for a
          specific conversation intent (e.g., 'Architecture', 'Proof_Points',
          'Business_Value', 'Solution_Overview', 'Current_State',
          'Market_Trends', 'Strategic_Partnership', 'Why_Google_Cloud',
          'Commercials', 'Path_to_Prod').
        strict_search: Whether to perform strict tag/entity-based matching.
        tool_context: ADK ToolContext providing user identity and active session
          state.

    Returns:
        A serialized JSON string containing formatted search results with
        slide_job classifications, deck_id, slide_id, and view_url.
    """
    user_ldap = ""
    if tool_context is not None:
      _, user_ldap = extract_session_user_email_and_ldap(tool_context)

    active_pres_id, session_ctx = (
        PitchGenSkills._resolve_active_presentation_and_context(
            "", tool_context
        )
    )
    customer_name = str(session_ctx.get("customer_name") or "").strip()
    industry = str(session_ctx.get("industry") or "").strip()
    sales_play = str(session_ctx.get("salesPlay") or "").strip()

    raw_q = (search_query or "").strip()
    q_lower = raw_q.lower()
    is_customer_ref_query = str(slide_job).strip().lower() in (
        "proof_points",
        "proof points",
        "customer_references",
    ) or any(
        kw in q_lower
        for kw in (
            "customer reference",
            "customer story",
            "customer stories",
            "case stud",
            "proof point",
            "reference",
            "peer",
            "win story",
            "success story",
        )
    )

    effective_sidebar_query = raw_q
    if (
        not raw_q
        or q_lower
        in (
            "customer references",
            "additional customer references",
            "search for additional customer references",
            "more customer references",
            "case studies",
            "proof points",
        )
        or (
            is_customer_ref_query
            and len(raw_q.split()) <= 5
            and industry
            and industry.lower() not in q_lower
        )
    ):
      context_terms = [
          t
          for t in (industry, sales_play, "Customer Reference Case Study")
          if t
      ]
      if context_terms:
        effective_sidebar_query = f"{raw_q} {' '.join(context_terms)}".strip()

    print(
        f"[PitchGenSkills] Enterprise slide search for: '{raw_q}'"
        f" (effective='{effective_sidebar_query}', slide_job='{slide_job}',"
        f" customer='{customer_name}', industry='{industry}',"
        f" user={user_ldap})..."
    )
    try:
      from agents.sidebar_agent import SidebarAgent
      from agents.gtm_skills import GTMSkills

      try:
        import pitchgen_utils.a2ui_util as a2ui_util
      except Exception:
        try:
          from pitchgen_utils import a2ui_util
        except Exception:
          try:
            import src.pitchgen_utils.a2ui_util as a2ui_util
          except Exception:
            try:
              from ge import a2ui as a2ui_util
            except Exception:
              try:
                from src.ge import a2ui as a2ui_util
              except Exception:
                from ge import a2ui as a2ui_util

      config = load_config()
      formatted_slides: List[Dict[str, Any]] = []
      seen_keys: set[str] = set()

      if is_customer_ref_query:
        try:
          from agents.workflows.customer_reference_retriever import NewLibraryCustomerReferenceRetriever

          ref_retriever = NewLibraryCustomerReferenceRetriever(
              config, datastore_id="", ds_key="cust_ref"
          )
          ref_state = {
              "customer_name": customer_name,
              "industry": industry or raw_q,
              "closest_industry": industry,
              "salesPlay": sales_play,
              "sales_play": sales_play,
              "context": raw_q,
          }
          ref_results = ref_retriever.search_slides(
              query=effective_sidebar_query or raw_q,
              context=ref_state,
              limit=12,
          )
          for ref in ref_results or []:
            norm_ref = a2ui_util.normalize_slide_search_item(
                item=ref,
                idx=len(formatted_slides) + 1,
                default_slide_job="Proof_Points",
            )
            s_id = norm_ref["slide_id"]
            d_id = norm_ref["pres_id"]
            title = norm_ref["title"]
            dedup_key = f"{d_id}:{s_id}" if (d_id or s_id) else title.lower()
            if dedup_key in seen_keys:
              continue
            seen_keys.add(dedup_key)
            formatted_slides.append({
                "title": title,
                "slide_title": title,
                "slide_job": "Proof_Points",
                "category": norm_ref["customer"] or "Customer Reference",
                "customer": norm_ref["customer"],
                "industry": (
                    norm_ref["industry"]
                    or a2ui_util.normalize_slide_search_item(
                        {"industry": industry}
                    ).get("industry", "")
                ),
                "solution": ref.get("sales_play") or sales_play or "",
                "product": ref.get("products") or "",
                "slide_id": s_id,
                "deck_id": d_id,
                "presentation_id": d_id,
                "source_deck_title": (
                    ref.get("deck_title")
                    or (
                        norm_ref["source_deck_title"]
                        if norm_ref["source_deck_title"]
                        != "CloudHub Reusable Slide Library"
                        else "Customer Reference Library Google Slides Customer Reference Library"
                    )
                ),
                "summary": norm_ref["summary"],
                "view_url": norm_ref["view_url"],
            })
        except Exception as ref_err:
          print(
              f"[PitchGenSkills] CustomerReferenceRetriever warning: {ref_err}"
          )
      else:
        agent = SidebarAgent(config)
        raw_result = agent.search(
            search_query=effective_sidebar_query or raw_q,
            strict_search=strict_search,
            user_ldap=user_ldap,
        )

        search_results = (
            raw_result.get("search_results", [])
            if isinstance(raw_result, dict)
            else []
        )
        for slide in search_results:
          inferred_job = (
              slide.get("slide_job")
              or slide.get("slideJob")
              or GTMSkills.infer_slide_job(slide)
          )

          if slide_job and str(slide_job).strip() != "":
            target_job = (
                str(slide_job)
                .strip()
                .lower()
                .replace("-", "_")
                .replace(" ", "_")
            )
            current_job = (
                str(inferred_job).lower().replace("-", "_").replace(" ", "_")
            )
            if target_job not in current_job and current_job not in target_job:
              continue

          slide_ids_list = slide.get("slideIds")
          raw_s_id = (
              slide.get("slide_id")
              or slide.get("slideId")
              or (
                  slide_ids_list[0]
                  if isinstance(slide_ids_list, list) and slide_ids_list
                  else ""
              )
              or ""
          )
          cand_slide = dict(slide)
          if raw_s_id:
            cand_slide["slide_id"] = str(raw_s_id).strip()
          cand_slide["slide_job"] = inferred_job
          if not cand_slide.get("industry") and industry:
            cand_slide["industry"] = industry

          norm_slide = a2ui_util.normalize_slide_search_item(
              item=cand_slide,
              idx=len(formatted_slides) + 1,
              default_slide_job=inferred_job,
          )
          s_id = norm_slide["slide_id"]
          d_id = norm_slide["pres_id"]
          title = norm_slide["title"]
          dedup_key = f"{d_id}:{s_id}" if (d_id or s_id) else title.lower()
          if dedup_key in seen_keys:
            continue
          seen_keys.add(dedup_key)

          formatted_slides.append({
              "title": title,
              "slide_title": title,
              "slide_job": inferred_job,
              "category": (
                  norm_slide["customer"]
                  or slide.get("category")
                  or slide.get("slide_category")
                  or ""
              ),
              "customer": norm_slide["customer"],
              "industry": norm_slide["industry"],
              "solution": slide.get("solution") or slide.get("salesPlay") or "",
              "product": slide.get("product") or slide.get("products") or "",
              "slide_id": s_id,
              "deck_id": d_id,
              "presentation_id": d_id,
              "source_deck_title": norm_slide["source_deck_title"],
              "summary": norm_slide["summary"],
              "view_url": norm_slide["view_url"],
          })

      output_data = {
          "status": "success",
          "query": raw_q or effective_sidebar_query,
          "effective_query": effective_sidebar_query,
          "customer_name": customer_name,
          "industry": industry,
          "active_presentation_id": active_pres_id,
          "filtered_by_slide_job": (
              slide_job or ("Proof_Points" if is_customer_ref_query else "ALL")
          ),
          "total_found": len(formatted_slides),
          "ui_rendering_note": (
              "All matched slides are rendered interactively inside the"
              " pitchgen-slide-search A2UI widget below (including slide"
              " titles, linked source deck titles, full descriptions, and"
              " 1-click insertion). Respond with ONLY 1-2 concise sentences"
              " directing the user to explore or insert slides in the Slide"
              " Search widget below. Do NOT list or repeat individual slides,"
              " bullet points, or URLs in chat."
          ),
          "slides": formatted_slides[:10],
      }
      return json.dumps(output_data, indent=2)
    except Exception as e:
      import traceback
      print(f"[PitchGenSkills] Error in enterprise_search_slides_skill: {e}")
      traceback.print_exc()
      return json.dumps({"status": "error", "error": str(e)})

  @staticmethod
  def enterprise_insert_slide_skill(
      source_presentation_id: str,
      template_slide_id: str,
      target_presentation_id: str = "",
      slide_title: str = "",
      slide_job: str = "Proof_Points",
      tool_context=None,
  ) -> str:
    """Inserts a reusable library or customer reference slide into the active Google Slides presentation.

    Args:
        source_presentation_id: Source library Google Slides presentation ID or
          URL.
        template_slide_id: Slide objectId within the source presentation to
          insert.
        target_presentation_id: Target presentation ID or URL (auto-resolves
          from active Canvas deck if omitted).
        slide_title: Optional title of the slide being inserted for fallback
          matching.
        slide_job: Optional Slide Job classification (e.g., 'Proof_Points',
          'Architecture').
        tool_context: ADK ToolContext providing user identity and session state.

    Returns:
        Serialized JSON string confirming slide insertion and updated deck URL.
    """
    clean_source_id = (
        extract_presentation_id(source_presentation_id, None)
        or (source_presentation_id or "").strip()
    )
    resolved_target_id, session_ctx = (
        PitchGenSkills._resolve_active_presentation_and_context(
            target_presentation_id, tool_context
        )
    )
    if resolved_target_id and resolved_target_id == clean_source_id:
      resolved_target_id, session_ctx = (
          PitchGenSkills._resolve_active_presentation_and_context(
              "", tool_context
          )
      )
    clean_slide_id = (template_slide_id or "").strip()

    if not resolved_target_id:
      return json.dumps({
          "status": "error",
          "error": (
              "No active target presentation found. Please generate or provide"
              " a Google Slides presentation first."
          ),
      })

    user_ldap = ""
    user_oauth_token = ""
    if tool_context is not None:
      _, user_ldap = extract_session_user_email_and_ldap(tool_context)
      try:
        from oauth_helper import get_user_access_token

        silent_token = get_user_access_token(user_ldap)
        if silent_token:
          user_oauth_token = silent_token
      except Exception:
        pass
    clean_ldap = (
        (user_ldap or os.environ.get("USER", "user"))
        .split("@")[0]
        .lower()
        .strip()
    )
    candidate_tokens = _build_apps_script_candidate_tokens(
        clean_ldap, user_oauth_token, tool_context=tool_context
    )

    import uuid
    import requests as req_lib

    temp_slide_id = f"pg_ins_{uuid.uuid4().hex[:10]}"
    created_placeholder = False

    for _, tok in candidate_tokens:
      if not tok:
        continue
      try:
        resp = req_lib.post(
            f"https://slides.googleapis.com/v1/presentations/{resolved_target_id}:batchUpdate",
            headers={
                "Authorization": f"Bearer {tok}",
                "Content-Type": "application/json",
            },
            json={"requests": [{"createSlide": {"objectId": temp_slide_id}}]},
            timeout=20,
        )
        if resp.status_code == 200:
          created_placeholder = True
          break
      except Exception:
        continue

    relinked_count = 0
    final_inserted_slide_id = temp_slide_id
    if clean_source_id:
      source_slide_url = (
          f"https://docs.google.com/presentation/d/{clean_source_id}/edit#slide=id.{clean_slide_id}"
          if clean_slide_id
          else f"https://docs.google.com/presentation/d/{clean_source_id}/edit"
      )
      relink_payload = {
          "action": "relink_slides",
          "presentationId": resolved_target_id,
          "slides": [{
              "oldSlideId": temp_slide_id,
              "sourcePresId": clean_source_id,
              "sourceSlideId": clean_slide_id,
              "fallbackTitle": slide_title,
              "slideUrl": source_slide_url,
              "slideLabel": slide_title or clean_slide_id,
          }],
      }
      script_resp = execute_apps_script_request(
          relink_payload,
          clean_ldap,
          user_oauth_token,
          tool_context=tool_context,
      )
      if isinstance(script_resp, dict):
        relinked_list = script_resp.get("relinked")
        if isinstance(relinked_list, list) and relinked_list:
          relinked_count = len(relinked_list)
          first_relinked = relinked_list[0]
          if isinstance(first_relinked, dict) and first_relinked.get(
              "newSlideId"
          ):
            final_inserted_slide_id = str(first_relinked["newSlideId"])
        else:
          relinked_count = int(script_resp.get("relinkedCount") or 0)

    deck_url = (
        f"https://docs.google.com/presentation/d/{resolved_target_id}/edit"
    )
    return json.dumps(
        {
            "status": "success",
            "message": (
                f"Successfully inserted slide '{slide_title or clean_slide_id}'"
                f" into active presentation {deck_url}."
            ),
            "target_presentation_id": resolved_target_id,
            "source_presentation_id": clean_source_id,
            "template_slide_id": clean_slide_id,
            "inserted_slide_id": final_inserted_slide_id,
            "relinked_linked_slide": relinked_count > 0,
            "placeholder_created": created_placeholder,
            "slide_title": slide_title,
            "slide_job": slide_job,
            "deck_url": deck_url,
            "customer_name": session_ctx.get("customer_name", ""),
        },
        indent=2,
    )

  @staticmethod
  def enterprise_transform_slide_text_skill(
      presentation_url_or_id: str = "",
      customization_criteria: str = "Improve clarity and professional tone",
      target_slide_indices: str = "",
      customer_name: str = "",
      industry: str = "",
      audience: str = "",
      full_deck_scope: bool = False,
      tool_context=None,
  ) -> str:
    """Polishes and transforms the text of an existing Google Slides presentation (active Canvas deck or linked from Google Drive).

    Applies Go-to-Market (GTM) copywriting rules, Slide Job intensity
    governance, and account customization while preserving layout structure.

    Args:
        presentation_url_or_id: Google Slides presentation URL or Presentation
          ID (auto-resolves from active Canvas deck if omitted).
        customization_criteria: The editing criteria (e.g., 'Make tone executive
          for CxO', 'Customize for Disney focusing on ROI proof points').
        target_slide_indices: Optional comma-separated slide indices (e.g., '1,
          2, 4') to transform. If omitted or empty, transforms all slides.
        customer_name: Optional target customer/account name.
        industry: Optional target industry vertical.
        audience: Optional target audience persona(s).
        full_deck_scope: Whether to transform the full deck (all slides).
        tool_context: ADK ToolContext providing user credentials and session
          state.

    Returns:
        A serialized JSON response containing the presentation URL and
        transformation confirmation.
    """
    clean_target_slides = str(target_slide_indices or "").strip()
    is_specific_slide_scope = bool(
        clean_target_slides
        and clean_target_slides.lower()
        not in ("all", "full_deck", "entire_deck", "*")
    )
    if is_specific_slide_scope:
      full_deck_scope = False
      effective_target_slides = clean_target_slides
    else:
      effective_target_slides = "" if full_deck_scope else clean_target_slides
    presentation_id, session_ctx = (
        PitchGenSkills._resolve_active_presentation_and_context(
            presentation_url_or_id, tool_context
        )
    )
    if not presentation_id:
      return json.dumps({
          "status": "error",
          "error": (
              "No active presentation found to transform. Please generate or"
              " provide a Google Slides presentation first."
          ),
      })

    user_email = ""
    user_ldap = ""
    user_oauth_token = ""
    if tool_context is not None:
      user_email, user_ldap = extract_session_user_email_and_ldap(tool_context)
      try:
        from oauth_helper import get_user_access_token
        silent_token = get_user_access_token(user_ldap)
        if silent_token:
          user_oauth_token = silent_token
      except Exception:
        pass

    if not user_ldap:
      user_ldap = os.environ.get("USER", "user")

    clean_ldap = user_ldap.split("@")[0].lower().strip()
    presentation_url = (
        f"https://docs.google.com/presentation/d/{presentation_id}/edit"
    )
    resolved_customer = customer_name or str(
        session_ctx.get("customer_name") or ""
    )
    resolved_industry = industry or str(session_ctx.get("industry") or "")

    print(
        f"[PitchGenSkills] Transforming presentation '{presentation_id}' for"
        f" user '{clean_ldap}' with criteria: '{customization_criteria}'"
        f" (slides='{effective_target_slides or 'ALL'}')..."
    )

    rest_result: Dict[str, Any] = {}
    candidate_tokens = _build_apps_script_candidate_tokens(
        clean_ldap, user_oauth_token, tool_context=tool_context
    )
    try:
      rest_result = PitchGenSkills._transform_presentation_slides_via_rest_api(
          presentation_id=presentation_id,
          customization_criteria=customization_criteria,
          target_slide_indices=effective_target_slides,
          customer_name=resolved_customer,
          industry=resolved_industry,
          audience=audience,
          sales_play=str(session_ctx.get("salesPlay") or ""),
          customer_research=str(session_ctx.get("customer_research") or ""),
          candidate_tokens=candidate_tokens,
      )
    except Exception as rest_err:
      print(
          "[PitchGenSkills] REST API text transform fallback notice:"
          f" {rest_err}"
      )

    if rest_result.get("status") != "success":
      try:
        from services.deck_transformation_service import DeckTransformationService

        svc_res_str = DeckTransformationService.transform_deck_text(
            presentation_identifier=presentation_id,
            transform_instructions=customization_criteria,
            target_slide_numbers=effective_target_slides,
            customer_name=resolved_customer,
            industry=resolved_industry,
            audience=audience,
            full_deck_scope=full_deck_scope,
            tool_context=tool_context,
        )
        svc_res = (
            json.loads(svc_res_str)
            if isinstance(svc_res_str, str)
            and svc_res_str.strip().startswith("{")
            else {"message": str(svc_res_str)}
        )
        msg_str = (
            str(svc_res.get("message", ""))
            if isinstance(svc_res, dict)
            else str(svc_res_str)
        )
        if isinstance(svc_res, dict) and (
            svc_res.get("status") in ("success", 200, "200")
            or "deck_url" in svc_res
            or "deckURL" in svc_res
            or "successfully transformed" in msg_str.lower()
            or "successfully translated" in msg_str.lower()
        ):
          return json.dumps(
              {
                  "status": "success",
                  "message": (
                      msg_str
                      or f"Successfully transformed slide text for presentation: {presentation_url}"
                  ),
                  "presentation_id": presentation_id,
                  "deck_url": (
                      svc_res.get("deck_url")
                      or svc_res.get("deckURL")
                      or presentation_url
                  ),
                  "customization_criteria": customization_criteria,
                  "customer_name": resolved_customer,
                  "industry": resolved_industry,
                  "audience": audience,
                  "scope": (
                      f"Slides {effective_target_slides}"
                      if effective_target_slides
                      else "Full Deck"
                  ),
              },
              indent=2,
          )
      except Exception as svc_err:
        print(
            "[PitchGenSkills] Notice: DeckTransformationService fallback"
            f" ({svc_err})"
        )

    if rest_result.get("status") != "success" and not candidate_tokens:
      auth_url = get_authorization_url(clean_ldap or "unknown")
      return json.dumps(
          {
              "status": "auth_required",
              "auth_url": auth_url,
              "message": (
                  "Please authorize PitchGen to access presentations in your"
                  f" Google Drive by clicking this link: {auth_url}\n\nOnce"
                  " authorized, simply say 'continue' or repeat your request."
              ),
          },
          indent=2,
      )

    deck_url = presentation_url

    result = {
        "status": "success",
        "message": (
            f"Successfully transformed slide text for presentation: {deck_url}"
        ),
        "presentation_id": presentation_id,
        "deck_url": deck_url,
        "customization_criteria": customization_criteria,
        "scope": (
            f"Slides {effective_target_slides}"
            if effective_target_slides
            else "Full Deck"
        ),
        "slides_modified": rest_result.get("slides_modified", 0),
        "elements_modified": rest_result.get("elements_modified", 0),
        "customer_name": resolved_customer,
        "industry": resolved_industry,
        "audience": audience,
    }
    return json.dumps(result, indent=2)

  @staticmethod
  def enterprise_generate_visuals_skill(
      prompt: str,
      presentation_url_or_id: str = "",
      visual_style: str = "Google Cloud Modern Architecture (Flat vector, precise topology)",
      target_slide_index: int = 1,
      mode: str = "generate",
      target_slide_indices: str = "",
      in_place_only: bool = False,
      selected_model: str = "nano_banana_pro",
      customer_name: str = "",
      gifs_only: bool = False,
      include_gifs: bool = False,
      tool_context=None,
  ) -> str:
    """Synthesizes bespoke 2K technical architecture diagrams, flowcharts, and slide visuals OR transforms existing slide visuals in-place using Nano Banana (Gemini 3.1 Image) and Veo 2 Video-to-Video for GIFs.

    Args:
        prompt: Detailed description of the architecture diagram, visual flow,
          or visual transformation instruction (e.g. 'Customize with Nvidia
          visuals').
        presentation_url_or_id: Optional target Google Slides presentation URL
          or ID (auto-resolves from active Canvas presentation if omitted).
        visual_style: Visual style preset (e.g., 'Google Cloud Modern
          Architecture', 'Executive Minimalist').
        target_slide_index: 1-based slide index for visual placement or
          transformation.
        mode: 'generate' to synthesize a new slide visual, or 'transform' to
          transform existing slide images in-place via replaceImage.
        target_slide_indices: Optional comma-separated 1-based slide numbers or
          ranges (e.g., '2, 4-6') for multi-slide in-place image transformation.
        in_place_only: When True, only replaces embedded in-slide images via
          replaceImage and never appends a new full-bleed blank slide.
        selected_model: Model selector ('nano_banana_pro', 'nano_banana_2_1', or
          'nano_banana_flash').
        customer_name: Optional target customer/account name.
        gifs_only: When True, only customizes animated in-slide GIFs (n_frames >
          1) via video-to-video and skips static PNG/JPEG images.
        include_gifs: When True, also customizes animated in-slide GIFs via
          video-to-video alongside static in-slide images.
        tool_context: ADK ToolContext providing user identity and session state.

    Returns:
        Serialized JSON string containing the generated/transformed visual GCS
        URI,
        signed preview URL, and presentation modification details.
    """
    presentation_id, session_ctx = (
        PitchGenSkills._resolve_active_presentation_and_context(
            presentation_url_or_id, tool_context
        )
    )
    prev_sess_cust = str(session_ctx.get("customer_name") or "").strip()
    explicit_cust = str(customer_name or "").strip()
    if not explicit_cust and prompt:
      m_cust_ctx = re.search(
          r"\(Customer Context:\s*([^\)]+)\)", str(prompt), re.IGNORECASE
      )
      if m_cust_ctx:
        explicit_cust = m_cust_ctx.group(1).strip()
      else:
        m_for = re.search(
            r"\b(?:for|with|to)\s+([A-Z][A-Za-z0-9&\-\s]{1,30}?)(?:\s+visuals?|\s+branding|\s+aesthetic|\s*\(|\s*$)",
            str(prompt).strip(),
        )
        if m_for:
          cand_c = m_for.group(1).strip()
          if cand_c.lower() not in (
              "google",
              "google cloud",
              "gemini",
              "gemini enterprise",
              "cxo",
              "executive",
          ):
            explicit_cust = cand_c
    cust_changed = bool(
        explicit_cust
        and prev_sess_cust
        and explicit_cust.lower() != prev_sess_cust.lower()
    )
    customer_name = explicit_cust or prev_sess_cust
    industry = (
        "" if cust_changed else str(session_ctx.get("industry") or "").strip()
    )
    sales_play = (
        "" if cust_changed else str(session_ctx.get("salesPlay") or "").strip()
    )

    def _get_cfg(cfg_obj, sec: str, opt: str, default: str = "") -> str:
      if hasattr(cfg_obj, "has_section"):
        try:
          return str(cfg_obj.get(sec, opt, fallback=default) or default)
        except Exception:
          return default
      if isinstance(cfg_obj, dict):
        sec_d = cfg_obj.get(sec)
        if isinstance(sec_d, dict):
          return str(sec_d.get(opt) or default)
      return default

    user_ldap = ""
    user_oauth_token = ""
    if tool_context is not None:
      _, user_ldap = extract_session_user_email_and_ldap(tool_context)
      try:
        from oauth_helper import get_user_access_token

        silent_token = get_user_access_token(user_ldap)
        if silent_token:
          user_oauth_token = silent_token
      except Exception:
        pass
    clean_ldap = (
        (user_ldap or os.environ.get("USER", "user"))
        .split("@")[0]
        .lower()
        .strip()
    )

    prompt_low = str(prompt or "").strip().lower()
    is_transform_mode = (
        bool(in_place_only)
        or bool(gifs_only)
        or bool(include_gifs)
        or str(mode or "").strip().lower() == "transform"
        or any(
            kw in prompt_low
            for kw in (
                "customize with",
                "transform slide",
                "transform visual",
                "transform image",
                "replace visual",
                "replace image",
                "restyle visual",
                "adapt visual",
            )
        )
    )

    generated_gcs_uri = ""
    signed_image_url = ""
    inserted_slide_id = ""
    replaced_image_count = 0
    replaced_gif_count = 0

    # Visual transformation path when mode=='transform' and an active presentation exists
    if is_transform_mode and presentation_id:
      try:
        import base64
        import concurrent.futures
        import time
        import uuid
        import requests as req_lib
        from config_loader import load_config
        from agents.workflows.visual_transformation_workflow import VisualTransformationWorkflow
        from pitchgen_utils.image_util import (
            _element_bbox_pt,
            _ensure_high_res_output_png,
            _flatten_slide_elements,
            _select_gemini_aspect_ratio_and_size,
            clean_base64_data,
            cleanup_temp_drive_docs,
            customize_slide_gif_for_customer,
            customize_slide_picture_for_customer,
            extract_customizable_slide_gifs,
            extract_customizable_slide_pictures,
            generate_gcs_v4_signed_url,
            image_bytes_to_content_uri,
            is_gif_or_animated_bytes,
            upload_bytes_to_gcs,
        )

        config = load_config()
        primary_bucket = (
            _get_cfg(config, "bucket", "content")
            or _get_cfg(config, "gcs", "content_uploading_bucket")
            or "your-pitchgen-content-bucket"
        )
        project_id = (
            _get_cfg(config, "default", "project_name") or "your-gcp-project-id"
        )
        candidate_tokens = _build_apps_script_candidate_tokens(
            clean_ldap, user_oauth_token, tool_context=tool_context
        )
        pres_data = None
        active_tok = None
        for _, tok in candidate_tokens:
          if not tok:
            continue
          r_get = req_lib.get(
              f"https://slides.googleapis.com/v1/presentations/{presentation_id}",
              headers={"Authorization": f"Bearer {tok}"},
              timeout=25,
          )
          if r_get.status_code == 200:
            pres_data = r_get.json()
            active_tok = tok
            break

        if pres_data and active_tok:
          slides_list = pres_data.get("slides", [])
          target_tasks = []  # list of (pic_info, slide_text_ctx, slide_object_id)

          def _get_slide_text_summary(sl_obj: dict) -> str:
            txts = []
            for pe_i in sl_obj.get("pageElements", []):
              for te_i in (
                  pe_i.get("shape", {}).get("text", {}).get("textElements", [])
              ):
                if "textRun" in te_i:
                  t_s = te_i["textRun"].get("content", "").strip()
                  if t_s:
                    txts.append(t_s)
            return " | ".join(txts)[:400]

          def _get_slide_notes_summary(sl_obj: dict) -> str:
            notes_pg = (sl_obj.get("slideProperties") or {}).get(
                "notesPage"
            ) or {}
            n_txts = []
            for n_pe in notes_pg.get("pageElements") or []:
              for n_te in ((n_pe.get("shape") or {}).get("text") or {}).get(
                  "textElements"
              ) or []:
                if "textRun" in n_te:
                  n_s = (n_te["textRun"].get("content") or "").strip()
                  if n_s:
                    n_txts.append(n_s)
            return " ".join(n_txts).lower()

          parsed_slide_nums: List[int] = []
          raw_idx_spec = str(target_slide_indices or "").strip()
          if raw_idx_spec and raw_idx_spec.lower() not in (
              "all",
              "full_deck",
              "entire_deck",
              "*",
          ):
            for part in raw_idx_spec.split(","):
              part = part.strip()
              if not part:
                continue
              if "-" in part:
                b_parts = part.split("-", 1)
                if (
                    b_parts[0].strip().isdigit()
                    and b_parts[1].strip().isdigit()
                ):
                  for s_n in range(
                      int(b_parts[0].strip()), int(b_parts[1].strip()) + 1
                  ):
                    if (
                        1 <= s_n <= len(slides_list)
                        and s_n not in parsed_slide_nums
                    ):
                      parsed_slide_nums.append(s_n)
              elif part.isdigit():
                s_n = int(part)
                if (
                    1 <= s_n <= len(slides_list)
                    and s_n not in parsed_slide_nums
                ):
                  parsed_slide_nums.append(s_n)
          elif (
              not in_place_only
              and target_slide_index
              and 1 <= int(target_slide_index) <= len(slides_list)
          ):
            parsed_slide_nums.append(int(target_slide_index))

          # Mode A: NanoBanana Studio full-slide visual restyling (not in_place_only)
          if not in_place_only and slides_list:
            target_s_num = (
                parsed_slide_nums[0]
                if parsed_slide_nums
                else max(1, min(int(target_slide_index or 1), len(slides_list)))
            )
            t_sl = slides_list[target_s_num - 1]
            t_sl_oid = t_sl.get("objectId", "")
            t_ctx = _get_slide_text_summary(t_sl)
            b64_slide_thumb = ""
            if t_sl_oid:
              try:
                r_thumb = req_lib.get(
                    f"https://slides.googleapis.com/v1/presentations/{presentation_id}/pages/{t_sl_oid}/thumbnail?thumbnailProperties.thumbnailSize=LARGE",
                    headers={"Authorization": f"Bearer {active_tok}"},
                    timeout=20,
                )
                if r_thumb.status_code == 200:
                  thumb_url = (r_thumb.json() or {}).get("contentUrl", "")
                  if thumb_url:
                    dl_th = req_lib.get(thumb_url, timeout=15)
                    if dl_th.status_code == 200 and dl_th.content:
                      b64_slide_thumb = (
                          "data:image/png;base64,"
                          + base64.b64encode(dl_th.content).decode("utf-8")
                      )
              except Exception as th_err:
                print(
                    "[PitchGenSkills] Slide thumbnail fetch notice for"
                    f" {t_sl_oid}: {th_err}"
                )

            if b64_slide_thumb or t_ctx:
              try:
                tf_wf = VisualTransformationWorkflow(config)
                cust_clause = (
                    f" for {customer_name} ({industry or 'Enterprise'})"
                    if customer_name
                    else ""
                )
                full_slide_req = (
                    f"{prompt}. Restyle and transform this presentation slide"
                    " into a cohesive, executive-ready 16:9 visual"
                    f" slide{cust_clause} preserving its core narrative and key"
                    f" takeaways: {t_ctx[:350]}."
                )
                out_b64 = tf_wf.execute(
                    request=full_slide_req,
                    existing_slide_image_url=b64_slide_thumb,
                    base64_image=b64_slide_thumb,
                    theme=visual_style,
                    aspect_ratio="16:9",
                    image_size="2K",
                    customer_name=customer_name,
                    industry=industry,
                    sales_play=sales_play,
                    model_override=selected_model,
                )
                if out_b64:
                  out_raw = (
                      base64.b64decode(clean_base64_data(out_b64))
                      if isinstance(out_b64, str)
                      else out_b64
                  )
                  hi_bytes = _ensure_high_res_output_png(
                      out_raw,
                      width_pt=680.0,
                      height_pt=382.0,
                      slide_index=target_s_num - 1,
                  )
                  ts_now = int(time.time() * 1000)
                  b_path = f"nanoBanana_imageGen/ge_slidetf_{clean_ldap}_{t_sl_oid}_{ts_now}.png"
                  g_uri = upload_bytes_to_gcs(
                      hi_bytes,
                      primary_bucket,
                      b_path,
                      content_type="image/png",
                      project_id=project_id,
                      mirror_buckets=[
                          "your-pitchgen-content-bucket",
                          "your-pitchgen-content-bucket",
                      ],
                  )
                  sig_u = generate_gcs_v4_signed_url(
                      primary_bucket,
                      b_path,
                      project_id=project_id,
                      expiration_seconds=14400,
                      raw_bytes=hi_bytes,
                      mime_type="image/png",
                      oauth_token=active_tok,
                  )
                  if sig_u and t_sl_oid:
                    new_img_id = f"pg_img_{uuid.uuid4().hex[:10]}"
                    create_img_req = {
                        "createImage": {
                            "objectId": new_img_id,
                            "url": sig_u,
                            "elementProperties": {
                                "pageObjectId": t_sl_oid,
                                "size": {
                                    "width": {"magnitude": 680, "unit": "PT"},
                                    "height": {"magnitude": 382, "unit": "PT"},
                                },
                                "transform": {
                                    "scaleX": 1,
                                    "scaleY": 1,
                                    "translateX": 20,
                                    "translateY": 11,
                                    "unit": "PT",
                                },
                            },
                        }
                    }
                    del_reqs = [
                        {"deleteObject": {"objectId": pe.get("objectId")}}
                        for pe in t_sl.get("pageElements", [])
                        if pe.get("objectId")
                    ]
                    r_upd = req_lib.post(
                        f"https://slides.googleapis.com/v1/presentations/{presentation_id}:batchUpdate",
                        headers={
                            "Authorization": f"Bearer {active_tok}",
                            "Content-Type": "application/json",
                        },
                        json={"requests": del_reqs + [create_img_req]},
                        timeout=25,
                    )
                    if r_upd.status_code != 200:
                      c_uri, _ = image_bytes_to_content_uri(
                          hi_bytes,
                          mime_type="image/png",
                          oauth_token=active_tok,
                      )
                      if c_uri:
                        create_img_req["createImage"]["url"] = c_uri
                        sig_u = c_uri
                      r_upd = req_lib.post(
                          f"https://slides.googleapis.com/v1/presentations/{presentation_id}:batchUpdate",
                          headers={
                              "Authorization": f"Bearer {active_tok}",
                              "Content-Type": "application/json",
                          },
                          json={"requests": del_reqs + [create_img_req]},
                          timeout=25,
                      )
                    if r_upd.status_code != 200:
                      r_upd = req_lib.post(
                          f"https://slides.googleapis.com/v1/presentations/{presentation_id}:batchUpdate",
                          headers={
                              "Authorization": f"Bearer {active_tok}",
                              "Content-Type": "application/json",
                          },
                          json={"requests": [create_img_req]},
                          timeout=25,
                      )
                    if r_upd.status_code == 200:
                      replaced_image_count = 1
                      inserted_slide_id = t_sl_oid
                      signed_image_url = sig_u
                      generated_gcs_uri = g_uri
                      try:
                        cleanup_temp_drive_docs(oauth_token=active_tok)
                      except Exception:
                        pass
              except Exception as full_tf_err:
                print(
                    "[PitchGenSkills] Full-slide visual restyle notice:"
                    f" {full_tf_err}"
                )

          # Mode B: In-place embedded picture replacement (Card 3 images_only / both, or fallback)
          if replaced_image_count == 0 and not gifs_only:
            # 1. If specific slide(s) were targeted, inspect those slides first
            for s_num in parsed_slide_nums:
              t_sl = slides_list[s_num - 1]
              t_ctx_s = _get_slide_text_summary(t_sl)
              t_pics = extract_customizable_slide_pictures(
                  t_sl,
                  slide_index=s_num - 1,
                  is_cust_ref_slide=False,
                  min_width_pt=50.0,
                  min_height_pt=50.0,
                  explicit_user_request=True,
              )
              if not t_pics:
                # Permissive fallback for explicitly targeted slides so an in-slide image is never skipped
                fallback_candidates = []
                for pe in _flatten_slide_elements(t_sl.get("pageElements", [])):
                  img_obj = pe.get("image")
                  if not img_obj:
                    continue
                  oid = pe.get("objectId", "")
                  c_u = str(
                      img_obj.get("contentUrl")
                      or img_obj.get("sourceUrl")
                      or ""
                  ).strip()
                  if not oid or not c_u or is_gif_or_animated_bytes(url=c_u):
                    continue
                  _, _, w_p, h_p, is_flip = _element_bbox_pt(pe)
                  if (
                      is_flip
                      or w_p < 50.0
                      or h_p < 50.0
                      or (w_p >= 680.0 and h_p >= 380.0)
                  ):
                    continue
                  g_ar, t_sz = _select_gemini_aspect_ratio_and_size(
                      w_p, h_p, slide_index=s_num - 1
                  )
                  fallback_candidates.append({
                      "objectId": oid,
                      "contentUrl": c_u,
                      "width_pt": round(w_p, 1),
                      "height_pt": round(h_p, 1),
                      "aspect_ratio": round(w_p / max(1.0, h_p), 2),
                      "gemini_aspect_ratio": g_ar,
                      "image_size": t_sz,
                      "is_title_slide": (s_num - 1) <= 1,
                      "slide_index": s_num - 1,
                      "_area": w_p * h_p,
                  })
                fallback_candidates.sort(
                    key=lambda x: x.get("_area", 0.0), reverse=True
                )
                t_pics = fallback_candidates[:2]
              for p_inf in t_pics:
                target_tasks.append((p_inf, t_ctx_s, t_sl.get("objectId", "")))

            # 2. If no specific slide was targeted (or in_place_only full deck), scan customizable slides across the deck
            if not target_tasks and not parsed_slide_nums:
              for s_i, sl_obj in enumerate(slides_list):
                s_ctx = _get_slide_text_summary(sl_obj)
                s_ctx_low = s_ctx.lower()
                s_notes_low = _get_slide_notes_summary(sl_obj)
                has_cym = "cymbal" in s_ctx_low or "cymbal" in s_notes_low
                # Skip internal context Slide 0 and verified non-Cymbal customer reference / cited stats slides
                if s_i == 0 and any(
                    k in s_ctx_low
                    for k in (
                        "internal context",
                        "remove this slide",
                        "opportunity id",
                    )
                ):
                  continue
                if not has_cym and (
                    "exec summary:" in s_notes_low
                    or "customer_reference_library" in s_notes_low
                    or "sources:" in s_ctx_low
                ):
                  continue
                s_pics = extract_customizable_slide_pictures(
                    sl_obj,
                    slide_index=s_i,
                    is_cust_ref_slide=False,
                    min_width_pt=80.0,
                    min_height_pt=70.0,
                )
                for p_inf in s_pics:
                  target_tasks.append(
                      (p_inf, s_ctx, sl_obj.get("objectId", ""))
                  )

            if target_tasks:
              target_tasks = target_tasks[:16]

              def _transform_single_pic(task_item):
                p_inf, s_ctx_item, sl_oid = task_item
                obj_id = p_inf.get("objectId", "")
                c_url = p_inf.get("contentUrl", "")
                if not obj_id or not c_url:
                  return None
                try:
                  sl_idx = int(p_inf.get("slide_index") or 0)
                  is_cover_pic = bool(
                      p_inf.get("is_title_slide") or sl_idx == 0
                  )
                  # During full-deck scan on content slides, run multimodal triage + crop/alpha mask preservation via customize_slide_picture_for_customer
                  if (
                      not parsed_slide_nums
                      and not is_cover_pic
                      and customer_name
                  ):
                    cust_pic_res = customize_slide_picture_for_customer(
                        pic_info=p_inf,
                        slide_text_context=s_ctx_item,
                        customer_name=customer_name,
                        industry=industry,
                        config=config,
                    )
                    if not isinstance(
                        cust_pic_res, dict
                    ) or not cust_pic_res.get("replaceImage"):
                      return None
                    extra_reqs = []
                    if cust_pic_res.get("_reset_crop_request"):
                      extra_reqs.append(cust_pic_res["_reset_crop_request"])
                    if cust_pic_res.get("_alt_text_request"):
                      extra_reqs.append(cust_pic_res["_alt_text_request"])
                    return {
                        "replace_req": {
                            "replaceImage": cust_pic_res["replaceImage"]
                        },
                        "extra_reqs": extra_reqs,
                        "raw_bytes": None,
                        "obj_id": obj_id,
                        "gcs_uri": "",
                        "signed_url": (
                            cust_pic_res["replaceImage"].get("url", "")
                        ),
                        "slide_id": sl_oid,
                    }

                  dl_resp = req_lib.get(c_url, timeout=12)
                  if dl_resp.status_code != 200 or not dl_resp.content:
                    return None
                  raw_b = dl_resp.content
                  if is_gif_or_animated_bytes(
                      raw_bytes=raw_b,
                      content_type=dl_resp.headers.get("Content-Type", ""),
                      url=c_url,
                  ):
                    return None
                  mime_t = (
                      "image/jpeg"
                      if raw_b.startswith(b"\xff\xd8\xff")
                      else "image/png"
                  )
                  b64_src = f"data:{mime_t};base64," + base64.b64encode(
                      raw_b
                  ).decode("utf-8")
                  w_pt = float(p_inf.get("width_pt") or 280.0)
                  h_pt = float(p_inf.get("height_pt") or 200.0)
                  gem_ar, img_sz = _select_gemini_aspect_ratio_and_size(
                      w_pt, h_pt, slide_index=sl_idx
                  )
                  tf_wf = VisualTransformationWorkflow(config)
                  raw_p = str(prompt or "").strip()
                  raw_p_low = raw_p.lower()
                  # Strip generic boilerplate or text-only persona instructions so in-place image adaptation stays focused on the picture and target account
                  is_generic_prompt = (
                      not raw_p
                      or raw_p_low.startswith("customize slide visuals")
                      or raw_p_low.startswith("transform presentation text")
                      or raw_p_low.startswith("customize for ")
                      or raw_p_low.startswith("customize to ")
                      or raw_p_low.startswith("customize visual for ")
                      or (
                          any(
                              k in raw_p_low
                              for k in (
                                  "cfo",
                                  "ceo",
                                  "cto",
                                  "ciso",
                                  "cdo",
                                  "cmo",
                                  "bullet",
                                  "word",
                                  "concise",
                                  "tone",
                              )
                          )
                          and not any(
                              v in raw_p_low
                              for v in (
                                  "image",
                                  "photo",
                                  "picture",
                                  "visual",
                                  "product",
                                  "scene",
                                  "color",
                                  "background",
                              )
                          )
                      )
                  )
                  user_pic_hint = "" if is_generic_prompt else raw_p
                  target_acct = customer_name or "the target account"
                  domain_clause = f" ({industry})" if industry else ""
                  if is_cover_pic:
                    tf_req = (
                        "CRITICAL COVER SLIDE 3D SCULPTURE RULE: Do NOT keep"
                        " the generic circular ring/torus shape from the"
                        " reference image. Use the reference image ONLY for its"
                        " aesthetic medium (luminous 3D point-cloud particles"
                        " and gossamer flowing light waves suspended on a"
                        " seamless pure #000000 pitch-black background). "
                        + (f"{user_pic_hint}. " if user_pic_hint else "")
                        + "Reshape the 3D particle geometry into an iconic,"
                        " futuristic 3D sculptural form unmistakably inspired"
                        f" by {target_acct}{domain_clause}'s core products,"
                        " brand identity, and technology, positioned cleanly in"
                        " the center-right of the composition with a pure"
                        " #000000 black background on the left edge so slide"
                        " title text never collides. Render with ZERO text,"
                        " ZERO letters, ZERO words, ZERO numbers, and ZERO"
                        " logos."
                    )
                  else:
                    tf_req = (
                        "CRITICAL IN-SLIDE PICTURE RULE: Focus exclusively on"
                        " the attached image and the target account"
                        f" ({target_acct}{domain_clause}). "
                        + (f"{user_pic_hint}. " if user_pic_hint else "")
                        + "Preserve the exact visual medium (e.g., product"
                        " photography, studio/lifestyle scene, 3D render, or"
                        " editorial illustration), lighting, camera angle, and"
                        " compositional framing of the attached image, while"
                        " replacing any generic/template products, packaging,"
                        " objects, or environments (such as Cymbal cans,"
                        " bottles, boxes, or generic retail items) with"
                        " authentic, recognizable products, environments, and"
                        f" brand aesthetic native to {target_acct}."
                        " STRICT NEGATIVE CONSTRAINT: Render ZERO text, ZERO"
                        " slide titles, ZERO bottom caption banners, ZERO UI"
                        " labels, and ZERO diagrams inside the image."
                    )
                  out_b64 = tf_wf.execute(
                      request=tf_req,
                      existing_slide_image_url=b64_src,
                      base64_image=b64_src,
                      aspect_ratio=gem_ar,
                      image_size=img_sz,
                      customer_name=customer_name,
                      industry="",
                      is_cover_sculpture=is_cover_pic,
                      is_in_place_picture=not is_cover_pic,
                      model_override=selected_model,
                  )
                  if not out_b64:
                    return None
                  out_raw = (
                      base64.b64decode(clean_base64_data(out_b64))
                      if isinstance(out_b64, str)
                      else out_b64
                  )
                  hi_bytes = _ensure_high_res_output_png(
                      out_raw, width_pt=w_pt, height_pt=h_pt, slide_index=sl_idx
                  )
                  ts_now = int(time.time() * 1000)
                  b_path = f"nanoBanana_imageGen/ge_tf_{clean_ldap}_{obj_id}_{ts_now}.png"
                  g_uri = upload_bytes_to_gcs(
                      hi_bytes,
                      primary_bucket,
                      b_path,
                      content_type="image/png",
                      project_id=project_id,
                      mirror_buckets=[
                          "your-pitchgen-content-bucket",
                          "your-pitchgen-content-bucket",
                      ],
                  )
                  sig_u = generate_gcs_v4_signed_url(
                      primary_bucket,
                      b_path,
                      project_id=project_id,
                      expiration_seconds=14400,
                      raw_bytes=hi_bytes,
                      mime_type="image/png",
                      oauth_token=active_tok,
                  )
                  if not sig_u:
                    return None
                  return {
                      "replace_req": {
                          "replaceImage": {
                              "imageObjectId": obj_id,
                              "url": sig_u,
                              "imageReplaceMethod": "CENTER_CROP",
                          }
                      },
                      "extra_reqs": [],
                      "raw_bytes": hi_bytes,
                      "obj_id": obj_id,
                      "gcs_uri": g_uri,
                      "signed_url": sig_u,
                      "slide_id": sl_oid,
                  }
                except Exception as item_err:
                  print(
                      "[PitchGenSkills] In-place image transform warning for"
                      f" {obj_id}: {item_err}"
                  )
                  return None

              replace_items = []
              with concurrent.futures.ThreadPoolExecutor(
                  max_workers=min(len(target_tasks), 4)
              ) as ex:
                for res_item in ex.map(_transform_single_pic, target_tasks):
                  if isinstance(res_item, dict) and res_item.get("replace_req"):
                    replace_items.append(res_item)
                    if not signed_image_url:
                      signed_image_url = res_item.get("signed_url") or ""
                      generated_gcs_uri = res_item.get("gcs_uri") or ""
                      inserted_slide_id = res_item.get("slide_id") or ""

              if replace_items:
                for item_info in replace_items:
                  req_single = item_info["replace_req"]
                  extra_reqs = list(item_info.get("extra_reqs") or [])
                  try:
                    r_upd = req_lib.post(
                        f"https://slides.googleapis.com/v1/presentations/{presentation_id}:batchUpdate",
                        headers={
                            "Authorization": f"Bearer {active_tok}",
                            "Content-Type": "application/json",
                        },
                        json={"requests": [req_single] + extra_reqs},
                        timeout=25,
                    )
                    if r_upd.status_code != 200 and item_info.get("raw_bytes"):
                      c_uri, _ = image_bytes_to_content_uri(
                          item_info["raw_bytes"],
                          mime_type="image/png",
                          oauth_token=active_tok,
                      )
                      if c_uri:
                        req_single["replaceImage"]["url"] = c_uri
                        r_upd = req_lib.post(
                            f"https://slides.googleapis.com/v1/presentations/{presentation_id}:batchUpdate",
                            headers={
                                "Authorization": f"Bearer {active_tok}",
                                "Content-Type": "application/json",
                            },
                            json={"requests": [req_single] + extra_reqs},
                            timeout=25,
                        )
                    if r_upd.status_code == 200:
                      replaced_image_count += 1
                    else:
                      print(
                          "[PitchGenSkills] replaceImage failed for"
                          f" {item_info.get('obj_id')}: {r_upd.status_code}"
                          f" {r_upd.text[:160]}"
                      )
                  except Exception:
                    pass
                try:
                  cleanup_temp_drive_docs(oauth_token=active_tok)
                except Exception:
                  pass

          # Mode C: In-place animated GIF video-to-video customization (Card 3 gifs_only / both)
          if (gifs_only or include_gifs) and customer_name:
            gif_tasks = []
            if parsed_slide_nums:
              for s_num in parsed_slide_nums:
                if 1 <= s_num <= len(slides_list):
                  t_sl = slides_list[s_num - 1]
                  s_gifs = extract_customizable_slide_gifs(
                      t_sl,
                      slide_index=s_num - 1,
                      is_cust_ref_slide=False,
                      explicit_user_request=True,
                  )
                  for g_inf in s_gifs:
                    gif_tasks.append((
                        g_inf,
                        _get_slide_text_summary(t_sl),
                        t_sl.get("objectId", ""),
                    ))
            else:
              for s_i, sl_obj in enumerate(slides_list):
                s_ctx = _get_slide_text_summary(sl_obj)
                s_ctx_low = s_ctx.lower()
                s_notes_low = _get_slide_notes_summary(sl_obj)
                has_cym = "cymbal" in s_ctx_low or "cymbal" in s_notes_low
                if s_i == 0 and any(
                    k in s_ctx_low
                    for k in (
                        "internal context",
                        "remove this slide",
                        "opportunity id",
                    )
                ):
                  continue
                if not has_cym and (
                    "exec summary:" in s_notes_low
                    or "customer_reference_library" in s_notes_low
                    or "sources:" in s_ctx_low
                ):
                  continue
                s_gifs = extract_customizable_slide_gifs(
                    sl_obj,
                    slide_index=s_i,
                    is_cust_ref_slide=False,
                    explicit_user_request=False,
                )
                for g_inf in s_gifs:
                  gif_tasks.append((g_inf, s_ctx, sl_obj.get("objectId", "")))

            for g_inf, g_slide_ctx, _ in gif_tasks[:10]:
              try:
                g_oid = g_inf.get("objectId", "")
                g_url = g_inf.get("contentUrl", "")
                if not g_oid or not g_url:
                  continue
                dl_resp = req_lib.get(g_url, timeout=18)
                if dl_resp.status_code != 200 or not dl_resp.content:
                  continue
                raw_gif_b = dl_resp.content
                if not is_gif_or_animated_bytes(
                    raw_bytes=raw_gif_b,
                    content_type=dl_resp.headers.get("Content-Type", ""),
                    url=g_url,
                ):
                  continue
                custom_gif_res = customize_slide_gif_for_customer(
                    gif_info=g_inf,
                    raw_gif_bytes=raw_gif_b,
                    customer_name=customer_name,
                    industry=industry,
                    slide_text_context=g_slide_ctx,
                    slide_title_or_context=g_slide_ctx,
                    slide_index=int(g_inf.get("slide_index") or 0),
                    config=config,
                )
                custom_gif_b = (
                    custom_gif_res.get("_gif_bytes")
                    if isinstance(custom_gif_res, dict)
                    else custom_gif_res
                )
                if not custom_gif_b or custom_gif_b == raw_gif_b:
                  continue
                sig_gif_u = (
                    custom_gif_res.get("replaceImage", {}).get("url")
                    if isinstance(custom_gif_res, dict)
                    else ""
                )
                g_uri = (
                    custom_gif_res.get("_gcs_uri", "")
                    if isinstance(custom_gif_res, dict)
                    else ""
                )
                if not sig_gif_u:
                  ts_ms = int(time.time() * 1000)
                  gif_blob = f"nanoBanana_imageGen/ge_gif_tf_{clean_ldap}_{g_oid}_{ts_ms}.gif"
                  g_uri = upload_bytes_to_gcs(
                      custom_gif_b,
                      primary_bucket,
                      gif_blob,
                      content_type="image/gif",
                      project_id=project_id,
                      mirror_buckets=[
                          "your-pitchgen-content-bucket",
                          "your-pitchgen-content-bucket",
                      ],
                  )
                  sig_gif_u = generate_gcs_v4_signed_url(
                      primary_bucket,
                      gif_blob,
                      project_id=project_id,
                      expiration_seconds=14400,
                      raw_bytes=custom_gif_b,
                      mime_type="image/gif",
                      oauth_token=active_tok,
                  )
                  if not sig_gif_u:
                    sig_gif_u, _ = image_bytes_to_content_uri(
                        custom_gif_b,
                        mime_type="image/gif",
                        oauth_token=active_tok,
                    )
                if not sig_gif_u:
                  continue
                reqs = [{
                    "replaceImage": {
                        "imageObjectId": g_oid,
                        "imageReplaceMethod": "CENTER_INSIDE",
                        "url": sig_gif_u,
                    }
                }]
                if isinstance(custom_gif_res, dict):
                  if "_reset_crop_request" in custom_gif_res:
                    reqs.append(custom_gif_res["_reset_crop_request"])
                  if "_alt_text_request" in custom_gif_res:
                    reqs.append(custom_gif_res["_alt_text_request"])
                r_gif_upd = req_lib.post(
                    f"https://slides.googleapis.com/v1/presentations/{presentation_id}:batchUpdate",
                    headers={
                        "Authorization": f"Bearer {active_tok}",
                        "Content-Type": "application/json",
                    },
                    json={"requests": reqs},
                    timeout=25,
                )
                if r_gif_upd.status_code == 200:
                  replaced_gif_count += 1
                  replaced_image_count += 1
                  if not signed_image_url:
                    signed_image_url = sig_gif_u
                  if not generated_gcs_uri and g_uri:
                    generated_gcs_uri = g_uri
              except Exception as gif_tf_err:
                print(
                    "[PitchGenSkills] In-place GIF transformation notice:"
                    f" {gif_tf_err}"
                )
      except Exception as tf_mode_err:
        print(
            f"[PitchGenSkills] In-place visual transformation notice: {tf_mode_err}"
        )

    # Standard visual synthesis path if mode=='generate' or if no in-place images were replaced (unless in_place_only=True or gifs_only=True)
    if (
        replaced_image_count == 0
        and replaced_gif_count == 0
        and not in_place_only
        and not gifs_only
    ):
      high_res_bytes = b""
      try:
        import base64
        import time
        from config_loader import load_config
        from agents.workflows.visual_synthesis_workflow import VisualSynthesisWorkflow
        from pitchgen_utils.image_util import (
            _ensure_high_res_output_png,
            clean_base64_data,
            generate_gcs_v4_signed_url,
            image_bytes_to_content_uri,
            upload_bytes_to_gcs,
        )

        config = load_config()
        workflow = VisualSynthesisWorkflow(config)
        b64_img = workflow.execute(
            prompt_text_or_request=prompt,
            theme=visual_style,
            customer_name=customer_name,
            industry=industry,
            sales_play=sales_play,
            model_override=selected_model,
        )
        if b64_img:
          raw_img_bytes = (
              base64.b64decode(clean_base64_data(b64_img))
              if isinstance(b64_img, str)
              else b64_img
          )
          high_res_bytes = _ensure_high_res_output_png(
              raw_img_bytes,
              width_pt=680.0,
              height_pt=382.0,
              slide_index=target_slide_index,
          )
          ts_ms = int(time.time() * 1000)
          blob_path = f"nanoBanana_imageGen/ge_visual_{clean_ldap}_{ts_ms}.png"
          primary_bucket = (
              _get_cfg(config, "bucket", "content")
              or _get_cfg(config, "gcs", "content_uploading_bucket")
              or "your-pitchgen-content-bucket"
          )
          project_id = (
              _get_cfg(config, "default", "project_name") or "your-gcp-project-id"
          )
          generated_gcs_uri = upload_bytes_to_gcs(
              high_res_bytes,
              primary_bucket,
              blob_path,
              content_type="image/png",
              project_id=project_id,
              mirror_buckets=[
                  "your-pitchgen-content-bucket",
                  "your-pitchgen-content-bucket",
              ],
          )
          signed_image_url = generate_gcs_v4_signed_url(
              primary_bucket,
              blob_path,
              project_id=project_id,
              expiration_seconds=14400,
              raw_bytes=high_res_bytes,
              mime_type="image/png",
              oauth_token=user_oauth_token or None,
          )
      except Exception as synth_err:
        print(f"[PitchGenSkills] VisualSynthesisWorkflow warning: {synth_err}")

      if presentation_id and (signed_image_url or high_res_bytes):
        try:
          import uuid
          import requests as req_lib
          from pitchgen_utils.image_util import (
              cleanup_temp_drive_docs,
              image_bytes_to_content_uri,
          )

          candidate_tokens = _build_apps_script_candidate_tokens(
              clean_ldap, user_oauth_token, tool_context=tool_context
          )
          new_slide_id = f"pg_vis_{uuid.uuid4().hex[:10]}"
          new_img_id = f"pg_img_{uuid.uuid4().hex[:10]}"
          create_slide_req: Dict[str, Any] = {
              "objectId": new_slide_id,
              "slideLayoutReference": {"predefinedLayout": "BLANK"},
          }
          if 1 <= target_slide_index <= 1000:
            create_slide_req["insertionIndex"] = max(0, target_slide_index - 1)
          used_tok = None
          for _, tok in candidate_tokens:
            if not tok:
              continue
            img_url_to_use = signed_image_url
            if not img_url_to_use and high_res_bytes:
              img_url_to_use, _ = image_bytes_to_content_uri(
                  high_res_bytes, mime_type="image/png", oauth_token=tok
              )
            if not img_url_to_use:
              continue
            resp = req_lib.post(
                f"https://slides.googleapis.com/v1/presentations/{presentation_id}:batchUpdate",
                headers={
                    "Authorization": f"Bearer {tok}",
                    "Content-Type": "application/json",
                },
                json={
                    "requests": [
                        {"createSlide": create_slide_req},
                        {
                            "createImage": {
                                "objectId": new_img_id,
                                "url": img_url_to_use,
                                "elementProperties": {
                                    "pageObjectId": new_slide_id,
                                    "size": {
                                        "width": {
                                            "magnitude": 680,
                                            "unit": "PT",
                                        },
                                        "height": {
                                            "magnitude": 382,
                                            "unit": "PT",
                                        },
                                    },
                                    "transform": {
                                        "scaleX": 1,
                                        "scaleY": 1,
                                        "translateX": 20,
                                        "translateY": 11,
                                        "unit": "PT",
                                    },
                                },
                            }
                        },
                    ]
                },
                timeout=25,
            )
            if resp.status_code != 200 and high_res_bytes:
              c_uri, _ = image_bytes_to_content_uri(
                  high_res_bytes, mime_type="image/png", oauth_token=tok
              )
              if c_uri and c_uri != img_url_to_use:
                resp = req_lib.post(
                    f"https://slides.googleapis.com/v1/presentations/{presentation_id}:batchUpdate",
                    headers={
                        "Authorization": f"Bearer {tok}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "requests": [
                            {"createSlide": create_slide_req},
                            {
                                "createImage": {
                                    "objectId": new_img_id,
                                    "url": c_uri,
                                    "elementProperties": {
                                        "pageObjectId": new_slide_id,
                                        "size": {
                                            "width": {
                                                "magnitude": 680,
                                                "unit": "PT",
                                            },
                                            "height": {
                                                "magnitude": 382,
                                                "unit": "PT",
                                            },
                                        },
                                        "transform": {
                                            "scaleX": 1,
                                            "scaleY": 1,
                                            "translateX": 20,
                                            "translateY": 11,
                                            "unit": "PT",
                                        },
                                    },
                                }
                            },
                        ]
                    },
                    timeout=25,
                )
            if resp.status_code == 200:
              inserted_slide_id = new_slide_id
              used_tok = tok
              break
          try:
            cleanup_temp_drive_docs(
                oauth_token=used_tok or user_oauth_token or None
            )
          except Exception:
            pass
        except Exception as ins_err:
          print(f"[PitchGenSkills] Slide image insertion notice: {ins_err}")

    deck_url = (
        f"https://docs.google.com/presentation/d/{presentation_id}/edit"
        if presentation_id
        else ""
    )
    return json.dumps(
        {
            "status": "success",
            "mode": "transform" if replaced_image_count > 0 else mode,
            "replaced_image_count": replaced_image_count,
            "replaced_gif_count": replaced_gif_count,
            "prompt": prompt,
            "visual_style": visual_style,
            "target_slide_index": target_slide_index,
            "presentation_id": presentation_id,
            "deck_url": deck_url,
            "inserted_slide_id": inserted_slide_id,
            "gcs_uri": generated_gcs_uri,
            "generated_image_url": signed_image_url,
            "customer_name": customer_name,
        },
        indent=2,
    )

  @staticmethod
  def transform_raw_text_skill(
      text: str,
      customization_criteria: str = "Improve clarity and professional tone",
      customer_name: str = "",
      industry: str = "",
      sales_play: str = "",
      tool_context=None,
  ) -> str:
    """Polishes and transforms raw slide text, bullet points, or narrative copy according to GTM copywriting rubrics and Slide Job intensity governance.

    Args:
        text: The raw text, bullet points, or slide content to transform.
        customization_criteria: The editing/polishing goal (e.g., 'Make tone executive for CxO', 'Tailor for Walmart focusing on ROI proof points', 'Condense into 3 high-impact bullets').
        customer_name: Optional target customer name for contextual tailoring.
        industry: Optional customer industry.
        sales_play: Optional Google Cloud sales play.
        tool_context: ADK ToolContext providing user credentials.

    Returns:
        A serialized JSON response containing the original text, transformed text, and applied criteria.
    """
    try:
      from config_loader import load_config
      from agents.workflows.text_transformer_workflow import TextTransformerWorkflow

      config = load_config()
      workflow = TextTransformerWorkflow(config)
      context = {
          "customer_name": customer_name,
          "industry": industry,
          "salesPlay": sales_play,
      }
      transformed = workflow.execute(
          text=text,
          criteria=customization_criteria,
          context=context,
      )
      return json.dumps({
          "status": "success",
          "original_text": text,
          "transformed_text": transformed,
          "criteria_applied": customization_criteria,
          "customer": customer_name or "N/A",
      }, indent=2)
    except Exception as e:
      import traceback
      print(f"[PitchGenSkills] Error in transform_raw_text_skill: {e}")
      traceback.print_exc()
      return json.dumps({"status": "error", "error": str(e), "fallback_text": text})

  @staticmethod
  def enterprise_translate_deck_skill(
      presentation_url_or_id: str = "",
      target_language: str = "Spanish",
      target_slide_indices: str = "",
      translate_instructions: str = "",
      full_deck_scope: bool = False,
      tool_context=None,
  ) -> str:
    """Translates the text in an existing Google Slides presentation (active Canvas presentation or linked from Google Drive) into a target language.

    Args:
        presentation_url_or_id: Google Slides presentation URL, Presentation ID,
          or Drive file reference (auto-resolves from active Canvas deck if
          omitted).
        target_language: Target language for translation (e.g., 'Spanish',
          'German', 'French', 'Japanese', 'de', 'es').
        target_slide_indices: Optional comma-separated slide indices (e.g., '3',
          '1, 2, 4') to translate. If omitted or empty, translates all slides.
        translate_instructions: Optional user instructions or glossary terms.
        full_deck_scope: Whether to force translation across the entire deck.
        tool_context: ADK ToolContext providing user credentials and session
          state.

    Returns:
        A serialized JSON response containing the presentation URL and
        translation status.
    """
    presentation_id, session_ctx = (
        PitchGenSkills._resolve_active_presentation_and_context(
            presentation_url_or_id, tool_context
        )
    )
    if not presentation_id:
      return json.dumps({
          "status": "error",
          "error": (
              "No active presentation found to translate. Please generate or"
              " provide a Google Slides presentation first."
          ),
      })

    lang_name, lang_code = resolve_target_language(target_language)

    user_email = ""
    user_ldap = ""
    user_oauth_token = ""
    if tool_context is not None:
      user_email, user_ldap = extract_session_user_email_and_ldap(tool_context)
      try:
        from oauth_helper import get_user_access_token
        silent_token = get_user_access_token(user_ldap)
        if silent_token:
          user_oauth_token = silent_token
      except Exception:
        pass

    if not user_ldap:
      user_ldap = os.environ.get("USER", "user")

    clean_ldap = user_ldap.split("@")[0].lower().strip()
    presentation_url = (
        f"https://docs.google.com/presentation/d/{presentation_id}/edit"
    )

    effective_target_slides = (
        "" if full_deck_scope else str(target_slide_indices or "").strip()
    )
    scope_criteria = (
        f"Translate slide text on slide(s) {effective_target_slides} into"
        f" {lang_name} ({lang_code})"
        if effective_target_slides
        else f"Translate all slide text into {lang_name} ({lang_code})"
    )
    if translate_instructions:
      scope_criteria += (
          f". Translation instructions / glossary: {translate_instructions}"
      )
    print(
        f"[PitchGenSkills] Translating presentation '{presentation_id}' to"
        f" '{lang_name}' ({lang_code}) for user '{clean_ldap}'"
        f" (slides='{effective_target_slides or 'ALL'}')..."
    )

    rest_result: Dict[str, Any] = {}
    candidate_tokens = _build_apps_script_candidate_tokens(
        clean_ldap, user_oauth_token, tool_context=tool_context
    )
    try:
      rest_result = PitchGenSkills._transform_presentation_slides_via_rest_api(
          presentation_id=presentation_id,
          customization_criteria=scope_criteria,
          target_slide_indices=effective_target_slides,
          customer_name=str(session_ctx.get("customer_name") or ""),
          industry=str(session_ctx.get("industry") or ""),
          sales_play=str(session_ctx.get("salesPlay") or ""),
          target_language=f"{lang_name} ({lang_code})",
          candidate_tokens=candidate_tokens,
      )
    except Exception as rest_err:
      print(
          f"[PitchGenSkills] REST API translation fallback notice: {rest_err}"
      )

    if rest_result.get("status") != "success" and not candidate_tokens:
      auth_url = get_authorization_url(clean_ldap or "unknown")
      return json.dumps(
          {
              "status": "auth_required",
              "auth_url": auth_url,
              "message": (
                  "Please authorize PitchGen to access presentations in your"
                  f" Google Drive by clicking this link: {auth_url}\n\nOnce"
                  " authorized, simply say 'continue' or repeat your request."
              ),
          },
          indent=2,
      )

    deck_url = presentation_url

    result = {
        "status": "success",
        "message": (
            f"Successfully translated presentation to {target_language}:"
            f" {deck_url}"
        ),
        "presentation_id": presentation_id,
        "deck_url": deck_url,
        "target_language": target_language,
        "resolved_language": lang_name,
        "target_slide_indices": effective_target_slides,
        "slides_modified": rest_result.get("slides_modified", 0),
        "customer_name": session_ctx.get("customer_name", ""),
    }
    return json.dumps(result, indent=2)

  @staticmethod
  def sidebar_search(
      search_query: str,
      strict_search: bool = False,
      user_ldap: str = "",
      slide_job: str = "",
  ) -> str:
    """Search for reusable slides based on a search query.

    Args:
        search_query: The query string to search for (e.g. 'Gaming industry').
        strict_search: Whether to perform a strict tag-based search.
        user_ldap: User's LDAP/email.
        slide_job: Target slide job category (e.g. 'Why_Google_Cloud', 'Proof_Points').
    """
    search_query_str = str(search_query).strip()
    if search_query_str.startswith("{"):
      return dispatch_payload(search_query_str)

    print(f"[PitchGenSkills] Sidebar search for: {search_query} (slide_job='{slide_job}')...")
    try:
      import traceback
      from agents.sidebar_agent import sidebar_search as search_impl

      return search_impl(
          search_query,
          strict_search=strict_search,
          user_ldap=user_ldap,
          slide_job=slide_job,
      )
    except Exception as e:
      import traceback

      return json.dumps({"error": f"{str(e)}\n{traceback.format_exc()}"})

  @staticmethod
  def sidebar_generate(
      slide_content: str,
      slide_title: str = "",
      slide_layout: str = "",
      slide_category: str = "",
      deck_id: str = "",
      slide_id: str = "",
      audience: str = "",
      industry: str = "",
      product: str = "",
      region: str = "GLOBAL",
      action: str = "add_generate",
      er_number: str = "21212",
      user_ldap: str = "",
      presentation_id: str = "",
      slide_image_url: str = "",
  ) -> str:
    """Generate a new slide based on the given instructions."""
    slide_content_str = str(slide_content).strip()
    if slide_content_str.startswith("{"):
      return dispatch_payload(slide_content_str)

    print(f"[PitchGenSkills] Sidebar generate for: {slide_title}...")
    try:
      from agents.sidebar_agent import sidebar_generate as generate_impl

      return generate_impl(
          slide_content=slide_content,
          slide_title=slide_title,
          slide_layout=slide_layout,
          slide_category=slide_category,
          deck_id=deck_id,
          slide_id=slide_id,
          audience=audience,
          industry=industry,
          product=product,
          region=region,
          action=action,
          er_number=er_number,
          user_ldap=user_ldap,
          presentation_id=presentation_id,
          slide_image_url=slide_image_url,
      )
    except Exception as e:
      import traceback

      return json.dumps({"error": f"{str(e)}\n{traceback.format_exc()}"})

  @staticmethod
  def process_json_payload(request_file_url: str) -> str:
    """Translates slide texts based on the provided GCS package file.

    Args:
        request_file_url: GCS path containing the slides translation package.

    Returns:
        A serialized JSON string containing the GCS path of the translated
        response: {"response": "gs://..."}.
    """
    request_file_url_str = str(request_file_url).strip()
    if request_file_url_str.startswith("{"):
      return dispatch_payload(request_file_url_str)

    print(f"[PitchGenSkills] Translating slides payload: {request_file_url}...")
    config = load_config()
    try:
      from workflows.translation_workflow import TranslationWorkflow

      skill = TranslationWorkflow(config)
      result_url = skill.execute(request_file_url)

      # DB Logging Translation removed

      return json.dumps({"response": result_url})
    except Exception as e:
      return json.dumps({"error": str(e)})

  @staticmethod
  def transform_visual(request_file_url: str) -> str:
    """Transforms a slide layout or revises its content based on GCS input package.

    Args:
        request_file_url: GCS path containing the slide transformation request.

    Returns:
        A serialized JSON string containing the GCS path of the transformed
        response: {"response": "gs://..."}.
    """
    request_file_url_str = str(request_file_url).strip()
    if request_file_url_str.startswith("{"):
      return dispatch_payload(request_file_url_str)

    print(f"[PitchGenSkills] Reshuffling slide payload: {request_file_url}...")
    config = load_config()
    try:
      from workflows.reshuffle_workflow import ReshuffleWorkflow

      skill = ReshuffleWorkflow(config)
      result_url = skill.execute(request_file_url)

      # DB Logging Reshuffle removed

      return json.dumps({"response": result_url})
    except Exception as e:
      return json.dumps({"error": str(e)})

  @staticmethod
  def translate_slide_payload(payload_json: str) -> str:
    """Translates a full presentation JSON object via GCS upload and TranslationWorkflow.

    Args:
        payload_json: JSON string containing 'presentationId', 'targetLanguage',
          and the presentation data mapping dict.
    """
    if isinstance(payload_json, dict):
      payload = payload_json
    else:
      payload_json_str = str(payload_json).strip()
      if payload_json_str.startswith("{"):
        return dispatch_payload(payload_json_str, default_action="translate")
      try:
        payload = robust_json_loads(payload_json_str)
      except Exception as e:
        return json.dumps({"error": f"Failed to parse JSON payload: {str(e)}"})

    print("[PitchGenSkills] Translating slide payload via GCS...")
    try:
      res = execute_gcs_translation(payload)
      return json.dumps(res)
    except Exception as e:
      return json.dumps({"error": str(e)})

  @staticmethod
  def transform_slide_payload(payload_json: str) -> str:
    """Transforms a slide's layout or content directly in-memory.

    Args:
        payload_json: JSON string containing 'action', 'toggle', and target
          params (slide_layout, slide_category, output_criteria,
          slide_image_url).
    """
    payload_json_str = str(payload_json).strip()
    if payload_json_str.startswith("{"):
      return dispatch_payload(payload_json_str, default_action="transform")

    print("[PitchGenSkills] Reshuffling/Polishing slide payload in-memory...")
    config = load_config()
    try:
      from agents.slide_engineering_agent import SlideEngineeringAgent

      agent = SlideEngineeringAgent(config)
      payload = json.loads(payload_json)
      payload["action"] = "transform"
      result = agent.run_payload(payload)
      return json.dumps(result)
    except Exception as e:
      return json.dumps({"error": str(e)})

  @staticmethod
  def generate_visual_payload(payload_json: str) -> str:
    """Generates new visuals or transforms existing slide images in-memory.

    Args:
        payload_json: JSON string containing either 'user_inputs' (for
          generation) or 'existing_slide_image_url' (for transformation).
    """
    payload_json_str = str(payload_json).strip()
    if payload_json_str.startswith("{"):
      return dispatch_payload(payload_json_str)

    print("[PitchGenSkills] Generating/Transforming slide visual in-memory...")
    config = load_config()
    try:
      from agents.visual_agent import VisualAgent

      agent = VisualAgent(config)
      payload = json.loads(payload_json)
      result = agent.run_payload(payload)
      return json.dumps(result)
    except Exception as e:
      import traceback

      return json.dumps({"error": f"{str(e)}\n{traceback.format_exc()}"})

  @staticmethod
  def sales_play(request_file_url: str) -> str:
    """Processes Sales Play customized deck copy and customer research content generation.

    Args:
        request_file_url: GCS path containing the sales play request.

    Returns:
        A serialized JSON string containing the GCS path of the final response:
        {"response": "gs://..."}.
    """
    print(
        f"[PitchGenSkills] Processing Sales Play payload: {request_file_url}..."
    )
    config = load_config()
    try:
      from agents.workflows.sales_play_workflow import SalesPlayWorkflow

      skill = SalesPlayWorkflow(config)
      result_url = skill.execute(request_file_url)
      return json.dumps({"response": result_url})
    except Exception as e:
      return json.dumps({"error": str(e)})

  @staticmethod
  def debug_list_dir(path: str = ".") -> str:
    """Debug tool to list files in the container.

    Args:
        path: The root path to search.
    """
    try:
      import os
      import sys

      info = {
          "cwd": os.getcwd(),
          "sys_path": sys.path,
          "listdir": os.listdir("."),
      }
      return json.dumps(info)
    except Exception as e:
      return str(e)


class SlideGeneratorTool(BaseAuthenticatedTool):
  """Phase 2: Generates the final deck structure (content synthesis & slide mapping)

  based on the provided (and potentially refined) GlobalState.
  """

  def __init__(self, auth_config: AuthConfig = None) -> None:
    super().__init__(
        name="slide_generator_skill",
        description=(
            "Phase 2: Generates the final deck structure (content synthesis &"
            " slide mapping) based on the provided GlobalState."
        ),
        auth_config=auth_config,
    )

  def _get_declaration(self) -> types.FunctionDeclaration:
    return types.FunctionDeclaration(
        name=self.name,
        description=self.description,
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "state_json": types.Schema(
                    type="STRING",
                    description=(
                        "Serialized GlobalState JSON string, containing"
                        " potentially modified agendas."
                    ),
                )
            },
            required=["state_json"],
        ),
    )

  async def _run_async_impl(
      self,
      *,
      args: dict[str, Any],
      tool_context: ToolContext,
      credential: AuthCredential,
  ) -> Any:
    state_json = args.get("state_json")
    
    import sys
    print(f"[SlideGeneratorTool] _run_async_impl: tool_context.user_id={tool_context.user_id}", file=sys.stderr)
    if tool_context.session:
      print(f"[SlideGeneratorTool] _run_async_impl: tool_context.session.id={tool_context.session.id}", file=sys.stderr)

    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        PitchGenSkills.slide_generator_skill,
        state_json,
        "gemini_enterprise",
        credential
    )
    return result


# Initialize SlideGeneratorTool with auth config if Agent Identity is available
_config = load_config()
_connector_name = _config["default"].get(
    "auth_connector",
    "projects/your-gcp-project-id/locations/us-central1/connectors/gws-slides-connector",
)
if HAS_AGENT_IDENTITY and _connector_name and _connector_name.strip() and _connector_name.lower() != "none":
  _continue_uri = _config["default"].get("continue_uri")
  if _continue_uri == "https://google.com":
    _continue_uri = None
  _auth_scheme = GcpAuthProviderScheme(
      name=_connector_name,
      scopes=[
          "https://www.googleapis.com/auth/presentations",
          "https://www.googleapis.com/auth/drive",
      ],
      continue_uri=_continue_uri,
  )
  _auth_config = AuthConfig(auth_scheme=_auth_scheme)
  slide_generator_tool = SlideGeneratorTool(auth_config=_auth_config)
else:
  print("[PitchGen] Falling back to non-authenticated slide_generator_skill.", file=sys.stderr)
  slide_generator_tool = PitchGenSkills.slide_generator_skill


# Create the Agent for ADK Web UI
config = load_config()
project_id = config.get("default", "project_name")
region = config.get("default", "region", fallback="us-central1")
model_name = config.get(
    "default", "gemini_model", fallback="gemini-3.8-flash"
)

# Use 'global' location for the model path since gemini-3.8-flash and all other
# listed models in this project are accessible via the 'global' location.
model_region = "global"


def route_payload_before_model(callback_context, llm_request):
  if not llm_request.contents:
    return None

  last_content = llm_request.contents[-1]
  if not last_content.parts:
    return None

  last_part = last_content.parts[-1]
  if not last_part.text:
    return None

  text = last_part.text.strip()
  if text.startswith('"') and text.endswith('"'):
    try:
      import json
      parsed = json.loads(text)
      if isinstance(parsed, str):
        text = parsed.strip()
    except Exception:
      pass

  if not text.startswith("{"):
    return None

  try:
    print("[PitchGenSkills] before_model_callback: Intercepting JSON payload...")
    client_src = "slides_extension"
    try:
      import json
      parsed_payload = json.loads(text)
      if isinstance(parsed_payload, dict):
        inner_payload = (
            parsed_payload.get("data")
            if parsed_payload.get("kind") == "data"
            and isinstance(parsed_payload.get("data"), dict)
            else parsed_payload
        )
        a2ui_keys = {
            "event",
            "userAction",
            "clientAction",
            "surfaceId",
            "sourceComponentId",
            "target_card",
            "targetCard",
            "workflow_mode",
            "workflowMode",
            "actionName",
        }
        a2ui_action_names = {
            "launch_feature",
            "launch_feature_card",
            "create_proposal_outline",
            "generate_outline",
            "approve_outline",
            "approve_outline_and_generate",
            "generate_deck",
            "refine_outline",
            "refine_proposal_outline",
            "insert_library_slide",
            "transform_slide_text",
            "transform_deck_text",
            "transform_with_nano_banana",
            "generate_visuals",
        }
        if (
            parsed_payload.get("kind") == "data"
            or "version" in parsed_payload
            or "version" in inner_payload
            or bool(a2ui_keys.intersection(parsed_payload.keys()))
            or bool(a2ui_keys.intersection(inner_payload.keys()))
            or isinstance(parsed_payload.get("action"), dict)
            or isinstance(inner_payload.get("action"), dict)
            or parsed_payload.get("name") in a2ui_action_names
            or inner_payload.get("name") in a2ui_action_names
        ):
          print(
              "[PitchGenSkills] before_model_callback: Detected A2UI event"
              " payload; passing through to enterprise_agent."
          )
          return None
        if "client_source" in parsed_payload:
          client_src = parsed_payload["client_source"]
    except Exception:
      pass
    result_str = dispatch_payload(text, client_source=client_src)
    from google.adk.models.llm_response import LlmResponse
    from google.genai.types import Content, Part
    str_output = json.dumps(result_str) if isinstance(result_str, (dict, list)) else str(result_str or "")
    if "Unknown payload format or action" in str_output:
      print(
          "[PitchGenSkills] before_model_callback: Unrecognized JSON payload;"
          " passing through to LLM."
      )
      return None
    return LlmResponse(
        content=Content(
            role="model",
            parts=[Part.from_text(text=str_output)]
        )
    )
  except Exception as e:
    print(f"[PitchGenSkills] before_model_callback: Error during dispatch: {e}")
    return None


root_agent = Agent(
    name="pitchgen_multiagent",
    before_model_callback=route_payload_before_model,
    model=f"projects/{project_id}/locations/{model_region}/publishers/google/models/{model_name}",
    description=(
        "A powerful agent for automating sales pitch deck blueprints using the"
        " Coordinator-Agent-Skill hierarchy."
    ),
    instruction=(
        "You are the PitchGen ADK 2.0 Orchestrator. Your mission is to assist"
        " users in creating professional sales pitch blueprints.\n\nThis is a"
        " two-phase process for generating new pitch decks:\n1. Phase 1"
        " (Outline Generation): Use the 'create_proposal_outline' tool to"
        " generate the initial outline and agendas. CRITICAL: After Phase 1"
        " completes, you MUST STOP, present the outline/agendas to the user,"
        " and ask them to validate, edit, or approve it. Do NOT call"
        " 'slide_generator_skill' yet!\n2. Phase 2 (Final Deck Generation):"
        " Once the user has reviewed and explicitly approved or modified the"
        " outline, take that outline (represented as the state JSON,"
        " incorporating any edits they provided) and call the"
        " 'slide_generator_skill' tool to generate the final deck"
        " structure.\n\nCRITICAL USER-FACING RULE: When presenting the output of"
        " 'slide_generator_skill' (Phase 2), you MUST ONLY present the"
        " 'deck_url' (the Google Slides presentation link) to the user. You"
        " MUST NEVER print, list, or reference the GCS paths (e.g., gs://...),"
        " intermediate JSON filenames (e.g., architectural_*.json,"
        " *_outputs.json), or raw JSON structures returned by the tool. If"
        " 'deck_url' is not present in the tool response, explain that the"
        " slide generation succeeded but the link is not available, and do NOT"
        " show the GCS files.\n\nFor other features:\n- For slide"
        " translation, use the 'process_json_payload' tool (or the direct"
        " 'translate_slide_payload' tool).\n- For slide visual transformation"
        " or content revision, use the 'transform_visual' tool (or the direct"
        " 'transform_slide_payload' tool).\n- For generating or transforming"
        " slide images, use 'generate_visual_payload'.\n- For automated Sales"
        " Play assembly and insights generation, use the 'sales_play' tool.\n-"
        " For searching reusable slides in the sidebar, use 'sidebar_search'.\n-"
        " For generating new slides in the sidebar, use 'sidebar_generate'."
    ),
    tools=[
        PitchGenSkills.create_proposal_outline,
        slide_generator_tool,
        PitchGenSkills.process_json_payload,
        PitchGenSkills.translate_slide_payload,
        PitchGenSkills.transform_visual,
        PitchGenSkills.transform_slide_payload,
        PitchGenSkills.generate_visual_payload,
        PitchGenSkills.sales_play,
        PitchGenSkills.sidebar_search,
        PitchGenSkills.sidebar_generate,
        PitchGenSkills.debug_list_dir,
        PitchGenSkills.submit_authorization_code,
        GTMSkills.phub_handoff_skill,
        GTMSkills.rfp_accelerator_skill,
    ],
)

from google.adk.apps.app import App

_existing_ge_mod = sys.modules.get("enterprise_agent")
if _existing_ge_mod is not None and not hasattr(
    _existing_ge_mod, "enterprise_agent"
):
  # enterprise_agent is currently importing agent.py; it will bind agent.root_agent and agent.app upon completion
  app = App(root_agent=root_agent, name="src")
else:
  try:
    from enterprise_agent import enterprise_agent as _ge_root_agent, app as _ge_app

    root_agent = _ge_root_agent
    app = _ge_app
  except Exception as _ge_err:
    print(
        f"[PitchGen] Falling back to base root_agent ({_ge_err})",
        file=sys.stderr,
    )
    app = App(root_agent=root_agent, name="src")

if __name__ == "__main__":
  print(f"Agent {root_agent.name} is ready for ADK Web UI.")
