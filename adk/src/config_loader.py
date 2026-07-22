import configparser
import os


def load_config(file_path=None):
  # Remove any API keys from the environment to prevent the google-genai SDK
  # from using them instead of standard Google Cloud IAM/ADC credentials.
  os.environ.pop('GEMINI_API_KEY', None)
  os.environ.pop('GOOGLE_API_KEY', None)
  os.environ.pop('API_KEY', None)

  if file_path is None:
    # Resolve path relative to this file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, 'config', 'config.ini')

  config = configparser.ConfigParser()
  if not os.path.exists(file_path):
    raise FileNotFoundError(f'Config file not found at {file_path}')
  config.read(file_path)

  # Set the GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_QUOTA_PROJECT environment variables
  # so the GenAI SDK and other Google Cloud services can resolve the correct project and quota.
  if config.has_section('default'):
    if config.has_option('default', 'project_name'):
      project_name = config.get('default', 'project_name')
      os.environ['GOOGLE_CLOUD_PROJECT'] = project_name
      os.environ['GOOGLE_CLOUD_QUOTA_PROJECT'] = project_name
    if config.has_option('default', 'region'):
      region = config.get('default', 'region')
      os.environ['GOOGLE_CLOUD_LOCATION'] = region


  return config


_SECRET_CACHE = {}


def resolve_secret_with_cache(secret_name):
  """Resolves a secret from Google Secret Manager with in-memory caching."""
  if not secret_name:
    return secret_name

  if secret_name in _SECRET_CACHE:
    return _SECRET_CACHE[secret_name]

  # Import lazily to avoid heavy dependencies on startup
  from google.cloud import secretmanager

  config = load_config()
  try:
    project_id = config.get("default", "project_name")
    secret_client = secretmanager.SecretManagerServiceClient()
    secret_path = secret_client.secret_path(project_id, secret_name)
    response = secret_client.access_secret_version(
        request={"name": f"{secret_path}/versions/latest"}
    )
    resolved_value = response.payload.data.decode("UTF-8").strip()
    print(
        f"[config_loader] Resolved secret '{secret_name}' to '{resolved_value}'"
    )
    _SECRET_CACHE[secret_name] = resolved_value
    return resolved_value
  except Exception as e:
    # Cache the failure (by storing the secret_name itself) to avoid hitting Secret Manager again
    _SECRET_CACHE[secret_name] = secret_name
    print(
        f"[config_loader] Could not resolve secret '{secret_name}' in Secret Manager,"
        f" using as is. (Error: {e})"
    )
    return secret_name

