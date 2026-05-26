import uuid
from typing import Dict, Any
from google import genai
from google.genai import types
from google.cloud import storage

def build_multimodal_prompt(inputs: Dict[str, Any]) -> list:
    """
    Dynamically builds the instruction and attaches the appropriate image URIs
    based on the exact combination of inputs provided by the user.
    """
    request = inputs.get('request', '').strip()
    theme = inputs.get('theme', '').strip()
    layout = inputs.get('layout', '').strip()
    existing_url = inputs.get('existing_slide_image_url', '').strip()
    template_url = inputs.get('template_slide_image_url', '').strip()
    user_url = inputs.get('User_input_slide_image_url', '').strip()

    if not existing_url:
        raise ValueError("The 'existing_slide_image_url' field is mandatory as the base canvas.")

    prompt_contents = []
    
    prompt_contents.append("TARGET IMAGE (EXISTING SLIDE):")
    prompt_contents.append(types.Part.from_uri(file_uri=existing_url, mime_type='image/png'))

    instruction = "You are an expert presentation designer. Your task is to modify the TARGET IMAGE according to the following constraints:\n\n"

    if request and template_url:
        instruction += (
            f"INSTRUCTION: Apply the visual design and layout of the reference template to the original image. "
            f"Update the text/content only if explicitly instructed to do so by the request; otherwise, preserve the original content. "
            f"Request: '{request}'."
        )
        prompt_contents.append("REFERENCE TEMPLATE:")
        prompt_contents.append(types.Part.from_uri(file_uri=template_url, mime_type='image/png'))

    elif request and user_url:
        instruction += (
            f"INSTRUCTION: Merge the original image and the user's uploaded image exactly as instructed by the request, "
            f"which will dictate whether to apply the user image's layout/content to the original image, or vice versa. "
            f"When executing layout and design changes, preserve the original core content; you may only alter or rephrase the text "
            f"if it is strictly necessary to fit the new layout requirements. "
            f"Request: '{request}'."
        )
        prompt_contents.append("REFERENCE IMAGE (USER ASSET):")
        prompt_contents.append(types.Part.from_uri(file_uri=user_url, mime_type='image/png'))

    elif request and not template_url and not user_url:
        instruction += (
            f"INSTRUCTION: Modify either the text/content or the visual design/layout of the original image based on the request. "
            f"Do not alter both simultaneously. "
            f"Request: '{request}'."
        )

    elif template_url and not request:
        instruction += (
            f"INSTRUCTION: Apply the visual design and layout of the reference template to the original image. "
            f"You must preserve the original core content and meaning. You may only slightly adjust or rephrase the text "
            f"if it is strictly necessary to fit the new layout."
        )
        prompt_contents.append("REFERENCE TEMPLATE:")
        prompt_contents.append(types.Part.from_uri(file_uri=template_url, mime_type='image/png'))

    elif user_url and not request:
        instruction += (
            f"INSTRUCTION: Apply the visual design and layout of the user's uploaded image to the original image. "
            f"You must preserve the original core content and meaning. You may only slightly adjust or rephrase the text "
            f"if it is strictly necessary to fit the new layout."
        )
        prompt_contents.append("REFERENCE IMAGE (USER ASSET):")
        prompt_contents.append(types.Part.from_uri(file_uri=user_url, mime_type='image/png'))

    else:
        instruction += "Return an optimized, enhanced version of the TARGET IMAGE without altering its core content."

    metadata_instructions = []
    if theme:
        metadata_instructions.append(f"Ensure the overall aesthetic matches the theme: {theme}.")
    if layout:
        metadata_instructions.append(f"Strictly adhere to the following layout constraints: {layout}.")
    
    if metadata_instructions:
        instruction += "\n\nADDITIONAL CONSTRAINTS:\n" + "\n".join(metadata_instructions)

    prompt_contents.insert(0, instruction)

    return prompt_contents

def transform_slide_pipeline(
    inputs: Dict[str, Any], 
    project_name: str, 
    bucket_name: str, 
    location: str,
    destination_blob_name: str,
    model: str
) -> str:
    """
    Main pipeline to execute the Nano Banana image generation and upload to GCS.
    """
    client = genai.Client(vertexai=True, project=project_name, location=location)
    storage_client = storage.Client(project=project_name)
    bucket = storage_client.bucket(bucket_name)

    print("Step 1: Assembling dynamic multimodal prompt...")
    image_contents = build_multimodal_prompt(inputs)

    print(f"Step 2: Sending request to {model}...")
    image_response = client.models.generate_content(
        model=model,
        contents=image_contents,
    )

    gcs_path = None

    print("Step 3: Processing response and uploading to storage...")
    for part in image_response.parts:
        if part.inline_data is not None:
            raw_image_bytes = part.inline_data.data
            out_mime_type = part.inline_data.mime_type
            
            blob = bucket.blob(destination_blob_name)
            blob.upload_from_string(raw_image_bytes, content_type=out_mime_type)
            
            gcs_path = f"gs://{bucket_name}/{destination_blob_name}"
            print(f"Success! Uploaded generated image to {gcs_path}")
            break 
            
    if not gcs_path:
        raise RuntimeError("Model generation completed, but no image data was returned in the response parts.")

    return gcs_path