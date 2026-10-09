"""Unit tests for Golden Gate skills, CustomerInsightsWorkflow, and Customer Reference Library GSlides NewLibraryCustomerReferenceRetriever."""

import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")),
)

# Ensure tests can run in bare python3 as well as blaze test
try:
  from google.cloud import discoveryengine_v1  # noqa: F401
except ImportError:
  google_mod = sys.modules.setdefault("google", types.ModuleType("google"))
  cloud_mod = sys.modules.setdefault(
      "google.cloud", types.ModuleType("google.cloud")
  )
  de_mod = types.ModuleType("google.cloud.discoveryengine_v1")
  de_mod.SearchServiceClient = MagicMock()
  de_mod.SearchRequest = MagicMock()
  cloud_mod.discoveryengine_v1 = de_mod
  sys.modules["google.cloud.discoveryengine_v1"] = de_mod
  pb_mod = sys.modules.setdefault(
      "google.protobuf", types.ModuleType("google.protobuf")
  )
  jf_mod = types.ModuleType("google.protobuf.json_format")
  pb_mod.json_format = jf_mod
  sys.modules["google.protobuf.json_format"] = jf_mod

from agents.skill_loader import get_matching_skill_instructions, load_skill_instructions
from agents.workflows.customer_insights_workflow import CustomerInsightsWorkflow
from agents.workflows.customer_reference_retriever import (
    CUSTOMER_REFERENCE_MASTER_DECK_IDS,
    CUSTOMER_REF_SERVING_CONFIG,
    NewLibraryCustomerReferenceRetriever,
    _extract_gslides_url_and_ids,
)
from agents.workflows.isolated_sales_play_retriever import IsolatedSalesPlayRetriever
from agents.workflows.slide_retriever_factory import SlideRetrieverFactory


class TestGoldenGateAndNewCustRefLibrary(unittest.TestCase):

  def setUp(self):
    self.mock_config = {
        "default": {"project_name": "your-gcp-project-id"},
        "reusable": {
            "sales_play_reusables": (
                "your-sales-play-slides-datastore-id"
            ),
            "cust_ref": CUSTOMER_REF_SERVING_CONFIG,
        },
        "bucket": {"content": "your-pitchgen-content-bucket"},
    }

  def test_slide_retriever_factory_routes_cust_ref_to_customer_ref_library_retriever(self):
    retriever = SlideRetrieverFactory.get_retriever(
        "cust_ref",
        "",
        self.mock_config,
    )
    self.assertIsInstance(retriever, NewLibraryCustomerReferenceRetriever)
    self.assertEqual(retriever.datastore_id, CUSTOMER_REF_SERVING_CONFIG)

  def test_extract_gslides_url_and_ids_enforces_gslides_only(self):
    # 1. Valid customer_slide_library asset_url with explicit #slide=id.xxx
    csl_struct = {
        "asset_url": (
            "https://docs.google.com/presentation/d/"
            "SAMPLE_CUST_REF_MASTER_DECK_ID_000000001/edit"
            "?slide=id.g375d2c9bbad_1_8473#slide=id.g375d2c9bbad_1_8473"
        )
    }
    res = _extract_gslides_url_and_ids(csl_struct)
    self.assertIsNotNone(res)
    clean_url, deck_id, slide_id, has_explicit = res
    self.assertEqual(deck_id, "SAMPLE_CUST_REF_MASTER_DECK_ID_000000001")
    self.assertEqual(slide_id, "g375d2c9bbad_1_8473")
    self.assertTrue(has_explicit)
    self.assertEqual(
        clean_url,
        "https://docs.google.com/presentation/d/"
        "SAMPLE_CUST_REF_MASTER_DECK_ID_000000001/edit"
        "#slide=id.g375d2c9bbad_1_8473",
    )

    # 2. Non-GSlides URLs (blogs, YouTube, Docs, PDFs) must return None
    non_gslides_struct = {
        "asset_url": "https://cloud.google.com/customers/some-blog-post",
        "asset_urls": [
            "https://www.youtube.com/watch?v=123456",
            "https://docs.google.com/document/d/1abc12345678901234567890/edit",
        ],
    }
    self.assertIsNone(_extract_gslides_url_and_ids(non_gslides_struct))

  @patch(
      "agents.workflows.isolated_sales_play_retriever.discoveryengine.SearchServiceClient"
  )
  def test_isolated_sales_play_retriever_only_customer_refs_filter(
      self, mock_client_cls
  ):
    retriever = IsolatedSalesPlayRetriever(
        project_id="your-gcp-project-id",
        datastore_id=(
            "your-sales-play-slides-datastore-id"
        ),
    )
    f_only = retriever._build_filter_expression(
        {"only_customer_refs": True, "exclude_customer_refs": False}
    )
    self.assertEqual(f_only, 'customer_references = "true"')

    f_proof = retriever._build_filter_expression(
        {"proof_points_job_filter": True, "exclude_customer_refs": False}
    )
    self.assertEqual(f_proof, 'slide_job: ANY("Proof_Points")')

    f_exclude = retriever._build_filter_expression(
        {"exclude_customer_refs": True}
    )
    self.assertEqual(f_exclude, 'customer_references = "false"')

  def test_customer_ref_library_retriever_gslides_only_and_relevance_ranking(self):
    mock_customer_ref_library_results = [
        # 1. Blog / non-GSlides record -> must be excluded
        {
            "document": {
                "id": "BLOG_1",
                "structData": {
                    "customer_name": "The Home Depot",
                    "industry": "Retail",
                    "asset_url": (
                        "https://cloud.google.com/customers/home-depot"
                    ),
                    "description": "Home Depot blog story on BigQuery and AI.",
                },
            }
        },
        # 2. Internal Alphabet self-reference -> must be excluded
        {
            "document": {
                "id": "CSL_INTERNAL",
                "structData": {
                    "customer_name": "Google Cloud",
                    "industry": "Alphabet Internal",
                    "source_type": "customer_slide_library",
                    "asset_url": (
                        "https://docs.google.com/presentation/d/"
                        "SAMPLE_CUST_REF_MASTER_DECK_ID_000000001/edit#slide=id.g_int"
                    ),
                },
                "derivedStructData": {
                    "extractive_answers": [
                        {"content": "Internal Google deployment of Gemini."}
                    ]
                },
            }
        },
        # 3. Workspace-only GSlides record -> must be filtered out by product disambiguation
        {
            "document": {
                "id": "CSL_WS",
                "structData": {
                    "customer_name": "Some Corp",
                    "industry": "Retail",
                    "source_type": "customer_slide_library",
                    "google_products": ["Google Workspace"],
                    "asset_url": (
                        "https://docs.google.com/presentation/d/"
                        "SAMPLE_CUST_REF_MASTER_DECK_ID_000000001/edit#slide=id.s_workspace_only"
                    ),
                },
                "derivedStructData": {
                    "extractive_answers": [{
                        "content": (
                            "Improved email drafting in Gmail and Docs with"
                            " Gemini for Google Workspace."
                        )
                    }]
                },
            }
        },
        # 4. Orthogonal industry GSlides record (Healthcare when pitching Retail)
        {
            "document": {
                "id": "CSL_HC",
                "structData": {
                    "customer_name": "Mayo Clinic",
                    "industry": "Healthcare",
                    "source_type": "customer_slide_library",
                    "google_products": ["Gemini Enterprise", "BigQuery"],
                    "ai_pillar": True,
                    "asset_url": (
                        "https://docs.google.com/presentation/d/"
                        "SAMPLE_CUST_REF_MASTER_DECK_ID_000000001/edit#slide=id.s_healthcare"
                    ),
                },
                "derivedStructData": {
                    "extractive_answers": [{
                        "content": (
                            "Mayo Clinic accelerated clinical search with"
                            " Gemini Enterprise."
                        )
                    }]
                },
            }
        },
        # 5. Generic Retail GSlides record
        {
            "document": {
                "id": "CSL_GENERIC_RETAIL",
                "structData": {
                    "customer_name": "Regional Grocer Co",
                    "industry": "Retail",
                    "source_type": "customer_slide_library",
                    "google_products": ["Gemini Enterprise"],
                    "ai_pillar": True,
                    "asset_url": (
                        "https://docs.google.com/presentation/d/"
                        "1abcDEF12345678901234567890/edit#slide=id.s_generic_retail"
                    ),
                },
                "derivedStructData": {
                    "extractive_answers": [{
                        "content": (
                            "Regional Grocer Co deployed Gemini Enterprise"
                            " agents across stores."
                        )
                    }]
                },
            }
        },
        # 6. Priority Retail Customer (The Home Depot) + Master Deck ID + Gemini Enterprise & BigQuery
        {
            "document": {
                "id": "CSL_HOMEDEPOT",
                "structData": {
                    "customer_name": "The Home Depot",
                    "industry": "Retail",
                    "sub_industry": "Home Improvement Retail",
                    "source_type": "customer_slide_library",
                    "google_products": ["Gemini Enterprise", "BigQuery"],
                    "gemini_enterprise": True,
                    "ai_native_data_cloud": True,
                    "ai_pillar": True,
                    "quantifiable_business_impact": True,
                    "asset_url": (
                        "https://docs.google.com/presentation/d/"
                        f"{CUSTOMER_REFERENCE_MASTER_DECK_IDS[0]}/edit#slide=id.s_priority_homedepot"
                    ),
                },
                "derivedStructData": {
                    "extractive_answers": [{
                        "content": (
                            "<b>The Home Depot</b> scaled agentic associate"
                            " search with Gemini Enterprise &amp; BigQuery,"
                            " achieving 35% faster lookup across 2,300 stores."
                        )
                    }]
                },
            }
        },
    ]

    retriever = NewLibraryCustomerReferenceRetriever(
        self.mock_config,
        "",
        "cust_ref",
    )
    with patch.object(
        retriever,
        "_query_customer_ref_library_engine",
        return_value=mock_customer_ref_library_results,
    ):
      results = retriever.search_slides(
          query="Gemini Enterprise BigQuery retail associate search",
          context={
              "closest_industry": "Retail",
              "section_sales_play": "Lead the Agentic Workplace Transformation",
              "product": ["Gemini Enterprise", "BigQuery"],
          },
          limit=5,
      )

    returned_ids = [r["slide_id"] for r in results]
    # Non-GSlides blog, internal Alphabet, and Workspace-only slides must be excluded
    self.assertNotIn("g_int", returned_ids)
    self.assertNotIn("s_workspace_only", returned_ids)
    self.assertIn("s_priority_homedepot", returned_ids)
    self.assertIn("s_generic_retail", returned_ids)

    # Priority customer (The Home Depot) + Master Deck ID + Retail + Gemini Enterprise/BigQuery ranks #1
    top_slide = results[0]
    self.assertEqual(top_slide["slide_id"], "s_priority_homedepot")
    self.assertEqual(
        top_slide["deck_id"], CUSTOMER_REFERENCE_MASTER_DECK_IDS[0]
    )
    self.assertEqual(top_slide["slide_job"], "Proof_Points")
    self.assertTrue(top_slide["is_proof_point"])
    self.assertTrue(top_slide["is_cust_ref"])
    self.assertEqual(top_slide["_source_library"], "customer_ref_gslides")
    self.assertIn("docs.google.com/presentation/d/", top_slide["slide_url"])
    self.assertIn("35% faster lookup", top_slide["summary"])
    # Orthogonal Healthcare slide should rank below Retail slides
    self.assertGreater(
        results[0]["_sim_score"],
        results[-1]["_sim_score"],
    )

  def test_customer_insights_workflow_enrichment(self):
    wf = CustomerInsightsWorkflow(self.mock_config)
    res = wf.execute(
        customer_name="Target",
        industry="Retail",
        sub_industry="Big-Box Omnichannel Retail",
        sales_plays=["Gemini Enterprise for Customer Experience"],
    )
    self.assertTrue(res["voc_ebc_themes"])
    self.assertTrue(res["top_blockers_and_mitigations"])
    self.assertIn("BigQuery", res["compete_swot"])
    self.assertIn(
        "STRATEGIC CUSTOMER & COMPETITIVE INTELLIGENCE",
        res["formatted_briefing"],
    )
    self.assertGreaterEqual(len(res["priority_peer_references"]), 3)

  def test_golden_gate_skills_loaded_by_skill_loader(self):
    compete_inst = load_skill_instructions("compete_differentiation")
    self.assertIn("Compete & Differentiation Skill (`K6`)", compete_inst)
    self.assertIn("15% LIGHT", compete_inst)

    cust_ref_inst = load_skill_instructions("customer_reference_governance")
    self.assertIn(
        "Customer Reference & Customer Reference Library Governance Skill (`K3`)", cust_ref_inst
    )
    self.assertIn("0% IMMUTABLE", cust_ref_inst)

    nano_inst = load_skill_instructions("nano_banana_slide")
    self.assertIn("4-Part Boardroom Art Director Directive", nano_inst)

    matched = get_matching_skill_instructions(
        "How do we differentiate against AWS Bedrock and show customer"
        " references?"
    )
    self.assertIn("Compete Differentiation Guidelines", matched)
    self.assertIn("Customer Reference Governance Guidelines", matched)


if __name__ == "__main__":
  unittest.main()
