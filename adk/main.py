import os
import sys
from config_loader import load_config
from orchestrators.creative_orchestrator import CreativeOrchestrator
from orchestrators.narrative_orchestrator import NarrativeOrchestrator


def get_input(prompt, default):
  if not sys.stdin.isatty():
    return default
  try:
    val = input(f"{prompt} [{default}]: ")
    return val if val else default
  except EOFError:
    return default


def main():
  config = load_config()

  # Check for CLI input or provide defaults
  print("--- PitchGen ADK 2.0 Execution ---")
  customer_name = get_input("Enter Customer Name", "Acme Corp")
  business_context = get_input(
      "Enter Business Context",
      "Generate a deck for Acme Corp on how Google Cloud AI can help improve"
      " their manufacturing efficiency.",
  )
  industry = get_input("Enter Industry", "Manufacturing")
  solution = get_input(
      "Enter Solution(s) separated by comma", "Vertex AI, Gemini"
  )
  solution_list = [s.strip() for s in solution.split(",")]

  # 1. Narrative Orchestration
  narrative_orch = NarrativeOrchestrator(config)

  initial_context = {
      "customer_name": customer_name,
      "business_context": business_context,
      "industry": industry,
      "solution": solution_list,
      "visuals_requested": True,
  }

  state = narrative_orch.run(initial_context)

  # 2. Creative Orchestration
  creative_orch = CreativeOrchestrator(config)
  final_state = creative_orch.run(state)

  print("\n--- Final Deck Blueprint ---")
  print(final_state.to_json())


if __name__ == "__main__":
  # Add current dir to sys.path
  sys.path.append(os.path.dirname(os.path.abspath(__file__)))
  main()
