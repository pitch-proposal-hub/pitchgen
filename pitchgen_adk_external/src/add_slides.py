"""
This module contains functions for generating and adding slides to a presentation deck.
test comment
"""

import json
import re
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.cloud import storage
from google import genai
from google.genai import types

from src.configuration import configuration
from src.template_sorting import get_placeholders_json

def generate(prompt, model):
    """
    Generates content for a slide based on the given prompt using a generative model.

    Parameters:
    - prompt (str): The input prompt or context for generating slide content.

    Returns:
    - str: The generated content for the slide.
    """
    config=configuration()
    project_id = config['default']['PROJECT_NAME']
    region = config['default']['REGION']
#     vertexai.init(project=project_id, location=region)
#     model = GenerativeModel("gemini-2.5-pro", system_instruction = ["Please provide output in json format."])
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
        project=config['default']['PROJECT_NAME'], 
        location=config['default']['region']
    )

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction="Please provide output in json format.",
            response_mime_type="application/json",
            temperature=0,
        )
    )

    output_text = ""
    if response.candidates and response.candidates[0].content.parts:
        output_text = "".join([
            part.text for part in response.candidates[0].content.parts 
            if hasattr(part, 'text') and part.text
        ])
    
    return output_text

def image_data_extraction(text, input_data):
    """
    Generates content for a slide based on the given prompt using a generative model.

    Parameters:
    - prompt (str): The input prompt or context for generating slide content.

    Returns:
    - str: The generated content for the slide.
    """
    config=configuration()
    project_id = config['default']['PROJECT_NAME']
    region = config['default']['REGION']
    bucket_name_content = config['bucket']['CONTENT']
#     vertexai.init(project=project_id, location=region)

#     model = GenerativeModel("gemini-2.5-pro")

#     generation_config = {
#         "max_output_tokens": 2048,
#         "top_p": 0.4,
#         "top_k": 32,
# 		"response_mime_type": "application/json"
#     }
#     response = model.generate_content([text, input_data], generation_config=generation_config)
    client = genai.Client(
        vertexai=True, 
        project=config['default']['PROJECT_NAME'], 
        location=config['default']['region']
    )

    response = client.models.generate_content(
        model=config['default']['GEMINI_MODEL'],
        contents=[text, input_data],
        config=types.GenerateContentConfig(
            system_instruction="Please provide output in json format.",
            response_mime_type="application/json",
            temperature=0,
        )
    )

    slide_details_json = ""
    if response.candidates and response.candidates[0].content.parts:
        slide_details_json = "".join([
            part.text for part in response.candidates[0].content.parts 
            if hasattr(part, 'text') and part.text
        ])
    
    #slide_details_json = response.text

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
    print("audience:",audience)
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
    print("solution:",solution)
    
    

    filename = f"extracted_slide_details_{customer_name}.json"  
    upload_json_from_blob(bucket_name_content, json.dumps(output_data, indent=2), filename)
    return er_number, audience, industry, solution, customer_name, business_context

def upload_json_from_blob(bucket_name, data, file_name):
    """
    Upload JSON data to a specified Google Cloud Storage bucket.

    Args:
        bucket_name (str): The name of the GCS bucket.
        data (str): The JSON data to upload.
        file_name (str): The name of the file to create in the bucket.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    blob.upload_from_string(data, content_type='application/json')


def clean_json_string(json_string):
  """
  Clean the generated JSON string by ensuring proper escaping and removing any trailing commas or problematic newlines.
  """
  json_string = json_string.strip()
  json_string = re.sub(r',\s*}', '}', json_string)
  json_string = re.sub(r',\s*]', ']', json_string)
  json_string = json_string.replace(r'\s*\n', r'\n')
  json_string = json_string.replace(r'\s*\r', r'\r')
  return json_string

def add_slide(ensemble_retriever, slide_title, slide_content, slide_layout, slide_category, deck_id, slide_id, model):
    """
    Adds a new slide to a presentation deck based on given inputs.

    Parameters:
    - ensemble_retriever: An instance of the ensemble retriever used to retrieve documents.
    - slide_title (str): The title of the slide to be added.
    - slide_content (str): The content or text of the slide.
    - slide_layout: The layout or format of the slide.
    - slide_category: The category or type of the slide.
    - deck_id (str): The ID of the presentation deck.
    - slide_id (str): The ID of the slide within the deck.

    Returns:
    - dict: A JSON object containing placeholders filled according to the generated content.
    """
    docs = ensemble_retriever.retrieve(slide_content)
    text = ''
    for doc in docs:
        text += doc["page_content"]
    text = re.sub(r'\n+', '\n', text)
    text = text[:19000]
    print("\ntext:\n", text)

    if slide_layout == "Google Cloud AI":
        slide_category = "GC_AI_"+slide_category
    
    if slide_layout == "Google Cloudstyle":
        slide_category = "CS_"+slide_category

    if slide_layout == "GTM Accelerate":
        slide_category = "GTM_"+slide_category
        
    if not slide_id:
      with open("prompt_templates/add_slide_designer.txt", "r") as prompt_template:
        prompt_template = prompt_template.read()
      prompt_template = prompt_template.split('"""')
      prompt = [
        prompt_template[0],
        text,
        prompt_template[1],
        slide_content,
        prompt_template[2]
      ]
      designed_slide = generate(prompt, model)
      designed_slide = clean_json_string(designed_slide)
      designed_slide = designed_slide.strip()
      designed_slide = (designed_slide[designed_slide.index('{'): (((len(designed_slide) - 1) - designed_slide[::-1].index('}') + 1))])
      designed_slide = json.loads(designed_slide.strip(), strict=False)
      slide_title_content = f"""
-----Task 1 Completed successfully-----



Slide Title: {designed_slide['slide_title']}
Slide Content: {designed_slide['slide_content']}

"""
      if not slide_category:
        op_json = get_placeholders_json(slide_title_content, "Context")
        return {
          "deck_id":op_json['agendas']['0']['slides']['1']['temp_url'].split('d/')[1].split('/')[0],
          "slide_id":op_json['agendas']['0']['slides']['1']['temp_url'].split('d/')[1].split('/')[1].split('.')[1],
          "placeholders":op_json['agendas']['0']['slides']['1']['placeholders']
        }

      
        
      op_json = get_placeholders_json(slide_title_content, slide_category)
      return {
          "deck_id":op_json['agendas']['0']['slides']['1']['temp_url'].split('d/')[1].split('/')[0],
          "slide_id":op_json['agendas']['0']['slides']['1']['temp_url'].split('d/')[1].split('/')[1].split('.')[1],
          "placeholders":op_json['agendas']['0']['slides']['1']['placeholders']
        }
    
      
      
    config=configuration()
    bucket_name = config['bucket']['TEMPLATE']
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    templates_metadata = {
        "Case Study": "templates_metadata/case_study.txt",
        "Charts": "templates_metadata/charts.txt",
        "Circle Charts": "templates_metadata/circle_charts.txt",
        "Context": "templates_metadata/context.txt",
        "Next Steps": "templates_metadata/next_steps.txt",
        "Timeline": "templates_metadata/timeline.txt",
        "GC_AI_Title and content": "templates_metadata/gc_ai_title_and_content.txt",
        "GC_AI_Divider": "templates_metadata/gc_ai_divider.txt",
        "GC_AI_Agenda": "templates_metadata/gc_ai_agendas.txt",
        "CS_Title and content": "templates_metadata/cs_title_and_content.txt",
        "CS_Divider": "templates_metadata/cs_divider.txt",
        "CS_Agenda": "templates_metadata/cs_agendas.txt",
        "GC_AI_Agenda slides General AI": "templates_metadata/gc_ai_Agenda_slides_General_AI.txt",
        "GC_AI_Title slides General AI": "templates_metadata/gc_ai_title_slides_general_ai.txt",
        "GC_AI_Title slides AI agents": "templates_metadata/gc_ai_Title_slides_AI_agents.txt",
        "GC_AI_Welcome slide Gradient": "templates_metadata/gc_ai_welcome_slide_gradient.txt",
        "GC_AI_Welcome slide General AI": "templates_metadata/gc_ai_welcome_slide_general_ai.txt",
        "GC_AI_Welcome slide AI agents": "templates_metadata/gc_ai_Welcome_slide_AI_agents.txt",
        "GC_AI_Agenda slides AI agents": "templates_metadata/gc_ai_Agenda_slides_AI_agents.txt",
        "GC_AI_Divider slides Gradient": "templates_metadata/gc_ai_Divider_slides_Gradient.txt",
        "GC_AI_Divider slides General AI": "templates_metadata/gc_ai_Divider_slides_General AI.txt",
        "GC_AI_Divider slides AI agents": "templates_metadata/gc_ai_Divider_slides_AI_agents.txt",
        "GC_AI_Content slides": "templates_metadata/gc_ai_Content_slides.txt",
        "GC_AI_Speaker slides General AI": "templates_metadata/gc_ai_Speaker_slides_General_AI.txt",
        "GC_AI_Speaker slides AI agents": "templates_metadata/gc_ai_Speaker_slides_AI_agents.txt",
        "GC_AI_Key takeaway slides General AI": "templates_metadata/gc_ai_Key_takeaway_slides_General AI.txt",
        "GC_AI_Key takeaway slides AI agents": "templates_metadata/gc_ai_Key_takeaway_slides_AI_agents.txt",
        "GC_AI_Key takeaway slides Gradient": "templates_metadata/gc_ai_Key_takeaway_slides_Gradient.txt",
        "GC_AI_Quote slides General AI": "templates_metadata/gc_ai_Quote_slides_General AI.txt",
        "GC_AI_Quote slides AI agents": "templates_metadata/gc_ai_Quote_slides_AI_agents.txt",
        "GC_AI_Quote slides Gradient": "templates_metadata/gc_ai_Quote_slides_Gradient.txt",
        "CS_Chart":"templates_metadata/cs_chart.txt",
        "CS_Content":"templates_metadata/cs_content.txt",
        "CS_Quote":"templates_metadata/cs_quote.txt",
        "CS_Speaker":"templates_metadata/cs_speaker.txt",
        "CS_Stats":"templates_metadata/cs_stats.txt",
        "CS_Timeline":"templates_metadata/cs_timeline.txt",
        "CS_Table":"templates_metadata/cs_table.txt",
        "CS_Title":"templates_metadata/cs_title.txt",
        "Customer References":"templates_metadata/Customer_References.txt",
        "GTM_GTM Layout":"templates_metadata/gtm_gtm_layout.txt"
    }
    
    with open(templates_metadata[slide_category], "r") as meta_json:
        meta_json = meta_json.read()
    meta_json = json.loads(meta_json)
    
    
    template = ""
    for key, value in meta_json.items():
        if slide_id in key:
            template = value
    template = json.dumps(template, indent = 2)
    with open("prompt_templates/add_slide.txt", "r") as prompt_template:
        prompt_template = prompt_template.read()
    prompt_template = prompt_template.split('"""')
    if not slide_title:
      slide_title = ' '
    prompt = [
        prompt_template[0],
        text,
        prompt_template[1],
        slide_content,
        prompt_template[2],
        slide_title,
        prompt_template[3],
        template,
        prompt_template[4]
    ]
    retry_count = 0
    while retry_count < 2:
        try:
            if retry_count > 0:
                print("retrying...")
            output = generate(prompt, model)
            output = clean_json_string(output)
            output = output.strip()
            output = ( output[output.index('{'): (((len(output) - 1) - output[::-1].index('}') + 1))])
            placeholders_json = json.loads(output.strip(), strict=False)
            return {
              "deck_id":deck_id,
              "slide_id":slide_id,
              "placeholders":placeholders_json
            }
        except Exception as e:
            print(e)
            retry_count += 1
            prompt[1] = text[:10000]