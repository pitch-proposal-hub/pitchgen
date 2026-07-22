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

For each slide, generate the notes using this exact markdown structure:

```markdown
Slide X: [Slide Title/Topic]
Key Message: [State what this slide communicates in one clear sentence.]
Framework Section: [e.g., WHY CHANGE: Trends & Changes]
Talking Points:
- [Bulleted talking point 1]
- [Bulleted talking point 2]
- [Bulleted talking point 3]
Thought Provoking Questions:
- [Bulleted question 1]
- [Bulleted question 2]
```

## Content Generation Guidelines

1.  **Key Message**: Identify in a single, clear sentence.
2.  **Talking Points**: 3-5 concise bulleted points that directly align with the
    specified framework section or slide goal. Must be complete sentences that a
    presenter could say verbatim. Persuasive, conversational, and
    client-focused. Provide context so presenter understands what to convey.
3.  **Questions**: 1-2 thought-provoking questions for the audience.
4.  **Clarity and Conciseness**: Clear, direct, easy to follow. Avoid jargon,
    keep sentences succinct.
5.  **Tone**: Professional, authoritative, empathetic, concise, conversational.
