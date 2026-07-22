from agents.base_agent import BaseAgent
from agents.workflows.agenda_workflow import AgendaWorkflow
from agents.workflows.outline_workflow import OutlineWorkflow


class AgendaAgent(BaseAgent):

  def __init__(self, config):
    super().__init__(
        "AgendaAgent",
        "Responsible for generating outlines and converting them to agendas.",
    )
    self.add_skill("outline", OutlineWorkflow(config))
    self.add_skill("agenda", AgendaWorkflow(config))

  def run(self, global_state):
    print(f"[{self.name}] Starting narrative strategy...")

    # 1. Generate Outline
    outline = self.skills["outline"].execute(global_state.context)
    global_state.outline = outline

    # 2. Generate Agendas
    agendas = self.skills["agenda"].execute(outline)
    global_state.agendas = agendas

    print(f"[{self.name}] Narrative strategy completed.")
    return global_state
