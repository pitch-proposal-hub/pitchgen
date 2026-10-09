"""Outline generation skill leveraging customer context and search tools."""

import json
import os
import re
from google import genai
try:
  from google.cloud import discoveryengine_v1 as discoveryengine
except ImportError as e:
  import sys
  print(f"[DEBUG] ImportError caught during discoveryengine import: {e}")
  print(f"[DEBUG] sys.path: {sys.path}")
  try:
    import google
    print(f"[DEBUG] google module path: {google.__path__}")
  except Exception as ge:
    print(f"[DEBUG] Failed to print google path: {ge}")
  try:
    import google.cloud
    print(f"[DEBUG] google.cloud module path: {google.cloud.__path__}")
  except Exception as gce:
    print(f"[DEBUG] Failed to print google.cloud path: {gce}")
  raise e
from google.cloud import secretmanager
from google.genai import types
from agents.workflows.base_workflow import BaseWorkflow
from agents.workflows.developer_knowledge_workflow import DeveloperKnowledgeWorkflow
from config_loader import resolve_secret_with_cache

_CUSTOMER_RESEARCH_CACHE: dict[str, str] = {}
_INDUSTRY_HIERARCHY_CACHE: dict[tuple[str, str], dict] = {}


class OutlineWorkflow(BaseWorkflow):
  """Generates a structured presentation outline from business context."""

  def __init__(self, config):
    super().__init__(
        "OutlineWorkflow", "Generates a structured outline from business context."
    )
    self.config = config
    self.project_id = config["default"]["project_name"]
    self.gemini_model = config["default"].get(
        "gemini_model",
        config["default"].get("gemini_model_1", "gemini-3.5-flash-lite"),
    )
    self.fast_model = config["default"].get(
        "gemini_model_1", "gemini-3.5-flash-lite"
    )

    # Discovery Engine Setup
    self.discovery_client = discoveryengine.SearchServiceClient()
    self.location = "global"

    # Secret Manager Setup (Resolved with cache)
    try:
      if hasattr(self.config, "has_option") and self.config.has_option("datastore", "website"):
        self.website_secret_name = self.config.get("datastore", "website")
      elif isinstance(self.config, dict) and isinstance(self.config.get("datastore"), dict):
        self.website_secret_name = self.config.get("datastore", {}).get("website")
      else:
        self.website_secret_name = None
    except Exception:
      self.website_secret_name = None
    self.website_store_id = (
        resolve_secret_with_cache(self.website_secret_name)
        if self.website_secret_name
        else None
    )
    if self.website_store_id:
      self.website_serving_config = self.discovery_client.serving_config_path(
          project=self.project_id,
          location=self.location,
          data_store=self.website_store_id,
          serving_config="default_config",
      )
    else:
      self.website_serving_config = None
    self.dk_skill = DeveloperKnowledgeWorkflow(config)
    from agents.workflows.foundation_deck_workflow import FoundationDeckWorkflow
    self.foundation_deck_workflow = FoundationDeckWorkflow(config)

  @staticmethod
  def is_s0_customer_discovery_mode(
      win_cycle: str = "", business_context: str = ""
  ) -> bool:
    """Returns True when the request targets S0 Discovery / Customer-Research & Discovery-Questions mode."""
    wc_upper = str(win_cycle or "").strip().upper()
    if wc_upper == "S0" or "S0" in wc_upper or "FIRST_CALL" in wc_upper:
      return True
    ctx_low = str(business_context or "").lower()
    discovery_signals = (
        "customer research",
        "discovery question",
        "discovery questions",
        "opportunity discovery",
        "drive discovery",
        "qualify opportunity",
        "qualification questions",
        "first call",
    )
    return sum(1 for sig in discovery_signals if sig in ctx_low) >= 2 or (
        "customer research" in ctx_low and "question" in ctx_low
    )

  CANONICAL_CLOUD_GTM_ARCHETYPES = (
      "First_Call_Discovery",
      "Executive_Vision_Briefing",
      "Sales_Play_Business_Pitch",
      "Technical_Solutioning_Pitch",
      "Architecture_PoC_Workshop",
      "Value_Case_Commercial_Proposal",
      "Competitive_Takeout_Migration",
      "QBR_Adoption_Expansion",
  )

  ARCHETYPE_CANONICAL_MAP = {
      # Canonical 8 Cloud GTM Archetypes
      "first_call_discovery": "First_Call_Discovery",
      "executive_vision_briefing": "Executive_Vision_Briefing",
      "sales_play_business_pitch": "Sales_Play_Business_Pitch",
      "technical_Solutioning_pitch": "Technical_Solutioning_Pitch",
      "technical_solutioning_pitch": "Technical_Solutioning_Pitch",
      "architecture_poc_workshop": "Architecture_PoC_Workshop",
      "value_case_commercial_proposal": "Value_Case_Commercial_Proposal",
      "competitive_takeout_migration": "Competitive_Takeout_Migration",
      "qbr_adoption_expansion": "QBR_Adoption_Expansion",
      # Legacy & Fine-Grained Aliases -> Canonical 8
      "discovery_first_call": "First_Call_Discovery",
      "first_call": "First_Call_Discovery",
      "executive_vision_strategic": "Executive_Vision_Briefing",
      "executive_vision_thought_leadership": "Executive_Vision_Briefing",
      "executive_vision": "Executive_Vision_Briefing",
      "industry_business_pitch": "Sales_Play_Business_Pitch",
      "general_value_pitch": "Sales_Play_Business_Pitch",
      "technical_architecture": "Technical_Solutioning_Pitch",
      "cio_technical_strategy": "Technical_Solutioning_Pitch",
      "technical_deep_dive": "Architecture_PoC_Workshop",
      "practitioner_technical_architecture": "Architecture_PoC_Workshop",
      "poc_engagement_proposal": "Architecture_PoC_Workshop",
      "poc_results_value": "Architecture_PoC_Workshop",
      "cfo_business_case": "Value_Case_Commercial_Proposal",
      "commercial_proposal": "Value_Case_Commercial_Proposal",
      "business_case": "Value_Case_Commercial_Proposal",
      "customer_adoption_playbook": "QBR_Adoption_Expansion",
      "executive_qbr_value_realization": "QBR_Adoption_Expansion",
      "qbr": "QBR_Adoption_Expansion",
  }

  ARCHETYPE_CVI_BLUEPRINTS = {
      "First_Call_Discovery": {
          "win_stage": "S0: Qualify",
          "lead_role": "FSR / KAx (Support: Platform CE)",
          "cvi_split": (
              "Context (Why Change): 40% | Vision (Why Now): 20% | Solution"
              " (Why Google): 20% | Impact (Proof): 10% | Realization"
              " (Next Steps): 10%"
          ),
          "directive": (
              "Spend 40% of the outline on CVI Part 1 'Why Change' (Industry"
              " Market Trends, Customer Current State, Cost of Inaction, and"
              " consultative discovery questions), 20% on Future State Vision,"
              " 20% on a high-level L100 Solution Preview, 10% on Peer Proof,"
              " and close with a Joint Discovery / Value Workshop charter."
          ),
      },
      "Executive_Vision_Briefing": {
          "win_stage": "S0–S1: Inspire / Strategy (EBC)",
          "lead_role": "FSR + Executive Sponsor (Support: Platform CE)",
          "cvi_split": (
              "Context (Why Change): 25% | Vision (Strategic Partnership): 30%"
              " | Solution (Why Google): 15% | Impact (Value & Proof): 20% |"
              " Realization (Governance): 10%"
          ),
          "directive": (
              "Tailor for C-Suite / Board / EBC at L100 depth. Emphasize"
              " macro industry transformation (25%), multi-year Strategic"
              " Partnership & One Google / Alphabet co-innovation (30%),"
              " executive capability pillars (15%), board-level Business Value"
              " & Peer Proof (20%), and Joint Executive Governance (10%)."
          ),
      },
      "Sales_Play_Business_Pitch": {
          "win_stage": "S1: Position & Build",
          "lead_role": "FSR + Sales Specialist (Support: Platform CE)",
          "cvi_split": (
              "Context (Why Change): 25% | Vision (Why Now): 15% | Solution"
              " (Sales Play Capabilities): 25% | Impact (ROI & Peer Proof):"
              " 25% | Realization (Next Steps): 10%"
          ),
          "directive": (
              "Follow the core L100–L200 Sales Play Business Pitch arc:"
              " connect the customer's business challenges and cost of inaction"
              " (25%) to a transformed Future State (15%), the selected Google"
              " Cloud Priority Sales Play capabilities & differentiators (25%),"
              " quantified Business Value & immutable Customer Proof Points"
              " (25%), and a clear Path to Technical Solutioning (10%)."
          ),
      },
      "Technical_Solutioning_Pitch": {
          "win_stage": "S2: Tech Solutioning",
          "lead_role": "Platform CE / Practice CE (Support: FSR)",
          "cvi_split": (
              "Context (Technical Recap): 10% (1 slide) | Vision (Platform"
              " Strategy): 10% | Solution (L200 Architecture & Capabilities):"
              " 50% | Impact (Engineering Proof): 15% | Realization (Roadmap):"
              " 15%"
          ),
          "directive": (
              "Compress 'Why Change' Context to 1 concise technical"
              " requirements recap slide (10%) and allocate 50% of the deck to"
              " L200 Solution Architecture, Gemini Enterprise & Google Cloud"
              " technical differentiators, data/agent integration, and"
              " multi-cloud governance, followed by engineering proof (15%)"
              " and implementation roadmap (15%)."
          ),
      },
      "Architecture_PoC_Workshop": {
          "win_stage": "S2: Tech Validation & PoC",
          "lead_role": "Practice CE / Platform CE (Support: GCC / Partners)",
          "cvi_split": (
              "Context (Problem & Success Criteria): 10% (1 slide) | Vision:"
              " 5% | Solution (L300 Reference Architecture & Security): 55% |"
              " Impact (Benchmarks): 10% | Realization (PoC Plan & Milestones):"
              " 20%"
          ),
          "directive": (
              "Focus on securing the Technical Win (L200–L300). Open with 1"
              " slide on technical problem statement & success criteria, spend"
              " 55% on end-to-end Reference Architecture, data/agent pipelines,"
              " VPC-SC security & IAM governance, 10% on performance"
              " benchmarks, and 20% on concrete PoC scope, dataset onboarding,"
              " and validation milestones."
          ),
      },
      "Value_Case_Commercial_Proposal": {
          "win_stage": "S1–S3: Build Business Case & Propose",
          "lead_role": "FSR + Value Creation / Deal Desk (Support: CE, GCC)",
          "cvi_split": (
              "Context (Cost of Inaction): 15% | Vision: 10% | Solution"
              " (Economic Drivers): 10% | Impact (3-Year ROI, TCO, NPV & Peer"
              " Proof): 40% | Realization (Commercials, EDP/CUD & CAF Plan):"
              " 25%"
          ),
          "directive": (
              "Tailor for CFO, Finance, Procurement, and CIO. Dedicate 40% of"
              " the outline to quantified Business Value (3-year ROI, TCO"
              " reduction, NPV, payback <12-18 mo, unit economics, and peer"
              " financial benchmarks) and 25% to Commercial Packaging (EDP,"
              " CUDs, RaMP incentives) and value realization governance."
          ),
      },
      "Competitive_Takeout_Migration": {
          "win_stage": "S1–S2: Competitive Displacement & Migration",
          "lead_role": "FSR + Specialist + Practice CE (Support: RaMP)",
          "cvi_split": (
              "Context (Legacy Debt & Lock-In): 20% | Vision: 10% | Solution"
              " (Why Google Wins & Coexistence Arch): 35% | Impact (Takeout"
              " TCO & Peer Swaps): 20% | Realization (RaMP Migration Plan): 15%"
          ),
          "directive": (
              "Structure for competitive takeout and de-risked migration:"
              " expose incumbent technical debt, egress taxes, and lock-in"
              " friction (20%), highlight Google Cloud's open lakehouse/AI"
              " differentiation and brownfield coexistence architecture (35%),"
              " prove TCO savings and peer migrations (20%), and detail the"
              " de-risked RaMP Migration Factory & commercial incentives (15%)."
          ),
      },
      "QBR_Adoption_Expansion": {
          "win_stage": "S4: Mobilize & Deliver / S0': Optimize & Grow",
          "lead_role": "Outcome CE / GCC / TAM / FSR",
          "cvi_split": (
              "Context (Partnership Scorecard): 15% | Vision (Next-Wave"
              " Co-Innovation): 20% | Solution (Expansion Sales Plays): 20% |"
              " Impact (Value Realized to Date): 25% | Realization"
              " (Next-Quarter 90-Day Plan): 20%"
          ),
          "directive": (
              "Structure as an Executive QBR & Expansion Playbook: review"
              " partnership scorecard, SLA health, and Value Realized to date"
              " (40% combined Context + Impact), optimize current commitment"
              " adoption, introduce Next-Wave Expansion Sales Plays (40%"
              " Vision + Solution), and align on the next 30-60-90 day joint"
              " execution charter (20%)."
          ),
      },
  }

  @classmethod
  def normalize_presentation_archetype(cls, archetype: str) -> str:
    """Normalizes any canonical or legacy archetype identifier to one of the 8 Canonical Cloud GTM Archetypes."""
    if not archetype:
      return "Sales_Play_Business_Pitch"
    cleaned = str(archetype).strip()
    key = cleaned.lower().replace("-", "_").replace(" ", "_")
    # Strip descriptive suffixes if passed from UI dropdown (e.g., "First_Call_Discovery (S0: Qualify)")
    if "(" in key:
      key = key.split("(", 1)[0].strip("_ ")
    return cls.ARCHETYPE_CANONICAL_MAP.get(key, "Sales_Play_Business_Pitch")

  @classmethod
  def get_archetype_cvi_directive(cls, archetype: str) -> str:
    """Returns the dynamic 5-Cluster CVI allocation and narrative blueprint for an archetype."""
    canonical = cls.normalize_presentation_archetype(archetype)
    bp = cls.ARCHETYPE_CVI_BLUEPRINTS.get(
        canonical, cls.ARCHETYPE_CVI_BLUEPRINTS["Sales_Play_Business_Pitch"]
    )
    return (
        f"- Canonical Cloud GTM Archetype: `{canonical}` (Selected:"
        f" `{archetype}`)\n- WIN Cycle Stage Alignment: {bp['win_stage']}\n-"
        f" GTM Role Ownership: {bp['lead_role']}\n- Dynamic 5-Cluster CVI"
        f" Allocation: {bp['cvi_split']}\n- Structural Blueprint Mandate:"
        f" {bp['directive']}"
    )

  def detect_presentation_archetype(
      self,
      client,
      business_context="",
      audience=None,
      segment="",
      win_cycle="",
      explicit_archetype="",
  ):
    """Detects the canonical Cloud GTM presentation archetype based on business context, audience, segment, and win_cycle."""
    import re

    if explicit_archetype and str(explicit_archetype).strip().lower() not in (
        "",
        "auto",
        "auto_detect",
        "auto-detect",
        "none",
        "null",
    ):
      return self.normalize_presentation_archetype(explicit_archetype)

    audience_list = (
        audience
        if isinstance(audience, list)
        else ([audience] if audience else [])
    )
    audience_str = " ".join([str(a) for a in audience_list]).lower()
    # Strip parenthetical examples from dropdown labels like "C-Suite / Executive (CEO, CFO, Board)"
    audience_no_parens = re.sub(r"\([^)]*\)", " ", audience_str)
    audience_words = set(re.findall(r"\b\w+\b", audience_no_parens))
    ctx_str = str(business_context).lower()
    ctx_words = set(re.findall(r"\b\w+\b", ctx_str))
    segment_str = str(segment).lower()
    win_cycle_raw = str(win_cycle).strip().upper()
    # Extract short stage code (e.g. "S0: Qualify" -> "S0", "S0': Optimize & Grow" -> "S0'")
    stage_match = re.match(r"^(S[0-4]'?)", win_cycle_raw)
    win_cycle_str = stage_match.group(1) if stage_match else win_cycle_raw

    # 1. QBR / Post-Sale Adoption & Expansion (S4 & S0')
    if (
        win_cycle_str in ("S4", "S0'", "S4'")
        or "qbr" in ctx_words
        or "quarterly business review" in ctx_str
        or "value realization" in ctx_str
        or "value realized" in ctx_str
        or "adoption playbook" in ctx_str
        or "customer adoption" in ctx_str
        or "mobilize" in ctx_str
        or "optimize and grow" in ctx_str
        or "outcome ce" in audience_str
        or "tam" in audience_words
    ):
      return "QBR_Adoption_Expansion"

    # 2. Competitive Takeout & Migration (S1-S2 Displacement)
    if (
        any(
            phrase in ctx_str
            for phrase in (
                "competitive takeout",
                "displace ",
                "displacement",
                "migrate off",
                "migrate from",
                "switch from",
                "replace aws",
                "replace azure",
                "replace snowflake",
                "replace databricks",
                "replace oracle",
                "replace vmware",
                "vs aws",
                "vs. aws",
                "vs azure",
                "vs. azure",
                "vs snowflake",
                "vs databricks",
                "ramp migration",
                "migration factory",
            )
        )
        or "takeout" in ctx_words
    ):
      return "Competitive_Takeout_Migration"

    # 3. First Call Discovery (S0: Qualify)
    if (
        self.is_s0_customer_discovery_mode(win_cycle_str, ctx_str)
        or "first call" in ctx_str
        or "intro" in ctx_words
        or "discovery call" in ctx_str
        or "maturity framework" in ctx_str
        or (
            win_cycle_str == "S0"
            and "ebc" not in ctx_str
            and "ceo" not in ctx_words
            and "board" not in audience_words
        )
    ):
      return "First_Call_Discovery"

    # 4. Value Case & Commercial Proposal (S1-S3 CFO ROI/TCO & Commercials)
    if (
        win_cycle_str == "S3"
        or any(
            w in ctx_words
            for w in (
                "roi",
                "tco",
                "npv",
                "cfo",
                "pricing",
                "edp",
                "cud",
                "sow",
            )
        )
        or "business case" in ctx_str
        or "commercial proposal" in ctx_str
        or "contract" in ctx_str
        or "procurement" in audience_words
        or "sourcing" in audience_words
        or (
            ("cfo" in audience_words or "finance" in audience_words)
            and "ceo" not in ctx_words
        )
    ):
      return "Value_Case_Commercial_Proposal"

    # 5. Architecture & PoC Workshop (S2 L300 / PoC Validation)
    if (
        any(w in ctx_words for w in ("poc", "l300", "vpc-sc"))
        or "proof of concept" in ctx_str
        or "reference architecture workshop" in ctx_str
        or "architecture workshop" in ctx_str
        or "technical validation" in ctx_str
        or "deep dive architecture" in ctx_str
        or "hands-on workshop" in ctx_str
    ):
      return "Architecture_PoC_Workshop"

    # 6. Technical Solutioning Pitch (S2 L200 Technical Pitch & CIO/CTO Strategy)
    if (
        win_cycle_str == "S2"
        or "architecture" in ctx_str
        or "data pipeline" in ctx_str
        or "technical pitch" in ctx_str
        or "tech pitch" in ctx_str
        or "l200" in ctx_words
        or "cto" in audience_words
        or "architect" in audience_words
        or "architects" in audience_words
        or "developers" in audience_words
        or "engineers" in audience_words
    ):
      return "Technical_Solutioning_Pitch"

    # 7. Executive Vision Briefing (S0-S1 EBC / C-Suite Strategic Partnership)
    if (
        "ebc" in ctx_str
        or "executive briefing" in ctx_str
        or "executive" in ctx_str
        or "ceo" in ctx_words
        or "one google" in ctx_str
        or "c-suite" in audience_str
        or "executive" in audience_words
        or "ceo" in audience_words
        or "board" in audience_words
        or "strategic" in segment_str
    ):
      return "Executive_Vision_Briefing"

    # 8. Sales Play Business Pitch (S1 Core L100 Solution & Industry Value Pitch)
    return "Sales_Play_Business_Pitch"

  def detect_sales_play(self, client, business_context, play_guidelines):
    """Detects all relevant sales plays from the user's business context."""
    prompt = f"""Analyze the following user business request and identify all applicable official Google Cloud Sales Plays that apply across Practice Areas (e.g. Agentic Workplace Transformation, AI, Data, Infrastructure, Security).

User Request: "{business_context}"

Guidelines & Available Sales Plays:
{play_guidelines}

Instructions:
1. Identify all relevant sales plays across the practice areas that match the user's needs. For example:
   - Agentic Workplace Transformation (e.g. "Lead the Agentic Workplace Transformation", "Lead the Agentic Workplace Transformation - Gemini Enterprise", "Lead the Agentic Workplace Transformation - Google Workspace")
   - AI (e.g. "Gemini Enterprise for Customer Experience", "Scale AI Apps and Agents", "Your Business, Your Models", "Leverage Generative Media in Your Business")
   - Security (e.g. "Agentic Defense with Google Security", "Secure Innovation with Google Cloud", "SOC Transformation", "Achieve Resilience Together with Mandiant")
   - Data (e.g. "Agentic Data Cloud", "Migrate, Modernize, and Build with Data Cloud")
   - Infrastructure (e.g. "AI Infrastructure", "Sovereign", "Migrate, Modernize and Build")
2. Return a JSON object with:
   - "detected_plays": A list of all matching sales plays from the guidelines (e.g., ["Lead the Agentic Workplace Transformation", "Gemini Enterprise for Customer Experience", "Scale AI Apps and Agents", "Secure Innovation with Google Cloud"]).
   - "primary_play": The single most central sales play.

Return ONLY the valid JSON object.
"""

    try:
      response = client.models.generate_content(
          model=self.fast_model,
          contents=prompt,
          config=types.GenerateContentConfig(
              response_mime_type="application/json",
              temperature=0,
          ),
      )
      res = self.extract_json(response, default={})
      detected_list: list[str] = []
      if isinstance(res, list):
        for item in res:
          if isinstance(item, str) and item.strip():
            detected_list.append(item.strip())
          elif isinstance(item, dict):
            sub_plays = item.get("detected_plays")
            if isinstance(sub_plays, list):
              detected_list.extend(str(p).strip() for p in sub_plays if p)
            else:
              single = (
                  item.get("detected_play")
                  or item.get("primary_play")
                  or item.get("sales_play")
                  or item.get("name")
              )
              if single:
                detected_list.append(str(single).strip())
      elif isinstance(res, dict):
        plays = res.get("detected_plays")
        if isinstance(plays, list) and plays:
          detected_list.extend(str(p).strip() for p in plays if p)
        else:
          detected = (
              res.get("detected_play")
              or res.get("primary_play")
              or res.get("sales_play")
          )
          if detected:
            detected_list.append(str(detected).strip())

      bc_low = str(business_context or "").lower()
      workspace_explicit = any(
          re.search(r"\b" + re.escape(kw) + r"\b", bc_low)
          for kw in (
              "workspace",
              "google workspace",
              "gws",
              "gmail",
              "google docs",
              "google sheets",
              "google slides",
              "google meet",
              "google chat",
              "google drive",
              "google vids",
              "workspace ai",
          )
      )
      if not workspace_explicit and detected_list:
        cleaned_plays: list[str] = []
        for p_item in detected_list:
          if "workspace" in p_item.lower():
            ge_replacement = (
                "Lead the Agentic Workplace Transformation - Gemini Enterprise"
            )
            if ge_replacement not in cleaned_plays:
              cleaned_plays.append(ge_replacement)
          elif p_item not in cleaned_plays:
            cleaned_plays.append(p_item)
        detected_list = cleaned_plays

      if any(
          k in bc_low
          for k in (
              "agentic commerce",
              "commerce",
              "shopping",
              "customer experience",
              "conversational commerce",
              "personalization",
          )
      ):
        for sp_default in (
            "Gemini Enterprise for Customer Experience",
            "Agentic Data Cloud",
        ):
          if sp_default not in detected_list:
            detected_list.append(sp_default)
      return detected_list
    except Exception as e:  # pylint: disable=broad-exception-caught
      print(f"[OutlineWorkflow] Warning: Sales play detection failed: {e}")
      bc_low = str(business_context or "").lower()
      if any(
          k in bc_low
          for k in (
              "agentic commerce",
              "commerce",
              "shopping",
              "customer experience",
          )
      ):
        return [
            "Gemini Enterprise for Customer Experience",
            "Agentic Data Cloud",
        ]
      return []

  def web_search(self, query):
    content_search_spec = discoveryengine.SearchRequest.ContentSearchSpec(
        summary_spec=(
            discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec(
                summary_result_count=5,
                include_citations=True,
                ignore_adversarial_query=True,
                ignore_non_summary_seeking_query=True,
            )
        )
    )
    request = discoveryengine.SearchRequest(
        content_search_spec=content_search_spec,
        serving_config=self.website_serving_config,
        query=query,
        page_size=5,
    )
    try:
      response = self.discovery_client.search(request)
      return response.summary.summary_with_metadata.summary
    except Exception as e:  # pylint: disable=broad-exception-caught
      print(f"Web search error: {e}")
      return ""

  def research_customer(self, client, customer_name, existing_research=""):
    """Researches the customer using live Google Search to extract flagship products, tech stack, architecture, and strategic priorities."""
    if not customer_name:
      return "No customer name provided for research."

    if existing_research and len(str(existing_research).strip()) >= 150:
      print(
          "[OutlineWorkflow] -> Reusing existing session customer research for"
          f" '{customer_name}' ({len(str(existing_research))} chars)."
      )
      return str(existing_research)

    cache_key = customer_name.strip().lower()
    if cache_key in _CUSTOMER_RESEARCH_CACHE:
      cached = _CUSTOMER_RESEARCH_CACHE[cache_key]
      print(
          "[OutlineWorkflow] -> Cache hit: Reusing customer research for"
          f" '{customer_name}' ({len(cached)} chars)."
      )
      return cached

    prompt = f"""Conduct a focused corporate and technical research on '{customer_name}' using Google Search.
Extract and summarize concisely:
1. Core Business & Value Proposition: What does {customer_name} do, who are their primary users/customers, and what is their business model?
2. Flagship Products & Internal Platforms: What are their primary customer-facing products, developer platforms, proprietary algorithms, and brand names (e.g. for Nebius: Token Factory inference gateway, ClickHouse, GPU cloud; for Netflix: Open Connect CDN, SSAI transcode pipelines; for Canva: Magic Studio; for Klarna: AI Assistant; for Stripe: Radar, Agentic Billing)?
3. Technology Stack & Infrastructure Primitives: What hardware (GPUs/TPUs), orchestrators (Slurm, GKE/Kubernetes), databases/analytics (ClickHouse, BigQuery, PostgreSQL, Iceberg), and networking (InfiniBand, RoCE) do they use or build?
4. Strategic Priorities & Engineering Challenges: What are their top technical and business initiatives (e.g., token inference latency, Model FLOPs Utilization, multi-cloud interconnect, cost per token, subscriber retention)?

Provide an authoritative, detailed technical briefing with specific platform names and domain lexicon.
"""
    try:
      print(f"[OutlineWorkflow] Performing live Google Search customer research for: '{customer_name}'...")
      response = client.models.generate_content(
          model=self.fast_model,
          contents=prompt,
          config=types.GenerateContentConfig(
              tools=[types.Tool(google_search=types.GoogleSearch())]
          ),
      )
      extracted = self.extract_text(response)
      if extracted and len(extracted.strip()) >= 150:
        print(f"[OutlineWorkflow] -> Retrieved live customer research for '{customer_name}' ({len(extracted)} chars).")
        _CUSTOMER_RESEARCH_CACHE[cache_key] = extracted
        return extracted
      print(f"[OutlineWorkflow] -> Sparse research for '{customer_name}' (<150 chars). Falling back to industry vertical grounding.")
      fallback = (
          f"Target Account: {customer_name} (SMB / Emerging Account with"
          " limited public web telemetry).\nGrounding Strategy: Ground"
          " strictly on authoritative industry vertical, sub-industry"
          " operational KPIs, and domain lexicon without hallucinating"
          " nonexistent proprietary platforms."
      )
      _CUSTOMER_RESEARCH_CACHE[cache_key] = fallback
      return fallback
    except Exception as e:  # pylint: disable=broad-exception-caught
      print(f"[OutlineWorkflow] Warning: Customer research failed: {e}")
      return (
          f"Target Account: {customer_name} (SMB / Emerging Account).\n"
          f"Grounding Strategy: Ground strictly on authoritative industry vertical and sub-industry domain lexicon."
      )

  def resolve_industry_hierarchy(
      self,
      client,
      business_context="",
      customer_name="",
      customer_research="",
      raw_industry="",
  ):
    """Maps sub/micro-industries or niche customer domains to the closest canonical parent Google Cloud industry vertical, while preserving granular sub-industry and micro-industry for deep customization."""
    cache_key = (
        str(customer_name).strip().lower(),
        str(raw_industry).strip().lower(),
    )
    if cache_key[0] and cache_key in _INDUSTRY_HIERARCHY_CACHE:
      cached = _INDUSTRY_HIERARCHY_CACHE[cache_key]
      print(
          "[OutlineWorkflow] -> Cache hit: Resolved Industry Hierarchy for"
          f" '{customer_name}': {cached.get('industry')}"
      )
      return dict(cached)

    canonical_industries = [
        "Technology",
        "Retail",
        "Financial Services",
        "Healthcare & Life Sciences",
        "Media & Entertainment",
        "Manufacturing",
        "Automotive",
        "Telecommunications",
        "Travel & Hospitality",
        "Logistics & Supply Chain",
        "Energy & Utilities",
        "Gaming",
        "Public Sector",
    ]

    prompt = f"""Analyze the customer, user request, and domain context below:
    
    User Request: "{business_context}"
    Customer Name: "{customer_name}"
    Customer Research: "{customer_research}"
    Initial Industry: "{raw_industry}"
    
    Canonical Google Cloud Industry Verticals:
    {canonical_industries}
    
    Instructions:
    1. Identify the closest matching parent 'closest_canonical_industry' from the Canonical list.
       - If the user/customer operates in a micro-vertical (e.g. 'Sneaker Resale', 'Luxury Watches', 'Ghost Kitchens', 'Crypto Trading', 'Formula 1', 'Cold Chain Shipping', 'EV Battery'), find its closest parent vertical from the list.
    2. Identify the specific 'sub_industry' (e.g. 'Athletic Footwear & Apparel', 'Luxury Goods', 'Restaurants & Food Service', 'Capital Markets & FinTech', 'Motorsports & Broadcasting', 'Freight & Cold Chain').
    3. Identify the granular 'micro_industry' (e.g. 'D2C Secondary Sneaker Marketplace', 'High-Horology Watchmaking', 'Cloud Kitchen Delivery Hub', 'High-Frequency Crypto Exchange', 'F1 Trackside Aerodynamics Telemetry').
    4. Provide 3-5 key domain-specific pain points, technical KPIs, and business vocabulary terms ('domain_lexicon') to drive customized copywriting.
    
    Return your response in JSON format with:
    - "closest_canonical_industry": exact parent name from the Canonical list
    - "sub_industry": string
    - "micro_industry": string
    - "domain_lexicon": list of strings
    """
    try:
      response = client.models.generate_content(
          model=self.fast_model,
          contents=prompt,
          config=types.GenerateContentConfig(
              response_mime_type="application/json",
              temperature=0,
          ),
      )
      res = self.extract_json(response, default={})
      resolved = {
          "industry": (
              res.get("closest_canonical_industry") or raw_industry or ""
          ),
          "sub_industry": res.get("sub_industry") or "",
          "micro_industry": res.get("micro_industry") or "",
          "domain_lexicon": res.get("domain_lexicon") or [],
      }
      if cache_key[0]:
        _INDUSTRY_HIERARCHY_CACHE[cache_key] = dict(resolved)
      return resolved
    except Exception as e:
      print(f"[OutlineWorkflow] Warning: Industry hierarchy resolution failed: {e}")
      return {
          "industry": raw_industry or "",
          "sub_industry": "",
          "micro_industry": "",
          "domain_lexicon": [],
      }

  def determine_sub_industry(self, client, customer_name, customer_research, industry):
    """Determines the specific sub-industry of the customer from research data."""
    if not customer_name:
      return ""

    prompt = f"""Based on the customer name '{customer_name}' and the following customer research summary, determine their specific sub-industry vertical.
    
    Customer Research:
    {customer_research}
    
    Parent Industry: {industry}
    
    Identify the most accurate sub-industry (e.g., 'Grocery', 'Quick Service Restaurant (QSR)', 'Banking', 'E-commerce', 'Biopharma', 'Automotive OEM', 'Retail').
    Return your response in JSON format with a single key "sub_industry" containing the name of the sub-industry, or null if it cannot be determined.
    """
    try:
      response = client.models.generate_content(
          model=self.fast_model,
          contents=prompt,
          config=types.GenerateContentConfig(
              response_mime_type="application/json",
              temperature=0,
          ),
      )
      res = self.extract_json(response, default={})
      return res.get("sub_industry") or ""
    except Exception as e:  # pylint: disable=broad-exception-caught
      print(f"[OutlineWorkflow] Warning: Sub-industry classification failed: {e}")
      return ""

  def execute(self, context):
    business_context = context.get("business_context") or context.get("user_request") or ""
    raw_customer_name = str(context.get("customer_name", "")).strip()

    client = genai.Client(
        vertexai=True, project=self.project_id, location="global"
    )

    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "prompt_templates",
        "contextEntities.txt",
    )
    with open(prompt_path, "r") as f:
      entities_prompt = f.read()

    def _extract_entities_fn():
      try:
        response = client.models.generate_content(
            model=self.fast_model,
            contents=[entities_prompt, business_context, "\n[output]\n"],
            config=types.GenerateContentConfig(
                system_instruction="Please provide output in json format.",
                response_mime_type="application/json",
                temperature=0,
            ),
        )
        return self.extract_json(response, default={})
      except Exception as e:
        print(f"[OutlineWorkflow] Warning: Entity extraction failed: {e}")
        return {}

    from concurrent.futures import ThreadPoolExecutor
    from agents.skill_loader import load_skill_instructions, split_sales_plays_safely

    raw_selected_plays = split_sales_plays_safely([
        context.get("salesPlay"),
        context.get("sales_play"),
        context.get("secondary_sales_play"),
        context.get("additional_sales_plays"),
        context.get("sales_plays"),
    ])
    sales_play_selected = raw_selected_plays if raw_selected_plays else None
    if sales_play_selected:
      context["salesPlay"] = sales_play_selected
      context["sales_plays"] = sales_play_selected
    sales_play_instructions = load_skill_instructions("sales_play_selection")

    # If customer_name is already known, run entity extraction concurrently inside the thread pool
    if raw_customer_name and raw_customer_name not in ("-", "None", "null"):
      customer_name = raw_customer_name
      context["customer_name"] = customer_name
      existing_res = context.get("customer_research") or ""
      print(
          "[OutlineWorkflow] Executing concurrent preparation pipeline for:"
          f" '{customer_name}'..."
      )
      with ThreadPoolExecutor(max_workers=6) as executor:
        future_entities = executor.submit(_extract_entities_fn)
        future_research = executor.submit(
            self.research_customer, client, customer_name, existing_res
        )
        future_archetype = executor.submit(
            self.detect_presentation_archetype,
            client,
            business_context=business_context,
            audience=context.get("audience", []),
            segment=context.get("segment", ""),
            win_cycle=context.get("win_cycle")
            or context.get("sales_stage", ""),
            explicit_archetype=context.get("presentation_archetype", ""),
        )
        future_sales_play = (
            executor.submit(
                self.detect_sales_play,
                client,
                business_context,
                sales_play_instructions,
            )
            if (not sales_play_selected and sales_play_instructions)
            else None
        )
        entities = future_entities.result()
        print(f"Extracted entities: {entities}")
        solutions = list(
            set(context.get("solution", []) + entities.get("solution", []))
        )

        def fetch_dk_solutions(sols):
          sol_data_list = []
          for sol in sols:
            dk_summary = self.dk_skill.execute(sol)
            if dk_summary and "unavailable" not in dk_summary:
              sol_data_list.append(f"{sol}.\nDeveloper Docs: {dk_summary}")
          return "\n".join(sol_data_list)

        future_dk = executor.submit(fetch_dk_solutions, solutions)
        customer_research = future_research.result()
        archetype = future_archetype.result()
        if future_sales_play:
          detected_plays = future_sales_play.result()
          if detected_plays:
            sales_play_selected = detected_plays
            context["sales_plays"] = detected_plays
            context["salesPlay"] = detected_plays
        sol_data = future_dk.result()
    else:
      entities = _extract_entities_fn()
      print(f"Extracted entities: {entities}")
      customer_name = raw_customer_name
      if not customer_name or customer_name in ("-", "None", "null"):
        extracted_name = entities.get("customer_name") or ""
        if extracted_name and extracted_name.strip() not in (
            "-",
            "None",
            "null",
        ):
          customer_name = extracted_name.strip()
      context["customer_name"] = customer_name
      solutions = list(
          set(context.get("solution", []) + entities.get("solution", []))
      )
      existing_res = context.get("customer_research") or ""
      print(
          "[OutlineWorkflow] Executing concurrent preparation pipeline for:"
          f" '{customer_name}'..."
      )
      with ThreadPoolExecutor(max_workers=5) as executor:
        future_research = executor.submit(
            self.research_customer, client, customer_name, existing_res
        )
        future_archetype = executor.submit(
            self.detect_presentation_archetype,
            client,
            business_context=business_context,
            audience=context.get("audience", entities.get("audience", [])),
            segment=context.get("segment", ""),
            win_cycle=context.get("win_cycle")
            or context.get("sales_stage", ""),
            explicit_archetype=context.get("presentation_archetype", ""),
        )
        future_sales_play = (
            executor.submit(
                self.detect_sales_play,
                client,
                business_context,
                sales_play_instructions,
            )
            if (not sales_play_selected and sales_play_instructions)
            else None
        )

        def fetch_dk_solutions(sols):
          sol_data_list = []
          for sol in sols:
            dk_summary = self.dk_skill.execute(sol)
            if dk_summary and "unavailable" not in dk_summary:
              sol_data_list.append(f"{sol}.\nDeveloper Docs: {dk_summary}")
          return "\n".join(sol_data_list)

        future_dk = executor.submit(fetch_dk_solutions, solutions)

        customer_research = future_research.result()
        archetype = future_archetype.result()
        if future_sales_play:
          detected_plays = future_sales_play.result()
          if detected_plays:
            sales_play_selected = detected_plays
            context["sales_plays"] = detected_plays
            context["salesPlay"] = detected_plays
        sol_data = future_dk.result()

    context["customer_research"] = customer_research
    context["presentation_archetype"] = archetype

    # 3. Industry Hierarchy Resolution: Resolve canonical parent industry, sub-industry, and micro-industry
    raw_ind = context.get("industry") or entities.get("industry", "")
    hierarchy = self.resolve_industry_hierarchy(
        client=client,
        business_context=business_context,
        customer_name=customer_name,
        customer_research=customer_research,
        raw_industry=raw_ind,
    )
    industry = hierarchy["industry"]
    sub_industry = context.get("sub_industry") or hierarchy["sub_industry"]
    micro_industry = hierarchy["micro_industry"]
    domain_lexicon = hierarchy["domain_lexicon"]

    print(
        f"[OutlineWorkflow] Resolved Industry Hierarchy -> Closest Parent: '{industry}', "
        f"Sub-Industry: '{sub_industry}', Micro-Industry: '{micro_industry}'"
    )
    context["industry"] = industry
    context["sub_industry"] = sub_industry
    context["micro_industry"] = micro_industry
    context["domain_lexicon"] = domain_lexicon

    # 3b. Enrich with Golden Gate Customer Insights (2026 VoC/EBC), Blocker Mitigations, Compete SWOT & Priority Peers
    try:
      from agents.workflows.customer_insights_workflow import CustomerInsightsWorkflow

      reusable_cfg = (
          self.config.get("reusable", {})
          if isinstance(self.config, dict)
          else {}
      )
      enable_gg = str(
          reusable_cfg.get("enable_golden_gate_integration", "true")
      ).strip().lower() not in ("false", "0", "no")
      if enable_gg:
        insights_wf = CustomerInsightsWorkflow(self.config)
        strategic_insights = insights_wf.execute(
            customer_name=customer_name,
            industry=industry,
            sub_industry=sub_industry,
            sales_plays=split_sales_plays_safely(sales_play_selected),
        )
        context["strategic_customer_insights"] = strategic_insights
        if strategic_insights.get("formatted_briefing"):
          customer_research = (
              f"{customer_research}\n{strategic_insights['formatted_briefing']}"
          )
          context["customer_research"] = customer_research
    except Exception as ins_err:
      print(
          "[OutlineWorkflow] CustomerInsightsWorkflow notice (fail-open):"
          f" {ins_err}"
      )

    # Discover Premier Foundation Deck using exact resolved industry, stage, audience, and archetype
    foundation_deck = self.foundation_deck_workflow.execute({
        "user_request": business_context,
        "business_context": business_context,
        "customer_name": customer_name,
        "industry": industry,
        "sub_industry": sub_industry,
        "salesPlay": sales_play_selected,
        "sales_stage": (
            context.get("sales_stage") or context.get("win_cycle") or "S1"
        ),
        "win_cycle": (
            context.get("win_cycle") or context.get("sales_stage") or "S1"
        ),
        "audience": context.get("audience", []),
        "segment": context.get("segment", ""),
        "presentation_archetype": archetype,
    })

    # 4. Generate Outline
    outline_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "prompt_templates",
        "outlineGen.txt",
    )
    with open(outline_path, "r") as f:
      outline_prompt = f.read()

    # Dynamically load CVI Framework and WIN Cycle Skill instructions
    from agents.skill_loader import load_skill_instructions

    cvi_instructions = load_skill_instructions("cvi_framework")
    win_cycle_instructions = load_skill_instructions("win_cycle")

    if cvi_instructions:
      print(
          "[OutlineWorkflow] Dynamically loaded and injected 'cvi_framework'"
          " guidelines."
      )
      outline_prompt = (
          f"{outline_prompt}\n\n### Detailed CVI Framework"
          f" Guidelines:\n{cvi_instructions}"
      )

    if win_cycle_instructions:
      print(
          "[OutlineWorkflow] Dynamically loaded and injected 'win_cycle'"
          " guidelines."
      )
      outline_prompt = (
          f"{outline_prompt}\n\n### Google Cloud WIN Cycle"
          f" Guidelines:\n{win_cycle_instructions}"
      )

      # Grounding with detailed win cycle stages & roles
      from agents.skill_loader import load_skill_reference

      win_cycle_details = load_skill_reference(
          "win_cycle", "win_cycle_details.md"
      )
      if win_cycle_details:
        print(
            "[OutlineWorkflow] Dynamically grounded with detailed"
            " 'win_cycle_details' reference."
        )
        outline_prompt = (
            f"{outline_prompt}\n\n### Detailed WIN Cycle Stages &"
            f" Roles:\n{win_cycle_details}"
        )

    # Conditionally load Segment Targeting Skill if audience contains "segment" or segment names
    user_audiences = [a.lower().strip() for a in context.get("audience", [])]
    has_segment = "segment" in user_audiences or any(
        s in user_audiences
        for s in ["smb", "startups", "corporate", "enterprise", "strategic"]
    )
    if has_segment:
      segment_instructions = load_skill_instructions("segment_targeting")
      if segment_instructions:
        print(
            "[OutlineWorkflow] Dynamically loaded and injected 'segment_targeting'"
            " guidelines based on audience."
        )
        outline_prompt = (
            f"{outline_prompt}\n\n### Customer Segment Targeting"
            f" Guidelines:\n{segment_instructions}"
        )

    # Conditionally load Sales Play Selection and specific play guidelines
    if sales_play_selected and sales_play_instructions:
      print(
          "[OutlineWorkflow] Dynamically loaded 'sales_play_selection' guidelines"
          f" for: {sales_play_selected}"
      )
      outline_prompt = (
          f"{outline_prompt}\n\n### Google Cloud Sales Play"
          f" Guidelines:\n{sales_play_instructions}"
      )

      # Grounding for specific plays
      from agents.skill_loader import load_skill_reference

      plays_list = split_sales_plays_safely(sales_play_selected)

      combined_play_str = " ".join(plays_list).lower().replace("_", " ")

      # Map play keywords to reference files
      play_ref_map = {
          "scale_ai_apps_and_agents.md": ["scale ai", "scale apps", "agent platform"],
          "agentic_workplace_transformation.md": ["workplace", "awt", "workspace", "employee"],
          "gemini_enterprise_for_customer_experience.md": ["customer experience", "customer service", "cx", "contact center"],
          "security_sales_plays.md": ["security", "defense", "soc", "mandiant", "cybershield"],
          "agentic_data_cloud.md": ["data cloud", "bigquery", "agentic data"],
      }

      loaded_refs = set()
      for ref_file, keywords in play_ref_map.items():
        if any(kw in combined_play_str for kw in keywords):
          if ref_file not in loaded_refs:
            play_details = load_skill_reference("sales_play_selection", ref_file)
            if play_details:
              loaded_refs.add(ref_file)
              print(
                  f"[OutlineWorkflow] Dynamically loaded and grounded with '{ref_file}' play details."
              )
              outline_prompt = (
                  f"{outline_prompt}\n\n### Specific Sales Play Grounding Details ({ref_file}):\n{play_details}"
              )

    # Conditionally load Industry Specific Skills (Industry Verticals)
    from agents.skill_loader import get_domain_and_account_glossary

    industry_instructions = load_skill_instructions("industry_verticals")
    if industry_instructions:
      print(
          "[OutlineWorkflow] Dynamically loaded and injected 'industry_verticals' GTM guidelines."
      )
      outline_prompt = (
          f"{outline_prompt}\n\n### Google Cloud Industry Vertical Guidelines:\n{industry_instructions}"
      )

    glossary = get_domain_and_account_glossary({
        "industry": industry,
        "sub_industry": sub_industry,
    })
    if glossary:
      print(
          f"[OutlineWorkflow] Dynamically grounded with industry vertical glossary for: '{industry}' / '{sub_industry}'."
      )
      outline_prompt = f"{outline_prompt}\n\n{glossary}"

    domain_label = micro_industry or sub_industry
    if domain_label:
      lex_str = (
          ", ".join(domain_lexicon)
          if domain_lexicon
          else "Domain-specific operational KPIs & technical architecture"
      )
      outline_prompt = (
          f"{outline_prompt}\n\n### Sub-Industry & Micro-Industry Customization Mandate:\n"
          f"- Target Customer: {customer_name}\n"
          f"- Closest Canonical Parent Industry: {industry}\n"
          f"- Sub-Industry: {sub_industry}\n"
          f"- Micro-Industry / Specific Niche: {domain_label}\n"
          f"- Domain Lexicon & Target KPIs: {lex_str}\n"
          f"- CRITICAL CUSTOMIZATION MANDATE: Do NOT generate generic parent industry boilerplate. "
          f"Every outline topic, value driver, and narrative bullet point MUST speak directly to the operational reality, "
          f"specific technical workflows, competitive pressures, and domain vocabulary of '{domain_label}'."
      )

    # Conditionally load Presentation Archetypes Skill and active archetype grounding
    archetype_instructions = load_skill_instructions("presentation_archetypes")
    archetype_cvi_directive = self.get_archetype_cvi_directive(archetype)
    if archetype_instructions:
      print(
          "[OutlineWorkflow] Dynamically loaded and injected 'presentation_archetypes' GTM guidelines."
      )
      outline_prompt = (
          f"{outline_prompt}\n\n### Google Cloud Presentation Archetype"
          f" Guidelines:\n{archetype_instructions}\n\n### Active Presentation"
          " Archetype & Dynamic CVI Allocation"
          f" Directive:\n{archetype_cvi_directive}"
      )
    else:
      outline_prompt = (
          f"{outline_prompt}\n\n### Active Presentation Archetype & Dynamic CVI"
          f" Allocation Directive:\n{archetype_cvi_directive}"
      )

    if foundation_deck:
      f_deck_id = foundation_deck["primary_anchor_deck_id"]
      f_deck_title = foundation_deck["primary_anchor_deck_title"]
      f_source = foundation_deck.get("primary_anchor_deck_source", "")
      context["primary_anchor_deck_id"] = f_deck_id
      context["primary_anchor_deck_title"] = f_deck_title
      context["primary_anchor_deck_source"] = f_source
      context["anchor_decks"] = foundation_deck.get("anchor_decks", [])
      context["anchor_deck_ids"] = foundation_deck.get("anchor_deck_ids", [])
      context["anchor_deck_map"] = foundation_deck.get("anchor_deck_map", {})
      context["closest_industry"] = foundation_deck.get("closest_industry", "")
      context["vertical_anchor"] = foundation_deck.get("vertical_anchor")
      context["solution_anchors"] = foundation_deck.get("solution_anchors", [])

      anchors_summary_lines = []
      for a in foundation_deck.get("anchor_decks", []):
        anchors_summary_lines.append(
            f"- [{a.get('sales_play')} Foundation Asset]: '{a.get('deck_title')}' (Deck ID: {a.get('deck_id')})\n"
            f"  * Context / Overview: {a.get('group_summary', '')}\n"
            f"  * Match Reason: {a.get('match_reason', '')}"
        )
      anchors_text = "\n".join(anchors_summary_lines)

      print(
          f"[OutlineWorkflow] Anchoring outline on {len(foundation_deck.get('anchor_decks', []))} Foundation Decks: {[a['deck_title'] for a in foundation_deck.get('anchor_decks', [])]}"
      )
      req_plays = foundation_deck.get("required_sales_plays", [])
      context["required_sales_plays"] = req_plays
      req_plays_str = ", ".join(req_plays) if req_plays else "active plays"

      is_s0_discovery = self.is_s0_customer_discovery_mode(
          context.get("win_cycle") or context.get("sales_stage", ""),
          business_context,
      )
      context["is_s0_customer_discovery"] = is_s0_discovery
      if is_s0_discovery and not context.get("presentation_archetype_override"):
        archetype = "First_Call_Discovery"
        context["presentation_archetype"] = archetype

      discovery_guidance = (
          "- MEETING DISCOVERY & QUALIFICATION FOCUS: Because this meeting"
          " focuses on opportunity discovery and qualification for"
          f" '{customer_name}', ensure the opening and closing outline topics"
          f" explicitly include (a) '{customer_name}'s named strategic"
          " initiatives and current technology footprint from `customer_data`,"
          " (b) specific operational bottlenecks and consultative executive"
          " discovery questions (`?...`) to validate with leadership, and (c)"
          " a concrete Joint Value Discovery Workshop / pilot charter.\n"
          if is_s0_discovery
          else ""
      )
      outline_prompt = (
          f"{outline_prompt}\n\n### Customer-Centric Meeting Context & Sales"
          f" Play Grounding Directives:\n{anchors_text}\n- DEEP"
          " CUSTOMER-CENTRICITY MANDATE: Every single outline topic MUST be"
          f" tailored to '{customer_name}' and the specific meeting context in"
          f" `user_request`. Explicitly weave '{customer_name}'s actual"
          " strategic programs, operational priorities, digital platforms, and"
          " technology footprint from `customer_data` into the outline items"
          " rather than writing generic industry"
          f" boilerplate.\n{discovery_guidance}- SALES PLAY ALIGNMENT"
          f" DIRECTIVE: The meeting covers {len(req_plays)} selected Sales"
          f" Play(s): {req_plays_str}. Connect each selected sales play"
          f" directly to '{customer_name}'s specific business workflows, use"
          " cases, and value drivers so the solution narrative feels"
          f" custom-built for '{customer_name}'s meeting agenda.\n- INDUSTRY"
          " STRATEGIC CONTEXT DIRECTIVE: Ground Market Trends, Business"
          " Challenges, and Why Google Cloud on the customer's exact"
          " retail/industry domain and operational reality."
      )

    outline_data = {
        "audience": ", ".join(
            context.get("audience", entities.get("audience", []))
        ),
        "industry": industry,
        "sub_industry": sub_industry,
        "region": context.get("region") or entities.get("region", ""),
        "sales_stage": (
            context.get("sales_stage") or context.get("win_cycle") or "S1"
        ),
        "win_cycle": (
            context.get("win_cycle") or context.get("sales_stage") or "S1"
        ),
        "presentation_archetype": archetype,
        "is_s0_customer_discovery": bool(
            context.get("is_s0_customer_discovery")
        ),
        "primary_anchor_deck_id": context.get("primary_anchor_deck_id"),
        "primary_anchor_deck_title": context.get("primary_anchor_deck_title"),
        "anchor_deck_ids": context.get("anchor_deck_ids", []),
        "user_request": business_context,
        "deck_length": (
            context.get("deck_length")
            or context.get("request_type")
            or context.get("target_slide_count")
            or "Standard"
        ),
        "customer_data": customer_research,
        "solutions_data": sol_data,
        "outline_items": entities.get("outline_items", []),
    }

    # Redundant open closed by previous faulty edit
    # with open('prompt_templates/outlineGen.txt', 'r') as f:
    #     outline_prompt = f.read()

    try:
      response = client.models.generate_content(
          model=self.gemini_model,
          contents=[outline_prompt, json.dumps(outline_data), "\n[output]\n"],
          config=types.GenerateContentConfig(
              system_instruction="Please provide output in json format.",
              response_mime_type="application/json",
              temperature=0,
          ),
      )
      outline = self.extract_json(
          response,
          default={
              "title": f"Pitch Deck for {customer_name}",
              "outline": ["Executive Summary", "Solution Overview", "Next Steps"],
          },
      )
    except Exception as e:
      print(f"[OutlineWorkflow] Error generating outline: {e}")
      outline = {
          "title": f"Pitch Deck for {customer_name}",
          "outline": ["Executive Summary", "Solution Overview", "Next Steps"],
      }

    # Sanitize outline items for consultative proposition framing (Never take partnership for granted)
    import re
    cleaned_items = []
    for item in outline.get("outline", []):
      s_item = re.sub(
          r"(?i)\bWhy\s+([A-Za-z0-9\s&]+?)\s+(?:partners\s+with|chooses|selects)\s+Google\b",
          r"Why \1 Should Partner with Google",
          item,
      )
      cleaned_items.append(s_item)
    outline["outline"] = cleaned_items

    resolved_plays = context.get("required_sales_plays") or (
        sales_play_selected
        if isinstance(sales_play_selected, list)
        else [sales_play_selected]
        if sales_play_selected
        else []
    )
    outline["title"] = self.normalize_modern_cover_title(
        outline.get("title", ""),
        customer_name=customer_name,
        customer_research=customer_research,
        sales_plays=resolved_plays,
        industry=industry,
    )
    outline["customer_name"] = customer_name
    outline["industry"] = industry
    outline["sub_industry"] = sub_industry
    outline["micro_industry"] = micro_industry
    outline["domain_lexicon"] = domain_lexicon
    outline["deck_length"] = outline_data.get("deck_length", "Standard")
    outline["request_type"] = outline_data.get("deck_length", "Standard")
    outline["audience"] = context.get("audience", entities.get("audience", []))
    outline["sales_stage"] = outline_data.get("sales_stage", "S1")
    outline["win_cycle"] = outline_data.get("win_cycle", "S1")
    outline["required_sales_plays"] = resolved_plays
    outline["sales_plays"] = resolved_plays
    outline["salesPlay"] = resolved_plays
    outline["presentation_archetype"] = archetype
    outline["is_s0_customer_discovery"] = bool(
        context.get("is_s0_customer_discovery")
    )
    if context.get("primary_anchor_deck_id"):
      outline["primary_anchor_deck_id"] = context["primary_anchor_deck_id"]
      outline["primary_anchor_deck_title"] = context.get("primary_anchor_deck_title", "")
      outline["primary_anchor_deck_source"] = context.get("primary_anchor_deck_source", "")
      outline["anchor_decks"] = context.get("anchor_decks", [])
      outline["anchor_deck_ids"] = context.get("anchor_deck_ids", [])
      outline["anchor_deck_map"] = context.get("anchor_deck_map", {})
      outline["closest_industry"] = context.get("closest_industry", "")
      outline["vertical_anchor"] = context.get("vertical_anchor")
      outline["solution_anchors"] = context.get("solution_anchors", [])
    return outline

  @staticmethod
  def normalize_modern_cover_title(
      raw_title: str,
      customer_name: str = "",
      customer_research: str = "",
      sales_plays: list | None = None,
      industry: str = "",
  ) -> str:
    """Normalizes cover titles into modern, concise (<= 28 chars), colon-free Sentence-case headlines designed for 68pt hero typography."""
    import re

    t = (raw_title or "").strip().strip("\"'")
    cust = (customer_name or "").strip()
    if cust in ("-", "None", "null"):
      cust = ""

    # Detect iconic customer flagship product/brand concept when known (e.g. LifeWear for Uniqlo)
    combined_ctx = f"{t} {cust} {customer_research or ''}".lower()
    if "uniqlo" in combined_ctx or "lifewear" in combined_ctx:
      # If already a modern colon-free Uniqlo/LifeWear headline <= 28 chars, keep it Sentence-cased
      if (
          t
          and ":" not in t
          and "google cloud" not in t.lower()
          and "pitch deck" not in t.lower()
          and "proposal" not in t.lower()
          and len(t) <= 28
          and ("lifewear" in t.lower() or "uniqlo" in t.lower())
      ):
        pass
      else:
        return "Reimagining LifeWear with AI"

    # Strip rigid colon or dash splits like "Agentic Commerce: Google Cloud for Uniqlo" or "Uniqlo: Agentic Commerce"
    if ":" in t or " - " in t or " – " in t or " — " in t:
      parts = [p.strip() for p in re.split(r"[:\-\–\—]", t) if p.strip()]
      # Pick the segment that is NOT just the customer name or "Google Cloud for [Customer]"
      chosen_theme = ""
      for p in parts:
        p_low = p.lower()
        if cust and p_low == cust.lower():
          continue
        if re.match(
            r"^(?:google\s+cloud(?:\s+for\s+.+)?|co-innovating\s+with\s+google\s+cloud|pitch\s+deck.*|proposal.*)$",
            p_low,
        ):
          continue
        chosen_theme = p
        break
      if chosen_theme:
        t = chosen_theme

    # Remove boilerplate vendor phrases ("with Google Cloud", "Google Cloud Proposal for X", "Pitch Deck for X")
    t = re.sub(
        r"(?i)^(?:google\s+cloud\s+(?:proposal|pitch(?:\s+deck)?)\s+for|pitch\s+deck\s+for|proposal\s+for)\s+",
        "",
        t,
    ).strip()
    t = re.sub(r"(?i)\s+(?:with|on|by)\s+google\s+cloud\b.*$", "", t).strip()
    t = re.sub(r"(?i)^google\s+cloud\s*[&+]\s*", "", t).strip()

    # If stripping left only the customer name or generic boilerplate, synthesize a modern concise theme
    if (
        not t
        or (cust and t.lower() == cust.lower())
        or t.lower()
        in (
            "integrate efficiency",
            "innovate and transform",
            "transform and innovate",
            "strategic transformation",
            "google cloud pitch presentation",
        )
    ):
      plays_str = " ".join(str(p) for p in sales_plays or []).lower()
      ind_low = (industry or "").lower()
      if "agentic commerce" in plays_str or "retail" in ind_low:
        theme_base = "Agentic commerce"
      elif "data" in plays_str:
        theme_base = "Agentic data"
      elif "security" in plays_str:
        theme_base = "AI-powered security"
      elif "media" in ind_low or "gaming" in ind_low:
        theme_base = "Next-gen media"
      elif "financial" in ind_low or "bank" in ind_low:
        theme_base = "Intelligent finance"
      elif "health" in ind_low:
        theme_base = "Modernizing care"
      else:
        theme_base = "Next-gen AI"
      t = f"{theme_base} at {cust}" if cust else f"{theme_base} in action"
    elif cust and cust.lower() not in t.lower() and len(f"{t} at {cust}") <= 28:
      t = f"{t} at {cust}"

    # Enforce Sentence case while preserving proper nouns, customer name, and acronyms
    words = t.split()
    if words:
      preserve_tokens = {
          "ai",
          "ml",
          "roi",
          "sap",
          "it",
          "cx",
          "pos",
          "erp",
          "lifewear",
          "gemini",
          "bigquery",
      }
      if cust:
        for ct in re.findall(r"[A-Za-z0-9']+", cust):
          preserve_tokens.add(ct.lower())
      out_w = []
      for i, w in enumerate(words):
        clean_w = w.strip(",;:.!?\"'()")
        low_w = clean_w.lower()
        has_internal_cap = any(c.isupper() for c in clean_w[1:]) and any(
            c.islower() for c in clean_w
        )
        if i == 0:
          if clean_w.isupper() or has_internal_cap:
            out_w.append(w)
          else:
            out_w.append(w[0].upper() + w[1:].lower())
        elif (
            (len(clean_w) >= 2 and clean_w.isupper())
            or has_internal_cap
            or low_w in preserve_tokens
        ):
          if cust and low_w in {
              ct.lower() for ct in re.findall(r"[A-Za-z0-9']+", cust)
          }:
            # Match customer capitalization
            for ct in re.findall(r"[A-Za-z0-9']+", cust):
              if ct.lower() == low_w:
                out_w.append(ct)
                break
          elif low_w == "lifewear":
            out_w.append("LifeWear")
          elif low_w == "ai":
            out_w.append("AI")
          else:
            out_w.append(w)
        else:
          out_w.append(w.lower())
      t = " ".join(out_w)

    # Hard cap at 28 characters on a clean word boundary so 68pt cover titles never exceed 3 lines
    if len(t) > 28:
      if cust and f" at {cust}" in t and len(cust) <= 12:
        prefix_budget = 28 - len(f" at {cust}")
        prefix_words = t[: t.find(f" at {cust}")].split()
        kept = []
        cur_l = 0
        for pw in prefix_words:
          if cur_l + (1 if kept else 0) + len(pw) <= prefix_budget:
            kept.append(pw)
            cur_l += (1 if len(kept) > 1 else 0) + len(pw)
          else:
            break
        if kept:
          t = " ".join(kept) + f" at {cust}"
      if len(t) > 28:
        kept = []
        cur_l = 0
        for w in t.split():
          if cur_l + (1 if kept else 0) + len(w) <= 28:
            kept.append(w)
            cur_l += (1 if len(kept) > 1 else 0) + len(w)
          else:
            break
        if kept:
          t = " ".join(kept).rstrip(",;:-—&+/ ")

    return t


CANONICAL_CLOUD_GTM_ARCHETYPES = OutlineWorkflow.CANONICAL_CLOUD_GTM_ARCHETYPES
CANONICAL_PRESENTATION_ARCHETYPES = (
    OutlineWorkflow.CANONICAL_CLOUD_GTM_ARCHETYPES
)
normalize_presentation_archetype = (
    OutlineWorkflow.normalize_presentation_archetype
)
