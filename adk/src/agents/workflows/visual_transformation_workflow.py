import base64
from google import genai
from google.genai import types
from agents.workflows.base_workflow import BaseWorkflow
from pitchgen_utils.image_util import get_image_mime_type, clean_base64_data, load_image_part


class VisualTransformationWorkflow(BaseWorkflow):

  def __init__(self, config):
    super().__init__(
        "VisualTransformationWorkflow",
        "Performs slide image transformation using Gemini multimodal"
        " capabilities.",
    )
    self.config = config
    self.gemini_model = config["default"].get("gemini_model", "gemini-3.5-flash")
    self.project_id = config["default"].get("project_name", os.getenv("GOOGLE_CLOUD_PROJECT", "YOUR_PROJECT_ID"))
    self.image_model = config["default"].get(
        "gemini_image_model_1", "gemini-3.1-flash-image"
    )
    self.image_model_fallback = config["default"].get(
        "gemini_image_model_2", "gemini-3.1-pro-image"
    )

  def execute(
      self,
      request,
      existing_slide_image_url,
      theme="",
      layout="",
      industry="",
      sales_play="",
      customer_name="",
      products="",
      solutions="",
      user_input_slide_image_url=None,
      template_slide_image_url=None,
  ):
    """Transforms an existing slide image according to visual requests and parameters.

    Returns a base64 encoded PNG string.
    """
    client = genai.Client(
        vertexai=True, project=self.project_id, location="global"
    )

    from agents.skill_loader import load_skill_instructions, load_skill_reference, detect_industry_category
    import os

    tone_instructions = load_skill_instructions("slide_tone")
    product_instructions = load_skill_instructions("product_knowledge")
    brand_instructions = load_skill_instructions("google_brand")

    # Load industry GTM dynamically
    current_dir = os.path.dirname(os.path.abspath(__file__))
    skills_dir = os.path.join(os.path.dirname(current_dir), "skills")
    if not os.path.exists(skills_dir):
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
            f"{industry_instructions}\n\n### Industry Pillars & Grounding:\n{pillars}"
        )

    # Load play guidelines dynamically
    play_instructions = ""
    if sales_play:
      play_norm = str(sales_play).lower().replace("_", " ").strip()
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
          play_instructions = load_skill_instructions("sales_play_selection")
          play_instructions = (
              f"{play_instructions}\n\n### Specific Play Details:\n{play_details}"
          )

    prompt_parts = [
        "Modify the target image slide according to these instructions:",
        f"- Change request: {request}",
    ]
    if theme:
      prompt_parts.append(f"- Aesthetic theme: {theme}")
    if layout:
      prompt_parts.append(f"- Target layout: {layout}")
    if customer_name:
      prompt_parts.append(f"- Customer name: {customer_name}")
    if industry:
      prompt_parts.append(f"- Industry vertical: {industry}")
    if products:
      prompt_parts.append(f"- Products: {products}")
    if solutions:
      prompt_parts.append(f"- Solutions: {solutions}")

    if tone_instructions:
      prompt_parts.append(f"\n### Slide Tone and Style Guidelines:\n{tone_instructions}")
    if product_instructions:
      prompt_parts.append(f"\n### Google Cloud Product Naming & Branding Guidelines:\n{product_instructions}")
    if brand_instructions:
      prompt_parts.append(f"\n### Google Brand Guidelines:\n{brand_instructions}")
    if industry_instructions:
      prompt_parts.append(f"\n### Google Cloud {detected_industry.capitalize()} Industry Guidelines:\n{industry_instructions}")
    if play_instructions:
      prompt_parts.append(f"\n### Google Cloud Sales Play Guidelines:\n{play_instructions}")

    contents = []
    has_existing = False
    if existing_slide_image_url and existing_slide_image_url.strip():
      try:
        image_part = load_image_part(existing_slide_image_url)
        if image_part:
          contents.append(image_part)
          has_existing = True
      except Exception as e:
        print(f"[VisualTransformationWorkflow] Error loading existing image: {e}")

    has_template = False
    if template_slide_image_url and template_slide_image_url.strip():
      try:
        image_part = load_image_part(template_slide_image_url)
        if image_part:
          contents.append(image_part)
          has_template = True
      except Exception as e:
        print(f"[VisualTransformationWorkflow] Error loading template image: {e}")

    has_ref = False
    if user_input_slide_image_url and user_input_slide_image_url.strip():
      try:
        image_part = load_image_part(user_input_slide_image_url)
        if image_part:
          contents.append(image_part)
          has_ref = True
      except Exception as e:
        print(f"[VisualTransformationWorkflow] Error loading reference image: {e}")

    prompt_str = "\n".join(prompt_parts)
    
    instructions = []
    image_idx = 1
    if has_existing:
      instructions.append(f"- Image {image_idx} is the original slide containing the content to preserve and edit.")
      image_idx += 1
    if has_template:
      instructions.append(f"- Image {image_idx} is the target template slide showing the layout structure and visual style to apply.")
      image_idx += 1
    if has_ref:
      instructions.append(f"- Image {image_idx} is a reference slide for additional structure or style inspiration.")
      image_idx += 1

    if instructions:
      prompt_str += "\n\nInstructions for attached images:\n" + "\n".join(instructions)
      if has_template:
        prompt_str += (
            "\nTransform the original slide to adapt the structure, layout, theme, and visual style of the target template slide"
            f"{' (and use the reference slide for style inspiration)' if has_ref else ''}, while extracting and preserving all text content and data from the original slide and applying the requested edits."
        )
      else:
        prompt_str += "\nTransform the original slide to apply the requested edits while preserving the content."
    else:
      prompt_str += "\n\nPreserve the structure and details where appropriate but execute the requested edits."

    prompt_str += (
        "\n\nCRITICAL: Do NOT write literal layout names (e.g. 'Timeline', 'Circle Charts', 'Stats') or theme names (e.g. 'Google Cloudstyle', 'PitchHub') as text headers or elements on the slide. These are instructions for layout and style choice only. The generated slide must only contain real, polished business text related to the slide's topic."
    )

    contents.append(prompt_str)

    try:
      response = self.generate_content_with_fallback(
          client=client,
          model=self.image_model,
          contents=contents,
          config=types.GenerateContentConfig(
              response_modalities=["IMAGE"],
              temperature=0.4,
              tools=[
                  types.Tool(
                      google_search=types.GoogleSearch(
                          search_types=types.SearchTypes(
                              image_search=types.ImageSearch(),
                              web_search=types.WebSearch(),
                          )
                      )
                  )
              ],
          ),
          fallback_model=self.image_model_fallback,
      )
      image_bytes = None
      if response.candidates and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
          if part.inline_data is not None:
            image_bytes = part.inline_data.data
            break
      if image_bytes:
        return base64.b64encode(image_bytes).decode("utf-8")
    except Exception as e:  # pylint: disable=broad-exception-caught
      print(f"[VisualTransformationWorkflow] Image transformation failed: {e}")

    # Fallback to green dot base64
    return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
