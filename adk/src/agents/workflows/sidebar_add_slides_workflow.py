"""This module contains functions for generating and adding slides to a presentation deck.

test comment
"""

import json
import os
import re
from google import genai
from google.cloud import storage
from google.genai import types
from config_loader import load_config
from pitchgen_utils.template_sorting import get_placeholders_json


def generate(prompt, model):
  """Generates content for a slide based on the given prompt using a generative model.

  Parameters:
  - prompt (str): The input prompt or context for generating slide content.

  Returns:
  - str: The generated content for the slide.
  """
  config = load_config()
  project_id = config["default"]["project_name"]
  region = config["default"]["region"]
  #     vertexai.init(project=project_id, location=region)
  #     model = GenerativeModel("gemini-3.5-flash", system_instruction = ["Please provide output in json format."])
  #     generation_config = {
  #       "top_p": 0.95,
  #       "temperature": 0,
  # 	  "response_mime_type": "application/json"
  #     }

  #     responses = model.generate_content(
  #         prompt,
  #         generation_config=generation_config
  #     )
  client = genai.Client(
      vertexai=True,
      project=project_id,
      location="global",
  )

  response = client.models.generate_content(
      model=model,
      contents=prompt,
      config=types.GenerateContentConfig(
          system_instruction="Please provide output in json format.",
          response_mime_type="application/json",
          temperature=0,
      ),
  )

  output_text = ""
  if response.candidates and response.candidates[0].content.parts:
    output_text = "".join([
        part.text
        for part in response.candidates[0].content.parts
        if hasattr(part, "text") and part.text
    ])

  return output_text


def image_data_extraction(text, input_data):
  """Generates content for a slide based on the given prompt using a generative model.

  Parameters:
  - prompt (str): The input prompt or context for generating slide content.

  Returns:
  - str: The generated content for the slide.
  """
  config = load_config()
  project_id = config["default"]["project_name"]
  region = config["default"]["region"]
  bucket_name_content = config["bucket"]["content"]
  #     vertexai.init(project=project_id, location=region)

  #     model = GenerativeModel("gemini-3.5-flash")

  #     generation_config = {
  #         "max_output_tokens": 2048,
  #         "top_p": 0.4,
  #         "top_k": 32,
  # 		"response_mime_type": "application/json"
  #     }
  #     response = model.generate_content([text, input_data], generation_config=generation_config)
  client = genai.Client(
      vertexai=True,
      project=project_id,
      location="global",
  )

  response = client.models.generate_content(
      model=config["default"]["gemini_model"],
      contents=[text, input_data],
      config=types.GenerateContentConfig(
          system_instruction="Please provide output in json format.",
          response_mime_type="application/json",
          temperature=0,
      ),
  )

  slide_details_json = ""
  if response.candidates and response.candidates[0].content.parts:
    slide_details_json = "".join([
        part.text
        for part in response.candidates[0].content.parts
        if hasattr(part, "text") and part.text
    ])

  # slide_details_json = response.text

  slide_details_json = slide_details_json.replace("```json", "")
  slide_details_json = slide_details_json.replace("```", "")

  try:
    output_data = json.loads(slide_details_json.strip())
  except json.JSONDecodeError as e:
    print(f"Error decoding JSON: {e}")
    return

  print(json.dumps(output_data, indent=2))

  audiences = output_data.get("Audience", [])
  if audiences != []:
    try:
      try:
        audience = audiences.split(",")
      except Exception as e:
        audience = audiences.split(", ")
    except Exception as e:
      audience = [audiences]
  else:
    audience = audiences
  print("audience:", audience)
  customer_name = output_data.get("Customer Name", "")
  business_context = output_data.get("Business context", "")
  er_number = output_data.get("ER Number", "")
  industry = output_data.get("Industry", "")
  solutions = output_data.get("Solution", [])
  if solutions != []:
    try:
      try:
        solution = solutions.split(", ")
      except Exception as e:
        solution = solutions.split(",")
    except Exception as e:
      solution = [solutions]
  else:
    solution = solutions
  print("solution:", solution)

  filename = f"extracted_slide_details_{customer_name}.json"
  upload_json_from_blob(
      bucket_name_content, json.dumps(output_data, indent=2), filename
  )
  return (
      er_number,
      audience,
      industry,
      solution,
      customer_name,
      business_context,
  )


def upload_json_from_blob(bucket_name, data, file_name):
  """Upload JSON data to a specified Google Cloud Storage bucket.

  Args:
      bucket_name (str): The name of the GCS bucket.
      data (str): The JSON data to upload.
      file_name (str): The name of the file to create in the bucket.
  """
  client = storage.Client()
  bucket = client.bucket(bucket_name)
  blob = bucket.blob(file_name)
  blob.upload_from_string(data, content_type="application/json")


def clean_json_string(json_string):
  """Clean the generated JSON string by ensuring proper escaping and removing any trailing commas or problematic newlines."""
  json_string = json_string.strip()
  json_string = re.sub(r",\s*}", "}", json_string)
  json_string = re.sub(r",\s*]", "]", json_string)
  json_string = json_string.replace(r"\s*\n", r"\n")
  json_string = json_string.replace(r"\s*\r", r"\r")
  return json_string


def add_slide(
    ensemble_retriever,
    slide_title,
    slide_content,
    slide_layout,
    slide_category,
    deck_id,
    slide_id,
    model,
):
  """Adds a new slide to a presentation deck based on given inputs.

  Parameters:
  - ensemble_retriever: An instance of the ensemble retriever used to retrieve
  documents.
  - slide_title (str): The title of the slide to be added.
  - slide_content (str): The content or text of the slide.
  - slide_layout: The layout or format of the slide.
  - slide_category: The category or type of the slide.
  - deck_id (str): The ID of the presentation deck.
  - slide_id (str): The ID of the slide within the deck.

  Returns:
  - dict: A JSON object containing placeholders filled according to the
  generated content.
  """
  docs = ensemble_retriever.retrieve(slide_content)
  text = ""
  for doc in docs:
    text += doc["page_content"]
  text = re.sub(r"\n+", "\n", text)
  text = text[:19000]
  print("\ntext:\n", text)

  if slide_layout == "Google Cloud AI":
    slide_category = "GC_AI_" + slide_category

  if slide_layout == "Google Cloudstyle":
    slide_category = "CS_" + slide_category

  if slide_layout == "GTM Accelerate":
    slide_category = "GTM_" + slide_category

  if not slide_id:
    designer_prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "prompt_templates/add_slide_designer.txt",
    )
    with open(designer_prompt_path, "r") as prompt_template_file:
      prompt_template = prompt_template_file.read()
    prompt = prompt_template.replace("{context}", text).replace("{slide_description}", slide_content)
    designed_slide = generate(prompt, model)
    designed_slide = clean_json_string(designed_slide)
    designed_slide = designed_slide.strip()
    designed_slide = designed_slide[
        designed_slide.index("{") : (
            ((len(designed_slide) - 1) - designed_slide[::-1].index("}") + 1)
        )
    ]
    designed_slide = json.loads(designed_slide.strip(), strict=False)
    slide_title_content = f"""
-----Task 1 Completed successfully-----



Slide Title: {designed_slide['slide_title']}
Slide Content: {designed_slide['slide_content']}

"""
    if not slide_category:
      op_json = get_placeholders_json(slide_title_content, "Context")
      return {
          "deck_id": (
              op_json["agendas"]["0"]["slides"]["1"]["temp_url"]
              .split("d/")[1]
              .split("/")[0]
          ),
          "slide_id": (
              op_json["agendas"]["0"]["slides"]["1"]["temp_url"]
              .split("d/")[1]
              .split("/")[1]
              .split(".")[1]
          ),
          "placeholders": op_json["agendas"]["0"]["slides"]["1"][
              "placeholders"
          ],
      }

    op_json = get_placeholders_json(slide_title_content, slide_category)
    return {
        "deck_id": (
            op_json["agendas"]["0"]["slides"]["1"]["temp_url"]
            .split("d/")[1]
            .split("/")[0]
        ),
        "slide_id": (
            op_json["agendas"]["0"]["slides"]["1"]["temp_url"]
            .split("d/")[1]
            .split("/")[1]
            .split(".")[1]
        ),
        "placeholders": op_json["agendas"]["0"]["slides"]["1"]["placeholders"],
    }

  config = load_config()
  bucket_name = config["bucket"]["template"]
  client = storage.Client()
  bucket = client.bucket(bucket_name)
  templates_metadata = {
      "Case Study": "case_study",
      "Charts": "charts",
      "Circle Charts": "circle_charts",
      "Context": "context",
      "Title and content": "context",
      "Next Steps": "next_steps",
      "Timeline": "timeline",
      "GC_AI_Title and content": "gc_ai_title_and_content",
      "GC_AI_Divider": "gc_ai_divider",
      "GC_AI_Agenda": "gc_ai_agendas",
      "CS_Title and content": "cs_title_and_content",
      "CS_Divider": "cs_divider",
      "CS_Agenda": "cs_agendas",
      "GC_AI_Agenda slides General AI": "gc_ai_Agenda_slides_General_AI",
      "GC_AI_Title slides General AI": "gc_ai_title_slides_general_ai",
      "GC_AI_Title slides AI agents": "gc_ai_Title_slides_AI_agents",
      "GC_AI_Welcome slide Gradient": "gc_ai_welcome_slide_gradient",
      "GC_AI_Welcome slide General AI": "gc_ai_welcome_slide_general_ai",
      "GC_AI_Welcome slide AI agents": "gc_ai_Welcome_slide_AI_agents",
      "GC_AI_Agenda slides AI agents": "gc_ai_Agenda_slides_AI_agents",
      "GC_AI_Divider slides Gradient": "gc_ai_Divider_slides_Gradient",
      "GC_AI_Divider slides General AI": "gc_ai_Divider_slides_General AI",
      "GC_AI_Divider slides AI agents": "gc_ai_Divider_slides_AI_agents",
      "GC_AI_Content slides": "gc_ai_Content_slides",
      "GC_AI_Speaker slides General AI": "gc_ai_Speaker_slides_General_AI",
      "GC_AI_Speaker slides AI agents": "gc_ai_Speaker_slides_AI_agents",
      "GC_AI_Key takeaway slides General AI": "gc_ai_Key_takeaway_slides_General AI",
      "GC_AI_Key takeaway slides AI agents": "gc_ai_Key_takeaway_slides_AI_agents",
      "GC_AI_Key takeaway slides Gradient": "gc_ai_Key_takeaway_slides_Gradient",
      "GC_AI_Quote slides General AI": "gc_ai_Quote_slides_General AI",
      "GC_AI_Quote slides AI agents": "gc_ai_Quote_slides_AI_agents",
      "GC_AI_Quote slides Gradient": "gc_ai_Quote_slides_Gradient",
      "CS_Chart": "cs_chart",
      "CS_Content": "cs_content",
      "CS_Quote": "cs_quote",
      "CS_Speaker": "cs_speaker",
      "CS_Stats": "cs_stats",
      "CS_Timeline": "cs_timeline",
      "CS_Table": "cs_table",
      "CS_Title": "cs_title",
      "Customer References": "Customer_References",
      "GTM_GTM Layout": "gtm_gtm_layout",
      "Industry Use Case": "industry_use_case",
  }

  workflows_dir = os.path.dirname(os.path.abspath(__file__)) # src/agents/workflows
  src_dir = os.path.dirname(os.path.dirname(workflows_dir)) # src/
  
  layout_name = templates_metadata.get(slide_category, "context")
  layout_file = os.path.join(
      src_dir, "prompt_templates", "layouts", f"{layout_name}.json"
  )

  with open(layout_file, "r") as f:
    layout_data = json.load(f)

  # Load templates metadata to map slide_id to template number
  metadata_file = os.path.join(
      src_dir, "templates_metadata", f"{layout_name}.txt"
  )
  
  template_num = None
  if os.path.exists(metadata_file):
    try:
      with open(metadata_file, "r") as f:
        metadata = json.load(f)
      for key in metadata.keys():
        parts = key.split("@")
        if len(parts) >= 3 and parts[2] == slide_id:
          template_num = parts[0]
          break
    except Exception as e:
      print(f"[SidebarAddSlidesWorkflow] Error loading metadata: {e}")

  template = None
  if template_num and template_num in layout_data["templates"]:
    template = layout_data["templates"][template_num]

  if template is None:
    # Fallback to first template placeholders if not found
    first_key = list(layout_data["templates"].keys())[0]
    template = layout_data["templates"][first_key]
  template = json.dumps(template, indent=2)
  add_slide_prompt_path = os.path.join(
      os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
      "prompt_templates/add_slide.txt",
  )
  with open(add_slide_prompt_path, "r") as prompt_template_file:
    prompt_template = prompt_template_file.read()
  if not slide_title:
    slide_title = " "
  prompt = prompt_template.replace("{text}", text).replace("{slide_description}", slide_content).replace("{slide_title}", slide_title).replace("{template}", template)
  retry_count = 0
  while retry_count < 2:
    try:
      if retry_count > 0:
        print("retrying...")
      output = generate(prompt, model)
      output = clean_json_string(output)
      output = output.strip()
      output = output[
          output.index("{") : (
              ((len(output) - 1) - output[::-1].index("}") + 1)
          )
      ]
      placeholders_json = json.loads(output.strip(), strict=False)
      return {
          "deck_id": deck_id,
          "slide_id": slide_id,
          "placeholders": placeholders_json,
      }
    except Exception as e:
      print(e)
      retry_count += 1
      prompt = prompt_template.replace("{text}", text[:10000]).replace("{slide_description}", slide_content).replace("{slide_title}", slide_title).replace("{template}", template)
