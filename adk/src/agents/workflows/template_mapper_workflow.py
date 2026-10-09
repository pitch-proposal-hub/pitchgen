import json
import os
import re
from google import genai
from google.genai import types
from agents.workflows.base_workflow import BaseWorkflow


class TemplateMapperWorkflow(BaseWorkflow):

  def __init__(self, config):
    super().__init__(
        "TemplateMapperWorkflow",
        "Maps generated text to Google Slides placeholders.",
    )
    self.config = config
    self.project_id = config["default"]["project_name"]
    self.gemini_model = config["default"]["gemini_model_1"]

    self.layout_mapping = {
        "Context": "context",
        "Title and content": "context",
        "Case Study": "case_study",
        "Charts": "charts",
        "Circle Charts": "circle_charts",
        "Next Steps": "next_steps",
        "Timeline": "timeline",
        "Industry Use Case": "industry_use_case",
        # GC AI Brand Slides - Always enforce the 'AI_agents' style layouts
        "GC_AI_Title": "gc_ai_Title_slides_AI_agents",
        "GC_AI_Agenda": "gc_ai_Agenda_slides_AI_agents",
        "GC_AI_Divider": "gc_ai_Divider_slides_AI_agents",
        "GC_AI_Welcome": "gc_ai_Welcome_slide_AI_agents",
        "GC_AI_Speaker": "gc_ai_Speaker_slides_AI_agents",
        "GC_AI_Quote": "gc_ai_Quote_slides_AI_agents",
        "GC_AI_Key_takeaway": "gc_ai_Key_takeaway_slides_AI_agents",
    }

  def execute(
      self,
      slide_title,
      slide_content,
      layout="Context",
      used_slide_ids=None,
      context=None,
      min_cards: int = 0,
  ):
    if used_slide_ids is None:
      used_slide_ids = []

    workflows_dir = os.path.dirname(
        os.path.abspath(__file__)
    )  # src/agents/workflows
    src_dir = os.path.dirname(os.path.dirname(workflows_dir))  # src/

    # 1. Load consolidated layout JSON
    layout_file_part = self.layout_mapping.get(layout, "context")
    layout_file = os.path.join(
        src_dir, "prompt_templates", "layouts", f"{layout_file_part}.json"
    )

    if not os.path.exists(layout_file):
      # Fallback to context if specific layout file doesn't exist
      layout_file = os.path.join(
          src_dir, "prompt_templates", "layouts", "context.json"
      )

    with open(layout_file, "r") as f:
      layout_data = json.load(f)

    # Load metadata file to map template numbers to deck_id and slide_id
    metadata_file = os.path.join(
        src_dir, "templates_metadata", f"{layout_file_part}.txt"
    )
    template_coords = {}
    if os.path.exists(metadata_file):
      try:
        with open(metadata_file, "r") as f:
          metadata = json.load(f)
        for key in metadata.keys():
          parts = key.split("@")
          if len(parts) >= 3:
            template_coords[parts[0]] = {
                "deck_id": parts[1],
                "slide_id": parts[2],
            }
      except Exception as e:
        print(f"[TemplateMapperWorkflow] Error loading template metadata: {e}")

    # 2. Build and compile prompt dynamically from template_sorter_base.txt
    all_templates = layout_data.get("templates", {})

    # Resolve already used template numbers for deterministic deduplication
    used_templates = []
    for t_num in all_templates.keys():
      coords = template_coords.get(t_num)
      if coords and coords["slide_id"] in used_slide_ids:
        used_templates.append(str(t_num))

    # Visual layout families in Context-v1 so consecutive bespoke slides use distinct visual structures
    visual_families = [
        ("3col_vertical", ["3", "7", "14", "20"]),
        ("4col_vertical", ["12", "13", "21", "26"]),
        ("4card_grid_or_rows", ["8", "9", "15", "24", "28"]),
        ("5col_stairstep", ["6", "16", "17", "19"]),
        ("3card_left_rail", ["2", "18", "25"]),
        ("3col_dual_tier", ["22"]),
        ("kpi_plus_4col", ["23"]),
        ("statement_banners", ["1", "11", "27"]),
        ("2card_split", ["4"]),
    ]
    template_to_family = {}
    for fam_name, fam_members in visual_families:
      for m in fam_members:
        template_to_family[m] = fam_name

    used_families = {
        template_to_family[t]
        for t in used_templates
        if t in template_to_family
    }

    capacities = {}
    for t_num, t_info in all_templates.items():
      if isinstance(t_info, dict):
        num_headers = sum(
            1 for k in t_info.keys() if re.match(r"^header\d+$", str(k))
        )
        num_items = sum(
            1 for k in t_info.keys() if re.match(r"^item\d+$", str(k))
        )
        capacities[str(t_num)] = max(num_headers, num_items)

    # Filter out already-used templates first
    unused_templates = {
        str(k): v
        for k, v in all_templates.items()
        if str(k) not in used_templates
    }
    if not unused_templates:
      unused_templates = {str(k): v for k, v in all_templates.items()}

    # Filter by min_cards capacity when a slide must cover multiple outline subtopics,
    # while allowing 3, 4, and 5-card templates so 4-card and 5-card stairstep layouts (16, 17, 6, 19) are actively used
    candidate_pool = {}
    if min_cards and min_cards >= 2:
      max_cap = (
          max(capacities.get(k, 0) for k in unused_templates.keys())
          if unused_templates
          else 0
      )
      effective_min = min(min_cards, max_cap) if max_cap > 0 else min_cards
      for t_num, t_info in unused_templates.items():
        if capacities.get(t_num, 0) >= effective_min:
          candidate_pool[t_num] = t_info
    if not candidate_pool:
      candidate_pool = dict(unused_templates)

    # Prefer templates from visual families that have NOT been used yet in this deck
    fresh_family_pool = {
        t_num: t_info
        for t_num, t_info in candidate_pool.items()
        if template_to_family.get(t_num) not in used_families
    }
    if fresh_family_pool:
      candidate_pool = fresh_family_pool

    # Deterministically rotate/shuffle candidate keys per slide so the LLM does not default
    # to the first keys or repeat the same template across runs
    import hashlib
    import random

    seed_str = f"{slide_title}|{len(used_slide_ids)}|{','.join(used_templates)}"
    seed_int = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed_int)

    # Group candidates by visual family and pick up to 2 per family in rotated order
    # so the prompt presents a balanced, diverse menu across 3-card, 4-card, 5-card, dual-tier, KPI, and banner layouts
    fam_buckets = {}
    for t_num, t_info in candidate_pool.items():
      fam = template_to_family.get(t_num, f"other_{t_num}")
      fam_buckets.setdefault(fam, []).append((t_num, t_info))
    for fam_list in fam_buckets.values():
      rng.shuffle(fam_list)

    fam_keys = list(fam_buckets.keys())
    rng.shuffle(fam_keys)

    ordered_pairs = []
    round_idx = 0
    while True:
      added_any = False
      for fk in fam_keys:
        if round_idx < len(fam_buckets[fk]):
          ordered_pairs.append(fam_buckets[fk][round_idx])
          added_any = True
      if not added_any:
        break
      round_idx += 1

    templates_prompt_schema = {k: v for k, v in ordered_pairs}

    base_prompt_file = os.path.join(
        src_dir, "prompt_templates", "template_sorter_base.txt"
    )
    with open(base_prompt_file, "r") as f:
      base_prompt = f.read()

    used_templates_instruction = ""
    if used_templates:
      used_templates_instruction = (
          f"\nAlready Used Templates (DO NOT USE): {used_templates}. You MUST"
          " select a template key from the provided `Templates:` JSON object"
          " above that has NOT been used yet.\n"
      )
    used_templates_instruction += (
        "\nLAYOUT DIVERSITY & PLACEHOLDER MAPPING RULES:\n"
        "- Actively vary layouts across the deck: use 4-card grids/columns"
        " (8, 9, 12, 13, 15, 21, 24, 26, 28), 5-column stair-step layouts"
        " (6, 16, 17, 19), dual-tier columns (22), KPI + 4-column layouts"
        " (23), statement banners (1, 11, 27), and 3-column layouts (2, 3,"
        " 7, 14, 18, 20, 25).\n"
        "- If you select a 4-card or 5-card template (e.g., 6, 16, 17, 19)"
        " and the input has 3 or 4 bullets, split or unpack the richest"
        " dimension into an additional complementary pillar so EVERY"
        " placeholder in the chosen template is completely populated.\n"
        "- If you select Template 22 (`header1..3`, `header1_content..3`,"
        " `item1..3`), populate `header1..3` and `header1_content..3` with"
        " the 3 core pillars and `item1..3` with each pillar's concrete"
        " business outcome or architectural takeaway.\n"
        "- If you select Template 23 (`item1..3` 2-12 chars + `header1..4`),"
        " populate `item1..3` with crisp metric/KPI callouts (e.g. '99.99%',"
        " '3x', '<10ms') and `header1..4` with 4 strategic pillars.\n"
        "- If you select an `item1..N` statement template (1, 11, 27),"
        " synthesize each bullet's header and body into a single cohesive"
        " executive statement per `itemK`.\n"
    )
    if min_cards and min_cards >= 2:
      used_templates_instruction += (
          f"\nCRITICAL MULTI-TOPIC REQUIREMENT: This slide covers {min_cards}"
          " distinct outline subtopics. You MUST choose a template with at"
          f" least {min_cards} slots and populate every single subtopic"
          " without dropping any subtopic.\n"
      )

    input_text = f"Slide Title: {slide_title}\nSlide Content: {slide_content}"

    full_prompt = base_prompt.format(
        templates=json.dumps(templates_prompt_schema, indent=2),
        used_templates_instruction=used_templates_instruction,
        examples=layout_data.get("examples", ""),
        input_text=input_text,
    )

    client = genai.Client(
        vertexai=True, project=self.project_id, location="global"
    )

    import time

    max_retries = 4
    base_delay = 1.6
    response = None

    for attempt in range(max_retries):
      try:
        response = client.models.generate_content(
            model=self.gemini_model,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        break
      except Exception as e:  # pylint: disable=broad-exception-caught
        err_msg = str(e).lower()
        if (
            "429" in err_msg
            or "resource_exhausted" in err_msg
            or "rate limit" in err_msg
            or "quota" in err_msg
        ):
          if attempt == max_retries - 1:
            print(
                f"[TemplateMapperWorkflow] Quota exhausted after {max_retries}"
                " attempts; falling back to deterministic placeholder mapping."
            )
            break
          sleep_time = (base_delay ** attempt) + random.uniform(0.2, 0.9)
          print(
              "[TemplateMapperWorkflow] Rate limit (429) hit. Retrying in"
              f" {sleep_time:.2f}s... (Attempt {attempt + 1}/{max_retries})"
          )
          time.sleep(sleep_time)
        else:
          print(
              f"[TemplateMapperWorkflow] Model call error ({e}); falling back"
              " to deterministic placeholder mapping."
          )
          break

    first_key = (
        list(templates_prompt_schema.keys())[0]
        if templates_prompt_schema
        else (
            list(layout_data["templates"].keys())[0]
            if layout_data.get("templates")
            else "1"
        )
    )
    fallback_spec = layout_data.get("templates", {}).get(first_key, {}) or {}
    fallback_placeholders = self._deterministic_map_placeholders(
        slide_title, slide_content, fallback_spec
    )
    response_json = self.extract_json(
        response,
        default={"template": first_key, "placeholders": fallback_placeholders},
    )
    if isinstance(response_json, list) and len(response_json) > 0:
      response_json = response_json[0]
    if not isinstance(response_json, dict) or not response_json.get(
        "placeholders"
    ):
      response_json = {
          "template": first_key,
          "placeholders": fallback_placeholders,
      }

    # 3. Resolve template coordinates
    template_num = str(response_json.get("template"))
    coords = template_coords.get(template_num)

    if not coords:
      print(
          f"[TemplateMapperWorkflow] Warning: Template {template_num} not found"
          f" in metadata. Falling back to {first_key}."
      )
      template_num = first_key
      coords = template_coords.get(first_key)

    if coords:
      slide_id = coords["slide_id"]
      deck_id = coords["deck_id"]
    else:
      slide_id = ""
      deck_id = ""

    # Failsafe post-processing deduplication if LLM hallucinated a used template not in templates_prompt_schema
    if slide_id and slide_id in used_slide_ids:
      print(
          f"[TemplateMapperWorkflow] Failsafe: Slide ID '{slide_id}' already"
          " used. Finding structural alternative..."
      )
      target_schema_keys = set(
          layout_data["templates"].get(template_num, {}).keys()
      )

      for alt_num, alt_placeholders in candidate_pool.items():
        alt_coords = template_coords.get(alt_num)
        if (
            alt_coords
            and alt_coords["slide_id"] not in used_slide_ids
            and set(alt_placeholders.keys()) == target_schema_keys
        ):
          print(
              "[TemplateMapperWorkflow] Failsafe alternative found: Template"
              f" '{alt_num}'"
          )
          template_num = str(alt_num)
          coords = alt_coords
          slide_id = coords["slide_id"]
          deck_id = coords["deck_id"]
          break
      else:
        for alt_num, alt_placeholders in layout_data["templates"].items():
          alt_coords = template_coords.get(alt_num)
          if (
              alt_coords
              and alt_coords["slide_id"] not in used_slide_ids
              and set(alt_placeholders.keys()) == target_schema_keys
          ):
            print(
                "[TemplateMapperWorkflow] Failsafe alternative found: Template"
                f" '{alt_num}'"
            )
            template_num = str(alt_num)
            coords = alt_coords
            slide_id = coords["slide_id"]
            deck_id = coords["deck_id"]
            break

    temp_url = (
        f"https://docs.google.com/presentation/d/{deck_id}/edit#slide=id.{slide_id}"
        if slide_id
        else None
    )

    # Deterministically enforce placeholder character limits against the chosen template spec
    raw_placeholders = response_json.get("placeholders", {}) or {}
    chosen_spec = layout_data.get("templates", {}).get(template_num, {}) or {}
    enforced_placeholders = self._enforce_placeholder_char_limits(
        raw_placeholders, chosen_spec
    )
    response_json["placeholders"] = enforced_placeholders

    # Dynamically load Speaker Notes guidelines and generate notes
    from agents.skill_loader import load_skill_instructions

    notes_instructions = load_skill_instructions("speaker_notes")

    speaker_notes = ""
    if notes_instructions:
      print(
          "[TemplateMapperWorkflow] Dynamically loaded 'speaker_notes'"
          " guidelines. Generating notes..."
      )
      notes_prompt = f"""Generate speaker notes for this slide following these guidelines.
            
            Guidelines:
            {notes_instructions}
            
            Slide Data:
            Title: {slide_title}
            Content: {json.dumps(response_json.get("placeholders", {}))}
            """
      try:
        notes_response = client.models.generate_content(
            model=self.gemini_model, contents=notes_prompt
        )
        raw_notes = notes_response.text.strip() if notes_response.text else ""
        speaker_notes = self._clean_speaker_notes(raw_notes)
      except Exception as notes_err:  # pylint: disable=broad-exception-caught
        print(
            "[TemplateMapperWorkflow] Speaker notes LLM fallback triggered"
            f" ({notes_err})."
        )
        speaker_notes = ""

    return {
        "template": template_num,
        "temp_url": temp_url,
        "slide_id": slide_id,
        "placeholders": response_json.get("placeholders", {}),
        "speaker_notes": speaker_notes,
    }

  def _deterministic_map_placeholders(
      self, slide_title: str, slide_content: str, template_spec: dict
  ) -> dict:
    """Deterministically populates template placeholders from slide_title and slide_content bullets when LLM quota is unavailable."""
    if not isinstance(template_spec, dict):
      return {"title": str(slide_title or "").strip()[:62]}
    out = {}
    clean_title = str(slide_title or "Advancing enterprise transformation").strip()
    lines = [
        re.sub(r"^[\s\*\-•\d\.\)]+", "", ln).strip()
        for ln in str(slide_content or "").splitlines()
        if re.sub(r"^[\s\*\-•\d\.\)]+", "", ln).strip()
    ]
    parsed_cards = []
    for ln in lines:
      if ":" in ln:
        h, b = ln.split(":", 1)
        parsed_cards.append((h.strip(), b.strip()))
      else:
        words = ln.split()
        parsed_cards.append((" ".join(words[:3]), ln))
    if not parsed_cards:
      parsed_cards = [
          (
              "Strategic Alignment",
              (
                  "Unifying multimodal enterprise context and governed AI"
                  " workflows to accelerate execution velocity."
              ),
          ),
          (
              "Architectural Scale",
              (
                  "Connecting core data foundations with Gemini Enterprise and"
                  " Google Cloud Agent Engine at global scale."
              ),
          ),
          (
              "Measurable Impact",
              (
                  "Driving sustained productivity gains, lower operational"
                  " friction, and verifiable business ROI."
              ),
          ),
      ]

    for key in template_spec.keys():
      kl = str(key).lower()
      if kl in ("title", "use_case_title"):
        out[key] = clean_title[:62]
      elif kl == "subtitle":
        out[key] = parsed_cards[0][1][:110]
      elif re.match(r"^header\d+$", kl):
        idx = int(re.findall(r"\d+", kl)[0]) - 1
        card = parsed_cards[idx % len(parsed_cards)]
        out[key] = card[0][:28]
      elif re.match(r"^header\d+_content$", kl):
        idx = int(re.findall(r"\d+", kl)[0]) - 1
        card = parsed_cards[idx % len(parsed_cards)]
        out[key] = card[1][:160]
      elif re.match(r"^item\d+$", kl):
        idx = int(re.findall(r"\d+", kl)[0]) - 1
        card = parsed_cards[idx % len(parsed_cards)]
        out[key] = f"{card[0]}: {card[1]}"[:160]
      else:
        out[key] = parsed_cards[0][1][:120]
    return out

  def _enforce_placeholder_char_limits(
      self, placeholders: dict, template_spec: dict
  ) -> dict:
    """Ensures mapped placeholder text fits within the template's character bounds without amputating single-sentence card bodies."""
    if not isinstance(placeholders, dict):
      return {}
    cleaned = {}
    for k, val in placeholders.items():
      text = str(val or "").strip()
      if not text:
        cleaned[k] = ""
        continue
      spec_str = str((template_spec or {}).get(k) or "")
      nums = [int(x) for x in re.findall(r"\d+", spec_str)]
      min_chars = min(nums) if nums else 0
      max_chars = max(nums) if nums else 0
      kl = k.lower()
      is_header_or_title = (
          kl in ("title", "subtitle", "use_case_title")
          or bool(re.match(r"^(header|subtitle)\d+$", kl))
          or (max_chars > 0 and max_chars <= 38)
      )
      if max_chars > 0:
        if is_header_or_title:
          effective_max = max(12, max_chars)
          tolerance = 1.05 if max_chars <= 38 else 1.10
        elif max_chars <= 85:
          # Compact grid cards (e.g. Template 5, Template 8 with 60-80 chars)
          effective_max = max_chars
          tolerance = 1.02
        else:
          effective_max = max(112, max_chars)
          tolerance = 1.12
        if len(text) > int(effective_max * tolerance):
          try:
            from agents.workflows.text_transformer_workflow import TextTransformerWorkflow

            trim_wf = TextTransformerWorkflow(self.config)
            text = trim_wf._trim_to_char_limit(
                text, effective_max, is_title_or_header=is_header_or_title
            )
          except Exception:
            if len(text) > effective_max:
              cut = text[:effective_max].rsplit(" ", 1)[0].rstrip(" ,;:-")
              text = cut if is_header_or_title else (cut + ".")
        elif (
            not is_header_or_title
            and min_chars >= 105
            and 35 <= len(text) < 108
        ):
          suffix = (
              " to accelerate enterprise scale and measurable operational"
              " impact."
          )
          base = text.rstrip(" .!?;")
          if len(base) + len(suffix) <= effective_max:
            text = base + suffix
          else:
            short_sfx = " for measurable operational impact."
            if len(base) + len(short_sfx) >= 106:
              text = base + short_sfx
      cleaned[k] = text
    return cleaned

  def _clean_speaker_notes(self, raw_notes: str) -> str:
    """Cleans up raw model output to ensure plain, professional speaker notes."""
    if not raw_notes:
      return ""
    text = raw_notes.strip()
    # Strip markdown code blocks
    if text.startswith("```"):
      lines = text.splitlines()
      if len(lines) >= 2:
        start_idx = 1
        end_idx = len(lines) - 1 if lines[-1].strip().startswith("```") else len(lines)
        text = "\n".join(lines[start_idx:end_idx]).strip()

    # Strip internal labels like "Slide X:" or "Framework Section:"
    cleaned_lines = []
    for line in text.splitlines():
      line_str = line.strip()
      if re.match(r"^slide\s*(x|\d+)\s*:", line_str, re.IGNORECASE):
        continue
      if re.match(r"^framework\s*section\s*:", line_str, re.IGNORECASE):
        continue
      cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()
