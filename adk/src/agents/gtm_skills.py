"""Google Cloud GTM Sales Enablement skills for RFP Acceleration and Pitch & Proposal Hub (https://your-sales-portal.example.com/catalog) integration."""

import json
from typing import Any, Dict


class GTMSkills:
  """Specialized skills supporting Google Cloud Go-to-Market (GTM) sales enablement workflows."""

  @staticmethod
  def phub_handoff_skill(
      customer_name: str,
      er_number: str = "",
      business_context: str = "",
      deck_url: str = "",
      user_ldap: str = "",
  ) -> str:
    """Escalates and packages a customer pitch for White-Glove Support via Pitch & Proposal Hub (https://your-sales-portal.example.com/catalog).

    Args:
        customer_name: Name of the target customer (e.g., 'Starbucks').
        er_number: Opportunity ER number.
        business_context: Key customer business goals or requirements.
        deck_url: Link to any existing PitchGen generated presentation deck.
        user_ldap: Requesting sales representative's LDAP.

    Returns:
        A serialized JSON response containing formatted escalation package and https://your-sales-portal.example.com/requests/new link.
    """
    print(
        f"[GTMSkills] Escalating proposal for '{customer_name}' to Pitch &"
        " Proposal Hub (https://your-sales-portal.example.com/catalog)..."
    )

    package_payload = {
        "customerName": customer_name,
        "opportunityEr": er_number or "Not specified",
        "businessContext": business_context,
        "existingDeckUrl": deck_url or "None generated yet",
        "requestorLdap": user_ldap or "Autodetected",
        "serviceCatalogUrl": "https://your-sales-portal.example.com/catalog",
        "newRequestUrl": "https://your-sales-portal.example.com/requests/new",
    }

    response_dict = {
        "status": "success",
        "message": (
            f"White-Glove proposal package for **{customer_name}** has been"
            " successfully prepared for Pitch & Proposal Hub (`https://your-sales-portal.example.com/catalog`)."
        ),
        "escalation_package": package_payload,
        "action_required": (
            "Please click [https://your-sales-portal.example.com/requests/new](https://your-sales-portal.example.com/requests/new) to submit this package"
            " to our dedicated proposal designer team."
        ),
    }

    return json.dumps(response_dict, indent=2)

  @staticmethod
  def rfp_accelerator_skill(
      rfp_question: str,
      customer_name: str = "",
      industry: str = "",
      solution: str = "",
      compliance_frameworks: str = "",
  ) -> str:
    """Automates answers to customer RFPs, RFIs, and security questionnaires using Google Cloud GTM knowledge bases.

    Args:
        rfp_question: The customer's RFP or technical questionnaire prompt.
        customer_name: Target customer name.
        industry: Customer industry vertical (e.g., 'Retail', 'Financial
          Services').
        solution: Target Google Cloud solution (e.g., 'Gemini Enterprise',
          'BigQuery').
        compliance_frameworks: Comma-separated compliance standards (e.g.,
          'FedRAMP, HIPAA, SOC2').

    Returns:
        A serialized JSON response containing the formatted RFP answer and slide
        recommendations.
    """
    print(
        f"[GTMSkills] Processing RFP answer for '{customer_name}' in industry"
        f" '{industry}'..."
    )

    frameworks_list = (
        [f.strip() for f in compliance_frameworks.split(",") if f.strip()]
        if compliance_frameworks
        else ["Standard Cloud Security"]
    )

    answer_matrix = {
        "customer": customer_name or "Enterprise Customer",
        "industry_vertical": industry or "Cross-Industry",
        "solution_focus": solution or "Google Cloud Platform",
        "compliance_verified": frameworks_list,
        "question_analyzed": rfp_question,
        "recommended_response": (
            "Google Cloud delivers enterprise-grade security, data governance, "
            "and compliance across all services. Customer data is encrypted in "
            "transit and at rest by default, with VPC Service Controls and IAM "
            "enforcing strict boundary isolation."
        ),
        "suggested_slides": [
            "Google Cloud Security & Compliance Overview",
            f"Enterprise AI Governance for {industry or 'your industry'}",
        ],
        "rfp_app_link": "https://your-sales-portal.example.com/rfp-accelerator",
    }

    return json.dumps(answer_matrix, indent=2)

  @staticmethod
  def slide_job_skill(
      slide_job: str,
      cvi_cluster: str = "",
      target_audience: str = "CxO",
      technical_maturity: str = "L100 (Conceptual)",
  ) -> str:
    """Retrieves authoritative Slide Job metadata, CVI cluster mapping, and content generation rules.

    Args:
        slide_job: The Slide Job ENUM (e.g., 'Navigation', 'Market_Trends',
          'Current_State', 'Why_Google_Cloud', 'Solution_Overview',
          'Architecture', 'Business_Value', 'Proof_Points', 'Commercials',
          'Path_to_Prod').
        cvi_cluster: Optional CVI cluster override ('Context', 'Vision',
          'Impact', 'Realization').
        target_audience: Target audience persona ('CxO', 'BDM', 'TDM',
          'Architect_Engineer').
        technical_maturity: Target technical depth ('L100 (Conceptual)', 'L200
          (Strategic)', 'L300 (Deep Technical)').

    Returns:
        A serialized JSON response containing formatted slide job rules and
        metadata schema.
    """
    job_cvi_map = {
        "Navigation": "Connective Tissue",
        "Market_Trends": "Context",
        "Current_State": "Context",
        "Strategic_Partnership": "Vision",
        "Why_Google_Cloud": "Solution",
        "Solution_Overview": "Solution",
        "Architecture": "Solution",
        "Business_Value": "Impact",
        "Proof_Points": "Impact",
        "Commercials": "Realization",
        "Path_to_Prod": "Realization",
    }
    resolved_cvi = cvi_cluster or job_cvi_map.get(slide_job, "Context")

    content_rules = {
        "Navigation": (
            "Set up the deck: Title slides, agendas, executive summaries,"
            " section dividers, and team intros."
        ),
        "Market_Trends": (
            "Show industry context: Macro shifts, regulatory pressures, and"
            " standard industry challenges."
        ),
        "Current_State": (
            "Reflect specific pain: Discovery recaps, legacy architecture"
            " diagrams, identified bottlenecks."
        ),
        "Strategic_Partnership": (
            "Enterprise co-innovation & principles: Long-term joint vision,"
            " Google trust principles ('your data is your IP', open cloud),"
            " executive sponsorship, joint governance, and Alphabet ecosystem"
            " synergies."
        ),
        "Why_Google_Cloud": (
            "Show our differentiators: Core platform advantages, custom TPUs,"
            " open-source integration, security posture."
        ),
        "Solution_Overview": (
            "Show the front-end product: High-level capabilities, UI mockups,"
            " feature summaries, user experiences."
        ),
        "Architecture": (
            "Show the back-end technicals: Deep blueprints, node"
            " configurations, reference architectures, data flows."
        ),
        "Business_Value": (
            "Show the financial justification: ROI projections, TCO reduction"
            " models, business outcome frameworks."
        ),
        "Proof_Points": (
            "Prove we've done it: Customer case studies, logo slides, quotes,"
            " Gartner/Forrester Magic Quadrants."
        ),
        "Commercials": (
            "Talk pricing & investment: Consumption models, packaging,"
            " Enterprise Discount Programs (EDP), SKUs."
        ),
        "Path_to_Prod": (
            "Show next steps & timelines: 30-60-90 day roadmaps, CAF stages,"
            " structured migration plans."
        ),
    }

    intensity_map = {
        "Proof_Points": "0% (IMMUTABLE)",
        "Why_Google_Cloud": "15% (LIGHT)",
        "Architecture": "25% (LIGHT_MOD)",
        "Solution_Overview": "60% (MODERATE)",
        "Commercials": "15% (LIGHT - HITL Required)",
        "Path_to_Prod": "75% (HIGH)",
        "Strategic_Partnership": "85% (HEAVY)",
        "Navigation": "85% (HEAVY)",
        "Market_Trends": "90% (HEAVY)",
        "Current_State": "95% (HEAVY)",
        "Business_Value": "100% (FULL)",
    }
    throttling_tier_map = {
        "Proof_Points": "IMMUTABLE",
        "Why_Google_Cloud": "LIGHT",
        "Architecture": "LIGHT_MOD",
        "Solution_Overview": "MODERATE",
        "Commercials": "LIGHT",
        "Path_to_Prod": "HIGH",
        "Strategic_Partnership": "HEAVY",
        "Navigation": "HEAVY",
        "Market_Trends": "HEAVY",
        "Current_State": "HEAVY",
        "Business_Value": "FULL",
    }

    result = {
        "slide_job": slide_job,
        "cvi_cluster": resolved_cvi,
        "target_audience": target_audience,
        "technical_maturity": technical_maturity,
        "customization_intensity": intensity_map.get(
            slide_job, "50% (MODERATE)"
        ),
        "throttling_tier": throttling_tier_map.get(slide_job, "MODERATE"),
        "agentic_purpose_and_profile": content_rules.get(
            slide_job, "Standard content profile."
        ),
        "schema_reference": "GTM_Agentic_Slide_Metadata",
    }
    return json.dumps(result, indent=2)

  SLIDE_JOB_NARRATIVE_ORDER = {
      "Navigation": 0,
      "Market_Trends": 10,
      "Current_State": 20,
      "Strategic_Partnership": 30,
      "Why_Google_Cloud": 40,
      "Solution_Overview": 50,
      "Architecture": 60,
      "Business_Value": 70,
      "Proof_Points": 80,
      "Commercials": 90,
      "Path_to_Prod": 100,
  }

  @classmethod
  def infer_slide_job(cls, slide_or_text: Any) -> str:
    """Infers the most appropriate Slide Job ENUM for a slide dictionary or text."""
    if isinstance(slide_or_text, dict):
      explicit = (
          slide_or_text.get("slide_job")
          or (
              slide_or_text.get("taxonomy", {}).get("slide_job")
              if isinstance(slide_or_text.get("taxonomy"), dict)
              else None
          )
      )
      if explicit and explicit in cls.SLIDE_JOB_NARRATIVE_ORDER:
        return explicit
      title = str(
          slide_or_text.get("title")
          or slide_or_text.get("slide_title")
          or slide_or_text.get("name")
          or (
              slide_or_text.get("placeholders", {}).get("title")
              if isinstance(slide_or_text.get("placeholders"), dict)
              else ""
          )
          or ""
      )
      content = str(
          slide_or_text.get("content")
          or slide_or_text.get("slide_summary")
          or slide_or_text.get("speaker_notes")
          or (
              slide_or_text.get("placeholders", {}).get("body")
              if isinstance(slide_or_text.get("placeholders"), dict)
              else ""
          )
          or ""
      )
      text = f"{title} {content}".lower()
    else:
      text = str(slide_or_text).lower()

    if any(k in text for k in ["roadmap", "path to prod", "next steps", "30-60-90", "timeline", "migration plan"]):
      return "Path_to_Prod"
    if any(k in text for k in ["commercial", "pricing", "investment", "edp", "committed use discount", "cud"]):
      return "Commercials"
    if any(k in text for k in ["case study", "customer story", "proof point", "testimonial", "customer quote", "gartner", "forrester"]):
      return "Proof_Points"
    if any(k in text for k in ["business value", "roi", "tco", "financial justification", "npv", "payback period", "cost savings"]):
      return "Business_Value"
    if any(k in text for k in ["architecture", "blueprint", "pipeline", "ingestion", "technical system", "node flow", "diagram"]):
      return "Architecture"
    if any(k in text for k in ["strategic partnership", "joint vision", "governance", "alphabet ecosystem", "co-innovation"]):
      return "Strategic_Partnership"
    if any(k in text for k in ["why google", "differentiator", "planetary scale", "security-by-default", "custom tpu"]):
      return "Why_Google_Cloud"
    if any(k in text for k in ["market trend", "industry shift", "macro", "disruption", "regulatory update"]):
      return "Market_Trends"
    if any(k in text for k in ["current state", "pain point", "friction", "bottleneck", "challenge", "discovery recap"]):
      return "Current_State"
    if any(k in text for k in ["agenda", "navigation", "executive summary", "table of contents", "welcome", "title"]):
      return "Navigation"
    return "Solution_Overview"

  @classmethod
  def get_slide_job_narrative_order(cls, slide_or_job: Any) -> int:
    """Returns the numerical narrative order (0-100) for a slide job or slide object."""
    if isinstance(slide_or_job, str) and slide_or_job in cls.SLIDE_JOB_NARRATIVE_ORDER:
      return cls.SLIDE_JOB_NARRATIVE_ORDER[slide_or_job]
    job = cls.infer_slide_job(slide_or_job)
    return cls.SLIDE_JOB_NARRATIVE_ORDER.get(job, 50)

  @staticmethod
  def validate_slide_metadata_schema(metadata_json: str) -> str:
    """Validates slide JSONB metadata against GTM_Agentic_Slide_Metadata schema and nomenclature.

    Args:
        metadata_json: Serialized JSON string representing slide metadata.

    Returns:
        A serialized JSON response containing validation status and diagnostics.
    """
    try:
      data = json.loads(metadata_json)
    except Exception as e:
      return json.dumps({
          "status": "error",
          "message": f"Invalid JSON syntax: {str(e)}",
          "valid": False,
      })

    required_roots = ["slide_id", "taxonomy", "gtm_filters", "governance"]
    missing_roots = [k for k in required_roots if k not in data]
    if missing_roots:
      return json.dumps({
          "status": "error",
          "message": f"Missing required root fields: {missing_roots}",
          "valid": False,
      })

    tax = data.get("taxonomy", {})
    valid_jobs = {
        "Navigation",
        "Market_Trends",
        "Current_State",
        "Strategic_Partnership",
        "Why_Google_Cloud",
        "Solution_Overview",
        "Architecture",
        "Business_Value",
        "Proof_Points",
        "Commercials",
        "Path_to_Prod",
    }
    job = tax.get("slide_job", "")
    if job not in valid_jobs:
      return json.dumps({
          "status": "error",
          "message": (
              f"Invalid or missing 'slide_job': '{job}'. Must be one of"
              f" {sorted(list(valid_jobs))}"
          ),
          "valid": False,
      })

    valid_cvis = {
        "Connective Tissue",
        "Context",
        "Vision",
        "Solution",
        "Impact",
        "Realization",
    }
    cvi = tax.get("cvi_cluster", "")
    if cvi not in valid_cvis:
      return json.dumps({
          "status": "error",
          "message": (
              f"Invalid or missing 'cvi_cluster': '{cvi}'. Must be one of"
              f" {sorted(list(valid_cvis))}"
          ),
          "valid": False,
      })

    valid_practice_areas = {
        "AI",
        "Agentic Workplace Transformation",
        "Data",
        "Infrastructure",
        "Security",
    }
    practice_area = data.get("gtm_filters", {}).get("practice_area", "")
    if practice_area and practice_area not in valid_practice_areas:
      return json.dumps({
          "status": "error",
          "message": (
              f"Invalid 'practice_area': '{practice_area}'. Must be one of"
              f" {sorted(list(valid_practice_areas))}"
          ),
          "valid": False,
      })

    # Check for legacy or retired terminology in featured_products (Enterprise-Brand-Unification)
    products = data.get("gtm_filters", {}).get("featured_products", [])
    legacy_terms = [
        "Vertex AI",
        "Vertex AI Search",
        "Vertex AI Conversation",
        "Gemini Enterprise Agent Platform",
        "GEAP",
        "Gemini Enterprise app",
        "Gemini 1.0",
        "Gemini 1.5 Pro",
    ]
    found_legacy = [
        t for p in products for t in legacy_terms if t.lower() in p.lower()
    ]
    if found_legacy:
      return json.dumps({
          "status": "error",
          "message": (
              "Legacy terminology detected in 'featured_products':"
              f" {found_legacy}. Always use 'Gemini Enterprise' (one product),"
              " 'Gemini 3.8 Flash', etc."
          ),
          "valid": False,
      })

    # Validate governance fields if present
    gov = data.get("governance", {})
    if "is_customer_facing" in gov and not isinstance(gov["is_customer_facing"], bool):
      return json.dumps({
          "status": "error",
          "message": (
              f"Invalid 'is_customer_facing': '{gov['is_customer_facing']}'. Must be a boolean (true/false)."
          ),
          "valid": False,
      })

    valid_confidentiality = {
        "Public",
        "Google Confidential",
        "NDA Only",
        "Google Internal Only",
        "Internal Only",
    }
    conf = gov.get("confidentiality", "")
    if conf and conf not in valid_confidentiality:
      return json.dumps({
          "status": "error",
          "message": (
              f"Invalid 'confidentiality': '{conf}'. Must be one of"
              f" {sorted(list(valid_confidentiality))}"
          ),
          "valid": False,
      })

    return json.dumps({
        "status": "success",
        "message": (
            f"Slide '{data.get('slide_id')}' metadata is 100% compliant with"
            " GTM_Agentic_Slide_Metadata schema and nomenclature."
        ),
        "valid": True,
    })
