import os
import sys

pitchgen_dir = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, pitchgen_dir)
sys.path.insert(0, os.path.join(pitchgen_dir, "src"))

# Run InitGoogle for Enterprise Workspace
try:
  from enterprise_workspace.base.python.clif import googleinit
  googleinit.Run(sys.argv[:1])
except ImportError:
  pass

from config_loader import load_config
from state import GlobalState
from agents.slide_engineering_agent import SlideEngineeringAgent


def test_netflix_pitch():
  config = load_config()
  from agents.workflows.text_transformer_workflow import TextTransformerWorkflow

  transformer = TextTransformerWorkflow(config)

  context = {
      "customer_name": "Netflix",
      "industry": "Media & Entertainment",
      "sub_industry": "Streaming & Global Studio Production",
      "audience": "CEO & Executive Leadership",
      "salesPlay": "Scale AI Apps and Agents",
  }

  print("\n" + "=" * 75)
  print("SLIDE 1: Gemini Enterprise App (Workplace / Studio Agentic Platform)")
  print("=" * 75)

  slide1_title = "Gemini Enterprise app"
  slide1_headline = "Your home for agentic workplace transformation\nAchieve absolute enterprise productivity with AI grounded in your business data"
  slide1_bullets = [
      "Build, manage and deploy agents from a single, purpose-built app",
      "Connect enterprise data to employee workflows",
      "Seamlessly create, view and edit work across applications, all in one place",
      "Put the latest Google AI innovations in the hands of all your employees"
  ]

  customized_headline = transformer.execute(
      text=slide1_headline,
      criteria="strategic_partnership and business_value headline customization for Netflix CEO pitch. Focus on autonomous studio productivity, global streaming scale, and creative workflows.",
      context=context,
  )

  customized_bullets = transformer.execute_batch(
      texts=slide1_bullets,
      criteria="solution_overview and business_value customization for Netflix CEO pitch. Tailor to studio operations, localized creative production, content pipelines, and IP-secure enterprise data.",
      context=context,
  )

  print(f"\n[Original Headline]:\n{slide1_headline}")
  print(f"\n[Customized Headline]:\n{customized_headline}")
  print("\n[Bullet Points Customization]:")
  for orig, cust in zip(slide1_bullets, customized_bullets):
    print(f"  • [ORIGINAL]   : {orig}")
    print(f"    [CUSTOMIZED] : {cust}\n")

  print("=" * 75)
  print("SLIDE 2: Passive AI vs Agentic Transformation (Streaming / Ad-Tier Journey)")
  print("=" * 75)

  slide2_header = "The era of passive AI is over.\nAgentic transformation has arrived."
  slide2_steps = [
      "What is the latest performance data for our summer 2026 ad campaign?",
      "Compare the click-through rates of our email campaigns from Q1 and Q2",
      "Identify our highest-value segment and draft personalized campaigns to maximize their lifetime value"
  ]

  customized_header = transformer.execute(
      text=slide2_header,
      criteria="strategic_partnership and business_value transformation for Netflix CEO pitch. Emphasize moving from reactive data queries to autonomous agentic execution across global streaming & ad-tier operations.",
      context=context,
  )

  customized_steps = transformer.execute_batch(
      texts=slide2_steps,
      criteria="Tailor step progression (Chat -> Reason -> Execute) for Netflix CEO pitch. Focus on ad-supported tier subscriber monetization, viewing engagement, and automated localized marketing.",
      context=context,
  )

  print(f"\n[Original Header]:\n{slide2_header}")
  print(f"\n[Customized Header]:\n{customized_header}")
  print("\n[Step Progression Customization]:")
  steps = ["Step 1: Chat (Query)", "Step 2: Think and reason (Analyze)", "Step 3: Execute (Autonomous Action)"]
  for s_name, orig, cust in zip(steps, slide2_steps, customized_steps):
    print(f"  [{s_name}]")
    print(f"    ORIGINAL   : {orig}")
    print(f"    CUSTOMIZED : {cust}\n")

  # =========================================================================
  # TEST MODE 3: EXECUTIVE SPEAKER NOTES & OBJECTION HANDLING
  # =========================================================================
  print("=" * 75)
  print("MODE 3: EXECUTIVE SPEAKER NOTES (Netflix CEO Delivery & Objections)")
  print("=" * 75)
  from agents.workflows.template_mapper_workflow import TemplateMapperWorkflow
  mapper = TemplateMapperWorkflow(config)
  slide_result = mapper.execute(
      slide_title=customized_headline,
      slide_content="\n".join([f"• {b}" for b in customized_bullets]),
      layout="Context",
      context=context,
  )
  print(f"[Generated Executive Speaker Notes]:\n{slide_result.get('speaker_notes')}\n")


def test_dynamic_use_case_discovery():
  print("=" * 75)
  print("TESTING DYNAMIC USE CASE DISCOVERY ACROSS ALL VERTICALS")
  print("=" * 75)
  from agents.skill_loader import get_all_use_case_databases
  from agents.skill_loader import find_matching_use_case

  all_dbs = get_all_use_case_databases()
  print(f"[SkillLoader] Discovered {len(all_dbs)} JSON use case databases dynamically:")
  for db_name, items in all_dbs.items():
    print(f"  - {db_name} ({len(items)} use cases)")

  assert len(all_dbs) >= 2, "Should discover databases across multiple directories"

  # Test 1: Retail supply chain matching with retail context
  retail_match = find_matching_use_case(
      query_text="Supply Chain and Demand Forecasting",
      context={"industry": "Retail", "customer_name": "Target"},
  )
  print(f"\n[Test 1 Retail Match]: {retail_match.get('use_case_title') if retail_match else 'None'}")
  assert retail_match is not None

  # Test 2: Energy grid / foresight matching with power & energy context
  energy_match = find_matching_use_case(
      query_text="Strategic Foresight and Resilient Grid Infrastructure",
      context={"industry": "Power & Energy", "customer_name": "NextEra"},
  )
  print(f"[Test 2 Energy Match]: {energy_match.get('use_case_title') if energy_match else 'None'}")
  assert energy_match is not None

  # Test 3: Connected store matching
  store_match = find_matching_use_case(
      query_text="Create the Connected Store with Real-time Edge AI",
  )
  print(f"[Test 3 Store Match]: {store_match.get('use_case_title') if store_match else 'None'}")
  assert store_match is not None

  print("\n>>> All dynamic use case discovery tests PASSED!")


def test_pitchhub_title_and_content_templates_and_deck_gen_library():
  import json
  from pathlib import Path

  src_dir = Path(pitchgen_dir) / "src"
  meta_txt = json.loads(
      (src_dir / "templates_metadata" / "context.txt").read_text()
  )
  ctx_json = json.loads(
      (src_dir / "prompt_templates" / "layouts" / "context.json").read_text()
  )
  new_ctx_json = json.loads(
      (
          src_dir / "prompt_templates" / "layouts" / "new_context.json"
      ).read_text()
  )

  expected_28_sids = [
      "g36ba0835289_0_3140",
      "g36ba0835289_0_3171",
      "g36ba0835289_0_3205",
      "g36ba0835289_0_3241",
      "g36ba0835289_0_3267",
      "g36ba0835289_0_3296",
      "g36ba0835289_0_3327",
      "g36ba0835289_0_3357",
      "g36ba0835289_0_3400",
      "g36ba0835289_0_3427",
      "g36ba0835289_0_3459",
      "g36ba0835289_0_3472",
      "g36ba0835289_0_3512",
      "g36ba0835289_0_3603",
      "g36ba0835289_0_3660",
      "g36ba0835289_0_3696",
      "g36ba0835289_0_3796",
      "g36ba0835289_0_3882",
      "g36ba0835289_0_3952",
      "g36ba0835289_0_4025",
      "g36ba0835289_0_4070",
      "g36ba0835289_0_4106",
      "g36ba0835289_0_4158",
      "g36ba0835289_0_4190",
      "g36ba0835289_0_4270",
      "g36ba0835289_0_4388",
      "g36ba0835289_0_16229",
      "g36ba0835289_0_18067",
  ]

  actual_sids = [
      k.split("@")[2]
      for k in sorted(meta_txt.keys(), key=lambda x: int(x.split("@")[0]))
  ]
  assert len(actual_sids) >= 26
  assert actual_sids == [s for s in expected_28_sids if s in set(actual_sids)]
  expected_idx_keys = [
      k.split("@")[0]
      for k in sorted(meta_txt.keys(), key=lambda x: int(x.split("@")[0]))
  ]
  assert list(ctx_json["templates"].keys()) == expected_idx_keys
  assert len(new_ctx_json["templates"]) >= 26

  for idx_str, key in sorted(
      [(k.split("@")[0], k) for k in meta_txt.keys()],
      key=lambda t: int(t[0]),
  ):
    assert set(meta_txt[key].keys()) == set(
        ctx_json["templates"][idx_str].keys()
    )

  config = load_config()
  from agents.slide_engineering_agent import get_final_content

  agent = SlideEngineeringAgent(config)
  assert (
      agent._infer_bespoke_layout(0, "Customer Challenge", "Context")
      == "Context"
  )
  assert (
      agent._infer_bespoke_layout(2, "Technical Architecture", "Solution")
      == "Context"
  )

  from types import SimpleNamespace

  sampled_covers = set()
  for _ in range(60):
    final_res = get_final_content(
        SimpleNamespace(title="Pitch"),
        {"1": {"slides": {}}},
        {
            "1": {"title": "Sec 1"},
            "2": {"title": "Sec 2"},
            "3": {"title": "Sec 3"},
            "4": {"title": "Sec 4"},
            "5": {"title": "Sec 5"},
        },
        {},
        [],
    )
    cover_url = final_res["sections"]["title"]["slides"]["1"]["temp_url"]
    assert "TEMPLATE_DECK_TITLE_V1_PLACEHOLDER_00001" in cover_url
    sampled_covers.add(cover_url.split("slide=id.")[-1])
  assert len(sampled_covers) > 1


if __name__ == "__main__":
  test_pitchhub_title_and_content_templates_and_deck_gen_library()
  test_dynamic_use_case_discovery()
  test_netflix_pitch()
