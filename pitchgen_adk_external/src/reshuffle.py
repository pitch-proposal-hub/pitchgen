"""
This module provides functions for reshuffling slides in a presentation deck.

It includes functions to generate slide content based on provided prompts 
using a generative model,as well as functions to reshuffle slides
based on certain criteria.

"""
import json
import base64
import os
import re
import vertexai

from google import genai
from google.genai import types
from vertexai.generative_models import GenerativeModel, Part#, FinishReason

from src.configuration import configuration

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

def generate_data(existing_content, output_criteria, model):
  config = configuration()

  client = genai.Client(
        vertexai=True,
        project=config['default']['project_name'],
        location=config['default']['region'],
  )

  msg1_text1 = types.Part.from_text(text=f"""You will be provided with the existing content that needs to be updated and the output criteria for the new content.

Here is the existing content:{existing_content}

Here is the output criteria for the new content:{output_criteria}

Follow these instructions precisely to complete the task:
1.  **Analyze the Structure:** Carefully examine the provided `existing_content`. Identify its format, layout, and structure (e.g., headings, bullet points, paragraphs, JSON key-value pairs, etc.).
2.  **Review the Criteria:** Thoroughly read and understand all the requirements detailed in the `output_criteria`.
3.  **Generate and Overwrite:** Create the new content strictly based on the `output_criteria`. Use this new content to replace the information in the original structure you identified in step 1.
4.  **Final Output:** Your response must be ONLY the final, updated content. The generated content MUST BE presise, consise and on point. It must follow the exact same structure and format as the `existing_content`. Do not include any extra text, explanations, or introductory phrases like \"Here is the updated content:\".""")
  si_text1 = """You are an Expert Content Editor and Revisor. Your task is to analyze existing content to understand its structure and then generate new content based on a given set of criteria to overwrite the original. You must perfectly preserve the original content's format and structure."""

  #model = model
  contents = [
    types.Content(
      role="user",
      parts=[
        msg1_text1
      ]
    ),
  ]
  tools = [
    types.Tool(google_search=types.GoogleSearch()),
  ]

  generate_content_config = types.GenerateContentConfig(
    temperature = 0,
    top_p = 0.95,
    max_output_tokens = 65535,
    safety_settings = [types.SafetySetting(
      category="HARM_CATEGORY_HATE_SPEECH",
      threshold="OFF"
    ),types.SafetySetting(
      category="HARM_CATEGORY_DANGEROUS_CONTENT",
      threshold="OFF"
    ),types.SafetySetting(
      category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
      threshold="OFF"
    ),types.SafetySetting(
      category="HARM_CATEGORY_HARASSMENT",
      threshold="OFF"
    )],
    tools = tools,
    system_instruction=[types.Part.from_text(text=si_text1)],
    thinking_config=types.ThinkingConfig(
      thinking_budget=-1,
    ),
  )
  text_chunks = []
  for chunk in client.models.generate_content_stream(
    model = model,
    contents = contents,
    config = generate_content_config,
  ):
    if not chunk.candidates or not chunk.candidates[0].content or not chunk.candidates[0].content.parts:
        continue
    
    for part in chunk.candidates[0].content.parts:
        if hasattr(part, 'text') and part.text:
            text_chunks.append(part.text)

  final_response = "".join(text_chunks)
  
  final_response = final_response.replace("```json", "").replace("```", "").strip()

  python_dict = json.loads(final_response)

  return python_dict
#   text_chunks = []
#   for chunk in client.models.generate_content_stream(
#     model = model,
#     contents = contents,
#     config = generate_content_config,
#     ):
#     if not chunk.candidates or not chunk.candidates[0].content or not chunk.candidates[0].content.parts:
#         continue
#     #print(chunk.text, end="")
#     text_chunks.append(chunk.text)

#   final_response = "".join(text_chunks)
#   python_dict = json.loads(final_response)

#   return python_dict

def generate_new(data, output_criteria, model):
    new_dict = {item['shapeId']: item['text'] for item in data['data']}
    json_output = json.dumps(new_dict, indent=4)
    print("Input: \n",json_output)

    received_output = generate_data(json_output, output_criteria, model)
    print("\nOutput: \n",received_output)

    given_input = json.loads(json_output)
    if given_input.keys() == received_output.keys():
        print("\n--- True ---\n")
    else:
        print("\n--- False ---\n")

    print("--- Updating data... ---")
    for item in data['data']:
        shape_id = item['shapeId']

        if shape_id in received_output:
            print(f"Match found! Updating {shape_id}")
            item['text'] = received_output[shape_id]
        else:
            print(f"No match for {shape_id}, skipping.")

    print("\n--- Final Updated Data ---")
    print(json.dumps(data['data'], indent=4))
    
    return data

def generate(model, prompt):
    """
    Generate slide content based on the provided prompt using a generative model.

    Args:
    - prompt (str or list): The prompt or list of prompts to generate content from.

    Returns:
    - str: The generated text content for the slides.
    """
    config=configuration()
    project_id=config['default']['PROJECT_NAME']
    region=config['default']['REGION']
#     vertexai.init(project=project_id, location=region)
#     # model = GenerativeModel("gemini-2.5-pro-preview-0409")
#     # model = GenerativeModel("gemini-1.0-pro-vision-001")
#     model = GenerativeModel("gemini-2.5-pro", system_instruction = ["Please provide output in json format."])
#     # model = GenerativeModel("gemini-1.0-pro-002")

#     generation_config = {
#         # "max_output_tokens": 8192,
#         "top_p": 0.95,
#         "temperature": 0,
# 		"response_mime_type": "application/json"
#     }

#     responses = model.generate_content(
#         prompt,
#         generation_config=generation_config,
#         # stream=True,
#     )
    # for response in responses:
    #   print(response.text, end='')
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
    # return response.text

def reshuffle_slide(input_url, input_data_output_criteria, slide_layout,
                    input_data_slide_category, deck_id, slide_id, model):
    """
    Reshuffles slides in a presentation deck based on provided criteria.

    Args:
    - input_url (str): The URL of the input image.
    - input_data_output_criteria (str): The criteria for the output generated from the input data.
    - slide_layout (str): The layout of the slide.
    - input_data_slide_category (str): The category of the input data slide.
    - deck_id (str): The ID of the deck.
    - slide_id (str): The ID of the slide.

    Returns:
    - dict: A dictionary containing placeholders for the reshuffled slide content.
    """
    config=configuration()
    bucket_name = config['bucket']['TEMPLATE']
    slide_deck_dumps= config['bucket']['SLIDES']
    old_slide = types.Part.from_uri(file_uri=input_url, mime_type='image/png')
    
    old_slide_eg1_path = config.get('examples', 'example_slide_1', fallback=f'{slide_deck_dumps}/examples/example_slide_1.png')
    old_slide_eg1 = types.Part.from_uri(
        file_uri=f'gs://{old_slide_eg1_path}',
        mime_type='image/png'
    )
    
    old_slide_eg2_path = config.get('examples', 'example_slide_2', fallback=f'{slide_deck_dumps}/examples/example_slide_2.png')
    old_slide_eg2 = types.Part.from_uri(
        file_uri=f'gs://{old_slide_eg2_path}',
        mime_type='image/png'
    )
    
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
    if slide_layout == "Google Cloud AI":
      input_data_slide_category = "GC_AI_"+input_data_slide_category
    if slide_layout == "Google Cloudstyle":
      input_data_slide_category = "CS_"+input_data_slide_category 
    if slide_layout == "GTM Accelerate":
      input_data_slide_category = "GTM_"+input_data_slide_category
    with open(templates_metadata[input_data_slide_category], "r") as meta_json:
        meta_json = meta_json.read()
    meta_json = json.loads(meta_json)
    
    new_slide_template = ""
    for key, value in meta_json.items():
        if slide_id in key:
            new_slide_template = value
    new_slide_template = json.dumps(new_slide_template, indent = 2)
    with open("prompt_templates/reshuffle.txt", "r") as prompt_template:
        prompt_template = prompt_template.read()
    prompt_template = prompt_template.split('"""')
    prompt = [
        prompt_template[0],
        old_slide_eg1,
        prompt_template[1],
        old_slide_eg2,
        prompt_template[2],
        old_slide,
        prompt_template[3],
        input_data_output_criteria,
        prompt_template[4],
        new_slide_template,
        prompt_template[5]
    ]
    retry_count = 0
    while retry_count < 2:
        try:
            if retry_count > 0:
                print("retrying...")
            output = generate(model, prompt)
            output = clean_json_string(output)
            output = output.strip()
            output = (output[output.index('{'): (((len(output) - 1) - output[::-1].index('}') + 1))])
            placeholders_json = json.loads(output.strip(), strict=False)
            return placeholders_json
        except:
            retry_count += 1