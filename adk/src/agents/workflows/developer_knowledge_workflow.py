"""Skill to query the Developer Knowledge API via REST using googleapiclient."""

from googleapiclient import discovery
from googleapiclient import errors
from agents.workflows.base_workflow import BaseWorkflow

DISCOVERY_URL = (
    "https://developerknowledge.googleapis.com/$discovery/rest?version=v1"
)


class DeveloperKnowledgeWorkflow(BaseWorkflow):

  def __init__(self, config):
    super().__init__(
        "DeveloperKnowledgeWorkflow",
        "Queries Developer Knowledge API for product documentation.",
    )
    self.config = config
    self._service = None

  def _get_service(self):
    if not self._service:
      self._service = discovery.build(
          "developerknowledge",
          "v1",
          discoveryServiceUrl=DISCOVERY_URL,
          static_discovery=False,
      )
    return self._service

  def execute(self, query):
    print(f"[DeveloperKnowledgeWorkflow] Searching for: {query} via REST...")
    try:
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

    except errors.HttpError as e:
      print(f"[DeveloperKnowledgeWorkflow] HTTP Error: {e}")
      return f"Failed to retrieve developer docs due to HTTP error: {e}"
    except Exception as e:
      print(f"[DeveloperKnowledgeWorkflow] Error: {e}")
      return f"Failed to retrieve developer docs due to error: {e}"
