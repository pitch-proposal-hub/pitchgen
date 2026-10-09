import json
import os
import sys

try:
  import urllib3.contrib.pyopenssl
  urllib3.contrib.pyopenssl.extract_from_urllib3()
except Exception:
  pass

# Prepend enterprise_workspace path for execution
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Run InitGoogle for Enterprise Workspace
try:
  from enterprise_workspace.base.python.clif import googleinit
  googleinit.Run(sys.argv[:1])
except ImportError:
  pass

from agent import PitchGenSkills
from state import GlobalState
import inspect
from agents.skill_loader import load_skill_json_database



def test_split_workflow():
  print("--- Starting Split Workflow Test ---")

  # Phase 1: Create Outline & Agenda
  customer_name = "Starbucks"
  business_context = (
      "How Google Cloud AI can help Starbucks optimize supply chain."
  )
  industry = "Retail"
  solution = "Vertex AI, Gemini"

  print("\n[Test] Running Phase 1 (create_proposal_outline)...")
  state_json_str = PitchGenSkills.create_proposal_outline(
      customer_name=customer_name,
      business_context=business_context,
      industry=industry,
      solution=solution,
      audience="segment, Enterprise",
      user_ldap="test_user",
      er_number="12345",
      user_input_id="test_session_123",
      sub_industry="QSR",
      salesPlay="Scale AI Apps and Agents,Your Business, Your Models",
  )

  state_data = json.loads(state_json_str)
  if state_data.get("error") is not None:
    print(f"[Test] Phase 1 Failed with error: {state_json_str}")
    return

  state = GlobalState.from_json(state_json_str)
  print(f"[Test] Phase 1 Completed. Generated {len(state.agendas)} agendas.")
  print("Agendas:")
  for k, v in state.agendas.items():
    print(f"  {k}: {v['title']}")

  # Simulate UI edit: Let's rename one agenda to test that Retrieval runs on edited agendas
  if "1" in state.agendas:
    old_title = state.agendas["1"]["title"]
    state.agendas["1"][
        "title"
    ] = "Optimized Starbucks Supply Chain with Vertex AI"
    print(
        f"\n[Test] Simulating UI Edit: Renamed Agenda 1 from '{old_title}' to"
        f" '{state.agendas['1']['title']}'"
    )

  # Inject a mock retrieved slide suggestion to test dynamic GTM/Tone/Account-based Customization!
  state.reusable_slides = {
      "1": {
          "title": "Optimized Starbucks Supply Chain with Vertex AI",
          "suggestions": [{
              "original_title": "Google Cloud Retail Data Platform Overview",
              "original_content": (
                  "78% of retailers struggle with legacy POS and warehouse inventory databases.\n"
                  "Google Cloud helps retailers modernize legacy systems, reduce out-of-stock rates, and improve store operational metrics."
              ),
              "temp_url": (
                  "https://docs.google.com/presentation/d/TEMPLATE_DECK_CONTEXT_V1_PLACEHOLDER_001/edit#slide=id.g36ba0835289_0_3660"
              ),
          }],
      }
  }
  edited_state_json_str = state.to_json()

  # Phase 2: Retrieval + Creative Gen
  print("\n[Test] Running Phase 2 (slide_generator_skill)...")
  final_state_json_str = PitchGenSkills.slide_generator_skill(
      edited_state_json_str
  )

  response_data = json.loads(final_state_json_str)
  if isinstance(response_data, dict) and response_data.get("error") is not None:
    print(f"[Test] Phase 2 Failed with error: {final_state_json_str}")
    return

  print("\n[Test] Phase 2 Completed.")
  print("Wrapped Phase 2 Response:", json.dumps(response_data, indent=2))

  if isinstance(response_data, dict):
    if response_data.get("status") == "success":
      print(f"[Test] Final Deck URL: {response_data.get('deck_url')}")
    arch_filename = response_data.get("architectural_filename")
    outputs_filename = response_data.get("outputs_filename")
  else:
    arch_filename = next(
        item["architectural_filename"]
        for item in response_data
        if "architectural_filename" in item
    )
    outputs_filename = next(
        item["outputs_filename"]
        for item in response_data
        if "outputs_filename" in item
    )

  from pitchgen_utils.gcs_util import read_gcs_file
  from config_loader import load_config
  config = load_config()
  bucket_name = config.get("bucket", "content")

  print("\n[Test] Reading architectural data from GCS...")
  arch_data_json = read_gcs_file(f"gs://{bucket_name}/{arch_filename}")
  reusable_slides = json.loads(arch_data_json)
  print("\n[Test] Reusable Slides mapped:")
  print(json.dumps(reusable_slides, indent=2))

  print("\n[Test] Reading outputs data from GCS...")
  outputs_data_json = read_gcs_file(f"gs://{bucket_name}/{outputs_filename}")

  outputs_data = json.loads(outputs_data_json)
  print("\n--- Final Deck Structure ---")
  print(json.dumps(outputs_data.get("sections"), indent=2))

  import sys
  sys.stdout.flush()
  import os
  os._exit(0)


if __name__ == "__main__":
  test_split_workflow()
