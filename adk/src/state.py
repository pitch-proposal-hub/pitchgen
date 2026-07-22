import json


class GlobalState:

  def __init__(self):
    self.context = {}
    self.outline = None
    self.agendas = None
    self.reusable_slides = None
    self.generated_content = None
    self.final_deck_structure = None

  def to_json(self):
    self._normalize()
    return json.dumps(self.__dict__, indent=2)

  def _normalize(self):
    # Normalize outline if it is a list
    if isinstance(self.outline, list):
      print("[GlobalState] Normalizing outline list to expected dictionary structure...")
      self.outline = {
          "title": "Outline",
          "outline": self.outline
      }
    
    # Normalize agendas if it is a list
    if isinstance(self.agendas, list):
      print("[GlobalState] Normalizing agendas list to expected dictionary structure...")
      agendas_dict = {}
      for idx, agenda in enumerate(self.agendas):
        agendas_dict[str(idx + 1)] = agenda
      self.agendas = agendas_dict

  @classmethod
  def from_json(cls, json_str):
    data = json.loads(json_str)
    if isinstance(data, dict) and "Status" in data and "data" in data:
      data = data["data"]
    state = cls()
    state.__dict__.update(data)
    state._normalize()
    return state

