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

    if criteria.get("only_customer_refs"):
      filters.append('customer_references = "true"')
    elif criteria.get("proof_points_job_filter"):
      filters.append('slide_job: ANY("Proof_Points")')
    elif criteria.get("exclude_customer_refs", True):
      # Hard safety filter: Exclude customer references to prevent competitor leaks during generic searches
      filters.append('customer_references = "false"')

    # Optional strict industry filter if requested
    if criteria.get("strict_industry") and criteria.get("industry"):
      filters.append(
          f'industry: ANY("{criteria["industry"]}", "Cross-Industry")'
      )

    return " AND ".join(filters)

  def _build_boost_spec(
      self, criteria: Dict[str, Any]
  ) -> discoveryengine.SearchRequest.BoostSpec:
    """Constructs relevance boost spec for multi-dimensional metadata alignment."""
    condition_boost_specs = []

    # 0. Specific Section Anchor Deck Boost (radically prioritizes section's matched foundation deck)
    if criteria.get("section_anchor_deck_id"):
      sec_deck_id = criteria["section_anchor_deck_id"]
      condition_boost_specs.append(
          discoveryengine.SearchRequest.BoostSpec.ConditionBoostSpec(
              condition=f'deck_id: ANY("{sec_deck_id}")', boost=1.0
          )
      )

    # 0b. Vertical Anchor ("Why Google for <Industry>") Deck Boost
    if criteria.get("vertical_anchor_deck_id"):
      v_deck_id = criteria["vertical_anchor_deck_id"]
      condition_boost_specs.append(
          discoveryengine.SearchRequest.BoostSpec.ConditionBoostSpec(
              condition=f'deck_id: ANY("{v_deck_id}")', boost=0.95
          )
      )

    # 0c. All Pitch Anchor Decks Boost (sales play decks + closest Why Google deck)
    if criteria.get("anchor_deck_ids"):
      anchor_ids = criteria["anchor_deck_ids"]
      if isinstance(anchor_ids, str):
        anchor_ids = [anchor_ids]
      quoted_ids = ", ".join([f'"{d}"' for d in anchor_ids if d])
      if quoted_ids:
        condition_boost_specs.append(
            discoveryengine.SearchRequest.BoostSpec.ConditionBoostSpec(
                condition=f"deck_id: ANY({quoted_ids})", boost=0.8
            )
        )

    # 0d. Target Industry Vertical Boost (prioritizes industry-specific slides over generic cross-industry)
    target_ind = criteria.get("closest_industry") or criteria.get("industry")
    if target_ind and str(target_ind).strip().lower() not in (
        "none",
        "n/a",
        "cross-industry",
        "generic",
        "agnostic",
        "enterprise",
    ):
      ind_clean = str(target_ind).strip()
      condition_boost_specs.append(
          discoveryengine.SearchRequest.BoostSpec.ConditionBoostSpec(
              condition=f'industry: ANY("{ind_clean}")', boost=0.65
          )
      )

    # 0e. Section Specific Sales Play Boost
    if criteria.get("section_sales_play"):
      sec_sp = criteria["section_sales_play"]
      condition_boost_specs.append(
          discoveryengine.SearchRequest.BoostSpec.ConditionBoostSpec(
              condition=f'sales_play: ANY("{sec_sp}")', boost=0.7
          )
      )

    # 1. Slide Job Boost (scaled by Archetype weighting if provided)
    if criteria.get("slide_job"):
      jobs = criteria["slide_job"]
      job_list = (
          [jobs] if isinstance(jobs, str) else [str(j) for j in jobs if j]
      )
      if job_list:
        job_quoted = ", ".join([f'"{j}"' for j in job_list])
        boost_val = float(criteria.get("job_boost", 0.8))
        condition_boost_specs.append(
            discoveryengine.SearchRequest.BoostSpec.ConditionBoostSpec(
                condition=f"slide_job: ANY({job_quoted})", boost=boost_val
            )
        )

    # 2. CVI Narrative Stage Boost
    if criteria.get("cvi_cluster"):
      cvi = criteria["cvi_cluster"]
      cvi_list = [cvi] if isinstance(cvi, str) else [str(c) for c in cvi if c]
      if cvi_list:
        cvi_quoted = ", ".join([f'"{c}"' for c in cvi_list])
        condition_boost_specs.append(
                    discoveryengine.SearchRequest.BoostSpec.ConditionBoostSpec(
                        condition=f'cvi_cluster: ANY({cvi_quoted})',
                        boost=0.6
                    )
                )

    # 3. Core Topics Boost
    if criteria.get("core_topics"):
      topics = criteria["core_topics"]
      topic_list = [topics] if isinstance(topics, str) else [str(t) for t in topics if t]
      if topic_list:
        topics_quoted = ", ".join([f'"{t}"' for t in topic_list[:5]])
        condition_boost_specs.append(
                    discoveryengine.SearchRequest.BoostSpec.ConditionBoostSpec(
                        condition=f'core_topics: ANY({topics_quoted})',
                        boost=0.5
                    )
                )

    # 4. Target Google Products Boost
    if criteria.get("google_product"):
      prods = criteria["google_product"]
      prod_list = [prods] if isinstance(prods, str) else [str(p) for p in prods if p]
      if prod_list:
        prod_quoted = ", ".join([f'"{p}"' for p in prod_list[:5]])
        condition_boost_specs.append(
                    discoveryengine.SearchRequest.BoostSpec.ConditionBoostSpec(
                        condition=f'google_product: ANY({prod_quoted})',
                        boost=0.5
                    )
                )

    # 5. Sales Play Boost
    if criteria.get("sales_play"):
      from agents.skill_loader import split_sales_plays_safely

      sp_list = split_sales_plays_safely(criteria["sales_play"])
      if sp_list:
        sp_quoted = ", ".join([f'"{p}"' for p in sp_list])
        condition_boost_specs.append(
                    discoveryengine.SearchRequest.BoostSpec.ConditionBoostSpec(
                        condition=f'sales_play: ANY({sp_quoted})',
                        boost=0.4
                    )
                )

    # 6. Target Audience Boost
    if criteria.get("target_audience"):
      auds = criteria["target_audience"]
      aud_list = [auds] if isinstance(auds, str) else [str(a) for a in auds if a]
      if aud_list:
        aud_quoted = ", ".join([f'"{a}"' for a in aud_list])
        condition_boost_specs.append(
                    discoveryengine.SearchRequest.BoostSpec.ConditionBoostSpec(
                        condition=f'target_audience: ANY({aud_quoted})',
                        boost=0.3
                    )
                )

    # 7. Technical Maturity Boost
    if criteria.get("technical_maturity"):
      mat = criteria["technical_maturity"]
      mat_list = [mat] if isinstance(mat, str) else [str(m) for m in mat if m]
      if mat_list:
        mat_quoted = ", ".join([f'"{m}"' for m in mat_list])
        condition_boost_specs.append(
                    discoveryengine.SearchRequest.BoostSpec.ConditionBoostSpec(
                        condition=f'technical_maturity: ANY({mat_quoted})',
                        boost=0.3
                    )
                )

    if criteria.get("practice_area"):
      pa = criteria["practice_area"]
      if isinstance(pa, str):
        pa_list = [p.strip() for p in pa.split(",") if p.strip()]
      elif isinstance(pa, list):
        pa_list = [str(p).strip() for p in pa if p]
      else:
        pa_list = [str(pa).strip()]
      if pa_list:
        pa_quoted = ", ".join([f'"{p}"' for p in pa_list])
        condition_boost_specs.append(
                    discoveryengine.SearchRequest.BoostSpec.ConditionBoostSpec(
                        condition=f'practice_area: ANY({pa_quoted})',
                        boost=0.3
                    )
                )

    return discoveryengine.SearchRequest.BoostSpec(
            condition_boost_specs=condition_boost_specs
        )

  def search_reusable_slides(self, query: str, criteria: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    """Queries the Sales Play datastore using filters, boost rules, and targeted Foundation Anchor Deck recall."""
    filter_expr = self._build_filter_expression(criteria)
    boost_spec = self._build_boost_spec(criteria)

    results: List[Dict[str, Any]] = []
    seen_slide_ids = set()

    def _collect_from_response(resp, default_rel_boost: float = 0.0) -> None:
      for result in resp._response.results:
        doc_dict = json_format.MessageToDict(result.document._pb)
        struct_data = doc_dict.get("structData", {})
        s_id = (
            struct_data.get("slide_id")
            or (struct_data.get("slideIds") or [None])[0]
            or struct_data.get("slideId")
            or result.document.id
        )
        if s_id and s_id in seen_slide_ids:
          continue
        if s_id:
          seen_slide_ids.add(s_id)
        struct_data["_sim_score"] = max(
            getattr(result, "relevance", 0.0), default_rel_boost
        )
        results.append(struct_data)

    # 1. Targeted Foundation Anchor Deck Recall (guarantees candidate slides from the section's assigned
    # "Why Google for <Industry>" vertical_anchor deck or assigned Sales Play foundation deck are always retrieved)
    target_deck_ids = []
    sec_deck_id = criteria.get("section_anchor_deck_id")
    vert_deck_id = criteria.get("vertical_anchor_deck_id")
    if sec_deck_id and str(sec_deck_id).strip():
      target_deck_ids.append(str(sec_deck_id).strip())
    if (
        vert_deck_id
        and str(vert_deck_id).strip()
        and str(vert_deck_id).strip() not in target_deck_ids
    ):
      target_deck_ids.append(str(vert_deck_id).strip())

    if target_deck_ids:
      quoted_target_ids = ", ".join([f'"{d}"' for d in target_deck_ids])
      anchor_filter = (
          f"{filter_expr} AND deck_id: ANY({quoted_target_ids})"
          if filter_expr
          else f"deck_id: ANY({quoted_target_ids})"
      )
      try:
        anchor_req = discoveryengine.SearchRequest(
            serving_config=self.serving_config,
            query=query,
            filter=anchor_filter,
            boost_spec=boost_spec,
            page_size=max(6, limit),
        )
        anchor_resp = self.client.search(anchor_req)
        _collect_from_response(anchor_resp, default_rel_boost=0.88)
        recalled_decks = {
            r.get("deck_id") or r.get("deckId") for r in results
        }
        missing_decks = [d for d in target_deck_ids if d not in recalled_decks]
        if missing_decks:
          m_quoted = ", ".join([f'"{d}"' for d in missing_decks])
          fallback_filter = (
              f"{filter_expr} AND deck_id: ANY({m_quoted})"
              if filter_expr
              else f"deck_id: ANY({m_quoted})"
          )
          fallback_req = discoveryengine.SearchRequest(
              serving_config=self.serving_config,
              query="",
              filter=fallback_filter,
              page_size=max(6, len(missing_decks) * 4),
          )
          fallback_resp = self.client.search(fallback_req)
          _collect_from_response(fallback_resp, default_rel_boost=0.82)
      except Exception as anchor_err:
        print(f"[PoC Search] Targeted anchor deck recall notice: {anchor_err}")

    # 2. Broad Boosted Datastore Search
    request = discoveryengine.SearchRequest(
        serving_config=self.serving_config,
        query=query,
        filter=filter_expr,
        boost_spec=boost_spec,
        page_size=limit,
    )

    try:
      response = self.client.search(request)
      _collect_from_response(response)
      return results
    except Exception as e:
      print(f"[PoC Search] Error querying datastore: {e}")
      return results
