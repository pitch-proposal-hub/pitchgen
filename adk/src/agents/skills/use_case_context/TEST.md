# Use Case Context Skill - Test Plan

## Prerequisites

-   Read `SKILL.md` to understand target JSON schema.
-   Ensure reference files are present in `references/` directory.

--------------------------------------------------------------------------------

## Test 1: Generate JSON for Conversational Commerce

**Prompt:** "Create a slide for the 'Conversational Commerce' use case. Use the
`use-case-context` skill to guide you."

**Verify:**

-   The agent produces a valid JSON object matching the target schema.
-   The JSON contains data specific to 'Conversational Commerce' extracted from
    `references/capture_unified_and_agentic_commerce_growth.md`.
-   The `horizontal_plays` array contains relevant sales plays aligned with the
    `sales-play-selection` skill.

--------------------------------------------------------------------------------

## Test 2: Generate JSON with User Context

**Prompt:** "Create a slide for 'Autonomous Shopping Agents' for customer 'Acme
Corp' targeting 'VPs of E-commerce'. Use the `use-case-context` skill to guide
you."

**Verify:**

-   The agent produces a valid JSON object matching the target schema.
-   The JSON integrates 'Acme Corp' and 'VPs of E-commerce' into the generated
    content (e.g., in narratives or descriptions).

--------------------------------------------------------------------------------

## Test 3: Generate JSON for Different Pillar

**Prompt:** "Create a slide for the 'Trend Analysis' use case. Use the
`use-case-context` skill to guide you."

**Verify:**

-   The agent finds the use case in
    `references/leverage_ai_to_transform_data_into_value.md`.
-   The agent produces a valid JSON object matching the target schema.
