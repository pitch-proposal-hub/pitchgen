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
    default_sec = config["default"] if "default" in config else {}
    self.project_id = default_sec.get("project_name", "your-gcp-project-id")
    self.image_model = default_sec.get(
        "gemini_image_model_1", "gemini-3.1-flash-image"
    )
    self.image_model_fallback = default_sec.get(
        "gemini_image_model_2", "gemini-3.1-pro-image"
    )

  def execute(
      self,
      request,
      existing_slide_image_url="",
      theme="",
      layout="",
      industry="",
      sales_play="",
      customer_name="",
      products="",
      solutions="",
      user_input_slide_image_url=None,
      template_slide_image_url=None,
      image_size="2K",
      aspect_ratio=None,
      is_cover_sculpture=False,
      is_in_place_picture=False,
      base64_image=None,
      model_override=None,
  ):
    """Transforms an existing slide image according to visual requests and parameters.

    Returns a base64 encoded PNG string (minimum 1K, defaulting to 2K for title/large visuals).
    """
    if not existing_slide_image_url and base64_image:
      existing_slide_image_url = base64_image
    client = genai.Client(
        vertexai=True, project=self.project_id, location="global"
    )

    from agents.skill_loader import load_skill_instructions, load_skill_reference
    import os

    is_pure_picture_mode = bool(is_cover_sculpture or is_in_place_picture)

    tone_instructions = (
        "" if is_pure_picture_mode else load_skill_instructions("slide_tone")
    )
    product_instructions = (
        ""
        if is_pure_picture_mode
        else load_skill_instructions("product_knowledge")
    )
    brand_instructions = (
        "" if is_pure_picture_mode else load_skill_instructions("google_brand")
    )

    # Load industry GTM dynamically only for full-slide restyling
    from agents.skill_loader import get_domain_and_account_glossary

    industry_instructions = ""
    if not is_pure_picture_mode:
      industry_instructions = (
          load_skill_instructions("industry_verticals") or ""
      )
      glossary = get_domain_and_account_glossary({"industry": industry})
      if glossary:
        industry_instructions = f"{industry_instructions}\n\n{glossary}"

    # Load play guidelines dynamically only for full-slide restyling
    play_instructions = ""
    if sales_play and not is_pure_picture_mode:
      current_dir = os.path.dirname(os.path.abspath(__file__))
      skills_dir = os.path.join(os.path.dirname(current_dir), "skills")
      if not os.path.exists(skills_dir):
        skills_dir = os.path.join(
            os.path.dirname(os.path.dirname(current_dir)),
            "src",
            "agents",
            "skills",
        )
        if not os.path.exists(skills_dir):
          skills_dir = os.path.join(
              os.path.dirname(os.path.dirname(current_dir)), "skills"
          )

      play_norm = str(sales_play).lower().replace("_", " ").strip()
      play_ref_dir = os.path.join(
          skills_dir, "sales_play_selection", "references"
      )
      detected_play_file = None
      if os.path.exists(play_ref_dir):
        ref_files = [f for f in os.listdir(play_ref_dir) if f.endswith(".md")]
        for rf in ref_files:
          play_keywords = rf.replace(".md", "").replace("_", " ").lower()
          if play_keywords in play_norm or play_norm in play_keywords:
            detected_play_file = rf
            break

      if detected_play_file:
        play_details = load_skill_reference(
            "sales_play_selection", detected_play_file
        )
        if play_details:
          play_instructions = load_skill_instructions("sales_play_selection")
          play_instructions = (
              f"{play_instructions}\n\n### Specific Play Details:\n{play_details}"
          )

    if is_pure_picture_mode:
      prompt_parts = [
          (
              "Transform this standalone visual/picture element for the target"
              " account according to these instructions:"
          ),
          f"- Visual transformation request: {request}",
      ]
      if customer_name:
        prompt_parts.append(f"- Target account / brand: {customer_name}")
        if not is_cover_sculpture:
          prompt_parts.append(
              "- White-label replacement rule: 'Cymbal' (including Cymbal"
              " Retail, Cymbal Superstore, Cymbal Shops, and Cymbal product"
              " packaging) is a generic white-label placeholder brand. Replace"
              " all visible 'Cymbal' logos, text, products, and packaging with"
              f" {customer_name} branding and products."
          )
      if industry:
        prompt_parts.append(f"- Account domain: {industry}")
    else:
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
        prompt_parts.append(
            f"\n### Slide Tone and Style Guidelines:\n{tone_instructions}"
        )
      if product_instructions:
        prompt_parts.append(
            "\n### Google Cloud Product Naming & Branding"
            f" Guidelines:\n{product_instructions}"
        )
      if brand_instructions:
        prompt_parts.append(
            f"\n### Google Brand Guidelines:\n{brand_instructions}"
        )
      if industry_instructions:
        ind_title = industry.capitalize() if industry else "Vertical"
        prompt_parts.append(
            f"\n### Google Cloud {ind_title} Industry"
            f" Guidelines:\n{industry_instructions}"
        )
      if play_instructions:
        prompt_parts.append(
            f"\n### Google Cloud Sales Play Guidelines:\n{play_instructions}"
        )

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
      if is_cover_sculpture:
        instructions.append(
            f"- Image {image_idx} is an aesthetic style and lighting reference"
            " ONLY (pitch-black #000000 background, glowing volumetric"
            " point-cloud particle mesh, and gossamer light-field waves). DO"
            " NOT preserve the generic circular ring/torus silhouette from"
            f" Image {image_idx}."
        )
      elif is_in_place_picture:
        instructions.append(
            f"- Image {image_idx} is a standalone picture/visual element"
            " embedded inside a presentation slide (NOT a full slide)."
            f" Preserve Image {image_idx}'s visual medium (e.g., product"
            " photography, lifestyle/studio scene, 3D render, or editorial"
            " illustration), camera angle, lighting, and compositional"
            " balance, while adapting the subject matter, products,"
            " environment, and brand aesthetic to"
            f" {customer_name or 'the target account'}."
        )
      else:
        instructions.append(
            f"- Image {image_idx} is the original slide containing the content"
            " to preserve and edit."
        )
      image_idx += 1
    if has_template:
      instructions.append(
          f"- Image {image_idx} is the target template slide showing the layout"
          " structure and visual style to apply."
      )
      image_idx += 1
    if has_ref:
      instructions.append(
          f"- Image {image_idx} is a reference slide for additional structure"
          " or style inspiration."
      )
      image_idx += 1

    if instructions:
      prompt_str += "\n\nInstructions for attached images:\n" + "\n".join(
          instructions
      )
      if is_cover_sculpture:
        prompt_str += (
            "\nMatch the exact dark-mode glowing particle-wave aesthetic,"
            " volumetric point-cloud density, and pure #000000 black"
            " background of Image 1, but completely morph the 3D sculptural"
            " geometry into an iconic 3D form tailored to"
            f" {customer_name or 'the target customer'}."
        )
      elif is_in_place_picture:
        prompt_str += (
            "\nFocus exclusively on Image 1 and the target account"
            f" ({customer_name or 'the target customer'}). Re-anchor the"
            " objects, products, and environment in Image 1 so they are"
            " unmistakably authentic to"
            f" {customer_name or 'the target customer'} while keeping Image 1's"
            " visual style, framing, and lighting."
        )
      elif has_template:
        prompt_str += (
            "\nTransform the original slide to adapt the structure, layout,"
            " theme, and visual style of the target template"
            f" slide{' (and use the reference slide for style inspiration)' if has_ref else ''},"
            " while extracting and preserving all text content and data from"
            " the original slide and applying the requested edits."
        )
      else:
        prompt_str += (
            "\nTransform the original slide to apply the requested edits while"
            " preserving the content."
        )
    else:
      prompt_str += (
          "\n\nPreserve the structure and details where appropriate but execute"
          " the requested edits."
      )

    if is_pure_picture_mode:
      prompt_str += (
          "\n\nCRITICAL EMBEDDED PICTURE RULE: This image replaces a standalone"
          " picture element inside a slide that ALREADY has its own slide"
          " titles and text boxes outside the image. Render ZERO slide titles,"
          " ZERO caption banners, ZERO bullet points, ZERO UI labels, and ZERO"
          " architecture diagrams inside the image."
      )
    else:
      prompt_str += (
          "\n\nCRITICAL: Do NOT write literal layout names (e.g. 'Timeline',"
          " 'Circle Charts', 'Stats') or theme names (e.g. 'Google Cloudstyle',"
          " 'PitchHub') as text headers or elements on the slide. These are"
          " instructions for layout and style choice only. The generated slide"
          " must only contain real, polished business text related to the"
          " slide's topic."
      )

    contents.append(prompt_str)

    effective_size = str(image_size or "2K").upper()
    if effective_size not in ("1K", "2K", "4K"):
      effective_size = "2K"
    img_cfg_kwargs = {"image_size": effective_size}
    if aspect_ratio in ("1:1", "3:2", "2:3", "4:3", "3:4", "16:9", "9:16"):
      img_cfg_kwargs["aspect_ratio"] = aspect_ratio

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

    try:
      gen_cfg_kwargs = {
          "response_modalities": ["IMAGE"],
          "temperature": 0.4,
          "image_config": types.ImageConfig(**img_cfg_kwargs),
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
      print(f"[VisualTransformationWorkflow] Image transformation failed: {e}")

    # Fallback to green dot base64
    return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
