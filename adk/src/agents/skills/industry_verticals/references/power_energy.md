# Enterprise GTM Playbook: Power & Energy (Utilities, Oil & Gas, Renewables)

## 1. Industry Executive Summary & Macro Dynamics
Power and energy organizations face the dual challenge of decarbonizing grid infrastructure while managing renewable energy intermittency, aging transmission assets, and volatile global commodity prices. Executive priorities center on **smart grid IoT balancing**, **subsurface seismic HPC analytics**, **drone-based asset visual inspection**, and **carbon emissions reporting**.

## 2. Google Cloud Competitive Differentiation
- **Planetary Geospatial & Environmental Leader**: **Google Earth Engine** and **BigQuery GIS** provide energy companies with satellite imagery and climate modeling to assess renewable site feasibility (solar/wind) and pipeline vegetation risks.
- **Superior Subsurface HPC**: Private global fiber networks and NVIDIA GPUs on **Google Cloud HPC** execute massive seismic inversion and reservoir simulations up to 3x faster than on-prem clusters.
- **Grid Telemetry & DER Analytics**: **Pub/Sub** and **BigQuery** ingest smart meter and Distributed Energy Resource (DER) sensor streams to forecast load demand in real time.
- **Drone Asset Vision**: **Gemini Enterprise Agent Platform (Multimodal Vision)** automatically inspects drone video of transmission towers, wind blades, and pipelines for structural cracks.

## 3. Executive Persona KPI Alignment (Cross-Skill: `@executive-persona`)
- **CTO / VP of Grid Modernization (`@cto-persona`)**:
  - *Primary KPIs*: Grid load forecasting accuracy, outage MTTR, smart meter ingestion latency.
  - *Value Proposition*: Multi-region active-active **Cloud Spanner** for utility customer billing and real-time DER management.
- **CFO (`@cfo-persona`)**:
  - *Primary KPIs*: Subsurface exploration HPC CapEx, transmission asset inspection cost.
  - *Value Proposition*: Reducing pipeline and power-line helicopter physical inspection costs by 50% via automated drone AI.
- **Chief Sustainability Officer (`@cdo-persona`)**:
  - *Primary KPIs*: Methane leak detection speed, Scope 1/2 carbon audit compliance.
  - *Value Proposition*: Earth Engine satellite methane tracking.

## 4. Segment-Targeting Playbook (Cross-Skill: `@segment-targeting`)
- **Enterprise Accounts (Global Energy Supermajors, National Electric Utilities)**:
  - *Strategy*: Lead with enterprise subsurface HPC grids, multi-year smart meter lakehouses, and joint climate AI labs (`https://your-sales-portal.example.com/catalog`).
- **Select Accounts (Regional Electric/Gas Utilities, Renewable Developers)**:
  - *Strategy*: Pitch turnkey drone visual inspection and BigQuery ML load forecasting.
- **Digital Natives (CleanTech Startups, Virtual Power Plants - VPPs)**:
  - *Strategy*: Emphasize real-time bidding and DER optimization APIs on Cloud Run.

## 5. Enterprise Reference Architecture & High-Impact Use Cases
1. **Smart Grid & Renewable Energy Intermittency Balancing**:
   - *Architecture*: Smart meter telemetry + weather forecasts -> **Pub/Sub** -> **BigQuery ML** -> predicting solar/wind output drops to trigger battery storage dispatch.
2. **Automated Power-Line Drone Visual Inspection**:
   - *Architecture*: Inspection drone footage -> **Cloud Storage** -> **Gemini Enterprise Agent Platform (Multimodal Vision)** -> identifying insulator corrosion or vegetation encroachment.

## 6. Objection Handling & Risk Mitigation
- **Objection**: *"Public utility commissions (PUCs) regulate our IT spending; cloud OpEx cannot be capitalized into our rate base."*
  - **Google Cloud Response**: Collaborate with regulatory affairs teams to show how **Google Cloud regulatory accounting models** allow utilities to capitalize software-as-a-service and cloud implementation expenditures under FERC/state PUC guidelines.
