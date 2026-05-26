"""
This module defines the `outline_generator` class used to generate a structured 
outline based on provided business context and configuration settings. 
It leverages Google Cloud's Vertex AI for generative content and Discovery Engine 
for web search.
"""
import re
import base64
import json
import vertexai
from google.cloud import secretmanager
from vertexai.generative_models import GenerativeModel
from google.cloud import discoveryengine_v1 as discoveryengine
from google import genai
from google.genai import types

#from src.company_data import Company

class outline_generator:
    """
    A class to generate structured outlines based on business context and configuration settings.
    
    This class uses Google Cloud's Vertex AI for generating content and Discovery Engine for web search
    to gather relevant information. It processes business context data and generates a comprehensive
    outline tailored to the provided context.
    """
    def __init__(self, item, config):
        """
        Initializes the outline_generator with the provided business context and configuration.

        Args:
            item: An object containing business context and relevant data for generating 
            the outline.
            config: A dictionary containing configuration settings, including project and 
            datastore information.

        Attributes:
            config (dict): Configuration settings.
            item (object): Business context and data.
            __project_id (str): Google Cloud project ID.
            __location (str): Location for the services, default is 'global'.
            __website_store_id (str): Datastore ID for the website.
            __web_client (discoveryengine_v1.SearchServiceClient): Client for Discovery Engine 
            search.
            website_serving_config (str): Path to the serving configuration for the website.
            model (GenerativeModel): Vertex AI generative model instance.
            generation_config (dict): Configuration for the generative model, e.g., temperature 
            setting.

        Methods:
            web_search(query: str) -> str:
                Performs a web search using the Discovery Engine and returns a 
                summary of the results.

            generateOutline() -> dict:
                Generates a structured outline based on the business context and 
                configuration settings.
        """
        self.config = config
        self.item = item
        self.__project_id = config['default']['PROJECT_NAME']
        self.__region = config['default']['REGION']
        self.__location = config.get('default', 'discovery_engine_location', fallback=config.get('default', 'region', fallback='global'))
        self.__gemini_model=config['default']['GEMINI_MODEL']
        self.__gemini_model_1=config['default']['GEMINI_MODEL_1']
        self.__url_business_context = self.item.business_context
        self.__url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
        self.__url_list = re.findall(self.__url_pattern, self.__url_business_context)
        
        try:
            sec_client = secretmanager.SecretManagerServiceClient()
            sec_parent = sec_client.secret_path(
                project=self.__project_id,
                secret=self.config['datastore']['website'])
            response = sec_client.access_secret_version(
                request={"name": f"{sec_parent}/versions/latest"})
            self.__website_store_id = response.payload.data.decode('UTF-8')
        except Exception as e:
            print(f"Could not access secret, falling back to default: {e}")
            self.__website_store_id = self.config['datastore']['website']

        self.__web_client = discoveryengine.SearchServiceClient()

        self.website_serving_config = self.__web_client.serving_config_path(
            project=self.__project_id,
            location=self.__location,
            data_store=self.__website_store_id,
            serving_config='default_config',
        )

        vertexai.init(project= self.__project_id, location=self.__region)
        import os
        model_name = os.getenv("MODEL", "gemini-2.5-pro")
        self.model = GenerativeModel(
          model_name,
          system_instruction=['You must generate a JSON object.'])
        self.generation_config = {
            'temperature': 0,
			"response_mime_type": "application/json"
          }
        self.context_entities = {
          'customer_name': '',
          'audience': [],
          'industry': '',
          'sub-industry': '',
          'solution': [],
          'product': [],
          'region': '',
          'outline_items': []}

        self.outline = {
          'title': 'Google Cloud ',
          'outline': [],
          'url_list': [],
          'region': '',
          'industry': '',
          'audience': [],
          'product': [],
          'solution': [],
          'er_number': '',
          'customer_name': '',
          'business_context': '',
          'filename': '',
          'salesPlay': []}

    def web_search(self, query):
        """
        Performs a web search using the Discovery Engine and returns a summary of the results.

        Args:
            query (str): The search query string.

        Returns:
            str: A summary of the search results with metadata.
        """
        result = ''
        content_search_spec = discoveryengine.SearchRequest.ContentSearchSpec(
            summary_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec(
                summary_result_count=5,
                include_citations=True,
                ignore_adversarial_query=True,
                ignore_non_summary_seeking_query=True,
            )
        )
        request = discoveryengine.SearchRequest(
            content_search_spec=content_search_spec,
            serving_config=self.website_serving_config,
            query=query,
            page_size=5,
        )
        try:
            response = self.__web_client.search(request)
            result = response.summary.summary_with_metadata.summary
        except Exception as e:
            print(e)
            pass
        return result

    def generate(self, company_name):
        client = genai.Client(
            vertexai=True,
            project=self.__project_id,
            location=self.config['default']['region'],
        )
        prefix_text=f"""Analyze the following company: {company_name}."""
        suffix_text="""\nDetermine the primary industry from this list: ['Automotive', 'Consumer Packaged Goods', 'Energy & Utilities', 'Financial Services & Insurance', 'Games', 'Healthcare', 'Life Sciences', 'Manufacturing', 'Media & Entertainment', 'Public Sector & EDU', 'Retail & Consumer', 'Telecommunications', 'Travel & Hospitality', 'Supply Chain Management', 'Logistics', 'Sustainability'].\n\nConduct a SWOT analysis consisting of strengths, weaknesses, opportunities, and threats.\n\nThe output should be in the following JSON format:\n```json\n{\"Company_Name\": \"\", \"Company_Description\": \"\", \"Industry\": \"\", \"SWOT_Analysis\": \"\"}\n```"""
        msg1_text1 = types.Part.from_text(text=prefix_text+ "\n" + suffix_text)
        si_text1 = """You are a business analyst expert at performing company analysis. Your task is to analyze a given company, identify its listed company name, provide its description, determine its primary industry from a given list of industries, and conduct a SWOT analysis consisting of strengths, weaknesses, opportunities, and threats."""

        model=self.__gemini_model_1
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
          temperature = 1,
          top_p = 0.95,
          seed = 0,
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
            # Verify candidates and parts exist before iterating
            if not chunk.candidates or not chunk.candidates[0]:
                continue
            content = chunk.candidates[0].content
            if not content or not content.parts:
                continue
            
            # Safely extract ONLY the text part, ignoring thoughts and signatures
            for part in content.parts:
                if hasattr(part, 'text') and part.text:
                    text_chunks.append(part.text)

        final_response = "".join(text_chunks)

        return final_response
#         text_chunks=[]
#         for chunk in client.models.generate_content_stream(
#           model = model,
#           contents = contents,
#           config = generate_content_config,
#           ):
#             if not chunk.candidates or not chunk.candidates[0].content or not chunk.candidates[0].content.parts:
#                 continue
#             text_chunks.append(chunk.text)

#         final_response = "".join(text_chunks)

#         return final_response

    def generateOutline(self):
        """
        Generates a structured outline based on the business context and configuration settings.

        Returns:
            dict: A dictionary containing the generated outline and related information.
        """
        with open('config/ind_mapping.json','r') as f:
            mappings = json.loads(f.read())
        indToGD = mappings['indToGD']
        indToAbb = mappings['indABBrev']
        abbToInd = mappings['indABB']
        indToSub = mappings['subInd']
        
        indList = list(indToGD.keys()) + ['gaming']
        subIndList = list(set(sum(list(indToSub.values()), [])))
        subIndList = list(map(lambda x:x.lower(),subIndList))
        subIndList.remove('other')

        with open('prompt_templates/contextEntities.txt', 'r') as f:
            entities_prompt = f.read()
        business_context = self.item.business_context
        retry_cnt = 0
        output = ''
        while retry_cnt < 2:
            try:
                if retry_cnt > 0:
                    print('retrying...')
              #   response = self.model.generate_content(
              #     [entities_prompt, business_context, '\n[output]\n'],
              # generation_config=self.generation_config)
                client = genai.Client(
                    vertexai=True, 
                    project=self.__project_id, 
                    location=self.config['default']['region']
                )

                response = client.models.generate_content(
                    model=self.__gemini_model_1,
                    contents=[entities_prompt, business_context, '\n[output]\n'],
                    config=types.GenerateContentConfig(
                        system_instruction="Please provide output in json format.",
                        response_mime_type="application/json",
                        temperature=0,
                    )
                )
                output = ""
                content = response.candidates[0].content if response.candidates and response.candidates[0] else None
                if content and content.parts:
                    output = "".join([
                        part.text for part in content.parts 
                        if hasattr(part, 'text') and part.text
                    ])
                #output = response.text
                self.context_entities = json.loads(
                    str(output[output.index('{'):len(output)- output[::-1].index('}')]).strip(),
                    strict=False)
                break
            except Exception as e:
                if output:
                    print(output)
                print('Entity extraction failed due to: ', e)
                retry_cnt+=1
                continue

        print('entity extraction output:\n', self.context_entities)
        region = self.item.region or self.context_entities['region'] or 'GLOBAL'
        customer_name = self.item.customer_name or self.context_entities['customer_name']
        
        industry = self.item.industry
        if 'public' in industry.lower():
            industry = 'Public Sector'
        subInd = ''
        uiInd = ''

        indEnt = self.context_entities['industry'].lower().split(' in ')
        noInd = ''
        for contInd in indEnt:
            for val in [
                contInd, contInd.replace(' and ', ' & ')]:
                if val in indList:
                    industry = industry or val.title()
                    break
                elif val in subIndList:
                    subInd = val.title().replace(' And ', ' and ')
                    for indKey in indToSub.keys():
                        if subInd in indToSub[indKey]:
                            industry = industry or indKey.title()
                            break
                    break
                else:
                    noInd = contInd.title()

        company_desc = ''
        company_details = ''
        company_data = ''
        listed_company_name = None
        try:
            if customer_name:
                company_data=self.generate(customer_name)

                company_data = company_data.replace("```json", "")
                company_data = company_data.replace("```", "")

                try:
                    company_data = json.loads(company_data.strip())
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON: {e}")

                print('company_data:\n',company_data)
                print('type of company_data: ',type(company_data))

                if company_data:
                    listed_company_name = company_data['Company_Name']
                    industry = company_data['Industry']
                    ui_industry = company_data['Industry']
                    company_desc = company_data['Company_Description']
                    if company_data['SWOT_Analysis']:
                        for key in company_data['SWOT_Analysis'].keys():
                            company_details += key
                            company_details += ':\n'
                            company_details += '\n'.join([
                                  str(i+1)+'.'+company_data['SWOT_Analysis'][key][i]
                                  for i in range(len(company_data['SWOT_Analysis'][key]))])
                            company_details += '\n'
                            company_details = company_details.replace('*', '')

        except Exception as e:
            print(e)
            print('Company Extraction Failed with error: ' + str(e))
            pass

        if industry:
            ind = industry
            uiInd = ('Public Sector - Non US' 
                     if 'public' in industry.lower() else industry)
        else:
            ind = noInd
            uiInd = noInd

        solutions = self.item.solution
        if self.context_entities['solution']:
            low_sol = list(map(lambda x: x.lower(), solutions))
            for val in self.context_entities['solution']:
                if val.lower() not in low_sol:
                    solutions.append(val)
        solutions = list(set(solutions))

        sol_list = [sol + f' solution for {ind} industry.' for sol in solutions]
        sol_web = [sol + '. ' + self.web_search(sol) for sol in sol_list]
        sol_data = '\n'.join(sol_web)

        audience = self.item.audience
        if self.context_entities['audience']:
            low_aud = list(map(lambda x: x.lower(), audience))
            for val in self.context_entities['audience']:
                if val.lower() not in low_aud:
                    audience.append(val)
        audience = list(set(audience))
        audience_str = ', '.join(audience)

        products = self.item.product
        if self.context_entities['product']:
            low_prod = list(map(lambda x: x.lower(), products))
            for val in self.context_entities['product']:
                if val.lower() not in low_prod:
                    products.append(val)
        products = list(set(products))

        outline_data = {
          'audience': audience_str,
          'industry': ind,
          'region': region,
          'user_request': business_context,
          'customer_data': company_desc + '\n' + company_details,
          'solutions_data': sol_data,
          'outline_items': self.context_entities['outline_items']
        }

        print(outline_data)
        with open('prompt_templates/outlineGen.txt', 'r') as f:
            outline_prompt = f.read()

        retry_cnt = 0
        output =''
        while retry_cnt < 2:
            try:
                if retry_cnt > 0:
                    print('retrying...')
                # response = self.model.generate_content(
                #     [outline_prompt, json.dumps(outline_data), '\n[output]\n'],
                #     generation_config=self.generation_config)
                client = genai.Client(
                    vertexai=True, 
                    project=self.__project_id, 
                    location=self.config['default']['region']
                )

                response = client.models.generate_content(
                    model=self.__gemini_model_1,
                    contents=[outline_prompt, json.dumps(outline_data), '\n[output]\n'],
                    config=types.GenerateContentConfig(
                        system_instruction="Please provide output in json format.",
                        response_mime_type="application/json",
                        temperature=0,
                    )
                )
                output = ""
                content = response.candidates[0].content if response.candidates and response.candidates[0] else None
                if content and content.parts:
                    output = "".join([
                        part.text for part in content.parts 
                        if hasattr(part, 'text') and part.text
                    ])
                # output = response.text
                self.outline = json.loads(
                    str(output[output.index('{'):len(output)- output[::-1].index('}')]).strip(),
                    strict=False)
                break
            except Exception as e:
                if output:
                    print(output)
                    print('Outline generation failed due to: ', e)
                    retry_cnt+=1
                    continue

        self.outline['url_list'] = self.__url_list
        self.outline['region'] = region
        self.outline['industry'] = uiInd
        self.outline['audience'] = audience
        self.outline['product'] = list(map(lambda x: x.replace(' and ', ' & '), products))
        self.outline['solution'] = list(map(lambda x: x.replace(' and ', ' & '), solutions))
        self.outline['er_number'] = self.item.er_number
        self.outline['customer_name'] = (listed_company_name if (company_data and listed_company_name) else customer_name)
        self.outline['business_context'] = business_context
        self.outline['salesPlay'] = self.item.salesPlay
        if retry_cnt > 1:
            if customer_name:
                self.outline['title'] += f'for {customer_name}'
            elif industry:
                self.outline['title'] += f'for {industry}'
            else:
                self.outline['title'] += 'Solutions'
        
        print('outline generation output:\n', self.outline)
        return self.outline
