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

## Prompting Guidelines

When prompting the Nano Banana models for slides, follow these guidelines:

1.  **Be Specific about Layout**: Describe the desired layout. Refer to the
    specific layout styles defined in
    [google_brand/layouts/](../google_brand/layouts/README.md) (e.g., Title
    Slide, Content Slide, Quote Slide).
2.  **Enforce Tone**: Align with the brand tone. See
    [slide_tone/SKILL.md](../slide_tone/SKILL.md) for details.
3.  **Keep it Brief**: Slides should not be walls of text. Focus on key
    messages.

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
