from abc import ABC, abstractmethod
from typing import Any, Dict, List

def _is_standalone_title_or_divider_candidate(r: Dict[str, Any]) -> bool:
  """Returns True if a search result from Vertex AI Search is a standalone Title Card, Section Divider, Agenda, or Thank You slide."""
  job = str(r.get("slide_job") or "").strip().lower()
  if job in (
      "title",
      "title_slide",
      "section_divider",
      "divider",
      "agenda",
      "cover",
      "thank_you",
      "closing",
      "q_and_a",
  ):
    return True
  title = str(
      r.get("slide_title")
      or r.get("original_title")
      or r.get("name")
      or r.get("title")
      or ""
  ).strip()
  summary = str(
        r.get("slide_summary")
        or r.get("original_content")
        or r.get("desc")
        or r.get("content")
        or r.get("speaker_notes")
        or ""
    ).strip()
  lower_title = title.lower().strip(" .!?:;-")
  lower_summary = summary.lower()
  # Explicitly block Thank You / Q&A / Closing / Appendix slides regardless of deck_id
  if lower_title in (
      "thank you",
      "thanks",
      "thank you!",
      "questions",
      "questions?",
      "q&a",
      "q & a",
      "appendix",
      "agenda",
      "table of contents",
  ) or lower_title.startswith("thank you"):
    return True
  if any(
      marker in lower_summary
      for marker in (
          "title card",
          "title slide",
          "section divider",
          "section header",
          "chapter divider",
          "agenda slide",
          "table of contents",
          "thank you slide",
          "closing slide",
      )
  ):
    return True
  # If the slide has no substantive body/summary text (< 45 chars) and no products/topics
  slide_job = str(r.get("slide_job") or "").strip()
  substantive_jobs = {
      "Solution_Overview",
      "Architecture",
      "Why_Google_Cloud",
      "Business_Value",
      "Strategic_Partnership",
      "Market_Trends",
      "Current_State",
      "Proof_Points",
      "Vision",
      "Path_to_Prod",
      "Commercials",
  }
  if (
      len(title) < 35
      and len(summary) < 45
      and slide_job not in substantive_jobs
      and not r.get("google_product")
      and not r.get("core_topics")
  ):
    return True
  return False


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
            if _is_standalone_title_or_divider_candidate(r):
                continue
            formatted = dict(r)
            formatted["slide_id"] = r.get("slideIds", [None])[0] or r.get("slideId")
            formatted["deck_id"] = r.get("deckId")
            formatted["slide_url"] = r.get("temp_url") or r.get("tempUrl")
            formatted["title"] = r.get("name") or r.get("title") or "No Title"
            formatted["content"] = r.get("desc") or r.get("content") or ""
            formatted["customer"] = r.get("customer") or r.get("customer_name") or ""
            formatted["sim_score"] = r.get("_sim_score", 0.0)
            formatted["_source_datastore_key"] = self.ds_key

            # Guarantee that all slides from customer references datastores are strictly catalogued as Proof_Points
            if self.ds_key in ("cust_ref", "customer_references", "customer_stories") or "cust-ref" in self.datastore_id.lower():
                formatted["slide_job"] = "Proof_Points"
                formatted["is_cust_ref"] = True
                formatted["is_proof_point"] = True
            else:
                formatted["slide_job"] = r.get("slide_job", "")

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
      print(
          "[PoC Fallback] Primary empty. Retrying query on backup store:"
          f" '{backup_ds_id}'"
      )

      # Query backup datastore using standard layout search
      from agents.workflows.slide_search_workflow import SlideSearchWorkflow

      fallback_workflow = SlideSearchWorkflow(self.config)
      backup_results = fallback_workflow.execute(query, backup_ds_id)
      return backup_results
    return results

  def search_slides(
      self, query: str, context: Dict[str, Any], limit: int = 5
  ) -> List[Dict[str, Any]]:
    search_criteria = {
        "region": context.get("region"),
        "industry": context.get("closest_industry") or context.get("industry"),
        "closest_industry": context.get("closest_industry"),
        "google_product": (
            context.get("product")
            or context.get("google_product")
            or context.get("expected_products")
        ),
        "target_audience": (
            context.get("audience") or context.get("target_audience")
        ),
        "sales_play": (
            context.get("section_sales_play")
            or context.get("salesPlay")
            or context.get("sales_play")
            or context.get("sales_plays")
        ),
        "section_sales_play": context.get("section_sales_play"),
        "practice_area": context.get("practice_area"),
        "slide_job": (
            context.get("expected_slide_jobs") or context.get("slide_job")
        ),
        "cvi_cluster": (
            context.get("expected_cvi_cluster") or context.get("cvi_cluster")
        ),
        "core_topics": (
            context.get("expected_core_topics") or context.get("core_topics")
        ),
        "technical_maturity": (
            context.get("expected_maturity")
            or context.get("technical_maturity")
        ),
        "job_boost": context.get("job_boost", 0.8),
        "primary_anchor_deck_id": context.get("primary_anchor_deck_id"),
        "section_anchor_deck_id": context.get("section_anchor_deck_id"),
        "vertical_anchor_deck_id": context.get("vertical_anchor_deck_id"),
        "anchor_deck_ids": context.get("anchor_deck_ids", []),
        "exclude_customer_refs": context.get("exclude_customer_refs", True),
    }

    raw_results = self._execute_with_fallback(query, search_criteria, limit)

    # Output Interface Alignment mapping
    formatted_results = []
    for r in raw_results:
      if _is_standalone_title_or_divider_candidate(r):
        continue
      formatted = dict(r)
      formatted["slide_id"] = r.get("slide_id") or (
          r.get("slideIds", [None])[0] if "slideIds" in r else None
      )
      formatted["deck_id"] = r.get("deck_id") or r.get("deckId")
      formatted["slide_url"] = (
          r.get("slide_url") or r.get("temp_url") or r.get("tempUrl")
      )
      formatted["deck_title"] = r.get("deck_title") or ""
      slide_summary_str = str(
          r.get("slide_summary")
          or r.get("desc")
          or r.get("group_summary")
          or ""
      ).strip()
      derived_slide_title = (
          r.get("slide_title")
          or r.get("name")
          or (
              slide_summary_str.split(".")[0][:90].strip()
              if slide_summary_str
              else ""
          )
          or r.get("deck_title")
          or "No Title"
      )
      formatted["title"] = derived_slide_title
      formatted["name"] = derived_slide_title
      formatted["content"] = (
          r.get("slide_summary")
          or r.get("speaker_notes")
          or r.get("group_summary")
          or r.get("desc")
          or ""
      )
      formatted["speaker_notes"] = r.get("speaker_notes") or ""
      formatted["customer_references"] = r.get("customer_references")
      formatted["customer"] = ""
      formatted["sim_score"] = r.get("_sim_score", 0.0)
      formatted["_source_datastore_key"] = self.ds_key

      # Map structural & topic metadata
      formatted["slide_job"] = r.get("slide_job") or ""
      formatted["cvi_cluster"] = r.get("cvi_cluster") or ""
      formatted["core_topics"] = r.get("core_topics", [])
      formatted["google_product"] = r.get("google_product", [])
      formatted["product"] = r.get("google_product", [])
      formatted["sales_play"] = r.get("sales_play", [])
      formatted["salesPlay"] = r.get("sales_play", [])
      formatted["target_audience"] = r.get("target_audience", [])
      formatted["technical_maturity"] = r.get("technical_maturity") or ""
      formatted_results.append(formatted)
    return formatted_results


class SlideRetrieverFactory:
  """Orchestrates retriever strategy mapping."""

  @staticmethod
  def get_retriever(
      ds_key: str, datastore_id: str, config: Dict[str, Any]
  ) -> BaseRetriever:
    if ds_key == "sales_play_reusables":
      return IsolatedSalesPlayRetriever(config, datastore_id, ds_key)
    elif ds_key in ("cust_ref", "customer_references", "customer_stories"):
      reusable_cfg = (
          config.get("reusable", {}) if isinstance(config, dict) else {}
      )
      enable_new_lib = str(
          reusable_cfg.get("enable_new_cust_ref_library", "true")
      ).strip().lower() not in ("false", "0", "no")
      if enable_new_lib:
        from agents.workflows.customer_reference_retriever import NewLibraryCustomerReferenceRetriever

        return NewLibraryCustomerReferenceRetriever(
            config, datastore_id, ds_key
        )
      legacy_id = (
          reusable_cfg.get("legacy_cust_ref")
          or "reusable-cust-ref-ds-v1_1752739526903_gcs_store"
      )
      return StandardDatastoreRetriever(config, legacy_id, ds_key)
    else:
      return StandardDatastoreRetriever(config, datastore_id, ds_key)
