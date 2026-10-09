"""Gemini Enterprise A2UI Card Generator for Slide Search (Side Panel).

Implements Workflow 2:
- Searches CloudHub and reusable slide library
- Renders slide thumbnails and filmstrip grid in the UCS Canvas Side Panel
- Provides 1-click insertion action to append library slides into active decks
"""

import ast
import re
from typing import Any, Dict, List, Optional, Tuple

try:
  from ge import a2ui
except ImportError:
  from src.ge import a2ui  # pylint: disable=g-import-not-at-top

_AMBIGUOUS_LOWERCASE_CUSTOMERS = {
    "time",
    "one",
    "discover",
    "target",
    "box",
    "block",
    "square",
    "next",
    "total",
    "gap",
    "orange",
    "shell",
    "match",
    "inge",
    "coherent",
    "carta",
}

_NON_CUSTOMER_TOKENS = {
    "the",
    "this",
    "that",
    "these",
    "those",
    "google",
    "google cloud",
    "gemini",
    "gemini enterprise",
    "customers",
    "customer",
    "organizations",
    "organization",
    "enterprises",
    "enterprise",
    "companies",
    "company",
    "teams",
    "users",
    "clients",
    "leaders",
    "other",
    "none",
    "null",
    "general",
    "all",
    "n/a",
    "reusable slide",
    "customer reference",
    "verified customer reference",
    "verified customer proof point",
}

_GENERIC_DECK_TITLES = {
    "",
    "cloudhub asset library",
    "cloudhub reusable slide library",
    "2026 consolidated customer reference library",
    "reusable slide library",
    "untitled deck",
    "untitled presentation",
}


def sanitize_search_text(text: Any) -> str:
  """Cleans slide description text and enforces Enterprise-Brand-Unification terminology."""
  s = str(text or "").strip()
  if not s:
    return ""
  s = re.sub(
      r"\bGemini\s+Enterprise\s+and\s+an?\s+Agent\s+Platform\b",
      "Gemini Enterprise",
      s,
      flags=re.IGNORECASE,
  )
  s = re.sub(
      r"\bGemini\s+Enterprise\s+Agent\s+Platform\b|\bGEAP\b",
      "Gemini Enterprise",
      s,
      flags=re.IGNORECASE,
  )
  s = re.sub(
      r"\b(?:the\s+)?Gemini\s+Enterprise\s+(?:platform|app|application)\b",
      "Gemini Enterprise",
      s,
      flags=re.IGNORECASE,
  )
  s = re.sub(
      r"\bVertex\s+AI\s+(?:Agent\s+Builder|Search(?:\s+and\s+Conversation)?|Platform)\b",
      "Gemini Enterprise",
      s,
      flags=re.IGNORECASE,
  )
  s = re.sub(r"\bVertex\s+AI\b|\bVertex\b", "Gemini Enterprise", s)
  s = re.sub(
      r"\bPowered\s+by\s+Gemini(?!\s+Enterprise)\b",
      "Built with Gemini",
      s,
      flags=re.IGNORECASE,
  )
  s = re.sub(r"\s+", " ", s).strip()
  return s


def format_industry_label(raw_ind: Any) -> str:
  """Formats industry values cleanly, unpacking Python lists or stringified lists."""
  if raw_ind is None:
    return ""
  items: List[str] = []
  if isinstance(raw_ind, (list, tuple, set)):
    items = [str(x).strip() for x in raw_ind if x is not None]
  else:
    s = str(raw_ind).strip()
    if s.startswith("[") and s.endswith("]"):
      try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, (list, tuple, set)):
          items = [str(x).strip() for x in parsed if x is not None]
      except Exception:
        inner = s[1:-1].strip()
        items = [
            part.strip().strip("'\"")
            for part in inner.split(",")
            if part.strip()
        ]
    elif "," in s:
      items = [
          part.strip().strip("'\"") for part in s.split(",") if part.strip()
      ]
    elif s:
      items = [s.strip("'\"")]

  cleaned: List[str] = []
  seen = set()
  for it in items:
    val = it.strip().strip("'\"")
    low = val.lower()
    if not val or low in {"other", "none", "null", "all", "general", "n/a"}:
      continue
    if low not in seen:
      seen.add(low)
      cleaned.append(val)

  if not cleaned:
    return ""
  if len(cleaned) >= 4:
    return "Cross-Industry"
  return ", ".join(cleaned)


def format_slide_job_label(raw_job: Any) -> str:
  """Formats slide_job identifiers (e.g. 'Proof_Points' -> 'Proof Points')."""
  s = str(raw_job or "").strip()
  if not s:
    return ""
  clean = s.replace("_", " ").replace("-", " ").strip()
  return re.sub(r"\s+", " ", clean)


def extract_customer_from_summary(summary: str) -> str:
  """Extracts an explicit customer name from slide summary text when present."""
  if not summary:
    return ""
  patterns = [
      r"(?:customer\s+success\s+story|case\s+study|customer\s+reference|customer\s+story|success\s+story|proof\s+point)\s+(?:for|on|featuring|highlighting|about|with)\s+([A-Z0-9][A-Za-z0-9&.\-\s]{1,34}?)(?:,|\.|;|\s+—|\s+-|\s+(?:detailing|showcasing|highlighting|demonstrating|illustrating|showing|who|which|where|how|a\s+|an\s+|in\s+|to\s+|using|leveraging))",
      r"\bhow\s+([A-Z][A-Za-z0-9&.\-]{1,24}(?:\s+[A-Z][A-Za-z0-9&.\-]{1,24}){0,2})\s+(?:used|leveraged|adopted|deployed|implemented|built|transformed|migrated|partnered|achieved|improved|reduced|automated|scaled|streamlined)\b",
      r"^(?:In\s+this\s+slide,\s+)?([A-Z][A-Za-z0-9&.\-]{1,24}(?:\s+[A-Z][A-Za-z0-9&.\-]{1,24}){0,2})\s+(?:used|leveraged|adopted|deployed|implemented|achieved|improved|reduced|automated|migrated)\b",
  ]
  for pat in patterns:
    m = re.search(pat, summary)
    if m:
      cand = m.group(1).strip().strip(".,;:-—")
      if cand and cand.lower() not in _NON_CUSTOMER_TOKENS:
        return cand
  return ""


def resolve_clean_customer(
    item: Dict[str, Any], summary: str, raw_title: str = ""
) -> str:
  """Resolves customer name while filtering out false-positive common word matches."""
  raw_cust = str(
      item.get("customer") or item.get("customer_name") or ""
  ).strip()
  if isinstance(item.get("customer"), list):
    cust_list = [
        str(c).strip()
        for c in item.get("customer", [])
        if c and str(c).strip().lower() not in _NON_CUSTOMER_TOKENS
    ]
    raw_cust = cust_list[0] if cust_list else ""

  extracted = extract_customer_from_summary(summary)
  if raw_cust.lower() in _NON_CUSTOMER_TOKENS or not raw_cust:
    return extracted

  if raw_cust.lower() in _AMBIGUOUS_LOWERCASE_CUSTOMERS:
    if extracted and extracted.lower() != raw_cust.lower():
      return extracted
    # Require a capitalized occurrence that is not just sentence-start or common noun
    cap_word = raw_cust[0].upper() + raw_cust[1:]
    if not re.search(
        rf"(?<!^)\b{re.escape(cap_word)}\b", f"{raw_title} {summary}"
    ):
      return extracted

  return raw_cust


def is_deck_like_title(title: str, source_deck_title: str = "") -> bool:
  """Returns True when a candidate slide title is actually a deck title or generic placeholder."""
  t = str(title or "").strip()
  if not t:
    return True
  low = t.lower()
  if low in {
      "untitled slide",
      "reusable slide",
      "verified customer proof point",
      "verified customer reference",
      "customer reference",
      "slide",
  } or re.match(r"^(?:reference\s+)?slide\s+\d+$", low):
    return True
  if source_deck_title and low == source_deck_title.strip().lower():
    return True
  if re.search(r"\[go/[^\]]+\]", t, re.IGNORECASE):
    return True
  if re.search(r"\([a-z]{2}(?:-[a-z]{2})?\)\s*$", t, re.IGNORECASE):
    return True
  if re.match(r"^why\s+google\s+cloud\b", t, re.IGNORECASE):
    return True
  if re.search(
      r"\b(?:first\s+call\s+deck|master\s+deck|pitch\s+deck|template\s+library|customer\s+reference\s+library|consolidated\s+customer\s+reference|sales\s+play\s+deck)\b",
      t,
      re.IGNORECASE,
  ):
    return True
  return False


def clean_deck_title_for_display(raw_deck_title: str) -> str:
  """Cleans a source deck title so it renders cleanly inside a Markdown link [Deck Title](url)."""
  s = str(raw_deck_title or "").strip()
  if not s:
    return ""
  # Replace square brackets with parentheses so Markdown link [label](url) never breaks
  s = s.replace("[", "(").replace("]", ")")
  s = re.sub(r"\s+", " ", s).strip()
  return s


def _synthesize_headline_from_summary(
    summary: str, customer: str, core_topics: List[str], solution: str = ""
) -> str:
  """Synthesizes a concise, specific slide title from slide summary and metadata."""
  clean_topics = [
      str(t).strip()
      for t in core_topics or []
      if t
      and str(t).strip().lower()
      not in _NON_CUSTOMER_TOKENS | {customer.lower() if customer else ""}
  ]
  if clean_topics:
    primary_topic = clean_topics[0]
    if len(primary_topic) <= 55:
      return f"{customer} — {primary_topic}" if customer else primary_topic

  if summary:
    # Look for a concrete outcome or action clause (e.g., "to improve advertising campaign resolution time by 200%")
    m_outcome = re.search(
        r"\bto\s+((?:improve|increase|reduce|accelerate|automate|streamline|transform|modernize|scale|enhance|achieve|save|build|deliver|optimize|unify|enable|boost|drive|lower)\s+[^.,;]{8,62})",
        summary,
        flags=re.IGNORECASE,
    )
    if m_outcome:
      phrase = m_outcome.group(1).strip()
      phrase = re.sub(
          r"\s+(?:and|or|with|by|for|in|on|at|to|from|a|an|the)$",
          "",
          phrase,
          flags=re.IGNORECASE,
      ).strip()
      if phrase:
        headline = phrase[0].upper() + phrase[1:]
        return f"{customer} — {headline}" if customer else headline

    # Strip boilerplate intro phrases ("The slide showcases...", "This slide presents...")
    stripped = re.sub(
        r"^(?:the\s+slide|this\s+slide)\s+(?:showcases|presents|illustrates|details|highlights|demonstrates|describes|outlines|covers|explains|provides)\s+",
        "",
        summary,
        flags=re.IGNORECASE,
    ).strip()
    stripped = re.sub(
        r"^(?:a\s+|an\s+)?(?:customer\s+success\s+story|case\s+study|customer\s+reference|success\s+story|overview|summary)\s+(?:for|of|on|about|featuring)\s+",
        "",
        stripped,
        flags=re.IGNORECASE,
    ).strip()
    if customer and stripped.lower().startswith(customer.lower()):
      stripped = stripped[len(customer) :].lstrip(" ,.:;-—")
    stripped = re.sub(
        r"^(?:detailing|showcasing|highlighting|demonstrating|showing|explaining)\s+how\s+(?:they|the\s+company|the\s+customer|[A-Za-z0-9&.\-\s]{1,25}?)\s+",
        "",
        stripped,
        flags=re.IGNORECASE,
    ).strip()
    first_clause = re.split(
        r"[.;]|,\s+(?:achieving|resulting|saving|and\s+)", stripped
    )[0].strip()
    if 8 <= len(first_clause) <= 68:
      headline = first_clause[0].upper() + first_clause[1:]
      return f"{customer} — {headline}" if customer else headline
    elif len(first_clause) > 68:
      words = first_clause[:65].rsplit(" ", 1)[0].strip(" ,;:-—")
      if words:
        headline = words[0].upper() + words[1:]
        return f"{customer} — {headline}" if customer else headline

  if customer and solution:
    return f"{customer} — {solution}"
  if customer:
    return f"{customer} — Customer Success Story"
  if solution:
    return solution
  return ""


def derive_slide_and_deck_title(
    item: Dict[str, Any],
    idx: int = 1,
    customer: str = "",
    summary: str = "",
) -> Tuple[str, str]:
  """Resolves a distinct (slide_title, source_deck_title) pair from a search result item."""
  raw_deck = str(
      item.get("source_deck_title")
      or item.get("deck_title")
      or item.get("deckTitle")
      or ""
  ).strip()
  raw_slide = str(
      item.get("slide_title")
      or item.get("slideTitle")
      or item.get("original_title")
      or ""
  ).strip()
  raw_title = str(item.get("title") or item.get("name") or "").strip()

  # Rescue actual deck title if raw_deck is empty/generic and raw_title holds a deck title
  if raw_deck.lower() in _GENERIC_DECK_TITLES:
    if raw_title and is_deck_like_title(raw_title):
      raw_deck = raw_title
    elif raw_slide and is_deck_like_title(raw_slide):
      raw_deck = raw_slide

  clean_deck = clean_deck_title_for_display(raw_deck)
  if not clean_deck:
    clean_deck = "CloudHub Reusable Slide Library"

  # Pick genuine slide title if available
  slide_title = ""
  for cand in (raw_slide, raw_title):
    if cand and not is_deck_like_title(cand, raw_deck):
      slide_title = sanitize_search_text(cand)
      break

  if not slide_title:
    core_topics = item.get("core_topics") or []
    if isinstance(core_topics, str):
      core_topics = [core_topics]
    solution = str(
        item.get("solution")
        or item.get("sales_play")
        or item.get("salesPlay")
        or ""
    ).strip()
    slide_title = _synthesize_headline_from_summary(
        summary=summary,
        customer=customer,
        core_topics=core_topics,
        solution=solution,
    )

  if not slide_title:
    slide_title = (
        f"{customer} — Verified Reference Slide"
        if customer
        else f"Reference Slide {idx}"
    )

  return slide_title, clean_deck


def normalize_slide_search_item(
    item: Dict[str, Any], idx: int = 1, default_slide_job: str = ""
) -> Dict[str, Any]:
  """Normalizes a slide search result dict with clean slide title, deck title, customer, industry, and full summary."""
  url_slide_id = ""
  url_pres_id = ""
  for url_key in ("slideURL", "view_url", "slide_url", "link"):
    raw_url = str(item.get(url_key) or "")
    if not raw_url:
      continue
    if not url_slide_id:
      m_slide = re.search(r"#slide=id\.([A-Za-z0-9_\-.]+)", raw_url)
      if m_slide:
        url_slide_id = m_slide.group(1)
    if not url_pres_id:
      m_pres = re.search(r"/presentation/d/([a-zA-Z0-9_-]{20,})", raw_url)
      if m_pres:
        url_pres_id = m_pres.group(1)
  slide_id = str(
      item.get("slide_id")
      or item.get("slideId")
      or item.get("id")
      or url_slide_id
      or f"slide_{idx}"
  ).strip()
  pres_id = str(
      item.get("presentation_id")
      or item.get("deck_id")
      or item.get("deckId")
      or url_pres_id
      or ""
  ).strip()
  raw_summary = (
      item.get("summary")
      or item.get("description")
      or item.get("slide_summary")
      or item.get("content")
      or item.get("original_content")
      or item.get("group_summary")
      or ""
  )
  summary = sanitize_search_text(raw_summary)
  raw_title = str(
      item.get("slide_title")
      or item.get("slideTitle")
      or item.get("title")
      or item.get("name")
      or ""
  ).strip()
  customer = resolve_clean_customer(item, summary, raw_title)
  industry = format_industry_label(item.get("industry"))
  raw_job = (
      item.get("slide_job")
      or item.get("slideJob")
      or default_slide_job
      or "Proof_Points"
  )
  item_job = str(raw_job).strip()
  item_job_label = format_slide_job_label(item_job)
  slide_title, deck_title = derive_slide_and_deck_title(
      item=item, idx=idx, customer=customer, summary=summary
  )
  view_url = str(
      item.get("view_url")
      or item.get("slideURL")
      or item.get("slide_url")
      or item.get("temp_url")
      or (
          f"https://docs.google.com/presentation/d/{pres_id}/edit#slide=id.{slide_id}"
          if pres_id and slide_id
          else (
              f"https://docs.google.com/presentation/d/{pres_id}/edit"
              if pres_id
              else ""
          )
      )
  ).strip()

  if not summary:
    summary = (
        f"Verified Google Cloud reference slide for {customer}"
        f" ({industry or item_job_label})."
        if customer
        else f"Verified Google Cloud reusable slide from {deck_title}."
    )

  return {
      "slide_id": slide_id,
      "pres_id": pres_id,
      "title": slide_title,
      "source_deck_title": deck_title,
      "customer": customer,
      "industry": industry,
      "slide_job": item_job,
      "slide_job_label": item_job_label,
      "summary": summary,
      "view_url": view_url,
  }


def create_slide_search_panel_card(
    search_query: str = "",
    results: Optional[List[Dict[str, Any]]] = None,
    target_presentation_id: str = "",
    target_slide_position: int = -1,
    query: str = "",
    slide_job: str = "",
) -> Dict[str, Any]:
  """Builds the side-panel A2UI card rendering search results as slide tiles."""
  effective_query = (
      search_query or query or "Customer References & Reusable Slides"
  )
  items_list = results or []
  slide_tiles = []

  for idx, item in enumerate(items_list, 1):
    norm = normalize_slide_search_item(
        item=item, idx=idx, default_slide_job=slide_job or "Solution_Overview"
    )
    slide_id = norm["slide_id"]
    pres_id = norm["pres_id"]
    title = norm["title"]
    category = (
        norm["customer"]
        or norm["industry"]
        or str(item.get("category") or item.get("slide_category") or "General")
    )
    item_slide_job = norm["slide_job"]
    thumbnail_url = (
        item.get("thumbnail_url")
        or item.get("image_url")
        or norm["view_url"]
        or ""
    )
    source_deck = norm["source_deck_title"]
    summary = norm["summary"]

    tile = {
        "id": f"slide_tile_{slide_id}",
        "type": "slide_preview_tile",
        "title": title,
        "category": category,
        "slide_job": item_slide_job,
        "thumbnail_url": thumbnail_url,
        "source": source_deck,
        "summary": summary,
        "actions": [{
            "id": f"btn_insert_{slide_id}",
            "label": "➕ Insert Slide",
            "style": "primary",
            "action": {
                "type": "a2ui_action",
                "actionName": "insert_library_slide",
                "parameters": {
                    "template_slide_id": slide_id,
                    "source_presentation_id": pres_id,
                    "target_presentation_id": target_presentation_id,
                    "target_position": target_slide_position,
                    "slide_job": item_slide_job,
                    "slide_title": title,
                },
            },
        }],
    }
    slide_tiles.append(tile)

  return {
      "type": "card",
      "surface": "canvas_side_panel",
      "title": f"🔍 Slide Library Results ({len(items_list)})",
      "subtitle": f'Query: "{effective_query}"',
      "metadata": {
          "mimeType": a2ui.A2UI_MIME_TYPE,
          "canvas_panel": "UCS_SIDE_PANEL",
      },
      "sections": [{
          "type": "tile_grid",
          "columns": 1,
          "items": slide_tiles,
      }],
  }


def create_a2ui_v09_search_messages(
    search_query: str = "",
    results: Optional[List[Dict[str, Any]]] = None,
    target_presentation_id: str = "",
    slide_job: str = "",
    customer_name: str = "",
    surface_id: str = "pitchgen-slide-search",
) -> List[Dict[str, Any]]:
  """Generates canonical A2UI v0.9 messages for interactive Slide & Customer Reference Search."""
  items_list = results or []
  has_results = len(items_list) > 0
  effective_query = search_query or ""

  font_sans = "'Google Sans', 'Google Sans Text', Roboto, Arial, sans-serif"

  slide_job_options = [
      {"label": "All Slide Types & Categories", "value": ""},
      {
          "label": "Customer Proof Points & Case Studies",
          "value": "Proof_Points",
      },
      {"label": "Solution Overview & Product", "value": "Solution_Overview"},
      {"label": "Current State & Industry Trends", "value": "Current_State"},
      {"label": "Business Value & ROI", "value": "Business_Value"},
      {"label": "Architecture, Security & Governance", "value": "Architecture"},
      {"label": "Path to Production & Roadmap", "value": "Path_to_Prod"},
  ]

  header_title_text = (
      f"🔍 CloudHub & Customer Reference Library ({len(items_list)} Matches)"
      if has_results
      else "🔍 Search CloudHub & Customer Reference Slides"
  )
  if has_results:
    subtitle_parts = [f'Query: "{effective_query or "Customer References"}"']
    if customer_name:
      subtitle_parts.append(f"Account: {customer_name}")
    if slide_job:
      subtitle_parts.append(f"Filter: {slide_job}")
    header_subtitle_text = " • ".join(subtitle_parts)
  else:
    header_subtitle_text = (
        "Search verified Google Cloud customer case studies, reusable sales"
        " play slides, and architecture templates."
    )

  components: List[Dict[str, Any]] = []
  root_children: List[str] = [
      "header-col",
      "divider-top",
      "input-search-query",
      "search-filters-row",
      "btn-run-search",
  ]

  components.extend([
      {
          "id": "header-col",
          "component": "MaterialColumn",
          "style": {"gap": "4px"},
          "children": ["title-txt", "subtitle-txt"],
      },
      {
          "id": "title-txt",
          "component": "MaterialText",
          "text": header_title_text,
          "usageHint": "h3",
          "style": {
              "fontFamily": font_sans,
              "fontSize": "18px",
              "fontWeight": "600",
              "color": "var(--mat-sys-on-surface, #1f1f1f)",
              "margin": "0",
          },
      },
      {
          "id": "subtitle-txt",
          "component": "MaterialText",
          "text": header_subtitle_text,
          "usageHint": "body",
          "style": {
              "fontFamily": font_sans,
              "fontSize": "13px",
              "color": "var(--mat-sys-on-surface-variant, #444746)",
              "margin": "0",
          },
      },
      {
          "id": "divider-top",
          "component": "MaterialDivider",
      },
      {
          "id": "input-search-query",
          "component": "MaterialInput",
          "label": "Search Query (Topic, Customer Story, Industry, or Product)",
          "placeholder": (
              "e.g., Retail Gemini Enterprise proof points, Zero Trust security"
          ),
          "value": {"path": "/search/query"},
      },
      {
          "id": "search-filters-row",
          "component": "MaterialRow",
          "style": {"gap": "12px", "width": "100%"},
          "children": ["select-slide-job", "input-target-deck"],
      },
      {
          "id": "select-slide-job",
          "component": "MaterialSelect",
          "label": "Slide Category / Job Filter",
          "value": {"path": "/search/slide_job"},
          "options": slide_job_options,
          "weight": 1,
      },
      {
          "id": "input-target-deck",
          "component": "MaterialInput",
          "label": "Target Google Slides Deck ID / URL (Optional)",
          "placeholder": "Paste deck URL/ID for 1-click slide insertion",
          "value": {"path": "/search/target_presentation_id"},
          "weight": 1,
      },
      {
          "id": "btn-run-search",
          "component": "MaterialButton",
          "label": "🔍 Search Slide Library",
          "variant": "flat",
          "style": {
              "fontFamily": font_sans,
              "fontWeight": "500",
              "borderRadius": "999px",
          },
          "action": {
              "event": {
                  "name": "search_slides",
                  "context": {
                      "search_query": {"path": "/search/query"},
                      "slide_job": {"path": "/search/slide_job"},
                      "target_presentation_id": {
                          "path": "/search/target_presentation_id"
                      },
                      "customer_name": customer_name,
                  },
              }
          },
      },
  ])

  if has_results:
    div_results_id = "divider-results"
    root_children.append(div_results_id)
    components.append({
        "id": div_results_id,
        "component": "MaterialDivider",
    })

  for idx, item in enumerate(items_list[:8], 1):
    norm = normalize_slide_search_item(
        item=item, idx=idx, default_slide_job=slide_job or "Proof_Points"
    )
    slide_id = norm["slide_id"]
    pres_id = norm["pres_id"]
    title = norm["title"]
    deck_title = norm["source_deck_title"]
    customer = norm["customer"]
    industry = norm["industry"]
    item_job = norm["slide_job"]
    item_job_label = norm["slide_job_label"]
    summary = norm["summary"]
    view_url = norm["view_url"]

    row_id = f"res-card-{idx}"
    title_id = f"res-title-{idx}"
    meta_id = f"res-meta-{idx}"
    desc_id = f"res-desc-{idx}"
    action_row_id = f"res-actions-{idx}"
    btn_insert_id = f"btn-insert-{idx}"

    meta_parts = [p for p in [customer, industry, item_job_label] if p]
    meta_str = (
        " • ".join(meta_parts) if meta_parts else "Verified Reusable Asset"
    )
    if view_url:
      meta_str += f" • Source: [{deck_title}]({view_url})"
    elif deck_title:
      meta_str += f" • Source: {deck_title}"

    root_children.append(row_id)
    components.extend([
        {
            "id": row_id,
            "component": "MaterialColumn",
            "style": {
                "gap": "6px",
                "padding": "14px",
                "borderRadius": "12px",
                "backgroundColor": (
                    "var(--mat-sys-surface-container-low, #f8fafd)"
                ),
                "border": "1px solid var(--mat-sys-outline-variant, #dadce0)",
            },
            "children": [title_id, meta_id, desc_id, action_row_id],
        },
        {
            "id": title_id,
            "component": "MaterialText",
            "text": f"{idx}. {title}",
            "usageHint": "h4",
            "style": {
                "fontFamily": font_sans,
                "fontSize": "15px",
                "fontWeight": "600",
                "color": "var(--mat-sys-on-surface, #1f1f1f)",
                "margin": "0",
            },
        },
        {
            "id": meta_id,
            "component": "MaterialText",
            "text": meta_str,
            "usageHint": "caption",
            "style": {
                "fontFamily": font_sans,
                "fontSize": "12px",
                "color": "var(--mat-sys-primary, #0b57d0)",
                "margin": "0",
            },
        },
        {
            "id": desc_id,
            "component": "MaterialText",
            "text": (
                summary or "Verified Google Cloud customer reference slide."
            ),
            "usageHint": "body",
            "style": {
                "fontFamily": font_sans,
                "fontSize": "13px",
                "lineHeight": "1.45",
                "color": "var(--mat-sys-on-surface-variant, #444746)",
                "margin": "0",
            },
        },
        {
            "id": action_row_id,
            "component": "MaterialRow",
            "style": {"gap": "8px", "marginTop": "4px"},
            "children": [btn_insert_id],
        },
        {
            "id": btn_insert_id,
            "component": "MaterialButton",
            "label": "➕ Insert Slide into Active Deck",
            "variant": "stroked",
            "style": {
                "fontFamily": font_sans,
                "fontSize": "12.5px",
                "fontWeight": "500",
                "borderRadius": "999px",
            },
            "action": {
                "event": {
                    "name": "insert_library_slide",
                    "context": {
                        "template_slide_id": slide_id,
                        "source_presentation_id": pres_id,
                        "target_presentation_id": {
                            "path": "/search/target_presentation_id"
                        },
                        "slide_job": item_job,
                        "slide_title": title,
                        "source_deck_title": deck_title,
                        "view_url": view_url,
                    },
                }
            },
        },
    ])

  components.insert(
      0,
      {
          "id": "root",
          "component": "MaterialCard",
          "appearance": "outlined",
          "style": {
              "padding": "24px",
              "borderRadius": "16px",
              "backgroundColor": "var(--mat-sys-surface, #ffffff)",
              "border": "1px solid var(--mat-sys-outline-variant, #dadce0)",
          },
          "children": ["main-col"],
      },
  )
  components.insert(
      1,
      {
          "id": "main-col",
          "component": "MaterialColumn",
          "style": {"gap": "14px"},
          "children": root_children,
      },
  )

  return [
      {
          "version": "v0.9",
          "createSurface": {
              "surfaceId": surface_id,
              "catalogId": a2ui.A2UI_MATERIAL_CATALOG_ID,
          },
      },
      {
          "version": "v0.9",
          "updateDataModel": {
              "surfaceId": surface_id,
              "value": {
                  "search_query": effective_query,
                  "slide_job": slide_job or "",
                  "target_presentation_id": target_presentation_id or "",
                  "search": {
                      "query": effective_query,
                      "slide_job": slide_job or "",
                      "target_presentation_id": target_presentation_id or "",
                  },
              },
          },
      },
      {
          "version": "v0.9",
          "updateComponents": {
              "surfaceId": surface_id,
              "components": components,
          },
      },
  ]


SEARCH_RESULTS_SURFACE_PREFIX = "pitchgen-search-results"
SEARCH_RESULTS_MAX_TILES = 8

SEARCH_SLIDE_ICON_URL = (
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg'"
    " width='40' height='40' viewBox='0 0 72 72'><rect x='0' y='0'"
    " width='72' height='72' rx='16' fill='rgb(232,240,254)'/><circle"
    " cx='32.5' cy='32.5' r='10.5' fill='none' stroke='rgb(26,115,232)'"
    " stroke-width='5.2'/><line x1='40.5' y1='40.5' x2='50.5' y2='50.5'"
    " stroke='rgb(26,115,232)' stroke-width='5.2'"
    " stroke-linecap='round'/></svg>"
)

_SEARCH_SLIDE_JOB_OPTIONS = [
    {"label": "All Slide Types & Categories", "value": ""},
    {
        "label": "Customer Proof Points & Case Studies",
        "value": "Proof_Points",
    },
    {"label": "Solution Overview & Product", "value": "Solution_Overview"},
    {"label": "Current State & Industry Trends", "value": "Current_State"},
    {"label": "Business Value & ROI", "value": "Business_Value"},
    {"label": "Architecture, Security & Governance", "value": "Architecture"},
    {"label": "Path to Production & Roadmap", "value": "Path_to_Prod"},
]


def _usable_thumbnail_url(raw: Any) -> str:
  """Returns raw if it is a real https/data image URL (never /export or /edit links)."""
  s = str(raw or "").strip()
  if not s:
    return ""
  if s.startswith("data:image/"):
    return s
  if not s.startswith("https://"):
    return ""
  if "/export" in s or "exportFormat=" in s:
    return ""
  if "docs.google.com/presentation/" in s:
    return ""
  return s


def create_a2ui_v09_search_form_messages(
    search_query: str = "",
    target_presentation_id: str = "",
    slide_job: str = "",
    customer_name: str = "",
    surface_id: str = "pitchgen-slide-search",
    **kwargs: Any,
) -> List[Dict[str, Any]]:
  """Builds the Slide Search input form (Material catalog) ported from A2UI-GE.

  Emits only the form. Submitting fires the `search_slides` event, which
  `enterprise_before_model_callback` routes deterministically to
  `enterprise_search_slides_skill`.
  """
  del kwargs
  font_sans = "'Google Sans', 'Google Sans Text', Roboto, Arial, sans-serif"
  effective_query = search_query or ""
  subtitle = (
      "Search and preview brand-vetted reusable slides and verified customer"
      " references from CloudHub by topic, customer story, or architecture."
  )
  if customer_name:
    subtitle += f" Account: {customer_name}."

  components: List[Dict[str, Any]] = [
      {
          "id": "root",
          "component": "MaterialCard",
          "appearance": "outlined",
          "style": {
              "padding": "24px",
              "borderRadius": "16px",
              "backgroundColor": "var(--mat-sys-surface, #ffffff)",
              "border": "1px solid var(--mat-sys-outline-variant, #dadce0)",
          },
          "children": ["main_column"],
      },
      {
          "id": "main_column",
          "component": "MaterialColumn",
          "style": {"gap": "14px"},
          "children": [
              "header_row",
              "header_divider",
              "input-search-query",
              "search-filters-row",
              "btn-run-search",
          ],
      },
      {
          "id": "header_row",
          "component": "MaterialRow",
          "justify": "start",
          "align": "center",
          "style": {"gap": "12px", "alignItems": "center"},
          "children": ["header_icon", "header_text_col"],
      },
      a2ui.material_header_icon("header_icon", "manage_search"),
      {
          "id": "header_text_col",
          "component": "MaterialColumn",
          "style": {"gap": "4px"},
          "children": ["title-txt", "subtitle-txt"],
      },
      {
          "id": "title-txt",
          "component": "MaterialText",
          "text": "Search Slide Library",
          "usageHint": "h3",
          "style": {
              "fontFamily": font_sans,
              "fontSize": "18px",
              "fontWeight": "600",
              "color": "var(--mat-sys-on-surface, #1f1f1f)",
              "margin": "0",
          },
      },
      {
          "id": "subtitle-txt",
          "component": "MaterialText",
          "text": subtitle,
          "usageHint": "body",
          "style": {
              "fontFamily": font_sans,
              "fontSize": "13px",
              "color": "var(--mat-sys-on-surface-variant, #444746)",
              "margin": "0",
          },
      },
      {
          "id": "header_divider",
          "component": "MaterialDivider",
      },
      {
          "id": "input-search-query",
          "component": "MaterialInput",
          "label": "Describe the slide you need *",
          "placeholder": (
              "e.g., Retail Gemini Enterprise proof points, BigQuery ROI,"
              " Zero Trust architecture"
          ),
          "value": {"path": "/search/query"},
      },
      {
          "id": "search-filters-row",
          "component": "MaterialRow",
          "style": {"gap": "12px", "width": "100%"},
          "children": ["select-slide-job", "input-target-deck"],
      },
      {
          "id": "select-slide-job",
          "component": "MaterialSelect",
          "label": "Slide Category / Job Filter",
          "value": {"path": "/search/slide_job"},
          "options": _SEARCH_SLIDE_JOB_OPTIONS,
          "weight": 1,
      },
      {
          "id": "input-target-deck",
          "component": "MaterialInput",
          "label": "Target Deck ID / URL (Optional)",
          "placeholder": "Defaults to the active deck on Canvas",
          "value": {"path": "/search/target_presentation_id"},
          "weight": 1,
      },
      {
          "id": "btn-run-search",
          "component": "MaterialButton",
          "label": "🔍 Search Slides",
          "variant": "flat",
          "style": {
              "fontFamily": font_sans,
              "fontWeight": "500",
              "borderRadius": "999px",
          },
          "action": {
              "event": {
                  "name": "search_slides",
                  "context": {
                      "search_query": {"path": "/search/query"},
                      "slide_job": {"path": "/search/slide_job"},
                      "target_presentation_id": {
                          "path": "/search/target_presentation_id"
                      },
                      "customer_name": customer_name,
                  },
              }
          },
      },
  ]

  return [
      {
          "version": "v0.9",
          "createSurface": {
              "surfaceId": surface_id,
              "catalogId": a2ui.A2UI_MATERIAL_CATALOG_ID,
          },
      },
      {
          "version": "v0.9",
          "updateDataModel": {
              "surfaceId": surface_id,
              "value": {
                  "search_query": effective_query,
                  "slide_job": slide_job or "",
                  "target_presentation_id": target_presentation_id or "",
                  "search": {
                      "query": effective_query,
                      "slide_job": slide_job or "",
                      "target_presentation_id": target_presentation_id or "",
                  },
              },
          },
      },
      {
          "version": "v0.9",
          "updateComponents": {
              "surfaceId": surface_id,
              "components": components,
          },
      },
  ]


def create_a2ui_v09_search_results_messages(
    search_query: str = "",
    results: Optional[List[Dict[str, Any]]] = None,
    target_presentation_id: str = "",
    slide_job: str = "",
    customer_name: str = "",
    surface_id: str = SEARCH_RESULTS_SURFACE_PREFIX,
    max_results: int = SEARCH_RESULTS_MAX_TILES,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
  """Builds the Slide Search results card on the GE Material catalog.

  Visual language matches the PitchGen welcome card (outlined surface card,
  tinted icon header, 2-column grid of secondary tiles, Google Sans fonts,
  pill primary buttons). Each tile shows the slide thumbnail (MaterialImage;
  only trusted https URLs such as Slides `getThumbnail` contentUrls), the
  title, a category/deck caption and an Insert button wired to
  `insert_library_slide` (routed to `enterprise_insert_slide_skill`). There is
  no full-screen preview Modal.
  """
  del kwargs
  font_sans = "'Google Sans', 'Google Sans Text', Roboto, Arial, sans-serif"
  items = [r for r in results or [] if isinstance(r, dict)][
      : max(0, int(max_results))
  ]
  effective_query = search_query or "Customer References"

  subtitle_parts = [f'Query: "{effective_query}"']
  if customer_name:
    subtitle_parts.append(f"Account: {customer_name}")
  if slide_job:
    subtitle_parts.append(f"Filter: {format_slide_job_label(slide_job)}")

  title_style = {
      "fontFamily": font_sans,
      "fontWeight": "600",
      "color": "var(--mat-sys-on-surface, #1f1f1f)",
      "margin": "0",
  }
  desc_style = {
      "fontFamily": font_sans,
      "fontSize": "12px",
      "color": "var(--mat-sys-on-surface-variant, #444746)",
      "margin": "0",
  }
  tile_style = {
      "padding": "12px",
      "borderRadius": "14px",
      "backgroundColor": "var(--mat-sys-surface-container-low, #f8fafd)",
      "border": "1px solid var(--mat-sys-outline-variant, #dadce0)",
      "boxShadow": "none",
      "height": "100%",
      "boxSizing": "border-box",
  }
  grid_style = {
      "display": "grid",
      "gridTemplateColumns": "repeat(2, minmax(0, 1fr))",
      "gap": "12px",
      "width": "100%",
      "alignItems": "stretch",
  }
  primary_btn_style = {
      "fontFamily": font_sans,
      "fontWeight": "500",
      "borderRadius": "999px",
      "width": "100%",
  }

  main_children: List[str] = ["header_row", "header_divider"]
  components: List[Dict[str, Any]] = [
      {
          "id": "root",
          "component": "MaterialCard",
          "appearance": "outlined",
          "style": {
              "padding": "24px",
              "borderRadius": "16px",
              "backgroundColor": "var(--mat-sys-surface, #ffffff)",
              "border": "1px solid var(--mat-sys-outline-variant, #dadce0)",
              "fontFamily": font_sans,
          },
          "children": ["main_column"],
      },
      {
          "id": "header_row",
          "component": "MaterialRow",
          "justify": "start",
          "align": "center",
          "style": {"gap": "12px", "alignItems": "center"},
          "children": ["header_icon", "header_text_col"],
      },
      a2ui.material_header_icon("header_icon", "manage_search"),
      {
          "id": "header_text_col",
          "component": "MaterialColumn",
          "style": {"gap": "4px"},
          "children": ["header_title", "header_subtitle"],
      },
      {
          "id": "header_title",
          "component": "MaterialText",
          "usageHint": "h3",
          "text": f"Slide Library Results ({len(items)})",
          "style": {**title_style, "fontSize": "18px"},
      },
      {
          "id": "header_subtitle",
          "component": "MaterialText",
          "usageHint": "body",
          "text": " • ".join(subtitle_parts),
          "style": {**desc_style, "fontSize": "13px"},
      },
      {"id": "header_divider", "component": "MaterialDivider"},
  ]

  if not items:
    main_children.append("empty_state_txt")
    components.append({
        "id": "empty_state_txt",
        "component": "MaterialText",
        "usageHint": "body",
        "text": (
            "No matching slides found. Try a broader topic, a customer name,"
            " or a different slide category."
        ),
        "style": {**desc_style, "fontSize": "13px"},
    })

  row_buffer: List[str] = []
  for idx, item in enumerate(items, start=1):
    norm = normalize_slide_search_item(
        item=item, idx=idx, default_slide_job=slide_job or "Proof_Points"
    )
    slide_id = norm["slide_id"]
    pres_id = norm["pres_id"]
    title = norm["title"]
    deck_title = norm["source_deck_title"]
    item_job = norm["slide_job"]
    category = norm["customer"] or norm["industry"] or norm["slide_job_label"]
    view_url = norm["view_url"]
    thumb_url = _usable_thumbnail_url(
        item.get("thumbnail_url") or item.get("image_url")
    )
    # GE's MaterialSecurityService blocks data: URIs; only https images render.
    if not thumb_url.startswith("https://"):
      thumb_url = ""

    tile_id = f"slide_tile_card_{idx}"
    tile_col_id = f"slide_tile_col_{idx}"
    thumb_id = f"slide_thumb_{idx}"
    tile_title_id = f"slide_tile_title_{idx}"
    tile_meta_id = f"slide_tile_meta_{idx}"
    insert_btn_id = f"slide_insert_btn_{idx}"

    row_buffer.append(tile_id)
    if len(row_buffer) == 2 or idx == len(items):
      row_id = f"results_grid_row_{(idx + 1) // 2}"
      main_children.append(row_id)
      components.append({
          "id": row_id,
          "component": "MaterialRow",
          "style": grid_style,
          "children": list(row_buffer),
      })
      row_buffer = []

    if thumb_url:
      preview_components = [{
          "id": thumb_id,
          "component": "MaterialImage",
          "url": thumb_url,
          "alt": title,
          "fit": "contain",
          "width": "100%",
          "aspectRatio": "16/9",
          "borderRadius": "8px",
          "style": {
              "width": "100%",
              "aspectRatio": "16/9",
              "borderRadius": "8px",
              "backgroundColor": "var(--mat-sys-surface, #ffffff)",
              "border": "1px solid var(--mat-sys-outline-variant, #dadce0)",
              "objectFit": "contain",
          },
      }]
    else:
      placeholder_icon_id = f"slide_thumb_icon_{idx}"
      placeholder_txt_id = f"slide_thumb_txt_{idx}"
      preview_components = [
          {
              "id": thumb_id,
              "component": "MaterialColumn",
              "style": {
                  "width": "100%",
                  "aspectRatio": "16/9",
                  "borderRadius": "8px",
                  "backgroundColor": (
                      "var(--mat-sys-primary-container, #e8f0fe)"
                  ),
                  "display": "flex",
                  "alignItems": "center",
                  "justifyContent": "center",
                  "gap": "4px",
              },
              "children": [placeholder_icon_id, placeholder_txt_id],
          },
          {
              "id": placeholder_icon_id,
              "component": "MaterialIcon",
              "icon": "slideshow",
              "color": "primary",
          },
          {
              "id": placeholder_txt_id,
              "component": "MaterialText",
              "usageHint": "caption",
              "text": "Preview unavailable",
              "style": desc_style,
          },
      ]

    components.extend([
        {
            "id": tile_id,
            "component": "MaterialCard",
            "appearance": "outlined",
            "weight": 1,
            "style": tile_style,
            "children": [tile_col_id],
        },
        {
            "id": tile_col_id,
            "component": "MaterialColumn",
            "style": {"gap": "8px", "height": "100%"},
            "children": [thumb_id, tile_title_id, tile_meta_id, insert_btn_id],
        },
        *preview_components,
        {
            "id": tile_title_id,
            "component": "MaterialText",
            "usageHint": "subtitle2",
            "text": f"{idx}. {title}",
            "style": {**title_style, "fontSize": "14px"},
        },
        {
            "id": tile_meta_id,
            "component": "MaterialText",
            "usageHint": "caption",
            "text": f"{category or 'Reusable slide'} • {deck_title}",
            "style": desc_style,
        },
        {
            "id": insert_btn_id,
            "component": "MaterialButton",
            "variant": "flat",
            "color": "primary",
            "leadingIcon": "add",
            "loadingOnClick": True,
            "label": "Insert",
            "style": {**primary_btn_style, "marginTop": "auto"},
            "action": {
                "event": {
                    "name": "insert_library_slide",
                    "context": {
                        "template_slide_id": slide_id,
                        "source_presentation_id": pres_id,
                        "target_presentation_id": target_presentation_id or "",
                        "slide_title": title,
                        "slide_job": item_job,
                        "source_deck_title": deck_title,
                        "view_url": view_url,
                    },
                }
            },
        },
    ])

  components.insert(
      1,
      {
          "id": "main_column",
          "component": "MaterialColumn",
          "style": {"gap": "14px"},
          "children": main_children,
      },
  )

  return [
      {
          "version": "v0.9",
          "createSurface": {
              "surfaceId": surface_id,
              "catalogId": a2ui.A2UI_MATERIAL_CATALOG_ID,
          },
      },
      {
          "version": "v0.9",
          "updateComponents": {
              "surfaceId": surface_id,
              "components": components,
          },
      },
      {
          "version": "v0.9",
          "updateDataModel": {
              "surfaceId": surface_id,
              "value": {
                  "search_query": effective_query,
                  "slide_job": slide_job or "",
                  "target_presentation_id": target_presentation_id or "",
              },
          },
      },
  ]


def create_a2ui_search_form_messages(
    search_query: str = "",
    target_presentation_id: str = "",
    slide_job: str = "",
    customer_name: str = "",
    surface_id: str = "pitchgen-slide-search",
    **kwargs: Any,
) -> List[Dict[str, Any]]:
  """Wrapper for the Slide Search input form (form only, no results)."""
  return create_a2ui_v09_search_form_messages(
      search_query=search_query,
      target_presentation_id=target_presentation_id,
      slide_job=slide_job,
      customer_name=customer_name,
      surface_id=surface_id,
      **kwargs,
  )


def create_a2ui_search_results_messages(
    search_query: str = "",
    results: Optional[List[Dict[str, Any]]] = None,
    target_presentation_id: str = "",
    slide_job: str = "",
    customer_name: str = "",
    surface_id: str = SEARCH_RESULTS_SURFACE_PREFIX,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
  """Wrapper for the Slide Search results card (results only, no form)."""
  return create_a2ui_v09_search_results_messages(
      search_query=search_query,
      results=results,
      target_presentation_id=target_presentation_id,
      slide_job=slide_job,
      customer_name=customer_name,
      surface_id=surface_id,
      **kwargs,
  )


def create_a2ui_search_messages(
    search_query: str = "",
    results: Optional[List[Dict[str, Any]]] = None,
    target_presentation_id: str = "",
    slide_job: str = "",
    customer_name: str = "",
    surface_id: str = "pitchgen-slide-search",
) -> List[Dict[str, Any]]:
  """Version-aware wrapper returning A2UI v0.9 search surface messages.

  Without results this returns the A2UI-GE-style input form; with results it
  keeps returning the legacy combined Material card for backward compatibility.
  """
  if not results:
    return create_a2ui_v09_search_form_messages(
        search_query=search_query,
        target_presentation_id=target_presentation_id,
        slide_job=slide_job,
        customer_name=customer_name,
        surface_id=surface_id,
    )
  return create_a2ui_v09_search_messages(
      search_query=search_query,
      results=results,
      target_presentation_id=target_presentation_id,
      slide_job=slide_job,
      customer_name=customer_name,
      surface_id=surface_id,
  )
