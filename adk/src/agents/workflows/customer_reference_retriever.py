"""Customer Reference Library Retriever for Google Slides Proof Points.

Queries the customer's configured Vertex AI Search (`cust_ref`) datastore or
engine for verified Google Slides customer case studies, enforces strict
Google Slides URL extraction, filters internal/orthogonal assets, and ranks
results across the 5 Value Pillars (Cost Reduction, Revenue Growth,
Operational Efficiency, Risk Mitigation, Strategic Agility).
"""

from __future__ import annotations

import html
import re
from typing import Any

from agents.workflows.slide_retriever_factory import BaseRetriever
from google.cloud import discoveryengine_v1 as discoveryengine
from google.protobuf.json_format import MessageToDict

# Default serving config or datastore ID placeholder (overridden by config.ini [reusable] cust_ref)
CUSTOMER_REF_SERVING_CONFIG = "your-customer-references-datastore-id"
CUSTOMER_REF_LIBRARY_SERVING_CONFIG = CUSTOMER_REF_SERVING_CONFIG

# Curated Master Customer Reference Slide Deck IDs (configure with your organization's case study decks)
CUSTOMER_REFERENCE_MASTER_DECK_IDS: tuple[str, ...] = (
    "SAMPLE_CUST_REF_MASTER_DECK_ID_000000001",
    "SAMPLE_CUST_REF_MASTER_DECK_ID_000000002",
    "SAMPLE_CUST_REF_MASTER_DECK_ID_000000003",
    "SAMPLE_CUST_REF_MASTER_DECK_ID_000000004",
)

# Exemplary public enterprise reference accounts by industry vertical
PRIORITY_CUSTOMERS_BY_INDUSTRY: dict[str, tuple[str, ...]] = {
    "retail": (
        "The Home Depot",
        "Target",
        "Walmart",
        "Carrefour",
        "LVMH",
        "Wayfair",
        "Etsy",
        "Sephora",
        "IKEA",
        "Walgreens",
    ),
    "financial services": (
        "HSBC",
        "Deutsche Bank",
        "Citigroup",
        "PayPal",
        "Commerzbank",
        "Goldman Sachs",
        "Charles Schwab",
        "Macquarie",
        "CME Group",
        "Discover",
    ),
    "healthcare": (
        "Mayo Clinic",
        "HCA Healthcare",
        "Bayer",
        "Pfizer",
        "Highmark Health",
        "Hackensack Meridian Health",
        "Moderna",
        "Quest Diagnostics",
    ),
    "media": (
        "Spotify",
        "Paramount",
        "Warner Bros. Discovery",
        "Canva",
        "FOX Sports",
        "New York Times",
    ),
    "manufacturing": (
        "Toyota",
        "Ford",
        "General Motors",
        "Continental",
        "Siemens",
        "Honeywell",
        "UPS",
        "FedEx",
    ),
    "telecommunications": (
        "Verizon",
        "Vodafone",
        "Bell Canada",
        "Orange",
        "T-Mobile",
        "AT&T",
    ),
    "games": (
        "Square Enix",
        "Niantic",
        "Roblox",
        "Ubisoft",
        "NetEase",
        "King",
    ),
}

_GSLIDES_URL_RE = re.compile(
    r"https?://docs\.google\.com/presentation/d/([a-zA-Z0-9_-]{20,})"
    r"(?:/[^\s\"'<>#?]*)?(?:\?[^\s\"'<>#]*)?(?:#slide=id\.([a-zA-Z0-9_.-]+))?",
    re.IGNORECASE,
)
_SLIDE_PARAM_RE = re.compile(
    r"(?:[?#&]slide=id\.)([a-zA-Z0-9_.-]+)", re.IGNORECASE
)


def _extract_gslides_url_and_ids(
    struct_data: dict[str, Any],
) -> tuple[str, str, str, bool] | None:
  """Extracts a verified Google Slides URL, deck_id, slide_id, and explicit-slide flag.

  Strictly rejects non-GSlides URLs (blogs, YouTube videos, Google Docs, PDFs).
  """
  if not isinstance(struct_data, dict):
    return None

  candidate_urls: list[str] = []
  for key in (
      "asset_url",
      "slide_url",
      "slideURL",
      "url",
      "link",
      "temp_url",
      "presentation_url",
  ):
    val = struct_data.get(key)
    if isinstance(val, str) and val.strip():
      candidate_urls.append(val.strip())
    elif isinstance(val, list):
      candidate_urls.extend(str(v).strip() for v in val if v)

  for list_key in ("asset_urls", "urls", "links"):
    val_list = struct_data.get(list_key)
    if isinstance(val_list, list):
      candidate_urls.extend(str(v).strip() for v in val_list if v)

  for raw_url in candidate_urls:
    m = _GSLIDES_URL_RE.search(raw_url)
    if not m:
      continue
    deck_id = m.group(1)
    slide_id = m.group(2) or ""
    if not slide_id:
      m_param = _SLIDE_PARAM_RE.search(raw_url)
      if m_param:
        slide_id = m_param.group(1)
    has_explicit_slide = bool(slide_id)
    if not slide_id:
      slide_id = str(
          struct_data.get("slide_id") or struct_data.get("slideId") or "p"
      ).strip()
    clean_url = (
        f"https://docs.google.com/presentation/d/{deck_id}/edit"
        f"#slide=id.{slide_id}"
    )
    return clean_url, deck_id, slide_id, has_explicit_slide

  # Fallback if explicit deck_id + slide_id fields are present
  deck_id = str(
      struct_data.get("deck_id") or struct_data.get("deckId") or ""
  ).strip()
  slide_id = str(
      struct_data.get("slide_id") or struct_data.get("slideId") or ""
  ).strip()
  if deck_id and len(deck_id) >= 20:
    has_explicit = bool(slide_id)
    slide_id = slide_id or "p"
    clean_url = (
        f"https://docs.google.com/presentation/d/{deck_id}/edit"
        f"#slide=id.{slide_id}"
    )
    return clean_url, deck_id, slide_id, has_explicit

  return None


def _clean_html_snippet(raw_text: str) -> str:
  text = html.unescape(str(raw_text or ""))
  text = re.sub(r"<[^>]+>", " ", text)
  return re.sub(r"\s+", " ", text).strip()


class CustomerReferenceRetriever(BaseRetriever):
  """Retrieves and ranks verified Google Slides customer case studies from Vertex AI Search."""

  def __init__(
      self,
      config: Any,
      datastore_id: str = "",
      ds_key: str = "cust_ref",
  ) -> None:
    super().__init__()
    self.config = config
    self.ds_key = ds_key
    self.project_id = (
        config["default"].get("project_name", "your-gcp-project-id")
        if config and "default" in config
        else "your-gcp-project-id"
    )
    if not datastore_id and config and "reusable" in config:
      datastore_id = config["reusable"].get(
          "cust_ref", CUSTOMER_REF_SERVING_CONFIG
      )
    self.datastore_id = datastore_id or CUSTOMER_REF_SERVING_CONFIG

  def _query_customer_ref_library_engine(
      self, query: str, page_size: int = 35
  ) -> list[dict[str, Any]]:
    """Queries the configured Vertex AI Search datastore/engine for customer reference documents."""
    try:
      client = discoveryengine.SearchServiceClient()
      if self.datastore_id.startswith("projects/"):
        serving_config = self.datastore_id
      else:
        serving_config = client.serving_config_path(
            project=self.project_id,
            location="global",
            data_store=self.datastore_id,
            serving_config="default_config",
        )
      request = discoveryengine.SearchRequest(
          serving_config=serving_config,
          query=query,
          page_size=page_size,
      )
      response = client.search(request)
      docs: list[dict[str, Any]] = []
      for res in response.results:
        try:
          docs.append(MessageToDict(res.document._pb))
        except Exception:
          docs.append({"document": MessageToDict(res.document._pb)})
      return docs
    except Exception as e:
      print(f"[CustomerReferenceRetriever] Search notice: {e}")
      return []

  def _query_customer_ref_engine(
      self, query: str, page_size: int = 35
  ) -> list[dict[str, Any]]:
    return self._query_customer_ref_library_engine(
        query=query, page_size=page_size
    )

  def search_slides(
      self,
      query: str,
      context: dict[str, Any] | None = None,
      limit: int = 10,
      industry: str = "",
      products: list[str] | None = None,
      customer_name: str = "",
  ) -> list[dict[str, Any]]:
    """Searches and ranks verified Google Slides customer case studies."""
    ctx = dict(context or {})
    target_ind = (
        industry
        or ctx.get("closest_industry")
        or ctx.get("industry")
        or ""
    ).strip()
    target_prods = list(products or ctx.get("product") or [])
    if isinstance(target_prods, str):
      target_prods = [target_prods]
    target_play = str(
        ctx.get("section_sales_play")
        or ctx.get("salesPlay")
        or ctx.get("sales_play")
        or ""
    ).lower()
    want_workspace = any(
        w in f"{query} {target_play} {' '.join(target_prods)}".lower()
        for w in ("google workspace", "gmail", "docs", "meet")
    ) and not any(
        w in f"{query} {target_play} {' '.join(target_prods)}".lower()
        for w in ("gemini enterprise", "bigquery", "agentic")
    )

    raw_results = self._query_customer_ref_library_engine(
        query, page_size=max(25, limit * 4)
    )
    ranked_slides: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    ind_low = target_ind.lower()
    priority_list: tuple[str, ...] = ()
    for k, custs in PRIORITY_CUSTOMERS_BY_INDUSTRY.items():
      if k in ind_low or ind_low in k:
        priority_list = custs
        break

    for item in raw_results:
      doc = item.get("document", item) if isinstance(item, dict) else {}
      struct = doc.get("structData", {}) or {}
      derived = doc.get("derivedStructData", {}) or {}

      extracted = _extract_gslides_url_and_ids(struct)
      if not extracted:
        continue
      clean_url, deck_id, slide_id, has_explicit_slide = extracted

      cust = str(
          struct.get("customer_name") or struct.get("customer") or ""
      ).strip()
      rec_ind = str(struct.get("industry") or "").strip()
      rec_sub_ind = str(struct.get("sub_industry") or "").strip()

      # Exclude internal self-references
      if any(
          internal_kw in f"{cust} {rec_ind}".lower()
          for internal_kw in (
              "alphabet internal",
              "google cloud",
              "google internal",
          )
      ):
        continue

      # Extract summary from extractive_answers or description
      answers = derived.get("extractive_answers", []) or []
      snippet_parts = [
          _clean_html_snippet(a.get("content", ""))
          for a in answers
          if isinstance(a, dict) and a.get("content")
      ]
      desc = _clean_html_snippet(
          struct.get("description")
          or struct.get("slide_summary")
          or struct.get("summary")
          or " ".join(snippet_parts)
      )

      rec_prods = (
          struct.get("google_products") or struct.get("google_product") or []
      )
      if isinstance(rec_prods, str):
        rec_prods = [rec_prods]
      prod_text = f"{' '.join(str(p) for p in rec_prods)} {desc}".lower()

      # Product disambiguation: filter Workspace-only references when pitching Cloud AI / Gemini Enterprise
      is_ws_only = (
          ("google workspace" in prod_text or "gmail" in prod_text)
          and "gemini enterprise" not in prod_text
          and "bigquery" not in prod_text
          and not struct.get("gemini_enterprise")
      )
      if is_ws_only and not want_workspace:
        continue

      dedup_key = f"{deck_id}_{slide_id}"
      if dedup_key in seen_keys:
        continue
      seen_keys.add(dedup_key)

      # Multi-factor relevance scoring
      score = 0.55
      if has_explicit_slide:
        score += 0.08
      if deck_id in CUSTOMER_REFERENCE_MASTER_DECK_IDS:
        score += 0.12
      if cust and any(p.lower() in cust.lower() for p in priority_list):
        score += 0.14
      if customer_name and customer_name.lower() in cust.lower():
        score += 0.20

      if target_ind:
        if ind_low in rec_ind.lower() or rec_ind.lower() in ind_low:
          score += 0.12
        elif rec_ind:
          score -= 0.18

      for tp in target_prods:
        if tp and tp.lower() in prod_text:
          score += 0.06

      if struct.get("quantifiable_business_impact") or re.search(
          r"\b\d+(?:\.\d+)?%", desc
      ):
        score += 0.06

      final_score = round(max(0.1, min(0.99, score)), 4)
      title = (
          struct.get("slide_title")
          or struct.get("title")
          or (
              f"{cust} — Customer Case Study"
              if cust
              else "Customer Case Study"
          )
      )

      ranked_slides.append({
          "deck_id": deck_id,
          "deckId": deck_id,
          "slide_id": slide_id,
          "slideId": slide_id,
          "slide_url": clean_url,
          "slideURL": clean_url,
          "temp_url": clean_url,
          "title": title,
          "name": title,
          "customer": cust,
          "customer_name": cust,
          "industry": rec_ind,
          "sub_industry": rec_sub_ind,
          "product": rec_prods,
          "google_product": rec_prods,
          "summary": desc,
          "content": desc,
          "desc": desc,
          "slide_job": "Proof_Points",
          "cvi_cluster": "Impact",
          "is_proof_point": True,
          "is_cust_ref": True,
          "_source_datastore_key": "cust_ref",
          "_source_library": "customer_ref_gslides",
          "_sim_score": final_score,
          "sim_score": final_score,
      })

    ranked_slides.sort(key=lambda x: x.get("_sim_score", 0.0), reverse=True)
    return ranked_slides[:limit]


# Backward-compatible class alias
NewLibraryCustomerReferenceRetriever = CustomerReferenceRetriever
