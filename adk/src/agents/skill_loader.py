import os
import re


def load_skill_instructions(skill_name: str) -> str:
  """Loads and parses the instructions from a given ADK agent skill folder.

  It reads the SKILL.md file, strips the YAML frontmatter, and returns the
  raw markdown instructions.

  Args:
      skill_name: The name of the skill folder (e.g., 'cvi_framework').

  Returns:
      The raw markdown instructions of the skill, or an empty string if not
      found.
  """
  current_dir = os.path.dirname(os.path.abspath(__file__))
  skill_md_path = os.path.join(current_dir, "skills", skill_name, "SKILL.md")

  if not os.path.exists(skill_md_path):
    print(f"[SkillLoader] Warning: Skill file not found at {skill_md_path}")
    return ""

  try:
    with open(skill_md_path, "r") as f:
      content = f.read()

    # Strip YAML frontmatter
    frontmatter_pattern = r"^---\s*\n.*?\n---\s*\n"
    cleaned_content = re.sub(
        frontmatter_pattern, "", content, flags=re.DOTALL | re.MULTILINE
    )

    return cleaned_content.strip()
  except Exception as e:
    print(f"[SkillLoader] Error reading skill {skill_name}: {e}")
    return ""


def load_skill_reference(skill_name: str, reference_name: str) -> str:
  """Loads and parses a reference markdown file inside a given skill folder.

  Args:
      skill_name: The name of the skill folder (e.g., 'sales_play_selection').
      reference_name: The name of the reference file without path (e.g.,
        'scale_ai_apps_and_agents.md').

  Returns:
      The raw markdown content of the reference file, or empty string if not
      found.
  """
  current_dir = os.path.dirname(os.path.abspath(__file__))
  ref_path = os.path.join(
      current_dir, "skills", skill_name, "references", reference_name
  )

  if not os.path.exists(ref_path):
    print(f"[SkillLoader] Warning: Reference file not found at {ref_path}")
    return ""

  try:
    with open(ref_path, "r") as f:
      content = f.read()
    return content.strip()
  except Exception as e:
    print(f"[SkillLoader] Error reading reference {reference_name}: {e}")
    return ""


def load_skill_json_database(skill_name: str, database_name: str) -> dict:
  """Loads and parses a JSON database file inside a given skill's references/ folder.

  Args:
      skill_name: The name of the skill folder (e.g., 'use_case_context').
      database_name: The name of the JSON file without path (e.g.,
        'retail/create_the_connected_store.json').

  Returns:
      A dictionary representing the parsed JSON database, or an empty dict if
      not found.
  """
  import json

  current_dir = os.path.dirname(os.path.abspath(__file__))
  db_path = os.path.join(
      current_dir, "skills", skill_name, "references", database_name
  )

  if not os.path.exists(db_path):
    print(f"[SkillLoader] Warning: JSON database file not found at {db_path}")
    return {}

  import time
  for attempt in range(5):
    try:
      with open(db_path, "r") as f:
        content = f.read()
      return json.loads(content)
    except FileNotFoundError as fnf:
      if attempt == 4:
        print(f"[SkillLoader] CRITICAL FileNotFoundError: db_path = {db_path}", flush=True)
        print(f"[SkillLoader] exists inside handler = {os.path.exists(db_path)}", flush=True)
        try:
            st = os.stat(db_path)
            print(f"[SkillLoader] stat details: mode={st.st_mode}, size={st.st_size}", flush=True)
        except Exception:
            pass
        raise fnf
      time.sleep(0.05 * (attempt + 1))
    except Exception as e:
      print(f"[SkillLoader] Error reading JSON database {database_name}: {e}")
      return {}
  return {}


def detect_industry_category(client, gemini_model: str, input_industry: str, available_categories: list) -> str:
  """Uses Gemini to map the input industry name to one of the available skill folders."""
  if not input_industry or not available_categories:
    return "None"

  input_lower = input_industry.lower().strip()
  for cat in available_categories:
    if cat.lower().strip() == input_lower:
      return cat

  prompt = f"""Given the list of available target industry GTM folders: {available_categories}
  And the target customer's industry: "{input_industry}"

  Identify which available industry folder is the most appropriate parent or matching category for this customer's industry.
  If the customer's industry matches or is a clear sub-category of one of the available folders, return the exact name of that folder.
  If there is no logical relation at all, return "None".

  Examples:
  - Input: "Gaming", Available: ["retail", "media"] -> Return "media"
  - Input: "Grocery Store", Available: ["retail", "media"] -> Return "retail"
  - Input: "Investment Banking", Available: ["retail", "media"] -> Return "None"
  - Input: "CPG", Available: ["retail", "media"] -> Return "retail"
  - Input: "Utilities", Available: ["retail", "power_energy"] -> Return "power_energy"

  Respond ONLY with the name of the folder or "None". No other text or explanation.
  """
  try:
    from google.genai import types
    response = client.models.generate_content(
        model=gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
        ),
    )
    result = response.text.strip().replace('"', '').replace("'", "")
    if result in available_categories:
      return result
  except Exception as e:
    print(f"[SkillLoader] Error during industry category detection: {e}")
  return "None"

