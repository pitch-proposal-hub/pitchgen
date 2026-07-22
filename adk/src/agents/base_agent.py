from abc import ABC, abstractmethod


class BaseAgent(ABC):

  def __init__(self, name, description):
    self.name = name
    self.description = description
    self.skills = {}

  def add_skill(self, skill_name, skill_instance):
    self.skills[skill_name] = skill_instance

  @abstractmethod
  def run(self, input_data):
    pass
