"""Outline generation skill leveraging customer context and search tools."""

import json
import os
import re
from google import genai
try:
  from google.cloud import discoveryengine_v1 as discoveryengine
except ImportError as e:
  import sys
  print(f"[DEBUG] ImportError caught during discoveryengine import: {e}")
  print(f"[DEBUG] sys.path: {sys.path}")
  try:
    import google
    print(f"[DEBUG] google module path: {google.__path__}")
  except Exception as ge:
    print(f"[DEBUG] Failed to print google path: {ge}")
  try:
    import google.cloud
    print(f"[DEBUG] google.cloud module path: {google.cloud.__path__}")
  except Exception as gce:
    print(f"[DEBUG] Failed to print google.cloud path: {gce}")
  raise e
from google.cloud import secretmanager
from google.genai import types
from agents.workflows.base_workflow import BaseWorkflow
from agents.workflows.developer_knowledge_workflow import DeveloperKnowledgeWorkflow
from config_loader import resolve_secret_with_cache


class OutlineWorkflow(BaseWorkflow):
  """Generates a structured presentation outline from business context."""

  def __init__(self, config):
    super().__init__(
        "OutlineWorkflow", "Generates a structured outline from business context."
    )
    self.config = config
    self.project_id = config["default"]["project_name"]
    self.gemini_model = config["default"].get(
        "gemini_model",
        config["default"].get("gemini_model_1", "gemini-3.1-flash-lite"),
    )

    # Discovery Engine Setup
    self.discovery_client = discoveryengine.SearchServiceClient()
    self.location = "global"

    # Secret Manager Setup (Resolved with cache)
    self.website_secret_name = self.config["datastore"]["website"]
    self.website_store_id = resolve_secret_with_cache(self.website_secret_name)

    self.website_serving_config = self.discovery_client.serving_config_path(
        project=self.project_id,
        location=self.location,
        data_store=self.website_store_id,
        serving_config="default_config",
    )
    self.dk_skill = DeveloperKnowledgeWorkflow(config)

  def detect_sales_play(self, client, business_context, play_guidelines):
    """Detects the most relevant sales play from the user's business context."""
    prompt = f"""Analyze the following user business request and identify if it maps to any of the official Google Cloud Sales Plays listed in the guidelines below.
        
        User Request: "{business_context}"
        
        Guidelines & Available Sales Plays:
        {play_guidelines}
        
        Return your response in JSON format with a key "detected_play" containing the play name (e.g., "Scale AI Apps and Agents", "Agentic Data Cloud"), or null.
        """

    try:
      response = client.models.generate_content(
          model=self.gemini_model,
          contents=prompt,
          config=types.GenerateContentConfig(
              response_mime_type="application/json",
              temperature=0,
          ),
      )
      res = json.loads(response.text)
      return res.get("detected_play")
    except Exception as e:  # pylint: disable=broad-exception-caught
      print(f"[OutlineWorkflow] Warning: Sales play detection failed: {e}")
      return None

  def web_search(self, query):
    content_search_spec = discoveryengine.SearchRequest.ContentSearchSpec(
        summary_spec=(
            discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec(
                summary_result_count=5,
                include_citations=True,
                ignore_adversarial_query=True,
                ignore_non_summary_seeking_query=True,
            )
        )
    )
    request = discoveryengine.SearchRequest(
        content_search_spec=content_search_spec,
        serving_config=self.website_serving_config,
        query=query,
        page_size=5,
    )
    try:
      response = self.discovery_client.search(request)
      return response.summary.summary_with_metadata.summary
    except Exception as e:  # pylint: disable=broad-exception-caught
      print(f"Web search error: {e}")
      return ""

  def research_customer(self, client, customer_name):
    """Researches the customer using Gemini Google Search."""
    if not customer_name:
      return "No customer name provided for research."

    prompt = (
        f"Research company {customer_name}. Summarize business model, news,"
        " financials, priorities, and challenges."
    )
    try:
      print(f"[OutlineWorkflow] Researching customer: {customer_name}")
      response = client.models.generate_content(
          model=self.gemini_model,
          contents=prompt,
          config=types.GenerateContentConfig(
              tools=[types.Tool(google_search=types.GoogleSearch())]
          )
      )
      return response.text
    except Exception as e:  # pylint: disable=broad-exception-caught
      print(f"[OutlineWorkflow] Warning: Customer research failed: {e}")
      return (
          f"Failed to retrieve research for {customer_name} due to error: {e}"
      )

  def determine_sub_industry(self, client, customer_name, customer_research, industry):
    """Determines the specific sub-industry of the customer from research data."""
    if not customer_name:
      return ""

    prompt = f"""Based on the customer name '{customer_name}' and the following customer research summary, determine their specific sub-industry vertical.
    
    Customer Research:
    {customer_research}
    
    Parent Industry: {industry}
    
    Identify the most accurate sub-industry (e.g., 'Grocery', 'Quick Service Restaurant (QSR)', 'Banking', 'E-commerce', 'Biopharma', 'Automotive OEM', 'Retail').
    Return your response in JSON format with a single key "sub_industry" containing the name of the sub-industry, or null if it cannot be determined.
    """
    try:
      response = client.models.generate_content(
          model=self.gemini_model,
          contents=prompt,
          config=types.GenerateContentConfig(
              response_mime_type="application/json",
              temperature=0,
          ),
      )
      res = json.loads(response.text)
      return res.get("sub_industry") or ""
    except Exception as e:  # pylint: disable=broad-exception-caught
      print(f"[OutlineWorkflow] Warning: Sub-industry classification failed: {e}")
      return ""

  def execute(self, context):
    business_context = context.get("business_context", "")
    customer_name = context.get("customer_name", "")

    client = genai.Client(
        vertexai=True, project=self.project_id, location="global"
    )
    customer_research = self.research_customer(client, customer_name)

    # 1. Extract Entities
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "prompt_templates",
        "contextEntities.txt",
    )
    with open(prompt_path, "r") as f:
      entities_prompt = f.read()

    response = client.models.generate_content(
        model=self.gemini_model,
        contents=[entities_prompt, business_context, "\n[output]\n"],
        config=types.GenerateContentConfig(
            system_instruction="Please provide output in json format.",
            response_mime_type="application/json",
            temperature=0,
        ),
    )

    entities = json.loads(response.text)
    print(f"Extracted entities: {entities}")

    # 2. Resolve Industry & Sub-industry
    sub_industry = context.get("sub_industry", "")
    industry = context.get("industry", entities.get("industry", "General"))

    extracted_ind = entities.get("industry", "")
    if not sub_industry and " in " in extracted_ind:
      parts = extracted_ind.split(" in ", 1)
      sub_industry = parts[0].strip()
      industry = parts[1].strip()

    if not sub_industry and customer_name:
      sub_industry = self.determine_sub_industry(
          client, customer_name, customer_research, industry
      )

    if sub_industry:
      print(f"[OutlineWorkflow] Resolved sub-industry: '{sub_industry}'")
      context["sub_industry"] = sub_industry
      context["industry"] = industry # update in context

    # 3. Web Search for solutions
    solutions = context.get("solution", []) + entities.get("solution", [])
    solutions = list(set(solutions))

    sol_data_list = []
    for sol in solutions:
      search_query = f"{sol} solution for {industry} industry."
      web_summary = self.web_search(search_query)

      # Query Developer Knowledge API for product details
      dk_summary = self.dk_skill.execute(sol)

      combined_summary = f"Web Search: {web_summary}"
      if dk_summary and "unavailable" not in dk_summary:
        combined_summary += f"\nDeveloper Docs: {dk_summary}"

      sol_data_list.append(f"{sol}.\n{combined_summary}")

    sol_data = "\n".join(sol_data_list)

    # 4. Generate Outline
    outline_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "prompt_templates",
        "outlineGen.txt",
    )
    with open(outline_path, "r") as f:
      outline_prompt = f.read()

    # Dynamically load CVI Framework and WIN Cycle Skill instructions
    from agents.skill_loader import load_skill_instructions

    cvi_instructions = load_skill_instructions("cvi_framework")
    win_cycle_instructions = load_skill_instructions("win_cycle")

    if cvi_instructions:
      print(
          "[OutlineWorkflow] Dynamically loaded and injected 'cvi_framework'"
          " guidelines."
      )
      outline_prompt = (
          f"{outline_prompt}\n\n### Detailed CVI Framework"
          f" Guidelines:\n{cvi_instructions}"
      )

    if win_cycle_instructions:
      print(
          "[OutlineWorkflow] Dynamically loaded and injected 'win_cycle'"
          " guidelines."
      )
      outline_prompt = (
          f"{outline_prompt}\n\n### Google Cloud WIN Cycle"
          f" Guidelines:\n{win_cycle_instructions}"
      )

      # Grounding with detailed win cycle stages & roles
      from agents.skill_loader import load_skill_reference

      win_cycle_details = load_skill_reference(
          "win_cycle", "win_cycle_details.md"
      )
      if win_cycle_details:
        print(
            "[OutlineWorkflow] Dynamically grounded with detailed"
            " 'win_cycle_details' reference."
        )
        outline_prompt = (
            f"{outline_prompt}\n\n### Detailed WIN Cycle Stages &"
            f" Roles:\n{win_cycle_details}"
        )

    # Conditionally load Segment Targeting Skill if audience contains "segment" or segment names
    user_audiences = [a.lower().strip() for a in context.get("audience", [])]
    has_segment = "segment" in user_audiences or any(
        s in user_audiences
        for s in ["smb", "startups", "corporate", "enterprise", "strategic"]
    )
    if has_segment:
      segment_instructions = load_skill_instructions("segment_targeting")
      if segment_instructions:
        print(
            "[OutlineWorkflow] Dynamically loaded and injected 'segment_targeting'"
            " guidelines based on audience."
        )
        outline_prompt = (
            f"{outline_prompt}\n\n### Customer Segment Targeting"
            f" Guidelines:\n{segment_instructions}"
        )

    # Conditionally load Sales Play Selection and specific play guidelines
    sales_play_selected = context.get("salesPlay")
    sales_play_instructions = load_skill_instructions("sales_play_selection")

    if not sales_play_selected and sales_play_instructions:
      # Auto-detect based on business context/request
      detected_play = self.detect_sales_play(
          client, business_context, sales_play_instructions
      )
      if detected_play:
        print(
            "[OutlineWorkflow] Proactively detected relevant sales play from user"
            f" prompt: '{detected_play}'"
        )
        sales_play_selected = detected_play

    if sales_play_selected and sales_play_instructions:
      print(
          "[OutlineWorkflow] Dynamically loaded 'sales_play_selection' guidelines"
          f" for: {sales_play_selected}"
      )
      outline_prompt = (
          f"{outline_prompt}\n\n### Google Cloud Sales Play"
          f" Guidelines:\n{sales_play_instructions}"
      )

      # Grounding for specific plays (e.g. Scale AI Apps and Agents)
      from agents.skill_loader import load_skill_reference

      if isinstance(sales_play_selected, list):
        play_norm = ",".join(sales_play_selected).lower().replace("_", " ").strip()
      else:
        play_norm = str(sales_play_selected).lower().replace("_", " ").strip()
      if "scale ai" in play_norm:
        play_details = load_skill_reference(
            "sales_play_selection", "scale_ai_apps_and_agents.md"
        )
        if play_details:
          print(
              "[OutlineWorkflow] Dynamically loaded and grounded with"
              " 'scale_ai_apps_and_agents' play details."
          )
          outline_prompt = (
              f"{outline_prompt}\n\n### Specific Sales Play Grounding Details"
              f" (Scale AI Apps and Agents):\n{play_details}"
          )

    # Conditionally load Industry Specific Skills (Retail / Media)
    user_industry = context.get("industry", "").lower()
    extracted_industries = (
        [i.lower() for i in entities.get("industry", [])]
        if isinstance(entities.get("industry"), list)
        else [str(entities.get("industry")).lower()]
    )

    is_retail = "retail" in user_industry or any(
        "retail" in i for i in extracted_industries
    )
    is_media = any(
        m in user_industry for m in ["media", "entertainment", "gaming"]
    ) or any(
        any(m in i for m in ["media", "entertainment", "gaming"])
        for i in extracted_industries
    )

    if is_retail:
      retail_instructions = load_skill_instructions("retail_industry")
      if retail_instructions:
        print(
            "[OutlineWorkflow] Dynamically loaded and injected 'retail_industry'"
            " GTM guidelines."
        )
        outline_prompt = (
            f"{outline_prompt}\n\n### Google Cloud Retail & Consumer Industry"
            f" Guidelines:\n{retail_instructions}"
        )

      # Grounding with detailed retail industry pillars & blockers
      from agents.skill_loader import load_skill_reference

      retail_pillars = load_skill_reference(
          "retail_industry", "industry_pillars.md"
      )
      if retail_pillars:
        print(
            "[OutlineWorkflow] Dynamically grounded with detailed retail industry"
            " pillars & blockers."
        )
        outline_prompt = (
            f"{outline_prompt}\n\n### Detailed Retail Product & Blocker"
            f" Grounding:\n{retail_pillars}"
        )

    if is_media:
      media_instructions = load_skill_instructions("media_industry")
      if media_instructions:
        print(
            "[OutlineWorkflow] Dynamically loaded and injected 'media_industry'"
            " GTM guidelines."
        )
        outline_prompt = (
            f"{outline_prompt}\n\n### Google Cloud Media & Entertainment"
            f" Industry Guidelines:\n{media_instructions}"
        )

      # Grounding with detailed media industry pillars & case studies
      from agents.skill_loader import load_skill_reference

      media_pillars = load_skill_reference(
          "media_industry", "industry_pillars.md"
      )
      if media_pillars:
        print(
            "[OutlineWorkflow] Dynamically grounded with detailed media industry"
            " pillars & case studies."
        )
        outline_prompt = (
            f"{outline_prompt}\n\n### Detailed Media Product & Case Study"
            f" Grounding:\n{media_pillars}"
        )

    if sub_industry:
      outline_prompt = (
          f"{outline_prompt}\n\n### Sub-Industry Specific Guidelines:\n"
          f"- The customer operates in the '{sub_industry}' sub-industry.\n"
          f"- Tailor the outline topics, value drivers, and language specifically to '{sub_industry}' business dynamics."
      )

    outline_data = {
        "audience": ", ".join(
            context.get("audience", entities.get("audience", []))
        ),
        "industry": industry,
        "sub_industry": sub_industry,
        "region": context.get("region", entities.get("region", "GLOBAL")),
        "user_request": business_context,
        "customer_data": customer_research,
        "solutions_data": sol_data,
        "outline_items": entities.get("outline_items", []),
    }

    # Redundant open closed by previous faulty edit
    # with open('prompt_templates/outlineGen.txt', 'r') as f:
    #     outline_prompt = f.read()

    response = client.models.generate_content(
        model=self.gemini_model,
        contents=[outline_prompt, json.dumps(outline_data), "\n[output]\n"],
        config=types.GenerateContentConfig(
            system_instruction="Please provide output in json format.",
            response_mime_type="application/json",
            temperature=0,
        ),
    )

    outline = json.loads(response.text)
    outline["sub_industry"] = sub_industry
    return outline
