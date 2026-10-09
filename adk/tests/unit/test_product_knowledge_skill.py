"""Unit tests for Product Knowledge Skill and Developer Knowledge Grounding."""

import os
import sys

pitchgen_dir = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, pitchgen_dir)
sys.path.insert(0, os.path.join(pitchgen_dir, "src"))

from agents.skill_loader import load_skill_instructions
from agents.workflows.text_transformer_workflow import TextTransformerWorkflow
from configparser import ConfigParser


def test_product_knowledge_skill_loads_and_has_mandates():
  instructions = load_skill_instructions("product_knowledge")
  assert instructions, "product_knowledge SKILL.md should not be empty"
  assert "Developer Knowledge API" in instructions
  assert "Forward-Modernization" in instructions
  assert "Anti-Downgrade" in instructions
  assert "Architecture Blueprint" in instructions
  assert "Zero Hallucination" in instructions
  assert "October 2026 Gemini Brand Unification" in instructions
  assert "The Core Naming Swaps Table" in instructions
  assert "Built with Gemini" in instructions
  assert "Antigravity in Gemini platform" in instructions
  assert "Model Garden in Gemini platform" in instructions
  assert "agent runtime in Gemini platform" in instructions
  assert "Gemini for financial services" in instructions
  assert "Gemini Enterprise Standard edition" in instructions
  assert "AI Hypercomputer" in instructions
  assert "Knowledge Catalog" in instructions


def test_product_knowledge_modernization_rules():
  instructions = load_skill_instructions("product_knowledge")
  # Verify October 2026 Gemini brand unification rules (Enterprise-Brand-Unification) and prohibited terms
  assert "Gemini platform" in instructions
  assert "Gemini Enterprise Agent Platform" in instructions
  assert "GEAP" in instructions
  assert "Gemini Enterprise app" in instructions
  assert "Knowledge Catalog" in instructions
  assert "AI Hypercomputer" in instructions
  assert "Chrome Enterprise Construct" in instructions
  # Verify anti-downgrade guidance
  assert "Never replace or downgrade" in instructions or "Strict Anti-Downgrade" in instructions


def test_h2_2026_one_product_deterministic_sanitizer():
  config = ConfigParser()
  config.read("src/config/config.ini")
  workflow = TextTransformerWorkflow(config)

  assert (
      workflow._sanitize_output(
          "Deploy agents on Gemini Enterprise Agent Platform and GEAP.",
          original_len=0,
      )
      == "Deploy agents on Gemini platform and Gemini platform."
  )
  assert (
      workflow._sanitize_output(
          "The Gemini Enterprise app, built on the Agent Platform, unifies"
          " search.",
          original_len=0,
      )
      == "Gemini, built on the Gemini platform, unifies search."
  )
  assert (
      workflow._sanitize_output(
          "Connect the GE app with Gemini Enterprise platform.",
          original_len=0,
      )
      == "Connect Gemini with Gemini platform."
  )
  assert (
      workflow._sanitize_output(
          "Use Antigravity with Agent Platform for app users and platform"
          " customers.",
          original_len=0,
      )
      == "Use Antigravity in Gemini platform for Gemini users and Gemini users."
  )
  assert (
      workflow._sanitize_output(
          "Gemini Enterprise for Financial Services and GECX with GEAP Model"
          " Garden.",
          original_len=0,
      )
      == "Gemini for financial services and Gemini for customer experience with"
      " Model Garden in Gemini platform."
  )
  assert (
      workflow._sanitize_output(
          "Powered by Gemini and powered by Gemini Enterprise.",
          original_len=0,
      )
      == "Built with Gemini and powered by Gemini Enterprise."
  )


def test_internal_enablement_slide_detection():
  config = ConfigParser()
  config.read("src/config/config.ini")
  workflow = TextTransformerWorkflow(config)

  # Internal Context Slide
  internal_slide = {
      "slideId": "slide_ic",
      "title": "Internal Context: Agentic Data Cloud",
      "data": [
          {"shapeId": "sh_1", "text": "Target persona: CDO, CTO"},
          {"shapeId": "sh_2", "text": "Who to contact: Alyssa Cori"},
          {"shapeId": "sh_3", "text": "Real Talk Coaching Videos"},
      ],
  }
  assert workflow._is_internal_enablement_slide(internal_slide) is True

  # Customer Narrative Slide
  customer_slide = {
      "slideId": "slide_cust",
      "title": "The Modern Retail Foundation",
      "data": [
          {"shapeId": "sh_1", "text": "The Modern Retail Foundation"},
          {"shapeId": "sh_2", "text": "Streamline logistics and inventory."},
      ],
  }
  assert workflow._is_internal_enablement_slide(customer_slide) is False


def test_developer_knowledge_query_detection():
  config = ConfigParser()
  config.read("src/config/config.ini")
  workflow = TextTransformerWorkflow(config)

  texts = ["Google's Agentic Data Cloud", "Knowledge Catalog", "AI Hypercomputer"]
  should_fetch, query = workflow._detect_developer_knowledge_intent(
      criteria="make concise", texts=texts, context={}
  )
  assert should_fetch is True
  assert "Google Cloud" in query
  assert "knowledge catalog" in query or "ai hypercomputer" in query or "agentic" in query


if __name__ == "__main__":
  test_product_knowledge_skill_loads_and_has_mandates()
  test_product_knowledge_modernization_rules()
  test_h2_2026_one_product_deterministic_sanitizer()
  test_internal_enablement_slide_detection()
  test_developer_knowledge_query_detection()
  print("All product knowledge unit tests passed!")
