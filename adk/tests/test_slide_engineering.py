import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# googleinit removed

from unittest.mock import MagicMock

from config_loader import load_config
from state import GlobalState
from agents.slide_engineering_agent import SlideEngineeringAgent


def test_slide_engineering():
  config = load_config()
  agent = SlideEngineeringAgent(config)

  # Mock the synthesis skill to return dummy content
  dummy_content = {
      "1": (
          "Slide Title: Enterprise AI Solutions\nSlide Content:\n* Vertex AI:"
          " Platform to build and deploy ML.\n* Gemini: Multimodal models for"
          " enterprise.\n* BigQuery: Serverless data warehouse."
      )
  }
  agent.skills["synthesis"].execute = MagicMock(return_value=dummy_content)

  state = GlobalState()

  # Run agent
  final_state = agent.run(state)

  print("\n--- Final Deck Structure ---")
  print(json.dumps(final_state.final_deck_structure, indent=2))


if __name__ == "__main__":
  test_slide_engineering()
