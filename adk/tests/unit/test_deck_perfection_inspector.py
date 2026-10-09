"""Unit tests for the Stratified Combinatorial Matrix and 16-Point Deck Perfection Inspector."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any

WORKSPACE_ROOT = Path(os.path.abspath(__file__)).parents[2]
for p in (WORKSPACE_ROOT, WORKSPACE_ROOT / "src"):
  if str(p) not in sys.path:
    sys.path.insert(0, str(p))

from evals.deck_perfection_inspector import DeckPerfectionInspector, DeckTransformationInspector
from evals.e2e_test_matrix import get_test_matrix, verify_matrix_coverage


def _make_text_shape(
    object_id: str,
    text: str,
    *,
    font_pt: float = 14.0,
    x_pt: float = 40.0,
    y_pt: float = 100.0,
    w_pt: float = 300.0,
    h_pt: float = 100.0,
    link_url: str = "",
) -> dict[str, Any]:
  style: dict[str, Any] = {"fontSize": {"magnitude": font_pt, "unit": "PT"}}
  if link_url:
    style["link"] = {"url": link_url}
  return {
      "objectId": object_id,
      "size": {
          "width": {"magnitude": w_pt, "unit": "PT"},
          "height": {"magnitude": h_pt, "unit": "PT"},
      },
      "transform": {
          "scaleX": 1.0,
          "scaleY": 1.0,
          "translateX": x_pt * 12700.0,
          "translateY": y_pt * 12700.0,
          "unit": "EMU",
      },
      "shape": {
          "shapeType": "TEXT_BOX",
          "text": {
              "textElements": [
                  {"textRun": {"content": text, "style": style}},
              ]
          },
      },
  }


def _make_image_element(
    object_id: str,
    *,
    x_pt: float,
    y_pt: float,
    w_pt: float,
    h_pt: float,
) -> dict[str, Any]:
  return {
      "objectId": object_id,
      "size": {
          "width": {"magnitude": w_pt, "unit": "PT"},
          "height": {"magnitude": h_pt, "unit": "PT"},
      },
      "transform": {
          "scaleX": 1.0,
          "scaleY": 1.0,
          "translateX": x_pt * 12700.0,
          "translateY": y_pt * 12700.0,
          "unit": "EMU",
      },
      "image": {"contentUrl": f"https://example.com/{object_id}.png"},
  }


def _make_slide(
    slide_id: str,
    elements: list[dict[str, Any]],
    notes_text: str = "",
    notes_link: str = "",
) -> dict[str, Any]:
  notes_el = _make_text_shape(
      f"{slide_id}_notes",
      notes_text,
      font_pt=11.0,
      link_url=notes_link,
  )
  return {
      "objectId": slide_id,
      "pageElements": elements,
      "slideProperties": {
          "notesPage": {
              "notesProperties": {"speakerNotesObjectId": f"{slide_id}_notes"},
              "pageElements": [notes_el],
          }
      },
  }


def _build_perfect_mock_presentation() -> dict[str, Any]:
  cover = _make_slide(
      "cover_1",
      elements=[
          _make_text_shape(
              "cover_title",
              "Agentic Commerce at Uniqlo",
              font_pt=68.0,
              x_pt=38.0,
              y_pt=80.0,
              w_pt=385.0,
              h_pt=180.0,
          ),
          _make_image_element(
              "cover_sculpture", x_pt=360.0, y_pt=0.0, w_pt=360.0, h_pt=405.0
          ),
          _make_image_element(
              "cover_logo", x_pt=618.0, y_pt=24.2, w_pt=72.0, h_pt=36.0
          ),
      ],
      notes_text="Welcome to the executive briefing for Uniqlo.",
  )

  content_slides = []
  topics = [
      (
          "Unified inventory telemetry connects global retail channels",
          "reusable",
          (
              "Uniqlo store associates and digital shoppers experience unified "
              "real-time stock accuracy across 2,400 global retail locations "
              "using BigQuery and Spanner."
          ),
          (
              "RFID shelf sensors stream live garment movement directly into "
              "regional fulfillment hubs, cutting out-of-stock incidents by "
              "forty percent during seasonal peaks."
          ),
          (
              "Automated replenishment pipelines balance inventory between "
              "flagship urban stores and suburban warehouses without manual "
              "merchandising intervention."
          ),
      ),
      (
          "Gemini Enterprise powers conversational product discovery",
          "bespoke",
          (
              "Multimodal styling agents built with Gemini Enterprise"
              " synthesize localized weather, fabric preferences, and live"
              " warehouse availability in milliseconds."
          ),
          (
              "Shoppers upload inspiration photos on mobile to receive curated"
              " LifeWear outfit combinations grounded in verified catalog"
              " metadata and sizing history."
          ),
          (
              "Conversational checkout flows reduce cart abandonment while "
              "preserving Uniqlo brand voice across twenty-five languages and "
              "regional storefronts."
          ),
      ),
      (
          "Real-time demand sensing eliminates supply chain blind spots",
          "reusable",
          (
              "Predictive demand forecasting combines historical point-of-sale "
              "ledgers with macroeconomic signals and regional climate trends "
              "inside BigQuery ML."
          ),
          (
              "Production planners adjust textile mill allocations weeks"
              " earlier, preventing markdown waste on seasonal outerwear and"
              " HeatTech collections."
          ),
          (
              "End-to-end shipment visibility tracks container milestones from"
              " partner factories through customs clearance to store loading"
              " docks in real time."
          ),
      ),
      (
          "Autonomous workflow orchestration accelerates developer velocity",
          "bespoke",
          (
              "Enterprise governance controls enforce strict data residency,"
              " zero-trust access policies, and verifiable grounding across"
              " every regional engineering market."
          ),
          (
              "Engineering squads deploy microservices onto GKE Enterprise with"
              " automated canary rollouts, continuous vulnerability scanning,"
              " and sub-second observability."
          ),
          (
              "Shared agent blueprints allow regional digital teams to launch"
              " localized customer experiences in days rather than"
              " multi-quarter release cycles."
          ),
      ),
  ]
  for idx, (headline, origin, col1_txt, col2_txt, col3_txt) in enumerate(
      topics, start=2
  ):
    if origin == "reusable":
      notes = (
          "Executive takeaway for this reusable strategy slide showing verified"
          " impact.\n🔗 Source Slide: Uniqlo Retail Deck (Slide 4)\n🔗"
          " Transition to next slide: Next we examine architectural execution."
      )
      link = "https://docs.google.com/presentation/d/1AbCdEfGhIjKlMnOpQrStUvWxYz123456/edit#slide=id.p4"
    else:
      notes = (
          "✨ Custom generated slide tailored to Uniqlo omnichannel"
          " architecture.\n🔗 Transition to next slide: Moving from"
          " architecture to governance."
      )
      link = ""

    elements = [
        _make_text_shape(
            f"s{idx}_title",
            headline,
            font_pt=26.0,
            x_pt=36.0,
            y_pt=24.0,
            w_pt=640.0,
            h_pt=40.0,
        ),
        _make_text_shape(
            f"s{idx}_col1",
            col1_txt,
            font_pt=12.0,
            x_pt=36.0,
            y_pt=110.0,
            w_pt=190.0,
            h_pt=210.0,
        ),
        _make_text_shape(
            f"s{idx}_col2",
            col2_txt,
            font_pt=12.0,
            x_pt=250.0,
            y_pt=110.0,
            w_pt=190.0,
            h_pt=210.0,
        ),
        _make_text_shape(
            f"s{idx}_col3",
            col3_txt,
            font_pt=12.0,
            x_pt=464.0,
            y_pt=110.0,
            w_pt=190.0,
            h_pt=210.0,
        ),
    ]
    content_slides.append(_make_slide(f"slide_{idx}", elements, notes, link))

  closing = _make_slide(
      "closing_slide",
      elements=[
          _make_text_shape(
              "closing_text",
              "Thank you",
              font_pt=42.0,
              x_pt=200.0,
              y_pt=150.0,
              w_pt=300.0,
              h_pt=80.0,
          )
      ],
  )

  return {
      "presentationId": "1MockPerfectUniqloPresentationId999999",
      "title": "[PitchGen] Uniqlo | Agentic Commerce (Sep 2026)",
      "slides": [cover, *content_slides, closing],
  }


def test_matrix_tiers_and_combinatorial_coverage() -> None:
  tier1 = get_test_matrix("tier1_smoke")
  assert len(tier1) == 9
  cov1 = verify_matrix_coverage(tier1)
  assert cov1["all_strategy_x_length_covered"] is True
  assert cov1["stages_covered"] == 5

  tier2 = get_test_matrix("tier2_pairwise")
  assert len(tier2) == 36
  cov2 = verify_matrix_coverage(tier2)
  assert cov2["all_19_industries_covered"] is True
  assert cov2["all_strategy_x_length_covered"] is True
  assert cov2["all_strategy_x_track_covered"] is True
  assert cov2["all_solution_x_strategy_covered"] is True

  tier3 = get_test_matrix("tier3_marathon")
  assert len(tier3) == 108
  cov3 = verify_matrix_coverage(tier3)
  assert cov3["all_27_plays_covered"] is True


def test_inspector_passes_perfect_presentation() -> None:
  pres = _build_perfect_mock_presentation()
  inspector = DeckPerfectionInspector()
  report = inspector.inspect_presentation_dict(
      pres,
      customer_name="Uniqlo",
      deck_strategy="smart_hybrid",
      deck_length="Brief (4-6 slides)",
      sales_stage="S1",
  )
  assert report.passed_all_gates is True, [
      (g.gate_id, g.violations) for g in report.gate_results if not g.passed
  ]
  assert report.gates_passed == 16
  assert report.overall_score == 100.0


def test_inspector_catches_cover_and_title_and_density_regressions() -> None:
  pres = _build_perfect_mock_presentation()
  # 1. Regress cover title to 48pt with rigid colon and "Google Cloud for Uniqlo"
  cover_title_el = pres["slides"][0]["pageElements"][0]
  cover_title_el["shape"]["text"]["textElements"][0]["textRun"][
      "content"
  ] = "Agentic Commerce: Google Cloud for Uniqlo"
  cover_title_el["shape"]["text"]["textElements"][0]["textRun"]["style"][
      "fontSize"
  ]["magnitude"] = 48.0

  # 2. Regress bespoke Slide 3 title to bare imperative command + Title Case + <24pt
  bespoke_slide = pres["slides"][2]
  bespoke_slide["pageElements"][0]["shape"]["text"]["textElements"][0][
      "textRun"
  ]["content"] = "Unlock High-Velocity Omnichannel Commerce Now"
  bespoke_slide["pageElements"][0]["shape"]["text"]["textElements"][0][
      "textRun"
  ]["style"]["fontSize"]["magnitude"] = 20.0

  # 3. Regress tall card col1 to sparse 55 chars + forbidden "Vertex AI" naming
  bespoke_slide["pageElements"][1]["shape"]["text"]["textElements"][0][
      "textRun"
  ]["content"] = "Short sparse card using Vertex AI and the GE app."

  inspector = DeckPerfectionInspector()
  report = inspector.inspect_presentation_dict(
      pres,
      customer_name="Uniqlo",
      deck_strategy="smart_hybrid",
      deck_length="Brief (4-6 slides)",
      sales_stage="S1",
  )
  by_id = {g.gate_id: g for g in report.gate_results}
  assert by_id["G04"].passed is False
  assert by_id["G06"].passed is False
  assert by_id["G07"].passed is False
  assert by_id["G15"].passed is False


def test_inspector_catches_cvi_slide_order_and_untransformed_visuals_and_repo_alignment() -> (
    None
):
  pres = _build_perfect_mock_presentation()

  # 1. Regress Slide 2 to be "Let's get started" (stage=80) before Solution slides (stage=40)
  pres["slides"][1]["pageElements"][0]["shape"]["text"]["textElements"][0][
      "textRun"
  ]["content"] = "Let's get started with a joint pilot"

  # 2. Regress Cover Slide sculpture to an untransformed template URL without PitchGen-Transformed altText
  pres["slides"][0]["pageElements"][1]["image"][
      "contentUrl"
  ] = "https://lh3.googleusercontent.com/template_default_circle_ring.png"

  # 3. Regress Reusable Slide 4 speaker notes to lack a valid 20+ char repo deck ID
  pres["slides"][3]["slideProperties"]["notesPage"]["pageElements"][0]["shape"][
      "text"
  ]["textElements"][0]["textRun"]["style"].pop("link", None)

  inspector = DeckPerfectionInspector()
  report = inspector.inspect_presentation_dict(
      pres,
      customer_name="Uniqlo",
      deck_strategy="smart_hybrid",
      deck_length="Brief (4-6 slides)",
      sales_stage="S1",
  )
  by_id = {g.gate_id: g for g in report.gate_results}
  assert by_id["G05"].passed is False
  assert any(
      "Out-of-order CVI slide progression" in v for v in by_id["G05"].violations
  )
  assert any(
      "cover 3D sculpture image was not transformed" in v
      for v in by_id["G05"].violations
  )
  assert by_id["G03"].passed is False
  assert any(
      "lacks a verified repository source presentation ID" in v
      for v in by_id["G03"].violations
  )


def test_empirical_marathon_fixes_logo_cvi_and_gate09() -> None:
  from pitchgen_utils.logo_util import _synthesize_fallback_logo_badge

  # 1. Fallback customer logo badge produces a valid PNG byte stream
  badge_bytes = _synthesize_fallback_logo_badge(
      "NextEra Energy", "nexteraenergy.com"
  )
  assert badge_bytes.startswith(b"\x89PNG\r\n\x1a\n")
  assert len(badge_bytes) > 500

  # 2. Gate 05 uses largest-fontSize shape even when pageElements[0] is a small body/eyebrow shape
  pres = _build_perfect_mock_presentation()
  slide_with_eyebrow_first = _make_slide(
      "slide_cvi_test",
      elements=[
          _make_text_shape(
              "eyebrow_0",
              "Platform capability overview and governance",
              font_pt=11.0,
              x_pt=36.0,
              y_pt=12.0,
              w_pt=300.0,
              h_pt=18.0,
          ),
          _make_text_shape(
              "main_title_1",
              "Let's get started with a 3-step pilot",
              font_pt=28.0,
              x_pt=36.0,
              y_pt=32.0,
              w_pt=600.0,
              h_pt=40.0,
          ),
      ],
  )
  inspector = DeckPerfectionInspector()
  g05_res = inspector._gate_05_cover_logo_and_sculpture(
      pres["slides"][0],
      content_slides=[(2, slide_with_eyebrow_first)],
      customer_name="Uniqlo",
  )
  assert g05_res.details["cvi_stages"][0]["stage"] == 80

  # 3. Gate 09 computes req_h per paragraph using paragraph-level font sizes (14pt header + 9pt body)
  pres = _build_perfect_mock_presentation()
  bespoke_slide = pres["slides"][2]
  multi_para_card = {
      "objectId": "s3_col1_multipara",
      "size": {
          "width": {"magnitude": 140.0 * 12700.0, "unit": "EMU"},
          "height": {"magnitude": 96.0 * 12700.0, "unit": "EMU"},
      },
      "transform": {
          "scaleX": 1.0,
          "scaleY": 1.0,
          "translateX": 36.0 * 12700.0,
          "translateY": 110.0 * 12700.0,
          "unit": "EMU",
      },
      "shape": {
          "shapeType": "TEXT_BOX",
          "text": {
              "textElements": [
                  {
                      "textRun": {
                          "content": "Unified Data Governance\n",
                          "style": {
                              "fontSize": {"magnitude": 14.0, "unit": "PT"},
                              "bold": True,
                          },
                      }
                  },
                  {
                      "textRun": {
                          "content": (
                              "Gemini Enterprise enforces zero-trust IAM"
                              " boundaries and real-time catalog lineage across"
                              " global Uniqlo retail stores and fulfillment"
                              " nodes.\n"
                          ),
                          "style": {
                              "fontSize": {"magnitude": 9.0, "unit": "PT"},
                              "bold": False,
                          },
                      }
                  },
              ]
          },
      },
  }
  bespoke_slide["pageElements"][1] = multi_para_card
  inspector = DeckPerfectionInspector()
  report = inspector.inspect_presentation_dict(
      pres,
      customer_name="Uniqlo",
      deck_strategy="smart_hybrid",
      deck_length="Brief (4-6 slides)",
      sales_stage="S1",
  )
  by_id = {g.gate_id: g for g in report.gate_results}
  assert by_id["G09"].passed is True, by_id["G09"].violations


def test_s0_customer_discovery_mode_and_cvi_context_alignment() -> None:
  """Verifies S0 / Customer-Research & Discovery-Questions mode detection and Context CVI stage 15 alignment."""
  from agents.workflows.outline_workflow import OutlineWorkflow

  assert (
      OutlineWorkflow.is_s0_customer_discovery_mode(
          "S0", "Build a smart hybrid pitch deck for Carrefour."
      )
      is True
  )
  assert (
      OutlineWorkflow.is_s0_customer_discovery_mode(
          "S1",
          "Build a smart hybrid deck that helps drive discovery of an"
          " opportunity with customer research and discovery questions.",
      )
      is True
  )
  assert (
      OutlineWorkflow.is_s0_customer_discovery_mode(
          "S2",
          "Generate a technical architecture deck for Stripe on Agentic Data"
          " Cloud.",
      )
      is False
  )

  # Verify Gate 05 recognizes S0 Customer Research & Strategic Footprint titles as Context stage 15
  pres = _build_perfect_mock_presentation()
  s_context = pres["slides"][2]
  s_context["pageElements"][0]["shape"]["text"]["textElements"][0]["textRun"][
      "content"
  ] = "Aligning with Carrefour 2026 strategic initiatives\n"
  inspector = DeckPerfectionInspector()
  g05_res = inspector._gate_05_cover_logo_and_sculpture(
      pres["slides"][0],
      content_slides=[(3, s_context)],
      customer_name="Carrefour",
  )
  assert g05_res.passed is True, g05_res.violations
  assert g05_res.details["cvi_stages"][0]["stage"] == 15

  # Verify template_sorter_base.txt preserves Customer Research named entities and Discovery Questions (?...)
  sorter_path = (
      WORKSPACE_ROOT / "src" / "prompt_templates" / "template_sorter_base.txt"
  )
  sorter_txt = sorter_path.read_text(encoding="utf-8")
  assert "CUSTOMER RESEARCH & EXECUTIVE DISCOVERY QUESTION" in sorter_txt
  assert "Consultative Discovery Questions (`?...`)" in sorter_txt


def test_inspector_catches_agenda_to_slide_misalignment() -> None:
  pres = _build_perfect_mock_presentation()
  agenda_slide = _make_slide(
      "agenda_slide",
      elements=[
          _make_text_shape(
              "ag_title",
              "Agenda",
              font_pt=36.0,
              x_pt=40.0,
              y_pt=35.0,
              w_pt=250.0,
              h_pt=50.0,
          ),
          _make_text_shape(
              "ag_1",
              "Carrefour Strategic Initiatives",
              font_pt=18.0,
              x_pt=80.0,
              y_pt=110.0,
              w_pt=250.0,
              h_pt=35.0,
          ),
          _make_text_shape(
              "ag_2",
              "Operational Bottlenecks",
              font_pt=18.0,
              x_pt=80.0,
              y_pt=160.0,
              w_pt=250.0,
              h_pt=35.0,
          ),
          _make_text_shape(
              "ag_3",
              "Executive Discovery Questions",
              font_pt=18.0,
              x_pt=80.0,
              y_pt=210.0,
              w_pt=250.0,
              h_pt=35.0,
          ),
          _make_text_shape(
              "ag_4",
              "Art of the Possible with Gemini",
              font_pt=18.0,
              x_pt=380.0,
              y_pt=110.0,
              w_pt=250.0,
              h_pt=35.0,
          ),
          _make_text_shape(
              "ag_5",
              "Joint Value Discovery Workshop",
              font_pt=18.0,
              x_pt=380.0,
              y_pt=160.0,
              w_pt=250.0,
              h_pt=35.0,
          ),
      ],
  )
  # Case 1: Misaligned slides (Bottlenecks overwritten to "Mobilizing...", no '?' discovery questions, Workshop replaced by seat pricing)
  s_context = pres["slides"][2]
  s_context["pageElements"][0]["shape"]["text"]["textElements"][0]["textRun"][
      "content"
  ] = "Mobilizing enterprise data context to power agentic retail\n"
  s_closing = pres["slides"][3]
  s_closing["pageElements"][0]["shape"]["text"]["textElements"][0]["textRun"][
      "content"
  ] = "Scaling retail agent adoption with Gemini\n"
  s_closing["pageElements"][1]["shape"]["text"]["textElements"][0]["textRun"][
      "content"
  ] = (
      "Blend pay-as-you-go and seat pricing to eliminate sunk seat license"
      " expenses."
  )

  inspector = DeckPerfectionInspector()
  g05_bad = inspector._gate_05_cover_logo_and_sculpture(
      pres["slides"][0],
      content_slides=[(3, s_context), (4, s_closing)],
      agenda_slide=agenda_slide,
      customer_name="Carrefour",
  )
  assert g05_bad.passed is False
  assert any("Operational Bottlenecks" in v for v in g05_bad.violations)
  assert any("Executive Discovery Questions" in v for v in g05_bad.violations)
  assert any("Joint Value Discovery Workshop" in v for v in g05_bad.violations)

  # Case 2: Aligned slides pass Gate 05
  s_bottleneck = pres["slides"][1]
  s_bottleneck["pageElements"][0]["shape"]["text"]["textElements"][0][
      "textRun"
  ][
      "content"
  ] = "Operational bottlenecks across Carrefour store and media silos\n"
  s_questions = pres["slides"][2]
  s_questions["pageElements"][0]["shape"]["text"]["textElements"][0]["textRun"][
      "content"
  ] = "Executive discovery questions to unlock Carrefour value\n"
  s_questions["pageElements"][1]["shape"]["text"]["textElements"][0]["textRun"][
      "content"
  ] = (
      "How can Carrefour evolve Hopla into a multimodal shopping agent? Where"
      " can BigQuery Data Clean Rooms accelerate Unlimitail attribution?"
  )
  s_workshop = pres["slides"][3]
  s_workshop["pageElements"][0]["shape"]["text"]["textElements"][0]["textRun"][
      "content"
  ] = "Joint Value Discovery Workshop and 30-60-90 day charter\n"
  s_workshop["pageElements"][1]["shape"]["text"]["textElements"][0]["textRun"][
      "content"
  ] = (
      "Step 1: Discovery sprint in Weeks 1-2. Step 2: Architecture design in"
      " Weeks 3-4. Step 3: Store pilot validation."
  )

  g05_good = inspector._gate_05_cover_logo_and_sculpture(
      pres["slides"][0],
      content_slides=[(3, s_bottleneck), (4, s_questions), (5, s_workshop)],
      agenda_slide=agenda_slide,
      customer_name="Carrefour",
  )
  assert g05_good.passed is True, g05_good.violations


def test_meeting_context_customer_centric_pipeline_and_shape_alignment() -> (
    None
):
  """Verifies customer-centric bespoke section detection and strict shape_id mapping without positional shift."""
  from agents.workflows.content_synthesis_workflow import ContentSynthesisWorkflow

  assert (
      ContentSynthesisWorkflow.is_customer_centric_bespoke_section(
          "1",
          {"title": "Carrefour Strategic Initiatives"},
          [
              "Carrefour 2026 Strategic Plan & Digital Retail Priorities",
              "Current Technology Footprint: SAP S/4HANA, BigQuery & Hopla",
          ],
      )
      is True
  )
  assert (
      ContentSynthesisWorkflow.is_customer_centric_bespoke_section(
          "2",
          {"title": "Operational Bottlenecks"},
          ["Data Silos Across 12,000 Stores & Retail Media Latency"],
      )
      is True
  )
  assert (
      ContentSynthesisWorkflow.is_customer_centric_bespoke_section(
          "3",
          {"title": "Executive Discovery Questions"},
          ["Consultative Questions to Uncover High-ROI Pilots"],
      )
      is True
  )
  assert (
      ContentSynthesisWorkflow.is_customer_centric_bespoke_section(
          "5",
          {"title": "Joint Value Discovery Workshop"},
          ["30-60-90 Day Pilot Charter & Architecture Alignment"],
      )
      is True
  )
  assert (
      ContentSynthesisWorkflow.is_customer_centric_bespoke_section(
          "4",
          {"title": "Art of the Possible with Gemini"},
          [
              "Gemini Enterprise for Customer Experience",
              "Lead the Agentic Workplace Transformation",
          ],
      )
      is False
  )

  from agents.skill_loader import resolve_required_sales_plays

  plays = resolve_required_sales_plays({
      "salesPlay": [
          "Gemini Enterprise for Customer Experience",
          "Lead the Agentic Workplace Transformation",
      ],
      "business_context": (
          "Carrefour runs SAP S/4HANA on Google Cloud and BigQuery across"
          " 12,000 stores. We want to explore agentic commerce and workplace"
          " productivity."
      ),
  })
  assert plays == [
      "Gemini Enterprise for Customer Experience",
      "Lead the Agentic Workplace Transformation",
  ], plays


def _simulate_slide_from_requests(
    slide_id: str,
    reqs: list[dict],
    notes_text: str = "Custom generated slide (Context-v1 bespoke synthesis).\nExecutive talking points for Carrefour.",
) -> dict:
  """Converts a list of Slides API createShape/insertText/updateTextStyle requests into a mock slide dict for DeckPerfectionInspector."""
  shapes_by_id: dict[str, dict] = {}
  for req in reqs:
    if "createShape" in req:
      cs = req["createShape"]
      oid = cs["objectId"]
      ep = cs["elementProperties"]
      shapes_by_id[oid] = {
          "objectId": oid,
          "size": ep["size"],
          "transform": ep["transform"],
          "shape": {
              "shapeType": cs["shapeType"],
              "text": {"textElements": []},
          },
      }
    elif "insertText" in req:
      it = req["insertText"]
      oid = it["objectId"]
      if oid in shapes_by_id:
        shapes_by_id[oid]["shape"]["text"]["textElements"].append({
            "textRun": {
                "content": it["text"] + "\n",
                "style": {
                    "fontSize": {"magnitude": 11.0, "unit": "PT"},
                    "bold": False,
                },
            }
        })
    elif "updateTextStyle" in req:
      uts = req["updateTextStyle"]
      oid = uts["objectId"]
      if (
          oid in shapes_by_id
          and shapes_by_id[oid]["shape"]["text"]["textElements"]
      ):
        st = uts.get("style", {})
        run_style = shapes_by_id[oid]["shape"]["text"]["textElements"][0][
            "textRun"
        ]["style"]
        if "fontSize" in st:
          run_style["fontSize"] = st["fontSize"]
        if "bold" in st:
          run_style["bold"] = st["bold"]

  return _make_slide(
      slide_id,
      elements=list(shapes_by_id.values()),
      notes_text=notes_text,
  )


def test_deck_transformation_inspector_10_gates():
  """Verifies DeckTransformationInspector (T01-T10) on valid and invalid transformations."""
  from evals.deck_perfection_inspector import DeckTransformationInspector

  inspector = DeckTransformationInspector()
  before_pres = {
      "presentationId": "1AbCdEfGhIjKlMnOpQrStUvWxYz123456",
      "slides": [
          _make_slide(
              "s1_cover",
              elements=[
                  _make_text_shape(
                      "s1_title",
                      "Agentic Commerce at Uniqlo",
                      font_pt=68.0,
                      w_pt=385.0,
                      h_pt=180.0,
                  )
              ],
          ),
          {
              **_make_slide(
                  "s2_agenda",
                  elements=[
                      _make_text_shape(
                          "s2_title",
                          "Agenda",
                          font_pt=28.0,
                          y_pt=24.0,
                          w_pt=640.0,
                          h_pt=65.0,
                      ),
                      _make_text_shape(
                          "s2_item1",
                          "01 Omnichannel Strategy",
                          font_pt=18.0,
                          y_pt=110.0,
                          w_pt=300.0,
                          h_pt=65.0,
                      ),
                  ],
              ),
              "slide_role": "agenda",
              "agenda_items": ["01 Omnichannel Strategy"],
          },
          {
              **_make_slide(
                  "s3_sol",
                  elements=[
                      _make_text_shape(
                          "s3_title",
                          "Monetize",
                          font_pt=28.0,
                          y_pt=24.0,
                          w_pt=640.0,
                          h_pt=80.0,
                      ),
                      _make_text_shape(
                          "s3_card1",
                          (
                              "Legacy batch replenishment pipelines delay store"
                              " stock updates across regional hubs."
                          ),
                          font_pt=12.0,
                          y_pt=110.0,
                          w_pt=200.0,
                          h_pt=180.0,
                      ),
                  ],
                  notes_text="🔗 Source Slide: Retail Deck (Slide 6)",
              ),
              "template_id": "T1",
              "card_count": 3,
          },
          _make_slide(
              "s4_proof",
              elements=[
                  _make_text_shape(
                      "s4_title",
                      "H&M reduced stockouts by 35% with Google Cloud",
                      font_pt=26.0,
                      y_pt=24.0,
                      w_pt=640.0,
                      h_pt=65.0,
                  ),
                  _make_text_shape(
                      "s4_body",
                      "Verified customer case study quote from H&M leadership.",
                      font_pt=14.0,
                      y_pt=110.0,
                      w_pt=500.0,
                      h_pt=120.0,
                  ),
              ],
              notes_text="Lock: IMMUTABLE Customer Reference slide.",
          ),
      ],
  }

  after_pres = {
      "presentationId": "1AbCdEfGhIjKlMnOpQrStUvWxYz123456",
      "slides": [
          before_pres["slides"][0],
          {
              **_make_slide(
                  "s2_agenda",
                  elements=[
                      _make_text_shape(
                          "s2_title",
                          "Executive briefing agenda for Uniqlo",
                          font_pt=28.0,
                          y_pt=24.0,
                          w_pt=640.0,
                          h_pt=65.0,
                      ),
                      _make_text_shape(
                          "s2_item1",
                          "Uniqlo Connected Store Vision",
                          font_pt=18.0,
                          y_pt=110.0,
                          w_pt=300.0,
                          h_pt=65.0,
                      ),
                  ],
              ),
              "slide_role": "agenda",
              "agenda_items": ["Uniqlo Connected Store Vision"],
          },
          {
              **_make_slide(
                  "s3_sol",
                  elements=[
                      _make_text_shape(
                          "s3_title",
                          (
                              "Unifying Uniqlo store replenishment with Gemini"
                              " Enterprise"
                          ),
                          font_pt=26.0,
                          y_pt=24.0,
                          w_pt=640.0,
                          h_pt=80.0,
                      ),
                      _make_text_shape(
                          "s3_card1",
                          (
                              "Uniqlo store associates receive real-time RFID"
                              " stock alerts in Gemini Enterprise on mobile."
                          ),
                          font_pt=12.0,
                          y_pt=110.0,
                          w_pt=200.0,
                          h_pt=180.0,
                      ),
                  ],
                  notes_text="🔗 Source Slide: Retail Deck (Slide 6)",
              ),
              "template_id": "T2",
              "card_count": 3,
          },
          before_pres["slides"][3],
      ],
  }

  report = inspector.inspect_transformation_dict(
      before_pres,
      after_pres,
      workflow_type="transform_slide",
      customer_name="Uniqlo",
      specific_use_case="Uniqlo RFID store replenishment",
      target_slide_numbers=[2, 3],
  )
  assert report.passed_all_gates is True, [
      (g.gate_id, g.violations) for g in report.gate_results if not g.passed
  ]
  assert len(report.gate_results) == 10

  # Introduce violations across T01, T02, T03, T07, T09, T10
  bad_after_pres = {
      "presentationId": "1AbCdEfGhIjKlMnOpQrStUvWxYz123456",
      "slides": [
          before_pres["slides"][0],
          before_pres["slides"][1],
          {
              **_make_slide(
                  "s3_sol",
                  elements=[
                      _make_text_shape(
                          "s3_title",
                          "01 Vertex AI Agent Builder for Uniqlo",
                          font_pt=20.0,
                          y_pt=24.0,
                          w_pt=640.0,
                          h_pt=45.0,
                      ),
                      _make_text_shape(
                          "s3_card1",
                          (
                              "Legacy batch replenishment pipelines delay store"
                              " stock updates across Uniqlo hubs."
                          ),
                          font_pt=12.0,
                          y_pt=110.0,
                          w_pt=200.0,
                          h_pt=180.0,
                      ),
                  ],
              ),
              "template_id": "T1",
              "card_count": 2,
          },
          _make_slide(
              "s4_proof",
              elements=[
                  _make_text_shape(
                      "s4_title",
                      "H&M reduced stockouts by 35% with Google Cloud",
                      font_pt=26.0,
                      y_pt=24.0,
                      w_pt=640.0,
                      h_pt=45.0,
                  ),
                  _make_text_shape(
                      "s4_body",
                      "Mutated customer case study quote for Uniqlo.",
                      font_pt=14.0,
                      y_pt=110.0,
                      w_pt=500.0,
                      h_pt=120.0,
                  ),
              ],
              notes_text="Lock: IMMUTABLE Customer Reference slide.",
          ),
      ],
  }
  bad_report = inspector.inspect_transformation_dict(
      before_pres,
      bad_after_pres,
      workflow_type="transform_slide",
      customer_name="Uniqlo",
      specific_use_case="Uniqlo RFID store replenishment",
      target_slide_numbers=[2, 3],
  )
  assert bad_report.passed_all_gates is False
  failed_ids = {g.gate_id for g in bad_report.gate_results if not g.passed}
  for expected_gate in ("T01", "T02", "T03", "T05", "T07", "T10"):
    assert (
        expected_gate in failed_ids
    ), f"Expected {expected_gate} in {failed_ids}"


def test_pitch_deck_qa_skill_loader():
  """Verifies pitch_deck_qa skill loading and dynamic matching."""
  from agents.skill_loader import get_matching_skill_instructions, load_skill_instructions

  matched = get_matching_skill_instructions(
      "Run QA audit on deck transformation and verify 16 gates"
  )
  assert "G01" in matched and "G16" in matched
  assert "T01" in matched and "T10" in matched
  skill_md = load_skill_instructions("pitch_deck_qa")
  assert "4-Quadrant" in skill_md or "Quadrant" in skill_md
  assert "TITLE_ONLY_CUSTOMIZATION" in skill_md


def test_transformation_inspector_title_only_and_light_ceiling():
  """Verifies T02 15% LIGHT ceiling and T03 TITLE_ONLY_CUSTOMIZATION detection."""
  inspector = DeckTransformationInspector()
  before_pres = {
      "presentationId": "1TitleOnlyTestDeck1234567890",
      "slides": [
          _make_slide(
              "s1_cover",
              elements=[
                  _make_text_shape(
                      "s1_title",
                      "Agentic retail at Uniqlo",
                      font_pt=68.0,
                      y_pt=40.0,
                      w_pt=380.0,
                      h_pt=180.0,
                  )
              ],
          ),
          {
              **_make_slide(
                  "s2_cur_state",
                  elements=[
                      _make_text_shape(
                          "s2_title",
                          "Current retail challenges",
                          font_pt=28.0,
                          y_pt=24.0,
                          w_pt=640.0,
                          h_pt=65.0,
                      ),
                      _make_text_shape(
                          "s2_body1",
                          "Generic retail inventory silos delay store"
                          " restocking.",
                          font_pt=12.0,
                          y_pt=110.0,
                          w_pt=200.0,
                          h_pt=180.0,
                      ),
                      _make_text_shape(
                          "s2_body2",
                          "Manual markdown forecasting erodes gross margin.",
                          font_pt=12.0,
                          y_pt=110.0,
                          w_pt=200.0,
                          h_pt=180.0,
                      ),
                  ],
              ),
              "slide_job": "Current_State",
          },
          {
              **_make_slide(
                  "s3_wgc",
                  elements=[
                      _make_text_shape(
                          "s3_title",
                          "Why Google Cloud",
                          font_pt=28.0,
                          y_pt=24.0,
                          w_pt=640.0,
                          h_pt=65.0,
                      ),
                      _make_text_shape(
                          "s3_diff1",
                          "Planet-scale AI infrastructure and custom TPUs.",
                          font_pt=12.0,
                          y_pt=110.0,
                          w_pt=200.0,
                          h_pt=180.0,
                      ),
                      _make_text_shape(
                          "s3_diff2",
                          "Unified open data cloud with zero-copy governance.",
                          font_pt=12.0,
                          y_pt=110.0,
                          w_pt=200.0,
                          h_pt=180.0,
                      ),
                  ],
              ),
              "slide_job": "Why_Google_Cloud",
          },
      ],
  }
  after_pres = {
      "presentationId": "1TitleOnlyTestDeck1234567890",
      "slides": [
          before_pres["slides"][0],
          {
              **_make_slide(
                  "s2_cur_state",
                  elements=[
                      _make_text_shape(
                          "s2_title",
                          "Resolving Uniqlo store inventory bottlenecks",
                          font_pt=28.0,
                          y_pt=24.0,
                          w_pt=640.0,
                          h_pt=65.0,
                      ),
                      # Both body shapes left completely uncustomized!
                      before_pres["slides"][1]["pageElements"][1],
                      before_pres["slides"][1]["pageElements"][2],
                  ],
              ),
              "slide_job": "Current_State",
          },
          {
              **_make_slide(
                  "s3_wgc",
                  elements=[
                      _make_text_shape(
                          "s3_title",
                          "Why Google Cloud for Uniqlo",
                          font_pt=28.0,
                          y_pt=24.0,
                          w_pt=640.0,
                          h_pt=65.0,
                      ),
                      # Both Why_Google_Cloud body cards mutated (> 25% ceiling!)
                      _make_text_shape(
                          "s3_diff1",
                          "Uniqlo custom store network infrastructure.",
                          font_pt=12.0,
                          y_pt=110.0,
                          w_pt=200.0,
                          h_pt=180.0,
                      ),
                      _make_text_shape(
                          "s3_diff2",
                          "Uniqlo custom RFID data lakehouse.",
                          font_pt=12.0,
                          y_pt=110.0,
                          w_pt=200.0,
                          h_pt=180.0,
                      ),
                  ],
              ),
              "slide_job": "Why_Google_Cloud",
          },
      ],
  }
  report = inspector.inspect_transformation_dict(
      before_pres,
      after_pres,
      workflow_type="transform_text",
      customer_name="Uniqlo",
      specific_use_case="Uniqlo RFID store replenishment",
      target_slide_numbers=[2, 3],
  )
  by_gate = {g.gate_id: g for g in report.gate_results}
  assert by_gate["T02"].passed is False
  assert any("15% LIGHT ceiling" in v for v in by_gate["T02"].violations)
  assert by_gate["T03"].passed is False
  assert any("TITLE_ONLY_CUSTOMIZATION" in v for v in by_gate["T03"].violations)


def test_smart_hybrid_reusable_recall_and_side_panel_actions() -> None:
  """Verifies G03 smart_hybrid reusable recall gate and 5-Card A2UI side-panel T01-T10 audits."""
  from src.evals.deck_perfection_inspector import DeckTransformationInspector

  # 1. G03 fails if smart_hybrid has >= 3 content slides and 0 reusable/CR slides
  pres = _build_perfect_mock_presentation()
  # Turn slide 2 (index 1, reusable), slide 4 (index 3, reusable), and slide 5 (index 4, CR) into bespoke slides
  for s_idx in (1, 3, 4):
    pres["slides"][s_idx]["slideProperties"]["notesPage"]["pageElements"][0][
        "shape"
    ]["text"]["textElements"][0]["textRun"]["content"] = (
        "Talking Points:\nBespoke slide synthesized for Uniqlo.\n"
        "Slide Design Rationale: Bespoke Context-v1 (T5)."
    )
    pres["slides"][s_idx]["slideProperties"]["notesPage"]["pageElements"][0][
        "shape"
    ]["text"]["textElements"][0]["textRun"]["style"].pop("link", None)

  inspector = DeckPerfectionInspector()
  report = inspector.inspect_presentation_dict(
      pres,
      customer_name="Uniqlo",
      deck_strategy="smart_hybrid",
      deck_length="Brief (4-6 slides)",
      sales_stage="S1",
  )
  by_id = {g.gate_id: g for g in report.gate_results}
  assert by_id["G03"].passed is False
  assert any(
      "yielded 0 reusable/CR slides" in v for v in by_id["G03"].violations
  )

  # 2. insert_library_slide side-panel action passes T01-T10 when +1 non-blank slide is inserted
  before_pres = _build_perfect_mock_presentation()
  inserted_slide = _make_slide(
      "s_inserted_lib",
      elements=[
          _make_text_shape(
              "ins_title",
              "How Carrefour scaled omnichannel checkout on Google Cloud",
              font_pt=28.0,
              y_pt=24.0,
              w_pt=640.0,
              h_pt=60.0,
          ),
          _make_text_shape(
              "ins_body",
              "Carrefour reduced checkout latency by 42% using Spanner and"
              " Gemini Enterprise across 14,000 stores.",
              font_pt=12.0,
              y_pt=110.0,
              w_pt=450.0,
              h_pt=160.0,
          ),
      ],
      notes_text=(
          "Talking Points:\nVerified Customer Reference from 2026 Library.\n"
          "Source Slide:"
          " https://docs.google.com/presentation/d/1AbCdEfGhIjKlMnOpQrStUvWxYz123456/edit#slide=id.p1"
      ),
      notes_link="https://docs.google.com/presentation/d/1AbCdEfGhIjKlMnOpQrStUvWxYz123456/edit#slide=id.p1",
  )
  after_pres = {
      "presentationId": before_pres["presentationId"],
      "slides": list(before_pres["slides"]) + [inserted_slide],
  }
  tf_inspector = DeckTransformationInspector()
  ins_report = tf_inspector.inspect_transformation_dict(
      before_pres,
      after_pres,
      workflow_type="insert_library_slide",
      customer_name="Uniqlo",
      target_slide_numbers=[len(after_pres["slides"])],
  )
  assert ins_report.passed_all_gates is True, [
      (g.gate_id, g.violations) for g in ins_report.gate_results if not g.passed
  ]

  # 3. Verify 108-deck marathon matrix includes all 7 post-deck side-panel actions
  specs_108 = get_test_matrix("tier3_marathon")
  cov = verify_matrix_coverage(specs_108)
  assert cov["total_specs"] == 108
  assert len(cov["side_panel_actions_covered"]) >= 7
  assert cov["smart_hybrid_specs_count"] >= 36

  # 4. Split-element "You" + "Thank" + "Proprietary & Confidential" closing slide is detected as closing slide
  from src.evals.deck_perfection_inspector import _is_closing_thank_you_slide

  split_closing = _make_slide(
      "g3ed09d4594d_0_144",
      elements=[
          _make_text_shape("you_box", "You", font_pt=48.0, y_pt=180.0),
          _make_text_shape("thank_box", "Thank", font_pt=48.0, y_pt=120.0),
          _make_text_shape(
              "footer_box",
              "Proprietary & Confidential",
              font_pt=8.0,
              y_pt=380.0,
          ),
      ],
  )
  assert _is_closing_thank_you_slide(split_closing) is True


if __name__ == "__main__":
  import pytest

  raise SystemExit(pytest.main([__file__]))
