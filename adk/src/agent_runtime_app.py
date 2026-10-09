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
import json
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
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.sessions.in_memory_session_service import InMemorySessionService
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
try:
  from enterprise_agent import app as adk_app
except Exception as e:
  print(
      f"DEBUG_ENV: Failed to import enterprise_agent ({e}), falling back to"
      " agent.py",
      file=sys.stderr,
  )
  from agent import app as adk_app
from config_loader import load_config
from pitchgen_app.app_utils.telemetry import setup_telemetry
from pitchgen_app.app_utils.typing import Feedback

# Load environment variables from .env file at runtime
load_dotenv()


class ResilientGcsSessionService(InMemorySessionService):
  """In-memory + GCS-backed session service that eliminates VertexAiSessionService 429/500 errors.

  Persists session state and recent events to GCS so multi-turn sessions survive
  across
  container instances and redeployments without hitting Vertex AI Session
  Service QPS quotas.
  """

  def __init__(
      self,
      bucket_name: str | None = None,
      project: str | None = None,
      location: str | None = None,
      agent_engine_id: str | None = None,
  ) -> None:
    super().__init__()
    if bucket_name is not None:
      self._bucket_name = bucket_name
    else:
      self._bucket_name = (
          os.environ.get("GCS_BUCKET_CONTENT") or "your-pitchgen-content-bucket"
      )
    self._project = project or os.environ.get("GOOGLE_CLOUD_PROJECT")
    self._location = (
        location
        or os.environ.get("GOOGLE_CLOUD_REGION")
        or os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_LOCATION")
        or "us-central1"
    )
    self._agent_engine_id = agent_engine_id or os.environ.get(
        "GOOGLE_CLOUD_AGENT_ENGINE_ID"
    )
    self._checked_remote_sessions: set[str] = set()

  @staticmethod
  def _normalize_session_id(session_id: str | None) -> str:
    if not session_id:
      return ""
    s = str(session_id).strip()
    if "/" in s:
      parts = [p for p in s.split("/") if p]
      if len(parts) >= 2 and parts[-2] == "sessions":
        return parts[-1]
      return parts[-1]
    return s

  @staticmethod
  def _safe_blob_key(session_id: str) -> str:
    import re

    cleaned = re.sub(r"[^A-Za-z0-9_.-]", "_", str(session_id or "default"))
    return f"ge_sessions/{cleaned}.json"

  def _load_session_from_gcs(
      self, app_name: str, user_id: str, session_id: str
  ) -> Any:
    if not self._bucket_name or not session_id:
      return None
    try:
      from google.adk.sessions.session import Session
      from google.cloud import storage

      client = storage.Client(project=self._project)
      bucket = client.bucket(self._bucket_name)
      blob = bucket.blob(self._safe_blob_key(session_id))
      if not blob.exists():
        return None
      raw = blob.download_as_text()
      data = json.loads(raw)
      if not isinstance(data, dict):
        return None
      data["id"] = session_id
      data["app_name"] = app_name
      data["user_id"] = user_id
      session = Session.model_validate(data)
      self.sessions.setdefault(app_name, {}).setdefault(user_id, {})[
          session_id
      ] = session
      return session
    except Exception as e:
      logging.debug(
          "[ResilientGcsSessionService] GCS session load notice for %s: %s",
          session_id,
          e,
      )
      return None

  def _persist_session_to_gcs(self, session: Any) -> None:
    if not self._bucket_name or not session or not getattr(session, "id", None):
      return
    try:
      from google.cloud import storage

      dump_data = session.model_dump(mode="json", exclude_none=True)
      # Strip transient temp: keys and cap stored events to last 50 to keep payloads compact
      if isinstance(dump_data.get("state"), dict):
        dump_data["state"] = {
            k: v
            for k, v in dump_data["state"].items()
            if not str(k).startswith("temp:")
        }
      if (
          isinstance(dump_data.get("events"), list)
          and len(dump_data["events"]) > 50
      ):
        dump_data["events"] = dump_data["events"][-50:]

      client = storage.Client(project=self._project)
      bucket = client.bucket(self._bucket_name)
      blob = bucket.blob(self._safe_blob_key(session.id))
      blob.upload_from_string(
          json.dumps(dump_data), content_type="application/json"
      )
    except Exception as e:
      logging.debug(
          "[ResilientGcsSessionService] GCS session save notice for %s: %s",
          getattr(session, "id", ""),
          e,
      )

  async def create_session(
      self,
      *,
      app_name: str,
      user_id: str,
      state: dict[str, Any] | None = None,
      session_id: str | None = None,
      **kwargs: Any,
  ):
    del kwargs
    norm_id = self._normalize_session_id(session_id) or None
    if norm_id:
      existing = self._get_session_impl(
          app_name=app_name, user_id=user_id, session_id=norm_id
      )
      if existing:
        if state:
          storage_sess = self.sessions[app_name][user_id][norm_id]
          storage_sess.state.update(state)
          self._persist_session_to_gcs(storage_sess)
          return self._get_session_impl(
              app_name=app_name, user_id=user_id, session_id=norm_id
          )
        return existing
    created = self._create_session_impl(
        app_name=app_name,
        user_id=user_id,
        state=state,
        session_id=norm_id,
    )
    storage_sess = (
        self.sessions.get(app_name, {})
        .get(user_id, {})
        .get(created.id, created)
    )
    self._persist_session_to_gcs(storage_sess)
    return created

  async def get_session(
      self,
      *,
      app_name: str,
      user_id: str,
      session_id: str,
      config: Any = None,
      **kwargs: Any,
  ):
    del kwargs
    norm_id = self._normalize_session_id(session_id)
    if not norm_id:
      return None

    # 1. Fast in-memory lookup
    mem_session = self._get_session_impl(
        app_name=app_name,
        user_id=user_id,
        session_id=norm_id,
        config=config,
    )
    if mem_session is not None:
      return mem_session

    # Also check if session was stored under another user_id for the same app_name
    app_sessions = self.sessions.get(app_name, {})
    for other_uid, uid_map in list(app_sessions.items()):
      if norm_id in uid_map and other_uid != user_id:
        aliased = uid_map[norm_id].model_copy(deep=True)
        aliased.user_id = user_id
        self.sessions.setdefault(app_name, {}).setdefault(user_id, {})[
            norm_id
        ] = aliased
        return self._get_session_impl(
            app_name=app_name,
            user_id=user_id,
            session_id=norm_id,
            config=config,
        )

    # 2. GCS session snapshot lookup (survives container restarts / scale-out)
    gcs_session = self._load_session_from_gcs(app_name, user_id, norm_id)
    if gcs_session is not None:
      return self._get_session_impl(
          app_name=app_name,
          user_id=user_id,
          session_id=norm_id,
          config=config,
      )

    # 3. One-time fail-open migration check from VertexAiSessionService for legacy sessions
    if self._agent_engine_id and norm_id not in self._checked_remote_sessions:
      self._checked_remote_sessions.add(norm_id)
      try:
        import asyncio
        from google.adk.sessions.vertex_ai_session_service import (
            VertexAiSessionService,
        )

        remote_svc = VertexAiSessionService(
            project=self._project,
            location=self._location,
            agent_engine_id=self._agent_engine_id,
        )
        remote_sess = await asyncio.wait_for(
            remote_svc.get_session(
                app_name=app_name,
                user_id=user_id,
                session_id=norm_id,
                config=config,
            ),
            timeout=2.5,
        )
        if remote_sess is not None:
          self.sessions.setdefault(app_name, {}).setdefault(user_id, {})[
              norm_id
          ] = remote_sess
          self._persist_session_to_gcs(remote_sess)
          return self._get_session_impl(
              app_name=app_name,
              user_id=user_id,
              session_id=norm_id,
              config=config,
          )
      except Exception as e:
        logging.debug(
            "[ResilientGcsSessionService] Remote Vertex session fallback"
            " skipped for %s: %s",
            norm_id,
            e,
        )

    return None

  async def append_event(self, session: Any, event: Any):
    if getattr(event, "partial", False):
      return event

    app_name = session.app_name
    user_id = session.user_id
    norm_id = self._normalize_session_id(session.id)
    session.id = norm_id

    # Ensure session exists in storage map so super().append_event never drops the event
    if (
        app_name not in self.sessions
        or user_id not in self.sessions.get(app_name, {})
        or norm_id not in self.sessions.get(app_name, {}).get(user_id, {})
    ):
      self.sessions.setdefault(app_name, {}).setdefault(user_id, {})[
          norm_id
      ] = session

    result = await super().append_event(session=session, event=event)
    storage_session = (
        self.sessions.get(app_name, {}).get(user_id, {}).get(norm_id)
    )
    has_state_delta = bool(
        getattr(event, "actions", None)
        and getattr(event.actions, "state_delta", None)
    )
    is_turn_complete = bool(getattr(event, "turn_complete", False))
    if storage_session is not None and (has_state_delta or is_turn_complete):
      self._persist_session_to_gcs(storage_session)
    return result


class AgentEngineApp(AdkApp):

  async def _init_session(
      self,
      session_service: Any,
      artifact_service: Any,
      request: Any,
  ):
    """Initializes the session while preserving request.session_id when provided."""
    from google.adk.events.event import Event

    req_session_id = getattr(request, "session_id", None)
    try:
      session = await session_service.create_session(
          app_name=self._app_name(),
          user_id=request.user_id,
          session_id=req_session_id,
      )
    except TypeError:
      session = await session_service.create_session(
          app_name=self._app_name(),
          user_id=request.user_id,
      )
    if not session:
      raise RuntimeError("Create session failed.")
    if getattr(request, "events", None):
      for event in request.events:
        try:
          ev_obj = (
              event if isinstance(event, Event) else Event.model_validate(event)
          )
          await session_service.append_event(session, ev_obj)
        except Exception as ev_err:
          logging.debug("[AgentEngineApp] Event replay notice: %s", ev_err)
    if getattr(request, "artifacts", None):
      await self._save_artifacts(session.id, artifact_service, request)
    return session

  def set_up(self) -> None:
    """Initialize the agent engine app with logging and telemetry."""
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    engine_location = (
        os.environ.get("GOOGLE_CLOUD_REGION")
        or os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_LOCATION")
        or "us-central1"
    )
    vertexai.init(project=project_id, location=engine_location)
    self._tmpl_attrs["location"] = engine_location

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
gemini_project = config.get("default", "project", fallback="your-gcp-project-id")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", gemini_project)
os.environ.setdefault("CLOUD_ML_PROJECT_ID", gemini_project)
gemini_location = config.get("default", "region", fallback="global")
os.environ["GOOGLE_CLOUD_LOCATION"] = gemini_location
logs_bucket_name = os.environ.get("LOGS_BUCKET_NAME")
content_bucket_name = config.get(
    "bucket", "content", fallback="your-pitchgen-content-bucket"
)
if os.environ.get("TEST_TMPDIR"):
  agent_runtime = None
else:
  try:
    agent_runtime = AgentEngineApp(
        app=adk_app,
        session_service_builder=lambda: ResilientGcsSessionService(
            bucket_name=content_bucket_name
        ),
        memory_service_builder=lambda: InMemoryMemoryService(),
        artifact_service_builder=lambda: (
            GcsArtifactService(bucket_name=logs_bucket_name)
            if logs_bucket_name
            else InMemoryArtifactService()
        ),
    )
  except Exception as e:
    logging.warning(
        "AgentEngineApp deferred in hermetic environment without ADC: %s", e
    )
    agent_runtime = None
