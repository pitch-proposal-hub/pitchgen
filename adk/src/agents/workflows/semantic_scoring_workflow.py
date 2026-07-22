"""Semantic scoring skill for calculating relevance scores for slides using embeddings."""

import json
from google.cloud import discoveryengine_v1 as discoveryengine
from google.cloud import secretmanager
from google import genai
from google.genai import types
import numpy as np
from agents.workflows.base_workflow import BaseWorkflow


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

  def get_embeddings(self, queries):
    """Generates embedding vectors for a list of string queries."""
    model_name = self.config['default'].get(
        'embedding_model', 'text-embedding-005'
    )
    response = self.client.models.embed_content(
        model=model_name,
        contents=queries,
    )
    return [np.array(e.values) for e in response.embeddings]

  def cosine_similarity(self, v1, v2):
    """Calculates cosine similarity score between two embedding vectors."""
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

  def execute(self, query, slide_data_list):
    """Scores slide items against a query by semantic similarity."""
    query_emd = self.get_embeddings([query])[0]

    # Identify slides missing embeddings and gather their descriptions
    missing_indices = []
    missing_descriptions = []
    for idx, slide in enumerate(slide_data_list):
      if 'desc_embedding' not in slide:
        desc = slide.get('desc') or slide.get('content') or ''
        if desc:
          missing_indices.append(idx)
          missing_descriptions.append(desc)
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
        f"[{self.name}] Scoring {len(slide_data_list)} slides against query:"
        f" '{query[:50]}...'"
    )
    skipped_no_emb = 0
    for slide in slide_data_list:
      if 'desc_embedding' in slide:
        score = self.cosine_similarity(
            query_emd, np.array(slide['desc_embedding'])
        )
        print(
            f"[{self.name}] Slide: '{slide.get('name', 'N/A')}', Score: {score}"
        )
        if score >= 0.4:
          slide['sim_score'] = score
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
