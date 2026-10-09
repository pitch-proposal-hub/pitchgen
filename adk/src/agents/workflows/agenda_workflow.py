import json
import os
from agents.workflows.base_workflow import BaseWorkflow
from google import genai
from google.genai import types


class AgendaWorkflow(BaseWorkflow):

  def __init__(self, config):
    super().__init__(
        'AgendaWorkflow',
        'Converts a structured outline into presentation agendas.',
    )
    self.config = config
    self.project_id = config['default']['project_name']
    self.gemini_model = config['default']['gemini_model_1']

  def execute(self, outline_data):
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'prompt_templates',
        'outlineToAgendas.txt',
    )
    with open(prompt_path, 'r') as f:
      agendas_prompt = f.read()

    client = genai.Client(
        vertexai=True, project=self.project_id, location='global'
    )

    industry = outline_data.get('industry', '')
    required_sales_plays = outline_data.get('required_sales_plays', [])
    aud = outline_data.get('audience', [])
    audience_str = ', '.join(aud) if isinstance(aud, list) else str(aud or '')

    from agents.workflows.outline_workflow import OutlineWorkflow

    is_s0_discovery = bool(
        outline_data.get('is_s0_customer_discovery')
    ) or OutlineWorkflow.is_s0_customer_discovery_mode(
        outline_data.get('win_cycle') or outline_data.get('sales_stage', ''),
        outline_data.get('user_request', ''),
    )

    cust_name = (
        outline_data.get('customer_name')
        or outline_data.get('customer', '')
        or 'Customer'
    )

    agendas_inp = {
        'customer': cust_name,
        'audience': audience_str,
        'industry': industry,
        'deck_length': (
            outline_data.get('deck_length')
            or outline_data.get('request_type')
            or 'Standard'
        ),
        'outline_items': outline_data.get('outline', []),
        'required_sales_plays': required_sales_plays,
    }

    agendas_prompt = (
        f'{agendas_prompt}\n\n### CUSTOMER-CENTRIC AGENDA GROUPING MANDATE:\n-'
        ' Group `outline_items` IN EXACT SEQUENCE into 4 to 6 cohesive,'
        f' executive agenda sections tailored to {cust_name}.\n- Every agenda'
        ' `title` MUST be crisp (<= 42 characters), consultative, and directly'
        ' describe the exact outline `parts` grouped inside it so that every'
        ' slide generated or retrieved for that section clearly fits its'
        ' Agenda heading.\n- Keep customer context / strategic priorities /'
        ' operational bottlenecks in the opening section(s), solution / sales'
        ' play pillars in the middle section(s), customer proof points /'
        ' architecture validation in the penultimate section, and joint'
        ' discovery workshop / roadmap / next steps in the final section.'
    )

    try:
      response = client.models.generate_content(
          model=self.gemini_model,
          contents=[agendas_prompt, json.dumps(agendas_inp), '\n[output]\n'],
          config=types.GenerateContentConfig(
              system_instruction='Please provide output in json format.',
              response_mime_type='application/json',
              temperature=0,
          ),
      )
      agenda_struct = self.extract_json(response, default={})
      raw_agendas = agenda_struct.get('agendas', {})
      reconciled = self.reconcile_agendas_with_deck_length(
          raw_agendas, agendas_inp.get('deck_length', 'Standard')
      )
      if isinstance(reconciled, dict):
        stage_up = (
            str(
                agendas_inp.get('sales_stage')
                or agendas_inp.get('win_cycle')
                or ''
            )
            .strip()
            .upper()
        )
        is_s0_stage = stage_up == 'S0'
        for s_idx, (s_k, s_val) in enumerate(reconciled.items(), start=1):
          if not isinstance(s_val, dict):
            continue
          t_comb = (
              f"{s_val.get('title', '')}"
              f" {' '.join(str(p) for p in (s_val.get('parts') or []))}".lower()
          )
          is_solution_or_proof = any(
              kw in t_comb
              for kw in (
                  'customer reference',
                  'case stud',
                  'proof point',
                  'peer outcome',
                  'proven result',
              )
          )
          is_explicit_discovery_or_footprint = any(
              kw in t_comb
              for kw in (
                  'discovery question',
                  'executive question',
                  'prioritized question',
                  'opportunity hypothes',
                  'opportunity matrix',
                  'technology footprint',
                  'tech footprint',
                  'current footprint',
                  'customer research',
              )
          )
          is_s0_research_opener = (
              is_s0_stage
              and s_idx == 1
              and any(
                  kw in t_comb
                  for kw in (
                      'strategic initiative',
                      'strategic priorit',
                      'operational bottleneck',
                      'joint value discovery',
                  )
              )
          )
          if not is_solution_or_proof and (
              is_explicit_discovery_or_footprint or is_s0_research_opener
          ):
            s_val['bespoke_research_focus'] = True
      return reconciled
    except Exception as e:
      print(f'[AgendaWorkflow] Error generating agendas: {e}')
      return {}

  @staticmethod
  def reconcile_agendas_with_deck_length(
      agendas: dict,
      deck_length: str = 'Standard',
      preserve_explicit_counts: bool = False,
  ) -> dict:
    """Aligns each agenda section's slide_count so the sum of content slides across sections matches deck_length (excluding Cover, Agenda, and Closing)."""
    if not isinstance(agendas, dict) or not agendas:
      return agendas

    try:
      sorted_keys = sorted(
          agendas.keys(), key=lambda x: int(x) if str(x).isdigit() else str(x)
      )
    except Exception:
      sorted_keys = list(agendas.keys())

    n_sec = len(sorted_keys)
    if n_sec == 0:
      return agendas

    if preserve_explicit_counts:
      for k in sorted_keys:
        if isinstance(agendas[k], dict):
          agendas[k]['slide_count'] = max(
              1,
              int(
                  agendas[k].get('slide_count') or agendas[k].get('slides') or 1
              ),
          )
      return agendas

    dl_low = str(deck_length or 'Standard').lower()
    is_brief = any(
        k in dl_low for k in ('brief', 'short', 'concise', '4-6', '5-8')
    )
    is_comp = any(k in dl_low for k in ('comprehensive', '15-20', 'deep'))

    # Note: deck_length refers to CONTENT slides across the agenda sections (excluding Title Cover, Agenda, and Closing).
    if is_brief:
      # Brief (4-6 content slides): 1 content slide per section across 4-6 sections
      # (all subtopics in a section are covered together as cards on 1 multi-pillar slide).
      counts = {k: 1 for k in sorted_keys}
      total_c = sum(counts.values())
      # If fewer than 4 sections exist, allocate +1 slide to the densest middle section to reach 4 content slides
      while total_c < 4 and n_sec > 0:
        best_k = max(
            sorted_keys,
            key=lambda k: len((agendas[k] or {}).get('parts', [])) - counts[k],
        )
        counts[best_k] += 1
        total_c += 1
      for k in sorted_keys:
        if isinstance(agendas[k], dict):
          agendas[k]['slide_count'] = counts[k]
      return agendas

    if is_comp:
      # Comprehensive (15-20 content slides): 15 to 18 content slides across sections
      counts = {}
      for k in sorted_keys:
        sec = agendas[k] if isinstance(agendas[k], dict) else {}
        parts = sec.get('parts') or sec.get('subtopics') or []
        counts[k] = max(1, len(parts) if isinstance(parts, list) else 3)
      total_c = sum(counts.values())
      # Ensure at least 15 content slides
      while total_c < 15 and n_sec > 0:
        best_k = max(
            sorted_keys,
            key=lambda k: (
                len((agendas[k] or {}).get('parts', [])) - counts[k],
                1 if (1 < (sorted_keys.index(k) + 1) < n_sec) else 0,
                -counts[k],
            ),
        )
        counts[best_k] += 1
        total_c += 1
      # Cap at 20 content slides
      while total_c > 20:
        best_k = max(sorted_keys, key=lambda k: counts[k])
        if counts[best_k] <= 1:
          break
        counts[best_k] -= 1
        total_c -= 1
      for k in sorted_keys:
        if isinstance(agendas[k], dict):
          agendas[k]['slide_count'] = counts[k]
      return agendas

    # Standard (8-12 content slides): target 10 content slides across sections (squarely in the middle of 8-12)
    target_content_slides = min(11, max(8, 10))
    counts = {k: 1 for k in sorted_keys}
    extra_budget = max(0, target_content_slides - n_sec)

    if extra_budget > 0:
      scored_keys = []
      for idx, k in enumerate(sorted_keys, start=1):
        sec = agendas[k] if isinstance(agendas[k], dict) else {}
        parts = sec.get('parts') or sec.get('subtopics') or []
        n_parts = len(parts) if isinstance(parts, list) else 1
        if n_parts <= 1:
          continue
        sec_text = (
            f"{sec.get('title', '')} {' '.join(str(p) for p in parts)}".lower()
        )
        has_case_study = any(
            w in sec_text
            for w in (
                'customer impact',
                'proven results',
                'case stud',
                'customer success',
                'proof point',
            )
        )
        has_roadmap = any(
            w in sec_text
            for w in (
                'roadmap',
                'next step',
                'transformation journey',
                'milestone',
                'timeline',
            )
        )
        score = n_parts * 20
        # Highest priority: section that combines Customer Case Studies + Next Steps/Roadmap
        if has_case_study and has_roadmap:
          score += 100
        # Second priority: core Why Google / Solution Architecture middle sections
        elif 1 < idx < n_sec:
          score += 50
        scored_keys.append((score, k, n_parts))

      scored_keys.sort(key=lambda x: x[0], reverse=True)
      # Pass 1: bring sections with 2+ subtopics up to 2 slides
      for _, k, n_parts in scored_keys:
        if extra_budget <= 0:
          break
        if counts[k] < min(2, n_parts):
          counts[k] += 1
          extra_budget -= 1
      # Pass 2: if budget remains, allocate +1 slide to the highest-priority 3+ subtopic section(s)
      for _, k, n_parts in scored_keys:
        if extra_budget <= 0:
          break
        if counts[k] < n_parts:
          counts[k] += 1
          extra_budget -= 1

    for k in sorted_keys:
      if isinstance(agendas[k], dict):
        agendas[k]['slide_count'] = counts[k]
    return agendas
