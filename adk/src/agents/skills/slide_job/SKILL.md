---
name: slide-job
description: >-
  Guides slide retrieval, generation, and transformation based on the intention behind the slide
  using the authoritative Slide Job taxonomy (Navigation, Market_Trends, Current_State, Strategic_Partnership,
  Why_Google_Cloud, Solution_Overview, Architecture, Business_Value, Proof_Points, Commercials, Path_to_Prod) and CVI Clusters.
---

# Agentic Slide Repository: Taxonomy & Metadata Specification

This skill defines the authoritative structural taxonomy, ENUM definitions, and orchestration rules for the agentic slide retrieval and generation platform. It shifts slide selection from legacy keyword searches to an **intent-based architecture** utilizing the **CVI Framework** (`@cvi-framework`) and an intuitive **Slide Job** taxonomy.

---

## 1. The Strategic Orchestration Layer
To enable PitchGen to build cohesive, narrative-driven pitch decks automatically, slides are categorized not just by "what is on them" (products), but by **"what they do" in a sales conversation**. The orchestrator uses two primary dimensions:

-   **CVI Cluster** (`Connective Tissue`, `Context`, `Vision`, `Solution`,
    `Impact`, `Realization`)
-   **Slide Job ENUM** (11 micro-intent categories)

---

## 2. CVI Cluster & Slide Job Mapping Table

CVI Cluster                                      | Slide Job ENUM          | Agentic Purpose & Content Profile
:----------------------------------------------- | :---------------------- | :--------------------------------
**Connective Tissue** *(CVI 00)*                 | `Navigation`            | **Set up the deck**: Title slides, agendas, executive summaries, section dividers, and team intros.
**Context** *(Why Change? — CVI 01 & 02)*        | `Market_Trends`         | **Show industry context**: Macro shifts, regulatory pressures, and standard industry challenges.
**Context** *(Why Change? — CVI 01 & 02)*        | `Current_State`         | **Reflect customer reality & business priorities**: Discovery recap mirroring the customer's strategic goals, business challenges, executive priorities, operational friction, and organizational roadblocks (kept strategic and business-focused, not overly technical).
**Vision** *(Why Now? — CVI 03)*                 | `Strategic_Partnership` | **Enterprise co-innovation & principles**: Long-term joint vision, Google trust principles (data sovereignty, "your data is your IP", open cloud), executive sponsorship, joint governance, and Alphabet ecosystem synergies (tailored to Enterprise & Strategic accounts).
**Solution** *(Why Google Cloud? — CVI 04a/04b)* | `Why_Google_Cloud`      | **Show our differentiators**: Core platform advantages, custom TPUs, open-source integration, security posture.
**Solution** *(Why Google Cloud? — CVI 04a/04b)* | `Solution_Overview`     | **Show the front-end product**: High-level capabilities, UI mockups, feature summaries, user experiences.
**Solution** *(Why Google Cloud? — CVI 04a/04b)* | `Architecture`          | **Show the back-end technicals**: Deep blueprints, node configurations, reference architectures, data flows.
**Impact** *(Proof & Value — CVI 04c)*           | `Business_Value`        | **Show the financial justification**: ROI projections, TCO reduction models, business outcome frameworks.
**Impact** *(Proof & Value — CVI 04c)*           | `Proof_Points`          | **Prove we've done it**: Customer case studies, logo slides, quotes, Gartner/Forrester Magic Quadrants.
**Realization** *(How We Deliver — CVI 05)*      | `Commercials`           | **Talk pricing & investment**: Consumption models, packaging, Enterprise Discount Programs (EDP), SKUs.
**Realization** *(How We Deliver — CVI 05)*      | `Path_to_Prod`          | **Show next steps & timelines**: 30-60-90 day roadmaps, CAF stages, structured migration plans.

---

## 3. How Slide Job Shapes Content Generation & Transformation
When generating a new slide or polishing an existing slide (`TextTransformerWorkflow` / `SlideEngineeringAgent`), the **Slide Job** dictates the visual density, tone, and required content elements:

-   **`Navigation`**: Keep clean and uncluttered. Use clear section headers and brief executive takeaway bullets.
-   **`Market_Trends`**: Use quantitative external citations (e.g., Gartner, IDC, industry reports) and high-level macro drivers.
-   **`Current_State`**: Focus squarely on the customer's business challenges, top executive priorities, strategic growth goals, and operational roadblocks. Avoid low-level technical jargon or minutiae; frame bottlenecks in terms of business impact (e.g., time-to-market delays, customer churn, revenue loss).
-   **`Strategic_Partnership`**: Highlight Google's commitment as a strategic long-term partner for Enterprise & Strategic accounts. Articulate Google's trust principles ("your data is your data / IP", zero lock-in open ecosystem), joint roadmap co-innovation, executive sponsorship (Joint Steering Committee), and Alphabet-wide capabilities.
-   **`Why_Google_Cloud`**: Highlight Google's planetary scale,
    security-by-default, AI/ML leadership (`Gemini Enterprise`), and open-source
    commitments.
-   **`Solution_Overview`**: Present clear product capability pillars, UI mockups, and end-user benefits without dense code blocks.
-   **`Architecture`**: Include technical system diagrams, data ingestion-to-serving pipelines, security boundaries, and explicit product integrations.
-   **`Business_Value`**: Quantify financial metrics: Net Present Value (NPV), Total Cost of Ownership (TCO) savings, and payback periods (`<12–18 months`) for `@cfo-persona`.
-   **`Proof_Points`**: Highlight verified customer success metrics, anonymized or public logo references, and authoritative third-party analyst validation.
-   **`Commercials`**: Present structured consumption pricing, Committed Use Discount (CUD) tiers, and migration co-investment incentives.
-   **`Path_to_Prod`**: Show clear, phased milestones (30-60-90 days, Cloud Adoption Framework / CAF stages, PoC to Production).

---

## 4. Account Customization Intensity Governance (e.g., Account = "Nike")
When customizing an existing presentation deck or individual slide for a specific target account (e.g., "Nike", "Starbucks", "Ford"), the **Slide Job ENUM** dictates the **Customization Intensity (0% to 100%)** to prevent altering factual case studies or distorting core technical architectures:

Slide Job ENUM              | Customization Intensity | Throttling Tier | Mandatory Customization Behavior
:-------------------------- | :---------------------- | :-------------- | :-------------------------------
**`Proof_Points`**          | **0%** (None)           | `IMMUTABLE`     | **Do NOT customize customer references.** Factual case studies (e.g., Home Depot, Adidas, Walmart) must remain intact. Only add an executive transition sentence (e.g., *"How retail leaders achieve scale"*). Never replace third-party logos or quote attribution.
**`Why_Google_Cloud`**      | **15%** (Light)         | `LIGHT`         | **Preserve Google Cloud differentiators.** Keep core platform advantages (custom TPUs, global fiber, `Gemini Enterprise`, BeyondCorp) unchanged.
**`Architecture`**          | **25%** (Light-Mod)     | `LIGHT_MOD`     | **Preserve back-end blueprints.** Keep core services (`Pub/Sub`, `BigQuery`, `GKE`, `AlloyDB`) intact. Customize only edge ingestion labels (e.g., *"SNKRS App Telemetry"*) and downstream serving targets.
**`Solution_Overview`**     | **60%** (Moderate)      | `MODERATE`      | **Tailor product capabilities to customer use cases.** Highlight features relevant to Nike (e.g., Retail Search for sneaker drops, BigQuery Clean Rooms for loyalty data).
**`Commercials`**           | **15%** (Light)         | `LIGHT`         | **HITL Required for pricing & packaging.** Do NOT invent or alter discount percentages, Committed Use Discount (CUD) tiers, or Enterprise Discount Program (EDP) terms without Human-In-The-Loop (HITL) review. Keep standard consumption pricing structure intact.
**`Path_to_Prod`**          | **75%** (High)          | `HIGH`          | **Customize milestones & governance.** Map the 30-60-90 day CAF stages to the customer's internal engineering teams and planned launch dates.
**`Strategic_Partnership`** | **85%** (Heavy)         | `HEAVY`         | **Personalize joint vision & co-innovation.** Customize strategic initiatives, joint business goals, executive governance models, and Alphabet synergies to the account while preserving Google's core trust/openness principles.
**`Navigation`**            | **85%** (Heavy)         | `HEAVY`         | **Personalize deck structure.** Title slides, agendas, and executive summaries must explicitly reference the customer's brand, leadership, and partnership vision.
**`Market_Trends`**         | **90%** (Heavy)         | `HEAVY`         | **Align to customer's macro reality.** Cite retail/footwear-specific shifts (e.g., D2C digital commerce surge, sneaker drop traffic spikes, Scope 3 compliance).
**`Current_State`**         | **95%** (Heavy)         | `HEAVY`         | **Mirror exact customer business challenges & priorities.** Articulate the customer's specific strategic goals, growth initiatives, and organizational friction points identified during discovery.
**`Business_Value`**        | **100%** (Full)         | `FULL`          | **100% Account-Specific Financial Justification.** Quantify Net Present Value (NPV), TCO savings, and payback periods (`<12–18 months`) tied directly to `@cfo-persona` KPIs.

---

## 5. Persona & Maturity Alignment
To prevent serving highly complex technical diagrams to business executives, slide selection mandates audience and technical density mapping:

-   **Target Audience Array**: `CxO` (Executive strategy/finance), `BDM` (Line-of-business KPI focus), `TDM` (High-level system design), `Architect_Engineer` (Deep technical/code level).
-   **Technical Maturity**:
    -   `L100 (Conceptual)`: Abstract block diagrams, non-technical flows.
    -   `L200 (Strategic)`: Functional service mappings, mid-level architecture.
    -   `L300 (Deep Technical)`: Granular microservices, specific product boundaries.

---

## 5. Production JSON Schema (`GTM_Agentic_Slide_Metadata`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "GTM_Agentic_Slide_Metadata",
  "type": "object",
  "properties": {
    "slide_id": { "type": "string" },
    "slide_title": { "type": "string" },
    "deck_source_url": { "type": "string" },
    "slide_index": { "type": "integer" },
    "taxonomy": {
      "type": "object",
      "properties": {
        "slide_job": {
          "type": "string",
          "enum": [
            "Navigation", "Market_Trends", "Current_State", "Strategic_Partnership",
            "Why_Google_Cloud", "Solution_Overview", "Architecture",
            "Business_Value", "Proof_Points", "Commercials", "Path_to_Prod"
          ]
        },
        "cvi_cluster": {
          "type": "string",
          "enum": ["Connective Tissue", "Context", "Vision", "Solution", "Impact", "Realization"]
        },
        "target_audience": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["CxO", "BDM", "TDM", "Architect_Engineer"]
          }
        },
        "technical_maturity": {
          "type": "string",
          "enum": ["L100 (Conceptual)", "L200 (Strategic)", "L300 (Deep Technical)"]
        }
      },
      "required": ["slide_job", "cvi_cluster", "target_audience", "technical_maturity"]
    },
    "gtm_filters": {
      "type": "object",
      "properties": {
        "industry_verticals": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["FSI", "HCLS", "Retail", "Manufacturing", "Digital Native", "Media", "Telco", "Public Sector", "Cross-Industry"]
          }
        },
        "sales_stage_meddpicc": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["Discovery", "Validation", "Decision Process", "Closing"]
          }
        },
        "solution_pillars": {
          "type": "array",
          "items": { "type": "string" }
        },
        "featured_products": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },
    "governance": {
      "type": "object",
      "properties": {
        "is_customer_facing": {
          "type": "boolean",
          "description": "True if the slide is suitable for customer presentations; False if it is an internal sales coaching/enablement slide."
        },
        "confidentiality": {
          "type": "string",
          "enum": ["Public", "Google Confidential", "NDA Only", "Google Internal Only"]
        },
        "owner_ldap": { "type": "string" },
        "last_updated": { "type": "string", "format": "date" },
        "status": {
          "type": "string",
          "enum": ["Draft", "Approved", "Deprecated"]
        }
      },
      "required": ["is_customer_facing", "confidentiality", "status"]
    }
  },
  "required": ["slide_id", "taxonomy", "gtm_filters", "governance"]
}
```

---

## 6. Connection to Presentation Archetypes (`@presentation-archetypes`)

While the 11 Slide Jobs define **what each slide does**, the initial weighting,
density, and dynamic CVI phase allocation across these jobs are governed by the
**8 Canonical Cloud GTM Presentation Archetypes** (`@presentation-archetypes` /
[`presentation_archetypes/SKILL.md`](../presentation_archetypes/SKILL.md)):

1.  **`First_Call_Discovery`** *(alias: `Discovery_First_Call` — `S0:
    Qualify`)*: Heavy weighting on `Market_Trends`, `Current_State`, and
    `Strategic_Partnership` (`40% Context` / `20% Vision`).
2.  **`Executive_Vision_Briefing`** *(alias: `Executive_Vision_Strategic` —
    `S0–S1: Inspire / EBC`)*: Heavy weighting on `Strategic_Partnership`,
    `Market_Trends`, `Current_State`, and `Business_Value` (`L100`).
3.  **`Sales_Play_Business_Pitch`** *(alias: `Industry_Business_Pitch`,
    `General_Value_Pitch` — `S1: Position & Build`)*: Balanced weighting across
    `Current_State`, `Solution_Overview`, `Why_Google_Cloud`, `Business_Value`,
    and `Proof_Points` (`L100–L200`).
4.  **`Technical_Solutioning_Pitch`** *(alias: `CIO_Technical_Strategy`,
    `Technical_Architecture` — `S2: Tech Solutioning`)*: Compresses `Context` to
    1 slide and heavily weights `Architecture`, `Solution_Overview`, and
    `Why_Google_Cloud` (`L200`).
5.  **`Architecture_PoC_Workshop`** *(alias:
    `Practitioner_Technical_Architecture`, `PoC_Engagement_Proposal` — `S2: Tech
    Validation`)*: Heavy weighting on `Architecture`, `Solution_Overview`, and
    `Path_to_Prod` PoC execution (`L200–L300`).
6.  **`Value_Case_Commercial_Proposal`** *(alias: `CFO_Business_Case`,
    `Commercial_Proposal` — `S1–S3: Business Case & Propose`)*: Heavy weighting
    on `Business_Value`, `Commercials`, `Proof_Points`, and `Path_to_Prod`
    (`L100 Financial`).
7.  **`Competitive_Takeout_Migration`** *(`S1–S2: Displacement & Migration`)*:
    Heavy weighting on `Why_Google_Cloud`, `Business_Value` (TCO),
    `Architecture`, `Proof_Points`, and `Path_to_Prod` (`RaMP`).
8.  **`QBR_Adoption_Expansion`** *(alias: `Executive_QBR_Value_Realization`,
    `Customer_Adoption_Playbook` — `S4 & S0': Deliver & Grow`)*: Heavy weighting
    on `Business_Value` (realized impact), `Path_to_Prod` (90-day adoption),
    `Strategic_Partnership`, and `Solution_Overview` (next-wave expansion).
