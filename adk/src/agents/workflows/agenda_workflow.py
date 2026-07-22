import json
import os
from google import genai
from google.genai import types
from agents.workflows.base_workflow import BaseWorkflow


class AgendaWorkflow(BaseWorkflow):

  def __init__(self, config):
    super().__init__(
        'AgendaWorkflow',
        'Converts a structured outline into presentation agendas.',
    )
    self.config = config
    self.project_id = config['default']['project_name']
    self.gemini_model = config['default']['gemini_model_1']

  def execute(self, outline_data):
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'prompt_templates',
        'outlineToAgendas.txt',
    )
    with open(prompt_path, 'r') as f:
      agendas_prompt = f.read()

    client = genai.Client(
        vertexai=True, project=self.project_id, location='global'
    )

    industry = outline_data.get('industry', '')
    # Mapping logic (simplified from main.py)
    agendas_inp = {
        'customer': outline_data.get('customer_name', ''),
        'audience': ', '.join(outline_data.get('audience', [])),
        'industry': industry,
        'outline_items': outline_data.get('outline', []),
    }

    response = client.models.generate_content(
        model=self.gemini_model,
        contents=[agendas_prompt, json.dumps(agendas_inp), '\n[output]\n'],
        config=types.GenerateContentConfig(
            system_instruction='Please provide output in json format.',
            response_mime_type='application/json',
            temperature=0,
        ),
    )

    agenda_struct = json.loads(response.text)
    return agenda_struct.get('agendas', {})
