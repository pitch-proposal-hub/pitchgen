import os
from typing import Any, Dict, List
from google.cloud import discoveryengine_v1 as discoveryengine
import google.protobuf.json_format as json_format

class IsolatedSalesPlayRetriever:
    """Isolated retriever class for the consolidated Sales Play Datastore."""

    def __init__(self, project_id: str, datastore_id: str, location: str = "global"):
        self.project_id = project_id
        self.datastore_id = datastore_id
        self.location = location
        self.client = discoveryengine.SearchServiceClient()
        self.serving_config = self.client.serving_config_path(
            project=self.project_id,
            location=self.location,
            data_store=self.datastore_id,
            serving_config="default_config"
        )

    def _build_filter_expression(self, criteria: Dict[str, Any]) -> str:
        """Constructs strict metadata filters based on the opportunity context."""
        filters = []
        
        # Region filter (string Array)
        if criteria.get("region"):
            filters.append(f'region: ANY("{criteria["region"]}")')
            
        # Industry filter (string Array)
        if criteria.get("industry"):
            filters.append(f'industry: ANY("{criteria["industry"]}")')
            
        # Target Products (string Array)
        if criteria.get("product"):
            prods = criteria["product"]
            prod_list = [prods] if isinstance(prods, str) else prods
            prod_filter = ", ".join([f'"{p}"' for p in prod_list])
            filters.append(f'product: ANY({prod_filter})')
            
        # Target Audience (string Array)
        if criteria.get("target_audience"):
            auds = criteria["target_audience"]
            aud_list = [auds] if isinstance(auds, str) else auds
            aud_filter = ", ".join([f'"{a}"' for a in aud_list])
            filters.append(f'target_audience: ANY({aud_filter})')

        # Technical Maturity filter (string)
        if criteria.get("technical_maturity"):
            filters.append(f'technical_maturity: ANY("{criteria["technical_maturity"]}")')
            
        # CVI Narrative Stage (string)
        if criteria.get("cvi_cluster"):
            filters.append(f'cvi_cluster: ANY("{criteria["cvi_cluster"]}")')

        # Exclude customer references to prevent competitor leaks during generic searches
        if criteria.get("exclude_customer_refs", True):
            filters.append('customer_references = "false"')

        return " AND ".join(filters)

    def _build_boost_spec(self, criteria: Dict[str, Any]) -> discoveryengine.SearchRequest.BoostSpec:
        """Constructs relevance boost spec for opportunity context alignment."""
        condition_boost_specs = []
        if criteria.get("sales_play"):
            condition_boost_specs.append(
                discoveryengine.SearchRequest.BoostSpec.ConditionBoostSpec(
                    condition=f'sales_play: ANY("{criteria["sales_play"]}")',
                    boost=0.5
                )
            )
        if criteria.get("practice_area"):
            condition_boost_specs.append(
                discoveryengine.SearchRequest.BoostSpec.ConditionBoostSpec(
                    condition=f'practice_area: ANY("{criteria["practice_area"]}")',
                    boost=0.3
                )
            )
        return discoveryengine.SearchRequest.BoostSpec(
            condition_boost_specs=condition_boost_specs
        )

    def search_reusable_slides(self, query: str, criteria: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
        """Queries the Sales Play datastore using filters and boost rules."""
        filter_expr = self._build_filter_expression(criteria)
        boost_spec = self._build_boost_spec(criteria)
        
        request = discoveryengine.SearchRequest(
            serving_config=self.serving_config,
            query=query,
            filter=filter_expr,
            boost_spec=boost_spec,
            page_size=limit
        )

        try:
            response = self.client.search(request)
            results = []
            for result in response._response.results:
                doc_dict = json_format.MessageToDict(result.document._pb)
                struct_data = doc_dict.get("structData", {})
                struct_data["_sim_score"] = getattr(result, "relevance", 0.0)
                results.append(struct_data)
            return results
        except Exception as e:
            print(f"[PoC Search] Error querying datastore: {e}")
            return []
