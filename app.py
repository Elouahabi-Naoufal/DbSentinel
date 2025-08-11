import os
import sqlite3
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import tempfile
import shutil

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'db', 'sqlite', 'sqlite3'}

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def test_database_connection(db_path, password=None):
    """Test if database can be opened, return (success, is_encrypted, error_message)."""
    try:
        # First try without password
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        cursor.fetchall()
        conn.close()
        return True, False, None
    except sqlite3.DatabaseError as e:
        error_msg = str(e).lower()
        if 'file is not a database' in error_msg or 'file is encrypted' in error_msg:
            # Database might be encrypted
            if password:
                try:
                    # Note: In a real implementation, you'd use pysqlcipher3 here
                    # For this web version, we'll simulate the check
                    return False, True, "SQLCipher encrypted databases require desktop application with pysqlcipher3"
                except Exception as e:
                    return False, True, f"Password incorrect: {str(e)}"
            else:
                return False, True, "Database appears to be encrypted. Password required."
        else:
            return False, False, f"Database error: {str(e)}"

def get_tables(db_path):
    """Get list of tables from the database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tables
    except Exception as e:
        raise Exception(f"Error getting tables: {str(e)}")

def get_table_data(db_path, table_name, page=1, per_page=100):
    """Get data from a specific table with pagination."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get column information
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Get total count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        total_count = cursor.fetchone()[0]
        
        # Get paginated data
        offset = (page - 1) * per_page
        cursor.execute(f"SELECT * FROM {table_name} LIMIT {per_page} OFFSET {offset}")
        rows = cursor.fetchall()
        
        conn.close()
        
        return {
            'columns': columns,
            'rows': rows,
            'total_count': total_count,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_count + per_page - 1) // per_page
        }
    except Exception as e:
        raise Exception(f"Error getting table data: {str(e)}")

def execute_query(db_path, query, params=None):
    """Execute a query on the database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if query.strip().upper().startswith('SELECT'):
            result = cursor.fetchall()
            conn.close()
            return result
        else:
            conn.commit()
            conn.close()
            return True
    except Exception as e:
        raise Exception(f"Query error: {str(e)}")

@app.route('/')
def index():
    """Main page for file upload."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle database file upload."""
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Add timestamp to avoid conflicts
        import time
        filename = f"{int(time.time())}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Test database connection
        success, is_encrypted, error_msg = test_database_connection(filepath)
        
        if success:
            session['db_path'] = filepath
            session['db_name'] = file.filename
            return redirect(url_for('database_view'))
        elif is_encrypted:
            session['temp_db_path'] = filepath
            session['db_name'] = file.filename
            flash(error_msg, 'warning')
            return render_template('index.html', show_password=True)
        else:
            os.remove(filepath)  # Clean up invalid file
            flash(error_msg, 'error')
            return redirect(url_for('index'))
    else:
        flash('Invalid file type. Please upload .db, .sqlite, or .sqlite3 files', 'error')
        return redirect(url_for('index'))

@app.route('/unlock', methods=['POST'])
def unlock_database():
    """Handle password unlock for encrypted databases."""
    password = request.form.get('password')
    temp_path = session.get('temp_db_path')
    
    if not temp_path or not password:
        flash('Missing database or password', 'error')
        return redirect(url_for('index'))
    
    # Test with password
    success, is_encrypted, error_msg = test_database_connection(temp_path, password)
    
    if success:
        session['db_path'] = temp_path
        session.pop('temp_db_path', None)
        return redirect(url_for('database_view'))
    else:
        flash(error_msg, 'error')
        return render_template('index.html', show_password=True)

@app.route('/database')
def database_view():
    """Main database exploration interface."""
    db_path = session.get('db_path')
    if not db_path or not os.path.exists(db_path):
        flash('No database loaded', 'error')
        return redirect(url_for('index'))
    
    try:
        tables = get_tables(db_path)
        db_name = session.get('db_name', 'Unknown')
        return render_template('database.html', tables=tables, db_name=db_name)
    except Exception as e:
        flash(f'Error loading database: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/api/table/<table_name>')
def get_table_api(table_name):
    """API endpoint to get table data."""
    db_path = session.get('db_path')
    if not db_path:
        return jsonify({'error': 'No database loaded'}), 400
    
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 100, type=int)
        data = get_table_data(db_path, table_name, page, per_page)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/table/<table_name>/add', methods=['POST'])
def add_row_api(table_name):
    """API endpoint to add a new row."""
    db_path = session.get('db_path')
    if not db_path:
        return jsonify({'error': 'No database loaded'}), 400
    
    try:
        data = request.json
        columns = data.get('columns', [])
        values = data.get('values', [])
        
        # Build INSERT query
        placeholders = ', '.join(['?' for _ in values])
        column_names = ', '.join(columns)
        query = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"
        
        execute_query(db_path, query, values)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/table/<table_name>/update', methods=['POST'])
def update_row_api(table_name):
    """API endpoint to update a row."""
    db_path = session.get('db_path')
    if not db_path:
        return jsonify({'error': 'No database loaded'}), 400
    
    try:
        data = request.json
        row_id = data.get('row_id')
        column = data.get('column')
        value = data.get('value')
        
        # Simple update based on ROWID (assuming SQLite)
        query = f"UPDATE {table_name} SET {column} = ? WHERE ROWID = ?"
        execute_query(db_path, query, [value, row_id])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/table/<table_name>/delete', methods=['POST'])
def delete_row_api(table_name):
    """API endpoint to delete rows."""
    db_path = session.get('db_path')
    if not db_path:
        return jsonify({'error': 'No database loaded'}), 400
    
    try:
        data = request.json
        row_ids = data.get('row_ids', [])
        
        for row_id in row_ids:
            query = f"DELETE FROM {table_name} WHERE ROWID = ?"
            execute_query(db_path, query, [row_id])
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/close')
def close_database():
    """Close current database and return to main page."""
    db_path = session.get('db_path')
    if db_path and os.path.exists(db_path):
        try:
            os.remove(db_path)
        except:
            pass  # File might be in use
    
    session.clear()
    flash('Database closed', 'info')
    return redirect(url_for('index'))

@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    flash('File too large. Maximum size is 100MB', 'error')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
