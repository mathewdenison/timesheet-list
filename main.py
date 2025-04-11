import os
import json
import logging
import base64

from google.cloud import logging as cloud_logging

# Import shared code from your published package.
from timesheet_common_timesheet_mfdenison_hopkinsep.models import TimeLog
from timesheet_common_timesheet_mfdenison_hopkinsep.serializers import TimeLogSerializer
from timesheet_common_timesheet_mfdenison_hopkinsep.utils.dashboard import send_dashboard_update

# Initialize Google Cloud Logging (so logs show up in Cloud Logging)
client = cloud_logging.Client()
client.setup_logging()

logger = logging.getLogger("employee_timelog_list")
logger.setLevel(logging.INFO)

def timelog_list_handler(event, context):
    """
    Cloud Function triggered by a Pub/Sub message to retrieve and send an employee's timelog list.

    The function performs these steps:
      1. Decodes the incoming Pub/Sub message (handles potential double JSON encoding).
      2. Patches the payload so that if an "employee" key is provided instead of "employee_id" it is adjusted.
      3. Retrieves TimeLog objects filtered by the provided employee_id.
      4. Serializes the timelogs using a custom serializer.
      5. Builds a dashboard payload and sends it using the shared send_dashboard_update utility.

    Args:
        event (dict): The Pub/Sub event payload, where event["data"] is base64‑encoded.
        context (google.cloud.functions.Context): Metadata for the event.

    If the function completes without raising an exception, the message is automatically acknowledged.
    """
    employee_id = None
    dashboard_payload = {
        "employee_id": None,
        "type": "timelog_list_retrieved",
        "payload": {}
    }

    try:
        # Decode the incoming Pub/Sub message.
        raw_data = base64.b64decode(event["data"]).decode("utf-8")
        logger.info(f"Raw message received: {raw_data}")

        # Decode JSON. If the result is still a string, decode it again.
        first_pass = json.loads(raw_data)
        data = json.loads(first_pass) if isinstance(first_pass, str) else first_pass

        # Patch the data if 'employee' is provided instead of 'employee_id'
        if "employee" in data:
            data["employee_id"] = data.pop("employee")

        employee_id = data.get("employee_id")
        dashboard_payload["employee_id"] = employee_id
        logger.info(f"Received request to fetch timelogs for employee_id={employee_id}")

        # Retrieve all TimeLog objects for this employee.
        # (Assuming your shared model provides a Django-like filter method.)
        logs = TimeLog.objects.filter(employee_id=employee_id)
        serializer = TimeLogSerializer(logs, many=True)

        dashboard_payload["payload"]["timelogs"] = serializer.data
        dashboard_payload["payload"]["message"] = f"Time logs retrieved for employee_id {employee_id}"
        logger.info(dashboard_payload["payload"]["message"])

    except Exception as e:
        dashboard_payload["payload"]["timelogs"] = []
        dashboard_payload["payload"]["message"] = (
            f"Failed to retrieve timelogs for employee_id {employee_id or 'unknown'}. Reason: {str(e)}"
        )
        logger.exception(dashboard_payload["payload"]["message"])

    finally:
        try:
            send_dashboard_update(dashboard_payload)
            logger.info(f"Dashboard update sent for employee_id={employee_id or 'unknown'}")
        except Exception as e:
            logger.warning(f"Dashboard update failed for employee_id={employee_id or 'unknown'}: {str(e)}")

    # No explicit message acknowledgement is needed in Cloud Functions—if the function finishes
    # without error, the message is automatically acknowledged.
