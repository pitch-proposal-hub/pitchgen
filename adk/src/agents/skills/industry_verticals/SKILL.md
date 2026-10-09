---
name: industry-verticals
description: >-
  Provides Google Cloud GTM sales enablement guidelines across industry verticals and sub-industries
  (FSI, Healthcare, Retail, Media, Manufacturing, Public Sector, Gaming, etc.).
  Directly connected with use_case_context (@use-case-context) to structure use case slides and JSON payloads.
---

# Industry Verticals & Sub-Industries GTM Guidelines

Use this skill when tailoring presentations, Executive Briefings, or use-case messaging for a specific industry or sub-industry.

## Core Vertical Rules

- Always use authoritative industry terminology and regulatory compliance frameworks (e.g., PCI-DSS, HIPAA, FedRAMP, DORA).
-   Frame Google Cloud solutions around the vertical's highest-priority business
    outcomes and industry-specific AI solutions on Gemini Enterprise (e.g.,
    MedLM, AML AI, Gemini Enterprise for Customer Experience, Retail Search).
-   Ensure 100% technical and solution alignment with `product_knowledge`
    (`Enterprise-Brand-Unification`) and the Developer Knowledge API. Always reference
    current active solutions (`Gemini Enterprise` as one product, `Antigravity`,
    `Agent Studio`, `Model Garden`, `Gemini Code Assist`); NEVER reference
    legacy or retired terms (`Vertex AI`, `Gemini Enterprise Agent Platform`,
    `GEAP`, `Gemini Enterprise app`, `Gemini 1.0`, `Gemini 1.5 Pro`).
- Check the relevant sub-reference file in `references/` for granular sub-industry KPIs and reference architectures.
- When structuring use case slides or generating structured JSON for specific industry plays, couple with `use_case_context` (`@use-case-context`) to map Section 5 (*Enterprise Reference Architecture & High-Impact Use Cases*) into the authoritative `use_case_classification`, `technical_details`, and `value_points` JSON schema.
