"""Text transformer workflow for polishing presentation text with GTM skill and Slide Job intensity governance."""

import concurrent.futures
import json
import re
from agents.skill_loader import get_domain_and_account_glossary
from agents.skill_loader import get_domain_and_account_glossary_with_name
from agents.skill_loader import get_matching_skill_instructions
from agents.skill_loader import get_persona_guidelines
from agents.skill_loader import get_persona_guidelines_with_name
from agents.skill_loader import load_skill_instructions
from agents.workflows.base_workflow import BaseWorkflow
from agents.workflows.developer_knowledge_workflow import DeveloperKnowledgeWorkflow
from google import genai
from google.genai import types

try:
  from services.deck_transformation_service import extract_entities_from_user_prompt
except ImportError:

  def extract_entities_from_user_prompt(prompt_text: str) -> dict:
    return {
        "customer_name": "",
        "industry": "",
        "audience": "",
        "sales_play": "",
        "opportunity_id": "",
        "products": "",
        "user_prompt": str(prompt_text or ""),
    }


# Process-wide customer research cache shared across OutlineWorkflow, SlideEngineeringAgent, and TextTransformerWorkflow
_GLOBAL_CUSTOMER_RESEARCH_CACHE: dict[str, str] = {}


class TextTransformerWorkflow(BaseWorkflow):
  """Polishes and transforms presentation slide text based on edit criteria and Slide Job intensity."""

  def __init__(self, config):
    super().__init__(
        "TextTransformerWorkflow",
        "Polishes/transforms text based on specific criteria and domain"
        " skills.",
    )
    self.config = config
    cfg_default = config["default"] if "default" in config else (config["DEFAULT"] if "DEFAULT" in config else {})
    self.project_id = cfg_default.get("project_name", "your-gcp-project-id") if hasattr(cfg_default, "get") else "your-gcp-project-id"
    self.region = cfg_default.get("region", "global") if hasattr(cfg_default, "get") else "global"

    # Primary copywriting model for all text customization & transformation
    self.gemini_model = cfg_default.get("gemini_model", "gemini-3.8-flash") if hasattr(cfg_default, "get") else "gemini-3.8-flash"

    # Fallback model for API retries
    self.gemini_model_fallback = cfg_default.get("gemini_model_1", "gemini-3.5-flash-lite") if hasattr(cfg_default, "get") else "gemini-3.5-flash-lite"

    # Aliases used by review_deck_cohesion and customize_reusable_slide
    self.model = self.gemini_model
    self.fast_model = self.gemini_model_fallback

    # Cached client
    self.client = genai.Client(
        vertexai=True, project=self.project_id, location=self.region
    )

    # Grounding via Developer Knowledge API with in-memory caching
    self.dk_workflow = DeveloperKnowledgeWorkflow(config)
    self._dk_cache: dict[str, str] = {}
    self._customer_research_cache: dict[str, str] = _GLOBAL_CUSTOMER_RESEARCH_CACHE

  def _get_or_research_customer(
      self, customer_name: str, context: dict | None = None
  ) -> str:
    """Retrieves customer research from context, process-wide cache, or conducts live Google Search research with fast fallback."""
    if not customer_name:
      return ""

    norm_key = customer_name.strip().lower()
    try:
      from src.agents.workflows.outline_workflow import _CUSTOMER_RESEARCH_CACHE as outline_res_cache
    except Exception:
      outline_res_cache = {}

    if context and isinstance(context, dict) and context.get("customer_research"):
      res = str(context["customer_research"]).strip()
      if res:
        self._customer_research_cache[customer_name] = res
        _GLOBAL_CUSTOMER_RESEARCH_CACHE[norm_key] = res
        outline_res_cache[norm_key] = res
        return res

    if customer_name in self._customer_research_cache:
      return self._customer_research_cache[customer_name]
    if norm_key in _GLOBAL_CUSTOMER_RESEARCH_CACHE:
      return _GLOBAL_CUSTOMER_RESEARCH_CACHE[norm_key]
    if norm_key in outline_res_cache:
      cached = outline_res_cache[norm_key]
      self._customer_research_cache[customer_name] = cached
      _GLOBAL_CUSTOMER_RESEARCH_CACHE[norm_key] = cached
      return cached

    prompt = f"""Conduct a deep corporate and technical research on '{customer_name}' using Google Search.
Structure the briefing into these 4 explicit grounding vectors specific to their industry domain:
1. VECTOR 1 - PROPRIETARY PLATFORMS & CORE SYSTEMS: What are their primary customer-facing platforms, developer portals, proprietary algorithms, and technology products (e.g., streaming CDNs, trading engines, core apps, internal developer platforms)?
2. VECTOR 2 - OPERATIONAL SCALE & INFRASTRUCTURE PRIMITIVES: What is their operational scale (e.g., global users, subscriber base, streaming concurrency, transaction throughput, GPU clusters) and technical infrastructure stack?
3. VECTOR 3 - STRATEGIC EXECUTIVE MANDATES & BUSINESS DRIVERS: What are their top strategic, technical, and business priorities (e.g., subscriber retention, content localization, production velocity, margin expansion, latency reduction)?
4. VECTOR 4 - NATIVE DOMAIN & NICHE OPERATIONAL LEXICON: What specific niche domain terminology, acronyms, and workflow terms do their engineering, creative, or operations teams use?

Provide an authoritative, detailed technical briefing organized by these 4 vectors with concrete platform names and domain vocabulary.
"""
    for attempt_model, timeout_ms in [
        (self.gemini_model, 18000),
        (self.gemini_model_fallback, 15000),
    ]:
      if not attempt_model:
        continue
      try:
        print(
            f"[TextTransformerWorkflow] Performing live Google Search customer"
            f" research for: '{customer_name}' (model={attempt_model})..."
        )
        response = self.client.models.generate_content(
            model=attempt_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                http_options=types.HttpOptions(timeout=timeout_ms),
            ),
        )
        extracted = self.extract_text(response)
        if extracted and len(extracted.strip()) >= 150:
          print(
              "[TextTransformerWorkflow] -> Retrieved live customer research"
              f" for '{customer_name}' ({len(extracted)} chars)."
          )
          self._customer_research_cache[customer_name] = extracted
          _GLOBAL_CUSTOMER_RESEARCH_CACHE[norm_key] = extracted
          return extracted
      except Exception as e:
        print(
            f"[TextTransformerWorkflow] Notice: Customer research attempt with"
            f" {attempt_model} failed ({e}); trying fallback..."
        )

    fallback = (
        f"Target Account: {customer_name}.\n"
        "Grounding Strategy: Ground strictly on authoritative industry"
        " vertical, sub-industry operational KPIs, and domain lexicon without"
        " hallucinating nonexistent proprietary platforms."
    )
    self._customer_research_cache[customer_name] = fallback
    _GLOBAL_CUSTOMER_RESEARCH_CACHE[norm_key] = fallback
    return fallback

  def _select_model(self, criteria: str = "") -> tuple[str, str]:
    """Selects primary (Gemini 3.8 Flash) and fallback (Gemini 3.5 Flash-Lite) models."""
    return self.gemini_model, self.gemini_model_fallback

  def _get_rules_for_job(self, job_name: str, is_explicit_sidebar: bool = False) -> tuple[str, str, int]:
    """Returns (job_enum, governance_instruction, customization_intensity_pct)."""
    job_lower = (job_name or "").lower().replace(" ", "_")
    if "proof_point" in job_lower or "proof" in job_lower or "case_study" in job_lower:
      return (
          "Proof_Points",
          "\nSLIDE JOB GOVERNANCE (0% IMMUTABLE - PROOF POINTS & CUSTOMER REFERENCES):\n"
          "CRITICAL MANDATE: This slide contains factual third-party customer case studies, quotes, or proof points. "
          "Do NOT customize or replace existing third-party customer references, customer names (e.g. Home Depot, PayPal, Adidas, Walmart, Lowe's, Cynergy Bank), "
          "logos, quote attributions, or empirical metrics with the target account name. Keep the proof points 100% intact.",
          0,
      )
    elif "why_google" in job_lower or "why_gcp" in job_lower:
      return (
          "Why_Google_Cloud",
          (
              "\nSLIDE JOB GOVERNANCE (15-25% LIGHT CUSTOMIZATION - WHY GOOGLE"
              " CLOUD):\nCRITICAL LOW INTENSITY TOKEN CONSTRAINT (≤10%):"
              " Perform strictly minimal edits. Only substitute domain nouns,"
              " entity names, and KPIs. Keep all verbs, prepositions, sentence"
              " structure, and clause syntax 100% identical to the original"
              " text. Preserve core Google Cloud differentiators and platform"
              " features (e.g., custom TPUs, Gemini Enterprise, BeyondCorp) and"
              " global backbone infrastructure."
          ),
          15,
      )
    elif "architecture" in job_lower or "blueprint" in job_lower or "diagram" in job_lower:
      return (
          "Architecture",
          (
              "\nSLIDE JOB GOVERNANCE (15-25% LIGHT CUSTOMIZATION - TECHNICAL"
              " ARCHITECTURE):\nCRITICAL: Preserve core Google Cloud"
              " differentiators and back-end blueprints (e.g., BigQuery, Gemini"
              " Enterprise, GKE, Pub/Sub). Only customize edge ingestion"
              " labels, client apps, and workload context to the target"
              " account."
          ),
          25,
      )
    elif "commercial" in job_lower or "pricing" in job_lower or "cud" in job_lower or "edp" in job_lower:
      return (
          "Commercials",
          "\nSLIDE JOB GOVERNANCE (15% LIGHT CUSTOMIZATION - HITL REQUIRED FOR PRICING):\n"
          "CRITICAL: Do NOT invent or alter discount percentages, Committed Use Discount (CUD) tiers, or Enterprise Discount Program (EDP) terms without Human-In-The-Loop (HITL) review. Keep standard consumption pricing structure intact.",
          15,
      )
    elif "solution" in job_lower or "overview" in job_lower:
      return (
          "Solution_Overview",
          "\nSLIDE JOB GOVERNANCE (60% MODERATE CUSTOMIZATION - SOLUTION OVERVIEW):\n"
          "Tailor product capability pillars, solution value, and end-user benefits to the target account's use case.",
          60,
      )
    elif "path" in job_lower or "roadmap" in job_lower or "timeline" in job_lower:
      return (
          "Path_to_Prod",
          "\nSLIDE JOB GOVERNANCE (75% HIGH CUSTOMIZATION - ROADMAP & PATH TO PROD):\n"
          "Map implementation milestones, 30-60-90 day timelines, and Cloud Adoption Framework stages to the target account.",
          75,
      )
    elif "partnership" in job_lower or "strategic" in job_lower or "joint" in job_lower:
      return (
          "Strategic_Partnership",
          "\nSLIDE JOB GOVERNANCE (85% HEAVY CUSTOMIZATION - STRATEGIC PARTNERSHIP & PRINCIPLES):\n"
          "Tailor joint strategic initiatives, executive governance (e.g., Joint Steering Committee), shared long-term vision, and Alphabet ecosystem synergies directly to the target account. Preserve Google's foundational trust principles (data sovereignty: 'your data is your IP', open multi-cloud posture, zero vendor lock-in).",
          85,
      )
    elif "navigation" in job_lower or "agenda" in job_lower or "divider" in job_lower or "title" in job_lower or "section_header" in job_lower or "thank" in job_lower:
      if is_explicit_sidebar:
        return (
            "Navigation",
            "\nSLIDE JOB GOVERNANCE (85% CUSTOMIZATION - USER-INITIATED SIDEBAR EDIT):\n"
            "Apply the user's specific editing instructions to this navigation/title/agenda slide while maintaining clean, executive brevity.",
            85,
        )
      else:
        return (
            "Navigation",
            "\nSLIDE JOB GOVERNANCE (0% IMMUTABLE - AUTOMATIC DECK GENERATION):\n"
            "CRITICAL MANDATE: This is an automatic deck generation run. Preserve the titles, agenda items, and section headers 100% verbatim to maintain cohesion with the agreed outline.",
            0,
        )
    elif "market" in job_lower or "trend" in job_lower:
      return (
          "Market_Trends",
          "\nSLIDE JOB GOVERNANCE (MARKET TRENDS & CITED BENCHMARK INTEGRITY):\n"
          "1. QUALITATIVE TRENDS: Align overarching industry pressures, digital transformation imperatives, and macroeconomic drivers to the target account's vertical.\n"
          "2. CITED THIRD-PARTY RESEARCH & BENCHMARKS (0% IMMUTABLE METRIC CLAIMS): "
          "If the slide contains cited statistics, analyst surveys (e.g. Gartner, IDC, BCG, McKinsey, Forrester, PYMNTS), or empirical benchmarks, "
          "NEVER alter the measured population (e.g. do NOT change 'firms' to 'OEMs' or 'banks') or the metric definition (e.g. do NOT change 'megabreaches' to 'fleet exploits'). "
          "Preserve the cited metric and scope 100% verbatim to avoid fabricating research. "
          "Bridge the macro research to the target customer strictly via the slide headline / takeaway layer.",
          70,
      )
    elif "current" in job_lower or "pain" in job_lower or "discovery" in job_lower:
      return (
          "Current_State",
          "\nSLIDE JOB GOVERNANCE (95% HEAVY ACCOUNT CUSTOMIZATION - CURRENT STATE):\n"
          "Focus squarely on the target customer's top business challenges, strategic priorities, and organizational bottlenecks.",
          95,
      )
    elif "business" in job_lower or "value" in job_lower or "roi" in job_lower or "tco" in job_lower:
      return (
          "Business_Value",
          "\nSLIDE JOB GOVERNANCE (85-100% FULL ACCOUNT CUSTOMIZATION - BUSINESS VALUE & ROI):\n"
          "Tailor every bullet and financial proof point (ROI, TCO, Net Present Value, payback period) directly to the target account's business scale, executive KPIs, and industry economics.",
          100,
      )
    return (
        "Solution_Overview",
        "\nSLIDE JOB GOVERNANCE (85-100% FULL ACCOUNT CUSTOMIZATION):\n"
        "Tailor every bullet and financial proof point to the target account.",
        85,
    )

  def _get_slide_job_throttling_rules(self, job_or_criteria: str) -> str:
    """Helper method for backward-compatibility to retrieve governance rule string."""
    _, rule, _ = self._get_rules_for_job(job_or_criteria)
    return rule

  def resolve_slide_job(
      self,
      texts: list[str],
      slide_data: dict | None = None,
      criteria: str = "",
      context: dict | None = None,
  ) -> tuple[str, str, int]:
    """Resolves Slide Job ENUM, governance instruction, and customization intensity (0-100%)."""
    slide_data = slide_data or {}
    context = context or {}

    # 1. Slide-Level Schema Metadata Check (Discovery Engine / Reusable Slides Schema)
    is_sidebar = (
        context.get("client_source") == "sidebar"
        or context.get("action") == "sidebar_transform"
        or slide_data.get("client_source") == "sidebar"
        or (criteria and "Tailor presentation text to" not in criteria and len(criteria) > 10)
    )

    explicit_job = (
        slide_data.get("slide_job")
        or slide_data.get("taxonomy", {}).get("slide_job")
        or context.get("slide_job")
    )
    slide_cat = str(
        slide_data.get("category")
        or slide_data.get("slide_category")
        or slide_data.get("taxonomy", {}).get("category")
        or ""
    ).lower()

    is_cust_ref_schema = (
        slide_data.get("customer_references") in (True, "true", "True")
        or slide_data.get("is_customer_story") in (True, "true")
        or slide_data.get("is_cust_ref") in (True, "true")
        or slide_data.get("_source_datastore_key") in ("customer_references", "cust_ref")
        or "cust-ref" in str(slide_data.get("_source_datastore", "")).lower()
        or "cust_ref" in str(slide_data.get("deck_source_url", "")).lower()
        or "cust_ref" in str(slide_data.get("slide_id", "")).lower()
        or slide_cat in ("customer_references", "customer_reference", "customer_story", "case_study", "proof_points", "proof_point")
    )
    if is_cust_ref_schema:
      return self._get_rules_for_job("Proof_Points", is_explicit_sidebar=is_sidebar)

    if explicit_job:
      return self._get_rules_for_job(str(explicit_job), is_explicit_sidebar=is_sidebar)

    # 2. Content-Based Automatic Detection
    combined_content = " ".join([str(t) for t in texts]).lower()
    title_str = str(slide_data.get("title", "") or slide_data.get("slide_title", "")).lower()
    speaker_notes_str = ""
    for note_k in ("speaker_notes", "speakerNotes", "notes", "speaker_note", "notes_text", "speaker_notes_shape"):
      if note_k in slide_data and slide_data[note_k]:
        speaker_notes_str += " " + str(slide_data[note_k])

    full_text = f"{title_str} {combined_content} {speaker_notes_str.lower()}"

    # A. Proof Points detection (Specific to verified customer reference slides & speaker notes)
    has_speaker_notes_ref = any(
        sn_term in speaker_notes_str.lower()
        for sn_term in (
            "customer_reference_library", "https://your-sales-portal.example.com/customer-references", "https://your-sales-portal.example.com/customer-references", "customer_reference_crm",
            "customer stories older than", "references are meant to be leveraged", "publish date: 20",
            "talking points for customer story"
        )
    )

    title_is_proof_point = any(
        k in title_str
        for k in (
            "case study:", "customer story:", "customer spotlight:", "success story:", "customer case study"
        )
    )

    has_case_study_structure = (
        any(c in full_text for c in ("challenge:", "[challenge]"))
        and any(s in full_text for s in ("solution:", "[solution]"))
        and any(r in full_text for r in ("results:", "[impact]"))
    )

    has_known_cust_name = any(
        c in title_str
        for c in (
            "case study", "customer story", "lowe's", "lowes", "smartersorting", "smarter sorting",
            "home depot", "wayfair", "carrefour", "spotify", "paypal", "cynergy bank"
        )
    )

    if (
        title_is_proof_point
        or has_speaker_notes_ref
        or has_case_study_structure
        or has_known_cust_name
    ):
      return self._get_rules_for_job("Proof_Points", is_explicit_sidebar=is_sidebar)

    # B. Architecture detection
    has_arch_terms = any(k in full_text for k in ("architecture", "blueprint", "data flow", "data ingestion", "pipeline", "reference architecture", "system design", "infrastructure", "microservices", "control plane", "data plane", "mesh"))
    gcp_services = sum(1 for p in ("bigquery", "vertex ai", "gke", "pub/sub", "cloud storage", "dataflow", "dataproc", "alloydb", "spanner", "looker", "cloud run", "apigee", "anthos") if p in full_text)
    if has_arch_terms or gcp_services >= 2:
      return self._get_rules_for_job("Architecture", is_explicit_sidebar=is_sidebar)

    # C. Navigation detection (Agenda, Dividers, Table of Contents)
    is_nav = any(k in full_text for k in ("agenda", "table of contents", "section divider", "overview of topics", "executive summary", "welcome to", "objectives"))
    if is_nav:
      return self._get_rules_for_job("Navigation", is_explicit_sidebar=is_sidebar)

    # D. Commercials detection (Pricing, EDP, CUD)
    has_commercials = any(k in full_text for k in ("pricing", "commercials", "consumption model", "committed use discount", "cud", "enterprise discount program", "edp", "sku", "billing model", "co-investment"))
    if has_commercials:
      return self._get_rules_for_job("Commercials", is_explicit_sidebar=is_sidebar)

    # E. Business Value detection (Financial ROI, TCO, NPV)
    has_biz_val = any(k in full_text for k in ("business value", "roi", "tco", "net present value", "npv", "payback period", "financial justification", "economic impact", "cost savings", "cost takeout"))
    if has_biz_val:
      return self._get_rules_for_job("Business_Value", is_explicit_sidebar=is_sidebar)

    # F. Market Trends detection
    has_market_trends = any(k in full_text for k in ("market trends", "industry landscape", "macroeconomic", "macro trends", "industry shifts", "regulatory pressure", "market dynamics", "market growth"))
    if has_market_trends:
      return self._get_rules_for_job("Market_Trends", is_explicit_sidebar=is_sidebar)

    # G. Current State detection (Discovery, Pain Points, Friction)
    has_current_state = any(k in full_text for k in ("current state", "pain points", "challenges", "roadblocks", "friction", "bottlenecks", "discovery recap", "as-is", "operational hurdles"))
    if has_current_state:
      return self._get_rules_for_job("Current_State", is_explicit_sidebar=is_sidebar)

    # H. Path to Prod detection (Roadmap, Timelines)
    has_path_to_prod = any(k in full_text for k in ("path to prod", "roadmap", "timeline", "30-60-90", "milestones", "migration plan", "adoption framework", "next steps", "rollout plan"))
    if has_path_to_prod:
      return self._get_rules_for_job("Path_to_Prod", is_explicit_sidebar=is_sidebar)

    # I. Strategic Partnership detection
    has_partnership = any(k in full_text for k in ("strategic partnership", "joint vision", "joint roadmap", "co-innovation", "steering committee", "trust principles", "alphabet synergies", "data sovereignty"))
    if has_partnership:
      return self._get_rules_for_job("Strategic_Partnership", is_explicit_sidebar=is_sidebar)

    # J. Why Google Cloud detection
    has_why_gcp = any(k in full_text for k in ("why google cloud", "why google", "google differentiators", "custom tpus", "gemini enterprise agent platform", "planetary scale", "beyondcorp"))
    if has_why_gcp:
      return self._get_rules_for_job("Why_Google_Cloud", is_explicit_sidebar=is_sidebar)

    # Check criteria if none of the above matched
    criteria_lower = (criteria or "").lower()
    if any(k in criteria_lower for k in ("proof", "case_study", "reference")):
      return self._get_rules_for_job("Proof_Points", is_explicit_sidebar=is_sidebar)
    if any(k in criteria_lower for k in ("why_google", "differentiator")):
      return self._get_rules_for_job("Why_Google_Cloud", is_explicit_sidebar=is_sidebar)
    if any(k in criteria_lower for k in ("architecture", "diagram", "blueprint")):
      return self._get_rules_for_job("Architecture", is_explicit_sidebar=is_sidebar)
    if any(k in criteria_lower for k in ("commercial", "pricing", "cud", "edp")):
      return self._get_rules_for_job("Commercials", is_explicit_sidebar=is_sidebar)
    if any(k in criteria_lower for k in ("partnership", "joint_vision", "principles")):
      return self._get_rules_for_job("Strategic_Partnership", is_explicit_sidebar=is_sidebar)
    if any(k in criteria_lower for k in ("current_state", "discovery", "pain_points")):
      return self._get_rules_for_job("Current_State", is_explicit_sidebar=is_sidebar)
    if any(k in criteria_lower for k in ("business_value", "roi", "tco")):
      return self._get_rules_for_job("Business_Value", is_explicit_sidebar=is_sidebar)
    if any(k in criteria_lower for k in ("market_trends", "trends")):
      return self._get_rules_for_job("Market_Trends", is_explicit_sidebar=is_sidebar)

    return self._get_rules_for_job("Solution_Overview", is_explicit_sidebar=is_sidebar)

  @staticmethod
  def compute_algebraic_text_height_pt(
      text_or_chars: str | int,
      width_pt: float,
      font_size: float = 11.0,
      line_spacing_pct: float = 125.0,
      padding_top_pt: float = 6.0,
      padding_bottom_pt: float = 6.0,
      header_height_pt: float = 0.0,
  ) -> float:
    """Computes the algebraic required height H_req (in PT) for text inside a shape of width `width_pt`.

    Formula (from gslides-designer algebraic layout gate):
      CharsPerLine(w, fs) = max(8, floor((w - 12) / (fs * 0.54)))
      EstimatedLines = sum_p ceil(len(p) / CharsPerLine)
      H_req = Padding_top + H_header + EstimatedLines * fs * (LineSpacing / 100)
      + Padding_bottom
    """
    import math

    w_val = max(36.0, float(width_pt or 180.0))
    fs = max(6.0, float(font_size or 11.0))
    usable_w = max(24.0, w_val - 12.0)
    chars_per_line = max(8, int(usable_w // (fs * 0.54)))

    if isinstance(text_or_chars, int):
      n_chars = max(0, text_or_chars)
      total_lines = (
          max(1, math.ceil(n_chars / float(chars_per_line)))
          if n_chars > 0
          else 0
      )
    else:
      raw_str = str(text_or_chars or "").strip()
      if not raw_str:
        total_lines = 0
      else:
        paras = [p.strip() for p in raw_str.split("\n") if p.strip()]
        total_lines = sum(
            max(1, math.ceil(len(p) / float(chars_per_line))) for p in paras
        )

    line_height_pt = fs * (float(line_spacing_pct) / 100.0)
    return (
        float(padding_top_pt)
        + float(header_height_pt)
        + (total_lines * line_height_pt)
        + float(padding_bottom_pt)
    )

  @staticmethod
  def compute_algebraic_char_capacity(
      width_pt: float,
      height_pt: float,
      font_size: float = 11.0,
      line_spacing_pct: float = 125.0,
      padding_top_pt: float = 6.0,
      padding_bottom_pt: float = 6.0,
      header_height_pt: float = 0.0,
  ) -> int:
    """Inverts the Pre-Batch Algebraic Text-Height Gate (H_req <= H_card) to compute the maximum character budget that physically fits inside (width_pt, height_pt)."""
    w_val = max(36.0, float(width_pt or 180.0))
    h_val = max(18.0, float(height_pt or 100.0))
    fs = max(6.0, float(font_size or 11.0))
    usable_w = max(24.0, w_val - 12.0)
    chars_per_line = max(8, int(usable_w // (fs * 0.54)))
    line_height_pt = fs * (float(line_spacing_pct) / 100.0)
    usable_h = max(
        line_height_pt,
        h_val
        - float(padding_top_pt)
        - float(padding_bottom_pt)
        - float(header_height_pt),
    )
    max_lines = max(1, int(usable_h // line_height_pt))
    return max(12, int(max_lines * chars_per_line))

  def _compute_char_budget(
      self,
      original_len: int,
      font_size: float | None = None,
      is_action_title: bool = False,
      width_pt: float | None = None,
      clearance_pt: float | None = None,
      height_pt: float | None = None,
  ) -> tuple[int, int]:
    """Computes (target_chars, hard_max_chars) based on original character count, font size (pt), and box geometry, enforcing the Pre-Batch Algebraic Text-Height Gate (H_req <= H_card).

    - Action titles: geometry-aware when width_pt/clearance_pt are known (narrow
    column <= 36 chars, wide header 52-68 chars).
    - Display headers (font_size >= 28pt and original_len <= 42 when not
    is_action_title): capped at 32 chars.
    - Tier 1 (fontSize >= 18pt or <= 30 chars): target -10% (0.90x), hard max
    -5% (0.95x).
    - Tier 2 (12pt <= fontSize < 18pt): target -8% (0.92x), hard max -5%
    (0.95x).
    - Tier 3 (fontSize < 12pt or unspecified): target -5% (0.95x), hard max -5%
    (0.95x).
    - Pre-Batch Algebraic Text-Height Gate: when width_pt and height_pt (or
    clearance_pt) are known, clamps hard_max_chars so H_req <= H_card.
    """
    if original_len <= 0:
      return 0, 0

    fs = float(font_size) if font_size is not None else 12.0
    eff_box_h = self._resolve_effective_height_pt(height_pt, clearance_pt)
    if is_action_title:
      if fs >= 48.0:
        # 68pt Cover Slide primary title sits in a 380pt-wide column (~10 chars/line); cap at 28 chars (2-3 lines) so it never wraps onto 4-5 lines
        return 24, 28
      if width_pt is not None and float(width_pt) > 0:
        w_val = float(width_pt)
        if w_val >= 340.0:
          # Wide horizontal top-of-slide title (including Context-v1 421.8pt x 32.7pt placeholders that auto-expand downward to 2 lines at 26-30pt):
          # NEVER clamp max_lines to 1 using nominal 1-line placeholder height_pt (32.7pt)!
          # Only restrict to 1 line when an explicit tight vertical clearance_pt < 48pt to a non-decorative text box below exists.
          if clearance_pt is not None and 0 < float(clearance_pt) < 48.0:
            hard_max_chars = min(46, max(36, int(w_val / (24.0 * 0.52))))
            target_chars = max(30, int(hard_max_chars * 0.88))
            return target_chars, hard_max_chars
          # Standard 1-2 line horizontal executive thesis title (46 to 58 chars, matching Deck Generation Context-v1 title budget)
          effective_base = min(62, max(original_len, 56)) if original_len >= 8 else 56
          hard_max_chars = min(60, max(52, int(effective_base * 0.98)))
          target_chars = min(52, max(44, int(hard_max_chars * 0.88)))
          return target_chars, hard_max_chars

        # Narrow left-rail column title (w_val < 340.0, e.g. T2/T18/T25 165-212pt wide or split-column 255-280pt wide):
        eff_v_space = None
        if clearance_pt is not None and float(clearance_pt) > 0:
          eff_v_space = float(clearance_pt)
        elif height_pt is not None and float(height_pt) > 0:
          eff_v_space = float(height_pt)
        if clearance_pt is None or (eff_v_space is not None and eff_v_space >= 115.0):
          # Open left-column title box (clearance_pt is None or >=115pt, e.g. T2/T18 with 220pt open below): allow 3-line consultative thesis headlines (44-54 chars)
          hard_max_chars = min(56, max(54, min(original_len, 56)))
          target_chars = max(44, int(hard_max_chars * 0.85))
          return target_chars, hard_max_chars
        if clearance_pt is not None and 0 < float(clearance_pt) < 68.0:
          hard_max_chars = 36
          target_chars = 30
          return target_chars, hard_max_chars
        # Standard left-rail title with moderate vertical clearance (68-115pt): 40-50 chars
        hard_max_chars = 50
        target_chars = 42
        return target_chars, hard_max_chars

      if fs >= 24.0:
        # Main slide titles (24pt-34pt) sit in wide header boxes (405pt-661pt wide) that comfortably fit 46-64 chars.
        effective_base = (
            min(66, max(original_len, 56)) if original_len >= 8 else 56
        )
        target_chars = min(56, max(44, int(effective_base * 0.90)))
        hard_max_chars = min(
            66,
            max(
                52,
                original_len
                if original_len >= 60
                else int(effective_base * 0.98),
            ),
        )
        return target_chars, hard_max_chars

    # Non-action-title 2-column display header (fontSize >= 28pt and original_len <= 42): cap at 32 chars
    if not is_action_title and fs >= 28.0 and original_len <= 42:
      hard_max_chars = min(32, max(1, int(original_len * 0.95)))
      target_chars = min(28, max(1, int(original_len * 0.90)))
      return target_chars, hard_max_chars

    is_spacious_body_card = bool(
        width_pt is not None
        and eff_box_h is not None
        and float(width_pt) >= 160.0
        and eff_box_h >= 40.0
        and fs <= 13.0
        and original_len >= 20
    )
    has_spacious_header_geom = bool(
        width_pt is not None
        and eff_box_h is not None
        and not is_spacious_body_card
        and (
            (float(width_pt) >= 135.0 and eff_box_h >= 20.0)
            or (float(width_pt) >= 110.0 and eff_box_h >= 28.0)
        )
    )
    if (
        original_len <= 4
        or (
            original_len <= 15
            and not has_spacious_header_geom
            and not is_spacious_body_card
        )
    ):
      return max(1, int(original_len * 0.95)), original_len
    if 16 <= original_len <= 22 and fs <= 14.0 and not has_spacious_header_geom:
      if width_pt is not None and 0 < float(width_pt) < 130.0 and (eff_box_h is None or eff_box_h < 32.0):
        # Narrow 18pt-tall UI pill (e.g. 112pt wide "Example use case" -> "Silicon use case"): cap at 16 chars so it stays 1 line
        return 16, 16
      if width_pt is None or float(width_pt) >= 130.0 or (eff_box_h is not None and eff_box_h >= 32.0):
        # Wider UI pill (>=130pt) or 2-line vertical pill card (>=32pt tall): allow up to 22 chars
        return min(original_len, 18), max(original_len, 22)

    if fs >= 18.0 or original_len <= 30:
      target_chars = max(1, int(original_len * 0.90))
      hard_max_chars = max(1, int(original_len * 0.95))
    elif fs >= 12.0:
      target_chars = max(1, int(original_len * 0.92))
      hard_max_chars = max(1, int(original_len * 0.95))
    else:
      target_chars = max(1, int(original_len * 0.95))
      hard_max_chars = max(1, int(original_len * 0.95))

    # Pre-Batch Algebraic Text-Height Gate (H_req <= H_card) when physical box geometry is provided
    if width_pt is not None and float(width_pt) > 0:
      eff_h = eff_box_h
      if eff_h is not None and eff_h > 0:
        w_f = float(width_pt)
        alg_cap = self.compute_algebraic_char_capacity(
            width_pt=w_f,
            height_pt=eff_h,
            font_size=fs,
        )
        if alg_cap < hard_max_chars:
          # Only apply original_len floor for nominal thin (<55pt) unconstrained text boxes
          # whose Slides API size.height is a single-line placeholder; for >=55pt card boxes
          # or clearance-bounded boxes, strictly enforce alg_cap so text never overflows the card.
          floor_chars = (
              max(16, int(original_len * 0.95))
              if (
                  not is_action_title
                  and original_len > 0
                  and eff_h < 55.0
                  and clearance_pt is None
              )
              else 16
          )
          hard_max_chars = max(floor_chars, alg_cap)
          target_chars = min(target_chars, max(14, int(hard_max_chars * 0.92)))
        elif not is_action_title and alg_cap > hard_max_chars:
          # 1) Spacious body cards (w_f >= 160pt, eff_h >= 40pt, fs <= 13pt) MUST be evaluated first
          # so short 20-35 char body fragments inside 260pt x 58pt cards are never mis-capped at 36 chars by the header rule.
          if (
              20 <= original_len <= 105
              and w_f >= 160.0
              and eff_h >= 40.0
              and fs <= 13.5
          ):
            if w_f >= 200.0 and eff_h >= 48.0:
              # Anchor directly to physical 3-line card capacity (110-115 chars) even if current text was degraded to ~30 chars
              hard_max_chars = min(alg_cap, max(hard_max_chars, 114))
              target_chars = min(
                  hard_max_chars, max(98, int(hard_max_chars * 0.90))
              )
            else:
              expanded_cap = 115 if (w_f >= 220.0 and eff_h >= 48.0) else 105
              mult = (
                  2.2
                  if (w_f >= 180.0 and eff_h >= 44.0 and original_len <= 70)
                  else 1.65
              )
              hard_max_chars = min(
                  alg_cap,
                  max(
                      hard_max_chars,
                      min(expanded_cap, max(90, int(original_len * mult))),
                  ),
              )
              target_chars = min(
                  hard_max_chars, max(target_chars, int(hard_max_chars * 0.88))
              )
          # 2) Spacious sub-card / pill headers (including 1-word degraded labels >= 5 chars like 'Margin' inside 116pt x 60pt pills)
          elif (
              5 <= original_len <= 35
              and (
                  (w_f >= 135.0 and eff_h >= 20.0)
                  or (w_f >= 110.0 and eff_h >= 28.0)
              )
              and fs <= 18.0
          ):
            if w_f < 135.0:
              hard_max_chars = min(alg_cap, max(hard_max_chars, 22))
              target_chars = min(hard_max_chars, max(16, int(hard_max_chars * 0.80)))
            else:
              cap_limit = 36
              hard_max_chars = min(
                  alg_cap,
                  max(
                      hard_max_chars,
                      min(cap_limit, max(22, int(original_len * 1.45))),
                  ),
              )
              target_chars = min(
                  hard_max_chars, max(16, int(hard_max_chars * 0.85))
              )
          elif (
              24 <= original_len <= 95
              and w_f >= 160.0
              and eff_h >= 40.0
              and fs <= 16.0
          ):
            expanded_cap = 115 if (w_f >= 220.0 and eff_h >= 48.0) else 105
            mult = (
                2.0
                if (w_f >= 220.0 and eff_h >= 48.0 and original_len <= 70)
                else 1.65
            )
            hard_max_chars = min(
                alg_cap,
                max(hard_max_chars, min(expanded_cap, int(original_len * mult))),
            )
            target_chars = min(
                hard_max_chars, max(target_chars, int(hard_max_chars * 0.88))
            )

    return target_chars, hard_max_chars

  @staticmethod
  def _resolve_effective_height_pt(
      height_pt: float | None, clearance_pt: float | None
  ) -> float | None:
    """Resolves effective vertical box height in points, expanding nominal 1-line placeholders (<50pt) when vertical clearance allows."""
    h_val = (
        float(height_pt)
        if (height_pt is not None and float(height_pt) > 0)
        else None
    )
    c_val = (
        float(clearance_pt)
        if (clearance_pt is not None and float(clearance_pt) > 0)
        else None
    )
    if h_val is not None and c_val is not None:
      if h_val < 50.0 and c_val > h_val:
        return min(180.0, max(h_val, c_val - 6.0))
      return min(h_val, c_val)
    return h_val if h_val is not None else c_val

  def _normalize_consultative_action_title(
      self, text: str, customer_name: str = ""
  ) -> str:
    """Normalizes bare imperative commands, leading '-ing' gerund fragments, and Title-Cased internal slide titles into crisp, Google Brand Voice & Tone Sentence-case headlines."""
    if not text or "\n" in text:
      return text
    cleaned = text.strip()
    words = cleaned.split()
    if len(words) < 2:
      return text

    # Pattern 1: "Uniting/Unifying/Combining X with Y" -> "X meets Y"
    m_unite = re.match(
        r"^(?:uniting|unifying|unite|unify|combining|combine|bridging|bridge)\s+(.+?)\s+(?:with|and)\s+(.+)$",
        cleaned,
        flags=re.IGNORECASE,
    )
    if m_unite:
      cleaned = f"{m_unite.group(1).strip()} meets {m_unite.group(2).strip()}"
      words = cleaned.split()

    # Pattern 2: "Turning/Turn/Shifting X into/to Y" -> "From X to Y"
    m_turn = re.match(
        r"^(?:turning|turn|transitioning|transition|shifting|shift|moving|move)\s+(?:from\s+)?(.+?)\s+(?:into|to)\s+(.+)$",
        cleaned,
        flags=re.IGNORECASE,
    )
    if m_turn and not m_unite:
      cleaned = f"From {m_turn.group(1).strip()} to {m_turn.group(2).strip()}"
      words = cleaned.split()

    # Pattern 3: "Reimagining/Redefining/Transforming X with/through/via Y"
    m_reimagine = re.match(
        r"^(?:reimagining|reimagine|redefining|redefine|reinventing|reinvent|transforming|transform)\s+(.+?)\s+(?:with|through|via|using)\s+(.+)$",
        cleaned,
        flags=re.IGNORECASE,
    )
    if m_reimagine and not m_unite and not m_turn:
      obj_phrase = m_reimagine.group(1).strip()
      actor_phrase = m_reimagine.group(2).strip().rstrip(".")
      actor_words = actor_phrase.split()
      if (
          1 <= len(actor_words) <= 4
          and actor_words[-1].lower().endswith("s")
          and not actor_words[-1].lower().endswith(("ss", "us", "is", "os"))
      ):
        cleaned = f"{actor_phrase} transform {obj_phrase}"
      else:
        cleaned = f"Next-generation {obj_phrase} with {actor_phrase}"
      words = cleaned.split()

    # Pattern 4: Replace leading imperative/gerund modifiers with crisp adjectives or strip throat-clearing filler verbs
    leading_to_adjective = {
        "automate": "Automated",
        "automating": "Automated",
        "unify": "Unified",
        "unifying": "Unified",
        "modernize": "Modern",
        "modernizing": "Modern",
        "streamline": "Streamlined",
        "streamlining": "Streamlined",
        "consolidate": "Consolidated",
        "consolidating": "Consolidated",
        "harmonize": "Harmonized",
        "harmonizing": "Harmonized",
        "optimize": "Optimized",
        "optimizing": "Optimized",
        "fortify": "Fortified",
        "fortifying": "Fortified",
        "strengthen": "Stronger",
        "strengthening": "Stronger",
        "accelerate": "Faster",
        "accelerating": "Faster",
    }
    throat_clearing_verbs = {
        "unlock",
        "unlocking",
        "scale",
        "scaling",
        "empower",
        "empowering",
        "deliver",
        "delivering",
        "transform",
        "transforming",
        "elevate",
        "elevating",
        "drive",
        "driving",
        "orchestrate",
        "orchestrating",
        "capture",
        "capturing",
        "reimagine",
        "reimagining",
        "redefine",
        "redefining",
        "reinvent",
        "reinventing",
        "pioneer",
        "pioneering",
        "operationalize",
        "operationalizing",
        "establish",
        "establishing",
        "activate",
        "activating",
        "advance",
        "advancing",
        "cultivate",
        "cultivating",
        "shape",
        "shaping",
        "expand",
        "expanding",
    }
    non_strippable_second_words = {
        "to",
        "with",
        "into",
        "from",
        "for",
        "in",
        "on",
        "at",
        "by",
        "of",
        "across",
        "through",
        "beyond",
        "up",
        "out",
        "it",
        "us",
        "them",
    }
    first_clean = words[0].lower().strip(",;:.!?\"'()-")
    if first_clean in leading_to_adjective:
      words[0] = leading_to_adjective[first_clean]
    elif (
        first_clean in throat_clearing_verbs
        and len(words) >= 5
        and words[1].lower().strip(",;:.!?\"'()-")
        not in non_strippable_second_words
    ):
      words = words[1:]

    preserve_proper = {
        "google": "Google",
        "cloud": "Cloud",
        "cloud's": "Cloud's",
        "gemini": "Gemini",
        "enterprise": "Enterprise",
        "bigquery": "BigQuery",
        "spanner": "Spanner",
        "alloydb": "AlloyDB",
        "antigravity": "Antigravity",
        "hypercomputer": "Hypercomputer",
        "workspace": "Workspace",
        "looker": "Looker",
        "apigee": "Apigee",
        "notebooklm": "NotebookLM",
        "imagen": "Imagen",
        "veo": "Veo",
        "chirp": "Chirp",
        "sec-palm": "Sec-PaLM",
        "chronicle": "Chronicle",
        "mandiant": "Mandiant",
        "firebase": "Firebase",
        "flutter": "Flutter",
        "android": "Android",
        "youtube": "YouTube",
        "waymo": "Waymo",
        "deepmind": "DeepMind",
        "dataflow": "Dataflow",
        "dataproc": "Dataproc",
        "pubsub": "Pub/Sub",
        "pub/sub": "Pub/Sub",
        "iceberg": "Iceberg",
        "apache": "Apache",
        "spark": "Spark",
        "kafka": "Kafka",
        "flink": "Flink",
        "airflow": "Airflow",
        "kubernetes": "Kubernetes",
        "titus": "Titus",
        "metaflow": "Metaflow",
        "snowflake": "Snowflake",
        "databricks": "Databricks",
        "teradata": "Teradata",
        "oracle": "Oracle",
        "sap": "SAP",
        "salesforce": "Salesforce",
        "servicenow": "ServiceNow",
        "workday": "Workday",
        "lifewear": "LifeWear",
        "ariake": "Ariake",
        "uniqlo": "Uniqlo",
        "uniqlo's": "Uniqlo's",
        "nvidia": "NVIDIA",
        "nvidia's": "NVIDIA's",
        "netflix": "Netflix",
        "netflix's": "Netflix's",
        "costco": "Costco",
        "wayfair": "Wayfair",
        "walmart": "Walmart",
        "spotify": "Spotify",
        "paypal": "PayPal",
        "carrefour": "Carrefour",
        "lowe's": "Lowe's",
        "target": "Target",
    }
    if customer_name:
      for tok in re.findall(r"[A-Za-z0-9']+", customer_name):
        preserve_proper[tok.lower()] = tok
        preserve_proper[f"{tok.lower()}'s"] = f"{tok}'s"

    # Preserve multi-word canonical Google Cloud product names when adjacent
    joined_lower = " ".join(w.lower().strip(",;:.!?") for w in words)
    preserve_indices = {0}
    multi_word_products = [
        ("model", "garden"),
        ("agent", "garden"),
        ("agent", "studio"),
        ("agent", "engine"),
        ("agent", "registry"),
        ("knowledge", "catalog"),
        ("code", "assist"),
        ("customer", "experience"),
    ]
    lower_tokens = [w.lower().strip(",;:.!?\"'()") for w in words]
    for i in range(len(lower_tokens) - 1):
      if (lower_tokens[i], lower_tokens[i + 1]) in multi_word_products:
        # Preserve "Gemini Enterprise for Customer Experience"
        if (lower_tokens[i], lower_tokens[i + 1]) == ("customer", "experience"):
          if (
              i >= 2
              and lower_tokens[i - 1] == "for"
              and lower_tokens[i - 2] == "enterprise"
          ):
            preserve_indices.add(i)
            preserve_indices.add(i + 1)
        else:
          preserve_indices.add(i)
          preserve_indices.add(i + 1)

    out_words = []
    after_colon = False
    for idx, w in enumerate(words):
      clean_w = w.strip(",;:.!?\"'()")
      low_w = clean_w.lower()
      # Keep first word, word right after colon/dash, all-caps acronyms (AI, ROI, CX, DTC, ERP, POS, SKU), camelCase (BigQuery, LifeWear), or proper nouns
      is_acronym = len(clean_w) >= 2 and clean_w.isupper()
      has_internal_cap = any(c.isupper() for c in clean_w[1:]) and any(
          c.islower() for c in clean_w
      )
      if (
          idx in preserve_indices
          or after_colon
          or is_acronym
          or has_internal_cap
          or low_w in preserve_proper
      ):
        if low_w in preserve_proper:
          lead_punct = w[: len(w) - len(w.lstrip(",;:.!?\"'()"))]
          trail_punct = w[len(w.rstrip(",;:.!?\"'()")) :]
          out_words.append(f"{lead_punct}{preserve_proper[low_w]}{trail_punct}")
        elif idx == 0 and w and w[0].islower():
          out_words.append(w[0].upper() + w[1:])
        else:
          out_words.append(w)
      elif "-" in clean_w:
        # Handle hyphenated Title-Case words like "Co-Innovation" -> "co-innovation"
        parts = w.split("-")
        norm_parts = []
        for p in parts:
          p_clean = p.strip(",;:.!?\"'()")
          p_low = p_clean.lower()
          if p_low in preserve_proper:
            lp = p[: len(p) - len(p.lstrip(",;:.!?\"'()"))]
            tp = p[len(p.rstrip(",;:.!?\"'()")) :]
            norm_parts.append(f"{lp}{preserve_proper[p_low]}{tp}")
          elif p_clean.isupper():
            norm_parts.append(p)
          else:
            norm_parts.append(p.lower())
        out_words.append("-".join(norm_parts))
      else:
        out_words.append(w.lower())
      after_colon = w.endswith((":", "—", "–"))

    return " ".join(out_words)

  def _strip_leading_section_number(
      self, text: str, font_size: float | None = None, is_action_title: bool = False
  ) -> str:
    """Strips standalone or inline section numbers (e.g. '02\\n', '04 Maximizing...', 'Section 2:') from slide titles."""
    if not text:
      return text
    cleaned = text.strip()
    lines = cleaned.split("\n")
    # 1. Strip standalone first-line section number (e.g. "02\nUnlocking...", "04\nMaximizing...", "Section 02\n")
    if len(lines) >= 2 and re.match(
        r"^\s*(?:0[1-9]|[1-9]\d?|section\s*\d+|part\s*\d+)[\.\:\-]?\s*$",
        lines[0],
        re.IGNORECASE,
    ):
      lines = lines[1:]
      cleaned = "\n".join(lines).strip()

    # 2. Strip inline leading zero-padded or 'Section X' prefix on line 0 (e.g. "04 Maximizing platform productivity")
    # Also strip 1-2 digit prefix ("1. ", "2 - ") on title/header shapes (fontSize >= 18 or is_action_title)
    if lines:
      first_line = lines[0].strip()
      first_line = re.sub(
          r"^\s*(?:0[1-9]|section\s*\d+|part\s*\d+)(?:[\.\:\-\s]+)",
          "",
          first_line,
          flags=re.IGNORECASE,
      ).strip()
      fs = float(font_size) if font_size is not None else 12.0
      if fs >= 18.0 or is_action_title:
        # Strip '1. Title' or '2: Title' while preserving stats like '74% of...', '10x...', '100M+...', '1 prompt...'
        if not re.match(r"^\d+(?:%|x\b|m\b|b\b|k\b|\+|\s+prompt\b)", first_line, re.IGNORECASE):
          first_line = re.sub(
              r"^\s*\d{1,2}[\.\:\-]\s+",
              "",
              first_line,
          ).strip()
      lines[0] = first_line
      cleaned = "\n".join(lines).strip()
    return cleaned

  def _trim_to_char_limit(
      self, text: str, max_len: int, is_title_or_header: bool = False
  ) -> str:
    """Cleanly trims text to <= max_len at sentence, clause, or word boundaries without dangling words or collapsing newlines."""
    if max_len <= 0 or len(text) <= max_len:
      return text

    # Strictly preserve multi-line / multi-bullet structure (\n) whenever present
    if "\n" in text:
      lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
      if len(lines) == 2:
        header = lines[0]
        body = lines[1]
        rem_budget = max_len - len(header) - 1
        if rem_budget >= 15:
          trimmed_body = self._trim_to_char_limit(
              body, rem_budget, is_title_or_header=False
          )
          return f"{header}\n{trimmed_body}"
      elif len(lines) > 2:
        header = lines[0]
        rest_lines = list(lines[1:])
        rem_budget = max(
            len(rest_lines) * 10, max_len - len(header) - len(rest_lines)
        )
        total_rest = sum(len(ln) for ln in rest_lines)
        if total_rest <= rem_budget:
          return "\n".join([header] + rest_lines)
        # Only trim the longest line(s) that exceed their proportional budget, leaving short lines untouched
        excess = total_rest - rem_budget
        out_rest = list(rest_lines)
        longest_idx = max(
            range(len(out_rest)), key=lambda idx: len(out_rest[idx])
        )
        if len(out_rest[longest_idx]) - excess >= 18:
          out_rest[longest_idx] = self._trim_to_char_limit(
              out_rest[longest_idx],
              len(out_rest[longest_idx]) - excess,
              is_title_or_header=False,
          )
          return "\n".join([header] + out_rest)
        total_rest = max(1, total_rest)
        out_lines = [header]
        for ln in rest_lines:
          ln_budget = max(14, int(rem_budget * (len(ln) / total_rest)))
          out_lines.append(
              self._trim_to_char_limit(ln, ln_budget, is_title_or_header=False)
          )
        return "\n".join(out_lines)

    clipped = text[:max_len].rstrip()
    dangling_words = {
        "&",
        "+",
        "/",
        "-",
        "–",
        "—",
        "and",
        "or",
        "the",
        "a",
        "an",
        "to",
        "for",
        "with",
        "without",
        "in",
        "of",
        "by",
        "on",
        "at",
        "from",
        "as",
        "into",
        "via",
        "across",
        "through",
        "using",
        "while",
        "between",
        "within",
        "towards",
        "toward",
        "compared",
        "versus",
        "vs",
        "vs.",
        "than",
        "including",
        "like",
        "whether",
        "despite",
        "although",
        "because",
        "since",
        "unless",
        "until",
        "per",
        "that",
        "which",
        "who",
        "whom",
        "whose",
        "where",
        "when",
        "is",
        "are",
        "be",
        "must",
        "can",
        "will",
        "should",
        "may",
        "might",
        "could",
        "would",
        "shall",
        "need",
        "needs",
        "under",
        "over",
        "beyond",
        "during",
        "before",
        "after",
        "around",
        "their",
        "your",
        "our",
        "its",
        "this",
        "these",
        "those",
        "each",
        "every",
        "all",
        "any",
        "some",
        "more",
        "most",
        "less",
        "very",
        "highly",
        "fully",
        "deeply",
        "newly",
        "dynamically",
        "seamless",
        "seamlessly",
        "dedicated",
        "provisioned",
        "cross-cloud",
        "multi-cloud",
        "global",
        "international",
        "worldwide",
        "real-time",
        "autonomous",
        "proprietary",
        "custom",
        "bespoke",
        "use",
        "multi-step",
        "supports",
        "enables",
        "complex",
        "digital",
        "delayed",
        "valuable",
        "wholesale",
        "native",
        "predictive",
        "actionable",
        "conversational",
        "unified",
        "siloed",
        "disparate",
        "fragmented",
        "automated",
        "governed",
        "scalable",
        "secure",
        "enterprise",
        "strategic",
        "operational",
        "commercial",
        "technical",
        "retail",
        "consumer",
        "customer",
        "hybrid",
        "shared",
        "intelligent",
        "agentic",
        "proactive",
        "personalized",
        "hyper-personalized",
        "end-to-end",
        "next-gen",
        "ai-powered",
        "cloud-native",
        "data-driven",
        "high-impact",
        "mission-critical",
        "enterprise-grade",
        "average",
        "inefficient",
        "phantom",
        "reusable",
        "joint",
        "existing",
        "legacy",
        "new",
        "key",
        "core",
        "main",
        "primary",
        "full",
        "high",
        "low",
        "fast",
        "rapid",
        "smart",
        "modern",
        "local",
        "single",
        "multiple",
        "various",
        "different",
        "specific",
        "certain",
        "other",
        "such",
        "both",
        "either",
        "neither",
        "create",
        "creates",
        "build",
        "builds",
        "drive",
        "drives",
        "deliver",
        "delivers",
        "delivering",
        "enable",
        "enabling",
        "support",
        "supporting",
        "provide",
        "provides",
        "providing",
        "ensure",
        "ensures",
        "ensuring",
        "optimize",
        "optimizes",
        "optimizing",
        "recommend",
        "recommends",
        "recommending",
        "detect",
        "detects",
        "detecting",
        "trap",
        "traps",
        "connect",
        "connects",
        "connecting",
        "unify",
        "unifies",
        "unifying",
        "enrich",
        "enriches",
        "enriching",
        "launch",
        "launches",
        "launching",
        "empower",
        "empowers",
        "empowering",
        "deploy",
        "deploys",
        "deploying",
        "establish",
        "establishes",
        "establishing",
        "standardize",
        "standardizes",
        "automate",
        "automates",
        "automating",
        "streamline",
        "streamlines",
        "streamlining",
        "consolidate",
        "consolidates",
        "consolidating",
        "expand",
        "expands",
        "expanding",
        "increase",
        "increases",
        "increasing",
        "reduce",
        "reduces",
        "reducing",
        "accelerate",
        "accelerates",
        "accelerating",
        "transform",
        "transforms",
        "transforming",
        "compress",
        "compresses",
        "compressing",
        "athletic",
        "operating",
        "financial",
        "promotional",
        "omnichannel",
        "frictionless",
        "cultural",
        "gross",
        "net",
        "working",
    }

    if not is_title_or_header and max_len >= 32:
      # 1. Try natural sentence or punctuation boundary first if it retains >= 50% of max_len
      for sep, add_period in [
          (". ", True),
          ("; ", True),
          (" — ", True),
          (" – ", True),
          (": ", True),
          (", ", True),
      ]:
        idx = clipped.rfind(sep)
        if idx >= int(max_len * 0.50):
          candidate = clipped[:idx].rstrip(",;:-—–&+/ ")
          cand_words = candidate.split()
          while (
              len(cand_words) > 1
              and cand_words[-1].lower().strip(",;:-—.&+/") in dangling_words
          ):
            cand_words.pop()
          candidate = " ".join(cand_words).rstrip(",;:-—–&+/ ")
          if candidate:
            if add_period and not candidate.endswith((".", "!", "?")):
              if len(candidate) + 1 <= max_len:
                candidate += "."
            return candidate

      # 2. Try trailing comparative / participial sub-clause boundary near the end of the budget
      clause_seps = (
          " compared to ",
          " compared with ",
          " relative to ",
          " versus ",
          " vs. ",
          " vs ",
          " while ",
          " enabling ",
          " driving ",
          " ensuring ",
          " reducing ",
          " accelerating ",
          " delivering ",
          " unlocking ",
          " powering ",
          " connecting ",
          " unifying ",
          " transforming ",
          " automating ",
          " scaling ",
          " supporting ",
          " where ",
          " which ",
      )
      best_clause_idx = -1
      for c_sep in clause_seps:
        c_idx = clipped.lower().rfind(c_sep)
        if c_idx >= int(max_len * 0.62) and c_idx > best_clause_idx:
          best_clause_idx = c_idx
      if best_clause_idx >= int(max_len * 0.62):
        candidate = clipped[:best_clause_idx].rstrip(",;:-—–&+/ ")
        cand_words = candidate.split()
        while (
            len(cand_words) > 1
            and cand_words[-1].lower().strip(",;:-—.&+/") in dangling_words
        ):
          cand_words.pop()
        candidate = " ".join(cand_words).rstrip(",;:-—–&+/ ")
        if len(cand_words) >= 3:
          if (
              text.endswith(".")
              and not candidate.endswith((".", "!", "?"))
              and len(candidate) + 1 <= max_len
          ):
            candidate += "."
          return candidate

    # 3. Fall back to word boundary trimming and strip trailing dangling modifiers/prepositions/verbs
    if " " in clipped:
      words = text.split()
      trimmed = []
      cur = 0
      reserve_period = 1 if (not is_title_or_header and text.endswith(".")) else 0
      effective_max = max(1, max_len - reserve_period)
      for w in words:
        sep_len = 1 if trimmed else 0
        if cur + sep_len + len(w) <= effective_max:
          trimmed.append(w)
          cur += sep_len + len(w)
        else:
          break
      while (
          len(trimmed) > 1
          and trimmed[-1].lower().strip(",;:-—.&+/") in dangling_words
      ):
        trimmed.pop()
      if trimmed:
        result = " ".join(trimmed).rstrip(",;:-—&+/ ")
        if reserve_period and not result.endswith((".", "!", "?")) and len(result) + 1 <= max_len:
          result += "."
        return result

    return clipped

  @staticmethod
  def replace_cymbal_with_customer(
      text: str, customer_name: str | None = None
  ) -> str:
    """Replaces all occurrences of Google Cloud's fictional 'Cymbal' white-label brand with the target customer."""
    if not text or "cymbal" not in text.lower():
      return text
    cust = str(customer_name or "").strip()
    if not cust or cust.lower() in (
        "-",
        "none",
        "null",
        "cymbal",
        "the target enterprise",
    ):
      return text
    slug = re.sub(r"[^a-z0-9]", "", cust.lower()) or "enterprise"
    out = text
    # 1. Replace email domains & URLs
    out = re.sub(r"\bcymbal\.com\b", f"{slug}.com", out, flags=re.IGNORECASE)
    out = re.sub(r"@cymbal\b", f"@{slug}", out, flags=re.IGNORECASE)
    # 2. Replace compound white-label sub-brands (unless followed by an operational document/unit noun like "Operations Manual")
    out = re.sub(
        r"\bCymbal\s+(?:Superstore|Shops|Direct|FinTech|Global|Corp|Inc|Group|Enterprises)\b",
        cust,
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"\bCymbal\s+(?:Retail|Bank|Health|Sports|Air|Beverage|Groceries|Coffee|Media|Auto|Telecom|Energy|Logistics|Insurance)\b(?!\s+(?:Operations|Policy|Policies|Manual|Handbook|Standards|Guidelines|Playbook|Store|Stores|Locations|Branches|Team|Teams|Associates|Network|Supply|Catalog|Platform|App|Portal|Division))",
        cust,
        out,
        flags=re.IGNORECASE,
    )
    # 3. Replace possessive and standalone Cymbal
    out = re.sub(r"\bCymbal's\b", f"{cust}'s", out, flags=re.IGNORECASE)
    out = re.sub(r"\bCymbal’s\b", f"{cust}’s", out, flags=re.IGNORECASE)
    out = re.sub(r"\bCymbal\b", cust, out, flags=re.IGNORECASE)
    return out

  def _sanitize_output(
      self,
      text: str,
      is_cover_slide: bool = True,
      customer_name: str = "",
      original_len: int = 0,
      is_action_title: bool = False,
      font_size: float | None = None,
      width_pt: float | None = None,
      clearance_pt: float | None = None,
      height_pt: float | None = None,
  ) -> str:
    """Removes enclosing quotes, markdown code fences, leading slide numbers, and enforces strict bounding box length and algebraic height (H_req <= H_card) limits."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
      lines = cleaned.splitlines()
      if len(lines) >= 2:
        cleaned = "\n".join(lines[1:-1]).strip()
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (
        cleaned.startswith("'") and cleaned.endswith("'")
    ):
      cleaned = cleaned[1:-1].strip()

    # Strip standalone or inline leading slide/section numbers (e.g. "04\n", "04 Maximizing...", "Section 04\n")
    cleaned = self._strip_leading_section_number(
        cleaned, font_size=font_size, is_action_title=is_action_title
    )

    # Deterministic October 2026 Canonical Google Cloud & Gemini Brand Unification Sanitizer (Enterprise-Brand-Unification)
    for legacy_pat, modern_repl in [
        (
            r"\b(?:the\s+)?Gemini\s+Enterprise\s+app(?:lication)?,\s*built\s+on\s+(?:the\s+)?(?:Gemini\s+Enterprise\s+)?Agent\s+Platform\b",
            "Gemini, built on the Gemini platform",
        ),
        (
            r"\bAntigravity\s+with\s+(?:the\s+app|(?:the\s+)?(?:Gemini\s+Enterprise\s+)?Agent\s+Platform)\b",
            "Antigravity in Gemini platform",
        ),
        (
            r"\bAntigravity\s+in\s+Gemini\s+Enterprise\b",
            "Antigravity in Gemini platform",
        ),
        (
            r"\b(?:GEAP|Gemini\s+Enterprise|Gemini\s+platform)\s+Model\s+Garden\b",
            "Model Garden in Gemini platform",
        ),
        (
            r"\bModel\s+Garden\s+in\s+Gemini\s+Enterprise\b",
            "Model Garden in Gemini platform",
        ),
        (
            r"\bagent\s+runtime\s+in\s+Gemini\s+Enterprise\b",
            "agent runtime in Gemini platform",
        ),
        (
            r"\bGemini\s+Enterprise\s+for\s+Financial\s+Services\b",
            "Gemini for financial services",
        ),
        (
            r"\bGemini\s+Enterprise\s+for\s+Legal\b",
            "Gemini for legal",
        ),
        (
            r"\b(?:Gemini\s+Enterprise\s+for\s+(?:Customer\s+Experience|CX)|GECX)\b",
            "Gemini for customer experience",
        ),
        (
            r"\bGemini\s+Enterprise\s+for\s+Healthcare\b",
            "Gemini for healthcare",
        ),
        (
            r"\bGemini\s+Enterprise\s+for\s+Life\s+Sciences\b",
            "Gemini for life sciences",
        ),
        (
            r"\bGemini\s+Enterprise\s+for\s+Government(?:\s+Services)?\b",
            "Gemini for government services",
        ),
        (
            r"\bGemini\s+Enterprise\s+for\s+Retail\b",
            "Gemini for retail",
        ),
        (
            r"\bGemini\s+Enterprise\s+for\s+Marketing\b",
            "Gemini for marketing",
        ),
        (r"\bGemini\s+Enterprise\s+Agent\s+Platform\b", "Gemini platform"),
        (r"\b(?:the\s+)?Agent\s+Platform\b", "Gemini platform"),
        (r"\bGEAP\b", "Gemini platform"),
        (
            r"\b(?:the\s+)?Gemini\s+Enterprise\s+app(?:lication)?\b",
            "Gemini",
        ),
        (r"\b(?:the\s+)?GE\s+app\b", "Gemini"),
        (r"\bSobi\b", "Gemini"),
        (
            r"(?<!Apache\s)\bSpark\b(?!\s+(?:SQL|Streaming|MLlib|clusters|jobs))",
            "Gemini",
        ),
        (r"\bGoogle\s+Cloud's\s+Gemini\s+agent\b", "Gemini"),
        (r"\bGemini\s+Enterprise\s+platform\b", "Gemini platform"),
        (r"\bGemini\s+Platform\b", "Gemini platform"),
        (
            r"\b(?:app\s+users|platform\s+customers|Gemini\s+Enterprise\s+users)\b",
            "Gemini users",
        ),
        (r"\b[Pp]owered\s+by\s+Gemini\b(?!\s+Enterprise)", "Built with Gemini"),
        (r"\bVertex\s+AI\s+Agent\s+Builder\b", "Google ADK"),
        (r"\bVertex\s+AI\s+Search\b", "Gemini"),
        (r"\bVertex\s+AI\b", "Gemini platform"),
        (r"\bDataplex\b", "Knowledge Catalog"),
        (r"\bAI\s+Supercompute(?:r)?\b", "AI Hypercomputer"),
        (r"\b(?:Duet\s+AI|Agentspace)\b", "Gemini"),
        (r"\biceberg\b", "Iceberg"),
        (r"\btitus\b", "Titus"),
        (r"\bmetaflow\b", "Metaflow"),
        (r"\bbigquery\b", "BigQuery"),
        (r"\balloydb\b", "AlloyDB"),
    ]:
      cleaned = re.sub(legacy_pat, modern_repl, cleaned, flags=re.IGNORECASE)

    # Deterministic Cymbal White-Label Placeholder Brand Replacement
    cleaned = self.replace_cymbal_with_customer(cleaned, customer_name)

    if not is_cover_slide and customer_name and len(cleaned) <= 60 and "\n" not in cleaned:
      # Strip trailing " for [Customer]" or " with [Customer]" from internal slide titles
      pattern = rf"\s+(?:for|with)\s+{re.escape(customer_name)}\s*$"
      cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

    # Normalize Cover Slide primary title to modern, concise (<=28 chars), colon-free Sentence-case headline for 68pt typography
    if (
        is_cover_slide
        and cleaned
        and "\n" not in cleaned
        and (
            is_action_title
            or (font_size is not None and float(font_size) >= 48.0)
        )
    ):
      from agents.workflows.outline_workflow import OutlineWorkflow

      cleaned = OutlineWorkflow.normalize_modern_cover_title(
          cleaned, customer_name=customer_name
      )

    # Convert Title-Case and bare imperative commands on internal slide titles into consultative Sentence-case headlines
    norm_delta = 0
    if (
        is_action_title
        and not is_cover_slide
        and cleaned
        and "\n" not in cleaned
    ):
      pre_norm_len = len(cleaned)
      cleaned = self._normalize_consultative_action_title(
          cleaned, customer_name=customer_name
      )
      norm_delta = max(0, len(cleaned) - pre_norm_len)

    # Strict Font-Size-Aware & Pre-Batch Algebraic Text-Height Gate (H_req <= H_card)
    if original_len > 0:
      _, hard_max_len = self._compute_char_budget(
          original_len,
          font_size=font_size,
          is_action_title=is_action_title,
          width_pt=width_pt,
          clearance_pt=clearance_pt,
          height_pt=height_pt,
      )
      if is_action_title and norm_delta > 0:
        hard_max_len += norm_delta
      is_header_or_title = bool(
          "\n" not in cleaned
          and (
              is_action_title
              or (
                  font_size is not None
                  and float(font_size) >= 18.0
                  and original_len <= 90
              )
              or original_len <= 45
          )
      )
      if (
          not is_action_title
          and width_pt is not None
          and float(width_pt) > 0
          and (
              (height_pt is not None and float(height_pt) > 0)
              or (clearance_pt is not None and float(clearance_pt) > 0)
          )
      ):
        fs_val = float(font_size) if font_size is not None else 12.0
        eff_h_card = (
            self._resolve_effective_height_pt(height_pt, clearance_pt) or 0.0
        )
        alg_cap = self.compute_algebraic_char_capacity(
            width_pt=float(width_pt),
            height_pt=eff_h_card,
            font_size=fs_val,
        )
        if eff_h_card < 55.0 and clearance_pt is None:
          # Nominal thin (<55pt) unconstrained text box: never truncate below original_len
          hard_max_len = max(
              original_len,
              min(alg_cap, max(int(original_len * 1.15), original_len + 10)),
          )
        else:
          # Card box (>=55pt) or clearance-bounded shape: allow up to +15% (+10 chars) only within alg_cap so H_req <= H_card
          hard_max_len = min(
              alg_cap,
              max(hard_max_len, int(original_len * 1.15), original_len + 10),
          )
        if len(cleaned) > hard_max_len:
          cleaned = self._trim_to_char_limit(
              cleaned, hard_max_len, is_title_or_header=is_header_or_title
          )
      else:
        if len(cleaned) > hard_max_len:
          cleaned = self._trim_to_char_limit(
              cleaned, hard_max_len, is_title_or_header=is_header_or_title
          )

    return cleaned

  def _detect_developer_knowledge_intent(
      self, criteria: str, texts: list[str], context: dict | None = None
  ) -> tuple[bool, str]:
    """Detects if slide content or criteria references Google Cloud products, Gemini models, or technical architectures."""
    context = context or {}
    criteria_lower = (criteria or "").lower()
    full_content = (
        criteria_lower
        + " "
        + " ".join(texts)
        + " "
        + str(context.get("product", ""))
        + " "
        + str(context.get("solution", ""))
    ).lower()

    # 1. Gemini Models & AI Foundation Features
    is_model_update = any(
        k in criteria_lower
        for k in (
            "latest model",
            "upgrade model",
            "update model",
            "newest model",
            "model version",
            "latest gemini",
            "upgrade gemini",
        )
    )
    if is_model_update:
      return True, "latest Gemini models overview"

    if any(
        k in full_content
        for k in (
            "image generation",
            "image model",
            "flash image",
            "pro image",
            "image generation resolution",
            "nano banana",
        )
    ):
      return True, "Google Cloud active image generation models documentation"

    if any(k in full_content for k in ("veo", "video generation", "video model")):
      return True, "Google Cloud active video generation models documentation"

    # 2. Specific Google Cloud Products, Platforms & Services
    gcp_product_catalog = [
        "gemini enterprise agent platform",
        "google cloud agent engine",
        "knowledge catalog",
        "ai hypercomputer",
        "agentic data cloud",
        "gemini enterprise",
        "agent studio",
        "agent engine",
        "model garden",
        "discovery engine",
        "code assist",
        "biglake",
        "iceberg",
        "lakehouse",
        "dataplex",
        "bigquery",
        "cloud spanner",
        "alloydb",
        "cloud sql",
        "dataproc",
        "dataflow",
        "looker",
        "pub/sub",
        "pubsub",
        "cloud storage",
        "gcs",
        "bigtable",
        "gke",
        "cloud run",
        "compute engine",
        "tpu",
        "gpu",
        "anthos",
        "beyondcorp",
        "security command center",
        "mandiant",
        "secops",
        "chronicle",
        "apigee",
        "vpc-sc",
        "cmek",
        "vertex ai",
        "vertex",
        "workspace studio",
        "agentic",
    ]
    matched_products = [p for p in gcp_product_catalog if p in full_content]

    # Explicit product/solution passed in context
    explicit_product = context.get("product") or context.get("solution")

    if matched_products:
      primary = matched_products[0]
      if "gemini" in primary:
        return True, f"Google Cloud {primary}"
      return True, f"Google Cloud {primary} overview and architecture"

    if explicit_product:
      return True, f"Google Cloud {explicit_product} architecture"

    # 3. Technical Architectures & Engineering Elements
    tech_keywords = [
        "technical architecture",
        "system blueprint",
        "ingestion pipeline",
        "api limit",
        "service quota",
        "cloud adoption framework",
    ]
    matched_tech = [t for t in tech_keywords if t in full_content]
    if matched_tech and any(
        k in full_content for k in ("google", "gcp", "cloud", "vertex")
    ):
      return True, f"Google Cloud {matched_tech[0]}"

    return False, ""

  def _is_internal_enablement_slide(self, slide: dict) -> bool:
    """Detects if a slide is an internal sales enablement briefing/guidance slide."""
    if not isinstance(slide, dict):
      return False

    # Check slide title, name, or metadata
    slide_name = str(
        slide.get("slide_name")
        or slide.get("name")
        or slide.get("title")
        or ""
    ).lower().strip()
    if (
        "internal context" in slide_name
        or "internal guidance" in slide_name
        or "remove this slide" in slide_name
    ):
      return True

    # Check text inside all shapes
    all_texts = []
    if "data" in slide and isinstance(slide["data"], list):
      for s in slide["data"]:
        if isinstance(s, dict) and s.get("text"):
          all_texts.append(str(s.get("text")).lower().strip())
    else:
      def extract(obj):
        if isinstance(obj, dict):
          for k, v in obj.items():
            if k.lower() in ("text", "content") and isinstance(v, str):
              all_texts.append(v.lower().strip())
            else:
              extract(v)
        elif isinstance(obj, list):
          for item in obj:
            extract(item)
      extract(slide)

    combined_text = " ".join(all_texts)
    if (
        "internal context:" in combined_text
        or combined_text.startswith("internal context")
        or "please remove this slide before you present" in combined_text
    ):
      return True
    if (
        "opportunity id" in combined_text
        and "target customer" in combined_text
        and "sales plays" in combined_text
    ):
      return True
    if "who to contact" in combined_text and ("coaching videos" in combined_text or "target persona" in combined_text or "additional resources" in combined_text):
      return True

    return False

  def is_closing_slide(self, slide: dict, texts: list[str] = None) -> bool:
    """Detects standalone Closing / Thank You slides (0% Immutable)."""
    if not isinstance(slide, dict):
      return False
    job = str(
        slide.get("slide_job")
        or slide.get("taxonomy", {}).get("slide_job")
        or ""
    ).lower()
    if job in ("closing_slide", "thank_you", "thankyou", "closing", "q_and_a"):
      return True

    title_str = (
        str(
            slide.get("title")
            or slide.get("slide_title")
            or slide.get("name")
            or ""
        )
        .strip()
        .lower()
    )
    clean_title = re.sub(r"[^a-zA-Z\s]", "", title_str).strip()
    if clean_title in (
        "thank you",
        "thank you!",
        "thanks",
        "questions",
        "qa",
        "q and a",
        "contact us",
        "thank you for your time",
    ):
      return True

    combined_texts = []
    if texts:
      combined_texts.extend([str(t).strip() for t in texts if str(t).strip()])
    else:

      def extract(obj):
        if isinstance(obj, dict):
          for k, v in obj.items():
            if k.lower() in ("text", "content") and isinstance(v, str):
              combined_texts.append(v.strip())
            else:
              extract(v)
        elif isinstance(obj, list):
          for item in obj:
            extract(item)

      extract(slide)

    clean_all = " ".join(
        [re.sub(r"[^a-zA-Z\s]", "", t).strip().lower() for t in combined_texts]
    )
    if any(
        k in clean_all
        for k in (
            "thank you",
            "thankyou",
            "thanks",
            "questions",
            "q and a",
            "q a",
            "contact us",
        )
    ):
      return True
    return False

  def transform_internal_enablement_slide(
      self, slide: dict, context: dict | None = None, criteria: str = ""
  ) -> dict:
    """Updates only dynamic Column 2 metadata fields (Target Customer, Industry, User Prompt), locking all banner, button, and Column 1 labels."""
    context = context or {}
    prompt_source = str(
        criteria
        or context.get("business_context")
        or context.get("user_request")
        or ""
    ).strip()
    extracted = extract_entities_from_user_prompt(prompt_source)

    cust_name = str(
        context.get("customer_name")
        or extracted.get("customer_name")
        or context.get("customer")
        or ""
    ).strip()
    industry = str(
        context.get("industry") or extracted.get("industry") or ""
    ).strip()
    audience = str(
        context.get("audience") or extracted.get("audience") or ""
    ).strip()
    sales_play = str(
        context.get("salesPlay") or extracted.get("sales_play") or ""
    ).strip()
    opportunity_id = str(
        context.get("opportunity_id") or extracted.get("opportunity_id") or ""
    ).strip()
    user_prompt = prompt_source

    if not cust_name and "hdfc" in prompt_source.lower():
      cust_name = "HDFC Bank"
    elif cust_name.lower() == "hdfc bank" or cust_name.lower() == "hdfc":
      cust_name = "HDFC Bank"

    if not industry and (
        "financial" in prompt_source.lower()
        or "banking" in prompt_source.lower()
        or "fsi" in prompt_source.lower()
    ):
      industry = "Financial Services"

    if not audience:
      if (
          "financial" in prompt_source.lower()
          or "banking" in prompt_source.lower()
          or "hdfc" in prompt_source.lower()
      ):
        audience = "C-Level & Line of Business Executives"
      else:
        audience = "Executive Leadership & Technical Decision Makers"

    if not sales_play:
      if (
          "bigquery" in prompt_source.lower()
          or "data" in prompt_source.lower()
          or "analytics" in prompt_source.lower()
      ):
        sales_play = "Smart Analytics & Data Modernization"
      else:
        sales_play = "Cloud Modernization & AI Adoption"

    print(
        "[TextTransformerWorkflow] Customizing Internal Context metadata:"
        f" Customer='{cust_name}', Industry='{industry}',"
        f" Audience='{audience}', SalesPlay='{sales_play}',"
        f" OppID='{opportunity_id}'..."
    )

    # Format 1: slide has "tables" dict
    tables_dict = slide.get("tables", {})
    if isinstance(tables_dict, dict) and tables_dict:
      for table_id, table_cells in tables_dict.items():
        if not isinstance(table_cells, dict):
          continue
        for cell_pos, segs in list(table_cells.items()):
          if not isinstance(segs, dict):
            continue
          parts = cell_pos.split("_")
          if len(parts) != 2:
            continue
          r_idx = parts[0]
          cell_text = (
              " ".join([
                  str(v.get("Text", ""))
                  for v in segs.values()
                  if isinstance(v, dict)
              ])
              .strip()
              .lower()
          )
          val_pos = f"{r_idx}_1"
          val_segs = table_cells.get(val_pos)

          is_cust_row = any(
              k in cell_text
              for k in (
                  "target customer",
                  "customer",
                  "zielkunde",
                  "目标客户",
                  "client",
              )
          )
          is_ind_row = any(
              k in cell_text
              for k in ("industry", "branche", "行业", "sector", "vertical")
          )
          is_prompt_row = any(
              k in cell_text
              for k in (
                  "user prompt",
                  "user-prompt",
                  "prompt",
                  "用户提示",
                  "business context",
              )
          )
          is_opp_row = any(
              k in cell_text
              for k in (
                  "opportunity id",
                  "opportunity-id",
                  "opportunity",
                  "opp id",
                  "er number",
                  "er id",
                  "业务机会",
              )
          )
          is_aud_row = any(
              k in cell_text
              for k in ("audience", "zielgruppe", "受众", "persona")
          )
          is_sp_row = any(
              k in cell_text
              for k in (
                  "sales plays",
                  "sales play",
                  "sales-play",
                  "销售策略",
                  "vertriebsstrategie",
              )
          )
          is_next_row = any(
              k in cell_text
              for k in ("next steps", "nächste schritte", "后续步骤")
          )

          if is_cust_row:
            if cust_name:
              if not val_segs:
                val_segs = {"0": {"Text": "", "HadNewline": False}}
                table_cells[val_pos] = val_segs
              self._set_shape_dict_text(val_segs, cust_name)
          elif is_ind_row:
            if industry:
              if not val_segs:
                val_segs = {"0": {"Text": "", "HadNewline": False}}
                table_cells[val_pos] = val_segs
              self._set_shape_dict_text(val_segs, industry)
          elif is_prompt_row:
            if user_prompt:
              if not val_segs:
                val_segs = {"0": {"Text": "", "HadNewline": False}}
                table_cells[val_pos] = val_segs
              self._set_shape_dict_text(val_segs, user_prompt)
          elif is_opp_row:
            if opportunity_id:
              if not val_segs:
                val_segs = {"0": {"Text": "", "HadNewline": False}}
                table_cells[val_pos] = val_segs
              self._set_shape_dict_text(val_segs, opportunity_id)
          elif is_aud_row:
            if audience:
              if not val_segs:
                val_segs = {"0": {"Text": "", "HadNewline": False}}
                table_cells[val_pos] = val_segs
              self._set_shape_dict_text(val_segs, audience)
          elif is_sp_row:
            if sales_play:
              if not val_segs:
                val_segs = {"0": {"Text": "", "HadNewline": False}}
                table_cells[val_pos] = val_segs
              self._set_shape_dict_text(val_segs, sales_play)
          elif is_next_row:
            fixed_next_steps = (
                "Edit your deck with the PitchGen sidebar: “Extensions →"
                " PitchGen → Edit my Presentation”\nLearn more about PitchGen"
                " in CloudHub"
            )
            if not val_segs:
              val_segs = {"0": {"Text": "", "HadNewline": False}}
              table_cells[val_pos] = val_segs
            self._set_shape_dict_text(val_segs, fixed_next_steps)

    # Format 2: slide has "shapes" dict
    shapes_dict = slide.get("shapes", {})
    if isinstance(shapes_dict, dict) and shapes_dict:
      shape_keys = list(shapes_dict.keys())
      for i, sh_id in enumerate(shape_keys):
        segs = shapes_dict[sh_id]
        if not isinstance(segs, dict):
          continue
        sh_text = (
            " ".join([
                str(v.get("Text", ""))
                for v in segs.values()
                if isinstance(v, dict)
            ])
            .strip()
            .lower()
        )
        next_sh_id = shape_keys[i + 1] if i + 1 < len(shape_keys) else None

        is_cust_sh = any(
            k in sh_text
            for k in (
                "target customer",
                "customer",
                "zielkunde",
                "目标客户",
                "client",
            )
        )
        is_ind_sh = any(
            k in sh_text
            for k in ("industry", "branche", "行业", "sector", "vertical")
        )
        is_prompt_sh = any(
            k in sh_text
            for k in (
                "user prompt",
                "user-prompt",
                "prompt",
                "用户提示",
                "business context",
            )
        )
        is_opp_sh = any(
            k in sh_text
            for k in (
                "opportunity id",
                "opportunity-id",
                "opportunity",
                "opp id",
                "er number",
                "er id",
                "业务机会",
            )
        )
        is_aud_sh = any(
            k in sh_text for k in ("audience", "zielgruppe", "受众", "persona")
        )
        is_sp_sh = any(
            k in sh_text
            for k in (
                "sales plays",
                "sales play",
                "sales-play",
                "销售策略",
                "vertriebsstrategie",
            )
        )
        is_next_sh = any(
            k in sh_text for k in ("next steps", "nächste schritte", "后续步骤")
        )

        if is_cust_sh and next_sh_id:
          self._set_shape_dict_text(shapes_dict[next_sh_id], cust_name)
        elif is_ind_sh and next_sh_id:
          if industry:
            self._set_shape_dict_text(shapes_dict[next_sh_id], industry)
        elif is_prompt_sh and next_sh_id:
          if user_prompt:
            self._set_shape_dict_text(shapes_dict[next_sh_id], user_prompt)
        elif is_opp_sh and next_sh_id:
          self._set_shape_dict_text(shapes_dict[next_sh_id], opportunity_id)
        elif is_aud_sh and next_sh_id:
          if audience:
            self._set_shape_dict_text(shapes_dict[next_sh_id], audience)
        elif is_sp_sh and next_sh_id:
          if sales_play:
            self._set_shape_dict_text(shapes_dict[next_sh_id], sales_play)
        elif is_next_sh and next_sh_id:
          fixed_next_steps = (
              "Edit your deck with the PitchGen sidebar: “Extensions → PitchGen"
              " → Edit my Presentation”\nLearn more about PitchGen in CloudHub"
          )
          self._set_shape_dict_text(shapes_dict[next_sh_id], fixed_next_steps)

    # Format 3: slide has "data" list
    data_list = slide.get("data", [])
    if isinstance(data_list, list) and data_list:
      for i, item in enumerate(data_list):
        if not isinstance(item, dict):
          continue
        t_val = str(item.get("text", "")).strip().lower()
        next_item = (
            data_list[i + 1]
            if i + 1 < len(data_list) and isinstance(data_list[i + 1], dict)
            else None
        )

        is_cust_d = any(
            k in t_val
            for k in (
                "target customer",
                "customer",
                "zielkunde",
                "目标客户",
                "client",
            )
        )
        is_ind_d = any(
            k in t_val
            for k in ("industry", "branche", "行业", "sector", "vertical")
        )
        is_prompt_d = any(
            k in t_val
            for k in (
                "user prompt",
                "user-prompt",
                "prompt",
                "用户提示",
                "business context",
            )
        )
        is_opp_d = any(
            k in t_val
            for k in (
                "opportunity id",
                "opportunity-id",
                "opportunity",
                "opp id",
                "er number",
                "er id",
                "业务机会",
            )
        )
        is_aud_d = any(
            k in t_val for k in ("audience", "zielgruppe", "受众", "persona")
        )
        is_sp_d = any(
            k in t_val
            for k in (
                "sales plays",
                "sales play",
                "sales-play",
                "销售策略",
                "vertriebsstrategie",
            )
        )
        is_next_d = any(
            k in t_val for k in ("next steps", "nächste schritte", "后续步骤")
        )

        if is_cust_d and next_item:
          next_item["text"] = cust_name
        elif is_ind_d and next_item:
          if industry:
            next_item["text"] = industry
        elif is_prompt_d and next_item:
          if user_prompt:
            next_item["text"] = user_prompt
        elif is_opp_d and next_item:
          next_item["text"] = opportunity_id
        elif is_aud_d and next_item:
          if audience:
            next_item["text"] = audience
        elif is_sp_d and next_item:
          if sales_play:
            next_item["text"] = sales_play
        elif is_next_d and next_item:
          next_item["text"] = (
              "Edit your deck with the PitchGen sidebar: “Extensions → PitchGen"
              " → Edit my Presentation”\nLearn more about PitchGen in CloudHub"
          )

    return slide

  def _set_shape_dict_text(self, shape_segs: dict, new_text: str):
    """Sets text in a shape segments dictionary, clearing trailing segments."""
    if not isinstance(shape_segs, dict):
      return
    sorted_k = sorted(
        shape_segs.keys(), key=lambda x: int(x) if str(x).isdigit() else x
    )
    if "0" in shape_segs:
      shape_segs["0"]["Text"] = new_text
    elif sorted_k:
      shape_segs[sorted_k[0]]["Text"] = new_text
    for sk in sorted_k[1:]:
      if isinstance(shape_segs[sk], dict):
        shape_segs[sk]["Text"] = ""

  def _fetch_developer_knowledge_grounding(
      self, criteria: str, texts: list[str], context: dict | None = None
  ) -> tuple[str, bool]:
    """Dynamically detects technical GCP/Gemini intent and queries Developer Knowledge API when relevant."""
    should_fetch, search_query = self._detect_developer_knowledge_intent(
        criteria, texts, context
    )
    if not should_fetch:
      return "", False

    if search_query in self._dk_cache:
      cached_results = self._dk_cache[search_query]
      if cached_results:
        return (
            f"\nAUTHORITATIVE DEVELOPER KNOWLEDGE API GROUNDING (CACHED):\n{cached_results}\n",
            True,
        )
      return "", False

    try:
      print(
          f"[TextTransformerWorkflow] -> Technical/GCP/Gemini intent detected. Querying Developer Knowledge API for: '{search_query}'"
      )
      results = self.dk_workflow.execute(search_query)
      if results and not results.startswith("Failed to retrieve"):
        self._dk_cache[search_query] = results
        print(
            f"[TextTransformerWorkflow] -> Grounded with Developer Knowledge API ({len(results)} chars)."
        )
        return (
            f"\nAUTHORITATIVE DEVELOPER KNOWLEDGE API GROUNDING:\n{results}\n",
            True,
        )
      else:
        self._dk_cache[search_query] = ""
    except Exception as e:
      self._dk_cache[search_query] = ""
      print(
          f"[TextTransformerWorkflow] Warning: Developer Knowledge query failed: {e}"
      )
    return "", False

  def execute(
      self,
      text: str,
      criteria: str = "Improve clarity and professional tone",
      context: dict | None = None,
      extra_grounding: str = "",
      slide_name: str = "",
      slide_data: dict | None = None,
  ) -> str:
    """Transforms text based on edit/polishing criteria, account context, and domain knowledge skills."""
    if not text or not text.strip():
      return text

    # Dynamically query Developer Knowledge API and load product_knowledge only when technical/GCP/Gemini intent is detected
    dk_grounding, dk_triggered = self._fetch_developer_knowledge_grounding(
        criteria, [text], context
    )

    extra_skills = ["product_knowledge"]
    skill_context = get_matching_skill_instructions(
        f"{criteria} {text}", always_include=extra_skills
    )
    resolved_job, throttling_rules, intensity = self.resolve_slide_job(
        texts=[text],
        slide_data=slide_data,
        criteria=criteria,
        context=context,
    )
    original_len = len(text)
    primary_model, fallback_model = self._select_model(criteria)

    slide_suffix = f" ({slide_name})" if slide_name else ""
    print(
        f"[TextTransformerWorkflow] Executing transform with model='{primary_model}', criteria='{criteria}'{slide_suffix}"
    )
    print(
        f"[TextTransformerWorkflow] -> Resolved Slide Job: {resolved_job} ({intensity}% Customization Intensity)"
    )

    # 100% IMMUTABLE BYPASS: If Proof_Points (0% Intensity), never invoke LLM!
    if intensity == 0 or resolved_job == "Proof_Points":
      print(
          f"[TextTransformerWorkflow] -> Slide{slide_suffix} is Proof_Points (0% Immutable) -> Skipping transform, preserving original text 100%."
      )
      return text

    account_info = ""
    customer_name = ""
    if context and isinstance(context, dict):
      customer_name = str(context.get("customer_name") or context.get("customer") or "").strip()
      if not customer_name or customer_name in ("-", "None", "null"):
        # Attempt fallback extraction from business_context
        b_ctx = str(context.get("business_context") or context.get("user_request") or "")
        match = re.search(r'\b(?:for|pitch\s+for|customer)\s+([A-Z][a-zA-Z0-9_\s&]+)', b_ctx, re.IGNORECASE)
        if match:
          candidate = match.group(1).split()[0].strip()
          if candidate.lower() not in ("a", "an", "the", "us", "uk", "our", "why", "google"):
            customer_name = candidate

      industry = context.get("industry")
      sub_industry = context.get("sub_industry")
      micro_industry = context.get("micro_industry")
      domain_lexicon = context.get("domain_lexicon")
      sales_play = context.get("salesPlay")
      parts = []
      if customer_name:
        parts.append(f"Target Customer: {customer_name}")
      if industry:
        parts.append(f"Parent Industry: {industry}")
      if sub_industry:
        parts.append(f"Sub-Industry: {sub_industry}")
      if micro_industry:
        parts.append(f"Micro-Industry / Niche: {micro_industry}")
      if domain_lexicon and isinstance(domain_lexicon, list):
        parts.append(f"Domain Lexicon & Target KPIs: {', '.join(domain_lexicon)}")
      if sales_play:
        parts.append(f"Sales Play: {sales_play}")
      cust_research = self._get_or_research_customer(customer_name, context)
      if cust_research:
        parts.append(
            f"\nLIVE CUSTOMER RESEARCH & TECHNICAL PROFILE (GROUNDING SOURCE):\n{cust_research}"
        )
      if parts:
        account_info = "\nTARGET ACCOUNT CONTEXT:\n" + "\n".join(parts) + "\n"

    grounding_info = ""
    if extra_grounding:
      grounding_info = f"\nGROUNDING CONTEXT:\n{extra_grounding}\n"

    if dk_grounding:
      grounding_info = (grounding_info or "") + dk_grounding

    from agents.skill_loader import get_domain_and_account_glossary_with_name
    from agents.skill_loader import get_persona_guidelines_with_name

    glossary_info, matched_vertical = get_domain_and_account_glossary_with_name(context, criteria)
    persona_info, matched_persona = get_persona_guidelines_with_name(context, criteria)

    if glossary_info and matched_vertical:
      print(f"[TextTransformerWorkflow] -> Ingested Industry Vertical Glossary: {matched_vertical}")
    if persona_info and matched_persona:
      print(f"[TextTransformerWorkflow] -> Ingested Executive Persona Playbook: {matched_persona}")

    is_cover_slide = (
        resolved_job == "Title_Slide"
        or (slide_name and any(k in slide_name.lower() for k in ["cover", "title_slide", "front_page"]))
    )
    is_header = (original_len <= 35) or (slide_name and "title" in slide_name.lower())

    shape_font_size = None
    if context and isinstance(context, dict):
      shape_font_size = context.get("fontSize") or context.get("font_size")
    is_primary_slide_title = bool(
        is_header
        and (
            (slide_name and "title" in slide_name.lower())
            or original_len >= 28
        )
    )
    target_chars, max_chars = self._compute_char_budget(
        original_len,
        font_size=shape_font_size,
        is_action_title=is_primary_slide_title,
    )

    if is_cover_slide:
      length_rule = (
          "1. LENGTH & MODERN COVER TITLE FORMATTING (FOR 68PT TYPOGRAPHY):"
          " For the primary Cover/Title slide, craft a modern,"
          " executive-grade, colon-free headline in **Sentence case** (18 to"
          " 28 characters, 3 to 5 words) that weaves the customer's flagship"
          " brand concept or core transformation theme into a crisp noun"
          " phrase (e.g. 'Agentic banking at HSBC' or 'Next-gen LifeWear with"
          f" AI' or 'Agentic commerce at {customer_name or 'the Enterprise'}')."
          " NEVER start with '-ing' gerunds, NEVER use colons (`:`), and"
          " NEVER repeat 'Google Cloud' (e.g. NEVER write 'Agentic Commerce:"
          " Google Cloud for [Customer]'). Keep it strictly <= 28 characters"
          " so it wraps into at most 3 lines at 68pt font size.\n"
      )
    elif is_header:
      if is_primary_slide_title:
        length_rule = (
            "1. STRICT LENGTH & GOOGLE BRAND VOICE ACTION TITLE FORMATTING:"
            f" For primary slide titles/headers (original length {original_len}"
            f" chars, font_size {shape_font_size or 18}pt), craft a crisp,"
            " conversational, outcome-first declarative thesis headline in"
            " **Sentence case** (capitalize only the first word and proper"
            " nouns/acronyms) using **Subject + finite active verb + outcome**"
            " or a **clean noun/contrast phrase** (e.g. 'Autonomous agents"
            " transform global banking workflows', 'One governed data fabric"
            " unifies 169PB on BigQuery', 'From fragmented copilots to an"
            f" autonomous enterprise'), targeting ~{target_chars} characters"
            f" and STRICTLY NEVER EXCEEDING {max_chars} characters (original -"
            " 5%). STRICT ANTI-GERUND & ANTI-COMMAND MANDATE (Google Brand"
            " Voice & Tone — 'Get to the point' & 'Write like you talk'):"
            " NEVER start slide titles with '-ing' continuous/gerund verbs"
            " (e.g. NEVER start with 'Reimagining...', 'Elevating...',"
            " 'Uniting...', 'Activating...', 'Scaling...', 'Orchestrating...',"
            " 'Establishing...', or 'Unlocking...') and NEVER output bare"
            " imperative commands or Title-Case slogans (e.g. NEVER output"
            " 'Unlock Agentic Commerce' or 'Automate Employee Workflows')."
            f" CRITICAL MANDATE: NEVER append 'for {customer_name}' or"
            " '[Customer]' to internal slide titles!\n"
        )
      else:
        length_rule = (
            "1. STRICT LENGTH & COMPACT CARD HEADER/BADGE FORMATTING: For short card"
            f" sub-headers, badges, or labels (original length {original_len}"
            f" chars), keep the output concise (~{target_chars} chars) and STRICTLY NEVER EXCEED {max_chars} chars (original - 5%). CRITICAL MANDATE: NEVER"
            f" append 'for {customer_name}' or '[Customer]' to internal"
            " labels!\n"
        )
    else:
      length_rule = (
          f"1. STRICT LENGTH CONSTRAINT (ORIGINAL - 5% CEILING): Transformed body text MUST target ~{target_chars} characters "
          f"and MUST NEVER EXCEED {max_chars} characters (95% of original {original_len} chars) to prevent shape overflow.\n"
      )

    system_instruction = (
        "You are an expert Google Cloud Go-to-Market (GTM) copywriter and"
        " presentation strategist.\nYour task is to polish and transform"
        " presentation slide text according to the resolved Slide Job"
        f" ({resolved_job}) and intensity ({intensity}%).\n\n"
        f"MANDATORY SLIDE JOB GOVERNANCE RULE:\n{throttling_rules}\n\n"
        "RULES:\n"
        f"{length_rule}"
        "2. FORMATTING: Preserve existing bullet points (•, -, *), numbered"
        " lists, line breaks, and paragraph structures.\n"
        "3. CANONICAL PRODUCT BRANDING & OCTOBER 2026 GEMINI BRAND UNIFICATION"
        " (Enterprise-Brand-Unification): Strictly follow the attached PRODUCT KNOWLEDGE"
        " SKILL GUIDELINES for all Google Cloud and Gemini product naming"
        " ('Gemini', 'Gemini platform', 'Model Garden in Gemini platform',"
        " 'agent runtime in Gemini platform', 'Antigravity in Gemini platform',"
        " 'Gemini for [industry]', 'Gemini in BigQuery', 'Gemini Enterprise"
        " [Business/Standard/Plus] edition', 'AI Hypercomputer', 'Knowledge"
        " Catalog', 'Built with Gemini'). NEVER use retired terms ('Vertex AI',"
        " 'GEAP', 'Gemini Enterprise Agent Platform', 'Gemini Enterprise app',"
        " 'the GE app', 'Sobi', 'Spark', 'GECX', 'Gemini Enterprise platform',"
        " or 'Powered by Gemini'), and NEVER invent synthetic product"
        " portmanteaus.\n"
        "4. RESEARCH & CITATION INTEGRITY (ZERO SPOOFING OF THIRD-PARTY"
        " METRICS): "
        "When slide text contains cited third-party analyst research, surveys,"
        " or empirical benchmarks (e.g. BCG, Gartner, IDC, PYMNTS, McKinsey,"
        " Forrester, or footnotes like 'Source: (1,2) BCG'):\n"
        "   a. NEVER alter or fabricate the measured population (e.g. do NOT"
        " change 'firms' to 'OEMs' or 'banks').\n"
        "   b. NEVER alter the metric definition (e.g. do NOT change"
        " 'megabreaches' to 'fleet exploits' or 'breach containment' to"
        " 'vehicle patching').\n"
        "   c. Keep all empirical numbers, percentages, duration metrics, and"
        " source citations 100% intact and factually accurate to the cited"
        " study.\n"
        "   d. Tailor the target vertical strictly via consultative slide"
        " headers, titles, or overarching takeaways without altering cited"
        " benchmark data.\n"
        "5. MEANINGFUL CUSTOMER GROUNDING (SUBSTANCE OVER NAME STAMPING): "
        "Remember you are speaking DIRECTLY TO the customer. "
        "a. NEVER use third-person outsider phrasing in slide titles or headers"
        " like 'Partnering with [Customer]', 'Working with [Customer]', or"
        " 'Helping [Customer]'. "
        "b. Instead, use direct, conversational, outcome-focused framing"
        " (e.g. 'Let's build together', 'Our path forward', 'Joint governance"
        " and a phased path to production', 'Your 90-day path to production')."
        " Preserve iconic collaborative titles like 'Let's build together'. "
        "c. FLAGSHIP PLATFORM & REAL-WORLD TECH STACK GROUNDING: Weave in the"
        " customer's actual flagship products, internal architectures, and"
        " technical ecosystems strictly matching their researched profile and"
        " verified industry vertical. Never invent or inject terminology from"
        " unrelated industries. "
        "d. STRICT ZERO NAME STAMPING RULE: NEVER stamp or append the"
        " customer's name onto every slide title or bullet (e.g. do NOT write"
        " 'Develop Agentic Apps for [Customer]' or 'Governed Data for"
        " [Customer]'). The customer name is permitted ONLY on the Cover slide"
        " and optionally the Next Steps slide. For all internal slides,"
        " customization MUST come strictly from blending researched technical"
        " platforms, operational realities, and domain lexicon, NOT from name"
        " repetition.\n"
        "e. SUB/MICRO-INDUSTRY PRECISION & DOMAIN GROUNDING (NO VERTICAL"
        " MISMATCH): "
        "When customizing for an industry vertical or sub-vertical, tailor"
        " strictly to the target industry and sub-industry using the provided"
        " Industry Vertical Glossary. "
        "NEVER inject business models or lexicon from unrelated industries"
        " (e.g. NEVER use retail, POS, shopping cart, or store telemetry terms"
        " for media/entertainment accounts).\n"
        "f. PROPOSITION-BASED FRAMING (NEVER TAKE PARTNERSHIP FOR GRANTED): In"
        " sales pitches and proposals, never assume the prospective customer"
        " has already chosen or partnered with Google Cloud. NEVER write"
        " presumptive titles or headlines like 'Why [Customer] Chooses...' or"
        " 'Why [Customer] Partners With...'. Instead, use suggestion-based"
        " framing: 'Why [Customer] should partner with Google Cloud', 'Why"
        " Google Cloud for [Customer]', or 'The value of partnering with Google"
        " Cloud'.\n"
        "6. GOOGLE BRAND VOICE & TONE HEADLINES (ACTIVE VOICE, ZERO '-ING'"
        " GERUNDS, ZERO BARE COMMANDS): For slide titles, subtitles, card"
        " headers, and takeaways, write crisp, conversational **Sentence case**"
        " headlines (capitalize only the first word and proper nouns/acronyms)"
        " using **Subject + finite active verb + outcome** or a **clean"
        " noun/contrast phrase** (e.g. 'Autonomous agents transform global"
        " banking workflows', 'One governed data fabric unifies 169PB on"
        " BigQuery', 'From fragmented copilots to an autonomous enterprise')."
        " NEVER start headlines or subtitles with '-ing' continuous/gerund"
        " verbs (e.g. NEVER start with 'Reimagining...', 'Elevating...',"
        " 'Uniting...', 'Activating...', 'Scaling...', 'Orchestrating...',"
        " 'Establishing...', or 'Accelerating...'), and NEVER use bare"
        " imperative commands or Title-Case slogans (e.g. avoid 'Unlock"
        " Agentic Commerce', 'Automate Employee Workflows', 'Scale Global"
        " Customer Care').\n"
        "7. HOLISTIC SLIDE COHESION & VOCABULARY DIVERSITY: When customizing"
        " multiple bullet points or sentences, evaluate the slide as a unified"
        " whole. Never repeat identical buzzwords, adjectives, or modifier"
        " phrases"
        " (such as 'IP-secure', 'seamlessly', 'accelerate', 'autonomous')"
        " across"
        " multiple bullets. Each bullet must articulate a distinct,"
        " differentiated"
        " facet of the value proposition.\n"
        "8. STRICT CUSTOMER REFERENCE & CASE STUDY IMMUTABILITY (ZERO"
        " THIRD-PARTY SPREADING/REBRANDING) & 'CYMBAL' WHITE-LABEL"
        " EXCEPTION: "
        "NEVER replace, rename, swap, or rebrand real third-party customer"
        " names (e.g. Cynergy Bank, Lowe's, Home Depot, PayPal, Adidas,"
        " Walmart, Spotify, etc.), "
        "customer quotes, case study stories, or proof points with the target"
        " customer name. "
        "If a slide describes what another enterprise built with Google Cloud"
        " as a reference or case study, KEEP that customer's name, their"
        " architecture, and their story 100% INTACT. "
        "CRITICAL WHITE-LABEL EXCEPTION: 'Cymbal' (including 'Cymbal Retail',"
        " 'Cymbal Superstore', 'Cymbal Shops', 'Cymbal Direct', 'Cymbal Bank',"
        " 'Cymbal Health', 'Cymbal FinTech', 'Cymbal Sports', '@cymbal.com')"
        " is Google Cloud's fictional white-label placeholder brand, NEVER a"
        " real customer! You MUST ALWAYS replace every 'Cymbal' reference with"
        f" the target customer ({customer_name or 'the target enterprise'}).\n"
        "9. OUTPUT FORMAT: Return ONLY the modified text. Do NOT include"
        " markdown code blocks, quotes, or conversational preamble.\n\n"
        f"{account_info}"
        f"{glossary_info}"
        f"{persona_info}"
        f"{grounding_info}"
        f"{skill_context}"
    )

    prompt = (
        f"Polishing Criteria: '{criteria}'\n"
        f"Original Length: {original_len} chars | Target Length: {target_chars} chars | Hard Maximum Ceiling: {max_chars} chars\n\n"
        f"Original Text:\n{text}"
    )

    try:
      thinking_cfg = (
          types.ThinkingConfig(thinking_level=types.ThinkingLevel.MEDIUM)
          if "3.8" in primary_model
          else None
      )
      response = self.generate_content_with_fallback(
          client=self.client,
          model=primary_model,
          contents=[prompt],
          config=types.GenerateContentConfig(
              system_instruction=system_instruction,
              temperature=0.2,
              thinking_config=thinking_cfg,
          ),
          fallback_model=fallback_model,
      )
      extracted = self.extract_text(response)
      return (
          self._sanitize_output(
              extracted,
              is_cover_slide=is_cover_slide,
              customer_name=customer_name,
              original_len=original_len,
              is_action_title=is_primary_slide_title,
              font_size=shape_font_size,
          )
          if extracted
          else text
      )
    except Exception as e:  # pylint: disable=broad-exception-caught
      print(f"[TextTransformerWorkflow] Gemini call failed: {e}")
      return text

  def execute_batch(
      self,
      texts: list[str],
      criteria: str = "Improve clarity and professional tone",
      context: dict | None = None,
      extra_grounding: str = "",
      holistic: bool = True,
      max_workers: int = 8,
      slide_name: str = "",
      slide_data: dict | None = None,
  ) -> list[str]:
    """Transforms a list of slide text elements either holistically or concurrently."""
    if not texts:
      return []

    primary_model, fallback_model = self._select_model(criteria)

    # 1. Slide Job Resolution (Metadata + Content-Based Detection)
    resolved_job, throttling_rules, intensity = self.resolve_slide_job(
        texts=texts,
        slide_data=slide_data,
        criteria=criteria,
        context=context,
    )

    slide_suffix = f" ({slide_name})" if slide_name else ""
    print(
        f"[TextTransformerWorkflow] Executing batch transform for {len(texts)} slide items with model='{primary_model}'{slide_suffix}"
    )
    print(
        f"[TextTransformerWorkflow] -> Resolved Slide Job: {resolved_job} ({intensity}% Customization Intensity)"
    )

    # 100% IMMUTABLE BYPASS: If Proof_Points (0% Intensity), never invoke LLM!
    if intensity == 0 or resolved_job == "Proof_Points":
      print(
          f"[TextTransformerWorkflow] -> Slide{slide_suffix} is Proof_Points (0% Immutable) -> Skipping transform, preserving original text 100%."
      )
      return list(texts)

    if holistic and len(texts) > 1:
      account_info = ""
      c_name = ""
      if context:
        c_name = str(context.get("customer_name", "") or context.get("customer", "")).strip()
        if not c_name or c_name in ("-", "None", "null"):
          b_ctx = str(context.get("business_context") or context.get("user_request") or "")
          match = re.search(r'\b(?:for|pitch\s+for|customer)\s+([A-Z][a-zA-Z0-9_\s&]+)', b_ctx, re.IGNORECASE)
          if match:
            cand = match.group(1).split()[0].strip()
            if cand.lower() not in ("a", "an", "the", "us", "uk", "our", "why", "google"):
              c_name = cand

        ind = context.get("industry", "")
        sub_ind = context.get("sub_industry", "")
        play = context.get("salesPlay", "")
        aud = context.get("audience", "")
        cust_research = self._get_or_research_customer(c_name, context)
        cust_research_block = (
            f"\nLIVE CUSTOMER RESEARCH & TECHNICAL PROFILE (GROUNDING SOURCE):\n{cust_research}\n\n"
            if cust_research
            else ""
        )
        account_info = (
            f"TARGET ACCOUNT CONTEXT:\n"
            f"- Customer: {c_name}\n"
            f"- Industry: {ind} (Sub-industry: {sub_ind})\n"
            f"- Audience: {aud}\n"
            f"- Sales Play: {play}\n\n"
            f"{cust_research_block}"
        )

      grounding_info = ""
      if extra_grounding:
        grounding_info = f"GROUNDING CONTEXT:\n{extra_grounding}\n\n"

      # Dynamically query Developer Knowledge API and load product_knowledge only when technical/GCP/Gemini intent is detected
      dk_grounding, dk_triggered = self._fetch_developer_knowledge_grounding(criteria, texts, context)
      if dk_grounding:
        grounding_info = (grounding_info or "") + dk_grounding

      from agents.skill_loader import get_domain_and_account_glossary_with_name
      from agents.skill_loader import get_persona_guidelines_with_name

      glossary_info, matched_vertical = get_domain_and_account_glossary_with_name(context, criteria)
      persona_info, matched_persona = get_persona_guidelines_with_name(context, criteria)

      if glossary_info and matched_vertical:
        print(f"[TextTransformerWorkflow] -> Ingested Industry Vertical Glossary: {matched_vertical}")
      if persona_info and matched_persona:
        print(f"[TextTransformerWorkflow] -> Ingested Executive Persona Playbook: {matched_persona}")

      extra_skills = ["product_knowledge"]
      combined_query = f"{criteria} " + " ".join(texts)
      skill_context = get_matching_skill_instructions(
          combined_query, always_include=extra_skills
      )

      system_instruction = (
          "You are an expert Google Cloud Go-to-Market (GTM) presentation"
          " strategist and copywriter.\nYour task is to transform a list of"
          " related text elements (bullets, cards, or steps) for a single"
          f" slide according to the resolved Slide Job ({resolved_job}) and"
          f" intensity ({intensity}%).\n\n"
          f"MANDATORY SLIDE JOB GOVERNANCE RULE:\n{throttling_rules}\n\n"
          "MANDATES:\n"
          "1. HOLISTIC COHESION & VOCABULARY DIVERSITY: Evaluate the slide"
          " holistically. NEVER repeat identical buzzwords, modifier"
          " phrases, or"
          " adjectives (e.g., 'IP-secure', 'autonomous', 'scalable',"
          " 'seamlessly')"
          " across items. Distribute distinct, complementary angles across the"
          " items"
          " (e.g. Item 1: Orchestration/Tooling; Item 2: Enterprise Data"
          " Grounding;"
          " Item 3: Studio Workflow UX; Item 4: Model Scale & Governance).\n"
          "2. STRICT LENGTH CONSTRAINTS & SHAPE BOUNDS (ORIGINAL - 5%"
          " CEILING):\n"
          "   - Every item specifies 'length', 'target_chars' (-5% to -10%),"
          " and 'max_chars' (95% of original).\n"
          "   - Each transformed item MUST target 'target_chars' and MUST NEVER"
          " EXCEED 'max_chars' (original_len - 5%) to prevent Google Slides"
          " shape overflow.\n"
          "   - For short badges, pills, and compact card sub-headers (<30"
          " chars that are NOT the primary slide title), keep the output"
          " strictly <= 'max_chars'. NEVER generate long descriptive"
          " sentences for a badge or pill.\n"
          "   - For primary slide Action Titles/Headlines, craft complete,"
          " substantive, conversational, declarative thesis headlines in"
          " **Sentence case** (capitalize only the first word and proper"
          " nouns/acronyms) using **Subject + finite active verb + outcome** or"
          " a **clean noun/contrast phrase** (e.g. 'Autonomous agents transform"
          " global banking workflows', 'One governed data fabric unifies 169PB"
          " on BigQuery', 'From fragmented copilots to an autonomous"
          " enterprise') that fit strictly within 'max_chars' (original_len -"
          " 5%). STRICT ANTI-GERUND & ANTI-COMMAND MANDATE (Google Brand Voice"
          " & Tone): NEVER start slide titles with '-ing' continuous/gerund"
          " verbs (e.g. NEVER start with 'Reimagining...', 'Elevating...',"
          " 'Uniting...', 'Activating...', 'Scaling...', 'Orchestrating...',"
          " 'Establishing...', or 'Unlocking...') and NEVER output bare"
          " imperative commands or Title-Case slogans (e.g. NEVER output"
          " 'Unlock Agentic Commerce' or 'Automate Employee Workflows'). NEVER"
          " append 'for [Customer]' to internal slide titles.\n"
          "   - For the primary Cover Slide only, craft a modern,"
          " executive-grade, colon-free headline in **Sentence case** (18 to 28"
          " chars, 3 to 5 words) that weaves the customer's flagship brand"
          " concept or core transformation theme into a crisp noun phrase (e.g."
          " 'Agentic banking at HSBC' or 'Agentic commerce at [Customer]')"
          " without '-ing' gerunds, colons (`:`), or repeating 'Google"
          " Cloud'.\n"
          "3. MULTI-LINE SHAPE INTEGRITY: If an input element contains a"
          " Header/Title followed by a Description separated by a newline"
          " (\\n), you MUST strictly preserve the exact same 2-part structure"
          " with a newline (\\n) separating the Header/Title from the"
          " Description so that distinct formatting (Bold Header vs Regular"
          " Body) is preserved within the shape.\n"
          "4. CANONICAL PRODUCT BRANDING & OCTOBER 2026 GEMINI BRAND"
          " UNIFICATION"
          " (Enterprise-Brand-Unification): Strictly follow the attached PRODUCT KNOWLEDGE"
          " SKILL GUIDELINES for all Google Cloud and Gemini product naming"
          " ('Gemini', 'Gemini platform', 'Model Garden in Gemini platform',"
          " 'agent runtime in Gemini platform', 'Antigravity in Gemini"
          " platform', 'Gemini for [industry]', 'Gemini in BigQuery', 'Gemini"
          " Enterprise [Business/Standard/Plus] edition', 'AI Hypercomputer',"
          " 'Knowledge Catalog', 'Built with Gemini'). NEVER use retired terms"
          " ('Vertex AI', 'GEAP', 'Gemini Enterprise Agent Platform', 'Gemini"
          " Enterprise app', 'the GE app', 'Sobi', 'Spark', 'GECX', 'Gemini"
          " Enterprise platform', or 'Powered by Gemini'), and NEVER invent"
          " synthetic product portmanteaus.\n"
          "5. RESEARCH & CITATION INTEGRITY (ZERO SPOOFING OF THIRD-PARTY"
          " METRICS): "
          "When slide elements contain cited third-party analyst research,"
          " surveys, or empirical benchmarks (e.g. BCG, Gartner, IDC, PYMNTS,"
          " McKinsey, Forrester, or footnotes like 'Source: (1,2) BCG'):\n"
          "   a. NEVER alter or fabricate the measured population (e.g. do NOT"
          " change 'firms' to 'OEMs' or 'banks').\n"
          "   b. NEVER alter the metric definition (e.g. do NOT change"
          " 'megabreaches' to 'fleet exploits' or 'breach containment' to"
          " 'vehicle patching').\n"
          "   c. Keep all empirical numbers, percentages, duration metrics, and"
          " source citations 100% intact and factually accurate to the cited"
          " study.\n"
          "   d. Tailor the target vertical strictly via consultative slide"
          " headers, titles, or overarching takeaways without altering cited"
          " benchmark data.\n"
          "6. MEANINGFUL CUSTOMER & VERTICAL GROUNDING (SUBSTANCE OVER BUZZWORD"
          " STAMPING): "
          "Weave in the customer's actual flagship platforms, internal"
          " architectures, and technical ecosystems strictly matching their"
          " researched profile and verified industry vertical. "
          "Tailor strictly to the target industry and sub-industry using the"
          " provided Industry Vertical Glossary. "
          "CRITICAL: NEVER inject terminology or business models from unrelated"
          " industries (e.g. NEVER use retail, POS, shopping cart, or store"
          " telemetry terms for media/entertainment accounts). "
          "NEVER stamp or append the customer or vertical name repeatedly onto"
          " internal slide titles or cards (e.g. do NOT write 'Develop Agentic"
          " Apps for [Customer]'). Reserve specific customer names for the"
          " Cover slide. Let authentic domain vocabulary, operational"
          " workflows, and technical substance carry the customization across"
          " internal slides.\n"
          "7. GOOGLE BRAND VOICE & TONE HEADLINES (ACTIVE VOICE, ZERO '-ING'"
          " GERUNDS, ZERO BARE COMMANDS): For slide titles, subtitles, card"
          " headers, and takeaways, write crisp, conversational **Sentence"
          " case**"
          " headlines using **Subject + finite active verb + outcome** or a"
          " **clean noun/contrast phrase** (e.g. 'Autonomous agents transform"
          " global banking workflows', 'One governed data fabric unifies 169PB"
          " on BigQuery', 'From fragmented copilots to an autonomous"
          " enterprise'). NEVER start headlines or subtitles with '-ing'"
          " continuous/gerund verbs (e.g. NEVER start with 'Reimagining...',"
          " 'Elevating...', 'Uniting...', 'Activating...', 'Scaling...',"
          " 'Orchestrating...', 'Establishing...', or 'Accelerating...'), and"
          " NEVER generate bare imperative commands or Title-Case slogans (e.g."
          " avoid 'Unlock Agentic Commerce', 'Automate Employee Workflows',"
          " 'Scale Global Customer Care'). "
          "NEVER assume the prospective customer has already chosen or"
          " partnered with Google Cloud (avoid 'Why [Customer] Chooses...',"
          " 'Why [Customer] Partners With...'). "
          "Instead, use suggestion-based framing (e.g. 'Why [Customer] should"
          " partner with Google Cloud', 'Why Google Cloud for [Customer]',"
          " 'Co-innovating with Google Cloud').\n"
          "8. STRICT CUSTOMER REFERENCE & CASE STUDY IMMUTABILITY (ZERO"
          " THIRD-PARTY SPREADING/REBRANDING) & 'CYMBAL' WHITE-LABEL"
          " EXCEPTION: "
          "NEVER replace, rename, swap, or rebrand real third-party customer"
          " names (e.g. Cynergy Bank, Lowe's, Home Depot, PayPal, Adidas,"
          " Walmart, Spotify, etc.), "
          "customer quotes, case study stories, or proof points with the target"
          " customer name. "
          "If a slide describes what another enterprise built with Google Cloud"
          " as a reference or case study, KEEP that customer's name, their"
          " architecture, and their story 100% INTACT. "
          "CRITICAL WHITE-LABEL EXCEPTION: 'Cymbal' (including 'Cymbal Retail',"
          " 'Cymbal Superstore', 'Cymbal Shops', 'Cymbal Direct', 'Cymbal"
          " Bank', 'Cymbal Health', 'Cymbal FinTech', 'Cymbal Sports',"
          " '@cymbal.com') is Google Cloud's fictional white-label placeholder"
          " brand, NEVER a real customer! You MUST ALWAYS replace every"
          " 'Cymbal' reference with the target customer"
          f" ({c_name or 'the target enterprise'}).\n"
          "9. OUTPUT FORMAT: Return a valid JSON array of strings containing"
          f" exactly {len(texts)} transformed strings matching the order of"
          " inputs.\n\n"
          f"{account_info}"
          f"{glossary_info}"
          f"{persona_info}"
          f"{grounding_info}"
          f"{skill_context}"
      )

      slide_shapes_meta = []
      primary_title_idx = 0
      if (
          isinstance(slide_data, dict)
          and isinstance(slide_data.get("data"), list)
          and slide_data.get("data")
      ):
        slide_shapes_meta = [
            s
            for s in slide_data["data"]
            if isinstance(s, dict) and s.get("text")
        ]
        if slide_shapes_meta:
          primary_title_idx = self._select_primary_title_idx(slide_shapes_meta)

      batch_items = []
      for i, t in enumerate(texts):
        sh_meta = (
            slide_shapes_meta[i]
            if i < len(slide_shapes_meta)
            and isinstance(slide_shapes_meta[i], dict)
            else {}
        )
        is_title_i = i == primary_title_idx
        fs_i = float(sh_meta.get("fontSize") or (28.0 if is_title_i else 12.0))
        w_i = sh_meta.get("width_pt")
        h_i = sh_meta.get("height_pt")
        c_i = sh_meta.get("clearance_pt")
        t_chars, m_chars = self._compute_char_budget(
            len(t),
            font_size=fs_i,
            is_action_title=is_title_i,
            width_pt=w_i,
            clearance_pt=c_i,
            height_pt=h_i,
        )
        batch_items.append({
            "id": i,
            "text": t,
            "length": len(t),
            "font_size": fs_i,
            "role": "action_title" if is_title_i else "body_or_header",
            "target_chars": t_chars,
            "max_chars": m_chars,
        })
      items_json = json.dumps(batch_items, indent=2)
      prompt = f"Polishing Criteria: '{criteria}'\n\nSlide Elements to Transform:\n{items_json}"

      try:
        thinking_cfg = (
            types.ThinkingConfig(thinking_level=types.ThinkingLevel.MEDIUM)
            if "3.8" in primary_model
            else None
        )
        response = self.generate_content_with_fallback(
            client=self.client,
            model=primary_model,
            contents=[prompt],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2,
                response_mime_type="application/json",
                thinking_config=thinking_cfg,
            ),
            fallback_model=fallback_model,
        )
        parsed = self.extract_json(response)
        if isinstance(parsed, list) and len(parsed) == len(texts):
          # Extract strings whether returned as list of strings or list of objects
          results = []
          for item in parsed:
            if isinstance(item, dict):
              results.append(item.get("transformed") or item.get("text") or str(item))
            else:
              results.append(str(item))
          is_cover_slide = resolved_job == "Title_Slide" or (
              slide_name
              and any(
                  k in slide_name.lower()
                  for k in ["cover", "title_slide", "front_page"]
              )
          )
          out_sanitized = []
          for idx_i, (r, orig_t) in enumerate(zip(results, texts)):
            sh_meta = (
                slide_shapes_meta[idx_i]
                if idx_i < len(slide_shapes_meta)
                and isinstance(slide_shapes_meta[idx_i], dict)
                else {}
            )
            is_title_i = idx_i == primary_title_idx
            fs_i = float(
                sh_meta.get("fontSize") or (28.0 if is_title_i else 12.0)
            )
            out_sanitized.append(
                self._sanitize_output(
                    r,
                    is_cover_slide=is_cover_slide,
                    customer_name=c_name,
                    original_len=len(orig_t),
                    is_action_title=is_title_i,
                    font_size=fs_i,
                    width_pt=sh_meta.get("width_pt"),
                    clearance_pt=sh_meta.get("clearance_pt"),
                    height_pt=sh_meta.get("height_pt"),
                )
            )
          return out_sanitized
      except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"[TextTransformerWorkflow] Holistic batch failed, falling back to concurrent: {e}")

    # Fallback to concurrent individual execution
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max_workers
    ) as executor:
      futures = [
          executor.submit(
              self.execute, t, criteria, context, extra_grounding, slide_name, slide_data
          )
          for t in texts
      ]
      return [f.result() for f in futures]

  def review_deck_cohesion(
      self,
      slides_list: list[dict],
      context: dict | None = None,
      criteria: str = "Ensure seamless end-to-end narrative flow, smooth transitions, and eliminate cross-slide repetitive buzzwords",
  ) -> list[dict]:
    """Reviews the macro presentation flow across all slides to ensure narrative coherence, transitional continuity, and diverse vocabulary. (Option A: Global Editorial Pass)."""
    if not slides_list or len(slides_list) <= 1:
      return slides_list

    print(f"[TextTransformerWorkflow] Executing Option A Global Deck Cohesion Review across {len(slides_list)} slides...")

    # Extract macro slide summaries
    deck_overview = []
    for idx, s in enumerate(slides_list):
      if not isinstance(s, dict):
        continue
      title = str(s.get("title") or s.get("slide_title") or s.get("name") or f"Slide {idx+1}")
      job = str(s.get("slide_job") or s.get("taxonomy", {}).get("slide_job") or "")

      # Collect top texts/takeaways
      slide_texts = []
      def collect(x):
        if isinstance(x, dict):
          for k, v in x.items():
            if k.lower() in ("text", "texts", "header", "lead_takeaway") and isinstance(v, str) and v.strip():
              slide_texts.append(v.strip())
            else:
              collect(v)
        elif isinstance(x, list):
          for item in x:
            collect(item)
      collect(s)

      deck_overview.append({
          "slide_index": idx + 1,
          "slide_id": s.get("slide_id") or s.get("slideId") or f"s_{idx+1}",
          "slide_job": job,
          "title": title,
          "key_points": slide_texts[:3],
          "is_proof_point": "proof" in job.lower() or "case_study" in job.lower() or s.get("is_cust_ref") is True or s.get("_source_datastore_key") == "cust_ref",
      })

    account_info = ""
    if context and isinstance(context, dict):
      c_name = context.get("customer_name")
      ind = context.get("industry")
      if c_name:
        account_info += f"Target Customer: {c_name}\n"
      if ind:
        account_info += f"Industry Vertical: {ind}\n"

    system_instruction = (
        "You are an executive Google Cloud Go-to-Market (GTM) Presentation Editor and Narrative Director.\n"
        "Your task is to review the macro flow of this presentation end-to-end to ensure exceptional cohesion, seamless transitions, and diverse executive vocabulary.\n\n"
        "EDITORIAL MANDATES:\n"
        "1. NARRATIVE ARC & RHYTHM: Ensure titles and lead headlines build a progressive story (Context/Challenges ➔ Solution Pillars ➔ Technical Architecture ➔ Verified Proof Points ➔ Phased Transformation Journey).\n"
        "2. TRANSITIONAL CONNECTORS: Harmonize slide titles so each slide naturally bridges to the next without abrupt jumps.\n"
        "3. ELIMINATE REPETITIVE BUZZWORDS: If buzzwords or modifier phrases (e.g. 'IP-secure', 'autonomous', 'accelerate', 'seamlessly', 'future-ready') appear repeatedly across different slide headers, diversify them with rich, consultative enterprise terminology.\n"
        "4. STRICT PROOF POINT IMMUTABILITY (0% RULE): NEVER modify or alter third-party customer case study references, customer names, or empirical proof point metrics. Keep them 100% intact.\n"
        "5. OUTPUT FORMAT: Return a valid JSON array of objects with keys: 'slide_index', 'polished_title', 'transition_note'.\n"
    )

    prompt = (
        f"{account_info}\n"
        f"Overarching Criteria: '{criteria}'\n\n"
        f"Deck Macro Structure:\n{json.dumps(deck_overview, indent=2)}"
    )

    try:
      response = self.generate_content_with_fallback(
          client=self.client,
          model=self.fast_model,
          contents=[prompt],
          config=types.GenerateContentConfig(
              system_instruction=system_instruction,
              temperature=0.2,
              response_mime_type="application/json",
          ),
          fallback_model=self.model,
      )
      parsed = self.extract_json(response)
      if isinstance(parsed, list):
        title_map = {}
        for item in parsed:
          if isinstance(item, dict):
            idx = item.get("slide_index")
            p_title = item.get("polished_title")
            if idx is not None and p_title:
              title_map[int(idx) - 1] = p_title

        # Apply polished titles back
        for i, s in enumerate(slides_list):
          if i in title_map and isinstance(s, dict):
            # Do not alter immutable proof points
            if s.get("is_cust_ref") or s.get("_source_datastore_key") == "cust_ref":
              continue
            old_t = s.get("title") or s.get("slide_title") or ""
            new_t = title_map[i]
            if "title" in s:
              s["title"] = new_t
            if "slide_title" in s:
              s["slide_title"] = new_t
            print(f"[TextTransformerWorkflow] -> Slide {i+1} title harmonized: '{old_t}' ➔ '{new_t}'")

      print("[TextTransformerWorkflow] Global Deck Cohesion Review completed successfully.")
    except Exception as e:
      print(f"[TextTransformerWorkflow] Global Deck Cohesion Review notice: {e}")

    return slides_list

  def customize_reusable_slide(self, suggestion: dict, context: dict | None = None) -> dict:
    """Customizes a retrieved reusable slide using a single fast JSON call to optimize Phase 2 latency."""
    original_title = suggestion.get("original_title") or suggestion.get("name") or ""
    original_content = suggestion.get("original_content") or ""

    # Strict Proof Point Immutability (0% Rule)
    if (
        suggestion.get("is_cust_ref")
        or suggestion.get("_source_datastore_key") == "cust_ref"
        or suggestion.get("is_proof_point")
    ):
      print(
          f"[TextTransformerWorkflow] -> Skipping customization for Proof Point / Customer Reference slide: '{original_title}'"
      )
      return {
          "customized_title": original_title,
          "customized_content": original_content,
      }

    if not original_title and not original_content:
      return {}

    ctx = context or {}
    customer_name = ctx.get("customer_name") or "Target Customer"
    industry = ctx.get("industry") or "Enterprise"
    sub_industry = ctx.get("sub_industry") or ""
    audience = ctx.get("audience") or ""
    if isinstance(audience, list):
      audience = ", ".join(str(a) for a in audience if a)
    sales_play = ctx.get("salesPlay") or ""
    if isinstance(sales_play, list):
      sales_play = ", ".join(str(p) for p in sales_play if p)
    win_cycle = ctx.get("win_cycle") or ctx.get("sales_stage") or "S1"
    business_context = ctx.get("business_context") or ""
    customer_research = str(ctx.get("customer_research") or "")[:1200]

    prompt = (
        "Customize this reusable presentation slide for Target Customer:"
        f" {customer_name} (Industry:"
        f" {industry}{f' / {sub_industry}' if sub_industry else ''}, Audience:"
        f" {audience or 'Executive Leadership'}, WIN Stage:"
        f" {win_cycle}).\nSales Play:"
        f" {sales_play or 'General Enterprise Transformation'}\nBusiness"
        " Context & Priorities:"
        f" {business_context}\n{f'Account Intelligence:\n{customer_research}\n' if customer_research else ''}\nOriginal"
        f" Title: {original_title}\nOriginal"
        f" Content:\n{original_content}\n\nMandates:\n1. Transform the slide"
        " title into an active, outcome-driven, executive headline (<75 chars)"
        " tailored specifically to the target customer, their"
        " sub-industry/domain, and executive audience.\n2. Transform the slide"
        " body content and bullet points to weave in the customer's strategic"
        " imperatives, technical realities, and vocabulary while maintaining"
        " structural layout and factual accuracy.\n3. ONE-PRODUCT NAMING RULE:"
        " Position 'Gemini Enterprise' as one unified product (differentiate"
        " by surface: 'Gemini Enterprise on web', 'in Antigravity', 'in Model"
        " Garden', 'via API'). NEVER use retired terms like 'Vertex', 'Vertex"
        " AI', 'Gemini Enterprise app', 'GE app', 'GEAP', or 'Powered by"
        " Gemini' (use 'Built with Gemini' or 'powered by Gemini"
        " Enterprise').\nReturn ONLY a JSON object with keys"
        " 'customized_title' and 'customized_content'."
    )

    try:
      response = self.generate_content_with_fallback(
          client=self.client,
          model=self.fast_model,
          contents=[prompt],
          config=types.GenerateContentConfig(
              temperature=0.2,
              response_mime_type="application/json",
          ),
          fallback_model=self.model,
      )
      parsed = self.extract_json(response)
      if isinstance(parsed, dict):
        customized_title = str(
            parsed.get("customized_title") or original_title
        ).strip()
        customized_content = str(
            parsed.get("customized_content") or original_content
        ).strip()
      else:
        customized_title = original_title
        customized_content = original_content
    except Exception as e:
      print(
          "[TextTransformerWorkflow] Fast slide customization fallback for"
          f" '{original_title}': {e}"
      )
      customized_title = original_title
      customized_content = original_content

    print(
        f"[TextTransformerWorkflow] Successfully customized reusable slide '{original_title}'"
    )
    return {
        "customized_title": customized_title,
        "customized_content": customized_content,
    }

  def _is_locked_gcp_product_badge(
      self, text: str, is_architecture_slide: bool = False
  ) -> bool:
    """Returns True if a shape is a standalone official Google Cloud product/layer badge that must remain locked verbatim (subject only to canonical Enterprise-Brand-Unification sanitization)."""
    if not text:
      return False
    clean = re.sub(r"\s+", " ", text.strip()).lower().strip("•*-–—:;,.!?()[]{}")
    if not clean or len(clean) > 52:
      return False
    official_badges = {
        "google cloud",
        "gemini",
        "gemini 3",
        "gemini enterprise",
        "gemini enterprise for customer experience",
        "vertex ai",
        "vertex ai search",
        "vertex ai agent builder",
        "ai hypercomputer",
        "ai platform",
        "agents & applications",
        "agents & apps",
        "models",
        "research & frontier multimodal models",
        "model garden",
        "google adk",
        "adk",
        "agent engine",
        "agent gateway",
        "agentic data cloud",
        "knowledge catalog",
        "dataplex",
        "borderless lakehouse",
        "analytical systems",
        "operational systems",
        "bigquery",
        "alloydb",
        "spanner",
        "cloud sql",
        "cloud storage",
        "cloud run",
        "cloud cdn",
        "google kubernetes engine",
        "gke",
        "looker",
        "pub/sub",
        "dataflow",
        "dataproc",
        "apigee",
        "mandiant",
        "chronicle",
        "security command center",
        "imagen",
        "imagen 3",
        "veo",
        "chirp",
        "lyria",
        "tpu",
        "gpu",
        "openness",
        "security",
        "responsibility",
        "sustainability",
        "infrastructure",
        "data cloud",
        "google workspace",
        "notebooklm",
        "antigravity",
    }
    if clean in official_badges:
      return True
    if is_architecture_slide and len(clean) <= 48:
      tokens = [
          t.strip().lower() for t in re.split(r"[,/\n•|]+", clean) if t.strip()
      ]
      if tokens and all(t in official_badges for t in tokens):
        return True
    return False

  def _select_primary_title_idx(self, slide_shapes: list[dict]) -> int:
    """Selects the true primary slide title index, disqualifying bulleted lists, tall body boxes, and low-Y shapes."""
    best_idx = 0
    best_score = (-1.0, -1.0)
    for cand_i, cand_s in enumerate(slide_shapes):
      if not isinstance(cand_s, dict):
        continue
      cand_t = str(cand_s.get("text") or "").strip()
      if not cand_t:
        continue
      cand_lower = cand_t.lower()
      if (
          "proprietary & confidential" in cand_lower
          or cand_t.isdigit()
          or cand_lower in ("google cloud", "app", "ge", "gemini enterprise")
      ):
        continue
      if cand_s.get("has_bullets"):
        continue
      w_pt = float(cand_s.get("width_pt") or 0.0)
      h_pt = float(cand_s.get("height_pt") or 0.0)
      y_pt = float(cand_s.get("y_pt") or 0.0)
      if h_pt > 145.0 or y_pt > 135.0:
        continue
      cand_fs = float(cand_s.get("fontSize") or 12.0)
      ph_type = str(cand_s.get("placeholder_type") or "").upper()
      is_title_ph = ph_type in ("TITLE", "CENTERED_TITLE")
      if cand_fs >= 18.0 or is_title_ph:
        eff_fs = max(cand_fs, 28.0 if is_title_ph else cand_fs)
        top_bonus = 2.0 if (is_title_ph or (0.0 < y_pt < 75.0)) else 0.0
        wide_bonus = 3.0 if (w_pt >= 340.0 and y_pt < 95.0) else 0.0
        score = (eff_fs + top_bonus + wide_bonus, -y_pt)
        if score > best_score:
          best_score = score
          best_idx = cand_i
    return best_idx

  def execute_deck_holistic(
      self,
      slides_list: list[dict],
      criteria: str = "Tailor presentation text to the target customer and industry while preserving technical accuracy, consultative tone, and length constraints",
      context: dict | None = None,
      target_slide_ids: list | None = None,
  ) -> list[dict]:
    """Transforms an entire deck of slides in a single holistic LLM call to build a progressive narrative arc and eliminate repetitive cross-slide buzzwords."""
    if not slides_list:
      return []

    print(
        f"[TextTransformerWorkflow] Executing Whole-Deck Holistic Transformation across {len(slides_list)} slides..."
    )

    import copy
    output_slides = copy.deepcopy(slides_list)

    # 1. Structure the deck elements with Full-Deck Narrative Spine & Neighbor Context
    slide_meta_spine = []
    for idx, s in enumerate(output_slides):
      if not isinstance(s, dict):
        slide_meta_spine.append(
            {"title": f"Slide {idx+1}", "is_reusable": True}
        )
        continue
      s_title = str(s.get("slide_title") or s.get("title") or "").strip()
      if (
          not s_title
          and "data" in s
          and isinstance(s["data"], list)
          and s["data"]
      ):
        first_sh = s["data"][0]
        if isinstance(first_sh, dict):
          s_title = str(first_sh.get("text") or "").split("\n")[0][:80].strip()
      slide_meta_spine.append({
          "title": s_title or f"Slide {idx+1}",
          "is_reusable": bool(s.get("is_reusable", True)),
      })

    structured_deck = []
    all_deck_texts = []
    for idx, slide in enumerate(output_slides):
      if not isinstance(slide, dict):
        continue

      slide_id = (
          slide.get("slideId")
          or slide.get("slide_id")
          or slide.get("id")
          or f"slide_{idx+1}"
      )

      # CRITICAL: Handle internal enablement guidance slides (e.g. 'Internal Context')
      if self._is_internal_enablement_slide(slide):
        print(
            "[TextTransformerWorkflow] Customizing internal enablement"
            f" metadata for slide {idx+1} ({slide_id})."
        )
        self.transform_internal_enablement_slide(
            slide, context=context, criteria=criteria
        )
        slide["_skip_mutation"] = True
        continue

      # CRITICAL: Handle standalone Closing / Thank You slides (0% Immutable)
      if self.is_closing_slide(slide):
        print(
            "[TextTransformerWorkflow] Preserving standalone closing slide"
            f" {idx+1} ({slide_id}) 100% intact (0% Immutable)."
        )
        slide["_skip_mutation"] = True
        slide["skip"] = True
        continue

      # CRITICAL: Preserve Customer Proof Points / Case Studies & Cited Stats slides 100% intact (0% Immutable)
      if bool(
          slide.get("_skip_mutation")
          or slide.get("is_proof_point")
          or slide.get("is_cited_stats_slide")
          or slide.get("is_cust_ref")
          or slide.get("_source_datastore_key") == "cust_ref"
      ):
        slide["_skip_mutation"] = True
        continue

      is_reusable = bool(slide.get("is_reusable", True))
      is_arch_slide = bool(slide.get("is_architecture_product_slide", False))
      slide_title = slide_meta_spine[idx]["title"]
      prev_ctx = slide.get("prev_slide_context") or (
          {
              "slide_index": idx,
              "title": slide_meta_spine[idx - 1]["title"],
              "origin": (
                  "Reusable Reference Slide"
                  if slide_meta_spine[idx - 1]["is_reusable"]
                  else "Phase 2 Generated Slide"
              ),
          }
          if idx > 0
          else None
      )
      next_ctx = slide.get("next_slide_context") or (
          {
              "slide_index": idx + 2,
              "title": slide_meta_spine[idx + 1]["title"],
              "origin": (
                  "Reusable Reference Slide"
                  if slide_meta_spine[idx + 1]["is_reusable"]
                  else "Phase 2 Generated Slide"
              ),
          }
          if idx < len(slide_meta_spine) - 1
          else None
      )
      is_final_slide_in_deck = bool(
          slide.get(
              "is_final_slide_in_deck",
              idx == len(output_slides) - 1 and len(output_slides) > 1,
          )
      )

      # Check if this slide is targeted
      is_targeted = True
      if target_slide_ids:
        is_targeted = (
            (idx + 1) in target_slide_ids
            or slide_id in target_slide_ids
            or str(idx + 1) in [str(x) for x in target_slide_ids]
            or str(slide_id) in [str(x) for x in target_slide_ids]
        )

      shapes_to_transform = []
      header_case_votes = {"title": 0, "sentence": 0}

      # Format A: slide has "data" list of shape dicts
      if "data" in slide and isinstance(slide["data"], list):
        primary_title_idx = self._select_primary_title_idx(slide["data"])

        for s_i, s in enumerate(slide["data"]):
          if isinstance(s, dict) and s.get("text") and str(s.get("text")).strip():
            raw_t = str(s.get("text")).strip()
            all_deck_texts.append(raw_t)
            font_sz = s.get("fontSize") or 12
            is_title_shape = s_i == primary_title_idx
            w_pt = s.get("width_pt")
            h_pt = s.get("height_pt")
            c_pt = s.get("clearance_pt")
            is_conversational_prompt = (
                "?" in raw_t or '"' in raw_t or "“" in raw_t
            )
            is_locked_badge = (
                not is_title_shape
                and self._is_locked_gcp_product_badge(
                    raw_t, is_architecture_slide=is_arch_slide
                )
            )
            t_chars, m_chars = self._compute_char_budget(
                len(raw_t),
                font_size=font_sz,
                is_action_title=is_title_shape,
                width_pt=w_pt,
                clearance_pt=c_pt,
                height_pt=h_pt,
            )
            is_bold_or_medium = bool(
                s.get("bold") or int(s.get("fontWeight") or 400) >= 500
            )
            if is_title_shape:
              role = "action_title"
            elif is_locked_badge:
              role = "locked_product_badge"
            elif is_arch_slide:
              role = "architecture_value_framing"
            elif not is_reusable:
              role = "phase2_synthesized_body"
            elif (
                is_bold_or_medium
                and (len(raw_t) <= 14 and len(raw_t.split()) == 1)
                and m_chars <= 15
                and not is_conversational_prompt
            ):
              role = "short_badge_or_header"
            elif (
                is_bold_or_medium
                and len(raw_t) <= 45
                and not is_conversational_prompt
            ):
              role = "sub_card_header"
              hdr_words = [
                  w for w in re.findall(r"[A-Za-z]+", raw_t) if len(w) > 2
              ]
              if len(hdr_words) >= 2:
                if all(w[0].isupper() for w in hdr_words[1:]):
                  header_case_votes["title"] += 1
                else:
                  header_case_votes["sentence"] += 1
            else:
              role = "reusable_body"

            if role == "sub_card_header" and m_chars >= 16:
              min_chars = 12
            elif (
                role == "reusable_body"
                and m_chars >= 98
                and w_pt is not None
                and float(w_pt) >= 180.0
            ):
              min_chars = 92
            elif role == "action_title" and m_chars >= 48:
              min_chars = 42
            else:
              min_chars = max(1, int(t_chars * 0.75))

            shapes_to_transform.append({
                "shape_id": (
                    s.get("shapeId") or s.get("shape_id") or s.get("id")
                ),
                "text": raw_t,
                "char_count": len(raw_t),
                "font_size": font_sz,
                "width_pt": w_pt,
                "height_pt": h_pt,
                "min_chars": min_chars,
                "target_chars": t_chars,
                "max_chars": m_chars,
                "bold": is_bold_or_medium,
                "role": role,
                "preserve_body_content": bool(
                    not is_reusable or is_locked_badge
                ),
            })
      # Format B: slide is a dict with shape/table keys
      else:
        shapes_dict = slide.get("shapes", {})
        if isinstance(shapes_dict, dict) and shapes_dict:
          for shape_id, segs in shapes_dict.items():
            if isinstance(segs, dict):
              sorted_k = sorted(
                  segs.keys(), key=lambda x: int(x) if str(x).isdigit() else x
              )
              parts = []
              has_newlines = False
              for sk in sorted_k:
                seg_item = segs[sk]
                if isinstance(seg_item, dict) and seg_item.get("Text"):
                  t_val = str(seg_item["Text"]).strip()
                  if t_val:
                    parts.append(t_val)
                    if seg_item.get("HadNewline"):
                      has_newlines = True
              full_text = (
                  "\n".join(parts)
                  if has_newlines or len(parts) > 1
                  else " ".join(parts)
              ).strip()
              if (
                  full_text
                  and not (full_text.isdigit() and len(full_text) <= 3)
                  and full_text not in ("‹#›", "<#>", "#")
              ):
                all_deck_texts.append(full_text)
                t_chars, m_chars = self._compute_char_budget(
                    len(full_text), font_size=12.0, is_action_title=False
                )
                shapes_to_transform.append({
                    "shape_id": shape_id,
                    "text": full_text,
                    "char_count": len(full_text),
                    "font_size": 12.0,
                    "target_chars": t_chars,
                    "max_chars": m_chars,
                    "bold": False,
                    "role": (
                        "reusable_body"
                        if is_reusable
                        else "phase2_synthesized_body"
                    ),
                    "preserve_body_content": not is_reusable,
                })
        else:

          def extract_shapes(obj, path=""):
            if isinstance(obj, dict):
              for k, v in obj.items():
                if (
                    k.lower() in ("text", "content")
                    and isinstance(v, str)
                    and v.strip()
                ):
                  raw_t = v.strip()
                  all_deck_texts.append(raw_t)
                  t_chars, m_chars = self._compute_char_budget(
                      len(raw_t), font_size=12.0, is_action_title=False
                  )
                  shapes_to_transform.append({
                      "shape_id": path or k,
                      "text": raw_t,
                      "char_count": len(raw_t),
                      "font_size": 12.0,
                      "target_chars": t_chars,
                      "max_chars": m_chars,
                      "bold": False,
                      "role": (
                          "reusable_body"
                          if is_reusable
                          else "phase2_synthesized_body"
                      ),
                      "preserve_body_content": not is_reusable,
                  })
                else:
                  extract_shapes(v, f"{path}.{k}" if path else k)
            elif isinstance(obj, list):
              for i, item in enumerate(obj):
                extract_shapes(item, f"{path}[{i}]")

          extract_shapes(slide)

      if shapes_to_transform:
        cvi_stage_num = int(slide.get("cvi_stage") or 46)
        ag_title_low = str(slide.get("agenda_section_title") or "").lower()
        is_context_reusable = is_reusable and (
            cvi_stage_num <= 20
            or (
                cvi_stage_num <= 25
                and any(
                    k in ag_title_low
                    for k in (
                        "context",
                        "imperative",
                        "challenge",
                        "current state",
                        "bottleneck",
                        "landscape",
                        "friction",
                        "foundation",
                    )
                )
            )
        )
        if is_arch_slide:
          slide_job = "Architecture_Stack"
          customization_intensity = (
              "40% (Unlock Action Title, Subtitle & Layer Value Framing for"
              " Customer Use Case; Strictly Preserve Locked GCP Product Badges)"
          )
        elif is_context_reusable:
          slide_job = "Context_Imperative"
          customization_intensity = (
              "85% (Context & Strategic Imperative Framing: Frame Action Title,"
              " Sub-Card Headers, and Body around the Customer's strategic"
              " imperative, data/operational foundation requirements, and why"
              " legacy approaches must evolve BEFORE pitching product"
              " solutions)"
          )
        elif is_reusable:
          slide_job = "Solution_Use_Case"
          customization_intensity = (
              "85% (Deep Use-Case Re-Anchoring: Rewrite Action Title, Sub-Card"
              " Headers, and Body Bullets around the Customer's specific prompt"
              " objective & workflows; FORBID shallow 1-word noun swaps)"
          )
        else:
          slide_job = "Bespoke_Archetype"
          customization_intensity = (
              "100% (Executive Specificity: Keep bespoke synthesized body"
              " shapes intact & generate presenter transition hook)"
          )
        header_case_style = (
            "Title Case"
            if header_case_votes["title"] > header_case_votes["sentence"]
            else "Sentence case"
        )
        slide["_header_case_style"] = header_case_style
        structured_deck.append({
            "slide_index": idx + 1,
            "slide_id": slide_id,
            "slide_title": slide_title,
            "slide_job": slide_job,
            "cvi_stage": cvi_stage_num,
            "customization_intensity": customization_intensity,
            "header_case_style": header_case_style,
            "is_final_slide_in_deck": is_final_slide_in_deck,
            "agenda_section_index": str(
                slide.get("agenda_section_index") or ""
            ),
            "agenda_section_title": str(
                slide.get("agenda_section_title") or ""
            ),
            "assigned_agenda_subtopic": str(
                slide.get("assigned_agenda_subtopic") or ""
            ),
            "agenda_section_subtopics": list(
                slide.get("agenda_section_parts") or []
            ),
            "is_reusable": is_reusable,
            "slide_origin": (
                f"Reusable Architecture/Stack Slide ({customization_intensity})"
                if is_arch_slide
                else (
                    "Reusable Context/Imperative Slide"
                    f" ({customization_intensity})"
                    if is_context_reusable
                    else (
                        "Reusable Solution/Use-Case Slide"
                        f" ({customization_intensity})"
                        if is_reusable
                        else (
                            "Phase 2 Synthesized Slide (Transition Hook Anchor"
                            " Only; Keep Synthesized Title & Body Shapes"
                            " Intact)"
                        )
                    )
                )
            ),
            "prev_slide_context": prev_ctx,
            "next_slide_context": next_ctx,
            "is_targeted": is_targeted,
            "is_proof_point": False,
            "shapes": shapes_to_transform,
        })

    if not structured_deck:
      return output_slides

    # 2. Gather context, domain glossaries, and live Developer Knowledge grounding
    context = context or {}
    customer_name = context.get("customer_name") or context.get("customer", "")
    industry = context.get("industry", "")
    sub_industry = context.get("sub_industry", "")

    # Safety fallback: parse customer and industry from criteria string if context was omitted
    if (not customer_name or not industry) and criteria:
      crit_match = re.search(r"Tailor presentation text to ([^ in]+(?: [^ in]+)*?) in the ([^,]+?) industry", criteria, re.IGNORECASE)
      if crit_match:
        if not customer_name:
          customer_name = crit_match.group(1).strip()
        if not industry:
          industry = crit_match.group(2).strip()
          context["industry"] = industry
      if not customer_name:
        simple_match = re.search(r"Tailor presentation text to ([A-Z][a-zA-Z0-9_& ]+?)(?: in the|\.|$)", criteria)
        if simple_match and simple_match.group(1).lower() not in ("the target customer", "the customer"):
          customer_name = simple_match.group(1).strip()
      if customer_name and not context.get("customer_name"):
        context["customer_name"] = customer_name

    account_info = ""
    if customer_name:
      account_info += f"Target Customer: {customer_name}\n"
      briefing = context.get("customer_research") or self._get_or_research_customer(customer_name, context=context)
      if briefing:
        account_info += f"Customer Research Briefing:\n{briefing}\n"
    if industry:
      account_info += f"Industry: {industry}\n"
    if sub_industry:
      account_info += f"Sub-Industry: {sub_industry}\n"

    glossary_info, matched_vertical = get_domain_and_account_glossary_with_name(context, criteria)
    persona_info, matched_persona = get_persona_guidelines_with_name(context, criteria)
    dk_grounding, _ = self._fetch_developer_knowledge_grounding(criteria, all_deck_texts, context=context)
    product_knowledge_guidelines = load_skill_instructions("product_knowledge")

    system_instruction = (
        "You are an executive Google Cloud Go-to-Market (GTM) Principal"
        " Strategist, Narrative Architect, and Lead Copywriter.\nYour mission"
        " is to transform an ENTIRE hybrid presentation deck (combining"
        " Reusable Reference Slides and Phase 2 Synthesized Slides) into a"
        " single, seamless, consultative executive story.\n\nCRITICAL"
        " DECK-WIDE EDITORIAL & COHESION MANDATES:\n0. HIGH-PRIORITY USER"
        " TRANSFORMATION & EXECUTIVE PERSONA DIRECTIVE (OVERRIDES GENERIC"
        " DEFAULTS):\n   - Whenever `Customization Criteria` or `EXECUTIVE"
        " PERSONA GUIDELINES` specifies a concrete transformation request or"
        " target executive persona (e.g., 'Customize to CFO needs', 'Tailor"
        " for CISO', 'Condense bullets', or specific account priorities), you"
        " MUST visibly and substantively reframe every unlocked shape on the"
        " targeted slide(s) ('action_title', 'sub_card_header',"
        " 'reusable_body', and 'architecture_value_framing') to directly"
        " fulfill that instruction!\n   - For example, when targeting a"
        " **CFO** or financial audience, re-anchor the slide's Action Title,"
        " sub-card headers, and body sentences around **quantifiable ROI,"
        " gross margin expansion, working capital velocity, FinOps unit"
        " economics, TCO reduction, and predictable OpEx governance**.\n   -"
        " NEVER leave unlocked shapes unchanged or merely swap a company name"
        " when the user requests a persona or criteria transformation.\n   -"
        " If an input shape contains multiple paragraphs separated by `\\n`"
        " (such as a card header on line 1 followed by body text on line 2),"
        " you MUST preserve the exact `\\n` line structure and transform BOTH"
        " the header line and the body line(s).\n1. GRANULAR CUSTOMIZATION"
        " INTENSITY BY SLIDE JOB & SHAPE ROLE (NON-NEGOTIABLE):\n   - Each"
        " slide specifies 'slide_job', 'customization_intensity',"
        " 'is_reusable', 'slide_origin', 'agenda_section_index',"
        " 'agenda_section_title', 'assigned_agenda_subtopic',"
        " 'agenda_section_subtopics', 'prev_slide_context', and"
        " 'next_slide_context'.\n   - A0. CONTEXT / IMPERATIVE / FOUNDATION"
        " SLIDES ('slide_job': 'Context_Imperative' — 85% Context & Imperative"
        " Framing):\n     * These slides appear at the opening of the deck"
        " (CVI Part 1: Why Change / Context / Strategic Imperative).\n     *"
        " DO NOT pitch Google Cloud products in the 'action_title' of a"
        " 'Context_Imperative' slide! Frame the 'action_title',"
        " 'sub_card_header', and 'reusable_body' around the customer's"
        " strategic imperative, data/operational foundation requirements, and"
        " why legacy approaches must evolve (e.g., 'Re-evaluating Uniqlo\\'s"
        " global data foundation for real-time LifeWear demand' or 'Core"
        " operational priorities driving Uniqlo\\'s digital retail"
        " evolution').\n   - A. SOLUTION / USE-CASE / WORKFLOW SLIDES"
        " ('slide_job': 'Solution_Use_Case' — 85% Deep Use-Case Re-Anchoring"
        " Intensity):\n     * SHALLOW 1-WORD NOUN SWAPS (e.g., merely"
        " replacing 'media' with '[Customer]' while leaving generic template"
        " sub-topics unchanged) ARE STRICTLY FORBIDDEN.\n     * You MUST"
        " deeply re-anchor the slide's 'action_title', every"
        " 'sub_card_header', and every 'reusable_body' shape directly to the"
        " **PRIMARY CUSTOMER INITIATIVE & USE CASE** stated in `Customization"
        " Criteria` AND the slide's 'assigned_agenda_subtopic' (e.g., if the"
        " customer's objective is video translation and dubbing across global"
        " geographies, transform generic media sub-card headers like 'Create &"
        " edit video', 'Engage audiences', 'Live Production', 'Creative"
        " Assist', 'Internal Media Search' into specific initiative"
        " sub-workflows such as 'Multi-language AI dubbing', 'Voice & lip-sync"
        " cloning', 'Localized catalog search', 'Automated subtitle studio',"
        " and 'Global regional compliance', and rewrite their companion card"
        " bodies to explain how Google Cloud solves that exact workflow for"
        " the customer).\n     * STRICT AGENDA SECTION & SUBTOPIC ALIGNMENT:\n"
        "       - When 'assigned_agenda_subtopic' is provided, the slide's"
        " 'action_title', 'sub_card_header', and 'reusable_body' MUST directly"
        " address that exact subtopic while connecting to the customer's named"
        " systems, brands, and operational priorities from `Customer Research"
        " Briefing`.\n       - When 'agenda_section_title' addresses"
        " **Operational Bottlenecks, Challenges, Friction, or Current State**,"
        " the slide's 'action_title' and body MUST explicitly frame the"
        " customer's operational bottlenecks, fragmented silos, or structural"
        " friction. NEVER rewrite a Bottlenecks / Current State slide into a"
        " generic positive solution headline.\n       - When"
        " 'agenda_section_title' addresses a **Joint Value Discovery Workshop,"
        " Discovery Sprint, Next Steps, or Implementation Roadmap**, the"
        " slide's 'action_title' and cards MUST explicitly frame the **Joint"
        " Value Discovery Workshop, 3-Step Pilot Charter, or Architecture"
        " Sprint**. NEVER write or retain commercial seat-licensing or"
        " pay-as-you-go pricing copy on a Workshop / Next Steps slide!\n      "
        " - When multiple slides share the same 'agenda_section_title', each"
        " slide MUST focus on its distinct 'assigned_agenda_subtopic' so"
        " slides in the same section never repeat the same points.\n     *"
        " CONVERSATIONAL UI MOCKUP & CHAT BUBBLE LOCALIZATION:\n       -"
        " Whenever a Reusable Reference Slide contains sample user prompts,"
        " chat bubbles, search queries, or conversational UI mockup text, you"
        " MUST localize and rewrite those prompts to reflect the target"
        " customer's actual geography, product catalog, and primary use case"
        " while staying strictly <= 'max_chars'.\n   - B. ARCHITECTURE &"
        " UNIFIED STACK SLIDES ('slide_job': 'Architecture_Stack' — 40%"
        " Shape-Level Lock Intensity):\n     * Shapes with 'role':"
        " 'locked_product_badge' represent official Google Cloud product and"
        " architecture layer badges (e.g., 'Gemini Enterprise', 'AI"
        " Hypercomputer', 'Agents & Applications', 'AI Platform', 'Models',"
        " 'BigQuery', 'Model Garden') — return them 100% verbatim.\n     * By"
        " contrast, you MUST customize the slide's 'action_title' and"
        " 'architecture_value_framing' shapes so the headline, framing"
        " subtitle, and layer descriptions explicitly explain how this unified"
        " Google Cloud stack powers the target customer's primary initiative"
        " and use case (while keeping all official Google Cloud product names"
        " inside those descriptions intact).\n   - C. BESPOKE SYNTHESIZED"
        " ARCHETYPES ('slide_job': 'Bespoke_Archetype', 'is_reusable': false —"
        " 100% Executive Specificity):\n     * Their 'action_title' and"
        " 'phase2_synthesized_body' shapes ('preserve_body_content': true)"
        " were already custom-synthesized for the customer in Phase 2 with"
        " rich executive Action Titles.\n     * DO NOT rewrite, shorten, or"
        " replace shapes on 'is_reusable': false slides — return their text"
        " verbatim and generate only their 'transition_hook'!\n\n2. MANDATORY"
        " TRIPARTITE CVI SPEAKER NOTES & TRANSITION HOOKS ('speaker_notes' &"
        " 'transition_hook'):\n   - For EVERY slide in the batch, generate:\n "
        "    * 'speaker_notes': Structured Tripartite CVI Speaker Notes"
        " tailored to the transformed slide content and target executive"
        " persona in this exact format:\n       Key Takeaway: [1-sentence"
        " executive synthesis of the slide's core business value]\n\n      "
        " Talking Points:\n       • [Substantive consultative talking point 1"
        " addressing Card 1 / primary operational driver]\n       •"
        " [Substantive consultative talking point 2 addressing Card 2 /"
        " architectural & data mechanism]\n       • [Substantive consultative"
        " talking point 3 addressing Card 3 / measurable P&L or enterprise"
        " outcome]\n\n       Discovery Question:\n       • [1 consultative,"
        " open-ended executive discovery question ending with '?']\n     *"
        " 'transition_hook': If 'is_final_slide_in_deck' is false, ALWAYS"
        ' output "🔗 Transition to next slide: [1-2 sentence verbal presenter'
        " bridge connecting this slide's takeaway to next_slide_context]\""
        " (NEVER use \"🎯 Executive Takeaway:\" when 'is_final_slide_in_deck'"
        " is false!). Only when 'is_final_slide_in_deck' is true, output \"🎯"
        ' Executive Takeaway: [summary and call-to-action]".\n   - NEVER use'
        " retired product terms ('Gemini Enterprise app', 'the GE app',"
        " 'Gemini Enterprise Agent Platform', 'GEAP', 'GECX', 'Sobi', 'Spark',"
        " 'Gemini Enterprise platform', 'Vertex AI', or 'Powered by Gemini')"
        " in speaker notes or transition hooks; strictly follow the attached"
        " PRODUCT KNOWLEDGE SKILL GUIDELINES ('Gemini', 'Gemini platform',"
        " 'Gemini for [industry]', 'Model Garden in Gemini platform', 'agent"
        " runtime in Gemini platform', 'Antigravity in Gemini platform',"
        " 'Gemini Enterprise [Business/Standard/Plus] edition', 'Built with"
        " Gemini').\n\n3. STRICT INDUSTRY VERTICAL SKILL GROUNDING &"
        " ANTI-CONTAMINATION:\n   - You MUST ground all domain terminology,"
        " industry challenges, solution capabilities, operational workflows,"
        " and business metrics strictly on the attached INDUSTRY VERTICAL"
        " SKILL GUIDELINES.\n   - ABSOLUTELY FORBIDDEN: NEVER invent,"
        " hallucinate, or cross-pollinate terminology from unrelated"
        " industries.\n\n4. STRICT VOCABULARY, GOOGLE BRAND VOICE HEADLINE &"
        " SUB-CARD HEADER MANDATE (FULL EDITORIAL DEPTH):\n   - No two slide"
        " titles may share the same leading phrase, verb, or structure.\n   -"
        " STRICT ANTI-GERUND & ANTI-COMMAND MANDATE (Google Brand Voice & Tone"
        " — 'Get to the point' & 'Write like you talk'): NEVER start slide"
        " titles with '-ing' continuous/gerund verbs (e.g. NEVER start with"
        " 'Reimagining...', 'Elevating...', 'Uniting...', 'Activating...',"
        " 'Scaling...', 'Orchestrating...', 'Establishing...', 'Driving...',"
        " or 'Unlocking...') and NEVER write bare imperative command titles,"
        " Title-Case slogans, or short 2-to-4 word labels (e.g., NEVER write"
        " 'Predictable GPU scaling', 'Automated model governance', 'Unlock"
        " Agentic Commerce', or 'Automate Employee Workflows').\n   - Instead,"
        " write crisp, conversational, assertive declarative thesis headlines"
        " in **Sentence case** (capitalize only the first word and proper"
        " nouns/product names/acronyms) using **Subject + finite active verb +"
        " outcome** or a **clean noun/contrast phrase** (e.g., 'Autonomous"
        " agents transform global banking workflows', 'One governed data"
        " fabric unifies 169PB on BigQuery', 'Alphabet AI research meets HSBC"
        " global scale', 'From fragmented copilots to an autonomous"
        " enterprise', 'Joint governance and a phased path to production').\n "
        "  - Primary Slide Action Titles ('role': 'action_title' with"
        " 'max_chars' >= 45 on 'is_reusable': true slides) MUST be complete,"
        " substantive, consultative 7-to-10 word executive thesis headlines"
        " (44 to 'max_chars' characters, strictly <= 'max_chars').\n   -"
        " Left-Rail Primary Slide Action Titles ('role': 'action_title' with"
        " 'max_chars' < 45) MUST be consultative, Sentence-case 6-to-8 word"
        " thesis headlines (38 to 'max_chars' characters, strictly <="
        " 'max_chars') — NEVER shrink a slide title to a 3-word fragment!\n  "
        " - NEVER append 'for [Customer]' to internal slide titles.\n   -"
        " Sub-card headers ('role': 'sub_card_header' with 'max_chars' >= 16)"
        " MUST be substantive **2-to-4 word conceptual pillar headers**"
        " ('min_chars' to 'max_chars' characters, e.g., 'Multi-model market"
        " intelligence', 'Institutional trade velocity', 'Unified 169PB data"
        " fabric') — NEVER output a single 1-word label or bare imperative"
        " command, and strictly match the slide's 'header_case_style' ('Title"
        " Case' or 'Sentence case') across all sub-card headers on the"
        " slide.\n   - Compact 1-word UI badges or pills ('role':"
        " 'short_badge_or_header') MUST remain strictly <= 'max_chars'.\n\n5."
        " STRICT CVI NARRATIVE DENSITY FLOOR ('min_chars') & BOUNDING BOX"
        " CEILING ('max_chars'):\n   - Every shape in the input payload"
        " includes 'char_count', 'font_size' (in pt), 'min_chars',"
        " 'target_chars', and 'max_chars'.\n   - SPACIOUS CARD BODY DENSITY"
        " MANDATE ('role': 'reusable_body' with 'min_chars' >= 85): You MUST"
        " write a complete, self-contained **14-to-20 word compound executive"
        " sentence** between 'min_chars' (92+ chars) and 'max_chars' (110-115"
        " chars) structured as: `[Specific Operational/Financial Driver] +"
        " [Mechanism] + [Enterprise/P&L Impact]` (e.g., 'Escalating"
        " promotional markdowns and supply chain volatility compress gross"
        " margins across global wholesale and direct-to-consumer footwear"
        " channels.').\n   - STRICTLY FORBIDDEN ON SPACIOUS CARDS: NEVER write"
        " short 4-to-7 word telegraphic fragments (< 85 characters, such as"
        " 'Markdowns erode DTC gross margin.' or 'Stockouts trap working"
        " capital.') when 'min_chars' >= 85! Every card body on a multi-card"
        " slide MUST have uniform 2-to-3 line visual density (95 to 114"
        " characters).\n   - Every transformed shape MUST stay between"
        " 'min_chars' and 'max_chars' (aiming for 'target_chars' and NEVER"
        " EXCEEDING 'max_chars') to guarantee both executive richness and zero"
        " shape overflow!\n   - CRITICAL MULTI-PARAGRAPH / MULTI-BULLET RULE:"
        " If an input shape text contains multiple lines or bullet items"
        " separated by newlines (\\n), you MUST preserve the exact same number"
        " of lines separated by newlines (\\n) — NEVER collapse a multi-bullet"
        " shape into a single paragraph!\n\n6. STRICT THIRD-PARTY REFERENCE"
        " IMMUTABILITY (0% RULE) & 'CYMBAL' WHITE-LABEL EXCEPTION:\n   - NEVER"
        " alter, rename, or rebrand real third-party customer case studies"
        " (e.g. Wendy's, Lowe's, Carrefour, Spotify, PayPal), quotes, or"
        " empirical metrics. Keep them 100% intact.\n   - CRITICAL WHITE-LABEL"
        " EXCEPTION: 'Cymbal' (including 'Cymbal Retail', 'Cymbal Superstore',"
        " 'Cymbal Shops', 'Cymbal Direct', 'Cymbal Bank', 'Cymbal Health',"
        " 'Cymbal FinTech', 'Cymbal Sports', '@cymbal.com') is Google Cloud's"
        " fictional white-label placeholder brand, NEVER a real customer! You"
        " MUST ALWAYS replace every 'Cymbal' reference (in titles, headers,"
        " body text, chat prompts, UI mockups, and speaker notes) with the"
        f" target customer ({customer_name or 'the target enterprise'}).\n\n7."
        " MANDATORY OCTOBER 2026 CANONICAL PRODUCT NOMENCLATURE & ARCHITECTURE"
        " FIDELITY (Enterprise-Brand-Unification):\n   - Always use current, official"
        " October 2026 Google Cloud & Gemini brand unification"
        " nomenclature.\nMANDATORY PRODUCT KNOWLEDGE"
        f" GUIDELINES:\n{product_knowledge_guidelines}\n\n{dk_grounding}\n8."
        " OUTPUT FORMAT: Return a valid JSON object with the following"
        ' schema:\n   {\n     "slides": [\n       {\n        '
        ' "slide_id": "...",\n         "speaker_notes": "Key Takeaway:'
        " ...\\n\\nTalking Points:\\n• ...\\n• ...\\n• ...\\n\\nDiscovery"
        ' Question:\\n• ...?",\n         "transition_hook": "🔗 Transition'
        ' to next slide: ...",\n         "shapes": [\n           {\n      '
        '       "shape_id": "...",\n             "transformed_text":'
        ' "..."\n           }\n         ]\n       }\n     ]\n   }\n'
    )

    try:
      primary_model, fallback_model = self._select_model(criteria)
      thinking_cfg = (
          types.ThinkingConfig(thinking_level=types.ThinkingLevel.MEDIUM)
          if "3.8" in primary_model
          else None
      )
      full_deck_spine_lines = [
          f"  - Slide {sd.get('slide_index')} ({sd.get('slide_id')}):"
          f" \"{sd.get('slide_title')}\" | {sd.get('slide_origin')}"
          for sd in structured_deck
      ]
      full_deck_spine_summary = (
          "FULL-DECK NARRATIVE SPINE (For Cross-Deck Storyline & Headline"
          " Diversity Awareness — ensure no two slides share the same leading"
          " verb or phrase, and NEVER start slide titles with '-ing' gerunds or"
          " bare imperative commands):\n"
          + "\n".join(full_deck_spine_lines)
      )
      chunk_size = 4
      deck_chunks = [
          (c_idx, structured_deck[i : i + chunk_size])
          for c_idx, i in enumerate(range(0, len(structured_deck), chunk_size))
      ]

      def _run_chunk_call(chunk_slides):
        chunk_prompt = (
            f"{account_info}\n{glossary_info}\n{persona_info}\n{full_deck_spine_summary}\nCustomization"
            f" Criteria: '{criteria}'\n\nPresentation Deck Elements to"
            f" Transform in This Batch:\n{json.dumps(chunk_slides, indent=2)}"
        )
        resp = self.generate_content_with_fallback(
            client=self.client,
            model=primary_model,
            contents=[chunk_prompt],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2,
                response_mime_type="application/json",
                thinking_config=thinking_cfg,
                http_options=types.HttpOptions(timeout=90000),
            ),
            fallback_model=fallback_model,
        )
        p_obj = self.extract_json(resp)
        if isinstance(p_obj, dict) and isinstance(p_obj.get("slides"), list):
          return p_obj["slides"]
        if isinstance(p_obj, list):
          return p_obj
        if isinstance(p_obj, dict) and isinstance(p_obj.get("data"), list):
          return p_obj["data"]
        return []

      def _transform_chunk(chunk_tuple):
        c_idx, chunk_slides = chunk_tuple
        try:
          res = _run_chunk_call(chunk_slides)
          if res:
            return res
        except Exception as chunk_err:
          print(
              f"[TextTransformerWorkflow] Warning: Chunk {c_idx}"
              f" ({len(chunk_slides)} slides) encountered error ({chunk_err});"
              " retrying in 2-slide sub-batches with ThinkingLevel.MEDIUM..."
          )
        # Fault-isolated retry in smaller 2-slide sub-batches with ThinkingLevel.MEDIUM preserved
        sub_results = []
        for s_i in range(0, len(chunk_slides), 2):
          sub_slice = chunk_slides[s_i : s_i + 2]
          try:
            sub_res = _run_chunk_call(sub_slice)
            if sub_res:
              sub_results.extend(sub_res)
          except Exception as sub_err:
            print(
                "[TextTransformerWorkflow] Warning: Sub-batch retry failed for"
                f" chunk {c_idx}: {sub_err}"
            )
        return sub_results

      parsed_slides = []
      if len(deck_chunks) == 1:
        parsed_slides = _transform_chunk(deck_chunks[0])
      else:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(len(deck_chunks), 6)
        ) as chunk_exec:
          for chunk_res in chunk_exec.map(_transform_chunk, deck_chunks):
            if chunk_res:
              parsed_slides.extend(chunk_res)

      if parsed_slides:
        print(f"[TextTransformerWorkflow] Received holistic response for {len(parsed_slides)} slides. Mapping to deck shapes...")

        for idx, slide in enumerate(output_slides):
          if bool(
              slide.get("_skip_mutation")
              or slide.get("is_proof_point")
              or slide.get("is_cited_stats_slide")
              or slide.get("is_cust_ref")
              or slide.get("_source_datastore_key") == "cust_ref"
          ):
            continue
          slide_id = str(
              slide.get("slideId")
              or slide.get("slide_id")
              or slide.get("id")
              or f"slide_{idx+1}"
          )
          is_reusable = bool(slide.get("is_reusable", True))
          is_arch_slide = bool(
              slide.get("is_architecture_product_slide", False)
          )

          # Find matching parsed slide by:
          # 1. exact slide_id match
          # 2. slide_index match (idx + 1)
          # 3. "slide_{idx+1}" / "Slide {idx+1}" match
          # 4. positional fallback (only when parsed_slides count matches output_slides count)
          matched_p_slide = None
          for p_s in parsed_slides:
            p_s_id = str(p_s.get("slide_id") or p_s.get("slideId") or "")
            p_s_idx = p_s.get("slide_index") or p_s.get("index")
            if p_s_id and p_s_id == slide_id:
              matched_p_slide = p_s
              break
            if p_s_idx is not None and str(p_s_idx) == str(idx + 1):
              matched_p_slide = p_s
              break
            if p_s_id in (str(idx + 1), f"slide_{idx+1}", f"Slide {idx+1}"):
              matched_p_slide = p_s
              break

          if (
              not matched_p_slide
              and len(parsed_slides) == len(output_slides)
              and idx < len(parsed_slides)
          ):
            matched_p_slide = parsed_slides[idx]

          if matched_p_slide:
            raw_s_idx = slide.get("slideIndex")
            if raw_s_idx is None:
              raw_s_idx = slide.get("slide_index")
            has_zero_based = any(
                (s.get("slideIndex") == 0 or s.get("slide_index") == 0)
                for s in output_slides
                if isinstance(s, dict)
            )
            if raw_s_idx is not None:
              actual_slide_num = int(raw_s_idx) + (1 if has_zero_based else 0)
            else:
              actual_slide_num = idx + 1
            has_cover_font = any(
                isinstance(sh_d, dict)
                and float(sh_d.get("fontSize") or 0.0) >= 42.0
                for sh_d in (slide.get("data") or [])
            )
            is_cover = bool(
                slide.get("is_cover_slide")
                or slide.get("is_title_slide")
                or (
                    idx == 0
                    and actual_slide_num == 1
                    and (len(output_slides) > 1 or has_cover_font)
                )
            )
            p_shapes = matched_p_slide.get("shapes", [])
            shape_map = {}
            p_shapes_list = []
            for sh in p_shapes:
              sh_id = str(sh.get("shape_id") or sh.get("shapeId") or "")
              t_text = sh.get("transformed_text") or sh.get("text") or ""
              if t_text:
                p_shapes_list.append(t_text)
                if sh_id:
                  shape_map[sh_id] = t_text

            # Attach Speaker Notes & Transition Hook if returned (and sanitize per Enterprise-Brand-Unification)
            is_final_slide = bool(
                slide.get(
                    "is_final_slide_in_deck",
                    idx == len(output_slides) - 1,
                )
            )
            gen_notes = self._sanitize_output(
                str(matched_p_slide.get("speaker_notes") or "").strip(),
                is_cover_slide=False,
                customer_name=customer_name,
                original_len=0,
            )
            transition_hook = self._sanitize_output(
                str(matched_p_slide.get("transition_hook") or "").strip(),
                is_cover_slide=False,
                customer_name=customer_name,
                original_len=0,
            )
            if transition_hook:
              if not is_final_slide and transition_hook.startswith(
                  "🎯 Executive Takeaway:"
              ):
                transition_hook = (
                    "🔗 Transition to next slide:"
                    + transition_hook[len("🎯 Executive Takeaway:") :]
                )
              elif (
                  not transition_hook.startswith("🔗 Transition to next slide:")
                  and not transition_hook.startswith("🎯 Executive Takeaway:")
              ):
                prefix = (
                    "🎯 Executive Takeaway: "
                    if is_final_slide
                    else "🔗 Transition to next slide: "
                )
                transition_hook = f"{prefix}{transition_hook}"
            if gen_notes:
              slide["transformed_speaker_notes"] = gen_notes
            if transition_hook:
              slide["transition_hook"] = transition_hook
              existing_notes = self._sanitize_output(
                  str(slide.get("speaker_notes") or "").strip(),
                  is_cover_slide=False,
                  customer_name=customer_name,
                  original_len=0,
              )
              if transition_hook not in existing_notes:
                slide["speaker_notes"] = (
                    f"{existing_notes}\n\n{transition_hook}".strip()
                    if existing_notes
                    else (
                        f"{gen_notes}\n\n{transition_hook}".strip()
                        if gen_notes
                        else transition_hook
                    )
                )
            elif gen_notes and not str(slide.get("speaker_notes") or "").strip():
              slide["speaker_notes"] = gen_notes

            # Format A: "data" array of shapes
            if "data" in slide and isinstance(slide["data"], list):
              primary_title_idx = self._select_primary_title_idx(slide["data"])
              hdr_case_style = slide.get("_header_case_style")

              for s_idx, s in enumerate(slide["data"]):
                sh_id = str(s.get("shapeId") or s.get("shape_id") or s.get("id") or "")
                raw_t = str(s.get("text") or "").strip()
                font_sz = s.get("fontSize") or 12
                is_title_shape = s_idx == primary_title_idx

                # Shape-level lock for official Google Cloud product/layer badges
                if not is_title_shape and self._is_locked_gcp_product_badge(
                    raw_t, is_architecture_slide=is_arch_slide
                ):
                  s["text"] = self._sanitize_output(
                      raw_t,
                      is_cover_slide=False,
                      customer_name=customer_name,
                      original_len=0,
                  )
                  continue

                new_val = shape_map.get(sh_id)
                # Fallback to positional shape matching ONLY if no shape_id matched on this slide and counts match 1:1
                if (
                    not new_val
                    and not shape_map
                    and len(p_shapes_list) == len(slide["data"])
                    and s_idx < len(p_shapes_list)
                ):
                  new_val = p_shapes_list[s_idx]

                if not is_reusable:
                  if not is_title_shape:
                    continue
                  # Preserve Phase 2 synthesized Action Titles when already 6+ words, and never downgrade to <6 word slogans
                  if (
                      len(raw_t.split()) >= 6
                      or len(str(new_val or "").strip().split()) < 6
                  ):
                    continue

                if new_val:
                  sanitized_val = self._sanitize_output(
                      new_val,
                      is_cover_slide=is_cover,
                      customer_name=customer_name,
                      original_len=len(raw_t),
                      is_action_title=is_title_shape,
                      font_size=font_sz,
                      width_pt=s.get("width_pt"),
                      clearance_pt=s.get("clearance_pt"),
                      height_pt=s.get("height_pt"),
                  )
                  # Enforce 2-to-3 word conceptual headers and uniform casing on sub_card_header shapes
                  _, m_c_sh = self._compute_char_budget(
                      len(raw_t),
                      font_size=font_sz,
                      is_action_title=is_title_shape,
                      width_pt=s.get("width_pt"),
                      clearance_pt=s.get("clearance_pt"),
                      height_pt=s.get("height_pt"),
                  )
                  is_bold_or_med = bool(
                      s.get("bold") or int(s.get("fontWeight") or 400) >= 500
                  )
                  w_pt_sh = float(s.get("width_pt") or 0.0)
                  h_pt_sh = float(s.get("height_pt") or 0.0)
                  is_sub_hdr = (
                      not is_title_shape
                      and not is_cover
                      and "\n" not in sanitized_val
                      and 16 <= m_c_sh <= 42
                      and (
                          (
                              is_bold_or_med
                              and len(raw_t) <= 45
                              and not (w_pt_sh >= 185.0 and h_pt_sh >= 42.0 and float(font_sz or 12) <= 13.0)
                          )
                          or (
                              11.5 <= float(font_sz or 12) <= 18.0
                              and len(raw_t) <= 35
                              and w_pt_sh <= 190.0
                          )
                      )
                  )
                  if is_sub_hdr and sanitized_val:
                    hdr_words = sanitized_val.split()
                    if hdr_case_style == "Title Case" and len(hdr_words) >= 2:
                      _minor = {"a", "an", "the", "and", "or", "for", "to", "in", "on", "of", "at", "by", "with"}
                      tc_words = []
                      for wi, hw in enumerate(hdr_words):
                        if hw.isupper() and len(hw) >= 2:
                          tc_words.append(hw)
                        elif wi > 0 and hw.lower() in _minor:
                          tc_words.append(hw.lower())
                        else:
                          tc_words.append(hw[:1].upper() + hw[1:])
                      sanitized_val = " ".join(tc_words)
                    elif hdr_case_style == "Sentence case" and len(hdr_words) >= 2:
                      sc_words = []
                      for wi, hw in enumerate(hdr_words):
                        if hw.isupper() and len(hw) >= 2:
                          sc_words.append(hw)
                        elif wi == 0:
                          sc_words.append(hw[:1].upper() + hw[1:].lower())
                        else:
                          sc_words.append(hw.lower())
                      sanitized_val = " ".join(sc_words)
                  s["text"] = sanitized_val
            # Format B: nested dict
            else:
              shapes_dict = slide.get("shapes", {})
              if isinstance(shapes_dict, dict) and shapes_dict:
                for shape_id, segs in shapes_dict.items():
                  raw_new = shape_map.get(shape_id)
                  if raw_new and isinstance(segs, dict) and is_reusable:
                    sanitized = self._sanitize_output(
                        raw_new,
                        is_cover_slide=is_cover,
                        customer_name=customer_name,
                        font_size=12.0,
                    )
                    sorted_k = sorted(
                        segs.keys(),
                        key=lambda x: int(x) if str(x).isdigit() else x,
                    )
                    lines = [
                        ln.strip() for ln in sanitized.split("\n") if ln.strip()
                    ]
                    if len(lines) > 1 and len(sorted_k) > 1:
                      for i, sk in enumerate(sorted_k):
                        if i < len(lines):
                          segs[sk]["Text"] = lines[i]
                          if i < len(lines) - 1:
                            segs[sk]["HadNewline"] = True
                        else:
                          if isinstance(segs[sk], dict):
                            segs[sk]["Text"] = ""
                    else:
                      if "0" in segs:
                        segs["0"]["Text"] = sanitized
                      elif sorted_k:
                        segs[sorted_k[0]]["Text"] = sanitized
                      for sk in sorted_k[1:]:
                        if isinstance(segs[sk], dict):
                          segs[sk]["Text"] = ""
              else:

                def apply_shapes(obj, path=""):
                  if isinstance(obj, dict):
                    for k, v in list(obj.items()):
                      cur_path = f"{path}.{k}" if path else k
                      if k.lower() in ("text", "content") and isinstance(
                          v, str
                      ):
                        raw_new = shape_map.get(cur_path) or shape_map.get(k)
                        if raw_new and is_reusable:
                          obj[k] = self._sanitize_output(
                              raw_new,
                              is_cover_slide=is_cover,
                              customer_name=customer_name,
                              original_len=len(v.strip()),
                              font_size=12.0,
                          )
                      else:
                        apply_shapes(v, cur_path)
                  elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                      apply_shapes(item, f"{path}[{i}]")

                apply_shapes(slide)

        if customer_name:
          for sl_d in output_slides:
            if not isinstance(sl_d, dict) or bool(
                sl_d.get("is_proof_point")
                or sl_d.get("is_cust_ref")
                or sl_d.get("_source_datastore_key") == "cust_ref"
            ):
              continue
            for nk in (
                "speaker_notes",
                "transformed_speaker_notes",
                "transition_hook",
            ):
              if isinstance(sl_d.get(nk), str) and sl_d[nk]:
                sl_d[nk] = self.replace_cymbal_with_customer(
                    sl_d[nk], customer_name
                )
            if isinstance(sl_d.get("data"), list):
              for sh_d in sl_d["data"]:
                if isinstance(sh_d, dict) and isinstance(sh_d.get("text"), str):
                  sh_d["text"] = self.replace_cymbal_with_customer(
                      sh_d["text"], customer_name
                  )
            if isinstance(sl_d.get("shapes"), dict):
              for seg_map in sl_d["shapes"].values():
                if isinstance(seg_map, dict):
                  for seg_v in seg_map.values():
                    if isinstance(seg_v, dict) and isinstance(
                        seg_v.get("Text"), str
                    ):
                      seg_v["Text"] = self.replace_cymbal_with_customer(
                          seg_v["Text"], customer_name
                      )

        print("[TextTransformerWorkflow] Whole-Deck Holistic Transformation applied successfully!")
        return output_slides

    except Exception as e:
      print(f"[TextTransformerWorkflow] Whole-deck holistic transformation error: {e}")

    # Fallback to per-slide parallel transformation if holistic call fails
    print("[TextTransformerWorkflow] Falling back to per-slide parallel transformation...")
    def process_single_slide(slide_item):
      s_idx, s_data = slide_item
      if not isinstance(s_data, dict) or s_data.get("_skip_mutation"):
        return s_idx, s_data

      s_id = str(s_data.get("slideId") or s_data.get("slide_id") or s_data.get("id") or f"slide_{s_idx+1}")
      if target_slide_ids:
        should_run = (
            (s_idx + 1) in target_slide_ids
            or s_id in target_slide_ids
            or str(s_idx + 1) in [str(x) for x in target_slide_ids]
            or str(s_id) in [str(x) for x in target_slide_ids]
        )
        if not should_run:
          return s_idx, s_data

      if "data" in s_data and isinstance(s_data["data"], list):
        texts_to_trans = [s.get("text", "") for s in s_data["data"] if isinstance(s, dict) and s.get("text")]
        if texts_to_trans:
          trans_texts = self.execute_batch(
              texts_to_trans, criteria=criteria, context=context, slide_name=f"Slide {s_idx+1}", slide_data=s_data
          )
          t_idx = 0
          for s in s_data["data"]:
            if isinstance(s, dict) and s.get("text"):
              if t_idx < len(trans_texts):
                s["text"] = trans_texts[t_idx]
                t_idx += 1
      return s_idx, s_data

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(output_slides), 12)) as executor:
      ordered = list(executor.map(process_single_slide, enumerate(output_slides)))
      ordered.sort(key=lambda x: x[0])
      res_slides = [r[1] for r in ordered]
      if customer_name:
        for sl_d in res_slides:
          if isinstance(sl_d, dict) and isinstance(sl_d.get("data"), list):
            for sh_d in sl_d["data"]:
              if isinstance(sh_d, dict) and isinstance(sh_d.get("text"), str):
                sh_d["text"] = self.replace_cymbal_with_customer(
                    sh_d["text"], customer_name
                )
      return res_slides
