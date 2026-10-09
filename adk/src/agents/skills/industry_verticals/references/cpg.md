# Enterprise GTM Playbook: Consumer Packaged Goods (CPG)

## 1. Industry Executive Summary & Macro Dynamics
Consumer Packaged Goods (CPG) brand manufacturers face volatile raw material costs, promotional trade spend inefficiency, supply chain fragmentation, and the imperative to build direct-to-consumer (D2C) relationships without alienating retail partners. Executive priorities center on **trade promotion optimization (TPO)**, **demand forecasting**, **agentic commerce**, and **sustainable ingredient lineage**.

## 2. Google Cloud Competitive Differentiation
- **Superior Trade Promotion & Demand AI**: **BigQuery ML** and **Gemini Enterprise Agent Platform** time-series forecasting predict demand spikes from promotions and weather, improving forecast accuracy by 15–25%.
- **Agentic Commerce & D2C Copilots**: **Gemini 3.6 Flash** and **Gemini Enterprise Agent Platform (Retail Search)** power conversational product discovery and recipe assistants across brand websites.
- **Supply Chain & Sustainability Lineage**: **Google Earth Engine** and **BigQuery** trace agricultural sourcing (cocoa, palm oil, coffee) to prove Scope 3 carbon compliance and deforestation-free provenance.
- **CPG-Retailer Data Clean Rooms**: **BigQuery Data Clean Rooms** enable CPG brands to collaborate securely with grocery and retail partners on loyalty and ad attribution without exposing PII.

## 3. Executive Persona KPI Alignment (Cross-Skill: `@executive-persona`)
- **CFO (`@cfo-persona`)**:
  - *Primary KPIs*: Trade promotion spend ROI, inventory stockout cost, COGS inflation.
  - *Value Proposition*: Unlocking 5–10% improvement in trade promotion spend efficiency through AI modeling in BigQuery.
- **CMO / Chief Brand Officer (`@cmo-persona`)**:
  - *Primary KPIs*: Brand equity, D2C conversion rate, clean-room ad attribution.
  - *Value Proposition*: Accelerating localized ad creative and packaging imagery generation using **Gemini** and **Imagen 3**.
- **Chief Supply Chain Officer (`@cdo-persona`)**:
  - *Primary KPIs*: On-time-in-full (OTIF) delivery, supplier Scope 3 carbon transparency.
  - *Value Proposition*: End-to-end multi-tier supplier visibility on BigQuery.

## 4. Segment-Targeting Playbook (Cross-Skill: `@segment-targeting`)
- **Enterprise Accounts (Global Top-50 CPG Conglomerates)**:
  - *Strategy*: Pitch global trade promotion lakehouses, multi-year SAP-on-Google Cloud modernization, and joint marketing AI hubs (`https://your-sales-portal.example.com/catalog`).
- **Select Accounts (Mid-Market CPG & Food Brands)**:
  - *Strategy*: Lead with turnkey D2C conversion boosters: conversational recipe copilots and BigQuery ML forecasting.
- **Digital Natives (D2C Sustainable & Challenger Brands)**:
  - *Strategy*: Emphasize agile social commerce APIs on Cloud Run and real-time customer lifetime value (LTV) modeling.

## 5. Enterprise Reference Architecture & High-Impact Use Cases
1. **Trade Promotion Optimization (TPO) Lakehouse**:
   - *Architecture*: Retailer scanner POS data + promotional calendars -> **BigQuery** -> **Gemini Enterprise Agent Platform** regression models predicting optimal discount depth per product SKU.
2. **Deforestation & Scope 3 Ingredient Traceability**:
   - *Architecture*: Supplier GPS farm coordinates -> **Google Earth Engine** satellite deforestation check -> verified sustainability badge stored in **BigQuery**.

## 6. Objection Handling & Risk Mitigation
- **Objection**: *"Our retail partners (Walmart, Target) own the shopper POS data; we cannot build accurate demand models without it."*
  - **Google Cloud Response**: Show how **BigQuery Data Clean Rooms** enable major retailers to share anonymized POS scanner sales with CPG suppliers in a privacy-safe, zero-copy environment.
