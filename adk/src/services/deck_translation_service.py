"""Deck Translation Service.

Dedicated workflow for translating entire Google Slides presentations headlessly
into target languages using Gemini Enterprise TranslationWorkflow and Apps
Script.
"""

import json
import os
import re
import sys
from typing import Any
import uuid

# Ensure parent directory (src/) is in sys.path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
  sys.path.insert(0, parent_dir)

import requests
from config_loader import load_config
from google.cloud import storage
from oauth_helper import (
    get_adc_bearer_token,
    get_enduser_bearer_token,
    get_user_access_token,
    resolve_user_ldap,
)


def extract_presentation_id(prompt_text: str, tool_context=None) -> str:
  """Extracts Presentation ID from Drive attachments, user_content parts, URLs, or raw ID strings."""
  prompt_text = prompt_text or ""

  # 1. First Priority: Check explicit Google Slides / Drive URL in current prompt text
  slides_url_match = re.search(
      r"docs\.google\.com/presentation/d/([a-zA-Z0-9_-]{25,65})", prompt_text
  )
  drive_url_match = re.search(
      r"drive\.google\.com/file/d/([a-zA-Z0-9_-]{25,65})", prompt_text
  )
  if slides_url_match:
    return slides_url_match.group(1).strip()
  if drive_url_match:
    return drive_url_match.group(1).strip()

  # 2. Second Priority: Check current request file attachments / user_content parts
  if tool_context:
    # A. Check user_content parts (where Gemini Enterprise UI attaches Drive file chips)
    user_content = getattr(tool_context, "user_content", None)
    if user_content:
      parts = getattr(user_content, "parts", []) or []
      for p in parts:
        p_str = str(p)
        if "memory://" in p_str or "artifacts/" in p_str:
          continue
        file_data = getattr(p, "file_data", None)
        file_uri = getattr(file_data, "file_uri", "") if file_data else ""
        uri = (
            getattr(p, "uri", "")
            or getattr(p, "gcs_uri", "")
            or file_uri
            or p_str
        )
        match = re.search(r"([a-zA-Z0-9_-]{25,65})", str(uri))
        if (
            match
            and len(match.group(1)) >= 25
            and not match.group(1).startswith("start_of_user_uploaded")
            and not match.group(1).startswith("end_of_user_uploaded")
        ):
          print(
              f"[extract_presentation_id] Found Drive ID '{match.group(1)}' in"
              " user_content part!"
          )
          return match.group(1).strip()

    # B. Check current request attachments
    attachments = (
        getattr(tool_context, "attachments", None)
        or getattr(tool_context, "files", None)
        or getattr(tool_context, "input_files", None)
        or []
    )
    if isinstance(tool_context, dict):
      attachments = (
          tool_context.get("attachments", [])
          or tool_context.get("files", [])
          or tool_context.get("input_files", [])
      )

    for att in attachments:
      if isinstance(att, dict):
        for field in [
            "file_id",
            "id",
            "presentationId",
            "drive_id",
            "driveId",
            "uri",
            "url",
            "resourceName",
            "name",
            "gcs_uri",
        ]:
          val = str(att.get(field, "") or "").strip()
          match = re.search(r"([a-zA-Z0-9_-]{25,65})", val)
          if (
              match
              and len(match.group(1)) >= 25
              and not match.group(1).startswith("start_of_user_uploaded")
              and not match.group(1).startswith("end_of_user_uploaded")
          ):
            print(
                f"[extract_presentation_id] Found Drive ID '{match.group(1)}'"
                f" in field '{field}' of attachment dict: {att}"
            )
            return match.group(1).strip()
      else:
        att_str = str(att)
        match = re.search(r"([a-zA-Z0-9_-]{25,65})", att_str)
        if (
            match
            and len(match.group(1)) >= 25
            and not match.group(1).startswith("start_of_user_uploaded")
            and not match.group(1).startswith("end_of_user_uploaded")
        ):
          print(
              f"[extract_presentation_id] Found Drive ID '{match.group(1)}' in"
              f" attachment string: {att_str}"
          )
          return match.group(1).strip()

  # 3. Third Priority: Check Upload from Drive placeholder tag <start_of_user_uploaded_file: title>
  tag_match = re.search(
      r"<start_of_user_uploaded_file:\s*([^>]+)>", prompt_text
  )
  if tag_match:
    title = tag_match.group(1).strip()
    tag_id_match = re.search(r"([a-zA-Z0-9_-]{25,65})", title)
    if (
        tag_id_match
        and len(tag_id_match.group(1)) >= 25
        and not tag_id_match.group(1).startswith("start_of_user_uploaded")
    ):
      return tag_id_match.group(1).strip()
    print(
        f"[extract_presentation_id] Extracted presentation title '{title}' from"
        " Upload from Drive tag!"
    )
    res = title
    if "/" in res:
      res = os.path.basename(res)
    if "." in res:
      res = os.path.splitext(res)[0]
    return res

  # 4. Fourth Priority: Raw ID match in prompt text (with hyphens & underscores)
  raw_id_match = re.search(
      r"(?:^|[\s\"/:=])([a-zA-Z0-9_-]{25,65})(?:$|[\s\"/?#])", prompt_text
  )
  if (
      raw_id_match
      and not raw_id_match.group(1).startswith("start_of_user_uploaded")
      and not raw_id_match.group(1).startswith("end_of_user_uploaded")
  ):
    return raw_id_match.group(1).strip()

  # 5. Last Fallback: Historical artifact_service memory
  if tool_context:
    inv_ctx = getattr(tool_context, "_invocation_context", None) or getattr(
        tool_context, "invocation_context", None
    )
    if inv_ctx:
      art_svc = getattr(inv_ctx, "artifact_service", None)
      if art_svc:
        artifacts = getattr(art_svc, "artifacts", {}) or {}
        for art_key, art_val in artifacts.items():
          match = re.search(
              r"([a-zA-Z0-9_-]{25,65})", str(art_key) + str(art_val)
          )
          if (
              match
              and len(match.group(1)) >= 25
              and not match.group(1).startswith("start_of_user_uploaded")
              and not match.group(1).startswith("end_of_user_uploaded")
          ):
            print(
                f"[extract_presentation_id] Found Drive ID '{match.group(1)}'"
                " in artifact_service!"
            )
            return match.group(1).strip()

  res = prompt_text.strip()
  if "/" in res:
    res = os.path.basename(res)
  if "." in res:
    res = os.path.splitext(res)[0]

  return res


def call_apps_script_web_app(
    payload: dict, user_ldap: str = None, tool_context=None
) -> dict:
  """Generic HTTP POST invoker for the PitchGen Apps Script Web App."""
  user_ldap = resolve_user_ldap(
      user_ldap or payload.get("user_ldap"), tool_context=tool_context
  )

  try:
    config = load_config()
    url = config.get("appscript", "url")
  except Exception:
    url = "https://script.google.com/macros/s/YOUR_APPS_SCRIPT_DEPLOYMENT_ID/exec"

  class AuthPreservingSession(requests.Session):

    def rebuild_auth(self, prepared_request, response):
      if "Authorization" in response.request.headers:
        prepared_request.headers["Authorization"] = response.request.headers[
            "Authorization"
        ]

  session = AuthPreservingSession()
  tokens = [
      get_enduser_bearer_token(tool_context=tool_context),
      get_user_access_token(user_ldap),
      get_adc_bearer_token(),
  ]

  for token in tokens:
    if not token:
      continue
    try:
      headers = {
          "Authorization": f"Bearer {token}",
          "Content-Type": "application/json",
      }
      response = session.post(url, headers=headers, json=payload, timeout=300)
      if response.status_code == 200 and not response.text.startswith(
          "<!DOCTYPE html>"
      ):
        try:
          return response.json()
        except Exception:
          return {"status": 200, "raw": response.text.strip()}
    except Exception:
      pass

  return {"status": 500, "error": "Failed to reach Apps Script Web App"}


def resolve_target_language(target_lang_input: str) -> tuple[str, str]:
  """Resolves natural language input or ISO code to (Language Name, ISO Code)."""
  if not target_lang_input:
    return ("German", "de")

  translate_config_path = os.path.join(parent_dir, "config", "translate.json")
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
        "de": "German",
        "es": "Spanish",
        "fr": "French",
        "id": "Indonesian",
        "it": "Italian",
        "pt": "Portuguese",
        "ja": "Japanese",
        "ko": "Korean",
        "zh-TW": "Chinese (Traditional)",
        "zh-CN": "Chinese (Simplified)",
        "da": "Danish",
        "nl": "Dutch",
        "fi": "Finnish",
        "el": "Greek",
        "pl": "Polish",
        "sv": "Swedish",
        "th": "Thai",
        "en": "English",
    }
    lang_to_code = {v.lower(): k for k, v in code_to_lang.items()}

  clean_input = target_lang_input.strip()
  lower_input = clean_input.lower()
  norm_input = re.sub(r"[^a-z0-9]", "", lower_input)

  code_to_lang_lower = {k.lower(): (v, k) for k, v in code_to_lang.items()}
  if lower_input in code_to_lang_lower:
    lang_name, orig_code = code_to_lang_lower[lower_input]
    return (lang_name, orig_code)

  aliases = {
      "chinesesimplified": ("Chinese (Simplified)", "zh-CN"),
      "simplifiedchinese": ("Chinese (Simplified)", "zh-CN"),
      "chinesetraditional": ("Chinese (Traditional)", "zh-TW"),
      "traditionalchinese": ("Chinese (Traditional)", "zh-TW"),
      "chinese": ("Chinese (Simplified)", "zh-CN"),
      "zhcn": ("Chinese (Simplified)", "zh-CN"),
      "zhtw": ("Chinese (Traditional)", "zh-TW"),
  }
  if norm_input in aliases:
    return aliases[norm_input]

  if lower_input in code_to_lang:
    return (code_to_lang[lower_input], lower_input)

  if lower_input in lang_to_code:
    code = lang_to_code[lower_input]
    return (code_to_lang[code], code)

  for name_lower, code in lang_to_code.items():
    norm_name = re.sub(r"[^a-z0-9]", "", name_lower)
    if norm_name in norm_input or norm_input in norm_name:
      return (code_to_lang[code], code)

  return ("German", "de")


def execute_gcs_translation(payload: dict) -> dict:
  """Uploads extraction payload to GCS and triggers TranslationWorkflow."""
  print("[DeckTranslationService] Starting GCS-based slide translation...")
  config = load_config()
  project_id = config["default"].get("project_name", "your-gcp-project-id")
  presentation_id = payload.get("presentationId")
  if not presentation_id:
    for k in payload.keys():
      if k not in [
          "presentationId",
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
      "bucket", "translation", fallback="translation-uploads-dev-p2"
  )
  request_blob_name = f"{presentation_id}_{unique_id}_Request.json"
  request_gcs_url = f"gs://{request_bucket_name}/{request_blob_name}"

  print(
      "[DeckTranslationService] Uploading request payload to GCS URL:"
      f" {request_gcs_url}..."
  )
  storage_client = storage.Client(project=project_id)
  req_bucket = storage_client.bucket(request_bucket_name)
  req_blob = req_bucket.blob(request_blob_name)
  req_blob.upload_from_string(
      json.dumps(payload, indent=2), content_type="application/json"
  )

  print("[DeckTranslationService] Executing TranslationWorkflow...")
  from agents.workflows.translation_workflow import TranslationWorkflow

  skill = TranslationWorkflow(config)
  response_gcs_url = skill.execute(request_gcs_url)
  print(
      "[DeckTranslationService] Translation complete. Response URL:"
      f" {response_gcs_url}"
  )

  return {
      "data": {"request": request_gcs_url, "response": response_gcs_url},
      "message": "Success",
  }


class DeckTranslationService:
  """Dedicated, self-contained service for Google Slides translation."""

  @staticmethod
  def _normalize_language_input(val: Any) -> str:
    """Normalizes a single or multi-select A2UI ChoicePicker language value into a clean string."""
    if val is None:
      return ""
    skip_tokens = {
        "",
        "none",
        "null",
        "select language",
        "— (blank)",
        "-(blank)",
    }
    if isinstance(val, (list, tuple)):
      for item in val:
        s_item = str(item).strip()
        if s_item and s_item.lower() not in skip_tokens:
          return s_item
      return ""
    s_val = str(val).strip()
    if s_val.lower() in skip_tokens:
      return ""
    return s_val

  @staticmethod
  def _parse_target_slide_indices(
      target_slide_numbers: str, full_deck_scope=None
  ) -> set[int]:
    """Parses comma-separated slide numbers and ranges (e.g. '1, 2, 4-6') into 1-based integer indices.

    Returns an empty set if Full Deck is selected or no specific slides are
    requested.
    """
    if full_deck_scope is not None:
      if isinstance(full_deck_scope, list) and any(
          str(x).strip().lower() in ("full_deck", "all", "true")
          for x in full_deck_scope
      ):
        return set()
      if isinstance(full_deck_scope, bool) and full_deck_scope:
        return set()
      if isinstance(
          full_deck_scope, str
      ) and full_deck_scope.strip().lower() in (
          "full_deck",
          "all",
          "true",
      ):
        return set()

    raw = str(target_slide_numbers or "").strip()
    if not raw or raw.lower() in ("all", "full", "full_deck", "full deck"):
      return set()

    indices: set[int] = set()
    for rng_match in re.finditer(r"(\d+)\s*-\s*(\d+)", raw):
      start_idx = int(rng_match.group(1))
      end_idx = int(rng_match.group(2))
      if start_idx <= end_idx:
        indices.update(range(start_idx, end_idx + 1))
      else:
        indices.update(range(end_idx, start_idx + 1))

    remaining = re.sub(r"\d+\s*-\s*\d+", " ", raw)
    for num_str in re.findall(r"\d+", remaining):
      idx = int(num_str)
      if idx >= 1:
        indices.add(idx)

    return indices

  @staticmethod
  def translate_presentation_deck(
      presentation_identifier: str = "",
      target_language: Any = "German",
      translate_instructions: str = "",
      target_slide_numbers: str = "",
      full_deck_scope=None,
      tool_context=None,
  ) -> str:
    """Translates an entire Google Slides presentation deck (or specified slides) headlessly into any target language (e.g. German, Spanish, French, Chinese, Japanese, Korean, Italian, Portuguese, Dutch, etc.).

    CRITICAL: ALWAYS use this tool whenever the user asks to translate a
    presentation deck, convert its language, or specifies a target language.
    NEVER use transform_deck_text for translation requests.
    TERMINAL: After calling this tool, do NOT call create_proposal_outline or
    any other tool.

    Args:
        presentation_identifier: The Google Slides URL, Drive file URL, or
          44-character Presentation ID.
        target_language: Target language name or code (e.g. 'German', 'Spanish',
          'French', 'Japanese', 'Chinese', 'de', 'es', 'zh-CN', 'zh-TW').
        translate_instructions: Optional custom translation instructions,
          terminology glossary, or tone criteria from the Translate card.
        target_slide_numbers: Optional comma-separated slide numbers or ranges
          (e.g. '1, 2, 4-6') when Full Deck is unchecked.
        full_deck_scope: Optional full deck scope flag/list (e.g. ['full_deck']
          or []) from the A2UI Translate card.
        tool_context: ADK ToolContext providing user credentials and session
          state.
    """
    pres_id = extract_presentation_id(presentation_identifier, tool_context)
    if (
        not pres_id
        or pres_id.startswith("start_of_user_uploaded")
        or pres_id.startswith("end_of_user_uploaded")
    ):
      return (
          "Error: Could not extract a valid Google Slides Presentation ID or"
          f" file title from '{presentation_identifier}'. "
          "Please paste the full Google Slides presentation URL directly in"
          " your prompt text (e.g."
          " https://docs.google.com/presentation/d/SAMPLE_PRESENTATION_ID_PLACEHOLDER_00004/edit)."
      )

    normalized_lang = DeckTranslationService._normalize_language_input(
        target_language
    )
    lang_name, lang_code = resolve_target_language(normalized_lang or "German")
    user_ldap = resolve_user_ldap(
        getattr(tool_context, "user_id", ""),
        tool_context=tool_context,
    )
    clean_instructions = str(translate_instructions or "").strip()
    target_indices_set = DeckTranslationService._parse_target_slide_indices(
        target_slide_numbers, full_deck_scope=full_deck_scope
    )
    effective_slide_numbers = (
        ", ".join(str(i) for i in sorted(target_indices_set))
        if target_indices_set
        else ""
    )

    print(
        f"[DeckTranslationService] Translating deck '{pres_id}' into"
        f" {lang_name} ({lang_code})"
        f" (scope='{f'Slides {effective_slide_numbers}' if effective_slide_numbers else 'Full Deck'}',"
        f" instructions='{clean_instructions[:80]}') for user '{user_ldap}'..."
    )

    # Step 1: Call Apps Script Web App to extract deck text headlessly
    extract_payload = {
        "action": "extract_deck_text",
        "presentationId": pres_id,
        "targetLanguage": lang_name,
        "isFullDeckTranslation": not bool(target_indices_set),
        "user_ldap": user_ldap,
    }

    try:
      web_app_resp = call_apps_script_web_app(
          extract_payload, user_ldap=user_ldap, tool_context=tool_context
      )
      extracted_json = (
          web_app_resp.get("data") if isinstance(web_app_resp, dict) else None
      )
    except Exception as e:
      print(f"[DeckTranslationService] Web App extraction note: {e}")
      extracted_json = None

    resolved_id = (
        extracted_json.get("presentationId", pres_id)
        if isinstance(extracted_json, dict)
        else pres_id
    )
    if not extracted_json or (
        pres_id not in extracted_json and resolved_id not in extracted_json
    ):
      err_msg = (
          web_app_resp.get("error")
          if isinstance(web_app_resp, dict)
          else "Extraction response empty or missing presentation data"
      )
      print(f"[DeckTranslationService] Web App extraction failed: {err_msg}")
      return (
          "Error: Unable to extract text content from presentation deck"
          f" '{pres_id}'. Details: {err_msg}. Please verify that the Google"
          " Slides presentation ID is correct and shared with your account."
      )

    pres_id = resolved_id
    extracted_json["targetLanguage"] = lang_name
    if clean_instructions:
      extracted_json["translateInstructions"] = clean_instructions

    # Filter extracted slides if specific target slide numbers were requested.
    # Keep non-targeted slide keys with empty shapes/tables so Apps Script
    # translationFromModalHeadless preserves the exact 0-based slideIndex
    # (e.g. slideIndex 0 = Enablement slide, slideIndex 1 = Hero cover slide).
    pres_slides = extracted_json.get(pres_id)
    if target_indices_set and isinstance(pres_slides, dict) and pres_slides:
      raw_slide_tokens = {
          t.strip()
          for t in str(target_slide_numbers or "").split(",")
          if t.strip()
      }
      filtered_slides = {}
      matched_count = 0
      for idx_1based, (s_id, s_data) in enumerate(pres_slides.items(), start=1):
        if idx_1based in target_indices_set or s_id in raw_slide_tokens:
          filtered_slides[s_id] = s_data
          matched_count += 1
        else:
          filtered_slides[s_id] = {"shapes": {}, "tables": {}}
      if matched_count > 0:
        print(
            f"[DeckTranslationService] Filtered deck '{pres_id}' to"
            f" {matched_count}/{len(pres_slides)} slide(s) matching indices"
            f" {sorted(target_indices_set)}."
        )
        extracted_json[pres_id] = filtered_slides
        extracted_json["isFullDeckTranslation"] = False
      else:
        return (
            f"Error: Requested target slide numbers ({effective_slide_numbers})"
            f" are out of range for presentation '{pres_id}' (total slides:"
            f" {len(pres_slides)})."
        )

    # Step 2: Execute TranslationWorkflow engine via GCS
    try:
      gcs_result = execute_gcs_translation(extracted_json)
      response_gcs_url = gcs_result.get("data", {}).get("response", "")
      if response_gcs_url.startswith("gs://"):
        parts = response_gcs_url.replace("gs://", "").split("/", 1)
        response_filename = parts[1] if len(parts) > 1 else parts[0]
      else:
        response_filename = response_gcs_url
    except Exception as e:
      print(
          f"[DeckTranslationService] Error executing translation workflow: {e}"
      )
      return f"Error executing translation workflow: {str(e)}"

    # Step 3: Call Apps Script Web App to apply translated JSON back to the deck headlessly
    try:
      cfg = load_config()
      bucket_name = cfg.get(
          "bucket", "content", fallback="your-pitchgen-content-bucket"
      )
    except Exception:
      bucket_name = "your-pitchgen-content-bucket"
    apply_payload = {
        "action": "apply_translation",
        "presentationId": pres_id,
        "bucketName": bucket_name,
        "response_gcs_filename": response_filename,
        "user_ldap": user_ldap,
    }

    try:
      apply_res = call_apps_script_web_app(
          apply_payload, user_ldap=user_ldap, tool_context=tool_context
      )
      if isinstance(apply_res, dict) and (
          apply_res.get("status") == 500
          or (apply_res.get("error") and not apply_res.get("deckURL"))
      ):
        err_detail = (
            apply_res.get("error")
            or "Apps Script failed to apply translated text"
        )
        return (
            f"Error applying translation to presentation '{pres_id}':"
            f" {err_detail}"
        )
      deck_url = apply_res.get(
          "deckURL", f"https://docs.google.com/presentation/d/{pres_id}/edit"
      )
      if "open?id=" in deck_url:
        extracted_id = deck_url.split("open?id=")[-1].split("&")[0]
        deck_url = f"https://docs.google.com/presentation/d/{extracted_id}/edit"
    except Exception as apply_err:
      return (
          f"Error applying translation to presentation '{pres_id}': {apply_err}"
      )

    if effective_slide_numbers:
      return (
          f"🎉 Presentation (Slides {effective_slide_numbers}) successfully"
          f" translated into {lang_name}! View your deck here: {deck_url}"
      )
    return (
        f"🎉 Presentation successfully translated into {lang_name}! View your"
        f" deck here: {deck_url}"
    )
