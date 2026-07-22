"""Utility functions for interacting with Google Cloud Storage."""

import re
from google.cloud import storage


def parse_gcs_url(url):
  """Parses a gs:// URL into bucket and blob name."""
  match = re.match(r'gs://([^/]+)/(.*)', url)
  if not match:
    raise ValueError(f'Invalid GCS URL: {url}')
  return match.groups()


def read_gcs_file(url, project_id=None):
  """Reads a file from GCS and returns its content as string."""
  try:
    bucket_name, blob_name = parse_gcs_url(url)
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    return blob.download_as_text()
  except Exception as e:
    print(f"[GCSUtil] Standard read failed: {e}. Falling back to gcloud storage cat...")
    import subprocess
    result = subprocess.run(["gcloud", "storage", "cat", url], capture_output=True, text=True)
    if result.returncode != 0:
      raise Exception(f"gcloud storage cat failed: {result.stderr}")
    return result.stdout


def write_gcs_file(
    url, content, content_type='application/json', project_id=None
):
  """Writes string content to a GCS URL."""
  try:
    bucket_name, blob_name = parse_gcs_url(url)
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(content, content_type=content_type)
  except Exception as e:
    print(f"[GCSUtil] Standard upload failed: {e}. Falling back to gcloud storage cp...")
    import subprocess
    import tempfile
    import os
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
      f.write(content)
      temp_path = f.name
    try:
      result = subprocess.run(["gcloud", "storage", "cp", temp_path, url], capture_output=True, text=True)
      if result.returncode != 0:
        raise Exception(f"gcloud storage cp failed: {result.stderr}")
    finally:
      if os.path.exists(temp_path):
        os.remove(temp_path)

