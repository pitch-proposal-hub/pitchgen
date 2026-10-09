---
name: use-case-context
description: >-
  Generates structured JSON content for use case related slides in the PitchGen ADK.
  Use when a user asks to create a slide for a specific use case, providing details
  from the Retail Use Cases repository.
---

# Use Case Context

## Overview

This skill helps the agent generate a structured JSON object containing use case
details, which is used by the PitchGen ADK to generate slides. It uses reference
data extracted from the Retail Use Cases repository.

## Target JSON Schema

The agent must produce a JSON object matching this structure:

```json
{
  "use_case_classification": {
    "description_and_problem_statement": "string",
    "industry_pillar": "string",
    "horizontal_plays": ["string"],
    "key_personas": ["string"]
  },
  "technical_details": {
    "customer_user_journeys": ["string"],
    "how_it_works_narrative": "string",
    "key_technologies": ["string"]
  },
  "value_points": {
    "google_proof_points": ["string"],
    "value_drivers": ["string"],
    "value_narrative": "string",
    "kpis": ["string"],
    "google_differentiation": "string"
  },
  "opportunity_sizing": {
    "estimated_revenue": "string",
    "estimated_acv": "string"
  },
  "delivery_and_deployment_options": {
    "preferred_partners": ["string"],
    "isvs": ["string"]
  }
}
```

## Guidelines for Generating JSON

1.  **Find the Use Case**: Locate the requested use case in the reference files
    listed below. They are grouped by Industry Pillar.
2.  **Map Fields**:
    *   Map comma-separated lists in the sheet to arrays in the JSON (e.g., `Key
        Technologies`, `KPIs`, `Preferred Partners`).
    *   Align `horizontal_plays` with the names defined in the
        `sales-play-selection` skill.
3.  **Incorporate User Context and Grounding**:
    *   If the user provides a specific customer name (e.g., Nike), the agent
        MUST perform a web search to identify recent news, earnings call
        statements, or articles regarding that customer's specific challenges or
        strategic focus areas related to the use case.
    *   Use this specific context to tailor the
        `description_and_problem_statement` and `customer_user_journeys` instead
        of just replacing generic terms with the customer name.
    *   The agent MAY customize the `value_narrative` to align with the target
        customer's goals found via search.
    *   The agent MAY prioritize specific `kpis` from the list. Do not add new
        metrics unless they are 100% clear to represent the same KPI listed in
        the reference files (e.g., using a customer-specific term for 'Customer
        Retention').
    *   All customizations MUST remain grounded in the themes and options
        provided in the reference files.

## Reference Files

Use case details are organized by industry in the following sections.

### Retail

Use case details are organized by industry pillar in these JSON files:

-   [Capture Unified and Agentic Commerce Growth](references/retail/capture_unified_and_agentic_commerce_grwoth.json)
-   [Create the Connected Store](references/retail/create_the_connected_store.json)
-   [Leverage AI to Transform Data into Value](references/retail/leverage_ai_to_transform_data_into_value.json)
-   [Drive Sustainable and Efficient Operations](references/retail/drive_sustainable_and_efficient_operations.json)

### Power & Energy

Use case details are organized by industry pillar in these JSON files:

-   [Plan Forecast & Model with enhanced data-driven tools (Strategic Foresight)](references/power_energy/strategic_foresight.json)
-   [Build and Operate secure resilient infrastructure more efficiently (Operational Excellence)](references/power_energy/operational_excellence.json)
-   [Enable a Secure and Scalable foundation to advance your AI journey (Robust Core)](references/power_energy/robust_core.json)

## Validation Checklist

Before producing the final JSON, the agent must verify: - [ ] Is the problem
statement tailored to the specific customer's known challenges or public
statements (if a customer was named)? - [ ] Are the `horizontal_plays` aligned
with the `sales-play-selection` skill? - [ ] Are comma-separated lists from
references converted to JSON arrays?

## Feedback Loops

If the generated JSON does not parse or is missing required fields: 1. Check the
target schema in this file. 2. Verify that all required fields are present. 3.
Regenerate the JSON.
