# 16-Gate Generated Deck Quality Assurance Specification (`G01`–`G16`)

This reference defines the **16-Gate Deck Perfection Inspector (`G01`–`G16`)**
used by `pitch-deck-qa` (`audit_generated_deck_quality.py` /
`DeckPerfectionInspector`) to audit newly generated presentations
(`generate_pitch`, `generate_slide`, `search_slide` insertion, and
`generate_nanobanana`).

It enforces the **8 Cloud GTM Presentation Archetypes**, the **5-Cluster CVI
Narrative Spine** mapped 1:1 to the **11 Canonical `slide_job` ENUMs**, and
**Per-`slide_job` Body Customization Intensity (`0%`–`100%`) & Multi-Source
Content Augmentation**.

--------------------------------------------------------------------------------

## Gate `G01`: Deck Access & Title Format (`BLOCKER`)

-   **Pass Criteria**:
    1.  Presentation object resolves with a valid non-empty `presentation_id`.
    2.  Total slide count `>= 3` (Cover + at least 1 Content slide +
        Closing/Next Steps).
    3.  Presentation `title` references `customer_name` or includes the
        `[PitchGen]` prefix (`[PitchGen] <Customer> | <Topic> (<Month Year>)`).
-   **Auto-Remediation**: Normalize `presentation_id` via
    `normalize_presentation_url()` and update the Google Drive file title to
    `[PitchGen] {customer_name} | {use_case_title}`.

--------------------------------------------------------------------------------

## Gate `G02`: Slide Count Budget & 8-Archetype Phase Balance (`HIGH`)

-   **Pass Criteria**:
    1.  Count **content slides** by excluding:
        -   Slide 1 (`Cover` / `Title_Slide`)
        -   Standalone `Agenda` / `Navigation` divider slides
        -   Final `Thank You` / `Questions?` closing slide (`is_closing_slide`)
        -   Internal seller context slides (`Pitch Context & Seller Brief`)
    2.  Verify `content_slide_count` falls within the requested `deck_length`
        budget:
        -   `Brief (4-6 slides)`: **`3 <= content_slide_count <= 7`**
        -   `Standard (8-12 slides)`: **`7 <= content_slide_count <= 14`**
        -   `Comprehensive (15-20 slides)`: **`13 <= content_slide_count <=
            22`**
    3.  **8-Archetype Phase Balance & Minimum `Context` Rule**:
        -   When `presentation_archetype` is one of the 8 canonical Cloud GTM
            archetypes (`First_Call_Discovery`, `Executive_Vision_Briefing`,
            `Sales_Play_Business_Pitch`, `Technical_Solutioning_Pitch`,
            `Architecture_PoC_Workshop`, `Value_Case_Commercial_Proposal`,
            `Competitive_Takeout_Migration`, `QBR_Adoption_Expansion`), the deck
            must include **at least 1 `Context` slide (`Market_Trends` or
            `Current_State`)** — never compressing `Context` to `0%` even in
            late-stage technical or commercial decks.
-   **Auto-Remediation**: Prune redundant lowest-scoring slides if over budget,
    or synthesize a missing CVI stage slide (`Context-v1` `T1`–`T28`) if under
    budget or missing `Context`.

--------------------------------------------------------------------------------

## Gate `G03`: Strategy Composition & Provenance (`BLOCKER`)

-   **Pass Criteria**:
    1.  **Strategy Ratio Enforcement**:
        -   `cloudhub` (`reusable_only`): `bespoke_count == 0` and
            `reusable_count + customer_ref_count >= 1`.
        -   `bespoke_custom` (`bespoke_only`): `reusable_count == 0` (verified
            `Proof_Points` Customer Case Studies remain allowed as
            `customer_ref_count`) and `bespoke_count >= 1`.
        -   `smart_hybrid` (`hybrid`): Contains a balanced blend of reusable
            library slides (`Why_Google_Cloud` + `Solution_Overview` +
            `Architecture` + `Proof_Points`) and bespoke `Context-v1`
            synthesized slides (`Market_Trends`, `Current_State`,
            `Strategic_Partnership`, `Business_Value`, `Path_to_Prod`).
    2.  **Provenance Link Verification**:
        -   Every `reusable` or `customer_ref` slide must include a verified
            Google Slides URL (`https://docs.google.com/presentation/d/<20+ char
            ID>`) in its speaker notes (`🔗 Source Slide:` header).
-   **Auto-Remediation**: Inject missing `🔗 Source Slide: <Deck Title> (Slide
    <N>)` clickable hyperlinks from the `slide_plan` manifest into speaker
    notes.

--------------------------------------------------------------------------------

## Gate `G04`: Cover Slide `68.0pt` Title & Modern Style (`BLOCKER`)

-   **Pass Criteria**:
    1.  Primary Cover Slide (`Slide 1`) title shape uses **`fontSize ==
        68.0pt`** (`>= 60.0pt` hard floor).
    2.  Left-column bounding box width **`width <= 395.0pt`** (`translateX <
        300.0pt`) so it never collides with the right-half 3D cover sculpture.
    3.  **Modern Colon-Free Sentence Case**:
        -   Zero colons (`:`) in the Cover Slide primary title.
        -   Character count **`18–28 chars` ideal** (`<= 34 chars` hard ceiling,
            `3–5 words`).
        -   Never uses legacy rigid templates (`"Google Cloud for <Customer>"`
            or `"<Customer>: <Topic>"`).
-   **Auto-Remediation**: Rewrite the Cover Slide title to a modern colon-free
    hook (e.g., `"Agentic commerce at {customer_name}"`) and emit
    `updateTextStyle` (`fontSize: 68.0pt`, `weightedFontFamily: {"fontFamily":
    "Google Sans", "weight": 500}`).

--------------------------------------------------------------------------------

## Gate `G05`: Cover Logo Badge, Transformed 3D Sculpture, 5-Cluster CVI Spine & Context Purity (`BLOCKER`)

-   **Pass Criteria**:
    1.  **Customer Logo Badge**: Present at top-right of Slide 1 (`595.0pt <= x
        <= 645.0pt`, `y <= 75.0pt`, `w <= 120.0pt`), directly beside the Google
        Cloud emblem (`660.3pt, 24.2pt`). If no official transparent PNG logo
        was found in Drive, a crisp fallback monogram badge PNG must be
        synthesized and placed.
    2.  **Transformed Right-Half 3D Sculpture**: Cover Slide right-half visual
        (`x >= 240.0pt`, `w >= 180.0pt`) must be transformed for the customer's
        industry/theme (verified via `storage.googleapis.com` signed URL or
        `PitchGen-Transformed` alt-text marker, never the raw uncustomized
        template ring).
    3.  **5-Cluster CVI Narrative Spine Progression (`11` Canonical
        `slide_job`s)**:
        -   Content slides must progress monotonically across the 5 CVI
            clusters:
            -   Cluster `0` (`stage 10` — `Connective Tissue` / `CVI 00`):
                `Navigation`
            -   Cluster `1` (`stage 15` — `Context: Why Change?` / `CVI 01 &
                02`): `Market_Trends`, `Current_State`
            -   Cluster `2` (`stage 25` — `Vision: Why Now?` / `CVI 03`):
                `Strategic_Partnership`
            -   Cluster `3` (`stage 40` — `Solution: Why Google Cloud?` / `CVI
                04a & 04b`): `Why_Google_Cloud`, `Solution_Overview`,
                `Architecture`
            -   Cluster `4` (`stage 65` — `Impact: Proof & Value` / `CVI 04c`):
                `Business_Value`, `Proof_Points`
            -   Cluster `5` (`stage 80` — `Realization: How We Deliver` / `CVI
                05`): `Commercials`, `Path_to_Prod`
        -   No `Realization` (`stage 80`) slide may appear before core
            `Solution` (`stage 40`) slides.
    4.  **CVI Context Purity (Zero Premature Product Pitching)**:
        -   Slides assigned to Cluster `1` (`Market_Trends` or `Current_State`)
            must remain 100% focused on industry catalysts, external pressures,
            customer pain points, and discovery questions — **never prematurely
            pitching specific Google Cloud product SKUs (`BigQuery`, `Spanner`,
            `AlloyDB`, `GKE`, `Looker`, `Apigee`, `Gemini Enterprise`) in
            `Current_State` body copy**.
    5.  **Agenda-to-Slide Alignment**:
        -   If an Agenda slide lists *"Operational Bottlenecks"*, *"Executive
            Discovery Questions"*, or *"Joint Value Discovery Workshop"*,
            corresponding content slides must exist with matching domain
            terminology and explicit `?` discovery questions.
-   **Auto-Remediation**: Reorder out-of-sequence CVI slides via
    `updateSlidesPosition`, strip premature product SKU pitches from
    `Current_State`/`Market_Trends` slides, insert the customer logo badge at
    `(618.0pt, 24.2pt)`, and align bespoke section headlines with Agenda
    promises.

--------------------------------------------------------------------------------

## Gate `G06`: Consultative Sentence-Case Titles, Sub-Card Headers & Proposition Framing (`HIGH`)

-   **Pass Criteria**:
    1.  Every internal content slide's primary action title has **`fontSize >=
        24.0pt`** (`Google Sans Medium`, `weightedFontFamily.weight >= 500`).
    2.  **Zero Leading Section Numbers**: No action title starts with `"01\n"`,
        `"02 \x0b"`, `"04 - "`, etc.
    3.  **Zero Bare Imperative Command or Repetitive `-ing` Gerund Starts
        (Google Brand Voice & Tone)**: Action titles on bespoke and customized
        slides must never start with bare imperative verbs (`"Unlock "`,
        `"Accelerate "`, `"Transform "`, `"Revolutionize "`, `"Supercharge "`,
        `"Empower "`, `"Maximize "`, `"Drive "`, `"Build "`, `"Deploy "`) or
        repetitive `-ing` continuous/gerund openers (`"Reimagining "`,
        `"Elevating "`, `"Uniting "`, `"Activating "`, `"Scaling "`,
        `"Orchestrating "`, `"Establishing "`). Use **Subject + finite active
        verb + outcome** or **clean noun/contrast phrases** instead (e.g.,
        `"Autonomous agents transform global banking workflows"`, `"One governed
        data fabric unifies 169PB on BigQuery"`, `"From fragmented copilots to
        an autonomous enterprise"`).
    4.  **Proposition-Based Partnership Framing (CVI Governance Invariant 3)**:
        -   Action titles and `sub_card_header` shapes on
            `Strategic_Partnership` and `Why_Google_Cloud` slides must never use
            presumptive phrases that claim the customer has already chosen
            Google Cloud (`"Why <Customer> Chooses Google Cloud"`, `"Why
            <Customer> Partners with Google Cloud"`, `"Why <Customer> Selected
            Google Cloud"`).
        -   Always frame as an executive value proposition: *"Why `<Customer>`
            Should Partner with Google Cloud"*, *"Why Google Cloud for
            `<Customer>`"*, or *"Alphabet AI innovation meets `<Customer>`
            scale"*.
    5.  **Sub-Card Header Re-Anchoring (`sub_card_header`)**:
        -   Multi-word card headers (`2–5 words`, `<= 45 chars`) on customizable
            `Current_State`, `Strategic_Partnership`, `Solution_Overview`,
            `Business_Value`, and `Path_to_Prod` slides must be tailored to the
            customer's domain workflows (never left as generic template headers
            like `"Pillar 1"`, `"Key Benefit"`, `"Feature A"`, `"Step 1"`).
-   **Auto-Remediation**: Strip leading section numbers, convert bare
    imperatives and `-ing` gerund openers to active-voice or noun-led Sentence
    case, rewrite presumptive `"Chooses/Partners with"` headers into
    proposition-based framing, and enforce `fontSize >= 24.0pt` with `Google
    Sans Medium` (`weight: 500`).

--------------------------------------------------------------------------------

## Gate `G07`: Body Card Content Augmentation & Multi-Source Specificity (`>= 105 chars`) (`HIGH`)

-   **Pass Criteria**:
    1.  **Tall-Card Character Density (`>= 105 chars`)**:
        -   On bespoke 3-column and 4-column layouts (`Context-v1` `T1`–`T28`),
            any vertical card shape with effective height **`eff_h_pt >=
            165.0pt`** and width **`115.0pt <= eff_w_pt <= 230.0pt`** must
            contain **`>= 105 characters`** of concrete executive copy (`25–42
            words`), so tall cards never look visually hollow.
        -   **Exemption**: Up to `3` concise consultative discovery question
            prompts ending in `?` (`>= 45 chars`) on an Executive Discovery
            Questions slide.
    2.  **Multi-Source Body Content Augmentation**:
        -   Non-title body shapes (`body_card`, `bullet_list`, `callout_box`,
            `architecture_edge_label`) across customizable slides (`intensity >=
            25%`) must synthesize **at least 3 of the 4 Content Augmentation
            Dimensions**:
            1.  **Account & Workload Context**: Explicit customer name, current
                data/cloud stack, or operational workflow from
                `specific_use_case`.
            2.  **Industry Sub-Vertical & Regulatory Context**
                (`@industry-verticals`): Sub-vertical operational mechanics and
                regulatory/compliance guardrails (e.g., `PCI-DSS`, `HIPAA`,
                `DORA`, `FedRAMP`, `omnichannel fulfillment`, `claims
                adjudication`, `supply-chain telemetry`).
            3.  **Executive Persona KPIs** (`@executive-persona`): Target CxO
                value metrics (`TCO`, `ROAS`, `MTTR`, `LTV`, `gross margin`,
                `conversion rate`, `finops`, `developer velocity`).
            4.  **Unified Product & Architectural Surface**
                (`@product-knowledge`): Concrete Google Cloud capabilities and
                unified `Gemini Enterprise` surfaces (`Gemini Enterprise on
                web`, `in Antigravity`, `in Model Garden`, `via API`,
                `BigQuery`, `Spanner`, `AlloyDB`, `GKE`, `Mandiant`).
-   **Auto-Remediation**: Expand sparse or generic body card copy (`< 105
    chars`) with multi-source domain mechanisms, persona KPIs, and unified
    `Gemini Enterprise` architectural specifics up to `125–165 chars` while
    staying within $H_{\text{req}} \le H_{\text{card}}$.

--------------------------------------------------------------------------------

## Gate `G08`: Zero Mid-Sentence or Dangling-Word Truncation (`BLOCKER`)

-   **Pass Criteria**:
    1.  No text shape ends with a dangling preposition, conjunction, article, or
        auxiliary verb (`"with"`, `"and"`, `"or"`, `"to"`, `"for"`, `"in"`,
        `"of"`, `"by"`, `"from"`, `"the"`, `"a"`, `"an"`, `"via"`, `"into"`,
        `"across"`, `"through"`, `"is"`, `"are"`, `"that"`, `"which"`).
    2.  All parentheses `(...)`, square brackets `[...]`, and quotation marks
        `"..."` are balanced.
-   **Auto-Remediation**: Rewrite truncated sentences into complete,
    self-contained executive statements within `char_budget`.

--------------------------------------------------------------------------------

## Gate `G09`: Pre-Batch Algebraic Text-Height Fit & Zero 2D Overlap (`BLOCKER`)

-   **Pass Criteria**:
    1.  **Per-Paragraph Algebraic Height Gate**:
        -   For every paragraph $i$ in a shape with effective width
            $W_{\text{card}}$ (pt), height $H_{\text{card}}$ (pt), and paragraph
            font size $F_i$ (pt): $$W_{\text{cpl}, i} = \max\left(8.0,\
            \frac{W_{\text{card}} - 14.0}{F_i \times 0.56}\right)$$
            $$L_{\text{wrap}, i} = \left\lceil
            \frac{\text{len}(\text{para}_i)}{W_{\text{cpl}, i}} \right\rceil,
            \qquad H_{\text{req}} = \sum_i L_{\text{wrap}, i} \times (F_i \times
            1.32) + 10.0$$
        -   Must satisfy **$H_{\text{req}} \le H_{\text{card}} \times 1.15$**
            (zero vertical overflow).
    2.  **Zero 2D Bounding-Box Collision**:
        -   No two non-coincident text shapes on the same slide may intersect
            with $\text{IoU} = \frac{\text{Area}(A \cap B)}{\min(\text{Area}(A),
            \text{Area}(B))} > 0.22$.
-   **Auto-Remediation**: Tighten paragraph copy by `15–25%` or reduce body font
    size by `1pt` (`>= 10.5pt` floor) until $H_{\text{req}} \le
    H_{\text{card}}$.

--------------------------------------------------------------------------------

## Gate `G10`: Zero Unreplaced Placeholders (`BLOCKER`)

-   **Pass Criteria**:
    -   Zero occurrences of `{{...}}`, `{header...}`, `{body...}`,
        `{metric...}`, `[Insert ...]`, `[Customer Name]`, `Lorem ipsum`, `ipsum
        dolor`, or standalone `TBD` / `TODO` across any slide shape or speaker
        notes.
-   **Auto-Remediation**: Replace residual template tokens with
    customer-specific copy or delete the orphaned placeholder shape.

--------------------------------------------------------------------------------

## Gate `G11`: Per-`slide_job` Body Customization Intensity, Zero Title-Only Customization & Zero Duplicate/Blank Slides (`BLOCKER`)

-   **Pass Criteria**:
    1.  **Zero Blank Default Slides**: Slide 1 is never the default blank Google
        Slides `SLIDES_API*_0` page (`< 5 chars` of text and `0` images).
    2.  **Zero Duplicate Content Slides**: No two content slides have normalized
        word-set Jaccard similarity $\frac{|W_A \cap W_B|}{\min(|W_A|, |W_B|)}
        \ge 0.82$.
    3.  **Per-`slide_job` Body Customization Intensity Floors (`11` Canonical
        `slide_job`s)**:
        -   We audit **non-title body shapes** (`sub_card_header`, `body_card`,
            `bullet_list`, `callout_box`, `architecture_edge_label`) separately
            from the slide title (`is_action_title`):
            -   `Proof_Points` (`0% IMMUTABLE`): `0%` body mutation (100%
                locked).
            -   `Why_Google_Cloud` (`15% LIGHT`): `<= 25%` body mutation (only
                action title/subtitle framing; differentiator pillars & SWOT
                stats stay locked).
            -   `Commercials` (`15% LIGHT / HITL`): `<= 25%` body mutation
                (pricing/SKU cells must never be hallucinated).
            -   `Architecture` (`25–35% LIGHT_MOD`): Official GCP product/layer
                badges remain locked, while **`>= 25%` of unlocked callouts /
                data-flow edge labels** are augmented with the customer's source
                systems and ingestion/serving paths.
            -   `Solution_Overview` (`50–60% MODERATE`): **`>= 50%` of non-title
                body shapes** (`sub_card_header` + `body_card` / `bullet_list`)
                must be customized and augmented for the customer's use case.
            -   `Path_to_Prod` (`75% HIGH`): **`>= 70%` of non-title body
                shapes** must be customized with concrete pilot milestones, POC
                charter steps, and mutual owners.
            -   `Navigation` (`85% HEAVY`): **`>= 75%` of agenda/divider items**
                customized to the customer's strategic imperatives.
            -   `Strategic_Partnership` (`85% HEAVY`): **`>= 70%` of non-title
                body shapes** customized with co-innovation pillars and
                north-star outcomes.
            -   `Market_Trends` (`90% HEAVY`): **`>= 75%` of non-cited body
                shapes** customized (while keeping third-party analyst stats
                `0%` immutable).
            -   `Current_State` (`95% HEAVY`): **`>= 80%` of non-title body
                shapes** customized with customer-specific pain points, tech
                debt, and discovery questions.
            -   `Business_Value` (`100% FULL`): **`>= 85%` of non-title body
                shapes** customized with persona-specific value drivers and
                conservative `"Target:"` / `"Estimated:"` range framing.
    4.  **Zero Title-Only Customization (`TITLE_ONLY_CUSTOMIZATION`)**:
        -   Any slide whose `slide_job` requires `>= 25%` customization
            intensity (`Architecture`, `Solution_Overview`, `Path_to_Prod`,
            `Navigation`, `Strategic_Partnership`, `Market_Trends`,
            `Current_State`, `Business_Value`) **automatically fails `G11`** if
            only the slide title (`is_action_title`) mentions the customer or
            use case while the non-title body shapes (`sub_card_header`,
            `body_card`, `bullet_list`) remain generic template boilerplate.
-   **Auto-Remediation**: Delete blank `SLIDES_API*_0` slides, deduplicate
    near-identical slides, and run holistic body-shape customization and
    multi-source augmentation on any slide flagged for
    `TITLE_ONLY_CUSTOMIZATION` or below its `slide_job` body intensity floor.

--------------------------------------------------------------------------------

## Gate `G12`: 4-Part Executive Speaker Notes & Clickable Provenance (`HIGH`)

-   **Pass Criteria**:
    1.  Every content slide contains **`>= 40 characters`** of executive speaker
        notes.
    2.  Every `reusable` or `customer_ref` slide includes a clickable `🔗 Source
        Slide: <Deck Title> (Slide <N>)` hyperlink
        (`https://docs.google.com/presentation/d/<id>/edit#slide=id.<page_id>`).
    3.  Every bespoke slide includes `✨ Custom generated slide` provenance.
    4.  Content slides include a `🔗 Transition to next slide:` bridge hook
        connecting the narrative arc.
-   **Auto-Remediation**: Generate and attach the 4-part speaker notes block (`🎯
    EXECUTIVE HEADLINE`, `🗣️ TALKING POINTS`, `💡 STRATEGIC PROOF & VALUE`, `🔗
    Transition to next slide:`) via `updateSpeakerNotes`.

--------------------------------------------------------------------------------

## Gate `G13`: Customer Reference Immutability (`Proof_Points`) (`BLOCKER`)

-   **Pass Criteria**:
    1.  All `Proof_Points` (Customer Case Study) slides originate from the
        verified Customer Reference repository
        (`SlidesApp.SlideLinkingMode.LINKED`, `0% IMMUTABLE`).
    2.  Zero bespoke slides fabricate a `"Customer Case Study:"`, `"Customer
        Story:"`, or `"Customer Reference:"` header.
-   **Auto-Remediation**: Replace any fabricated bespoke case study with a
    verified `LINKED` slide from `moma_collections_manifest.yaml`
    (`customer_reference_master_decks`).

--------------------------------------------------------------------------------

## Gate `G14`: Architecture & Cited Statistics Integrity (`BLOCKER`)

-   **Pass Criteria**:
    1.  Zero `[citation needed]`, `[source needed]`, or `[stat needed]` markers
        on any slide.
    2.  All third-party analyst citations (`Gartner`, `Forrester`, `IDC`,
        `McKinsey`, `eMarketer`) on `is_cited_stats_slide` slides remain 100%
        intact.
-   **Auto-Remediation**: Strip ungrounded markers or restore the verified
    analyst citation from the source slide.

--------------------------------------------------------------------------------

## Gate `G15`: `Enterprise-Brand-Unification` & 8-Archetype / WIN-Cycle Stage Gate Compliance (`BLOCKER`)

-   **Pass Criteria**:
    1.  **100% `Enterprise-Brand-Unification` Compliance**:
        -   Zero occurrences of retired split-product terms in bespoke slides,
            customized text shapes, or speaker notes:
        -   `"Vertex AI"` / standalone `"Vertex"` (unless the customer's own
            legal name is `"Vertex"`, e.g., *Vertex Pharmaceuticals*)
        -   `"Gemini Enterprise app"` / `"the GE app"` -> use **`Gemini
            Enterprise on web`** (or `on desktop` / `on mobile`)
        -   `"Gemini Enterprise Agent Platform"` / `"GEAP"` -> use **`Gemini
            Enterprise`**
        -   `"Gemini Enterprise platform"` -> use **`Gemini Enterprise`**
        -   `"Powered by Gemini"` (without `Enterprise`) -> use **`Built with
            Gemini`** or **`powered by Gemini Enterprise`**
    2.  **8-Archetype & WIN-Cycle Stage Gate (`S0`/`S1` vs. `S2`/`S3`/`S4`)**:
        -   When `sales_stage` is `S0` or `S1` (or `presentation_archetype` is
            `First_Call_Discovery` or `Executive_Vision_Briefing`), zero slides
            may be pulled from `L200 Technical Pitch Deck` sources.
        -   When `presentation_archetype` is `Technical_Solutioning_Pitch` or
            `Architecture_PoC_Workshop` (`S2`), at least 1 `Architecture` or
            `Solution_Overview` slide must be included.
-   **Auto-Remediation**: Run `sanitize_product_naming()` across all slide
    shapes and speaker notes, and swap any `L200` slide in `S0`/`S1` for an
    `L100` business-value slide.

--------------------------------------------------------------------------------

## Gate `G16`: Thumbnail Render & 4-Quadrant Active Vision QA Readiness (`HIGH`)

-   **Pass Criteria**:
    1.  `presentations.pages.getThumbnail` (`MEDIUM` / `LARGE` 150 DPI PNG)
        returns a valid `contentUrl` for sampled slides (Cover Slide + content
        slides).
    2.  Passes the **5-Dimension, 4-Quadrant Active Vision Audit (`V01`–`V05`)**
        defined in `references/visual_4_quadrant_audit_rubric.md`.
-   **Auto-Remediation**: Re-execute layout or image fixes for any quadrant
    exhibiting text clipping, overlap, or AI-generated image gibberish text.
