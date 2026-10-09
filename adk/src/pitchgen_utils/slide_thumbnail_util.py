"""Google Slides thumbnail resolution for PitchGen slide search results.

Calls the Slides REST API `presentations.pages.getThumbnail` endpoint for up to
N search results in parallel and returns the short-lived `contentUrl` image URL
(valid ~30 minutes) so A2UI result tiles can render real slide previews.

Bearer tokens come from PitchGen's existing 4-tier token waterfall
(`agent._build_apps_script_candidate_tokens`). Candidates are tried in order and
the first HTTP 200 wins. `/export` URLs are never used as thumbnails.
"""

import concurrent.futures
import logging
import os
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import requests

SLIDES_THUMBNAIL_ENDPOINT = (
    "https://slides.googleapis.com/v1/presentations/{presentation_id}"
    "/pages/{page_object_id}/thumbnail"
)
THUMBNAIL_PARAMS = {
    "thumbnailProperties.thumbnailSize": "MEDIUM",
    "thumbnailProperties.mimeType": "PNG",
}
DEFAULT_MAX_ITEMS = 8
DEFAULT_PER_CALL_TIMEOUT_S = 6.0
DEFAULT_TOTAL_BUDGET_S = 10.0
CACHE_TTL_S = 25 * 60  # contentUrl expires after ~30 minutes

_CACHE: Dict[Tuple[str, str], Tuple[str, float]] = {}
_CACHE_LOCK = threading.Lock()

_PRES_ID_RE = re.compile(r"/presentation/d/([a-zA-Z0-9_-]{20,})")
_SLIDE_ID_RE = re.compile(r"#slide=id\.([A-Za-z0-9_\-.]+)")
_SYNTHETIC_SLIDE_ID_RE = re.compile(r"^slide_\d+$")

CandidateTokens = Sequence[Tuple[str, str]]


def is_export_url(url: Any) -> bool:
  """Returns True for Google Slides/Drive export URLs, which are never valid thumbnails."""
  s = str(url or "")
  return "/export" in s or "export?format" in s or "exportFormat=" in s


def thumbnails_disabled() -> bool:
  """True when PITCHGEN_DISABLE_SLIDE_THUMBNAILS is set to a truthy value."""
  val = os.environ.get("PITCHGEN_DISABLE_SLIDE_THUMBNAILS", "")
  return val.strip().lower() in ("1", "true", "yes", "on")


def clear_thumbnail_cache() -> None:
  """Clears the in-process thumbnail cache (used by tests)."""
  with _CACHE_LOCK:
    _CACHE.clear()


def get_cached_thumbnail(
    presentation_id: str, slide_id: str, now: Optional[float] = None
) -> str:
  """Returns a cached, non-expired contentUrl for (presentation_id, slide_id) or ''."""
  key = (str(presentation_id or ""), str(slide_id or ""))
  ts_now = time.time() if now is None else now
  with _CACHE_LOCK:
    hit = _CACHE.get(key)
    if not hit:
      return ""
    url, stored_at = hit
    if ts_now - stored_at > CACHE_TTL_S:
      _CACHE.pop(key, None)
      return ""
    return url


def _store_cached_thumbnail(
    presentation_id: str, slide_id: str, url: str
) -> None:
  with _CACHE_LOCK:
    _CACHE[(str(presentation_id), str(slide_id))] = (url, time.time())


def extract_slide_ids(item: Dict[str, Any]) -> Tuple[str, str]:
  """Extracts (presentation_id, slide_object_id) from a search result dict.

  Supports snake_case and camelCase keys, plus Customer Reference Library-style
  `.../presentation/d/<id>/edit#slide=id.<slide>` URLs.
  """
  if not isinstance(item, dict):
    return "", ""
  pres_id = str(
      item.get("presentation_id")
      or item.get("pres_id")
      or item.get("deck_id")
      or item.get("deckId")
      or item.get("source_presentation_id")
      or ""
  ).strip()
  slide_id = str(
      item.get("slide_id")
      or item.get("slideId")
      or item.get("slide_object_id")
      or item.get("template_slide_id")
      or ""
  ).strip()
  for url_key in ("view_url", "slideURL", "slide_url", "link", "temp_url"):
    url = str(item.get(url_key) or "")
    if not url:
      continue
    if not pres_id:
      m_p = _PRES_ID_RE.search(url)
      if m_p:
        pres_id = m_p.group(1)
    if not slide_id:
      m_s = _SLIDE_ID_RE.search(url)
      if m_s:
        slide_id = m_s.group(1)
  if _SYNTHETIC_SLIDE_ID_RE.match(slide_id):
    slide_id = ""
  return pres_id, slide_id


def resolve_thumbnail_candidate_tokens(
    tool_context: Any = None,
) -> List[Tuple[str, str]]:
  """Builds bearer-token candidates from PitchGen's existing waterfall.

  Delegates to `agent._build_apps_script_candidate_tokens` (user short-lived
  token / headers -> user GCS refresh token -> service-owner token -> ADC).
  """
  try:
    from agent import (  # pylint: disable=g-import-not-at-top
        _build_apps_script_candidate_tokens,
        extract_session_user_email_and_ldap,
    )
  except Exception as import_err:  # pragma: no cover - runtime path only
    logging.warning(
        "[slide_thumbnail_util] Token waterfall unavailable: %s", import_err
    )
    return []
  user_ldap = ""
  try:
    if tool_context is not None:
      _, user_ldap = extract_session_user_email_and_ldap(tool_context)
  except Exception:
    user_ldap = ""
  clean_ldap = str(user_ldap or "").split("@")[0].lower().strip()
  if clean_ldap in ("unknown", "unknown_user", "user", "none"):
    clean_ldap = ""
  try:
    return list(
        _build_apps_script_candidate_tokens(
            clean_ldap, None, tool_context=tool_context
        )
        or []
    )
  except Exception as tok_err:
    logging.warning(
        "[slide_thumbnail_util] Token waterfall failed: %s", tok_err
    )
    return []


def fetch_slide_thumbnail_url(
    presentation_id: str,
    slide_id: str,
    candidate_tokens: CandidateTokens,
    per_call_timeout: float = DEFAULT_PER_CALL_TIMEOUT_S,
    deadline: Optional[float] = None,
) -> str:
  """Fetches a Slides thumbnail contentUrl, trying candidate tokens in order.

  Non-200 responses (401/403/404/429/5xx) fall through to the next token. A
  timeout or exhausted deadline stops the waterfall and returns ''.
  """
  if not presentation_id or not slide_id:
    return ""
  cached = get_cached_thumbnail(presentation_id, slide_id)
  if cached:
    return cached
  url = SLIDES_THUMBNAIL_ENDPOINT.format(
      presentation_id=presentation_id, page_object_id=slide_id
  )
  for label, token in candidate_tokens or []:
    if not token:
      continue
    timeout = per_call_timeout
    if deadline is not None:
      remaining = deadline - time.monotonic()
      if remaining <= 0.05:
        return ""
      timeout = min(per_call_timeout, remaining)
    try:
      resp = requests.get(
          url,
          params=THUMBNAIL_PARAMS,
          headers={"Authorization": f"Bearer {token}"},
          timeout=timeout,
      )
    except requests.exceptions.Timeout:
      logging.info(
          "[slide_thumbnail_util] Thumbnail timeout for %s/%s (auth=%s)",
          presentation_id,
          slide_id,
          label,
      )
      return ""
    except Exception as req_err:
      logging.info(
          "[slide_thumbnail_util] Thumbnail request error for %s/%s"
          " (auth=%s): %s",
          presentation_id,
          slide_id,
          label,
          req_err,
      )
      continue
    if getattr(resp, "status_code", 0) != 200:
      continue
    try:
      content_url = str((resp.json() or {}).get("contentUrl") or "").strip()
    except Exception:
      content_url = ""
    if content_url.startswith("https://") and not is_export_url(content_url):
      _store_cached_thumbnail(presentation_id, slide_id, content_url)
      return content_url
  return ""


def enrich_results_with_thumbnails(
    results: Optional[List[Dict[str, Any]]],
    tool_context: Any = None,
    candidate_tokens: Optional[CandidateTokens] = None,
    token_provider: Optional[Callable[[Any], CandidateTokens]] = None,
    max_items: int = DEFAULT_MAX_ITEMS,
    per_call_timeout: float = DEFAULT_PER_CALL_TIMEOUT_S,
    total_budget: float = DEFAULT_TOTAL_BUDGET_S,
) -> List[Dict[str, Any]]:
  """Returns shallow copies of `results` with real `thumbnail_url` values.

  Only the first `max_items` results are enriched. Existing `/export`
  thumbnails are stripped. Results without a resolvable thumbnail get
  `thumbnail_url = ''` so the UI renders a text placeholder tile.
  """
  items: List[Dict[str, Any]] = [
      dict(r) for r in results or [] if isinstance(r, dict)
  ]
  start = time.monotonic()
  deadline = start + max(0.0, float(total_budget))

  pending: List[Tuple[int, str, str]] = []
  for idx, item in enumerate(items):
    existing = str(item.get("thumbnail_url") or "")
    if existing and is_export_url(existing):
      item["thumbnail_url"] = ""
      existing = ""
    if idx >= max_items:
      continue
    if existing.startswith("https://"):
      continue
    pres_id, slide_id = extract_slide_ids(item)
    if not pres_id or not slide_id:
      item["thumbnail_url"] = ""
      continue
    cached = get_cached_thumbnail(pres_id, slide_id)
    if cached:
      item["thumbnail_url"] = cached
      continue
    item["thumbnail_url"] = ""
    pending.append((idx, pres_id, slide_id))

  if not pending:
    return items
  if thumbnails_disabled():
    return items

  tokens: CandidateTokens = candidate_tokens or ()
  if not tokens:
    provider = token_provider or resolve_thumbnail_candidate_tokens
    try:
      tokens = provider(tool_context) or ()
    except Exception as prov_err:
      logging.warning(
          "[slide_thumbnail_util] Token provider failed: %s", prov_err
      )
      tokens = ()
  if not tokens:
    return items

  executor = concurrent.futures.ThreadPoolExecutor(
      max_workers=min(len(pending), max_items) or 1,
      thread_name_prefix="pg-thumb",
  )
  futures = {}
  try:
    for idx, pres_id, slide_id in pending:
      fut = executor.submit(
          fetch_slide_thumbnail_url,
          pres_id,
          slide_id,
          tokens,
          per_call_timeout,
          deadline,
      )
      futures[fut] = idx
    remaining = max(0.0, deadline - time.monotonic())
    done, _ = concurrent.futures.wait(list(futures), timeout=remaining)
    for fut in done:
      try:
        thumb = fut.result()
      except Exception:
        thumb = ""
      if thumb:
        items[futures[fut]]["thumbnail_url"] = thumb
  finally:
    executor.shutdown(wait=False, cancel_futures=True)

  logging.info(
      "[slide_thumbnail_util] Resolved %d/%d slide thumbnails in %.2fs",
      sum(1 for i, _, _ in pending if items[i].get("thumbnail_url")),
      len(pending),
      time.monotonic() - start,
  )
  return items
