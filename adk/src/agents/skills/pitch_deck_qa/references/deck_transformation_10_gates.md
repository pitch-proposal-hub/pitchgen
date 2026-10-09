# 10-Gate Deck Transformation & Localization QA Specification (`T01`–`T10`)

This reference defines the **10-Gate Deck Transformation Inspector
(`T01`–`T10`)** used by `pitch-deck-qa` (`audit_deck_transformation_quality.py`
/ `DeckTransformationInspector`) to audit before/after presentation diffs across
all 4 transformation workflows:

-   **`transform_text`**: In-place presentation/slide text customization
    (`DeckTransformationService` / `batch_update_presentation_content`).
-   **`transform_slide`**: Single-slide or multi-slide structural layout
    reshuffle across the 28 `Context-v1` archetypes (`T1`–`T28`).
-   **`translate`**: Multi-language presentation localization
    (`transform_presentation(..., target_language=...)`).
-   **`transform_nanobanana`**: In-place `2K` visual replacement
    (`replaceAllShapesWithImage` / `replaceImage`).

It enforces the **11 Canonical `slide_job` Customization Intensity Tiers (`0%`
to `100%`)**, blocks **Title-Only Customization (`TITLE_ONLY_CUSTOMIZATION`)**
and **Shallow Noun Swaps (`SHALLOW_NOUN_SWAP`)**, and verifies **Multi-Source
Body Content Augmentation**.

--------------------------------------------------------------------------------

## Gate `T01`: Scope & Slide-Targeting Fidelity (`BLOCKER`)

-   **Applicable Workflows**: `transform_text`, `transform_slide`, `translate`,
    `transform_nanobanana`
-   **Before/After Invariant**:
    1.  **Untargeted Slide Isolation**: When `target_slide_indices` (1-based) is
        specified, every slide $s \notin \text{target\_slide\_indices}$ must
        have **zero text, style, or image mutations** ($\text{after}[s] ==
        \text{before}[s]$).
    2.  **Closing / Thank You Slide Lock (`is_closing_slide`)**: Slides whose
        primary text is `"Thank You"`, `"Thank you!"`, `"Questions?"`, or
        `"Q&A"` (with `<= 40 chars` of other text) must never be rewritten into
        body content slides (`_skip_mutation = True`).
    3.  **Internal Seller Context Isolation**: Slide 1 `"Pitch Context & Seller
        Brief"` table cells are updated only when explicitly targeted; internal
        instructions never leak onto customer-facing slides.
-   **Auto-Remediation**: Revert any mutated shape or image on untargeted or
    closing slides to its exact `before_slides` snapshot.

--------------------------------------------------------------------------------

## Gate `T02`: Immutable Slide, Shape-Level Lock & Intensity Ceiling Preservation (`BLOCKER`)

-   **Applicable Workflows**: `transform_text`, `transform_slide`,
    `transform_nanobanana`
-   **Before/After Invariant**:
    1.  **`Proof_Points` (`0% IMMUTABLE` Customer Case Studies)**:
        -   Verified Customer Reference slides (`slide_job == "Proof_Points"` or
            `[lock: immutable]` in speaker notes) must undergo **zero text or
            image mutations** on customer quotes, customer logos, and verified
            impact metrics (`0%` body shape mutation ceiling).
    2.  **`Why_Google_Cloud` (`15% LIGHT` Competitive Differentiation Guard)**:
        -   On `Why_Google_Cloud` slides, core competitive differentiator cards,
            SWOT comparisons, and analyst rankings remain locked (`<= 25%` body
            shape mutation ceiling); only the primary action title, subtitle
            framing, and speaker notes are tailored to the customer.
    3.  **`Commercials` (`15% LIGHT / HITL` Pricing & Investment Guard)**:
        -   On `Commercials` slides, pricing tables, SKU discount cells, and
            contractual terms remain locked unless explicitly supplied by the
            seller (`<= 25%` body shape mutation ceiling).
    4.  **Cited Analyst Statistics Lock (`is_cited_stats_slide` on
        `Market_Trends`)**:
        -   Any shape containing third-party research citations (`Sources:`,
            `Gartner`, `Forrester`, `IDC`, `eMarketer`, `Nielsen`, `McKinsey`,
            `PwC`, `Ampere Analysis`) must have `skip_mutation == True` so
            verified percentages and multipliers are never altered or attributed
            to another customer.
    5.  **`Architecture` Shape-Level Lock (`25–35% LIGHT_MOD`)**:
        -   On `Architecture` / `is_architecture_product_slide` slides, official
            Google Cloud product and layer badges (`Agentic Data Cloud`, `AI
            Hypercomputer`, `Agentic Defense`, `Research & Frontier Multimodal
            Models`, `ADK, Agent Runtime`, `Agent Gateway`, `BigQuery`,
            `Spanner`, `AlloyDB`, `GKE`) remain locked (`skip_mutation ==
            True`), while the slide's primary action title, subtitle, and
            customer data-flow edge callouts are augmented (`25–50%` of shapes
            mutated).
    6.  **Footer, Legal Disclaimer & Page Number Lock**:
        -   Shapes with `font_size_pt <= 9.0pt`, `"Proprietary + Confidential"`,
            `"Proprietary & Confidential"`, or standalone numeric badges
            (`01`–`99`) remain untouched.
-   **Auto-Remediation**: Restore original text from `before_slides` on any
    locked shape (`skip_mutation == True`) or any `Proof_Points` /
    `Why_Google_Cloud` / `Commercials` body shape that exceeded its lock
    ceiling.

--------------------------------------------------------------------------------

## Gate `T03`: Per-`slide_job` Body Customization Intensity Floor, Multi-Source Augmentation & Zero Title-Only Customization (`BLOCKER`)

-   **Applicable Workflows**: `transform_text`, `transform_slide`
-   **Before/After Invariant**:
    1.  **Non-Title Body Shape Customization Intensity Floor (by `slide_job`)**:
        -   We evaluate **unlocked non-title body shapes** (`sub_card_header`,
            `body_card`, `bullet_list`, `callout_box`,
            `architecture_edge_label`) separately from `is_action_title`:
            -   `Architecture` (`25–35% LIGHT_MOD`): **`>= 25%` of unlocked
                callout/edge-label shapes** mutated with customer source systems
                and data flows.
            -   `Solution_Overview` (`50–60% MODERATE`): **`>= 50%` of unlocked
                non-title body shapes** (`sub_card_header` + `body_card` /
                `bullet_list`) mutated and re-anchored to the customer's stated
                use case.
            -   `Path_to_Prod` (`75% HIGH`): **`>= 70%` of unlocked non-title
                body shapes** mutated with concrete pilot milestones, POC
                charter steps, and mutual owners.
            -   `Navigation` (`85% HEAVY`): **`>= 75%` of unlocked
                agenda/divider items** mutated to reflect the customer's
                strategic imperatives.
            -   `Strategic_Partnership` (`85% HEAVY`): **`>= 70%` of unlocked
                non-title body shapes** mutated with joint vision pillars and
                proposition-based partnership framing.
            -   `Market_Trends` (`90% HEAVY`): **`>= 75%` of unlocked non-cited
                body shapes** mutated to the customer's sub-vertical catalysts.
            -   `Current_State` (`95% HEAVY`): **`>= 80%` of unlocked non-title
                body shapes** mutated with customer-specific operational
                bottlenecks, legacy constraints, and discovery questions.
            -   `Business_Value` (`100% FULL`): **`>= 85%` of unlocked non-title
                body shapes** mutated with persona-specific KPIs and
                conservative `"Target:"` / `"Estimated:"` range framing.
    2.  **Zero Title-Only Customization (`TITLE_ONLY_CUSTOMIZATION`)**:
        -   If a targeted slide (`intensity >= 25%`) mutates its action title
            (`is_action_title`) to mention `customer_name` or
            `specific_use_case` while **zero non-title body shapes are mutated**
            (or body shapes contain zero domain/use-case tokens), `T03`
            **immediately fails as a BLOCKER**.
    3.  **Zero Shallow 1-Word Noun Swaps (`SHALLOW_NOUN_SWAP`)**:
        -   Mutated body shapes (`body_card`, `bullet_list`) must not merely
            replace `"Customer"` / `"the enterprise"` with `customer_name` while
            leaving `> 85%` of the original generic template words unchanged.
            Body shapes must be holistically augmented with:
            -   Customer-specific workflows and data sources from
                `specific_use_case`
            -   Industry sub-vertical terminology and compliance guardrails
            -   Target executive persona KPIs
    4.  **Sub-Card Header Re-Anchoring (`sub_card_header`)**:
        -   Multi-word card headers (`2–5 words`, `<= 45 chars`) on customizable
            use-case, challenge, and roadmap cards must be tailored to the
            customer's domain workflow rather than left verbatim from the
            template.
-   **Auto-Remediation**: Re-run holistic body-shape synthesis on any slide
    flagged with `TITLE_ONLY_CUSTOMIZATION`, `SHALLOW_NOUN_SWAP`, or below its
    `slide_job` body intensity floor, explicitly rewriting `sub_card_header`,
    `body_card`, and `bullet_list` shapes with multi-source customer and
    vertical context.

--------------------------------------------------------------------------------

## Gate `T04`: Agenda-to-Section-Divider Synchronization (`HIGH`)

-   **Applicable Workflows**: `transform_text`, `translate`
-   **Before/After Invariant**:
    -   When a presentation contains an **Agenda / Contents** slide (`01`, `02`,
        `03`... numbered items) and corresponding **Section Divider / Break**
        slides:
    -   Every Section Divider slide's active headline must match its
        corresponding transformed Agenda item **character-for-character**
        (`_extract_agenda_sync_map` -> `_sync_divider_slide`).
-   **Auto-Remediation**: Overwrite out-of-sync Section Divider headlines with
    the exact transformed Agenda item text for that section number.

--------------------------------------------------------------------------------

## Gate `T05`: Typography, Bullet & Run-Style Preservation (`BLOCKER`)

-   **Applicable Workflows**: `transform_text`, `translate`
-   **Before/After Invariant**:
    1.  **Action Title Font Weight & Size Floor**:
        -   Every mutated internal slide action title preserves
            **`font_size_pt >= 24.0pt`** (`68.0pt` on Cover Slide) and uses
            **`weightedFontFamily: {"fontFamily": "Google Sans", "weight":
            500}`** (never bare `fields: "fontFamily"` which resets Medium `500`
            weight to Regular `400`).
    2.  **Leading Section Number Stripping & Color Reset**:
        -   Inline blue (`#4285F4`) leading section numbers (`"02 \x0b..."`,
            `"04\n..."`) are stripped from mutated action titles, and the title
            text style explicitly resets `foregroundColor` to dark charcoal
            (`#202124`) so the title never inherits the deleted number's blue
            color.
    3.  **Bullet List & Hanging Indent Integrity**:
        -   Shapes that originally had native bullet lists (`paragraphs_meta`
            with `is_bullet: True`) retain native `createParagraphBullets`
            formatting without prepending literal `•` or `-` characters
            (`delete_ParagraphBullets` + `createParagraphBullets`).
        -   In mixed shapes (unbulleted header followed by bulleted lines),
            unbulleted header paragraphs explicitly reset `indentStart: 0pt,
            indentFirstLine: 0pt` so they never inherit a hanging indent.
    4.  **Bold / Accent Lead-In Preservation (`lead_style`)**:
        -   Paragraph lead-in phrases (`1–5 words` before `:` or `–`) that
            originally used bold or brand blue (`#3186ff`) styling retain their
            `updateTextStyle` run highlight.
-   **Auto-Remediation**: Emit corrective `updateTextStyle`
    (`weightedFontFamily`, `foregroundColor`, `fontSize`) and
    `updateParagraphStyle` (`indentStart: 0pt`) requests.

--------------------------------------------------------------------------------

## Gate `T06`: Body Shape Character Budget Expansion & Algebraic Fit Delta (`BLOCKER`)

-   **Applicable Workflows**: `transform_text`, `transform_slide`, `translate`
-   **Before/After Invariant**:
    1.  Every mutated text shape satisfies its font-size-aware `char_budget`:
        -   **Primary Action Titles (`>= 24pt`)**: `52 <= len(new_text) <= 68`
            characters (expanding short 1-word template headers like
            `"Monetize"` into full consultative Sentence-case headlines when box
            geometry permits).
        -   **2-Column Display Subheaders (`>= 28pt`, `original_len <= 42`)**:
            `len(new_text) <= 32` characters (`max 2 lines`).
        -   **Body & Card Shapes (`body_card`, `bullet_list`)**:
            -   Never overflows `char_budget` (`-10%` for `18–23pt`, `-8%` for
                `12–17pt`, `-5%` for `< 12pt`).
            -   **Geometry-Aware Content Augmentation**: When a source card
                contains a sparse fragment (`< 50 chars`) inside a roomy card
                box (`alg_cap >= 105 chars`), `char_budget` expands to
                $\min(\text{alg\_cap}, 135)$ so the body shape is augmented with
                complete executive sentences rather than starved to a 4-word
                fragment.
    2.  Every mutated shape passes the **Pre-Batch Algebraic Text-Height Gate**
        ($H_{\text{req}} \le H_{\text{card}} \times 1.15$).
-   **Auto-Remediation**: Compress overflowing text shapes to `<= char_budget`
    or expand under-augmented sparse fragments in tall cards while preserving
    complete sentence structure.

--------------------------------------------------------------------------------

## Gate `T07`: Layout Reshuffle (`transform_slide`) Fidelity (`HIGH`)

-   **Applicable Workflows**: `transform_slide`
-   **Before/After Invariant**:
    1.  **Distinct Target Archetype**: The selected `Context-v1` `template_id`
        (`T1`–`T28` from deck `TEMPLATE_DECK_CONTEXT_V1_PLACEHOLDER_001`) is
        structurally distinct from the source slide's layout (`after_template_id
        != before_template_id`).
    2.  **Semantic Card-Count Match**: The chosen layout's `card_count` matches
        the source slide's core value pillars (`2`, `3`, `4`, `5`, or `6–12`
        grid items), never dropping a key argument or metric.
    3.  **Density-Tier Budget Compliance**:
        -   `2-column` (`T2`, `T6`, `T7`, `T27`): `165–210 chars` per card
        -   `3-column` (`T1`, `T5`, `T8`, `T9`, `T13`, `T17`, `T18`, `T23`,
            `T28`): `125–165 chars` per card
        -   `4-column` (`T3`, `T10`, `T12`, `T14`, `T20`, `T21`, `T22`, `T25`,
            `T26`): `100–125 chars` per card
        -   `5-column` (`T11`, `T15`, `T19`): `55–90 chars` per card
        -   `6–12 grid` (`T4`, `T16`, `T24`): `50–80 chars` per cell
-   **Auto-Remediation**: Re-map the reshuffled content to the `Context-v1`
    template whose `card_count` matches the semantic pillar count and adjust
    per-card character density.

--------------------------------------------------------------------------------

## Gate `T08`: Localization & Translation (`translate`) Integrity (`BLOCKER`)

-   **Applicable Workflows**: `translate`
-   **Before/After Invariant**:
    1.  **Language Contraction Budgets**:
        -   Romance/Germanic languages (`es`, `fr`, `de`, `pt`, `it`, `nl`)
            expand `15–25%` if translated literally; translated strings must
            obey the `85–90%` contraction ceiling relative to the English
            `char_budget` so zero text boxes overflow.
        -   CJK languages (`ja`, `ko`, `zh`) obey `65%` character count ceiling.
    2.  **Official Product Proper-Noun Lock**:
        -   Official Google Cloud product names (**`Gemini Enterprise`**,
            **`BigQuery`**, **`Spanner`**, **`AlloyDB`**, **`Looker`**,
            **`Apigee`**, **`Mandiant`**, **`Google Cloud`**, **`Google
            Workspace`**, **`Antigravity`**, **`Model Garden`**, **`GKE`**)
            remain in their canonical English form and are never translated
            phonetically or literally.
    3.  **Icon Font Ligature & Provenance URL Preservation**:
        -   Material Symbols / Google Symbols single-character icon ligatures
            (`\ue000`–`\uf8ff`) and `🔗 Source Slide:` URLs remain 100% intact.
    4.  **Complete Slide + Speaker Notes Localization**:
        -   Both unlocked slide text shapes and the 4-part executive speaker
            notes are localized into `target_language`.
-   **Auto-Remediation**: Restore any translated product proper nouns back to
    canonical English (`Gemini Enterprise`, `BigQuery`, etc.) and tighten
    overflowing localized phrases.

--------------------------------------------------------------------------------

## Gate `T09`: Visual Transformation (`transform_nanobanana`) 5 Safety Guards & `2K` Resolution (`BLOCKER`)

-   **Applicable Workflows**: `transform_nanobanana`, `generate_nanobanana`
-   **Before/After Invariant**:
    1.  **Guard 1 (Zero GIF Replacement)**: Never replace animated GIFs (`.gif`
        or `mime_type == "image/gif"`).
    2.  **Guard 2 (Zero Micro-Icon Replacement)**: Never replace small icons, UI
        badges, or brand emblems (`width < 100pt` or `height < 85pt`).
    3.  **Guard 3 (Zero Flipped-Shape Replacement)**: Never replace shapes with
        negative transform scale (`scaleX < 0` or `scaleY < 0`).
    4.  **Guard 4 (Zero Overlapping Composite Stack Replacement)**: Never
        replace images that overlap another image by `>= 35%`
        (`bbox_overlap_ratio >= 0.35`) or overlap text shapes by `> 8%`.
    5.  **Guard 5 (Zero Locked-Slide or Customer-Logo Misuse)**: Never replace
        images on `Proof_Points`, `is_cited_stats_slide`, or
        `is_architecture_product_slide` slides, and **never replace large
        in-slide content visuals (`>= 100x85pt`) with `customer_logo_url`
        (`CENTER_INSIDE`)**.
    6.  **`2K` Resolution & Zero-Text-in-Image**: Generated visuals use `>= 2K`
        resolution (`>= 1600x1080px` for Cover/hero visuals) and contain **zero
        rendered words, labels, or watermarks** inside the bitmap.
-   **Auto-Remediation**: Revert any image replacement that violated Guards 1–5
    to its original `contentUrl`, or regenerate any Nano Banana image that
    contains rendered text/watermarks.

--------------------------------------------------------------------------------

## Gate `T10`: Sentence Integrity, Micro-Badge Cleanup & `Enterprise-Brand-Unification` Lint (`BLOCKER`)

-   **Applicable Workflows**: All Transformation Workflows (`transform_text`,
    `transform_slide`, `translate`, `transform_nanobanana`)
-   **Before/After Invariant**:
    1.  **Zero Hallucinated Leading Bullet Symbols**: Mutated text runs never
        inject literal leading `➔`, `●`, `•`, `▪`, `▸`, or `- ` characters into
        unbulleted shapes or on top of existing native bullets.
    2.  **Zero Dangling Line-Break Splits
        (`verify_and_lint_transformed_text`)**: No line or text box ends with a
        dangling preposition, conjunction, or article (`"with"`, `"and"`,
        `"to"`, `"for"`, `"of"`, `"the"`), and all quotes/parentheses are
        balanced.
    3.  **Legacy Split-Product Micro-Badge Deletion**: Any standalone small
        callout shape (`width <= 115pt, height <= 45pt`) containing only `"app"`
        or `"GE"` from legacy `"Gemini Enterprise"` + `"app"` diagrams is
        deleted (`deleteObject`).
    4.  **100% `Enterprise-Brand-Unification` Compliance**: Zero occurrences of `"Vertex
        AI"`, `"the GE app"`, `"Gemini Enterprise app"`, `"GEAP"`, `"Gemini
        Enterprise platform"`, or `"Powered by Gemini"` (without `Enterprise`)
        across any mutated shape or speaker notes.
-   **Auto-Remediation**: Run `verify_and_lint_transformed_text()` and
    `sanitize_product_naming()` on all mutated shapes and emit `deleteObject`
    for orphaned `"app"`/`"GE"` micro-badges.
