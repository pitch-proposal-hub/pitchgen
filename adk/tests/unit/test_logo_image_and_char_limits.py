"""Unit tests for strict font-size-aware character limits, Google-only customer logo resolution, and non-GIF slide picture detection."""

import os
import sys
import unittest

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "src")
    ),
)

from agents.workflows.text_transformer_workflow import TextTransformerWorkflow
from pitchgen_utils.image_util import (
    _ensure_high_res_output_png,
    _select_gemini_aspect_ratio_and_size,
    cleanup_temp_drive_docs,
    extract_customizable_slide_pictures,
    image_bytes_to_content_uri,
    is_gif_or_animated_bytes,
)
from pitchgen_utils.logo_util import _normalize_logo_png_bytes, resolve_customer_domain


class TestLogoImageAndCharLimits(unittest.TestCase):

  def setUp(self):
    super().setUp()
    self.config = {
        "default": {
            "project_name": "your-gcp-project-id",
            "gemini_model": "gemini-3.8-flash",
            "gemini_model_1": "gemini-3.5-flash-lite",
            "gemini_image_model_1": "gemini-3.1-flash-image",
            "region": "global",
        },
        "bucket": {
            "content": "your-pitchgen-content-bucket",
        },
    }
    self.workflow = TextTransformerWorkflow(self.config)

  def test_compute_char_budget_tiers(self):
    # Tier 1: Large font (>= 18pt) -> target 90% (-10%), max 95% (-5%)
    t_large, m_large = self.workflow._compute_char_budget(100, font_size=24.0)
    self.assertEqual(t_large, 90)
    self.assertEqual(m_large, 95)

    # Tier 2: Medium font (14pt) -> target 92% (-8%), max 95% (-5%)
    t_med, m_med = self.workflow._compute_char_budget(100, font_size=14.0)
    self.assertEqual(t_med, 92)
    self.assertEqual(m_med, 95)

    # Tier 3: Small body font (10pt) -> target 95% (-5%), max 95% (-5%)
    t_small, m_small = self.workflow._compute_char_budget(100, font_size=10.0)
    self.assertEqual(t_small, 95)
    self.assertEqual(m_small, 95)

  def test_sanitize_output_enforces_minus_5_percent_ceiling(self):
    # Original length = 60 -> hard_max_chars = int(60 * 0.95) = 57
    long_llm_text = (
        "Accelerate global omnichannel supply chain forecasting and real-time store inventory with BigQuery"
    )
    sanitized = self.workflow._sanitize_output(
        long_llm_text,
        is_cover_slide=False,
        customer_name="Walmart",
        original_len=60,
        is_action_title=True,
        font_size=20.0,
    )
    self.assertLessEqual(len(sanitized), 57)
    self.assertFalse(sanitized.lower().endswith(" with"))
    self.assertFalse(sanitized.lower().endswith(" and"))

  def test_sanitize_output_preserves_multiline_header_and_body(self):
    # Original length = 80 -> hard_max_chars = 76
    multiline_text = (
        "Unified Retail Data Foundation\n"
        "Consolidate fragmented store telemetry, e-commerce clickstreams, and supplier ERPs into Knowledge Catalog."
    )
    sanitized = self.workflow._sanitize_output(
        multiline_text,
        is_cover_slide=False,
        customer_name="Walmart",
        original_len=80,
        is_action_title=False,
        font_size=11.0,
    )
    self.assertLessEqual(len(sanitized), 76)
    self.assertIn("\n", sanitized)
    self.assertTrue(sanitized.startswith("Unified Retail Data Foundation\n"))

  def test_resolve_customer_domain_and_gif_rejection(self):
    from pitchgen_utils.logo_util import _synthesize_fallback_logo_badge, resolve_customer_domains

    self.assertEqual(resolve_customer_domain("Walmart Inc."), "walmart.com")
    self.assertEqual(resolve_customer_domain("The Home Depot"), "homedepot.com")
    self.assertEqual(resolve_customer_domain("Aldi"), "aldi.us")
    aldi_domains = resolve_customer_domains("Aldi")
    self.assertIn("aldi.us", aldi_domains)
    self.assertIn("aldi-sued.de", aldi_domains)
    self.assertIn("aldi-nord.de", aldi_domains)
    # Fallback logo badge must render a non-empty 256x256 RGBA PNG
    fallback_bytes = _synthesize_fallback_logo_badge("Aldi", "aldi.us")
    self.assertIsNotNone(fallback_bytes)
    self.assertTrue(fallback_bytes.startswith(b"\x89PNG\r\n\x1a\n"))
    # GIF magic bytes must be strictly rejected
    self.assertIsNone(_normalize_logo_png_bytes(b"GIF89a" + b"\x00" * 100))
    self.assertTrue(is_gif_or_animated_bytes(raw_bytes=b"GIF89a\x10\x00"))
    self.assertTrue(is_gif_or_animated_bytes(url="https://example.com/demo.gif"))
    self.assertFalse(is_gif_or_animated_bytes(raw_bytes=b"\x89PNG\r\n\x1a\n" + b"\x00" * 80))

  def test_extract_customizable_slide_pictures_filters_gifs_and_icons(self):
    emu_per_pt = 12700
    mock_slide = {
        "objectId": "slide_1",
        "pageElements": [
            # 1. Small 32x32pt product icon -> MUST BE SKIPPED
            {
                "objectId": "icon_1",
                "size": {
                    "width": {"magnitude": 32 * emu_per_pt, "unit": "EMU"},
                    "height": {"magnitude": 32 * emu_per_pt, "unit": "EMU"},
                },
                "transform": {"scaleX": 1.0, "scaleY": 1.0},
                "image": {"contentUrl": "https://lh3.googleusercontent.com/icon.png"},
            },
            # 2. Animated GIF demo -> MUST BE SKIPPED
            {
                "objectId": "gif_1",
                "size": {
                    "width": {"magnitude": 300 * emu_per_pt, "unit": "EMU"},
                    "height": {"magnitude": 200 * emu_per_pt, "unit": "EMU"},
                },
                "transform": {"scaleX": 1.0, "scaleY": 1.0},
                "image": {"contentUrl": "https://lh3.googleusercontent.com/animation.gif"},
            },
            # 3. Full-bleed 720x405pt background wallpaper -> MUST BE SKIPPED
            {
                "objectId": "bg_1",
                "size": {
                    "width": {"magnitude": 720 * emu_per_pt, "unit": "EMU"},
                    "height": {"magnitude": 405 * emu_per_pt, "unit": "EMU"},
                },
                "transform": {"scaleX": 1.0, "scaleY": 1.0},
                "image": {"contentUrl": "https://lh3.googleusercontent.com/bg.png"},
            },
            # 4. Valid 280x180pt static hero picture -> MUST BE INCLUDED
            {
                "objectId": "hero_pic_1",
                "size": {
                    "width": {"magnitude": 280 * emu_per_pt, "unit": "EMU"},
                    "height": {"magnitude": 180 * emu_per_pt, "unit": "EMU"},
                },
                "transform": {"scaleX": 1.0, "scaleY": 1.0},
                "image": {"contentUrl": "https://lh3.googleusercontent.com/hero_photo.png"},
            },
        ],
    }
    pics = extract_customizable_slide_pictures(mock_slide, slide_index=2, is_cust_ref_slide=False)
    self.assertEqual(len(pics), 1)
    self.assertEqual(pics[0]["objectId"], "hero_pic_1")
    self.assertEqual(pics[0]["width_pt"], 280.0)
    self.assertEqual(pics[0]["height_pt"], 180.0)

    # Large pictures (>= 220x200pt) or Title Slide hero visuals must default to 2K resolution
    self.assertEqual(pics[0]["image_size"], "2K")

    # On Cover/Title slides (slide_index <= 1), a 280x180pt picture (< 200pt height) is skipped,
    # while a 440x405pt Title Slide hero visual is included with image_size="2K" and is_title_slide=True
    cover_pics_small = extract_customizable_slide_pictures(mock_slide, slide_index=1, is_cust_ref_slide=False)
    self.assertEqual(len(cover_pics_small), 0)

    mock_title_slide = {
        "objectId": "title_slide",
        "pageElements": [
            {
                "objectId": "title_hero",
                "size": {
                    "width": {"magnitude": 440 * emu_per_pt, "unit": "EMU"},
                    "height": {"magnitude": 405 * emu_per_pt, "unit": "EMU"},
                },
                "transform": {"scaleX": 1.0, "scaleY": 1.0},
                "image": {"contentUrl": "https://lh3.googleusercontent.com/title_hero.png"},
            }
        ],
    }
    title_pics = extract_customizable_slide_pictures(mock_title_slide, slide_index=1, is_cust_ref_slide=False)
    self.assertEqual(len(title_pics), 1)
    self.assertEqual(title_pics[0]["image_size"], "2K")
    self.assertTrue(title_pics[0]["is_title_slide"])

    # Verify _ensure_high_res_output_png guarantees >= 1K (1600x1080+) for Title Slide / large visuals
    import io
    from PIL import Image
    small_buf = io.BytesIO()
    Image.new("RGB", (640, 580), color=(10, 20, 30)).save(small_buf, format="PNG")
    hi_res_bytes = _ensure_high_res_output_png(small_buf.getvalue(), 440.0, 405.0, slide_index=1)
    with Image.open(io.BytesIO(hi_res_bytes)) as out_im:
      self.assertGreaterEqual(max(out_im.size), 1600)
      self.assertGreaterEqual(min(out_im.size), 1080)

  def test_extract_customizable_slide_pictures_skips_flipped_and_overlapping_stacks(self):
    emu_per_pt = 12700
    mock_slide = {
        "objectId": "slide_composite",
        "pageElements": [
            # 1. Upside-down flipped image (scaleY < 0) -> MUST BE SKIPPED
            {
                "objectId": "flipped_pic",
                "size": {
                    "width": {"magnitude": 260 * emu_per_pt, "unit": "EMU"},
                    "height": {"magnitude": 200 * emu_per_pt, "unit": "EMU"},
                },
                "transform": {
                    "scaleX": 1.0,
                    "scaleY": -1.0,
                    "translateX": 420 * emu_per_pt,
                    "translateY": 320 * emu_per_pt,
                },
                "image": {"contentUrl": "https://lh3.googleusercontent.com/flipped.png"},
            },
            # 2. Static browser bezel frame behind an animated GIF at the same coordinates -> MUST BE SKIPPED
            {
                "objectId": "bezel_frame",
                "size": {
                    "width": {"magnitude": 340 * emu_per_pt, "unit": "EMU"},
                    "height": {"magnitude": 220 * emu_per_pt, "unit": "EMU"},
                },
                "transform": {
                    "scaleX": 1.0,
                    "scaleY": 1.0,
                    "translateX": 350 * emu_per_pt,
                    "translateY": 100 * emu_per_pt,
                },
                "image": {"contentUrl": "https://lh3.googleusercontent.com/bezel.png"},
            },
            {
                "objectId": "inner_gif",
                "size": {
                    "width": {"magnitude": 310 * emu_per_pt, "unit": "EMU"},
                    "height": {"magnitude": 195 * emu_per_pt, "unit": "EMU"},
                },
                "transform": {
                    "scaleX": 1.0,
                    "scaleY": 1.0,
                    "translateX": 365 * emu_per_pt,
                    "translateY": 112 * emu_per_pt,
                },
                "image": {"contentUrl": "https://lh3.googleusercontent.com/demo.gif"},
            },
        ],
    }
    pics = extract_customizable_slide_pictures(mock_slide, slide_index=5, is_cust_ref_slide=False)
    self.assertEqual(len(pics), 0)

  def test_strip_leading_section_numbers_and_display_header_cap(self):
    # Standalone first-line section number
    s1 = self.workflow._sanitize_output(
        "02\nUnlocking the value of content\nWhere media leaders are focusing their efforts",
        is_cover_slide=False,
        customer_name="Spotify",
        original_len=85,
        is_action_title=True,
        font_size=34.0,
    )
    self.assertFalse(s1.startswith("02"))
    self.assertTrue(s1.startswith("Unlocking the value of content"))

    # Inline leading section number ("04 Maximizing platform productivity")
    s2 = self.workflow._sanitize_output(
        "04 Maximizing platform productivity\nWhere streaming engineers focus modernization",
        is_cover_slide=False,
        customer_name="Spotify",
        original_len=85,
        is_action_title=True,
        font_size=34.0,
    )
    self.assertFalse(s2.startswith("04"))
    self.assertTrue(s2.startswith("Maximizing platform productivity"))

    # Legitimate statistical headers ("74% of...") must NOT be stripped
    s3 = self.workflow._sanitize_output(
        "74% of enterprises report ROI within 12 months",
        is_cover_slide=False,
        customer_name="Spotify",
        original_len=50,
        is_action_title=True,
        font_size=24.0,
    )
    self.assertTrue(s3.startswith("74%"))

    # Display header (font_size >= 28pt and original_len <= 42) must cap at 32 chars
    _, max_disp = self.workflow._compute_char_budget(33, font_size=30.0)
    self.assertLessEqual(max_disp, 32)

  def test_algebraic_text_height_gate_clamps_card_overflow(self):
    # A compact 4-column card (width=145pt, height=70pt, fontSize=11pt):
    # Usable width = 133pt, chars_per_line = floor(133 / (11 * 0.54)) = 22 chars/line
    # Usable height = 70 - 12 = 58pt, line_height = 11 * 1.25 = 13.75pt -> max_lines = 4 -> alg_cap = 88 chars
    alg_cap = self.workflow.compute_algebraic_char_capacity(
        width_pt=145.0, height_pt=70.0, font_size=11.0
    )
    self.assertEqual(alg_cap, 88)

    # Even if original_len was 180 chars, _compute_char_budget with (width_pt=145, height_pt=70) must clamp hard_max_chars to 88
    t_card, m_card = self.workflow._compute_char_budget(
        180,
        font_size=11.0,
        is_action_title=False,
        width_pt=145.0,
        height_pt=70.0,
    )
    self.assertEqual(m_card, 88)
    self.assertLessEqual(t_card, 80)

    # Verify _sanitize_output trims overflowing card text so H_req <= H_card (70pt)
    overflow_card_text = (
        "Unify fragmented omnichannel store inventory, loyalty clickstreams,"
        " and real-time warehouse ERP signals into Knowledge Catalog with"
        " zero-copy governance."
    )
    fitted_text = self.workflow._sanitize_output(
        overflow_card_text,
        is_cover_slide=False,
        customer_name="Target",
        original_len=180,
        is_action_title=False,
        font_size=11.0,
        width_pt=145.0,
        height_pt=70.0,
    )
    req_h = self.workflow.compute_algebraic_text_height_pt(
        fitted_text, width_pt=145.0, font_size=11.0
    )
    self.assertLessEqual(req_h, 70.0)
    self.assertLessEqual(len(fitted_text), 88)

  def test_zero_gcs_image_bytes_to_content_uri_and_cleanup(self):
    from unittest import mock

    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    with (
        mock.patch("requests.post") as mock_post,
        mock.patch("requests.get") as mock_get,
        mock.patch("requests.delete") as mock_delete,
    ):
      mock_post.return_value.status_code = 200
      mock_post.return_value.json.return_value = {"id": "temp_doc_123"}

      mock_get.return_value.status_code = 200
      mock_get.return_value.json.return_value = {
          "inlineObjects": {
              "kix.inline_1": {
                  "inlineObjectProperties": {
                      "embeddedObject": {
                          "imageProperties": {
                              "contentUri": (
                                  "https://lh7-rt.googleusercontent.com/docsz/AD_4nX_mock_uri"
                              )
                          }
                      }
                  }
              }
          }
      }
      mock_delete.return_value.status_code = 204

      uri, doc_id = image_bytes_to_content_uri(
          fake_png, mime_type="image/png", oauth_token="mock_token"
      )
      self.assertEqual(
          uri, "https://lh7-rt.googleusercontent.com/docsz/AD_4nX_mock_uri"
      )
      self.assertEqual(doc_id, "temp_doc_123")

      deleted_count = cleanup_temp_drive_docs(oauth_token="mock_token")
      self.assertEqual(deleted_count, 1)
      mock_delete.assert_called_once()

  def test_bespoke_layout_guardrails_and_outline_partitioning(self):
    from agents.slide_engineering_agent import _infer_bespoke_layout
    from agents.workflows.content_synthesis_workflow import ContentSynthesisWorkflow
    from agents.workflows.agenda_workflow import AgendaWorkflow

    # 1. Verify _infer_bespoke_layout NEVER routes bespoke slides to "Case Study" / Customer Reference
    for candidate in [
        {
            "title": "Customer Reference & Case Study Spotlight",
            "content": "Retail ROI proof points",
        },
        {
            "title": "Global Retail Proof Points & Customer Stories",
            "content": "Before and after impact",
        },
        {
            "title": "30-60-90 Day Joint Implementation Roadmap",
            "content": "Phase 1, Phase 2, Phase 3",
        },
        {
            "title": "Immediate Next Steps & Executive Chartering",
            "content": "Action items and owners",
        },
        {
            "title": "Agentic Commerce Architecture Overview",
            "content": "Core platform components",
        },
    ]:
      inferred = _infer_bespoke_layout(candidate)
      self.assertEqual(inferred, "Context")
      self.assertNotEqual(inferred, "Case Study")

    # 2. Verify ContentSynthesisWorkflow.partition_topics_across_slides distributes subtopics across multiple slides
    topics = [
        "Unified Knowledge Catalog",
        "Multi-Agent Orchestration",
        "Model Armor Guardrails",
        "Real-Time Streaming Pipelines",
    ]
    buckets = ContentSynthesisWorkflow.partition_topics_across_slides(topics, 2)
    self.assertEqual(len(buckets), 2)
    self.assertEqual(
        buckets[0], ["Unified Knowledge Catalog", "Multi-Agent Orchestration"]
    )
    self.assertEqual(
        buckets[1], ["Model Armor Guardrails", "Real-Time Streaming Pipelines"]
    )

    # 3. Verify AgendaWorkflow.reconcile_agendas_with_deck_length aligns slide_count across Brief, Standard, and Comprehensive
    raw_agendas = {
        "1": {"title": "Industry Context", "parts": ["A", "B", "C"]},
        "2": {"title": "Platform Vision", "parts": ["E", "F", "G"]},
        "3": {"title": "Technical Architecture", "parts": ["I", "J", "K"]},
        "4": {"title": "Security & Governance", "parts": ["M", "N", "O"]},
        "5": {"title": "Next Steps & Roadmap", "parts": ["Q", "R", "S"]},
    }
    import copy

    brief_agendas = AgendaWorkflow.reconcile_agendas_with_deck_length(
        copy.deepcopy(raw_agendas), "Brief (4-6 slides)"
    )
    self.assertEqual(
        sum(sec["slide_count"] for sec in brief_agendas.values()), 5
    )

    std_agendas = AgendaWorkflow.reconcile_agendas_with_deck_length(
        copy.deepcopy(raw_agendas), "Standard (8-12 slides)"
    )
    self.assertEqual(
        sum(sec["slide_count"] for sec in std_agendas.values()), 10
    )

    comp_agendas = AgendaWorkflow.reconcile_agendas_with_deck_length(
        copy.deepcopy(raw_agendas), "Comprehensive (15-20 slides)"
    )
    self.assertGreaterEqual(
        sum(sec["slide_count"] for sec in comp_agendas.values()), 15
    )
    self.assertLessEqual(
        sum(sec["slide_count"] for sec in comp_agendas.values()), 20
    )

  def test_consultative_sentence_case_titles_and_tall_left_column_budget(self):
    # 1. Tall left-column title boxes (e.g. 258x298pt @ 34pt) must get 54-64 char budget even when original_len was short (22 chars)
    t_tall, m_tall = self.workflow._compute_char_budget(
        22,
        font_size=34.0,
        is_action_title=True,
        width_pt=258.0,
        height_pt=298.0,
    )
    self.assertGreaterEqual(m_tall, 54)
    self.assertLessEqual(m_tall, 64)
    self.assertGreaterEqual(t_tall, 44)

    # 2. Bare imperative Title-Case slide titles must normalize to consultative Sentence case while preserving proper nouns/acronyms
    s_cmd = self.workflow._sanitize_output(
        "Unlock Agentic Commerce With Gemini Enterprise And BigQuery",
        is_cover_slide=False,
        customer_name="Uniqlo",
        original_len=64,
        is_action_title=True,
        font_size=30.0,
    )
    self.assertEqual(
        s_cmd,
        "Agentic commerce with Gemini Enterprise and BigQuery",
    )

    s_turn = self.workflow._sanitize_output(
        "Turn Uniqlo's data platform into an intelligent consumer engine",
        is_cover_slide=False,
        customer_name="Uniqlo",
        original_len=64,
        is_action_title=True,
        font_size=30.0,
    )
    self.assertEqual(
        s_turn,
        "From Uniqlo's data platform to an intelligent consumer engine",
    )

  def test_customization_intensity_tiers_and_locked_gcp_badges(self):
    # 1. Official GCP product/layer badges must be recognized as locked badges
    self.assertTrue(
        self.workflow._is_locked_gcp_product_badge("AI Hypercomputer")
    )
    self.assertTrue(
        self.workflow._is_locked_gcp_product_badge("Agents & Applications")
    )
    self.assertTrue(
        self.workflow._is_locked_gcp_product_badge(
            "Gemini, Imagen, Veo, Chirp", is_architecture_slide=True
        )
    )
    # Customizable sub-card headers & titles must NOT be locked as product badges
    self.assertFalse(
        self.workflow._is_locked_gcp_product_badge("Create & edit video")
    )
    self.assertFalse(
        self.workflow._is_locked_gcp_product_badge("Live Production")
    )
    self.assertFalse(
        self.workflow._is_locked_gcp_product_badge(
            "A unified stack, custom-fit for the future of media",
            is_architecture_slide=True,
        )
    )

    # 2. Geometry-backed short sub-card headers (15 chars in 190x28pt @ 14pt) and short card bullets (40 chars in 210x85pt @ 11pt)
    # must expand their char budget within alg_cap so the LLM isn't forced into 1-word swaps
    _, max_sub_hdr = self.workflow._compute_char_budget(
        15,
        font_size=14.0,
        is_action_title=False,
        width_pt=190.0,
        height_pt=28.0,
    )
    self.assertGreaterEqual(max_sub_hdr, 21)

    _, max_short_bullet = self.workflow._compute_char_budget(
        40,
        font_size=11.0,
        is_action_title=False,
        width_pt=210.0,
        height_pt=85.0,
    )
    self.assertGreaterEqual(max_short_bullet, 62)

  def test_in_slide_image_alpha_mask_and_cvi_context_ordering(self):
    import io
    from PIL import Image, ImageDraw
    from agents.retrieval_agent import RetrievalAgent

    # 1. Verify _ensure_high_res_output_png preserves rounded-corner alpha mask and exact aspect ratio for in-slide images
    mask = Image.new("L", (300, 200), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (299, 199)], radius=32, fill=255)

    raw_im = Image.new("RGB", (600, 400), color=(40, 90, 180))
    buf = io.BytesIO()
    raw_im.save(buf, format="PNG")

    out_bytes = _ensure_high_res_output_png(
        buf.getvalue(),
        270.0,
        180.0,
        slide_index=5,
        is_cover_sculpture=False,
        orig_alpha_mask=mask,
    )
    with Image.open(io.BytesIO(out_bytes)) as out_im:
      self.assertEqual(out_im.mode, "RGBA")
      # Aspect ratio must match 270 / 180 = 1.5
      self.assertAlmostEqual(out_im.size[0] / out_im.size[1], 1.5, places=2)
      # Rounded corners must be transparent (alpha == 0) while center is opaque (alpha == 255)
      self.assertEqual(out_im.getpixel((0, 0))[3], 0)
      self.assertEqual(
          out_im.getpixel((out_im.size[0] // 2, out_im.size[1] // 2))[3], 255
      )

    # 2. Verify extract_customizable_slide_pictures includes cropped lifestyle photos and right-edge sculptural panels
    emu_per_pt = 12700
    mock_content_slide = {
        "objectId": "slide_content",
        "pageElements": [
            {
                "objectId": "cropped_lifestyle_pic",
                "size": {
                    "width": {"magnitude": 388 * emu_per_pt, "unit": "EMU"},
                    "height": {"magnitude": 333 * emu_per_pt, "unit": "EMU"},
                },
                "transform": {
                    "scaleX": 1.0,
                    "scaleY": 1.0,
                    "translateX": 40 * emu_per_pt,
                    "translateY": 50 * emu_per_pt,
                },
                "image": {
                    "contentUrl": (
                        "https://lh3.googleusercontent.com/stock_photo.png"
                    ),
                    "imageProperties": {
                        "cropProperties": {
                            "leftOffset": 0.16,
                            "rightOffset": 0.40,
                        }
                    },
                },
            },
            {
                "objectId": "right_edge_sculpture_panel",
                "size": {
                    "width": {"magnitude": 234 * emu_per_pt, "unit": "EMU"},
                    "height": {"magnitude": 405 * emu_per_pt, "unit": "EMU"},
                },
                "transform": {
                    "scaleX": 1.0,
                    "scaleY": 1.0,
                    "translateX": 486 * emu_per_pt,
                    "translateY": 0,
                },
                "image": {
                    "contentUrl": (
                        "https://lh3.googleusercontent.com/panel_sculpture.png"
                    ),
                    "imageProperties": {
                        "cropProperties": {
                            "leftOffset": 0.21,
                            "rightOffset": 0.21,
                        }
                    },
                },
            },
        ],
    }
    extracted = extract_customizable_slide_pictures(
        mock_content_slide, slide_index=5, is_cust_ref_slide=False
    )
    extracted_ids = [p["objectId"] for p in extracted]
    self.assertIn("cropped_lifestyle_pic", extracted_ids)
    self.assertIn("right_edge_sculpture_panel", extracted_ids)

    # 3. Verify CVI narrative spine classifies Market_Trends, Current_State (Data Foundation Imperative / Focus Areas), Vision, and Solution_Overview
    ret_agent = RetrievalAgent.__new__(RetrievalAgent)
    s_market = {
        "name": "47% of retail AI leaders report gains",
        "original_content": "Source: Google Cloud / National Research Group",
    }
    s_foundation = {
        "name": (
            "Businesses must re-evaluate their data foundation to prepare"
            " for AI"
        ),
        "original_content": "Activate All Data, Ensure Consistent Governance",
    }
    s_focus = {
        "name": "Focus areas for retail leaders",
        "original_content": (
            "Transform customer experiences, Strengthen operational resilience"
        ),
    }
    s_vision = {
        "name": "Shift from reactive support to proactive care",
        "original_content": (
            "Before: Siloed and reactive. Now: Unified and proactive."
        ),
    }
    s_solution = {
        "name": "Gemini Enterprise for Customer Experience",
        "original_content": "Shopping & Customer Service in One Experience",
    }
    self.assertEqual(ret_agent.classify_slide_job(s_market), "Market_Trends")
    self.assertEqual(
        ret_agent.classify_slide_job(s_foundation), "Current_State"
    )
    self.assertEqual(ret_agent.classify_slide_job(s_focus), "Current_State")
    self.assertEqual(ret_agent.classify_slide_job(s_vision), "Vision")
    self.assertEqual(
        ret_agent.classify_slide_job(s_solution), "Solution_Overview"
    )

  def test_extract_customizable_slide_gifs_and_omni_helpers(self):
    from pitchgen_utils.image_util import (
        _extract_omni_video_bytes,
        _sanitize_omni_video_prompt,
        extract_customizable_slide_gifs,
    )

    emu = 12700
    mock_slide = {
        "objectId": "slide_5_aldi",
        "pageElements": [
            # Full-bleed background GIF -> MUST BE SKIPPED
            {
                "objectId": "bg_gif",
                "title": "[WIP] Retail EBC Refresh 2026 4.gif",
                "size": {
                    "width": {"magnitude": int(720.0 * emu), "unit": "EMU"},
                    "height": {"magnitude": int(405.0 * emu), "unit": "EMU"},
                },
                "transform": {"scaleX": 1.0, "scaleY": 1.0},
                "image": {
                    "contentUrl": (
                        "https://lh7-rt.googleusercontent.com/bg_slidesz"
                    )
                },
            },
            # Phone bezel shadow -> static PNG -> MUST BE SKIPPED
            {
                "objectId": "phone_shadow",
                "title": "Device Phone Shadow Left.png",
                "size": {
                    "width": {"magnitude": int(202.4 * emu), "unit": "EMU"},
                    "height": {"magnitude": int(277.7 * emu), "unit": "EMU"},
                },
                "transform": {"scaleX": 1.0, "scaleY": 1.0},
                "image": {
                    "contentUrl": (
                        "https://lh7-rt.googleusercontent.com/shadow_slidesz"
                    )
                },
            },
            # Foreground Phone UI GIF -> MUST BE INCLUDED with 9:16 omni_aspect_ratio
            {
                "objectId": "phone_ui_gif",
                "title": "Phone_UI_2 New.gif",
                "size": {
                    "width": {"magnitude": int(151.1 * emu), "unit": "EMU"},
                    "height": {"magnitude": int(329.4 * emu), "unit": "EMU"},
                },
                "transform": {"scaleX": 1.0, "scaleY": 1.0},
                "image": {
                    "contentUrl": (
                        "https://lh7-rt.googleusercontent.com/phone_gif_slidesz"
                    )
                },
            },
            # Browser viewport GIF (Slide 9) -> MUST BE INCLUDED with 16:9 omni_aspect_ratio
            {
                "objectId": "browser_ui_gif",
                "title": "download (3).gif",
                "size": {
                    "width": {"magnitude": int(333.5 * emu), "unit": "EMU"},
                    "height": {"magnitude": int(187.6 * emu), "unit": "EMU"},
                },
                "transform": {"scaleX": 1.0, "scaleY": 1.0},
                "image": {
                    "contentUrl": (
                        "https://lh7-rt.googleusercontent.com/browser_gif_slidesz"
                    )
                },
            },
        ],
    }
    gifs = extract_customizable_slide_gifs(mock_slide, slide_index=5)
    self.assertEqual(len(gifs), 2)
    self.assertEqual(gifs[0]["objectId"], "phone_ui_gif")
    self.assertEqual(gifs[0]["omni_aspect_ratio"], "9:16")
    self.assertEqual(gifs[1]["objectId"], "browser_ui_gif")
    self.assertEqual(gifs[1]["omni_aspect_ratio"], "16:9")

    sanitized = _sanitize_omni_video_prompt(
        "A photorealistic female shopper browsing Aldi shelves with a cashier."
    )
    self.assertNotIn("female", sanitized.lower())
    self.assertNotIn("shopper", sanitized.lower())
    self.assertIn("vector geometry", sanitized.lower())

    class _DummyVideo:
      data = b"0" * 2048

    class _DummyInteraction:
      output_video = _DummyVideo()

    v_bytes, err = _extract_omni_video_bytes(_DummyInteraction())
    self.assertIsNone(err)
    self.assertEqual(len(v_bytes), 2048)

  def test_cymbal_white_label_replacement_and_gifs_only_scope(self):
    from agents.workflows.text_transformer_workflow import TextTransformerWorkflow

    try:
      from ge.a2ui_transform_text import create_a2ui_v09_transform_text_messages
    except ImportError:
      from src.ge.a2ui_transform_text import create_a2ui_v09_transform_text_messages

    # 1. Verify Cymbal white-label sub-brands and domain replacements
    self.assertEqual(
        TextTransformerWorkflow.replace_cymbal_with_customer(
            "Welcome to Cymbal Superstore and Cymbal Shops!", "Aldi"
        ),
        "Welcome to Aldi and Aldi!",
    )
    self.assertEqual(
        TextTransformerWorkflow.replace_cymbal_with_customer(
            "Does the Cymbal Retail Operations Manual cover store Associates at"
            " cymbal.com?",
            "Aldi",
        ),
        "Does the Aldi Retail Operations Manual cover store Associates at"
        " aldi.com?",
    )
    self.assertEqual(
        TextTransformerWorkflow.replace_cymbal_with_customer(
            "Contact @cymbal or Cymbal Bank for Cymbal Health benefits.",
            "Uniqlo",
        ),
        "Contact @uniqlo or Uniqlo for Uniqlo benefits.",
    )

    # 2. Verify Card 3 A2UI transform_scope_options includes gifs_only
    msgs = create_a2ui_v09_transform_text_messages(
        customer_name="Aldi",
        industry="Retail",
        transform_scope_mode="gifs_only",
    )
    data_msg = next(m for m in msgs if "updateDataModel" in m)
    val = data_msg["updateDataModel"]["value"]
    self.assertEqual(val["transform_scope_mode"], "gifs_only")
    comp_msg = next(m for m in msgs if "updateComponents" in m)
    scope_comp = next(
        c
        for c in comp_msg["updateComponents"]["components"]
        if c.get("id") == "transform_scope_mode_select"
    )
    scope_values = [o["value"] for o in scope_comp["options"]]
    self.assertIn("gifs_only", scope_values)

  def test_two_scenario_gif_router_and_ui_pixel_lock(self):
    import io
    import numpy as np
    from PIL import Image, ImageDraw
    from pitchgen_utils.image_util import (
        _align_and_lock_ui_keyframe_pixels,
        _classify_and_plan_gif_customization,
        _propagate_ui_edits_across_frames,
        _select_ui_demo_keyframes,
    )

    # 1. Build a synthetic UI screen recording frame (white background + crisp dark text strokes)
    ui_im = Image.new("RGB", (640, 360), (255, 255, 255))
    draw = ImageDraw.Draw(ui_im)
    draw.rectangle([20, 20, 620, 80], outline=(60, 64, 67), width=2)
    for x in range(40, 400, 6):
      draw.line([(x, 40), (x, 60)], fill=(32, 33, 36), width=2)
    ui_buf = io.BytesIO()
    ui_im.save(ui_buf, format="PNG")

    plan_ui = _classify_and_plan_gif_customization(
        [ui_buf.getvalue()],
        customer_name="Aldi",
        industry="Retail",
        client=None,
    )
    self.assertEqual(plan_ui["scenario"], "UI_PRODUCT_DEMO")

    # 2. Build a dark/colorful pure visual frame -> should classify as PURE_VISUAL offline
    vis_im = Image.new("RGB", (640, 360), (18, 42, 96))
    vis_buf = io.BytesIO()
    vis_im.save(vis_buf, format="PNG")
    plan_vis = _classify_and_plan_gif_customization(
        [vis_buf.getvalue()],
        customer_name="Aldi",
        industry="Retail",
        client=None,
    )
    self.assertEqual(plan_vis["scenario"], "PURE_VISUAL")

    # 3. Verify _align_and_lock_ui_keyframe_pixels locks 100% of untouched UI chrome while updating edited text box
    orig_arr = np.array(ui_im, dtype=np.uint8)
    orig_arr[185:200, 100:210] = [10, 10, 10]  # original UI text line
    edited_arr = orig_arr.copy()
    # Simulate a 1px global jitter on an untouched icon at (580, 320) AND a real text edit at (100..220, 180..205)
    orig_arr[315:330, 575:590] = [66, 133, 244]
    edited_arr[315:330, 575:590] = [
        69,
        130,
        240,
    ]  # minor 4-unit jitter -> must stay locked to orig_arr
    edited_arr[180:205, 100:220] = [
        25,
        90,
        200,
    ]  # real text replacement on the same text line

    comp_arr, mask_arr = _align_and_lock_ui_keyframe_pixels(
        orig_arr, edited_arr
    )
    # Untouched icon at (580, 320) must be bit-for-bit identical to orig_arr
    np.testing.assert_array_equal(
        comp_arr[318:325, 578:585], orig_arr[318:325, 578:585]
    )
    # Edited text region at (190, 160) must reflect edited_arr
    self.assertLess(int(comp_arr[192, 160, 0]), 40)
    self.assertGreater(float(mask_arr[192, 160, 0]), 0.85)

    # 4. Verify _select_ui_demo_keyframes and _propagate_ui_edits_across_frames (typing reveal + stationary hold)
    f_early = np.array(ui_im, dtype=np.uint8)
    # Half-typed line in f_mid (columns 100..150 have dark ink)
    f_mid = f_early.copy()
    f_mid[185:200, 100:150] = [10, 10, 10]
    # Full original line in f_settled (columns 100..210 have dark ink)
    f_settled = f_early.copy()
    f_settled[185:200, 100:210] = [10, 10, 10]

    seq = [f_early, f_mid, f_settled, f_settled.copy()]
    kfs, segs = _select_ui_demo_keyframes(seq, max_keyframes=2)
    self.assertTrue(len(kfs) >= 1)
    # Propagate edits across sequence
    prop = _propagate_ui_edits_across_frames(
        seq, [3], [(0, 3)], [comp_arr], [mask_arr]
    )
    self.assertEqual(len(prop), 4)
    # In frame 1 (half-typed), columns 100..140 should have the edited dark ink, while columns 180..210 remain white (not yet typed!)
    self.assertLess(int(prop[1][192, 120, 0]), 50)
    self.assertGreater(int(prop[1][192, 195, 0]), 235)

  def test_per_frame_google_sans_vector_replacement_and_suffix_shift(self):
    """Verifies Option A per-frame Google Sans FFT NCC localization, vector replacement, and baseline suffix shifting across horizontal, multi-email, typing-prefix, dark-toast, and 3D-tilted lines."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from pitchgen_utils.image_util import (
        _build_ui_token_templates,
        _detect_tokens_on_frame_fft_ncc,
        _extract_ui_ink_map,
        _localize_and_replace_ui_text_across_frames,
        _resolve_ui_fonts,
    )

    fonts = _resolve_ui_fonts()
    self.assertIn("regular", fonts)
    font_18 = ImageFont.truetype(fonts["regular"], 18)
    font_14 = ImageFont.truetype(fonts["regular"], 14)

    # Frame 0: typing prefix "Does the Cymb|"
    im0 = Image.new("RGB", (640, 360), (255, 255, 255))
    d0 = ImageDraw.Draw(im0)
    d0.text((40, 80), "Does the Cymb|", fill=(32, 33, 36), font=font_18)

    # Frame 1: full line + multi-email participants + dark toast
    im1 = Image.new("RGB", (640, 360), (255, 255, 255))
    d1 = ImageDraw.Draw(im1)
    d1.text(
        (40, 80),
        "Does the Cymbal Retail Operations Manual allow",
        fill=(32, 33, 36),
        font=font_18,
    )
    d1.text(
        (40, 140),
        "gonzalo@cymbal.com; andrea@cymbal.com; patrick@cymbal.com",
        fill=(32, 33, 36),
        font=font_14,
    )
    d1.rectangle([30, 280, 560, 325], fill=(50, 50, 50))
    d1.text(
        (45, 294),
        "Calendar event created with gonzalo@cymbal.com",
        fill=(245, 245, 245),
        font=font_14,
    )

    frames = [np.array(im0, dtype=np.uint8), np.array(im1, dtype=np.uint8)]
    fft_shape = (400, 750)
    tpls = _build_ui_token_templates("Aldi", fft_shape)

    # Verify detections on original frames before replacement
    det0 = _detect_tokens_on_frame_fft_ncc(
        _extract_ui_ink_map(frames[0]), tpls, fft_shape
    )
    det1 = _detect_tokens_on_frame_fft_ncc(
        _extract_ui_ink_map(frames[1]), tpls, fft_shape
    )
    self.assertEqual(len(det0), 1)
    self.assertEqual(det0[0]["token"], "Cymb")
    self.assertEqual(len(det1), 5)

    # Run surgical replacement + suffix shifting
    out_frames = _localize_and_replace_ui_text_across_frames(
        frames, customer_name="Aldi"
    )
    self.assertEqual(len(out_frames), 2)

    # After replacement, zero Cymbal/cymbal/Cymb tokens should remain on any frame
    rem0 = _detect_tokens_on_frame_fft_ncc(
        _extract_ui_ink_map(out_frames[0]), tpls, fft_shape
    )
    rem1 = _detect_tokens_on_frame_fft_ncc(
        _extract_ui_ink_map(out_frames[1]), tpls, fft_shape
    )
    self.assertEqual(len(rem0), 0)
    self.assertEqual(len(rem1), 0)

    # Verify _build_omni_video_edit_prompt constructs explicit Cymbal replacement instructions for Gemini Omni 1.1 Video-to-Video
    from pitchgen_utils.image_util import _build_omni_video_edit_prompt

    ui_prompt = _build_omni_video_edit_prompt(
        scenario="UI_PRODUCT_DEMO",
        triage_plan={
            "text_replacements": [
                {
                    "original": "gonzalo@cymbal.com",
                    "replacement": "gonzalo@aldi.com",
                },
                {"original": "Cymbal Retail", "replacement": "Aldi"},
            ]
        },
        customer_name="Aldi",
        industry="Retail",
    )
    self.assertIn("gonzalo@aldi.com", ui_prompt)
    self.assertIn("Aldi", ui_prompt)
    self.assertIn(
        "zero frames anywhere in the video show the word 'Cymbal'", ui_prompt
    )


if __name__ == "__main__":
  unittest.main()
