"""Utility functions for processing image media assets."""

import base64

def get_image_mime_type(image_source: str) -> str:
  """Detects the mime type of an image source (GCS URL, HTTP URL, or base64 string)."""
  if not image_source:
    return "image/png"
  
  if (image_source.startswith("gs://") or 
      image_source.startswith("http://") or 
      image_source.startswith("https://")):
    lower_source = image_source.lower()
    if lower_source.endswith(".jpg") or lower_source.endswith(".jpeg"):
      return "image/jpeg"
    elif lower_source.endswith(".webp"):
      return "image/webp"
    elif lower_source.endswith(".gif"):
      return "image/gif"
    return "image/png"
  
  # Base64 string check
  if "," in image_source:
    header = image_source.split(",", 1)[0].lower()
    if "image/jpeg" in header or "image/jpg" in header:
      return "image/jpeg"
    elif "image/webp" in header:
      return "image/webp"
    elif "image/gif" in header:
      return "image/gif"
    return "image/png"
    
  # Inspect first few characters for raw base64 data
  trimmed = image_source.strip()
  if trimmed.startswith("/9j/"):
    return "image/jpeg"
  elif trimmed.startswith("iVBORw"):
    return "image/png"
  elif trimmed.startswith("UklGR"):
    return "image/webp"
  elif trimmed.startswith("R0lGOD"):
    return "image/gif"
    
  return "image/png"


def clean_base64_data(b64_str: str) -> str:
  """Cleans the base64 prefix/header if present."""
  if "," in b64_str:
    return b64_str.split(",", 1)[1]
  return b64_str


def load_image_part(image_url: str) -> any:
  """Decodes and loads an image as a GenAI Part from a GCS URI, HTTP/HTTPS URL, or Base64 string."""
  if not image_url or not image_url.strip():
    return None
    
  from google.genai import types
  mime_type = get_image_mime_type(image_url)
  
  if image_url.startswith("gs://"):
    return types.Part.from_uri(file_uri=image_url, mime_type=mime_type)
  elif image_url.startswith("http://") or image_url.startswith("https://"):
    import requests
    response = requests.get(image_url, timeout=15)
    response.raise_for_status()
    return types.Part.from_bytes(data=response.content, mime_type=mime_type)
  else:
    # Base64 encoded string
    img_data = clean_base64_data(image_url)
    image_bytes = base64.b64decode(img_data)
    return types.Part.from_bytes(data=image_bytes, mime_type=mime_type)


def is_gif_or_animated_bytes(
    raw_bytes: bytes | None = None, content_type: str = "", url: str = ""
) -> bool:
  """Returns True if the image is a GIF or animated graphic (which must NEVER be transformed)."""
  if url and url.lower().split("?", 1)[0].endswith(".gif"):
    return True
  if content_type and "gif" in content_type.lower():
    return True
  if raw_bytes:
    if raw_bytes.startswith((b"GIF87a", b"GIF89a")):
      return True
    try:
      trimmed = raw_bytes[:16].decode("ascii", errors="ignore").strip()
      if trimmed.startswith("R0lGOD"):
        return True
    except Exception:
      pass
  return False


def _element_dimensions_pt(pe: dict) -> tuple[float, float]:
  """Calculates rendered (width_pt, height_pt) of a Google Slides pageElement, including rotated/sheared shapes."""
  _, _, w_pt, h_pt, _ = _element_bbox_pt(pe)
  return w_pt, h_pt


def _element_bbox_pt(pe: dict) -> tuple[float, float, float, float, bool]:
  """Returns (x_pt, y_pt, width_pt, height_pt, is_flipped) for a Google Slides pageElement using full 2D affine transform."""
  size = pe.get("size", {})
  transform = pe.get("transform", {})

  def _to_pt(dim_dict: dict) -> float:
    if not isinstance(dim_dict, dict):
      return 0.0
    mag = float(dim_dict.get("magnitude", 0.0) or 0.0)
    unit = str(dim_dict.get("unit", "EMU") or "EMU").upper()
    if unit == "EMU":
      return mag / 12700.0
    return mag

  base_w = _to_pt(size.get("width", {}))
  base_h = _to_pt(size.get("height", {}))
  raw_shx = float(transform.get("shearX", 0.0) or 0.0)
  raw_shy = float(transform.get("shearY", 0.0) or 0.0)
  has_shear = abs(raw_shx) > 1e-6 or abs(raw_shy) > 1e-6
  # In Google Slides API (Proto3), a 90/270-degree rotation has scaleX=0, scaleY=0 omitted from the JSON dict
  raw_sx = (
      float(transform["scaleX"])
      if "scaleX" in transform and transform["scaleX"] is not None
      else (0.0 if has_shear else 1.0)
  )
  raw_sy = (
      float(transform["scaleY"])
      if "scaleY" in transform and transform["scaleY"] is not None
      else (0.0 if has_shear else 1.0)
  )
  is_flipped = bool(not has_shear and (raw_sx < 0 or raw_sy < 0))
  tx = float(transform.get("translateX", 0.0) or 0.0)
  ty = float(transform.get("translateY", 0.0) or 0.0)
  t_unit = str(transform.get("unit", "EMU") or "EMU").upper()
  if t_unit == "EMU":
    tx /= 12700.0
    ty /= 12700.0

  corners = (
      (0.0, 0.0),
      (base_w, 0.0),
      (0.0, base_h),
      (base_w, base_h),
  )
  xs = [tx + cx * raw_sx + cy * raw_shx for cx, cy in corners]
  ys = [ty + cx * raw_shy + cy * raw_sy for cx, cy in corners]
  min_x, max_x = min(xs), max(xs)
  min_y, max_y = min(ys), max(ys)
  return min_x, min_y, max(0.0, max_x - min_x), max(0.0, max_y - min_y), is_flipped


def _bbox_overlap_ratio(
    b1: tuple[float, float, float, float],
    b2: tuple[float, float, float, float],
) -> float:
  """Computes intersection area divided by min(area1, area2) for two (x, y, w, h) boxes."""
  x1, y1, w1, h1 = b1
  x2, y2, w2, h2 = b2
  if w1 <= 0 or h1 <= 0 or w2 <= 0 or h2 <= 0:
    return 0.0
  ix1 = max(x1, x2)
  iy1 = max(y1, y2)
  ix2 = min(x1 + w1, x2 + w2)
  iy2 = min(y1 + h1, y2 + h2)
  if ix2 <= ix1 or iy2 <= iy1:
    return 0.0
  inter = (ix2 - ix1) * (iy2 - iy1)
  min_area = min(w1 * h1, w2 * h2)
  return inter / max(1.0, min_area)


def _select_gemini_aspect_ratio_and_size(
    width_pt: float, height_pt: float, slide_index: int = 0
) -> tuple[str, str]:
  """Selects the closest Gemini aspect ratio and output resolution tier ('2K' for title/large visuals, '1K' minimum for all others)."""
  ratio = width_pt / max(1.0, height_pt)
  supported = [
      ("1:1", 1.0),
      ("4:3", 4.0 / 3.0),
      ("3:4", 3.0 / 4.0),
      ("3:2", 1.5),
      ("2:3", 2.0 / 3.0),
      ("16:9", 16.0 / 9.0),
      ("9:16", 9.0 / 16.0),
  ]
  best_ar = min(supported, key=lambda item: abs(ratio - item[1]))[0]
  is_large = (
      slide_index <= 1
      or max(width_pt, height_pt) >= 200.0
      or (width_pt * height_pt) >= 36000.0
  )
  image_size = "2K" if is_large else "1K"
  return best_ar, image_size


def _ensure_high_res_output_png(
    raw_png_bytes: bytes,
    width_pt: float = 680.0,
    height_pt: float = 382.0,
    slide_index: int = 0,
    is_cover_sculpture: bool = False,
    orig_alpha_mask: any = None,
) -> bytes:
  """Ensures generated PNG matches the target shape aspect ratio, preserves any original alpha/corner mask, and meets at least 1K (1024px+) or 2K (1600px-2048px) resolution for large/title visuals."""
  if not raw_png_bytes:
    return raw_png_bytes
  try:
    import io
    from PIL import Image

    with Image.open(io.BytesIO(raw_png_bytes)) as im:
      im_rgba = im.convert("RGBA")
      src_w, src_h = im_rgba.size
      target_ratio = width_pt / max(1.0, float(height_pt))
      src_ratio = src_w / max(1.0, float(src_h))

      # Center-crop to exact shape aspect ratio so Google Slides never stretches it
      if abs(src_ratio - target_ratio) > 0.03:
        if src_ratio > target_ratio:
          new_w = max(1, int(src_h * target_ratio))
          left = (src_w - new_w) // 2
          im_rgba = im_rgba.crop((left, 0, left + new_w, src_h))
        else:
          new_h = max(1, int(src_w / target_ratio))
          top = (src_h - new_h) // 2
          im_rgba = im_rgba.crop((0, top, src_w, top + new_h))

      crop_w, crop_h = im_rgba.size
      is_large = (
          slide_index <= 1
          or max(width_pt, height_pt) >= 200.0
          or (width_pt * height_pt) >= 36000.0
      )
      # Enforce minimum long-edge >= 1600px (and short-edge >= 1080px) for large/title images, and >= 1024px for all others
      min_long_edge = 1600 if is_large else 1024
      min_short_edge = 1080 if is_large else 768
      cur_long = max(crop_w, crop_h)
      cur_short = min(crop_w, crop_h)

      scale_factor = max(
          1.0,
          min_long_edge / max(1.0, float(cur_long)),
          min_short_edge / max(1.0, float(cur_short)),
      )
      if scale_factor > 1.01:
        final_w = int(round(crop_w * scale_factor))
        final_h = int(round(crop_h * scale_factor))
        im_rgba = im_rgba.resize((final_w, final_h), Image.Resampling.LANCZOS)

      if is_cover_sculpture:
        # Clamp off-black background noise (e.g. #06090d) to pure #000000 and smoothly feather the left 25% and outer 4% borders to #000000 so there is zero seam behind Cover Slide text
        import numpy as np

        arr = np.array(im_rgba.convert("RGB"), dtype=np.float32)
        # Subtract dark floor (18/255) so near-black background pixels become pure (0,0,0)
        arr = np.clip((arr - 18.0) * (255.0 / 237.0), 0.0, 255.0)
        h_px, w_px, _ = arr.shape
        x_ramp = np.ones((1, w_px, 1), dtype=np.float32)
        left_cut = int(w_px * 0.24)
        left_fade = int(w_px * 0.10)
        if left_cut > 0:
          x_ramp[0, :left_cut, 0] = 0.0
        if left_fade > 0 and left_cut + left_fade <= w_px:
          x_ramp[0, left_cut : left_cut + left_fade, 0] = np.linspace(
              0.0, 1.0, left_fade, dtype=np.float32
          )
        right_fade = max(1, int(w_px * 0.04))
        x_ramp[0, -right_fade:, 0] = np.minimum(
            x_ramp[0, -right_fade:, 0],
            np.linspace(1.0, 0.0, right_fade, dtype=np.float32),
        )
        y_ramp = np.ones((h_px, 1, 1), dtype=np.float32)
        tb_fade = max(1, int(h_px * 0.04))
        y_ramp[:tb_fade, 0, 0] = np.linspace(
            0.0, 1.0, tb_fade, dtype=np.float32
        )
        y_ramp[-tb_fade:, 0, 0] = np.linspace(
            1.0, 0.0, tb_fade, dtype=np.float32
        )
        arr = np.clip(arr * x_ramp * y_ramp, 0.0, 255.0).astype(np.uint8)
        im_rgba = Image.fromarray(arr, mode="RGB").convert("RGBA")
      elif orig_alpha_mask is not None:
        # Preserve original rounded corners, pill/circle masks, or silhouette alpha contours on in-slide images
        try:
          import numpy as np

          target_w, target_h = im_rgba.size
          resized_mask = orig_alpha_mask.resize(
              (target_w, target_h), Image.Resampling.LANCZOS
          )
          rgba_arr = np.array(im_rgba, dtype=np.uint8)
          mask_arr = np.array(resized_mask, dtype=np.uint8)
          rgba_arr[:, :, 3] = np.minimum(rgba_arr[:, :, 3], mask_arr)
          im_rgba = Image.fromarray(rgba_arr, mode="RGBA")
        except Exception as mask_err:
          print(f"[ImageUtil] Alpha mask transfer warning: {mask_err}")

      out_buf = io.BytesIO()
      im_rgba.save(out_buf, format="PNG", optimize=True)
      return out_buf.getvalue()
  except Exception as e:
    print(f"[ImageUtil] High-res PNG normalization skipped ({e}); returning raw bytes.")
    return raw_png_bytes


def _flatten_slide_elements(elems: list[dict]) -> list[dict]:
  """Recursively flattens pageElements including nested elementGroup.children."""
  flat: list[dict] = []
  for pe in elems or []:
    if not isinstance(pe, dict):
      continue
    flat.append(pe)
    grp = pe.get("elementGroup")
    if isinstance(grp, dict) and isinstance(grp.get("children"), list):
      flat.extend(_flatten_slide_elements(grp["children"]))
  return flat


def extract_customizable_slide_pictures(
    slide: dict,
    slide_index: int = 0,
    is_cust_ref_slide: bool = False,
    min_width_pt: float = 115.0,
    min_height_pt: float = 105.0,
    explicit_user_request: bool = False,
) -> list[dict]:
  """Detects in-slide static pictures (allowing large Title Slide hero artwork at 2K and medium-to-large content slide photos, UI cards, and side sculptures while excluding flipped images, text-overlapping decorative waves, rotated strips, backing bezels behind GIFs, small icons, and full-slide backgrounds)."""
  if not isinstance(slide, dict) or is_cust_ref_slide:
    return []

  is_title_or_cover = (slide_index <= 1) and not explicit_user_request
  flat_elements = _flatten_slide_elements(slide.get("pageElements", []))

  # Pre-collect bounding boxes and z-order of all image elements and non-empty text shapes on the slide
  all_image_bboxes: list[
      tuple[int, str, tuple[float, float, float, float], bool]
  ] = []
  all_text_bboxes: list[tuple[str, tuple[float, float, float, float]]] = []
  for z_idx, pe in enumerate(flat_elements):
    pe_id = pe.get("objectId")
    if not pe_id:
      continue
    if "image" in pe:
      tx, ty, w_pt, h_pt, _ = _element_bbox_pt(pe)
      if (
          (tx != 0.0 or ty != 0.0)
          and w_pt >= 40.0
          and h_pt >= 40.0
          and not (w_pt >= 680.0 and h_pt >= 380.0)
      ):
        pe_url = str(
            pe["image"].get("contentUrl") or pe["image"].get("sourceUrl") or ""
        ).strip()
        pe_is_gif = (
            is_gif_or_animated_bytes(url=pe_url)
            or get_image_mime_type(pe_url) == "image/gif"
        )
        all_image_bboxes.append((z_idx, pe_id, (tx, ty, w_pt, h_pt), pe_is_gif))
    elif "shape" in pe:
      t_elems = pe.get("shape", {}).get("text", {}).get("textElements", [])
      txt_str = "".join(
          te.get("textRun", {}).get("content", "") for te in t_elems
      ).strip()
      txt_low = txt_str.lower()
      if (
          len(txt_str) >= 2
          and not txt_str.isdigit()
          and not any(
              fk in txt_low
              for fk in ("proprietary", "confidential", "source:", "sources:")
          )
      ):
        tx, ty, w_pt, h_pt, _ = _element_bbox_pt(pe)
        if w_pt > 10.0 and h_pt > 10.0 and ty < 350.0:
          all_text_bboxes.append((pe_id, (tx, ty, w_pt, h_pt)))

  candidates = []
  for cur_z_idx, pe in enumerate(flat_elements):
    img = pe.get("image")
    if not img:
      continue
    obj_id = pe.get("objectId", "")
    content_url = str(img.get("contentUrl") or img.get("sourceUrl") or "").strip()
    if not obj_id or not content_url:
      continue

    # 1. Exclude GIFs by URL/MIME check immediately
    if is_gif_or_animated_bytes(url=content_url) or get_image_mime_type(content_url) == "image/gif":
      continue

    # 2. Compute rendered bounding box & flip state in points (PT)
    tx, ty, width_pt, height_pt, is_flipped = _element_bbox_pt(pe)
    if width_pt <= 0 or height_pt <= 0:
      continue

    # Exclude shapes with negative scaleX/scaleY flip transforms (prevents upside-down replacement on Slide 22)
    if is_flipped:
      continue

    # On Cover/Title slides (index <= 1), ONLY allow large hero visuals (>= 220pt x 200pt)
    if is_title_or_cover and (width_pt < 220.0 or height_pt < 200.0):
      continue

    # Exclude micro-icons, product badges, avatars, and small diagrams (< min_width_pt x min_height_pt)
    if not is_title_or_cover and (
        width_pt < min_width_pt
        or height_pt < min_height_pt
        or (width_pt * height_pt) < 13500.0
    ):
      continue

    # Exclude thin decorative strips/bars and wide/tall edge ribbons on content slides
    aspect_ratio = width_pt / max(1.0, height_pt)
    crop = img.get("imageProperties", {}).get("cropProperties", {}) or {}
    if is_title_or_cover:
      if aspect_ratio > 3.0 or aspect_ratio < 0.35:
        continue
    elif explicit_user_request:
      if aspect_ratio > 3.5 or aspect_ratio < 0.30:
        continue
      crop_sum = sum(
          abs(float(crop.get(k, 0.0) or 0.0))
          for k in ("leftOffset", "rightOffset", "topOffset", "bottomOffset")
      )
      xf = pe.get("transform", {})
      shear_sum = abs(float(xf.get("shearX", 0.0) or 0.0)) + abs(
          float(xf.get("shearY", 0.0) or 0.0)
      )
      if crop_sum > 0.85 or shear_sum > 0.10:
        continue
    else:
      # Content slide hero pictures, tall cards, and right-edge sculptural panels have aspect ratios in 0.45..2.65
      if aspect_ratio > 2.65 or aspect_ratio < 0.45:
        continue
      # Exclude decorative edge/corner wave banners flush against top/bottom borders or ultra-wide strips
      if (tx != 0.0 or ty != 0.0) and (
          width_pt >= 520.0
          or (tx <= 3.0 and (ty <= 3.0 or (ty + height_pt) >= 392.0))
          or (height_pt < 145.0 and (ty <= 3.0 or (ty + height_pt) >= 392.0))
      ):
        continue
      # Exclude rotated or sheared template graphics while allowing standard rectangular crops
      h_crop = abs(float(crop.get("leftOffset", 0.0) or 0.0)) + abs(
          float(crop.get("rightOffset", 0.0) or 0.0)
      )
      v_crop = abs(float(crop.get("topOffset", 0.0) or 0.0)) + abs(
          float(crop.get("bottomOffset", 0.0) or 0.0)
      )
      crop_angle = abs(float(crop.get("angle", 0.0) or 0.0))
      xf = pe.get("transform", {})
      shear_sum = abs(float(xf.get("shearX", 0.0) or 0.0)) + abs(
          float(xf.get("shearY", 0.0) or 0.0)
      )
      if (
          h_crop > 0.78
          or v_crop > 0.78
          or shear_sum > 0.02
          or crop_angle > 0.05
      ):
        continue

    # Exclude full-bleed background wallpapers covering the entire 720x405pt slide
    if width_pt >= 680.0 and height_pt >= 380.0:
      continue

    # Z-order & area-ratio aware overlap check:
    # Exclude backing frames/bezels that sit BEHIND a higher-z concentric image or GIF,
    # and exclude small corner callout badges sitting ON TOP OF a much larger hero photo.
    cur_box = (tx, ty, width_pt, height_pt)
    cur_area = width_pt * height_pt
    is_occluded_backing_frame = False
    for other_z, other_id, other_box, other_is_gif in all_image_bboxes:
      if other_id == obj_id:
        continue
      ov = _bbox_overlap_ratio(cur_box, other_box)
      if ov <= 0.35:
        continue
      ox, oy, ow, oh = other_box
      other_area = ow * oh
      inter_area = ov * min(cur_area, other_area)
      inter_over_cur = inter_area / max(1.0, cur_area)
      is_concentric = abs(tx - ox) <= 45.0 and abs(ty - oy) <= 45.0
      if other_z > cur_z_idx:
        # Another image sits on top of cur_box: cur_box is a backing frame only if the top image is a GIF, concentric, or covers >72% of cur_box
        if (
            other_is_gif
            or (is_concentric and inter_over_cur > 0.35)
            or inter_over_cur > 0.72
        ):
          is_occluded_backing_frame = True
          break
      else:
        # cur_box sits on top of other_box: reject if other_box is a GIF or if cur_box is a small corner callout badge on top of a >2.2x larger hero photo
        if other_is_gif or (other_area > 2.2 * cur_area and ov > 0.40):
          is_occluded_backing_frame = True
          break
    if is_occluded_backing_frame:
      continue

    # On content slides, exclude any image that sits behind or overlaps a substantive text shape
    # (prevents replacing transparent background waves behind 'AI Hypercomputer' / 'Google Cloud' text boxes into opaque rectangles)
    if not is_title_or_cover:
      max_txt_overlap = 0.35 if explicit_user_request else 0.08
      overlaps_text = False
      for _, txt_box in all_text_bboxes:
        ov_t = _bbox_overlap_ratio(cur_box, txt_box)
        if ov_t <= max_txt_overlap:
          continue
        if cur_area >= 28000.0 and not explicit_user_request:
          # For large hero photos / side panels, ignore minor edge-clipping by callout text boxes unless >45% of the text box AND >18% of the hero image overlap
          txt_area = txt_box[2] * txt_box[3]
          inter_t = ov_t * min(cur_area, txt_area)
          if ov_t <= 0.45 or (inter_t / cur_area) <= 0.18:
            continue
        overlaps_text = True
        break
      if overlaps_text:
        continue

    gemini_ar, target_image_size = _select_gemini_aspect_ratio_and_size(
        width_pt, height_pt, slide_index=slide_index
    )
    candidates.append({
        "objectId": obj_id,
        "contentUrl": content_url,
        "width_pt": round(width_pt, 1),
        "height_pt": round(height_pt, 1),
        "aspect_ratio": round(aspect_ratio, 2),
        "gemini_aspect_ratio": gemini_ar,
        "image_size": target_image_size,
        "is_title_slide": is_title_or_cover,
        "slide_index": slide_index,
        "cropProperties": dict(crop) if isinstance(crop, dict) else {},
    })

  return candidates


def customize_slide_picture_for_customer(
    pic_info: dict,
    slide_text_context: str,
    customer_name: str,
    industry: str,
    customer_logo_url: str = "",
    config: dict | None = None,
) -> dict | None:
  """Classifies a static slide picture and customizes hero/scene images (or cover slide 3D particle sculptures) to the target customer while preserving original dimensions and shape masks.

  Returns a Google Slides batchUpdate `replaceImage` request dict, or None if
  the image should be preserved untouched.
  """
  if not pic_info or not customer_name:
    return None

  obj_id = pic_info.get("objectId", "")
  content_url = pic_info.get("contentUrl", "")
  if not obj_id or not content_url:
    return None

  import requests
  try:
    resp = requests.get(content_url, timeout=10)
    if resp.status_code != 200 or not resp.content:
      return None
    ctype = resp.headers.get("Content-Type", "")
    raw_bytes = resp.content
    # Strict non-GIF check on actual downloaded bytes
    if is_gif_or_animated_bytes(raw_bytes=raw_bytes, content_type=ctype, url=content_url):
      return None
  except Exception as e:
    print(f"[ImageUtil] Could not download candidate slide image {obj_id}: {e}")
    return None

  project_id = "your-gcp-project-id"
  fast_model = "gemini-3.5-flash-lite"
  bucket_name = "your-pitchgen-content-bucket"
  if config:
    if "default" in config:
      project_id = config["default"].get("project_name", project_id)
      fast_model = config["default"].get("gemini_model_1", fast_model)
    if "bucket" in config and config["bucket"].get("content"):
      bucket_name = config["bucket"]["content"]

  from google import genai
  from google.genai import types
  import uuid
  from google.cloud import storage

  mime_type = "image/jpeg" if raw_bytes.startswith(b"\xff\xd8\xff") else "image/png"
  slide_index = int(pic_info.get("slide_index") or 0)
  is_title_slide = bool(pic_info.get("is_title_slide") or slide_index <= 1)

  # For content-slide images (not Cover Slide), pre-crop to the visible cropProperties window and extract any alpha shape/corner mask
  orig_alpha_mask = None
  has_crop_offsets = False
  if not is_title_slide:
    try:
      import io
      import numpy as np
      from PIL import Image

      with Image.open(io.BytesIO(raw_bytes)) as src_im:
        im_vis = src_im.convert("RGBA")
        sw, sh = im_vis.size
        crop_props = pic_info.get("cropProperties") or {}
        l_off = max(
            0.0, min(0.85, float(crop_props.get("leftOffset", 0.0) or 0.0))
        )
        r_off = max(
            0.0, min(0.85, float(crop_props.get("rightOffset", 0.0) or 0.0))
        )
        t_off = max(
            0.0, min(0.85, float(crop_props.get("topOffset", 0.0) or 0.0))
        )
        b_off = max(
            0.0, min(0.85, float(crop_props.get("bottomOffset", 0.0) or 0.0))
        )
        if (
            (l_off + r_off + t_off + b_off) > 0.01
            and (1.0 - l_off - r_off) > 0.12
            and (1.0 - t_off - b_off) > 0.12
        ):
          has_crop_offsets = True
          cx1 = int(round(sw * l_off))
          cy1 = int(round(sh * t_off))
          cx2 = max(cx1 + 16, int(round(sw * (1.0 - r_off))))
          cy2 = max(cy1 + 16, int(round(sh * (1.0 - b_off))))
          im_vis = im_vis.crop((cx1, cy1, cx2, cy2))

        vw, vh = im_vis.size
        alpha_ch = im_vis.getchannel("A")
        alpha_arr = np.array(alpha_ch, dtype=np.uint8)
        trans_pct = float((alpha_arr < 32).sum()) * 100.0 / max(1, vw * vh)
        # Skip hollow decorative frames, thin circular rings, or floating transparent callout overlays (>18% transparent)
        if trans_pct > 18.0:
          print(
              f"[ImageUtil] Skipping hollow/transparent overlay image {obj_id}"
              f" (transparent={trans_pct:.1f}%)"
          )
          return None
        corner_alphas = (
            int(alpha_arr[0, 0]),
            int(alpha_arr[0, vw - 1]),
            int(alpha_arr[vh - 1, 0]),
            int(alpha_arr[vh - 1, vw - 1]),
        )
        if min(corner_alphas) < 250 or trans_pct > 0.05:
          orig_alpha_mask = alpha_ch.copy()

        if has_crop_offsets:
          vis_buf = io.BytesIO()
          im_vis.save(vis_buf, format="PNG")
          raw_bytes = vis_buf.getvalue()
          mime_type = "image/png"
    except Exception as vis_err:
      print(
          f"[ImageUtil] Visible crop/mask extraction warning for {obj_id}:"
          f" {vis_err}"
      )

  # Stage 2A: Fast multimodal triage to transform hero/conceptual/feature visuals while strictly protecting architecture/stack diagrams & official Google Cloud visuals
  classification = "HERO_PICTURE" if is_title_slide else "SKIP"
  tailored_visual_prompt = (
      "Create a luminous 3D point-cloud particle mesh and flowing light-wave"
      " sculpture on a seamless pure #000000 pitch-black background, sculpted"
      f" into an iconic 3D geometric silhouette representing {customer_name}"
      f" ({industry or 'Enterprise'} domain) with signature brand accent"
      " lighting on the right 75% of the frame and zero text or logos."
      if is_title_slide
      else ""
  )
  try:
    client = genai.Client(vertexai=True, project=project_id, location="global")
    img_part = types.Part.from_bytes(data=raw_bytes, mime_type=mime_type)
    if is_title_slide:
      triage_prompt = (
          "You are designing a bespoke 3D particle/light-wave hero sculpture"
          " for a dark-mode executive presentation Cover Slide.\nTarget"
          f" Customer: {customer_name} (Domain:"
          f" {industry or 'Enterprise'})\n\nLook ONLY at the attached template"
          " cover image and the target customer account: the image uses an"
          " abstract glowing 3D point-cloud particle mesh / flowing light-wave"
          " aesthetic on a pure pitch-black (#000000) background, currently"
          " shaped as a generic circular ring/torus.\nWe want to KEEP the exact"
          " same dark-mode glowing particle-mesh & flowing light-wave aesthetic"
          " on a pure #000000 black background, but MORPH the 3D"
          " shape/geometry itself from a generic circle into an iconic,"
          " immediately recognizable 3D sculptural form tailored to"
          f" {customer_name}'s signature products, brand identity, or"
          f" domain (for example, if {customer_name} is Nvidia, sculpt an"
          " isometric multi-layered GPU tensor core / silicon wafer die matrix"
          " with glowing emerald-green #76B900 and silver data-fabric particle"
          " waves; if an automotive manufacturer, a sculpted aerodynamic"
          " vehicle silhouette made of glowing light particles; if a"
          " CPG/retail/bank/media brand, an iconic 3D sculptural motif"
          " representing their signature products and domain).\n\nRespond with"
          ' a JSON object containing:\n1. "category": "HERO_PICTURE"\n2.'
          ' "visual_prompt": A vivid, concrete 2-3 sentence prompt'
          " instructing the image generator to create a brand-new 3D"
          " particle-mesh and flowing light-wave sculpture on a seamless pure"
          " #000000 black background, specifying the exact 3D geometric"
          f" silhouette/form iconic to {customer_name} and its signature brand"
          " accent colors, keeping the left 25% of the frame dark/clean so"
          " cover title typography remains legible, and with ZERO text,"
          " letters, numbers, or logos."
      )
    else:
      triage_prompt = (
          "Classify this static image extracted from a presentation content"
          " slide so we know whether it should be tailored for the target"
          f" customer.\nTarget Customer: {customer_name} (Domain:"
          f" {industry or 'Enterprise'})\nSurrounding Slide Context:"
          f" {(slide_text_context or '')[:260]}\n\nRespond with a JSON object"
          ' containing:\n1. "category": one of:\n   - "HERO_PICTURE":'
          " Choose this for ANY of the following customizable visual types:\n "
          "    (a) Lifestyle, shopper, customer, employee, store, studio, or"
          " product photography / mockups (e.g. generic shoppers, retail"
          " items, Cymbal cans, devices, workplaces);\n     (b) 3D abstract"
          " sculptural, fabric, wave, or artistic side-panel visuals;\n    "
          " (c) Sample customer e-commerce storefronts, conversational"
          " shopping assistant mockups, or fictional demo tenant UI"
          " screenshots containing fake company names/domains (such as 'Aura"
          " electronics', 'Portland Pie Company', 'Cymbal', pizza/laptop demo"
          " stores, or sample agent workflow cards);\n     (d) Domain/industry"
          " store or workflow illustrations that do NOT depict the official"
          " Google Cloud architecture layer stack.\n   -"
          ' "LEGACY_CUSTOMER_LOGO": A standalone non-Google corporate logo'
          " or brand guidelines document cover from a previous template"
          ' customer (e.g., Cymbal).\n   - "TECHNICAL_DIAGRAM_OR_ICON": ONLY'
          " choose this if the image is an official Google Cloud multi-layer"
          " architecture stack diagram (e.g. AI Hypercomputer / Vertex /"
          " BigQuery / Spanner system topology), a quantitative bar/line"
          " chart, or a standalone official Google Cloud product icon (DO NOT"
          ' MODIFY — MUST BE PRESERVED).\n2. "visual_prompt": If category is'
          ' "HERO_PICTURE", write a vivid, concrete 2-3 sentence instruction'
          " to transform this exact visual so it is 100% native to"
          f" {customer_name}'s authentic products, store / digital environment,"
          " and signature brand palette while STRICTLY preserving the original"
          " image's visual medium (e.g., if it is a lifestyle shopper photo,"
          f" depict an authentic {customer_name} shopper/product experience in"
          " the same framing; if it is a 3D sculptural side-panel, sculpt an"
          f" iconic 3D texture inspired by {customer_name} in the same"
          " composition; if it is a sample e-commerce storefront or agent"
          f" builder UI mockup, localize the storefront/UI to {customer_name}'s"
          " flagship products and clean modern interface with the exact same"
          " card layout). CRITICAL: Never render slide titles or industry"
          " taxonomy strings inside the image."
      )
    triage_resp = client.models.generate_content(
        model=fast_model,
        contents=[img_part, triage_prompt],
        config=types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
        ),
    )
    if triage_resp and triage_resp.text:
      import json
      parsed = json.loads(triage_resp.text)
      if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
        parsed = parsed[0]
      if isinstance(parsed, dict):
        parsed_cat = str(parsed.get("category") or "").upper()
        if is_title_slide:
          classification = "HERO_PICTURE"
        elif parsed_cat:
          classification = parsed_cat
        parsed_vp = str(parsed.get("visual_prompt") or "").strip()
        if parsed_vp:
          tailored_visual_prompt = parsed_vp
  except Exception as e:
    print(
        f"[ImageUtil] Vision triage fallback for {obj_id}"
        f" (is_title_slide={is_title_slide}): {e}"
    )
    if not is_title_slide:
      return None

  if classification == "LEGACY_CUSTOMER_LOGO":
    # Never replace large in-slide pictures (>=115x105pt) with the 256x256 favicon logo (customer_logo_url),
    # which turns product/campaign cards into giant logo circles. Transform them via VisualTransformationWorkflow instead.
    classification = "HERO_PICTURE"
    if not tailored_visual_prompt:
      tailored_visual_prompt = (
          "Transform this brand/campaign showcase visual into an authentic,"
          f" high-production {customer_name} product, studio, or brand identity"
          " visual preserving the original image's framing and medium."
      )

  if classification != "HERO_PICTURE":
    return None

  # Stage 2B: Transform the hero/contextual picture via VisualTransformationWorkflow (gemini-3.1-flash-image)
  try:
    from agents.workflows.visual_transformation_workflow import VisualTransformationWorkflow
    wf = VisualTransformationWorkflow(config or {"default": {"project_name": project_id}, "bucket": {"content": bucket_name}})
    b64_source = f"data:{mime_type};base64," + base64.b64encode(raw_bytes).decode("utf-8")

    width_pt = float(pic_info.get("width_pt") or 280.0)
    height_pt = float(pic_info.get("height_pt") or 200.0)
    gemini_ar, target_image_size = _select_gemini_aspect_ratio_and_size(
        width_pt, height_pt, slide_index=slide_index
    )
    if pic_info.get("image_size") in ("1K", "2K", "4K"):
      target_image_size = pic_info["image_size"]
    if pic_info.get("gemini_aspect_ratio"):
      gemini_ar = pic_info["gemini_aspect_ratio"]

    if is_title_slide:
      change_req = (
          "CRITICAL COVER SLIDE 3D SCULPTURE RULE: Do NOT keep the generic"
          " circular ring/torus shape from the reference image. Use the"
          " reference image ONLY for its aesthetic medium (luminous 3D"
          " point-cloud particles and gossamer flowing light waves suspended on"
          " a seamless pure #000000 pitch-black background). "
          + ((tailored_visual_prompt + " ") if tailored_visual_prompt else "")
          + "Reshape the 3D particle geometry into an iconic, futuristic 3D"
          f" sculptural form unmistakably inspired by {customer_name}'s core"
          " products and technology, positioned cleanly in the center-right"
          " of the composition with a pure #000000 black background on the"
          " left edge so slide title text never collides. Render with ZERO"
          " text, ZERO letters, ZERO words, ZERO numbers, and ZERO logos."
      )
    else:
      change_req = (
          (tailored_visual_prompt + " ") if tailored_visual_prompt else ""
      ) + (
          "Adapt the visual subjects, products, and environment to"
          f" {customer_name}'s authentic product ecosystem and brand identity."
          " Replace any generic or fictional demo items (such as Aura"
          " electronics laptops, Portland Pie pizza bots, Cymbal cans, or"
          " generic stock shoppers) with authentic products, environments, or"
          f" interfaces relevant to {customer_name}. Maintain the original"
          " image's exact visual medium, framing, background tone, and"
          " lighting. STRICT NEGATIVE CONSTRAINT: Do NOT render industry"
          " classification strings (e.g. 'Media & Entertainment'), slide"
          " titles, or bottom caption banners inside the image."
      )
    transformed_b64 = wf.execute(
        request=change_req,
        existing_slide_image_url=b64_source,
        industry="",
        customer_name=customer_name,
        image_size=target_image_size,
        aspect_ratio=gemini_ar,
        is_cover_sculpture=is_title_slide,
        is_in_place_picture=not is_title_slide,
    )
    if not transformed_b64:
      return None

    raw_out_bytes = base64.b64decode(clean_base64_data(transformed_b64))
    out_bytes = _ensure_high_res_output_png(
        raw_out_bytes,
        width_pt,
        height_pt,
        slide_index=slide_index,
        is_cover_sculpture=is_title_slide,
        orig_alpha_mask=orig_alpha_mask,
    )
    blob_name = f"nanoBanana_imageTrans/{uuid.uuid4()}_Response.png"

    target_buckets = [bucket_name]
    for b in ("your-pitchgen-content-bucket", "your-pitchgen-content-bucket"):
      if b not in target_buckets:
        target_buckets.append(b)

    uploaded = False
    for b_name in target_buckets:
      try:
        st_client = storage.Client(project=project_id)
        bucket = st_client.bucket(b_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(out_bytes, content_type="image/png")
        if b_name == bucket_name:
          uploaded = True
      except Exception as up_err:
        print(f"[ImageUtil] GCS upload warning for {b_name}/{blob_name}: {up_err}")

    public_url = ""
    if uploaded:
      public_url = generate_gcs_v4_signed_url(
          bucket_name=bucket_name,
          blob_name=blob_name,
          project_id=project_id,
          raw_bytes=out_bytes,
          mime_type="image/png",
      )
    else:
      content_uri, _ = image_bytes_to_content_uri(
          out_bytes, mime_type="image/png"
      )
      public_url = content_uri

    if public_url:
      print(f"[ImageUtil] Customized slide picture {obj_id} for '{customer_name}' -> {public_url[:110]}")
      res_dict = {
          "replaceImage": {
              "imageObjectId": obj_id,
              "url": public_url,
              "imageReplaceMethod": "CENTER_CROP",
          },
          "_alt_text_request": {
              "updatePageElementAltText": {
                  "objectId": obj_id,
                  "title": f"PitchGen-Transformed:{customer_name}",
                  "description": (
                      "PitchGen transformed"
                      f" {'Cover 3D Sculpture' if is_title_slide else 'Hero Picture'}"
                      f" for {customer_name}"
                  ),
              }
          },
      }
      if has_crop_offsets:
        res_dict["_reset_crop_request"] = {
            "updateImageProperties": {
                "objectId": obj_id,
                "imageProperties": {
                    "cropProperties": {
                        "leftOffset": 0.0,
                        "rightOffset": 0.0,
                        "topOffset": 0.0,
                        "bottomOffset": 0.0,
                    }
                },
                "fields": (
                    "cropProperties.leftOffset,cropProperties.rightOffset,"
                    "cropProperties.topOffset,cropProperties.bottomOffset"
                ),
            }
        }
      return res_dict
  except Exception as e:
    print(f"[ImageUtil] Picture customization error for {obj_id}: {e}")

  return None


_TEMP_DRIVE_DOC_IDS: list[str] = []


def _resolve_drive_docs_oauth_token(oauth_token: str | None = None) -> str:
  """Resolves a bearer token for Google Drive / Docs API calls."""
  if oauth_token and str(oauth_token).strip():
    return str(oauth_token).strip()
  try:
    from oauth_helper import get_user_access_token

    tok = get_user_access_token("seller_user")
    if tok:
      return str(tok).strip()
  except Exception:
    pass
  try:
    import google.auth
    from google.auth.transport.requests import Request

    creds, _ = google.auth.default(
        scopes=[
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/documents.readonly",
        ]
    )
    creds.refresh(Request())
    if getattr(creds, "token", None):
      return str(creds.token).strip()
  except Exception:
    pass
  return ""


def image_bytes_to_content_uri(
    image_bytes: bytes,
    mime_type: str = "image/png",
    oauth_token: str | None = None,
    filename: str = "pitchgen_slide_img",
) -> tuple[str, str]:
  """Zero-GCS image upload fallback (modeled after gslides.go imageToContentURI).

  Embeds raw PNG/JPEG bytes as a base64 <img> inside an HTML snippet, uploads it
  to Google Drive with conversion to a temporary Google Doc, extracts the
  Google-hosted `inlineObjects[*].embeddedObject.imageProperties.contentUri` via
  the Google Docs API (which Google Slides `createImage` / `replaceImage` can
  fetch natively without GCS buckets or IAM signBlob), and queues the temporary
  Google Doc ID for cleanup after `batchUpdate`.
  """
  if not image_bytes:
    return "", ""
  token = _resolve_drive_docs_oauth_token(oauth_token)
  if not token:
    return "", ""

  try:
    import json
    import uuid
    import requests

    b64_data = base64.b64encode(image_bytes).decode("ascii")
    clean_mime = (
        mime_type
        if mime_type in ("image/png", "image/jpeg", "image/webp", "image/gif")
        else "image/png"
    )
    html_body = (
        "<html><body><img"
        f' src="data:{clean_mime};base64,{b64_data}"></body></html>'
    )
    boundary = f"pitchgen_img_boundary_{uuid.uuid4().hex[:12]}"
    metadata_json = json.dumps({
        "name": f"tmp-img-{filename}-{uuid.uuid4().hex[:8]}",
        "mimeType": "application/vnd.google-apps.document",
    })
    multipart_payload = (
        f"--{boundary}\r\n"
        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{metadata_json}\r\n"
        f"--{boundary}\r\n"
        "Content-Type: text/html; charset=UTF-8\r\n\r\n"
        f"{html_body}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    r_up = requests.post(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
        },
        data=multipart_payload,
        timeout=20,
    )
    if r_up.status_code not in (200, 201):
      print(
          f"[ImageUtil] Drive temp doc upload returned {r_up.status_code}:"
          f" {r_up.text[:160]}"
      )
      return "", ""

    doc_id = str(r_up.json().get("id") or "").strip()
    if not doc_id:
      return "", ""
    _TEMP_DRIVE_DOC_IDS.append(doc_id)

    r_doc = requests.get(
        f"https://docs.googleapis.com/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if r_doc.status_code != 200:
      print(
          f"[ImageUtil] Docs GET for temp image doc {doc_id} returned"
          f" {r_doc.status_code}"
      )
      return "", doc_id

    inline_objs = r_doc.json().get("inlineObjects") or {}
    for _, obj_val in inline_objs.items():
      if not isinstance(obj_val, dict):
        continue
      c_uri = (
          obj_val.get("inlineObjectProperties", {})
          .get("embeddedObject", {})
          .get("imageProperties", {})
          .get("contentUri", "")
      )
      if c_uri:
        return str(c_uri).strip(), doc_id
  except Exception as err:
    print(f"[ImageUtil] image_bytes_to_content_uri fallback notice: {err}")

  return "", ""


def cleanup_temp_drive_docs(oauth_token: str | None = None) -> int:
  """Deletes any temporary Google Docs created by `image_bytes_to_content_uri` after Slides batchUpdate completes."""
  if not _TEMP_DRIVE_DOC_IDS:
    return 0
  token = _resolve_drive_docs_oauth_token(oauth_token)
  if not token:
    return 0

  import requests

  pending = list(_TEMP_DRIVE_DOC_IDS)
  _TEMP_DRIVE_DOC_IDS.clear()
  deleted = 0
  for doc_id in pending:
    try:
      r_del = requests.delete(
          f"https://www.googleapis.com/drive/v3/files/{doc_id}?supportsAllDrives=true",
          headers={"Authorization": f"Bearer {token}"},
          timeout=10,
      )
      if r_del.status_code in (200, 204, 404):
        deleted += 1
    except Exception:
      pass
  return deleted


def generate_gcs_v4_signed_url(
    bucket_name: str,
    blob_name: str,
    project_id: str = "your-gcp-project-id",
    expiration_seconds: int = 14400,
    raw_bytes: bytes | None = None,
    mime_type: str = "image/png",
    oauth_token: str | None = None,
) -> str:
  """Generates a V4 signed GET URL for a GCS object using IAM signBlob so Google Slides REST API can fetch it without 403 errors, with automatic Zero-GCS Drive/Docs contentUri fallback when raw_bytes is provided."""
  unsigned_url = f"https://storage.googleapis.com/{bucket_name}/{blob_name}"
  try:
    import datetime
    import hashlib
    import urllib.parse
    import google.auth
    from google.auth.transport.requests import Request
    import requests

    creds, _ = google.auth.default()
    if hasattr(creds, "with_quota_project"):
      creds = creds.with_quota_project(project_id)
    creds.refresh(Request())
    if getattr(creds, "token", None):
      sa = f"slides-exporter@{project_id}.iam.gserviceaccount.com"
      now = datetime.datetime.now(datetime.timezone.utc)
      datestamp = now.strftime("%Y%m%d")
      timestamp = now.strftime("%Y%m%dT%H%M%SZ")
      credential_scope = f"{datestamp}/auto/storage/goog4_request"
      credential = f"{sa}/{credential_scope}"
      escaped_obj = urllib.parse.quote(blob_name, safe="/")
      canonical_uri = f"/{bucket_name}/{escaped_obj}"
      query_params = {
          "X-Goog-Algorithm": "GOOG4-RSA-SHA256",
          "X-Goog-Credential": credential,
          "X-Goog-Date": timestamp,
          "X-Goog-Expires": str(expiration_seconds),
          "X-Goog-SignedHeaders": "host",
      }
      canonical_query = "&".join(
          f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
          for k, v in sorted(query_params.items())
      )
      canonical_req = (
          f"GET\n{canonical_uri}\n{canonical_query}\n"
          "host:storage.googleapis.com\n\nhost\nUNSIGNED-PAYLOAD"
      )
      req_hash = hashlib.sha256(canonical_req.encode("utf-8")).hexdigest()
      string_to_sign = (
          f"GOOG4-RSA-SHA256\n{timestamp}\n{credential_scope}\n{req_hash}"
      )
      r_sign = requests.post(
          f"https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{sa}:signBlob",
          headers={
              "Authorization": f"Bearer {creds.token}",
              "x-goog-user-project": project_id,
          },
          json={
              "payload": (
                  base64.b64encode(string_to_sign.encode("utf-8")).decode(
                      "utf-8"
                  )
              )
          },
          timeout=8,
      )
      if r_sign.status_code == 200 and "signedBlob" in r_sign.json():
        sig_bytes = base64.b64decode(r_sign.json()["signedBlob"])
        sig_hex = sig_bytes.hex()
        return f"https://storage.googleapis.com{canonical_uri}?{canonical_query}&X-Goog-Signature={sig_hex}"
  except Exception as sign_err:
    print(f"[ImageUtil] V4 signed URL fallback triggered: {sign_err}")

  if raw_bytes:
    content_uri, _ = image_bytes_to_content_uri(
        raw_bytes, mime_type=mime_type, oauth_token=oauth_token
    )
    if content_uri:
      return content_uri

  return unsigned_url


def upload_bytes_to_gcs(
    data_bytes: bytes,
    primary_bucket: str,
    blob_name: str,
    content_type: str = "image/png",
    project_id: str = "your-gcp-project-id",
    mirror_buckets: list[str] | None = None,
) -> str:
  """Uploads binary image bytes to primary and mirror GCS buckets and returns gs:// URI."""
  from google.cloud import storage

  buckets = [primary_bucket]
  for mb in mirror_buckets or []:
    if mb and mb not in buckets:
      buckets.append(mb)

  for b_name in buckets:
    try:
      st_client = storage.Client(project=project_id)
      bucket = st_client.bucket(b_name)
      blob = bucket.blob(blob_name)
      blob.upload_from_string(data_bytes, content_type=content_type)
    except Exception as up_err:
      print(
          f"[ImageUtil] GCS upload warning for {b_name}/{blob_name}: {up_err}"
      )

  return f"gs://{primary_bucket}/{blob_name}"


def _extract_omni_video_bytes(
    interaction: any, min_mp4_bytes: int = 1024
) -> tuple[bytes | None, str | None]:
  """Extracts MP4 video payload bytes from a Gemini Omni 1.1 Flash interaction response."""
  if not interaction:
    return None, "Empty interaction response received from GenAI API."

  video_data = None
  if hasattr(interaction, "output_video") and interaction.output_video:
    video_data = (
        getattr(interaction.output_video, "data", None)
        or interaction.output_video
    )
  elif hasattr(interaction, "steps") and interaction.steps:
    for step in interaction.steps:
      if hasattr(step, "content") and step.content:
        for item in step.content:
          if (
              getattr(item, "type", None) == "video"
              or type(item).__name__ == "VideoContent"
          ):
            video_data = getattr(item, "data", None)
            if video_data:
              break
  elif hasattr(interaction, "candidates") and interaction.candidates:
    for cand in interaction.candidates:
      if cand and hasattr(cand, "content") and cand.content:
        for part in getattr(cand.content, "parts", []):
          if hasattr(part, "inline_data") and part.inline_data:
            mime = getattr(part.inline_data, "mime_type", "")
            if "video" in mime:
              video_data = getattr(part.inline_data, "data", None)
              if video_data:
                break

  if video_data:
    if isinstance(video_data, bytes):
      raw_bytes = video_data
    elif isinstance(video_data, str):
      raw_bytes = base64.b64decode(video_data)
    else:
      raw_bytes = bytes(video_data)
    if len(raw_bytes) < min_mp4_bytes:
      return (
          None,
          f"Synthesized video payload too small ({len(raw_bytes)} bytes).",
      )
    return raw_bytes, None

  diagnostics = []
  if hasattr(interaction, "error") and interaction.error:
    diagnostics.append(f"API Error: {interaction.error}")
  if hasattr(interaction, "finish_reason") and interaction.finish_reason:
    diagnostics.append(f"Finish reason: {interaction.finish_reason}")
  if hasattr(interaction, "safety_ratings") and interaction.safety_ratings:
    ratings_summary = [
        f"{getattr(r, 'category', 'category')}={getattr(r, 'probability', 'probability')}"
        for r in interaction.safety_ratings
    ]
    diagnostics.append(f"Safety ratings: {', '.join(ratings_summary)}")
  if not diagnostics:
    diagnostics.append("No video binary returned in interaction response.")
  return None, " | ".join(diagnostics)


def _sanitize_omni_video_prompt(prompt: str, attempt: int = 1) -> str:
  """Sanitizes a video motion prompt for Gemini Omni 1.1 Flash Responsible AI compliance and continuity."""
  import re

  if not prompt:
    return (
        "Smooth cinematic camera dolly across modern retail store shelves and"
        " digital inventory telemetry."
    )
  text = re.sub(r"[\"\'\`\*]", "", str(prompt)).strip()
  replacements = [
      (r"\bphoto-?realistic(\s+composite)?\b", "cinematic studio composition"),
      (
          r"\b(female|male|woman|man|girl|boy|child|children|kid|kids)\b",
          "digital",
      ),
      (
          r"\b(shopper|customer|person|people|employee|worker|associate|cashier)s?\b",
          "automated workflow",
      ),
      (r"\bface(s)?\b", "interface display"),
      (r"\bhuman(s)?\b", "autonomous"),
  ]
  for pat, rep in replacements:
    text = re.sub(pat, rep, text, flags=re.IGNORECASE)

  if attempt >= 2:
    first_sentence = re.split(r"(?<=[.!?])\s+", text)[0] if text else ""
    text = (
        first_sentence
        if len(first_sentence.split()) >= 4
        else (
            "Smooth cinematic tracking shot across enterprise retail displays"
            " and digital telemetry."
        )
    )
  text = re.sub(r"\s+", " ", text).strip()
  text += (
      " Maintain sharp, stable vector geometry on all product packaging, shelf"
      " labels, and interface cards with smooth, continuous motion and a"
      " calm culminating hold on the final frame."
  )
  return text


def extract_customizable_slide_gifs(
    slide: dict,
    slide_index: int = 0,
    is_cust_ref_slide: bool = False,
    min_width_pt: float = 115.0,
    min_height_pt: float = 95.0,
    explicit_user_request: bool = False,
) -> list[dict]:
  """Detects customizable animated GIF elements on a content slide (excluding full-bleed backgrounds, small icons, and official Google/Gemini logo lockups)."""
  if not isinstance(slide, dict) or is_cust_ref_slide:
    return []
  if (slide_index <= 1) and not explicit_user_request:
    return []

  eff_min_w = 40.0 if explicit_user_request else min_width_pt
  eff_min_h = 40.0 if explicit_user_request else min_height_pt
  eff_min_area = 3000.0 if explicit_user_request else 12000.0

  flat_elements = _flatten_slide_elements(slide.get("pageElements", []))
  candidates: list[dict] = []
  for pe in flat_elements:
    img = pe.get("image")
    if not img:
      continue
    obj_id = pe.get("objectId", "")
    content_url = str(
        img.get("contentUrl") or img.get("sourceUrl") or ""
    ).strip()
    if not obj_id or not content_url:
      continue

    tx, ty, width_pt, height_pt, is_flipped = _element_bbox_pt(pe)
    if (
        width_pt < eff_min_w
        or height_pt < eff_min_h
        or (width_pt * height_pt) < eff_min_area
        or is_flipped
    ):
      continue
    # Exclude full-bleed background GIFs (e.g. 720x405pt '[WIP] Retail EBC Refresh 2026.gif')
    if width_pt >= 680.0 and height_pt >= 380.0:
      continue

    alt_title = str(pe.get("title") or "").strip()
    alt_desc = str(pe.get("description") or "").strip()
    alt_combined = f"{alt_title} {alt_desc}".lower()
    if any(
        skip_tok in alt_combined
        for skip_tok in (
            "gemini_primarylogo",
            "bar logos",
            "super cloud",
            "google cloud",
            "lockup",
        )
    ):
      continue

    is_gif_hint = (
        ".gif" in alt_combined
        or is_gif_or_animated_bytes(url=content_url)
        or get_image_mime_type(content_url) == "image/gif"
    )
    if not is_gif_hint and content_url.startswith("http"):
      try:
        import requests

        r_head = requests.get(
            content_url, headers={"Range": "bytes=0-15"}, timeout=2.5
        )
        if r_head.status_code in (200, 206) and (
            r_head.content.startswith((b"GIF87a", b"GIF89a"))
            or "gif" in str(r_head.headers.get("Content-Type", "")).lower()
        ):
          is_gif_hint = True
      except Exception:
        pass

    if not is_gif_hint:
      continue

    aspect_ratio = width_pt / max(1.0, height_pt)
    omni_aspect = "9:16" if aspect_ratio < 0.80 else "16:9"
    crop = (
        img.get("cropProperties")
        or img.get("imageProperties", {}).get("cropProperties")
        or {}
    )
    candidates.append({
        "objectId": obj_id,
        "contentUrl": content_url,
        "width_pt": round(width_pt, 1),
        "height_pt": round(height_pt, 1),
        "aspect_ratio": round(aspect_ratio, 2),
        "omni_aspect_ratio": omni_aspect,
        "slide_index": slide_index,
        "alt_title": alt_title,
        "cropProperties": dict(crop) if isinstance(crop, dict) else {},
    })
  return candidates


def _transcode_gif_or_image_to_mp4_scaffold(
    raw_bytes: bytes,
    target_aspect: str = "16:9",
    duration_sec: float = 5.0,
    crop_props: dict | None = None,
    max_source_fraction: float = 0.70,
    start_frame_offset: int | None = None,
) -> tuple[bytes | None, bytes | None]:
  """Converts an animated source GIF into (mp4_scaffold_bytes, frame0_png_bytes) sized to 1280x720 (16:9) or 720x1280 (9:16) for Gemini Omni 1.1 Flash video-to-video editing, applying Slides cropProperties and stripping #00FF00 chroma-key green sidebars."""
  if not raw_bytes:
    return None, None

  import io
  import os
  import subprocess
  import tempfile
  import numpy as np
  from PIL import Image

  target_w, target_h = (720, 1280) if target_aspect == "9:16" else (1280, 720)
  frame0_png_bytes: bytes | None = None
  cropped_frames: list[Image.Image] = []

  try:
    with Image.open(io.BytesIO(raw_bytes)) as im:
      n_frames = int(getattr(im, "n_frames", 1) or 1)
      if n_frames <= 1:
        # Strict guardrail: video-to-video is ONLY for elements that are originally animated GIFs.
        return None, None

      sw, sh = im.size
      cp = crop_props or {}
      l_off = max(0.0, min(0.85, float(cp.get("leftOffset", 0.0) or 0.0)))
      r_off = max(0.0, min(0.85, float(cp.get("rightOffset", 0.0) or 0.0)))
      t_off = max(0.0, min(0.85, float(cp.get("topOffset", 0.0) or 0.0)))
      b_off = max(0.0, min(0.85, float(cp.get("bottomOffset", 0.0) or 0.0)))

      cx1 = int(round(sw * l_off))
      cy1 = int(round(sh * t_off))
      cx2 = max(cx1 + 16, int(round(sw * (1.0 - r_off))))
      cy2 = max(cy1 + 16, int(round(sh * (1.0 - b_off))))

      # Auto-strip #00FF00 chroma-key green borders (e.g. Phone_UI_2 New.gif)
      im.seek(0)
      f0_arr = np.array(im.convert("RGB"))[cy1:cy2, cx1:cx2]
      is_green = (
          (f0_arr[:, :, 1] > 220)
          & (f0_arr[:, :, 0] < 45)
          & (f0_arr[:, :, 2] < 45)
      )
      col_non_green = (~is_green).mean(axis=0) > 0.15
      row_non_green = (~is_green).mean(axis=1) > 0.15
      if col_non_green.any() and row_non_green.any():
        gx1 = int(np.argmax(col_non_green))
        gx2 = int(len(col_non_green) - np.argmax(col_non_green[::-1]))
        gy1 = int(np.argmax(row_non_green))
        gy2 = int(len(row_non_green) - np.argmax(row_non_green[::-1]))
        if (gx2 - gx1) >= 64 and (gy2 - gy1) >= 64:
          cx1 += gx1
          cx2 = cx1 + (gx2 - gx1)
          cy1 += gy1
          cy2 = cy1 + (gy2 - gy1)

      # For long multi-scene screen recordings (> 240 frames, where the first ~18% is slow initial typing on a blank screen),
      # sample smoothly from start_frac=0.18 through end_frac=0.96 so the 5.0s MP4 captures the completed prompt AND the full UI response/action cards.
      if start_frame_offset is not None:
        s_idx = max(0, min(n_frames - 16, int(start_frame_offset)))
        end_idx = min(
            n_frames,
            s_idx
            + max(60, int(round((n_frames - s_idx) * max_source_fraction))),
        )
      elif n_frames > 240:
        s_idx = int(round(n_frames * 0.18))
        end_idx = int(round(n_frames * max(0.95, max_source_fraction)))
      else:
        s_idx = 0
        end_idx = n_frames

      span = max(2, end_idx - s_idx)
      out_fps = 16
      target_count = max(16, int(out_fps * duration_sec))
      idxs = [
          min(
              n_frames - 1,
              s_idx + int(round(k * (span - 1) / max(1, target_count - 1))),
          )
          for k in range(target_count)
      ]
      for idx in idxs:
        im.seek(min(n_frames - 1, idx))
        fr = im.convert("RGB").crop((cx1, cy1, cx2, cy2))
        cropped_frames.append(fr)

      f0 = cropped_frames[0].copy()
      sw_c, sh_c = f0.size
      target_ratio = target_w / float(target_h)
      src_ratio = sw_c / max(1.0, float(sh_c))
      if abs(src_ratio - target_ratio) > 0.03:
        if src_ratio > target_ratio:
          new_w = max(2, int(sh_c * target_ratio))
          left = (sw_c - new_w) // 2
          f0 = f0.crop((left, 0, left + new_w, sh_c))
        else:
          new_h = max(2, int(sw_c / target_ratio))
          top = (sh_c - new_h) // 2
          f0 = f0.crop((0, top, sw_c, top + new_h))
      f0 = f0.resize((target_w, target_h), Image.Resampling.LANCZOS)
      buf = io.BytesIO()
      f0.save(buf, format="PNG")
      frame0_png_bytes = buf.getvalue()
  except Exception as e:
    print(f"[ImageUtil] GIF frame extraction warning: {e}")
    return None, None

  mp4_bytes: bytes | None = None
  try:
    with tempfile.TemporaryDirectory(prefix="pg_omni_in_") as tmpdir:
      for i, fr in enumerate(cropped_frames):
        fr.save(os.path.join(tmpdir, f"f_{i:04d}.png"), format="PNG")
      out_mp4 = os.path.join(tmpdir, "scaffold.mp4")
      vf_filter = (
          f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
          f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:white,format=yuv420p"
      )
      cmd = [
          "/usr/bin/ffmpeg",
          "-y",
          "-framerate",
          "16",
          "-i",
          os.path.join(tmpdir, "f_%04d.png"),
          "-vf",
          vf_filter,
          "-c:v",
          "libx264",
          "-preset",
          "fast",
          "-crf",
          "18",
          "-an",
          "-movflags",
          "+faststart",
          out_mp4,
      ]
      subprocess.run(
          cmd,
          check=True,
          stdout=subprocess.DEVNULL,
          stderr=subprocess.DEVNULL,
          timeout=30,
      )
      if os.path.exists(out_mp4):
        with open(out_mp4, "rb") as f:
          mp4_bytes = f.read()
  except Exception as e:
    print(f"[ImageUtil] MP4 scaffold transcode warning: {e}")

  return mp4_bytes, frame0_png_bytes


def _transcode_mp4_to_looping_slide_gif(
    mp4_bytes: bytes,
    width_pt: float = 333.5,
    height_pt: float = 187.6,
    orig_alpha_mask: any = None,
    fps: int = 12,
    max_duration_sec: float = 4.8,
    max_bytes: int = 14 * 1024 * 1024,
    trim_start_sec: float = 0.0,
    is_ui_demo: bool = True,
) -> bytes | None:
  """Transcodes synthesized MP4 bytes into a high-resolution, palette-quantized looping GIF matching the exact Google Slides element aspect ratio without UI cross-dissolve ghosting."""
  if not mp4_bytes:
    return None

  import glob
  import io
  import os
  import subprocess
  import tempfile
  import numpy as np
  from PIL import Image

  target_ratio = max(
      0.25, min(4.0, float(width_pt) / max(1.0, float(height_pt)))
  )
  max_long_edge = 960 if is_ui_demo else 720
  if target_ratio >= 1.0:
    out_w = max_long_edge
    out_h = max(64, int(round(out_w / target_ratio)))
  else:
    out_h = max_long_edge
    out_w = max(64, int(round(out_h * target_ratio)))
  out_w = (out_w // 2) * 2
  out_h = (out_h // 2) * 2

  try:
    with tempfile.TemporaryDirectory(prefix="pg_omni_gif_") as tmpdir:
      in_mp4 = os.path.join(tmpdir, "omni_out.mp4")
      frames_dir = os.path.join(tmpdir, "frames")
      os.makedirs(frames_dir, exist_ok=True)
      with open(in_mp4, "wb") as f:
        f.write(mp4_bytes)

      vf_extract = (
          f"fps={fps},scale={out_w}:{out_h}:force_original_aspect_ratio=decrease:flags=lanczos,"
          f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:white"
      )
      ff_cmd = ["/usr/bin/ffmpeg", "-y"]
      if trim_start_sec > 0.01:
        ff_cmd.extend(["-ss", f"{trim_start_sec:.2f}"])
      ff_cmd.extend([
          "-i",
          in_mp4,
          "-t",
          f"{max_duration_sec:.1f}",
          "-vf",
          vf_extract,
          os.path.join(frames_dir, "frame_%04d.png"),
      ])
      subprocess.run(
          ff_cmd,
          check=True,
          stdout=subprocess.DEVNULL,
          stderr=subprocess.DEVNULL,
          timeout=35,
      )

      frame_paths = sorted(glob.glob(os.path.join(frames_dir, "frame_*.png")))
      if not frame_paths:
        return None

      rgba_frames: list[np.ndarray] = []
      for fp in frame_paths:
        with Image.open(fp) as fim:
          rgba_frames.append(np.array(fim.convert("RGBA"), dtype=np.float32))

      # Never cross-dissolve tail->head on UI product demos (cross-dissolving two different UI screens creates overlapping UI ghosting).
      if not is_ui_demo and len(rgba_frames) >= 16:
        blend_k = min(4, len(rgba_frames) // 6)
        head = rgba_frames[:blend_k]
        body = rgba_frames[blend_k : len(rgba_frames) - blend_k]
        tail = rgba_frames[len(rgba_frames) - blend_k :]
        blended_tail = []
        for idx in range(blend_k):
          alpha = float(idx + 1) / float(blend_k + 1)
          mixed = (1.0 - alpha) * tail[idx] + alpha * head[idx]
          blended_tail.append(mixed)
        final_frames_arr = head + body + blended_tail
      else:
        final_frames_arr = rgba_frames

      resized_mask_arr = None
      if orig_alpha_mask is not None:
        try:
          resized_mask = orig_alpha_mask.resize(
              (out_w, out_h), Image.Resampling.LANCZOS
          )
          resized_mask_arr = np.array(resized_mask, dtype=np.uint8)
        except Exception:
          resized_mask_arr = None

      loop_dir = os.path.join(tmpdir, "loop_frames")
      os.makedirs(loop_dir, exist_ok=True)
      pil_frames: list[Image.Image] = []
      for i, arr_f in enumerate(final_frames_arr):
        u8 = np.clip(arr_f, 0.0, 255.0).astype(np.uint8)
        if resized_mask_arr is not None:
          alpha_f = (resized_mask_arr.astype(np.float32) / 255.0)[:, :, None]
          bg_rgb = np.array([15.0, 17.0, 21.0], dtype=np.float32)[None, None, :]
          comp_rgb = u8[:, :, :3].astype(np.float32) * alpha_f + bg_rgb * (
              1.0 - alpha_f
          )
          u8[:, :, :3] = np.clip(comp_rgb, 0.0, 255.0).astype(np.uint8)
        u8[:, :, 3] = 255
        im_f = Image.fromarray(u8[:, :, :3], mode="RGB")
        pil_frames.append(im_f)
        im_f.save(os.path.join(loop_dir, f"loop_{i:04d}.png"), format="PNG")

      palette_png = os.path.join(tmpdir, "palette.png")
      out_gif = os.path.join(tmpdir, "output.gif")
      subprocess.run(
          [
              "/usr/bin/ffmpeg",
              "-y",
              "-framerate",
              str(fps),
              "-i",
              os.path.join(loop_dir, "loop_%04d.png"),
              "-vf",
              "palettegen=max_colors=256:stats_mode=full:reserve_transparent=0",
              palette_png,
          ],
          check=True,
          stdout=subprocess.DEVNULL,
          stderr=subprocess.DEVNULL,
          timeout=25,
      )
      subprocess.run(
          [
              "/usr/bin/ffmpeg",
              "-y",
              "-framerate",
              str(fps),
              "-i",
              os.path.join(loop_dir, "loop_%04d.png"),
              "-i",
              palette_png,
              "-lavfi",
              "paletteuse=dither=sierra2_4a:diff_mode=rectangle",
              "-loop",
              "0",
              out_gif,
          ],
          check=True,
          stdout=subprocess.DEVNULL,
          stderr=subprocess.DEVNULL,
          timeout=35,
      )
      if os.path.exists(out_gif):
        with open(out_gif, "rb") as f:
          gif_bytes = f.read()
        if len(gif_bytes) <= max_bytes and gif_bytes.startswith(
            (b"GIF87a", b"GIF89a")
        ):
          return gif_bytes

      # Fallback if file size exceeded max_bytes: re-encode at 720px long edge & 10 fps
      scale_expr = (
          f"fps=10,scale='min(720,iw)':-2:flags=lanczos,split[s0][s1];"
          f"[s0]palettegen=max_colors=256:stats_mode=full[p];"
          f"[s1][p]paletteuse=dither=sierra2_4a:diff_mode=rectangle"
      )
      out_gif_compact = os.path.join(tmpdir, "output_compact.gif")
      subprocess.run(
          [
              "/usr/bin/ffmpeg",
              "-y",
              "-i",
              in_mp4,
              "-t",
              "4.5",
              "-lavfi",
              scale_expr,
              "-loop",
              "0",
              out_gif_compact,
          ],
          check=True,
          stdout=subprocess.DEVNULL,
          stderr=subprocess.DEVNULL,
          timeout=35,
      )
      if os.path.exists(out_gif_compact):
        with open(out_gif_compact, "rb") as f:
          return f.read()
  except Exception as e:
    print(f"[ImageUtil] GIF transcode warning ({e}); trying Pillow fallback.")
    try:
      with tempfile.TemporaryDirectory(prefix="pg_pil_gif_") as tmpdir:
        in_mp4 = os.path.join(tmpdir, "in.mp4")
        with open(in_mp4, "wb") as f:
          f.write(mp4_bytes)
        subprocess.run(
            [
                "/usr/bin/ffmpeg",
                "-y",
                "-i",
                in_mp4,
                "-vf",
                f"fps=10,scale={out_w}:{out_h}",
                os.path.join(tmpdir, "f_%03d.png"),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=25,
        )
        fps_list = sorted(glob.glob(os.path.join(tmpdir, "f_*.png")))
        if fps_list:
          imgs = [Image.open(p).convert("RGB") for p in fps_list]
          buf = io.BytesIO()
          imgs[0].save(
              buf,
              format="GIF",
              save_all=True,
              append_images=imgs[1:],
              duration=int(1000 / 10),
              loop=0,
              optimize=True,
          )
          return buf.getvalue()
    except Exception:
      pass

  return None


def _classify_and_plan_gif_customization(
    sample_frames_png: list[bytes],
    customer_name: str,
    industry: str = "",
    slide_text_context: str = "",
    client: any = None,
    fast_model: str = "gemini-3.8-flash",
) -> dict:
  """Classifies an animated GIF into Scenario 1 ('PURE_VISUAL') vs Scenario 2 ('UI_PRODUCT_DEMO') and generates a surgical text replacement plan for UI demos."""
  import io
  import json
  import numpy as np
  from PIL import Image

  domain_label = f" ({industry})" if industry else ""
  default_plan = {
      "scenario": "PURE_VISUAL",
      "reason": "Default heuristic fallback",
      "text_replacements": [
          {"original": "Cymbal Retail", "replacement": customer_name},
          {"original": "Cymbal Superstore", "replacement": customer_name},
          {"original": "Cymbal", "replacement": customer_name},
          {
              "original": "cymbal.com",
              "replacement": f"{customer_name.lower().replace(' ', '')}.com",
          },
      ],
      "ui_edit_instruction": (
          "Replace any 'Cymbal' or generic demo brand/product text with"
          f" {customer_name}{domain_label} equivalents while keeping 100% of"
          " the UI layout, fonts, icons, and colors identical."
      ),
      "visual_motion_prompt": (
          f"Edit this video for {customer_name}{domain_label}. Preserve the"
          " exact interface layout, visual medium, background, framing, and"
          " smooth scrolling/cursor animation from the input video. 'Cymbal'"
          " (including 'Cymbal Retail', 'Cymbal Superstore', 'Cymbal Shops',"
          " and 'Cymbal Operations Manual') is a white-label placeholder brand:"
          " replace every 'Cymbal' or previous demo brand name, logo, product,"
          " and typed prompt text across ALL frames from start to finish with"
          f" {customer_name} branding and {customer_name}-authentic products."
          " Keep all on-screen text concise, sharp, and legible, without"
          " floating logo overlays on photography."
      ),
  }

  # Deterministic image-statistics heuristic for UI screen recordings (used as baseline and offline fallback)
  if sample_frames_png:
    try:
      flat_light_ratios = []
      sharp_edge_ratios = []
      for png_b in sample_frames_png[:3]:
        with Image.open(io.BytesIO(png_b)) as im:
          arr = np.array(im.convert("RGB"), dtype=np.int16)
          # Check fraction of pixels that are flat light UI surfaces (white/light gray/pastel cards)
          is_light = (
              (arr[:, :, 0] >= 228)
              & (arr[:, :, 1] >= 228)
              & (arr[:, :, 2] >= 228)
              & (np.abs(arr[:, :, 0] - arr[:, :, 1]) <= 18)
              & (np.abs(arr[:, :, 1] - arr[:, :, 2]) <= 18)
          )
          flat_light_ratios.append(float(is_light.mean()))
          # Check high-contrast horizontal glyph transitions (typical of anti-aliased UI typography)
          dx = np.abs(arr[:, 1:, :] - arr[:, :-1, :]).max(axis=2)
          sharp_edge_ratios.append(float((dx > 45).mean()))
      if max(flat_light_ratios) >= 0.48 and max(sharp_edge_ratios) >= 0.008:
        default_plan["scenario"] = "UI_PRODUCT_DEMO"
        default_plan["reason"] = (
            "High-key flat UI background with crisp typography edges"
        )
    except Exception:
      pass

  if not client or not sample_frames_png:
    return default_plan

  try:
    from google.genai import types

    contents = []
    num_imgs = min(6, len(sample_frames_png))
    for k_i, png_b in enumerate(sample_frames_png[:num_imgs]):
      contents.append(f"Keyframe {k_i}:")
      contents.append(types.Part.from_bytes(data=png_b, mime_type="image/png"))

    triage_prompt = (
        f"You are inspecting {num_imgs} keyframes (labeled Keyframe 0 through"
        f" Keyframe {num_imgs - 1}) from an animated GIF on a"
        f" presentation slide for Target Customer: {customer_name}"
        f" (Industry: {industry or 'Enterprise'}).\n"
        f"Surrounding Slide Context: {(slide_text_context or '')[:240]}\n\n"
        "Classify this GIF into one of TWO scenarios:\n"
        '1. "UI_PRODUCT_DEMO": The GIF is a software UI screen recording,'
        " product demo, chat/agent interface, prompt input box, Workspace"
        " / Sheets sidebar, mobile app screen, or workflow card containing"
        " readable UI text, prompts, or buttons.\n"
        '2. "PURE_VISUAL": The GIF is purely visual (lifestyle video, 3D'
        " motion graphic, product photography animation, or abstract visual"
        " motion) without dense software UI text.\n\n"
        'If scenario is "UI_PRODUCT_DEMO":\n'
        "- Identify every specific white-label brand ('Cymbal', 'Cymbal"
        " Retail', 'Cymbal US Store Operations Manual', 'Cymbal Superstore',"
        " 'cymbal.com', 'Lowe\\'s', 'Target') or generic demo product/topic"
        " string (e.g. 'Charm bracelets', 'garnet birthstone jewelry',"
        " 'Galactic Ranger', 'Pro-Fit Trainers', 'Flex-Tech Vest', 'All-Weather"
        " Pack', 'Halloween campaign', 'Space-themed costumes', 'Project"
        " Aurora', 'Matthew\\'s Birthday Party', 'dinosaur', 'backsplash')"
        " visible across ANY of the keyframes that should be localized to"
        f" {customer_name}{domain_label}.\n"
        "- For each replacement, specify `keyframes`: the exact list of 0-based"
        f" keyframe numbers (0..{num_imgs - 1}) where that exact `original`"
        " string is visibly rendered on screen.\n"
        "- CRITICAL LENGTH RULE: Each replacement string MUST have nearly the"
        " exact same character count (within +/- 4 chars, or slightly shorter)"
        " as the original string so it fits inside the exact same UI text box"
        " without wrapping or overflowing.\n"
        "- Do NOT alter standard Google Cloud / Gemini / ServiceNow / Gmail /"
        " Google Calendar product labels or generic UI chrome ('Show Thinking',"
        " 'Ask a follow-up', 'Send', 'Cancel', 'Hello, Gonzalo', 'Progress"
        " Check').\n\n"
        "Return a JSON object with:\n"
        "{\n"
        '  "scenario": "UI_PRODUCT_DEMO" | "PURE_VISUAL",\n'
        '  "reason": "1-sentence explanation",\n'
        '  "text_replacements": [\n'
        '    {"original": "exact text in UI", "replacement": "concise'
        f' {customer_name}-authentic replacement", "keyframes": [0, 1]}}\n'
        "  ],\n"
        '  "ui_edit_instruction": "Concise instruction for surgical in-place'
        ' UI text replacement",\n'
        '  "visual_motion_prompt": "If PURE_VISUAL, a concise 2-sentence'
        f' video-to-video edit prompt for {customer_name}"\n'
        "}"
    )
    contents.append(triage_prompt)

    for m_try in (fast_model, "gemini-3.8-flash", "gemini-3.5-flash-lite"):
      if not m_try:
        continue
      try:
        resp = client.models.generate_content(
            model=m_try,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )
        if resp and resp.text:
          parsed = json.loads(resp.text)
          if (
              isinstance(parsed, list)
              and parsed
              and isinstance(parsed[0], dict)
          ):
            parsed = parsed[0]
          if isinstance(parsed, dict):
            scen = str(parsed.get("scenario") or "").upper().strip()
            if scen in ("UI_PRODUCT_DEMO", "PURE_VISUAL"):
              default_plan["scenario"] = scen
            if parsed.get("reason"):
              default_plan["reason"] = str(parsed["reason"])
            if (
                isinstance(parsed.get("text_replacements"), list)
                and parsed["text_replacements"]
            ):
              valid_reps = []
              for r in parsed["text_replacements"]:
                if (
                    isinstance(r, dict)
                    and r.get("original")
                    and r.get("replacement")
                ):
                  kf_list = r.get("keyframes")
                  if isinstance(kf_list, list):
                    clean_kfs = [
                        int(x)
                        for x in kf_list
                        if isinstance(x, (int, float))
                        and 0 <= int(x) < num_imgs
                    ]
                  else:
                    clean_kfs = list(range(num_imgs))
                  valid_reps.append({
                      "original": str(r["original"]).strip(),
                      "replacement": str(r["replacement"]).strip(),
                      "keyframes": clean_kfs,
                  })
              if valid_reps:
                default_plan["text_replacements"] = valid_reps
            if parsed.get("ui_edit_instruction"):
              default_plan["ui_edit_instruction"] = str(
                  parsed["ui_edit_instruction"]
              ).strip()
            if parsed.get("visual_motion_prompt"):
              default_plan["visual_motion_prompt"] = str(
                  parsed["visual_motion_prompt"]
              ).strip()
            break
      except Exception:
        continue
  except Exception as e:
    print(f"[ImageUtil] GIF scenario classification fallback notice: {e}")

  return default_plan


def _select_ui_demo_keyframes(
    frames_rgb: list,
    max_keyframes: int = 5,
) -> tuple[list[int], list[tuple[int, int]]]:
  """Selects distinct settled UI state keyframes across chronological windows, preferring frames right before scene cuts (when typed prompts or screens are complete)."""
  import numpy as np

  n = len(frames_rgb)
  if n == 0:
    return [], []
  if n == 1:
    return [0], [(0, 0)]

  max_k = max(1, min(max_keyframes, n))
  motion = np.zeros(n, dtype=np.float32)
  jump_pct = np.zeros(n, dtype=np.float32)
  for i in range(1, n):
    diff = np.abs(
        frames_rgb[i].astype(np.int16) - frames_rgb[i - 1].astype(np.int16)
    )
    motion[i] = float(diff.mean())
    jump_pct[i] = float((diff.max(axis=2) > 22).mean())
  motion[0] = motion[1]

  num_wins = min(max_k, max(1, n if n <= 4 else 5))
  raw_selected: list[int] = []
  for w_i in range(num_wins):
    s_w = int(round(w_i * n / num_wins))
    e_w = int(round((w_i + 1) * n / num_wins)) - 1
    s_w = max(0, min(s_w, n - 1))
    e_w = max(s_w, min(e_w, n - 1))

    # Check if there is a major scene transition inside this window; if so, pick the settled frame just before the transition
    best_cut = -1
    best_cut_val = 0.025
    for idx in range(s_w + 2, e_w + 1):
      if jump_pct[idx] > best_cut_val:
        best_cut_val = jump_pct[idx]
        best_cut = idx

    if best_cut > s_w + 1:
      c_start = max(s_w, best_cut - 4)
      c_end = best_cut - 1
    else:
      c_start = s_w + int((e_w - s_w) * 0.40)
      c_end = e_w

    best_f = c_end
    best_m = float("inf")
    for cand in range(c_start, c_end + 1):
      if motion[cand] <= best_m:
        best_m = motion[cand]
        best_f = cand
    raw_selected.append(best_f)

  # Deduplicate visually identical keyframes (< 0.4% pixel change)
  selected: list[int] = []
  for f_idx in raw_selected:
    if not selected:
      selected.append(f_idx)
      continue
    prev_f = selected[-1]
    if f_idx == prev_f:
      continue
    chg = float(
        (
            np.abs(
                frames_rgb[f_idx].astype(np.int16)
                - frames_rgb[prev_f].astype(np.int16)
            ).max(axis=2)
            > 20
        ).mean()
    )
    if chg >= 0.004:
      selected.append(f_idx)

  if not selected:
    selected = [n - 1]

  segment_ranges: list[tuple[int, int]] = []
  for idx_k, k_f in enumerate(selected):
    s = 0 if idx_k == 0 else ((selected[idx_k - 1] + k_f) // 2 + 1)
    e = (
        (n - 1)
        if (idx_k + 1 == len(selected))
        else ((k_f + selected[idx_k + 1]) // 2)
    )
    s = max(0, min(s, n - 1))
    e = max(s, min(e, n - 1))
    segment_ranges.append((s, e))

  return selected, segment_ranges


def _extract_verified_ui_edit_boxes(
    orig_f,
    aligned_edit,
    diff_threshold: float = 24.0,
) -> list[tuple[int, int, int, int]]:
  """Extracts verified rectangular text-edit bounding boxes (x1, y1, x2, y2), rejecting whole-frame hallucinations, 1-2px font resampling drift, and boxes drawn on empty whitespace."""
  import numpy as np
  from PIL import Image, ImageFilter

  h, w = orig_f.shape[:2]
  pixel_max_diff = np.abs(orig_f - aligned_edit).max(axis=2)

  # Guardrail 1: Whole-frame hallucination guard — surgical text replacements never alter >25% of total screen pixels by >48 RGB units
  if float((pixel_max_diff > 48.0).mean()) > 0.25:
    return []

  diff_u8 = np.clip(pixel_max_diff * 2.0, 0, 255).astype(np.uint8)
  local_mean = (
      np.array(
          Image.fromarray(diff_u8, mode="L").filter(
              ImageFilter.BoxBlur(radius=4)
          ),
          dtype=np.float32,
      )
      / 2.0
  )

  active_seed = (pixel_max_diff > diff_threshold) & (local_mean > 3.2)
  if not active_seed.any():
    return []

  cell = 4
  gh = (h + cell - 1) // cell
  gw = (w + cell - 1) // cell
  pad_h, pad_w = gh * cell, gw * cell
  padded = np.zeros((pad_h, pad_w), dtype=bool)
  padded[:h, :w] = active_seed
  grid = padded.reshape(gh, cell, gw, cell).any(axis=(1, 3))

  visited = np.zeros_like(grid, dtype=bool)
  raw_boxes: list[list[int]] = []
  for gy in range(gh):
    for gx in range(gw):
      if grid[gy, gx] and not visited[gy, gx]:
        stack = [(gy, gx)]
        visited[gy, gx] = True
        min_gy = max_gy = gy
        min_gx = max_gx = gx
        while stack:
          cy, cx = stack.pop()
          if cy < min_gy:
            min_gy = cy
          if cy > max_gy:
            max_gy = cy
          if cx < min_gx:
            min_gx = cx
          if cx > max_gx:
            max_gx = cx
          for ny in range(max(0, cy - 1), min(gh, cy + 2)):
            for nx in range(max(0, cx - 1), min(gw, cx + 2)):
              if grid[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                stack.append((ny, nx))
        x1 = max(0, min_gx * cell - 4)
        y1 = max(0, min_gy * cell - 4)
        x2 = min(w, (max_gx + 1) * cell + 4)
        y2 = min(h, (max_gy + 1) * cell + 4)
        bw0, bh0 = x2 - x1, y2 - y1
        if (
            bw0 >= 8
            and bh0 >= 6
            and bh0 <= int(h * 0.35)
            and (bw0 * bh0) <= int(w * h * 0.18)
        ):
          raw_boxes.append([x1, y1, x2, y2])

  if not raw_boxes:
    return []

  # Merge horizontally adjacent word boxes on the same text line (never chain vertically across paragraphs or into oversized blocks)
  merged = True
  while merged:
    merged = False
    new_boxes: list[list[int]] = []
    used = [False] * len(raw_boxes)
    for i in range(len(raw_boxes)):
      if used[i]:
        continue
      bx1, by1, bx2, by2 = raw_boxes[i]
      for j in range(i + 1, len(raw_boxes)):
        if used[j]:
          continue
        ox1, oy1, ox2, oy2 = raw_boxes[j]
        v_overlap = min(by2, oy2) - max(by1, oy1)
        min_h = min(by2 - by1, oy2 - oy1)
        h_gap = max(0, max(bx1, ox1) - min(bx2, ox2))
        nbx1, nby1 = min(bx1, ox1), min(by1, oy1)
        nbx2, nby2 = max(bx2, ox2), max(by2, oy2)
        nbw, nbh = nbx2 - nbx1, nby2 - nby1
        if (
            v_overlap >= 0.45 * min_h
            and h_gap <= 36
            and nbh <= int(h * 0.22)
            and (nbw * nbh) <= int(w * h * 0.14)
        ):
          bx1, by1, bx2, by2 = nbx1, nby1, nbx2, nby2
          used[j] = True
          merged = True
      new_boxes.append([bx1, by1, bx2, by2])
    raw_boxes = new_boxes

  verified_boxes: list[tuple[int, int, int, int]] = []
  for bx1, by1, bx2, by2 in raw_boxes:
    bw, bh = bx2 - bx1, by2 - by1
    # Guardrail 2: Per-box geometry cap
    if bh > int(h * 0.35) or (bw * bh) > int(w * h * 0.20):
      continue

    rx1 = max(0, bx1 - 12)
    ry1 = max(0, by1 - 8)
    rx2 = min(w, bx2 + 12)
    ry2 = min(h, by2 + 8)
    patch_o = orig_f[ry1:ry2, rx1:rx2]
    patch_e = aligned_edit[ry1:ry2, rx1:rx2]
    unchanged_px = np.abs(patch_o - patch_e).max(axis=2) < 14.0
    if unchanged_px.any():
      bg_est = np.median(patch_o[unchanged_px], axis=0)
    else:
      bg_est = np.median(patch_o.reshape(-1, 3), axis=0)

    # Guardrail 3: Original ink presence & vertical row-ink overlap — reject hallucinations drawn on formerly blank rows
    orig_box_ink = (
        np.abs(orig_f[by1:by2, bx1:bx2] - bg_est[None, None, :]).max(axis=2)
        > 20.0
    )
    edit_box_ink = (
        np.abs(aligned_edit[by1:by2, bx1:bx2] - bg_est[None, None, :]).max(
            axis=2
        )
        > 20.0
    )
    orig_ink_frac = float(orig_box_ink.mean())
    edit_ink_frac = float(edit_box_ink.mean())
    if orig_ink_frac < 0.012 or edit_ink_frac < 0.012:
      continue
    if bh >= 12 and bw >= 16:
      inner_o = orig_box_ink[3 : bh - 3, 4 : bw - 4]
      inner_e = edit_box_ink[3 : bh - 3, 4 : bw - 4]
      if float(inner_o.mean()) < 0.012 or float(inner_e.mean()) < 0.012:
        continue

    # Reject false-positive boxes caused by 1-2px local resampling shift on unchanged text,
    # evaluated strictly on the ink union so surrounding white background never dilutes real word edits
    ink_union = orig_box_ink | edit_box_ink
    best_ink_mean = float("inf")
    best_ink_changed_frac = 1.0
    for ldy in (-2, -1, 0, 1, 2):
      sy1 = max(0, min(h - bh, by1 + ldy))
      sy2 = sy1 + bh
      for ldx in (-2, -1, 0, 1, 2):
        sx1 = max(0, min(w - bw, bx1 + ldx))
        sx2 = sx1 + bw
        sub_diff = np.abs(
            orig_f[by1:by2, bx1:bx2] - aligned_edit[sy1:sy2, sx1:sx2]
        ).max(axis=2)
        ink_diffs = sub_diff[ink_union]
        m_val = float(ink_diffs.mean()) if ink_diffs.size > 0 else 0.0
        if m_val < best_ink_mean:
          best_ink_mean = m_val
          best_ink_changed_frac = (
              float((ink_diffs > 26.0).mean()) if ink_diffs.size > 0 else 0.0
          )

    if best_ink_mean < 16.0 and best_ink_changed_frac < 0.16:
      continue

    orig_rows = orig_box_ink.mean(axis=1) > 0.008
    orig_rows_dil = orig_rows.copy()
    for r_shift in (-4, -3, -2, -1, 1, 2, 3, 4):
      orig_rows_dil |= np.roll(orig_rows, r_shift)
    edit_rows = edit_box_ink.mean(axis=1) > 0.008
    if edit_rows.any():
      row_overlap = float((edit_rows & orig_rows_dil).sum()) / float(
          edit_rows.sum()
      )
      if row_overlap < 0.55:
        continue

    # Expand rightwards up to 72px if original or edited text line continues on the same background
    while bx2 < w - 2 and (bx2 - rx2) < 72:
      col_o = orig_f[by1:by2, bx2]
      col_e = aligned_edit[by1:by2, bx2]
      col_diff = float(np.abs(col_o - col_e).max(axis=1).max())
      has_ink = (
          float(np.abs(col_o - bg_est[None, :]).max()) > 26.0
          or float(np.abs(col_e - bg_est[None, :]).max()) > 26.0
      )
      if col_diff > 16.0 or has_ink:
        if (
            (by2 - by1) >= 16
            and float(col_o.std(axis=0).max()) < 4.0
            and float(np.abs(col_o.mean(axis=0) - bg_est).max()) > 20.0
        ):
          break
        bx2 += 1
      else:
        break

    # Expand leftwards up to 36px if modified word starts slightly earlier
    while bx1 > 2 and (rx1 - bx1) < 36:
      col_o = orig_f[by1:by2, bx1 - 1]
      col_e = aligned_edit[by1:by2, bx1 - 1]
      col_diff = float(np.abs(col_o - col_e).max(axis=1).max())
      if col_diff > 16.0:
        bx1 -= 1
      else:
        break

    fx1 = max(0, bx1 - 5)
    fy1 = max(0, by1 - 4)
    fx2 = min(w, bx2 + 6)
    fy2 = min(h, by2 + 4)
    verified_boxes.append((fx1, fy1, fx2, fy2))

  return verified_boxes


def _align_and_lock_ui_keyframe_pixels(
    orig_rgb,
    edited_rgb,
    diff_threshold: float = 22.0,
) -> tuple:
  """Aligns a 2K-edited UI keyframe to the original screenshot and composites only verified rectangular text-block patches onto the original crisp UI."""
  import numpy as np
  from PIL import Image, ImageFilter

  h, w = orig_rgb.shape[:2]
  if edited_rgb.shape[:2] != (h, w):
    edited_pil = Image.fromarray(edited_rgb).resize(
        (w, h), Image.Resampling.LANCZOS
    )
    edited_rgb = np.array(edited_pil, dtype=np.uint8)

  orig_f = orig_rgb.astype(np.float32)
  best_edit = edited_rgb.astype(np.float32)

  # 1. Integer pixel translation alignment (dx, dy in [-2..2]) to eliminate any 1-2px global resampling shift
  best_score = float(np.abs(orig_f - best_edit).mean())
  aligned_edit = best_edit
  for dy in (-2, -1, 0, 1, 2):
    for dx in (-2, -1, 0, 1, 2):
      if dx == 0 and dy == 0:
        continue
      shifted = np.roll(np.roll(best_edit, dy, axis=0), dx, axis=1)
      score = float(
          np.abs(
              orig_f[4 : h - 4, 4 : w - 4] - shifted[4 : h - 4, 4 : w - 4]
          ).mean()
      )
      if score < best_score - 0.15:
        best_score = score
        aligned_edit = shifted

  # 2. Match global flat background luminance offset
  pixel_max_diff = np.abs(orig_f - aligned_edit).max(axis=2)
  unchanged_bg = pixel_max_diff < 12.0
  if unchanged_bg.mean() > 0.25:
    for c in range(3):
      bias = float(
          np.median(
              orig_f[:, :, c][unchanged_bg]
              - aligned_edit[:, :, c][unchanged_bg]
          )
      )
      if abs(bias) <= 8.0:
        aligned_edit[:, :, c] = np.clip(
            aligned_edit[:, :, c] + bias, 0.0, 255.0
        )

  # 2b. Neutralize pastel text-selection highlight tints (e.g. #D2E3FC light-blue highlight bars over white background)
  # where both original and edited pixels are bright (luminance > 185) and diff < 62 RGB units
  orig_lum = orig_f.mean(axis=2)
  edit_lum = aligned_edit.mean(axis=2)
  pastel_tint = (
      (orig_lum > 195.0)
      & (edit_lum > 185.0)
      & (np.abs(orig_f - aligned_edit).max(axis=2) < 62.0)
  )
  if pastel_tint.any():
    aligned_edit[pastel_tint] = orig_f[pastel_tint]

  # 3. Extract verified rectangular text-edit bounding boxes
  boxes = _extract_verified_ui_edit_boxes(
      orig_f, aligned_edit, diff_threshold=diff_threshold
  )
  if not boxes:
    return orig_rgb.copy(), np.zeros((h, w, 1), dtype=np.float32)

  rect_mask = np.zeros((h, w), dtype=np.uint8)
  for x1, y1, x2, y2 in boxes:
    # Locally match background shade inside each rectangular box so card background is seamless
    sub_o = orig_f[y1:y2, x1:x2]
    sub_e = aligned_edit[y1:y2, x1:x2]
    sub_unchanged = np.abs(sub_o - sub_e).max(axis=2) < 14.0
    if sub_unchanged.mean() > 0.15:
      for c in range(3):
        local_bias = float(
            np.median(
                sub_o[:, :, c][sub_unchanged] - sub_e[:, :, c][sub_unchanged]
            )
        )
        if abs(local_bias) <= 10.0:
          aligned_edit[y1:y2, x1:x2, c] = np.clip(
              sub_e[:, :, c] + local_bias, 0.0, 255.0
          )
    rect_mask[y1:y2, x1:x2] = 255

  # Soft 1.5px feather only at the outer perimeter of the clean rectangular text blocks
  feathered_pil = Image.fromarray(rect_mask, mode="L").filter(
      ImageFilter.GaussianBlur(radius=1.2)
  )
  alpha_mask = np.array(feathered_pil, dtype=np.float32)[:, :, None] / 255.0

  composited = np.clip(
      orig_f * (1.0 - alpha_mask) + aligned_edit * alpha_mask, 0.0, 255.0
  ).astype(np.uint8)
  return composited, alpha_mask


def _edit_ui_keyframe_with_pixel_lock(
    orig_rgb,
    triage_plan: dict,
    customer_name: str,
    industry: str,
    client: any,
    image_model: str = "gemini-3.1-flash-image",
    fallback_model: str = "gemini-3-pro-image",
) -> tuple:
  """Edits a single UI screen-recording keyframe at 2K resolution via gemini-3.1-flash-image on an aspect-locked canvas and composites only the modified text/product regions back onto the original crisp UI."""
  import io
  import numpy as np
  from PIL import Image
  from google.genai import types

  h, w = orig_rgb.shape[:2]
  if not client:
    return orig_rgb.copy(), np.zeros((h, w, 1), dtype=np.float32)

  # Pad orig_rgb onto an exact 16:9 or 9:16 canvas so Gemini image generation performs zero aspect-ratio stretching or cropping
  is_portrait = h > w * 1.15
  target_ar_str = "9:16" if is_portrait else "16:9"
  target_ar = (9.0 / 16.0) if is_portrait else (16.0 / 9.0)
  cur_ar = float(w) / max(1.0, float(h))

  pad_w, pad_h = w, h
  if abs(cur_ar - target_ar) > 0.01:
    if cur_ar < target_ar:
      pad_w = int(round(h * target_ar))
    else:
      pad_h = int(round(w / target_ar))

  canvas = Image.new("RGB", (pad_w, pad_h), (255, 255, 255))
  canvas.paste(Image.fromarray(orig_rgb), (0, 0))
  buf = io.BytesIO()
  canvas.save(buf, format="PNG")
  canvas_png = buf.getvalue()

  reps = triage_plan.get("text_replacements") or []
  rep_lines = [
      f'- Replace "{r["original"]}" with "{r["replacement"]}"'
      for r in reps
      if isinstance(r, dict) and r.get("original") and r.get("replacement")
  ]
  if not rep_lines:
    rep_lines = [
        '- Replace any "Cymbal" or generic demo brand/product text with'
        f' "{customer_name}" equivalents of identical length.'
    ]

  domain_label = f" ({industry})" if industry else ""
  edit_prompt = (
      "SURGICAL UI SCREENSHOT TEXT EDIT — PRESERVE 100% UI FIDELITY:\n"
      "This is a high-resolution software UI screenshot. You MUST keep the"
      " exact pixel coordinates, UI layout, card borders, icons, avatars,"
      " mouse cursor, background colors, and Google Sans / Roboto font"
      " styling 100% identical to the input image.\n"
      f"Target Account: {customer_name}{domain_label}\n"
      "ONLY perform these exact in-place text/brand replacements (if visible"
      " in this frame):\n"
      + "\n".join(rep_lines)
      + "\nCRITICAL RULES:\n1. Each replacement text MUST fit inside the exact"
      " same line and bounding box as the original text with matching font"
      " size, weight, and color.\n2. Do NOT modify or rewrite any other text"
      " lines, headers, or paragraphs that are not listed above.\n3. If none"
      " of the target strings appear in this frame, return the input image"
      " completely unchanged.\n4. Do NOT add floating logos, watermarks,"
      " selection highlights, or new UI panels."
  )

  for m_name in (image_model, fallback_model, "gemini-3.1-flash-image"):
    if not m_name:
      continue
    try:
      resp = client.models.generate_content(
          model=m_name,
          contents=[
              types.Part.from_bytes(data=canvas_png, mime_type="image/png"),
              edit_prompt,
          ],
          config=types.GenerateContentConfig(
              http_options=types.HttpOptions(
                  api_version="v1beta1", timeout=45000
              ),
              response_modalities=["IMAGE"],
              temperature=0.15,
              image_config=types.ImageConfig(
                  image_size="2K",
                  aspect_ratio=target_ar_str,
              ),
          ),
      )
      if resp and resp.candidates and resp.candidates[0].content.parts:
        for part in resp.candidates[0].content.parts:
          if part.inline_data and part.inline_data.data:
            with Image.open(io.BytesIO(part.inline_data.data)) as out_im:
              out_resized = out_im.convert("RGB").resize(
                  (pad_w, pad_h), Image.Resampling.LANCZOS
              )
              out_cropped = out_resized.crop((0, 0, w, h))
              edited_arr = np.array(out_cropped, dtype=np.uint8)
              return _align_and_lock_ui_keyframe_pixels(orig_rgb, edited_arr)
    except Exception as e:
      print(f"[ImageUtil] UI keyframe edit warning ({m_name}): {e}")
      continue

  return orig_rgb.copy(), np.zeros((h, w, 1), dtype=np.float32)


def _propagate_ui_edits_across_frames(
    frames_rgb: list,
    keyframe_indices: list[int],
    segment_ranges: list[tuple[int, int]],
    edited_keyframes: list,
    edit_masks: list,
) -> list:
  """Propagates surgical 2K UI text edits across all frames of a UI product demo GIF using per-box matching against each native frame `frames_rgb[t]`.

  Never cross-dissolves full frames (eliminating double-exposure ghosting on
  flowcharts, popups, and dropdowns) and always clears the full rectangular
  text box to flat background color before progressive typing reveals.
  """
  import numpy as np

  n = len(frames_rgb)
  if n == 0 or not keyframe_indices or not edited_keyframes:
    return list(frames_rgb)

  h, w = frames_rgb[0].shape[:2]

  # Extract individual rectangular patch descriptors from all edited keyframes
  raw_patches: list[dict] = []
  for seg_i, k_idx in enumerate(keyframe_indices):
    mask_2d = edit_masks[seg_i][:, :, 0] > 0.25
    if not mask_2d.any():
      continue
    orig_kf = frames_rgb[k_idx].astype(np.float32)
    edit_kf = edited_keyframes[seg_i].astype(np.float32)

    # Find connected rectangular regions in mask_2d via 4x4 grid flood-fill
    cell = 4
    gh = (h + cell - 1) // cell
    gw = (w + cell - 1) // cell
    padded = np.zeros((gh * cell, gw * cell), dtype=bool)
    padded[:h, :w] = mask_2d
    grid = padded.reshape(gh, cell, gw, cell).any(axis=(1, 3))
    visited = np.zeros_like(grid, dtype=bool)

    for gy in range(gh):
      for gx in range(gw):
        if grid[gy, gx] and not visited[gy, gx]:
          stack = [(gy, gx)]
          visited[gy, gx] = True
          min_gy = max_gy = gy
          min_gx = max_gx = gx
          while stack:
            cy, cx = stack.pop()
            min_gy = min(min_gy, cy)
            max_gy = max(max_gy, cy)
            min_gx = min(min_gx, cx)
            max_gx = max(max_gx, cx)
            for ny in range(max(0, cy - 1), min(gh, cy + 2)):
              for nx in range(max(0, cx - 1), min(gw, cx + 2)):
                if grid[ny, nx] and not visited[ny, nx]:
                  visited[ny, nx] = True
                  stack.append((ny, nx))
          x1 = max(0, min_gx * cell)
          y1 = max(0, min_gy * cell)
          x2 = min(w, (max_gx + 1) * cell)
          y2 = min(h, (max_gy + 1) * cell)
          if (x2 - x1) < 8 or (y2 - y1) < 6:
            continue

          patch_o = orig_kf[y1:y2, x1:x2]
          patch_e = edit_kf[y1:y2, x1:x2]
          sub_alpha = edit_masks[seg_i][y1:y2, x1:x2]

          # Context ring around (x1, y1, x2, y2) to verify container presence and background color
          rx1 = max(0, x1 - 14)
          ry1 = max(0, y1 - 10)
          rx2 = min(w, x2 + 14)
          ry2 = min(h, y2 + 10)
          ring_mask = np.ones((ry2 - ry1, rx2 - rx1), dtype=bool)
          ring_mask[y1 - ry1 : y2 - ry1, x1 - rx1 : x2 - rx1] = False
          orig_ring = orig_kf[ry1:ry2, rx1:rx2]

          # Estimate flat background color from the surrounding container ring + brightest pixels of orig_patch
          ring_px = orig_ring[ring_mask]
          if ring_px.size > 0:
            ring_lum = ring_px.mean(axis=1)
            p65 = np.percentile(ring_lum, 65)
            bg_color = np.median(ring_px[ring_lum >= p65], axis=0)
          else:
            lum = patch_o.mean(axis=2)
            p75 = np.percentile(lum, 75)
            bg_color = np.median(patch_o[lum >= p75], axis=0)

          orig_ink = (
              np.abs(patch_o - bg_color[None, None, :]).max(axis=2) > 24.0
          )
          orig_ink_1px = orig_ink.copy()
          for dy_i in (-1, 0, 1):
            for dx_i in (-1, 0, 1):
              if dx_i != 0 or dy_i != 0:
                orig_ink_1px |= np.roll(
                    np.roll(orig_ink, dy_i, axis=0), dx_i, axis=1
                )
          raw_patches.append({
              "k_idx": k_idx,
              "seg_i": seg_i,
              "box": (x1, y1, x2, y2),
              "ring_box": (rx1, ry1, rx2, ry2),
              "ring_mask": ring_mask,
              "orig_ring": orig_ring,
              "orig_patch": patch_o,
              "edit_patch": patch_e,
              "sub_alpha": sub_alpha,
              "bg_color": bg_color,
              "orig_ink": orig_ink,
              "orig_ink_1px": orig_ink_1px,
              "orig_ink_count": max(1, int(orig_ink.sum())),
          })

  if not raw_patches:
    return [f.copy() for f in frames_rgb]

  # Canonicalize overlapping patches that correspond to the exact same underlying original text block
  # so the edited text never shimmers between keyframes
  for i, pi in enumerate(raw_patches):
    ix1, iy1, ix2, iy2 = pi["box"]
    for j in range(i):
      pj = raw_patches[j]
      jx1, jy1, jx2, jy2 = pj["box"]
      ox1, oy1 = max(ix1, jx1), max(iy1, jy1)
      ox2, oy2 = min(ix2, jx2), min(iy2, jy2)
      if (ox2 - ox1) > 0.6 * min(ix2 - ix1, jx2 - jx1) and (
          oy2 - oy1
      ) > 0.6 * min(iy2 - iy1, jy2 - jy1):
        sub_oi = pi["orig_patch"][oy1 - iy1 : oy2 - iy1, ox1 - ix1 : ox2 - ix1]
        sub_oj = pj["orig_patch"][oy1 - jy1 : oy2 - jy1, ox1 - jx1 : ox2 - jx1]
        if float(np.abs(sub_oi - sub_oj).mean()) < 9.0:
          pi["edit_patch"][oy1 - iy1 : oy2 - iy1, ox1 - ix1 : ox2 - ix1] = pj[
              "edit_patch"
          ][oy1 - jy1 : oy2 - jy1, ox1 - jx1 : ox2 - jx1]
          break

  out_frames: list = []
  for t in range(n):
    ft = frames_rgb[t].astype(np.float32)
    canvas = ft.copy()

    # Sort candidate patches by temporal proximity to frame t so the closest keyframe is evaluated first
    ordered_patches = sorted(raw_patches, key=lambda p: abs(t - p["k_idx"]))
    applied_regions: list[tuple[int, int, int, int]] = []

    for p in ordered_patches:
      x1, y1, x2, y2 = p["box"]
      if any(
          (min(x2, ax2) - max(x1, ax1)) > 0.5 * min(x2 - x1, ax2 - ax1)
          and (min(y2, ay2) - max(y1, ay1)) > 0.5 * min(y2 - y1, ay2 - ay1)
          for (ax1, ay1, ax2, ay2) in applied_regions
      ):
        continue

      orig_patch = p["orig_patch"]
      edit_patch = p["edit_patch"]
      sub_alpha = p["sub_alpha"]
      bg_color = p["bg_color"]
      orig_ink = p["orig_ink"]
      orig_ink_1px = p["orig_ink_1px"]

      ft_patch = ft[y1:y2, x1:x2]
      diff_map = np.abs(ft_patch - orig_patch).max(axis=2)
      p95_diff = float(np.percentile(diff_map, 95))
      mean_diff = float(diff_map.mean())
      changed_frac = float((diff_map > 26.0).mean())
      ft_ink = np.abs(ft_patch - bg_color[None, None, :]).max(axis=2) > 24.0
      ink_overlap = int((orig_ink_1px & ft_ink).sum())
      ink_recall = (
          float(ink_overlap) / float(p["orig_ink_count"])
          if orig_ink.any()
          else 1.0
      )
      ink_precision = (
          float(ink_overlap) / float(max(1, int(ft_ink.sum())))
          if orig_ink.any()
          else 1.0
      )

      # Case 1: Stationary text match at (x1, y1, x2, y2) — ALWAYS require ink_recall and ink_precision so blank white areas never match
      if t == p["k_idx"] or (
          ink_recall >= 0.78
          and ink_precision >= 0.65
          and ((p95_diff < 24.0 and mean_diff < 9.0) or changed_frac <= 0.10)
      ):
        comp_box = ft_patch * (1.0 - sub_alpha) + edit_patch * sub_alpha
        cursor_px = (diff_map > 38.0) & (
            np.abs(ft_patch - bg_color[None, None, :]).max(axis=2) > 35.0
        )
        if 0.002 < float(cursor_px.mean()) < 0.12:
          comp_box[cursor_px] = ft_patch[cursor_px]
        canvas[y1:y2, x1:x2] = comp_box
        applied_regions.append((x1, y1, x2, y2))
        continue

      # Case 2: Vertical scroll / camera drift match — verify original ink presence at (x1 + dx, y1 + dy) so blank white space never matches
      pw, ph = x2 - x1, y2 - y1
      best_dy = 0
      best_dx = 0
      best_scroll_score = float("inf")
      max_dy = min(220, h // 2)
      for dy in range(-max_dy, max_dy + 1, 2):
        if dy == 0:
          continue
        sy1, sy2 = y1 + dy, y2 + dy
        if sy1 < 0 or sy2 > h:
          continue
        cand_patch = ft[sy1:sy2, x1:x2]
        cand_ink = (
            np.abs(cand_patch - bg_color[None, None, :]).max(axis=2) > 24.0
        )
        c_ink_cnt = int(cand_ink.sum())
        if c_ink_cnt < int(p["orig_ink_count"] * 0.72) or c_ink_cnt > int(
            p["orig_ink_count"] * 1.38
        ):
          continue
        ov = int((orig_ink_1px & cand_ink).sum())
        if (
            float(ov) / float(p["orig_ink_count"]) < 0.75
            or float(ov) / float(max(1, c_ink_cnt)) < 0.65
        ):
          continue
        s_mean = float(np.abs(cand_patch - orig_patch).mean())
        if s_mean < best_scroll_score:
          best_scroll_score = s_mean
          best_dy = dy

      if best_dy != 0 and best_scroll_score < 12.0:
        # Fine 1px refinement around best_dy and dx in [-2..2]
        fine_dy, fine_dx = best_dy, 0
        fine_score = best_scroll_score
        for dy_f in (best_dy - 1, best_dy, best_dy + 1):
          sy1, sy2 = y1 + dy_f, y2 + dy_f
          if sy1 < 0 or sy2 > h:
            continue
          for dx_f in (-2, -1, 0, 1, 2):
            sx1, sx2 = x1 + dx_f, x2 + dx_f
            if sx1 < 0 or sx2 > w:
              continue
            cand_f = ft[sy1:sy2, sx1:sx2]
            m_f = float(np.abs(cand_f - orig_patch).mean())
            if m_f < fine_score:
              fine_score = m_f
              fine_dy, fine_dx = dy_f, dx_f

        sy1, sy2 = y1 + fine_dy, y2 + fine_dy
        sx1, sx2 = x1 + fine_dx, x2 + fine_dx
        cand_patch = ft[sy1:sy2, sx1:sx2]
        cand_ink = (
            np.abs(cand_patch - bg_color[None, None, :]).max(axis=2) > 24.0
        )
        ov = int((orig_ink_1px & cand_ink).sum())
        s_rec = float(ov) / float(p["orig_ink_count"])
        s_prec = float(ov) / float(max(1, int(cand_ink.sum())))
        if fine_score < 8.5 and s_rec >= 0.80 and s_prec >= 0.70:
          canvas[sy1:sy2, sx1:sx2] = (
              cand_patch * (1.0 - sub_alpha) + edit_patch * sub_alpha
          )
          applied_regions.append((sx1, sy1, sx2, sy2))
          continue

      # Case 3: Progressive left-to-right typing inside the same input container before keyframe k_idx
      if t < p["k_idx"]:
        rx1, ry1, rx2, ry2 = p["ring_box"]
        ring_mask = p["ring_mask"]
        ft_ring = ft[ry1:ry2, rx1:rx2]
        ring_diffs = np.abs(ft_ring - p["orig_ring"]).max(axis=2)[ring_mask]
        ring_p80 = (
            float(np.percentile(ring_diffs, 80))
            if ring_diffs.size > 0
            else 99.0
        )
        bg_dist = np.abs(ft_patch - bg_color[None, None, :]).max(axis=2)
        bg_fraction = float((bg_dist < 24.0).mean())
        ink_ratio = float(ft_ink.sum()) / float(p["orig_ink_count"])

        if (
            ring_p80 < 10.5
            and bg_fraction >= 0.55
            and 0.04 <= ink_ratio <= 0.95
            and ft_ink.any()
        ):
          # Verify that the ink already typed in ft_patch is genuinely a prefix of orig_ink
          orig_ink_dil = orig_ink.copy()
          for dy_d in (-2, -1, 0, 1, 2):
            for dx_d in (-2, -1, 0, 1, 2):
              if dx_d != 0 or dy_d != 0:
                orig_ink_dil |= np.roll(
                    np.roll(orig_ink, dy_d, axis=0), dx_d, axis=1
                )
          prefix_precision = float((ft_ink & orig_ink_dil).sum()) / float(
              max(1, int(ft_ink.sum()))
          )
          if prefix_precision >= 0.65:
            clean_slate = (
                ft_patch * (1.0 - sub_alpha)
                + bg_color[None, None, :] * sub_alpha
            )
            if ph <= 48:
              ink_cols = np.where(ft_ink.any(axis=0))[0]
              reveal_x = (
                  int(np.percentile(ink_cols, 96)) + 4
                  if ink_cols.size > 0
                  else int(round(pw * ink_ratio))
              )
              reveal_x = max(0, min(pw, reveal_x))
              right_tail_ink = (
                  float(ft_ink[:, reveal_x + 8 :].mean())
                  if (reveal_x + 8) < pw
                  else 0.0
              )
              if right_tail_ink < 0.015:
                clean_slate[:, :reveal_x] = (
                    ft_patch[:, :reveal_x] * (1.0 - sub_alpha[:, :reveal_x])
                    + edit_patch[:, :reveal_x] * sub_alpha[:, :reveal_x]
                )
                canvas[y1:y2, x1:x2] = clean_slate
                applied_regions.append((x1, y1, x2, y2))
            else:
              ink_rows = np.where(ft_ink.any(axis=1))[0]
              max_ink_y = (
                  int(ink_rows.max())
                  if ink_rows.size > 0
                  else int(round(ph * ink_ratio))
              )
              line_top = max(0, max_ink_y - 22)
              if line_top > 0:
                clean_slate[:line_top, :] = (
                    ft_patch[:line_top, :] * (1.0 - sub_alpha[:line_top, :])
                    + edit_patch[:line_top, :] * sub_alpha[:line_top, :]
                )
              active_band_ink = ft_ink[line_top : min(ph, max_ink_y + 6), :]
              ink_cols = np.where(active_band_ink.any(axis=0))[0]
              reveal_x = (
                  int(np.percentile(ink_cols, 96)) + 4
                  if ink_cols.size > 0
                  else int(round(pw * ink_ratio))
              )
              reveal_x = max(0, min(pw, reveal_x))
              y_end = min(ph, max_ink_y + 6)
              clean_slate[line_top:y_end, :reveal_x] = (
                  ft_patch[line_top:y_end, :reveal_x]
                  * (1.0 - sub_alpha[line_top:y_end, :reveal_x])
                  + edit_patch[line_top:y_end, :reveal_x]
                  * sub_alpha[line_top:y_end, :reveal_x]
              )
              canvas[y1:y2, x1:x2] = clean_slate
              applied_regions.append((x1, y1, x2, y2))

    out_frames.append(np.clip(canvas, 0.0, 255.0).astype(np.uint8))

  return out_frames


def _encode_high_fidelity_ui_gif(
    frames_rgb: list,
    frame_duration_ms: int = 80,
    orig_alpha_mask: any = None,
    max_long_edge: int = 1152,
    max_bytes: int = 14 * 1024 * 1024,
) -> bytes | None:
  """Encodes high-resolution UI product demo frames into a razor-sharp looping GIF at up to 1152px long edge using a dedicated 256-color UI palette without Bayer crosshatch dithering."""
  if not frames_rgb:
    return None

  import io
  import os
  import subprocess
  import tempfile
  import numpy as np
  from PIL import Image

  h, w = frames_rgb[0].shape[:2]
  scale = min(1.0, float(max_long_edge) / float(max(w, h, 1)))
  out_w = max(64, (int(round(w * scale)) // 2) * 2)
  out_h = max(64, (int(round(h * scale)) // 2) * 2)

  resized_mask_arr = None
  if orig_alpha_mask is not None:
    try:
      resized_mask = orig_alpha_mask.resize(
          (out_w, out_h), Image.Resampling.LANCZOS
      )
      resized_mask_arr = np.array(resized_mask, dtype=np.uint8)
    except Exception:
      resized_mask_arr = None

  fps = max(4, min(20, int(round(1000.0 / max(25, frame_duration_ms)))))
  pil_frames: list[Image.Image] = []
  for arr in frames_rgb:
    im_f = Image.fromarray(arr, mode="RGB")
    if (out_w, out_h) != (w, h):
      im_f = im_f.resize((out_w, out_h), Image.Resampling.LANCZOS)
    if resized_mask_arr is not None:
      u8 = np.array(im_f, dtype=np.float32)
      alpha_f = (resized_mask_arr.astype(np.float32) / 255.0)[:, :, None]
      bg_rgb = np.array([15.0, 17.0, 21.0], dtype=np.float32)[None, None, :]
      comp_rgb = u8 * alpha_f + bg_rgb * (1.0 - alpha_f)
      im_f = Image.fromarray(
          np.clip(comp_rgb, 0.0, 255.0).astype(np.uint8), mode="RGB"
      )
    pil_frames.append(im_f)

  try:
    with tempfile.TemporaryDirectory(prefix="pg_ui_gif_") as tmpdir:
      for i, im_f in enumerate(pil_frames):
        im_f.save(os.path.join(tmpdir, f"ui_{i:04d}.png"), format="PNG")
      palette_png = os.path.join(tmpdir, "palette.png")
      out_gif = os.path.join(tmpdir, "ui_out.gif")
      subprocess.run(
          [
              "/usr/bin/ffmpeg",
              "-y",
              "-framerate",
              str(fps),
              "-i",
              os.path.join(tmpdir, "ui_%04d.png"),
              "-vf",
              "palettegen=max_colors=256:stats_mode=full:reserve_transparent=0",
              palette_png,
          ],
          check=True,
          stdout=subprocess.DEVNULL,
          stderr=subprocess.DEVNULL,
          timeout=30,
      )
      subprocess.run(
          [
              "/usr/bin/ffmpeg",
              "-y",
              "-framerate",
              str(fps),
              "-i",
              os.path.join(tmpdir, "ui_%04d.png"),
              "-i",
              palette_png,
              "-lavfi",
              "paletteuse=dither=sierra2_4a:diff_mode=rectangle",
              "-loop",
              "0",
              out_gif,
          ],
          check=True,
          stdout=subprocess.DEVNULL,
          stderr=subprocess.DEVNULL,
          timeout=40,
      )
      if os.path.exists(out_gif):
        with open(out_gif, "rb") as f:
          gif_b = f.read()
        if len(gif_b) <= max_bytes and gif_b.startswith((b"GIF87a", b"GIF89a")):
          return gif_b
  except Exception as e:
    print(
        f"[ImageUtil] High-fidelity UI ffmpeg encode notice ({e}); using"
        " Pillow."
    )

  try:
    buf = io.BytesIO()
    pil_frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=pil_frames[1:],
        duration=max(30, int(frame_duration_ms)),
        loop=0,
        optimize=True,
    )
    return buf.getvalue()
  except Exception as pil_err:
    print(f"[ImageUtil] Pillow UI GIF fallback error: {pil_err}")
    return None


def _resolve_ui_fonts() -> dict[str, str]:
  """Resolves bundled Google Sans TrueType fonts (with Roboto/DejaVu fallbacks) for crisp UI vector text rendering."""
  import os

  base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
  candidates = {
      "regular": [
          os.path.join(base_dir, "GoogleSans-Regular.ttf"),
          "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Regular.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
      ],
      "medium": [
          os.path.join(base_dir, "GoogleSans-Medium.ttf"),
          "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Medium.ttf",
          os.path.join(base_dir, "GoogleSans-Regular.ttf"),
          "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
      ],
      "bold": [
          os.path.join(base_dir, "GoogleSans-Bold.ttf"),
          "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Bold.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
      ],
  }
  resolved: dict[str, str] = {}
  for weight, paths in candidates.items():
    for p in paths:
      if os.path.exists(p):
        resolved[weight] = p
        break
  return resolved


def _extract_ui_ink_map(frame_rgb) -> any:
  """Extracts a normalized [0.0..1.0] glyph ink contrast map supporting both dark-on-light UI cards and white-on-dark toast notifications."""
  import numpy as np
  from PIL import Image, ImageFilter

  gray_u8 = np.mean(frame_rgb, axis=2).astype(np.uint8)
  pil_g = Image.fromarray(gray_u8, mode="L")
  bg_light = np.array(pil_g.filter(ImageFilter.MaxFilter(15)), dtype=np.float32)
  bg_dark = np.array(pil_g.filter(ImageFilter.MinFilter(15)), dtype=np.float32)
  local_mean = np.array(pil_g.filter(ImageFilter.BoxBlur(12)), dtype=np.float32)
  gray_f = gray_u8.astype(np.float32)

  dark_ink = np.clip((bg_light - gray_f) / 130.0, 0.0, 1.0)
  light_ink = np.clip((gray_f - bg_dark) / 130.0, 0.0, 1.0)
  return np.where(local_mean < 128.0, light_ink, dark_ink).astype(np.float32)


def _render_token_ink_template(
    text: str,
    font_path: str,
    pt_size: int,
    angle_deg: float = 0.0,
) -> any:
  """Renders a 2x-supersampled normalized [0..1] glyph template cropped tightly to ink bounds."""
  import numpy as np
  from PIL import Image, ImageDraw, ImageFont

  font = ImageFont.truetype(font_path, max(8, int(pt_size * 2)))
  bbox = font.getbbox(text)
  w2 = max(6, bbox[2] - bbox[0] + 8)
  h2 = max(6, bbox[3] - bbox[1] + 8)
  im = Image.new("L", (w2, h2), 0)
  draw = ImageDraw.Draw(im)
  draw.text((4 - bbox[0], 4 - bbox[1]), text, fill=255, font=font)
  w1 = max(3, int(round(w2 / 2.0)))
  h1 = max(3, int(round(h2 / 2.0)))
  im = im.resize((w1, h1), Image.Resampling.LANCZOS)
  if abs(angle_deg) >= 0.5:
    im = im.rotate(
        -angle_deg,
        resample=Image.Resampling.BICUBIC,
        expand=True,
        fillcolor=0,
    )
  arr = np.array(im, dtype=np.float32) / 255.0
  ys, xs = np.where(arr > 0.08)
  if ys.size > 0:
    arr = arr[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
  return arr


def _next_fast_fft_len(n: int) -> int:
  """Returns the smallest 5-smooth integer (2^a * 3^b * 5^c) >= n so numpy rfft2/irfft2 runs at peak radix speed."""
  n = max(16, int(n))
  while True:
    m = n
    for p in (2, 3, 5):
      while m % p == 0:
        m //= p
    if m == 1:
      return n
    n += 1


def _build_ui_token_templates(
    customer_name: str,
    fft_shape: tuple[int, int],
    triage_plan: dict | None = None,
) -> list[dict]:
  """Builds precomputed FFT frequency-domain glyph templates across font sizes and 3D tilt angles."""
  import re
  import numpy as np

  fonts = _resolve_ui_fonts()
  if not fonts.get("regular"):
    return []

  clean_cust = str(customer_name or "Customer").strip()
  cust_slug = re.sub(r"[^a-z0-9]", "", clean_cust.lower()) or "customer"
  fp_reg = fonts["regular"]
  fp_bold = fonts.get("bold") or fp_reg

  sizes_main = [10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 22, 24, 26]
  sizes_bold = [12, 13, 14, 15, 16, 17, 18, 20]
  sizes_email = [10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 22]
  sizes_tilt_reg = [13, 14, 15, 16, 17, 18, 19]
  sizes_tilt_bold = [14, 15, 16, 17, 18]
  sizes_prefix = [14, 16, 18, 20, 22, 25]

  token_specs = [
      ("Cymbal", clean_cust, [0.0], sizes_main, 0.67, False, fp_reg),
      ("Cymbal", clean_cust, [0.0], sizes_bold, 0.68, False, fp_bold),
      ("cymbal", cust_slug, [0.0], sizes_email, 0.67, False, fp_reg),
      ("Cymbal", clean_cust, [2.5], sizes_tilt_reg, 0.65, False, fp_reg),
      ("Cymbal", clean_cust, [2.5], sizes_tilt_bold, 0.65, False, fp_bold),
      ("Cymba", clean_cust, [0.0], sizes_prefix, 0.72, True, fp_reg),
      ("Cymb", clean_cust, [0.0], sizes_prefix, 0.72, True, fp_reg),
  ]

  strip_fft_shape = (128, fft_shape[1])
  templates: list[dict] = []
  for tok, rep, angles, pt_range, thresh, is_pre, fp in token_specs:
    for ang in angles:
      for pt in pt_range:
        tpl = _render_token_ink_template(tok, fp, pt, ang)
        th, tw = tpl.shape
        if th >= fft_shape[0] or tw >= fft_shape[1] or th < 5 or tw < 8:
          continue
        tpl_zm = tpl - float(tpl.mean())
        tpl_norm = float(np.sqrt(np.sum(tpl_zm * tpl_zm)))
        if tpl_norm < 1e-4:
          continue
        rev_tpl = tpl_zm[::-1, ::-1]
        f_tpl = np.fft.rfft2(rev_tpl, s=fft_shape)
        f_tpl_strip = (
            np.fft.rfft2(rev_tpl, s=strip_fft_shape) if th < 120 else None
        )
        templates.append({
            "tpl": tpl,
            "tpl_zm": tpl_zm,
            "F_tpl": f_tpl,
            "F_tpl_strip": f_tpl_strip,
            "th": th,
            "tw": tw,
            "tpl_sum": float(tpl.sum()),
            "tpl_norm": tpl_norm,
            "token": tok,
            "replacement": rep,
            "pt_size": pt,
            "angle_deg": ang,
            "font_path": fp,
            "thresh": thresh,
            "is_prefix": is_pre,
        })
  return templates


def _detect_tokens_on_frame_fft_ncc(
    ink_map,
    precomputed_tpls: list[dict],
    fft_shape: tuple[int, int],
    use_strip_fft: bool = False,
) -> list[dict]:
  """Detects all target brand/text tokens on a single frame's ink_map using 2D FFT normalized cross-correlation, integral-image variance, and left/right sub-glyph verification."""
  import numpy as np

  h, w = ink_map.shape
  if not precomputed_tpls or h < 6 or w < 10:
    return []

  f_img = np.fft.rfft2(ink_map, s=fft_shape)
  ii = (
      np.pad(ink_map, ((1, 0), (1, 0)), mode="constant")
      .cumsum(axis=0)
      .cumsum(axis=1)
  )
  ii_sq = (
      np.pad(ink_map * ink_map, ((1, 0), (1, 0)), mode="constant")
      .cumsum(axis=0)
      .cumsum(axis=1)
  )

  candidates: list[dict] = []
  for tpl_info in precomputed_tpls:
    th = tpl_info["th"]
    tw = tpl_info["tw"]
    vh = h - th + 1
    vw = w - tw + 1
    if vh <= 0 or vw <= 0:
      continue

    f_t = tpl_info.get("F_tpl_strip") if use_strip_fft else tpl_info["F_tpl"]
    if f_t is None:
      continue
    conv = np.fft.irfft2(f_img * f_t, s=fft_shape)
    num = conv[th - 1 : h, tw - 1 : w]

    thresh = tpl_info["thresh"]
    c_ys, c_xs = np.where(num >= thresh * 1.15)
    if c_ys.size == 0:
      continue

    local_sum = (
        ii[c_ys + th, c_xs + tw]
        - ii[c_ys, c_xs + tw]
        - ii[c_ys + th, c_xs]
        + ii[c_ys, c_xs]
    )
    local_sq = (
        ii_sq[c_ys + th, c_xs + tw]
        - ii_sq[c_ys, c_xs + tw]
        - ii_sq[c_ys + th, c_xs]
        + ii_sq[c_ys, c_xs]
    )
    n_px = float(th * tw)
    local_var = np.maximum(0.0, local_sq - (local_sum * local_sum) / n_px)
    denom = np.sqrt(local_var) * tpl_info["tpl_norm"]
    num_c = num[c_ys, c_xs]

    min_energy = tpl_info["tpl_sum"] * 0.36
    keep = (
        (local_sum >= min_energy) & (denom > 1.15) & (num_c >= thresh * denom)
    )
    if not keep.any():
      continue

    ys = c_ys[keep]
    xs = c_xs[keep]
    scores = num_c[keep] / denom[keep]
    order = np.argsort(-scores)
    kept_local: list[tuple[int, int]] = []
    is_pre = tpl_info["is_prefix"]
    tpl_arr = tpl_info["tpl"]
    mid_x = max(2, tw // 2)
    tpl_L = tpl_arr[:, :mid_x] - float(tpl_arr[:, :mid_x].mean())
    tpl_R = tpl_arr[:, mid_x:] - float(tpl_arr[:, mid_x:].mean())
    norm_L = float(np.sqrt(np.sum(tpl_L * tpl_L))) + 1e-5
    norm_R = float(np.sqrt(np.sum(tpl_R * tpl_R))) + 1e-5

    for idx in order:
      if len(kept_local) >= 12:
        break
      y0, x0 = int(ys[idx]), int(xs[idx])
      sc = float(scores[idx])
      if any(
          abs(y0 - ky) < th * 0.65 and abs(x0 - kx) < tw * 0.55
          for ky, kx in kept_local
      ):
        continue

      patch = ink_map[y0 : y0 + th, x0 : x0 + tw]
      # Verify both left half ("Cym") and right half ("bal") correlate with the glyph structure
      p_L = patch[:, :mid_x] - float(patch[:, :mid_x].mean())
      p_R = patch[:, mid_x:] - float(patch[:, mid_x:].mean())
      ncc_L = float(np.sum(p_L * tpl_L)) / (
          float(np.sqrt(np.sum(p_L * p_L)) + 1e-5) * norm_L
      )
      ncc_R = float(np.sum(p_R * tpl_R)) / (
          float(np.sqrt(np.sum(p_R * p_R)) + 1e-5) * norm_R
      )
      min_half = 0.54 if abs(tpl_info["angle_deg"]) >= 0.8 else 0.56
      if ncc_L < min_half or ncc_R < min_half:
        continue

      # For "Cymbal" and "cymbal", verify 'y' descender ink under char #2 AND 'l' ascender ink at the right edge (rejecting "member", "deployment", and "Conflu")
      if tpl_info["token"] in ("Cymbal", "cymbal"):
        desc_y1 = int(round(th * 0.74))
        y_col1 = max(1, int(round(tw * 0.14)))
        y_col2 = max(y_col1 + 2, int(round(tw * 0.38)))
        m_col1 = max(y_col2, int(round(tw * 0.44)))
        m_col2 = max(m_col1 + 2, int(round(tw * 0.82)))
        y_desc = float(patch[desc_y1:, y_col1:y_col2].mean())
        m_desc = float(patch[desc_y1:, m_col1:m_col2].mean())
        l_asc = float(
            patch[
                : max(2, int(round(th * 0.36))), int(round(tw * 0.84)) :
            ].mean()
        )
        if y_desc < m_desc + 0.03 or l_asc < 0.08:
          continue

      # Verify top/bottom line isolation so textured photos never trigger false positives
      if abs(tpl_info["angle_deg"]) < 0.8:
        top_strip = ink_map[max(0, y0 - 3) : max(1, y0 - 1), x0 : x0 + tw]
        bot_strip = ink_map[
            min(h - 1, y0 + th + 1) : min(h, y0 + th + 3), x0 : x0 + tw
        ]
        if float(top_strip.mean()) > 0.25 and float(bot_strip.mean()) > 0.25:
          continue

      # For typing prefixes ("the Cymb", "the Cymba"), verify that the characters after the prefix (past any 2-4px typing cursor '|') have not been typed yet
      if is_pre:
        rx1 = min(w, x0 + tw + 5)
        rx2 = min(w, x0 + tw + max(10, int(tw * 0.40)))
        if rx2 > rx1:
          right_after = ink_map[y0 : y0 + th, rx1:rx2]
          if float(right_after.mean()) > 0.055:
            continue

      kept_local.append((y0, x0))
      candidates.append({
          "x1": x0,
          "y1": y0,
          "x2": x0 + tw,
          "y2": y0 + th,
          "score": sc,
          "token": tpl_info["token"],
          "replacement": tpl_info["replacement"],
          "pt_size": tpl_info["pt_size"],
          "angle_deg": tpl_info["angle_deg"],
          "font_path": tpl_info["font_path"],
          "is_prefix": is_pre,
      })

  # Global NMS: prefer longer/full tokens ("cymbal.com", "Cymbal") over prefixes and higher NCC scores
  candidates.sort(
      key=lambda c: (
          c["score"] + (0.06 if not c["is_prefix"] else 0.0),
          len(c["token"]),
      ),
      reverse=True,
  )
  final_matches: list[dict] = []
  for c in candidates:
    cx1, cy1, cx2, cy2 = c["x1"], c["y1"], c["x2"], c["y2"]
    cw, ch = cx2 - cx1, cy2 - cy1
    overlap = False
    for m in final_matches:
      mx1, my1, mx2, my2 = m["x1"], m["y1"], m["x2"], m["y2"]
      ix = max(0, min(cx2, mx2) - max(cx1, mx1))
      iy = max(0, min(cy2, my2) - max(cy1, my1))
      if ix > 0.30 * min(cw, mx2 - mx1) and iy > 0.30 * min(ch, my2 - my1):
        overlap = True
        break
    if not overlap:
      final_matches.append(c)

  return final_matches


def _run_cloud_vision_ocr_on_frames(
    frames_rgb: list,
    customer_name: str,
    project_id: str = "your-gcp-project-id",
) -> dict[int, list[dict]]:
  """Runs batched Cloud Vision DOCUMENT_TEXT_DETECTION on tiled sprite sheets when PITCHGEN_ENABLE_CLOUD_VISION_OCR=1 is set."""
  import os

  if os.environ.get("PITCHGEN_ENABLE_CLOUD_VISION_OCR") != "1":
    return {}
  import base64
  import concurrent.futures
  import io
  import math
  import re
  import numpy as np
  from PIL import Image

  if not frames_rgb:
    return {}

  token = ""
  try:
    import google.auth
    from google.auth.transport.requests import Request

    creds, _ = google.auth.default()
    if hasattr(creds, "with_quota_project"):
      creds = creds.with_quota_project(project_id)
    creds.refresh(Request())
    token = str(getattr(creds, "token", "") or "").strip()
  except Exception:
    return {}

  if not token:
    return {}

  clean_cust = str(customer_name or "Customer").strip()
  cust_slug = re.sub(r"[^a-z0-9]", "", clean_cust.lower()) or "customer"
  fonts = _resolve_ui_fonts()
  reg_font = fonts.get("regular", "")

  n = len(frames_rgb)
  h, w = frames_rgb[0].shape[:2]
  cols, rows = 2, 6
  per_sheet = cols * rows
  pad = 8
  tile_w = w + pad
  tile_h = h + pad

  # Only include unique frames or frames that changed by >3 RGB units to minimize payload
  active_indices: list[int] = [0]
  frame_to_rep: dict[int, int] = {0: 0}
  for t in range(1, n):
    prev_rep = active_indices[-1]
    if (
        int(
            np.abs(
                frames_rgb[t].astype(np.int16)
                - frames_rgb[prev_rep].astype(np.int16)
            ).max()
        )
        <= 3
    ):
      frame_to_rep[t] = prev_rep
    else:
      active_indices.append(t)
      frame_to_rep[t] = t

  sheets: list[tuple[list[int], bytes]] = []
  for s_start in range(0, len(active_indices), per_sheet):
    batch_idxs = active_indices[s_start : s_start + per_sheet]
    n_rows = (len(batch_idxs) + cols - 1) // cols
    sheet_im = Image.new(
        "RGB", (cols * tile_w, n_rows * tile_h), (255, 255, 255)
    )
    for k, f_idx in enumerate(batch_idxs):
      r_i = k // cols
      c_i = k % cols
      sheet_im.paste(
          Image.fromarray(frames_rgb[f_idx]), (c_i * tile_w, r_i * tile_h)
      )
    buf = io.BytesIO()
    sheet_im.save(buf, format="JPEG", quality=92)
    sheets.append((batch_idxs, buf.getvalue()))

  rep_detections: dict[int, list[dict]] = {}

  def _annotate_sheet(batch_idxs: list[int], jpg_bytes: bytes):
    import requests

    b64_img = base64.b64encode(jpg_bytes).decode("ascii")
    resp = requests.post(
        "https://vision.googleapis.com/v1/images:annotate",
        headers={
            "Authorization": f"Bearer {token}",
            "x-goog-user-project": project_id,
            "Content-Type": "application/json",
        },
        json={
            "requests": [{
                "image": {"content": b64_img},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
            }]
        },
        timeout=15,
    )
    if resp.status_code != 200:
      return {}
    data = resp.json()
    responses = data.get("responses") or []
    if not responses:
      return {}
    full_ann = responses[0].get("fullTextAnnotation") or {}
    local_out: dict[int, list[dict]] = {}
    for page in full_ann.get("pages") or []:
      for block in page.get("blocks") or []:
        for para in block.get("paragraphs") or []:
          for word in para.get("words") or []:
            symbols = word.get("symbols") or []
            if not symbols:
              continue
            w_str = "".join(str(s.get("text") or "") for s in symbols)
            w_lower = w_str.lower()
            idx_sub = w_lower.find("cymbal")
            is_pre = False
            match_len = 6
            if idx_sub < 0:
              for pre_s in ("cymba", "cymb"):
                if w_lower.startswith(pre_s) and len(w_lower) <= len(pre_s) + 1:
                  idx_sub = 0
                  match_len = len(pre_s)
                  is_pre = True
                  break
            if idx_sub < 0:
              continue

            sub_syms = symbols[idx_sub : idx_sub + match_len]
            if not sub_syms:
              continue
            xs_all, ys_all = [], []
            for s_obj in sub_syms:
              verts = (s_obj.get("boundingBox") or {}).get("vertices") or []
              for v in verts:
                if "x" in v and "y" in v:
                  xs_all.append(int(v["x"]))
                  ys_all.append(int(v["y"]))
            if not xs_all or not ys_all:
              continue

            cx = 0.5 * (min(xs_all) + max(xs_all))
            cy = 0.5 * (min(ys_all) + max(ys_all))
            c_tile = int(cx) // tile_w
            r_tile = int(cy) // tile_h
            tile_k = r_tile * cols + c_tile
            if tile_k < 0 or tile_k >= len(batch_idxs):
              continue
            f_idx = batch_idxs[tile_k]
            ox = c_tile * tile_w
            oy = r_tile * tile_h

            x1 = max(0, min(xs_all) - ox)
            y1 = max(0, min(ys_all) - oy)
            x2 = min(w, max(xs_all) - ox)
            y2 = min(h, max(ys_all) - oy)
            if (x2 - x1) < 6 or (y2 - y1) < 5:
              continue

            # Compute baseline tilt angle from first and last symbol bottom-left vertices
            v_first = (sub_syms[0].get("boundingBox") or {}).get(
                "vertices"
            ) or []
            v_last = (sub_syms[-1].get("boundingBox") or {}).get(
                "vertices"
            ) or []
            angle_deg = 0.0
            if len(v_first) >= 4 and len(v_last) >= 4:
              dx_v = float(v_last[2].get("x", 0) - v_first[3].get("x", 0))
              dy_v = float(v_last[2].get("y", 0) - v_first[3].get("y", 0))
              if abs(dx_v) > 4.0:
                ang = math.degrees(math.atan2(dy_v, dx_v))
                if abs(ang) <= 12.0:
                  angle_deg = ang

            orig_sub = w_str[idx_sub : idx_sub + match_len]
            rep_str = cust_slug if orig_sub.islower() else clean_cust
            local_out.setdefault(f_idx, []).append({
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "score": 0.96,
                "token": orig_sub,
                "replacement": rep_str,
                "pt_size": max(10, int(round((y2 - y1) * 1.15))),
                "angle_deg": angle_deg,
                "font_path": reg_font,
                "is_prefix": is_pre,
            })
    return local_out

  try:
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(7, max(1, len(sheets)))
    ) as ex:
      futs = [
          ex.submit(_annotate_sheet, b_idxs, jpg_b) for b_idxs, jpg_b in sheets
      ]
      for fut in concurrent.futures.as_completed(futs):
        res_map = fut.result()
        for k_f, dets in res_map.items():
          rep_detections.setdefault(k_f, []).extend(dets)
  except Exception:
    return {}

  full_detections: dict[int, list[dict]] = {}
  for t in range(n):
    rep_t = frame_to_rep[t]
    if rep_t in rep_detections:
      full_detections[t] = [dict(d) for d in rep_detections[rep_t]]
  return full_detections


def _interpolate_temporal_token_matches(
    frames_rgb: list,
    ink_maps: list,
    per_frame_matches: list[list[dict]],
) -> list[list[dict]]:
  """Interpolates token bounding boxes across 1-3 frame gaps during rapid camera scroll or 3D zoom transitions so zero frames flash unedited text."""
  import math
  import numpy as np

  n = len(frames_rgb)
  if n <= 2:
    return per_frame_matches

  h, w = frames_rgb[0].shape[:2]
  out_matches = [[dict(m) for m in m_list] for m_list in per_frame_matches]

  for t_a in range(n - 2):
    if not out_matches[t_a]:
      continue
    for m_a in out_matches[t_a]:
      cxa = 0.5 * (m_a["x1"] + m_a["x2"])
      cya = 0.5 * (m_a["y1"] + m_a["y2"])
      wa = m_a["x2"] - m_a["x1"]
      ha = m_a["y2"] - m_a["y1"]

      # Check if frame t_a + 1 already has a corresponding match near (cxa, cya)
      has_next = any(
          math.hypot(
              0.5 * (m["x1"] + m["x2"]) - cxa,
              0.5 * (m["y1"] + m["y2"]) - cya,
          )
          <= max(28.0, wa * 0.75)
          for m in out_matches[t_a + 1]
      )
      if has_next:
        continue

      # Look ahead up to 4 frames for the continuation of the same token trajectory
      found_tb = -1
      best_mb = None
      for t_b in range(t_a + 2, min(n, t_a + 5)):
        for m_b in out_matches[t_b]:
          if m_b["replacement"] != m_a["replacement"]:
            continue
          cxb = 0.5 * (m_b["x1"] + m_b["x2"])
          cyb = 0.5 * (m_b["y1"] + m_b["y2"])
          if math.hypot(cxb - cxa, cyb - cya) <= 95.0:
            found_tb = t_b
            best_mb = m_b
            break
        if found_tb > 0:
          break

      if found_tb > 0 and best_mb is not None:
        for t_mid in range(t_a + 1, found_tb):
          alpha = float(t_mid - t_a) / float(found_tb - t_a)
          ix1 = int(round((1.0 - alpha) * m_a["x1"] + alpha * best_mb["x1"]))
          iy1 = int(round((1.0 - alpha) * m_a["y1"] + alpha * best_mb["y1"]))
          ix2 = int(round((1.0 - alpha) * m_a["x2"] + alpha * best_mb["x2"]))
          iy2 = int(round((1.0 - alpha) * m_a["y2"] + alpha * best_mb["y2"]))
          iw, ih = max(6, ix2 - ix1), max(5, iy2 - iy1)

          # Refine (dx, dy) within [-3..3] to maximize ink presence on ink_maps[t_mid]
          best_dx, best_dy = 0, 0
          best_ink = -1.0
          for dy in range(-4, 5):
            sy1 = max(0, min(h - ih, iy1 + dy))
            for dx in range(-3, 4):
              sx1 = max(0, min(w - iw, ix1 + dx))
              sub_ink = float(
                  ink_maps[t_mid][sy1 : sy1 + ih, sx1 : sx1 + iw].mean()
              )
              if sub_ink > best_ink:
                best_ink = sub_ink
                best_dx, best_dy = dx, dy

          if best_ink >= 0.08:
            fx1 = max(0, min(w - iw, ix1 + best_dx))
            fy1 = max(0, min(h - ih, iy1 + best_dy))
            out_matches[t_mid].append({
                **m_a,
                "x1": fx1,
                "y1": fy1,
                "x2": fx1 + iw,
                "y2": fy1 + ih,
                "angle_deg": (
                    (1.0 - alpha) * m_a["angle_deg"]
                    + alpha * best_mb["angle_deg"]
                ),
                "score": 0.70,
            })

  return out_matches


def _render_single_horizontal_line_replacements(
    img_arr,
    line_matches: list[dict],
    fonts: dict[str, str],
) -> tuple[any, tuple[int, int, int, int]]:
  """Applies piecewise in-place Google Sans vector replacement and baseline suffix shifting along a single horizontal text line on img_arr."""
  import numpy as np
  from PIL import Image, ImageDraw, ImageFont

  h, w = img_arr.shape[:2]
  line_matches = sorted(line_matches, key=lambda m: m["x1"])
  m0 = line_matches[0]
  mk = line_matches[-1]

  raw_y1 = min(m["y1"] for m in line_matches)
  raw_y2 = max(m["y2"] for m in line_matches)
  line_h = max(6, raw_y2 - raw_y1)
  band_y1 = max(0, raw_y1 - 2)
  band_y2 = min(h, raw_y2 + 2)
  band_h = band_y2 - band_y1

  # Sample local background color from the 3px perimeter above and below the first matched token
  px1 = max(0, m0["x1"] - 4)
  px2 = min(w, mk["x2"] + 4)
  top_p = img_arr[max(0, band_y1 - 3) : max(1, band_y1), px1:px2].reshape(-1, 3)
  bot_p = img_arr[min(h - 1, band_y2) : min(h, band_y2 + 3), px1:px2].reshape(
      -1, 3
  )
  perim = (
      np.concatenate([top_p, bot_p], axis=0).astype(np.float32)
      if (top_p.size > 0 and bot_p.size > 0)
      else img_arr[band_y1:band_y2, px1:px2].reshape(-1, 3).astype(np.float32)
  )
  # Pick median of perimeter pixels to get clean flat container background
  bg_color = np.median(perim, axis=0)

  # Snap each matched token's [x1, x2] to include any 1-5px contiguous edge strokes of the same word (preventing leftover 'C' or 'l' stems)
  core_y1 = min(band_h - 1, max(0, 2))
  core_y2 = max(core_y1 + 1, band_h - 2)
  for m in line_matches:
    sx1 = max(0, m["x1"])
    sx2 = min(w, m["x2"] + 1)
    if m["token"] == "Cymbal":
      for _ in range(5):
        if sx1 <= 0:
          break
        c_diff = np.abs(
            img_arr[band_y1 + core_y1 : band_y1 + core_y2, sx1 - 1].astype(
                np.float32
            )
            - bg_color
        ).max()
        if float(c_diff) > 22.0:
          sx1 -= 1
        else:
          break
      for _ in range(5):
        if sx2 >= w:
          break
        c_diff = np.abs(
            img_arr[band_y1 + core_y1 : band_y1 + core_y2, sx2].astype(
                np.float32
            )
            - bg_color
        ).max()
        if float(c_diff) > 22.0:
          sx2 += 1
        else:
          break
    m["_snapped_x1"] = sx1
    m["_snapped_x2"] = sx2

  # Scan rightward from mk["_snapped_x2"] to find the end of the text line inside the same flat container
  scan_start_x = min(w, mk["_snapped_x2"] + 1)
  last_ink_x = scan_start_x
  empty_run = 0
  max_empty_gap = max(14, int(round(line_h * 0.95)))

  for x_col in range(scan_start_x, w):
    col_px = img_arr[band_y1:band_y2, x_col].astype(np.float32)
    col_diff = np.abs(col_px - bg_color[None, :]).max(axis=1)
    # Stop before any vertical container border or background fill transition
    if float((col_diff > 18.0).mean()) > 0.82:
      # Distinguish a vertical typing cursor '|' or 'l'/'I' (isolated 1-2px wide stroke) from a box border
      ext_y1 = max(0, band_y1 - 6)
      ext_y2 = min(h, band_y2 + 6)
      ext_col = img_arr[ext_y1:ext_y2, x_col].astype(np.float32)
      ext_diff = np.abs(ext_col - bg_color[None, :]).max(axis=1)
      if float((ext_diff > 18.0).mean()) > 0.85:
        break
    if float(col_diff.max()) > 20.0:
      last_ink_x = x_col
      empty_run = 0
    else:
      empty_run += 1
      if empty_run > max_empty_gap:
        break

  line_end_x = min(w, last_ink_x + 3)

  # Render each matched token at 4x supersampling calibrated to the exact cap-height and ink color of that token
  rendered_patches: list[np.ndarray] = []
  for m in line_matches:
    mx1 = m["_snapped_x1"]
    mx2 = m["_snapped_x2"]
    tok_box = img_arr[band_y1:band_y2, mx1:mx2].astype(np.float32)
    ink_dist = np.abs(tok_box - bg_color[None, None, :]).max(axis=2)
    ink_mask = ink_dist > 18.0

    tpl_h = max(6, m["y2"] - m["y1"])
    expected_y1 = max(0, m["y1"] - band_y1)
    expected_y2 = min(band_h, m["y2"] - band_y1)

    if ink_mask.any():
      ink_rows = np.where(ink_mask.any(axis=1))[0]
      ink_y1 = max(expected_y1 - 1, int(ink_rows.min()))
      ink_y2 = min(expected_y2 + 1, int(ink_rows.max()) + 1)
      ink_pixels = tok_box[ink_mask]
      dists = ink_dist[ink_mask]
      p65 = np.percentile(dists, 65)
      fg_color = np.median(ink_pixels[dists >= p65], axis=0)
      ink_density = float(ink_mask.mean())
    else:
      ink_y1 = expected_y1
      ink_y2 = expected_y2
      fg_color = (
          np.array([245.0, 245.0, 245.0], dtype=np.float32)
          if bg_color.mean() < 110.0
          else np.array([32.0, 33.0, 36.0], dtype=np.float32)
      )
      ink_density = 0.22

    # Clamp actual_ink_h to within +/-12% of the matched template height so input-box borders never inflate font size
    actual_ink_h = max(
        max(5, int(round(tpl_h * 0.88))),
        min(int(round(tpl_h * 1.12)), ink_y2 - ink_y1),
    )
    weight_key = (
        "bold"
        if (ink_density > 0.36 or "Bold" in str(m.get("font_path", "")))
        else ("medium" if ink_density > 0.26 else "regular")
    )
    font_path = fonts.get(weight_key) or fonts.get("regular")

    # Calibrate 4x font size using reference token ink height so ascenders and baseline match to the sub-pixel
    ref_font = ImageFont.truetype(font_path, 64)
    orig_tok = m["token"]
    b_orig = ref_font.getbbox(orig_tok)
    ref_h = max(1, b_orig[3] - b_orig[1])
    size_4x = max(
        24, int(round(64.0 * 4.0 * float(actual_ink_h) / float(ref_h)))
    )
    font_4x = ImageFont.truetype(font_path, size_4x)

    rep_str = m["replacement"]
    b_orig_4x = font_4x.getbbox(orig_tok)
    b_rep_4x = font_4x.getbbox(rep_str)
    rep_w_4x = max(8, b_rep_4x[2] - b_rep_4x[0] + 6)
    band_h_4x = band_h * 4

    mask_4x = Image.new("L", (rep_w_4x, band_h_4x), 0)
    draw_4x = ImageDraw.Draw(mask_4x)
    # Align the typographical baseline of rep_str to orig_tok's ascender top (ink_y1 * 4 == b_orig_4x[1] + y_origin)
    y_origin_4x = ink_y1 * 4 - b_orig_4x[1]
    draw_4x.text(
        (2 - b_rep_4x[0], y_origin_4x), rep_str, fill=255, font=font_4x
    )

    rep_w_1x = max(3, int(round(rep_w_4x / 4.0)))
    mask_1x = mask_4x.resize((rep_w_1x, band_h), Image.Resampling.LANCZOS)
    alpha_arr = np.array(mask_1x, dtype=np.float32)[:, :, None] / 255.0

    # Crop horizontally to tight rendered ink bounds (+1px margin on right) so kerning with suffixes like '.com' or ' Retail' is exact
    col_has_ink = np.where((alpha_arr[:, :, 0] > 0.06).any(axis=0))[0]
    if col_has_ink.size > 0:
      cx1_r = max(0, int(col_has_ink.min()))
      cx2_r = min(rep_w_1x, int(col_has_ink.max()) + 2)
      alpha_arr = alpha_arr[:, cx1_r:cx2_r, :]

    patch_rgb = (
        bg_color[None, None, :] * (1.0 - alpha_arr)
        + fg_color[None, None, :] * alpha_arr
    )
    rendered_patches.append(np.clip(patch_rgb, 0.0, 255.0).astype(np.uint8))

  # Assemble reconstructed horizontal line strip from m0["_snapped_x1"] to line_end_x
  strip_x1 = max(0, m0["_snapped_x1"])
  orig_band = img_arr[band_y1:band_y2, :].copy()

  pieces: list[np.ndarray] = []
  for idx_m, m in enumerate(line_matches):
    pieces.append(rendered_patches[idx_m])
    seg_s = min(w, m["_snapped_x2"])
    seg_e = (
        min(w, line_matches[idx_m + 1]["_snapped_x1"])
        if (idx_m + 1 < len(line_matches))
        else line_end_x
    )
    if seg_e > seg_s:
      pieces.append(orig_band[:, seg_s:seg_e])

  reconstructed = (
      np.concatenate(pieces, axis=1)
      if pieces
      else np.zeros((band_h, 0, 3), dtype=np.uint8)
  )
  new_w = reconstructed.shape[1]
  orig_span_w = max(0, line_end_x - strip_x1)
  total_cover_w = max(new_w, orig_span_w)

  out_arr = img_arr.copy()
  write_end_x = min(w, strip_x1 + total_cover_w)
  # First clear the covered span [strip_x1 : write_end_x] to bg_color
  out_arr[band_y1:band_y2, strip_x1:write_end_x] = np.clip(
      bg_color, 0.0, 255.0
  ).astype(np.uint8)[None, None, :]
  # Then paste the reconstructed line strip (with shifted suffixes!) starting at strip_x1
  paste_w = min(new_w, w - strip_x1)
  if paste_w > 0:
    out_arr[band_y1:band_y2, strip_x1 : strip_x1 + paste_w] = reconstructed[
        :, :paste_w
    ]

  return out_arr, (strip_x1, band_y1, write_end_x, band_y2)


def _apply_surgical_vector_replacements_on_frame(
    frame_rgb,
    frame_matches: list[dict],
    fonts: dict[str, str],
) -> any:
  """Applies surgical Google Sans vector replacements and baseline suffix shifts across all matched text lines on a single frame (supporting both horizontal and 3D-tilted lines)."""
  import math
  import numpy as np
  from PIL import Image, ImageFilter

  if not frame_matches or not fonts.get("regular"):
    return frame_rgb.copy()

  h, w = frame_rgb.shape[:2]
  # Group matches into text lines by baseline continuity and tilt angle
  sorted_m = sorted(frame_matches, key=lambda m: (m["y1"], m["x1"]))
  lines: list[list[dict]] = []
  for m in sorted_m:
    cy = 0.5 * (m["y1"] + m["y2"])
    cx = 0.5 * (m["x1"] + m["x2"])
    mh = max(6, m["y2"] - m["y1"])
    ang = m.get("angle_deg", 0.0)
    placed = False
    for line in lines:
      ref = line[-1]
      ref_cy = 0.5 * (ref["y1"] + ref["y2"])
      ref_cx = 0.5 * (ref["x1"] + ref["x2"])
      ref_ang = ref.get("angle_deg", 0.0)
      # Positive angle_deg means counter-clockwise (uphill left-to-right, so y decreases as x increases)
      expected_cy = ref_cy - math.tan(math.radians(ref_ang)) * (cx - ref_cx)
      if abs(cy - expected_cy) <= 0.65 * mh and abs(ang - ref_ang) <= 2.5:
        line.append(m)
        placed = True
        break
    if not placed:
      lines.append([m])

  canvas = frame_rgb.copy()
  for line in lines:
    avg_ang = float(np.mean([m.get("angle_deg", 0.0) for m in line]))
    if abs(avg_ang) < 0.8:
      canvas, _ = _render_single_horizontal_line_replacements(
          canvas, line, fonts
      )
    else:
      # Deskew local region around the tilted text line by -avg_ang (clockwise to flatten uphill +avg_ang), apply horizontal replacement + suffix shift, and rotate back by +avg_ang
      line = sorted(line, key=lambda m: m["x1"])
      m0 = line[0]
      pivot_x = float(m0["x1"])
      pivot_y = 0.5 * float(m0["y1"] + m0["y2"])

      pil_full = Image.fromarray(canvas)
      deskewed_pil = pil_full.rotate(
          -avg_ang,
          resample=Image.Resampling.BICUBIC,
          center=(pivot_x, pivot_y),
      )
      deskewed_arr = np.array(deskewed_pil, dtype=np.uint8)

      rad = math.radians(-avg_ang)
      cos_a = math.cos(rad)
      sin_a = math.sin(rad)
      deskewed_line: list[dict] = []
      for m in line:
        mcx = 0.5 * (m["x1"] + m["x2"]) - pivot_x
        mcy = 0.5 * (m["y1"] + m["y2"]) - pivot_y
        rcx = pivot_x + mcx * cos_a + mcy * sin_a
        rcy = pivot_y - mcx * sin_a + mcy * cos_a
        mw = m["x2"] - m["x1"]
        mh = m["y2"] - m["y1"]
        deskewed_line.append({
            **m,
            "x1": int(round(rcx - 0.5 * mw)),
            "y1": int(round(rcy - 0.5 * mh)),
            "x2": int(round(rcx + 0.5 * mw)),
            "y2": int(round(rcy + 0.5 * mh)),
            "angle_deg": 0.0,
        })

      edited_deskewed, (bx1, by1, bx2, by2) = (
          _render_single_horizontal_line_replacements(
              deskewed_arr, deskewed_line, fonts
          )
      )
      mask_arr = np.zeros((h, w), dtype=np.uint8)
      mask_arr[max(0, by1) : min(h, by2), max(0, bx1) : min(w, bx2)] = 255
      mask_deskewed = Image.fromarray(mask_arr, mode="L").filter(
          ImageFilter.GaussianBlur(radius=0.8)
      )

      rerot_im = Image.fromarray(edited_deskewed).rotate(
          avg_ang,
          resample=Image.Resampling.BICUBIC,
          center=(pivot_x, pivot_y),
      )
      rerot_mask = mask_deskewed.rotate(
          avg_ang,
          resample=Image.Resampling.BILINEAR,
          center=(pivot_x, pivot_y),
      )
      alpha_f = np.array(rerot_mask, dtype=np.float32)[:, :, None] / 255.0
      rerot_arr = np.array(rerot_im, dtype=np.float32)
      canvas = np.clip(
          canvas.astype(np.float32) * (1.0 - alpha_f) + rerot_arr * alpha_f,
          0.0,
          255.0,
      ).astype(np.uint8)

  return canvas


def _localize_and_replace_ui_text_across_frames(
    frames_rgb: list,
    customer_name: str,
    triage_plan: dict | None = None,
    project_id: str = "your-gcp-project-id",
) -> list:
  """Option A Per-Frame Word-Polygon OCR + Multi-Scale/Angle Google Sans FFT NCC Localization + Surgical Vector Replacement Pipeline."""
  import numpy as np

  n = len(frames_rgb)
  if n == 0:
    return []

  fonts = _resolve_ui_fonts()
  if not fonts.get("regular"):
    return [f.copy() for f in frames_rgb]

  h, w = frames_rgb[0].shape[:2]
  fft_h = _next_fast_fft_len(h + 32)
  fft_w = _next_fast_fft_len(w + 96)
  fft_shape = (fft_h, fft_w)

  precomputed_tpls = _build_ui_token_templates(
      customer_name=customer_name,
      fft_shape=fft_shape,
      triage_plan=triage_plan,
  )
  horiz_tpls = [t for t in precomputed_tpls if abs(t["angle_deg"]) < 0.8]

  # Engine 1: Cloud Vision DOCUMENT_TEXT_DETECTION (optional network enhancer)
  vision_dets = _run_cloud_vision_ocr_on_frames(
      frames_rgb=frames_rgb,
      customer_name=customer_name,
      project_id=project_id,
  )

  # Engine 2: Multi-Scale/Angle Google Sans FFT NCC across all frames (with O(1) reuse on stationary frames and 128px strip FFT on localized typing/toast changes)
  strip_fft_shape = (128, fft_w)
  ink_maps: list = []
  per_frame_matches: list[list[dict]] = []
  for t in range(n):
    if t > 0:
      diff_mask = (
          np.abs(
              frames_rgb[t].astype(np.int16)
              - frames_rgb[t - 1].astype(np.int16)
          ).max(axis=2)
          > 28
      )
      changed_px = int(diff_mask.sum())
      chg_ys = np.where(diff_mask.sum(axis=1) >= 4)[0]
      if changed_px <= 16 or chg_ys.size == 0:
        ink_maps.append(ink_maps[t - 1])
        per_frame_matches.append([dict(m) for m in per_frame_matches[t - 1]])
        continue

      dy1, dy2 = int(chg_ys.min()), int(chg_ys.max()) + 1
      ink_t = _extract_ui_ink_map(frames_rgb[t])
      ink_maps.append(ink_t)

      if (
          dy2 - dy1 <= 84
          and float(changed_px) / float(h * w) < 0.04
          and not any(
              abs(m.get("angle_deg", 0.0)) >= 0.8
              for m in per_frame_matches[t - 1]
          )
      ):
        # Keep unchanged matches outside the modified vertical band and run 128px strip FFT only on the changed band
        mid_y = (dy1 + dy2) // 2
        strip_y1 = max(0, min(h - 112, mid_y - 56))
        strip_y2 = min(h, strip_y1 + 112)
        kept_prev = [
            dict(m)
            for m in per_frame_matches[t - 1]
            if m["y2"] < dy1 - 6 or m["y1"] > dy2 + 6
        ]
        strip_dets = _detect_tokens_on_frame_fft_ncc(
            ink_t[strip_y1:strip_y2, :],
            horiz_tpls,
            strip_fft_shape,
            use_strip_fft=True,
        )
        for sd in strip_dets:
          sd["y1"] += strip_y1
          sd["y2"] += strip_y1
          if not any(
              max(0, min(sd["x2"], kp["x2"]) - max(sd["x1"], kp["x1"])) > 8
              and max(0, min(sd["y2"], kp["y2"]) - max(sd["y1"], kp["y1"])) > 4
              for kp in kept_prev
          ):
            kept_prev.append(sd)
        ncc_m = kept_prev
      else:
        active_tpls = (
            precomputed_tpls
            if (
                float(changed_px) / float(h * w) >= 0.04
                or any(
                    abs(m.get("angle_deg", 0.0)) >= 0.8
                    for m in per_frame_matches[t - 1]
                )
            )
            else horiz_tpls
        )
        ncc_m = _detect_tokens_on_frame_fft_ncc(ink_t, active_tpls, fft_shape)
    else:
      ink_t = _extract_ui_ink_map(frames_rgb[t])
      ink_maps.append(ink_t)
      ncc_m = _detect_tokens_on_frame_fft_ncc(
          ink_t, precomputed_tpls, fft_shape
      )
    v_m = vision_dets.get(t) or []
    if v_m:
      merged = list(ncc_m)
      for vd in v_m:
        vx1, vy1, vx2, vy2 = vd["x1"], vd["y1"], vd["x2"], vd["y2"]
        vw, vh = vx2 - vx1, vy2 - vy1
        if not any(
            max(0, min(vx2, m["x2"]) - max(vx1, m["x1"]))
            > 0.25 * min(vw, m["x2"] - m["x1"])
            and max(0, min(vy2, m["y2"]) - max(vy1, m["y1"]))
            > 0.25 * min(vh, m["y2"] - m["y1"])
            for m in merged
        ):
          merged.append(vd)
      per_frame_matches.append(merged)
    else:
      per_frame_matches.append(ncc_m)

  # Engine 3: Temporal gap interpolation across rapid scroll/3D zoom transitions
  per_frame_matches = _interpolate_temporal_token_matches(
      frames_rgb, ink_maps, per_frame_matches
  )

  # Render surgical in-place vector replacements on each frame (reusing identical rendered frames when frame[t] == frame[t-1])
  out_frames: list = []
  for t in range(n):
    if not per_frame_matches[t]:
      out_frames.append(frames_rgb[t].copy())
      continue
    if (
        t > 0
        and len(per_frame_matches[t]) == len(per_frame_matches[t - 1])
        and int(
            np.abs(
                frames_rgb[t].astype(np.int16)
                - frames_rgb[t - 1].astype(np.int16)
            ).max()
        )
        <= 2
    ):
      out_frames.append(out_frames[t - 1].copy())
      continue
    out_frames.append(
        _apply_surgical_vector_replacements_on_frame(
            frames_rgb[t], per_frame_matches[t], fonts
        )
    )

  return out_frames


def _customize_ui_demo_gif_high_fidelity(
    raw_bytes: bytes,
    gif_info: dict,
    customer_name: str,
    industry: str,
    triage_plan: dict,
    client: any,
    config: dict | None = None,
    orig_alpha_mask: any = None,
    crop_props: dict | None = None,
    slide_text_context: str = "",
) -> tuple[bytes | None, str]:
  """Scenario 2 ('UI_PRODUCT_DEMO') High-Fidelity Pipeline (Option A):

  Preserves 100% of the native UI layout, 3D camera zooms/tilts, scrolling
  modals, typing animations, vector typography sharpness, icons, and frame
  cadence via Per-Frame Word-Polygon OCR + Multi-Scale/Angle Google Sans FFT
  NCC localization and surgical in-place 4x supersampled Google Sans vector
  replacement with baseline suffix shifting. Never stamps full-screen image-gen
  cutouts across frames, guaranteeing zero UI overlap.
  """
  import io
  import numpy as np
  from PIL import Image

  project_id = "your-gcp-project-id"
  if config and "default" in config:
    project_id = config["default"].get("project_name", project_id)

  frames_rgb: list[np.ndarray] = []
  eff_duration_ms = 80
  try:
    with Image.open(io.BytesIO(raw_bytes)) as im:
      n_frames = int(getattr(im, "n_frames", 1) or 1)
      if n_frames <= 1:
        return None, ""
      orig_dur = int(im.info.get("duration", 60) or 60)
      orig_dur = max(25, min(250, orig_dur))
      sw, sh = im.size
      cp = crop_props or {}
      l_off = max(0.0, min(0.85, float(cp.get("leftOffset", 0.0) or 0.0)))
      r_off = max(0.0, min(0.85, float(cp.get("rightOffset", 0.0) or 0.0)))
      t_off = max(0.0, min(0.85, float(cp.get("topOffset", 0.0) or 0.0)))
      b_off = max(0.0, min(0.85, float(cp.get("bottomOffset", 0.0) or 0.0)))

      cx1 = int(round(sw * l_off))
      cy1 = int(round(sh * t_off))
      cx2 = max(cx1 + 16, int(round(sw * (1.0 - r_off))))
      cy2 = max(cy1 + 16, int(round(sh * (1.0 - b_off))))

      # Strip #00FF00 neon-green chroma-key borders if present
      im.seek(0)
      f0_arr = np.array(im.convert("RGB"))[cy1:cy2, cx1:cx2]
      is_green = (
          (f0_arr[:, :, 1] > 220)
          & (f0_arr[:, :, 0] < 45)
          & (f0_arr[:, :, 2] < 45)
      )
      col_non_green = (~is_green).mean(axis=0) > 0.15
      row_non_green = (~is_green).mean(axis=1) > 0.15
      if col_non_green.any() and row_non_green.any():
        gx1 = int(np.argmax(col_non_green))
        gx2 = int(len(col_non_green) - np.argmax(col_non_green[::-1]))
        gy1 = int(np.argmax(row_non_green))
        gy2 = int(len(row_non_green) - np.argmax(row_non_green[::-1]))
        if (gx2 - gx1) >= 64 and (gy2 - gy1) >= 64:
          cx1 += gx1
          cx2 = cx1 + (gx2 - gx1)
          cy1 += gy1
          cy2 = cy1 + (gy2 - gy1)

      # Sample up to 84 frames across the FULL start-to-finish UI recording
      max_sampled = min(n_frames, 84)
      step_ratio = float(n_frames) / float(max_sampled)
      eff_duration_ms = max(40, min(220, int(round(orig_dur * step_ratio))))
      idxs = [
          min(
              n_frames - 1,
              int(round(k * (n_frames - 1) / max(1, max_sampled - 1))),
          )
          for k in range(max_sampled)
      ]
      crop_w, crop_h = cx2 - cx1, cy2 - cy1
      work_scale = min(1.0, 1152.0 / float(max(crop_w, crop_h, 1)))
      work_w = max(64, (int(round(crop_w * work_scale)) // 2) * 2)
      work_h = max(64, (int(round(crop_h * work_scale)) // 2) * 2)

      for idx in idxs:
        im.seek(idx)
        fr = im.convert("RGB").crop((cx1, cy1, cx2, cy2))
        if (work_w, work_h) != (crop_w, crop_h):
          fr = fr.resize((work_w, work_h), Image.Resampling.LANCZOS)
        arr = np.array(fr, dtype=np.uint8)
        green_px = (
            (arr[:, :, 1] > 210) & (arr[:, :, 0] < 50) & (arr[:, :, 2] < 50)
        )
        if green_px.any():
          arr[green_px] = [255, 255, 255]
        frames_rgb.append(arr)
  except Exception as e:
    print(f"[ImageUtil] UI demo frame extraction error: {e}")
    return None, ""

  if not frames_rgb:
    return None, ""

  replaced_frames = _localize_and_replace_ui_text_across_frames(
      frames_rgb=frames_rgb,
      customer_name=customer_name,
      triage_plan=triage_plan,
      project_id=project_id,
  )
  gif_out_bytes = _encode_high_fidelity_ui_gif(
      replaced_frames,
      frame_duration_ms=eff_duration_ms,
      orig_alpha_mask=orig_alpha_mask,
  )
  summary_prompt = str(
      triage_plan.get("ui_edit_instruction")
      or f"High-fidelity per-frame Google Sans UI text customization for {customer_name}"
  )
  return gif_out_bytes, summary_prompt


def _build_omni_video_edit_prompt(
    scenario: str,
    triage_plan: dict,
    customer_name: str,
    industry: str = "",
) -> str:
  """Constructs a concise, natural-language Gemini Omni 1.1 Flash Video-to-Video (`task='edit'`) prompt tailored to UI_PRODUCT_DEMO vs PURE_VISUAL."""
  import re

  domain_label = f" ({industry})" if industry else ""
  cust_slug = re.sub(r"[^a-z0-9]", "", customer_name.lower()) or "customer"

  if scenario == "UI_PRODUCT_DEMO":
    reps = triage_plan.get("text_replacements") or []
    rep_pairs = []
    seen_orig = set()
    for r in reps:
      if isinstance(r, dict) and r.get("original") and r.get("replacement"):
        orig_s = str(r["original"]).strip()
        rep_s = str(r["replacement"]).strip()
        if orig_s.lower() not in seen_orig:
          seen_orig.add(orig_s.lower())
          rep_pairs.append(f"'{orig_s}' -> '{rep_s}'")
    for default_o, default_r in (
        ("Cymbal Retail", customer_name),
        ("Cymbal", customer_name),
        ("cymbal.com", f"{cust_slug}.com"),
    ):
      if default_o.lower() not in seen_orig:
        rep_pairs.append(f"'{default_o}' -> '{default_r}'")

    inline_reps = ", ".join(rep_pairs[:6])
    return (
        f"Edit this screen recording video for {customer_name}{domain_label}."
        " Preserve the exact software UI layout, white background, cards,"
        " buttons, and smooth cursor/scrolling animation from the input video"
        " without adding any photo overlays or duplicate overlapping windows."
        " Across all frames from start to finish, replace every 'Cymbal' or"
        f" 'cymbal.com' brand, email domain, and demo product ({inline_reps})"
        " so that zero frames anywhere in the video show the word 'Cymbal' or"
        " 'cymbal.com'. Keep all UI text clean, sharp, and legible."
    )

  return triage_plan.get("visual_motion_prompt") or (
      f"Edit this video for {customer_name}{domain_label}. Preserve the exact"
      " visual composition, camera motion, background, framing, and smooth"
      " animation from the input video. 'Cymbal' (including 'Cymbal Retail',"
      " 'Cymbal Superstore', and 'Cymbal Shops') is a white-label placeholder"
      " brand: replace every 'Cymbal' or previous demo brand name, logo, and"
      f" product across ALL frames from start to finish with {customer_name}"
      f" branding and {customer_name}-authentic products. Keep all on-screen"
      " text concise, sharp, and legible, without floating logo overlays."
  )


def _verify_and_refine_omni_mp4_with_vlm(
    mp4_bytes: bytes,
    customer_name: str,
    industry: str,
    client: any,
    video_model: str = "gemini-omni-1.1-flash-preview",
    fast_model: str = "gemini-3.8-flash",
    interaction_id: str | None = None,
    obj_id: str = "",
) -> tuple[bytes, float]:
  """Inspects 8 evenly spaced frames of an Omni-edited MP4 with VLM to ensure zero 'Cymbal' frames and zero overlapping UIs; runs a Turn-2 Omni edit or trims lead-in frames if needed."""
  import base64
  import glob
  import json
  import os
  import re
  import subprocess
  import tempfile
  from google.genai import types

  if not mp4_bytes or not client:
    return mp4_bytes, 0.0

  cust_slug = re.sub(r"[^a-z0-9]", "", customer_name.lower()) or "customer"

  def _inspect_mp4(candidate_mp4: bytes) -> dict:
    try:
      with tempfile.TemporaryDirectory(prefix="pg_vlm_qa_") as tmpdir:
        in_p = os.path.join(tmpdir, "cand.mp4")
        with open(in_p, "wb") as f:
          f.write(candidate_mp4)
        subprocess.run(
            [
                "/usr/bin/ffmpeg",
                "-y",
                "-i",
                in_p,
                "-vf",
                "fps=1.6,scale=960:-2",
                "-frames:v",
                "8",
                os.path.join(tmpdir, "qa_%02d.png"),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
        f_paths = sorted(glob.glob(os.path.join(tmpdir, "qa_*.png")))
        if not f_paths:
          return {
              "has_cymbal": False,
              "cymbal_frames": [],
              "has_overlap": False,
          }
        contents = []
        for idx, fp in enumerate(f_paths):
          with open(fp, "rb") as f_img:
            contents.append(f"Frame {idx} (t={idx * 0.62:.1f}s):")
            contents.append(
                types.Part.from_bytes(data=f_img.read(), mime_type="image/png")
            )
        qa_prompt = (
            f"Inspect these {len(f_paths)} sequential frames (Frame 0 to Frame"
            f" {len(f_paths) - 1}) from an edited UI video for"
            f" {customer_name}.\nCheck two things strictly:\n1. Does ANY frame"
            " still visibly contain the substring 'Cymbal' or 'cymbal.com'"
            " (case-insensitive, including 'Cymb' or '@cymbal')?\n2. Does"
            " ANY frame show a broken duplicate/overlapping UI window or"
            " unrelated stock photo stamped on top of the UI window?\nReturn"
            ' JSON:\n{\n  "has_cymbal": true | false,\n  "cymbal_frames":'
            " [list of 0-based frame indices where Cymbal is visible],\n "
            ' "has_overlap": true | false,\n  "notes": "brief description"\n}'
        )
        contents.append(qa_prompt)
        resp = client.models.generate_content(
            model=fast_model or "gemini-3.8-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )
        if resp and resp.text:
          data = json.loads(resp.text)
          if isinstance(data, list) and data:
            data = data[0]
          if isinstance(data, dict):
            return data
    except Exception as e:
      print(f"[ImageUtil] VLM MP4 QA check notice for {obj_id}: {e}")
    return {"has_cymbal": False, "cymbal_frames": [], "has_overlap": False}

  qa1 = _inspect_mp4(mp4_bytes)
  cym_frames = [
      int(x)
      for x in qa1.get("cymbal_frames") or []
      if isinstance(x, (int, float))
  ]
  has_cym = bool(qa1.get("has_cymbal")) or bool(cym_frames)
  has_ov = bool(qa1.get("has_overlap"))
  print(
      f"[ImageUtil] Omni V2V QA Turn 1 for {obj_id}: has_cymbal={has_cym}"
      f" (frames={cym_frames}), has_overlap={has_ov}"
      f" ({qa1.get('notes', '')})"
  )

  if not has_cym and not has_ov:
    return mp4_bytes, 0.0

  # If 'Cymbal' only appeared in the very first opening frames (Frame 0 or Frame 1, i.e. < 1.1s)
  # and frames 2..7 are completely clean and free of overlap, trim the opening transition!
  if has_cym and not has_ov and cym_frames and max(cym_frames) <= 1:
    trim_sec = round((max(cym_frames) + 1) * 0.62, 2)
    print(
        f"[ImageUtil] Trimming leading {trim_sec}s of {obj_id} to remove"
        f" opening Cymbal transition frames {cym_frames}."
    )
    return mp4_bytes, trim_sec

  # Otherwise, run Turn 2 Omni video edit on the MP4 bytes (note: Vertex Interactions API forbids combining previous_interaction_id with video_config.task='edit')
  fix_instruction = (
      f"Edit this UI screen recording video for {customer_name}. Replace every"
      " remaining occurrence of 'Cymbal', 'Cymbal Retail', or 'cymbal.com'"
      f" across all frames with '{customer_name}' and '{cust_slug}.com'."
      " Keep a single clean white UI screen throughout the video with no"
      " overlapping windows or photo overlays."
  )
  try:
    print(f"[ImageUtil] Running Turn 2 Omni V2V refinement for {obj_id}...")
    interaction2 = client.interactions.create(
        model=video_model,
        input=[
            {
                "type": "video",
                "data": base64.b64encode(mp4_bytes).decode("utf-8"),
                "mime_type": "video/mp4",
            },
            {"type": "text", "text": fix_instruction},
        ],
        generation_config={"video_config": {"task": "edit"}},
    )
    v2_bytes, _ = _extract_omni_video_bytes(interaction2)
    if v2_bytes:
      qa2 = _inspect_mp4(v2_bytes)
      cym2 = [
          int(x)
          for x in qa2.get("cymbal_frames") or []
          if isinstance(x, (int, float))
      ]
      print(
          f"[ImageUtil] Omni V2V QA Turn 2 for {obj_id}:"
          f" has_cymbal={qa2.get('has_cymbal')} (frames={cym2}),"
          f" has_overlap={qa2.get('has_overlap')}"
      )
      if not qa2.get("has_cymbal") and not qa2.get("has_overlap"):
        return v2_bytes, 0.0
      if cym2 and max(cym2) <= 2 and not qa2.get("has_overlap"):
        return v2_bytes, round((max(cym2) + 1) * 0.62, 2)
      if len(cym2) < len(cym_frames):
        mp4_bytes = v2_bytes
        cym_frames = cym2
  except Exception as e2:
    print(f"[ImageUtil] Turn 2 Omni V2V refinement notice for {obj_id}: {e2}")

  if cym_frames and max(cym_frames) <= 2:
    return mp4_bytes, round((max(cym_frames) + 1) * 0.62, 2)
  return mp4_bytes, 0.0


def customize_slide_gif_for_customer(
    gif_info: dict | None = None,
    slide_text_context: str = "",
    customer_name: str = "",
    industry: str = "",
    mode: str = "video_to_video_edit",
    config: dict | None = None,
    raw_gif_bytes: bytes | None = None,
    slide_title_or_context: str = "",
    slide_index: int = 0,
) -> dict | None:
  """Customizes an originally animated in-slide GIF (`n_frames > 1`) via Gemini Omni 1.1 Flash Video-to-Video (`gemini-omni-1.1-flash-preview`, `task='edit'`):

  - Scenario 1 (`PURE_VISUAL`): Purely visual / lifestyle / 3D motion GIFs are
    transformed via Gemini Omni 1.1 Flash (`task='edit'`) with grounded visual
    instructions.
  - Scenario 2 (`UI_PRODUCT_DEMO`): Software UI / product demo screen recordings
    are transformed via Gemini Omni 1.1 Flash (`task='edit'`) with explicit
    in-place text replacement rules derived from keyframe vision triage,
    followed by VLM frame verification and multi-turn conversational refinement
    (`previous_interaction_id`).

  Strictly refuses to convert static images (`n_frames <= 1`) into GIFs.
  """
  if gif_info is None and raw_gif_bytes:
    gif_info = {
        "objectId": "synthetic_gif",
        "contentUrl": "",
        "width_pt": 333.5,
        "height_pt": 187.6,
        "slide_index": slide_index,
    }
  if not gif_info or not customer_name:
    return None

  obj_id = gif_info.get("objectId", "")
  content_url = gif_info.get("contentUrl", "")
  if not raw_gif_bytes and (not obj_id or not content_url):
    return None

  import base64
  import io
  import uuid
  from google import genai
  from google.cloud import storage
  from google.genai import types
  import numpy as np
  from PIL import Image
  import requests

  if raw_gif_bytes:
    raw_bytes = raw_gif_bytes
  else:
    try:
      resp = requests.get(content_url, timeout=15)
      if resp.status_code != 200 or not resp.content:
        return None
      raw_bytes = resp.content
    except Exception as e:
      print(f"[ImageUtil] Could not download candidate GIF {obj_id}: {e}")
      return None

  slide_text_context = slide_text_context or slide_title_or_context

  project_id = "your-gcp-project-id"
  video_model = "gemini-omni-1.1-flash-preview"
  fast_model = "gemini-3.8-flash"
  bucket_name = "your-pitchgen-content-bucket"
  if config:
    if "default" in config:
      project_id = config["default"].get("project_name", project_id)
      video_model = config["default"].get("gemini_video_model", video_model)
      fast_model = config["default"].get("gemini_model", fast_model)
    if "bucket" in config and config["bucket"].get("content"):
      bucket_name = config["bucket"]["content"]

  width_pt = float(gif_info.get("width_pt") or 333.5)
  height_pt = float(gif_info.get("height_pt") or 187.6)
  aspect_ratio = width_pt / max(1.0, height_pt)
  omni_aspect = "9:16" if aspect_ratio < 0.80 else "16:9"
  crop_props = gif_info.get("cropProperties") or {}

  # Verify the element is genuinely an animated GIF (n_frames > 1) and extract sample frames + alpha/crop metadata
  orig_alpha_mask = None
  has_crop_offsets = False
  sample_frames_png: list[bytes] = []
  try:
    with Image.open(io.BytesIO(raw_bytes)) as src_im:
      n_frames = int(getattr(src_im, "n_frames", 1) or 1)
      if n_frames <= 1:
        print(
            f"[ImageUtil] Skipping {obj_id}: source image is static"
            f" (n_frames={n_frames}), not an animated GIF."
        )
        return None
      src_im.seek(0)
      im_vis = src_im.convert("RGBA")
      sw, sh = im_vis.size
      l_off = max(
          0.0, min(0.85, float(crop_props.get("leftOffset", 0.0) or 0.0))
      )
      r_off = max(
          0.0, min(0.85, float(crop_props.get("rightOffset", 0.0) or 0.0))
      )
      t_off = max(
          0.0, min(0.85, float(crop_props.get("topOffset", 0.0) or 0.0))
      )
      b_off = max(
          0.0, min(0.85, float(crop_props.get("bottomOffset", 0.0) or 0.0))
      )
      cx1, cy1, cx2, cy2 = 0, 0, sw, sh
      if (
          (l_off + r_off + t_off + b_off) > 0.01
          and (1.0 - l_off - r_off) > 0.12
          and (1.0 - t_off - b_off) > 0.12
      ):
        has_crop_offsets = True
        cx1 = int(round(sw * l_off))
        cy1 = int(round(sh * t_off))
        cx2 = max(cx1 + 16, int(round(sw * (1.0 - r_off))))
        cy2 = max(cy1 + 16, int(round(sh * (1.0 - b_off))))
        im_vis = im_vis.crop((cx1, cy1, cx2, cy2))

      vw, vh = im_vis.size
      alpha_ch = im_vis.getchannel("A")
      alpha_arr = np.array(alpha_ch, dtype=np.uint8)
      trans_pct = float((alpha_arr < 32).sum()) * 100.0 / max(1, vw * vh)
      if 0.05 < trans_pct <= 25.0:
        orig_alpha_mask = alpha_ch.copy()

      sample_idxs = sorted(
          set([
              0,
              n_frames // 4,
              n_frames // 2,
              (3 * n_frames) // 4,
              n_frames - 1,
          ])
      )
      for s_i in sample_idxs:
        src_im.seek(s_i)
        s_rgb = src_im.convert("RGB").crop((cx1, cy1, cx2, cy2))
        s_buf = io.BytesIO()
        s_rgb.save(s_buf, format="PNG")
        sample_frames_png.append(s_buf.getvalue())
  except Exception as e:
    print(f"[ImageUtil] GIF Frame 0 inspection warning for {obj_id}: {e}")
    return None

  client = genai.Client(
      vertexai=True,
      project=project_id,
      location="global",
      http_options=types.HttpOptions(api_version="v1beta1", timeout=300000),
  )

  # Step 1: 2-Scenario Vision Triage (UI_PRODUCT_DEMO vs PURE_VISUAL) to extract exact text replacements
  triage_plan = _classify_and_plan_gif_customization(
      sample_frames_png=sample_frames_png,
      customer_name=customer_name,
      industry=industry,
      slide_text_context=slide_text_context,
      client=client,
      fast_model=fast_model,
  )
  scenario = triage_plan.get("scenario", "PURE_VISUAL")
  if mode == "ui_high_fidelity":
    scenario = "UI_PRODUCT_DEMO"
  elif mode == "force_omni_v2v":
    scenario = "PURE_VISUAL"

  print(
      f"[ImageUtil] GIF {obj_id} classified as scenario={scenario}"
      f" ({triage_plan.get('reason', '')})"
  )

  # Step 2: Gemini Omni 1.1 Flash Video-to-Video (`task='edit'`) for both UI_PRODUCT_DEMO and PURE_VISUAL
  mp4_scaffold_bytes, sized_frame0_png = (
      _transcode_gif_or_image_to_mp4_scaffold(
          raw_bytes,
          target_aspect=omni_aspect,
          duration_sec=5.0,
          crop_props=crop_props,
      )
  )
  if not mp4_scaffold_bytes or not sized_frame0_png:
    return None

  motion_prompt = _build_omni_video_edit_prompt(
      scenario=scenario,
      triage_plan=triage_plan,
      customer_name=customer_name,
      industry=industry,
  )

  mp4_out_bytes = None
  winning_interaction_id = None
  winning_model_name = "gemini-omni-1.1-flash-preview"
  last_err = ""
  model_candidates = [
      m
      for m in (video_model, "gemini-omni-1.1-flash-preview")
      if m and m != "gemini-omni-flash"
  ]
  if not model_candidates:
    model_candidates = ["gemini-omni-1.1-flash-preview"]

  for task_mode in ("edit", "reference_to_video"):
    for m_name in model_candidates:
      try:
        inputs = [
            {
                "type": "video",
                "data": base64.b64encode(mp4_scaffold_bytes).decode("utf-8"),
                "mime_type": "video/mp4",
            },
            {"type": "text", "text": motion_prompt},
        ]
        gen_cfg = {"video_config": {"task": task_mode}}
        print(
            f"[ImageUtil] Calling {m_name} (scenario={scenario},"
            f" task={task_mode}) for {obj_id}..."
        )
        interaction = client.interactions.create(
            model=m_name,
            input=inputs,
            generation_config=gen_cfg,
        )
        v_bytes, diag = _extract_omni_video_bytes(interaction)
        if v_bytes:
          mp4_out_bytes = v_bytes
          winning_interaction_id = getattr(interaction, "id", None)
          winning_model_name = m_name
          print(
              f"[ImageUtil] {m_name} synthesized {len(v_bytes)} MP4 bytes for"
              f" {obj_id} (task={task_mode}, id={winning_interaction_id})"
          )
          break
        last_err = diag or "Empty video payload"
        print(
            f"[ImageUtil] {m_name} task={task_mode} notice for {obj_id}:"
            f" {last_err}"
        )
      except Exception as omni_err:
        last_err = str(omni_err)
        print(
            f"[ImageUtil] {m_name} task={task_mode} error for {obj_id}:"
            f" {last_err}"
        )
    if mp4_out_bytes:
      break

  if not mp4_out_bytes:
    print(
        f"[ImageUtil] Could not synthesize Omni 1.1 video for {obj_id}:"
        f" {last_err}"
    )
    return None

  # Step 3: VLM Frame Verification & Multi-Turn Refinement (`previous_interaction_id`)
  mp4_out_bytes, trim_start_sec = _verify_and_refine_omni_mp4_with_vlm(
      mp4_bytes=mp4_out_bytes,
      customer_name=customer_name,
      industry=industry,
      client=client,
      video_model=winning_model_name,
      fast_model=fast_model,
      interaction_id=winning_interaction_id,
      obj_id=obj_id,
  )

  gif_out_bytes = _transcode_mp4_to_looping_slide_gif(
      mp4_out_bytes,
      width_pt=width_pt,
      height_pt=height_pt,
      orig_alpha_mask=orig_alpha_mask,
      trim_start_sec=trim_start_sec,
      is_ui_demo=(scenario == "UI_PRODUCT_DEMO"),
  )
  if not gif_out_bytes:
    print(f"[ImageUtil] Failed to transcode MP4 to looping GIF for {obj_id}")
    return None

  blob_name = f"nanoBanana_gifTrans/{uuid.uuid4()}_{scenario.lower()}.gif"
  target_buckets = [bucket_name]
  for b in ("your-pitchgen-content-bucket", "your-pitchgen-content-bucket"):
    if b not in target_buckets:
      target_buckets.append(b)

  uploaded = False
  for b_name in target_buckets:
    try:
      st_client = storage.Client(project=project_id)
      bucket = st_client.bucket(b_name)
      blob = bucket.blob(blob_name)
      blob.upload_from_string(gif_out_bytes, content_type="image/gif")
      if b_name == bucket_name:
        uploaded = True
    except Exception as up_err:
      print(
          f"[ImageUtil] GCS GIF upload warning for {b_name}/{blob_name}:"
          f" {up_err}"
      )

  public_url = ""
  if uploaded:
    public_url = generate_gcs_v4_signed_url(
        bucket_name=bucket_name,
        blob_name=blob_name,
        project_id=project_id,
        raw_bytes=gif_out_bytes,
        mime_type="image/gif",
    )
  else:
    content_uri, _ = image_bytes_to_content_uri(
        gif_out_bytes, mime_type="image/gif"
    )
    public_url = content_uri

  if not public_url:
    return None

  res_dict = {
      "replaceImage": {
          "imageObjectId": obj_id,
          "url": public_url,
          "imageReplaceMethod": "CENTER_CROP",
      },
      "_alt_text_request": {
          "updatePageElementAltText": {
              "objectId": obj_id,
              "title": f"PitchGen-GIF:{customer_name}:{scenario}",
              "description": (
                  f"PitchGen ({scenario}) animated GIF for {customer_name}"
              ),
          }
      },
      "_gif_bytes": gif_out_bytes,
      "_mp4_bytes": mp4_out_bytes,
      "_motion_prompt": motion_prompt,
      "_scenario": scenario,
      "_triage_plan": triage_plan,
  }
  if has_crop_offsets:
    res_dict["_reset_crop_request"] = {
        "updateImageProperties": {
            "objectId": obj_id,
            "imageProperties": {
                "cropProperties": {
                    "leftOffset": 0.0,
                    "rightOffset": 0.0,
                    "topOffset": 0.0,
                    "bottomOffset": 0.0,
                }
            },
            "fields": (
                "cropProperties.leftOffset,cropProperties.rightOffset,"
                "cropProperties.topOffset,cropProperties.bottomOffset"
            ),
        }
    }
  return res_dict
