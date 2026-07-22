from agents.workflows.base_workflow import BaseWorkflow


class SlideAssemblyWorkflow(BaseWorkflow):

  def __init__(self, config):
    super().__init__(
        "SlideAssemblyWorkflow", "Assembles final slide content and status."
    )
    self.config = config

  def execute(self, content, status="success"):
    """Assembles the output dictionary for the transformation request."""
    return {"content": content, "status": status}
