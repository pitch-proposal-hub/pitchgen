"""Unit tests for Gemini Enterprise A2UI 4 Core Workflows in ge/."""

import os
import sys
import unittest

pitchgen_dir = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, pitchgen_dir)
sys.path.insert(0, os.path.join(pitchgen_dir, "src"))

try:
  from ge import a2ui
except ImportError:
  from src.ge import a2ui


class TestGeA2uiWorkflows(unittest.TestCase):
  """Tests for the 4 core A2UI workflows mapped into Gemini Enterprise."""

  def test_workflow_0_welcome_intro_card(self):
    """Workflow 0: Welcome & Intro Card with feature quick actions."""
    card = a2ui.create_welcome_intro_card(user_ldap="seller_user")
    self.assertEqual(card["type"], "card")
    self.assertEqual(card["metadata"]["mimeType"], a2ui.A2UI_MIME_TYPE)
    self.assertIn("Welcome to PitchGen", card["title"])
    self.assertIn("seller_user", card["title"])

    # Verify quick actions: Outline only appears after completing intake!
    quick_actions_sec = next(
        s for s in card["sections"] if s["type"] == "quick_actions"
    )
    act_names = [
        a["action"]["actionName"] for a in quick_actions_sec["actions"]
    ]
    self.assertIn("intake", act_names)
    self.assertNotIn("outline", act_names)
    self.assertIn("search", act_names)
    self.assertIn("diagram", act_names)
    self.assertIn("transform", act_names)

  def test_workflow_1_gtm_intake_card(self):
    """Workflow 1: GTM Intake Card covers popup fields & 3 deck strategies."""
    card = a2ui.create_gtm_intake_card(
        user_prompt="Build an enterprise retail AI modernization pitch.",
        customer_name="Target",
        industry="Retail & CPG",
        sales_play="Scale AI Apps & Agents",
        audience="C-Level / Executive Leadership",
        region="AMER",
        er_number="006Kf00000M0PJcIAN",
        deck_strategy="smart_hybrid",
        deck_length="Standard (8-12 slides)",
        context_file_url="https://drive.google.com/file/d/sample_rfp",
        context_file_name="Target_RFP_2026.pdf",
    )

    self.assertEqual(card["type"], "card")
    self.assertEqual(card["metadata"]["mimeType"], a2ui.A2UI_MIME_TYPE)
    self.assertIn("Target", card["title"])

    # Verify stepper and form sections
    stepper_section = card["sections"][0]
    self.assertEqual(stepper_section["type"], "stepper")
    self.assertEqual(len(stepper_section["steps"]), 3)

    form_section = card["sections"][1]
    self.assertEqual(form_section["type"], "form")
    field_ids = [f["id"] for f in form_section["fields"]]

    expected_fields = [
        "user_prompt",
        "customer_name",
        "er_number",
        "sales_play",
        "industry",
        "audience",
        "region",
        "deck_strategy",
        "deck_length",
        "context_file_attachment",
    ]
    for ef in expected_fields:
      self.assertIn(ef, field_ids)

    # microindustry has been removed from intake
    self.assertNotIn("microindustry", field_ids)

    # Verify exactly 3 canonical deck strategies are available as dropdown select (no legacy duplicate)
    strat_field = next(
        f for f in form_section["fields"] if f["id"] == "deck_strategy"
    )
    self.assertEqual(strat_field["type"], "select")
    strat_values = [opt["value"] for opt in strat_field["options"]]
    self.assertEqual(len(strat_values), 3)
    self.assertIn("smart_hybrid", strat_values)
    self.assertIn("cloudhub", strat_values)
    self.assertIn("bespoke_custom", strat_values)
    strat_labels = [opt["label"] for opt in strat_field["options"]]
    self.assertTrue(all("Legacy ID" not in lbl for lbl in strat_labels))

    # Verify dropdown types for regions, audience, sales play, industry, and deck length
    field_map = {f["id"]: f for f in form_section["fields"]}
    self.assertEqual(field_map["region"]["type"], "select")
    self.assertIn("AMER", field_map["region"]["options"])
    self.assertEqual(field_map["audience"]["type"], "select")
    self.assertEqual(field_map["sales_play"]["type"], "select")
    self.assertEqual(field_map["industry"]["type"], "select")
    self.assertEqual(field_map["deck_length"]["type"], "select")

    # Verify generate_outline action button
    action_section = next(s for s in card["sections"] if s["type"] == "actions")
    button = next(
        b
        for b in action_section["buttons"]
        if b["action"]["actionName"] == "generate_outline"
    )
    self.assertEqual(button["action"]["actionName"], "generate_outline")
    self.assertEqual(button["action"]["parameters"]["customer_name"], "Target")
    self.assertEqual(
        button["action"]["parameters"]["deck_strategy"], "smart_hybrid"
    )

  def test_workflow_1_outline_review_card(self):
    """Workflow 1 (Step 2): Outline Review Card before slide synthesis."""
    agenda_sections = [
        {
            "title": "Executive Summary",
            "subtopics": ["Strategic Vision", "Market Pressures"],
            "slide_count": 1,
        },
        {
            "title": "Current State Architecture",
            "subtopics": ["Legacy Silos", "Latency Bottlenecks"],
            "slide_count": 2,
        },
        {
            "title": "Google Cloud Solution & ROI",
            "subtopics": ["Vertex AI", "BigQuery", "3.2x ROI"],
            "slide_count": 2,
        },
    ]

    card = a2ui.create_outline_review_card(
        customer_name="LVMH",
        agenda_sections=agenda_sections,
        deck_strategy="smart_hybrid",
        executive_summary="Tailored luxury clienteling transformation.",
    )

    self.assertEqual(card["type"], "card")
    self.assertIn("LVMH", card["title"])
    self.assertIn("Smart Hybrid", card["subtitle"])

    # Verify agenda items
    agenda_section = card["sections"][1]
    self.assertEqual(agenda_section["type"], "agenda_list")
    self.assertEqual(len(agenda_section["items"]), 3)
    self.assertEqual(agenda_section["items"][0]["title"], "Executive Summary")

    # Verify approve action
    actions = card["sections"][2]["buttons"]
    approve_action = actions[0]["action"]
    self.assertEqual(
        approve_action["actionName"], "approve_outline_and_generate"
    )
    self.assertEqual(approve_action["parameters"]["customer_name"], "LVMH")

  def test_workflow_2_slide_search_panel_card(self):
    """Workflow 2: Side Panel Slide Search Results & 1-Click Insertion."""
    sample_results = [
        {
            "slide_id": "spanner_arch_1",
            "title": "Cloud Spanner Global Consistency",
            "category": "Architecture",
            "slide_job": "Solution_Overview",
            "thumbnail_url": (
                "https://storage.googleapis.com/sample_bucket/thumb1.png"
            ),
            "presentation_id": "pres_abc123",
        },
        {
            "slide_id": "retail_cvi_proof",
            "title": "Major Retailer 40% TCO Reduction",
            "category": "Customer Proof Point",
            "slide_job": "Proof_Points",
            "thumbnail_url": (
                "https://storage.googleapis.com/sample_bucket/thumb2.png"
            ),
            "presentation_id": "pres_xyz789",
        },
    ]

    card = a2ui.create_slide_search_panel_card(
        search_query="retail spanner migration",
        results=sample_results,
        target_presentation_id="active_deck_456",
        target_slide_position=3,
    )

    self.assertEqual(card["type"], "card")
    self.assertEqual(card["surface"], "canvas_side_panel")
    self.assertIn("retail spanner migration", card["subtitle"])

    tiles = card["sections"][0]["items"]
    self.assertEqual(len(tiles), 2)
    self.assertEqual(tiles[0]["slide_job"], "Solution_Overview")
    self.assertEqual(tiles[1]["slide_job"], "Proof_Points")

    # Verify insert action
    insert_btn = tiles[0]["actions"][0]
    self.assertEqual(insert_btn["action"]["actionName"], "insert_library_slide")
    self.assertEqual(
        insert_btn["action"]["parameters"]["template_slide_id"],
        "spanner_arch_1",
    )
    self.assertEqual(
        insert_btn["action"]["parameters"]["target_presentation_id"],
        "active_deck_456",
    )

  def test_workflow_3_text_transform_account_augmentation(self):
    """Workflow 3: Text Augmentation & Customization governed by slide_jobs."""
    card = a2ui.create_text_transform_card(
        presentation_id="deck_target_789",
        scope="current_slide",
        selected_slide_index=4,
        slide_job="Business_Value",
        customer_name="Deutsche Bank",
        region="EMEA (GDPR/DORA)",
        audience="C-Level / Executive (EBITDA, TCO, Strategic Differentiators)",
        language="German",
    )

    self.assertEqual(card["type"], "card")
    self.assertIn("100% Full Customization", card["subtitle"])

    # Verify Canvas Preview is attached to showcase the active deck
    self.assertIn("canvasPreview", card)
    self.assertIn("deck_target_789", card["canvasPreview"]["workspaceUri"])

    # Verify Slide Job Governance banner
    info_banner = card["sections"][0]
    self.assertIn("financial metrics", info_banner["text"].lower())

    # Verify form fields
    form_fields = card["sections"][1]["fields"]
    field_ids = [f["id"] for f in form_fields]
    self.assertIn("presentation_id", field_ids)
    self.assertIn("transform_scope", field_ids)
    self.assertIn("target_customer", field_ids)
    self.assertIn("target_region", field_ids)
    self.assertIn("target_audience", field_ids)
    self.assertNotIn("target_microindustry", field_ids)
    self.assertNotIn("microindustry", field_ids)
    self.assertIn("slide_job", field_ids)
    self.assertIn("target_language", field_ids)

    # Verify dropdown types and options for transformation scope, regions, audience, and languages
    field_map = {f["id"]: f for f in form_fields}
    self.assertEqual(field_map["transform_scope"]["type"], "select")
    self.assertTrue(len(field_map["transform_scope"]["options"]) >= 3)
    self.assertEqual(field_map["target_region"]["type"], "select")
    self.assertIn("AMER", field_map["target_region"]["options"])
    self.assertEqual(field_map["target_audience"]["type"], "select")
    self.assertTrue(len(field_map["target_audience"]["options"]) >= 3)
    self.assertEqual(field_map["slide_job"]["type"], "select")
    self.assertEqual(field_map["target_language"]["type"], "select")
    self.assertIn("German", field_map["target_language"]["options"])
    self.assertIn("English", field_map["target_language"]["options"])

    # Verify action execution parameters
    action = card["sections"][2]["buttons"][0]["action"]
    self.assertEqual(action["actionName"], "transform_slide_text")
    self.assertEqual(action["parameters"]["customer_name"], "Deutsche Bank")
    self.assertEqual(action["parameters"]["slide_job"], "Business_Value")
    self.assertEqual(action["parameters"]["language"], "German")

  def test_workflow_3_provide_deck_prompt_when_no_deck(self):
    """Workflow 3: Provide presentation prompt card when no active canvas deck."""
    prompt_card = a2ui.create_provide_deck_prompt_card(
        customer_name="Home Depot"
    )
    self.assertEqual(prompt_card["type"], "card")
    self.assertIn("Provide Presentation", prompt_card["title"])
    form_fields = prompt_card["sections"][1]["fields"]
    field_ids = [f["id"] for f in form_fields]
    self.assertIn("presentation_url", field_ids)

    actions = prompt_card["sections"][2]["buttons"]
    action_names = [a["action"]["actionName"] for a in actions]
    self.assertIn("transform", action_names)
    self.assertIn("intake", action_names)

  def test_workflow_3_proof_points_metric_integrity_governance(self):
    """Workflow 3: Proof Points enforces verified metric protection."""
    card = a2ui.create_text_transform_card(
        presentation_id="deck_sample_123",
        scope="current_slide",
        selected_slide_index=2,
        slide_job="Proof_Points",
        customer_name="Siemens",
    )

    self.assertIn("Metric Integrity Protected", card["subtitle"])
    info_banner = card["sections"][0]["text"]
    self.assertIn("verbatim", info_banner)

  def test_workflow_4_nano_banana_card(self):
    """Workflow 4: Nano Banana visual diagram & architecture synthesis."""
    card = a2ui.create_nano_banana_card(
        presentation_id="deck_spanner_999",
        target_slide_index=3,
        selected_model="nano_banana_pro",
        visual_style=(
            "Google Cloud Modern Architecture (Flat vector, precise topology)"
        ),
        reference_image_url="https://drive.google.com/sample_diagram.png",
    )

    self.assertEqual(card["type"], "card")
    self.assertEqual(card["title"], "Nano Banana Studio")

    # Verify model options
    form_fields = card["sections"][1]["fields"]
    model_field = next(f for f in form_fields if f["id"] == "nano_banana_model")
    model_ids = [opt["value"] for opt in model_field["options"]]
    self.assertEqual(
        model_ids,
        ["nano_banana_pro", "nano_banana", "gemini-nano-banana-2.1"],
    )

    # Verify action
    action = card["sections"][2]["buttons"][0]["action"]
    self.assertEqual(action["actionName"], "transform_with_nano_banana")
    self.assertEqual(
        action["parameters"]["presentation_id"], "deck_spanner_999"
    )
    self.assertEqual(action["parameters"]["model"], "nano_banana_pro")

  def test_identity_resolution_with_oauth_token(self):
    """Test OAuth token exchange and automatic LDAP derivation."""
    from unittest.mock import patch

    mock_email = "testuser@example.com"
    with patch.object(
        a2ui, "get_email_from_oauth_token", return_value=mock_email
    ):
      context = type("MockContext", (), {"state": {}})()
      email, ldap = a2ui.resolve_ge_user_identity(
          tool_context=context,
          access_token="mock_bearer_token_12345",
      )
      self.assertEqual(email, "testuser@example.com")
      self.assertEqual(ldap, "testuser")
      # Verify cached on context.state
      self.assertEqual(context.state.get("user_email"), "testuser@example.com")
      self.assertEqual(context.state.get("user_ldap"), "testuser")

  def test_identity_resolution_context_caching(self):
    """Test that existing cached identity is returned immediately without exchange."""
    context = type(
        "MockContext",
        (),
        {"state": {"user_email": "cached@example.com", "user_ldap": "cached"}},
    )()
    email, ldap = a2ui.resolve_ge_user_identity(tool_context=context)
    self.assertEqual(email, "cached@example.com")
    self.assertEqual(ldap, "cached")

  def test_format_a2ui_deck_card_auto_resolves_ldap(self):
    """Test format_a2ui_deck_card auto-populates user_ldap if not provided."""
    deck_url = "https://docs.google.com/presentation/d/SAMPLE_TEST_PRESENTATION_ID_000000000004/edit"
    res = a2ui.format_a2ui_deck_card(
        deck_url=deck_url,
        customer_name="LVMH",
        user_ldap="",  # empty
    )
    self.assertEqual(res["status"], "success")
    # Verify card text contains a resolved account rather than blank
    card_text = res["a2ui_card"]["sections"][0]["content"]
    self.assertIn("edit permissions granted", card_text)

  def test_server_test_harness_and_endpoints(self):
    """Test local visual test harness server and workflow dispatching."""
    try:
      from ge import server
    except ImportError:
      from ge import server

    import asyncio

    # 1. Health check
    health = asyncio.run(server.health_check())
    self.assertEqual(health["status"], "healthy")

    # 2. HTML visual test harness route
    html = asyncio.run(server.local_a2ui_tester())
    self.assertIn("PitchGen - A2UI Visual Test Harness", html)
    self.assertIn("GTM Intake Card", html)
    self.assertIn("Canvas Panel Preview", html)
    self.assertIn("canvas-panel", html)
    self.assertIn("WS_SLIDES", html)

    # 3. Direct identity test endpoint
    id_res = asyncio.run(
        server.test_identity_resolution(
            server.IdentityTestRequest(fallback_ldap="test_ldap")
        )
    )
    self.assertEqual(id_res["status"], "success")
    self.assertEqual(id_res["user_ldap"], "test_ldap")

    # 4. Turn dispatcher for all 5 core workflows
    intake_res = server.execute_pitchgen_turn("intake", {}, user_ldap="seller_user")
    self.assertEqual(len(intake_res["a2ui_payloads"]), 1)
    self.assertEqual(intake_res["a2ui_payloads"][0]["type"], "card")

    outline_res = server.execute_pitchgen_turn(
        "outline", {"customer_name": "Nike"}, user_ldap="seller_user"
    )
    self.assertIn("Nike", outline_res["a2ui_payloads"][0]["title"])

    search_res = server.execute_pitchgen_turn(
        "search", {"search_query": "Vertex AI"}, user_ldap="seller_user"
    )
    self.assertIn("CloudHub", search_res["text"])

    diag_res = server.execute_pitchgen_turn("diagram", {}, user_ldap="seller_user")
    self.assertIn("Nano Banana", diag_res["text"])

    # 4a. Transform with NO active deck on Canvas -> prompts user to provide presentation
    transform_prompt = server.execute_pitchgen_turn(
        "transform", {}, user_ldap="seller_user"
    )
    self.assertIn("No Active Deck", transform_prompt["text"])
    self.assertIn(
        "Provide Presentation", transform_prompt["a2ui_payloads"][0]["title"]
    )

    # 4b. Transform WITH active deck on Canvas -> returns text transform card
    transform_res = server.execute_pitchgen_turn(
        "transform",
        {"presentation_id": "deck_sample_123", "tone": "EXECUTIVE"},
        user_ldap="seller_user",
    )
    self.assertIn("Executive Tone", transform_res["text"])
    self.assertIn("deck_sample_123", transform_res["text"])

    intro_res = server.execute_pitchgen_turn("intro", {}, user_ldap="seller_user")
    self.assertIn("Welcome to PitchGen", intro_res["a2ui_payloads"][0]["title"])

    # 5. Outline Approval & Full Deck Generation showcasing in Canvas Panel
    gen_res = server.execute_pitchgen_turn(
        "approve_outline_and_generate",
        {"customer_name": "Target", "deck_strategy": "smart_hybrid"},
        user_ldap="seller_user",
    )
    self.assertIn("Target", gen_res["text"])
    self.assertIn("Canvas Panel", gen_res["text"])
    self.assertTrue(gen_res["a2ui_payloads"][0]["canvasPreview"]["autoOpen"])
    self.assertEqual(
        gen_res["a2ui_payloads"][0]["canvasPreview"]["canvasType"], "WS_SLIDES"
    )

    deck_res = server.execute_pitchgen_turn("hello", {}, user_ldap="seller_user")
    self.assertIn("presentation deck is ready", deck_res["text"])
    self.assertTrue(deck_res["a2ui_payloads"][0]["canvasPreview"]["supported"])
    self.assertTrue(deck_res["a2ui_payloads"][0]["canvasPreview"]["autoOpen"])

  def test_interactive_outline_editing_and_refinement(self):
    """Workflow 1 (Step 2): Test inline editable outline and natural language refinement."""
    try:
      from ge import server
    except ImportError:
      from ge import server

    # 1. Verify create_outline_review_card metadata
    agenda_sections = [
        {
            "title": "Custom Section 1",
            "subtopics": ["A", "B"],
            "slide_count": 2,
        },
        {
            "title": "Custom Section 2",
            "subtopics": ["C", "D"],
            "slide_count": 3,
        },
    ]
    card = a2ui.create_outline_review_card(
        customer_name="Nordstrom",
        agenda_sections=agenda_sections,
    )
    agenda_sec = card["sections"][1]
    self.assertTrue(agenda_sec["editable"])
    self.assertTrue(agenda_sec["allow_add"])
    self.assertEqual(agenda_sec["deck_strategy"], "smart_hybrid")
    self.assertTrue(
        any(
            s["id"] == "bespoke_custom"
            for s in agenda_sec["available_strategies"]
        )
    )
    self.assertIn("+ Security & Zero Trust", agenda_sec["refinement_presets"])
    self.assertEqual(len(agenda_sec["items"]), 2)
    self.assertTrue(agenda_sec["items"][0]["editable"])

    # Verify modify_deck_strategy does NOT exist as an action button (now an inline dropdown)
    action_names = [
        b["action"]["actionName"] for b in card["sections"][2]["buttons"]
    ]
    self.assertNotIn("modify_deck_strategy", action_names)

    # 2. Refine outline with natural language prompt "include enterprise security and zero trust"
    refined = server.execute_pitchgen_turn(
        "refine_outline",
        {
            "customer_name": "Nordstrom",
            "agenda_sections": agenda_sections,
            "refine_prompt": (
                "Please include enterprise security and zero trust governance"
            ),
        },
        user_ldap="seller_user",
    )
    self.assertIn("Security", refined["text"])
    refined_card = refined["a2ui_payloads"][0]
    refined_items = refined_card["sections"][1]["items"]
    titles = [item["title"] for item in refined_items]
    self.assertTrue(any("Security" in t for t in titles))

    # 3. Approve outline with customized sections and verify custom summary in deck generation
    approve_res = server.execute_pitchgen_turn(
        "approve_outline_and_generate",
        {
            "customer_name": "Nordstrom",
            "agenda_sections": refined_items,
            "deck_strategy": "smart_hybrid",
        },
        user_ldap="seller_user",
    )
    self.assertIn("customized sections", approve_res["text"])
    self.assertIn("Nordstrom", approve_res["text"])

  def test_gcbp_canonical_a2ui_presentation_and_canvas(self):
    """Verify alignment with A2UI v0.9 Canvas + IFrameUrl and v0.8 WebFrameUrl fallback."""
    # 1. Material Symbols token validation per GCBP generic canvas spec
    self.assertEqual(a2ui.validate_card_icon("slideshow"), "slideshow")
    self.assertEqual(a2ui.validate_card_icon("edit_note"), "edit_note")
    self.assertEqual(
        a2ui.validate_card_icon("invalid icon with spaces!"), "slideshow"
    )

    # 2. Default A2UI v0.9+v0.8 provide-and-open-canvas messages (Canvas + IFrameUrl and WebFrameUrl)
    deck_url = "https://docs.google.com/presentation/d/deck_gcbp_123/edit"
    messages = a2ui.create_a2ui_canvas_messages(
        deck_url=deck_url,
        card_title="Google Cloud Strategic Pitch",
        card_description="Live executive presentation in Canvas",
        card_icon="slideshow",
        surface_id="canvas_surface_test_1",
        auto_open=True,
    )
    self.assertEqual(len(messages), 4)
    self.assertEqual(messages[0]["version"], "v0.9")
    self.assertEqual(
        messages[0]["createSurface"]["surfaceId"], "canvas_surface_test_1"
    )
    self.assertEqual(
        messages[0]["createSurface"]["catalogId"],
        a2ui.A2UI_MATERIAL_CATALOG_ID,
    )

    comps = messages[1]["updateComponents"]["components"]
    comp_map = {c["id"]: c for c in comps}
    self.assertEqual(comp_map["root"]["component"], "Canvas")
    self.assertEqual(
        comp_map["root"]["cardTitle"], "Google Cloud Strategic Pitch"
    )
    self.assertEqual(comp_map["root"]["cardIcon"], "slideshow")
    self.assertTrue(comp_map["root"]["autoOpen"])
    self.assertIn("slides-iframe", comp_map["root"]["children"])
    self.assertEqual(comp_map["slides-iframe"]["component"], "IFrameUrl")
    self.assertIn("deck_gcbp_123/embed", comp_map["slides-iframe"]["url"])

    # Verify v0.8 WebFrameUrl messages are also emitted alongside v0.9
    self.assertEqual(
        messages[2]["beginRendering"]["surfaceId"], "canvas_surface_test_1_v08"
    )

    # 2b. Verify v0.8 fallback when version="v0.8" is explicitly passed
    v08_messages = a2ui.create_a2ui_canvas_messages(
        deck_url=deck_url,
        card_title="Google Cloud Strategic Pitch",
        card_description="Live executive presentation in Canvas",
        card_icon="slideshow",
        surface_id="canvas_surface_test_v08",
        auto_open=True,
        version="v0.8",
    )
    self.assertEqual(
        v08_messages[0]["beginRendering"]["surfaceId"],
        "canvas_surface_test_v08",
    )

    # 3. Canonical close-canvas command (v0.9)
    delete_msg = a2ui.create_a2ui_delete_surface_message(
        "canvas_surface_test_1"
    )
    self.assertEqual(delete_msg[0]["version"], "v0.9")
    self.assertEqual(
        delete_msg[0]["deleteSurface"]["surfaceId"], "canvas_surface_test_1"
    )

    # 4. A2A DataPart wrapping per GCBP EPE standard (<a2a_datapart_json>)
    datapart_str = a2ui.format_a2ui_datapart({"test_key": "test_val"})
    self.assertTrue(datapart_str.startswith(a2ui.A2A_DATA_PART_START_TAG))
    self.assertTrue(datapart_str.endswith(a2ui.A2A_DATA_PART_END_TAG))
    self.assertIn("application/json+a2ui", datapart_str)
    self.assertIn("test_key", datapart_str)

    # 5. Integrated deck card contains canonical canvasMessages
    deck_card_res = a2ui.format_a2ui_deck_card(
        deck_url=deck_url,
        customer_name="Target",
        user_ldap="seller_user",
    )
    self.assertIn("canvas_messages", deck_card_res)
    self.assertEqual(len(deck_card_res["canvas_messages"]), 4)
    self.assertIn("canvasMessages", deck_card_res["a2ui_card"])

    # 6. Canvas artifact contains canonical canvasMessages
    artifact = a2ui.create_ge_canvas_artifact(
        deck_url=deck_url,
        customer_name="Target",
    )
    self.assertIn("canvasMessages", artifact)

  def test_a2ui_v09_canonical_messages(self):
    """Verifies canonical A2UI v0.9 Material NG message generation for Gemini Enterprise."""
    # 1. Intake messages (v0.9: createSurface + updateDataModel + updateComponents)
    intake_msgs = a2ui.create_a2ui_v09_intake_messages(
        user_prompt="Modernize retail analytics with Vertex AI.",
        customer_name="Target Corporation",
        industry="Retail & CPG",
        er_number="006Kf00000M0PJcIAN",
        deck_strategy="smart_hybrid",
    )
    self.assertIsInstance(intake_msgs, list)
    self.assertEqual(len(intake_msgs), 3)
    self.assertEqual(intake_msgs[0]["version"], "v0.9")
    self.assertIn("createSurface", intake_msgs[0])
    self.assertEqual(
        intake_msgs[0]["createSurface"]["surfaceId"],
        "pitchgen-intake",
    )
    self.assertEqual(intake_msgs[1]["version"], "v0.9")
    self.assertIn("updateDataModel", intake_msgs[1])
    self.assertEqual(
        intake_msgs[1]["updateDataModel"]["value"]["customer_name"],
        "Target Corporation",
    )
    self.assertEqual(intake_msgs[2]["version"], "v0.9")
    self.assertIn("updateComponents", intake_msgs[2])
    components = intake_msgs[2]["updateComponents"]["components"]
    comp_ids = [c["id"] for c in components]
    self.assertIn("root", comp_ids)
    self.assertIn("intake_col", comp_ids)
    self.assertIn("customer_name_input", comp_ids)
    self.assertIn("business_context_input", comp_ids)
    self.assertIn("deck_strategy_select", comp_ids)
    self.assertIn("industry_select", comp_ids)
    self.assertIn("sales_play_select", comp_ids)
    self.assertIn("audience_select", comp_ids)
    self.assertIn("sales_stage_select", comp_ids)
    self.assertIn("submit_btn", comp_ids)

    # Verify intake card attaches v09 canonical messages
    intake_card = a2ui.create_gtm_intake_card(
        customer_name="Target Corporation"
    )
    self.assertIn("a2ui_v09_messages", intake_card)
    self.assertEqual(len(intake_card["a2ui_v09_messages"]), 3)

    # 2. Outline review messages (v0.9: createSurface + updateDataModel + updateComponents)
    agenda_sections = [
        {
            "title": "Exec Summary",
            "subtopics": ["Vision", "Goals"],
            "slide_count": 2,
        },
        {
            "title": "Architecture",
            "subtopics": ["Vertex AI", "BigQuery"],
            "slide_count": 4,
        },
    ]
    outline_msgs = a2ui.create_a2ui_v09_outline_messages(
        customer_name="Target Corporation",
        agenda_sections=agenda_sections,
        deck_strategy="smart_hybrid",
    )
    self.assertIsInstance(outline_msgs, list)
    self.assertEqual(len(outline_msgs), 3)
    self.assertEqual(outline_msgs[0]["version"], "v0.9")
    self.assertIn("createSurface", outline_msgs[0])
    self.assertEqual(
        outline_msgs[0]["createSurface"]["surfaceId"],
        "pitchgen-outline",
    )
    self.assertEqual(outline_msgs[1]["version"], "v0.9")
    self.assertIn("updateDataModel", outline_msgs[1])
    self.assertEqual(outline_msgs[2]["version"], "v0.9")
    self.assertIn("updateComponents", outline_msgs[2])
    outline_comps = outline_msgs[2]["updateComponents"]["components"]
    outline_comp_ids = [c["id"] for c in outline_comps]
    self.assertIn("root", outline_comp_ids)
    self.assertIn("approve_btn", outline_comp_ids)

    # Verify outline card attaches v09 canonical messages
    outline_card = a2ui.create_outline_review_card(
        customer_name="Target Corporation",
        agenda_sections=agenda_sections,
    )
    self.assertIn("a2ui_v09_messages", outline_card)
    self.assertEqual(len(outline_card["a2ui_v09_messages"]), 3)

  def test_create_a2ui_v09_canvas_messages(self):
    """Tests canonical A2UI v0.9 Canvas messages with IFrameUrl for Gemini Enterprise."""
    msgs = a2ui.create_a2ui_v09_canvas_messages(
        surface_id="pitchgen-canvas-preview",
        card_title="Target Corporation Pitch",
        card_description="Click to open full presentation in side canvas",
        deck_title="Target AI Modernization",
        deck_subtitle="14 Slides ready for presentation",
        presentation_id="SAMPLE_PRESENTATION_ID_PLACEHOLDER_00001",
        metadata_items=[
            "Opportunity: 006Kf00000M0PJcIAN",
            "Strategy: Smart Hybrid",
        ],
    )
    self.assertEqual(len(msgs), 2)
    self.assertEqual(msgs[0]["version"], "v0.9")
    self.assertIn("createSurface", msgs[0])
    self.assertEqual(msgs[1]["version"], "v0.9")
    self.assertIn("updateComponents", msgs[1])
    comps = msgs[1]["updateComponents"]["components"]
    comp_map = {c["id"]: c for c in comps}
    self.assertIn("root", comp_map)
    self.assertEqual(comp_map["root"]["component"], "Canvas")
    self.assertTrue(comp_map["root"].get("autoOpen"))
    self.assertIn("slides-iframe", comp_map)
    self.assertEqual(comp_map["slides-iframe"]["component"], "IFrameUrl")

  def test_redefined_ge_quick_actions(self):
    """Tests that deck quick actions point to search, transform, and generate_visuals."""
    actions = a2ui.create_ge_quick_actions(
        deck_url="https://docs.google.com/presentation/d/SAMPLE_PRESENTATION_ID_PLACEHOLDER_00001/edit",
        customer_name="Target",
    )
    self.assertEqual(len(actions), 3)
    action_map = {a["action"]["actionName"]: a for a in actions}
    self.assertIn("search", action_map)
    self.assertIn("transform", action_map)
    self.assertIn("generate_visuals", action_map)

    # Verify search action points to slide search parameters
    search_act = action_map["search"]
    self.assertIn("Search", search_act["label"])
    self.assertEqual(search_act["style"], "primary")
    self.assertEqual(
        search_act["action"]["parameters"]["presentation_id"],
        "SAMPLE_PRESENTATION_ID_PLACEHOLDER_00001",
    )
    self.assertEqual(
        search_act["action"]["parameters"]["customer_name"], "Target"
    )

    # Verify transform action points to slide transform parameters
    trans_act = action_map["transform"]
    self.assertIn("Transform", trans_act["label"])
    self.assertEqual(trans_act["style"], "primary")
    self.assertEqual(
        trans_act["action"]["parameters"]["presentation_id"],
        "SAMPLE_PRESENTATION_ID_PLACEHOLDER_00001",
    )
    self.assertEqual(trans_act["action"]["parameters"]["scope"], "entire_deck")

    # Verify generate_visuals action points to nano banana diagram parameters
    vis_act = action_map["generate_visuals"]
    self.assertIn("Visuals", vis_act["label"])
    self.assertEqual(vis_act["style"], "primary")
    self.assertEqual(
        vis_act["action"]["parameters"]["presentation_id"],
        "SAMPLE_PRESENTATION_ID_PLACEHOLDER_00001",
    )

  def test_format_a2ui_deck_card_prioritizes_ge_features(self):
    """Tests that deck card prioritizes native GE quick actions over external links."""
    card_dict = a2ui.format_a2ui_deck_card(
        deck_url="https://docs.google.com/presentation/d/SAMPLE_PRESENTATION_ID_PLACEHOLDER_00001/edit",
        customer_name="Target",
        er_number="006Kf00000M0PJcIAN",
        user_ldap="seller_user",
    )
    card = card_dict.get("a2ui_card", card_dict)
    sections = card["sections"]
    self.assertEqual(len(sections), 3)

    # 1. Summary text
    self.assertEqual(sections[0]["type"], "text")
    self.assertIn("Target", sections[0]["content"])

    # 2. Native GE Quick Actions (Primary focus)
    self.assertEqual(sections[1]["type"], "quick_actions")
    self.assertIn("Refine & Enhance in Gemini Enterprise", sections[1]["title"])
    for act in sections[1]["actions"]:
      self.assertEqual(act["style"], "primary")

    # 3. Secondary Options & External Links (Demoted)
    self.assertEqual(sections[2]["type"], "actions")
    self.assertIn("Secondary Options & External Links", sections[2]["title"])
    for btn in sections[2]["buttons"]:
      self.assertEqual(btn["style"], "secondary")

  def test_enterprise_agent_wrappers_and_callback(self):
    """Tests enterprise_agent wrappers and after_model_callback A2UI injection."""
    import asyncio

    try:
      from pitchgen.src import enterprise_agent
    except ImportError:
      from src import enterprise_agent
    from google.genai import types

    class DummyContext:

      def __init__(self):
        self.state = {"user_ldap": "seller_user", "user_email": "seller_user@example.com"}

    ctx = DummyContext()

    # 1. Test enterprise_generate_visuals_skill stashes payload and does NOT leak <a2ui-json> in return string
    vis_res = enterprise_agent.enterprise_generate_visuals_skill(
        prompt="Retail Recommendation Engine Architecture",
        presentation_url_or_id="SAMPLE_PRESENTATION_ID_PLACEHOLDER_00001",
        tool_context=ctx,
    )
    self.assertNotIn("<a2ui-json>", vis_res)
    self.assertIn("a2ui_payloads_to_inject", ctx.state)
    self.assertEqual(len(ctx.state["a2ui_payloads_to_inject"]), 1)

    # 2. Test enterprise_after_model_callback processes stashed payloads and strips both <a2ui-json> and <a2a_datapart_json> tags
    class DummyContent:

      def __init__(self, parts, role="model"):
        self.parts = parts
        self.role = role

    class DummyResponse:

      def __init__(self, text):
        self.content = DummyContent([types.Part(text=text)])
        self.custom_metadata = {}

      def model_copy(self, update=None):
        res = DummyResponse("")
        if update:
          if "content" in update:
            res.content = update["content"]
          if "custom_metadata" in update:
            res.custom_metadata = update["custom_metadata"]
        return res

    sample_text = (
        'Here is your architecture deck:\n\n<a2ui-json>\n{"version": "v0.9",'
        ' "createSurface": {"surfaceId": "test-surface", "catalogId":'
        ' "test-cat"}}\n</a2ui-json><a2a_datapart_json>{"kind": "data",'
        ' "metadata": {"mimeType": "application/json+a2ui"}, "data":'
        ' {"version": "v0.9", "createSurface": {"surfaceId":'
        ' "echoed-surface"}}}</a2a_datapart_json>'
    )
    resp = DummyResponse(sample_text)
    cb_result = enterprise_agent.enterprise_after_model_callback(ctx, resp)
    if asyncio.iscoroutine(cb_result):
      updated_resp = asyncio.run(cb_result)
    else:
      updated_resp = cb_result

    # Verify a2a:response custom_metadata is set
    self.assertTrue(updated_resp.custom_metadata.get("a2a:response"))

    # Verify raw <a2ui-json> and <a2a_datapart_json> tags were stripped from chat text
    text_parts = [p.text for p in updated_resp.content.parts if p.text]
    self.assertTrue(
        any("Here is your architecture deck:" in t for t in text_parts)
    )
    self.assertFalse(any("<a2ui-json>" in t for t in text_parts))
    self.assertFalse(any("<a2a_datapart_json>" in t for t in text_parts))

    # Verify inline_data parts were created with text/plain containing <a2a_datapart_json>
    inline_parts = [
        p.inline_data for p in updated_resp.content.parts if p.inline_data
    ]
    mimes = [p.mime_type for p in inline_parts]
    self.assertIn("text/plain", mimes)
    payload_texts = [p.data.decode("utf-8") for p in inline_parts]
    self.assertTrue(any("<a2a_datapart_json>" in pt for pt in payload_texts))
    self.assertTrue(any("application/json+a2ui" in pt for pt in payload_texts))

    # Verify stashed payloads were popped
    self.assertEqual(len(ctx.state.get("a2ui_payloads_to_inject", [])), 0)

  def test_enterprise_intake_form_skill(self):
    """Tests that enterprise_intake_form_skill stashes canonical v0.9 intake messages."""
    try:
      from pitchgen.src import enterprise_agent
    except ImportError:
      from src import enterprise_agent

    class DummyContext:

      def __init__(self):
        self.state = {}

    ctx = DummyContext()
    res = enterprise_agent.enterprise_intake_form_skill(
        customer_name="Target",
        industry="Retail & CPG",
        business_context="Enterprise retail modernization",
        tool_context=ctx,
    )
    self.assertIn("<a2ui-json>", res)
    self.assertIn("a2ui_payloads_to_inject", ctx.state)
    payloads = ctx.state["a2ui_payloads_to_inject"]
    self.assertGreaterEqual(len(payloads), 3)
    self.assertEqual(payloads[0]["version"], "v0.9")
    self.assertIn("createSurface", payloads[0])
    self.assertEqual(
        payloads[0]["createSurface"]["surfaceId"], "pitchgen-intake"
    )
    self.assertEqual(payloads[1]["version"], "v0.9")
    self.assertIn("updateDataModel", payloads[1])
    self.assertEqual(payloads[2]["version"], "v0.9")
    self.assertIn("updateComponents", payloads[2])
    self.assertEqual(
        payloads[2]["updateComponents"]["surfaceId"], "pitchgen-intake"
    )

  def test_enterprise_after_model_callback_greeting_fallback(self):
    """Tests that enterprise_after_model_callback injects canonical v0.9 intake messages

    when LLM generates greeting/welcome text referencing the intake form
    without explicitly invoking enterprise_intake_form_skill.
    """
    import asyncio

    try:
      from pitchgen.src import enterprise_agent
    except ImportError:
      from src import enterprise_agent
    from google.genai import types

    class DummyState(dict):
      pass

    class DummyContext:

      def __init__(self):
        self.state = DummyState()

    class DummyContent:

      def __init__(self, parts, role="model"):
        self.parts = parts
        self.role = role

    class DummyResponse:

      def __init__(self, text):
        self.content = DummyContent([types.Part(text=text)])
        self.custom_metadata = {}

      def model_copy(self, update=None):
        res = DummyResponse("")
        if update:
          if "content" in update:
            res.content = update["content"]
          if "custom_metadata" in update:
            res.custom_metadata = update["custom_metadata"]
        return res

    ctx = DummyContext()
    # Simulate LLM output from session 3660479825417515986
    model_greeting = (
        "Welcome to **PitchGen**! I'm your Google Cloud Sales Catalyst.\n\nYou"
        " can use the interactive **GTM Intake form** above to configure your"
        " account narrative..."
    )
    resp = DummyResponse(model_greeting)
    cb_result = enterprise_agent.enterprise_after_model_callback(ctx, resp)
    if asyncio.iscoroutine(cb_result):
      updated_resp = asyncio.run(cb_result)
    else:
      updated_resp = cb_result

    # Verify a2a:response custom_metadata is set
    self.assertTrue(updated_resp.custom_metadata.get("a2a:response"))

    # Verify inline_data parts were created with text/plain containing <a2a_datapart_json>
    inline_parts = [
        p.inline_data for p in updated_resp.content.parts if p.inline_data
    ]
    self.assertGreater(len(inline_parts), 0)
    mimes = [p.mime_type for p in inline_parts]
    self.assertIn("text/plain", mimes)
    payload_texts = [p.data.decode("utf-8") for p in inline_parts]
    self.assertTrue(any("<a2a_datapart_json>" in pt for pt in payload_texts))
    self.assertTrue(any("application/json+a2ui" in pt for pt in payload_texts))
    self.assertTrue(any("createSurface" in pt for pt in payload_texts))
    self.assertTrue(any("updateComponents" in pt for pt in payload_texts))

  def test_enterprise_create_proposal_outline_dict_agendas(self):
    """Tests that enterprise_create_proposal_outline correctly handles dictionary agendas

    from PitchGenSkills (e.g. from session 14872548558295701022) without
    crashing on 'str' object has no attribute 'get'.
    """
    import json
    from unittest.mock import patch

    try:
      from pitchgen.src import enterprise_agent
    except ImportError:
      from src import enterprise_agent

    sample_dict_outline = json.dumps({
        "Status": "True",
        "data": {
            "agendas": {
                "1": {
                    "title": "Retail Media Network Challenges",
                    "parts": [
                        (
                            "Retail media networks face mounting demand for"
                            " personalized, multi-format ad creative at scale"
                        ),
                        (
                            "Manual creative production cycles and fragmented"
                            " workflows bottleneck supplier campaign velocity"
                        ),
                    ],
                },
                "2": {
                    "title": "Envisioning Autonomous Creative",
                    "parts": [
                        (
                            "Envisioning autonomous dynamic creative"
                            " optimization powered by unified first-party"
                            " shopper intelligence"
                        ),
                    ],
                },
            },
            "customer": "Walmart",
            "context": {
                "deck_strategy": "smart_hybrid",
            },
        },
        "message": "Success",
    })

    class DummyState(dict):
      pass

    class DummyContext:

      def __init__(self):
        self.state = DummyState()

    ctx = DummyContext()
    with patch.object(
        enterprise_agent.PitchGenSkills,
        "create_proposal_outline",
        return_value=sample_dict_outline,
    ):
      res = enterprise_agent.enterprise_create_proposal_outline(
          business_context="Walmart generative media ad network",
          customer_name="Walmart",
          tool_context=ctx,
      )

    self.assertNotIn("<a2ui-json>", res)
    self.assertIn("a2ui_payloads_to_inject", ctx.state)
    stashed = [
        m
        for m in ctx.state["a2ui_payloads_to_inject"]
        if "deleteSurface" not in m
    ]
    self.assertEqual(len(stashed), 3)
    self.assertEqual(stashed[0]["version"], "v0.9")
    self.assertIn("createSurface", stashed[0])
    self.assertTrue(
        stashed[0]["createSurface"]["surfaceId"].startswith("pitchgen-outline")
    )
    self.assertEqual(stashed[1]["version"], "v0.9")
    self.assertIn("updateDataModel", stashed[1])
    self.assertEqual(stashed[2]["version"], "v0.9")
    self.assertIn("updateComponents", stashed[2])
    self.assertTrue(
        stashed[2]["updateComponents"]["surfaceId"].startswith(
            "pitchgen-outline"
        )
    )

  def test_developer_knowledge_workflow_thread_safe_concurrent_calls(self):
    """Verify DeveloperKnowledgeWorkflow runs safely across concurrent threads without sharing non-thread-safe sockets."""
    from concurrent.futures import ThreadPoolExecutor
    from unittest.mock import MagicMock, patch
    from src.agents.workflows.developer_knowledge_workflow import DeveloperKnowledgeWorkflow

    wf = DeveloperKnowledgeWorkflow(
        config={"default": {"project_name": "your-gcp-project-id"}}
    )
    wf._cached_search.cache_clear()

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [{
            "parent": "https://cloud.google.com/vertex-ai",
            "content": "Reasoning Engine thread-safe architecture.",
        }]
    }
    mock_session.get.return_value = mock_resp

    with patch.object(wf, "_get_session", return_value=mock_session):
      with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(wf.execute, f"query {i}") for i in range(6)]
        results = [f.result() for f in futures]

    self.assertEqual(len(results), 6)
    for res in results:
      self.assertIn("Reasoning Engine thread-safe architecture", res)

  def test_text_transformer_execute_deck_holistic_smart_hybrid_cohesion(self):
    """Verify execute_deck_holistic preserves Phase 2 body shapes on generated slides while customizing reusable slides and adding speaker note transition hooks."""
    import json
    from unittest.mock import MagicMock, patch
    from src.agents.workflows.text_transformer_workflow import TextTransformerWorkflow

    wf = TextTransformerWorkflow(
        config={
            "default": {
                "project_name": "your-gcp-project-id",
                "gemini_model": "gemini-3.8-flash",
                "gemini_model_1": "gemini-3.5-flash-lite",
            }
        }
    )

    sample_slides = [
        {
            "slide_id": "gen_slide_1",
            "slide_index": 0,
            "is_reusable": False,
            "speaker_notes": "Original speaker notes for slide 1.",
            "data": [
                {
                    "shapeId": "title_1",
                    "text": (
                        "GoogleCloud EnterpriseAI DistributedInfrastructure"
                        " AcceleratedTraining HighThroughput"
                    ),
                    "fontSize": 22,
                    "bold": True,
                },
                {
                    "shapeId": "body_1",
                    "text": "Preserved Phase 2 body content for slide 1.",
                    "fontSize": 12,
                    "bold": False,
                },
            ],
        },
        {
            "slide_id": "reusable_slide_2",
            "slide_index": 1,
            "is_reusable": True,
            "speaker_notes": "Original reference speaker notes for slide 2.",
            "data": [
                {
                    "shapeId": "title_2",
                    "text": (
                        "Cloud Interconnect Overview for High-Bandwidth"
                        " Multi-Region Enterprise Network Topologies"
                    ),
                    "fontSize": 22,
                    "bold": True,
                },
                {
                    "shapeId": "body_2",
                    "text": (
                        "Generic Cloud Interconnect bullet points covering"
                        " low-latency enterprise hybrid connectivity to Cloud"
                        " Storage."
                    ),
                    "fontSize": 12,
                    "bold": False,
                },
            ],
        },
    ]

    mock_holistic_response = json.dumps({
        "slides": [
            {
                "slide_id": "gen_slide_1",
                "transition_hook": (
                    "🔗 Transition to next slide: Now let's examine how Cloud"
                    " Interconnect powers this high-throughput AI data"
                    " pipeline."
                ),
                "shapes": [
                    {
                        "shape_id": "title_1",
                        "transformed_text": (
                            "Accelerating Nebius AI Training with Google Cloud"
                            " Infrastructure"
                        ),
                    },
                    {
                        "shape_id": "body_1",
                        "transformed_text": (
                            "Attempted rewrite of Phase 2 body that should be"
                            " ignored."
                        ),
                    },
                ],
            },
            {
                "slide_id": "reusable_slide_2",
                "transition_hook": (
                    "🔗 Transition to next slide: Next, we review the"
                    " implementation timeline."
                ),
                "shapes": [
                    {
                        "shape_id": "title_2",
                        "transformed_text": (
                            "Dedicated Cloud Interconnect for Nebius"
                            " Multi-Terabit Fabrics"
                        ),
                    },
                    {
                        "shape_id": "body_2",
                        "transformed_text": (
                            "Tailored low-latency Dedicated Interconnect"
                            " linking Nebius GPU clusters to GCS."
                        ),
                    },
                ],
            },
        ],
    })

    mock_resp = MagicMock()
    mock_resp.text = mock_holistic_response

    with (
        patch.object(
            wf, "generate_content_with_fallback", return_value=mock_resp
        ),
        patch.object(
            wf,
            "_get_or_research_customer",
            return_value="Nebius AI Cloud Infrastructure profile.",
        ),
        patch.object(
            wf.dk_workflow, "execute", return_value="Developer knowledge docs."
        ),
    ):
      res = wf.execute_deck_holistic(
          sample_slides,
          context={
              "customer_name": "Nebius",
              "industry": "AI Cloud Infrastructure",
              "region": "Global",
              "audience": "Executive",
              "business_context": (
                  "High-bandwidth Dedicated Interconnect and GCS storage for"
                  " LLM training"
              ),
          },
      )

    self.assertEqual(len(res), 2)
    # Slide 1 (Generated Cover): title normalized to concise modern headline, Phase 2 body preserved intact
    s1_shapes = {s["shapeId"]: s["text"] for s in res[0]["data"]}
    self.assertEqual(
        s1_shapes["title_1"],
        "Accelerating Nebius AI",
    )
    self.assertEqual(
        s1_shapes["body_1"], "Preserved Phase 2 body content for slide 1."
    )
    self.assertIn("🔗 Transition to next slide:", res[0]["speaker_notes"])

    # Slide 2 (Reusable): both title and body tailored to Nebius in Sentence case
    s2_shapes = {s["shapeId"]: s["text"] for s in res[1]["data"]}
    self.assertEqual(
        s2_shapes["title_2"],
        "Dedicated Cloud interconnect for Nebius Multi-Terabit fabrics",
    )
    self.assertEqual(
        s2_shapes["body_2"],
        "Tailored low-latency Dedicated Interconnect linking Nebius GPU"
        " clusters to GCS.",
    )
    self.assertIn("🔗 Transition to next slide:", res[1]["speaker_notes"])

  def test_slide_generator_state_hydration_and_immersive_artifact_marker(self):
    """Verifies that enterprise_slide_generator_skill hydrates agendas from proposal_outline and emits [canvas artifact: ...] for Workspace ImmersiveArtifact."""
    import json
    from unittest.mock import patch
    from enterprise_agent import enterprise_slide_generator_skill, _LATEST_OUTLINE_CACHE

    class DummyToolContext:

      def __init__(self):
        self.state = {
            "proposal_outline": json.dumps({
                "Status": "True",
                "data": {
                    "context": {
                        "customer_name": "Nike",
                        "user_ldap": "seller_user",
                        "customer_research": "Authoritative Nike research.",
                        "developer_knowledge": (
                            "Authoritative Google Cloud docs."
                        ),
                    },
                    "agendas": {
                        "1": {
                            "title": "Executive Overview",
                            "subtopics": ["Cloud Retail Modernization"],
                            "slides_number": 2,
                        }
                    },
                },
            })
        }

    ctx = DummyToolContext()
    partial_state = json.dumps({
        "context": {
            "customer_name": "Nike",
            "user_ldap": "seller_user",
            "customer_research": "[Cached in session state]",
        }
    })

    captured_state = {}

    def mock_slide_generator(state_json, tool_context=None):
      captured_state["hydrated"] = json.loads(state_json)
      return json.dumps({
          "deck_url": (
              "https://docs.google.com/presentation/d/pres_nike_12345/edit"
          ),
          "presentation_id": "pres_nike_12345",
      })

    with patch(
        "enterprise_agent.PitchGenSkills.enterprise_slide_generator_skill",
        side_effect=mock_slide_generator,
    ):
      res = enterprise_slide_generator_skill(
          state_json=partial_state, tool_context=ctx
      )

    self.assertIn("agendas", captured_state["hydrated"])
    self.assertEqual(
        captured_state["hydrated"]["context"]["customer_research"],
        "Authoritative Nike research.",
    )
    self.assertNotIn("[canvas artifact:", res)
    self.assertNotIn("<a2ui-json>", res)
    self.assertNotIn("a2ui_payloads_to_inject", ctx.state)
    self.assertIn("canvas_artifact", ctx.state)
    self.assertIn(
        "google_slides_uri:"
        ' "https://docs.google.com/presentation/d/pres_nike_12345/edit"',
        ctx.state["canvas_artifact"],
    )

  def test_extract_presentation_id_and_immersive_artifact_from_open_id_url(
      self,
  ):
    """Verifies that open?id= URLs from Apps Script extract presentation_id and populate canvas_artifact without [canvas artifact: ...] text leakage."""
    import json
    from unittest.mock import patch
    from enterprise_agent import enterprise_slide_generator_skill

    open_url = "https://docs.google.com/open?id=SAMPLE_TEST_PRESENTATION_ID_000000000006"
    pres_id = a2ui.extract_presentation_id(open_url)
    self.assertEqual(pres_id, "SAMPLE_TEST_PRESENTATION_ID_000000000006")

    def mock_slide_gen_open_url(state_json, tool_context=None):
      return json.dumps({
          "deckURL": open_url,
          "status": 200,
      })

    ctx = type("MockCtx", (), {"state": {}})()
    with patch(
        "enterprise_agent.PitchGenSkills.enterprise_slide_generator_skill",
        side_effect=mock_slide_gen_open_url,
    ):
      res = enterprise_slide_generator_skill(
          state_json=json.dumps(
              {"context": {"customer_name": "Nike", "user_ldap": "seller_user"}}
          ),
          tool_context=ctx,
      )

    self.assertNotIn("[canvas artifact:", res)
    self.assertNotIn("<a2ui-json>", res)
    self.assertIn("canvas_artifact", ctx.state)
    self.assertIn(
        "google_slides_uri:"
        ' "https://docs.google.com/presentation/d/SAMPLE_TEST_PRESENTATION_ID_000000000006/edit"',
        ctx.state["canvas_artifact"],
    )

  def test_canvas_artifact_textproto_and_file_data_in_state_delta(self):
    """Verifies that enterprise_slide_generator_skill and enterprise_after_model_callback populate canvas_artifact textproto, attach Google Slides FileData part, and strip any [canvas artifact: ...] text."""
    import json
    from unittest.mock import patch
    from google.genai import types
    from enterprise_agent import enterprise_slide_generator_skill, enterprise_after_model_callback

    deck_url = "https://docs.google.com/presentation/d/SAMPLE_TEST_PRESENTATION_ID_000000000001/edit"
    textproto = a2ui.build_canvas_artifact_textproto(
        deck_url=deck_url,
        title="Nike Presentation Deck",
        model_generated_id=(
            "pitchgen-deck-SAMPLE_TEST_PRESENTATION_ID_000000000001"
        ),
    )
    self.assertIn('title: "Nike Presentation Deck"', textproto)
    self.assertIn(
        "model_generated_id:"
        ' "pitchgen-deck-SAMPLE_TEST_PRESENTATION_ID_000000000001"',
        textproto,
    )
    self.assertIn("google_slides_artifact {", textproto)
    self.assertIn(f'google_slides_uri: "{deck_url}"', textproto)

    ctx = type("MockCtx", (), {"state": {}})()

    def mock_slide_gen(state_json, tool_context=None):
      return json.dumps({"deckURL": deck_url, "status": 200})

    with patch(
        "enterprise_agent.PitchGenSkills.enterprise_slide_generator_skill",
        side_effect=mock_slide_gen,
    ):
      enterprise_slide_generator_skill(
          state_json=json.dumps(
              {"context": {"customer_name": "Nike", "user_ldap": "seller_user"}}
          ),
          tool_context=ctx,
      )

    self.assertIn("canvas_artifact", ctx.state)
    self.assertIn(
        "google_slides_uri:"
        ' "https://docs.google.com/presentation/d/SAMPLE_TEST_PRESENTATION_ID_000000000001/edit"',
        ctx.state["canvas_artifact"],
    )
    self.assertNotIn("a2ui_payloads_to_inject", ctx.state)

    from google.adk.models.llm_response import LlmResponse

    llm_resp = LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    text=(
                        "[canvas artifact:"
                        " pitchgen-deck-SAMPLE_TEST_PRESENTATION_ID_000000000007"
                        " title='Nike Presentation Deck' for"
                        " @[https://docs.google.com/presentation/d/SAMPLE_TEST_PRESENTATION_ID_000000000007/edit:PitchGen_2026/09/15]]\nHere"
                        " is your Nike presentation deck."
                    )
                )
            ],
        )
    )
    out_resp = enterprise_after_model_callback(ctx, llm_resp)
    self.assertIn("canvas_artifact", ctx.state)
    text_parts = [
        p.text for p in out_resp.content.parts if getattr(p, "text", None)
    ]
    self.assertEqual(text_parts, ["Here is your Nike presentation deck."])
    file_parts = [
        p for p in out_resp.content.parts if getattr(p, "file_data", None)
    ]
    self.assertEqual(len(file_parts), 1)
    self.assertEqual(
        file_parts[0].file_data.mime_type,
        "application/vnd.google-apps.presentation",
    )
    self.assertEqual(file_parts[0].file_data.file_uri, deck_url)

    # Verify thinking/steps support and PitchGen Agent persona
    from enterprise_agent import enterprise_agent

    self.assertIn("You are the PitchGen Agent", enterprise_agent.instruction)
    self.assertNotIn("PitchGen Sales Catalyst", enterprise_agent.instruction)
    self.assertIsNotNone(enterprise_agent.planner)
    self.assertTrue(enterprise_agent.planner.thinking_config.include_thoughts)

    fn_resp = LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    function_call=types.FunctionCall(
                        name="enterprise_create_proposal_outline",
                        args={"customer_name": "Nike"},
                    )
                )
            ],
        )
    )
    fn_out = enterprise_after_model_callback(ctx, fn_resp)
    thought_parts = [
        p for p in fn_out.content.parts if getattr(p, "thought", False)
    ]
    self.assertEqual(len(thought_parts), 1)
    self.assertIn("Researching organization context", thought_parts[0].text)

  def test_post_assembly_parity_and_action_title_preservation(self):
    """Verifies UI Extension parity: [PitchGen] deck title format, 🔗 Source Slide links, reusable slide transformation, and full executive Action Titles."""
    from unittest.mock import MagicMock, patch
    from agent import format_pitchgen_deck_title, post_process_assembled_presentation
    from agents.workflows.text_transformer_workflow import TextTransformerWorkflow

    # 1. Verify [PitchGen] <Account> | <Strategic Theme> (<Mon YYYY>) deck title formatting
    outputs_data = {
        "customer_name": "Nike",
        "deck_theme": (
            "Pitch Deck for Nike: Scale AI and GenMedia with Google Cloud"
        ),
        "context": {"customer_name": "Nike", "industry": "Retail & CPG"},
        "sections": {
            "title": {
                "slides": {
                    "1": {
                        "placeholders": {
                            "title": "Scale AI and GenMedia with Google Cloud"
                        }
                    }
                }
            },
            "1": {
                "slides": {
                    "1": {
                        "placeholders": {
                            "title": (
                                "Accelerating DTC Member Engagement Across"
                                " High-Velocity Athletic Drops"
                            )
                        }
                    }
                }
            },
        },
    }
    formatted_title = format_pitchgen_deck_title(outputs_data)
    self.assertTrue(
        formatted_title.startswith(
            "[PitchGen] Nike | Scale AI and GenMedia with Google Cloud ("
        )
    )
    self.assertTrue(formatted_title.endswith(")"))

    # 2. Verify _sanitize_output with is_action_title=True preserves full 6-11 word executive titles (no 3-word truncation)
    wf = TextTransformerWorkflow.__new__(TextTransformerWorkflow)
    long_exec_title = (
        "Accelerating Creative Supply Chain Velocity with Google Cloud GenMedia"
    )
    sanitized_title = wf._sanitize_output(
        long_exec_title,
        is_cover_slide=False,
        customer_name="Nike",
        original_len=80,
        is_action_title=True,
    )
    self.assertEqual(
        sanitized_title,
        "Faster creative supply chain velocity with Google Cloud GenMedia",
    )
    self.assertGreaterEqual(len(sanitized_title.split()), 8)

    # 3. Verify post_process_assembled_presentation renames deck, attaches 🔗 Source Slide clickable link, and transforms reusable slide text
    reusable_slides = {
        "1": {
            "suggestions": [{
                "name": (
                    "Why Google Cloud for Marketing Pitch"
                    " (marketing_foundation_pitch)"
                ),
                "values": [
                    "https://docs.google.com/presentation/d/SAMPLE_TEST_PRESENTATION_ID_000000000015/edit?#slide=id.g3e2552bee3b_0_1378"
                ],
                "date": "2026-09-15",
                "_source_datastore_key": "sales_play_reusables",
            }]
        }
    }

    fake_pres_response = {
        "presentationId": "pres_123",
        "title": "PitchGen_2026/09/21",
        "slides": [
            {
                "objectId": "slide_internal_0",
                "pageElements": [{
                    "objectId": "sh_0",
                    "shape": {
                        "text": {
                            "textElements": [{
                                "textRun": {
                                    "content": (
                                        "INTERNAL CONTEXT: PLEASE REMOVE THIS"
                                        " SLIDE"
                                    )
                                }
                            }]
                        }
                    },
                }],
            },
            {
                "objectId": "slide_title_1",
                "pageElements": [{
                    "objectId": "sh_1",
                    "shape": {
                        "text": {
                            "textElements": [{
                                "textRun": {
                                    "content": (
                                        "Scale AI and GenMedia with Google"
                                        " Cloud"
                                    )
                                }
                            }]
                        }
                    },
                }],
            },
            {
                "objectId": "slide_agenda_2",
                "pageElements": [{
                    "objectId": "sh_2",
                    "shape": {
                        "text": {
                            "textElements": [{
                                "textRun": {
                                    "content": "Agenda\n01 Retail Trends"
                                }
                            }]
                        }
                    },
                }],
            },
            {
                "objectId": "slide_reusable_3",
                "pageElements": [
                    {
                        "objectId": "sh_reuse_title",
                        "shape": {
                            "text": {
                                "textElements": [{
                                    "textRun": {
                                        "content": (
                                            "Localized ads for global athletic"
                                            " brand campaigns across retail"
                                            " channels and regional digital"
                                            " markets\n"
                                        ),
                                        "style": {
                                            "fontSize": {
                                                "magnitude": 22,
                                                "unit": "PT",
                                            },
                                            "bold": True,
                                        },
                                    }
                                }]
                            }
                        },
                    },
                    {
                        "objectId": "sh_reuse_body",
                        "shape": {
                            "text": {
                                "textElements": [{
                                    "textRun": {
                                        "content": (
                                            "From one hero brand asset to"
                                            " thousands of dynamically"
                                            " localized omnichannel campaign"
                                            " variations across global markets"
                                            " and retail formats.\n"
                                        ),
                                        "style": {
                                            "fontSize": {
                                                "magnitude": 12,
                                                "unit": "PT",
                                            },
                                            "bold": False,
                                        },
                                    }
                                }]
                            }
                        },
                    },
                ],
                "slideProperties": {
                    "notesPage": {
                        "notesProperties": {
                            "speakerNotesObjectId": "notes_reuse_3"
                        },
                        "pageElements": [{
                            "objectId": "notes_reuse_3",
                            "shape": {
                                "text": {
                                    "textElements": [{
                                        "textRun": {
                                            "content": (
                                                "Original speaker notes here.\n"
                                            )
                                        }
                                    }]
                                }
                            },
                        }],
                    }
                },
            },
            {
                "objectId": "slide_gen_4",
                "pageElements": [{
                    "objectId": "sh_gen_title",
                    "shape": {
                        "text": {
                            "textElements": [{
                                "textRun": {
                                    "content": (
                                        "Accelerating DTC Member Engagement"
                                        " Across High-Velocity Athletic Drops\n"
                                    ),
                                    "style": {
                                        "fontSize": {
                                            "magnitude": 22,
                                            "unit": "PT",
                                        },
                                        "bold": True,
                                    },
                                }
                            }]
                        }
                    },
                }],
                "slideProperties": {
                    "notesPage": {
                        "notesProperties": {
                            "speakerNotesObjectId": "notes_gen_4"
                        },
                        "pageElements": [{
                            "objectId": "notes_gen_4",
                            "shape": {
                                "text": {
                                    "textElements": [{
                                        "textRun": {
                                            "content": (
                                                "Key Takeaway: DTC drops.\n"
                                            )
                                        }
                                    }]
                                }
                            },
                        }],
                    }
                },
            },
            {
                "objectId": "slide_thanks_5",
                "pageElements": [{
                    "objectId": "sh_5",
                    "shape": {
                        "text": {
                            "textElements": [
                                {"textRun": {"content": "Thank You"}}
                            ]
                        }
                    },
                }],
            },
        ],
    }

    def fake_holistic(
        slides_list, criteria="", context=None, target_slide_ids=None
    ):
      out = []
      for s in slides_list:
        s_copy = dict(s)
        if s_copy.get("is_reusable"):
          s_copy["data"] = [
              {
                  "shapeId": "sh_reuse_title",
                  "text": (
                      "Scaling Personalized Campaign Localization Across Global"
                      " Athletic Markets"
                  ),
              },
              {
                  "shapeId": "sh_reuse_body",
                  "text": (
                      "Transform hero athletic footwear assets into localized"
                      " omnichannel variations."
                  ),
              },
          ]
        s_copy["speaker_notes"] = (
            s_copy.get("speaker_notes", "")
            + "\n\n🔗 Transition to next slide: Bridge to Nike DTC"
            " architecture."
        )
        out.append(s_copy)
      return out

    with (
        patch("requests.patch") as mock_patch,
        patch("requests.get") as mock_get,
        patch("requests.post") as mock_post,
        patch.object(TextTransformerWorkflow, "__init__", return_value=None),
        patch.object(
            TextTransformerWorkflow,
            "execute_deck_holistic",
            side_effect=fake_holistic,
        ),
    ):
      mock_patch.return_value = MagicMock(status_code=200)
      mock_get.return_value = MagicMock(
          status_code=200, json=lambda: fake_pres_response
      )
      mock_post.return_value = MagicMock(status_code=200)

      res_title = post_process_assembled_presentation(
          presentation_id="pres_123",
          token="test_token",
          outputs_data=outputs_data,
          reusable_slides=reusable_slides,
          config={},
      )

      self.assertTrue(
          res_title.startswith(
              "[PitchGen] Nike | Scale AI and GenMedia with Google Cloud"
          )
      )
      mock_patch.assert_called_once()
      self.assertEqual(mock_patch.call_args.kwargs["json"]["name"], res_title)

      self.assertGreaterEqual(mock_post.call_count, 1)
      batch_reqs = mock_post.call_args_list[-1].kwargs["json"]["requests"]
      inserted_texts = [
          r["insertText"]["text"] for r in batch_reqs if "insertText" in r
      ]
      # Verify reusable slide title & body were transformed
      self.assertIn(
          "Scaling Personalized Campaign Localization Across Global Athletic"
          " Markets",
          inserted_texts,
      )
      self.assertIn(
          "Transform hero athletic footwear assets into localized omnichannel"
          " variations.",
          inserted_texts,
      )
      # Verify Phase 2 generated slide title was NOT mutated
      self.assertFalse(
          any(
              r.get("insertText", {}).get("objectId") == "sh_gen_title"
              for r in batch_reqs
          )
      )
      # Verify 🔗 Source Slide link + original speaker notes + transition hook were inserted into notes_reuse_3
      notes_inserts = [
          r["insertText"]["text"]
          for r in batch_reqs
          if "insertText" in r
          and r["insertText"]["objectId"] == "notes_reuse_3"
      ]
      self.assertEqual(len(notes_inserts), 1)
      self.assertIn(
          "🔗 Source Slide: Why Google Cloud for Marketing Pitch",
          notes_inserts[0],
      )
      self.assertIn(
          "https://docs.google.com/presentation/d/SAMPLE_TEST_PRESENTATION_ID_000000000015/edit?#slide=id.g3e2552bee3b_0_1378",
          notes_inserts[0],
      )
      self.assertIn("--- Original Speaker Notes ---", notes_inserts[0])
      self.assertIn("🔗 Transition to next slide:", notes_inserts[0])
      # Verify clickable hyperlink style was applied to notes_reuse_3
      link_styles = [
          r["updateTextStyle"]
          for r in batch_reqs
          if "updateTextStyle" in r
          and r["updateTextStyle"]["objectId"] == "notes_reuse_3"
          and "link" in r["updateTextStyle"].get("style", {})
      ]
      self.assertEqual(len(link_styles), 1)

  def test_multi_user_tahilyani_hydration_and_service_token_fallback(self):
    """Verifies that _hydrate_slide_generator_state preserves user_ldap/user_oauth_token even when agendas are present and customer_research is omitted, and call_apps_script_to_create_deck falls back to the service owner token and shares the deck with tahilyani@example.com."""
    import json
    from unittest.mock import MagicMock, patch
    from enterprise_agent import _hydrate_slide_generator_state
    from agent import call_apps_script_to_create_deck

    class DummyCtx:

      def __init__(self):
        self.state = {
            "proposal_outline": json.dumps({
                "Status": "True",
                "data": {
                    "context": {
                        "customer_name": "Walmart",
                        "user_ldap": "tahilyani",
                        "user_oauth_token": (
                            "mock_oauth_bearer_token_for_tahilyani_session_test_1234567890_abcdef"
                        ),
                        "customer_research": (
                            "Walmart CPG supply chain research."
                        ),
                    },
                    "agendas": {
                        "1": {
                            "title": "Retail Challenges",
                            "subtopics": ["Margin compression"],
                        }
                    },
                },
            })
        }

    # LLM passes agendas (has_agendas=True) and omits customer_research, user_ldap, and user_oauth_token
    llm_passed_json = json.dumps({
        "context": {"customer_name": "Walmart", "industry": "Retail"},
        "agendas": {
            "1": {
                "title": "Retail Challenges",
                "subtopics": ["Margin compression"],
            }
        },
    })
    hydrated_str = _hydrate_slide_generator_state(llm_passed_json, DummyCtx())
    hydrated = json.loads(hydrated_str)
    self.assertEqual(hydrated["context"]["user_ldap"], "tahilyani")
    self.assertTrue(
        hydrated["context"]["user_oauth_token"].startswith(
            "mock_oauth_bearer_token_"
        )
    )
    self.assertEqual(
        hydrated["context"]["customer_research"],
        "Walmart CPG supply chain research.",
    )

    # Simulate Apps Script returning <!DOCTYPE html> for tahilyani's token, then succeeding with service_owner token
    def fake_requests_post(
        url, headers=None, json=None, allow_redirects=True, timeout=300
    ):
      auth_hdr = (headers or {}).get("Authorization", "")
      if "script.google.com" in url:
        if "mock_oauth_bearer_token_" in auth_hdr:
          return MagicMock(
              status_code=200,
              text=(
                  "<!DOCTYPE html><html><body>Google Sign-in"
                  " required</body></html>"
              ),
          )
        if "service_owner_token_seller_user" in auth_hdr:
          return MagicMock(
              status_code=200,
              text=(
                  '{"status": 200, "deckURL":'
                  ' "https://docs.google.com/presentation/d/pres_walmart_999/edit"}'
              ),
              json=lambda: {
                  "status": 200,
                  "deckURL": (
                      "https://docs.google.com/presentation/d/pres_walmart_999/edit"
                  ),
              },
          )
      # Drive permissions POST or Slides batchUpdate POST
      return MagicMock(status_code=200, text="{}")

    with (
        patch("requests.post", side_effect=fake_requests_post) as mock_post,
        patch("requests.patch", return_value=MagicMock(status_code=200)),
        patch(
            "requests.get",
            return_value=MagicMock(
                status_code=200, json=lambda: {"slides": []}
            ),
        ),
        patch(
            "oauth_helper.get_user_access_token",
            side_effect=lambda ldap: "service_owner_token_seller_user"
            if ldap == "seller_user"
            else None,
        ),
        patch("oauth_helper.get_cached_active_token", return_value=None),
        patch("oauth_helper.get_enduser_bearer_token", return_value=None),
    ):
      deck_url = call_apps_script_to_create_deck(
          outputs_gcs_url=(
              "gs://your-pitchgen-content-bucket/tahilyani_20260921.json"
          ),
          architectural_gcs_url="gs://your-pitchgen-content-bucket/architectural_tahilyani_20260921.json",
          user_ldap="tahilyani",
          user_oauth_token=hydrated["context"]["user_oauth_token"],
          outputs_data={
              "customer_name": "Walmart",
              "context": hydrated["context"],
          },
          reusable_slides={},
      )

      self.assertEqual(
          deck_url,
          "https://docs.google.com/presentation/d/pres_walmart_999/edit",
      )
      # Verify Drive permissions API was called to grant writer access to tahilyani@example.com
      perm_calls = [
          c
          for c in mock_post.call_args_list
          if "drive/v3/files/pres_walmart_999/permissions"
          in str(c.args[0] if c.args else c.kwargs.get("url", ""))
      ]
      self.assertEqual(len(perm_calls), 1)
      self.assertEqual(
          perm_calls[0].kwargs["json"]["emailAddress"], "tahilyani@example.com"
      )
      self.assertIn(perm_calls[0].kwargs["json"]["role"], ("owner", "writer"))

  def test_sanitize_replayed_google_slides_file_data_prevents_vertex_400(self):
    """Verifies that enterprise_before_model_callback converts replayed Google Slides file_data URLs into text context parts so follow-up turns never fail with Vertex 400 INVALID_ARGUMENT (URL_ERROR-ERROR_AUTHENTICATION)."""
    from google.genai import types
    from enterprise_agent import enterprise_before_model_callback

    deck_id = "SAMPLE_TEST_PRESENTATION_ID_000000000016"
    deck_url = f"https://docs.google.com/presentation/d/{deck_id}/edit"

    prior_model_turn = types.Content(
        role="model",
        parts=[
            types.Part(text="Here is your Disney presentation deck."),
            types.Part(
                file_data=types.FileData(
                    file_uri=deck_url,
                    mime_type="application/vnd.google-apps.presentation",
                    display_name="[PitchGen] Disney | Scale AI (Sep 2026)",
                )
            ),
            types.Part(
                inline_data=types.Blob(
                    mime_type="text/plain",
                    data=b'<a2a_datapart_json>{"kind":"data","metadata":{"mimeType":"application/json+a2ui"}}</a2a_datapart_json>',
                )
            ),
        ],
    )
    follow_up_user_turn = types.Content(
        role="user",
        parts=[types.Part(text="Search for additional customer references")],
    )
    dummy_req = type(
        "DummyLlmReq", (), {"contents": [prior_model_turn, follow_up_user_turn]}
    )()
    ctx = type("DummyCtx", (), {"state": {"customer_name": "Disney"}})()

    cb_res = enterprise_before_model_callback(ctx, dummy_req)
    self.assertIsNone(cb_res)

    # 1. Verify no non-gs:// file_data parts remain in replayed history
    for content_obj in dummy_req.contents:
      for part in content_obj.parts:
        f_data = getattr(part, "file_data", None)
        if f_data is not None:
          self.assertTrue(str(f_data.file_uri).startswith("gs://"))

    # 2. Verify replayed Google Slides URL was converted into text context and saved to session state
    prior_texts = [
        p.text for p in prior_model_turn.parts if getattr(p, "text", None)
    ]
    self.assertTrue(
        any(
            "Active Google Slides Presentation on Canvas" in t and deck_id in t
            for t in prior_texts
        )
    )
    self.assertEqual(ctx.state.get("presentation_id"), deck_id)
    self.assertEqual(ctx.state.get("deck_url"), deck_url)

    # 3. Verify old <a2a_datapart_json> inline_data blob was stripped from prior model turn
    prior_inline = [
        p for p in prior_model_turn.parts if getattr(p, "inline_data", None)
    ]
    self.assertEqual(len(prior_inline), 0)

  def test_enterprise_search_slides_and_insert_slide_workflows(self):
    """Verifies customer reference & slide library search, session context enrichment, camelCase slideId/deckId normalization, and 1-click slide insertion."""
    import json
    from unittest.mock import MagicMock, patch
    from google.genai import types
    from enterprise_agent import (
        enterprise_before_model_callback,
        enterprise_insert_slide_skill,
        enterprise_search_slides_skill,
    )

    deck_id = "SAMPLE_TEST_PRESENTATION_ID_000000000016"
    ctx = type(
        "DummyCtx",
        (),
        {
            "state": {
                "user_ldap": "seller_user",
                "customer_name": "Disney",
                "industry": "Media & Entertainment",
                "salesPlay": "Scale AI Apps & Agents",
                "presentation_id": deck_id,
                "deck_url": (
                    f"https://docs.google.com/presentation/d/{deck_id}/edit"
                ),
            }
        },
    )()

    fake_cust_refs = [
        {
            "customer": "FOX Sports",
            "title": "FOX Sports: Real-Time GenMedia Highlights on Vertex AI",
            "industry": "Media & Entertainment",
            "summary": (
                "FOX Sports reduced live highlight turnaround by 60% using"
                " Vertex AI and Gemini."
            ),
            "deck_id": "1refDeckFox123",
            "slide_id": "g_fox_slide_1",
            "link": (
                "https://docs.google.com/presentation/d/1refDeckFox123/edit#slide=id.g_fox_slide_1"
            ),
            "source_library": (
                "Customer Reference Library Customer Reference Library (Google Slides)"
            ),
        },
        {
            "customer": "Warner Bros. Discovery",
            "title": (
                "Warner Bros. Discovery: Scaling Streaming Personalization"
            ),
            "slideId": "g_wbd_slide_2",
            "deckId": "1refDeckWbd456",
            "deckTitle": "M&E Master Reference Deck",
            "slideURL": (
                "https://docs.google.com/presentation/d/1refDeckWbd456/edit#slide=id.g_wbd_slide_2"
            ),
            "description": (
                "3.4x viewer engagement lift with BigQuery and Gemini"
                " Enterprise."
            ),
            "source_library": (
                "Customer Reference Library Customer Reference Library (Google Slides)"
            ),
        },
    ]

    with (
        patch(
            "agents.workflows.customer_reference_retriever.NewLibraryCustomerReferenceRetriever.search_slides",
            return_value=fake_cust_refs,
        ),
        patch(
            "agents.sidebar_agent.SidebarAgent.search",
            return_value={"search_results": []},
        ) as mock_sidebar,
        patch(
            "pitchgen_utils.slide_thumbnail_util.resolve_thumbnail_candidate_tokens",
            return_value=[],
        ),
    ):
      raw_search = enterprise_search_slides_skill(
          search_query="Search for additional customer references",
          slide_job="Proof_Points",
          tool_context=ctx,
      )
      mock_sidebar.assert_not_called()

    parsed_search = json.loads(raw_search)
    self.assertEqual(parsed_search["status"], "success")
    self.assertEqual(parsed_search["active_presentation_id"], deck_id)
    self.assertGreaterEqual(parsed_search["total_found"], 2)

    slides = parsed_search["slides"]
    self.assertEqual(slides[0]["deck_id"], "1refDeckFox123")
    self.assertEqual(slides[0]["slide_id"], "g_fox_slide_1")
    self.assertEqual(slides[1]["deck_id"], "1refDeckWbd456")
    self.assertEqual(slides[1]["slide_id"], "g_wbd_slide_2")

    # Verify exactly one A2UI results card (separate from the search form) was
    # stashed with insert_library_slide wired to the active deck.
    self.assertEqual(len(ctx.state["a2ui_payloads_to_inject"]), 1)
    stashed_card = ctx.state["a2ui_payloads_to_inject"][0]
    self.assertIn("a2ui_v09_messages", stashed_card)
    v09_msgs = stashed_card["a2ui_v09_messages"]
    creates = [m for m in v09_msgs if "createSurface" in m]
    self.assertEqual(len(creates), 1)
    self.assertTrue(
        creates[0]["createSurface"]["surfaceId"].startswith(
            "pitchgen-search-results-"
        )
    )
    self.assertNotIn("pitchgen-slide-search", json.dumps(v09_msgs))
    self.assertIn("insert_library_slide", json.dumps(v09_msgs))
    self.assertIn(deck_id, json.dumps(v09_msgs))

    # Test 1-click slide insertion into active presentation
    with (
        patch("requests.post") as mock_post,
        patch(
            "agent.execute_apps_script_request",
            return_value={"status": 200, "relinkedCount": 1},
        ) as mock_script,
        patch(
            "agent._build_apps_script_candidate_tokens",
            return_value=[("user", "fake_token")],
        ),
    ):
      mock_post.return_value = MagicMock(status_code=200)
      raw_insert = enterprise_insert_slide_skill(
          source_presentation_id="1refDeckFox123",
          template_slide_id="g_fox_slide_1",
          target_presentation_id="",  # auto-resolves from ctx.state["presentation_id"]
          slide_title="FOX Sports: Real-Time GenMedia Highlights on Vertex AI",
          tool_context=ctx,
      )

    parsed_insert = json.loads(raw_insert)
    self.assertEqual(parsed_insert["status"], "success")
    self.assertEqual(parsed_insert["target_presentation_id"], deck_id)
    self.assertTrue(parsed_insert["placeholder_created"])
    self.assertTrue(parsed_insert["relinked_linked_slide"])
    mock_script.assert_called_once()

    # Verify A2UI client action routing for insert_library_slide in enterprise_before_model_callback
    action_turn = types.Content(
        role="user",
        parts=[
            types.Part(
                text=(
                    '<a2a_datapart_json>{"kind":"data","data":{"action":{"name":"insert_library_slide","context":{"source_presentation_id":"1refDeckFox123","template_slide_id":"g_fox_slide_1","target_presentation_id":"SAMPLE_TEST_PRESENTATION_ID_000000000016","slide_title":"FOX'
                    ' Sports"}}}}</a2a_datapart_json>'
                )
            )
        ],
    )
    req_obj = type("DummyReq", (), {"contents": [action_turn]})()
    enterprise_before_model_callback(ctx, req_obj)
    self.assertIn(
        "Invoke enterprise_insert_slide_skill",
        action_turn.parts[0].text,
    )

  def test_executive_chain_of_thought_sanitization(self):
    """Verifies that enterprise_after_model_callback replaces meta-prompt CoT leakages (WORKFLOW 0/1, state_json, <Customer>, <user_ldap>) with executive GTM reasoning."""
    from google.adk.models.llm_response import LlmResponse
    from google.genai import types
    from enterprise_agent import enterprise_after_model_callback

    ctx = type(
        "DummyCtx",
        (),
        {
            "state": {
                "customer_name": "Disney",
                "industry": "Media & Entertainment",
                "salesPlay": "Scale AI Apps & Agents",
            }
        },
    )()

    # 1. Pre-tool call with leaked prompt instructions in thought
    leaked_pre_tool_resp = LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    text=(
                        "My thought process on WORKFLOW 1: I need to call"
                        " enterprise_search_slides_skill with state_json and"
                        " <Customer> / <user_ldap> per my mandatory"
                        " requirement."
                    ),
                    thought=True,
                ),
                types.Part(
                    function_call=types.FunctionCall(
                        name="enterprise_search_slides_skill",
                        args={
                            "search_query": "Disney customer references",
                            "slide_job": "Proof_Points",
                        },
                    )
                ),
            ],
        )
    )
    sanitized_pre = enterprise_after_model_callback(ctx, leaked_pre_tool_resp)
    pre_thoughts = [
        p.text
        for p in sanitized_pre.content.parts
        if getattr(p, "thought", False)
    ]
    self.assertEqual(len(pre_thoughts), 1)
    self.assertNotIn("WORKFLOW 1", pre_thoughts[0])
    self.assertNotIn("<Customer>", pre_thoughts[0])
    self.assertNotIn("state_json", pre_thoughts[0])
    self.assertIn(
        "2026 Consolidated Customer Reference Library", pre_thoughts[0]
    )
    self.assertIn("Disney", pre_thoughts[0])

    # 2. Post-tool response with stashed executive CoT summary replacing low-quality thought
    ctx.state["latest_cot_summary"] = (
        "**Customer Reference & Slide Library Retrieval**\n- **Query & Account"
        " Context**: Searched consolidated 2026 Customer Reference Library for"
        " `Disney`.\n- **Matched Assets (4 found)**: Ranked verified Media &"
        " Entertainment proof points."
    )
    leaked_post_tool_resp = LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    text="Following WORKFLOW 2 and <deck_url> rules...",
                    thought=True,
                ),
                types.Part(
                    text=(
                        "Here are the top Media & Entertainment customer"
                        " references for Disney."
                    )
                ),
            ],
        )
    )
    sanitized_post = enterprise_after_model_callback(ctx, leaked_post_tool_resp)
    post_thoughts = [
        p.text
        for p in sanitized_post.content.parts
        if getattr(p, "thought", False)
    ]
    self.assertEqual(len(post_thoughts), 1)
    self.assertNotIn("WORKFLOW 2", post_thoughts[0])
    self.assertNotIn("<deck_url>", post_thoughts[0])
    self.assertIn(
        "Customer Reference & Slide Library Retrieval", post_thoughts[0]
    )

  def test_resilient_gcs_session_service_prevents_429_and_500_crashes(self):
    """Verifies ResilientGcsSessionService handles create_session, get_session, and append_event without Vertex AI Session Service 429/500 errors and preserves session_id."""
    import asyncio
    from google.adk.events.event import Event
    from google.adk.events.event_actions import EventActions
    from google.genai import types
    from agent_runtime_app import ResilientGcsSessionService

    svc = ResilientGcsSessionService(bucket_name="")

    async def _run_check():
      # 1. Create session with a full resource name or GE session_id
      sess = await svc.create_session(
          app_name="YOUR_REASONING_ENGINE_ID",
          user_id="seller_user",
          session_id="projects/000000000000/locations/us-central1/reasoningEngines/YOUR_REASONING_ENGINE_ID/sessions/11996700356475901323",
          state={
              "customer_name": "Mercedes",
              "presentation_id": "SAMPLE_TEST_PRESENTATION_ID_000000000005",
          },
      )
      self.assertEqual(sess.id, "11996700356475901323")
      self.assertEqual(sess.state["customer_name"], "Mercedes")

      # 2. Duplicate create_session with same session_id updates/returns existing session instead of raising AlreadyExistsError
      sess_dup = await svc.create_session(
          app_name="YOUR_REASONING_ENGINE_ID",
          user_id="seller_user",
          session_id="11996700356475901323",
          state={"industry": "Automotive"},
      )
      self.assertEqual(sess_dup.id, "11996700356475901323")
      self.assertEqual(sess_dup.state["industry"], "Automotive")

      # 3. Append event with state_delta
      ev = Event(
          author="pitchgen_enterprise_agent",
          invocation_id="inv_1",
          content=types.Content(
              role="model",
              parts=[types.Part(text="Found 8 automotive references.")],
          ),
          actions=EventActions(
              state_delta={"last_query": "Mercedes references"}
          ),
          turn_complete=True,
      )
      await svc.append_event(sess_dup, ev)

      # 4. Retrieve session even if caller passes a different user_id alias
      fetched = await svc.get_session(
          app_name="YOUR_REASONING_ENGINE_ID",
          user_id="default-user-id",
          session_id="11996700356475901323",
      )
      self.assertIsNotNone(fetched)
      self.assertEqual(fetched.state.get("customer_name"), "Mercedes")
      self.assertEqual(fetched.state.get("last_query"), "Mercedes references")
      self.assertEqual(len(fetched.events), 1)

    asyncio.run(_run_check())

  def test_in_place_a2ui_insert_and_transform_preserve_active_deck(self):
    """Verifies that A2UI slide search, insertion, and transformation mutate the active iframe presentation in-place without matching tool names or creating a new deck."""
    import json
    from unittest import mock
    from google.genai import types

    try:
      from pitchgen.src import agent as core_agent
      from pitchgen.src import enterprise_agent as ent_agent
    except ImportError:
      import agent as core_agent
      import enterprise_agent as ent_agent

    active_deck_id = "SAMPLE_TEST_PRESENTATION_ID_000000000017"
    source_lib_id = "SAMPLE_TEST_PRESENTATION_ID_000000000002"

    # 1. Verify extract_presentation_id in both a2ui and agent rejects snake_case tool names
    for tool_name in (
        "enterprise_insert_slide_skill",
        "enterprise_transform_slide_text_skill",
        "enterprise_search_slides_skill",
        "enterprise_slide_generator_skill",
        "active",
        "current_deck",
    ):
      self.assertIsNone(a2ui.extract_presentation_id(tool_name))
      self.assertEqual(core_agent.extract_presentation_id(tool_name), "")

    # 2. Verify extract_presentation_id ignores rewritten prompt text in user_content.parts
    # and resolves the real presentation_id from explicit argument or state
    class DummyCtx:

      def __init__(self):
        self.state = {
            "presentation_id": active_deck_id,
            "deck_url": (
                f"https://docs.google.com/presentation/d/{active_deck_id}/edit"
            ),
            "customer_name": "Intel",
        }
        self.user_content = types.Content(
            role="user",
            parts=[
                types.Part(
                    text=(
                        "Invoke enterprise_transform_slide_text_skill with"
                        f" presentation_url_or_id='{active_deck_id}'."
                    )
                )
            ],
        )

    ctx = DummyCtx()
    self.assertEqual(
        core_agent.extract_presentation_id(active_deck_id, ctx),
        active_deck_id,
    )
    self.assertEqual(
        core_agent.extract_presentation_id(source_lib_id, ctx),
        source_lib_id,
    )
    self.assertEqual(
        core_agent.extract_presentation_id("active", ctx),
        active_deck_id,
    )

    # 3. Verify enterprise_insert_slide_skill targets active_deck_id in-place and reads 'relinked'
    with (
        mock.patch.object(
            core_agent, "_build_apps_script_candidate_tokens", return_value=[]
        ),
        mock.patch.object(
            core_agent, "execute_apps_script_request"
        ) as mock_apps_script,
        mock.patch.object(
            core_agent.PitchGenSkills,
            "_transform_presentation_slides_via_rest_api",
        ) as mock_rest_transform,
    ):
      mock_apps_script.return_value = {
          "status": "success",
          "relinked": [{
              "placeholderId": "g_temp_1",
              "newSlideId": "g_relinked_slide_99",
              "sourceId": source_lib_id,
              "templateSlideId": "g_src_slide_42",
          }],
      }
      mock_rest_transform.return_value = {
          "status": "success",
          "transformed_count": 1,
          "slides_summary": [
              {"slide_index": 5, "slide_id": "g_relinked_slide_99"}
          ],
      }

      insert_res_raw = core_agent.PitchGenSkills.enterprise_insert_slide_skill(
          source_presentation_id=source_lib_id,
          template_slide_id="g_src_slide_42",
          target_presentation_id="active",
          slide_title="Broadcom Semiconductor Proof Point",
          slide_job="Proof_Points",
          tool_context=ctx,
      )
      insert_res = json.loads(insert_res_raw)
      self.assertEqual(insert_res["status"], "success")
      self.assertEqual(insert_res["target_presentation_id"], active_deck_id)
      self.assertEqual(insert_res["inserted_slide_id"], "g_relinked_slide_99")
      self.assertIn(active_deck_id, insert_res["deck_url"])

    # 4. Verify enterprise_transform_slide_text_skill mutates active_deck_id in-place without calling execute_apps_script_request when REST succeeds
    with (
        mock.patch.object(
            core_agent, "execute_apps_script_request"
        ) as mock_apps_script_tf,
        mock.patch.object(
            core_agent.PitchGenSkills,
            "_transform_presentation_slides_via_rest_api",
        ) as mock_rest_tf,
    ):
      mock_rest_tf.return_value = {
          "status": "success",
          "transformed_count": 3,
          "slides_summary": [
              {"slide_index": 1, "slide_id": "s1"},
              {"slide_index": 2, "slide_id": "s2"},
              {"slide_index": 3, "slide_id": "s3"},
          ],
      }
      tf_res_raw = (
          core_agent.PitchGenSkills.enterprise_transform_slide_text_skill(
              presentation_url_or_id="active",
              customization_criteria="Tighten executive tone for Intel",
              target_slide_indices="1-3",
              tool_context=ctx,
          )
      )
      tf_res = json.loads(tf_res_raw)
      self.assertEqual(tf_res["status"], "success")
      self.assertEqual(tf_res["presentation_id"], active_deck_id)
      self.assertIn(active_deck_id, tf_res["deck_url"])
      mock_apps_script_tf.assert_not_called()

  def test_a2ui_v09_pitchgen_launcher_and_routing(self):
    """Verifies Card 1 (pitchgen-launcher) A2UI v0.9 generation, tool callback stripping, and 8-feature launch_feature routing."""
    import json
    from google.genai import types
    from google.adk.models.llm_response import LlmResponse
    from enterprise_agent import (
        enterprise_launcher_card_skill,
        enterprise_after_tool_callback,
        enterprise_before_model_callback,
        enterprise_after_model_callback,
    )

    # 1. Verify canonical A2UI v0.9 messages for pitchgen-launcher
    msgs = a2ui.create_a2ui_v09_launcher_messages(
        surface_id="pitchgen-launcher"
    )
    self.assertEqual(len(msgs), 3)
    self.assertEqual(msgs[0]["version"], "v0.9")
    self.assertEqual(msgs[0]["createSurface"]["surfaceId"], "pitchgen-launcher")
    self.assertEqual(
        msgs[0]["createSurface"]["catalogId"],
        "https://a2ui.org/specification/v0_9/material_catalog.json",
    )
    self.assertEqual(msgs[1]["version"], "v0.9")
    self.assertEqual(
        msgs[1]["updateComponents"]["surfaceId"], "pitchgen-launcher"
    )
    self.assertEqual(len(msgs[1]["updateComponents"]["components"]), 48)
    self.assertEqual(msgs[2]["version"], "v0.9")
    self.assertEqual(
        msgs[2]["updateDataModel"]["surfaceId"], "pitchgen-launcher"
    )

    # Verify all 5 consolidated launch_feature MaterialButton components exist with expected target_card values
    btns = [
        c
        for c in msgs[1]["updateComponents"]["components"]
        if c.get("component") == "MaterialButton"
    ]
    self.assertEqual(len(btns), 5)
    icons = [
        c
        for c in msgs[1]["updateComponents"]["components"]
        if c.get("component") == "MaterialIcon"
    ]
    self.assertEqual(len(icons), 6)
    brand_logos = [
        c
        for c in msgs[1]["updateComponents"]["components"]
        if c.get("id") == "pitchgen_tool_logo"
        and c.get("component") == "MaterialRow"
    ]
    self.assertEqual(len(brand_logos), 1)
    self.assertEqual(
        brand_logos[0]["children"],
        ["pitchgen_logo_icon", "pitchgen_logo_text_row"],
    )
    self.assertFalse(
        any(
            c.get("component") == "Image"
            for c in msgs[1]["updateComponents"]["components"]
        )
    )
    target_cards = [
        b["action"]["event"]["context"]["target_card"] for b in btns
    ]
    self.assertEqual(
        target_cards,
        [
            "generate_pitch",
            "search_slide",
            "transform_text",
            "generate_nanobanana",
            "translate",
        ],
    )
    comp_by_id = {c["id"]: c for c in msgs[1]["updateComponents"]["components"]}
    self.assertEqual(
        comp_by_id["grid_row_1"]["children"], ["card_generate_pitch"]
    )
    self.assertEqual(
        comp_by_id["grid_row_1"]["style"]["gridTemplateColumns"],
        "minmax(0, 1fr)",
    )
    self.assertEqual(
        comp_by_id["grid_row_2"]["children"],
        ["card_search_slide", "card_transform_text"],
    )
    self.assertEqual(
        comp_by_id["grid_row_2"]["style"]["gridTemplateColumns"],
        "repeat(2, minmax(0, 1fr))",
    )
    self.assertEqual(
        comp_by_id["grid_row_3"]["children"],
        ["card_generate_nanobanana", "card_translate"],
    )
    self.assertEqual(
        comp_by_id["grid_row_3"]["style"]["gridTemplateColumns"],
        "repeat(2, minmax(0, 1fr))",
    )
    header_dm = msgs[2]["updateDataModel"]["value"]["header"]
    self.assertEqual(header_dm["title"], "PitchGen")
    self.assertEqual(
        header_dm["subtitle"],
        "AI-Powered Google Slides Enablement & Presentation Studio",
    )

    # 2. Verify enterprise_launcher_card_skill + enterprise_after_tool_callback
    ctx = type("MockCtx", (), {"state": {}})()
    raw_tool_res = enterprise_launcher_card_skill(tool_context=ctx)
    self.assertIn("<a2ui-json>", raw_tool_res)
    self.assertEqual(len(ctx.state.get("a2ui_payloads_to_inject", [])), 3)

    mock_tool = type(
        "MockTool", (), {"name": "enterprise_launcher_card_skill"}
    )()
    cleaned_dict = enterprise_after_tool_callback(
        mock_tool, {}, ctx, raw_tool_res
    )
    self.assertIsInstance(cleaned_dict, dict)
    self.assertNotIn("<a2ui-json>", cleaned_dict["result"])
    self.assertEqual(len(ctx.state.get("a2ui_payloads_to_inject", [])), 3)

    # 3. Verify enterprise_after_model_callback wraps pitchgen-launcher in <a2a_datapart_json>
    llm_resp = LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    text=(
                        "Welcome to **PitchGen**! Use the Feature Launcher Hub"
                        " above."
                    )
                )
            ],
        )
    )
    final_resp = enterprise_after_model_callback(ctx, llm_resp)
    self.assertTrue(final_resp.custom_metadata.get("a2a:response"))
    inline_parts = [
        p.inline_data.data.decode("utf-8")
        for p in final_resp.content.parts
        if getattr(p, "inline_data", None)
    ]
    self.assertEqual(len(inline_parts), 3)
    self.assertIn('"surfaceId": "pitchgen-launcher"', inline_parts[0])
    self.assertIn('"updateComponents"', inline_parts[1])
    self.assertIn('"updateDataModel"', inline_parts[2])

    # 4. Verify enterprise_before_model_callback routes launch_feature target_cards
    for tc in target_cards:
      cb_ctx = type("MockCtx", (), {"state": {}})()
      action_payload = json.dumps({
          "action": {
              "event": {
                  "name": "launch_feature",
                  "context": {"target_card": tc},
              }
          }
      })
      req = type(
          "MockReq",
          (),
          {
              "contents": [
                  types.Content(
                      role="user",
                      parts=[types.Part(text=action_payload)],
                  )
              ]
          },
      )()
      resp = enterprise_before_model_callback(cb_ctx, req)
      self.assertEqual(
          cb_ctx.state.get("last_target_card"),
          "" if tc in ("search_slide", "search") else tc,
          f"Unexpected last_target_card for {tc}",
      )
      self.assertIsNotNone(resp)
      self.assertTrue(resp.custom_metadata.get("a2a:response"))
      inline_parts = [
          p.inline_data.data.decode("utf-8")
          for p in resp.content.parts
          if getattr(p, "inline_data", None)
      ]
      self.assertGreaterEqual(len(inline_parts), 2)

    # 5. Verify normal responses containing "hi" inside words ("this", "architecture") do NOT falsely inject launcher card
    non_greeting_ctx = type("MockCtx", (), {"state": {}})()
    non_greeting_resp = LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    text=(
                        "Here is your polished executive copy for this cloud"
                        " architecture slide."
                    )
                )
            ],
        )
    )
    out_non_greeting = enterprise_after_model_callback(
        non_greeting_ctx, non_greeting_resp
    )
    non_greeting_inline = [
        p
        for p in out_non_greeting.content.parts
        if getattr(p, "inline_data", None)
    ]
    self.assertEqual(len(non_greeting_inline), 0)

    # 6. Verify bare greeting turn ("Hi!") fast-paths to launcher hub via enterprise_before_model_callback
    greet_ctx = type("MockCtx", (), {"state": {}})()
    greet_req = type(
        "MockReq",
        (),
        {
            "contents": [
                types.Content(role="user", parts=[types.Part(text="Hi!")])
            ]
        },
    )()
    fast_greet_resp = enterprise_before_model_callback(greet_ctx, greet_req)
    self.assertIsNotNone(fast_greet_resp)
    self.assertTrue(fast_greet_resp.custom_metadata.get("a2a:response"))
    fast_greet_inline = [
        p.inline_data.data.decode("utf-8")
        for p in fast_greet_resp.content.parts
        if getattr(p, "inline_data", None)
    ]
    self.assertEqual(len(fast_greet_inline), 3)
    self.assertIn('"surfaceId": "pitchgen-launcher"', fast_greet_inline[0])

    # Also verify fallback injection via enterprise_after_model_callback if is_greeting_turn was flagged
    fallback_ctx = type(
        "MockCtx", (), {"state": {"is_greeting_turn": True}}
    )()
    greet_resp = LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part(text="Hello! How can I help you today?")],
        )
    )
    out_greet = enterprise_after_model_callback(fallback_ctx, greet_resp)
    greet_inline = [
        p.inline_data.data.decode("utf-8")
        for p in out_greet.content.parts
        if getattr(p, "inline_data", None)
    ]
    self.assertEqual(len(greet_inline), 3)
    self.assertIn('"surfaceId": "pitchgen-launcher"', greet_inline[0])
    self.assertFalse(fallback_ctx.state.get("is_greeting_turn"))

    # 7. Verify multi-part user Content (DataPart + trailing TextPart) preserves last_target_card and nested userAction.event
    mp_ctx = type("MockCtx", (), {"state": {}})()
    nested_event_json = json.dumps({
        "userAction": {
            "event": {
                "name": "launch_feature_card",
                "context": {"targetCard": "generate_pitch"},
            }
        }
    })
    mp_req = type(
        "MockReq",
        (),
        {
            "contents": [
                types.Content(
                    role="user",
                    parts=[
                        types.Part(text=nested_event_json),
                        types.Part(text="Launch Deck Generation →"),
                    ],
                )
            ]
        },
    )()
    enterprise_before_model_callback(mp_ctx, mp_req)
    self.assertEqual(mp_ctx.state.get("last_target_card"), "generate_pitch")

    # 8. Verify visible anchor text is automatically added if LLM only emitted a thought part when A2UI messages are present
    thought_only_ctx = type(
        "MockCtx",
        (),
        {"state": {"a2ui_payloads_to_inject": msgs}},
    )()
    thought_only_resp = LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part(text="Thinking about greeting...", thought=True)],
        )
    )
    out_thought_only = enterprise_after_model_callback(
        thought_only_ctx, thought_only_resp
    )
    visible_texts = [
        p.text
        for p in out_thought_only.content.parts
        if getattr(p, "text", None) and not getattr(p, "thought", False)
    ]
    self.assertEqual(len(visible_texts), 1)
    self.assertIn("Welcome to **PitchGen**", visible_texts[0])

    # 9. Verify cross-session isolation: calling enterprise_intake_form_skill on session A does not leak into session B's enterprise_after_tool_callback
    from enterprise_agent import enterprise_intake_form_skill

    session_a_ctx = type("MockCtx", (), {"state": {}})()
    enterprise_intake_form_skill(
        customer_name="Nike", tool_context=session_a_ctx
    )
    session_b_ctx = type("MockCtx", (), {"state": {}})()
    raw_b = enterprise_launcher_card_skill(tool_context=session_b_ctx)
    enterprise_after_tool_callback(mock_tool, {}, session_b_ctx, raw_b)
    self.assertEqual(
        len(session_b_ctx.state.get("a2ui_payloads_to_inject", [])), 3
    )
    self.assertEqual(
        session_b_ctx.state["a2ui_payloads_to_inject"][0]["createSurface"][
            "surfaceId"
        ],
        "pitchgen-launcher",
    )

    # 10. Verify non-launcher <a2a_datapart_json> A2UI events (create_proposal_outline, refine_proposal_outline, approve_outline_and_generate) map to explicit tool prompts and pass through to LLM (return None)
    outline_datapart = a2ui.format_a2ui_datapart({
        "userAction": {
            "name": "create_proposal_outline",
            "surfaceId": "gtm_intake_surface",
            "context": {
                "customer_name": "Walmart",
                "sales_play": "Scale AI Apps & Agents",
            },
        }
    })
    outline_req = type(
        "MockReq",
        (),
        {
            "contents": [
                types.Content(
                    role="user", parts=[types.Part(text=outline_datapart)]
                )
            ]
        },
    )()
    outline_ctx = type("MockCtx", (), {"state": {}})()
    cb_result = enterprise_before_model_callback(outline_ctx, outline_req)
    self.assertIsNone(cb_result)
    self.assertNotIn(
        a2ui.A2A_DATA_PART_START_TAG, outline_req.contents[0].parts[0].text
    )
    self.assertIn(
        "enterprise_create_proposal_outline",
        outline_req.contents[0].parts[0].text,
    )
    self.assertIn("Walmart", outline_req.contents[0].parts[0].text)

    approve_datapart = a2ui.format_a2ui_datapart({
        "event": {
            "name": "approve_outline_and_generate",
            "context": {
                "customer_name": "Walmart",
                "deck_strategy": "smart_hybrid",
            },
        }
    })
    approve_req = type(
        "MockReq",
        (),
        {
            "contents": [
                types.Content(
                    role="user", parts=[types.Part(text=approve_datapart)]
                )
            ]
        },
    )()
    self.assertIsNone(
        enterprise_before_model_callback(outline_ctx, approve_req)
    )
    self.assertIn(
        "enterprise_slide_generator_skill",
        approve_req.contents[0].parts[0].text,
    )

    # 11. Verify server.extract_action_payload extracts userAction from message.parts with kind=='data'
    from ge import server as ge_server

    prompt_out, params_out = ge_server.extract_action_payload({
        "message": {
            "role": "user",
            "parts": [{
                "kind": "data",
                "data": {
                    "userAction": {
                        "name": "launch_feature",
                        "context": {"target_card": "generate_pitch"},
                    }
                },
            }],
        }
    })
    self.assertEqual(prompt_out, "launch_feature")
    self.assertEqual(params_out.get("target_card"), "generate_pitch")

    # 12. Verify _hydrate_slide_generator_state propagates top-level deck_strategy and agenda_sections
    from src.enterprise_agent import _hydrate_slide_generator_state, enterprise_create_proposal_outline

    hydrate_ctx = type(
        "MockHydrateCtx",
        (),
        {
            "state": {
                "proposal_outline": json.dumps({
                    "Status": "True",
                    "data": {
                        "context": {
                            "customer_name": "Walmart",
                            "industry": "Retail & CPG",
                            "salesPlay": ["Scale AI Apps & Agents"],
                            "er_number": "ER-99999",
                            "deck_strategy": "smart_hybrid",
                            "user_ldap": "admin_user",
                        },
                        "agendas": {
                            "1": {
                                "title": "Old Section 1",
                                "parts": ["Old bullet"],
                            },
                        },
                    },
                })
            }
        },
    )()
    hydrated_str = _hydrate_slide_generator_state(
        json.dumps({
            "customer_name": "Walmart",
            "deck_strategy": "bespoke_custom",
            "agenda_sections": [{
                "title": "Updated Section 1",
                "subtopics": ["New bullet A", "New bullet B"],
            }],
        }),
        tool_context=hydrate_ctx,
    )
    hydrated_obj = json.loads(hydrated_str)
    self.assertEqual(hydrated_obj["context"]["deck_strategy"], "bespoke_custom")
    self.assertEqual(hydrated_obj["context"]["er_number"], "ER-99999")
    self.assertEqual(hydrated_obj["agendas"]["1"]["title"], "Updated Section 1")
    self.assertEqual(
        hydrated_obj["agendas"]["1"]["parts"], ["New bullet A", "New bullet B"]
    )

    # 13. Verify enterprise_create_proposal_outline backfills omitted fields during refinement
    from unittest import mock
    from src import enterprise_agent as ea_mod

    with mock.patch.object(
        ea_mod.PitchGenSkills, "create_proposal_outline"
    ) as mock_cpo:
      mock_cpo.return_value = hydrate_ctx.state["proposal_outline"]
      enterprise_create_proposal_outline(
          business_context="Add Zero Trust Security section",
          customer_name="Walmart",
          tool_context=hydrate_ctx,
      )
      called_kwargs = mock_cpo.call_args.kwargs
      self.assertEqual(called_kwargs["industry"], "Retail & CPG")
      self.assertEqual(called_kwargs["er_number"], "ER-99999")
      self.assertIn(
          called_kwargs["salesPlay"],
          ("Scale AI Apps & Agents", "Scale AI Apps and Agents"),
      )

    # 14. Verify enterprise_agent.tools includes all 15+ tools covering all 8 Card 1 capabilities + GTM & OAuth tools
    tool_names = [
        getattr(t, "__name__", getattr(t, "name", str(t)))
        for t in ea_mod.enterprise_agent.tools
    ]
    for expected_tool in [
        "enterprise_launcher_card_skill",
        "enterprise_intake_form_skill",
        "enterprise_transform_text_form_skill",
        "consult_skill",
        "enterprise_create_proposal_outline",
        "enterprise_slide_generator_skill",
        "enterprise_search_slides_skill",
        "sidebar_generate",
        "enterprise_transform_slide_text_skill",
        "enterprise_generate_visuals_skill",
        "transform_raw_text_skill",
        "enterprise_translate_deck_skill",
        "phub_handoff_skill",
        "rfp_accelerator_skill",
        "submit_authorization_code",
    ]:
      self.assertIn(expected_tool, tool_names)

  def test_transform_text_a2ui_v09_integration(self):
    """Verify A2UI v0.9 pitchgen-transform-text card, form skill, callback routing, and service helpers."""
    import json
    import google.genai
    from src import enterprise_agent as ea_mod
    from src.services.deck_transformation_service import DeckTransformationService

    # 1. Verify create_a2ui_v09_transform_text_messages returns exact 3-message A2UI v0.9 Material structure
    msgs = a2ui.create_a2ui_v09_transform_text_messages()
    self.assertEqual(len(msgs), 3)
    self.assertEqual(msgs[0]["version"], "v0.9")
    self.assertEqual(
        msgs[0]["createSurface"]["surfaceId"], "pitchgen-transform-text"
    )
    self.assertEqual(
        msgs[0]["createSurface"]["catalogId"],
        "https://a2ui.org/specification/v0_9/material_catalog.json",
    )
    dm = msgs[1]["updateDataModel"]["value"]
    self.assertEqual(dm["full_deck_scope"], ["full_deck"])
    self.assertEqual(dm["industry"], "")
    self.assertEqual(dm["audience"], "")

    comps = {c["id"]: c for c in msgs[2]["updateComponents"]["components"]}
    self.assertEqual(comps["root"]["component"], "MaterialCard")
    self.assertEqual(comps["industry_select"]["component"], "MaterialSelect")
    self.assertEqual(
        comps["industry_select"]["options"][0]["label"], "Industry Vertical"
    )
    self.assertEqual(comps["audience_select"]["component"], "MaterialSelect")
    self.assertEqual(
        comps["audience_select"]["options"][0]["label"],
        "Target Audience Persona",
    )
    submit_ctx = comps["btn_transform_submit"]["action"]["event"]["context"]
    self.assertEqual(submit_ctx["industry"], {"path": "/industry"})
    self.assertEqual(submit_ctx["audience"], {"path": "/audience"})

    # 2. Verify enterprise_transform_text_form_skill pre-populates active deck & customer from session state
    ctx = type(
        "MockTransformCtx",
        (),
        {
            "state": {
                "last_presentation_id": "deck_active_999",
                "customer_name": "Acme Corp",
            }
        },
    )()
    res_str = ea_mod.enterprise_transform_text_form_skill(tool_context=ctx)
    self.assertIn("<a2ui-json>", res_str)
    self.assertIn("pitchgen-transform-text", res_str)
    self.assertEqual(len(ctx.state["a2ui_payloads_to_inject"]), 3)
    self.assertEqual(
        ctx.state["a2ui_payloads_to_inject"][1]["updateDataModel"]["value"][
            "presentation_url_or_id"
        ],
        "deck_active_999",
    )
    self.assertEqual(
        ctx.state["a2ui_payloads_to_inject"][1]["updateDataModel"]["value"][
            "customer_name"
        ],
        "Acme Corp",
    )

    # 3. Verify launch_feature_card with target_card="transform_text" routes to enterprise_transform_text_form_skill
    launch_dp = a2ui.format_a2ui_datapart({
        "event": {
            "name": "launch_feature_card",
            "context": {
                "target_card": "transform_text",
                "workflow_mode": "transform_text",
            },
        }
    })
    launch_req = type(
        "MockReq",
        (),
        {
            "contents": [
                google.genai.types.Content(
                    role="user", parts=[google.genai.types.Part(text=launch_dp)]
                )
            ]
        },
    )()
    launch_ctx = type("MockCtx", (), {"state": {}})()
    launch_resp = ea_mod.enterprise_before_model_callback(
        launch_ctx, launch_req
    )
    self.assertIsNotNone(launch_resp)
    self.assertTrue(launch_resp.custom_metadata.get("a2a:response"))
    inline_parts = [
        p.inline_data.data.decode("utf-8")
        for p in launch_resp.content.parts
        if getattr(p, "inline_data", None)
    ]
    self.assertTrue(any("pitchgen-transform-text" in s for s in inline_parts))

    # 4. Verify transform_slide_text event submission maps all v0.9 context fields
    submit_dp = a2ui.format_a2ui_datapart({
        "event": {
            "name": "transform_slide_text",
            "context": {
                "presentation_url_or_id": "abcd_deck_id",
                "custom_instructions": "Rewrite for retail executives",
                "customer_name": "Target",
                "full_deck_scope": [],
                "target_slide_indices": "1,2",
                "industry": [""],
                "audience": ["Executive"],
            },
        }
    })
    submit_req = type(
        "MockReq",
        (),
        {
            "contents": [
                google.genai.types.Content(
                    role="user", parts=[google.genai.types.Part(text=submit_dp)]
                )
            ]
        },
    )()
    submit_ctx = type("MockCtx", (), {"state": {}})()
    self.assertIsNone(
        ea_mod.enterprise_before_model_callback(submit_ctx, submit_req)
    )
    prompt_text = submit_req.contents[0].parts[0].text
    self.assertIn("enterprise_transform_slide_text_skill", prompt_text)
    self.assertIn("abcd_deck_id", prompt_text)
    self.assertIn("Rewrite for retail executives", prompt_text)
    self.assertIn("1,2", prompt_text)
    self.assertIn("Target", prompt_text)
    self.assertIn("Executive", prompt_text)

    # 5. Verify DeckTransformationService field normalization and slide index parsing
    self.assertEqual(
        DeckTransformationService._normalize_card_list_field([""]), ""
    )
    self.assertEqual(
        DeckTransformationService._normalize_card_list_field(["industry"]), ""
    )
    self.assertEqual(
        DeckTransformationService._normalize_card_list_field(["audience"]), ""
    )
    self.assertEqual(
        DeckTransformationService._normalize_card_list_field(
            ["Retail & Consumer Goods"]
        ),
        "Retail & Consumer Goods",
    )
    self.assertEqual(
        DeckTransformationService._normalize_card_list_field(
            ["Executive", "Technical"]
        ),
        "Executive, Technical",
    )
    self.assertEqual(
        DeckTransformationService._parse_target_slide_indices("1, 2, 4-5", []),
        {1, 2, 4, 5},
    )
    self.assertEqual(
        DeckTransformationService._parse_target_slide_indices(
            "1, 2", ["full_deck"]
        ),
        set(),
    )

    # 6. Verify multi-slide SlideEngineeringAgent.transform_presentation (Agenda/Divider sync, Proof Point & Closing immutability, Internal Context table update, and target_slide_ids scoping)
    from unittest import mock
    from agents.slide_engineering_agent import SlideEngineeringAgent

    se_agent = SlideEngineeringAgent({
        "default": {
            "project_name": "your-gcp-project-id",
            "gemini_model": "gemini-3.8-flash",
            "gemini_model_1": "gemini-3.5-flash-lite",
            "region": "global",
        }
    })

    def fake_execute_batch(
        texts,
        criteria="",
        context=None,
        slide_name="",
        slide_data=None,
        **kwargs,
    ):
      if "Agenda" in slide_name or any("Agenda" in t for t in texts):
        out = []
        for t in texts:
          if "Agenda" in t:
            out.append("Agenda")
          elif "01" in t:
            out.append("01 Retail Supply Chain")
          elif "02" in t:
            out.append("02 Agentic Store Operations")
          else:
            out.append(f"[Transformed] {t}")
        return out
      return [f"[Transformed] {t}" for t in texts]

    sample_deck = {
        "slide_1_internal": {
            "shapes": {
                "banner_1": {
                    "0": {
                        "Text": (
                            "INTERNAL CONTEXT: PLEASE REMOVE THIS SLIDE BEFORE"
                            " YOU PRESENT"
                        ),
                        "HadNewline": False,
                    }
                },
            },
            "tables": {
                "tbl_1": {
                    "0_0": {
                        "0": {"Text": "Opportunity ID", "HadNewline": False}
                    },
                    "0_1": {"0": {"Text": "-", "HadNewline": False}},
                    "1_0": {
                        "0": {"Text": "Target Customer", "HadNewline": False}
                    },
                    "1_1": {"0": {"Text": "Old Customer", "HadNewline": False}},
                    "3_0": {"0": {"Text": "Industry", "HadNewline": False}},
                    "3_1": {"0": {"Text": "Old Industry", "HadNewline": False}},
                }
            },
        },
        "slide_2_agenda": {
            "shapes": {
                "sh_ag_title": {"0": {"Text": "Agenda", "HadNewline": False}},
                "sh_ag_items": {
                    "0": {
                        "Text": "01 Legacy Banking Trends",
                        "HadNewline": True,
                    },
                    "1": {
                        "Text": "02 Core Banking Platform",
                        "HadNewline": False,
                    },
                },
            }
        },
        "slide_3_divider": {
            "shapes": {
                "sh_div_num": {"0": {"Text": "01", "HadNewline": False}},
                "sh_div_title": {
                    "0": {"Text": "Legacy Banking Trends", "HadNewline": False}
                },
            }
        },
        "slide_4_proof": {
            "shapes": {
                "sh_pf_title": {
                    "0": {
                        "Text": (
                            "Case Study: Lowe's transforms retail with Google"
                            " Cloud"
                        ),
                        "HadNewline": False,
                    }
                },
                "sh_pf_body": {
                    "0": {
                        "Text": (
                            "Challenge: Legacy stores. Solution: Gemini"
                            " Enterprise. Results: 40% faster."
                        ),
                        "HadNewline": False,
                    }
                },
            }
        },
        "slide_5_content": {
            "shapes": {
                "sh_ct_title": {
                    "0": {
                        "Text": "Modernizing Enterprise Data Architecture",
                        "HadNewline": False,
                    }
                },
                "sh_ct_body": {
                    "0": {
                        "Text": (
                            "Unify real-time data pipelines across global"
                            " operations."
                        ),
                        "HadNewline": False,
                    }
                },
            }
        },
        "slide_6_closing": {
            "shapes": {
                "sh_cl_title": {
                    "0": {"Text": "Thank You", "HadNewline": False}
                },
            }
        },
    }

    with mock.patch.object(
        se_agent.skills["text_transformer"],
        "execute_batch",
        side_effect=fake_execute_batch,
    ):
      transformed_full = se_agent.transform_presentation(
          presentation_data=sample_deck,
          output_criteria=(
              "Tailor presentation text to Target in the Retail & Consumer"
              " Goods industry."
          ),
          slide_name="Full Deck Transform Text",
          context={
              "customer_name": "Target",
              "industry": "Retail & Consumer Goods",
              "opportunity_id": "ER-12345",
          },
      )
      # Slide 1 Internal Enablement: shapes cleared so header shapes aren't mutated, table cells updated
      self.assertEqual(transformed_full["slide_1_internal"]["shapes"], {})
      self.assertEqual(
          transformed_full["slide_1_internal"]["tables"]["tbl_1"]["1_1"]["0"][
              "Text"
          ],
          "Target",
      )
      # Slide 3 Divider: synced to Agenda item 01 ("Retail Supply Chain")
      self.assertEqual(
          transformed_full["slide_3_divider"]["shapes"]["sh_div_title"]["0"][
              "Text"
          ],
          "Retail Supply Chain",
      )
      # Slide 4 Proof Point: 0% immutable (_skip_mutation = True, skip = True)
      self.assertTrue(transformed_full["slide_4_proof"].get("_skip_mutation"))
      self.assertTrue(transformed_full["slide_4_proof"].get("skip"))
      # Slide 5 Content: transformed
      self.assertIn(
          "[Transformed]",
          transformed_full["slide_5_content"]["shapes"]["sh_ct_title"]["0"][
              "Text"
          ],
      )
      # Slide 6 Closing: 0% immutable (_skip_mutation = True, skip = True)
      self.assertTrue(transformed_full["slide_6_closing"].get("_skip_mutation"))
      self.assertTrue(transformed_full["slide_6_closing"].get("skip"))

      # Test target_slide_ids scoping (only Slide 5 targeted)
      transformed_scoped = se_agent.transform_presentation(
          presentation_data=sample_deck,
          output_criteria=(
              "Tailor presentation text to Target in the Retail & Consumer"
              " Goods industry."
          ),
          slide_name="Slides 5",
          context={
              "customer_name": "Target",
              "industry": "Retail & Consumer Goods",
              "target_slide_ids": {5},
          },
      )
      self.assertTrue(
          transformed_scoped["slide_2_agenda"].get("_skip_mutation")
      )
      self.assertFalse(
          transformed_scoped["slide_5_content"].get("_skip_mutation", False)
      )
      self.assertIn(
          "[Transformed]",
          transformed_scoped["slide_5_content"]["shapes"]["sh_ct_title"]["0"][
              "Text"
          ],
      )

  def test_ucs_material_catalog_strict_zod_schemas_and_session_isolation(self):
    """Verifies that all 8 A2UI v0.9 cards strictly obey UcsMaterialCatalog .strict() Zod schemas and brand-new sessions never leak Netflix/Mercedes state or skip the Slide Search input card."""
    import json
    import enterprise_agent as ea
    from ge import a2ui

    # 1. Exact allowed keys per UcsMaterialCatalog (ucs_widget/components/a2ui/v0_9/material/schema/*.ts .strict() Zod schemas)
    allowed_keys_by_component = {
        "MaterialCard": {
            "id",
            "component",
            "weight",
            "style",
            "children",
            "appearance",
            "align",
            "ariaLabel",
            "ariaLabelledby",
        },
        "MaterialColumn": {
            "id",
            "component",
            "weight",
            "children",
            "justify",
            "align",
            "style",
        },
        "MaterialRow": {
            "id",
            "component",
            "weight",
            "children",
            "justify",
            "align",
            "style",
        },
        "MaterialText": {
            "id",
            "component",
            "weight",
            "text",
            "usageHint",
            "style",
        },
        "MaterialInput": {
            "id",
            "component",
            "weight",
            "label",
            "placeholder",
            "value",
            "ariaDescribedby",
            "ariaLabelledby",
            "ariaLabel",
            "disabled",
            "name",
            "readonly",
            "type",
            "style",
            "validationRegexp",
            "checks",
        },
        "MaterialSelect": {
            "id",
            "component",
            "weight",
            "label",
            "placeholder",
            "value",
            "ariaLabel",
            "ariaLabelledby",
            "ariaDescribedby",
            "disabled",
            "options",
            "style",
            "checks",
        },
        "MaterialButton": {
            "id",
            "component",
            "weight",
            "label",
            "leadingIcon",
            "trailingIcon",
            "color",
            "disabled",
            "variant",
            "action",
            "style",
            "ariaLabel",
            "ariaLabelledby",
            "ariaDescribedby",
            "tooltip",
            "loadingOnClick",
        },
        "MaterialDivider": {
            "id",
            "component",
            "weight",
            "inset",
            "vertical",
            "style",
        },
        "MaterialIcon": {
            "id",
            "component",
            "weight",
            "icon",
            "color",
            "style",
        },
        "Card": {"id", "component", "weight", "child", "accessibility"},
        "Column": {
            "id",
            "component",
            "weight",
            "children",
            "justify",
            "align",
            "accessibility",
        },
        "Row": {
            "id",
            "component",
            "weight",
            "children",
            "justify",
            "align",
            "accessibility",
        },
        "Text": {
            "id",
            "component",
            "weight",
            "text",
            "variant",
            "accessibility",
        },
        "TextField": {
            "id",
            "component",
            "weight",
            "label",
            "value",
            "variant",
            "validationRegexp",
            "checks",
            "accessibility",
        },
        "ChoicePicker": {
            "id",
            "component",
            "weight",
            "label",
            "variant",
            "options",
            "value",
            "displayStyle",
            "filterable",
            "checks",
            "accessibility",
        },
        "Modal": {
            "id",
            "component",
            "weight",
            "trigger",
            "content",
            "accessibility",
        },
        "Divider": {"id", "component", "weight", "axis", "accessibility"},
        "Button": {
            "id",
            "component",
            "weight",
            "child",
            "action",
            "variant",
            "checks",
            "accessibility",
        },
        "Image": {
            "id",
            "component",
            "weight",
            "url",
            "description",
            "fit",
            "variant",
            "accessibility",
        },
    }
    valid_button_variants = {"basic", "raised", "stroked", "flat"}
    valid_text_usage_hints = {
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "caption",
        "body",
        "subtitle1",
        "subtitle2",
        "body1",
        "body2",
    }

    card_payload_sets = [
        ("launcher", a2ui.create_a2ui_launcher_messages()),
        ("intake", a2ui.create_a2ui_intake_messages()),
        (
            "outline",
            a2ui.create_a2ui_outline_messages(
                customer_name="Acme",
                agenda_sections=[
                    {"title": "Sec 1", "subtopics": ["A"], "slide_count": 1}
                ],
            ),
        ),
        (
            "search_input",
            a2ui.create_a2ui_search_messages(search_query="", results=[]),
        ),
        (
            "search_results",
            a2ui.create_a2ui_search_messages(
                search_query="Retail",
                results=[{
                    "title": "Target Case Study",
                    "slide_id": "s1",
                    "deck_id": "d1",
                    "slide_job": "Proof_Points",
                    "customer": "Target",
                    "industry": "Retail",
                    "view_url": (
                        "https://docs.google.com/presentation/d/d1/edit"
                    ),
                }],
            ),
        ),
        ("generate_slide", a2ui.create_a2ui_generate_slide_messages()),
        ("transform_text_input", a2ui.create_a2ui_transform_text_messages()),
        (
            "transform_results",
            a2ui.create_a2ui_transform_messages(
                presentation_id="1abcDeckId",
                customer_name="Target",
                criteria="Executive C-Suite tone",
                slides_modified=5,
            ),
        ),
        ("translate", a2ui.create_a2ui_translate_messages()),
        (
            "nano_banana_gen",
            a2ui.create_a2ui_nano_banana_messages(mode="generate"),
        ),
        (
            "nano_banana_trans",
            a2ui.create_a2ui_nano_banana_messages(
                mode="transform",
                generated_image_url=(
                    "https://storage.googleapis.com/demo/img.png"
                ),
            ),
        ),
    ]

    for card_name, msgs in card_payload_sets:
      self.assertEqual(len(msgs), 3, f"{card_name} must emit 3 v0.9 messages")
      self.assertIn("createSurface", msgs[0])
      comp_msg = next(m for m in msgs if "updateComponents" in m)
      for comp in comp_msg["updateComponents"]["components"]:
        c_type = comp["component"]
        self.assertIn(
            c_type,
            allowed_keys_by_component,
            f"{card_name}: unsupported component type {c_type}",
        )
        unrecognized = set(comp.keys()) - allowed_keys_by_component[c_type]
        if (
            card_name == "intake"
            and comp["id"] in ("sales_play_select", "audience_select")
            and comp.get("multiple") is True
        ):
          # Documented exception: A2UI-GE multi-select Sales Play / Audience
          # (user-confirmed to render in GE); single selects must not carry it.
          unrecognized.discard("multiple")
        self.assertEqual(
            unrecognized,
            set(),
            f"{card_name} component {comp['id']} ({c_type}) has unrecognized"
            f" keys: {unrecognized}",
        )
        if c_type == "MaterialCard":
          self.assertIn(
              "children",
              comp,
              f"{card_name} MaterialCard {comp['id']} must have 'children'",
          )
          self.assertIsInstance(comp["children"], list)
          self.assertNotIn("child", comp)
        if c_type == "MaterialIcon":
          self.assertIn(
              "icon",
              comp,
              f"{card_name} MaterialIcon {comp['id']} must have 'icon'",
          )
          self.assertNotIn("name", comp)
        if c_type == "MaterialButton" and "variant" in comp:
          self.assertIn(comp["variant"], valid_button_variants)
        if c_type == "MaterialText" and "usageHint" in comp:
          self.assertIn(comp["usageHint"], valid_text_usage_hints)

    # 2. Cross-session isolation: brand-new session must NOT pull Netflix/Mercedes from _LATEST_OUTLINE_CACHE
    ea._LATEST_OUTLINE_CACHE["_latest_deck_id_"] = (
        "1NetflixDeckIdFromOtherSession99999"
    )
    ea._LATEST_OUTLINE_CACHE["_latest_customer_name_"] = "Netflix"
    fresh_ctx = type("FreshCtx", (), {"state": {}})()
    pres_id, deck_url, cust_name = ea._resolve_active_deck_from_state_or_cache(
        "", fresh_ctx
    )
    self.assertEqual(pres_id, "")
    self.assertEqual(deck_url, "")
    self.assertEqual(cust_name, "")

    # 3. A stale last_target_card='search_slide' (left over from a launcher
    # fast path) must NOT turn a real search into a form re-render: the search
    # runs and emits exactly one results card, and the stale flag is cleared.
    fresh_ctx.state["last_target_card"] = "search_slide"
    from unittest.mock import patch as _patch  # pylint: disable=g-import-not-at-top

    with (
        _patch(
            "agents.workflows.customer_reference_retriever.NewLibraryCustomerReferenceRetriever.search_slides",
            return_value=[],
        ),
        _patch(
            "agents.sidebar_agent.SidebarAgent.search",
            return_value={"search_results": []},
        ),
        _patch(
            "pitchgen_utils.slide_thumbnail_util.resolve_thumbnail_candidate_tokens",
            return_value=[],
        ),
    ):
      ea.enterprise_search_slides_skill(
          search_query="Customer References", tool_context=fresh_ctx
      )
    self.assertEqual(fresh_ctx.state.get("last_target_card"), "")
    stashed_json = json.dumps(
        fresh_ctx.state.get("a2ui_payloads_to_inject", [])
    )
    self.assertNotIn("pitchgen-slide-search", stashed_json)
    self.assertNotIn("search_slides", stashed_json)
    self.assertIn("pitchgen-search-results-", stashed_json)

    # The dedicated form skill still renders the empty input form card.
    form_ctx = type("FormCtx", (), {"state": {}})()
    res_form = ea.enterprise_search_slides_form_skill(tool_context=form_ctx)
    self.assertIn("pitchgen-slide-search", res_form)
    stashed = form_ctx.state.get("a2ui_payloads_to_inject", [])
    self.assertEqual(len(stashed), 3)
    self.assertEqual(
        stashed[0]["createSurface"]["surfaceId"], "pitchgen-slide-search"
    )
    self.assertEqual(stashed[1]["updateDataModel"]["value"]["search_query"], "")

    # 4. Verify all 8 launcher form skills open without TypeError and emit distinct surfaceIds
    all_cards_ctx = type("AllCardsCtx", (), {"state": {}})()
    form_skill_calls = [
        (
            "pitchgen-intake",
            lambda: ea.enterprise_intake_form_skill(tool_context=all_cards_ctx),
        ),
        (
            "pitchgen-slide-search",
            lambda: ea.enterprise_search_slides_form_skill(
                tool_context=all_cards_ctx
            ),
        ),
        (
            "pitchgen-generate-slide",
            lambda: ea.enterprise_generate_slide_form_skill(
                tool_context=all_cards_ctx
            ),
        ),
        (
            "pitchgen-transform-slide",
            lambda: ea.enterprise_transform_slide_form_skill(
                tool_context=all_cards_ctx
            ),
        ),
        (
            "pitchgen-transform-text",
            lambda: ea.enterprise_transform_text_form_skill(
                tool_context=all_cards_ctx
            ),
        ),
        (
            "pitchgen-translate",
            lambda: ea.enterprise_translate_form_skill(
                tool_context=all_cards_ctx
            ),
        ),
        (
            "pitchgen-generate-nanobanana",
            lambda: ea.enterprise_nano_banana_form_skill(
                mode="generate", tool_context=all_cards_ctx
            ),
        ),
        (
            "pitchgen-transform-nanobanana",
            lambda: ea.enterprise_nano_banana_form_skill(
                mode="transform", tool_context=all_cards_ctx
            ),
        ),
    ]
    seen_surfaces = set()
    for expected_surface, fn in form_skill_calls:
      all_cards_ctx.state["a2ui_payloads_to_inject"] = []
      out = fn()
      self.assertIn(expected_surface, out)
      injected = all_cards_ctx.state.get("a2ui_payloads_to_inject", [])
      self.assertEqual(
          len(injected), 3, f"Expected 3 messages for {expected_surface}"
      )
      actual_surface = injected[0]["createSurface"]["surfaceId"]
      self.assertEqual(actual_surface, expected_surface)
      self.assertNotIn(actual_surface, seen_surfaces)
      seen_surfaces.add(actual_surface)

    # Re-opening a form skill in the same session generates a unique surfaceId so ucs_widget renders it again
    all_cards_ctx.state["a2ui_payloads_to_inject"] = []
    ea.enterprise_translate_form_skill(tool_context=all_cards_ctx)
    reopened_surface = all_cards_ctx.state["a2ui_payloads_to_inject"][0][
        "createSurface"
    ]["surfaceId"]
    self.assertTrue(reopened_surface.startswith("pitchgen-translate-"))
    self.assertNotEqual(reopened_surface, "pitchgen-translate")

    # 5. Verify Generate Deck Intake defaults (A2UI-GE layout, qa-p2 backend):
    # deck_strategy='smart_hybrid', deck_length='Standard (8-12 slides)',
    # sales_play/audience=[] (multi-select), industry/stage/archetype=''.
    intake_msgs = a2ui.create_a2ui_intake_messages()
    intake_dm = intake_msgs[1]["updateDataModel"]["value"]
    self.assertEqual(intake_dm["deck_strategy"], "smart_hybrid")
    self.assertEqual(intake_dm["deck_length"], "Standard (8-12 slides)")
    self.assertEqual(intake_dm["sales_play"], [])
    self.assertEqual(intake_dm["audience"], [])
    for field_key in ("industry", "sales_stage", "presentation_archetype"):
      self.assertEqual(
          intake_dm[field_key],
          "",
          f"Intake default for {field_key} must be empty string (Auto-Detect)",
      )
    intake_comps = {
        c["id"]: c for c in intake_msgs[2]["updateComponents"]["components"]
    }
    self.assertEqual(
        intake_comps["deck_strategy_select"]["options"][0]["value"],
        "smart_hybrid",
    )
    self.assertTrue(intake_comps["sales_play_select"]["multiple"])
    self.assertTrue(intake_comps["audience_select"]["multiple"])
    self.assertEqual(
        intake_comps["industry_select"]["options"][0],
        {"label": "Auto-detect industry", "value": ""},
    )
    self.assertEqual(
        intake_comps["sales_stage_select"]["options"][0],
        {"label": "Auto-detect stage", "value": ""},
    )
    self.assertEqual(
        intake_comps["archetype_select"]["options"][0],
        {"label": "Auto-detect archetype", "value": ""},
    )
    self.assertEqual(
        [o["value"] for o in intake_comps["deck_length_select"]["options"]],
        [
            "Brief (4-6 slides)",
            "Standard (8-12 slides)",
            "Comprehensive (15-20 slides)",
        ],
    )

  def test_slide_selection_scoping_for_translation_and_transformation(self):
    """Verifies that selecting specific slide indices scopes translation and transformation to those slides only and does not apply across the full deck."""
    import json
    from unittest import mock
    from google.genai import types as genai_types
    import src.enterprise_agent as ea_mod
    from src.ge import a2ui_transform_text

    # 1. A2UI v0.9 Translate Action in enterprise_before_model_callback preserves target_slide_indices
    trans_dp = a2ui.format_a2ui_datapart({
        "action": {
            "name": "translate_deck",
            "surfaceId": "pitchgen-translate",
            "sourceComponentId": "btn-translate-deck",
            "context": {
                "presentation_id": (
                    "https://docs.google.com/presentation/d/SAMPLE_TEST_PRESENTATION_ID_000000000003/edit"
                ),
                "target_language": "Spanish",
                "target_slide_indices": "3",
                "customer_name": "Spotify",
            },
        }
    })
    trans_req = type(
        "MockReq",
        (),
        {
            "contents": [
                genai_types.Content(
                    role="user", parts=[genai_types.Part(text=trans_dp)]
                )
            ]
        },
    )()
    trans_ctx = type("MockCtx", (), {"state": {}})()
    self.assertIsNone(
        ea_mod.enterprise_before_model_callback(trans_ctx, trans_req)
    )
    prompt_text = trans_req.contents[0].parts[0].text
    self.assertIn("enterprise_translate_deck_skill", prompt_text)
    self.assertIn("SAMPLE_TEST_PRESENTATION_ID_000000000003", prompt_text)
    self.assertIn("Spanish", prompt_text)
    self.assertIn("target_slide_indices='3'", prompt_text)
    self.assertEqual(
        trans_ctx.state.get("last_translate_card_ctx", {}).get(
            "target_slide_indices"
        ),
        "3",
    )

    # 2. PitchGenSkills.enterprise_translate_deck_skill passes target_slide_indices to _transform_presentation_slides_via_rest_api
    valid_pres_id = "SAMPLE_TEST_PRESENTATION_ID_000000000003"
    mock_tool_ctx = type(
        "MockCtx",
        (),
        {
            "state": {
                "presentation_id": valid_pres_id,
                "customer_name": "Spotify",
            }
        },
    )()
    with mock.patch.object(
        ea_mod.PitchGenSkills,
        "_transform_presentation_slides_via_rest_api",
        return_value={"status": "success", "slides_modified": 1},
    ) as mock_rest:
      with mock.patch(
          "src.agent._build_apps_script_candidate_tokens",
          return_value=[("live", "fake_token")],
      ):
        res_json = ea_mod.PitchGenSkills.enterprise_translate_deck_skill(
            presentation_url_or_id=valid_pres_id,
            target_language="Spanish",
            target_slide_indices="3",
            tool_context=mock_tool_ctx,
        )
        res_data = json.loads(res_json)
        self.assertEqual(res_data.get("status"), "success")
        self.assertEqual(res_data.get("target_slide_indices"), "3")
        self.assertEqual(res_data.get("slides_modified"), 1)
        mock_rest.assert_called_once()
        call_kwargs = mock_rest.call_args[1]
        self.assertEqual(call_kwargs.get("target_slide_indices"), "3")
        self.assertIn(
            "slide(s) 3", call_kwargs.get("customization_criteria", "")
        )

    # 3. ea_mod.enterprise_translate_deck_skill forwards target_slide_indices
    with mock.patch.object(
        ea_mod.PitchGenSkills,
        "enterprise_translate_deck_skill",
        return_value=json.dumps({
            "status": "success",
            "presentation_id": valid_pres_id,
            "deck_url": (
                f"https://docs.google.com/presentation/d/{valid_pres_id}/edit"
            ),
            "slides_modified": 1,
            "target_slide_indices": "3",
        }),
    ) as mock_skill:
      ea_res = ea_mod.enterprise_translate_deck_skill(
          presentation_url_or_id=valid_pres_id,
          target_language="Spanish",
          target_slide_indices="3",
          tool_context=mock_tool_ctx,
      )
      mock_skill.assert_called_once()
      self.assertEqual(mock_skill.call_args[1].get("target_slide_indices"), "3")

    # 4. A2UI v0.9 Text Transform Action overrides full_deck_scope when target_slide_indices has specific numbers
    trans_text_dp = a2ui.format_a2ui_datapart({
        "action": {
            "name": "transform_slide_text",
            "surfaceId": "pitchgen-transform-text",
            "sourceComponentId": "btn_transform_submit",
            "context": {
                "presentation_url_or_id": "pres_12345",
                "custom_instructions": "Make executive for CIO",
                "customer_name": "Spotify",
                "full_deck_scope": ["full_deck"],
                "target_slide_indices": "3",
            },
        }
    })
    trans_text_req = type(
        "MockReq",
        (),
        {
            "contents": [
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=trans_text_dp)],
                )
            ]
        },
    )()
    trans_text_ctx = type("MockCtx", (), {"state": {}})()
    self.assertIsNone(
        ea_mod.enterprise_before_model_callback(trans_text_ctx, trans_text_req)
    )
    prompt_text_2 = trans_text_req.contents[0].parts[0].text
    self.assertIn("target_slide_indices='3'", prompt_text_2)
    self.assertIn("full_deck_scope=False", prompt_text_2)

    # 5. create_a2ui_v09_transform_text_messages data model defaults full_deck_scope only when target_slide_indices is blank
    msgs_default = a2ui_transform_text.create_a2ui_v09_transform_text_messages(
        presentation_url_or_id="pres_12345",
        target_slide_indices="",
    )
    dm_default = msgs_default[1]["updateDataModel"]["value"]
    self.assertEqual(dm_default.get("full_deck_scope"), ["full_deck"])
    self.assertEqual(dm_default.get("target_slide_indices"), "")

    msgs_specific = a2ui_transform_text.create_a2ui_v09_transform_text_messages(
        presentation_url_or_id="pres_12345",
        target_slide_indices="3",
    )
    dm_specific = msgs_specific[1]["updateDataModel"]["value"]
    self.assertEqual(dm_specific.get("full_deck_scope"), [])
    self.assertEqual(dm_specific.get("target_slide_indices"), "3")

  def test_slide_search_a2ui_title_deck_link_full_summary_and_chat_dedup(self):
    """Verifies slide search A2UI cards display slide title, linked deck title, full description, and deduplicate chat lists."""
    from google.genai import types as genai_types
    from src import enterprise_agent as ea_mod
    from src.ge import a2ui_search

    full_cadent_summary = (
        "The slide showcases a customer success story for Cadent, detailing"
        " how they used Gemini Enterprise and an Agent Platform to improve"
        " advertising campaign resolution time by 200%, achieve a 99% data"
        " match rate, and save 3,000 employee hours annually across global"
        " media operations."
    )
    raw_cadent_item = {
        "slide_id": "g3e66f86_0_12",
        "deck_id": "SAMPLE_TEST_PRESENTATION_ID_000000000018",
        "title": "Why Google Cloud for Sports [sports_ebc_pitch] (pt)",
        "customer": "Time",
        "industry": ["Media & Entertainment"],
        "slide_job": "Proof_Points",
        "summary": full_cadent_summary,
        "view_url": (
            "https://docs.google.com/presentation/d/SAMPLE_TEST_PRESENTATION_ID_000000000018/edit#slide=id.g3e66f86_0_12"
        ),
    }

    msgs = a2ui_search.create_a2ui_v09_search_messages(
        search_query="Customer References",
        results=[raw_cadent_item],
        target_presentation_id="active_deck_999",
    )
    comps = {c["id"]: c for c in msgs[2]["updateComponents"]["components"]}

    # 1. Card title must be the derived slide title (with Cadent), NOT the deck title
    card_title = comps["res-title-1"]["text"]
    self.assertIn("Cadent", card_title)
    self.assertNotIn("Why Google Cloud for Sports", card_title)
    self.assertNotIn("[sports_ebc_pitch]", card_title)

    # 2. Metadata must show Cadent (not false-positive 'Time'), unpacked 'Media & Entertainment',
    # formatted 'Proof Points', and the source deck title linked to the slide URL
    card_meta = comps["res-meta-1"]["text"]
    self.assertIn("Cadent • Media & Entertainment • Proof Points", card_meta)
    self.assertNotIn("['Media & Entertainment']", card_meta)
    self.assertNotIn("Time •", card_meta)
    self.assertIn(
        "Source: [Why Google Cloud for Sports (sports_ebc_pitch)"
        " (pt)](https://docs.google.com/presentation/d/SAMPLE_TEST_PRESENTATION_ID_000000000018/edit#slide=id.g3e66f86_0_12)",
        card_meta,
    )

    # 3. Description must NOT be truncated at 240 chars and must enforce Enterprise-Brand-Unification
    card_desc = comps["res-desc-1"]["text"]
    self.assertGreater(len(card_desc), 240)
    self.assertIn(
        "save 3,000 employee hours annually across global media operations.",
        card_desc,
    )
    self.assertIn("Gemini Enterprise to improve", card_desc)
    self.assertNotIn("Agent Platform", card_desc)

    # 4. enterprise_after_model_callback strips duplicate numbered slide lists from chat when pitchgen-slide-search has results
    cb_ctx = type(
        "MockCbCtx",
        (),
        {"state": {"a2ui_payloads_to_inject": msgs}},
    )()
    verbose_chat = (
        "Here are the top verified customer references matching your"
        " search:\n\n1. **Why Google Cloud for Sports [sports_ebc_pitch]"
        " (pt)**\n   * **Industry:** Media & Entertainment\n   * **Link:**"
        " [View"
        " Slide](https://docs.google.com/presentation/d/SAMPLE_TEST_PRESENTATION_ID_000000000018/edit)\n2."
        " **Wayfair — Catalog AI**\n   * **Industry:** Retail\n"
    )
    llm_resp = genai_types.GenerateContentResponse(
        candidates=[
            genai_types.Candidate(
                content=genai_types.Content(
                    role="model",
                    parts=[genai_types.Part(text=verbose_chat)],
                )
            )
        ]
    )
    # Attach content directly as ADK LlmResponse does
    mock_llm_resp = type(
        "MockLlmResp",
        (),
        {
            "content": llm_resp.candidates[0].content,
            "custom_metadata": {},
            "model_copy": lambda self_obj, update: type(
                "MockLlmRespCopy", (), update
            )(),
        },
    )()
    updated = ea_mod.enterprise_after_model_callback(cb_ctx, mock_llm_resp)
    text_parts = [
        p.text
        for p in updated.content.parts
        if getattr(p, "text", None) and not getattr(p, "thought", False)
    ]
    self.assertEqual(len(text_parts), 1)
    self.assertNotIn("1. **Why Google Cloud for Sports", text_parts[0])
    self.assertNotIn("2. **Wayfair", text_parts[0])
    self.assertIn("Slide Search", text_parts[0])

  def test_enterprise_before_model_callback_greeting_fast_path(self):
    """Greeting turns ('hi', 'hello', 'hey', 'start', 'menu', 'launcher', 'what can you do', empty prompt) fast-path Launcher Hub via LlmResponse without LLM call."""
    from google.genai import types as genai_types
    import src.enterprise_agent as ea_mod

    greetings = [
        "hi",
        "Hi!",
        "hello",
        "Hello.",
        "hey there",
        "hello pitchgen",
        "start",
        "menu",
        "launcher",
        "what can you do?",
        "",
        "   ",
    ]
    for g in greetings:
      req = type(
          "MockReq",
          (),
          {
              "contents": [
                  genai_types.Content(
                      role="user",
                      parts=[genai_types.Part(text=g)],
                  )
              ]
          },
      )()
      ctx = type("MockCtx", (), {"state": {}})()
      resp = ea_mod.enterprise_before_model_callback(ctx, req)
      self.assertIsNotNone(
          resp, f"Expected LlmResponse fast-path for greeting '{g}'"
      )
      self.assertTrue(hasattr(resp, "content"))
      self.assertTrue(getattr(resp, "custom_metadata", {}).get("a2a:response"))
      all_text = " ".join(
          getattr(p, "text", "") or "" for p in resp.content.parts
      )
      self.assertIn("Welcome to **PitchGen**", all_text)
      # Check A2UI data part
      inline_data_parts = [
          p
          for p in resp.content.parts
          if getattr(p, "inline_data", None) is not None
      ]
      self.assertTrue(len(inline_data_parts) >= 1)
      blob_str = inline_data_parts[0].inline_data.data.decode("utf-8")
      self.assertIn("pitchgen-launcher", blob_str)

  def test_enterprise_before_model_callback_substantive_prompt_passthrough(
      self,
  ):
    """Prompts with substantive customer names or pitch tasks pass through to the LLM (returning None)."""
    from google.genai import types as genai_types
    import src.enterprise_agent as ea_mod

    substantive_prompts = [
        "Hi, create a pitch deck for Nike",
        "Hello, search for healthcare customer references",
        "Hey, transform slide 3 to make it concise",
        "Synthesize an architecture diagram for Spanner",
        "Translate active deck to French",
    ]
    for p_text in substantive_prompts:
      req = type(
          "MockReq",
          (),
          {
              "contents": [
                  genai_types.Content(
                      role="user",
                      parts=[genai_types.Part(text=p_text)],
                  )
              ]
          },
      )()
      ctx = type("MockCtx", (), {"state": {}})()
      resp = ea_mod.enterprise_before_model_callback(ctx, req)
      self.assertIsNone(
          resp, f"Substantive prompt '{p_text}' should pass through to LLM"
      )

  def test_enterprise_before_model_callback_launcher_card_clicks_fast_path(
      self,
  ):
    """Clicking any of the 8 feature cards on the launcher returns its interactive card via LlmResponse instantly."""
    from google.genai import types as genai_types
    import src.enterprise_agent as ea_mod

    target_cards_to_expected_surfaces = {
        "generate_pitch": "pitchgen-intake",
        "intake": "pitchgen-intake",
        "search_slide": "pitchgen-slide-search",
        "search": "pitchgen-slide-search",
        "generate_slide": "pitchgen-generate-slide",
        "transform_slide": "pitchgen-transform-slide",
        "transform_text": "pitchgen-transform-text",
        "transform": "pitchgen-transform-text",
        "translate": "pitchgen-translate",
        "generate_nanobanana": "pitchgen-generate-nanobanana",
        "diagram": "pitchgen-generate-nanobanana",
        "transform_nanobanana": "pitchgen-transform-nanobanana",
    }

    for tc, expected_surf in target_cards_to_expected_surfaces.items():
      action_dp = a2ui.format_a2ui_datapart({
          "action": {
              "name": "launch_feature_card",
              "target_card": tc,
              "surfaceId": "pitchgen-launcher",
              "sourceComponentId": f"card_{tc}",
              "context": {},
          }
      })
      req = type(
          "MockReq",
          (),
          {
              "contents": [
                  genai_types.Content(
                      role="user",
                      parts=[genai_types.Part(text=action_dp)],
                  )
              ]
          },
      )()
      ctx = type(
          "MockCtx",
          (),
          {
              "state": {
                  "presentation_id": "deck_12345",
                  "customer_name": "Alphabet",
              }
          },
      )()
      resp = ea_mod.enterprise_before_model_callback(ctx, req)
      self.assertIsNotNone(
          resp, f"Expected LlmResponse fast-path for target_card '{tc}'"
      )
      self.assertTrue(getattr(resp, "custom_metadata", {}).get("a2a:response"))
      inline_data_parts = [
          p
          for p in resp.content.parts
          if getattr(p, "inline_data", None) is not None
      ]
      self.assertTrue(len(inline_data_parts) >= 1)
      blob_str = inline_data_parts[0].inline_data.data.decode("utf-8")
      self.assertIn(expected_surf, blob_str)

  def test_intake_sales_plays_deduplicated_ordered_grouped_and_defaults(self):
    """Verifies sales plays have no duplicates, are grouped by Practice Area and alphabetically ordered within each Practice Area, and intake defaults match requirements."""
    from src.ge import a2ui_intake
    import src.enterprise_agent as ea_mod

    # 1. No duplicates in DEFAULT_SALES_PLAYS
    self.assertEqual(
        len(a2ui_intake.DEFAULT_SALES_PLAYS),
        len(set(a2ui_intake.DEFAULT_SALES_PLAYS)),
        "DEFAULT_SALES_PLAYS must not contain duplicate entries",
    )
    self.assertNotIn(
        "Scale AI Apps & Agents",
        a2ui_intake.DEFAULT_SALES_PLAYS,
        "Legacy duplicate 'Scale AI Apps & Agents' must be removed in favor of 'Scale AI Apps and Agents'",
    )
    self.assertIn(
        "Scale AI Apps and Agents",
        a2ui_intake.DEFAULT_SALES_PLAYS,
    )

    # 2. Practice Area groupings and alphabetical ordering within each Practice Area
    expected_practice_areas = [
        "AI",
        "Agentic Workplace Transformation",
        "Data",
        "Infrastructure",
        "Security",
    ]
    self.assertEqual(
        list(a2ui_intake.SALES_PLAYS_BY_PRACTICE_AREA.keys()),
        expected_practice_areas,
    )
    for pa, plays in a2ui_intake.SALES_PLAYS_BY_PRACTICE_AREA.items():
      self.assertEqual(
          plays,
          sorted(plays),
          f"Sales plays in Practice Area '{pa}' must be alphabetically ordered",
      )

    # 3. v0.9 intake sales play values are canonical names in practice-area
    # order; labels carry a "Practice Area — " prefix; no header rows.
    msgs = a2ui_intake.create_a2ui_v09_intake_messages()
    dm = msgs[1]["updateDataModel"]["value"]
    self.assertEqual(dm["deck_length"], "Standard (8-12 slides)")
    self.assertEqual(dm["deck_strategy"], "smart_hybrid")
    self.assertEqual(dm["industry"], "")
    self.assertEqual(dm["sales_play"], [])

    comps = {c["id"]: c for c in msgs[2]["updateComponents"]["components"]}
    sp_options = comps["sales_play_select"]["options"]
    self.assertTrue(comps["sales_play_select"]["multiple"])
    self.assertEqual(
        [o["value"] for o in sp_options], a2ui_intake.DEFAULT_SALES_PLAYS
    )
    for opt in sp_options:
      self.assertTrue(opt["value"])
      self.assertTrue(opt["label"].endswith(" — " + opt["value"]))
      self.assertNotIn(" — ", opt["value"])
    self.assertNotIn(
        "AI", [o["value"] for o in sp_options], "No practice-area header rows"
    )

    # 4. Normalization of legacy & Practice-Area-prefixed sales play values
    self.assertEqual(
        a2ui_intake.normalize_sales_play_value("Scale AI Apps & Agents"),
        "Scale AI Apps and Agents",
    )
    self.assertEqual(
        a2ui_intake.normalize_sales_play_value(
            "AI — Scale AI Apps and Agents"
        ),
        "Scale AI Apps and Agents",
    )
    self.assertEqual(
        ea_mod._clean_intake_select_val("✨ Auto-Detect Industry Vertical"),
        "",
    )
    self.assertEqual(
        ea_mod._clean_intake_select_val("Data — Analytics & AI Platform"),
        "Analytics & AI Platform",
    )

  def test_consolidated_5_card_suite_transform_scope_and_nanobanana_studio(
      self,
  ):
    """Verifies Card 3 transform_scope_mode (text_only, images_only, both) and Card 4 NanoBanana Visual Studio (no Visual Architecture Style dropdown, CTA 'Run NanoBanana')."""
    import json
    from unittest import mock
    import src.enterprise_agent as ea_mod
    from src.ge import a2ui_nano_banana
    from src.ge import a2ui_transform_text

    # 1. Card 3 (Transform Slide / Deck) includes transform_scope_mode_select with 3 options
    tf_msgs = a2ui_transform_text.create_a2ui_v09_transform_text_messages(
        presentation_url_or_id="1ActiveDeckId",
        transform_scope_mode="images_only",
    )
    tf_dm = tf_msgs[1]["updateDataModel"]["value"]
    self.assertEqual(tf_dm["transform_scope_mode"], "images_only")
    tf_comps = {
        c["id"]: c for c in tf_msgs[2]["updateComponents"]["components"]
    }
    self.assertIn("transform_scope_mode_select", tf_comps)
    scope_opts = [
        opt["value"]
        for opt in tf_comps["transform_scope_mode_select"]["options"]
    ]
    self.assertEqual(
        scope_opts, ["text_only", "images_only", "gifs_only", "both"]
    )
    self.assertEqual(
        tf_comps["btn_transform_submit"]["label"], "🪄 Transform Slide / Deck"
    )
    self.assertEqual(
        tf_comps["btn_transform_submit"]["action"]["event"]["context"][
            "transform_scope_mode"
        ],
        {"path": "/transform_scope_mode"},
    )

    # 2. Card 4 (Nano Banana Studio) removes select-style, sets title to 'Nano Banana Studio', and configures mode/model options
    for mode_val in ("generate", "transform"):
      nb_msgs = a2ui_nano_banana.create_a2ui_v09_nano_banana_messages(
          presentation_id="1ActiveDeckId",
          mode=mode_val,
      )
      nb_comps = {
          c["id"]: c for c in nb_msgs[2]["updateComponents"]["components"]
      }
      self.assertNotIn(
          "select-style",
          nb_comps,
          "Visual Architecture Style dropdown must be removed from Card 4",
      )
      self.assertEqual(nb_comps["header-txt"]["text"], "Nano Banana Studio")
      self.assertIn("select-mode", nb_comps)
      self.assertEqual(
          nb_comps["select-mode"]["options"],
          [
              {"label": "Generate New Visual", "value": "generate"},
              {"label": "Restyle Existing Slide", "value": "transform"},
          ],
      )
      self.assertIn("select-model", nb_comps)
      self.assertEqual(
          nb_comps["select-model"]["options"],
          [
              {"label": "Nano Banana Pro", "value": "nano_banana_pro"},
              {"label": "Nano Banana", "value": "nano_banana"},
              {"label": "Nano Banana 2.1", "value": "gemini-nano-banana-2.1"},
          ],
      )
      self.assertEqual(
          nb_comps["btn-generate-visual"]["label"], "Run NanoBanana"
      )
      nb_legacy = a2ui_nano_banana.create_nano_banana_card(
          presentation_id="1ActiveDeckId",
          mode=mode_val,
      )
      self.assertEqual(nb_legacy["title"], "Nano Banana Studio")
      legacy_field_ids = [f["id"] for f in nb_legacy["sections"][1]["fields"]]
      self.assertNotIn("visual_style", legacy_field_ids)
      self.assertIn("nano_banana_model", legacy_field_ids)
      self.assertEqual(
          nb_legacy["sections"][2]["buttons"][0]["label"], "Run NanoBanana"
      )

    # 3. enterprise_transform_slide_text_skill with transform_scope_mode='images_only' calls enterprise_generate_visuals_skill with in_place_only=True
    mock_ctx = type(
        "MockCtx",
        (),
        {
            "state": {
                "presentation_id": "1ActiveDeckId",
                "customer_name": "Nike",
            }
        },
    )()
    with (
        mock.patch.object(
            ea_mod.PitchGenSkills,
            "enterprise_transform_slide_text_skill",
        ) as mock_text_tf,
        mock.patch.object(
            ea_mod.PitchGenSkills,
            "enterprise_generate_visuals_skill",
            return_value=json.dumps({
                "status": "success",
                "presentation_id": "1ActiveDeckId",
                "deck_url": (
                    "https://docs.google.com/presentation/d/1ActiveDeckId/edit"
                ),
                "replaced_image_count": 2,
                "mode": "transform",
            }),
        ) as mock_vis_tf,
    ):
      res_img_only = ea_mod.enterprise_transform_slide_text_skill(
          presentation_url_or_id="1ActiveDeckId",
          customization_criteria=(
              "Restyle embedded charts to Nike brand palette"
          ),
          target_slide_indices="2, 4",
          customer_name="Nike",
          transform_scope_mode="images_only",
          tool_context=mock_ctx,
      )
      mock_text_tf.assert_not_called()
      mock_vis_tf.assert_called_once()
      self.assertTrue(mock_vis_tf.call_args.kwargs.get("in_place_only"))
      self.assertEqual(
          mock_vis_tf.call_args.kwargs.get("target_slide_indices"), "2, 4"
      )
      parsed_img_only = json.loads(res_img_only)
      self.assertEqual(
          parsed_img_only.get("transform_scope_mode"), "images_only"
      )
      self.assertEqual(parsed_img_only.get("replaced_image_count"), 2)

    # 4. enterprise_transform_slide_text_skill with transform_scope_mode='both' runs both text and in-place image transformation
    with (
        mock.patch.object(
            ea_mod.PitchGenSkills,
            "enterprise_transform_slide_text_skill",
            return_value=json.dumps({
                "status": "success",
                "presentation_id": "1ActiveDeckId",
                "deck_url": (
                    "https://docs.google.com/presentation/d/1ActiveDeckId/edit"
                ),
                "slides_modified": 2,
            }),
        ) as mock_text_both,
        mock.patch.object(
            ea_mod.PitchGenSkills,
            "enterprise_generate_visuals_skill",
            return_value=json.dumps({
                "status": "success",
                "presentation_id": "1ActiveDeckId",
                "replaced_image_count": 1,
            }),
        ) as mock_vis_both,
    ):
      res_both = ea_mod.enterprise_transform_slide_text_skill(
          presentation_url_or_id="1ActiveDeckId",
          customization_criteria="Update narrative and diagram for Nike",
          target_slide_indices="3",
          customer_name="Nike",
          transform_scope_mode="both",
          tool_context=mock_ctx,
      )
      mock_text_both.assert_called_once()
      mock_vis_both.assert_called_once()
      self.assertTrue(mock_vis_both.call_args.kwargs.get("in_place_only"))
      parsed_both = json.loads(res_both)
      self.assertEqual(parsed_both.get("transform_scope_mode"), "both")
      self.assertEqual(parsed_both.get("slides_modified"), 2)
      self.assertEqual(parsed_both.get("replaced_image_count"), 1)

  def test_translate_material_card_visuals_configparser_and_undo_preservation(
      self,
  ):
    """Verifies Material Translate card alignment, welcome card PitchGen banner, ConfigParser bucket lookup in enterprise_generate_visuals_skill, Slide 8 picture extraction with explicit_user_request=True, and Canvas Undo preservation."""
    import configparser
    import json
    from unittest import mock
    import src.agent as agent_mod
    import src.enterprise_agent as ea_mod
    from src.ge import a2ui_translate
    from src.pitchgen_utils import image_util

    # 1. Translate card uses A2UI_MATERIAL_CATALOG_ID and MaterialCard/MaterialSelect/MaterialInput/MaterialButton
    trans_msgs = a2ui_translate.create_a2ui_v09_translate_messages(
        presentation_url_or_id="1ColgateDeckId",
        target_language="French",
        target_slide_indices="8",
        slides_modified=1,
    )
    self.assertEqual(
        trans_msgs[0]["createSurface"]["catalogId"],
        "https://a2ui.org/specification/v0_9/material_catalog.json",
    )
    trans_comps = {
        c["id"]: c for c in trans_msgs[2]["updateComponents"]["components"]
    }
    self.assertEqual(trans_comps["root"]["component"], "MaterialCard")
    self.assertEqual(
        trans_comps["target_language_select"]["component"], "MaterialSelect"
    )
    self.assertEqual(
        trans_comps["target_slides_input"]["component"], "MaterialInput"
    )
    self.assertEqual(
        trans_comps["btn_translate_submit"]["component"], "MaterialButton"
    )
    self.assertEqual(
        trans_comps["btn_translate_submit"]["style"]["borderRadius"], "999px"
    )

    # 2. Welcome card uses native MaterialRow + MaterialIcon + MaterialText PitchGen logo banner without duplicate header_title text
    launcher_msgs = a2ui.create_a2ui_v09_launcher_messages()
    launcher_comps = {
        c["id"]: c for c in launcher_msgs[1]["updateComponents"]["components"]
    }
    self.assertIn("pitchgen_tool_logo", launcher_comps)
    self.assertEqual(
        launcher_comps["pitchgen_tool_logo"]["component"], "MaterialRow"
    )
    self.assertEqual(launcher_comps["pitchgen_logo_pitch"]["text"], "Pitch")
    self.assertEqual(launcher_comps["pitchgen_logo_gen"]["text"], "Gen")
    self.assertNotIn("header_title", launcher_comps)
    launcher_features = launcher_msgs[2]["updateDataModel"]["value"]["features"]
    self.assertEqual(
        launcher_features["generate_nanobanana"]["title"],
        "Nano Banana Studio",
    )
    self.assertEqual(
        launcher_features["generate_nanobanana"]["button_label"],
        "Open Nano Banana Studio",
    )

    # 3. extract_customizable_slide_pictures with explicit_user_request=True extracts Slide 8 picture even with crop or border proximity
    slide_8_mock = {
        "objectId": "slide_8_oid",
        "pageElements": [{
            "objectId": "img_8_colgate",
            "size": {
                "width": {"magnitude": 300, "unit": "PT"},
                "height": {"magnitude": 110, "unit": "PT"},
            },
            "transform": {
                "scaleX": 1.0,
                "scaleY": 1.0,
                "translateX": 10.0,
                "translateY": 80.0,
                "unit": "PT",
            },
            "image": {
                "contentUrl": "https://lh3.googleusercontent.com/slide8_pic",
                "imageProperties": {
                    "cropProperties": {
                        "leftOffset": 0.3,
                        "rightOffset": 0.3,
                    }
                },
            },
        }],
    }
    # Strict auto-scan skips it due to crop_sum=0.6 > 0.50 and x_pt=10 < 12 border margin
    self.assertEqual(
        len(
            image_util.extract_customizable_slide_pictures(
                slide_8_mock, explicit_user_request=False
            )
        ),
        0,
    )
    # Explicit user request on Slide 8 extracts it cleanly
    extracted_explicit = image_util.extract_customizable_slide_pictures(
        slide_8_mock,
        min_width_pt=50.0,
        min_height_pt=50.0,
        explicit_user_request=True,
    )
    self.assertEqual(len(extracted_explicit), 1)
    self.assertEqual(extracted_explicit[0]["objectId"], "img_8_colgate")

    # 4. PitchGenSkills.enterprise_generate_visuals_skill works with a real ConfigParser instance without AttributeError: 'dict' object has no attribute 'lower'
    real_cp = configparser.ConfigParser()
    real_cp.add_section("bucket")
    real_cp.set("bucket", "image_gen_bucket", "test-pitchgen-bucket")
    real_cp.add_section("models")
    real_cp.set("models", "gemini_image_model_2", "gemini-3-pro-image")

    mock_resp_get = mock.MagicMock()
    mock_resp_get.status_code = 200
    mock_resp_get.content = b"\x89PNG\r\n\x1a\nmock_in"
    mock_resp_get.headers = {"Content-Type": "image/png"}
    mock_resp_get.json.return_value = {
        "slides": (
            [{"objectId": f"s_{i}", "pageElements": []} for i in range(1, 8)]
            + [slide_8_mock]
        )
    }
    mock_resp_post = mock.MagicMock()
    mock_resp_post.status_code = 200
    mock_resp_post.json.return_value = {}

    with (
        mock.patch("config_loader.load_config", return_value=real_cp),
        mock.patch.object(
            agent_mod,
            "_build_apps_script_candidate_tokens",
            return_value=[("user", "mock_access_token_xyz")],
        ),
        mock.patch(
            "pitchgen_utils.image_util.upload_bytes_to_gcs",
            return_value="gs://test-pitchgen-bucket/colgate_s8.png",
        ),
        mock.patch(
            "pitchgen_utils.image_util.generate_gcs_v4_signed_url",
            return_value="https://storage.googleapis.com/test-pitchgen-bucket/colgate_s8.png",
        ),
        mock.patch(
            "pitchgen_utils.image_util._ensure_high_res_output_png",
            return_value=b"\x89PNG\r\n\x1a\nmock_hi",
        ),
        mock.patch(
            "agents.workflows.visual_transformation_workflow.VisualTransformationWorkflow.execute",
            return_value=b"\x89PNG\r\n\x1a\nmockpng",
        ) as mock_tf_exec,
        mock.patch("requests.get", return_value=mock_resp_get),
        mock.patch(
            "requests.post", return_value=mock_resp_post
        ) as mock_post_fn,
    ):
      res_in_place = agent_mod.PitchGenSkills.enterprise_generate_visuals_skill(
          prompt="Customize visual for Colgate",
          presentation_url_or_id="SAMPLE_TEST_PRESENTATION_ID_000000000003",
          target_slide_index=8,
          target_slide_indices="8",
          mode="transform",
          in_place_only=True,
          customer_name="Colgate",
          selected_model="nano_banana_pro",
      )
      parsed_in_place = json.loads(res_in_place)
      self.assertEqual(parsed_in_place.get("status"), "success")
      self.assertEqual(parsed_in_place.get("replaced_image_count"), 1)
      post_payload = mock_post_fn.call_args.kwargs["json"]
      rep_img = post_payload["requests"][0]["replaceImage"]
      self.assertEqual(rep_img.get("imageReplaceMethod"), "CENTER_CROP")
      self.assertNotIn("replaceMethod", rep_img)
      tf_kwargs = mock_tf_exec.call_args.kwargs
      self.assertTrue(tf_kwargs.get("is_in_place_picture"))
      self.assertFalse(tf_kwargs.get("is_cover_sculpture"))
      self.assertIn("Colgate", tf_kwargs.get("request", ""))
      self.assertNotIn(
          "Cymbal Retail Architecture Overview", tf_kwargs.get("request", "")
      )
      self.assertNotIn(
          "Google Cloud Modern Architecture", tf_kwargs.get("request", "")
      )

    # 5. Nano Banana Studio card title, modes, and models (including Nano Banana 2.1)
    nb_msgs = a2ui.create_a2ui_nano_banana_messages(mode="generate")
    nb_comps = {
        c["id"]: c for c in nb_msgs[2]["updateComponents"]["components"]
    }
    self.assertEqual(nb_comps["header-txt"]["text"], "Nano Banana Studio")
    mode_labels = [opt["label"] for opt in nb_comps["select-mode"]["options"]]
    self.assertEqual(
        mode_labels, ["Generate New Visual", "Restyle Existing Slide"]
    )
    model_opts = {
        opt["label"]: opt["value"]
        for opt in nb_comps["select-model"]["options"]
    }
    self.assertEqual(
        model_opts,
        {
            "Nano Banana Pro": "nano_banana_pro",
            "Nano Banana": "nano_banana",
            "Nano Banana 2.1": "gemini-nano-banana-2.1",
        },
    )

    # 6. Legacy create_a2ui_transform_messages delegates to unified Transform Slide / Deck card
    tf_legacy_msgs = a2ui.create_a2ui_transform_messages(
        presentation_id="1ColgateDeckId",
        customer_name="Colgate",
        criteria="Customize to CFO needs",
        slides_modified=1,
    )
    tf_legacy_comps = {
        c["id"]: c for c in tf_legacy_msgs[2]["updateComponents"]["components"]
    }
    self.assertEqual(
        tf_legacy_comps["header_title"]["text"],
        "🪄 Transform Slide / Deck (Text & In-Slide Images)",
    )

    # 7. Canvas Undo preservation: deck_just_generated is NOT set when presentation_id is already active in state
    undo_ctx = type(
        "UndoCtx",
        (),
        {
            "state": {
                "presentation_id": "1ColgateDeckId",
                "customer_name": "Colgate",
            }
        },
    )()
    with mock.patch.object(
        ea_mod.PitchGenSkills,
        "enterprise_transform_slide_text_skill",
        return_value=json.dumps({
            "status": "success",
            "presentation_id": "1ColgateDeckId",
            "deck_url": (
                "https://docs.google.com/presentation/d/1ColgateDeckId/edit"
            ),
            "slides_modified": 1,
        }),
    ):
      ea_mod.enterprise_transform_slide_text_skill(
          presentation_url_or_id="1ColgateDeckId",
          customization_criteria="Update for Colgate",
          target_slide_indices="8",
          customer_name="Colgate",
          transform_scope_mode="text_only",
          tool_context=undo_ctx,
      )
      self.assertFalse(undo_ctx.state.get("deck_just_generated", False))

  def test_multi_sales_play_intake_and_pipeline_logic(self):
    """Tests multi-sales-play selection in A2UI intake cards and comma-safe multi-play pipeline logic."""
    import json
    from unittest import mock

    try:
      from pitchgen.src import enterprise_agent as ea_mod
      from pitchgen.src.ge import a2ui_intake
      from pitchgen.src.agents.skill_loader import (
          resolve_required_sales_plays,
          split_sales_plays_safely,
      )
    except ImportError:
      from src import enterprise_agent as ea_mod
      from src.ge import a2ui_intake
      from src.agents.skill_loader import (
          resolve_required_sales_plays,
          split_sales_plays_safely,
      )

    # 1. Verify A2UI v0.9 Intake Card uses a single multi-select Sales Play
    # (A2UI-GE design) and merges the legacy secondary_sales_play kwarg into it.
    v09_msgs = a2ui_intake.create_a2ui_v09_intake_messages(
        customer_name="Colgate",
        sales_play="Agents & AI Powered Apps",
        secondary_sales_play="Migrate, Modernize, and Build with Data Cloud",
    )
    v09_dm = v09_msgs[1]["updateDataModel"]["value"]
    self.assertEqual(
        v09_dm["sales_play"],
        [
            "Agents & AI Powered Apps",
            "Migrate, Modernize, and Build with Data Cloud",
        ],
    )
    self.assertNotIn("secondary_sales_play", v09_dm)
    v09_comps = {
        c["id"]: c for c in v09_msgs[2]["updateComponents"]["components"]
    }
    self.assertIn("sales_play_select", v09_comps)
    self.assertNotIn("secondary_sales_play_select", v09_comps)
    self.assertTrue(v09_comps["sales_play_select"]["multiple"])
    self.assertEqual(
        v09_comps["sales_play_industry_row"]["children"],
        ["sales_play_select", "industry_select"],
    )
    # Pre-filled plays outside the canonical list still get a selectable option.
    sp_values = [o["value"] for o in v09_comps["sales_play_select"]["options"]]
    self.assertIn("Agents & AI Powered Apps", sp_values)
    submit_ctx = v09_comps["submit_btn"]["action"]["event"]["context"]
    self.assertNotIn("secondary_sales_play", submit_ctx)
    self.assertEqual(submit_ctx["sales_play"], {"path": "/sales_play"})

    # 2. Verify split_sales_plays_safely protects comma-containing canonical plays and strips prefixes/placeholders
    parsed_plays = split_sales_plays_safely(
        "AI — Your Business, Your Models, Data — Migrate, Modernize, and Build"
        " with Data Cloud, Infrastructure — Migrate, Modernize and Build,"
        " ➕ None / Single Sales Play"
    )
    self.assertEqual(
        parsed_plays,
        [
            "Your Business, Your Models",
            "Migrate, Modernize, and Build with Data Cloud",
            "Migrate, Modernize and Build",
        ],
    )

    # 4. Verify resolve_required_sales_plays resolves both primary + secondary plays without false substring collision
    resolved = resolve_required_sales_plays({
        "salesPlay": "Agents & AI Powered Apps",
        "secondary_sales_play": "Migrate, Modernize, and Build with Data Cloud",
        "business_context": (
            "Unify enterprise data and build agentic workflows."
        ),
    })
    self.assertIn("Agents & AI Powered Apps", resolved)
    self.assertIn("Migrate, Modernize, and Build with Data Cloud", resolved)
    # Ensure Data Cloud play did NOT falsely trigger Infrastructure's "Migrate, Modernize and Build"
    self.assertNotIn("Migrate, Modernize and Build", resolved)

    # 5. Verify enterprise_create_proposal_outline merges primary + secondary sales plays and preserves them across refinement
    captured_kwargs = {}

    def _fake_outline(**kwargs):
      captured_kwargs.update(kwargs)
      return json.dumps({
          "Status": "True",
          "data": {
              "agendas": {"1": {"title": "Vision", "parts": ["Part 1"]}},
              "customer": "Colgate",
              "context": {
                  "salesPlay": [
                      "Agents & AI Powered Apps",
                      "Migrate, Modernize, and Build with Data Cloud",
                  ],
                  "deck_strategy": "smart_hybrid",
              },
          },
      })

    ctx = type("DummyCtx", (), {"state": {}})()
    with mock.patch.object(
        ea_mod.PitchGenSkills,
        "create_proposal_outline",
        side_effect=_fake_outline,
    ):
      ea_mod.enterprise_create_proposal_outline(
          business_context="Data and AI transformation",
          customer_name="Colgate",
          salesPlay="Agents & AI Powered Apps",
          secondary_sales_play="Migrate, Modernize, and Build with Data Cloud",
          tool_context=ctx,
      )
      self.assertEqual(
          captured_kwargs.get("salesPlay"),
          "Agents & AI Powered Apps | Migrate, Modernize, and Build with Data"
          " Cloud",
      )

      # Now test outline refinement without explicitly passing salesPlay: both plays must be preserved from prev_ctx
      captured_kwargs.clear()
      ea_mod.enterprise_create_proposal_outline(
          business_context="Add a slide on governance",
          customer_name="Colgate",
          tool_context=ctx,
      )
      self.assertEqual(
          captured_kwargs.get("salesPlay"),
          "Agents & AI Powered Apps | Migrate, Modernize, and Build with Data"
          " Cloud",
      )

  def _outline_section_fixture(self):
    import json

    from google.genai import types

    from src import enterprise_agent as ea_mod

    sections = [
        {
            "title": "Current State",
            "subtopics": ["Legacy data silos", "Manual operations"],
            "slide_count": 2,
        },
        {"title": "The Solution", "subtopics": ["Agents"], "slide_count": 3},
        {
            "title": "Next Steps",
            "subtopics": ["Pilot", "Roadmap"],
            "slide_count": 1,
        },
    ]
    outline = {
        "Status": "True",
        "data": {
            "context": {
                "customer_name": "Acme",
                "deck_strategy": "smart_hybrid",
                "salesPlay": ["Agents & AI Powered Apps"],
                "deck_length": "Standard",
            },
            "agendas": {
                str(i + 1): {
                    "title": s["title"],
                    "parts": s["subtopics"],
                    "slide_count": s["slide_count"],
                }
                for i, s in enumerate(sections)
            },
        },
    }
    ea_mod._LATEST_OUTLINE_CACHE.clear()
    ctx = type(
        "OutlineCtx",
        (),
        {
            "state": {
                "proposal_outline": json.dumps(outline),
                "outline_surface_ids": ["pitchgen-outline-00000001"],
                "last_outline_surface_id": "pitchgen-outline-00000001",
            }
        },
    )()

    def click(name, context, surface_id):
      datapart = a2ui.format_a2ui_datapart({
          "action": {"name": name, "surfaceId": surface_id, "context": context}
      })
      req = type(
          "MockReq",
          (),
          {
              "contents": [
                  types.Content(role="user", parts=[types.Part(text=datapart)])
              ]
          },
      )()
      return ea_mod.enterprise_before_model_callback(ctx, req), req

    def agendas():
      d = json.loads(ctx.state["proposal_outline"])["data"]["agendas"]
      return [d[k] for k in sorted(d, key=int)]

    def a2ui_messages(resp):
      out = []
      for part in resp.content.parts:
        if part.inline_data:
          raw = part.inline_data.data.decode("utf-8")
          inner = raw.split(a2ui.A2A_DATA_PART_START_TAG)[1].split(
              a2ui.A2A_DATA_PART_END_TAG
          )[0]
          out.append(json.loads(inner)["data"])
      return out

    return ea_mod, ctx, sections, click, agendas, a2ui_messages

  def _assert_valid_basic_outline_surface(self, msgs):
    creates = [m for m in msgs if "createSurface" in m]
    self.assertEqual(len(creates), 1)
    self.assertEqual(
        creates[0]["createSurface"]["catalogId"], a2ui.A2UI_BASIC_CATALOG_ID
    )
    surface_id = creates[0]["createSurface"]["surfaceId"]
    self.assertRegex(surface_id, r"^pitchgen-outline-[0-9a-f]{8}$")
    comps = next(m for m in msgs if "updateComponents" in m)[
        "updateComponents"
    ]["components"]
    ids = [c["id"] for c in comps]
    self.assertEqual(len(ids), len(set(ids)))
    basic = {
        "Card",
        "Column",
        "Row",
        "Text",
        "TextField",
        "Modal",
        "Divider",
        "Button",
        "Image",
    }
    referenced = set()
    events = {}
    for comp in comps:
      self.assertIn(comp["component"], basic, comp["id"])
      self.assertNotIn("style", comp, comp["id"])
      for key in ("child", "trigger", "content"):
        if key in comp:
          self.assertIn(comp[key], ids, comp["id"])
          referenced.add(comp[key])
      for child in comp.get("children", []):
        self.assertIn(child, ids, comp["id"])
        referenced.add(child)
      event = (comp.get("action") or {}).get("event")
      if event:
        events[event["name"]] = event["context"]
    self.assertEqual(set(ids) - referenced, {"root"})
    return surface_id, events, comps

  def _assert_valid_material_outline_surface(self, msgs):
    creates = [m for m in msgs if "createSurface" in m]
    self.assertEqual(len(creates), 1)
    self.assertEqual(
        creates[0]["createSurface"]["catalogId"], a2ui.A2UI_MATERIAL_CATALOG_ID
    )
    surface_id = creates[0]["createSurface"]["surfaceId"]
    self.assertRegex(surface_id, r"^pitchgen-outline-[0-9a-f]{8}$")
    comps = next(m for m in msgs if "updateComponents" in m)[
        "updateComponents"
    ]["components"]
    ids = [c["id"] for c in comps]
    self.assertEqual(len(ids), len(set(ids)))
    material = {
        "MaterialCard",
        "MaterialColumn",
        "MaterialRow",
        "MaterialText",
        "MaterialInput",
        "MaterialButton",
        "MaterialDivider",
        "MaterialIcon",
    }
    referenced = set()
    events = {}
    for comp in comps:
      self.assertIn(comp["component"], material, comp["id"])
      self.assertNotIn("child", comp, comp["id"])
      for child in comp.get("children", []):
        self.assertIn(child, ids, comp["id"])
        referenced.add(child)
      if comp["component"] == "MaterialButton":
        self.assertIn(comp["variant"], {"basic", "raised", "stroked", "flat"})
        self.assertEqual(comp["style"]["borderRadius"], "999px")
      if comp["component"] == "MaterialInput":
        self.assertIn(comp.get("type", "text"), {"text", "number"})
      event = (comp.get("action") or {}).get("event")
      if event:
        events.setdefault(event["name"], []).append(event["context"])
    self.assertEqual(set(ids) - referenced, {"root"})
    return surface_id, events, comps

  def test_outline_card_interactive_sections_basic_catalog(self):
    """Basic fallback (outline_style='basic'): per-section Edit/Remove Modals, Add topic, Refine, Approve."""
    msgs = a2ui.create_a2ui_outline_messages(
        customer_name="Acme",
        agenda_sections=[
            {
                "title": "Current State",
                "subtopics": ["A", "B"],
                "slide_count": 2,
            },
            {"title": "Solution", "subtopics": "X • Y", "slide_count": 1},
        ],
        previous_surface_ids=["pitchgen-outline-deadbeef"],
        sales_play="Agents & AI Powered Apps",
        outline_style="basic",
    )
    self.assertEqual(
        msgs[0],
        {
            "version": "v0.9",
            "deleteSurface": {"surfaceId": "pitchgen-outline-deadbeef"},
        },
    )
    _, events, comps = self._assert_valid_basic_outline_surface(msgs)
    self.assertEqual(
        set(events),
        {
            "save_outline_section_edit",
            "delete_outline_section",
            "add_outline_section",
            "refine_proposal_outline",
            "approve_outline_and_generate",
        },
    )
    # Approve must never bind refinement_instructions; refine must.
    self.assertNotIn(
        "refinement_instructions", events["approve_outline_and_generate"]
    )
    self.assertIn("refinement_instructions", events["refine_proposal_outline"])
    by_id = {c["id"]: c for c in comps}
    self.assertEqual(by_id["sec_1_edit_modal"]["component"], "Modal")
    self.assertEqual(by_id["sec_1_delete_btn"]["variant"], "borderless")
    self.assertEqual(by_id["approve_btn"]["variant"], "primary")
    self.assertEqual(by_id["add_topic_modal"]["component"], "Modal")
    self.assertEqual(
        by_id["pitchgen_tool_logo"]["url"], a2ui.PITCHGEN_TOOL_LOGO_URL
    )
    self.assertEqual(by_id["outline_header_title"]["text"], "Proposal Outline")
    self.assertIn("Acme", by_id["outline_header_subtitle"]["text"])
    self.assertIn(
        "Agents & AI Powered Apps", by_id["outline_header_subtitle"]["text"]
    )
    self.assertEqual(by_id["sec_2_sub_1"]["text"], "• Y")
    self.assertEqual(by_id["sec_1_meta"]["text"], "2 slides")
    data_model = msgs[2]["updateDataModel"]["value"]
    self.assertEqual(data_model["sections"][0]["subtopics_text"], "A\nB")
    self.assertEqual(data_model["sections"][0]["slide_count"], "2")
    # v0.8 fallback still renders.
    v08 = a2ui.create_a2ui_outline_messages(
        customer_name="Acme",
        agenda_sections=[{"title": "S", "subtopics": ["A"], "slide_count": 1}],
        version="v0.8",
    )
    self.assertTrue(any("beginRendering" in m for m in v08))

  def test_outline_section_edit_delete_add_mutate_state_without_llm(self):
    """Edit/Delete/Add events mutate state['proposal_outline'] and re-render the card."""
    ea_mod, ctx, _, click, agendas, a2ui_messages = (
        self._outline_section_fixture()
    )

    # Edit section 2.
    resp, _ = click(
        "save_outline_section_edit",
        {
            "section_index": 1,
            "section_number": 2,
            "section_title": "Agentic Solution",
            "subtopics_text": "Agents\nGovernance",
            "slide_count": "4",
            "customer_name": "Acme",
            "deck_strategy": "smart_hybrid",
        },
        "pitchgen-outline-00000001",
    )
    self.assertIsNotNone(resp)
    msgs = a2ui_messages(resp)
    sid_edit, _, _ = self._assert_valid_material_outline_surface(msgs)
    deleted = [
        m["deleteSurface"]["surfaceId"] for m in msgs if "deleteSurface" in m
    ]
    self.assertIn("pitchgen-outline-00000001", deleted)
    self.assertEqual(
        agendas()[1],
        {
            "title": "Agentic Solution",
            "parts": ["Agents", "Governance"],
            "slide_count": 4,
        },
    )
    self.assertEqual(ctx.state["last_outline_surface_id"], sid_edit)
    self.assertIn("Updated section 2", resp.content.parts[0].text)

    # Add a topic: inserted before the closing 'Next Steps' section.
    resp, _ = click(
        "add_outline_section",
        {
            "new_topic_title": "Security & Trust",
            "new_topic_subtopics": "Zero Trust\nIAM",
            "new_topic_slides": "2",
            "customer_name": "Acme",
        },
        sid_edit,
    )
    msgs = a2ui_messages(resp)
    sid_add, _, _ = self._assert_valid_material_outline_surface(msgs)
    self.assertIn(
        sid_edit,
        [m["deleteSurface"]["surfaceId"] for m in msgs if "deleteSurface" in m],
    )
    self.assertEqual(
        [a["title"] for a in agendas()],
        ["Current State", "Agentic Solution", "Security & Trust", "Next Steps"],
    )
    self.assertEqual(agendas()[2]["parts"], ["Zero Trust", "IAM"])
    self.assertEqual(agendas()[2]["slide_count"], 2)

    # Add without a title is a no-op.
    before = ctx.state["proposal_outline"]
    resp, _ = click("add_outline_section", {"new_topic_title": ""}, sid_add)
    self.assertEqual(
        [a["title"] for a in agendas()],
        ["Current State", "Agentic Solution", "Security & Trust", "Next Steps"],
    )
    self.assertIn("Enter a topic title", resp.content.parts[0].text)
    sid_noop = ctx.state["last_outline_surface_id"]

    # Delete section 1 (title guard matches).
    resp, _ = click(
        "delete_outline_section",
        {
            "section_index": 0,
            "section_number": 1,
            "section_title": "Current State",
        },
        sid_noop,
    )
    self._assert_valid_material_outline_surface(a2ui_messages(resp))
    self.assertEqual(
        [a["title"] for a in agendas()],
        ["Agentic Solution", "Security & Trust", "Next Steps"],
    )
    self.assertNotEqual(before, ctx.state["proposal_outline"])

    # Stale index: delete falls back to matching the section title.
    click(
        "delete_outline_section",
        {"section_index": 0, "section_title": "Next Steps"},
        ctx.state["last_outline_surface_id"],
    )
    self.assertEqual(
        [a["title"] for a in agendas()],
        ["Agentic Solution", "Security & Trust"],
    )

    # Slide generator hydration reflects the edits.
    import json

    hydrated = json.loads(
        ea_mod._hydrate_slide_generator_state(
            json.dumps({"customer_name": "Acme"}), ctx
        )
    )
    self.assertEqual(
        [
            hydrated["agendas"][k]["title"]
            for k in sorted(hydrated["agendas"], key=int)
        ],
        ["Agentic Solution", "Security & Trust"],
    )

  def test_outline_section_delete_keeps_last_section(self):
    """Deleting the only remaining section is refused."""
    import json

    from src import enterprise_agent as ea_mod

    raw = json.dumps({
        "data": {
            "context": {"customer_name": "Acme"},
            "agendas": {
                "1": {"title": "Only", "parts": ["A"], "slide_count": 1}
            },
        }
    })
    updated, sections, cust, _, summary = ea_mod._apply_outline_section_action(
        raw, "delete_outline_section", {"section_index": 0}
    )
    self.assertEqual([s["title"] for s in sections], ["Only"])
    self.assertEqual(cust, "Acme")
    self.assertIn("at least one section", summary)
    self.assertEqual(
        json.loads(updated)["data"]["agendas"]["1"]["title"], "Only"
    )

  def test_outline_approve_still_routes_to_slide_generator(self):
    """Approve keeps routing to enterprise_slide_generator_skill with inline edits applied."""
    import json
    from unittest import mock

    ea_mod, ctx, _, click, agendas, _ = self._outline_section_fixture()
    with mock.patch.object(
        ea_mod,
        "_apply_outline_refinement_and_edits",
        wraps=ea_mod._apply_outline_refinement_and_edits,
    ) as m_apply:
      with mock.patch(
          "pitchgen_utils.gcs_util.write_gcs_file", return_value=None
      ):
        resp, req = click(
            "approve_outline_and_generate",
            {
                "customer_name": "Acme",
                "deck_strategy": "smart_hybrid",
                "sec_1_title": "Today's Landscape",
                "sec_1_subtopics": "Silos\nCost",
                "prompt": (
                    "Approve outline and synthesize presentation deck for Acme"
                ),
            },
            "pitchgen-outline-00000001",
        )
    self.assertIsNone(resp)
    text = req.contents[-1].parts[0].text
    self.assertIn("enterprise_slide_generator_skill", text)
    self.assertNotIn("enterprise_refine_proposal_outline", text)
    self.assertEqual(m_apply.call_args.kwargs["refinement_instructions"], "")
    self.assertEqual(agendas()[0]["title"], "Today's Landscape")
    self.assertEqual(agendas()[0]["parts"], ["Silos", "Cost"])
    self.assertTrue(json.loads(ctx.state["proposal_outline"]))

  def test_outline_material_card_default_and_inline_blocks(self):
    """Material card is the default; inline editor/confirm/add blocks appear only when selected."""
    sections = [
        {"title": "Current State", "subtopics": ["A", "B"], "slide_count": 2},
        {"title": "Solution", "subtopics": "X • Y", "slide_count": 1},
        {"title": "Next Steps", "subtopics": ["Pilot"], "slide_count": 1},
    ]

    def render(**kw):
      msgs = a2ui.create_a2ui_outline_messages(
          customer_name="Acme",
          agenda_sections=sections,
          sales_play="Agents & AI Powered Apps",
          **kw,
      )
      _, events, comps = self._assert_valid_material_outline_surface(msgs)
      return msgs, events, {c["id"]: c for c in comps}

    msgs, events, by_id = render()
    self.assertEqual(
        set(events),
        {
            "open_outline_section_editor",
            "open_outline_section_delete_confirm",
            "open_outline_add_topic",
            "refine_proposal_outline",
            "approve_outline_and_generate",
        },
    )
    self.assertFalse(any(k.endswith("_edit_title_input") for k in by_id))
    self.assertNotIn("add_topic_card", by_id)
    self.assertEqual(by_id["root"]["style"]["borderRadius"], "16px")
    self.assertEqual(by_id["sec_1_card"]["style"]["borderRadius"], "12px")
    self.assertIn(
        "surface-container-low", by_id["sec_1_card"]["style"]["backgroundColor"]
    )
    # Native Material logo pill (GE's Material catalog renders no `Image`).
    self.assertEqual(by_id["pitchgen_tool_logo"]["component"], "MaterialRow")
    self.assertEqual(by_id["pitchgen_logo_gen"]["text"], "Gen")
    self.assertEqual(by_id["outline_header_title"]["text"], "Proposal Outline")
    self.assertIn(
        "Agents & AI Powered Apps", by_id["outline_header_subtitle"]["text"]
    )
    self.assertEqual(by_id["sec_2_badge"]["text"], "2")
    self.assertEqual(by_id["sec_2_sub_1"]["text"], "• Y")
    self.assertEqual(by_id["sec_1_meta"]["text"], "2 slides")
    self.assertEqual(by_id["sec_1_edit_btn"]["label"], "Edit")
    self.assertEqual(by_id["sec_1_delete_btn"]["label"], "Remove")
    self.assertEqual(by_id["approve_btn"]["variant"], "flat")
    self.assertEqual(
        by_id["sec_3_edit_btn"]["action"]["event"]["context"]["section_index"],
        2,
    )
    approve_ctx = events["approve_outline_and_generate"][0]
    self.assertNotIn("refinement_instructions", approve_ctx)
    self.assertIn(
        "refinement_instructions", events["refine_proposal_outline"][0]
    )
    self.assertEqual(
        approve_ctx["sec_2_subtopics"], {"path": "/sections/1/subtopics_text"}
    )
    self.assertEqual(
        msgs[1]["updateDataModel"]["value"]["sections"][1]["subtopics_text"],
        "X; Y",
    )

    # Editor for section 2 only.
    _, events, by_id = render(editing_index=1)
    self.assertIn("sec_2_edit_title_input", by_id)
    self.assertEqual(by_id["sec_2_edit_slides_input"]["type"], "number")
    self.assertNotIn("sec_1_edit_title_input", by_id)
    self.assertNotIn("sec_3_edit_title_input", by_id)
    self.assertNotIn("sec_2_edit_btn", by_id)
    self.assertIn("sec_1_edit_btn", by_id)
    (save_ctx,) = events["save_outline_section_edit"]
    self.assertEqual(save_ctx["section_index"], 1)
    self.assertEqual(
        save_ctx["subtopics_text"], {"path": "/sections/1/subtopics_text"}
    )
    self.assertIn("cancel_outline_section_edit", events)

    # Remove confirmation for section 3 only.
    _, events, by_id = render(confirm_delete_index=2)
    self.assertIn("sec_3_confirm_delete_btn", by_id)
    self.assertNotIn("sec_3_delete_btn", by_id)
    self.assertNotIn("sec_1_confirm_delete_btn", by_id)
    (del_ctx,) = events["delete_outline_section"]
    self.assertEqual(del_ctx["section_title"], "Next Steps")

    # Inline add-topic block.
    _, events, by_id = render(show_add_topic=True)
    self.assertIn("add_topic_card", by_id)
    self.assertNotIn("add_topic_trigger_btn", by_id)
    self.assertIn("add_outline_section", events)

    # Only one inline block at a time (editor wins); bad indices are ignored.
    _, _, by_id = render(
        editing_index=0, confirm_delete_index=1, show_add_topic=True
    )
    self.assertIn("sec_1_edit_title_input", by_id)
    self.assertNotIn("sec_2_confirm_delete_btn", by_id)
    self.assertNotIn("add_topic_card", by_id)
    _, _, by_id = render(editing_index=9)
    self.assertFalse(any(k.endswith("_edit_title_input") for k in by_id))

  def test_outline_material_open_cancel_do_not_mutate(self):
    """Open editor / confirm / add and Cancel re-render the card without touching the outline."""
    ea_mod, ctx, _, click, agendas, a2ui_messages = (
        self._outline_section_fixture()
    )
    original = ctx.state["proposal_outline"]

    def comps_of(resp):
      msgs = a2ui_messages(resp)
      sid, _, comps = self._assert_valid_material_outline_surface(msgs)
      deleted = [
          m["deleteSurface"]["surfaceId"] for m in msgs if "deleteSurface" in m
      ]
      return sid, {c["id"] for c in comps}, deleted

    resp, req = click(
        "open_outline_section_editor",
        {"section_index": 1, "section_number": 2, "customer_name": "Acme"},
        "pitchgen-outline-00000001",
    )
    self.assertIsNotNone(resp)
    sid1, ids, deleted = comps_of(resp)
    self.assertIn("pitchgen-outline-00000001", deleted)
    self.assertIn("sec_2_edit_title_input", ids)
    self.assertNotIn("sec_1_edit_title_input", ids)
    self.assertNotIn("sec_3_edit_title_input", ids)
    self.assertEqual(
        ctx.state["outline_ui_state"], {"mode": "edit", "index": 1}
    )
    self.assertEqual(ctx.state["proposal_outline"], original)
    self.assertEqual(ctx.state["last_outline_surface_id"], sid1)
    self.assertIn("Editing section 2", resp.content.parts[0].text)

    resp, _ = click("cancel_outline_section_edit", {"section_index": 1}, sid1)
    sid2, ids, deleted = comps_of(resp)
    self.assertIn(sid1, deleted)
    self.assertFalse(any(i.endswith("_edit_title_input") for i in ids))
    self.assertIsNone(ctx.state["outline_ui_state"])
    self.assertEqual(ctx.state["proposal_outline"], original)

    resp, _ = click(
        "open_outline_section_delete_confirm",
        {"section_index": 0, "section_title": "Current State"},
        sid2,
    )
    sid3, ids, _ = comps_of(resp)
    self.assertIn("sec_1_confirm_delete_btn", ids)
    self.assertNotIn("sec_2_confirm_delete_btn", ids)
    self.assertEqual(
        ctx.state["outline_ui_state"], {"mode": "confirm_delete", "index": 0}
    )
    self.assertEqual(ctx.state["proposal_outline"], original)

    resp, _ = click("open_outline_add_topic", {"customer_name": "Acme"}, sid3)
    sid4, ids, _ = comps_of(resp)
    self.assertIn("add_topic_card", ids)
    self.assertEqual(ctx.state["proposal_outline"], original)

    # Add with an empty title keeps the inline add block open, no mutation.
    resp, _ = click("add_outline_section", {"new_topic_title": ""}, sid4)
    sid5, ids, _ = comps_of(resp)
    self.assertIn("add_topic_card", ids)
    self.assertEqual(len(agendas()), 3)

    # Confirmed delete mutates and closes the inline block.
    resp, _ = click(
        "delete_outline_section",
        {
            "section_index": 0,
            "section_number": 1,
            "section_title": "Current State",
        },
        sid5,
    )
    _, ids, _ = comps_of(resp)
    self.assertNotIn("add_topic_card", ids)
    self.assertIsNone(ctx.state["outline_ui_state"])
    self.assertEqual(
        [a["title"] for a in agendas()], ["The Solution", "Next Steps"]
    )

  def test_outline_material_confirm_delete_last_section_guard(self):
    """The remove confirmation is not offered for the only remaining section."""
    import json

    ea_mod, ctx, _, click, _, a2ui_messages = self._outline_section_fixture()
    ctx.state["proposal_outline"] = json.dumps({
        "data": {
            "context": {"customer_name": "Acme"},
            "agendas": {
                "1": {"title": "Only", "parts": ["A"], "slide_count": 1}
            },
        }
    })
    resp, _ = click(
        "open_outline_section_delete_confirm",
        {"section_index": 0, "section_title": "Only"},
        "pitchgen-outline-00000001",
    )
    _, _, comps = self._assert_valid_material_outline_surface(
        a2ui_messages(resp)
    )
    self.assertNotIn("sec_1_confirm_delete_btn", {c["id"] for c in comps})
    self.assertIn("at least one section", resp.content.parts[0].text)
    self.assertIsNone(ctx.state["outline_ui_state"])

  def test_outline_view_event_without_cached_outline_skips_llm(self):
    """View-only events with no cached outline answer directly (no prompt rewrite)."""
    ea_mod, ctx, _, click, _, _ = self._outline_section_fixture()
    ctx.state.pop("proposal_outline")
    ea_mod._LATEST_OUTLINE_CACHE.clear()
    resp, _ = click(
        "open_outline_section_editor",
        {"section_index": 0},
        "pitchgen-outline-00000001",
    )
    self.assertIsNotNone(resp)
    self.assertIn(
        "couldn't find the current outline", resp.content.parts[0].text
    )

  def test_a2ui_ge_intake_layout_multi_select_and_backend_alignment(self):
    """Verifies the A2UI-GE intake layout on qa-p2's backend contract.

    Multi-select Sales Play / Audience lists, Sales Stage + Presentation
    Archetype selects, no Context Files, and backend joining of audience lists.
    """
    import json
    from unittest import mock

    import src.enterprise_agent as ea_mod
    from src.ge import a2ui_intake

    msgs = a2ui_intake.create_a2ui_v09_intake_messages(
        customer_name="Colgate",
        user_prompt="Agentic data platform",
        sales_play=["Agentic Data Cloud", "AI — Scale AI Apps and Agents"],
        audience="CDO (Chief Data Officer), CTO (Chief Technology Officer)",
        sales_stage="s2",
        presentation_archetype="Technical_Solutioning_Pitch",
        surface_id="pitchgen-intake-abc123",
    )
    self.assertEqual(len(msgs), 3)
    self.assertEqual(
        msgs[0]["createSurface"]["catalogId"],
        "https://a2ui.org/specification/v0_9/material_catalog.json",
    )
    for m in msgs:
      inner = next(v for k, v in m.items() if k != "version")
      self.assertEqual(inner["surfaceId"], "pitchgen-intake-abc123")

    dm = msgs[1]["updateDataModel"]["value"]
    self.assertEqual(
        dm["sales_play"], ["Agentic Data Cloud", "Scale AI Apps and Agents"]
    )
    self.assertEqual(
        dm["audience"],
        ["CDO (Chief Data Officer)", "CTO (Chief Technology Officer)"],
    )
    self.assertEqual(dm["sales_stage"], "S2")
    self.assertEqual(
        dm["presentation_archetype"], "Technical_Solutioning_Pitch"
    )

    comps = msgs[2]["updateComponents"]["components"]
    by_id = {c["id"]: c for c in comps}
    self.assertEqual(len(by_id), len(comps), "Duplicate component ids")
    referenced = set()
    for c in comps:
      for child in c.get("children", []):
        self.assertIn(child, by_id, f"Missing child component {child}")
        referenced.add(child)
    self.assertEqual(set(by_id) - referenced, {"root"}, "Orphan components")

    self.assertEqual(
        by_id["intake_col"]["children"],
        [
            "tool_logo_row",
            "header_row",
            "header_divider",
            "business_context_input",
            "account_er_row",
            "strategy_length_row",
            "sales_play_industry_row",
            "stage_archetype_row",
            "audience_segment_row",
            "footer_divider",
            "submit_btn",
        ],
    )
    self.assertEqual(by_id["header_title"]["text"], "Generate a Pitch Deck")
    # Native Material logo pill (GE blocks data: images on Material surfaces).
    self.assertEqual(by_id["pitchgen_tool_logo"]["component"], "MaterialRow")
    self.assertFalse(any(c["component"] == "Image" for c in comps))
    self.assertEqual(
        by_id["audience_segment_row"]["children"],
        ["audience_select", "segment_select"],
    )
    self.assertEqual(by_id["segment_select"]["value"], {"path": "/segment"})
    seg_values = [o["value"] for o in by_id["segment_select"]["options"]]
    self.assertEqual(seg_values[0], "")
    self.assertEqual(seg_values[1:], list(a2ui_intake.INTAKE_SEGMENTS))
    audience_values = {o["value"] for o in by_id["audience_select"]["options"]}
    self.assertFalse(audience_values & set(a2ui_intake.INTAKE_SEGMENTS))
    # Sales play options are labelled "Practice Area — Play", sorted, with the
    # canonical play name as the value.
    sp_opts = by_id["sales_play_select"]["options"]
    sp_labels = [o["label"] for o in sp_opts]
    self.assertTrue(all(" — " in lbl for lbl in sp_labels))
    self.assertEqual(
        sp_labels,
        [
            f"{area} — {play}"
            for area, plays in a2ui_intake.SALES_PLAYS_BY_PRACTICE_AREA.items()
            for play in sorted(plays)
        ],
    )
    self.assertTrue(
        all(o["label"].endswith(" — " + o["value"]) for o in sp_opts)
    )
    self.assertTrue(by_id["sales_play_select"]["multiple"])
    self.assertTrue(by_id["audience_select"]["multiple"])
    for single_id in (
        "deck_strategy_select",
        "deck_length_select",
        "industry_select",
        "sales_stage_select",
        "archetype_select",
    ):
      self.assertNotIn("multiple", by_id[single_id])
    self.assertEqual(
        [o["value"] for o in by_id["sales_stage_select"]["options"]],
        ["", "S0", "S1", "S2", "S3", "S4"],
    )
    self.assertEqual(
        [o["value"] for o in by_id["archetype_select"]["options"]][1:],
        [a["id"] for a in a2ui_intake.DEFAULT_ARCHETYPES],
    )
    blob = json.dumps(msgs).lower()
    self.assertNotIn("context_files", blob)
    self.assertNotIn("context files", blob)
    self.assertNotIn("secondary_sales_play", blob)

    event = by_id["submit_btn"]["action"]["event"]
    self.assertEqual(event["name"], "create_proposal_outline")
    self.assertEqual(
        set(event["context"]),
        {
            "customer_name",
            "business_context",
            "sales_play",
            "industry",
            "audience",
            "sales_stage",
            "presentation_archetype",
            "er_number",
            "deck_strategy",
            "deck_length",
            "prompt",
            "segment",
        },
    )
    self.assertEqual(by_id["submit_btn"]["style"]["borderRadius"], "999px")

    # Segment pre-filled via audience is moved into its own dropdown.
    seg_msgs = a2ui_intake.create_a2ui_v09_intake_messages(
        customer_name="Colgate",
        audience="Enterprise, CTO (Chief Technology Officer)",
    )
    seg_dm = seg_msgs[1]["updateDataModel"]["value"]
    self.assertEqual(seg_dm["segment"], "Enterprise")
    self.assertEqual(seg_dm["audience"], ["CTO (Chief Technology Officer)"])

    # v0.8 fallback still renders with list inputs.
    with mock.patch.dict("os.environ", {"A2UI_VERSION": "v0.8"}):
      v08 = a2ui_intake.create_a2ui_intake_messages(
          sales_play=["Agentic Data Cloud"],
          audience=[
              "CDO (Chief Data Officer)",
              "CTO (Chief Technology Officer)",
          ],
      )
    self.assertTrue(v08)

    # Backend: audience lists are joined with ', ' and placeholders stripped.
    self.assertEqual(
        ea_mod._clean_intake_multi_val([
            "CDO (Chief Data Officer)",
            "Target Audience Persona",
            "CTO (Chief Technology Officer)",
            "CDO (Chief Data Officer)",
        ]),
        "CDO (Chief Data Officer), CTO (Chief Technology Officer)",
    )
    self.assertEqual(ea_mod._clean_intake_multi_val([]), "")
    self.assertEqual(ea_mod._clean_intake_multi_val(None), "")
    self.assertEqual(
        ea_mod._clean_intake_sales_plays([
            "Agentic Data Cloud",
            "Migrate, Modernize, and Build with Data Cloud",
        ]),
        "Agentic Data Cloud | Migrate, Modernize, and Build with Data Cloud",
    )

    # Backend: enterprise_create_proposal_outline forwards joined audience,
    # all sales plays, and the explicit archetype.
    captured = {}

    def _fake_outline(**kwargs):
      captured.update(kwargs)
      return json.dumps({
          "Status": "True",
          "data": {
              "agendas": {"1": {"title": "Vision", "parts": ["Part 1"]}},
              "customer": "Colgate",
              "context": {"deck_strategy": "smart_hybrid"},
          },
      })

    ctx = type("DummyCtx", (), {"state": {}})()
    with mock.patch.object(
        ea_mod.PitchGenSkills,
        "create_proposal_outline",
        side_effect=_fake_outline,
    ):
      ea_mod.enterprise_create_proposal_outline(
          business_context="Agentic data platform",
          customer_name="ColgateIntakeHybrid",
          salesPlay=["Agentic Data Cloud", "Scale AI Apps and Agents"],
          audience=[
              "CDO (Chief Data Officer)",
              "CTO (Chief Technology Officer)",
          ],
          presentation_archetype="Technical_Solutioning_Pitch",
          tool_context=ctx,
      )
    self.assertEqual(
        captured.get("audience"),
        "CDO (Chief Data Officer), CTO (Chief Technology Officer)",
    )
    self.assertEqual(
        captured.get("salesPlay"),
        "Agentic Data Cloud | Scale AI Apps and Agents",
    )
    self.assertEqual(
        captured.get("presentation_archetype"), "Technical_Solutioning_Pitch"
    )


if __name__ == "__main__":
  unittest.main()
