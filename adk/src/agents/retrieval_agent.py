from agents.base_agent import BaseAgent
from agents.workflows.semantic_scoring_workflow import SemanticScoringWorkflow
from agents.workflows.slide_search_workflow import SlideSearchWorkflow


class RetrievalAgent(BaseAgent):

  def __init__(self, config):
    super().__init__(
        'RetrievalAgent',
        'Responsible for finding reusable slides and sales play insights.',
    )
    self.config = config
    self.add_skill('search', SlideSearchWorkflow(config))
    self.add_skill('score', SemanticScoringWorkflow(config))

  def _filter_raw_results(self, raw_results, customer_name):
    filtered_results = []
    for r in raw_results:
      is_cust_ref = (
          'cust-ref' in str(r.get('_source_datastore', '')).lower()
          or r.get('_source_datastore_key', '') == 'cust_ref'
      )
      slide_customer = r.get('customer') or r.get('customer_name') or ''
      slide_customer_lower = str(slide_customer).lower().strip()
      is_other_customer = False
      if slide_customer_lower and slide_customer_lower not in ['', 'none', 'other', 'generic', 'n/a']:
        target_cust_lower = str(customer_name).lower().strip()
        if target_cust_lower:
          if target_cust_lower not in slide_customer_lower and slide_customer_lower not in target_cust_lower:
            is_other_customer = True
        else:
          is_other_customer = True
      if is_other_customer and not is_cust_ref:
        print(
            f"[{self.name}] Excluding slide '{r.get('name') or r.get('title')}'"
            f" from datastore '{r.get('_source_datastore_key')}' because it"
            f" belongs to another customer: '{slide_customer}' (Target:"
            f" '{customer_name}')"
        )
        continue
      filtered_results.append(r)
    return filtered_results

  def run(self, global_state):
    print(f'[{self.name}] Starting asset discovery...')
    agendas = global_state.agendas
    reusable_slides = {}
    context = global_state.context or {}
    customer_name = context.get('customer_name', '')
    global_seen_slide_keys = set()

    # Get all reusable datastores from config
    datastores = {}
    if 'reusable' in self.config:
      for key in self.config['reusable']:
        datastores[key] = self.config['reusable'][key]

    if not datastores:
      print(f'[{self.name}] Warning: No datastores found in config.')

    for key, agenda in agendas.items():
      title = agenda.get('title', '')
      parts = agenda.get('parts', [])
      query = f"{title}. {' '.join(parts)}"
      
      if customer_name:
        import re
        pattern = re.compile(re.escape(customer_name), re.IGNORECASE)
        query = pattern.sub("", query)
        query = re.sub(r'\s+', ' ', query).strip()

      is_customer_story_agenda = False
      customer_story_keywords = [
          "customer story",
          "customer stories",
          "proof point",
          "customer success",
          "success story",
          "success stories",
          "case study",
          "case studies",
          "reference",
          "references",
      ]
      for kw in customer_story_keywords:
        if kw in title.lower() or any(kw in part.lower() for part in parts):
          is_customer_story_agenda = True
          break

      # Partition datastores for this agenda
      tier1_ds = {}
      tier2_ds = {}
      for ds_key, ds_id in datastores.items():
        if ds_key == 'cust_ref':
          if is_customer_story_agenda:
            tier1_ds[ds_key] = ds_id
        elif 'silver' in ds_key or ds_key == 'pitch_grp':
          tier2_ds[ds_key] = ds_id
        else:
          tier1_ds[ds_key] = ds_id

      all_raw_results = []
      print(f"[{self.name}] Querying Tier 1 datastores for agenda: '{title}'...")
      for ds_key, ds_id in tier1_ds.items():
        from agents.workflows.slide_retriever_factory import SlideRetrieverFactory
        retriever = SlideRetrieverFactory.get_retriever(ds_key, ds_id, self.config)
        raw_results = retriever.search_slides(query, context)
        for r in raw_results:
          r['_source_datastore'] = ds_id
          r['_source_datastore_key'] = ds_key
        filtered_results = self._filter_raw_results(raw_results, customer_name)
        all_raw_results.extend(filtered_results)

      # Helper functions to extract deck ID and slide ID from a slide
      def get_deck_id(slide):
        for key_name in ['deckId', 'deck_id', 'deck_ID']:
          if key_name in slide and slide[key_name]:
            return slide[key_name]
        temp_url = slide.get('temp_url', '') or slide.get('tempUrl', '')
        if temp_url:
          m = re.search(r'/presentation/d/([a-zA-Z0-9-_]+)', temp_url)
          if m:
            return m.group(1)
        return None

      def get_slide_id(slide):
        for key_name in ['slideId', 'slide_id', 'slide_ID']:
          if key_name in slide and slide[key_name]:
            return slide[key_name]
        for key_name in ['slideIds', 'slide_ids', 'slide_IDs']:
          if key_name in slide and slide[key_name]:
            val = slide[key_name]
            if isinstance(val, list) and val:
              return val[0]
            elif isinstance(val, str) and val:
              return val
        temp_url = slide.get('temp_url', '') or slide.get('tempUrl', '')
        if temp_url:
          m = re.search(r'slide=id\.([a-zA-Z0-9-_]+)', temp_url)
          if m:
            return m.group(1)
        return None

      # 2. Score Tier 1
      scored_results = self.skills['score'].execute(query, all_raw_results)

      # Primary threshold = 0.6
      high_scored_anchors = [
          s for s in scored_results if s.get('sim_score', 0) >= 0.6
      ]

      tier2_scored = None
      if not high_scored_anchors:
        print(
            f"[{self.name}] No Tier 1 slides met primary threshold (>= 0.6). Falling"
            f" back to Tier 2 (Silver) for agenda: '{title}'"
        )
        tier2_raw_results = []
        for ds_key, ds_id in tier2_ds.items():
          from agents.workflows.slide_retriever_factory import SlideRetrieverFactory
          retriever = SlideRetrieverFactory.get_retriever(ds_key, ds_id, self.config)
          raw_results = retriever.search_slides(query, context)
          for r in raw_results:
            r['_source_datastore'] = ds_id
            r['_source_datastore_key'] = ds_key
          filtered_results = self._filter_raw_results(raw_results, customer_name)
          tier2_raw_results.extend(filtered_results)

        if tier2_raw_results:
          tier2_scored = self.skills['score'].execute(query, tier2_raw_results)
          high_scored_anchors = [
              s for s in tier2_scored if s.get('sim_score', 0) >= 0.6
          ]
          if high_scored_anchors:
            scored_results = tier2_scored
            all_raw_results = tier2_raw_results

      # Fallback to secondary threshold >= 0.5 if no primary matches found
      if not high_scored_anchors:
        print(
            f"[{self.name}] No slides met primary threshold (>= 0.6) in either Tier."
            f" Falling back to secondary threshold (>= 0.5) for agenda: '{title}'"
        )
        # Try Tier 1 first
        high_scored_anchors = [
            s for s in scored_results if s.get('sim_score', 0) >= 0.5
        ]
        
        # If Tier 1 has nothing >= 0.5, try Tier 2 (Silver)
        if not high_scored_anchors:
          # If we haven't searched/scored Tier 2 yet, do it now
          if tier2_scored is None:
            tier2_raw_results = []
            for ds_key, ds_id in tier2_ds.items():
              from agents.workflows.slide_retriever_factory import SlideRetrieverFactory
              retriever = SlideRetrieverFactory.get_retriever(ds_key, ds_id, self.config)
              raw_results = retriever.search_slides(query, context)
              for r in raw_results:
                r['_source_datastore'] = ds_id
                r['_source_datastore_key'] = ds_key
              filtered_results = self._filter_raw_results(raw_results, customer_name)
              tier2_raw_results.extend(filtered_results)
            if tier2_raw_results:
              tier2_scored = self.skills['score'].execute(query, tier2_raw_results)
          
          if tier2_scored:
            high_scored_anchors = [
                s for s in tier2_scored if s.get('sim_score', 0) >= 0.5
            ]
            if high_scored_anchors:
              scored_results = tier2_scored
              all_raw_results = tier2_raw_results

      high_scored_anchors = high_scored_anchors[:3]

      if not high_scored_anchors:
        print(
            f"[{self.name}] No slides met similarity standard (score >= 0.5) in"
            f" either Tier for agenda: '{title}'"
        )
        suggestions = []
      else:
        # Extract unique deck IDs from anchors
        deck_ids = set()
        for slide in high_scored_anchors:
          d_id = get_deck_id(slide)
          if d_id:
            deck_ids.add(d_id)

        print(
            f'[{self.name}] Found highly scored anchors from decks: {deck_ids}'
        )

        # Collect all sibling slides from all_raw_results that belong to these deck IDs
        cluster_slides = []
        seen_slide_keys = set()

        def get_slide_key(s):
          s_id = get_slide_id(s)
          if s_id:
            return s_id
          return s.get('temp_url', '') or s.get('original_title', '')

        # Add all highly scored anchors first
        for s in high_scored_anchors:
          key_id = get_slide_key(s)
          if key_id not in seen_slide_keys and key_id not in global_seen_slide_keys:
            cluster_slides.append(s)
            seen_slide_keys.add(key_id)
            global_seen_slide_keys.add(key_id)

        # Add sibling slides from the same decks in all_raw_results
        for s in all_raw_results:
          d_id = get_deck_id(s)
          if d_id in deck_ids:
            key_id = get_slide_key(s)
            if key_id not in seen_slide_keys and key_id not in global_seen_slide_keys:
              cluster_slides.append(s)
              seen_slide_keys.add(key_id)
              global_seen_slide_keys.add(key_id)

        # Fallback/fill to minimum 3 if needed
        if len(cluster_slides) < 3:
          for s in scored_results:
            key_id = get_slide_key(s)
            if key_id not in seen_slide_keys and key_id not in global_seen_slide_keys:
              cluster_slides.append(s)
              seen_slide_keys.add(key_id)
              global_seen_slide_keys.add(key_id)
              if len(cluster_slides) >= 3:
                break
        cluster_slides = cluster_slides[:5]
        formatted_suggestions = []
        for slide in cluster_slides:
          deck_id = get_deck_id(slide)
          slide_id = get_slide_id(slide)
          slide_url = f"https://docs.google.com/presentation/d/{deck_id}/edit?#slide=id.{slide_id}" if deck_id and slide_id else ""
          
          # Calculate tag score (simple overlap)
          tag_score = 0.0
          context = global_state.context
          if context:
            slide_tags = set()
            for field in ['industry', 'solution', 'product', 'region', 'customer', 'sub-industry', 'sub-solution']:
              val = slide.get(field)
              if val:
                if isinstance(val, list):
                  slide_tags.update([str(x).lower() for x in val])
                else:
                  slide_tags.add(str(val).lower())
            
            context_tags = set()
            for field in ['industry', 'solution', 'product', 'region', 'customer_name']:
              val = context.get(field)
              if val:
                if isinstance(val, list):
                  context_tags.update([str(x).lower() for x in val])
                else:
                  context_tags.add(str(val).lower())
            
            if context_tags:
              intersection = slide_tags.intersection(context_tags)
              tag_score = float(len(intersection))
              customer_name = context.get('customer_name', '').lower()
              slide_customer = str(slide.get('customer', '')).lower()
              if customer_name and slide_customer and (customer_name in slide_customer or slide_customer in customer_name):
                tag_score += 1.0

          original_title = slide.get('name') or slide.get('title') or slide.get('customer') or 'No Title'
          original_content = slide.get('desc') or slide.get('content') or 'No Content'

          formatted_sug = {
              'date': slide.get('date', ''),
              'name': original_title,
              'tag_score': tag_score,
              'values': [slide_url] if slide_url else [],
              'original_title': original_title,
              'original_content': original_content,
              '_source_datastore_key': slide.get('_source_datastore_key', '')
          }
          if 'sim_score' in slide:
            formatted_sug['sim_score'] = slide['sim_score']
          
          is_golden = 'golden' in slide.get('_source_datastore', '').lower()
          if is_golden:
            formatted_sug['is_golden'] = True
            
          formatted_suggestions.append(formatted_sug)
        # Sort suggestions by tag_score descending, then by sim_score descending to prioritize matching industries/products
        formatted_suggestions.sort(
            key=lambda x: (x.get('tag_score', 0.0), x.get('sim_score', 0.0)),
            reverse=True
        )
        suggestions = self._deduplicate_suggestions(formatted_suggestions)
        print(
            f'[{self.name}] Dynamic retrieval fetched {len(suggestions)} slides'
            f" (after deduplication) for agenda: '{title}'"
        )

      reusable_slides[key] = {'title': title, 'suggestions': suggestions}

    global_state.reusable_slides = reusable_slides
    print(f'[{self.name}] Asset discovery completed.')
    return global_state

  def _deduplicate_suggestions(self, suggestions, threshold=85):
    try:
      from fuzzywuzzy import fuzz
    except ImportError:
      print(f"[{self.name}] Warning: fuzzywuzzy not installed. Skipping deduplication.")
      return suggestions

    unique_suggestions = []
    for sug in suggestions:
      sug_text = f"{sug.get('original_title', '')} {sug.get('original_content', '')}".strip().lower()
      is_duplicate = False
      for u_sug in unique_suggestions:
        u_text = f"{u_sug.get('original_title', '')} {u_sug.get('original_content', '')}".strip().lower()
        score = fuzz.token_set_ratio(sug_text, u_text)
        if score >= threshold:
          is_duplicate = True
          print(
              f"[{self.name}] Discarding duplicate suggestion '{sug.get('original_title')}'"
              f" (Similarity score {score}% to '{u_sug.get('original_title')}')"
          )
          break
      if not is_duplicate:
        unique_suggestions.append(sug)
    return unique_suggestions
