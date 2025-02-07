from flask import Flask, render_template
import requests
from datetime import datetime

app = Flask(__name__)

# API endpoint URL - replace with your actual API URL
API_URL = "your_api_endpoint_here"

def get_data_from_api():
    try:
        response = requests.get(API_URL)
        return response.json()
    except Exception as e:
        print(f"Error fetching data: {str(e)}")
        return []

@app.route('/')
def index():
    try:
        data = get_data_from_api()
        if data:
            # Get column names from the first record
            columns = list(data[0].keys())
            return render_template('index.html', data=data, columns=columns, datetime=datetime)
        return "No data available"
    except Exception as e:
        return f"An error occurred: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True)