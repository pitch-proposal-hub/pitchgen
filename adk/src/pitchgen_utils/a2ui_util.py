"""Compatibility layer re-exporting Gemini Enterprise A2UI & Canvas utilities from ge.a2ui."""

from typing import Any

try:
  from src.ge import a2ui
except ImportError:
  try:
    from ge import a2ui
  except ImportError:
    try:
      from ge import a2ui
    except ImportError:
      import a2ui  # pylint: disable=g-import-not-at-top

A2A_DATA_PART_END_TAG = a2ui.A2A_DATA_PART_END_TAG
A2A_DATA_PART_START_TAG = a2ui.A2A_DATA_PART_START_TAG
A2UI_BASIC_CATALOG_ID = a2ui.A2UI_BASIC_CATALOG_ID
A2UI_GE_COMPOSITE_CATALOG_ID = a2ui.A2UI_GE_COMPOSITE_CATALOG_ID
A2UI_GE_CUSTOM_CATALOG_ID = a2ui.A2UI_GE_CUSTOM_CATALOG_ID
A2UI_MATERIAL_CATALOG_ID = a2ui.A2UI_MATERIAL_CATALOG_ID
A2UI_MIME_TYPE = a2ui.A2UI_MIME_TYPE
A2UI_OHARA_CATALOG_ID = a2ui.A2UI_OHARA_CATALOG_ID
A2UI_URI_V08 = a2ui.A2UI_URI_V08
A2UI_URI_V09 = a2ui.A2UI_URI_V09
PITCHGEN_TRANSLATE_LANGUAGES = getattr(a2ui, "PITCHGEN_TRANSLATE_LANGUAGES", [])
DEFAULT_SALES_PLAYS = getattr(a2ui, "DEFAULT_SALES_PLAYS", [])
GROUPED_SALES_PLAY_OPTIONS = getattr(a2ui, "GROUPED_SALES_PLAY_OPTIONS", [])
SALES_PLAYS_BY_PRACTICE_AREA = getattr(a2ui, "SALES_PLAYS_BY_PRACTICE_AREA", {})
normalize_sales_play_value = getattr(a2ui, "normalize_sales_play_value", None)
build_canvas_artifact_textproto = a2ui.build_canvas_artifact_textproto
create_translate_card = getattr(a2ui, "create_translate_card", None)
create_a2ui_canvas_messages = a2ui.create_a2ui_canvas_messages
create_a2ui_delete_surface_message = a2ui.create_a2ui_delete_surface_message
create_a2ui_generate_slide_messages = a2ui.create_a2ui_generate_slide_messages
create_a2ui_intake_messages = a2ui.create_a2ui_intake_messages
create_a2ui_launcher_messages = a2ui.create_a2ui_launcher_messages
create_a2ui_nano_banana_messages = a2ui.create_a2ui_nano_banana_messages
create_a2ui_outline_messages = a2ui.create_a2ui_outline_messages
create_a2ui_search_messages = a2ui.create_a2ui_search_messages
create_a2ui_search_form_messages = getattr(
    a2ui, "create_a2ui_search_form_messages", a2ui.create_a2ui_search_messages
)
create_a2ui_search_results_messages = getattr(
    a2ui, "create_a2ui_search_results_messages", None
)
create_a2ui_transform_messages = a2ui.create_a2ui_transform_messages
create_a2ui_transform_text_messages = a2ui.create_a2ui_transform_text_messages
create_a2ui_translate_messages = a2ui.create_a2ui_translate_messages
create_a2ui_v09_canvas_messages = a2ui.create_a2ui_v09_canvas_messages
create_a2ui_v09_generate_slide_messages = (
    a2ui.create_a2ui_v09_generate_slide_messages
)
create_a2ui_v09_intake_messages = a2ui.create_a2ui_v09_intake_messages
create_a2ui_v09_launcher_messages = a2ui.create_a2ui_v09_launcher_messages
create_a2ui_v09_nano_banana_messages = a2ui.create_a2ui_v09_nano_banana_messages
create_a2ui_v09_outline_messages = a2ui.create_a2ui_v09_outline_messages
create_a2ui_v09_search_messages = a2ui.create_a2ui_v09_search_messages
create_a2ui_v09_transform_messages = a2ui.create_a2ui_v09_transform_messages
create_a2ui_v09_transform_text_messages = (
    a2ui.create_a2ui_v09_transform_text_messages
)
create_a2ui_v09_translate_messages = a2ui.create_a2ui_v09_translate_messages
create_ge_canvas_artifact = a2ui.create_ge_canvas_artifact
create_ge_quick_actions = a2ui.create_ge_quick_actions
create_gtm_intake_card = a2ui.create_gtm_intake_card
create_nano_banana_card = a2ui.create_nano_banana_card
create_outline_review_card = a2ui.create_outline_review_card
create_provide_deck_prompt_card = a2ui.create_provide_deck_prompt_card
create_slide_search_panel_card = a2ui.create_slide_search_panel_card
create_text_transform_card = a2ui.create_text_transform_card
create_welcome_intro_card = a2ui.create_welcome_intro_card
detect_client_a2ui_version = a2ui.detect_client_a2ui_version
extract_presentation_id = a2ui.extract_presentation_id
format_a2ui_datapart = a2ui.format_a2ui_datapart
format_a2ui_deck_card = a2ui.format_a2ui_deck_card
get_email_from_oauth_token = a2ui.get_email_from_oauth_token
normalize_slide_search_item = getattr(a2ui, "normalize_slide_search_item", None)
resolve_ge_user_identity = a2ui.resolve_ge_user_identity
to_canvas_embed_url = a2ui.to_canvas_embed_url
validate_card_icon = a2ui.validate_card_icon
wrap_a2ui_response_json = a2ui.wrap_a2ui_response_json


def create_a2a_part_from_a2ui_payload(payload: Any) -> Any:
  """Creates a google.genai.types.Part with MIME application/json+a2ui for A2A communication.

  Conforms to the GCBP & Gemini Enterprise A2UI Part specification.
  """
  from google.genai import types  # pylint: disable=g-import-not-at-top
  import json  # pylint: disable=g-import-not-at-top

  if isinstance(payload, dict) and "kind" in payload and "metadata" in payload:
    final_item = payload
  else:
    final_item = {
        "kind": "data",
        "metadata": {"mimeType": A2UI_MIME_TYPE},
        "data": payload,
    }

  tagged_json = f"{A2A_DATA_PART_START_TAG}{json.dumps(final_item)}{A2A_DATA_PART_END_TAG}"
  return types.Part(
      inline_data=types.Blob(
          data=tagged_json.encode("utf-8"), mime_type="text/plain"
      )
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
    "create_a2a_part_from_a2ui_payload",
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
    "create_a2ui_v09_search_messages",
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
