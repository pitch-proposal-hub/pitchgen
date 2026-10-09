# Enterprise GTM Playbook: FSI - Banking (Retail & Commercial Banking)

## 1. Industry Executive Summary & Macro Dynamics
Retail and commercial banks face intense pressure from digital challenger banks, rising interest rate volatility, strict regulatory capital requirements (Basel III/IV, DORA), and legacy mainframe technical debt. Executive priorities center on **core banking modernization**, **real-time fraud prevention**, **open banking API monetization**, and **conversational AI self-service**.

## 2. Google Cloud Competitive Differentiation
- **Mainframe & Core Banking Migration**: Proven reference architectures for re-platforming COBOL/CICS workloads and core engines (Temenos, Thought Machine, Mambu) to **GKE** and **Cloud Spanner** with zero downtime.
- **Superior Fraud & AML AI**: Purpose-built **Google Cloud AML AI** and **Gemini Enterprise Agent Platform** transaction monitoring models reduce false positives by up to 60% compared to legacy rules-based systems.
- **Sovereign & Controlled Cloud**: **Assured Workloads**, **Customer-Managed Encryption Keys (CMEK)**, and **VPC Service Controls** meet the strictest central bank residency and data sovereignty mandates.
- **Conversational Banking Leader**: **Gemini Enterprise** and **Contact Center AI (CCAI)** automate complex retail banking inquiries with high containment rates.

## 3. Executive Persona KPI Alignment (Cross-Skill: `@executive-persona`)
- **CFO (`@cfo-persona`)**:
  - *Primary KPIs*: Cost-to-income ratio, fraud loss write-offs, branch infrastructure OpEx reduction.
  - *Value Proposition*: Cutting AML compliance review costs by 40% while reducing cloud TCO through FinOps and Committed Use Discounts (CUDs).
- **CTO / Chief Architect (`@cto-persona`)**:
  - *Primary KPIs*: Five-nines (99.999%) core payment gateway availability, API TPS throughput, mainframe decommissioning.
  - *Value Proposition*: Multi-region active-active **Cloud Spanner** for ACID-compliant ledger transactions without sharding complexity.
- **CISO / Chief Risk Officer (`@ciso-persona`)**:
  - *Primary KPIs*: PCI-DSS compliance, DORA operational resilience, zero-trust network segmentation.
  - *Value Proposition*: **BeyondCorp Enterprise**, hardware-backed **Titan security chips**, and automated threat detection with **Security Command Center**.
- **CDO (`@cdo-persona`)**:
  - *Primary KPIs*: Data liquidity across retail/commercial silos, real-time credit scoring latency.
  - *Value Proposition*: **BigQuery** lakehouse with **Dataplex** end-to-end data lineage and governance.

## 4. Segment-Targeting Playbook (Cross-Skill: `@segment-targeting`)
- **Enterprise Accounts (Global Tier-1 Banks)**:
  - *Strategy*: Lead with mainframe co-investment, multi-year strategic AI partnerships, and regulatory-approved sovereign cloud enclaves (`https://your-sales-portal.example.com/catalog`).
- **Select Accounts (Regional Banks & Credit Unions)**:
  - *Strategy*: Pitch rapid-ROI pre-packaged solutions: CCAI virtual banking assistants and BigQuery ML credit risk scoring.
- **Digital Natives & FinTechs (Neobanks, Payment Processors)**:
  - *Strategy*: Emphasize sub-millisecond payment authorization on Spanner/AlloyDB and serverless elasticity on Cloud Run.

## 5. Enterprise Reference Architecture & High-Impact Use Cases
1. **Real-Time Payment Fraud & Anti-Money Laundering (AML)**:
   - *Architecture*: Payment stream ingestion via **Pub/Sub** -> **Dataflow** -> **BigQuery ML / Gemini Enterprise Agent Platform** -> sub-50ms fraud scoring API serving transaction block/allow verdicts.
2. **Conversational Wealth & Retail Banking Concierge**:
   - *Architecture*: **Gemini 3.6 Flash** and **Gemini Enterprise Agent Platform & Conversation** grounded on verified banking product disclosures and fee schedules via **Gemini Enterprise**.
3. **Core Payment Ledger on Cloud Spanner**:
   - *Architecture*: Multi-region **Cloud Spanner** deployment handling high-throughput ledger debits/credits with strict serializability and automatic failover.

## 6. Objection Handling & Risk Mitigation
- **Objection**: *"Central banking regulators (e.g., ECB, PRA, OCC) will not permit us to put core banking customer PII into public cloud."*
  - **Google Cloud Response**: Demonstrate **Google Cloud Assured Workloads** and **External Key Manager (EKM)**, proving that the bank retains sole cryptographic control of customer data and that Google administrators have zero access.
- **Objection**: *"Migrating our mainframe ledger is too risky; a single outage would cost millions in regulatory fines."*
  - **Google Cloud Response**: Propose an **event-driven Strangler Fig pattern**, streaming DB2/VSAM changes via **Datastream** into **Cloud Spanner** for shadow-read verification before cutting over transaction writes.
