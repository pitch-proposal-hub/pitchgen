"""Skill to query the Developer Knowledge API via REST using thread-safe clients."""

import functools
import threading
from agents.workflows.base_workflow import BaseWorkflow
import google.auth
from google.auth.transport.requests import AuthorizedSession
from googleapiclient import discovery
from googleapiclient import errors

DISCOVERY_URL = (
    "https://developerknowledge.googleapis.com/$discovery/rest?version=v1"
)
REST_SEARCH_URL = "https://developerknowledge.googleapis.com/v1/documents:searchDocumentChunks"


class DeveloperKnowledgeWorkflow(BaseWorkflow):
  """Thread-safe workflow for querying the Developer Knowledge API."""

  def __init__(self, config):
    super().__init__(
        "DeveloperKnowledgeWorkflow",
        "Queries Developer Knowledge API for product documentation.",
    )
    self.config = config
    self._local = threading.local()

  def _get_session(self) -> AuthorizedSession:
    session = getattr(self._local, "session", None)
    if session is None:
      creds, _ = google.auth.default(
          scopes=["https://www.googleapis.com/auth/cloud-platform"]
      )
      session = AuthorizedSession(creds)
      self._local.session = session
    return session

  def _get_service(self):
    service = getattr(self._local, "service", None)
    if service is None:
      service = discovery.build(
          "developerknowledge",
          "v1",
          discoveryServiceUrl=DISCOVERY_URL,
          static_discovery=False,
      )
      self._local.service = service
    return service

  @functools.lru_cache(maxsize=128)
  def _cached_search(self, query: str) -> str:
    # Primary path: thread-safe AuthorizedSession REST request (urllib3 pool)
    try:
      session = self._get_session()
      resp = session.get(
          REST_SEARCH_URL,
          params={"query": query, "pageSize": 3},
          timeout=6.0,
      )
      if resp.status_code == 200:
        data = resp.json()
        results = []
        for res in data.get("results", []):
          parent = res.get("parent", "")
          content = res.get("content", "")
          results.append(f"Source: {parent}\nSnippet: {content}")
        return "\n\n".join(results)
    except Exception as rest_err:
      print(
          "[DeveloperKnowledgeWorkflow] REST session fallback notice:"
          f" {rest_err}"
      )

    # Fallback path: thread-local googleapiclient discovery service
    service = self._get_service()
    response = (
        service.documents()
        .searchDocumentChunks(query=query, pageSize=3)
        .execute()
    )
    results = []
    if "results" in response:
      for res in response["results"]:
        parent = res.get("parent", "")
        content = res.get("content", "")
        results.append(f"Source: {parent}\nSnippet: {content}")
    return "\n\n".join(results)

  def execute(self, query):
    print(f"[DeveloperKnowledgeWorkflow] Searching for: {query} via REST...")
    try:
      return self._cached_search(str(query or "").strip())
    except errors.HttpError as e:
      print(f"[DeveloperKnowledgeWorkflow] HTTP Error: {e}")
      return f"Failed to retrieve developer docs due to HTTP error: {e}"
    except Exception as e:
      print(f"[DeveloperKnowledgeWorkflow] Error: {e}")
      return f"Failed to retrieve developer docs due to error: {e}"
