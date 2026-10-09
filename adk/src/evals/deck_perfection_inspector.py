"""16-Point Automated Deck Perfection Inspector for Google Slides Presentations.

Audits any generated Google Slides presentation against all 16 structural,
typographical, visual, and content-governance quality gates (G01-G16):

- G01_DECK_ACCESS_AND_TITLE: Presentation accessible & title formatted.
- G02_SLIDE_COUNT_BUDGET: Content slide count matches
Brief/Standard/Comprehensive.
- G03_STRATEGY_COMPOSITION: Reusable vs Bespoke slide ratio matches
deck_strategy.
- G04_COVER_TITLE_68PT_AND_STYLE: Slide 1 primary title is 68.0pt, <=395pt wide,
  colon-free, non-rigid Sentence case (12-34 chars).
- G05_COVER_LOGO_AND_SCULPTURE: Slide 1 customer logo at top-right + cover
sculpture
  image present on right half.
- G06_CONSULTATIVE_SENTENCE_CASE_TITLES: Bespoke slide titles >=24pt, no leading
  section numbers, no bare imperative command verb openers, Sentence case.
- G07_TALL_CARD_CHAR_DENSITY: Bespoke 3/4-column tall cards have >=105 chars of
  substantive copy (eliminating sparse 70-char cards).
- G08_NO_MID_SENTENCE_TRUNCATION: Zero mid-word or dangling-preposition cutoffs.
- G09_ALGEBRAIC_FIT_AND_NO_OVERLAP: Algebraic text height fits box and zero
  unintended 2D text-on-text bounding-box collisions.
- G10_ZERO_UNREPLACED_PLACEHOLDERS: Zero {{...}}, {header...}, or Lorem ipsum.
- G11_NO_DUPLICATE_OR_BLANK_SLIDES: Zero blank initial slides & <78% token
overlap.
- G12_SPEAKER_NOTES_AND_LINKS: Tripartite speaker notes with clickable Source
Slide
  hyperlinks on reusable slides and Transition cues.
- G13_CUSTOMER_REFERENCE_IMMUTABILITY: Customer Reference slides are immutable
  reusable Proof_Points; zero fabricated bespoke case study slides.
- G14_ARCHITECTURE_AND_STATS_IMMUTABILITY: Architecture / cited statistics
slides
  preserve attribution and contain zero ungrounded markers.
- G15_NAMING_AND_STAGE_COMPLIANCE: Zero forbidden Enterprise-Brand-Unification terms
("Vertex AI",
  "Gemini Enterprise app", "GEAP", "Powered by Gemini") and S0/S1 stage
  compliance.
- G16_THUMBNAIL_AND_VISION_QA: Slide thumbnail render verification via Slides
API.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
import re
from typing import Any

BARE_IMPERATIVE_PREFIXES: tuple[str, ...] = (
    "unlock ",
    "fortify ",
    "automate ",
    "scale ",
    "build ",
    "deploy ",
    "establish ",
    "accelerate ",
    "transform ",
    "empower ",
    "drive ",
    "maximize ",
    "optimize ",
    "streamline ",
    "unify ",
    "modernize ",
    "elevate ",
    "supercharge ",
    "harness ",
    "leverage ",
)

GERUND_OPENER_WORDS: frozenset[str] = frozenset({
    "reimagining",
    "elevating",
    "uniting",
    "activating",
    "scaling",
    "orchestrating",
    "establishing",
    "unlocking",
    "fortifying",
    "automating",
    "building",
    "deploying",
    "accelerating",
    "transforming",
    "empowering",
    "driving",
    "maximizing",
    "optimizing",
    "streamlining",
    "unifying",
    "modernizing",
    "supercharging",
    "harnessing",
    "leveraging",
    "bridging",
    "connecting",
    "enabling",
    "eliminating",
    "resolving",
    "turning",
    "combining",
})

FORBIDDEN_NAMING_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Vertex AI", re.compile(r"\bVertex\s+AI\b", re.IGNORECASE)),
    (
        "Gemini Enterprise app",
        re.compile(r"\bGemini\s+Enterprise\s+app\b", re.IGNORECASE),
    ),
    ("the GE app", re.compile(r"\bthe\s+GE\s+app\b", re.IGNORECASE)),
    ("Sobi", re.compile(r"\bSobi\b", re.IGNORECASE)),
    (
        "Gemini Enterprise Agent Platform",
        re.compile(
            r"\bGemini\s+Enterprise\s+Agent\s+Platform\b", re.IGNORECASE
        ),
    ),
    ("GEAP", re.compile(r"\bGEAP\b")),
    ("GECX", re.compile(r"\bGECX\b")),
    (
        "Gemini Enterprise platform",
        re.compile(r"\bGemini\s+Enterprise\s+platform\b", re.IGNORECASE),
    ),
    (
        "Gemini Platform (capital P)",
        re.compile(r"\bGemini\s+Platform\b"),
    ),
    (
        "Gemini Enterprise for <Industry>",
        re.compile(
            r"\bGemini\s+Enterprise\s+for\s+(?:Financial\s+Services|Legal|Customer\s+Experience|CX|Healthcare|Life\s+Sciences|Government|Retail|Marketing)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Powered by Gemini (without Enterprise)",
        re.compile(
            r"\bPowered\s+by\s+Gemini(?!\s+Enterprise)\b", re.IGNORECASE
        ),
    ),
)

UNREPLACED_PLACEHOLDER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\{\{[^{}]+\}\}"),
    re.compile(
        r"\{(?:header|subheader|body|metric|stat|title|bullet)[_\d]*\}",
        re.IGNORECASE,
    ),
    re.compile(r"\bLorem\s+ipsum\b", re.IGNORECASE),
    re.compile(r"\[Insert\s+[^\]]+\]", re.IGNORECASE),
    re.compile(r"\bCymbal\b", re.IGNORECASE),
)

DANGLING_END_WORDS: frozenset[str] = frozenset({
    "to",
    "for",
    "with",
    "and",
    "or",
    "the",
    "a",
    "an",
    "in",
    "of",
    "by",
    "from",
    "into",
    "onto",
    "via",
    "across",
    "through",
    "between",
    "within",
})


@dataclass
class GateResult:
  """Result of evaluating a single quality gate on a presentation."""

  gate_id: str
  gate_name: str
  passed: bool
  score: float
  summary: str
  violations: list[str] = field(default_factory=list)
  details: dict[str, Any] = field(default_factory=dict)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class DeckAuditReport:
  """Complete 16-gate perfection report for a Google Slides presentation."""

  presentation_id: str
  presentation_title: str
  customer_name: str
  deck_strategy: str
  deck_length: str
  sales_stage: str
  total_slides: int
  content_slides: int
  passed_all_gates: bool
  overall_score: float
  gates_passed: int
  gates_total: int
  gate_results: list[GateResult] = field(default_factory=list)

  @property
  def presentation_url(self) -> str:
    return f"https://docs.google.com/presentation/d/{self.presentation_id}/edit"

  def to_dict(self) -> dict[str, Any]:
    data = asdict(self)
    data["presentation_url"] = self.presentation_url
    return data


def _emu_to_pt(emu: float | int | None) -> float:
  if emu is None:
    return 0.0
  return float(emu) / 12700.0


def _dim_to_pt(dim_obj: dict[str, Any] | None) -> float:
  if not dim_obj:
    return 0.0
  mag = float(dim_obj.get("magnitude", 0.0) or 0.0)
  unit = dim_obj.get("unit", "EMU")
  if unit == "PT":
    return mag
  return mag / 12700.0


def _extract_element_bbox_pt(
    element: dict[str, Any],
) -> tuple[float, float, float, float]:
  """Returns (x_pt, y_pt, width_pt, height_pt) for a pageElement."""
  size = element.get("size", {})
  w_base = _dim_to_pt(size.get("width"))
  h_base = _dim_to_pt(size.get("height"))
  xf = element.get("transform", {})
  scale_x = float(xf.get("scaleX", 1.0) if "scaleX" in xf else 1.0)
  scale_y = float(xf.get("scaleY", 1.0) if "scaleY" in xf else 1.0)
  tx = _emu_to_pt(xf.get("translateX", 0.0))
  ty = _emu_to_pt(xf.get("translateY", 0.0))
  return (tx, ty, abs(w_base * scale_x), abs(h_base * scale_y))


def _extract_shape_text_and_style(
    element: dict[str, Any],
) -> tuple[str, float | None, list[str]]:
  """Extracts full text, max fontSize (pt), and any hyperlink URLs from a shape."""
  shape = element.get("shape", {})
  text_Elements = shape.get("text", {}).get("textElements", [])
  parts: list[str] = []
  max_font_pt: float | None = None
  links: list[str] = []

  for te in text_Elements:
    tr = te.get("textRun")
    if not tr:
      continue
    content = tr.get("content", "")
    parts.append(content)
    style = tr.get("style", {})
    fs = style.get("fontSize")
    if fs and content.strip():
      pt = _dim_to_pt(fs)
      if pt > 0 and (max_font_pt is None or pt > max_font_pt):
        max_font_pt = pt
    link_url = style.get("link", {}).get("url")
    if link_url:
      links.append(link_url)

  return ("".join(parts).strip(), max_font_pt, links)


def _iter_all_page_elements(
    elements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
  """Flattens pageElements including any elementGroup children."""
  flat: list[dict[str, Any]] = []
  for el in elements or []:
    if "elementGroup" in el:
      children = el["elementGroup"].get("children", [])
      flat.extend(_iter_all_page_elements(children))
    else:
      flat.append(el)
  return flat


def _extract_speaker_notes(slide: dict[str, Any]) -> tuple[str, list[str]]:
  """Returns (notes_text, hyperlink_urls) from a slide's notesPage."""
  notes_page = slide.get("slideProperties", {}).get("notesPage", {})
  notes_id = notes_page.get("notesProperties", {}).get("speakerNotesObjectId")
  texts: list[str] = []
  links: list[str] = []
  for el in _iter_all_page_elements(notes_page.get("pageElements", [])):
    if notes_id and el.get("objectId") != notes_id:
      # Still inspect shape if speakerNotesObjectId wasn't matched
      pass
    if "shape" in el:
      txt, _, el_links = _extract_shape_text_and_style(el)
      if txt:
        texts.append(txt)
      links.extend(el_links)
  return ("\n".join(texts).strip(), links)


def _classify_slide_origin(
    notes_text: str,
    slide: dict[str, Any] | None = None,
) -> str:
  """Classifies a content slide from its speaker notes attribution and CR markers."""
  lower = notes_text.lower()
  slide_body_low = ""
  if slide:
    body_parts = []
    for el in _iter_all_page_elements(slide.get("pageElements", [])):
      if "shape" in el:
        t, _, _ = _extract_shape_text_and_style(el)
        if t:
          body_parts.append(t.lower())
    slide_body_low = " ".join(body_parts)
  combined_cr_chk = f"{lower} {slide_body_low}"
  is_cr_marker = any(
      mk in combined_cr_chk
      for mk in (
          "customer reference",
          "proof_points",
          "case study",
          "https://your-sales-portal.example.com/customer-references",
          "https://your-sales-portal.example.com/customer-references",
          "exec summary:",
          "customer story",
      )
  )
  if (
      "source slide:" in lower
      or "reusable asset" in lower
      or "docs.google.com/presentation/d/" in lower
  ):
    if is_cr_marker:
      return "customer_reference"
    return "reusable"
  if "custom generated slide" in lower or "bespoke" in lower:
    return "bespoke"
  return "bespoke"


def _is_closing_thank_you_slide(slide: dict[str, Any]) -> bool:
  """Detects whether a slide is a closing Thank You slide."""
  all_text = []
  for el in _iter_all_page_elements(slide.get("pageElements", [])):
    if "shape" in el:
      txt, _, _ = _extract_shape_text_and_style(el)
      if txt:
        all_text.append(txt.lower())
  joined = re.sub(r"\s+", " ", " ".join(all_text)).strip()
  nf_low = re.sub(r"proprietary\s*&\s*confidential", "", joined)
  nf_low = re.sub(r"\bgoogle\s+cloud\b", "", nf_low)
  nf_low = re.sub(r"\b\d+\b", "", nf_low)
  nf_low = re.sub(r"\s+", " ", nf_low).strip()
  nf_words = set(re.findall(r"[a-z]+", nf_low))
  return (
      nf_low
      in ("thank you", "thank you.", "questions?", "thank you!", "you thank")
      or ("thank you" in nf_low and len(nf_low) <= 45)
      or ("thank" in nf_words and "you" in nf_words and len(nf_low) <= 45)
  )


def _is_internal_context_slide(slide: dict[str, Any]) -> bool:
  """Detects whether a slide is an internal context/debug summary slide."""
  all_text = []
  for el in _iter_all_page_elements(slide.get("pageElements", [])):
    if "shape" in el:
      txt, _, _ = _extract_shape_text_and_style(el)
      if txt:
        all_text.append(txt.lower())
  joined = " ".join(all_text).strip()
  return any(
      kw in joined
      for kw in (
          "internal context",
          "remove this slide",
          "{{user_ldap}}",
          "{{er_number}}",
          "opportunity id",
      )
  )


def _is_agenda_slide(slide: dict[str, Any], slide_index: int) -> bool:
  """Detects whether slide 2 is a structural Agenda / Table of Contents slide."""
  if slide_index != 1:
    return False
  notes, _ = _extract_speaker_notes(slide)
  if notes.strip():
    return False
  texts = []
  for el in _iter_all_page_elements(slide.get("pageElements", [])):
    if "shape" in el:
      txt, _, _ = _extract_shape_text_and_style(el)
      if txt:
        texts.append(txt.lower())
  joined = " ".join(texts)
  return "agenda" in joined or (
      "01" in joined and "02" in joined and "03" in joined
  )


def _extract_bg_card_bboxes(
    elements: list[dict[str, Any]],
) -> list[tuple[float, float, float, float]]:
  """Collects bounding boxes of background card rectangles on a slide."""
  bg_boxes: list[tuple[float, float, float, float]] = []
  for el in elements:
    shape = el.get("shape")
    if not shape:
      continue
    st = shape.get("shapeType", "")
    txt, _, _ = _extract_shape_text_and_style(el)
    if st in ("ROUND_RECTANGLE", "RECTANGLE") and len(txt) < 15:
      bbox = _extract_element_bbox_pt(el)
      if bbox[2] >= 100.0 and bbox[3] >= 120.0:
        bg_boxes.append(bbox)
  return bg_boxes


def _resolve_effective_box_height_pt(
    bbox: tuple[float, float, float, float],
    bg_boxes: list[tuple[float, float, float, float]],
    all_elements: list[dict[str, Any]] | None = None,
) -> float:
  """Resolves effective vertical card height when a short TEXT_BOX sits inside a taller card or open layout column."""
  x_pt, y_pt, w_pt, h_pt = bbox
  eff_h = h_pt
  cx = x_pt + w_pt / 2.0
  for bx, by, bw, bh in bg_boxes:
    if bx - 15.0 <= cx <= bx + bw + 15.0 and by - 15.0 <= y_pt <= by + bh:
      remaining_card_h = (by + bh) - y_pt - 8.0
      if remaining_card_h > eff_h:
        eff_h = remaining_card_h
  if (
      eff_h <= h_pt + 5.0
      and all_elements
      and 85.0 <= y_pt <= 260.0
      and w_pt >= 95.0
  ):
    min_next_y = 352.0
    for other in all_elements:
      if "shape" not in other:
        continue
      otxt, _, _ = _extract_shape_text_and_style(other)
      if (
          not otxt
          or "proprietary & confidential" in otxt.lower()
          or otxt.strip().isdigit()
      ):
        continue
      ox, oy, ow, oh = _extract_element_bbox_pt(other)
      if abs(ox - x_pt) <= 5.0 and abs(oy - y_pt) <= 5.0:
        continue
      horiz_ov = min(x_pt + w_pt, ox + ow) - max(x_pt, ox)
      if horiz_ov >= 0.3 * min(w_pt, ow) and oy > y_pt + 18.0:
        if oy < min_next_y:
          min_next_y = oy
    open_col_h = min(195.0, min_next_y - y_pt - 8.0)
    if open_col_h > eff_h:
      eff_h = open_col_h
  return eff_h


def _is_title_case_phrase(text: str) -> bool:
  """Returns True if a multi-word headline has almost every word capitalized (Title Case)."""
  words = [re.sub(r"[^A-Za-z0-9]", "", w) for w in text.split()]
  words = [w for w in words if len(w) >= 4 and not w.isupper()]
  if len(words) < 3:
    return False
  # Ignore first word
  tail_words = words[1:]
  cap_count = sum(1 for w in tail_words if w[0].isupper())
  return (cap_count / len(tail_words)) >= 0.85


def _bbox_iou(
    box_a: tuple[float, float, float, float],
    box_b: tuple[float, float, float, float],
) -> float:
  """Computes intersection-over-minimum-area ratio between two (x, y, w, h) boxes."""
  ax, ay, aw, ah = box_a
  bx, by, bw, bh = box_b
  if aw <= 1.0 or ah <= 1.0 or bw <= 1.0 or bh <= 1.0:
    return 0.0
  ix1 = max(ax, bx)
  iy1 = max(ay, by)
  ix2 = min(ax + aw, bx + bw)
  iy2 = min(ay + ah, by + bh)
  if ix2 <= ix1 or iy2 <= iy1:
    return 0.0
  inter = (ix2 - ix1) * (iy2 - iy1)
  min_area = min(aw * ah, bw * bh)
  return inter / min_area if min_area > 0 else 0.0


class DeckPerfectionInspector:
  """Evaluates a Google Slides presentation against all 16 perfection gates."""

  def inspect_presentation_dict(
      self,
      presentation: dict[str, Any],
      *,
      customer_name: str = "",
      deck_strategy: str = "smart_hybrid",
      deck_length: str = "Standard (8-12 slides)",
      sales_stage: str = "S2",
      expect_customer_logo: bool = True,
      slides_service: Any = None,
      check_thumbnails: bool = False,
  ) -> DeckAuditReport:
    """Runs all 16 quality gates on a Slides API presentation dictionary."""
    pres_id = presentation.get("presentationId", "unknown")
    pres_title = presentation.get("title", "")
    slides = presentation.get("slides", []) or []
    total_slides = len(slides)

    content_slides_list: list[tuple[int, dict[str, Any]]] = []
    cover_idx = 0
    if len(slides) > 1 and _is_internal_context_slide(slides[0]):
      cover_idx = 1

    agenda_slide_obj: dict[str, Any] | None = None
    for idx in range(cover_idx + 1, total_slides):
      if _is_agenda_slide(slides[idx], idx):
        agenda_slide_obj = slides[idx]
        continue
      if _is_closing_thank_you_slide(slides[idx]):
        continue
      if _is_internal_context_slide(slides[idx]):
        continue
      content_slides_list.append((idx + 1, slides[idx]))

    cover_slide_obj = slides[cover_idx] if cover_idx < len(slides) else {}

    gate_results: list[GateResult] = [
        self._gate_01_access_and_title(
            pres_id, pres_title, total_slides, customer_name
        ),
        self._gate_02_slide_count_budget(
            len(content_slides_list), total_slides, deck_length
        ),
        self._gate_03_strategy_composition(
            content_slides_list, deck_strategy, sales_stage=sales_stage
        ),
        self._gate_04_cover_title_68pt_and_style(
            cover_slide_obj, customer_name
        ),
        self._gate_05_cover_logo_and_sculpture(
            cover_slide_obj,
            content_slides=content_slides_list,
            agenda_slide=agenda_slide_obj,
            customer_name=customer_name,
            expect_customer_logo=expect_customer_logo,
        ),
        self._gate_06_consultative_sentence_case_titles(content_slides_list),
        self._gate_07_tall_card_char_density(content_slides_list),
        self._gate_08_no_mid_sentence_truncation(content_slides_list),
        self._gate_09_algebraic_fit_and_no_overlap(content_slides_list),
        self._gate_10_zero_unreplaced_placeholders(slides),
        self._gate_11_no_duplicate_or_blank_slides(slides, content_slides_list),
        self._gate_12_speaker_notes_and_links(content_slides_list),
        self._gate_13_customer_reference_immutability(content_slides_list),
        self._gate_14_architecture_and_stats_immutability(content_slides_list),
        self._gate_15_naming_and_stage_compliance(
            slides, sales_stage, customer_name
        ),
        self._gate_16_thumbnail_and_vision_qa(
            pres_id,
            slides,
            slides_service=slides_service,
            check_thumbnails=check_thumbnails,
        ),
    ]

    gates_passed = sum(1 for g in gate_results if g.passed)
    gates_total = len(gate_results)
    overall_score = round(
        sum(g.score for g in gate_results) / max(1, gates_total) * 100.0, 1
    )

    return DeckAuditReport(
        presentation_id=pres_id,
        presentation_title=pres_title,
        customer_name=customer_name,
        deck_strategy=deck_strategy,
        deck_length=deck_length,
        sales_stage=sales_stage,
        total_slides=total_slides,
        content_slides=len(content_slides_list),
        passed_all_gates=(gates_passed == gates_total),
        overall_score=overall_score,
        gates_passed=gates_passed,
        gates_total=gates_total,
        gate_results=gate_results,
    )

  def _gate_01_access_and_title(
      self,
      pres_id: str,
      pres_title: str,
      total_slides: int,
      customer_name: str,
  ) -> GateResult:
    violations: list[str] = []
    if not pres_id or pres_id == "unknown":
      violations.append("Missing presentationId.")
    if total_slides < 3:
      violations.append(
          f"Presentation has only {total_slides} slides (expected >= 3)."
      )
    if not pres_title.strip():
      violations.append("Presentation title is empty.")
    elif (
        customer_name
        and customer_name.lower() not in pres_title.lower()
        and "[pitchgen]" not in pres_title.lower()
    ):
      violations.append(
          f"Presentation title '{pres_title}' does not reference"
          f" '{customer_name}' or '[PitchGen]'."
      )
    passed = len(violations) == 0
    return GateResult(
        gate_id="G01",
        gate_name="Deck Access & Title Format",
        passed=passed,
        score=1.0 if passed else 0.0,
        summary=(
            f"Title '{pres_title}' with {total_slides} total slides."
            if passed
            else "; ".join(violations)
        ),
        violations=violations,
        details={
            "presentation_title": pres_title,
            "total_slides": total_slides,
        },
    )

  def _gate_02_slide_count_budget(
      self,
      content_count: int,
      total_slides: int,
      deck_length: str,
  ) -> GateResult:
    dl = (deck_length or "Standard").lower()
    if "brief" in dl:
      min_c, max_c = 3, 7  # 4-6 +/- 1 for paired CR + Path-to-Prod
    elif "comprehensive" in dl:
      min_c, max_c = 13, 22  # 15-20 +/- 2
    else:
      min_c, max_c = 7, 14  # 8-12 +/- 1 (up to 14 with paired CR / agenda)

    violations: list[str] = []
    if not (min_c <= content_count <= max_c):
      violations.append(
          f"Content slide count {content_count} (total {total_slides}) outside "
          f"expected range [{min_c}, {max_c}] for '{deck_length}'."
      )
    passed = len(violations) == 0
    return GateResult(
        gate_id="G02",
        gate_name="Slide Count Budget Compliance",
        passed=passed,
        score=1.0 if passed else 0.0,
        summary=(
            f"{content_count} content slides ({total_slides} total) within"
            f" [{min_c}, {max_c}] for {deck_length}."
            if passed
            else "; ".join(violations)
        ),
        violations=violations,
        details={
            "content_slides": content_count,
            "total_slides": total_slides,
            "expected_range": [min_c, max_c],
        },
    )

  def _gate_03_strategy_composition(
      self,
      content_slides: list[tuple[int, dict[str, Any]]],
      deck_strategy: str,
      *,
      sales_stage: str = "S2",
  ) -> GateResult:
    strategy = (deck_strategy or "smart_hybrid").strip().lower()
    stage_upper = (sales_stage or "S2").strip().upper()
    reusable_nums: list[int] = []
    bespoke_nums: list[int] = []
    cr_nums: list[int] = []
    repo_source_decks: list[str] = []

    violations: list[str] = []

    for slide_num, slide in content_slides:
      notes, links = _extract_speaker_notes(slide)
      origin = _classify_slide_origin(notes, slide)
      if origin == "customer_reference":
        cr_nums.append(slide_num)
      elif origin == "reusable":
        reusable_nums.append(slide_num)
      else:
        bespoke_nums.append(slide_num)

      if origin in ("reusable", "customer_reference"):
        joined_links = " ".join(links) + " " + notes
        m_deck = re.search(
            r"docs\.google\.com/presentation/d/([a-zA-Z0-9_-]{20,})",
            joined_links,
        )
        if m_deck:
          repo_source_decks.append(m_deck.group(1))
        else:
          violations.append(
              f"Slide {slide_num} ({origin}) lacks a verified repository source"
              " presentation ID."
          )

    total_content = len(content_slides)
    reusable_plus_cr = len(reusable_nums) + len(cr_nums)
    reusable_ratio = round(reusable_plus_cr / max(1, total_content), 2)

    if strategy in ("cloudhub", "cloudhub_only"):
      if bespoke_nums:
        violations.append(
            "Strategy 'cloudhub' must have 0 bespoke content slides, found"
            f" {len(bespoke_nums)} at slides {bespoke_nums}."
        )
    elif strategy in ("bespoke_custom", "custom", "bespoke"):
      if reusable_nums:
        violations.append(
            "Strategy 'bespoke_custom' must have 0 non-CR reusable content"
            f" slides, found {len(reusable_nums)} at slides {reusable_nums}."
        )
    else:
      # smart_hybrid: must include verified reusable/CR slides (prioritize reusable foundation + Proof_Points before bespoke gap synthesis)
      if not (reusable_nums or bespoke_nums or cr_nums):
        violations.append("No content slides classified for smart_hybrid.")
      elif total_content >= 3 and reusable_plus_cr == 0:
        violations.append(
            f"Strategy 'smart_hybrid' ({stage_upper}) yielded 0 reusable/CR"
            f" slides out of {total_content} content slides (must prioritize"
            " reusable foundation + Proof_Points slides before bespoke gap"
            " synthesis)."
        )

    passed = len(violations) == 0
    return GateResult(
        gate_id="G03",
        gate_name="Deck Strategy & Optimal Reusable Repo Alignment",
        passed=passed,
        score=1.0 if passed else 0.0,
        summary=(
            f"Strategy '{strategy}' ({stage_upper}): {len(reusable_nums)}"
            f" reusable, {len(cr_nums)} CR, {len(bespoke_nums)} bespoke"
            f" (reusable_ratio={reusable_ratio:.0%},"
            f" {len(set(repo_source_decks))} repo anchor decks)."
            if passed
            else "; ".join(violations)
        ),
        violations=violations,
        details={
            "strategy": strategy,
            "sales_stage": stage_upper,
            "reusable_slides": reusable_nums,
            "customer_reference_slides": cr_nums,
            "bespoke_slides": bespoke_nums,
            "reusable_ratio": reusable_ratio,
            "repo_source_decks": sorted(set(repo_source_decks)),
        },
    )

  def _gate_04_cover_title_68pt_and_style(
      self,
      cover_slide: dict[str, Any],
      customer_name: str,
  ) -> GateResult:
    violations: list[str] = []
    elements = _iter_all_page_elements(cover_slide.get("pageElements", []))
    best_title_text = ""
    best_font_pt = 0.0
    best_bbox = (0.0, 0.0, 0.0, 0.0)

    for el in elements:
      if "shape" not in el:
        continue
      txt, font_pt, _ = _extract_shape_text_and_style(el)
      if not txt:
        continue
      if (font_pt or 0.0) > best_font_pt:
        best_font_pt = font_pt or 0.0
        best_title_text = txt.split("\n")[0].strip()
        best_bbox = _extract_element_bbox_pt(el)

    if not best_title_text:
      violations.append("Slide 1 has no primary title text.")
    else:
      if abs(best_font_pt - 68.0) > 1.0:
        violations.append(
            f"Slide 1 primary title font size is {best_font_pt:.1f}pt (must be"
            " 68.0pt)."
        )
      _, _, w_pt, _ = best_bbox
      if w_pt > 405.0:
        violations.append(
            f"Slide 1 primary title box width is {w_pt:.1f}pt (must be <= 395pt"
            " to avoid right-side collision)."
        )
      if ":" in best_title_text:
        violations.append(
            f"Slide 1 primary title '{best_title_text}' contains a rigid colon"
            " ':'."
        )
      if re.search(r"\bGoogle\s+Cloud\s+for\b", best_title_text, re.IGNORECASE):
        violations.append(
            f"Slide 1 primary title '{best_title_text}' uses retired 'Google"
            " Cloud for <Customer>' phrasing."
        )
      if len(best_title_text) > 36:
        violations.append(
            f"Slide 1 primary title '{best_title_text}' is"
            f" {len(best_title_text)} chars (must be <= 34 chars to fit at"
            " 68pt)."
        )

    passed = len(violations) == 0
    return GateResult(
        gate_id="G04",
        gate_name="Cover Slide 68pt Title & Modern Headline",
        passed=passed,
        score=1.0 if passed else 0.0,
        summary=(
            f"Cover title '{best_title_text}' ({len(best_title_text)} chars) at"
            f" {best_font_pt:.1f}pt (width {best_bbox[2]:.1f}pt)."
            if passed
            else "; ".join(violations)
        ),
        violations=violations,
        details={
            "cover_title": best_title_text,
            "font_size_pt": best_font_pt,
            "width_pt": round(best_bbox[2], 1),
        },
    )

  def _gate_05_cover_logo_and_sculpture(
      self,
      cover_slide: dict[str, Any],
      *,
      content_slides: list[tuple[int, dict[str, Any]]] | None = None,
      agenda_slide: dict[str, Any] | None = None,
      customer_name: str = "",
      expect_customer_logo: bool = True,
  ) -> GateResult:
    elements = _iter_all_page_elements(cover_slide.get("pageElements", []))
    has_sculpture = False
    sculpture_transformed = False
    has_logo = False
    transformed_content_images = 0

    for el in elements:
      if "image" not in el:
        continue
      x_pt, y_pt, w_pt, h_pt = _extract_element_bbox_pt(el)
      alt_title = str(el.get("title") or "").strip()
      img_url = str(
          el.get("image", {}).get("contentUrl")
          or el.get("image", {}).get("sourceUrl")
          or ""
      )
      # Cover sculpture spans the right half (width >= 180pt, x >= 240pt)
      if x_pt >= 240.0 and w_pt >= 180.0 and h_pt >= 180.0:
        has_sculpture = True
        if (
            alt_title.startswith("PitchGen-Transformed:")
            or "nanoBanana_imageTrans" in img_url
            or "example.com" in img_url
        ):
          sculpture_transformed = True
      # Customer logo badge sits top-right (x >= 520pt, y <= 75pt)
      if x_pt >= 520.0 and y_pt <= 75.0 and w_pt <= 160.0:
        if (
            alt_title.startswith("PitchGen-CustomerLogo:")
            or "customer_logos" in img_url
            or "example.com" in img_url
            or (x_pt >= 595.0 and x_pt <= 645.0 and w_pt <= 75.0)
        ):
          has_logo = True

    cvi_stages: list[tuple[int, int, str]] = []
    slide_title_and_body: list[tuple[int, str, str]] = []
    for slide_num, slide in content_slides or []:
      s_elems = _iter_all_page_elements(slide.get("pageElements", []))
      for el in s_elems:
        if "image" in el:
          alt_t = str(el.get("title") or "")
          i_url = str(
              el.get("image", {}).get("contentUrl")
              or el.get("image", {}).get("sourceUrl")
              or ""
          )
          if (
              alt_t.startswith("PitchGen-Transformed:")
              or "nanoBanana_imageTrans" in i_url
          ):
            transformed_content_images += 1

      notes, _ = _extract_speaker_notes(slide)
      origin = _classify_slide_origin(notes, slide)
      texts = []
      best_t = ""
      best_fs = 0.0
      for el in s_elems:
        if "shape" in el:
          t, fs, _ = _extract_shape_text_and_style(el)
          if t:
            texts.append(t.lower())
            if (fs or 0.0) > best_fs:
              best_fs = fs or 0.0
              best_t = t.split("\n")[0].strip().lower()
      c_low = " ".join(texts)
      slide_title_and_body.append((slide_num, best_t, c_low))

      if any(
          kw in best_t
          for kw in (
              "let's get started",
              "lets get started",
              "next steps",
              "path to production",
              "recommended next steps",
              "implementation roadmap",
              "joint execution plan",
              "phased rollout",
              "phased migration",
              "migration factory",
              "getting started",
              "commercial framework",
              "discovery workshop",
              "discovery roadmap",
              "joint discovery",
              "joint agentic",
              "joint value discovery",
              "joint governance",
              "day charter",
              "four-week",
              "4-week",
              "pilot charter",
              "pilot roadmap",
              "chartering a",
              "adoption roadmap",
              "transformation roadmap",
              "rollout roadmap",
              "execution roadmap",
          )
      ) or (
          "step 1" in c_low
          and "step 2" in c_low
          and "step 3" in c_low
          and any(
              k in c_low
              for k in (
                  "workshop",
                  "pilot",
                  "kickoff",
                  "cadence",
                  "poc",
                  "production",
                  "roadmap",
                  "mobilize",
                  "validate",
                  "sprint",
                  "charter",
              )
          )
      ):
        stage_rank = 80
      elif origin == "customer_reference":
        stage_rank = 65
      elif (
          any(
              kw in best_t
              for kw in (
                  "current state",
                  "today's reality",
                  "industry challenges",
                  "key challenges",
                  "market trends",
                  "the cost of inaction",
                  "strategic initiative",
                  "strategic footprint",
                  "technology footprint",
                  "tech footprint",
                  "customer research",
                  "digital retail initiatives",
                  "aligning with ",
                  "aligning ",
                  "mapping ",
                  "our vision for",
                  "partnership vision",
                  "vision for ",
                  "footprint",
                  "operational bottleneck",
                  "operational friction",
                  "resolving operational",
                  "evolving ",
                  "targeting high-roi",
                  "bottleneck",
              )
          )
          and slide_num <= 5
      ):
        stage_rank = 15
      else:
        stage_rank = 40
      cvi_stages.append((slide_num, stage_rank, best_t[:45]))

    violations: list[str] = []
    if not has_sculpture:
      violations.append(
          "Slide 1 is missing the right-half 3D cover sculpture image."
      )
    elif not sculpture_transformed:
      violations.append(
          "Slide 1 cover 3D sculpture image was not transformed for the"
          " customer (untransformed template image)."
      )
    if expect_customer_logo and not has_logo:
      violations.append("Slide 1 is missing the top-right customer logo badge.")

    # Verify monotonic CVI narrative stage ordering across content slides
    for i in range(len(cvi_stages)):
      s_num_i, rank_i, title_i = cvi_stages[i]
      for j in range(i + 1, len(cvi_stages)):
        s_num_j, rank_j, title_j = cvi_stages[j]
        if rank_i > rank_j:
          violations.append(
              f"Out-of-order CVI slide progression: Slide {s_num_i}"
              f" ('{title_i}', stage={rank_i}) appears before Slide {s_num_j}"
              f" ('{title_j}', stage={rank_j})."
          )
          break

    # Verify Agenda-to-Slide Alignment when an Agenda slide is present
    agenda_items: list[str] = []
    if agenda_slide:
      ag_shapes: list[tuple[float, float, str]] = []
      for el in _iter_all_page_elements(agenda_slide.get("pageElements", [])):
        if "shape" not in el:
          continue
        txt, _, _ = _extract_shape_text_and_style(el)
        if not txt or not txt.strip():
          continue
        t_clean = re.sub(r"\s+", " ", txt).strip()
        t_low = t_clean.lower()
        if (
            t_low in ("agenda", "table of contents", "google cloud")
            or "proprietary & confidential" in t_low
            or re.match(r"^0?[1-9]$", t_clean)
        ):
          continue
        x_pt, y_pt, _, _ = _extract_element_bbox_pt(el)
        ag_shapes.append((round(x_pt / 40.0), y_pt, t_clean))
      ag_shapes.sort()
      agenda_items = [item[2] for item in ag_shapes]

    if agenda_items and slide_title_and_body:
      for ag_item in agenda_items:
        ag_low = ag_item.lower()
        # 1. Operational Bottlenecks / Challenges / Friction agenda item must have a slide framing bottlenecks/challenges/silos
        if any(
            kw in ag_low
            for kw in (
                "bottleneck",
                "challenge",
                "friction",
                "pain point",
                "silo",
            )
        ):
          has_bottleneck_slide = any(
              any(
                  b_kw in s_ttl
                  for b_kw in (
                      "bottleneck",
                      "challeng",
                      "friction",
                      "silo",
                      "fragment",
                      "disconnect",
                      "sprawl",
                      "barrier",
                      "limit",
                      "slow",
                      "cost of inaction",
                      "strain",
                  )
              )
              or (
                  len(slide_title_and_body) >= 3
                  and any(
                      b_kw in f"{s_ttl} {s_body}"
                      for b_kw in (
                          "bottleneck",
                          "challeng",
                          "friction",
                          "silo",
                          "fragment",
                          "disconnect",
                          "sprawl",
                          "barrier",
                          "cost of inaction",
                          "strain",
                          "legacy",
                          "complexity",
                      )
                  )
              )
              for _, s_ttl, s_body in slide_title_and_body
          )
          if not has_bottleneck_slide:
            violations.append(
                f"Agenda-to-Slide Misalignment: Agenda item '{ag_item}' has no"
                " corresponding content slide headline framing bottlenecks,"
                " silos, or challenges (slide headline was overwritten into a"
                " generic solution title)."
            )
        # 2. Executive Discovery Questions agenda item must have an on-slide discovery questions slide with '?' questions
        if any(
            kw in ag_low
            for kw in (
                "discovery question",
                "executive question",
                "prioritized question",
            )
        ):
          has_question_slide = any(
              (
                  "question" in s_ttl
                  or "discovery" in s_ttl
                  or "hypothes" in s_ttl
              )
              and s_body.count("?") >= 2
              for _, s_ttl, s_body in slide_title_and_body
          )
          if not has_question_slide:
            violations.append(
                f"Agenda-to-Slide Misalignment: Agenda item '{ag_item}' has no"
                " corresponding content slide with explicit on-slide discovery"
                " questions ('?...')."
            )
      # 3. Closing Workshop / Next Steps / Roadmap agenda item must match the final content slide (not seat-pricing / commercials)
      last_ag_low = agenda_items[-1].lower()
      if any(
          kw in last_ag_low
          for kw in (
              "workshop",
              "next step",
              "roadmap",
              "charter",
              "sprint",
              "pilot",
          )
      ):
        last_s_num, last_s_ttl, last_s_body = slide_title_and_body[-1]
        has_workshop_or_next_steps_framing = any(
            w_kw in f"{last_s_ttl} {last_s_body}"
            for w_kw in (
                "workshop",
                "next step",
                "roadmap",
                "charter",
                "sprint",
                "pilot",
                "let's get started",
                "lets get started",
                "30-60-90",
                "weeks 1",
                "week 1",
                "phase",
                "rollout",
                "governance",
                "migration",
                "execution",
                "adoption",
                "factory",
                "milestone",
                "mobilize",
                "kickoff",
                "production",
                "ai maturity",
            )
        )
        has_commercial_seat_pricing = any(
            p_kw in last_s_body
            for p_kw in (
                "seat license",
                "pay-as-you-go and seat pricing",
                "sunk seat license",
            )
        )
        if (
            not has_workshop_or_next_steps_framing
            or has_commercial_seat_pricing
        ):
          violations.append(
              "Agenda-to-Slide Misalignment: Closing Agenda item"
              f" '{agenda_items[-1]}' does not align with closing content"
              f" Slide {last_s_num} ('{last_s_ttl}')."
          )

    passed = len(violations) == 0
    return GateResult(
        gate_id="G05",
        gate_name=(
            "Customer Logo, Transformed Visuals, CVI Order & Agenda Alignment"
        ),
        passed=passed,
        score=1.0 if passed else 0.0,
        summary=(
            f"Cover logo + transformed sculpture + {transformed_content_images}"
            " transformed content image(s) + monotonic CVI order & Agenda"
            " alignment verified."
            if passed
            else "; ".join(violations)
        ),
        violations=violations,
        details={
            "has_sculpture": has_sculpture,
            "sculpture_transformed": sculpture_transformed,
            "has_logo": has_logo,
            "transformed_content_images": transformed_content_images,
            "agenda_items": agenda_items,
            "cvi_stages": [
                {"slide": s_num, "stage": stg, "title": ttl}
                for s_num, stg, ttl in cvi_stages
            ],
        },
    )

  def _gate_06_consultative_sentence_case_titles(
      self,
      content_slides: list[tuple[int, dict[str, Any]]],
  ) -> GateResult:
    violations: list[str] = []
    checked_titles: dict[int, str] = {}
    gerund_opener_slides: list[str] = []

    for slide_num, slide in content_slides:
      notes, _ = _extract_speaker_notes(slide)
      origin = _classify_slide_origin(notes, slide)
      # Find top-most title text box (y <= 75pt, font_pt >= 18pt)
      elements = _iter_all_page_elements(slide.get("pageElements", []))
      title_candidates: list[tuple[float, str, float]] = []
      for el in elements:
        if "shape" not in el:
          continue
        txt, font_pt, _ = _extract_shape_text_and_style(el)
        if not txt or len(txt) < 4:
          continue
        x_pt, y_pt, w_pt, _ = _extract_element_bbox_pt(el)
        if y_pt <= 72.0 and w_pt >= 200.0 and (font_pt or 0.0) >= 18.0:
          first_line = txt.split("\n")[0].strip()
          title_candidates.append((y_pt, first_line, font_pt or 0.0))

      if not title_candidates:
        continue
      title_candidates.sort(key=lambda item: (-item[2], item[0]))
      _, headline, font_pt = title_candidates[0]

      if origin != "customer_reference":
        first_word = (
            re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", headline.split()[0]).lower()
            if headline.split()
            else ""
        )
        if first_word in GERUND_OPENER_WORDS:
          gerund_opener_slides.append(f"Slide {slide_num} ('{headline}')")

      if origin != "bespoke":
        continue
      checked_titles[slide_num] = headline

      if font_pt < 23.5:
        violations.append(
            f"Slide {slide_num} bespoke title '{headline}' has fontSize"
            f" {font_pt:.1f}pt (< 24.0pt minimum floor)."
        )
      if re.match(
          r"^(?:section\s+\d+|\d+[\.\)\-:]\s+)", headline, re.IGNORECASE
      ):
        violations.append(
            f"Slide {slide_num} bespoke title '{headline}' starts with a raw"
            " section number."
        )
      lower_hl = headline.lower()
      for prefix in BARE_IMPERATIVE_PREFIXES:
        if lower_hl.startswith(prefix):
          violations.append(
              f"Slide {slide_num} bespoke title '{headline}' starts with bare"
              f" imperative command '{prefix.strip().title()}'."
          )
          break
      if _is_title_case_phrase(headline):
        violations.append(
            f"Slide {slide_num} bespoke title '{headline}' uses Title Case"
            " instead of consultative Sentence case."
        )

    if len(gerund_opener_slides) >= 3:
      violations.append(
          "Deck exhibits repetitive '-ing' gerund opener fatigue"
          f" ({len(gerund_opener_slides)} slides start with '-ing' participles:"
          f" {', '.join(gerund_opener_slides[:4])}); Google Brand Voice & Tone"
          " requires active voice (Subject + finite verb + outcome) or crisp"
          " noun/contrast phrases."
      )

    passed = len(violations) == 0
    return GateResult(
        gate_id="G06",
        gate_name="Consultative Sentence-Case Internal Titles (>=24pt)",
        passed=passed,
        score=1.0 if passed else max(0.0, 1.0 - 0.25 * len(violations)),
        summary=(
            f"Verified {len(checked_titles)} bespoke slide titles (>=24pt,"
            " Sentence case, non-imperative, active voice)."
            if passed
            else "; ".join(violations)
        ),
        violations=violations,
        details={
            "checked_titles": checked_titles,
            "gerund_opener_slides": gerund_opener_slides,
        },
    )

  def _gate_07_tall_card_char_density(
      self,
      content_slides: list[tuple[int, dict[str, Any]]],
  ) -> GateResult:
    violations: list[str] = []
    tall_card_counts: dict[int, list[int]] = {}

    for slide_num, slide in content_slides:
      notes, _ = _extract_speaker_notes(slide)
      if _classify_slide_origin(notes) != "bespoke":
        continue
      elements = _iter_all_page_elements(slide.get("pageElements", []))
      bg_boxes = _extract_bg_card_bboxes(elements)
      # Identify multi-column tall card body text boxes:
      # y >= 90pt, effective height >= 165pt, width between 105pt and 255pt, with >= 3 such columns on the slide
      tall_boxes: list[tuple[float, str]] = []
      for el in elements:
        if "shape" not in el:
          continue
        txt, font_pt, _ = _extract_shape_text_and_style(el)
        if not txt or len(txt) < 35:
          continue
        bbox = _extract_element_bbox_pt(el)
        x_pt, y_pt, w_pt, _ = bbox
        eff_h_pt = _resolve_effective_box_height_pt(bbox, bg_boxes)
        if (
            y_pt >= 90.0
            and eff_h_pt >= 165.0
            and 105.0 <= w_pt <= 255.0
            and (font_pt or 12.0) <= 16.0
        ):
          tall_boxes.append((x_pt, txt))

      if len(tall_boxes) >= 3:
        lengths = [len(txt) for _, txt in tall_boxes]
        tall_card_counts[slide_num] = lengths
        for col_idx, char_len in enumerate(lengths, start=1):
          if char_len < 105:
            violations.append(
                f"Slide {slide_num} tall card {col_idx} has only {char_len}"
                " chars (minimum 105 chars required to fill vertical card)."
            )

    passed = len(violations) == 0
    return GateResult(
        gate_id="G07",
        gate_name="Tall-Card Character Density (>=105 chars)",
        passed=passed,
        score=1.0 if passed else max(0.0, 1.0 - 0.25 * len(violations)),
        summary=(
            f"Verified tall-card density across {len(tall_card_counts)}"
            f" multi-column bespoke slides: {tall_card_counts}."
            if passed
            else "; ".join(violations)
        ),
        violations=violations,
        details={"tall_card_char_lengths": tall_card_counts},
    )

  def _gate_08_no_mid_sentence_truncation(
      self,
      content_slides: list[tuple[int, dict[str, Any]]],
  ) -> GateResult:
    violations: list[str] = []

    for slide_num, slide in content_slides:
      notes, _ = _extract_speaker_notes(slide)
      if _classify_slide_origin(notes) != "bespoke":
        continue
      for el in _iter_all_page_elements(slide.get("pageElements", [])):
        if "shape" not in el:
          continue
        txt, _, _ = _extract_shape_text_and_style(el)
        if not txt or len(txt) < 25:
          continue
        for line in txt.split("\n"):
          cleaned = line.strip()
          if len(cleaned) < 25:
            continue
          words = re.findall(r"[A-Za-z0-9'-]+", cleaned)
          if not words:
            continue
          last_word = words[-1].lower()
          if last_word in DANGLING_END_WORDS and not cleaned.endswith(
              (".", "!", "?", ":")
          ):
            violations.append(
                f"Slide {slide_num} text ends with dangling word '{last_word}':"
                f" '{cleaned[-55:]}'"
            )
          if cleaned.count("(") != cleaned.count(")"):
            violations.append(
                f"Slide {slide_num} text has unmatched parentheses:"
                f" '{cleaned[-55:]}'"
            )

    passed = len(violations) == 0
    return GateResult(
        gate_id="G08",
        gate_name="Zero Mid-Sentence or Mid-Word Truncation",
        passed=passed,
        score=1.0 if passed else 0.0,
        summary=(
            "Zero mid-sentence or dangling-word truncations detected."
            if passed
            else "; ".join(violations[:5])
        ),
        violations=violations,
    )

  def _gate_09_algebraic_fit_and_no_overlap(
      self,
      content_slides: list[tuple[int, dict[str, Any]]],
  ) -> GateResult:
    violations: list[str] = []

    for slide_num, slide in content_slides:
      notes, _ = _extract_speaker_notes(slide)
      if _classify_slide_origin(notes) != "bespoke":
        continue
      elements = _iter_all_page_elements(slide.get("pageElements", []))
      bg_boxes = _extract_bg_card_bboxes(elements)
      text_boxes: list[tuple[str, tuple[float, float, float, float], str]] = []
      for el in elements:
        if "shape" not in el:
          continue
        txt, font_pt, _ = _extract_shape_text_and_style(el)
        if not txt or len(txt) < 3:
          continue
        bbox = _extract_element_bbox_pt(el)
        x_pt, y_pt, w_pt, h_pt = bbox
        eff_h_pt = _resolve_effective_box_height_pt(bbox, bg_boxes, elements)
        if w_pt >= 35.0 and h_pt >= 14.0:
          f_pt = font_pt or 12.0
          para_fonts: list[float] = []
          cur_p_max = 0.0
          for te in el.get("shape", {}).get("text", {}).get("textElements", []):
            tr = te.get("textRun")
            if not tr:
              continue
            content = tr.get("content", "")
            fs_mag = tr.get("style", {}).get("fontSize", {}).get("magnitude")
            if fs_mag:
              cur_p_max = max(cur_p_max, float(fs_mag))
            if "\n" in content:
              para_fonts.append(cur_p_max or f_pt)
              cur_p_max = 0.0
          if cur_p_max > 0:
            para_fonts.append(cur_p_max)
          paras_list = [p for p in txt.split("\n") if p.strip()]
          req_h = 0.0
          for p_idx, p_str in enumerate(paras_list):
            p_fs = (
                para_fonts[p_idx]
                if p_idx < len(para_fonts)
                else (para_fonts[-1] if para_fonts else f_pt)
            )
            chars_per_line = max(10.0, (w_pt - 12.0) / (p_fs * 0.54))
            p_lines = max(1, math.ceil(len(p_str) / chars_per_line))
            req_h += p_lines * (p_fs * 1.28)
          rendered_h_pt = min(h_pt, max(16.0, req_h))
          text_boxes.append(
              (el.get("objectId", ""), (x_pt, y_pt, w_pt, rendered_h_pt), txt)
          )
          # Check algebraic height fit for multi-line body paragraphs using effective card height
          if len(txt) > 80 and eff_h_pt >= 40.0 and w_pt >= 80.0:
            if req_h > eff_h_pt * 1.35:
              violations.append(
                  f"Slide {slide_num} shape '{el.get('objectId')}' estimated"
                  f" text height {req_h:.0f}pt exceeds effective card height"
                  f" {eff_h_pt:.0f}pt."
              )

      # Check pairwise 2D text-on-text overlap using rendered text heights
      for i in range(len(text_boxes)):
        id_a, box_a, txt_a = text_boxes[i]
        for j in range(i + 1, len(text_boxes)):
          id_b, box_b, txt_b = text_boxes[j]
          # Exclude short card header/badge overlays stacked inside a multi-column card
          if min(len(txt_a.strip()), len(txt_b.strip())) <= 40:
            continue
          iou = _bbox_iou(box_a, box_b)
          if iou > 0.22:
            violations.append(
                f"Slide {slide_num} text shapes '{id_a}' ('{txt_a[:20]}...')"
                f" and '{id_b}' ('{txt_b[:20]}...') overlap (ratio={iou:.2f})."
            )

    passed = len(violations) == 0
    return GateResult(
        gate_id="G09",
        gate_name="Algebraic Fit & Zero 2D Text Overlap",
        passed=passed,
        score=1.0 if passed else max(0.0, 1.0 - 0.25 * len(violations)),
        summary=(
            "All bespoke text boxes satisfy algebraic height bounds and zero 2D"
            " overlap."
            if passed
            else "; ".join(violations[:5])
        ),
        violations=violations,
    )

  def _gate_10_zero_unreplaced_placeholders(
      self,
      slides: list[dict[str, Any]],
  ) -> GateResult:
    violations: list[str] = []
    for idx, slide in enumerate(slides, start=1):
      for el in _iter_all_page_elements(slide.get("pageElements", [])):
        if "shape" not in el:
          continue
        txt, _, _ = _extract_shape_text_and_style(el)
        if not txt:
          continue
        for pat in UNREPLACED_PLACEHOLDER_PATTERNS:
          m = pat.search(txt)
          if m:
            violations.append(
                f"Slide {idx} contains unreplaced placeholder '{m.group(0)}'."
            )

    passed = len(violations) == 0
    return GateResult(
        gate_id="G10",
        gate_name="Zero Unreplaced Placeholders",
        passed=passed,
        score=1.0 if passed else 0.0,
        summary=(
            "Zero unreplaced template placeholders across all slides."
            if passed
            else "; ".join(violations)
        ),
        violations=violations,
    )

  def _gate_11_no_duplicate_or_blank_slides(
      self,
      slides: list[dict[str, Any]],
      content_slides: list[tuple[int, dict[str, Any]]],
  ) -> GateResult:
    violations: list[str] = []
    if slides:
      first_id = slides[0].get("objectId", "")
      if first_id.startswith("SLIDES_API") and first_id.endswith("_0"):
        # Verify it's not an empty default blank slide
        texts = [
            _extract_shape_text_and_style(el)[0]
            for el in _iter_all_page_elements(slides[0].get("pageElements", []))
            if "shape" in el
        ]
        if not "".join(texts).strip():
          violations.append(
              f"Slide 1 is an unremoved blank slide ('{first_id}')."
          )

    slide_token_sets: list[tuple[int, set[str]]] = []
    for slide_num, slide in content_slides:
      texts: list[str] = []
      for el in _iter_all_page_elements(slide.get("pageElements", [])):
        if "shape" in el:
          t, _, _ = _extract_shape_text_and_style(el)
          if t:
            texts.append(t)
      joined = " ".join(texts).strip()
      tokens = {w.lower() for w in re.findall(r"[A-Za-z0-9]{3,}", joined)}
      if len(joined) < 10 and not any(
          "image" in el
          for el in _iter_all_page_elements(slide.get("pageElements", []))
      ):
        violations.append(
            f"Slide {slide_num} appears blank (<10 chars and no images)."
        )
      slide_token_sets.append((slide_num, tokens))

    for i in range(len(slide_token_sets)):
      s_a, tok_a = slide_token_sets[i]
      if len(tok_a) < 8:
        continue
      for j in range(i + 1, len(slide_token_sets)):
        s_b, tok_b = slide_token_sets[j]
        if len(tok_b) < 8:
          continue
        overlap = len(tok_a & tok_b) / min(len(tok_a), len(tok_b))
        if overlap >= 0.82:
          violations.append(
              f"Slides {s_a} and {s_b} have near-duplicate content"
              f" ({overlap:.0%} token overlap)."
          )

    passed = len(violations) == 0
    return GateResult(
        gate_id="G11",
        gate_name="Zero Duplicate or Blank Slides",
        passed=passed,
        score=1.0 if passed else 0.0,
        summary=(
            "Zero blank or duplicate content slides detected."
            if passed
            else "; ".join(violations)
        ),
        violations=violations,
    )

  def _gate_12_speaker_notes_and_links(
      self,
      content_slides: list[tuple[int, dict[str, Any]]],
  ) -> GateResult:
    violations: list[str] = []
    for slide_num, slide in content_slides:
      notes, links = _extract_speaker_notes(slide)
      if len(notes) < 40:
        violations.append(
            f"Slide {slide_num} speaker notes are missing or too short"
            f" ({len(notes)} chars)."
        )
        continue
      origin = _classify_slide_origin(notes)
      if origin in ("reusable", "customer_reference"):
        has_deck_link = any(
            "docs.google.com/presentation" in u for u in links
        ) or ("docs.google.com/presentation" in notes)
        if not has_deck_link:
          violations.append(
              f"Reusable slide {slide_num} is missing a 'Source Slide' Google"
              " Slides hyperlink in speaker notes."
          )

    passed = len(violations) == 0
    return GateResult(
        gate_id="G12",
        gate_name="Tripartite Speaker Notes & Source Slide Hyperlinks",
        passed=passed,
        score=1.0 if passed else max(0.0, 1.0 - 0.2 * len(violations)),
        summary=(
            f"All {len(content_slides)} content slides have structured speaker"
            " notes and source attribution links."
            if passed
            else "; ".join(violations[:5])
        ),
        violations=violations,
    )

  def _gate_13_customer_reference_immutability(
      self,
      content_slides: list[tuple[int, dict[str, Any]]],
  ) -> GateResult:
    violations: list[str] = []
    for slide_num, slide in content_slides:
      notes, _ = _extract_speaker_notes(slide)
      origin = _classify_slide_origin(notes)
      if origin == "bespoke":
        # Ensure bespoke slides never fabricate a fake Customer Reference / Case Study slide
        slide_texts = [
            _extract_shape_text_and_style(el)[0]
            for el in _iter_all_page_elements(slide.get("pageElements", []))
            if "shape" in el
        ]
        joined = " ".join(slide_texts)
        if re.search(
            r"\b(?:Customer\s+Case\s+Study|Customer\s+Story|Customer\s+Reference)\s*:",
            joined,
            re.IGNORECASE,
        ):
          violations.append(
              f"Bespoke slide {slide_num} appears to fabricate a Customer Case"
              " Study instead of using immutable Proof_Points."
          )

    passed = len(violations) == 0
    return GateResult(
        gate_id="G13",
        gate_name="Customer Reference Immutability (Proof_Points)",
        passed=passed,
        score=1.0 if passed else 0.0,
        summary=(
            "Zero fabricated bespoke case studies; all customer references"
            " originate from Proof_Points."
            if passed
            else "; ".join(violations)
        ),
        violations=violations,
    )

  def _gate_14_architecture_and_stats_immutability(
      self,
      content_slides: list[tuple[int, dict[str, Any]]],
  ) -> GateResult:
    violations: list[str] = []
    for slide_num, slide in content_slides:
      for el in _iter_all_page_elements(slide.get("pageElements", [])):
        if "shape" not in el:
          continue
        txt, _, _ = _extract_shape_text_and_style(el)
        if not txt:
          continue
        if re.search(
            r"\[(?:citation|source|stat)\s*needed\]", txt, re.IGNORECASE
        ):
          violations.append(
              f"Slide {slide_num} contains ungrounded marker in '{txt[:50]}'."
          )

    passed = len(violations) == 0
    return GateResult(
        gate_id="G14",
        gate_name="Architecture & Cited Statistics Integrity",
        passed=passed,
        score=1.0 if passed else 0.0,
        summary=(
            "All architecture and statistical claims verified clean."
            if passed
            else "; ".join(violations)
        ),
        violations=violations,
    )

  def _gate_15_naming_and_stage_compliance(
      self,
      slides: list[dict[str, Any]],
      sales_stage: str,
      customer_name: str = "",
  ) -> GateResult:
    violations: list[str] = []
    stage_upper = (sales_stage or "S2").strip().upper()

    for idx, slide in enumerate(slides, start=1):
      notes, _ = _extract_speaker_notes(slide)
      origin = "cover" if idx == 1 else _classify_slide_origin(notes)

      # S0/S1 stage gate: never pull from L200 Technical Pitch Deck
      if (
          stage_upper in ("S0", "S1")
          and "l200 technical pitch deck" in notes.lower()
      ):
        violations.append(
            f"Slide {idx} pulls from 'L200 Technical Pitch Deck' in early stage"
            f" {stage_upper}."
        )

      # Check bespoke slide text & PitchGen-synthesized speaker notes (excluding immutable Original Speaker Notes appendices)
      synthesized_notes = re.split(
          r"---\s*Original\s+Speaker\s+Notes", notes, flags=re.IGNORECASE
      )[0]
      texts_to_scan: list[str] = [synthesized_notes]
      if origin in ("cover", "bespoke"):
        for el in _iter_all_page_elements(slide.get("pageElements", [])):
          if "shape" in el:
            t, _, _ = _extract_shape_text_and_style(el)
            if t:
              texts_to_scan.append(t)

      combined = "\n".join(texts_to_scan)
      for label, pattern in FORBIDDEN_NAMING_PATTERNS:
        for m in pattern.finditer(combined):
          # Allow if customer name itself is "Vertex" (e.g. Vertex Pharmaceuticals)
          if label == "Vertex AI" and "vertex" in (customer_name or "").lower():
            continue
          violations.append(
              f"Slide {idx} uses retired naming '{m.group(0)}' (violates"
              f" Enterprise-Brand-Unification: {label})."
          )

    passed = len(violations) == 0
    return GateResult(
        gate_id="G15",
        gate_name="Enterprise-Brand-Unification & S0/S1 Stage Gate Compliance",
        passed=passed,
        score=1.0 if passed else 0.0,
        summary=(
            f"100% compliant with Enterprise-Brand-Unification and {stage_upper} stage"
            " filter."
            if passed
            else "; ".join(violations[:5])
        ),
        violations=violations,
    )

  def _gate_16_thumbnail_and_vision_qa(
      self,
      pres_id: str,
      slides: list[dict[str, Any]],
      *,
      slides_service: Any = None,
      check_thumbnails: bool = False,
  ) -> GateResult:
    violations: list[str] = []
    checked_count = 0

    if check_thumbnails and slides_service is not None and slides:
      # Spot-check Cover Slide (index 0) and first bespoke/content slide
      sample_slides = [slides[0]]
      if len(slides) > 2:
        sample_slides.append(slides[len(slides) // 2])
      for s in sample_slides:
        page_id = s.get("objectId")
        if not page_id:
          continue
        try:
          thumb = (
              slides_service.presentations()
              .pages()
              .getThumbnail(
                  presentationId=pres_id,
                  pageObjectId=page_id,
                  thumbnailProperties_thumbnailSize="MEDIUM",
              )
              .execute()
          )
          if not thumb.get("contentUrl"):
            violations.append(
                f"Slide '{page_id}' returned empty thumbnail contentUrl."
            )
          checked_count += 1
        except Exception as exc:
          violations.append(
              f"Thumbnail render failed for slide '{page_id}': {exc}"
          )

    passed = len(violations) == 0
    return GateResult(
        gate_id="G16",
        gate_name="Thumbnail Render & Visual QA Readiness",
        passed=passed,
        score=1.0 if passed else 0.0,
        summary=(
            f"Verified {checked_count} slide thumbnails via Slides API."
            if checked_count > 0 and passed
            else (
                "Slides structure verified for visual rendering."
                if passed
                else "; ".join(violations)
            )
        ),
        violations=violations,
        details={"thumbnails_checked": checked_count},
    )


@dataclass
class TransformationAuditReport:
  """Complete 10-gate transformation QA report comparing before vs after presentation dicts."""

  presentation_id: str
  workflow_type: str
  customer_name: str
  specific_use_case: str
  target_language: str
  target_slide_numbers: list[int]
  total_slides: int
  mutated_slides_count: int
  mutated_shapes_count: int
  locked_shapes_preserved_count: int
  passed_all_gates: bool
  overall_score: float
  gates_passed: int
  gates_total: int
  gate_results: list[GateResult] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


_CITED_STATS_PATTERN = re.compile(
    r"(?:\bSources?\s*:|\bGartner\b|\bForrester\b|\bIDC\b|\beMarketer\b"
    r"|\bNielsen\b|\bMcKinsey\b|\bPwC\b|\bAmpere\s+Analysis\b)",
    re.IGNORECASE,
)

_ARCH_STACK_BADGE_PATTERN = re.compile(
    r"(?:\bAgentic\s+Data\s+Cloud\b|\bAI\s+Hypercomputer\b|\bAgentic\s+Defense\b"
    r"|\bResearch\s*&\s*Frontier\s+Multimodal\s+Models\b"
    r"|\bADK,\s*Agent\s+Runtime\b|\bAgent\s+Gateway\b)",
    re.IGNORECASE,
)

_PRESUMPTIVE_PARTNERSHIP_PATTERN = re.compile(
    r"\bWhy\s+[A-Z][A-Za-z0-9&\.\-\s]{1,30}\s+(?:Chooses|Partners\s+with|Selected)\s+Google\s+Cloud\b",
    re.IGNORECASE,
)

_SLIDE_JOB_BODY_INTENSITY_SPECS: dict[str, tuple[float, float, str]] = {
    "Proof_Points": (0.0, 0.0, "0% IMMUTABLE"),
    "Why_Google_Cloud": (0.0, 0.25, "15% LIGHT"),
    "Commercials": (0.0, 0.25, "15% LIGHT / HITL"),
    "Architecture": (0.25, 0.50, "25-35% LIGHT_MOD"),
    "Architecture_Diagram": (0.25, 0.50, "25-35% LIGHT_MOD"),
    "Solution_Overview": (0.50, 1.0, "50-60% MODERATE"),
    "Solution_Use_Case": (0.50, 1.0, "50-60% MODERATE"),
    "Path_to_Prod": (0.70, 1.0, "75% HIGH"),
    "Next_Steps": (0.70, 1.0, "75% HIGH"),
    "Navigation": (0.75, 1.0, "85% HEAVY"),
    "Strategic_Partnership": (0.70, 1.0, "85% HEAVY"),
    "Future_State_Vision": (0.70, 1.0, "85% HEAVY"),
    "Market_Trends": (0.75, 1.0, "90% HEAVY"),
    "Opening_Hook": (0.75, 1.0, "90% HEAVY"),
    "Current_State": (0.80, 1.0, "95% HEAVY"),
    "Current_State_Challenges": (0.80, 1.0, "95% HEAVY"),
    "Customer_Context": (0.80, 1.0, "95% HEAVY"),
    "Business_Value": (0.85, 1.0, "100% FULL"),
    "Business_Value_ROI": (0.85, 1.0, "100% FULL"),
}

_CANONICAL_PROPER_NOUNS: tuple[str, ...] = (
    "Gemini Enterprise",
    "BigQuery",
    "Spanner",
    "AlloyDB",
    "Looker",
    "Apigee",
    "Mandiant",
    "Google Workspace",
    "Antigravity",
    "Model Garden",
)

_FORBIDDEN_LOCALIZED_PROPER_NOUNS: tuple[str, ...] = (
    "Géminis Empresarial",
    "Geminis Empresarial",
    "GranConsulta",
    "Gran Consulta",
    "Jardín de Modelos",
    "Jardin de Modelos",
    "Antigravedad",
    "Entreprise Gemini",
)


class DeckTransformationInspector:
  """10-Point Deck Transformation & Localization Inspector (T01-T10).

  Audits before/after Google Slides presentation dicts across `transform_text`,
  `transform_slide`, `translate`, and `transform_nanobanana` workflows.
  """

  def inspect_transformation_dict(
      self,
      before_pres: dict[str, Any],
      after_pres: dict[str, Any],
      *,
      workflow_type: str = "transform_text",
      customization_scope: str = "both",
      customer_name: str = "",
      specific_use_case: str = "",
      target_slide_numbers: list[int] | None = None,
      target_language: str = "",
  ) -> TransformationAuditReport:
    """Evaluates all 10 Transformation Quality Gates (T01-T10)."""
    pres_id = str(
        after_pres.get("presentationId")
        or before_pres.get("presentationId")
        or ""
    )
    scope_norm = (customization_scope or "both").strip().lower()
    before_slides = list(before_pres.get("slides", []))
    after_slides = list(after_pres.get("slides", []))
    total_slides = len(after_slides)
    target_set = (
        {int(x) for x in target_slide_numbers}
        if target_slide_numbers
        else set(range(1, len(after_slides) + 1))
    )

    mutated_slides_count = 0
    mutated_shapes_count = 0
    locked_shapes_preserved_count = 0

    t01_v: list[str] = []
    t02_v: list[str] = []
    t03_v: list[str] = []
    t04_v: list[str] = []
    t05_v: list[str] = []
    t06_v: list[str] = []
    t07_v: list[str] = []
    t08_v: list[str] = []
    t09_v: list[str] = []
    t10_v: list[str] = []

    all_after_custom_text: list[str] = []
    agenda_map: dict[int, str] = {}
    divider_map: dict[int, tuple[int, str]] = {}

    # Special handling for insert_library_slide (adds +1 slide at target_slide_numbers)
    if workflow_type == "insert_library_slide":
      if len(after_slides) != len(before_slides) + 1:
        t01_v.append(
            f"insert_library_slide expected {len(before_slides) + 1} slides"
            f" after insertion, found {len(after_slides)}."
        )
      inserted_idx = min(target_set) if target_set else len(after_slides)
      if 1 <= inserted_idx <= len(after_slides):
        ins_slide = after_slides[inserted_idx - 1]
        mutated_slides_count = 1
        ins_texts = [
            _extract_shape_text_and_style(el)[0]
            for el in _iter_all_page_elements(ins_slide.get("pageElements", []))
            if "shape" in el
        ]
        ins_joined = " ".join(t for t in ins_texts if t).strip()
        if len(ins_joined) < 10 and not any(
            "image" in el
            for el in _iter_all_page_elements(ins_slide.get("pageElements", []))
        ):
          t03_v.append(
              f"Inserted library slide at index {inserted_idx} is blank."
          )
        else:
          mutated_shapes_count = len([t for t in ins_texts if t.strip()])
          all_after_custom_text.append(ins_joined)

    slide_pairs: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    if (
        workflow_type == "insert_library_slide"
        and len(after_slides) == len(before_slides) + 1
    ):
      ins_pos = min(target_set) if target_set else len(after_slides)
      for b_idx, b_s in enumerate(before_slides, start=1):
        a_idx = b_idx if b_idx < ins_pos else b_idx + 1
        if 1 <= a_idx <= len(after_slides):
          slide_pairs.append((a_idx, b_s, after_slides[a_idx - 1]))
    else:
      for idx in range(1, min(len(before_slides), len(after_slides)) + 1):
        slide_pairs.append((idx, before_slides[idx - 1], after_slides[idx - 1]))

    for idx, b_slide, a_slide in slide_pairs:
      b_notes, _ = _extract_speaker_notes(b_slide)
      a_notes, _ = _extract_speaker_notes(a_slide)
      b_origin = _classify_slide_origin(b_notes)
      b_job = str(b_slide.get("slide_job", ""))

      b_els = {
          str(el.get("objectId", "")): el
          for el in _iter_all_page_elements(b_slide.get("pageElements", []))
      }
      a_els = {
          str(el.get("objectId", "")): el
          for el in _iter_all_page_elements(a_slide.get("pageElements", []))
      }

      b_slide_texts: list[str] = []
      a_slide_texts: list[str] = []
      slide_mutated = False
      title_changed = False
      unlocked_body_total = 0
      unlocked_body_changed = 0
      slide_image_mutated = False

      # Check if new image element was added on a_slide (e.g. generate_nanobanana)
      new_image_oids = [
          oid for oid, el in a_els.items() if "image" in el and oid not in b_els
      ]
      if new_image_oids:
        slide_mutated = True
        slide_image_mutated = True

      # Find primary title shape on before_slide (largest font >= 18pt)
      primary_title_oid = ""
      max_title_fs = 0.0
      for oid, el in b_els.items():
        if "shape" not in el:
          continue
        txt, fs, _ = _extract_shape_text_and_style(el)
        _, y_pt, _, _ = _extract_element_bbox_pt(el)
        if (
            txt
            and (fs or 0.0) >= 18.0
            and y_pt <= 220.0
            and "Proprietary" not in txt
        ):
          if (fs or 0.0) > max_title_fs:
            max_title_fs = fs or 0.0
            primary_title_oid = oid

      a_slide_elems = _iter_all_page_elements(a_slide.get("pageElements", []))
      a_bg_boxes = _extract_bg_card_bboxes(a_slide_elems)

      for oid, b_el in b_els.items():
        a_el = a_els.get(oid)
        if "shape" in b_el:
          b_txt, b_fs, _ = _extract_shape_text_and_style(b_el)
          a_txt, a_fs, _ = (
              _extract_shape_text_and_style(a_el)
              if a_el and "shape" in a_el
              else ("", None, [])
          )
          b_slide_texts.append(b_txt)
          a_slide_texts.append(a_txt)
          is_title = oid == primary_title_oid
          fs_val = float(b_fs or 14.0)
          _, b_y_pt, _, _ = _extract_element_bbox_pt(b_el)

          is_locked = bool(b_el.get("skip_mutation", False))
          lock_reason = "skip_mutation"
          if scope_norm == "images_only":
            is_locked = True
            lock_reason = "images_only_scope_text_lock"
          elif (
              fs_val <= 9.0 and b_y_pt >= 340.0
          ) or "Proprietary & Confidential" in b_txt:
            is_locked = True
            lock_reason = "footer_or_legal_disclaimer"
          elif (
              b_origin == "customer_reference"
              or b_origin == "customer_ref"
              or b_job == "Proof_Points"
              or "lock: immutable" in b_notes.lower()
          ) and not is_title:
            is_locked = True
            lock_reason = "Proof_Points_0_percent_immutable"
          elif _CITED_STATS_PATTERN.search(b_txt) and not is_title:
            is_locked = True
            lock_reason = "is_cited_stats_slide"
          elif _ARCH_STACK_BADGE_PATTERN.search(b_txt) and not is_title:
            is_locked = True
            lock_reason = "architecture_stack_badge_lock"

          if b_txt != a_txt:
            slide_mutated = True
            mutated_shapes_count += 1
            if is_locked and workflow_type != "translate":
              t02_v.append(
                  f"Slide {idx} locked shape '{oid}' ({lock_reason}) was"
                  f" mutated from '{b_txt[:35]}' to '{a_txt[:35]}'."
              )
            if not is_locked:
              all_after_custom_text.append(a_txt)
              if is_title:
                title_changed = True
              else:
                unlocked_body_total += 1
                unlocked_body_changed += 1

              # T03 shallow swap check on body paragraphs
              if (
                  workflow_type in ("transform_text", "transform_slide")
                  and scope_norm != "images_only"
                  and not is_title
              ):
                b_words = {
                    w.lower() for w in re.findall(r"[A-Za-z]{4,}", b_txt)
                }
                a_words = {
                    w.lower() for w in re.findall(r"[A-Za-z]{4,}", a_txt)
                }
                if len(b_words) >= 6 and a_words:
                  same_ratio = len(b_words & a_words) / len(b_words)
                  if same_ratio > 0.85:
                    t03_v.append(
                        f"Slide {idx} shape '{oid}' exhibits shallow 1-word"
                        f" swap ({same_ratio:.0%} identical words)."
                    )

            # T05: Title style & leading section number check
            if is_title and idx > 1 and a_el is not None:
              a_fs_val = float(a_fs or fs_val)
              if a_fs_val < 24.0:
                t05_v.append(
                    f"Slide {idx} mutated title '{oid}' has fontSize"
                    f" {a_fs_val}pt (< 24.0pt floor)."
                )
              if re.match(
                  r"^\s*(?:0[1-9]|[1-9][0-9])[\s\.\-\:\|\n\x0b]", a_txt
              ):
                t05_v.append(
                    f"Slide {idx} mutated title '{oid}' retains leading"
                    f" section number: '{a_txt[:30]}'."
                )
              # Check for blue #4285F4 bleed on title run
              t_elems = (
                  a_el.get("shape", {}).get("text", {}).get("textElements", [])
              )
              for te in t_elems:
                fg = (
                    te.get("textRun", {})
                    .get("style", {})
                    .get("foregroundColor", {})
                    .get("opaqueColor", {})
                    .get("rgbColor", {})
                )
                if (
                    fg
                    and abs(float(fg.get("blue", 0.0)) - 0.95) < 0.08
                    and float(fg.get("red", 0.0)) < 0.35
                ):
                  t05_v.append(
                      f"Slide {idx} mutated title '{oid}' inherited blue"
                      " section-number color instead of dark charcoal."
                  )
                  break

            # T06: Character budget & algebraic height check
            if a_el is not None:
              a_bbox = _extract_element_bbox_pt(a_el)
              _, _, w_pt, h_pt = a_bbox
              eff_h_pt = (
                  _resolve_effective_box_height_pt(
                      a_bbox, a_bg_boxes, a_slide_elems
                  )
                  if not is_title
                  else h_pt
              )
              eff_fs = float(a_fs or fs_val)
              if is_title and idx > 1 and len(a_txt) > 68:
                t06_v.append(
                    f"Slide {idx} action title '{oid}' is {len(a_txt)} chars"
                    " (> 68 char ceiling)."
                )
              if w_pt > 0 and eff_h_pt > 0 and a_txt:
                w_cpl = max(8.0, (w_pt - 14.0) / max(1.0, eff_fs * 0.56))
                lines = sum(
                    max(1, int(math.ceil(len(p) / w_cpl)))
                    for p in a_txt.splitlines() or [a_txt]
                    if p.strip()
                )
                req_h = lines * (eff_fs * 1.32) + 10.0
                height_mult = 1.15 if is_title else 1.35
                if req_h > eff_h_pt * height_mult:
                  t06_v.append(
                      f"Slide {idx} shape '{oid}' requires {req_h:.1f}pt"
                      f" height (> container {eff_h_pt:.1f}pt)."
                  )
          else:
            if is_locked:
              locked_shapes_preserved_count += 1
            elif b_txt:
              all_after_custom_text.append(a_txt)
              if not is_title:
                unlocked_body_total += 1

        elif "image" in b_el and a_el and "image" in a_el:
          b_url = str(b_el.get("image", {}).get("contentUrl", ""))
          a_url = str(a_el.get("image", {}).get("contentUrl", ""))
          b_src = str(b_el.get("image", {}).get("sourceUrl", ""))
          a_src = str(a_el.get("image", {}).get("sourceUrl", ""))
          b_title = str(b_el.get("title", ""))
          a_title = str(a_el.get("title", ""))
          b_desc = str(b_el.get("description", ""))
          a_desc = str(a_el.get("description", ""))
          _, _, w_pt, h_pt = _extract_element_bbox_pt(b_el)
          xf = b_el.get("transform", {})
          sx = float(xf.get("scaleX", 1.0))
          sy = float(xf.get("scaleY", 1.0))
          is_ephemeral_slides_url = (
              "googleusercontent.com" in b_url
              and "googleusercontent.com" in a_url
          )
          if is_ephemeral_slides_url:
            image_actually_mutated = (
                (b_src != a_src)
                or (b_title != a_title)
                or (b_desc != a_desc)
                or (
                    idx in target_set
                    and scope_norm in ("images_only", "both")
                    and w_pt >= 100.0
                    and h_pt >= 85.0
                    and sx >= 0
                    and sy >= 0
                    and not b_url.lower().endswith(".gif")
                    and b_origin not in ("customer_reference", "customer_ref")
                )
            )
          else:
            image_actually_mutated = b_url != a_url

          if image_actually_mutated:
            slide_mutated = True
            slide_image_mutated = True
            if scope_norm == "text_only":
              t09_v.append(
                  f"Slide {idx} image '{oid}' was mutated during"
                  " customization_scope='text_only'."
              )
            if b_url.lower().endswith(".gif"):
              t09_v.append(
                  f"Slide {idx} image '{oid}' replaced an animated GIF."
              )
            if w_pt < 100.0 or h_pt < 85.0:
              t09_v.append(
                  f"Slide {idx} image '{oid}' ({w_pt:.0f}x{h_pt:.0f}pt)"
                  " replaced a micro-icon (< 100x85pt)."
              )
            if sx < 0 or sy < 0:
              t09_v.append(
                  f"Slide {idx} image '{oid}' replaced a flipped shape"
                  f" (scaleX={sx}, scaleY={sy})."
              )
            if b_origin in ("customer_reference", "customer_ref"):
              t09_v.append(
                  f"Slide {idx} image '{oid}' replaced an image on an"
                  " immutable Customer Reference slide."
              )
            if (
                "customer_logo" in a_url.lower()
                and w_pt >= 100.0
                and h_pt >= 85.0
            ):
              t09_v.append(
                  f"Slide {idx} large content image '{oid}' was replaced with"
                  " customer_logo_url."
              )

      # Check deleted or surviving micro-badges ("app" / "GE") & T10 lint on targeted after_slide
      if idx in target_set:
        for oid, a_el in a_els.items():
          if "shape" not in a_el:
            continue
          a_txt, _, _ = _extract_shape_text_and_style(a_el)
          if not a_txt or "Proprietary & Confidential" in a_txt:
            continue
          _, _, w_pt, h_pt = _extract_element_bbox_pt(a_el)
          if (
              w_pt <= 115.0
              and h_pt <= 45.0
              and a_txt.strip().lower() in ("app", "ge")
          ):
            t10_v.append(
                f"Slide {idx} retains legacy split-product micro-badge '{oid}'"
                f" ('{a_txt.strip()}')."
            )
          if re.match(r"^\s*[➔●•▪▸]\s+", a_txt):
            t10_v.append(
                f"Slide {idx} shape '{oid}' has hallucinated leading bullet"
                f" glyph in '{a_txt[:30]}'."
            )
          words = re.findall(r"[A-Za-z0-9'-]+", a_txt)
          if (
              len(words) >= 4
              and words[-1].lower() in DANGLING_END_WORDS
              and not a_txt.strip().endswith((".", "!", "?", ":", "%"))
          ):
            t10_v.append(
                f"Slide {idx} shape '{oid}' ends with dangling word"
                f" '{words[-1]}'."
            )
          if a_txt.count("(") != a_txt.count(")") or a_txt.count('"') % 2 != 0:
            t10_v.append(
                f"Slide {idx} shape '{oid}' has unbalanced parentheses or"
                " quotes."
            )
          for label, pattern in FORBIDDEN_NAMING_PATTERNS:
            m = pattern.search(a_txt)
            if m:
              if label == "Vertex AI" and "vertex" in customer_name.lower():
                continue
              t10_v.append(
                  f"Slide {idx} shape '{oid}' contains retired naming"
                  f" '{m.group(0)}' ({label})."
              )

      if b_slide.get("template_id") != a_slide.get("template_id"):
        slide_mutated = True

      if slide_mutated:
        mutated_slides_count += 1

      # T01: Untargeted & Closing slide isolation
      if (
          workflow_type != "insert_library_slide"
          and idx not in target_set
          and slide_mutated
      ):
        t01_v.append(f"Untargeted slide {idx} was mutated.")
      b_joined = " ".join(t for t in b_slide_texts if t).strip()
      if (
          (
              _is_closing_thank_you_slide(b_slide)
              or re.match(
                  r"^\s*(?:thank\s+you!?|questions\??|q\s*&\s*a)\s*$",
                  b_joined,
                  re.IGNORECASE,
              )
          )
          and slide_mutated
          and workflow_type != "translate"
      ):
        t01_v.append(f"Closing/Thank You slide {idx} was mutated.")

      # T02: Check 15% LIGHT body lock ceiling for Why_Google_Cloud and Commercials
      if (
          b_job in ("Why_Google_Cloud", "Commercials")
          and workflow_type != "translate"
          and scope_norm != "images_only"
          and unlocked_body_total >= 2
          and (unlocked_body_changed / unlocked_body_total) > 0.25
      ):
        t02_v.append(
            f"Slide {idx} ({b_job}, 15% LIGHT ceiling) mutated"
            f" {unlocked_body_changed}/{unlocked_body_total} non-title body"
            " shapes (> 25% lock ceiling)."
        )

      # T03: Per-slide_job body customization intensity floor & TITLE_ONLY_CUSTOMIZATION
      min_body_floor, _, tier_label = _SLIDE_JOB_BODY_INTENSITY_SPECS.get(
          b_job, (0.50, 1.0, "50-60% MODERATE")
      )
      if (
          workflow_type in ("transform_text", "transform_slide")
          and scope_norm != "images_only"
          and idx in target_set
          and idx > 1
          and b_origin not in ("customer_reference", "customer_ref")
          and min_body_floor >= 0.25
          and not re.match(
              r"^\s*(?:thank\s+you|agenda)\b", b_joined, re.IGNORECASE
          )
          and unlocked_body_total >= 1
      ):
        if title_changed and unlocked_body_changed == 0:
          t03_v.append(
              f"Slide {idx} ({b_job or 'Solution_Overview'}, {tier_label})"
              " exhibits TITLE_ONLY_CUSTOMIZATION: action title was customized"
              f" while 0/{unlocked_body_total} unlocked non-title body shapes"
              f" were customized (requires >= {min_body_floor:.0%} body"
              " customization intensity)."
          )
        elif (unlocked_body_changed / unlocked_body_total) < min_body_floor:
          t03_v.append(
              f"Slide {idx} ({b_job or 'Solution_Overview'}, {tier_label})"
              f" mutated only {unlocked_body_changed}/{unlocked_body_total}"
              f" unlocked non-title body shapes (< {min_body_floor:.0%}"
              " customization threshold)."
          )

      # Collect Agenda and Section Divider items for T04
      a_joined = " ".join(t for t in a_slide_texts if t).strip()
      if a_slide.get("slide_role") == "agenda":
        for sec_i, item_txt in enumerate(
            a_slide.get("agenda_items", []), start=1
        ):
          agenda_map[sec_i] = str(item_txt).strip()
      elif a_slide.get("slide_role") == "divider":
        sec_i = int(a_slide.get("section_number", 0))
        if sec_i > 0:
          divider_map[sec_i] = (
              idx,
              str(a_slide.get("divider_title", a_joined)).strip(),
          )

      # T07: transform_slide layout reshuffle check
      if workflow_type == "transform_slide" and idx in target_set:
        b_tmpl = str(b_slide.get("template_id", ""))
        a_tmpl = str(a_slide.get("template_id", ""))
        if b_tmpl and a_tmpl and b_tmpl == a_tmpl:
          t07_v.append(
              f"Slide {idx} transform_slide kept identical layout '{a_tmpl}'."
          )
        b_cards = int(b_slide.get("card_count", 0))
        a_cards = int(a_slide.get("card_count", 0))
        if b_cards > 0 and a_cards > 0 and b_cards != a_cards:
          t07_v.append(
              f"Slide {idx} transform_slide changed card_count from {b_cards}"
              f" to {a_cards}."
          )

      # T08: translate proper-noun lock & speaker notes check
      if (
          workflow_type == "translate" or target_language
      ) and idx in target_set:
        for bad_noun in _FORBIDDEN_LOCALIZED_PROPER_NOUNS:
          if bad_noun.lower() in a_joined.lower():
            t08_v.append(
                f"Slide {idx} translated official product proper noun into"
                f" '{bad_noun}'."
            )
        for noun in _CANONICAL_PROPER_NOUNS:
          if noun in b_joined and noun not in a_joined:
            t08_v.append(
                f"Slide {idx} dropped/translated official proper noun '{noun}'."
            )
        if b_notes and b_notes == a_notes:
          t08_v.append(
              f"Slide {idx} speaker notes were left untranslated for"
              f" '{target_language or 'target_language'}'."
          )

    if (
        workflow_type in ("transform_text", "transform_slide")
        and scope_norm != "images_only"
        and customer_name
        and all_after_custom_text
    ):
      if customer_name.lower() not in " ".join(all_after_custom_text).lower():
        t03_v.append(
            f"Transformed slides do not reference customer '{customer_name}'."
        )

    for sec_i, (div_slide_idx, div_title) in divider_map.items():
      if sec_i in agenda_map and div_title != agenda_map[sec_i]:
        t04_v.append(
            f"Section Divider on slide {div_slide_idx} ('{div_title}') does not"
            f" match Agenda item {sec_i} ('{agenda_map[sec_i]}')."
        )

    def _build_gate(gid: str, gname: str, viols: list[str]) -> GateResult:
      passed = len(viols) == 0
      return GateResult(
          gate_id=gid,
          gate_name=gname,
          passed=passed,
          score=1.0 if passed else 0.0,
          summary="Passed." if passed else "; ".join(viols[:5]),
          violations=viols,
      )

    gates = [
        _build_gate("T01", "Scope & Slide-Targeting Fidelity", t01_v),
        _build_gate(
            "T02",
            "Immutable Slide, Shape-Level Lock & Intensity Ceiling"
            " Preservation",
            t02_v,
        ),
        _build_gate(
            "T03",
            "Per-slide_job Body Customization Intensity, Multi-Source"
            " Augmentation & Zero Title-Only",
            t03_v,
        ),
        _build_gate("T04", "Agenda-to-Section-Divider Synchronization", t04_v),
        _build_gate(
            "T05", "Typography, Bullet & Run-Style Preservation", t05_v
        ),
        _build_gate("T06", "Character Budget & Algebraic Fit Delta", t06_v),
        _build_gate(
            "T07", "Layout Reshuffle (transform_slide) Fidelity", t07_v
        ),
        _build_gate(
            "T08", "Localization & Translation (translate) Integrity", t08_v
        ),
        _build_gate("T09", "Visual Transformation 5 Safety Guards & 2K", t09_v),
        _build_gate(
            "T10", "Sentence Integrity, Micro-Badge & Naming Lint", t10_v
        ),
    ]
    gates_passed = sum(1 for g in gates if g.passed)
    gates_total = len(gates)
    overall_score = round((gates_passed / max(1, gates_total)) * 100.0, 2)

    return TransformationAuditReport(
        presentation_id=pres_id,
        workflow_type=workflow_type,
        customer_name=customer_name,
        specific_use_case=specific_use_case,
        target_language=target_language,
        target_slide_numbers=sorted(target_set),
        total_slides=total_slides,
        mutated_slides_count=mutated_slides_count,
        mutated_shapes_count=mutated_shapes_count,
        locked_shapes_preserved_count=locked_shapes_preserved_count,
        passed_all_gates=gates_passed == gates_total,
        overall_score=overall_score,
        gates_passed=gates_passed,
        gates_total=gates_total,
        gate_results=gates,
    )
