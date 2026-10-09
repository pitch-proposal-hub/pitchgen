from google import genai
from google.genai import types
from agents.workflows.base_workflow import BaseWorkflow


class TranslationEngineWorkflow(BaseWorkflow):

  def __init__(self, config):
    super().__init__(
        'TranslationEngineWorkflow', 'Translates text to a target language.'
    )
    self.config = config
    self.project_id = config['default'].get('project_name', 'your-gcp-project-id')
    self.gemini_model = config['default'].get(
        'gemini_model',
        config['default'].get('gemini_model_1', 'gemini-3.5-flash-lite'),
    )
    self.region = 'global'


  def execute(self, text, target_language='German'):
    """Translates text to target language using Gemini."""
    if not text or not text.strip():
      return text

    client = genai.Client(
        vertexai=True, project=self.project_id, location=self.region
    )

    prompt = (
        'You are an expert translator. Translate the following text into'
        f' {target_language}. Ensure that the professional business tone is'
        ' preserved. Return ONLY the translated text, with no preamble,'
        f' quotes, or explanations.\n\nText: {text}'
    )

    try:
      response = client.models.generate_content(
          model=self.gemini_model,
          contents=[prompt],
          config=types.GenerateContentConfig(
              temperature=0.1,
          ),
      )
      res_text = getattr(response, 'text', None)
      if isinstance(res_text, str) and res_text.strip():
        return res_text.strip()
      if response and response.candidates:
        candidate = response.candidates[0]
        content = getattr(candidate, 'content', None)
        parts = getattr(content, 'parts', None) if content else None
        if parts:
          parts_text = ''.join(
              str(getattr(p, 'text', ''))
              for p in parts
              if getattr(p, 'text', None)
          )
          if parts_text.strip():
            return parts_text.strip()
      return text
    except Exception as e:
      print(f'[TranslationEngineWorkflow] Gemini call failed: {e}')
      return text
