import json
import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src"))
)

from agents.skill_loader import is_workspace_explicitly_requested, is_orthogonal_sales_play
from agents.retrieval_agent import RetrievalAgent
from agents.workflows.outline_workflow import OutlineWorkflow
from pitchgen_utils.image_util import extract_customizable_slide_pictures


class TestHsbcDeckFixes(unittest.TestCase):

  def test_detect_sales_play_replaces_workspace_with_gemini_enterprise(self):
    wf = OutlineWorkflow.__new__(OutlineWorkflow)
    wf.config = {"default": {"gemini_model": "gemini-3.8-flash"}}
    wf.fast_model = "gemini-3.8-flash"
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = json.dumps({
        "detected_plays": [
            "Lead the Agentic Workplace Transformation - Google Workspace",
            "Become an Autonomous Agent-Powered Enterprise",
            "Win with the Agentic Data Fabric",
        ]
    })
    mock_client.models.generate_content.return_value = mock_resp

    hsbc_context = (
        "Generate a pitch for HSBC about Agentic banking at HSBC. "
        "Focus on Gemini Enterprise, ADK, Model Armor, and AI Markets."
    )
    plays = wf.detect_sales_play(mock_client, hsbc_context, {})
    self.assertNotIn(
        "Lead the Agentic Workplace Transformation - Google Workspace",
        plays,
    )
    self.assertIn(
        "Lead the Agentic Workplace Transformation - Gemini Enterprise",
        plays,
    )

  def test_workspace_not_self_authorized_by_llm_inferred_sales_plays(self):
    session_state = {
        "business_context": (
            "Agentic banking at HSBC with Gemini Enterprise and BigQuery"
        ),
        "sales_plays": [
            "Lead the Agentic Workplace Transformation - Google Workspace",
            "Become an Autonomous Agent-Powered Enterprise",
        ],
    }
    self.assertFalse(is_workspace_explicitly_requested(session_state))

    # Verify is_orthogonal_sales_play catches the Google Workspace Pitch Deck slide
    ws_candidate = {
        "deck_id": "SAMPLE_TEST_PRESENTATION_ID_000000000010",
        "slide_id": "g3d3ec39e5d1_0_17561",
        "sales_play": (
            "Lead the Agentic Workplace Transformation - Google Workspace"
        ),
        "slide_or_deck_title": "Google Workspace Pitch Deck (2026)",
        "content": (
            "The slide outlines a conceptual vision within Google Workspace."
        ),
    }
    self.assertIsNotNone(
        is_orthogonal_sales_play(
            slide_or_deck_title=ws_candidate["slide_or_deck_title"],
            slide_metadata=ws_candidate,
            active_context=session_state,
        )
    )

  def test_retrieval_filter_rejects_workspace_and_description_placeholders(
      self,
  ):
    agent = RetrievalAgent.__new__(RetrievalAgent)
    agent.name = "RetrievalAgent"
    session_state = {
        "business_context": "Agentic banking at HSBC with Gemini Enterprise",
        "sales_plays": [
            "Become an Autonomous Agent-Powered Enterprise",
            "Win with the Agentic Data Fabric",
        ],
    }
    raw_results = [
        {
            "deck_id": "SAMPLE_TEST_PRESENTATION_ID_000000000010",
            "slide_id": "g3d3ec39e5d1_0_17561",
            "sales_play": (
                "Lead the Agentic Workplace Transformation - Google Workspace"
            ),
            "slide_or_deck_title": "Google Workspace Pitch Deck (2026)",
            "name": "The slide outlines a conceptual vision",
            "content": (
                "Shared enterprise-wide context Description Common user"
                " interfaces Description Unified agent orchestration"
                " Description"
            ),
        },
        {
            "deck_id": "SAMPLE_TEST_PRESENTATION_ID_000000000011",
            "slide_id": "g3d89b5ae8bb_28_3503",
            "sales_play": "Become an Autonomous Agent-Powered Enterprise",
            "slide_or_deck_title": "Agentic Enterprise Foundation",
            "name": "Google Cloud AI platform benefits",
            "content": (
                "Innovation without lock-in through Model Garden and"
                " Provisioned Throughput."
            ),
        },
    ]
    filtered = agent._filter_raw_results(
        raw_results,
        customer_name="HSBC",
        active_context=session_state,
    )
    slide_ids = [r.get("slide_id") for r in filtered]
    self.assertNotIn("g3d3ec39e5d1_0_17561", slide_ids)
    self.assertIn("g3d89b5ae8bb_28_3503", slide_ids)

  def test_demonstrated_customer_impact_classified_as_proof_points(self):
    agent = RetrievalAgent.__new__(RetrievalAgent)
    agent.name = "RetrievalAgent"
    sec_val = {
        "title": "Demonstrated Customer Impact",
        "parts": [
            "Show how leading financial institutions achieve measurable ROI"
            " with Google Cloud."
        ],
    }
    meta = agent._extract_section_metadata(sec_val, {})
    self.assertIn("Proof_Points", meta["expected_slide_jobs"])
    self.assertEqual(meta["expected_cvi_cluster"], "Impact")

  def test_cited_stats_slide_allows_picture_customization(self):
    slide = {
        "objectId": "SLIDES_API1859781567_161",
        "pageElements": [
            {
                "objectId": "SLIDES_API1859781567_162",
                "shape": {
                    "shapeType": "TEXT_BOX",
                    "text": {
                        "textElements": [{
                            "textRun": {
                                "content": (
                                    "49% of FSI executives will allocate 50%+"
                                    " of their future AI budget to AI"
                                    " agents\nSource: Google Cloud / NRG, 2025"
                                    " ROI of AI Report"
                                )
                            }
                        }]
                    },
                },
                "size": {
                    "width": {"magnitude": 300 * 12700, "unit": "EMU"},
                    "height": {"magnitude": 100 * 12700, "unit": "EMU"},
                },
                "transform": {
                    "scaleX": 1.0,
                    "scaleY": 1.0,
                    "translateX": 18.0 * 12700,
                    "translateY": 298.0 * 12700,
                    "unit": "EMU",
                },
            },
            {
                "objectId": "SLIDES_API1859781567_163",
                "image": {"contentUrl": "https://example.com/stat_graphic.png"},
                "size": {
                    "width": {"magnitude": 287.0 * 12700, "unit": "EMU"},
                    "height": {"magnitude": 281.8 * 12700, "unit": "EMU"},
                },
                "transform": {
                    "scaleX": 1.0,
                    "scaleY": 1.0,
                    "translateX": 416.0 * 12700,
                    "translateY": 20.0 * 12700,
                    "unit": "EMU",
                },
            },
        ],
    }
    pics = extract_customizable_slide_pictures(
        slide, slide_index=3, is_cust_ref_slide=False
    )
    self.assertEqual(len(pics), 1)
    self.assertEqual(pics[0]["objectId"], "SLIDES_API1859781567_163")

  def test_google_brand_voice_degerunding_and_gate06_fatigue(self):
    from agents.workflows.text_transformer_workflow import TextTransformerWorkflow
    from evals.deck_perfection_inspector import DeckPerfectionInspector, GERUND_OPENER_WORDS

    # 1. Verify _normalize_consultative_action_title converts -ing gerund openers to active voice / noun phrases
    wf = TextTransformerWorkflow.__new__(TextTransformerWorkflow)
    hsbc_gerunds = [
        "Reimagining global banking with autonomous agents",
        "Elevating institutional client interactions and risk operations",
        "Scaling open, interoperable agentic banking workflows",
        "Uniting Alphabet AI innovation with HSBC global scale",
        "Activating an agentic data fabric across 169PB on BigQuery",
        "Orchestrating faster risk simulations and trade synthesis",
        "Establishing joint governance and a phased path to production",
    ]
    for raw_hl in hsbc_gerunds:
      normalized = wf._normalize_consultative_action_title(raw_hl)
      first_word = normalized.split()[0].lower().strip(",.:;")
      self.assertNotIn(
          first_word,
          GERUND_OPENER_WORDS,
          f"Expected '{raw_hl}' to be de-gerunded, got '{normalized}'",
      )

    # Verify specific structural rewrites
    self.assertEqual(
        wf._normalize_consultative_action_title(
            "Uniting Alphabet AI innovation with HSBC global scale"
        ),
        "Alphabet AI innovation meets HSBC global scale",
    )
    self.assertEqual(
        wf._normalize_consultative_action_title(
            "Reimagining global banking with autonomous agents"
        ),
        "Autonomous agents transform global banking",
    )
    self.assertEqual(
        wf._normalize_consultative_action_title(
            "Turning fragmented data into real-time insight"
        ),
        "From fragmented data to real-time insight",
    )

    # 2. Verify DeckPerfectionInspector Gate 06 flags >= 3 gerund openers
    inspector = DeckPerfectionInspector()

    def _make_headline_slide(idx: int, title_text: str):
      return (
          idx,
          {
              "objectId": f"s_{idx}",
              "pageElements": [{
                  "objectId": f"s_{idx}_t",
                  "size": {
                      "width": {"magnitude": 600 * 12700, "unit": "EMU"},
                      "height": {"magnitude": 40 * 12700, "unit": "EMU"},
                  },
                  "transform": {
                      "scaleX": 1.0,
                      "scaleY": 1.0,
                      "translateX": 36 * 12700,
                      "translateY": 24 * 12700,
                      "unit": "EMU",
                  },
                  "shape": {
                      "shapeType": "TEXT_BOX",
                      "text": {
                          "textElements": [{
                              "textRun": {
                                  "content": title_text,
                                  "style": {
                                      "fontSize": {
                                          "magnitude": 26.0,
                                          "unit": "PT",
                                      }
                                  },
                              }
                          }]
                      },
                  },
              }],
          },
      )

    bad_slides = [
        _make_headline_slide(
            2, "Reimagining global banking with autonomous agents"
        ),
        _make_headline_slide(3, "Elevating institutional client interactions"),
        _make_headline_slide(
            4, "Uniting Alphabet AI innovation with HSBC scale"
        ),
    ]
    g06_bad = inspector._gate_06_consultative_sentence_case_titles(bad_slides)
    self.assertFalse(g06_bad.passed)
    self.assertTrue(
        any("gerund opener fatigue" in v for v in g06_bad.violations)
    )


if __name__ == "__main__":
  unittest.main()
