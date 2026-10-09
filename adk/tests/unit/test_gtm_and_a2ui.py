import json
import os
import sys

if not os.path.exists("/opt/google/endpoint-verification/bin/apihelper"):
  os.environ["GOOGLE_API_USE_CLIENT_CERTIFICATE"] = "false"

# Ensure modules can be imported
pitchgen_dir = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, pitchgen_dir)
sys.path.insert(0, os.path.join(pitchgen_dir, "src"))

from agents.gtm_skills import GTMSkills
from pitchgen_utils.a2ui_util import format_a2ui_deck_card


def test_format_a2ui_deck_card():
  deck_url = (
      "https://docs.google.com/presentation/d/1234567890/edit?usp=sharing"
  )
  result = format_a2ui_deck_card(
      deck_url=deck_url,
      customer_name="Starbucks",
      er_number="ER-9999",
      user_ldap="seller_user",
      architectural_gcs_url="gs://bucket/arch.json",
      outputs_gcs_url="gs://bucket/out.json",
  )

  assert result["status"] == "success"
  assert result["deck_url"] == deck_url
  assert "embed" in result["canvas_embed_url"]
  assert result["metadata"]["mimeType"] == "application/json+a2ui"
  card = result["a2ui_card"]
  assert card["type"] == "card"
  assert "Starbucks" in card["title"]
  assert "ER-9999" in card["subtitle"]
  assert card["canvasPreview"]["supported"] is True
  assert len(card["sections"]) >= 2
  actions_sec = next(
      (s for s in card["sections"] if s.get("type") == "actions"), None
  )
  assert actions_sec is not None
  buttons = actions_sec["buttons"]
  assert len(buttons) == 3
  assert buttons[0]["url"] == deck_url
  assert buttons[1]["url"] == "https://your-sales-portal.example.com/pitchgen"
  assert buttons[2]["url"] == "https://your-sales-portal.example.com/catalog"
  assert any(s.get("type") == "quick_actions" for s in card["sections"])


def test_phub_handoff_skill():
  response_json = GTMSkills.phub_handoff_skill(
      customer_name="Target Corp",
      er_number="ER-8888",
      business_context="Need custom Retail AI demo deck.",
      deck_url="https://docs.google.com/presentation/d/abc",
      user_ldap="seller_user",
  )
  data = json.loads(response_json)
  assert data["status"] == "success"
  assert "Target Corp" in data["message"]
  assert data["escalation_package"]["opportunityEr"] == "ER-8888"
  assert data["escalation_package"]["serviceCatalogUrl"] == "https://your-sales-portal.example.com/catalog"
  assert data["escalation_package"]["newRequestUrl"] == "https://your-sales-portal.example.com/requests/new"


def test_rfp_accelerator_skill():
  response_json = GTMSkills.rfp_accelerator_skill(
      rfp_question="How does Vertex AI encrypt customer data at rest?",
      customer_name="Home Depot",
      industry="Retail",
      solution="Vertex AI",
      compliance_frameworks="FedRAMP, SOC2",
  )
  data = json.loads(response_json)
  assert data["customer"] == "Home Depot"
  assert "FedRAMP" in data["compliance_verified"]
  assert "SOC2" in data["compliance_verified"]
  assert "Google Cloud delivers enterprise-grade security" in data["recommended_response"]
  assert data["rfp_app_link"] == "https://your-sales-portal.example.com/rfp-accelerator"


def test_polish_presentation_text_options():
  from agents.slide_engineering_agent import SlideEngineeringAgent

  class DummyTextTransformer:
    def execute(self, text, criteria=""):
      return f"[Polished] {text}"

  from config_loader import load_config
  agent = SlideEngineeringAgent(load_config())
  agent.skills["text_transformer"] = DummyTextTransformer()

  deck_data = {
      "slides": [
          {"objectId": "slide_1", "text": "Slide 1 Content"},
          {"objectId": "slide_2", "text": "Slide 2 Content"},
          {"objectId": "slide_3", "text": "Slide 3 Content"},
      ]
  }

  # Test 1: Full Deck transformation (target_slide_ids=None)
  full_res = agent.polish_presentation_text(deck_data, target_slide_ids=None)
  assert full_res["slides"][0]["text"] == "[Polished] Slide 1 Content"
  assert full_res["slides"][1]["text"] == "[Polished] Slide 2 Content"
  assert full_res["slides"][2]["text"] == "[Polished] Slide 3 Content"

  # Test 2: Multiple / Selected slides transformation
  partial_res = agent.polish_presentation_text(
      deck_data, target_slide_ids=["slide_2", "slide_3"]
  )
  assert partial_res["slides"][0]["text"] == "Slide 1 Content"
  assert partial_res["slides"][1]["text"] == "[Polished] Slide 2 Content"
  assert partial_res["slides"][2]["text"] == "[Polished] Slide 3 Content"


def test_slide_job_customization_intensity():
  # Test 1: Verify GTMSkills.slide_job_skill returns intensity and throttling tiers
  proof_json = GTMSkills.slide_job_skill("Proof_Points")
  proof_data = json.loads(proof_json)
  assert proof_data["customization_intensity"] == "0% (IMMUTABLE)"
  assert proof_data["throttling_tier"] == "IMMUTABLE"

  why_json = GTMSkills.slide_job_skill("Why_Google_Cloud")
  why_data = json.loads(why_json)
  assert why_data["customization_intensity"] == "15% (LIGHT)"
  assert why_data["throttling_tier"] == "LIGHT"

  val_json = GTMSkills.slide_job_skill("Business_Value")
  val_data = json.loads(val_json)
  assert val_data["customization_intensity"] == "100% (FULL)"
  assert val_data["throttling_tier"] == "FULL"

  # Test 2: Verify TextTransformerWorkflow throttling guardrail strings
  from agents.workflows.text_transformer_workflow import TextTransformerWorkflow
  from config_loader import load_config
  workflow = TextTransformerWorkflow(load_config())

  imm_rule = workflow._get_slide_job_throttling_rules("Proof_Points slide for Nike")
  assert "0% IMMUTABLE" in imm_rule
  assert "Do NOT customize or replace existing third-party customer references" in imm_rule

  light_rule = workflow._get_slide_job_throttling_rules("Why_Google_Cloud slide for Starbucks")
  assert "15-25% LIGHT CUSTOMIZATION" in light_rule
  assert "Preserve core Google Cloud differentiators" in light_rule

  heavy_rule = workflow._get_slide_job_throttling_rules("Customize this slide for Nike")
  assert "85-100% FULL ACCOUNT CUSTOMIZATION" in heavy_rule
  assert "Tailor every bullet and financial proof point" in heavy_rule


def test_validate_slide_metadata_schema():
  # Test 1: Valid compliant schema
  valid_metadata = {
      "slide_id": "test_slide_01",
      "taxonomy": {
          "slide_job": "Architecture",
          "cvi_cluster": "Vision",
          "target_audience": ["TDM"],
          "technical_maturity": "L300 (Deep Technical)",
      },
      "gtm_filters": {
          "industry_verticals": ["Retail"],
          "featured_products": ["Gemini Enterprise", "BigQuery"],
      },
      "governance": {
          "confidentiality": "Google Confidential",
          "status": "Approved",
      },
  }
  res_valid = json.loads(
      GTMSkills.validate_slide_metadata_schema(json.dumps(valid_metadata))
  )
  assert res_valid["status"] == "success"
  assert res_valid["valid"] is True

  # Test 2: Invalid legacy nomenclature (Vertex AI)
  invalid_metadata = dict(valid_metadata)
  invalid_metadata["gtm_filters"] = {
      "featured_products": ["Vertex AI Search", "BigQuery"]
  }
  res_invalid = json.loads(
      GTMSkills.validate_slide_metadata_schema(json.dumps(invalid_metadata))
  )
  assert res_invalid["status"] == "error"
  assert res_invalid["valid"] is False
  assert "Legacy terminology detected" in res_invalid["message"]


def test_presentation_archetypes_skill_and_detection():
  from agents.skill_loader import load_skill_instructions
  from agents.workflows.outline_workflow import (
      CANONICAL_PRESENTATION_ARCHETYPES,
      OutlineWorkflow,
      normalize_presentation_archetype,
  )
  from config_loader import load_config

  # 1. Verify skill markdown loads properly with all 8 Cloud GTM archetypes
  instructions = load_skill_instructions("presentation_archetypes")
  assert instructions is not None
  for arch_id in CANONICAL_PRESENTATION_ARCHETYPES:
    assert arch_id in instructions

  # 2. Verify legacy alias normalization
  assert (
      normalize_presentation_archetype("Executive_Vision_Strategic")
      == "Executive_Vision_Briefing"
  )
  assert (
      normalize_presentation_archetype("Technical_Architecture")
      == "Technical_Solutioning_Pitch"
  )
  assert (
      normalize_presentation_archetype("Practitioner_Technical_Architecture")
      == "Architecture_PoC_Workshop"
  )
  assert (
      normalize_presentation_archetype("CFO_Business_Case")
      == "Value_Case_Commercial_Proposal"
  )
  assert (
      normalize_presentation_archetype("Discovery_First_Call")
      == "First_Call_Discovery"
  )
  assert (
      normalize_presentation_archetype("General_Value_Pitch")
      == "Sales_Play_Business_Pitch"
  )
  assert (
      normalize_presentation_archetype("Executive_QBR_Value_Realization")
      == "QBR_Adoption_Expansion"
  )

  # 3. Verify OutlineWorkflow detection heuristics across the 8 GTM archetypes
  workflow = OutlineWorkflow(load_config())

  # Executive Vision Briefing (S0-S1)
  arch_exec = workflow.detect_presentation_archetype(
      client=None,
      business_context="Prepare EBC presentation for Kroger",
      audience=["CEO", "Board"],
      segment="Strategic",
  )
  assert arch_exec == "Executive_Vision_Briefing"

  # Technical Solutioning Pitch (S2)
  arch_tech = workflow.detect_presentation_archetype(
      client=None,
      business_context="Deep dive into data pipeline and ML serving",
      audience=["CTO", "Lead Architect"],
      segment="Enterprise",
  )
  assert arch_tech == "Technical_Solutioning_Pitch"

  # Architecture & PoC Workshop (S2)
  arch_poc = workflow.detect_presentation_archetype(
      client=None,
      business_context="Hands-on PoC readout and sandbox pilot validation",
      audience=["Staff Engineer", "DevOps"],
      win_cycle="S2",
  )
  assert arch_poc == "Architecture_PoC_Workshop"

  # Value Case & Commercial Proposal (S1-S3)
  arch_cfo = workflow.detect_presentation_archetype(
      client=None,
      business_context="Calculate ROI, TCO reduction, and NPV for cloud migration",
      audience=["CFO", "VP Finance"],
      segment="Enterprise",
  )
  assert arch_cfo == "Value_Case_Commercial_Proposal"

  # First Call Discovery (S0)
  arch_disc = workflow.detect_presentation_archetype(
      client=None,
      business_context="First call intro and problem awareness teaser",
      audience=["Director of Retail"],
      win_cycle="S0",
  )
  assert arch_disc == "First_Call_Discovery"

  # Competitive Takeout & Migration (S1-S2)
  arch_comp = workflow.detect_presentation_archetype(
      client=None,
      business_context="AWS displacement and VMware exit with RaMP incentives",
      audience=["VP Infrastructure"],
      win_cycle="S1",
  )
  assert arch_comp == "Competitive_Takeout_Migration"

  # QBR, Adoption & Expansion (S4 / S0')
  arch_qbr = workflow.detect_presentation_archetype(
      client=None,
      business_context="Q3 Executive QBR and CUD commit consumption review",
      audience=["VP Cloud"],
      win_cycle="S4",
  )
  assert arch_qbr == "QBR_Adoption_Expansion"

  # Default -> Sales Play Business Pitch (S1)
  arch_default = workflow.detect_presentation_archetype(
      client=None,
      business_context="General overview of cloud services",
      audience=[],
      segment="",
  )
  assert arch_default == "Sales_Play_Business_Pitch"


def test_internal_only_slide_filtering():
  from agents.retrieval_agent import RetrievalAgent
  from config_loader import load_config

  agent = RetrievalAgent(load_config())

  # 1. Slide with explicit is_customer_facing = False
  slide_explicit_false = {
      "title": "Opportunity 01 | Catalog & Content Enrichment",
      "is_customer_facing": False,
  }
  assert agent._is_internal_only_slide(slide_explicit_false) is True

  # 2. Slide with governance.is_customer_facing = False
  slide_gov_false = {
      "title": "Retail Opportunity Strategy",
      "governance": {
          "is_customer_facing": False,
          "confidentiality": "Google Internal Only",
      },
  }
  assert agent._is_internal_only_slide(slide_gov_false) is True

  # 3. Slide with badge or title containing "INTERNAL ONLY"
  slide_badge = {
      "title": "Opportunity 01 | Catalog & Content Enrichment | INTERNAL ONLY 👁",
      "content": "Pain Points: Low engagement. Products: Gemini Enterprise Agent Platform",
  }
  assert agent._is_internal_only_slide(slide_badge) is True

  # 4. Slide with content mentioning "for internal use only"
  slide_content_internal = {
      "title": "Sales Play Cheat Sheet",
      "content": "Confidential - For internal use only - Do not share with customers",
  }
  assert agent._is_internal_only_slide(slide_content_internal) is True

  # 5. Customer-facing slide
  slide_customer_facing = {
      "title": "Enterprise Agentic Commerce Reference Architecture",
      "content": "Architecture overview using Gemini Enterprise and BigQuery",
      "is_customer_facing": True,
      "governance": {
          "is_customer_facing": True,
          "confidentiality": "Google Confidential",
      },
  }
  assert agent._is_internal_only_slide(slide_customer_facing) is False

  # 6. Verify _filter_raw_results drops internal slides
  raw_slides = [
      slide_badge,
      slide_customer_facing,
      slide_explicit_false,
  ]
  filtered = agent._filter_raw_results(raw_slides, customer_name="Nike")
  assert len(filtered) == 1
  assert filtered[0]["title"] == "Enterprise Agentic Commerce Reference Architecture"


def test_slide_job_narrative_ordering():
  from agents.gtm_skills import GTMSkills

  # 1. Verify slide job inferral
  assert GTMSkills.infer_slide_job({"title": "Current Friction & Data Silos"}) == "Current_State"
  assert GTMSkills.infer_slide_job({"title": "Global Ingestion Architecture Blueprint"}) == "Architecture"
  assert GTMSkills.infer_slide_job({"title": "Home Depot Customer Case Study & Metrics"}) == "Proof_Points"
  assert GTMSkills.infer_slide_job({"title": "30-60-90 Day Migration Roadmap"}) == "Path_to_Prod"

  # 2. Verify narrative hierarchy ordering
  order_current_state = GTMSkills.get_slide_job_narrative_order("Current_State")
  order_solution = GTMSkills.get_slide_job_narrative_order("Solution_Overview")
  order_arch = GTMSkills.get_slide_job_narrative_order("Architecture")
  order_proof = GTMSkills.get_slide_job_narrative_order("Proof_Points")
  order_prod = GTMSkills.get_slide_job_narrative_order("Path_to_Prod")

  assert order_current_state < order_solution < order_arch < order_proof < order_prod


def test_intertwined_slide_sequencing():
  from agents.slide_engineering_agent import get_final_content

  class MockItem:
    title = "Test Proposal"

  # Agenda with 1 section and 3 outline sub-points
  agendas = {
      "1": {
          "title": "Architecture & Production Roadmap",
          "parts": [
              "Current State Friction",
              "Enterprise Agentic Architecture",
              "Migration Timeline",
          ],
      }
  }

  # Generated slides for gap sub-point 0 (Current State) and sub-point 2 (Roadmap)
  place_holders = {
      "1": {
          "slides": {
              "1": {
                  "slide_id": "gen_slide_pain",
                  "title": "Customer Pain Points & Friction",
                  "sequence_index": 0,
                  "slide_job": "Current_State",
                  "cvi_order": 20,
                  "source_type": "generated",
              },
              "2": {
                  "slide_id": "gen_slide_roadmap",
                  "title": "30-60-90 Day Execution Plan",
                  "sequence_index": 2,
                  "slide_job": "Path_to_Prod",
                  "cvi_order": 100,
                  "source_type": "generated",
              },
          }
      }
  }

  # Reusable slide for sub-point 1 (Architecture)
  reusable_slides = {
      "1": {
          "title": "Architecture & Production Roadmap",
          "suggestions": [
              {
                  "slide_id": "reusable_arch_01",
                  "title": "Enterprise Agentic Commerce Architecture",
                  "sequence_index": 1,
                  "slide_job": "Architecture",
                  "cvi_order": 60,
                  "source_type": "reusable",
              }
          ],
      }
  }

  final_struct = get_final_content(
      item=MockItem(),
      place_holders=place_holders,
      agendas=agendas,
      reusable_slides=reusable_slides,
      sources={},
  )

  section_1_slides = final_struct["sections"]["1"]["slides"]

  # Generated slides in section 1
  assert len(section_1_slides) == 2
  assert section_1_slides["1"]["slide_id"] == "gen_slide_pain"
  assert section_1_slides["2"]["slide_id"] == "gen_slide_roadmap"

  # Verify reusable_slides suggestions were assigned intertwined order
  assert reusable_slides["1"]["suggestions"][0]["intertwined_order"] == 1


def test_full_deck_intertwined_e2e():
  """Comprehensive E2E integration test for a full 16+ slide enterprise deck

  verifying that title, agenda, section dividers, reusable slides, and
  synthesized gap slides are all correctly ordered, intertwined, and assembled.
  """
  from agents.slide_engineering_agent import get_final_content

  class MockDeckItem:
    title = "Google Cloud Enterprise AI Transformation for Target"

  # 4 Comprehensive Agenda Sections
  agendas = {
      "1": {
          "title": "Executive Summary & Market Context",
          "parts": [
              "Macro Retail Trends & Consumer Shifts",
              "Target Current State Architecture & Inefficiencies",
          ],
      },
      "2": {
          "title": "Google Cloud Solution & Architecture",
          "parts": [
              "Why Google Cloud & Planetary AI Infrastructure",
              "Agentic Commerce Platform Overview",
              "Real-time Inventory & Recommendation Pipeline Architecture",
          ],
      },
      "3": {
          "title": "Business Value & Proof Points",
          "parts": [
              "Quantified Financial Impact & ROI Projections",
              "Global Retail Proof Points & Customer Stories",
          ],
      },
      "4": {
          "title": "Commercials & Path to Production",
          "parts": [
              "Enterprise EDP Commercial Structure & Pricing",
              "30-60-90 Day Structured CAF Production Roadmap",
          ],
      },
  }

  # Synthesized gap-filling slides from ContentSynthesisWorkflow
  place_holders = {
      "1": {
          "slides": {
              "1": {
                  "slide_id": "gen_s1_current_state",
                  "title": "Target Current State Architecture & Inefficiencies",
                  "sequence_index": 1,
                  "slide_job": "Current_State",
                  "cvi_order": 20,
                  "source_type": "generated",
              }
          }
      },
      "2": {
          "slides": {
              "1": {
                  "slide_id": "gen_s2_platform_overview",
                  "title": "Agentic Commerce Platform Overview",
                  "sequence_index": 1,
                  "slide_job": "Solution_Overview",
                  "cvi_order": 50,
                  "source_type": "generated",
              }
          }
      },
      "3": {
          "slides": {
              "1": {
                  "slide_id": "gen_s3_roi_model",
                  "title": "Quantified Financial Impact & ROI Projections",
                  "sequence_index": 0,
                  "slide_job": "Business_Value",
                  "cvi_order": 70,
                  "source_type": "generated",
              }
          }
      },
      "4": {
          "slides": {
              "1": {
                  "slide_id": "gen_s4_commercials",
                  "title": "Enterprise EDP Commercial Structure & Pricing",
                  "sequence_index": 0,
                  "slide_job": "Commercials",
                  "cvi_order": 90,
                  "source_type": "generated",
              },
              "2": {
                  "slide_id": "gen_s4_roadmap",
                  "title": "30-60-90 Day Structured CAF Production Roadmap",
                  "sequence_index": 1,
                  "slide_job": "Path_to_Prod",
                  "cvi_order": 100,
                  "source_type": "generated",
              },
          }
      },
  }

  # Reusable slides retrieved from GTM sales playbooks & discovery engine
  reusable_slides = {
      "1": {
          "title": "Executive Summary & Market Context",
          "suggestions": [
              {
                  "slide_id": "reusable_s1_market_trends",
                  "title": "Macro Retail Trends & Consumer Shifts",
                  "sequence_index": 0,
                  "slide_job": "Market_Trends",
                  "cvi_order": 10,
                  "source_type": "reusable",
              }
          ],
      },
      "2": {
          "title": "Google Cloud Solution & Architecture",
          "suggestions": [
              {
                  "slide_id": "reusable_s2_why_gcp",
                  "title": "Why Google Cloud & Planetary AI Infrastructure",
                  "sequence_index": 0,
                  "slide_job": "Why_Google_Cloud",
                  "cvi_order": 40,
                  "source_type": "reusable",
              },
              {
                  "slide_id": "reusable_s2_arch_blueprint",
                  "title": (
                      "Real-time Inventory & Recommendation Pipeline"
                      " Architecture"
                  ),
                  "sequence_index": 2,
                  "slide_job": "Architecture",
                  "cvi_order": 60,
                  "source_type": "reusable",
              },
          ],
      },
      "3": {
          "title": "Business Value & Proof Points",
          "suggestions": [
              {
                  "slide_id": "reusable_s3_case_study",
                  "title": "Global Retail Proof Points & Customer Stories",
                  "sequence_index": 1,
                  "slide_job": "Proof_Points",
                  "cvi_order": 80,
                  "source_type": "reusable",
              }
          ],
      },
      "4": {
          "title": "Commercials & Path to Production",
          "suggestions": [],
      },
  }

  sources = {
      "1": ["GTM Retail Playbook 2026"],
      "2": ["Google Cloud Reference Architecture Library"],
      "3": ["Customer Success Case Studies"],
      "4": ["Google Cloud Pricing Calculator"],
  }

  # Assemble full presentation deck structure
  final_deck = get_final_content(
      item=MockDeckItem(),
      place_holders=place_holders,
      agendas=agendas,
      reusable_slides=reusable_slides,
      sources=sources,
  )

  sections = final_deck["sections"]

  # 1. Verify Deck Structural Sections (without disruptive divider break slides)
  assert "title" in sections
  assert "agenda" in sections
  assert "1" in sections
  assert "2" in sections
  assert "3" in sections
  assert "4" in sections
  assert "thank_you" in sections

  # 2. Count total sections (title + agenda + 4 content sections + thank you = 7)
  assert len(sections) == 7
  assert len(sections["1"]["slides"]) == 1
  assert len(sections["2"]["slides"]) == 1
  assert len(sections["3"]["slides"]) == 1
  assert len(sections["4"]["slides"]) == 2


def test_consult_skill():
  from agent import PitchGenSkills

  # Test valid skill
  res_str = PitchGenSkills.consult_skill("cvi_framework")
  res = json.loads(res_str)
  assert res["status"] == "success"
  assert res["skill_name"] == "cvi_framework"
  assert "Customer Value Imperative" in res["instructions"] or "CVI" in res["instructions"]

  # Test unknown skill returns list of available skills
  unknown_str = PitchGenSkills.consult_skill("unknown_skill_xyz")
  unknown_res = json.loads(unknown_str)
  assert unknown_res["status"] == "not_found"
  assert "cvi_framework" in unknown_res["available_skills"]


def test_foundation_deck_closest_industry_and_vertical_isolation():
  from agents.workflows.foundation_deck_workflow import FoundationDeckWorkflow
  from config_loader import load_config

  wf = FoundationDeckWorkflow(load_config())

  # 1. Resolve closest industry for Lovable with GenMedia
  context = {
      "customer_name": "Lovable",
      "industry": "Technology",
      "salesPlay": [
          "Leverage Generative Media in Your Business",
          "Lead the Agentic Workplace Transformation",
      ],
      "user_request": "Pitch Lovable on GenMedia and Agentic Workplace.",
  }
  closest = wf.resolve_closest_industry(context)
  assert closest == "Technology"

  # 2. Candidate deck evaluation: GenMedia and Why Google for closest industry should have positive score
  genmedia_deck = {
      "deck_id": "SAMPLE_TEST_PRESENTATION_ID_000000000009",
      "title": (
          "[External] Customer Presentation | GenMedia: Accelerate and Enhance"
          " Content Creation with AI"
      ),
  }
  eval_context = dict(context)
  eval_context["closest_industry"] = closest
  score_gm = wf.evaluate_deck_affinity(
      genmedia_deck,
      target_play="Leverage Generative Media in Your Business",
      context=eval_context,
      is_technical=False,
  )
  assert score_gm > 0

  # 3. Candidate deck evaluation: Manufacturing, Banking, and CPG must be strictly disqualified (-100.0)
  mfg_deck = {
      "deck_id": "g3d2c57493e6_0_7",
      "title": "Why Google Cloud for Manufacturing",
  }
  score_mfg = wf.evaluate_deck_affinity(
      mfg_deck,
      target_play=f"Why Google Cloud ({closest})",
      context={"closest_industry": closest},
      is_technical=False,
  )
  assert score_mfg == -100.0

  banking_deck = {
      "deck_id": "g3dac0806830_0_4631",
      "title": "Why Google Cloud for Banking",
  }
  score_banking = wf.evaluate_deck_affinity(
      banking_deck,
      target_play=f"Why Google Cloud ({closest})",
      context={"closest_industry": closest},
      is_technical=False,
  )
  assert score_banking == -100.0

  cpg_deck = {
      "deck_id": "g3f52427a1a4_0_0",
      "title": "Why Google Cloud for CPG",
  }
  score_cpg = wf.evaluate_deck_affinity(
      cpg_deck,
      target_play=f"Why Google Cloud ({closest})",
      context={"closest_industry": closest},
      is_technical=False,
  )
  assert score_cpg == -100.0


def test_retrieval_agent_leak_filtering_and_proof_points():
  from agents.retrieval_agent import RetrievalAgent
  from config_loader import load_config

  agent = RetrievalAgent(load_config())

  context = {
      "customer_name": "Lovable",
      "salesPlay": [
          "Leverage Generative Media in Your Business",
          "Lead the Agentic Workplace Transformation",
      ],
      "closest_industry": "Media & Entertainment",
      "anchor_deck_ids": [
          "SAMPLE_TEST_PRESENTATION_ID_000000000009",
          "deck_why_google_media",
      ],
  }

  raw_slides = [
      # Leaked slides from user deck:
      {
          "deck_id": "g39a46c8b9f6_0_548",
          "title": "[Corporate] Agentic Data Cloud Pitch Deck",
          "name": "Data Slide",
      },
      {
          "deck_id": "g39b153f05e0_0_4545",
          "title": (
              "FSI - HPC IBM Spectrum Symphony Solution Play - Business Pitch"
          ),
          "name": "IBM HPC Slide",
      },
      {
          "deck_id": "g3d2c57493e6_0_7",
          "title": "Why Google Cloud for Manufacturing",
          "name": "Mfg Slide",
      },
      {
          "deck_id": "g3dac0806830_0_4631",
          "title": "Why Google Cloud for Banking",
          "name": "Banking Slide",
      },
      {
          "deck_id": "g3f52427a1a4_0_0",
          "title": "Why Google Cloud for CPG",
          "name": "CPG Slide",
      },
      {
          "deck_id": "vmware_slide_01",
          "title": "Enterprise Platform of Choice: VMware - GCVE Architecture",
          "name": "VMware Slide",
      },
      {
          "deck_id": "sap_slide_01",
          "title": "Enterprise Platform of Choice: SAP on Google Cloud",
          "name": "SAP Slide",
      },
      {
          "deck_id": "db_mig_slide_01",
          "title": "Database Migration Service to Cloud SQL & Spanner",
          "name": "Migration Slide",
          "sales_play": "Migrate, Modernize, and Build with Data Cloud",
      },
      # Legitimate slides:
      {
          "deck_id": "SAMPLE_TEST_PRESENTATION_ID_000000000009",
          "title": "GenMedia Content Creation",
          "name": "GenMedia Slide",
      },
      {
          "deck_id": "cust_ref_123",
          "title": "Customer Success Case Study",
          "name": "Case Study",
          "is_cust_ref": True,
          "is_proof_point": True,
      },
  ]

  filtered = agent._filter_raw_results(
      raw_slides, customer_name="Lovable", active_context=context
  )
  filtered_deck_ids = [s.get("deck_id") for s in filtered]

  # All unrequested orthogonal sales plays and vertical leaks must be dynamically eliminated
  assert "g39a46c8b9f6_0_548" not in filtered_deck_ids
  assert "g39b153f05e0_0_4545" not in filtered_deck_ids
  assert "g3d2c57493e6_0_7" not in filtered_deck_ids
  assert "g3dac0806830_0_4631" not in filtered_deck_ids
  assert "g3f52427a1a4_0_0" not in filtered_deck_ids
  assert "vmware_slide_01" not in filtered_deck_ids
  assert "sap_slide_01" not in filtered_deck_ids
  assert "db_mig_slide_01" not in filtered_deck_ids

  # Legitimate anchor deck slide and customer reference must be retained
  assert "SAMPLE_TEST_PRESENTATION_ID_000000000009" in filtered_deck_ids
  assert "cust_ref_123" in filtered_deck_ids

  # Dynamically verify that when explicitly requested, those same plays ARE admitted
  vmware_context = dict(context)
  vmware_context["salesPlay"] = ["Enterprise Platform of Choice: VMware"]
  vmware_filtered = agent._filter_raw_results(
      raw_slides, customer_name="Lovable", active_context=vmware_context
  )
  vmware_ids = [s.get("deck_id") for s in vmware_filtered]
  assert "vmware_slide_01" in vmware_ids


def test_genmedia_cross_industry_decoupling():
  """Tests that GenMedia is treated as a cross-industry horizontal solution play.

  Verifies:
  1. A retail customer requesting GenMedia has their industry resolved to
  Retail (not Media).
  2. GenMedia slides are NOT rejected as orthogonal industry verticals for
  Retail customers.
  3. GenMedia slides are admitted when GenMedia is requested.
  4. Orthogonal vertical slides (e.g. Banking) are still rejected for Retail
  customers.
  """
  from agents.skill_loader import is_orthogonal_industry_vertical, is_orthogonal_sales_play
  from agents.workflows.foundation_deck_workflow import FoundationDeckWorkflow
  from config_loader import load_config

  workflow = FoundationDeckWorkflow(load_config())
  context = {
      "customer_name": "Nike",
      "industry": "Retail",
      "sub_industry": "Footwear & Apparel",
      "salesPlay": "GenMedia",
      "business_context": (
          "Need generative media pipeline for digital storefront asset"
          " generation"
      ),
  }

  # 1. Industry resolves to Retail
  resolved_ind = workflow.resolve_closest_industry(context)
  assert (
      "Retail" in resolved_ind
  ), f"Expected Retail cluster but got {resolved_ind}"

  # 2. GenMedia slide is NOT orthogonal to Retail
  genmedia_slide_title = "Generative Media Studio and AI Asset Pipeline"
  genmedia_metadata = {
      "title": genmedia_slide_title,
      "sales_play": "GenMedia",
      "industry": ["Cross-Industry", "Media"],
  }
  assert (
      is_orthogonal_industry_vertical(
          genmedia_slide_title, genmedia_metadata, context
      )
      is None
  )

  # 3. Banking slide IS orthogonal to Retail
  banking_slide_title = "Why Google Cloud for Core Banking & Lending"
  banking_metadata = {
      "title": banking_slide_title,
      "industry": ["Financial Services & Insurance"],
  }
  conflicting = is_orthogonal_industry_vertical(
      banking_slide_title, banking_metadata, context
  )
  assert conflicting == "Financial Services & Insurance"

  # 4. GenMedia is recognized as requested sales play
  assert (
      is_orthogonal_sales_play(genmedia_slide_title, genmedia_metadata, context)
      is None
  )


def test_gaming_vertical_rejection_for_technology_account():
  """Verifies that Gaming vertical decks and slides are strictly rejected as orthogonal
  for Technology accounts (e.g. Lovable - software engineering platform)."""
  from agents.skill_loader import is_orthogonal_industry_vertical
  from agents.workflows.foundation_deck_workflow import FoundationDeckWorkflow
  from config_loader import load_config

  lovable_context = {
      "customer_name": "Lovable",
      "industry": "Technology",
      "sub_industry": "Developer Tools",
      "business_context": "Vibe coding AI platform for full stack web development",
  }

  games_deck_title = "Why Google Cloud for Games (games_ebc_pitch) (pt)"
  games_metadata = {
      "title": games_deck_title,
      "industry": ["Media & Entertainment", "Gaming"],
      "deck_id": "SAMPLE_TEST_PRESENTATION_ID_000000000008",
  }

  # 1. is_orthogonal_industry_vertical must flag the gaming deck as orthogonal
  conflicting = is_orthogonal_industry_vertical(
      games_deck_title, games_metadata, lovable_context
  )
  assert conflicting is not None, "Gaming deck must be rejected as orthogonal for Technology account"
  assert "Gaming" in conflicting or "Media" in conflicting

  # 2. FoundationDeckWorkflow must score affinity as -100.0 (strictly rejected)
  workflow = FoundationDeckWorkflow(load_config())
  affinity = workflow.evaluate_deck_affinity(
      games_metadata,
      target_play="Why Google Cloud (Technology)",
      context=lovable_context,
      is_technical=False,
  )
  assert affinity == -100.0, f"Expected affinity -100.0 for orthogonal gaming deck, got {affinity}"


def test_anchor_deck_orthogonal_vertical_exclusion():
  """Verifies that RetrievalAgent does NOT blindly bypass orthogonal vertical checks
  even if a slide deck ID is listed in anchor_deck_ids."""
  from agents.retrieval_agent import RetrievalAgent
  from config_loader import load_config

  agent = RetrievalAgent(load_config())
  context = {
      "customer_name": "Lovable",
      "industry": "Technology",
      "sub_industry": "Developer Tools",
      "anchor_deck_ids": ["SAMPLE_TEST_PRESENTATION_ID_000000000008"],
  }

  raw_slides = [
      {
          "deck_id": "SAMPLE_TEST_PRESENTATION_ID_000000000008",
          "title": "Why Google Cloud for Games (games_ebc_pitch) (pt)",
          "name": "We have led AI for Games since the beginning",
          "industry": ["Gaming"],
      }
  ]

  filtered = agent._filter_raw_results(
      raw_slides, customer_name="Lovable", active_context=context
  )
  assert len(filtered) == 0, "Orthogonal gaming slide in anchor deck must be filtered out"


def test_retrieval_slide_job_gating_for_realization():
  """Verifies that RetrievalAgent strictly disqualifies Market_Trends / Why_Google_Cloud
  slides from Realization (Next Steps / Roadmap) agendas."""
  from agents.retrieval_agent import RetrievalAgent
  from config_loader import load_config

  agent = RetrievalAgent(load_config())

  # Check that Market_Trends or Why_Google_Cloud are not accepted into Realization
  market_trends_slide = {
      "title": "We have led AI for Games since the beginning",
      "desc": "AlphaGo, AlphaStar, and GameNGen history of research in gaming",
      "slide_job": "Market_Trends",
  }
  classified_job = agent.classify_slide_job(market_trends_slide, "Lovable")
  assert classified_job in ("Market_Trends", "Why_Google_Cloud", "Solution_Overview")

  # Verify CVI_DISALLOWED_JOBS rule for Realization
  disallowed_for_realization = {
      "Market_Trends", "Current_State", "Why_Google_Cloud", "Vision",
      "Solution_Overview", "Architecture", "Proof_Points", "Strategic_Partnership"
  }
  assert classified_job in disallowed_for_realization, (
      f"Job '{classified_job}' must be in disallowed set for Realization agendas"
  )


def test_closing_section_roadmap_final_positioning():
  """Verifies that in get_final_content, any reusable slide in a closing/realization
  section is ordered before the synthetic Joint Implementation Roadmap."""
  from agents.slide_engineering_agent import get_final_content

  class MockItem:
    title = "Executive Proposal for Lovable"

  mapped_slides = {
      "5": {
          "slides": {
              "1": {
                  "temp_url": "https://docs.google.com/presentation/d/template/edit#slide=id.p1",
                  "placeholders": {"title": "Joint Implementation Roadmap"},
              }
          }
      }
  }

  agendas = {
      "1": {"title": "Context & Challenge"},
      "2": {"title": "Solution Architecture"},
      "3": {"title": "Agentic Platform"},
      "4": {"title": "Customer Proof Points"},
      "5": {"title": "Next Steps & Implementation Roadmap"},
  }

  reusable_slides = {
      "5": {
          "suggestions": [
              {
                  "name": "Cloud Adoption Framework Governance",
                  "original_title": "Cloud Adoption Framework Governance",
                  "slide_job": "Path_to_Prod",
              }
          ]
      }
  }

  final_struct = get_final_content(
      item=MockItem(),
      place_holders=mapped_slides,
      agendas=agendas,
      reusable_slides=reusable_slides,
      sources={},
  )

  # Check that intertwined_order for the reusable slide is 0 (preceding the roadmap)
  sug = reusable_slides["5"]["suggestions"][0]
  assert sug["intertwined_order"] == 0, (
      f"Expected intertwined_order 0 for reusable slide in closing section, got {sug['intertwined_order']}"
  )


def test_cvi_and_slide_job_cluster_retrieval():
  """Verifies that RetrievalAgent preserves complete intra-deck slide clusters
  sharing the same CVI cluster and valid slide jobs, rather than arbitrarily
  truncating them, while strictly excluding slides with mismatched CVI stages."""
  from agents.retrieval_agent import RetrievalAgent
  from config_loader import load_config

  agent = RetrievalAgent(load_config())

  class MockState:
    agendas = {
        "1": {
            "title": "Intelligent Platform & Architecture",
            "parts": ["Gemini Enterprise Agent Platform", "AI Hypercomputer"],
        }
    }
    context = {
        "customer_name": "Lovable",
        "industry": "Technology",
    }
    reusable_slides = {}

  deck_id = "deck_gemini_platform_123"
  candidates = [
      {
          "deck_id": deck_id,
          "slide_id": "slide_1",
          "name": "Gemini Enterprise Agent Platform Overview",
          "cvi_cluster": "Vision",
          "slide_job": "Solution_Overview",
          "sim_score": 0.85,
      },
      {
          "deck_id": deck_id,
          "slide_id": "slide_2",
          "name": "Agent Engine Runtime Architecture",
          "cvi_cluster": "Vision",
          "slide_job": "Architecture",
          "sim_score": 0.75,
      },
      {
          "deck_id": deck_id,
          "slide_id": "slide_3",
          "name": "Model Serving & Context Pipelines",
          "cvi_cluster": "Vision",
          "slide_job": "Solution_Overview",
          "sim_score": 0.70,
      },
      {
          "deck_id": deck_id,
          "slide_id": "slide_4",
          "name": "Enterprise Security & Isolation Boundary",
          "cvi_cluster": "Vision",
          "slide_job": "Architecture",
          "sim_score": 0.68,
      },
      {
          "deck_id": deck_id,
          "slide_id": "slide_5",
          "name": "Market Trends in AI Development",
          "cvi_cluster": "Context",
          "slide_job": "Market_Trends",
          "sim_score": 0.78,
      },
      {
          "deck_id": deck_id,
          "slide_id": "slide_6",
          "name": "Customer Reference Spotlight: Spotify",
          "cvi_cluster": "Impact",
          "slide_job": "Proof_Points",
          "is_cust_ref": True,
          "sim_score": 0.80,
      },
  ]

  class MockScorer:
    def execute(self, query, raw_results, section_metadata=None):
      return list(candidates)

  agent.skills["score"] = MockScorer()

  state = MockState()
  agent.retrieve_reusable_slides(state)

  section_sugs = state.reusable_slides.get("1", {}).get("suggestions", [])
  sug_names = [s.get("name") for s in section_sugs]

  # Verify the 4 Vision slides from the cluster are ALL retrieved without arbitrary truncation
  assert len(section_sugs) == 4, f"Expected 4 slides in cluster, got {len(section_sugs)}: {sug_names}"
  assert "Gemini Enterprise Agent Platform Overview" in sug_names
  assert "Agent Engine Runtime Architecture" in sug_names
  assert "Model Serving & Context Pipelines" in sug_names
  assert "Enterprise Security & Isolation Boundary" in sug_names

  # Verify the mismatched CVI slide and case study were excluded
  assert "Market Trends in AI Development" not in sug_names
  assert "Customer Reference Spotlight: Spotify" not in sug_names


def test_resolve_required_sales_plays_multi_play():
  from agents.skill_loader import resolve_required_sales_plays

  # Test case 1: Dropdown contains GenMedia, Prompt mentions Gemini Enterprise
  context_1 = {
      "salesPlay": "Leverage Generative Media in Your Business",
      "user_request": "We need to empower employees with Gemini Enterprise agents and creative workflows.",
      "business_context": "We need to empower employees with Gemini Enterprise agents and creative workflows.",
  }
  plays_1 = resolve_required_sales_plays(context_1)
  assert "Leverage Generative Media in Your Business" in plays_1
  assert any("Agentic Workplace Transformation" in p for p in plays_1)
  assert len(plays_1) == 2

  # Test case 2: List of sales plays provided in dropdown
  context_2 = {
      "salesPlay": [
          "Scale AI Apps and Agents",
          "Agentic Workplace Transformation",
      ],
      "business_context": "Scaling enterprise AI assistants.",
  }
  plays_2 = resolve_required_sales_plays(context_2)
  assert "Scale AI Apps and Agents" in plays_2
  assert "Lead the Agentic Workplace Transformation" in plays_2

  # Test case 3: String with multiple comma-separated sales plays
  context_3 = {
      "sales_plays": "GenMedia, Security",
      "business_context": "Media production and SOC resilience.",
  }
  plays_3 = resolve_required_sales_plays(context_3)
  assert "Leverage Generative Media in Your Business" in plays_3
  assert any("Security" in p or "Defense" in p for p in plays_3)


def test_retrieval_agent_multi_anchor_guarantee():
  from agents.retrieval_agent import RetrievalAgent
  from config_loader import load_config

  agent = RetrievalAgent(load_config())
  deck_1 = "deck_genmedia_111"
  deck_2 = "deck_gemini_enterprise_222"

  class MockState:
    def __init__(self):
      self.agendas = {
          "1": {
              "title": "Creative Innovation with GenMedia",
              "parts": ["GenMedia workflows on agent platform"],
          }
      }
      self.context = {
          "customer_name": "Globex",
          "anchor_decks": [
              {
                  "deck_id": deck_1,
                  "deck_title": "GenMedia on Agent Platform Business Pitch (pt)",
                  "sales_play": "Leverage Generative Media in Your Business",
              },
              {
                  "deck_id": deck_2,
                  "deck_title": "Agentic Workplace Transformation Business Pitch Deck (pt)",
                  "sales_play": "Lead the Agentic Workplace Transformation",
              },
          ],
          "anchor_deck_ids": [deck_1, deck_2],
      }
      self.reusable_slides = {}

  # Candidate slides initially only returned from deck_1
  initial_slides = [
      {
          "deck_id": deck_1,
          "slide_id": "gm_slide_1",
          "name": "GenMedia Studio Overview",
          "cvi_cluster": "Vision",
          "slide_job": "Solution_Overview",
          "sim_score": 0.85,
      }
  ]

  class MockScorer:
    def execute(self, query, raw_results, section_metadata=None):
      return list(initial_slides)

  agent.skills["score"] = MockScorer()

  # Mock the slide retriever factory for the multi-anchor guarantee
  from agents.workflows.slide_retriever_factory import SlideRetrieverFactory

  class MockDedicatedRetriever:
    def search_slides(self, query, recovery_context, limit=5):
      sec_id = recovery_context.get("section_anchor_deck_id")
      return [
          {
              "deck_id": sec_id,
              "slide_id": "ge_slide_1",
              "name": "Gemini Enterprise Overview",
              "cvi_cluster": "Vision",
              "slide_job": "Solution_Overview",
              "sim_score": 0.85,
          }
      ]

  orig_get_retriever = SlideRetrieverFactory.get_retriever
  SlideRetrieverFactory.get_retriever = staticmethod(
      lambda key, ds, cfg: MockDedicatedRetriever()
  )

  try:
    state = MockState()
    agent.retrieve_reusable_slides(state)

    # Verify both anchor decks are represented in the final suggestions
    represented_decks = set()
    for sec_data in state.reusable_slides.values():
      for sug in sec_data.get("suggestions", []):
        represented_decks.add(sug.get("deck_id"))

    assert deck_1 in represented_decks, "Deck 1 (GenMedia) should be represented"
    assert deck_2 in represented_decks, "Deck 2 (Gemini Enterprise) must be guaranteed by Multi-Anchor Review"
  finally:
    SlideRetrieverFactory.get_retriever = orig_get_retriever


def test_workspace_isolation_and_anchor_protection():
  from agents.skill_loader import (
      is_workspace_explicitly_requested,
      resolve_required_sales_plays,
      is_orthogonal_sales_play,
  )
  from agents.retrieval_agent import RetrievalAgent
  from config_loader import load_config

  # 1. Test is_workspace_explicitly_requested
  ctx_no_ws = {
      "user_request": "Build a GenMedia and Gemini Enterprise pitch for Disney",
      "business_context": "Transform media production workflows with AI",
  }
  assert is_workspace_explicitly_requested(ctx_no_ws) is False

  ctx_ws_prompt = {
      "user_request": "Build a Google Workspace AI pitch for Disney",
  }
  assert is_workspace_explicitly_requested(ctx_ws_prompt) is True

  ctx_ws_play = {
      "user_request": "Enterprise pitch for Disney",
      "salesPlay": ["Lead the Agentic Workplace Transformation - Google Workspace"],
  }
  assert is_workspace_explicitly_requested(ctx_ws_play) is True

  # 2. Test resolve_required_sales_plays does not pull Workspace without explicit request
  detected_plays = resolve_required_sales_plays(ctx_no_ws)
  play_names = [(p["name"] if isinstance(p, dict) else p) for p in detected_plays]
  assert any("Agentic Workplace" in name for name in play_names)
  assert any("Generative Media" in name for name in play_names)
  assert not any("Google Workspace" in name for name in play_names)

  # 3. Test is_orthogonal_sales_play
  # Workspace deck should be rejected as orthogonal when Workspace is unrequested
  ws_deck_title = "[FINAL] Google Workspace AI For Every Business - M&E Business Pitch"
  assert is_orthogonal_sales_play(ws_deck_title, active_context=ctx_no_ws) == "Google Workspace"

  # Why Google Cloud foundation decks are exempt
  mne_ebc_deck = "why google cloud for media & entertainment [media_ebc_pitch] (pt)"
  assert is_orthogonal_sales_play(mne_ebc_deck, active_context=ctx_no_ws) is None

  # 4. Test anchor deck protection in RetrievalAgent._filter_raw_results
  agent = RetrievalAgent(load_config())
  tech_anchor_slide = {
      "deck_id": "genmedia_tech_deck_id",
      "deck_title": "GenMedia - Tech Pitch Deck (pt)",
      "title": "GenMedia Architecture",
      "content": "Generative media technical capabilities",
  }
  # Active anchor deck context
  recovery_ctx = {
      "anchor_deck_ids": ["genmedia_tech_deck_id"],
      "user_request": "Build a GenMedia pitch for Disney",
  }
  filtered = agent._filter_raw_results(
      [tech_anchor_slide],
      customer_name="Disney",
      active_context=recovery_ctx,
  )
  assert len(filtered) == 1
  assert filtered[0]["deck_id"] == "genmedia_tech_deck_id"


def test_segment_gating_corporate_and_smb():
  from agents.workflows.foundation_deck_workflow import FoundationDeckWorkflow
  from agents.retrieval_agent import RetrievalAgent
  from config_loader import load_config
  wf = FoundationDeckWorkflow(load_config())
  agent = RetrievalAgent(load_config())

  corp_deck = {
      "deck_id": "corp_play_1",
      "title": "[Corporate] Agentic Workplace Transformation Business Pitch Deck (pt)",
  }
  smb_deck = {
      "deck_id": "smb_play_1",
      "title": "[SMB] Agentic Workplace Transformation Business Pitch Deck (pt)",
  }
  ent_deck = {
      "deck_id": "ent_play_1",
      "title": "Agentic Workplace Transformation Business Pitch Deck (pt)",
  }

  # 1. Corporate Segment
  ctx_corp = {"segment": "Corporate", "salesPlay": ["Lead the Agentic Workplace Transformation"]}
  assert wf.resolve_active_segment(ctx_corp) == "Corporate"
  score_corp = wf.evaluate_deck_affinity(corp_deck, "Lead the Agentic Workplace Transformation", ctx_corp, False)
  score_smb_under_corp = wf.evaluate_deck_affinity(smb_deck, "Lead the Agentic Workplace Transformation", ctx_corp, False)
  score_ent_under_corp = wf.evaluate_deck_affinity(ent_deck, "Lead the Agentic Workplace Transformation", ctx_corp, False)

  assert score_corp > 0, "Corporate deck should have positive affinity for Corporate customer"
  assert score_smb_under_corp == -100.0, "SMB deck must be disqualified for Corporate customer"
  assert score_corp > score_ent_under_corp, "Corporate deck should score higher than generic enterprise deck for Corporate"

  # 2. SMB Segment
  ctx_smb = {"segment": "SMB", "salesPlay": ["Lead the Agentic Workplace Transformation"]}
  assert wf.resolve_active_segment(ctx_smb) == "SMB"
  score_smb = wf.evaluate_deck_affinity(smb_deck, "Lead the Agentic Workplace Transformation", ctx_smb, False)
  score_corp_under_smb = wf.evaluate_deck_affinity(corp_deck, "Lead the Agentic Workplace Transformation", ctx_smb, False)
  assert score_smb > 0, "SMB deck should have positive affinity for SMB customer"
  assert score_corp_under_smb == -100.0, "Corporate deck must be disqualified for SMB customer"

  # 3. Enterprise Segment
  ctx_ent = {"segment": "Enterprise", "salesPlay": ["Lead the Agentic Workplace Transformation"]}
  assert wf.resolve_active_segment(ctx_ent) == "Enterprise"
  score_corp_under_ent = wf.evaluate_deck_affinity(corp_deck, "Lead the Agentic Workplace Transformation", ctx_ent, False)
  score_smb_under_ent = wf.evaluate_deck_affinity(smb_deck, "Lead the Agentic Workplace Transformation", ctx_ent, False)
  assert score_corp_under_ent == -100.0, "Corporate deck must be disqualified for Enterprise customer"
  assert score_smb_under_ent == -100.0, "SMB deck must be disqualified for Enterprise customer"

  # 4. Slide-level gating in RetrievalAgent._filter_raw_results
  corp_slide = {"deck_title": "[Corporate] Agentic Workplace Transformation Business Pitch Deck (pt)", "name": "Slide 1"}
  smb_slide = {"deck_title": "[SMB] Agentic Workplace Transformation Business Pitch Deck (pt)", "name": "Slide 1"}
  ent_slide = {"deck_title": "Agentic Workplace Transformation Business Pitch Deck (pt)", "name": "Slide 1"}

  # Filtered for Enterprise customer
  res_ent = agent._filter_raw_results([corp_slide, smb_slide, ent_slide], customer_name="Acme", active_context=ctx_ent)
  assert len(res_ent) == 1
  assert res_ent[0]["deck_title"] == ent_slide["deck_title"]

  # Filtered for Corporate customer
  res_corp = agent._filter_raw_results([corp_slide, smb_slide, ent_slide], customer_name="Acme", active_context=ctx_corp)
  assert any(r["deck_title"] == corp_slide["deck_title"] for r in res_corp)
  assert not any(r["deck_title"] == smb_slide["deck_title"] for r in res_corp)


def test_win_cycle_stage_steering():
  from agents.workflows.foundation_deck_workflow import FoundationDeckWorkflow
  from config_loader import load_config
  wf = FoundationDeckWorkflow(load_config())

  tech_deck = {
      "deck_id": "tech_deck_1",
      "title": "Migrate, Modernize, and Build with Data Cloud Technical Pitch (L200/L300)",
  }
  biz_deck = {
      "deck_id": "biz_deck_1",
      "title": "Migrate, Modernize, and Build with Data Cloud Business Pitch Deck",
  }
  play = "Migrate, Modernize, and Build with Data Cloud"

  # S2: Tech Solutioning -> prefers Technical Pitch
  ctx_s2 = {"sales_stage": "S2: Tech Solutioning (S2)", "segment": "Enterprise"}
  score_tech_s2 = wf.evaluate_deck_affinity(tech_deck, play, ctx_s2, is_technical=True)
  score_biz_s2 = wf.evaluate_deck_affinity(biz_deck, play, ctx_s2, is_technical=True)
  assert score_tech_s2 > score_biz_s2, "S2 stage should favor technical pitch"

  # S1: Position & Build -> prefers Business Pitch
  ctx_s1 = {"sales_stage": "S1: Position & Build (S1)", "segment": "Enterprise"}
  score_tech_s1 = wf.evaluate_deck_affinity(tech_deck, play, ctx_s1, is_technical=False)
  score_biz_s1 = wf.evaluate_deck_affinity(biz_deck, play, ctx_s1, is_technical=False)
  assert score_biz_s1 > score_tech_s1, "S1 stage should favor business pitch"

  # Seller prompt override: S2 but seller explicitly asks for business pitch
  ctx_s2_biz_prompt = {
      "sales_stage": "S2",
      "user_request": "Give me an executive business pitch deck for our CIO",
      "segment": "Enterprise",
  }
  score_biz_override = wf.evaluate_deck_affinity(biz_deck, play, ctx_s2_biz_prompt, is_technical=False)
  score_tech_override = wf.evaluate_deck_affinity(tech_deck, play, ctx_s2_biz_prompt, is_technical=False)
  assert score_biz_override > score_tech_override, "Explicit business prompt should override S2 stage default"


def test_concept_c_dual_anchor_architecture():
  from agents.workflows.foundation_deck_workflow import FoundationDeckWorkflow
  from agents.retrieval_agent import RetrievalAgent
  from config_loader import load_config
  wf = FoundationDeckWorkflow(load_config())
  agent = RetrievalAgent(load_config())

  vertical_deck = {
      "deck_id": "v_deck_retail",
      "deck_title": "Why Google Cloud for Retail & Consumer (pt)",
      "sales_play": "Why Google Cloud (Retail & Consumer)",
      "source_datastore": "sales_play_reusables",
  }
  sol_deck_1 = {
      "deck_id": "sol_deck_gm",
      "deck_title": "GenMedia on Agent Platform Business Pitch (pt)",
      "sales_play": "Leverage Generative Media in Your Business",
      "source_datastore": "sales_play_reusables",
  }
  sol_deck_2 = {
      "deck_id": "sol_deck_ge",
      "deck_title": "Agentic Workplace Transformation Business Pitch Deck (pt)",
      "sales_play": "Lead the Agentic Workplace Transformation",
      "source_datastore": "sales_play_reusables",
  }

  sec_context = {
      "vertical_anchor": vertical_deck,
      "solution_anchors": [sol_deck_1, sol_deck_2],
      "anchor_decks": [vertical_deck, sol_deck_1, sol_deck_2],
      "anchor_deck_ids": [vertical_deck["deck_id"], sol_deck_1["deck_id"], sol_deck_2["deck_id"]],
  }

  # Agenda 1 (Context / Why Google) must bind to vertical_anchor
  agenda_1 = {"title": "Strategic Context & Industry Trends", "parts": ["Market dynamics in Retail", "Why Google Cloud for Retail"]}
  meta_1 = agent._extract_section_metadata(agenda_1, sec_context)
  assert meta_1["section_anchor_deck_id"] == vertical_deck["deck_id"], "Agenda 1 should bind to vertical anchor"

  # Agenda 2 (GenMedia Solution) must bind to GenMedia solution_anchor
  agenda_2 = {"title": "Leveraging Generative Media for Content Creation", "parts": ["GenMedia studio", "Creative workflows"]}
  meta_2 = agent._extract_section_metadata(agenda_2, sec_context)
  assert meta_2["section_anchor_deck_id"] == sol_deck_1["deck_id"], "GenMedia agenda should bind to GenMedia solution anchor"

  # Agenda 3 (Agentic Workplace) must bind to Agentic Workplace solution_anchor
  agenda_3 = {"title": "Transforming the Workplace with Agentic AI", "parts": ["Workplace productivity", "Gemini Enterprise"]}
  meta_3 = agent._extract_section_metadata(agenda_3, sec_context)
  assert meta_3["section_anchor_deck_id"] == sol_deck_2["deck_id"], "Workplace agenda should bind to Workplace solution anchor"


def test_geometry_aware_char_budget_and_multiline_preservation():
  from agents.workflows.text_transformer_workflow import TextTransformerWorkflow
  from config_loader import load_config

  wf = TextTransformerWorkflow(load_config())

  # 1. Narrow left-column title (width_pt=288pt, fontSize=28pt) -> capped <= 36 chars
  t_narrow, m_narrow = wf._compute_char_budget(
      14,
      font_size=28.0,
      is_action_title=True,
      width_pt=288.0,
      clearance_pt=68.0,
  )
  assert (
      m_narrow <= 54
  ), f"Narrow column title max_chars should be <= 54, got {m_narrow}"
  assert t_narrow >= 18

  # 2. Wide header title (width_pt=592pt, fontSize=28pt) -> expands short template title to 48-68 chars
  t_wide, m_wide = wf._compute_char_budget(
      19,
      font_size=28.0,
      is_action_title=True,
      width_pt=592.0,
      clearance_pt=90.0,
  )
  assert (
      48 <= m_wide <= 68
  ), f"Wide header title max_chars should be 48-68, got {m_wide}"

  # 3. Short UI pill ("Example use case", 16 chars) inside >=110pt box -> allows up to 22 chars ("Semiconductor use case")
  _, m_pill = wf._compute_char_budget(
      16, font_size=10.5, is_action_title=False, width_pt=135.0
  )
  assert m_pill >= 22
  sanitized_pill = wf._sanitize_output(
      "Semiconductor use case",
      is_cover_slide=False,
      customer_name="Intel",
      original_len=16,
      is_action_title=False,
      font_size=10.5,
      width_pt=135.0,
  )
  assert sanitized_pill == "Semiconductor use case"

  # 4. Multi-bullet shape with 18pt lead paragraph + 4 bullet lines (Slide 17 bug) must NEVER collapse newlines
  orig_multiline = (
      "Agents that handle complex, mission-critical tasks\nSpecialized agents"
      " for data science, software development, and customer"
      " engagement\nSupports complex, multi-step workflows\nAccelerates"
      " time-to-value for high-priority use cases\nBuilt-in governance and"
      " enterprise security controls"
  )
  candidate_multiline = (
      "Agents that accelerate complex silicon engineering tasks\nSpecialized"
      " agents for RTL verification, yield analysis, and fab"
      " automation\nSupports multi-step design-to-manufacturing workflows"
      " across global fabs\nAccelerates time-to-yield for 18A process nodes and"
      " foundry customers\nBuilt-in IP protection and enterprise security"
      " controls"
  )
  sanitized_multi = wf._sanitize_output(
      candidate_multiline,
      is_cover_slide=False,
      customer_name="Intel",
      original_len=len(orig_multiline),
      is_action_title=False,
      font_size=18.0,
  )
  assert sanitized_multi.count("\n") == 4, (
      "Expected 4 newlines preserved across 5 paragraphs, got"
      f" {sanitized_multi.count(chr(10))}: {sanitized_multi!r}"
  )

  # 5. _select_primary_title_idx must pick top TITLE placeholder over bulleted 18pt body box (Slide 14 bug)
  slide14_shapes = [
      {
          "shapeId": "title_3189",
          "text": "Agent orchestration",
          "fontSize": 28.0,
          "y_pt": 23.5,
          "width_pt": 591.7,
          "height_pt": 42.0,
          "has_bullets": False,
          "placeholder_type": "TITLE",
      },
      {
          "shapeId": "body_3190",
          "text": (
              "Seamlessly routes user requests across agents\nSupports complex"
              " multi-step tasks"
          ),
          "fontSize": 18.0,
          "y_pt": 92.6,
          "width_pt": 288.4,
          "height_pt": 248.0,
          "has_bullets": True,
          "placeholder_type": "OBJECT",
      },
  ]
  assert wf._select_primary_title_idx(slide14_shapes) == 0
