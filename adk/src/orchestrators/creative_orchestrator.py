from agents.slide_engineering_agent import SlideEngineeringAgent
from agents.visual_agent import VisualAgent


class CreativeOrchestrator:

  def __init__(self, config):
    self.config = config
    self.slide_agent = SlideEngineeringAgent(config)
    self.visual_agent = VisualAgent(config)

  def run(self, global_state):
    print("[CreativeOrchestrator] Initializing Creative Phase...")

    # 1. Slide Engineering Agent (Content + Mapping)
    global_state = self.slide_agent.run(global_state)

    # 2. Visual Agent (Parallel in theory, sequential here for simplicity)
    global_state = self.visual_agent.run(global_state)

    print("[CreativeOrchestrator] Creative Phase Completed.")
    return global_state
