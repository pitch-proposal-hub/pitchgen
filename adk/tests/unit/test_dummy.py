# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
You can add your unit tests here.
This is where you test your business logic, including agent functionality,
data processing, and other core components of your application.
"""


def test_dummy() -> None:
    """Placeholder - replace with real tests."""
    assert 1 == 1


def test_rotated_card_bbox_pt() -> None:
    """Verifies _element_bbox_pt handles 90/270-deg rotated shapes where Proto3 omits scaleX=0, scaleY=0."""
    import importlib
    import os
    import sys

    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src"))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    image_util = importlib.import_module("pitchgen_utils.image_util")
    _element_bbox_pt = image_util._element_bbox_pt

    pe = {
        "size": {
            "width": {"magnitude": 3000000, "unit": "EMU"},
            "height": {"magnitude": 3000000, "unit": "EMU"},
        },
        "transform": {
            "shearX": -1.1822,
            "shearY": 0.3394,
            "translateX": 8686800,
            "translateY": 744775,
            "unit": "EMU",
        },
    }
    x_pt, y_pt, w_pt, h_pt, is_flipped = _element_bbox_pt(pe)
    assert abs(x_pt - 404.7) < 1.0
    assert abs(y_pt - 58.6) < 1.0
    assert abs(w_pt - 279.3) < 1.0
    assert abs(h_pt - 80.2) < 1.0
    assert is_flipped is False


def test_text_transformer_budgets_and_single_slide_non_cover() -> None:
    """Verifies single-slide internal transform does not apply 28-char Cover Slide clamp and expands nominal 1-line card placeholders."""
    import importlib
    import os
    import sys
    import types

    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src"))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    for mod_name in (
        "google",
        "google.auth",
        "google.auth.transport",
        "google.auth.transport.requests",
        "google.genai",
        "google.genai.types",
        "dotenv",
        "agents.workflows.developer_knowledge_workflow",
    ):
        if mod_name not in sys.modules:
            try:
                importlib.import_module(mod_name)
            except ModuleNotFoundError:
                m = types.ModuleType(mod_name)
                if mod_name == "dotenv":
                    setattr(m, "load_dotenv", lambda *a, **kw: None)
                elif mod_name == "google.auth.transport.requests":
                    setattr(m, "AuthorizedSession", object)
                    setattr(m, "Request", object)
                elif mod_name == "google.genai":
                    setattr(m, "Client", object)
                    setattr(m, "types", types.SimpleNamespace())
                elif mod_name == "agents.workflows.developer_knowledge_workflow":
                    setattr(m, "DeveloperKnowledgeWorkflow", object)
                sys.modules[mod_name] = m
    if hasattr(sys.modules.get("google"), "__dict__"):
        setattr(sys.modules["google"], "auth", sys.modules.get("google.auth"))
        setattr(sys.modules["google"], "genai", sys.modules.get("google.genai"))
    tt_mod = importlib.import_module("agents.workflows.text_transformer_workflow")
    TextTransformerWorkflow = tt_mod.TextTransformerWorkflow

    wf = object.__new__(TextTransformerWorkflow)

    # 1. Left-rail title (T18: width=211.7pt, clearance=None) allows 44-56 chars
    t_title, m_title = wf._compute_char_budget(
        original_len=45,
        font_size=24.0,
        is_action_title=True,
        width_pt=211.7,
        clearance_pt=None,
        height_pt=21.8,
    )
    assert m_title >= 54
    assert t_title >= 44

    # 2. 2-line vertical pill header (width=128.0pt, height=51.1pt) allows up to 22 chars
    t_pill, m_pill = wf._compute_char_budget(
        original_len=20,
        font_size=14.0,
        is_action_title=False,
        width_pt=128.0,
        clearance_pt=102.7,
        height_pt=51.1,
    )
    assert m_pill >= 20

    # 3. Nominal 1-line placeholder body box (height=12.1pt, clearance=66.2pt) expands to ~60pt and allows >=100 chars
    t_body, m_body = wf._compute_char_budget(
        original_len=66,
        font_size=10.5,
        is_action_title=False,
        width_pt=260.2,
        clearance_pt=66.2,
        height_pt=12.1,
    )
    assert m_body >= 100
    assert t_body >= 88

    # 4. Internal slide title (is_cover_slide=False) preserves 54-char 3-line left-rail title intact (and is NOT chopped to <=28 chars)
    sanitized_title = wf._sanitize_output(
        "Navigating margin compression across athletic footwear",
        is_cover_slide=False,
        customer_name="Adidas",
        original_len=45,
        is_action_title=True,
        font_size=24.0,
        width_pt=211.7,
        clearance_pt=None,
        height_pt=21.8,
    )
    assert sanitized_title == "Navigating margin compression across athletic footwear"

    # 5. If a title overflows a tighter 45-char limit at 'across athletic', dangling_words strips 'across athletic' cleanly
    trimmed_tight = wf._trim_to_char_limit(
        "Navigating margin compression across athletic footwear",
        45,
        is_title_or_header=True,
    )
    assert trimmed_tight == "Navigating margin compression"

    # 6. Degraded 6-char 1-word pill header ("Margin") inside a 116.4pt x 60.7pt pill is budgeted by physical geometry (target>=16, max>=20), not clamped to 6 chars
    t_deg_hdr, m_deg_hdr = wf._compute_char_budget(
        original_len=6,
        font_size=14.0,
        is_action_title=False,
        width_pt=116.4,
        clearance_pt=66.7,
        height_pt=17.0,
    )
    assert m_deg_hdr >= 20
    assert t_deg_hdr >= 16

    # 7. Degraded 33-char spacious card body ("Markdowns erode DTC gross margin.") inside a 260.2pt x 60.2pt card is budgeted as a spacious body card (target>=98, max>=110), not a 36-char header
    t_deg_body, m_deg_body = wf._compute_char_budget(
        original_len=33,
        font_size=12.0,
        is_action_title=False,
        width_pt=260.2,
        clearance_pt=66.2,
        height_pt=12.1,
    )
    assert m_deg_body >= 110
    assert t_deg_body >= 98

    # 8. End-to-end execute_deck_holistic post-processing: expands 1-word sub_card_header, normalizes header casing, and fixes non-final transition_hook
    import json
    from unittest.mock import MagicMock

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = json.dumps({
        "slides": [
            {
                "slide_number": 3,
                "speaker_notes": (
                    "Key Takeaway: Protect operating margins across global retail.\n\n"
                    "Talking Points:\n- Align footwear allocation to regional demand.\n\n"
                    "Discovery Question: Where do markdowns compress gross margin most?"
                ),
                "transition_hook": (
                    "🎯 Executive Takeaway: Next, we examine how real-time demand sensing "
                    "protects gross margin."
                ),
                "shapes": [
                    {
                        "shape_id": "title_1",
                        "transformed_text": "Protecting gross margins across global footwear",
                    },
                    {
                        "shape_id": "hdr_1",
                        "transformed_text": "Margin protection",
                    },
                    {
                        "shape_id": "hdr_2",
                        "transformed_text": "Inventory velocity",
                    },
                    {
                        "shape_id": "body_1",
                        "transformed_text": (
                            "Unplanned seasonal markdowns erode gross margin when regional "
                            "footwear allocation lags shifts in consumer demand."
                        ),
                    },
                ],
            }
        ]
    })
    wf.client = mock_client
    wf.gemini_model = "gemini-3.8-flash"
    wf.gemini_model_fallback = "gemini-3.5-flash-lite"
    wf.gemini_model_1 = "gemini-3.5-flash-lite"
    wf._fetch_developer_knowledge_grounding = lambda *a, **kw: ("", [])
    wf.generate_content_with_fallback = lambda *a, **kw: mock_resp

    from unittest.mock import patch

    with patch.multiple(
        tt_mod.types,
        GenerateContentConfig=lambda **kw: kw,
        ThinkingConfig=lambda **kw: kw,
        ThinkingLevel=types.SimpleNamespace(MEDIUM="MEDIUM"),
        HttpOptions=lambda **kw: kw,
    ):
        holistic_out = wf.execute_deck_holistic(
        slides_list=[
            {
                "slide_number": 3,
                "is_cover_slide": False,
                "is_reusable_slide": True,
                "is_final_slide_in_deck": False,
                "prev_slide_context": "Slide 2: Executive Agenda",
                "next_slide_context": "Slide 4: Navigating margin compression",
                "speaker_notes": "Key Takeaway: Legacy notes",
                "data": [
                    {
                        "shapeId": "title_1",
                        "text": "Mitigating global footwear margin risks",
                        "fontSize": 24.0,
                        "bold": False,
                        "fontWeight": 400,
                        "width_pt": 211.7,
                        "height_pt": 21.8,
                        "clearance_pt": None,
                    },
                    {
                        "shapeId": "hdr_1",
                        "text": "Margin",
                        "fontSize": 14.0,
                        "bold": True,
                        "fontWeight": 500,
                        "width_pt": 116.4,
                        "height_pt": 17.0,
                        "clearance_pt": 66.7,
                    },
                    {
                        "shapeId": "hdr_2",
                        "text": "Inventory Velocity",
                        "fontSize": 14.0,
                        "bold": True,
                        "fontWeight": 500,
                        "width_pt": 116.4,
                        "height_pt": 17.0,
                        "clearance_pt": 66.7,
                    },
                    {
                        "shapeId": "body_1",
                        "text": "Markdowns erode DTC gross margin.",
                        "fontSize": 12.0,
                        "bold": False,
                        "fontWeight": 400,
                        "width_pt": 260.2,
                        "height_pt": 12.1,
                        "clearance_pt": 66.2,
                    },
                ],
            }
        ],
        criteria="Target Executive Persona: Chief Financial Officer (CFO).",
        context={
            "customer_name": "Adidas",
            "industry": "Retail",
            "customer_research": "Adidas global footwear & apparel.",
        },
    )
    out_slide = holistic_out[0]
    out_shapes = {s["shapeId"]: s["text"] for s in out_slide["data"]}
    assert len(out_shapes["hdr_1"].split()) >= 2
    assert out_shapes["hdr_2"].lower() == "inventory velocity"
    assert out_slide["transition_hook"].startswith("🔗 Transition to next slide:")
    assert "🎯 Executive Takeaway:" not in out_slide["transition_hook"]



def test_canvas_marker_bracket_stripping() -> None:
    """Verifies [Active Google Slides Presentation on Canvas: [PitchGen] ...] is completely stripped from chat text."""
    import re

    sample = (
        "Here are the 3 best matching slides from the library. "
        "[Active Google Slides Presentation on Canvas: [PitchGen] Adidas | Agentic commerce at Adidas (Oct 2026) "
        "(presentation_id=SAMPLE_TEST_PRESENTATION_ID_000000000012, "
        "url=https://docs.google.com/presentation/d/SAMPLE_TEST_PRESENTATION_ID_000000000012/edit)]"
    )
    cleaned = re.sub(
        r"\[Active Google Slides Presentation on Canvas:[^\n]*?\)\]\s*",
        "",
        sample,
    ).strip()
    assert cleaned == "Here are the 3 best matching slides from the library."

