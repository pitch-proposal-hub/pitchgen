"""Enterprise Agent definition for Gemini Enterprise App deck generation."""

import os
import sys

# Remove any API keys from the environment to prevent the google-genai SDK
# from using them instead of standard Google Cloud IAM/ADC credentials.
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("GOOGLE_API_KEY", None)
os.environ.pop("API_KEY", None)

# Ensure the current directory is in the path to resolve local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from google.adk.agents.llm_agent import Agent
from google.adk.apps.app import App
from config_loader import load_config
from agent import PitchGenSkills

config = load_config()
project_id = config["default"].get("project_name", os.environ.get("GCP_PROJECT_ID", "<YOUR_GCP_PROJECT_ID>"))
model_name = config["default"].get("gemini_model", "gemini-3.5-flash")
model_region = "global"

enterprise_agent = Agent(
    name="pitchgen_deck_creator",
    model=f"projects/{project_id}/locations/{model_region}/publishers/google/models/{model_name}",
    description=(
        "An enterprise agent for co-creating sales presentation slide decks."
    ),
    instruction=(
        "You are the PitchGen Sales Catalyst, an expert AI assistant dedicated to co-creating "
        "high-impact, customized Google Cloud sales presentations.\n\n"
        "Your style is collaborative, professional, and results-driven. Make the process engaging "
        "and fun for sales teams by asking targeted questions and celebrating draft milestones.\n\n"
        "Follow this two-phase execution workflow:\n"
        "1. Phase 1 (Outline Generation): When a user wants to build a new deck, gather the customer name, "
        "business context, industry vertical, target products/solutions, relevant sales play, and audience "
        "details (e.g., C-level executives, technical architects, business leaders). Do not hesitate to ask "
        "clarifying questions to gather these details so the deck is perfectly tailored. Once gathered, execute "
        "the 'create_proposal_outline' tool. Present the generated outline to the user in a clean, "
        "professional format. Ask them for feedback, refinements, or approval before moving forward.\n"
        "2. Phase 2 (Deck Generation): Once the user approves the outline, call the 'slide_generator_skill' tool "
        "with the approved outline configuration JSON to generate the slide structures.\n\n"
        "3. Wrap-up & Next Steps: After generating the slides, present the final deck structure to the user. "
        "To make their journey seamless, always recommend the following follow-up resources:\n"
        " - 🚀 **Self-Service Editing**: Install the PitchGen Google Slides extension via <YOUR_PITCHGEN_EXTENSION_URL> "
        "to search, generate, and polish presentation content directly inside Google Slides.\n"
        " - 🎨 **White-Glove Support**: Need custom visuals, demo support, or professional designer help? Request "
        "white-glove proposal services from the Pitch & Proposal Hub team via <YOUR_PROPOSAL_SUPPORT_URL>."
    ),
    tools=[
        PitchGenSkills.create_proposal_outline,
        PitchGenSkills.slide_generator_skill,
    ],
)

app = App(root_agent=enterprise_agent, name="src")
