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

try:
  from fuzzywuzzy import fuzz, process
except ImportError:
  fuzz = None
  process = None
from google import genai
from google.genai import types
from google.cloud import discoveryengine_v1 as discoveryengine
from google.cloud import secretmanager
from google.protobuf.json_format import MessageToDict
import numpy as np
from pitchgen_utils.gcs_util import read_gcs_file
from agents.workflows.base_workflow import BaseWorkflow


_CACHED_CUST_NAMES = None


class slide_search(BaseWorkflow):
  """A class to search single reusable slides based on user's query.

  This class uses Google Cloud's Gemini for entity extraction and Discovery
  Engine for structured
  datastore search to gather contextually relevant single reusable slides.
  """

  def __init__(self, search_query, is_strict, config, model, slide_job=''):
    super().__init__('SidebarSlideSearchWorkflow', 'Searches reusable slides in sidebar.')
    self.config = config
    self.search_query = search_query
    self.slide_job = str(slide_job).strip()
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
    try:
      self.search_bucket_name = self.config.get('bucket', 'content', fallback='pitchgen-content')
    except Exception:
      self.search_bucket_name = 'pitchgen-content'

    global _CACHED_CUST_NAMES
    if _CACHED_CUST_NAMES is not None:
      self.cust_names = _CACHED_CUST_NAMES
    else:
      self.cust_names = []
      _CACHED_CUST_NAMES = []
      try:
        from google.cloud import storage
        storage_client = storage.Client(project=self.__project_name)
        bucket = storage_client.bucket(self.search_bucket_name)
        blob = bucket.blob('search_data/customer_names/cust_names.json')
        cust_data = blob.download_as_text()
        _CACHED_CUST_NAMES = json.loads(cust_data).get('cust_names', [])
        self.cust_names = _CACHED_CUST_NAMES
      except Exception as e:
        print(f"[SidebarSlideSearchWorkflow] Could not load cust_names from GCS: {e}")

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
        'core_topics': [],
    }

  def get_embeddings_list(self, queries):
    """function to get text embedding of list of strings"""
    try:
      client = genai.Client(
          vertexai=True, project=self.__project_name, location='global'
      )
      response = client.models.embed_content(
          model=self.embedding_model_name,
          contents=queries,
      )
      return [np.array(e.values) for e in response.embeddings]
    except Exception:
      return [np.zeros(768) for _ in queries]

  def get_similarity_score(self, emd1, emd2):
    """function to get cosine similarity score between 2 embeddings"""
    norm1 = np.linalg.norm(emd1)
    norm2 = np.linalg.norm(emd2)
    if norm1 == 0 or norm2 == 0:
      return 0.0
    return float(np.dot(emd1, emd2) / (norm1 * norm2))

  def fetch_search_entities(self):
    """Fetches all the entities like industry, solution, core_topics, etc., from the search query."""
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
        model_entities = json.loads(
            output[output.index('{') : len(output) - output[::-1].index('}')],
            strict=False,
        )
        break
      except Exception as e:
        if output:
          print(output)
        print('Entity extraction failed due to: ', e)
        try:
          import vertexai
          from vertexai.generative_models import GenerativeModel
          vertexai.init(project=self.__project_name, location=self.__location)
          vmodel = GenerativeModel(self.__gemini_model)
          full_prompt = f"{entities_prompt}\n{self.search_query}\n</input>\n<output>\n"
          vres = vmodel.generate_content(full_prompt)
          vtext = vres.text if hasattr(vres, 'text') else str(vres)
          model_entities = json.loads(
              vtext[vtext.index('{') : len(vtext) - vtext[::-1].index('}')],
              strict=False,
          )
          break
        except Exception as e_v:
          print('Vertex AI GenerativeModel fallback also failed:', e_v)
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

    for val in self.search_entities.get('industry', []):
      temp = val.lower().split(' in ')
      if len(temp) > 1:
        subInd.append(temp[0].replace(' and ', ' & '))
        industry.append(temp[1].replace(' and ', ' & '))
      else:
        industry.append(temp[0].replace(' and ', ' & '))

    ind_mapping_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'config/ind_mapping.json',
    )
    with open(ind_mapping_path, 'r') as f:
      mappings = json.loads(f.read())
    oTnMapInd = mappings.get('oldToNewInd', {})
    oTnMapSubInd = mappings.get('oldToNewSubInd', {})

    for i in range(len(industry)):
      if industry[i] == 'insurance':
        industry.append('financial services')
        subInd.append('insurance')
      elif industry[i] in oTnMapInd.keys():
        industry.extend(oTnMapInd[industry[i]])

    for i in range(len(subInd)):
      if subInd[i] == 'aerospace':
        industry.append('manufacturing, industrial & transportation')
        subInd.append('air')
      elif subInd[i] in oTnMapSubInd.keys():
        subInd.extend(oTnMapSubInd[subInd[i]])

    self.search_entities['industry'] = list(set(industry))
    self.search_entities['sub-industry'] = list(set(subInd))

    customers = list(
        map(lambda x: x.lower(), self.search_entities.get('organization_names', []))
    )
    final_cust = []
    for val in customers:
      if process is not None and fuzz is not None and self.cust_names:
        fuzz_res = process.extract(
            val, self.cust_names, scorer=fuzz.partial_ratio
        )
        for res in fuzz_res:
          if res[1] > 80:
            final_cust.append(res[0])
          else:
            final_cust.append(val)
      else:
        final_cust.append(val)
    self.search_entities['customer'] = list(set(final_cust))

    regions = list(map(lambda x: x.lower(), self.search_entities.get('region', [])))
    self.search_entities['region'] = list(set(regions))

    solutions = list(map(lambda x: x.lower(), self.search_entities.get('solution', [])))
    self.search_entities['solution'] = list(set(solutions))

    products = list(map(lambda x: x.lower(), self.search_entities.get('product', [])))
    self.search_entities['product'] = list(set(products))

    datastores = list(
        map(lambda x: x.lower(), self.search_entities.get('datastore', []))
    )
    self.search_entities['datastore'] = list(set(datastores))

    core_topics = list(
        map(lambda x: str(x).strip(), self.search_entities.get('core_topics', []))
    )
    self.search_entities['core_topics'] = [t for t in core_topics if t]

    print('search entities:\n', self.search_entities)

  def get_datastore_filters(self, datastore):
    """Generates valid Discovery Engine filter expressions specific to the target datastore schema."""
    filters = []

    INDUSTRY_MAP = {
        'retail': 'Retail & Consumer',
        'retail & consumer': 'Retail & Consumer',
        'cpg': 'Consumer Packaged Goods',
        'consumer packaged goods': 'Consumer Packaged Goods',
        'fsi': 'Financial Services & Insurance',
        'financial services': 'Financial Services & Insurance',
        'financial services & insurance': 'Financial Services & Insurance',
        'games': 'Games',
        'gaming': 'Games',
        'healthcare': 'Healthcare',
        'hcls': 'Healthcare',
        'life sciences': 'Life Sciences',
        'logistics': 'Logistics',
        'manufacturing': 'Manufacturing',
        'media': 'Media & Entertainment',
        'media & entertainment': 'Media & Entertainment',
        'm&e': 'Media & Entertainment',
        'energy': 'Power & Energy',
        'power & energy': 'Power & Energy',
        'public sector': 'Public Sector & EDU',
        'public sector & edu': 'Public Sector & EDU',
        'education': 'Public Sector & EDU',
        'software': 'Software & Internet',
        'software & internet': 'Software & Internet',
        'tech': 'Software & Internet',
        'supply chain': 'Supply Chain Management',
        'supply chain management': 'Supply Chain Management',
        'sustainability': 'Sustainability',
        'telco': 'Telecommunications',
        'telecommunications': 'Telecommunications',
        'telecom': 'Telecommunications',
        'travel': 'Travel & Hospitality',
        'travel & hospitality': 'Travel & Hospitality',
        'automotive': 'Automotive',
        'auto': 'Automotive',
    }

    PRODUCT_MAP = {
        'gemini': 'Gemini Enterprise',
        'gemini enterprise': 'Gemini Enterprise',
        'workspace': 'Workspace',
        'google workspace': 'Workspace',
        'agent': 'Agent and Model Platform',
        'agent and model platform': 'Agent and Model Platform',
        'agents': 'Agent and Model Platform',
        'genai': 'Generative AI',
        'generative ai': 'Generative AI',
        'bigquery': 'BigQuery EPE',
        'looker': 'Cloud BI and Embed Analytics (Looker)',
        'alloydb': 'Modernize Databases (Heterogeneous - Spanner, AlloyDB, Bigtable)',
        'spanner': 'Modernize Databases (Heterogeneous - Spanner, AlloyDB, Bigtable)',
        'cloud sql': 'Move to Managed Databases (Homogeneous - Cloud SQL, AlloyDB, Firestore)',
        'gke': 'GKE/CloudRun',
        'cloud run': 'GKE/CloudRun',
        'networking': 'Networking',
        'security': 'Secure Innovation with Google Cloud',
        'mandiant': 'Achieve Resilience Together with Mandiant',
        'vmware': 'VMware Engine',
        'oracle': 'Oracle on Compute',
        'sap': 'SAP RISE',
    }

    if datastore in ['sales_play_reusables', 'sales_play']:
      ind_vals = set()
      for iv in self.search_entities.get('industry', []):
        norm = INDUSTRY_MAP.get(iv.lower().strip())
        if norm:
          ind_vals.add(norm)
        else:
          ind_vals.add(iv.title().strip())

      prod_vals = set()
      for pv in self.search_entities.get('product', []):
        norm = PRODUCT_MAP.get(pv.lower().strip())
        if norm:
          prod_vals.add(norm)
        else:
          prod_vals.add(pv.title().strip())

      ind_filter = f"industry: ANY({', '.join([f'\"{v}\"' for v in sorted(list(ind_vals))])})" if ind_vals else ""
      prod_filter = f"google_product: ANY({', '.join([f'\"{v}\"' for v in sorted(list(prod_vals))])})" if prod_vals else ""

      slide_job_filter = ""
      if self.slide_job and self.slide_job.lower() not in ['all', 'all slide types', 'select repository', '']:
        slide_job_filter = f'slide_job: ANY("{self.slide_job}")'

      if slide_job_filter:
        if ind_filter and prod_filter:
          filters.append(f"{slide_job_filter} AND {ind_filter} AND {prod_filter}")
        if ind_filter:
          filters.append(f"{slide_job_filter} AND {ind_filter}")
        if prod_filter:
          filters.append(f"{slide_job_filter} AND {prod_filter}")
        filters.append(slide_job_filter)
      else:
        if ind_filter and prod_filter:
          filters.append(f"{ind_filter} AND {prod_filter}")
        if ind_filter:
          filters.append(ind_filter)
        if prod_filter:
          filters.append(prod_filter)
        # Always allow unfiltered semantic search over sales_play_reusables as final fallback
        filters.append('')

    elif datastore in ['cust_ref', 'customer references']:
      ind_vals = set()
      for iv in self.search_entities.get('industry', []):
        norm = INDUSTRY_MAP.get(iv.lower().strip())
        if norm:
          ind_vals.add(norm)
        else:
          ind_vals.add(iv.title().strip())

      prod_vals = set()
      for pv in self.search_entities.get('product', []):
        norm = PRODUCT_MAP.get(pv.lower().strip())
        if norm:
          prod_vals.add(norm)
        else:
          prod_vals.add(pv.title().strip())

      ind_filter = (
          'industry:'
          f" ANY({', '.join([f'\"{v}\"' for v in sorted(list(ind_vals))])})"
          if ind_vals
          else ''
      )
      prod_filter = (
          'google_product:'
          f" ANY({', '.join([f'\"{v}\"' for v in sorted(list(prod_vals))])})"
          if prod_vals
          else ''
      )

      if ind_filter and prod_filter:
        filters.append(
            f'customer_references = "true" AND {ind_filter} AND {prod_filter}'
        )
      if ind_filter:
        filters.append(f'customer_references = "true" AND {ind_filter}')
        filters.append(f'slide_job: ANY("Proof_Points") AND {ind_filter}')
      if prod_filter:
        filters.append(f'customer_references = "true" AND {prod_filter}')
      filters.append('customer_references = "true"')
      filters.append('slide_job: ANY("Proof_Points")')

    deduped = []
    for f in filters:
      if f not in deduped:
        deduped.append(f)
    return deduped

  def get_datastoreID(self, datastoreName):
    if 'reusable' in self.config and datastoreName in self.config['reusable']:
      secret_name = self.config['reusable'][datastoreName]
    else:
      secret_name = datastoreName

    try:
      sec_parent = self.sec_client.secret_path(
          project=self.__project_name,
          secret=secret_name,
      )
      response = self.sec_client.access_secret_version(
          request={'name': f'{sec_parent}/versions/latest'}
      )
      val = response.payload.data.decode('UTF-8')
      return val
    except Exception:
      return secret_name

  def search_datastore(self, searchFilter, datastoreID, result_count=20):
    """search datastore."""
    try:
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
        try:
          doc_dict = MessageToDict(res.document._pb)
          temp = doc_dict.get('structData', {})
        except Exception:
          temp = {}
          for key in res.document.struct_data.keys():
            val = res.document.struct_data.get(key)
            if hasattr(val, '__iter__') and not isinstance(val, str):
              temp[key] = [str(x) for x in val]
            else:
              temp[key] = str(val)
        data.append(temp)

      return data
    except Exception as e:
      print(f"[SidebarSlideSearchWorkflow] Search error on DS {datastoreID} (filter='{searchFilter}'): {e}")
      return []

  def get_datastore_results(self, datastore, query_filter='', num_results=20):
    datastore_id = self.get_datastoreID(datastore)
    res_slides = self.search_datastore(
        searchFilter=query_filter,
        datastoreID=datastore_id,
        result_count=num_results,
    )

    op_results = []
    for res in res_slides:
      deck_id = res.get('deck_id') or res.get('deckId') or ''
      raw_slide_id = res.get('slide_id') or res.get('slideId') or res.get('slideIds') or ''
      if isinstance(raw_slide_id, list):
        slide_id = raw_slide_id[0] if raw_slide_id else ''
      else:
        slide_id = str(raw_slide_id)

      deck_title = res.get('deck_title') or res.get('deckTitle') or ''
      slide_title = res.get('slide_title') or res.get('slideTitle') or ''
      title = (
          slide_title
          or res.get('name')
          or deck_title
          or res.get('customer')
          or 'Reusable Slide'
      )
      summary = res.get('slide_summary') or res.get('desc') or res.get('content') or res.get('group_summary') or ''
      core_topics = res.get('core_topics', [])
      if isinstance(core_topics, str):
        core_topics = [core_topics]

      all_tags = set()
      for tag_key in ['sub_industry', 'sub-industry', 'industry', 'solution', 'product', 'google_product', 'sales_play', 'region', 'customer']:
        val = res.get(tag_key)
        if isinstance(val, list):
          all_tags.update([str(v) for v in val if v and str(v).lower() not in ['', 'other', 'none']])
        elif isinstance(val, str) and val and val.lower() not in ['', 'other', 'none']:
          all_tags.add(val)
      if core_topics:
        all_tags.update([str(t) for t in core_topics if t])

      tags = {val for val in all_tags if val not in ['', 'other']}

      if 'desc_embedding' in res and isinstance(res['desc_embedding'], list) and len(res['desc_embedding']) > 0:
        emd = np.array(res['desc_embedding'])
      else:
        emd = np.zeros(768)

      date_val = res.get('date') or res.get('ingestion_timestamp') or ''
      slide_url = res.get('slide_url') or res.get('slideURL') or (
          f"https://docs.google.com/presentation/d/{deck_id}/edit#slide=id.{slide_id}" if deck_id and slide_id else ""
      )

      op_results.append({
          'date': date_val,
          'name': title,
          'slide_title': slide_title,
          'deck_title': deck_title,
          'deckTitle': deck_title,
          'customer': res.get('customer') or '',
          'industry': res.get('industry') or '',
          'solution': (
              res.get('solution')
              or res.get('sales_play')
              or res.get('salesPlay')
              or ''
          ),
          'product': res.get('product') or res.get('google_product') or '',
          'slide_job': res.get('slide_job') or res.get('slideJob') or '',
          'emd': emd,
          'deckId': deck_id,
          'slideId': slide_id,
          'slideURL': slide_url,
          'tags': list(tags),
          'summary': summary,
          'core_topics': core_topics,
      })

    return op_results

  def execute(self):
    self.fetch_search_entities()
    try:
      self.query_emd = self.get_embeddings_list([self.search_query])[0]
    except Exception:
      self.query_emd = np.zeros(768)

    query_ds = set()
    for ds in self.search_entities.get('datastore', []):
      code = self.nameToCode.get(ds) or self.nameToCode.get(ds.lower())
      if code:
        query_ds.add(code)

    if not query_ds:
      if self.slide_job and self.slide_job.lower() not in ['all', 'all slide types', 'proof_points', 'proof points', 'customer references', '']:
        query_ds = {'sales_play_reusables'}
      elif self.slide_job and self.slide_job.lower() in ['proof_points', 'proof points', 'customer references']:
        query_ds = {'cust_ref'}
      else:
        query_ds = {'sales_play_reusables', 'cust_ref'}

    print(f"[SidebarSlideSearchWorkflow] Query: '{self.search_query}', SlideJob: '{self.slide_job}', Query DS: {query_ds}")

    only_customers = (
        len(self.search_entities.get('customer', [])) > 0
        and len(
            self.search_entities.get('industry', [])
            + self.search_entities.get('solution', [])
            + self.search_entities.get('product', [])
            + self.search_entities.get('region', [])
        )
        == 0
    )

    if only_customers:
      ordered_ds = ['cust_ref']
    else:
      ordered_ds = []
      if 'sales_play_reusables' in query_ds:
        ordered_ds.append('sales_play_reusables')
      if 'cust_ref' in query_ds:
        ordered_ds.append('cust_ref')
      for other in query_ds:
        if other not in ordered_ds:
          ordered_ds.append(other)

    seen_slide_keys = set()
    raw_collected_slides = []

    for ds in ordered_ds:
      if ds == 'cust_ref':
        try:
          from agents.workflows.customer_reference_retriever import NewLibraryCustomerReferenceRetriever

          customer_ref_library_retriever = NewLibraryCustomerReferenceRetriever(
              self.config, datastore_id='', ds_key='cust_ref'
          )
          ind_list = self.search_entities.get('industry', [])
          prod_list = self.search_entities.get(
              'product', []
          ) + self.search_entities.get('solution', [])
          cust_list = self.search_entities.get('customer', [])
          customer_ref_library_slides = customer_ref_library_retriever.search_slides(
              query=self.search_query,
              limit=25,
              industry=ind_list[0] if ind_list else '',
              products=prod_list,
              customer_name=cust_list[0] if cust_list else '',
          )
          for ent in customer_ref_library_slides:
            d_id = ent.get('deckId') or ent.get('deck_id')
            s_id = ent.get('slideId') or ent.get('slide_id')
            slide_key = f'{d_id}_{s_id}'
            if not d_id or not s_id or slide_key in seen_slide_keys:
              continue
            seen_slide_keys.add(slide_key)
            cleaned_ent = dict(ent)
            cleaned_ent['deckId'] = d_id
            cleaned_ent['slideId'] = s_id
            cleaned_ent['date'] = datetime.now().strftime('%Y-%m-%d')
            raw_collected_slides.append(cleaned_ent)
        except Exception as customer_ref_library_err:
          print(
              '[SidebarSlideSearchWorkflow] Customer Reference Library cust_ref error:'
              f' {customer_ref_library_err}'
          )
        continue

      ds_filters = self.get_datastore_filters(ds)
      for stage_filter in ds_filters:
        if len(raw_collected_slides) >= 100:
          break
        res_list = self.get_datastore_results(ds, stage_filter, num_results=50)
        for ent in res_list:
          slide_key = f"{ent.get('deckId')}_{ent.get('slideId')}"
          if not ent.get('deckId') or not ent.get('slideId') or slide_key in seen_slide_keys:
            continue

          seen_slide_keys.add(slide_key)

          date_val = ent.get('date')
          if date_val:
            if isinstance(date_val, (int, float)):
              ent['date'] = datetime.fromtimestamp(int(date_val) / 1000).strftime('%Y-%m-%d')
            elif isinstance(date_val, str):
              if date_val.isnumeric():
                ent['date'] = datetime.fromtimestamp(int(date_val) / 1000).strftime('%Y-%m-%d')
              elif " " in date_val:
                ent['date'] = date_val.split(" ")[0]
          else:
            ent['date'] = datetime.now().strftime('%Y-%m-%d')

          cleaned_ent = dict(ent)
          if 'emd' in cleaned_ent:
            del cleaned_ent['emd']

          raw_collected_slides.append(cleaned_ent)

    # Perform Near-Duplicate Deduplication (>=95% content similarity, keeping freshest version)
    deduped_slides = self._deduplicate_search_results(raw_collected_slides, similarity_threshold=95)
    return deduped_slides[:50]

  def _deduplicate_search_results(self, slides: list, similarity_threshold: int = 95) -> list:
    """Deduplicates search results with >=95% similarity, retaining the newest version."""
    try:
      from fuzzywuzzy import fuzz
    except ImportError:
      return slides

    unique_slides = []
    for s in slides:
      s_title = str(s.get('name', '')).strip().lower()
      s_summary = str(s.get('summary', '')).strip().lower()
      s_text = f"{s_title} {s_summary}".strip()
      s_date_str = str(s.get('date', ''))

      is_duplicate = False
      for idx, u in enumerate(unique_slides):
        u_title = str(u.get('name', '')).strip().lower()
        u_summary = str(u.get('summary', '')).strip().lower()
        u_text = f"{u_title} {u_summary}".strip()
        u_date_str = str(u.get('date', ''))

        # Calculate token similarity on body summary and full text
        summary_sim = fuzz.token_set_ratio(s_summary, u_summary) if (s_summary and u_summary) else 0
        full_sim = fuzz.token_set_ratio(s_text, u_text)
        title_sim = fuzz.token_set_ratio(s_title, u_title)

        if summary_sim >= similarity_threshold or (full_sim >= similarity_threshold and title_sim >= 90):
          is_duplicate = True
          # Keep the newer version if timestamps are comparable
          if s_date_str > u_date_str:
            unique_slides[idx] = s
          break

      if not is_duplicate:
        unique_slides.append(s)

    return unique_slides
