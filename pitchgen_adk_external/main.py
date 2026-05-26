"""
This module provides a FastAPI application for generating and managing presentation slides
using Google's Vertex AI and GenAI SDK. The application offers endpoints for
generating agendas, content, adding slides, and reshuffling slides based on input parameters.
"""

# Standard library imports
import re
import json
import gcsfs
import random
import time
import concurrent.futures
from datetime import datetime

# Third-party imports
import vertexai
from pydantic import BaseModel
from google.cloud import storage
from vertexai.generative_models import GenerativeModel, Part
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from google import genai
from google.genai import types

# Internal imports

from src.reusable_slides import Architectural_slides
from src.add_slides import add_slide, image_data_extraction
from src.reshuffle import reshuffle_slide, generate_new
from src.configuration import configuration
from src.template_sorting import get_placeholders_json
from src.outline_generator import outline_generator
from src.slide_search import slide_search
from src.translate_slides import Translate_slides
from src.new_content_gen import gen_text, run_parallel_task, run_cust_task, ensemble_retriver, generate_cust_info
from src.sales_play import sales_play, cust_insights
from src.nano_banana_generate import generate_slide_pipeline
from src.nano_banana_transform import transform_slide_pipeline

app = FastAPI()

@app.get("/")
def home():
    """Home endpoint to check the API status."""
    return {"message": "Now you are in PitchGen API endpoint"}

class Parameters(BaseModel):
    """Model for parameters required to generate agendas."""
    business_context: str
    region: str = ""
    industry: str = ""
    er_number: str = ""
    customer_name: str = ""
    audience: list[str] = []
    solution: list[str] = []
    product: list[str] = []
    salesPlay: list[str] = []

class Fields(BaseModel):
    """Model for fields required to generate content."""
    title: str
    business_context: str
    filename: str
    region: str = ""
    industry: str = ""
    er_number: str = ""
    customer_name: str = ""
    outline: list[str]
    url_list: list[str] = []
    audience: list[str] = []
    solution: list[str] = []
    product: list[str] = []
    salesPlay: list[str] = []

class Fields_V1(BaseModel):
    """Model for fields required to generate content."""
    title: str
    business_context: str
    filename: str
    region: str = ""
    industry: str = ""
    er_number: str = ""
    customer_name: str = ""
    outline: list[str]
    url_list: list[str] = []
    audience: list[str] = []
    solution: list[str] = []
    product: list[str] = []
    agendas: list[dict]
    salesPlay: list[str] = []

class Slides(BaseModel):
    """Model for slide details required to add a new slide."""
    slide_image_url: str = ""
    slide_title: str = ""
    slide_content: str
    slide_layout: str = ""
    slide_category: str = ""
    deck_id: str = ""
    slide_id: str = ""

class Shuffle(BaseModel):
    """Model for shuffle details required to reshuffle a slide."""
    request_file_url: str

class translationData(BaseModel):
    """Model for translate details required to translate a slide."""
    request_file_url: str

class searchSchema(BaseModel):
    """Model for search details required to search a slide."""
    request_id: str
    search_query: str
    strict_search: bool = False

class salesPlayData(BaseModel):
    """Model for sales play details required to generate sales play deck."""
    request_file_url: str

class imageGenSchema(BaseModel):
    """Model for image generation details required to generate a slide."""
    request_file_url: str

class imageTransSchema(BaseModel):
    """Model for transformation image generation details required to generate a transformed image."""
    request_file_url: str

def upload_text_from_blob(bucket_name, data, filename):
    """
    Upload text data to a specified Google Cloud Storage bucket.

    Args:
        bucket_name (str): The name of the GCS bucket.
        data (str): The text data to upload.
        filename (str): The name of the file to create in the bucket.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(filename)
    blob.upload_from_string(data)

def upload_json_from_blob(bucket_name, data, filename):
    """
    Upload JSON data to a specified Google Cloud Storage bucket.

    Args:
        bucket_name (str): The name of the GCS bucket.
        data (str): The JSON data to upload.
        filename (str): The name of the file to create in the bucket.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(filename)
    blob.upload_from_string(data, content_type='application/json')

def get_agenda_struct(agenda_text):
    """
    Parses agenda text and structures it.

    Args:
        agenda_text (str): Raw agenda text.

    Returns:
        dict: Structured representation of the agenda.
    """
    agenda_lines = agenda_text.split('\n')
    agenda_lines = [val.replace('*', '').strip() for val in agenda_lines if val]

    agendas = {}
    for i in range(len(agenda_lines)):
        temp = []
        first = ''
        dot_ind = agenda_lines[i].find('.')
        if dot_ind > -1:
            first = agenda_lines[i][:dot_ind]
        if first.isnumeric():
            temp.append(agenda_lines[i])
            i += 1
            while(i < len(agenda_lines) and (not agenda_lines[i][0].isnumeric())):
                temp.append(agenda_lines[i])
                i += 1
            temp[0] = temp[0].split('.')[1].strip()
            agendas[first] = {
              'title': temp[0],
              'parts': temp[1:]
              }
            i-=1
    return agendas

def get_final_content(item, place_holders, agendas, reusable_slides, sources):
    """
    Generate the final presentation content by merging placeholders, agendas, and reusable slides.

    Args:
        place_holders (dict): The placeholders for slide content.
        agendas (dict): The structured agendas.
        reusable_slides (dict): The reusable slide suggestions.
        customer_name (str): The name of the customer.

    Returns:
        dict: The final structured content for the presentation.
    """
    noAgendas = len(agendas.keys())

    with open('config/mapping.json','r') as f:
        mappings = json.loads(f.read())

    title_slide_id = mappings['title'][str(random.randint(1, 3))]
    title_slide = {
        "temp_url": (
          f"https://docs.google.com/presentation/d/"
          f"{mappings['title']['deckId']}/edit#slide=id.{title_slide_id}"
        ),
        "placeholders": {"title": item.title}
      }

    if noAgendas < 4:
        agenda_slide_id = random.choice(mappings['agenda']['4'])
    elif noAgendas > 10:
        agenda_slide_id = random.choice(mappings['agenda']['10'])
    else:
        agenda_slide_id = random.choice(mappings['agenda'][str(noAgendas)])

    ph_dict = {}
    for key in agendas.keys():
        ph_dict["agenda"+key] = agendas[key]['title']
    agenda_slide = {
        "temp_url": f"https://docs.google.com/presentation/d/{mappings['agenda']['deckId']}/edit#slide=id.{agenda_slide_id}",
        "placeholders": ph_dict
      }

    divider_slide_ids = mappings['divider'][str(random.randint(1, 4))]
    divider_slides = {}
    for key in agendas.keys():
        ind = (int(key) - 1) % 4
        divider_slides[key] = {
        "temp_url": (
          f"https://docs.google.com/presentation/d/"
          f"{mappings['divider']['deckId']}/edit#slide=id."
          f"{divider_slide_ids[ind]}"
        ),
        "placeholders": {
            "num": "{:02d}".format(int(key)),
            "title": agendas[key]['title']
            },
        "sources": sources[key] if key in sources.keys() else []
        }

    thank_slide_id = mappings['thank'][str(random.randint(1, 6))]
    thank_slide = {
        "temp_url": (
          f"https://docs.google.com/presentation/d/"
          f"{mappings['thank']['deckId']}/edit#slide=id."
          f"{thank_slide_id}"
        ),
      }

    finalcontent = [[] for i in range(noAgendas+1)]
    finalcontent[0].extend([title_slide, agenda_slide])
    
    for i in range(noAgendas):
        finalcontent[i].append(divider_slides[str(i+1)])
        try:
            for j in range(len(place_holders[str(i+1)]['slides'].keys())):
                finalcontent[i].append(place_holders[str(i+1)]['slides'][str(j+1)])
        except Exception as e:
            print(e)
            continue
    finalcontent[-1].append(thank_slide)
    
    finalcontent_struct = {"sections": {}}
    for i in range(len(finalcontent)):
        finalcontent_struct['sections'][str(i)] = {"slides": {}}
        for j in range(len(finalcontent[i])):
            finalcontent_struct['sections'][str(i)]["slides"][str(j+1)] = finalcontent[i][j]

    return finalcontent_struct

@app.post("/getAgendas")
async def getAgendas(item: Parameters, request: Request):
    """
    Endpoint to generate agendas based on provided parameters.

    Args:
        item (parameters): Object containing parameters such as 
        ER number, audience, industry, solution, support type,
        business context, and customer name.
        request (Request): FastAPI request object.

    Returns:
        dict: Agenda structure generated based on the input context.
    """
    print("Generating outline...")

    config= configuration()
    query_url = str(request.base_url) + "/getAgendas"

    er_number = item.er_number
    filename = item.customer_name.replace(" ","_")

    input_context = f"""
      ER: {er_number}
      Customer: {item.customer_name}
      Audience: {item.audience}
      Industry: {item.industry}
      Solutions: {item.solution}
      Products: {item.product}
      Business Context and Focus: {item.business_context}
      """
    
    print("-----------------------------------------------------------------------")
    print("Context: ")
    print(input_context.strip())
    print("-----------------------------------------------------------------------")

    try:
        project_id=config['default']['PROJECT_NAME']
        region = config['default']['REGION']
        bucket_name = config['bucket']['CONTENT']
        print("Sending context to the model...")
        out_gen = outline_generator(item, config)
        outline = out_gen.generateOutline()

        if not outline:
            raise Exception("Error occured while generating outline.")

        outID = datetime.now().strftime('%Y%m%d%H%M%S%f')
        outfile = f"outline_{er_number}_{filename}_{outID}.json"
        outline['filename'] = f"gs://{bucket_name}/{outfile}"

        item = Fields(title= '', outline= [], url_list= [], region= '', industry= '', audience= [], product= [], solution= [], er_number= '', customer_name= '', business_context= '', filename= '', salesPlay= [])
        item.title = outline['title']
        item.outline = outline['outline']
        item.url_list = outline['url_list']
        item.region = outline['region']
        item.industry = outline['industry']
        item.audience = outline['audience']
        item.product = outline['product']
        item.solution = outline['solution']
        item.er_number = outline['er_number']
        item.customer_name = outline['customer_name']
        item.business_context = outline['business_context']
        item.filename = outline['filename']
        item.salesPlay = outline['salesPlay']

        # vertexai.init(project=project_id, location=region)
        # model = GenerativeModel(
        #   "gemini-2.5-pro",
        #   system_instruction=["You must generate a JSON object."])
        # generation_config = {
        #     "temperature": 0,
        #     "response_mime_type": "application/json"
        #   }
        client = genai.Client(
            vertexai=True, 
            project=config['default']['PROJECT_NAME'], 
            location=config['default']['region']
        )

        audience = ", ".join(item.audience)
        industry = item.industry
        customer_name = item.customer_name
        filename = item.filename
        outline = item.outline

        #print("-----item-----", item)
        filter_outline = Architectural_slides(item,{})
        #print("-----filter_outline-----\n",filter_outline)
        results = filter_outline.filtered_outline()
        #print("-----results-----\n",results)
        filtered_outline = results[1]
        #print("-----filtered_outline-----",filtered_outline)

        with open("prompt_templates/outlineToAgendas.txt", "r") as f:
            agendas_prompt = f.read()

        with open('config/ind_mapping.json','r') as f:
            mappings = json.loads(f.read())
        indMap = mappings['indABB']

        if '-' in industry and ('public' not in industry.lower()):
            ind_parts = list(map(lambda x: x.strip(), industry.split(' - ')))
            industry = {'industry': indMap[ind_parts[0]], 'sub-industry': ind_parts[1]}

        agendas_inp = {
          "customer": customer_name,
          "audience": audience,
          "industry": (industry['sub-industry']+" in "+industry['industry']
                       if isinstance(industry, dict) else industry),
          "outline_items": filtered_outline
        }

        # response = model.generate_content(
        #   [agendas_prompt, json.dumps(agendas_inp), "\n[output]\n"],
        #   generation_config=generation_config)
        
        response = client.models.generate_content(
            model=config['default']['GEMINI_MODEL_1'],
            contents=[agendas_prompt, json.dumps(agendas_inp), "\n[output]\n"],
            config=types.GenerateContentConfig(
                system_instruction="Please provide output in json format.",
                response_mime_type="application/json",
                temperature=0,
            )
        )

        output = ""
        if response.candidates and response.candidates[0].content.parts:
            output = "".join([
                part.text for part in response.candidates[0].content.parts 
                if hasattr(part, 'text') and part.text
            ])

        #output = response.text
        #print("-----agenda output-----\n",output)
        start_index = output.index('{')
        end_index = len(output) - output[::-1].index('}')
        agenda_struct = json.loads(str(output[start_index:end_index]).strip(), strict=False)
        #print("-----structured agenda-----\n",agenda_struct)

        agendas = agenda_struct['agendas']
        cust_agenda = {
            "title": "Customer Success Stories",
            "parts": results[0],
            "cust_ref": True}

        flag = 0
        if results[0]:
            flag = 1
            cust_ind = str(len(agendas.keys()) + 1)
            for key in agendas.keys():
                if results[2] in agendas[key]['parts']:
                    cust_ind = key
                    break

            after_cust = sorted(
                [key for key in agendas.keys() if int(key)>=int(cust_ind)],
                key=lambda x: int(x),
                reverse=True)
            for val in after_cust:
                agendas[str(int(val)+1)] = agendas[val]
            agendas[cust_ind] = cust_agenda


        rem_key = []
        filter_agendas = Architectural_slides(item,{})
        cust_emds = filter_agendas.get_cust_ref_emds()
        for key in agendas.keys():
            title_emd = filter_agendas.get_embeddings_list([agendas[key]['title']])[0]
            scores = [filter_agendas.get_similarity_score(title_emd, cust_emd) for cust_emd in cust_emds]
            if any([score >= 0.7 for score in scores]) and ("cust_ref" not in agendas[key].keys()):
                rem_key.append(int(key))

        if flag:
            for val in rem_key:
                del agendas[str(val)]
        elif rem_key:
            for val in rem_key:
                if val != max(rem_key):
                    del agendas[str(val)]
            agendas[str(max(rem_key))] = cust_agenda

        i = 1
        for key in sorted(agendas.keys(), key=lambda x: int(x)):
            agendas[str(i)]=agendas[key]
            i+=1

        final_outline= {}

        final_outline['title'] = item.title
        final_outline['outline'] = item.outline
        final_outline['agendas'] = agendas
        final_outline['url_list'] = item.url_list
        final_outline['region'] = item.region
        final_outline['industry'] = item.industry
        final_outline['audience'] = item.audience
        final_outline['product'] = item.product
        final_outline['solution'] = item.solution
        final_outline['er_number'] = item.er_number
        final_outline['customer_name'] = item.customer_name
        final_outline['business_context'] = item.business_context
        final_outline['filename'] = item.filename
        final_outline['salesPlay'] = item.salesPlay

        upload_json_from_blob(bucket_name, json.dumps(final_outline, indent=2), outfile)
        print("-----------------------------------------------------------------------")
        print("Outline file uploaded to the cloud storage")
        print("-----------------------------------------------------------------------")

    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail=e)

    return final_outline

@app.post("/contentGen")
async def generation(item: Fields_V1, background_tasks: BackgroundTasks,  request: Request):
    """
    Endpoint to generate content based on provided parameters.

    Args:
        item (fields): Object containing parameters such as ER number, audience, industry, solution, 
                       support type, business context, customer name, filename, and agendas.
        background_tasks (BackgroundTasks): BackgroundTasks object to run tasks asynchronously.
        request (Request): FastAPI request object.

    Returns:
        dict: Slide result generated based on the input context.
    """
    print("Generating content...")

    config = configuration()
    project_id = config['default']['PROJECT_NAME']
    region = config['default']['REGION']
    bucket_name = config['bucket']['CONTENT']

    query_url = str(request.base_url) + "/contentGen"
    agendas = item.agendas
    customer_name = item.customer_name
    filename = item.filename

    agendas = {str(i): agenda_item for i, agenda_item in enumerate(agendas, start=1)}

    DEFAULT_VALUE = '2'

    KEYS_TO_CHECK = ['reusable', 'generated']

    for inner_dict in agendas.values():
        for key in KEYS_TO_CHECK:
            if inner_dict.get(key) == '':
                inner_dict[key] = DEFAULT_VALUE
     
    reusable_slides = Architectural_slides(item, agendas)
    #print("-----agendas-----\n", agendas)
    slides_result = reusable_slides.get_reusable_slides()

    # agendas = {str(i): item1 for i, item1 in enumerate(agendas, start=1)}

    title_lookup_map = {}
    for item1 in agendas.values():
        title = item1.get('title')
        if title:
            title_lookup_map[title] = item1

    for target_item1 in slides_result.values():
        target_title = target_item1.get('title')

        if target_title in title_lookup_map:
            source_match = title_lookup_map[target_title]

            target_item1['reusable'] = source_match.get('reusable', '')
            # target_item1['generated'] = source_match.get('generated', '')

    for outer_item1 in slides_result.values():
        try:
            limit_str = outer_item1.get('reusable')
            if not limit_str:
                continue
            cumulative_limit = int(limit_str)
        except ValueError:
            print(f"Warning: Invalid 'reusable' value found: {limit_str}. Skipping item1.")
            continue

        suggestions_list = outer_item1.get('suggestions')
        if not suggestions_list or not isinstance(suggestions_list, list):
            continue

        item1s_collected_so_far = 0
        valid_suggestions = []

        for sug_dict in suggestions_list:
            values_list = sug_dict.get('values')

            if not values_list or not isinstance(values_list, list):
                 values_list = []

            slots_remaining = cumulative_limit - item1s_collected_so_far

            if slots_remaining > 0:
                new_values = values_list[:slots_remaining]
                sug_dict['values'] = new_values
                item1s_collected_so_far += len(new_values)
            else:
                sug_dict['values'] = []

            if sug_dict['values']:
                valid_suggestions.append(sug_dict)

        outer_item1['suggestions'] = valid_suggestions

    for nested_dict in slides_result.values():
        nested_dict.pop('reusable', None)

    if customer_name == "":
        json_file_content = json.dumps(slides_result, indent=2)
    else:
        new_suggestion = {"1": {"title": "Customer Research & Insights", "suggestions": []}}

        shifted_dict = {str(int(k) + 1): v for k, v in slides_result.items()}
        slides_result = {**new_suggestion, **shifted_dict}

        json_file_content = json.dumps(slides_result, indent=2)

        new_agenda = {'1': {'title': 'Customer Research & Insights', 'parts': [], 'cust_info': True, 'reusable': '0', 'generated': '6'}}

        shifted_dict = {str(int(k) + 1): v for k, v in agendas.items()}
        agendas = {**new_agenda, **shifted_dict}

    #json_file_content = json.dumps(slides_result, indent=2)
    print("agendas:\n", agendas)
    #print("slides_result:\n", json_file_content)

    upload_json_from_blob(bucket_name, json_file_content, f"architectural_{filename}.json")
    print("-----------------------------------------------------------------------")
    print("Architectural slide suggestions file saved and uploaded to the cloud storage")
    print("-----------------------------------------------------------------------")

    background_tasks.add_task(run, item, agendas, bucket_name, slides_result)
    
    total_reusables = 0
    for key, data in slides_result.items():
        if isinstance(data, dict) and 'suggestions' in data:
            for sugg in data['suggestions']:
                if isinstance(sugg, dict):
                    total_reusables += len(sugg.get('values', []))

    final_payload = [
        slides_result,
        {"filename": f"architectural_{filename}.json"},
        {"agenda": len(agendas.keys())},
        {"reusableslide": total_reusables},
        {"gsurl": f"gs://{bucket_name}/architectural_{filename}.json"}
    ]
    return final_payload

def run(item, agendas, bucket_name, slides_result):
    """
    Run the content generation process asynchronously.

    Args:
        item (fields): Object containing parameters such as ER number, audience, industry, solution, 
                       support type, business context, customer name, filename, and agendas.
        bucket_name (str): The name of the bucket.
        slides_result (dict): The result of the slides generated.

    Returns:
        str: Task completion message.
    """
    print("New content generation started...")

    er_number= item.er_number
    audience = ", ".join(item.audience)
    
    with open('config/ind_mapping.json','r') as f:
        mappings = json.loads(f.read())
    indMap = mappings['indABB']
    
    industry = item.industry
    if '-' in industry and ('public' not in industry.lower()):
        ind_parts = list(map(lambda x: x.strip(), industry.split(' - ')))
        industry = {'industry': indMap[ind_parts[0]], 'sub-industry': ind_parts[1]}
    
    
    solution = ", ".join(item.solution)
    product = ", ".join(item.product)
    business_context = item.business_context.replace("\n"," ")
    customer_name = item.customer_name
    filename = item.filename
    url_list = item.url_list

    input_context = f"""
      Customer: {customer_name}
      Audience: {audience}
      Industry: {(industry['sub-industry']+" in "+industry['industry']
                   if isinstance(industry, dict) else industry)}
      Solutions: {solution}
      Products: {product}
      Business Context and Focus: {business_context}
      """

    objective = f"Generate Customer Information and swot analysis slide contents for the customer: {customer_name}"

    if industry:
        objective += (f''' with {(industry['sub-industry']+" in "+industry['industry']
            if isinstance(industry, dict) else industry)} industry''')
    if solution:
        objective += f" showcasing {solution} solutions"
    if product:
        objective += f"and using the products of {product}"
    if audience:
        objective += f" to the {audience}"
    if business_context:
        objective += f", with respect to the User's request: \"{business_context}\""

    for attempt in range(2):
        try:
            config=configuration()
            project_id=config['default']['PROJECT_NAME']

            new_task_list = []
            for key in agendas.keys():
                if "cust_ref" not in agendas[key].keys():
                    if agendas[key]['parts']:
                        combined_parts = " ".join(agendas[key]['parts'])
                        combined_number = " ".join(agendas[key]['generated'])
                        new_task_list.append(key + "1: " + agendas[key]['title'] + '. ' + combined_parts + '-::- ' + combined_number)
                    else:
                        combined_number = " ".join(agendas[key]['generated'])
                        new_task_list.append(key + "1: " + agendas[key]['title'] + '-::- ' + combined_number)

            split_list = [item1.split('-::-') for item1 in new_task_list]

            task_list = [[part.strip() for part in item1] for item1 in split_list]

            if customer_name == "":
                print("------Customer Name Not Avaliable------")
                formatted_content, final_source_urls = gen_text(task_list, url_list)
                final_source_urls_json = json.dumps(final_source_urls, indent=2)
            else:
                print("------Customer Name Avaliable------")
                cust_content = ""
                cust_content += f"-----Task 11 Completed successfully-----\n\n"
                cust_response = generate_cust_info(customer_name, objective)
                cust_content += cust_response + "\n\n"

                task_list = task_list[1:]
                formatted_content, final_source_urls = gen_text(task_list,url_list)
                formatted_content = "".join([cust_content, formatted_content])

                final_source_urls_json = json.dumps(final_source_urls, indent=2)

            upload_json_from_blob(bucket_name, final_source_urls_json, f"{filename}_sources.json")
            print("Sources file uploaded to the cloud storage\n")

            upload_text_from_blob(bucket_name, formatted_content, f"{filename}.txt")
            print("Text content uploaded to the cloud storage\n")

            output = get_placeholders_json(formatted_content, layout='Context')
            final_content = get_final_content(item, output['agendas'], agendas, slides_result, final_source_urls)

            final_content = json.dumps(final_content, indent=2)
            upload_json_from_blob(bucket_name, final_content, f"{filename}.json")
            print("Contents with template file uploaded to the cloud storage\n")

            break

        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < 1:
                print("Retrying...")
                #time.sleep(30)

    else:
        print("\nBoth attempts failed. Could not fetch data.")

    return {"Task completed successfully"}

@app.post("/addSlide")
async def addSlide(item: Slides, request: Request):
    """
    Add a new slide to the presentation.

    Args:
        slides (Slides): The details of the slide to add.

    Returns:
        dict: The response after adding the slide.
    """
    print("Generating new slide content...")
    query_url = str(request.base_url) + "/addSlide"
    slide_image_url = item.slide_image_url
    slide_title = item.slide_title
    slide_content = item.slide_content
    slide_layout = item.slide_layout
    slide_category = item.slide_category
    slide_id = item.slide_id
    deck_id = item.deck_id
    
    if slide_image_url != "":
        try:
            text = """Extract all the text with all the fields like ER Number, Customer Name, Audience, Industry, Solution, Business context from the below image and save in a .json format"""
            
            # Create Part object for the image input
            input_data = Part.from_uri(slide_image_url, mime_type='image/png')

            er_number, audience, industry, solution, customer_name, business_context = image_data_extraction(text, input_data)
            
            with open('config/ind_mapping.json','r') as f:
                mappings = json.loads(f.read())
            indMap = mappings['indABB']
            if '-' in industry and ('public' not in industry.lower()):
                ind_parts = list(map(lambda x: x.strip(), industry.split(' - ')))
                industry = indMap[ind_parts[0]]
            
        except Exception as e:
            print("error:",e)
            audience = []
            industry = ""
            solution = []
            customer_name = ""                   
    else:
        audience = []
        industry = ""
        solution = []
        customer_name = ""
        
    input_context = f"""
      Customer Audience: {audience}
      Industry: {industry}
      solution: {solution}
      """
    print("-----------------------------------------------------------------------")
    print("Context: ")
    print(input_context.strip())
    print("-----------------------------------------------------------------------")

    max_retries = 2
    config = configuration()
    model=config['default']['GEMINI_MODEL']

    for attempt in range(max_retries + 1):
        try:
            print("model: ",model)
            config = configuration()
            project_id = config['default']['PROJECT_NAME']

            url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
            url_list = re.findall(url_pattern, slide_content)
            print("url list: ", url_list)

            ensemble_retriever = ensemble_retriver(url_list)

            new_slide = add_slide(ensemble_retriever, slide_title, slide_content,
                                  slide_layout, slide_category, deck_id, slide_id, model)
            print("-----------------------------------------------------------------------")
            print("new slide generation completed")
            print("-----------------------------------------------------------------------")
            
            break 

        except Exception as e:
            if attempt < max_retries:
                print(f"Attempt {attempt + 1} failed: {e}. Retrying...")
                config = configuration()
                model=config['default']['GEMINI_MODEL_1']
            else:
                print(f"Final attempt failed: {e}")
                raise HTTPException(status_code=400, detail=str(e))
#     try:
#         config=configuration()
#         project_id=config['default']['PROJECT_NAME']

#         url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
#         url_list = re.findall(url_pattern, slide_content)
#         print("url list: ", url_list)

#         ensemble_retriever=ensemble_retriver(url_list)

#         new_slide = add_slide(ensemble_retriever, slide_title, slide_content,
#                               slide_layout, slide_category, deck_id, slide_id)
#         print("-----------------------------------------------------------------------")
#         print("new slide generation completed")
#         print("-----------------------------------------------------------------------")

#     except Exception as e:
#         print(e)
#         raise HTTPException(status_code=400, detail=e)

    return new_slide

@app.post("/reShuffle")
async def reshuffle(item: Shuffle, request: Request):
    """
    Reshuffle a slide based on specified criteria.

    Args:
        shuffle (Shuffle): The details of the slide to reshuffle.

    Returns:
        dict: The response after reshuffling the slide.
    """
    print("Transforming slide...")
    query_url = str(request.base_url) + "/reShuffle"
    request_file_url = item.request_file_url

    max_retries = 3
    config = configuration()
    model=config['default']['GEMINI_MODEL']

    for attempt in range(max_retries):
        try:
            print("model: ",model)
            config = configuration()

            project_name = config['default']['project_name']
            bucket_name = config['bucket']['content']
            gcs_file_system = gcsfs.GCSFileSystem(project=project_name)

            with gcs_file_system.open(request_file_url, 'r') as transform_object:
                transform_data = transform_object.read()

            transform_dict = json.loads(transform_data)

            toggle = transform_dict['toggle']

            if toggle is False:
                print("toggle is false")
                slide_image_url = transform_dict['slide_image_url']
                output_criteria = transform_dict['output_criteria']
                slide_layout = transform_dict['slide_layout']
                slide_category = transform_dict['slide_category']
                deck_id = transform_dict['deck_id']
                slide_id = transform_dict['slide_id']

                reshuffled_slide = reshuffle_slide(slide_image_url, output_criteria, slide_layout,
                                                   slide_category, deck_id, slide_id, model)
                print("\nreshuffled_slide: \n",reshuffled_slide)

                response_file_name = ('transform_data/' + ''.join(request_file_url.split('/')[-1].split('_')[:-1]) + '_TrueResponse.json')
                storage_client = storage.Client()
                transform_bucket = storage_client.bucket(config['bucket']['content'])
                blob = transform_bucket.blob(response_file_name)
                blob.upload_from_string(json.dumps(reshuffled_slide, indent=2), content_type='application/json')
                response_file_url = f"gs://{config['bucket']['content']}/{response_file_name}"

                response = {
                                "request": request_file_url,
                                "response": response_file_url
                            }
                print("-----------------------------------------------------------------------")
                print("Slide transformation completed")
                print("-----------------------------------------------------------------------")

            else:
                print("toggle is true")
                output_criteria = transform_dict['output_criteria']

                final_data = generate_new(transform_dict, output_criteria, model)
                print("\nfinal_data: \n",final_data)

                response_file_name = ('transform_data/' + ''.join(request_file_url.split('/')[-1].split('_')[:-1]) + '_FalseResponse.json')
                storage_client = storage.Client()
                transform_bucket = storage_client.bucket(config['bucket']['content'])
                blob = transform_bucket.blob(response_file_name)
                blob.upload_from_string(json.dumps(final_data, indent=2), content_type='application/json')
                response_file_url = f"gs://{config['bucket']['content']}/{response_file_name}"

                response = {
                                "request": request_file_url,
                                "response": response_file_url
                            }
                print("-----------------------------------------------------------------------")
                print("Slide transformation completed")
                print("-----------------------------------------------------------------------")
            break
            
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying...")
                config = configuration()
                model=config['default']['GEMINI_MODEL_1']
                #time.sleep(delay_seconds)
            else:
                print("  All retries failed.")
                
    else:
        print("\nBoth attempts failed. Could not fetch data.")
        response = {
                        "request": request_file_url,
                        "response": request_file_url
                    }

    return response

@app.post("/searchSlide")
async def searchSlide(item: searchSchema, request: Request):
    """
    Search a slide based on user's query.

    Args:
        item (searchSchema): Query details to search a slide.

    Returns:
        response (dict): request id with response file url.
    """
    print("Searching slides...")
    query_url = str(request.base_url) + "/searchSlide"
    request_id = item.request_id
    searchQuery = item.search_query
    is_strict = item.strict_search

    max_retries = 2
    response = None
    config = configuration()
    model=config['default']['GEMINI_MODEL']

    for attempt in range(max_retries + 1):
        try:
            print("model: ",model)
            config = configuration()
            bucket_name = config['bucket']['content']
            
            slide_search_obj = slide_search(searchQuery, is_strict, config, model)
            slide_search_res = slide_search_obj.search_slides()
            
            if slide_search_res:
                slide_search_op = {
                    "search_query": searchQuery,
                    "search_results": slide_search_res
                }

                json_file_content = json.dumps(slide_search_op, indent=2)
                upload_json_from_blob(
                    bucket_name, json_file_content, f"search_data/search_{request_id}.json")
                result_filename = f"gs://{bucket_name}/search_data/search_{request_id}.json"
                print(f"res_filename: {result_filename}")
                
                response = {
                    "request_id": request_id,
                    "response_file_url": result_filename
                }
            else:
                response = {
                    "request_id": request_id,
                    "response_file_url": None
                }
                
            print("-----------------------------------------------------------------------")
            print("Slide search completed")
            print("-----------------------------------------------------------------------")
            
            break 

        except Exception as e:
            if attempt < max_retries:
                print(f"Attempt {attempt + 1} failed: {e}. Adjusting inputs and retrying...")
                config = configuration()
                model=config['default']['GEMINI_MODEL_1']
            else:
                print(f"Final attempt failed: {e}")
                raise HTTPException(status_code=400, detail=str(e))

    return response

#     try:
#         config = configuration()
#         bucket_name = config['bucket']['content']
#         slide_search_obj = slide_search(searchQuery, is_strict, config)
#         slide_search_res = slide_search_obj.search_slides()
#         if slide_search_res:
#             slide_search_op = {
#                 "search_query": searchQuery,
#                 "search_results": slide_search_res
#             }

#             json_file_content = json.dumps(slide_search_op, indent=2)
#             upload_json_from_blob(
#                 bucket_name, json_file_content, f"search_data/search_{request_id}.json")
#             result_filename = f"gs://{bucket_name}/search_data/search_{request_id}.json"
#             print(f"res_filename: {result_filename}")
#             response = {
#                 "request_id": request_id,
#                 "response_file_url": result_filename
#             }
#         else:
#             response = {
#                 "request_id": request_id,
#                 "response_file_url": None
#             }
#         print("-----------------------------------------------------------------------")
#         print("Slide search completed")
#         print("-----------------------------------------------------------------------")

#     except Exception as e:
#         print(e)
#         raise HTTPException(status_code=400, detail=e)

#     return response

@app.post("/translation")
async def translation(item: translationData, background_tasks: BackgroundTasks, request: Request):
    """
    Translate a slide based on specified criteria.

    Args:
        request_file_url (translationData): The details of the slide to be translated.

    Returns:
        response (dict): request url and response url after translation of the deck/slide.
    """
    print("translation response filename generation in progress...")

    query_url = str(request.base_url) + "/translation"
    request_file_url = item.request_file_url

    try:
        config = configuration()
        model=config['default']['GEMINI_MODEL']
        project_name = config['default']['project_name']
        bucket_name = config['bucket']['content']
        gcs_file_system = gcsfs.GCSFileSystem(project=project_name)

        with open('config/translate.json','r') as f:
            mappings = json.loads(f.read())
        codeToLang = mappings['codeToLang']
        langToCode = mappings['langToCode']

        print("you are now in translation module")
        with gcs_file_system.open(request_file_url, 'r') as translate_object:
            translate_data = translate_object.read()

        translate_dict = json.loads(translate_data)

        input_data = translate_dict[translate_dict['presentationId']] # fetch actual data
        target_lang = translate_dict['targetLanguage']
        print("target language: ",target_lang)
        target_lang_code = langToCode[target_lang]

        translation_func = Translate_slides(model)
        lang_data = translation_func.get_translation_data(input_data)
        detected_langs = set(lang_data.keys())
        translate_langs = detected_langs.difference({target_lang_code})
        # print(lang_data)
        print(f"Detected languages: {detected_langs}")
        print(f"Translation to be done on: {translate_langs}")

        if translate_langs:
            response_file_name = ('translation_data/' + ''.join(request_file_url.split('/')[-1].split('_')[:-1]) + '_Response.json')
            response_file_url = f"gs://{bucket_name}/{response_file_name}"

            response = {
                "request": request_file_url,
                "response": response_file_url
            }

            print("-----------------------------------------------------------------------")
            print("translation response filename generation in completed")
            print("-----------------------------------------------------------------------")

            background_tasks.add_task(translationrun, item)

            return response
        else:
            response = {
                "request": request_file_url,
                "response": request_file_url
            }

            print("-----------------------------------------------------------------------")
            print("translation response filename generation failed")
            print("-----------------------------------------------------------------------")

            return response

    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail=e)

def translationrun(item):
    print("translation in-progress...")

    request_file_url = item.request_file_url

    max_retries = 2
    response_file_url = None
    config = configuration()
    model=config['default']['GEMINI_MODEL']

    for attempt in range(max_retries + 1):
        try:
            print("model: ", model)
            translation_func = Translate_slides(model)
            response_file_url = translation_func.process_translate_io(request_file_url)

            print("request: ", request_file_url)
            print("response: ", response_file_url)

            print("-----------------------------------------------------------------------")
            print("Slide translation completed")
            print("-----------------------------------------------------------------------")
            
            break

        except Exception as e:
            if attempt < max_retries:
                print(f"Attempt {attempt + 1} failed: {e}. Adjusting inputs and retrying...")
                config = configuration()
                model=config['default']['GEMINI_MODEL_1']
            else:
                print(f"Final attempt failed: {e}")
                raise HTTPException(status_code=400, detail=str(e))
#     try:
#         translation_func = Translate_slides()
#         response_file_url = translation_func.process_translate_io(request_file_url)

#         print("request: ", request_file_url)
#         print("response: ", response_file_url)

#         print("-----------------------------------------------------------------------")
#         print("Slide translation completed")
#         print("-----------------------------------------------------------------------")

#     except Exception as e:
#         print(e)
#         raise HTTPException(status_code=400, detail=e)

    return {"translation completed..."}

@app.post("/salesPlay")
async def salesPlay(item: salesPlayData, background_tasks: BackgroundTasks, request: Request):
    print("sales play response filename generation in progress...")

    query_url = str(request.base_url) + "/salesPlay"
    request_file_url = item.request_file_url

    try:
        
        config = configuration()

        project_name = config['default']['project_name']
        bucket_name = config['bucket']['content']
        gcs_file_system = gcsfs.GCSFileSystem(project=project_name)

        with gcs_file_system.open(request_file_url, 'r') as salesplay_object:
            salesplay_data = salesplay_object.read()

        salesplay_dict = json.loads(salesplay_data)

        customer_name=salesplay_dict['customerName']
        slide_data_json=salesplay_dict['titleObj']
        print("customer name: ",customer_name)

        response_file_name = ('sales_play/' + ''.join(request_file_url.split('/')[-1].split('_')[:-1]) + '_ContentResponse.json')
        response_file_url = f"gs://{bucket_name}/{response_file_name}"

        response = {
                        "request": request_file_url,
                        "response": response_file_url
                    }

        print("-----------------------------------------------------------------------")
        print("sales play response filename generation is completed")
        print("-----------------------------------------------------------------------")

        background_tasks.add_task(salesplayrun, item)

        return response

    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail=e)
        
def salesplayrun(item):

    request_file_url = item.request_file_url

    max_retries = 2
    response = None
    config = configuration()
    model=config['default']['GEMINI_MODEL']

    for attempt in range(max_retries + 1):
        try:
            print("model: ", model)
            print("sales play title generation in-progress...")
            response = sales_play(request_file_url, model)
            
            print("sales play content generation in-progress...")
            response_file_url = response['response']
            response = cust_insights(response_file_url, model)

            print("request: ", request_file_url)
            print("response: ", response['response'])

            print("-----------------------------------------------------------------------")
            print("sales play generation completed")
            print("-----------------------------------------------------------------------")
            
            break

        except Exception as e:
            if attempt < max_retries:
                print(f"Attempt {attempt + 1} failed: {e}. Adjusting inputs and retrying...")
                config = configuration()
                model=config['default']['GEMINI_MODEL_1']
            else:
                print(f"Final attempt failed: {e}")
                raise HTTPException(status_code=400, detail=str(e))
#     try:
#         print("sales play title generation in-progress...")
#         response = sales_play(request_file_url, model)
        
#         print("sales play content generation in-progress...")
#         response_file_url = response['response']
#         response = cust_insights(response_file_url, model)

#         print("request: ", request_file_url)
#         print("response: ", response['response'])

#         print("-----------------------------------------------------------------------")
#         print("sales play generation completed")
#         print("-----------------------------------------------------------------------")

#     except Exception as e:
#         print(e)
#         raise HTTPException(status_code=400, detail=e)

    return {"sales play completed..."}

@app.post("/nanoBanana_imageGen")
async def imageGen(item: imageGenSchema, request: Request):
    """
    generate an image slide based on user's query.

    Args:
        item (imageGenSchema): Query details to generate an image slide.

    Returns:
        response (dict): request id with response file url.
    """
    print("reading the input...")
    query_url = str(request.base_url) + "/nanoBanana_imageGen"
    request_file_url = item.request_file_url

    max_retries = 2
    response = None
    config = configuration()
    model=config['default']['GEMINI_MODEL']
    model_1=config['default']['GEMINI_MODEL_2']
    project_name = config['default']['project_name']
    bucket_name = config['bucket']['content']
    gcs_file_system = gcsfs.GCSFileSystem(project=project_name)

    for attempt in range(max_retries + 1):
        try:
            print("model: ",model)
            print("model_1: ",model_1)
            config = configuration()
            bucket_name = config['bucket']['content']

            with gcs_file_system.open(request_file_url, 'r') as image_object:
                image_data = image_object.read()

            image_dict = json.loads(image_data)
            #inputs = image_dict['user_inputs']
            print(image_dict)
            
            destination_blob_name = ('nanoBanana_imageGen/' + ''.join(request_file_url.split('/')[-1].split('.json')[:-1]) + '_Response.png')

            final_image_url=generate_slide_pipeline(image_dict, bucket_name, destination_blob_name, model, model_1)

            response = {
                "request": request_file_url,
                "response": final_image_url
            }
                
            print("-----------------------------------------------------------------------")
            print("image generation completed")
            print("-----------------------------------------------------------------------")
            
            break 

        except Exception as e:
            if attempt < max_retries:
                print(f"Attempt {attempt + 1} failed: {e}. Adjusting inputs and retrying...")
                config = configuration()
                model=config['default']['GEMINI_MODEL']
                model_1=config['default']['GEMINI_MODEL_2']
            else:
                print(f"Final attempt failed: {e}")
                raise HTTPException(status_code=400, detail=str(e))

    return response

@app.post("/nanoBanana_imageTrans")
async def imageTrans(item: imageTransSchema, request: Request):
    """
    generate an image slide based on user's query.

    Args:
        item (imageTransSchema): Query details to generate an image slide.

    Returns:
        response (dict): request id with response file url.
    """
    print("reading the input...")
    query_url = str(request.base_url) + "/nanoBanana_imageTrans"
    request_file_url = item.request_file_url

    max_retries = 2
    response = None
    config = configuration()
    model=config['default']['GEMINI_MODEL_2']
    #model_1=config['default']['GEMINI_MODEL_2']
    project_name = config['default']['project_name']
    bucket_name = config['bucket']['content']
    location = 'global'
    gcs_file_system = gcsfs.GCSFileSystem(project=project_name)

    for attempt in range(max_retries + 1):
        try:
            print("model: ",model)
            #print("model_1: ",model_1)
            config = configuration()
            bucket_name = config['bucket']['content']

            with gcs_file_system.open(request_file_url, 'r') as image_object:
                image_data = image_object.read()

            image_dict = json.loads(image_data)
            #inputs = image_dict['user_inputs']
            print(image_dict)
            
            destination_blob_name = ('nanoBanana_imageTrans/' + ''.join(request_file_url.split('/')[-1].split('.json')[:-1]) + '_Response.png')

            final_image_url=transform_slide_pipeline(image_dict, project_name, bucket_name, location, destination_blob_name, model)

            response = {
                "request": request_file_url,
                "response": final_image_url
            }
                
            print("-----------------------------------------------------------------------")
            print("image generation completed")
            print("-----------------------------------------------------------------------")
            
            break 

        except Exception as e:
            if attempt < max_retries:
                print(f"Attempt {attempt + 1} failed: {e}. Adjusting inputs and retrying...")
                config = configuration()
                model=config['default']['GEMINI_MODEL_2']
                #model_1=config['default']['GEMINI_MODEL_2']
            else:
                print(f"Final attempt failed: {e}")
                raise HTTPException(status_code=400, detail=str(e))

    return response
