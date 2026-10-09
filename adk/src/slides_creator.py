import json
import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from pitchgen_utils.gcs_util import read_gcs_file

MASTER_TEMPLATE_ID = "SAMPLE_PRESENTATION_ID_PLACEHOLDER_00003"

FEEDBACK_LINK = "https://docs.google.com/forms/d/e/1FAIpQLScgEdrWopnj2AUE6cfR6JU3sRwQL81j_KT8KYWk9x6s9ZCAUA/viewform"
PITCHHUB_LINK = "https://your-sales-portal.example.com/requests/new"
CLOUDHUB_LINK = "https://your-sales-portal.example.com/pitchgen"

def create_deck_in_user_drive(outputs_gcs_url: str, architectural_gcs_url: str, user_token: str) -> str:
  """
    Creates a complete Google Slides presentation directly in the end-user's Google Drive as Owner
    using direct Google Drive & Google Slides REST APIs.
    Full feature parity with Apps Script:
    - Internal Context Metadata Table (Slide 1)
    - Embedded Active Links: Share Feedback, PitchHub Support (https://your-sales-portal.example.com/requests/new), CloudHub (https://your-sales-portal.example.com/pitchgen)
    - Title & Subtitle Slide (Slide 2)
    - Agenda Slides & Section Dividers
    - Exact Slide Positioning (updateSlidesPosition for multi-agenda interleaved reusable & generated slides)
    - Reusable Slides (Layer 1) + Provenance Links in Speaker Notes
    - Generated Content & Speaker Notes (Layer 2)
    - Thank You Slides & Cleanup.
    """
  try:
    print("[SlidesCreator] Initializing Drive & Slides API clients with user Bearer token...")
    credentials = Credentials(user_token)
    drive_service = build("drive", "v3", credentials=credentials)
    slides_service = build("slides", "v1", credentials=credentials)

    formatted_date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y/%m/%d")
    presentation_name = f"PitchGen_{formatted_date}"

    # Step 1: Copy Master Template directly into User's Google Drive as Owner
    print(f"[SlidesCreator] Copying master template {MASTER_TEMPLATE_ID} to user's Drive...")
    copy_body = {"name": presentation_name}
    new_file = drive_service.files().copy(fileId=MASTER_TEMPLATE_ID, body=copy_body).execute()
    new_presentation_id = new_file.get("id")
    print(f"[SlidesCreator] New Presentation created! ID: {new_presentation_id}")

    # Step 2: Read GCS Payloads (Architectural & Creative Outputs)
    print("[SlidesCreator] Reading synthesis data from GCS...")
    arch_data = {}
    outputs_data = {}

    try:
      arch_raw = read_gcs_file(architectural_gcs_url)
      if arch_raw:
        arch_data = json.loads(arch_raw)
    except Exception as e:
      print(f"[SlidesCreator] Notice: Could not read architectural payload: {e}")

    try:
      outputs_raw = read_gcs_file(outputs_gcs_url)
      if outputs_raw:
        outputs_data = json.loads(outputs_raw)
    except Exception as e:
      print(f"[SlidesCreator] Notice: Could not read outputs payload: {e}")

    batch_requests = []

    # Step 3: Copy Reusable Slides, Set Exact Target Positions & Append Provenance Speaker Notes Links
    reusable_suggestions = arch_data.get("reusable_slides") or arch_data.get("suggestions") or []
    if isinstance(reusable_suggestions, list):
      for item in reusable_suggestions:
        if isinstance(item, dict):
          source_deck = item.get("presentation_id") or item.get("deck_id")
          slide_id = item.get("slide_id") or item.get("page_id")
          target_pos = item.get("position") or item.get("insertion_index")

          if source_deck and slide_id:
            try:
              res = slides_service.presentations().pages().copy(
                                presentationId=source_deck,
                                pageObjectId=slide_id,
                                body={}
                            ).execute()
              new_slide_id = res.get("objectId")
              print(f"[SlidesCreator] Successfully copied reusable slide {slide_id} from {source_deck} -> new ID {new_slide_id}")

              # Update exact slide index position if target_pos is specified
              if target_pos is not None and new_slide_id:
                try:
                  batch_requests.append({
                                        "updateSlidesPosition": {
                                            "slideObjectIds": [new_slide_id],
                                            "insertionIndex": int(target_pos)
                                        }
                                    })
                except Exception as pos_err:
                  print(f"[SlidesCreator] Notice: Could not set target position {target_pos}: {pos_err}")

              # Construct Provenance Speaker Notes Link matching screenshot: "Title (portal-shortlink) (Date)"
              source_title = item.get("title") or item.get("slide_title") or item.get("slide_name") or "Reusable Slide"
              source_link = item.get("go_link") or item.get("source_url") or f"https://docs.google.com/presentation/d/{source_deck}/edit#slide=id.{slide_id}"
              source_date = item.get("date") or formatted_date

              provenance_notes = f"\n{source_title} ({source_link}) ({source_date})"

              # Append provenance notes to copied slide's speaker notes
              batch_requests.append({
                                "replaceAllText": {
                                    "containsText": {"text": "{{SPEAKER_NOTES}}", "matchCase": True},
                                    "replaceText": provenance_notes,
                                    "pageObjectIds": [new_slide_id] if new_slide_id else []
                                }
                            })
            except Exception as copy_err:
              print(f"[SlidesCreator] Warning: Failed to copy reusable slide {slide_id}: {copy_err}")

    # Step 4: Populate Slide 1 Internal Context Metadata Table & Action Button Links
    context = outputs_data.get("context", {})
    outline = outputs_data.get("outline", {})

    user_ldap = context.get("user_ldap") or "user"
    if user_ldap and not user_ldap.endswith("@example.com") and not "@" in user_ldap:
      user_ldap = f"{user_ldap}@example.com"

    er_number = context.get("er_number") or "N/A"
    customer_name = context.get("customer_name") or "-"
    audience = ", ".join(context.get("audience")) if (isinstance(context.get("audience"), list) and context.get("audience")) else (context.get("audience") or "-")
    industry = context.get("industry") or "-"
    sales_play = ", ".join(context.get("salesPlay")) if (isinstance(context.get("salesPlay"), list) and context.get("salesPlay")) else (context.get("salesPlay") or "-")
    business_context = context.get("business_context") or "Pitch Presentation"

    proposed_title = outline.get("title") or business_context or "Unlocking Value with Google Cloud"
    subtitle = f"Customized Pitch Strategy for {customer_name if customer_name != '-' else 'Google Cloud'}"

    print(f"[SlidesCreator] Populating Slide 1 Metadata Table: Owner='{user_ldap}', ER='{er_number}', Customer='{customer_name}', Industry='{industry}'")

    # Slide 1: Internal Context Metadata Table Replacements
    batch_requests.append({"replaceAllText": {"containsText": {"text": "{{user_ldap}}", "matchCase": True}, "replaceText": str(user_ldap)}})
    batch_requests.append({"replaceAllText": {"containsText": {"text": "{{er_number}}", "matchCase": True}, "replaceText": str(er_number)}})
    batch_requests.append({"replaceAllText": {"containsText": {"text": "{{customer_name}}", "matchCase": True}, "replaceText": str(customer_name)}})
    batch_requests.append({"replaceAllText": {"containsText": {"text": "{{audience}}", "matchCase": True}, "replaceText": str(audience)}})
    batch_requests.append({"replaceAllText": {"containsText": {"text": "{{industry}}", "matchCase": True}, "replaceText": str(industry)}})
    batch_requests.append({"replaceAllText": {"containsText": {"text": "{{salesPlay}}", "matchCase": True}, "replaceText": str(sales_play)}})
    batch_requests.append({"replaceAllText": {"containsText": {"text": "{{business_context}}", "matchCase": True}, "replaceText": str(business_context)}})

    # Slide 1: Active Button Link Replacements
    batch_requests.append({"replaceAllText": {"containsText": {"text": "{{FEEDBACK_LINK}}", "matchCase": True}, "replaceText": FEEDBACK_LINK}})
    batch_requests.append({"replaceAllText": {"containsText": {"text": "{{PITCHHUB_LINK}}", "matchCase": True}, "replaceText": PITCHHUB_LINK}})
    batch_requests.append({"replaceAllText": {"containsText": {"text": "{{CLOUDHUB_LINK}}", "matchCase": True}, "replaceText": CLOUDHUB_LINK}})

    # Slide 2: Title Slide Placeholders
    title_placeholders = [
            "{{PROPOSED_PRESENTATION_TITLE}}",
            "{{PRESENTATION_TITLE}}",
            "{{MAIN_TITLE}}",
            "{{TITLE_GOES_HERE}}",
            "{{HEADER_TITLE}}"
        ]
    for ph in title_placeholders:
      batch_requests.append({
          "replaceAllText": {
              "containsText": {"text": ph, "matchCase": True},
              "replaceText": proposed_title,
          }
      })

    if customer_name:
      for ph in [
          "{{CUSTOMER_NAME}}",
          "{{customer_name}}",
          "{{CUSTOMER}}",
          "{{customer}}",
          "{{Customer}}",
          "{{Customer Name}}",
          "[Customer]",
          "[Customer Name]",
          "<Customer>",
          "<Customer Name>",
      ]:
        batch_requests.append({
            "replaceAllText": {
                "containsText": {"text": ph, "matchCase": False},
                "replaceText": str(customer_name),
            }
        })
    batch_requests.append({
        "replaceAllText": {
            "containsText": {"text": "{{SUBTITLE}}", "matchCase": True},
            "replaceText": subtitle,
        }
    })
    batch_requests.append({
        "replaceAllText": {
            "containsText": {"text": "{{DATE}}", "matchCase": True},
            "replaceText": formatted_date,
        }
    })

    # Step 5: Populate Section Slides, Body Content, and Generated Speaker Notes (Layer 2)
    sections = outputs_data.get("sections", {})
    if isinstance(sections, dict):
      for sec_key, sec_data in sections.items():
        if isinstance(sec_data, dict):
          sec_title = sec_data.get("title", "")
          body_parts = sec_data.get("parts") or sec_data.get("content") or []
          speaker_notes = (
              sec_data.get("speaker_notes") or sec_data.get("notes") or ""
          )

          if sec_title:
            batch_requests.append({
                "replaceAllText": {
                    "containsText": {"text": "{{TITLE}}", "matchCase": True},
                    "replaceText": sec_title,
                }
            })

          if isinstance(body_parts, list):
            for idx, part in enumerate(body_parts, 1):
              if isinstance(part, str):
                batch_requests.append({
                    "replaceAllText": {
                        "containsText": {
                            "text": f"{{PART_{idx}}}",
                            "matchCase": True,
                        },
                        "replaceText": part,
                    }
                })

          if speaker_notes:
            batch_requests.append({
                "replaceAllText": {
                    "containsText": {
                        "text": "{{SPEAKER_NOTES}}",
                        "matchCase": True,
                    },
                    "replaceText": speaker_notes,
                }
            })

    # Step 6: Execute single fast batchUpdate payload
    if batch_requests:
      print(
          f"[SlidesCreator] Executing batchUpdate with {len(batch_requests)}"
          " operations..."
      )
      slides_service.presentations().batchUpdate(
          presentationId=new_presentation_id, body={"requests": batch_requests}
      ).execute()

    deck_url = f"https://docs.google.com/presentation/d/{new_presentation_id}/edit"
    print(f"[SlidesCreator] Success! Full presentation generated in user Drive: {deck_url}")
    return deck_url

  except Exception as err:
    print(f"[SlidesCreator] Error creating deck via REST API: {err}")
    return f"Error: Failed to create presentation via Drive API: {str(err)}"
