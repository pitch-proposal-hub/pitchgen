import re

try:
  import urllib3.util
  import urllib3.util.ssl_
  urllib3.util.IS_PYOPENSSL = False
  urllib3.util.ssl_.IS_PYOPENSSL = False
except Exception:
  pass

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
  """Writes string content to a GCS URL and mirrors between QA and DEV buckets."""
  bucket_name, blob_name = parse_gcs_url(url)
  target_buckets = [bucket_name]
  if bucket_name in ("your-pitchgen-content-bucket", "your-pitchgen-content-bucket"):
    for b in ("your-pitchgen-content-bucket", "your-pitchgen-content-bucket"):
      if b not in target_buckets:
        target_buckets.append(b)

  for b_name in target_buckets:
    target_url = f"gs://{b_name}/{blob_name}"
    try:
      client = storage.Client(project=project_id)
      bucket = client.bucket(b_name)
      blob = bucket.blob(blob_name)
      blob.upload_from_string(content, content_type=content_type)
    except Exception as e:
      print(
          f"[GCSUtil] Standard upload to {target_url} failed: {e}. Falling back"
          " to gcloud storage cp..."
      )
      import subprocess
      import tempfile
      import os

      with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write(content)
        temp_path = f.name
      try:
        result = subprocess.run(
            ["gcloud", "storage", "cp", temp_path, target_url],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 and b_name == bucket_name:
          raise Exception(f"gcloud storage cp failed: {result.stderr}")
      finally:
        if os.path.exists(temp_path):
          os.remove(temp_path)
