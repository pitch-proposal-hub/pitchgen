import base64
import os
import uuid
from agents.base_agent import BaseAgent
from google.cloud import storage
from agents.workflows.visual_synthesis_workflow import VisualSynthesisWorkflow
from agents.workflows.visual_transformation_workflow import VisualTransformationWorkflow


class VisualAgent(BaseAgent):

  def __init__(self, config):
    super().__init__(
        "VisualAgent",
        "Responsible for generating and transforming visual assets.",
    )
    self.config = config
    self.project_id = config["default"]["project_name"]
    self.bucket_name = config["bucket"]["content"]
    self.add_skill("synthesis", VisualSynthesisWorkflow(config))
    self.add_skill("transformation", VisualTransformationWorkflow(config))

  def _upload_to_gcs(self, img_b64, action_type):
    if not img_b64:
      return None, "No image generated"
    try:
      storage_client = storage.Client(project=self.project_id)
      bucket = storage_client.bucket(self.bucket_name)

      # Determine GCS path prefix
      sub_dir = (
          "nanoBanana_imageGen"
          if action_type == "gen"
          else "nanoBanana_imageTrans"
      )
      request_file_name = str(uuid.uuid4())
      destination_blob_name = f"{sub_dir}/{request_file_name}_Response.png"

      blob = bucket.blob(destination_blob_name)
      image_bytes = base64.b64decode(img_b64)
      blob.upload_from_string(image_bytes, content_type="image/png")

      return f"gs://{self.bucket_name}/{destination_blob_name}", None
    except Exception as e:
      print(f"[VisualAgent] GCS Upload failed: {e}")
      return None, str(e)

  def run(self, global_state):
    print(f"[{self.name}] Starting visual generation...")

    # Check if visuals are requested in context
    if global_state.context.get("visuals_requested"):
      prompt = global_state.context.get(
          "visual_prompt", "Professional business slide"
      )

      ref_image = global_state.context.get("User_input_slide_image_url")
      if not ref_image:
        ref_image = global_state.context.get("slide_image_url", "")

      # 1. Generate image in base64
      img_base64 = self.skills["synthesis"].execute(
          prompt_text_or_request=prompt,
          user_input_slide_image_url=ref_image,
      )

      # 2. Upload base64 image to GCS for slide inclusion
      gcs_uri, err = self._upload_to_gcs(img_base64, "gen")
      if gcs_uri:
        print(
            f"[{self.name}] Successfully generated and uploaded image:"
            f" {gcs_uri}"
        )
        if not global_state.context.get("visual_assets"):
          global_state.context["visual_assets"] = []
        global_state.context["visual_assets"].append(gcs_uri)
      else:
        print(f"[{self.name}] Error uploading visual: {err}")

    print(f"[{self.name}] Visual generation completed.")
    return global_state

  def run_payload(self, input_data):
    """Processes input payloads for generating net-new visuals or transforming existing slides.

    Matches the App Engine / WSGI input-output format for Option 1.
    """
    user_inputs = input_data.get("user_inputs", {})

    # Extract existing image url (either top level or inside user_inputs)
    existing_image = input_data.get("existing_slide_image_url")
    if not existing_image:
      existing_image = user_inputs.get("existing_slide_image_url", "")

    # Determine if it's a transform request based on existence of existing_image
    if existing_image:
      # Resolve distinct template and reference images
      template_image = user_inputs.get("template_slide_image_url") or input_data.get("template_slide_image_url", "")
      ref_image = user_inputs.get("User_input_slide_image_url") or input_data.get("User_input_slide_image_url", "")

      # Transform Visual
      request = user_inputs.get("request") or input_data.get("request", "")
      layout = user_inputs.get("layout") or input_data.get("layout", "")
      theme = user_inputs.get("theme") or input_data.get("theme", "")
      industry = user_inputs.get("industry") or input_data.get("industry", "")
      sales_play = user_inputs.get("salesPlay") or input_data.get("salesPlay", "")
      customer_name = user_inputs.get("customer_name") or input_data.get("customer_name", "")
      products = user_inputs.get("products") or input_data.get("products", "")
      solutions = user_inputs.get("solutions") or input_data.get("solutions", "")

      img_base64 = self.skills["transformation"].execute(
          request=request,
          existing_slide_image_url=existing_image,
          user_input_slide_image_url=ref_image,
          template_slide_image_url=template_image,
          theme=theme,
          layout=layout,
          industry=industry,
          sales_play=sales_play,
          customer_name=customer_name,
          products=products,
          solutions=solutions,
      )
      gcs_link, gcs_error = self._upload_to_gcs(img_base64, "trans")
      http_link = (
          gcs_link.replace("gs://", "https://storage.googleapis.com/")
          if gcs_link
          else None
      )
      return {
          "message": "Success! The slide image has been transformed and uploaded directly to GCS.",
          "gcs_link": http_link,
          "gcs_error": gcs_error,
      }

    elif "user_inputs" in input_data or "request" in input_data:
      # Generate Visual
      request = user_inputs.get("request") or input_data.get("request", "")
      layout = user_inputs.get("layout") or input_data.get("layout", "")
      theme = user_inputs.get("theme") or input_data.get("theme", "")
      products = user_inputs.get("products") or input_data.get("products", "")
      customer_name = user_inputs.get("customer_name") or input_data.get("customer_name", "")
      industry = user_inputs.get("industry") or input_data.get("industry", "")
      sales_play = user_inputs.get("salesPlay") or input_data.get("salesPlay", "")
      solutions = user_inputs.get("solutions") or input_data.get("solutions", "")


      # Resolve distinct template and reference images (slide_image_url is used for template in generation)
      template_image = (
          user_inputs.get("template_slide_image_url")
          or user_inputs.get("slide_image_url")
          or input_data.get("template_slide_image_url")
          or input_data.get("slide_image_url", "")
      )
      ref_image = (
          user_inputs.get("User_input_slide_image_url")
          or input_data.get("User_input_slide_image_url", "")
      )

      img_base64 = self.skills["synthesis"].execute(
          prompt_text_or_request=request,
          theme=theme,
          layout=layout,
          products=products,
          customer_name=customer_name,
          industry=industry,
          solutions=solutions,
          user_input_slide_image_url=ref_image,
          template_slide_image_url=template_image,
          sales_play=sales_play,
      )
      gcs_link, gcs_error = self._upload_to_gcs(img_base64, "gen")
      http_link = (
          gcs_link.replace("gs://", "https://storage.googleapis.com/")
          if gcs_link
          else None
      )
      return {
          "message": "Success! The slide image has been generated and uploaded directly to GCS.",
          "gcs_link": http_link,
          "gcs_error": gcs_error,
      }

    else:
      return {
          "status": "error",
          "message": (
              "Unknown payload format: neither 'user_inputs' nor"
              " 'existing_slide_image_url' found."
          ),
      }
