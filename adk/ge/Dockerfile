FROM python:3.11-slim

# Force stdout/stderr buffering off to ensure live logs show up in GCP Cloud Logging
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

# Copy the exporter script into the container
COPY web_exporter.py /app/web_exporter.py

# Install dependencies for the exporter
RUN pip install --no-cache-dir requests google-cloud-storage

# Expose the standard Cloud Run port
EXPOSE 8080

# Start the exporter server
CMD ["python", "web_exporter.py"]
