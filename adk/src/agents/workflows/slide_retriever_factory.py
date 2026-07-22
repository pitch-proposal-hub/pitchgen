from abc import ABC, abstractmethod
from typing import Any, Dict, List

class BaseRetriever(ABC):
    @abstractmethod
    def search_slides(self, query: str, context: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
        pass

class StandardDatastoreRetriever(BaseRetriever):
    """Wrapper strategy for all existing/legacy datastores."""
    def __init__(self, config: Dict[str, Any], datastore_id: str, ds_key: str):
        from agents.workflows.slide_search_workflow import SlideSearchWorkflow
        self.search_workflow = SlideSearchWorkflow(config)
        self.datastore_id = datastore_id
        self.ds_key = ds_key

    def search_slides(self, query: str, context: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
        raw_results = self.search_workflow.execute(query, self.datastore_id)
        formatted_results = []
        for r in raw_results:
            formatted = dict(r)
            formatted["slide_id"] = r.get("slideIds", [None])[0] or r.get("slideId")
            formatted["deck_id"] = r.get("deckId")
            formatted["slide_url"] = r.get("temp_url") or r.get("tempUrl")
            formatted["title"] = r.get("name") or r.get("title") or "No Title"
            formatted["content"] = r.get("desc") or r.get("content") or ""
            formatted["customer"] = r.get("customer") or r.get("customer_name") or ""
            formatted["sim_score"] = r.get("_sim_score", 0.0)
            formatted["_source_datastore_key"] = self.ds_key
            formatted_results.append(formatted)
        return formatted_results

class IsolatedSalesPlayRetriever(BaseRetriever):
    """Sandboxed retriever strategy for the new consolidated Sales Play datastore."""
    def __init__(self, config: Dict[str, Any], datastore_id: str, ds_key: str):
        from agents.workflows.isolated_sales_play_retriever import IsolatedSalesPlayRetriever as PoCRetriever
        self.poc_retriever = PoCRetriever(
            project_id=config["default"]["project_name"],
            datastore_id=datastore_id
        )
        self.config = config
        self.ds_key = ds_key

    def _execute_with_fallback(self, query: str, criteria: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        # 1. Query Consolidated Primary Datastore
        results = self.poc_retriever.search_reusable_slides(query, criteria, limit=limit)
        
        # 2. Failover to Backup Singles Datastore if Primary is Empty
        if not results:
            backup_secret = "reusable_sales_play_singles_datastore"
            from config_loader import resolve_secret_with_cache
            backup_ds_id = resolve_secret_with_cache(backup_secret)
            print(f"[PoC Fallback] Primary empty. Retrying query on backup store: '{backup_ds_id}'")
            
            # Query backup datastore using standard layout search
            from agents.workflows.slide_search_workflow import SlideSearchWorkflow
            fallback_workflow = SlideSearchWorkflow(self.config)
            backup_results = fallback_workflow.execute(query, backup_ds_id)
            return backup_results
        return results

    def search_slides(self, query: str, context: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
        search_criteria = {
            "region": context.get("region"),
            "industry": context.get("industry"),
            "product": context.get("product"),
            "target_audience": context.get("audience"),
            "sales_play": context.get("salesPlay"),
            "practice_area": context.get("practice_area"),
            "exclude_customer_refs": True
        }
        
        raw_results = self._execute_with_fallback(query, search_criteria, limit)
        
        # Output Interface Alignment mapping
        formatted_results = []
        for r in raw_results:
            formatted = dict(r)
            formatted["slide_id"] = r.get("slide_id") or (r.get("slideIds", [None])[0] if "slideIds" in r else None)
            formatted["deck_id"] = r.get("deck_id") or r.get("deckId")
            formatted["slide_url"] = r.get("slide_url") or r.get("temp_url") or r.get("tempUrl")
            formatted["title"] = r.get("slide_title") or r.get("deck_title") or r.get("name") or "No Title"
            formatted["content"] = r.get("slide_summary") or r.get("speaker_notes") or r.get("group_summary") or r.get("desc") or ""
            formatted["customer"] = ""
            formatted["sim_score"] = r.get("_sim_score", 0.0)
            formatted["_source_datastore_key"] = self.ds_key
            
            # Map new schema lists back to legacy fields so the tag scorer can calculate overlaps
            formatted["product"] = r.get("product", [])
            formatted["salesPlay"] = r.get("sales_play", [])
            formatted_results.append(formatted)
        return formatted_results

class SlideRetrieverFactory:
    """Orchestrates retriever strategy mapping."""
    @staticmethod
    def get_retriever(ds_key: str, datastore_id: str, config: Dict[str, Any]) -> BaseRetriever:
        if ds_key == "sales_play_reusables":
            return IsolatedSalesPlayRetriever(config, datastore_id, ds_key)
        else:
            return StandardDatastoreRetriever(config, datastore_id, ds_key)
