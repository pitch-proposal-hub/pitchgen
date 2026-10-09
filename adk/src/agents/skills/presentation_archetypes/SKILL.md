---
name: presentation-archetypes
description: >-
  Defines the 8 authoritative Google Cloud GTM Presentation Archetypes across the WIN Cycle (S0-S4 & S0'),
  governing sales role ownership (FSR, Platform CE, Practice CE, Outcome CE, GCC/Partners), CloudHub BOM
  anchor asset mapping, dynamic 5-Cluster CVI phase allocation, slide job weighting profiles, and technical maturity limits.
---

# Cloud GTM Presentation Archetypes Specification & Slide Job Weighting Matrix

This skill defines the authoritative **8 Google Cloud Go-To-Market (GTM)
Presentation Archetypes**. Archetypes bridge sales opportunity context—**WIN
Cycle stage (`S0`–`S4` & `S0'`)**, **GTM Seller Role (`FSR`/`KAx`, `Platform
CE`, `Practice CE`, `Outcome CE`, `GCC`/`Partners`)**, **Target Buyer Persona
(`@executive-persona`)**, and **Account Segment (`@segment-targeting`)**—to
dynamic **5-Cluster CVI** outline generation and intent-driven **Slide Job
(`@slide-job`)** retrieval.

---

## 1. The 8 Canonical Cloud GTM Presentation Archetypes

\#    | Canonical Archetype ID                                                                                                                | WIN Cycle Stage                                                      | Lead & Support GTM Roles                                                               | Primary Target Audience                                        | CloudHub BOM Anchor Assets                                                                                           | Technical Maturity
:---- | :------------------------------------------------------------------------------------------------------------------------------------ | :------------------------------------------------------------------- | :------------------------------------------------------------------------------------- | :------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------- | :-----------------
**1** | **`First_Call_Discovery`**<br>*(alias: `Discovery_First_Call`)*                                                                       | **Stage 0 (`S0: Qualify`)**                                          | **Lead**: `FSR` / `KAx`<br>**Support**: `Platform CE`                                  | Line-of-Business (LOB) VPs, Directors, Digital/IT Leaders      | Customer Discovery Guide, Customer Maturity Framework, Industry First-Call Teaser                                    | `L100 (Conceptual)`
**2** | **`Executive_Vision_Briefing`**<br>*(aliases: `Executive_Vision_Strategic`, `Executive_Vision_Thought_Leadership`)*                   | **Stage 0–1 (`S0–S1: Inspire / Strategy`)**                          | **Lead**: `FSR` + Exec Sponsor<br>**Support**: `Platform CE`, Industry Leader          | CEO, Board, CDO, CMO, Executive Committee (EBC)                | *Why Google Cloud for `<Industry>`* Deck, Executive Briefing (EBC) Deck, One Google / Alphabet Co-Innovation         | `L100 (Conceptual)`
**3** | **`Sales_Play_Business_Pitch`**<br>*(aliases: `Industry_Business_Pitch`, `General_Value_Pitch`)*                                      | **Stage 1 (`S1: Position & Build`)**                                 | **Lead**: `FSR` + Sales Specialist<br>**Support**: `Platform CE`                       | LOB Buyers, BDM, CDO, CIO, VP Product/Ops                      | Official **L100 Sales Play Business Pitch Deck** + Industry Vertical Use-Case Playbook + Customer References         | `L100–L200`
**4** | **`Technical_Solutioning_Pitch`**<br>*(aliases: `CIO_Technical_Strategy`, `Technical_Architecture`)*                                  | **Stage 2 (`S2: Tech Solutioning`)**                                 | **Lead**: `Platform CE` / `Practice CE`<br>**Support**: `FSR`                          | CIO, CTO, VP Infrastructure, Head of Enterprise Architecture   | Official **L200 Sales Play Technical Pitch Deck**, IT Modernization & Multi-Cloud Governance Blueprint               | `L200 (Strategic)`
**5** | **`Architecture_PoC_Workshop`**<br>*(aliases: `Practitioner_Technical_Architecture`, `PoC_Engagement_Proposal`, `PoC_Results_Value`)* | **Stage 2 (`S2: Tech Validation & PoC`)**                            | **Lead**: `Practice CE` / `Platform CE`<br>**Support**: `GCC` / Partners               | Principal Architects, VP Engineering, Security/CISO, Dev Leads | **L300 Reference Architecture Deck**, VPC-SC / Security Deep-Dive, Demo Flow & PoC Scoping/Validation Charter        | `L200–L300 (Deep Technical)`
**6** | **`Value_Case_Commercial_Proposal`**<br>*(aliases: `CFO_Business_Case`, `Commercial_Proposal`)*                                       | **Stage 1–3 (`S1–S3: Business Case & Propose`)**                     | **Lead**: `FSR` + Value Creation / Deal Desk<br>**Support**: `Platform CE`, `GCC`      | CFO, VP Finance, Procurement, Sourcing, CIO                    | Executive ROI / TCO / NPV Business Case, Proactive Proposal Template, EDP / CUD Commercial Packaging                 | `L100 (Financial & Commercial)`
**7** | **`Competitive_Takeout_Migration`**                                                                                                   | **Stage 1–2 (`S1–S2: Displacement & Migration`)**                    | **Lead**: `FSR` + Specialist + `Practice CE`<br>**Support**: Migration Center / `RaMP` | CIO, CTO, CFO, VP Infrastructure & Data                        | Competitive Takeout Playbook (vs. AWS, Azure, Snowflake, Databricks, Oracle, SAP, VMware) + `RaMP` Migration Factory | `L100–L200`
**8** | **`QBR_Adoption_Expansion`**<br>*(aliases: `Executive_QBR_Value_Realization`, `Customer_Adoption_Playbook`)*                          | **Stage 4 & 0' (`S4: Mobilize & Deliver` / `S0': Optimize & Grow`)** | **Lead**: `Outcome CE` / `GCC` / `TAM` / `FSR`<br>**Support**: `Platform CE`, Partners | Executive Sponsors, Steering Committee, Cloud CoE, IT Ops      | Executive QBR Value Realized Scorecard, Consumption/Commitment Health, 30-60-90 CAF Adoption & Next-Wave Expansion   | `L100–L200`

---

## 2. Dynamic 5-Cluster CVI Phase Allocation by Archetype

Rather than forcing every presentation into a static 50/50 split between *Why
Change* and *Why Google Cloud*, each archetype dynamically allocates the deck's
slide budget across the **5 CVI Clusters** (`Context`, `Vision`, `Solution`,
`Impact`, `Realization`):

Canonical Archetype                     | 1. `Context` (*Why Change*)<br>`Market_Trends`, `Current_State` | 2. `Vision` (*Why Now*)<br>`Strategic_Partnership` | 3. `Solution` (*Why Google*)<br>`Why_Google_Cloud`, `Solution_Overview`, `Architecture` | 4. `Impact` (*Proof & Value*)<br>`Business_Value`, `Proof_Points` | 5. `Realization` (*How We Deliver*)<br>`Commercials`, `Path_to_Prod` | Typical 10-Slide Section Breakdown
:-------------------------------------- | :-------------------------------------------------------------: | :------------------------------------------------: | :-------------------------------------------------------------------------------------: | :---------------------------------------------------------------: | :------------------------------------------------------------------: | :---------------------------------
**1. `First_Call_Discovery`**           | **40%**                                                         | **20%**                                            | **20%**                                                                                 | **10%**                                                           | **10%**                                                              | `1 Nav` + `4 Context` + `2 Vision` + `1 Solution` + `1 Proof` + `1 Next Steps`
**2. `Executive_Vision_Briefing`**      | **25%**                                                         | **30%**                                            | **15%**                                                                                 | **20%**                                                           | **10%**                                                              | `1 Nav` + `2 Context` + `3 Vision` + `1 Solution` + `2 Impact` + `1 Next Steps`
**3. `Sales_Play_Business_Pitch`**      | **25%**                                                         | **15%**                                            | **25%**                                                                                 | **25%**                                                           | **10%**                                                              | `1 Nav` + `2 Context` + `1 Vision` + `3 Solution` + `2 Impact` + `1 Next Steps`
**4. `Technical_Solutioning_Pitch`**    | **10%** *(1 slide)*                                             | **10%**                                            | **50%**                                                                                 | **15%**                                                           | **15%**                                                              | `1 Nav` + `1 Context Recap` + `1 Vision` + `4 Solution/Arch` + `2 Proof` + `1 Roadmap`
**5. `Architecture_PoC_Workshop`**      | **10%** *(1 slide)*                                             | **5%**                                             | **55%**                                                                                 | **10%**                                                           | **20%**                                                              | `1 Nav` + `1 Technical Context` + `5 Deep Arch & Security` + `1 Benchmark Proof` + `2 PoC Plan`
**6. `Value_Case_Commercial_Proposal`** | **15%**                                                         | **10%**                                            | **10%**                                                                                 | **40%**                                                           | **25%**                                                              | `1 Nav` + `1 Cost of Inaction` + `1 Vision` + `1 Solution` + `4 ROI & Peer Proof` + `2 Commercials/Timeline`
**7. `Competitive_Takeout_Migration`**  | **20%** *(Legacy Debt)*                                         | **10%**                                            | **35%** *(Diff)*                                                                        | **20%** *(Peer Swaps)*                                            | **15%** *(RaMP)*                                                     | `1 Nav` + `2 Legacy Friction` + `3 Why Google & Coexistence Arch` + `2 Takeout Proof/TCO` + `2 RaMP Plan`
**8. `QBR_Adoption_Expansion`**         | **15%** *(Scorecard)*                                           | **20%** *(Next Wave)*                              | **20%** *(New Plays)*                                                                   | **25%** *(Realized ROI)*                                          | **20%** *(90-Day Plan)*                                              | `1 Nav` + `2 Realized Value & Health` + `2 Next-Wave Vision` + `2 New Solution Plays` + `1 Peer Proof` + `2 90-Day Charter`

--------------------------------------------------------------------------------

## 3. Archetype Slide Job Weighting Matrix (`0.0` to `1.0`)

When searching and re-ranking reusable slides in `RetrievalAgent`, the active
**Presentation Archetype** scales the importance of each of the **11 Canonical
Slide Jobs**. Both the **8 Canonical Cloud GTM Archetypes** and **Legacy Alias
Keys** are defined below for 100% backward compatibility:

```json
{
  "First_Call_Discovery": {
    "Market_Trends": 1.0,
    "Current_State": 1.0,
    "Strategic_Partnership": 0.7,
    "Why_Google_Cloud": 0.8,
    "Solution_Overview": 0.6,
    "Proof_Points": 0.7,
    "Business_Value": 0.4,
    "Architecture": 0.1,
    "Commercials": 0.0,
    "Path_to_Prod": 0.4,
    "Navigation": 0.8
  },
  "Executive_Vision_Briefing": {
    "Strategic_Partnership": 1.0,
    "Market_Trends": 0.9,
    "Current_State": 0.9,
    "Why_Google_Cloud": 0.8,
    "Business_Value": 0.8,
    "Proof_Points": 0.8,
    "Solution_Overview": 0.6,
    "Path_to_Prod": 0.6,
    "Architecture": 0.1,
    "Commercials": 0.1,
    "Navigation": 0.8
  },
  "Sales_Play_Business_Pitch": {
    "Current_State": 0.9,
    "Solution_Overview": 1.0,
    "Why_Google_Cloud": 0.8,
    "Business_Value": 0.9,
    "Proof_Points": 0.9,
    "Market_Trends": 0.8,
    "Strategic_Partnership": 0.7,
    "Path_to_Prod": 0.7,
    "Architecture": 0.4,
    "Commercials": 0.2,
    "Navigation": 0.8
  },
  "Technical_Solutioning_Pitch": {
    "Architecture": 1.0,
    "Solution_Overview": 0.9,
    "Why_Google_Cloud": 0.9,
    "Path_to_Prod": 0.8,
    "Proof_Points": 0.7,
    "Strategic_Partnership": 0.6,
    "Current_State": 0.6,
    "Business_Value": 0.5,
    "Market_Trends": 0.3,
    "Commercials": 0.2,
    "Navigation": 0.8
  },
  "Architecture_PoC_Workshop": {
    "Architecture": 1.0,
    "Path_to_Prod": 0.9,
    "Solution_Overview": 0.8,
    "Why_Google_Cloud": 0.8,
    "Proof_Points": 0.6,
    "Current_State": 0.5,
    "Business_Value": 0.3,
    "Strategic_Partnership": 0.3,
    "Market_Trends": 0.2,
    "Commercials": 0.1,
    "Navigation": 0.8
  },
  "Value_Case_Commercial_Proposal": {
    "Business_Value": 1.0,
    "Commercials": 0.95,
    "Proof_Points": 0.9,
    "Current_State": 0.8,
    "Path_to_Prod": 0.8,
    "Strategic_Partnership": 0.7,
    "Solution_Overview": 0.4,
    "Why_Google_Cloud": 0.4,
    "Market_Trends": 0.4,
    "Architecture": 0.1,
    "Navigation": 0.8
  },
  "Competitive_Takeout_Migration": {
    "Why_Google_Cloud": 1.0,
    "Business_Value": 0.95,
    "Proof_Points": 0.9,
    "Current_State": 0.85,
    "Architecture": 0.8,
    "Path_to_Prod": 0.85,
    "Solution_Overview": 0.75,
    "Commercials": 0.6,
    "Strategic_Partnership": 0.6,
    "Market_Trends": 0.5,
    "Navigation": 0.8
  },
  "QBR_Adoption_Expansion": {
    "Business_Value": 1.0,
    "Path_to_Prod": 0.95,
    "Strategic_Partnership": 0.9,
    "Solution_Overview": 0.85,
    "Current_State": 0.8,
    "Proof_Points": 0.75,
    "Why_Google_Cloud": 0.6,
    "Architecture": 0.5,
    "Commercials": 0.5,
    "Market_Trends": 0.4,
    "Navigation": 0.8
  },
  "Discovery_First_Call": {
    "Market_Trends": 1.0,
    "Current_State": 1.0,
    "Why_Google_Cloud": 0.8,
    "Solution_Overview": 0.6,
    "Proof_Points": 0.7,
    "Strategic_Partnership": 0.7,
    "Business_Value": 0.4,
    "Architecture": 0.1,
    "Commercials": 0.0,
    "Path_to_Prod": 0.4,
    "Navigation": 0.8
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
    "Market_Trends": 0.8,
    "Navigation": 0.8
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
    "Navigation": 0.8
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
    "Navigation": 0.8
  },
  "Technical_Architecture": {
    "Architecture": 1.0,
    "Solution_Overview": 0.9,
    "Why_Google_Cloud": 0.9,
    "Path_to_Prod": 0.8,
    "Proof_Points": 0.7,
    "Strategic_Partnership": 0.5,
    "Current_State": 0.6,
    "Business_Value": 0.4,
    "Market_Trends": 0.3,
    "Commercials": 0.1,
    "Navigation": 0.8
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
    "Navigation": 0.8
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
    "Navigation": 0.8
  },
  "PoC_Engagement_Proposal": {
    "Path_to_Prod": 1.0,
    "Solution_Overview": 0.9,
    "Architecture": 0.9,
    "Proof_Points": 0.7,
    "Current_State": 0.6,
    "Why_Google_Cloud": 0.6,
    "Business_Value": 0.4,
    "Strategic_Partnership": 0.4,
    "Commercials": 0.3,
    "Market_Trends": 0.2,
    "Navigation": 0.8
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
    "Navigation": 0.8
  },
  "Commercial_Proposal": {
    "Commercials": 1.0,
    "Path_to_Prod": 0.9,
    "Strategic_Partnership": 0.8,
    "Proof_Points": 0.7,
    "Business_Value": 0.8,
    "Current_State": 0.5,
    "Solution_Overview": 0.4,
    "Why_Google_Cloud": 0.4,
    "Architecture": 0.2,
    "Market_Trends": 0.2,
    "Navigation": 0.8
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
    "Navigation": 0.8
  }
}
```
