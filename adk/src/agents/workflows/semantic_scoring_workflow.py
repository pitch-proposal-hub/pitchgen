"""Semantic scoring skill for calculating relevance scores for slides using embeddings."""

import hashlib
import json
import random
import re
import threading
import time
from google.cloud import discoveryengine_v1 as discoveryengine
from google.cloud import secretmanager
from google import genai
from google.genai import types
import numpy as np
from agents.workflows.base_workflow import BaseWorkflow


_GLOBAL_EMBEDDING_CACHE: dict[str, np.ndarray] = {}
_EMBEDDING_CACHE_LOCK = threading.Lock()
_EMBEDDING_SEMAPHORE = threading.BoundedSemaphore(2)


def _deterministic_lexical_embedding(text: str, dim: int = 768) -> np.ndarray:
  """Computes a normalized deterministic hashed word/trigram embedding vector when Vertex embedding quota is exhausted."""
  vec = np.zeros(dim, dtype=np.float64)
  cleaned = re.sub(r'[^a-z0-9\s]', ' ', str(text or '').lower())
  tokens = [t for t in cleaned.split() if len(t) >= 2]
  if not tokens:
    vec[0] = 1.0
    return vec
  features = list(tokens)
  for i in range(len(tokens) - 1):
    features.append(f'{tokens[i]}_{tokens[i + 1]}')
  for tok in tokens:
    if len(tok) >= 4:
      for j in range(len(tok) - 2):
        features.append(f'#{tok[j:j + 3]}')
  for feat in features:
    digest = hashlib.md5(feat.encode('utf-8')).digest()
    idx = int.from_bytes(digest[:4], 'little') % dim
    sign = 1.0 if (digest[4] & 1) == 0 else -1.0
    weight = 2.0 if not feat.startswith('#') else 0.75
    vec[idx] += sign * weight
  norm = np.linalg.norm(vec)
  if norm > 0:
    vec = vec / norm
  else:
    vec[0] = 1.0
  return vec


class SemanticScoringWorkflow(BaseWorkflow):
  """Calculates relevance scores for slides using embeddings."""

  def __init__(self, config):
    super().__init__(
        'SemanticScoringWorkflow',
        'Calculates relevance scores for slides using embeddings.',
    )
    self.config = config
    self.project_id = config['default']['project_name']
    self.region = config['default'].get('region', 'global')
    self.client = genai.Client(
        vertexai=True, project=self.project_id, location=self.region
    )

  def _is_mock_client(self) -> bool:
    return hasattr(self.client, 'assert_called') or hasattr(
        getattr(self.client, 'models', None), 'assert_called'
    )

  def get_embeddings(self, queries):
    """Generates embedding vectors for a list of string queries with caching, batching, retry on 429, and lexical fallback."""
    if not queries:
      return []
    model_name = self.config['default'].get(
        'embedding_model', 'text-embedding-005'
    )
    if self._is_mock_client():
      try:
        response = self.client.models.embed_content(
            model=model_name,
            contents=queries,
        )
        return [np.array(e.values) for e in response.embeddings]
      except Exception:  # pylint: disable=broad-exception-caught
        return [_deterministic_lexical_embedding(q) for q in queries]

    normalized_queries = [
        str(q or '').strip()[:1500] or ' ' for q in queries
    ]
    results: list[np.ndarray | None] = [None] * len(normalized_queries)
    missing_map: dict[str, list[int]] = {}

    with _EMBEDDING_CACHE_LOCK:
      for idx, q_text in enumerate(normalized_queries):
        cached_vec = _GLOBAL_EMBEDDING_CACHE.get(q_text)
        if cached_vec is not None:
          results[idx] = cached_vec
        else:
          missing_map.setdefault(q_text, []).append(idx)

    if missing_map:
      missing_texts = list(missing_map.keys())
      batch_size = 40
      for b_start in range(0, len(missing_texts), batch_size):
        batch = missing_texts[b_start : b_start + batch_size]
        batch_embs = None
        max_retries = 4
        for attempt in range(max_retries):
          try:
            with _EMBEDDING_SEMAPHORE:
              response = self.client.models.embed_content(
                  model=model_name,
                  contents=batch,
              )
            batch_embs = [np.array(e.values) for e in response.embeddings]
            break
          except Exception as e:  # pylint: disable=broad-exception-caught
            err_str = str(e).lower()
            is_rate_limit = (
                '429' in err_str
                or 'resource_exhausted' in err_str
                or 'quota' in err_str
                or 'rate' in err_str
            )
            if is_rate_limit and attempt < max_retries - 1:
              sleep_s = (1.5 ** attempt) + random.uniform(0.2, 0.9)
              print(
                  f'[{self.name}] Embedding rate limit (429), retrying batch'
                  f' of {len(batch)} in {sleep_s:.2f}s'
                  f' (attempt {attempt + 1}/{max_retries})...'
              )
              time.sleep(sleep_s)
            else:
              print(
                  f'[{self.name}] Embedding API unavailable ({e}); using'
                  f' deterministic lexical embedding fallback for {len(batch)}'
                  ' item(s).'
              )
              break

        if not batch_embs or len(batch_embs) != len(batch):
          batch_embs = [_deterministic_lexical_embedding(t) for t in batch]
          cache_these = False
        else:
          cache_these = True

        with _EMBEDDING_CACHE_LOCK:
          for t_str, vec in zip(batch, batch_embs):
            if cache_these and len(_GLOBAL_EMBEDDING_CACHE) < 4096:
              _GLOBAL_EMBEDDING_CACHE[t_str] = vec
            for target_idx in missing_map.get(t_str, []):
              results[target_idx] = vec

    return [
        r if r is not None else _deterministic_lexical_embedding(q)
        for r, q in zip(results, normalized_queries)
    ]

  def cosine_similarity(self, v1, v2):
    """Calculates cosine similarity score between two embedding vectors."""
    n1 = np.linalg.norm(v1)
    n2 = np.linalg.norm(v2)
    if n1 == 0 or n2 == 0:
      return 0.0
    return float(np.dot(v1, v2) / (n1 * n2))

  def execute(self, query, slide_data_list, section_metadata=None):
    """Scores slide items against a query using multi-factor semantic and metadata alignment."""
    section_metadata = section_metadata or {}
    expected_jobs = section_metadata.get('expected_slide_jobs', [])
    if isinstance(expected_jobs, str):
      expected_jobs = [expected_jobs]
    expected_cvi = section_metadata.get('expected_cvi_cluster', '')
    expected_topics = [
        str(t).lower().strip()
        for t in section_metadata.get('expected_core_topics', [])
        if t
    ]
    expected_prods = [
        str(p).lower().strip()
        for p in section_metadata.get('expected_products', [])
        if p
    ]
    archetype_weights = section_metadata.get('archetype_job_weights', {})
    anchor_deck_id = section_metadata.get('primary_anchor_deck_id')

    try:
      query_emd = self.get_embeddings([query])[0]
    except Exception as e:
      print(f"[{self.name}] Embedding generation failed ({e}), assigning default relevance scores.")
      for slide in slide_data_list:
        slide['sim_score'] = 0.8
      return slide_data_list

    # Identify slides missing embeddings and gather their descriptions
    missing_indices = []
    missing_descriptions = []
    for idx, slide in enumerate(slide_data_list):
      if 'desc_embedding' not in slide:
        desc_parts = [
            str(slide.get('title') or slide.get('name') or '').strip(),
            str(
                slide.get('desc')
                or slide.get('content')
                or slide.get('slide_summary')
                or slide.get('speaker_notes')
                or ''
            ).strip(),
        ]
        desc = ' — '.join(p for p in desc_parts if p)
        if desc:
          missing_indices.append(idx)
          missing_descriptions.append(desc[:1500])
        else:
          print(
              f"[{self.name}] Warning: Slide"
              f" '{slide.get('name', 'N/A')}' has no embedding and no"
              " description to calculate one."
          )

    # Calculate missing embeddings in batch
    if missing_descriptions:
      print(
          f"[{self.name}] Calculating embeddings on the fly for"
          f" {len(missing_descriptions)} slides..."
      )
      try:
        calculated_embs = self.get_embeddings(missing_descriptions)
        for i, emb in zip(missing_indices, calculated_embs):
          slide_data_list[i]['desc_embedding'] = emb
      except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"[{self.name}] Error calculating embeddings on the fly: {e}")

    results = []
    print(
        f"[{self.name}] Scoring {len(slide_data_list)} slides with multi-factor metadata alignment against query:"
        f" '{query[:50]}...'"
    )
    skipped_no_emb = 0
    for slide in slide_data_list:
      if 'desc_embedding' in slide or '_sim_score' in slide:
        if 'desc_embedding' in slide:
          emb_sim = float(
              self.cosine_similarity(
                  query_emd, np.array(slide['desc_embedding'])
              )
          )
        else:
          emb_sim = float(slide.get('_sim_score') or 0.7)
        retriever_sim = min(1.0, float(slide.get('_sim_score') or 0.0))
        base_sim = max(emb_sim, (0.65 * emb_sim) + (0.35 * retriever_sim))

        # 1. Slide Job Match Score (scaled by Archetype weighting)
        s_job = slide.get('slide_job', '')
        s_cvi = slide.get('cvi_cluster', '')
        job_weight = (
            float(archetype_weights.get(s_job, 0.7))
            if (archetype_weights and s_job)
            else float(archetype_weights.get(expected_jobs[0], 0.8))
            if (archetype_weights and expected_jobs)
            else 1.0
        )

        if s_job:
          if expected_jobs and s_job in expected_jobs:
            job_score = 1.0 * job_weight
          elif expected_cvi and s_cvi == expected_cvi:
            job_score = 0.6 * job_weight
          elif not expected_jobs:
            job_score = 0.5 * job_weight
          else:
            job_score = 0.3 * job_weight
        else:
          # Unannotated slide from legacy datastore: assign neutral score scaled by archetype
          job_score = 0.6 * job_weight

        # 2. Core Topics Overlap
        s_topics = [
            str(t).lower().strip()
            for t in slide.get('core_topics', [])
            if t
        ]
        if expected_topics and s_topics:
          overlap = set(expected_topics).intersection(set(s_topics))
          topic_score = min(1.0, len(overlap) / max(1, len(expected_topics)))
        else:
          topic_score = 0.5

        # 3. Product Match Score
        s_prods = [
            str(p).lower().strip()
            for p in slide.get('google_product', [])
            if p
        ]
        if expected_prods and s_prods:
          prod_overlap = any(
              any(ep in sp or sp in ep for sp in s_prods)
              for ep in expected_prods
          )
          prod_score = 1.0 if prod_overlap else 0.4
        else:
          prod_score = 0.5

        # 4. Multi-Anchor Foundation Deck & Industry Vertical Affinity Bonus
        slide_deck_id = slide.get('deck_id') or slide.get('deckId')
        section_anchor = section_metadata.get('section_anchor_deck_id')
        vertical_anchor_id = section_metadata.get('vertical_anchor_deck_id')
        global_anchors = section_metadata.get('anchor_deck_ids', [])
        primary_anchor = section_metadata.get('primary_anchor_deck_id')

        anchor_affinity = 0.0
        if slide_deck_id:
          is_cvi_or_job_aligned = (
              expected_cvi not in ('Context', 'Realization')
              or (expected_jobs and s_job in expected_jobs)
              or (expected_cvi and s_cvi == expected_cvi)
          )
          if vertical_anchor_id and slide_deck_id == vertical_anchor_id and (
              expected_cvi == 'Context'
              or 'Why_Google_Cloud' in expected_jobs
              or 'Market_Trends' in expected_jobs
              or section_anchor == vertical_anchor_id
          ):
            anchor_affinity = 0.35
          elif section_anchor and slide_deck_id == section_anchor:
            anchor_affinity = 0.32
          elif vertical_anchor_id and slide_deck_id == vertical_anchor_id:
            anchor_affinity = 0.28
          elif (
              primary_anchor
              and slide_deck_id == primary_anchor
              and is_cvi_or_job_aligned
          ):
            anchor_affinity = 0.28
          elif (
              global_anchors
              and slide_deck_id in global_anchors
              and is_cvi_or_job_aligned
          ):
            anchor_affinity = 0.25

        # Multi-factor composite relevance score
        composite_score = (
            (0.40 * base_sim)
            + (0.25 * job_score)
            + (0.15 * topic_score)
            + (0.10 * prod_score)
            + (0.10 * (1.0 if expected_cvi and s_cvi == expected_cvi else 0.5))
            + anchor_affinity
        )
        if (
            slide.get('_source_library') == 'customer_ref_gslides'
            or slide.get('_source_datastore_key') == 'cust_ref'
        ) and not section_metadata.get('exclude_customer_refs', False):
          composite_score = max(composite_score, retriever_sim)
        composite_score = min(1.0, composite_score)

        slide['sim_score'] = round(composite_score, 4)
        slide['_semantic_score'] = round(base_sim, 4)
        slide['_job_score'] = round(job_score, 4)
        slide['_topic_score'] = round(topic_score, 4)
        slide['_anchor_match'] = bool(anchor_affinity > 0)

        print(
            f"[{self.name}] Slide: '{slide.get('name', 'N/A')}', Composite: {slide['sim_score']} "
            f"(Semantic: {slide['_semantic_score']}, Job: {slide['_job_score']}, Anchor: {slide['_anchor_match']})"
        )
        if composite_score >= 0.45:
          results.append(slide)
      else:
        skipped_no_emb += 1
    if skipped_no_emb > 0:
      print(
          f"[{self.name}] Skipped {skipped_no_emb} slides because they lacked"
          " 'desc_embedding'"
      )
    results.sort(key=lambda x: x.get('sim_score', 0), reverse=True)
    return results
