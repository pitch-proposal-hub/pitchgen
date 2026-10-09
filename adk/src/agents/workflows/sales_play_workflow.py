import json
import os
from google import genai
from google.cloud import storage
from google.genai import types
from pitchgen_utils.gcs_util import read_gcs_file
from pitchgen_utils.template_sorting import get_placeholders_json
from agents.workflows.base_workflow import BaseWorkflow


class SalesPlayEngine:
  """Engine that handles customization of sales play templates and customer research slide generation."""

  def __init__(self, config):
    self.config = config
    self.project_id = config["default"]["project_name"]
    self.gemini_model = config["default"]["gemini_model"]
    self.bucket_name = config["bucket"]["content"]
    self.storage_client = storage.Client(project=self.project_id)
    self.salesplay_bucket = self.storage_client.bucket(self.bucket_name)

  def generate(self, customer_name, slide_data_json):
    client = genai.Client(
        vertexai=True,
        project=self.project_id,
        location="global",
    )
    prefix_text = f"""You will be provided with the customer's name and a JSON data structure containing slide information. Your goal is to modify the 'title' field in the JSON by including the customer's name, but only if it fits naturally and enhances the title without changing its meaning.

Here is the customer's name: {customer_name}

Here is the JSON data structure containing slide information: {slide_data_json}

Follow these steps:
1.  Analyze the 'title' field of each slide in the JSON data.
2.  Determine if incorporating the customer name enhances the title without changing its original meaning.
3.  If it fits naturally, insert the customer name into the title.
4.  Ensure the modified title remains grammatically correct and contextually relevant.
5.  Do not add the customer name if it makes the title awkward or changes its meaning.
6.  Output the modified JSON data structure.
7.  Do not hallucinate or invent information. Only use the provided data.
"""

    examples_text = """
Examples:

<input>
Customer Name: Acme Corp
JSON Data:
```json
[
  {
    "slideId": "SLIDES_API1167096495_2177",
    "shapeId": "SLIDES_API1167096495_2178",
    "title": "Introduction to Our Services"
  },
  {
    "slideId": "SLIDES_API1167096495_2626",
    "shapeId": "SLIDES_API1167096495_2627",
    "title": "Agenda"
  }
]
```
</input>

<output>
```json
[
  {
    "slideId": "SLIDES_API1167096495_2177",
    "shapeId": "SLIDES_API1167096495_2178",
    "title": "Introduction to Our Services for Acme Corp"
  },
  {
    "slideId": "SLIDES_API1167096495_2626",
    "shapeId": "SLIDES_API1167096495_2627",
    "title": "Agenda"
  }
]
```
</output>
"""

    suffix_text = f"""
<input>
Customer Name: {customer_name}
JSON Data:
```json
{slide_data_json}
```
</input>

<output>
"""
    msg1_text1 = types.Part.from_text(
        text=prefix_text + examples_text + suffix_text
    )
    si_text1 = """You are a creative marketing assistant. Your task is to personalize presentation slide titles by incorporating the customer's name where contextually appropriate, without altering the original meaning of the sentence."""

    contents = [
        types.Content(role="user", parts=[msg1_text1]),
    ]

    generate_content_config = types.GenerateContentConfig(
        temperature=1,
        top_p=0.95,
        seed=0,
        max_output_tokens=65535,
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
        system_instruction=[types.Part.from_text(text=si_text1)],
    )
    text_chunks = []
    for chunk in client.models.generate_content_stream(
        model=self.gemini_model,
        contents=contents,
        config=generate_content_config,
    ):
      if chunk.candidates and chunk.candidates[0].content.parts:
        for part in chunk.candidates[0].content.parts:
          if hasattr(part, "text") and part.text:
            text_chunks.append(part.text)

    final_response = "".join(text_chunks)
    final_response = (
        final_response.replace("```json\n", "")
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    return final_response

  def sales_play(self, request_file_url):
    salesplay_data = read_gcs_file(request_file_url, project_id=self.project_id)

    salesplay_dict = json.loads(salesplay_data)

    customer_name = salesplay_dict["customerName"]
    slide_data_json = salesplay_dict["titleObj"]

    for i in range(len(slide_data_json)):
      slide_data_json[i]["title"] = slide_data_json[i]["title"].replace(
          "\u000b", " "
      )

    json_response = self.generate(customer_name, slide_data_json)
    json_response = json_response.replace("```json", "")
    json_response = json_response.replace("```", "")
    json_response = json.loads(json_response.strip())

    salesplay_dict["titleObj"] = json_response

    response_file_name = (
        "sales_play/"
        + "".join(request_file_url.split("/")[-1].split("_")[:-1])
        + "_TitleResponse.json"
    )
    blob = self.salesplay_bucket.blob(response_file_name)
    blob.upload_from_string(
        json.dumps(salesplay_dict, indent=2), content_type="application/json"
    )
    response_file_url = f"gs://{self.bucket_name}/{response_file_name}"

    return response_file_url

  def generate_cust_data(self, customer_name, context):
    client = genai.Client(
        vertexai=True,
        project=self.project_id,
        location="global",
    )
    number_of_slides = 3
    msg1_text1 = types.Part.from_text(
        text=f"""You will be provided with a customer name, context and number of slides. Use this following information to create slides.

Follow these steps:

1.  Use the provided customer name and context to gather relevant customer information data.
2.  Generate the specified number of slides, ensuring that each slide contains only customer information data.
3.  Organize the customer information data into a clear and concise format on each slide.
4.  Ensure that the content on each slide is accurate and relevant to the customer.
5.  Present the slides in a logical order, ensuring a smooth flow of information.
6.  Review the generated slides to ensure they meet the requirements and are free of errors.
7.  Use the following format for each slide:
    Slide Title: [Slide Title]
    Slide Content: [Slide Content]

<input>
customer name: {customer_name}
context: {context}
number of slides: {number_of_slides}
</input>

<output>"""
    )
    si_text1 = """You are a content generation specialist. Your task is to generate a specific number of slides with only the customer information data for a given customer based on the provided customer name and context."""

    contents = [
        types.Content(role="user", parts=[msg1_text1]),
    ]
    tools = [
        types.Tool(google_search=types.GoogleSearch()),
    ]

    generate_content_config = types.GenerateContentConfig(
        temperature=1,
        top_p=0.95,
        seed=0,
        max_output_tokens=65535,
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
        tools=tools,
        system_instruction=[types.Part.from_text(text=si_text1)],
    )
    text_chunks = []
    for chunk in client.models.generate_content_stream(
        model=self.gemini_model,
        contents=contents,
        config=generate_content_config,
    ):
      if (
          not chunk.candidates
          or not chunk.candidates[0].content
          or not chunk.candidates[0].content.parts
      ):
        continue

      for part in chunk.candidates[0].content.parts:
        if hasattr(part, "text") and part.text:
          text_chunks.append(part.text)

    final_response = "".join(text_chunks)
    return final_response

  def cust_insights(self, request_file_url):
    salesplay_data = read_gcs_file(request_file_url, project_id=self.project_id)

    salesplay_dict = json.loads(salesplay_data)

    customer_name = salesplay_dict["customerName"]
    presentation = salesplay_dict["presentation"]
    objective = f"""Generate the slide contents for the customer: {customer_name}, with Customer Information on,
1. The Customers New Announcements and recent acquisition in IT sector.
2. Key Statistics and Performance.
3. New Deals and Strategic Priorities.
4. Industry Trends, Changes associated and the risks involved.
5. problem focus, thinking, solution and Goals."""

    for attempt in range(2):
      try:
        cust_content = ""
        cust_content += f"-----Task 11 Completed successfully-----\n\n"
        cust_response = self.generate_cust_data(customer_name, objective)
        cust_content += cust_response + "\n\n"

        output = get_placeholders_json(cust_content, layout="Context")

        input_data = output["agendas"]["1"]["slides"]
        constant_first_item = {
            "temp_url": (
                "https://docs.google.com/presentation/d/TEMPLATE_DECK_SALES_PLAY_PLACEHOLDER_001/edit#slide=id.g348daf40754_0_533"
            ),
            "placeholders": {
                "num": "01",
                "title": "Customer Research & Insights",
            },
            "sources": [],
        }

        output_data = {}
        output_data["1"] = constant_first_item

        for old_key_str in sorted(input_data.keys(), key=int):
          new_key_str = str(int(old_key_str) + 1)
          output_data[new_key_str] = input_data[old_key_str]

        salesplay_dict["slide_content"] = output_data

        response_file_name = (
            "sales_play/"
            + "".join(request_file_url.split("/")[-1].split("_")[:-1])
            + "_ContentResponse.json"
        )
        blob = self.salesplay_bucket.blob(response_file_name)
        blob.upload_from_string(
            json.dumps(salesplay_dict, indent=2),
            content_type="application/json",
        )
        response_file_url = f"gs://{self.bucket_name}/{response_file_name}"

        return response_file_url

      except Exception as e:
        print(f"[SalesPlayEngine] Attempt {attempt + 1} failed: {e}")
        if attempt < 1:
          print("Retrying sales play content generation...")
    raise Exception(
        "Failed to generate customer insights slides after retries."
    )


class SalesPlayWorkflow(BaseWorkflow):
  """Skill to process automated Sales Plays (customizing slide titles and generating customer research slides)."""

  def __init__(self, config):
    super().__init__(
        "SalesPlayWorkflow",
        "Customizes standardized Sales Play slide decks and appends dynamically"
        " synthesized customer research slides.",
    )
    self.config = config
    self.engine = SalesPlayEngine(config)

  def execute(self, request_file_url: str) -> str:
    """Executes the Sales Play custom assembly pipeline.

    Args:
        request_file_url: GCS path containing the initial sales play request
          package.

    Returns:
        GCS path containing the finalized response package.
    """
    try:
      print(
          "[SalesPlayWorkflow] Customizing template titles for payload:"
          f" {request_file_url}"
      )
      title_response_url = self.engine.sales_play(request_file_url)

      print(f"[SalesPlayWorkflow] Generating dynamic customer insights slides...")
      final_response_url = self.engine.cust_insights(title_response_url)

      return final_response_url
    except Exception as e:
      print(f"[SalesPlayWorkflow] Error during execution: {e}")
      raise e
