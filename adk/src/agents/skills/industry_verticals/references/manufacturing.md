# Enterprise GTM Playbook: Manufacturing (Discrete, Process & Industrial)

## 1. Industry Executive Summary & Macro Dynamics
Industrial manufacturers face rising energy costs, supply chain bottlenecks, aging skilled labor workforces, and the challenge of modernizing Operational Technology (OT) on factory floors. Executive priorities center on **smart factory visual inspection**, **digital twins & IoT machine telemetry**, **worker safety & manual copilots**, and **OT/IT cybersecurity convergence**.

## 2. Google Cloud Competitive Differentiation
- **Superior Factory Edge Vision AI**: **Gemini Enterprise Agent Platform (Multimodal Vision)** and **GKE Edge** run visual inspection models directly on assembly lines to detect sub-millimeter defects in real time.
- **Planetary Machine IoT Telemetry**: **Pub/Sub** and **BigQuery** ingest sensor telemetry across global factories to simulate digital twins and predict equipment failure.
- **Worker Assistance & Manual Copilots**: **Gemini 3.6 Flash** and **Gemini Enterprise** ingest 500+ page machine repair manuals and schematics to guide shop-floor technicians.
- **Zero-Trust Industrial Security**: **BeyondCorp** and **Security Command Center** secure OT networks without disrupting production PLCs.

## 3. Executive Persona KPI Alignment (Cross-Skill: `@executive-persona`)
- **CTO / VP of Manufacturing Technology (`@cto-persona`)**:
  - *Primary KPIs*: Overall Equipment Effectiveness (OEE), unplanned downtime, factory edge compute reliability.
  - *Value Proposition*: Increasing OEE by 5–10% via predictive maintenance in BigQuery.
- **CFO (`@cfo-persona`)**:
  - *Primary KPIs*: Scrap and rework costs, warranty claims, factory CapEx.
  - *Value Proposition*: Cutting assembly line defect scrap costs by 25% using visual inspection AI.
- **Chief Supply Chain Officer (`@cdo-persona`)**:
  - *Primary KPIs*: Tier-1/2 part shortage alerts, production schedule adherence.
  - *Value Proposition*: Real-time material flow tracking on BigQuery.

## 4. Segment-Targeting Playbook (Cross-Skill: `@segment-targeting`)
- **Enterprise Accounts (Global Industrial & Automotive OEMs)**:
  - *Strategy*: Lead with enterprise-wide digital twin lakehouses, global factory edge GKE rollouts, and custom AI inspection labs (`https://your-sales-portal.example.com/catalog`).
- **Select Accounts (Mid-Market Component Manufacturers)**:
  - *Strategy*: Pitch turnkey defect inspection: drop-in visual quality inspection models.
- **Digital Natives (Industrial IoT & Robotics Startups)**:
  - *Strategy*: Emphasize high-throughput telemetry APIs on Pub/Sub and Cloud Run.

## 5. Enterprise Reference Architecture & High-Impact Use Cases
1. **Automated Factory Visual Inspection at the Edge**:
   - *Architecture*: Assembly line cameras -> **GKE Edge / Google Distributed Cloud Edge** -> **Gemini Enterprise Agent Platform (Multimodal Vision)** -> instant pass/fail defect routing.
2. **Shop-Floor Maintenance & Repair Copilot**:
   - *Architecture*: Technician voice/tablet query -> **Gemini Enterprise** searching technical manuals -> step-by-step repair guidance.

## 6. Objection Handling & Risk Mitigation
- **Objection**: *"Factory floor machines operate on closed OT networks; we cannot connect them directly to cloud."*
  - **Google Cloud Response**: Propose **Google Distributed Cloud Edge**, which deploys local Kubernetes compute on-premise inside the OT security perimeter, processing inspection AI locally and only syncing anonymized telemetry to Google Cloud.
