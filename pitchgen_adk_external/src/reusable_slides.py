"""Module for generating reusable architectural slides.

This module provides a class, ArchitecturalSlides, for generating
architectural slides based on a provided solution,
industry, and agenda structure. It integrates with Google Cloud
services such as Discovery Engine and Vertex AI's
TextEmbeddingModel to search for relevant content and retrieve slides.
"""

from datetime import datetime
from itertools import chain, combinations
import json
import time
from google.cloud import discoveryengine_v1 as discoveryengine
from google.cloud import secretmanager
import numpy as np
from src.configuration import configuration
from google import genai


class Architectural_slides:
  """class for generating architectural slides."""

  def __init__(self, item, agenda_struct):
    """initialize with inputs & configurations."""
    self.config = configuration()

    self.__project_id = self.config['default']['PROJECT_NAME']
    self.__location = self.config.get('default', 'region', fallback='global')

    from google.api_core.client_options import ClientOptions
    endpoint = f"{self.__location}-discoveryengine.googleapis.com" if self.__location and self.__location != "global" else "global-discoveryengine.googleapis.com"
    client_options = ClientOptions(api_endpoint=endpoint)
    self.__slides_client = discoveryengine.SearchServiceClient(client_options=client_options)
    self.sec_client = secretmanager.SecretManagerServiceClient()
    
    self.genai_client = genai.Client(
        vertexai=True,
        project=self.__project_id,
        location=self.__location,
    )

    self.item = item
    self.err_cnt = 1
    self.agenda_struct = agenda_struct

    # --- Fetch Datastore IDs ONCE ---
    self.datastore_ids = {}
    ds_keys = [
        'cust_ref',
        'sales_play_grp',
        'sales_play_sin',
        'cloudhub_golden_grp',
        'cloudhub_golden_sin',
        'cloudhub_silver_grp',
        'cloudhub_silver_sin',
        'pitch_grp',
        'pitch_sin',
    ]
    for key in ds_keys:
      try:
        sec_parent = self.sec_client.secret_path(
            project=self.__project_id, secret=self.config['reusable'][key]
        )
        sec_resp = self.sec_client.access_secret_version(
            request={'name': f'{sec_parent}/versions/latest'}
        )
        self.datastore_ids[key] = sec_resp.payload.data.decode('UTF-8')
      except Exception as e:
        print(
            f'Warning: Could not fetch secret for {key}: {e}, falling back to'
            ' datastore name.'
        )
        self.datastore_ids[key] = self.config['reusable'][key]

    # --- Industry Taxonomy Mapping ---
    with open('config/ind_mapping.json', 'r') as f:
      mappings = json.loads(f.read())
    indMap = mappings['indABB']
    self.subIndustry = ''

    if '-' in item.industry and ('public' not in item.industry.lower()):
      ind_parts = list(map(lambda x: x.strip(), item.industry.split(' - ')))
      self.industry = indMap[ind_parts[0]].lower()
      if 'public' in self.industry:
        self.industry = 'public sector - non us'
      self.subIndustry = ind_parts[1].lower()
    else:
      self.industry = item.industry.lower()

    oTnMapInd = mappings['oldToNewInd']
    oTnMapSubInd = mappings['oldToNewSubInd']
    if self.industry == 'insurance':
      self.industry = ['financial services']
      self.subIndustry = ['insurance']
    elif self.subIndustry == 'aerospace':
      self.industry = ['manufacturing, industrial & transportation']
      self.subIndustry = ['air']
    else:
      if self.industry in oTnMapInd.keys():
        self.industry = oTnMapInd[self.industry]
      if self.subIndustry in oTnMapSubInd.keys():
        self.subIndustry = oTnMapSubInd[self.subIndustry]
      if isinstance(self.industry, str):
        self.industry = [] + [self.industry]
      if isinstance(self.subIndustry, str):
        self.subIndustry = [] + [self.subIndustry]

  def get_embeddings_list(self, queries):
    """function to get text embedding of list of strings"""
    import os
    model_id = os.getenv('EMBEDDING_MODEL', 'text-embedding-005')
    response = self.genai_client.models.embed_content(
        model=model_id,
        contents=queries,
    )
    query_emds = [np.array(emb.values) for emb in response.embeddings]
    return query_emds

  def get_similarity_score(self, emd1, emd2):
    """function to get cosine similarity score between 2 embeddings"""
    score = np.dot(emd1, emd2) / (np.linalg.norm(emd1) * np.linalg.norm(emd2))
    return score

  def get_cust_ref_emds(self):
    cust_titles = [
        'customer references',
        'customer success stories',
        'success stories',
        'case studies',
        'success stories, case studies',
    ]
    cust_emds = self.get_embeddings_list(cust_titles)
    return cust_emds

  def filtered_outline(self):
    """filters 'Customer references' related outline items

    returns:
        list of items (list):
        first entry: customer references related outline items (list).
        second entry: filtered outline items (list).
        third entry: item next to the latest customer references item (str).
    """
    cust_emds = self.get_cust_ref_emds()
    outline = self.item.outline
    next_item = ''
    cust_out = []
    max_ind = 0
    for i in range(len(outline)):
      query_emd = self.get_embeddings_list([outline[i]])[0]
      scores = [
          self.get_similarity_score(query_emd, cust_emd)
          for cust_emd in cust_emds
      ]
      if any([score >= 0.7 for score in scores]):
        if i > max_ind:
          max_ind = i
        cust_out.append(outline[i])

    filtered_out = [val for val in outline if val not in cust_out]
    if max_ind < len(outline) - 1:
      next_item = outline[max_ind + 1]

    return [cust_out, filtered_out, next_item]

  def get_reusable_slides(self):
    """retrieve reusable slides handling Sales Plays limits and optimized datastore constraints."""
    slides = {}
    non_cust_keys = []

    try:
      for key in self.agenda_struct.keys():
        # --- Read Limit from Agenda (Default to 4 if not specified) ---
        try:
          reusable_limit = int(str(self.agenda_struct[key].get('reusable', 4)))
        except ValueError:
          reusable_limit = 4

        title = self.agenda_struct[key]['title']
        parts = self.agenda_struct[key]['parts']
        query = title + '. ' + '. '.join(parts)
        query = query.replace(self.item.customer_name, '')

        slides[key] = {}
        slides[key]['title'] = title
        slides[key]['suggestions'] = []

        if reusable_limit <= 0:
          continue

        if 'cust_ref' in self.agenda_struct[key].keys():
          # ==========================================
          # CUSTOMER REFERENCES
          # ==========================================
          store_type_cust = 2
          searchFilter_cust = []
          solutions_cust = ''
          if self.item.solution:
            solutions_cust += (
                """(solution: ANY("""
                + ', '.join(
                    [f'''"{sol.lower()}"''' for sol in self.item.solution]
                )
                + """))"""
            )
            searchFilter_cust.append(solutions_cust)

          indFil_cust = ''
          if self.industry:
            indFil_cust += (
                """(industry: ANY("""
                + ', '.join([f'''"{ind}"''' for ind in self.industry])
                + """))"""
            )
            searchFilter_cust.append(indFil_cust)

          if store_type_cust and self.item.region:
            searchFilter_cust.append(
                f"""(region: ANY("{self.item.region.lower()}"))"""
            )

          filter_comb_cust = list(
              chain.from_iterable(
                  combinations(searchFilter_cust, r)
                  for r in range(len(searchFilter_cust) + 1)
              )
          )
          filter_comb_cust = list(
              map(list, sorted(filter_comb_cust, key=len, reverse=True))
          )

          indInd_cust = [val for val in filter_comb_cust if indFil_cust in val]
          subInd_cust = []
          if self.subIndustry:
            temp_cust = (
                """(sub-industry: ANY("""
                + ', '.join([f'''"{sub}"''' for sub in self.subIndustry])
                + """))"""
            )
            subInd_cust = [
                list(map(lambda x: x.replace(indFil_cust, temp_cust), val))
                for val in indInd_cust
            ]

          filters_cust = subInd_cust + indInd_cust
          filters_cust.extend(
              [val for val in filter_comb_cust if val not in filters_cust]
          )

          final_filter_comb_cust = [
              val
              for val in filters_cust
              if val
              and val != [f"""(region: ANY("{self.item.region.lower()}"))"""]
          ]
          searchFilters_cust_list = [
              """ AND """.join(val) for val in final_filter_comb_cust
          ]

          cust_datastore_id = self.datastore_ids.get('cust_ref')
          i, cust_slides = 0, []

          while (
              len(cust_slides) < 10
              and i < len(searchFilters_cust_list)
              and cust_datastore_id
          ):
            req_cust = discoveryengine.SearchRequest(
                serving_config=self.__slides_client.serving_config_path(
                    project=self.__project_id,
                    location=self.__location,
                    data_store=cust_datastore_id,
                    serving_config='default_config',
                ),
                query=query,
                filter=searchFilters_cust_list[i],
                page_size=10,
            )
            resp_cust = self.__slides_client.search(req_cust)
            for raw_doc in resp_cust._response.results:
              struct_dict = {
                  k: raw_doc.document.struct_data.get(k)
                  for k in raw_doc.document.struct_data.keys()
              }
              cust_slides.append(struct_dict)
            i += 1

          for slide_data in cust_slides:
            score = 0
            if 'region' in slide_data.keys() and (
                self.item.region.lower() in slide_data['region']
            ):
              score += 1
            if set(self.industry).intersection(set(slide_data['industry'])):
              score += 3
            if 'sub-industry' in slide_data.keys() and (
                set(self.subIndustry).intersection(
                    set(slide_data['sub-industry'])
                )
            ):
              score += 5
            score += (
                len(
                    set(slide_data['product']).intersection(
                        set(list(map(lambda x: x.lower(), self.item.product)))
                    )
                )
            ) * 0.2
            score += (
                len(
                    set(slide_data['solution']).intersection(
                        set(list(map(lambda x: x.lower(), self.item.solution)))
                    )
                )
            ) * 0.4
            slide_data['tag_score'] = score

          cust_slides.sort(key=lambda x: x['tag_score'], reverse=True)

          refined_res = [
              {
                  'date': slide.get('date', ''),
                  'deckId': slide.get('deckId', ''),
                  'slideId': slide.get('slideIds', [''])[0],
                  'tag_score': slide.get('tag_score', 0),
              }
              for slide in cust_slides
          ]

          cust_sin = []
          for val in refined_res:
            if val not in cust_sin:
              cust_sin.append(val)
              if len(cust_sin) == reusable_limit:
                break

          slides[key]['suggestions'] = [
              {
                  'date': val['date'],
                  'values': [
                      f"https://docs.google.com/presentation/d/{val['deckId']}/edit?#slide=id.{val['slideId']}"
                  ],
                  'tag_score': val['tag_score'],
              }
              for val in cust_sin
          ]

        else:
          non_cust_keys.append(key)
          query_emd = self.get_embeddings_list([query])[0]

          dsresults = {}
          for dtkey in [
              'sales_play_grp',
              'sales_play_sin',
              'cloudhub_golden_grp',
              'cloudhub_golden_sin',
              'cloudhub_silver_grp',
              'cloudhub_silver_sin',
              'pitch_grp',
              'pitch_sin',
          ]:
            dsresults[dtkey] = {
                'id': self.datastore_ids.get(dtkey.lower(), ''),
                'th_score': (
                    0.7
                    if ('golden' in dtkey or 'sales_play' in dtkey)
                    else (0.75 if 'silver' in dtkey else 0.75)
                ),
                'is_golden': 'golden' in dtkey or 'sales_play' in dtkey,
                'results': [],
            }

          # --- Retrieve the input dynamically from item.salesPlay ---
          sales_play_list = getattr(self.item, 'salesPlay', [])
          total_sales_play_slides_found = 0

          # ==========================================
          # PHASE 1: SALES PLAY DATASTORES
          # ==========================================
          if sales_play_list:
            sp_formatted = ', '.join([f'"{sp}"' for sp in sales_play_list])
            sp_filter_str = f'(sales_play_name: ANY({sp_formatted}))'

            for ds in ['sales_play_grp', 'sales_play_sin']:
              ds_id = dsresults[ds]['id']
              if not ds_id:
                continue

              req_sp = discoveryengine.SearchRequest(
                  serving_config=self.__slides_client.serving_config_path(
                      project=self.__project_id,
                      location=self.__location,
                      data_store=ds_id,
                      serving_config='default_config',
                  ),
                  query=query,
                  filter=sp_filter_str,
                  page_size=10,
              )

              resp_sp = self.__slides_client.search(req_sp)
              sp_dataslides = []

              for raw_doc in resp_sp._response.results:
                struct_dict = {
                    k: raw_doc.document.struct_data.get(k)
                    for k in raw_doc.document.struct_data.keys()
                }
                if 'desc_embedding' not in struct_dict:
                  continue

                emd1 = np.array(struct_dict['desc_embedding'])
                score = np.dot(emd1, query_emd) / (
                    np.linalg.norm(emd1) * np.linalg.norm(query_emd)
                )

                if score >= dsresults[ds]['th_score']:
                  struct_dict['values'] = [
                      f"https://docs.google.com/presentation/d/{struct_dict['deckId']}/edit?#slide=id.{val}"
                      for val in struct_dict.get('slideIds', [])
                  ]
                  struct_dict['sim_score'] = score
                  struct_dict['tag_score'] = 10
                  del struct_dict['desc_embedding']
                  sp_dataslides.append(struct_dict)

              dsresults[ds]['results'] = sorted(
                  sp_dataslides, key=lambda x: x['sim_score'], reverse=True
              )

            sp_urls = set()
            for ds in ['sales_play_grp', 'sales_play_sin']:
              for res in dsresults[ds]['results']:
                if res.get('values'):
                  sp_urls.add(res['values'][0])
            total_sales_play_slides_found = len(sp_urls)

          # ==========================================
          # PHASE 2: REGULAR DATASTORES
          # ==========================================
          if (
              not sales_play_list
              or total_sales_play_slides_found < reusable_limit
          ):
            regular_ds_keys = [
                'cloudhub_golden_grp',
                'cloudhub_golden_sin',
                'cloudhub_silver_grp',
                'cloudhub_silver_sin',
                'pitch_grp',
                'pitch_sin',
            ]

            for ds in regular_ds_keys:
              ds_id = dsresults[ds]['id']
              if not ds_id:
                continue

              th_score = dsresults[ds]['th_score']

              searchFilters_list = []
              inclusive_filters = []

              if self.industry:
                inds = [f'"{ind}"' for ind in self.industry] + [
                    '"industry agnostic"',
                    '"all"',
                    '"other"',
                ]
                inclusive_filters.append(f"(industry: ANY({', '.join(inds)}))")

              if self.item.region and th_score > 0.75:
                regs = [
                    f'"{self.item.region.lower()}"',
                    '"global"',
                    '"all"',
                    '"other"',
                ]
                inclusive_filters.append(f"(region: ANY({', '.join(regs)}))")

              if self.item.solution:
                sols = [f'"{s.lower()}"' for s in self.item.solution] + [
                    '"all"',
                    '"other"',
                ]
                inclusive_filters.append(f"(solution: ANY({', '.join(sols)}))")

              if inclusive_filters:
                searchFilters_list.append(' AND '.join(inclusive_filters))

              searchFilters_list.append('')

              i, dataslides = 0, []
              while not dataslides and i < len(searchFilters_list):
                req_dt = discoveryengine.SearchRequest(
                    serving_config=self.__slides_client.serving_config_path(
                        project=self.__project_id,
                        location=self.__location,
                        data_store=ds_id,
                        serving_config='default_config',
                    ),
                    query=query,
                    filter=searchFilters_list[i],
                    page_size=10,
                )
                resp_dt = self.__slides_client.search(req_dt)

                for raw_doc in resp_dt._response.results:
                  struct_dict = {
                      k: raw_doc.document.struct_data.get(k)
                      for k in raw_doc.document.struct_data.keys()
                  }
                  if 'desc_embedding' not in struct_dict:
                    continue

                  emd1 = np.array(struct_dict['desc_embedding'])
                  score = np.dot(emd1, query_emd) / (
                      np.linalg.norm(emd1) * np.linalg.norm(query_emd)
                  )

                  if score >= th_score:
                    struct_dict['values'] = [
                        f"https://docs.google.com/presentation/d/{struct_dict['deckId']}/edit?#slide=id.{val}"
                        for val in struct_dict.get('slideIds', [])
                    ]
                    struct_dict['sim_score'] = score

                    tag_score = 0
                    if 'region' in struct_dict and (
                        self.item.region.lower() in struct_dict['region']
                    ):
                      tag_score += 1
                    if 'industry' in struct_dict and set(
                        self.industry
                    ).intersection(set(struct_dict['industry'])):
                      tag_score += 3
                    if 'sub-industry' in struct_dict and (
                        set(self.subIndustry).intersection(
                            set(struct_dict['sub-industry'])
                        )
                    ):
                      tag_score += 5
                    if 'product' in struct_dict:
                      tag_score += (
                          len(
                              set(struct_dict['product']).intersection(
                                  set(
                                      list(
                                          map(
                                              lambda x: x.lower(),
                                              self.item.product,
                                          )
                                      )
                                  )
                              )
                          )
                      ) * 0.2
                    if 'solution' in struct_dict:
                      tag_score += (
                          len(
                              set(struct_dict['solution']).intersection(
                                  set(
                                      list(
                                          map(
                                              lambda x: x.lower(),
                                              self.item.solution,
                                          )
                                      )
                                  )
                              )
                          )
                      ) * 0.4
                    struct_dict['tag_score'] = tag_score

                    del struct_dict['desc_embedding']
                    dataslides.append(struct_dict)
                i += 1

              dsresults[ds]['results'] = sorted(
                  dataslides,
                  key=lambda x: x['sim_score'] + x['tag_score'],
                  reverse=True,
              )

          # ==========================================
          # EXCLUSIONS & DEDUPLICATION
          # ==========================================
          for ds_key in dsresults.keys():
            slide_score = {}
            for res_item in dsresults[ds_key]['results']:
              val_key = res_item['values'][0] if res_item.get('values') else ''
              if val_key and (
                  val_key not in slide_score
                  or slide_score[val_key] < res_item['sim_score']
              ):
                slide_score[val_key] = res_item['sim_score']

            final_temp = []
            for res_item in dsresults[ds_key]['results']:
              val_key = res_item['values'][0] if res_item.get('values') else ''
              if (
                  val_key
                  and res_item['sim_score'] >= slide_score[val_key]
                  and res_item not in final_temp
              ):
                final_temp.append(res_item)
            dsresults[ds_key]['results'] = final_temp

          # Single vs Group overlapping removal
          pairs = [
              ('sales_play_sin', 'sales_play_grp'),
              ('pitch_sin', 'pitch_grp'),
              ('cloudhub_golden_sin', 'cloudhub_golden_grp'),
              ('cloudhub_silver_sin', 'cloudhub_silver_grp'),
          ]
          for sin_ds, grp_ds in pairs:
            sin_results = dsresults[sin_ds]['results']
            grp_results = dsresults[grp_ds]['results']
            grp_urls = set()
            for grp_res in grp_results:
              for url in grp_res.get('values', []):
                grp_urls.add(url)

            dsresults[sin_ds]['results'] = [
                sin_res
                for sin_res in sin_results
                if not (
                    sin_res.get('values') and sin_res['values'][0] in grp_urls
                )
            ]

          # ==========================================
          # AGGREGATE RESULTS MATCHING ORIGINAL OUTPUT
          # ==========================================
          all_sugg = []
          for ds_name in dsresults.keys():
            for res in dsresults[ds_name]['results']:
              all_sugg.append({
                  'date': res.get('date', ''),
                  'name': res.get('name', ''),
                  'values': res.get('values', []),
                  'sim_score': res.get('sim_score', 0),
                  'tag_score': res.get('tag_score', 0),
                  'is_golden': dsresults[ds_name].get('is_golden', False),
              })

          all_sugg.sort(
              key=lambda x: x['sim_score']
              + x['tag_score']
              + (0.05 if x['is_golden'] else 0),
              reverse=True,
          )

          unique_sugg = []
          seen_urls = set()
          for sugg in all_sugg:
            url = sugg['values'][0] if sugg['values'] else ''
            if url and url not in seen_urls:
              seen_urls.add(url)
              unique_sugg.append(sugg)
              if len(unique_sugg) == reusable_limit:
                break

          slides[key]['suggestions'] = unique_sugg

    except Exception as e:
      print(f'Exception during slide generation: {e}')
      if self.err_cnt:
        self.err_cnt = 0
        print('Error occured. Trying to recover......', e)
        time.sleep(30)
        return self.get_reusable_slides()
      else:
        print("Error occured! can't fetch reusable slides.")

    # --- Exact Original Output Structure & Date Formatting loop ---
    for key in slides.keys():
      for val in slides[key]['suggestions']:
        try:
          if val.get('date'):
            if str(val['date']).replace('.', '', 1).isdigit():
              val['date'] = datetime.fromtimestamp(
                  int(float(val['date'])) / 1000
              ).strftime('%Y-%m-%d')
            elif ' ' in str(val['date']):
              val['date'] = str(val['date']).split(' ')[0]
        except Exception:
          pass

    return slides
