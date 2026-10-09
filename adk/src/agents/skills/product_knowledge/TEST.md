# Product Knowledge Skill - Test Plan

## Prerequisites
- Read `SKILL.md` to understand the dynamic Developer Knowledge grounding protocol, canonical modernization hierarchy, and architecture fidelity guidelines.
- Ensure `DeveloperKnowledgeWorkflow` is configured and accessible via Google API Client.

---

## Test 1: Dynamic Developer Knowledge Grounding & Live Research
**Objective:** Verify that technical product queries dynamically trigger live documentation retrieval from the Developer Knowledge API rather than relying on frozen static knowledge.

**Verification Steps:**
1. Execute `DeveloperKnowledgeWorkflow.execute("Google Cloud Knowledge Catalog BigQuery Lakehouse")`.
2. Ensure the response returns verified, live documentation chunks from `cloud.google.com` (e.g. Gemini-powered context graph, universal business context, Lakehouse metadata).
3. Execute `DeveloperKnowledgeWorkflow.execute("Google Cloud AI Hypercomputer")`.
4. Ensure the response returns authoritative AI supercomputing infrastructure documentation.

---

## Test 2: Forward Product Modernization (Upgrading Legacy Names)
**Objective:** Verify that when slides contain deprecated or legacy product names, the model modernizes them forward to current canonical 2026 Google Cloud branding.

**Input Slide Shapes:**
* Shape 1: `"Dataplex Catalog"`
* Shape 2: `"AI Supercompute"`
* Shape 3: `"Duet AI"`

**Expected Transformed Output:**
* Shape 1 must modernize to **`"Knowledge Catalog"`** (or keep `"Knowledge Catalog"` if already modern).
* Shape 2 must modernize to **`"AI Hypercomputer"`**.
* Shape 3 must modernize to **`"Gemini Enterprise"`**.

---

## Test 3: Architecture Diagram & Blueprint Preservation
**Objective:** Verify that technical architecture diagrams and product tier maps preserve official product names and cloud boundaries without hallucinating fictional terms.

**Input Slide (Google's Agentic Data Cloud Architecture):**
* Title: `"Google's Agentic Data Cloud"`
* Tier 1: `"Agentic-First Experiences"` -> `["Agentic Development", "Gemini Enterprise"]`
* Tier 2: `"AI Powered Engines"` -> `["Analytical Systems", "Operational Databases", "Business Intelligence"]`
* Tier 3: `"Knowledge Catalog"`
* Tier 4: `"AI-Native, Borderless Lakehouse"` -> `["Google Cloud Storage", "AWS", "Azure", "On-Prem"]`
* Tier 5: `"AI Hypercomputer"`

**Verification Assertions:**
* Title remains `"Google's Agentic Data Cloud"` (NOT *"Federated Data Fabric"*).
* Tier 1 preserves `"Agentic Development"` and `"Gemini Enterprise"` (NOT *"Token Factory Layer"* or *"Vertex AI Garden"*).
* Tier 3 preserves `"Knowledge Catalog"` (NEVER downgraded to *"Dataplex Catalog"*).
* Tier 4 preserves `"Google Cloud Storage"`, `"AWS"`, `"Azure"`, `"On-Prem"`.
* Tier 5 preserves `"AI Hypercomputer"` (NOT *"AI Supercompute"*).

---

## Test 4: Anti-Downgrade & Anti-Hallucination Integrity
**Objective:** Verify that the model never hallucinates made-up portmanteaus or downgrades active products.

**Banned Hallucinations (Must NEVER appear in transformed slides):**
* ❌ `"Token Factory Layer"`
* ❌ `"ClickHouse BigQuery"`
* ❌ `"Looker Telemetry Hub"`
* ❌ `"Federated Data Fabric"`
* ❌ `"Vertex AI Garden"`
