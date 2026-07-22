import datetime
import json
import os
from google.cloud import discoveryengine_v1 as discoveryengine
from google.cloud import secretmanager
from google import genai
from google.genai import types
import requests

client = genai.Client(vertexai=True, project=os.getenv("GOOGLE_CLOUD_PROJECT", "YOUR_PROJECT_ID"), location='us-central1')


# Helper to get absolute path relative to this file
def get_path(relative_path):
  # This file is in src/, so we go up one level to the agent root
  base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  return os.path.join(base_path, relative_path)


# Placeholders for future agents
def retrieval_skill_placeholder():
  """Placeholder for Retrieval Agent skills."""
  return 'Retrieval Skill Placeholder'


def visual_skill_placeholder():
  """Placeholder for Visual Agent skills."""
  return 'Visual Skill Placeholder'


def slide_engineering_skill_placeholder():
  """Placeholder for Slide Engineering Agent skills."""
  return 'Slide Engineering Skill Placeholder'


# Proposal Agent Skills


def extract_context_entities(business_context: str) -> dict:
  """Extracts key entities (customer, industry, solutions, etc.) from the user's business context.

  Args:
      business_context (str): The raw text provided by the user describing their
        needs.

  Returns:
      dict: A dictionary containing extracted entities.
  """
  with open(get_path('prompt_templates/contextEntities.txt'), 'r') as f:
    prompt = f.read()

  response = client.models.generate_content(
      model='gemini-2.5-flash-lite',
      contents=[prompt, business_context, '\n[output]\n']
  )
  try:
    # Extract JSON from response
    text = response.text
    start = text.find('{')
    end = text.rfind('}') + 1
    return json.loads(text[start:end])
  except Exception as e:
    return {'error': f'Entity extraction failed: {str(e)}'}


def perform_web_search(
    query: str, project_id: str, location: str, datastore_id: str
) -> str:
  """Performs a semantic web search using Google Discovery Engine."""
  client = discoveryengine.SearchServiceClient()
  serving_config = client.serving_config_path(
      project=project_id,
      location=location,
      data_store=datastore_id,
      serving_config='default_config',
  )

  content_search_spec = discoveryengine.SearchRequest.ContentSearchSpec(
      summary_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec(
          summary_result_count=5,
          include_citations=True,
      )
  )
  request = discoveryengine.SearchRequest(
      content_search_spec=content_search_spec,
      serving_config=serving_config,
      query=query,
      page_size=5,
  )

  try:
    response = client.search(request)
    return response.summary.summary_with_metadata.summary
  except Exception as e:
    return f'Search failed: {str(e)}'


def generate_proposal_outline(context_data: dict) -> dict:
  """Generates a structured proposal outline based on extracted data and research.

  Args:
      context_data (dict): Combined data from entity extraction and web search.

  Returns:
      dict: The final structured outline.
  """
  with open(get_path('prompt_templates/outlineGen.txt'), 'r') as f:
    prompt = f.read()

  response = client.models.generate_content(
      model='gemini-2.5-flash-lite',
      contents=[prompt, json.dumps(context_data), '\n[output]\n']
  )
  try:
    text = response.text
    start = text.find('{')
    end = text.rfind('}') + 1
    return json.loads(text[start:end])
  except Exception as e:
    return {'error': f'Outline generation failed: {str(e)}'}


class ProposalSkills:
  """Namespace for Proposal Agent skills to be used by ADK."""

  @staticmethod
  def create_proposal_outline(business_context: str) -> str:
    """End-to-end skill to generate a proposal outline from business context.

    This represents the core Proposal Agent logic.
    """
    # 1. Extract Entities
    entities = extract_context_entities(business_context)
    if 'error' in entities:
      return json.dumps(entities)

    # 2. (Optional) Web Search / Company Data logic would go here
    # For brevity in this automation setup, we'll assume entity extraction is the primary step
    # that feeds into the outline generation.

    # 3. Generate Outline
    outline = generate_proposal_outline(entities)
    return json.dumps(outline, indent=2)
