"""Gemini Enterprise A2UI v0.9 Card for Presentation Translation ('pitchgen-translate').

Implements Card 6 (Translate Presentation):
- Google Slides Deck ID / URL * (mandatory shortText)
- Translate Instructions / Criteria (optional longText)
- Target Language * (mandatory dropdown with 18 PitchGen languages)
- Target Slides / Scope (checkbox 'Translate Full Deck (All Slides)' + slide
numbers input)
"""

from typing import Any, Dict, List, Optional

A2UI_MIME_TYPE = "application/json+a2ui"
A2UI_BASIC_CATALOG_ID = "https://a2ui.org/specification/v0_9/basic_catalog.json"
A2UI_MATERIAL_CATALOG_ID = (
    "https://a2ui.org/specification/v0_9/material_catalog.json"
)

PITCHGEN_TRANSLATE_LANGUAGES = [
    "Arabic",
    "Chinese (Simplified)",
    "Chinese (Traditional)",
    "Danish",
    "Dutch",
    "English",
    "Finnish",
    "French",
    "German",
    "Greek",
    "Hindi",
    "Indonesian",
    "Italian",
    "Japanese",
    "Korean",
    "Polish",
    "Portuguese",
    "Spanish",
    "Swedish",
    "Thai",
    "Turkish",
]


def _normalize_target_language_selection(
    target_language: Optional[Any],
) -> List[str]:
  """Normalizes target_language into a 1-element list for backwards compatibility."""
  placeholder = "Select Language"
  if not target_language:
    return [placeholder]
  if isinstance(target_language, list):
    cleaned = [
        str(x).strip()
        for x in target_language
        if str(x).strip()
        and str(x).strip().lower() not in ("", "none", "select language")
    ]
    if not cleaned:
      return [placeholder]
    candidate = cleaned[0]
  else:
    candidate = str(target_language).strip()
    if not candidate or candidate.lower() in ("none", "select language"):
      return [placeholder]

  lang_map = {lang.lower(): lang for lang in PITCHGEN_TRANSLATE_LANGUAGES}
  if candidate.lower() in lang_map:
    return [lang_map[candidate.lower()]]
  return [candidate]


def create_a2ui_v09_translate_messages(
    presentation_url_or_id: str = "",
    translate_instructions: str = "",
    target_language: Optional[Any] = None,
    full_deck_scope: Optional[List[str]] = None,
    target_slide_indices: str = "",
    surface_id: str = "pitchgen-translate",
    slides_modified: int = 0,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
  """Creates the canonical A2UI v0.9 Material Catalog messages for the Translate Presentation card ('pitchgen-translate')."""
  font_sans = "'Google Sans', 'Google Sans Text', Roboto, Arial, sans-serif"
  resolved_pres = presentation_url_or_id or str(
      kwargs.get("presentation_id") or ""
  )
  resolved_lang_list = _normalize_target_language_selection(target_language)
  resolved_language = (
      resolved_lang_list[0]
      if resolved_lang_list and resolved_lang_list[0] != "Select Language"
      else "Spanish"
  )

  if full_deck_scope is None:
    resolved_full_deck = (
        []
        if (target_slide_indices and str(target_slide_indices).strip())
        else ["full_deck"]
    )
  elif isinstance(full_deck_scope, bool):
    resolved_full_deck = ["full_deck"] if full_deck_scope else []
  elif isinstance(full_deck_scope, list):
    resolved_full_deck = (
        []
        if (target_slide_indices and str(target_slide_indices).strip())
        else [str(x) for x in full_deck_scope if str(x).strip()]
    )
  else:
    resolved_full_deck = ["full_deck"]

  language_options = [
      {"label": lang, "value": lang} for lang in PITCHGEN_TRANSLATE_LANGUAGES
  ]

  subtitle_text = (
      f"Translated {slides_modified} slide(s) into {resolved_language} in deck"
      f" {resolved_pres}."
      if slides_modified and resolved_pres
      else (
          "Translate slide copy, titles, and speaker notes into 21+ global"
          " languages while preserving native Google Slides layouts and brand"
          " nomenclature."
      )
  )

  components: List[Dict[str, Any]] = [
      {
          "id": "root",
          "component": "MaterialCard",
          "appearance": "outlined",
          "style": {
              "padding": "24px",
              "borderRadius": "16px",
              "backgroundColor": "var(--mat-sys-surface, #ffffff)",
              "border": "1px solid var(--mat-sys-outline-variant, #dadce0)",
          },
          "children": ["main_column"],
      },
      {
          "id": "main_column",
          "component": "MaterialColumn",
          "style": {"gap": "14px"},
          "children": [
              "header_title",
              "header_subtitle",
              "header_divider",
              "presentation_url_input",
              "row_lang_slides",
              "translate_instructions_input",
              "btn_translate_submit",
          ],
      },
      {
          "id": "header_title",
          "component": "MaterialText",
          "text": "🌐 Translate Presentation",
          "usageHint": "h3",
          "style": {
              "fontFamily": font_sans,
              "fontSize": "18px",
              "fontWeight": "600",
              "color": "var(--mat-sys-on-surface, #1f1f1f)",
              "margin": "0",
          },
      },
      {
          "id": "header_subtitle",
          "component": "MaterialText",
          "text": subtitle_text,
          "usageHint": "body",
          "style": {
              "fontFamily": font_sans,
              "fontSize": "13px",
              "color": "var(--mat-sys-on-surface-variant, #444746)",
              "margin": "0",
          },
      },
      {
          "id": "header_divider",
          "component": "MaterialDivider",
      },
      {
          "id": "presentation_url_input",
          "component": "MaterialInput",
          "label": "Google Slides Deck ID / URL *",
          "placeholder": "Paste Google Slides URL or Presentation ID",
          "value": {
              "path": "/presentation_url_or_id",
          },
      },
      {
          "id": "row_lang_slides",
          "component": "MaterialRow",
          "style": {"gap": "12px", "width": "100%"},
          "children": ["target_language_select", "target_slides_input"],
      },
      {
          "id": "target_language_select",
          "component": "MaterialSelect",
          "label": "Target Language *",
          "placeholder": "Select Target Language",
          "value": {
              "path": "/target_language",
          },
          "options": language_options,
          "weight": 1,
      },
      {
          "id": "target_slides_input",
          "component": "MaterialInput",
          "label": "Target Slides (Blank = Full Deck, or e.g. 2, 4-6)",
          "placeholder": "All slides (Full Deck) or e.g., 2, 4-6",
          "value": {
              "path": "/target_slide_indices",
          },
          "weight": 1,
      },
      {
          "id": "translate_instructions_input",
          "component": "MaterialInput",
          "label": "Translation Instructions / Glossary Criteria (Optional)",
          "placeholder": (
              "e.g., Use formal executive register (Sie/usted), keep product"
              " names in English"
          ),
          "value": {
              "path": "/translate_instructions",
          },
      },
      {
          "id": "btn_translate_submit",
          "component": "MaterialButton",
          "label": "🌐 Translate Presentation",
          "variant": "flat",
          "style": {
              "fontFamily": font_sans,
              "fontWeight": "500",
              "borderRadius": "999px",
          },
          "action": {
              "event": {
                  "name": "translate_presentation_deck",
                  "context": {
                      "presentation_url_or_id": {
                          "path": "/presentation_url_or_id",
                      },
                      "translate_instructions": {
                          "path": "/translate_instructions",
                      },
                      "target_language": {
                          "path": "/target_language",
                      },
                      "full_deck_scope": {
                          "path": "/full_deck_scope",
                      },
                      "target_slide_indices": {
                          "path": "/target_slide_indices",
                      },
                  },
              },
          },
      },
  ]

  data_model = {
      "presentation_url_or_id": resolved_pres,
      "translate_instructions": translate_instructions or "",
      "target_language": resolved_language,
      "full_deck_scope": resolved_full_deck,
      "target_slide_indices": str(target_slide_indices or ""),
  }

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
          "updateDataModel": {
              "surfaceId": surface_id,
              "value": data_model,
          },
      },
      {
          "version": "v0.9",
          "updateComponents": {
              "surfaceId": surface_id,
              "components": components,
          },
      },
  ]


def create_a2ui_translate_messages(
    presentation_url_or_id: str = "",
    translate_instructions: str = "",
    target_language: Optional[Any] = None,
    full_deck_scope: Optional[List[str]] = None,
    target_slide_indices: str = "",
    surface_id: str = "pitchgen-translate",
    version: str = "v0.9",
    **kwargs: Any,
) -> List[Dict[str, Any]]:
  """Generates A2UI v0.9 messages for the Translate Presentation card ('pitchgen-translate')."""
  del version
  return create_a2ui_v09_translate_messages(
      presentation_url_or_id=presentation_url_or_id,
      translate_instructions=translate_instructions,
      target_language=target_language,
      full_deck_scope=full_deck_scope,
      target_slide_indices=target_slide_indices,
      surface_id=surface_id,
      **kwargs,
  )


def create_translate_card(
    presentation_id: str = "",
    target_language: str = "",
    translate_instructions: str = "",
    target_slide_indices: str = "",
    full_deck_scope: Optional[List[str]] = None,
) -> Dict[str, Any]:
  """Constructs the structured A2UI card wrapper for Presentation Translation."""
  v09_messages = create_a2ui_v09_translate_messages(
      presentation_url_or_id=presentation_id,
      translate_instructions=translate_instructions,
      target_language=target_language,
      full_deck_scope=full_deck_scope,
      target_slide_indices=target_slide_indices,
  )
  res: Dict[str, Any] = {
      "type": "card",
      "title": "🌐 Translate Presentation",
      "subtitle": (
          f"Active Canvas Deck: {presentation_id or 'Unset'} • 18 Global"
          " Languages"
      ),
      "metadata": {"mimeType": A2UI_MIME_TYPE},
      "a2ui_v09_messages": v09_messages,
      "canvas_messages": v09_messages,
  }
  if presentation_id:
    res["canvasPreview"] = {
        "supported": True,
        "canvasType": "WS_SLIDES",
        "workspaceUri": (
            f"https://docs.google.com/presentation/d/{presentation_id}/edit"
        ),
        "iframeUrl": (
            f"https://docs.google.com/presentation/d/{presentation_id}/embed?start=false&loop=false&delayms=3000"
        ),
        "autoOpen": True,
    }
  return res
