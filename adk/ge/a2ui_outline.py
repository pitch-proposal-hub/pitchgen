"""Gemini Enterprise A2UI Card Generator for Outline & Agenda Review.

Implements Workflow 1 (Step 2):
- Presents proposed agenda topics, sections, and slide titles for user review
- Allows editing and toggling between the 3 deck strategies:
  1. smart_hybrid (CloudHub Reusable + Bespoke Anchors)
  2. cloudhub (100% Brand-Vetted Reusable Slides)
  3. bespoke_custom (100% Net-New Custom Synthesized Layouts)
- Approves outline to trigger full deck rendering, or refines with feedback.
"""

import re
from typing import Any, Dict, List, Optional

try:
  from ge import a2ui
except ImportError:
  from src.ge import a2ui  # pylint: disable=g-import-not-at-top


def create_outline_review_card(
    customer_name: str,
    agenda_sections: List[Dict[str, Any]],
    deck_strategy: str = "smart_hybrid",
    executive_summary: str = "",
    context: Optional[Dict[str, Any]] = None,
    er_number: str = "",
) -> Dict[str, Any]:
  """Builds the interactive Outline Review card before slide synthesis."""
  context = context or {}
  if er_number and "er_number" not in context:
    context["er_number"] = er_number

  strategy_badges = {
      "smart_hybrid": "⚡ Smart Hybrid (CloudHub + Bespoke Anchors)",
      "cloudhub_focused": "📁 CloudHub Focused (Vetted Templates)",
      "cloudhub": "📁 CloudHub Focused (Vetted Templates)",
      "bespoke_custom": "✨ Bespoke Custom (100% Tailored Layouts)",
  }

  strategy_badge = strategy_badges.get(deck_strategy, "⚡ Smart Hybrid")

  formatted_sections = []
  for idx, sec in enumerate(agenda_sections, 1):
    sec_title = sec.get("title", f"Section {idx}")
    subtopics = sec.get("subtopics") or sec.get("topics") or []
    if isinstance(subtopics, list):
      subtopics_text = " • ".join(str(t) for t in subtopics)
    else:
      subtopics_text = str(subtopics)

    formatted_sections.append({
        "index": idx,
        "title": sec_title,
        "subtopics": subtopics_text,
        "slide_count": sec.get("slide_count", 1),
        "expected_slide_jobs": sec.get(
            "expected_slide_jobs", ["Solution_Overview"]
        ),
        "editable": True,
    })

  refinement_presets = [
      "+ Security & Zero Trust",
      "+ 3.2x ROI Proof Points",
      "Focus C-Level Vision",
      "Shorten to 4 Slides",
      "Technical Architecture Deep Dive",
  ]

  available_strategies = [
      {
          "id": "smart_hybrid",
          "label": "⚡ Smart Hybrid (CloudHub + Bespoke Anchors)",
          "description": (
              "Blends vetted slides from CloudHub with custom synthesized"
              " slides."
          ),
      },
      {
          "id": "cloudhub",
          "label": "📁 CloudHub Focused (100% Brand-Vetted Reusable Slides)",
          "description": (
              "Prioritizes 100% brand-vetted enterprise library slides."
          ),
      },
      {
          "id": "bespoke_custom",
          "label": "✨ Bespoke Custom (100% Tailored Layouts)",
          "description": (
              "Synthesizes 100% net-new tailored slides from scratch."
          ),
      },
  ]

  actions = [
      {
          "id": "btn_approve_generate",
          "label": "🚀 Approve Outline & Generate Deck",
          "style": "primary",
          "action": {
              "type": "a2ui_action",
              "actionName": "approve_outline_and_generate",
              "parameters": {
                  "customer_name": customer_name,
                  "deck_strategy": deck_strategy,
                  "agenda_sections": agenda_sections,
                  "context": context,
              },
          },
      },
      {
          "id": "btn_refine_outline",
          "label": "✨ Refine with Gemini",
          "style": "secondary",
          "action": {
              "type": "a2ui_action",
              "actionName": "refine_outline",
              "parameters": {
                  "customer_name": customer_name,
              },
          },
      },
  ]

  v08_messages = create_a2ui_outline_messages(
      customer_name=customer_name,
      agenda_sections=agenda_sections,
      deck_strategy=deck_strategy,
  )

  return {
      "type": "card",
      "title": f"📋 Outline Review: {customer_name}",
      "subtitle": f"Active Strategy: {strategy_badge}",
      "metadata": {"mimeType": a2ui.A2UI_MIME_TYPE},
      "sections": [
          {
              "type": "info_banner",
              "text": (
                  "✏️ Interactive Proposal Outline: Edit section titles, slide"
                  " counts, and topics directly below, or use natural language"
                  " refinement before generating your deck."
              ),
          },
          {
              "type": "agenda_list",
              "executive_summary": executive_summary,
              "customer_name": customer_name,
              "deck_strategy": deck_strategy,
              "available_strategies": available_strategies,
              "editable": True,
              "allow_add": True,
              "refinement_presets": refinement_presets,
              "items": formatted_sections,
          },
          {
              "type": "actions",
              "buttons": actions,
          },
      ],
      "canvas_messages": v08_messages,
      "a2ui_v09_messages": v08_messages,
  }


def create_a2ui_v08_outline_messages(
    customer_name: str,
    agenda_sections: List[Dict[str, Any]],
    deck_strategy: str = "smart_hybrid",
    surface_id: str = "pitchgen-outline",
) -> List[Dict[str, Any]]:
  """Generates canonical A2UI v0.8 messages for outline review.

  Adheres to canonical A2UI v0.8 wire protocol:
  [beginRendering, surfaceUpdate] with Card, Column, Text, Divider,
  MultipleChoice, and Button components.

  Args:
      customer_name: Target customer account name.
      agenda_sections: List of outline sections with titles and slide counts.
      deck_strategy: Active deck strategy identifier.
      surface_id: A2UI surface identifier.

  Returns:
      A list of A2UI v0.8 wire protocol messages.
  """
  strategy_options = [
      {
          "label": {
              "literalString": "⚡ Smart Hybrid (CloudHub + Bespoke Anchors)"
          },
          "value": "smart_hybrid",
      },
      {
          "label": {
              "literalString": "📁 CloudHub Focused (100% Brand-Vetted Slides)"
          },
          "value": "cloudhub",
      },
      {
          "label": {
              "literalString": "✨ Bespoke Custom (100% Tailored Layouts)"
          },
          "value": "bespoke_custom",
      },
  ]

  components: List[Dict[str, Any]] = [
      {
          "id": "root",
          "component": {
              "Card": {
                  "child": "outline_col",
              }
          },
      },
  ]
  col_children = ["outline_title", "outline_subtitle", "divider_top"]

  components.append({
      "id": "outline_title",
      "component": {
          "Text": {
              "text": {
                  "literalString": (
                      f"📋 PitchGen Proposal Outline: {customer_name}"
                      if customer_name
                      else "📋 PitchGen Proposal Outline"
                  )
              },
              "usageHint": "h2",
          }
      },
  })
  components.append({
      "id": "outline_subtitle",
      "component": {
          "Text": {
              "text": {
                  "literalString": (
                      f"Review and refine the {len(agenda_sections)}"
                      " presentation sections before synthesizing slides"
                  )
              },
              "usageHint": "body",
          }
      },
  })
  components.append({
      "id": "divider_top",
      "component": {
          "Divider": {
              "axis": "horizontal",
          }
      },
  })

  for idx, sec in enumerate(agenda_sections, start=1):
    sec_id = f"sec_{idx}"
    card_id = f"{sec_id}_card"
    col_id = f"{sec_id}_col"
    title_id = f"{sec_id}_title"
    desc_id = f"{sec_id}_desc"
    slides_id = f"{sec_id}_slides"

    col_children.append(card_id)

    title_val = sec.get("title", f"Section {idx}")
    subtopics = sec.get("subtopics") or sec.get("topics") or []
    sub_str = (
        " • ".join(str(t) for t in subtopics)
        if isinstance(subtopics, list)
        else str(subtopics)
    )
    slide_count_val = str(sec.get("slide_count", 1))

    components.extend([
        {
            "id": card_id,
            "component": {
                "Card": {
                    "child": col_id,
                }
            },
        },
        {
            "id": col_id,
            "component": {
                "Column": {
                    "children": {
                        "explicitList": [title_id, desc_id, slides_id],
                    },
                    "distribution": "start",
                    "alignment": "stretch",
                }
            },
        },
        {
            "id": title_id,
            "component": {
                "Text": {
                    "text": {"literalString": f"{idx}. {title_val}"},
                    "usageHint": "h3",
                }
            },
        },
        {
            "id": desc_id,
            "component": {
                "Text": {
                    "text": {
                        "literalString": f"Topics: {sub_str or title_val}"
                    },
                    "usageHint": "body",
                }
            },
        },
        {
            "id": slides_id,
            "component": {
                "Text": {
                    "text": {
                        "literalString": (
                            f"Target slide count: {slide_count_val}"
                        )
                    },
                    "usageHint": "caption",
                }
            },
        },
    ])

  col_children.extend([
      "divider_mid",
      "strategy_label",
      "strategy_picker",
      "refinement_input",
      "divider_bottom",
      "actions_row",
  ])

  v08_refine_context = [
      {
          "key": "customer_name",
          "value": {"literalString": customer_name or "Customer"},
      },
      {
          "key": "deck_strategy",
          "value": {"literalString": deck_strategy or "smart_hybrid"},
      },
      {
          "key": "refinement_instructions",
          "value": {"path": "/refinement_instructions"},
      },
      {
          "key": "prompt",
          "value": {
              "literalString": (
                  f"Refine proposal outline for {customer_name}"
                  if customer_name
                  else "Refine proposal outline"
              )
          },
      },
  ]

  v08_approve_context = [
      {
          "key": "customer_name",
          "value": {"literalString": customer_name or "Customer"},
      },
      {
          "key": "deck_strategy",
          "value": {"literalString": deck_strategy or "smart_hybrid"},
      },
      {
          "key": "refinement_instructions",
          "value": {"path": "/refinement_instructions"},
      },
      {
          "key": "prompt",
          "value": {
              "literalString": (
                  "Approve outline and synthesize"
                  f" presentation deck for {customer_name}"
                  if customer_name
                  else "Approve outline and synthesize presentation deck"
              )
          },
      },
  ]

  components.extend([
      {
          "id": "divider_mid",
          "component": {
              "Divider": {
                  "axis": "horizontal",
              }
          },
      },
      {
          "id": "strategy_label",
          "component": {
              "Text": {
                  "text": {"literalString": "Selected Deck Strategy:"},
                  "usageHint": "h4",
              }
          },
      },
      {
          "id": "strategy_picker",
          "component": {
              "MultipleChoice": {
                  "selections": {
                      "literalArray": [
                          deck_strategy if deck_strategy else "smart_hybrid"
                      ]
                  },
                  "options": strategy_options,
                  "maxAllowedSelections": 1,
                  "variant": "chips",
              }
          },
      },
      {
          "id": "refinement_input",
          "component": {
              "TextField": {
                  "label": {
                      "literalString": "Refinement Instructions (Optional)"
                  },
                  "text": {"path": "/refinement_instructions"},
              }
          },
      },
      {
          "id": "divider_bottom",
          "component": {
              "Divider": {
                  "axis": "horizontal",
              }
          },
      },
      {
          "id": "actions_row",
          "component": {
              "Row": {
                  "children": {
                      "explicitList": ["refine_btn", "approve_btn"],
                  },
                  "distribution": "end",
                  "alignment": "center",
              }
          },
      },
      {
          "id": "refine_btn",
          "component": {
              "Button": {
                  "child": "refine_btn_text",
                  "primary": False,
                  "action": {
                      "name": "refine_proposal_outline",
                      "context": v08_refine_context,
                  },
              }
          },
      },
      {
          "id": "refine_btn_text",
          "component": {
              "Text": {
                  "text": {"literalString": "🔄 Refine Outline"},
              }
          },
      },
      {
          "id": "approve_btn",
          "component": {
              "Button": {
                  "child": "approve_btn_text",
                  "primary": True,
                  "action": {
                      "name": "generate_deck",
                      "context": v08_approve_context,
                  },
              }
          },
      },
      {
          "id": "approve_btn_text",
          "component": {
              "Text": {
                  "text": {
                      "literalString": "🚀 Approve Outline & Generate Deck"
                  },
              }
          },
      },
      {
          "id": "outline_col",
          "component": {
              "Column": {
                  "children": {
                      "explicitList": col_children,
                  },
                  "distribution": "start",
                  "alignment": "stretch",
              }
          },
      },
  ])

  return [
      {
          "beginRendering": {
              "surfaceId": surface_id,
              "root": "root",
          }
      },
      {
          "dataModelUpdate": {
              "surfaceId": surface_id,
              "path": "/",
              "contents": [
                  {
                      "key": "customer_name",
                      "valueString": customer_name or "Customer",
                  },
                  {
                      "key": "deck_strategy",
                      "valueString": deck_strategy or "smart_hybrid",
                  },
                  {
                      "key": "refinement_instructions",
                      "valueString": "",
                  },
              ],
          }
      },
      {
          "surfaceUpdate": {
              "surfaceId": surface_id,
              "components": components,
          }
      },
  ]


# Inline outline-document icon for the outline card header (data: SVG with
# rgb() fills and zero '%' / '#' characters so GE's basic Image renders it).
OUTLINE_HEADER_ICON_URL = (
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg'"
    " width='45' height='45' viewBox='0 0 72 72'><rect x='0' y='0'"
    " width='72' height='72' rx='14' fill='rgb(232,240,254)'/><rect"
    " x='16' y='14' width='40' height='44' rx='5' fill='none'"
    " stroke='rgb(26,115,232)' stroke-width='3.5'/><line x1='24'"
    " y1='25' x2='48' y2='25' stroke='rgb(26,115,232)'"
    " stroke-width='3.5' stroke-linecap='round'/><line x1='24'"
    " y1='35' x2='48' y2='35' stroke='rgb(26,115,232)'"
    " stroke-width='3.5' stroke-linecap='round'/><line x1='24'"
    " y1='45' x2='38' y2='45' stroke='rgb(26,115,232)'"
    " stroke-width='3.5' stroke-linecap='round'/></svg>"
)

# A2UI event names emitted by the per-section controls on the outline card.
OUTLINE_SECTION_EDIT_EVENT = "save_outline_section_edit"
OUTLINE_SECTION_DELETE_EVENT = "delete_outline_section"
OUTLINE_SECTION_ADD_EVENT = "add_outline_section"
OUTLINE_SECTION_EVENTS = (
    OUTLINE_SECTION_EDIT_EVENT,
    OUTLINE_SECTION_DELETE_EVENT,
    OUTLINE_SECTION_ADD_EVENT,
)

_DEFAULT_SUBTOPIC = "Executive overview & key takeaways"
_SLIDE_COUNT_REGEXP = r"^\s*[1-9][0-9]?\s*$"


def split_outline_subtopics(raw: Any) -> List[str]:
  """Splits subtopics given as a list or as a newline/bullet/semicolon string."""
  if isinstance(raw, (list, tuple)):
    items = [str(s) for s in raw]
  elif raw is None:
    items = []
  else:
    text = str(raw)
    if "\n" in text or "•" in text or ";" in text:
      items = re.split(r"[\n•;]+", text)
    else:
      items = text.split(",") if "," in text else [text]
  cleaned = []
  for item in items:
    s = str(item).strip().lstrip("•-*").strip()
    if s:
      cleaned.append(s)
  return cleaned


def _basic_text(
    comp_id: str, text: str, variant: str = "body"
) -> Dict[str, Any]:
  return {"id": comp_id, "component": "Text", "text": text, "variant": variant}


def _basic_button(
    comp_id: str, label: str, action: Dict[str, Any], variant: str = "default"
) -> List[Dict[str, Any]]:
  """Returns a basic-catalog Button plus its Text label child."""
  text_id = f"{comp_id}_text"
  return [
      {
          "id": comp_id,
          "component": "Button",
          "variant": variant,
          "child": text_id,
          "action": action,
      },
      _basic_text(text_id, label),
  ]


# Basic-catalog Buttons require an `action`; Modal trigger buttons use a no-op
# client-side function call so clicking only opens the Modal (no server turn).
_MODAL_TRIGGER_NOOP_ACTION: Dict[str, Any] = {
    "functionCall": {
        "call": "formatString",
        "args": {"value": ""},
        "returnType": "string",
    }
}


def create_a2ui_v09_outline_basic_messages(
    customer_name: str,
    agenda_sections: List[Dict[str, Any]],
    deck_strategy: str = "smart_hybrid",
    surface_id: str = "pitchgen-outline",
    sales_play: str = "",
) -> List[Dict[str, Any]]:
  """Generates the basic-catalog Proposal Outline card (Modal fallback).

  Not wired by default; selected via `outline_style="basic"`. The whole
  surface is declared against the v0.9 basic catalog because it uses
  `Modal` (per-section Edit / Remove confirmation and 'Add agenda topic').
  Basic components do not accept `style` (strict `unevaluatedProperties`), so
  the card is polished via typography variants, Card grouping, Row alignment
  and Button variants (primary / default / borderless) only.

  Events:
    - `save_outline_section_edit`, `delete_outline_section`,
      `add_outline_section`: handled deterministically (no LLM) in
      `enterprise_before_model_callback`.
    - `refine_proposal_outline` and `approve_outline_and_generate`: unchanged
      qa-p2 event names/contexts (approve never binds refinement_instructions).

  Args:
    customer_name: Target customer account name.
    agenda_sections: Outline sections (title, subtopics, slide_count).
    deck_strategy: Active deck strategy identifier.
    surface_id: Unique A2UI surface identifier for this card revision.
    sales_play: Optional sales play label shown in the header subtitle.

  Returns:
    [createSurface, updateDataModel, updateComponents] v0.9 messages.
  """
  cust_label = str(customer_name or "").strip()
  if cust_label.lower() == "customer":
    cust_label = ""
  if isinstance(sales_play, (list, tuple)):
    sales_play = ", ".join(str(s).strip() for s in sales_play if str(s).strip())
  sp_label = str(sales_play or "").strip()

  sections: List[Dict[str, Any]] = []
  for idx, sec in enumerate(agenda_sections or [], start=1):
    if not isinstance(sec, dict):
      sec = {"title": str(sec)}
    title_val = str(sec.get("title") or f"Section {idx}").strip()
    subs = split_outline_subtopics(
        sec.get("subtopics") or sec.get("topics") or sec.get("parts") or []
    )
    if not subs:
      subs = [_DEFAULT_SUBTOPIC]
    try:
      slide_count = max(1, int(sec.get("slide_count") or len(subs) or 1))
    except (TypeError, ValueError):
      slide_count = max(1, len(subs))
    sections.append(
        {"title": title_val, "subtopics": subs, "slide_count": slide_count}
    )

  total_slides = sum(s["slide_count"] for s in sections)
  data_model: Dict[str, Any] = {
      "customer_name": customer_name or "Customer",
      "deck_strategy": deck_strategy or "smart_hybrid",
      "refinement_instructions": "",
      "new_topic_title": "",
      "new_topic_subtopics": "",
      "new_topic_slides": "1",
      "sections": [
          {
              "title": s["title"],
              "subtopics_text": "\n".join(s["subtopics"]),
              "slide_count": str(s["slide_count"]),
          }
          for s in sections
      ],
  }

  subtitle_bits = [b for b in (cust_label, sp_label) if b]
  header_subtitle = " · ".join(subtitle_bits) or "Review your presentation"
  summary_text = (
      f"{len(sections)} section{'s' if len(sections) != 1 else ''} ·"
      f" {total_slides} target slide{'s' if total_slides != 1 else ''}, plus"
      " cover, agenda & closing. Edit, remove, or add agenda topics, refine"
      " with Gemini, then approve to build the deck."
  )

  col_children: List[str] = [
      "tool_logo_row",
      "header_row",
      "outline_summary",
      "header_divider",
  ]
  components: List[Dict[str, Any]] = [
      {"id": "root", "component": "Card", "child": "outline_col"},
      {
          "id": "tool_logo_row",
          "component": "Row",
          "justify": "center",
          "align": "center",
          "children": ["pitchgen_tool_logo"],
      },
      {
          "id": "pitchgen_tool_logo",
          "component": "Image",
          "description": "PitchGen",
          "url": a2ui.PITCHGEN_TOOL_LOGO_URL,
      },
      {
          "id": "header_row",
          "component": "Row",
          "justify": "start",
          "align": "center",
          "children": ["outline_header_icon", "header_text_col"],
      },
      {
          "id": "outline_header_icon",
          "component": "Image",
          "description": "Proposal Outline",
          "url": OUTLINE_HEADER_ICON_URL,
      },
      {
          "id": "header_text_col",
          "component": "Column",
          "justify": "start",
          "align": "start",
          "children": ["outline_header_title", "outline_header_subtitle"],
      },
      _basic_text("outline_header_title", "Proposal Outline", "h3"),
      _basic_text("outline_header_subtitle", f"**{header_subtitle}**"),
      _basic_text("outline_summary", summary_text),
      {"id": "header_divider", "component": "Divider", "axis": "horizontal"},
  ]

  section_bindings: Dict[str, Any] = {}
  for idx, sec in enumerate(sections, start=1):
    pos = idx - 1
    sid = f"sec_{idx}"
    base_path = f"/sections/{pos}"
    section_bindings[f"sec_{idx}_title"] = {"path": f"{base_path}/title"}
    section_bindings[f"sec_{idx}_subtopics"] = {
        "path": f"{base_path}/subtopics_text"
    }
    col_children.append(f"{sid}_card")

    sub_ids = [f"{sid}_sub_{s_i}" for s_i in range(len(sec["subtopics"]))]
    slides_word = "slide" if sec["slide_count"] == 1 else "slides"
    common_ctx = {
        "section_index": pos,
        "section_number": idx,
        "customer_name": {"path": "/customer_name"},
        "deck_strategy": {"path": "/deck_strategy"},
    }
    edit_ctx = dict(common_ctx)
    edit_ctx.update({
        "section_title": {"path": f"{base_path}/title"},
        "subtopics_text": {"path": f"{base_path}/subtopics_text"},
        "slide_count": {"path": f"{base_path}/slide_count"},
    })
    delete_ctx = dict(common_ctx)
    delete_ctx["section_title"] = sec["title"]

    components.extend([
        {"id": f"{sid}_card", "component": "Card", "child": f"{sid}_col"},
        {
            "id": f"{sid}_col",
            "component": "Column",
            "justify": "start",
            "align": "stretch",
            "children": [f"{sid}_header_row"] + sub_ids + [f"{sid}_meta"],
        },
        {
            "id": f"{sid}_header_row",
            "component": "Row",
            "justify": "spaceBetween",
            "align": "center",
            "children": [f"{sid}_title", f"{sid}_actions_row"],
        },
        _basic_text(f"{sid}_title", f"{idx}. {sec['title']}", "h4"),
        {
            "id": f"{sid}_actions_row",
            "component": "Row",
            "justify": "end",
            "align": "center",
            "children": [f"{sid}_edit_modal", f"{sid}_delete_modal"],
        },
        # --- Edit Modal ---
        {
            "id": f"{sid}_edit_modal",
            "component": "Modal",
            "trigger": f"{sid}_edit_btn",
            "content": f"{sid}_edit_col",
        },
        *_basic_button(
            f"{sid}_edit_btn", "Edit", _MODAL_TRIGGER_NOOP_ACTION, "default"
        ),
        {
            "id": f"{sid}_edit_col",
            "component": "Column",
            "justify": "start",
            "align": "stretch",
            "children": [
                f"{sid}_edit_heading",
                f"{sid}_edit_title_input",
                f"{sid}_edit_subtopics_input",
                f"{sid}_edit_slides_input",
                f"{sid}_edit_actions_row",
            ],
        },
        _basic_text(f"{sid}_edit_heading", f"Edit section {idx}", "h4"),
        {
            "id": f"{sid}_edit_title_input",
            "component": "TextField",
            "label": "Section title",
            "variant": "shortText",
            "value": {"path": f"{base_path}/title"},
        },
        {
            "id": f"{sid}_edit_subtopics_input",
            "component": "TextField",
            "label": "Subtopics (one per line)",
            "variant": "longText",
            "value": {"path": f"{base_path}/subtopics_text"},
        },
        {
            "id": f"{sid}_edit_slides_input",
            "component": "TextField",
            "label": "Target slides",
            "variant": "number",
            "validationRegexp": _SLIDE_COUNT_REGEXP,
            "value": {"path": f"{base_path}/slide_count"},
        },
        {
            "id": f"{sid}_edit_actions_row",
            "component": "Row",
            "justify": "end",
            "align": "center",
            "children": [f"{sid}_edit_save_btn"],
        },
        *_basic_button(
            f"{sid}_edit_save_btn",
            "Save",
            {
                "event": {
                    "name": OUTLINE_SECTION_EDIT_EVENT,
                    "context": edit_ctx,
                }
            },
            "primary",
        ),
        # --- Remove (confirmation Modal, subtle borderless trigger) ---
        {
            "id": f"{sid}_delete_modal",
            "component": "Modal",
            "trigger": f"{sid}_delete_btn",
            "content": f"{sid}_delete_col",
        },
        *_basic_button(
            f"{sid}_delete_btn",
            "Remove",
            _MODAL_TRIGGER_NOOP_ACTION,
            "borderless",
        ),
        {
            "id": f"{sid}_delete_col",
            "component": "Column",
            "justify": "start",
            "align": "stretch",
            "children": [
                f"{sid}_delete_heading",
                f"{sid}_delete_body",
                f"{sid}_delete_actions_row",
            ],
        },
        _basic_text(f"{sid}_delete_heading", f"Remove section {idx}?", "h4"),
        _basic_text(
            f"{sid}_delete_body",
            f"**{sec['title']}** will be removed from the outline. You can"
            " add it back any time with *Add agenda topic*.",
        ),
        {
            "id": f"{sid}_delete_actions_row",
            "component": "Row",
            "justify": "end",
            "align": "center",
            "children": [f"{sid}_delete_confirm_btn"],
        },
        *_basic_button(
            f"{sid}_delete_confirm_btn",
            "Remove section",
            {
                "event": {
                    "name": OUTLINE_SECTION_DELETE_EVENT,
                    "context": delete_ctx,
                }
            },
            "default",
        ),
    ])
    for s_i, sub_text in enumerate(sec["subtopics"]):
      components.append(_basic_text(sub_ids[s_i], f"• {sub_text}"))
    components.append(
        _basic_text(
            f"{sid}_meta", f"{sec['slide_count']} {slides_word}", "caption"
        )
    )

  col_children.extend([
      "add_topic_row",
      "footer_divider",
      "refinement_input",
      "actions_row",
  ])

  refine_ctx: Dict[str, Any] = {
      "customer_name": {"path": "/customer_name"},
      "deck_strategy": {"path": "/deck_strategy"},
      "refinement_instructions": {"path": "/refinement_instructions"},
      "prompt": (
          f"Refine proposal outline for {customer_name}"
          if customer_name
          else "Refine proposal outline"
      ),
  }
  refine_ctx.update(section_bindings)
  # NOTE: approve must never bind refinement_instructions (qa-p2 invariant).
  approve_ctx: Dict[str, Any] = {
      "customer_name": {"path": "/customer_name"},
      "deck_strategy": {"path": "/deck_strategy"},
      "prompt": (
          "Approve outline and synthesize presentation deck"
          f" for {customer_name}"
          if customer_name
          else "Approve outline and synthesize presentation deck"
      ),
  }
  approve_ctx.update(section_bindings)

  components.extend([
      {
          "id": "add_topic_row",
          "component": "Row",
          "justify": "start",
          "align": "center",
          "children": ["add_topic_modal"],
      },
      {
          "id": "add_topic_modal",
          "component": "Modal",
          "trigger": "add_topic_trigger_btn",
          "content": "add_topic_col",
      },
      *_basic_button(
          "add_topic_trigger_btn",
          "+ Add agenda topic",
          _MODAL_TRIGGER_NOOP_ACTION,
          "default",
      ),
      {
          "id": "add_topic_col",
          "component": "Column",
          "justify": "start",
          "align": "stretch",
          "children": [
              "add_topic_heading",
              "new_topic_title_input",
              "new_topic_subtopics_input",
              "new_topic_slides_input",
              "add_topic_actions_row",
          ],
      },
      _basic_text("add_topic_heading", "Add agenda topic", "h4"),
      {
          "id": "new_topic_title_input",
          "component": "TextField",
          "label": "Topic title",
          "variant": "shortText",
          "value": {"path": "/new_topic_title"},
      },
      {
          "id": "new_topic_subtopics_input",
          "component": "TextField",
          "label": "Subtopics (one per line)",
          "variant": "longText",
          "value": {"path": "/new_topic_subtopics"},
      },
      {
          "id": "new_topic_slides_input",
          "component": "TextField",
          "label": "Target slides",
          "variant": "number",
          "validationRegexp": _SLIDE_COUNT_REGEXP,
          "value": {"path": "/new_topic_slides"},
      },
      {
          "id": "add_topic_actions_row",
          "component": "Row",
          "justify": "end",
          "align": "center",
          "children": ["add_topic_confirm_btn"],
      },
      *_basic_button(
          "add_topic_confirm_btn",
          "Add topic",
          {
              "event": {
                  "name": OUTLINE_SECTION_ADD_EVENT,
                  "context": {
                      "customer_name": {"path": "/customer_name"},
                      "deck_strategy": {"path": "/deck_strategy"},
                      "new_topic_title": {"path": "/new_topic_title"},
                      "new_topic_subtopics": {"path": "/new_topic_subtopics"},
                      "new_topic_slides": {"path": "/new_topic_slides"},
                  },
              }
          },
          "primary",
      ),
      {"id": "footer_divider", "component": "Divider", "axis": "horizontal"},
      {
          "id": "refinement_input",
          "component": "TextField",
          "label": "Refine with Gemini (optional)",
          "variant": "longText",
          "value": {"path": "/refinement_instructions"},
      },
      {
          "id": "actions_row",
          "component": "Row",
          "justify": "end",
          "align": "center",
          "children": ["refine_btn", "approve_btn"],
      },
      *_basic_button(
          "refine_btn",
          "Refine",
          {"event": {"name": "refine_proposal_outline", "context": refine_ctx}},
          "default",
      ),
      *_basic_button(
          "approve_btn",
          "Approve & Generate Deck",
          {
              "event": {
                  "name": "approve_outline_and_generate",
                  "context": approve_ctx,
              }
          },
          "primary",
      ),
      {
          "id": "outline_col",
          "component": "Column",
          "justify": "start",
          "align": "stretch",
          "children": col_children,
      },
  ])

  return [
      {
          "version": "v0.9",
          "createSurface": {
              "surfaceId": surface_id,
              "catalogId": a2ui.A2UI_BASIC_CATALOG_ID,
              "sendDataModel": True,
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


# Server-driven inline-editing events emitted by the Material outline card.
# These only toggle which inline block is shown; they never mutate the outline.
OUTLINE_OPEN_EDITOR_EVENT = "open_outline_section_editor"
OUTLINE_OPEN_DELETE_CONFIRM_EVENT = "open_outline_section_delete_confirm"
OUTLINE_OPEN_ADD_TOPIC_EVENT = "open_outline_add_topic"
OUTLINE_CANCEL_EDIT_EVENT = "cancel_outline_section_edit"
OUTLINE_VIEW_EVENTS = (
    OUTLINE_OPEN_EDITOR_EVENT,
    OUTLINE_OPEN_DELETE_CONFIRM_EVENT,
    OUTLINE_OPEN_ADD_TOPIC_EVENT,
    OUTLINE_CANCEL_EDIT_EVENT,
)

_FONT_SANS = "'Google Sans', 'Google Sans Text', Roboto, Arial, sans-serif"


def _normalize_outline_sections(
    agenda_sections: Optional[List[Any]],
) -> List[Dict[str, Any]]:
  """Normalizes agenda sections into {title, subtopics[list], slide_count[int]}."""
  sections: List[Dict[str, Any]] = []
  for idx, sec in enumerate(agenda_sections or [], start=1):
    if not isinstance(sec, dict):
      sec = {"title": str(sec)}
    title_val = str(sec.get("title") or f"Section {idx}").strip()
    subs = split_outline_subtopics(
        sec.get("subtopics") or sec.get("topics") or sec.get("parts") or []
    )
    if not subs:
      subs = [_DEFAULT_SUBTOPIC]
    try:
      slide_count = max(1, int(sec.get("slide_count") or len(subs) or 1))
    except (TypeError, ValueError):
      slide_count = max(1, len(subs))
    sections.append(
        {"title": title_val, "subtopics": subs, "slide_count": slide_count}
    )
  return sections


def _coerce_outline_index(raw: Any, n_sections: int) -> Optional[int]:
  """Returns a valid 0-based section index or None."""
  if raw is None or isinstance(raw, bool):
    return None
  try:
    pos = int(float(str(raw).strip()))
  except (TypeError, ValueError):
    return None
  return pos if 0 <= pos < n_sections else None


def _mat_text(
    comp_id: str,
    text: str,
    usage_hint: str = "body",
    style: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
  merged = {"fontFamily": _FONT_SANS, "margin": "0"}
  merged.update(style or {})
  return {
      "id": comp_id,
      "component": "MaterialText",
      "text": text,
      "usageHint": usage_hint,
      "style": merged,
  }


def _mat_button(
    comp_id: str,
    label: str,
    event_name: str,
    context: Dict[str, Any],
    kind: str = "filled",
) -> Dict[str, Any]:
  """Pill MaterialButton. kind: filled | tonal | outlined | text | danger."""
  style: Dict[str, Any] = {
      "fontFamily": _FONT_SANS,
      "fontWeight": "500",
      "borderRadius": "999px",
  }
  variant = "flat"
  if kind == "tonal":
    variant = "basic"
    style.update({
        "backgroundColor": "var(--mat-sys-secondary-container, #c2e7ff)",
        "color": "var(--mat-sys-on-secondary-container, #001d35)",
        "padding": "0 16px",
    })
  elif kind == "outlined":
    variant = "stroked"
  elif kind == "text":
    variant = "basic"
    style["color"] = "var(--mat-sys-on-surface-variant, #444746)"
  elif kind == "danger":
    style.update({
        "backgroundColor": "var(--mat-sys-error, #b3261e)",
        "color": "var(--mat-sys-on-error, #ffffff)",
    })
  return {
      "id": comp_id,
      "component": "MaterialButton",
      "label": label,
      "variant": variant,
      "style": style,
      "action": {"event": {"name": event_name, "context": context}},
  }


def _mat_input(
    comp_id: str,
    label: str,
    path: str,
    placeholder: str = "",
    input_type: str = "text",
    validation_regexp: str = "",
) -> Dict[str, Any]:
  comp: Dict[str, Any] = {
      "id": comp_id,
      "component": "MaterialInput",
      "label": label,
      "value": {"path": path},
      "type": input_type,
      "style": {"width": "100%"},
  }
  if placeholder:
    comp["placeholder"] = placeholder
  if validation_regexp:
    comp["validationRegexp"] = validation_regexp
  return comp


def _mat_row(
    comp_id: str,
    children: List[str],
    justify: str = "start",
    gap: str = "8px",
    extra_style: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
  style = {"gap": gap, "width": "100%", "alignItems": "center"}
  style.update(extra_style or {})
  return {
      "id": comp_id,
      "component": "MaterialRow",
      "justify": justify,
      "align": "center",
      "style": style,
      "children": children,
  }


def create_a2ui_v09_outline_material_messages(
    customer_name: str,
    agenda_sections: List[Dict[str, Any]],
    deck_strategy: str = "smart_hybrid",
    surface_id: str = "pitchgen-outline",
    sales_play: str = "",
    editing_index: Optional[int] = None,
    confirm_delete_index: Optional[int] = None,
    show_add_topic: bool = False,
) -> List[Dict[str, Any]]:
  """Generates the Material-catalog Proposal Outline card (server-driven inline editing).

  Visually matches the launcher / translate Material cards (outlined 16px
  MaterialCard, Google Sans, `var(--mat-sys-*)` tokens, pill buttons, logo
  row). Instead of client-side Modals, per-section Edit / Remove and Add topic
  are server-driven: the trigger buttons emit view-only events
  (`open_outline_section_editor`, `open_outline_section_delete_confirm`,
  `open_outline_add_topic`, `cancel_outline_section_edit`) and the agent
  re-renders this card (new surfaceId) with at most one inline editor block
  expanded, selected by `editing_index` / `confirm_delete_index` /
  `show_add_topic`. Mutations use `save_outline_section_edit`,
  `delete_outline_section` and `add_outline_section`. Refine / Approve keep
  the qa-p2 event names and contexts (approve never binds
  refinement_instructions).

  Args:
    customer_name: Target customer account name.
    agenda_sections: Outline sections (title, subtopics, slide_count).
    deck_strategy: Active deck strategy identifier.
    surface_id: Unique A2UI surface identifier for this card revision.
    sales_play: Optional sales play label shown in the header subtitle.
    editing_index: 0-based section index whose inline editor is expanded.
    confirm_delete_index: 0-based section index showing the remove confirm.
    show_add_topic: Whether the inline 'Add agenda topic' block is expanded.

  Returns:
    [createSurface, updateDataModel, updateComponents] v0.9 messages.
  """
  cust_label = str(customer_name or "").strip()
  if cust_label.lower() == "customer":
    cust_label = ""
  if isinstance(sales_play, (list, tuple)):
    sales_play = ", ".join(str(s).strip() for s in sales_play if str(s).strip())
  sp_label = str(sales_play or "").strip()

  sections = _normalize_outline_sections(agenda_sections)
  n_sections = len(sections)
  edit_pos = _coerce_outline_index(editing_index, n_sections)
  confirm_pos = _coerce_outline_index(confirm_delete_index, n_sections)
  if edit_pos is not None:
    # Only one inline block is expanded at a time.
    confirm_pos = None
    show_add_topic = False
  elif confirm_pos is not None:
    show_add_topic = False

  total_slides = sum(s["slide_count"] for s in sections)
  data_model: Dict[str, Any] = {
      "customer_name": customer_name or "Customer",
      "deck_strategy": deck_strategy or "smart_hybrid",
      "refinement_instructions": "",
      "new_topic_title": "",
      "new_topic_subtopics": "",
      "new_topic_slides": "1",
      # MaterialInput is single-line, so subtopics are '; '-separated.
      "sections": [
          {
              "title": s["title"],
              "subtopics_text": "; ".join(s["subtopics"]),
              "slide_count": str(s["slide_count"]),
          }
          for s in sections
      ],
  }

  subtitle_bits = [b for b in (cust_label, sp_label) if b]
  header_subtitle = " · ".join(subtitle_bits) or "Review your presentation"
  summary_text = (
      f"{n_sections} section{'s' if n_sections != 1 else ''} ·"
      f" {total_slides} target slide{'s' if total_slides != 1 else ''}, plus"
      " cover, agenda & closing. Edit, remove, or add agenda topics, refine"
      " with Gemini, then approve to build the deck."
  )

  base_ctx: Dict[str, Any] = {
      "customer_name": {"path": "/customer_name"},
      "deck_strategy": {"path": "/deck_strategy"},
  }

  col_children: List[str] = [
      "tool_logo_row",
      "outline_header_title",
      "outline_header_subtitle",
      "outline_summary",
      "header_divider",
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
          "children": ["outline_col"],
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
          "children": ["pitchgen_tool_logo"],
      },
      # Native Material logo pill: GE's Material catalog has no `Image` and
      # its MaterialImage blocks data: URIs, so the SVG logo never rendered.
      *a2ui.pitchgen_logo_components(),
      _mat_text(
          "outline_header_title",
          "Proposal Outline",
          "h3",
          {
              "fontSize": "18px",
              "fontWeight": "600",
              "color": "var(--mat-sys-on-surface, #1f1f1f)",
          },
      ),
      _mat_text(
          "outline_header_subtitle",
          header_subtitle,
          "body",
          {
              "fontSize": "14px",
              "fontWeight": "500",
              "color": "var(--mat-sys-primary, #0b57d0)",
          },
      ),
      _mat_text(
          "outline_summary",
          summary_text,
          "body",
          {
              "fontSize": "13px",
              "color": "var(--mat-sys-on-surface-variant, #444746)",
          },
      ),
      {
          "id": "header_divider",
          "component": "MaterialDivider",
          "style": {
              "borderTopColor": "var(--mat-sys-outline-variant, #e0e3e7)",
              "margin": "2px 0 6px 0",
          },
      },
  ]

  section_bindings: Dict[str, Any] = {}
  for idx, sec in enumerate(sections, start=1):
    pos = idx - 1
    sid = f"sec_{idx}"
    base_path = f"/sections/{pos}"
    section_bindings[f"sec_{idx}_title"] = {"path": f"{base_path}/title"}
    section_bindings[f"sec_{idx}_subtopics"] = {
        "path": f"{base_path}/subtopics_text"
    }
    col_children.append(f"{sid}_card")
    is_editing = pos == edit_pos
    is_confirming = pos == confirm_pos

    idx_ctx = dict(base_ctx)
    idx_ctx.update({"section_index": pos, "section_number": idx})

    card_border = (
        "1px solid var(--mat-sys-primary, #0b57d0)"
        if (is_editing or is_confirming)
        else "1px solid var(--mat-sys-outline-variant, #e1e3e1)"
    )
    components.append({
        "id": f"{sid}_card",
        "component": "MaterialCard",
        "appearance": "outlined",
        "style": {
            "padding": "16px",
            "borderRadius": "12px",
            "backgroundColor": "var(--mat-sys-surface-container-low, #f8fafd)",
            "border": card_border,
        },
        "children": [f"{sid}_col"],
    })
    components.append({
        "id": f"{sid}_header_row",
        "component": "MaterialRow",
        "justify": "start",
        "align": "center",
        "style": {"gap": "10px", "alignItems": "center"},
        "children": [f"{sid}_badge", f"{sid}_title"],
    })
    components.append(
        _mat_text(
            f"{sid}_badge",
            str(idx),
            "caption",
            {
                "display": "inline-block",
                "minWidth": "24px",
                "height": "24px",
                "lineHeight": "24px",
                "textAlign": "center",
                "borderRadius": "999px",
                "fontSize": "12px",
                "fontWeight": "600",
                "backgroundColor": "var(--mat-sys-primary-container, #d3e3fd)",
                "color": "var(--mat-sys-on-primary-container, #041e49)",
            },
        )
    )
    components.append(
        _mat_text(
            f"{sid}_title",
            "Edit section" if is_editing else sec["title"],
            "h4",
            {
                "fontSize": "15px",
                "fontWeight": "600",
                "color": "var(--mat-sys-on-surface, #1f1f1f)",
            },
        )
    )

    if is_editing:
      edit_ctx = dict(idx_ctx)
      edit_ctx.update({
          "section_title": {"path": f"{base_path}/title"},
          "subtopics_text": {"path": f"{base_path}/subtopics_text"},
          "slide_count": {"path": f"{base_path}/slide_count"},
      })
      components.extend([
          {
              "id": f"{sid}_col",
              "component": "MaterialColumn",
              "style": {"gap": "10px"},
              "children": [
                  f"{sid}_header_row",
                  f"{sid}_edit_title_input",
                  f"{sid}_edit_subtopics_input",
                  f"{sid}_edit_slides_input",
                  f"{sid}_edit_actions_row",
              ],
          },
          _mat_input(
              f"{sid}_edit_title_input", "Section title", f"{base_path}/title"
          ),
          _mat_input(
              f"{sid}_edit_subtopics_input",
              "Subtopics (separate with ;)",
              f"{base_path}/subtopics_text",
              placeholder="e.g., Current challenges; Business impact",
          ),
          _mat_input(
              f"{sid}_edit_slides_input",
              "Target slides",
              f"{base_path}/slide_count",
              input_type="number",
              validation_regexp=_SLIDE_COUNT_REGEXP,
          ),
          _mat_row(
              f"{sid}_edit_actions_row",
              [f"{sid}_edit_cancel_btn", f"{sid}_edit_save_btn"],
              justify="end",
          ),
          _mat_button(
              f"{sid}_edit_cancel_btn",
              "Cancel",
              OUTLINE_CANCEL_EDIT_EVENT,
              dict(idx_ctx),
              "text",
          ),
          _mat_button(
              f"{sid}_edit_save_btn",
              "Save",
              OUTLINE_SECTION_EDIT_EVENT,
              edit_ctx,
              "filled",
          ),
      ])
      continue

    sub_ids = [f"{sid}_sub_{s_i}" for s_i in range(len(sec["subtopics"]))]
    footer_id = f"{sid}_confirm_row" if is_confirming else f"{sid}_footer_row"
    components.append({
        "id": f"{sid}_col",
        "component": "MaterialColumn",
        "style": {"gap": "6px"},
        "children": [f"{sid}_header_row"] + sub_ids + [footer_id],
    })
    for s_i, sub_text in enumerate(sec["subtopics"]):
      components.append(
          _mat_text(
              sub_ids[s_i],
              f"• {sub_text}",
              "body",
              {
                  "fontSize": "13px",
                  "color": "var(--mat-sys-on-surface-variant, #444746)",
                  "margin": "0 0 0 34px",
              },
          )
      )
    slides_word = "slide" if sec["slide_count"] == 1 else "slides"
    if is_confirming:
      delete_ctx = dict(idx_ctx)
      delete_ctx["section_title"] = sec["title"]
      components.extend([
          _mat_row(
              footer_id,
              [
                  f"{sid}_confirm_text",
                  f"{sid}_confirm_cancel_btn",
                  f"{sid}_confirm_delete_btn",
              ],
              justify="end",
              extra_style={"marginTop": "6px"},
          ),
          _mat_text(
              f"{sid}_confirm_text",
              "Remove this section?",
              "body",
              {
                  "fontSize": "13px",
                  "fontWeight": "500",
                  "color": "var(--mat-sys-error, #b3261e)",
                  "marginRight": "auto",
              },
          ),
          _mat_button(
              f"{sid}_confirm_cancel_btn",
              "Cancel",
              OUTLINE_CANCEL_EDIT_EVENT,
              dict(idx_ctx),
              "text",
          ),
          _mat_button(
              f"{sid}_confirm_delete_btn",
              "Remove",
              OUTLINE_SECTION_DELETE_EVENT,
              delete_ctx,
              "danger",
          ),
      ])
    else:
      open_delete_ctx = dict(idx_ctx)
      open_delete_ctx["section_title"] = sec["title"]
      components.extend([
          _mat_row(
              footer_id,
              [f"{sid}_meta", f"{sid}_actions_row"],
              justify="spaceBetween",
              extra_style={"marginTop": "4px"},
          ),
          _mat_text(
              f"{sid}_meta",
              f"{sec['slide_count']} {slides_word}",
              "caption",
              {
                  "fontSize": "12px",
                  "fontWeight": "500",
                  "color": "var(--mat-sys-primary, #0b57d0)",
              },
          ),
          _mat_row(
              f"{sid}_actions_row",
              [f"{sid}_edit_btn", f"{sid}_delete_btn"],
              justify="end",
              extra_style={"width": "auto", "marginLeft": "auto"},
          ),
          _mat_button(
              f"{sid}_edit_btn",
              "Edit",
              OUTLINE_OPEN_EDITOR_EVENT,
              dict(idx_ctx),
              "tonal",
          ),
          _mat_button(
              f"{sid}_delete_btn",
              "Remove",
              OUTLINE_OPEN_DELETE_CONFIRM_EVENT,
              open_delete_ctx,
              "text",
          ),
      ])

  # --- Add agenda topic (inline block or tonal trigger) ---
  if show_add_topic:
    col_children.append("add_topic_card")
    add_ctx = dict(base_ctx)
    add_ctx.update({
        "new_topic_title": {"path": "/new_topic_title"},
        "new_topic_subtopics": {"path": "/new_topic_subtopics"},
        "new_topic_slides": {"path": "/new_topic_slides"},
    })
    components.extend([
        {
            "id": "add_topic_card",
            "component": "MaterialCard",
            "appearance": "outlined",
            "style": {
                "padding": "16px",
                "borderRadius": "12px",
                "backgroundColor": (
                    "var(--mat-sys-surface-container-low, #f8fafd)"
                ),
                "border": "1px solid var(--mat-sys-primary, #0b57d0)",
            },
            "children": ["add_topic_col"],
        },
        {
            "id": "add_topic_col",
            "component": "MaterialColumn",
            "style": {"gap": "10px"},
            "children": [
                "add_topic_heading",
                "new_topic_title_input",
                "new_topic_subtopics_input",
                "new_topic_slides_input",
                "add_topic_actions_row",
            ],
        },
        _mat_text(
            "add_topic_heading",
            "Add agenda topic",
            "h4",
            {
                "fontSize": "15px",
                "fontWeight": "600",
                "color": "var(--mat-sys-on-surface, #1f1f1f)",
            },
        ),
        _mat_input(
            "new_topic_title_input",
            "Topic title",
            "/new_topic_title",
            placeholder="e.g., Security & Trust",
        ),
        _mat_input(
            "new_topic_subtopics_input",
            "Subtopics (separate with ;)",
            "/new_topic_subtopics",
            placeholder="e.g., Zero Trust; Data residency",
        ),
        _mat_input(
            "new_topic_slides_input",
            "Target slides",
            "/new_topic_slides",
            input_type="number",
            validation_regexp=_SLIDE_COUNT_REGEXP,
        ),
        _mat_row(
            "add_topic_actions_row",
            ["add_topic_cancel_btn", "add_topic_confirm_btn"],
            justify="end",
        ),
        _mat_button(
            "add_topic_cancel_btn",
            "Cancel",
            OUTLINE_CANCEL_EDIT_EVENT,
            dict(base_ctx),
            "text",
        ),
        _mat_button(
            "add_topic_confirm_btn",
            "Add",
            OUTLINE_SECTION_ADD_EVENT,
            add_ctx,
            "filled",
        ),
    ])
  else:
    col_children.append("add_topic_row")
    components.extend([
        _mat_row("add_topic_row", ["add_topic_trigger_btn"], justify="start"),
        _mat_button(
            "add_topic_trigger_btn",
            "+ Add agenda topic",
            OUTLINE_OPEN_ADD_TOPIC_EVENT,
            dict(base_ctx),
            "tonal",
        ),
    ])

  # --- Refine + Approve (qa-p2 event names / contexts unchanged) ---
  refine_ctx: Dict[str, Any] = {
      "customer_name": {"path": "/customer_name"},
      "deck_strategy": {"path": "/deck_strategy"},
      "refinement_instructions": {"path": "/refinement_instructions"},
      "prompt": (
          f"Refine proposal outline for {customer_name}"
          if customer_name
          else "Refine proposal outline"
      ),
  }
  refine_ctx.update(section_bindings)
  # NOTE: approve must never bind refinement_instructions (qa-p2 invariant).
  approve_ctx: Dict[str, Any] = {
      "customer_name": {"path": "/customer_name"},
      "deck_strategy": {"path": "/deck_strategy"},
      "prompt": (
          "Approve outline and synthesize presentation deck"
          f" for {customer_name}"
          if customer_name
          else "Approve outline and synthesize presentation deck"
      ),
  }
  approve_ctx.update(section_bindings)

  col_children.extend(["footer_divider", "refinement_input", "actions_row"])
  components.extend([
      {
          "id": "footer_divider",
          "component": "MaterialDivider",
          "style": {
              "borderTopColor": "var(--mat-sys-outline-variant, #e0e3e7)",
              "margin": "6px 0 2px 0",
          },
      },
      _mat_input(
          "refinement_input",
          "Refine with Gemini (optional)",
          "/refinement_instructions",
          placeholder=(
              "e.g., Add a section on Zero Trust Security, merge sections 2 &"
              " 3, or emphasize CFO ROI"
          ),
      ),
      _mat_row(
          "actions_row",
          ["refine_btn", "approve_btn"],
          justify="end",
          gap="12px",
      ),
      _mat_button(
          "refine_btn",
          "Refine Outline",
          "refine_proposal_outline",
          refine_ctx,
          "outlined",
      ),
      _mat_button(
          "approve_btn",
          "Approve & Generate Deck",
          "approve_outline_and_generate",
          approve_ctx,
          "filled",
      ),
      {
          "id": "outline_col",
          "component": "MaterialColumn",
          "style": {"gap": "14px"},
          "children": col_children,
      },
  ])

  return [
      {
          "version": "v0.9",
          "createSurface": {
              "surfaceId": surface_id,
              "catalogId": a2ui.A2UI_MATERIAL_CATALOG_ID,
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


def create_a2ui_v09_outline_messages(
    customer_name: str,
    agenda_sections: List[Dict[str, Any]],
    deck_strategy: str = "smart_hybrid",
    surface_id: str = "pitchgen-outline",
    sales_play: str = "",
    outline_style: str = "material",
    editing_index: Optional[int] = None,
    confirm_delete_index: Optional[int] = None,
    show_add_topic: bool = False,
) -> List[Dict[str, Any]]:
  """Generates v0.9 Proposal Outline messages.

  `outline_style="material"` (default) renders the Material-catalog card with
  server-driven inline editing; `outline_style="basic"` renders the
  basic-catalog fallback with client-side Modals.
  """
  if str(outline_style or "").strip().lower() == "basic":
    return create_a2ui_v09_outline_basic_messages(
        customer_name=customer_name,
        agenda_sections=agenda_sections,
        deck_strategy=deck_strategy,
        surface_id=surface_id,
        sales_play=sales_play,
    )
  return create_a2ui_v09_outline_material_messages(
      customer_name=customer_name,
      agenda_sections=agenda_sections,
      deck_strategy=deck_strategy,
      surface_id=surface_id,
      sales_play=sales_play,
      editing_index=editing_index,
      confirm_delete_index=confirm_delete_index,
      show_add_topic=show_add_topic,
  )


def create_a2ui_outline_messages(
    customer_name: str,
    agenda_sections: List[Dict[str, Any]],
    deck_strategy: str = "smart_hybrid",
    surface_id: str = "pitchgen-outline",
    version: str = "v0.9",
    previous_surface_id: Optional[str] = None,
    previous_surface_ids: Optional[List[str]] = None,
    sales_play: str = "",
    outline_style: str = "material",
    editing_index: Optional[int] = None,
    confirm_delete_index: Optional[int] = None,
    show_add_topic: bool = False,
) -> List[Dict[str, Any]]:
  """Generates A2UI messages for Outline Review (defaults to v0.9).

  v0.9 renders the Material-catalog outline card with server-driven inline
  Edit / Remove / Add agenda topic blocks (`outline_style="basic"` selects the
  basic-catalog Modal fallback); v0.8 keeps the legacy fallback.

  Always assigns a unique surfaceId per outline card revision so Gemini
  Enterprise's A2uiService.anchorSurface (introducedSurfaceIds) anchors the
  refined outline card in the new turn's chat bubble, and deletes all
  previous outline surfaceIds so only a single outline card remains visible.
  """
  import os  # pylint: disable=g-import-not-at-top
  import uuid  # pylint: disable=g-import-not-at-top

  active_version = os.environ.get("A2UI_VERSION", version or "v0.9")
  effective_surface_id = surface_id
  if not effective_surface_id or effective_surface_id == "pitchgen-outline":
    effective_surface_id = f"pitchgen-outline-{uuid.uuid4().hex[:8]}"

  all_prev_ids: List[str] = []
  if previous_surface_id and str(previous_surface_id).strip():
    all_prev_ids.append(str(previous_surface_id).strip())
  if previous_surface_ids and isinstance(previous_surface_ids, list):
    for pid in previous_surface_ids:
      s_pid = str(pid or "").strip()
      if s_pid and s_pid not in all_prev_ids:
        all_prev_ids.append(s_pid)

  messages: List[Dict[str, Any]] = []
  for prev_id in all_prev_ids:
    if prev_id and prev_id != effective_surface_id:
      if active_version == "v0.8":
        messages.append({"deleteSurface": {"surfaceId": prev_id}})
      else:
        messages.append({
            "version": "v0.9",
            "deleteSurface": {"surfaceId": prev_id},
        })

  if active_version == "v0.8":
    messages.extend(
        create_a2ui_v08_outline_messages(
            customer_name=customer_name,
            agenda_sections=agenda_sections,
            deck_strategy=deck_strategy,
            surface_id=effective_surface_id,
        )
    )
    return messages

  messages.extend(
      create_a2ui_v09_outline_messages(
          customer_name=customer_name,
          agenda_sections=agenda_sections,
          deck_strategy=deck_strategy,
          surface_id=effective_surface_id,
          sales_play=sales_play,
          outline_style=outline_style,
          editing_index=editing_index,
          confirm_delete_index=confirm_delete_index,
          show_add_topic=show_add_topic,
      )
  )
  return messages
