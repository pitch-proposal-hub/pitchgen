---
name: compete_differentiation
description: >
  K6: Compete & Differentiation Skill for PitchGen. Synthesizes Google Cloud
  competitive differentiation, SWOT positioning (vs. AWS, Microsoft Azure,
  Snowflake, Databricks, Oracle), One Google ecosystem advantages, and
  competitor disambiguation guardrails from Golden Gate's Strategic Customer
  Insights, Executive Brief Builder, and Insights AI agents.
---

# Compete & Differentiation Skill (`K6`)

## 1. Core Governance & Slide Customization Rules

-   **Slide Canvas (`Why_Google_Cloud` = `15% LIGHT`):**
    -   Keep all on-slide text strictly **positive and Google Cloud-focused**
        ("Why Google Cloud for `<Industry>`", open multi-cloud architecture,
        unified AI + Data foundation, planet-scale infrastructure).
    -   **NEVER** print competitor names (AWS, Azure, Snowflake, Databricks,
        Oracle) or negative attack copy directly on customer-facing slide shapes
        unless the user explicitly asked for a side-by-side comparison table.
    -   Follow modern Google Cloud terminology: use **Gemini Enterprise**,
        **Google Agent Development Kit (ADK)**, **Google GenAI SDK**,
        **BigQuery**, **AlloyDB**, **Spanner**, **Cloud Run**, and **Enterprise
        Data Stores**.
-   **Speaker Notes (`speaker_notes` = Proactive Competitive Landmines):**
    -   Place concrete competitive differentiation, trap-setting questions, and
        objection-handling talking points inside the slide's **Speaker Notes**
        (`🎯 Competitive Positioning & Objection Handling`).
-   **Strict Entity & Competitor Disambiguation Guardrail (from
    `InsightsAiAgent`):**
    -   Distinguish between a customer's **incumbent footprint** (e.g., existing
        Azure AD, AWS S3, or Oracle ERP workloads that Google Cloud
        interoperates with via BigQuery Omni / Cross-Cloud Interconnect) and an
        **active head-to-head competitor evaluation**.
    -   Frame incumbent workloads through **"Embrace & Extend (Open
        Multi-Cloud)"** rather than rip-and-replace friction.

## 2. Competitive Differentiation Matrix by Incumbent / Alternative

Competitor / Alternative                                | Customer Pain Point (`Current_State`)                                                                                                                                                             | Google Cloud Differentiator (`Why_Google_Cloud` Canvas)                                                                                                                                                                                         | Speaker Note Landmine / Trap Question
:------------------------------------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------
**AWS (Bedrock / Redshift / SageMaker)**                | Fragmented AI & data services requiring complex stitching across S3, Glue, Redshift, and Bedrock; rigid model lock-in and unpredictable egress/compute TCO.                                       | **Unified AI-Ready Data Cloud & Full-Stack Innovation:** First-party frontier multimodal **Gemini Models**, custom TPUs, **BigQuery** zero-ETL lakehouse, and open **Google Agent Development Kit (ADK)** in one integrated platform.           | *"Ask the architect: How many separate data copies and IAM policies are required today to move operational data into an agentic workflow with sub-second grounding?"*
**Microsoft Azure (OpenAI Service / Fabric / Copilot)** | Proprietary ecosystem lock-in, rigid per-seat licensing minimums, fragmented Fabric capacity throttling, and lack of multi-model / multi-system agent interoperability.                           | **Open, Multi-Model & Multi-Cloud Enterprise Agent Platform:** **Gemini Enterprise** connects natively to Microsoft 365, SharePoint, ServiceNow, Salesforce, SAP, and Jira via the open **A2A Protocol** without forcing single-vendor lock-in. | *"Highlight that Gemini Enterprise indexes and grounds across Microsoft, Salesforce, and SAP estates natively—giving business users one cross-enterprise agentic workspace."*
**Snowflake / Databricks**                              | Siloed data compute billing spikes, bolted-on third-party LLMs with separate governance planes, and lack of native operational transactional engines (Spanner/AlloyDB) + global network backbone. | **Zero-Copy Unified Data-to-AI Continuum:** **BigQuery** natively handles structured, unstructured, vector, and Apache Iceberg workloads with built-in **Gemini Models** and real-time federation to **AlloyDB** and **Spanner**.               | *"Emphasize open Apache Iceberg support and zero-copy governance: run multimodal Gemini reasoning directly where enterprise data already lives."*
**Oracle (OCI / Legacy Exadata)**                       | Punitive licensing audits, hardware refresh lock-in, and inability to natively fuse core ERP/transactional data with modern agentic AI and analytics.                                             | **Oracle on Google Cloud + AlloyDB Modernization:** Run mission-critical Oracle workloads on bare-metal/OCI interconnect at near-zero latency to **BigQuery** and **Gemini Enterprise**, or modernize to PostgreSQL-compatible **AlloyDB**.     | *"Position Google Cloud as the fastest bridge from core Oracle ERP/database estates to real-time AI analytics without risky day-1 application rewrites."*

## 3. "One Google" Ecosystem Advantage (from `ExecBriefAgent`)

When pitching to **CxO / Executive Personas** (`Strategic_Partnership` &
`Why_Google_Cloud`), weave in relevant **One Google** co-innovation pillars
where applicable to the customer's industry:

-   **Retail, CPG & Media:** Google Search, YouTube, Google Ads & DV360 audience
    reach combined with Cloud AI personalization and commerce agents.
-   **Automotive, Logistics & Energy:** Google Maps Platform, Earth Engine
    geospatial intelligence, Android Automotive OS, and Waymo/DeepMind research
    heritage.
-   **Financial Services & Public Sector:** Mandiant frontline threat
    intelligence, Google SecOps, CyberShield, and Assured Workloads sovereign
    controls.
