"""Deck Generation Service.

Dedicated workflow for Phase 1 (Proposal Outline Generation) and
Phase 2 (Deck Generation: Content Synthesis, Slide Layout Mapping & Apps Script
Assembly).
"""

import ast
import datetime
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
from oauth_helper import (
    get_adc_bearer_token,
    get_enduser_bearer_token,
    get_user_access_token,
    resolve_user_ldap,
)
from pitchgen_utils.gcs_util import write_gcs_file
from state import GlobalState
from agents.agenda_agent import AgendaAgent
from agents.retrieval_agent import RetrievalAgent
from orchestrators.creative_orchestrator import CreativeOrchestrator


def robust_json_loads(s: Any) -> dict:
  """Robust JSON parsing with fallback for single quotes and malformed LLM outputs."""
  if isinstance(s, dict):
    return s
  if not isinstance(s, str):
    return {}
  s = s.strip()
  open_braces = s.count("{")
  close_braces = s.count("}")
  if open_braces > close_braces:
    s += "}" * (open_braces - close_braces)

  try:
    return json.loads(s)
  except Exception:
    pass

  try:
    temp = s
    temp = re.sub(r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)", r"\1'\2'\3", temp)
    return ast.literal_eval(temp)
  except Exception as e:
    try:
      fallback_str = s.replace("'", '"')
      fallback_str = re.sub(
          r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)", r'\1"\2"\3', fallback_str
      )
      return json.loads(fallback_str)
    except Exception:
      raise e


def call_apps_script_to_create_deck(
    outputs_gcs_url: str,
    architectural_gcs_url: str,
    user_ldap: str,
    user_oauth_token: str = None,
    context: dict = None,
    tool_context=None,
) -> str:
  """Creates presentation deck using Apps Script Web App endpoint."""
  user_ldap = resolve_user_ldap(user_ldap, tool_context=tool_context)

  try:
    config = load_config()
    url = config.get("appscript", "url")
  except Exception:
    url = "https://script.google.com/macros/s/YOUR_APPS_SCRIPT_DEPLOYMENT_ID/exec"

  payload = {
      "outputs_filename": outputs_gcs_url,
      "architectural_filename": architectural_gcs_url,
      "user_ldap": user_ldap,
  }
  if context and isinstance(context, dict):
    payload["context"] = context
    if "customer_name" in context and context["customer_name"]:
      payload["customer_name"] = context["customer_name"]
    if "industry" in context and context["industry"]:
      payload["industry"] = context["industry"]
    if "business_context" in context and context["business_context"]:
      payload["business_context"] = context["business_context"]
    if "audience" in context and context["audience"]:
      payload["audience"] = (
          ", ".join(context["audience"])
          if isinstance(context["audience"], list)
          else str(context["audience"])
      )
    if "salesPlay" in context and context["salesPlay"]:
      payload["salesPlay"] = (
          ", ".join(context["salesPlay"])
          if isinstance(context["salesPlay"], list)
          else str(context["salesPlay"])
      )
    if (
        "er_number" in context
        and context["er_number"]
        and str(context["er_number"]).strip() != "21212"
    ):
      payload["er_number"] = str(context["er_number"]).strip()
    else:
      payload["er_number"] = ""

  print(
      "[DeckGenerationService] Calling Apps Script Web App endpoint for user"
      f" '{user_ldap}' at {url}...",
      flush=True,
  )

  try:

    class AuthPreservingSession(requests.Session):

      def rebuild_auth(self, prepared_request, response):
        if "Authorization" in response.request.headers:
          prepared_request.headers["Authorization"] = response.request.headers[
              "Authorization"
          ]

    session = AuthPreservingSession()

    # 1. Attempt 1: Try Short-Lived Access Token first (from header or GCS access_token)
    header_token = get_enduser_bearer_token(tool_context=tool_context)
    short_lived_token = user_oauth_token or header_token

    if short_lived_token:
      print(
          "[DeckGenerationService] 🔑 ATTEMPT 1: Trying Short-Lived Access"
          f" Token for '{user_ldap}' (Length: {len(short_lived_token)})...",
          flush=True,
      )
      headers = {
          "Authorization": f"Bearer {short_lived_token}",
          "Content-Type": "application/json",
      }
      response = session.post(url, headers=headers, json=payload, timeout=300)
      if response.status_code == 200 and not response.text.startswith(
          "<!DOCTYPE html>"
      ):
        print(
            "[DeckGenerationService] 🎉 ATTEMPT 1 SUCCESS! Apps Script"
            f" Response: {response.text}",
            flush=True,
        )
        try:
          resp_json = response.json()
          if "deckURL" in resp_json:
            return resp_json["deckURL"]
        except Exception:
          pass
        return response.text.strip()
      print(
          "[DeckGenerationService] ⚠️ ATTEMPT 1 FAILED (Status:"
          f" {response.status_code}). Falling back to Long-Lived Refresh"
          " Token...",
          flush=True,
      )

    # 2. Attempt 2: Fallback to Long-Lived Refresh Token (1//...) in GCS
    long_lived_token = get_user_access_token(user_ldap)
    if long_lived_token:
      print(
          "[DeckGenerationService] 🔄 ATTEMPT 2: Minted fresh access token via"
          f" Long-Lived Refresh Token in GCS for '{user_ldap}'...",
          flush=True,
      )
      headers = {
          "Authorization": f"Bearer {long_lived_token}",
          "Content-Type": "application/json",
      }
      response = session.post(url, headers=headers, json=payload, timeout=300)
      if response.status_code == 200 and not response.text.startswith(
          "<!DOCTYPE html>"
      ):
        print(
            "[DeckGenerationService] 🎉 ATTEMPT 2 SUCCESS! Apps Script"
            f" Response: {response.text}",
            flush=True,
        )
        try:
          resp_json = response.json()
          if "deckURL" in resp_json:
            return resp_json["deckURL"]
        except Exception:
          pass
        return response.text.strip()
      print(
          "[DeckGenerationService] ⚠️ ATTEMPT 2 FAILED (Status:"
          f" {response.status_code}). Falling back to ADC token...",
          flush=True,
      )

    # 3. Attempt 3: Final Fallback to ADC Bearer Token
    adc_token = get_adc_bearer_token()
    print(
        "[DeckGenerationService] 🛡️ ATTEMPT 3: Using Fallback ADC Bearer Token"
        f" for '{user_ldap}'...",
        flush=True,
    )
    headers = {
        "Authorization": f"Bearer {adc_token}",
        "Content-Type": "application/json",
    }
    response = session.post(url, headers=headers, json=payload, timeout=300)

    if response.status_code == 200 and not response.text.startswith(
        "<!DOCTYPE html>"
    ):
      print(
          "[DeckGenerationService] 🎉 ATTEMPT 3 SUCCESS! Apps Script Response:"
          f" {response.text}",
          flush=True,
      )
      try:
        resp_json = response.json()
        if "deckURL" in resp_json:
          return resp_json["deckURL"]
      except Exception:
        pass
      return response.text.strip()

    # Retry clean headers if HTML login redirect
    clean_headers = {"Content-Type": "application/json"}
    response = session.post(
        url, headers=clean_headers, json=payload, timeout=300
    )
    if response.status_code == 200 and not response.text.startswith(
        "<!DOCTYPE html>"
    ):
      try:
        resp_json = response.json()
        if "deckURL" in resp_json:
          return resp_json["deckURL"]
      except Exception:
        pass
      return response.text.strip()

    print(
        "[DeckGenerationService] ❌ APPS SCRIPT FAILURE! HTTP"
        f" {response.status_code} Response: {response.text[:500]}",
        flush=True,
    )
    return f"Error: Apps Script returned status {response.status_code}"
  except Exception as e:
    print(
        "[DeckGenerationService] ❌ CRITICAL HTTP ERROR calling Apps Script"
        f" for '{user_ldap}': {e}",
        flush=True,
    )
    return f"Error: Failed to connect to Apps Script: {str(e)}"


class DeckGenerationService:
  """Dedicated, self-contained service for Phase 1 & Phase 2 Google Slides generation."""

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
      print(f"[DeckGenerationService] Token exchange failed for {user_ldap}:")
      traceback.print_exc()
      return f"Error: Authorization failed: {str(e)}"

  @staticmethod
  def create_proposal_outline(
      business_context: str,
      customer_name: str = "",
      industry: str = "",
      solution: str = "",
      user_ldap: str = "",
      er_number: str = "",
      audience: str = "",
      region: str = "",
      product: str = "",
      request_type: str = "",
      presentation_id: str = "",
      salesPlay: str = "",
      user_input_id: str = "",
      sub_industry: str = "",
      deck_strategy: str = "smart_hybrid",
      tool_context=None,
  ) -> str:
    """Phase 1: Generates the initial outline and agendas for creating a BRAND-NEW presentation deck from scratch.

    CRITICAL: Use this tool ONLY when the user asks to create/generate a new
    presentation deck from scratch. Do NOT call this tool when transforming,
    translating, or editing an existing presentation deck.

    Args:
        business_context: The business context or goal for the pitch.
        customer_name: The name of the target customer (e.g., 'Acme Corp').
        industry: The industry of the customer.
        solution: The proposed solutions or products, separated by commas.
        user_ldap: LDAP of the user.
        er_number: Opportunity ER number.
        audience: Target audience list, comma separated.
        region: Target region.
        product: Specific Google products list, comma separated.
        request_type: Request type (e.g., 'Full Deck').
        presentation_id: Active Slides Presentation ID.
        salesPlay: Name of the Sales Play if applicable.
        user_input_id: Unique generated session ID.
        sub_industry: Sub-industry name if applicable.

    Returns:
        A serialized GlobalState JSON string containing outline and agendas.
    """
    print(
        "[DeckGenerationService] Generating outline for customer:"
        f" '{customer_name}'..."
    )
    if not user_ldap and tool_context and hasattr(tool_context, "user_id"):
      user_ldap = str(tool_context.user_id or "").strip()
      print(
          "[DeckGenerationService] Extracted user_id from ADK ToolContext:"
          f" {user_ldap}"
      )

    user_ldap = resolve_user_ldap(user_ldap, tool_context=tool_context)

    # Silently capture incoming bearer token to GCS in the background during Phase 1
    try:
      get_enduser_bearer_token(tool_context=tool_context)
    except Exception as t_err:
      print(
          f"[DeckGenerationService] Background token capture notice: {t_err}",
          flush=True,
      )

    print(
        "[DeckGenerationService] 🚀 Phase 1: Generating outline"
        f" unconditionally for user '{user_ldap}'...",
        flush=True,
    )

    if not user_input_id or user_input_id == "":
      user_input_id = str(uuid.uuid4())

    solution_list = (
        [s.strip() for s in solution.split(",") if s.strip()]
        if solution
        else []
    )

    if isinstance(salesPlay, list):
      sales_play_list = salesPlay
    elif isinstance(salesPlay, str):
      sales_play_list = (
          [p.strip() for p in salesPlay.split(",") if p.strip()]
          if salesPlay
          else []
      )
    else:
      sales_play_list = []

    initial_context = {
        "customer_name": customer_name,
        "business_context": business_context,
        "industry": industry,
        "sub_industry": sub_industry,
        "solution": solution_list,
        "visuals_requested": True,
        "user_ldap": user_ldap,
        "er_number": er_number,
        "audience": audience.split(",") if audience else [],
        "region": region,
        "product": product.split(",") if product else [],
        "request_type": request_type,
        "presentation_id": presentation_id,
        "salesPlay": sales_play_list,
        "user_input_id": user_input_id,
        "deck_strategy": deck_strategy or "smart_hybrid",
    }

    try:
      config = load_config()
      state = GlobalState()
      state.context = initial_context
      agenda_agent = AgendaAgent(config)
      state = agenda_agent.run(state)

      # Generate GCS URL for outline
      bucket_name = config.get(
          "bucket", "content", fallback="your-pitchgen-content-bucket"
      )
      timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
      if er_number:
        filename_str = f"outline_{er_number}_{timestamp}.json"
      else:
        filename_str = f"outline_no_er_{user_input_id}_{timestamp}.json"
      gcs_url = f"gs://{bucket_name}/{filename_str}"

      # Write raw outline JSON to GCS
      try:
        write_gcs_file(gcs_url, state.to_json())
        print(
            "[DeckGenerationService] Successfully uploaded outline to GCS:"
            f" {gcs_url}"
        )
      except Exception as gcse:
        print(
            "[DeckGenerationService] Warning: Failed to upload outline to GCS:"
            f" {gcse}"
        )

      state_dict = json.loads(state.to_json())
      state_dict["filename"] = gcs_url
      wrapped_response = {
          "Status": "True",
          "data": state_dict,
          "message": "Success",
      }
      return json.dumps(wrapped_response, indent=2)
    except Exception as e:
      print(f"[DeckGenerationService] Error in create_proposal_outline: {e}")
      return json.dumps({"error": str(e)})

  @staticmethod
  def slide_generator_skill(state_json: str, tool_context=None) -> str:
    """Phase 2: Generates the final deck structure (content synthesis & slide mapping)

    based on the approved GlobalState and calls Apps Script to create the Google
    Slides presentation.

    Args:
        state_json: Serialized GlobalState JSON string containing approved
          agendas.

    Returns:
        A serialized JSON string with deck_url and final deck metadata.
    """
    print(
        "[DeckGenerationService] Phase 2: Generating final deck from state..."
    )
    config = load_config()

    try:
      if isinstance(state_json, dict):
        state_data = state_json
      else:
        cleaned_str = str(state_json).strip()
        if cleaned_str.startswith("```"):
          cleaned_str = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned_str)
          cleaned_str = re.sub(r"\n?```$", "", cleaned_str).strip()
        state_data = robust_json_loads(cleaned_str)

      if (
          isinstance(state_data, dict)
          and "Status" in state_data
          and "data" in state_data
      ):
        state_data = state_data["data"]

      state = GlobalState()
      if isinstance(state_data, dict):
        state.__dict__.update(state_data)
      state._normalize()

      # 1. Resolve User LDAP and OAuth token
      user_ldap = state.context.get("user_ldap", "")
      if not user_ldap and tool_context and hasattr(tool_context, "user_id"):
        user_ldap = str(tool_context.user_id or "").strip()
      user_ldap = resolve_user_ldap(user_ldap, tool_context=tool_context)
      state.context["user_ldap"] = user_ldap

      user_oauth_token = state.context.get(
          "user_oauth_token", ""
      ) or get_enduser_bearer_token(tool_context=tool_context)
      token = user_oauth_token
      if not token or token.strip() == "":
        token = get_user_access_token(user_ldap)

      if not token or token.strip() == "":
        try:
          token = get_adc_bearer_token()
          print(
              "[DeckGenerationService] Pre-check: Silent ADC token resolved"
              f" for user {user_ldap}."
          )
        except Exception as adc_err:
          print(
              "[DeckGenerationService] Pre-check warning: Could not resolve"
              f" ADC token: {adc_err}"
          )

      # 2. Execute Retrieval and Creative Generation
      retrieval_agent = RetrievalAgent(config)
      state = retrieval_agent.run(state)
      creative_orch = CreativeOrchestrator(config)
      final_state = creative_orch.run(state)

      # 3. Generate GCS Filenames & URLs
      bucket_name = config.get(
          "bucket", "content", fallback="your-pitchgen-content-bucket"
      )
      timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
      er_number = final_state.context.get("er_number") or ""

      outputs_filename = (
          f"{er_number}_{timestamp}.json"
          if er_number
          else f"outputs_{timestamp}.json"
      )
      architectural_filename = (
          f"architectural_{er_number}_{timestamp}.json"
          if er_number
          else f"architectural_{timestamp}.json"
      )

      gsurl_outputs = f"gs://{bucket_name}/{outputs_filename}"
      gsurl_architectural = f"gs://{bucket_name}/{architectural_filename}"

      # Upload architectural data and outputs data to GCS
      try:
        write_gcs_file(
            gsurl_architectural, json.dumps(final_state.reusable_slides or {})
        )
        outputs_data = {
            "context": final_state.context or {},
            "sections": final_state.final_deck_structure or {},
        }
        write_gcs_file(gsurl_outputs, json.dumps(outputs_data))
        print(
            "[DeckGenerationService] Successfully uploaded architectural and"
            " outputs to GCS."
        )
      except Exception as gcse:
        print(
            "[DeckGenerationService] Warning: Failed to upload Phase 2 outputs"
            f" to GCS: {gcse}"
        )

      # 4. Call Apps Script to create the deck
      deck_url = call_apps_script_to_create_deck(
          outputs_gcs_url=gsurl_outputs,
          architectural_gcs_url=gsurl_architectural,
          user_ldap=user_ldap,
          user_oauth_token=token,
          context=final_state.context or {},
          tool_context=tool_context,
      )

      wrapped_response = {
          "status": (
              "success"
              if not deck_url.startswith("Error")
              and not deck_url.startswith("Auth Error")
              else "failure"
          ),
          "deck_url": deck_url,
          "architectural_filename": architectural_filename,
          "outputs_filename": outputs_filename,
          "gsurl_architectural": gsurl_architectural,
          "gsurl_outputs": gsurl_outputs,
      }
      return json.dumps(wrapped_response, indent=2)
    except Exception as e:
      print(f"[DeckGenerationService] Error in slide_generator_skill: {e}")
      return json.dumps({"error": str(e)})
