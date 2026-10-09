---
name: cvi-framework
description: >-
  Guides the generation of content following the Customer Value Imperative (CVI) framework.
  Structures sales narratives across the 5-Cluster CVI Spine (Context, Vision, Solution, Impact, Realization)
  mapped 1:1 to the 11 Slide Jobs and dynamically calibrated across the 8 Cloud GTM Presentation Archetypes (WIN Cycle S0-S4 & S0').
---

# Customer Value Imperative (CVI) Framework Skill

This skill guides the generation of consultative, outcome-first sales narratives
following the **Customer Value Imperative (CVI)** framework. It bridges the two
foundational acts of executive persuasion (**Part 1: Why Change?** and **Part 2:
Why Google Cloud & How We Deliver?**) into a **5-Cluster CVI Narrative Spine**
mapped 1:1 to the **11 Canonical Slide Jobs** (`@slide-job`) and dynamically
weighted by the **8 Cloud GTM Presentation Archetypes**
(`@presentation-archetypes`).

--------------------------------------------------------------------------------

## 1. The 5-Cluster CVI Spine & 11 Slide Job Mapping

Every Google Cloud presentation follows the CVI narrative order so commercial
urgency is established before introducing product capabilities or technical
architecture:

CVI Act                                                     | CVI Cluster          | CVI Step                                                                         | Canonical Slide Job ENUMs (`@slide-job`)                    | Core Persuasion Question Answered
:---------------------------------------------------------- | :------------------- | :------------------------------------------------------------------------------- | :---------------------------------------------------------- | :--------------------------------
**Connective Tissue**                                       | `Connective Tissue`  | **00 Framing**                                                                   | `Navigation`                                                | *"What is our executive thesis and agenda for today?"*
**Part 1: Why Change?** *(Defeat the Status Quo)*           | **1. `Context`**     | **01 Current State & Problem Awareness**<br>**02 Implication & Business Impact** | `Market_Trends`<br>`Current_State`                          | *"What macro industry shifts and internal operational bottlenecks make the status quo untenable, and what is the cost of inaction?"*
**Part 1 $\rightarrow$ 2 Bridge: Why Now?**                 | **2. `Vision`**      | **03 Future State & Strategic Partnership**                                      | `Strategic_Partnership`                                     | *"How should the customer rethink the problem, and what does a co-innovated future state and strategic partnership look like?"*
**Part 2: Why Google Cloud?** *(Differentiate & Prove)*     | **3. `Solution`**    | **04a The Solution**<br>**04b Technical Differentiation**                        | `Why_Google_Cloud`<br>`Solution_Overview`<br>`Architecture` | *"How does Google Cloud and Gemini Enterprise uniquely solve this problem across front-end capabilities, differentiated platform strengths, and reference architecture?"*
**Part 2: Why Google Cloud?** *(Validate Value)*            | **4. `Impact`**      | **04c Quantified Value & Peer Proof**                                            | `Business_Value`<br>`Proof_Points`                          | *"What measurable ROI/TCO impact will the customer realize, and where has Google Cloud proven this with industry peers?"*
**Part 2 Extension: How We Deliver?** *(De-Risk Execution)* | **5. `Realization`** | **05 Commercials & Path to Production**                                          | `Commercials`<br>`Path_to_Prod`                             | *"How do we structure the investment (EDP/CUDs) and execute a de-risked 30-60-90 day path to production?"*

--------------------------------------------------------------------------------

## 2. Deep-Dive: CVI Steps & Persuasion Mechanics

### Part 1: Why Change? (`Context` & `Vision`)

Your first job isn't to convince prospects to choose Google Cloud over a
competitor—it is to persuade them that **remaining in the status quo is their
highest risk** (over 40% of enterprise B2B deals end in *"No Decision"*).

#### 01 Current State & Problem Awareness (`Market_Trends`, `Current_State`)

-   **Goal**: Establish macro industry context and mirror the customer's exact
    strategic priorities and operational bottlenecks.
-   **Questions to Address**:
    -   **Trends & External Pressures (`Market_Trends`)**: What industry shifts,
        competitive disruptions, or regulatory mandates are putting pressure on
        the customer's board-level goals?
    -   **Flawed Approach / Status Quo Friction (`Current_State`)**: How is the
        customer responding today, and why is their legacy approach creating
        technical debt, data silos, or slow time-to-market?
    -   **Unconsidered Needs**: What critical risk or opportunity has the
        customer underappreciated?

#### 02 Implication & Business Impact (`Current_State`)

-   **Goal**: Elevate technical or operational friction into a critical C-suite
    business driver.
-   **Questions to Address**:
    -   **Cost of Inaction**: What happens to revenue growth, operating margin,
        customer retention, or security posture over the next 12–24 months if
        they stay on their current trajectory?

#### 03 Future State & Desired Outcomes (`Strategic_Partnership`)

-   **Goal**: Articulate a compelling North Star vision before pitching
    individual SKUs.
-   **Questions to Address**:
    -   **New Thinking**: How *should* leadership reframe their problem (e.g.,
        shifting from isolated chatbots to an governed agentic enterprise)?
    -   **Strategic Co-Innovation**: How does a long-term partnership with
        Google (trust principles, *"your data is your IP"*, open cloud, One
        Google / Alphabet ecosystem synergies, Joint Steering Committee) de-risk
        their transformation?

--------------------------------------------------------------------------------

### Part 2: Why Google Cloud & How We Deliver? (`Solution`, `Impact`, `Realization`)

Once the case for change is established, connect Google Cloud's capabilities
directly to the customer's business outcomes, prove it with verified peer
references, and lay out an executable path forward.

#### 04a & 04b The Solution, Differentiation & Architecture (`Why_Google_Cloud`, `Solution_Overview`, `Architecture`)

-   **Connect Solution to Problem (`Solution_Overview`)**:
    -   **Customer Challenge**: *"A challenge we consistently see across
        [Industry] leaders is..."*
    -   **Do Statement**: *"What if your teams could..."* (focus on 3
        high-impact capabilities).
-   **Differentiate Why Google Cloud (`Why_Google_Cloud`)**:
    -   **Means Statement**: *"Which means your organization achieves..."*
    -   **Is Statement**: *"And this is uniquely enabled by Google Cloud
        through..."* (planetary infrastructure, custom TPUs, `Gemini Enterprise`
        as one unified product: *clients, agent, tools, governance*, BigQuery
        zero-ETL openness, security-by-default).
-   **Prove Technical Viability (`Architecture`)**:
    -   Show the concrete end-to-end reference blueprint, data/agent flows,
        security boundaries (VPC Service Controls, IAM, Model Armor), and
        brownfield coexistence with existing clouds.

#### 04c Quantified Business Value & Customer Proof (`Business_Value`, `Proof_Points`)

-   **Financial Justification (`Business_Value`)**:
    -   Quantify TCO reduction, revenue uplift, developer productivity gains,
        NPV, and payback period (`<12–18 months`) aligned to
        `@executive-persona` (especially CFO/CEO/CIO).
-   **Verified Customer Proof (`Proof_Points`)**:
    -   Anchor claims with `0% IMMUTABLE` verified customer case studies
        (`Before` challenge $\rightarrow$ `After` capability $\rightarrow$
        quantified `Impact`) and third-party analyst validation (Gartner,
        Forrester, IDC).

#### 05 Commercials & Path to Production (`Commercials`, `Path_to_Prod`)

-   **Commercial Packaging (`Commercials`)**:
    -   Present transparent consumption economics, Enterprise Discount Program
        (EDP) / Committed Use Discount (CUD) structures, and migration
        incentives (`RaMP`).
-   **Executable Roadmap (`Path_to_Prod`)**:
    -   Define a concrete 30-60-90 day Mutual Action Plan, PoC success criteria,
        Cloud Adoption Framework (CAF) workstreams, and partner/PSO delivery
        governance.

--------------------------------------------------------------------------------

## 3. Dynamic CVI Phase Allocation Across the WIN Cycle (`@presentation-archetypes`)

> [!IMPORTANT] **Resolving the "Why Change = Business / Why Google = Technical"
> Myth**: Every sales presentation—whether an `S0` discovery teaser, an `S2`
> deep architecture workshop, or an `S3` CFO business case—uses the CVI spine.
> However, **you should never use a rigid 50/50 split on every deck**. As a deal
> advances from `S0` to `S4`, the customer has *already bought into "Why
> Change"*, so the CVI phase allocation shifts dynamically from left (`Context`
> & `Vision`) to right (`Solution`, `Impact`, & `Realization`):

Cloud GTM Presentation Archetype        | WIN Cycle Stage                  | 1. `Context` (*Why Change*)  | 2. `Vision` (*Why Now*) | 3. `Solution` (*Why Google*) | 4. `Impact` (*Proof & ROI*) | 5. `Realization` (*How We Deliver*)
:-------------------------------------- | :------------------------------- | :--------------------------: | :---------------------: | :--------------------------: | :-------------------------: | :---------------------------------:
**1. `First_Call_Discovery`**           | `S0: Qualify`                    | **40%**                      | **20%**                 | **20%**                      | **10%**                     | **10%**
**2. `Executive_Vision_Briefing`**      | `S0–S1: Inspire / EBC`           | **25%**                      | **30%**                 | **15%**                      | **20%**                     | **10%**
**3. `Sales_Play_Business_Pitch`**      | `S1: Position & Build`           | **25%**                      | **15%**                 | **25%**                      | **25%**                     | **10%**
**4. `Technical_Solutioning_Pitch`**    | `S2: Tech Solutioning`           | **10%** *(1 slide recap)*    | **10%**                 | **50%**                      | **15%**                     | **15%**
**5. `Architecture_PoC_Workshop`**      | `S2: Tech Validation`            | **10%** *(1 slide recap)*    | **5%**                  | **55%**                      | **10%**                     | **20%** *(PoC Plan)*
**6. `Value_Case_Commercial_Proposal`** | `S1–S3: Business Case & Propose` | **15%** *(Cost of Inaction)* | **10%**                 | **10%**                      | **40%** *(ROI/TCO)*         | **25%** *(Commercials)*
**7. `Competitive_Takeout_Migration`**  | `S1–S2: Displacement`            | **20%** *(Legacy Debt)*      | **10%**                 | **35%** *(Diff)*             | **20%** *(Peer Swaps)*      | **15%** *(RaMP Plan)*
**8. `QBR_Adoption_Expansion`**         | `S4 & S0': Deliver & Grow`       | **15%** *(Scorecard)*        | **20%** *(Next Wave)*   | **20%** *(New Plays)*        | **25%** *(Value Realized)*  | **20%** *(90-Day Plan)*

--------------------------------------------------------------------------------

## 4. Governance & Gotchas

1.  **Do Not Mix "Why Change" and "Why Google" on the Same Slide**:
    -   Keep `Context` slides (`Market_Trends`, `Current_State`) focused 100% on
        the customer's industry and business problem without prematurely
        pitching Google Cloud SKUs.
2.  **Never Compress `Context` to Zero in Late-Stage Decks**:
    -   Even in an `S2` `Architecture_PoC_Workshop` or `S3`
        `Value_Case_Commercial_Proposal`, always open with **1 concise
        `Current_State` / Executive Thesis slide** that anchors the technical
        blueprint or financial model back to the customer's agreed-upon business
        problem.
3.  **Never Take Partnership For Granted (Proposition-Based Framing)**:
    -   Never write presumptive headlines such as *"Why [Customer] Chooses
        Google Cloud"* or *"Why [Customer] Partners with Google Cloud"*.
    -   Always use consultative, proposition-based framing: *"Why [Customer]
        Should Partner with Google Cloud"*, *"Why Google Cloud for [Customer]"*,
        *"The Value of Partnering with Google Cloud"*, or *"Co-Innovating with
        Google Cloud"*.
