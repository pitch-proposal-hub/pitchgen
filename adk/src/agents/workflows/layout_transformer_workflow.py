import base64
import json
from google import genai
from google.genai import types
from agents.workflows.base_workflow import BaseWorkflow


class LayoutTransformerWorkflow(BaseWorkflow):

  def __init__(self, config):
    super().__init__(
        "LayoutTransformerWorkflow",
        "Transforms a slide image and options into layout-mapped content.",
    )
    self.config = config
    self.project_id = config["default"].get("project_name", "your-gcp-project-id")
    self.gemini_model = config["default"].get(
        "gemini_model",
        config["default"].get("gemini_model_1", "gemini-3.5-flash-lite"),
    )
    self.region = "global"

  def execute(
      self, slide_layout, slide_category, output_criteria, slide_image_url=None, slide_id=None
  ):
    """Transforms the slide content based on layout, category, output criteria, and base64 image.

    Returns a JSON string representing the mapped placeholder values.
    """
    # Set up Vertex AI client
    client = genai.Client(
        vertexai=True, project=self.project_id, location=self.region
    )

    templates_metadata_map = {
        "Case Study": "templates_metadata/case_study.txt",
        "Charts": "templates_metadata/charts.txt",
        "Circle Charts": "templates_metadata/circle_charts.txt",
        "Context": "templates_metadata/context.txt",
        "Title and content": "templates_metadata/context.txt",
        "Next Steps": "templates_metadata/next_steps.txt",
        "Timeline": "templates_metadata/timeline.txt",
        "GC_AI_Title and content": (
            "templates_metadata/gc_ai_title_and_content.txt"
        ),
        "GC_AI_Divider": "templates_metadata/gc_ai_divider.txt",
        "GC_AI_Agenda": "templates_metadata/gc_ai_agendas.txt",
        "CS_Title and content": "templates_metadata/cs_title_and_content.txt",
        "CS_Divider": "templates_metadata/cs_divider.txt",
        "CS_Agenda": "templates_metadata/cs_agendas.txt",
        "GC_AI_Agenda slides General AI": (
            "templates_metadata/gc_ai_Agenda_slides_General_AI.txt"
        ),
        "GC_AI_Title slides General AI": (
            "templates_metadata/gc_ai_title_slides_general_ai.txt"
        ),
        "GC_AI_Title slides AI agents": (
            "templates_metadata/gc_ai_Title_slides_AI_agents.txt"
        ),
        "GC_AI_Welcome slide Gradient": (
            "templates_metadata/gc_ai_welcome_slide_gradient.txt"
        ),
        "GC_AI_Welcome slide General AI": (
            "templates_metadata/gc_ai_welcome_slide_general_ai.txt"
        ),
        "GC_AI_Welcome slide AI agents": (
            "templates_metadata/gc_ai_Welcome_slide_AI_agents.txt"
        ),
        "GC_AI_Agenda slides AI agents": (
            "templates_metadata/gc_ai_Agenda_slides_AI_agents.txt"
        ),
        "GC_AI_Divider slides Gradient": (
            "templates_metadata/gc_ai_Divider_slides_Gradient.txt"
        ),
        "GC_AI_Divider slides General AI": (
            "templates_metadata/gc_ai_Divider_slides_General_AI.txt"
        ),
        "GC_AI_Divider slides AI agents": (
            "templates_metadata/gc_ai_Divider_slides_AI_agents.txt"
        ),
        "GC_AI_Content slides": "templates_metadata/gc_ai_Content_slides.txt",
        "GC_AI_Speaker slides General AI": (
            "templates_metadata/gc_ai_Speaker_slides_General_AI.txt"
        ),
        "GC_AI_Speaker slides AI agents": (
            "templates_metadata/gc_ai_Speaker_slides_AI_agents.txt"
        ),
        "GC_AI_Key takeaway slides General AI": (
            "templates_metadata/gc_ai_Key_takeaway_slides_General_AI.txt"
        ),
        "GC_AI_Key takeaway slides AI agents": (
            "templates_metadata/gc_ai_Key_takeaway_slides_AI_agents.txt"
        ),
        "GC_AI_Key takeaway slides Gradient": (
            "templates_metadata/gc_ai_Key_takeaway_slides_Gradient.txt"
        ),
        "GC_AI_Quote slides General AI": (
            "templates_metadata/gc_ai_Quote_slides_General_AI.txt"
        ),
        "GC_AI_Quote slides AI agents": (
            "templates_metadata/gc_ai_Quote_slides_AI_agents.txt"
        ),
        "GC_AI_Quote slides Gradient": (
            "templates_metadata/gc_ai_Quote_slides_Gradient.txt"
        ),
        "CS_Chart": "templates_metadata/cs_chart.txt",
        "CS_Content": "templates_metadata/cs_content.txt",
        "CS_Quote": "templates_metadata/cs_quote.txt",
        "CS_Speaker": "templates_metadata/cs_speaker.txt",
        "CS_Stats": "templates_metadata/cs_stats.txt",
        "CS_Timeline": "templates_metadata/cs_timeline.txt",
        "CS_Table": "templates_metadata/cs_table.txt",
        "CS_Title": "templates_metadata/cs_title.txt",
        "Customer References": "templates_metadata/Customer_References.txt",
        "GTM_GTM Layout": "templates_metadata/gtm_gtm_layout.txt",
        "Industry Use Case": "templates_metadata/industry_use_case.txt",
    }

    category_key = slide_category
    prefixed_key = category_key
    if slide_layout == "Google Cloud AI" and not category_key.startswith("GC_AI_"):
      prefixed_key = "GC_AI_" + category_key
    elif slide_layout == "Google Cloudstyle" and not category_key.startswith("CS_"):
      prefixed_key = "CS_" + category_key
    elif slide_layout == "GTM Accelerate" and not category_key.startswith("GTM_"):
      prefixed_key = "GTM_" + category_key

    if prefixed_key in templates_metadata_map:
      category_key = prefixed_key

    template_keys = []
    if slide_id and category_key in templates_metadata_map:
      try:
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        metadata_path = os.path.join(base_dir, templates_metadata_map[category_key])
        with open(metadata_path, 'r', encoding='utf-8') as f:
          meta_json = json.loads(f.read())

        # Look for slide_id in the keys
        for key, val in meta_json.items():
          if slide_id in key:
            template_keys = list(val.keys())
            break
        if not template_keys and meta_json:
          first_val = next(iter(meta_json.values()))
          if isinstance(first_val, dict):
            template_keys = list(first_val.keys())
      except Exception as e:
        print(f"[LayoutTransformerWorkflow] Error loading template keys: {e}")

    keys_instruction = ""
    if template_keys:
      keys_instruction = f"\nThe target template placeholders you MUST map the content to are: {template_keys}. Your output JSON keys must be a subset of these target placeholders. Do not generate any other keys."

    prompt = (
        "You are an expert slide engineer. Transform the slide shown in the"
        f" image based on these parameters:\n- Target Layout: {slide_layout}\n-"
        f" Target Category: {slide_category}\n- Output Criteria:"
        f" {output_criteria}\n\nAnalyze the text, layout, and structure in the"
        " image. Rephrase, enhance, or format the text to fit the new"
        " layout/category according to the output criteria. Return a JSON"
        " object containing keys mapping to text placeholders for this"
        " layout.\n- HEADLINE STYLE: Write the primary slide title in"
        " crisp, conversational, declarative **Sentence case** using **Subject"
        " + finite active verb + outcome** or a **clean noun/contrast phrase**"
        " (44 to 62 chars; capitalize only the first word and proper"
        " nouns/acronyms). NEVER start with '-ing' gerunds, bare imperative"
        " commands, or Title-Case slogans.\n- CARD BODY DENSITY: Write each"
        " card body description"
        " (`header1_content`, `header2_content`, `header3_content`) at 135 to"
        " 165 characters so cards look visually balanced and"
        f" substantive.\n{keys_instruction}\nMake sure your response contains"
        " ONLY the valid JSON object, without any markdown formatting wrappers"
        " (like ```json ... ```)."
    )

    contents = []
    if slide_image_url and slide_image_url.strip():
      try:
        if slide_image_url.startswith("gs://"):
          contents.append(
              types.Part.from_uri(
                  file_uri=slide_image_url, mime_type="image/png"
              )
          )
        else:
          img_data = slide_image_url
          if "," in img_data:
            img_data = img_data.split(",", 1)[1]
          image_bytes = base64.b64decode(img_data)
          image_part = types.Part.from_bytes(
              data=image_bytes, mime_type="image/png"
          )
          contents.append(image_part)
      except Exception as e:
        print(f"[LayoutTransformerWorkflow] Error loading image: {e}")

    contents.append(prompt)

    try:
      response = client.models.generate_content(
          model=self.gemini_model,
          contents=contents,
          config=types.GenerateContentConfig(
              response_mime_type="application/json",
              temperature=0.2,
          ),
      )
      if not response.text:
        raise ValueError("Empty response received from Gemini model.")
      # Ensure it is a valid JSON string
      text_resp = response.text.strip()
      # Double check JSON syntax by parsing
      json.loads(text_resp)
      return text_resp
    except Exception as e:
      print(f"[LayoutTransformerWorkflow] Gemini generation/parsing failed: {e}")
      # Fallback output structure matching expected format
      fallback = {
          "header1": "Driving Innovation with AI Technology",
          "header1_content": "Google Cloud Proprietary Confidential",
      }
      return json.dumps(fallback, indent=2)
