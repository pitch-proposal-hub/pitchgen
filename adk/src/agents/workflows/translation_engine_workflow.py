from google import genai
from google.genai import types
from agents.workflows.base_workflow import BaseWorkflow


class TranslationEngineWorkflow(BaseWorkflow):

  def __init__(self, config):
    super().__init__(
        'TranslationEngineWorkflow', 'Translates text to a target language.'
    )
    self.config = config
    self.project_id = config['default'].get('project_name', os.getenv("GOOGLE_CLOUD_PROJECT", "YOUR_PROJECT_ID"))
    self.gemini_model = config['default'].get(
        'gemini_model',
        config['default'].get('gemini_model_1', 'gemini-3.1-flash-lite'),
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
      return response.text.strip()
    except Exception as e:
      print(f'[TranslationEngineWorkflow] Gemini call failed: {e}')
      return text
