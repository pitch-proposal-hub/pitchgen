"""Gemini Enterprise A2UI Card Generator for GTM Intake & Strategy Selection.

Implements Workflow 1: Captures full user popup fields:
- User Prompt / Business Context
- Customer / Account Name
- Sales Plays
- Industry & Microindustry
- Audience Persona
- Region / Geo
- Opportunity ID / ER Number
- 3 Deck Strategies (CloudHub, Smart Hybrid, Bespoke Custom)
- Deck Length (Brief, Standard, Comprehensive)
- Context File Attachments (Drive / Uploads)
"""

from typing import Any, Dict, List, Optional

A2UI_MIME_TYPE = "application/json+a2ui"
A2UI_GE_COMPOSITE_CATALOG_ID = (
    "https://a2ui.org/specification/v0_9/material_catalog.json"
)


SALES_PLAYS_BY_PRACTICE_AREA: Dict[str, List[str]] = {
    "AI": [
        "Gemini Enterprise for Customer Experience",
        "Gemini Enterprise for Customer Experience - Customer Service",
        "Leverage Generative Media in Your Business",
        "Scale AI Apps and Agents",
        "Your Business, Your Models",
    ],
    "Agentic Workplace Transformation": [
        "Lead the Agentic Workplace Transformation",
        "Lead the Agentic Workplace Transformation - Gemini Enterprise",
        "Lead the Agentic Workplace Transformation - Google Workspace",
    ],
    "Data": [
        "Agentic Data Cloud",
        "Migrate, Modernize, and Build with Data Cloud",
    ],
    "Infrastructure": [
        "AI Infrastructure",
        "Enterprise Platform of Choice: Oracle",
        "Enterprise Platform of Choice: SAP",
        "Enterprise Platform of Choice: VMware",
        "Enterprise Storage (GCNV)",
        "Google Distributed Cloud (GDC)",
        "High Performance Computing (HPC)",
        "Managed Global WAN (Cloud WAN)",
        "Migrate, Modernize and Build",
        "Modern Compute (ARM)",
        "Sovereign",
    ],
    "Security": [
        "Achieve Resilience Together with Mandiant",
        "Agentic Defense with Google Security",
        "Cybershield",
        "SOC Transformation",
        "Secure Innovation with Google Cloud",
    ],
}

DEFAULT_SALES_PLAYS: List[str] = [
    play
    for plays in SALES_PLAYS_BY_PRACTICE_AREA.values()
    for play in plays
]

GROUPED_SALES_PLAY_OPTIONS: List[Dict[str, str]] = [
    {"label": f"{practice_area} — {play}", "value": play}
    for practice_area, plays in SALES_PLAYS_BY_PRACTICE_AREA.items()
    for play in plays
]


_COMMA_SALES_PLAY_MAP = (
    (
        "migrate, modernize, and build with data cloud",
        "Migrate, Modernize, and Build with Data Cloud",
    ),
    (
        "migrate, modernize and build with data cloud",
        "Migrate, Modernize, and Build with Data Cloud",
    ),
    (
        "migrate, modernize and build",
        "Migrate, Modernize and Build",
    ),
    (
        "migrate, modernize, and build",
        "Migrate, Modernize and Build",
    ),
    (
        "your business, your models",
        "Your Business, Your Models",
    ),
)


def normalize_sales_play_value(sales_play: str) -> str:
  """Normalizes legacy or Practice-Area-prefixed sales play strings to canonical names."""
  clean = str(sales_play or "").strip()
  if not clean or clean.lower() in (
      "none",
      "null",
      "undefined",
      "➕ none / single sales play",
      "none / single sales play",
      "✨ auto-detect sales play",
      "auto-detect sales play",
  ):
    return ""
  if " — " in clean:
    prefix, remainder = clean.split(" — ", 1)
    if prefix.strip() in SALES_PLAYS_BY_PRACTICE_AREA:
      clean = remainder.strip()
  if clean == "Scale AI Apps & Agents":
    return "Scale AI Apps and Agents"
  return clean


def normalize_sales_plays_list(
    sales_play: Any = "", secondary_sales_play: Any = ""
) -> List[str]:
  """Splits and normalizes 1 or more sales plays while preserving comma-containing play names."""
  import re  # pylint: disable=g-import-not-at-top

  raw_items: List[Any] = []
  for src in (sales_play, secondary_sales_play):
    if not src:
      continue
    if isinstance(src, (list, tuple, set)):
      raw_items.extend(src)
    else:
      raw_items.append(src)

  result: List[str] = []
  seen_low: set[str] = set()
  for item in raw_items:
    s = str(item or "").strip()
    if not s:
      continue
    placeholders: Dict[str, str] = {}
    protected = s
    for idx, (pat_low, canon) in enumerate(_COMMA_SALES_PLAY_MAP):
      ph = f"__INTAKE_COMMA_PLAY_{idx}__"
      pattern = re.compile(re.escape(pat_low), flags=re.IGNORECASE)
      if pattern.search(protected):
        placeholders[ph] = canon
        protected = pattern.sub(ph, protected)
    for part in re.split(r"\s*(?:\||;|,)\s*", protected):
      restored = part.strip()
      if not restored:
        continue
      for ph, canon in placeholders.items():
        if ph in restored:
          restored = restored.replace(ph, canon)
      norm = normalize_sales_play_value(restored)
      if norm and norm.lower() not in seen_low:
        seen_low.add(norm.lower())
        result.append(norm)
  return result


DEFAULT_INDUSTRIES = [
    # Industries
    "Automotive",
    "Consumer Packaged Goods",
    "Financial Services & Insurance",
    "Games",
    "Healthcare",
    "Int'l Public Sector",
    "Life Sciences",
    "Logistics",
    "Manufacturing",
    "Media & Entertainment",
    "Power & Energy",
    "Retail & Consumer",
    "Retail & CPG",
    "Software & Internet",
    "Telecommunications",
    "Travel & Hospitality",
    # Domains
    "Marketing",
    "Supply Chain",
    "Sustainability",
]

DEFAULT_AUDIENCES = [
    # Executive / C-Suite
    "CDO (Chief Data Officer)",
    "CEO (Chief Executive Officer)",
    "CFO (Chief Financial Officer)",
    "CIO (Chief Information Officer)",
    "CISO (Chief Information Security Officer)",
    "CMO (Chief Marketing Officer)",
    "CTO (Chief Technology Officer)",
    # Business & Management
    "ITDM (IT Decision Maker)",
    "Line of Business",
    "Procurement & Purchasing",
    # Technical Practitioners
    "Cloud & Solution Architects",
    "Developers & Engineers",
    # Segments
    "Corporate",
    "Enterprise",
    "SMB",
    "Startups",
    "Strategic",
    # Legacy / Shortform compatibility
    "C-Level / Executive Leadership",
    "Technical Decision Makers & Architects",
    "Line of Business Executives",
    "IT Operations & Cloud Platform Leads",
]

DEFAULT_REGIONS = [
    "NORTHAM",
    "AMER",
    "EMEA",
    "APAC",
    "LATAM",
    "JAPAN",
    "GLOBAL",
]

DECK_STRATEGIES = [
    {
        "id": "smart_hybrid",
        "name": "⚡ Smart Hybrid (Recommended)",
        "description": (
            "Blends vetted CloudHub reusable slides with bespoke synthesized"
            " anchor slides."
        ),
    },
    {
        "id": "cloudhub",
        "name": "📁 CloudHub Focused",
        "description": (
            "Prioritizes brand-approved CloudHub assets, minimizing synthetic"
            " layout changes."
        ),
    },
    {
        "id": "bespoke_custom",
        "name": "✨ Bespoke Custom",
        "description": (
            "100% custom-tailored layouts synthesized from scratch for the"
            " account."
        ),
    },
]

DECK_LENGTHS = [
    "Brief (4-6 slides)",
    "Standard (8-12 slides)",
    "Comprehensive (15-20 slides)",
]

DEFAULT_ARCHETYPES = [
    {
        "id": "First_Call_Discovery",
        "label": "🔍 First Call & Discovery (S0: Qualify — FSR/KAx Lead)",
    },
    {
        "id": "Executive_Vision_Briefing",
        "label": (
            "🏛️ Executive Vision & EBC (S0–S1: Inspire / Strategy — Exec"
            " Sponsor)"
        ),
    },
    {
        "id": "Sales_Play_Business_Pitch",
        "label": (
            "🎯 Sales Play Business Pitch (S1: Position & Build L100 — FSR +"
            " Specialist)"
        ),
    },
    {
        "id": "Technical_Solutioning_Pitch",
        "label": (
            "⚙️ Technical Solutioning Pitch (S2: Tech Solutioning L200 —"
            " Platform/Practice CE)"
        ),
    },
    {
        "id": "Architecture_PoC_Workshop",
        "label": (
            "🛠️ Architecture & PoC Workshop (S2: Tech Validation L200/L300 —"
            " Practice CE)"
        ),
    },
    {
        "id": "Value_Case_Commercial_Proposal",
        "label": (
            "💰 Value Case & Commercial Proposal (S1–S3: ROI/TCO & Propose —"
            " Value/Deal Desk)"
        ),
    },
    {
        "id": "Competitive_Takeout_Migration",
        "label": (
            "⚔️ Competitive Takeout & Migration (S1–S2: Displacement & RaMP —"
            " FSR + CE)"
        ),
    },
    {
        "id": "QBR_Adoption_Expansion",
        "label": (
            "📈 QBR, Adoption & Expansion (S4 & S0': Mobilize / Grow — Outcome"
            " CE / TAM)"
        ),
    },
]


def create_gtm_intake_card(
    user_prompt: str = "",
    customer_name: str = "",
    industry: str = "",
    sales_play: Any = "",
    audience: str = "C-Level / Executive Leadership",
    region: str = "AMER",
    er_number: str = "",
    deck_strategy: str = "smart_hybrid",
    deck_length: str = "Standard (8-12 slides)",
    context_file_url: str = "",
    context_file_name: str = "",
    presentation_archetype: str = "",
    sales_stage: str = "",
    secondary_sales_play: Any = "",
) -> Dict[str, Any]:
  """Constructs the interactive A2UI intake card for deck generation."""
  normalized_plays = normalize_sales_plays_list(
      sales_play, secondary_sales_play
  )
  normalized_sales_play = normalized_plays[0] if normalized_plays else ""
  normalized_secondary_play = (
      " | ".join(normalized_plays[1:]) if len(normalized_plays) > 1 else ""
  )
  resolved_strategy = deck_strategy or "smart_hybrid"
  resolved_length = deck_length or "Standard (8-12 slides)"
  resolved_industry = industry or ""

  strategy_options = [
      {
          "value": strat["id"],
          "label": f"{strat['name']} - {strat['description']}",
          "selected": strat["id"] == resolved_strategy,
      }
      for strat in DECK_STRATEGIES
  ]
  archetype_select_options = [{
      "value": "",
      "label": "✨ Auto-Detect from Prompt, Audience & WIN Stage",
      "selected": not presentation_archetype,
  }] + [
      {
          "value": arch["id"],
          "label": arch["label"],
          "selected": arch["id"] == presentation_archetype,
      }
      for arch in DEFAULT_ARCHETYPES
  ]

  fields = [
      {
          "id": "user_prompt",
          "type": "textarea",
          "label": "Business Context / User Prompt",
          "value": user_prompt,
          "placeholder": (
              "e.g. Build an AI modernization pitch focusing on customer"
              " journey and ROI..."
          ),
          "required": True,
      },
      {
          "id": "customer_name",
          "type": "text",
          "label": "Customer / Account Name",
          "value": customer_name,
          "placeholder": "e.g. Target, LVMH, Deutsche Bank",
          "required": True,
      },
      {
          "id": "er_number",
          "type": "text",
          "label": "Opportunity ID / ER URL",
          "value": er_number,
          "placeholder": "e.g. 006Kf00000M0PJcIAN or Lightning URL",
          "required": False,
      },
      {
          "id": "sales_play",
          "type": "select",
          "label": "Primary Sales Play",
          "value": normalized_sales_play,
          "options": DEFAULT_SALES_PLAYS,
          "grouped_options": GROUPED_SALES_PLAY_OPTIONS,
          "practice_area_groups": SALES_PLAYS_BY_PRACTICE_AREA,
      },
      {
          "id": "secondary_sales_play",
          "type": "select",
          "label": "Additional Sales Play (Optional — Multi-Play Pitch)",
          "value": normalized_secondary_play,
          "options": [""] + DEFAULT_SALES_PLAYS,
          "grouped_options": (
              [{"label": "➕ None / Single Sales Play", "value": ""}]
              + list(GROUPED_SALES_PLAY_OPTIONS)
          ),
          "practice_area_groups": SALES_PLAYS_BY_PRACTICE_AREA,
      },
      {
          "id": "industry",
          "type": "select",
          "label": "Industry Vertical",
          "value": resolved_industry,
          "options": DEFAULT_INDUSTRIES,
      },
      {
          "id": "audience",
          "type": "select",
          "label": "Target Audience Persona",
          "value": audience,
          "options": DEFAULT_AUDIENCES,
      },
      {
          "id": "presentation_archetype",
          "type": "select",
          "label": "Cloud GTM Presentation Archetype",
          "value": presentation_archetype,
          "options": archetype_select_options,
      },
      {
          "id": "region",
          "type": "select",
          "label": "Target Region / Geo",
          "value": region,
          "options": DEFAULT_REGIONS,
      },
      {
          "id": "deck_strategy",
          "type": "select",
          "label": "Deck Strategy",
          "value": resolved_strategy,
          "options": strategy_options,
      },
      {
          "id": "deck_length",
          "type": "select",
          "label": "Deck Length",
          "value": resolved_length,
          "options": DECK_LENGTHS,
      },
      {
          "id": "context_file_attachment",
          "type": "file_attachment",
          "label": "Additional Context Files (Drive / Document Upload)",
          "file_url": context_file_url,
          "file_name": context_file_name,
          "supported_types": [
              "application/pdf",
              "application/vnd.google-apps.document",
              ".docx",
              ".txt",
          ],
      },
  ]

  actions = [{
      "id": "btn_generate_outline",
      "label": "📋 Generate Outline & Agenda",
      "style": "primary",
      "action": {
          "type": "a2ui_action",
          "actionName": "generate_outline",
          "parameters": {
              "customer_name": customer_name,
              "sales_play": normalized_sales_play,
              "secondary_sales_play": normalized_secondary_play,
              "sales_plays": normalized_plays,
              "industry": resolved_industry,
              "audience": audience,
              "region": region,
              "er_number": er_number,
              "deck_strategy": resolved_strategy,
              "deck_length": resolved_length,
              "presentation_archetype": presentation_archetype,
              "sales_stage": sales_stage,
              "context_file_url": context_file_url,
          },
      },
  }]

  step1_fields = [
      {
          "id": "customer_name",
          "type": "text",
          "label": "Customer / Account Name",
          "value": customer_name,
          "placeholder": "e.g. Target Corporation, LVMH, Deutsche Bank",
          "required": True,
      },
      {
          "id": "user_prompt",
          "type": "textarea",
          "label": "Pitch Objective & Business Narrative",
          "value": user_prompt,
          "placeholder": (
              "e.g. Build an AI modernization pitch focusing on customer"
              " journey, store operations with AI agents..."
          ),
          "required": True,
      },
  ]

  step2_fields = [
      {
          "id": "deck_strategy",
          "type": "select",
          "label": "Presentation Synthesis Mode",
          "value": resolved_strategy,
          "options": strategy_options,
      },
      {
          "id": "presentation_archetype",
          "type": "select",
          "label": "Cloud GTM Presentation Archetype",
          "value": presentation_archetype,
          "options": archetype_select_options,
      },
      {
          "id": "industry",
          "type": "select",
          "label": "Industry Vertical",
          "value": resolved_industry,
          "options": DEFAULT_INDUSTRIES,
      },
      {
          "id": "sales_play",
          "type": "select",
          "label": "Primary Google Cloud Sales Play",
          "value": normalized_sales_play,
          "options": DEFAULT_SALES_PLAYS,
          "grouped_options": GROUPED_SALES_PLAY_OPTIONS,
          "practice_area_groups": SALES_PLAYS_BY_PRACTICE_AREA,
      },
      {
          "id": "secondary_sales_play",
          "type": "select",
          "label": "Additional Sales Play (Optional — Multi-Play Pitch)",
          "value": normalized_secondary_play,
          "options": [""] + DEFAULT_SALES_PLAYS,
          "grouped_options": (
              [{"label": "➕ None / Single Sales Play", "value": ""}]
              + list(GROUPED_SALES_PLAY_OPTIONS)
          ),
          "practice_area_groups": SALES_PLAYS_BY_PRACTICE_AREA,
      },
  ]

  step3_fields = [
      {
          "id": "audience",
          "type": "select",
          "label": "Target Audience Persona",
          "value": audience,
          "options": DEFAULT_AUDIENCES,
      },
      {
          "id": "deck_length",
          "type": "select",
          "label": "Presentation Length",
          "value": resolved_length,
          "options": DECK_LENGTHS,
      },
      {
          "id": "region",
          "type": "select",
          "label": "Target Region / Geo",
          "value": region,
          "options": DEFAULT_REGIONS,
      },
      {
          "id": "er_number",
          "type": "text",
          "label": "Opportunity ID / ER URL (Optional)",
          "value": er_number,
          "placeholder": "e.g. 006Kf00000M0PJcIAN or Lightning URL",
          "required": False,
      },
      {
          "id": "context_file_attachment",
          "type": "file_attachment",
          "label": "Additional Context Files (Drive / Document Upload)",
          "file_url": context_file_url,
          "file_name": context_file_name,
          "supported_types": [
              "application/pdf",
              "application/vnd.google-apps.document",
              ".docx",
              ".txt",
          ],
      },
  ]

  common_params = {
      "customer_name": customer_name,
      "sales_play": normalized_sales_play,
      "secondary_sales_play": normalized_secondary_play,
      "sales_plays": normalized_plays,
      "industry": resolved_industry,
      "audience": audience,
      "region": region,
      "er_number": er_number,
      "deck_strategy": resolved_strategy,
      "deck_length": resolved_length,
      "presentation_archetype": presentation_archetype,
      "sales_stage": sales_stage,
      "context_file_url": context_file_url,
  }

  quick_action = {
      "id": "btn_quick_generate",
      "label": "⚡ Quick Synthesize",
      "style": "primary",
      "action": {
          "type": "a2ui_action",
          "actionName": "generate_outline",
          "parameters": common_params,
      },
  }

  final_action = {
      "id": "btn_generate_outline",
      "label": "✨ Synthesize Proposal Outline",
      "style": "primary",
      "action": {
          "type": "a2ui_action",
          "actionName": "generate_outline",
          "parameters": common_params,
      },
  }

  title = (
      f"🎯 PitchGen GTM Studio: {customer_name}"
      if customer_name
      else "🎯 PitchGen GTM Studio"
  )

  v08_messages = create_a2ui_intake_messages(
      user_prompt=user_prompt,
      customer_name=customer_name,
      industry=resolved_industry,
      sales_play=normalized_sales_play,
      secondary_sales_play=normalized_secondary_play,
      audience=audience,
      region=region,
      er_number=er_number,
      deck_strategy=resolved_strategy,
      deck_length=resolved_length,
      presentation_archetype=presentation_archetype,
      sales_stage=sales_stage,
  )

  return {
      "type": "card",
      "title": title,
      "subtitle": "Google Cloud GTM Sales Enablement",
      "metadata": {"mimeType": A2UI_MIME_TYPE},
      "sections": [
          {
              "type": "stepper",
              "steps": [
                  {
                      "id": "step1",
                      "title": "1. Narrative & Goal",
                      "subtitle": "Account context and pitch objective",
                      "fields": step1_fields,
                      "actions": [quick_action],
                  },
                  {
                      "id": "step2",
                      "title": "2. GTM Strategy",
                      "subtitle": "Synthesis mode and aligned sales play",
                      "fields": step2_fields,
                      "actions": [],
                  },
                  {
                      "id": "step3",
                      "title": "3. Delivery Specs",
                      "subtitle": "Audience persona, length, and ER ID",
                      "fields": step3_fields,
                      "actions": [final_action],
                  },
              ],
          },
          {
              "type": "form",
              "fields": step1_fields + step2_fields + step3_fields,
          },
          {
              "type": "actions",
              "buttons": [quick_action, final_action],
          },
      ],
      "canvas_messages": v08_messages,
      "a2ui_v09_messages": v08_messages,
  }


def create_a2ui_v08_intake_messages(
    user_prompt: str = "",
    customer_name: str = "",
    industry: str = "",
    sales_play: Any = "",
    audience: str = "",
    region: str = "",
    er_number: str = "",
    deck_strategy: str = "smart_hybrid",
    deck_length: str = "Standard (8-12 slides)",
    surface_id: str = "pitchgen-intake",
    secondary_sales_play: Any = "",
) -> List[Dict[str, Any]]:
  """Generates canonical A2UI v0.8 messages for GTM Intake.

  Adheres to canonical A2UI v0.8 wire protocol:
  [beginRendering, surfaceUpdate] with Card, Column, Row, Text, TextField,
  MultipleChoice, Divider, and Button components.

  Args:
      user_prompt: Initial business context or prompt text.
      customer_name: Target customer account name.
      industry: Selected industry vertical name.
      sales_play: Selected sales play (or list/multi-play string).
      audience: Target audience persona.
      region: Target region or geography.
      er_number: Enterprise Opportunity ER identification number.
      deck_strategy: Selected presentation deck strategy identifier.
      deck_length: Selected presentation length.
      surface_id: A2UI surface identifier.
      secondary_sales_play: Optional additional sales play(s).

  Returns:
      A list of A2UI v0.8 wire protocol messages.
  """
  normalized_plays = [
      p
      for p in normalize_sales_plays_list(sales_play, secondary_sales_play)
      if p in DEFAULT_SALES_PLAYS
  ]
  normalized_sales_play = (
      " | ".join(normalized_plays)
      if normalized_plays
      else normalize_sales_play_value(sales_play)
  )
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
  industry_options = [
      {"label": {"literalString": "✨ Auto-Detect Industry Vertical"}, "value": ""}
  ] + [
      {"label": {"literalString": ind}, "value": ind}
      for ind in DEFAULT_INDUSTRIES
  ]
  sales_play_options = [
      {"label": {"literalString": "✨ Auto-Detect Sales Play"}, "value": ""}
  ] + [
      {"label": {"literalString": opt["label"]}, "value": opt["value"]}
      for opt in GROUPED_SALES_PLAY_OPTIONS
  ]
  audience_options = [
      {"label": {"literalString": aud}, "value": aud}
      for aud in DEFAULT_AUDIENCES
  ]
  length_options = [
      {"label": {"literalString": dl}, "value": dl} for dl in DECK_LENGTHS
  ]
  region_options = [
      {"label": {"literalString": reg}, "value": reg} for reg in DEFAULT_REGIONS
  ]

  components = [
      {
          "id": "root",
          "component": {
              "Card": {
                  "child": "intake_shell_col",
              }
          },
      },
      {
          "id": "intake_shell_col",
          "component": {
              "Column": {
                  "children": {
                      "explicitList": [
                          "header_row",
                          "divider_top",
                          "sec1_label",
                          "customer_name_field",
                          "user_prompt_field",
                          "divider_sec1",
                          "sec2_label",
                          "strategy_picker",
                          "industry_picker",
                          "sales_play_picker",
                          "divider_sec2",
                          "sec3_label",
                          "audience_picker",
                          "deck_length_picker",
                          "region_picker",
                          "er_field",
                          "divider_bottom",
                          "submit_btn",
                      ]
                  },
                  "distribution": "start",
                  "alignment": "stretch",
              }
          },
      },
      {
          "id": "header_row",
          "component": {
              "Row": {
                  "children": {
                      "explicitList": ["header_title_col"],
                  },
                  "distribution": "spaceBetween",
                  "alignment": "center",
              }
          },
      },
      {
          "id": "header_title_col",
          "component": {
              "Column": {
                  "children": {
                      "explicitList": ["title_text", "subtitle_text"],
                  },
                  "distribution": "start",
                  "alignment": "stretch",
              }
          },
      },
      {
          "id": "title_text",
          "component": {
              "Text": {
                  "text": {
                      "literalString": (
                          f"🎯 PitchGen GTM Studio: {customer_name}"
                          if customer_name
                          else "🎯 PitchGen GTM Studio"
                      )
                  },
                  "usageHint": "h2",
              }
          },
      },
      {
          "id": "subtitle_text",
          "component": {
              "Text": {
                  "text": {
                      "literalString": (
                          "Configure account narrative, strategy, and audience"
                          " parameters to synthesize your deck"
                      )
                  },
                  "usageHint": "body",
              }
          },
      },
      {
          "id": "divider_top",
          "component": {
              "Divider": {
                  "axis": "horizontal",
              }
          },
      },
      {
          "id": "sec1_label",
          "component": {
              "Text": {
                  "text": {
                      "literalString": "1. Pitch Objective & Account Narrative"
                  },
                  "usageHint": "h3",
              }
          },
      },
      {
          "id": "customer_name_field",
          "component": {
              "TextField": {
                  "label": {
                      "literalString": "Customer / Account Name (Required)"
                  },
                  "text": {"literalString": customer_name},
                  "textFieldType": "shortText",
              }
          },
      },
      {
          "id": "user_prompt_field",
          "component": {
              "TextField": {
                  "label": {
                      "literalString": (
                          "Pitch Objective & Business Narrative (Required)"
                      )
                  },
                  "text": {
                      "literalString": (
                          user_prompt
                          or "Build an AI modernization pitch focusing on customer journey and ROI"
                      )
                  },
                  "textFieldType": "longText",
              }
          },
      },
      {
          "id": "divider_sec1",
          "component": {
              "Divider": {
                  "axis": "horizontal",
              }
          },
      },
      {
          "id": "sec2_label",
          "component": {
              "Text": {
                  "text": {"literalString": "2. GTM Strategy & Synthesis Mode"},
                  "usageHint": "h3",
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
          "id": "industry_picker",
          "component": {
              "MultipleChoice": {
                  "selections": {
                      "literalArray": [
                          industry if industry in DEFAULT_INDUSTRIES else ""
                      ]
                  },
                  "options": industry_options,
                  "maxAllowedSelections": 1,
                  "variant": "chips",
                  "filterable": True,
              }
          },
      },
      {
          "id": "sales_play_picker",
          "component": {
              "MultipleChoice": {
                  "selections": {
                      "literalArray": (
                          normalized_plays if normalized_plays else [""]
                      )
                  },
                  "options": sales_play_options,
                  "maxAllowedSelections": 3,
                  "variant": "chips",
                  "filterable": True,
              }
          },
      },
      {
          "id": "divider_sec2",
          "component": {
              "Divider": {
                  "axis": "horizontal",
              }
          },
      },
      {
          "id": "sec3_label",
          "component": {
              "Text": {
                  "text": {"literalString": "3. Audience Persona & Parameters"},
                  "usageHint": "h3",
              }
          },
      },
      {
          "id": "audience_picker",
          "component": {
              "MultipleChoice": {
                  "selections": {
                      "literalArray": [
                          audience
                          if audience in DEFAULT_AUDIENCES
                          else "C-Level / Executive Leadership"
                      ]
                  },
                  "options": audience_options,
                  "maxAllowedSelections": 1,
                  "variant": "chips",
                  "filterable": True,
              }
          },
      },
      {
          "id": "deck_length_picker",
          "component": {
              "MultipleChoice": {
                  "selections": {
                      "literalArray": [
                          deck_length
                          if deck_length in DECK_LENGTHS
                          else "Standard (8-12 slides)"
                      ]
                  },
                  "options": length_options,
                  "maxAllowedSelections": 1,
                  "variant": "chips",
              }
          },
      },
      {
          "id": "region_picker",
          "component": {
              "MultipleChoice": {
                  "selections": {
                      "literalArray": [
                          region if region in DEFAULT_REGIONS else "AMER"
                      ]
                  },
                  "options": region_options,
                  "maxAllowedSelections": 1,
                  "variant": "chips",
              }
          },
      },
      {
          "id": "er_field",
          "component": {
              "TextField": {
                  "label": {
                      "literalString": "Opportunity ID / ER URL (Optional)"
                  },
                  "text": {"literalString": er_number},
                  "textFieldType": "shortText",
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
          "id": "submit_btn",
          "component": {
              "Button": {
                  "child": "submit_btn_text",
                  "primary": True,
                  "action": {
                      "name": "generate_outline",
                      "context": [
                          {
                              "key": "customer_name",
                              "value": {"literalString": customer_name},
                          },
                          {
                              "key": "sales_play",
                              "value": {"literalString": normalized_sales_play},
                          },
                          {
                              "key": "industry",
                              "value": {"literalString": industry or ""},
                          },
                          {
                              "key": "audience",
                              "value": {
                                  "literalString": (
                                      audience
                                      or "C-Level / Executive Leadership"
                                  )
                              },
                          },
                          {
                              "key": "region",
                              "value": {"literalString": region or "AMER"},
                          },
                          {
                              "key": "er_number",
                              "value": {"literalString": er_number},
                          },
                          {
                              "key": "deck_strategy",
                              "value": {
                                  "literalString": (
                                      deck_strategy or "smart_hybrid"
                                  )
                              },
                          },
                          {
                              "key": "prompt",
                              "value": {
                                  "literalString": (
                                      "Generate proposal outline for"
                                      f" {customer_name}"
                                      if customer_name
                                      else "Generate Proposal Outline"
                                  )
                              },
                          },
                      ],
                  },
              },
          },
      },
      {
          "id": "submit_btn_text",
          "component": {
              "Text": {
                  "text": {"literalString": "✨ Synthesize Proposal Outline"},
              }
          },
      },
  ]

  return [
      {
          "beginRendering": {
              "surfaceId": surface_id,
              "root": "root",
          }
      },
      {
          "surfaceUpdate": {
              "surfaceId": surface_id,
              "components": components,
          }
      },
  ]


_INTAKE_MULTI_SELECT_SKIP = frozenset({
    "",
    "none",
    "null",
    "undefined",
    "n/a",
    "— (blank)",
    "-(blank)",
    "sales_play",
    "audience",
    "target audience persona",
    "auto-detect sales play",
    "✨ auto-detect sales play",
    "primary sales play",
})

# Fallback copy of a2ui.PITCHGEN_TOOL_LOGO_URL (used only if ge.a2ui cannot be
# imported lazily, e.g. when this module is loaded standalone in tests).
_PITCHGEN_TOOL_LOGO_URL_FALLBACK = (
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

# "Generate a Pitch" header icon (wand + deck), ported from the A2UI-GE intake.
GENERATE_PITCH_ICON_URL = (
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg'"
    " width='96' height='45' viewBox='0 0 154 72'><rect x='0' y='0'"
    " width='72' height='72' rx='14' fill='rgb(232,240,254)'/><line"
    " x1='24' y1='48' x2='46' y2='26' stroke='rgb(26,115,232)'"
    " stroke-width='9' stroke-linecap='round'/><line x1='38.5'"
    " y1='33.5' x2='43.5' y2='28.5' stroke='rgb(232,240,254)'"
    " stroke-width='2.3' stroke-linecap='round'/><path d='M26 24"
    " L27.8 28.2 L32 30 L27.8 31.8 L26 36 L24.2 31.8 L20 30 L24.2"
    " 28.2 Z M33.5 19 L34.7 21.8 L37.5 23 L34.7 24.2 L33.5 27 L32.3"
    " 24.2 L29.5 23 L32.3 21.8 Z M45.5 37.5 L47.1 41.4 L51 43 L47.1"
    " 44.6 L45.5 48.5 L43.9 44.6 L40 43 L43.9 41.4 Z'"
    " fill='rgb(26,115,232)'/><rect x='82' y='0' width='72'"
    " height='72' rx='14' fill='rgb(232,240,254)'/><rect x='98'"
    " y='22.5' width='40' height='27' rx='5' transform='rotate(8 118"
    " 36)' fill='rgb(138,154,242)'/><rect x='96' y='22.5' width='44'"
    " height='27' rx='6' fill='rgb(74,104,238)'/><rect x='100.5'"
    " y='26.8' width='35' height='18.4' rx='3'"
    " fill='rgb(238,243,255)'/><rect x='104.8' y='30' width='4'"
    " height='12' rx='1' fill='rgb(62,98,232)'/><rect x='112.2'"
    " y='30.8' width='15.5' height='3' rx='1'"
    " fill='rgb(71,104,235)'/><rect x='112' y='36' width='11'"
    " height='6' rx='1' fill='rgb(92,122,242)'/><rect x='124.8' y='36'"
    " width='5' height='6' rx='1' fill='rgb(77,111,240)'/></svg>"
)

INTAKE_SALES_STAGES = ("S0", "S1", "S2", "S3", "S4")

# Account segments (segment-targeting skill). Rendered as their own select and
# excluded from the Target Audience Persona multi-select.
INTAKE_SEGMENTS = ("SMB", "Startups", "Corporate", "Enterprise", "Strategic")
_INTAKE_SEGMENTS_LOW = {s.lower(): s for s in INTAKE_SEGMENTS}


def _practice_area_sales_play_options() -> List[Dict[str, str]]:
  """Sales play options labelled 'Practice Area — Play'.

  Ordered by the canonical GTM practice-area order (AI, Agentic Workplace
  Transformation, Data, Infrastructure, Security), then alphabetically by play
  within each area. Values stay the canonical play names so backend sales play
  detection is unchanged.
  """
  return [
      {"label": f"{area} — {play}", "value": play}
      for area, plays in SALES_PLAYS_BY_PRACTICE_AREA.items()
      for play in sorted(plays)
  ]


def _a2ui_module():
  """Lazily imports ge.a2ui (it imports this module at load time)."""
  try:
    from ge import a2ui as _a2ui  # pylint: disable=g-import-not-at-top

    return _a2ui
  except Exception:  # pylint: disable=broad-except
    from ge import a2ui as _a2ui  # pylint: disable=g-import-not-at-top

    return _a2ui


def _pitchgen_logo_components() -> List[Dict[str, Any]]:
  return _a2ui_module().pitchgen_logo_components()


def _material_header_icon(component_id: str, icon: str) -> Dict[str, Any]:
  return _a2ui_module().material_header_icon(component_id, icon)


def _resolve_pitchgen_tool_logo_url() -> str:
  """Returns the shared PitchGen logo data URI (lazy import avoids a cycle)."""
  try:
    from ge import a2ui as _a2ui  # pylint: disable=g-import-not-at-top

    return _a2ui.PITCHGEN_TOOL_LOGO_URL
  except Exception:  # pylint: disable=broad-except
    pass
  try:
    from ge import a2ui as _a2ui  # pylint: disable=g-import-not-at-top

    return _a2ui.PITCHGEN_TOOL_LOGO_URL
  except Exception:  # pylint: disable=broad-except
    return _PITCHGEN_TOOL_LOGO_URL_FALLBACK


def _normalize_multi_select_value(val: Any) -> List[str]:
  """Normalizes a string or list into a clean, de-duplicated list of strings.

  Strings are split on commas, pipes, and semicolons that are NOT inside
  parentheses, so labels like 'CDO (Chief Data Officer)' stay intact.
  Placeholder labels are dropped.
  """
  import re  # pylint: disable=g-import-not-at-top

  if val is None:
    return []
  raw: List[Any] = list(val) if isinstance(val, (list, tuple, set)) else [val]
  result: List[str] = []
  seen_low: set[str] = set()
  for item in raw:
    s = str(item or "").strip()
    if not s:
      continue
    for part in re.split(r"\s*[,|;]\s*(?![^()]*\))", s):
      p = part.strip().strip("[]'\"").strip()
      if not p or p.lower() in _INTAKE_MULTI_SELECT_SKIP:
        continue
      if p.lower() not in seen_low:
        seen_low.add(p.lower())
        result.append(p)
  return result


def _options_with_extras(
    base_values: List[str], selected: List[str]
) -> List[Dict[str, str]]:
  """Builds flat {label, value} options, appending any pre-filled unknown values."""
  options = [{"label": v, "value": v} for v in base_values]
  known_low = {v.lower() for v in base_values}
  for v in selected:
    if v.lower() not in known_low:
      known_low.add(v.lower())
      options.append({"label": v, "value": v})
  return options


def create_a2ui_v09_intake_messages(
    user_prompt: str = "",
    customer_name: str = "",
    industry: str = "",
    sales_play: Any = "",
    audience: Any = "",
    region: str = "",
    er_number: str = "",
    deck_strategy: str = "smart_hybrid",
    deck_length: str = "Standard (8-12 slides)",
    surface_id: str = "pitchgen-intake",
    presentation_archetype: str = "",
    sales_stage: str = "",
    secondary_sales_play: Any = "",
    segment: str = "",
) -> List[Dict[str, Any]]:
  """Generates canonical A2UI v0.9 Angular Material messages for GTM Intake.

  Layout follows the A2UI-GE 'Generate a Pitch' intake (logo row, icon header,
  account/ER row, multi-select Sales Play and Audience) while keeping the
  qa-p2 backend contract: action `create_proposal_outline` with qa-p2 context
  keys, plus Sales Stage and Presentation Archetype selects.

  `secondary_sales_play` is still accepted for backward compatibility and is
  merged into the multi-select `sales_play` list.
  """
  font_sans = "'Google Sans', 'Google Sans Text', Roboto, Arial, sans-serif"

  stage_raw = str(sales_stage or "").strip().upper()
  if stage_raw not in INTAKE_SALES_STAGES:
    region_raw = str(region or "").strip().upper()
    stage_raw = region_raw if region_raw in INTAKE_SALES_STAGES else ""
  resolved_sales_play = normalize_sales_plays_list(
      sales_play, secondary_sales_play
  )
  resolved_audience = _normalize_multi_select_value(audience)
  resolved_segment = _INTAKE_SEGMENTS_LOW.get(
      str(segment or "").strip().lower(), ""
  )
  audience_wo_segments: List[str] = []
  for aud in resolved_audience:
    seg_match = _INTAKE_SEGMENTS_LOW.get(aud.strip().lower())
    if seg_match:
      resolved_segment = resolved_segment or seg_match
    else:
      audience_wo_segments.append(aud)
  resolved_audience = audience_wo_segments
  industry_raw = str(industry or "").strip()
  resolved_industry = (
      industry_raw
      if industry_raw.lower()
      not in ("", "none", "null", "industry", "industry vertical")
      else ""
  )
  archetype_ids = [arch["id"] for arch in DEFAULT_ARCHETYPES]
  archetype_raw = str(presentation_archetype or "").strip()
  resolved_archetype = ""
  if archetype_raw:
    for arch_id in archetype_ids:
      if archetype_raw.lower().replace(" ", "_") == arch_id.lower():
        resolved_archetype = arch_id
        break

  data_model = {
      "customer_name": customer_name or "",
      "er_number": er_number or "",
      "deck_strategy": deck_strategy or "smart_hybrid",
      "deck_length": deck_length or "Standard (8-12 slides)",
      "sales_play": resolved_sales_play,
      "industry": resolved_industry,
      "sales_stage": stage_raw,
      "presentation_archetype": resolved_archetype,
      "audience": resolved_audience,
      "segment": resolved_segment,
      "business_context": user_prompt or "",
  }

  strategy_options = [
      {
          "label": "⚡ Smart Hybrid (CloudHub + Bespoke Anchors)",
          "value": "smart_hybrid",
      },
      {
          "label": "📁 CloudHub Focused (100% Brand-Vetted Slides)",
          "value": "cloudhub",
      },
      {
          "label": "✨ Bespoke Custom (100% Tailored Layouts)",
          "value": "bespoke_custom",
      },
  ]
  length_values = list(DECK_LENGTHS)
  if data_model["deck_length"] not in length_values:
    length_values.append(data_model["deck_length"])
  length_options = [{"label": dl, "value": dl} for dl in length_values]
  # NOTE: only sales_play_select / audience_select carry `multiple: True`
  # (A2UI-GE design, user-confirmed to render in GE). The enterprise_workspace UCS strict
  # MaterialSelect schema does not list `multiple`, so single selects omit it.
  # Labels are 'Practice Area — Play' (sorted by practice area, then play);
  # values stay the canonical play names so backend detection matches.
  sales_play_options = _practice_area_sales_play_options()
  known_play_low = {o["value"].lower() for o in sales_play_options}
  for play in resolved_sales_play:
    if play.lower() not in known_play_low:
      known_play_low.add(play.lower())
      sales_play_options.append({"label": play, "value": play})
  industry_options = [{"label": "Auto-detect industry", "value": ""}] + [
      {"label": ind, "value": ind} for ind in DEFAULT_INDUSTRIES
  ]
  if resolved_industry and resolved_industry not in DEFAULT_INDUSTRIES:
    industry_options.append(
        {"label": resolved_industry, "value": resolved_industry}
    )
  audience_options = _options_with_extras(
      [a for a in DEFAULT_AUDIENCES if a.lower() not in _INTAKE_SEGMENTS_LOW],
      resolved_audience,
  )
  segment_options = [{"label": "Auto-detect segment", "value": ""}] + [
      {"label": seg, "value": seg} for seg in INTAKE_SEGMENTS
  ]
  stage_options = [
      {"label": "Auto-detect stage", "value": ""},
      {"label": "S0: Prospecting", "value": "S0"},
      {"label": "S1: Discovery", "value": "S1"},
      {"label": "S2: Scoping & Solution", "value": "S2"},
      {"label": "S3: Proposal & Validation", "value": "S3"},
      {"label": "S4: Negotiation", "value": "S4"},
  ]
  archetype_options = [{"label": "Auto-detect archetype", "value": ""}] + [
      {"label": arch["label"], "value": arch["id"]}
      for arch in DEFAULT_ARCHETYPES
  ]

  row_style = {"gap": "12px", "width": "100%"}

  components = [
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
          "children": ["intake_col"],
      },
      {
          "id": "intake_col",
          "component": "MaterialColumn",
          "style": {"gap": "14px"},
          "children": [
              "tool_logo_row",
              "header_row",
              "header_divider",
              "business_context_input",
              "account_er_row",
              "strategy_length_row",
              "sales_play_industry_row",
              "stage_archetype_row",
              "audience_segment_row",
              "footer_divider",
              "submit_btn",
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
          "children": ["pitchgen_tool_logo"],
      },
      *_pitchgen_logo_components(),
      {
          "id": "header_row",
          "component": "MaterialRow",
          "justify": "start",
          "align": "center",
          "style": {"gap": "12px", "width": "100%", "alignItems": "center"},
          "children": ["logo_generate_pitch", "header_text_col"],
      },
      _material_header_icon("logo_generate_pitch", "auto_awesome"),
      {
          "id": "header_text_col",
          "component": "MaterialColumn",
          "style": {"gap": "2px"},
          "children": ["header_title", "header_subtitle"],
      },
      {
          "id": "header_title",
          "component": "MaterialText",
          "text": "Generate a Pitch Deck",
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
              "Set the account, sales plays, and audience to draft a tailored"
              " proposal outline. Fields marked * are required."
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
          "id": "account_er_row",
          "component": "MaterialRow",
          "justify": "spaceBetween",
          "align": "start",
          "style": row_style,
          "children": ["customer_name_input", "er_number_input"],
      },
      {
          "id": "customer_name_input",
          "component": "MaterialInput",
          "label": "Customer / Account Name *",
          "placeholder": "e.g., Target, LVMH, Deutsche Bank",
          "value": {"path": "/customer_name"},
          "weight": 1,
      },
      {
          "id": "er_number_input",
          "component": "MaterialInput",
          "label": "Opportunity ID / ER Number",
          "placeholder": "e.g., 006Kf00000M0PJcIAN or Lightning URL",
          "value": {"path": "/er_number"},
          "weight": 1,
      },
      {
          "id": "strategy_length_row",
          "component": "MaterialRow",
          "justify": "spaceBetween",
          "align": "start",
          "style": row_style,
          "children": ["deck_strategy_select", "deck_length_select"],
      },
      {
          "id": "deck_strategy_select",
          "component": "MaterialSelect",
          "label": "Deck Strategy",
          "value": {"path": "/deck_strategy"},
          "options": strategy_options,
          "weight": 1,
      },
      {
          "id": "deck_length_select",
          "component": "MaterialSelect",
          "label": "Target Deck Length",
          "value": {"path": "/deck_length"},
          "options": length_options,
          "weight": 1,
      },
      {
          "id": "sales_play_industry_row",
          "component": "MaterialRow",
          "justify": "spaceBetween",
          "align": "start",
          "style": row_style,
          "children": ["sales_play_select", "industry_select"],
      },
      {
          "id": "sales_play_select",
          "component": "MaterialSelect",
          "label": "Sales Plays",
          "multiple": True,
          "value": {"path": "/sales_play"},
          "options": sales_play_options,
          "weight": 1,
      },
      {
          "id": "industry_select",
          "component": "MaterialSelect",
          "label": "Industry Vertical",
          "value": {"path": "/industry"},
          "options": industry_options,
          "weight": 1,
      },
      {
          "id": "stage_archetype_row",
          "component": "MaterialRow",
          "justify": "spaceBetween",
          "align": "start",
          "style": row_style,
          "children": ["sales_stage_select", "archetype_select"],
      },
      {
          "id": "sales_stage_select",
          "component": "MaterialSelect",
          "label": "Sales Stage (S0–S4)",
          "value": {"path": "/sales_stage"},
          "options": stage_options,
          "weight": 1,
      },
      {
          "id": "archetype_select",
          "component": "MaterialSelect",
          "label": "Presentation Archetype",
          "value": {"path": "/presentation_archetype"},
          "options": archetype_options,
          "weight": 1,
      },
      {
          "id": "audience_segment_row",
          "component": "MaterialRow",
          "justify": "spaceBetween",
          "align": "start",
          "style": row_style,
          "children": ["audience_select", "segment_select"],
      },
      {
          "id": "audience_select",
          "component": "MaterialSelect",
          "label": "Target Audience Persona",
          "multiple": True,
          "value": {"path": "/audience"},
          "options": audience_options,
          "weight": 1,
      },
      {
          "id": "segment_select",
          "component": "MaterialSelect",
          "label": "Customer Segment",
          "value": {"path": "/segment"},
          "options": segment_options,
          "weight": 1,
      },
      {
          "id": "business_context_input",
          "component": "MaterialInput",
          "label": "What should this pitch achieve? *",
          "placeholder": (
              "Describe customer pain points, target architecture, or meeting"
              " goals..."
          ),
          "value": {"path": "/business_context"},
      },
      {
          "id": "footer_divider",
          "component": "MaterialDivider",
      },
      {
          "id": "submit_btn",
          "component": "MaterialButton",
          "label": "✨ Synthesize Proposal Outline",
          "variant": "flat",
          "color": "primary",
          "style": {
              "fontFamily": font_sans,
              "fontWeight": "500",
              "borderRadius": "999px",
          },
          "action": {
              "event": {
                  "name": "create_proposal_outline",
                  "context": {
                      "customer_name": {"path": "/customer_name"},
                      "business_context": {"path": "/business_context"},
                      "sales_play": {"path": "/sales_play"},
                      "industry": {"path": "/industry"},
                      "audience": {"path": "/audience"},
                      "segment": {"path": "/segment"},
                      "sales_stage": {"path": "/sales_stage"},
                      "presentation_archetype": {
                          "path": "/presentation_archetype"
                      },
                      "er_number": {"path": "/er_number"},
                      "deck_strategy": {"path": "/deck_strategy"},
                      "deck_length": {"path": "/deck_length"},
                      "prompt": (
                          f"Generate proposal outline for {customer_name}"
                          if customer_name
                          else "Generate Proposal Outline"
                      ),
                  },
              }
          },
      },
  ]

  return [
      {
          "version": "v0.9",
          "createSurface": {
              "surfaceId": surface_id,
              "catalogId": A2UI_GE_COMPOSITE_CATALOG_ID,
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


def create_a2ui_intake_messages(
    user_prompt: str = "",
    customer_name: str = "",
    industry: str = "",
    sales_play: Any = "",
    audience: Any = "",
    region: str = "",
    er_number: str = "",
    deck_strategy: str = "smart_hybrid",
    deck_length: str = "Standard (8-12 slides)",
    surface_id: str = "pitchgen-intake",
    version: str = "v0.9",
    presentation_archetype: str = "",
    sales_stage: str = "",
    secondary_sales_play: Any = "",
) -> List[Dict[str, Any]]:
  """Generates A2UI messages for GTM Intake (defaults to v0.9 Material NG)."""
  import os  # pylint: disable=g-import-not-at-top

  active_version = os.environ.get("A2UI_VERSION", version or "v0.9")
  if active_version == "v0.8":
    audience_str = (
        ", ".join(str(a) for a in audience if a)
        if isinstance(audience, (list, tuple, set))
        else (audience or "")
    )
    return create_a2ui_v08_intake_messages(
        user_prompt=user_prompt,
        customer_name=customer_name,
        industry=industry,
        sales_play=sales_play,
        secondary_sales_play=secondary_sales_play,
        audience=audience_str,
        region=region,
        er_number=er_number,
        deck_strategy=deck_strategy or "smart_hybrid",
        deck_length=deck_length or "Standard (8-12 slides)",
        surface_id=surface_id,
    )
  return create_a2ui_v09_intake_messages(
      user_prompt=user_prompt,
      customer_name=customer_name,
      industry=industry,
      sales_play=sales_play,
      secondary_sales_play=secondary_sales_play,
      audience=audience,
      region=region,
      er_number=er_number,
      deck_strategy=deck_strategy or "smart_hybrid",
      deck_length=deck_length or "Standard (8-12 slides)",
      surface_id=surface_id,
      presentation_archetype=presentation_archetype,
      sales_stage=sales_stage,
  )
