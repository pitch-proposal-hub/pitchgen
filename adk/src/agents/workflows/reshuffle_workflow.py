import json
import os
import re
from google import genai
from google.cloud import storage
from google.genai import types
from pitchgen_utils.gcs_util import read_gcs_file
from agents.workflows.base_workflow import BaseWorkflow


class SlideReshuffler:
  """Class to perform slide layout transformation and content revision using Gemini Multimodal."""

  def __init__(self, config):
    self.config = config
    self.project_id = config['default']['project_name']
    self.__location = 'global'
    self.gemini_model = config['default']['gemini_model']
    self.storage_client = storage.Client(project=self.project_id)
    self.bucket_name = config['bucket']['content']
    self.bucket = self.storage_client.bucket(self.bucket_name)
    self.bucket_slides = config['bucket']['slides']

    self.current_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )

  def clean_json_string(self, json_string):
    json_string = json_string.strip()
    json_string = re.sub(r',\s*}', '}', json_string)
    json_string = re.sub(r',\s*]', ']', json_string)
    json_string = json_string.replace(r'\s*\n', r'\n')
    json_string = json_string.replace(r'\s*\r', r'\r')
    return json_string

  def generate_data(self, existing_content, output_criteria):
    client = genai.Client(
        vertexai=True,
        project=self.project_id,
        location='global',
    )

    msg1_text1 = types.Part.from_text(
        text=(
            'You will be provided with the existing content that needs to be'
            ' updated and the output criteria for the new content.\n\nHere is'
            f' the existing content:{existing_content}\n\nHere is the output'
            f' criteria for the new content:{output_criteria}\n\nFollow these'
            ' instructions precisely to complete the task:\n1.  **Analyze the'
            ' Structure:** Carefully examine the provided `existing_content`.'
            ' Identify its format, layout, and structure (e.g., headings,'
            ' bullet points, paragraphs, JSON key-value pairs, etc.).\n2. '
            ' **Review the Criteria:** Thoroughly read and understand all the'
            ' requirements detailed in the `output_criteria`.\n3.  **Generate'
            ' and Overwrite:** Create the new content strictly based on the'
            ' `output_criteria`. Use this new content to replace the'
            ' information in the original structure you identified in step'
            ' 1.\n4.  **Final Output:** Your response must be ONLY the final,'
            ' updated content. The generated content MUST BE presise, consise'
            ' and on point. It must follow the exact same structure and format'
            ' as the `existing_content`. Do not include any extra text,'
            ' explanations, or introductory phrases like "Here is the updated'
            ' content:".'
        )
    )
    si_text1 = (
        'You are an Expert Content Editor and Revisor. Your task is to analyze'
        ' existing content to understand its structure and then generate new'
        ' content based on a given set of criteria to overwrite the original.'
        " You must perfectly preserve the original content's format and"
        ' structure.'
    )

    contents = [
        types.Content(role='user', parts=[msg1_text1]),
    ]
    tools = [
        types.Tool(google_search=types.GoogleSearch()),
    ]

    generate_content_config = types.GenerateContentConfig(
        temperature=0,
        top_p=0.95,
        max_output_tokens=65535,
        safety_settings=[
            types.SafetySetting(
                category='HARM_CATEGORY_HATE_SPEECH', threshold='OFF'
            ),
            types.SafetySetting(
                category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='OFF'
            ),
            types.SafetySetting(
                category='HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold='OFF'
            ),
            types.SafetySetting(
                category='HARM_CATEGORY_HARASSMENT', threshold='OFF'
            ),
        ],
        tools=tools,
        system_instruction=[types.Part.from_text(text=si_text1)],
    )

    text_chunks = []
    for chunk in client.models.generate_content_stream(
        model=self.gemini_model,
        contents=contents,
        config=generate_content_config,
    ):
      candidate = chunk.candidates[0] if chunk.candidates else None
      content = candidate.content if candidate else None
      if not content or not content.parts:
        continue

      for part in content.parts:
        if hasattr(part, 'text') and part.text:
          text_chunks.append(part.text)

    final_response = ''.join(text_chunks)
    final_response = (
        final_response.replace('```json', '').replace('```', '').strip()
    )
    return json.loads(final_response)

  def generate_new(self, data, output_criteria):
    new_dict = {item['shapeId']: item['text'] for item in data['data']}
    json_output = json.dumps(new_dict, indent=4)
    print('Input: \n', json_output)

    received_output = self.generate_data(json_output, output_criteria)
    print('\nOutput: \n', received_output)

    for item in data['data']:
      shape_id = item['shapeId']
      if shape_id in received_output:
        print(f'Match found! Updating {shape_id}')
        item['text'] = received_output[shape_id]
      else:
        print(f'No match for {shape_id}, skipping.')

    return data

  def generate(self, prompt):
    client = genai.Client(
        vertexai=True, project=self.project_id, location='global'
    )

    response = client.models.generate_content(
        model=self.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction='Please provide output in json format.',
            response_mime_type='application/json',
            temperature=0,
        ),
    )
    output_text = ''
    candidate = response.candidates[0] if response.candidates else None
    content = candidate.content if candidate else None
    if content and content.parts:
      output_text = ''.join([
          part.text
          for part in content.parts
          if hasattr(part, 'text') and part.text
      ])
    return output_text

  def reshuffle_slide(
      self,
      input_url,
      input_data_output_criteria,
      slide_layout,
      input_data_slide_category,
      slide_id,
  ):
    old_slide = types.Part.from_uri(file_uri=input_url, mime_type='image/png')
    old_slide_eg1 = types.Part.from_uri(
        file_uri=(
            f'gs://{self.bucket_slides}/EngFHRM/Copy of Puma & Google Cloud -'
            ' Puma North America Ecom/6_g232f9a97ecf_0_230.png'
        ),
        mime_type='image/png',
    )
    old_slide_eg2 = types.Part.from_uri(
        file_uri=(
            f'gs://{self.bucket_slides}/EngFHRM/Copy of Pitch Hub_TOKIO MARINE'
            ' KILN SYNDICATES LIMITED_Artificial Intelligence_2024 01 10'
            ' /23_g2b24520d7ab_0_1342.png'
        ),
        mime_type='image/png',
    )

    templates_metadata = {
        'Case Study': 'templates_metadata/case_study.txt',
        'Charts': 'templates_metadata/charts.txt',
        'Circle Charts': 'templates_metadata/circle_charts.txt',
        'Context': 'templates_metadata/context.txt',
        'Title and content': 'templates_metadata/context.txt',
        'Next Steps': 'templates_metadata/next_steps.txt',
        'Timeline': 'templates_metadata/timeline.txt',
        'Industry Use Case': 'templates_metadata/industry_use_case.txt',
        'GC_AI_Title and content': (
            'templates_metadata/gc_ai_title_and_content.txt'
        ),
        'GC_AI_Divider': 'templates_metadata/gc_ai_divider.txt',
        'GC_AI_Agenda': 'templates_metadata/gc_ai_agendas.txt',
        'CS_Title and content': 'templates_metadata/cs_title_and_content.txt',
        'CS_Divider': 'templates_metadata/cs_divider.txt',
        'CS_Agenda': 'templates_metadata/cs_agendas.txt',
        'GC_AI_Agenda slides General AI': (
            'templates_metadata/gc_ai_Agenda_slides_General_AI.txt'
        ),
        'GC_AI_Title slides General AI': (
            'templates_metadata/gc_ai_title_slides_general_ai.txt'
        ),
        'GC_AI_Title slides AI agents': (
            'templates_metadata/gc_ai_Title_slides_AI_agents.txt'
        ),
        'GC_AI_Welcome slide Gradient': (
            'templates_metadata/gc_ai_welcome_slide_gradient.txt'
        ),
        'GC_AI_Welcome slide General AI': (
            'templates_metadata/gc_ai_welcome_slide_general_ai.txt'
        ),
        'GC_AI_Welcome slide AI agents': (
            'templates_metadata/gc_ai_Welcome_slide_AI_agents.txt'
        ),
        'GC_AI_Agenda slides AI agents': (
            'templates_metadata/gc_ai_Agenda_slides_AI_agents.txt'
        ),
        'GC_AI_Divider slides Gradient': (
            'templates_metadata/gc_ai_Divider_slides_Gradient.txt'
        ),
        'GC_AI_Divider slides General AI': (
            'templates_metadata/gc_ai_Divider_slides_General_AI.txt'
        ),
        'GC_AI_Divider slides AI agents': (
            'templates_metadata/gc_ai_Divider_slides_AI_agents.txt'
        ),
        'GC_AI_Content slides': 'templates_metadata/gc_ai_Content_slides.txt',
        'GC_AI_Speaker slides General AI': (
            'templates_metadata/gc_ai_Speaker_slides_General_AI.txt'
        ),
        'GC_AI_Speaker slides AI agents': (
            'templates_metadata/gc_ai_Speaker_slides_AI_agents.txt'
        ),
        'GC_AI_Key takeaway slides General AI': (
            'templates_metadata/gc_ai_Key_takeaway_slides_General_AI.txt'
        ),
        'GC_AI_Key takeaway slides AI agents': (
            'templates_metadata/gc_ai_Key_takeaway_slides_AI_agents.txt'
        ),
        'GC_AI_Key takeaway slides Gradient': (
            'templates_metadata/gc_ai_Key_takeaway_slides_Gradient.txt'
        ),
        'GC_AI_Quote slides General AI': (
            'templates_metadata/gc_ai_Quote_slides_General_AI.txt'
        ),
        'GC_AI_Quote slides AI agents': (
            'templates_metadata/gc_ai_Quote_slides_AI_agents.txt'
        ),
        'GC_AI_Quote slides Gradient': (
            'templates_metadata/gc_ai_Quote_slides_Gradient.txt'
        ),
        'CS_Chart': 'templates_metadata/cs_chart.txt',
        'CS_Content': 'templates_metadata/cs_content.txt',
        'CS_Quote': 'templates_metadata/cs_quote.txt',
        'CS_Speaker': 'templates_metadata/cs_speaker.txt',
        'CS_Stats': 'templates_metadata/cs_stats.txt',
        'CS_Timeline': 'templates_metadata/cs_timeline.txt',
        'CS_Table': 'templates_metadata/cs_table.txt',
        'CS_Title': 'templates_metadata/cs_title.txt',
        'Customer References': 'templates_metadata/Customer_References.txt',
        'GTM_GTM Layout': 'templates_metadata/gtm_gtm_layout.txt',
    }

    if slide_layout == 'Google Cloud AI':
      input_data_slide_category = 'GC_AI_' + input_data_slide_category
    if slide_layout == 'Google Cloudstyle':
      input_data_slide_category = 'CS_' + input_data_slide_category
    if slide_layout == 'GTM Accelerate':
      input_data_slide_category = 'GTM_' + input_data_slide_category

    meta_rel_path = templates_metadata.get(
        input_data_slide_category, 'templates_metadata/context.txt'
    )
    meta_path = os.path.join(self.current_dir, meta_rel_path)
    with open(meta_path, 'r') as meta_json:
      meta_json = meta_json.read()
    meta_json = json.loads(meta_json)

    new_slide_template = ''
    for key, value in meta_json.items():
      if slide_id in key:
        new_slide_template = value
        break
    if not new_slide_template and meta_json:
      new_slide_template = next(iter(meta_json.values()))
    new_slide_template = json.dumps(new_slide_template, indent=2)

    prompt_path = os.path.join(
        self.current_dir, 'prompt_templates', 'reshuffle.txt'
    )
    with open(prompt_path, 'r') as prompt_template:
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
        prompt_template[5],
    ]

    retry_count = 0
    while retry_count < 2:
      try:
        if retry_count > 0:
          print('retrying reshuffle...')
        output = self.generate(prompt)
        output = self.clean_json_string(output)
        output = output.strip()
        output = output[
            output.index('{') : (
                ((len(output) - 1) - output[::-1].index('}') + 1)
            )
        ]
        return json.loads(output.strip(), strict=False)
      except Exception as e:
        print(f'Reshuffle error (retry {retry_count}): {e}')
        retry_count += 1
    raise Exception('Failed to reshuffle slide after retries.')

  def process_reshuffle_io(self, request_file_url):
    print(
        '[SlideReshuffler] Processing GCS reshuffle payload:'
        f' {request_file_url}'
    )

    transform_data = read_gcs_file(request_file_url, project_id=self.project_id)
    transform_dict = json.loads(transform_data)

    toggle = transform_dict['toggle']

    if toggle is False:
      print('[SlideReshuffler] Visual Reshuffle Path (toggle = False)')
      slide_image_url = transform_dict['slide_image_url']
      output_criteria = transform_dict['output_criteria']
      slide_layout = transform_dict['slide_layout']
      slide_category = transform_dict['slide_category']
      slide_id = transform_dict['slide_id']

      reshuffled_slide = self.reshuffle_slide(
          input_url=slide_image_url,
          input_data_output_criteria=output_criteria,
          slide_layout=slide_layout,
          input_data_slide_category=slide_category,
          slide_id=slide_id,
      )

      response_file_name = (
          'transform_data/'
          + ''.join(request_file_url.split('/')[-1].split('_')[:-1])
          + '_TrueResponse.json'
      )
      response_file_url = f'gs://{self.bucket_name}/{response_file_name}'

      blob = self.bucket.blob(response_file_name)
      blob.upload_from_string(
          json.dumps(reshuffled_slide, indent=2),
          content_type='application/json',
      )
    else:
      print('[SlideReshuffler] Content Revision Path (toggle = True)')
      output_criteria = transform_dict['output_criteria']

      final_data = self.generate_new(transform_dict, output_criteria)

      response_file_name = (
          'transform_data/'
          + ''.join(request_file_url.split('/')[-1].split('_')[:-1])
          + '_FalseResponse.json'
      )
      response_file_url = f'gs://{self.bucket_name}/{response_file_name}'

      blob = self.bucket.blob(response_file_name)
      blob.upload_from_string(
          json.dumps(final_data, indent=2), content_type='application/json'
      )

    return response_file_url


class ReshuffleWorkflow(BaseWorkflow):
  """Skill to perform slide layout transformation and content revision via GCS payloads."""

  def __init__(self, config):
    super().__init__(
        'ReshuffleWorkflow',
        "Transforms a slide's visual layout or content based on structural"
        ' style templates and GCS payloads.',
    )
    self.config = config
    self.reshuffler = SlideReshuffler(config)

  def execute(self, request_file_url: str) -> str:
    """Processes GCS payload for slide visual transformation or content revision.

    Args:
        request_file_url: GCS path containing the reshuffle package.

    Returns:
        GCS path containing the reshuffled slide response package.
    """
    try:
      result_url = self.reshuffler.process_reshuffle_io(request_file_url)
      return result_url
    except Exception as e:
      print(f'[ReshuffleWorkflow] Error: {e}')
      raise e
