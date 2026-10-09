import concurrent.futures
import json
import random
import re
import time
from config_loader import load_config
from google import genai
from google.cloud import storage
from google.genai import types

# Module-level variables to fix undefined warnings
deck_id = None
data = {}
layout_prompt = None


def generate_speaker_notes(slide_title, slide_content):
  config = load_config()
  project_id = config["default"]["project_name"]
  client = genai.Client(
      vertexai=True,
      project=project_id,
      location="global",
  )

  msg1_text1 = types.Part.from_text(
      text=f"""You are a presentation assistant tasked with generating speaker notes.
Your goal is to create relevant, first-person speaker notes in plain text format that act as a ready-to-use script.
Ensure the talking points perfectly align with the provided slide title and content.
The speaker notes should be on point and should not include any irrelevant contents such as greetings or stage directions.
The desired tone of the speaker notes should be formal and the generated script must be within 500 words.

<input>
Slide Title: PepsiCo at a Glance: A Global Food and Beverage Giant
Slide Content: *   **Company Overview:** PepsiCo, Inc. is an American multinational food, snack, and beverage corporation formed in 1965 through the merger of Pepsi-Cola and Frito-Lay. Its diverse portfolio includes some of the world's most recognized brands, such as Lay's, Doritos, Cheetos, Gatorade, Pepsi-Cola, Mountain Dew, and Quaker.
*   **Immense Global Reach:** PepsiCo's products are enjoyed by consumers more than one billion times a day in over 200 countries and territories. The company employs approximately 318,000 people worldwide as of 2024.
*   **Market Position:** It is the second-largest food and beverage business in the world, behind Nestlé. The company's portfolio includes 23 brands that each generate more than $1 billion in annual retail sales.
*   **Scale and Financials:** PepsiCo generated nearly $92 billion in net revenue in 2024. The business is almost evenly split between food (53%) and beverages (47%).
</input>

<output>
When examining PepsiCo, it is important to recognize the breadth of its operations. The company was established in 1965 through the merger of Pepsi-Cola and Frito-Lay, creating a robust and diverse portfolio. This portfolio now encompasses globally recognized brands such as Lay's, Doritos, Cheetos, Gatorade, Pepsi-Cola, Mountain Dew, and Quaker.

PepsiCo's global presence is substantial, with its products consumed over one billion times daily across more than 200 countries and territories. As of 2024, the company's global workforce stands at approximately 319,000 individuals.

In terms of market position, PepsiCo is recognized as the second-largest food and beverage enterprise globally, positioned directly behind Nestlé. A significant driver of this success is its portfolio, which includes 23 distinct brands each generating over $1 billion in annual retail sales.

Financially, PepsiCo reported nearly $92 billion in net revenue in 2024. The revenue composition is nearly balanced, with food and snacks contributing approximately 53% and beverages approximately 47%. This balanced structure represents a considerable strength for the organization.
</output>

<input>
Slide Title: Vertex AI: A Single Platform to Build, Deploy, and Scale ML Models
Slide Content: *   **Unified AI/ML Platform:** Consolidates all AI/ML tasks into one platform, streamlining the entire lifecycle from data preparation to deployment and monitoring for both predictive and generative AI.
*   **End-to-End MLOps:** Provides a complete set of tools to manage the entire AI model lifecycle, ensuring reliability, scalability, and continuous improvement.
*   **Reduces Complexity & Cost:** Eliminates heavy lifting by tackling key challenges like model proliferation, scaling difficulties, cost control, and security, thus reducing administrative overhead.
*   **Flexible & Open:** Supports both open-source frameworks (like PyTorch and TensorFlow) and Google's AutoML tools.
*   **Optimized Infrastructure:** Offers fast inference on GPUs & TPUs with flexible consumption models (On-demand, Spot VMs) to optimize cost and performance.
</input>

<output>
Vertex AI serves as a unified platform designed to build, deploy, and scale machine learning models. It consolidates all AI and ML tasks into a single environment, which streamlines the entire lifecycle—from the initial stages of data preparation to the final deployment and monitoring for both predictive and generative AI.

The platform provides a complete set of MLOps tools to manage the entire AI model lifecycle. This end-to-end management ensures reliability, facilitates scalability, and supports continuous improvement of the models in production.

A key benefit of Vertex AI is the reduction of both complexity and cost. It addresses significant challenges such as model proliferation, difficulties with scaling, cost control, and security. By managing this heavy lifting, the platform effectively reduces administrative overhead.

Furthermore, Vertex AI is designed to be both flexible and open. It offers support for popular open-source frameworks like PyTorch and TensorFlow, while also integrating with Google's own AutoML tools.

Finally, the platform runs on optimized infrastructure. It delivers fast inference on both GPUs and TPUs and provides flexible consumption models, including On-demand and Spot VMs, allowing for the optimization of both cost and performance.
</output>

<input>
Slide Title: The Google Cloud Advantage: Innovation at Scale
Slide Content: **Enterprise-Ready Tools:** Leverage cutting-edge AI/ML capabilities and a global infrastructure designed for rapid, scalable deployment.
   **AI-Driven Culture:** Tap into a culture of 10x thinking to unlock new opportunities aligned with PepsiCo’s strategic pillars.
   **Open Ecosystem:** Benefit from a vast ecosystem of over 350 open Gen AI partners, ensuring you have the best tools for any challenge.
   **Focus on Business Value:** The platform design allows developers to focus on building value-driving applications rather than managing complex infrastructure.
</input>

<output>
The Google Cloud advantage is rooted in our commitment to fostering innovation at a massive scale. Our enterprise-ready tools provide access to cutting-edge AI and machine learning capabilities, all supported by a global infrastructure engineered for rapid and scalable deployment.

We also offer the opportunity to tap into a culture of "10x thinking." This approach encourages aiming for solutions that are ten times better, rather than just ten percent better, and can help unlock new opportunities that align with PepsiCo’s strategic pillars.

Furthermore, our platform is built on an open ecosystem. This provides the benefit of access to over 350 open generative AI partners, ensuring that the best and most appropriate tools are available for any given challenge.

Ultimately, the design of our platform allows developers to focus on what truly matters: building applications that drive business value. By managing the underlying complexities of infrastructure, we free up valuable resources to concentrate on innovation and strategic growth.
</output>

<input>
Slide Title: {slide_title}
Slide Content: {slide_content}
</input>

<output>"""
  )

  model = config["default"].get("gemini_model_1", "gemini-3.5-flash-lite")
  contents = [
      types.Content(role="user", parts=[msg1_text1]),
  ]

  generate_content_config = types.GenerateContentConfig(
      temperature=0.2,
      top_p=0.95,
      max_output_tokens=1024,
      safety_settings=[
          types.SafetySetting(
              category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"
          ),
          types.SafetySetting(
              category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"
          ),
          types.SafetySetting(
              category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"
          ),
          types.SafetySetting(
              category="HARM_CATEGORY_HARASSMENT", threshold="OFF"
          ),
      ],
  )
  text_chunks = []
  for chunk in client.models.generate_content_stream(
      model=model,
      contents=contents,
      config=generate_content_config,
  ):
    if not chunk.candidates:
      continue
    candidate = chunk.candidates[0]
    if not candidate.content:
      continue
    content = candidate.content
    if not content.parts:
      continue

    for part in content.parts:
      if hasattr(part, "text") and part.text:
        text_chunks.append(part.text)

  final_response = "".join(text_chunks)
  final_response = final_response.replace('"', "")

  return final_response


#   text_chunks=[]
#   for chunk in client.models.generate_content_stream(
#     model = model,
#     contents = contents,
#     config = generate_content_config,
#     ):
#     if not chunk.candidates or not chunk.candidates[0].content or not chunk.candidates[0].content.parts:
#         continue

#     text_chunks.append(chunk.text)

#   final_response = "".join(text_chunks)
#   final_response = final_response.replace('"', '')

#   return final_response


def clean_json_string(json_string):
  """Clean the generated JSON string by ensuring proper escaping and removing any trailing commas or problematic newlines."""
  json_string = json_string.strip()
  json_string = re.sub(r",\s*}", "}", json_string)
  json_string = re.sub(r",\s*]", "]", json_string)
  json_string = json_string.replace(r"\s*\n", r"\n")
  json_string = json_string.replace(r"\s*\r", r"\r")
  return json_string


def generate(prompt):
  """Generate content based on a prompt using a generative model.

  Args:
      prompt (str): The prompt for content generation.

  Returns:
      str: The generated content.
  """
  config = load_config()
  project_id = config["default"]["project_name"]
  client = genai.Client(
      vertexai=True,
      project=config["default"]["project_name"],
      location="global",
  )

  response = client.models.generate_content(
      model=config["default"]["gemini_model_1"],
      contents=prompt,
      config=types.GenerateContentConfig(
          system_instruction="Please provide output in json format.",
          response_mime_type="application/json",
          temperature=0,
      ),
  )
  output_text = ""
  if response.candidates:
    candidate = response.candidates[0]
    if candidate.content and candidate.content.parts:
      output_text = "".join([
          part.text
          for part in candidate.content.parts
          if hasattr(part, "text") and part.text
      ])

  return output_text
  # return response.text


def format_input_text_1(slide_title, slide_content):
  import os

  current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  # Load base instructions
  with open(
      os.path.join(current_dir, "prompt_templates/template_sorter_base.txt"),
      "r",
  ) as f:
    base_template = f.read()

  # Load layout JSON data
  layout_file = os.path.join(
      current_dir, f"prompt_templates/layouts/{layout_prompt}.json"
  )
  with open(layout_file, "r") as f:
    layout_data = json.loads(f.read())

  # Shuffle templates to avoid positional bias
  templates = layout_data["templates"]
  json_list = list(templates.items())
  random.shuffle(json_list)
  shuffled_templates = dict(json_list)

  # Get examples raw text
  examples_text = layout_data["examples"]

  input_text = f"Slide Title: {slide_title}\nSlide Content: {slide_content}"

  # Compile final prompt
  compiled_prompt = base_template.format(
      templates=json.dumps(shuffled_templates, indent=4),
      used_templates_instruction="",
      examples=examples_text,
      input_text=input_text,
  )

  placeholders_json = generate(prompt=compiled_prompt)
  placeholders_json = clean_json_string(placeholders_json)
  placeholders_json = placeholders_json.strip()
  placeholders_json = placeholders_json[
      placeholders_json.index("{") : ((
          (len(placeholders_json) - 1) - placeholders_json[::-1].index("}") + 1
      ))
  ]
  placeholders_json = json.loads(placeholders_json.strip())
  return placeholders_json


def generate_placeholders_json(slide_title, slide_content):
  placeholders_dict = format_input_text_1(slide_title, slide_content)
  speaker_notes = generate_speaker_notes(slide_title, slide_content)
  final_json = {}
  v = placeholders_dict["template"]
  final_json["temp_url"] = (
      f"https://docs.google.com/presentation/d/{deck_id}/edit#slide=id."
      f"{data['slideids'][int(v) - 1]}"
  )
  final_json["placeholders"] = placeholders_dict["placeholders"]
  final_json["speaker_notes"] = speaker_notes
  return final_json


def process_agenda(agenda_key, agenda_value):
  """Process an agenda item and generate JSON placeholders for each slide.

  Args:
    agenda_key (str): The key of the agenda item.
    agenda_value (dict): The value (slides) of the agenda item.

  Returns:
    dict: A dictionary containing the generated JSON placeholders for the agenda
    item's slides.
  """
  slides_json = {}
  for slide_key, slide_value in agenda_value.items():
    slides_json[slide_key] = generate_placeholders_json(
        slide_value["Slide Title"], slide_value["Slide Content"]
    )
  return {agenda_key: {"slides": slides_json}}


def retry_generate_placeholders_json(
    slide_title, slide_content, retries=2, delay=10
):
  """Retry generating JSON placeholders for a slide.

  Args:
    slide_title (str): The title of the slide.
    slide_content (str): The content of the slide.
    retries (int): The number of retries.
    delay (int): The delay between retries.

  Returns:
    dict: A dictionary containing the generated JSON placeholders, or None if
    all retries fail.
  """
  for _ in range(retries):
    try:
      return generate_placeholders_json(slide_title, slide_content)
    except Exception as e:
      print(f"Error generating JSON for slide '{slide_title}': {e}")
      print("Retrying...")
      time.sleep(delay)
  # If all retries fail, return None
  return None


def get_placeholders_json(text_content, layout):
  """Parse text content containing slide titles and content,

  extract agendas, and generate JSON placeholders
  for each slide.

  Args:
      text_content (str): The text content containing slide titles and content.

  Returns:
      dict: A dictionary containing the generated JSON placeholders for the
      slides in the agendas.
  """

  config = load_config()
  BUCKET_NAME = config["bucket"]["template"]
  # global template_pdf_documents
  # template_pdf_documents = {'Context':f'gs://{BUCKET_NAME}/Context/Context.pdf'}
  json_files = {
      "Context": "TEMPLATE_DECK_CONTEXT_V1_PLACEHOLDER_001.json",
      "Title and content": "TEMPLATE_DECK_CONTEXT_V1_PLACEHOLDER_001.json",
      "Case Study": "TEMPLATE_DECK_CASE_STUDY_PLACEHOLDER_001.json",
      "Charts": "TEMPLATE_DECK_CHARTS_V1_PLACEHOLDER_0001.json",
      "Circle Charts": "TEMPLATE_DECK_CIRCLE_CHART_PLACEHOLDER_1.json",
      "Next Steps": "TEMPLATE_DECK_NEXT_STEPS_PLACEHOLDER_001.json",
      "Timeline": "TEMPLATE_DECK_TIMELINE_V1_PLACEHOLDER_01.json",
      "Industry Use Case": "TEMPLATE_DECK_IND_USECASE_PLACEHOLDER_01.json",
      "GC_AI_Title and content": (
          "TEMPLATE_DECK_GCAI_TTLCNT_PLACEHOLDER_01.json"
      ),
      "GC_AI_Divider": "TEMPLATE_DECK_GCAI_DIVIDR_PLACEHOLDER_01.json",
      "GC_AI_Agenda": "TEMPLATE_DECK_GCAI_AGENDA_PLACEHOLDER_01.json",
      "CS_Title and content": (
          "TEMPLATE_DECK_CS_TITLECNT_PLACEHOLDER_01.json"
      ),
      "CS_Divider": "TEMPLATE_DECK_CS_DIVIDER_PLACEHOLDER_001.json",
      "CS_Agenda": "TEMPLATE_DECK_CS_AGENDAS_PLACEHOLDER_001.json",
      "GC_AI_Agenda slides General AI": (
          "TEMPLATE_DECK_GCAI_AGD_GN_PLACEHOLDER_01.json"
      ),
      "GC_AI_Title slides General AI": (
          "TEMPLATE_DECK_GCAI_TTL_GN_PLACEHOLDER_01.json"
      ),
      "GC_AI_Title slides AI agents": (
          "TEMPLATE_DECK_GCAI_TTL_AG_PLACEHOLDER_01.json"
      ),
      "GC_AI_Welcome slide Gradient": (
          "TEMPLATE_DECK_WELCOME_GRAD_PLACEHOLDER_1.json"
      ),
      "GC_AI_Welcome slide General AI": (
          "TEMPLATE_DECK_GCAI_WLC_GN_PLACEHOLDER_01.json"
      ),
      "GC_AI_Welcome slide AI agents": (
          "TEMPLATE_DECK_WELCOME_AGNT_PLACEHOLDER_1.json"
      ),
      "GC_AI_Agenda slides AI agents": (
          "TEMPLATE_DECK_GCAI_AGD_AG_PLACEHOLDER_01.json"
      ),
      "GC_AI_Divider slides Gradient": (
          "TEMPLATE_DECK_GCAI_DIV_GR_PLACEHOLDER_01.json"
      ),
      "GC_AI_Divider slides General AI": (
          "TEMPLATE_DECK_GCAI_DIV_GN_PLACEHOLDER_01.json"
      ),
      "GC_AI_Divider slides AI agents": (
          "TEMPLATE_DECK_GCAI_DIV_AG_PLACEHOLDER_01.json"
      ),
      "GC_AI_Content slides": (
          "TEMPLATE_DECK_GCAI_CNT_V1_PLACEHOLDER_01.json"
      ),
      "GC_AI_Speaker slides General AI": (
          "TEMPLATE_DECK_SPEAKER_GEN_PLACEHOLDER_01.json"
      ),
      "GC_AI_Speaker slides AI agents": (
          "TEMPLATE_DECK_GCAI_SPK_AG_PLACEHOLDER_01.json"
      ),
      "GC_AI_Key takeaway slides General AI": (
          "TEMPLATE_DECK_GCAI_KEY_GN_PLACEHOLDER_01.json"
      ),
      "GC_AI_Key takeaway slides AI agents": (
          "TEMPLATE_DECK_GCAI_KEY_AG_PLACEHOLDER_01.json"
      ),
      "GC_AI_Key takeaway slides Gradient": (
          "TEMPLATE_DECK_GCAI_KEY_GR_PLACEHOLDER_01.json"
      ),
      "GC_AI_Quote slides General AI": (
          "TEMPLATE_DECK_GCAI_QUO_GN_PLACEHOLDER_01.json"
      ),
      "GC_AI_Quote slides AI agents": (
          "TEMPLATE_DECK_GCAI_QUO_AG_PLACEHOLDER_01.json"
      ),
      "GC_AI_Quote slides Gradient": (
          "TEMPLATE_DECK_GCAI_QUO_GR_PLACEHOLDER_01.json"
      ),
      "CS_Chart": "TEMPLATE_DECK_CS_CHART_V1_PLACEHOLDER_01.json",
      "CS_Content": "TEMPLATE_DECK_CS_CONTENT_PLACEHOLDER_001.json",
      "CS_Quote": "TEMPLATE_DECK_CS_QUOTE_V1_PLACEHOLDER_01.json",
      "CS_Speaker": "TEMPLATE_DECK_CS_SPEAKER_PLACEHOLDER_001.json",
      "CS_Stats": "TEMPLATE_DECK_CS_STATS_V1_PLACEHOLDER_01.json",
      "CS_Timeline": "TEMPLATE_DECK_CS_TIMELINE_PLACEHOLDER_01.json",
      "CS_Table": "TEMPLATE_DECK_CS_TABLE_V1_PLACEHOLDER_01.json",
      "CS_Title": "TEMPLATE_DECK_CS_TITLE_V1_PLACEHOLDER_01.json",
      "Customer References": (
          "TEMPLATE_DECK_CUST_REF_PLACEHOLDER_00001.json"
      ),
      "GTM_GTM Layout": "TEMPLATE_DECK_GTM_LAYOUT_PLACEHOLDER_001.json",
  }
  prompt_ref = {
      "Context": "context",
      "Title and content": "context",
      "Case Study": "case_study",
      "Charts": "charts",
      "Circle Charts": "circle_charts",
      "Next Steps": "next_steps",
      "Timeline": "timeline",
      "Industry Use Case": "industry_use_case",
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
      "GC_AI_Key takeaway slides General AI": (
          "gc_ai_Key_takeaway_slides_General AI"
      ),
      "GC_AI_Key takeaway slides AI agents": (
          "gc_ai_Key_takeaway_slides_AI_agents"
      ),
      "GC_AI_Key takeaway slides Gradient": (
          "gc_ai_Key_takeaway_slides_Gradient"
      ),
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
  }
  global layout_prompt
  layout_prompt = prompt_ref.get(layout, "context")

  global deck_id
  deck_id = json_files.get(
      layout, "TEMPLATE_DECK_CONTEXT_V1_PLACEHOLDER_001.json"
  ).split(".")[0]
  global data
  import os

  current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  local_meta_path = os.path.join(
      current_dir, "templates_metadata", f"{layout_prompt}.txt"
  )
  if os.path.exists(local_meta_path):
    with open(local_meta_path, "r") as mf:
      meta_dict = json.load(mf)
    ordered_sids = []
    for k in sorted(
        meta_dict.keys(),
        key=lambda x: int(x.split("@")[0])
        if x.split("@")[0].isdigit()
        else 999,
    ):
      parts = k.split("@")
      if len(parts) >= 3:
        ordered_sids.append(parts[2])
    data = {"slideids": ordered_sids}
  else:
    client = storage.Client(project=config["default"]["project_name"])
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"slides/{json_files[layout]}")
    json_string = blob.download_as_string().decode("utf-8")
    data = json.loads(json_string, strict=False)

  text_content = re.sub(r"\n+", "\n", text_content)
  pattern = r"\*\*Slide Title\:\*\*"
  text_content = re.sub(pattern, "Slide Title:", text_content)
  pattern = r"\*\*Slide Content\:\*\*"
  text_content = re.sub(pattern, "Slide Content:", text_content)

  lines = text_content.strip().splitlines()

  Agendas = dict()
  agenda_num = None
  slide_num = None
  slide_count = 0
  sflag = 0
  for line in lines:
    if line == "\n":
      continue
    if line.startswith("-----Task"):
      slide_count = 0
      sflag = 0
      num = re.search(r"\d+", line)
      if num:
        task_num = int(num.group())
        agenda_num = str(int(task_num / 10))
        slide_num = str(task_num % 10)
      else:
        agenda_num = None
        slide_num = None

      if agenda_num is not None and slide_num is not None:
        if agenda_num not in Agendas:
          Agendas[agenda_num] = dict()
        Agendas[agenda_num][slide_num] = dict()

    else:
      if agenda_num is not None and slide_num is not None:
        if "Slide Title" in line:
          sflag = 1
          slide_count += 1
          Agendas[agenda_num][slide_num][str(slide_count)] = {}
          Agendas[agenda_num][slide_num][str(slide_count)]["Slide Title"] = (
              line.split("Slide Title:")[1]
          )
        elif "Slide Content" in line:
          Agendas[agenda_num][slide_num][str(slide_count)]["Slide Content"] = ""
          if len(line.split("Slide Content:")) <= 1:
            continue
          Agendas[agenda_num][slide_num][str(slide_count)][
              "Slide Content"
          ] += line.split("Slide Content:")[1]
        elif sflag:
          Agendas[agenda_num][slide_num][str(slide_count)]["Slide Content"] += (
              "\n" + line
          )

  # print(Agendas)
  fin_agendas = dict()
  for key in Agendas:
    sub_num = 1
    slide_num = 1
    fin_agendas[key] = dict()
    while str(sub_num) in Agendas[key]:
      k = 1
      while str(k) in Agendas[key][str(sub_num)]:
        fin_agendas[key][str(slide_num)] = Agendas[key][str(sub_num)][str(k)]
        k += 1
        slide_num += 1
      sub_num += 1

  op_json = {"agendas": dict()}

  with concurrent.futures.ThreadPoolExecutor() as executor:
    futures = {
        executor.submit(process_agenda, key, value): key
        for key, value in fin_agendas.items()
    }
    for future in concurrent.futures.as_completed(futures):
      agenda_key = futures[future]
      try:
        op_json["agendas"].update(future.result())
      except Exception as e:
        print(f"Error processing agenda {agenda_key}: {e}")

  # Retry generating placeholders for slides that failed initially
  for agenda_key, agenda_value in fin_agendas.items():
    for slide_key, slide_value in agenda_value.items():
      if slide_key not in op_json["agendas"].get(agenda_key, {}).get(
          "slides", {}
      ):
        slide_title = slide_value["Slide Title"]
        slide_content = slide_value["Slide Content"]
        retry_result = retry_generate_placeholders_json(
            slide_title, slide_content
        )
        if retry_result:
          op_json["agendas"].setdefault(agenda_key, {"slides": {}})
          op_json["agendas"][agenda_key]["slides"][slide_key] = retry_result

  op_json = {
      "agendas": {
          int(i): op_json["agendas"][i] for i in sorted(op_json["agendas"])
      }
  }
  op_json = {
      "agendas": {
          str(i): op_json["agendas"][i] for i in sorted(op_json["agendas"])
      }
  }
  return op_json
