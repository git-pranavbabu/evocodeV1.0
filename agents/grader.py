# agents/grader.py
import os
import requests
import time
from google.cloud import secretmanager
import google.auth

judge0_key = None

def get_judge0_key():
    """Retrieves the Judge0 API key from Secret Manager."""
    global judge0_key
    if judge0_key is not None:
        return judge0_key

    try:
        _, project_id = google.auth.default()
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/judge0-api-key/versions/latest"
        response = client.access_secret_version(name=name)
        judge0_key = response.payload.data.decode("UTF-8").strip()
        print("Successfully loaded Judge0 API key.")
        return judge0_key
    except Exception as e:
        print(f"FATAL: Could not load Judge0 API key: {e}")
        raise

def grade_submission(source_code: str, language_id: int) -> tuple[bool, str, str | None]:
    """
    Submits code to Judge0 and returns correctness and any error messages.
    Returns a tuple of (is_correct, status_description, error_details).
    """
    api_key = get_judge0_key()
    # ... (API key, payload, headers are the same) ...
    payload = {
        "source_code": source_code,
        "language_id": language_id,
    }
    # -----------------------------------------

    headers = {
        "content-type": "application/json",
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "judge0-ce.p.rapidapi.com"
    }

    # 1. Submit the code
    try:
        response = requests.post("https://judge0-ce.p.rapidapi.com/submissions?base64_encoded=false&wait=false", json=payload, headers=headers)
        response.raise_for_status()
        submission_token = response.json().get('token')
        if not submission_token:
            return (False, "Failed to get submission token.", None)
    except requests.exceptions.RequestException as e:
        return (False, f"API request to Judge0 failed: {e}", None)

    # 2. Poll for the result
    for _ in range(10):
        try:
            response = requests.get(f"https://judge0-ce.p.rapidapi.com/submissions/{submission_token}?base64_encoded=false", headers=headers)
            response.raise_for_status()
            result = response.json()
            status = result.get('status', {})
            status_description = status.get('description', 'Unknown')
            
            if status.get('id', 0) > 2:  # Statuses > 2 are "In Queue" and "Processing"
                is_correct = (status.get('id') == 3) # ID 3 is "Accepted"
                
                # Get detailed error messages if they exist
                error_details = result.get('stderr') or result.get('compile_output')
                
                return (is_correct, status_description, error_details)
        except requests.exceptions.RequestException as e:
             return (False, f"API polling to Judge0 failed: {e}", None)
        time.sleep(1)
        
    return (False, "Grading timed out.", None)