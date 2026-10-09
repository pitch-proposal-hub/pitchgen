"""Stratified Combinatorial E2E Test Matrix for PitchGen Deck Generation.

Defines 3 tiers of end-to-end presentation test specifications:
- tier1_smoke (9 decks): 3x3 orthogonal Latin Square across all 3 Deck
Strategies
  x all 3 Deck Lengths, spanning 9 Industries, 9 Sales Plays, all 5 Sales Stages
  (S0-S4), and both Executive & Technical personas.
- tier2_pairwise (36 decks): 100% 1-way coverage of all 19 Industries, all 5
  Solution Areas, all 3 Deck Strategies, all 3 Deck Lengths, all 5 Sales Stages,
  and 100% 2-way pairwise coverage of (Strategy x Length), (Strategy x Stage
  Track),
  and (Solution Area x Strategy).
- tier3_marathon (108 decks): Full sweep across all 27 canonical Sales Plays,
  multi-play combinations, international domains (.co.jp, .de, .co.uk, .com.br),
  and post-deck actions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

DECK_STRATEGIES: tuple[str, ...] = (
    "smart_hybrid",
    "cloudhub",
    "bespoke_custom",
)

DECK_LENGTHS: tuple[str, ...] = (
    "Brief (4-6 slides)",
    "Standard (8-12 slides)",
    "Comprehensive (15-20 slides)",
)

SALES_STAGES: tuple[str, ...] = ("S0", "S1", "S2", "S3", "S4")

SOLUTION_AREAS: tuple[str, ...] = (
    "AI & Machine Learning",
    "Data Analytics & Databases",
    "Security",
    "Infrastructure & Application Modernization",
    "Workspace & Collaboration",
)

INDUSTRIES: tuple[str, ...] = (
    "Retail & Consumer Goods",
    "Financial Services",
    "Healthcare & Life Sciences",
    "Manufacturing & Industrial",
    "Media & Entertainment",
    "Telecommunications",
    "Automotive & Mobility",
    "Gaming",
    "Energy & Utilities",
    "Public Sector & Government",
    "Education & EdTech",
    "Software & Internet",
    "Travel & Hospitality",
    "Logistics & Supply Chain",
    "Professional Services",
    "Agriculture & AgTech",
    "Real Estate & PropTech",
    "Aerospace & Defense",
    "Insurance",
)

SALES_PLAYS_BY_SOLUTION: dict[str, tuple[str, ...]] = {
    "AI & Machine Learning": (
        "Customer Experience & Conversational AI",
        "Employee Productivity & Knowledge Agents",
        "Creative Content & Marketing Studio",
        "Code & Software Engineering Acceleration",
        "AI Infrastructure & Model Training",
        "Back-Office Process Automation",
    ),
    "Data Analytics & Databases": (
        "Unified Data & AI Platform (BigQuery)",
        "Database Modernization & AlloyDB Migration",
        "Legacy EDW Offload (Teradata / Snowflake / Netezza)",
        "Real-Time Streaming & Event Intelligence",
        "Business Intelligence & Conversational Analytics (Looker)",
        "SAP Data Estate & Enterprise Data Sharing",
    ),
    "Security": (
        "AI-Driven SecOps & Threat Detection",
        "Mandate & Regulatory Compliance",
        "Cloud Workload & Posture Security",
        "Zero Trust & Secure Enterprise Browsing",
        "Proactive Cyber Defense & Mandiant Threat Intelligence",
        "Data Security & Sovereign Controls",
    ),
    "Infrastructure & Application Modernization": (
        "VMware Exit & Data Center Migration",
        "Cloud-Native Kubernetes & GKE Enterprise",
        "SAP on Google Cloud Transformation",
        "High-Performance Computing & Batch Workloads",
        "Mainframe Modernization",
        "Edge & Distributed Cloud Operations",
    ),
    "Workspace & Collaboration": (
        "AI-First Employee Collaboration (Gemini for Workspace)",
        "Frontline Worker Mobilization",
        "Legacy Office & Messaging Consolidation",
    ),
}

ALL_SALES_PLAYS: tuple[str, ...] = tuple(
    play for plays in SALES_PLAYS_BY_SOLUTION.values() for play in plays
)


@dataclass(frozen=True)
class DeckTestSpec:
  """Single end-to-end presentation test specification."""

  test_id: str
  tier: str
  customer_name: str
  customer_domain: str
  industry: str
  sub_industry: str
  solution: str
  sales_play: str
  sales_stage: str
  deck_strategy: str
  deck_length: str
  audience_persona: str
  business_context: str
  region: str = "NORTHAM"
  segment: str = "Enterprise"
  post_deck_action: str = ""

  @property
  def stage_track(self) -> str:
    """Returns 'early_s0_s1' for S0/S1 or 'technical_s2_s4' for S2-S4."""
    return (
        "early_s0_s1" if self.sales_stage in ("S0", "S1") else "technical_s2_s4"
    )

  def to_dict(self) -> dict[str, Any]:
    data = asdict(self)
    data["stage_track"] = self.stage_track
    return data


TIER1_SMOKE_SPECS: tuple[DeckTestSpec, ...] = (
    DeckTestSpec(
        test_id="T1-01",
        tier="tier1_smoke",
        customer_name="Uniqlo",
        customer_domain="uniqlo.com",
        industry="Retail & Consumer Goods",
        sub_industry="Apparel & Fast Fashion",
        solution="AI & Machine Learning",
        sales_play="Customer Experience & Conversational AI",
        sales_stage="S1",
        deck_strategy="smart_hybrid",
        deck_length="Standard (8-12 slides)",
        audience_persona="Executive",
        business_context=(
            "Uniqlo is unifying global e-commerce and in-store inventory"
            " discovery with multimodal conversational shopping agents and"
            " personalized styling experiences built with Gemini Enterprise on"
            " Google Cloud."
        ),
        region="JAPAC",
        segment="Select",
        post_deck_action="regenerate_slide",
    ),
    DeckTestSpec(
        test_id="T1-02",
        tier="tier1_smoke",
        customer_name="Stripe",
        customer_domain="stripe.com",
        industry="Financial Services",
        sub_industry="Payments & FinTech",
        solution="Data Analytics & Databases",
        sales_play="Database Modernization & AlloyDB Migration",
        sales_stage="S3",
        deck_strategy="smart_hybrid",
        deck_length="Brief (4-6 slides)",
        audience_persona="Technical",
        business_context=(
            "Stripe is modernizing high-throughput payment ledger databases"
            " onto AlloyDB and BigQuery for sub-millisecond transactional SLA"
            " and real-time fraud feature engineering."
        ),
        region="NORTHAM",
        segment="Select",
        post_deck_action="shorten_text",
    ),
    DeckTestSpec(
        test_id="T1-03",
        tier="tier1_smoke",
        customer_name="Pfizer",
        customer_domain="pfizer.com",
        industry="Healthcare & Life Sciences",
        sub_industry="Biopharmaceuticals",
        solution="Security",
        sales_play="AI-Driven SecOps & Threat Detection",
        sales_stage="S2",
        deck_strategy="smart_hybrid",
        deck_length="Comprehensive (15-20 slides)",
        audience_persona="Technical",
        business_context=(
            "Pfizer is consolidating global R&D security telemetry into Google"
            " Security Operations with Mandiant threat intelligence to protect"
            " clinical trial intellectual property and automate alert triage."
        ),
        region="NORTHAM",
        segment="Select",
        post_deck_action="expand_text",
    ),
    DeckTestSpec(
        test_id="T1-04",
        tier="tier1_smoke",
        customer_name="Siemens",
        customer_domain="siemens.com",
        industry="Manufacturing & Industrial",
        sub_industry="Industrial Automation",
        solution="Infrastructure & Application Modernization",
        sales_play="SAP on Google Cloud Transformation",
        sales_stage="S0",
        deck_strategy="cloudhub",
        deck_length="Brief (4-6 slides)",
        audience_persona="Executive",
        business_context=(
            "Siemens is evaluating a clean-core SAP S/4HANA transformation"
            " integrated with BigQuery and Gemini Enterprise to harmonize"
            " factory supply chain visibility across 120 global plants."
        ),
        region="EMEA",
        segment="Select",
    ),
    DeckTestSpec(
        test_id="T1-05",
        tier="tier1_smoke",
        customer_name="Spotify",
        customer_domain="spotify.com",
        industry="Media & Entertainment",
        sub_industry="Digital Audio & Streaming",
        solution="Data Analytics & Databases",
        sales_play="Unified Data & AI Platform (BigQuery)",
        sales_stage="S2",
        deck_strategy="cloudhub",
        deck_length="Standard (8-12 slides)",
        audience_persona="Technical",
        business_context=(
            "Spotify is scaling unified lakehouse analytics and multimodal"
            " podcast recommendations on BigQuery with autonomous data"
            " engineering workflows."
        ),
        region="EMEA",
        segment="Select",
    ),
    DeckTestSpec(
        test_id="T1-06",
        tier="tier1_smoke",
        customer_name="Vodafone",
        customer_domain="vodafone.com",
        industry="Telecommunications",
        sub_industry="Wireless & Fixed Telecom",
        solution="AI & Machine Learning",
        sales_play="Employee Productivity & Knowledge Agents",
        sales_stage="S4",
        deck_strategy="cloudhub",
        deck_length="Comprehensive (15-20 slides)",
        audience_persona="Executive",
        business_context=(
            "Vodafone is deploying Gemini Enterprise knowledge agents across"
            " 45,000 network operations and customer care engineers to cut"
            " mean-time-to-repair and unify commercial contract governance."
        ),
        region="EMEA",
        segment="Select",
    ),
    DeckTestSpec(
        test_id="T1-07",
        tier="tier1_smoke",
        customer_name="Rivian",
        customer_domain="rivian.com",
        industry="Automotive & Mobility",
        sub_industry="Electric Vehicles & Connected Fleet",
        solution="Workspace & Collaboration",
        sales_play="AI-First Employee Collaboration (Gemini for Workspace)",
        sales_stage="S1",
        deck_strategy="bespoke_custom",
        deck_length="Brief (4-6 slides)",
        audience_persona="Executive",
        business_context=(
            "Rivian is equipping vehicle engineering and retail showroom teams"
            " with Gemini for Google Workspace to accelerate design reviews and"
            " field service collaboration."
        ),
        region="NORTHAM",
        segment="Enterprise",
        post_deck_action="generate_visual",
    ),
    DeckTestSpec(
        test_id="T1-08",
        tier="tier1_smoke",
        customer_name="Nintendo",
        customer_domain="nintendo.com",
        industry="Gaming",
        sub_industry="Interactive Entertainment & Console Gaming",
        solution="Infrastructure & Application Modernization",
        sales_play="Cloud-Native Kubernetes & GKE Enterprise",
        sales_stage="S3",
        deck_strategy="bespoke_custom",
        deck_length="Standard (8-12 slides)",
        audience_persona="Technical",
        business_context=(
            "Nintendo is modernizing global multiplayer matchmaking and"
            " live-ops backends on GKE Enterprise and Cloud Spanner for"
            " zero-downtime title launches."
        ),
        region="JAPAC",
        segment="Select",
        post_deck_action="create_custom_slide",
    ),
    DeckTestSpec(
        test_id="T1-09",
        tier="tier1_smoke",
        customer_name="NextEra Energy",
        customer_domain="nexteraenergy.com",
        industry="Energy & Utilities",
        sub_industry="Renewable Power & Grid Operations",
        solution="Security",
        sales_play="Cloud Workload & Posture Security",
        sales_stage="S2",
        deck_strategy="bespoke_custom",
        deck_length="Comprehensive (15-20 slides)",
        audience_persona="Technical",
        business_context=(
            "NextEra Energy is securing distributed wind, solar, and grid"
            " telemetry workloads with Security Command Center Enterprise and"
            " sovereign zero-trust controls on Google Cloud."
        ),
        region="NORTHAM",
        segment="Select",
        post_deck_action="change_theme",
    ),
)


def _build_tier2_additional_specs() -> tuple[DeckTestSpec, ...]:
  """Builds 27 additional specs (T2-10..T2-36) to complete 36-deck pairwise suite."""
  additional_rows = [
      (
          "T2-10",
          "State of California",
          "ca.gov",
          "Public Sector & Government",
          "State & Local Government",
          "Security",
          "Mandate & Regulatory Compliance",
          "S1",
          "smart_hybrid",
          "Brief (4-6 slides)",
          "Executive",
          (
              "Modernizing constituent digital services with FedRAMP High"
              " compliance and automated cyber posture monitoring."
          ),
          "NORTHAM",
          "Public Sector",
      ),
      (
          "T2-11",
          "Coursera",
          "coursera.org",
          "Education & EdTech",
          "Online Learning Platforms",
          "AI & Machine Learning",
          "Creative Content & Marketing Studio",
          "S2",
          "bespoke_custom",
          "Standard (8-12 slides)",
          "Executive",
          (
              "Scaling multilingual course dubbing, adaptive tutoring agents,"
              " and interactive assessments built with Gemini Enterprise."
          ),
          "NORTHAM",
          "Enterprise",
      ),
      (
          "T2-12",
          "Atlassian",
          "atlassian.com",
          "Software & Internet",
          "Enterprise SaaS",
          "AI & Machine Learning",
          "Code & Software Engineering Acceleration",
          "S3",
          "cloudhub",
          "Brief (4-6 slides)",
          "Technical",
          (
              "Accelerating developer velocity and automated PR validation"
              " across distributed engineering teams on Google Cloud."
          ),
          "JAPAC",
          "Select",
      ),
      (
          "T2-13",
          "Marriott International",
          "marriott.com",
          "Travel & Hospitality",
          "Global Hotels & Resorts",
          "Data Analytics & Databases",
          "Legacy EDW Offload (Teradata / Snowflake / Netezza)",
          "S0",
          "smart_hybrid",
          "Comprehensive (15-20 slides)",
          "Executive",
          (
              "Unifying 180M Bonvoy loyalty profiles on BigQuery to enable"
              " dynamic room pricing and personalized travel concierges."
          ),
          "NORTHAM",
          "Select",
      ),
      (
          "T2-14",
          "Maersk",
          "maersk.com",
          "Logistics & Supply Chain",
          "Global Ocean & Inland Freight",
          "Infrastructure & Application Modernization",
          "VMware Exit & Data Center Migration",
          "S2",
          "cloudhub",
          "Brief (4-6 slides)",
          "Technical",
          (
              "Exiting legacy regional data centers and migrating"
              " mission-critical port scheduling systems to Google Cloud."
          ),
          "EMEA",
          "Select",
      ),
      (
          "T2-15",
          "Deloitte",
          "deloitte.com",
          "Professional Services",
          "Global Advisory & Tax",
          "Workspace & Collaboration",
          "Legacy Office & Messaging Consolidation",
          "S1",
          "smart_hybrid",
          "Standard (8-12 slides)",
          "Executive",
          (
              "Empowering global practice practitioners with secure"
              " collaborative workspaces and grounded audit research"
              " assistants."
          ),
          "NORTHAM",
          "Select",
      ),
      (
          "T2-16",
          "John Deere",
          "deere.com",
          "Agriculture & AgTech",
          "Precision Agriculture & Autonomous Equipment",
          "Infrastructure & Application Modernization",
          "Edge & Distributed Cloud Operations",
          "S4",
          "bespoke_custom",
          "Brief (4-6 slides)",
          "Technical",
          (
              "Running computer vision crop telemetry at the edge and"
              " synchronizing fleet analytics into BigQuery."
          ),
          "NORTHAM",
          "Select",
      ),
      (
          "T2-17",
          "CBRE",
          "cbre.com",
          "Real Estate & PropTech",
          "Commercial Real Estate Services",
          "Data Analytics & Databases",
          "Business Intelligence & Conversational Analytics (Looker)",
          "S1",
          "cloudhub",
          "Standard (8-12 slides)",
          "Executive",
          (
              "Delivering conversational portfolio valuation and building"
              " sustainability insights via Looker and BigQuery."
          ),
          "NORTHAM",
          "Enterprise",
      ),
      (
          "T2-18",
          "Airbus",
          "airbus.com",
          "Aerospace & Defense",
          "Commercial Aviation Manufacturing",
          "Infrastructure & Application Modernization",
          "High-Performance Computing & Batch Workloads",
          "S3",
          "smart_hybrid",
          "Standard (8-12 slides)",
          "Technical",
          (
              "Scaling aerodynamic digital twin simulations and avionics"
              " verification on Google Cloud HPC clusters."
          ),
          "EMEA",
          "Select",
      ),
      (
          "T2-19",
          "Allianz",
          "allianz.com",
          "Insurance",
          "Global Property & Casualty Insurance",
          "AI & Machine Learning",
          "Back-Office Process Automation",
          "S0",
          "bespoke_custom",
          "Comprehensive (15-20 slides)",
          "Executive",
          (
              "Automating multimodal claims adjudication and underwriting risk"
              " extraction with Gemini Enterprise."
          ),
          "EMEA",
          "Select",
      ),
      (
          "T2-20",
          "Target",
          "target.com",
          "Retail & Consumer Goods",
          "Omnichannel Mass Retail",
          "Workspace & Collaboration",
          "Frontline Worker Mobilization",
          "S2",
          "cloudhub",
          "Comprehensive (15-20 slides)",
          "Executive",
          (
              "Connecting 400,000 store associates with mobile Workspace tools"
              " and real-time inventory lookup agents."
          ),
          "NORTHAM",
          "Select",
      ),
      (
          "T2-21",
          "JPMorgan Chase",
          "jpmorganchase.com",
          "Financial Services",
          "Global Banking & Capital Markets",
          "Security",
          "Zero Trust & Secure Enterprise Browsing",
          "S1",
          "cloudhub",
          "Comprehensive (15-20 slides)",
          "Executive",
          (
              "Enforcing zero-trust enterprise browsing and sovereign"
              " cryptographic key governance across global trading desks."
          ),
          "NORTHAM",
          "Select",
      ),
      (
          "T2-22",
          "Moderna",
          "modernatx.com",
          "Healthcare & Life Sciences",
          "mRNA Therapeutics",
          "AI & Machine Learning",
          "AI Infrastructure & Model Training",
          "S3",
          "bespoke_custom",
          "Standard (8-12 slides)",
          "Technical",
          (
              "Training genomic sequence foundation models on Cloud TPU pods"
              " with automated MLOps governance."
          ),
          "NORTHAM",
          "Enterprise",
      ),
      (
          "T2-23",
          "Caterpillar",
          "caterpillar.com",
          "Manufacturing & Industrial",
          "Heavy Construction Equipment",
          "Data Analytics & Databases",
          "Real-Time Streaming & Event Intelligence",
          "S1",
          "bespoke_custom",
          "Standard (8-12 slides)",
          "Executive",
          (
              "Streaming IoT diagnostics from 1.5M connected machines into"
              " BigQuery for predictive maintenance alerts."
          ),
          "NORTHAM",
          "Select",
      ),
      (
          "T2-24",
          "Warner Bros. Discovery",
          "wbd.com",
          "Media & Entertainment",
          "Film, Television & Streaming",
          "Data Analytics & Databases",
          "SAP Data Estate & Enterprise Data Sharing",
          "S0",
          "cloudhub",
          "Standard (8-12 slides)",
          "Executive",
          (
              "Harmonizing global content licensing financials across SAP and"
              " BigQuery to optimize streaming ROI."
          ),
          "NORTHAM",
          "Select",
      ),
      (
          "T2-25",
          "T-Mobile",
          "t-mobile.com",
          "Telecommunications",
          "5G Wireless Carrier",
          "Security",
          "Proactive Cyber Defense & Mandiant Threat Intelligence",
          "S4",
          "smart_hybrid",
          "Brief (4-6 slides)",
          "Technical",
          (
              "Integrating Mandiant threat intelligence and continuous"
              " red-teaming across 5G core network infrastructure."
          ),
          "NORTHAM",
          "Select",
      ),
      (
          "T2-26",
          "BMW Group",
          "bmw.com",
          "Automotive & Mobility",
          "Luxury Automotive Manufacturing",
          "Infrastructure & Application Modernization",
          "Mainframe Modernization",
          "S2",
          "smart_hybrid",
          "Standard (8-12 slides)",
          "Technical",
          (
              "Refactoring legacy parts-ordering mainframe systems onto"
              " cloud-native microservices and AlloyDB."
          ),
          "EMEA",
          "Select",
      ),
      (
          "T2-27",
          "Electronic Arts",
          "ea.com",
          "Gaming",
          "Global Sports & Action Gaming",
          "Workspace & Collaboration",
          "AI-First Employee Collaboration (Gemini for Workspace)",
          "S3",
          "smart_hybrid",
          "Brief (4-6 slides)",
          "Technical",
          (
              "Connecting global game studios with Gemini for Workspace to"
              " streamline live-service production workflows."
          ),
          "NORTHAM",
          "Select",
      ),
      (
          "T2-28",
          "Shell",
          "shell.com",
          "Energy & Utilities",
          "Global Integrated Energy",
          "Security",
          "Data Security & Sovereign Controls",
          "S1",
          "smart_hybrid",
          "Standard (8-12 slides)",
          "Executive",
          (
              "Protecting subsurface seismic data and European trading"
              " operations with Sovereign Controls on Google Cloud."
          ),
          "EMEA",
          "Select",
      ),
      (
          "T2-29",
          "Mercado Libre",
          "mercadolibre.com",
          "Retail & Consumer Goods",
          "Latin America E-Commerce & FinTech",
          "AI & Machine Learning",
          "Customer Experience & Conversational AI",
          "S2",
          "cloudhub",
          "Brief (4-6 slides)",
          "Technical",
          (
              "Deploying Spanish and Portuguese conversational shopping"
              " assistants for 100M active buyers across Latin America."
          ),
          "LATAM",
          "Select",
      ),
      (
          "T2-30",
          "Deutsche Bank",
          "db.com",
          "Financial Services",
          "Corporate & Investment Banking",
          "Infrastructure & Application Modernization",
          "VMware Exit & Data Center Migration",
          "S1",
          "bespoke_custom",
          "Brief (4-6 slides)",
          "Executive",
          (
              "Accelerating regulatory-compliant data center exit and core"
              " banking modernization on Google Cloud."
          ),
          "EMEA",
          "Select",
      ),
      (
          "T2-31",
          "Mayo Clinic",
          "mayoclinic.org",
          "Healthcare & Life Sciences",
          "Academic Medical Center",
          "Workspace & Collaboration",
          "Frontline Worker Mobilization",
          "S0",
          "cloudhub",
          "Brief (4-6 slides)",
          "Executive",
          (
              "Reducing clinician administrative burden with secure mobile"
              " collaboration and clinical handoff synthesis."
          ),
          "NORTHAM",
          "Select",
      ),
      (
          "T2-32",
          "Toyota Motor",
          "toyota.co.jp",
          "Automotive & Mobility",
          "Global Automotive OEM",
          "Data Analytics & Databases",
          "Unified Data & AI Platform (BigQuery)",
          "S1",
          "smart_hybrid",
          "Comprehensive (15-20 slides)",
          "Executive",
          (
              "Unifying global connected vehicle telemetry and dealer supply"
              " chain forecasting on BigQuery."
          ),
          "JAPAC",
          "Select",
      ),
      (
          "T2-33",
          "Canva",
          "canva.com",
          "Software & Internet",
          "Visual Communication Platform",
          "Workspace & Collaboration",
          "Legacy Office & Messaging Consolidation",
          "S2",
          "bespoke_custom",
          "Comprehensive (15-20 slides)",
          "Technical",
          (
              "Integrating visual design workflows with Google Workspace and"
              " scaling low-latency media storage."
          ),
          "JAPAC",
          "Enterprise",
      ),
      (
          "T2-34",
          "FedEx",
          "fedex.com",
          "Logistics & Supply Chain",
          "Global Express & Parcel Logistics",
          "Security",
          "AI-Driven SecOps & Threat Detection",
          "S1",
          "bespoke_custom",
          "Standard (8-12 slides)",
          "Executive",
          (
              "Securing global air and ground hub operations with AI-driven"
              " threat detection and automated response."
          ),
          "NORTHAM",
          "Select",
      ),
      (
          "T2-35",
          "AXA",
          "axa.com",
          "Insurance",
          "Global Life & Health Insurance",
          "Data Analytics & Databases",
          "Database Modernization & AlloyDB Migration",
          "S3",
          "cloudhub",
          "Comprehensive (15-20 slides)",
          "Technical",
          (
              "Migrating legacy commercial policy databases to AlloyDB with"
              " zero-downtime replication."
          ),
          "EMEA",
          "Select",
      ),
      (
          "T2-36",
          "Lockheed Martin",
          "lockheedmartin.com",
          "Aerospace & Defense",
          "Defense Systems & Space",
          "Workspace & Collaboration",
          "AI-First Employee Collaboration (Gemini for Workspace)",
          "S4",
          "smart_hybrid",
          "Comprehensive (15-20 slides)",
          "Executive",
          (
              "Enabling assured mission engineering collaboration with strict"
              " air-gapped security controls."
          ),
          "NORTHAM",
          "Select",
      ),
  ]

  side_panel_actions = (
      "insert_library_slide",
      "transform_text_cfo_persona",
      "transform_images_only_account",
      "transform_both_scope",
      "nanobanana_generate_visual",
      "nanobanana_restyle_slide",
      "translate_es",
  )

  return tuple(
      DeckTestSpec(
          test_id=row[0],
          tier="tier2_pairwise",
          customer_name=row[1],
          customer_domain=row[2],
          industry=row[3],
          sub_industry=row[4],
          solution=row[5],
          sales_play=row[6],
          sales_stage=row[7],
          deck_strategy=row[8],
          deck_length=row[9],
          audience_persona=row[10],
          business_context=row[11],
          region=row[12],
          segment=row[13],
          post_deck_action=side_panel_actions[idx % len(side_panel_actions)],
      )
      for idx, row in enumerate(additional_rows)
  )


TIER2_PAIRWISE_SPECS: tuple[DeckTestSpec, ...] = (
    TIER1_SMOKE_SPECS + _build_tier2_additional_specs()
)


def _build_tier3_additional_specs() -> tuple[DeckTestSpec, ...]:
  """Builds 72 additional specs (T3-37..T3-108) for the 108-deck marathon suite."""
  intl_customers = [
      ("Rakuten", "rakuten.co.jp", "Retail & Consumer Goods", "JAPAC"),
      ("SAP SE", "sap.de", "Software & Internet", "EMEA"),
      ("Barclays", "barclays.co.uk", "Financial Services", "EMEA"),
      ("Itaú Unibanco", "itau.com.br", "Financial Services", "LATAM"),
      ("Carrefour", "carrefour.com", "Retail & Consumer Goods", "EMEA"),
      ("Novartis", "novartis.com", "Healthcare & Life Sciences", "EMEA"),
      ("Bosch", "bosch.de", "Manufacturing & Industrial", "EMEA"),
      ("Sony", "sony.co.jp", "Media & Entertainment", "JAPAC"),
      ("NTT Docomo", "docomo.ne.jp", "Telecommunications", "JAPAC"),
      ("Hyundai", "hyundai.com", "Automotive & Mobility", "JAPAC"),
      ("Ubisoft", "ubisoft.com", "Gaming", "EMEA"),
      ("Iberdrola", "iberdrola.com", "Energy & Utilities", "EMEA"),
  ]
  actions = (
      "insert_library_slide",
      "transform_text_cfo_persona",
      "transform_images_only_account",
      "transform_both_scope",
      "nanobanana_generate_visual",
      "nanobanana_restyle_slide",
      "translate_es",
  )

  specs: list[DeckTestSpec] = []
  for idx in range(72):
    spec_num = 37 + idx
    cust_name, cust_domain, industry, region = intl_customers[
        idx % len(intl_customers)
    ]
    solution = SOLUTION_AREAS[idx % len(SOLUTION_AREAS)]
    plays_for_sol = SALES_PLAYS_BY_SOLUTION[solution]
    primary_play = plays_for_sol[idx % len(plays_for_sol)]
    # Every 4th spec uses a multi-play combination
    if idx % 4 == 0 and len(plays_for_sol) > 1:
      secondary_play = plays_for_sol[(idx + 1) % len(plays_for_sol)]
      sales_play = f"{primary_play}, {secondary_play}"
    else:
      sales_play = primary_play

    strategy = DECK_STRATEGIES[idx % len(DECK_STRATEGIES)]
    length = DECK_LENGTHS[(idx // 3) % len(DECK_LENGTHS)]
    stage = SALES_STAGES[idx % len(SALES_STAGES)]
    persona = (
        "Executive" if stage in ("S0", "S1") or idx % 2 == 0 else "Technical"
    )
    action = actions[idx % len(actions)]

    specs.append(
        DeckTestSpec(
            test_id=f"T3-{spec_num:03d}",
            tier="tier3_marathon",
            customer_name=cust_name,
            customer_domain=cust_domain,
            industry=industry,
            sub_industry="Global Enterprise Operations",
            solution=solution,
            sales_play=sales_play,
            sales_stage=stage,
            deck_strategy=strategy,
            deck_length=length,
            audience_persona=persona,
            business_context=(
                f"{cust_name} is executing a strategic {solution}"
                f" transformation focused on {primary_play} with Gemini"
                " Enterprise on Google Cloud."
            ),
            region=region,
            segment="Select",
            post_deck_action=action,
        )
    )
  return tuple(specs)


TIER3_MARATHON_SPECS: tuple[DeckTestSpec, ...] = (
    TIER2_PAIRWISE_SPECS + _build_tier3_additional_specs()
)


def get_test_matrix(tier: str = "tier1_smoke") -> list[DeckTestSpec]:
  """Returns the list of DeckTestSpec objects for the requested tier."""
  normalized = (tier or "tier1_smoke").strip().lower()
  if normalized in ("tier1", "tier1_smoke", "smoke"):
    return list(TIER1_SMOKE_SPECS)
  if normalized in ("tier2", "tier2_pairwise", "pairwise"):
    return list(TIER2_PAIRWISE_SPECS)
  if normalized in ("tier3", "tier3_marathon", "marathon", "all"):
    return list(TIER3_MARATHON_SPECS)
  raise ValueError(
      f"Unknown test tier '{tier}'. Valid tiers: tier1_smoke, tier2_pairwise,"
      " tier3_marathon"
  )


def verify_matrix_coverage(specs: list[DeckTestSpec]) -> dict[str, Any]:
  """Computes combinatorial coverage metrics across a list of DeckTestSpecs."""
  strategies = {s.deck_strategy for s in specs}
  lengths = {s.deck_length for s in specs}
  stages = {s.sales_stage for s in specs}
  solutions = {s.solution for s in specs}
  industries = {s.industry for s in specs}
  plays = {
      p.strip() for s in specs for p in s.sales_play.split(",") if p.strip()
  }
  side_panel_actions = {s.post_deck_action for s in specs if s.post_deck_action}

  strategy_x_length = {(s.deck_strategy, s.deck_length) for s in specs}
  strategy_x_track = {(s.deck_strategy, s.stage_track) for s in specs}
  solution_x_strategy = {(s.solution, s.deck_strategy) for s in specs}

  return {
      "total_specs": len(specs),
      "strategies_covered": len(strategies),
      "lengths_covered": len(lengths),
      "stages_covered": len(stages),
      "solutions_covered": len(solutions),
      "industries_covered": len(industries),
      "sales_plays_covered": len(plays),
      "side_panel_actions_covered": sorted(side_panel_actions),
      "smart_hybrid_specs_count": sum(
          1 for s in specs if s.deck_strategy == "smart_hybrid"
      ),
      "strategy_x_length_pairs": len(strategy_x_length),
      "strategy_x_track_pairs": len(strategy_x_track),
      "solution_x_strategy_pairs": len(solution_x_strategy),
      "all_strategy_x_length_covered": len(strategy_x_length) == 9,
      "all_strategy_x_track_covered": len(strategy_x_track) == 6,
      "all_solution_x_strategy_covered": len(solution_x_strategy) == 15,
      "all_19_industries_covered": len(industries) >= 19,
      "all_27_plays_covered": len(plays) >= 27,
  }
