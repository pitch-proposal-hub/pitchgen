# Enterprise GTM Playbook: FSI - Insurance (P&C, Life, Health, Reinsurance)

## 1. Industry Executive Summary & Macro Dynamics
Insurance carriers face severe underwriting margin compression from climate change catastrophes, medical cost inflation, fraudulent claim rings, and legacy mainframe policy administration systems. Executive priorities center on **automated claims processing**, **multimodal underwriting AI**, **actuarial catastrophe modeling**, and **broker/agent conversational enablement**.

## 2. Google Cloud Competitive Differentiation
- **Multimodal Document & Image AI Leader**: **Gemini 3.6 Flash** and **Document AI** automatically ingest unstructured policy PDFs, handwritten medical records, and accident photos to adjudicate claims in seconds.
- **Geospatial & Climate Risk Superiority**: **Google Earth Engine** and **BigQuery GIS** provide insurers with planetary-scale satellite imagery and flood/fire risk modeling that competitors cannot match.
- **Unified Policy & Claims Lakehouse**: **BigQuery** unifies siloed policy administration, claims, and billing data for 360-degree customer risk scoring.
- **Sovereign & Compliant AI**: Strict HIPAA, GLBA, and NAIC compliance with **Assured Workloads** and zero customer data training without consent.

## 3. Executive Persona KPI Alignment (Cross-Skill: `@executive-persona`)
- **CFO (`@cfo-persona`)**:
  - *Primary KPIs*: Combined ratio, loss adjustment expense (LAE), claims payout leakage.
  - *Value Proposition*: Cutting claim adjudication administrative costs by 35% and reducing fraudulent claim leakage via BigQuery ML anomaly detection.
- **Chief Underwriting Officer / Actuarial VP (`@cdo-persona`)**:
  - *Primary KPIs*: Pricing accuracy, catastrophe modeling runtime, loss ratio.
  - *Value Proposition*: Combining Google Cloud satellite imagery with actuarial models in BigQuery to price weather and flood risk with hyperlocal precision.
- **CTO (`@cto-persona`)**:
  - *Primary KPIs*: Policy administration system (PAS) uptime, mainframe modernization velocity.
  - *Value Proposition*: API encapsulation around legacy PAS (Guidewire, Duck Creek) using **Apigee** and **GKE**.
- **CISO (`@ciso-persona`)**:
  - *Primary KPIs*: PHI/PII protection, regulatory compliance (NYDFS 500, GLBA).
  - *Value Proposition*: Encryption at rest/in transit, **Cloud Armor**, and automated compliance monitoring with **Security Command Center**.

## 4. Segment-Targeting Playbook (Cross-Skill: `@segment-targeting`)
- **Enterprise Accounts (Global P&C and Life Carriers)**:
  - *Strategy*: Lead with enterprise actuarial risk lakehouse on BigQuery, automated claims intake pipelines, and joint AI workshops (`https://your-sales-portal.example.com/catalog`).
- **Select Accounts (Regional Mutual Insurers, Specialty Lines)**:
  - *Strategy*: Pitch turnkey agent enablement: Gemini Enterprise broker search copilots across policy coverage manuals.
- **Digital Natives & InsurTechs (Digital P&C, Embedded Insurance)**:
  - *Strategy*: Emphasize API-driven quote/bind instant pricing on Cloud Run and AlloyDB.

## 5. Enterprise Reference Architecture & High-Impact Use Cases
1. **Multimodal Automated Claim Triage & Adjudication**:
   - *Architecture*: Policyholder mobile upload (photos/PDFs) -> **Cloud Storage** -> **Document AI + Gemini 3.6 Flash** -> extraction of damage extent and policy limits -> automated approval verdict in **BigQuery**.
2. **Geospatial Climate & Catastrophe Risk Modeling**:
   - *Architecture*: **Google Earth Engine** satellite imagery -> **BigQuery GIS** spatial join with policyholder address coordinates -> calculating flood/wildfire premium adjustments.
3. **Agent & Broker Coverage Copilot**:
   - *Architecture*: Ingesting thousands of policy underwriting guidelines into **Gemini Enterprise Agent Platform** -> **Gemini Enterprise** conversational interface answering broker exclusion questions instantly.

## 6. Objection Handling & Risk Mitigation
- **Objection**: *"We rely on legacy Guidewire/Duck Creek on-prem installations; cloud migration would take five years."*
  - **Google Cloud Response**: Propose **Guidewire/Duck Creek on Google Cloud (GCP Marketplace)** or a **Strangler Fig API pattern** using **Apigee** to build modern claims AI apps without replacing core policy engines upfront.
- **Objection**: *"AI cannot be trusted for insurance underwriting due to regulatory fairness and bias laws."*
  - **Google Cloud Response**: Show **Gemini Enterprise Agent Platform Model Monitoring and Explainable AI**, which provide transparent feature attribution and bias audit logs required by NAIC and state insurance regulators.
