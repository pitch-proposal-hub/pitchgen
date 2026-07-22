import json
import os
from google import genai
from google.genai import types
from agents.workflows.base_workflow import BaseWorkflow


class ReusableSlideCustomizerWorkflow(BaseWorkflow):

  def __init__(self, config):
    super().__init__(
        "ReusableSlideCustomizerWorkflow",
        "Dynamically customizes retrieved reusable slides to resonate"
        " specifically with the target account.",
    )
    self.config = config
    self.project_id = config["default"]["project_name"]
    self.gemini_model = config["default"]["gemini_model"]
    self.gemini_model_fallback = config["default"].get("gemini_model_1")

  def find_matching_use_case(self, title: str, content: str) -> dict[str, any] | None:
    """Pre-matches the slide title/content to the use case databases."""
    from agents.skill_loader import load_skill_json_database
    import re

    databases = [
        "retail/capture_unified_and_agentic_commerce_grwoth.json",
        "retail/create_the_connected_store.json",
        "retail/drive_sustainable_and_efficient_operations.json",
        "retail/leverage_ai_to_transform_data_into_value.json",
        "power_energy/strategic_foresight.json",
        "power_energy/operational_excellence.json",
        "power_energy/robust_core.json",
    ]

    combined_text = f"{title} {content}".lower()
    slide_words = set(re.findall(r"\w+", combined_text))

    best_match = None
    best_score = 0

    for db_name in databases:
      db = load_skill_json_database("use_case_context", db_name)
      if not db or not isinstance(db, list):
        continue

      for uc in db:
        uc_title = uc.get("use_case_title", "")
        uc_title_words = set(re.findall(r"\w+", uc_title.lower()))

        overlap = slide_words.intersection(uc_title_words)
        score = len(overlap)

        # Extra weight for key themes
        if "supply" in overlap and "chain" in overlap:
          score += 2
        if "forecasting" in overlap or "demand" in overlap:
          score += 2
        if "store" in overlap or "connected" in overlap:
          score += 2
        if "analytics" in overlap or "data" in overlap:
          score += 1

        if score > best_score:
          best_score = score
          best_match = uc

    return best_match if best_score >= 1 else None

  def execute(self, suggestion, context):
    """Customizes the slide suggestion text based on target account context."""
    original_title = suggestion.get("original_title", "")
    original_content = suggestion.get("original_content", "")

    if not original_title and not original_content:
      return {}

    customer_name = context.get("customer_name", "Starbucks")
    industry = context.get("industry", "Retail")

    # 1. Load Dynamic Guidelines from active skills!
    from agents.skill_loader import load_skill_instructions, load_skill_reference, detect_industry_category

    client = genai.Client(
        vertexai=True, project=self.project_id, location="global"
    )

    tone_instructions = load_skill_instructions("slide_tone")
    product_instructions = load_skill_instructions("product_knowledge")

    # Load industry GTM dynamically
    current_dir = os.path.dirname(os.path.abspath(__file__))
    skills_dir = os.path.join(os.path.dirname(current_dir), "skills")
    if not os.path.exists(skills_dir):
      # Fallback to local structure inside workspace
      skills_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "src", "agents", "skills")
      if not os.path.exists(skills_dir):
        skills_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "skills")

    available_industries = []
    if os.path.exists(skills_dir):
      available_industries = [
          d.replace("_industry", "")
          for d in os.listdir(skills_dir)
          if os.path.isdir(os.path.join(skills_dir, d)) and d.endswith("_industry")
      ]

    detected_industry = None
    if industry:
      mapped_ind = detect_industry_category(client, self.gemini_model, industry, available_industries)
      if mapped_ind != "None":
        detected_industry = mapped_ind

    industry_instructions = ""
    if detected_industry:
      industry_skill = f"{detected_industry}_industry"
      industry_instructions = load_skill_instructions(industry_skill)
      pillars = load_skill_reference(industry_skill, "industry_pillars.md")
      if pillars:
        industry_instructions = (
            f"{industry_instructions}\n\n### Pillars & Grounding:\n{pillars}"
        )

    # Load play guidelines dynamically
    play_instructions = load_skill_instructions("sales_play_selection")

    # Extract play name
    play_selected = context.get("salesPlay") or ""
    if isinstance(play_selected, list):
      play_norm = ",".join(play_selected).lower().replace("_", " ").strip()
    else:
      play_norm = str(play_selected).lower().replace("_", " ").strip()

    play_ref_dir = os.path.join(skills_dir, "sales_play_selection", "references")
    detected_play_file = None
    if os.path.exists(play_ref_dir):
      ref_files = [f for f in os.listdir(play_ref_dir) if f.endswith(".md")]
      for rf in ref_files:
        play_keywords = rf.replace(".md", "").replace("_", " ").lower()
        if play_keywords in play_norm or play_norm in play_keywords:
          detected_play_file = rf
          break

    if detected_play_file:
      play_details = load_skill_reference("sales_play_selection", detected_play_file)
      if play_details:
        play_instructions = (
            f"{play_instructions}\n\n### Specific Play Details:\n{play_details}"
        )


    # Find matching use case for grounding
    use_case = self.find_matching_use_case(original_title, original_content)
    use_case_grounding = ""
    if use_case:
      print(
          "[ReusableSlideCustomizerWorkflow] Grounding customization of"
          f" '{original_title}' with use case: '{use_case.get('use_case_title')}'"
      )
      use_case_grounding = (
          "\n### Official Use Case Grounding Context:\n"
          f"{json.dumps(use_case, indent=2)}\n"
      )

    # Load Segment Targeting instructions if applicable
    segment_instructions = ""
    audience_input = context.get("audience", "")
    if isinstance(audience_input, str):
      audience_tokens = [a.lower().strip() for a in audience_input.split(",")]
    elif isinstance(audience_input, list):
      audience_tokens = [str(a).lower().strip() for a in audience_input]
    else:
      audience_tokens = []

    has_segment = any(
        s in audience_tokens
        for s in ["segment", "smb", "startups", "corporate", "enterprise", "strategic"]
    )
    if has_segment:
      segment_instructions = load_skill_instructions("segment_targeting")

    # 2. Compile customizer prompt
    system_instruction = (
        "You are an expert Google Cloud GTM presentation editor."
    )
    if tone_instructions:
      system_instruction = (
          f"{system_instruction}\n\n### Slide Tone"
          f" Guidelines:\n{tone_instructions}"
      )
    if segment_instructions:
      system_instruction = (
          f"{system_instruction}\n\n### Customer Segment Targeting"
          f" Guidelines:\n{segment_instructions}"
      )
    if product_instructions:
      system_instruction = (
          f"{system_instruction}\n\n### Product Grounding"
          f" Guidelines:\n{product_instructions}"
      )

    sub_industry = context.get("sub_industry", "")
    sub_industry_prompt = ""
    if sub_industry:
      sub_industry_prompt = f"Target Sub-Industry: {sub_industry}\n"

    prompt = f"""Customize the following approved, retrieved Google Cloud slide content to resonate specifically with the target account.

Target Account: {customer_name}
Target Industry: {industry}
{sub_industry_prompt}
### Target Industry GTM Guidelines:
{industry_instructions}

### Target Sales Play Guidelines:
{play_instructions}
{use_case_grounding}
### Original Slide Data to Tailor:
Original Title: {original_title}
Original Content: {original_content}

Rules for Customization:
1. Contextual Reference Replacement (Avoid Blind Swapping):
   - DO NOT replace generic industry terms in industry-wide trends, statistics, or benchmarks (e.g., "78% of retailers face X" must NOT become "78% of {customer_name} face X"). Keep it general, or frame it as "{customer_name}'s peers in the {industry} industry face X".
   - DO replace generic placeholders when referring to Google Cloud partnerships, solutions, or value delivery (e.g., "helping retailers modernize" should become "helping {customer_name} modernize").
2. Soften Presumptive/Accusatory Statements:
   - Avoid stating that {customer_name} struggles with a challenge unless it is confirmed by the provided context or grounding. Instead, frame it as a common industry challenge that {customer_name} is addressing (e.g., "To address the industry-wide challenge of X, {customer_name} can...").
3. Segment and Sub-Industry Alignment:
   - Tailor the terminology, metrics, and tone to align with {customer_name}'s customer segment and sub-industry.
   - For example, if sub-industry is QSR, prioritize terms like 'franchisees', 'drive-thru operations', 'menu management', and 'guest experience'. If it is Grocery, prioritize 'basket size', 'fresh food shrinkage', 'aisles', and 'in-store shoppers'.
4. Grounding and Alignment:
   - Ground the customization using the provided "Official Use Case Grounding Context" (if available), aligning the value proposition, value drivers, and KPIs with the official guidelines.
   - Align the customized benefit points directly with {customer_name}'s business domain and vocabulary.
5. Maintain Presentation Integrity:
   - Maintain the original slide layout structure and keep all technical Google Cloud product names intact. Do not add or hallucinate new products.
6. Tone:
   - Enforce our active slide tone guidelines (brief, punchy, direct, conversational).

Return the customized slide content strictly in this JSON format:
{{
  "customized_title": "Tailored Title",
  "customized_content": "Tailored slide content bullet points or text"
}}
"""

    client = genai.Client(
        vertexai=True, project=self.project_id, location="global"
    )

    try:
      response = self.generate_content_with_fallback(
          client=client,
          model=self.gemini_model,
          contents=prompt,
          config=types.GenerateContentConfig(
              response_mime_type="application/json",
              system_instruction=system_instruction,
              temperature=0.3,
          ),
          fallback_model=self.gemini_model_fallback,
      )

      response_json = json.loads(response.text)
      if isinstance(response_json, list) and len(response_json) > 0:
        response_json = response_json[0]

      print(
          "[ReusableSlideCustomizerWorkflow] Successfully customized slide"
          f" '{original_title}' for {customer_name}!"
      )
      return response_json

    except Exception as e:
      print(f"[ReusableSlideCustomizerWorkflow] Error customising slide: {e}")
      return {
          "customized_title": original_title,
          "customized_content": original_content,
      }
