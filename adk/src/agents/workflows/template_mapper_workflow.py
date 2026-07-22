import json
import os
from google import genai
from google.genai import types
from agents.workflows.base_workflow import BaseWorkflow


class TemplateMapperWorkflow(BaseWorkflow):

  def __init__(self, config):
    super().__init__(
        "TemplateMapperWorkflow",
        "Maps generated text to Google Slides placeholders.",
    )
    self.config = config
    self.project_id = config["default"]["project_name"]
    self.gemini_model = config["default"]["gemini_model_1"]

    self.layout_mapping = {
        "Context": "context",
        "Title and content": "context",
        "Case Study": "case_study",
        "Charts": "charts",
        "Circle Charts": "circle_charts",
        "Next Steps": "next_steps",
        "Timeline": "timeline",
        "Industry Use Case": "industry_use_case",
        # GC AI Brand Slides - Always enforce the 'AI_agents' style layouts
        "GC_AI_Title": "gc_ai_Title_slides_AI_agents",
        "GC_AI_Agenda": "gc_ai_Agenda_slides_AI_agents",
        "GC_AI_Divider": "gc_ai_Divider_slides_AI_agents",
        "GC_AI_Welcome": "gc_ai_Welcome_slide_AI_agents",
        "GC_AI_Speaker": "gc_ai_Speaker_slides_AI_agents",
        "GC_AI_Quote": "gc_ai_Quote_slides_AI_agents",
        "GC_AI_Key_takeaway": "gc_ai_Key_takeaway_slides_AI_agents",
    }

  def execute(
      self, slide_title, slide_content, layout="Context", used_slide_ids=None
  ):
    if used_slide_ids is None:
      used_slide_ids = []
    
    workflows_dir = os.path.dirname(os.path.abspath(__file__)) # src/agents/workflows
    src_dir = os.path.dirname(os.path.dirname(workflows_dir)) # src/

    # 1. Load consolidated layout JSON
    layout_file_part = self.layout_mapping.get(layout, "context")
    layout_file = os.path.join(
        src_dir, "prompt_templates", "layouts", f"{layout_file_part}.json"
    )

    if not os.path.exists(layout_file):
      # Fallback to context if specific layout file doesn't exist
      layout_file = os.path.join(
          src_dir, "prompt_templates", "layouts", "context.json"
      )

    with open(layout_file, "r") as f:
      layout_data = json.load(f)

    # Load metadata file to map template numbers to deck_id and slide_id
    metadata_file = os.path.join(
        src_dir, "templates_metadata", f"{layout_file_part}.txt"
    )
    template_coords = {}
    if os.path.exists(metadata_file):
      try:
        with open(metadata_file, "r") as f:
          metadata = json.load(f)
        for key in metadata.keys():
          parts = key.split("@")
          if len(parts) >= 3:
            template_coords[parts[0]] = {
                "deck_id": parts[1],
                "slide_id": parts[2]
            }
      except Exception as e:
        print(f"[TemplateMapperWorkflow] Error loading template metadata: {e}")

    # Resolve already used template numbers for LLM-based deduplication
    used_templates = []
    for t_num in layout_data["templates"].keys():
      coords = template_coords.get(t_num)
      if coords and coords["slide_id"] in used_slide_ids:
        used_templates.append(t_num)

    # 2. Build and compile prompt dynamically from template_sorter_base.txt
    templates_prompt_schema = {}
    for t_num, t_info in layout_data["templates"].items():
      templates_prompt_schema[t_num] = t_info

    base_prompt_file = os.path.join(
        src_dir, "prompt_templates", "template_sorter_base.txt"
    )
    with open(base_prompt_file, "r") as f:
      base_prompt = f.read()

    used_templates_instruction = ""
    if used_templates:
      used_templates_instruction = (
          f"\nAlready Used Templates: {used_templates}. Avoid choosing these"
          " templates to ensure visual variety and avoid repetitions. Prefer"
          " other compatible layouts.\n"
      )

    input_text = f"Slide Title: {slide_title}\nSlide Content: {slide_content}"

    full_prompt = base_prompt.format(
        templates=json.dumps(templates_prompt_schema, indent=2),
        used_templates_instruction=used_templates_instruction,
        examples=layout_data.get("examples", ""),
        input_text=input_text,
    )

    client = genai.Client(
        vertexai=True, project=self.project_id, location="global"
    )

    import time
    import random

    max_retries = 6
    base_delay = 2.0
    response = None

    for attempt in range(max_retries):
      try:
        response = client.models.generate_content(
            model=self.gemini_model,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0,
            ),
        )
        break
      except Exception as e:
        err_msg = str(e).lower()
        if "429" in err_msg or "resource_exhausted" in err_msg or "rate limit" in err_msg:
          if attempt == max_retries - 1:
            print(f"[TemplateMapperWorkflow] Quota exhausted after {max_retries} attempts.")
            raise e
          sleep_time = (base_delay ** attempt) + random.uniform(0, 1.0)
          print(f"[TemplateMapperWorkflow] Rate limit (429) hit. Retrying in {sleep_time:.2f}s... (Attempt {attempt+1}/{max_retries})")
          time.sleep(sleep_time)
        else:
          raise e

    response_json = json.loads(response.text)
    if isinstance(response_json, list) and len(response_json) > 0:
      response_json = response_json[0]

    # 3. Resolve template coordinates
    template_num = str(response_json.get("template"))
    coords = template_coords.get(template_num)

    if not coords:
      print(f"[TemplateMapperWorkflow] Warning: Template {template_num} not found in metadata. Falling back to first template.")
      first_key = list(layout_data["templates"].keys())[0]
      coords = template_coords.get(first_key)

    if coords:
      slide_id = coords["slide_id"]
      deck_id = coords["deck_id"]
    else:
      slide_id = ""
      deck_id = ""

    # Failsafe post-processing deduplication
    if slide_id and slide_id in used_slide_ids:
      print(f"[TemplateMapperWorkflow] Failsafe: Slide ID '{slide_id}' already used. Finding structural alternative...")
      target_schema_keys = set(layout_data["templates"].get(template_num, {}).keys())

      for alt_num, alt_placeholders in layout_data["templates"].items():
        alt_coords = template_coords.get(alt_num)
        if (
            alt_coords
            and alt_coords["slide_id"] not in used_slide_ids
            and set(alt_placeholders.keys()) == target_schema_keys
        ):
          print(f"[TemplateMapperWorkflow] Failsafe alternative found: Template '{alt_num}'")
          coords = alt_coords
          slide_id = coords["slide_id"]
          deck_id = coords["deck_id"]
          break

    temp_url = f"https://docs.google.com/presentation/d/{deck_id}/edit#slide=id.{slide_id}" if slide_id else None

    # Dynamically load Speaker Notes guidelines and generate notes
    from agents.skill_loader import load_skill_instructions

    notes_instructions = load_skill_instructions("speaker_notes")

    speaker_notes = ""
    if notes_instructions:
      print(
          "[TemplateMapperWorkflow] Dynamically loaded 'speaker_notes' guidelines."
          " Generating notes..."
      )
      notes_prompt = f"""Generate speaker notes for this slide following these guidelines.
            
            Guidelines:
            {notes_instructions}
            
            Slide Data:
            Title: {slide_title}
            Content: {json.dumps(response_json.get("placeholders", {}))}
            """

      notes_response = client.models.generate_content(
          model=self.gemini_model, contents=notes_prompt
      )
      speaker_notes = notes_response.text.strip() if notes_response.text else ""

    return {
        "temp_url": temp_url,
        "slide_id": slide_id,
        "placeholders": response_json.get("placeholders", {}),
        "speaker_notes": speaker_notes,
    }
