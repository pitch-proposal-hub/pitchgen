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
