import json
import random
import re
from agents.base_agent import BaseAgent
from agents.workflows.content_synthesis_workflow import ContentSynthesisWorkflow
from agents.workflows.layout_transformer_workflow import LayoutTransformerWorkflow
from agents.workflows.slide_assembly_workflow import SlideAssemblyWorkflow
from agents.workflows.template_mapper_workflow import TemplateMapperWorkflow
from agents.workflows.text_transformer_workflow import TextTransformerWorkflow
from agents.workflows.translation_engine_workflow import TranslationEngineWorkflow


def get_final_content(item, place_holders, agendas, reusable_slides, sources):
  """
    Generate the final presentation content by merging placeholders, agendas, and reusable slides.

    Args:
        place_holders (dict): The placeholders for slide content.
        agendas (dict): The structured agendas.
        reusable_slides (dict): The reusable slide suggestions.
        customer_name (str): The name of the customer.

    Returns:
        dict: The final structured content for the presentation.
    """
  noAgendas = len(agendas.keys())

  # Locate mapping.json dynamically to be robust to different working directories
  import os
  mapping_path = 'config/mapping.json'
  if not os.path.exists(mapping_path):
    import inspect
    caller_file = inspect.getfile(inspect.currentframe())
    caller_dir = os.path.dirname(os.path.abspath(caller_file))
    possible_paths = [
            os.path.join(caller_dir, 'config/mapping.json'),
            os.path.join(caller_dir, '../config/mapping.json'),
            os.path.join(caller_dir, '../../config/mapping.json'),
            os.path.join(caller_dir, 'src/config/mapping.json'),
            os.path.join(caller_dir, '../src/config/mapping.json'),
            os.path.join(caller_dir, '../../src/config/mapping.json'),
            'src/config/mapping.json',
            'config/mapping.json'
        ]
    for path in possible_paths:
      if os.path.exists(path):
        mapping_path = path
        break

  with open(mapping_path,'r') as f:
    mappings = json.loads(f.read())

  sys_rng = random.SystemRandom()
  title_keys = [k for k in mappings["title"].keys() if k != "deckId"]
  title_slide_id = mappings["title"][sys_rng.choice(title_keys)]

  title_slide = {
        "temp_url": (
          f"https://docs.google.com/presentation/d/"
          f"{mappings['title']['deckId']}/edit#slide=id.{title_slide_id}"
        ),
        "placeholders": {"title": item.title}
      }

  agenda_keys = [k for k in mappings["agenda"].keys() if k != "deckId"]
  numeric_agenda_keys = sorted(
      [int(k) for k in agenda_keys if str(k).isdigit()]
  )
  if numeric_agenda_keys:
    clamped_count = str(
        min(max(noAgendas, numeric_agenda_keys[0]), numeric_agenda_keys[-1])
    )
  else:
    clamped_count = str(noAgendas)
  if clamped_count in mappings["agenda"]:
    agenda_slide_id = sys_rng.choice(mappings["agenda"][clamped_count])
  else:
    agenda_slide_id = sys_rng.choice(
        mappings["agenda"][sys_rng.choice(agenda_keys)]
    )

  ph_dict = {}
  for key in agendas.keys():
    ph_dict["agenda"+key] = agendas[key]['title']
  agenda_slide = {
        "temp_url": f"https://docs.google.com/presentation/d/{mappings['agenda']['deckId']}/edit#slide=id.{agenda_slide_id}",
        "placeholders": ph_dict
      }

  thank_keys = [k for k in mappings["thank"].keys() if k != "deckId"]
  thank_slide_id = mappings["thank"][sys_rng.choice(thank_keys)]

  thank_slide = {
        "temp_url": (
          f"https://docs.google.com/presentation/d/"
          f"{mappings['thank']['deckId']}/edit#slide=id."
          f"{thank_slide_id}"
        ),
      }

  sections = {}
  sections["title"] = {"slides": {"1": title_slide}}
  sections["agenda"] = {"slides": {"1": agenda_slide}}

  for i in range(noAgendas):
    agenda_key = str(i + 1)
    # Omit section break / divider slides for a continuous, seamless narrative flow
    if agenda_key in place_holders:
      sections[agenda_key] = place_holders[agenda_key]
    else:
      sections[agenda_key] = {"slides": {}}

    # Update intertwined ordering in reusable_slides suggestions
    if agenda_key in reusable_slides and "suggestions" in reusable_slides[agenda_key]:
      is_closing_section = (noAgendas > 1 and i == noAgendas - 1)
      has_synthetic_roadmap = (
                agenda_key in place_holders
                and place_holders[agenda_key].get("slides")
            )
      for s_idx, reu_sug in enumerate(reusable_slides[agenda_key]["suggestions"], 1):
        # For closing/realization sections with a synthetic implementation roadmap,
        # any supporting reusable slide (e.g. CAF / adoption governance) must precede
        # the roadmap so the presentation culminates with the Joint Implementation Roadmap.
        if is_closing_section and has_synthetic_roadmap:
          reu_sug["intertwined_order"] = 0
        else:
          reu_sug["intertwined_order"] = s_idx

  sections["thank_you"] = {"slides": {"1": thank_slide}}

  finalcontent_struct = {"sections": sections}

  return finalcontent_struct


def extract_entities_from_user_prompt(prompt_text: str) -> dict:
  """Intelligently extracts customer_name, industry, audience, sales_play, opportunity_id, and products from user prompts."""
  if not prompt_text or not isinstance(prompt_text, str):
    return {
        "customer_name": "",
        "industry": "",
        "audience": "",
        "sales_play": "",
        "opportunity_id": "",
        "products": "",
        "user_prompt": "",
    }

  text = prompt_text.strip()
  res = {
      "customer_name": "",
      "industry": "",
      "audience": "",
      "sales_play": "",
      "opportunity_id": "",
      "products": "",
      "user_prompt": text,
  }

  # 1. Opportunity ID / ER Number Extraction
  opp_m = re.search(
      r"\b(?:opportunity\s*id|opp\s*id|er\s*number|er\s*id|opportunity\s*#|opp\s*#)\s*[:=]?\s*([A-Za-z0-9_\-]+)|\b(?:opportunity|opp)\s*[:=]\s*([A-Za-z0-9_\-]+)|\b(ER-?[0-9]+)\b",
      text,
      re.IGNORECASE,
  )
  if opp_m:
    val = (opp_m.group(1) or opp_m.group(2) or opp_m.group(3) or "").strip()
    if val and val.lower() not in ("opportunities", "opportunity"):
      res["opportunity_id"] = val

  # 2. Industry Vertical Extraction
  ind_m = re.search(
      r"\b(?:in|within|focusing\s+on|focus\s+on|towards|to|for)\s+(?:the\s+)?((?:(?!in\b|for\b|to\b|towards\b|with\b)[A-Za-z0-9_&]+)(?:\s+(?!in\b|for\b|to\b|towards\b|with\b)[A-Za-z0-9_&]+){0,3})\s+(?:(?:industry|sector|vertical|domain)\s*)+\b",
      text,
      re.IGNORECASE,
  )
  if not ind_m:
    ind_m = re.search(
        r"\b(?:industry|sector|vertical)\s*[:=]\s*([A-Za-z0-9_&]+(?:\s+[A-Za-z0-9_&]+){0,3})\b",
        text,
        re.IGNORECASE,
    )
  if not ind_m:
    ind_m = re.search(
        r"\b(?:in|within|focusing\s+on|focus\s+on)\s+((?:(?!in\b|for\b|to\b|towards\b|with\b)[A-Za-z0-9_&]+)(?:\s+(?!in\b|for\b|to\b|towards\b|with\b)[A-Za-z0-9_&]+){0,3})(?:,\s*tailoring|\s*\.|\s*$)",
        text,
        re.IGNORECASE,
    )

  if ind_m:
    raw_ind = ind_m.group(1).strip()
    raw_ind = re.sub(
        r"\b(trends|landscape|overview|domain|sector|requirements|industry|vertical)\b",
        "",
        raw_ind,
        flags=re.IGNORECASE,
    ).strip()
    for kw in (
        "with ",
        "for ",
        "in ",
        "towards ",
        "to ",
        "focusing on ",
        "the ",
    ):
      if raw_ind.lower().startswith(kw):
        raw_ind = raw_ind[len(kw) :].strip()
    raw_lower = raw_ind.lower()
    if any(
        k in raw_lower
        for k in ("cpg", "consumer packaged", "consumer goods", "fmcg")
    ):
      res["industry"] = "Consumer Packaged Goods (CPG)"
    elif any(
        k in raw_lower
        for k in (
            "fsi",
            "financial services",
            "banking",
            "fintech",
            "wealth",
            "insurance",
            "finance",
        )
    ):
      res["industry"] = "Financial Services"
    elif any(
        k in raw_lower
        for k in (
            "healthcare",
            "life sciences",
            "hcls",
            "pharma",
            "biotech",
            "hospital",
        )
    ):
      res["industry"] = "Healthcare & Life Sciences"
    elif any(
        k in raw_lower
        for k in (
            "retail",
            "e-commerce",
            "ecommerce",
            "grocery",
            "merchandising",
        )
    ):
      res["industry"] = "Retail & Consumer"
    elif any(
        k in raw_lower
        for k in (
            "telecom",
            "telecommunications",
            "media",
            "entertainment",
            "broadcasting",
        )
    ):
      res["industry"] = "Telecommunications, Media & Entertainment"
    elif any(
        k in raw_lower
        for k in (
            "manufacturing",
            "automotive",
            "supply chain",
            "industrial",
            "aerospace",
        )
    ):
      res["industry"] = "Manufacturing & Industrial"
    elif any(
        k in raw_lower
        for k in (
            "public sector",
            "public",
            "government",
            "education",
            "fed",
            "state & local",
        )
    ):
      res["industry"] = "Public Sector"
    elif any(
        k in raw_lower
        for k in ("energy", "utilities", "oil", "gas", "power", "renewables")
    ):
      res["industry"] = "Energy & Utilities"
    elif any(
        k in raw_lower
        for k in ("tech", "technology", "software", "saas", "digital")
    ):
      res["industry"] = "Technology & Software"
    elif raw_ind:
      res["industry"] = raw_ind.title()
  else:
    for ind_kw, ind_canonical in [
        (
            (
                r"\b(?:financial services|banking|fsi|finance|wealth"
                r" management|insurance|payments)\b"
            ),
            "Financial Services",
        ),
        (
            r"\b(?:consumer packaged goods|cpg|consumer goods|fmcg)\b",
            "Consumer Packaged Goods (CPG)",
        ),
        (
            (
                r"\b(?:healthcare|life"
                r" sciences|hcls|pharma|clinical|biotech|hospital)\b"
            ),
            "Healthcare & Life Sciences",
        ),
        (
            r"\b(?:retail|e-commerce|ecommerce|grocery|merchandising)\b",
            "Retail & Consumer",
        ),
        (
            r"\b(?:telecom|telecommunications|media|entertainment|broadcasting)\b",
            "Telecommunications, Media & Entertainment",
        ),
        (
            (
                r"\b(?:manufacturing|automotive|supply"
                r" chain|logistics|industrial|aerospace)\b"
            ),
            "Manufacturing & Industrial",
        ),
        (
            (
                r"\b(?:public sector|government|defense|education|fed|state &"
                r" local)\b"
            ),
            "Public Sector",
        ),
        (
            r"\b(?:energy|utilities|oil & gas|power|renewables)\b",
            "Energy & Utilities",
        ),
        (r"\b(?:technology|software|saas)\b", "Technology & Software"),
    ]:
      if re.search(ind_kw, text, re.IGNORECASE):
        res["industry"] = ind_canonical
        break

  # 3. Target Audience / Persona Extraction
  aud_m = re.search(
      r"\b(?:audience|target audience|persona|for persona|targeting"
      r" audience|for"
      r" audience|targeting)\s*[:=]?\s*([A-Za-z0-9_&\s\-]+?)(?:,|$|\.|\s+with\b|\s+focusing\b|\s+sales\b|\s+opp\b|\s+products\b)",
      text,
      re.IGNORECASE,
  )
  if aud_m:
    aud_candidate = aud_m.group(1).strip()
    if aud_candidate.lower() in (
        "cio",
        "cto",
        "cdo",
        "cmo",
        "cro",
        "cfo",
        "ceo",
    ):
      res["audience"] = aud_candidate.upper()
    else:
      res["audience"] = aud_candidate.title()
  elif re.search(
      r"\b(?:c-suite|c-level|executives|cio|cto|cdo|cmo|cro|cfo|executive"
      r" leadership)\b",
      text,
      re.IGNORECASE,
  ):
    res["audience"] = "C-Level Executives"
  elif re.search(
      r"\b(?:architects|developers|engineers|technical teams|practitioners)\b",
      text,
      re.IGNORECASE,
  ):
    res["audience"] = "Technical Architects & Engineers"
  elif re.search(
      r"\b(?:business leaders|line of business|operations managers)\b",
      text,
      re.IGNORECASE,
  ):
    res["audience"] = "Business & Operations Leaders"

  # 4. Sales Play Extraction
  sp_m = re.search(
      r"\b(?:sales\s*play|salesplay|play)\s*[:=]?\s*([A-Za-z0-9_&\s\-]+?)(?:,|$|\.|\s+for\b|\s+with\b|\s+targeting\b|\s+opp\b|\s+products\b)",
      text,
      re.IGNORECASE,
  )
  if sp_m:
    res["sales_play"] = sp_m.group(1).strip().title()
  elif re.search(
      r"\b(?:genai adoption|generative ai adoption|ai adoption)\b",
      text,
      re.IGNORECASE,
  ):
    res["sales_play"] = "GenAI Adoption"
  elif re.search(
      r"\b(?:cloud migration|infrastructure modernization|cloud"
      r" modernization)\b",
      text,
      re.IGNORECASE,
  ):
    res["sales_play"] = "Cloud Modernization"
  elif re.search(
      r"\b(?:data modernization|analytics modernization|smart analytics)\b",
      text,
      re.IGNORECASE,
  ):
    res["sales_play"] = "Data Modernization"
  elif re.search(
      r"\b(?:security modernization|security operations|secops)\b",
      text,
      re.IGNORECASE,
  ):
    res["sales_play"] = "Security Modernization"

  # 5. Products / Solutions Mentioned
  prod_m = re.search(
      r"\b(?:products?|solutions?|technolog(?:y|ies))\s*[:=]?\s*([A-Za-z0-9_&,\s\-]+?)(?:$|\.|\s+for\b|\s+opp\b|\s+audience\b|\s+sales\b)",
      text,
      re.IGNORECASE,
  )
  if prod_m:
    res["products"] = prod_m.group(1).strip()

  # 6. Customer Name Extraction
  clean_text_for_cust = text
  if ind_m:
    clean_text_for_cust = clean_text_for_cust.replace(ind_m.group(0), " ")
  if aud_m:
    clean_text_for_cust = clean_text_for_cust.replace(aud_m.group(0), " ")
  if sp_m:
    clean_text_for_cust = clean_text_for_cust.replace(sp_m.group(0), " ")
  if opp_m:
    clean_text_for_cust = clean_text_for_cust.replace(opp_m.group(0), " ")
  if prod_m:
    clean_text_for_cust = clean_text_for_cust.replace(prod_m.group(0), " ")

  clean_text_for_cust = re.sub(
      r"\b(?:financial services|retail & consumer|healthcare & life"
      r" sciences|healthcare|life sciences|consumer packaged"
      r" goods|telecommunications|manufacturing|public"
      r" sector)\s+(?:industry|sector|vertical)\b",
      " ",
      clean_text_for_cust,
      flags=re.IGNORECASE,
  )

  # Priority 1: High-precedence explicit customer / tailoring phrases
  cust_m = re.search(
      r"\b(?:specifically\s+for|customiz(?:e|ing)(?:\s+it)?(?:\s+(?:the\s+)?(?:entire\s+)?(?:presentation|deck|slides)?)?\s+(?:towards|to|for)|tailor(?:ing)?(?:\s+it)?(?:\s+(?:the\s+)?(?:entire\s+)?(?:presentation|deck|slides)?)?\s+(?:towards|to|for)|transform(?:ing)?(?:\s+it)?(?:\s+(?:the\s+)?(?:entire\s+)?(?:presentation|deck|slides)?)?\s+(?:towards|to|for)|adapt(?:ing)?(?:\s+it)?(?:\s+(?:the\s+)?(?:entire\s+)?(?:presentation|deck|slides)?)?\s+(?:towards|to|for)|target\s+customer\s*[:=]|customer\s*[:=]|account\s*[:=]|client\s*[:=]|for\s+customer|for\s+account|for\s+client)\s+([A-Za-z0-9_&\'\s\-]+?)(?:,|$|\.|\s+into\b|\s+on\b|\s+focusing\b|\s+with\b|\s+in\b|\s+adjust\b|\s+align\b|\s+audience\b|\s+sales\b|\s+targeting\b|\s+for\b|\s+opp\b|\s+products\b)",
      clean_text_for_cust,
      re.IGNORECASE,
  )
  if not cust_m:
    # Priority 2: General targeting / for phrase
    cust_m = re.search(
        r"\b(?:presenting\s+to|pitching\s+to|focusing(?:\s+it)?\s+on|focus\s+on|focused\s+on|targeting|for|towards|to)\s+([A-Za-z0-9_&\'\s\-]+?)(?:,|$|\.|\s+into\b|\s+on\b|\s+in\b|\s+with\b|\s+focusing\b|\s+adjust\b|\s+align\b|\s+audience\b|\s+sales\b|\s+targeting\b|\s+for\b|\s+executive\b|\s+opp\b|\s+products\b)",
        clean_text_for_cust,
        re.IGNORECASE,
    )
  if not cust_m:
    # Priority 3: Customer noun with negative lookahead for common CX terms
    cust_m = re.search(
        r"\b(?:customer|account|client)\s+(?!(?:experience|service|journey|satisfaction|support|success|retention|engagement|feedback|centric|facing|telemetry|profiles|regulations|priorities)\b)([A-Za-z0-9_&\'\s\-]+?)(?:,|$|\.|\s+into\b|\s+on\b|\s+towards\b|\s+in\b|\s+with\b|\s+focusing\b)",
        clean_text_for_cust,
        re.IGNORECASE,
    )

  if cust_m:
    candidate = cust_m.group(1).strip()
    stop_words = {
        "the",
        "a",
        "an",
        "this",
        "my",
        "our",
        "all",
        "entire",
        "deck",
        "presentation",
        "slides",
        "google",
        "google cloud",
        "fsi",
        "banking",
        "retail",
        "cpg",
        "healthcare",
        "financial",
        "services",
        "industry",
        "sector",
        "vertical",
        "c-suite",
        "executives",
        "executive",
        "leadership",
        "digital",
        "transformation",
        "compliance",
        "trust",
        "risk",
        "management",
        "journey",
        "experience",
        "service",
        "support",
        "regulations",
        "priorities",
        "strategic",
        "adjust",
        "terminology",
        "examples",
        "tone",
        "align",
        "institutional",
        "supply",
        "chain",
        "modernization",
        "above",
        "deck",
        "by",
    }
    candidate = re.sub(r"[,\.:;]+$", "", candidate).strip()
    cand_tokens = [w for w in candidate.split() if w.lower() not in stop_words]
    if cand_tokens:
      final_cust = " ".join(cand_tokens)
      c_lower = final_cust.lower()
      if c_lower in (
          "jp morgan chase",
          "jpmorgan chase",
          "jpmorgan",
          "jp morgan",
          "jpmc",
      ):
        res["customer_name"] = "JPMorgan Chase"
      elif c_lower in ("anz", "anz bank"):
        res["customer_name"] = "ANZ Bank"
      elif c_lower == "pepsico":
        res["customer_name"] = "PepsiCo"
      elif c_lower in ("walmart", "wal-mart"):
        res["customer_name"] = "Walmart"
      elif c_lower in ("tata", "tata motors"):
        res["customer_name"] = "Tata Motors"
      elif c_lower in ("standard chartered", "scb"):
        res["customer_name"] = "Standard Chartered"
      elif c_lower in ("deutsche bank", "db"):
        res["customer_name"] = "Deutsche Bank"
      elif c_lower in ("santander", "banco santander"):
        res["customer_name"] = "Santander"
      elif c_lower in ("goldman sachs", "goldman"):
        res["customer_name"] = "Goldman Sachs"
      elif c_lower in ("morgan stanley",):
        res["customer_name"] = "Morgan Stanley"
      elif c_lower in ("citi", "citigroup"):
        res["customer_name"] = "Citigroup"
      elif c_lower in ("bank of america", "bofa"):
        res["customer_name"] = "Bank of America"
      elif c_lower in ("wells fargo",):
        res["customer_name"] = "Wells Fargo"
      elif c_lower in ("target", "target corporation", "target corp"):
        res["customer_name"] = "Target"
      else:
        res["customer_name"] = final_cust.title()

  if not res["customer_name"]:
    for known_cust in (
        "HDFC Bank",
        "HDFC",
        "JPMorgan Chase",
        "JP Morgan Chase",
        "JPMorgan",
        "ANZ Bank",
        "ANZ",
        "PepsiCo",
        "Walmart",
        "Tata Motors",
        "Target",
        "Home Depot",
        "Costco",
        "CVS",
        "Walgreens",
        "Standard Chartered",
        "Deutsche Bank",
        "Santander",
        "Goldman Sachs",
        "Morgan Stanley",
        "Citigroup",
        "Bank of America",
        "Wells Fargo",
    ):
      if re.search(r"\b" + re.escape(known_cust) + r"\b", text, re.IGNORECASE):
        if known_cust.upper().startswith("ANZ"):
          res["customer_name"] = "ANZ Bank"
        elif (
            "jpmorgan" in known_cust.lower()
            or "jp morgan" in known_cust.lower()
        ):
          res["customer_name"] = "JPMorgan Chase"
        else:
          res["customer_name"] = known_cust
        break

  return res


class SlideEngineeringAgent(BaseAgent):

  def __init__(self, config):
    super().__init__(
        "SlideEngineeringAgent",
        "Responsible for synthesizing, transforming and assembling slides.",
    )
    self.config = config

    # Equip agent with skills for content synthesis, mapping, transformation, and assembly
    self.add_skill("synthesis", ContentSynthesisWorkflow(config))
    self.add_skill("mapping", TemplateMapperWorkflow(config))
    self.add_skill("layout_transformer", LayoutTransformerWorkflow(config))
    self.add_skill("text_transformer", TextTransformerWorkflow(config))
    self.add_skill("translation_engine", TranslationEngineWorkflow(config))
    self.add_skill("slide_assembly", SlideAssemblyWorkflow(config))

  def polish_presentation_text(self, deck_data, target_slide_ids=None, criteria=""):
    """Transforms / polishes text elements across target slides in a presentation deck."""
    if not isinstance(deck_data, dict) or "slides" not in deck_data:
      return deck_data

    transformer = self.skills.get("text_transformer")
    new_slides = []
    for slide in deck_data.get("slides", []):
      s_id = slide.get("objectId") or slide.get("slide_id") or slide.get("id")
      should_transform = True
      if target_slide_ids is not None:
        should_transform = s_id in target_slide_ids or str(s_id) in [str(x) for x in target_slide_ids]

      if should_transform and transformer:
        new_slide = dict(slide)
        if "text" in slide:
          new_slide["text"] = transformer.execute(slide["text"], criteria=criteria)
        new_slides.append(new_slide)
      else:
        new_slides.append(slide)

    res = dict(deck_data)
    res["slides"] = new_slides
    return res

  def transform_slide(
      self, slide_layout, slide_category, output_criteria, slide_image_url=None, slide_id=None
  ):
    """Transforms slide content based on layout, category, output criteria, and slide image."""
    content_str = self.skills["layout_transformer"].execute(
        slide_layout=slide_layout,
        slide_category=slide_category,
        output_criteria=output_criteria,
        slide_image_url=slide_image_url,
        slide_id=slide_id,
    )
    return self.skills["slide_assembly"].execute(
        content=content_str, status="success"
    )

  def _recursive_transform_text(self, item, transform_func):
    """Recursively applies transform_func to all 'text'/'Text' string fields in a nested structure."""
    if isinstance(item, dict):
      new_dict = {}
      for k, v in item.items():
        if k.lower() == "text" and isinstance(v, str) and v.strip():
          new_dict[k] = transform_func(v)
        else:
          new_dict[k] = self._recursive_transform_text(v, transform_func)
      return new_dict
    elif isinstance(item, list):
      return [self._recursive_transform_text(x, transform_func) for x in item]
    return item

  def translate_presentation(self, presentation_data, target_language="German"):
    """Recursively translates all text entries in the presentation structure."""

    def translate_func(val):
      return self.skills["translation_engine"].execute(
          val, target_language=target_language
      )

    return self._recursive_transform_text(presentation_data, translate_func)

  def is_proof_points_slide(self, slide_data: dict, texts: list[str] = None) -> bool:
    """Checks metadata, taxonomy, and content to identify Proof Points / Case Studies."""
    if not isinstance(slide_data, dict):
      return False

    job = str(
        slide_data.get("slide_job")
        or slide_data.get("taxonomy", {}).get("slide_job")
        or ""
    ).lower()
    if job in ("proof_points", "proof points", "proof_point", "case_study", "customer_reference", "customer_references"):
      return True

    slide_cat = str(
        slide_data.get("category")
        or slide_data.get("slide_category")
        or slide_data.get("taxonomy", {}).get("category")
        or ""
    ).lower()

    if (
        slide_data.get("customer_references") in (True, "true", "True")
        or slide_data.get("is_customer_story") in (True, "true")
        or slide_data.get("is_cust_ref") in (True, "true")
        or slide_data.get("_source_datastore_key") in ("customer_references", "cust_ref")
        or "cust-ref" in str(slide_data.get("_source_datastore", "")).lower()
        or "cust_ref" in str(slide_data.get("deck_source_url", "")).lower()
        or "cust_ref" in str(slide_data.get("slide_id", "")).lower()
        or slide_cat in ("customer_references", "customer_reference", "customer_story", "case_study", "proof_points", "proof_point")
    ):
      return True

    # Content-based heuristic check
    combined_texts = []
    if texts:
      combined_texts.extend([str(t) for t in texts])
    if "title" in slide_data:
      combined_texts.append(str(slide_data["title"]))
    if "slide_title" in slide_data:
      combined_texts.append(str(slide_data["slide_title"]))
    for note_k in ("speaker_notes", "speakerNotes", "notes", "speaker_note", "notes_text", "speaker_notes_shape"):
      if note_k in slide_data and slide_data[note_k]:
        combined_texts.append(str(slide_data[note_k]))

    def extract_deep(obj):
      if isinstance(obj, dict):
        for k, v in obj.items():
          if k.lower() in ("text", "content") and isinstance(v, str):
            combined_texts.append(v.strip())
          else:
            extract_deep(v)
      elif isinstance(obj, list):
        for el in obj:
          extract_deep(el)

    extract_deep(slide_data)

    all_content_lower = " ".join(combined_texts).lower()
    title_str = str(
        slide_data.get("title", "") or slide_data.get("slide_title", "") or ""
    ).lower()

    # 1. GTM customer reference library signatures
    if any(
        sig in all_content_lower
        for sig in (
            "customer_reference_library",
            "https://your-sales-portal.example.com/customer-references",
            "https://your-sales-portal.example.com/customer-references",
            "customer_reference_crm",
            "customer stories older than",
            "older reference",
            "sensitive customer",
            "customer reference manager",
            "customer reference",
            "customer spotlight",
            "success story",
            "case study",
            "head of data office",
            "head of reporting and modelling",
            "applicable product",
            "applicable product(s)",
            "mission of",
            "the mission of",
            "quote attribution",
        )
    ):
      return True

    # 2. Case study titles
    if any(
        cs in title_str
        for cs in (
            "case study:",
            "customer story:",
            "customer spotlight:",
            "success story:",
            "customer case study",
        )
    ):
      return True

    # 3. Known third-party customer case study brands
    if any(
        brand in all_content_lower
        for brand in (
            "central group",
            "cainz",
            "wpp",
            "banco abc brasil",
            "banco abc",
            "cynergy bank",
            "home depot",
            "lowe's",
            "lowes",
            "carrefour",
            "spotify",
            "paypal",
            "wayfair",
            "smartersorting",
            "smarter sorting",
            "mercedes-benz",
            "deutsche bank",
            "vodafone",
        )
    ):
      if any(
          att in all_content_lower
          for att in (
              "chief",
              "officer",
              "vp",
              "director",
              "head of",
              "lead of",
              "lead,",
              "president",
              "applicable product",
              "impact",
              "results",
              "challenge",
              "solution",
              "mission",
              "%",
              "quote",
              "active agents",
              "faster",
              "delivery",
              "2x",
              "3x",
              "5x",
              "10x",
              "workflows",
              "transforming",
              "creative workflows",
          )
      ):
        return True

    # 4. Executive quote / attribution signatures (e.g. Central Group & Cainz CDO quotes)
    has_exec_title = any(
        t in all_content_lower
        for t in (
            "chief digital officer",
            "chief technology officer",
            "chief information officer",
            "chief executive officer",
            "vice president",
            "vp of",
            "head of",
            "lead of",
            "director of",
            "managing director",
            "head of data",
            "head of engineering",
        )
    )
    has_quote_or_metric = (
        '"' in all_content_lower
        or "“" in all_content_lower
        or "”" in all_content_lower
        or "—" in all_content_lower
        or "-" in all_content_lower
    )
    if has_exec_title and has_quote_or_metric:
      return True

    return False

  def is_internal_enablement_slide(
      self, slide_data: dict, texts: list[str] = None
  ) -> bool:
    """Checks metadata, taxonomy, and content to identify Internal Context / Enablement slides."""
    if not isinstance(slide_data, dict):
      return False
    slide_name = (
        str(
            slide_data.get("slide_name")
            or slide_data.get("name")
            or slide_data.get("title")
            or ""
        )
        .lower()
        .strip()
    )
    if (
        "internal context" in slide_name
        or "internal guidance" in slide_name
        or "remove this slide" in slide_name
    ):
      return True

    combined_texts = []
    if texts:
      combined_texts.extend([str(t) for t in texts])

    def extract(obj):
      if isinstance(obj, dict):
        for k, v in obj.items():
          if k.lower() in ("text", "content") and isinstance(v, str):
            combined_texts.append(v.lower().strip())
          else:
            extract(v)
      elif isinstance(obj, list):
        for item in obj:
          extract(item)

    extract(slide_data)

    all_content_lower = " ".join(combined_texts).lower()
    if (
        "internal context:" in all_content_lower
        or "internal context" in all_content_lower
        or "please remove this slide before you present" in all_content_lower
    ):
      return True
    if (
        "opportunity id" in all_content_lower
        and "target customer" in all_content_lower
        and "sales plays" in all_content_lower
    ):
      return True
    if "who to contact" in all_content_lower and (
        "coaching videos" in all_content_lower
        or "target persona" in all_content_lower
    ):
      return True
    return False

  def is_closing_slide(self, slide_data: dict, texts: list[str] = None) -> bool:
    """Checks metadata, taxonomy, and content to identify standalone Closing / Thank You slides."""
    if not isinstance(slide_data, dict):
      return False
    job = str(
        slide_data.get("slide_job")
        or slide_data.get("taxonomy", {}).get("slide_job")
        or ""
    ).lower()
    if job in ("closing_slide", "thank_you", "thankyou", "closing", "q_and_a"):
      return True

    title_str = (
        str(
            slide_data.get("title", "")
            or slide_data.get("slide_title", "")
            or slide_data.get("name", "")
        )
        .strip()
        .lower()
    )
    clean_title = re.sub(r"[^a-zA-Z\s]", "", title_str).strip()
    if clean_title in (
        "thank you",
        "thank you!",
        "thanks",
        "questions",
        "qa",
        "q and a",
        "contact us",
        "thank you for your time",
    ):
      return True

    combined_texts = []
    if texts:
      combined_texts.extend([str(t).strip() for t in texts if str(t).strip()])
    else:

      def extract(obj):
        if isinstance(obj, dict):
          for k, v in obj.items():
            if k.lower() in ("text", "content") and isinstance(v, str):
              combined_texts.append(v.strip())
            else:
              extract(v)
        elif isinstance(obj, list):
          for item in obj:
            extract(item)

      extract(slide_data)

    clean_all = " ".join(
        [re.sub(r"[^a-zA-Z\s]", "", t).strip().lower() for t in combined_texts]
    )
    if any(
        k in clean_all
        for k in (
            "thank you",
            "thankyou",
            "thanks",
            "questions",
            "q and a",
            "q a",
            "contact us",
        )
    ):
      return True
    return False

  def _is_agenda_slide(self, slide_obj: dict) -> bool:
    """Detects if a slide is an Agenda / Table of Contents slide."""
    if not isinstance(slide_obj, dict):
      return False
    layout = str(
        slide_obj.get("layout", "") or slide_obj.get("slide_layout", "")
    ).lower()
    category = str(
        slide_obj.get("slide_category", "") or slide_obj.get("category", "")
    ).lower()
    if "agenda" in layout or "agenda" in category or "gc_ai_agenda" in layout:
      return True
    title = str(
        slide_obj.get("title", "")
        or slide_obj.get("slide_title", "")
        or slide_obj.get("name", "")
    ).lower()
    if any(
        k in title
        for k in (
            "agenda",
            "table of contents",
            "today's agenda",
            "executive agenda",
            "overview of topics",
            "topics for today",
        )
    ):
      return True
    slide_texts = []

    def collect_texts(x):
      if isinstance(x, dict):
        for k, v in x.items():
          if (
              k.lower() in ("text", "content")
              and isinstance(v, str)
              and v.strip()
          ):
            slide_texts.append(v.strip())
          else:
            collect_texts(v)
      elif isinstance(x, list):
        for el in x:
          collect_texts(el)

    collect_texts(slide_obj)
    for st in slide_texts:
      st_clean = re.sub(r"[^a-zA-Z\s]", "", st).strip().lower()
      if st_clean in (
          "agenda",
          "table of contents",
          "todays agenda",
          "executive agenda",
          "topics for today",
          "overview of topics",
      ):
        return True
      if re.search(
          r"\b(?:agenda|table\s+of\s+contents|overview\s+of\s+topics)\b",
          st,
          re.IGNORECASE,
      ):
        return True
    return False

  def is_title_slide(self, slide_data: dict, texts: list[str] = None) -> bool:
    """Checks metadata, taxonomy, and content to identify the main Presentation Title / Cover slide."""
    if not isinstance(slide_data, dict):
      return False
    job = str(
        slide_data.get("slide_job")
        or slide_data.get("taxonomy", {}).get("slide_job")
        or ""
    ).lower()
    if job in ("title", "title_slide", "cover", "cover_slide", "main_title"):
      return True
    layout = str(
        slide_data.get("layout", "") or slide_data.get("slide_layout", "")
    ).lower()
    category = str(
        slide_data.get("slide_category", "") or slide_data.get("category", "")
    ).lower()
    if any(
        k in layout or k in category
        for k in ("title_slide", "cover", "deck_title", "main_title")
    ):
      return True
    name = str(
        slide_data.get("name", "") or slide_data.get("title", "")
    ).lower()
    if any(
        k in name for k in ("title slide", "cover slide", "presentation title")
    ):
      return True
    return False

  def _is_divider_slide(self, slide_obj: dict, sync_map: dict = None) -> bool:
    """Detects if a slide is a Section Divider / Transition slide."""
    if not isinstance(slide_obj, dict):
      return False
    # CRITICAL: Exclude Enablement, Title, Closing, and Proof Points slides
    if (
        self.is_internal_enablement_slide(slide_obj)
        or self.is_title_slide(slide_obj)
        or self.is_closing_slide(slide_obj)
        or self.is_proof_points_slide(slide_obj)
    ):
      return False

    job = str(
        slide_obj.get("slide_job")
        or slide_obj.get("taxonomy", {}).get("slide_job")
        or ""
    ).lower()
    if job in ("divider", "section_divider", "transition", "section_break"):
      return True
    layout = str(
        slide_obj.get("layout", "") or slide_obj.get("slide_layout", "")
    ).lower()
    category = str(
        slide_obj.get("slide_category", "") or slide_obj.get("category", "")
    ).lower()
    if any(
        k in layout or k in category
        for k in ("divider", "section_divider", "section_break", "transition")
    ):
      return True

    slide_texts = []

    def collect_texts(x):
      if isinstance(x, dict):
        for k, v in x.items():
          if (
              k.lower() in ("text", "content")
              and isinstance(v, str)
              and v.strip()
          ):
            slide_texts.append(v.strip())
          else:
            collect_texts(v)
      elif isinstance(x, list):
        for el in x:
          collect_texts(el)

    collect_texts(slide_obj)

    content_texts = [
        st
        for st in slide_texts
        if not any(
            fn in st.lower()
            for fn in (
                "proprietary",
                "confidential",
                "feedback",
                "pitchgen",
                "share feedback",
                "request pitchhub",
                "internal use only",
            )
        )
        and st.strip().lower() != "google cloud"
    ]

    # Divider slides do not have tables or many content blocks
    if slide_obj.get("tables") or len(content_texts) > 2:
      return False

    combined_len = sum(len(st) for st in content_texts)
    if combined_len > 80 or combined_len == 0:
      return False

    if sync_map and content_texts:
      for st in content_texts:
        st_clean = (
            re.sub(
                r"^(\d+[\.\-\s:]+|[•\-\*]\s*|section\s*\d+[\.\-\s:]*)",
                "",
                st,
                flags=re.IGNORECASE,
            )
            .strip()
            .lower()
        )
        if not st_clean or len(st_clean) < 3:
          continue
        if st_clean in sync_map or st.strip().lower() in sync_map:
          return True
        st_words = set(re.findall(r"\w+", st_clean))
        for key in sync_map.keys():
          if key == "__seq__":
            continue
          key_words = set(re.findall(r"\w+", str(key)))
          if not key_words or not st_words:
            continue
          overlap = st_words.intersection(key_words)
          score = len(overlap) / max(len(st_words), len(key_words))
          if score >= 0.60:
            return True

    if 1 <= len(content_texts) <= 2 and combined_len <= 75:
      return True

    return False

  def _extract_agenda_sync_map(
      self, orig_slide: dict, trans_slide: dict
  ) -> dict:
    """Extracts a 1-to-1 sync dictionary mapping original agenda section titles to transformed titles."""
    orig_raw_texts = []
    trans_raw_texts = []

    def collect(x, lst):
      if isinstance(x, dict):
        for k, v in x.items():
          if (
              k.lower() in ("text", "content")
              and isinstance(v, str)
              and v.strip()
          ):
            lst.append(v.strip())
          else:
            collect(v, lst)
      elif isinstance(x, list):
        for el in x:
          collect(el, lst)

    collect(orig_slide, orig_raw_texts)
    collect(trans_slide, trans_raw_texts)

    def is_pure_number(t):
      return bool(re.match(r"^\s*(?:0?[1-9]|[1-9]\d?)\.?\s*$", t))

    def is_meta_text(t):
      return (
          any(
              fn in t.lower()
              for fn in (
                  "proprietary",
                  "confidential",
                  "feedback",
                  "pitchgen",
                  "share feedback",
                  "request pitchhub",
                  "internal use only",
              )
          )
          or t.strip().lower() == "google cloud"
      )

    def is_agenda_header(t):
      c = re.sub(r"[^a-zA-Z\s]", "", t).strip().lower()
      return c in (
          "agenda",
          "table of contents",
          "todays agenda",
          "executive agenda",
          "topics for today",
          "overview of topics",
      )

    orig_titles = [
        t
        for t in orig_raw_texts
        if not is_pure_number(t)
        and not is_agenda_header(t)
        and not is_meta_text(t)
    ]
    trans_titles = [
        t
        for t in trans_raw_texts
        if not is_pure_number(t)
        and not is_agenda_header(t)
        and not is_meta_text(t)
    ]

    sync_map = {}
    agenda_seq_list = []

    for idx, (o_txt, t_txt) in enumerate(zip(orig_titles, trans_titles)):
      clean_orig = (
          re.sub(
              r"^(\d+[\.\-\s:]+|[•\-\*]\s*|section\s*\d+[\.\-\s:]*)",
              "",
              o_txt,
              flags=re.IGNORECASE,
          )
          .strip()
          .lower()
      )
      clean_orig = re.sub(r"\s+", " ", clean_orig).strip()
      clean_trans = re.sub(
          r"^(\d+[\.\-\s:]+|[•\-\*]\s*|section\s*\d+[\.\-\s:]*)",
          "",
          t_txt,
          flags=re.IGNORECASE,
      ).strip()
      clean_trans = re.sub(r"\s+", " ", clean_trans).strip()
      raw_orig_norm = re.sub(r"\s+", " ", o_txt.strip().lower())

      seq_item = {
          "clean": clean_trans,
          "raw": t_txt.strip(),
          "clean_orig": clean_orig,
          "index": idx + 1,
      }
      agenda_seq_list.append(seq_item)

      if clean_orig and len(clean_orig) >= 3:
        sync_map[clean_orig] = seq_item
        sync_map[raw_orig_norm] = seq_item
      sync_map[f"__idx_{idx + 1}__"] = seq_item
      sync_map[f"0{idx + 1}"] = seq_item
      sync_map[f"{idx + 1}"] = seq_item

    sync_map["__seq__"] = agenda_seq_list
    return sync_map

  def _sync_divider_slide(
      self,
      orig_slide: dict,
      trans_slide: dict,
      sync_map: dict,
      slide_name: str = "",
      seq_item: dict = None,
  ) -> dict:
    """Synchronizes section divider titles verbatim with the transformed Agenda."""
    if not isinstance(trans_slide, dict):
      return trans_slide

    import copy

    agenda_seq_list = sync_map.get("__seq__", []) if sync_map else []
    target_item = seq_item

    # Find any explicit section number present anywhere on this divider slide (e.g. from a number shape "03" or "Section 03")
    slide_texts = []

    def collect_slide_texts(x):
      if isinstance(x, dict):
        for k, v in x.items():
          if (
              k.lower() in ("text", "content")
              and isinstance(v, str)
              and v.strip()
          ):
            slide_texts.append(v.strip())
          else:
            collect_slide_texts(v)
      elif isinstance(x, list):
        for el in x:
          collect_slide_texts(el)

    collect_slide_texts(orig_slide)

    slide_sec_num = None
    for st in slide_texts:
      nm = re.search(
          r"\b(?:section\s*|part\s*)?(0?[1-9]|[1-9]\d?)\b", st, re.IGNORECASE
      )
      if nm:
        try:
          n_val = int(nm.group(1))
          if 1 <= n_val <= len(agenda_seq_list):
            slide_sec_num = n_val
            break
        except (ValueError, IndexError):
          pass

    def is_pure_number(t):
      return bool(re.match(r"^\s*(?:0?[1-9]|[1-9]\d?)\.?\s*$", str(t).strip()))

    def is_meta_text(t):
      return (
          any(
              fn in t.lower()
              for fn in (
                  "proprietary",
                  "confidential",
                  "feedback",
                  "pitchgen",
                  "share feedback",
                  "request pitchhub",
                  "internal use only",
              )
          )
          or t.strip().lower() == "google cloud"
      )

    def find_best_match(text):
      if not text or not isinstance(text, str):
        return None
      if is_pure_number(text) or is_meta_text(text):
        return None  # Preserve standalone number box or footer untouched

      if target_item:
        return target_item

      text_clean = (
          re.sub(
              r"^(\d+[\.\-\s:]+|[•\-\*]\s*|section\s*\d+[\.\-\s:]*)",
              "",
              text,
              flags=re.IGNORECASE,
          )
          .strip()
          .lower()
      )
      text_clean = re.sub(r"\s+", " ", text_clean).strip()

      if text_clean in sync_map:
        return sync_map[text_clean]

      norm_raw = re.sub(r"\s+", " ", text.strip().lower())
      if norm_raw in sync_map:
        return sync_map[norm_raw]

      text_words = set(re.findall(r"\w+", text_clean))
      best_val = None
      best_score = 0.0
      for item in agenda_seq_list:
        key = item.get("clean_orig", "")
        key_words = set(re.findall(r"\w+", key))
        if not key_words or not text_words:
          continue
        overlap = text_words.intersection(key_words)
        score = len(overlap) / max(len(text_words), len(key_words))
        if score > best_score and score >= 0.60:
          best_score = score
          best_val = item
      if best_val:
        return best_val

      num_match = re.search(
          r"\b(?:section\s*|part\s*)?(0?[1-9]|[1-9]\d?)\b", text, re.IGNORECASE
      )
      if num_match and agenda_seq_list:
        try:
          sec_num = int(num_match.group(1))
          if 1 <= sec_num <= len(agenda_seq_list):
            return agenda_seq_list[sec_num - 1]
        except (ValueError, IndexError):
          pass

      if slide_sec_num and 1 <= slide_sec_num <= len(agenda_seq_list):
        return agenda_seq_list[slide_sec_num - 1]

      return None

    # Format 1: Shapes dictionary (Google Slides layout)
    shapes_dict = trans_slide.get("shapes")
    if isinstance(shapes_dict, dict) and shapes_dict:
      res_slide = copy.deepcopy(trans_slide)
      for sh_id, segs in res_slide["shapes"].items():
        if not isinstance(segs, dict):
          continue
        full_sh_text = " ".join([
            str(v.get("Text", "")) for v in segs.values() if isinstance(v, dict)
        ]).strip()
        if is_meta_text(full_sh_text) or is_pure_number(full_sh_text):
          continue
        match_data = target_item or find_best_match(full_sh_text)
        if match_data:
          target_text = match_data["clean"]
          sorted_keys = sorted(
              segs.keys(), key=lambda x: int(x) if str(x).isdigit() else str(x)
          )
          first_key = sorted_keys[0] if sorted_keys else "0"
          if (
              first_key in segs
              and isinstance(segs[first_key], dict)
              and "Text" in segs[first_key]
          ):
            segs[first_key]["Text"] = target_text
          for s_k in sorted_keys[1:]:
            if isinstance(segs[s_k], dict) and "Text" in segs[s_k]:
              segs[s_k]["Text"] = ""
          print(
              f"[{self.name}] -> Synced Divider Slide '{slide_name}' shape"
              f" '{sh_id}' with Agenda: '{target_text}'"
          )
      return res_slide

    def sync_recursive(orig_item, trans_item):
      if isinstance(orig_item, dict) and isinstance(trans_item, dict):
        new_dict = {}
        for k, v in trans_item.items():
          orig_v = orig_item.get(k)
          if (
              isinstance(v, str)
              and isinstance(orig_v, str)
              and (
                  "text" in k.lower()
                  or "title" in k.lower()
                  or "header" in k.lower()
              )
          ):
            match_data = find_best_match(orig_v)
            if match_data:
              prefix_match = re.match(
                  r"^(\d+[\.\-\s:]+|[•\-\*]\s*|section\s*\d+[\.\-\s:]*)",
                  orig_v,
                  re.IGNORECASE,
              )
              prefix = prefix_match.group(0) if prefix_match else ""
              new_dict[k] = (
                  f"{prefix}{match_data['clean']}"
                  if prefix
                  else match_data["clean"]
              )
              print(
                  f"[{self.name}] -> Synced Divider Slide '{slide_name}'"
                  f" ('{orig_v}') with Agenda: '{new_dict[k]}'"
              )
            else:
              new_dict[k] = v
          else:
            new_dict[k] = sync_recursive(orig_v, v)
        return new_dict
      elif isinstance(orig_item, list) and isinstance(trans_item, list):
        return [
            sync_recursive(o, t) if i < len(trans_item) else t
            for i, (o, t) in enumerate(zip(orig_item, trans_item))
        ]
      return trans_item

    return sync_recursive(orig_slide, trans_slide)

  def transform_internal_enablement_slide(
      self, slide_data: dict, context: dict = None, criteria: str = ""
  ) -> dict:
    """Transforms only mutable fields (Target Customer, Industry, User Prompt) in the enablement table, preserving all locked labels, buttons, and Next Steps."""
    import copy

    slide_res = copy.deepcopy(slide_data)
    context = context or {}

    prompt_source = str(
        criteria
        or context.get("business_context")
        or context.get("user_request")
        or ""
    ).strip()
    extracted = extract_entities_from_user_prompt(prompt_source)

    customer_name = str(
        context.get("customer_name")
        or extracted.get("customer_name")
        or context.get("customer")
        or ""
    ).strip()
    industry = str(
        context.get("industry") or extracted.get("industry") or ""
    ).strip()
    audience = str(
        context.get("audience") or extracted.get("audience") or ""
    ).strip()
    sales_play = str(
        context.get("salesPlay") or extracted.get("sales_play") or ""
    ).strip()
    opportunity_id = str(
        context.get("opportunity_id") or extracted.get("opportunity_id") or ""
    ).strip()
    user_prompt = prompt_source

    # Smart fallbacks for well-known customer names and industries
    if not customer_name and "hdfc" in prompt_source.lower():
      customer_name = "HDFC Bank"
    elif (
        customer_name.lower() == "hdfc bank" or customer_name.lower() == "hdfc"
    ):
      customer_name = "HDFC Bank"

    if not industry and (
        "financial" in prompt_source.lower()
        or "banking" in prompt_source.lower()
        or "fsi" in prompt_source.lower()
    ):
      industry = "Financial Services"

    if not audience:
      if (
          "financial" in prompt_source.lower()
          or "banking" in prompt_source.lower()
          or "hdfc" in prompt_source.lower()
      ):
        audience = "C-Level & Line of Business Executives"
      else:
        audience = "Executive Leadership & Technical Decision Makers"

    if not sales_play:
      if (
          "bigquery" in prompt_source.lower()
          or "data" in prompt_source.lower()
          or "analytics" in prompt_source.lower()
      ):
        sales_play = "Smart Analytics & Data Modernization"
      else:
        sales_play = "Cloud Modernization & AI Adoption"

    print(
        f"[{self.name}] Updating Internal Context Slide metadata:"
        f" Customer='{customer_name}', Industry='{industry}',"
        f" Audience='{audience}', SalesPlay='{sales_play}',"
        f" OppID='{opportunity_id}'..."
    )

    # Format 1: Update tables dict (extracted via extractDeckTextHeadless)
    tables_dict = slide_res.get("tables", {})
    if isinstance(tables_dict, dict) and tables_dict:
      for table_id, table_cells in tables_dict.items():
        if not isinstance(table_cells, dict):
          continue
        for cell_pos, segs in list(table_cells.items()):
          if not isinstance(segs, dict):
            continue
          parts = cell_pos.split("_")
          if len(parts) != 2:
            continue
          r_idx, c_idx = parts[0], parts[1]
          if c_idx != "0":  # Only inspect column 0 (the field labels)
            continue

          cell_text = (
              " ".join([
                  str(v.get("Text", ""))
                  for v in segs.values()
                  if isinstance(v, dict)
              ])
              .strip()
              .lower()
          )
          val_pos = f"{r_idx}_1"
          val_segs = table_cells.get(val_pos)

          is_cust_row = any(
              k in cell_text
              for k in (
                  "target customer",
                  "customer",
                  "zielkunde",
                  "目标客户",
                  "client",
              )
          )
          is_ind_row = any(
              k in cell_text
              for k in ("industry", "branche", "行业", "sector", "vertical")
          )
          is_prompt_row = any(
              k in cell_text
              for k in (
                  "user prompt",
                  "user-prompt",
                  "prompt",
                  "用户提示",
                  "business context",
              )
          )
          is_opp_row = any(
              k in cell_text
              for k in (
                  "opportunity id",
                  "opportunity-id",
                  "opportunity",
                  "opp id",
                  "er number",
                  "er id",
                  "业务机会",
              )
          )
          is_aud_row = any(
              k in cell_text
              for k in ("audience", "zielgruppe", "受众", "persona")
          )
          is_sp_row = any(
              k in cell_text
              for k in (
                  "sales plays",
                  "sales play",
                  "sales-play",
                  "销售策略",
                  "vertriebsstrategie",
              )
          )
          is_next_row = any(
              k in cell_text
              for k in ("next steps", "nächste schritte", "后续步骤")
          )

          if is_cust_row:
            if customer_name:
              if not val_segs:
                table_cells[val_pos] = {
                    "0": {"Text": customer_name, "HadNewline": False}
                }
              else:
                self._set_shape_text(val_segs, customer_name)
          elif is_ind_row:
            if industry:
              if not val_segs:
                table_cells[val_pos] = {
                    "0": {"Text": industry, "HadNewline": False}
                }
              else:
                self._set_shape_text(val_segs, industry)
          elif is_prompt_row:
            if user_prompt:
              if not val_segs:
                table_cells[val_pos] = {
                    "0": {"Text": user_prompt, "HadNewline": False}
                }
              else:
                self._set_shape_text(val_segs, user_prompt)
          elif is_opp_row:
            if opportunity_id:
              if not val_segs:
                table_cells[val_pos] = {
                    "0": {"Text": opportunity_id, "HadNewline": False}
                }
              else:
                self._set_shape_text(val_segs, opportunity_id)
          elif is_aud_row:
            if audience:
              if not val_segs:
                table_cells[val_pos] = {
                    "0": {"Text": audience, "HadNewline": False}
                }
              else:
                self._set_shape_text(val_segs, audience)
          elif is_sp_row:
            if sales_play:
              if not val_segs:
                table_cells[val_pos] = {
                    "0": {"Text": sales_play, "HadNewline": False}
                }
              else:
                self._set_shape_text(val_segs, sales_play)
          elif is_next_row:
            next_steps_text = (
                "Edit your deck with the PitchGen sidebar: “Extensions →"
                " PitchGen → Edit my Presentation”\nLearn more about PitchGen"
                " in CloudHub"
            )
            if not val_segs:
              table_cells[val_pos] = {
                  "0": {"Text": next_steps_text, "HadNewline": False}
              }
            else:
              self._set_shape_text(val_segs, next_steps_text)

    # Format 2: Update shapes dict
    shapes_dict = slide_res.get("shapes", {})
    if isinstance(shapes_dict, dict) and shapes_dict:
      shape_keys = list(shapes_dict.keys())
      for i, sh_id in enumerate(shape_keys):
        segs = shapes_dict[sh_id]
        if not isinstance(segs, dict):
          continue
        sh_text = (
            " ".join([
                str(v.get("Text", ""))
                for v in segs.values()
                if isinstance(v, dict)
            ])
            .strip()
            .lower()
        )
        next_sh_id = shape_keys[i + 1] if i + 1 < len(shape_keys) else None

        if "target customer" in sh_text and next_sh_id:
          if customer_name:
            self._set_shape_text(shapes_dict[next_sh_id], customer_name)
        elif "industry" in sh_text and "services" not in sh_text and next_sh_id:
          if industry:
            self._set_shape_text(shapes_dict[next_sh_id], industry)
        elif ("user prompt" in sh_text or "prompt" in sh_text) and next_sh_id:
          if user_prompt:
            self._set_shape_text(shapes_dict[next_sh_id], user_prompt)
        elif "opportunity" in sh_text and next_sh_id:
          if opportunity_id:
            self._set_shape_text(shapes_dict[next_sh_id], opportunity_id)
        elif ("audience" in sh_text or "persona" in sh_text) and next_sh_id:
          if audience:
            self._set_shape_text(shapes_dict[next_sh_id], audience)
        elif "sales play" in sh_text and next_sh_id:
          if sales_play:
            self._set_shape_text(shapes_dict[next_sh_id], sales_play)
        elif "next steps" in sh_text and next_sh_id:
          next_steps_text = (
              "Edit your deck with the PitchGen sidebar: “Extensions → PitchGen"
              " → Edit my Presentation”\nLearn more about PitchGen in CloudHub"
          )
          self._set_shape_text(shapes_dict[next_sh_id], next_steps_text)

    # Format 3: Update data list
    data_list = slide_res.get("data", [])
    if isinstance(data_list, list) and data_list:
      for i, item in enumerate(data_list):
        if not isinstance(item, dict):
          continue
        t_val = str(item.get("text", "")).strip().lower()
        next_item = (
            data_list[i + 1]
            if i + 1 < len(data_list) and isinstance(data_list[i + 1], dict)
            else None
        )
        if "target customer" in t_val and next_item:
          if customer_name:
            next_item["text"] = customer_name
        elif "industry" in t_val and "services" not in t_val and next_item:
          if industry:
            next_item["text"] = industry
        elif ("user prompt" in t_val or "prompt" in t_val) and next_item:
          if user_prompt:
            next_item["text"] = user_prompt
        elif "opportunity" in t_val and next_item:
          if opportunity_id:
            next_item["text"] = opportunity_id
        elif ("audience" in t_val or "persona" in t_val) and next_item:
          if audience:
            next_item["text"] = audience
        elif "sales play" in t_val and next_item:
          if sales_play:
            next_item["text"] = sales_play
        elif "next steps" in t_val and next_item:
          next_item["text"] = (
              "Edit your deck with the PitchGen sidebar: “Extensions → PitchGen"
              " → Edit my Presentation”\nLearn more about PitchGen in CloudHub"
          )

    # Crucial: Clear shapes dict so Slide 1 header shapes (Owner email, feedback link, support link) are 100% untouched
    slide_res["shapes"] = {}
    slide_res["_is_enablement"] = True
    return slide_res

  def _set_shape_text(self, shape_segs: dict, new_text: str):
    """Sets text in a shape segments dict, clearing extra segments to prevent duplication."""
    if not isinstance(shape_segs, dict):
      return
    sorted_k = sorted(
        shape_segs.keys(), key=lambda x: int(x) if str(x).isdigit() else x
    )
    if "0" in shape_segs:
      shape_segs["0"]["Text"] = new_text
    elif sorted_k:
      shape_segs[sorted_k[0]]["Text"] = new_text
    for sk in sorted_k[1:]:
      if isinstance(shape_segs[sk], dict):
        shape_segs[sk]["Text"] = ""

  def transform_presentation(
      self,
      presentation_data,
      output_criteria="Improve clarity and professional tone",
      slide_name="",
      context=None,
  ):
    """Recursively transforms and polishes all text entries for a slide or full multi-slide presentation deck."""
    text_targets = []

    def collect_texts(item):
      if isinstance(item, dict):
        for k, v in item.items():
          if k.lower() in ("text", "texts") and isinstance(v, str) and v.strip():
            text_targets.append(v)
          elif k.lower() in ("text", "texts") and isinstance(v, list):
            for sub_v in v:
              if isinstance(sub_v, str) and sub_v.strip():
                text_targets.append(sub_v)
              else:
                collect_texts(sub_v)
          else:
            collect_texts(v)
      elif isinstance(item, list):
        for x in item:
          if isinstance(x, str) and x.strip():
            text_targets.append(x)
          else:
            collect_texts(x)
      elif isinstance(item, str) and item.strip():
        text_targets.append(item)

    collect_texts(presentation_data)

    if not text_targets:
      return presentation_data

    is_multi_slide_dict = (
        isinstance(presentation_data, dict)
        and len(presentation_data.keys()) >= 1
        and all(isinstance(v, dict) for v in presentation_data.values())
        and not any(
            k in presentation_data
            for k in (
                "shapes",
                "tables",
                "data",
                "text",
                "slide_job",
                "category",
            )
        )
        and (
            len(presentation_data.keys()) > 1
            or any(
                any(sk in v for sk in ("shapes", "tables", "data"))
                for v in presentation_data.values()
            )
        )
    )

    # If this is a full-deck / slide-keyed dictionary, transform Agenda first, then parallelize remaining slides!
    if is_multi_slide_dict:
      from concurrent.futures import ThreadPoolExecutor

      target_slide_ids = (context or {}).get("target_slide_ids")
      all_slide_ids = list(presentation_data.keys())
      slide_idx_lookup = {
          s_id: idx + 1 for idx, s_id in enumerate(all_slide_ids)
      }

      def is_slide_targeted(s_id):
        if not target_slide_ids:
          return True
        idx_1based = slide_idx_lookup.get(s_id)
        str_targets = {str(x) for x in target_slide_ids}
        return (
            s_id in target_slide_ids
            or str(s_id) in str_targets
            or (
                idx_1based is not None
                and (
                    idx_1based in target_slide_ids
                    or str(idx_1based) in str_targets
                )
            )
        )

      # Pre-fetch customer research once so all threads share cached briefing
      cust_name = (context or {}).get("customer_name")
      if cust_name:
        text_transformer = self.skills.get("text_transformer")
        if text_transformer and hasattr(
            text_transformer, "_get_or_research_customer"
        ):
          try:
            c_res = text_transformer._get_or_research_customer(
                cust_name, context=context
            )
            if c_res and context:
              context["customer_research"] = c_res
          except Exception as ex:
            print(f"[{self.name}] Customer research pre-fetch notice: {ex}")

      # Step A: Identify Agenda slide
      agenda_s_id = None
      for s_id, s_data in presentation_data.items():
        if self._is_agenda_slide(s_data) or "agenda" in str(s_id).lower():
          agenda_s_id = s_id
          break

      agenda_sync_map = {}
      result_deck = {}

      if agenda_s_id is not None:
        if is_slide_targeted(agenda_s_id):
          print(
              f"[{self.name}] Agenda slide detected ({agenda_s_id}) ->"
              " Transforming Agenda first for deck-wide alignment."
          )
          orig_agenda = presentation_data[agenda_s_id]
          trans_agenda = self.transform_presentation(
              orig_agenda,
              output_criteria=output_criteria,
              slide_name=f"Slide {agenda_s_id} (Agenda)",
              context=context,
          )
          result_deck[agenda_s_id] = trans_agenda
          agenda_sync_map = self._extract_agenda_sync_map(
              orig_agenda, trans_agenda
          )
          print(
              f"[{self.name}] Built Agenda Sync Map with {len(agenda_sync_map)}"
              f" section mappings: {list(agenda_sync_map.keys())}"
          )
        else:
          skipped_agenda = dict(presentation_data[agenda_s_id])
          skipped_agenda["_skip_mutation"] = True
          skipped_agenda["skip"] = True
          result_deck[agenda_s_id] = skipped_agenda

      # Step B: Scan deck in sequential order to tag each slide with its current Section Topic and track Divider order!
      slide_section_map = {}
      current_section = ""
      last_slide_id = all_slide_ids[-1] if len(all_slide_ids) > 1 else None
      divider_slides_in_order = []
      agenda_idx = (
          all_slide_ids.index(agenda_s_id)
          if (agenda_s_id in all_slide_ids)
          else -1
      )

      for idx, (s_id, s_data) in enumerate(presentation_data.items()):
        if s_id == agenda_s_id:
          slide_section_map[s_id] = "Agenda"
          continue
        if self.is_internal_enablement_slide(s_data):
          slide_section_map[s_id] = "Internal Enablement"
          continue
        if (agenda_idx != -1 and idx < agenda_idx) or self.is_title_slide(
            s_data
        ):
          slide_section_map[s_id] = "Title Slide"
          continue
        if (
            not target_slide_ids and s_id == last_slide_id
        ) or self.is_closing_slide(s_data):
          slide_section_map[s_id] = "Closing"
          continue
        if self._is_divider_slide(s_data, sync_map=agenda_sync_map):
          divider_slides_in_order.append(s_id)
          seq_idx = len(divider_slides_in_order)
          agenda_seq_list = agenda_sync_map.get("__seq__", [])
          if agenda_seq_list and 1 <= seq_idx <= len(agenda_seq_list):
            current_section = agenda_seq_list[seq_idx - 1]["clean"]
          else:
            divider_texts = []

            def get_t(x):
              if isinstance(x, dict):
                for k, v in x.items():
                  if (
                      k.lower() in ("text", "content")
                      and isinstance(v, str)
                      and v.strip()
                  ):
                    divider_texts.append(v.strip())
                  else:
                    get_t(v)
              elif isinstance(x, list):
                for el in x:
                  get_t(el)

            get_t(s_data)
            clean_d_texts = [
                st
                for st in divider_texts
                if not any(
                    fn in st.lower()
                    for fn in (
                        "proprietary",
                        "confidential",
                        "feedback",
                        "pitchgen",
                        "share feedback",
                        "request pitchhub",
                        "internal use only",
                    )
                )
                and st.strip().lower() != "google cloud"
            ]
            if clean_d_texts:
              d_raw = clean_d_texts[0]
              d_clean = (
                  re.sub(
                      r"^(\d+[\.\-\s:]+|[•\-\*]\s*|section\s*\d+[\.\-\s:]*)",
                      "",
                      d_raw,
                      flags=re.IGNORECASE,
                  )
                  .strip()
                  .lower()
              )
              d_clean = re.sub(r"\s+", " ", d_clean).strip()
              if d_clean in agenda_sync_map:
                current_section = agenda_sync_map[d_clean]["clean"]
              else:
                current_section = d_raw
          slide_section_map[s_id] = f"Section Divider: {current_section}"
        else:
          slide_section_map[s_id] = current_section or "Main Presentation"

      remaining_items = [
          (s_id, s_data)
          for s_id, s_data in presentation_data.items()
          if s_id != agenda_s_id
      ]

      def process_single_slide_worker(item):
        s_id, s_data = item
        if not isinstance(s_data, dict):
          return s_id, s_data

        if not is_slide_targeted(s_id):
          skipped_slide = dict(s_data)
          skipped_slide["_skip_mutation"] = True
          skipped_slide["skip"] = True
          return s_id, skipped_slide

        # 100% Immutable Gate for Closing slide (last slide of full deck or explicit closing slide)
        if (
            not target_slide_ids and s_id == last_slide_id
        ) or self.is_closing_slide(s_data):
          print(
              f"[{self.name}] Slide {s_id} is the Closing slide (0% Immutable)"
              " -> Preserving intact."
          )
          closing_slide = dict(s_data)
          closing_slide["_skip_mutation"] = True
          closing_slide["skip"] = True
          return s_id, closing_slide

        slide_ctx = dict(context or {})
        slide_ctx["current_section"] = slide_section_map.get(s_id, "")
        t_slide = self.transform_presentation(
            s_data,
            output_criteria=output_criteria,
            slide_name=f"Slide {s_id}",
            context=slide_ctx,
        )
        is_skip = bool(
            isinstance(t_slide, dict)
            and (t_slide.get("_skip_mutation") or t_slide.get("skip"))
        )
        if (
            agenda_sync_map
            and not is_skip
            and not self.is_internal_enablement_slide(s_data)
            and not self.is_title_slide(s_data)
            and not self.is_closing_slide(s_data)
            and not self.is_proof_points_slide(s_data)
            and s_id in divider_slides_in_order
        ):
          seq_idx = divider_slides_in_order.index(s_id) + 1
          agenda_seq_list = agenda_sync_map.get("__seq__", [])
          seq_item = (
              agenda_seq_list[seq_idx - 1]
              if (agenda_seq_list and 1 <= seq_idx <= len(agenda_seq_list))
              else None
          )
          t_slide = self._sync_divider_slide(
              s_data,
              t_slide,
              agenda_sync_map,
              slide_name=f"Slide {s_id}",
              seq_item=seq_item,
          )
        return s_id, t_slide

      if remaining_items:
        max_workers = max(1, min(len(remaining_items), 4))
        print(
            f"[{self.name}] Transforming {len(remaining_items)} slides in"
            f" parallel using {max_workers} worker threads..."
        )
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
          results = executor.map(process_single_slide_worker, remaining_items)
          for s_id, transformed_slide in results:
            result_deck[s_id] = transformed_slide

      # Preserve original slide key order
      ordered_deck = {}
      for k in presentation_data.keys():
        if k in result_deck:
          ordered_deck[k] = result_deck[k]
        else:
          ordered_deck[k] = presentation_data[k]
      return ordered_deck

    # Check if this slide is an Internal Enablement / Context slide
    if self.is_internal_enablement_slide(presentation_data, texts=text_targets):
      print(
          f"[{self.name}] Slide '{slide_name or 'current'}' is an Internal"
          " Enablement slide -> Updating metadata fields."
      )
      return self.transform_internal_enablement_slide(
          presentation_data, context=context, criteria=output_criteria
      )

    # Check if this single slide is a 100% Immutable Customer Reference / Proof Points slide
    if self.is_proof_points_slide(presentation_data, texts=text_targets):
      print(
          f"[{self.name}] Slide '{slide_name or 'current'}' is a Customer Reference / Proof Points slide (0% Immutable) -> Preserving original verified content."
      )
      if isinstance(presentation_data, dict):
        result_data = dict(presentation_data)
        result_data["_skip_mutation"] = True
        result_data["skip"] = True
        return result_data
      return presentation_data

    # Check if this single slide is a 100% Immutable Closing / Thank You slide
    if self.is_closing_slide(presentation_data, texts=text_targets):
      print(
          f"[{self.name}] Slide '{slide_name or 'current'}' is a Closing /"
          " Thank You slide (0% Immutable) -> Preserving original closing"
          " layout."
      )
      if isinstance(presentation_data, dict):
        result_data = dict(presentation_data)
        result_data["_skip_mutation"] = True
        result_data["skip"] = True
        return result_data
      return presentation_data

    def verify_and_lint_transformed_text(
        orig_text: str, polished_text: str
    ) -> str:
      """Automated post-transformation visual alignment and sentence integrity validator."""
      if not polished_text or not isinstance(polished_text, str):
        return polished_text

      res = polished_text.strip()

      # 1. Strip leading redundant bullet marks that LLMs sometimes hallucinate into raw text
      res = re.sub(r"^[➔●•\-\*]\s*", "", res)
      res = re.sub(r"\n[➔●•\-\*]\s*", "\n", res)

      # 2. Prevent dangling sentence split across line breaks (e.g. 'Migrate & modernize your\nfinancial data')
      dangling_words = (
          "your",
          "the",
          "and",
          "with",
          "of",
          "to",
          "in",
          "for",
          "across",
          "by",
          "a",
          "an",
          "or",
          "&",
          "+",
          "our",
          "their",
          "its",
          "into",
          "from",
          "on",
          "as",
          "at",
          "ihre",
          "ihren",
          "ihrem",
          "ihrer",
          "die",
          "der",
          "das",
          "den",
          "dem",
          "mit",
          "einer",
          "einem",
          "einen",
          "und",
          "für",
          "in",
          "an",
          "auf",
          "von",
          "zu",
          "über",
          "durch",
          "unter",
          "als",
          "wie",
      )
      if "\n" in res:
        lines = [l.strip() for l in res.split("\n") if l.strip()]
        merged_lines = []
        i = 0
        while i < len(lines):
          curr = lines[i]
          while i + 1 < len(lines):
            next_line = lines[i + 1]
            words = curr.split()
            last_w = re.sub(r"[^\w]", "", words[-1].lower()) if words else ""
            is_dangling = last_w in dangling_words
            is_lower = bool(
                next_line
                and next_line[0].islower()
                and not curr.endswith((".", ":", "!", "?"))
            )
            is_short_cont = (
                len(next_line.split()) <= 2
                and not curr.endswith((".", ":", "!", "?"))
                and len(words) >= 3
            )

            if is_dangling or is_lower or is_short_cont:
              curr = f"{curr} {next_line}"
              i += 1
            else:
              break
          merged_lines.append(curr)
          i += 1
        res = "\n".join(merged_lines)

      # 3. Punctuation & Quotes Balancing
      for q_open, q_close in (
          ('"', '"'),
          ("“", "”"),
          ("«", "»"),
          ("(", ")"),
          ("[", "]"),
      ):
        count_open = res.count(q_open)
        count_close = res.count(q_close)
        if q_open == q_close and count_open % 2 != 0:
          res = f"{res}{q_close}"
        elif q_open != q_close and count_open > count_close:
          res = f"{res}{q_close * (count_open - count_close)}"

      # 4. Material Symbols ligatures restoration
      res = res.replace("WasSPEICHER", "Was ").replace("Was SPEICHER", "Was ")
      res = res.replace("WarumHILFE", "Warum ").replace(
          "Warum HILFE", "Warum "
      )
      res = res.replace("What memory", "What ").replace("Whatmemory", "What ")
      res = res.replace("Why help", "Why ").replace("Whyhelp", "Why ")

      return res

    transformed_cache = {}
    unique_texts = list(dict.fromkeys(text_targets))
    text_transformer = self.skills["text_transformer"]
    if hasattr(text_transformer, "execute_batch") and len(unique_texts) > 1:
      try:
        transformed_texts = text_transformer.execute_batch(
            unique_texts,
            criteria=output_criteria,
            context=context,
            slide_name=slide_name,
            slide_data=presentation_data if isinstance(presentation_data, dict) else None,
        )
        for orig, polished in zip(unique_texts, transformed_texts):
          transformed_cache[orig] = verify_and_lint_transformed_text(
              orig, polished
          )
      except Exception as e:
        print(f"[{self.name}] Batch text transform error: {e}, falling back to single execution")
        for text in unique_texts:
          try:
            raw_polished = text_transformer.execute(
                text,
                criteria=output_criteria,
                context=context,
                slide_name=slide_name,
                slide_data=presentation_data
                if isinstance(presentation_data, dict)
                else None,
            )
            transformed_cache[text] = verify_and_lint_transformed_text(
                text, raw_polished
            )
          except Exception as ex:
            print(f"[{self.name}] Single text transform error: {ex}")
            transformed_cache[text] = text
    else:
      for text in unique_texts:
        try:
          raw_polished = text_transformer.execute(
              text,
              criteria=output_criteria,
              context=context,
              slide_name=slide_name,
              slide_data=presentation_data
              if isinstance(presentation_data, dict)
              else None,
          )
          transformed_cache[text] = verify_and_lint_transformed_text(
              text, raw_polished
          )
        except Exception as ex:
          print(f"[{self.name}] Single text transform error: {ex}")
          transformed_cache[text] = text

    def apply_transformed(item):
      if isinstance(item, dict):
        new_dict = {}
        for k, v in item.items():
          if k.lower() == "text" and isinstance(v, str):
            new_dict[k] = transformed_cache.get(v, v)
          else:
            new_dict[k] = apply_transformed(v)
        return new_dict
      elif isinstance(item, list):
        return [apply_transformed(x) for x in item]
      else:
        return item

    return apply_transformed(presentation_data)

  def run(self, global_state):
    print(f"[{self.name}] Starting creative synthesis...")

    raw_strat = (
        str(global_state.context.get("deck_strategy", "smart_hybrid")).lower()
        if hasattr(global_state, "context")
        and isinstance(global_state.context, dict)
        else "smart_hybrid"
    )
    if any(k in raw_strat for k in ["bespoke", "custom"]):
      strategy = "bespoke_custom"
    elif any(k in raw_strat for k in ["cloudhub"]):
      strategy = "cloudhub"
    else:
      strategy = "smart_hybrid"

    # In bespoke_custom mode, clear non-Customer-Reference reusable slide suggestions BEFORE synthesis
    # so ContentSynthesisWorkflow generates bespoke slides for every outline subtopic while preserving
    # 0% immutable LINKED Customer Reference (Proof_Points) slides.
    if (
        strategy == "bespoke_custom"
        and hasattr(global_state, "reusable_slides")
        and global_state.reusable_slides
    ):
      print(
          f"[{self.name}] Strategy 'bespoke_custom': Clearing non-CR reusable"
          " slide suggestions before synthesis for pure bespoke generation."
      )
      cleaned_reu = {}
      for k, v in global_state.reusable_slides.items():
        s_list = (
            (v or {}).get("suggestions") or [] if isinstance(v, dict) else []
        )
        cr_only = [
            s
            for s in s_list
            if isinstance(s, dict)
            and (
                s.get("_source_datastore_key") == "cust_ref"
                or s.get("is_cust_ref")
                or s.get("is_proof_point")
                or s.get("slide_job") == "Proof_Points"
            )
        ]
        cleaned_reu[k] = {"suggestions": cr_only[:1]}
      global_state.reusable_slides = cleaned_reu

    # 1. Synthesize new content for gaps / bespoke sections
    new_content = self.skills["synthesis"].execute(global_state)
    global_state.generated_content = new_content

    # 2. Map to templates (with visual deduplication!)
    mapped_slides = {}
    used_slide_ids = []
    import re

    if not hasattr(global_state, "reusable_slides") or global_state.reusable_slides is None:
      global_state.reusable_slides = {}

    # --- Prepare Title & Agenda Slides (resolved from Title_Slides_Pres and Agendas_Pres via mapping.json in get_final_content) ---
    from agents.workflows.outline_workflow import OutlineWorkflow

    deck_title = global_state.outline.get("title") if global_state.outline else None
    customer_name = str(global_state.context.get("customer_name", "")).strip() if global_state.context else ""
    cust_res = (
        str(global_state.context.get("customer_research", "")).strip()
        if global_state.context
        else ""
    )
    ind_str = (
        str(global_state.context.get("industry", "")).strip()
        if global_state.context
        else ""
    )
    plays_list = (
        global_state.context.get("required_sales_plays")
        or global_state.context.get("sales_plays")
        if global_state.context
        else None
    )
    deck_title = OutlineWorkflow.normalize_modern_cover_title(
        deck_title or "",
        customer_name=customer_name,
        customer_research=cust_res,
        sales_plays=plays_list,
        industry=ind_str,
    )

    global_state.reusable_slides["title"] = {"suggestions": []}
    if global_state.agendas:
      global_state.reusable_slides["agenda"] = {"suggestions": []}

    # Process content sections according to deck_strategy
    gap_tasks = []
    total_agendas = len(global_state.agendas.keys()) if global_state.agendas else 1
    ctx = (
        global_state.context
        if hasattr(global_state, "context")
        and isinstance(global_state.context, dict)
        else {}
    )
    deck_len_str = str(
        ctx.get("deck_length")
        or ctx.get("request_type")
        or ctx.get("target_slide_count")
        or ""
    ).lower()
    is_comprehensive = any(
        k in deck_len_str for k in ("comprehensive", "15-20")
    )

    for key, content_str in new_content.items():
      reu_sugs = (
          global_state.reusable_slides.get(key, {}).get("suggestions", [])
          if hasattr(global_state, "reusable_slides") and global_state.reusable_slides
          else []
      )
      valid_reusable_count = 0
      if reu_sugs:
        for sug in reu_sugs:
          if isinstance(sug, dict) and sug.get("values") and len(sug["values"]) > 0:
            valid_reusable_count += 1
      has_valid_reusable = valid_reusable_count > 0

      is_anchor_section = (str(key) == "1") or (str(key) == str(total_agendas))
      agenda_info = (
          (global_state.agendas or {}).get(key, {})
          if isinstance(global_state.agendas, dict)
          else {}
      )
      sec_parts = (
          agenda_info.get("parts", []) if isinstance(agenda_info, dict) else []
      )
      target_sec_slides = int(
          (
              agenda_info.get("slide_count")
              if isinstance(agenda_info, dict)
              else 0
          )
          or (agenda_info.get("slides") if isinstance(agenda_info, dict) else 0)
          or len(sec_parts)
          or 1
      )

      if strategy == "cloudhub" and has_valid_reusable:
        print(f"[{self.name}] Strategy 'cloudhub': Section {key} covered by reusable slides. Skipping synthetic generation.")
        continue

      # In smart_hybrid, if a section already has valid_reusable_count >= target_sec_slides
      # (including Opening, Closing/Next Steps, and Comprehensive mode), synthesize 0 bespoke slides
      # and rely on TextTransformerWorkflow to tailor those reusable slides to the section's subtopics.
      if (
          strategy == "smart_hybrid"
          and has_valid_reusable
          and valid_reusable_count >= target_sec_slides
      ):
        print(
            f"[{self.name}] Strategy 'smart_hybrid': Section {key}"
            f" already has {valid_reusable_count} reusable slides (target"
            f" {target_sec_slides}). Skipping extra synthetic slide."
        )
        continue

      synthesized_topics = (
          agenda_info.get("_synthesized_topics")
          if isinstance(agenda_info, dict)
          and isinstance(agenda_info.get("_synthesized_topics"), list)
          and agenda_info.get("_synthesized_topics")
          else sec_parts
      )

      remaining_budget = (
          max(0, target_sec_slides - valid_reusable_count)
          if strategy != "bespoke_custom"
          else target_sec_slides
      )
      if strategy != "bespoke_custom" and remaining_budget <= 0:
        continue

      pattern = r"(?:#+\s*|\*\*)*Slide\s*\d*\s*Title:(?:\*\*)*\s*(.*?)\s*(?:#+\s*|\*\*)*Slide\s*\d*\s*Content:(?:\*\*)*\s*(.*?)(?=(?:#+\s*|\*\*)*Slide\s*\d*\s*Title:|$)"
      matches = re.findall(pattern, content_str, re.DOTALL | re.IGNORECASE)
      if not matches:
        assigned_grp = [
            str(p).strip() for p in synthesized_topics if str(p).strip()
        ]
        subtopic_hint = "; ".join(assigned_grp) if assigned_grp else ""
        min_cards = len(assigned_grp)
        gap_tasks.append(
            (key, 1, "Generated Slide", content_str, subtopic_hint, min_cards)
        )
      else:
        if strategy != "bespoke_custom" and len(matches) > remaining_budget:
          matches = matches[:remaining_budget]
        slide_topic_groups = (
            ContentSynthesisWorkflow.partition_topics_across_slides(
                synthesized_topics, len(matches)
            )
        )
        for idx, (title, content) in enumerate(matches, 1):
          assigned_grp = (
              slide_topic_groups[idx - 1]
              if idx - 1 < len(slide_topic_groups)
              else []
          )
          assigned_grp = [
              str(p).strip() for p in assigned_grp if str(p).strip()
          ]
          subtopic_hint = "; ".join(assigned_grp) if assigned_grp else ""
          min_cards = len(assigned_grp)
          gap_tasks.append((
              key,
              idx,
              title.strip(),
              content.strip(),
              subtopic_hint,
              min_cards,
          ))

    def _infer_bespoke_layout(
        sec_title: str,
        slide_title: str = "",
        slide_content: str = "",
        subtopic_hint: str = "",
    ) -> str:
      # In full deck generation, all bespoke content slides use Context-v1 ("Context")
      # to ensure visual consistency and avoid legacy Next Steps / Timeline / Case Study templates.
      return "Context"

    SlideEngineeringAgent._infer_bespoke_layout = staticmethod(
        _infer_bespoke_layout
    )

    if gap_tasks:
      for task in gap_tasks:
        key, slide_idx, title, content, subtopic_hint, min_cards = task
        agenda_info = (
            (global_state.agendas or {}).get(key, {})
            if isinstance(global_state.agendas, dict)
            else {}
        )
        sec_title = (
            str(agenda_info.get("title", ""))
            if isinstance(agenda_info, dict)
            else ""
        )
        inferred_layout = _infer_bespoke_layout(
            sec_title, title, content, subtopic_hint
        )
        print(
            f"[{self.name}] Mapping parsed slide {slide_idx} for section {key}:"
            f" '{title}' (layout='{inferred_layout}', min_cards={min_cards})..."
        )
        try:
          res = self.skills["mapping"].execute(
              title,
              content,
              layout=inferred_layout,
              used_slide_ids=list(used_slide_ids),
              min_cards=min_cards,
          )
          if res:
            if key not in mapped_slides:
              mapped_slides[key] = {"slides": {}}
            mapped_slides[key]["slides"][str(slide_idx)] = res
            selected_id = res.get("slide_id")
            if selected_id:
              used_slide_ids.append(selected_id)
        except Exception as ex:
          print(f"[{self.name}] Error mapping gap slide '{title}': {ex}")

    # Integrate get_final_content to build the final presentation structure
    class ObjectView(object):
      def __init__(self, d):
        self.__dict__ = d

    title_str = OutlineWorkflow.normalize_modern_cover_title(
        deck_title or "",
        customer_name=customer_name,
        customer_research=cust_res,
        sales_plays=plays_list,
        industry=ind_str,
    )
    item_obj = ObjectView({"title": title_str})
    agendas_dict = global_state.agendas or {}
    reusable_slides_dict = getattr(global_state, "reusable_slides", {}) or {}
    sources_dict = getattr(global_state, "sources", {}) or {}

    finalcontent_struct = get_final_content(
        item=item_obj,
        place_holders=mapped_slides,
        agendas=agendas_dict,
        reusable_slides=reusable_slides_dict,
        sources=sources_dict
    )
    global_state.final_deck_structure = finalcontent_struct.get("sections", {})

    # 3. Dynamically customize retrieved Reusable Slides based on account research & active GTM skills!

    if (
        hasattr(global_state, "reusable_slides")
        and global_state.reusable_slides
    ):
      print(
          f"[{self.name}] Reusable slides ready for assembly; deferring text"
          " transformation to post-assembly holistic pass on live Google"
          " Slides shapes."
      )

    print(f"[{self.name}] Creative synthesis completed.")
    return global_state

  def run_payload(self, input_data):
    """Direct payload processing for layout reshuffling, text polishing and translation.

    Matches the remote SlideEngineeringAgent routing interface.
    """
    if "search_query" in input_data:
      try:
        try:
          from agents.sidebar_agent import sidebar_search as search_impl
        except ImportError:
          from Sidebar_search_generator.agent import sidebar_search as search_impl
        res = search_impl(
            search_query=input_data.get("search_query"),
            strict_search=input_data.get("strict_search", False),
            user_ldap=input_data.get("user_ldap", ""),
        )
        return json.loads(res)
      except Exception as e:
        return {"error": str(e)}

    action = input_data.get("action") or input_data.get("Action")
    if isinstance(action, str) and action.lower() == "transform":
      toggle_val = input_data.get("toggle")
      if toggle_val is None:
        toggle_val = input_data.get("Toggle")

      # User requested layout reshuffle if toggle is False
      if toggle_val is False or str(toggle_val).lower() == "false":
        return self.transform_slide(
            slide_layout=input_data.get("slide_layout"),
            slide_category=input_data.get("slide_category"),
            output_criteria=input_data.get("output_criteria"),
            slide_image_url=input_data.get("slide_image_url"),
            slide_id=input_data.get("slide_id") or input_data.get("slideId"),
        )
      else:
        # Text Transformation / Polishing (toggle is True)
        presentation_id = (
            input_data.get("presentation_id", "")
            or input_data.get("presentationId", "")
        )
        slide_id = input_data.get("slideId", "") or input_data.get("slide_id", "")
        output_criteria = (
            input_data.get("output_criteria")
            or input_data.get("criteria")
            or input_data.get("prompt")
            or input_data.get("instruction")
            or "Improve clarity and professional tone"
        )
        context = {
            "industry": input_data.get("industry", ""),
            "sub_industry": input_data.get("sub_industry", ""),
            "customer_name": input_data.get("customer_name") or input_data.get("customer", ""),
            "audience": input_data.get("audience", ""),
            "salesPlay": input_data.get("salesPlay", ""),
            "region": input_data.get("region", "GLOBAL"),
        }

        # Pre-fetch customer research once so concurrent slide threads reuse the cached briefing
        cust_name = context.get("customer_name")
        if cust_name:
          text_transformer = self.skills.get("text_transformer")
          if text_transformer and hasattr(text_transformer, "_get_or_research_customer"):
            try:
              c_res = text_transformer._get_or_research_customer(cust_name, context=context)
              if c_res:
                context["customer_research"] = c_res
            except Exception as ex:
              print(f"[{self.name}] Customer research pre-fetch error: {ex}")

        # 1. Primary UI Payload Format (Array of slides under "slides" or "sections")
        if "sections" in input_data or "slides" in input_data:
          target_key = "sections" if "sections" in input_data else "slides"
          raw_slides = input_data[target_key]
          target_slide_ids = input_data.get("target_slide_ids") or input_data.get("targetSlideIds")

          if isinstance(raw_slides, list) and len(raw_slides) > 1:
            text_transformer = self.skills.get("text_transformer")
            if text_transformer and hasattr(text_transformer, "execute_deck_holistic"):
              print(f"[{self.name}] Initiating Whole-Deck Holistic Transformation across {len(raw_slides)} slides...")
              transformed_slides = text_transformer.execute_deck_holistic(
                  raw_slides,
                  criteria=output_criteria,
                  context=context,
                  target_slide_ids=target_slide_ids,
              )
            else:
              # Fallback to parallel execution
              from concurrent.futures import ThreadPoolExecutor
              def process_slide_item(args):
                idx, slide = args
                should_transform = True
                if target_slide_ids:
                  slide_id = slide.get("slide_id") or slide.get("id") or slide.get("slideId")
                  should_transform = (
                      (idx + 1) in target_slide_ids
                      or (slide_id in target_slide_ids if slide_id else False)
                      or str(idx + 1) in [str(x) for x in target_slide_ids]
                  )
                if not should_transform:
                  return idx, slide

                t_slide = self.transform_presentation(
                    slide,
                    output_criteria,
                    slide_name=f"Slide {idx + 1}",
                    context=context,
                )
                return idx, t_slide

              max_workers = max(1, min(len(raw_slides), 8))
              with ThreadPoolExecutor(max_workers=max_workers) as executor:
                ordered_results = list(executor.map(process_slide_item, enumerate(raw_slides)))
                ordered_results.sort(key=lambda x: x[0])
                transformed_slides = [r[1] for r in ordered_results]
          elif isinstance(raw_slides, list) and len(raw_slides) == 1:
            should_transform = True
            if target_slide_ids:
              slide = raw_slides[0]
              slide_id = slide.get("slide_id") or slide.get("id") or slide.get("slideId")
              should_transform = (
                  1 in target_slide_ids
                  or (slide_id in target_slide_ids if slide_id else False)
                  or "1" in [str(x) for x in target_slide_ids]
              )
            if should_transform:
              transformed_slides = [
                  self.transform_presentation(
                      raw_slides[0],
                      output_criteria,
                      slide_name="Slide 1",
                      context=context,
                  )
              ]
            else:
              transformed_slides = [raw_slides[0]]
          else:
            should_transform = True
            if target_slide_ids:
              slide_id = raw_slides.get("slide_id") or raw_slides.get("id") or raw_slides.get("slideId")
              should_transform = (
                  1 in target_slide_ids
                  or (slide_id in target_slide_ids if slide_id else False)
                  or "1" in [str(x) for x in target_slide_ids]
              )
            if should_transform:
              transformed_slides = self.transform_presentation(
                  raw_slides, output_criteria, slide_name="Slide 1", context=context
              )
            else:
              transformed_slides = raw_slides
          output_data = dict(input_data)
          output_data[target_key] = transformed_slides
          return {"status": "success", "data": output_data}

        # 2. Presentation Dictionary Payload (when presentation_id is a dict key)
        if presentation_id and presentation_id in input_data and isinstance(input_data[presentation_id], dict):
          pres_dict = input_data[presentation_id]
          target_slide_ids = input_data.get("target_slide_ids") or input_data.get("targetSlideIds")
          if not target_slide_ids and slide_id:
            target_slide_ids = [slide_id]
          if target_slide_ids:
            context["target_slide_ids"] = target_slide_ids

          transformed_pres = self.transform_presentation(
              pres_dict,
              output_criteria=output_criteria,
              slide_name="Full Deck Transform",
              context=context,
          )

          # Option A: Global Deck Cohesion Review across dictionary items
          if len(transformed_pres) > 1 and "text_transformer" in self.skills:
            keys_list = list(transformed_pres.keys())
            slides_list = [transformed_pres[k] for k in keys_list]
            reviewed_slides = self.skills["text_transformer"].review_deck_cohesion(
                slides_list, context=context, criteria=output_criteria
            )
            for k, s in zip(keys_list, reviewed_slides):
              transformed_pres[k] = s

          output_data = dict(input_data)
          output_data[presentation_id] = transformed_pres
          return {"status": "success", "data": output_data}

        # Single Slide Text Transformation Path
        data_list = input_data.get("data", [])
        raw_texts = [item.get("text", "") for item in data_list] if isinstance(data_list, list) else []

        if self.is_proof_points_slide(input_data, texts=raw_texts):
          print(f"[{self.name}] Slide '{slide_id or 'single'}' is Proof_Points (0% Immutable) -> Skipping transform and mutating zero shapes.")
          output_payload = dict(input_data)
          output_payload["action"] = "skipped"
          output_payload["skip"] = True
          output_payload["reason"] = "Proof_Points slides are immutable to preserve verified customer case studies and formatting."
          output_payload["data"] = data_list
          output_payload["json_filename"] = f"reshuffle_true/{presentation_id}_{slide_id}.json"
          content_json_str = json.dumps(output_payload, indent=2)
          return self.skills["slide_assembly"].execute(
              content=content_json_str, status="success"
          )

        text_transformer = self.skills["text_transformer"]
        if hasattr(text_transformer, "execute_batch"):
          texts = [item.get("text", "") for item in data_list]
          transformed_texts = text_transformer.execute_batch(
              texts,
              criteria=output_criteria,
              context=context,
              slide_name=str(slide_id or "Single Slide"),
              slide_data=input_data,
          )
          new_data_list = []
          for item, new_text in zip(data_list, transformed_texts):
            new_item = dict(item)
            if "text" in item:
              new_item["text"] = new_text
            new_data_list.append(new_item)
        else:
          new_data_list = []
          for item in data_list:
            new_item = dict(item)
            if "text" in item:
              original_text = item["text"]
              transformed_text = text_transformer.execute(
                  original_text,
                  criteria=output_criteria,
                  context=context,
                  slide_name=str(slide_id or "Single Slide"),
                  slide_data=input_data,
              )
              new_item["text"] = transformed_text
            new_data_list.append(new_item)

        output_payload = dict(input_data)
        output_payload["data"] = new_data_list
        output_payload["json_filename"] = (
            f"reshuffle_true/{presentation_id}_{slide_id}.json"
        )

        content_json_str = json.dumps(output_payload, indent=2)
        return self.skills["slide_assembly"].execute(
            content=content_json_str, status="success"
        )

    elif action == "translate":
      target_lang = input_data.get("targetLanguage", "German")
      pres_id = input_data.get("presentationId")

      # Extract presentation dict matching presentation_id
      pres_data = input_data.get(pres_id) if pres_id else None

      if target_lang and pres_data is not None:
        transformed_data = self.translate_presentation(pres_data, target_lang)
      else:
        transformed_data = pres_data

      # Return the structured result
      output_data = dict(input_data)
      if pres_id and pres_data is not None:
        output_data[pres_id] = transformed_data

      return {"status": "success", "data": output_data}

    return {"error": f"Unknown action: {action}"}


def _infer_bespoke_layout(
    sec_title: str,
    slide_title: str = "",
    slide_content: str = "",
    subtopic_hint: str = "",
) -> str:
  """Infers bespoke slide layout category for deck generation (exclusively 'Context' from Context-v1)."""
  return "Context"


SlideEngineeringAgent._infer_bespoke_layout = staticmethod(
    _infer_bespoke_layout
)
