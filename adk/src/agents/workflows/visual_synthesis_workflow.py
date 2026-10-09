"""Visual synthesis skill for generating slides using multimodal models."""

import base64
from google import genai
from google.genai import types
from agents.workflows.base_workflow import BaseWorkflow
from pitchgen_utils.image_util import get_image_mime_type, clean_base64_data, load_image_part


class VisualSynthesisWorkflow(BaseWorkflow):
  """Generates visual slide content using Gemini image models."""

  def __init__(self, config):
    super().__init__(
        "VisualSynthesisWorkflow",
        (
            "Generates visual slide content using Nano Banana / Gemini 3.0"
            " image models."
        ),
    )
    self.config = config
    default_sec = config["default"] if "default" in config else {}
    self.project_id = default_sec.get("project_name", "your-gcp-project-id")
    self.image_model = default_sec.get(
        "gemini_image_model_1", "gemini-3.1-flash-image"
    )
    self.image_model_fallback = default_sec.get(
        "gemini_image_model_2", "gemini-3.1-pro-image"
    )
    self.disable_image_generation = (
        str(default_sec.get("disable_image_generation", "false")).lower()
        == "true"
    )
    self.region = "global"

  def execute(
      self,
      prompt_text_or_request,
      reference_image=None,
      theme="",
      layout="",
      products="",
      customer_name="",
      industry="",
      solutions="",
      user_input_slide_image_url=None,
      sales_play="",
      template_slide_image_url=None,
      model_override=None,
  ):
    """Generates a net-new slide image.

    Supports both old single-prompt signature and advanced payload signature.

    Args:
      prompt_text_or_request: The description prompt or change request.
      reference_image: Optional reference image to guide style/layout.
      theme: Optional aesthetic theme.
      layout: Optional target layout.
      products: Products to showcase.
      customer_name: Target customer account name.
      industry: Customer's industry vertical.
      solutions: Google Cloud solutions to highlight.
      user_input_slide_image_url: Override reference image URL.
      sales_play: Optional target sales play.

    Returns:
      A base64 encoded PNG string.
    """
    if self.disable_image_generation:
      print(
          "[VisualSynthesisWorkflow] Image generation is disabled. Returning"
          " placeholder base64."
      )
      return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="

    client = genai.Client(
        vertexai=True, project=self.project_id, location=self.region
    )

    # Support both signatures
    if (
        not theme
        and not layout
        and not products
        and not customer_name
        and not industry
        and not solutions
    ):
      # Old monolithic flow
      prompt_str = prompt_text_or_request
      ref_img = user_input_slide_image_url or reference_image
    else:
      # Advanced payload flow
      from agents.skill_loader import load_skill_instructions, load_skill_reference
      import os

      tone_instructions = load_skill_instructions("slide_tone")
      product_instructions = load_skill_instructions("product_knowledge")
      brand_instructions = load_skill_instructions("google_brand")

      # Load industry GTM dynamically
      from agents.skill_loader import get_domain_and_account_glossary

      industry_instructions = load_skill_instructions("industry_verticals") or ""
      glossary = get_domain_and_account_glossary({"industry": industry})
      if glossary:
        industry_instructions = f"{industry_instructions}\n\n{glossary}"

      # Load play guidelines dynamically
      play_instructions = ""
      if sales_play:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        skills_dir = os.path.join(os.path.dirname(current_dir), "skills")
        if not os.path.exists(skills_dir):
          skills_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "src", "agents", "skills")
          if not os.path.exists(skills_dir):
            skills_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "skills")

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
          "Generate a presentation slide with the following constraints:",
          f"- Topic request: {prompt_text_or_request}",
      ]
      if theme:
        prompt_parts.append(f"- Theme: {theme}")
      if layout:
        prompt_parts.append(f"- Layout: {layout}")
      if products:
        prompt_parts.append(f"- Products to highlight: {products}")
      if customer_name:
        prompt_parts.append(f"- Customer name: {customer_name}")
      if industry:
        prompt_parts.append(f"- Industry vertical: {industry}")
      if solutions:
        prompt_parts.append(f"- Solutions: {solutions}")

      if tone_instructions:
        prompt_parts.append(f"\n### Slide Tone and Style Guidelines:\n{tone_instructions}")
      if product_instructions:
        prompt_parts.append(f"\n### Google Cloud Product Naming & Branding Guidelines:\n{product_instructions}")
      if brand_instructions:
        prompt_parts.append(f"\n### Google Brand Guidelines:\n{brand_instructions}")
      if industry_instructions:
        ind_title = industry.capitalize() if industry else "Vertical"
        prompt_parts.append(f"\n### Google Cloud {ind_title} Industry Guidelines:\n{industry_instructions}")
      if play_instructions:
        prompt_parts.append(f"\n### Google Cloud Sales Play Guidelines:\n{play_instructions}")

      prompt_str = (
          "\n".join(prompt_parts)
          + "\n\nPlease render a modern, visually stunning and polished"
          " presentation slide."
          "\n\nCRITICAL: Do NOT write literal layout names (e.g. 'Timeline', 'Circle Charts', 'Stats') or theme names (e.g. 'Google Cloudstyle', 'PitchHub') as text headers or elements on the slide. These are instructions for layout and style choice only. The generated slide must only contain real, polished business text related to the slide's topic."
      )
      ref_img = user_input_slide_image_url or reference_image

    contents = []
    has_template = False
    if template_slide_image_url and template_slide_image_url.strip():
      try:
        image_part = load_image_part(template_slide_image_url)
        if image_part:
          contents.append(image_part)
          has_template = True
      except Exception as e:
        print(f"[VisualSynthesisWorkflow] Error loading template image: {e}")

    has_ref = False
    if ref_img and ref_img.strip():
      try:
        image_part = load_image_part(ref_img)
        if image_part:
          contents.append(image_part)
          has_ref = True
      except Exception as e:
        print(f"[VisualSynthesisWorkflow] Error loading reference image: {e}")

    instructions = []
    image_idx = 1
    if has_template:
      instructions.append(f"- Image {image_idx} is the target template slide showing the layout structure and visual style to apply.")
      image_idx += 1
    if has_ref:
      instructions.append(f"- Image {image_idx} is a reference slide for style and layout inspiration.")
      image_idx += 1

    if instructions:
      prompt_str += "\n\nInstructions for attached images:\n" + "\n".join(instructions)
      if has_template:
        prompt_str += (
            "\nGenerate the new slide by adapting the structure, layout, theme, and visual style of the target template slide"
            f"{' (and use the reference slide for style inspiration)' if has_ref else ''}."
        )
      else:
        prompt_str += "\nUse the attached reference slide as inspiration for the structure, layout, and style."

    contents.append(prompt_str)

    active_model = self.image_model
    active_fallback = self.image_model_fallback
    if model_override:
      mo_clean = str(model_override).strip().lower()
      if "2.1" in mo_clean or "2_1" in mo_clean:
        active_model = "gemini-nano-banana-2.1"
        active_fallback = self.image_model_fallback
      elif "pro" in mo_clean:
        active_model = self.image_model_fallback
        active_fallback = self.image_model
      elif "flash" in mo_clean or mo_clean in ("nano_banana", "nano banana"):
        active_model = self.image_model
        active_fallback = self.image_model_fallback
      elif mo_clean.startswith("gemini-"):
        active_model = str(model_override).strip()

    print(
        "[VisualSynthesisWorkflow] Calling multimodal image generation using"
        f" Nano Banana {active_model}..."
    )
    try:
      gen_cfg_kwargs = {
          "response_modalities": ["IMAGE"],
          "temperature": 0.4,
          "image_config": types.ImageConfig(
              image_size="2K",
              aspect_ratio="16:9",
          ),
      }
      if "flash-image" in str(active_model):
        gen_cfg_kwargs["tools"] = [
            types.Tool(
                google_search=types.GoogleSearch(
                    search_types=types.SearchTypes(
                        image_search=types.ImageSearch(),
                        web_search=types.WebSearch(),
                    )
                )
            )
        ]
      response = self.generate_content_with_fallback(
          client=client,
          model=active_model,
          contents=contents,
          config=types.GenerateContentConfig(**gen_cfg_kwargs),
          fallback_model=active_fallback,
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
      print(f"[VisualSynthesisWorkflow] Image generation failed: {e}")

    # Fallback to red dot base64
    return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
