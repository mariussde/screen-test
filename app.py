from flask import Flask, render_template
import pyodbc
import pandas as pd
from datetime import datetime

app = Flask(__name__)

# Database configuration
DB_CONFIG = {
    'server': 'sqlexpressva.c2xw7rscu4uh.us-east-1.rds.amazonaws.com',
    'database': 'Prima',
    'username': 'mlefter_dbeaver',
    'password': 'lefter01',
    'port': '1433'
}

def get_db_connection():
    conn_str = (
        f"DRIVER={{SQL Server}};"
        f"SERVER={DB_CONFIG['server']},{DB_CONFIG['port']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['username']};"
        f"PWD={DB_CONFIG['password']}"
    )
    return pyodbc.connect(conn_str)

@app.route('/')
def index():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("EXEC dbo.sp_Debulk_Today 'PLL', 'GREER'")
        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        data = [dict(zip(columns, row)) for row in rows]
        cursor.close()
        conn.close()
        
        return render_template('index.html', data=data, columns=columns, datetime=datetime)
    
    except Exception as e:
        return f"An error occurred: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True)