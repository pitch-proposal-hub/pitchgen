"""This module defines the `outline_generator` class used to generate a structured

outline based on provided business context and configuration settings.
It leverages Google Cloud's Vertex AI for generative content and Discovery
Engine
for web search.
"""

import concurrent.futures
from datetime import datetime
import json
import math
import os
from fuzzywuzzy import fuzz, process
from google import genai
from google.genai import types
from google.cloud import discoveryengine_v1 as discoveryengine
from google.cloud import secretmanager
import numpy as np
from pitchgen_utils.gcs_util import read_gcs_file
from agents.workflows.base_workflow import BaseWorkflow


class slide_search(BaseWorkflow):
  """A class to search single reusable slides based on user's query.

  This class uses Google Cloud's Gemini for entity extraction and Discovery
  Engine for structured
  datastore search to gather contextually relevant single reusable slides.
  """

  def __init__(self, search_query, is_strict, config, model):
    super().__init__('SidebarSlideSearchWorkflow', 'Searches reusable slides in sidebar.')
    self.config = config
    self.search_query = search_query
    self.query_emd = np.array([])
    self.is_strict = is_strict
    self.__project_name = config['default']['project_name']
    self.__location = 'global'
    self.__gemini_model = model

    self.datastore_client = discoveryengine.SearchServiceClient()
    self.sec_client = secretmanager.SecretManagerServiceClient()

    self.client = genai.Client(
        vertexai=True, project=self.__project_name, location=self.__location
    )
    self.embedding_model_name = os.getenv('EMBEDDING_MODEL', 'text-embedding-005')
    self.search_bucket_name = self.config['bucket']['content']
    cust_data = read_gcs_file(
        f'gs://{self.search_bucket_name}/search_data/customer_names/cust_names.json',
        project_id=self.__project_name,
    )
    self.cust_names = json.loads(cust_data)['cust_names']

    config_file_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'config/datastore.json',
    )
    with open(config_file_path, 'r') as f:
      mappings = json.loads(f.read())
    self.nameToCode = mappings['datastore_map']

    self.generation_config = {
        'temperature': 0.0,
        'response_mime_type': 'application/json',
    }
    self.search_entities = {
        'organization_names': [],
        'customer': [],
        'industry': [],
        'solution': [],
        'product': [],
        'region': [],
        'datastore': [],
    }

  def get_embeddings_list(self, queries):
    """function to get text embedding of list of strings"""
    response = self.client.models.embed_content(
        model=self.embedding_model_name,
        contents=queries,
    )
    return [np.array(e.values) for e in response.embeddings]

  def get_similarity_score(self, emd1, emd2):
    """function to get cosine similarity score between 2 embeddings"""
    score = np.dot(emd1, emd2) / (np.linalg.norm(emd1) * np.linalg.norm(emd2))
    return score

  def fetch_search_entities(self):
    """Fetches all the entities like industry, solution, etc., from the search query.

    Updates 'search_entities' attribute with key-value pairs of all the entities
    found.
    """
    model_entities = dict()
    entities_prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'prompt_templates/searchEntities.txt',
    )
    with open(entities_prompt_path, 'r') as f:
      entities_prompt = f.read()
    retry_cnt = 0
    output = ''
    while retry_cnt < 2:
      try:
        if retry_cnt > 0:
          print('retrying...')
        # response = self.genModel.generate_content(
        #     [entities_prompt, self.search_query, '</input>\n<output>\n'],
        #     generation_config=self.generation_config)
        client = genai.Client(
            vertexai=True, project=self.__project_name, location='global'
        )

        response = client.models.generate_content(
            model=self.__gemini_model,
            contents=[
                entities_prompt,
                self.search_query,
                '</input>\n<output>\n',
            ],
            config=types.GenerateContentConfig(
                system_instruction='Please provide output in json format.',
                response_mime_type='application/json',
                temperature=0,
            ),
        )
        output = ''
        if response.candidates and response.candidates[0].content.parts:
          output = ''.join([
              part.text
              for part in response.candidates[0].content.parts
              if hasattr(part, 'text') and part.text
          ])
        # output = response.text
        model_entities = json.loads(
            output[output.index('{') : len(output) - output[::-1].index('}')],
            strict=False,
        )
        break
      except Exception as e:
        if output:
          print(output)
        print('Entity extraction failed due to: ', e)
        retry_cnt += 1
        continue

    print('model output:\n', model_entities)
    commkeys = set(model_entities.keys()).intersection(
        set(self.search_entities.keys())
    )

    for key in commkeys:
      self.search_entities[key] = model_entities[key]

    industry = []
    subInd = []

    for val in self.search_entities['industry']:
      temp = val.lower().split(' in ')
      if len(temp) > 1:
        subInd.append(temp[0].replace(' and ', ' & '))
        industry.append(temp[1].replace(' and ', ' & '))
      else:
        industry.append(temp[0].replace(' and ', ' & '))
    # print("1",subInd)
    # print("1",industry)

    ind_mapping_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'config/ind_mapping.json',
    )
    with open(ind_mapping_path, 'r') as f:
      mappings = json.loads(f.read())
    oTnMapInd = mappings['oldToNewInd']
    oTnMapSubInd = mappings['oldToNewSubInd']

    for i in range(len(industry)):
      if industry[i] == 'insurance':
        industry.append('financial services')
        subInd.append('insurance')
      elif industry[i] in oTnMapInd.keys():
        industry.extend(oTnMapInd[industry[i]])

    # print("2",subInd)
    # print("2",industry)
    remInd = []
    for i in range(len(subInd)):
      if subInd[i] == 'aerospace':
        industry.append('manufacturing, industrial & transportation')
        subInd.append('air')
      elif subInd[i] in oTnMapSubInd.keys():
        subInd.extend(oTnMapSubInd[subInd[i]])

    # print("3",subInd)
    # print("3",industry)
    self.search_entities['industry'] = list(set(industry))
    self.search_entities['sub-industry'] = list(set(subInd))

    customers = list(
        map(lambda x: x.lower(), self.search_entities['organization_names'])
    )
    final_cust = []
    for val in customers:
      fuzz_res = process.extract(
          val, self.cust_names, scorer=fuzz.partial_ratio
      )
      for res in fuzz_res:
        if res[1] > 80:
          final_cust.append(res[0])
        else:
          final_cust.append(val)
    self.search_entities['customer'] = list(set(final_cust))

    regions = list(map(lambda x: x.lower(), self.search_entities['region']))
    self.search_entities['region'] = list(set(regions))

    solutions = list(map(lambda x: x.lower(), self.search_entities['solution']))
    self.search_entities['solution'] = list(set(solutions))

    products = list(map(lambda x: x.lower(), self.search_entities['product']))
    self.search_entities['product'] = list(set(products))

    datastores = list(
        map(lambda x: x.lower(), self.search_entities['datastore'])
    )
    self.search_entities['datastore'] = list(set(datastores))

    print('search entities:\n', self.search_entities)

  def get_search_filters(self):
    """Generates a list of search filters.

    returns:
        searchFilters (list): list of search filter strings.
    """
    filterStr = dict()

    for key in self.search_entities.keys():
      if self.search_entities[key] and (
          key not in ['organization_names', 'datastore']
      ):
        filterStr[key] = f"""{key}: ANY("""
        for val in self.search_entities[key]:
          if key == 'customer':
            variations = sorted(list({val, val.lower(), val.upper(), val.title(), val.capitalize()}))
            for var in variations:
              filterStr[key] += f""""{var}", """
          else:
            filterStr[key] += f""""{val}", """   
        filterStr[key] = filterStr[key][:-2]
        filterStr[key] += """)"""

    searchFilters1 = []
    for val in ['customer', 'sub-industry', 'industry']:
      if val in filterStr.keys():
        searchFilters1.append(filterStr[val])

    searchFilters2 = [
        (
            """ AND """.join(
                [filterStr[val] for val in ['product', 'solution', 'region']]
            )
        )
        if not set(['product', 'solution', 'region']).difference(
            set(filterStr.keys())
        )
        else '',
        f"""{filterStr['product']} AND {filterStr['solution']}"""
        if not set(['product', 'solution']).difference(set(filterStr.keys()))
        else '',
        filterStr['product'] if 'product' in filterStr.keys() else '',
        filterStr['solution'] if 'solution' in filterStr.keys() else '',
        filterStr['region'] if 'region' in filterStr.keys() else '',
    ]
    searchFilters2 = [val for val in searchFilters2 if val]

    finalFilters = []
    for val in searchFilters1:
      for ent in searchFilters2:
        finalFilters.append(f"""{val} AND {ent}""")

    finalFilters += searchFilters1 + searchFilters2

    # for val in finalFilters:
    #     val = '(' + val + ')'

    return finalFilters[:1] if self.is_strict else finalFilters

  def get_datastoreID(self, datastoreName):
    secret_name = self.config['reusable'][datastoreName]
    print(f"[DEBUG] get_datastoreID: project={self.__project_name}, datastoreName={datastoreName}, secret_name={secret_name}")
    try:
      sec_parent = self.sec_client.secret_path(
          project=self.__project_name,
          secret=secret_name,
      )
      print(f"[DEBUG] get_datastoreID: sec_parent={sec_parent}")
      response = self.sec_client.access_secret_version(
          request={'name': f'{sec_parent}/versions/latest'}
      )
      val = response.payload.data.decode('UTF-8')
      print(f"[DEBUG] get_datastoreID: retrieved value={val}")
      return val
    except Exception as e:
      print(
          f'[DEBUG] Could not access secret for {datastoreName} (secret: {secret_name}), falling back to'
          f' default: {e}'
      )
      return secret_name

  def search_datastore(self, searchFilter, datastoreID, result_count=20):
    """search datastore.

    args:
        searchFilter (str): search filter.
        datastoreID (str): id of the datastore to be searched.
        result_count (int): number of results.

    returns:
        data (list): A list of search results.
    """
    request = discoveryengine.SearchRequest(
        serving_config=self.datastore_client.serving_config_path(
            project=self.__project_name,
            location=self.__location,
            data_store=datastoreID,
            serving_config='default_config',
        ),
        query=self.search_query,
        filter=searchFilter,
        page_size=result_count,
    )
    response = self.datastore_client.search(request)
    results = response._response.results

    data = []
    for res in results:
      temp = {}
      for key in res.document.struct_data.keys():
        temp[key] = res.document.struct_data.get(key)
      data.append(temp)

    return data

  def get_datastore_results(self, datastore, query_filter='', num_results=20):
    datastore_id = self.get_datastoreID(datastore)
    res_slides = self.search_datastore(
        searchFilter=query_filter,
        datastoreID=datastore_id,
        result_count=num_results,
    )

    flag = 1
    if (datastore in ['pitch_sin', 'golden_sin']) and (not query_filter):
      flag = 0

    op_results = []
    for res in res_slides:
      if not flag:
        score = self.get_similarity_score(
            np.array(res['desc_embedding']), self.query_emd
        )
        if score >= 0.7:
          flag = 1
      if flag:
        all_tags = set(res['sub-industry'])
        all_tags.update(res['industry'])
        all_tags.update(res['solution'])
        all_tags.update(res['product'])
        all_tags.update(res['region'])
        all_tags.update(([] + [res['customer']]))

        tags = {val for val in all_tags if val not in ['', 'other']}

        op_results.append({
            'date': res['date'],
            'name': res['name'] if 'name' in res.keys() else res['customer'],
            'emd': (
                np.array(res['desc_embedding'])
                if 'desc_embedding' in res.keys()
                else self.get_embeddings_list([res['desc']])[0]
            ),
            'deckId': res['deckId'],
            'slideId': res['slideIds'][0],
            'slideURL': (
                f"https://docs.google.com/presentation/d/{res['deckId']}"
                + f"/edit?#slide=id.{res['slideIds'][0]}"
            ),
            'tags': list(tags),
        })

    return op_results

  def execute(self):
    self.fetch_search_entities()
    self.query_emd = self.get_embeddings_list([self.search_query])[0]
    query_ds = set(
        [self.nameToCode[ds] for ds in self.search_entities['datastore']]
    )
    if 'golden_sin' in query_ds:
      query_ds.add('silver_sin')
    if not query_ds:
      query_ds = {'golden_sin', 'silver_sin'}

    slides_ui = []
    generic_search = 1
    search_filters = self.get_search_filters()
    if search_filters:
      generic_search = 0
    print(search_filters)

    only_customers = (
        len(self.search_entities['customer']) > 0
        and len(
            self.search_entities['industry']
            + self.search_entities['solution']
            + self.search_entities['product']
            + self.search_entities['region']
        )
        == 0
    )

    if only_customers:
      query_ds.update({'cust_ref'})

    # dup_check = query_ds.difference({'cust_ref', 'cjms'})

    i = 0
    unq_deck_cnt = dict()
    emd_list = []
    max_deck_limit = 20 if 'cust_ref' in query_ds else 2
    while len(slides_ui) < 20 and i <= len(search_filters):
      temp = []
      if i < len(search_filters):
        with concurrent.futures.ThreadPoolExecutor() as executor:
          futures = [
              executor.submit(self.get_datastore_results, ds, search_filters[i])
              for ds in query_ds
          ]
      elif generic_search:
        with concurrent.futures.ThreadPoolExecutor() as executor:
          futures = [
              executor.submit(self.get_datastore_results, ds) for ds in query_ds
          ]
      else:
        break

      ds_search_res = []
      for future in futures:
        try:
          result = future.result()
          ds_search_res.append(result)
        except Exception as e:
          print(e)
          continue

      j = int(math.ceil(((20 - len(slides_ui)) / len(query_ds))))
      itr = 0
      while (len(slides_ui) + len(temp)) < 20:
        prev_len = len(temp)
        for res in ds_search_res:
          for ent in res[j * itr : j * (itr + 1)]:
            if not only_customers:  # and dup_check:
              dup_scores = [
                  self.get_similarity_score(ent['emd'], val) >= 0.85
                  for val in emd_list
              ]
            if only_customers or (not any(dup_scores)):  # or (not dup_check):
              emd_list.append(ent['emd'])
              del ent['emd']
              if ent['deckId'] not in unq_deck_cnt.keys():
                unq_deck_cnt[ent['deckId']] = 1
                temp.append(ent)
              elif (not only_customers) and (unq_deck_cnt[ent['deckId']] < max_deck_limit):                
                # and dup_check
                unq_deck_cnt[ent['deckId']] += 1
                temp.append(ent)

        if (len(temp) - prev_len) == 0:
          break
        itr += 1

      for val in temp:
        date_val = val.get('date')
        if date_val:
          if isinstance(date_val, (int, float)):
            val['date'] = datetime.fromtimestamp(int(date_val) / 1000).strftime('%Y-%m-%d')
          elif isinstance(date_val, str):
            if date_val.isnumeric():
              val['date'] = datetime.fromtimestamp(int(date_val) / 1000).strftime('%Y-%m-%d')
            elif " " in date_val:
              val['date'] = date_val.split(" ")[0]

      slides_ui.extend(sorted(temp, key=lambda x: x['date'], reverse=True))
      i += 1

    return slides_ui
