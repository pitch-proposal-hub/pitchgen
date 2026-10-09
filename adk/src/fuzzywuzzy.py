"""Lightweight stdlib implementation of fuzzywuzzy.fuzz and fuzzywuzzy.process for PitchGen RetrievalAgent."""

from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Callable, Iterable


class _FuzzModule:
  """Stdlib-backed replacement for fuzzywuzzy.fuzz."""

  @staticmethod
  def ratio(s1: str, s2: str) -> int:
    if not s1 and not s2:
      return 100
    if not s1 or not s2:
      return 0
    return int(
        round(
            SequenceMatcher(None, str(s1).lower(), str(s2).lower()).ratio()
            * 100
        )
    )

  @staticmethod
  def partial_ratio(s1: str, s2: str) -> int:
    if not s1 and not s2:
      return 100
    if not s1 or not s2:
      return 0
    shorter, longer = (
        (str(s1).lower(), str(s2).lower())
        if len(str(s1)) <= len(str(s2))
        else (str(s2).lower(), str(s1).lower())
    )
    m = SequenceMatcher(None, shorter, longer)
    blocks = m.get_matching_blocks()
    scores = [0.0]
    for b in blocks:
      if b.size == 0:
        continue
      start = max(0, b.b - b.a)
      sub = longer[start : start + len(shorter)]
      scores.append(SequenceMatcher(None, shorter, sub).ratio())
    return int(round(max(scores) * 100))

  @staticmethod
  def token_set_ratio(s1: str, s2: str) -> int:
    if not s1 and not s2:
      return 100
    if not s1 or not s2:
      return 0
    t1 = set(re.findall(r"[a-z0-9]+", str(s1).lower()))
    t2 = set(re.findall(r"[a-z0-9]+", str(s2).lower()))
    if not t1 or not t2:
      return _FuzzModule.ratio(s1, s2)
    inter = sorted(t1 & t2)
    diff1 = sorted(t1 - t2)
    diff2 = sorted(t2 - t1)

    sect = " ".join(inter)
    combined_1 = (sect + " " + " ".join(diff1)).strip()
    combined_2 = (sect + " " + " ".join(diff2)).strip()

    scores = [
        SequenceMatcher(None, combined_1, combined_2).ratio(),
    ]
    if sect:
      scores.append(SequenceMatcher(None, sect, combined_1).ratio())
      scores.append(SequenceMatcher(None, sect, combined_2).ratio())
    return int(round(max(scores) * 100))


class _ProcessModule:
  """Stdlib-backed replacement for fuzzywuzzy.process."""

  @staticmethod
  def extract(
      query: str,
      choices: Iterable[str],
      scorer: Callable[[str, str], int] | None = None,
      limit: int = 5,
  ) -> list[tuple[str, int]]:
    score_fn = scorer or _FuzzModule.ratio
    scored = [(c, int(score_fn(query, c))) for c in choices]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]


fuzz = _FuzzModule()
process = _ProcessModule()
