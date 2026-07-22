import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure modules can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.sidebar_agent import sidebar_search, sidebar_generate


class TestSidebarSearchGenerator(unittest.TestCase):

  @patch("agents.sidebar_agent.slide_search")
  def test_sidebar_search(self, mock_slide_search):
    # Setup mock search instance and return value
    mock_instance = MagicMock()
    mock_slide_search.return_value = mock_instance

    mock_instance.execute.return_value = [{
        "date": "2026-05-04 12:47:03",
        "deckId": "1kabh4PBXWN3Imub-DK8vqSlZQR-KxzNMT62tjpjLKbQ",
        "name": (
            "AI/ML Infrastructure Games Business [<YOUR_PITCH_LINK>]"
        ),
        "slideId": "g359631dcfc9_0_2427",
        "slideURL": (
            "https://docs.google.com/presentation/d/1kabh4PBXWN3Imub-DK8vqSlZQR-KxzNMT62tjpjLKbQ/edit?#slide=id.g359631dcfc9_0_2427"
        ),
        "tags": ["gaming"],
    }]

    response_str = sidebar_search("Gaming industry", strict_search=False)
    print("SEARCH RESPONSE:", response_str)
    response = json.loads(response_str)

    self.assertEqual(response["search_query"], "Gaming industry")
    self.assertEqual(len(response["search_results"]), 1)
    self.assertEqual(
        response["search_results"][0]["deckId"],
        "1kabh4PBXWN3Imub-DK8vqSlZQR-KxzNMT62tjpjLKbQ",
    )

  @patch("agents.sidebar_agent.add_slide")
  @patch("agents.sidebar_agent.ensemble_retriver")
  def test_sidebar_generate(self, mock_ensemble_retriver, mock_add_slide):
    # Setup mocks
    mock_retriever = MagicMock()
    mock_ensemble_retriver.return_value = mock_retriever

    mock_add_slide.return_value = {
        "deck_id": "<YOUR_PRESENTATION_ID>",
        "placeholders": {
            "header1": "Operational Efficiency",
            "header1_content": "Reduce complexity...",
            "title": "Elevate Your Business with AI Solutions",
        },
        "slide_id": "g36ba0835289_0_3267",
    }

    response_str = sidebar_generate(
        slide_content="GCP",
        slide_title="Elevate Your Business",
        slide_layout="Enterprise Style",
        slide_category="Context",
        deck_id="1ZZFBxZsGYIrz09NWvKmHtFTjtvEviEJXRbJlfxDVwSs",
        slide_id="SLIDES_123",
    )
    print("GENERATE RESPONSE:", response_str)
    response = json.loads(response_str)

    self.assertEqual(response["Status"], "True")
    self.assertEqual(response["message"], "Success")
    self.assertEqual(
        response["data"]["deck_id"],
        "<YOUR_PRESENTATION_ID>",
    )
    self.assertEqual(response["data"]["slide_id"], "g36ba0835289_0_3267")


if __name__ == "__main__":
  unittest.main()
