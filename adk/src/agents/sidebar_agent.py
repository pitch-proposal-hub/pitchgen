import base64
import json
import os
import re
import sys

from config_loader import load_config
from google.adk.agents.llm_agent import Agent
from google.genai import types

from agents.base_agent import BaseAgent
from agents.workflows.sidebar_slide_search_workflow import slide_search
from agents.workflows.sidebar_add_slides_workflow import add_slide, image_data_extraction
from agents.workflows.sidebar_new_content_gen_workflow import ensemble_retriver
from pitchgen_utils.image_util import get_image_mime_type, clean_base64_data


class SidebarAgent(BaseAgent):
  """Agent responsible for sidebar reusable slide search and new slide content generation."""

  def __init__(self, config):
    super().__init__(
        "SidebarAgent",
        "Agent responsible for sidebar search of reusable slides and new slide content generation."
    )
    self.config = config
    self.add_skill("search", slide_search)
    self.add_skill("add_slide", add_slide)
    self.add_skill("ensemble_retriever", ensemble_retriver)

  def run(self, input_data):
    """Abstract method implementation. Unused for SidebarAgent since it exposes direct tool endpoints."""
    pass

  def search(self, search_query: str, strict_search: bool = False, user_ldap: str = "") -> dict:
    model = self.config.get("default", "gemini_model")

    # Instantiate and run slide search
    search_obj = self.skills["search"](search_query, strict_search, self.config, model)
    results = search_obj.execute()

    # Clean results for JSON serialization if needed
    cleaned_results = []
    for res in results:
      cleaned_results.append(dict(res))

    return {"search_query": search_query, "search_results": cleaned_results}

  def generate(
      self,
      slide_content: str,
      slide_title: str = "",
      slide_layout: str = "",
      slide_category: str = "",
      deck_id: str = "",
      slide_id: str = "",
      audience: str = "",
      industry: str = "",
      product: str = "",
      region: str = "GLOBAL",
      action: str = "add_generate",
      er_number: str = "21212",
      user_ldap: str = "",
      presentation_id: str = "",
      slide_image_url: str = "",
  ) -> dict:
    model = self.config.get("default", "gemini_model")

    # Check if slide_image_url is provided and not empty
    if slide_image_url != "":
      try:
        # Handle base64 vs GCS URI for input_data
        mime_type = get_image_mime_type(slide_image_url)
        if slide_image_url.startswith("gs://"):
          input_data = types.Part.from_uri(
              file_uri=slide_image_url, mime_type=mime_type
          )
        else:
          b64_data = clean_base64_data(slide_image_url)
          decoded_bytes = base64.b64decode(b64_data)
          input_data = types.Part.from_bytes(
              data=decoded_bytes, mime_type=mime_type
          )

        text_prompt = """Extract all the text with all the fields like ER Number, Customer Name, Audience, Industry, Solution, Business context from the below image and save in a .json format"""

        (
            er_number_extracted,
            audience_extracted,
            industry_extracted,
            solution_extracted,
            customer_name_extracted,
            business_context_extracted,
        ) = image_data_extraction(text_prompt, input_data)

        # Use extracted values if valid
        if audience_extracted:
          audience = (
              ", ".join(audience_extracted)
              if isinstance(audience_extracted, list)
              else audience_extracted
          )
        if industry_extracted:
          industry = industry_extracted
      except Exception as img_err:
        print(f"Image data extraction error: {img_err}")

    # Build URL list for ensemble retriever
    url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
    url_list = re.findall(url_pattern, slide_content)

    ensemble_retriever = self.skills["ensemble_retriever"](url_list)

    new_slide = self.skills["add_slide"](
        ensemble_retriever=ensemble_retriever,
        slide_title=slide_title,
        slide_content=slide_content,
        slide_layout=slide_layout,
        slide_category=slide_category,
        deck_id=deck_id,
        slide_id=slide_id,
        model=model,
    )

    return new_slide


def sidebar_search(
    search_query: str, strict_search: bool = False, user_ldap: str = ""
) -> str:
  """Search for reusable slides based on a search query.

  Args:
      search_query: The query string to search for (e.g. 'Gaming industry').
      strict_search: Whether to perform a strict tag-based search.
      user_ldap: User's LDAP/email.
  """
  try:
    config = load_config()
    agent = SidebarAgent(config)
    result = agent.search(search_query, strict_search, user_ldap)
    return json.dumps(result, indent=2)
  except Exception as e:
    return json.dumps({"error": str(e)})


def sidebar_generate(
    slide_content: str,
    slide_title: str = "",
    slide_layout: str = "",
    slide_category: str = "",
    deck_id: str = "",
    slide_id: str = "",
    audience: str = "",
    industry: str = "",
    product: str = "",
    region: str = "GLOBAL",
    action: str = "add_generate",
    er_number: str = "21212",
    user_ldap: str = "",
    presentation_id: str = "",
    slide_image_url: str = "",
) -> str:
  """Generate a new slide based on the given instructions.

  Args:
      slide_content: The text content or URL context for generating the slide.
      slide_title: The title of the slide.
      slide_layout: Slide design layout style.
      slide_category: Slide category template.
      deck_id: Target presentation deck ID.
      slide_id: Target template slide ID.
      audience: Target audience.
      industry: Target vertical industry.
      product: Products context.
      region: Target geographic region.
      action: Generating action (e.g. 'add_generate').
      er_number: Enterprise request number.
      user_ldap: User's LDAP/email.
      presentation_id: Presentation ID.
      slide_image_url: Base64 or URL of slide screenshot image.
  """
  try:
    config = load_config()
    agent = SidebarAgent(config)
    new_slide = agent.generate(
        slide_content=slide_content,
        slide_title=slide_title,
        slide_layout=slide_layout,
        slide_category=slide_category,
        deck_id=deck_id,
        slide_id=slide_id,
        audience=audience,
        industry=industry,
        product=product,
        region=region,
        action=action,
        er_number=er_number,
        user_ldap=user_ldap,
        presentation_id=presentation_id,
        slide_image_url=slide_image_url,
    )
    output = {"Status": "True", "data": new_slide, "message": "Success"}
    return json.dumps(output, indent=2)
  except Exception as e:
    return json.dumps({"Status": "False", "message": str(e)})


# Initialize the Root Agent using ADK standard syntax for web UI loading
try:
  config = load_config()
  default_model = config.get("default", "gemini_model", fallback="gemini-3.1-flash-lite")
except Exception:
  default_model = "gemini-3.1-flash-lite"

root_agent = Agent(
    name="SidebarSearchGeneratorAgent",
    model=os.getenv("MODEL", default_model),
    description=(
        "Agent responsible for sidebar search of reusable slides and new slide"
        " content generation."
    ),
    instruction=(
        "You are the Sidebar Search and Generator Agent. You help users search"
        " for reusable slides or generate new slide content. Use the provided"
        " tools to fulfill requests."
    ),
    tools=[sidebar_search, sidebar_generate],
)
