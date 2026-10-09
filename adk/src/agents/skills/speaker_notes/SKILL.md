---
name: speaker-notes
description: >-
  Generates clear and compelling speaker notes for sales presentations.
  Supports both CVI (Customer Value Initiative) framework and general speaker notes modes.
---

# Speaker Notes Skill

This skill helps in generating clear, compelling, and consistent speaker notes
for sales presentations. It supports two modes: Assisted CVI and General Speaker
Notes.

## Modes

### Mode 1: Assisted CVI

Apply the CVI framework to mapped slides. For unmapped slides, generate general
speaker notes based on the slide's goal. Use existing notes as primary source
material.

**Core CVI Narrative Context:**

-   **Why Change Narrative:**
    -   Trend/Change: Critical shift in their world.
    -   Flawed Approach: Current reaction and why it's flawed.
    -   Consequence of No Change: Risk or loss if they continue.
    -   New Way: New approach to adopt.
    -   Likely Outcome: Positive results of embracing the new way.
-   **Why You (Google) Narrative:**
    -   Challenge: Specific problem we solve.
    -   Do Statement (New Action): What customer can do differently.
    -   Means Statement (Business Impact): Meaning for their business.
    -   Is Statement (Unique Differentiator): Unique capability we lack.
    -   Telling Detail: Specific customer story/detail making it tangible.

### Mode 2: General Speaker Notes

Generate high-quality, professional speaker notes without the CVI framework.
Focus on key message, talking points (verbatim sentences), and audience
questions.

## Desired Output Format

For each slide, generate clean, professional speaker notes in plain text using this structure:

Key Takeaway: [State what this slide communicates in 1-2 clear, compelling sentences.]

Talking Points:
• [Conversational talking point 1 that the presenter can say directly to the customer]
• [Conversational talking point 2 highlighting business value and Google Cloud differentiation]
• [Conversational talking point 3 addressing architecture or implementation scale]

Discovery Question:
• [Thought-provoking consultative question to engage the customer]

## Content Generation Guidelines

1.  **Format Integrity**: Return ONLY plain text. NEVER include markdown code fences (do NOT output ```markdown or ```). NEVER include internal taxonomy headers or framework labels (do NOT output 'Slide X:', 'Framework Section:', 'WHY CHANGE:', 'Do Statement', etc.).
2.  **Key Takeaway**: Identify in a single, clear executive sentence.
3.  **Talking Points**: 2-3 concise bulleted points that directly align with the slide's business outcome. Must be complete, natural sentences that a presenter can say verbatim.
4.  **Discovery Question**: 1-2 thought-provoking consultative questions for the customer.
5.  **Tone**: Professional, consultative, empathetic, concise, and conversational.
