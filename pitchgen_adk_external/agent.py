import sys
import os
import json
import datetime
import random
from google.adk import Agent
from google.adk.tools import FunctionTool
from google.cloud import storage

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
os.chdir(current_dir)

from src.configuration import configuration
from src_agent.skills.content_generator import generate_slide_content
from src_agent.skills.template_selector import process_slides_with_templates

def upload_json_to_gcs(data_dict, filename):
    try:
        config = configuration()
        bucket_name = config['bucket']['content']
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(filename)
        blob.upload_from_string(
            json.dumps(data_dict, indent=2), 
            content_type='application/json'
        )
        return f"gs://{bucket_name}/{filename}"
    except Exception as e:
        print(f"Error uploading to GCS: {e}")
        return None

def upload_text_to_gcs(text_data, filename):
    try:
        config = configuration()
        bucket_name = config['bucket']['content']
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(filename)
        blob.upload_from_string(text_data, content_type='text/plain')
        return f"gs://{bucket_name}/{filename}"
    except Exception as e:
        print(f"Error uploading text to GCS: {e}")
        return None

def get_final_content(item, place_holders, agendas, reusable_slides, sources):
    """
    Generate the final presentation content by merging placeholders, agendas, and reusable slides.
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

def slide_generator_skill(payload_json: str) -> str:

    """
    Skill to generate slide content and map templates from a JSON payload.
    It first tries to retrieve reusable slides. If no reusable slides are found,
    it falls back to generative content creation.
    """
    try:
        payload = json.loads(payload_json)
        if not isinstance(payload, dict):
            return "Error: Invalid JSON payload. Expected a dictionary/object, but got a list or other type."
    except json.JSONDecodeError:
        return "Error: Invalid JSON payload provided. Please provide a valid JSON string."

    agendas = payload.get('agendas', [])
    url_list = payload.get('url_list', [])
    
    filename_prefix = payload.get('filename', payload.get('user_input_id', 'agent_response'))
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    gcs_filename = f"{filename_prefix}_{timestamp}.json"
    
    print("Agent: Checking for reusable slides...")
    try:
        from src.reusable_slides import Architectural_slides
        class MockItem:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        item = MockItem(
            industry=payload.get('industry', ''),
            solution=[payload.get('solution')] if isinstance(payload.get('solution'), str) else payload.get('solution', []),
            customer_name=payload.get('customer_name', ''),
            product=[payload.get('product')] if isinstance(payload.get('product'), str) else payload.get('product', []),
            region=payload.get('region', ''),
            outline=payload.get('outline', []),
            title=payload.get('title', ''),
            audience=payload.get('audience', []),
            business_context=payload.get('business_context', ''),
            salesPlay=payload.get('salesPlay', [])
        )
        
        # Build original agendas_dict for Architectural_slides
        agendas_dict_original = {}
        for i, agenda_item in enumerate(agendas, start=1):
            agenda_copy = agenda_item.copy()
            agenda_copy['key'] = str(i)
            agendas_dict_original[str(i)] = agenda_copy

        DEFAULT_VALUE = '2'
        for inner_dict in agendas_dict_original.values():
            for key in ['reusable', 'generated']:
                if inner_dict.get(key) == '':
                    inner_dict[key] = DEFAULT_VALUE
                    
        reusable_slides = Architectural_slides(item, agendas_dict_original)
        slides_result = reusable_slides.get_reusable_slides()

        title_lookup_map = {item1.get('title'): item1 for item1 in agendas_dict_original.values() if item1.get('title')}
        for target_item1 in slides_result.values():
            target_title = target_item1.get('title')
            if target_title in title_lookup_map:
                target_item1['reusable'] = title_lookup_map[target_title].get('reusable', '')

        total_reusables = 0
        for outer_item1 in slides_result.values():
            try:
                limit_str = outer_item1.get('reusable')
                cumulative_limit = int(limit_str) if limit_str else 0
            except ValueError:
                cumulative_limit = 0
                
            suggestions_list = outer_item1.get('suggestions', [])
            item1s_collected_so_far = 0
            valid_suggestions = []
            if suggestions_list and isinstance(suggestions_list, list):
                for sug_dict in suggestions_list:
                    values_list = sug_dict.get('values', [])
                    if not isinstance(values_list, list): values_list = []
                    slots_remaining = cumulative_limit - item1s_collected_so_far
                    if slots_remaining > 0:
                        new_values = values_list[:slots_remaining]
                        sug_dict['values'] = new_values
                        item1s_collected_so_far += len(new_values)
                        valid_suggestions.append(sug_dict)
                    else:
                        sug_dict['values'] = []
                        
            outer_item1['suggestions'] = valid_suggestions
            total_reusables += item1s_collected_so_far
                
        for nested_dict in slides_result.values():
            nested_dict.pop('reusable', None)

        # Now construct the final agendas_dict (inserting customer success if needed)
        agendas_dict = agendas_dict_original.copy()
        if item.customer_name != "":
            # Update slides_result
            new_suggestion = {"1": {"title": "Customer Research & Insights", "suggestions": []}}
            shifted_dict = {str(int(k) + 1): v for k, v in slides_result.items()}
            slides_result = {**new_suggestion, **shifted_dict}

            # Update agendas_dict
            new_agenda = {'key': '1', 'title': 'Customer Research & Insights', 'parts': [], 'cust_info': True, 'reusable': '0', 'generated': '6'}
            shifted_agendas = {str(int(k) + 1): {**v, 'key': str(int(v['key']) + 1)} for k, v in agendas_dict.items()}
            agendas_dict = {**new_agenda, **shifted_agendas}

        agendas_to_generate = [agenda for agenda in agendas_dict.values() if not agenda.get('cust_ref') and not agenda.get('cust_info')]
        agendas_for_templates = [agenda for agenda in agendas_dict.values() if not agenda.get('cust_ref')]

    except Exception as e:
        print(f"Agent: Error fetching reusable slides: {e}. Falling back to generation.")
        slides_result = {}
        total_reusables = 0
        
        # Build agendas_dict from original agendas
        agendas_dict = {}
        for i, agenda_item in enumerate(agendas, start=1):
            agenda_copy = agenda_item.copy()
            agenda_copy['key'] = str(i)
            agendas_dict[str(i)] = agenda_copy
            
        if item.customer_name != "":
            new_agenda = {'key': '1', 'title': 'Customer Research & Insights', 'parts': [], 'cust_info': True, 'reusable': '0', 'generated': '6'}
            shifted_agendas = {str(int(k) + 1): {**v, 'key': str(int(v['key']) + 1)} for k, v in agendas_dict.items()}
            agendas_dict = {**new_agenda, **shifted_agendas}
            
        agendas_to_generate = [agenda for agenda in agendas_dict.values() if not agenda.get('cust_ref') and not agenda.get('cust_info')]
        agendas_for_templates = [agenda for agenda in agendas_dict.values() if not agenda.get('cust_ref')]

    total_slides = 0
    formatted_content = ""
    final_source_urls = {}

    if agendas_to_generate or (item.customer_name != ""):
        print(f"Agent: Starting generative content creation...")
        
        cust_content = ""
        if item.customer_name != "":
            print("Agent: Customer Name Available. Generating customer info...")
            from src.new_content_gen import generate_cust_info
            
            audience = ", ".join(item.audience) if isinstance(item.audience, list) else item.audience
            solution = ", ".join(item.solution)
            product = ", ".join(item.product)
            business_context = item.business_context.replace("\n", " ")
            
            objective = f"Generate Customer Information and swot analysis slide contents for the customer: {item.customer_name}"
            if item.industry:
                objective += f" with {item.industry} industry"
            if solution:
                objective += f" showcasing {solution} solutions"
            if product:
                objective += f" and using the products of {product}"
            if audience:
                objective += f" to the {audience}"
            if business_context:
                objective += f", with respect to the User's request: \"{business_context}\""
                
            cust_content += f"-----Task 11 Completed successfully-----\n\n"
            cust_response = generate_cust_info(item.customer_name, objective)
            cust_content += cust_response + "\n\n"

        if agendas_to_generate:
            gen_content, gen_sources = generate_slide_content(agendas_to_generate, url_list)
            formatted_content = cust_content + gen_content
            final_source_urls = gen_sources
        else:
            formatted_content = cust_content
            final_source_urls = {}

        text_filename = f"{filename_prefix}_{timestamp}.txt"
        text_gcs_path = upload_text_to_gcs(formatted_content, text_filename)
        if text_gcs_path:
            print(f"Agent: Text content successfully uploaded to {text_gcs_path}")

        print("Agent: Starting template selection and placeholder mapping...")
        sections_raw, total_templates = process_slides_with_templates(formatted_content, agendas_for_templates)

        place_holders = {}
        for key, val in sections_raw.items():
            place_holders[key] = {
                "slides": val["slides"]
            }

        final_content = get_final_content(item, place_holders, agendas_dict, slides_result, final_source_urls)
        total_slides = sum(len(sec["slides"]) for sec in final_content["sections"].values())
    else:
        place_holders = {key: {"slides": {}} for key in agendas_dict.keys()}
        final_content = get_final_content(item, place_holders, agendas_dict, slides_result, final_source_urls)

    agenda_count = len(agendas_dict)
    arch_filename = f"architectural_{filename_prefix}_{timestamp}.json"
    content_filename = f"{filename_prefix}_{timestamp}.json"

    print("Agent: Uploading twin files to GCS...")
    gcs_path_arch = upload_json_to_gcs(slides_result, arch_filename)
    gcs_path_content = upload_json_to_gcs(final_content, content_filename)

    final_list = [
        {"architectural_filename": arch_filename},
        {"outputs_filename": content_filename},
        {"agenda": agenda_count}
    ]

    if total_reusables > 0:
        final_list.append({"reusableslide": total_reusables})
    if total_slides > 0:
        final_list.append({"generatedslides": total_slides})
    if gcs_path_arch:
        final_list.append({"gsurl_architectural": gcs_path_arch})
    if gcs_path_content:
        final_list.append({"gsurl_outputs": gcs_path_content})

    print("Agent: Response twin files uploaded successfully.")
    return json.dumps(final_list, indent=2)


# Define the ADK Agent
root_agent = Agent(
    name="slide_generator_agent_payloadinputoupt",
    model=os.getenv("MODEL", "gemini-2.5-flash"),
    description="Generates slide content and maps templates from a JSON agenda.",
    instruction="You are a Slide Generator Agent. Use the 'slide_generator_skill' tool to process the user's JSON payload. Always pass the raw JSON string to the tool.",
    tools=[FunctionTool(slide_generator_skill)]
)

if __name__ == "__main__":
    # Example payload for testing
    example_payload = {
        "agendas": [
            {
                "title": "Strategic AI Vision & Readiness",
                "parts": ["Defining the strategic vision for AI adoption", "Assessing organizational readiness and data maturity"],
                "reusable": ""
            }
        ],
        "url_list": [],
        "filename": "test",
        "industry": "insurance",
        "solution": ["artificial intelligence"],
        "region": "GLOBAL"
    }
    
    try:
        print("Running standalone test...")
        result = slide_generator_skill(json.dumps(example_payload))
        print(result)
    except Exception as e:
        print(f"Error during execution: {e}")
