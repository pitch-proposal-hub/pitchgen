---
name: pitch-deck-qa
description: Executes comprehensive Quality Assurance (QA) audits and autonomous self-healing remediation for both newly generated Google Slides pitch decks (16-Gate Deck Perfection Inspector G01-G16) and transformed/localized presentations (10-Gate Deck Transformation Inspector T01-T10 + 4-Quadrant Active Vision Audit V01-V05). Enforces the 5-Cluster CVI Spine, 8 Cloud GTM Presentation Archetypes, and 11-Slide-Job Body Content Customization Intensity & Multi-Source Content Augmentation rules. Use whenever reviewing, auditing, validating, or self-healing outputs from any of the 8 PitchGen workflows (generate_pitch, search_slide, generate_slide, transform_slide, transform_text, translate, generate_nanobanana, transform_nanobanana) prior to surfacing the final presentation in the Google Slides Canvas.
metadata:
  owner: pitchgen-team
  version: "2.2"
  sales_agent_compatible: "true"
  supported_qa_modes:
    - "generated_deck_qa"
    - "deck_transformation_qa"
    - "body_content_customization_intensity_qa"
    - "smart_hybrid_reusable_recall_qa"
    - "side_panel_post_deck_qa"
    - "visual_4_quadrant_qa"
    - "translation_qa"
  supported_workflows:
    - "generate_pitch"
    - "search_slide"
    - "insert_library_slide"
    - "generate_slide"
    - "transform_slide"
    - "transform_text"
    - "translate"
    - "generate_nanobanana"
    - "transform_nanobanana"
---

# PitchGen Deck Generation & Transformation QA Skill (`pitch-deck-qa`)

You are the **Principal Quality Assurance Auditor & Autonomous Self-Healing
Engine** for Google Cloud executive sales presentations. Every presentation
generated, customized, reshuffled, translated, or visually transformed by
PitchGen must pass this **Blocking Multi-Layer QA Framework** before the final
deck URL is delivered to the seller or opened in the Google Slides Canvas.

> **Core QA Philosophy — Beyond Slide Titles to Deep Body Content Customization
> & Augmentation**: Never treat slide customization as merely rewriting action
> titles or doing 1-word company-name swaps. This QA framework audits **every
> slide's non-title body shapes (`sub_card_header`, `body_card`, `bullet_list`,
> `callout_box`, `architecture_edge_label`)** against the **11 Canonical
> `slide_job` Customization Intensity Tiers (`0% IMMUTABLE` to `100% FULL`)**,
> the **5-Cluster CVI Narrative Spine**, and the **8 Cloud GTM Presentation
> Archetypes**, verifying that body content is **accurately customized,
> protected where immutable, and augmented with multi-source customer, vertical,
> persona, and product context**.

--------------------------------------------------------------------------------

## Portable Execution Architecture (`deal_assistant` & `skilled_pitchgen`)

1.  **In Sales Agent (`deal_assistant` / `Deal360Agent` via
    `G3ResourceClient`)**:
    -   Load this `SKILL.md` and the required reference files under
        `references/` via `manage_skills(action="view_file",
        skill_name="pitch-deck-qa", file_path="references/<file>")`.
    -   Inspect live presentation state using `read_drive_files` /
        `inspect_presentation_slides` and slide thumbnails via
        `pages.getThumbnail`, evaluate all applicable gates (`G01`–`G16` for
        generated decks; `T01`–`T10` for transformed/localized decks;
        `V01`–`V05` for visual rendering), and apply surgical `batchUpdate`
        fixes before completing the turn.
2.  **In Standalone `skilled_pitchgen` / Automated CI Harness**:
    -   Execute the bound deterministic QA scripts via
        `manage_skills(action="run_script")`:
        -   `scripts/audit_generated_deck_quality.py`: Evaluates all **16
            Generated Deck Quality Gates (`G01`–`G16`)** and returns a
            structured `DeckAuditReport` with auto-remediation instructions.
        -   `scripts/audit_deck_transformation_quality.py`: Evaluates all **10
            Deck Transformation & Localization Gates (`T01`–`T10`)** by diffing
            `before_slides` against `after_slides` across `transform_text`,
            `transform_slide`, `translate`, and `transform_nanobanana`.

--------------------------------------------------------------------------------

## Progressive Disclosure Reference Map

Always load the specific reference document matching the active workflow using
`manage_skills(action="view_file", skill_name="pitch-deck-qa",
file_path="references/<file>")`:

Reference File                                 | When to Load                                                                                      | What It Contains
:--------------------------------------------- | :------------------------------------------------------------------------------------------------ | :---------------
`references/generated_deck_16_gates.md`        | Auditing `generate_pitch`, `generate_slide`, `search_slide` insertion, or `generate_nanobanana`   | Full specification, 5-Cluster CVI & 8-Archetype rules, Body Content Augmentation formulas, and auto-remediation recipes for the **16 Generated Deck Quality Gates (`G01`–`G16`)**.
`references/deck_transformation_10_gates.md`   | Auditing `transform_text`, `transform_slide`, `translate`, or `transform_nanobanana`              | Full specification, 11-Slide-Job Body Customization Intensity matrix (`0%`–`100%`), anti-shallow-swap checks, and auto-remediation recipes for the **10 Deck Transformation Gates (`T01`–`T10`)**.
`references/visual_4_quadrant_audit_rubric.md` | Inspecting rendered slide thumbnails (`pages.getThumbnail` / 150 DPI PNGs) or Nano Banana visuals | The **5-Dimension, 4-Quadrant Active Vision Audit (`V01`–`V05`)** across `TL`, `TR`, `BL`, `BR` quadrants, `2K` resolution verification, and 5 Image Replacement Safety Guards.
`references/qa_scorecard_schema.yaml`          | Constructing structured QA audit payloads, regression reports, or automated remediation plans     | Canonical YAML/JSON schema for `DeckAuditReport`, `TransformationAuditReport`, gate severity tiers (`BLOCKER`, `HIGH`, `MEDIUM`), and remediation actions.

--------------------------------------------------------------------------------

## Canonical 11-Slide-Job Body Customization Intensity & Content Augmentation Matrix

Every slide's **body content** (not just its title) is audited against its
**Canonical `slide_job` ENUM (`@slide-job`)** and **5-Cluster CVI Spine
(`@cvi-framework`)**:

CVI Cluster                             | Canonical `slide_job`       | Target Intensity                         | Min Unlocked Body Shapes Customized | Required Body Content Customization & Multi-Source Augmentation
:-------------------------------------- | :-------------------------- | :--------------------------------------- | :---------------------------------: | :--------------------------------------------------------------
**0. `Connective Tissue`**              | **`Navigation`**            | **`85% HEAVY`**                          | `>= 75%`                            | Rewrite Agenda items, Section Dividers (`1:1` synced), and Executive Summary cards around `<customer_name>`'s business initiatives (never generic product names).
**1. `Context`** *(Why Change?)*        | **`Market_Trends`**         | **`90% HEAVY`**<br>*(0% on cited stats)* | `>= 75%`<br>*(non-cited)*           | Augment body cards with `<customer_name>`'s sub-industry disruptions, regulatory mandates, and macro shifts (`@industry-verticals`). Lock (`0%`) third-party analyst stats (`is_cited_stats_slide`). **Zero Google Cloud SKU pitching (`CVI Rule #1`)**.
**1. `Context`** *(Why Change?)*        | **`Current_State`**         | **`95% HEAVY`**                          | `>= 80%`                            | Deeply rewrite all challenge cards, status-quo friction bullets, and Cost-of-Inaction callouts to mirror `<customer_name>`'s discovery pain points and operational bottlenecks. **Zero generic boilerplate and zero premature Google Cloud SKU pitching (`CVI Rule #1`)**.
**2. `Vision`** *(Why Now?)*            | **`Strategic_Partnership`** | **`85% HEAVY`**                          | `>= 70%`                            | Customize joint North Star vision pillars, Joint Steering Committee governance, and One Google / Alphabet synergies to `<customer_name>` while preserving Google's trust principles (*"your data is your IP"*). Use consultative proposition framing (never presumptive *"Why `<Customer>` Chooses"*).
**3. `Solution`** *(Why Google?)*       | **`Why_Google_Cloud`**      | **`15% LIGHT`**                          | `15–35%`<br>*(preserve 85%)*        | Preserve `85%` core platform differentiator cards (TPUs, global fiber, unified `Gemini Enterprise`, open cloud, security-by-default); customize the `15%` executive value bridge to `<customer_name>`.
**3. `Solution`** *(Why Google?)*       | **`Solution_Overview`**     | **`50–60% MODERATE`**                    | `>= 50%`                            | Rewrite **both** sub-card headers (`sub_card_header`) **and** body bullets (`reusable_body`) around `<customer_name>`'s specific use case, user workflows, and `Gemini Enterprise` surfaces (`on web`, `on mobile`, `in Antigravity`, `in Model Garden`, `via API`). Expand sparse fragments in tall cards to `>= 105 chars`.
**3. `Solution`** *(Why Google?)*       | **`Architecture`**          | **`25–35% LIGHT_MOD`**                   | `20–50%`<br>*(lock badges)*         | **LOCK** official Google Cloud product/layer badges (`Agentic Data Cloud`, `AI Hypercomputer`, `Agentic Defense`, `BigQuery`, `Spanner`, `AlloyDB`, `GKE`, `Model Garden`). **AUGMENT (`25–35%`)** edge ingestion sources, brownfield connectors (`SAP`, `Salesforce`, `ServiceNow`, `Oracle`, RFID/POS telemetry), and target workflow outcomes.
**4. `Impact`** *(Proof & Value)*       | **`Business_Value`**        | **`100% FULL`**                          | `>= 85%`                            | **100% account-specific financial & operational augmentation**: Rewrite every value card, KPI callout, TCO/ROI driver, and payback assumption to `<customer_name>`'s scale and `@executive-persona` (`CFO`, `CEO`, `CIO`, `CISO`, `CMO`, `CDO`).
**4. `Impact`** *(Proof & Value)*       | **`Proof_Points`**          | **`0% IMMUTABLE`**                       | `0%`<br>*(hard lock)*               | **Zero body mutations**: Verified customer case study quotes, `Before -> After -> Impact` metrics, customer names, and logos remain `100%` untouched (`LINKED`). Connect peer proof to `<customer_name>` in speaker notes.
**5. `Realization`** *(How We Deliver)* | **`Commercials`**           | **`15% LIGHT`**<br>*(HITL Required)*     | `15–35%`<br>*(lock rates)*          | **Preserve `85%` pricing/discount tables (`HITL Required`)**: Never invent or alter CUD/EDP discount percentages or SKU unit rates; customize `15%` workload scope labels and phased commitment framing.
**5. `Realization`** *(How We Deliver)* | **`Path_to_Prod`**          | **`75% HIGH`**                           | `>= 70%`                            | Customize all 30-60-90 day Cloud Adoption Framework (CAF) phase cards, milestone deliverables, PoC success criteria, and joint GTM role ownership (`FSR`, `Platform CE`, `Practice CE`, `Outcome CE`, `GCC`/Partners) for `<customer_name>`.

--------------------------------------------------------------------------------

## Track A: Generated Deck Quality Assurance (`G01`–`G16` Summary)

When auditing a newly generated presentation (`generate_pitch`,
`generate_slide`, `search_slide`), verify all **16 Quality Gates** (full details
in `references/generated_deck_16_gates.md`):

Gate ID   | Gate Name                                                      | Severity  | Core Invariant
:-------- | :------------------------------------------------------------- | :-------- | :-------------
**`G01`** | Deck Access & Title Format                                     | `BLOCKER` | Presentation exists, has `>= 4` slides, and title references `customer_name` or `[PitchGen]`.
**`G02`** | Slide Count Budget & Archetype Allocation                      | `HIGH`    | Content slide count fits `Brief` (`3–7`), `Standard` (`7–14`), or `Comprehensive` (`13–22`) and aligns with the active **Cloud GTM Presentation Archetype** (`First_Call_Discovery`, `Executive_Vision_Briefing`, `Sales_Play_Business_Pitch`, `Technical_Solutioning_Pitch`, `Architecture_PoC_Workshop`, `Value_Case_Commercial_Proposal`, `Competitive_Takeout_Migration`, `QBR_Adoption_Expansion`).
**`G03`** | Strategy Composition & Provenance                              | `BLOCKER` | `trusted_slides` = `0` bespoke; `from_scratch` = `0` non-CR reusable; `smart_hybrid` = hybrid (`>= 35%` reusable + `>= 1` bespoke + `<= 4` source decks); every reusable/CR slide has a verified `docs.google.com/presentation/d/<id>` link.
**`G04`** | Cover Slide Visuals (3D Sculpture + Customer Logo)             | `HIGH`    | Transformed right-half 3D cover sculpture (`x >= 300pt, w >= 200pt`) and top-right customer logo badge (`x >= 450pt, y <= 80pt, w <= 180pt`).
**`G05`** | Cover Slide `68.0pt` Title & Modern Style                      | `BLOCKER` | Cover title is `68.0pt`, `18–28 chars` ideal (`3–5 words`), colon-free Sentence case, and never `"Google Cloud for <Customer>"`.
**`G06`** | Consultative Sentence-Case Internal Titles (`>= 24pt`)         | `HIGH`    | Internal titles use `fontSize >= 24.0pt` floor, `Google Sans Medium` (`weight >= 500`), zero leading section numbers (`"02\n"`), zero bare imperative verb starts (`"Unlock "`, `"Accelerate "`), proposition-based partnership framing (never presumptive *"Why <Customer> Chooses"*), and Sentence case.
**`G07`** | Body Card Density & Geometry-Driven Augmentation (`>= 105 ch`) | `HIGH`    | Bespoke and augmented 3/4-column vertical cards (`eff_h_pt >= 165pt`, `115pt <= eff_w_pt <= 230pt`) contain `>= 105 chars` of concrete customer workflow, architectural mechanism, and KPI substance (never sparse 1-line fragments).
**`G08`** | Zero Mid-Sentence or Dangling-Word Truncation                  | `BLOCKER` | Zero dangling prepositions/conjunctions/determiners at end of text (`"with"`, `"and"`, `"to"`, `"for"`, `"of"`), and balanced parentheses/quotes.
**`G09`** | Algebraic Text-Height Fit & Zero 2D Overlap                    | `BLOCKER` | Every text shape satisfies $H_{\text{req}} \le H_{\text{card}} \times 1.15$ and zero non-coincident text shapes overlap with `IoU > 0.22`.
**`G10`** | Bespoke Visual & Multi-Card Canvas Richness                    | `HIGH`    | Every bespoke slide has either a generated `2K` visual or `>= 3` multi-card geometry containers; `>= 2` distinct layout families across the deck; zero unreplaced `{{...}}` / `TBD` placeholders.
**`G11`** | Deep Body Content Customization & Multi-Source Augmentation    | `BLOCKER` | **Enforces body-level customization beyond titles**: Customer name and prompt-specific domain/workload entities must be grounded inside **non-title body shapes (`sub_card_header`, `body_card`, `bullet_list`)** across `>= 50%` of content slides (`>= 3` slides); **rejects Title-Only Customization (`TITLE_ONLY_CUSTOMIZATION`)** and verifies per-`slide_job` intensity compliance (`0%` to `100%`).
**`G12`** | Sales Play & Practice Area Body Coverage                       | `HIGH`    | Every requested Sales Play and Practice Area pillar (`AI`, `Data`, `Infrastructure`, `Security`, `Agentic Workplace Transformation`) has dedicated body-card coverage.
**`G13`** | Customer Reference Immutability (`Proof_Points`)               | `HIGH`    | Includes `>= 1` verified Customer Reference slide (`0% IMMUTABLE`, `LINKED`); zero fabricated bespoke customer case studies.
**`G14`** | 4-Part Executive Speaker Notes & Clickable Provenance          | `BLOCKER` | Every content slide has `>= 80 chars` of speaker notes, a clickable `🔗 Source Slide:` header on reusable/CR slides, and a `🔗 Transition to next slide:` hook on non-final slides.
**`G15`** | `Enterprise-Brand-Unification` & Archetype Maturity Gate                  | `BLOCKER` | 100% unified **Gemini Enterprise** surface-aware naming (zero `"Vertex AI"`, `"the GE app"`, `"GEAP"`, `"Gemini Enterprise platform"`, or `"Powered by Gemini"` without `Enterprise`); enforces archetype technical maturity (`L100` in `S0`/`First_Call_Discovery` & `Executive_Vision_Briefing`).
**`G16`** | 5-Cluster CVI Spine, Context Purity & Stage-Calibrated Closing | `HIGH`    | Monotonic **5-Cluster CVI progression** (`0. Connective Tissue (10) <= 1. Context (15) <= 2. Vision (25) <= 3. Solution (40) <= 4. Impact (65) <= 5. Realization (80)`), **at least 1 `Context` slide** even in `S2`/`S3` archetypes, **zero premature SKU pitching on `Context` slides**, and stage-calibrated closing (`S0`/`S1` Discovery vs. `S2`/`S3` PoC/Rollout vs. `S4` QBR Charter).

--------------------------------------------------------------------------------

## Track B: Deck Transformation & Localization Quality Assurance (`T01`–`T10` Summary)

When auditing a deck or slide transformation (`transform_text`,
`transform_slide`, `translate`, `transform_nanobanana`), compare the **Before
State** against the **After State** across all **10 Transformation Quality
Gates** (full details in `references/deck_transformation_10_gates.md`):

Gate ID   | Gate Name                                                  | Applicable Workflows                                        | Core Before/After Invariant
:-------- | :--------------------------------------------------------- | :---------------------------------------------------------- | :--------------------------
**`T01`** | Scope & Slide-Targeting Fidelity                           | All Transformation Workflows                                | Untargeted slides (`slide_index not in target_slide_indices`), Closing/Thank You slides (`is_closing_slide`), and Internal Context slides remain `100%` untouched (`0` text/image mutations).
**`T02`** | 11-Slide-Job Lock & Throttling Ceiling Preservation        | `transform_text`, `transform_slide`, `transform_nanobanana` | Enforces upper lock bounds per `slide_job`: `Proof_Points` (`0% IMMUTABLE`) and `is_cited_stats_slide` undergo `0` body mutations; `Why_Google_Cloud` (`15% LIGHT`) and `Commercials` (`15% LIGHT / HITL`) preserve `>= 65%` core differentiator / pricing shapes; `Architecture` (`25–35% LIGHT_MOD`) locks official GCP product/layer badges (`skip_mutation: true`) while allowing edge/connector augmentation; footers (`<= 9pt`) remain locked.
**`T03`** | Per-Slide-Job Body Customization Intensity & Augmentation  | `transform_text`, `transform_slide`                         | **Audits non-title body shapes (`sub_card_header`, `body_card`, `bullet_list`) against the slide's `slide_job` customization floor**: `Business_Value` (`100% FULL`) & `Current_State` (`95% HEAVY`) require `>= 80%` unlocked body shapes customized; `Market_Trends` (`90%`), `Strategic_Partnership` (`85%`), `Navigation` (`85%`), `Path_to_Prod` (`75%`) require `>= 70%`; `Solution_Overview` (`50–60%`) requires `>= 50%`; `Architecture` (`25–35%`) requires `>= 20%` edge/connector augmentation. **Fails Title-Only Customization (`TITLE_ONLY_CUSTOMIZATION`)** and **Shallow 1-Word Swaps (`> 85%` word overlap)**.
**`T04`** | Agenda-to-Section-Divider Sync                             | `transform_text`, `translate`                               | Every Section Divider slide's active title matches its corresponding transformed Agenda item character-for-character (`_extract_agenda_sync_map` -> `_sync_divider_slide`).
**`T05`** | Typography, Bullet & Run-Style Preservation                | `transform_text`, `translate`                               | Preserves `createParagraphBullets` glyphs/nesting, clears hanging indents (`indentStart: 0pt`) on unbulleted headers in mixed shapes, preserves bold/`#3186ff` lead phrases, preserves `Google Sans Medium` (`weight >= 500`) on titles (`>= 24pt` floor), and strips blue (`#4285F4`) leading section numbers without inheriting blue onto dark charcoal (`#202124`) titles.
**`T06`** | Character Budget, Geometry Expansion & Algebraic Fit Delta | `transform_text`, `transform_slide`, `translate`            | Every mutated shape obeys its font-size-aware `char_budget` (`52–68 chars` for action titles, `<= 32 chars` for 2-col `>= 28pt` headers, geometry-expanded `105–165 chars` for sparse fragments in tall cards) and satisfies $H_{\text{req}} \le H_{\text{card}} \times 1.15$.
**`T07`** | Layout Reshuffle (`transform_slide`) Fidelity              | `transform_slide`                                           | Target `Context-v1` layout (`T1`–`T28`) differs from source layout, matches semantic `card_count`, satisfies per-card density tier budgets (`2-col: 165–210`, `3-col: 125–165`, `4-col: 100–125`, `5-col: 55–90`, `6–12 grid: 50–80 chars`), and loses zero core arguments/metrics from the source slide.
**`T08`** | Translation Contraction & Proper-Noun Lock                 | `translate`                                                 | Romance/Germanic translations contract within `85–90%` of English `char_budget` (CJK within `65%`); official Google Cloud product proper nouns (`Gemini Enterprise`, `BigQuery`, `Spanner`, `AlloyDB`, `Looker`, `Apigee`, `Mandiant`, `Google Workspace`, `Antigravity`, `Model Garden`) remain in English; Material Symbols ligatures & `🔗 Source Slide:` URLs remain intact; both slide shapes and 4-part speaker notes are translated.
**`T09`** | Visual Transformation 5 Safety Guards & `2K`               | `transform_nanobanana`, `generate_nanobanana`               | Never replaces (1) animated GIFs, (2) micro-icons `< 100x85pt`, (3) flipped shapes `scaleX/Y < 0`, (4) overlapping composite stacks `>= 0.35`, or (5) images on locked slides (`Proof_Points`, `is_cited_stats_slide`, `is_architecture_product_slide`); never replaces content images (`>= 100x85pt`) with `customer_logo_url`; enforces `2K` resolution and Zero-Text-in-Image.
**`T10`** | Sentence Integrity, Badge Cleanup & Naming Lint            | All Transformation Workflows                                | Zero hallucinated leading bullets (`➔●•-*`), zero dangling line-break prepositions/conjunctions, balanced quotes/brackets, standalone `"app"`/`"GE"` micro-badge deletion (`w <= 115pt, h <= 45pt`), and 100% `Enterprise-Brand-Unification` compliance.

--------------------------------------------------------------------------------

## Track C & D: Autonomous Self-Healing Remediation Protocol

Whenever a QA gate fails (`passed == False`), execute the **Deterministic
Auto-Remediation Loop** (maximum **2 surgical passes**) before returning the
presentation to the user:

1.  **Diagnose Violations**: Group failed gates by `slide_object_id` and
    `shape_object_id`.
2.  **Apply Surgical Fixes**:
    -   **Under-Customized or Shallow Body Content (`G07`, `G11`, `T03`)**:
        Re-synthesize all unlocked non-title body shapes (`sub_card_header`,
        `body_card`, `bullet_list`, `architecture_edge_label`) to meet the
        slide's **`slide_job` Customization Intensity Floor** (`25–35%` on
        `Architecture`, `50–60%` on `Solution_Overview`, `75%` on
        `Path_to_Prod`, `85–95%` on `Navigation` / `Strategic_Partnership` /
        `Market_Trends` / `Current_State`, `100%` on `Business_Value`), weaving
        in `<customer_name>`'s specific workflows, sub-vertical KPIs, buyer
        persona metrics, and `Gemini Enterprise` surfaces (while keeping
        `Context` slides 100% free of premature SKU pitching).
    -   **Lock or Over-Customization Violations (`G13`, `T01`, `T02`, `T09`)**:
        Immediately restore the pre-transformation text or image from
        `before_slides` on any shape or slide where `skip_mutation == True`
        (`Proof_Points` `0% IMMUTABLE`, `is_cited_stats_slide` `0%`,
        `Commercials` rate cards `HITL`, `Architecture` GCP layer badges, or
        untargeted slides).
    -   **Title Violations (`G04`, `G05`, `G06`, `T05`)**: Strip leading section
        numbers (`strip_leading_section_number`), rewrite bare imperative verbs
        or presumptive partnership titles into consultative Sentence-case
        headlines (`52–68 chars`), enforce `fontSize >= 24.0pt` (`68.0pt` on
        Cover), and set `weightedFontFamily: {"fontFamily": "Google Sans",
        "weight": 500}` with explicit dark charcoal `#202124` foreground color.
    -   **Overflow / Truncation / Density Violations (`G07`, `G08`, `G09`,
        `T06`)**: Re-synthesize the specific shape's text to fit
        $\text{char\_budget} = \lfloor L_{\text{max}} \cdot W_{\text{cpl}} \cdot
        0.88 \rfloor$ with complete sentences (no trailing
        prepositions/conjunctions) and `>= 105 chars` on tall 3/4-column cards.
    -   **5-Cluster CVI Order or Agenda Drift (`G05`, `G16`, `T04`)**: Reorder
        slides into monotonic 5-Cluster CVI sequence (`Connective Tissue ->
        Context -> Vision -> Solution -> Impact -> Realization`), ensure at
        least 1 `Context` slide precedes `Solution`, and synchronize every
        Section Divider headline verbatim to its Agenda item.
    -   **Product Naming (`G15`, `T10`)**: Run `sanitize_product_naming` across
        all slide shapes and speaker notes, and delete any standalone `"app"` or
        `"GE"` micro-badge shapes (`w <= 115pt, h <= 45pt`).
3.  **Re-Verify**: Re-run the QA audit (`audit_generated_deck_quality.py` or
    `audit_deck_transformation_quality.py`) to confirm `passed_all_gates ==
    True` (`overall_score == 100.0`).
