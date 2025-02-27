from flask import Flask, render_template
import requests
from datetime import datetime
from typing import Optional, Dict, Any, List
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import threading
import urllib3
from collections import Counter, defaultdict

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

def process_chart_data(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process the tipper room data into chart-friendly format."""
    if not data:
        return None

    # Initialize chart data structure
    chart_data = {
        'barChart': {
            'labels': [],
            'datasets': [{
                'label': 'Count',
                'data': [],
                'backgroundColor': [
                    'rgba(255, 99, 132, 0.5)',
                    'rgba(54, 162, 235, 0.5)',
                    'rgba(255, 206, 86, 0.5)',
                    'rgba(75, 192, 192, 0.5)',
                ],
                'borderColor': [
                    'rgb(255, 99, 132)',
                    'rgb(54, 162, 235)',
                    'rgb(255, 206, 86)',
                    'rgb(75, 192, 192)',
                ],
                'borderWidth': 1
            }]
        },
        'lineChart': {
            'labels': [],
            'datasets': [{
                'label': 'Timeline',
                'data': [],
                'fill': False,
                'borderColor': 'rgb(75, 192, 192)',
                'tension': 0.1
            }]
        },
        'pieChart': {
            'labels': [],
            'datasets': [{
                'data': [],
                'backgroundColor': [
                    'rgba(255, 99, 132, 0.5)',
                    'rgba(54, 162, 235, 0.5)',
                    'rgba(255, 206, 86, 0.5)',
                    'rgba(75, 192, 192, 0.5)',
                ],
                'borderColor': [
                    'rgb(255, 99, 132)',
                    'rgb(54, 162, 235)',
                    'rgb(255, 206, 86)',
                    'rgb(75, 192, 192)',
                ],
            }]
        },
        'doughnutChart': {
            'labels': [],
            'datasets': [{
                'data': [],
                'backgroundColor': [
                    'rgba(255, 99, 132, 0.5)',
                    'rgba(54, 162, 235, 0.5)',
                    'rgba(255, 206, 86, 0.5)',
                    'rgba(75, 192, 192, 0.5)',
                ],
                'borderColor': [
                    'rgb(255, 99, 132)',
                    'rgb(54, 162, 235)',
                    'rgb(255, 206, 86)',
                    'rgb(75, 192, 192)',
                ],
            }]
        }
    }

    # Process data for charts
    status_counts = Counter()
    type_counts = Counter()
    category_counts = Counter()
    timeline_data = defaultdict(int)

    for item in data:
        # Update counters based on available fields
        if 'status' in item:
            status_counts[item['status']] += 1
        if 'type' in item:
            type_counts[item['type']] += 1
        if 'category' in item:
            category_counts[item['category']] += 1
        if 'timestamp' in item:
            timeline_data[item['timestamp']] += 1

    # Bar Chart - Status Distribution
    chart_data['barChart']['labels'] = list(status_counts.keys())
    chart_data['barChart']['datasets'][0]['data'] = list(status_counts.values())

    # Line Chart - Timeline
    sorted_timeline = sorted(timeline_data.items())
    chart_data['lineChart']['labels'] = [item[0] for item in sorted_timeline]
    chart_data['lineChart']['datasets'][0]['data'] = [item[1] for item in sorted_timeline]

    # Pie Chart - Type Distribution
    chart_data['pieChart']['labels'] = list(type_counts.keys())
    chart_data['pieChart']['datasets'][0]['data'] = list(type_counts.values())

    # Doughnut Chart - Category Distribution
    chart_data['doughnutChart']['labels'] = list(category_counts.keys())
    chart_data['doughnutChart']['datasets'][0]['data'] = list(category_counts.values())

    return chart_data

@app.route('/analytics')
def analytics():
    """Analytics route handler that displays table data and key statistics."""
    try:
        # Use cached data if available and recent
        current_time = datetime.now()
        if (cached_data["data"] and cached_data["timestamp"] and 
            (current_time - cached_data["timestamp"]).seconds < 60):
            data = cached_data["data"]
        else:
            data = get_tipper_room_data()
        
        if not data:
            return render_template(
                'analytics.html',
                error="Unable to retrieve tipper room data. Attempting to reconnect...",
                connection_status=connection_status,
                datetime=datetime
            )

        # Ensure data is a list
        data_list = data if isinstance(data, list) else [data]
        
        # Get column names from the first record if data is a list
        if data_list:
            columns = list(data_list[0].keys())
        else:
            columns = []
        
        # Initialize key statistics
        max_gross_weight = "N/A"
        average_runtime_minutes = "N/A"
        runtime_minutes_over_80 = 0

        # Extract and calculate from data if available
        try:
            if data_list:
                # Extract gross weights if available
                weights = []
                for item in data_list:
                    if 'Gross Wgt' in item and item['Gross Wgt']:
                        try:
                            weight = float(item['Gross Wgt'])
                            weights.append(weight)
                        except (ValueError, TypeError):
                            pass
                
                if weights:
                    max_gross_weight = f"{max(weights):,.2f} kg"
                
                # Extract runtime minutes if available
                runtimes = []
                for item in data_list:
                    if 'Runtime Minutes' in item and item['Runtime Minutes']:
                        try:
                            runtime = float(item['Runtime Minutes'])
                            runtimes.append(runtime)
                        except (ValueError, TypeError):
                            pass
                
                if runtimes:
                    average_runtime_minutes = f"{sum(runtimes) / len(runtimes):.1f} min"
                    runtime_minutes_over_80 = sum(1 for runtime in runtimes if runtime > 80)
        except Exception as stat_error:
            print(f"Error calculating statistics: {str(stat_error)}")
        
        return render_template(
            'analytics.html',
            data=data_list,
            columns=columns,
            max_gross_weight=max_gross_weight,
            average_runtime_minutes=average_runtime_minutes,
            runtime_minutes_over_80=runtime_minutes_over_80,
            connection_status=connection_status,
            datetime=datetime
        )
    
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return render_template(
            'analytics.html',
            error=f"An error occurred: {str(e)}",
            connection_status=connection_status,
            datetime=datetime
        )

if __name__ == '__main__':
    start_background_tasks()
    app.run(debug=True)
