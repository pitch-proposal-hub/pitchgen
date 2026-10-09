"""Gemini Enterprise A2UI Card for Slide Text Augmentation & Customization.

Implements Workflow 3:
- Focuses on augmentation and customization towards:
  - Target Customer / Account
  - Target Region / Geo (compliance, sovereign cloud, regional data centers)
  - Target Audience Persona (C-Level, Technical Architect, Line of Business)
  - Microindustry Vertical (e.g. QSR vs Luxury vs Grocery)
- Aligned to Slide Jobs logic and Governance rules:
  - Business_Value / ROI (100% full account customization)
  - Current_State (95% heavy customization on pain points)
  - Strategic_Partnership (85% joint vision, steering committee)
  - Path_to_Prod (75% roadmap, Cloud Adoption Framework)
  - Solution_Overview (60% value pillars to customer use case)
  - Proof_Points / Market_Trends (0-20% metric integrity protected)
- Supports Single Slide, Multi-Slide, or Full Deck scope.
"""

from typing import Any, Dict, List, Optional

try:
  from ge import a2ui
except ImportError:
  from src.ge import a2ui  # pylint: disable=g-import-not-at-top

SUPPORTED_LANGUAGES = [
    "Chinese (Simplified)",
    "Chinese (Traditional)",
    "Danish",
    "Dutch",
    "English",
    "Finnish",
    "French",
    "German",
    "Greek",
    "Indonesian",
    "Italian",
    "Japanese",
    "Korean",
    "Polish",
    "Portuguese",
    "Spanish",
    "Swedish",
    "Thai",
    # Additional global enterprise coverage
    "Arabic",
    "Hindi",
    "Turkish",
]

SLIDE_JOB_GOVERNANCE = {
    "Business_Value": {
        "name": "Business Value / ROI",
        "intensity": "100% Full Customization",
        "rule": (
            "Tailors financial metrics, ROI payback, and executive KPIs"
            " directly to the target account scale."
        ),
    },
    "Current_State": {
        "name": "Current State / Discovery",
        "intensity": "95% Heavy Customization",
        "rule": (
            "Focuses squarely on customer business challenges, legacy tech"
            " debt, and operational bottlenecks."
        ),
    },
    "Strategic_Partnership": {
        "name": "Strategic Partnership",
        "intensity": "85% Heavy Customization",
        "rule": (
            "Tailors joint strategic roadmap and executive steering committee"
            " while preserving Google trust principles."
        ),
    },
    "Path_to_Prod": {
        "name": "Path to Production / Roadmap",
        "intensity": "75% High Customization",
        "rule": (
            "Maps 30-60-90 day timelines and Cloud Adoption Framework stages to"
            " the target account."
        ),
    },
    "Solution_Overview": {
        "name": "Solution Overview / Architecture",
        "intensity": "60% Moderate Customization",
        "rule": (
            "Tailors capability pillars, architecture value, and benefits to"
            " the customer use case."
        ),
    },
    "Proof_Points": {
        "name": "Customer Proof Points / References",
        "intensity": "0-20% Metric Integrity Protected",
        "rule": (
            "Preserves verified customer metrics and quotes 100% verbatim;"
            " bridges strictly via the takeaway headline."
        ),
    },
    "Market_Trends": {
        "name": "Market Trends & Benchmarks",
        "intensity": "Qualitative Aligned / Data Protected",
        "rule": (
            "Aligns industry trends to the vertical; preserves cited analyst"
            " figures (Gartner/IDC/McKinsey) verbatim."
        ),
    },
}


def create_provide_deck_prompt_card(
    customer_name: str = "",
    default_url: str = "",
) -> Dict[str, Any]:
  """Builds a prompt card requesting the user to provide a deck when none is active on Canvas."""
  fields = [
      {
          "id": "presentation_url",
          "type": "text",
          "label": "Google Slides Presentation Link or ID",
          "value": default_url,
          "placeholder": (
              "https://docs.google.com/presentation/d/... or Presentation ID"
          ),
          "required": True,
      },
      {
          "id": "target_customer",
          "type": "text",
          "label": "Target Account / Customer (Optional)",
          "value": customer_name,
          "placeholder": "e.g. Target, LVMH, Deutsche Bank",
          "required": False,
      },
  ]

  actions = [
      {
          "id": "btn_load_and_transform",
          "label": "🚀 Load to Canvas & Transform",
          "style": "primary",
          "action": {
              "type": "a2ui_action",
              "actionName": "transform",
              "parameters": {
                  "customer_name": customer_name,
              },
          },
      },
      {
          "id": "btn_create_new_deck",
          "label": "➕ Start New Pitch Deck",
          "style": "secondary",
          "action": {
              "type": "a2ui_action",
              "actionName": "intake",
              "parameters": {},
          },
      },
  ]

  return {
      "type": "card",
      "title": "🪄 Transform Deck: Select or Provide Presentation",
      "subtitle": "Deck Required • No active presentation found on Canvas",
      "metadata": {"mimeType": a2ui.A2UI_MIME_TYPE},
      "sections": [
          {
              "type": "info_banner",
              "text": (
                  "⚠️ No Active Presentation on Canvas: To polish tone or"
                  " transform slide copy, please provide a Google Slides"
                  " presentation URL or ID below, or generate a new pitch deck"
                  " first."
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


def create_a2ui_v09_transform_text_messages(
    presentation_url_or_id: str = "",
    custom_instructions: str = "",
    customer_name: str = "",
    full_deck_scope: Optional[List[str]] = None,
    target_slide_indices: str = "",
    industry: Optional[Any] = None,
    audience: Optional[Any] = None,
    transform_scope_mode: str = "text_only",
    surface_id: str = "pitchgen-transform-text",
    **kwargs: Any,
) -> List[Dict[str, Any]]:
  """Generates the canonical A2UI v0.9 Material Catalog JSON array for the consolidated Transform Slide / Deck card ('pitchgen-transform-text')."""
  font_sans = "'Google Sans', 'Google Sans Text', Roboto, Arial, sans-serif"
  resolved_pres = presentation_url_or_id or str(
      kwargs.get("presentation_id") or ""
  )
  raw_scope_mode = (
      str(transform_scope_mode or kwargs.get("transform_mode") or "text_only")
      .strip()
      .lower()
  )
  if raw_scope_mode in ("images_only", "image_only", "visuals_only", "images"):
    resolved_scope_mode = "images_only"
  elif raw_scope_mode in (
      "gifs_only",
      "gif_only",
      "gifs",
      "animated_gifs",
      "video_to_video",
  ):
    resolved_scope_mode = "gifs_only"
  elif raw_scope_mode in ("both", "text_and_images", "all"):
    resolved_scope_mode = "both"
  else:
    resolved_scope_mode = "text_only"

  if full_deck_scope is None:
    resolved_full_deck = (
        []
        if (target_slide_indices and str(target_slide_indices).strip())
        else ["full_deck"]
    )
  elif isinstance(full_deck_scope, list):
    resolved_full_deck = (
        []
        if (target_slide_indices and str(target_slide_indices).strip())
        else full_deck_scope
    )
  elif isinstance(full_deck_scope, bool):
    resolved_full_deck = (
        []
        if (target_slide_indices and str(target_slide_indices).strip())
        else (["full_deck"] if full_deck_scope else [])
    )
  elif str(full_deck_scope).strip().lower() in ("full_deck", "true", "all"):
    resolved_full_deck = (
        []
        if (target_slide_indices and str(target_slide_indices).strip())
        else ["full_deck"]
    )
  else:
    resolved_full_deck = []

  if isinstance(industry, list):
    clean_ind = [
        str(x).strip()
        for x in industry
        if str(x).strip()
        and str(x).strip().lower() not in ("industry", "industry vertical")
    ]
    resolved_industry = clean_ind[0] if clean_ind else ""
  elif (
      isinstance(industry, str)
      and industry.strip()
      and industry.strip().lower() not in ("industry", "industry vertical")
  ):
    resolved_industry = industry.strip()
  else:
    resolved_industry = ""

  if isinstance(audience, list):
    clean_aud = [
        str(x).strip()
        for x in audience
        if str(x).strip()
        and str(x).strip().lower()
        not in ("audience", "target audience persona")
    ]
    resolved_audience = clean_aud[0] if clean_aud else ""
  elif (
      isinstance(audience, str)
      and audience.strip()
      and audience.strip().lower()
      not in ("audience", "target audience persona")
  ):
    parts = [
        p.strip()
        for p in audience.split(",")
        if p.strip()
        and p.strip().lower() not in ("audience", "target audience persona")
    ]
    resolved_audience = parts[0] if parts else ""
  else:
    resolved_audience = ""

  transform_scope_options = [
      {
          "label": "✍️ Text & Narrative Only (Editable Shapes)",
          "value": "text_only",
      },
      {
          "label": "🖼️ In-Slide Images Only (Replace Picture Shapes)",
          "value": "images_only",
      },
      {
          "label": "🎬 In-Slide GIFs Only (Animated Video-to-Video)",
          "value": "gifs_only",
      },
      {
          "label": "✨ Both Text & In-Slide Visuals (Images + GIFs)",
          "value": "both",
      },
  ]

  industry_options = [
      {"label": "Industry Vertical", "value": ""},
      {"label": "Automotive", "value": "Automotive"},
      {"label": "Consumer Packaged Goods", "value": "Consumer Packaged Goods"},
      {
          "label": "Financial Services & Insurance",
          "value": "Financial Services & Insurance",
      },
      {"label": "Games", "value": "Games"},
      {"label": "Healthcare", "value": "Healthcare"},
      {"label": "Int'l Public Sector", "value": "Int'l Public Sector"},
      {"label": "Life Sciences", "value": "Life Sciences"},
      {"label": "Logistics", "value": "Logistics"},
      {"label": "Manufacturing", "value": "Manufacturing"},
      {"label": "Media & Entertainment", "value": "Media & Entertainment"},
      {"label": "Power & Energy", "value": "Power & Energy"},
      {"label": "Retail & Consumer", "value": "Retail & Consumer"},
      {"label": "Retail & CPG", "value": "Retail & CPG"},
      {"label": "Software & Internet", "value": "Software & Internet"},
      {"label": "Telecommunications", "value": "Telecommunications"},
      {"label": "Travel & Hospitality", "value": "Travel & Hospitality"},
      {"label": "Marketing", "value": "Marketing"},
      {"label": "Supply Chain", "value": "Supply Chain"},
      {"label": "Sustainability", "value": "Sustainability"},
  ]

  audience_options = [
      {"label": "Target Audience Persona", "value": ""},
      {
          "label": "C-Level / Executive Leadership",
          "value": "C-Level / Executive Leadership",
      },
      {
          "label": "CDO (Chief Data Officer)",
          "value": "CDO (Chief Data Officer)",
      },
      {
          "label": "CEO (Chief Executive Officer)",
          "value": "CEO (Chief Executive Officer)",
      },
      {
          "label": "CFO (Chief Financial Officer)",
          "value": "CFO (Chief Financial Officer)",
      },
      {
          "label": "CIO (Chief Information Officer)",
          "value": "CIO (Chief Information Officer)",
      },
      {
          "label": "CISO (Chief Information Security Officer)",
          "value": "CISO (Chief Information Security Officer)",
      },
      {
          "label": "CMO (Chief Marketing Officer)",
          "value": "CMO (Chief Marketing Officer)",
      },
      {
          "label": "CTO (Chief Technology Officer)",
          "value": "CTO (Chief Technology Officer)",
      },
      {
          "label": "ITDM (IT Decision Maker)",
          "value": "ITDM (IT Decision Maker)",
      },
      {"label": "Line of Business", "value": "Line of Business"},
      {
          "label": "Procurement & Purchasing",
          "value": "Procurement & Purchasing",
      },
      {
          "label": "Cloud & Solution Architects",
          "value": "Cloud & Solution Architects",
      },
      {
          "label": "Developers & Engineers",
          "value": "Developers & Engineers",
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
              "transform_scope_mode_select",
              "custom_instructions_input",
              "row_account_scope",
              "industry_audience_row",
              "btn_transform_submit",
          ],
      },
      {
          "id": "header_title",
          "component": "MaterialText",
          "text": "🪄 Transform Slide / Deck (Text & In-Slide Images)",
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
          "text": (
              f"Transformed {int(kwargs.get('slides_modified') or 0)} slide(s)"
              f" in active deck {resolved_pres}. Adjust parameters below to run"
              " another slide or deck transformation."
              if int(kwargs.get("slides_modified") or 0) > 0 and resolved_pres
              else (
                  "Rewrite editable slide copy, replace embedded in-slide"
                  " picture shapes, or adapt both across any slide or full deck"
                  " while preserving native Google Slides layouts and verified"
                  " proof points."
              )
          ),
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
          "value": {"path": "/presentation_url_or_id"},
      },
      {
          "id": "transform_scope_mode_select",
          "component": "MaterialSelect",
          "label": "What to Transform",
          "placeholder": "Select Transformation Scope",
          "value": {"path": "/transform_scope_mode"},
          "options": transform_scope_options,
      },
      {
          "id": "custom_instructions_input",
          "component": "MaterialInput",
          "label": "Transform Instructions / Customization Criteria *",
          "placeholder": (
              "e.g., Tailor for a retail CFO audience, condense bullets to 12"
              " words max, or replace in-slide visuals with retail store"
              " telemetry"
          ),
          "value": {"path": "/custom_instructions"},
      },
      {
          "id": "row_account_scope",
          "component": "MaterialRow",
          "style": {"gap": "12px", "width": "100%"},
          "children": ["customer_name_input", "target_slides_input"],
      },
      {
          "id": "customer_name_input",
          "component": "MaterialInput",
          "label": "Customer / Account Name",
          "placeholder": "e.g., Target, LVMH",
          "value": {"path": "/customer_name"},
          "weight": 1,
      },
      {
          "id": "target_slides_input",
          "component": "MaterialInput",
          "label": "Target Slides (Blank = Full Deck, or e.g. 2, 4-6)",
          "placeholder": "All slides (Full Deck) or e.g., 2, 4-6",
          "value": {"path": "/target_slide_indices"},
          "weight": 1,
      },
      {
          "id": "industry_audience_row",
          "component": "MaterialRow",
          "style": {"gap": "12px", "width": "100%"},
          "children": ["industry_select", "audience_select"],
      },
      {
          "id": "industry_select",
          "component": "MaterialSelect",
          "label": "Industry Vertical",
          "placeholder": "Industry Vertical",
          "value": {"path": "/industry"},
          "options": industry_options,
          "weight": 1,
      },
      {
          "id": "audience_select",
          "component": "MaterialSelect",
          "label": "Target Audience Persona",
          "placeholder": "Target Audience Persona",
          "value": {"path": "/audience"},
          "options": audience_options,
          "weight": 1,
      },
      {
          "id": "btn_transform_submit",
          "component": "MaterialButton",
          "label": "🪄 Transform Slide / Deck",
          "variant": "flat",
          "style": {
              "fontFamily": font_sans,
              "fontWeight": "500",
              "borderRadius": "999px",
          },
          "action": {
              "event": {
                  "name": "transform_slide_text",
                  "context": {
                      "presentation_url_or_id": {
                          "path": "/presentation_url_or_id"
                      },
                      "transform_scope_mode": {"path": "/transform_scope_mode"},
                      "custom_instructions": {"path": "/custom_instructions"},
                      "customer_name": {"path": "/customer_name"},
                      "full_deck_scope": {"path": "/full_deck_scope"},
                      "target_slide_indices": {"path": "/target_slide_indices"},
                      "industry": {"path": "/industry"},
                      "audience": {"path": "/audience"},
                  },
              }
          },
      },
  ]

  data_model = {
      "presentation_url_or_id": resolved_pres,
      "transform_scope_mode": resolved_scope_mode,
      "custom_instructions": custom_instructions or "",
      "customer_name": customer_name or "",
      "full_deck_scope": resolved_full_deck,
      "target_slide_indices": str(target_slide_indices or ""),
      "industry": resolved_industry,
      "audience": resolved_audience,
  }

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


def create_a2ui_transform_text_messages(
    presentation_url_or_id: str = "",
    custom_instructions: str = "",
    customer_name: str = "",
    full_deck_scope: Optional[List[str]] = None,
    target_slide_indices: str = "",
    industry: Optional[Any] = None,
    audience: Optional[Any] = None,
    transform_scope_mode: str = "text_only",
    surface_id: str = "pitchgen-transform-text",
    **kwargs: Any,
) -> List[Dict[str, Any]]:
  """Generates A2UI v0.9 messages for the Transform Slide / Deck card ('pitchgen-transform-text')."""
  return create_a2ui_v09_transform_text_messages(
      presentation_url_or_id=presentation_url_or_id,
      custom_instructions=custom_instructions,
      customer_name=customer_name,
      full_deck_scope=full_deck_scope,
      target_slide_indices=target_slide_indices,
      industry=industry,
      audience=audience,
      transform_scope_mode=transform_scope_mode,
      surface_id=surface_id,
      **kwargs,
  )


def create_text_transform_card(
    presentation_id: str = "",
    scope: str = "current_slide",
    selected_slide_index: int = 1,
    slide_job: str = "Solution_Overview",
    customer_name: str = "",
    region: str = "AMER",
    audience: str = "C-Level / Executive Leadership",
    language: str = "English",
    deck_url: str = "",
    criteria: str = "",
    indices: str = "",
    industry: str = "",
    custom_instructions: str = "",
    transform_scope_mode: str = "text_only",
    **kwargs: Any,
) -> Dict[str, Any]:
  """Constructs the A2UI card for Account Augmentation & Customization."""
  if not presentation_id and deck_url:
    presentation_id = a2ui.extract_presentation_id(deck_url) or deck_url
  resolved_criteria = custom_instructions or criteria
  if indices and indices.strip() and indices.strip().lower() not in ("all", ""):
    slide_range_val = indices.strip()
  else:
    slide_range_val = str(selected_slide_index)
  job_info = SLIDE_JOB_GOVERNANCE.get(
      slide_job,
      {
          "name": slide_job,
          "intensity": "85% Account Customization",
          "rule": "Tailors narrative points directly to the target account.",
      },
  )

  scope_options = [
      {
          "value": "current_slide",
          "label": f"Current Slide (Slide {selected_slide_index})",
          "selected": scope == "current_slide",
      },
      {
          "value": "multi_slide",
          "label": "Multi-Slide Selection (e.g. 2, 4-6)",
          "selected": scope == "multi_slide",
      },
      {
          "value": "full_deck",
          "label": "Full Presentation Deck",
          "selected": scope == "full_deck",
      },
  ]

  job_options = [
      {
          "value": k,
          "label": f"{v['name']} ({v['intensity']})",
          "selected": k == slide_job,
      }
      for k, v in SLIDE_JOB_GOVERNANCE.items()
  ]

  fields = [
      {
          "id": "presentation_id",
          "type": "text",
          "label": "Target Presentation (Active Canvas Deck)",
          "value": presentation_id,
          "placeholder": "Presentation ID or Google Slides URL",
          "required": True,
      },
      {
          "id": "transform_scope",
          "type": "select",
          "label": "Transformation Scope",
          "value": scope,
          "options": scope_options,
      },
      {
          "id": "slide_range",
          "type": "text",
          "label": "Slide Range (if Multi-Slide selected)",
          "value": slide_range_val,
          "placeholder": "e.g. 2, 4-6",
      },
      {
          "id": "target_customer",
          "type": "text",
          "label": "Target Account / Customer",
          "value": customer_name,
          "placeholder": "e.g. Target, LVMH, Deutsche Bank",
          "required": True,
      },
      {
          "id": "target_region",
          "type": "select",
          "label": "Regional Localization & Compliance",
          "value": region,
          "options": [
              "AMER",
              "EMEA (GDPR/DORA)",
              "APAC",
              "LATAM",
              "Japan (FISC)",
          ],
      },
      {
          "id": "target_audience",
          "type": "select",
          "label": "Target Audience Persona",
          "value": audience or "C-Level / Executive Leadership",
          "options": [
              "C-Level / Executive Leadership",
              "Technical Architect (APIs, Latency, Infrastructure)",
              "Line of Business (Operational Velocity, Productivity)",
              "IT Platform & Cloud Operations",
          ],
      },
      {
          "id": "slide_job",
          "type": "select",
          "label": "Slide Job Classification",
          "value": slide_job,
          "options": job_options,
      },
      {
          "id": "target_language",
          "type": "select",
          "label": "Language / Translation (18 Languages)",
          "value": language,
          "options": SUPPORTED_LANGUAGES,
      },
      {
          "id": "custom_instructions",
          "type": "textarea",
          "label": "Specific Augmentation Guidance",
          "value": resolved_criteria,
          "placeholder": (
              "e.g. Emphasize multi-cloud zero-trust security and retail margin"
              " optimization..."
          ),
      },
  ]

  actions = [{
      "id": "btn_execute_transform",
      "label": "✨ Augment & Transform Slide Text",
      "style": "primary",
      "action": {
          "type": "a2ui_action",
          "actionName": "transform_slide_text",
          "parameters": {
              "presentation_id": presentation_id,
              "scope": scope,
              "slide_range": slide_range_val,
              "customer_name": customer_name,
              "region": region,
              "audience": audience or "C-Level / Executive Leadership",
              "slide_job": slide_job,
              "language": language,
              "custom_instructions": resolved_criteria,
          },
      },
  }]

  v09_messages = create_a2ui_v09_transform_text_messages(
      presentation_url_or_id=presentation_id,
      custom_instructions=resolved_criteria,
      customer_name=customer_name,
      full_deck_scope=["full_deck"] if scope == "full_deck" else [],
      target_slide_indices=""
      if scope == "full_deck"
      else (slide_range_val if slide_range_val else ""),
      industry=industry,
      audience=audience,
  )

  res = {
      "type": "card",
      "title": "🪄 Slide Text Augmentation & Customization",
      "subtitle": (
          f"Active Canvas Deck: {presentation_id} • {job_info['name']} •"
          f" {job_info['intensity']}"
      ),
      "metadata": {"mimeType": a2ui.A2UI_MIME_TYPE},
      "a2ui_v09_messages": v09_messages,
      "canvas_messages": v09_messages,
      "sections": [
          {
              "type": "info_banner",
              "text": (
                  f"🎯 Active Canvas Deck: {presentation_id} • Slide Job"
                  f" Governance: {job_info['rule']}"
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


def create_a2ui_v09_transform_messages(
    presentation_id: str = "",
    presentation_url_or_id: str = "",
    customer_name: str = "",
    criteria: str = "",
    indices: str = "",
    language: str = "English",
    slides_modified: int = 0,
    surface_id: str = "pitchgen-transform-slide",
    **kwargs: Any,
) -> List[Dict[str, Any]]:
  """Delegates to the consolidated Transform Slide / Deck (Text & In-Slide Images) card so the legacy 'Transform Slide & Adapt Structure' card is never shown."""
  del language  # Handled by dedicated Translate card
  resolved_pres = presentation_id or presentation_url_or_id or ""
  clean_indices = (
      ""
      if str(indices or "").strip().lower()
      in ("all", "full_deck", "entire_deck")
      else str(indices or "").strip()
  )
  return create_a2ui_v09_transform_text_messages(
      presentation_url_or_id=resolved_pres,
      custom_instructions=criteria
      or str(kwargs.get("custom_instructions") or ""),
      customer_name=customer_name,
      target_slide_indices=clean_indices,
      industry=kwargs.get("industry"),
      audience=kwargs.get("audience"),
      transform_scope_mode=str(
          kwargs.get("transform_scope_mode") or "text_only"
      ),
      surface_id=surface_id,
      slides_modified=slides_modified,
  )


def create_a2ui_transform_messages(
    presentation_id: str = "",
    presentation_url_or_id: str = "",
    customer_name: str = "",
    criteria: str = "",
    indices: str = "",
    language: str = "English",
    slides_modified: int = 0,
    surface_id: str = "pitchgen-transform-slide",
    **kwargs: Any,
) -> List[Dict[str, Any]]:
  """Version-aware wrapper returning A2UI v0.9 transform messages."""
  return create_a2ui_v09_transform_messages(
      presentation_id=presentation_id,
      presentation_url_or_id=presentation_url_or_id,
      customer_name=customer_name,
      criteria=criteria,
      indices=indices,
      language=language,
      slides_modified=slides_modified,
      surface_id=surface_id,
      **kwargs,
  )


def create_a2ui_v09_translate_messages(
    presentation_id: str = "",
    presentation_url_or_id: str = "",
    target_language: str = "Spanish",
    target_slide_indices: str = "",
    customer_name: str = "",
    slides_modified: int = 0,
    surface_id: str = "pitchgen-translate",
    **kwargs: Any,
) -> List[Dict[str, Any]]:
  """Delegates to the canonical Translate Presentation card in a2ui_translate."""
  del customer_name
  try:
    from pitchgen.ge.a2ui_translate import (
        create_a2ui_v09_translate_messages as _canonical_translate_msgs,
    )
  except ImportError:
    from ge.a2ui_translate import (  # pylint: disable=g-import-not-at-top
        create_a2ui_v09_translate_messages as _canonical_translate_msgs,
    )
  return _canonical_translate_msgs(
      presentation_url_or_id=presentation_url_or_id or presentation_id,
      translate_instructions=str(kwargs.get("translate_instructions") or ""),
      target_language=target_language,
      target_slide_indices=target_slide_indices,
      surface_id=surface_id,
      slides_modified=slides_modified,
  )


def create_a2ui_translate_messages(
    presentation_id: str = "",
    presentation_url_or_id: str = "",
    target_language: str = "Spanish",
    target_slide_indices: str = "",
    customer_name: str = "",
    slides_modified: int = 0,
    surface_id: str = "pitchgen-translate",
    **kwargs: Any,
) -> List[Dict[str, Any]]:
  """Version-aware wrapper returning A2UI v0.9 translate messages."""
  return create_a2ui_v09_translate_messages(
      presentation_id=presentation_id,
      presentation_url_or_id=presentation_url_or_id,
      target_language=target_language,
      target_slide_indices=target_slide_indices,
      customer_name=customer_name,
      slides_modified=slides_modified,
      surface_id=surface_id,
      **kwargs,
  )


def create_a2ui_v09_generate_slide_messages(
    presentation_id: str = "",
    presentation_url_or_id: str = "",
    slide_topic: str = "",
    customer_name: str = "",
    slide_job: str = "",
    surface_id: str = "pitchgen-generate-slide",
    **kwargs: Any,
) -> List[Dict[str, Any]]:
  """Generates canonical A2UI v0.9 messages for the Generate Single Slide card ('pitchgen-generate-slide')."""
  del kwargs  # Unused
  font_sans = "'Google Sans', 'Google Sans Text', Roboto, Arial, sans-serif"
  resolved_pres = presentation_id or presentation_url_or_id or ""
  job_options = [
      {"label": "Slide Type / Layout Governance", "value": ""},
  ] + [
      {"label": f"{v['name']} ({v['intensity']})", "value": k}
      for k, v in SLIDE_JOB_GOVERNANCE.items()
  ]
  effective_job = slide_job if slide_job in SLIDE_JOB_GOVERNANCE else ""
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
              "path": "/generate_slide",
              "value": {
                  "presentation_id": resolved_pres,
                  "slide_topic": slide_topic or "",
                  "customer_name": customer_name or "",
                  "slide_job": effective_job,
              },
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
                          "padding": "24px",
                          "borderRadius": "16px",
                          "backgroundColor": "var(--mat-sys-surface, #ffffff)",
                          "border": (
                              "1px solid var(--mat-sys-outline-variant,"
                              " #dadce0)"
                          ),
                      },
                      "children": ["main-col"],
                  },
                  {
                      "id": "main-col",
                      "component": "MaterialColumn",
                      "style": {"gap": "14px"},
                      "children": [
                          "header-txt",
                          "sub-txt",
                          "divider-1",
                          "input-topic",
                          "row-slide-meta",
                          "input-deck-id",
                          "btn-generate-slide",
                      ],
                  },
                  {
                      "id": "header-txt",
                      "component": "MaterialText",
                      "text": "➕ Generate Custom Single Slide",
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
                      "text": (
                          "Synthesize a bespoke executive slide with"
                          " tailored layout, bullet copy, and speaker notes."
                      ),
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
                  {
                      "id": "input-topic",
                      "component": "MaterialInput",
                      "label": "Slide Topic & Key Message *",
                      "placeholder": (
                          "e.g., Executive ROI summary for migrating legacy"
                          " data warehouses to BigQuery & Gemini Enterprise"
                      ),
                      "value": {"path": "/generate_slide/slide_topic"},
                  },
                  {
                      "id": "row-slide-meta",
                      "component": "MaterialRow",
                      "style": {"gap": "12px", "width": "100%"},
                      "children": ["input-customer", "select-slide-job"],
                  },
                  {
                      "id": "input-customer",
                      "component": "MaterialInput",
                      "label": "Customer / Account Name (Optional)",
                      "placeholder": "e.g., Target, LVMH",
                      "value": {"path": "/generate_slide/customer_name"},
                      "weight": 1,
                  },
                  {
                      "id": "select-slide-job",
                      "component": "MaterialSelect",
                      "label": "Slide Type / Layout Governance",
                      "placeholder": "Slide Type / Layout Governance",
                      "value": {"path": "/generate_slide/slide_job"},
                      "options": job_options,
                      "weight": 1,
                  },
                  {
                      "id": "input-deck-id",
                      "component": "MaterialInput",
                      "label": "Target Google Slides Deck ID / URL (Optional)",
                      "placeholder": (
                          "Paste Google Slides URL/ID to append slide directly"
                      ),
                      "value": {"path": "/generate_slide/presentation_id"},
                  },
                  {
                      "id": "btn-generate-slide",
                      "component": "MaterialButton",
                      "label": "✨ Synthesize Custom Slide",
                      "variant": "flat",
                      "style": {
                          "fontFamily": font_sans,
                          "fontWeight": "500",
                          "borderRadius": "999px",
                      },
                      "action": {
                          "event": {
                              "name": "generate_single_slide",
                              "context": {
                                  "slide_topic": {
                                      "path": "/generate_slide/slide_topic"
                                  },
                                  "customer_name": {
                                      "path": "/generate_slide/customer_name"
                                  },
                                  "slide_job": {
                                      "path": "/generate_slide/slide_job"
                                  },
                                  "presentation_id": {
                                      "path": "/generate_slide/presentation_id"
                                  },
                              },
                          }
                      },
                  },
              ],
          },
      },
  ]


def create_a2ui_generate_slide_messages(
    presentation_id: str = "",
    presentation_url_or_id: str = "",
    slide_topic: str = "",
    customer_name: str = "",
    slide_job: str = "",
    surface_id: str = "pitchgen-generate-slide",
    **kwargs: Any,
) -> List[Dict[str, Any]]:
  """Version-aware wrapper returning A2UI v0.9 generate slide messages."""
  return create_a2ui_v09_generate_slide_messages(
      presentation_id=presentation_id,
      presentation_url_or_id=presentation_url_or_id,
      slide_topic=slide_topic,
      customer_name=customer_name,
      slide_job=slide_job,
      surface_id=surface_id,
      **kwargs,
  )
