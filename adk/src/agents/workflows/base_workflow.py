"""Base skill definition with fallback model calling capabilities."""

import abc
import json


class BaseWorkflow(abc.ABC):
  """Abstract base class for all PitchGen Multi-Agent skills."""

  def __init__(self, name, description):
    self.name = name
    self.description = description

  @abc.abstractmethod
  def execute(self, *args, **kwargs):
    pass

  def extract_text(self, response) -> str:
    """Safely extracts text from a Gemini response, handling None, candidates, and parts."""
    if not response:
      return ""
    # Try direct response.text
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
      return text.strip()
    # Fallback to inspect candidates and parts
    candidates = getattr(response, "candidates", None)
    if candidates:
      candidate = candidates[0]
      content = getattr(candidate, "content", None)
      parts = getattr(content, "parts", None) if content else None
      if parts:
        extracted = "".join(
            str(getattr(part, "text", ""))
            for part in parts
            if getattr(part, "text", None)
        ).strip()
        if extracted:
          return extracted
    return ""

  def extract_json(self, response, default=None):
    """Safely parses JSON from a Gemini response with fallback handling."""
    text = self.extract_text(response)
    if not text:
      if default is not None:
        return default
      raise ValueError(f"[{self.name}] Empty response text received from model.")

    # Strip markdown code blocks if present
    cleaned = text
    if "```json" in cleaned:
      cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in cleaned:
      cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()

    try:
      return json.loads(cleaned)
    except Exception as e:
      if default is not None:
        print(f"[{self.name}] JSON parse failed ({e}), using default.")
        return default
      raise e

  def generate_content_with_fallback(
      self,
      client,
      model,
      contents,
      config,
      fallback_model=None,
  ):
    """Generates content using the primary model with 429 backoff, falling back to fallback_model if needed."""
    import copy
    import random
    import time

    is_mock = hasattr(client, "assert_called") or hasattr(
        getattr(client, "models", None), "assert_called"
    )
    max_attempts = 1 if is_mock else 3

    last_err = None
    for attempt in range(max_attempts):
      try:
        print(f"[{self.name}] Calling model {model}...")
        return client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
      except Exception as e:  # pylint: disable=broad-exception-caught
        last_err = e
        err_low = str(e).lower()
        is_429 = (
            "429" in err_low
            or "resource_exhausted" in err_low
            or "rate limit" in err_low
            or "quota" in err_low
        )
        if is_429 and attempt < max_attempts - 1:
          sleep_s = (1.6 ** attempt) + random.uniform(0.25, 0.9)
          print(
              f"[{self.name}] Rate limit (429) on {model}, retrying in"
              f" {sleep_s:.2f}s (attempt {attempt + 1}/{max_attempts})..."
          )
          time.sleep(sleep_s)
        elif ("400" in err_low or "invalid_argument" in err_low) and getattr(
            config, "tools", None
        ):
          print(
              f"[{self.name}] Model {model} rejected tools config (400);"
              " retrying without tools..."
          )
          no_tools_cfg = copy.copy(config)
          no_tools_cfg.tools = None
          try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=no_tools_cfg,
            )
          except Exception as retry_err:  # pylint: disable=broad-exception-caught
            last_err = retry_err
            break
        else:
          break

    if fallback_model and str(fallback_model) != str(model):
      print(
          f"[{self.name}] Primary model {model} failed: {last_err}. Retrying"
          f" with fallback model {fallback_model}..."
      )
      fb_config = copy.copy(config) if config is not None else None
      if (
          fb_config is not None
          and hasattr(fb_config, "thinking_config")
          and fb_config.thinking_config
          and "3.8" not in str(fallback_model)
      ):
        fb_config.thinking_config = None
      if (
          fb_config is not None
          and getattr(fb_config, "tools", None)
          and "flash-image" not in str(fallback_model)
      ):
        fb_config.tools = None
      for fb_attempt in range(max_attempts):
        try:
          return client.models.generate_content(
              model=fallback_model,
              contents=contents,
              config=fb_config,
          )
        except Exception as fb_err:  # pylint: disable=broad-exception-caught
          last_err = fb_err
          err_low = str(fb_err).lower()
          is_429 = (
              "429" in err_low
              or "resource_exhausted" in err_low
              or "rate limit" in err_low
              or "quota" in err_low
          )
          if is_429 and fb_attempt < max_attempts - 1:
            sleep_s = (1.6 ** fb_attempt) + random.uniform(0.25, 0.9)
            print(
                f"[{self.name}] Rate limit (429) on fallback {fallback_model},"
                f" retrying in {sleep_s:.2f}s"
                f" (attempt {fb_attempt + 1}/{max_attempts})..."
            )
            time.sleep(sleep_s)
          else:
            raise fb_err
    raise last_err
