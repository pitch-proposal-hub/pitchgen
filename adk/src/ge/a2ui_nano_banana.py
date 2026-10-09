"""Gemini Enterprise A2UI Card for Nano Banana Visual Slide Transformation.

Implements Workflow 4:
- Generates and enhances slide visuals using Nano Banana models:
  - Nano Banana Pro (gemini-3.1-pro-image): Complex architectures, customer
  journey maps, high visual fidelity.
  - Nano Banana Flash (gemini-3.1-flash-image): Fast iterations, conceptual
  diagrams, visual icon cards.
- Supports Style Reference Image continuity.
- Covers single slide or full presentation visual polish.
"""

from typing import Any, Dict, List, Optional

try:
  from ge import a2ui
except ImportError:
  from src.ge import a2ui  # pylint: disable=g-import-not-at-top

NANO_BANANA_MODELS = [
    {
        "id": "nano_banana_pro",
        "model_id": "gemini-3.1-pro-image",
        "name": "Nano Banana Pro",
        "description": (
            "Enterprise architectures, complex topologies, customer journey"
            " maps."
        ),
    },
    {
        "id": "nano_banana",
        "model_id": "gemini-3.1-flash-image",
        "name": "Nano Banana",
        "description": (
            "Rapid conceptual diagrams, infographic cards, layout polish."
        ),
    },
    {
        "id": "gemini-nano-banana-2.1",
        "model_id": "gemini-nano-banana-2.1",
        "name": "Nano Banana 2.1",
        "description": (
            "Latest Nano Banana 2.1 visual synthesis and slide restyling"
            " engine."
        ),
    },
]

VISUAL_STYLES = [
    "Google Cloud Modern Architecture (Flat vector, precise topology)",
    "Executive Minimalist (Clean typography, whitespace, subtle accents)",
    "Customer Journey Map (Linear phase cards, persona touchpoints)",
    "Infographic Data Flow (Gradients, metrics, process nodes)",
]


def create_nano_banana_card(
    presentation_id: str = "",
    target_slide_index: int = 1,
    selected_model: str = "nano_banana_pro",
    visual_style: str = "Google Cloud Modern Architecture (Flat vector, precise topology)",
    reference_image_url: str = "",
    prompt: str = "",
    deck_url: str = "",
    generated_image_url: str = "",
    mode: str = "generate",
    **kwargs: Any,
) -> Dict[str, Any]:
  """Constructs the A2UI card for Nano Banana visual and diagram synthesis."""
  del mode, kwargs
  if not presentation_id and deck_url:
    presentation_id = a2ui.extract_presentation_id(deck_url) or deck_url
  model_options = [
      {
          "value": m["id"],
          "label": m["name"],
          "selected": m["id"] == selected_model,
      }
      for m in NANO_BANANA_MODELS
  ]

  fields = [
      {
          "id": "target_slide_index",
          "type": "number",
          "label": "Target Slide Number",
          "value": target_slide_index,
          "min": 1,
          "required": True,
      },
      {
          "id": "nano_banana_model",
          "type": "select",
          "label": "Model Engine",
          "value": selected_model,
          "options": model_options,
      },
      {
          "id": "style_reference_image",
          "type": "image_upload",
          "label": "Style Reference Image (Optional continuity)",
          "image_url": reference_image_url,
          "placeholder": "Paste slide image URL or upload reference diagram...",
      },
      {
          "id": "visual_prompt",
          "type": "textarea",
          "label": "Visual / Diagram Prompt",
          "value": prompt,
          "placeholder": (
              "e.g. Architecture topology connecting Gemini Enterprise,"
              " BigQuery, and Private Service Connect with zero-trust"
              " perimeter..."
          ),
          "required": True,
      },
  ]

  actions = [{
      "id": "btn_generate_nano_banana",
      "label": "Run NanoBanana",
      "style": "primary",
      "action": {
          "type": "a2ui_action",
          "actionName": "transform_with_nano_banana",
          "parameters": {
              "presentation_id": presentation_id,
              "slide_index": target_slide_index,
              "model": selected_model,
              "style": visual_style,
              "reference_image_url": reference_image_url,
              "prompt": prompt,
              "generated_image_url": generated_image_url,
          },
      },
  }]

  return {
      "type": "card",
      "title": "Nano Banana Studio",
      "subtitle": "Generative 2K Diagrams & Full-Slide Visual Restyling",
      "metadata": {"mimeType": a2ui.A2UI_MIME_TYPE},
      "sections": [
          {
              "type": "info_banner",
              "text": (
                  "Nano Banana models synthesize high-fidelity technical"
                  " diagrams and visuals directly into your Google Slides"
                  " presentation."
              ),
          },
          {
              "type": "form",
              "fields": fields,
          },
          {
              "type": "actions",
              "buttons": actions,
          },
      ],
  }


def create_a2ui_v09_nano_banana_messages(
    presentation_id: str = "",
    presentation_url_or_id: str = "",
    prompt: str = "",
    visual_style: str = "",
    target_slide_index: int = 1,
    generated_image_url: str = "",
    inserted_slide_id: str = "",
    customer_name: str = "",
    reference_image_url: str = "",
    selected_model: str = "nano_banana_pro",
    mode: str = "generate",
    surface_id: str = "",
    **kwargs: Any,
) -> List[Dict[str, Any]]:
  """Generates canonical A2UI v0.9 messages for the consolidated Nano Banana Studio card ('pitchgen-generate-nanobanana' or 'pitchgen-transform-nanobanana')."""
  del kwargs  # Unused
  font_sans = "'Google Sans', 'Google Sans Text', Roboto, Arial, sans-serif"
  resolved_pres = presentation_id or presentation_url_or_id or ""
  is_transform_mode = str(mode or "").strip().lower() in (
      "transform",
      "transform_nanobanana",
      "restyle",
      "restyle existing slide",
  )

  resolved_surface_id = (
      surface_id
      if (surface_id and surface_id != "pitchgen-nano-banana")
      else (
          "pitchgen-transform-nanobanana"
          if is_transform_mode
          else "pitchgen-generate-nanobanana"
      )
  )

  effective_style = visual_style if visual_style in VISUAL_STYLES else ""

  mode_options = [
      {
          "label": "Generate New Visual",
          "value": "generate",
      },
      {
          "label": "Restyle Existing Slide",
          "value": "transform",
      },
  ]
  model_options = [
      {
          "label": "Nano Banana Pro",
          "value": "nano_banana_pro",
      },
      {
          "label": "Nano Banana",
          "value": "nano_banana",
      },
      {
          "label": "Nano Banana 2.1",
          "value": "gemini-nano-banana-2.1",
      },
  ]
  raw_model = str(selected_model or "").strip().lower()
  if raw_model in (
      "gemini-nano-banana-2.1",
      "nano_banana_2_1",
      "nano banana 2.1",
  ):
    effective_model = "gemini-nano-banana-2.1"
  elif raw_model in ("nano_banana", "nano_banana_flash", "nano banana"):
    effective_model = "nano_banana"
  else:
    effective_model = "nano_banana_pro"

  header_title = "Nano Banana Studio"
  subtitle_text = (
      f"Inserted high-resolution visual onto slide ({inserted_slide_id}) in"
      f" deck {resolved_pres}."
      if inserted_slide_id and resolved_pres
      else (
          "Synthesized high-resolution visual via Nano Banana Studio."
          if generated_image_url
          else (
              "Generate a new visual or restyle an existing slide using"
              " Nano Banana Pro, Nano Banana, or Nano Banana 2.1."
          )
      )
  )
  btn_label = "Run NanoBanana"
  main_col_children = [
      "header-txt",
      "sub-txt",
      "divider-1",
      "row-mode-model",
      "input-prompt",
      "row-target-deck",
      "row-brand-ref",
      "btn-generate-visual",
  ]
  mode_components = [
      {
          "id": "row-mode-model",
          "component": "MaterialRow",
          "style": {"gap": "12px", "width": "100%"},
          "children": ["select-mode", "select-model"],
      },
      {
          "id": "select-mode",
          "component": "MaterialSelect",
          "label": "Studio Mode",
          "value": {"path": "/visual/mode"},
          "options": mode_options,
          "weight": 1,
      },
      {
          "id": "select-model",
          "component": "MaterialSelect",
          "label": "Model Engine",
          "value": {"path": "/visual/model"},
          "options": model_options,
          "weight": 1,
      },
      {
          "id": "input-prompt",
          "component": "MaterialInput",
          "label": "Architecture / Visual Concept Prompt *",
          "placeholder": (
              "e.g., Enterprise GenAI reference architecture connecting"
              " Gemini Enterprise, BigQuery, and Cloud Run"
          ),
          "value": {"path": "/visual/prompt"},
      },
      {
          "id": "row-target-deck",
          "component": "MaterialRow",
          "style": {"gap": "12px", "width": "100%"},
          "children": ["input-deck-id", "input-slide-idx"],
      },
      {
          "id": "input-deck-id",
          "component": "MaterialInput",
          "label": "Target Google Slides Deck ID / URL (Optional)",
          "placeholder": (
              "Paste Google Slides URL or ID to insert or restyle visual in"
              " deck"
          ),
          "value": {"path": "/visual/presentation_id"},
          "weight": 2,
      },
      {
          "id": "input-slide-idx",
          "component": "MaterialInput",
          "label": "Target Slide #",
          "placeholder": "e.g., 1",
          "value": {"path": "/visual/target_slide_index"},
          "weight": 1,
      },
      {
          "id": "row-brand-ref",
          "component": "MaterialRow",
          "style": {"gap": "12px", "width": "100%"},
          "children": ["input-customer-brand", "input-reference-url"],
      },
      {
          "id": "input-customer-brand",
          "component": "MaterialInput",
          "label": "Target Customer / Brand Context (Optional)",
          "placeholder": "e.g., Target, LVMH, Deutsche Bank",
          "value": {"path": "/visual/customer_name"},
          "weight": 1,
      },
      {
          "id": "input-reference-url",
          "component": "MaterialInput",
          "label": "Style Reference Image URL (Optional)",
          "placeholder": (
              "Optional reference diagram or brand visual URL for style"
              " continuity"
          ),
          "value": {"path": "/visual/reference_image_url"},
          "weight": 1,
      },
  ]

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
          "children": ["main-col"],
      },
      {
          "id": "main-col",
          "component": "MaterialColumn",
          "style": {"gap": "14px"},
          "children": main_col_children,
      },
      {
          "id": "header-txt",
          "component": "MaterialText",
          "text": header_title,
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
          "id": "sub-txt",
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
          "id": "divider-1",
          "component": "MaterialDivider",
      },
  ]
  components.extend(mode_components)
  components.append({
      "id": "btn-generate-visual",
      "component": "MaterialButton",
      "label": btn_label,
      "variant": "flat",
      "style": {
          "fontFamily": font_sans,
          "fontWeight": "500",
          "borderRadius": "999px",
      },
      "action": {
          "event": {
              "name": "transform_with_nano_banana",
              "context": {
                  "presentation_id": {"path": "/visual/presentation_id"},
                  "prompt": {"path": "/visual/prompt"},
                  "slide_index": {"path": "/visual/target_slide_index"},
                  "customer_name": {"path": "/visual/customer_name"},
                  "reference_image_url": {
                      "path": "/visual/reference_image_url"
                  },
                  "model": {"path": "/visual/model"},
                  "mode": {"path": "/visual/mode"},
              },
          }
      },
  })

  return [
      {
          "version": "v0.9",
          "createSurface": {
              "surfaceId": resolved_surface_id,
              "catalogId": a2ui.A2UI_MATERIAL_CATALOG_ID,
          },
      },
      {
          "version": "v0.9",
          "updateDataModel": {
              "surfaceId": resolved_surface_id,
              "path": "/visual",
              "value": {
                  "presentation_id": resolved_pres,
                  "prompt": prompt or "",
                  "visual_style": effective_style,
                  "target_slide_index": str(target_slide_index or 1),
                  "customer_name": customer_name or "",
                  "reference_image_url": reference_image_url or "",
                  "model": effective_model,
                  "generated_image_url": generated_image_url or "",
                  "mode": "transform" if is_transform_mode else "generate",
              },
          },
      },
      {
          "version": "v0.9",
          "updateComponents": {
              "surfaceId": resolved_surface_id,
              "components": components,
          },
      },
  ]


def create_a2ui_nano_banana_messages(
    presentation_id: str = "",
    presentation_url_or_id: str = "",
    prompt: str = "",
    visual_style: str = "",
    target_slide_index: int = 1,
    generated_image_url: str = "",
    inserted_slide_id: str = "",
    customer_name: str = "",
    reference_image_url: str = "",
    selected_model: str = "nano_banana_pro",
    mode: str = "generate",
    surface_id: str = "",
    **kwargs: Any,
) -> List[Dict[str, Any]]:
  """Version-aware wrapper returning A2UI v0.9 Nano Banana visual synthesis messages."""
  return create_a2ui_v09_nano_banana_messages(
      presentation_id=presentation_id,
      presentation_url_or_id=presentation_url_or_id,
      prompt=prompt,
      visual_style=visual_style,
      target_slide_index=target_slide_index,
      generated_image_url=generated_image_url,
      inserted_slide_id=inserted_slide_id,
      customer_name=customer_name,
      reference_image_url=reference_image_url,
      selected_model=selected_model,
      mode=mode,
      surface_id=surface_id,
      **kwargs,
  )
