from google import genai
from google.genai import types
from agents.workflows.base_workflow import BaseWorkflow


class TextTransformerWorkflow(BaseWorkflow):

  def __init__(self, config):
    super().__init__(
        'TextTransformerWorkflow',
        'Polishes/transforms text based on specific criteria.',
    )
    self.config = config
    self.project_id = config['default'].get('project_name', os.getenv("GOOGLE_CLOUD_PROJECT", "YOUR_PROJECT_ID"))
    self.gemini_model = config['default'].get(
        'gemini_model',
        config['default'].get('gemini_model_1', 'gemini-3.1-flash-lite'),
    )
    self.region = config['default'].get('region', 'global')

  def execute(self, text, criteria='Improve clarity and professional tone'):
    """Transforms text based on edit/polishing criteria."""
    if not text or not text.strip():
      return text

    client = genai.Client(
        vertexai=True, project=self.project_id, location=self.region
    )

    original_len = len(text)
    prompt = (
        'You are a professional copywriter. Polish and transform the following'
        f" text according to these criteria: '{criteria}'.\n"
        "CRITICAL CONSTRAINT: The transformed text MUST be approximately the same length as the original text. "
        f"Aim for around {original_len} characters (within a strict margin of +/- 10%). "
        "Do not expand or truncate the content significantly. "
        "Preserve formatting and key terms but optimize the wording and tone for a professional presentation. "
        "Return ONLY the modified text, with no preamble, quotes, or conversational responses.\n\n"
        f"Original Text: {text}"
    )

    try:
      response = client.models.generate_content(
          model=self.gemini_model,
          contents=[prompt],
          config=types.GenerateContentConfig(
              temperature=0.2,
          ),
      )
      return response.text.strip()
    except Exception as e:
      print(f'[TextTransformerWorkflow] Gemini call failed: {e}')
      return text
