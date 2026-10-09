"""Strategic Customer & Competitive Intelligence Workflow.

Synthesizes Voice-of-the-Customer (VoC) executive briefing themes, adoption
risk mitigations, competitive SWOT positioning, and industry peer reference
recommendations to ground Phase 1 Outlines and Phase 2 Slide Synthesis.
"""

from __future__ import annotations

from typing import Any
from agents.workflows.base_workflow import BaseWorkflow
from agents.workflows.customer_reference_retriever import PRIORITY_CUSTOMERS_BY_INDUSTRY


INDUSTRY_VOC_THEMES: dict[str, list[str]] = {
    "retail": [
        "Unified omnichannel commerce & conversational product discovery",
        "Real-time inventory visibility & supply chain demand forecasting",
        "Frontline store associate productivity & automated clienteling",
    ],
    "financial services": [
        "Autonomous financial research, risk modeling & regulatory compliance",
        "Real-time payment fraud detection & AML investigation automation",
        "Modernizing core banking data platforms with zero-trust governance",
    ],
    "healthcare": [
        "Clinical workflow automation & multimodal patient record synthesis",
        "Interoperable healthcare data foundation (FHIR) & claims intelligence",
        "Accelerating life sciences R&D and clinical trial discovery",
    ],
    "default": [
        "Scaling production AI agents with enterprise governance and grounding",
        "Unifying multimodal operational data for real-time decision intelligence",
        "Reducing total cost of ownership (TCO) while accelerating time-to-market",
    ],
}

TOP_BLOCKERS_AND_MITIGATIONS: list[dict[str, str]] = [
    {
        "blocker": "Data silos, governance complexity, and security compliance",
        "mitigation": (
            "Zero-copy lakehouse federation, Customer-Managed Encryption Keys"
            " (CMEK), VPC Service Controls, and unified Knowledge Catalog"
            " lineage."
        ),
    },
    {
        "blocker": "Pilot-to-production gap & agent hallucination risk",
        "mitigation": (
            "Managed agent runtime in Gemini platform with Enterprise Search"
            " grounding, deterministic guardrails, and continuous evaluation."
        ),
    },
    {
        "blocker": "Multi-cloud lock-in & unpredictable AI inference TCO",
        "mitigation": (
            "Open Model Garden in Gemini platform, dynamic model routing"
            " (Gemini Flash & Pro), and AI Hypercomputer price-performance."
        ),
    },
]

COMPETE_SWOT_HIGHLIGHTS: dict[str, str] = {
    "Data & AI Unification": (
        "BigQuery and AlloyDB provide native vector search and multimodal AI"
        " invocation directly in SQL without complex ETL duplication."
    ),
    "Agentic Platform": (
        "Gemini platform unifies first-party and open-weight models in Model"
        " Garden with Antigravity multi-agent orchestration and A2A"
        " interoperability."
    ),
    "Infrastructure & Security": (
        "End-to-end custom silicon (TPU + Axion) paired with unified cloud"
        " posture management and autonomous threat intelligence."
    ),
}


class CustomerInsightsWorkflow(BaseWorkflow):
  """Synthesizes strategic customer, industry, and competitive intelligence."""

  def __init__(self, config: Any) -> None:
    super().__init__(
        "CustomerInsightsWorkflow",
        "Synthesizes industry value drivers, objection mitigations, and"
        " competitive differentiation.",
    )
    self.config = config

  def execute(
      self,
      customer_name: str,
      industry: str = "",
      sub_industry: str = "",
      sales_plays: list[str] | None = None,
      business_context: str = "",
  ) -> dict[str, Any]:
    """Generates a structured strategic briefing for outline and slide synthesis."""
    ind_low = f"{industry} {sub_industry}".lower()
    voc_themes = INDUSTRY_VOC_THEMES["default"]
    peer_refs = list(PRIORITY_CUSTOMERS_BY_INDUSTRY.get("retail", ()))[:4]

    for key, themes in INDUSTRY_VOC_THEMES.items():
      if key != "default" and key in ind_low:
        voc_themes = themes
        break

    for key, peers in PRIORITY_CUSTOMERS_BY_INDUSTRY.items():
      if key in ind_low:
        peer_refs = [
            p for p in peers if p.lower() != str(customer_name or "").lower()
        ][:5]
        break

    compete_summary = " | ".join(
        f"{k}: {v}" for k, v in COMPETE_SWOT_HIGHLIGHTS.items()
    )
    plays_str = (
        ", ".join(sales_plays or []) or "Enterprise AI & Data Modernization"
    )

    lines = [
        "=== STRATEGIC CUSTOMER & COMPETITIVE INTELLIGENCE ===",
        (
            f"Target Account: {customer_name or 'Enterprise Customer'} "
            f"({industry or 'Cross-Industry'}"
            f"{' / ' + sub_industry if sub_industry else ''})"
        ),
        f"Active Solution Plays: {plays_str}",
        "1. Voice-of-Customer (VoC) Executive Priorities:",
        *[f"   - {t}" for t in voc_themes],
        "2. Proactive Risk & Objection Mitigations:",
        *[
            f"   - [{b['blocker']}] -> {b['mitigation']}"
            for b in TOP_BLOCKERS_AND_MITIGATIONS
        ],
        f"3. Differentiated Platform Strengths: {compete_summary}",
        f"4. Verified Industry Peer References: {', '.join(peer_refs)}",
    ]
    formatted_briefing = "\n".join(lines)

    return {
        "customer_name": customer_name,
        "industry": industry,
        "sub_industry": sub_industry,
        "voc_ebc_themes": voc_themes,
        "top_blockers_and_mitigations": TOP_BLOCKERS_AND_MITIGATIONS,
        "compete_swot": compete_summary,
        "priority_peer_references": peer_refs,
        "formatted_briefing": formatted_briefing,
    }
