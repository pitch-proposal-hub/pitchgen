"""Base skill definition with fallback model calling capabilities."""

from abc import ABC, abstractmethod


class BaseWorkflow(ABC):
  """Abstract base class for all PitchGen Multi-Agent skills."""

  def __init__(self, name, description):
    self.name = name
    self.description = description

  @abstractmethod
  def execute(self, *args, **kwargs):
    pass

  def generate_content_with_fallback(
      self,
      client,
      model,
      contents,
      config,
      fallback_model=None,
  ):
    """Generates content using the primary model, falling back if needed."""
    try:
      print(f"[{self.name}] Calling model {model}...")
      return client.models.generate_content(
          model=model,
          contents=contents,
          config=config,
      )
    except Exception as e:  # pylint: disable=broad-exception-caught
      if fallback_model:
        print(
            f"[{self.name}] Primary model {model} failed: {e}. Retrying with"
            f" fallback model {fallback_model}..."
        )
        return client.models.generate_content(
            model=fallback_model,
            contents=contents,
            config=config,
        )
      else:
        raise e
