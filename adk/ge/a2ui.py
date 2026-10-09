"""Gemini Enterprise A2UI (Agent-to-User Interface) & Canvas Panel Utilities.

This module formats structured A2UI cards and Canvas side-panel payloads for
Gemini Enterprise, adhering to:
- A2UI wire protocol ('application/json+a2ui')
- UCS Widget Canvas Panel (WS_SLIDES / embedded presentation iframe)
- Interactive Quick Actions (tone adjustment, proof points, translation)
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

A2UI_MIME_TYPE = "application/json+a2ui"
A2UI_URI_V08 = "https://a2ui.org/a2a-extension/a2ui/v0.8"
A2UI_URI_V09 = "https://a2ui.org/a2a-extension/a2ui/v0.9"
A2UI_GE_CUSTOM_CATALOG_ID = (
    "https://a2ui.org/specification/v0_9/ge_custom_catalog.json"
)

# Standard A2UI Catalogs from GCBP & A2UI v0.9 specs
A2UI_GE_COMPOSITE_CATALOG_ID = (
    "https://a2ui.org/specification/v0_9/material_catalog.json"
)
A2UI_BASIC_CATALOG_ID = "https://a2ui.org/specification/v0_9/basic_catalog.json"
A2UI_MATERIAL_CATALOG_ID = (
    "https://a2ui.org/specification/v0_9/material_catalog.json"
)
A2UI_OHARA_CATALOG_ID = "https://ohara.corp.google.com/a2ui/v0_9/catalog.json"

# PitchGen brand logo (inline SVG data URI, shared with the A2UI-GE branch).
PITCHGEN_TOOL_LOGO_URL = (
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg'"
    " width='206' height='52' viewBox='0 0 206 52'><rect x='0' y='0'"
    " width='206' height='52' rx='14' fill='rgb(232,240,254)'/><g"
    " transform='translate(8,3)'><rect x='6' y='7' width='46'"
    " height='32' rx='7' transform='rotate(8 29 23)'"
    " fill='rgb(138,154,242)'/><rect x='4' y='7' width='50'"
    " height='32' rx='8' fill='rgb(74,104,238)'/><rect x='9' y='12'"
    " width='40' height='22' rx='4' fill='rgb(238,243,255)'/><rect"
    " x='14' y='16' width='4.5' height='14' rx='1'"
    " fill='rgb(62,98,232)'/><rect x='22' y='17' width='17'"
    " height='3.5' rx='1' fill='rgb(71,104,235)'/><rect x='21.5'"
    " y='23' width='12.5' height='7' rx='1'"
    " fill='rgb(92,122,242)'/><rect x='36' y='23' width='5.5'"
    " height='7' rx='1' fill='rgb(77,111,240)'/><text x='66' y='32'"
    " font-family='Google Sans, Roboto, Arial, sans-serif'"
    " font-size='27' font-weight='700'"
    " fill='rgb(32,33,36)'>Pitch<tspan"
    " fill='rgb(37,99,235)'>Gen</tspan></text></g></svg>"
)


def pitchgen_logo_components(
    logo_id: str = "pitchgen_tool_logo",
) -> List[Dict[str, Any]]:
  """Returns the native Material PitchGen brand pill (icon + 'Pitch' + 'Gen').

  GE's Material catalog renderer (`MaterialSecurityService.sanitizeImageUrl`)
  only loads https images from trusted Google CDN domains and blocks `data:`
  URIs, so the inline SVG logo (PITCHGEN_TOOL_LOGO_URL) renders blank there.
  This pill reproduces the logo with MaterialIcon + MaterialText, which always
  renders. The caller must place `logo_id` as a child of its own row.
  """
  font = "'Google Sans', Roboto, Arial, sans-serif"
  word_style = {
      "fontFamily": font,
      "fontSize": "26px",
      "fontWeight": "700",
      "lineHeight": "1.1",
      "margin": "0",
      "width": "auto",
      "whiteSpace": "nowrap",
  }
  return [
      {
          "id": logo_id,
          "component": "MaterialRow",
          "justify": "center",
          "align": "center",
          "style": {
              "display": "inline-flex",
              "minWidth": "0",
              "width": "fit-content",
              "backgroundColor": "var(--mat-sys-primary-container, #e8f0fe)",
              "borderRadius": "14px",
              "padding": "10px 22px",
              "gap": "12px",
              "alignItems": "center",
              "justifyContent": "center",
          },
          "children": ["pitchgen_logo_icon", "pitchgen_logo_text_row"],
      },
      {
          "id": "pitchgen_logo_icon",
          "component": "MaterialIcon",
          "icon": "view_quilt",
          "color": "primary",
          "style": {
              "display": "inline-flex",
              "alignItems": "center",
              "justifyContent": "center",
              "width": "42px",
              "height": "30px",
              "minWidth": "42px",
              "borderRadius": "8px",
              "backgroundColor": "#4a68ee",
              "color": "#eef3ff",
              "fontSize": "22px",
              "boxShadow": "3px -3px 0px #8a9af2",
          },
      },
      {
          "id": "pitchgen_logo_text_row",
          "component": "MaterialRow",
          "justify": "start",
          "align": "center",
          "style": {
              "display": "inline-flex",
              "minWidth": "0",
              "width": "fit-content",
              "gap": "0px",
              "alignItems": "baseline",
          },
          "children": ["pitchgen_logo_pitch", "pitchgen_logo_gen"],
      },
      {
          "id": "pitchgen_logo_pitch",
          "component": "MaterialText",
          "usageHint": "h2",
          "text": "Pitch",
          "style": {
              **word_style,
              "color": "var(--mat-sys-on-surface, #202124)",
          },
      },
      {
          "id": "pitchgen_logo_gen",
          "component": "MaterialText",
          "usageHint": "h2",
          "text": "Gen",
          "style": {**word_style, "color": "var(--mat-sys-primary, #2563eb)"},
      },
  ]


def material_header_icon(component_id: str, icon: str) -> Dict[str, Any]:
  """Returns a tinted 40px MaterialIcon badge matching the launcher tiles."""
  return {
      "id": component_id,
      "component": "MaterialIcon",
      "icon": icon,
      "color": "primary",
      "style": {
          "display": "flex",
          "alignItems": "center",
          "justifyContent": "center",
          "width": "40px",
          "height": "40px",
          "minWidth": "40px",
          "borderRadius": "10px",
          "backgroundColor": "var(--mat-sys-primary-container, #e8f0fe)",
          "color": "var(--mat-sys-on-primary-container, #0b57d0)",
          "fontSize": "22px",
      },
  }


# A2A DataPart Delimiters per GCBP A2UI Framework
A2A_DATA_PART_START_TAG = "<a2a_datapart_json>"
A2A_DATA_PART_END_TAG = "</a2a_datapart_json>"


def get_email_from_oauth_token(access_token: str) -> Optional[str]:
  """Exchanges a Gemini Enterprise OAuth access token for user email via Google OAuth2 UserInfo API.

  Args:
      access_token: OAuth 2.0 Bearer token provided by Gemini Enterprise or
        client.

  Returns:
      User email string if exchange succeeds, else None.
  """
  if not access_token or not isinstance(access_token, str):
    return None

  clean_token = access_token.strip()
  if clean_token.lower().startswith("bearer "):
    clean_token = clean_token[7:].strip()
  if not clean_token:
    return None

  # Attempt 1: Using googleapiclient & Credentials
  try:
    from google.oauth2.credentials import Credentials  # pylint: disable=g-import-not-at-top
    from googleapiclient.discovery import build  # pylint: disable=g-import-not-at-top

    credentials = Credentials(token=clean_token)
    service = build(
        "oauth2", "v2", credentials=credentials, cache_discovery=False
    )
    user_info = service.userinfo().get().execute()
    email = user_info.get("email")
    if email and "@" in str(email):
      return str(email).strip().lower()
  except Exception:
    pass

  # Attempt 2: Direct HTTPS call to userinfo endpoint
  try:
    import urllib.request  # pylint: disable=g-import-not-at-top

    req = urllib.request.Request(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {clean_token}"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
      if resp.status == 200:
        data = json.loads(resp.read().decode("utf-8"))
        email = data.get("email")
        if email and "@" in str(email):
          return str(email).strip().lower()
  except Exception:
    pass

  return None


def resolve_ge_user_identity(
    tool_context: Any = None,
    access_token: Optional[str] = None,
    fallback_ldap: str = "",
) -> tuple[str, str]:
  """Resolves userEmail and derived user_ldap from GE OAuth token, context, or session state.

  Populates resolved values back into tool_context.state for downstream tools.

  Args:
      tool_context: ADK ToolContext or session context object.
      access_token: Optional explicit OAuth token string.
      fallback_ldap: Default LDAP to return if resolution yields no email.

  Returns:
      Tuple of (user_email, user_ldap).
  """
  token = access_token
  state_obj = getattr(tool_context, "state", None) if tool_context else None

  # 1. Check cached values on state if available
  if isinstance(state_obj, dict):
    cached_email = state_obj.get("user_email")
    cached_ldap = state_obj.get("user_ldap")
    if cached_email and cached_ldap:
      return str(cached_email), str(cached_ldap)
    if not token:
      ge_auth_id = os.environ.get("GE_AUTH_ID", "ge_oauth_token")
      token = (
          state_obj.get("oauth_access_token")
          or state_obj.get("user_oauth_token")
          or state_obj.get("bearer_token")
          or state_obj.get(ge_auth_id)
          or state_obj.get("token")
      )

  # 2. Extract from context attributes if still no token
  if not token and tool_context:
    for attr in ["oauth_token", "access_token", "bearer_token"]:
      val = getattr(tool_context, attr, None)
      if val and isinstance(val, str):
        token = val
        break

  # 3. If token found, exchange for email via OAuth2 UserInfo API
  if token and isinstance(token, str):
    exchanged_email = get_email_from_oauth_token(token)
    if exchanged_email:
      ldap = exchanged_email.split("@")[0].lower()
      if isinstance(state_obj, dict):
        state_obj["user_email"] = exchanged_email
        state_obj["user_ldap"] = ldap
        state_obj["oauth_access_token"] = token
      return exchanged_email, ldap

  # 4. Fallback to candidate email/ldap strings on context/session
  candidates = []
  if tool_context:
    for attr in ["user_email", "userEmail", "user_id", "email"]:
      val = getattr(tool_context, attr, None)
      if val and isinstance(val, str) and "@" in val:
        candidates.append(val.strip().lower())

    inv_ctx = getattr(tool_context, "_invocation_context", None) or getattr(
        tool_context, "invocation_context", None
    )
    if inv_ctx:
      for attr in ["user_email", "userEmail", "user_id", "email"]:
        val = getattr(inv_ctx, attr, None)
        if val and isinstance(val, str) and "@" in val:
          candidates.append(val.strip().lower())

    session_obj = getattr(tool_context, "session", None) or getattr(
        tool_context, "_session", None
    )
    if session_obj:
      if isinstance(session_obj, dict):
        val = (
            session_obj.get("userEmail")
            or session_obj.get("user_email")
            or session_obj.get("user_id")
        )
        if val and isinstance(val, str) and "@" in val:
          candidates.append(val.strip().lower())
      else:
        for attr in ["user_email", "userEmail", "user_id", "email"]:
          val = getattr(session_obj, attr, None)
          if val and isinstance(val, str) and "@" in val:
            candidates.append(val.strip().lower())

  if candidates:
    email = candidates[0]
    ldap = email.split("@")[0].lower()
    if isinstance(state_obj, dict):
      state_obj["user_email"] = email
      state_obj["user_ldap"] = ldap
    return email, ldap

  final_ldap = (
      fallback_ldap or os.environ.get("USER") or os.environ.get("USER_LDAP", "")
  )
  final_email = (
      f"{final_ldap}@example.com"
      if final_ldap and "@" not in final_ldap
      else final_ldap
  )
  return final_email, final_ldap


def extract_presentation_id(url: str) -> Optional[str]:
  """Extracts the Google Slides presentation ID from a URL or raw ID string."""
  if not url or not isinstance(url, str):
    return None
  clean = url.strip()
  if clean.startswith("pitchgen-deck-"):
    clean = clean[len("pitchgen-deck-") :].strip()
  match = re.search(r"/presentation/d/([a-zA-Z0-9_-]+)", clean)
  if match:
    return match.group(1)
  match_file = re.search(r"/file/d/([a-zA-Z0-9_-]+)", clean)
  if match_file:
    return match_file.group(1)
  match_open = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", clean)
  if match_open:
    return match_open.group(1)
  if (
      "/" not in clean
      and re.match(r"^[a-zA-Z0-9_-]{6,60}$", clean)
      and not re.match(r"^[a-z_-]+$", clean)
      and clean.lower()
      not in (
          "active",
          "current",
          "current_deck",
          "active_deck",
          "this_deck",
          "none",
          "null",
          "default",
          "canvas",
          "iframe",
      )
      and not clean.lower().startswith((
          "start_of_user_uploaded",
          "end_of_user_uploaded",
          "enterprise_",
          "pitchgen_",
      ))
  ):
    return clean
  return None


def to_canvas_embed_url(deck_url: str) -> str:
  """Converts a Google Slides presentation URL to the embedded iframe format.

  Suitable for rendering directly in the Gemini Enterprise UCS Canvas side panel
  (<ucs-canvas-panel>).
  """
  pres_id = extract_presentation_id(deck_url)
  if not pres_id:
    return deck_url
  return f"https://docs.google.com/presentation/d/{pres_id}/embed?start=false&loop=false&delayms=3000"


def validate_card_icon(icon: str, default: str = "slideshow") -> str:
  """Validates Material Symbols token per GCBP A2UI Canvas specification."""
  if (
      icon
      and isinstance(icon, str)
      and re.match(r"^[a-z0-9_]{1,64}$", icon.strip())
  ):
    return icon.strip()
  return default


def detect_client_a2ui_version(
    tool_context: Any = None,
    default_version: str = "v0.9",
) -> str:
  """Detects whether the Gemini Enterprise client supports A2UI v0.9 or v0.8.

  Inspects environment variable A2UI_VERSION, session state, or incoming
  a2uiClientCapabilities payloads in request parts. Defaults to 'v0.9'.
  """
  env_ver = os.environ.get("A2UI_VERSION")
  if env_ver in ("v0.8", "v0.9"):
    return env_ver

  if tool_context is not None:
    state = getattr(tool_context, "state", None)
    if state is not None and hasattr(state, "get"):
      cached_ver = state.get("a2ui_version")
      if cached_ver in ("v0.8", "v0.9"):
        return cached_ver

    # Inspect invocation_context / user_content for a2uiClientCapabilities
    for attr in ("user_content", "invocation_context"):
      obj = getattr(tool_context, attr, None)
      if obj is not None:
        raw_str = str(obj)
        if "a2uiClientCapabilities" in raw_str:
          if "material_catalog.json" in raw_str or "v0_9" in raw_str:
            if state is not None and hasattr(state, "__setitem__"):
              try:
                state["a2ui_version"] = "v0.9"
              except Exception:
                pass
            return "v0.9"

  return default_version


def create_a2ui_v08_canvas_messages(
    deck_url: str,
    card_title: str = "Interactive Presentation Deck",
    card_description: str = "Live Google Slides presentation embedded in Canvas",
    card_icon: str = "slideshow",
    surface_id: str = "canvas_surface_1",
    auto_open: bool = True,
) -> List[Dict[str, Any]]:
  """Generates canonical A2UI v0.8 WebFrameUrl canvas messages."""
  embed_url = to_canvas_embed_url(deck_url)
  valid_icon = validate_card_icon(card_icon, default="slideshow")
  return [
      {
          "beginRendering": {
              "surfaceId": surface_id,
              "root": "canvas-root",
          }
      },
      {
          "surfaceUpdate": {
              "surfaceId": surface_id,
              "components": [{
                  "id": "canvas-root",
                  "component": {
                      "WebFrameUrl": {
                          "url": {
                              "literalString": embed_url,
                          },
                          "cardTitle": card_title or "Interactive content",
                          "cardDescription": card_description,
                          "cardIcon": valid_icon,
                          "autoOpen": auto_open,
                      }
                  },
              }],
          }
      },
  ]


def create_a2ui_v09_canvas_messages(
    surface_id: str = "pitchgen-canvas-preview",
    card_title: str = "Interactive Presentation Deck",
    card_description: str = "Live Google Slides presentation embedded in Canvas",
    deck_title: str = "",
    deck_subtitle: str = "",
    presentation_id: str = "",
    metadata_items: Optional[List[str]] = None,
    deck_url: str = "",
    card_icon: str = "slideshow",
    auto_open: bool = True,
) -> List[Dict[str, Any]]:
  """Generates canonical A2UI v0.9 Canvas + IFrameUrl messages.

  Uses the v0.9 Gemini Enterprise Canvas root component with an embedded
  IFrameUrl child component pointing to the Google Slides embed URL.
  """
  del metadata_items  # Unused.
  url = deck_url or (
      f"https://docs.google.com/presentation/d/{presentation_id}/edit"
      if presentation_id
      else ""
  )
  embed_url = to_canvas_embed_url(url)
  valid_icon = validate_card_icon(card_icon, default="slideshow")
  final_title = card_title or deck_title or "Interactive Presentation Deck"
  final_desc = (
      card_description
      or deck_subtitle
      or "Live Google Slides presentation embedded in Canvas"
  )
  return [
      {
          "version": "v0.9",
          "createSurface": {
              "surfaceId": surface_id,
              "catalogId": A2UI_MATERIAL_CATALOG_ID,
          },
      },
      {
          "version": "v0.9",
          "updateComponents": {
              "surfaceId": surface_id,
              "components": [
                  {
                      "id": "root",
                      "component": "Canvas",
                      "cardTitle": final_title,
                      "cardDescription": final_desc,
                      "cardIcon": valid_icon,
                      "autoOpen": auto_open,
                      "children": ["slides-iframe"],
                  },
                  {
                      "id": "slides-iframe",
                      "component": "IFrameUrl",
                      "url": embed_url,
                      "height": 620,
                  },
              ],
          },
      },
  ]


def create_a2ui_canvas_messages(
    deck_url: str,
    card_title: str = "Interactive Presentation Deck",
    card_description: str = "Live Google Slides presentation embedded in Canvas",
    card_icon: str = "slideshow",
    surface_id: str = "canvas_surface_1",
    auto_open: bool = True,
    version: str = "both",
) -> List[Dict[str, Any]]:
  """Generates A2UI canvas messages for Google Slides side panel rendering.

  When version is 'both' (or 'v0.9' without env override), emits both the v0.9
  Canvas + IFrameUrl surface and the v0.8 WebFrameUrl surface so that
  A2uiService.isSidePanelSurface() opens <ucs-a2ui-panel> regardless of whether
  isA2Ui09Enabled() is true or false on the host client.
  """
  active_version = os.environ.get("A2UI_VERSION", version or "both")
  if active_version == "v0.8":
    return create_a2ui_v08_canvas_messages(
        deck_url=deck_url,
        card_title=card_title,
        card_description=card_description,
        card_icon=card_icon,
        surface_id=surface_id,
        auto_open=auto_open,
    )
  v09_msgs = create_a2ui_v09_canvas_messages(
      surface_id=surface_id,
      card_title=card_title,
      card_description=card_description,
      deck_url=deck_url,
      card_icon=card_icon,
      auto_open=auto_open,
  )
  if active_version == "v0.9_only":
    return v09_msgs
  v08_surface_id = (
      f"{surface_id}_v08" if surface_id != "canvas_surface_v08" else surface_id
  )
  v08_msgs = create_a2ui_v08_canvas_messages(
      deck_url=deck_url,
      card_title=card_title,
      card_description=card_description,
      card_icon=card_icon,
      surface_id=v08_surface_id,
      auto_open=auto_open,
  )
  return v09_msgs + v08_msgs


def build_canvas_artifact_textproto(
    deck_url: str,
    title: str,
    model_generated_id: str = "",
) -> str:
  """Builds canonical textproto for cloud_ml_discoveryengine_schema.Artifact with GoogleSlidesArtifact.

  When stored in session state['canvas_artifact'], Dolphin's agent_server.py
  (_SupportCanvasArtifactsAndGwsLog -> state.get_canvas_artifact) parses this
  via text_format.Parse into artifact_pb2.Artifact and attaches it to
  DolphinAgentResponse.canvas_artifacts, which Assistant Service converts into
  StreamAssistResponse.answer.replies[].immersive_artifact
  (CanvasType.WS_SLIDES).
  """
  safe_title = (
      (title or "Presentation Deck").replace('"', '\\"').replace("\n", " ")
  )
  safe_id = (
      (model_generated_id or "pitchgen-deck")
      .replace('"', '\\"')
      .replace("\n", "")
  )
  safe_url = deck_url.replace('"', '\\"').replace("\n", "")
  return (
      f'title: "{safe_title}"\n'
      f'model_generated_id: "{safe_id}"\n'
      "google_slides_artifact {\n"
      f'  google_slides_uri: "{safe_url}"\n'
      "}\n"
  )


def create_a2ui_delete_surface_message(
    surface_id: str = "canvas_surface_1",
    version: str = "v0.9",
) -> List[Dict[str, Any]]:
  """Generates standard GCBP A2UI close-canvas command (defaults to v0.9)."""
  active_version = os.environ.get("A2UI_VERSION", version or "v0.9")
  if active_version == "v0.8":
    return [
        {
            "deleteSurface": {
                "surfaceId": surface_id,
            }
        }
    ]
  return [{
      "version": "v0.9",
      "deleteSurface": {
          "surfaceId": surface_id,
      },
  }]


def format_a2ui_datapart(payload: Any) -> str:
  """Formats a JSON payload wrapped in A2A DataPart tags per GCBP A2UI specification."""
  if isinstance(payload, dict) and "kind" not in payload:
    final_payload = {
        "kind": "data",
        "metadata": {"mimeType": A2UI_MIME_TYPE},
        "data": payload,
    }
  else:
    final_payload = payload
  return f"{A2A_DATA_PART_START_TAG}{json.dumps(final_payload)}{A2A_DATA_PART_END_TAG}"


def create_ge_quick_actions(
    deck_url: str = "",
    customer_name: str = "",
) -> List[Dict[str, Any]]:
  """Builds interactive quick-action definitions for Gemini Enterprise.

  Provides 1-click transitions to the 3 complementary A2UI components:
  1. "search": Slide Search Panel card (searching CloudHub reusable slides)
  2. "transform": Slide Text Transformation card (polishing tone, scope,
  language)
  3. "generate visuals": Nano Banana card (synthesizing diagrams and visual
  assets)
  """
  pres_id = extract_presentation_id(deck_url) or ""
  return [
      {
          "id": "quick_action_search",
          "label": "🔍 Search Slides",
          "style": "primary",
          "action": {
              "type": "a2ui_action",
              "actionName": "search",
              "parameters": {
                  "presentation_id": pres_id,
                  "customer_name": customer_name,
                  "search_query": (
                      f"{customer_name} Architecture"
                      if customer_name
                      else "Cloud Solutions"
                  ),
              },
          },
      },
      {
          "id": "quick_action_transform",
          "label": "✍️ Transform Slide Text",
          "style": "primary",
          "action": {
              "type": "a2ui_action",
              "actionName": "transform",
              "parameters": {
                  "presentation_id": pres_id,
                  "customer_name": customer_name,
                  "scope": "entire_deck",
                  "tone": "EXECUTIVE",
              },
          },
      },
      {
          "id": "quick_action_generate_visuals",
          "label": "🍌 Generate Visuals",
          "style": "primary",
          "action": {
              "type": "a2ui_action",
              "actionName": "generate_visuals",
              "parameters": {
                  "presentation_id": pres_id,
                  "customer_name": customer_name,
                  "visual_style": (
                      "Google Cloud Modern Architecture (Flat vector, precise"
                      " topology)"
                  ),
              },
          },
      },
  ]


def format_a2ui_deck_card(
    deck_url: str,
    customer_name: str = "",
    er_number: str = "",
    user_ldap: str = "",
    architectural_gcs_url: str = "",
    outputs_gcs_url: str = "",
) -> Dict[str, Any]:
  """Formats a slide generation result as an A2UI interactive card for Gemini Enterprise.

  Includes required MIME metadata ('application/json+a2ui') so the UCS widget
  renders interactive UI cards with direct action buttons and Canvas panel
  integration.

  Args:
      deck_url: The clickable Google Slides presentation URL.
      customer_name: Target customer name.
      er_number: Opportunity ER number.
      user_ldap: User's LDAP/email alias.
      architectural_gcs_url: GCS URL for architectural reusable slide metadata.
      outputs_gcs_url: GCS URL for generated section outputs.

  Returns:
      A structured dictionary compatible with A2A DataPart and A2UI rendering.
  """
  if not user_ldap:
    _, resolved_ldap = resolve_ge_user_identity()
    if resolved_ldap:
      user_ldap = resolved_ldap

  is_valid_url = (
      bool(deck_url)
      and not deck_url.startswith("Error")
      and not deck_url.startswith("Auth Error")
  )
  status = "success" if is_valid_url else "failure"
  embed_url = to_canvas_embed_url(deck_url) if is_valid_url else ""

  title = (
      f"🎯 PitchGen Presentation Deck: {customer_name}"
      if customer_name
      else "🎯 PitchGen Presentation Deck"
  )
  subtitle = f"ER #{er_number}" if er_number else "Google Cloud GTM Enablement"

  quick_actions = create_ge_quick_actions(deck_url, customer_name)

  secondary_buttons = [
      {
          "label": "📊 Open Google Slides Presentation",
          "url": deck_url,
          "style": "secondary",
      },
      {
          "label": "🚀 Edit via Slides Extension (https://your-sales-portal.example.com/pitchgen)",
          "url": "https://your-sales-portal.example.com/pitchgen",
          "style": "secondary",
      },
      {
          "label": "🎨 White-Glove Support (https://your-sales-portal.example.com/catalog)",
          "url": "https://your-sales-portal.example.com/catalog",
          "style": "secondary",
      },
  ]

  card_payload = {
      "type": "card",
      "title": title,
      "subtitle": subtitle,
      "metadata": {"mimeType": A2UI_MIME_TYPE},
      "canvasPreview": {
          "supported": is_valid_url,
          "canvasType": "WS_SLIDES",
          "workspaceUri": deck_url,
          "iframeUrl": embed_url,
          "autoOpen": True,
      },
      "sections": [
          {
              "type": "text",
              "content": (
                  "Your customized presentation deck for"
                  f" **{customer_name or 'your customer'}** has been"
                  " successfully synthesized and edit permissions granted to"
                  f" **{user_ldap or 'your account'}**."
              ),
          },
          {
              "type": "quick_actions",
              "title": "⚡ Refine & Enhance in Gemini Enterprise",
              "description": (
                  "Use native Gemini Enterprise AI capabilities to tailor your"
                  " presentation:"
              ),
              "actions": quick_actions,
          },
          {
              "type": "actions",
              "title": "Secondary Options & External Links",
              "buttons": secondary_buttons,
          },
      ],
  }
  canvas_msgs = (
      create_a2ui_canvas_messages(
          deck_url=deck_url,
          card_title=title,
          card_description=(
              f"Tailored presentation deck for {customer_name or 'customer'}"
          ),
          card_icon="slideshow",
          surface_id="canvas_surface_pitchgen",
          auto_open=True,
      )
      if is_valid_url
      else []
  )
  pres_id = extract_presentation_id(deck_url) or ""
  v09_canvas_msgs = (
      create_a2ui_v09_canvas_messages(
          surface_id="pitchgen-canvas-preview",
          card_title=title,
          card_description=(
              f"Tailored presentation deck for {customer_name or 'customer'}"
          ),
          deck_title=f"{customer_name or 'Customer'} Presentation Deck",
          deck_subtitle=(
              "Synthesized pitch presentation ready for presentation."
          ),
          presentation_id=pres_id,
          metadata_items=[f"ER #{er_number}"] if er_number else None,
      )
      if is_valid_url
      else []
  )
  card_payload["canvasMessages"] = canvas_msgs
  card_payload["a2ui_v09_messages"] = v09_canvas_msgs

  arch_fn = (
      architectural_gcs_url.split("/")[-1]
      if "/" in architectural_gcs_url
      else architectural_gcs_url
  )
  out_fn = (
      outputs_gcs_url.split("/")[-1]
      if "/" in outputs_gcs_url
      else outputs_gcs_url
  )

  return {
      "status": status,
      "deck_url": deck_url,
      "canvas_embed_url": embed_url,
      "architectural_filename": arch_fn,
      "outputs_filename": out_fn,
      "gsurl_architectural": architectural_gcs_url,
      "gsurl_outputs": outputs_gcs_url,
      "metadata": {"mimeType": A2UI_MIME_TYPE},
      "a2ui_card": card_payload,
      "canvas_messages": canvas_msgs,
      "a2ui_v09_messages": v09_canvas_msgs,
  }


def create_ge_canvas_artifact(
    deck_url: str,
    title: str = "PitchGen Presentation Deck",
    customer_name: str = "",
) -> Dict[str, Any]:
  """Creates an ImmersiveArtifact representation for the UCS Canvas side panel.

  Matches the GE Canvas WS_SLIDES (Workspace Slides) specification.
  """
  embed_url = to_canvas_embed_url(deck_url)
  return {
      "name": f"artifacts/slides/{extract_presentation_id(deck_url) or 'deck'}",
      "title": title,
      "type": "WS_SLIDES",
      "workspaceUri": deck_url,
      "iframeUrl": embed_url,
      "autoOpen": True,
      "metadata": {
          "customer_name": customer_name,
          "mimeType": A2UI_MIME_TYPE,
      },
      "canvasMessages": create_a2ui_canvas_messages(
          deck_url=deck_url,
          card_title=title,
          card_description=(
              f"Customer pitch deck: {customer_name or 'presentation'}"
          ),
          card_icon="slideshow",
      ),
  }


def wrap_a2ui_response_json(
    deck_url: str,
    customer_name: str = "",
    er_number: str = "",
    user_ldap: str = "",
    architectural_gcs_url: str = "",
    outputs_gcs_url: str = "",
) -> str:
  """Returns the serialized JSON string of the A2UI card response."""
  card_dict = format_a2ui_deck_card(
      deck_url=deck_url,
      customer_name=customer_name,
      er_number=er_number,
      user_ldap=user_ldap,
      architectural_gcs_url=architectural_gcs_url,
      outputs_gcs_url=outputs_gcs_url,
  )
  return json.dumps(card_dict, indent=2)


def create_welcome_intro_card(user_ldap: str = "") -> Dict[str, Any]:
  """Constructs the Welcome / Intro message card for Gemini Enterprise."""
  display_user = (
      f" ({user_ldap})" if user_ldap and user_ldap != "unknown_user" else ""
  )
  v09_launcher_msgs = create_a2ui_v09_launcher_messages()
  return {
      "type": "card",
      "title": f"👋 Welcome to PitchGen for Gemini Enterprise{display_user}",
      "subtitle": "AI-Powered Google Slides Enablement & Sales Modernization",
      "metadata": {"mimeType": A2UI_MIME_TYPE},
      "sections": [
          {
              "type": "info_banner",
              "text": (
                  "PitchGen connects Gemini Enterprise with your Google Drive"
                  " and the CloudHub Asset Library to generate, search, and"
                  " refine executive sales presentations."
              ),
          },
          {
              "type": "quick_actions",
              "title": "Select a Feature to Get Started",
              "actions": [
                  {
                      "id": "intro_start_deck",
                      "label": "🚀 Start New Pitch Deck (GTM Intake)",
                      "style": "primary",
                      "action": {
                          "type": "a2ui_action",
                          "actionName": "intake",
                          "parameters": {"target_card": "generate_pitch"},
                      },
                  },
                  {
                      "id": "intro_search_slides",
                      "label": "🔍 Search CloudHub Slide Library",
                      "style": "secondary",
                      "action": {
                          "type": "a2ui_action",
                          "actionName": "search",
                          "parameters": {"target_card": "search_slide"},
                      },
                  },
                  {
                      "id": "intro_nano_banana",
                      "label": "🍌 Synthesize Architecture Diagram",
                      "style": "secondary",
                      "action": {
                          "type": "a2ui_action",
                          "actionName": "diagram",
                          "parameters": {"target_card": "generate_nanobanana"},
                      },
                  },
                  {
                      "id": "intro_transform_text",
                      "label": "✍️ Transform / Polish Slide Text",
                      "style": "secondary",
                      "action": {
                          "type": "a2ui_action",
                          "actionName": "transform",
                          "parameters": {"target_card": "transform_text"},
                      },
                  },
              ],
          },
      ],
      "canvas_messages": v09_launcher_msgs,
      "a2ui_v09_messages": v09_launcher_msgs,
  }


def create_a2ui_v09_launcher_messages(
    surface_id: str = "pitchgen-launcher",
    catalog_id: str = "https://a2ui.org/specification/v0_9/material_catalog.json",
) -> List[Dict[str, Any]]:
  """Constructs the A2UI v0.9 Material NG Introduction / Feature Launcher Hub card ('pitchgen-launcher').

  Uses the Gemini Enterprise Material Catalog (material_catalog.json) for:
  - Native Google Sans typography via MaterialText (h2, h4, h5, body2) &
  MaterialButton
  - GM3 theme-adaptive surface/card/button colors (--mat-sys-surface,
  --mat-sys-surface-container-low,
    --mat-sys-primary-container, --mat-sys-on-primary-container,
    --mat-sys-outline-variant)
  - Top-middle PitchGen GM3 brand pill ('pitchgen_tool_logo') with MaterialIcon
  + MaterialText
  - Consolidated 5-card grid of non-overlapping PitchGen workflows:
    1. Generate a Pitch Deck ('generate_pitch' -> 'Launch Deck Generation')
    2. Search & Insert Slides ('search_slide' -> 'Open Slide Search')
    3. Transform Slide / Deck ('transform_text' -> 'Open Slide Transformer')
    4. NanoBanana Visual Studio ('generate_nanobanana' -> 'Open NanoBanana
    Studio')
    5. Translate Presentation ('translate' -> 'Open Translator')
  """
  icon_badge_style = {
      "display": "flex",
      "alignItems": "center",
      "justifyContent": "center",
      "width": "40px",
      "height": "40px",
      "minWidth": "40px",
      "borderRadius": "10px",
      "backgroundColor": "var(--mat-sys-primary-container, #e8f0fe)",
      "color": "var(--mat-sys-on-primary-container, #0b57d0)",
      "fontSize": "22px",
  }
  primary_card_style = {
      "backgroundColor": "var(--mat-sys-surface-container-low, #f8fafd)",
      "border": "1.5px solid var(--mat-sys-primary, #0b57d0)",
      "borderRadius": "14px",
      "height": "100%",
      "boxSizing": "border-box",
  }
  secondary_card_style = {
      "backgroundColor": "var(--mat-sys-surface-container-low, #f8fafd)",
      "border": "1px solid var(--mat-sys-outline-variant, #e0e3e7)",
      "borderRadius": "14px",
      "height": "100%",
      "boxSizing": "border-box",
  }
  grid_row_style = {
      "display": "grid",
      "gridTemplateColumns": "repeat(2, minmax(0, 1fr))",
      "gap": "12px",
      "width": "100%",
  }
  single_row_style = {
      "display": "grid",
      "gridTemplateColumns": "minmax(0, 1fr)",
      "gap": "12px",
      "width": "100%",
  }
  card_col_style = {
      "gap": "10px",
      "height": "100%",
      "justifyContent": "space-between",
  }
  logo_row_style = {
      "gap": "12px",
      "alignItems": "center",
  }
  card_title_style = {
      "fontFamily": "'Google Sans', Roboto, sans-serif",
      "fontWeight": "600",
      "color": "var(--mat-sys-on-surface, #1f1f1f)",
      "margin": "0",
  }
  card_desc_style = {
      "fontFamily": "'Google Sans', 'Google Sans Text', Roboto, sans-serif",
      "color": "var(--mat-sys-on-surface-variant, #444746)",
      "lineHeight": "1.45",
      "margin": "0",
  }
  primary_btn_style = {
      "width": "100%",
      "borderRadius": "999px",
      "fontFamily": "'Google Sans', Roboto, sans-serif",
      "fontWeight": "500",
  }
  tonal_btn_style = {
      "width": "100%",
      "borderRadius": "999px",
      "backgroundColor": "var(--mat-sys-primary-container, #e8f0fe)",
      "color": "var(--mat-sys-on-primary-container, #0b57d0)",
      "fontFamily": "'Google Sans', Roboto, sans-serif",
      "fontWeight": "500",
  }

  return [
      {
          "version": "v0.9",
          "createSurface": {
              "surfaceId": surface_id,
              "catalogId": catalog_id,
          },
      },
      {
          "version": "v0.9",
          "updateComponents": {
              "surfaceId": surface_id,
              "components": [
                  {
                      "id": "root",
                      "component": "MaterialCard",
                      "appearance": "outlined",
                      "style": {
                          "backgroundColor": "var(--mat-sys-surface, #ffffff)",
                          "border": (
                              "1px solid var(--mat-sys-outline-variant,"
                              " #dadce0)"
                          ),
                          "borderRadius": "16px",
                          "padding": "8px",
                      },
                      "children": [
                          "main_column",
                      ],
                  },
                  {
                      "id": "main_column",
                      "component": "MaterialColumn",
                      "justify": "start",
                      "align": "stretch",
                      "style": {
                          "gap": "14px",
                          "width": "100%",
                      },
                      "children": [
                          "tool_logo_row",
                          "header_subtitle",
                          "header_divider",
                          "grid_row_1",
                          "grid_row_2",
                          "grid_row_3",
                      ],
                  },
                  {
                      "id": "tool_logo_row",
                      "component": "MaterialRow",
                      "justify": "center",
                      "align": "center",
                      "style": {
                          "width": "100%",
                          "justifyContent": "center",
                          "alignItems": "center",
                      },
                      "children": [
                          "pitchgen_tool_logo",
                      ],
                  },
                  *pitchgen_logo_components(),
                  {
                      "id": "header_subtitle",
                      "component": "MaterialText",
                      "usageHint": "body",
                      "text": {
                          "path": "/header/subtitle",
                      },
                      "style": {
                          "fontFamily": (
                              "'Google Sans', 'Google Sans Text', Roboto,"
                              " sans-serif"
                          ),
                          "textAlign": "center",
                          "color": "var(--mat-sys-on-surface-variant, #444746)",
                          "margin": "0 0 4px 0",
                      },
                  },
                  {
                      "id": "header_divider",
                      "component": "MaterialDivider",
                      "style": {
                          "borderTopColor": (
                              "var(--mat-sys-outline-variant, #e0e3e7)"
                          ),
                          "margin": "2px 0 6px 0",
                      },
                  },
                  {
                      "id": "grid_row_1",
                      "component": "MaterialRow",
                      "justify": "spaceBetween",
                      "align": "stretch",
                      "style": single_row_style,
                      "children": [
                          "card_generate_pitch",
                      ],
                  },
                  {
                      "id": "card_generate_pitch",
                      "component": "MaterialCard",
                      "appearance": "outlined",
                      "weight": 1,
                      "style": primary_card_style,
                      "children": [
                          "col_generate_pitch",
                      ],
                  },
                  {
                      "id": "col_generate_pitch",
                      "component": "MaterialColumn",
                      "justify": "spaceBetween",
                      "align": "stretch",
                      "style": card_col_style,
                      "children": [
                          "logo_row_generate_pitch",
                          "desc_generate_pitch",
                          "btn_generate_pitch",
                      ],
                  },
                  {
                      "id": "logo_row_generate_pitch",
                      "component": "MaterialRow",
                      "justify": "start",
                      "align": "center",
                      "style": logo_row_style,
                      "children": [
                          "logo_generate_pitch",
                          "title_generate_pitch",
                      ],
                  },
                  {
                      "id": "logo_generate_pitch",
                      "component": "MaterialIcon",
                      "icon": "auto_awesome",
                      "color": "primary",
                      "style": icon_badge_style,
                  },
                  {
                      "id": "title_generate_pitch",
                      "component": "MaterialText",
                      "usageHint": "h5",
                      "text": {
                          "path": "/features/generate_pitch/title",
                      },
                      "style": card_title_style,
                  },
                  {
                      "id": "desc_generate_pitch",
                      "component": "MaterialText",
                      "usageHint": "body",
                      "text": {
                          "path": "/features/generate_pitch/description",
                      },
                      "style": card_desc_style,
                  },
                  {
                      "id": "btn_generate_pitch",
                      "component": "MaterialButton",
                      "variant": "flat",
                      "color": "primary",
                      "trailingIcon": "arrow_forward",
                      "loadingOnClick": True,
                      "label": {
                          "path": "/features/generate_pitch/button_label",
                      },
                      "style": primary_btn_style,
                      "action": {
                          "event": {
                              "name": "launch_feature_card",
                              "context": {
                                  "target_card": "generate_pitch",
                                  "workflow_mode": "generate_pitch",
                              },
                          },
                      },
                  },
                  {
                      "id": "grid_row_2",
                      "component": "MaterialRow",
                      "justify": "spaceBetween",
                      "align": "stretch",
                      "style": grid_row_style,
                      "children": [
                          "card_search_slide",
                          "card_transform_text",
                      ],
                  },
                  {
                      "id": "card_search_slide",
                      "component": "MaterialCard",
                      "appearance": "outlined",
                      "weight": 1,
                      "style": secondary_card_style,
                      "children": [
                          "col_search_slide",
                      ],
                  },
                  {
                      "id": "col_search_slide",
                      "component": "MaterialColumn",
                      "justify": "spaceBetween",
                      "align": "stretch",
                      "style": card_col_style,
                      "children": [
                          "logo_row_search_slide",
                          "desc_search_slide",
                          "btn_search_slide",
                      ],
                  },
                  {
                      "id": "logo_row_search_slide",
                      "component": "MaterialRow",
                      "justify": "start",
                      "align": "center",
                      "style": logo_row_style,
                      "children": [
                          "logo_search_slide",
                          "title_search_slide",
                      ],
                  },
                  {
                      "id": "logo_search_slide",
                      "component": "MaterialIcon",
                      "icon": "manage_search",
                      "color": "primary",
                      "style": icon_badge_style,
                  },
                  {
                      "id": "title_search_slide",
                      "component": "MaterialText",
                      "usageHint": "h5",
                      "text": {
                          "path": "/features/search_slide/title",
                      },
                      "style": card_title_style,
                  },
                  {
                      "id": "desc_search_slide",
                      "component": "MaterialText",
                      "usageHint": "body",
                      "text": {
                          "path": "/features/search_slide/description",
                      },
                      "style": card_desc_style,
                  },
                  {
                      "id": "btn_search_slide",
                      "component": "MaterialButton",
                      "variant": "flat",
                      "trailingIcon": "arrow_forward",
                      "loadingOnClick": True,
                      "label": {
                          "path": "/features/search_slide/button_label",
                      },
                      "style": tonal_btn_style,
                      "action": {
                          "event": {
                              "name": "launch_feature_card",
                              "context": {
                                  "target_card": "search_slide",
                                  "workflow_mode": "search_slide",
                              },
                          },
                      },
                  },
                  {
                      "id": "card_transform_text",
                      "component": "MaterialCard",
                      "appearance": "outlined",
                      "weight": 1,
                      "style": secondary_card_style,
                      "children": [
                          "col_transform_text",
                      ],
                  },
                  {
                      "id": "col_transform_text",
                      "component": "MaterialColumn",
                      "justify": "spaceBetween",
                      "align": "stretch",
                      "style": card_col_style,
                      "children": [
                          "logo_row_transform_text",
                          "desc_transform_text",
                          "btn_transform_text",
                      ],
                  },
                  {
                      "id": "logo_row_transform_text",
                      "component": "MaterialRow",
                      "justify": "start",
                      "align": "center",
                      "style": logo_row_style,
                      "children": [
                          "logo_transform_text",
                          "title_transform_text",
                      ],
                  },
                  {
                      "id": "logo_transform_text",
                      "component": "MaterialIcon",
                      "icon": "edit_note",
                      "color": "primary",
                      "style": icon_badge_style,
                  },
                  {
                      "id": "title_transform_text",
                      "component": "MaterialText",
                      "usageHint": "h5",
                      "text": {
                          "path": "/features/transform_text/title",
                      },
                      "style": card_title_style,
                  },
                  {
                      "id": "desc_transform_text",
                      "component": "MaterialText",
                      "usageHint": "body",
                      "text": {
                          "path": "/features/transform_text/description",
                      },
                      "style": card_desc_style,
                  },
                  {
                      "id": "btn_transform_text",
                      "component": "MaterialButton",
                      "variant": "flat",
                      "trailingIcon": "arrow_forward",
                      "loadingOnClick": True,
                      "label": {
                          "path": "/features/transform_text/button_label",
                      },
                      "style": tonal_btn_style,
                      "action": {
                          "event": {
                              "name": "launch_feature_card",
                              "context": {
                                  "target_card": "transform_text",
                                  "workflow_mode": "transform_text",
                              },
                          },
                      },
                  },
                  {
                      "id": "grid_row_3",
                      "component": "MaterialRow",
                      "justify": "spaceBetween",
                      "align": "stretch",
                      "style": grid_row_style,
                      "children": [
                          "card_generate_nanobanana",
                          "card_translate",
                      ],
                  },
                  {
                      "id": "card_generate_nanobanana",
                      "component": "MaterialCard",
                      "appearance": "outlined",
                      "weight": 1,
                      "style": secondary_card_style,
                      "children": [
                          "col_generate_nanobanana",
                      ],
                  },
                  {
                      "id": "col_generate_nanobanana",
                      "component": "MaterialColumn",
                      "justify": "spaceBetween",
                      "align": "stretch",
                      "style": card_col_style,
                      "children": [
                          "logo_row_generate_nanobanana",
                          "desc_generate_nanobanana",
                          "btn_generate_nanobanana",
                      ],
                  },
                  {
                      "id": "logo_row_generate_nanobanana",
                      "component": "MaterialRow",
                      "justify": "start",
                      "align": "center",
                      "style": logo_row_style,
                      "children": [
                          "logo_generate_nanobanana",
                          "title_generate_nanobanana",
                      ],
                  },
                  {
                      "id": "logo_generate_nanobanana",
                      "component": "MaterialIcon",
                      "icon": "palette",
                      "color": "primary",
                      "style": icon_badge_style,
                  },
                  {
                      "id": "title_generate_nanobanana",
                      "component": "MaterialText",
                      "usageHint": "h5",
                      "text": {
                          "path": "/features/generate_nanobanana/title",
                      },
                      "style": card_title_style,
                  },
                  {
                      "id": "desc_generate_nanobanana",
                      "component": "MaterialText",
                      "usageHint": "body",
                      "text": {
                          "path": "/features/generate_nanobanana/description",
                      },
                      "style": card_desc_style,
                  },
                  {
                      "id": "btn_generate_nanobanana",
                      "component": "MaterialButton",
                      "variant": "flat",
                      "trailingIcon": "arrow_forward",
                      "loadingOnClick": True,
                      "label": {
                          "path": "/features/generate_nanobanana/button_label",
                      },
                      "style": tonal_btn_style,
                      "action": {
                          "event": {
                              "name": "launch_feature_card",
                              "context": {
                                  "target_card": "generate_nanobanana",
                                  "workflow_mode": "generate_nanobanana",
                              },
                          },
                      },
                  },
                  {
                      "id": "card_translate",
                      "component": "MaterialCard",
                      "appearance": "outlined",
                      "weight": 1,
                      "style": secondary_card_style,
                      "children": [
                          "col_translate",
                      ],
                  },
                  {
                      "id": "col_translate",
                      "component": "MaterialColumn",
                      "justify": "spaceBetween",
                      "align": "stretch",
                      "style": card_col_style,
                      "children": [
                          "logo_row_translate",
                          "desc_translate",
                          "btn_translate",
                      ],
                  },
                  {
                      "id": "logo_row_translate",
                      "component": "MaterialRow",
                      "justify": "start",
                      "align": "center",
                      "style": logo_row_style,
                      "children": [
                          "logo_translate",
                          "title_translate",
                      ],
                  },
                  {
                      "id": "logo_translate",
                      "component": "MaterialIcon",
                      "icon": "translate",
                      "color": "primary",
                      "style": icon_badge_style,
                  },
                  {
                      "id": "title_translate",
                      "component": "MaterialText",
                      "usageHint": "h5",
                      "text": {
                          "path": "/features/translate/title",
                      },
                      "style": card_title_style,
                  },
                  {
                      "id": "desc_translate",
                      "component": "MaterialText",
                      "usageHint": "body",
                      "text": {
                          "path": "/features/translate/description",
                      },
                      "style": card_desc_style,
                  },
                  {
                      "id": "btn_translate",
                      "component": "MaterialButton",
                      "variant": "flat",
                      "trailingIcon": "arrow_forward",
                      "loadingOnClick": True,
                      "label": {
                          "path": "/features/translate/button_label",
                      },
                      "style": tonal_btn_style,
                      "action": {
                          "event": {
                              "name": "launch_feature_card",
                              "context": {
                                  "target_card": "translate",
                                  "workflow_mode": "translate",
                              },
                          },
                      },
                  },
              ],
          },
      },
      {
          "version": "v0.9",
          "updateDataModel": {
              "surfaceId": surface_id,
              "value": {
                  "launcher": {
                      "active_workflow": "generate_pitch",
                  },
                  "header": {
                      "title": "PitchGen",
                      "subtitle": (
                          "AI-Powered Google Slides Enablement & Presentation"
                          " Studio"
                      ),
                  },
                  "features": {
                      "generate_pitch": {
                          "title": "Generate a Pitch Deck",
                          "description": (
                              "Create an end-to-end tailored customer pitch"
                              " deck from account context, industry, and sales"
                              " plays."
                          ),
                          "button_label": "Launch Deck Generation",
                      },
                      "search_slide": {
                          "title": "Search & Insert Slides",
                          "description": (
                              "Search and preview reusable slides and customer"
                              " stories from the governed repository with"
                              " 1-click deck insertion."
                          ),
                          "button_label": "Open Slide Search",
                      },
                      "transform_text": {
                          "title": "Transform Slide / Deck",
                          "description": (
                              "Rewrite text, replace in-slide images, or adapt"
                              " both across any slide or full deck while"
                              " preserving native Google Slides layouts."
                          ),
                          "button_label": "Open Slide Transformer",
                      },
                      "generate_nanobanana": {
                          "title": "Nano Banana Studio",
                          "description": (
                              "Generate bespoke 2K technical architecture"
                              " diagrams or restyle an entire slide into a"
                              " cohesive visual canvas."
                          ),
                          "button_label": "Open Nano Banana Studio",
                      },
                      "translate": {
                          "title": "Translate Presentation",
                          "description": (
                              "Translate slide copy, titles, and speaker notes"
                              " into 21+ global languages while preserving"
                              " Google Slides layout."
                          ),
                          "button_label": "Open Translator",
                      },
                      "generate_slide": {
                          "title": "Generate Slide",
                          "description": (
                              "Synthesize a brand-new bespoke slide from a"
                              " topic prompt, customer pain points, and layout"
                              " style."
                          ),
                          "button_label": "Open Slide Generator",
                      },
                      "transform_slide": {
                          "title": "Transform Slide",
                          "description": (
                              "Customize and adapt an existing reusable slide"
                              " for a specific target customer and industry."
                          ),
                          "button_label": "Open Slide Transformer",
                      },
                      "transform_nanobanana": {
                          "title": "Transform NanoBanana",
                          "description": (
                              "Restyle, edit, or adapt existing slide visuals"
                              " and graphics using NanoBanana AI image"
                              " controls."
                          ),
                          "button_label": "Open NanoBanana Transformer",
                      },
                  },
              },
          },
      },
  ]


def create_a2ui_launcher_messages(
    surface_id: str = "pitchgen-launcher",
    catalog_id: str = "https://a2ui.org/specification/v0_9/material_catalog.json",
    version: str = "v0.9",
) -> List[Dict[str, Any]]:
  """Generates the PitchGen Introduction / Feature Launcher Hub A2UI v0.9 messages."""
  del version  # Always emits canonical v0.9 pitchgen-launcher surface
  return create_a2ui_v09_launcher_messages(
      surface_id=surface_id,
      catalog_id=catalog_id,
  )


# ==============================================================================
# Re-exports of the Core A2UI Workflows
# ==============================================================================
try:
  from pitchgen.ge.a2ui_intake import (
      DEFAULT_SALES_PLAYS,
      GROUPED_SALES_PLAY_OPTIONS,
      SALES_PLAYS_BY_PRACTICE_AREA,
      create_a2ui_intake_messages,
      create_a2ui_v09_intake_messages,
      create_gtm_intake_card,
      normalize_sales_play_value,
  )
  from pitchgen.ge.a2ui_outline import (
      create_a2ui_outline_messages,
      create_a2ui_v09_outline_messages,
      create_outline_review_card,
  )
  from pitchgen.ge.a2ui_search import (
      create_a2ui_search_form_messages,
      create_a2ui_search_messages,
      create_a2ui_search_results_messages,
      create_a2ui_v09_search_form_messages,
      create_a2ui_v09_search_messages,
      create_a2ui_v09_search_results_messages,
      create_slide_search_panel_card,
      normalize_slide_search_item,
  )
  from pitchgen.ge.a2ui_transform_text import (
      create_a2ui_generate_slide_messages,
      create_a2ui_transform_messages,
      create_a2ui_transform_text_messages,
      create_a2ui_v09_generate_slide_messages,
      create_a2ui_v09_transform_messages,
      create_a2ui_v09_transform_text_messages,
      create_provide_deck_prompt_card,
      create_text_transform_card,
  )
  from pitchgen.ge.a2ui_translate import (
      PITCHGEN_TRANSLATE_LANGUAGES,
      create_a2ui_translate_messages,
      create_a2ui_v09_translate_messages,
      create_translate_card,
  )
  from pitchgen.ge.a2ui_nano_banana import (
      create_a2ui_nano_banana_messages,
      create_a2ui_v09_nano_banana_messages,
      create_nano_banana_card,
  )
except ImportError:
  from ge.a2ui_intake import (  # pylint: disable=g-import-not-at-top
      DEFAULT_SALES_PLAYS,
      GROUPED_SALES_PLAY_OPTIONS,
      SALES_PLAYS_BY_PRACTICE_AREA,
      create_a2ui_intake_messages,
      create_a2ui_v09_intake_messages,
      create_gtm_intake_card,
      normalize_sales_play_value,
  )
  from ge.a2ui_outline import (  # pylint: disable=g-import-not-at-top
      create_a2ui_outline_messages,
      create_a2ui_v09_outline_messages,
      create_outline_review_card,
  )
  from ge.a2ui_search import (  # pylint: disable=g-import-not-at-top
      create_a2ui_search_form_messages,
      create_a2ui_search_messages,
      create_a2ui_search_results_messages,
      create_a2ui_v09_search_form_messages,
      create_a2ui_v09_search_messages,
      create_a2ui_v09_search_results_messages,
      create_slide_search_panel_card,
      normalize_slide_search_item,
  )
  from ge.a2ui_transform_text import (  # pylint: disable=g-import-not-at-top
      create_a2ui_generate_slide_messages,
      create_a2ui_transform_messages,
      create_a2ui_transform_text_messages,
      create_a2ui_v09_generate_slide_messages,
      create_a2ui_v09_transform_messages,
      create_a2ui_v09_transform_text_messages,
      create_provide_deck_prompt_card,
      create_text_transform_card,
  )
  from ge.a2ui_translate import (  # pylint: disable=g-import-not-at-top
      PITCHGEN_TRANSLATE_LANGUAGES,
      create_a2ui_translate_messages,
      create_a2ui_v09_translate_messages,
      create_translate_card,
  )
  from ge.a2ui_nano_banana import (  # pylint: disable=g-import-not-at-top
      create_a2ui_nano_banana_messages,
      create_a2ui_v09_nano_banana_messages,
      create_nano_banana_card,
  )
__all__ = [
    "A2A_DATA_PART_END_TAG",
    "A2A_DATA_PART_START_TAG",
    "A2UI_BASIC_CATALOG_ID",
    "A2UI_GE_COMPOSITE_CATALOG_ID",
    "A2UI_GE_CUSTOM_CATALOG_ID",
    "A2UI_MATERIAL_CATALOG_ID",
    "A2UI_MIME_TYPE",
    "A2UI_OHARA_CATALOG_ID",
    "A2UI_URI_V08",
    "A2UI_URI_V09",
    "DEFAULT_SALES_PLAYS",
    "GROUPED_SALES_PLAY_OPTIONS",
    "PITCHGEN_TRANSLATE_LANGUAGES",
    "SALES_PLAYS_BY_PRACTICE_AREA",
    "create_a2ui_canvas_messages",
    "create_a2ui_delete_surface_message",
    "create_a2ui_generate_slide_messages",
    "create_a2ui_intake_messages",
    "create_a2ui_launcher_messages",
    "create_a2ui_nano_banana_messages",
    "create_a2ui_outline_messages",
    "create_a2ui_search_form_messages",
    "create_a2ui_search_messages",
    "create_a2ui_search_results_messages",
    "create_a2ui_transform_messages",
    "create_a2ui_transform_text_messages",
    "create_a2ui_translate_messages",
    "create_a2ui_v09_canvas_messages",
    "create_a2ui_v09_generate_slide_messages",
    "create_a2ui_v09_intake_messages",
    "create_a2ui_v09_launcher_messages",
    "create_a2ui_v09_nano_banana_messages",
    "create_a2ui_v09_outline_messages",
    "create_a2ui_v09_search_form_messages",
    "create_a2ui_v09_search_messages",
    "create_a2ui_v09_search_results_messages",
    "create_a2ui_v09_transform_messages",
    "create_a2ui_v09_transform_text_messages",
    "create_a2ui_v09_translate_messages",
    "create_ge_canvas_artifact",
    "create_ge_quick_actions",
    "create_gtm_intake_card",
    "create_nano_banana_card",
    "create_outline_review_card",
    "create_provide_deck_prompt_card",
    "create_slide_search_panel_card",
    "create_text_transform_card",
    "create_welcome_intro_card",
    "detect_client_a2ui_version",
    "extract_presentation_id",
    "format_a2ui_datapart",
    "format_a2ui_deck_card",
    "get_email_from_oauth_token",
    "normalize_sales_play_value",
    "resolve_ge_user_identity",
    "to_canvas_embed_url",
    "validate_card_icon",
    "wrap_a2ui_response_json",
]
