"""Foundation deck discovery workflow for radically prioritizing core GTM assets."""

import re
from typing import Any, Dict, List, Optional
from agents.skill_loader import INDUSTRY_VERTICAL_REGISTRY, resolve_required_sales_plays, split_sales_plays_safely
from agents.workflows.base_workflow import BaseWorkflow
from agents.workflows.slide_retriever_factory import SlideRetrieverFactory


class FoundationDeckWorkflow(BaseWorkflow):
  """Discovers and extracts structural pillars from golden foundation decks using logic-driven semantic scoring."""

  def __init__(self, config: Dict[str, Any]):
    super().__init__(
        "FoundationDeckWorkflow",
        "Discovers and extracts structural pillars from core GTM foundation decks.",
    )
    self.config = config

  def resolve_closest_industry(self, context: Dict[str, Any]) -> str:
    """Determines the closest industry vertical cluster for the customer context."""
    ind = str(context.get("industry") or "").strip()
    sub_ind = str(context.get("sub_industry") or "").strip()
    cust = str(context.get("customer_name") or "").strip()
    biz_ctx = str(
        context.get("user_request") or context.get("business_context") or ""
    ).strip()
    comb = f"{ind} {sub_ind} {cust} {biz_ctx}".lower()

    # 1. Direct match with explicit industry parameter if provided
    if ind and ind.lower() not in (
        "none",
        "n/a",
        "cross-industry",
        "generic",
        "agnostic",
    ):
      # Exact or word boundary match on cluster name first (e.g. Retail -> Retail & Consumer)
      for _, meta in INDUSTRY_VERTICAL_REGISTRY.items():
        cluster = str(meta.get("cluster") or "")
        if re.search(r"\b" + re.escape(ind.lower()) + r"\b", cluster.lower()):
          return cluster

      # Exact token match on registered scopes (no loose substring collisions)
      for _, meta in INDUSTRY_VERTICAL_REGISTRY.items():
        cluster = str(meta.get("cluster") or "")
        if ind.lower() in [s.lower() for s in meta.get("scope", [])]:
          return cluster

      return ind

    # 2. Dynamic scoring across all registered industry vertical scopes in INDUSTRY_VERTICAL_REGISTRY
    cluster_scores = {}
    comb_tokens = set(re.findall(r"\w+", comb))
    for _, meta in INDUSTRY_VERTICAL_REGISTRY.items():
      cluster = str(meta.get("cluster") or "")
      if not cluster:
        continue
      scope_words = meta.get("scope", [])
      cluster_keywords = set(re.findall(r"\w+", cluster.lower())) - {
          "and",
          "for",
          "the",
          "in",
          "of",
          "services",
      }
      matches = 0
      for kw in cluster_keywords:
        if kw in comb_tokens:
          matches += 2
      for w in scope_words:
        if " " in w:
          if re.search(r"\b" + re.escape(w) + r"\b", comb):
            matches += 1
        elif len(w) >= 3 and w in comb_tokens:
          matches += 1
      if matches > 0:
        cluster_scores[cluster] = cluster_scores.get(cluster, 0) + matches

    if cluster_scores:
      return max(cluster_scores, key=cluster_scores.get)

    return (
        "Technology"
        if any(
            k in comb
            for k in ("software vendor", "semiconductor", "cloud provider")
        )
        else "Cross-Industry"
    )

  def resolve_active_segment(self, context: Dict[str, Any]) -> str:
    """Resolves customer segment (Corporate, SMB, Enterprise/Strategic)."""
    seg = str(
        context.get("segment")
        or context.get("customer_segment")
        or ""
    ).strip().lower()
    if seg in ("corporate", "corp", "commercial", "mid-market", "mid market", "mmb"):
      return "Corporate"
    if seg in ("smb", "small business", "small and medium business", "startups"):
      return "SMB"
    if seg in ("enterprise", "strategic", "select"):
      return "Enterprise"

    # Infer from audience if provided
    aud_list = (
        [str(a).lower() for a in context.get("audience", [])]
        if isinstance(context.get("audience"), list)
        else [str(context.get("audience", "")).lower()]
    )
    for a in aud_list:
      if any(k in a for k in ("corporate", "corp", "commercial", "mid-market")):
        return "Corporate"
      if "smb" in a or "small business" in a:
        return "SMB"

    # Check user request / business context
    biz_ctx = str(
        context.get("user_request") or context.get("business_context") or ""
    ).lower()
    if re.search(r"\b(corporate|mid-market|commercial)\b", biz_ctx):
      return "Corporate"
    if re.search(r"\b(smb|small business)\b", biz_ctx):
      return "SMB"

    return "Enterprise"

  def evaluate_deck_affinity(
      self,
      deck_data: Dict[str, Any],
      target_play: str,
      context: Dict[str, Any],
      is_technical: bool,
  ) -> float:
    """Calculates semantic and domain affinity of a candidate anchor deck against active context."""
    title = str(
        deck_data.get("deck_title")
        or deck_data.get("title")
        or deck_data.get("name")
        or deck_data.get("original_title")
        or ""
    )
    summary = str(deck_data.get("content") or deck_data.get("desc") or "")
    t_low = title.lower()

    # 1. Language validation: reject translated/localized decks unless explicitly requested.
    # NOTE: In Google Cloud sales assets, '(pt)' designates PLATINUM tier sales play decks, NOT Portuguese!
    # Portuguese localized decks are designated by '(portuguese)' or '(pt-br)'.
    user_lang = str(context.get("language", "English")).lower()
    for lang_code, lang_name in [
        ("(portuguese)", "portug"),
        ("(pt-br)", "portug"),
        ("(espanol)", "span"),
        ("(spanish)", "span"),
        ("(ja)", "japan"),
        ("(japanese)", "japan"),
        ("(french)", "french"),
        ("(german)", "german"),
        ("(italian)", "italian"),
        ("(korean)", "korean"),
    ]:
      if lang_code in t_low and lang_name not in user_lang:
        return -100.0

    # 2. Sales Play Semantic Alignment & Unrequested Play Isolation
    from agents.skill_loader import is_orthogonal_sales_play, is_orthogonal_industry_vertical, is_workspace_explicitly_requested

    # Strict Workspace Isolation: Reject workspace decks unless explicitly requested
    is_workspace_deck = any(
        kw in t_low for kw in ["workspace", "google workspace", "workspace ai", "gws"]
    )
    if is_workspace_deck and not is_workspace_explicitly_requested(context):
      return -100.0

    play_ctx = dict(context or {})
    if target_play:
      existing_plays = (
          play_ctx.get("salesPlay")
          or play_ctx.get("sales_play")
          or play_ctx.get("sales_plays")
          or play_ctx.get("salesPlays")
      )
      if not existing_plays:
        play_ctx["salesPlay"] = [target_play]
      elif (
          isinstance(existing_plays, list) and target_play not in existing_plays
      ):
        play_ctx["salesPlay"] = list(existing_plays) + [target_play]
      elif (
          isinstance(existing_plays, str)
          and target_play.lower() not in existing_plays.lower()
      ):
        play_ctx["salesPlay"] = [existing_plays, target_play]
    conflicting_play = is_orthogonal_sales_play(title, deck_data, play_ctx)
    if conflicting_play:
      return -100.0

    target_play_clean = target_play.lower().replace("_", " ")
    play_words = set(re.findall(r"\w+", target_play_clean))
    title_words = set(re.findall(r"\w+", t_low))
    play_overlap = len(play_words.intersection(title_words))

    play_score = float(play_overlap) * 2.0
    if any(k in t_low for k in target_play_clean.split() if len(k) > 3):
      play_score += 3.0
    if (
        "gemini enterprise" in target_play_clean
        or "gemini enterprise"
        in str(context.get("business_context", "")).lower()
        or "gemini enterprise" in str(context.get("user_request", "")).lower()
    ) and "gemini enterprise" in t_low:
      play_score += 8.0

    # 3. Dynamic Industry Vertical Domain Compatibility
    conflicting_vertical = is_orthogonal_industry_vertical(
        title, deck_data, context
    )
    if conflicting_vertical:
      return -100.0

    active_industry = str(
        context.get("closest_industry") or context.get("industry") or ""
    ).lower()

    # Check if deck specifically matches target vertical for a positive boost
    deck_vertical_cluster = None
    for _, meta in INDUSTRY_VERTICAL_REGISTRY.items():
      for scope_word in meta.get("scope", []):
        if len(scope_word) >= 3 and re.search(
            rf"(?:^|[^a-z0-9]){re.escape(scope_word)}(?:$|[^a-z0-9])", t_low
        ):
          deck_vertical_cluster = meta.get("cluster")
          break
      if deck_vertical_cluster:
        break

    if deck_vertical_cluster:
      cluster_low = deck_vertical_cluster.lower()
      if (
          active_industry
          and active_industry
          not in ("generic", "cross-industry", "agnostic", "none", "n/a")
          and (cluster_low in active_industry or active_industry in cluster_low)
      ):
        industry_score = 5.0
      else:
        # Deck is explicitly scoped to a different industry vertical (e.g. 'Retail | ...' for a Healthcare/Energy customer)
        return -100.0
    else:
      industry_score = 2.0

    # 4. Customer Segment Gating: Corporate vs. SMB vs. Enterprise
    active_segment = self.resolve_active_segment(context)
    is_corp_deck = any(k in t_low for k in ["[corporate]", "[corp]", "mmb_"])
    is_smb_deck = "[smb]" in t_low

    segment_score = 0.0
    if is_corp_deck:
      if active_segment != "Corporate":
        return -100.0
      segment_score = 4.0
    elif is_smb_deck:
      if active_segment != "SMB":
        return -100.0
      segment_score = 4.0
    else:
      segment_score = 0.0

    # 5. Technical vs Business Track Alignment (Strictly disqualify L200 / Technical Sales Play decks in S0, S1, or non-technical tracks)
    is_tech_deck = any(
        w in t_low
        for w in [
            "technical",
            "tech pitch",
            "techpitch",
            "architecture",
            "blueprint",
            "deep dive",
            "l200",
            "l300",
        ]
    )
    win_stage_chk = (
        str(context.get("sales_stage") or context.get("win_cycle") or "S1")
        .strip()
        .upper()
    )
    if is_tech_deck and (not is_technical or win_stage_chk in ("S0", "S1")):
      return -100.0

    track_score = 0.0
    if is_technical and is_tech_deck:
      track_score = 3.0
    elif not is_technical and not is_tech_deck:
      track_score = 3.0

    return play_score + industry_score + track_score + segment_score

  def execute(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Discovers golden foundation decks matching the active GTM sales plays and industry context."""
    business_context = (
        context.get("user_request") or context.get("business_context") or ""
    )
    customer_name = context.get("customer_name") or ""
    industry = context.get("industry") or ""
    sub_industry = context.get("sub_industry") or ""
    # Dynamically analyze user prompt AND optional dropdown fields to determine all required Sales Plays
    required_sales_plays = resolve_required_sales_plays(context)
    if required_sales_plays:
      sales_plays = list(required_sales_plays)
      context["required_sales_plays"] = required_sales_plays
      context["sales_plays"] = required_sales_plays
      context["salesPlay"] = required_sales_plays
    else:
      raw_sales_plays = (
          context.get("salesPlay")
          or context.get("sales_play")
          or context.get("sales_plays")
          or []
      )
      sales_plays = split_sales_plays_safely(raw_sales_plays)
      context["required_sales_plays"] = sales_plays

    print(
        f"[{self.name}] Required sales plays analyzed: {sales_plays} "
        f"({len(sales_plays)} anchor decks required)"
    )
    ctx_lower = str(business_context).lower()

    # Clean query of specific customer name
    clean_query = business_context
    if customer_name:
      clean_query = re.sub(
          re.escape(customer_name), "", clean_query, flags=re.IGNORECASE
      ).strip()
    clean_query = re.sub(r"\s+", " ", clean_query)

    sp_ds = "your-sales-play-slides-datastore-id"
    if "reusable" in self.config:
      sp_ds = self.config["reusable"].get("sales_play_reusables", sp_ds)

    datastores_to_check = [
        ("sales_play_reusables", sp_ds),
    ]
    discovered_anchors: List[Dict[str, Any]] = []
    seen_deck_ids = set()

    def add_anchor(
        deck_id: str,
        title: str,
        play_label: str,
        reason: str,
        ds_key: str,
        summary: str,
    ):
      if deck_id not in seen_deck_ids:
        seen_deck_ids.add(deck_id)
        discovered_anchors.append({
            "deck_id": deck_id,
            "deck_title": title,
            "sales_play": play_label,
            "match_reason": reason,
            "source_datastore": ds_key,
            "group_summary": summary,
        })
        print(
            f"[{self.name}] Discovered Anchor Deck: '{title}' ({deck_id}) for"
            f" [{play_label}]"
        )

    # Detect whether the request calls for a Technical Pitch Deck vs. Default Business Pitch Deck
    aud_list = (
        [str(a).lower() for a in context.get("audience", [])]
        if isinstance(context.get("audience"), list)
        else [str(context.get("audience", "")).lower()]
    )
    aud_str_combined = " ".join(aud_list)
    aud_tokens = set(re.findall(r"\b\w+\b", aud_str_combined))
    technical_audiences = {
        "architects",
        "architect",
        "developers",
        "developer",
        "engineers",
        "engineer",
    }
    business_audiences = {
        "ceo",
        "cfo",
        "cmo",
        "cdo",
        "cio",
        "cto",
        "procurement",
        "executive",
        "board",
        "suite",
    }
    is_strictly_technical_aud = bool(
        aud_tokens & technical_audiences
    ) and not bool(aud_tokens & business_audiences)

    active_archetype = context.get("presentation_archetype") or ""
    is_technical_archetype = active_archetype in [
        "Technical_Solutioning_Pitch",
        "Architecture_PoC_Workshop",
        "Practitioner_Technical_Architecture",
        "PoC_Engagement_Proposal",
        "CIO_Technical_Strategy",
        "Technical_Architecture",
    ]

    # WIN Cycle directional steering
    raw_stage = str(context.get("sales_stage") or context.get("win_cycle") or "").strip().upper()
    canonical_stage = "S1"
    if raw_stage in ["S0", "S1", "S2", "S3", "S4", "S0'"]:
      canonical_stage = raw_stage
    elif "S0'" in raw_stage or "OPTIMIZE" in raw_stage or "GROW" in raw_stage:
      canonical_stage = "S0'"
    elif "S0" in raw_stage or "QUALIFY" in raw_stage:
      canonical_stage = "S0"
    elif "S2" in raw_stage or "TECH" in raw_stage:
      canonical_stage = "S2"
    elif "S3" in raw_stage or "PROPOSE" in raw_stage:
      canonical_stage = "S3"
    elif "S4" in raw_stage or "MOBILIZE" in raw_stage:
      canonical_stage = "S4"
    elif "S1" in raw_stage or "POSITION" in raw_stage:
      canonical_stage = "S1"
    elif active_archetype in ("First_Call_Discovery", "Discovery_First_Call"):
      canonical_stage = "S0"
    elif is_technical_archetype:
      canonical_stage = "S2"
    elif active_archetype in (
        "Value_Case_Commercial_Proposal",
        "CFO_Business_Case",
        "Commercial_Proposal",
    ):
      canonical_stage = "S3"
    elif active_archetype in (
        "QBR_Adoption_Expansion",
        "Executive_QBR_Value_Realization",
        "Customer_Adoption_Playbook",
    ):
      canonical_stage = "S4"

    prompt_lower = str(business_context).lower()
    explicit_technical_prompt = any(
        k in prompt_lower
        for k in [
            "technical pitch",
            "tech pitch",
            "architecture deep dive",
            "l200",
            "l300",
        ]
    )
    explicit_business_prompt = any(
        k in prompt_lower
        for k in [
            "business pitch",
            "executive",
            "c-level",
            "ceo",
            "cfo",
            "board",
            "business value",
            "overview",
        ]
    )

    if (
        canonical_stage in ("S0", "S1")
        and not explicit_technical_prompt
        and not is_technical_archetype
    ):
      is_technical = False
    elif (
        explicit_technical_prompt
        or is_strictly_technical_aud
        or is_technical_archetype
    ):
      is_technical = True
    elif explicit_business_prompt or bool(aud_tokens & business_audiences):
      is_technical = False
    elif canonical_stage == "S2":
      is_technical = True  # Directionally steer to Technical Pitch during S2: Tech Solutioning
    else:
      is_technical = False  # Directionally steer to Business Pitch for S0, S1, S3, S4

    active_segment = self.resolve_active_segment(context)
    context["segment"] = active_segment
    context["active_segment"] = active_segment
    context["sales_stage"] = canonical_stage
    context["win_cycle"] = canonical_stage

    track_name = "Technical Pitch" if is_technical else "Business Pitch (Default)"
    print(
        f"[{self.name}] Sales Play discovery track: '{track_name}'"
        f" (Technical intent detected: {is_technical}, WIN Cycle Stage: {canonical_stage}, Segment: {active_segment})"
    )

    closest_industry = self.resolve_closest_industry(context)
    context["closest_industry"] = closest_industry
    print(
        f"[{self.name}] Resolved closest industry cluster for customer:"
        f" '{closest_industry}'"
    )

    # A. Check for Vertical / Industry Foundation Deck
    vertical_queries = []
    if sub_industry and sub_industry.lower() not in [
        "none",
        "n/a",
        "cross-industry",
    ]:
      vertical_queries.append(f"Why Google Cloud for {sub_industry}")
      vertical_queries.append(f"{sub_industry} Business Pitch Deck")
    if industry and industry.lower() not in [
        "none",
        "n/a",
        "cross-industry",
        "cross_industry",
    ]:
      vertical_queries.append(f"Why Google Cloud for {industry}")
      vertical_queries.append(f"{industry} Business Pitch Deck")
    if closest_industry and closest_industry.lower() not in [
        "none",
        "n/a",
        "cross-industry",
    ]:
      vertical_queries.append(f"Why Google Cloud for {closest_industry}")
      vertical_queries.append(f"{closest_industry} Business Pitch Deck")
    vertical_queries.append("Why Google Cloud Business Pitch Deck")
    vertical_queries.append("Why Google Cloud")

    best_vertical_deck = None
    best_vertical_score = 0.0
    best_vertical_ds = ""

    if vertical_queries:

      for ds_key, ds_id in datastores_to_check:
        retriever = SlideRetrieverFactory.get_retriever(
            ds_key, ds_id, self.config
        )
        for q in vertical_queries:
          try:
            results = retriever.search_slides(
                q, {"industry": closest_industry or industry}, limit=8
            )
          except Exception as e:
            print(f"[{self.name}] Error searching {ds_key} for vertical: {e}")
            continue

          for r in results:
            deck_id = r.get("deck_id") or r.get("deckId")
            if not deck_id or deck_id in seen_deck_ids:
              continue

            affinity = self.evaluate_deck_affinity(
                r,
                target_play=(
                    "Why Google Cloud"
                    f" ({closest_industry or industry or 'Vertical'})"
                ),
                context=context,
                is_technical=is_technical,
            )
            if affinity > best_vertical_score:
              best_vertical_score = affinity
              best_vertical_deck = r
              best_vertical_ds = ds_key

      if best_vertical_deck and best_vertical_score > 0:
        v_title = (
            best_vertical_deck.get("deck_title")
            or best_vertical_deck.get("title")
            or best_vertical_deck.get("name")
            or best_vertical_deck.get("original_title")
            or ""
        )
        v_deck_id = best_vertical_deck.get("deck_id") or best_vertical_deck.get(
            "deckId"
        )
        add_anchor(
            deck_id=v_deck_id,
            title=v_title,
            play_label=(
                "Why Google Cloud"
                f" ({closest_industry or industry or 'Vertical'})"
            ),
            reason=(
                f"Why Google Cloud Vertical Foundation Deck ('{v_title}',"
                f" score: {best_vertical_score:.1f})"
            ),
            ds_key=best_vertical_ds,
            summary=best_vertical_deck.get("content", ""),
        )

    # B. Discover Anchor Deck for active Sales Play(s)
    # Ensure sales plays pitch decks are ALWAYS discovered alongside the Why Google vertical deck
    user_req_low = str(context.get("user_request") or context.get("business_context") or "").lower()
    is_generic_why_google = any(k in user_req_low for k in ["why google", "why gcp", "why google cloud", "general pitch", "overview", "pitch deck for", "deck for"]) and not any(k in user_req_low for k in ["sap", "oracle", "vmware", "mandiant", "soc", "hpc", "wan", "netapp", "gdc"])

    if not sales_plays and best_vertical_deck and is_generic_why_google:
      target_plays = []
      print(
          f"[{self.name}] Generic 'Why Google Cloud' pitch for vertical"
          f" '{closest_industry}': Anchoring 100% on vertical foundation deck"
          " without cross-industry dilution."
      )
    else:
      target_plays = list(sales_plays)

    for play in target_plays:
      play_queries = [
          (
              f"{play} Technical Pitch Deck"
              if is_technical
              else f"{play} Business Pitch Deck"
          ),
          f"{play} Playbook",
          f"{play} Pitch Deck",
          f"{play} (pt)",
      ]
      if active_segment == "Corporate":
        play_queries.insert(0, f"[Corporate] {play} Business Pitch Deck")
        play_queries.insert(1, f"[Corporate] {play} Pitch Deck")
        play_queries.insert(2, f"{play} Business Pitch [CORP]")
      elif active_segment == "SMB":
        play_queries.insert(0, f"[SMB] {play} Business Pitch Deck")
        play_queries.insert(1, f"[SMB] {play} Pitch Deck")

      play_low = play.lower()
      if "agentic workplace" in play_low or "workplace transformation" in play_low or "gemini enterprise" in play_low:
        if active_segment == "Corporate":
          play_queries.extend([
              "[Corporate] Agentic Workplace Transformation Business Pitch Deck (pt)",
              "[Corporate] Agentic Workplace Transformation (pt)",
          ])
        elif active_segment == "SMB":
          play_queries.extend([
              "[SMB] Agentic Workplace Transformation Business Pitch Deck (pt)",
              "[SMB] Agentic Workplace Transformation (pt)",
          ])
        elif (
            "gemini enterprise" in play_low or "gemini enterprise" in ctx_lower
        ):
          play_queries.insert(
              0,
              "Gemini Enterprise App Business Pitch Deck"
              " [Enterprise_Business_Pitch] (pt)",
          )
          if is_technical:
            play_queries.insert(
                1,
                "Gemini Enterprise App Technical Pitch Deck"
                " [Enterprise_Technical_Pitch] (pt)",
            )
          play_queries.extend([
              (
                  "Agentic Workplace Transformation Business Pitch Deck"
                  " (Workplace_Transformation_Pitch) (pt)"
              ),
              "Gemini Enterprise (pt)",
              "Agentic Workplace Transformation (pt)",
          ])
          if is_technical:
            play_queries.append(
                "AWT Technical Pitch Deck"
                " (Workplace_Transformation_TechPitch) (pt)"
            )
        else:
          play_queries.extend([
              (
                  "Agentic Workplace Transformation Business Pitch Deck"
                  " (Workplace_Transformation_Pitch) (pt)"
              ),
              (
                  "Gemini Enterprise App Business Pitch Deck"
                  " [Enterprise_Business_Pitch] (pt)"
              ),
              "Agentic Workplace Transformation (pt)",
              "Gemini Enterprise (pt)",
          ])
          if is_technical:
            play_queries.extend([
                (
                    "Gemini Enterprise App Technical Pitch Deck"
                    " [Enterprise_Technical_Pitch] (pt)"
                ),
                (
                    "AWT Technical Pitch Deck"
                    " (Workplace_Transformation_TechPitch) (pt)"
                ),
            ])
      elif "data cloud" in play_low:
        play_queries.insert(
            0, "Agentic Data Cloud Pitch Deck (Agentic_Data_Cloud_Pitch) (pt)"
        )
        play_queries.insert(
            1,
            "Migrate, Modernize, and Build with Data Cloud Pitch"
            " (Modernize_Data_Cloud_Pitch) (pt)",
        )
      elif "genmedia" in play_low or "generative media" in play_low:
        play_queries.extend([
            "GenMedia on Agent Platform Business Pitch (pt)",
            "GenMedia Business Pitch (pt)",
            "GenMedia (pt)",
        ])
      elif "scale ai" in play_low:
        play_queries.extend([
            "Scale AI Apps and Agents Business Pitch (pt)",
            "Scale AI Apps (pt)",
        ])

      scored_play_decks: Dict[str, tuple[float, Dict[str, Any], str]] = {}

      for ds_key, ds_id in datastores_to_check:
        retriever = SlideRetrieverFactory.get_retriever(
            ds_key, ds_id, self.config
        )
        for q in play_queries:
          try:
            results = retriever.search_slides(
                q,
                {"salesPlay": play, "industry": closest_industry or industry},
                limit=8,
            )
          except Exception as e:
            print(f"[{self.name}] Error searching {ds_key} for {play}: {e}")
            continue

          for r in results:
            deck_id = r.get("deck_id") or r.get("deckId")
            if not deck_id or deck_id in seen_deck_ids:
              continue

            affinity = self.evaluate_deck_affinity(
                r, target_play=play, context=context, is_technical=is_technical
            )
            if affinity > 0:
              prev = scored_play_decks.get(deck_id)
              if not prev or affinity > prev[0]:
                scored_play_decks[deck_id] = (affinity, r, ds_key)

      ranked_play_decks = sorted(
          scored_play_decks.values(), key=lambda x: x[0], reverse=True
      )
      if ranked_play_decks:
        best_play_score = ranked_play_decks[0][0]
        # Register the top primary deck plus up to 2 complementary high-affinity decks for the play
        # (e.g., Gemini Enterprise Business Pitch + Gemini Enterprise Technical Pitch + AWT Business Pitch)
        for idx_d, (d_score, d_obj, d_ds) in enumerate(ranked_play_decks[:3]):
          if idx_d > 0 and d_score < best_play_score * 0.55:
            continue
          p_title = (
              d_obj.get("deck_title")
              or d_obj.get("title")
              or d_obj.get("name")
              or d_obj.get("original_title")
              or ""
          )
          p_deck_id = d_obj.get("deck_id") or d_obj.get("deckId")
          add_anchor(
              deck_id=p_deck_id,
              title=p_title,
              play_label=play,
              reason=(
                  f"Sales Play Foundation Deck for '{play}' ('{p_title}',"
                  f" score: {d_score:.1f})"
              ),
              ds_key=d_ds,
              summary=d_obj.get("content", ""),
          )

    if not discovered_anchors:
      return None

    vertical_anchor = None
    solution_anchors = []

    for a in discovered_anchors:
      p_low = str(a.get("sales_play", "")).lower()
      t_low = str(a.get("deck_title", "")).lower()
      if "why google" in p_low or "why google" in t_low:
        if not vertical_anchor:
          vertical_anchor = a
      else:
        solution_anchors.append(a)

    primary = discovered_anchors[0]
    if solution_anchors:
      primary = solution_anchors[0]
    elif vertical_anchor:
      primary = vertical_anchor

    return {
        "primary_anchor_deck_id": primary["deck_id"],
        "primary_anchor_deck_title": primary["deck_title"],
        "primary_anchor_deck_source": primary["source_datastore"],
        "closest_industry": closest_industry,
        "active_segment": active_segment,
        "win_cycle_stage": canonical_stage,
        "required_sales_plays": list(sales_plays),
        "required_anchor_count": len(solution_anchors) + (1 if vertical_anchor else 0),
        "vertical_anchor": vertical_anchor,
        "solution_anchors": solution_anchors,
        "anchor_decks": discovered_anchors,
        "anchor_deck_ids": [a["deck_id"] for a in discovered_anchors],
        "anchor_deck_map": {
            a["sales_play"]: a["deck_id"] for a in discovered_anchors
        },
    }
