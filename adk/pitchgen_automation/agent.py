import os
import sys

# Ensure the current directory is in the path to resolve local imports like 'src'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Remove any API keys from the environment to prevent the google-genai SDK
# from using them instead of standard Google Cloud IAM/ADC credentials.
os.environ.pop('GEMINI_API_KEY', None)
os.environ.pop('GOOGLE_API_KEY', None)
os.environ.pop('API_KEY', None)

from google.adk.agents.llm_agent import Agent
from src.skills import (
    ProposalSkills,
    retrieval_skill_placeholder,
    visual_skill_placeholder,
    slide_engineering_skill_placeholder,
)

# specialist agents
proposal_agent = Agent(
    name="proposal_agent",
    model="gemini-2.5-flash-lite",
    description="Specialist for business strategy and proposal generation.",
    instruction=(
        "You are the Proposal Agent. Your job is to generate a structured pitch"
        " deck outline. Use the 'create_proposal_outline' skill to perform"
        " entity extraction and outline generation. DO NOT show raw JSON,"
        " dictionaries, or code-like structures in your final response."
    ),
    tools=[ProposalSkills.create_proposal_outline],
)

retrieval_agent = Agent(
    name="retrieval_agent",
    model="gemini-2.5-flash-lite",
    description="Specialist for semantic search and relevance scoring.",
    instruction="Placeholder for retrieval logic.",
    tools=[retrieval_skill_placeholder],
)

visual_agent = Agent(
    name="visual_agent",
    model="gemini-2.5-flash-lite",
    description="Specialist for image synthesis and transformation.",
    instruction="Placeholder for visual logic.",
    tools=[visual_skill_placeholder],
)

slide_engineering_agent = Agent(
    name="slide_engineering_agent",
    model="gemini-2.5-flash-lite",
    description="Specialist for slide assembly and layout transformation.",
    instruction="Placeholder for slide engineering logic.",
    tools=[slide_engineering_skill_placeholder],
)

# Root Orchestrator
root_agent = Agent(
    name="pitchgen_orchestrator",
    model="gemini-2.5-flash-lite",
    description="The central coordinator for PitchGen.",
    instruction=(
        "You are the PitchGen Orchestrator. Your goal is to guide the user"
        " through the deck creation process. First, coordinate with the"
        " 'proposal_agent' to generate a readable outline. "
    ),
    sub_agents=[
        proposal_agent,
        retrieval_agent,
        visual_agent,
        slide_engineering_agent,
    ],
)
