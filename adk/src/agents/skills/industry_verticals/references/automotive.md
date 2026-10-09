# Enterprise GTM Playbook: Automotive & Mobility

## 1. Industry Executive Summary & Macro Dynamics
The automotive industry is undergoing a structural shift toward the **Software-Defined Vehicle (SDV)**, connected electric vehicles (EVs), autonomous driving (ADAS), and smart manufacturing. Executive priorities center on **vehicle telemetry ingestion**, **OTA software platform velocity**, **factory visual inspection**, and **in-cabin conversational AI**.

## 2. Google Cloud Competitive Differentiation
- **Android Automotive & Google Ecosystem**: Seamless synergy with Google Maps Platform, Android Automotive OS, and Google Assistant/Gemini for in-cabin infotainment.
- **Unrivaled AI Platform for Autonomous Perception**: **Gemini Enterprise Agent Platform** and Google Cloud TPUs provide the most cost-effective training infrastructure for multi-camera perception and autonomous driving models.
- **Planetary Vehicle IoT Telemetry**: **BigQuery** and **Pub/Sub** ingest millions of connected vehicle telemetry streams per second for real-time diagnostic alerts and predictive maintenance.
- **Smart Factory Vision**: **Gemini Enterprise Agent Platform (Multimodal Vision)** detects assembly line paint and weld defects at edge compute nodes.

## 3. Executive Persona KPI Alignment (Cross-Skill: `@executive-persona`)
- **CTO / Head of SDV Engineering (`@cto-persona`)**:
  - *Primary KPIs*: OTA update deployment frequency, in-vehicle software reliability, ADAS training compute cost.
  - *Value Proposition*: Cutting autonomous driving perception training compute costs by 35% on Cloud TPUs and GKE.
- **CFO (`@cfo-persona`)**:
  - *Primary KPIs*: Warranty claim costs, assembly line defect scrap rate.
  - *Value Proposition*: Reducing warranty recall expenses via predictive telemetry analysis in BigQuery.
- **Chief Supply Chain Officer (`@cdo-persona`)**:
  - *Primary KPIs*: Tier-1 supplier part visibility, JIT inventory accuracy.
  - *Value Proposition*: Supply chain data clean rooms on BigQuery.

## 4. Segment-Targeting Playbook (Cross-Skill: `@segment-targeting`)
- **Enterprise Accounts (Global Automotive OEMs)**:
  - *Strategy*: Lead with Software-Defined Vehicle (SDV) cloud platforms, multi-year TPU AI partnerships, and factory edge modernization (`https://your-sales-portal.example.com/catalog`).
- **Select Accounts (Tier-1 Auto Suppliers, Fleet Operators)**:
  - *Strategy*: Pitch turnkey predictive fleet maintenance and quality inspection.
- **Digital Natives (EV Startups, Autonomous Tech Companies)**:
  - *Strategy*: Emphasize raw TPU ML cluster scaling and serverless IoT backend microservices.

## 5. Enterprise Reference Architecture & High-Impact Use Cases
1. **Connected Vehicle Telemetry & Predictive Maintenance**:
   - *Architecture*: Vehicle CAN-bus / MQTT -> **Pub/Sub** -> **Dataflow** -> **BigQuery** -> **Gemini Enterprise Agent Platform** predicting component wear before roadside breakdown.
2. **In-Cabin Multimodal Conversational Assistant**:
   - *Architecture*: **Gemini 3.6 Flash** and **Gemini Enterprise** powering natural-language vehicle manual queries and navigation assistance.

## 6. Objection Handling & Risk Mitigation
- **Objection**: *"We have our own proprietary in-vehicle OS; we cannot use Google's consumer stack."*
  - **Google Cloud Response**: Clarify that **Google Cloud SDV infrastructure** (GKE, Pub/Sub, BigQuery, Gemini Enterprise Agent Platform) is OS-agnostic and supports Linux, QNX, AUTOSAR, and custom vehicle architectures.
