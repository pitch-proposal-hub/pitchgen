import concurrent.futures
import re
from uuid import uuid4

from google import genai
from google.cloud import discoveryengine_v1 as discoveryengine
from google.cloud import secretmanager
from google.genai import types
from google.genai.types import GenerateContentConfig, Tool
import numpy as np
from config_loader import load_config, resolve_secret_with_cache


def create_embeddings(text: str, client: genai.Client):
  import os

  model_id = os.getenv("EMBEDDING_MODEL", "text-embedding-005")
  response = client.models.embed_content(model=model_id, contents=text)
  return response.embeddings[0].values


def faiss_retriever_creation(url_list):
  url_content_list = []

  config = load_config()
  project_id = config["default"]["project_name"]
  client = genai.Client(
      vertexai=True,
      project=project_id,
      location="global",
  )
  embedding_client = genai.Client(
      vertexai=True,
      project=project_id,
      location="global",
  )
  model_id = config["default"]["gemini_model"]

  for i in range(len(url_list)):
    url = url_list[i]
    tools = [{"url_context": {}}]
    response = client.models.generate_content(
        model=model_id,
        contents=f"Extract all the contents from the given url: {url}",
        config=GenerateContentConfig(tools=tools),
    )
    url_content = ""
    if response.candidates and response.candidates[0].content.parts:
      url_content = "".join([
          part.text
          for part in response.candidates[0].content.parts
          if hasattr(part, "text") and part.text
      ])
    if not url_content.strip():
      print(f"Warning: Could not extract valid text from {url}")
      continue

    doc_dict = {
        "page_content": url_content,
        "metadata": {"url": url, "name": url.split("//")[1].split("/")[0]},
    }
    url_content_list.append(doc_dict)

  if not url_content_list:
    return None, []

  # Generate embeddings for all docs
  embeddings_list = []
  for doc in url_content_list:
    emb = create_embeddings(doc["page_content"], embedding_client)
    embeddings_list.append(emb)

  embeddings_np = np.array(embeddings_list).astype("float32")

  return embeddings_np, url_content_list


def search_faiss_index(embeddings_np, doc_store, query, client, k=1):
  if embeddings_np is None or not doc_store:
    return []

  query_emb = create_embeddings(query, client)

  # Compute cosine similarities
  query_norm = query_emb / (np.linalg.norm(query_emb) + 1e-9)
  embeddings_norm = embeddings_np / (
      np.linalg.norm(embeddings_np, axis=1, keepdims=True) + 1e-9
  )

  similarities = np.dot(embeddings_norm, query_norm)

  # Get top k indices
  top_indices = np.argsort(similarities)[::-1][:k]

  results = []
  for idx in top_indices:
    if idx < len(doc_store) and idx >= 0:
      results.append(doc_store[idx])
  return results


def search_vertex_datastore(
    project_id, location, datastore_id, query, num_results=3
):
  client = discoveryengine.SearchServiceClient()
  serving_config = client.serving_config_path(
      project=project_id,
      location=location,
      data_store=datastore_id,
      serving_config="default_config",
  )
  request = discoveryengine.SearchRequest(
      serving_config=serving_config,
      query=query,
      page_size=num_results,
      content_search_spec=discoveryengine.SearchRequest.ContentSearchSpec(
          extractive_content_spec=discoveryengine.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
              max_extractive_answer_count=3
          )
      ),
  )

  try:
    response = client.search(request)
    results = []
    for result in response.results:
      content = ""
      extractive_answers = result.document.derived_struct_data.get(
          "extractive_answers", []
      )
      if extractive_answers:
        content = " ".join(
            [ans.get("content", "") for ans in extractive_answers]
        )
      else:
        struct_data = result.document.struct_data
        if struct_data:
          content = str(struct_data)

      url = ""
      if "link" in result.document.derived_struct_data:
        url = result.document.derived_struct_data["link"]
      elif (
          hasattr(result.document, "content")
          and result.document.content
          and result.document.content.uri
      ):
        url = result.document.content.uri

      doc_dict = {
          "page_content": content,
          "metadata": {"url": url, "name": datastore_id},
      }
      results.append(doc_dict)
    return results
  except Exception as e:
    print(f"Error searching datastore {datastore_id}: {e}")
    return []


class CustomEnsembleRetriever:

  def __init__(self, url_list):
    self.config = load_config()
    self.project_id = self.config["default"]["project_name"]
    self.location = self.config["default"]["region"]

    self.client = genai.Client(
        vertexai=True,
        project=self.project_id,
        location="global",
    )
    self.embedding_client = genai.Client(
        vertexai=True,
        project=self.project_id,
        location="global",
    )

    self.pitch_decks_ds_id = get_datastoreID("pitch_decks")
    self.website_ds_id = get_datastoreID("website")

    self.faiss_index = None
    self.doc_store = []
    if url_list:
      self.faiss_index, self.doc_store = faiss_retriever_creation(url_list)

  def retrieve(self, query):
    results = []

    with concurrent.futures.ThreadPoolExecutor() as executor:
      futures = [
          executor.submit(
              search_vertex_datastore,
              self.project_id,
              self.location,
              self.pitch_decks_ds_id,
              query,
          ),
          executor.submit(
              search_vertex_datastore,
              self.project_id,
              self.location,
              self.website_ds_id,
              query,
          ),
      ]
      if self.faiss_index:
        futures.append(
            executor.submit(
                search_faiss_index,
                self.faiss_index,
                self.doc_store,
                query,
                self.embedding_client,
            )
        )

      for future in concurrent.futures.as_completed(futures):
        try:
          res = future.result()
          if res:
            results.extend(res)
        except Exception as e:
          print(f"Error in ensemble search: {e}")
    return results

  def batch(self, queries):
    return [self.retrieve(q) for q in queries]


def ensemble_retriver(url_list):
  return CustomEnsembleRetriever(url_list)


def get_datastoreID(datastoreName):
  config = load_config()
  return resolve_secret_with_cache(config["datastore"][datastoreName])
