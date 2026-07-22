import json
import os
import sys



sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# googleinit removed

from agent import PitchGenSkills



def test_sidebar_real_search():
  print("--- Starting Real Sidebar Search E2E Test ---")

  # Test search query
  search_query = "retail supply chain"

  print(f"\n[Test] Calling sidebar_search for query: '{search_query}'...")
  try:
    result_json_str = PitchGenSkills.sidebar_search(
        search_query=search_query, strict_search=False, user_ldap="test_user"
    )

    result = json.loads(result_json_str)
    if "error" in result:
      print(f"[Test] Real Sidebar Search Failed with error: {result['error']}")
      return

    print(f"[Test] E2E Search Completed successfully!")
    print(f"Search Query: {result.get('search_query')}")

    results = result.get("search_results", [])
    print(f"Number of retrieved slide suggestions: {len(results)}")

    print("\nTop retrieved slides:")
    for idx, slide in enumerate(results[:3]):
      print(
          f"  {idx + 1}: {slide.get('name')} (Score:"
          f" {slide.get('sim_score', 'N/A')})"
      )
      print(f"     URL: {slide.get('slideURL')}")
      print(f"     Date: {slide.get('date')}")
      print(f"     Tags: {slide.get('tags', [])}")

  except Exception as e:
    print(f"[Test] Unexpected exception during E2E test: {e}")


def main(argv):
  del argv  # Unused
  test_sidebar_real_search()

if __name__ == "__main__":
  from absl import app
  app.run(main)

