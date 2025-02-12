from flask import Flask, render_template
import requests
from datetime import datetime
from typing import Optional, Dict, Any
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import threading
import urllib3

# Disable SSL verification warning, ask valerio if there's a good way of handling ssl verification

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# Authentication configuration
AUTH_CONFIG = {
    'token_url': 'https://auth.pacorini.com/auth/realms/Pacorini/protocol/openid-connect/token',
    'client_id': 'pacorini-api',
    'client_secret': '381e2bef-5613-44ba-b28d-b5234070aeee',
    'username': 'prima',
    'password': 'NeXOD2Owu#en2ku9oti4'
}

# API endpoint config
API_URL = "https://us.prima.pacorini.com/api/v1.0/Prima/tipperRoomDisplay"
COMPID = 'PLL'
WHID = '200NORDIC' # 'GREER' or '200NORDIC'

# Global variables for connection status and data
connection_status = {"is_connected": True, "last_successful": None}
cached_data = {"data": None, "timestamp": None}

# Configure retry strategy
retry_strategy = Retry(
    total=5,  # maximum number of retries
    backoff_factor=1,  # wait 1, 2, 4, 8, 16... seconds between retries
    status_forcelist=[500, 502, 503, 504],  # HTTP status codes to retry on
)

# Create a session with the retry strategy
session = requests.Session()
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)

def check_internet_connection() -> bool:
    """Check if internet connection is available."""
    try:
        # Try to connect to a reliable host
        session.get("https://8.8.8.8", timeout=3, verify=False)
        return True
    except requests.RequestException:
        return False

def get_access_token() -> Optional[str]:
    """
    Retrieve access token from authentication endpoint with retry logic.
    Returns None if the request fails after all retries.
    """
    try:
        payload = {
            'grant_type': 'password',
            'client_id': AUTH_CONFIG['client_id'],
            'client_secret': AUTH_CONFIG['client_secret'],
            'username': AUTH_CONFIG['username'],
            'password': AUTH_CONFIG['password']
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = session.post(
            AUTH_CONFIG['token_url'],
            data=payload,
            headers=headers,
            verify=False
        )
        
        response.raise_for_status()
        return response.json().get('access_token')
    
    except requests.exceptions.RequestException as e:
        print(f"Error getting access token: {str(e)}")
        return None

def get_tipper_room_data() -> Optional[Dict[str, Any]]:
    """
    Fetch tipper room display data using authentication token.
    Returns None if either token retrieval or data fetch fails.
    """
    try:
        access_token = get_access_token()
        if not access_token:
            raise Exception("Failed to obtain access token")
            
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        params = {
            'token': access_token,
            'CompID': COMPID,
            'WHID': WHID,
        }
        
        response = session.get(
            API_URL, 
            headers=headers, 
            params=params,
            verify=False
        )
        response.raise_for_status()
        data = response.json()
        
        # Update connection status and cached data
        connection_status["is_connected"] = True
        connection_status["last_successful"] = datetime.now()
        cached_data["data"] = data
        cached_data["timestamp"] = datetime.now()
        
        return data
        
    except Exception as e:
        print(f"Error fetching tipper room data: {str(e)}")
        connection_status["is_connected"] = False
        return None

def background_data_refresh():
    """Background task to continuously refresh data."""
    while True:
        if not check_internet_connection():
            print("Internet connection lost. Waiting to retry...")
            time.sleep(5)  # Wait 5 seconds before checking connection again
            continue
            
        try:
            get_tipper_room_data()
        except Exception as e:
            print(f"Error in background refresh: {str(e)}")
        
        time.sleep(30)  # Wait 30 seconds before next refresh

@app.route('/')
def index():
    """
    Main route handler that displays tipper room data.
    """
    try:
        # Use cached data if available and recent (less than 1 minute old)
        current_time = datetime.now()
        if (cached_data["data"] and cached_data["timestamp"] and 
            (current_time - cached_data["timestamp"]).seconds < 60):
            data = cached_data["data"]
        else:
            data = get_tipper_room_data()
            
        if not data:
            return render_template(
                'index.html',
                error="Unable to retrieve tipper room data. Attempting to reconnect...",
                connection_status=connection_status,
                datetime=datetime
            )
            
        # Get column names from the first record if data is a list
        if isinstance(data, list) and data:
            columns = list(data[0].keys())
        else:
            # Handle case where data might be a single object
            columns = list(data.keys())
            data = [data]
            
        return render_template(
            'index.html',
            data=data,
            columns=columns,
            connection_status=connection_status,
            datetime=datetime
        )
        
    except Exception as e:
        return render_template(
            'index.html',
            error=f"An error occurred: {str(e)}",
            connection_status=connection_status,
            datetime=datetime
        )

def start_background_tasks():
    """Start background tasks when the application starts."""
    refresh_thread = threading.Thread(target=background_data_refresh, daemon=True)
    refresh_thread.start()

if __name__ == '__main__':
    start_background_tasks()
    app.run(debug=True)
