"""Content synthesis skill for generating net-new slide deck presentation content."""

import json
import re
from agents.skill_loader import load_skill_instructions
from agents.skill_loader import load_skill_json_database
from google import genai
from google.genai import types
import numpy as np
from agents.workflows.base_workflow import BaseWorkflow
from agents.workflows.semantic_scoring_workflow import SemanticScoringWorkflow


class ContentSynthesisWorkflow(BaseWorkflow):
  """Skill for synthesizing slide presentation copy using Gemini models."""

  def __init__(self, config):
    super().__init__(
        "ContentSynthesisWorkflow", "Synthesizes net-new content for slide decks."
    )
    self.config = config
    self.project_id = config["default"]["project_name"]
    self.gemini_model = config["default"].get(
        "gemini_model", config["default"].get("gemini_model_1", "gemini-3.1-flash-lite")
    )

  def find_matching_use_case(self, agenda_item: str) -> dict[str, any] | None:
    """Pre-matches the agenda item to the use case databases in Python."""
    databases = [
        "retail/capture_unified_and_agentic_commerce_grwoth.json",
        "retail/create_the_connected_store.json",
        "retail/drive_sustainable_and_efficient_operations.json",
        "retail/leverage_ai_to_transform_data_into_value.json",
        "power_energy/strategic_foresight.json",
        "power_energy/operational_excellence.json",
        "power_energy/robust_core.json",
    ]

    agenda_words = set(re.findall(r"\w+", agenda_item.lower()))

    best_match = None
    best_score = 0

    for db_name in databases:
      db = load_skill_json_database("use_case_context", db_name)
      if not db or not isinstance(db, list):
        continue

      for uc in db:
        title = uc.get("use_case_title", "")
        title_words = set(re.findall(r"\w+", title.lower()))

        overlap = agenda_words.intersection(title_words)
        score = len(overlap)

        # Extra weight for operational supply chain/connected store keywords
        if "supply" in overlap and "chain" in overlap:
          score += 2
        if "forecasting" in overlap or "demand" in overlap:
          score += 2
        if "store" in overlap or "connected" in overlap:
          score += 2
        if "analytics" in overlap or "data" in overlap:
          score += 1
        # Extra weight for Power & Energy keywords
        if "infrastructure" in overlap or "resilient" in overlap:
          score += 2
        if "forecast" in overlap or "model" in overlap:
          score += 2
        if "secure" in overlap or "scalable" in overlap:
          score += 2

        if score > best_score:
          best_score = score
          best_match = uc

    return best_match if best_score >= 1 else None

  def generate_contents(self, client, context_text, agenda_item, num_slides):
    # Dynamically load Slide Tone and Product Grounding guidelines
    tone_instructions = load_skill_instructions("slide_tone")
    product_instructions = load_skill_instructions("product_knowledge")

    system_instruction = (
        "You are an expert content generator for sales presentations."
    )
    if tone_instructions:
      print(
          "[ContentSynthesisWorkflow] Dynamically loaded and injected 'slide_tone'"
          " guidelines."
      )
      system_instruction = (
          f"{system_instruction}\n\n### Slide Tone"
          f" Guidelines:\n{tone_instructions}"
      )
    if product_instructions:
      print(
          "[ContentSynthesisWorkflow] Dynamically loaded and injected"
          " 'product_knowledge' guidelines."
      )
      system_instruction = (
          f"{system_instruction}\n\n### Product Grounding"
          f" Guidelines:\n{product_instructions}"
      )

    # Proactively pre-match and load detailed Use Case Context grounding!
    use_case = self.find_matching_use_case(agenda_item)
    grounding_context = ""
    if use_case:
      print(
          f"[ContentSynthesisWorkflow] Proactively matched agenda '{agenda_item}'"
          f" to retail use case: '{use_case.get('use_case_title')}'"
      )
      grounding_context = (
          "\n\n### Official Google Cloud Grounding Use Case"
          f" Details:\n{json.dumps(use_case, indent=2)}"
      )

    prompt = f"""Use the following text to create {num_slides} slides for the agenda item: {agenda_item}
        Large Text: {context_text}
        {grounding_context}
        
        Format for each slide:
        Slide Title: [Title]
        Slide Content: [Content]
        """

    response = client.models.generate_content(
        model=self.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7,
        ),
    )
    return response.text

  def execute(self, global_state):
    client = genai.Client(
        vertexai=True, project=self.project_id, location="global"
    )
    agendas = global_state.agendas
    reusable_slides = global_state.reusable_slides

    scorer = SemanticScoringWorkflow(self.config)

    generated_content = {}

    for key, agenda in agendas.items():
      parts = agenda.get("parts", [])
      if not parts:
        parts = [agenda.get("title", "Main Topic")]

      suggestions = (
          reusable_slides.get(key, {}).get("suggestions", [])
          if reusable_slides
          else []
      )

      print(
          f"[ContentSynthesisWorkflow] Processing {key}: '{agenda.get('title')}'"
          f" with {len(parts)} parts and {len(suggestions)} reusable"
          " suggestions."
      )

      # 1. Compute embeddings for all suggestion slides to enable coverage check
      sug_embs = []
      for sug in suggestions:
        if "desc_embedding" in sug:
          sug_embs.append(np.array(sug["desc_embedding"]))
        else:
          text_to_embed = (
              sug.get("original_title", "")
              + " "
              + sug.get("original_content", "")
          )
          if text_to_embed.strip():
            sug_embs.append(scorer.get_embeddings([text_to_embed])[0])

      # 2. Determine covered parts vs. gaps using semantic similarity >= 0.7
      uncovered_parts = []
      for part in parts:
        part_emb = scorer.get_embeddings([part])[0]
        is_covered = False
        for sug_emb in sug_embs:
          sim = scorer.cosine_similarity(part_emb, sug_emb)
          if sim >= 0.7:
            is_covered = True
            break
        if is_covered:
          print(
              f"[ContentSynthesisWorkflow] Sub-point '{part}' is COVERED by"
              " retrieved reusable slides."
          )
        else:
          print(
              f"[ContentSynthesisWorkflow] GAP DETECTED: Sub-point '{part}' has no"
              " coverage."
          )
          uncovered_parts.append(part)

      # 3. Generate net-new content strictly as a last resort to cover gaps
      if uncovered_parts:
        num_to_gen = len(uncovered_parts)
        print(
            f"[ContentSynthesisWorkflow] Generating {num_to_gen} new slides to"
            f" cover gaps: {uncovered_parts}"
        )
        context_text = (
            "Detailed context covering the following outline topics:"
            f" {', '.join(uncovered_parts)}"
        )
        synthesis_query = (
            f"{agenda.get('title')} - focus on: {'; '.join(uncovered_parts)}"
        )
        content = self.generate_contents(
            client, context_text, synthesis_query, num_to_gen
        )
        generated_content[key] = content
        print(
            f"[ContentSynthesisWorkflow] Generated {len(content)} chars of"
            " content."
        )
      else:
        print(
            "[ContentSynthesisWorkflow] Complete coverage achieved via reusable"
            f" slides! No generation needed for '{agenda.get('title')}'."
        )

    return generated_content
