# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging
import os
from typing import Any

try:
  import vertexai
  from vertexai.agent_engines.templates.adk import AdkApp
except ImportError:
  from google.cloud.aiplatform import vertexai
  from google.cloud.aiplatform.vertexai.agent_engines.templates.adk import AdkApp

from dotenv import load_dotenv
from google.adk.artifacts.gcs_artifact_service import GcsArtifactService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.cloud import logging as google_cloud_logging

import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
print(f"DEBUG_ENV: sys.path={sys.path}", file=sys.stderr)
print(f"DEBUG_ENV: current_dir={current_dir}", file=sys.stderr)
try:
    print(f"DEBUG_ENV: files in current_dir={os.listdir(current_dir)}", file=sys.stderr)
except Exception as e:
    print(f"DEBUG_ENV: failed to list current_dir: {e}", file=sys.stderr)
from agent import app as adk_app
from config_loader import load_config
from pitchgen_app.app_utils.telemetry import setup_telemetry
from pitchgen_app.app_utils.typing import Feedback

# Load environment variables from .env file at runtime
load_dotenv()


class AgentEngineApp(AdkApp):
    def set_up(self) -> None:
        """Initialize the agent engine app with logging and telemetry."""
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
        vertexai.init(project=project_id, location=location)
        self._tmpl_attrs["location"] = location

        setup_telemetry()
        super().set_up()
        logging.basicConfig(level=logging.INFO)
        logging_client = google_cloud_logging.Client()
        self.logger = logging_client.logger(__name__)
        if gemini_location:
            os.environ["GOOGLE_CLOUD_LOCATION"] = gemini_location


    def register_feedback(self, feedback: dict[str, Any]) -> None:
        """Collect and log feedback."""
        feedback_obj = Feedback.model_validate(feedback)
        self.logger.log_struct(feedback_obj.model_dump(), severity="INFO")

    def register_operations(self) -> dict[str, list[str]]:
        """Registers the operations of the Agent."""
        operations = super().register_operations()
        operations[""] = [*operations.get("", []), "register_feedback"]
        return operations


config = load_config()
gemini_location = config.get("default", "region", fallback="global")
os.environ["GOOGLE_CLOUD_LOCATION"] = gemini_location
logs_bucket_name = os.environ.get("LOGS_BUCKET_NAME")
agent_runtime = AgentEngineApp(
    app=adk_app,
    artifact_service_builder=lambda: (
        GcsArtifactService(bucket_name=logs_bucket_name)
        if logs_bucket_name
        else InMemoryArtifactService()
    ),
)
