import re
from agents.base_agent import BaseAgent
from agents.workflows.semantic_scoring_workflow import SemanticScoringWorkflow
from agents.workflows.slide_search_workflow import SlideSearchWorkflow


class RetrievalAgent(BaseAgent):

  def __init__(self, config):
    super().__init__(
        'RetrievalAgent',
        'Responsible for finding reusable slides and sales play insights.',
    )
    self.config = config
    self.add_skill('search', SlideSearchWorkflow(config))
    self.add_skill('score', SemanticScoringWorkflow(config))

  def _get_deck_id(self, slide):
    """Extracts deck ID from various metadata fields or URL."""
    if not isinstance(slide, dict):
      return None
    for key_name in ['deckId', 'deck_id', 'deck_ID']:
      if key_name in slide and slide[key_name]:
        return slide[key_name]
    temp_url = slide.get('temp_url', '') or slide.get('tempUrl', '')
    if temp_url:
      import re
      m = re.search(r'/presentation/d/([a-zA-Z0-9-_]+)', temp_url)
      if m:
        return m.group(1)
    return None

  def _get_slide_id(self, slide):
    """Extracts slide ID from various metadata fields or URL."""
    if not isinstance(slide, dict):
      return None
    for key_name in ['slideId', 'slide_id', 'slide_ID']:
      if key_name in slide and slide[key_name]:
        return slide[key_name]
    for key_name in ['slideIds', 'slide_ids', 'slide_IDs']:
      if key_name in slide and slide[key_name]:
        val = slide[key_name]
        if isinstance(val, list) and val:
          return val[0]
        elif isinstance(val, str) and val:
          return val
    temp_url = slide.get('temp_url', '') or slide.get('tempUrl', '')
    if temp_url:
      import re
      m = re.search(r'slide=id\.([a-zA-Z0-9-_]+)', temp_url)
      if m:
        return m.group(1)
    return None

  def _is_internal_only_slide(self, slide_data):
    """Checks whether a slide is Google internal-only or internal catalog metadata and should not be customer-facing."""
    if not isinstance(slide_data, dict):
      return False

    # Explicit booleans
    if slide_data.get("is_customer_facing") is False:
      return True
    gov = slide_data.get("governance")
    if isinstance(gov, dict):
      if gov.get("is_customer_facing") is False:
        return True
      if str(gov.get("confidentiality", "")).lower() in ["google internal only", "internal only"]:
        return True

    # Title & text checks
    title = str(slide_data.get("title", "") or slide_data.get("name", "")).lower()
    content = str(slide_data.get("content", "") or slide_data.get("text", "") or slide_data.get("desc", "")).lower()
    comb_str = f"{title} {content}"

    # Filter internal confidential flags
    if any(k in comb_str for k in [
        "internal only",
        "internal use only",
        "for internal use only",
        "google internal only",
        "confidential - for internal use only",
        "internal context: please remove",
        "please remove this slide before you present",
        "internal context:",
        "request pitchhub support",
    ]):
      return True

    return False

  def _is_case_study_slide(self, slide_data, target_customer=""):
    """Determines whether a slide is a customer reference / case study based on metadata and standard Customer Reference Library markers."""
    if not isinstance(slide_data, dict):
      return False
    if slide_data.get("_source_datastore_key") in ("cust_ref", "customer_references", "case_studies"):
      return True
    if slide_data.get("is_cust_ref") or slide_data.get("is_proof_point"):
      return True
    if str(slide_data.get("customer_references", "")).strip().lower() == "true":
      return True

    title = str(slide_data.get("title", "") or slide_data.get("name", "") or slide_data.get("original_title", "")).lower()
    content = str(
        slide_data.get("content", "")
        or slide_data.get("desc", "")
        or slide_data.get("text", "")
        or slide_data.get("original_content", "")
    ).lower()
    notes = str(
        slide_data.get("speaker_notes", "")
        or slide_data.get("speakerNotes", "")
        or slide_data.get("notes", "")
    ).lower()
    comb = f"{title} {content} {notes}"

    # Standard Google Cloud Customer Reference Library metadata & summary markers
    if any(
        k in comb
        for k in [
            "case study",
            "customer story",
            "customer success slide",
            "customer reference slide",
            "proof point",
            "success story",
            "client story",
            "exec summary:",
            "customer_reference_library",
            "https://your-sales-portal.example.com/customer-references",
        ]
    ):
      return True

    # Customer field tagged with a third-party company
    customer_field = str(slide_data.get("customer", "") or slide_data.get("customer_name", "")).strip().lower()
    target_lower = str(target_customer).strip().lower()
    if customer_field and customer_field not in ("", "google", "gcp", "generic", "agnostic", "cross-industry"):
      if not target_lower or (target_lower not in customer_field and customer_field not in target_lower):
        return True

    return False

  def classify_slide_job(self, slide_data, target_customer=""):
    """Classifies the inherent slide job of a slide based on explicit metadata or content analysis."""
    if not isinstance(slide_data, dict):
      return "Solution_Overview"

    # 1. Customer Proof Points (checked first because sales_play_reusables sometimes tags embedded customer reference slides as Solution_Overview)
    if self._is_case_study_slide(slide_data, target_customer):
      return "Proof_Points"

    title = str(slide_data.get("title", "") or slide_data.get("name", "") or slide_data.get("original_title", "")).lower()
    content = str(
        slide_data.get("content", "")
        or slide_data.get("desc", "")
        or slide_data.get("text", "")
        or slide_data.get("original_content", "")
    ).lower()
    notes = str(
        slide_data.get("speaker_notes", "") or slide_data.get("notes", "")
    ).lower()
    comb = f"{title} {content} {notes}"

    # 2. Unmistakable CVI Realization (Path_to_Prod / Commercials) & Context (Current_State) content overrides
    #    (sales_play_reusables sometimes tags 3-step 'Let's get started' or 'Editions & pricing' slides as Why_Google_Cloud or Solution_Overview)
    if any(
        k in comb
        for k in [
            "three-step guide outlining how to initiate",
            "let's get started",
            "let’s get started",
            "waiting is no longer an option",
            "identify a high-impact use case",
            "launch a pilot",
            "transformation journey",
            "next steps",
            "recommended next steps",
            "getting started",
            "30-60-90",
            "cloud adoption framework",
            "adoption roadmap",
            "migration timeline",
        ]
    ):
      return "Path_to_Prod"

    if any(
        k in comb
        for k in [
            "details the pricing and features",
            "gemini enterprise app editions",
            "business edition",
            "frontline edition",
            "committed use discount",
            "per user/month",
        ]
    ):
      return "Commercials"

    if any(
        k in comb
        for k in [
            "beginning of a fundamental shift",
            "rapidly changing the retail landscape",
            "rapidly changing the",
            "quantifying the surge",
            "adoption and impact of generative ai",
            "economic impact of ai in retail",
            "national research group",
            "agentic commerce represents",
            "sources: (1)",
            "source: (1)",
        ]
    ) or (
        "source:" in comb
        and any(m in comb for m in ("47%", "74%", "52%", "$3t", "$5t"))
    ):
      return "Market_Trends"

    if any(
        k in comb
        for k in [
            "challenge of application sprawl",
            "problem of context fragmentation",
            "limits the potential for both human and ai agents",
            "navigate an average of 11+ apps",
            "necessity for retailers to re-evaluate their data foundation",
            "re-evaluate their data foundation",
            "outlines focus areas for retail leaders",
            "outlines focus areas for ",
            "focus areas for retail leaders",
            "where retail leaders are focusing",
            "drive sustainable and efficient operations",
        ]
    ):
      return "Current_State"

    if any(
        k in comb
        for k in [
            "moving from reactive to proactive",
            "from reactive to proactive",
            "shift from reactive",
            "reactive support to proactive",
            "reactive and isolated",
            "siloed and reactive",
            "proactive and unified",
            "unified and proactive",
        ]
    ) or ("before:" in comb and "now:" in comb):
      return "Vision"

    # 3. Explicit metadata
    explicit_job = slide_data.get("slide_job") or slide_data.get("job")
    if explicit_job and isinstance(explicit_job, str) and explicit_job.strip():
      return explicit_job.strip()

    # 2. Architecture & Technical Topologies
    if any(
        k in comb
        for k in [
            "architecture",
            "reference pattern",
            "data pipeline",
            "system flow",
            "infrastructure",
            "topology",
            "vpc service controls",
            "network topology",
            "cloud interconnect",
            "gke cluster",
            "streaming architecture",
            "solution blueprint",
            "agentic data cloud",
            "borderless lakehouse",
            "ai hypercomputer",
        ]
    ):
      return "Architecture"

    # 3. Market Trends & Macro Landscape
    if any(k in comb for k in [
        "market trend", "industry trend", "macro shift", "industry focus",
        "landscape", "emerging shift", "market pressure", "industry pressure"
    ]):
      return "Market_Trends"

    # 4. Current State & Challenges
    if any(
        k in comb
        for k in [
            "status quo",
            "legacy challenge",
            "friction",
            "bottleneck",
            "data silo",
            "cost of doing nothing",
            "pain point",
            "consequence of status quo",
            "data foundation",
            "focus areas for",
        ]
    ):
      return "Current_State"

    # 5. Strategic Partnership & Joint Vision
    if any(k in comb for k in [
        "strategic partnership", "joint vision", "co-innovation", "alphabet ecosystem", "one google"
    ]):
      return "Strategic_Partnership"

    # 6. Vision & Art of the Possible
    if any(k in comb for k in [
        "art of the possible", "envisioning the future", "next-generation", "vision for"
    ]):
      return "Vision"

    # 7. Business Value & ROI
    if any(k in comb for k in [
        "business value", "economic impact", "roi", "tco", "cost savings", "payback period",
        "npv", "financial value"
    ]):
      return "Business_Value"

    # 8. Path to Production & Next Steps
    if any(k in comb for k in [
        "transformation journey", "get started", "next steps", "30-60-90", "cloud adoption framework",
        "caf", "adoption roadmap", "migration timeline"
    ]):
      return "Path_to_Prod"

    # 9. Commercials
    if any(k in comb for k in [
        "commercial", "pricing", "edp", "committed use discount", "cud", "sow", "licensing"
    ]):
      return "Commercials"

    # 10. Why Google Cloud Differentiators
    if any(k in comb for k in [
        "why google cloud", "why google", "google cloud delivers", "platform differentiator", "tpu"
    ]):
      return "Why_Google_Cloud"

    # Default to Solution Overview
    return "Solution_Overview"

  def _filter_raw_results(self, raw_results, customer_name, active_context=None):
    filtered_results = []
    agnostic_tokens = {
        "", "none", "other", "generic", "n/a", "all", "cross-industry", "agnostic",
        "customer-agnostic", "google", "google cloud", "gcp", "alphabet", "enterprise",
        "cross industry", "general", "horizontal", "solution", "product"
    }
    active_context = active_context or {}
    sp_ctx = str(active_context.get("salesPlay") or active_context.get("sales_play") or "").lower()
    sol_ctx = str(active_context.get("solution") or "").lower()
    req_ctx = str(active_context.get("user_request") or "").lower()
    closest_ind = str(
        active_context.get("closest_industry")
        or active_context.get("industry")
        or ""
    ).lower()
    anchor_deck_ids = set(active_context.get("anchor_deck_ids") or [])
    strategy_chk = (
        str(active_context.get("deck_strategy") or "").strip().lower()
    )
    is_ai_or_genmedia = any(k in sp_ctx or k in sol_ctx or k in req_ctx for k in ["genmedia", "generative media", "veo", "imagen", "media & entertainment", "agentic workplace", "scale ai", "data cloud", "security"])

    for r in raw_results:
      if self._is_internal_only_slide(r):
        print(f"[{self.name}] Excluding internal-only slide: {r.get('title') or r.get('name')}")
        continue

      deck_title = (
          r.get("deck_title") or r.get("title") or r.get("original_title") or ""
      ).lower()
      slide_name_low = str(r.get("name") or r.get("title") or "").lower()

      # 1. Language validation: reject translated/localized slides unless explicitly requested
      user_lang = str(active_context.get("language", "English")).lower()
      is_foreign_lang = False
      for lang_code, lang_name in [
          ("(portuguese)", "portug"),
          ("(pt-br)", "portug"),
          ("(espanol)", "span"),
          ("(spanish)", "span"),
          ("(ja)", "japan"),
          ("(japanese)", "japan"),
          ("(french)", "french"),
          ("(german)", "german"),
          ("(italian)", "italian"),
          ("(korean)", "korean"),
      ]:
        if (lang_code in deck_title or lang_code in slide_name_low) and lang_name not in user_lang:
          is_foreign_lang = True
          break
      if is_foreign_lang:
        print(f"[{self.name}] Excluding localized foreign slide from deck: '{deck_title}'")
        continue

      # 2. Workspace-Only Slide Strict Isolation:
      # Workspace slides should only be included if explicitly requested or Workspace play chosen.
      from agents.skill_loader import is_workspace_explicitly_requested, is_orthogonal_sales_play, is_orthogonal_industry_vertical

      sp_str_low = str(r.get("sales_play") or "").lower()
      raw_slide_desc = str(
          r.get("desc")
          or r.get("slide_summary")
          or r.get("content")
          or r.get("original_content")
          or ""
      ).lower()
      is_workspace_slide = (
          (
              any(
                  kw in deck_title
                  for kw in [
                      "workspace",
                      "google workspace",
                      "workspace ai",
                      "gws",
                  ]
              )
              and "gemini enterprise" not in deck_title
          )
          or (
              any(
                  kw in sp_str_low
                  for kw in ["workspace", "google workspace", "gws"]
              )
              and not any(
                  kw in sp_str_low
                  for kw in [
                      "gemini enterprise",
                      "ai cloud",
                      "why google",
                  ]
              )
          )
          or (
              any(
                  kw in slide_name_low or kw in raw_slide_desc
                  for kw in [
                      "google workspace",
                      "workspace with gemini",
                      "gmail, docs",
                      "docs, sheets",
                  ]
              )
              and "gemini enterprise" not in slide_name_low
              and "gemini enterprise" not in raw_slide_desc
          )
      )
      if is_workspace_slide and not is_workspace_explicitly_requested(active_context):
        print(
            f"[{self.name}] Disqualifying Workspace-only slide because Workspace was not explicitly requested: '{deck_title}'"
        )
        continue

      # 2b. Reject unfinished/broken slides containing repeated template placeholder text (e.g., 4x 'Description' boxes)
      if (
          len(re.findall(r"\bdescription\b", raw_slide_desc)) >= 3
          or "lorem ipsum" in raw_slide_desc
      ):
        print(
            f"[{self.name}] Disqualifying unfinished placeholder slide from"
            f" deck '{deck_title}': '{r.get('name') or r.get('title')}'"
        )
        continue

      # 3. Dynamic Industry Vertical Domain Compatibility Filter
      # Always enforced to prevent cross-industry leakage (e.g. Gaming deck in Tech pitch), even for anchor decks.
      conflicting_vertical = is_orthogonal_industry_vertical(
          deck_title, r, active_context
      )
      if conflicting_vertical:
        print(
            f"[{self.name}] Disqualifying incompatible vertical slide"
            f" ('{conflicting_vertical}'): '{deck_title}'"
        )
        continue

      # Segment Gating Filter:
      # Disqualify [Corporate] decks for non-Corporate customers; disqualify [SMB] decks for non-SMB customers.
      raw_seg = str(
          active_context.get("segment")
          or active_context.get("customer_segment")
          or ""
      ).strip().lower()
      if raw_seg in ("corporate", "corp", "commercial", "mid-market", "mmb"):
        norm_segment = "Corporate"
      elif raw_seg in ("smb", "small business", "startups"):
        norm_segment = "SMB"
      else:
        norm_segment = "Enterprise"

      is_corp_slide = any(k in deck_title or k in slide_name_low for k in ["[corporate]", "[corp]", "mmb_"])
      is_smb_slide = "[smb]" in deck_title or "[smb]" in slide_name_low

      if is_corp_slide and norm_segment != "Corporate":
        print(f"[{self.name}] Disqualifying Corporate slide for {norm_segment} customer: '{deck_title}'")
        continue

      if is_smb_slide and norm_segment != "SMB":
        print(f"[{self.name}] Disqualifying SMB slide for {norm_segment} customer: '{deck_title}'")
        continue

      # 4. Technical vs Business Track Alignment
      # Strictly forbid L200 / Sales Play Technical Pitch Decks in S0 and S1, or in non-technical pitches
      win_stage_chk = (
          str(
              active_context.get("win_cycle")
              or active_context.get("sales_stage")
              or ""
          )
          .strip()
          .upper()
      )
      d_id = r.get("deck_id") or r.get("deckId")
      if d_id and d_id in anchor_deck_ids and win_stage_chk not in ("S0", "S1"):
        filtered_results.append(r)
        continue

      aud_list = [str(a).lower() for a in active_context.get("audience", [])]
      active_archetype = active_context.get("presentation_archetype") or ""
      is_strictly_technical = win_stage_chk not in ("S0", "S1") and (
          win_stage_chk in ("S2", "S3", "S4")
          or strategy_chk == "cloudhub"
          or any(
              kw in a
              for a in aud_list
              for kw in (
                  "architect",
                  "engineer",
                  "developer",
                  "devops",
                  "sre",
                  "tdm",
                  "cto",
                  "platform",
                  "data",
                  "security",
                  "ciso",
                  "cio",
              )
          )
          or active_archetype
          in [
              "Technical_Solutioning_Pitch",
              "Architecture_PoC_Workshop",
              "Technical_Architecture",
              "Practitioner_Technical_Architecture",
              "PoC_Engagement_Proposal",
              "CIO_Technical_Strategy",
          ]
      )
      tech_mat_str = str(r.get("technical_maturity") or "").lower()
      is_tech_deck = (
          any(
              w in deck_title
              for w in [
                  "technical pitch",
                  "tech pitch",
                  "techpitch",
                  "architecture deep dive",
                  "l200",
                  "l300",
                  "deep dive",
              ]
          )
          or "l200" in tech_mat_str
          or "l300" in tech_mat_str
      )
      if not is_strictly_technical and is_tech_deck:
        print(
            f"[{self.name}] Excluding L200/technical pitch slide from"
            f" {win_stage_chk or 'business'} deck: '{deck_title}'"
            f" ('{r.get('name') or r.get('title')}')"
        )
        continue

      # 5. Approved Active Anchor Deck Protection:
      # If slide belongs to an approved active anchor deck, it was explicitly chosen for this pitch.
      # Once vertical and L100/L200 compatibility is verified, accept anchor slides.
      if d_id and d_id in anchor_deck_ids:
        filtered_results.append(r)
        continue

      # 6. Customer References / Proof Points Protection:
      ds_key = str(r.get("_source_datastore_key", "")).lower()
      is_cust_ref = (
          "cust-ref" in str(r.get("_source_datastore", "")).lower()
          or ds_key in ("cust_ref", "customer_references", "case_studies")
          or r.get("is_cust_ref")
          or r.get("is_proof_point")
      )
      if is_cust_ref:
        filtered_results.append(r)
        continue

      # 7. Dynamic Sales Play Isolation: automatically reject slides from unrequested sales plays
      unrequested_play = is_orthogonal_sales_play(deck_title, r, active_context)
      if unrequested_play:
        if strategy_chk == "cloudhub":
          if "_relaxed_cloudhub_pool" not in locals():
            _relaxed_cloudhub_pool = []
          _relaxed_cloudhub_pool.append(r)
        print(
            f"[{self.name}] Disqualifying unrequested sales play slide"
            f" ('{unrequested_play}'): '{deck_title}'"
        )
        continue

      # Core product, genai, architecture, solution, and sales play datastores are customer-agnostic by definition
      if any(k in ds_key for k in ("genai", "ai_agent", "product", "solution", "arch", "golden", "pitch", "silver", "sales_play")):
        filtered_results.append(r)
        continue

      slide_customer = str(r.get("customer") or r.get("customer_name") or "").lower().strip()
      target_cust_lower = str(customer_name).lower().strip()

      if not slide_customer or slide_customer in agnostic_tokens or any(tok in slide_customer for tok in ("google", "gcp", "generic", "agnostic", "cross-industry")):
        filtered_results.append(r)
        continue

      if target_cust_lower and (target_cust_lower in slide_customer or slide_customer in target_cust_lower):
        filtered_results.append(r)
      else:
        print(
            f"[{self.name}] Excluding slide '{r.get('name') or r.get('title')}'"
            f" from datastore '{r.get('_source_datastore_key')}' because it"
            f" belongs specifically to another customer: '{slide_customer}' (Target:"
            f" '{customer_name}')"
        )
    if (
        not filtered_results
        and strategy_chk == "cloudhub"
        and locals().get("_relaxed_cloudhub_pool")
    ):
      filtered_results.extend(locals()["_relaxed_cloudhub_pool"][:6])
    return filtered_results

  def _extract_section_metadata(
      self,
      agenda: dict,
      sec_context: dict,
      weights: dict = None,
  ) -> dict:
    """Extracts CVI cluster, expected slide jobs, core topics, and bound anchor deck for an agenda section."""
    import re

    if weights is None:
      weights = {
          "Current_State": 0.9,
          "Solution_Overview": 0.9,
          "Why_Google_Cloud": 0.8,
          "Strategic_Partnership": 0.8,
          "Business_Value": 0.8,
          "Proof_Points": 0.8,
          "Path_to_Prod": 0.7,
          "Architecture": 0.5,
          "Market_Trends": 0.7,
          "Commercials": 0.3,
          "Navigation": 0.8,
      }

    sec_title = (
        agenda.get("title", "")
        if isinstance(agenda, dict)
        else str(agenda or "")
    )
    sec_parts = agenda.get("parts", []) if isinstance(agenda, dict) else []
    title_low = str(sec_title or "").lower().strip()
    comb = f"{sec_title} {' '.join(sec_parts)}".lower()
    sec_idx = int(sec_context.get("_current_section_index", 99))
    total_secs = int(sec_context.get("_total_sections", 6))
    is_last_sec = sec_idx == total_secs and total_secs >= 3

    if any(
        k in title_low
        for k in [
            "case stud",
            "customer stor",
            "proof point",
            "success stor",
            "customer reference",
            "customer success",
            "client reference",
            "customer impact",
            "demonstrated customer",
            "customer outcome",
            "peer outcome",
        ]
    ):
      jobs = ["Proof_Points"]
      cvi = "Impact"
    elif any(
        k in title_low
        for k in [
            "next step",
            "roadmap",
            "timeline",
            "migration plan",
            "implementation plan",
            "path to prod",
            "getting started",
            "engagement plan",
            "action plan",
            "30-60-90",
            "chartering",
        ]
    ) or (
        is_last_sec
        and any(
            k in comb
            for k in [
                "next step",
                "roadmap",
                "timeline",
                "adoption",
                "caf",
                "migration plan",
                "implementation",
                "chartering",
            ]
        )
    ):
      jobs = ["Path_to_Prod", "Commercials"]
      cvi = "Realization"
    elif any(
        k in title_low
        for k in [
            "commercial",
            "pricing",
            "edp",
            "cud",
            "investment",
            "licensing",
        ]
    ):
      jobs = ["Commercials", "Path_to_Prod"]
      cvi = "Realization"
    elif any(
        k in title_low
        for k in [
            "market trend",
            "industry trend",
            "macro",
            "regulatory",
            "landscape",
            "disruption",
            "shift in consumer",
            "industry challenge",
            "industry context",
            "market dynamic",
            "industry shift",
            "why change",
        ]
    ):
      jobs = ["Market_Trends", "Current_State"]
      cvi = "Context"
    elif any(
        k in title_low
        for k in [
            "current state",
            "challenge",
            "bottleneck",
            "friction",
            "status quo",
            "legacy",
            "roadblock",
            "pain point",
            "problem",
        ]
    ):
      jobs = ["Current_State", "Market_Trends"]
      cvi = "Context"
    elif any(
        k in title_low
        for k in [
            "security",
            "safeguard",
            "governance",
            "trust",
            "sovereignty",
            "compliance",
            "defense",
            "partnership",
            "joint vision",
            "co-innovat",
            "alphabet",
            "one google",
            "why choose google",
            "why google",
            "differentiator",
            "platform advantage",
        ]
    ):
      jobs = ["Why_Google_Cloud", "Strategic_Partnership", "Architecture"]
      cvi = "Vision"
    elif any(
        k in title_low
        for k in [
            "business value",
            "roi",
            "tco",
            "financial",
            "payback",
            "npv",
            "economic",
            "cost sav",
            "impact",
            "value",
            "outcome",
            "result",
            "demonstrated",
        ]
    ):
      jobs = [
          "Business_Value",
          "Proof_Points",
          "Why_Google_Cloud",
          "Solution_Overview",
      ]
      cvi = "Impact"
    elif any(
        k in title_low
        for k in [
            "reference architect",
            "architect",
            "blueprint",
            "topology",
            "system design",
        ]
    ):
      jobs = ["Architecture", "Solution_Overview", "Why_Google_Cloud"]
      cvi = "Vision"
    elif sec_idx == 2 and any(
        k in title_low
        for k in [
            "envision",
            "future",
            "autonomous",
            "vision",
            "reimagin",
            "art of the possible",
            "new way",
        ]
    ):
      jobs = [
          "Why_Google_Cloud",
          "Solution_Overview",
          "Strategic_Partnership",
      ]
      cvi = "Vision"
    elif any(
        k in title_low
        for k in [
            "gemini",
            "genmedia",
            "generative media",
            "creative",
            "agentic",
            "workplace",
            "solution",
            "platform",
            "moderniz",
            "data cloud",
            "transform",
        ]
    ):
      jobs = ["Solution_Overview", "Architecture", "Why_Google_Cloud"]
      cvi = "Vision"
    elif sec_idx == 1 and total_secs >= 3:
      jobs = ["Market_Trends", "Current_State"]
      cvi = "Context"
    elif any(
        k in comb
        for k in [
            "case stud",
            "customer stor",
            "proof point",
            "success stor",
            "customer reference",
            "customer success",
            "client reference",
        ]
    ):
      jobs = ["Proof_Points"]
      cvi = "Impact"
    elif any(
        k in comb
        for k in [
            "market trend",
            "industry trend",
            "macro",
            "regulatory",
            "landscape",
            "disruption",
            "shift in consumer",
            "industry challenge",
            "industry context",
            "market dynamic",
        ]
    ):
      jobs = ["Market_Trends", "Current_State"]
      cvi = "Context"
    elif any(
        k in comb
        for k in [
            "current state",
            "challenge",
            "bottleneck",
            "friction",
            "status quo",
            "legacy",
            "roadblock",
            "pain point",
            "problem",
        ]
    ):
      jobs = ["Current_State", "Market_Trends"]
      cvi = "Context"
    elif any(
        k in comb
        for k in [
            "partnership",
            "joint vision",
            "co-innovat",
            "alphabet",
            "one google",
            "trust",
            "governance",
            "sovereignty",
            "why choose google",
        ]
    ):
      jobs = ["Strategic_Partnership", "Why_Google_Cloud"]
      cvi = "Vision"
    else:
      jobs = ["Solution_Overview", "Why_Google_Cloud"]
      cvi = "Vision"

    primary_job = jobs[0]
    if len(jobs) > 1:
      secondary = sorted(
          jobs[1:], key=lambda j: weights.get(j, 0.5), reverse=True
      )
      jobs = [primary_job] + secondary
    job_boost = float(weights.get(primary_job, 0.8))

    words = re.findall(r"\b[a-zA-Z]{3,}\b", comb)
    stop_words = {
        "why",
        "for",
        "the",
        "and",
        "our",
        "all",
        "are",
        "with",
        "from",
        "that",
        "this",
        "your",
        "using",
        "their",
        "into",
        "cloud",
        "google",
        "platform",
        "solution",
        "how",
        "what",
        "can",
        "will",
        "more",
        "out",
    }
    filtered_words = [w for w in words if w not in stop_words]
    core_topics = list(dict.fromkeys(filtered_words))[:6]

    canonical_prods = [
        "Gemini Enterprise",
        "Gemini",
        "BigQuery",
        "Looker",
        "AlloyDB",
        "Google Workspace",
        "Gemini Code Assist",
        "BeyondCorp",
        "Agent Studio",
        "ChromeOS",
        "GKE",
        "Cloud Run",
        "Spanner",
        "Pub/Sub",
        "Dataproc",
    ]
    found_prods = [p for p in canonical_prods if p.lower() in comb]

    aud_list = [str(a).lower() for a in sec_context.get("audience", [])]
    if any(a in aud_list for a in ["ceo", "cfo", "cxo", "board", "executive"]):
      maturity = "L100 (Conceptual)"
    elif "Architecture" in jobs:
      maturity = "L200 (Strategic)"
    else:
      maturity = "L100 (Conceptual)"

    sec_sales_play = None
    sec_anchor_deck_id = None
    anchor_decks = sec_context.get("anchor_decks", [])
    vertical_anchor = sec_context.get("vertical_anchor")
    if not vertical_anchor and anchor_decks:
      for a in anchor_decks:
        if (
            "why google" in str(a.get("sales_play", "")).lower()
            or "why google" in str(a.get("deck_title", "")).lower()
        ):
          vertical_anchor = a
          break

    solution_anchors = sec_context.get("solution_anchors") or [
        a
        for a in anchor_decks
        if "why google" not in str(a.get("sales_play", "")).lower()
        and "why google" not in str(a.get("deck_title", "")).lower()
    ]
    assigned_solution_ids = sec_context.get("_assigned_solution_anchor_ids")

    is_cvi_context = (
        (sec_idx == 1 and total_secs >= 3)
        or cvi == "Context"
        or any(
            k in title_low
            for k in [
                "why google",
                "industry context",
                "market trend",
                "current state",
                "executive summary",
                "industry trends",
            ]
        )
    )

    if is_cvi_context and vertical_anchor:
      sec_sales_play = vertical_anchor.get("sales_play")
      sec_anchor_deck_id = vertical_anchor.get("deck_id")

    candidate_anchors = solution_anchors

    if (
        not sec_anchor_deck_id
        and candidate_anchors
        and not is_cvi_context
        and cvi != "Realization"
    ):
      from agents.skill_loader import load_registered_sales_plays

      registered_plays = load_registered_sales_plays()
      best_sp_anchor = None
      best_sp_score = -1
      comb_tokens = set(re.findall(r"\w+", comb))

      for a in candidate_anchors:
        p_name = a.get("sales_play", "")
        p_low = p_name.lower().strip()
        d_title = a.get("deck_title", "").lower()
        a_deck_id = a.get("deck_id")

        aliases = [p_low]
        for rp in registered_plays:
          rp_name_low = rp.get("name_lower", "")
          rp_aliases = rp.get("aliases", [])
          if (
              p_low == rp_name_low
              or p_low in rp_name_low
              or rp_name_low in p_low
              or any(al == p_low or al in p_low for al in rp_aliases)
          ):
            aliases = list(set([rp_name_low] + rp_aliases))
            break
        alias_tokens = set()
        for al in aliases:
          alias_tokens.update(re.findall(r"\w+", al.lower()))
        alias_tokens.update(re.findall(r"\w+", f"{p_low} {d_title}"))
        alias_tokens -= {
            "the",
            "and",
            "for",
            "with",
            "your",
            "our",
            "pitch",
            "deck",
            "solution",
            "play",
            "lead",
            "business",
            "transformation",
            "presentation",
        }
        direct_phrase_match = any(
            al in comb
            for al in aliases
            if len(al) >= 4 and al not in ("lead", "play", "deck")
        )
        overlap_score = len(comb_tokens & alias_tokens) + (
            10 if direct_phrase_match else 0
        )
        unassigned_bonus = (
            15
            if (
                isinstance(assigned_solution_ids, (set, list))
                and a_deck_id
                and a_deck_id not in assigned_solution_ids
                and overlap_score >= 1
            )
            else 0
        )
        score = overlap_score + unassigned_bonus
        if score > best_sp_score:
          best_sp_score = score
          best_sp_anchor = a

      if best_sp_anchor and best_sp_score >= 1:
        sec_sales_play = best_sp_anchor.get("sales_play")
        sec_anchor_deck_id = best_sp_anchor.get("deck_id")
        if isinstance(assigned_solution_ids, list) and sec_anchor_deck_id:
          if sec_anchor_deck_id not in assigned_solution_ids:
            assigned_solution_ids.append(sec_anchor_deck_id)
        elif isinstance(assigned_solution_ids, set) and sec_anchor_deck_id:
          assigned_solution_ids.add(sec_anchor_deck_id)
      elif (
          isinstance(assigned_solution_ids, (set, list))
          and candidate_anchors
          and not is_cvi_context
      ):
        for a in candidate_anchors:
          if a.get("deck_id") and a.get("deck_id") not in assigned_solution_ids:
            sec_sales_play = a.get("sales_play")
            sec_anchor_deck_id = a.get("deck_id")
            if isinstance(assigned_solution_ids, list):
              assigned_solution_ids.append(sec_anchor_deck_id)
            else:
              assigned_solution_ids.add(sec_anchor_deck_id)
            break

    if not sec_anchor_deck_id:
      if (
          is_cvi_context
          or cvi == "Vision"
          or sec_idx <= 1
          or not solution_anchors
      ) and vertical_anchor:
        sec_sales_play = vertical_anchor.get("sales_play")
        sec_anchor_deck_id = vertical_anchor.get("deck_id")
      elif solution_anchors and not is_cvi_context and cvi != "Realization":
        sec_sales_play = solution_anchors[0].get("sales_play")
        sec_anchor_deck_id = solution_anchors[0].get("deck_id")
      elif vertical_anchor:
        sec_sales_play = vertical_anchor.get("sales_play")
        sec_anchor_deck_id = vertical_anchor.get("deck_id")
      else:
        for a in anchor_decks:
          p_name = a.get("sales_play", "")
          p_low = p_name.lower()
          d_title = a.get("deck_title", "").lower()
          if "why google" in p_low or "why google" in d_title:
            sec_sales_play = p_name
            sec_anchor_deck_id = a.get("deck_id")
            break

    if (
        not sec_anchor_deck_id
        and anchor_decks
        and not is_cvi_context
        and cvi != "Realization"
    ):
      sec_sales_play = anchor_decks[0].get("sales_play")
      sec_anchor_deck_id = anchor_decks[0].get("deck_id")

    return {
        "expected_slide_jobs": jobs,
        "expected_cvi_cluster": cvi,
        "expected_core_topics": core_topics,
        "expected_products": found_prods,
        "expected_maturity": maturity,
        "job_boost": job_boost,
        "section_sales_play": sec_sales_play,
        "section_anchor_deck_id": sec_anchor_deck_id,
        "vertical_anchor_deck_id": (
            vertical_anchor.get("deck_id") if vertical_anchor else None
        ),
        "anchor_deck_ids": sec_context.get("anchor_deck_ids", []),
        "closest_industry": sec_context.get("closest_industry", ""),
    }

  def retrieve_reusable_slides(self, global_state):
    """Alias for run to retrieve reusable slides into global_state."""
    return self.run(global_state)

  def run(self, global_state):
    print(f'[{self.name}] Starting asset discovery...')
    agendas = global_state.agendas
    reusable_slides = {}
    context = global_state.context or {}
    customer_name = context.get('customer_name', '')
    global_seen_slide_keys = set()

    # Load active Presentation Archetype & Slide Job Weights Matrix (8 Canonical Cloud GTM Archetypes + Legacy Aliases)
    ARCHETYPE_WEIGHTS = {
        # 1. First_Call_Discovery (S0: Qualify)
        "First_Call_Discovery": {
            "Market_Trends": 1.0,
            "Current_State": 1.0,
            "Why_Google_Cloud": 0.8,
            "Solution_Overview": 0.6,
            "Proof_Points": 0.7,
            "Strategic_Partnership": 0.5,
            "Business_Value": 0.4,
            "Architecture": 0.1,
            "Commercials": 0.0,
            "Path_to_Prod": 0.5,
            "Navigation": 0.8,
        },
        "Discovery_First_Call": {
            "Market_Trends": 1.0,
            "Current_State": 1.0,
            "Why_Google_Cloud": 0.8,
            "Solution_Overview": 0.6,
            "Proof_Points": 0.7,
            "Strategic_Partnership": 0.5,
            "Business_Value": 0.4,
            "Architecture": 0.1,
            "Commercials": 0.0,
            "Path_to_Prod": 0.5,
            "Navigation": 0.8,
        },
        # 2. Executive_Vision_Briefing (S0-S1: Inspire / Strategy / EBC)
        "Executive_Vision_Briefing": {
            "Strategic_Partnership": 1.0,
            "Market_Trends": 1.0,
            "Current_State": 0.9,
            "Why_Google_Cloud": 0.9,
            "Business_Value": 0.8,
            "Proof_Points": 0.8,
            "Solution_Overview": 0.6,
            "Path_to_Prod": 0.6,
            "Architecture": 0.1,
            "Commercials": 0.1,
            "Navigation": 0.8,
        },
        "Executive_Vision_Strategic": {
            "Strategic_Partnership": 1.0,
            "Current_State": 0.9,
            "Why_Google_Cloud": 0.8,
            "Business_Value": 0.8,
            "Solution_Overview": 0.6,
            "Proof_Points": 0.7,
            "Path_to_Prod": 0.6,
            "Architecture": 0.1,
            "Commercials": 0.2,
            "Market_Trends": 0.7,
            "Navigation": 0.8,
        },
        "Executive_Vision_Thought_Leadership": {
            "Market_Trends": 1.0,
            "Strategic_Partnership": 1.0,
            "Why_Google_Cloud": 0.9,
            "Current_State": 0.8,
            "Solution_Overview": 0.5,
            "Business_Value": 0.5,
            "Proof_Points": 0.6,
            "Architecture": 0.1,
            "Commercials": 0.0,
            "Path_to_Prod": 0.3,
            "Navigation": 0.8,
        },
        # 3. Sales_Play_Business_Pitch (S1: Position & Build L100 Business Pitch)
        "Sales_Play_Business_Pitch": {
            "Solution_Overview": 1.0,
            "Current_State": 0.9,
            "Why_Google_Cloud": 0.9,
            "Proof_Points": 0.9,
            "Business_Value": 0.8,
            "Market_Trends": 0.8,
            "Path_to_Prod": 0.7,
            "Strategic_Partnership": 0.7,
            "Architecture": 0.4,
            "Commercials": 0.2,
            "Navigation": 0.8,
        },
        "Industry_Business_Pitch": {
            "Solution_Overview": 1.0,
            "Current_State": 0.9,
            "Proof_Points": 0.9,
            "Business_Value": 0.8,
            "Market_Trends": 0.8,
            "Why_Google_Cloud": 0.7,
            "Path_to_Prod": 0.6,
            "Architecture": 0.3,
            "Strategic_Partnership": 0.6,
            "Commercials": 0.2,
            "Navigation": 0.8,
        },
        "General_Value_Pitch": {
            "Current_State": 0.9,
            "Solution_Overview": 0.9,
            "Why_Google_Cloud": 0.8,
            "Strategic_Partnership": 0.8,
            "Business_Value": 0.8,
            "Proof_Points": 0.8,
            "Path_to_Prod": 0.7,
            "Architecture": 0.5,
            "Market_Trends": 0.7,
            "Commercials": 0.3,
            "Navigation": 0.8,
        },
        # 4. Technical_Solutioning_Pitch (S2: Tech Solutioning L200 Technical Pitch)
        "Technical_Solutioning_Pitch": {
            "Architecture": 1.0,
            "Solution_Overview": 0.9,
            "Why_Google_Cloud": 0.9,
            "Path_to_Prod": 0.8,
            "Proof_Points": 0.7,
            "Current_State": 0.7,
            "Strategic_Partnership": 0.6,
            "Business_Value": 0.6,
            "Commercials": 0.2,
            "Market_Trends": 0.4,
            "Navigation": 0.8,
        },
        "CIO_Technical_Strategy": {
            "Architecture": 0.9,
            "Solution_Overview": 0.9,
            "Why_Google_Cloud": 0.9,
            "Strategic_Partnership": 0.8,
            "Path_to_Prod": 0.8,
            "Current_State": 0.7,
            "Proof_Points": 0.7,
            "Business_Value": 0.5,
            "Commercials": 0.3,
            "Market_Trends": 0.4,
            "Navigation": 0.8,
        },
        "Technical_Architecture": {
            "Architecture": 1.0,
            "Solution_Overview": 0.9,
            "Why_Google_Cloud": 0.9,
            "Path_to_Prod": 0.8,
            "Proof_Points": 0.7,
            "Current_State": 0.7,
            "Strategic_Partnership": 0.6,
            "Business_Value": 0.6,
            "Commercials": 0.2,
            "Market_Trends": 0.4,
            "Navigation": 0.8,
        },
        # 5. Architecture_PoC_Workshop (S2: Tech Validation & PoC L200/L300)
        "Architecture_PoC_Workshop": {
            "Architecture": 1.0,
            "Path_to_Prod": 1.0,
            "Solution_Overview": 0.9,
            "Why_Google_Cloud": 0.7,
            "Proof_Points": 0.6,
            "Current_State": 0.5,
            "Business_Value": 0.4,
            "Strategic_Partnership": 0.3,
            "Commercials": 0.2,
            "Market_Trends": 0.2,
            "Navigation": 0.8,
        },
        "Practitioner_Technical_Architecture": {
            "Architecture": 1.0,
            "Solution_Overview": 0.8,
            "Why_Google_Cloud": 0.7,
            "Path_to_Prod": 0.7,
            "Proof_Points": 0.5,
            "Current_State": 0.4,
            "Strategic_Partnership": 0.2,
            "Business_Value": 0.2,
            "Commercials": 0.1,
            "Market_Trends": 0.2,
            "Navigation": 0.8,
        },
        "PoC_Engagement_Proposal": {
            "Path_to_Prod": 1.0,
            "Solution_Overview": 0.9,
            "Architecture": 0.8,
            "Proof_Points": 0.7,
            "Current_State": 0.6,
            "Why_Google_Cloud": 0.6,
            "Business_Value": 0.4,
            "Strategic_Partnership": 0.4,
            "Commercials": 0.3,
            "Market_Trends": 0.2,
            "Navigation": 0.8,
        },
        # 6. Value_Case_Commercial_Proposal (S1-S3: Business Case & Propose)
        "Value_Case_Commercial_Proposal": {
            "Business_Value": 1.0,
            "Commercials": 1.0,
            "Current_State": 0.9,
            "Proof_Points": 0.9,
            "Path_to_Prod": 0.8,
            "Strategic_Partnership": 0.7,
            "Solution_Overview": 0.5,
            "Why_Google_Cloud": 0.5,
            "Market_Trends": 0.4,
            "Architecture": 0.2,
            "Navigation": 0.8,
        },
        "CFO_Business_Case": {
            "Business_Value": 1.0,
            "Current_State": 0.9,
            "Proof_Points": 0.9,
            "Commercials": 0.8,
            "Strategic_Partnership": 0.5,
            "Solution_Overview": 0.4,
            "Path_to_Prod": 0.6,
            "Why_Google_Cloud": 0.3,
            "Market_Trends": 0.5,
            "Architecture": 0.1,
            "Navigation": 0.8,
        },
        "Commercial_Proposal": {
            "Commercials": 1.0,
            "Path_to_Prod": 0.9,
            "Strategic_Partnership": 0.8,
            "Proof_Points": 0.7,
            "Business_Value": 0.7,
            "Current_State": 0.5,
            "Solution_Overview": 0.4,
            "Why_Google_Cloud": 0.4,
            "Architecture": 0.2,
            "Market_Trends": 0.2,
            "Navigation": 0.8,
        },
        # 7. Competitive_Takeout_Migration (S1-S2: Displacement & Migration)
        "Competitive_Takeout_Migration": {
            "Why_Google_Cloud": 1.0,
            "Architecture": 0.9,
            "Business_Value": 0.9,
            "Proof_Points": 0.9,
            "Path_to_Prod": 0.9,
            "Current_State": 0.8,
            "Solution_Overview": 0.8,
            "Commercials": 0.6,
            "Strategic_Partnership": 0.6,
            "Market_Trends": 0.4,
            "Navigation": 0.8,
        },
        # 8. QBR_Adoption_Expansion (S4 & S0': Mobilize & Deliver / Optimize & Grow)
        "QBR_Adoption_Expansion": {
            "Business_Value": 1.0,
            "Strategic_Partnership": 1.0,
            "Path_to_Prod": 0.9,
            "Solution_Overview": 0.8,
            "Current_State": 0.8,
            "Proof_Points": 0.7,
            "Why_Google_Cloud": 0.6,
            "Architecture": 0.5,
            "Commercials": 0.5,
            "Market_Trends": 0.5,
            "Navigation": 0.8,
        },
    }

    # Canonical Slide Job Narrative Sequences per Archetype
    ARCHETYPE_JOB_SEQUENCES = {
        "First_Call_Discovery": [
            "Market_Trends",
            "Current_State",
            "Strategic_Partnership",
            "Why_Google_Cloud",
            "Solution_Overview",
            "Proof_Points",
            "Path_to_Prod",
        ],
        "Discovery_First_Call": [
            "Market_Trends",
            "Current_State",
            "Strategic_Partnership",
            "Why_Google_Cloud",
            "Solution_Overview",
            "Proof_Points",
            "Path_to_Prod",
        ],
        "Executive_Vision_Briefing": [
            "Market_Trends",
            "Current_State",
            "Strategic_Partnership",
            "Why_Google_Cloud",
            "Solution_Overview",
            "Business_Value",
            "Proof_Points",
            "Path_to_Prod",
        ],
        "Executive_Vision_Strategic": [
            "Market_Trends",
            "Current_State",
            "Strategic_Partnership",
            "Why_Google_Cloud",
            "Solution_Overview",
            "Proof_Points",
            "Path_to_Prod",
        ],
        "Executive_Vision_Thought_Leadership": [
            "Market_Trends",
            "Current_State",
            "Strategic_Partnership",
            "Why_Google_Cloud",
            "Proof_Points",
        ],
        "Sales_Play_Business_Pitch": [
            "Market_Trends",
            "Current_State",
            "Strategic_Partnership",
            "Why_Google_Cloud",
            "Solution_Overview",
            "Architecture",
            "Business_Value",
            "Proof_Points",
            "Path_to_Prod",
        ],
        "Industry_Business_Pitch": [
            "Market_Trends",
            "Current_State",
            "Strategic_Partnership",
            "Why_Google_Cloud",
            "Solution_Overview",
            "Architecture",
            "Business_Value",
            "Proof_Points",
            "Path_to_Prod",
        ],
        "General_Value_Pitch": [
            "Market_Trends",
            "Current_State",
            "Strategic_Partnership",
            "Why_Google_Cloud",
            "Solution_Overview",
            "Architecture",
            "Business_Value",
            "Proof_Points",
            "Path_to_Prod",
        ],
        "Technical_Solutioning_Pitch": [
            "Current_State",
            "Why_Google_Cloud",
            "Solution_Overview",
            "Architecture",
            "Proof_Points",
            "Business_Value",
            "Path_to_Prod",
        ],
        "CIO_Technical_Strategy": [
            "Current_State",
            "Why_Google_Cloud",
            "Solution_Overview",
            "Architecture",
            "Strategic_Partnership",
            "Path_to_Prod",
        ],
        "Technical_Architecture": [
            "Current_State",
            "Why_Google_Cloud",
            "Solution_Overview",
            "Architecture",
            "Proof_Points",
            "Path_to_Prod",
        ],
        "Architecture_PoC_Workshop": [
            "Current_State",
            "Solution_Overview",
            "Architecture",
            "Why_Google_Cloud",
            "Proof_Points",
            "Path_to_Prod",
        ],
        "Practitioner_Technical_Architecture": [
            "Solution_Overview",
            "Architecture",
            "Why_Google_Cloud",
            "Proof_Points",
            "Path_to_Prod",
        ],
        "PoC_Engagement_Proposal": [
            "Solution_Overview",
            "Architecture",
            "Path_to_Prod",
            "Proof_Points",
            "Commercials",
        ],
        "Value_Case_Commercial_Proposal": [
            "Current_State",
            "Strategic_Partnership",
            "Solution_Overview",
            "Business_Value",
            "Proof_Points",
            "Commercials",
            "Path_to_Prod",
        ],
        "CFO_Business_Case": [
            "Current_State",
            "Business_Value",
            "Proof_Points",
            "Commercials",
            "Path_to_Prod",
        ],
        "Commercial_Proposal": [
            "Commercials",
            "Path_to_Prod",
            "Business_Value",
            "Proof_Points",
            "Strategic_Partnership",
        ],
        "Competitive_Takeout_Migration": [
            "Current_State",
            "Why_Google_Cloud",
            "Solution_Overview",
            "Architecture",
            "Business_Value",
            "Proof_Points",
            "Path_to_Prod",
        ],
        "QBR_Adoption_Expansion": [
            "Current_State",
            "Business_Value",
            "Strategic_Partnership",
            "Solution_Overview",
            "Proof_Points",
            "Path_to_Prod",
        ],
    }

    active_archetype = (
        context.get("presentation_archetype") or "Sales_Play_Business_Pitch"
    )
    archetype_job_weights = ARCHETYPE_WEIGHTS.get(
        active_archetype, ARCHETYPE_WEIGHTS["Sales_Play_Business_Pitch"]
    )
    print(
        f"[{self.name}] Active presentation archetype for slide job weighting:"
        f" '{active_archetype}'"
    )

    def resolve_section_metadata(sec_title, sec_parts, sec_context, weights):
      import re

      title_low = str(sec_title or "").lower().strip()
      comb = f"{sec_title} {' '.join(sec_parts)}".lower()
      sec_idx = int(sec_context.get("_current_section_index", 99))
      total_secs = int(sec_context.get("_total_sections", 6))
      is_last_sec = sec_idx == total_secs and total_secs >= 3

      # 1. Classify Slide Job & CVI Cluster (prioritize sec_title + section position so incidental words
      #    in sub-bullets like 'commercial execution' or 'developer adoption' never hijack the section's CVI stage)
      if any(
          k in title_low
          for k in [
              "case stud",
              "customer stor",
              "proof point",
              "success stor",
              "customer reference",
              "customer success",
              "client reference",
              "customer impact",
              "demonstrated customer",
              "customer outcome",
              "peer outcome",
          ]
      ):
        jobs = ["Proof_Points"]
        cvi = "Impact"
      elif any(
          k in title_low
          for k in [
              "next step",
              "roadmap",
              "timeline",
              "migration plan",
              "implementation plan",
              "path to prod",
              "getting started",
              "engagement plan",
              "action plan",
              "30-60-90",
              "chartering",
          ]
      ) or (
          is_last_sec
          and any(
              k in comb
              for k in [
                  "next step",
                  "roadmap",
                  "timeline",
                  "adoption",
                  "caf",
                  "migration plan",
                  "implementation",
                  "chartering",
              ]
          )
      ):
        jobs = ["Path_to_Prod", "Commercials"]
        cvi = "Realization"
      elif any(
          k in title_low
          for k in [
              "commercial",
              "pricing",
              "edp",
              "cud",
              "investment",
              "licensing",
          ]
      ):
        jobs = ["Commercials", "Path_to_Prod"]
        cvi = "Realization"
      elif any(
          k in title_low
          for k in [
              "market trend",
              "industry trend",
              "macro",
              "regulatory",
              "landscape",
              "disruption",
              "shift in consumer",
              "industry challenge",
              "industry context",
              "market dynamic",
              "industry shift",
              "why change",
          ]
      ):
        jobs = ["Market_Trends", "Current_State"]
        cvi = "Context"
      elif any(
          k in title_low
          for k in [
              "current state",
              "challenge",
              "bottleneck",
              "friction",
              "status quo",
              "legacy",
              "roadblock",
              "pain point",
              "problem",
          ]
      ):
        jobs = ["Current_State", "Market_Trends"]
        cvi = "Context"
      elif any(
          k in title_low
          for k in [
              "security",
              "safeguard",
              "governance",
              "trust",
              "sovereignty",
              "compliance",
              "defense",
              "partnership",
              "joint vision",
              "co-innovat",
              "alphabet",
              "one google",
              "why choose google",
              "why google",
              "differentiator",
              "platform advantage",
          ]
      ):
        jobs = ["Why_Google_Cloud", "Strategic_Partnership", "Architecture"]
        cvi = "Vision"
      elif any(
          k in title_low
          for k in [
              "business value",
              "roi",
              "tco",
              "financial",
              "payback",
              "npv",
              "economic",
              "cost sav",
              "impact",
              "value",
              "outcome",
              "result",
              "demonstrated",
          ]
      ):
        jobs = [
            "Business_Value",
            "Proof_Points",
            "Why_Google_Cloud",
            "Solution_Overview",
        ]
        cvi = "Impact"
      elif any(
          k in title_low
          for k in [
              "reference architect",
              "architect",
              "blueprint",
              "topology",
              "system design",
          ]
      ):
        jobs = ["Architecture", "Solution_Overview", "Why_Google_Cloud"]
        cvi = "Vision"
      elif sec_idx == 2 and any(
          k in title_low
          for k in [
              "envision",
              "future",
              "autonomous",
              "vision",
              "reimagin",
              "art of the possible",
              "new way",
          ]
      ):
        jobs = [
            "Why_Google_Cloud",
            "Solution_Overview",
            "Strategic_Partnership",
        ]
        cvi = "Vision"
      elif any(
          k in title_low
          for k in [
              "gemini",
              "genmedia",
              "generative media",
              "creative",
              "agentic",
              "workplace",
              "solution",
              "platform",
              "moderniz",
              "data cloud",
              "transform",
          ]
      ):
        jobs = ["Solution_Overview", "Architecture", "Why_Google_Cloud"]
        cvi = "Vision"
      elif sec_idx == 1 and total_secs >= 3:
        jobs = ["Market_Trends", "Current_State"]
        cvi = "Context"
      elif any(
          k in comb
          for k in [
              "case stud",
              "customer stor",
              "proof point",
              "success stor",
              "customer reference",
              "customer success",
              "client reference",
          ]
      ):
        jobs = ["Proof_Points"]
        cvi = "Impact"
      elif any(
          k in comb
          for k in [
              "market trend",
              "industry trend",
              "macro",
              "regulatory",
              "landscape",
              "disruption",
              "shift in consumer",
              "industry challenge",
              "industry context",
              "market dynamic",
          ]
      ):
        jobs = ["Market_Trends", "Current_State"]
        cvi = "Context"
      elif any(
          k in comb
          for k in [
              "current state",
              "challenge",
              "bottleneck",
              "friction",
              "status quo",
              "legacy",
              "roadblock",
              "pain point",
              "problem",
          ]
      ):
        jobs = ["Current_State", "Market_Trends"]
        cvi = "Context"
      elif any(
          k in comb
          for k in [
              "partnership",
              "joint vision",
              "co-innovat",
              "alphabet",
              "one google",
              "trust",
              "governance",
              "sovereignty",
              "why choose google",
          ]
      ):
        jobs = ["Strategic_Partnership", "Why_Google_Cloud"]
        cvi = "Vision"
      else:
        jobs = ["Solution_Overview", "Why_Google_Cloud"]
        cvi = "Vision"

      # Keep primary_job (jobs[0]) pinned for the section's CVI role, and sort secondary jobs by archetype weight
      primary_job = jobs[0]
      if len(jobs) > 1:
        secondary = sorted(
            jobs[1:], key=lambda j: weights.get(j, 0.5), reverse=True
        )
        jobs = [primary_job] + secondary
      job_boost = float(weights.get(primary_job, 0.8))

      # 2. Extract Core Topics (meaningful words from title & parts)
      words = re.findall(r"\b[a-zA-Z]{3,}\b", comb)
      stop_words = {
          "why",
          "for",
          "the",
          "and",
          "our",
          "all",
          "are",
          "with",
          "from",
          "that",
          "this",
          "your",
          "using",
          "their",
          "into",
          "cloud",
          "google",
          "platform",
          "solution",
          "how",
          "what",
          "can",
          "will",
          "more",
          "out",
      }
      filtered_words = [w for w in words if w not in stop_words]
      core_topics = list(dict.fromkeys(filtered_words))[:6]

      # 3. Canonical Products
      canonical_prods = [
          "Gemini Enterprise",
          "Gemini",
          "BigQuery",
          "Looker",
          "AlloyDB",
          "Google Workspace",
          "Gemini Code Assist",
          "BeyondCorp",
          "Agent Studio",
          "ChromeOS",
          "GKE",
          "Cloud Run",
          "Spanner",
          "Pub/Sub",
          "Dataproc",
      ]
      found_prods = [p for p in canonical_prods if p.lower() in comb]

      # 4. Technical Maturity & Audience
      aud_list = [str(a).lower() for a in sec_context.get("audience", [])]
      if any(a in aud_list for a in ["ceo", "cfo", "cxo", "board", "executive"]):
        maturity = "L100 (Conceptual)"
      elif "Architecture" in jobs:
        maturity = "L200 (Strategic)"
      else:
        maturity = "L100 (Conceptual)"

      # 5. Resolve Section-Specific Sales Play & Target Anchor Deck
      sec_sales_play = None
      sec_anchor_deck_id = None
      anchor_decks = sec_context.get("anchor_decks", [])
      vertical_anchor = sec_context.get("vertical_anchor")
      if not vertical_anchor and anchor_decks:
        for a in anchor_decks:
          if (
              "why google" in str(a.get("sales_play", "")).lower()
              or "why google" in str(a.get("deck_title", "")).lower()
          ):
            vertical_anchor = a
            break

      solution_anchors = sec_context.get("solution_anchors") or [
          a
          for a in anchor_decks
          if "why google" not in str(a.get("sales_play", "")).lower()
          and "why google" not in str(a.get("deck_title", "")).lower()
      ]
      assigned_solution_ids = sec_context.get("_assigned_solution_anchor_ids")

      # Check if this section is CVI Context / Why Google Cloud (Agenda 1 / Introduction)
      is_cvi_context = (
          (sec_idx == 1 and total_secs >= 3)
          or cvi == "Context"
          or any(
              k in title_low
              for k in [
                  "why google",
                  "industry context",
                  "market trend",
                  "current state",
                  "executive summary",
                  "industry trends",
              ]
          )
      )

      # Step 5a: If Section 1 or CVI Context agenda, directly bind to Vertical Anchor ("Why Google for <Industry>") if available
      if is_cvi_context and vertical_anchor:
        sec_sales_play = vertical_anchor.get("sales_play")
        sec_anchor_deck_id = vertical_anchor.get("deck_id")

      # Step 5b: Match section title and parts to active Sales Play anchor decks dynamically,
      # with multi-sales-play coverage balancing so all requested plays get dedicated sections
      candidate_anchors = solution_anchors

      if (
          not sec_anchor_deck_id
          and candidate_anchors
          and not is_cvi_context
          and cvi != "Realization"
      ):
        from agents.skill_loader import load_registered_sales_plays

        registered_plays = load_registered_sales_plays()
        best_sp_anchor = None
        best_sp_score = -1
        comb_tokens = set(re.findall(r"\w+", comb))

        for a in candidate_anchors:
          p_name = a.get("sales_play", "")
          p_low = p_name.lower().strip()
          d_title = a.get("deck_title", "").lower()
          a_deck_id = a.get("deck_id")

          aliases = [p_low]
          for rp in registered_plays:
            rp_name_low = rp.get("name_lower", "")
            rp_aliases = rp.get("aliases", [])
            if (
                p_low == rp_name_low
                or p_low in rp_name_low
                or rp_name_low in p_low
                or any(al == p_low or al in p_low for al in rp_aliases)
            ):
              aliases = list(set([rp_name_low] + rp_aliases))
              break
          alias_tokens = set()
          for al in aliases:
            alias_tokens.update(re.findall(r"\w+", al.lower()))
          alias_tokens.update(re.findall(r"\w+", f"{p_low} {d_title}"))
          alias_tokens -= {
              "the",
              "and",
              "for",
              "with",
              "your",
              "our",
              "pitch",
              "deck",
              "solution",
              "play",
              "lead",
              "business",
              "transformation",
              "presentation",
          }
          direct_phrase_match = any(
              al in comb
              for al in aliases
              if len(al) >= 4 and al not in ("lead", "play", "deck")
          )
          overlap_score = len(comb_tokens & alias_tokens) + (
              10 if direct_phrase_match else 0
          )
          # Multi-sales-play coverage bonus: prioritize solution anchors that have not yet been assigned to an agenda section
          unassigned_bonus = (
              15
              if (
                  isinstance(assigned_solution_ids, (set, list))
                  and a_deck_id
                  and a_deck_id not in assigned_solution_ids
                  and overlap_score >= 1
              )
              else 0
          )
          score = overlap_score + unassigned_bonus
          if score > best_sp_score:
            best_sp_score = score
            best_sp_anchor = a

        if best_sp_anchor and best_sp_score >= 1:
          sec_sales_play = best_sp_anchor.get("sales_play")
          sec_anchor_deck_id = best_sp_anchor.get("deck_id")
          if isinstance(assigned_solution_ids, list) and sec_anchor_deck_id:
            if sec_anchor_deck_id not in assigned_solution_ids:
              assigned_solution_ids.append(sec_anchor_deck_id)
          elif isinstance(assigned_solution_ids, set) and sec_anchor_deck_id:
            assigned_solution_ids.add(sec_anchor_deck_id)
        elif (
            isinstance(assigned_solution_ids, (set, list))
            and candidate_anchors
            and not is_cvi_context
        ):
          # If a solution section had weak keyword overlap, assign the first unassigned solution_anchor so no requested sales play is dropped
          for a in candidate_anchors:
            if a.get("deck_id") and a.get("deck_id") not in assigned_solution_ids:
              sec_sales_play = a.get("sales_play")
              sec_anchor_deck_id = a.get("deck_id")
              if isinstance(assigned_solution_ids, list):
                assigned_solution_ids.append(sec_anchor_deck_id)
              else:
                assigned_solution_ids.add(sec_anchor_deck_id)
              break

      # Step 5c: If not a specific sales play, align with Why Google Cloud foundation deck for early/Context/Vision sections, or keep primary solution anchor for middle/late Solution sections
      if not sec_anchor_deck_id:
        if (
            is_cvi_context
            or cvi == "Vision"
            or sec_idx <= 1
            or not solution_anchors
        ) and vertical_anchor:
          sec_sales_play = vertical_anchor.get("sales_play")
          sec_anchor_deck_id = vertical_anchor.get("deck_id")
        elif solution_anchors and not is_cvi_context and cvi != "Realization":
          sec_sales_play = solution_anchors[0].get("sales_play")
          sec_anchor_deck_id = solution_anchors[0].get("deck_id")
        elif vertical_anchor:
          sec_sales_play = vertical_anchor.get("sales_play")
          sec_anchor_deck_id = vertical_anchor.get("deck_id")
        else:
          for a in anchor_decks:
            p_name = a.get("sales_play", "")
            p_low = p_name.lower()
            d_title = a.get("deck_title", "").lower()
            if "why google" in p_low or "why google" in d_title:
              sec_sales_play = p_name
              sec_anchor_deck_id = a.get("deck_id")
              break

      # Step 5d: Fallback to primary anchor deck only for non-Context / non-Realization solution sections if still unassigned
      if (
          not sec_anchor_deck_id
          and anchor_decks
          and not is_cvi_context
          and cvi != "Realization"
      ):
        sec_sales_play = anchor_decks[0].get("sales_play")
        sec_anchor_deck_id = anchor_decks[0].get("deck_id")

      return {
          "expected_slide_jobs": jobs,
          "expected_cvi_cluster": cvi,
          "expected_core_topics": core_topics,
          "expected_products": found_prods,
          "expected_maturity": maturity,
          "job_boost": job_boost,
          "section_sales_play": sec_sales_play,
          "section_anchor_deck_id": sec_anchor_deck_id,
          "vertical_anchor_deck_id": (
              vertical_anchor.get("deck_id") if vertical_anchor else None
          ),
          "anchor_deck_ids": sec_context.get("anchor_deck_ids", []),
          "closest_industry": sec_context.get("closest_industry", ""),
      }
    self._resolve_section_metadata_fn = resolve_section_metadata

    # Get all reusable datastores from config (excluding boolean feature flags and legacy_cust_ref)
    datastores = {}
    if 'reusable' in self.config:
      for key in self.config['reusable']:
        val = str(self.config["reusable"][key] or "").strip()
        if (
            key.startswith("enable_")
            or key == "legacy_cust_ref"
            or val.lower() in ("true", "false", "1", "0", "yes", "no", "")
        ):
          continue
        datastores[key] = val

    sol = context.get('solution') or context.get('solutions') or ''
    if isinstance(sol, list):
      sol = ' '.join([str(s) for s in sol if s])
    prod = context.get('product') or context.get('products') or ''
    if isinstance(prod, list):
      prod = ' '.join([str(p) for p in prod if p])
    prod_focus = f"{sol} {prod}".strip()

    assigned_solution_anchor_ids: list[str] = []
    context["_assigned_solution_anchor_ids"] = assigned_solution_anchor_ids
    context["_total_sections"] = len(agendas)
    global_seen_content_entries: list[str] = []

    customer_story_keywords = [
        "customer story",
        "customer stories",
        "proof point",
        "proof points",
        "customer success",
        "success story",
        "success stories",
        "case study",
        "case studies",
        "customer reference",
        "customer references",
        "client reference",
        "peer reference",
        "customer impact",
        "demonstrated customer",
        "customer outcome",
        "peer outcome",
    ]
    impact_section_keywords = [
        "business value",
        "roi",
        "tco",
        "financial",
        "payback",
        "npv",
        "economic",
        "cost sav",
        "impact",
        "value",
        "outcome",
        "result",
        "demonstrated",
    ]
    has_explicit_customer_story_section = False
    designated_impact_sec_idx = None
    for idx_probe, (_, ag_probe) in enumerate(agendas.items(), start=1):
      probe_title = str(ag_probe.get("title", "") or "").lower()
      probe_comb = (
          f"{probe_title} {' '.join(ag_probe.get('parts', []))}".lower()
      )
      if any(kw in probe_comb for kw in customer_story_keywords):
        has_explicit_customer_story_section = True
      if designated_impact_sec_idx is None and any(
          kw in probe_title for kw in impact_section_keywords
      ):
        designated_impact_sec_idx = idx_probe
    if (
        not has_explicit_customer_story_section
        and designated_impact_sec_idx is None
        and len(agendas) >= 3
    ):
      designated_impact_sec_idx = len(agendas) - 1

    for sec_enum_idx, (key, agenda) in enumerate(agendas.items(), start=1):
      context["_current_section_index"] = (
          int(key) if str(key).isdigit() else sec_enum_idx
      )
      title = agenda.get('title', '')
      parts = agenda.get('parts', [])
      query = f"{title}. {' '.join(parts)}"

      # Determine if this agenda is Path to Production / Next Steps / Realization
      # (check title first; only check parts if this is the final section so words like 'developer adoption' in middle sections don't trigger)
      title_lower_only = str(title or "").lower()
      title_parts_lower = f"{title} {' '.join(parts)}".lower()
      is_last_section = sec_enum_idx == len(agendas) and len(agendas) >= 3
      is_next_steps_agenda = any(
          kw in title_lower_only
          for kw in [
              "next step",
              "roadmap",
              "timeline",
              "path to prod",
              "getting started",
              "engagement plan",
              "action plan",
              "call to action",
              "30-60-90",
              "recommended steps",
              "chartering",
          ]
      ) or (
          is_last_section
          and any(
              kw in title_parts_lower
              for kw in [
                  "next step",
                  "roadmap",
                  "timeline",
                  "path to prod",
                  "adoption",
                  "getting started",
                  "engagement plan",
                  "action plan",
                  "call to action",
                  "30-60-90",
                  "caf",
                  "recommended steps",
              ]
          )
      )

      if prod_focus and not is_next_steps_agenda:
        query = f"{prod_focus}: {query}"
      elif is_next_steps_agenda:
        query = f"{query} recommended next steps roadmap path to production adoption"

      if customer_name:
        import re
        pattern = re.compile(re.escape(customer_name), re.IGNORECASE)
        query = pattern.sub("", query)
        query = re.sub(r'\s+', ' ', query).strip()

      # Resolve multi-dimensional section metadata & archetype boost
      agenda_metadata = resolve_section_metadata(
          title, parts, context, archetype_job_weights
      )

      is_customer_story_agenda = False
      title_parts_lower = f"{title} {' '.join(parts)}".lower()
      if any(kw in title_parts_lower for kw in customer_story_keywords):
        is_customer_story_agenda = True
      elif (
          agenda_metadata.get("expected_slide_jobs", [None])[0]
          == "Proof_Points"
      ):
        is_customer_story_agenda = True

      allow_customer_ref_library_proof_points = is_customer_story_agenda or (
          not has_explicit_customer_story_section
          and sec_enum_idx == designated_impact_sec_idx
          and not is_next_steps_agenda
      )
      if (
          allow_customer_ref_library_proof_points
          and "Proof_Points"
          not in agenda_metadata.get("expected_slide_jobs", [])
      ):
        agenda_metadata["expected_slide_jobs"] = list(
            agenda_metadata.get("expected_slide_jobs", [])
        ) + ["Proof_Points"]

      agenda_context = dict(context)
      agenda_context.update(agenda_metadata)
      agenda_context["archetype_job_weights"] = archetype_job_weights
      agenda_context["exclude_customer_refs"] = not allow_customer_ref_library_proof_points

      print(
          f"[{self.name}] Agenda '{title}' -> Slide Jobs:"
          f" {agenda_metadata['expected_slide_jobs']}, CVI:"
          f" {agenda_metadata['expected_cvi_cluster']}, Core Topics:"
          f" {agenda_metadata['expected_core_topics'][:3]}"
      )

      # Partition datastores for this agenda
      tier1_ds = {}
      tier2_ds = {}
      for ds_key, ds_id in datastores.items():
        if ds_key == 'cust_ref':
          if allow_customer_ref_library_proof_points:
            tier1_ds[ds_key] = ds_id
        elif 'silver' in ds_key or ds_key == 'pitch_grp':
          tier2_ds[ds_key] = ds_id
        else:
          tier1_ds[ds_key] = ds_id

      all_raw_results = []
      print(f"[{self.name}] Querying Tier 1 datastores in parallel for agenda: '{title}'...")
      from concurrent.futures import ThreadPoolExecutor

      def fetch_tier1_ds(item):
        ds_key, ds_id = item
        from agents.workflows.slide_retriever_factory import SlideRetrieverFactory
        retriever = SlideRetrieverFactory.get_retriever(ds_key, ds_id, self.config)
        raw_results = retriever.search_slides(query, agenda_context)
        for r in raw_results:
          r['_source_datastore'] = ds_id
          r['_source_datastore_key'] = ds_key
        return self._filter_raw_results(raw_results, customer_name, agenda_context)

      if tier1_ds:
        with ThreadPoolExecutor(max_workers=min(len(tier1_ds), 6)) as executor:
          for filtered_results in executor.map(fetch_tier1_ds, tier1_ds.items()):
            all_raw_results.extend(filtered_results)

      # Helper functions to extract deck ID and slide ID from a slide
      get_deck_id = self._get_deck_id
      get_slide_id = self._get_slide_id

      # 2. Score Tier 1 with multi-factor metadata alignment
      scored_results = self.skills['score'].execute(
          query, all_raw_results, section_metadata=agenda_context
      )

      # Primary threshold = 0.6
      high_scored_anchors = [
          s for s in scored_results if s.get('sim_score', 0) >= 0.6
      ]

      tier2_scored = None
      tier2_raw_results = []
      if not high_scored_anchors and tier2_ds:
        print(
            f"[{self.name}] No Tier 1 slides met primary threshold (>= 0.6). Falling"
            f" back to Tier 2 for agenda: '{title}'"
        )
        tier2_raw_results = []
        for ds_key, ds_id in tier2_ds.items():
          from agents.workflows.slide_retriever_factory import SlideRetrieverFactory
          retriever = SlideRetrieverFactory.get_retriever(ds_key, ds_id, self.config)
          raw_results = retriever.search_slides(query, agenda_context)
          for r in raw_results:
            r['_source_datastore'] = ds_id
            r['_source_datastore_key'] = ds_key
          filtered_results = self._filter_raw_results(raw_results, customer_name, agenda_context)
          tier2_raw_results.extend(filtered_results)

        if tier2_raw_results:
          tier2_scored = self.skills['score'].execute(
              query, tier2_raw_results, section_metadata=agenda_context
          )
          high_scored_anchors = [
              s for s in tier2_scored if s.get('sim_score', 0) >= 0.6
          ]
          if high_scored_anchors:
            scored_results = tier2_scored

      # Fallback to secondary threshold >= 0.5 if no primary matches found
      if not high_scored_anchors:
        print(
            f"[{self.name}] No slides met primary threshold (>= 0.6) in either Tier."
            f" Falling back to secondary threshold (>= 0.5) for agenda: '{title}'"
        )
        # Try Tier 1 first
        high_scored_anchors = [
            s for s in scored_results if s.get('sim_score', 0) >= 0.5
        ]

        # If Tier 1 has nothing >= 0.5, try Tier 2 (Silver)
        if not high_scored_anchors:
          # If we haven't searched/scored Tier 2 yet, do it now
          if tier2_scored is None:
            tier2_raw_results = []
            def fetch_tier2_ds(item):
              ds_key, ds_id = item
              from agents.workflows.slide_retriever_factory import SlideRetrieverFactory
              retriever = SlideRetrieverFactory.get_retriever(ds_key, ds_id, self.config)
              raw_results = retriever.search_slides(query, agenda_context)
              for r in raw_results:
                r['_source_datastore'] = ds_id
                r['_source_datastore_key'] = ds_key
              return self._filter_raw_results(raw_results, customer_name, agenda_context)

            if tier2_ds:
              with ThreadPoolExecutor(max_workers=min(len(tier2_ds), 6)) as executor:
                for filtered_results in executor.map(fetch_tier2_ds, tier2_ds.items()):
                  tier2_raw_results.extend(filtered_results)
            if tier2_raw_results:
              tier2_scored = self.skills['score'].execute(
                  query, tier2_raw_results, section_metadata=agenda_context
              )

          if tier2_scored:
            high_scored_anchors = [
                s for s in tier2_scored if s.get('sim_score', 0) >= 0.5
            ]

      # Strict CVI Cluster Slide Job Governance: Disallow structurally incompatible slide jobs
      CVI_DISALLOWED_JOBS = {
          "Realization": {
              "Market_Trends",
              "Current_State",
              "Why_Google_Cloud",
              "Vision",
              "Solution_Overview",
              "Architecture",
              "Proof_Points",
              "Strategic_Partnership",
          },
          "Context": {
              "Path_to_Prod",
              "Commercials",
              "Architecture",
              "Proof_Points",
              "Solution_Overview",
          },
          "Impact": {
              "Market_Trends",
              "Current_State",
              "Path_to_Prod",
              "Commercials",
          },
          "Vision": {
              "Market_Trends",
              "Current_State",
              "Path_to_Prod",
              "Commercials",
          },
          "Solution": {
              "Market_Trends",
              "Current_State",
              "Path_to_Prod",
              "Commercials",
          },
      }

      expected_cvi = agenda_metadata.get("expected_cvi_cluster", "")
      expected_jobs = agenda_metadata.get("expected_slide_jobs", [])
      disallowed_jobs = CVI_DISALLOWED_JOBS.get(expected_cvi, set())

      # Filter out anchors with disallowed jobs before cluster assembly so they are not consumed into global_seen_slide_keys
      if disallowed_jobs and high_scored_anchors:
        high_scored_anchors = [
            s
            for s in high_scored_anchors
            if self.classify_slide_job(s, customer_name) not in disallowed_jobs
        ]

      # Agenda intent alignment: filter or blend Customer Reference Library Google Slides case studies
      if is_customer_story_agenda:
        # Dedicated customer story agenda: prioritize verified Customer Reference Library GSlides case studies
        case_anchors = [
            s
            for s in high_scored_anchors
            if self._is_case_study_slide(s, customer_name)
        ]
        if case_anchors:
          high_scored_anchors = case_anchors[:2]
        else:
          high_scored_anchors = high_scored_anchors[:2]
      elif allow_customer_ref_library_proof_points:
        # Designated CVI Impact section when no standalone Customer Story section exists:
        # preserve top Business Value anchors AND attach top 1-2 Customer Reference Library GSlides customer references
        non_case_anchors = [
            s
            for s in high_scored_anchors
            if not self._is_case_study_slide(s, customer_name)
        ]
        customer_ref_library_case_anchors = [
            s
            for s in high_scored_anchors or scored_results
            if (
                s.get("_source_library") == "customer_ref_gslides"
                or s.get("_source_datastore_key") == "cust_ref"
            )
            and float(s.get("sim_score", 0.0)) >= 0.5
        ]
        high_scored_anchors = non_case_anchors[:2] + customer_ref_library_case_anchors[:2]
      else:
        non_case_anchors = [
            s
            for s in high_scored_anchors
            if not self._is_case_study_slide(s, customer_name)
        ]
        if non_case_anchors:
          high_scored_anchors = non_case_anchors
        else:
          print(
              f"[{self.name}] Discarding case study slides for non-proof"
              f" section '{title}'"
          )
          high_scored_anchors = []

      # If no slides met threshold for Next Steps / Realization agenda, recover closing Next Steps slides from anchor decks
      if not high_scored_anchors and is_next_steps_agenda:
        print(
            f"[{self.name}] Recovering Next Steps / Path to Production slides from anchor decks for '{title}'..."
        )
        next_step_anchors = []
        for s in all_raw_results:
          if self._is_case_study_slide(s, customer_name):
            continue
          s_title = str(s.get("title") or s.get("name") or s.get("original_title") or "").lower()
          s_content = str(s.get("content") or s.get("desc") or "").lower()
          s_comb = f"{s_title} {s_content}"
          if any(k in s_comb for k in [
              "next step", "get started", "roadmap", "call to action", "timeline",
              "adoption", "caf", "engagement", "immediate step", "journey"
          ]):
            s["slide_job"] = "Path_to_Prod"
            s["cvi_cluster"] = "Realization"
            s["sim_score"] = max(s.get("sim_score", 0.0), 0.75)
            next_step_anchors.append(s)
        if next_step_anchors:
          high_scored_anchors = next_step_anchors
          print(
              f"[{self.name}] Successfully recovered {len(high_scored_anchors)} Next Steps slides from anchor decks."
          )

      # If strategy is 'cloudhub' or 'smart_hybrid' and strict CVI/threshold filtering left 0 anchors,
      # recover top CVI-compatible foundation slides so reusable recall is never starved by customer-specific section titles.
      strat_low = (
          str(context.get("deck_strategy") or "smart_hybrid").strip().lower()
      )
      if not high_scored_anchors and strat_low in ("cloudhub", "smart_hybrid"):
        active_anchor_ids = {
            str(a.get("deck_id"))
            for a in (
                list(context.get("anchor_decks") or [])
                + list(context.get("solution_anchors") or [])
                + (
                    [context["vertical_anchor"]]
                    if isinstance(context.get("vertical_anchor"), dict)
                    else []
                )
            )
            if isinstance(a, dict) and a.get("deck_id")
        }
        fallback_pool = [
            s
            for s in (
                list(scored_results or [])
                + list(tier2_scored or [])
                + list(all_raw_results or [])
            )
            if (
                allow_customer_ref_library_proof_points
                or not self._is_case_study_slide(s, customer_name)
            )
            and self.classify_slide_job(s, customer_name) not in disallowed_jobs
            and (self._get_slide_id(s) or s.get("temp_url"))
            not in global_seen_slide_keys
            and (
                strat_low == "cloudhub"
                or float(s.get("sim_score") or 0.0) >= 0.42
                or self._get_deck_id(s) in active_anchor_ids
            )
        ]
        if fallback_pool:
          take_n = 3 if strat_low == "cloudhub" else 2
          for s in fallback_pool[:take_n]:
            s["sim_score"] = max(float(s.get("sim_score") or 0.0), 0.58)
          high_scored_anchors = fallback_pool[:take_n]
          print(
              f"[{self.name}] Strategy '{strat_low}' anchor-aware recall floor:"
              f" recovered {len(high_scored_anchors)} reusable slide(s) for"
              f" '{title}'."
          )

      if not high_scored_anchors:
        print(
            f"[{self.name}] No slides met similarity standard (score >= 0.5) in"
            f" either Tier for agenda: '{title}'"
        )
        suggestions = []
      else:
        # Extract unique deck IDs from anchors
        deck_ids = set()
        for slide in high_scored_anchors:
          d_id = get_deck_id(slide)
          if d_id:
            deck_ids.add(d_id)

        print(
            f'[{self.name}] Found highly scored anchors from decks: {deck_ids}'
        )

        def get_slide_key(s):
          s_id = get_slide_id(s)
          if s_id:
            return s_id
          return s.get('temp_url', '') or s.get('original_title', '') or s.get('name', '')

        def _slide_content_signature(s):
          t = (
              str(
                  s.get("original_title")
                  or s.get("name")
                  or s.get("title")
                  or ""
              )
              .strip()
              .lower()
          )
          c = (
              str(
                  s.get("original_content")
                  or s.get("desc")
                  or s.get("content")
                  or ""
              )
              .strip()
              .lower()
          )
          return f"{t} {c}".strip()

        def _is_cross_section_duplicate(s):
          sig = _slide_content_signature(s)
          if not sig or len(sig) < 20:
            return False
          try:
            from fuzzywuzzy import fuzz

            for prev_sig in global_seen_content_entries:
              if fuzz.token_set_ratio(sig, prev_sig) >= 78:
                return True
          except ImportError:
            sig_toks = set(re.findall(r"[a-z0-9]{4,}", sig))
            if len(sig_toks) >= 4:
              for prev_sig in global_seen_content_entries:
                prev_toks = set(re.findall(r"[a-z0-9]{4,}", prev_sig))
                if (
                    prev_toks
                    and len(sig_toks & prev_toks)
                    / max(1, min(len(sig_toks), len(prev_toks)))
                    >= 0.78
                ):
                  return True
          return False

        # Intra-Deck CVI & Slide Job Cluster Assembly:
        # If we find a high-scoring reusable anchor, expand to sibling slides within the SAME deck
        # that share the same CVI cluster and matching slide job to preserve cohesive authored modules
        # without bloating across unrelated deck sections.
        all_candidates = list(scored_results or []) + list(tier2_scored or [])
        cluster_slides = []
        seen_slide_keys = set()
        seen_cluster_decks = set()

        for anchor in high_scored_anchors:
          a_key = get_slide_key(anchor)
          if a_key in seen_slide_keys or a_key in global_seen_slide_keys:
            continue
          if _is_cross_section_duplicate(anchor):
            continue
          if not allow_customer_ref_library_proof_points and self._is_case_study_slide(
              anchor, customer_name
          ):
            continue

          d_id = get_deck_id(anchor)
          anchor_cvi = anchor.get('cvi_cluster') or expected_cvi
          anchor_job = self.classify_slide_job(anchor, customer_name)
          anchor["slide_job"] = anchor_job

          is_customer_ref_library_ref = (
              anchor.get("_source_library") == "customer_ref_gslides"
              or anchor.get("_source_datastore_key") == "cust_ref"
          )
          if is_customer_ref_library_ref:
            cluster_slides.append(anchor)
            seen_slide_keys.add(a_key)
            global_seen_slide_keys.add(a_key)
          elif d_id and d_id not in seen_cluster_decks:
            deck_siblings = []
            for s in all_candidates:
              if get_deck_id(s) != d_id:
                continue
              s_key = get_slide_key(s)
              if s_key in seen_slide_keys or s_key in global_seen_slide_keys:
                continue
              if _is_cross_section_duplicate(s):
                continue

              s_cvi = s.get('cvi_cluster') or expected_cvi
              s_job = self.classify_slide_job(s, customer_name)
              s['slide_job'] = s_job
              s['cvi_cluster'] = s_cvi

              # 1. CVI Narrative Stage Alignment (with Vision/Solution 5-Cluster compatibility)
              cvi_match = False
              if expected_cvi and s_cvi:
                s_cvi_l = s_cvi.lower()
                exp_cvi_l = expected_cvi.lower()
                cvi_match = (s_cvi_l == exp_cvi_l) or (
                    s_cvi_l in ("vision", "solution")
                    and exp_cvi_l in ("vision", "solution")
                )
              elif anchor_cvi and s_cvi:
                s_cvi_l = s_cvi.lower()
                anc_cvi_l = anchor_cvi.lower()
                cvi_match = (s_cvi_l == anc_cvi_l) or (
                    s_cvi_l in ("vision", "solution")
                    and anc_cvi_l in ("vision", "solution")
                )
              elif not s_cvi:
                cvi_match = True

              # 2. Slide Job Governance
              if s_job in disallowed_jobs:
                continue
              if not allow_customer_ref_library_proof_points and self._is_case_study_slide(
                  s, customer_name
              ):
                continue
              if is_customer_story_agenda and not self._is_case_study_slide(s, customer_name):
                continue

              job_match = (
                  s_job == anchor_job
                  or (expected_jobs and s_job in expected_jobs)
              )

              # 3. Minimum relevance floor for cluster siblings
              score_ok = (s.get("sim_score", 0.0) >= 0.45) or (s is anchor)

              if cvi_match and job_match and score_ok:
                deck_siblings.append(s)

            if deck_siblings:
              deck_siblings.sort(
                  key=lambda s_cand: (
                      bool(s_cand is anchor),
                      float(s_cand.get("sim_score", 0.0)),
                  ),
                  reverse=True,
              )
              print(
                  f"[{self.name}] Intra-deck CVI cluster expanded: {len(deck_siblings)} slides"
                  f" from deck '{d_id}' (CVI: '{expected_cvi}', Jobs: {[s.get('slide_job') for s in deck_siblings]})"
              )
              for s in deck_siblings:
                s_key = get_slide_key(s)
                cluster_slides.append(s)
                seen_slide_keys.add(s_key)
                global_seen_slide_keys.add(s_key)
              seen_cluster_decks.add(d_id)
            else:
              cluster_slides.append(anchor)
              seen_slide_keys.add(a_key)
              global_seen_slide_keys.add(a_key)
          else:
            cluster_slides.append(anchor)
            seen_slide_keys.add(a_key)
            global_seen_slide_keys.add(a_key)

        formatted_suggestions = []
        for slide in cluster_slides:
          deck_id = get_deck_id(slide)
          slide_id = get_slide_id(slide)
          slide_url = f"https://docs.google.com/presentation/d/{deck_id}/edit?#slide=id.{slide_id}" if deck_id and slide_id else ""

          # Calculate tag score (simple overlap)
          tag_score = 0.0
          context = global_state.context
          if context:
            slide_tags = set()
            for field in ['industry', 'solution', 'product', 'region', 'customer', 'sub-industry', 'sub-solution']:
              val = slide.get(field)
              if val:
                if isinstance(val, list):
                  slide_tags.update([str(x).lower() for x in val])
                else:
                  slide_tags.add(str(val).lower())

            context_tags = set()
            for field in ['industry', 'solution', 'product', 'region', 'customer_name']:
              val = context.get(field)
              if val:
                if isinstance(val, list):
                  context_tags.update([str(x).lower() for x in val])
                else:
                  context_tags.add(str(val).lower())

            if context_tags:
              intersection = slide_tags.intersection(context_tags)
              tag_score = float(len(intersection))
              customer_name = context.get('customer_name', '').lower()
              slide_customer = str(slide.get('customer', '')).lower()
              if customer_name and slide_customer and (customer_name in slide_customer or slide_customer in customer_name):
                tag_score += 1.0

          original_title = slide.get('name') or slide.get('title') or slide.get('customer') or 'No Title'
          original_content = slide.get('desc') or slide.get('content') or 'No Content'

          formatted_sug = {
              "date": slide.get("date", ""),
              "name": original_title,
              "deck_id": deck_id,
              "slide_id": slide_id,
              "tag_score": tag_score,
              "values": [slide_url] if slide_url else [],
              "original_title": original_title,
              "original_content": original_content,
              "speaker_notes": (
                  slide.get("speaker_notes", "") or original_content
              ),
              "core_topics": slide.get("core_topics", []),
              "slide_job": (
                  slide.get("slide_job")
                  or self.classify_slide_job(slide, customer_name)
              ),
              "is_cust_ref": bool(slide.get("is_cust_ref", False)),
              "is_proof_point": bool(slide.get("is_proof_point", False)),
              "customer_name": (
                  slide.get("customer_name") or slide.get("customer") or ""
              ),
              "_source_datastore_key": slide.get("_source_datastore_key", ""),
              "_source_library": slide.get("_source_library", ""),
              "_customer_ref_library_citation": slide.get("_customer_ref_library_citation"),
              "_anchor_match": bool(slide.get("_anchor_match", False)),
          }
          if 'sim_score' in slide:
            formatted_sug['sim_score'] = slide['sim_score']

          is_golden = 'golden' in slide.get('_source_datastore', '').lower()
          if is_golden:
            formatted_sug['is_golden'] = True

          formatted_suggestions.append(formatted_sug)

        valid_suggestions = []
        for s in formatted_suggestions:
          s_job = self.classify_slide_job(s, customer_name)
          s['slide_job'] = s_job
          if s_job in disallowed_jobs:
            print(
                f"[{self.name}] Disqualifying slide '{s.get('name') or s.get('original_title')}'"
                f" (job: '{s_job}') incompatible with section CVI cluster '{expected_cvi}' (Agenda: '{title}')"
            )
            continue
          if _is_cross_section_duplicate(s):
            print(
                f"[{self.name}] Skipping cross-section duplicate slide"
                f" '{s.get('name') or s.get('original_title')}' in '{title}'"
            )
            continue
          valid_suggestions.append(s)

        # Archetype-aware narrative ranking for candidate selection
        active_sequence = ARCHETYPE_JOB_SEQUENCES.get(
            active_archetype, ARCHETYPE_JOB_SEQUENCES["General_Value_Pitch"]
        )

        def suggestion_sort_key(x):
          # Inherent slide job
          s_job = self.classify_slide_job(x, customer_name)

          # 1. Exact match with expected job for this section gets highest affinity
          is_expected_job = s_job in expected_jobs
          job_affinity = 100.0 if is_expected_job else 50.0

          # 2. Archetype canonical sequence rank
          if s_job in active_sequence:
            seq_rank = float(len(active_sequence) - active_sequence.index(s_job))
          else:
            seq_rank = 0.0

          return (
              job_affinity,
              seq_rank,
              x.get('tag_score', 0.0),
              self._parse_date_to_timestamp(x.get('date', '')),
              x.get('sim_score', 0.0)
          )

        valid_suggestions.sort(key=suggestion_sort_key, reverse=True)
        suggestions = self._deduplicate_suggestions(valid_suggestions)

        # Natural multi-slide narrative cluster sizing:
        # Verified CVI + Slide Job clusters from the same deck are preserved completely
        # without arbitrary 3-slide truncation.
        # Customer reference sections remain focused (at most 2).
        if is_customer_story_agenda:
          suggestions = suggestions[:2]
        else:
          # Allow complete multi-slide clusters (up to 5 slides)
          max_cluster_sug = 5
          suggestions = suggestions[:max_cluster_sug]

        # Sort the selected suggestions within the section into strict CVI Narrative Progression Order:
        # L100 Macro/Trends (10) -> Current State / Data Foundations (15) -> Paradigm Shift / Vision (24) -> Platform Overview (30) -> Core Solution/Flow of Work (40-48) -> L200 Architecture/Governance/Defense (55-58) -> Value/Proof (60) -> Commercials (70) -> Next Steps (80)
        def _cvi_narrative_progression_key(sug_item):
          s_job = self.classify_slide_job(sug_item, customer_name)
          s_text = (
              f"{sug_item.get('name', '')} {sug_item.get('original_title', '')}"
              f" {sug_item.get('original_content', '')}"
              f" {sug_item.get('speaker_notes', '')}"
          ).lower()
          if s_job == "Market_Trends":
            stage = 10
          elif s_job == "Current_State" or any(
              k in s_text
              for k in (
                  (
                      "necessity for retailers to re-evaluate their data"
                      " foundations"
                  ),
                  "re-evaluate their data foundations",
                  "outlines focus areas for",
                  "drive sustainable and efficient operations",
              )
          ):
            stage = 15
          elif any(
              k in s_text
              for k in (
                  "moving from reactive to proactive",
                  "from reactive to proactive",
                  "reactive and isolated",
                  "proactive and unified",
              )
          ):
            stage = 24
          elif any(
              k in s_text
              for k in (
                  "front door",
                  "unified hub",
                  "overview of gemini enterprise",
                  "central nervous system",
                  "evolution of workplace",
                  "comprehensive ai stack",
                  "only provider",
                  "key differentiators of the gemini enterprise",
                  "conceptual vision",
              )
          ):
            stage = 30
          elif any(
              k in s_text
              for k in (
                  "trusted, resilient platform",
                  "safety is central",
                  "enterprise grade compliance",
              )
          ):
            stage = 35
          elif any(
              k in s_text
              for k in (
                  "boost productivity in the flow of work",
                  "teams and ai agents collaborating",
                  "shared context between",
                  "empowers employees",
                  "streamlines cross-departmental",
                  "synthesize",
                  "long-running agents",
              )
          ):
            stage = 40
          elif any(
              k in s_text
              for k in (
                  "interactive ui for agents",
                  "widget",
                  "agent designer",
                  "agent orchestration",
                  "federated connectors",
                  "governance controls",
                  "centralized control",
              )
          ):
            stage = 50
          elif any(
              k in s_text
              for k in (
                  "two enterprise security features",
                  "proactive defense",
                  "generally available",
              )
          ):
            stage = 55
          elif "model armor" in s_text:
            stage = 58
          elif s_job in ("Vision", "Why_Google_Cloud", "Strategic_Partnership"):
            stage = 32
          elif s_job == "Solution_Overview":
            stage = 42
          elif s_job == "Architecture":
            stage = 55
          elif s_job in ("Business_Value", "Proof_Points"):
            stage = 60
          elif s_job == "Commercials":
            stage = 70
          elif s_job == "Path_to_Prod":
            stage = 80
          else:
            stage = 45
          return (stage, -float(sug_item.get("sim_score", 0.0)))

        suggestions.sort(key=_cvi_narrative_progression_key)
        for s_item in suggestions:
          sig = _slide_content_signature(s_item)
          if sig:
            global_seen_content_entries.append(sig)

        print(
            f'[{self.name}] Dynamic retrieval fetched {len(suggestions)} slides'
            f" for agenda: '{title}'"
        )

      # In S0 Customer-Research & Discovery-Questions smart_hybrid mode, reserve Customer Research / Footprint
      # and Executive Discovery Questions sections for 100% bespoke synthesis (0 reusable slides)
      deck_strat_low = (
          str(context.get("deck_strategy") or "smart_hybrid").strip().lower()
      )
      is_s0_disc = bool(context.get("is_s0_customer_discovery")) or (
          str(context.get("win_cycle") or context.get("sales_stage") or "")
          .strip()
          .upper()
          == "S0"
      )
      is_bespoke_s0_section = (
          deck_strat_low == "smart_hybrid"
          and is_s0_disc
          and (
              bool(agenda.get("bespoke_research_focus"))
              or any(
                  kw in f"{title} {' '.join(parts)}".lower()
                  for kw in (
                      "discovery question",
                      "opportunity hypothes",
                      "opportunity matrix",
                      "strategic initiative",
                      "technology footprint",
                      "tech footprint",
                      "customer research",
                  )
              )
          )
      )
      if is_bespoke_s0_section:
        print(
            f"[{self.name}] [S0 SMART HYBRID] Reserving section {key}"
            f" ('{title}') for 100% bespoke Customer Research & Discovery"
            " Questions synthesis (0 reusable slides)."
        )
        suggestions = []

      reusable_slides[key] = {'title': title, 'suggestions': suggestions}

    # Balanced Global Proof Points Cap: Max 2 Customer References across the entire deck
    global_proof_points_count = 0
    cleaned_reusable_slides = {}
    for a_key, s_data in reusable_slides.items():
      filtered_sugs = []
      for sug in s_data.get("suggestions", []):
        name_lower = str(sug.get("name", "") or sug.get("original_title", "")).lower()
        content_lower = str(sug.get("original_content", "")).lower()
        is_proof_point = (
            sug.get("_source_datastore_key") in ("cust_ref", "customer_references", "case_studies")
            or sug.get("is_cust_ref")
            or sug.get("is_proof_point")
            or any(sig in name_lower for sig in ("case study", "customer story", "customer success", "proof point"))
            or any(sig in content_lower for sig in ("case study:", "customer spotlight:", "success story:"))
        )
        if is_proof_point:
          if global_proof_points_count < 2:
            filtered_sugs.append(sug)
            global_proof_points_count += 1
            print(f"[{self.name}] Retaining Customer Reference slide: '{sug.get('name')}'")
          else:
            print(f"[{self.name}] Suppressing extra Customer Reference slide to keep narrative focused: '{sug.get('name')}'")
        else:
          filtered_sugs.append(sug)
      cleaned_reusable_slides[a_key] = {"title": s_data.get("title"), "suggestions": filtered_sugs}

    # Multi-Anchor Review Guarantee:
    # Ensure that ALL active sales play platinum anchor decks have contributed slides (skip in S0 Customer Discovery smart_hybrid mode so reusable slides don't crowd out bespoke customer research & discovery questions).
    represented_deck_ids = set()
    for a_data in cleaned_reusable_slides.values():
      for sug in a_data.get("suggestions", []):
        d_id = sug.get("deck_id")
        if d_id:
          represented_deck_ids.add(d_id)
        elif sug.get("values"):
          import re
          m = re.search(r'/presentation/d/([a-zA-Z0-9-_]+)', sug["values"][0])
          if m:
            represented_deck_ids.add(m.group(1))

    is_s0_smart_hybrid = str(
        context.get("deck_strategy") or "smart_hybrid"
    ).strip().lower() == "smart_hybrid" and (
        bool(context.get("is_s0_customer_discovery"))
        or str(context.get("win_cycle") or context.get("sales_stage") or "")
        .strip()
        .upper()
        == "S0"
    )
    solution_anchors = context.get("solution_anchors")
    if is_s0_smart_hybrid:
      required_anchors = []
    elif solution_anchors is not None:
      required_anchors = [a for a in solution_anchors if a.get("deck_id")]
    else:
      required_anchors = [
          a for a in context.get("anchor_decks", [])
          if a.get("deck_id") and "why google" not in a.get("sales_play", "").lower()
      ]

    vertical_anchor = context.get("vertical_anchor")
    if (
        not is_s0_smart_hybrid
        and vertical_anchor
        and vertical_anchor.get("deck_id")
    ):
      v_copy = dict(vertical_anchor)
      v_copy["_is_vertical_foundation"] = True
      required_anchors = [v_copy] + required_anchors

    for req_anchor in required_anchors:
      req_deck_id = req_anchor.get("deck_id")
      req_play = req_anchor.get("sales_play", "")
      is_vert_foundation = bool(req_anchor.get("_is_vertical_foundation"))
      if req_deck_id and req_deck_id not in represented_deck_ids:
        print(
            f"[{self.name}] [MULTI-ANCHOR GUARANTEE] Required anchor deck '{req_anchor.get('deck_title')}'"
            f" ({req_deck_id}) for '{req_play}' has 0 slides retrieved. Initiating dedicated anchor review..."
        )
        # Find best middle solution agenda section (never the final Next Steps/Roadmap section)
        target_agenda_key = None
        best_match_score = -1
        req_play_tokens = set(re.findall(r"\w+", req_play.lower())) - {
            "the",
            "in",
            "your",
            "our",
            "and",
            "for",
            "with",
            "lead",
            "play",
            "deck",
            "transformation",
            "enterprise",
            "agentic",
            "ai",
            "cloud",
            "google",
        }
        all_keys = list(cleaned_reusable_slides.keys())
        # Exclude the last section (Next Steps / Roadmap) when placing solution sales play anchors
        solution_section_keys = (
            all_keys[1:-1] if len(all_keys) >= 3 else all_keys[:-1] or all_keys
        )
        for a_k in solution_section_keys:
          a_v = agendas.get(a_k, {})
          t_parts = f"{a_v.get('title', '')} {' '.join(a_v.get('parts', []))}".lower()
          if any(
              ns in t_parts
              for ns in (
                  "next steps",
                  "roadmap",
                  "implementation plan",
                  "path to prod",
              )
          ):
            continue
          t_tokens = set(re.findall(r"\w+", t_parts))
          overlap = len(req_play_tokens & t_tokens)
          if req_play.lower() in t_parts:
            overlap += 10
          if overlap > best_match_score and overlap > 0:
            best_match_score = overlap
            target_agenda_key = a_k
        if is_vert_foundation and all_keys:
          target_agenda_key = all_keys[0]
        elif not target_agenda_key and solution_section_keys:
          target_agenda_key = solution_section_keys[
              min(1, len(solution_section_keys) - 1)
          ]

        ds_id = datastores.get("sales_play_reusables")
        if ds_id:
          from agents.workflows.slide_retriever_factory import SlideRetrieverFactory
          retriever = SlideRetrieverFactory.get_retriever("sales_play_reusables", ds_id, self.config)
          recovery_context = dict(context)
          recovery_context["section_sales_play"] = req_play
          recovery_context["section_anchor_deck_id"] = req_deck_id
          if is_vert_foundation:
            recovery_context["vertical_anchor_deck_id"] = req_deck_id
          else:
            recovery_context["vertical_anchor_deck_id"] = ""
          recovery_context["exclude_customer_refs"] = True
          query_str = (
              f"{req_play} {req_anchor.get('deck_title', '')}"
              f" {'why google cloud industry trends' if is_vert_foundation else 'solution architecture capabilities'}"
          )
          try:
            from agents.workflows.slide_retriever_factory import _is_standalone_title_or_divider_candidate

            deck_slides = retriever.search_slides(
                query_str, recovery_context, limit=8
            )
            deck_slides = [
                s
                for s in deck_slides
                if not _is_standalone_title_or_divider_candidate(s)
                and str(s.get("slide_job") or "").lower()
                not in ("next_steps", "path_to_prod", "thank_you", "closing")
                and "accelerate your ai evolution"
                not in str(s.get("title") or s.get("slide_title") or "").lower()
                and "thank you"
                not in str(s.get("title") or s.get("slide_title") or "").lower()
            ]
            target_slides = [s for s in deck_slides if (s.get("deck_id") or s.get("deckId")) == req_deck_id]
            if not target_slides:
              target_slides = deck_slides[:2]

            curated_sugs = []
            for s in target_slides[:2]:
              s_id = self._get_slide_id(s)
              if not s_id or s_id == "p":
                continue
              d_id = req_deck_id
              s_url = f"https://docs.google.com/presentation/d/{d_id}/edit?#slide=id.{s_id}" if d_id and s_id else ""
              o_title = s.get('title') or s.get('name') or ('Why Google Cloud' if is_vert_foundation else 'Solution Overview')
              o_content = s.get('content') or s.get('desc') or 'Enterprise solution overview and architecture.'
              curated_sugs.append({
                  'name': o_title,
                  'title': o_title,
                  'original_title': o_title,
                  'content': o_content,
                  'original_content': o_content,
                  'deck_id': d_id,
                  'slide_id': s_id,
                  'values': [s_url] if s_url else [],
                  'slide_job': 'Why_Google_Cloud' if is_vert_foundation else 'Solution_Overview',
                  '_source_datastore_key': 'sales_play_reusables',
                  'sim_score': 0.90 if is_vert_foundation else 0.85,
              })

            if curated_sugs and target_agenda_key:
              print(
                  f"[{self.name}] [MULTI-ANCHOR GUARANTEE] Appended {len(curated_sugs)} curated slides from platinum anchor deck"
                  f" '{req_deck_id}' into Agenda {target_agenda_key}."
              )
              if is_vert_foundation:
                cleaned_reusable_slides[target_agenda_key]['suggestions'] = (
                    curated_sugs + cleaned_reusable_slides[target_agenda_key]['suggestions']
                )[:5]
              else:
                cleaned_reusable_slides[target_agenda_key]['suggestions'].extend(curated_sugs)
              represented_deck_ids.add(req_deck_id)
          except Exception as e:
            print(f"[{self.name}] Error in dedicated anchor review for {req_deck_id}: {e}")

    global_state.reusable_slides = cleaned_reusable_slides
    print(f'[{self.name}] Asset discovery completed with {global_proof_points_count} customer proof points.')
    return global_state

  def _parse_date_to_timestamp(self, date_val):
    if not date_val or not isinstance(date_val, str):
      return 0.0
    import datetime
    import re
    date_str = str(date_val).strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%Y",
    ]
    for fmt in formats:
      try:
        dt = datetime.datetime.strptime(date_str, fmt)
        return dt.timestamp()
      except ValueError:
        continue
    year_match = re.search(r'\b(202[0-9])\b', date_str)
    if year_match:
      try:
        return datetime.datetime(int(year_match.group(1)), 1, 1).timestamp()
      except ValueError:
        pass
    return 0.0

  def _deduplicate_suggestions(self, suggestions, threshold=82):
    try:
      from fuzzywuzzy import fuzz
    except ImportError:
      print(f"[{self.name}] Warning: fuzzywuzzy not installed. Skipping deduplication.")
      return suggestions

    unique_suggestions = []
    for sug in suggestions:
      sug_title = (sug.get('original_title') or sug.get('name') or sug.get('title') or '').strip().lower()
      sug_content = sug.get('original_content', '').strip().lower()
      sug_text = f"{sug_title} {sug_content}".strip()
      sug_date_ts = self._parse_date_to_timestamp(sug.get('date', ''))
      is_duplicate = False

      for idx, u_sug in enumerate(unique_suggestions):
        u_title = (u_sug.get('original_title') or u_sug.get('name') or u_sug.get('title') or '').strip().lower()
        u_content = u_sug.get('original_content', '').strip().lower()
        u_text = f"{u_title} {u_content}".strip()
        u_date_ts = self._parse_date_to_timestamp(u_sug.get('date', ''))

        has_real_content = bool(sug_content and u_content and sug_content != 'no content' and u_content != 'no content')
        content_sim = fuzz.token_set_ratio(sug_content, u_content) if has_real_content else 0
        score_text = fuzz.token_set_ratio(sug_text, u_text) if (sug_text and u_text) else 0
        score_title = fuzz.token_set_ratio(sug_title, u_title) if (sug_title and u_title) else 0

        # True duplicate only if body content is near identical (>=82%) with similar title (>=70%),
        # or both title and text are very high (>=85% & >=78%).
        # Avoid false deduplication on empty/placeholder content ('no content').
        if (has_real_content and content_sim >= threshold and score_title >= 70) or (score_title >= 85 and score_text >= 78):
          is_duplicate = True
          # Keep the latest slide between the duplicates
          if sug_date_ts > u_date_ts:
            print(
                f"[{self.name}] Replacing older duplicate '{u_sug.get('original_title')}' (date: {u_sug.get('date')})"
                f" with newer version '{sug.get('original_title')}' (date: {sug.get('date')})"
            )
            unique_suggestions[idx] = sug
          else:
            print(
                f"[{self.name}] Discarding older duplicate suggestion '{sug.get('original_title')}' (date: {sug.get('date')})"
                f" in favor of '{u_sug.get('original_title')}' (date: {u_sug.get('date')}) [Similarity: {max(score_text, content_sim)}%]"
            )
          break

      if not is_duplicate:
        unique_suggestions.append(sug)

    return unique_suggestions
