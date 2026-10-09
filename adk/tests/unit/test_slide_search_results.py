"""Unit tests for the hybrid Slide Search experience (form, results card, thumbnails, routing)."""

import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import requests  # pylint: disable=g-import-not-at-top

from ge import a2ui  # pylint: disable=g-import-not-at-top
from ge import a2ui_search  # pylint: disable=g-import-not-at-top
from pitchgen_utils import slide_thumbnail_util as stu  # pylint: disable=g-import-not-at-top

_DECK_A = "1AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_DECK_B = "1BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
_ACTIVE = "1ACTIVEACTIVEACTIVEACTIVEACTIVEACTIVEACTIV"


def _fake_results(n=3):
  out = []
  for i in range(n):
    deck = _DECK_A if i % 2 == 0 else _DECK_B
    out.append({
        "title": f"Customer story {i + 1}",
        "customer": f"Customer {i + 1}",
        "slide_id": f"g_slide_{i + 1}",
        "deck_id": deck,
        "presentation_id": deck,
        "source_deck_title": "Reference Deck",
        "slide_job": "Proof_Points",
        "view_url": (
            f"https://docs.google.com/presentation/d/{deck}/edit#slide=id.g_slide_{i + 1}"
        ),
    })
  return out


def _resp(status, payload=None):
  r = mock.MagicMock()
  r.status_code = status
  r.json.return_value = payload or {}
  return r


def _components(msgs):
  for m in msgs:
    if "updateComponents" in m:
      return m["updateComponents"]["components"]
  return []


def _assert_component_tree_valid(test, msgs):
  """Every referenced child id exists and every component is reachable from root."""
  comps = _components(msgs)
  by_id = {c["id"]: c for c in comps}
  test.assertEqual(len(by_id), len(comps), "duplicate component ids")
  test.assertIn("root", by_id)

  def _refs(c):
    refs = []
    if isinstance(c.get("child"), str):
      refs.append(c["child"])
    ch = c.get("children")
    if isinstance(ch, list):
      refs.extend(x for x in ch if isinstance(x, str))
    elif isinstance(ch, dict):
      exp = ch.get("explicitList")
      if isinstance(exp, list):
        refs.extend(exp)
    for k in ("trigger", "content", "entryPointChild", "contentChild"):
      if isinstance(c.get(k), str):
        refs.append(c[k])
    return refs

  reachable = set()
  stack = ["root"]
  while stack:
    cid = stack.pop()
    if cid in reachable:
      continue
    reachable.add(cid)
    for ref in _refs(by_id[cid]):
      test.assertIn(ref, by_id, f"{cid} references missing child {ref}")
      stack.append(ref)
  test.assertEqual(set(by_id) - reachable, set(), "orphan components")


class SlideThumbnailUtilTest(unittest.TestCase):

  def setUp(self):
    super().setUp()
    stu.clear_thumbnail_cache()

  def test_success_sets_content_url_and_caches(self):
    url = "https://lh7-us.googleusercontent.com/thumb_1"
    with mock.patch.object(
        stu.requests, "get", return_value=_resp(200, {"contentUrl": url})
    ) as m_get:
      out = stu.enrich_results_with_thumbnails(
          _fake_results(1), candidate_tokens=[("user", "tok")]
      )
      self.assertEqual(out[0]["thumbnail_url"], url)
      self.assertEqual(m_get.call_count, 1)
      args, kwargs = m_get.call_args
      self.assertIn(
          f"/presentations/{_DECK_A}/pages/g_slide_1/thumbnail", args[0]
      )
      self.assertEqual(kwargs["headers"]["Authorization"], "Bearer tok")
      # Second call is served from cache (no new HTTP request).
      out2 = stu.enrich_results_with_thumbnails(
          _fake_results(1), candidate_tokens=[("user", "tok")]
      )
      self.assertEqual(out2[0]["thumbnail_url"], url)
      self.assertEqual(m_get.call_count, 1)
    self.assertEqual(stu.get_cached_thumbnail(_DECK_A, "g_slide_1"), url)

  def test_403_falls_back_to_next_token(self):
    url = "https://lh7-us.googleusercontent.com/thumb_fallback"
    with mock.patch.object(
        stu.requests,
        "get",
        side_effect=[_resp(403), _resp(200, {"contentUrl": url})],
    ) as m_get:
      out = stu.enrich_results_with_thumbnails(
          _fake_results(1),
          candidate_tokens=[("user", "bad"), ("service_owner", "good")],
      )
    self.assertEqual(out[0]["thumbnail_url"], url)
    self.assertEqual(m_get.call_count, 2)
    auths = [c.kwargs["headers"]["Authorization"] for c in m_get.call_args_list]
    self.assertEqual(auths, ["Bearer bad", "Bearer good"])

  def test_timeout_leaves_placeholder(self):
    with mock.patch.object(
        stu.requests, "get", side_effect=requests.exceptions.Timeout("slow")
    ):
      out = stu.enrich_results_with_thumbnails(
          _fake_results(2), candidate_tokens=[("user", "tok")]
      )
    self.assertEqual([r["thumbnail_url"] for r in out], ["", ""])

  def test_export_urls_are_stripped_and_never_returned(self):
    items = _fake_results(1)
    items[0][
        "thumbnail_url"
    ] = f"https://docs.google.com/presentation/d/{_DECK_A}/export/png?pageid=g_slide_1"
    with mock.patch.object(
        stu.requests,
        "get",
        return_value=_resp(
            200,
            {
                "contentUrl": (
                    f"https://docs.google.com/presentation/d/{_DECK_A}/export?format=png"
                )
            },
        ),
    ):
      out = stu.enrich_results_with_thumbnails(
          items, candidate_tokens=[("user", "tok")]
      )
    self.assertEqual(out[0]["thumbnail_url"], "")
    # Input list is not mutated.
    self.assertIn("/export", items[0]["thumbnail_url"])

  def test_no_tokens_or_kill_switch_skips_network(self):
    with mock.patch.object(stu.requests, "get") as m_get:
      out = stu.enrich_results_with_thumbnails(
          _fake_results(2), token_provider=lambda _ctx: []
      )
      self.assertEqual([r["thumbnail_url"] for r in out], ["", ""])
      with mock.patch.dict(
          os.environ, {"PITCHGEN_DISABLE_SLIDE_THUMBNAILS": "1"}
      ):
        stu.enrich_results_with_thumbnails(
            _fake_results(2), candidate_tokens=[("user", "tok")]
        )
      m_get.assert_not_called()

  def test_extract_slide_ids_from_urls_and_camelcase(self):
    self.assertEqual(
        stu.extract_slide_ids({
            "slideURL": (
                f"https://docs.google.com/presentation/d/{_DECK_B}/edit#slide=id.g_x"
            )
        }),
        (_DECK_B, "g_x"),
    )
    self.assertEqual(
        stu.extract_slide_ids({"deckId": _DECK_A, "slideId": "g_y"}),
        (_DECK_A, "g_y"),
    )
    pres, slide = stu.extract_slide_ids(
        {"deck_id": _DECK_A, "slide_id": "slide_3"}
    )
    self.assertEqual((pres, slide), (_DECK_A, ""))


class SearchCardsTest(unittest.TestCase):

  def test_form_card_material_catalog_and_submit_event(self):
    msgs = a2ui.create_a2ui_v09_search_form_messages(
        target_presentation_id=_ACTIVE,
        customer_name="Acme",
        surface_id="pitchgen-slide-search-2",
    )
    self.assertEqual(
        [next(iter(k for k in m if k != "version")) for m in msgs],
        ["createSurface", "updateDataModel", "updateComponents"],
    )
    self.assertEqual(
        msgs[0]["createSurface"]["catalogId"], a2ui.A2UI_MATERIAL_CATALOG_ID
    )
    comps = _components(msgs)
    # Pure Material catalog (GE renders no `Image` on Material surfaces).
    self.assertTrue(all(c["component"].startswith("Material") for c in comps))
    _assert_component_tree_valid(self, msgs)
    buttons = [c for c in comps if c["component"] == "MaterialButton"]
    self.assertEqual(len(buttons), 1)
    event = buttons[0]["action"]["event"]
    self.assertEqual(event["name"], "search_slides")
    self.assertIn("search_query", event["context"])
    self.assertIn("slide_job", event["context"])
    self.assertIn("target_presentation_id", event["context"])
    # No PitchGen logo on the search form.
    self.assertNotIn("pitchgen_tool_logo", json.dumps(msgs))

  def test_results_card_material_grid_and_insert_event(self):
    results = _fake_results(3)
    results[0]["thumbnail_url"] = "https://lh7-us.googleusercontent.com/t1"
    results[1][
        "thumbnail_url"
    ] = f"https://docs.google.com/presentation/d/{_DECK_B}/export/png"
    msgs = a2ui.create_a2ui_v09_search_results_messages(
        search_query="retail agents",
        results=results,
        target_presentation_id=_ACTIVE,
        customer_name="Acme",
        surface_id="pitchgen-search-results-abc12345",
    )
    self.assertEqual(
        msgs[0]["createSurface"]["catalogId"], a2ui.A2UI_MATERIAL_CATALOG_ID
    )
    self.assertTrue(
        all(
            m.get(k, {}).get("surfaceId") == "pitchgen-search-results-abc12345"
            for m in msgs
            for k in m
            if k != "version"
        )
    )
    comps = _components(msgs)
    self.assertTrue(all(c["component"].startswith("Material") for c in comps))
    _assert_component_tree_valid(self, msgs)
    by_id = {c["id"]: c for c in comps}

    # No full-screen preview Modal/Dialog and no logo on the results card.
    self.assertFalse(
        any(c["component"] in ("Modal", "MaterialDialog") for c in comps)
    )
    self.assertNotIn("pitchgen_tool_logo", by_id)

    # Grid: rows of at most 2 tile Cards (3 results -> rows of 2 + 1).
    def _kids(c):
      ch = c.get("children")
      if isinstance(ch, dict):
        ch = ch.get("explicitList")
      return [x for x in ch or [] if isinstance(x, str)]

    tile_rows = [
        c
        for c in comps
        if c["component"] == "MaterialRow"
        and _kids(c)
        and all(by_id[x]["component"] == "MaterialCard" for x in _kids(c))
    ]
    self.assertEqual(sorted(len(_kids(r)) for r in tile_rows), [1, 2])

    for r in tile_rows:
      self.assertEqual(r["style"]["display"], "grid")

    # Only the real https thumbnail renders a MaterialImage; /export becomes a
    # placeholder tile.
    dumped = json.dumps(msgs)
    images = [c for c in comps if c["component"] == "MaterialImage"]
    self.assertEqual(len(images), 1)
    self.assertEqual(
        images[0]["url"], "https://lh7-us.googleusercontent.com/t1"
    )
    self.assertNotIn("/export", dumped)

    insert_buttons = [
        c
        for c in comps
        if c["component"] == "MaterialButton"
        and c.get("action", {}).get("event", {}).get("name")
        == "insert_library_slide"
    ]
    self.assertEqual(len(insert_buttons), 3)
    ctx0 = insert_buttons[0]["action"]["event"]["context"]
    for key in (
        "template_slide_id",
        "source_presentation_id",
        "target_presentation_id",
        "slide_title",
    ):
      self.assertIn(key, ctx0)
    self.assertEqual(insert_buttons[0]["label"], "Insert")
    # Each Insert button sits directly under its tile's thumbnail/title.
    tile_col = by_id["slide_tile_col_1"]
    self.assertEqual(tile_col["children"][-1], insert_buttons[0]["id"])
    self.assertNotIn("search_slides", dumped)

  def test_results_card_drops_data_uri_thumbnails(self):
    results = _fake_results(1)
    results[0]["thumbnail_url"] = "data:image/png;base64,AAAA"
    msgs = a2ui.create_a2ui_v09_search_results_messages(
        search_query="q",
        results=results,
        surface_id="pitchgen-search-results-d",
    )
    comps = _components(msgs)
    self.assertFalse(any(c["component"] == "MaterialImage" for c in comps))
    self.assertNotIn("data:image", json.dumps(msgs))

  def test_results_card_empty_state(self):
    msgs = a2ui.create_a2ui_v09_search_results_messages(
        search_query="nothing",
        results=[],
        surface_id="pitchgen-search-results-e",
    )
    _assert_component_tree_valid(self, msgs)
    self.assertNotIn("Modal", json.dumps(_components(msgs)))


def _decode_parts(parts):
  """Returns the text of each part, decoding base64 A2A inline DataParts."""
  out = []
  for p in parts:
    inline = getattr(p, "inline_data", None)
    if inline is not None and getattr(inline, "data", None):
      data = inline.data
      out.append(data.decode("utf-8") if isinstance(data, bytes) else str(data))
    elif getattr(p, "text", None):
      out.append(p.text)
  return out


class _Ctx:

  def __init__(self, state=None):
    self.state = dict(state or {})


class SearchRoutingTest(unittest.TestCase):

  def setUp(self):
    super().setUp()
    import enterprise_agent as ea  # pylint: disable=g-import-not-at-top

    self.ea = ea
    stu.clear_thumbnail_cache()
    self._patches = [
        mock.patch(
            "agents.workflows.customer_reference_retriever.NewLibraryCustomerReferenceRetriever.search_slides",
            return_value=_fake_results(3),
        ),
        mock.patch(
            "agents.sidebar_agent.SidebarAgent.search",
            return_value={"search_results": []},
        ),
        mock.patch.object(
            stu, "resolve_thumbnail_candidate_tokens", return_value=[]
        ),
    ]
    for p in self._patches:
      p.start()
      self.addCleanup(p.stop)

  def _results_creates(self, payloads):
    flat = []

    def _walk(o):
      if isinstance(o, list):
        for x in o:
          _walk(x)
      elif isinstance(o, dict):
        if isinstance(o.get("a2ui_v09_messages"), list):
          _walk(o["a2ui_v09_messages"])
        else:
          flat.append(o)

    _walk(payloads)
    return flat

  def test_one_results_card_per_search_and_prior_deleted(self):
    ctx = _Ctx({"customer_name": "Acme", "presentation_id": _ACTIVE})
    self.ea.enterprise_search_slides_skill(search_query="q1", tool_context=ctx)
    first = self._results_creates(ctx.state["a2ui_payloads_to_inject"])
    first_creates = [m for m in first if "createSurface" in m]
    self.assertEqual(len(first_creates), 1)
    sid1 = first_creates[0]["createSurface"]["surfaceId"]
    self.assertTrue(sid1.startswith("pitchgen-search-results-"))

    ctx.state["a2ui_payloads_to_inject"] = []
    self.ea.enterprise_search_slides_skill(search_query="q2", tool_context=ctx)
    second = self._results_creates(ctx.state["a2ui_payloads_to_inject"])
    second_creates = [m for m in second if "createSurface" in m]
    self.assertEqual(len(second_creates), 1)
    sid2 = second_creates[0]["createSurface"]["surfaceId"]
    self.assertNotEqual(sid1, sid2)
    deletes = [
        m["deleteSurface"]["surfaceId"] for m in second if "deleteSurface" in m
    ]
    self.assertEqual(deletes, [sid1])
    self.assertNotIn("pitchgen-slide-search", json.dumps(second))

  def test_before_model_search_slides_action_is_deterministic(self):
    from google.adk.models.llm_response import LlmResponse  # pylint: disable=g-import-not-at-top
    from google.genai import types  # pylint: disable=g-import-not-at-top

    ctx = _Ctx({
        "customer_name": "Acme",
        "presentation_id": _ACTIVE,
        "last_target_card": "search_slide",  # stale launcher flag
    })
    action = {
        "kind": "data",
        "data": {
            "action": {
                "name": "search_slides",
                "context": {
                    "search_query": "retail agents",
                    "slide_job": "Proof_Points",
                    "target_presentation_id": _ACTIVE,
                },
            }
        },
    }
    turn = types.Content(
        role="user",
        parts=[
            types.Part(
                text=f"<a2a_datapart_json>{json.dumps(action)}</a2a_datapart_json>"
            )
        ],
    )
    req = type("Req", (), {"contents": [turn]})()
    resp = self.ea.enterprise_before_model_callback(ctx, req)
    self.assertIsInstance(resp, LlmResponse)
    self.assertEqual(ctx.state.get("last_target_card"), "")
    self.assertEqual(ctx.state.get("a2ui_payloads_to_inject"), [])

    parts = resp.content.parts
    texts = [
        p.text for p in parts if getattr(p, "text", None) and not p.thought
    ]
    serialized = "\n".join(_decode_parts(parts))
    self.assertEqual(serialized.count("createSurface"), 1)
    self.assertIn("pitchgen-search-results-", serialized)
    self.assertNotIn("pitchgen-slide-search", serialized)
    self.assertTrue(any("retail agents" in t for t in texts))
    # No LLM prompt rewrite happened.
    self.assertNotIn(
        "Invoke enterprise_search_slides_skill", turn.parts[0].text
    )

  def test_launcher_fast_path_clears_stale_flag(self):
    from google.genai import types  # pylint: disable=g-import-not-at-top

    ctx = _Ctx({"customer_name": "Acme"})
    action = {
        "kind": "data",
        "data": {
            "action": {
                "name": "launch_feature",
                "context": {"target_card": "search_slide"},
            }
        },
    }
    turn = types.Content(
        role="user",
        parts=[
            types.Part(
                text=f"<a2a_datapart_json>{json.dumps(action)}</a2a_datapart_json>"
            )
        ],
    )
    req = type("Req", (), {"contents": [turn]})()
    resp = self.ea.enterprise_before_model_callback(ctx, req)
    self.assertIsNotNone(resp)
    self.assertEqual(ctx.state.get("last_target_card"), "")
    serialized = "\n".join(_decode_parts(resp.content.parts))
    self.assertIn("pitchgen-slide-search", serialized)
    self.assertIn("search_slides", serialized)

  def test_search_skill_signature_is_backward_compatible(self):
    import inspect  # pylint: disable=g-import-not-at-top

    params = inspect.signature(
        self.ea.enterprise_search_slides_skill
    ).parameters
    for name in ("search_query", "slide_job", "strict_search", "tool_context"):
      self.assertIn(name, params)
    self.assertEqual(params["target_presentation_id"].default, "")


if __name__ == "__main__":
  unittest.main()
