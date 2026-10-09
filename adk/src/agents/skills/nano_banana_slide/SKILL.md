---
name: nano-banana-slide
description: >-
  Guides generating slides using Nano Banana models (Gemini 3.1 Pro Image and Gemini 3.1 Flash Image).
  Use when asked to generate slides, sales presentations, or specific slide content.
  Connects to customer_journey_map for specific infographic slides.
---

# Nano Banana Slide Generation

This skill guides the generation of slides using the **Nano Banana** models. It
helps select the right model and craft effective prompts.

## Model Selection

-   **Complex Generations / High Visual Fidelity**: Use **Nano Banana Pro**
    (`gemini-3-pro-image`). Best for slides requiring complex layouts, detailed
    infographics, or high-quality imagery.
-   **Standard Generations / Rapid Iteration**: Use **Nano Banana 2**
    (`gemini-3.1-flash-image`). Best for standard content slides, text-heavy
    slides, or quick drafts.

## Prompting Guidelines & 4-Part Boardroom Art Director Directive

When prompting the Nano Banana models (`gemini-3-pro-image` /
`gemini-3.1-flash-image`) for executive slides or in-slide visual customization,
structure prompts using the **4-Part Boardroom Executive Art Director
Directive**:

1.  **Executive Audience & Medium**:
    -   Explicitly frame the visual as a crisp, modern **16:9 widescreen C-suite
        boardroom presentation visual** (`2K` resolution `>= 1600x1080px` for
        hero/title visuals, `1K` `>= 1024px` minimum for content visuals).
2.  **Palette & Framing**:
    -   Use clean Google Cloud Material 3 geometry: crisp white (`#FFFFFF`) or
        light slate (`#F8F9FA`) surfaces, generous negative space (`>= 25%`
        breathing room), subtle rounded elevation cards, and harmonized Google
        Cloud (`#4285F4`, `#34A853`, `#FBBC04`, `#EA4335`) + customer brand
        accent colors.
3.  **Grid & Structural Composition**:
    -   Anchor elements to a structured asymmetrical or 3-column bento/flow grid
        with clear directional visual hierarchy (left-to-right value progression
        or layered architectural stack).
4.  **Explicit Text & Iconography Hierarchy**:
    -   For Title/Cover hero artwork (`slide_index <= 1`): enforce **strict
        zero-text** (`NO text, NO words, NO letters, NO numbers`) so native
        Google Slides typography remains crystal clear.
    -   For data/infographic cards: limit text to short 2–4 word sans-serif
        callout badges and bold quantitative KPI highlights.

## Branding & Themes

The user may request either a Google-branded slide or a customer-themed slide.

-   **Google-Branded**: Follow the Google Brand Guidelines. Use core Google
    colors (Blue, Red, Yellow, Green) and typography. See
    [google_brand/SKILL.md](../google_brand/SKILL.md) for specific values.
-   **Customer-Themed**: Extract or request the customer's brand colors and
    style. Use these to customize the slide palette while maintaining the
    structural principles.

## Connected Skills

For specific types of content, connect to these skills:

-   **Customer Journey Maps**: If the slide requires a customer journey map
    infographic, use the specialized prompt template in
    [customer_journey_map/SKILL.md](../customer_journey_map/SKILL.md).

## Example Usage

### Complex Infographic Slide

**Request**: Create a slide showing the customer journey for onboarding.
**Action**: Use Nano Banana Pro and refer to `customer_journey_map/SKILL.md`.

### Standard Content Slide

**Request**: Create a slide listing the top 3 benefits of our solution.
**Action**: Use Nano Banana 2 with a focus on brevity and tone from
`slide_tone/SKILL.md`.
