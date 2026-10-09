"""Local Visual Test Harness & A2A/A2UI Protocol Server for PitchGen.

Provides:
1. Live visual testing interface (GET /) rendering interactive PitchGen A2UI
cards:
   - Workflow 1: GTM Intake Card & Outline Review Card
   - Workflow 2: Slide Search Side Panel with visual thumbnails
   - Workflow 3: Slide Text Augmentation & Customization (Slide Jobs)
   - Workflow 4: Nano Banana Architecture Synthesis (Flash/Pro)
   - Workflow 5: Canvas Embedded Presentation Iframe (WS_SLIDES)
2. A2A JSON-RPC 2.0 & SSE Event-Stream protocol endpoints (/a2a/v1/tasks/send,
/a2a/v1/chat)
3. Automatic Gemini Enterprise OAuth identity resolution (LDAP & corporate email
exchange)
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

try:
  from ge import a2ui
except ImportError:
  import a2ui  # pylint: disable=g-import-not-at-top

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("pitchgen_a2ui_server")

app = FastAPI(
    title="PitchGen - A2A & A2UI Protocol Service",
    description=(
        "Local Visual Test Harness and A2A Protocol Gateway for PitchGen"
        " Gemini Enterprise integration."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# Models & Health
# ==============================================================================
class IdentityTestRequest(BaseModel):
  access_token: Optional[str] = None
  fallback_ldap: Optional[str] = None


@app.get("/health")
async def health_check() -> Dict[str, str]:
  """Health check endpoint."""
  return {"status": "healthy", "service": "pitchgen-ge-a2ui"}


@app.get("/.well-known/agent.json")
@app.get("/.well-known/agent-card.json")
@app.get("/agent-card.json")
async def get_agent_card(request: Request) -> Dict[str, Any]:
  """Returns the A2A Agent Card specification with A2UI extension capabilities."""
  base_url = str(request.base_url).rstrip("/")
  return {
      "name": "PitchGen",
      "description": (
          "PitchGen Agent for creating, searching, transforming, and"
          " translating Google Cloud sales presentation decks."
      ),
      "url": base_url,
      "version": "2.0.0",
      "protocolVersion": "0.3.0",
      "preferredTransport": "JSONRPC",
      "defaultInputModes": ["text/plain"],
      "defaultOutputModes": ["text/plain", "application/json"],
      "capabilities": {
          "streaming": True,
          "extensions": [
              {
                  "uri": a2ui.A2UI_URI_V08,
                  "description": "Ability to render native A2UI v0.8 cards",
                  "required": False,
              },
              {
                  "uri": a2ui.A2UI_URI_V09,
                  "description": (
                      "Ability to render native A2UI v0.9 cards & Canvas panels"
                  ),
                  "required": False,
                  "params": {
                      "supportedCatalogIds": [
                          a2ui.A2UI_BASIC_CATALOG_ID,
                          a2ui.A2UI_MATERIAL_CATALOG_ID,
                          a2ui.A2UI_GE_CUSTOM_CATALOG_ID,
                      ]
                  },
              },
          ],
      },
      "skills": [
          {
              "id": "gtm_intake_card",
              "name": "GTM Deck Configuration & Intake",
              "description": (
                  "Captures business context, sales play, industry, and deck"
                  " strategy."
              ),
              "tags": ["intake", "strategy", "gtm", "a2ui"],
          },
          {
              "id": "outline_review_card",
              "name": "Proposal Outline & Agenda Review",
              "description": (
                  "Presents synthesized presentation agenda sections for"
                  " interactive review."
              ),
              "tags": ["outline", "agenda", "review", "a2ui"],
          },
          {
              "id": "slide_search_panel",
              "name": "Slide Search & Side Panel Insertion",
              "description": (
                  "Searches vetted CloudHub slide repositories with visual"
                  " thumbnails."
              ),
              "tags": ["search", "reusable", "cloudhub", "slides"],
          },
          {
              "id": "nano_banana_diagram",
              "name": "Nano Banana Architectural Synthesis",
              "description": (
                  "Generates technical architecture and flow diagrams."
              ),
              "tags": ["diagram", "architecture", "nano_banana"],
          },
      ],
  }


@app.post("/api/test/identity")
async def test_identity_resolution(req: IdentityTestRequest) -> Dict[str, Any]:
  """Direct endpoint for testing GE OAuth token exchange and user LDAP resolution."""
  email, ldap = a2ui.resolve_ge_user_identity(
      access_token=req.access_token,
      fallback_ldap=req.fallback_ldap or "",
  )
  return {
      "status": "success",
      "user_email": email,
      "user_ldap": ldap,
      "token_provided": bool(req.access_token),
  }


# ==============================================================================
# Action Event Extraction Ladder (From AskHR / GE Standard)
# ==============================================================================
def extract_action_payload(
    params: Dict[str, Any],
) -> tuple[str, Dict[str, Any]]:
  """Extracts structured action name and parameters from incoming client actions.

  Handles:
  - Direct params.prompt or message text
  - A2UI userAction / clientAction envelopes
  - Nested context arrays with key-value pairs
  - Action button names
  """
  action_obj = (
      params.get("userAction")
      or params.get("action")
      or params.get("clientAction")
      or params.get("event")
  )
  if isinstance(action_obj, dict) and isinstance(action_obj.get("event"), dict):
    action_obj = action_obj["event"]
  if not action_obj and isinstance(params.get("message"), dict):
    meta = params["message"].get("metadata", {})
    action_obj = (
        meta.get("action")
        or meta.get("userAction")
        or meta.get("event")
        or params["message"].get("action")
        or params["message"].get("userAction")
        or params["message"].get("event")
    )
    if not action_obj:
      for p in params["message"].get("parts", []):
        if isinstance(p, dict):
          p_data = p.get("data") if isinstance(p.get("data"), dict) else None
          if p_data:
            action_obj = (
                p_data.get("userAction")
                or p_data.get("action")
                or p_data.get("clientAction")
                or p_data.get("event")
                or p_data
            )
            break
    if isinstance(action_obj, dict) and isinstance(
        action_obj.get("event"), dict
    ):
      action_obj = action_obj["event"]

  extracted_prompt = None
  extracted_params: Dict[str, Any] = {}

  if isinstance(action_obj, dict):
    extracted_params = (
        action_obj.get("parameters") or action_obj.get("args") or {}
    )
    ctx = action_obj.get("context") or {}

    if isinstance(ctx, list):
      for item in ctx:
        if isinstance(item, dict) and "key" in item:
          k = item["key"]
          val = item.get("value")
          if isinstance(val, dict):
            extracted_params[k] = val.get("literalString") or val.get("value")
          else:
            extracted_params[k] = val
      if "prompt" in extracted_params:
        extracted_prompt = str(extracted_params["prompt"])
    elif isinstance(ctx, dict):
      extracted_params.update(ctx)
      extracted_prompt = ctx.get("prompt")

    if not extracted_prompt and "prompt" in action_obj:
      extracted_prompt = action_obj.get("prompt")

    if not extracted_prompt and action_obj.get("actionName"):
      extracted_prompt = action_obj["actionName"]
    elif not extracted_prompt and action_obj.get("name"):
      extracted_prompt = action_obj["name"]

  # Fallback to standard message text
  user_text = ""
  if "message" in params and isinstance(params["message"], dict):
    for p in params["message"].get("parts", []):
      if isinstance(p, dict) and p.get("kind") == "text":
        user_text += p.get("text", "")
      elif isinstance(p, dict) and "text" in p:
        user_text += p.get("text", "")
  elif "prompt" in params:
    user_text = str(params["prompt"])
  elif "text" in params:
    user_text = str(params["text"])

  if extracted_prompt:
    return extracted_prompt.strip(), extracted_params
  return user_text.strip(), extracted_params


# ==============================================================================
# Turn Execution & A2UI Dispatcher
# ==============================================================================
DEFAULT_PRESENTATION_ID = "SAMPLE_PRESENTATION_ID_PLACEHOLDER_00001"
DEFAULT_DECK_URL = (
    f"https://docs.google.com/presentation/d/{DEFAULT_PRESENTATION_ID}/edit"
)


def execute_pitchgen_turn(
    message: str,
    action_params: Dict[str, Any],
    user_ldap: str = "",
) -> Dict[str, Any]:
  """Dispatches user message or UI action to the appropriate PitchGen A2UI card."""
  msg_lower = message.lower().strip()
  target_card = (
      str(
          action_params.get("target_card")
          or action_params.get("targetCard")
          or action_params.get("workflow_mode")
          or action_params.get("workflowMode")
          or ""
      )
      .lower()
      .strip()
  )
  a2ui_payloads: List[Dict[str, Any]] = []
  response_text = ""

  # 0. Welcome / Introduction Feature Launcher Hub (pitchgen-launcher)
  if not target_card and any(
      k in msg_lower for k in ["pitchgen-launcher", "launcher"]
  ):
    a2ui_payloads.extend(a2ui.create_a2ui_v09_launcher_messages())
    response_text = (
        "👋 Welcome to **PitchGen** — your AI-Powered Presentation & Visual"
        " Suite for Gemini Enterprise! Select any of the 8 capabilities in the"
        " interactive launcher below, or tell me what you need."
    )
  elif not target_card and any(
      k in msg_lower
      for k in ["intro", "welcome", "get started", "welcome_intro"]
  ):
    card = a2ui.create_welcome_intro_card(user_ldap=user_ldap)
    a2ui_payloads.append(card)
    response_text = (
        "👋 Welcome to **PitchGen**! Select one of the core enablement"
        " workflows below to get started, or tell me about the customer pitch"
        " you need."
    )

  # 1. GTM Intake Card (including 'Launch Deck Generation ->' button from pitchgen-launcher)
  elif target_card in ("generate_pitch", "generate_slide", "intake") or any(
      k in msg_lower
      for k in [
          "intake",
          "configure",
          "start deck",
          "new pitch",
          "setup deck",
          "launch deck generation",
      ]
  ):
    card = a2ui.create_gtm_intake_card(
        user_prompt=action_params.get(
            "user_prompt", message if "intake" not in msg_lower else ""
        ),
        customer_name=action_params.get("customer_name")
        or action_params.get("target_customer", "Target"),
        sales_play=action_params.get("sales_play", "Scale AI Apps & Agents"),
        industry=action_params.get("industry", "Retail & Consumer"),
        audience=action_params.get("audience")
        or action_params.get(
            "target_audience", "C-Level / Executive Leadership"
        ),
        region=action_params.get("region")
        or action_params.get("target_region", "NORTHAM"),
        deck_strategy=action_params.get("deck_strategy", "smart_hybrid"),
        deck_length=action_params.get("deck_length", "Standard (8-12 slides)"),
    )
    a2ui_payloads.append(card)
    response_text = (
        "I have configured the GTM Intake Card for your pitch deck. Please"
        " review the strategy and parameters below."
    )

  # 2. Outline Review & Interactive Refinement Card
  elif any(
      k in msg_lower
      for k in [
          "generate_outline",
          "review outline",
          "refine_outline",
          "refine outline",
          "agenda",
          "outline",
      ]
  ) and not any(
      k in msg_lower
      for k in ["approve", "generate_deck", "create deck", "synthesize deck"]
  ):
    customer = (
        action_params.get("customer_name")
        or action_params.get("target_customer")
        or "Target"
    )
    existing_agenda = action_params.get("agenda_sections")
    refine_prompt = (
        action_params.get("refine_prompt")
        or action_params.get("prompt")
        or action_params.get("user_prompt")
        or ""
    )

    if (
        existing_agenda
        and isinstance(existing_agenda, list)
        and len(existing_agenda) > 0
    ):
      agenda = [dict(sec) for sec in existing_agenda]
    else:
      agenda = [
          {
              "title": "Executive Summary & Industry Challenges",
              "subtopics": ["Retail Transformation", "Margins & CX"],
              "slide_count": 1,
          },
          {
              "title": "Current State Architecture & Latency Bottlenecks",
              "subtopics": ["Legacy Point Solutions", "Data Silos"],
              "slide_count": 2,
          },
          {
              "title": "Proposed Google Cloud Modernization Solution",
              "subtopics": ["Vertex AI Agents", "BigQuery Studio"],
              "slide_count": 2,
          },
          {
              "title": "Proven Business Value & 3.2x ROI Proof Points",
              "subtopics": [
                  "Tier-1 Retail Case Studies",
                  "Total Cost of Ownership",
              ],
              "slide_count": 2,
          },
          {
              "title": "Deployment Roadmap & Strategic Next Steps",
              "subtopics": ["Production Pilot", "Partner Services Alignment"],
              "slide_count": 1,
          },
      ]

    refine_note = ""
    if refine_prompt:
      p_lower = refine_prompt.lower()
      if (
          "security" in p_lower
          or "compliance" in p_lower
          or "governance" in p_lower
      ):
        agenda.insert(
            min(3, len(agenda)),
            {
                "title": "Enterprise Security, Governance & Zero Trust",
                "subtopics": [
                    "FedRAMP / SOC2",
                    "Data Residency",
                    "Cloud IAM Guardrails",
                ],
                "slide_count": 1,
            },
        )
        refine_note = "Added Security, Governance & Zero Trust slide section."
      elif "roi" in p_lower or "case study" in p_lower or "proof" in p_lower:
        agenda.insert(
            min(4, len(agenda)),
            {
                "title": "Tier-1 Customer Proof Points & Verified ROI",
                "subtopics": [
                    "Quantified Margin Impact",
                    "Executive References",
                    "9-Month Payback",
                ],
                "slide_count": 2,
            },
        )
        refine_note = "Added Customer Proof Points & Quantified ROI section."
      elif "shorten" in p_lower or "4 slide" in p_lower:
        agenda = [
            {
                "title": "Executive Summary & Business Challenge",
                "subtopics": ["Market Opportunity", "Strategic Fit"],
                "slide_count": 1,
            },
            {
                "title": "Google Cloud Solution Architecture",
                "subtopics": ["Vertex AI Agents", "Modern Data Platform"],
                "slide_count": 1,
            },
            {
                "title": "Business Value, ROI & Proof Points",
                "subtopics": ["3.2x ROI", "Payback in 9 Months"],
                "slide_count": 1,
            },
            {
                "title": "Pilot Roadmap & Next Steps",
                "subtopics": ["4-Week Kickoff", "Executive Sponsorship"],
                "slide_count": 1,
            },
        ]
        refine_note = (
            "Consolidated outline into 4 high-impact executive slides."
        )
      elif (
          "architecture" in p_lower
          or "technical" in p_lower
          or "deep dive" in p_lower
      ):
        for item in agenda:
          if "Solution" in item.get("title", "") or "Architecture" in item.get(
              "title", ""
          ):
            item["slide_count"] = max(item.get("slide_count", 1), 2)
            sub = item.setdefault("subtopics", [])
            if "Low-Latency VPC-SC" not in sub:
              sub.extend(["Low-Latency VPC-SC", "Model Grounding Topology"])
        refine_note = "Expanded Technical Architecture & Blueprint depth."
      else:
        agenda.append({
            "title": f"Strategic Focus: {refine_prompt[:35]}",
            "subtopics": ["Account Specific Alignment", "Execution Milestones"],
            "slide_count": 1,
        })
        refine_note = (
            f"Tailored narrative with custom focus: '{refine_prompt[:35]}'."
        )

    card = a2ui.create_outline_review_card(
        customer_name=customer,
        agenda_sections=agenda,
        deck_strategy=action_params.get("deck_strategy", "smart_hybrid"),
        executive_summary=(
            f"Tailored AI-driven retail enablement proposal for {customer}."
        ),
    )
    a2ui_payloads.append(card)
    if refine_note:
      response_text = (
          f"✨ **Outline Refined:** {refine_note}\n\nReview the updated"
          " interactive sections below. You can make further edits or click"
          " **Approve & Generate Deck**."
      )
    else:
      response_text = (
          f"Here is the interactive proposal outline for **{customer}**. You"
          " can edit section titles, slide counts, subtopics, or refine with"
          " Gemini below."
      )

  # 3. Slide Search Side Panel
  elif target_card in ("search_slide", "search") or any(
      k in msg_lower
      for k in [
          "search",
          "find slides",
          "browse slides",
          "cloudhub slides",
          "insert_library_slide",
      ]
  ):
    query = action_params.get("search_query") or "Retail AI"
    results = [
        {
            "slide_id": "slide_arch_101",
            "title": "Vertex AI Agent Engine Reference Architecture",
            "slide_job": "Architecture",
            "category": "AI/ML Solutions",
            "thumbnail_url": (
                "https://storage.googleapis.com/cloudhub/sample_arch_thumb.png"
            ),
            "summary": (
                "Full microservices blueprint for enterprise agentic workflows"
                " with low-latency grounding."
            ),
        },
        {
            "slide_id": "slide_roi_204",
            "title": "Retail Omnichannel Personalization Proof Point",
            "slide_job": "Proof_Points",
            "category": "Customer Success",
            "thumbnail_url": (
                "https://storage.googleapis.com/cloudhub/sample_roi_thumb.png"
            ),
            "summary": (
                "Demonstrates 35% improvement in basket size and 2.8x"
                " conversion for enterprise retailers."
            ),
        },
    ]
    card = a2ui.create_slide_search_panel_card(
        search_query=query,
        results=results,
        target_presentation_id=action_params.get("target_presentation_id")
        or action_params.get("presentation_id")
        or DEFAULT_PRESENTATION_ID,
    )
    a2ui_payloads.append(card)
    response_text = (
        f"Found **{len(results)} vetted slides** in CloudHub matching"
        f" '{query}'."
    )

  # 4. Nano Banana Diagram Synthesis
  elif target_card in (
      "generate_nanobanana",
      "transform_nanobanana",
      "diagram",
  ) or any(
      k in msg_lower
      for k in [
          "diagram",
          "architecture",
          "nano banana",
          "synthesize diagram",
          "transform_with_nano_banana",
          "generate_visuals",
          "generate visuals",
          "visuals",
      ]
  ):
    card = a2ui.create_nano_banana_card(
        presentation_id=action_params.get("presentation_id")
        or DEFAULT_PRESENTATION_ID,
        target_slide_index=int(action_params.get("target_slide_index", 1)),
        selected_model=action_params.get("nano_banana_model")
        or action_params.get("model", "nano_banana_pro"),
        visual_style=action_params.get(
            "visual_style",
            "Google Cloud Modern Architecture (Flat vector, precise topology)",
        ),
        reference_image_url=action_params.get("reference_image_url", ""),
    )
    a2ui_payloads.append(card)
    response_text = (
        "Generated technical architecture diagram using **Nano Banana (Pro)**."
    )

  # 5. Slide Text Transformation
  elif target_card in (
      "transform_text",
      "transform_slide",
      "translate",
      "transform",
  ) or any(
      k in msg_lower
      for k in [
          "transform",
          "polish",
          "rewrite",
          "tone",
          "transform_deck_text",
          "transform_slide_text",
      ]
  ):
    raw_deck = (
        action_params.get("presentation_url_or_id")
        or action_params.get("presentation_id")
        or action_params.get("presentation_url")
        or action_params.get("target_presentation_id")
        or action_params.get("deck_url")
        or ""
    )
    pres_id = a2ui.extract_presentation_id(str(raw_deck)) if raw_deck else None

    if not pres_id:
      card = a2ui.create_provide_deck_prompt_card(
          customer_name=action_params.get("target_customer")
          or action_params.get("customer_name", "")
      )
      a2ui_payloads.append(card)
      response_text = (
          "⚠️ **No Active Deck on Canvas**: To transform or polish slide text,"
          " please provide your Google Slides URL or Presentation ID below (or"
          " load one onto the Canvas panel)."
      )
    else:
      full_deck_scope_val = action_params.get("full_deck_scope")
      slide_range_val = (
          action_params.get("target_slide_indices")
          or action_params.get("slide_range")
          or "1"
      )
      if (
          isinstance(full_deck_scope_val, list)
          and "full_deck" in full_deck_scope_val
      ):
        scope_val = "full_deck"
      else:
        scope_val = action_params.get("transform_scope") or action_params.get(
            "scope", "current_slide"
        )
      try:
        slide_idx = int(
            str(slide_range_val).split(",")[0].split("-")[0].strip()
        )
      except Exception:
        slide_idx = 1

      audience_raw = action_params.get("target_audience") or action_params.get(
          "audience", "C-Level / Executive Leadership"
      )
      if isinstance(audience_raw, list):
        cleaned_aud = [
            str(a).strip()
            for a in audience_raw
            if str(a).strip()
            and str(a).strip().lower() not in ("audience", "— (blank)")
        ]
        audience_str = ", ".join(cleaned_aud) if cleaned_aud else "Executive"
      else:
        audience_str = str(audience_raw)

      card = a2ui.create_text_transform_card(
          presentation_id=pres_id,
          scope=scope_val,
          selected_slide_index=slide_idx,
          slide_job=action_params.get("slide_job", "Solution_Overview"),
          customer_name=action_params.get("target_customer")
          or action_params.get("customer_name", "Target"),
          region=action_params.get("target_region")
          or action_params.get("region", "AMER"),
          audience=audience_str,
          language=action_params.get("target_language")
          or action_params.get("language", "English"),
      )
      a2ui_payloads.append(card)
      response_text = (
          f"Ready to polish slide text for presentation `{pres_id}` using"
          f" **Executive Tone** ({scope_val}) for"
          f" **{action_params.get('target_customer') or action_params.get('customer_name') or 'Target'}**"
          f" in **{action_params.get('target_language', 'English')}**."
      )

  # 6. Outline Approval & Full Deck Generation / Canvas Panel Preview
  elif any(
      k in msg_lower
      for k in [
          "approve_outline_and_generate",
          "generate_deck",
          "generate deck",
          "create deck",
          "synthesize deck",
          "presentation deck",
          "show deck",
          "open deck",
          "deck",
      ]
  ):
    customer = (
        action_params.get("customer_name")
        or action_params.get("target_customer")
        or "Target"
    )
    strategy = action_params.get("deck_strategy", "smart_hybrid")
    er_num = action_params.get("er_number", "006Kf00000M0PJcIAN")
    agenda_sections = action_params.get("agenda_sections") or []
    total_slides = (
        sum(s.get("slide_count", 1) for s in agenda_sections)
        if agenda_sections
        else 8
    )
    num_sections = len(agenda_sections) if agenda_sections else 5
    section_summary = (
        f" Built with **{num_sections} customized sections** ({total_slides}"
        " slides)."
        if agenda_sections
        else ""
    )
    deck_url = action_params.get("deck_url") or (
        f"https://docs.google.com/presentation/d/{action_params['presentation_id']}/edit"
        if action_params.get("presentation_id")
        else DEFAULT_DECK_URL
    )
    card_dict = a2ui.format_a2ui_deck_card(
        deck_url=deck_url,
        customer_name=customer,
        er_number=er_num,
        user_ldap=user_ldap,
    )
    card = card_dict.get("a2ui_card", card_dict)
    if "canvasPreview" in card:
      card["canvasPreview"]["autoOpen"] = True
      card["canvasPreview"]["customerName"] = customer
    a2ui_payloads.append(card)
    response_text = (
        "🚀 **Your PitchGen presentation deck is ready!**\n\nThe **Canvas"
        " Panel** on the right has opened to showcase your new deck for"
        f" **{customer}** (Strategy: `{strategy}`).{section_summary} You can"
        " review the slides directly in the embedded canvas, open them in"
        " Google Slides, or apply tone and visual transformations below."
    )

  # 7. Default: Generated Presentation Deck Card with Canvas Preview
  else:
    deck_url = action_params.get("deck_url") or (
        f"https://docs.google.com/presentation/d/{action_params['presentation_id']}/edit"
        if action_params.get("presentation_id")
        else DEFAULT_DECK_URL
    )
    card_dict = a2ui.format_a2ui_deck_card(
        deck_url=deck_url,
        customer_name="Target",
        er_number="006Kf00000M0PJcIAN",
        user_ldap=user_ldap,
    )
    card = card_dict.get("a2ui_card", card_dict)
    if "canvasPreview" in card:
      card["canvasPreview"]["autoOpen"] = True
    a2ui_payloads.append(card)
    response_text = (
        "Your PitchGen presentation deck is ready! You can preview it in"
        " Canvas, open it in Google Slides, or refine it using the quick"
        " actions below."
    )

  return {
      "text": response_text,
      "a2ui_payloads": a2ui_payloads,
  }


# ==============================================================================
# A2A Protocol Endpoints (JSON-RPC 2.0 & SSE)
# ==============================================================================
@app.post("/")
@app.post("/a2a/v1/tasks/send")
@app.post("/a2a/v1/message:send")
@app.post("/a2a/v1/chat")
async def a2a_tasks_send(request: Request):
  """A2A protocol endpoint supporting standard JSON-RPC and SSE text/event-stream."""
  try:
    body = await request.json()
  except Exception as exc:
    raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

  if not isinstance(body, dict):
    body = {}

  rpc_id = body.get("id", "1")
  raw_params = body.get("params")
  params = raw_params if isinstance(raw_params, dict) else body
  session_id = params.get("sessionId") or str(uuid.uuid4())

  # Identity resolution from GE OAuth or headers
  auth_header = request.headers.get("authorization", "")
  token = (
      auth_header.replace("Bearer ", "")
      if "Bearer " in auth_header
      else params.get("oauth_token")
  )
  _, resolved_ldap = a2ui.resolve_ge_user_identity(access_token=token)

  user_message, action_params = extract_action_payload(params)
  if not user_message:
    user_message = "intro"

  logger.info(
      "A2A turn | ldap: %s | session: %s | msg: %r",
      resolved_ldap,
      session_id,
      user_message,
  )

  turn_result = execute_pitchgen_turn(
      message=user_message,
      action_params=action_params,
      user_ldap=resolved_ldap,
  )

  a2a_parts: List[Dict[str, Any]] = []
  if turn_result["text"]:
    a2a_parts.append({"kind": "text", "text": turn_result["text"]})

  for p in turn_result["a2ui_payloads"]:
    a2a_parts.append({
        "kind": "data",
        "metadata": {"mimeType": a2ui.A2UI_MIME_TYPE},
        "data": p,
    })
    if (
        isinstance(p, dict)
        and "canvasPreview" in p
        and p["canvasPreview"].get("iframeUrl")
    ):
      canvas_info = p["canvasPreview"]
      a2a_parts.append({
          "kind": "artifact",
          "artifact": a2ui.create_ge_canvas_artifact(
              deck_url=canvas_info.get("workspaceUri", ""),
              title=p.get("title", "PitchGen Presentation Deck"),
              customer_name=canvas_info.get("customerName", ""),
          ),
      })

  msg_obj = {
      "messageId": str(uuid.uuid4()),
      "role": "agent",
      "parts": a2a_parts,
  }

  accept_header = request.headers.get("accept", "").lower()
  is_sse = "text/event-stream" in accept_header or bool(params.get("streaming"))

  if is_sse:

    async def sse_generator():
      payload = {
          "jsonrpc": "2.0",
          "id": rpc_id,
          "result": {
              "id": session_id,
              "taskId": session_id,
              "contextId": session_id,
              "status": {"state": "completed", "message": msg_obj},
              "final": True,
              "message": msg_obj,
          },
      }
      yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

  return JSONResponse(
      content={
          "jsonrpc": "2.0",
          "id": rpc_id,
          "result": {
              "id": session_id,
              "taskId": session_id,
              "contextId": session_id,
              "status": {"state": "completed", "message": msg_obj},
              "final": True,
              "message": msg_obj,
          },
      }
  )


# ==============================================================================
# Local Visual Test Harness Web Interface (GET /)
# ==============================================================================
HTML_TESTER = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PitchGen A2UI - Visual Test Harness</title>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;700&family=Roboto:wght@300;400;500&display=swap">
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0">
  <style>
    :root {
      --bg: #0b0f19;
      --surface: #131b2e;
      --card-bg: #1c2640;
      --border: #2c3a5e;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --accent: #10b981;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --chip-bg: #1e293b;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Google Sans', 'Roboto', sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }
    header {
      background: #0f172a;
      border-bottom: 1px solid var(--border);
      padding: 12px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 1.2rem;
      font-weight: 700;
      color: #fff;
    }
    .badge {
      font-size: 0.75rem;
      font-weight: 500;
      padding: 4px 10px;
      border-radius: 9999px;
      background: rgba(16, 185, 129, 0.15);
      color: var(--accent);
      border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .user-info {
      font-size: 0.85rem;
      color: var(--text-muted);
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .user-info strong { color: #fff; }
    .main-container {
      display: flex;
      flex: 1;
      overflow: hidden;
    }
    /* Left Sidebar: Workflow launchers */
    .sidebar {
      width: 320px;
      background: var(--surface);
      border-right: 1px solid var(--border);
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      overflow-y: auto;
    }
    .sidebar-section-title {
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      font-weight: 700;
    }
    .nav-btn {
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 12px 14px;
      border-radius: 10px;
      cursor: pointer;
      font-size: 0.9rem;
      text-align: left;
      display: flex;
      align-items: center;
      gap: 10px;
      transition: all 0.15s ease;
    }
    .nav-btn:hover {
      border-color: var(--primary);
      background: #233152;
      transform: translateX(2px);
    }
    .nav-btn .icon {
      color: var(--primary);
      font-size: 20px;
    }
    /* Identity Simulator Box */
    .identity-box {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .identity-box input {
      background: #0f172a;
      border: 1px solid var(--border);
      color: #fff;
      padding: 8px 10px;
      border-radius: 6px;
      font-size: 0.8rem;
    }
    .identity-box button {
      background: var(--primary);
      border: none;
      color: #fff;
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 0.8rem;
      cursor: pointer;
    }
    /* Chat & Canvas Area */
    .chat-view {
      flex: 1;
      display: flex;
      flex-direction: column;
      background: var(--bg);
      overflow: hidden;
    }
    .messages-container {
      flex: 1;
      padding: 24px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }
    .msg-row {
      display: flex;
      flex-direction: column;
      max-width: 85%;
    }
    .msg-row.user { align-self: flex-end; }
    .msg-row.bot { align-self: flex-start; width: 100%; max-width: 850px; }
    .bubble {
      padding: 14px 18px;
      border-radius: 14px;
      font-size: 0.95rem;
      line-height: 1.5;
    }
    .user .bubble { background: var(--primary); color: #fff; border-bottom-right-radius: 2px; }
    .bot .bubble { background: var(--surface); color: var(--text); border: 1px solid var(--border); border-bottom-left-radius: 2px; }

    /* A2UI Visual Component Renderers */
    .a2ui-card {
      margin-top: 14px;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .a2ui-card-title {
      font-size: 1.15rem;
      font-weight: 700;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .a2ui-card-subtitle {
      font-size: 0.85rem;
      color: var(--text-muted);
      margin-top: -10px;
    }
    .a2ui-form-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 14px;
    }
    .a2ui-field {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .a2ui-field.full-width {
      grid-column: 1 / -1;
    }
    .a2ui-field label {
      font-size: 0.8rem;
      font-weight: 500;
      color: var(--text-muted);
    }
    .a2ui-field input, .a2ui-field select, .a2ui-field textarea {
      background: #0f172a;
      border: 1px solid var(--border);
      color: #fff;
      padding: 9px 12px;
      border-radius: 8px;
      font-size: 0.88rem;
      font-family: inherit;
      outline: none;
      transition: border-color 0.15s ease;
    }
    .a2ui-field select {
      cursor: pointer;
      appearance: none;
      -webkit-appearance: none;
      background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%2394a3b8'%3e%3cpath d='M7 10l5 5 5-5z'/%3e%3c/svg%3e");
      background-repeat: no-repeat;
      background-position: right 10px center;
      background-size: 20px;
      padding-right: 34px;
    }
    .a2ui-field select option {
      background: #1e293b;
      color: #fff;
    }
    .a2ui-field input:focus, .a2ui-field select:focus, .a2ui-field textarea:focus {
      border-color: var(--primary);
    }
    .a2ui-info-banner {
      background: rgba(59, 130, 246, 0.12);
      border-left: 3px solid var(--primary);
      padding: 10px 14px;
      border-radius: 6px;
      font-size: 0.85rem;
      color: #93c5fd;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .a2ui-tile-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 14px;
    }
    .a2ui-slide-tile {
      background: rgba(15, 23, 42, 0.7);
      border: 1px solid var(--border);
      border-radius: 10px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }
    .a2ui-tile-thumb {
      width: 100%;
      height: 130px;
      object-fit: cover;
      background: #1e293b;
    }
    .a2ui-tile-content {
      padding: 12px 14px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .a2ui-tile-title {
      font-weight: 600;
      font-size: 0.9rem;
      color: #fff;
    }
    .a2ui-tile-meta {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .outline-strategy-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      background: rgba(15, 23, 42, 0.7);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 12px;
      margin-bottom: 12px;
    }
    .outline-strategy-label {
      font-size: 0.8rem;
      font-weight: 700;
      color: #94a3b8;
      display: flex;
      align-items: center;
      gap: 6px;
      white-space: nowrap;
    }
    .outline-strategy-select {
      flex: 1;
      max-width: 400px;
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 6px;
      color: #f8fafc;
      font-size: 0.82rem;
      font-weight: 500;
      padding: 6px 10px;
      cursor: pointer;
    }
    .outline-strategy-select:focus {
      outline: none;
      border-color: var(--primary);
    }
    .a2ui-agenda-list {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .editable-agenda-item {
      background: rgba(15, 23, 42, 0.7);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px 14px;
      transition: border-color 0.15s ease, background 0.15s ease;
    }
    .editable-agenda-item:hover {
      border-color: #3b82f6;
      background: rgba(30, 41, 59, 0.7);
    }
    .agenda-item-header {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 8px;
    }
    .outline-idx-badge {
      background: #1e293b;
      color: #93c5fd;
      font-size: 0.75rem;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 6px;
      border: 1px solid rgba(147, 197, 253, 0.2);
      flex-shrink: 0;
    }
    .outline-title-input {
      flex: 1;
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 6px;
      color: #f8fafc;
      font-size: 0.9rem;
      font-weight: 600;
      padding: 6px 10px;
    }
    .outline-title-input:focus {
      outline: none;
      border-color: var(--primary);
    }
    .outline-count-wrapper {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 0.8rem;
      color: var(--text-muted);
      flex-shrink: 0;
    }
    .outline-count-input {
      width: 48px;
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 6px;
      color: #fbbf24;
      font-weight: 700;
      text-align: center;
      padding: 4px;
      font-size: 0.85rem;
    }
    .btn-icon-danger {
      background: transparent;
      border: none;
      color: #ef4444;
      cursor: pointer;
      padding: 4px;
      border-radius: 4px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.15s ease;
    }
    .btn-icon-danger:hover {
      background: rgba(239, 68, 68, 0.15);
    }
    .outline-subtopics-input {
      width: 100%;
      background: rgba(15, 23, 42, 0.5);
      border: 1px dashed var(--border);
      border-radius: 6px;
      color: #94a3b8;
      font-size: 0.8rem;
      padding: 6px 10px;
      box-sizing: border-box;
    }
    .outline-subtopics-input:focus {
      outline: none;
      border-color: #3b82f6;
      color: #e2e8f0;
      background: #0f172a;
    }
    .btn-add-section {
      width: 100%;
      border: 1px dashed #3b82f6;
      background: rgba(59, 130, 246, 0.08);
      color: #93c5fd;
      border-radius: 8px;
      padding: 8px 14px;
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: background 0.15s ease;
    }
    .btn-add-section:hover {
      background: rgba(59, 130, 246, 0.18);
    }
    .outline-refine-box {
      margin-top: 12px;
      padding: 12px;
      background: rgba(15, 23, 42, 0.8);
      border: 1px solid rgba(147, 197, 253, 0.25);
      border-radius: 8px;
    }
    .outline-refine-box-title {
      font-size: 0.8rem;
      font-weight: 700;
      color: #93c5fd;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .outline-refine-input-row {
      display: flex;
      gap: 8px;
      margin-bottom: 8px;
    }
    .outline-refine-input {
      flex: 1;
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 6px;
      color: #f8fafc;
      font-size: 0.85rem;
      padding: 6px 10px;
    }
    .outline-refine-input:focus {
      outline: none;
      border-color: #60a5fa;
    }
    .chip-presets {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .chip-preset {
      background: #1e293b;
      border: 1px solid rgba(255, 255, 255, 0.1);
      color: #cbd5e1;
      font-size: 0.75rem;
      padding: 4px 8px;
      border-radius: 12px;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .chip-preset:hover {
      background: #2563eb;
      color: #fff;
      border-color: #3b82f6;
    }
    .a2ui-actions-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 6px;
    }
    .btn-action {
      background: #1e293b;
      border: 1px solid var(--border);
      color: #93c5fd;
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 0.85rem;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }
    .btn-action:hover {
      background: var(--primary);
      color: #fff;
      border-color: var(--primary);
    }
    .btn-action.primary {
      background: var(--primary);
      color: #fff;
      border-color: var(--primary);
    }
    .btn-action.primary:hover {
      background: var(--primary-hover);
    }
    /* A2UI Stepper / Guided Tabs Component */
    .a2ui-stepper {
      display: flex;
      flex-direction: column;
      gap: 16px;
      width: 100%;
    }
    .stepper-header {
      display: flex;
      align-items: center;
      gap: 8px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 8px;
      overflow-x: auto;
    }
    .stepper-tab {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 14px;
      border-radius: 8px;
      background: rgba(15, 23, 42, 0.6);
      border: 1px solid var(--border);
      color: var(--text-muted);
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
      white-space: nowrap;
    }
    .stepper-tab:hover {
      background: rgba(30, 41, 59, 0.8);
      color: #fff;
      border-color: #3b82f6;
    }
    .stepper-tab.active {
      background: rgba(59, 130, 246, 0.15);
      border-color: var(--primary);
      color: #93c5fd;
    }
    .stepper-tab-badge {
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: #1e293b;
      color: #94a3b8;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.75rem;
      font-weight: 700;
    }
    .stepper-tab.active .stepper-tab-badge {
      background: var(--primary);
      color: #fff;
    }
    .stepper-step {
      display: none;
      flex-direction: column;
      gap: 14px;
    }
    .stepper-step.active {
      display: flex;
    }
    .stepper-step-desc {
      font-size: 0.82rem;
      color: var(--text-muted);
      margin-bottom: 4px;
    }
    .stepper-nav-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-top: 14px;
      padding-top: 12px;
      border-top: 1px solid rgba(255, 255, 255, 0.08);
    }
    .canvas-iframe-container {
      width: 100%;
      height: 380px;
      border-radius: 8px;
      overflow: hidden;
      border: 1px solid var(--border);
      background: #000;
      margin-top: 8px;
    }
    .canvas-iframe-container iframe {
      width: 100%;
      height: 100%;
      border: none;
    }
    /* Gemini Enterprise Canvas Side Panel (WS_SLIDES) */
    .canvas-panel {
      width: 0;
      opacity: 0;
      pointer-events: none;
      background: #080d1a;
      border-left: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      transition: width 0.3s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.25s ease;
      overflow: hidden;
      position: relative;
      z-index: 10;
    }
    .canvas-panel.open {
      width: 52%;
      min-width: 480px;
      opacity: 1;
      pointer-events: auto;
    }
    .canvas-panel.expanded {
      width: 75%;
    }
    .canvas-header {
      padding: 12px 18px;
      background: #0f172a;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-shrink: 0;
    }
    .canvas-header-left {
      display: flex;
      align-items: center;
      gap: 10px;
      overflow: hidden;
      min-width: 0;
    }
    .canvas-title {
      font-size: 0.95rem;
      font-weight: 700;
      color: #fff;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .canvas-subtitle {
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .canvas-header-actions {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-shrink: 0;
    }
    .canvas-icon-btn {
      background: #1e293b;
      border: 1px solid var(--border);
      color: #94a3b8;
      padding: 6px 10px;
      border-radius: 6px;
      font-size: 0.8rem;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      text-decoration: none;
      transition: all 0.15s ease;
    }
    .canvas-icon-btn:hover {
      background: #334155;
      color: #fff;
      border-color: #64748b;
    }
    .canvas-icon-btn.close:hover {
      background: #ef4444;
      color: #fff;
      border-color: #ef4444;
    }
    .canvas-body {
      flex: 1;
      display: flex;
      flex-direction: column;
      padding: 16px;
      gap: 12px;
      overflow-y: auto;
      background: radial-gradient(circle at top right, rgba(59, 130, 246, 0.05), transparent 70%);
    }
    .canvas-iframe-container-panel {
      flex: 1;
      min-height: 480px;
      border-radius: 10px;
      overflow: hidden;
      border: 1px solid var(--border);
      background: #000;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
      position: relative;
    }
    .canvas-iframe-container-panel iframe {
      width: 100%;
      height: 100%;
      border: none;
    }
    .canvas-notice {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.75rem;
      color: var(--text-muted);
      padding: 0 4px;
    }
    .canvas-footer-toolbar {
      padding: 12px 18px;
      background: #0f172a;
      border-top: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      gap: 6px;
      flex-shrink: 0;
    }
    .canvas-quick-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .a2ui-canvas-indicator {
      background: rgba(245, 158, 11, 0.1);
      border: 1px solid rgba(245, 158, 11, 0.35);
      border-radius: 10px;
      padding: 12px 16px;
      display: flex;
      align-items: center;
      gap: 12px;
      margin-top: 8px;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .a2ui-canvas-indicator:hover {
      background: rgba(245, 158, 11, 0.18);
      border-color: rgba(245, 158, 11, 0.6);
    }
    /* Input Bar */
    .input-bar {
      background: #0f172a;
      border-top: 1px solid var(--border);
      padding: 16px 24px;
      display: flex;
      gap: 12px;
    }
    .input-bar input {
      flex: 1;
      background: var(--surface);
      border: 1px solid var(--border);
      color: #fff;
      padding: 12px 16px;
      border-radius: 10px;
      font-size: 0.95rem;
      outline: none;
    }
    .input-bar input:focus { border-color: var(--primary); }
    .input-bar button {
      background: var(--primary);
      color: #fff;
      border: none;
      padding: 12px 22px;
      border-radius: 10px;
      font-weight: 500;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <span class="material-symbols-outlined" style="color: #60a5fa;">slideshow</span>
      PitchGen - A2UI Visual Test Harness
    </div>
    <div style="display: flex; align-items: center; gap: 16px;">
      <span class="badge">A2A v1.0 / A2UI Active</span>
      <div class="user-info">
        <span class="material-symbols-outlined" style="font-size: 18px;">person</span>
        Resolved LDAP: <strong id="active-ldap">seller_user</strong>
      </div>
    </div>
  </header>

  <div class="main-container">
    <!-- Left Navigation -->
    <div class="sidebar">
      <div class="sidebar-section-title">Core A2UI Workflows</div>
      <button class="nav-btn" onclick="sendPrompt('pitchgen-launcher')">
        <span class="material-symbols-outlined icon">apps</span>
        <div>
          <strong>0A. PitchGen Launcher (A2UI v0.9)</strong>
          <div style="font-size: 0.75rem; color: var(--text-muted);">8-card v0.9 feature hub with custom SVGs</div>
        </div>
      </button>

      <button class="nav-btn" onclick="sendPrompt('intro')">
        <span class="material-symbols-outlined icon">waving_hand</span>
        <div>
          <strong>0. Intro / Welcome Card</strong>
          <div style="font-size: 0.75rem; color: var(--text-muted);">Session start & feature menu</div>
        </div>
      </button>

      <button class="nav-btn" onclick="sendPrompt('intake')">
        <span class="material-symbols-outlined icon">assignment</span>
        <div>
          <strong>1. GTM Intake Card (Start New Pitch)</strong>
          <div style="font-size: 0.75rem; color: var(--text-muted);">Popup fields -> Generates Outline</div>
        </div>
      </button>

      <button class="nav-btn" onclick="sendPrompt('search')">
        <span class="material-symbols-outlined icon">search</span>
        <div>
          <strong>2. Slide Search Panel</strong>
          <div style="font-size: 0.75rem; color: var(--text-muted);">CloudHub vetted slides & insertion</div>
        </div>
      </button>

      <button class="nav-btn" onclick="sendPrompt('transform')">
        <span class="material-symbols-outlined icon">auto_fix_high</span>
        <div>
          <strong>3. Slide Text Transform</strong>
          <div style="font-size: 0.75rem; color: var(--text-muted);">Slide Jobs executive tone polish</div>
        </div>
      </button>

      <button class="nav-btn" onclick="sendPrompt('diagram')">
        <span class="material-symbols-outlined icon">account_tree</span>
        <div>
          <strong>4. Nano Banana Diagram</strong>
          <div style="font-size: 0.75rem; color: var(--text-muted);">Architecture synthesis preview</div>
        </div>
      </button>

      <button class="nav-btn" onclick="openCanvasPanel(currentCanvasIframeUrl, 'Active Pitch Deck Preview', currentCanvasDeckUrl); sendPrompt('deck');">
        <span class="material-symbols-outlined icon">co_present</span>
        <div>
          <strong>5. Canvas Panel Preview</strong>
          <div style="font-size: 0.75rem; color: var(--text-muted);">Embedded WS_SLIDES iframe</div>
        </div>
      </button>

      <div class="sidebar-section-title" style="margin-top: 10px;">Active Target Deck</div>
      <div class="identity-box">
        <div style="font-size: 0.75rem; color: var(--text-muted);">Current Google Slides URL or ID</div>
        <input type="text" id="target-deck-input" value="" placeholder="Paste presentation URL or ID...">
        <div style="display: flex; gap: 6px;">
          <button onclick="setTargetDeck()" style="flex: 1;">Set & Load Deck</button>
          <button onclick="openSlidesInNewTab()" style="background: #334155; padding: 6px 10px;" title="Open in Google Slides"><span class="material-symbols-outlined" style="font-size: 16px;">open_in_new</span></button>
        </div>
      </div>

      <div class="sidebar-section-title" style="margin-top: 10px;">Identity & OAuth Simulator</div>
      <div class="identity-box">
        <div style="font-size: 0.75rem; color: var(--text-muted);">Simulate GE OAuth Bearer Token</div>
        <input type="text" id="oauth-token-input" placeholder="Paste token or leave blank...">
        <button onclick="testIdentity()">Verify & Sync Identity</button>
      </div>
    </div>

    <!-- Chat & A2UI Canvas -->
    <div class="chat-view">
      <div class="messages-container" id="chat-stream"></div>

      <div class="input-bar">
        <input type="text" id="user-input" placeholder="Type a message or click a workflow card on the left..." autofocus>
        <button onclick="sendMessage()"><span class="material-symbols-outlined">send</span> Send</button>
      </div>
    </div>

    <!-- Gemini Enterprise Canvas Side Panel (WS_SLIDES) -->
    <div class="canvas-panel" id="canvas-panel">
      <div class="canvas-header">
        <div class="canvas-header-left">
          <span class="material-symbols-outlined" style="color: #f59e0b; font-size: 22px;">co_present</span>
          <div style="min-width: 0;">
            <div class="canvas-title" id="canvas-title">Presentation Deck Preview</div>
            <div class="canvas-subtitle" id="canvas-subtitle">Workspace Slides &bull; Embedded Viewer</div>
          </div>
          <span class="badge" style="background: rgba(245,158,11,0.15); color: #fbbf24; border-color: rgba(245,158,11,0.3); margin-left: 6px;">WS_SLIDES</span>
        </div>
        <div class="canvas-header-actions">
          <a id="canvas-open-tab" href="https://docs.google.com/presentation/d/SAMPLE_PRESENTATION_ID_PLACEHOLDER_00001/edit" target="_blank" class="canvas-icon-btn" title="Open in Google Slides (external tab)">
            <span class="material-symbols-outlined" style="font-size: 16px;">open_in_new</span>
            <span>Slides</span>
          </a>
          <button class="canvas-icon-btn" onclick="reloadCanvas()" title="Reload Canvas Embed">
            <span class="material-symbols-outlined" style="font-size: 16px;">refresh</span>
          </button>
          <button class="canvas-icon-btn" id="canvas-size-toggle" onclick="toggleCanvasExpand()" title="Expand / Minimize Canvas">
            <span class="material-symbols-outlined" style="font-size: 16px;">fullscreen</span>
          </button>
          <button class="canvas-icon-btn close" onclick="closeCanvasPanel()" title="Close Canvas Panel">
            <span class="material-symbols-outlined" style="font-size: 16px;">close</span>
          </button>
        </div>
      </div>

      <div class="canvas-body">
        <div class="canvas-iframe-container-panel">
          <iframe id="canvas-iframe" src="" allow="autoplay; encrypted-media; fullscreen" allowfullscreen></iframe>
        </div>
        <div class="canvas-notice">
          <span class="material-symbols-outlined" style="font-size: 15px; color: #94a3b8;">info</span>
          <span>Live presentation canvas &bull; Edit access granted to <strong id="canvas-user-ldap">seller_user</strong> &bull; Syncs with Google Drive</span>
        </div>
      </div>

      <div class="canvas-footer-toolbar">
        <div style="font-size: 0.72rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px;">
          Direct Slide Transformations
        </div>
        <div class="canvas-quick-actions">
          <button class="btn-action" onclick="sendPrompt('transform')">
            <span class="material-symbols-outlined" style="font-size: 15px;">auto_fix_high</span> Polish Tone
          </button>
          <button class="btn-action" onclick="sendPrompt('diagram')">
            <span class="material-symbols-outlined" style="font-size: 15px;">palette</span> Synthesize Diagram
          </button>
          <button class="btn-action" onclick="sendPrompt('search')">
            <span class="material-symbols-outlined" style="font-size: 15px;">search</span> Insert Slide
          </button>
          <button class="btn-action" onclick="openSlidesInNewTab()">
            <span class="material-symbols-outlined" style="font-size: 15px;">slideshow</span> Edit in Google Slides
          </button>
        </div>
      </div>
    </div>
  </div>

  <script>
    let activeLdap = 'seller_user';
    let currentDeckId = '';
    let currentCanvasDeckUrl = '';
    let currentCanvasIframeUrl = '';

    function setTargetDeck() {
      const inputEl = document.getElementById('target-deck-input');
      const val = (inputEl ? inputEl.value : '').trim();
      if (!val) return;
      let presId = val;
      const match = val.match(/\/presentation\/d\/([a-zA-Z0-9_-]+)/);
      if (match) {
        presId = match[1];
      }
      currentDeckId = presId;
      currentCanvasDeckUrl = `https://docs.google.com/presentation/d/${presId}/edit`;
      currentCanvasIframeUrl = `https://docs.google.com/presentation/d/${presId}/embed?start=false&loop=false&delayms=3000`;
      openCanvasPanel(currentCanvasIframeUrl, `Active Deck: ${presId}`, currentCanvasDeckUrl);
      appendBotMessage(`🎯 Target deck loaded to Canvas: <strong><a href="${currentCanvasDeckUrl}" target="_blank">${presId}</a></strong>. Slide tools and text transformations now target this presentation.`);
    }

    function openCanvasPanel(iframeUrl, title, workspaceUri) {
      const panel = document.getElementById('canvas-panel');
      const iframe = document.getElementById('canvas-iframe');
      const titleEl = document.getElementById('canvas-title');
      const openTabEl = document.getElementById('canvas-open-tab');
      const userLdapEl = document.getElementById('canvas-user-ldap');

      if (iframeUrl) currentCanvasIframeUrl = iframeUrl;
      if (workspaceUri) currentCanvasDeckUrl = workspaceUri;

      if (iframe && iframe.src !== currentCanvasIframeUrl) {
        iframe.src = currentCanvasIframeUrl;
      }
      if (titleEl && title) {
        titleEl.textContent = title;
      }
      if (openTabEl) {
        openTabEl.href = currentCanvasDeckUrl;
      }
      if (userLdapEl) {
        userLdapEl.textContent = activeLdap;
      }

      if (panel) {
        panel.classList.add('open');
      }
    }

    function closeCanvasPanel() {
      const panel = document.getElementById('canvas-panel');
      if (panel) {
        panel.classList.remove('open');
        panel.classList.remove('expanded');
      }
    }

    function toggleCanvasExpand() {
      const panel = document.getElementById('canvas-panel');
      if (!panel) return;
      panel.classList.toggle('expanded');
      const btn = document.getElementById('canvas-size-toggle');
      if (btn) {
        if (panel.classList.contains('expanded')) {
          btn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 16px;">fullscreen_exit</span>';
        } else {
          btn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 16px;">fullscreen</span>';
        }
      }
    }

    function reloadCanvas() {
      const iframe = document.getElementById('canvas-iframe');
      if (iframe) {
        iframe.src = currentCanvasIframeUrl;
      }
    }

    function openSlidesInNewTab() {
      if (currentCanvasDeckUrl) {
        window.open(currentCanvasDeckUrl, '_blank');
      }
    }

    async function testIdentity() {
      const token = document.getElementById('oauth-token-input').value.trim();
      try {
        const res = await fetch('/api/test/identity', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({access_token: token, fallback_ldap: activeLdap})
        });
        const data = await res.json();
        if (data.user_ldap) {
          activeLdap = data.user_ldap;
          document.getElementById('active-ldap').innerText = activeLdap;
          appendBotMessage(`Identity Synced: User <strong>${data.user_ldap}</strong> (${data.user_email || 'No email'})`);
        }
      } catch (err) {
        appendBotMessage('Identity error: ' + err.message);
      }
    }

    async function sendPrompt(promptText) {
      document.getElementById('user-input').value = promptText;
      sendMessage();
    }

    async function sendMessage(overrideText = null, actionParams = null) {
      const inputEl = document.getElementById('user-input');
      const text = (overrideText || inputEl.value).trim();
      if (!text) return;
      if (!overrideText) inputEl.value = '';

      appendUserMessage(text);

      const effectiveParams = Object.assign({
        presentation_id: currentDeckId,
        target_presentation_id: currentDeckId,
        deck_url: currentCanvasDeckUrl,
      }, actionParams || {});

      try {
        const res = await fetch('/a2a/v1/tasks/send', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            jsonrpc: '2.0',
            id: String(Date.now()),
            params: {
              prompt: text,
              userAction: { parameters: effectiveParams, name: text }
            }
          })
        });
        const json = await res.json();
        if (json.result && json.result.message) {
          renderA2AParts(json.result.message.parts);
        }
      } catch (e) {
        appendBotMessage('Network error: ' + e.message);
      }
    }

    function appendUserMessage(text) {
      const container = document.getElementById('chat-stream');
      const row = document.createElement('div');
      row.className = 'msg-row user';
      row.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
      container.appendChild(row);
      container.scrollTop = container.scrollHeight;
    }

    function appendBotMessage(text) {
      const container = document.getElementById('chat-stream');
      const row = document.createElement('div');
      row.className = 'msg-row bot';
      row.innerHTML = `<div class="bubble">${text}</div>`;
      container.appendChild(row);
      container.scrollTop = container.scrollHeight;
    }

    function renderA2AParts(parts) {
      const container = document.getElementById('chat-stream');
      const row = document.createElement('div');
      row.className = 'msg-row bot';

      let innerHtml = '';
      const v09Messages = [];
      for (const part of parts) {
        if (part.kind === 'text' && part.text) {
          innerHtml += `<div class="bubble">${escapeHtml(part.text).replace(/\\n/g, '<br>')}</div>`;
        } else if (part.kind === 'data' && part.metadata?.mimeType === 'application/json+a2ui') {
          if (part.data && part.data.version === 'v0.9') {
            v09Messages.push(part.data);
          } else {
            innerHtml += renderA2UICard(part.data);
          }
        }
      }
      if (v09Messages.length > 0) {
        innerHtml += renderA2UIV09Surface(v09Messages);
      }

      row.innerHTML = innerHtml;
      container.appendChild(row);
      container.scrollTop = container.scrollHeight;
    }

    function resolveDataModelPath(dataModel, pathStr) {
      if (!pathStr || typeof pathStr !== 'string') return '';
      const segments = pathStr.replace(/^\/+/, '').split('/');
      let cur = dataModel;
      for (const seg of segments) {
        if (cur && typeof cur === 'object' && seg in cur) {
          cur = cur[seg];
        } else {
          return '';
        }
      }
      return (cur !== undefined && cur !== null) ? String(cur) : '';
    }

    function renderA2UIV09Surface(messages) {
      const compMap = {};
      let dataModel = {};
      let rootId = 'root';
      for (const m of messages) {
        if (m.updateComponents && Array.isArray(m.updateComponents.components)) {
          for (const c of m.updateComponents.components) {
            compMap[c.id] = c;
          }
        }
        if (m.updateDataModel && m.updateDataModel.value && typeof m.updateDataModel.value === 'object') {
          dataModel = Object.assign(dataModel, m.updateDataModel.value);
        }
      }
      if (!compMap[rootId]) return '';

      function resolveTextVal(txtProp) {
        if (typeof txtProp === 'string') return txtProp;
        if (txtProp && typeof txtProp === 'object') {
          if (txtProp.path) return resolveDataModelPath(dataModel, txtProp.path);
          if (txtProp.literalString) return txtProp.literalString;
        }
        return '';
      }

      function renderNode(id) {
        const node = compMap[id];
        if (!node) return '';
        const type = node.component;
        if (type === 'Card') {
          const flexStyle = node.weight ? `flex: ${node.weight};` : '';
          return `<div class="a2ui-card" style="margin-top: 8px; ${flexStyle}">${renderNode(node.child)}</div>`;
        }
        if (type === 'Column') {
          const childrenHtml = (node.children || []).map(cid => renderNode(cid)).join('');
          return `<div style="display: flex; flex-direction: column; gap: 12px; justify-content: ${node.justify === 'spaceBetween' ? 'space-between' : 'flex-start'}; height: 100%;">${childrenHtml}</div>`;
        }
        if (type === 'Row') {
          const childrenHtml = (node.children || []).map(cid => renderNode(cid)).join('');
          const justify = node.justify === 'center' ? 'center' : (node.justify === 'spaceBetween' ? 'space-between' : 'flex-start');
          return `<div style="display: flex; flex-direction: row; align-items: center; justify-content: ${justify}; gap: 14px;">${childrenHtml}</div>`;
        }
        if (type === 'Image') {
          return `<img src="${escapeHtml(node.url || '')}" alt="${escapeHtml(node.description || '')}" style="max-height: 52px; border-radius: 10px;">`;
        }
        if (type === 'Text') {
          const val = escapeHtml(resolveTextVal(node.text));
          if (node.variant === 'h2') return `<div style="font-size: 1.35rem; font-weight: 700; color: #fff;">${val}</div>`;
          if (node.variant === 'h4') return `<div style="font-size: 1.02rem; font-weight: 700; color: #f8fafc;">${val}</div>`;
          if (node.variant === 'caption') return `<div style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.45;">${val}</div>`;
          return `<span>${val}</span>`;
        }
        if (type === 'Divider') {
          return `<hr style="border: none; border-top: 1px solid var(--border); margin: 4px 0;">`;
        }
        if (type === 'Button') {
          const labelHtml = renderNode(node.child);
          const ev = (node.action && node.action.event) ? node.action.event : {};
          const evName = ev.name || 'launch_feature';
          const evCtx = escapeHtml(JSON.stringify(ev.context || {}));
          const cls = node.variant === 'primary' ? 'btn-action primary' : 'btn-action';
          return `<button type="button" class="${cls}" style="width: 100%; justify-content: center;" onclick="sendMessage('${escapeHtml(evName)}', ${evCtx})">${labelHtml}</button>`;
        }
        return '';
      }

      const composerAttr = `data-composer-json="${escapeHtml(JSON.stringify(messages, null, 2))}"`;
      return `<div class="a2ui-card" ${composerAttr} style="background: transparent; border: none; padding: 0;">
        <div style="display: flex; justify-content: flex-end; margin-bottom: -6px;">
          <button type="button" class="btn-action" style="font-size: 0.75rem; padding: 4px 8px; border-radius: 6px;" onclick="copyComposerJson(this)" title="Copy canonical A2UI v0.9 JSON array"><span class="material-symbols-outlined" style="font-size: 14px;">content_copy</span> Copy Composer JSON</button>
        </div>
        ${renderNode(rootId)}
      </div>`;
    }

    function renderFormField(f) {
      const fieldId = f.id || '';
      const label = f.label || fieldId;
      const val = (f.value !== undefined && f.value !== null) ? String(f.value) : '';
      const placeholder = f.placeholder || '';
      const isRequired = f.required ? 'required' : '';

      // Check if field has options or is select/dropdown
      if (f.type === 'select' || f.type === 'dropdown' || (Array.isArray(f.options) && f.options.length > 0)) {
        let opts = '';
        for (const opt of f.options) {
          let optVal = '';
          let optLabel = '';
          let isSelected = false;

          if (typeof opt === 'string') {
            optVal = opt;
            optLabel = opt;
            isSelected = (String(opt) === val);
          } else if (typeof opt === 'object' && opt !== null) {
            optVal = opt.value !== undefined ? opt.value : (opt.id || opt.label || '');
            optLabel = opt.label || opt.name || optVal;
            isSelected = (opt.selected === true || String(optVal) === val);
          }
          opts += `<option value="${escapeHtml(optVal)}" ${isSelected ? 'selected' : ''}>${escapeHtml(optLabel)}</option>`;
        }
        return `
          <div class="a2ui-field">
            <label for="${escapeHtml(fieldId)}">${escapeHtml(label)}</label>
            <select id="${escapeHtml(fieldId)}" name="${escapeHtml(fieldId)}" data-field-id="${escapeHtml(fieldId)}" class="a2ui-input" ${isRequired}>
              ${opts}
            </select>
          </div>
        `;
      } else if (f.type === 'textarea') {
        return `
          <div class="a2ui-field full-width">
            <label for="${escapeHtml(fieldId)}">${escapeHtml(label)}</label>
            <textarea id="${escapeHtml(fieldId)}" name="${escapeHtml(fieldId)}" data-field-id="${escapeHtml(fieldId)}" class="a2ui-input" rows="3" placeholder="${escapeHtml(placeholder)}" ${isRequired}>${escapeHtml(val)}</textarea>
          </div>
        `;
      } else if (f.type === 'number') {
        return `
          <div class="a2ui-field">
            <label for="${escapeHtml(fieldId)}">${escapeHtml(label)}</label>
            <input type="number" id="${escapeHtml(fieldId)}" name="${escapeHtml(fieldId)}" data-field-id="${escapeHtml(fieldId)}" class="a2ui-input" value="${escapeHtml(val)}" min="${f.min || 1}" ${isRequired}>
          </div>
        `;
      } else {
        return `
          <div class="a2ui-field">
            <label for="${escapeHtml(fieldId)}">${escapeHtml(label)}</label>
            <input type="text" id="${escapeHtml(fieldId)}" name="${escapeHtml(fieldId)}" data-field-id="${escapeHtml(fieldId)}" class="a2ui-input" value="${escapeHtml(val)}" placeholder="${escapeHtml(placeholder)}" ${isRequired}>
          </div>
        `;
      }
    }

    function submitCardAction(cardFormId, actionName, baseParams) {
      const collected = Object.assign({}, baseParams || {});
      const formEl = document.getElementById(cardFormId);
      if (formEl) {
        // Collect standard form inputs
        const inputs = formEl.querySelectorAll('.a2ui-input');
        inputs.forEach(el => {
          const fid = el.getAttribute('data-field-id') || el.name || el.id;
          if (fid) collected[fid] = el.value;
        });

        // Collect editable agenda items if present
        const agendaItems = formEl.querySelectorAll('.editable-agenda-item');
        if (agendaItems && agendaItems.length > 0) {
          const scrapedSections = [];
          agendaItems.forEach((itemEl, idx) => {
            const titleInput = itemEl.querySelector('.outline-title-input');
            const countInput = itemEl.querySelector('.outline-count-input');
            const subtopicsInput = itemEl.querySelector('.outline-subtopics-input');
            const title = titleInput ? titleInput.value.trim() : `Section ${idx + 1}`;
            const slideCount = countInput ? parseInt(countInput.value, 10) || 1 : 1;
            const subtopicsRaw = subtopicsInput ? subtopicsInput.value.trim() : '';
            const subtopics = subtopicsRaw ? subtopicsRaw.split(',').map(s => s.trim()).filter(Boolean) : [];
            scrapedSections.push({
              title: title,
              slide_count: slideCount,
              subtopics: subtopics
            });
          });
          collected.agenda_sections = scrapedSections;
        }

        // Collect deck strategy from outline dropdown if present
        const strategySelect = formEl.querySelector('[name="deck_strategy"]') || document.getElementById('strategy-select-' + cardFormId);
        if (strategySelect && strategySelect.value) {
          collected.deck_strategy = strategySelect.value;
        }

        // Collect refinement prompt if present
        const refineInput = document.getElementById('refine-input-' + cardFormId);
        if (refineInput && refineInput.value.trim()) {
          collected.refine_prompt = refineInput.value.trim();
        }

        // Auto-load deck to Canvas if presentation URL or ID submitted
        if (collected.presentation_url || collected.presentation_id) {
          const rawUrl = (collected.presentation_url || collected.presentation_id).trim();
          let presId = rawUrl;
          const match = rawUrl.match(/\/presentation\/d\/([a-zA-Z0-9_-]+)/);
          if (match) {
            presId = match[1];
          }
          if (presId) {
            currentDeckId = presId;
            currentCanvasDeckUrl = `https://docs.google.com/presentation/d/${presId}/edit`;
            currentCanvasIframeUrl = `https://docs.google.com/presentation/d/${presId}/embed?start=false&loop=false&delayms=3000`;
            const targetInp = document.getElementById('target-deck-input');
            if (targetInp) targetInp.value = currentCanvasDeckUrl;
            openCanvasPanel(currentCanvasIframeUrl, `Active Deck: ${presId}`, currentCanvasDeckUrl);
            collected.presentation_id = presId;
            collected.target_presentation_id = presId;
            collected.deck_url = currentCanvasDeckUrl;
          }
        }
      }
      sendMessage(actionName, collected);
    }

    function updateOutlineStrategy(selectEl, cardFormId) {
      const cardEl = document.getElementById(cardFormId);
      if (!cardEl) return;
      const subtitleEl = cardEl.querySelector('.a2ui-card-subtitle');
      if (subtitleEl) {
        const text = selectEl.options[selectEl.selectedIndex]?.text || selectEl.value;
        subtitleEl.textContent = 'Active Strategy: ' + text;
      }
    }

    function deleteOutlineSection(btn) {
      const item = btn.closest('.editable-agenda-item');
      if (!item) return;
      const list = item.closest('.a2ui-agenda-list');
      item.remove();
      if (list) renumberOutlineSections(list);
    }

    function renumberOutlineSections(list) {
      const items = list.querySelectorAll('.editable-agenda-item');
      items.forEach((item, idx) => {
        const badge = item.querySelector('.outline-idx-badge');
        if (badge) badge.textContent = '#' + (idx + 1);
      });
    }

    function addOutlineSection(listId) {
      const list = document.getElementById(listId);
      if (!list) return;
      const count = list.querySelectorAll('.editable-agenda-item').length;
      const nextIdx = count + 1;
      const div = document.createElement('div');
      div.className = 'editable-agenda-item';
      div.innerHTML = `
        <div class="agenda-item-header">
          <span class="outline-idx-badge">#${nextIdx}</span>
          <input type="text" class="outline-title-input" value="Custom Solution Section ${nextIdx}" placeholder="Section Title">
          <div class="outline-count-wrapper">
            <input type="number" min="1" max="10" class="outline-count-input" value="1">
            <span>Slides</span>
          </div>
          <button type="button" class="btn-icon-danger" title="Remove section" onclick="deleteOutlineSection(this)">
            <span class="material-symbols-outlined" style="font-size: 18px;">delete</span>
          </button>
        </div>
        <input type="text" class="outline-subtopics-input" value="" placeholder="Topics / Talking Points (comma-separated)">
      `;
      list.appendChild(div);
      renumberOutlineSections(list);
      const titleInp = div.querySelector('.outline-title-input');
      if (titleInp) titleInp.focus();
    }

    function submitOutlineRefinement(cardFormId, customerName) {
      const input = document.getElementById('refine-input-' + cardFormId);
      const prompt = input ? input.value.trim() : '';
      if (!prompt) return;
      const stratSelect = document.getElementById('strategy-select-' + cardFormId);
      const currentStrat = stratSelect ? stratSelect.value : 'smart_hybrid';
      submitCardAction(cardFormId, 'refine_outline', {
        customer_name: customerName,
        deck_strategy: currentStrat,
        refine_prompt: prompt
      });
    }

    function applyOutlinePreset(cardFormId, presetText, customerName) {
      const input = document.getElementById('refine-input-' + cardFormId);
      if (input) input.value = presetText;
      const stratSelect = document.getElementById('strategy-select-' + cardFormId);
      const currentStrat = stratSelect ? stratSelect.value : 'smart_hybrid';
      submitCardAction(cardFormId, 'refine_outline', {
        customer_name: customerName,
        deck_strategy: currentStrat,
        refine_prompt: presetText
      });
    }

    function renderA2UIMessageArray(messages) {
      if (Array.isArray(messages) && messages.some(m => m && m.version === 'v0.9')) {
        return renderA2UIV09Surface(messages);
      }
      let html = '';
      for (const msg of messages) {
        if (msg.deleteSurface) {
          closeCanvasPanel();
          html += `<div class="a2ui-info-banner" style="margin-top: 8px;"><span class="material-symbols-outlined" style="font-size: 18px; color: #94a3b8;">close</span><div>Canvas closed (${escapeHtml(msg.deleteSurface.surfaceId || '')})</div></div>`;
        }
        if (msg.surfaceUpdate && Array.isArray(msg.surfaceUpdate.components)) {
          for (const comp of msg.surfaceUpdate.components) {
            if (comp.component && comp.component.WebFrameUrl) {
              const wf = comp.component.WebFrameUrl;
              const url = (wf.url && wf.url.literalString) ? wf.url.literalString : '';
              const title = wf.cardTitle || 'Interactive Presentation';
              const icon = wf.cardIcon || 'slideshow';
              const desc = wf.cardDescription || 'Interactive Google Slides Canvas';
              const autoOpen = (wf.autoOpen !== false);

              if (url) {
                const match = url.match(/\/presentation\/d\/([a-zA-Z0-9_-]+)/);
                if (match) {
                  currentDeckId = match[1];
                  currentCanvasDeckUrl = `https://docs.google.com/presentation/d/${currentDeckId}/edit`;
                  currentCanvasIframeUrl = url;
                  const targetInp = document.getElementById('target-deck-input');
                  if (targetInp) targetInp.value = currentCanvasDeckUrl;
                }
                if (autoOpen) {
                  setTimeout(() => {
                    openCanvasPanel(url, title, currentCanvasDeckUrl || url);
                  }, 150);
                }
                html += `
                  <div class="a2ui-card" style="margin-top: 8px;">
                    <div class="a2ui-card-title">${escapeHtml(title)}</div>
                    <div class="a2ui-card-subtitle">${escapeHtml(desc)}</div>
                    <div class="a2ui-canvas-indicator" onclick="openCanvasPanel('${escapeHtml(url)}', '${escapeHtml(title)}', '${escapeHtml(currentCanvasDeckUrl || url)}')">
                      <span class="material-symbols-outlined" style="color: #f59e0b; font-size: 26px;">${escapeHtml(icon)}</span>
                      <div style="flex: 1;">
                        <strong style="color: #fbbf24;">${escapeHtml(title)} &rarr;</strong>
                        <div style="font-size: 0.8rem; color: #94a3b8;">${escapeHtml(desc)}</div>
                      </div>
                      <button class="btn-action primary" style="font-size: 0.8rem; padding: 6px 12px;" onclick="event.stopPropagation(); openCanvasPanel('${escapeHtml(url)}', '${escapeHtml(title)}', '${escapeHtml(currentCanvasDeckUrl || url)}')">
                        <span class="material-symbols-outlined" style="font-size: 16px;">open_in_new</span> Open Canvas Panel
                      </button>
                    </div>
                  </div>
                `;
              }
            }
          }
        }
      }
      return html;
    }

    function renderA2UICard(card) {
      if (!card) return '';
      if (Array.isArray(card)) {
        return renderA2UIMessageArray(card);
      }
      const title = card.title || 'PitchGen Card';
      const subtitle = card.subtitle || '';
      const cardFormId = 'card-form-' + Math.random().toString(36).substring(2, 9);

      let contentHtml = '';

      // Canvas preview: Showcase new deck in dedicated Canvas side panel
      if (card.canvasPreview && card.canvasPreview.iframeUrl) {
        const previewUrl = card.canvasPreview.iframeUrl;
        const deckUrl = card.canvasPreview.workspaceUri || currentCanvasDeckUrl;
        const cardTitle = card.title || 'Presentation Deck Preview';

        if (card.canvasPreview.workspaceUri) {
          const match = card.canvasPreview.workspaceUri.match(/\/presentation\/d\/([a-zA-Z0-9_-]+)/);
          if (match) {
            currentDeckId = match[1];
            currentCanvasDeckUrl = card.canvasPreview.workspaceUri;
            currentCanvasIframeUrl = previewUrl;
            const targetInp = document.getElementById('target-deck-input');
            if (targetInp) targetInp.value = currentCanvasDeckUrl;
          }
        } else if (card.presentation_id) {
          currentDeckId = card.presentation_id;
        }

        contentHtml += `
          <div class="a2ui-canvas-indicator" onclick="openCanvasPanel('${escapeHtml(previewUrl)}', '${escapeHtml(cardTitle)}', '${escapeHtml(deckUrl)}')">
            <span class="material-symbols-outlined" style="color: #f59e0b; font-size: 26px;">co_present</span>
            <div style="flex: 1;">
              <strong style="color: #fbbf24;">Interactive Presentation Active in Canvas Panel &rarr;</strong>
              <div style="font-size: 0.8rem; color: #94a3b8;">Presentation rendered in Google Slides canvas with live editor controls</div>
            </div>
            <button class="btn-action primary" style="font-size: 0.8rem; padding: 6px 12px;" onclick="event.stopPropagation(); openCanvasPanel('${escapeHtml(previewUrl)}', '${escapeHtml(cardTitle)}', '${escapeHtml(deckUrl)}')">
              <span class="material-symbols-outlined" style="font-size: 16px;">open_in_new</span> Open Canvas Panel
            </button>
          </div>
        `;

        // Automatically open the Canvas side panel to showcase the new deck
        setTimeout(() => {
          openCanvasPanel(previewUrl, cardTitle, deckUrl);
        }, 150);
      }

      // Sections
      const hasStepper = card.sections && card.sections.some(s => s.type === 'stepper');
      if (card.sections) {
        for (const sec of card.sections) {
          if (sec.type === 'stepper' && Array.isArray(sec.steps)) {
            const stepperId = 'stepper-' + Math.random().toString(36).substring(2, 9);
            const totalSteps = sec.steps.length;
            contentHtml += `<div class="a2ui-stepper" id="${stepperId}">`;

            // Tab headers
            contentHtml += `<div class="stepper-header">`;
            sec.steps.forEach((step, idx) => {
              const activeCls = (idx === 0) ? 'active' : '';
              contentHtml += `
                <button type="button" class="stepper-tab ${activeCls}" data-step-index="${idx}" onclick="switchStepperStep('${cardFormId}', '${stepperId}', ${idx})">
                  <span class="stepper-tab-badge">${idx + 1}</span>
                  <span>${escapeHtml(step.title || 'Step ' + (idx + 1))}</span>
                </button>
              `;
            });
            contentHtml += `</div>`;

            // Step bodies
            contentHtml += `<form class="stepper-body" onsubmit="return false;">`;
            sec.steps.forEach((step, idx) => {
              const activeCls = (idx === 0) ? 'active' : '';
              contentHtml += `<div class="stepper-step ${activeCls}" data-step-content="${idx}">`;
              if (step.subtitle) {
                contentHtml += `<div class="stepper-step-desc">${escapeHtml(step.subtitle)}</div>`;
              }
              contentHtml += `<div class="a2ui-form-grid">`;
              if (Array.isArray(step.fields)) {
                for (const f of step.fields) {
                  contentHtml += renderFormField(f);
                }
              }
              contentHtml += `</div>`;

              // Stepper navigation bar
              contentHtml += `<div class="stepper-nav-bar">`;
              if (idx > 0) {
                contentHtml += `
                  <button type="button" class="btn-action" onclick="switchStepperStep('${cardFormId}', '${stepperId}', ${idx - 1})">
                    <span class="material-symbols-outlined" style="font-size: 16px;">arrow_back</span> Back
                  </button>
                `;
              } else {
                contentHtml += `<div></div>`;
              }

              contentHtml += `<div style="display: flex; align-items: center; gap: 8px;">`;
              if (Array.isArray(step.actions)) {
                for (const act of step.actions) {
                  const baseParams = escapeHtml(JSON.stringify(act.action?.parameters || {}));
                  contentHtml += `
                    <button type="button" class="btn-action ${act.style || 'primary'}" onclick="submitCardAction('${cardFormId}', '${escapeHtml(act.action?.actionName || act.id)}', ${baseParams})">
                      ${escapeHtml(act.label)}
                    </button>
                  `;
                }
              }
              if (idx < totalSteps - 1) {
                const nextStepTitle = sec.steps[idx + 1].title || ('Step ' + (idx + 2));
                contentHtml += `
                  <button type="button" class="btn-action primary" onclick="switchStepperStep('${cardFormId}', '${stepperId}', ${idx + 1})">
                    Next: ${escapeHtml(nextStepTitle)} <span class="material-symbols-outlined" style="font-size: 16px;">arrow_forward</span>
                  </button>
                `;
              }
              contentHtml += `</div>`;
              contentHtml += `</div>`;
              contentHtml += `</div>`;
            });
            contentHtml += `</form>`;
            contentHtml += `</div>`;
          } else if (hasStepper && (sec.type === 'form' || sec.type === 'actions')) {
            // Suppress redundant flat form and actions when stepper wizard is active
            continue;
          } else if (sec.type === 'info_banner' && sec.text) {
            contentHtml += `
              <div class="a2ui-info-banner">
                <span class="material-symbols-outlined" style="font-size: 18px; color: #60a5fa; flex-shrink: 0;">shield</span>
                <div>${escapeHtml(sec.text)}</div>
              </div>
            `;
          } else if (sec.type === 'text' && sec.content) {
            contentHtml += `<div style="font-size: 0.9rem; line-height: 1.4;">${escapeHtml(sec.content)}</div>`;
          } else if (sec.type === 'form' && sec.fields) {
            contentHtml += `<form class="a2ui-form-grid" onsubmit="return false;">`;
            for (const f of sec.fields) {
              contentHtml += renderFormField(f);
            }
            contentHtml += '</form>';
          } else if (sec.type === 'agenda_list' && sec.items) {
            const listContainerId = 'agenda-list-' + Math.random().toString(36).substring(2, 9);
            const customerName = sec.customer_name || 'Target';
            const currentStrat = sec.deck_strategy || 'smart_hybrid';
            const strategies = sec.available_strategies || [
              {id: 'smart_hybrid', label: '⚡ Smart Hybrid (CloudHub + Bespoke Anchors)'},
              {id: 'cloudhub', label: '📁 CloudHub Focused (100% Brand-Vetted Slides)'},
              {id: 'bespoke_custom', label: '✨ Bespoke Custom (100% Tailored Layouts)'}
            ];
            const presets = sec.refinement_presets || [
              '+ Security & Zero Trust',
              '+ 3.2x ROI Proof Points',
              'Focus C-Level Vision',
              'Shorten to 4 Slides',
              'Technical Architecture Deep Dive'
            ];

            // In-place Deck Strategy dropdown (does not open new cards or elements)
            contentHtml += `
              <div class="outline-strategy-bar">
                <label for="strategy-select-${cardFormId}" class="outline-strategy-label">
                  <span class="material-symbols-outlined" style="font-size: 17px; color: #60a5fa;">tune</span>
                  Deck Strategy:
                </label>
                <select id="strategy-select-${cardFormId}" name="deck_strategy" data-field-id="deck_strategy" class="a2ui-input outline-strategy-select" onchange="updateOutlineStrategy(this, '${cardFormId}')">
            `;
            for (const strat of strategies) {
              const val = strat.id || strat.value;
              const sel = (val === currentStrat) ? 'selected' : '';
              contentHtml += `<option value="${escapeHtml(val)}" ${sel}>${escapeHtml(strat.label)}</option>`;
            }
            contentHtml += `
                </select>
              </div>
            `;

            contentHtml += `<div id="${listContainerId}" class="a2ui-agenda-list">`;
            sec.items.forEach((it, idx) => {
              const subtopicsStr = Array.isArray(it.subtopics)
                  ? it.subtopics.join(', ')
                  : (it.subtopics ? String(it.subtopics) : '');
              const slideCount = it.slide_count || 1;
              contentHtml += `
                <div class="editable-agenda-item">
                  <div class="agenda-item-header">
                    <span class="outline-idx-badge">#${idx + 1}</span>
                    <input type="text" class="outline-title-input" value="${escapeHtml(it.title || '')}" placeholder="Section Title">
                    <div class="outline-count-wrapper">
                      <input type="number" min="1" max="10" class="outline-count-input" value="${slideCount}">
                      <span>Slides</span>
                    </div>
                    <button type="button" class="btn-icon-danger" title="Remove section" onclick="deleteOutlineSection(this)">
                      <span class="material-symbols-outlined" style="font-size: 18px;">delete</span>
                    </button>
                  </div>
                  <input type="text" class="outline-subtopics-input" value="${escapeHtml(subtopicsStr)}" placeholder="Topics / Talking Points (comma-separated)">
                </div>
              `;
            });
            contentHtml += '</div>';

            // Add Section button
            contentHtml += `
              <div style="margin-top: 10px;">
                <button type="button" class="btn-add-section" onclick="addOutlineSection('${listContainerId}')">
                  <span class="material-symbols-outlined" style="font-size: 18px;">add_circle</span> Add Slide Section
                </button>
              </div>
            `;

            // Natural language refinement box with chips
            contentHtml += `
              <div class="outline-refine-box">
                <div class="outline-refine-box-title">
                  <span class="material-symbols-outlined" style="font-size: 16px; color: #60a5fa;">psychology</span>
                  Refine with Gemini Prompt
                </div>
                <div class="outline-refine-input-row">
                  <input type="text" id="refine-input-${cardFormId}" class="outline-refine-input" placeholder="e.g. Add 2 slides on Cloud Security & Zero Trust, emphasize retail ROI" onkeydown="if(event.key==='Enter'){submitOutlineRefinement('${cardFormId}', '${escapeHtml(customerName)}');}">
                  <button type="button" class="btn-action primary" style="padding: 6px 12px; font-size: 0.8rem;" onclick="submitOutlineRefinement('${cardFormId}', '${escapeHtml(customerName)}')">
                    <span class="material-symbols-outlined" style="font-size: 15px;">auto_awesome</span> Refine
                  </button>
                </div>
                <div class="chip-presets">
            `;
            for (const p of presets) {
              contentHtml += `<button type="button" class="chip-preset" onclick="applyOutlinePreset('${cardFormId}', '${escapeHtml(p)}', '${escapeHtml(customerName)}')">${escapeHtml(p)}</button>`;
            }
            contentHtml += `
                </div>
              </div>
            `;
          } else if ((sec.type === 'tile_grid' || sec.type === 'slide_grid') && (sec.items || sec.tiles)) {
            const tiles = sec.items || sec.tiles;
            contentHtml += '<div class="a2ui-tile-grid">';
            for (const it of tiles) {
              const insertAction = (it.actions && it.actions[0]) || null;
              const actionParams = insertAction ? escapeHtml(JSON.stringify(insertAction.action?.parameters || {})) : '{}';
              contentHtml += `
                <div class="a2ui-slide-tile">
                  ${it.thumbnail_url ? `<img src="${escapeHtml(it.thumbnail_url)}" class="a2ui-tile-thumb" onerror="this.style.display='none'">` : ''}
                  <div class="a2ui-tile-content">
                    <div class="a2ui-tile-title">${escapeHtml(it.title || '')}</div>
                    <div class="a2ui-tile-meta">
                      <span class="badge">${escapeHtml(it.slide_job || it.category || 'Vetted')}</span>
                      <span style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(it.source || '')}</span>
                    </div>
                    ${it.summary ? `<div style="font-size: 0.8rem; color: var(--text-muted);">${escapeHtml(it.summary)}</div>` : ''}
                    ${insertAction ? `
                      <div style="margin-top: 6px;">
                        <button class="btn-action primary" style="width: 100%; justify-content: center;" onclick="sendMessage('${escapeHtml(insertAction.action?.actionName || insertAction.id)}', ${actionParams})">${escapeHtml(insertAction.label || 'Insert Slide')}</button>
                      </div>
                    ` : ''}
                  </div>
                </div>
              `;
            }
            contentHtml += '</div>';
          } else if (sec.type === 'actions' && sec.buttons) {
            if (sec.title) {
              contentHtml += `<div style="font-size: 0.8rem; color: var(--text-muted); font-weight: 700; margin-bottom: 6px; margin-top: 12px;">${escapeHtml(sec.title)}</div>`;
            }
            contentHtml += '<div class="a2ui-actions-row">';
            for (const btn of sec.buttons) {
              if (btn.url) {
                contentHtml += `<a href="${escapeHtml(btn.url)}" target="_blank" class="btn-action ${btn.style || ''}">${escapeHtml(btn.label)}</a>`;
              } else if (btn.action?.actionName === 'open_canvas_panel') {
                const previewUrl = btn.action.parameters?.embed_url || currentCanvasIframeUrl;
                const deckUrl = btn.action.parameters?.deck_url || currentCanvasDeckUrl;
                contentHtml += `<button class="btn-action ${btn.style || ''}" onclick="openCanvasPanel('${escapeHtml(previewUrl)}', '${escapeHtml(title)}', '${escapeHtml(deckUrl)}')">${escapeHtml(btn.label)}</button>`;
              } else {
                const actName = btn.action?.actionName || btn.label;
                const baseParams = escapeHtml(JSON.stringify(btn.action?.parameters || {}));
                contentHtml += `<button class="btn-action ${btn.style || ''}" onclick="submitCardAction('${cardFormId}', '${escapeHtml(actName)}', ${baseParams})">${escapeHtml(btn.label)}</button>`;
              }
            }
            contentHtml += '</div>';
          } else if (sec.type === 'quick_actions' && sec.actions) {
            contentHtml += `
              <div style="margin-top: 12px; margin-bottom: 6px;">
                <div style="font-size: 0.85rem; color: var(--primary); font-weight: 700; margin-bottom: 4px;">${escapeHtml(sec.title || 'Quick Actions')}</div>
                ${sec.description ? `<div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 8px;">${escapeHtml(sec.description)}</div>` : ''}
                <div class="a2ui-actions-row">
            `;
            for (const act of sec.actions) {
              const baseParams = escapeHtml(JSON.stringify(act.action?.parameters || {}));
              contentHtml += `<button class="btn-action ${act.style || ''}" onclick="sendMessage('${escapeHtml(act.action?.actionName || act.id)}', ${baseParams})">${escapeHtml(act.label)}</button>`;
            }
            contentHtml += '</div></div>';
          }
        }
      }

      const v09Json = (card.a2ui_v09_messages || card.canvasMessages || null);
      const composerAttr = v09Json ? `data-composer-json="${escapeHtml(JSON.stringify(v09Json, null, 2))}"` : '';
      const copyBtn = v09Json ? `<button type="button" class="btn-action" style="font-size: 0.75rem; padding: 4px 8px; border-radius: 6px; margin-left: auto;" onclick="copyComposerJson(this)" title="Copy canonical A2UI v0.9 JSON array for A2UI Composer"><span class="material-symbols-outlined" style="font-size: 14px;">content_copy</span> Copy Composer JSON</button>` : '';

      return `
        <div class="a2ui-card" id="${cardFormId}" ${composerAttr}>
          <div class="a2ui-card-title" style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
            <div style="display: flex; align-items: center; gap: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
              <span class="material-symbols-outlined" style="color: #60a5fa; flex-shrink: 0;">auto_awesome</span>
              <span>${escapeHtml(title)}</span>
            </div>
            ${copyBtn}
          </div>
          ${subtitle ? `<div class="a2ui-card-subtitle">${escapeHtml(subtitle)}</div>` : ''}
          ${contentHtml}
        </div>
      `;
    }

    function copyComposerJson(btn) {
      const card = btn.closest('.a2ui-card');
      if (!card) return;
      const raw = card.getAttribute('data-composer-json');
      if (!raw) return;
      navigator.clipboard.writeText(raw).then(() => {
        const orig = btn.innerHTML;
        btn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 14px; color: #10b981;">check</span> Copied!';
        btn.style.borderColor = '#10b981';
        btn.style.color = '#10b981';
        setTimeout(() => {
          btn.innerHTML = orig;
          btn.style.borderColor = '';
          btn.style.color = '';
        }, 2000);
      }).catch(err => {
        alert('Could not copy automatically: ' + err);
      });
    }

    function switchStepperStep(cardFormId, stepperId, stepIdx) {
      const stepperEl = document.getElementById(stepperId);
      if (!stepperEl) return;
      const tabs = stepperEl.querySelectorAll('.stepper-tab');
      const steps = stepperEl.querySelectorAll('.stepper-step');
      tabs.forEach((tab, i) => {
        if (i === stepIdx) {
          tab.classList.add('active');
        } else {
          tab.classList.remove('active');
        }
      });
      steps.forEach((step, i) => {
        if (i === stepIdx) {
          step.classList.add('active');
        } else {
          step.classList.remove('active');
        }
      });
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    document.getElementById('user-input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') sendMessage();
    });

    // Auto-load welcome intro message on initial render
    window.addEventListener('DOMContentLoaded', () => {
      sendPrompt('intro');
    });
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def local_a2ui_tester() -> str:
  """Renders the local visual test harness single-page application."""
  return HTML_TESTER


if __name__ == "__main__":
  import argparse  # pylint: disable=g-import-not-at-top
  import threading  # pylint: disable=g-import-not-at-top
  import uvicorn  # pylint: disable=g-import-not-at-top

  parser = argparse.ArgumentParser(description="PitchGen A2UI Test Server")
  parser.add_argument(
      "--port",
      type=int,
      default=int(os.environ.get("PORT", 8000)),
      help="Port to listen on",
  )
  parser.add_argument(
      "--host", type=str, default="0.0.0.0", help="Host to listen on"
  )
  args, _ = parser.parse_known_args()

  primary_port = args.port
  secondary_port = 8080 if primary_port != 8080 else 8000

  def run_secondary():
    try:
      config = uvicorn.Config(
          app, host=args.host, port=secondary_port, log_level="warning"
      )
      server = uvicorn.Server(config)
      server.run()
    except Exception as e:
      logger.warning("Could not bind secondary port %d: %s", secondary_port, e)

  t = threading.Thread(target=run_secondary, daemon=True)
  t.start()

  logger.info(
      "Starting PitchGen A2UI Visual Test Harness on http://%s:%d and"
      " http://%s:%d",
      args.host,
      primary_port,
      args.host,
      secondary_port,
  )
  uvicorn.run(app, host=args.host, port=primary_port)
