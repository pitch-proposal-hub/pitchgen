"""Gemini Enterprise App agent for deck generation, search, transformation, visuals, and translation."""

import json
import logging
import os
import re
import sys
from typing import Any

# Remove any API keys from the environment to prevent the google-genai SDK
# from using them instead of standard Google Cloud IAM/ADC credentials.
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("GOOGLE_API_KEY", None)
os.environ.pop("API_KEY", None)

# Ensure the current directory (src/) is at sys.path[0] ahead of parent_dir
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
for p in [parent_dir, current_dir]:
  if p in sys.path:
    sys.path.remove(p)
  sys.path.insert(0, p)

from google.adk.agents.llm_agent import Agent
from google.adk.apps.app import App
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from config_loader import load_config
from agent import PitchGenSkills, route_payload_before_model
from agents.gtm_skills import GTMSkills
from pitchgen_utils import a2ui_util
from pitchgen_utils import slide_thumbnail_util

config = load_config()
project_id = os.environ.get(
    "GOOGLE_CLOUD_PROJECT",
    os.environ.get(
        "PROJECT_ID", config["default"].get("project_name", "your-gcp-project-id")
    ),
)
model_name = config["default"].get("gemini_model", "gemini-3.8-flash")
fallback_model_name = config["default"].get(
    "gemini_model_1", "gemini-3.5-flash-lite"
)
model_region = "global"


def _install_adk_gemini_429_fallback() -> None:
  """Wraps ADK's Gemini.generate_content_async to retry 429 errors and fall back to gemini_model_1."""
  try:
    import asyncio
    from google.adk.models import google_llm

    gemini_cls = getattr(google_llm, "Gemini", None)
    if gemini_cls is None or getattr(
        gemini_cls, "_pitchgen_429_patched", False
    ):
      return

    orig_generate = gemini_cls.generate_content_async

    async def _resilient_generate_content_async(
        self: Any, llm_request: Any, stream: bool = False
    ):
      base_req = (
          llm_request.model_copy(deep=True)
          if hasattr(llm_request, "model_copy")
          else llm_request
      )
      for attempt in range(2):
        try:
          req_try = (
              base_req.model_copy(deep=True)
              if hasattr(base_req, "model_copy")
              else base_req
          )
          async for resp in orig_generate(self, req_try, stream=stream):
            yield resp
          return
        except Exception as err:
          err_str = str(err)
          is_429 = (
              "429" in err_str
              or "RESOURCE_EXHAUSTED" in err_str.upper()
              or getattr(err, "code", None) == 429
              or err.__class__.__name__ == "_ResourceExhaustedError"
          )
          if not is_429:
            raise
          if attempt == 0:
            logging.warning(
                "[enterprise_agent] ADK model %s hit 429 RESOURCE_EXHAUSTED;"
                " retrying in 1.2s...",
                getattr(base_req, "model", model_name),
            )
            await asyncio.sleep(1.2)
            continue

          fb_model_path = (
              f"projects/{project_id}/locations/{model_region}"
              f"/publishers/google/models/{fallback_model_name}"
          )
          logging.warning(
              "[enterprise_agent] ADK primary model %s exhausted 429 retries;"
              " falling back to %s.",
              getattr(base_req, "model", model_name),
              fb_model_path,
          )
          fb_req = (
              base_req.model_copy(deep=True)
              if hasattr(base_req, "model_copy")
              else base_req
          )
          fb_req.model = fb_model_path
          try:
            async for resp in orig_generate(self, fb_req, stream=stream):
              yield resp
            return
          except Exception as fb_err:
            fb_err_str = str(fb_err)
            if (
                ("400" in fb_err_str or "INVALID_ARGUMENT" in fb_err_str)
                and getattr(fb_req, "config", None) is not None
                and getattr(fb_req.config, "thinking_config", None) is not None
            ):
              fb_req_no_think = (
                  base_req.model_copy(deep=True)
                  if hasattr(base_req, "model_copy")
                  else base_req
              )
              fb_req_no_think.model = fb_model_path
              fb_req_no_think.config.thinking_config = None
              async for resp in orig_generate(
                  self, fb_req_no_think, stream=stream
              ):
                yield resp
              return
            raise

    gemini_cls.generate_content_async = _resilient_generate_content_async
    gemini_cls._pitchgen_429_patched = True
  except Exception as patch_err:
    logging.warning(
        "[enterprise_agent] Could not install ADK 429 fallback wrapper: %s",
        patch_err,
    )


_install_adk_gemini_429_fallback()


def identity_resolution_callback(callback_context, **kwargs):
  """Session starter callback: resolves user identity from GE OAuth token before turn 1."""
  del kwargs  # Unused.
  try:
    state = getattr(callback_context, "state", None)
    if state is None:
      return
    if hasattr(state, "get") and state.get("initialized"):
      return
    email, ldap = a2ui_util.resolve_ge_user_identity(
        tool_context=callback_context
    )
    if email:
      state["user_email"] = email
    if ldap:
      state["user_ldap"] = ldap
    state["a2ui_version"] = a2ui_util.detect_client_a2ui_version(
        tool_context=callback_context, default_version="v0.9"
    )
    state["initialized"] = True
  except Exception as e:
    logging.warning("[enterprise_agent] Identity resolution notice: %s", e)


_PENDING_A2UI_PAYLOADS: list[dict[str, Any]] = []


def _stash_a2ui_payload(tool_context: Any, payloads: Any) -> None:
  """Safely stashes A2UI payloads into agent state and in-memory queue for injection into response DataParts."""
  flat_new: list[dict[str, Any]] = []

  def _flatten_into(source: Any, target: list[Any]) -> None:
    if isinstance(source, list):
      for sub in source:
        _flatten_into(sub, target)
    elif isinstance(source, dict):
      target.append(source)

  _flatten_into(payloads, flat_new)
  if not flat_new:
    return

  state = getattr(tool_context, "state", None) if tool_context else None
  if state is None:
    # Only fall back to module-level queue when tool_context.state is unavailable
    existing_pending_json = {
        json.dumps(x, sort_keys=True) for x in _PENDING_A2UI_PAYLOADS
    }
    for item in flat_new:
      s = json.dumps(item, sort_keys=True)
      if s not in existing_pending_json:
        existing_pending_json.add(s)
        _PENDING_A2UI_PAYLOADS.append(item)
    return
  current = []
  if hasattr(state, "get"):
    current = state.get("a2ui_payloads_to_inject") or []
  elif hasattr(state, "__getitem__") and "a2ui_payloads_to_inject" in state:
    current = state["a2ui_payloads_to_inject"] or []

  flat_current = []
  _flatten_into(current, flat_current)
  seen_json = {json.dumps(x, sort_keys=True) for x in flat_current}

  for item in flat_new:
    s = json.dumps(item, sort_keys=True)
    if s not in seen_json:
      seen_json.add(s)
      flat_current.append(item)
  state["a2ui_payloads_to_inject"] = flat_current


def enterprise_after_tool_callback(
    tool: Any,
    args: Any,
    tool_context: Any,
    tool_response: Any,
) -> Any:
  """Captures A2UI payloads from tool execution results, stashes them in state, and strips raw <a2ui-json> from LLM context."""
  del tool, args  # Unused
  try:
    # Flush any module-level pending payloads into session state now that tool_context is guaranteed
    if _PENDING_A2UI_PAYLOADS and tool_context:
      pending = list(_PENDING_A2UI_PAYLOADS)
      _PENDING_A2UI_PAYLOADS.clear()
      _stash_a2ui_payload(tool_context, pending)

    resp_text = ""
    if isinstance(tool_response, str):
      resp_text = tool_response
    elif isinstance(tool_response, dict):
      resp_text = str(tool_response.get("result") or json.dumps(tool_response))

    if "<a2ui-json>" in resp_text:
      matches = re.findall(
          r"<a2ui-json>(.*?)</a2ui-json>", resp_text, re.DOTALL
      )
      extracted = []
      for m in matches:
        try:
          parsed = json.loads(m.strip())
          if isinstance(parsed, list):
            extracted.extend(parsed)
          else:
            extracted.append(parsed)
        except Exception:
          pass
      if extracted:
        _stash_a2ui_payload(tool_context, extracted)

      # Strip massive <a2ui-json> payload from tool_response before sending to the LLM!
      cleaned_text = re.sub(
          r"\s*<a2ui-json>.*?(?:</a2ui-json>|$)", "", resp_text, flags=re.DOTALL
      ).strip()
      return {
          "result": (
              cleaned_text or "Interactive A2UI card rendered successfully."
          )
      }
  except Exception as e:
    logging.warning(
        "[enterprise_after_tool_callback] Error capturing A2UI: %s", e
    )
  return None


def _next_card_surface_id(tool_context: Any, base_surface_id: str) -> str:
  """Returns base_surface_id on first emission in a session, and appends a short suffix on subsequent emissions so ucs_widget introducedSurfaceIds never suppresses re-opened cards."""
  state = getattr(tool_context, "state", None) if tool_context else None
  if state is None or not hasattr(state, "get"):
    return base_surface_id
  try:
    emitted = list(state.get("emitted_card_surface_ids") or [])
    if base_surface_id not in emitted:
      emitted.append(base_surface_id)
      state["emitted_card_surface_ids"] = emitted
      return base_surface_id
    import uuid

    unique_id = f"{base_surface_id}-{uuid.uuid4().hex[:6]}"
    emitted.append(unique_id)
    state["emitted_card_surface_ids"] = emitted
    return unique_id
  except Exception:
    return base_surface_id


_SEARCH_FORM_SURFACE_IDS_KEY = "search_form_surface_ids"
_SEARCH_RESULTS_SURFACE_IDS_KEY = "search_results_surface_ids"


def _collect_prior_card_surface_ids(
    tool_context: Any, state_key: str
) -> list[str]:
  """Returns previously emitted surfaceIds for one card type (tracked in session state)."""
  state = getattr(tool_context, "state", None) if tool_context else None
  if state is None or not hasattr(state, "get"):
    return []
  try:
    raw = state.get(state_key) or []
    return [str(s) for s in raw if s] if isinstance(raw, list) else []
  except Exception:
    return []


def _record_card_surface_id(
    tool_context: Any, state_key: str, surface_id: str
) -> None:
  """Records a surfaceId for one card type in session state."""
  state = getattr(tool_context, "state", None) if tool_context else None
  sid = str(surface_id or "").strip()
  if state is None or not sid:
    return
  try:
    prior = _collect_prior_card_surface_ids(tool_context, state_key)
    if sid not in prior:
      prior.append(sid)
    state[state_key] = prior
  except Exception:
    pass


def _delete_surface_msgs(surface_ids: list[str], keep: str = "") -> list[Any]:
  """Builds v0.9 deleteSurface messages for prior surfaces (excluding `keep`)."""
  msgs: list[Any] = []
  for old_sid in surface_ids:
    if old_sid and old_sid != keep:
      msgs.extend(
          a2ui_util.create_a2ui_delete_surface_message(
              surface_id=old_sid, version="v0.9"
          )
      )
  return msgs


def _build_search_form_messages(
    tool_context: Any,
    active_pres_id: str = "",
    cust_name: str = "",
    slide_job: str = "",
) -> tuple[str, list[Any]]:
  """Returns (surface_id, messages) for the Slide Search form, deleting prior search forms."""
  surf_id = _next_card_surface_id(tool_context, "pitchgen-slide-search")
  prior = _collect_prior_card_surface_ids(
      tool_context, _SEARCH_FORM_SURFACE_IDS_KEY
  )
  form_msgs = a2ui_util.create_a2ui_search_form_messages(
      search_query="",
      target_presentation_id=active_pres_id,
      slide_job=slide_job,
      customer_name=cust_name,
      surface_id=surf_id,
  )
  _record_card_surface_id(tool_context, _SEARCH_FORM_SURFACE_IDS_KEY, surf_id)
  return surf_id, _delete_surface_msgs(prior, keep=surf_id) + list(form_msgs)


def _build_search_results_messages(
    tool_context: Any,
    search_query: str,
    slides: list[Any],
    active_pres_id: str = "",
    slide_job: str = "",
    cust_name: str = "",
) -> tuple[str, list[Any]]:
  """Returns (surface_id, messages) for exactly one Slide Search results card.

  Uses a unique surfaceId per search and deletes all prior results cards.
  """
  import uuid  # pylint: disable=g-import-not-at-top

  surf_id = f"pitchgen-search-results-{uuid.uuid4().hex[:8]}"
  prior = _collect_prior_card_surface_ids(
      tool_context, _SEARCH_RESULTS_SURFACE_IDS_KEY
  )
  results_msgs = a2ui_util.create_a2ui_search_results_messages(
      search_query=search_query,
      results=slides,
      target_presentation_id=active_pres_id,
      slide_job=slide_job,
      customer_name=cust_name,
      surface_id=surf_id,
  )
  _record_card_surface_id(
      tool_context, _SEARCH_RESULTS_SURFACE_IDS_KEY, surf_id
  )
  return surf_id, _delete_surface_msgs(prior, keep=surf_id) + list(results_msgs)


def _a2ui_payloads_to_parts(payloads: Any) -> list[Any]:
  """Flattens stashed A2UI payloads (incl.

  nested a2ui_v09_messages) into deduped A2A parts.
  """
  flat: list[dict[str, Any]] = []
  seen: set[str] = set()

  def _walk(obj: Any) -> None:
    if isinstance(obj, list):
      for sub in obj:
        _walk(sub)
      return
    if not isinstance(obj, dict):
      return
    nested = obj.get("a2ui_v09_messages")
    if isinstance(nested, list) and nested:
      _walk(nested)
      return
    key = json.dumps(obj, sort_keys=True)
    if key not in seen:
      seen.add(key)
      flat.append(obj)

  _walk(payloads)
  return [a2ui_util.create_a2a_part_from_a2ui_payload(m) for m in flat]


_INTAKE_FIELD_PLACEHOLDERS = {
    "primary sales play",
    "primary sales play (grouped by practice area)",
    "additional sales play (optional — multi-play pitch)",
    "➕ none / single sales play",
    "none / single sales play",
    "✨ auto-detect sales play",
    "auto-detect sales play",
    "industry vertical",
    "industry vertical (auto-detect)",
    "✨ auto-detect industry vertical",
    "auto-detect industry vertical",
    "target audience persona",
    "sales stage (s0-s4)",
    "deck strategy",
    "target deck length",
    "presentation archetype (auto-detect)",
    "✨ auto-detect from prompt, audience & win stage",
    "sales plays",
    "auto-detect industry",
    "auto-detect stage",
    "auto-detect archetype",
    "presentation archetype",
    "— (blank)",
    "— (optional / blank)",
}


def _clean_intake_select_val(val: Any, default: str = "") -> str:
  """Strips intake field-label placeholders and returns default if empty."""
  s = _clean_str(val).strip()
  if not s or s.lower() in _INTAKE_FIELD_PLACEHOLDERS:
    return default
  if " — " in s:
    prefix, rest = s.split(" — ", 1)
    if prefix.strip() in (
        "AI",
        "Agentic Workplace Transformation",
        "Data",
        "Infrastructure",
        "Security",
    ):
      s = rest.strip()
  if s == "Scale AI Apps & Agents":
    s = "Scale AI Apps and Agents"
  return s


def _clean_intake_sales_plays(val: Any, secondary_val: Any = "") -> str:
  """Normalizes 1 or more sales plays (list, pipe/comma-separated, or primary+secondary) into a pipe-delimited string."""
  try:
    from agents.skill_loader import split_sales_plays_safely  # pylint: disable=g-import-not-at-top

    raw_items: list[Any] = []
    for src in (val, secondary_val):
      if not src:
        continue
      if isinstance(src, (list, tuple, set)):
        raw_items.extend(src)
      else:
        raw_items.append(src)
    cleaned_items: list[str] = []
    seen_low: set[str] = set()
    for p in split_sales_plays_safely(raw_items):
      c = _clean_intake_select_val(p)
      if c and c.lower() not in seen_low:
        seen_low.add(c.lower())
        cleaned_items.append(c)
    return " | ".join(cleaned_items)
  except Exception:
    c1 = _clean_intake_select_val(val)
    c2 = _clean_intake_select_val(secondary_val)
    if c1 and c2 and c1.lower() != c2.lower():
      return f"{c1} | {c2}"
    return c1 or c2


def _clean_intake_multi_val(val: Any) -> str:
  """Normalizes a multi-select intake value (list or delimited string) to a ', '-joined string.

  Splits strings on commas/pipes/semicolons outside parentheses (so labels like
  'CDO (Chief Data Officer)' survive), strips placeholder labels, and
  de-duplicates while preserving order.
  """
  import re  # pylint: disable=g-import-not-at-top

  if val is None:
    return ""
  raw_items = list(val) if isinstance(val, (list, tuple, set)) else [val]
  cleaned: list[str] = []
  seen_low: set[str] = set()
  for item in raw_items:
    s = str(item or "").strip()
    if not s:
      continue
    for part in re.split(r"\s*[,|;]\s*(?![^()]*\))", s):
      c = _clean_intake_select_val(part.strip().strip("[]'\"").strip())
      if c and c.lower() not in ("none", "null", "undefined", "audience"):
        if c.lower() not in seen_low:
          seen_low.add(c.lower())
          cleaned.append(c)
  return ", ".join(cleaned)


def enterprise_launcher_card_skill(
    tool_context: Any = None,
) -> str:
  """Presents the interactive A2UI PitchGen Introduction & Feature Launcher Card (pitchgen-launcher) in Gemini Enterprise showcasing all 8 core capabilities."""
  active_ver = a2ui_util.detect_client_a2ui_version(
      tool_context=tool_context, default_version="v0.9"
  )
  surf_id = _next_card_surface_id(tool_context, "pitchgen-launcher")
  launcher_msgs = a2ui_util.create_a2ui_launcher_messages(
      surface_id=surf_id, version=active_ver
  )
  _stash_a2ui_payload(tool_context, launcher_msgs)
  return (
      "Welcome to **PitchGen** — your AI-Powered Presentation & Visual Suite"
      " for Gemini Enterprise! The interactive PitchGen Introduction & Feature"
      f" Launcher Card (surfaceId='{surf_id}') with all 8 core"
      " capabilities has been rendered below. Invite the user in 1-2 concise"
      " sentences to select a capability from the launcher card below or"
      " describe what they would like to build directly in"
      f" chat.\n\n<a2ui-json>\n{json.dumps(launcher_msgs)}\n</a2ui-json>"
  )


def enterprise_intake_form_skill(
    customer_name: str = "",
    industry: str = "",
    business_context: str = "",
    tool_context: Any = None,
) -> str:
  """Presents the interactive A2UI GTM Intake form in Gemini Enterprise to capture customer requirements, pitch goals, and deck strategy."""
  active_ver = a2ui_util.detect_client_a2ui_version(
      tool_context=tool_context, default_version="v0.9"
  )
  surf_id = _next_card_surface_id(tool_context, "pitchgen-intake")
  intake_msgs = a2ui_util.create_a2ui_intake_messages(
      customer_name=customer_name,
      industry=_clean_intake_select_val(industry),
      user_prompt=business_context,
      surface_id=surf_id,
      version=active_ver,
  )
  _stash_a2ui_payload(tool_context, intake_msgs)
  return (
      "Welcome to PitchGen! The interactive GTM Intake Form"
      f" (surfaceId='{surf_id}') has been rendered below. Invite the user"
      " in 1-2 concise sentences to configure their pitch deck parameters in"
      " the intake form below, or describe their customer and goals directly in"
      f" chat.\n\n<a2ui-json>\n{json.dumps(intake_msgs)}\n</a2ui-json>"
  )


def _clean_str(val: Any) -> str:
  if isinstance(val, (list, tuple)):
    return str(val[0]) if val else ""
  return str(val) if val is not None else ""


def enterprise_create_proposal_outline(
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
    deck_length: str = "",
    secondary_sales_play: str = "",
    tool_context: Any = None,
    presentation_archetype: str = "",
) -> str:
  """Phase 1: Generates the initial proposal outline and agendas with interactive A2UI review cards for Gemini Enterprise."""
  business_context = _clean_str(business_context)
  customer_name = _clean_str(customer_name)
  industry = _clean_intake_select_val(industry)
  solution = _clean_str(solution)
  user_ldap = _clean_str(user_ldap)
  user_oauth_token = _clean_str(user_oauth_token)
  er_number = _clean_str(er_number)
  audience = _clean_intake_multi_val(audience)
  presentation_archetype = _clean_intake_select_val(presentation_archetype)
  region = _clean_str(region)
  product = _clean_str(product)
  request_type = _clean_intake_select_val(request_type)
  deck_length = _clean_intake_select_val(deck_length)
  if not request_type and deck_length:
    request_type = deck_length
  elif request_type and not deck_length:
    deck_length = request_type
  sales_stage = _clean_intake_select_val(sales_stage)
  salesPlay = _clean_intake_sales_plays(salesPlay, secondary_sales_play)
  deck_strategy = _clean_intake_select_val(
      deck_strategy, default="smart_hybrid"
  )

  # Preserve existing outline metadata when the LLM re-invokes create_proposal_outline
  # during a refinement turn without passing all original form fields.
  prev_raw = None
  if (
      tool_context
      and hasattr(tool_context, "state")
      and tool_context.state is not None
  ):
    try:
      prev_raw = tool_context.state.get("proposal_outline")
    except Exception:
      prev_raw = None
  if not prev_raw:
    cust_key = (
        f"cust:{customer_name.strip().lower()}"
        if customer_name and customer_name.strip()
        else ""
    )
    if cust_key and cust_key in _LATEST_OUTLINE_CACHE:
      prev_raw = _LATEST_OUTLINE_CACHE[cust_key]
    elif (
        user_ldap
        and f"ldap:{user_ldap.strip().lower()}" in _LATEST_OUTLINE_CACHE
    ):
      prev_raw = _LATEST_OUTLINE_CACHE[f"ldap:{user_ldap.strip().lower()}"]
  if prev_raw:
    try:
      prev_dict = json.loads(prev_raw)
      prev_state = (
          prev_dict.get("data", prev_dict)
          if isinstance(prev_dict, dict)
          else {}
      )
      prev_ctx = (
          prev_state.get("context", {}) if isinstance(prev_state, dict) else {}
      )
      if isinstance(prev_ctx, dict):
        prev_cust = str(
            prev_ctx.get("customer_name")
            or prev_state.get("customer")
            or prev_state.get("customer_name")
            or ""
        ).strip()
        if (
            not customer_name
            or not prev_cust
            or customer_name.strip().lower() in (prev_cust.lower(), "customer")
        ):
          customer_name = customer_name or prev_cust
          er_number = er_number or str(prev_ctx.get("er_number") or "")
          industry = industry or str(prev_ctx.get("industry") or "")
          audience = audience or str(prev_ctx.get("audience") or "")
          region = region or str(prev_ctx.get("region") or "")
          sales_stage = sales_stage or str(prev_ctx.get("sales_stage") or "")
          win_cycle = win_cycle or str(prev_ctx.get("win_cycle") or "")
          segment = segment or str(prev_ctx.get("segment") or "")
          if not salesPlay:
            sp_prev = (
                prev_ctx.get("salesPlay")
                or prev_ctx.get("sales_plays")
                or prev_ctx.get("required_sales_plays")
            )
            salesPlay = _clean_intake_sales_plays(sp_prev)
          if deck_strategy == "smart_hybrid" and prev_ctx.get("deck_strategy"):
            deck_strategy = str(prev_ctx.get("deck_strategy"))
          if not deck_length:
            deck_length = str(
                prev_ctx.get("deck_length")
                or prev_ctx.get("request_type")
                or ""
            )
            if not request_type and deck_length:
              request_type = deck_length
    except Exception:
      pass

  if not deck_length:
    deck_length = "Standard (8-12 slides)"
  if not request_type:
    request_type = deck_length

  raw_outline = PitchGenSkills.create_proposal_outline(
      business_context=business_context,
      customer_name=customer_name,
      industry=industry,
      solution=solution,
      user_ldap=user_ldap,
      user_oauth_token=user_oauth_token,
      er_number=er_number,
      audience=audience,
      region=region,
      product=product,
      request_type=request_type,
      presentation_id=presentation_id,
      salesPlay=salesPlay,
      user_input_id=user_input_id,
      sub_industry=sub_industry,
      sales_stage=sales_stage,
      win_cycle=win_cycle,
      segment=segment,
      tool_context=tool_context,
      presentation_archetype=presentation_archetype,
  )

  try:
    data = json.loads(raw_outline)
    agendas = []
    cust = customer_name
    er = er_number
    strat = deck_strategy or "smart_hybrid"
    deck_len_val = deck_length or request_type or "Standard (8-12 slides)"
    if isinstance(data, dict):
      state_data = data.get("data", data)
      if isinstance(state_data, dict):
        if isinstance(state_data.get("context"), dict) and deck_strategy:
          state_data["context"]["deck_strategy"] = deck_strategy
        agendas = state_data.get("agendas", [])
        cust = (
            customer_name
            or (state_data.get("context", {}) or {}).get("customer_name", "")
            or state_data.get("customer", "")
            or state_data.get("customer_name", "")
        )
        er = (
            er_number
            or (state_data.get("context", {}) or {}).get("er_number", "")
            or state_data.get("er_number", "")
        )
        strat = (
            deck_strategy
            or (state_data.get("context", {}) or {}).get(
                "deck_strategy", "smart_hybrid"
            )
            or state_data.get("deck_strategy", "smart_hybrid")
        )
        deck_len_val = (
            deck_length
            or request_type
            or (state_data.get("context", {}) or {}).get("deck_length")
            or (state_data.get("context", {}) or {}).get("request_type")
            or state_data.get("deck_length")
            or "Standard"
        )

    agenda_sections = _normalize_agendas_to_sections(
        agendas, deck_length=str(deck_len_val)
    )
    if isinstance(data, dict):
      state_data = data.get("data", data)
      if isinstance(state_data, dict) and isinstance(
          state_data.get("agendas"), dict
      ):
        for idx, sec in enumerate(agenda_sections, start=1):
          k_str = str(idx)
          if k_str in state_data["agendas"] and isinstance(
              state_data["agendas"][k_str], dict
          ):
            state_data["agendas"][k_str]["slide_count"] = int(
                sec.get("slide_count", 1) or 1
            )
        raw_outline = json.dumps(data)

    active_ver = a2ui_util.detect_client_a2ui_version(
        tool_context=tool_context, default_version="v0.9"
    )
    prev_surface_ids = _collect_prior_outline_surface_ids(tool_context)

    import uuid

    new_surface_id = f"pitchgen-outline-{uuid.uuid4().hex[:8]}"
    outline_msgs = a2ui_util.create_a2ui_outline_messages(
        customer_name=cust or "Customer",
        agenda_sections=agenda_sections,
        deck_strategy=strat,
        surface_id=new_surface_id,
        version=active_ver,
        previous_surface_id=prev_surface_ids[-1] if prev_surface_ids else None,
        previous_surface_ids=prev_surface_ids,
        sales_play=_outline_sales_play_label(raw_outline),
    )

    _stash_a2ui_payload(tool_context, outline_msgs)
    _record_outline_surface_id(tool_context, new_surface_id)
    ctx_inner = (
        (state_data.get("context", {}) or {})
        if isinstance(state_data, dict)
        else {}
    )
    ind_val = str(ctx_inner.get("industry") or industry or "").strip()
    sp_val = ctx_inner.get("salesPlay") or salesPlay or ""
    if isinstance(sp_val, list):
      sp_val = ", ".join(str(x) for x in sp_val if x)
    sec_titles = [
        s.get("title", "") for s in agenda_sections[:6] if s.get("title")
    ]
    cot_outline = (
        f"**Executive GTM & Narrative Strategy ({cust or 'Customer'})**\n-"
        " **Account & Vertical Alignment**: Grounded proposal in"
        f" {ind_val or 'enterprise'} industry priorities"
        + (
            f" and Google Cloud **{sp_val}** value drivers.\n"
            if sp_val
            else ".\n"
        )
        + f"- **Narrative Arc ({len(agenda_sections)} Sections)**: Structured"
        " executive storyline across "
        + (
            ", ".join(f"*{t}*" for t in sec_titles)
            if sec_titles
            else "core CVI pillars"
        )
        + f" using `{strat}` synthesis strategy."
    )
    if (
        tool_context
        and hasattr(tool_context, "state")
        and tool_context.state is not None
    ):
      try:
        tool_context.state["outline_generated"] = True
        tool_context.state["proposal_outline"] = raw_outline
        tool_context.state["latest_outline_state_json"] = raw_outline
        if cust:
          tool_context.state["customer_name"] = cust
        if ind_val:
          tool_context.state["industry"] = ind_val
        if sp_val:
          tool_context.state["salesPlay"] = str(sp_val)
        tool_context.state["latest_cot_summary"] = cot_outline
      except Exception:
        pass

    try:
      _LATEST_OUTLINE_CACHE["_latest_"] = raw_outline
      _LATEST_OUTLINE_CACHE["_latest_cot_"] = cot_outline
      if cust:
        _LATEST_OUTLINE_CACHE["_latest_customer_name_"] = cust
        _LATEST_OUTLINE_CACHE[f"cust:{cust.strip().lower()}"] = raw_outline
      if ind_val:
        _LATEST_OUTLINE_CACHE["_latest_industry_"] = ind_val
      if sp_val:
        _LATEST_OUTLINE_CACHE["_latest_sales_play_"] = str(sp_val)
      if user_ldap:
        _LATEST_OUTLINE_CACHE[f"ldap:{user_ldap.strip().lower()}"] = raw_outline
      _persist_workspace_cache_to_gcs()
    except Exception:
      pass

    # Create a compact JSON summary for the LLM FunctionResponse so the LLM does not spend
    # 45+ seconds re-reading 20KB of raw customer_research and developer_knowledge text.
    try:
      import copy

      compact_data = (
          copy.deepcopy(data)
          if isinstance(data, dict)
          else {"raw": raw_outline}
      )
      inner = compact_data.get("data", compact_data)
      if isinstance(inner, dict) and isinstance(inner.get("context"), dict):
        if inner["context"].get("customer_research"):
          inner["context"]["customer_research"] = "[Cached in session state]"
        if inner["context"].get("developer_knowledge"):
          inner["context"]["developer_knowledge"] = "[Cached in session state]"
      compact_json_str = json.dumps(compact_data)
    except Exception:
      compact_json_str = raw_outline

    return compact_json_str
  except Exception as e:
    logging.warning("[enterprise_agent] A2UI outline processing notice: %s", e)
    return raw_outline


_LATEST_OUTLINE_CACHE: dict[str, str] = {}
_WORKSPACE_CACHE_LOADED = False
_WORKSPACE_CACHE_LOADED_AT = 0.0


def _persist_workspace_cache_to_gcs() -> None:
  """Persists active deck and outline pointers to GCS so follow-up turns survive container restarts."""
  try:
    from google.cloud import storage

    bucket_name = config.get(
        "bucket", "content", fallback="your-pitchgen-content-bucket"
    )
    payload = {
        k: v
        for k, v in _LATEST_OUTLINE_CACHE.items()
        if k
        in (
            "_latest_deck_id_",
            "_latest_deck_url_",
            "_latest_customer_name_",
            "_latest_industry_",
            "_latest_sales_play_",
            "_last_search_results_",
            "_latest_",
        )
    }
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob("ge_sessions/_latest_workspace_state.json")
    blob.upload_from_string(
        json.dumps(payload), content_type="application/json"
    )
  except Exception:
    pass


def _load_workspace_cache_from_gcs(force: bool = False) -> None:
  """Loads active deck and outline pointers from GCS when needed or when forced across multi-worker turns."""
  global _WORKSPACE_CACHE_LOADED, _WORKSPACE_CACHE_LOADED_AT
  import time

  now_ts = time.time()
  if (
      _WORKSPACE_CACHE_LOADED
      and not force
      and (now_ts - _WORKSPACE_CACHE_LOADED_AT) < 5.0
  ):
    return
  _WORKSPACE_CACHE_LOADED = True
  _WORKSPACE_CACHE_LOADED_AT = now_ts
  try:
    from google.cloud import storage

    bucket_name = config.get(
        "bucket", "content", fallback="your-pitchgen-content-bucket"
    )
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob("ge_sessions/_latest_workspace_state.json")
    if blob.exists():
      data = json.loads(blob.download_as_text())
      if isinstance(data, dict):
        for k, v in data.items():
          if v and isinstance(v, str):
            _LATEST_OUTLINE_CACHE[k] = v
  except Exception:
    pass


def _collect_prior_outline_surface_ids(tool_context: Any = None) -> list[str]:
  """Collects all previously emitted outline A2UI surfaceIds from session state and in-memory fallback cache."""
  seen: list[str] = []

  def _add(val: Any) -> None:
    if not val:
      return
    if isinstance(val, list):
      for item in val:
        _add(item)
      return
    s = str(val).strip()
    if s and s not in seen:
      seen.append(s)

  if (
      tool_context
      and hasattr(tool_context, "state")
      and tool_context.state is not None
  ):
    try:
      _add(tool_context.state.get("outline_surface_ids"))
      _add(tool_context.state.get("last_outline_surface_id"))
    except Exception:
      pass

  try:
    raw_list = _LATEST_OUTLINE_CACHE.get("_outline_surface_ids_")
    if raw_list:
      _add(json.loads(raw_list))
    _add(_LATEST_OUTLINE_CACHE.get("_latest_surface_id_"))
  except Exception:
    pass

  return seen


def _record_outline_surface_id(
    tool_context: Any = None, surface_id: str = ""
) -> None:
  """Records an outline A2UI surfaceId into both session state and in-memory fallback cache."""
  s = str(surface_id or "").strip()
  if not s or "outline" not in s.lower():
    return
  prior = _collect_prior_outline_surface_ids(tool_context)
  if s not in prior:
    prior.append(s)
  if (
      tool_context
      and hasattr(tool_context, "state")
      and tool_context.state is not None
  ):
    try:
      tool_context.state["last_outline_surface_id"] = s
      tool_context.state["outline_surface_ids"] = prior
    except Exception:
      pass
  try:
    _LATEST_OUTLINE_CACHE["_latest_surface_id_"] = s
    _LATEST_OUTLINE_CACHE["_outline_surface_ids_"] = json.dumps(prior)
  except Exception:
    pass


def _normalize_agendas_to_sections(
    agendas: Any,
    deck_length: str = "Standard",
    preserve_explicit_counts: bool = False,
) -> list[dict[str, Any]]:
  """Normalizes GlobalState agendas (dict keyed by '1'..'N' or list) into a list of section dicts with slide_count aligned to deck_length."""
  agendas_list = []
  if isinstance(agendas, dict):
    try:
      ag_items = sorted(
          agendas.items(),
          key=lambda x: int(x[0]) if str(x[0]).isdigit() else str(x[0]),
      )
      agendas_list = [v for k, v in ag_items]
    except Exception:
      agendas_list = list(agendas.values())
  elif isinstance(agendas, list):
    agendas_list = agendas
  elif agendas:
    agendas_list = [agendas]

  temp_agendas_dict = {}
  for idx, ag in enumerate(agendas_list, start=1):
    explicit_slides = None
    if isinstance(ag, dict):
      title = (
          ag.get("title")
          or ag.get("agenda_title")
          or ag.get("name")
          or f"Section {idx}"
      )
      subs = (
          ag.get("subtopics")
          or ag.get("parts")
          or ag.get("topics")
          or ag.get("bullets")
          or []
      )
      explicit_slides = ag.get("slides") or ag.get("slide_count")
    elif isinstance(ag, str):
      title = ag
      subs = []
    else:
      title = f"Section {idx}"
      subs = []

    if not isinstance(subs, list):
      subs = [str(subs)]

    sec_entry = {
        "title": str(title),
        "subtopics": subs,
        "parts": subs,
        "slide_count": (
            int(explicit_slides) if explicit_slides else max(1, len(subs))
        ),
    }
    temp_agendas_dict[str(idx)] = sec_entry

  # Reconcile section slide_count with chosen deck_length so A2UI Outline Card Target Slides matches requested deck length
  try:
    from agents.workflows.agenda_workflow import AgendaWorkflow

    AgendaWorkflow.reconcile_agendas_with_deck_length(
        temp_agendas_dict,
        deck_length=str(deck_length or "Standard"),
        preserve_explicit_counts=preserve_explicit_counts,
    )
  except Exception:
    pass

  try:
    sorted_keys = sorted(
        temp_agendas_dict.keys(),
        key=lambda x: int(x) if str(x).isdigit() else str(x),
    )
  except Exception:
    sorted_keys = list(temp_agendas_dict.keys())

  return [
      {
          "title": temp_agendas_dict[k]["title"],
          "subtopics": (
              temp_agendas_dict[k].get("subtopics")
              or temp_agendas_dict[k].get("parts")
              or []
          ),
          "slide_count": int(temp_agendas_dict[k].get("slide_count", 1) or 1),
      }
      for k in sorted_keys
  ]


def _extract_language_from_text(text: str) -> str:
  """Extracts a supported PitchGen target language from free-text instructions if mentioned."""
  clean = str(text or "").strip()
  if not clean:
    return ""
  low = clean.lower()
  alias_map = {
      "chinese (simplified)": "Chinese (Simplified)",
      "simplified chinese": "Chinese (Simplified)",
      "mandarin": "Chinese (Simplified)",
      "chinese (traditional)": "Chinese (Traditional)",
      "traditional chinese": "Chinese (Traditional)",
      "chinese": "Chinese (Simplified)",
  }
  for lang in getattr(a2ui_util, "PITCHGEN_TRANSLATE_LANGUAGES", []):
    alias_map.setdefault(lang.lower(), lang)

  ordered_keys = sorted(alias_map.keys(), key=len, reverse=True)
  pattern_keys = "|".join(re.escape(k) for k in ordered_keys)
  m_dir = re.search(
      rf"\b(?:into|to|in|target\s+language\s*[:=]?)\s+({pattern_keys})(?:\b|\))",
      low,
  )
  if m_dir:
    return alias_map[m_dir.group(1)]

  non_english_keys = [k for k in ordered_keys if k != "english"]
  for k in non_english_keys:
    if "(" in k or ")" in k:
      if k in low:
        return alias_map[k]
    elif re.search(rf"\b{re.escape(k)}\b", low):
      return alias_map[k]

  if re.match(r"^(?:translate\s+(?:to\s+|into\s+)?)?english[!.?\s]*$", low):
    return "English"
  return ""


def _apply_outline_refinement_and_edits(
    base_outline_raw: str,
    refinement_instructions: str = "",
    deck_strategy: str = "",
    section_edits: dict[str, Any] | None = None,
) -> tuple[str, list[dict[str, Any]], str, str]:
  """Applies inline A2UI section edits, deck strategy updates, and AI refinement instructions to a cached proposal outline.

  Returns:
    Tuple of (updated_raw_outline_json, updated_agenda_sections, customer_name, deck_strategy).
  """
  import copy
  from google import genai

  parsed = json.loads(base_outline_raw)
  wrapper = copy.deepcopy(parsed) if isinstance(parsed, dict) else {"data": {}}
  state_data = wrapper.get("data", wrapper) if isinstance(wrapper, dict) else {}
  if not isinstance(state_data, dict):
    state_data = {}

  ctx = state_data.get("context")
  if not isinstance(ctx, dict):
    ctx = {}
    state_data["context"] = ctx

  cust = str(
      ctx.get("customer_name")
      or state_data.get("customer_name")
      or (state_data.get("outline") or {}).get("customer_name")
      or "Customer"
  ).strip()

  if deck_strategy and str(deck_strategy).strip():
    strat = str(deck_strategy).strip()
    ctx["deck_strategy"] = strat
    state_data["deck_strategy"] = strat
  else:
    strat = str(
        ctx.get("deck_strategy")
        or state_data.get("deck_strategy")
        or "smart_hybrid"
    ).strip()

  deck_len_val = str(
      ctx.get("deck_length")
      or ctx.get("request_type")
      or state_data.get("deck_length")
      or (state_data.get("outline") or {}).get("deck_length")
      or "Standard"
  ).strip()

  # 1. Apply any inline section title/subtopic edits submitted from the A2UI form
  agendas = state_data.get("agendas", {})
  has_explicit_counts = isinstance(agendas, dict) and any(
      isinstance(v, dict) and v.get("slide_count") for v in agendas.values()
  )
  agenda_sections = _normalize_agendas_to_sections(
      agendas,
      deck_length=deck_len_val,
      preserve_explicit_counts=has_explicit_counts,
  )
  if section_edits and isinstance(section_edits, dict) and agenda_sections:
    for idx, sec in enumerate(agenda_sections, start=1):
      t_key = f"sec_{idx}_title"
      s_key = f"sec_{idx}_subtopics"
      if t_key in section_edits and str(section_edits[t_key] or "").strip():
        sec["title"] = str(section_edits[t_key]).strip()
      if s_key in section_edits and str(section_edits[s_key] or "").strip():
        raw_subs = str(section_edits[s_key]).strip()
        parts_list = [
            p.strip()
            for p in re.split(r"\s*[•|;\n]\s*", raw_subs)
            if p.strip()
        ]
        if parts_list:
          sec["subtopics"] = parts_list
    agenda_sections = _normalize_agendas_to_sections(
        agenda_sections,
        deck_length=deck_len_val,
        preserve_explicit_counts=True,
    )

  # Write normalized sections back into state_data["agendas"] and state_data["outline"]
  def _sync_sections_into_state(sections_list: list[dict[str, Any]]) -> None:
    new_agendas_dict = {}
    new_outline_items = []
    for i, s_obj in enumerate(sections_list, start=1):
      s_title = str(s_obj.get("title") or f"Section {i}").strip()
      s_subs = [
          str(x).strip()
          for x in (s_obj.get("subtopics") or [])
          if str(x).strip()
      ]
      if not s_subs:
        s_subs = [f"Key strategic insights for {s_title}"]
      s_count = int(s_obj.get("slide_count") or len(s_subs) or 1)
      new_agendas_dict[str(i)] = {
          "title": s_title,
          "parts": s_subs,
          "slide_count": s_count,
      }
      new_outline_items.extend(s_subs)
    state_data["agendas"] = new_agendas_dict
    if not isinstance(state_data.get("outline"), dict):
      state_data["outline"] = {"title": f"Pitch Deck for {cust}"}
    state_data["outline"]["outline"] = new_outline_items

  _sync_sections_into_state(agenda_sections)

  # 2. If user provided natural-language refinement_instructions, run fast Gemini refinement pass
  clean_instr = str(refinement_instructions or "").strip()
  if clean_instr:
    ctx["last_refinement_instructions"] = clean_instr
    orig_bc = str(ctx.get("business_context") or "").strip()
    ctx["business_context"] = (
        f"{orig_bc}\n\n[Refinement Requirement]: {clean_instr}".strip()
    )
    try:
      fast_model_name = config["default"].get(
          "gemini_model_1", "gemini-3.5-flash-lite"
      )
      client = genai.Client(
          vertexai=True, project=project_id, location="global"
      )
      refine_prompt = f"""You are refining an executive Google Cloud presentation outline and section agendas for '{cust}'.

Current Presentation Outline & Sections:
{json.dumps(agenda_sections, indent=2)}

Customer Context & Industry:
- Customer: {cust}
- Industry: {ctx.get('industry', '')}
- Sales Play(s): {ctx.get('salesPlay', [])}
- Audience: {ctx.get('audience', [])}
- Deck Length: {deck_len_val}
- Original Business Context: {orig_bc}

USER REFINEMENT INSTRUCTIONS:
"{clean_instr}"

Instructions:
1. Modify the presentation sections (`sections`) to directly fulfill the USER REFINEMENT INSTRUCTIONS above (e.g. adding new sections/slides, adjusting `slide_count`, removing sections, merging sections, reordering sections, or tailoring titles and subtopics).
2. Keep each section's existing `slide_count` unless the user asked to add or remove slides or sections.
3. Never include leading section numbers (like '01' or '1.') in `title` strings.
4. Return ONLY a valid JSON object with this exact schema:
{{
  "deck_title": "Updated presentation title",
  "sections": [
    {{
      "title": "Section Title",
      "subtopics": ["Subtopic 1", "Subtopic 2"],
      "slide_count": 1
    }}
  ]
}}"""
      resp = client.models.generate_content(
          model=fast_model_name,
          contents=refine_prompt,
          config=types.GenerateContentConfig(
              response_mime_type="application/json",
              temperature=0.2,
          ),
      )
      resp_text = getattr(resp, "text", "") or ""
      if resp_text:
        refined_json = json.loads(resp_text)
        refined_secs = refined_json.get("sections")
        if isinstance(refined_secs, list) and refined_secs:
          updated_sections = []
          for idx, r_sec in enumerate(refined_secs, start=1):
            if isinstance(r_sec, dict):
              r_title = re.sub(
                  r"^\s*(?:0?[1-9]|1[0-9])[\.\:\-\s]+",
                  "",
                  str(r_sec.get("title") or f"Section {idx}").strip(),
              ).strip()
              r_subs = [
                  str(x).strip()
                  for x in (r_sec.get("subtopics") or r_sec.get("parts") or [])
                  if str(x).strip()
              ]
              prior_sc = (
                  agenda_sections[idx - 1].get("slide_count", 1)
                  if idx - 1 < len(agenda_sections)
                  else 1
              )
              r_sc = int(r_sec.get("slide_count") or prior_sc or 1)
              updated_sections.append({
                  "title": r_title or f"Section {idx}",
                  "subtopics": r_subs or [f"Executive insights for {r_title}"],
                  "slide_count": max(1, r_sc),
              })
          if updated_sections:
            agenda_sections = _normalize_agendas_to_sections(
                updated_sections,
                deck_length=deck_len_val,
                preserve_explicit_counts=True,
            )
            _sync_sections_into_state(agenda_sections)
            if refined_json.get("deck_title") and isinstance(
                state_data.get("outline"), dict
            ):
              state_data["outline"]["title"] = str(
                  refined_json["deck_title"]
              ).strip()
    except Exception as llm_err:
      logging.warning(
          "[enterprise_agent] LLM outline refinement warning: %s", llm_err
      )

  # Upload updated outline to GCS if filename exists
  try:
    from pitchgen_utils.gcs_util import write_gcs_file
    import datetime

    bucket_name = config.get("bucket", "content")
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    er_num = str(ctx.get("er_number") or "").strip()
    uid = str(ctx.get("user_input_id") or "refined").strip()
    fname = (
        f"outline_{er_num}_{timestamp}.json"
        if er_num
        else f"outline_no_er_{uid}_{timestamp}.json"
    )
    gcs_url = f"gs://{bucket_name}/{fname}"
    state_data["filename"] = gcs_url
    write_gcs_file(gcs_url, json.dumps(state_data))
  except Exception:
    pass

  if "data" in wrapper:
    wrapper["data"] = state_data
  else:
    wrapper = {"Status": "True", "data": state_data, "message": "Success"}

  return json.dumps(wrapper, indent=2), agenda_sections, cust, strat


def _outline_sales_play_label(raw_outline: Any) -> str:
  """Returns a display label for an outline's sales play(s) for the outline card subtitle."""
  try:
    parsed = (
        json.loads(raw_outline) if isinstance(raw_outline, str) else raw_outline
    )
    inner = parsed.get("data", parsed) if isinstance(parsed, dict) else {}
    o_ctx = inner.get("context") if isinstance(inner, dict) else {}
    o_ctx = o_ctx if isinstance(o_ctx, dict) else {}
    sp = (
        o_ctx.get("salesPlay")
        or o_ctx.get("sales_play")
        or (inner.get("salesPlay") if isinstance(inner, dict) else "")
        or ""
    )
  except Exception:
    return ""
  if isinstance(sp, (list, tuple)):
    return ", ".join(str(x).strip() for x in sp if str(x).strip())
  return str(sp or "").strip()


def _split_outline_subtopics(raw: Any) -> list[str]:
  """Splits outline subtopics given as a list or a newline/bullet/semicolon/comma string."""
  if isinstance(raw, (list, tuple)):
    items = [str(s) for s in raw]
  elif raw is None or isinstance(raw, dict):
    items = []
  else:
    text = str(raw)
    if "\n" in text or "•" in text or ";" in text:
      items = re.split(r"[\n•;]+", text)
    else:
      items = text.split(",") if "," in text else [text]
  return [
      s.strip().lstrip("•-*").strip()
      for s in items
      if s.strip().lstrip("•-*").strip()
  ]


_OUTLINE_CLOSING_SECTION_RE = re.compile(
    r"next\s+steps?|roadmap|path\s+forward|call\s+to\s+action|realization"
    r"|commercials|way\s+forward",
    re.IGNORECASE,
)


def _apply_outline_section_action(
    base_outline_raw: str,
    action_name: str,
    action_ctx: dict[str, Any] | None = None,
) -> tuple[str, list[dict[str, Any]], str, str, str]:
  """Deterministically applies an outline card per-section Edit / Delete / Add action (no LLM).

  Args:
    base_outline_raw: Cached proposal outline JSON (state["proposal_outline"]).
    action_name: 'save_outline_section_edit', 'delete_outline_section' or
      'add_outline_section'.
    action_ctx: Resolved A2UI event context from the outline card.

  Returns:
    Tuple of (updated_raw_outline_json, agenda_sections, customer_name,
    deck_strategy, user_facing_summary).
  """
  import copy

  a_ctx = action_ctx if isinstance(action_ctx, dict) else {}

  def _val(*keys: str) -> str:
    for k in keys:
      v = a_ctx.get(k)
      if v is None or isinstance(v, dict):
        continue
      s = _clean_str(v).strip()
      if s:
        return s
    return ""

  def _count(raw: str, default: int) -> int:
    try:
      return max(1, min(99, int(float(str(raw).strip()))))
    except Exception:
      return max(1, int(default or 1))

  parsed = json.loads(base_outline_raw)
  wrapper = copy.deepcopy(parsed) if isinstance(parsed, dict) else {"data": {}}
  state_data = wrapper.get("data", wrapper) if isinstance(wrapper, dict) else {}
  if not isinstance(state_data, dict):
    state_data = {}
  o_ctx = state_data.get("context")
  if not isinstance(o_ctx, dict):
    o_ctx = {}
    state_data["context"] = o_ctx

  cust = str(
      o_ctx.get("customer_name")
      or state_data.get("customer_name")
      or _val("customer_name")
      or "Customer"
  ).strip()
  strat = str(
      o_ctx.get("deck_strategy")
      or state_data.get("deck_strategy")
      or _val("deck_strategy")
      or "smart_hybrid"
  ).strip()
  deck_len_val = str(
      o_ctx.get("deck_length")
      or o_ctx.get("request_type")
      or state_data.get("deck_length")
      or "Standard"
  ).strip()

  agendas = state_data.get("agendas", {})
  has_explicit_counts = isinstance(agendas, dict) and any(
      isinstance(v, dict) and v.get("slide_count") for v in agendas.values()
  )
  sections = _normalize_agendas_to_sections(
      agendas,
      deck_length=deck_len_val,
      preserve_explicit_counts=has_explicit_counts,
  )

  pos = -1
  raw_idx = _val("section_index", "section_zero_index")
  if raw_idx:
    try:
      pos = int(float(raw_idx))
    except Exception:
      pos = -1
  elif _val("section_number"):
    try:
      pos = int(float(_val("section_number"))) - 1
    except Exception:
      pos = -1

  act = str(action_name or "").strip().lower()
  changed = False
  if act == "view":
    # Read-only: normalize sections for re-rendering without any mutation.
    summary = ""
  elif "delete" in act:
    expected_title = _val("section_title")
    if expected_title and not (
        0 <= pos < len(sections)
        and sections[pos].get("title", "").strip().lower()
        == expected_title.lower()
    ):
      # Card indices may be stale; fall back to matching the section title.
      for i, sec in enumerate(sections):
        if sec.get("title", "").strip().lower() == expected_title.lower():
          pos = i
          break
    if not 0 <= pos < len(sections):
      summary = "That section was already removed from the outline."
    elif len(sections) <= 1:
      summary = (
          "The outline needs at least one section, so the last section was"
          " kept. Add a new topic first, then remove this one."
      )
    else:
      removed = sections.pop(pos)
      changed = True
      summary = f"Removed section {pos + 1}: **{removed.get('title', '')}**."
  elif "add" in act:
    new_title = _val("new_topic_title", "new_section_title", "section_title")
    new_title = re.sub(
        r"^\s*(?:0?[1-9]|1[0-9])[\.\:\-\s]+", "", new_title
    ).strip()
    if not new_title:
      summary = "Enter a topic title to add a new agenda section."
    else:
      new_subs = _split_outline_subtopics(
          _val("new_topic_subtopics", "new_subtopics_text", "subtopics_text")
      ) or [f"Key strategic insights for {new_title}"]
      new_sec = {
          "title": new_title,
          "subtopics": new_subs,
          "slide_count": _count(
              _val("new_topic_slides", "slide_count"), len(new_subs)
          ),
      }
      insert_at = len(sections)
      if len(sections) >= 2 and _OUTLINE_CLOSING_SECTION_RE.search(
          sections[-1].get("title", "")
      ):
        insert_at = len(sections) - 1
      sections.insert(insert_at, new_sec)
      changed = True
      summary = f"Added section {insert_at + 1}: **{new_title}**."
  else:
    if not 0 <= pos < len(sections):
      summary = "That section no longer exists in the outline."
    else:
      cur = dict(sections[pos])
      new_title = _val("section_title", "new_section_title")
      if new_title:
        cur["title"] = re.sub(
            r"^\s*(?:0?[1-9]|1[0-9])[\.\:\-\s]+", "", new_title
        ).strip() or cur.get("title", "")
      raw_subs = a_ctx.get("subtopics_text")
      if raw_subs is None or isinstance(raw_subs, dict):
        raw_subs = a_ctx.get("subtopics")
      if isinstance(raw_subs, (list, str)):
        subs = _split_outline_subtopics(raw_subs)
        if subs:
          cur["subtopics"] = subs
      new_sub = _val("new_subtopic")
      if new_sub and new_sub not in (cur.get("subtopics") or []):
        cur["subtopics"] = list(cur.get("subtopics") or []) + [new_sub]
      if _val("slide_count"):
        cur["slide_count"] = _count(
            _val("slide_count"), cur.get("slide_count", 1)
        )
      changed = cur != sections[pos]
      sections[pos] = cur
      summary = f"Updated section {pos + 1}: **{cur.get('title', '')}**."

  sections = _normalize_agendas_to_sections(
      sections, deck_length=deck_len_val, preserve_explicit_counts=True
  )

  if changed:
    new_agendas: dict[str, Any] = {}
    outline_items: list[str] = []
    for i, sec in enumerate(sections, start=1):
      s_title = str(sec.get("title") or f"Section {i}").strip()
      s_subs = [
          str(x).strip() for x in sec.get("subtopics") or [] if str(x).strip()
      ] or [f"Key strategic insights for {s_title}"]
      new_agendas[str(i)] = {
          "title": s_title,
          "parts": s_subs,
          "slide_count": int(sec.get("slide_count") or len(s_subs) or 1),
      }
      outline_items.extend(s_subs)
    state_data["agendas"] = new_agendas
    if not isinstance(state_data.get("outline"), dict):
      state_data["outline"] = {"title": f"Pitch Deck for {cust}"}
    state_data["outline"]["outline"] = outline_items

  if isinstance(wrapper, dict) and "data" in wrapper:
    wrapper["data"] = state_data
  else:
    wrapper = {"Status": "True", "data": state_data, "message": "Success"}
  return json.dumps(wrapper, indent=2), sections, cust, strat, summary


# View-only outline card events (server-driven inline editing on the Material
# outline card). They toggle which inline block is expanded and never mutate
# state["proposal_outline"].
_OUTLINE_VIEW_EVENTS = (
    "open_outline_section_editor",
    "open_outline_section_delete_confirm",
    "open_outline_add_topic",
    "cancel_outline_section_edit",
)
_OUTLINE_MUTATION_EVENTS = (
    "save_outline_section_edit",
    "delete_outline_section",
    "add_outline_section",
)


def _resolve_outline_section_pos(
    sections: list[dict[str, Any]], action_ctx: dict[str, Any]
) -> int:
  """Resolves the 0-based section index from an outline card event (index, number, then title)."""
  pos = -1
  for key, offset in (("section_index", 0), ("section_number", 1)):
    raw = action_ctx.get(key)
    if raw is None or isinstance(raw, (dict, bool)) or str(raw).strip() == "":
      continue
    try:
      pos = int(float(str(raw).strip())) - offset
      break
    except Exception:
      continue
  title = _clean_str(action_ctx.get("section_title") or "").strip().lower()
  if title and not (
      0 <= pos < len(sections)
      and str(sections[pos].get("title", "")).strip().lower() == title
  ):
    for i, sec in enumerate(sections):
      if str(sec.get("title", "")).strip().lower() == title:
        return i
  return pos if 0 <= pos < len(sections) else -1


def _handle_outline_section_action(
    callback_context: Any,
    action_name: str,
    action_ctx: dict[str, Any],
) -> Any:
  """Applies an outline card Edit/Delete/Add (or view-only open/cancel) action and returns an LlmResponse with the re-rendered outline card (or None if no outline is cached)."""
  state = getattr(callback_context, "state", None)
  cust_hint = _clean_str(action_ctx.get("customer_name") or "").strip()
  cached_raw = None
  if state is not None and hasattr(state, "get"):
    cached_raw = state.get("proposal_outline")
  if not cached_raw:
    cust_k = f"cust:{cust_hint.lower()}" if cust_hint else ""
    if cust_k and cust_k in _LATEST_OUTLINE_CACHE:
      cached_raw = _LATEST_OUTLINE_CACHE[cust_k]
    else:
      cached_raw = _LATEST_OUTLINE_CACHE.get("_latest_")
  if not cached_raw:
    return None

  is_view = action_name in _OUTLINE_VIEW_EVENTS
  updated_raw, sections, cust, strat, summary = _apply_outline_section_action(
      cached_raw, "view" if is_view else action_name, action_ctx
  )

  # Which inline block (if any) the re-rendered Material card expands.
  ui_kwargs: dict[str, Any] = {}
  ui_state: dict[str, Any] | None = None
  if is_view:
    pos = _resolve_outline_section_pos(sections, action_ctx)
    if action_name == "open_outline_section_editor" and pos >= 0:
      ui_kwargs["editing_index"] = pos
      ui_state = {"mode": "edit", "index": pos}
      summary = (
          f"Editing section {pos + 1}. Update the fields, then select Save."
      )
    elif action_name == "open_outline_section_delete_confirm" and pos >= 0:
      if len(sections) <= 1:
        summary = (
            "The outline needs at least one section, so this section can't be"
            " removed. Add a new topic first."
        )
      else:
        ui_kwargs["confirm_delete_index"] = pos
        ui_state = {"mode": "confirm_delete", "index": pos}
        summary = (
            f"Remove section {pos + 1}:"
            f" **{sections[pos].get('title', '')}**? Confirm below."
        )
    elif action_name == "open_outline_add_topic":
      ui_kwargs["show_add_topic"] = True
      ui_state = {"mode": "add", "index": None}
      summary = "Add a new agenda topic below, then select Add."
    elif action_name == "cancel_outline_section_edit":
      summary = "No changes made."
    else:
      summary = "That section no longer exists in the outline."
  elif action_name == "add_outline_section" and summary.startswith(
      "Enter a topic title"
  ):
    # Keep the inline add-topic block open so the seller can fill in a title.
    ui_kwargs["show_add_topic"] = True
    ui_state = {"mode": "add", "index": None}

  if state is not None:
    try:
      state["outline_ui_state"] = ui_state
      if not is_view:
        state["proposal_outline"] = updated_raw
        state["latest_outline_state_json"] = updated_raw
        state["outline_generated"] = True
    except Exception:
      pass
  if not is_view:
    try:
      _LATEST_OUTLINE_CACHE["_latest_"] = updated_raw
      if cust:
        _LATEST_OUTLINE_CACHE[f"cust:{cust.strip().lower()}"] = updated_raw
    except Exception:
      pass

  import uuid

  prev_surface_ids = _collect_prior_outline_surface_ids(callback_context)
  new_surface_id = f"pitchgen-outline-{uuid.uuid4().hex[:8]}"
  active_ver = a2ui_util.detect_client_a2ui_version(
      tool_context=callback_context, default_version="v0.9"
  )
  outline_msgs = a2ui_util.create_a2ui_outline_messages(
      customer_name=cust or cust_hint or "Customer",
      agenda_sections=sections,
      deck_strategy=strat,
      surface_id=new_surface_id,
      version=active_ver,
      previous_surface_id=prev_surface_ids[-1] if prev_surface_ids else None,
      previous_surface_ids=prev_surface_ids,
      sales_play=_outline_sales_play_label(updated_raw),
      **ui_kwargs,
  )
  _record_outline_surface_id(callback_context, new_surface_id)

  total_slides = sum(int(s.get("slide_count") or 1) for s in sections)
  if is_view or ui_kwargs:
    anchor_text = summary
  else:
    anchor_text = (
        f"{summary} The outline now has {len(sections)} sections and"
        f" {total_slides} target slides. Review it below, then approve to"
        " generate the deck."
    )
  logging.info(
      "[enterprise_before_model_callback] Outline section action '%s'"
      " applied without LLM (surfaceId='%s', sections=%d).",
      action_name,
      new_surface_id,
      len(sections),
  )
  return LlmResponse(
      content=types.Content(
          role="model",
          parts=[types.Part(text=anchor_text)]
          + [
              a2ui_util.create_a2a_part_from_a2ui_payload(m)
              for m in outline_msgs
          ],
      ),
      custom_metadata={"a2a:response": True},
  )


def enterprise_refine_proposal_outline(
    refinement_instructions: str = "",
    customer_name: str = "",
    deck_strategy: str = "",
    section_edits_json: str = "",
    tool_context: Any = None,
) -> str:
  """Refines the existing proposal outline and section agendas based on user instructions or inline A2UI edits, and emits an updated interactive A2UI Outline Review card."""
  refinement_instructions = _clean_str(refinement_instructions)
  customer_name = _clean_str(customer_name)
  deck_strategy = _clean_str(deck_strategy)

  cached_raw = None
  if (
      tool_context
      and hasattr(tool_context, "state")
      and tool_context.state is not None
  ):
    try:
      cached_raw = tool_context.state.get("proposal_outline")
    except Exception:
      pass

  prev_surface_ids = _collect_prior_outline_surface_ids(tool_context)

  if not cached_raw:
    cust_key = f"cust:{customer_name.strip().lower()}" if customer_name else ""
    if cust_key and cust_key in _LATEST_OUTLINE_CACHE:
      cached_raw = _LATEST_OUTLINE_CACHE[cust_key]
    else:
      cached_raw = _LATEST_OUTLINE_CACHE.get("_latest_")

  if not cached_raw:
    # No existing outline in session cache — fall back to creating a new outline
    return enterprise_create_proposal_outline(
        business_context=refinement_instructions
        or f"Executive pitch deck for {customer_name or 'Customer'}",
        customer_name=customer_name,
        tool_context=tool_context,
    )

  section_edits = {}
  if section_edits_json:
    try:
      section_edits = (
          json.loads(section_edits_json)
          if isinstance(section_edits_json, str)
          else dict(section_edits_json)
      )
    except Exception:
      section_edits = {}

  pre_refined_ready = False
  if (
      tool_context
      and hasattr(tool_context, "state")
      and tool_context.state is not None
  ):
    try:
      pre_refined_ready = bool(
          tool_context.state.get("_pre_refined_outline_ready")
      )
    except Exception:
      pre_refined_ready = False
  if not pre_refined_ready:
    pre_refined_ready = bool(_LATEST_OUTLINE_CACHE.get("_pre_refined_ready_"))

  if pre_refined_ready and cached_raw:
    try:
      if (
          tool_context
          and hasattr(tool_context, "state")
          and tool_context.state is not None
      ):
        tool_context.state["_pre_refined_outline_ready"] = False
      _LATEST_OUTLINE_CACHE["_pre_refined_ready_"] = False
      parsed_cached = json.loads(cached_raw)
      inner_cached = (
          parsed_cached.get("data", parsed_cached)
          if isinstance(parsed_cached, dict)
          else {}
      )
      updated_raw = cached_raw
      cached_dl = (
          (inner_cached.get("context") or {}).get("deck_length")
          or (inner_cached.get("context") or {}).get("request_type")
          or inner_cached.get("deck_length")
          or "Standard"
      )
      agenda_sections = _normalize_agendas_to_sections(
          inner_cached.get("agendas", {}), deck_length=str(cached_dl)
      )
      cust = (
          (inner_cached.get("context") or {}).get("customer_name")
          or customer_name
          or "Customer"
      )
      strat = (
          (inner_cached.get("context") or {}).get("deck_strategy")
          or deck_strategy
          or "smart_hybrid"
      )
    except Exception:
      updated_raw, agenda_sections, cust, strat = (
          _apply_outline_refinement_and_edits(
              base_outline_raw=cached_raw,
              refinement_instructions=refinement_instructions,
              deck_strategy=deck_strategy,
              section_edits=section_edits,
          )
      )
  else:
    updated_raw, agenda_sections, cust, strat = (
        _apply_outline_refinement_and_edits(
            base_outline_raw=cached_raw,
            refinement_instructions=refinement_instructions,
            deck_strategy=deck_strategy,
            section_edits=section_edits,
        )
    )

  import uuid

  new_surface_id = f"pitchgen-outline-{uuid.uuid4().hex[:8]}"
  active_ver = a2ui_util.detect_client_a2ui_version(
      tool_context=tool_context, default_version="v0.9"
  )
  outline_msgs = a2ui_util.create_a2ui_outline_messages(
      customer_name=cust or customer_name or "Customer",
      agenda_sections=agenda_sections,
      deck_strategy=strat,
      surface_id=new_surface_id,
      version=active_ver,
      previous_surface_id=prev_surface_ids[-1] if prev_surface_ids else None,
      previous_surface_ids=prev_surface_ids,
      sales_play=_outline_sales_play_label(updated_raw),
  )
  _stash_a2ui_payload(tool_context, outline_msgs)
  _record_outline_surface_id(tool_context, new_surface_id)

  sec_titles = [
      s.get("title", "") for s in agenda_sections[:6] if s.get("title")
  ]
  cot_refine = (
      "**Executive Outline Refinement"
      f" ({cust or customer_name or 'Customer'})**\n- **Applied Guidance**:"
      " Incorporated refinement directive"
      f" (`{refinement_instructions or 'inline section adjustments'}`) under"
      f" `{strat}` strategy.\n- **Updated Narrative Arc ({len(agenda_sections)}"
      " Sections)**: "
      + (
          ", ".join(f"*{t}*" for t in sec_titles)
          if sec_titles
          else "Refined CVI storyline"
      )
      + "."
  )

  if (
      tool_context
      and hasattr(tool_context, "state")
      and tool_context.state is not None
  ):
    try:
      tool_context.state["outline_generated"] = True
      tool_context.state["proposal_outline"] = updated_raw
      tool_context.state["latest_outline_state_json"] = updated_raw
      tool_context.state["latest_cot_summary"] = cot_refine
      if refinement_instructions:
        tool_context.state["last_applied_refinement_instructions"] = (
            refinement_instructions
        )
    except Exception:
      pass

  try:
    _LATEST_OUTLINE_CACHE["_latest_"] = updated_raw
    _LATEST_OUTLINE_CACHE["_latest_cot_"] = cot_refine
    if refinement_instructions:
      _LATEST_OUTLINE_CACHE["_last_applied_refinement_"] = (
          refinement_instructions
      )
    if cust:
      _LATEST_OUTLINE_CACHE[f"cust:{cust.strip().lower()}"] = updated_raw
  except Exception:
    pass

  try:
    import copy

    compact_data = json.loads(updated_raw)
    inner = compact_data.get("data", compact_data)
    if isinstance(inner, dict) and isinstance(inner.get("context"), dict):
      if inner["context"].get("customer_research"):
        inner["context"]["customer_research"] = "[Cached in session state]"
      if inner["context"].get("developer_knowledge"):
        inner["context"]["developer_knowledge"] = "[Cached in session state]"
    return json.dumps(compact_data)
  except Exception:
    return updated_raw


def _hydrate_slide_generator_state(
    state_json: str, tool_context: Any = None
) -> str:
  """Hydrates state_json from cached proposal_outline so user_ldap, user_oauth_token, customer_research, and refined agendas are always preserved even when omitted or stale in LLM arguments."""
  try:
    passed_dict = json.loads(state_json) if state_json else {}
  except Exception:
    passed_dict = {}

  passed_inner = (
      passed_dict.get("data", passed_dict)
      if isinstance(passed_dict, dict)
      else {}
  )
  ctx = (
      passed_inner.get("context", {}) if isinstance(passed_inner, dict) else {}
  )

  cached_raw = None
  if (
      tool_context
      and hasattr(tool_context, "state")
      and tool_context.state is not None
  ):
    try:
      cached_raw = tool_context.state.get("proposal_outline")
    except Exception:
      cached_raw = None

  if not cached_raw:
    cust = (
        str(ctx.get("customer_name") or passed_inner.get("customer_name") or "")
        .strip()
        .lower()
    )
    ldap = (
        str(ctx.get("user_ldap") or passed_inner.get("user_ldap") or "")
        .strip()
        .lower()
    )
    if cust and f"cust:{cust}" in _LATEST_OUTLINE_CACHE:
      cached_raw = _LATEST_OUTLINE_CACHE[f"cust:{cust}"]
    elif ldap and f"ldap:{ldap}" in _LATEST_OUTLINE_CACHE:
      cached_raw = _LATEST_OUTLINE_CACHE[f"ldap:{ldap}"]
    else:
      cached_raw = _LATEST_OUTLINE_CACHE.get("_latest_")

  if not cached_raw:
    return state_json

  try:
    cached_dict = json.loads(cached_raw)
    base_state = (
        cached_dict.get("data", cached_dict)
        if isinstance(cached_dict, dict)
        else {}
    )
    if isinstance(base_state, dict):
      merged = dict(base_state)
      if isinstance(passed_inner, dict):
        # Authoritative agendas/outline live in base_state (proposal_outline cache).
        # Only fall back to passed_inner if base_state has no agendas/outline, or if agenda_sections was explicitly passed.
        if not merged.get("agendas") and passed_inner.get("agendas"):
          merged["agendas"] = passed_inner["agendas"]
        elif (
            isinstance(passed_inner.get("agenda_sections"), list)
            and passed_inner["agenda_sections"]
        ):
          converted_agendas = {}
          for idx, sec in enumerate(passed_inner["agenda_sections"], start=1):
            if isinstance(sec, dict):
              converted_agendas[str(idx)] = {
                  "title": (
                      sec.get("title")
                      or sec.get("agenda_title")
                      or f"Section {idx}"
                  ),
                  "parts": (
                      sec.get("subtopics")
                      or sec.get("parts")
                      or sec.get("topics")
                      or []
                  ),
                  "slides_number": (
                      sec.get("slides") or sec.get("slide_count") or 2
                  ),
              }
            elif isinstance(sec, str):
              converted_agendas[str(idx)] = {
                  "title": sec,
                  "parts": [],
                  "slides_number": 2,
              }
          if converted_agendas:
            merged["agendas"] = converted_agendas
        if not merged.get("outline") and passed_inner.get("outline"):
          merged["outline"] = passed_inner["outline"]
        merged_ctx = dict(merged.get("context", {}))
        if isinstance(passed_inner.get("context"), dict):
          for k, v in passed_inner["context"].items():
            if not v or v == "[Cached in session state]":
              continue
            # Never overwrite an authoritative Phase 1 OAuth token or user_ldap with a truncated/placeholder value
            if (
                k == "user_oauth_token"
                and merged_ctx.get("user_oauth_token")
                and len(str(v).strip()) < 50
            ):
              continue
            if (
                k == "user_ldap"
                and merged_ctx.get("user_ldap")
                and str(v).strip().lower()
                in ("unknown", "user", "none", "null", "")
            ):
              continue
            merged_ctx[k] = v
        for top_key in (
            "deck_strategy",
            "customer_name",
            "er_number",
            "industry",
            "audience",
            "region",
            "sales_stage",
            "win_cycle",
            "segment",
        ):
          if (
              passed_inner.get(top_key)
              and passed_inner.get(top_key) != "[Cached in session state]"
          ):
            merged_ctx[top_key] = passed_inner[top_key]
        merged["context"] = merged_ctx
      return json.dumps(merged)
  except Exception as e:
    logging.warning("[enterprise_agent] State hydration notice: %s", e)

  return state_json


def enterprise_slide_generator_skill(
    state_json: str,
    tool_context: Any = None,
) -> str:
  """Phase 2: Generates the full Google Slides pitch presentation with interactive Canvas side panel and Gemini Enterprise Quick Actions."""
  if (
      tool_context
      and hasattr(tool_context, "state")
      and tool_context.state is not None
      and hasattr(tool_context.state, "get")
      and tool_context.state.get("deck_just_generated")
      and tool_context.state.get("last_generated_deck_summary")
  ):
    logging.info(
        "[enterprise_agent] Skipping duplicate enterprise_slide_generator_skill"
        " call in same turn; returning cached deck summary."
    )
    return str(tool_context.state["last_generated_deck_summary"])

  hydrated_state_json = _hydrate_slide_generator_state(state_json, tool_context)
  raw_result = PitchGenSkills.enterprise_slide_generator_skill(
      state_json=hydrated_state_json,
      tool_context=tool_context,
  )

  try:
    parsed = json.loads(raw_result)
    deck_url = ""
    pres_id = ""
    customer_name = ""
    user_ldap = ""
    er_number = ""
    industry_val = ""
    sales_play_val = ""

    try:
      state_dict = json.loads(hydrated_state_json)
      state_inner = (
          state_dict.get("data", state_dict)
          if isinstance(state_dict, dict)
          else {}
      )
      ctx = (
          state_inner.get("context", {})
          if isinstance(state_inner, dict)
          else {}
      )
      customer_name = ctx.get("customer_name", "")
      user_ldap = ctx.get("user_ldap", "")
      er_number = ctx.get("er_number", "")
      industry_val = ctx.get("industry", "")
      sp_raw = ctx.get("salesPlay", "")
      sales_play_val = (
          ", ".join(str(x) for x in sp_raw if x)
          if isinstance(sp_raw, list)
          else str(sp_raw or "")
      )
    except Exception:
      pass

    deck_title = ""
    if isinstance(parsed, list):
      for item in parsed:
        if isinstance(item, dict):
          if "deck_url" in item:
            deck_url = item["deck_url"]
          if "presentation_id" in item:
            pres_id = item["presentation_id"]
          if "deck_title" in item:
            deck_title = item["deck_title"]
    elif isinstance(parsed, dict):
      deck_url = parsed.get("deck_url", parsed.get("deckURL", ""))
      pres_id = parsed.get("presentation_id", "")
      deck_title = parsed.get("deck_title", "")

    if not pres_id and deck_url:
      pres_id = a2ui_util.extract_presentation_id(deck_url) or ""

    if pres_id and (
        "open?id=" in deck_url or "/presentation/d/" not in deck_url
    ):
      deck_url = f"https://docs.google.com/presentation/d/{pres_id}/edit"

    if not user_ldap:
      _, resolved_ldap = a2ui_util.resolve_ge_user_identity(
          tool_context=tool_context
      )
      user_ldap = resolved_ldap or "unknown_user"

    if (
        deck_url
        and not deck_url.startswith("Error")
        and not deck_url.startswith("Please authorize")
    ):
      safe_title = (
          deck_title or f"[PitchGen] {customer_name or 'Customer'} Presentation"
      ).replace("'", "")
      canvas_artifact_proto = a2ui_util.build_canvas_artifact_textproto(
          deck_url=deck_url,
          title=safe_title,
          model_generated_id=f"pitchgen-deck-{pres_id or 'deck'}",
      )

      active_ver = a2ui_util.detect_client_a2ui_version(
          tool_context=tool_context, default_version="v0.9"
      )
      prev_outline_ids = _collect_prior_outline_surface_ids(tool_context)
      delete_msgs = []
      for old_sid in prev_outline_ids:
        delete_msgs.extend(
            a2ui_util.create_a2ui_delete_surface_message(
                surface_id=old_sid,
                version="v0.9" if active_ver == "v0.9" else "v0.8",
            )
        )
      if delete_msgs:
        _stash_a2ui_payload(tool_context, delete_msgs)

      cot_deck = (
          "**Presentation Synthesis & Governance"
          f" ({customer_name or 'Customer'})**\n- **Foundation & Reusable"
          f" Library Matching**: Assembled `{safe_title}` (`{pres_id}`)"
          " combining verified CloudHub reusable slides with bespoke Nano"
          " Banana architecture visuals.\n- **Slide Job Copy Governance**:"
          " Applied character-budget guardrails and preserved cited customer"
          " proof point metrics intact while granting edit access to"
          f" `{user_ldap}`."
      )

      formatted_summary = (
          "Your customized presentation deck for"
          f" **{customer_name or 'your customer'}** has been successfully"
          " synthesized and edit permissions granted to"
          f" **{user_ldap}**.\n\n### ⚡ Quick Refinements in Gemini"
          " Enterprise\n- **🔍 Search Slides**: Find reusable slides and"
          " customer architecture patterns from CloudHub\n- **✍️ Transform"
          " Slide Text**: Refine executive tone, adjust length, or tailor"
          " bullet points\n- **🍌 Generate Visuals**: Synthesize custom"
          " diagrams, topologies, and Nano Banana illustrations\n\n### 🔗"
          " Secondary Options & External Links\n- [📊 Open Google Slides"
          f" Presentation]({deck_url})\n- [🚀 Edit in Slides"
          " (https://your-sales-portal.example.com/pitchgen)](https://your-sales-portal.example.com/pitchgen)\n- [🎨 White-Glove Support"
          " (https://your-sales-portal.example.com/requests/new)](https://your-sales-portal.example.com/requests/new)"
      )

      try:
        _LATEST_OUTLINE_CACHE["_just_generated_deck_"] = json.dumps({
            "deck_url": deck_url,
            "pres_id": pres_id or "deck",
            "deck_title": safe_title,
            "customer_name": customer_name or "Customer",
            "active_ver": active_ver,
            "prev_outline_ids": prev_outline_ids,
            "cot_deck": cot_deck,
            "formatted_summary": formatted_summary,
        })
        _LATEST_OUTLINE_CACHE["_latest_deck_id_"] = pres_id
        _LATEST_OUTLINE_CACHE["_latest_deck_url_"] = deck_url
        if customer_name:
          _LATEST_OUTLINE_CACHE["_latest_customer_name_"] = customer_name
        if industry_val:
          _LATEST_OUTLINE_CACHE["_latest_industry_"] = industry_val
        if sales_play_val:
          _LATEST_OUTLINE_CACHE["_latest_sales_play_"] = sales_play_val
        _LATEST_OUTLINE_CACHE["_latest_cot_"] = cot_deck
        _persist_workspace_cache_to_gcs()
      except Exception:
        pass

      if (
          tool_context
          and hasattr(tool_context, "state")
          and tool_context.state is not None
      ):
        try:
          tool_context.state["deck_just_generated"] = True
          tool_context.state["deck_generated"] = True
          tool_context.state["deck_url"] = deck_url
          tool_context.state["deck_title"] = safe_title
          tool_context.state["presentation_id"] = pres_id
          tool_context.state["customer_name"] = customer_name
          if industry_val:
            tool_context.state["industry"] = industry_val
          if sales_play_val:
            tool_context.state["salesPlay"] = sales_play_val
          tool_context.state["canvas_artifact"] = canvas_artifact_proto
          tool_context.state["latest_cot_summary"] = cot_deck
          tool_context.state["last_generated_deck_summary"] = formatted_summary
        except Exception:
          pass

      return formatted_summary

    return raw_result
  except Exception as e:
    logging.warning(
        "[enterprise_agent] Error wrapping slide generator response: %s", e
    )
    return raw_result


def _resolve_active_deck_from_state_or_cache(
    presentation_url_or_id: str = "",
    tool_context: Any = None,
) -> tuple[str, str, str]:
  """Returns (presentation_id, deck_url, customer_name) from argument, session state, or (when session already has active work) cache."""
  raw_arg = _clean_str(presentation_url_or_id)
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
  if explicit_active_keyword or raw_lower in ("none", "null", "default"):
    raw_arg = ""

  pres_id = a2ui_util.extract_presentation_id(raw_arg) or ""
  state = getattr(tool_context, "state", None) if tool_context else None
  cust_name = ""
  session_has_active_work = False

  if state is not None and hasattr(state, "get"):
    cust_name = str(state.get("customer_name") or "").strip()
    if not pres_id:
      pres_id = (
          a2ui_util.extract_presentation_id(
              str(state.get("presentation_id") or "")
          )
          or a2ui_util.extract_presentation_id(str(state.get("deck_url") or ""))
          or a2ui_util.extract_presentation_id(
              str(state.get("canvas_artifact") or "")
          )
          or ""
      )
    session_has_active_work = bool(
        pres_id
        or cust_name
        or state.get("deck_generated")
        or state.get("outline_generated")
        or state.get("proposal_outline")
    )

  # Strictly isolate brand-new sessions: only consult cross-worker _LATEST_OUTLINE_CACHE
  # if this session already has an active outline/deck or the caller explicitly asked for "active".
  if explicit_active_keyword or session_has_active_work:
    _load_workspace_cache_from_gcs()
    if not pres_id:
      _load_workspace_cache_from_gcs(force=True)
      pres_id = (
          a2ui_util.extract_presentation_id(
              str(_LATEST_OUTLINE_CACHE.get("_latest_deck_id_") or "")
          )
          or a2ui_util.extract_presentation_id(
              str(_LATEST_OUTLINE_CACHE.get("_latest_deck_url_") or "")
          )
          or ""
      )
    if not cust_name:
      cust_name = str(
          _LATEST_OUTLINE_CACHE.get("_latest_customer_name_") or ""
      ).strip()
    if not cust_name:
      try:
        latest_raw = _LATEST_OUTLINE_CACHE.get("_latest_")
        if latest_raw:
          parsed_o = json.loads(latest_raw)
          inner_o = (
              parsed_o.get("data", parsed_o)
              if isinstance(parsed_o, dict)
              else {}
          )
          cust_name = str(
              (inner_o.get("context") or {}).get("customer_name")
              or inner_o.get("customer_name")
              or ""
          ).strip()
      except Exception:
        pass

    if state is not None and hasattr(state, "__setitem__"):
      try:
        if pres_id:
          state["presentation_id"] = pres_id
          state["deck_url"] = (
              f"https://docs.google.com/presentation/d/{pres_id}/edit"
          )
        if cust_name and not state.get("customer_name"):
          state["customer_name"] = cust_name
        cached_ind = _LATEST_OUTLINE_CACHE.get("_latest_industry_")
        if cached_ind and not state.get("industry"):
          state["industry"] = cached_ind
        cached_sp = _LATEST_OUTLINE_CACHE.get("_latest_sales_play_")
        if cached_sp and not state.get("salesPlay"):
          state["salesPlay"] = cached_sp
      except Exception:
        pass

  deck_url = (
      f"https://docs.google.com/presentation/d/{pres_id}/edit"
      if pres_id
      else ""
  )
  return pres_id, deck_url, cust_name


def enterprise_search_slides_form_skill(
    search_query: str = "",
    slide_job: str = "",
    presentation_url_or_id: str = "",
    tool_context: Any = None,
) -> str:
  """Presents the interactive A2UI Slide Search input card ('pitchgen-slide-search') in Gemini Enterprise so the user can enter a search query and slide category filter."""
  active_pres_id, _, cust_name = _resolve_active_deck_from_state_or_cache(
      presentation_url_or_id, tool_context
  )
  surf_id, search_msgs = _build_search_form_messages(
      tool_context, active_pres_id, cust_name, slide_job
  )
  _stash_a2ui_payload(tool_context, search_msgs)
  return (
      "The interactive **Search CloudHub & Customer Reference Slides** card"
      f" (surfaceId='{surf_id}') has been rendered below. Invite the"
      " user in 1-2 concise sentences to enter their search query and optional"
      " slide category filter in the card below, then click **Search"
      f" Library**.\n\n<a2ui-json>\n{json.dumps(search_msgs)}\n</a2ui-json>"
  )


def enterprise_search_slides_skill(
    search_query: str = "",
    slide_job: str = "",
    strict_search: bool = False,
    target_presentation_id: str = "",
    tool_context: Any = None,
) -> str:
  """Searches reusable slide repositories, CloudHub templates, and verified customer reference case studies, returning one interactive A2UI results card (thumbnail grid, preview, 1-click insert)."""
  active_pres_id, _, cust_name = _resolve_active_deck_from_state_or_cache(
      target_presentation_id or "", tool_context
  )
  state = getattr(tool_context, "state", None) if tool_context else None
  if state is not None and hasattr(state, "get"):
    try:
      # A stale launcher flag must never turn a real search into a form re-render.
      if state.get("last_target_card") in ("search_slide", "search"):
        state["last_target_card"] = ""
      if active_pres_id and not state.get("presentation_id"):
        state["presentation_id"] = active_pres_id
      if cust_name and not state.get("customer_name"):
        state["customer_name"] = cust_name
    except Exception:
      pass

  clean_q = _clean_str(search_query).strip()
  if not clean_q:
    clean_q = (
        f"{cust_name} Customer References"
        if cust_name
        else "Customer References"
    )

  raw_res = PitchGenSkills.enterprise_search_slides_skill(
      search_query=clean_q,
      slide_job=slide_job,
      strict_search=strict_search,
      tool_context=tool_context,
  )
  try:
    data = json.loads(raw_res)
    slides = data.get("slides", []) or []
    effective_q = data.get("effective_query") or clean_q
    resolved_cust = data.get("customer_name") or cust_name
    resolved_ind = data.get("industry") or ""

    try:
      enriched = slide_thumbnail_util.enrich_results_with_thumbnails(
          slides, tool_context=tool_context
      )
    except Exception as thumb_err:  # pylint: disable=broad-except
      logging.warning(
          "[enterprise_agent] Slide thumbnail enrichment notice: %s", thumb_err
      )
      enriched = list(slides)

    _, results_msgs = _build_search_results_messages(
        tool_context,
        clean_q,
        enriched,
        active_pres_id,
        slide_job,
        resolved_cust,
    )
    search_card = a2ui_util.create_slide_search_panel_card(
        search_query=clean_q,
        results=enriched,
        target_presentation_id=active_pres_id,
        slide_job=slide_job,
    )
    search_card["a2ui_v09_messages"] = results_msgs
    _stash_a2ui_payload(tool_context, search_card)

    top_titles = [
        f"*{s.get('title', 'Slide')}*"
        f" ({s.get('customer') or s.get('category') or s.get('slide_job', 'Asset')})"
        for s in slides[:4]
        if isinstance(s, dict)
    ]
    cot_search = (
        "**Customer Reference & Slide Library Retrieval**\n- **Query & Account"
        " Context**: Searched consolidated 2026 Customer Reference Library and"
        f" CloudHub for `{effective_q}`"
        + (
            f" aligned to **{resolved_cust}** ({resolved_ind})"
            if resolved_cust
            else ""
        )
        + f".\n- **Matched Assets ({len(slides)} found)**: Ranked top verified"
        " slides including "
        + (", ".join(top_titles) if top_titles else "reusable proof points")
        + (
            f" with 1-click insertion wired to active deck `{active_pres_id}`."
            if active_pres_id
            else "."
        )
    )
    compact_slides = [
        {
            "title": s.get("title", ""),
            "slide_id": s.get("slide_id", ""),
            "deck_id": s.get("deck_id") or s.get("presentation_id") or "",
            "presentation_id": (
                s.get("presentation_id") or s.get("deck_id") or ""
            ),
            "source_deck_title": s.get("source_deck_title", ""),
            "slide_job": s.get("slide_job", "Proof_Points"),
            "customer": s.get("customer", ""),
            "industry": s.get("industry", ""),
            "view_url": s.get("view_url", ""),
        }
        for s in slides[:8]
        if isinstance(s, dict)
    ]
    if (
        tool_context
        and hasattr(tool_context, "state")
        and tool_context.state is not None
    ):
      try:
        tool_context.state["last_search_results"] = compact_slides
        tool_context.state["latest_cot_summary"] = cot_search
      except Exception:
        pass
    _LATEST_OUTLINE_CACHE["_last_search_results_"] = json.dumps(compact_slides)
    _LATEST_OUTLINE_CACHE["_latest_cot_"] = cot_search
    _persist_workspace_cache_to_gcs()
    return raw_res
  except Exception as e:
    logging.warning("[enterprise_agent] Search A2UI card notice: %s", e)
    return raw_res


def enterprise_insert_slide_skill(
    source_presentation_id: str = "",
    template_slide_id: str = "",
    target_presentation_id: str = "",
    slide_title: str = "",
    slide_job: str = "Proof_Points",
    tool_context: Any = None,
) -> str:
  """Inserts a reusable library or customer reference slide into the active Google Slides presentation on Canvas."""
  resolved_target_id, _, cust_name = _resolve_active_deck_from_state_or_cache(
      target_presentation_id, tool_context
  )

  # If source_presentation_id or template_slide_id was omitted, resolve from last search results
  if not source_presentation_id or not template_slide_id:
    last_slides = []
    if (
        tool_context
        and hasattr(tool_context, "state")
        and tool_context.state is not None
    ):
      last_slides = tool_context.state.get("last_search_results") or []
    if not last_slides and _LATEST_OUTLINE_CACHE.get("_last_search_results_"):
      try:
        last_slides = json.loads(_LATEST_OUTLINE_CACHE["_last_search_results_"])
      except Exception:
        last_slides = []
    if last_slides and isinstance(last_slides, list):
      chosen = last_slides[0]
      if slide_title:
        for s in last_slides:
          if slide_title.lower() in str(s.get("title", "")).lower():
            chosen = s
            break
      source_presentation_id = source_presentation_id or str(
          chosen.get("deck_id") or chosen.get("presentation_id") or ""
      )
      template_slide_id = template_slide_id or str(chosen.get("slide_id") or "")
      slide_title = slide_title or str(chosen.get("title") or "")

  raw_res = PitchGenSkills.enterprise_insert_slide_skill(
      source_presentation_id=source_presentation_id,
      template_slide_id=template_slide_id,
      target_presentation_id=resolved_target_id,
      slide_title=slide_title,
      slide_job=slide_job,
      tool_context=tool_context,
  )
  try:
    data = json.loads(raw_res)
    deck_url = data.get("deck_url") or (
        f"https://docs.google.com/presentation/d/{resolved_target_id}/edit"
        if resolved_target_id
        else ""
    )
    if deck_url and resolved_target_id:
      canvas_proto = a2ui_util.build_canvas_artifact_textproto(
          deck_url=deck_url,
          title=f"[PitchGen] {cust_name or 'Customer'} Presentation",
          model_generated_id=f"pitchgen-deck-{resolved_target_id}",
      )
      if (
          tool_context
          and hasattr(tool_context, "state")
          and tool_context.state is not None
      ):
        tool_context.state["canvas_artifact"] = canvas_proto
        tool_context.state["presentation_id"] = resolved_target_id
        tool_context.state["deck_url"] = deck_url
        tool_context.state["deck_just_generated"] = True
    cot_insert = (
        "**Reusable Slide Insertion & Linked Asset Governance**\n- **Source"
        f" Asset**: Linked `{slide_title or template_slide_id}` from library"
        f" deck `{source_presentation_id}`.\n- **Target Presentation**:"
        f" Inserted into active presentation `{resolved_target_id}` and"
        " refreshed the live Google Slides Canvas view."
    )
    if (
        tool_context
        and hasattr(tool_context, "state")
        and tool_context.state is not None
    ):
      tool_context.state["latest_cot_summary"] = cot_insert
    _LATEST_OUTLINE_CACHE["_latest_cot_"] = cot_insert
  except Exception as e:
    logging.warning("[enterprise_agent] Insert slide state notice: %s", e)
  return raw_res


def _normalize_transform_list(val: Any, placeholder: str = "") -> str:
  """Normalizes an A2UI ChoicePicker list or string into a comma-separated string, removing blank placeholders."""
  if val is None:
    return ""
  skip = {
      "",
      "none",
      "null",
      "— (blank)",
      "-(blank)",
      "industry vertical",
      "target audience persona",
      "slide transformation mode",
  }
  if placeholder:
    skip.add(placeholder.lower().strip())
  if isinstance(val, (list, tuple)):
    cleaned = [
        str(x).strip()
        for x in val
        if str(x).strip() and str(x).strip().lower() not in skip
    ]
    return ", ".join(cleaned)
  s_val = str(val).strip()
  if s_val.lower() in skip:
    return ""
  return s_val


def enterprise_transform_slide_form_skill(
    presentation_url_or_id: str = "",
    custom_instructions: str = "",
    customer_name: str = "",
    target_slide_indices: str = "",
    transformation_mode: str = "",
    tool_context: Any = None,
) -> str:
  """Presents the interactive A2UI Transform Slide Layout & Content card ('pitchgen-transform-slide') in Gemini Enterprise to capture the target Google Slides deck, slide indices, transformation mode, and instructions."""
  resolved_pres_id, resolved_deck_url, resolved_cust = (
      _resolve_active_deck_from_state_or_cache(
          presentation_url_or_id, tool_context
      )
  )
  surf_id = _next_card_surface_id(tool_context, "pitchgen-transform-slide")
  transform_slide_msgs = a2ui_util.create_a2ui_transform_messages(
      presentation_url_or_id=resolved_deck_url
      or resolved_pres_id
      or presentation_url_or_id,
      customer_name=customer_name or resolved_cust,
      criteria=custom_instructions,
      indices=target_slide_indices,
      transformation_mode=transformation_mode,
      surface_id=surf_id,
  )
  _stash_a2ui_payload(tool_context, transform_slide_msgs)
  return (
      "The interactive **Transform Slide Layout & Content** card"
      f" (surfaceId='{surf_id}') has been rendered below. Invite"
      " the user in 1-2 concise sentences to enter their Google Slides Deck ID"
      " or URL, slide numbers, transformation mode, and instructions in the"
      " card below, then click **Augment & Transform"
      f" Slides**.\n\n<a2ui-json>\n{json.dumps(transform_slide_msgs)}\n</a2ui-json>"
  )


def enterprise_transform_text_form_skill(
    presentation_url_or_id: str = "",
    custom_instructions: str = "",
    customer_name: str = "",
    target_slide_indices: str = "",
    full_deck_scope: bool = True,
    industry: str = "",
    audience: str = "",
    transform_scope_mode: str = "text_only",
    tool_context: Any = None,
) -> str:
  """Presents the interactive A2UI Transform Slide / Deck card ('pitchgen-transform-text') in Gemini Enterprise to capture the target Google Slides deck, custom instructions, customer name, target slide scope, what to transform (text, in-slide images, or both), industry, and audience."""
  resolved_pres = presentation_url_or_id
  resolved_cust = customer_name
  if (
      tool_context
      and hasattr(tool_context, "state")
      and tool_context.state is not None
  ):
    try:
      if not resolved_pres:
        resolved_pres = (
            tool_context.state.get("deck_url")
            or tool_context.state.get("presentation_id")
            or tool_context.state.get("last_presentation_id")
            or ""
        )
      if not resolved_cust:
        resolved_cust = tool_context.state.get("customer_name") or ""
    except Exception:
      pass

  full_deck_list = (
      []
      if (
          target_slide_indices
          and str(target_slide_indices).strip()
          and not full_deck_scope
      )
      else (["full_deck"] if full_deck_scope else [])
  )
  surf_id = _next_card_surface_id(tool_context, "pitchgen-transform-text")
  transform_msgs = a2ui_util.create_a2ui_transform_text_messages(
      presentation_url_or_id=resolved_pres,
      custom_instructions=custom_instructions,
      customer_name=resolved_cust,
      full_deck_scope=full_deck_list,
      target_slide_indices=target_slide_indices,
      industry=_normalize_transform_list(industry, placeholder="industry"),
      audience=_normalize_transform_list(audience, placeholder="audience"),
      transform_scope_mode=(
          _normalize_transform_list(
              transform_scope_mode, placeholder="transform_scope_mode"
          )
          or "text_only"
      ),
      surface_id=surf_id,
  )
  _stash_a2ui_payload(tool_context, transform_msgs)
  return (
      "The interactive **Transform Slide / Deck** card"
      f" (surfaceId='{surf_id}') has been rendered below. Invite"
      " the user in 1-2 concise sentences to enter their Google Slides Deck ID"
      " or URL, choose what to transform (text, in-slide images, or both), and"
      " provide transformation instructions in the card below, then click"
      " **Transform Slide /"
      f" Deck**.\n\n<a2ui-json>\n{json.dumps(transform_msgs)}\n</a2ui-json>"
  )


def enterprise_transform_slide_text_skill(
    presentation_url_or_id: str = "",
    customization_criteria: str = "Improve clarity and professional tone",
    target_slide_indices: str = "",
    customer_name: str = "",
    industry: str = "",
    audience: str = "",
    full_deck_scope: bool = False,
    language: str = "",
    transform_scope_mode: str = "text_only",
    tool_context: Any = None,
) -> str:
  """Transforms and polishes editable text and/or in-slide images inside an existing Google Slides deck (or the active Canvas presentation), returning an interactive A2UI transformation card."""
  card_ctx = {}
  if (
      tool_context
      and hasattr(tool_context, "state")
      and tool_context.state is not None
  ):
    try:
      stashed_ctx = tool_context.state.get("last_transform_card_ctx")
      if isinstance(stashed_ctx, dict):
        card_ctx = dict(stashed_ctx)
      tool_context.state["last_transform_card_ctx"] = None
    except Exception:
      pass

  raw_pres_input = str(
      presentation_url_or_id
      or card_ctx.get("presentation_url_or_id")
      or card_ctx.get("presentation_id")
      or card_ctx.get("presentation_url")
      or ""
  ).strip()
  resolved_pres_id, resolved_deck_url, cust_name = (
      _resolve_active_deck_from_state_or_cache(raw_pres_input, tool_context)
  )
  clean_pres = resolved_pres_id or raw_pres_input

  if (
      not customization_criteria
      or customization_criteria == "Improve clarity and professional tone"
  ) and (
      card_ctx.get("custom_instructions")
      or card_ctx.get("transform_instructions")
      or card_ctx.get("criteria")
      or card_ctx.get("transformation_mode")
  ):
    customization_criteria = str(
        card_ctx.get("custom_instructions")
        or card_ctx.get("transform_instructions")
        or card_ctx.get("criteria")
        or card_ctx.get("transformation_mode")
    ).strip()

  clean_customer = str(
      customer_name
      or card_ctx.get("customer_name")
      or card_ctx.get("target_customer")
      or cust_name
      or ""
  ).strip()
  clean_industry = _normalize_transform_list(
      industry or card_ctx.get("industry"), placeholder="industry"
  )
  clean_audience = _normalize_transform_list(
      audience or card_ctx.get("audience") or card_ctx.get("target_audience"),
      placeholder="audience",
  )
  raw_scope_mode = _normalize_transform_list(
      (
          transform_scope_mode
          if transform_scope_mode and transform_scope_mode != "text_only"
          else (card_ctx.get("transform_scope_mode") or transform_scope_mode)
      ),
      placeholder="transform_scope_mode",
  ).lower()
  if raw_scope_mode in (
      "gifs_only",
      "gif_only",
      "gifs",
      "animated_gifs",
      "video_to_video",
  ):
    effective_scope_mode = "gifs_only"
  elif raw_scope_mode in (
      "images_only",
      "image_only",
      "visuals_only",
      "images",
  ):
    effective_scope_mode = "images_only"
  elif raw_scope_mode in ("both", "text_and_images", "all"):
    effective_scope_mode = "both"
  else:
    effective_scope_mode = "text_only"

  raw_slides = str(
      target_slide_indices
      or card_ctx.get("target_slide_indices")
      or card_ctx.get("slide_range")
      or ""
  ).strip()
  is_specific_slide_scope = bool(
      raw_slides
      and raw_slides.lower() not in ("all", "full_deck", "entire_deck", "*")
  )
  if is_specific_slide_scope:
    full_deck_scope = False
    effective_slides = raw_slides
  else:
    if not full_deck_scope and "full_deck_scope" in card_ctx:
      raw_fds = card_ctx.get("full_deck_scope")
      if isinstance(raw_fds, list):
        full_deck_scope = any(
            str(x).strip().lower() in ("full_deck", "all", "true")
            for x in raw_fds
        )
      elif isinstance(raw_fds, bool):
        full_deck_scope = raw_fds
    effective_slides = "" if full_deck_scope else raw_slides

  if not clean_pres:
    surf_id = _next_card_surface_id(tool_context, "pitchgen-transform-text")
    transform_msgs = a2ui_util.create_a2ui_transform_text_messages(
        presentation_url_or_id="",
        custom_instructions=customization_criteria,
        customer_name=clean_customer,
        full_deck_scope=(
            ["full_deck"] if full_deck_scope or not effective_slides else []
        ),
        target_slide_indices=effective_slides,
        industry=clean_industry,
        audience=clean_audience,
        transform_scope_mode=effective_scope_mode,
        surface_id=surf_id,
    )
    _stash_a2ui_payload(tool_context, transform_msgs)
    return (
        "Please provide a valid Google Slides Presentation URL or Deck ID in"
        " the **Transform Slide / Deck** card below so I can polish and"
        " customize your"
        f" slides.\n\n<a2ui-json>\n{json.dumps(transform_msgs)}\n</a2ui-json>"
    )

  effective_criteria = (
      customization_criteria or "Improve clarity and professional tone"
  )
  if (
      language
      and language.strip().lower() not in ("", "english")
      and language.strip().lower() not in effective_criteria.lower()
  ):
    effective_criteria = (
        f"{effective_criteria} (Target Language: {language.strip()})"
    )

  raw_res = ""
  if effective_scope_mode in ("text_only", "both"):
    try:
      raw_res = PitchGenSkills.enterprise_transform_slide_text_skill(
          presentation_url_or_id=clean_pres,
          customization_criteria=effective_criteria,
          target_slide_indices=effective_slides,
          customer_name=clean_customer,
          industry=clean_industry,
          audience=clean_audience,
          full_deck_scope=full_deck_scope,
          tool_context=tool_context,
      )
    except TypeError:
      raw_res = PitchGenSkills.enterprise_transform_slide_text_skill(
          presentation_url_or_id=clean_pres,
          customization_criteria=effective_criteria,
          target_slide_indices=effective_slides,
          tool_context=tool_context,
      )

  vis_data = {}
  if effective_scope_mode in ("images_only", "gifs_only", "both"):
    first_idx = 1
    if effective_slides:
      m_idx = re.search(r"\d+", effective_slides)
      if m_idx:
        first_idx = max(1, int(m_idx.group(0)))
    vis_prompt = effective_criteria
    if clean_customer and clean_customer.lower() not in vis_prompt.lower():
      vis_prompt = f"{vis_prompt} (Customer Context: {clean_customer})"
    try:
      vis_raw = PitchGenSkills.enterprise_generate_visuals_skill(
          prompt=vis_prompt,
          presentation_url_or_id=clean_pres,
          target_slide_index=first_idx,
          target_slide_indices=effective_slides or "1",
          mode="transform",
          in_place_only=True,
          gifs_only=(effective_scope_mode == "gifs_only"),
          include_gifs=(effective_scope_mode in ("gifs_only", "both")),
          customer_name=clean_customer,
          tool_context=tool_context,
      )
      if vis_raw and str(vis_raw).strip().startswith("{"):
        vis_data = json.loads(vis_raw)
    except TypeError:
      vis_raw = PitchGenSkills.enterprise_generate_visuals_skill(
          prompt=vis_prompt,
          presentation_url_or_id=clean_pres,
          target_slide_index=first_idx,
          target_slide_indices=effective_slides or "1",
          mode="transform",
          in_place_only=True,
          customer_name=clean_customer,
          tool_context=tool_context,
      )
      if vis_raw and str(vis_raw).strip().startswith("{"):
        vis_data = json.loads(vis_raw)
    except Exception as vis_err:
      logging.warning(
          "[enterprise_agent] In-slide image/GIF transformation notice: %s",
          vis_err,
      )

  try:
    data = (
        json.loads(raw_res)
        if (raw_res and str(raw_res).strip().startswith("{"))
        else {}
    )
    if effective_scope_mode in ("images_only", "gifs_only"):
      data = dict(vis_data) if vis_data else {"status": "success"}
      data["transform_scope_mode"] = effective_scope_mode
      data.setdefault(
          "slides_modified",
          1
          if (
              int(data.get("replaced_image_count") or 0) > 0
              or int(data.get("replaced_gif_count") or 0) > 0
          )
          else 0,
      )
      raw_res = json.dumps(data)
    elif effective_scope_mode == "both" and isinstance(data, dict):
      data["transform_scope_mode"] = "both"
      data["replaced_image_count"] = int(
          vis_data.get("replaced_image_count") or 0
      )
      data["replaced_gif_count"] = int(vis_data.get("replaced_gif_count") or 0)
      if vis_data.get("generated_image_url"):
        data["generated_image_url"] = vis_data["generated_image_url"]
      raw_res = json.dumps(data)

    final_pres_id = (
        data.get("presentation_id")
        or resolved_pres_id
        or a2ui_util.extract_presentation_id(clean_pres)
        or clean_pres
    )
    final_deck_url = data.get("deck_url") or resolved_deck_url
    slides_mod = int(
        data.get("slides_modified") or data.get("transformed_count") or 0
    )

    surf_id = _next_card_surface_id(tool_context, "pitchgen-transform-text")
    transform_card = a2ui_util.create_text_transform_card(
        presentation_id=final_pres_id,
        deck_url=final_deck_url or clean_pres,
        customer_name=clean_customer,
        criteria=customization_criteria,
        indices=effective_slides,
        language=language or "English",
        industry=clean_industry,
        audience=clean_audience,
        transform_scope_mode=effective_scope_mode,
    )
    transform_card["a2ui_v09_messages"] = (
        a2ui_util.create_a2ui_v09_transform_text_messages(
            presentation_url_or_id=final_pres_id,
            custom_instructions=customization_criteria,
            customer_name=clean_customer,
            target_slide_indices=(
                ""
                if str(effective_slides or "").strip().lower()
                in ("all", "full_deck", "entire_deck")
                else str(effective_slides or "").strip()
            ),
            industry=clean_industry,
            audience=clean_audience,
            transform_scope_mode=effective_scope_mode,
            surface_id=surf_id,
            slides_modified=slides_mod,
        )
    )
    _stash_a2ui_payload(tool_context, transform_card)

    if final_deck_url and final_pres_id:
      canvas_proto = a2ui_util.build_canvas_artifact_textproto(
          deck_url=final_deck_url,
          title=f"[PitchGen] {clean_customer or 'Customer'} Presentation",
          model_generated_id=f"pitchgen-deck-{final_pres_id}",
      )
      if (
          tool_context
          and hasattr(tool_context, "state")
          and tool_context.state is not None
      ):
        prev_pres_id = str(tool_context.state.get("presentation_id") or "")
        tool_context.state["canvas_artifact"] = canvas_proto
        tool_context.state["presentation_id"] = final_pres_id
        tool_context.state["deck_url"] = final_deck_url
        if prev_pres_id != final_pres_id:
          tool_context.state["deck_just_generated"] = True

    cot_transform = (
        "**Holistic Slide Transformation & Copy Governance**\n- **Target"
        f" Presentation & Scope**: Applied `{effective_criteria}` (mode:"
        f" `{effective_scope_mode}`) across"
        f" `{f'Slides {effective_slides}' if effective_slides else 'Full Deck'}`"
        f" in `{final_pres_id}`.\n- **Formatting & Proof-Point Integrity**:"
        " Preserved Google Slides typography (`weightedFontFamily`), enforced"
        " character-length budgets, and protected verified customer metrics."
    )
    if (
        tool_context
        and hasattr(tool_context, "state")
        and tool_context.state is not None
    ):
      tool_context.state["latest_cot_summary"] = cot_transform
    _LATEST_OUTLINE_CACHE["_latest_cot_"] = cot_transform
    return raw_res
  except Exception as e:
    logging.warning("[enterprise_agent] Transform A2UI card notice: %s", e)
    return raw_res


def enterprise_generate_slide_form_skill(
    presentation_url_or_id: str = "",
    slide_topic: str = "",
    slide_job: str = "",
    tool_context: Any = None,
) -> str:
  """Presents the interactive A2UI Generate Single Slide card ('pitchgen-generate-slide') in Gemini Enterprise to capture the slide topic, key message, slide job, and optional target Google Slides deck."""
  resolved_pres_id, resolved_deck_url, cust_name = (
      _resolve_active_deck_from_state_or_cache(
          presentation_url_or_id, tool_context
      )
  )
  surf_id = _next_card_surface_id(tool_context, "pitchgen-generate-slide")
  gen_slide_msgs = a2ui_util.create_a2ui_generate_slide_messages(
      presentation_url_or_id=resolved_deck_url
      or resolved_pres_id
      or presentation_url_or_id,
      slide_topic=slide_topic,
      slide_job=slide_job,
      customer_name=cust_name,
      surface_id=surf_id,
  )
  _stash_a2ui_payload(tool_context, gen_slide_msgs)
  return (
      "The interactive **Generate a Single Slide** card"
      f" (surfaceId='{surf_id}') has been rendered below. Invite"
      " the user in 1-2 concise sentences to enter their slide topic, key"
      " message, and optional target Google Slides deck in the card below, then"
      " click **Generate"
      f" Slide**.\n\n<a2ui-json>\n{json.dumps(gen_slide_msgs)}\n</a2ui-json>"
  )


def enterprise_nano_banana_form_skill(
    mode: str = "generate",
    presentation_url_or_id: str = "",
    prompt: str = "",
    visual_style: str = "Google Cloud Modern Architecture (Flat vector, precise topology)",
    target_slide_index: int = 1,
    tool_context: Any = None,
) -> str:
  """Presents the interactive A2UI NanoBanana Visual Studio card ('pitchgen-generate-nanobanana' or 'pitchgen-transform-nanobanana') in Gemini Enterprise to capture the visual/architecture prompt, visual style, and target deck."""
  resolved_pres_id, _, cust_name = _resolve_active_deck_from_state_or_cache(
      presentation_url_or_id, tool_context
  )
  clean_mode = (
      "transform" if str(mode or "").lower() == "transform" else "generate"
  )
  base_surf = (
      "pitchgen-transform-nanobanana"
      if clean_mode == "transform"
      else "pitchgen-generate-nanobanana"
  )
  surf_id = _next_card_surface_id(tool_context, base_surf)
  nb_msgs = a2ui_util.create_a2ui_nano_banana_messages(
      presentation_id=resolved_pres_id or presentation_url_or_id,
      prompt=prompt,
      visual_style=visual_style,
      target_slide_index=target_slide_index,
      generated_image_url="",
      inserted_slide_id="",
      mode=clean_mode,
      brand_context=cust_name,
      surface_id=surf_id,
  )
  _stash_a2ui_payload(tool_context, nb_msgs)
  card_label = "Nano Banana Studio"
  return (
      f"The interactive **{card_label}** card"
      f" (surfaceId='{surf_id}') has been rendered below. Invite the"
      " user in 1-2 concise sentences to configure their visual parameters in"
      " the card"
      f" below.\n\n<a2ui-json>\n{json.dumps(nb_msgs)}\n</a2ui-json>"
  )


def enterprise_translate_form_skill(
    presentation_url_or_id: str = "",
    target_language: str = "Spanish",
    target_slide_indices: str = "",
    tool_context: Any = None,
) -> str:
  """Presents the interactive A2UI Translate Presentation card ('pitchgen-translate') in Gemini Enterprise to capture the target Google Slides deck and target language."""
  resolved_pres_id, resolved_deck_url, cust_name = (
      _resolve_active_deck_from_state_or_cache(
          presentation_url_or_id, tool_context
      )
  )
  surf_id = _next_card_surface_id(tool_context, "pitchgen-translate")
  trans_msgs = a2ui_util.create_a2ui_translate_messages(
      presentation_url_or_id=resolved_deck_url
      or resolved_pres_id
      or presentation_url_or_id,
      target_language=target_language or "Spanish",
      target_slide_indices=target_slide_indices,
      customer_name=cust_name,
      surface_id=surf_id,
  )
  _stash_a2ui_payload(tool_context, trans_msgs)
  return (
      "The interactive **Translate Presentation** card"
      f" (surfaceId='{surf_id}') has been rendered below. Invite the"
      " user in 1-2 concise sentences to enter their Google Slides Deck ID or"
      " URL and select the target language in the card below, then click"
      " **Translate"
      f" Presentation**.\n\n<a2ui-json>\n{json.dumps(trans_msgs)}\n</a2ui-json>"
  )


def enterprise_generate_visuals_skill(
    prompt: str = "",
    presentation_url_or_id: str = "",
    visual_style: str = "Google Cloud Modern Architecture (Flat vector, precise topology)",
    target_slide_index: int = 1,
    mode: str = "generate",
    selected_model: str = "nano_banana_pro",
    customer_name: str = "",
    tool_context: Any = None,
) -> str:
  """Synthesizes bespoke 2K technical architecture diagrams and slide visuals OR transforms existing slide visuals in-place using Nano Banana (Gemini 3.1 Image), and renders an interactive A2UI visual card."""
  resolved_pres_id, resolved_deck_url, cust_name = (
      _resolve_active_deck_from_state_or_cache(
          presentation_url_or_id, tool_context
      )
  )
  state = getattr(tool_context, "state", None) if tool_context else None
  last_tc = ""
  if state is not None and hasattr(state, "get"):
    try:
      last_tc = str(state.get("last_target_card") or "")
      if last_tc in ("generate_nanobanana", "transform_nanobanana", "diagram"):
        state["last_target_card"] = ""
    except Exception:
      pass

  clean_prompt = _clean_str(prompt).strip()
  if (
      last_tc in ("generate_nanobanana", "transform_nanobanana", "diagram")
      or not clean_prompt
  ):
    form_mode = (
        "transform"
        if (last_tc == "transform_nanobanana" or str(mode).lower() == "transform")
        else "generate"
    )
    return enterprise_nano_banana_form_skill(
        mode=form_mode,
        presentation_url_or_id=resolved_pres_id or presentation_url_or_id,
        prompt="",
        visual_style=visual_style,
        target_slide_index=target_slide_index,
        tool_context=tool_context,
    )

  raw_res = PitchGenSkills.enterprise_generate_visuals_skill(
      prompt=clean_prompt,
      presentation_url_or_id=resolved_pres_id or presentation_url_or_id,
      visual_style=visual_style,
      target_slide_index=target_slide_index,
      mode=mode,
      selected_model=selected_model,
      customer_name=customer_name or cust_name,
      tool_context=tool_context,
  )
  try:
    data = json.loads(raw_res) if raw_res else {}
  except Exception:
    data = {}

  final_pres_id = data.get("presentation_id") or resolved_pres_id or ""
  final_deck_url = data.get("deck_url") or resolved_deck_url or ""
  signed_url = data.get("generated_image_url") or ""
  inserted_slide_id = data.get("inserted_slide_id") or ""
  effective_mode = str(data.get("mode") or mode or "generate")
  replaced_image_count = int(data.get("replaced_image_count") or 0)

  visual_card = a2ui_util.create_nano_banana_card(
      presentation_id=final_pres_id,
      target_slide_index=target_slide_index,
      visual_style=visual_style,
      prompt=clean_prompt,
      generated_image_url=signed_url,
      mode=effective_mode,
  )
  visual_card["a2ui_v09_messages"] = a2ui_util.create_a2ui_nano_banana_messages(
      presentation_id=final_pres_id,
      prompt=clean_prompt,
      visual_style=visual_style,
      target_slide_index=target_slide_index,
      generated_image_url=signed_url,
      inserted_slide_id=inserted_slide_id,
      mode=effective_mode,
      selected_model=selected_model,
  )
  _stash_a2ui_payload(tool_context, visual_card)

  if final_deck_url and final_pres_id:
    try:
      canvas_proto = a2ui_util.build_canvas_artifact_textproto(
          deck_url=final_deck_url,
          title=f"[PitchGen] {cust_name or 'Customer'} Presentation",
          model_generated_id=f"pitchgen-deck-{final_pres_id}",
      )
      if (
          tool_context
          and hasattr(tool_context, "state")
          and tool_context.state is not None
      ):
        prev_pres_id = str(tool_context.state.get("presentation_id") or "")
        tool_context.state["canvas_artifact"] = canvas_proto
        tool_context.state["presentation_id"] = final_pres_id
        tool_context.state["deck_url"] = final_deck_url
        if prev_pres_id != final_pres_id and (
            inserted_slide_id or replaced_image_count > 0
        ):
          tool_context.state["deck_just_generated"] = True
    except Exception:
      pass

  cot_visual = (
      "**Nano Banana Architecture & Visual Synthesis**\n- **Visual"
      " Architecture Design**: Synthesized high-resolution 16:9 visual for"
      f" `{clean_prompt}` using style `{visual_style}`.\n"
      + (
          "- **Presentation Integration**: Inserted visual onto slide"
          f" `{inserted_slide_id}` in active deck `{final_pres_id}`."
          if inserted_slide_id
          else (
              "- **Presentation Transformation**: Replaced"
              f" {replaced_image_count} visual element(s) on target slide in"
              f" `{final_pres_id}`."
              if replaced_image_count > 0
              else (
                  "- **Asset Delivery**: Uploaded high-resolution PNG and"
                  " generated signed preview URL."
              )
          )
      )
  )
  if (
      tool_context
      and hasattr(tool_context, "state")
      and tool_context.state is not None
  ):
    try:
      tool_context.state["latest_cot_summary"] = cot_visual
    except Exception:
      pass
  _LATEST_OUTLINE_CACHE["_latest_cot_"] = cot_visual

  summary_lines = [
      f"Synthesized Google Cloud architecture visual: **{clean_prompt}**"
      f" (Style: {visual_style})."
  ]
  if inserted_slide_id and final_deck_url:
    summary_lines.append(
        "- **Inserted into Active Presentation**: [Open Slide in Google"
        f" Slides]({final_deck_url}#slide=id.{inserted_slide_id})"
    )
  elif replaced_image_count > 0 and final_deck_url:
    summary_lines.append(
        "- **Transformed in Active Presentation**: Replaced"
        f" {replaced_image_count} visual element(s) in [Google"
        f" Slides]({final_deck_url})."
    )
  elif final_deck_url:
    summary_lines.append(
        "- **Active Presentation**: [Open Google Slides"
        f" Deck]({final_deck_url})"
    )
  if signed_url:
    summary_lines.append(f"- [View High-Resolution PNG Asset]({signed_url})")
  return "\n".join(summary_lines)


def enterprise_translate_deck_skill(
    presentation_url_or_id: str = "",
    target_language: str = "Spanish",
    translate_instructions: str = "",
    target_slide_indices: str = "",
    full_deck_scope: bool = False,
    tool_context: Any = None,
) -> str:
  """Translates an existing Google Slides presentation (or the active Canvas presentation) into the target language while preserving layout and typography."""
  resolved_pres_id, resolved_deck_url, cust_name = (
      _resolve_active_deck_from_state_or_cache(
          presentation_url_or_id, tool_context
      )
  )
  state = getattr(tool_context, "state", None) if tool_context else None
  card_ctx: dict[str, Any] = {}
  is_card_launch = False
  if state is not None and hasattr(state, "get"):
    try:
      card_ctx = state.get("last_translate_card_ctx") or {}
      is_card_launch = state.get("last_target_card") in (
          "translate",
          "translate_deck",
      )
      if is_card_launch:
        state["last_target_card"] = ""
      state["last_translate_card_ctx"] = None
    except Exception:
      pass

  clean_pres = str(
      card_ctx.get("presentation_url_or_id")
      or card_ctx.get("presentation_id")
      or card_ctx.get("presentation_url")
      or resolved_pres_id
      or _clean_str(presentation_url_or_id).strip()
      or ""
  ).strip()

  clean_instructions = str(
      card_ctx.get("translate_instructions")
      or card_ctx.get("custom_instructions")
      or translate_instructions
      or ""
  ).strip()

  card_lang = _normalize_transform_list(
      card_ctx.get("target_language") or card_ctx.get("language"),
      placeholder="Select Language",
  )
  inst_lang = _extract_language_from_text(clean_instructions)
  arg_lang = _normalize_transform_list(
      target_language,
      placeholder="Select Language",
  )
  if card_ctx and ("target_language" in card_ctx or "language" in card_ctx):
    clean_lang = card_lang or inst_lang
  else:
    clean_lang = card_lang or inst_lang or arg_lang or "Spanish"

  if "full_deck_scope" in card_ctx:
    raw_fds = card_ctx.get("full_deck_scope")
    if isinstance(raw_fds, list):
      full_deck_scope = any(
          str(x).strip().lower() in ("full_deck", "all", "true")
          for x in raw_fds
      )
    elif isinstance(raw_fds, bool):
      full_deck_scope = raw_fds
    elif isinstance(raw_fds, str):
      full_deck_scope = raw_fds.strip().lower() in ("full_deck", "all", "true")

  card_slides = str(
      card_ctx.get("target_slide_indices") or card_ctx.get("slide_range") or ""
  ).strip()
  raw_slides = str(card_slides or target_slide_indices or "").strip()
  if card_slides and card_slides.lower() not in (
      "all",
      "full_deck",
      "full deck",
      "none",
      "null",
  ):
    full_deck_scope = False
  effective_slides = "" if full_deck_scope else raw_slides

  if is_card_launch or not clean_pres or not clean_lang:
    surf_id = _next_card_surface_id(tool_context, "pitchgen-translate")
    trans_msgs = a2ui_util.create_a2ui_translate_messages(
        presentation_url_or_id=resolved_deck_url or clean_pres,
        translate_instructions=clean_instructions,
        target_language=clean_lang,
        full_deck_scope=["full_deck"]
        if full_deck_scope or not effective_slides
        else [],
        target_slide_indices=effective_slides,
        surface_id=surf_id,
    )
    _stash_a2ui_payload(tool_context, trans_msgs)
    return (
        "The interactive **Translate Presentation** card"
        f" (surfaceId='{surf_id}') has been rendered below. Invite the"
        " user in 1-2 concise sentences to enter their Google Slides Deck ID or"
        " URL and select the target language in the card below, then click"
        " **Translate"
        f" Presentation**.\n\n<a2ui-json>\n{json.dumps(trans_msgs)}\n</a2ui-json>"
    )

  try:
    raw_res = PitchGenSkills.enterprise_translate_deck_skill(
        presentation_url_or_id=clean_pres,
        target_language=clean_lang,
        translate_instructions=clean_instructions,
        target_slide_indices=effective_slides,
        full_deck_scope=full_deck_scope or not bool(effective_slides),
        tool_context=tool_context,
    )
  except TypeError:
    raw_res = PitchGenSkills.enterprise_translate_deck_skill(
        presentation_url_or_id=clean_pres,
        target_language=clean_lang,
        target_slide_indices=effective_slides,
        tool_context=tool_context,
    )
  try:
    data = json.loads(raw_res) if raw_res else {}
    final_pres_id = data.get("presentation_id") or resolved_pres_id or ""
    final_deck_url = data.get("deck_url") or resolved_deck_url or ""
    slides_mod = int(
        data.get("slides_modified") or data.get("transformed_count") or 0
    )
    trans_msgs = a2ui_util.create_a2ui_translate_messages(
        presentation_url_or_id=final_deck_url or final_pres_id or clean_pres,
        translate_instructions=clean_instructions,
        target_language=clean_lang or "Spanish",
        full_deck_scope=["full_deck"]
        if full_deck_scope or not effective_slides
        else [],
        target_slide_indices=effective_slides,
        customer_name=cust_name,
        slides_modified=slides_mod,
    )
    _stash_a2ui_payload(tool_context, trans_msgs)
    if final_deck_url and final_pres_id:
      canvas_proto = a2ui_util.build_canvas_artifact_textproto(
          deck_url=final_deck_url,
          title=(
              f"[PitchGen] {cust_name or 'Customer'} Presentation"
              f" ({clean_lang})"
          ),
          model_generated_id=f"pitchgen-deck-{final_pres_id}",
      )
      if (
          tool_context
          and hasattr(tool_context, "state")
          and tool_context.state is not None
      ):
        prev_pres_id = str(tool_context.state.get("presentation_id") or "")
        tool_context.state["canvas_artifact"] = canvas_proto
        tool_context.state["presentation_id"] = final_pres_id
        tool_context.state["deck_url"] = final_deck_url
        if prev_pres_id != final_pres_id:
          tool_context.state["deck_just_generated"] = True
    scope_desc = (
        f"on slide(s) `{effective_slides}`"
        if effective_slides
        else "across all slides"
    )
    cot_trans = (
        f"**Executive Presentation Localization ({clean_lang})**\n-"
        f" **Target Deck**: Translated slide text elements in `{final_pres_id}`"
        f" {scope_desc} into **{clean_lang}**.\n- **Layout & Brand"
        " Preservation**: Maintained original Google Slides typography,"
        " product nomenclature, and slide geometry."
    )
    if (
        tool_context
        and hasattr(tool_context, "state")
        and tool_context.state is not None
    ):
      tool_context.state["latest_cot_summary"] = cot_trans
    _LATEST_OUTLINE_CACHE["_latest_cot_"] = cot_trans
  except Exception:
    pass
  return raw_res


def enterprise_customer_insights_skill(
    customer_name: str = "",
    industry: str = "",
    sales_play: str = "",
    focus_topic: str = "",
    tool_context: Any = None,
) -> str:
  """Retrieves Voice of the Customer (VoC), EBC executive engagement themes, competitive SWOT intelligence (AWS/Azure/Snowflake/Databricks), and verified peer customer references."""
  _, _, cached_cust = _resolve_active_deck_from_state_or_cache("", tool_context)
  state = getattr(tool_context, "state", None) if tool_context else None
  effective_cust = (
      _clean_str(customer_name)
      or cached_cust
      or (
          str(state.get("customer_name") or "").strip()
          if state and hasattr(state, "get")
          else ""
      )
      or "Enterprise Customer"
  )
  effective_ind = _clean_str(industry) or (
      str(state.get("industry") or "").strip()
      if state and hasattr(state, "get")
      else ""
  )
  effective_play = _clean_str(sales_play) or (
      str(state.get("salesPlay") or "").strip()
      if state and hasattr(state, "get")
      else ""
  )
  try:
    from agents.workflows.customer_insights_workflow import CustomerInsightsWorkflow

    workflow = CustomerInsightsWorkflow(config)
    insights = workflow.execute({
        "customer_name": effective_cust,
        "industry": effective_ind,
        "salesPlay": effective_play,
        "context": focus_topic,
    })
    cot_insights = (
        "**Customer Intelligence, VoC & Competitive SWOT"
        f" ({effective_cust})**\n- **Multi-Source Synthesis**: Aggregated EBC"
        " executive themes, VoC product feedback, and competitive"
        f" differentiation for **{effective_cust}**"
        + (f" ({effective_ind})" if effective_ind else "")
        + f".\n- **Reference & Compete Alignment**: Mapped peer proof points"
        f" and counter-positioning against hyperscaler and data-platform"
        f" alternatives."
    )
    if state is not None and hasattr(state, "__setitem__"):
      state["latest_cot_summary"] = cot_insights
    _LATEST_OUTLINE_CACHE["_latest_cot_"] = cot_insights
    return json.dumps(insights, indent=2)
  except Exception as e:
    logging.warning("[enterprise_agent] CustomerInsightsWorkflow error: %s", e)
    return json.dumps({"status": "error", "error": str(e)})


_TOOL_STEP_LABELS = {
    "enterprise_launcher_card_skill": (
        "Loading PitchGen AI-Powered Presentation & Visual Suite launcher..."
    ),
    "enterprise_intake_form_skill": (
        "Preparing interactive presentation intake form and configuration"
        " options..."
    ),
    "enterprise_search_slides_form_skill": (
        "Loading interactive Search CloudHub & Customer Reference Slides"
        " card..."
    ),
    "enterprise_generate_slide_form_skill": (
        "Loading interactive Generate a Single Slide card..."
    ),
    "enterprise_transform_slide_form_skill": (
        "Loading interactive Transform Slide Layout & Content card..."
    ),
    "enterprise_transform_text_form_skill": (
        "Loading interactive Transform Slide Text card..."
    ),
    "enterprise_nano_banana_form_skill": (
        "Loading interactive NanoBanana Pro visual studio card..."
    ),
    "enterprise_translate_form_skill": (
        "Loading interactive Translate Presentation card..."
    ),
    "consult_skill": "Consulting PitchGen GTM domain skill guidelines...",
    "enterprise_create_proposal_outline": (
        "Researching organization context, resolving industry benchmarks, and"
        " structuring the presentation outline..."
    ),
    "enterprise_refine_proposal_outline": (
        "Refining presentation outline sections and narrative flow based on"
        " your instructions..."
    ),
    "enterprise_slide_generator_skill": (
        "Matching reusable slide templates, synthesizing narrative copy &"
        " visuals, and building the Google Slides presentation deck..."
    ),
    "enterprise_search_slides_skill": (
        "Searching the CloudHub slide library and verified customer reference"
        " case studies..."
    ),
    "enterprise_insert_slide_skill": (
        "Linking and inserting the selected library slide into your active"
        " Google Slides presentation..."
    ),
    "sidebar_generate": (
        "Synthesizing bespoke single slide layout and content..."
    ),
    "enterprise_transform_slide_text_skill": (
        "Analyzing slide structure and transforming presentation text with"
        " holistic narrative cohesion..."
    ),
    "transform_raw_text_skill": (
        "Polishing and refining slide text and executive copy..."
    ),
    "enterprise_generate_visuals_skill": (
        "Designing architecture diagram and generating presentation visual"
        " assets..."
    ),
    "enterprise_translate_deck_skill": (
        "Translating presentation slides while preserving layout and"
        " formatting..."
    ),
    "enterprise_customer_insights_skill": (
        "Synthesizing Voice of the Customer (VoC) insights, competitive SWOT,"
        " and peer customer references..."
    ),
    "phub_handoff_skill": (
        "Preparing escalation package for the Pitch & Proposal Hub (https://your-sales-portal.example.com/catalog)..."
    ),
    "rfp_accelerator_skill": (
        "Synthesizing GTM RFP and security questionnaire response..."
    ),
    "submit_authorization_code": (
        "Exchanging OAuth authorization code for Google Workspace"
        " credentials..."
    ),
}


def _sanitize_llm_request_contents_for_vertex(
    llm_request: Any,
    callback_context: Any = None,
) -> None:
  """Sanitizes replayed conversation history before calling Vertex AI generate_content.

  Fixes the fatal Vertex AI 400 INVALID_ARGUMENT
  (URL_ERROR-ERROR_AUTHENTICATION)
  caused when ADK replays `file_data` parts containing
  `https://docs.google.com/presentation/d/...`
  from a previous deck-generation turn into `llm_request.contents`. Also strips
  replayed `<a2a_datapart_json>` inline blobs from prior model turns so the LLM
  context stays clean and focused.
  """
  contents = getattr(llm_request, "contents", None)
  if not contents or not isinstance(contents, list):
    return

  state = getattr(callback_context, "state", None) if callback_context else None
  last_content = contents[-1] if contents else None

  for content_obj in contents:
    parts = getattr(content_obj, "parts", None)
    if not parts or not isinstance(parts, list):
      continue
    is_last_user_turn = (
        content_obj is last_content
        and getattr(content_obj, "role", "user") == "user"
    )
    sanitized_parts = []
    for part in parts:
      # 1. Convert non-GCS file_data (e.g. Google Slides / Drive HTTPS URLs) into text context
      f_data = getattr(part, "file_data", None)
      if f_data is not None:
        f_uri = str(getattr(f_data, "file_uri", "") or "").strip()
        f_mime = str(getattr(f_data, "mime_type", "") or "").strip()
        f_name = str(
            getattr(f_data, "display_name", "") or "Google Slides Presentation"
        ).strip()
        if (
            (f_uri and not f_uri.startswith("gs://"))
            or "google-apps" in f_mime
            or "docs.google.com" in f_uri
            or "drive.google.com" in f_uri
        ):
          extracted_id = a2ui_util.extract_presentation_id(f_uri)
          if extracted_id:
            if state is not None and hasattr(state, "__setitem__"):
              try:
                state["presentation_id"] = extracted_id
                state["deck_url"] = (
                    f"https://docs.google.com/presentation/d/{extracted_id}/edit"
                )
              except Exception:
                pass
            _LATEST_OUTLINE_CACHE["_latest_deck_id_"] = extracted_id
            _LATEST_OUTLINE_CACHE["_latest_deck_url_"] = (
                f"https://docs.google.com/presentation/d/{extracted_id}/edit"
            )
          safe_f_name = re.sub(r"[\[\]]", "", str(f_name or "")).strip()
          sanitized_parts.append(
              types.Part(
                  text=(
                      "[Active Google Slides Presentation on Canvas:"
                      f" {safe_f_name} (presentation_id={extracted_id or 'active'},"
                      f" url={f_uri})]"
                  )
              )
          )
          continue

      # 1b. Recover active presentation_id from prior conversation turns (e.g. showcased iframe link)
      p_text_for_id = getattr(part, "text", None)
      if p_text_for_id and "docs.google.com/presentation/d/" in p_text_for_id:
        # Prefer explicit active deck links over library reference links
        m_active_link = re.search(
            r"(?:Open Google Slides Presentation|Open Active"
            r" Presentation|Active Google Slides Presentation on"
            r" Canvas|Presentation Link|Active"
            r" Deck)[^\n]*?https://docs\.google\.com/presentation/d/([a-zA-Z0-9_-]{25,60})",
            p_text_for_id,
            re.IGNORECASE,
        )
        recovered_id = (
            m_active_link.group(1)
            if m_active_link
            else (
                a2ui_util.extract_presentation_id(p_text_for_id)
                if getattr(content_obj, "role", "") == "user"
                else None
            )
        )
        if recovered_id:
          if state is not None and hasattr(state, "__setitem__"):
            try:
              state["presentation_id"] = recovered_id
              state["deck_url"] = (
                  f"https://docs.google.com/presentation/d/{recovered_id}/edit"
              )
            except Exception:
              pass
          _LATEST_OUTLINE_CACHE["_latest_deck_id_"] = recovered_id
          _LATEST_OUTLINE_CACHE["_latest_deck_url_"] = (
              f"https://docs.google.com/presentation/d/{recovered_id}/edit"
          )

      # 2. Strip replayed A2A / A2UI inline_data blobs from prior turns (keep on last user turn for action extraction)
      if not is_last_user_turn:
        in_data = getattr(part, "inline_data", None)
        if in_data is not None:
          raw_b = getattr(in_data, "data", b"")
          if isinstance(raw_b, bytes):
            decoded = raw_b.decode("utf-8", errors="ignore")
            if (
                "<a2a_datapart_json>" in decoded
                or "<a2ui-json>" in decoded
                or "application/json+a2ui" in decoded
            ):
              continue

        p_text = getattr(part, "text", None)
        if p_text and (
            "<a2a_datapart_json>" in p_text or "<a2ui-json>" in p_text
        ):
          cleaned_p_text = re.sub(
              r"<a2a_datapart_json>.*?(?:</a2a_datapart_json>|$)",
              "",
              p_text,
              flags=re.DOTALL,
          )
          cleaned_p_text = re.sub(
              r"<a2ui-json>.*?(?:</a2ui-json>|$)",
              "",
              cleaned_p_text,
              flags=re.DOTALL,
          ).strip()
          if not cleaned_p_text:
            continue
          if getattr(part, "thought", False):
            continue
          sanitized_parts.append(types.Part(text=cleaned_p_text))
          continue

      sanitized_parts.append(part)

    if not sanitized_parts:
      sanitized_parts.append(types.Part(text="[Continued session]"))
    content_obj.parts = sanitized_parts


def _extract_a2ui_event_info(raw_text: str) -> tuple[str, str, dict[str, Any]]:
  """Extracts (event_name, target_card, context_dict) if raw_text contains an A2UI button action/event payload."""
  text = (raw_text or "").strip()
  if not text:
    return "", "", {}
  if text.startswith((
      "User clicked ",
      "User submitted ",
      "User triggered A2UI event ",
      "Invoke ",
  )):
    return "", "", {}
  if a2ui_util.A2A_DATA_PART_START_TAG in text:
    m = re.search(
        rf"{re.escape(a2ui_util.A2A_DATA_PART_START_TAG)}(.*?){re.escape(a2ui_util.A2A_DATA_PART_END_TAG)}",
        text,
        re.DOTALL,
    )
    if m:
      text = m.group(1).strip()

  obj = None
  if (text.startswith("{") and text.endswith("}")) or (
      text.startswith("[") and text.endswith("]")
  ):
    try:
      obj = json.loads(text)
    except Exception:
      obj = None
  elif "{" in text and "}" in text:
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if 0 <= start_idx < end_idx:
      try:
        obj = json.loads(text[start_idx : end_idx + 1])
      except Exception:
        obj = None

  if isinstance(obj, list) and obj and isinstance(obj[0], dict):
    obj = obj[0]

  if not isinstance(obj, dict):
    m_tc = re.search(
        r'["\']?(?:target_card|targetCard|workflow_mode|workflowMode)["\']?\s*[:=]\s*["\']([a-zA-Z0-9_]+)["\']',
        text,
    )
    if m_tc:
      tc = m_tc.group(1).strip()
      return "launch_feature_card", tc, {"target_card": tc, "workflow_mode": tc}
    m_approve = re.match(
        r"^(?:🚀\s*)?approve\s+(?:the\s+)?(?:proposal\s+)?outline\s+and\s+(?:synthesize|generate)\s+(?:the\s+)?(?:presentation\s+)?deck(?:\s+for\s+(.+?))?[.!?\s]*$",
        text.strip(),
        re.IGNORECASE,
    )
    if m_approve:
      cust = (m_approve.group(1) or "").strip().strip("'\"")
      return (
          "approve_outline_and_generate",
          "",
          {"customer_name": cust} if cust else {},
      )
    return "", "", {}

  if obj.get("kind") == "data":
    inner_data = obj.get("data")
    if (
        isinstance(inner_data, list)
        and inner_data
        and isinstance(inner_data[0], dict)
    ):
      obj = inner_data[0]
    elif isinstance(inner_data, dict):
      obj = inner_data

  ev = (
      obj.get("event")
      or (
          obj.get("action", {}) if isinstance(obj.get("action"), dict) else {}
      ).get("event")
      or obj.get("userAction")
      or obj.get("clientAction")
      or obj.get("action")
      or obj
  )
  if isinstance(ev, dict) and isinstance(ev.get("event"), dict):
    ev = ev["event"]
  if not isinstance(ev, dict):
    return "", "", {}

  ev_name = str(
      ev.get("name") or ev.get("actionName") or obj.get("name") or ""
  ).strip()
  ctx = ev.get("context") or obj.get("context") or ev.get("parameters") or {}
  if isinstance(ctx, list):
    parsed_ctx = {}
    for item in ctx:
      if isinstance(item, dict) and "key" in item:
        val = item.get("value")
        if isinstance(val, dict):
          parsed_ctx[item["key"]] = (
              val.get("literalString")
              or val.get("literalNumber")
              or val.get("literalBoolean")
              or val.get("value")
              or ""
          )
        else:
          parsed_ctx[item["key"]] = val
    ctx = parsed_ctx
  elif not isinstance(ctx, dict):
    ctx = {}

  target_card = str(
      ctx.get("target_card")
      or ctx.get("targetCard")
      or ctx.get("workflow_mode")
      or ctx.get("workflowMode")
      or ev.get("target_card")
      or ev.get("targetCard")
      or obj.get("target_card")
      or obj.get("targetCard")
      or obj.get("workflow_mode")
      or ""
  ).strip()
  return ev_name, target_card, ctx


def _extract_a2ui_action_from_content(
    content_obj: Any,
) -> dict[str, Any] | None:
  """Extracts an A2UI client action (v0.9 action or v0.8 userAction) from the latest user turn's parts."""
  if not content_obj or getattr(content_obj, "role", "user") != "user":
    return None
  parts = getattr(content_obj, "parts", None) or []
  if any(
      getattr(p, "function_response", None)
      or getattr(p, "function_call", None)
      for p in parts
  ):
    return None

  for p in reversed(parts):
    txt = getattr(p, "text", None) or ""
    if not txt and getattr(p, "inline_data", None):
      try:
        raw_bytes = getattr(p.inline_data, "data", b"")
        if isinstance(raw_bytes, (bytes, bytearray)):
          txt = raw_bytes.decode("utf-8", errors="ignore")
        else:
          txt = str(raw_bytes)
        if "{" not in txt and "<" not in txt and txt.strip():
          import base64

          decoded_b64 = base64.b64decode(txt.strip()).decode(
              "utf-8", errors="ignore"
          )
          if "{" in decoded_b64 or "<" in decoded_b64:
            txt = decoded_b64
      except Exception:
        txt = ""
    if not txt:
      continue

    ev_name, target_card, ev_ctx = _extract_a2ui_event_info(txt)
    if ev_name or target_card:
      surface_id = ""
      try:
        m_surf = re.search(
            r'["\']surfaceId["\']\s*:\s*["\']([^"\']+)["\']', txt
        )
        if m_surf:
          surface_id = m_surf.group(1).strip()
      except Exception:
        pass
      return {
          "name": ev_name or ("launch_feature_card" if target_card else ""),
          "target_card": target_card,
          "surfaceId": surface_id,
          "sourceComponentId": "",
          "context": ev_ctx,
      }
  return None


_PURE_GREETING_REGEX = re.compile(
    r"^(?:"
    r"hi|hello|hey|hiya|howdy|hola|greetings|"
    r"hi\s+there|hello\s+there|hey\s+there|"
    r"hi\s+pitchgen|hello\s+pitchgen|hey\s+pitchgen|"
    r"good\s+(?:morning|afternoon|evening|day)|"
    r"welcome|start|get\s+started|start\s+pitchgen|"
    r"menu|launcher|show\s+launcher|open\s+launcher|"
    r"help|help\s+me|what\s+can\s+you\s+do\??|who\s+are\s+you\??|"
    r"pitchgen"
    r")[!.,?\s]*$",
    re.IGNORECASE,
)


def _is_pure_greeting_turn(content_obj: Any) -> bool:
  """Returns True if the user turn is a greeting, empty prompt, or launcher request without customer/task context."""
  if not content_obj or getattr(content_obj, "role", "user") != "user":
    return False
  parts = getattr(content_obj, "parts", None) or []
  if not parts:
    return True
  for p in parts:
    if getattr(p, "function_response", None) or getattr(p, "function_call", None):
      return False
    if getattr(p, "file_data", None):
      return False
    inline = getattr(p, "inline_data", None)
    if inline:
      mime = str(getattr(inline, "mime_type", "")).lower()
      if any(m in mime for m in ("image", "pdf", "audio", "video")):
        return False

  texts = [getattr(p, "text", "") or "" for p in parts]
  full_text = " ".join(t.strip() for t in texts if t.strip()).strip()
  if not full_text:
    return True
  return bool(_PURE_GREETING_REGEX.match(full_text))


def enterprise_before_model_callback(
    callback_context: Any,
    llm_request: Any,
) -> Any:
  """Intercepts Slides Add-On payloads, sanitizes replayed file_data URLs, and handles Gemini Enterprise A2UI client actions before the LLM call."""
  # 1. Delegate raw JSON payloads from the Google Slides Add-On
  addon_resp = route_payload_before_model(callback_context, llm_request)
  if addon_resp is not None:
    return addon_resp

  if not llm_request or not getattr(llm_request, "contents", None):
    return None

  # 2. Sanitize replayed Google Slides HTTPS file_data parts and old A2A blobs
  # so Vertex AI never fails with 400 INVALID_ARGUMENT (URL_ERROR-ERROR_AUTHENTICATION)
  _sanitize_llm_request_contents_for_vertex(llm_request, callback_context)

  last_content = llm_request.contents[-1]
  state = getattr(callback_context, "state", None)

  # Fast-Path Post-Tool Delivery for enterprise_slide_generator_skill:
  # When enterprise_slide_generator_skill has just synthesized a deck, deliver the
  # formatted summary, executive Chain-of-Thought, Canvas file_data, and outline
  # surface cleanup directly without making a redundant post-tool LLM call.
  last_parts = getattr(last_content, "parts", None) or []
  has_slide_gen_fn_resp = any(
      getattr(getattr(p, "function_response", None), "name", "")
      == "enterprise_slide_generator_skill"
      for p in last_parts
  )
  if has_slide_gen_fn_resp:
    cached_deck_raw = _LATEST_OUTLINE_CACHE.pop("_just_generated_deck_", None)
    cached_deck = None
    if cached_deck_raw:
      try:
        cached_deck = json.loads(cached_deck_raw)
      except Exception:
        cached_deck = None
    if cached_deck and cached_deck.get("deck_url"):
      deck_url = cached_deck["deck_url"]
      pres_id = cached_deck.get("pres_id") or "deck"
      deck_title = (
          cached_deck.get("deck_title")
          or f"[PitchGen] {cached_deck.get('customer_name') or 'Customer'} Presentation"
      ).replace("'", "")
      cot_deck = cached_deck.get("cot_deck") or (
          _LATEST_OUTLINE_CACHE.pop("_latest_cot_", "") or ""
      )
      formatted_summary = cached_deck.get("formatted_summary") or (
          state.get("last_generated_deck_summary")
          if (state is not None and hasattr(state, "get"))
          else ""
      )
      if state is not None:
        try:
          state["deck_just_generated"] = False
          state["latest_cot_summary"] = ""
          state["a2ui_payloads_to_inject"] = []
          state["canvas_artifact"] = a2ui_util.build_canvas_artifact_textproto(
              deck_url=deck_url,
              title=deck_title,
              model_generated_id=f"pitchgen-deck-{pres_id}",
          )
        except Exception:
          pass
      _PENDING_A2UI_PAYLOADS.clear()
      resp_parts = []
      if cot_deck:
        resp_parts.append(types.Part(text=cot_deck, thought=True))
      if formatted_summary:
        resp_parts.append(types.Part(text=formatted_summary))
      resp_parts.append(
          types.Part(
              file_data=types.FileData(
                  file_uri=deck_url,
                  mime_type="application/vnd.google-apps.presentation",
                  display_name=deck_title,
              )
          )
      )
      active_ver = cached_deck.get("active_ver") or "v0.9"
      for old_sid in cached_deck.get("prev_outline_ids") or []:
        for del_msg in a2ui_util.create_a2ui_delete_surface_message(
            surface_id=old_sid,
            version="v0.9" if active_ver == "v0.9" else "v0.8",
        ):
          resp_parts.append(
              a2ui_util.create_a2a_part_from_a2ui_payload(del_msg)
          )
      logging.info(
          "[enterprise_before_model_callback] Post-tool fast-path delivering"
          " generated deck '%s' (%s) without redundant LLM call.",
          deck_title,
          pres_id,
      )
      return LlmResponse(
          content=types.Content(role="model", parts=resp_parts),
          custom_metadata={"a2a:response": True},
      )

  # Convert incoming user inline_data A2UI payloads to text parts on the last turn
  if getattr(last_content, "role", "user") == "user" and getattr(
      last_content, "parts", None
  ):
    converted_parts = []
    for p in last_content.parts:
      inline = getattr(p, "inline_data", None)
      if inline and getattr(inline, "data", None):
        try:
          raw_bytes = inline.data
          decoded = (
              raw_bytes.decode("utf-8", errors="ignore")
              if isinstance(raw_bytes, (bytes, bytearray))
              else str(raw_bytes)
          )
          if "{" not in decoded and "<" not in decoded and decoded.strip():
            import base64

            decoded_b64 = base64.b64decode(decoded.strip()).decode(
                "utf-8", errors="ignore"
            )
            if "{" in decoded_b64 or "<" in decoded_b64:
              decoded = decoded_b64
          if (
              "a2ui" in str(getattr(inline, "mime_type", "")).lower()
              or a2ui_util.A2A_DATA_PART_START_TAG in decoded
              or decoded.strip().startswith("{")
              or decoded.strip().startswith("[")
          ):
            p = types.Part(text=decoded.strip())
        except Exception:
          pass
      converted_parts.append(p)
    last_content.parts = converted_parts

  a2ui_action = _extract_a2ui_action_from_content(last_content)
  if not a2ui_action:
    # Unwrap any raw A2A data part tags inside text parts
    if getattr(last_content, "role", "user") == "user":
      for p in getattr(last_content, "parts", None) or []:
        t_val = getattr(p, "text", None) or ""
        if t_val and a2ui_util.A2A_DATA_PART_START_TAG in t_val:
          unwrapped = re.sub(
              rf"{re.escape(a2ui_util.A2A_DATA_PART_START_TAG)}(.*?){re.escape(a2ui_util.A2A_DATA_PART_END_TAG)}",
              r"\1",
              t_val,
              flags=re.DOTALL,
          ).strip()
          p.text = unwrapped

    # Fast-Path: Detect pure greeting turns and render Launcher Hub instantly (<20ms) without calling the LLM
    has_active_deck_or_outline = bool(
        state is not None
        and hasattr(state, "get")
        and (
            state.get("presentation_id")
            or state.get("deck_url")
            or state.get("proposal_outline")
            or state.get("deck_generated")
            or state.get("outline_generated")
        )
    )
    is_pure_greeting = _is_pure_greeting_turn(last_content)
    is_explicit_launcher_cmd = False
    if getattr(last_content, "role", "user") == "user":
      raw_texts = [
          getattr(p, "text", "") or ""
          for p in (getattr(last_content, "parts", None) or [])
      ]
      combined_t = " ".join(t.strip().lower() for t in raw_texts if t.strip())
      if combined_t in ("menu", "launcher", "show launcher", "open launcher"):
        is_explicit_launcher_cmd = True

    if (
        not has_active_deck_or_outline and is_pure_greeting
    ) or is_explicit_launcher_cmd:
      if state is not None:
        try:
          state["last_target_card"] = ""
          state["is_greeting_turn"] = False
        except Exception:
          pass
      active_ver = a2ui_util.detect_client_a2ui_version(
          tool_context=callback_context, default_version="v0.9"
      )
      surf_id = _next_card_surface_id(callback_context, "pitchgen-launcher")
      launcher_msgs = a2ui_util.create_a2ui_launcher_messages(
          surface_id=surf_id, version=active_ver
      )
      a2ui_parts = [
          a2ui_util.create_a2a_part_from_a2ui_payload(m) for m in launcher_msgs
      ]
      anchor_text = (
          "Welcome to **PitchGen**! Choose a workflow below or describe your"
          " customer presentation goal in chat to get started."
      )
      logging.info(
          "[enterprise_before_model_callback] Fast-path launcher triggered"
          " (surfaceId='%s'); returning Launcher Hub via LlmResponse without"
          " calling LLM.",
          surf_id,
      )
      return LlmResponse(
          content=types.Content(
              role="model",
              parts=[types.Part(text=anchor_text)] + a2ui_parts,
          ),
          custom_metadata={"a2a:response": True},
      )

    return None

  action_name = a2ui_action["name"]
  target_card = a2ui_action.get("target_card") or ""
  surface_id = a2ui_action.get("surfaceId") or ""
  ctx = a2ui_action.get("context") or {}

  if surface_id:
    _record_outline_surface_id(callback_context, surface_id)

  if state is not None:
    try:
      state["last_target_card"] = target_card or ""
      state["is_greeting_turn"] = False
    except Exception:
      pass

  # CASE 0: User clicked one of the 8 Feature Cards on the PitchGen Introduction & Feature Launcher Card
  if (
      action_name in ("launch_feature", "launch_feature_card")
      or target_card
      or action_name == "intake"
  ):
    active_ver = a2ui_util.detect_client_a2ui_version(
        tool_context=callback_context, default_version="v0.9"
    )
    active_pres_id, resolved_deck_url, cust_name = (
        _resolve_active_deck_from_state_or_cache("", callback_context)
    )
    p_id = resolved_deck_url or active_pres_id

    # 1. GTM Intake Form
    if target_card in ("generate_pitch", "intake") or action_name == "intake":
      surf_id = _next_card_surface_id(callback_context, "pitchgen-intake")
      intake_msgs = a2ui_util.create_a2ui_intake_messages(
          customer_name=cust_name,
          surface_id=surf_id,
          version=active_ver,
      )
      a2ui_parts = [
          a2ui_util.create_a2a_part_from_a2ui_payload(m) for m in intake_msgs
      ]
      anchor_text = (
          "Configure your account narrative and pitch deck parameters in the"
          " **GTM Intake Form** below."
      )
      logging.info(
          "[enterprise_before_model_callback] Fast-path launcher click for"
          " intake (surfaceId='%s'); returning GTM Intake form without LLM.",
          surf_id,
      )
      return LlmResponse(
          content=types.Content(
              role="model",
              parts=[types.Part(text=anchor_text)] + a2ui_parts,
          ),
          custom_metadata={"a2a:response": True},
      )

    # 2. Slide Search
    if target_card in ("search_slide", "search"):
      surf_id, search_msgs = _build_search_form_messages(
          callback_context, active_pres_id, cust_name, ""
      )
      try:
        # after_model_callback never runs for a before_model fast path, so
        # clear the launcher flag here to avoid re-rendering the form later.
        callback_context.state["last_target_card"] = ""
      except Exception:  # pylint: disable=broad-except
        pass
      a2ui_parts = [
          a2ui_util.create_a2a_part_from_a2ui_payload(m) for m in search_msgs
      ]
      anchor_text = (
          "Search CloudHub templates and the 2026 Customer Reference Library"
          " in the **Slide Search** card below."
      )
      logging.info(
          "[enterprise_before_model_callback] Fast-path launcher click for"
          " slide search (surfaceId='%s'); returning search card without LLM.",
          surf_id,
      )
      return LlmResponse(
          content=types.Content(
              role="model",
              parts=[types.Part(text=anchor_text)] + a2ui_parts,
          ),
          custom_metadata={"a2a:response": True},
      )

    # 3. Generate Single Slide
    if target_card == "generate_slide":
      surf_id = _next_card_surface_id(
          callback_context, "pitchgen-generate-slide"
      )
      gen_slide_msgs = a2ui_util.create_a2ui_generate_slide_messages(
          presentation_url_or_id=p_id,
          slide_topic="",
          slide_job="",
          customer_name=cust_name,
          surface_id=surf_id,
      )
      a2ui_parts = [
          a2ui_util.create_a2a_part_from_a2ui_payload(m)
          for m in gen_slide_msgs
      ]
      anchor_text = (
          "Configure your slide topic, narrative objective, and optional target"
          " deck in the **Generate a Single Slide** card below."
      )
      logging.info(
          "[enterprise_before_model_callback] Fast-path launcher click for"
          " generate_slide (surfaceId='%s'); returning card without LLM.",
          surf_id,
      )
      return LlmResponse(
          content=types.Content(
              role="model",
              parts=[types.Part(text=anchor_text)] + a2ui_parts,
          ),
          custom_metadata={"a2a:response": True},
      )

    # 4. Transform Slide Layout & Content
    if target_card == "transform_slide":
      surf_id = _next_card_surface_id(
          callback_context, "pitchgen-transform-slide"
      )
      trans_slide_msgs = a2ui_util.create_a2ui_transform_messages(
          presentation_url_or_id=p_id,
          customer_name=cust_name,
          criteria="",
          indices="",
          transformation_mode="",
          surface_id=surf_id,
      )
      a2ui_parts = [
          a2ui_util.create_a2a_part_from_a2ui_payload(m)
          for m in trans_slide_msgs
      ]
      anchor_text = (
          "Configure your presentation link, slide indices, and transformation"
          " mode in the **Transform Slide Layout & Content** card below."
      )
      logging.info(
          "[enterprise_before_model_callback] Fast-path launcher click for"
          " transform_slide (surfaceId='%s'); returning card without LLM.",
          surf_id,
      )
      return LlmResponse(
          content=types.Content(
              role="model",
              parts=[types.Part(text=anchor_text)] + a2ui_parts,
          ),
          custom_metadata={"a2a:response": True},
      )

    # 5. Transform Slide Text
    if target_card in ("transform_text", "transform"):
      surf_id = _next_card_surface_id(
          callback_context, "pitchgen-transform-text"
      )
      trans_text_msgs = a2ui_util.create_a2ui_transform_text_messages(
          presentation_url_or_id=p_id,
          custom_instructions="",
          customer_name=cust_name,
          full_deck_scope=["full_deck"],
          target_slide_indices="",
          industry="",
          audience="",
          surface_id=surf_id,
      )
      a2ui_parts = [
          a2ui_util.create_a2a_part_from_a2ui_payload(m)
          for m in trans_text_msgs
      ]
      anchor_text = (
          "Configure your presentation link, transformation instructions, and"
          " target audience in the **Transform Slide Text** card below."
      )
      logging.info(
          "[enterprise_before_model_callback] Fast-path launcher click for"
          " transform_text (surfaceId='%s'); returning card without LLM.",
          surf_id,
      )
      return LlmResponse(
          content=types.Content(
              role="model",
              parts=[types.Part(text=anchor_text)] + a2ui_parts,
          ),
          custom_metadata={"a2a:response": True},
      )

    # 6. Translate Presentation
    if target_card == "translate":
      surf_id = _next_card_surface_id(callback_context, "pitchgen-translate")
      trans_msgs = a2ui_util.create_a2ui_translate_messages(
          presentation_url_or_id=p_id,
          target_language="Spanish",
          target_slide_indices="",
          customer_name=cust_name,
          surface_id=surf_id,
      )
      a2ui_parts = [
          a2ui_util.create_a2a_part_from_a2ui_payload(m) for m in trans_msgs
      ]
      anchor_text = (
          "Provide your Google Slides presentation link and target language in"
          " the **Translate Presentation** card below."
      )
      logging.info(
          "[enterprise_before_model_callback] Fast-path launcher click for"
          " translate (surfaceId='%s'); returning card without LLM.",
          surf_id,
      )
      return LlmResponse(
          content=types.Content(
              role="model",
              parts=[types.Part(text=anchor_text)] + a2ui_parts,
          ),
          custom_metadata={"a2a:response": True},
      )

    # 7. Generate Visuals with NanoBanana Pro
    if target_card in ("generate_nanobanana", "diagram"):
      surf_id = _next_card_surface_id(
          callback_context, "pitchgen-generate-nanobanana"
      )
      nb_msgs = a2ui_util.create_a2ui_nano_banana_messages(
          presentation_id=active_pres_id,
          prompt="",
          visual_style="Google Cloud Modern Architecture (Flat vector, precise topology)",
          target_slide_index=1,
          generated_image_url="",
          inserted_slide_id="",
          mode="generate",
          brand_context=cust_name,
          surface_id=surf_id,
      )
      a2ui_parts = [
          a2ui_util.create_a2a_part_from_a2ui_payload(m) for m in nb_msgs
      ]
      anchor_text = (
          "Configure your studio mode, model engine, and visual prompt in the"
          " **Nano Banana Studio** card below."
      )
      logging.info(
          "[enterprise_before_model_callback] Fast-path launcher click for"
          " generate_nanobanana (surfaceId='%s'); returning card without LLM.",
          surf_id,
      )
      return LlmResponse(
          content=types.Content(
              role="model",
              parts=[types.Part(text=anchor_text)] + a2ui_parts,
          ),
          custom_metadata={"a2a:response": True},
      )

    # 8. Nano Banana Studio (Restyle Existing Slide)
    if target_card == "transform_nanobanana":
      surf_id = _next_card_surface_id(
          callback_context, "pitchgen-transform-nanobanana"
      )
      nb_msgs = a2ui_util.create_a2ui_nano_banana_messages(
          presentation_id=active_pres_id,
          prompt="",
          visual_style="Google Cloud Modern Architecture (Flat vector, precise topology)",
          target_slide_index=1,
          generated_image_url="",
          inserted_slide_id="",
          mode="transform",
          brand_context=cust_name,
          surface_id=surf_id,
      )
      a2ui_parts = [
          a2ui_util.create_a2a_part_from_a2ui_payload(m) for m in nb_msgs
      ]
      anchor_text = (
          "Specify your target presentation slide and restyling instructions"
          " in the **Nano Banana Studio** card below."
      )
      logging.info(
          "[enterprise_before_model_callback] Fast-path launcher click for"
          " transform_nanobanana (surfaceId='%s'); returning card without LLM.",
          surf_id,
      )
      return LlmResponse(
          content=types.Content(
              role="model",
              parts=[types.Part(text=anchor_text)] + a2ui_parts,
          ),
          custom_metadata={"a2a:response": True},
      )

    card_routing_prompts = {
        "generate_pitch": (
            "User clicked 'Launch Deck Generation'"
            " (target_card='generate_pitch') on the PitchGen Introduction"
            " Card. Invoke enterprise_intake_form_skill immediately to display"
            " the GTM Intake Form ('pitchgen-intake')."
        ),
        "intake": (
            "User clicked 'Configure Deck Intake' (target_card='intake') on"
            " the PitchGen Welcome Card. Invoke enterprise_intake_form_skill"
            " immediately to display the GTM Intake Form ('pitchgen-intake')."
        ),
        "search_slide": (
            "User clicked 'Open Slide Search' (target_card='search_slide') on"
            " the PitchGen Introduction Card. Invoke"
            " enterprise_search_slides_form_skill immediately to display the"
            " Search CloudHub & Customer Reference Slides input card"
            " ('pitchgen-slide-search'). Do NOT run a search with default"
            " parameters first."
        ),
        "search": (
            "User clicked 'Search CloudHub Slides' (target_card='search') on"
            " the PitchGen Welcome Card. Invoke"
            " enterprise_search_slides_form_skill immediately to display the"
            " Search CloudHub & Customer Reference Slides input card"
            " ('pitchgen-slide-search'). Do NOT run a search with default"
            " parameters first."
        ),
        "generate_slide": (
            "User clicked 'Launch Slide Creator'"
            " (target_card='generate_slide') on the PitchGen Introduction"
            " Card. Invoke enterprise_generate_slide_form_skill immediately to"
            " display the Generate a Single Slide A2UI card"
            " ('pitchgen-generate-slide')."
        ),
        "transform_slide": (
            "User clicked 'Open Slide Transformer'"
            " (target_card='transform_slide') on the PitchGen Introduction"
            " Card. Invoke enterprise_transform_slide_form_skill immediately to"
            " display the Transform Slide Layout & Content A2UI card"
            " ('pitchgen-transform-slide')."
        ),
        "transform_text": (
            "User clicked 'Open Text Transformer'"
            " (target_card='transform_text') on the PitchGen Introduction"
            " Card. Invoke enterprise_transform_text_form_skill immediately to"
            " display the Transform Slide Text A2UI card"
            " ('pitchgen-transform-text')."
        ),
        "transform": (
            "User clicked 'Transform Slide Text' (target_card='transform') on"
            " the PitchGen Welcome Card. Invoke"
            " enterprise_transform_text_form_skill immediately to display the"
            " Transform Slide Text A2UI card ('pitchgen-transform-text')."
        ),
        "translate": (
            "User clicked 'Open Deck Translator' (target_card='translate') on"
            " the PitchGen Introduction Card. Invoke"
            " enterprise_translate_form_skill immediately to display the"
            " Translate Presentation A2UI card ('pitchgen-translate')."
        ),
        "generate_nanobanana": (
            "User clicked 'Open NanoBanana Generator'"
            " (target_card='generate_nanobanana') on the PitchGen Introduction"
            " Card. Invoke enterprise_nano_banana_form_skill with"
            " mode='generate' immediately to display the Generate Architecture"
            " & Visuals with NanoBanana Pro A2UI card"
            " ('pitchgen-generate-nanobanana')."
        ),
        "transform_nanobanana": (
            "User clicked 'Open NanoBanana Transformer'"
            " (target_card='transform_nanobanana') on the PitchGen"
            " Introduction Card. Invoke enterprise_nano_banana_form_skill with"
            " mode='transform' immediately to display the Transform Slide"
            " Visuals with NanoBanana Pro A2UI card"
            " ('pitchgen-transform-nanobanana')."
        ),
        "diagram": (
            "User clicked 'Synthesize Visuals' (target_card='diagram') on the"
            " PitchGen Welcome Card. Invoke enterprise_nano_banana_form_skill"
            " with mode='generate' immediately to display the Generate"
            " Architecture & Visuals with NanoBanana Pro A2UI card"
            " ('pitchgen-generate-nanobanana')."
        ),
    }
    mapped_prompt = card_routing_prompts.get(
        target_card,
        f"User triggered A2UI event '{action_name}' with"
        f" target_card='{target_card}' and context={json.dumps(ctx)}.",
    )
    last_content.parts = [types.Part(text=mapped_prompt)]
    return None

  # Extract any inline section edits (sec_1_title, sec_1_subtopics, etc.)
  section_edits = {
      k: v
      for k, v in ctx.items()
      if re.match(r"^sec_\d+_(?:title|subtopics)$", str(k))
  }
  cust_name = str(
      ctx.get("customer_name") or ctx.get("target_customer") or ""
  ).strip()
  deck_strategy = str(ctx.get("deck_strategy") or "").strip()
  refinement_instr = str(
      ctx.get("refinement_instructions")
      or ctx.get("refine_prompt")
      or ctx.get("prompt")
      or ""
  ).strip()

  # CASE A0: Per-section Edit / Delete / Add on the A2UI Outline Review card.
  # Applied deterministically to state["proposal_outline"] (no LLM call) and
  # the outline card is re-rendered with a fresh surfaceId.
  if action_name in _OUTLINE_MUTATION_EVENTS + _OUTLINE_VIEW_EVENTS:
    try:
      section_resp = _handle_outline_section_action(
          callback_context, action_name, ctx
      )
    except Exception as section_err:
      logging.warning(
          "[enterprise_before_model_callback] Outline section action notice:"
          " %s",
          section_err,
      )
      section_resp = None
    if section_resp is not None:
      return section_resp
    if action_name in _OUTLINE_VIEW_EVENTS:
      # Nothing to edit without a cached outline; answer without the LLM.
      return LlmResponse(
          content=types.Content(
              role="model",
              parts=[
                  types.Part(
                      text=(
                          "I couldn't find the current outline in this"
                          " session. Ask me to create the proposal outline"
                          " again, then edit it from the card."
                      )
                  )
              ],
          ),
      )
    sec_no = ctx.get("section_number") or ""
    sec_title = str(
        ctx.get("section_title") or ctx.get("new_topic_title") or ""
    ).strip()
    fallback_instr = {
        "save_outline_section_edit": (
            f"Update section {sec_no} to '{sec_title}' with subtopics:"
            f" {ctx.get('subtopics_text') or ''}"
        ),
        "delete_outline_section": f"Remove section {sec_no} '{sec_title}'",
        "add_outline_section": (
            f"Add a new agenda section '{sec_title}' with subtopics:"
            f" {ctx.get('new_topic_subtopics') or ''}"
        ),
    }[action_name]
    last_content.parts = [
        types.Part(
            text=(
                f"Refine the proposal outline for {cust_name or 'Customer'}."
                " Invoke enterprise_refine_proposal_outline with"
                f" customer_name='{cust_name}',"
                f" refinement_instructions='{fallback_instr}'. Do NOT call"
                " enterprise_slide_generator_skill yet."
            )
        )
    ]
    return None

  # CASE A: User clicked "🔄 Refine Outline" in the A2UI Outline Review card
  if action_name in ("refine_proposal_outline", "refine_outline"):
    logging.info(
        "[enterprise_before_model_callback] Intercepted A2UI outline"
        " refinement action (%s): customer='%s', instructions='%s', edits=%d",
        action_name,
        cust_name,
        refinement_instr,
        len(section_edits),
    )
    try:
      cached_raw = None
      if state is not None and hasattr(state, "get"):
        cached_raw = state.get("proposal_outline")
      if not cached_raw:
        cust_k = f"cust:{cust_name.strip().lower()}" if cust_name else ""
        if cust_k and cust_k in _LATEST_OUTLINE_CACHE:
          cached_raw = _LATEST_OUTLINE_CACHE[cust_k]
        else:
          cached_raw = _LATEST_OUTLINE_CACHE.get("_latest_")
      if cached_raw:
        updated_raw, _, resolved_c, _ = _apply_outline_refinement_and_edits(
            base_outline_raw=cached_raw,
            refinement_instructions=refinement_instr,
            deck_strategy=deck_strategy,
            section_edits=section_edits,
        )
        if state is not None:
          state["proposal_outline"] = updated_raw
          state["_pre_refined_outline_ready"] = True
          if refinement_instr:
            state["last_applied_refinement_instructions"] = refinement_instr
        _LATEST_OUTLINE_CACHE["_latest_"] = updated_raw
        _LATEST_OUTLINE_CACHE["_pre_refined_ready_"] = True
        if refinement_instr:
          _LATEST_OUTLINE_CACHE["_last_applied_refinement_"] = refinement_instr
        if resolved_c:
          _LATEST_OUTLINE_CACHE[f"cust:{resolved_c.strip().lower()}"] = (
              updated_raw
          )
    except Exception as pre_refine_err:
      logging.warning(
          "[enterprise_before_model_callback] Pre-refine sync notice: %s",
          pre_refine_err,
      )

    prompt_override = (
        f"Refine the proposal outline for {cust_name or 'Customer'} with"
        f" instructions: '{refinement_instr}' (Deck Strategy:"
        f" {deck_strategy or 'smart_hybrid'}). Invoke"
        f" enterprise_refine_proposal_outline with customer_name='{cust_name}',"
        f" refinement_instructions='{refinement_instr}',"
        f" deck_strategy='{deck_strategy or 'smart_hybrid'}', and"
        f" section_edits_json='{json.dumps(section_edits)}'. Do NOT call"
        " enterprise_slide_generator_skill yet; present the updated outline"
        " sections for review. (In your thinking, write 2-3 concise"
        " third-person executive GTM strategy bullets on how these refinements"
        f" strengthen the CVI narrative for {cust_name or 'the customer'};"
        " never start with 'My Thought Process' or 'Alright'.)"
    )
    last_content.parts = [types.Part(text=prompt_override)]
    return None

  # CASE B: User clicked "🚀 Approve Outline & Generate Deck" in the A2UI Outline Review card
  if action_name in (
      "approve_outline_and_generate",
      "approve_outline",
      "generate_deck",
  ):
    last_applied = ""
    if state is not None and hasattr(state, "get"):
      last_applied = str(
          state.get("last_applied_refinement_instructions") or ""
      ).strip()
    if not last_applied:
      last_applied = str(
          _LATEST_OUTLINE_CACHE.get("_last_applied_refinement_") or ""
      ).strip()
    pending_instr = (
        refinement_instr
        if (refinement_instr and refinement_instr != last_applied)
        else ""
    )
    # The Approve button's own literal `prompt` ("Approve outline and
    # synthesize presentation deck ...") is not a refinement instruction.
    if pending_instr.lower().startswith("approve outline"):
      pending_instr = ""
    if section_edits or deck_strategy or pending_instr:
      try:
        cached_raw = None
        if state is not None and hasattr(state, "get"):
          cached_raw = state.get("proposal_outline")
        if not cached_raw:
          cust_k = f"cust:{cust_name.strip().lower()}" if cust_name else ""
          if cust_k and cust_k in _LATEST_OUTLINE_CACHE:
            cached_raw = _LATEST_OUTLINE_CACHE[cust_k]
          else:
            cached_raw = _LATEST_OUTLINE_CACHE.get("_latest_")
        if cached_raw:
          updated_raw, _, resolved_c, _ = _apply_outline_refinement_and_edits(
              base_outline_raw=cached_raw,
              refinement_instructions=pending_instr,
              deck_strategy=deck_strategy,
              section_edits=section_edits,
          )
          if state is not None:
            state["proposal_outline"] = updated_raw
            if pending_instr:
              state["last_applied_refinement_instructions"] = pending_instr
          _LATEST_OUTLINE_CACHE["_latest_"] = updated_raw
          if pending_instr:
            _LATEST_OUTLINE_CACHE["_last_applied_refinement_"] = pending_instr
          if resolved_c:
            _LATEST_OUTLINE_CACHE[f"cust:{resolved_c.strip().lower()}"] = (
                updated_raw
            )
      except Exception as pre_gen_err:
        logging.warning(
            "[enterprise_before_model_callback] Pre-generation outline sync"
            " notice: %s",
            pre_gen_err,
        )

    compact_approve_state = json.dumps({
        "customer_name": cust_name or "Customer",
        "deck_strategy": deck_strategy or "smart_hybrid",
    })
    approve_prompt = (
        "Generate the Google Slides presentation deck for"
        f" '{cust_name or 'Customer'}' using the approved outline (Strategy:"
        f" {deck_strategy or 'smart_hybrid'}). Invoke"
        " enterprise_slide_generator_skill with"
        f" state_json='{compact_approve_state}'. (In your thinking, write 2-3"
        " concise third-person executive GTM strategy bullets on slide"
        " engineering, visual customization, and executive value alignment for"
        f" {cust_name or 'the customer'}; never start with 'My Thought Process'"
        " or 'Alright', and never mention tool names or JSON payloads.)"
    )
    last_content.parts = [types.Part(text=approve_prompt)]
    return None

  # CASE C: User clicked "✨ Synthesize Proposal Outline" in the A2UI GTM Intake form
  if action_name in ("create_proposal_outline", "generate_outline"):
    b_ctx = str(
        ctx.get("business_context")
        or ctx.get("user_prompt")
        or ctx.get("prompt")
        or ""
    ).strip()
    s_play = _clean_intake_sales_plays(
        ctx.get("sales_play") or ctx.get("salesPlay") or ctx.get("sales_plays"),
        ctx.get("secondary_sales_play") or ctx.get("additional_sales_plays"),
    )
    ind = _clean_intake_select_val(ctx.get("industry"))
    aud = _clean_intake_multi_val(
        ctx.get("audience") or ctx.get("target_audience")
    )
    s_stage = _clean_intake_select_val(
        ctx.get("sales_stage") or ctx.get("win_cycle")
    )
    arch = _clean_intake_select_val(ctx.get("presentation_archetype"))
    reg = str(ctx.get("region") or ctx.get("target_region") or "").strip()
    er_num = str(ctx.get("er_number") or "").strip()
    d_len = _clean_intake_select_val(
        ctx.get("deck_length") or ctx.get("request_type"),
        default="Standard (8-12 slides)",
    )
    strat = _clean_intake_select_val(
        ctx.get("deck_strategy"), default="smart_hybrid"
    )
    arch_arg = f" presentation_archetype='{arch}'," if arch else ""
    seg = _clean_intake_select_val(ctx.get("segment"))
    if seg.lower().startswith("auto-detect"):
      seg = ""
    seg_arg = f" segment='{seg}'," if seg else ""
    intake_prompt = (
        f"Synthesize a tailored Google Cloud proposal outline for {cust_name}:"
        f" customer_name='{cust_name}',"
        f" business_context='{b_ctx or f'Strategic Google Cloud proposal for {cust_name}'}',"
        f" salesPlay='{s_play}', industry='{ind}', audience='{aud}',"
        f" sales_stage='{s_stage}',{arch_arg}{seg_arg} region='{reg}',"
        f" er_number='{er_num}', request_type='{d_len}',"
        f" deck_strategy='{strat}'. Invoke enterprise_create_proposal_outline"
        " with these parameters. (In your thinking, write 3 concise"
        f" third-person executive GTM strategy bullets analyzing {cust_name}'s"
        " industry imperatives, CVI narrative architecture for"
        f" {aud or 'executives'} at stage {s_stage or 'S1'}, and"
        f" {s_play or 'Google Cloud'} differentiation; never start with 'My"
        " Thought Process' or 'Alright'.)"
    )
    last_content.parts = [types.Part(text=intake_prompt)]
    return None

  # CASE D: User clicked "➕ Insert Slide into Active Deck" in the Slide Search A2UI card
  if action_name == "insert_library_slide":
    src_pres = str(ctx.get("source_presentation_id") or "").strip()
    tmpl_slide = str(
        ctx.get("template_slide_id") or ctx.get("slide_id") or ""
    ).strip()
    raw_tgt_pres = str(
        ctx.get("target_presentation_id") or ctx.get("presentation_id") or ""
    ).strip()
    active_pres_id, _, _ = _resolve_active_deck_from_state_or_cache(
        raw_tgt_pres, callback_context
    )
    tgt_pres = active_pres_id or raw_tgt_pres
    s_title = str(ctx.get("slide_title") or "").strip()
    s_job = str(ctx.get("slide_job") or "Proof_Points").strip()
    insert_prompt = (
        "Invoke enterprise_insert_slide_skill with"
        f" source_presentation_id='{src_pres}',"
        f" template_slide_id='{tmpl_slide}',"
        f" target_presentation_id='{tgt_pres}',"
        f" slide_title='{s_title}',"
        f" slide_job='{s_job}'. Mutate the active presentation in-place; do NOT"
        " create a new deck."
    )
    last_content.parts = [types.Part(text=insert_prompt)]
    return None

  # CASE E: User clicked "🔍 Search Slides" or "🔍 Search Library" in A2UI.
  # Deterministic fast path: run the search directly and return exactly one
  # results card without an LLM round-trip (no form re-render).
  if action_name in ("search_slides", "search"):
    if state is not None:
      try:
        state["last_target_card"] = ""
      except Exception:
        pass
    raw_tgt = str(
        ctx.get("target_presentation_id") or ctx.get("presentation_id") or ""
    ).strip()
    active_pres_id, _, resolved_cust = _resolve_active_deck_from_state_or_cache(
        raw_tgt, callback_context
    )
    effective_cust = (
        str(ctx.get("customer_name") or "").strip()
        or cust_name
        or resolved_cust
    )
    s_query = str(
        ctx.get("search_query")
        or ctx.get("query")
        or (
            f"{effective_cust} Customer References"
            if effective_cust
            else "Customer References"
        )
    ).strip()
    s_job = _clean_str(ctx.get("slide_job")).strip()
    if s_job.lower() in ("all", "any", "all slide categories", "none"):
      s_job = ""
    if state is not None:
      try:
        state["a2ui_payloads_to_inject"] = []
      except Exception:
        pass
    _PENDING_A2UI_PAYLOADS.clear()
    raw_search = ""
    try:
      raw_search = enterprise_search_slides_skill(
          search_query=s_query,
          slide_job=s_job,
          target_presentation_id=active_pres_id or raw_tgt,
          tool_context=callback_context,
      )
    except Exception as search_err:  # pylint: disable=broad-except
      logging.warning(
          "[enterprise_before_model_callback] Deterministic slide search"
          " notice: %s",
          search_err,
      )
    stashed: Any = []
    cot_text = ""
    if state is not None:
      try:
        stashed = state.get("a2ui_payloads_to_inject") or []
        state["a2ui_payloads_to_inject"] = []
        cot_text = str(state.get("latest_cot_summary") or "")
        state["latest_cot_summary"] = ""
      except Exception:
        pass
    if _PENDING_A2UI_PAYLOADS:
      stashed = list(stashed) + list(_PENDING_A2UI_PAYLOADS)
      _PENDING_A2UI_PAYLOADS.clear()
    if not cot_text:
      cot_text = str(_LATEST_OUTLINE_CACHE.pop("_latest_cot_", "") or "")
    else:
      _LATEST_OUTLINE_CACHE.pop("_latest_cot_", None)
    a2ui_parts = _a2ui_payloads_to_parts(stashed)
    n_found = 0
    search_error = ""
    try:
      parsed = json.loads(raw_search) if raw_search else {}
      if isinstance(parsed, dict):
        n_found = len(parsed.get("slides") or [])
        search_error = str(parsed.get("error") or "")
    except Exception:  # pylint: disable=broad-except
      search_error = "" if raw_search else "search unavailable"
    if search_error and not n_found:
      anchor_text = (
          f"I couldn't complete the slide search for “{s_query}” right now."
          " Please try again or refine your query."
      )
    elif n_found:
      anchor_text = (
          f"Found {n_found} slide{'s' if n_found != 1 else ''} for"
          f" “{s_query}” — click a slide to preview it and insert it into"
          " your deck."
      )
    else:
      anchor_text = (
          f"No slides matched “{s_query}”. Try a broader query or a"
          " different slide category."
      )
    resp_parts: list[Any] = []
    if cot_text:
      resp_parts.append(types.Part(text=cot_text, thought=True))
    resp_parts.append(types.Part(text=anchor_text))
    resp_parts.extend(a2ui_parts)
    logging.info(
        "[enterprise_before_model_callback] Deterministic search_slides fast"
        " path: query='%s', results=%d, a2ui_parts=%d.",
        s_query,
        n_found,
        len(a2ui_parts),
    )
    return LlmResponse(
        content=types.Content(role="model", parts=resp_parts),
        custom_metadata={"a2a:response": True},
    )

  # CASE F: User clicked "✨ Augment & Transform Slide Text" or "✍️ Transform Slide Text"
  if action_name in (
      "transform_slide_text",
      "transform_deck_text",
      "transform",
  ):
    if state is not None:
      try:
        state["last_target_card"] = ""
      except Exception:
        pass
    raw_p_id = str(
        ctx.get("presentation_url_or_id")
        or ctx.get("presentation_id")
        or ctx.get("presentation_url")
        or ""
    ).strip()
    active_pres_id, _, resolved_cust = _resolve_active_deck_from_state_or_cache(
        raw_p_id, callback_context
    )
    p_id = raw_p_id or active_pres_id
    effective_cust = cust_name or resolved_cust
    t_mode = _normalize_transform_list(
        ctx.get("transformation_mode"), placeholder="slide transformation mode"
    )
    raw_crit = str(
        ctx.get("custom_instructions")
        or ctx.get("transform_instructions")
        or ctx.get("criteria")
        or ctx.get("tone")
        or ""
    ).strip()
    if t_mode and raw_crit and t_mode.lower() not in raw_crit.lower():
      crit = f"{t_mode}: {raw_crit}"
    else:
      crit = (
          raw_crit
          or t_mode
          or f"Align executive tone and value pillars for {effective_cust or 'the customer'}"
      )
    raw_s_range = str(
        ctx.get("target_slide_indices") or ctx.get("slide_range") or ""
    ).strip()
    has_specific_slide_scope = bool(
        raw_s_range
        and raw_s_range.lower() not in ("all", "full_deck", "entire_deck", "*")
    )
    if has_specific_slide_scope:
      is_full_deck = False
      s_range = raw_s_range
    else:
      is_full_deck = True
      s_range = ""
    ind = _normalize_transform_list(ctx.get("industry"), placeholder="industry")
    aud = _normalize_transform_list(
        ctx.get("audience") or ctx.get("target_audience"),
        placeholder="audience",
    )
    lang = str(
        ctx.get("language") or ctx.get("target_language") or "English"
    ).strip()
    raw_scope_mode = _normalize_transform_list(
        ctx.get("transform_scope_mode"), placeholder="what to transform"
    ).lower()
    scope_mode = (
        raw_scope_mode
        if raw_scope_mode in ("text_only", "images_only", "both")
        else "text_only"
    )
    if state is not None:
      try:
        state["last_transform_card_ctx"] = dict(ctx)
      except Exception:
        pass
    transform_prompt = (
        "Invoke enterprise_transform_slide_text_skill with"
        f" presentation_url_or_id='{p_id}',"
        f" customization_criteria='{crit}',"
        f" target_slide_indices='{s_range}',"
        f" customer_name='{effective_cust}',"
        f" industry='{ind}',"
        f" audience='{aud}',"
        f" full_deck_scope={is_full_deck},"
        f" transform_scope_mode='{scope_mode}',"
        f" language='{lang}'. Transform the existing presentation in-place;"
        " do NOT create a new presentation."
    )
    last_content.parts = [types.Part(text=transform_prompt)]
    return None

  # CASE G: User clicked "🍌 Generate Visuals" or "🍌 Synthesize & Insert Visual into Deck" or "Transform Slide Visual"
  if action_name in (
      "transform_with_nano_banana",
      "generate_visuals",
      "diagram",
  ):
    if state is not None:
      try:
        state["last_target_card"] = ""
      except Exception:
        pass
    raw_p_id = str(
        ctx.get("presentation_url_or_id") or ctx.get("presentation_id") or ""
    ).strip()
    active_pres_id, _, resolved_cust = _resolve_active_deck_from_state_or_cache(
        raw_p_id, callback_context
    )
    p_id = active_pres_id or raw_p_id
    brand_ctx = str(
        ctx.get("brand_context") or ctx.get("customer_name") or ""
    ).strip()
    ref_img = str(ctx.get("reference_image_url") or "").strip()
    effective_cust = brand_ctx or cust_name or resolved_cust
    v_prompt = str(
        ctx.get("prompt")
        or ctx.get("visual_prompt")
        or f"Enterprise Google Cloud Reference Architecture for {effective_cust or 'Customer'}"
    ).strip()
    if brand_ctx and brand_ctx.lower() not in v_prompt.lower():
      v_prompt = f"{v_prompt} (Target Brand/Account Context: {brand_ctx})"
    if ref_img:
      v_prompt = f"{v_prompt} (Style Reference Image: {ref_img})"
    v_style = _clean_str(
        ctx.get("style")
        or ctx.get("visual_style")
        or "Google Cloud Modern Architecture (Flat vector, precise topology)"
    ).strip()
    if v_style.lower() in ("visual architecture style", "target visual style"):
      v_style = (
          "Google Cloud Modern Architecture (Flat vector, precise topology)"
      )
    s_idx_raw = str(
        ctx.get("slide_index") or ctx.get("target_slide_index") or "1"
    ).strip()
    s_idx = int(s_idx_raw) if s_idx_raw.isdigit() else 1
    v_mode_raw = (
        (_normalize_transform_list(ctx.get("mode")) or "generate")
        .strip()
        .lower()
    )
    if "restyle" in v_mode_raw or "transform" in v_mode_raw:
      v_mode = "transform"
    else:
      v_mode = "generate"
    raw_sel_model = (
        (
            _normalize_transform_list(
                ctx.get("model") or ctx.get("selected_model")
            )
            or "nano_banana_pro"
        )
        .strip()
        .lower()
    )
    if "2.1" in raw_sel_model or "2_1" in raw_sel_model:
      sel_model = "gemini-nano-banana-2.1"
    elif "flash" in raw_sel_model or raw_sel_model in (
        "nano_banana",
        "nano banana",
    ):
      sel_model = "nano_banana"
    else:
      sel_model = "nano_banana_pro"
    visual_prompt = (
        "Invoke enterprise_generate_visuals_skill with"
        f" prompt='{v_prompt}', presentation_url_or_id='{p_id}',"
        f" visual_style='{v_style}', target_slide_index={s_idx},"
        f" mode='{v_mode}', selected_model='{sel_model}'."
    )
    last_content.parts = [types.Part(text=visual_prompt)]
    return None

  # CASE H: User clicked "🚀 Start New Pitch Deck (GTM Intake)"
  if action_name == "intake":
    last_content.parts = [
        types.Part(
            text=(
                "Invoke enterprise_intake_form_skill to open the GTM intake"
                " card."
            )
        )
    ]
    return None

  # CASE I: User clicked "🌐 Translate Presentation" in the Translate Presentation A2UI card
  if action_name in (
      "translate_presentation_deck",
      "translate_deck",
      "translate",
      "submit_translate",
      "pitchgen_translate_submit",
  ):
    if state is not None:
      try:
        state["last_target_card"] = ""
        state["last_translate_card_ctx"] = dict(ctx)
      except Exception:
        pass
    raw_p_id = str(
        ctx.get("presentation_url_or_id")
        or ctx.get("presentation_id")
        or ctx.get("presentation_url")
        or ""
    ).strip()
    active_pres_id, _, _ = _resolve_active_deck_from_state_or_cache(
        raw_p_id, callback_context
    )
    p_id = raw_p_id or active_pres_id
    inst = _clean_str(
        ctx.get("translate_instructions")
        or ctx.get("custom_instructions")
        or ""
    ).strip()
    t_lang = (
        _normalize_transform_list(
            ctx.get("target_language") or ctx.get("language") or "",
            placeholder="Select Language",
        )
        or _extract_language_from_text(inst)
        or "Spanish"
    )
    raw_full_deck = ctx.get("full_deck_scope")
    is_full_deck = False
    if isinstance(raw_full_deck, list):
      is_full_deck = any(
          str(x).strip().lower() in ("full_deck", "all", "true")
          for x in raw_full_deck
      )
    elif isinstance(raw_full_deck, bool):
      is_full_deck = raw_full_deck
    elif isinstance(raw_full_deck, str):
      is_full_deck = raw_full_deck.strip().lower() in (
          "full_deck",
          "all",
          "true",
      )
    elif str(ctx.get("scope") or "").strip().lower() == "full_deck":
      is_full_deck = True

    raw_s_indices = str(
        ctx.get("target_slide_indices") or ctx.get("slide_range") or ""
    ).strip()
    if raw_s_indices and raw_s_indices.lower() not in (
        "all",
        "full_deck",
        "full deck",
        "none",
        "null",
    ):
      is_full_deck = False
      s_indices = raw_s_indices
    else:
      s_indices = "" if is_full_deck else raw_s_indices

    slide_scope_desc = (
        f", target_slide_indices='{s_indices}'" if s_indices else ""
    )
    inst_desc = f", translate_instructions='{inst}'" if inst else ""
    translate_prompt = (
        "Invoke enterprise_translate_deck_skill with"
        f" presentation_url_or_id='{p_id}', target_language='{t_lang}'"
        f"{inst_desc}{slide_scope_desc}, full_deck_scope={is_full_deck}."
        " Translate the presentation in-place; do NOT create a new"
        " presentation."
    )
    last_content.parts = [types.Part(text=translate_prompt)]
    return None

  # CASE J: User clicked "➕ Generate Slide" in the Generate a Single Slide A2UI card
  if action_name in ("generate_single_slide", "generate_slide"):
    if state is not None:
      try:
        state["last_target_card"] = ""
      except Exception:
        pass
    raw_p_id = str(
        ctx.get("presentation_url_or_id") or ctx.get("presentation_id") or ""
    ).strip()
    active_pres_id, _, resolved_cust = _resolve_active_deck_from_state_or_cache(
        raw_p_id, callback_context
    )
    p_id = raw_p_id or active_pres_id
    effective_cust = cust_name or resolved_cust
    s_topic = str(ctx.get("slide_topic") or ctx.get("prompt") or "").strip()
    s_job = _clean_str(ctx.get("slide_job") or "Solution_Overview").strip()
    gen_slide_prompt = (
        f"Generate a custom Google Slides slide on topic '{s_topic}'"
        f" (Category: {s_job}, Customer: '{effective_cust or 'Customer'}',"
        f" Target Presentation: '{p_id}'). Invoke sidebar_generate with"
        f" user_prompt='{s_topic}', customer_name='{effective_cust}',"
        f" presentation_id='{p_id}'."
    )
    last_content.parts = [types.Part(text=gen_slide_prompt)]
    return None

  return None


_META_THOUGHT_LEAK_PATTERNS = (
    "workflow 0",
    "workflow 1",
    "workflow 2",
    "workflow 3",
    "workflow 4",
    "workflow 5",
    "workflow 6",
    "enterprise_intake_form_skill",
    "enterprise_create_proposal_outline",
    "enterprise_refine_proposal_outline",
    "enterprise_slide_generator_skill",
    "enterprise_search_slides_skill",
    "enterprise_transform_slide_text_skill",
    "enterprise_generate_visuals_skill",
    "enterprise_insert_slide_skill",
    "state_json",
    "<customer>",
    "<user_ldap>",
    "<deck_url>",
    "<a2a_datapart_json>",
    "<a2ui-json>",
    "inline_data",
    "my internal protocol",
    "mandatory requirement",
    "my thought process",
    "alright, so",
    "alright, i've",
    "received the output from the tool",
    "which is me in this context",
    "the instruction is crystal clear",
    "user has explicitly",
    "provided the exact",
)


def _is_low_quality_meta_thought(text: str) -> bool:
  """Returns True if a model thought part leaks internal prompt instructions, tool names, or placeholders."""
  if not text or not text.strip():
    return True
  lower = text.lower()
  return any(pat in lower for pat in _META_THOUGHT_LEAK_PATTERNS)


def _build_executive_pre_tool_thought(
    fn_calls: list[Any],
    callback_context: Any = None,
) -> str:
  """Builds a rich, customer-grounded executive Chain-of-Thought step for tool execution."""
  state = getattr(callback_context, "state", None) if callback_context else None
  sess_cust = ""
  sess_ind = ""
  sess_play = ""
  if state is not None and hasattr(state, "get"):
    sess_cust = str(state.get("customer_name") or "").strip()
    sess_ind = str(state.get("industry") or "").strip()
    sess_play = str(state.get("salesPlay") or "").strip()

  lines = []
  for fc in fn_calls:
    fn_name = getattr(fc, "name", "") or ""
    args = getattr(fc, "args", None) or {}
    if not isinstance(args, dict):
      try:
        args = dict(args)
      except Exception:
        args = {}

    cust = str(args.get("customer_name") or sess_cust or "").strip()
    ind = str(args.get("industry") or sess_ind or "").strip()
    play = str(
        args.get("salesPlay") or args.get("sales_play") or sess_play or ""
    ).strip()

    if fn_name == "enterprise_create_proposal_outline":
      lines.append(
          "Researching organization context, resolving industry benchmarks,"
          " and structuring the executive presentation outline for"
          f" **{cust or 'the target account'}**"
          + (f" ({ind})" if ind else "")
          + (f" anchored on Google Cloud **{play}**." if play else "...")
      )
    elif fn_name == "enterprise_refine_proposal_outline":
      instr = str(args.get("refinement_instructions") or "").strip()
      lines.append(
          "Refining executive narrative flow and agenda architecture for"
          f" **{cust or 'the presentation'}**"
          + (f" (`{instr[:120]}`)" if instr else "")
          + "..."
      )
    elif fn_name == "enterprise_slide_generator_skill":
      lines.append(
          "Matching verified CloudHub reusable slides, synthesizing tailored"
          " executive copy & Nano Banana visuals, and assembling the Google"
          f" Slides deck for **{cust or 'your account'}**..."
      )
    elif fn_name == "enterprise_search_slides_skill":
      q = str(args.get("search_query") or "Customer References").strip()
      job = str(args.get("slide_job") or "").strip()
      lines.append(
          "Searching the 2026 Consolidated Customer Reference Library and"
          f" CloudHub repository for **{q}**"
          + (f" (Slide Job: `{job}`)" if job else "")
          + (f" aligned to **{cust}** ({ind})" if cust else "")
          + "..."
      )
    elif fn_name == "enterprise_insert_slide_skill":
      s_title = str(
          args.get("slide_title")
          or args.get("template_slide_id")
          or "selected slide"
      ).strip()
      lines.append(
          f"Linking and inserting **{s_title}** into the active Google Slides"
          " presentation on Canvas..."
      )
    elif fn_name == "enterprise_transform_slide_text_skill":
      crit = str(
          args.get("customization_criteria") or "executive clarity and impact"
      ).strip()
      lines.append(
          "Analyzing slide layout hierarchy and transforming presentation copy"
          f" (`{crit[:100]}`) while preserving verified customer metrics..."
      )
    elif fn_name == "enterprise_generate_visuals_skill":
      p = str(
          args.get("prompt") or "Google Cloud architecture topology"
      ).strip()
      lines.append(
          f"Designing high-resolution 16:9 architecture visual (**{p[:100]}**)"
          " with Nano Banana..."
      )
    elif fn_name == "enterprise_customer_insights_skill":
      lines.append(
          "Synthesizing Voice of the Customer (VoC) insights, competitive SWOT"
          " positioning, and peer reference stories for"
          f" **{cust or 'the target account'}**..."
      )
    else:
      label = _TOOL_STEP_LABELS.get(
          fn_name, f"Executing {fn_name.replace('_', ' ')}..."
      )
      lines.append(label)
  return "\n".join(lines)


def enterprise_after_model_callback(
    callback_context: Any,
    llm_response: Any,
) -> Any:
  """Extracts and injects A2UI payloads, upgrades Chain-of-Thought quality, and sets Workspace ImmersiveArtifact state."""
  if not llm_response or not getattr(llm_response, "content", None):
    return llm_response

  parts = getattr(llm_response.content, "parts", None) or []
  fn_calls = [
      getattr(p, "function_call", None)
      for p in parts
      if getattr(p, "function_call", None)
  ]
  if fn_calls:
    exec_thought_text = _build_executive_pre_tool_thought(
        fn_calls, callback_context
    )
    has_thought = any(getattr(p, "thought", False) for p in parts)
    if not has_thought:
      thought_part = types.Part(text=exec_thought_text, thought=True)
      updated_fn_parts = [thought_part] + list(parts)
    else:
      updated_fn_parts = []
      replaced_first = False
      for p in parts:
        if getattr(p, "thought", False):
          raw_t = getattr(p, "text", "") or ""
          if not replaced_first and (
              _is_low_quality_meta_thought(raw_t)
              or "enterprise_create_proposal_outline"
              in [getattr(fc, "name", "") for fc in fn_calls]
          ):
            sig = getattr(p, "thought_signature", None)
            new_tp = types.Part(
                text=exec_thought_text,
                thought=True,
                thought_signature=sig,
            )
            updated_fn_parts.append(new_tp)
            replaced_first = True
          elif not _is_low_quality_meta_thought(raw_t):
            updated_fn_parts.append(p)
        else:
          updated_fn_parts.append(p)
      if not any(getattr(p, "thought", False) for p in updated_fn_parts):
        updated_fn_parts.insert(
            0, types.Part(text=exec_thought_text, thought=True)
        )

    if hasattr(llm_response.content, "parts"):
      llm_response.content.parts = updated_fn_parts
    return llm_response.model_copy(
        update={
            "content": types.Content(
                parts=updated_fn_parts,
                role=llm_response.content.role,
            )
        }
    )

  all_a2ui_messages = []

  # 1. Collect from session state and in-memory queue if stored by tool execution
  if _PENDING_A2UI_PAYLOADS:
    all_a2ui_messages.extend(_PENDING_A2UI_PAYLOADS)
    _PENDING_A2UI_PAYLOADS.clear()

  state = getattr(callback_context, "state", None)
  stashed_cot_summary = ""
  if state is not None:
    stashed = None
    if hasattr(state, "get"):
      stashed = state.get("a2ui_payloads_to_inject")
      stashed_cot_summary = str(state.get("latest_cot_summary") or "").strip()
    elif hasattr(state, "__getitem__") and "a2ui_payloads_to_inject" in state:
      stashed = state["a2ui_payloads_to_inject"]
    if stashed:
      if isinstance(stashed, list):
        all_a2ui_messages.extend(stashed)
      else:
        all_a2ui_messages.append(stashed)
      state["a2ui_payloads_to_inject"] = []
    if stashed_cot_summary and hasattr(state, "__setitem__"):
      try:
        state["latest_cot_summary"] = ""
      except Exception:
        pass
  if not stashed_cot_summary:
    stashed_cot_summary = str(
        _LATEST_OUTLINE_CACHE.pop("_latest_cot_", "") or ""
    ).strip()
  else:
    _LATEST_OUTLINE_CACHE.pop("_latest_cot_", None)

  # 2. Collect from <a2ui-json> or <a2a_datapart_json> tags in text parts and strip them
  cleaned_parts = []
  replaced_post_thought = False
  for part in parts:
    text = getattr(part, "text", None)
    inline = getattr(part, "inline_data", None)
    if not text and inline and getattr(inline, "data", None):
      try:
        raw_b = inline.data
        decoded_str = (
            raw_b.decode("utf-8", errors="ignore")
            if isinstance(raw_b, (bytes, bytearray))
            else str(raw_b)
        )
        if (
            a2ui_util.A2A_DATA_PART_START_TAG in decoded_str
            or "<a2ui-json>" in decoded_str
        ):
          text = decoded_str
      except Exception:
        pass
    if not text:
      cleaned_parts.append(part)
      continue

    is_thought = bool(getattr(part, "thought", False))

    # Extract any <a2ui-json> content
    tag_matches = re.findall(r"<a2ui-json>(.*?)</a2ui-json>", text, re.DOTALL)
    for tm in tag_matches:
      try:
        parsed_tm = json.loads(tm.strip())
        if isinstance(parsed_tm, list):
          all_a2ui_messages.extend(parsed_tm)
        else:
          all_a2ui_messages.append(parsed_tm)
      except Exception:
        pass

    # Also extract any <a2a_datapart_json> content echoed by LLM
    a2a_matches = re.findall(
        r"<a2a_datapart_json>(.*?)</a2a_datapart_json>", text, re.DOTALL
    )
    for am in a2a_matches:
      try:
        parsed_am = json.loads(am.strip())
        if (
            isinstance(parsed_am, dict)
            and "data" in parsed_am
            and parsed_am.get("kind") == "data"
        ):
          parsed_am = parsed_am["data"]
        if isinstance(parsed_am, list):
          all_a2ui_messages.extend(parsed_am)
        elif isinstance(parsed_am, dict):
          all_a2ui_messages.append(parsed_am)
      except Exception:
        pass

    # Strip raw <a2ui-json>, <a2a_datapart_json>, and [canvas artifact: ...] tags from displayed text
    cleaned_text = re.sub(
        r"<a2ui-json>.*?(?:</a2ui-json>|$)", "", text, flags=re.DOTALL
    )
    cleaned_text = re.sub(
        r"<a2a_datapart_json>.*?(?:</a2a_datapart_json>|$)",
        "",
        cleaned_text,
        flags=re.DOTALL,
    )
    cleaned_text = re.sub(
        r"\[canvas artifact:[^\n]*\]\s*", "", cleaned_text
    )
    cleaned_text = re.sub(
        r"\[Active Google Slides Presentation on Canvas:[^\n]*?\)\]\s*",
        "",
        cleaned_text,
    )
    cleaned_text = re.sub(
        r"\[Active Google Slides Presentation on Canvas:[^\]]*\]\s*",
        "",
        cleaned_text,
    )
    cleaned_text = re.sub(
        r"\s*(?:\[PitchGen\]\s*)?[A-Za-z0-9][^.\n]{0,120}\(presentation_id=[a-zA-Z0-9_-]+,\s*url=https://docs\.google\.com/presentation/d/[^\)]+\)\]\s*",
        "",
        cleaned_text,
    ).strip()

    if is_thought:
      if stashed_cot_summary and not replaced_post_thought:
        cleaned_parts.append(
            types.Part(
                text=stashed_cot_summary,
                thought=True,
                thought_signature=getattr(part, "thought_signature", None),
            )
        )
        replaced_post_thought = True
      elif _is_low_quality_meta_thought(cleaned_text):
        fallback_cot = (
            stashed_cot_summary
            or "**Executive GTM Synthesis**\n- Aligned response with Google Cloud Value Framework (CVI), industry benchmarks, and active presentation state."
        )
        if not replaced_post_thought:
          cleaned_parts.append(
              types.Part(
                  text=fallback_cot,
                  thought=True,
                  thought_signature=getattr(part, "thought_signature", None),
              )
          )
          replaced_post_thought = True
      elif cleaned_text:
        cleaned_parts.append(
            types.Part(
                text=cleaned_text,
                thought=True,
                thought_signature=getattr(part, "thought_signature", None),
            )
        )
      continue

    if cleaned_text:
      cleaned_parts.append(types.Part(text=cleaned_text))

  # If a deck was just generated on this turn, ensure the canvas_artifact state_delta, file_data, and A2UI Canvas sidepanel are present
  cached_deck_raw = _LATEST_OUTLINE_CACHE.pop("_just_generated_deck_", None)
  cached_deck = None
  if cached_deck_raw:
    try:
      cached_deck = json.loads(cached_deck_raw)
    except Exception:
      cached_deck = None

  is_deck_generated = bool(cached_deck) or (
      state is not None
      and hasattr(state, "get")
      and bool(state.get("deck_just_generated"))
  )
  if is_deck_generated:
    try:
      if state is not None and hasattr(state, "get"):
        state["deck_just_generated"] = False
      deck_url = (cached_deck or {}).get("deck_url") or (
          state.get("deck_url", "") if state is not None else ""
      )
      pres_id = (
          (cached_deck or {}).get("pres_id")
          or (state.get("presentation_id", "") if state is not None else "")
          or "deck"
      )
      cust_name = (
          (cached_deck or {}).get("customer_name")
          or (state.get("customer_name") if state is not None else "")
          or "Customer"
      ).replace("'", "")
      if deck_url:
        deck_title = (
            (cached_deck or {}).get("deck_title")
            or (state.get("deck_title") if state is not None else "")
            or f"[PitchGen] {cust_name} Presentation"
        ).replace("'", "")
        canvas_artifact_proto = a2ui_util.build_canvas_artifact_textproto(
            deck_url=deck_url,
            title=deck_title,
            model_generated_id=f"pitchgen-deck-{pres_id}",
        )
        if state is not None:
          try:
            state["canvas_artifact"] = canvas_artifact_proto
          except Exception:
            pass
        try:
          cleaned_parts.append(
              types.Part(
                  file_data=types.FileData(
                      file_uri=deck_url,
                      mime_type="application/vnd.google-apps.presentation",
                      display_name=deck_title,
                  )
              )
          )
        except Exception:
          pass

        active_ver = (cached_deck or {}).get(
            "active_ver"
        ) or a2ui_util.detect_client_a2ui_version(
            tool_context=callback_context, default_version="v0.9"
        )
        prev_outline_ids = (cached_deck or {}).get(
            "prev_outline_ids"
        ) or _collect_prior_outline_surface_ids(callback_context)
        for old_sid in prev_outline_ids:
          all_a2ui_messages.extend(
              a2ui_util.create_a2ui_delete_surface_message(
                  surface_id=old_sid,
                  version="v0.9" if active_ver == "v0.9" else "v0.8",
              )
          )
    except Exception:
      pass

  # Fallback: if no A2UI messages were captured (e.g. LLM chose conversational text
  # without invoking enterprise_launcher_card_skill, enterprise_intake_form_skill, or enterprise_transform_text_form_skill)
  if not all_a2ui_messages:
    full_text = " ".join(
        getattr(p, "text", "") or ""
        for p in parts
        if not getattr(p, "thought", False)
    ).lower()
    explicit_intake_triggers = [
        "intake form",
        "gtm intake",
        "intake card",
        "configure your account narrative",
        "configure your pitch deck parameters",
    ]
    explicit_transform_triggers = [
        "transform slide text",
        "pitchgen-transform-text",
        "text transformer",
    ]
    launcher_greeting_triggers = [
        "welcome to pitchgen",
        "welcome to **pitchgen**",
        "feature launcher",
        "8 capabilities",
        "eight capabilities",
        "interactive launcher",
        "launcher card",
        "launcher hub",
        "ai-powered presentation & visual suite",
    ]
    state = getattr(callback_context, "state", None)
    has_deck_or_outline = False
    last_target_card = ""
    is_greeting_turn = False
    active_pres = ""
    active_cust = ""
    if state is not None:
      if hasattr(state, "get"):
        has_deck_or_outline = bool(
            state.get("deck_url")
            or state.get("proposal_outline")
            or state.get("outline_generated")
            or state.get("deck_generated")
        )
        last_target_card = str(state.get("last_target_card") or "")
        is_greeting_turn = bool(state.get("is_greeting_turn"))
        active_pres = str(
            state.get("deck_url") or state.get("presentation_id") or ""
        )
        active_cust = str(state.get("customer_name") or "")
      elif hasattr(state, "__getitem__"):
        try:
          has_deck_or_outline = bool(
              state.get("deck_url")
              or state.get("proposal_outline")
              or state.get("outline_generated")
              or state.get("deck_generated")
          )
          last_target_card = str(state.get("last_target_card") or "")
          is_greeting_turn = bool(state.get("is_greeting_turn"))
          active_pres = str(
              state.get("deck_url") or state.get("presentation_id") or ""
          )
          active_cust = str(state.get("customer_name") or "")
        except Exception:
          pass

    active_ver = a2ui_util.detect_client_a2ui_version(
        tool_context=callback_context, default_version="v0.9"
    )
    if last_target_card in ("search_slide", "search"):
      surf_id, fallback_search_msgs = _build_search_form_messages(
          callback_context, active_pres, active_cust, ""
      )
      logging.info(
          "[enterprise_after_model_callback] Injecting fallback A2UI Slide"
          " Search input card (%s).",
          surf_id,
      )
      all_a2ui_messages.extend(fallback_search_msgs)
    elif last_target_card == "generate_slide":
      surf_id = _next_card_surface_id(
          callback_context, "pitchgen-generate-slide"
      )
      logging.info(
          "[enterprise_after_model_callback] Injecting fallback A2UI Generate"
          " Single Slide card (%s).",
          surf_id,
      )
      all_a2ui_messages.extend(
          a2ui_util.create_a2ui_generate_slide_messages(
              presentation_url_or_id=active_pres,
              customer_name=active_cust,
              surface_id=surf_id,
          )
      )
    elif last_target_card == "transform_slide":
      surf_id = _next_card_surface_id(
          callback_context, "pitchgen-transform-slide"
      )
      logging.info(
          "[enterprise_after_model_callback] Injecting fallback A2UI Transform"
          " Slide Layout & Content card (%s).",
          surf_id,
      )
      all_a2ui_messages.extend(
          a2ui_util.create_a2ui_transform_messages(
              presentation_url_or_id=active_pres,
              customer_name=active_cust,
              surface_id=surf_id,
          )
      )
    elif last_target_card in (
        "transform_text",
        "transform",
    ) or any(trig in full_text for trig in explicit_transform_triggers):
      surf_id = _next_card_surface_id(
          callback_context, "pitchgen-transform-text"
      )
      logging.info(
          "[enterprise_after_model_callback] Injecting fallback A2UI Transform"
          " Slide Text card (%s).",
          surf_id,
      )
      fallback_transform = a2ui_util.create_a2ui_transform_text_messages(
          presentation_url_or_id=active_pres,
          customer_name=active_cust,
          surface_id=surf_id,
      )
      all_a2ui_messages.extend(fallback_transform)
    elif last_target_card == "translate":
      surf_id = _next_card_surface_id(callback_context, "pitchgen-translate")
      logging.info(
          "[enterprise_after_model_callback] Injecting fallback A2UI Translate"
          " Presentation card (%s).",
          surf_id,
      )
      all_a2ui_messages.extend(
          a2ui_util.create_a2ui_translate_messages(
              presentation_url_or_id=active_pres,
              customer_name=active_cust,
              surface_id=surf_id,
          )
      )
    elif last_target_card in (
        "generate_nanobanana",
        "transform_nanobanana",
        "diagram",
    ):
      nb_mode = (
          "transform"
          if last_target_card == "transform_nanobanana"
          else "generate"
      )
      base_nb_surf = (
          "pitchgen-transform-nanobanana"
          if nb_mode == "transform"
          else "pitchgen-generate-nanobanana"
      )
      surf_id = _next_card_surface_id(callback_context, base_nb_surf)
      logging.info(
          "[enterprise_after_model_callback] Injecting fallback A2UI"
          " NanoBanana card (%s, mode=%s).",
          surf_id,
          nb_mode,
      )
      all_a2ui_messages.extend(
          a2ui_util.create_a2ui_nano_banana_messages(
              presentation_id=active_pres,
              prompt="",
              mode=nb_mode,
              brand_context=active_cust,
              surface_id=surf_id,
          )
      )
    elif last_target_card in ("generate_pitch", "intake") or (
        not has_deck_or_outline
        and any(trig in full_text for trig in explicit_intake_triggers)
    ):
      surf_id = _next_card_surface_id(callback_context, "pitchgen-intake")
      logging.info(
          "[enterprise_after_model_callback] Injecting fallback A2UI GTM Intake"
          " form (%s).",
          surf_id,
      )
      fallback_intake = a2ui_util.create_a2ui_intake_messages(
          surface_id=surf_id, version=active_ver
      )
      all_a2ui_messages.extend(fallback_intake)
    elif (
        not has_deck_or_outline
        and not last_target_card
        and (
            is_greeting_turn
            or any(trig in full_text for trig in launcher_greeting_triggers)
        )
    ):
      surf_id = _next_card_surface_id(callback_context, "pitchgen-launcher")
      logging.info(
          "[enterprise_after_model_callback] Model text indicates"
          " greeting/welcome without tool invocation; auto-injecting fallback"
          " A2UI PitchGen Launcher card (%s).",
          surf_id,
      )
      fallback_launcher = a2ui_util.create_a2ui_launcher_messages(
          surface_id=surf_id, version=active_ver
      )
      all_a2ui_messages.extend(fallback_launcher)

  # Unconditionally clear turn-scoped routing flags once final model response for the turn completes
  if state is not None:
    try:
      state["last_target_card"] = ""
      state["is_greeting_turn"] = False
    except Exception:
      pass

  # 3. Create inline data parts for each message
  # Deduplicate individual messages by serialized JSON
  seen_msg_json = set()
  unique_msgs = []

  def _flatten_msgs(obj: Any) -> None:
    if isinstance(obj, list):
      for sub in obj:
        _flatten_msgs(sub)
    elif isinstance(obj, dict):
      v09_nested = obj.get("a2ui_v09_messages")
      if isinstance(v09_nested, list) and v09_nested:
        for sub in v09_nested:
          _flatten_msgs(sub)
        return
      m_json = json.dumps(obj, sort_keys=True)
      if m_json not in seen_msg_json:
        seen_msg_json.add(m_json)
        unique_msgs.append(obj)

  _flatten_msgs(all_a2ui_messages)

  a2ui_parts = []
  for msg in unique_msgs:
    # Channel B: A2A DataPart envelope (<a2a_datapart_json>) per canonical GCBP framework
    a2ui_parts.append(a2ui_util.create_a2a_part_from_a2ui_payload(msg))

  serialized_msgs = json.dumps(unique_msgs) if a2ui_parts else ""
  if a2ui_parts and (
      "pitchgen-search-results" in serialized_msgs
      or (
          "pitchgen-slide-search" in serialized_msgs
          and "res-card-1" in serialized_msgs
      )
  ):
    deduped_parts = []
    for p in cleaned_parts:
      p_txt = getattr(p, "text", None)
      if p_txt and not getattr(p, "thought", False):
        has_result_list = bool(
            re.search(r"(?:^|\n)\s*(?:1\.|\*|-)\s+\*\*?", p_txt)
            or re.search(
                r"(?:^|\n)\s*1\.\s+\S+.*(?:\n\s*2\.\s+\S+)", p_txt, re.DOTALL
            )
            or p_txt.count("docs.google.com/presentation") >= 1
            or p_txt.count("Insert Slide into Active Deck") >= 2
        )
        if has_result_list:
          lines = p_txt.splitlines()
          intro_lines = []
          for ln in lines:
            stripped_ln = ln.strip()
            if re.match(r"^(?:\d+[\.\)]|\*|-|•)\s+", stripped_ln):
              break
            if "docs.google.com/presentation" in stripped_ln:
              break
            if stripped_ln:
              intro_lines.append(stripped_ln)
          intro_text = " ".join(intro_lines).strip()
          intro_text = re.sub(r"[:—\-]+\s*$", ".", intro_text)
          widget_cta = (
              "Explore the matched slides in the **Slide Search** widget below"
              " to review full descriptions, open source decks, or click"
              " **➕ Insert Slide into Active Deck**."
          )
          if intro_text and len(intro_text) <= 280:
            if (
                "widget below" not in intro_text.lower()
                and "card below" not in intro_text.lower()
            ):
              p_txt = f"{intro_text} {widget_cta}"
            else:
              p_txt = intro_text
          else:
            p_txt = (
                "Here are the top verified slides and customer references"
                f" matching your search. {widget_cta}"
            )
          deduped_parts.append(types.Part(text=p_txt))
        else:
          deduped_parts.append(p)
      else:
        deduped_parts.append(p)
    cleaned_parts = deduped_parts

  if a2ui_parts and not any(
      getattr(p, "text", None) and not getattr(p, "thought", False)
      for p in cleaned_parts
  ):
    if "pitchgen-launcher" in serialized_msgs:
      anchor_text = (
          "Welcome to **PitchGen**! Choose a workflow below or describe your"
          " customer presentation goal in chat to get started."
      )
    elif "pitchgen-intake" in serialized_msgs:
      anchor_text = (
          "Configure your account narrative and pitch deck parameters in the"
          " **GTM Intake Form** below."
      )
    elif "pitchgen-search-results" in serialized_msgs:
      anchor_text = (
          "Explore the matched slides in the **Slide Search results** card"
          " below — click a slide to preview it, then **Insert** it into your"
          " deck."
      )
    elif "pitchgen-slide-search" in serialized_msgs:
      if "res-card-1" in serialized_msgs:
        anchor_text = (
            "Explore the matched slides and customer references in the **Slide"
            " Search** widget below to review full descriptions, open source"
            " decks, or click **➕ Insert Slide into Active Deck**."
        )
      else:
        anchor_text = (
            "Search CloudHub templates and the 2026 Customer Reference Library"
            " in the **Slide Search** card below."
        )
    elif "pitchgen-generate-slide" in serialized_msgs:
      anchor_text = (
          "Configure your slide topic, narrative objective, and optional"
          " target deck in the **Generate a Single Slide** card below."
      )
    elif "pitchgen-transform-slide" in serialized_msgs:
      anchor_text = (
          "Configure your presentation link, slide indices, and transformation"
          " mode in the **Transform Slide Layout & Content** card below."
      )
    elif "pitchgen-transform-text" in serialized_msgs:
      anchor_text = (
          "Configure your presentation link, transformation instructions, and"
          " target audience in the **Transform Slide Text** card below."
      )
    elif "pitchgen-translate" in serialized_msgs:
      anchor_text = (
          "Provide your Google Slides presentation link and target language in"
          " the **Translate Presentation** card below."
      )
    elif "pitchgen-transform-nanobanana" in serialized_msgs:
      anchor_text = (
          "Specify your target presentation slide and brand/visual restyling"
          " instructions in the **Transform Slide Visuals with NanoBanana Pro**"
          " card below."
      )
    elif (
        "pitchgen-generate-nanobanana" in serialized_msgs
        or "pitchgen-nano-banana" in serialized_msgs
    ):
      anchor_text = (
          "Describe your technical architecture or visual and select a style"
          " in the **Generate Architecture & Visuals with NanoBanana Pro** card"
          " below."
      )
    elif "pitchgen-outline" in serialized_msgs:
      anchor_text = (
          "Review and customize your **Proposal Outline** below, then click"
          " **Generate Presentation** when ready."
      )
    else:
      anchor_text = "Here is your interactive PitchGen workspace card below."
    cleaned_parts.append(types.Part(text=anchor_text))

  updated_parts = cleaned_parts + a2ui_parts
  if hasattr(llm_response.content, "parts"):
    llm_response.content.parts = updated_parts

  if a2ui_parts:
    custom_metadata = dict(getattr(llm_response, "custom_metadata", None) or {})
    custom_metadata["a2a:response"] = True

    return llm_response.model_copy(
        update={
            "content": types.Content(
                parts=updated_parts,
                role=llm_response.content.role,
            ),
            "custom_metadata": custom_metadata,
        }
    )

  return llm_response.model_copy(
      update={
          "content": types.Content(
              parts=updated_parts,
              role=llm_response.content.role,
          ),
      }
  )


try:
  from google.adk.planners import built_in_planner

  _enterprise_planner = built_in_planner.BuiltInPlanner(
      thinking_config=types.ThinkingConfig(
          include_thoughts=True,
      )
  )
except Exception:
  _enterprise_planner = None


enterprise_agent = Agent(
    name="pitchgen_deck_creator",
    model=f"projects/{project_id}/locations/{model_region}/publishers/google/models/{model_name}",
    planner=_enterprise_planner,
    description=(
        "PitchGen Agent for creating Google Slides presentations from scratch,"
        " searching reusable slide repositories & verified customer references,"
        " inserting slides into active decks, transforming and polishing"
        " slide text, synthesizing architecture diagrams and visuals,"
        " retrieving VoC & competitive SWOT insights, and translating"
        " presentations inside Gemini Enterprise."
    ),
    instruction=(
        "You are the PitchGen Agent, a Principal Google Cloud Go-To-Market"
        " (GTM) Strategist & Solutions Architect for co-creating, searching,"
        " transforming, and polishing high-impact Google Slides presentations"
        " inside Gemini Enterprise.\n\nCHAIN OF THOUGHT & EXECUTIVE REASONING"
        " PROTOCOL:\n- Your internal thinking steps are visible to the user in"
        " the Gemini Enterprise Thinking UI. Write every thought strictly as a"
        " Principal Google Cloud GTM Strategist: analyze the customer's"
        " industry drivers, CVI narrative arc, relevant Google Cloud sales"
        " plays, verified customer proof points, and technical architecture.\n-"
        " NEVER recite prompt rule numbers, internal function names"
        " ('enterprise_...'), raw JSON arguments ('state_json'), or"
        " angle-bracket template placeholders in your thoughts.\n\nSKILL"
        " CONSULTATION PROTOCOL:\n- Do NOT invoke 'consult_skill' before"
        " calling 'enterprise_create_proposal_outline' or"
        " 'enterprise_slide_generator_skill' — those tools automatically load"
        " and inject all required GTM skills ('cvi_framework',"
        " 'sales_play_selection', 'win_cycle', 'industry_verticals')"
        " internally.\n- Only invoke 'consult_skill' for ad-hoc standalone GTM"
        " framework questions.\n\nEXECUTION CAPABILITIES:\n\n1. GREETINGS &"
        " FEATURE LAUNCHER HUB:\n- Whenever the user greets you ('Hi', 'Hello',"
        " 'Hey', 'Welcome', 'Start', 'Menu', 'Help') or asks what PitchGen can"
        " do without specifying a customer or workflow, invoke"
        " 'enterprise_launcher_card_skill' so the interactive PitchGen"
        " Introduction & Feature Launcher Card ('pitchgen-launcher') renders"
        " immediately.\n- When the user clicks 'Launch Deck Generation'"
        " (target_card='generate_pitch' or 'intake') or asks to open the GTM"
        " intake form without specifying a customer, invoke"
        " 'enterprise_intake_form_skill' to render the GTM Intake Form"
        " ('pitchgen-intake').\n- When the user clicks 'Open Slide Search'"
        " (target_card='search_slide' or 'search') without providing a specific"
        " search query, invoke 'enterprise_search_slides_form_skill' to render"
        " the Slide Search input card ('pitchgen-slide-search').\n- When the"
        " user clicks 'Launch Slide Creator' (target_card='generate_slide')"
        " without providing a slide topic, invoke"
        " 'enterprise_generate_slide_form_skill' to render the Generate a"
        " Single Slide card ('pitchgen-generate-slide').\n- When the user"
        " clicks 'Open Slide Transformer' (target_card='transform_slide')"
        " without providing both a deck URL/ID and instructions, invoke"
        " 'enterprise_transform_slide_form_skill' to render the Transform Slide"
        " Layout & Content card ('pitchgen-transform-slide').\n- When the user"
        " clicks 'Open Text Transformer' (target_card='transform_text' or"
        " 'transform') or asks to open the Transform Slide Text form without"
        " providing both a deck URL/ID and instructions, invoke"
        " 'enterprise_transform_text_form_skill' to render the Transform Slide"
        " Text card ('pitchgen-transform-text').\n- When the user clicks 'Open"
        " Deck Translator' (target_card='translate') without providing a deck"
        " URL/ID, invoke 'enterprise_translate_form_skill' to render the"
        " Translate Presentation card ('pitchgen-translate').\n- When the user"
        " clicks 'Open NanoBanana Generator'"
        " (target_card='generate_nanobanana') without providing a specific"
        " visual prompt, invoke 'enterprise_nano_banana_form_skill' with"
        " mode='generate' to render the Generate Architecture & Visuals with"
        " NanoBanana Pro card ('pitchgen-generate-nanobanana').\n- When the"
        " user clicks 'Open NanoBanana Transformer'"
        " (target_card='transform_nanobanana') without providing a specific"
        " visual prompt, invoke 'enterprise_nano_banana_form_skill' with"
        " mode='transform' to render the Transform Slide Visuals with"
        " NanoBanana Pro card ('pitchgen-transform-nanobanana').\n\n2."
        " GENERATING & REFINING A PITCH DECK OUTLINE:\n- Direct Outline"
        " Creation: When the user requests a new pitch deck or submits the"
        " intake form, immediately invoke 'enterprise_create_proposal_outline'"
        " with their verbatim 'business_context' and extracted account"
        " parameters.\n- Outline Refinement: When the user asks to refine, add,"
        " remove, or reorder sections in the outline, invoke"
        " 'enterprise_refine_proposal_outline' with their"
        " 'refinement_instructions'. Keep your chat summary concise (2-3"
        " sentences highlighting the strategic narrative arc).\n- Deck"
        " Generation: Once the user approves the outline, invoke"
        " 'enterprise_slide_generator_skill'. Return the tool's markdown"
        " summary highlighting the active customer name, the user's LDAP,"
        " Gemini Enterprise quick refinements (Search Slides, Transform Slide"
        " Text, Generate Visuals), and the clickable Google Slides URL.\n-"
        " STRICT IN-PLACE CANVAS GUARDRAIL: Once a presentation is active on"
        " Canvas (or showcased in the iframe), NEVER invoke"
        " 'enterprise_slide_generator_skill' or"
        " 'enterprise_create_proposal_outline' when the user asks to search"
        " slides, insert slides, transform/polish slide text, generate visuals,"
        " or translate slides. Always mutate the existing active presentation"
        " in-place using 'enterprise_search_slides_skill',"
        " 'enterprise_insert_slide_skill',"
        " 'enterprise_transform_slide_text_skill',"
        " 'enterprise_generate_visuals_skill', or"
        " 'enterprise_translate_deck_skill'.\n\n3. SEARCHING CUSTOMER"
        " REFERENCES, CASE STUDIES & REUSABLE SLIDES:\n- Whenever the user asks"
        " to search for customer references, case studies, proof points, peer"
        " stories, reusable slides, or architecture templates with a specific"
        " query (or submits the Slide Search card), immediately invoke"
        " 'enterprise_search_slides_skill'.\n- For customer reference / case"
        " study queries, pass slide_job='Proof_Points' so the 2026 Consolidated"
        " Customer Reference Library and Golden Gate verified stories are"
        " queried alongside CloudHub.\n- A2UI WIDGET-FIRST PRESENTATION (NO"
        " DUPLICATE CHAT LISTS): All matched slides, slide titles, linked"
        " source deck titles, and full descriptions are rendered directly"
        " inside the interactive 'pitchgen-slide-search' A2UI widget. Keep your"
        " chat response to ONLY 1-2 concise sentences introducing the search"
        " results in the Slide Search widget below and noting that the user can"
        " click '➕ Insert Slide into Active Deck' on any card. NEVER output a"
        " numbered or bulleted list of individual slides or URLs in chat.\n\n4."
        " INSERTING A LIBRARY SLIDE INTO"
        " THE ACTIVE PRESENTATION:\n- When the user asks to insert one of the"
        " searched slides into their active deck (or clicks '➕ Insert Slide"
        " into Active Deck'), invoke 'enterprise_insert_slide_skill'. It"
        " automatically targets the active presentation on Canvas and links the"
        " source slide.\n\n5. TRANSFORMING / POLISHING EXISTING SLIDES OR RAW"
        " TEXT:\n- In-Deck Transformation: When the user asks to polish,"
        " rewrite, customize, or adjust the tone of slides in the active"
        " presentation (or provides a Google Slides URL/ID), invoke"
        " 'enterprise_transform_slide_text_skill'. If no URL is provided, it"
        " automatically transforms the active presentation on Canvas.\n- Raw"
        " Text / Bullet Copy Transformation: When the user pastes raw text or"
        " bullets in chat to polish, invoke 'transform_raw_text_skill'.\n\n6."
        " GENERATING ARCHITECTURE DIAGRAMS & NANO BANANA VISUALS:\n- When the"
        " user asks to generate visuals, architecture diagrams, topologies, or"
        " Nano Banana illustrations with a specific prompt, invoke"
        " 'enterprise_generate_visuals_skill'. It synthesizes a 2K diagram,"
        " inserts it into the active presentation when available, and provides"
        " a preview card.\n\n7. TRANSLATING A PRESENTATION:\n- When the user"
        " asks to translate the active presentation (or a provided presentation"
        " link/ID) into another language, invoke"
        " 'enterprise_translate_deck_skill'.\n\n8. CUSTOMER INSIGHTS, VoC &"
        " COMPETITIVE SWOT:\n- When the user asks for Voice of the Customer"
        " (VoC) feedback, EBC engagement insights, competitive SWOT (vs. AWS,"
        " Azure, Snowflake, Databricks), or account intelligence, invoke"
        " 'enterprise_customer_insights_skill'.\n\n9. WHITE-GLOVE PROPOSAL &"
        " RFP SUPPORT:\n- For bespoke human designer help, invoke"
        " 'phub_handoff_skill'. For formal RFP/RFI questionnaire automation,"
        " invoke 'rfp_accelerator_skill'.\n\nCRITICAL USER-FACING RULES:\n-"
        " NEVER output <a2a_datapart_json>, </a2a_datapart_json>, <a2ui-json>,"
        " or </a2ui-json> tags or raw A2UI JSON in your text response.\n- Never"
        " print raw GCS URIs (gs://...) or intermediate JSON filenames.\n"
    ),
    before_agent_callback=identity_resolution_callback,
    before_model_callback=enterprise_before_model_callback,
    after_tool_callback=enterprise_after_tool_callback,
    after_model_callback=enterprise_after_model_callback,
    tools=[
        enterprise_launcher_card_skill,
        enterprise_intake_form_skill,
        enterprise_search_slides_form_skill,
        enterprise_generate_slide_form_skill,
        enterprise_transform_slide_form_skill,
        enterprise_transform_text_form_skill,
        enterprise_nano_banana_form_skill,
        enterprise_translate_form_skill,
        PitchGenSkills.consult_skill,
        enterprise_create_proposal_outline,
        enterprise_refine_proposal_outline,
        enterprise_slide_generator_skill,
        enterprise_search_slides_skill,
        enterprise_insert_slide_skill,
        PitchGenSkills.sidebar_generate,
        enterprise_transform_slide_text_skill,
        enterprise_generate_visuals_skill,
        PitchGenSkills.transform_raw_text_skill,
        enterprise_translate_deck_skill,
        enterprise_customer_insights_skill,
        GTMSkills.phub_handoff_skill,
        GTMSkills.rfp_accelerator_skill,
        PitchGenSkills.submit_authorization_code,
    ],
)

root_agent = enterprise_agent
app = App(root_agent=enterprise_agent, name="src")
