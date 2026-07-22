from google.cloud import discoveryengine_v1 as discoveryengine
from agents.workflows.base_workflow import BaseWorkflow
from config_loader import resolve_secret_with_cache


class SlideSearchWorkflow(BaseWorkflow):

  def __init__(self, config):
    super().__init__(
        'SlideSearchWorkflow',
        'Searches for relevant slides in specific datastores.',
    )
    self.config = config
    self.project_id = config['default']['project_name']
    self.discovery_client = discoveryengine.SearchServiceClient()
    self.location = 'global'

  def execute(self, query, datastore_id, filters=''):
    real_datastore_id = resolve_secret_with_cache(datastore_id)


    serving_config = self.discovery_client.serving_config_path(
        project=self.project_id,
        location=self.location,
        data_store=real_datastore_id,
        serving_config='default_config',
    )
    request = discoveryengine.SearchRequest(
        serving_config=serving_config,
        query=query,
        filter=filters,
        page_size=10,
    )
    try:
      response = self.discovery_client.search(request)
      results = []
      for result in response._response.results:
        # Convert struct_data and any nested proto objects to dict
        import google.protobuf.json_format as json_format

        doc_dict = json_format.MessageToDict(result.document._pb)
        struct_data = doc_dict.get('structData', {})
        results.append(struct_data)
      print(
          f"[{self.name}] Query: '{query}', Datastore:"
          f" {real_datastore_id}, Results found: {len(results)}"
      )
      return results
    except Exception as e:
      print(f'Slide search error: {e}')
      return []
