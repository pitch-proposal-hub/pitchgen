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
from agents.workflows.developer_knowledge_workflow import DeveloperKnowledgeWorkflow


class ContentSynthesisWorkflow(BaseWorkflow):
  """Skill for synthesizing slide presentation copy using Gemini models."""

  def __init__(self, config):
    super().__init__(
        "ContentSynthesisWorkflow", "Synthesizes net-new content for slide decks."
    )
    self.config = config
    self.project_id = config["default"]["project_name"]
    self.gemini_model = config["default"].get(
        "gemini_model", config["default"].get("gemini_model_1", "gemini-3.8-flash")
    )
    self.gemini_model_fallback = config["default"].get(
        "gemini_model_1", "gemini-3.5-flash-lite"
    )
    self.dk_workflow = DeveloperKnowledgeWorkflow(config)

  def find_matching_use_case(
      self, agenda_item: str, context: dict | None = None
  ) -> dict[str, any] | None:
    """Pre-matches the agenda item to the use case databases in Python, strictly scoped to the target industry vertical."""
    target_industry = ""
    if context and isinstance(context, dict):
      target_industry = (context.get("industry") or "").lower()

    databases = []
    if any(k in target_industry for k in ("retail", "consumer", "cpg", "grocery", "fashion")):
      databases.extend([
          "retail/capture_unified_and_agentic_commerce_grwoth.json",
          "retail/create_the_connected_store.json",
          "retail/drive_sustainable_and_efficient_operations.json",
          "retail/leverage_ai_to_transform_data_into_value.json",
      ])
    elif any(k in target_industry for k in ("energy", "power", "utility", "utilities")):
      databases.extend([
          "power_energy/strategic_foresight.json",
          "power_energy/operational_excellence.json",
          "power_energy/robust_core.json",
      ])

    if not databases:
      return None

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

  @staticmethod
  def partition_topics_across_slides(
      topics: list[str], num_slides: int
  ) -> list[list[str]]:
    """Partitions M outline subtopics sequentially across N slides so every subtopic is covered."""
    cleaned = [str(t).strip() for t in topics or [] if str(t).strip()]
    n = max(1, int(num_slides or 1))
    if not cleaned:
      return [[""] for _ in range(n)]
    if n == 1:
      return [cleaned]
    if len(cleaned) <= n:
      groups = [[t] for t in cleaned]
      while len(groups) < n:
        groups.append([cleaned[-1]])
      return groups
    # Distribute len(cleaned) items sequentially across n groups (e.g. 3 items across 2 slides -> [2, 1])
    groups = []
    base_size = len(cleaned) // n
    rem = len(cleaned) % n
    cursor = 0
    for i in range(n):
      sz = base_size + (1 if i < rem else 0)
      groups.append(cleaned[cursor : cursor + sz])
      cursor += sz
    return groups

  @staticmethod
  def is_customer_centric_bespoke_section(
      sec_key: str, agenda_obj: dict, sec_parts: list
  ) -> bool:
    """Identifies customer-centric / bespoke research sections in smart_hybrid."""
    if not isinstance(agenda_obj, dict):
      return False
    if bool(agenda_obj.get("bespoke_research_focus")):
      return True
    t_low = str(agenda_obj.get("title", "")).lower()
    p_low = " ".join(str(p) for p in sec_parts or []).lower()
    comb = f"{t_low} {p_low}"
    # Do not treat pure Customer Reference / Proof Point sections as bespoke-only
    if any(
        kw in t_low
        for kw in (
            "customer success",
            "case stud",
            "proof point",
            "customer reference",
            "peer outcome",
        )
    ):
      return False
    return any(
        kw in comb
        for kw in (
            "discovery question",
            "executive question",
            "prioritized question",
            "opportunity hypothes",
            "opportunity matrix",
            "technology footprint",
            "tech footprint",
            "current footprint",
            "customer research",
            "bottleneck",
            "operational bottleneck",
            "pain point",
            "workshop",
            "discovery workshop",
            "joint value",
            "pilot charter",
            "charter",
        )
    )

  def generate_contents(
      self,
      client,
      context_text,
      agenda_item,
      num_slides,
      context: dict | None = None,
      topics_to_cover: list[str] | None = None,
  ):
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

    # Proactively pre-match and load detailed Use Case Context grounding only when matching industry!
    use_case = self.find_matching_use_case(agenda_item, context)
    grounding_context = ""
    if use_case:
      print(
          f"[ContentSynthesisWorkflow] Proactively matched agenda '{agenda_item}'"
          f" to industry use case: '{use_case.get('use_case_title')}'"
      )
      grounding_context = (
          "\n\n### Official Google Cloud Grounding Use Case"
          f" Details:\n{json.dumps(use_case, indent=2)}"
      )

    # Dynamically query Developer Knowledge API for live official Google Cloud documentation
    dk_grounding = ""
    dk_query = ""
    if context:
      sol = context.get("solution") or context.get("solutions") or ""
      prod = context.get("product") or context.get("products") or ""
      play = context.get("salesPlay") or context.get("sales_play") or ""
      search_parts = []
      for item in (sol, prod, play):
        if item:
          if isinstance(item, list):
            search_parts.extend([str(x) for x in item if x])
          else:
            search_parts.append(str(item))
      if search_parts:
        dk_query = f"Google Cloud {' '.join(search_parts[:2])} architecture overview"
    if not dk_query and any(k in agenda_item.lower() for k in ("ai", "agent", "model", "platform", "media", "data", "infrastructure")):
      dk_query = f"Google Cloud {agenda_item} overview"

    if dk_query and hasattr(self, "dk_workflow"):
      try:
        dk_res = self.dk_workflow.execute(dk_query)
        if dk_res and not dk_res.startswith("Failed to retrieve"):
          print(f"[ContentSynthesisWorkflow] Dynamically grounded with Developer Knowledge ({len(dk_res)} chars) for query: '{dk_query}'")
          dk_grounding = f"\n\n### Official Google Cloud Live Documentation (Developer Knowledge Grounding):\n{dk_res}"
      except Exception as dke:
        print(f"[ContentSynthesisWorkflow] Notice: Developer Knowledge lookup skipped: {dke}")

    topics_list = [
        str(t).strip() for t in topics_to_cover or [] if str(t).strip()
    ]
    slide_groups = self.partition_topics_across_slides(topics_list, num_slides)
    alloc_lines = []
    for s_idx, grp in enumerate(slide_groups, start=1):
      clean_grp = [g for g in grp if g]
      if len(clean_grp) > 1:
        sub_bullets = "\n".join(
            f"            ({i}) {sub}"
            for i, sub in enumerate(clean_grp, start=1)
        )
        alloc_lines.append(
            f"        - Slide {s_idx} covers {len(clean_grp)} outline subtopics"
            f" together on this single slide:\n{sub_bullets}\n"
            f"          -> CRITICAL MULTI-TOPIC RULE FOR SLIDE {s_idx}: You"
            f" MUST provide at least {max(3, len(clean_grp))} structured"
            " cards/bullet points on this slide, dedicating at least 1 full"
            f" card (Header + Body) to EACH of the {len(clean_grp)} subtopics"
            " above. NEVER omit any subtopic and NEVER reduce a subtopic to"
            " only the slide title!"
        )
      elif len(clean_grp) == 1:
        alloc_lines.append(
            f"        - Slide {s_idx} exclusively covers this outline subtopic"
            f" in depth: {clean_grp[0]}\n          -> Provide 3 to 5 structured"
            " cards/bullet points unpacking its key dimensions, architecture,"
            " and business outcomes."
        )
      else:
        alloc_lines.append(
            f"        - Slide {s_idx} covers: {agenda_item} (3 to 5 structured"
            " cards/bullet points)."
        )

    slide_allocation_instructions = (
        "\n        COMPLETE OUTLINE COVERAGE & SLIDE ALLOCATION MANDATE"
        " (100% OF SUBTOPICS MUST BE COVERED):\n"
        f"        You MUST generate {num_slides} slide(s) following this exact"
        " topic-to-slide plan:\n"
        + "\n".join(alloc_lines)
    )

    prompt = f"""Use the following text to create {num_slides} distinct slide(s) for the agenda section: {agenda_item}
        Large Text: {context_text}
        {grounding_context}
        {dk_grounding}
        {slide_allocation_instructions}
        
        CRITICAL FORMATTING, BREVITY & PRODUCT MANDATE:
        - STRICT AGENDA SECTION FIT & ZERO CROSS-SECTION REPETITION (NON-NEGOTIABLE):
          * Every slide generated in this call belongs EXCLUSIVELY to Agenda Section: '{agenda_item}'.
          * Its Slide Title and all Card Headers/Bodies MUST directly address '{agenda_item}' and its assigned subtopic(s) above.
          * NEVER repeat general account background, generic tech-stack introductions, or metrics that belong to other Agenda sections listed in `Full Deck Agenda Map` inside `Large Text`. If another section covers Strategic Initiatives & Tech Footprint, and THIS section covers Operational Bottlenecks or Discovery Questions or Next Steps, dive 100% into THIS section's distinct focus!
        - Slide Title: Crisp, conversational, assertive declarative thesis statement in **Sentence case** using **Subject + finite active verb + outcome** or a **clean noun/contrast phrase** (strictly 6 to 10 words, 44 to 62 characters max so it fits in 1-2 lines at 28-30pt without overlapping the subtitle below; capitalize only the first word and proper nouns/product names/acronyms; e.g. 'Autonomous agents transform global banking workflows', 'One governed data fabric unifies 169PB on BigQuery', 'Joint governance and a phased path to production'). STRICT ANTI-GERUND & ANTI-COMMAND MANDATE (Google Brand Voice & Tone): NEVER start slide titles with '-ing' continuous/gerund verbs (e.g. NEVER start with 'Reimagining...', 'Elevating...', 'Uniting...', 'Activating...', 'Scaling...', 'Orchestrating...', 'Establishing...', or 'Unlocking...'), NEVER write bare imperative command slogans (e.g. NEVER write 'Unlock Agentic Commerce' or 'Automate Employee Workflows'), NEVER use Title Case Every Word, and NEVER append 'for [Customer]'.
        - Slide Content: For EACH slide, provide 3, 4, or 5 structured cards / bullet points (varying the number of cards across slides to match the topic's natural dimensions—e.g., 3 core pillars, 4 architectural layers/quadrants, or 5 phased milestones/capabilities), each with a crisp 2 to 4 word header (14 to 24 characters) and a substantive, outcome-driven body description.
        - SPECIALIZED SUBTOPIC FIDELITY:
          * If a slide's assigned subtopic focuses on Customer Strategic Initiatives, Technology Footprint, Account Intelligence, or Operational Hypotheses, EVERY card MUST explicitly cite the customer's actual named strategic programs, digital/retail media platforms, ERP/data infrastructure, and active AI/RAG assistants from `Account Intelligence` (never generic industry filler), connecting each concrete customer fact to a strategic opportunity or operational bottleneck.
          * If a slide's assigned subtopic focuses on Operational Bottlenecks, Structural Friction, or Cost of Inaction, EVERY card MUST diagnose a concrete operational bottleneck across the customer's business (e.g., store vs. digital inventory/loyalty fragmentation, manual catalog/associates overhead, retail media data latency, or legacy ERP batch delays) and quantify the business cost of inaction—without repeating the general company overview from Section 1.
          * If a slide's assigned subtopic focuses on Consultative Discovery Questions, Opportunity Qualification, or Opportunity Hypotheses, EVERY card MUST feature a crisp workstream header (3 to 4 words, 18 to 28 characters) and a substantive body (125 to 165 characters) that poses a direct, consultative **Executive Discovery Question ending with a question mark (`?`)** paired with the value hypothesis we aim to validate.
          * If a slide's assigned subtopic focuses on Customer Impact, Proven Results, or Case Studies, structure the cards around concrete industry reference architectures and quantified outcomes (Challenge, Architectural Solution, Measurable Business Impact).
          * If a slide's assigned subtopic focuses on Transformation Journey, Joint Value Discovery Workshop, Joint Roadmap, or Next Steps, structure the cards as phased execution milestones tailored to the customer's named systems and teams (e.g., Phase 1: Joint Discovery Sprint, Phase 2: Architecture & Pilot Validation, Phase 3: Production Scale & Governance).
          * If a slide includes a "Why Partner with Google Cloud" or Differentiation subtopic, ensure that subtopic receives its own dedicated card(s) with concrete partnership and architectural differentiators.
        - BODY LENGTH TARGET: Write each card body as 1 to 2 substantive, self-contained sentences between **18 and 26 words (125 to 165 characters)** so 2-, 3-, and 4-column tall cards fill 5 to 7 balanced lines inside the card without looking sparse or half-empty.
        - NEVER write sparse <85 character one-line fragments in tall cards, and NEVER write 250+ character walls of text.
        - DYNAMIC PRODUCT & MODEL GROUNDING: Strictly use the canonical H2 2026 Google Cloud product taxonomy from the Product Grounding guidelines and live Developer Knowledge documentation above (e.g. Gemini Enterprise as ONE product, Google Cloud Agent Engine, Agent Studio, Model Garden, Antigravity, AI Hypercomputer, Knowledge Catalog). NEVER default to legacy or retired designations (e.g. Vertex AI, Gemini Enterprise Agent Platform, GEAP, Gemini Enterprise app, Dataplex, AI Supercompute, or 'Powered by Gemini' instead of 'Built with Gemini') or deprecated model versions. Differentiate by surface (on web, on desktop, on mobile, in Antigravity, in Model Garden, via API), never by product. Dynamically verify and use active production models from the official documentation.
        
        Format for each slide (output plain labels without markdown bolding, repeating for Slide 1 .. Slide {num_slides}):
        Slide 1 Title: [Title]
        Slide 1 Content: [Content]
        """

    try:
      response = self.generate_content_with_fallback(
          client=client,
          model=self.gemini_model,
          contents=prompt,
          config=types.GenerateContentConfig(
              system_instruction=system_instruction,
              temperature=0.7,
          ),
          fallback_model=self.gemini_model_fallback,
      )
      text_out = self.extract_text(response)
      if text_out and text_out.strip():
        return text_out
    except Exception as e:  # pylint: disable=broad-exception-caught
      print(
          f"[ContentSynthesisWorkflow] Model synthesis failed ({e});"
          " synthesizing deterministic fallback slide copy."
      )
    return self._build_deterministic_fallback_slides(
        agenda_item=agenda_item,
        num_slides=num_slides,
        slide_topic_groups=slide_topic_groups,
        context=context,
    )

  def _build_deterministic_fallback_slides(
      self,
      agenda_item: str,
      num_slides: int,
      slide_topic_groups: list,
      context: dict | None = None,
  ) -> str:
    """Synthesizes structured Slide Title / Slide Content blocks deterministically when LLM quota is exhausted."""
    ctx = context if isinstance(context, dict) else {}
    sec_title = str(agenda_item or "Strategic Transformation").split(" - ")[0].strip()
    ind_str = str(ctx.get("industry") or "enterprise").strip()
    play_str = str(
        ctx.get("salesPlay")
        or ctx.get("sales_play")
        or "Gemini Enterprise and Google Cloud"
    ).strip()

    out_blocks = []
    for s_idx in range(1, max(1, int(num_slides or 1)) + 1):
      grp = (
          slide_topic_groups[s_idx - 1]
          if s_idx - 1 < len(slide_topic_groups)
          else []
      )
      clean_grp = [str(p).strip() for p in grp if str(p).strip()]
      if not clean_grp:
        clean_grp = [
            f"{sec_title}: Core Architecture & Capabilities",
            f"Faster {ind_str} operational velocity with {play_str}",
            "Enterprise Governance, Security & Measurable Business Impact",
        ]
      while len(clean_grp) < 3:
        if len(clean_grp) == 1:
          clean_grp.append(
              f"Unified {clean_grp[0][:40]} across {ind_str} workflows"
          )
        else:
          clean_grp.append(
              "Governed enterprise execution and measurable business ROI"
          )

      first_topic = clean_grp[0].split(":")[0].strip()
      raw_title = (
          f"Unified {first_topic.lower()} across {ind_str.lower()} operations"
      )
      if len(raw_title) > 60:
        raw_title = (
            f"Next-generation {sec_title.lower()} with Gemini Enterprise"[:60]
        )
      slide_title = raw_title[0].upper() + raw_title[1:]

      bullet_lines = []
      for b_idx, sub in enumerate(clean_grp[:4], start=1):
        if ":" in sub:
          hdr_part, body_part = sub.split(":", 1)
          hdr = hdr_part.strip()[:24]
          body = body_part.strip()
        else:
          words = [w for w in re.findall(r"[A-Za-z0-9&-]+", sub) if len(w) > 2]
          hdr = " ".join(words[:3]).title()[:24] or f"Strategic Pillar {b_idx}"
          body = sub.strip()
        if len(body) < 120:
          body = (
              f"{body.rstrip('.')} by unifying multimodal data, governed"
              " agentic workflows, and real-time operational intelligence"
              " on Google Cloud."
          )
        bullet_lines.append(f"- {hdr}: {body[:165].rstrip('.')}.")

      out_blocks.append(
          f"Slide {s_idx} Title: {slide_title}\nSlide {s_idx} Content:\n"
          + "\n".join(bullet_lines)
      )
    return "\n\n".join(out_blocks)

  def execute(self, global_state):
    client = genai.Client(
        vertexai=True, project=self.project_id, location="global"
    )
    agendas = global_state.agendas
    reusable_slides = global_state.reusable_slides
    context = getattr(global_state, "context", {}) or {}

    if isinstance(agendas, dict) and agendas:
      needs_reconcile = any(
          isinstance(v, dict)
          and not v.get("slide_count")
          and not v.get("slides")
          for v in agendas.values()
      )
      if needs_reconcile:
        try:
          from agents.workflows.agenda_workflow import AgendaWorkflow

          dl_str = str(
              context.get("deck_length")
              or context.get("request_type")
              or context.get("target_slide_count")
              or "Standard"
          )
          AgendaWorkflow.reconcile_agendas_with_deck_length(
              agendas, deck_length=dl_str
          )
        except Exception:
          pass

    scorer = SemanticScoringWorkflow(self.config)

    generated_content = {}

    has_any_cust_ref_in_deck = False
    total_reusable_in_deck = 0
    for sec_v in (reusable_slides or {}).values():
      if isinstance(sec_v, dict):
        s_list = sec_v.get("suggestions") or []
        total_reusable_in_deck += len(s_list)
        for s_it in s_list:
          if isinstance(s_it, dict) and (
              s_it.get("_source_datastore_key") == "cust_ref"
              or s_it.get("is_cust_ref")
              or s_it.get("is_proof_point")
              or s_it.get("slide_job") == "Proof_Points"
          ):
            has_any_cust_ref_in_deck = True
    total_target_slides = sum(
        int(a.get("slide_count") or a.get("slides") or 1)
        for a in (agendas or {}).values()
        if isinstance(a, dict)
    )

    all_agendas_lines = []
    if isinstance(agendas, dict):
      for a_k, a_v in agendas.items():
        if isinstance(a_v, dict):
          a_pts = "; ".join(str(p) for p in a_v.get("parts") or [])
          all_agendas_lines.append(
              f"  - Section {a_k} ('{a_v.get('title', '')}'): {a_pts}"
          )
    all_agendas_summary = "\n".join(all_agendas_lines)

    def _is_cust_ref_subtopic(part_str: str) -> bool:
      p_low = str(part_str or "").lower()
      return any(
          kw in p_low
          for kw in (
              "customer impact",
              "case stud",
              "customer reference",
              "proof point",
              "customer success",
              "proven retail",
              "proven enterprise",
              "reference story",
              "reference stories",
              "testimonial",
          )
      )

    def _is_customer_centric_bespoke_section(
        sec_key: str, agenda_obj: dict, sec_parts: list
    ) -> bool:
      return self.is_customer_centric_bespoke_section(
          sec_key, agenda_obj, sec_parts
      )

    def process_agenda(item):
      key, agenda = item
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

      # 1. Batch-compute embeddings for suggestion slides and parts in a single call
      sug_embs = []
      missing_sug_texts = []
      for sug in suggestions:
        if "desc_embedding" in sug and sug["desc_embedding"] is not None:
          sug_embs.append(np.array(sug["desc_embedding"]))
        else:
          text_to_embed = (
              str(sug.get("original_title", "") or "")
              + " "
              + str(sug.get("original_content", "") or "")
          ).strip()
          if text_to_embed:
            missing_sug_texts.append(text_to_embed)

      active_parts = []
      for part in parts:
        if has_any_cust_ref_in_deck and _is_cust_ref_subtopic(part):
          print(
              f"[ContentSynthesisWorkflow] Sub-point '{part}' is a Customer"
              " Reference / Proof Point topic already covered by verified"
              " Customer Reference slides in deck; skipping bespoke synthesis."
          )
          continue
        active_parts.append(part)

      part_embs_map = {}
      batch_to_embed = missing_sug_texts + active_parts
      if batch_to_embed:
        try:
          batch_vecs = scorer.get_embeddings(batch_to_embed)
          if batch_vecs and len(batch_vecs) == len(batch_to_embed):
            for s_vec in batch_vecs[: len(missing_sug_texts)]:
              sug_embs.append(s_vec)
            for p_str, p_vec in zip(
                active_parts, batch_vecs[len(missing_sug_texts) :]
            ):
              part_embs_map[p_str] = p_vec
        except Exception as emb_err:  # pylint: disable=broad-exception-caught
          print(
              f"[ContentSynthesisWorkflow] Embedding batch warning for section"
              f" {key}: {emb_err}. Proceeding with lexical gap detection."
          )

      # 2. Determine covered parts vs. gaps using pre-customization semantic similarity >= 0.52
      # (recognizing TextTransformerWorkflow customizes reusable slides to the customer's subtopic in Stage 2)
      uncovered_parts = []
      sug_token_sets = []
      for s in suggestions:
        s_txt = (
            f"{s.get('original_title', '')} {s.get('name', '')}"
            f" {s.get('original_content', '')} {s.get('desc', '')}"
        ).lower()
        sug_token_sets.append({w for w in re.findall(r"[a-z0-9]{4,}", s_txt)})

      for part in active_parts:
        part_emb = part_embs_map.get(part)
        is_covered = False
        if part_emb is not None and sug_embs:
          for sug_emb in sug_embs:
            try:
              sim = scorer.cosine_similarity(part_emb, sug_emb)
              if sim >= 0.52:
                is_covered = True
                break
            except Exception:  # pylint: disable=broad-exception-caught
              continue
        if not is_covered and sug_token_sets:
          p_tokens = {w for w in re.findall(r"[a-z0-9]{4,}", str(part).lower())}
          if any(len(p_tokens & s_toks) >= 2 for s_toks in sug_token_sets):
            is_covered = True
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

      # 3. Determine whether to synthesize net-new bespoke content based on deck_strategy
      raw_strat = str(context.get("deck_strategy", "smart_hybrid")).lower()
      if any(k in raw_strat for k in ["bespoke", "custom"]):
        strategy = "bespoke_custom"
      elif any(k in raw_strat for k in ["cloudhub"]):
        strategy = "cloudhub"
      else:
        strategy = "smart_hybrid"

      target_sec_slides = int(
          agenda.get("slide_count") or agenda.get("slides") or 1
      )
      remaining_budget = max(0, target_sec_slides - len(suggestions))

      should_synthesize = False
      topics_to_cover = []
      num_to_gen = 0

      if strategy == "bespoke_custom":
        topics_to_cover = [
            p
            for p in parts
            if not (has_any_cust_ref_in_deck and _is_cust_ref_subtopic(p))
        ]
        eff_budget = (
            remaining_budget if len(suggestions) > 0 else target_sec_slides
        )
        if topics_to_cover and eff_budget > 0:
          should_synthesize = True
          num_to_gen = max(1, min(len(topics_to_cover), eff_budget))
          print(
              "[ContentSynthesisWorkflow] Strategy 'bespoke_custom':"
              f" Synthesizing {num_to_gen} custom layout(s) for section {key}"
              f" ('{agenda.get('title')}')."
          )
      elif strategy == "cloudhub":
        if (
            total_reusable_in_deck == 0
            and len(suggestions) == 0
            and remaining_budget > 0
            and uncovered_parts
        ):
          should_synthesize = True
          topics_to_cover = list(uncovered_parts)
          num_to_gen = min(len(topics_to_cover), remaining_budget)
      else:
        # smart_hybrid: Prioritize retrieved reusable foundation & Customer Reference slides
        # (customized via TextTransformerWorkflow in Stage 2), reserving bespoke synthesis strictly for:
        # (a) Explicit Customer Discovery / Footprint / Prioritized Questions sections (is_cust_bespoke_sec),
        # (b) Remaining section slide budget (len(suggestions) < target_sec_slides) with uncovered subtopics, or
        # (c) 1 bespoke customer-researched opener in Section 1 ONLY when 100% of deck slots were filled by reusables.
        is_cust_bespoke_sec = _is_customer_centric_bespoke_section(
            str(key), agenda, parts
        )
        is_research_bespoke_anchor = (
            bool(context.get("customer_research"))
            and uncovered_parts
            and str(key) == "1"
            and len(suggestions) >= 2
            and total_reusable_in_deck >= total_target_slides
        )
        if is_cust_bespoke_sec:
          non_cr_parts = [
              p
              for p in parts
              if not (has_any_cust_ref_in_deck and _is_cust_ref_subtopic(p))
          ]
          cand_parts = (
              list(uncovered_parts) if uncovered_parts else non_cr_parts
          )
          if cand_parts:
            # Keep only verified Customer Reference slides in this section if any exist; drop generic product reusable slides
            kept_cr_sugs = [
                s
                for s in suggestions
                if isinstance(s, dict)
                and (
                    s.get("_source_datastore_key") == "cust_ref"
                    or s.get("is_cust_ref")
                    or s.get("is_proof_point")
                    or s.get("slide_job") == "Proof_Points"
                )
            ]
            if len(kept_cr_sugs) != len(suggestions):
              suggestions[:] = kept_cr_sugs
              remaining_budget = max(0, target_sec_slides - len(suggestions))
            should_synthesize = True
            topics_to_cover = list(cand_parts)
            num_to_gen = max(
                1, min(len(topics_to_cover), max(1, remaining_budget))
            )
            print(
                "[ContentSynthesisWorkflow] Strategy 'smart_hybrid'"
                " (Customer-Centric Discovery Section): Synthesizing"
                f" {num_to_gen} bespoke slide(s) for section {key}"
                f" ('{agenda.get('title')}')."
            )
        elif remaining_budget > 0 and (uncovered_parts or active_parts):
          should_synthesize = True
          topics_to_cover = list(
              uncovered_parts if uncovered_parts else active_parts
          )
          num_to_gen = min(len(topics_to_cover), remaining_budget)
        elif is_research_bespoke_anchor:
          suggestions[:] = suggestions[:-1]
          should_synthesize = True
          topics_to_cover = list(uncovered_parts[:2])
          num_to_gen = 1
          print(
              "[ContentSynthesisWorkflow] Strategy 'smart_hybrid':"
              " Synthesizing 1 customer-researched bespoke opener slide for"
              f" section {key} ('{agenda.get('title')}') while retaining"
              f" {len(suggestions)} reusable slide(s)."
          )
        else:
          if len(suggestions) > target_sec_slides:
            suggestions[:] = suggestions[:target_sec_slides]
          print(
              "[ContentSynthesisWorkflow] Strategy 'smart_hybrid': Section"
              f" {key} ('{agenda.get('title')}') has {len(suggestions)}"
              f" reusable slide(s) (target={target_sec_slides},"
              f" remaining_budget={remaining_budget}). Synthesizing 0 bespoke"
              " slides and relying on TextTransformerWorkflow."
          )

      if should_synthesize and num_to_gen > 0:
        if isinstance(agenda, dict):
          agenda["_synthesized_topics"] = list(topics_to_cover)

        print(
            f"[ContentSynthesisWorkflow] Synthesizing {num_to_gen} bespoke"
            f" slide(s) for section {key} (Strategy: '{strategy}', Target"
            f" Section Slides: {target_sec_slides}, Reusable:"
            f" {len(suggestions)}). Topics: {topics_to_cover}"
        )
        sol = context.get("solution") or context.get("solutions") or ""
        if isinstance(sol, list):
          sol = ", ".join([str(s) for s in sol if s])
        prod = context.get("product") or context.get("products") or ""
        if isinstance(prod, list):
          prod = ", ".join([str(p) for p in prod if p])
        play = context.get("salesPlay") or context.get("sales_play") or ""
        if isinstance(play, list):
          play = ", ".join([str(p) for p in play if p])
        aud = context.get("audience") or ""
        if isinstance(aud, list):
          aud = ", ".join([str(a) for a in aud if a])
        cust = context.get("customer_name") or "Enterprise Customer"
        ind = context.get("industry") or ""
        sub_ind = context.get("sub_industry") or ""
        win_cycle = (
            context.get("win_cycle") or context.get("sales_stage") or "S1"
        )
        biz = context.get("business_context") or ""
        cust_res = str(context.get("customer_research") or "")[:4500]

        context_text = (
            f"Customer: {cust}\nIndustry:"
            f" {ind}{f' / {sub_ind}' if sub_ind else ''}\nTarget Audience:"
            f" {aud or 'Executive Leadership'} (WIN Stage: {win_cycle})\nSales"
            f" Play: {play}\nTarget Solutions & Products (Must be prominently"
            f" featured): {sol} {prod}\nCustomer Business Context & Strategic"
            " Goals:"
            f" {biz}\n{f'Account Intelligence:\n{cust_res}\n' if cust_res else ''}{f'Full Deck Agenda Map (Do NOT repeat topics assigned to other sections):\n{all_agendas_summary}\n' if all_agendas_summary else ''}\nCURRENT"
            f" AGENDA SECTION TO GENERATE: Section {key} —"
            f" '{agenda.get('title')}'\nOutline Topics to cover in this section"
            f" ONLY: {', '.join(topics_to_cover)}"
        )
        synthesis_query = (
            f"{agenda.get('title')} - Product Focus: {play} {sol} {prod} -"
            f" topics: {'; '.join(topics_to_cover)}"
        )
        content = self.generate_contents(
            client,
            context_text,
            synthesis_query,
            num_to_gen,
            context=context,
            topics_to_cover=topics_to_cover,
        )
        return key, content
      else:
        print(
            "[ContentSynthesisWorkflow] Complete coverage achieved via reusable"
            f" slides! No generation needed for '{agenda.get('title')}'."
        )
        return key, None

    def safe_process_agenda(item):
      key, agenda = item
      try:
        return process_agenda(item)
      except Exception as sec_err:  # pylint: disable=broad-exception-caught
        print(
            f"[ContentSynthesisWorkflow] Error processing section {key}:"
            f" {sec_err}. Falling back to deterministic section copy if needed."
        )
        try:
          sec_parts = (
              agenda.get("parts") or [agenda.get("title", "Strategic Topic")]
              if isinstance(agenda, dict)
              else ["Strategic Topic"]
          )
          sugs = (
              reusable_slides.get(key, {}).get("suggestions", [])
              if reusable_slides
              else []
          )
          if not sugs:
            fb_copy = self._build_deterministic_fallback_slides(
                agenda_item=str(
                    agenda.get("title", "Strategic Overview")
                    if isinstance(agenda, dict)
                    else "Strategic Overview"
                ),
                num_slides=1,
                slide_topic_groups=[sec_parts[:3]],
                context=context,
            )
            return key, fb_copy
        except Exception:  # pylint: disable=broad-exception-caught
          pass
        return key, None

    from concurrent.futures import ThreadPoolExecutor

    max_workers = max(1, min(len(agendas), 3)) if agendas else 1
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
      results = list(executor.map(safe_process_agenda, agendas.items()))
      for key, content in results:
        if content:
          generated_content[key] = content

    return generated_content
