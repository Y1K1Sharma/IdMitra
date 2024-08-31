

import requests
import json

def push_data(data: str, url: str):
    headers = {'Content-type': 'application/json'}
    
    if "discord" in url:
        payload = {"content": data}
    else:
        payload = {"text": data}
    
    try:
        req = requests.post(
            url,
            headers=headers,
            json=payload,  # Use the json parameter to send JSON data
            timeout=7
        )

        req.raise_for_status()  # Raise an HTTPError for bad responses

        print('Scan results sent to webhook.')
    except requests.exceptions.RequestException as e:
        print(f'Couldn\'t send scan results to webhook. Reason: {e}')
