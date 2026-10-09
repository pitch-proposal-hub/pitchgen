import functools
import json
import os
import re
from typing import Any


@functools.lru_cache(maxsize=64)
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

    # Strip YAML frontmatter strictly at the beginning of the file
    frontmatter_pattern = r"\A---\s*\n.*?\n---\s*\n"
    cleaned_content = re.sub(
        frontmatter_pattern, "", content, count=1, flags=re.DOTALL
    )

    return cleaned_content.strip()
  except Exception as e:
    print(f"[SkillLoader] Error reading skill {skill_name}: {e}")
    return ""


def get_matching_skill_instructions(
    query_text: str, always_include: list[str] = None
) -> str:
  """Dynamically scans all available skills in src/agents/skills/ and returns matching guidelines.

  Any skill whose directory name matches terms in query_text will be
  automatically loaded and injected.
  """
  if always_include is None:
    always_include = []

  current_dir = os.path.dirname(os.path.abspath(__file__))
  skills_dir = os.path.join(current_dir, "skills")
  if not os.path.exists(skills_dir):
    return ""

  query_lower = query_text.lower()
  query_tokens = set(re.findall(r"\w+", query_lower))

  loaded_sections = []
  for skill_name in sorted(os.listdir(skills_dir)):
    skill_path = os.path.join(skills_dir, skill_name)
    if not os.path.isdir(skill_path):
      continue

    skill_tokens = set(re.findall(r"\w+", skill_name.lower()))
    slide_job_keywords = {
        "navigation",
        "market trends",
        "current state",
        "strategic partnership",
        "partnership",
        "joint vision",
        "principles",
        "why google",
        "solution overview",
        "architecture",
        "business value",
        "proof points",
        "commercials",
        "path to prod",
        "tco",
        "roi",
        "cvi",
        "slide job",
        "job",
    }
    should_load = (
        skill_name in always_include
        or bool(query_tokens & skill_tokens)
        or any(token in query_lower for token in skill_tokens if len(token) > 3)
        or (
            skill_name == "slide_job"
            and any(kw in query_lower for kw in slide_job_keywords)
        )
        or (
            skill_name in ("use_case_context", "industry_verticals")
            and any(
                term in query_lower
                for term in ("use case", "use_case", "industry", "vertical")
            )
        )
        or (
            skill_name == "product_knowledge"
            and any(
                term in query_lower
                for term in (
                    "gemini",
                    "google ai",
                    "google cloud",
                    "gcp",
                    "model",
                    "flash",
                    "pro",
                    "vertex",
                    "latest",
                    "upgrade",
                    "veo",
                    "product",
                    "solution",
                    "architecture",
                    "bigquery",
                    "spanner",
                    "alloydb",
                    "agent studio",
                    "agent",
                    "ai",
                    "wiz",
                    "nano banana",
                    "workspace",
                    "antigravity",
                    "geap",
                    "agent garden",
                    "model garden",
                    "agent registry",
                    "agentspace",
                    "duet",
                    "powered by gemini",
                )
            )
        )
        or (
            skill_name == "compete_differentiation"
            and any(
                term in query_lower
                for term in (
                    "compete",
                    "competitor",
                    "differentiation",
                    "why google",
                    "aws",
                    "azure",
                    "microsoft",
                    "bedrock",
                    "snowflake",
                    "databricks",
                    "oracle",
                    "oci",
                    "openai",
                    "swot",
                    "vs",
                    "objection",
                    "one google",
                )
            )
        )
        or (
            skill_name == "customer_reference_governance"
            and any(
                term in query_lower
                for term in (
                    "customer reference",
                    "customer references",
                    "case study",
                    "case studies",
                    "proof point",
                    "proof points",
                    "customer_ref_library",
                    "customer story",
                    "customer stories",
                    "reference",
                )
            )
        )
        or (
            skill_name == "pitch_deck_qa"
            and any(
                term in query_lower
                for term in (
                    "qa",
                    "quality assurance",
                    "quality gate",
                    "quality gates",
                    "audit",
                    "inspect",
                    "inspector",
                    "transform",
                    "transformation",
                    "translate",
                    "self-healing",
                    "remediation",
                    "quadrant",
                )
            )
        )
    )

    matching_refs = []
    refs_dir = os.path.join(skill_path, "references")
    if os.path.exists(refs_dir):
      for ref_file in sorted(os.listdir(refs_dir)):
        if ref_file.endswith(".md"):
          ref_token = ref_file[:-3].lower()
          ref_tokens = set(re.findall(r"\w+", ref_token))
          if bool(query_tokens & ref_tokens) or any(
              token in query_lower
              for token in ref_tokens
              if len(token) > 3
          ):
            matching_refs.append(ref_file)

    if should_load or matching_refs:
      inst = load_skill_instructions(skill_name)
      formatted_name = skill_name.replace("_", " ").title()
      section_content = f"### {formatted_name} Guidelines:\n{inst}" if inst else ""

      for ref_file in matching_refs:
        ref_content = load_skill_reference(skill_name, ref_file)
        if ref_content:
          ref_title = ref_file[:-3].replace("_", " ").title()
          section_content += (
              f"\n\n#### Reference ({ref_title}):\n{ref_content}"
          )

      if section_content:
        loaded_sections.append(section_content)

  return "\n\n".join(loaded_sections)


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
    # Enforce October 2026 Gemini Brand Unification (Enterprise-Brand-Unification) across all skill references
    content = re.sub(
        r"\bGemini\s+Enterprise\s+(?:Agent\s+Platform|platform)\b",
        "Gemini platform",
        content,
        flags=re.IGNORECASE,
    )
    content = re.sub(
        r"\bGemini\s+Enterprise\s+app(?:lication)?\b",
        "Gemini",
        content,
        flags=re.IGNORECASE,
    )
    return content.strip()
  except Exception as e:
    print(f"[SkillLoader] Error reading reference {reference_name}: {e}")
    return ""


@functools.lru_cache(maxsize=64)
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
    result = (response.text or "").strip().replace('"', '').replace("'", "")
    if result in available_categories:
      return result
  except Exception as e:
    print(f"[SkillLoader] Error during industry category detection: {e}")
  return "None"


# Authoritative Registry of Industry Vertical Reference Skills with Domain Clusters & Scopes
INDUSTRY_VERTICAL_REGISTRY = {
    # Media & Entertainment
    "media_streaming.md": {
        "cluster": "Media & Entertainment",
        "title": "Media - Direct-to-Consumer & Streaming",
        "scope": [
            "streaming",
            "svod",
            "avod",
            "ott",
            "vod",
            "subscriber",
            "direct-to-consumer",
            "dtc",
            "disney",
            "netflix",
            "hulu",
            "paramount",
            "max",
            "peacock",
            "video streaming",
            "content delivery",
            "video transcoding",
            "dynamic ad insertion",
            "ssai",
            "audience engagement",
        ],
    },
    "media_entertainment.md": {
        "cluster": "Media & Entertainment",
        "title": "Media - Entertainment & Studios",
        "scope": [
            "entertainment",
            "studio",
            "vfx",
            "animation",
            "film",
            "cinema",
            "box office",
            "creative production",
            "virtual production",
            "post-production",
            "rendering pipeline",
            "game engine",
            "intellectual property",
        ],
    },
    "media_broadcasting.md": {
        "cluster": "Media & Entertainment",
        "title": "Media - Broadcasting, News & Sports",
        "scope": [
            "broadcasting",
            "broadcast",
            "linear television",
            "cable",
            "radio",
            "sports broadcast",
            "live playout",
            "newsroom",
            "automated clipping",
            "sports telemetry",
            "live feed",
        ],
    },
    "games.md": {
        "cluster": "Media & Entertainment",
        "title": "Gaming & Interactive Entertainment",
        "scope": [
            "gaming",
            "game",
            "games",
            "gameplay",
            "game studio",
            "multiplayer",
            "esports",
            "in-game economy",
            "live ops",
            "player telemetry",
        ],
    },
    # Financial Services & Insurance
    "fsi_banking.md": {
        "cluster": "Financial Services & Insurance",
        "title": "Financial Services - Banking",
        "scope": [
            "bank",
            "banking",
            "retail banking",
            "commercial banking",
            "lending",
            "credit",
            "mortgage",
            "wealth management",
            "fintech",
            "payments",
            "core banking",
            "kyc",
            "aml",
            "fraud detection",
        ],
    },
    "fsi_capital_markets.md": {
        "cluster": "Financial Services & Insurance",
        "title": "Financial Services - Capital Markets",
        "scope": [
            "capital markets",
            "investment banking",
            "trading",
            "stock exchange",
            "asset management",
            "hedge fund",
            "brokerage",
            "quantitative trading",
            "market data",
            "risk modeling",
            "clearing",
        ],
    },
    "fsi_insurance.md": {
        "cluster": "Financial Services & Insurance",
        "title": "Financial Services - Insurance",
        "scope": [
            "insurance",
            "underwriting",
            "claims",
            "actuarial",
            "policyholder",
            "property and casualty",
            "p&c",
            "life insurance",
            "health insurance",
            "reinsurance",
        ],
    },
    # Healthcare & Life Sciences
    "healthcare.md": {
        "cluster": "Healthcare & Life Sciences",
        "title": "Healthcare & Providers",
        "scope": [
            "healthcare",
            "health",
            "hospital",
            "health system",
            "clinical",
            "patient care",
            "ehr",
            "emr",
            "medical imaging",
            "hipaa",
            "telehealth",
            "provider",
        ],
    },
    "life_sciences.md": {
        "cluster": "Healthcare & Life Sciences",
        "title": "Life Sciences & Pharmaceuticals",
        "scope": [
            "life sciences",
            "pharma",
            "pharmaceutical",
            "biotech",
            "genomics",
            "drug discovery",
            "clinical trials",
            "fda",
            "medical device",
            "molecular",
        ],
    },
    # Retail & Consumer Packaged Goods
    "retail_consumer.md": {
        "cluster": "Retail & Consumer",
        "title": "Retail - Omnichannel & Consumer Goods",
        "scope": [
            "retail",
            "omnichannel",
            "department store",
            "merchandising",
            "e-commerce",
            "bopis",
            "point of sale",
            "pos",
            "shopper",
            "cart abandonment",
            "store operations",
        ],
    },
    "retail_grocery.md": {
        "cluster": "Retail & Consumer",
        "title": "Retail - Grocery & Supermarkets",
        "scope": [
            "grocery",
            "supermarket",
            "food retail",
            "perishables",
            "dark store",
            "cold chain delivery",
            "fresh food shrinkage",
            "basket size",
            "aisles",
            "supercenter",
        ],
    },
    "retail_fashion.md": {
        "cluster": "Retail & Consumer",
        "title": "Retail - Fashion & Apparel",
        "scope": [
            "fashion",
            "apparel",
            "luxury",
            "footwear",
            "clothing",
            "sneaker",
            "brand styling",
            "seasonal collection",
            "lookbook",
            "d2c fashion",
        ],
    },
    "cpg.md": {
        "cluster": "Retail & Consumer",
        "title": "Consumer Packaged Goods (CPG)",
        "scope": [
            "cpg",
            "fmcg",
            "consumer packaged goods",
            "brand manufacturer",
            "trade promotion",
            "packaged goods",
            "d2c brand",
        ],
    },
    # Manufacturing, Automotive & Supply Chain
    "manufacturing.md": {
        "cluster": "Manufacturing & Industrial",
        "title": "Manufacturing & Industrial",
        "scope": [
            "manufacturing",
            "factory",
            "plant",
            "industrial",
            "discrete manufacturing",
            "process manufacturing",
            "oem",
            "digital twin",
            "shop floor",
            "iiot",
            "smart factory",
        ],
    },
    "automotive.md": {
        "cluster": "Manufacturing & Industrial",
        "title": "Automotive & Connected Mobility",
        "scope": [
            "automotive",
            "car",
            "vehicle",
            "connected vehicle",
            "telematics",
            "ev",
            "electric vehicle",
            "oem",
            "autonomous driving",
            "dealership",
            "fleet mobility",
        ],
    },
    "supply_chain.md": {
        "cluster": "Supply Chain & Logistics",
        "title": "Supply Chain Management",
        "scope": [
            "supply chain",
            "procurement",
            "inventory management",
            "warehouse management",
            "wms",
            "demand forecasting",
            "replenishment",
            "supplier collaboration",
        ],
    },
    "logistics.md": {
        "cluster": "Supply Chain & Logistics",
        "title": "Logistics & Fleet Operations",
        "scope": [
            "logistics",
            "freight",
            "fleet",
            "warehouse",
            "delivery",
            "shipping",
            "3pl",
            "route optimization",
            "last-mile delivery",
            "intermodal",
        ],
    },
    # Energy, Utilities & Sustainability
    "power_energy.md": {
        "cluster": "Energy & Utilities",
        "title": "Power, Utilities & Energy",
        "scope": [
            "energy",
            "power",
            "utility",
            "utilities",
            "grid",
            "oil",
            "gas",
            "renewable energy",
            "smart grid",
            "smart meter",
            "clean energy",
            "transmission",
        ],
    },
    "sustainability.md": {
        "cluster": "Sustainability & ESG",
        "title": "Corporate Sustainability & ESG",
        "scope": [
            "sustainability",
            "carbon footprint",
            "esg",
            "emissions",
            "net zero",
            "decarbonization",
            "scope 1 2 3",
            "circular economy",
        ],
    },
    # Telecommunications
    "telecommunications.md": {
        "cluster": "Telecommunications",
        "title": "Telecommunications",
        "scope": [
            "telecom",
            "telecommunications",
            "telco",
            "5g",
            "network operator",
            "ran",
            "open ran",
            "carrier",
            "broadband",
            "bss oss",
            "telco edge",
        ],
    },
    # Travel & Hospitality
    "travel_hospitality.md": {
        "cluster": "Travel & Hospitality",
        "title": "Travel & Hospitality",
        "scope": [
            "travel",
            "hospitality",
            "airline",
            "hotel",
            "resort",
            "booking engine",
            "flight operations",
            "guest experience",
            "theme park",
            "lodging",
        ],
    },
    # Public Sector
    "international_public_sector.md": {
        "cluster": "Public Sector",
        "title": "Public Sector & Government",
        "scope": [
            "public sector",
            "government",
            "ministry",
            "agency",
            "defense",
            "citizen services",
            "sovereign cloud",
            "education",
            "public health agency",
        ],
    },
    # AI NeoCloud Infrastructure
    "ai_cloud_infrastructure.md": {
        "cluster": "AI & Cloud Infrastructure",
        "title": "AI & Cloud Infrastructure (NeoCloud / Supercomputing)",
        "scope": [
            "neocloud",
            "gpu cluster",
            "slurm",
            "token factory",
            "ai hypercomputer",
            "ai infrastructure",
            "together ai",
            "coreweave",
            "nebius",
            "crusoe",
            "lambda labs",
            "inference cluster",
        ],
    },
    # Marketing & AdTech
    "marketing.md": {
        "cluster": "Marketing & AdTech",
        "title": "Marketing & AdTech",
        "scope": [
            "marketing",
            "for marketing",
            "marketing pitch",
            "martech",
            "adtech",
            "cmo",
            "advertising",
            "advertising campaign",
            "marketing technology",
            "customer data platform",
            "cdp",
            "audience segmentation",
            "brand marketing",
            "digital marketing",
        ],
    },
    # Software & Technology
    "technology_software.md": {
        "cluster": "Technology",
        "title": "Software & Technology",
        "scope": [
            "technology",
            "software",
            "saas",
            "isv",
            "developer tools",
            "devtools",
            "coding agent",
            "ide",
            "web app",
            "cloud native",
            "b2b software",
            "application development",
            "generative ai software",
            "semiconductor",
            "semiconductors",
            "silicon",
            "foundry",
            "hardware",
            "electronics",
            "high tech",
            "microelectronics",
            "eda",
        ],
    },
}


def get_domain_and_account_glossary_with_name(
    context: dict | None = None, criteria: str = ""
) -> tuple[str, str]:
  """Context-driven semantic resolver that loads authoritative domain lexicon, macro dynamics, and KPIs.

  Uses parent domain clusters and full contextual signals (sub-industry, customer profile, user request)
  to select the exact matching vertical reference without cross-industry collisions.
  """
  context = context or {}
  industry = str(context.get("industry") or "").strip()
  sub_industry = str(context.get("sub_industry") or "").strip()
  micro_industry = str(context.get("micro_industry") or "").strip()
  customer_name = str(context.get("customer_name") or "").strip()
  business_context = str(context.get("business_context") or context.get("user_request") or "").strip()
  criteria_str = str(criteria or "").strip()

  current_dir = os.path.dirname(os.path.abspath(__file__))
  refs_dir = os.path.join(current_dir, "skills", "industry_verticals", "references")
  if not os.path.exists(refs_dir):
    return "", ""

  combined_context = f"{industry} {sub_industry} {micro_industry} {customer_name} {business_context} {criteria_str}".lower()
  if not combined_context.strip():
    return "", ""

  # 1. Determine Allowed Parent Clusters based on context.industry
  ind_lower = industry.lower()
  allowed_clusters = set()

  if any(k in ind_lower for k in ("media", "entertainment", "broadcasting", "streaming")):
    allowed_clusters.add("Media & Entertainment")
    if any(k in combined_context for k in ("theme park", "parks", "resort")):
      allowed_clusters.add("Travel & Hospitality")
  elif any(k in ind_lower for k in ("financial", "bank", "fsi", "insurance", "capital market", "fintech", "wealth")):
    allowed_clusters.add("Financial Services & Insurance")
  elif any(k in ind_lower for k in ("healthcare", "health", "provider", "hospital", "life science", "pharma", "biotech")):
    allowed_clusters.add("Healthcare & Life Sciences")
  elif any(k in ind_lower for k in ("retail", "cpg", "consumer", "grocery", "fashion", "commerce", "supermarket")):
    allowed_clusters.add("Retail & Consumer")
  elif any(k in ind_lower for k in ("manufacturing", "automotive", "industrial", "mobility", "oem")):
    allowed_clusters.add("Manufacturing & Industrial")
    allowed_clusters.add("Supply Chain & Logistics")
  elif any(k in ind_lower for k in ("supply chain", "logistics", "freight", "fleet")):
    allowed_clusters.add("Supply Chain & Logistics")
  elif any(k in ind_lower for k in ("energy", "power", "utility", "utilities", "oil", "gas")):
    allowed_clusters.add("Energy & Utilities")
  elif any(k in ind_lower for k in ("telecom", "telecommunications", "telco", "5g", "network")):
    allowed_clusters.add("Telecommunications")
  elif any(k in ind_lower for k in ("travel", "hospitality", "airline", "hotel")):
    allowed_clusters.add("Travel & Hospitality")
  elif any(k in ind_lower for k in ("public sector", "government", "education")):
    allowed_clusters.add("Public Sector")
  elif any(k in ind_lower for k in ("infrastructure", "neocloud", "compute", "gpu", "token factory", "slurm")):
    allowed_clusters.add("AI & Cloud Infrastructure")

  # Add explicit horizontal skills only if explicitly requested in user context
  if any(k in combined_context for k in ("sustainability", "carbon footprint", "esg", "net zero", "decarbonization")):
    allowed_clusters.add("Sustainability & ESG")
  if any(k in combined_context for k in ("martech", "adtech", "cmo", "advertising campaign", "cdp")):
    allowed_clusters.add("Marketing & AdTech")

  # 2. Contextual Scoring of Candidate Reference Files within Allowed Clusters
  scored_refs = []
  for ref_file, meta in INDUSTRY_VERTICAL_REGISTRY.items():
    ref_path = os.path.join(refs_dir, ref_file)
    if not os.path.exists(ref_path):
      continue

    cluster = meta["cluster"]
    # If parent clusters are established, strictly enforce domain boundaries
    if allowed_clusters and cluster not in allowed_clusters:
      continue

    score = 0
    scopes = meta["scope"]
    # Match multi-word domain phrases against full contextual string
    for phrase in scopes:
      if phrase in combined_context:
        score += len(phrase.split()) * 2  # Multi-word phrase matches receive higher weight

    # Sub-industry exact alignment bonus
    sub_ind_lower = sub_industry.lower()
    if any(phrase in sub_ind_lower for phrase in scopes):
      score += 10

    if score > 0:
      scored_refs.append((score, ref_file))

  # Sort by contextual score descending
  scored_refs.sort(key=lambda x: x[0], reverse=True)
  matching_refs = [r[1] for r in scored_refs]

  # Fallback to primary vertical default if no specific sub-industry scored
  if not matching_refs and allowed_clusters:
    for ref_file, meta in INDUSTRY_VERTICAL_REGISTRY.items():
      if meta["cluster"] in allowed_clusters:
        matching_refs.append(ref_file)
        break

  if not matching_refs:
    return "", ""

  # Take top relevant vertical references (max 3) to prevent context bloat
  selected_refs = matching_refs[:3]

  loaded_sections = []
  titles = []
  for ref_file in selected_refs:
    ref_content = load_skill_reference("industry_verticals", ref_file)
    if ref_content:
      formatted_title = INDUSTRY_VERTICAL_REGISTRY.get(ref_file, {}).get("title") or ref_file[:-3].replace("_", " ").title()
      titles.append(f"{formatted_title} ({ref_file})")
      loaded_sections.append(f"### Industry Vertical ({formatted_title}):\n{ref_content}")

  if loaded_sections:
    doc = (
        "\nINDUSTRY VERTICALS SKILL GROUNDING (Authoritative Domain Lexicon & Guidelines):\n"
        + "\n\n".join(loaded_sections)
        + "\n\nMANDATE: Use authentic domain terminology and KPIs from the industry vertical reference above. Avoid generic software/IT placeholders.\n"
    )
    return doc, ", ".join(titles)
  return "", ""


def get_domain_and_account_glossary(
    context: dict | None = None, criteria: str = ""
) -> str:
  """Loads authoritative domain lexicon, macro dynamics, and KPIs directly from the industry_verticals skill."""
  doc, _ = get_domain_and_account_glossary_with_name(context, criteria)
  return doc


def get_persona_guidelines_with_name(
    context: dict | None = None, criteria: str = ""
) -> tuple[str, str]:
  """Dynamically queries and redirects to the executive_persona skill for persona-tailored guidelines.

  Returns a tuple of (persona_markdown, formatted_persona_titles).
  """
  context = context or {}
  audience_raw = context.get("audience")
  if isinstance(audience_raw, list):
    audience_str = " ".join([str(a) for a in audience_raw]).lower()
  else:
    audience_str = str(audience_raw or "").lower()

  persona_str = str(context.get("persona") or "").lower()
  biz_ctx_str = str(
      context.get("business_context") or context.get("user_request") or ""
  ).lower()
  criteria_str = f"{str(criteria or '').lower()} {biz_ctx_str}".strip()

  # Target explicit audience and persona context first, stripping parenthetical dropdown examples like "(CEO, CFO, Board)"
  target_audience_persona = re.sub(
      r"\([^)]*\)", " ", f"{audience_str} {persona_str}"
  ).strip()

  current_dir = os.path.dirname(os.path.abspath(__file__))
  refs_dir = os.path.join(current_dir, "skills", "executive_persona", "references")
  if not os.path.exists(refs_dir):
    return "", ""

  matching_refs = []

  # 1. Match explicit persona directives in business_context / criteria first (e.g. 'pitch for Intel CEO')
  if criteria_str:
    if re.search(r"\bceo\b", criteria_str) or "chief executive" in criteria_str:
      matching_refs.append("ceo.md")
    elif (
        re.search(r"\b(?:cto|cio)\b", criteria_str)
        or "chief technology officer" in criteria_str
    ):
      matching_refs.append("cto.md")
    elif (
        re.search(r"\bcfo\b", criteria_str)
        or "chief financial officer" in criteria_str
    ):
      matching_refs.append("cfo.md")
    elif (
        re.search(r"\bciso\b", criteria_str)
        or "chief information security officer" in criteria_str
    ):
      matching_refs.append("ciso.md")
    elif (
        re.search(r"\bcdo\b", criteria_str)
        or "chief data officer" in criteria_str
    ):
      matching_refs.append("cdo.md")
    elif (
        re.search(r"\bcmo\b", criteria_str)
        or "chief marketing officer" in criteria_str
    ):
      matching_refs.append("cmo.md")

  # 2. Match from explicit audience/persona fields (without parenthetical dropdown examples)
  if not matching_refs and target_audience_persona:
    target_tokens = set(re.findall(r"\w+", target_audience_persona))
    for ref_file in sorted(os.listdir(refs_dir)):
      if not ref_file.endswith(".md"):
        continue
      ref_name = ref_file[:-3].lower()
      ref_tokens = set(re.findall(r"\w+", ref_name))
      if bool(target_tokens & ref_tokens) or any(t in target_audience_persona for t in ref_tokens if len(t) > 2):
        matching_refs.append(ref_file)

    # Synonym matching for explicit audience/persona
    if not matching_refs:
      if any(
          k in target_audience_persona
          for k in (
              "chief executive",
              "president",
              "board",
              "executive",
              "c-suite",
              "ceo",
          )
      ):
        matching_refs.append("ceo.md")
      elif any(k in target_audience_persona for k in ("chief technology", "chief information", "cto", "cio", "vp engineering", "technical decision maker", "tdm", "chief architect")):
        matching_refs.append("cto.md")
      elif any(k in target_audience_persona for k in ("chief financial", "cfo", "head of finance", "procurement director", "commercial")):
        matching_refs.append("cfo.md")
      elif any(k in target_audience_persona for k in ("chief information security", "ciso", "cso", "head of security", "secops")):
        matching_refs.append("ciso.md")
      elif any(k in target_audience_persona for k in ("chief data", "cdo", "head of analytics", "chief analytics")):
        matching_refs.append("cdo.md")
      elif any(k in target_audience_persona for k in ("chief marketing", "cmo", "head of marketing", "brand officer")):
        matching_refs.append("cmo.md")
      elif any(k in target_audience_persona for k in ("vp engineering", "head of engineering")):
        matching_refs.append("vp_engineering.md")

  if not matching_refs:
    return "", ""

  # Load overarching executive persona skill instructions
  persona_skill_inst = load_skill_instructions("executive_persona") or ""

  loaded_sections = []
  titles = []
  for ref_file in matching_refs:
    ref_content = load_skill_reference("executive_persona", ref_file)
    if ref_content:
      formatted_title = ref_file[:-3].replace("_", " ").upper()
      titles.append(f"{formatted_title} ({ref_file})")
      loaded_sections.append(
          f"### Target Persona Playbook ({formatted_title}):\n{ref_content}"
      )

  if loaded_sections or persona_skill_inst:
    doc = (
        "\nEXECUTIVE PERSONA SKILL GUIDANCE (Audience Psychology, KPIs & Lens):\n"
        + f"{persona_skill_inst}\n\n"
        + "\n\n".join(loaded_sections)
        + "\n\nMANDATE: Frame all solution capabilities through the target buyer persona's strategic priorities, decision psychology, and outcome metrics above.\n"
    )
    return doc, ", ".join(titles) if titles else "Executive Persona"
  return "", ""


def get_persona_guidelines(
    context: dict | None = None, criteria: str = ""
) -> str:
  """Dynamically queries and redirects to the executive_persona skill for persona-tailored guidelines."""
  doc, _ = get_persona_guidelines_with_name(context, criteria)
  return doc


_USE_CASE_CACHE: dict[str, list[dict]] = {}


def get_all_use_case_databases() -> dict[str, list[dict]]:
  """Dynamically scans and loads all use case JSON databases across all vertical directories.

  Returns a dictionary mapping 'relative/path.json' to the parsed list of use case objects.
  """
  global _USE_CASE_CACHE
  if _USE_CASE_CACHE:
    return _USE_CASE_CACHE

  current_dir = os.path.dirname(os.path.abspath(__file__))
  refs_dir = os.path.join(current_dir, "skills", "use_case_context", "references")
  if not os.path.exists(refs_dir):
    return {}

  databases = {}
  for root, _, files in os.walk(refs_dir):
    for f in files:
      if f.endswith(".json"):
        full_path = os.path.join(root, f)
        rel_path = os.path.relpath(full_path, refs_dir)
        try:
          with open(full_path, "r") as json_f:
            data = json.load(json_f)
            if isinstance(data, list):
              databases[rel_path] = data
            elif isinstance(data, dict):
              databases[rel_path] = [data]
        except Exception as e:
          print(f"[SkillLoader] Error reading dynamic use case file {rel_path}: {e}")

  _USE_CASE_CACHE = databases
  return _USE_CASE_CACHE


def find_matching_use_case(
    query_text: str,
    content_text: str = "",
    context: dict | None = None,
) -> dict | None:
  """Dynamically matches query/slide text against all available use case databases.

  Args:
      query_text: Title or agenda item (e.g., 'Autonomous Shopping Agents').
      content_text: Optional slide body text or description.
      context: Optional account context containing 'industry', 'sub_industry', 'customer_name'.

  Returns:
      The highest-scoring matching use case dictionary, or None if score threshold is not met.
  """
  databases = get_all_use_case_databases()
  if not databases:
    return None

  combined_query = f"{query_text} {content_text}".lower()
  query_words = set(re.findall(r"\w+", combined_query))

  # Target vertical filter preference
  vertical_bias_tokens = set()
  if context and isinstance(context, dict):
    ind = (context.get("industry") or "").lower()
    sub_ind = (context.get("sub_industry") or "").lower()
    cust = (context.get("customer_name") or "").lower()
    vertical_bias_tokens = set(re.findall(r"\w+", f"{ind} {sub_ind} {cust}"))

  best_match = None
  best_score = 0

  for db_name, use_cases in databases.items():
    # If the database directory matches the target vertical context, boost score
    db_tokens = set(re.findall(r"\w+", db_name.lower()))
    vertical_affinity = 3 if bool(vertical_bias_tokens & db_tokens) else 0

    for uc in use_cases:
      if not isinstance(uc, dict):
        continue

      uc_title = (uc.get("use_case_title") or "").lower()
      uc_desc = (uc.get("description_and_problem_statement") or "").lower()
      uc_narrative = (uc.get("value_narrative") or "").lower()
      uc_plays = (
          " ".join(uc.get("horizontal_plays", [])).lower()
          if isinstance(uc.get("horizontal_plays"), list)
          else ""
      )

      title_words = set(re.findall(r"\w+", uc_title))
      desc_words = set(re.findall(r"\w+", f"{uc_desc} {uc_narrative} {uc_plays}"))

      # Overlap with title is weighted 3x, description/narrative is weighted 1x
      title_overlap = len(query_words.intersection(title_words))
      desc_overlap = len(query_words.intersection(desc_words))

      score = (title_overlap * 3) + desc_overlap + vertical_affinity

      # Specific high-value technical keyword bonus
      if "agent" in query_words and ("agent" in title_words or "agentic" in title_words):
        score += 2
      if "supply" in query_words and "chain" in query_words and "supply" in title_words:
        score += 2
      if "churn" in query_words and ("churn" in title_words or "retention" in title_words):
        score += 2
      if "store" in query_words and ("store" in title_words or "connected" in title_words):
        score += 2

      if score > best_score:
        best_score = score
        best_match = uc

  return best_match if best_score >= 2 else None


_REGISTERED_SALES_PLAYS_CACHE: list[dict[str, Any]] | None = None


def load_registered_sales_plays() -> list[dict[str, Any]]:
  """Loads and parses all registered Google Cloud sales plays dynamically from sales_play_selection/SKILL.md."""
  global _REGISTERED_SALES_PLAYS_CACHE
  if _REGISTERED_SALES_PLAYS_CACHE is not None:
    return _REGISTERED_SALES_PLAYS_CACHE

  instructions = load_skill_instructions("sales_play_selection")
  if not instructions:
    return []

  plays = []
  current_category = "General"
  lines = instructions.splitlines()

  for line in lines:
    line_strip = line.strip()
    if line_strip.startswith("### "):
      current_category = line_strip[4:].strip()
      continue

    m = re.match(
        r"^-\s+(?:\[\*\*(.+?)\*\*\]\(.*?\)|(?:\*\*(.+?)\*\*))(?:\s*\[(.+?)\])?",
        line_strip,
    )
    if m:
      name = (m.group(1) or m.group(2) or "").strip()
      tier = (m.group(3) or "").strip()
      if not name or name in (
          "Primary",
          "Growth",
          "Emerging",
          "Do this",
          "Not that",
          "Watch out for",
          "Clarification",
          "AI Plays",
      ):
        continue

      aliases = set()
      paren_match = re.search(r"\((.+?)\)", name)
      if paren_match:
        aliases.add(paren_match.group(1).lower())

      if ":" in name:
        after_colon = name.split(":", 1)[1].strip().lower()
        aliases.add(after_colon)
        if "vmware" in after_colon:
          aliases.add("gcve")
          aliases.add("vmware engine")
        elif "sap" in after_colon:
          aliases.add("sap on google")
        elif "oracle" in after_colon:
          aliases.add("oracle on google")

      if "spectrum symphony" in name.lower() or "hpc" in name.lower():
        aliases.add("spectrum symphony")
        aliases.add("ibm spectrum symphony")
      if "genmedia" in name.lower() or "generative media" in name.lower():
        aliases.add("genmedia")
        aliases.add("generative media")
        aliases.add("veo")
        aliases.add("omni") 
        aliases.add("gen media")
      if "agentic workplace" in name.lower() or "workplace transformation" in name.lower():
        if "google workspace" in name.lower() or "workspace" in name.lower():
          aliases.add("google workspace")
          aliases.add("workspace")
          aliases.add("workspace ai")
          aliases.add("gws")
        elif "gemini enterprise" in name.lower():
          aliases.add("gemini enterprise")
          aliases.add("enterprise ai assistant")
        else:
          aliases.add("agentic workplace")
          aliases.add("agentic workplace transformation")
          aliases.add("workplace transformation")
          aliases.add("gemini enterprise")
          aliases.add("awt")
          aliases.add("gemini business")
          aliases.add("enterprise ai assistant")
      if "scale ai" in name.lower():
        aliases.add("scale ai")
        aliases.add("scale ai apps")
        aliases.add("agent platform")
        aliases.add("vertex ai")
        aliases.add("agent studio")
        aliases.add("agent engine")
      if "customer service" in name.lower():
        aliases.add(
            "gemini enterprise for customer experience - customer service"
        )
        aliases.add("customer service")
        aliases.add("contact center")
        aliases.add("ces")
      elif "customer experience" in name.lower():
        aliases.add("gemini enterprise for customer experience")
        aliases.add("customer experience")
        aliases.add("cx")
      if "agentic data" in name.lower():
        aliases.add("agentic data cloud")
        aliases.add("agentic data")
        aliases.add("bigquery")
      elif "data cloud" in name.lower():
        aliases.add("data cloud")
        aliases.add("migrate, modernize, and build with data cloud")

      name_lower = name.lower()
      clean_name = re.sub(r"[\(\):\-]", " ", name_lower)
      tokens = [
          t
          for t in clean_name.split()
          if len(t) > 2
          and t
          not in (
              "the",
              "and",
              "for",
              "with",
              "your",
              "our",
              "lead",
              "choice",
              "platform",
              "enterprise",
          )
      ]

      plays.append({
          "name": name,
          "name_lower": name_lower,
          "practice_area": current_category,
          "tier": tier,
          "aliases": list(aliases),
          "tokens": tokens,
      })

  _REGISTERED_SALES_PLAYS_CACHE = plays
  return plays


_COMMA_CONTAINING_SALES_PLAYS: tuple[tuple[str, str], ...] = (
    (
        "migrate, modernize, and build with data cloud",
        "Migrate, Modernize, and Build with Data Cloud",
    ),
    (
        "migrate, modernize and build with data cloud",
        "Migrate, Modernize, and Build with Data Cloud",
    ),
    (
        "migrate, modernize and build",
        "Migrate, Modernize and Build",
    ),
    (
        "migrate, modernize, and build",
        "Migrate, Modernize and Build",
    ),
    (
        "your business, your models",
        "Your Business, Your Models",
    ),
)


def split_sales_plays_safely(raw_plays: Any) -> list[str]:
  """Splits sales play inputs into a deduplicated list while preserving comma-containing canonical play names.

  Handles:
  - Lists/tuples/sets of strings (which themselves may contain multiple plays)
  - Pipe ('|'), semicolon (';'), or comma (',') separated strings
  - Grouped Practice Area prefixes (e.g. 'AI — Scale AI Apps and Agents')
  - Canonical sales plays that contain commas ('Migrate, Modernize, and Build
  with Data Cloud',
    'Migrate, Modernize and Build', 'Your Business, Your Models')
  """
  if not raw_plays:
    return []

  if isinstance(raw_plays, (list, tuple, set)):
    combined: list[str] = []
    seen_low: set[str] = set()
    for elem in raw_plays:
      for sub in split_sales_plays_safely(elem):
        sub_low = sub.lower()
        if sub_low not in seen_low:
          seen_low.add(sub_low)
          combined.append(sub)
    return combined

  s = str(raw_plays).strip()
  if not s or s.lower() in (
      "none",
      "null",
      "undefined",
      "n/a",
      "➕ none / single sales play",
      "none / single sales play",
  ):
    return []

  # Strip grouped practice-area prefix on the whole string if present before protecting comma plays
  s = re.sub(
      r"(?:^|(?<=[|;,]))\s*(?:AI|Data|Security|Infrastructure|Agentic"
      r" Workplace(?:\s+Transformation)?)\s*[—–\-:]\s*(?=[A-Z])",
      "",
      s,
      flags=re.IGNORECASE,
  )

  # Protect comma-containing canonical sales play names before splitting on commas
  placeholders: dict[str, str] = {}
  protected = s
  for idx, (pat_low, canonical_name) in enumerate(
      _COMMA_CONTAINING_SALES_PLAYS
  ):
    ph = f"__PITCHGEN_COMMA_PLAY_{idx}__"
    pattern = re.compile(re.escape(pat_low), flags=re.IGNORECASE)
    if pattern.search(protected):
      placeholders[ph] = canonical_name
      protected = pattern.sub(ph, protected)

  # Also protect any dynamically registered sales play from SKILL.md whose name contains a comma
  for r_idx, reg_p in enumerate(load_registered_sales_plays()):
    reg_name = str(reg_p.get("name") or "").strip()
    if "," in reg_name:
      ph = f"__PITCHGEN_REG_COMMA_PLAY_{r_idx}__"
      pattern = re.compile(re.escape(reg_name), flags=re.IGNORECASE)
      if pattern.search(protected):
        placeholders[ph] = reg_name
        protected = pattern.sub(ph, protected)

  raw_parts = re.split(r"\s*(?:\||;|,)\s*", protected)
  result: list[str] = []
  seen_lower: set[str] = set()
  for part in raw_parts:
    restored = part.strip()
    if not restored:
      continue
    for ph, canon in placeholders.items():
      if ph in restored:
        restored = restored.replace(ph, canon)
    # Strip any Practice Area prefix on individual item
    restored = re.sub(
        r"^(?:AI|Data|Security|Infrastructure|Agentic"
        r" Workplace(?:\s+Transformation)?)\s*[—–\-:]\s*",
        "",
        restored,
        flags=re.IGNORECASE,
    ).strip()
    if not restored or restored.lower() in (
        "none",
        "null",
        "undefined",
        "n/a",
        "➕ none / single sales play",
        "none / single sales play",
    ):
      continue
    r_low = restored.lower()
    if r_low not in seen_lower:
      seen_lower.add(r_low)
      result.append(restored)
  return result


def is_workspace_explicitly_requested(active_context: dict[str, Any] | None) -> bool:
  """Determines if the user explicitly requested Google Workspace content or selected a Workspace sales play."""
  if not active_context:
    return False

  # 1. Check prompt text and free-form context for explicit Workspace keywords
  user_req = str(active_context.get("user_request") or "").lower()
  biz_ctx = str(active_context.get("business_context") or "").lower()
  sol_ctx = str(active_context.get("solution") or "").lower()
  comb_prompt = f"{user_req} {biz_ctx} {sol_ctx}"
  workspace_keywords = [
      "workspace",
      "google workspace",
      "gws",
      "gmail",
      "google docs",
      "google sheets",
      "google slides",
      "google meet",
      "workspace ai",
  ]
  if any(
      re.search(r"\b" + re.escape(kw) + r"\b", comb_prompt)
      for kw in workspace_keywords
  ):
    return True

  # 2. Check explicit user-selected sales play dropdown fields (exclude LLM-inferred 'sales_plays'/'required_sales_plays'
  # so auto-detected plays cannot circularly self-authorize Google Workspace when the user never asked for it)
  req_plays_sources = [
      active_context.get("salesPlay"),
      active_context.get("sales_play"),
      active_context.get("secondary_sales_play"),
      active_context.get("additional_sales_plays"),
  ]
  req_plays = [p.lower() for p in split_sales_plays_safely(req_plays_sources)]

  for p in req_plays:
    if "workspace" in p or "gws" in p:
      return True

  return False


def resolve_required_sales_plays(context: dict[str, Any] | None) -> list[str]:
  """Analyzes user prompt text and dropdown fields to identify all required Sales Plays.

  Guarantees that when multiple sales plays are referenced (either via explicit
  dropdown selections or described in prompt text/business context), every
  respective sales play is identified so its platinum foundation deck can be
  reviewed and anchored.
  """
  if not context:
    return []

  registered_plays = load_registered_sales_plays()
  detected_play_names: list[str] = []

  # 1. Inspect explicit dropdown / parameter fields (including secondary / additional sales plays)
  dropdown_sources = [
      context.get("salesPlay"),
      context.get("sales_play"),
      context.get("secondary_sales_play"),
      context.get("additional_sales_plays"),
      context.get("sales_plays"),
  ]
  dropdown_items: list[str] = split_sales_plays_safely(dropdown_sources)
  workspace_requested = is_workspace_explicitly_requested(context)

  for item in dropdown_items:
    item_low = item.lower()
    if "workspace" in item_low and not workspace_requested:
      continue
    matched = False
    # 1a. Exact name or exact alias match first so specific sub-plays
    # are matched accurately before substring checks
    for p in registered_plays:
      if item_low == p["name_lower"] or item_low in p["aliases"]:
        if p["name"] not in detected_play_names:
          detected_play_names.append(p["name"])
        matched = True
        break
    if not matched:
      # Sort by closest name length so 'Agentic Workplace Transformation' matches
      # 'Lead the Agentic Workplace Transformation' before '... - Gemini Enterprise'
      for p in sorted(
          registered_plays,
          key=lambda x: abs(len(x["name_lower"]) - len(item_low)),
      ):
        p_name_low = p["name_lower"]
        if "workspace" in p_name_low and not workspace_requested:
          continue
        if (
            item_low in p_name_low
            or p_name_low in item_low
            or any(
                alias == item_low or alias in item_low for alias in p["aliases"]
            )
        ):
          if p["name"] not in detected_play_names:
            detected_play_names.append(p["name"])
          matched = True
          break
    if not matched and item not in detected_play_names:
      detected_play_names.append(item)

  # 2. Inspect prompt text & free-form business context
  user_req_text = str(context.get("user_request") or "").lower()
  biz_ctx_text = str(context.get("business_context") or "").lower()
  prompt_text = f"{user_req_text} {biz_ctx_text}".strip()
  has_explicit_dropdown = len(detected_play_names) > 0

  for p in registered_plays:
    p_name = p["name"]
    p_name_low = p["name_lower"]
    if p_name in detected_play_names:
      continue

    # Workspace sales play must ONLY be detected if workspace is explicitly requested
    if "workspace" in p_name_low and not workspace_requested:
      continue

    # If base Agentic Workplace Transformation is already in detected_play_names,
    # do not duplicate with Gemini Enterprise or Workspace sub-tracks
    if "agentic workplace" in p_name_low:
      if any("agentic workplace" in d.lower() for d in detected_play_names):
        continue

    # Direct match on name or registered aliases
    # When explicit dropdown plays are selected, do not let incidental background
    # footprint mentions (e.g. "runs SAP S/4HANA and BigQuery") in business_context
    # inject unrequested sales plays via short product aliases.
    alias_search_text = user_req_text if has_explicit_dropdown else prompt_text
    is_prompt_match = False
    if re.search(r"\b" + re.escape(p_name_low) + r"\b", prompt_text):
      is_prompt_match = True
    elif alias_search_text and any(
        re.search(r"\b" + re.escape(alias) + r"\b", alias_search_text)
        for alias in p["aliases"]
    ):
      is_prompt_match = True

    if is_prompt_match and p_name not in detected_play_names:
      detected_play_names.append(p_name)

  return detected_play_names


def is_orthogonal_sales_play(
    slide_or_deck_title: str = "",
    slide_metadata: dict[str, Any] | None = None,
    active_context: dict[str, Any] | None = None,
) -> str | None:
  """Determines if a candidate slide or deck belongs to an unrequested, orthogonal sales play.

  Returns the name of the conflicting unrequested sales play if orthogonal, or
  None if valid.
  """
  if not active_context:
    return None

  slide_metadata = slide_metadata or {}
  d_title = (
      slide_or_deck_title
      or slide_metadata.get("deck_title")
      or slide_metadata.get("title")
      or slide_metadata.get("original_title")
      or ""
  ).lower()
  all_titles_low = " ".join(
      str(x or "").lower()
      for x in (
          slide_or_deck_title,
          slide_metadata.get("deck_title"),
          slide_metadata.get("source_deck_title"),
          slide_metadata.get("title"),
          slide_metadata.get("original_title"),
      )
      if x
  )

  # 1. Why Google Cloud / Industry foundation decks are never orthogonal sales plays
  if any(kw in d_title for kw in ["why google", "why gcp", "ebc_pitch", "why google cloud"]):
    return None

  # 2. Approved active anchor decks are inherently protected
  anchor_ids = active_context.get("anchor_deck_ids", [])
  s_deck_id = slide_metadata.get("deck_id") or slide_metadata.get("deckId")
  if s_deck_id and s_deck_id in anchor_ids:
    return None

  # 3. Workspace-only deck/slide strict isolation:
  # Workspace-only decks should ONLY be chosen when explicitly asking for Workspace content
  # or choosing the Workspace sales play. Otherwise, agentic workplace transformation must rely
  # on the base Agentic Workplace Transformation / Gemini Enterprise sales play deck.
  sp_str_low = str(slide_metadata.get("sales_play") or "").lower()
  is_workspace_asset = (
      any(
          kw in all_titles_low
          for kw in ["workspace", "google workspace", "workspace ai", "gws"]
      )
      and "gemini enterprise" not in all_titles_low
  ) or (
      any(kw in sp_str_low for kw in ["workspace", "google workspace", "gws"])
      and not any(
          kw in sp_str_low
          for kw in [
              "gemini enterprise",
              "ai cloud",
              "why google",
          ]
      )
  )
  if is_workspace_asset and not is_workspace_explicitly_requested(active_context):
    return "Google Workspace"

  registered_plays = load_registered_sales_plays()
  if not registered_plays:
    return None

  req_plays_sources = [
      active_context.get("salesPlay"),
      active_context.get("sales_play"),
      active_context.get("secondary_sales_play"),
      active_context.get("additional_sales_plays"),
      active_context.get("sales_plays"),
      active_context.get("required_sales_plays"),
  ]
  req_plays = [p.lower() for p in split_sales_plays_safely(req_plays_sources)]

  user_req = str(active_context.get("user_request") or "").lower()
  biz_ctx = str(active_context.get("business_context") or "").lower()
  sol_ctx = str(active_context.get("solution") or "").lower()
  comb_context = f"{' '.join(req_plays)} {user_req} {biz_ctx} {sol_ctx}"

  slide_metadata = slide_metadata or {}
  d_title = (
      slide_or_deck_title
      or slide_metadata.get("deck_title")
      or slide_metadata.get("title")
      or slide_metadata.get("original_title")
      or ""
  ).lower()
  slide_sp = str(
      slide_metadata.get("sales_play") or slide_metadata.get("salesPlay") or ""
  ).lower()
  comb_candidate = f"{d_title} {slide_sp}"

  for play in registered_plays:
    play_name_low = play["name_lower"]
    is_candidate_match = False

    if slide_sp and (play_name_low in slide_sp or slide_sp in play_name_low):
      is_candidate_match = True
    elif any(alias in comb_candidate for alias in play["aliases"]):
      is_candidate_match = True
    elif play_name_low in d_title:
      is_candidate_match = True
    elif len(play["tokens"]) >= 2 and all(
        t in comb_candidate for t in play["tokens"]
    ):
      is_candidate_match = True

    if is_candidate_match:
      is_requested = (
          any(play_name_low in req or req in play_name_low for req in req_plays)
          or any(alias in comb_context for alias in play["aliases"])
          or (
              len(play["tokens"]) >= 2
              and all(t in comb_context for t in play["tokens"])
          )
      )
      if not is_requested:
        return play["name"]

  return None


def is_orthogonal_industry_vertical(
    slide_or_deck_title: str,
    slide_metadata: dict[str, Any] | None,
    active_context: dict[str, Any] | None,
) -> str | None:
  """Determines if a candidate slide or deck belongs to an incompatible industry vertical cluster.

  Returns the conflicting cluster name if incompatible, or None if compatible.
  """
  if not active_context:
    return None

  active_ind = str(
      active_context.get("closest_industry")
      or active_context.get("industry")
      or ""
  ).strip()
  if not active_ind or active_ind.lower() in (
      "none",
      "n/a",
      "cross-industry",
      "generic",
      "agnostic",
  ):
    return None

  target_cluster = active_ind
  for _, meta in INDUSTRY_VERTICAL_REGISTRY.items():
    meta_cluster = str(meta.get("cluster") or "")
    if re.search(
        r"\b" + re.escape(active_ind.lower()) + r"\b", meta_cluster.lower()
    ):
      target_cluster = meta_cluster
      break
  else:
    for _, meta in INDUSTRY_VERTICAL_REGISTRY.items():
      meta_cluster = str(meta.get("cluster") or "")
      if active_ind.lower() in [s.lower() for s in meta.get("scope", [])]:
        target_cluster = meta_cluster
        break

  target_cluster_str = str(target_cluster or "")

  slide_metadata = slide_metadata or {}
  d_title = (
      slide_or_deck_title
      or slide_metadata.get("deck_title")
      or slide_metadata.get("title")
      or slide_metadata.get("original_title")
      or ""
  ).lower()

  slide_ind_raw = slide_metadata.get("industry")
  slide_inds = (
      [str(x).lower().strip() for x in slide_ind_raw]
      if isinstance(slide_ind_raw, list)
      else ([str(slide_ind_raw).lower().strip()] if slide_ind_raw else [])
  )
  # In sales_play_reusables, horizontal cross-industry slides are tagged with an array of all 17 industries.
  # Never concatenate multi-industry arrays (len >= 3) into slide_ind_str, or else 'Games' / 'Automotive'
  # inside the 17-industry list will falsely trigger vertical disqualification on horizontal decks.
  if len(slide_inds) >= 3:
    slide_ind_str = d_title
  else:
    slide_ind_str = f"{d_title} {' '.join(slide_inds)}".strip()

  # Horizontal cross-industry sales plays are applicable to all customer verticals
  # unless the deck title itself is explicitly scoped to a specific vertical (e.g. 'Healthcare | ...', 'M&E | ...').
  horizontal_sales_plays = [
      "genmedia",
      "generative media",
      "gemini enterprise",
      "agentic workplace",
      "agentic workplace transformation",
      "awt ",
      "scale ai apps",
      "scale ai apps and agents",
      "customer experience",
      "agentic cx",
      "smart analytics",
      "data cloud",
      "infrastructure modernization",
      "cyber security",
      "security operations",
      "app modernization",
  ]

  if any(
      x in slide_ind_str
      for x in [
          "cross-industry",
          "cross industry",
          "general",
          "horizontal",
          "agnostic",
      ]
  ) or any(h in target_cluster_str.lower() for h in horizontal_sales_plays):
    return None

  slide_tokens = set(re.findall(r"\w+", slide_ind_str))
  candidate_cluster = None
  for _, meta in INDUSTRY_VERTICAL_REGISTRY.items():
    cluster = meta.get("cluster")
    for scope_word in meta.get("scope", []):
      if " " in scope_word or not scope_word.isalnum():
        if len(scope_word) >= 3 and re.search(
            rf"(?:^|[^a-z0-9]){re.escape(scope_word)}(?:$|[^a-z0-9])",
            slide_ind_str,
        ):
          candidate_cluster = str(cluster or "")
          break
      elif len(scope_word) >= 3 and scope_word in slide_tokens:
        candidate_cluster = str(cluster or "")
        break
    if candidate_cluster:
      break

  # Specific sub-vertical isolation: Gaming is an isolated entertainment sub-domain
  # Never leak gaming decks/slides into general technology, B2B software, or enterprise SaaS accounts
  is_gaming_candidate = any(
      gw in slide_tokens
      for gw in ("gaming", "games", "gameplay", "esports", "liveops")
  ) or any(
      gw in slide_ind_str
      for gw in ("for games", "game studio", "player telemetry", "in-game")
  )
  target_context_tokens = set(
      re.findall(
          r"\w+",
          f"{active_ind} {active_context.get('sub_industry', '')} {active_context.get('micro_industry', '')} {active_context.get('customer_name', '')} {active_context.get('business_context', '')} {active_context.get('user_request', '')}".lower(),
      )
  )
  has_gaming_intent = bool(
      {"gaming", "games", "game", "gameplay", "esports"} & target_context_tokens
  )
  if is_gaming_candidate and not has_gaming_intent:
    return "Gaming & Interactive Entertainment"

  # Specific sub-vertical isolation: Marketing / CMO / MarTech is an isolated functional/vertical domain
  # Never leak "Why Google Cloud for Marketing" or CMO-specific decks into non-marketing accounts
  is_marketing_candidate = any(
      mw in slide_tokens for mw in ("martech", "adtech", "cmo", "advertising")
  ) or any(
      mw in slide_ind_str
      for mw in (
          "for marketing",
          "marketing pitch",
          "marketing_whygooglecloud",
          "customer data platform",
      )
  )
  has_marketing_intent = bool(
      {"marketing", "martech", "adtech", "cmo", "advertising", "campaign"}
      & target_context_tokens
  )
  if is_marketing_candidate and not has_marketing_intent:
    return "Marketing & AdTech"

  if candidate_cluster:
    if candidate_cluster.lower() == target_cluster_str.lower():
      return None
    if {candidate_cluster, target_cluster_str}.issubset({
        "Technology",
        "Technology & Software",
        "AI & Cloud Infrastructure",
    }):
      return None
    # Semiconductor, Silicon, Foundry, and EDA accounts straddle Technology and Manufacturing & Industrial
    is_semiconductor_or_hardware_account = bool(
        {
            "semiconductor",
            "semiconductors",
            "silicon",
            "foundry",
            "fab",
            "wafer",
            "eda",
            "microelectronics",
            "chip",
        }
        & target_context_tokens
    )
    if is_semiconductor_or_hardware_account and candidate_cluster in (
        "Manufacturing & Industrial",
        "Supply Chain & Logistics",
    ):
      return None
    return candidate_cluster

  return None
