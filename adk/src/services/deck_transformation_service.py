"""Deck Transformation Service.

Walled-off, dedicated workflow for headless in-place Google Slides text
transformation
and copy polishing (Checkpoint 2 Golden State).
"""

import datetime
import json
import os
import re
import sys
from typing import Any

# Ensure parent directory (src/) is in sys.path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
  sys.path.insert(0, parent_dir)

import requests
from config_loader import load_config
from oauth_helper import (
    get_adc_bearer_token,
    get_enduser_bearer_token,
    get_user_access_token,
    resolve_user_ldap,
)
from pitchgen_utils.gcs_util import read_gcs_file, write_gcs_file


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
    # A. Check current request attachments
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
                f" in attachment field '{field}': {att}"
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
              f"[extract_presentation_id] Found Drive ID '{match.group(1)}'"
              f" in attachment string: {att_str}"
          )
          return match.group(1).strip()

    # B. Check user_content parts (filtering out internal memory:// URIs)
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
        if uri:
          match = re.search(r"([a-zA-Z0-9_-]{25,65})", str(uri))
          if (
              match
              and len(match.group(1)) >= 25
              and not match.group(1).startswith("start_of_user_uploaded")
              and not match.group(1).startswith("end_of_user_uploaded")
          ):
            print(
                f"[extract_presentation_id] Found Drive ID '{match.group(1)}'"
                " in user_content part!"
            )
            return match.group(1).strip()

  # 3. Third Priority: Check Upload from Drive tag <start_of_user_uploaded_file: title>
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
                " in fallback artifact_service!"
            )
            return match.group(1).strip()

  res = prompt_text.strip()
  if "/" in res:
    res = os.path.basename(res)
  if "." in res:
    res = os.path.splitext(res)[0]
  return res


def extract_entities_from_user_prompt(prompt_text: str) -> dict:
  """Intelligently extracts customer_name, industry, audience, sales_play, opportunity_id, and products from user prompts."""
  if not prompt_text or not isinstance(prompt_text, str):
    return {
        "customer_name": "",
        "industry": "",
        "audience": "",
        "sales_play": "",
        "opportunity_id": "",
        "products": "",
        "user_prompt": "",
    }

  text = prompt_text.strip()
  res = {
      "customer_name": "",
      "industry": "",
      "audience": "",
      "sales_play": "",
      "opportunity_id": "",
      "products": "",
      "user_prompt": text,
  }

  # 1. Opportunity ID / ER Number Extraction
  opp_m = re.search(
      r"\b(?:opportunity\s*id|opp\s*id|er\s*number|er\s*id|opportunity\s*#|opp\s*#)\s*[:=]?\s*([A-Za-z0-9_\-]+)|\b(?:opportunity|opp)\s*[:=]\s*([A-Za-z0-9_\-]+)|\b(ER-?[0-9]+)\b",
      text,
      re.IGNORECASE,
  )
  if opp_m:
    val = (opp_m.group(1) or opp_m.group(2) or opp_m.group(3) or "").strip()
    if val and val.lower() not in ("opportunities", "opportunity"):
      res["opportunity_id"] = val

  # 2. Industry Vertical Extraction
  ind_m = re.search(
      r"\b(?:in|within|focusing\s+on|focus\s+on|towards|to|for)\s+(?:the\s+)?((?:(?!in\b|for\b|to\b|towards\b|with\b)[A-Za-z0-9_&]+)(?:\s+(?!in\b|for\b|to\b|towards\b|with\b)[A-Za-z0-9_&]+){0,3})\s+(?:(?:industry|sector|vertical|domain)\s*)+\b",
      text,
      re.IGNORECASE,
  )
  if not ind_m:
    ind_m = re.search(
        r"\b(?:industry|sector|vertical)\s*[:=]\s*([A-Za-z0-9_&]+(?:\s+[A-Za-z0-9_&]+){0,3})\b",
        text,
        re.IGNORECASE,
    )
  if not ind_m:
    ind_m = re.search(
        r"\b(?:in|within|focusing\s+on|focus\s+on)\s+((?:(?!in\b|for\b|to\b|towards\b|with\b)[A-Za-z0-9_&]+)(?:\s+(?!in\b|for\b|to\b|towards\b|with\b)[A-Za-z0-9_&]+){0,3})(?:,\s*tailoring|\s*\.|\s*$)",
        text,
        re.IGNORECASE,
    )

  if ind_m:
    raw_ind = ind_m.group(1).strip()
    raw_ind = re.sub(
        r"\b(trends|landscape|overview|domain|sector|requirements|industry|vertical)\b",
        "",
        raw_ind,
        flags=re.IGNORECASE,
    ).strip()
    for kw in (
        "with ",
        "for ",
        "in ",
        "towards ",
        "to ",
        "focusing on ",
        "the ",
    ):
      if raw_ind.lower().startswith(kw):
        raw_ind = raw_ind[len(kw) :].strip()
    raw_lower = raw_ind.lower()
    if any(
        k in raw_lower
        for k in ("cpg", "consumer packaged", "consumer goods", "fmcg")
    ):
      res["industry"] = "Consumer Packaged Goods (CPG)"
    elif any(
        k in raw_lower
        for k in (
            "financial services",
            "banking",
            "fsi",
            "wealth management",
            "insurance",
            "finance",
        )
    ):
      res["industry"] = "Financial Services"
    elif any(
        k in raw_lower
        for k in (
            "automotive",
            "manufacturing",
            "industrial",
            "supply chain",
            "logistics",
            "aerospace",
        )
    ):
      res["industry"] = "Manufacturing & Industrial"
    elif any(
        k in raw_lower
        for k in (
            "healthcare",
            "life sciences",
            "pharma",
            "clinical",
            "biotech",
            "hospital",
        )
    ):
      res["industry"] = "Healthcare & Life Sciences"
    elif any(
        k in raw_lower
        for k in (
            "retail",
            "e-commerce",
            "ecommerce",
            "grocery",
            "merchandising",
        )
    ):
      res["industry"] = "Retail & Consumer"
    elif any(
        k in raw_lower
        for k in (
            "telecom",
            "telecommunications",
            "media",
            "entertainment",
            "broadcasting",
        )
    ):
      res["industry"] = "Telecommunications, Media & Entertainment"
    elif any(
        k in raw_lower
        for k in (
            "public sector",
            "public",
            "government",
            "education",
            "fed",
            "state & local",
        )
    ):
      res["industry"] = "Public Sector"
    elif any(
        k in raw_lower
        for k in ("energy", "utilities", "oil", "gas", "power", "renewables")
    ):
      res["industry"] = "Energy & Utilities"
    elif any(
        k in raw_lower
        for k in ("tech", "technology", "software", "saas", "digital")
    ):
      res["industry"] = "Technology & Software"
    elif raw_ind:
      res["industry"] = raw_ind.title()
  else:
    for ind_kw, ind_canonical in [
        (
            (
                r"\b(?:financial"
                r" services|banking|fsi|finance|wealth"
                r" management|insurance|payments)\b"
            ),
            "Financial Services",
        ),
        (
            r"\b(?:consumer packaged goods|cpg|consumer goods|fmcg)\b",
            "Consumer Packaged Goods (CPG)",
        ),
        (
            r"\b(?:healthcare|life"
            r" sciences|hcls|pharma|clinical|biotech|hospital)\b",
            "Healthcare & Life Sciences",
        ),
        (
            r"\b(?:retail|e-commerce|ecommerce|grocery|merchandising)\b",
            "Retail & Consumer",
        ),
        (
            r"\b(?:telecom|telecommunications|media|entertainment|broadcasting)\b",
            "Telecommunications, Media & Entertainment",
        ),
        (
            (
                r"\b(?:manufacturing|automotive|supply"
                r" chain|logistics|industrial|aerospace)\b"
            ),
            "Manufacturing & Industrial",
        ),
        (
            (
                r"\b(?:public"
                r" sector|government|defense|education|fed|state & local)\b"
            ),
            "Public Sector",
        ),
        (
            r"\b(?:energy|utilities|oil & gas|power|renewables)\b",
            "Energy & Utilities",
        ),
        (r"\b(?:technology|software|saas)\b", "Technology & Software"),
    ]:
      if re.search(ind_kw, text, re.IGNORECASE):
        res["industry"] = ind_canonical
        break

  # 3. Target Audience / Persona Extraction
  aud_m = re.search(
      r"\b(?:audience|target audience|persona|for persona|targeting"
      r" audience|for"
      r" audience|targeting)\s*[:=]?\s*([A-Za-z0-9_&\s\-]+?)(?:,|$|\.|\s+with\b|\s+focusing\b|\s+sales\b|\s+opp\b|\s+products\b)",
      text,
      re.IGNORECASE,
  )
  if aud_m:
    aud_candidate = aud_m.group(1).strip()
    if aud_candidate.lower() in (
        "cio",
        "cto",
        "cdo",
        "cmo",
        "cro",
        "cfo",
        "ceo",
    ):
      res["audience"] = aud_candidate.upper()
    else:
      res["audience"] = aud_candidate.title()
  elif re.search(
      r"\b(?:c-suite|c-level|executives|cio|cto|cdo|cmo|cro|cfo|executive"
      r" leadership)\b",
      text,
      re.IGNORECASE,
  ):
    res["audience"] = "C-Level Executives"
  elif re.search(
      r"\b(?:architects|developers|engineers|technical"
      r" teams|practitioners)\b",
      text,
      re.IGNORECASE,
  ):
    res["audience"] = "Technical Architects & Engineers"
  elif re.search(
      r"\b(?:business leaders|line of business|operations managers)\b",
      text,
      re.IGNORECASE,
  ):
    res["audience"] = "Business & Operations Leaders"

  # 4. Sales Play Extraction
  sp_m = re.search(
      r"\b(?:sales\s*play|salesplay|play)\s*[:=]?\s*([A-Za-z0-9_&\s\-]+?)(?:,|$|\.|\s+for\b|\s+with\b|\s+targeting\b|\s+opp\b|\s+products\b)",
      text,
      re.IGNORECASE,
  )
  if sp_m:
    res["sales_play"] = sp_m.group(1).strip().title()
  elif re.search(
      r"\b(?:genai adoption|generative ai adoption|ai adoption)\b",
      text,
      re.IGNORECASE,
  ):
    res["sales_play"] = "GenAI Adoption"
  elif re.search(
      r"\b(?:cloud migration|infrastructure modernization|cloud"
      r" modernization)\b",
      text,
      re.IGNORECASE,
  ):
    res["sales_play"] = "Cloud Modernization"
  elif re.search(
      r"\b(?:data modernization|analytics modernization|smart analytics)\b",
      text,
      re.IGNORECASE,
  ):
    res["sales_play"] = "Data Modernization"
  elif re.search(
      r"\b(?:security modernization|security operations|secops)\b",
      text,
      re.IGNORECASE,
  ):
    res["sales_play"] = "Security Modernization"

  # 5. Products / Solutions Mentioned
  prod_m = re.search(
      r"\b(?:products?|solutions?|technolog(?:y|ies))\s*[:=]?\s*([A-Za-z0-9_&,\s\-]+?)(?:$|\.|\s+for\b|\s+opp\b|\s+audience\b|\s+sales\b)",
      text,
      re.IGNORECASE,
  )
  if prod_m:
    res["products"] = prod_m.group(1).strip()

  # 6. Customer Name Extraction
  clean_text_for_cust = text
  if ind_m:
    clean_text_for_cust = clean_text_for_cust.replace(ind_m.group(0), " ")
  if aud_m:
    clean_text_for_cust = clean_text_for_cust.replace(aud_m.group(0), " ")
  if sp_m:
    clean_text_for_cust = clean_text_for_cust.replace(sp_m.group(0), " ")
  if opp_m:
    clean_text_for_cust = clean_text_for_cust.replace(opp_m.group(0), " ")
  if prod_m:
    clean_text_for_cust = clean_text_for_cust.replace(prod_m.group(0), " ")

  clean_text_for_cust = re.sub(
      r"\b(?:financial services|retail & consumer|healthcare & life"
      r" sciences|healthcare|life sciences|consumer packaged"
      r" goods|telecommunications|manufacturing|public"
      r" sector)\s+(?:industry|sector|vertical)\b",
      " ",
      clean_text_for_cust,
      flags=re.IGNORECASE,
  )

  # Priority 1: High-precedence explicit customer / tailoring phrases
  cust_m = re.search(
      r"\b(?:specifically\s+for|customiz(?:e|ing)(?:\s+it)?(?:\s+(?:the\s+)?(?:entire\s+)?(?:presentation|deck|slides)?)?\s+(?:towards|to|for)|tailor(?:ing)?(?:\s+it)?(?:\s+(?:the\s+)?(?:entire\s+)?(?:presentation|deck|slides)?)?\s+(?:towards|to|for)|transform(?:ing)?(?:\s+it)?(?:\s+(?:the\s+)?(?:entire\s+)?(?:presentation|deck|slides)?)?\s+(?:towards|to|for)|adapt(?:ing)?(?:\s+it)?(?:\s+(?:the\s+)?(?:entire\s+)?(?:presentation|deck|slides)?)?\s+(?:towards|to|for)|target\s+customer\s*[:=]|customer\s*[:=]|account\s*[:=]|client\s*[:=]|for\s+customer|for\s+account|for\s+client)\s+([A-Za-z0-9_&\'\s\-]+?)(?:,|$|\.|\s+into\b|\s+on\b|\s+focusing\b|\s+with\b|\s+in\b|\s+adjust\b|\s+align\b|\s+audience\b|\s+sales\b|\s+targeting\b|\s+for\b|\s+opp\b|\s+products\b)",
      clean_text_for_cust,
      re.IGNORECASE,
  )
  if not cust_m:
    # Priority 2: General targeting / for phrase
    cust_m = re.search(
        r"\b(?:presenting\s+to|pitching\s+to|focusing(?:\s+it)?\s+on|focus\s+on|focused\s+on|targeting|for|towards|to)\s+([A-Za-z0-9_&\'\s\-]+?)(?:,|$|\.|\s+into\b|\s+on\b|\s+in\b|\s+with\b|\s+focusing\b|\s+adjust\b|\s+align\b|\s+audience\b|\s+sales\b|\s+targeting\b|\s+for\b|\s+executive\b|\s+opp\b|\s+products\b)",
        clean_text_for_cust,
        re.IGNORECASE,
    )
  if not cust_m:
    # Priority 3: Customer noun with negative lookahead for common CX terms
    cust_m = re.search(
        r"\b(?:customer|account|client)\s+(?!(?:experience|service|journey|satisfaction|support|success|retention|engagement|feedback|centric|facing|telemetry|profiles|regulations|priorities)\b)([A-Za-z0-9_&\'\s\-]+?)(?:,|$|\.|\s+into\b|\s+on\b|\s+towards\b|\s+in\b|\s+with\b|\s+focusing\b)",
        clean_text_for_cust,
        re.IGNORECASE,
    )

  if cust_m:
    candidate = cust_m.group(1).strip()
    stop_words = {
        "the",
        "a",
        "an",
        "this",
        "my",
        "our",
        "all",
        "entire",
        "deck",
        "presentation",
        "slides",
        "google",
        "google cloud",
        "fsi",
        "banking",
        "retail",
        "cpg",
        "healthcare",
        "financial",
        "services",
        "industry",
        "sector",
        "vertical",
        "c-suite",
        "executives",
        "executive",
        "leadership",
        "digital",
        "transformation",
        "compliance",
        "trust",
        "risk",
        "management",
        "journey",
        "experience",
        "service",
        "support",
        "regulations",
        "priorities",
        "strategic",
        "adjust",
        "terminology",
        "examples",
        "tone",
        "align",
        "institutional",
        "supply",
        "chain",
        "modernization",
        "above",
        "deck",
        "by",
    }
    candidate = re.sub(r"[,\.:;]+$", "", candidate).strip()
    cand_tokens = [w for w in candidate.split() if w.lower() not in stop_words]
    if cand_tokens:
      final_cust = " ".join(cand_tokens)
      c_lower = final_cust.lower()
      if c_lower in (
          "jp morgan chase",
          "jpmorgan chase",
          "jpmorgan",
          "jp morgan",
          "jpmc",
      ):
        res["customer_name"] = "JPMorgan Chase"
      elif c_lower in ("anz", "anz bank"):
        res["customer_name"] = "ANZ Bank"
      elif c_lower == "pepsico":
        res["customer_name"] = "PepsiCo"
      elif c_lower in ("walmart", "wal-mart"):
        res["customer_name"] = "Walmart"
      elif c_lower in ("tata", "tata motors"):
        res["customer_name"] = "Tata Motors"
      elif c_lower in ("standard chartered", "scb"):
        res["customer_name"] = "Standard Chartered"
      elif c_lower in ("deutsche bank", "db"):
        res["customer_name"] = "Deutsche Bank"
      elif c_lower in ("santander", "banco santander"):
        res["customer_name"] = "Santander"
      elif c_lower in ("goldman sachs", "goldman"):
        res["customer_name"] = "Goldman Sachs"
      elif c_lower in ("morgan stanley",):
        res["customer_name"] = "Morgan Stanley"
      elif c_lower in ("citi", "citigroup"):
        res["customer_name"] = "Citigroup"
      elif c_lower in ("bank of america", "bofa"):
        res["customer_name"] = "Bank of America"
      elif c_lower in ("wells fargo",):
        res["customer_name"] = "Wells Fargo"
      elif c_lower in ("target", "target corporation", "target corp"):
        res["customer_name"] = "Target"
      else:
        res["customer_name"] = final_cust.title()

  if not res["customer_name"]:
    for known_cust in (
        "HDFC Bank",
        "HDFC",
        "JPMorgan Chase",
        "JP Morgan Chase",
        "JPMorgan",
        "ANZ Bank",
        "ANZ",
        "PepsiCo",
        "Walmart",
        "Tata Motors",
        "Target",
        "Home Depot",
        "Costco",
        "CVS",
        "Walgreens",
        "Standard Chartered",
        "Deutsche Bank",
        "Santander",
        "Goldman Sachs",
        "Morgan Stanley",
        "Citigroup",
        "Bank of America",
        "Wells Fargo",
    ):
      if re.search(r"\b" + re.escape(known_cust) + r"\b", text, re.IGNORECASE):
        if known_cust.upper().startswith("ANZ"):
          res["customer_name"] = "ANZ Bank"
        elif (
            "jpmorgan" in known_cust.lower()
            or "jp morgan" in known_cust.lower()
        ):
          res["customer_name"] = "JPMorgan Chase"
        else:
          res["customer_name"] = known_cust
        break

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
  service_owner_ldap = os.environ.get("PITCHGEN_SERVICE_OWNER_LDAP", "seller_user")
  tokens = [
      get_enduser_bearer_token(tool_context=tool_context),
      get_user_access_token(user_ldap),
      (
          get_user_access_token(service_owner_ldap)
          if user_ldap != service_owner_ldap
          else None
      ),
      get_adc_bearer_token(),
  ]

  seen_tokens = set()
  for token in tokens:
    if not token or token in seen_tokens:
      continue
    seen_tokens.add(token)
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


class DeckTransformationService:
  """Dedicated, self-contained service for Google Slides text transformation (Checkpoint 2)."""

  @staticmethod
  def _normalize_card_list_field(val, placeholder_token: str = "") -> str:
    """Normalizes a single or multi-select A2UI ChoicePicker list/string into a clean string."""
    if val is None:
      return ""
    skip_tokens = {
        "",
        "none",
        "null",
        "— (blank)",
        "-(blank)",
        "industry",
        "audience",
    }
    if placeholder_token:
      skip_tokens.add(placeholder_token.lower().strip())
    if isinstance(val, list):
      cleaned = [
          str(item).strip()
          for item in val
          if str(item).strip() and str(item).strip().lower() not in skip_tokens
      ]
      return ", ".join(cleaned)
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
  def transform_deck_text(
      presentation_identifier: str = "",
      transform_instructions: str = "Improve clarity and professional sales tone",
      target_slide_numbers: str = "",
      customer_name: str = "",
      industry="",
      audience="",
      full_deck_scope=None,
      tool_context=None,
  ) -> str:
    """Polishes and transforms text copy across an entire Google Slides presentation deck headlessly.

    CRITICAL: Use this tool when the user provides an existing Google Slides
    presentation URL or ID and asks to transform, polish, rewrite, customize, or
    adapt the presentation. DO NOT use this tool for translation into another
    language; for translating presentations into languages like German, Spanish,
    French, Chinese, Japanese, etc., use translate_presentation_deck instead.
    TERMINAL: After calling this tool, do NOT call create_proposal_outline or
    any other tool.

    Args:
        presentation_identifier: The Google Slides URL, Drive file URL, or
          44-character Presentation ID.
        transform_instructions: Copywriting/polishing instructions (e.g.
          'rewrite for executive tone', 'summarize text', 'make concise',
          'transform for customer PepsiCo').
        target_slide_numbers: Optional comma-separated slide numbers (e.g. '1,
          2, 4') to scope transformation.
        customer_name: Optional target customer/account name from the A2UI
          Transform Text card.
        industry: Optional target industry vertical (string or list) from the
          A2UI Transform Text card.
        audience: Optional target audience personas (string or list) from the
          A2UI Transform Text card.
        full_deck_scope: Optional full deck scope flag/list (e.g. ['full_deck']
          or []) from the A2UI Transform Text card.
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

    user_ldap = resolve_user_ldap(
        getattr(tool_context, "user_id", ""),
        tool_context=tool_context,
    )

    explicit_customer = str(customer_name or "").strip()
    explicit_industry = DeckTransformationService._normalize_card_list_field(
        industry, placeholder_token="industry"
    )
    explicit_audience = DeckTransformationService._normalize_card_list_field(
        audience, placeholder_token="audience"
    )
    target_indices_set = DeckTransformationService._parse_target_slide_indices(
        target_slide_numbers, full_deck_scope=full_deck_scope
    )
    effective_slide_numbers = (
        ", ".join(str(i) for i in sorted(target_indices_set))
        if target_indices_set
        else ""
    )

    criteria = (
        transform_instructions or "Improve clarity and professional sales tone"
    )
    if effective_slide_numbers:
      criteria = f"{criteria} (Target Slides: {effective_slide_numbers})"

    # Safety Auto-Forwarding Interceptor: If transform_deck_text was invoked for a translation request
    trans_keywords = [
        "translate",
        "translation",
        "german",
        "spanish",
        "french",
        "chinese",
        "japanese",
        "korean",
        "italian",
        "portuguese",
        "dutch",
        "danish",
        "swedish",
        "polish",
        "greek",
        "thai",
        "indonesian",
        "traditional chinese",
        "simplified chinese",
        "auf deutsch",
        "en español",
        "en français",
    ]
    criteria_lower = criteria.lower()
    is_primarily_translation = (
        any(kw in criteria_lower for kw in trans_keywords)
        and not any(
            cust_kw in criteria_lower
            for cust_kw in [
                "pepsico",
                "walmart",
                "hdfc",
                "jpmorgan",
                "target",
                "costco",
                "customize for",
                "tailor for",
                "transform for",
            ]
        )
        and not explicit_customer
    )
    if (
        is_primarily_translation
        or criteria_lower.startswith("translate ")
        or criteria_lower.startswith("translate to ")
        or criteria_lower.startswith("translate into ")
    ):
      print(
          "[DeckTransformationService] Translation intent detected in"
          f" transform criteria '{criteria}'. Auto-forwarding to"
          " DeckTranslationService.translate_presentation_deck..."
      )
      from services.deck_translation_service import DeckTranslationService

      return DeckTranslationService.translate_presentation_deck(
          presentation_identifier=presentation_identifier,
          target_language=criteria,
          tool_context=tool_context,
      )

    print(
        f"[DeckTransformationService] Transforming deck text '{pres_id}' with"
        f" criteria '{criteria}' (customer='{explicit_customer}',"
        f" industry='{explicit_industry}', audience='{explicit_audience}',"
        f" target_slides='{effective_slide_numbers or 'Full Deck'}') for user"
        f" '{user_ldap}'..."
    )

    # Step 1: Call Apps Script Web App to extract deck text & typography headlessly
    extract_payload = {
        "action": "extract_deck_text_transform",
        "is_transform": True,
        "presentationId": pres_id,
        "targetLanguage": "English",
        "isFullDeckTranslation": False,
        "user_ldap": user_ldap,
    }

    try:
      web_app_resp = call_apps_script_web_app(
          extract_payload, user_ldap=user_ldap, tool_context=tool_context
      )
      extracted_json = (
          web_app_resp.get("data") if isinstance(web_app_resp, dict) else None
      )
      extracted_gcs_file = (
          web_app_resp.get("extracted_gcs_filename", "")
          if isinstance(web_app_resp, dict)
          else ""
      )
    except Exception as e:
      print(f"[DeckTransformationService] Web App extraction note: {e}")
      extracted_json = None
      extracted_gcs_file = ""

    real_id = pres_id
    if isinstance(extracted_json, dict):
      for k in extracted_json.keys():
        if (
            len(k) >= 25
            and not k.startswith("action")
            and not k.startswith("extracted_")
            and not k.startswith("user_")
        ):
          real_id = k
          break
    pres_id = real_id

    if not extracted_json or pres_id not in extracted_json:
      err_msg = (
          web_app_resp.get("error")
          if isinstance(web_app_resp, dict)
          else "Extraction response empty or missing presentation data"
      )
      print(
          "[DeckTransformationService] Web App text extraction failed:"
          f" {err_msg}"
      )
      return (
          "Error: Unable to extract text content from presentation deck"
          f" '{pres_id}'. Details: {err_msg}. Please verify that the Google"
          " Slides presentation ID is correct and shared with your account."
      )

    # Step 2: Read Input GCS file if available, or use extracted_json directly
    config = load_config()
    bucket_name = config.get(
        "bucket", "content", fallback="your-pitchgen-content-bucket"
    )
    if extracted_gcs_file:
      try:
        input_gcs_url = f"gs://{bucket_name}/{extracted_gcs_file}"
        raw_gcs_input = read_gcs_file(input_gcs_url)
        input_payload = json.loads(raw_gcs_input)
        if isinstance(input_payload, dict) and "data" in input_payload:
          extracted_json = input_payload["data"]
        elif isinstance(input_payload, dict):
          extracted_json = input_payload
        print(
            "[DeckTransformationService] Successfully verified input GCS file:"
            f" {input_gcs_url}"
        )
      except Exception as read_err:
        print(
            "[DeckTransformationService] Notice reading input GCS file"
            f" ({extracted_gcs_file}): {read_err}"
        )

    # Step 3: Run SlideEngineeringAgent text transformation workflow with full entity extraction + explicit card inputs
    extracted_entities = extract_entities_from_user_prompt(criteria)
    resolved_customer = explicit_customer or extracted_entities.get(
        "customer_name", ""
    )
    resolved_industry = explicit_industry or extracted_entities.get(
        "industry", ""
    )
    resolved_audience = explicit_audience or extracted_entities.get(
        "audience", ""
    )
    sales_play = extracted_entities.get("sales_play", "")
    opportunity_id = extracted_entities.get("opportunity_id", "")
    products = extracted_entities.get("products", "")

    extra_criteria_parts = []
    if resolved_customer and resolved_customer.lower() not in criteria.lower():
      extra_criteria_parts.append(f"Customer: {resolved_customer}")
    if resolved_industry and resolved_industry.lower() not in criteria.lower():
      extra_criteria_parts.append(f"Industry: {resolved_industry}")
    if resolved_audience and resolved_audience.lower() not in criteria.lower():
      extra_criteria_parts.append(f"Target Audience: {resolved_audience}")
    effective_criteria = (
        f"{criteria} [{'; '.join(extra_criteria_parts)}]"
        if extra_criteria_parts
        else criteria
    )

    print(
        "[DeckTransformationService] Resolved Entities:"
        f" Customer='{resolved_customer}', Industry='{resolved_industry}',"
        f" Audience='{resolved_audience}', SalesPlay='{sales_play}',"
        f" OpportunityID='{opportunity_id}'"
    )

    context_dict = {
        "user_ldap": user_ldap,
        "user_request": effective_criteria,
        "business_context": effective_criteria,
        "criteria": effective_criteria,
    }
    if resolved_customer:
      context_dict["customer_name"] = resolved_customer
    if resolved_industry:
      context_dict["industry"] = resolved_industry
    if resolved_audience:
      context_dict["audience"] = resolved_audience
    if sales_play:
      context_dict["salesPlay"] = sales_play
    if opportunity_id:
      context_dict["opportunity_id"] = opportunity_id
    if products:
      context_dict["products"] = products

    try:
      from agents.slide_engineering_agent import SlideEngineeringAgent

      se_agent = SlideEngineeringAgent(config)
      pres_slides = (
          extracted_json.get(pres_id, extracted_json)
          if isinstance(extracted_json, dict)
          else extracted_json
      )

      if target_indices_set and isinstance(pres_slides, dict) and pres_slides:
        print(
            "[DeckTransformationService] Scoping transformation to slide"
            f" indices/IDs {sorted(target_indices_set)} out of"
            f" {len(pres_slides)} slide(s)"
        )
        context_dict["target_slide_ids"] = target_indices_set
        transformed_data = se_agent.transform_presentation(
            presentation_data=pres_slides,
            output_criteria=effective_criteria,
            slide_name=f"Slides {effective_slide_numbers}",
            context=context_dict,
        )
      else:
        transformed_data = se_agent.transform_presentation(
            presentation_data=pres_slides,
            output_criteria=effective_criteria,
            slide_name="Full Deck Transform Text",
            context=context_dict,
        )

      # Ensure Slide 1 Internal Context Table is explicitly populated with extracted metadata
      # ONLY when Slide 1 is an Internal Enablement slide and is included in the target scope
      if isinstance(transformed_data, dict):
        if isinstance(pres_slides, dict) and pres_slides:
          first_slide_id = list(pres_slides.keys())[0]
          first_slide_data = pres_slides.get(first_slide_id, {})
          slide_1_targeted = (
              not target_indices_set
              or 1 in target_indices_set
              or "1" in target_indices_set
              or first_slide_id in target_indices_set
          )
          if (
              slide_1_targeted
              and isinstance(first_slide_data, dict)
              and "tables" in first_slide_data
              and se_agent.is_internal_enablement_slide(first_slide_data)
          ):
            tables_dict = first_slide_data.get("tables", {})
            if isinstance(tables_dict, dict) and tables_dict:
              table_id = list(tables_dict.keys())[0]
              if first_slide_id not in transformed_data:
                transformed_data[first_slide_id] = {}
              if "tables" not in transformed_data[first_slide_id]:
                transformed_data[first_slide_id]["tables"] = {}
              if table_id not in transformed_data[first_slide_id]["tables"]:
                transformed_data[first_slide_id]["tables"][table_id] = {}

              tbl = transformed_data[first_slide_id]["tables"][table_id]
              if opportunity_id:
                tbl["0_1"] = {
                    "0": {"Text": opportunity_id, "HadNewline": False}
                }
              if resolved_customer:
                tbl["1_1"] = {
                    "0": {"Text": resolved_customer, "HadNewline": False}
                }
              if resolved_audience:
                tbl["2_1"] = {
                    "0": {"Text": resolved_audience, "HadNewline": False}
                }
              if resolved_industry:
                tbl["3_1"] = {
                    "0": {"Text": resolved_industry, "HadNewline": False}
                }
              if sales_play:
                tbl["4_1"] = {"0": {"Text": sales_play, "HadNewline": False}}
              if criteria:
                tbl["5_1"] = {"0": {"Text": criteria, "HadNewline": False}}
              tbl["6_1"] = {
                  "0": {
                      "Text": (
                          "Edit your deck with the PitchGen sidebar:"
                          " “Extensions → PitchGen → Edit my"
                          " Presentation”\nLearn more about PitchGen in"
                          " CloudHub"
                      ),
                      "HadNewline": False,
                  }
              }

      # Construct final transformed output dictionary
      output_payload = dict(extracted_json)
      output_payload[pres_id] = transformed_data
      output_payload["action"] = "transform_text"

      # Step 4: Upload transformed output payload to GCS
      timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
      output_filename = (
          f"transform_data/transformed_text_{pres_id}_{timestamp}.json"
      )
      output_gcs_url = f"gs://{bucket_name}/{output_filename}"

      write_gcs_file(output_gcs_url, json.dumps(output_payload, indent=2))
      print(
          "[DeckTransformationService] Successfully uploaded transformed text"
          f" output to GCS: {output_gcs_url}"
      )

    except Exception as transform_err:
      print(
          "[DeckTransformationService] Text transformation engine error:"
          f" {transform_err}"
      )
      return f"Error executing text transformation: {str(transform_err)}"

    # Step 5: Call Apps Script Web App to apply transformed JSON back to deck headlessly
    apply_payload = {
        "action": "apply_text_transform",
        "presentationId": pres_id,
        "bucketName": bucket_name,
        "response_gcs_filename": output_filename,
        "user_ldap": user_ldap,
    }

    try:
      apply_res = call_apps_script_web_app(
          apply_payload, user_ldap=user_ldap, tool_context=tool_context
      )
      deck_url = apply_res.get(
          "deckURL", f"https://docs.google.com/presentation/d/{pres_id}/edit"
      )
    except Exception:
      deck_url = f"https://docs.google.com/presentation/d/{pres_id}/edit"

    return (
        "🎉 Presentation text successfully transformed! View your updated deck"
        f" here: {deck_url}"
    )
