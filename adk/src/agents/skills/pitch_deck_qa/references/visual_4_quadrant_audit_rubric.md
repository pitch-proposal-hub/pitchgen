# 5-Dimension, 4-Quadrant Active Vision Audit Rubric (`V01`–`V05`)

This reference defines the **Blocking 4-Quadrant Visual Audit Loop
(`V01`–`V05`)** for inspecting rendered Google Slides thumbnails
(`presentations.pages.getThumbnail` at `MEDIUM`/`LARGE` 150 DPI PNG) across both
**Generated Decks** and **Transformed Decks**.

--------------------------------------------------------------------------------

## Why API Success Is Never Enough

A Google Slides `batchUpdate` returning `HTTP 200 OK` only confirms that the
JSON payload was syntactically valid. It does **not** guarantee that:

-   Text did not wrap onto an extra line and clip against the bottom of a card
    container.
-   A long customer name (`"The Home Depot"`, `"Warner Bros. Discovery"`) did
    not collide with an adjacent column header or badge.
-   A replaced image (`replaceAllShapesWithImage`) maintained its aspect ratio
    and visual contrast against overlay text.

--------------------------------------------------------------------------------

## The 4-Quadrant Inspection Protocol (`TL`, `TR`, `BL`, `BR`)

For every sampled or modified slide, fetch its rendered PNG via
`pages.getThumbnail` (`1600x900` or `MEDIUM`/`LARGE`) and systematically scan
all **4 Quadrants**:

1.  **Top-Left Quadrant (`TL`: $x \in [0, 360\text{pt}],\ y \in [0,
    202.5\text{pt}]$)**:
    -   **Cover Slide**: Verify the `68.0pt` left-column title (`width <=
        395pt`) wraps cleanly on 2–3 lines without colon punctuation or
        clipping.
    -   **Internal Slides**: Verify the eyebrow tracker (`9–11pt` uppercase) and
        primary consultative Sentence-case action title (`>= 24.0pt`, `Google
        Sans Medium` weight `500`) have `>= 14pt` vertical clearance above
        top-row content cards and zero leading section numbers (`"02\n"`).
2.  **Top-Right Quadrant (`TR`: $x \in [360, 720\text{pt}],\ y \in [0,
    202.5\text{pt}]$)**:
    -   **Cover Slide**: Verify the customer logo badge (`x: 618.0pt, y: 24.2pt,
        30.2x30.2pt`) sits cleanly beside the Google Cloud emblem (`660.3pt,
        24.2pt`) with zero overlap, and the top half of the 3D industry
        sculpture is crisp (`2K` resolution).
    -   **Internal Slides**: Verify right-hand KPI callout badges, architecture
        layer tags, or right-column headers do not collide with the action title
        if the title wrapped to 2 lines.
3.  **Bottom-Left Quadrant (`BL`: $x \in [0, 360\text{pt}],\ y \in [202.5,
    405\text{pt}]$)**:
    -   Verify left-column cards, numbered step blocks, and table cells have `>=
        10pt` internal bottom padding, balanced paragraph density (`>= 105
        chars` on tall bespoke cards), and `>= 18pt` clearance above the
        `"Proprietary + Confidential"` footer (`y >= 380pt`).
4.  **Bottom-Right Quadrant (`BR`: $x \in [360, 720\text{pt}],\ y \in [202.5,
    405\text{pt}]$)**:
    -   Verify right-column cards, architecture diagrams, Nano Banana visuals,
        and page numbers (`<= 9pt`) have zero text-on-text collision (`IoU ==
        0`), zero text-on-image illegibility, and zero visual distortion.

--------------------------------------------------------------------------------

## The 5 Visual Audit Dimensions (`V01`–`V05`)

Visual Gate | Dimension                               | Pass Criterion                                                                                                                                                                                                                                                    | Deterministic Fix Recipe
:---------- | :-------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-----------------------
**`V01`**   | **Zero Text Overflow & Clipping**       | Every text run stays 100% inside its card/shape boundary with `>= 8pt` bottom/side margin; zero lines cut off at container edges.                                                                                                                                 | Reduce character count by `15–20%` or step down body font size by `1pt` (`>= 10.5pt` floor).
**`V02`**   | **Zero Element-on-Element Collision**   | Zero bounding-box overlap (`IoU <= 0.22`) between titles, subheaders, body cards, badges, and footers across all 4 quadrants.                                                                                                                                     | Reposition colliding shape `translateY` or shorten multi-line title to `<= 68 chars`.
**`V03`**   | **Visual Contrast & Hierarchy**         | WCAG AA contrast (`>= 4.5:1` for body text, `>= 3.0:1` for `>= 24pt` titles); dark charcoal `#202124` on light cards `#FFFFFF`/`#F8F9FA`, or `#FFFFFF` on dark navy `#0B1426` covers.                                                                             | Emit `updateTextStyle` to set explicit `foregroundColor` (`#202124` on light backgrounds, `#FFFFFF` on dark backgrounds).
**`V04`**   | **Card Balance & Whitespace Symmetry**  | Adjacent multi-column cards (`2-col`, `3-col`, `4-col`) have aligned top edges (`                                                                                                                                                                                 | \Delta y
**`V05`**   | **Zero-Text-in-Image & `2K` Sharpness** | All AI-generated (`generate_nanobanana` / `transform_nanobanana`) images are crisp (`>= 2K` resolution), properly cropped (`CENTER_CROP` for hero visuals, `CENTER_INSIDE` for logos), and contain **zero baked-in text, pseudowords, UI labels, or watermarks**. | Regenerate the visual with explicit negative prompt `"no text, no words, no letters, no numbers, no signage, no watermarks"`.
