from google import genai
from google.genai import types
from google.cloud import storage
from src.configuration import configuration

def generate_slide_pipeline(inputs, bucket_name, destination_blob_name, text_model, image_model):
    """
    Generates a presentation slide image based on text inputs.
    If 'slide_image_url' OR 'user_input_slide_image_url' (GCS URIs) is provided in the inputs, 
    it strictly enforces the structural layout and design of that reference image.
    
    Expected text_model: 'gemini-3.1-pro-preview' (or equivalent suitable for tool use)
    """
    config = configuration()
    client = genai.Client(vertexai=True, project=config['default']['PROJECT_NAME'], location=config['default']['region'])
    storage_client = storage.Client(project=config['default']['PROJECT_NAME'])
    bucket = storage_client.bucket(bucket_name)

    if not inputs.get('request'):
        raise ValueError("The 'request' field is mandatory.")

    slide_url = inputs.get('slide_image_url')
    user_url = inputs.get('User_input_slide_image_url')

    if slide_url and user_url:
        raise ValueError("Please provide either 'slide_image_url' OR 'user_input_slide_image_url', not both.")

    reference_image_gs_url = slide_url or user_url

    input_lines = [f"- Request: {inputs['request']}"]
    
    fields_to_include = ['theme', 'layout', 'industry', 'products', 'customer_name']
    for field in fields_to_include:
        if inputs.get(field):
            field_name = field.replace('_', ' ').title()
            input_lines.append(f"- {field_name}: {inputs[field]}")
            
    formatted_inputs = "\n".join(input_lines)

    system_instruction = """
    You are an expert presentation designer. Your job is to take raw inputs and convert them into a highly descriptive, single-paragraph prompt for an AI image generator. 
    Use your Google Search tool to find relevant real-world context, terminology, or recent facts based on the inputs to ensure the textual content requested on the slide is highly accurate.
    """

    if reference_image_gs_url:
        system_instruction += """
        CRITICAL: The user is providing a reference image to the image generator for the layout and design. 
        DO NOT describe a new layout, background, color palette, or design structure. 
        ONLY describe the specific textual content, key metrics, and the core subject matter that need to be injected into the existing design.
        """
    else:
        system_instruction += """
        The resulting image MUST be a complete presentation slide that prominently features text rendered directly into the design (such as a slide title, key metrics, or the customer name).
        Do not restrict the layout; let the visual composition be creative and natural.
        """

    few_shot_prompt = f"""
    {system_instruction}

    EXAMPLE 1
    Input:
    - Request: Conceptual visualization of security
    - Industry: FinTech/Banking
    - Customer Name: Apex Global Bank
    Output:
    A highly detailed corporate presentation slide. The slide features a dynamic, futuristic digital landscape with holographic data streams and biometric security elements. Prominently rendered in large, elegant typography on the slide is the text "Apex Global Bank: Next-Gen Security". Smaller textual elements reading "Encrypted Transactions" and "Zero-Trust Architecture" are integrated into the holographic interfaces.

    EXAMPLE 2
    Input:
    - Request: Show innovation and automation
    - Products: Cloud-connected robotic arms
    - Layout: Two-column infographic
    Output:
    A sleek presentation slide illustrating a bright, modern factory floor. Advanced robotic arms are actively assembling components. Floating digital displays surround the machinery. The text "Innovation in Automation" is written in bold, modern font across the background. Data tags reading "Cloud-Connected" and "Predictive Metrics" are visually overlaid next to the robotic arms.

    YOUR TURN
    Input:
    {formatted_inputs}
    Output:
    """

    print("Step 1: Generating optimized image prompt...")
    
    text_config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.4
    )

    text_response = client.models.generate_content(
        model=text_model,
        contents=[few_shot_prompt],
        config=text_config
    )
    
    optimized_image_prompt = text_response.text.strip()
    print(f"Optimized Image Prompt: {optimized_image_prompt}\n")

    image_contents = []

    if reference_image_gs_url and reference_image_gs_url.startswith('gs://'):
        print(f"Step 1.5: Attaching reference image URI for strict layout constraint: {reference_image_gs_url}...")
        try:
            reference_image_part = types.Part.from_uri(
                file_uri=reference_image_gs_url, 
                mime_type='image/png'
            )
            
            strict_layout_prompt = f"""
            Strictly replicate the exact design, layout, color palette, and structural format of the attached reference image. 
            Do not change the background or the overall positioning of graphical elements. 
            Only update the core subject and textual content to reflect the following:
            {optimized_image_prompt}
            """
            image_contents = [strict_layout_prompt, reference_image_part]
            print("Successfully attached reference image URI and applied strict layout wrapper.")
            
        except Exception as e:
            print(f"Error attaching reference image URI: {e}. Proceeding with standard generation.")
            image_contents = [optimized_image_prompt]
    else:
        image_contents = [optimized_image_prompt]

    print("Step 2: Generating final image...")
    image_response = client.models.generate_content(
        model=image_model,
        contents=image_contents,
    )

    gcs_path = None

    for part in image_response.parts:
        if part.inline_data is not None:
            raw_image_bytes = part.inline_data.data
            out_mime_type = part.inline_data.mime_type
            
            blob = bucket.blob(destination_blob_name)
            blob.upload_from_string(raw_image_bytes, content_type=out_mime_type)
            
            gcs_path = f"gs://{bucket_name}/{destination_blob_name}"
            print(f"Step 3: Successfully uploaded new generated image to {gcs_path}")
            break
            
    return gcs_path