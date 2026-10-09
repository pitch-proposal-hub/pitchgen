"""Customer logo resolution and GCS hosting utility using Google-only endpoints."""

import io
import re
from google import genai
from google.cloud import storage
from google.genai import types
import requests

_LOGO_URL_CACHE: dict[str, str] = {}
_LOGO_BYTES_CACHE: dict[str, bytes] = {}
_DOMAIN_CACHE: dict[str, str] = {}
_DOMAINS_LIST_CACHE: dict[str, list[str]] = {}

_KNOWN_ENTERPRISE_DOMAINS: dict[str, str] = {
    "walmart": "walmart.com",
    "target": "target.com",
    "aldi": "aldi.us",
    "aldi us": "aldi.us",
    "aldi sued": "aldi-sued.de",
    "aldi süd": "aldi-sued.de",
    "aldi nord": "aldi-nord.de",
    "lidl": "lidl.com",
    "7-eleven": "7-11int.com",
    "7 eleven": "7-11int.com",
    "h&m": "hm.com",
    "hm": "hm.com",
    "ikea": "ikea.com",
    "ahold delhaize": "aholddelhaize.com",
    "tesco": "tesco.com",
    "sainsbury's": "sainsburys.co.uk",
    "sainsburys": "sainsburys.co.uk",
    "heb": "heb.com",
    "h-e-b": "heb.com",
    "publix": "publix.com",
    "wegmans": "wegmans.com",
    "albertsons": "albertsons.com",
    "whole foods": "wholefoodsmarket.com",
    "home depot": "homedepot.com",
    "the home depot": "homedepot.com",
    "lowes": "lowes.com",
    "lowe's": "lowes.com",
    "costco": "costco.com",
    "kroger": "kroger.com",
    "carrefour": "carrefour.com",
    "lvmh": "lvmh.com",
    "nike": "nike.com",
    "adidas": "adidas.com",
    "starbucks": "starbucks.com",
    "mcdonalds": "mcdonalds.com",
    "mcdonald's": "mcdonalds.com",
    "wendy's": "wendys.com",
    "wendys": "wendys.com",
    "spotify": "spotify.com",
    "netflix": "netflix.com",
    "disney": "disney.com",
    "walt disney": "disney.com",
    "warner bros": "wbd.com",
    "paramount": "paramount.com",
    "sony": "sony.com",
    "jpmorgan": "jpmorganchase.com",
    "jp morgan": "jpmorganchase.com",
    "citi": "citigroup.com",
    "citibank": "citigroup.com",
    "bank of america": "bankofamerica.com",
    "wells fargo": "wellsfargo.com",
    "goldman sachs": "goldmansachs.com",
    "morgan stanley": "morganstanley.com",
    "hsbc": "hsbc.com",
    "barclays": "barclays.com",
    "paypal": "paypal.com",
    "stripe": "stripe.com",
    "visa": "visa.com",
    "mastercard": "mastercard.com",
    "pfizer": "pfizer.com",
    "johnson & johnson": "jnj.com",
    "novartis": "novartis.com",
    "roche": "roche.com",
    "merck": "merck.com",
    "unitedhealth": "unitedhealthgroup.com",
    "mayo clinic": "mayoclinic.org",
    "kaiser permanente": "kaiserpermanente.org",
    "toyota": "toyota.com",
    "ford": "ford.com",
    "general motors": "gm.com",
    "gm": "gm.com",
    "volkswagen": "vw.com",
    "bmw": "bmw.com",
    "mercedes-benz": "mercedes-benz.com",
    "mercedes": "mercedes-benz.com",
    "tesla": "tesla.com",
    "boeing": "boeing.com",
    "airbus": "airbus.com",
    "delta": "delta.com",
    "delta air lines": "delta.com",
    "united airlines": "united.com",
    "american airlines": "aa.com",
    "fedex": "fedex.com",
    "ups": "ups.com",
    "dhl": "dhl.com",
    "uber": "uber.com",
    "airbnb": "airbnb.com",
    "salesforce": "salesforce.com",
    "sap": "sap.com",
    "oracle": "oracle.com",
    "cisco": "cisco.com",
    "ibm": "ibm.com",
    "samsung": "samsung.com",
    "siemens": "siemens.com",
    "ge": "ge.com",
    "general electric": "ge.com",
    "shell": "shell.com",
    "bp": "bp.com",
    "chevron": "chevron.com",
    "exxonmobil": "exxonmobil.com",
    "unilever": "unilever.com",
    "procter & gamble": "pg.com",
    "p&g": "pg.com",
    "nestle": "nestle.com",
    "pepsico": "pepsico.com",
    "coca-cola": "coca-colacompany.com",
    "the coca-cola company": "coca-colacompany.com",
    "verizon": "verizon.com",
    "at&t": "att.com",
    "t-mobile": "t-mobile.com",
    "vodafone": "vodafone.com",
    "nvidia": "nvidia.com",
    "amd": "amd.com",
    "intel": "intel.com",
    "qualcomm": "qualcomm.com",
    "broadcom": "broadcom.com",
    "arm": "arm.com",
    "tsmc": "tsmc.com",
    "asml": "asml.com",
    "anthropic": "anthropic.com",
    "openai": "openai.com",
    "databricks": "databricks.com",
    "snowflake": "snowflake.com",
    "servicenow": "servicenow.com",
    "workday": "workday.com",
    "shopify": "shopify.com",
    "adobe": "adobe.com",
    "palantir": "palantir.com",
    "crowdstrike": "crowdstrike.com",
    "datadog": "datadog.com",
    "uniqlo": "uniqlo.com",
    "fast retailing": "fastretailing.com",
    "nintendo": "nintendo.com",
    "nextera energy": "nexteraenergy.com",
    "nextera": "nexteraenergy.com",
    "rivian": "rivian.com",
    "state of california": "ca.gov",
    "coursera": "coursera.org",
    "atlassian": "atlassian.com",
    "marriott international": "marriott.com",
    "marriott": "marriott.com",
    "maersk": "maersk.com",
    "deloitte": "deloitte.com",
    "john deere": "deere.com",
    "deere": "deere.com",
    "cbre": "cbre.com",
    "allianz": "allianz.com",
    "jpmorgan chase": "jpmorganchase.com",
    "moderna": "modernatx.com",
    "caterpillar": "caterpillar.com",
    "warner bros. discovery": "wbd.com",
    "warner bros discovery": "wbd.com",
    "bmw group": "bmw.com",
    "electronic arts": "ea.com",
    "ea": "ea.com",
    "mercado libre": "mercadolibre.com",
    "mercadolibre": "mercadolibre.com",
    "deutsche bank": "db.com",
    "toyota motor": "toyota.com",
    "canva": "canva.com",
    "axa": "axa.com",
    "lockheed martin": "lockheedmartin.com",
    "rakuten": "rakuten.co.jp",
    "sap se": "sap.com",
    "itau unibanco": "itau.com.br",
    "itaú unibanco": "itau.com.br",
    "itau": "itau.com.br",
    "bosch": "bosch.com",
    "ntt docomo": "docomo.ne.jp",
    "hyundai": "hyundai.com",
    "ubisoft": "ubisoft.com",
    "iberdrola": "iberdrola.com",
    "con edison": "coned.com",
    "epic games": "epicgames.com",
    "reliance jio": "jio.com",
    "bhp": "bhp.com",
    "telstra": "telstra.com.au",
    "bbva": "bbva.com",
    "lufthansa": "lufthansa.com",
    "astrazeneca": "astrazeneca.com",
    "standard chartered": "sc.com",
    "deutsche telekom": "telekom.com",
    "honda": "honda.com",
    "schneider electric": "se.com",
    "danone": "danone.com",
    "booking.com": "booking.com",
}

_SKIP_GROUNDING_DOMAINS = (
    "google.com",
    "googleapis.com",
    "googleusercontent.com",
    "youtube.com",
    "linkedin.com",
    "wikipedia.org",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "bloomberg.com",
    "reuters.com",
    "forbes.com",
    "yahoo.com",
)


def resolve_customer_domains(
    customer_name: str, customer_info: str = "", config: dict | None = None
) -> list[str]:
  """Resolves an ordered waterfall of official corporate/regional domains for a target customer using Grounding with Google Search."""
  if not customer_name or not str(customer_name).strip():
    return []

  clean_name = str(customer_name).strip()
  lower_name = clean_name.lower()
  if lower_name in (
      "-",
      "none",
      "null",
      "n/a",
      "target customer",
      "the customer",
      "google",
      "google cloud",
  ):
    return []

  if lower_name in _DOMAINS_LIST_CACHE:
    return list(_DOMAINS_LIST_CACHE[lower_name])

  candidates: list[str] = []

  def _add_candidate(dom: str) -> None:
    d = (
        re.sub(r"^https?://(?:www\.)?", "", str(dom or "").strip().lower())
        .split("/")[0]
        .strip()
    )
    if (
        d
        and re.match(r"^[a-z0-9][a-z0-9-]{1,61}\.[a-z]{2,}(?:\.[a-z]{2,})?$", d)
        and not any(skip in d for skip in _SKIP_GROUNDING_DOMAINS)
        and d not in candidates
    ):
      candidates.append(d)

  # 1. Check if customer_name itself is already a domain
  domain_match = re.search(
      r"\b([a-z0-9][a-z0-9-]{1,61}\.(?:com|org|net|io|ai|co|edu|gov|de|fr|uk|jp|ca|au|us))\b",
      lower_name,
  )
  if domain_match:
    _add_candidate(domain_match.group(1))
    if candidates:
      _DOMAINS_LIST_CACHE[lower_name] = list(candidates)
      _DOMAIN_CACHE[lower_name] = candidates[0]
      return candidates

  # 2. Check known enterprise map (instant 0ms lookup)
  normalized_key = re.sub(
      r"\b(?:inc\.?|corp\.?|corporation|llc|ltd\.?|limited|group|plc|holdings|company|co\.?)\b",
      "",
      lower_name,
  ).strip(" ,.-")
  if lower_name in _KNOWN_ENTERPRISE_DOMAINS:
    _add_candidate(_KNOWN_ENTERPRISE_DOMAINS[lower_name])
  elif normalized_key in _KNOWN_ENTERPRISE_DOMAINS:
    _add_candidate(_KNOWN_ENTERPRISE_DOMAINS[normalized_key])

  if candidates:
    if candidates[0] == "aldi.us":
      _add_candidate("aldi-sued.de")
      _add_candidate("aldi-nord.de")
    _DOMAINS_LIST_CACHE[lower_name] = list(candidates)
    _DOMAIN_CACHE[lower_name] = candidates[0]
    return candidates

  # 3. Extract explicit website domain from customer_info if present
  if customer_info:
    info_matches = re.findall(
        r"https?://(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?)(?:/|\b)",
        str(customer_info),
    )
    for cand in info_matches:
      _add_candidate(cand)
    if candidates:
      _DOMAINS_LIST_CACHE[lower_name] = list(candidates)
      _DOMAIN_CACHE[lower_name] = candidates[0]
      return candidates

  # 4. Use Gemini fast model with Grounding with Google Search to discover active corporate & regional operating domains
  try:
    project_id = "your-gcp-project-id"
    fast_model = "gemini-3.5-flash-lite"
    if config and "default" in config:
      project_id = config["default"].get("project_name", project_id)
      fast_model = config["default"].get(
          "gemini_model", config["default"].get("gemini_model_1", fast_model)
      )

    client = genai.Client(vertexai=True, project=project_id, location="global")
    prompt = (
        "Find the official active website domains for the company"
        f" '{clean_name}'. Return a comma-separated list of up to 4 active"
        " official domains (including primary US/global/regional operating"
        " domains, e.g. 'aldi.us, aldi-sued.de, aldi-nord.de'). Return ONLY"
        " the domain names separated by commas, with no https://, no paths,"
        " and no extra text."
    )
    resp = None
    try:
      resp = client.models.generate_content(
          model=fast_model,
          contents=prompt,
          config=types.GenerateContentConfig(
              temperature=0.0,
              max_output_tokens=80,
              tools=[types.Tool(google_search=types.GoogleSearch())],
          ),
      )
    except Exception:
      # Fallback to non-grounded generation if GoogleSearch tool is unavailable in a test/mocked environment
      resp = client.models.generate_content(
          model=fast_model,
          contents=(
              "Return ONLY the primary official corporate domain name (e.g.,"
              f" 'walmart.com') for the company '{clean_name}'. Do not include"
              " https://, www., paths, or any other text."
          ),
          config=types.GenerateContentConfig(
              temperature=0.0,
              max_output_tokens=30,
          ),
      )

    if resp and getattr(resp, "text", None):
      for token in re.findall(
          r"\b([a-z0-9][a-z0-9-]{1,61}\.[a-z]{2,}(?:\.[a-z]{2,})?)\b",
          resp.text.lower(),
      ):
        _add_candidate(token)

    # Also harvest verified web domains from Google Search grounding_chunks
    if resp and getattr(resp, "candidates", None):
      gm = getattr(resp.candidates[0], "grounding_metadata", None)
      if gm and getattr(gm, "grounding_chunks", None):
        for ch in gm.grounding_chunks:
          web = getattr(ch, "web", None)
          if web:
            title_dom = getattr(web, "title", "") or ""
            for token in re.findall(
                r"\b([a-z0-9][a-z0-9-]{1,61}\.[a-z]{2,}(?:\.[a-z]{2,})?)\b",
                title_dom.lower(),
            ):
              _add_candidate(token)
  except Exception as e:
    print(
        "[LogoUtil] Gemini grounded domain resolution fallback triggered for"
        f" '{clean_name}': {e}"
    )

  # 5. Deterministic slug fallback (e.g. "Acme Corp" -> "acmecorp.com")
  slug = re.sub(r"[^a-z0-9]", "", normalized_key or lower_name)
  if len(slug) >= 2:
    _add_candidate(f"{slug}.com")

  if candidates:
    _DOMAINS_LIST_CACHE[lower_name] = list(candidates[:4])
    _DOMAIN_CACHE[lower_name] = candidates[0]
    return list(candidates[:4])

  return []


def resolve_customer_domain(
    customer_name: str, customer_info: str = "", config: dict | None = None
) -> str:
  """Resolves the primary official corporate domain for a target customer (e.g.

  'Walmart' -> 'walmart.com').
  """
  if not customer_name or not str(customer_name).strip():
    return ""
  lower_name = str(customer_name).strip().lower()
  if lower_name in _DOMAIN_CACHE:
    return _DOMAIN_CACHE[lower_name]
  domains = resolve_customer_domains(
      customer_name, customer_info=customer_info, config=config
  )
  return domains[0] if domains else ""


def _synthesize_fallback_logo_badge(
    customer_name: str, domain: str = ""
) -> bytes | None:
  """Synthesizes a crisp 256x256 transparent-background executive brand emblem PNG if remote favicon endpoints fail."""
  try:
    from PIL import Image, ImageDraw, ImageFont

    canvas_size = 256
    badge = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(badge)
    # Draw a sleek executive rounded-square emblem with subtle Google Cloud blue/white accent
    margin = 16
    draw.rounded_rectangle(
        [margin, margin, canvas_size - margin, canvas_size - margin],
        radius=48,
        fill=(26, 115, 232, 235),
        outline=(255, 255, 255, 220),
        width=6,
    )
    clean_words = [
        w
        for w in re.split(r"[\s&.-]+", (customer_name or domain or "C").strip())
        if w
        and w.lower()
        not in ("the", "inc", "corp", "llc", "ltd", "se", "group", "plc", "co")
    ]
    if len(clean_words) >= 2:
      monogram = (clean_words[0][0] + clean_words[1][0]).upper()
    elif clean_words and len(clean_words[0]) <= 4:
      monogram = clean_words[0].upper()
    elif clean_words:
      monogram = clean_words[0][:2].upper()
    else:
      monogram = "GC"
    target_font_size = 88 if len(monogram) <= 2 else 64
    font = None
    for font_path in (
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    ):
      try:
        font = ImageFont.truetype(font_path, target_font_size)
        break
      except Exception:
        continue
    if font is None:
      try:
        font = ImageFont.load_default(size=target_font_size)
      except TypeError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), monogram, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (canvas_size - tw) // 2 - bbox[0]
    ty = (canvas_size - th) // 2 - bbox[1]
    draw.text((tx, ty), monogram, fill=(255, 255, 255, 255), font=font)
    out_buf = io.BytesIO()
    badge.save(out_buf, format="PNG")
    return out_buf.getvalue()
  except Exception:
    return None


def _normalize_logo_png_bytes(raw_bytes: bytes) -> bytes | None:
  """Validates non-GIF raster bytes and normalizes onto a clean padded PNG badge for Google Slides."""
  if not raw_bytes or len(raw_bytes) < 64:
    return None
  # Strictly reject GIFs (R0lGOD magic bytes)
  if raw_bytes.startswith((b"GIF87a", b"GIF89a")):
    return None
  # Accept PNG or JPEG magic bytes
  if not (raw_bytes.startswith(b"\x89PNG\r\n\x1a\n") or raw_bytes.startswith(b"\xff\xd8\xff")):
    return None

  try:
    from PIL import Image

    with Image.open(io.BytesIO(raw_bytes)) as img:
      if getattr(img, "is_animated", False) or (img.format and img.format.upper() == "GIF"):
        return None
      w, h = img.size
      # Reject tiny 16x16 generic globe favicons
      if w <= 16 and h <= 16:
        return None
      img_rgba = img.convert("RGBA")
      # Strip outer white/near-white background pixels connected to image borders so the logo is 100% transparent
      px = img_rgba.load()
      visited = set()
      stack = []
      for x in range(w):
        stack.append((x, 0))
        stack.append((x, h - 1))
      for y in range(h):
        stack.append((0, y))
        stack.append((w - 1, y))
      while stack:
        cx, cy = stack.pop()
        if (cx, cy) in visited or cx < 0 or cx >= w or cy < 0 or cy >= h:
          continue
        visited.add((cx, cy))
        r_v, g_v, b_v, a_v = px[cx, cy]
        if a_v == 0 or (r_v >= 232 and g_v >= 232 and b_v >= 232):
          px[cx, cy] = (0, 0, 0, 0)
          stack.extend([(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)])

      # Crop tightly to the non-transparent emblem bounding box
      bbox = img_rgba.getbbox()
      if bbox:
        img_rgba = img_rgba.crop(bbox)
      cw, ch = img_rgba.size

      # Center on a 100% transparent 256x256 square canvas (matching the non-invasive Google Cloud icon on the title slide)
      canvas_size = 256
      badge = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
      max_dim = canvas_size - 16
      scale = min(max_dim / float(max(1, cw)), max_dim / float(max(1, ch)))
      new_w = max(1, int(round(cw * scale)))
      new_h = max(1, int(round(ch * scale)))
      resized = img_rgba.resize((new_w, new_h), Image.Resampling.LANCZOS)
      offset_x = (canvas_size - new_w) // 2
      offset_y = (canvas_size - new_h) // 2
      badge.paste(resized, (offset_x, offset_y), resized)
      out_buf = io.BytesIO()
      badge.save(out_buf, format="PNG")
      return out_buf.getvalue()
  except Exception as e:
    print(f"[LogoUtil] PIL normalization skipped ({e}); returning raw validated PNG/JPEG bytes.")
    return raw_bytes


def fetch_google_customer_logo_bytes(
    domain: str | list[str], customer_name: str = ""
) -> tuple[bytes | None, str]:
  """Fetches a customer logo exclusively using Google endpoints (t2.gstatic.com/faviconV2 & google.com/s2/favicons) across candidate domains with PIL executive badge fallback."""
  if not domain:
    return None, ""

  if isinstance(domain, (list, tuple)):
    raw_domains = [str(d).strip().lower() for d in domain if str(d).strip()]
  else:
    raw_domains = [
        d.strip().lower() for d in str(domain).split(",") if d.strip()
    ]
  if not raw_domains:
    return None, ""

  primary_bare_dom = re.sub(r"^www\.", "", raw_domains[0])
  candidate_domains: list[str] = []
  for rd in raw_domains:
    b_dom = re.sub(r"^www\.", "", rd)
    for v_dom in (b_dom, f"www.{b_dom}"):
      if v_dom not in candidate_domains:
        candidate_domains.append(v_dom)
    if b_dom == "docomo.ne.jp":
      for alt in ("nttdocomo.co.jp", "www.ntt.co.jp", "global.ntt"):
        if alt not in candidate_domains:
          candidate_domains.append(alt)
    elif b_dom in ("toyota.co.jp", "toyota.com"):
      for alt in ("www.toyota.com", "global.toyota"):
        if alt not in candidate_domains:
          candidate_domains.append(alt)
    elif b_dom in ("aldi.com", "aldi.us"):
      for alt in ("aldi.us", "www.aldi.us", "aldi-sued.de", "aldi-nord.de"):
        if alt not in candidate_domains:
          candidate_domains.append(alt)

  google_endpoints = []
  for c_dom in candidate_domains:
    google_endpoints.append(
        f"https://t2.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://{c_dom}&size=256"
    )
    google_endpoints.append(
        f"https://www.google.com/s2/favicons?domain={c_dom}&sz=256"
    )

  for url in google_endpoints:
    try:
      resp = requests.get(url, timeout=8)
      if resp.status_code == 200 and resp.content:
        ctype = resp.headers.get("Content-Type", "").lower()
        if "gif" in ctype:
          continue
        normalized = _normalize_logo_png_bytes(resp.content)
        if normalized:
          return normalized, url
    except Exception as e:
      print(f"[LogoUtil] Google logo endpoint check failed for {url}: {e}")

  # Guaranteed executive monogram/wordmark badge fallback so Slide 1 never lacks a customer logo badge
  fallback_png = _synthesize_fallback_logo_badge(
      customer_name, primary_bare_dom
  )
  if fallback_png:
    return fallback_png, f"synthesized://{primary_bare_dom}"

  return None, ""


def resolve_customer_logo(
    customer_name: str, customer_info: str = "", config: dict | None = None
) -> str:
  """Resolves customer domains via Grounding with Google Search, fetches/caches normalized PNG bytes, uploads to gs://your-pitchgen-content-bucket/customer_logos/, and returns a fresh URL."""
  domains = resolve_customer_domains(
      customer_name, customer_info=customer_info, config=config
  )
  if not domains:
    return ""
  domain = domains[0]

  png_bytes = _LOGO_BYTES_CACHE.get(domain)
  google_source_url = ""
  if not png_bytes:
    png_bytes, google_source_url = fetch_google_customer_logo_bytes(
        domains, customer_name=customer_name
    )
    if png_bytes:
      _LOGO_BYTES_CACHE[domain] = png_bytes
  if not png_bytes:
    return ""

  # Determine target bucket from config.ini ([bucket] content = your-pitchgen-content-bucket)
  bucket_name = "your-pitchgen-content-bucket"
  project_id = "your-gcp-project-id"
  if config:
    if "bucket" in config and config["bucket"].get("content"):
      bucket_name = config["bucket"]["content"]
    if "default" in config and config["default"].get("project_name"):
      project_id = config["default"]["project_name"]

  sanitized_domain = re.sub(r"[^a-z0-9_.-]", "_", domain.lower())
  blob_path = f"customer_logos/{sanitized_domain}.png"

  # Mirror across qa-p2 and dev-p2 just like gcs_util.py so both environments and Slides API can read it
  target_buckets = [bucket_name]
  for b in ("your-pitchgen-content-bucket", "your-pitchgen-content-bucket"):
    if b not in target_buckets:
      target_buckets.append(b)

  uploaded_primary = False
  for b_name in target_buckets:
    try:
      client = storage.Client(project=project_id)
      bucket = client.bucket(b_name)
      blob = bucket.blob(blob_path)
      blob.upload_from_string(png_bytes, content_type="image/png")
      if b_name == bucket_name:
        uploaded_primary = True
    except Exception as e:
      print(f"[LogoUtil] GCS upload to gs://{b_name}/{blob_path} warning: {e}")

  from pitchgen_utils.image_util import generate_gcs_v4_signed_url, image_bytes_to_content_uri

  if uploaded_primary:
    public_url = generate_gcs_v4_signed_url(
        bucket_name=bucket_name,
        blob_name=blob_path,
        project_id=project_id,
        expiration_seconds=86400,
        raw_bytes=png_bytes,
        mime_type="image/png",
    )
    print(f"[LogoUtil] Uploaded normalized customer logo for '{customer_name}' ({domain}) -> {public_url[:110]}")
    return public_url

  # Zero-GCS Drive/Docs contentUri fallback (minted fresh per deck so cleanup_temp_drive_docs never invalidates future decks)
  content_uri, _ = image_bytes_to_content_uri(
      png_bytes, mime_type="image/png", filename=f"logo_{sanitized_domain}"
  )
  if content_uri:
    print(
        "[LogoUtil] Hosted normalized customer logo via Zero-GCS Drive/Docs"
        f" contentUri for '{customer_name}' ({domain})"
    )
    return content_uri

  return (
      google_source_url
      if not google_source_url.startswith("synthesized://")
      else ""
  )
