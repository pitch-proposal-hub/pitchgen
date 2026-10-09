"""Automated Zero-Leak Sanitization Audit for the PitchGen Solution Accelerator."""

from __future__ import annotations

import os
from pathlib import Path
import re

PACKAGE_ROOT = Path(__file__).resolve().parents[3]

FORBIDDEN_PATTERNS: dict[str, re.Pattern[str]] = {
    "google3_ref": re.compile(r"\bgoogle3\b", re.IGNORECASE),
    "go_shortlink": re.compile(r"(?:https?://)?\bgo/[a-zA-Z0-9_-]{2,}"),
    "internal_ldaps": re.compile(
        r"\b(?:ensaiz|varundm|gnagpal|mirchandania|cbunge|phub-genai-help)\b",
        re.IGNORECASE,
    ),
    "google_email": re.compile(
        r"[a-zA-Z0-9_.+-]+@google\.com\b", re.IGNORECASE
    ),
    "internal_gcp_projects": re.compile(
        r"\b(?:pitch-gen-(?:p2-qa|p2-dev|uat|prod|boq|server|dev-p2)|gcbp-agentspace)\b",
        re.IGNORECASE,
    ),
    "internal_project_numbers": re.compile(
        r"\b(?:654636733876|406735450337|1087006617075|598364513914|296281776133|2521797538269364224)\b"
    ),
    "internal_buckets": re.compile(
        r"\b(?:content-uploading-|temp-sort-|slides-deck-dumps-|python_backend-)[a-zA-Z0-9_-]*\b",
        re.IGNORECASE,
    ),
    "internal_appscript_ids": re.compile(
        r"(?:AKfycb[a-zA-Z0-9_-]{20,}|1Nf1JD2UKV6GcI4p_QGHPARL0_ZPIZc2iatSC7DIDZaEd5it7f04sad-p)"
    ),
    "internal_storylab_moma_bq": re.compile(
        r"\b(?:storylab|moma|cloud_cpe_surveys|cloud_blockers_data|customerreferencelibrary|whichcrm|geNamingUpdate|sales-play-reusabl_)\b",
        re.IGNORECASE,
    ),
    "internal_doc_id": re.compile(
        r"1cxELnvoWNG4c8n4uB50BuS17DlCKbupTbh90-2rTTDM"
    ),
    "raw_google_deck_id": re.compile(r"\b1[a-zA-Z0-9_-]{42,44}\b"),
}

ALLOWED_43_CHAR_TOKENS = {
    "1234567890123456789012345678901234567890123",
    "1AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    "1BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
    "1ACTIVEACTIVEACTIVEACTIVEACTIVEACTIVEACTIV",
}


def test_zero_internal_knowledge_leaks() -> None:
  """Scans all files in the Solution Accelerator and asserts zero internal references."""
  violations: list[str] = []
  scanned_count = 0

  for root, dirs, files in os.walk(PACKAGE_ROOT):
    dirs[:] = [
        d for d in dirs if d not in ("__pycache__", ".pytest_cache", ".venv")
    ]
    for fname in sorted(files):
      fpath = Path(root) / fname
      if fpath.name == "test_sanitization_audit.py":
        continue
      try:
        content = fpath.read_text(encoding="utf-8")
      except UnicodeDecodeError:
        continue
      scanned_count += 1
      rel = fpath.relative_to(PACKAGE_ROOT)

      for rule_name, pattern in FORBIDDEN_PATTERNS.items():
        scan_text = (
            re.sub(r"data:image/[^;]+;base64,[A-Za-z0-9+/=]+", "", content)
            if rule_name == "raw_google_deck_id"
            else content
        )
        for m in pattern.finditer(scan_text):
          matched_val = m.group(0)
          if (
              rule_name == "raw_google_deck_id"
              and matched_val in ALLOWED_43_CHAR_TOKENS
          ):
            continue
          line_no = scan_text.count("\n", 0, m.start()) + 1
          violations.append(f"{rel}:{line_no} [{rule_name}] -> {matched_val}")

  assert scanned_count >= 150, f"Expected >=150 files scanned, got {scanned_count}"
  assert not violations, (
      f"Found {len(violations)} sanitization violations:\n"
      + "\n".join(violations[:50])
  )
