#!/usr/bin/env python3
"""
SQLite Database Explorer - PyQt5 Desktop Application
====================================================

A comprehensive desktop application for exploring SQLite databases with full SQLCipher support.

Installation Requirements:
--------------------------
pip install PyQt5 pysqlcipher3

For Ubuntu/Debian systems, you may also need:
sudo apt-get install libsqlcipher-dev

Usage:
------
python sqlite_explorer.py

Features:
---------
- File browser dialog to select SQLite/SQLCipher database files
- Automatic detection of encrypted databases
- Password prompt for encrypted databases with retry mechanism
- Table explorer sidebar (VS Code-style)
- Full table data display with sortable columns
- Complete CRUD operations (Create, Read, Update, Delete)
- Direct cell editing with immediate database updates
- Add new rows via dialog forms
- Delete selected rows with confirmation
- Clean separation of UI and database logic
- Green-on-white theme styling
- Comprehensive error handling and input validation

Author: SQLite Explorer
Version: 1.0
"""

import sys
import os
import sqlite3
import io
import tempfile
import logging
from typing import Optional, List, Tuple, Any

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QInputDialog, QDialog,
    QDialogButtonBox, QFormLayout, QLineEdit, QLabel, QPushButton,
    QAbstractItemView, QCheckBox, QFrame, QComboBox, QScrollArea,
    QGroupBox, QGridLayout, QTextEdit, QSlider, QActionGroup
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QUrl, QDateTime
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor, QPixmap
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget

# Try to import PIL for image processing
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Try to import PyMuPDF for PDF preview
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# Try to import additional libraries for comprehensive file support
try:
    import zipfile
    import tarfile
    ZIP_AVAILABLE = True
except ImportError:
    ZIP_AVAILABLE = False

try:
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name, guess_lexer
    from pygments.formatters import HtmlFormatter
    PYGMENTS_AVAILABLE = True
except ImportError:
    PYGMENTS_AVAILABLE = False

try:
    import openpyxl
    import pandas as pd
    OFFICE_LIBS_AVAILABLE = True
except ImportError:
    OFFICE_LIBS_AVAILABLE = False

# Try to import pysqlcipher3 for encrypted database support
try:
    from pysqlcipher3 import dbapi2 as sqlcipher
    SQLCIPHER_AVAILABLE = True
except ImportError:
    SQLCIPHER_AVAILABLE = False
    sqlcipher = None


class DatabaseManager:
    """
    Handles all database operations including connection management,
    encrypted database detection, and CRUD operations.
    """
    
    def __init__(self):
        self.connection = None
        self.db_path = None
        self.is_encrypted = False
        self.password = None
    
    def test_database(self, db_path: str, password: str = None) -> Tuple[bool, bool, str]:
        """
        Test if database can be opened and detect if it's encrypted.
        
        Returns:
            (success, is_encrypted, error_message)
        """
        try:
            # First try with regular sqlite3
            if password is None:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1;")
                cursor.fetchone()
                conn.close()
                return True, False, ""
            else:
                # Password provided, try SQLCipher first
                if SQLCIPHER_AVAILABLE:
                    try:
                        conn = sqlcipher.connect(db_path)
                        cursor = conn.cursor()
                        cursor.execute(f"PRAGMA key = '{password}';")
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1;")
                        cursor.fetchone()
                        conn.close()
                        return True, True, ""
                    except Exception as cipher_error:
                        return False, True, f"Incorrect password or corrupted encrypted database: {str(cipher_error)}"
                else:
                    return False, True, "SQLCipher support not available. Install pysqlcipher3: pip install pysqlcipher3"
        except sqlite3.DatabaseError as e:
            error_msg = str(e).lower()
            if 'file is not a database' in error_msg or 'file is encrypted' in error_msg or 'malformed' in error_msg:
                # Database might be encrypted
                if not SQLCIPHER_AVAILABLE:
                    return False, True, "SQLCipher support not available. Install pysqlcipher3: pip install pysqlcipher3"
                else:
                    return False, True, "Database appears to be encrypted. Please provide password."
            else:
                return False, False, f"Database error: {str(e)}"
        except Exception as e:
            return False, False, f"Unexpected error: {str(e)}"
    
    def connect(self, db_path: str, password: str = None) -> bool:
        """Connect to the database."""
        try:
            if password and SQLCIPHER_AVAILABLE:
                self.connection = sqlcipher.connect(db_path)
                cursor = self.connection.cursor()
                cursor.execute(f"PRAGMA key = '{password}';")
                # Test the connection
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1;")
                cursor.fetchone()
                self.is_encrypted = True
                self.password = password
            else:
                self.connection = sqlite3.connect(db_path)
                self.is_encrypted = False
                self.password = None
            
            self.db_path = db_path
            return True
        except Exception as e:
            raise Exception(f"Failed to connect to database: {str(e)}")
    
    def disconnect(self):
        """Disconnect from the database."""
        if self.connection:
            self.connection.close()
            self.connection = None
        self.db_path = None
        self.is_encrypted = False
        self.password = None
    
    def get_tables(self) -> List[str]:
        """Get list of all tables in the database."""
        if not self.connection:
            raise Exception("No database connection")
        
        cursor = self.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        return [row[0] for row in cursor.fetchall()]
    
    def get_table_info(self, table_name: str) -> List[Tuple[str, str]]:
        """Get column information for a table."""
        if not self.connection:
            raise Exception("No database connection")
        
        cursor = self.connection.cursor()
        cursor.execute(f"PRAGMA table_info({table_name});")
        return [(row[1], row[2]) for row in cursor.fetchall()]  # (name, type)
    
    def get_table_data(self, table_name: str) -> Tuple[List[str], List[List[Any]], dict]:
        """Get all data from a table with column type information."""
        if not self.connection:
            raise Exception("No database connection")
        
        cursor = self.connection.cursor()
        
        # Get column names and types
        cursor.execute(f"PRAGMA table_info({table_name});")
        table_info = cursor.fetchall()
        columns = [row[1] for row in table_info]
        column_types = {row[1]: row[2] for row in table_info}
        
        # Add rowid to column types
        column_types['rowid'] = 'INTEGER'
        
        # Get data
        cursor.execute(f"SELECT rowid, * FROM {table_name};")
        rows = cursor.fetchall()
        
        return ['rowid'] + columns, rows, column_types
    
    def insert_row(self, table_name: str, data: dict) -> bool:
        """Insert a new row into the table."""
        if not self.connection:
            raise Exception("No database connection")
        
        # Filter out None values
        filtered_data = {k: v for k, v in data.items() if v is not None}
        
        if not filtered_data:
            return False
        
        print(f"DEBUG INSERT: table={table_name}, data keys={list(filtered_data.keys())}")
        sys.stdout.flush()
        
        columns = list(filtered_data.keys())
        values = []
        
        # Process values, converting bytes to sqlite3.Binary
        for k, v in filtered_data.items():
            if isinstance(v, bytes):
                print(f"DEBUG INSERT: Column {k} is BLOB with {len(v)} bytes")
                values.append(sqlite3.Binary(v))
            else:
                print(f"DEBUG INSERT: Column {k} is {type(v)} with value {repr(v)[:50]}")
                values.append(v)
        
        placeholders = ', '.join(['?' for _ in values])
        column_names = ', '.join(columns)
        
        query = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"
        print(f"DEBUG INSERT: Query={query}")
        
        cursor = self.connection.cursor()
        cursor.execute(query, values)
        self.connection.commit()
        
        # Get the inserted row ID and verify
        rowid = cursor.lastrowid
        print(f"DEBUG INSERT: Inserted with rowid={rowid}")
        
        cursor.close()
        return True
    
    def update_cell(self, table_name: str, rowid: int, column: str, value: Any) -> bool:
        """Update a single cell in the table."""
        if not self.connection:
            raise Exception("No database connection")
        
        cursor = self.connection.cursor()
        
        # Debug logging
        print(f"DEBUG UPDATE: table={table_name}, rowid={rowid}, column={column}")
        print(f"DEBUG UPDATE: value type={type(value)}, length={len(value) if hasattr(value, '__len__') else 'N/A'}")
        sys.stdout.flush()
        
        # Handle BLOB data with proper SQLite BLOB support
        if isinstance(value, bytes):
            query = f"UPDATE {table_name} SET {column} = ? WHERE rowid = ?"
            print(f"DEBUG UPDATE: Using sqlite3.Binary for BLOB data")
            cursor.execute(query, (sqlite3.Binary(value), rowid))
        else:
            query = f"UPDATE {table_name} SET {column} = ? WHERE rowid = ?"
            cursor.execute(query, (value, rowid))
        
        self.connection.commit()
        
        # Verify the update
        cursor.execute(f"SELECT {column} FROM {table_name} WHERE rowid = ?", (rowid,))
        result = cursor.fetchone()
        print(f"DEBUG UPDATE VERIFY: Retrieved data type={type(result[0]) if result else 'None'}, length={len(result[0]) if result and hasattr(result[0], '__len__') else 'N/A'}")
        
        cursor.close()
        return True
    
    def delete_rows(self, table_name: str, rowids: List[int]) -> bool:
        """Delete rows from the table."""
        if not self.connection:
            raise Exception("No database connection")
        
        cursor = self.connection.cursor()
        for rowid in rowids:
            cursor.execute(f"DELETE FROM {table_name} WHERE rowid = ?", (rowid,))
        self.connection.commit()
        return True
    
    def create_table(self, table_name: str, columns: List[dict]) -> bool:
        """Create a new table with specified columns."""
        if not self.connection:
            raise Exception("No database connection")
        
        column_defs = []
        for col in columns:
            col_def = f"{col['name']} {col['type']}"
            if col.get('primary_key'):
                col_def += " PRIMARY KEY"
            if col.get('not_null'):
                col_def += " NOT NULL"
            if col.get('unique'):
                col_def += " UNIQUE"
            if col.get('default'):
                col_def += f" DEFAULT {col['default']}"
            column_defs.append(col_def)
        
        query = f"CREATE TABLE {table_name} ({', '.join(column_defs)})"
        cursor = self.connection.cursor()
        cursor.execute(query)
        self.connection.commit()
        return True
    
    def add_column(self, table_name: str, column: dict) -> bool:
        """Add a new column to an existing table."""
        if not self.connection:
            raise Exception("No database connection")
        
        col_def = f"{column['name']} {column['type']}"
        if column.get('not_null'):
            col_def += " NOT NULL"
        if column.get('unique'):
            col_def += " UNIQUE"
        if column.get('default'):
            col_def += f" DEFAULT {column['default']}"
        
        query = f"ALTER TABLE {table_name} ADD COLUMN {col_def}"
        cursor = self.connection.cursor()
        cursor.execute(query)
        self.connection.commit()
        return True


class AddColumnDialog(QDialog):
    """Dialog for adding a column to an existing table."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("Add Column")
        self.setModal(True)
        self.resize(400, 300)
        self.setStyleSheet("""
            QDialog { background-color: white; }
            QLineEdit, QComboBox { padding: 8px; border: 2px solid #e9ecef; border-radius: 6px; font-size: 13px; }
            QLineEdit:focus, QComboBox:focus { border-color: #007bff; }
            QCheckBox { font-size: 13px; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Add New Column")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #2c3e50; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Form layout
        form_layout = QGridLayout()
        form_layout.setSpacing(10)
        
        # Column name
        form_layout.addWidget(QLabel("Column Name:"), 0, 0)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter column name")
        form_layout.addWidget(self.name_edit, 0, 1)
        
        # Column type
        form_layout.addWidget(QLabel("Data Type:"), 1, 0)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["TEXT", "INTEGER", "REAL", "BLOB", "NUMERIC", "VARCHAR(255)", "DATE", "DATETIME"])
        form_layout.addWidget(self.type_combo, 1, 1)
        
        # Constraints
        self.not_null_check = QCheckBox("Not Null")
        self.unique_check = QCheckBox("Unique")
        form_layout.addWidget(self.not_null_check, 2, 0)
        form_layout.addWidget(self.unique_check, 2, 1)
        
        # Default value
        form_layout.addWidget(QLabel("Default Value:"), 3, 0)
        self.default_edit = QLineEdit()
        self.default_edit.setPlaceholderText("Optional default value")
        form_layout.addWidget(self.default_edit, 3, 1)
        
        layout.addLayout(form_layout)
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        add_btn = QPushButton("Add Column")
        add_btn.clicked.connect(self.accept)
        add_btn.setProperty("class", "success")
        button_layout.addWidget(add_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def get_column_data(self):
        """Get column definition."""
        name = self.name_edit.text().strip()
        if not name:
            raise ValueError("Column name is required")
        
        return {
            'name': name,
            'type': self.type_combo.currentText(),
            'not_null': self.not_null_check.isChecked(),
            'unique': self.unique_check.isChecked(),
            'default': self.default_edit.text().strip() or None
        }


class CreateTableDialog(QDialog):
    """Dialog for creating new tables."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.columns = []
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("Create New Table")
        self.setModal(True)
        self.resize(700, 600)
        self.setStyleSheet("""
            QDialog { background-color: white; }
            QLineEdit, QComboBox { padding: 8px; border: 2px solid #e9ecef; border-radius: 6px; font-size: 13px; }
            QLineEdit:focus, QComboBox:focus { border-color: #007bff; }
            QGroupBox { font-weight: bold; padding-top: 10px; }
            QCheckBox { font-size: 13px; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Create New Table")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #2c3e50; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Table name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Table Name:"))
        self.table_name_edit = QLineEdit()
        self.table_name_edit.setPlaceholderText("Enter table name")
        name_layout.addWidget(self.table_name_edit)
        layout.addLayout(name_layout)
        
        # Columns section
        columns_group = QGroupBox("Columns")
        columns_layout = QVBoxLayout(columns_group)
        
        # Scroll area for columns
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(300)
        
        self.columns_widget = QWidget()
        self.columns_layout = QVBoxLayout(self.columns_widget)
        scroll.setWidget(self.columns_widget)
        
        columns_layout.addWidget(scroll)
        
        # Add column button
        add_col_btn = QPushButton("➕ Add Column")
        add_col_btn.clicked.connect(self.add_column)
        add_col_btn.setProperty("class", "success")
        columns_layout.addWidget(add_col_btn)
        
        layout.addWidget(columns_group)
        
        # Add first column by default
        self.add_column()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        create_btn = QPushButton("Create Table")
        create_btn.clicked.connect(self.accept)
        create_btn.setProperty("class", "success")
        button_layout.addWidget(create_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def add_column(self):
        """Add a new column configuration row."""
        col_widget = QWidget()
        col_layout = QGridLayout(col_widget)
        col_layout.setSpacing(10)
        
        row = len(self.columns)
        
        # Column name
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("Column name")
        col_layout.addWidget(QLabel("Name:"), 0, 0)
        col_layout.addWidget(name_edit, 0, 1)
        
        # Column type
        type_combo = QComboBox()
        type_combo.addItems(["TEXT", "INTEGER", "REAL", "BLOB", "NUMERIC", "VARCHAR(255)", "DATE", "DATETIME"])
        col_layout.addWidget(QLabel("Type:"), 0, 2)
        col_layout.addWidget(type_combo, 0, 3)
        
        # Constraints
        pk_check = QCheckBox("Primary Key")
        not_null_check = QCheckBox("Not Null")
        unique_check = QCheckBox("Unique")
        
        col_layout.addWidget(pk_check, 1, 0)
        col_layout.addWidget(not_null_check, 1, 1)
        col_layout.addWidget(unique_check, 1, 2)
        
        # Default value
        default_edit = QLineEdit()
        default_edit.setPlaceholderText("Default value (optional)")
        col_layout.addWidget(QLabel("Default:"), 1, 3)
        col_layout.addWidget(default_edit, 1, 4)
        
        # Remove button
        remove_btn = QPushButton("🗑️")
        remove_btn.setMaximumWidth(40)
        remove_btn.clicked.connect(lambda: self.remove_column(col_widget))
        remove_btn.setProperty("class", "danger")
        col_layout.addWidget(remove_btn, 0, 5)
        
        self.columns_layout.addWidget(col_widget)
        
        # Store references
        column_data = {
            'widget': col_widget,
            'name_edit': name_edit,
            'type_combo': type_combo,
            'pk_check': pk_check,
            'not_null_check': not_null_check,
            'unique_check': unique_check,
            'default_edit': default_edit
        }
        self.columns.append(column_data)
    
    def remove_column(self, widget):
        """Remove a column configuration row."""
        if len(self.columns) <= 1:
            QMessageBox.warning(self, "Warning", "Table must have at least one column.")
            return
        
        # Find and remove the column
        for i, col in enumerate(self.columns):
            if col['widget'] == widget:
                self.columns_layout.removeWidget(widget)
                widget.deleteLater()
                del self.columns[i]
                break
    
    def get_table_data(self):
        """Get table name and column definitions."""
        table_name = self.table_name_edit.text().strip()
        if not table_name:
            raise ValueError("Table name is required")
        
        columns = []
        for col_data in self.columns:
            name = col_data['name_edit'].text().strip()
            if not name:
                raise ValueError("All columns must have names")
            
            column = {
                'name': name,
                'type': col_data['type_combo'].currentText(),
                'primary_key': col_data['pk_check'].isChecked(),
                'not_null': col_data['not_null_check'].isChecked(),
                'unique': col_data['unique_check'].isChecked(),
                'default': col_data['default_edit'].text().strip() or None
            }
            columns.append(column)
        
        return table_name, columns


class BlobPreviewDialog(QDialog):
    """Dialog for previewing blob content."""
    
    def __init__(self, blob_data: bytes, column_name: str, parent=None):
        super().__init__(parent)
        self.blob_data = blob_data
        self.column_name = column_name
        self.seeking = False
        self.temp_files = []
        self.setup_ui()
        self.apply_theme()
    
    def setup_ui(self):
        self.setWindowTitle(f"Preview: {self.column_name}")
        self.setModal(True)
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        
        # Fixed header - won't expand
        header = QLabel(f"Content Preview - {self.column_name} ({len(self.blob_data)} bytes)")
        header.setFont(QFont("Segoe UI", 12, QFont.Bold))
        header.setObjectName("headerLabel")
        header.setFixedHeight(50)
        layout.addWidget(header)
        
        # Expandable content area - this will grow when dialog is resized
        self.content_widget = self.create_content_widget()
        layout.addWidget(self.content_widget, 1)  # stretch factor = 1
        
        # Fixed buttons - won't expand
        button_layout = QHBoxLayout()
        button_widget = QWidget()
        button_widget.setLayout(button_layout)
        button_widget.setFixedHeight(50)
        
        save_btn = QPushButton("Save As...")
        save_btn.setObjectName("saveButton")
        save_btn.clicked.connect(self.save_blob)
        button_layout.addWidget(save_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setObjectName("closeButton")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addWidget(button_widget)
    
    def apply_theme(self):
        """Apply current theme to dialog."""
        parent_window = self.parent()
        while parent_window and not hasattr(parent_window, 'current_theme'):
            parent_window = parent_window.parent()
        
        if parent_window and hasattr(parent_window, 'current_theme') and parent_window.current_theme == 'dark':
            style = """
            * { background-color: #020B1A; color: #FFFFFF; font-weight: bold; }
            QDialog { background-color: #020B1A; color: #FFFFFF; font-weight: bold; }
            QWidget { background-color: #020B1A; color: #FFFFFF; font-weight: bold; }
            QFrame { background-color: #020B1A; color: #FFFFFF; }
            QScrollArea { background-color: #020B1A; border: none; }
            QScrollArea QWidget { background-color: #020B1A; }
            QScrollArea > QWidget > QWidget { background-color: #020B1A; }
            QVBoxLayout { background-color: #020B1A; }
            QHBoxLayout { background-color: #020B1A; }
            QLabel { color: #FFFFFF; font-weight: bold; text-shadow: 0 0 3px #00AFFF; background-color: #020B1A; border: none; }
            QLabel#headerLabel { color: #FFFFFF; font-weight: bold; text-shadow: 0 0 5px #00AFFF; background-color: #001122; padding: 10px; border-radius: 6px; }
            QLabel#pdfHeader { color: #FFFFFF; font-weight: bold; text-shadow: 0 0 5px #FF0033; background-color: #1a0000; padding: 10px; border-radius: 6px; }
            QLabel#pdfPreviewHeader { color: #FFFFFF; font-weight: bold; text-shadow: 0 0 5px #00AFFF; background-color: #001122; padding: 8px; border-radius: 4px; }
            QLabel#docHeader { color: #FFFFFF; font-weight: bold; background-color: #001a33; padding: 10px; border-radius: 6px; }
            QLabel#rtfHeader { color: #FFFFFF; font-weight: bold; background-color: #1a1a00; padding: 10px; border-radius: 6px; }
            QPushButton { background-color: #00AFFF; color: #FFFFFF; border: 2px solid #00F6FF; padding: 12px 24px; border-radius: 8px; font-weight: bold; font-size: 14px; text-shadow: 0 0 8px #FFFFFF; min-width: 100px; }
            QPushButton:hover { background-color: #FF0033; color: #FFFFFF; border-color: #FF7700; text-shadow: 0 0 15px #FFFFFF; }
            QPushButton#pdfOpenButton { background-color: #0084FF; color: #FFFFFF; border: 2px solid #00F6FF; padding: 8px 16px; }
            QPushButton#pdfSystemButton { background-color: #FF0033; color: #FFFFFF; border: 2px solid #FF7700; padding: 12px 16px; }
            QPushButton#saveButton { background-color: #00AFFF; color: #FFFFFF; border: 2px solid #00F6FF; padding: 8px 16px; min-width: 80px; }
            QPushButton#closeButton { background-color: #FF0033; color: #FFFFFF; border: 2px solid #FF7700; padding: 8px 16px; min-width: 80px; }
            QTextEdit { background-color: #001122; color: #FFFFFF; border: 2px solid #00AFFF; border-radius: 8px; font-weight: bold; }
            QWebEngineView { background-color: #020B1A; }
            QVideoWidget { background-color: #020B1A; }
            QSlider { background-color: #020B1A; }
            QSlider::groove:horizontal { background-color: #001122; border: 1px solid #00AFFF; height: 4px; }
            QSlider::handle:horizontal { background-color: #00AFFF; border: 1px solid #00F6FF; width: 12px; margin: -4px 0; border-radius: 6px; }
            QComboBox { background-color: #001122; color: #FFFFFF; border: 2px solid #00AFFF; padding: 4px; }
            QComboBox::drop-down { background-color: #00AFFF; }
            QComboBox::down-arrow { color: #FFFFFF; }
            QGroupBox { background-color: #020B1A; color: #FFFFFF; border: 2px solid #00AFFF; border-radius: 6px; }
            QGroupBox::title { color: #FFFFFF; font-weight: bold; text-shadow: 0 0 5px #00AFFF; }
            """
        else:
            style = """
            * { background-color: #FDFDFD; color: #000000; font-weight: bold; }
            QDialog { background-color: #FDFDFD; color: #000000; font-weight: bold; }
            QLabel { color: #000000; font-weight: bold; background-color: #FDFDFD; }
            QLabel#headerLabel { color: #000000; font-weight: bold; background-color: #f8f9fa; padding: 10px; border-radius: 6px; }
            QLabel#pdfHeader { color: #000000; font-weight: bold; background-color: #ffebee; padding: 10px; border-radius: 6px; }
            QLabel#pdfPreviewHeader { color: #000000; font-weight: bold; background-color: #e8f5e8; padding: 8px; border-radius: 4px; }
            QPushButton { background-color: #0057FF; color: #FFFFFF; border: 2px solid #222222; padding: 12px 24px; border-radius: 8px; font-weight: bold; font-size: 14px; min-width: 100px; }
            QPushButton:hover { background-color: #FF0033; color: #FFFFFF; border-color: #000000; }
            QPushButton#pdfOpenButton { background-color: #0084FF; color: #FFFFFF; border: 2px solid #222222; padding: 8px 16px; }
            QPushButton#pdfSystemButton { background-color: #FF0033; color: #FFFFFF; border: 2px solid #222222; padding: 12px 16px; }
            QPushButton#saveButton { background-color: #0057FF; color: #FFFFFF; border: 2px solid #222222; padding: 8px 16px; min-width: 80px; }
            QPushButton#closeButton { background-color: #FF0033; color: #FFFFFF; border: 2px solid #222222; padding: 8px 16px; min-width: 80px; }
            QLabel#docHeader { color: #000000; font-weight: bold; background-color: #e3f2fd; padding: 10px; border-radius: 6px; }
            QLabel#rtfHeader { color: #000000; font-weight: bold; background-color: #fff3cd; padding: 10px; border-radius: 6px; }
            QTextEdit { background-color: #FFFFFF; color: #000000; border: 2px solid #222222; border-radius: 8px; font-weight: bold; }
            QScrollArea { background-color: #FDFDFD; }
            QWidget { background-color: #FDFDFD; color: #000000; }
            QFrame { background-color: #FDFDFD; color: #000000; }
            """
        
        self.setStyleSheet(style)
    
    def create_content_widget(self) -> QWidget:
        """Create appropriate widget based on blob content type."""
        content_type = self.detect_content_type()
        
        if content_type == 'image':
            return self.create_image_widget()
        elif content_type == 'text':
            return self.create_text_widget()
        elif content_type == 'markdown':
            return self.create_markdown_widget()
        elif content_type == 'video':
            return self.create_video_widget()
        elif content_type == 'audio':
            return self.create_audio_widget()
        elif content_type == 'pdf':
            return self.create_pdf_widget()
        elif content_type == 'document':
            return self.create_document_widget()
        elif content_type == 'archive':
            return self.create_archive_widget()
        elif content_type == 'code':
            return self.create_code_widget()
        elif content_type == 'markup':
            return self.create_markup_widget()
        elif content_type == 'json':
            return self.create_json_widget()
        elif content_type == 'font':
            return self.create_font_widget()
        elif content_type == 'executable':
            return self.create_executable_widget()
        else:
            return self.create_hex_widget()
    
    def detect_content_type(self) -> str:
        """Detect content type from blob data."""
        if not self.blob_data:
            return 'empty'
        
        # Check for archive formats first
        if self.blob_data.startswith(b'PK\x03\x04'):  # ZIP
            if (b'word/' in self.blob_data[:1000] or b'xl/' in self.blob_data[:1000] or
                b'ppt/' in self.blob_data[:1000] or b'content.xml' in self.blob_data[:1000]):
                return 'document'
            return 'archive'
        elif (self.blob_data.startswith(b'\x1f\x8b') or  # GZIP
              self.blob_data.startswith(b'BZh') or  # BZIP2
              self.blob_data.startswith(b'7z\xbc\xaf\x27\x1c') or  # 7Z
              self.blob_data.startswith(b'Rar!\x1a\x07\x00')):
            return 'archive'
        
        # Check for image formats
        elif self.blob_data.startswith(b'\xff\xd8\xff'):  # JPEG
            return 'image'
        elif self.blob_data.startswith(b'\x89PNG\r\n\x1a\n'):  # PNG
            return 'image'
        elif self.blob_data.startswith(b'GIF8'):  # GIF
            return 'image'
        elif self.blob_data.startswith(b'BM'):  # BMP
            return 'image'
        elif self.blob_data.startswith(b'RIFF') and b'WEBP' in self.blob_data[:12]:  # WebP
            return 'image'
        elif self.blob_data.startswith(b'<svg') or b'<SVG' in self.blob_data[:100]:  # SVG
            return 'image'
        
        # Check for video formats
        elif (self.blob_data.startswith(b'\x00\x00\x00\x18ftyp') or  # MP4, MOV, M4V
              self.blob_data.startswith(b'\x00\x00\x00\x20ftyp') or
              self.blob_data.startswith(b'\x1a\x45\xdf\xa3') or  # MKV/WebM
              self.blob_data.startswith(b'RIFF') and b'AVI ' in self.blob_data[:12] or  # AVI
              self.blob_data.startswith(b'\x00\x00\x01\xba') or  # MPEG
              self.blob_data.startswith(b'FLV\x01')):  # FLV
            return 'video'
        
        # Check for audio formats
        elif (self.blob_data.startswith(b'ID3') or  # MP3 with ID3
              self.blob_data.startswith(b'\xff\xfb') or  # MP3
              self.blob_data.startswith(b'\xff\xf3') or  # MP3
              self.blob_data.startswith(b'\xff\xf2') or  # MP3
              self.blob_data.startswith(b'\x00\x00\x00\x20ftypM4A') or  # M4A
              self.blob_data.startswith(b'fLaC') or  # FLAC
              self.blob_data.startswith(b'OggS') or  # OGG/Vorbis
              self.blob_data.startswith(b'RIFF') and b'WAVE' in self.blob_data[:12] or  # WAV
              self.blob_data.startswith(b'wvpk') or  # WavPack
              self.blob_data.startswith(b'MAC ')):  # APE
            return 'audio'
        
        # Check for font formats
        elif (self.blob_data.startswith(b'\x00\x01\x00\x00') or  # TTF
              self.blob_data.startswith(b'OTTO') or  # OTF
              self.blob_data.startswith(b'wOFF') or  # WOFF
              self.blob_data.startswith(b'wOF2')):  # WOFF2
            return 'font'
        
        # Check for executable formats
        elif (self.blob_data.startswith(b'MZ') or  # Windows EXE/DLL
              self.blob_data.startswith(b'\x7fELF') or  # Linux ELF
              self.blob_data.startswith(b'\xca\xfe\xba\xbe')):  # Mach-O
            return 'executable'
        
        # Check for document formats
        elif self.blob_data.startswith(b'%PDF'):  # PDF
            return 'pdf'
        elif (self.blob_data.startswith(b'\xd0\xcf\x11\xe0') or  # DOC, XLS, PPT
              self.blob_data.startswith(b'{\\rtf')):
            return 'document'
        
        # Check if it's text-based content
        try:
            text_content = self.blob_data.decode('utf-8')
            
            # Check for specific text formats
            if text_content.strip().startswith(('<?xml', '<html', '<HTML')):
                return 'markup'
            elif text_content.strip().startswith(('{', '[')) and ('}' in text_content or ']' in text_content):
                return 'json'
            elif ('# ' in text_content or '## ' in text_content or 
                  '**' in text_content or '*' in text_content or
                  '[' in text_content and '](' in text_content):
                return 'markdown'
            elif any(keyword in text_content[:200] for keyword in ['def ', 'class ', 'import ', 'function', 'var ', 'const ']):
                return 'code'
            return 'text'
        except UnicodeDecodeError:
            pass
        
        return 'binary'
    
    def create_image_widget(self) -> QWidget:
        """Create widget for image preview."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        try:
            # Create QPixmap from blob data
            pixmap = QPixmap()
            pixmap.loadFromData(self.blob_data)
            
            if not pixmap.isNull():
                # Scale image to fit while maintaining aspect ratio
                scaled_pixmap = pixmap.scaled(700, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                
                image_label = QLabel()
                image_label.setPixmap(scaled_pixmap)
                image_label.setAlignment(Qt.AlignCenter)
                image_label.setStyleSheet("background-color: #020B1A !important; border: 2px solid #00AFFF !important;")
                
                # Add scroll area for large images
                scroll = QScrollArea()
                scroll.setWidget(image_label)
                scroll.setWidgetResizable(True)
                layout.addWidget(scroll)
                
                # Image info
                info_label = QLabel(f"Image: {pixmap.width()}x{pixmap.height()} pixels")
                info_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
                layout.addWidget(info_label)
            else:
                layout.addWidget(QLabel("Unable to display image"))
        except Exception as e:
            layout.addWidget(QLabel(f"Error loading image: {str(e)}"))
        
        return widget
    
    def create_text_widget(self) -> QWidget:
        """Create widget for text preview."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        try:
            text_content = self.blob_data.decode('utf-8')
            text_edit = QTextEdit()
            text_edit.setPlainText(text_content)
            text_edit.setReadOnly(True)
            text_edit.setFont(QFont("Consolas", 10))
            layout.addWidget(text_edit)
        except Exception as e:
            layout.addWidget(QLabel(f"Error decoding text: {str(e)}"))
        
        return widget
    
    def create_markdown_widget(self) -> QWidget:
        """Create widget for markdown preview."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        try:
            markdown_content = self.blob_data.decode('utf-8')
            html_content = self.markdown_to_html(markdown_content)
            
            web_view = QWebEngineView()
            web_view.setHtml(html_content)
            layout.addWidget(web_view)
        except Exception as e:
            layout.addWidget(QLabel(f"Error rendering markdown: {str(e)}"))
        
        return widget
    
    def create_video_widget(self) -> QWidget:
        """Create widget for video preview."""
        logger.debug("Creating video widget")
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        try:
            # Detect video format and use appropriate extension
            video_ext = self.get_video_extension()
            logger.debug(f"Creating temporary file for video with extension: {video_ext}")
            with tempfile.NamedTemporaryFile(suffix=video_ext, delete=False) as temp_file:
                temp_file.write(self.blob_data)
                temp_path = temp_file.name
            logger.debug(f"Temporary video file created: {temp_path}")
            
            logger.debug("Creating QVideoWidget and QMediaPlayer")
            
            # Fixed format info header
            format_info = self.get_video_format_info()
            info_header = QLabel(f"{format_info['icon']} {format_info['name']} | {format_info['description']}")
            info_header.setStyleSheet("background-color: #020B1A !important; color: #FFFFFF !important; font-size: 12px; padding: 8px; border: 2px solid #00AFFF; border-radius: 6px; margin-bottom: 5px;")
            info_header.setAlignment(Qt.AlignCenter)
            info_header.setFixedHeight(35)
            layout.addWidget(info_header)
            
            # Expandable video widget - grows with dialog
            self.video_widget = QVideoWidget()
            self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
            self.media_player.setVideoOutput(self.video_widget)
            
            layout.addWidget(self.video_widget, 1)  # stretch factor = 1
            
            # Fixed controls area - won't expand
            controls_widget = QWidget()
            controls_widget.setFixedHeight(80)
            controls_main_layout = QVBoxLayout(controls_widget)
            
            # Playback controls
            controls_layout = QHBoxLayout()
            
            play_btn = QPushButton("▶️ PLAY")
            play_btn.setStyleSheet("QPushButton { background-color: #00AFFF; color: #FFFFFF; border: 2px solid #00F6FF; padding: 8px 16px; border-radius: 6px; font-weight: bold; } QPushButton:hover { background-color: #FF0033; }")
            play_btn.clicked.connect(lambda: self.safe_media_action("play"))
            controls_layout.addWidget(play_btn)
            
            pause_btn = QPushButton("⏸️ PAUSE")
            pause_btn.setStyleSheet("QPushButton { background-color: #FF7700; color: #FFFFFF; border: 2px solid #00F6FF; padding: 8px 16px; border-radius: 6px; font-weight: bold; } QPushButton:hover { background-color: #FF0033; }")
            pause_btn.clicked.connect(lambda: self.safe_media_action("pause"))
            controls_layout.addWidget(pause_btn)
            
            stop_btn = QPushButton("⏹️ STOP")
            stop_btn.setStyleSheet("QPushButton { background-color: #FF0033; color: #FFFFFF; border: 2px solid #00F6FF; padding: 8px 16px; border-radius: 6px; font-weight: bold; } QPushButton:hover { background-color: #FF7700; }")
            stop_btn.clicked.connect(lambda: self.safe_media_action("stop"))
            controls_layout.addWidget(stop_btn)
            
            # Seek slider with smooth seeking
            from PyQt5.QtWidgets import QSlider
            self.seek_slider = QSlider(Qt.Horizontal)
            self.seek_slider.setStyleSheet("QSlider { background-color: #020B1A; } QSlider::groove:horizontal { background-color: #001122; border: 1px solid #00AFFF; height: 6px; border-radius: 3px; } QSlider::handle:horizontal { background-color: #00AFFF; border: 2px solid #00F6FF; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }")
            self.seek_slider.setMinimum(0)
            self.seek_slider.setMaximum(10000)  # Higher resolution for smooth seeking
            self.seek_slider.setPageStep(100)  # Smaller page steps
            self.seek_slider.setSingleStep(10)  # Smaller single steps
            self.seek_slider.sliderPressed.connect(self.on_seek_start)
            self.seek_slider.sliderReleased.connect(self.on_seek_end)
            self.seek_slider.sliderMoved.connect(self.on_seek_moved)  # Real-time seeking
            controls_layout.addWidget(self.seek_slider)
            
            # Time labels
            self.time_label = QLabel("00:00 / 00:00")
            self.time_label.setStyleSheet("QLabel { color: #FFFFFF; font-weight: bold; background-color: #020B1A; padding: 4px; }")
            self.time_label.setMinimumWidth(80)
            controls_layout.addWidget(self.time_label)
            
            controls_main_layout.addLayout(controls_layout)
            
            # Speed control
            speed_layout = QHBoxLayout()
            speed_label = QLabel("Speed:")
            speed_label.setStyleSheet("QLabel { color: #FFFFFF; font-weight: bold; background-color: #020B1A; }")
            speed_layout.addWidget(speed_label)
            
            self.speed_combo = QComboBox()
            self.speed_combo.setStyleSheet("QComboBox { background-color: #001122; color: #FFFFFF; border: 2px solid #00AFFF; padding: 4px; font-weight: bold; } QComboBox::drop-down { background-color: #00AFFF; } QComboBox::down-arrow { color: #FFFFFF; }")
            self.speed_combo.addItems(["0.25x", "0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"])
            self.speed_combo.setCurrentText("1.0x")
            self.speed_combo.currentTextChanged.connect(self.on_speed_changed)
            speed_layout.addWidget(self.speed_combo)
            
            speed_layout.addStretch()
            controls_main_layout.addLayout(speed_layout)
            
            layout.addWidget(controls_widget)
            
            # Connect media player signals
            self.media_player.positionChanged.connect(self.on_position_changed)
            self.media_player.durationChanged.connect(self.on_duration_changed)
            
            logger.debug("Loading video media")
            self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(temp_path)))
            self.temp_files.append(temp_path)
            logger.debug("Video widget created successfully")
            
        except Exception as e:
            logger.error(f"Error creating video widget: {e}")
            layout.addWidget(QLabel(f"Error loading video: {str(e)}"))
        
        return widget
    
    def create_audio_widget(self) -> QWidget:
        """Create widget for audio preview."""
        logger.debug("Creating audio widget")
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        try:
            # Detect audio format and use appropriate extension
            audio_ext = self.get_audio_extension()
            logger.debug(f"Creating temporary file for audio with extension: {audio_ext}")
            with tempfile.NamedTemporaryFile(suffix=audio_ext, delete=False) as temp_file:
                temp_file.write(self.blob_data)
                temp_path = temp_file.name
            logger.debug(f"Temporary audio file created: {temp_path}")
            
            # Fixed format-specific info
            format_info = self.get_audio_format_info()
            info_label = QLabel(f"{format_info['icon']} {format_info['name']}\n{len(self.blob_data)} bytes | {format_info['description']}")
            info_label.setStyleSheet("background-color: #020B1A !important; color: #FFFFFF !important; font-size: 14px; padding: 20px; text-align: center; border: 2px solid #00AFFF; border-radius: 8px; margin: 10px;")
            info_label.setAlignment(Qt.AlignCenter)
            info_label.setFixedHeight(100)
            layout.addWidget(info_label)
            
            logger.debug("Creating QMediaPlayer for audio")
            self.media_player = QMediaPlayer(None, QMediaPlayer.LowLatency)
            
            controls_layout = QHBoxLayout()
            controls_layout.addStretch()
            
            play_btn = QPushButton("▶️ Play")
            play_btn.clicked.connect(lambda: self.safe_media_action("play"))
            play_btn.setMinimumSize(80, 40)
            controls_layout.addWidget(play_btn)
            
            pause_btn = QPushButton("⏸️ Pause")
            pause_btn.clicked.connect(lambda: self.safe_media_action("pause"))
            pause_btn.setMinimumSize(80, 40)
            controls_layout.addWidget(pause_btn)
            
            stop_btn = QPushButton("⏹️ Stop")
            stop_btn.clicked.connect(lambda: self.safe_media_action("stop"))
            stop_btn.setMinimumSize(80, 40)
            controls_layout.addWidget(stop_btn)
            
            controls_layout.addStretch()
            
            # Fixed controls area
            controls_widget = QWidget()
            controls_widget.setLayout(controls_layout)
            controls_widget.setFixedHeight(60)
            layout.addWidget(controls_widget)
            
            layout.addStretch(1)  # This expands to fill space
            
            logger.debug("Loading audio media")
            self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(temp_path)))
            self.temp_files.append(temp_path)
            logger.debug("Audio widget created successfully")
            
        except Exception as e:
            logger.error(f"Error creating audio widget: {e}")
            layout.addWidget(QLabel(f"Error loading audio: {str(e)}"))
        
        return widget
    
    def markdown_to_html(self, markdown_text: str) -> str:
        """Convert markdown to HTML."""
        html = markdown_text
        
        import re
        html = re.sub(r'### (.*)', r'<h3>\1</h3>', html)
        html = re.sub(r'## (.*)', r'<h2>\1</h2>', html)
        html = re.sub(r'# (.*)', r'<h1>\1</h1>', html)
        html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html)
        html = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', html)
        html = html.replace('\n', '<br>\n')
        
        return f"<html><body style='font-family: Arial; padding: 20px;'>{html}</body></html>"
    
    def create_pdf_widget(self) -> QWidget:
        """Create widget for PDF preview."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        try:
            # Create temporary file for PDF
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_file.write(self.blob_data)
                temp_path = temp_file.name
            
            # PDF header info
            header = QLabel(f"📄 PDF Document ({len(self.blob_data)} bytes)")
            header.setObjectName("pdfHeader")
            layout.addWidget(header)
            
            # Try to render PDF preview if PyMuPDF is available
            if PYMUPDF_AVAILABLE:
                try:
                    pdf_preview = self.create_pdf_preview(temp_path)
                    if pdf_preview:
                        layout.addWidget(pdf_preview)
                    else:
                        layout.addWidget(self.create_pdf_fallback(temp_path))
                except:
                    layout.addWidget(self.create_pdf_fallback(temp_path))
            else:
                layout.addWidget(self.create_pdf_fallback(temp_path))
            
            # Store temp file for cleanup
            self.temp_files.append(temp_path)
            
        except Exception as e:
            layout.addWidget(QLabel(f"Error loading PDF: {str(e)}"))
        
        return widget
    
    def open_pdf_externally(self, pdf_path: str):
        """Open PDF with system default viewer."""
        try:
            import subprocess
            import platform
            
            system = platform.system()
            if system == "Darwin":  # macOS
                subprocess.run(["open", pdf_path])
            elif system == "Windows":
                subprocess.run(["start", pdf_path], shell=True)
            else:  # Linux
                subprocess.run(["xdg-open", pdf_path])
                
            logger.debug(f"Opened PDF externally: {pdf_path}")
            
            # Schedule PDF file for deletion after a short delay
            QTimer.singleShot(2000, lambda: self.cleanup_temp_pdf(pdf_path))
            
        except Exception as e:
            logger.error(f"Failed to open PDF externally: {e}")
            QMessageBox.warning(self, "Error", f"Could not open PDF: {str(e)}\n\nPlease use 'Save As...' instead.")
    
    def cleanup_temp_pdf(self, pdf_path: str):
        """Clean up temporary PDF file after external viewer opens it."""
        try:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)
                logger.debug(f"Cleaned up temporary PDF: {pdf_path}")
        except Exception as e:
            logger.warning(f"Could not clean up temporary PDF {pdf_path}: {e}")
    
    def create_pdf_preview(self, pdf_path: str) -> QWidget:
        """Create PDF preview using PyMuPDF."""
        try:
            import fitz
            doc = fitz.open(pdf_path)
            
            if len(doc) == 0:
                return None
                
            preview_widget = QWidget()
            preview_layout = QVBoxLayout(preview_widget)
            
            # Fixed PDF info header
            info_label = QLabel(f"📄 PDF Preview - {len(doc)} page(s)")
            info_label.setObjectName("pdfPreviewHeader")
            info_label.setFixedHeight(40)
            preview_layout.addWidget(info_label)
            
            # Render first page
            page = doc[0]
            mat = fitz.Matrix(1.5, 1.5)  # Scale factor
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            
            # Display page image
            pixmap = QPixmap()
            pixmap.loadFromData(img_data)
            
            # Scale to fit
            scaled_pixmap = pixmap.scaled(600, 800, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            page_label = QLabel()
            page_label.setPixmap(scaled_pixmap)
            page_label.setAlignment(Qt.AlignCenter)
            page_label.setStyleSheet("background-color: #020B1A !important; border: 2px solid #00AFFF !important; margin: 10px;")
            
            # Expandable scroll area - this grows with dialog
            scroll = QScrollArea()
            scroll.setWidget(page_label)
            scroll.setWidgetResizable(True)
            preview_layout.addWidget(scroll, 1)  # stretch factor = 1
            
            # Fixed button area
            open_btn = QPushButton("🔍 Open Full PDF")
            open_btn.setObjectName("pdfOpenButton")
            open_btn.setFixedHeight(35)
            open_btn.clicked.connect(lambda: self.open_pdf_externally(pdf_path))
            preview_layout.addWidget(open_btn)
            
            doc.close()
            return preview_widget
            
        except Exception as e:
            logger.error(f"PDF preview error: {e}")
            return None
    
    def create_pdf_fallback(self, pdf_path: str) -> QWidget:
        """Create fallback PDF widget when preview is not available."""
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        
        # PDF icon and info
        pdf_icon = QLabel("📄 PDF Document")
        pdf_icon.setStyleSheet("font-size: 24px; text-align: center; padding: 20px;")
        pdf_icon.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(pdf_icon)
        
        # File size info
        size_mb = len(self.blob_data) / (1024 * 1024)
        size_info = QLabel(f"Size: {len(self.blob_data):,} bytes ({size_mb:.2f} MB)")
        size_info.setAlignment(Qt.AlignCenter)
        size_info.setStyleSheet("color: #666; margin: 10px;")
        info_layout.addWidget(size_info)
        
        # Open button
        open_btn = QPushButton("🔍 Open PDF in System Viewer")
        open_btn.setObjectName("pdfSystemButton")
        open_btn.clicked.connect(lambda: self.open_pdf_externally(pdf_path))
        info_layout.addWidget(open_btn)
        
        # Instructions
        instructions = QLabel("Click above to open PDF in your default PDF viewer\nor use 'Save As...' to save the file")
        instructions.setAlignment(Qt.AlignCenter)
        instructions.setStyleSheet("color: #666; font-style: italic; margin: 15px; padding: 10px;")
        info_layout.addWidget(instructions)
        
        # PyMuPDF installation hint
        if not PYMUPDF_AVAILABLE:
            hint = QLabel("💡 Install PyMuPDF for PDF preview: pip install PyMuPDF")
            hint.setAlignment(Qt.AlignCenter)
            hint.setStyleSheet("color: #007bff; font-size: 11px; font-style: italic; margin: 10px;")
            info_layout.addWidget(hint)
        
        info_layout.addStretch()
        return info_widget
    
    def create_hex_widget(self) -> QWidget:
        """Create widget for hex dump preview."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Create hex dump
        hex_text = self.create_hex_dump()
        
        text_edit = QTextEdit()
        text_edit.setPlainText(hex_text)
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Consolas", 9))
        layout.addWidget(text_edit)
        
        return widget
    
    def create_hex_dump(self) -> str:
        """Create hex dump of binary data."""
        lines = []
        data = self.blob_data[:4096]  # Limit to first 4KB
        
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            lines.append(f'{i:08x}  {hex_part:<48} |{ascii_part}|')
        
        if len(self.blob_data) > 4096:
            lines.append(f'\n... ({len(self.blob_data) - 4096} more bytes)')
        
        return '\n'.join(lines)
    
    def get_audio_extension(self) -> str:
        """Get appropriate file extension for audio format."""
        if self.blob_data.startswith(b'\x00\x00\x00\x20ftypM4A'):
            return '.m4a'
        elif self.blob_data.startswith(b'fLaC'):
            return '.flac'
        elif self.blob_data.startswith(b'OggS'):
            return '.ogg'
        elif self.blob_data.startswith(b'RIFF') and b'WAVE' in self.blob_data[:12]:
            return '.wav'
        elif self.blob_data.startswith(b'wvpk'):
            return '.wv'
        elif self.blob_data.startswith(b'MAC '):
            return '.ape'
        else:
            return '.mp3'  # Default
    
    def get_audio_format_info(self) -> dict:
        """Get detailed audio format information."""
        if self.blob_data.startswith(b'\x00\x00\x00\x20ftypM4A'):
            return {'icon': '🎵', 'name': 'M4A Audio', 'description': 'Apple AAC Format | High Quality'}
        elif self.blob_data.startswith(b'fLaC'):
            return {'icon': '🎼', 'name': 'FLAC Audio', 'description': 'Lossless Compression | Audiophile Quality'}
        elif self.blob_data.startswith(b'OggS'):
            return {'icon': '🎶', 'name': 'OGG Vorbis', 'description': 'Open Source | Web Optimized'}
        elif self.blob_data.startswith(b'RIFF') and b'WAVE' in self.blob_data[:12]:
            return {'icon': '🎧', 'name': 'WAV Audio', 'description': 'Uncompressed | Studio Quality'}
        elif self.blob_data.startswith(b'wvpk'):
            return {'icon': '🎵', 'name': 'WavPack', 'description': 'Lossless | Hybrid Compression'}
        elif self.blob_data.startswith(b'MAC '):
            return {'icon': '🎵', 'name': 'APE Audio', 'description': "Monkey's Audio | Lossless"}
        else:
            return {'icon': '🎵', 'name': 'MP3 Audio', 'description': 'MPEG Layer 3 | Universal Format'}
    
    def get_video_extension(self) -> str:
        """Get appropriate file extension for video format."""
        if self.blob_data.startswith(b'\x1a\x45\xdf\xa3'):
            return '.mkv'
        elif self.blob_data.startswith(b'RIFF') and b'AVI ' in self.blob_data[:12]:
            return '.avi'
        elif self.blob_data.startswith(b'\x00\x00\x01\xba'):
            return '.mpg'
        elif self.blob_data.startswith(b'FLV\x01'):
            return '.flv'
        elif b'ftypqt' in self.blob_data[:20]:
            return '.mov'
        else:
            return '.mp4'  # Default
    
    def get_video_format_info(self) -> dict:
        """Get detailed video format information."""
        if self.blob_data.startswith(b'\x1a\x45\xdf\xa3'):
            return {'icon': '🎥', 'name': 'MKV Video', 'description': 'Matroska Container | Open Standard'}
        elif self.blob_data.startswith(b'RIFF') and b'AVI ' in self.blob_data[:12]:
            return {'icon': '🎥', 'name': 'AVI Video', 'description': 'Audio Video Interleave | Legacy Format'}
        elif self.blob_data.startswith(b'\x00\x00\x01\xba'):
            return {'icon': '🎥', 'name': 'MPEG Video', 'description': 'MPEG Standard | Broadcast Quality'}
        elif self.blob_data.startswith(b'FLV\x01'):
            return {'icon': '🎥', 'name': 'FLV Video', 'description': 'Flash Video | Web Streaming'}
        elif b'ftypqt' in self.blob_data[:20]:
            return {'icon': '🎥', 'name': 'MOV Video', 'description': 'QuickTime | Apple Format'}
        else:
            return {'icon': '🎥', 'name': 'MP4 Video', 'description': 'MPEG-4 | Universal Standard'}
    
    def create_document_widget(self) -> QWidget:
        """Create widget for document preview."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        try:
            # Detect document type and create appropriate viewer
            if b'word/' in self.blob_data[:1000] or self.blob_data.startswith(b'\xd0\xcf\x11\xe0'):
                return self.create_office_viewer("📄 Word Document", '.docx')
            elif b'xl/' in self.blob_data[:1000]:
                return self.create_office_viewer("📊 Excel Spreadsheet", '.xlsx')
            elif b'ppt/' in self.blob_data[:1000]:
                return self.create_office_viewer("📽️ PowerPoint Presentation", '.pptx')
            elif b'content.xml' in self.blob_data[:1000]:
                return self.create_office_viewer("📝 OpenDocument", '.odt')
            elif self.blob_data.startswith(b'{\\rtf'):
                return self.create_rtf_viewer()
            else:
                layout.addWidget(QLabel("📄 Unknown Document Format"))
                
        except Exception as e:
            layout.addWidget(QLabel(f"Error loading document: {str(e)}"))
        
        return widget
    
    def create_office_viewer(self, doc_type: str, ext: str) -> QWidget:
        """Create viewer for Office/OpenDocument formats."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Header
        header = QLabel(f"{doc_type} ({len(self.blob_data)} bytes)")
        header.setObjectName("docHeader")
        layout.addWidget(header)
        
        # Document preview info
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(15)
        
        # Document icon and type
        type_label = QLabel(f"📄 {doc_type}")
        type_label.setStyleSheet("font-size: 18px; font-weight: bold; text-align: center; padding: 20px;")
        type_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(type_label)
        
        # File info
        size_mb = len(self.blob_data) / (1024 * 1024)
        info_text = f"File Size: {len(self.blob_data):,} bytes ({size_mb:.2f} MB)"
        size_label = QLabel(info_text)
        size_label.setAlignment(Qt.AlignCenter)
        size_label.setStyleSheet("color: #666; font-size: 12px;")
        info_layout.addWidget(size_label)
        
        # Instructions
        instruction_label = QLabel("💾 Click 'Save As...' to save and open with:")
        instruction_label.setAlignment(Qt.AlignCenter)
        instruction_label.setStyleSheet("font-size: 14px; margin: 20px 0 10px 0;")
        info_layout.addWidget(instruction_label)
        
        # Application list
        apps_text = "• Microsoft Office\n• LibreOffice\n• Google Docs (upload)\n• Apple iWork"
        apps_label = QLabel(apps_text)
        apps_label.setAlignment(Qt.AlignCenter)
        apps_label.setStyleSheet("background: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #dee2e6;")
        info_layout.addWidget(apps_label)
        
        info_layout.addStretch()
        layout.addWidget(info_widget)
        
        return widget
    
    def create_rtf_viewer(self) -> QWidget:
        """Create viewer for RTF documents."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        try:
            # Try to extract plain text from RTF
            rtf_content = self.blob_data.decode('utf-8', errors='ignore')
            
            # Simple RTF to plain text conversion
            import re
            # Remove RTF control codes
            text = re.sub(r'\\[a-z]+\d*\s?', '', rtf_content)
            text = re.sub(r'[{}]', '', text)
            text = text.replace('\\', '').strip()
            
            header = QLabel("📄 Rich Text Format Document")
            header.setObjectName("rtfHeader")
            layout.addWidget(header)
            
            text_edit = QTextEdit()
            text_edit.setPlainText(text[:5000] + ("..." if len(text) > 5000 else ""))
            text_edit.setReadOnly(True)
            layout.addWidget(text_edit)
            
        except Exception as e:
            layout.addWidget(QLabel(f"📄 RTF Document\nError parsing: {str(e)}"))
        
        return widget
    
    def save_blob(self):
        """Save blob data to file with proper extension."""
        # Detect content type and suggest appropriate extension
        content_type = self.detect_content_type()
        default_name = f"{self.column_name}_data"
        
        if content_type == 'pdf':
            default_name += '.pdf'
            file_filter = "PDF Files (*.pdf);;All Files (*)"
        elif content_type == 'image':
            if self.blob_data.startswith(b'\xff\xd8\xff'):
                default_name += '.jpg'
            elif self.blob_data.startswith(b'\x89PNG'):
                default_name += '.png'
            else:
                default_name += '.img'
            file_filter = "Image Files (*.jpg *.png *.gif *.bmp);;All Files (*)"
        elif content_type == 'video':
            default_name += self.get_video_extension()
            file_filter = "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)"
        elif content_type == 'audio':
            default_name += self.get_audio_extension()
            file_filter = "Audio Files (*.mp3 *.wav *.m4a *.flac);;All Files (*)"
        elif content_type == 'document':
            if b'word/' in self.blob_data[:1000]:
                default_name += '.docx'
            elif b'xl/' in self.blob_data[:1000]:
                default_name += '.xlsx'
            elif b'ppt/' in self.blob_data[:1000]:
                default_name += '.pptx'
            elif b'content.xml' in self.blob_data[:1000]:
                default_name += '.odt'
            else:
                default_name += '.doc'
            file_filter = "Document Files (*.docx *.xlsx *.pptx *.odt *.doc);;All Files (*)"
        else:
            file_filter = "All Files (*)"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save File",
            default_name,
            file_filter
        )
        
        if file_path:
            try:
                with open(file_path, 'wb') as f:
                    f.write(self.blob_data)
                QMessageBox.information(self, "Success", f"File saved to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {str(e)}")
    
    def safe_media_action(self, action: str):
        """Safely perform media player actions."""
        try:
            logger.debug(f"Performing media action: {action}")
            if hasattr(self, 'media_player') and self.media_player:
                if action == "play":
                    self.media_player.play()
                elif action == "pause":
                    self.media_player.pause()
                elif action == "stop":
                    self.media_player.stop()
                logger.debug(f"Media action {action} completed")
            else:
                logger.warning("No media player available for action")
        except Exception as e:
            logger.error(f"Error performing media action {action}: {e}")
    
    def on_position_changed(self, position):
        """Update seek slider and time label when video position changes."""
        if not self.seeking and hasattr(self, 'media_player'):
            duration = self.media_player.duration()
            if duration > 0:
                # Use higher resolution for smooth slider movement
                slider_value = int((position / duration) * 10000)
                self.seek_slider.setValue(slider_value)
            
            # Update time label
            current_time = self.format_time(position)
            total_time = self.format_time(duration)
            self.time_label.setText(f"{current_time} / {total_time}")
    
    def on_duration_changed(self, duration):
        """Update controls when video duration is available."""
        if hasattr(self, 'time_label'):
            total_time = self.format_time(duration)
            self.time_label.setText(f"00:00 / {total_time}")
        
        # Enable smooth seeking once duration is known
        if hasattr(self, 'seek_slider') and duration > 0:
            self.seek_slider.setEnabled(True)
    
    def on_seek_start(self):
        """Handle seek slider press."""
        self.seeking = True
    
    def on_seek_end(self):
        """Handle seek slider release."""
        if hasattr(self, 'media_player') and self.media_player:
            duration = self.media_player.duration()
            if duration > 0:
                # Use higher resolution for precise seeking
                position = int((self.seek_slider.value() / 10000) * duration)
                self.media_player.setPosition(position)
        self.seeking = False
    
    def on_seek_moved(self, value):
        """Handle real-time seeking while dragging."""
        if self.seeking and hasattr(self, 'media_player') and self.media_player:
            duration = self.media_player.duration()
            if duration > 0:
                # Real-time seeking for smooth video scrubbing
                position = int((value / 10000) * duration)
                self.media_player.setPosition(position)
                
                # Update time label in real-time
                current_time = self.format_time(position)
                total_time = self.format_time(duration)
                self.time_label.setText(f"{current_time} / {total_time}")
    
    def on_speed_changed(self, speed_text):
        """Handle playback speed change."""
        try:
            speed = float(speed_text.replace('x', ''))
            if hasattr(self, 'media_player') and self.media_player:
                self.media_player.setPlaybackRate(speed)
                logger.debug(f"Playback speed changed to {speed}x")
        except Exception as e:
            logger.error(f"Error changing playback speed: {e}")
    
    def format_time(self, ms):
        """Format milliseconds to MM:SS format."""
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def closeEvent(self, event):
        """Clean up temporary files and media player."""
        logger.debug("BlobPreviewDialog closeEvent triggered")
        
        try:
            # Stop and cleanup media player
            if hasattr(self, 'media_player') and self.media_player:
                logger.debug("Cleaning up media player")
                self.media_player.stop()
                self.media_player.setMedia(QMediaContent())
                self.media_player.setParent(None)
                self.media_player.deleteLater()
                self.media_player = None
                logger.debug("Media player cleanup completed")
            
            # Cleanup video widget
            if hasattr(self, 'video_widget') and self.video_widget:
                logger.debug("Cleaning up video widget")
                self.video_widget.deleteLater()
                self.video_widget = None
                logger.debug("Video widget cleanup completed")
            
            # Clean up temporary files (including PDFs)
            logger.debug(f"Cleaning up {len(self.temp_files)} temporary files")
            for temp_file in self.temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                        logger.debug(f"Deleted temp file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Could not delete temp file {temp_file}: {e}")
            
            logger.debug("BlobPreviewDialog cleanup completed, accepting close event")
            event.accept()
            
        except Exception as e:
            logger.error(f"Error during BlobPreviewDialog closeEvent: {e}")
            event.accept()  # Accept anyway to prevent hanging
    
    def reject(self):
        """Handle dialog rejection (ESC key, X button)."""
        # Force stop media before closing
        if hasattr(self, 'media_player') and self.media_player:
            self.media_player.stop()
            self.media_player.setPosition(0)
        
        # Clean up temp files immediately
        self.cleanup_temp_files_now()
        super().reject()
    
    def accept(self):
        """Handle dialog acceptance (OK button)."""
        # Force stop media before closing
        if hasattr(self, 'media_player') and self.media_player:
            self.media_player.stop()
            self.media_player.setPosition(0)
        
        # Clean up temp files immediately
        self.cleanup_temp_files_now()
        super().accept()
    
    def cleanup_temp_files_now(self):
        """Immediately clean up temporary files."""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    logger.debug(f"Immediately deleted temp file: {temp_file}")
            except Exception as e:
                logger.warning(f"Could not immediately delete temp file {temp_file}: {e}")


class SQLQueryDialog(QDialog):
    """Dialog for executing raw SQL queries with syntax highlighting."""
    
    def __init__(self, db_manager, initial_query: str = "", parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.initial_query = initial_query
        self.data_changed = False
        self.structure_changed = False
        self.setup_ui()
        self.apply_theme()
    
    def setup_ui(self):
        self.setWindowTitle("SQL Query Editor")
        self.setModal(True)
        self.resize(900, 700)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header = QLabel("🗃️ SQL Query Editor")
        header.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header.setObjectName("sqlHeader")
        layout.addWidget(header)
        
        # SQL Editor
        editor_label = QLabel("SQL Query:")
        editor_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        layout.addWidget(editor_label)
        
        self.sql_editor = QTextEdit()
        self.sql_editor.setFont(QFont("Consolas", 11))
        self.sql_editor.setPlainText(self.initial_query)
        self.sql_editor.setMinimumHeight(200)
        self.sql_editor.setObjectName("sqlEditor")
        layout.addWidget(self.sql_editor)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.run_btn = QPushButton("▶️ Run Query")
        self.run_btn.clicked.connect(self.run_query)
        self.run_btn.setObjectName("runButton")
        self.run_btn.setMinimumHeight(40)
        button_layout.addWidget(self.run_btn)
        
        self.clear_btn = QPushButton("🗑️ Clear")
        self.clear_btn.clicked.connect(lambda: self.sql_editor.clear())
        self.clear_btn.setMinimumHeight(40)
        button_layout.addWidget(self.clear_btn)
        
        button_layout.addStretch()
        
        self.close_btn = QPushButton("❌ Close")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setMinimumHeight(40)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        
        # Results area
        results_label = QLabel("Query Results:")
        results_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        layout.addWidget(results_label)
        
        self.results_table = QTableWidget()
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results_table.setSortingEnabled(True)
        self.results_table.setObjectName("resultsTable")
        
        # Enable smooth scrolling for SQL results table
        self.results_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.results_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        
        layout.addWidget(self.results_table)
        
        # Status
        self.status_label = QLabel("Ready to execute SQL queries")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)
    
    def apply_theme(self):
        """Apply current theme to dialog."""
        parent_window = self.parent()
        while parent_window and not hasattr(parent_window, 'current_theme'):
            parent_window = parent_window.parent()
        
        if parent_window and hasattr(parent_window, 'current_theme') and parent_window.current_theme == 'dark':
            style = """
            QDialog { background-color: #020B1A; color: #FFFFFF; font-weight: bold; }
            QLabel { color: #FFFFFF; font-weight: bold; text-shadow: 0 0 3px #00AFFF; }
            QLabel#sqlHeader { color: #FFFFFF; font-weight: bold; text-shadow: 0 0 8px #00AFFF; background-color: #001122; padding: 15px; border-radius: 8px; }
            QLabel#statusLabel { color: #00F6FF; font-weight: bold; text-shadow: 0 0 5px #00AFFF; background-color: #001122; padding: 8px; border-radius: 4px; }
            QTextEdit#sqlEditor { 
                background-color: #001122; 
                color: #FFFFFF; 
                border: 2px solid #00AFFF; 
                border-radius: 8px; 
                font-weight: bold;
                selection-background-color: #002244;
            }
            QPushButton { background-color: #00AFFF; color: #FFFFFF; border: 2px solid #00F6FF; padding: 12px 24px; border-radius: 8px; font-weight: bold; font-size: 14px; text-shadow: 0 0 8px #FFFFFF; }
            QPushButton:hover { background-color: #FF0033; color: #FFFFFF; border-color: #FF7700; text-shadow: 0 0 15px #FFFFFF; }
            QPushButton#runButton { background-color: #00D12E; color: #FFFFFF; border-color: #00F6FF; }
            QPushButton#runButton:hover { background-color: #00F6FF; color: #000000; border-color: #00D12E; text-shadow: 0 0 15px #000000; }
            QTableWidget#resultsTable { 
                background-color: #020B1A; 
                gridline-color: #00AFFF; 
                border: 2px solid #00F6FF; 
                border-radius: 8px; 
                color: #FFFFFF; 
                font-weight: bold; 
                alternate-background-color: #0A1520;
                selection-background-color: #002244;
            }
            QTableWidget#resultsTable::item { color: #FFFFFF; text-shadow: 0 0 3px #00AFFF; padding: 8px; }
            QTableWidget#resultsTable::item:selected { background-color: #002244; color: #00F6FF; text-shadow: 0 0 12px #00F6FF; }
            QHeaderView::section { background-color: #000000; color: #FFFFFF; padding: 12px; border: none; border-right: 2px solid #00AFFF; font-weight: bold; text-shadow: 0 0 8px #FF0033; }
            """
        else:
            style = """
            QDialog { background-color: #FDFDFD; color: #000000; font-weight: bold; }
            QLabel { color: #000000; font-weight: bold; }
            QLabel#sqlHeader { color: #000000; font-weight: bold; background-color: #f8f9fa; padding: 15px; border-radius: 8px; }
            QLabel#statusLabel { color: #0057FF; font-weight: bold; background-color: #e8f5e8; padding: 8px; border-radius: 4px; }
            QTextEdit#sqlEditor { 
                background-color: #FFFFFF; 
                color: #000000; 
                border: 2px solid #222222; 
                border-radius: 8px; 
                font-weight: bold;
                selection-background-color: #FFD300;
            }
            QPushButton { background-color: #0057FF; color: #FFFFFF; border: 2px solid #222222; padding: 12px 24px; border-radius: 8px; font-weight: bold; font-size: 14px; }
            QPushButton:hover { background-color: #FF0033; color: #FFFFFF; border-color: #000000; }
            QPushButton#runButton { background-color: #00D12E; color: #FFFFFF; border-color: #222222; }
            QPushButton#runButton:hover { background-color: #00B844; color: #FFFFFF; }
            QTableWidget#resultsTable { 
                background-color: #FFFFFF; 
                gridline-color: #222222; 
                border: 2px solid #222222; 
                border-radius: 8px; 
                color: #000000; 
                font-weight: bold; 
                alternate-background-color: #F8F8F8;
                selection-background-color: #FFD300;
            }
            QTableWidget#resultsTable::item { color: #000000; padding: 8px; }
            QTableWidget#resultsTable::item:selected { background-color: #FFD300; color: #000000; font-weight: bold; }
            QHeaderView::section { background-color: #000000; color: #FFFFFF; padding: 12px; border: none; border-right: 2px solid #222222; font-weight: bold; }
            """
        
        self.setStyleSheet(style)
        
        # Apply SQL syntax highlighting
        self.apply_sql_highlighting()
    
    def apply_sql_highlighting(self):
        """Apply SQL syntax highlighting to the editor."""
        try:
            from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor
            from PyQt5.QtCore import QRegExp
            
            class SQLHighlighter(QSyntaxHighlighter):
                def __init__(self, parent, is_dark_theme):
                    super().__init__(parent)
                    self.is_dark = is_dark_theme
                    self.setup_highlighting()
                
                def setup_highlighting(self):
                    # SQL Keywords
                    keyword_format = QTextCharFormat()
                    if self.is_dark:
                        keyword_format.setForeground(QColor("#00F6FF"))
                    else:
                        keyword_format.setForeground(QColor("#0057FF"))
                    keyword_format.setFontWeight(QFont.Bold)
                    
                    keywords = [
                        "SELECT", "FROM", "WHERE", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER",
                        "TABLE", "INDEX", "VIEW", "DATABASE", "SCHEMA", "PRIMARY", "KEY", "FOREIGN",
                        "REFERENCES", "CONSTRAINT", "UNIQUE", "NOT", "NULL", "DEFAULT", "CHECK",
                        "AND", "OR", "IN", "LIKE", "BETWEEN", "IS", "EXISTS", "CASE", "WHEN", "THEN",
                        "ELSE", "END", "AS", "DISTINCT", "ORDER", "BY", "GROUP", "HAVING", "LIMIT",
                        "OFFSET", "JOIN", "INNER", "LEFT", "RIGHT", "FULL", "OUTER", "ON", "UNION",
                        "INTERSECT", "EXCEPT", "ALL", "ANY", "SOME", "COUNT", "SUM", "AVG", "MIN", "MAX"
                    ]
                    
                    self.highlighting_rules = []
                    for keyword in keywords:
                        pattern = QRegExp(f"\\b{keyword}\\b", Qt.CaseInsensitive)
                        self.highlighting_rules.append((pattern, keyword_format))
                    
                    # String literals
                    string_format = QTextCharFormat()
                    if self.is_dark:
                        string_format.setForeground(QColor("#FFD300"))
                    else:
                        string_format.setForeground(QColor("#D00000"))
                    self.highlighting_rules.append((QRegExp("'[^']*'"), string_format))
                    self.highlighting_rules.append((QRegExp('"[^"]*"'), string_format))
                    
                    # Numbers
                    number_format = QTextCharFormat()
                    if self.is_dark:
                        number_format.setForeground(QColor("#FF7700"))
                    else:
                        number_format.setForeground(QColor("#FF6A00"))
                    self.highlighting_rules.append((QRegExp("\\b\\d+\\b"), number_format))
                    
                    # Comments
                    comment_format = QTextCharFormat()
                    if self.is_dark:
                        comment_format.setForeground(QColor("#666666"))
                    else:
                        comment_format.setForeground(QColor("#888888"))
                    comment_format.setFontItalic(True)
                    self.highlighting_rules.append((QRegExp("--[^\n]*"), comment_format))
                
                def highlightBlock(self, text):
                    for pattern, format in self.highlighting_rules:
                        expression = QRegExp(pattern)
                        index = expression.indexIn(text)
                        while index >= 0:
                            length = expression.matchedLength()
                            self.setFormat(index, length, format)
                            index = expression.indexIn(text, index + length)
            
            # Apply highlighter
            parent_window = self.parent()
            while parent_window and not hasattr(parent_window, 'current_theme'):
                parent_window = parent_window.parent()
            
            is_dark = (parent_window and hasattr(parent_window, 'current_theme') and 
                      parent_window.current_theme == 'dark')
            
            self.highlighter = SQLHighlighter(self.sql_editor.document(), is_dark)
            
        except Exception as e:
            logger.debug(f"SQL highlighting failed: {e}")
    
    def run_query(self):
        """Execute the SQL query with non-blocking UI."""
        query = self.sql_editor.toPlainText().strip()
        if not query:
            self.status_label.setText("❌ Please enter a SQL query")
            return
        
        # Check if query modifies data/structure
        query_upper = query.upper().strip()
        if any(query_upper.startswith(cmd) for cmd in ['INSERT', 'UPDATE', 'DELETE']):
            self.data_changed = True
        if any(query_upper.startswith(cmd) for cmd in ['CREATE', 'DROP', 'ALTER']):
            self.structure_changed = True
        
        # Disable run button and show progress
        self.run_btn.setEnabled(False)
        self.run_btn.setText("⏳ Running...")
        self.status_label.setText("⏳ Executing query...")
        
        # Use QTimer to execute query on next event loop iteration
        QTimer.singleShot(10, lambda: self.execute_query(query))
    
    def execute_query(self, query):
        """Execute the actual SQL query."""
        try:
            cursor = self.db_manager.connection.cursor()
            cursor.execute(query)
            
            query_upper = query.upper().strip()
            if query_upper.startswith('SELECT') or query_upper.startswith('PRAGMA'):
                results = cursor.fetchall()
                columns = [description[0] for description in cursor.description] if cursor.description else []
                self.display_results(columns, results)
                message = f"Query executed successfully. {len(results)} rows returned."
                if len(results) <= 1000:
                    self.status_label.setText(f"✅ {message}")
            else:
                self.db_manager.connection.commit()
                affected_rows = cursor.rowcount
                self.results_table.setRowCount(0)
                self.results_table.setColumnCount(0)
                if affected_rows >= 0:
                    message = f"Query executed successfully. {affected_rows} rows affected."
                else:
                    message = "Query executed successfully."
                self.status_label.setText(f"✅ {message}")
            
            cursor.close()
            
        except Exception as e:
            self.status_label.setText(f"❌ Error: {str(e)}")
            self.results_table.setRowCount(0)
            self.results_table.setColumnCount(0)
        
        finally:
            # Re-enable run button
            self.run_btn.setEnabled(True)
            self.run_btn.setText("▶️ Run Query")
    

    
    def display_results(self, columns, rows):
        """Display query results in the table."""
        # Limit rows for performance (show first 1000 rows)
        display_rows = rows[:1000] if len(rows) > 1000 else rows
        
        self.results_table.setRowCount(len(display_rows))
        self.results_table.setColumnCount(len(columns))
        self.results_table.setHorizontalHeaderLabels(columns)
        
        # Disable sorting during population for performance
        self.results_table.setSortingEnabled(False)
        
        for row_idx, row_data in enumerate(display_rows):
            for col_idx, cell_data in enumerate(row_data):
                display_text = str(cell_data) if cell_data is not None else ""
                # Truncate very long text for performance
                if len(display_text) > 500:
                    display_text = display_text[:500] + "..."
                item = QTableWidgetItem(display_text)
                self.results_table.setItem(row_idx, col_idx, item)
        
        # Re-enable sorting after population
        self.results_table.setSortingEnabled(True)
        
        # Show truncation warning if needed
        if len(rows) > 1000:
            self.status_label.setText(f"✅ Query executed successfully. Showing first 1000 of {len(rows)} rows.")
        
        # Resize columns to content (limit for performance)
        self.results_table.resizeColumnsToContents()
        for col in range(min(self.results_table.columnCount(), 20)):  # Limit column resizing
            current_width = self.results_table.columnWidth(col)
            if current_width < 100:
                self.results_table.setColumnWidth(col, 100)
            elif current_width > 300:  # Limit max width for performance
                self.results_table.setColumnWidth(col, 300)


class BlobFieldWidget(QWidget):
    """Widget for BLOB field input with file browser."""
    
    def __init__(self, column_name: str, parent=None):
        super().__init__(parent)
        self.column_name = column_name
        self.blob_data = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("color: #6c757d; font-style: italic; padding: 8px;")
        layout.addWidget(self.file_label)
        
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_file)
        self.browse_btn.setMaximumWidth(80)
        layout.addWidget(self.browse_btn)
    
    def browse_file(self):
        """Open file dialog to select file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select file for {self.column_name}",
            "",
            "All Files (*);;Images (*.jpg *.jpeg *.png *.bmp *.gif *.tiff *.webp *.svg);;Documents (*.pdf *.txt *.md *.doc *.docx *.xlsx *.pptx *.odt *.rtf);;Videos (*.mp4 *.avi *.mov *.mkv *.mpg *.flv *.webm);;Audio (*.mp3 *.wav *.m4a *.flac *.ogg *.wv *.ape);;Code (*.py *.js *.java *.c *.cpp *.html *.css *.php);;Archives (*.zip *.tar *.gz *.7z *.rar);;Fonts (*.ttf *.otf *.woff)"
        )
        
        if file_path:
            try:
                with open(file_path, 'rb') as f:
                    self.blob_data = f.read()
                
                filename = os.path.basename(file_path)
                file_size = len(self.blob_data)
                self.file_label.setText(f"Selected: {filename} ({file_size} bytes)")
                self.file_label.setStyleSheet("color: #28a745; font-weight: 500; padding: 8px;")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to read file: {str(e)}")
    
    def get_value(self):
        """Get the blob data."""
        return self.blob_data


class AddRowDialog(QDialog):
    """Dialog for adding new rows to a table."""
    
    def __init__(self, columns: List[Tuple[str, str]], parent=None):
        super().__init__(parent)
        self.columns = columns
        self.field_widgets = {}
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("Add New Row")
        self.setModal(True)
        self.resize(500, 400)
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QLineEdit {
                padding: 10px;
                border: 2px solid #e9ecef;
                border-radius: 6px;
                font-size: 13px;
                margin: 2px;
            }
            QLineEdit:focus {
                border-color: #007bff;
            }
            QLabel {
                font-weight: 500;
                color: #495057;
                margin: 5px 0;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Add New Row")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #2c3e50; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Form layout for input fields
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        for column_name, column_type in self.columns:
            if column_name.lower() == 'rowid':
                continue  # Skip rowid as it's auto-generated
            
            # Use file browser for BLOB fields
            if column_type.upper() == 'BLOB':
                blob_widget = BlobFieldWidget(column_name)
                self.field_widgets[column_name] = blob_widget
                form_layout.addRow(f"{column_name}:", blob_widget)
            else:
                line_edit = QLineEdit()
                line_edit.setPlaceholderText(f"Enter {column_name} ({column_type})")
                line_edit.setMinimumHeight(40)
                self.field_widgets[column_name] = line_edit
                form_layout.addRow(f"{column_name}:", line_edit)
        
        layout.addLayout(form_layout)
        layout.addStretch()
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText("Add Row")
        button_box.button(QDialogButtonBox.Cancel).setText("Cancel")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_data(self) -> dict:
        """Get the data from the form fields."""
        data = {}
        for column_name, widget in self.field_widgets.items():
            if isinstance(widget, BlobFieldWidget):
                data[column_name] = widget.get_value()
            else:
                value = widget.text().strip()
                data[column_name] = value if value else None
        return data


class TableWidget(QTableWidget):
    """Enhanced table widget with editing capabilities."""
    
    cell_changed_signal = pyqtSignal(int, int, str)
    blob_changed_signal = pyqtSignal(int, int, bytes)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_table()
        self.selected_rows = set()
        self.column_types = {}
    
    def setup_table(self):
        """Setup table properties and styling."""
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setGridStyle(Qt.SolidLine)
        self.setSortingEnabled(True)
        self.setShowGrid(True)
        self.setWordWrap(False)
        
        # Smooth scrolling
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        
        # Set header properties for responsiveness
        h_header = self.horizontalHeader()
        h_header.setStretchLastSection(True)
        h_header.setSectionResizeMode(QHeaderView.Interactive)
        h_header.setDefaultSectionSize(200)  # Increased default width
        h_header.setMinimumSectionSize(120)  # Increased minimum width
        h_header.setCascadingSectionResizes(True)
        
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(40)  # Increased row height
        
        # Connect signals
        self.itemChanged.connect(self.on_item_changed)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def on_item_changed(self, item):
        """Handle cell editing."""
        # Get column name to check if it's a BLOB column
        column_name = self.horizontalHeaderItem(item.column()).text()
        
        # Don't allow text editing of BLOB columns
        if self.column_types.get(column_name, '').upper() == 'BLOB':
            print(f"DEBUG: Preventing text edit of BLOB column {column_name}")
            sys.stdout.flush()
            # Revert the text change
            if hasattr(item, 'original_value') and isinstance(item.original_value, bytes):
                if len(item.original_value) > 100:
                    item.setText(repr(item.original_value[:100]) + "...")
                else:
                    item.setText(repr(item.original_value))
            return
        
        # Handle normal text cell editing
        if hasattr(item, 'original_value') and item.text() != str(item.original_value):
            self.cell_changed_signal.emit(item.row(), item.column(), item.text())
            item.original_value = item.text()
    
    def show_context_menu(self, position):
        """Show context menu for table items."""
        item = self.itemAt(position)
        if not item:
            return
        
        column_name = self.horizontalHeaderItem(item.column()).text()
        
        if self.column_types.get(column_name, '').upper() == 'BLOB':
            from PyQt5.QtWidgets import QMenu
            menu = QMenu(self)
            
            blob_data = item.original_value
            
            # Ensure blob_data is proper bytes
            if blob_data is not None and not isinstance(blob_data, bytes):
                if isinstance(blob_data, (bytearray, memoryview)):
                    blob_data = bytes(blob_data)
                elif isinstance(blob_data, str):
                    blob_data = blob_data.encode('utf-8')
                else:
                    blob_data = bytes(blob_data)
                item.original_value = blob_data
            
            if blob_data:
                view_action = menu.addAction("👁️ View")
                view_action.triggered.connect(lambda: self.preview_blob(blob_data, column_name))
                menu.addSeparator()
            
            browse_action = menu.addAction("📁 Browse & Replace")
            browse_action.triggered.connect(lambda: self.browse_blob_file(item))
            
            if isinstance(blob_data, bytes) and blob_data:
                save_action = menu.addAction("💾 Save As...")
                save_action.triggered.connect(lambda: self.save_blob(blob_data, column_name))
            
            menu.exec_(self.mapToGlobal(position))
    
    def preview_blob(self, blob_data: bytes, column_name: str):
        """Preview blob content."""
        dialog = BlobPreviewDialog(blob_data, column_name, self)
        dialog.exec_()
    
    def browse_blob_file(self, item):
        """Browse for file to replace blob content."""
        column_name = self.horizontalHeaderItem(item.column()).text()
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select file for {column_name}",
            "",
            "All Files (*);;Images (*.jpg *.jpeg *.png *.bmp *.gif *.tiff *.webp *.svg);;Documents (*.pdf *.txt *.md *.doc *.docx *.xlsx *.pptx *.odt *.rtf);;Videos (*.mp4 *.avi *.mov *.mkv *.mpg *.flv *.webm);;Audio (*.mp3 *.wav *.m4a *.flac *.ogg *.wv *.ape);;Code (*.py *.js *.java *.c *.cpp *.html *.css *.php);;Archives (*.zip *.tar *.gz *.7z *.rar);;Fonts (*.ttf *.otf *.woff)"
        )
        
        if file_path:
            try:
                with open(file_path, 'rb') as f:
                    blob_data = f.read()
                
                filename = os.path.basename(file_path)
                
                # Update display
                item.setText(f"<BLOB: {len(blob_data)} bytes> {filename} [Right-click to view]")
                item.original_value = blob_data
                
                # Emit signal for database update
                self.blob_changed_signal.emit(item.row(), item.column(), blob_data)
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to read file: {str(e)}")
    
    def save_blob(self, blob_data: bytes, column_name: str):
        """Save blob data to file with proper extension."""
        # Create temporary dialog to detect content type
        temp_dialog = BlobPreviewDialog(blob_data, column_name, self)
        content_type = temp_dialog.detect_content_type()
        
        default_name = f"{column_name}_data"
        if content_type == 'pdf':
            default_name += '.pdf'
            file_filter = "PDF Files (*.pdf);;All Files (*)"
        elif content_type == 'image':
            if blob_data.startswith(b'\xff\xd8\xff'):
                default_name += '.jpg'
            elif blob_data.startswith(b'\x89PNG'):
                default_name += '.png'
            else:
                default_name += '.img'
            file_filter = "Image Files (*.jpg *.png *.gif *.bmp);;All Files (*)"
        elif content_type == 'video':
            default_name += temp_dialog.get_video_extension()
            file_filter = "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)"
        elif content_type == 'audio':
            default_name += temp_dialog.get_audio_extension()
            file_filter = "Audio Files (*.mp3 *.wav *.m4a *.flac);;All Files (*)"
        elif content_type == 'document':
            if b'word/' in blob_data[:1000]:
                default_name += '.docx'
            elif b'xl/' in blob_data[:1000]:
                default_name += '.xlsx'
            elif b'ppt/' in blob_data[:1000]:
                default_name += '.pptx'
            else:
                default_name += '.doc'
            file_filter = "Document Files (*.docx *.xlsx *.pptx *.odt);;All Files (*)"
        else:
            file_filter = "All Files (*)"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save {column_name}",
            default_name,
            file_filter
        )
        
        if file_path:
            try:
                with open(file_path, 'wb') as f:
                    f.write(blob_data)
                QMessageBox.information(self, "Success", f"File saved to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {str(e)}")
    
    def load_data(self, columns: List[str], rows: List[List[Any]], column_types: dict = None):
        """Load data into the table."""
        self.setRowCount(len(rows))
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(columns)
        self.column_types = column_types or {}
        
        for row_idx, row_data in enumerate(rows):
            for col_idx, cell_data in enumerate(row_data):
                column_name = columns[col_idx]
                
                # Handle BLOB data display with debugging
                if self.column_types.get(column_name, '').upper() == 'BLOB' and cell_data is not None:
                    print(f"DEBUG: BLOB column {column_name}, data type: {type(cell_data)}, length: {len(cell_data) if hasattr(cell_data, '__len__') else 'N/A'}")
                    print(f"DEBUG: First 50 bytes: {repr(cell_data[:50]) if hasattr(cell_data, '__getitem__') else repr(cell_data)}")
                    sys.stdout.flush()
                    
                    # Convert SQLite BLOB data to bytes
                    if isinstance(cell_data, (bytes, bytearray, memoryview)):
                        blob_data = bytes(cell_data)
                    elif hasattr(cell_data, 'read'):  # File-like object
                        blob_data = cell_data.read()
                    else:
                        # Last resort - convert to string then bytes
                        blob_data = str(cell_data).encode('utf-8')
                    
                    print(f"DEBUG: Processed blob_data type: {type(blob_data)}, length: {len(blob_data)}")
                    sys.stdout.flush()
                    
                    # Show raw data instead of formatted display
                    if len(blob_data) > 100:
                        display_text = repr(blob_data[:100]) + "..."
                    else:
                        display_text = repr(blob_data)
                    
                    item = QTableWidgetItem(display_text)
                    item.original_value = blob_data
                    # Make BLOB cells non-editable
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                else:
                    display_text = str(cell_data) if cell_data is not None else ""
                    item = QTableWidgetItem(display_text)
                    item.original_value = cell_data
                
                self.setItem(row_idx, col_idx, item)
        
        # Resize columns to content but ensure minimum width for editing
        self.resizeColumnsToContents()
        for col in range(self.columnCount()):
            current_width = self.columnWidth(col)
            if current_width < 150:  # Ensure minimum width for comfortable editing
                self.setColumnWidth(col, 150)
    
    def get_selected_rowids(self) -> List[int]:
        """Get the rowids of selected rows."""
        selected_rows = set()
        for item in self.selectedItems():
            selected_rows.add(item.row())
        
        rowids = []
        for row in selected_rows:
            rowid_item = self.item(row, 0)  # First column is always rowid
            if rowid_item:
                rowids.append(int(rowid_item.text()))
        
        return rowids


class SQLiteExplorer(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        logger.debug("SQLiteExplorer.__init__: Starting initialization")
        super().__init__()
        logger.debug("SQLiteExplorer.__init__: Parent class initialized")
        
        self.db_manager = DatabaseManager()
        logger.debug("SQLiteExplorer.__init__: DatabaseManager created")
        
        self.current_table = None
        logger.debug("SQLiteExplorer.__init__: current_table set to None")
        
        self.recent_files = self.load_recent_files()
        logger.debug(f"SQLiteExplorer.__init__: Loaded {len(self.recent_files)} recent files")
        
        # Load theme preference
        self.theme_preference = self.load_theme_preference()
        logger.debug(f"SQLiteExplorer.__init__: Loaded theme preference: {self.theme_preference}")
        
        # Set current theme based on preference
        if self.theme_preference == 'system':
            self.current_theme = self.detect_system_theme()
        else:
            self.current_theme = self.theme_preference
        logger.debug(f"SQLiteExplorer.__init__: Set current theme: {self.current_theme}")
        
        self.setup_ui()
        logger.debug("SQLiteExplorer.__init__: UI setup completed")
        
        self.apply_styling()
        logger.debug("SQLiteExplorer.__init__: Styling applied")
        
        # Monitor system theme changes (only if using system theme)
        self.theme_timer = QTimer()
        logger.debug("SQLiteExplorer.__init__: Theme timer created")
        
        self.theme_timer.timeout.connect(self.check_system_theme)
        logger.debug("SQLiteExplorer.__init__: Theme timer connected to check_system_theme")
        
        if self.theme_preference == 'system':
            self.theme_timer.start(1000)  # Check every second only for system theme
            logger.debug("SQLiteExplorer.__init__: Theme timer started for system theme monitoring")
        else:
            logger.debug("SQLiteExplorer.__init__: Theme timer not started (manual theme selected)")
        
        logger.debug("SQLiteExplorer.__init__: Initialization completed successfully")
    

    
    def toggle_sidebar(self):
        """Toggle sidebar visibility."""
        if hasattr(self, 'sidebar_widget'):
            if self.sidebar_widget.isVisible():
                self.sidebar_widget.hide()
                # Change button to show arrow and move to main area
                if hasattr(self, 'sidebar_toggle_btn'):
                    self.sidebar_toggle_btn.setText("»")
                    self.sidebar_toggle_btn.setToolTip("Show sidebar")
                    self.sidebar_toggle_btn.setParent(self.main_widget)
                    self.sidebar_toggle_btn.move(5, 5)
                    self.sidebar_toggle_btn.show()
            else:
                self.sidebar_widget.show()
                # Change button back to hide arrow and move to sidebar
                if hasattr(self, 'sidebar_toggle_btn'):
                    self.sidebar_toggle_btn.setText("«")
                    self.sidebar_toggle_btn.setToolTip("Hide sidebar")
                    self.sidebar_toggle_btn.setParent(self.sidebar_widget)
                    # Re-add to header layout
                    header_layout = self.sidebar_widget.layout().itemAt(0).layout()
                    header_layout.addWidget(self.sidebar_toggle_btn)
    
    def setup_ui(self):
        """Setup the responsive user interface."""
        self.setWindowTitle("SQLite Database Explorer - Professional Edition")
        self.setMinimumSize(320, 480)  # Phone minimum size
        self.resize(1400, 900)
        
        # Enable window resizing and make it responsive
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        
        # Central widget with responsive layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        self.main_layout = QVBoxLayout(central_widget)  # Changed to VBox for mobile
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Create responsive container
        self.setup_responsive_layout()
        
        # Menu and toolbar
        self.setup_menu()
        
        # Status bar with professional styling
        status_bar = self.statusBar()
        status_bar.showMessage("Ready - Open a database to get started")
        status_bar.setStyleSheet("QStatusBar { border-top: 1px solid #e0e0e0; background: #f8f9fa; color: #495057; }")
        
        # Setup responsive behavior
        self.setup_responsive_behavior()
    
    def setup_responsive_layout(self):
        """Setup single responsive layout."""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(1)
        layout.addWidget(self.splitter)
        
        # Left sidebar for tables
        self.setup_sidebar(self.splitter)
        
        # Right main area for table data
        self.setup_main_area(self.splitter)
        
        # Set splitter proportions
        self.splitter.setSizes([300, 1100])
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        
        self.main_layout.addLayout(layout)
    
    def setup_sidebar(self, parent):
        """Setup the responsive sidebar with table list."""
        self.sidebar_widget = QWidget()
        self.sidebar_widget.setMinimumWidth(200)
        self.sidebar_widget.setMaximumWidth(400)
        sidebar_layout = QVBoxLayout(self.sidebar_widget)
        sidebar_layout.setContentsMargins(8, 8, 8, 8)
        sidebar_layout.setSpacing(6)
        
        # Header with icon, title and hide button
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("📊 Tables")
        title_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title_label.setStyleSheet("color: #0057FF; padding: 3px 0; font-weight: bold;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        self.sidebar_toggle_btn = QPushButton("«")
        self.sidebar_toggle_btn.setFixedSize(20, 20)
        self.sidebar_toggle_btn.setToolTip("Hide sidebar")
        self.sidebar_toggle_btn.clicked.connect(self.toggle_sidebar)
        self.sidebar_toggle_btn.setStyleSheet("QPushButton { font-size: 12px; font-weight: bold; }")
        header_layout.addWidget(self.sidebar_toggle_btn)
        
        sidebar_layout.addLayout(header_layout)
        
        # Table list
        self.table_list = QListWidget()
        self.table_list.itemClicked.connect(self.on_table_selected)
        self.table_list.setMinimumHeight(100)
        sidebar_layout.addWidget(self.table_list)
        
        parent.addWidget(self.sidebar_widget)
    
    def setup_main_area(self, parent):
        """Setup the main area with responsive controls."""
        self.main_widget = QWidget()
        main_layout = QVBoxLayout(self.main_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        
        # Table info
        self.table_info_label = QLabel("Select a table to view data")
        self.table_info_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.table_info_label.setStyleSheet("color: #FF0033; padding: 3px 0; font-weight: bold;")
        self.table_info_label.setWordWrap(True)
        main_layout.addWidget(self.table_info_label)
        
        # Responsive button container
        self.setup_responsive_buttons(main_layout)
        
        # Table widget with smooth scrolling
        self.table_widget = TableWidget()
        self.table_widget.cell_changed_signal.connect(self.on_cell_changed)
        self.table_widget.blob_changed_signal.connect(self.on_blob_changed)
        self.table_widget.itemSelectionChanged.connect(self.on_selection_changed)
        
        # Enable smooth scrolling for the main table
        self.table_widget.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table_widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        
        main_layout.addWidget(self.table_widget)
        
        parent.addWidget(self.main_widget)
    
    def setup_responsive_buttons(self, parent_layout):
        """Setup responsive button layout."""
        # Create button container with flow layout
        button_frame = QFrame()
        button_frame.setMaximumHeight(70)
        
        # Use grid layout for better control
        grid_layout = QGridLayout(button_frame)
        grid_layout.setSpacing(4)
        grid_layout.setContentsMargins(2, 2, 2, 2)
        
        # Create all buttons
        self.create_buttons()
        
        # Arrange buttons in responsive grid
        grid_layout.addWidget(self.create_table_btn, 0, 0)
        grid_layout.addWidget(self.add_column_btn, 0, 1)
        grid_layout.addWidget(self.add_row_btn, 0, 2)
        grid_layout.addWidget(self.delete_rows_btn, 1, 0)
        grid_layout.addWidget(self.refresh_btn, 1, 1)
        grid_layout.addWidget(self.sql_btn, 1, 2)
        
        parent_layout.addWidget(button_frame)
    
    def create_buttons(self):
        """Create all control buttons with responsive properties."""
        button_height = 28
        
        self.create_table_btn = QPushButton("📋 Create")
        self.create_table_btn.clicked.connect(self.create_table)
        self.create_table_btn.setEnabled(False)
        self.create_table_btn.setMinimumHeight(button_height)
        
        self.add_column_btn = QPushButton("➕ Column")
        self.add_column_btn.clicked.connect(self.add_column_to_table)
        self.add_column_btn.setEnabled(False)
        self.add_column_btn.setMinimumHeight(button_height)
        
        self.add_row_btn = QPushButton("➕ Row")
        self.add_row_btn.clicked.connect(self.add_row)
        self.add_row_btn.setEnabled(False)
        self.add_row_btn.setMinimumHeight(button_height)
        
        self.delete_rows_btn = QPushButton("🗑️ Delete")
        self.delete_rows_btn.clicked.connect(self.delete_selected_rows)
        self.delete_rows_btn.setEnabled(False)
        self.delete_rows_btn.setMinimumHeight(button_height)
        
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.refresh_table)
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setMinimumHeight(button_height)
        
        self.sql_btn = QPushButton("🗃️ SQL")
        self.sql_btn.clicked.connect(self.open_sql_dialog)
        self.sql_btn.setEnabled(False)
        self.sql_btn.setMinimumHeight(button_height)
    
    def setup_responsive_behavior(self):
        """Setup responsive behavior based on window size."""
        pass  # Simplified - no dynamic layout switching
    
    def setup_menu(self):
        """Setup menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        open_action = file_menu.addAction('Open Database...')
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_database)
        
        # Recent files submenu
        self.recent_menu = file_menu.addMenu('Recent Databases')
        self.update_recent_menu()
        
        file_menu.addSeparator()
        
        close_action = file_menu.addAction('Close Database')
        close_action.triggered.connect(self.close_database)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction('Exit')
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        
        # View menu
        view_menu = menubar.addMenu('View')
        
        # Sidebar toggle
        sidebar_action = view_menu.addAction('Show/Hide Sidebar')
        sidebar_action.setShortcut('Ctrl+B')
        sidebar_action.triggered.connect(self.toggle_sidebar)
        
        view_menu.addSeparator()
        theme_menu = view_menu.addMenu('Theme')
        
        system_action = theme_menu.addAction('System Theme')
        system_action.setCheckable(True)
        system_action.triggered.connect(lambda: self.set_theme_preference('system'))
        
        light_action = theme_menu.addAction('Light Theme')
        light_action.setCheckable(True)
        light_action.triggered.connect(lambda: self.set_theme_preference('light'))
        
        dark_action = theme_menu.addAction('Dark Theme')
        dark_action.setCheckable(True)
        dark_action.triggered.connect(lambda: self.set_theme_preference('dark'))
        
        # Create action group for exclusive selection
        self.theme_action_group = QActionGroup(self)
        self.theme_action_group.addAction(system_action)
        self.theme_action_group.addAction(light_action)
        self.theme_action_group.addAction(dark_action)
        
        # Set current selection
        if self.theme_preference == 'system':
            system_action.setChecked(True)
        elif self.theme_preference == 'light':
            light_action.setChecked(True)
        elif self.theme_preference == 'dark':
            dark_action.setChecked(True)
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        about_action = help_menu.addAction('About')
        about_action.triggered.connect(self.show_about)
    
    def apply_styling(self):
        """Apply theme styling based on current theme."""
        logger.debug(f"apply_styling: Starting styling application for theme: {self.current_theme}")
        
        # Set button classes BEFORE applying stylesheet
        if hasattr(self, 'delete_rows_btn'):
            logger.debug("apply_styling: Setting button properties")
            self.delete_rows_btn.setProperty("class", "danger")
            logger.debug("apply_styling: Set delete_rows_btn class to danger")
            
            self.add_row_btn.setProperty("class", "success")
            logger.debug("apply_styling: Set add_row_btn class to success")
            
            self.add_column_btn.setProperty("class", "success")
            logger.debug("apply_styling: Set add_column_btn class to success")
            
            self.create_table_btn.setProperty("class", "primary")
            logger.debug("apply_styling: Set create_table_btn class to primary")
            
            self.sql_btn.setProperty("class", "info")
            logger.debug("apply_styling: Set sql_btn class to info")
        else:
            logger.debug("apply_styling: Buttons not yet created, skipping property setting")
        
        if self.current_theme == 'dark':
            logger.debug("apply_styling: Applying dark theme")
            self.apply_dark_theme()
            logger.debug("apply_styling: Dark theme applied")
        else:
            logger.debug("apply_styling: Applying light theme")
            self.apply_light_theme()
            logger.debug("apply_styling: Light theme applied")
        
        # Force refresh all widgets
        if hasattr(self, 'delete_rows_btn'):
            logger.debug("apply_styling: Starting button refresh")
            buttons = [self.delete_rows_btn, self.add_row_btn, self.add_column_btn, self.create_table_btn, self.sql_btn]
            for i, btn in enumerate(buttons):
                logger.debug(f"apply_styling: Refreshing button {i+1}/{len(buttons)}")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                btn.update()
                logger.debug(f"apply_styling: Button {i+1}/{len(buttons)} refreshed")
            logger.debug("apply_styling: All buttons refreshed")
        else:
            logger.debug("apply_styling: Buttons not available for refresh")
        
        logger.debug("apply_styling: Styling application completed")
    
    def apply_light_theme(self):
        """Apply bold high-contrast light theme."""
        style = """
        QMainWindow { background-color: #FDFDFD; font-family: 'Segoe UI', 'Arial', sans-serif; color: #000000; font-weight: bold; }
        QWidget { background-color: #FDFDFD; color: #000000; }
        QSplitter::handle { background-color: #222222; width: 2px; }
        QSplitter::handle:hover { background-color: #FF0033; }
        QListWidget { background-color: #FFFFFF; border: 2px solid #222222; border-radius: 8px; padding: 8px; font-size: 13px; outline: none; color: #000000; font-weight: bold; }
        QListWidget::item { padding: 12px 16px; border-radius: 6px; margin: 2px 0; border: none; color: #000000; }
        QListWidget::item:hover { background-color: #FFD300; color: #000000; font-weight: bold; }
        QListWidget::item:selected { background-color: #0057FF; color: #FFFFFF; font-weight: bold; }
        QTableWidget { background-color: #FFFFFF; gridline-color: #222222; border: 2px solid #222222; border-radius: 8px; font-size: 13px; selection-background-color: #FFD300; color: #000000; font-weight: bold; alternate-background-color: #F8F8F8; }
        QTableWidget::item { padding: 8px 12px; border: none; min-width: 120px; color: #000000; }
        QTableWidget::item:selected { background-color: #FFD300; color: #000000; font-weight: bold; }
        QHeaderView::section { background-color: #000000; color: #FFFFFF; padding: 12px 16px; border: none; border-right: 2px solid #222222; font-weight: bold; font-size: 14px; }
        QPushButton { background-color: #0057FF; color: #FFFFFF; border: 2px solid #222222; padding: 8px 12px; border-radius: 6px; font-weight: bold; font-size: 12px; min-width: 80px; }
        QPushButton:hover { background-color: #FF0033; color: #FFFFFF; border-color: #000000; }
        QPushButton:disabled { background-color: #444444; color: #202020; border-color: #222222; }
        QPushButton[class="danger"] { background-color: #D00000; color: #FFFFFF; border-color: #222222; }
        QPushButton[class="danger"]:hover { background-color: #FF6A00; color: #FFFFFF; }
        QPushButton[class="success"] { background-color: #00D12E; color: #FFFFFF; border-color: #222222; }
        QPushButton[class="success"]:hover { background-color: #00B844; color: #FFFFFF; }
        QPushButton[class="primary"] { background-color: #0084FF; color: #FFFFFF; border-color: #222222; }
        QPushButton[class="primary"]:hover { background-color: #0078FF; color: #FFFFFF; }
        QPushButton[class="info"] { background-color: #17a2b8; color: #FFFFFF; border-color: #222222; }
        QPushButton[class="info"]:hover { background-color: #138496; color: #FFFFFF; }
        QMenuBar { background-color: #FFFFFF; border-bottom: 2px solid #222222; padding: 6px; color: #000000; font-weight: bold; }
        QMenuBar::item { background-color: transparent; padding: 10px 18px; border-radius: 6px; color: #000000; }
        QMenuBar::item:selected { background-color: #FFD300; color: #000000; font-weight: bold; }
        QMenu { background-color: #FFFFFF; border: 2px solid #222222; border-radius: 8px; padding: 6px; color: #000000; font-weight: bold; }
        QMenu::item { padding: 10px 18px; border-radius: 6px; color: #000000; }
        QMenu::item:selected { background-color: #0057FF; color: #FFFFFF; font-weight: bold; }
        QDialog { background-color: #FDFDFD; color: #000000; font-weight: bold; }
        QLineEdit { padding: 10px 14px; border: 2px solid #222222; border-radius: 8px; font-size: 14px; background-color: #FFFFFF; color: #000000; font-weight: bold; }
        QLineEdit:focus { border-color: #0057FF; color: #000000; background-color: #FFD300; }
        QLabel { color: #000000; font-weight: bold; }
        QStatusBar { background-color: #FFFFFF; color: #000000; border-top: 2px solid #222222; font-weight: bold; }
        """
        self.setStyleSheet(style)
    
    def apply_dark_theme(self):
        """Apply manly glowing Best Blue power theme."""
        style = """
        QMainWindow { background-color: #020B1A; font-family: 'Segoe UI', 'Arial', sans-serif; color: #FFFFFF; font-weight: bold; }
        QWidget { background-color: #020B1A; color: #FFFFFF; }
        QSplitter::handle { background-color: #00AFFF; width: 2px; }
        QSplitter::handle:hover { background-color: #FF0033; box-shadow: 0 0 10px #FF0033; }
        QListWidget { background-color: #020B1A; border: 2px solid #00F6FF; border-radius: 8px; padding: 8px; font-size: 13px; outline: none; color: #FFFFFF; font-weight: bold; }
        QListWidget::item { padding: 12px 16px; border-radius: 6px; margin: 2px 0; border: none; color: #FFFFFF; text-shadow: 0 0 5px #00AFFF; }
        QListWidget::item:hover { background-color: #001122; color: #00F6FF; text-shadow: 0 0 10px #00F6FF; border: 1px solid #00F6FF; }
        QListWidget::item:selected { background-color: #002244; color: #FFFFFF; font-weight: bold; text-shadow: 0 0 15px #00AFFF; border: 2px solid #00AFFF; }
        QTableWidget { background-color: #020B1A; gridline-color: #00AFFF; border: 2px solid #00F6FF; border-radius: 8px; font-size: 13px; selection-background-color: #001122; color: #FFFFFF; font-weight: bold; alternate-background-color: #0A1520; }
        QTableWidget::item { padding: 8px 12px; border: none; min-width: 120px; color: #FFFFFF; text-shadow: 0 0 3px #00AFFF; }
        QTableWidget::item:selected { background-color: #002244; color: #00F6FF; text-shadow: 0 0 12px #00F6FF; }
        QHeaderView::section { background-color: #000000; color: #FFFFFF; padding: 12px 16px; border: none; border-right: 2px solid #00AFFF; font-weight: bold; font-size: 14px; text-shadow: 0 0 8px #FF0033; }
        QPushButton { background-color: #00AFFF; color: #FFFFFF; border: 2px solid #00F6FF; padding: 8px 12px; border-radius: 6px; font-weight: bold; font-size: 12px; min-width: 80px; text-shadow: 0 0 8px #FFFFFF; }
        QPushButton:hover { background-color: #FF0033; color: #FFFFFF; border-color: #FF7700; text-shadow: 0 0 15px #FFFFFF; transform: scale(1.05); }
        QPushButton:disabled { background-color: #333333; color: #666666; border-color: #444444; text-shadow: none; }
        QPushButton[class="danger"] { background-color: #FF0033; color: #FFFFFF; border-color: #FF7700; text-shadow: 0 0 10px #FFFFFF; }
        QPushButton[class="danger"]:hover { background-color: #FF7700; color: #FFFFFF; border-color: #FF0033; text-shadow: 0 0 20px #FFFFFF; }
        QPushButton[class="success"] { background-color: #00AFFF; color: #FFFFFF; border-color: #00F6FF; text-shadow: 0 0 10px #FFFFFF; }
        QPushButton[class="success"]:hover { background-color: #00F6FF; color: #000000; border-color: #00AFFF; text-shadow: 0 0 15px #000000; }
        QPushButton[class="primary"] { background-color: #FF7700; color: #FFFFFF; border-color: #00F6FF; text-shadow: 0 0 10px #FFFFFF; }
        QPushButton[class="primary"]:hover { background-color: #00F6FF; color: #000000; border-color: #FF7700; text-shadow: 0 0 15px #000000; }
        QPushButton[class="info"] { background-color: #17a2b8; color: #FFFFFF; border-color: #00F6FF; text-shadow: 0 0 10px #FFFFFF; }
        QPushButton[class="info"]:hover { background-color: #138496; color: #FFFFFF; border-color: #00AFFF; text-shadow: 0 0 15px #FFFFFF; }
        QMenuBar { background-color: #020B1A; border-bottom: 2px solid #00AFFF; padding: 6px; color: #FFFFFF; font-weight: bold; }
        QMenuBar::item { background-color: transparent; padding: 10px 18px; border-radius: 6px; color: #FFFFFF; text-shadow: 0 0 5px #00AFFF; }
        QMenuBar::item:selected { background-color: #001122; color: #00F6FF; text-shadow: 0 0 12px #00F6FF; border: 1px solid #00F6FF; }
        QMenu { background-color: #020B1A; border: 2px solid #00F6FF; border-radius: 8px; padding: 6px; color: #FFFFFF; font-weight: bold; }
        QMenu::item { padding: 10px 18px; border-radius: 6px; color: #FFFFFF; text-shadow: 0 0 5px #00AFFF; }
        QMenu::item:selected { background-color: #002244; color: #00F6FF; text-shadow: 0 0 15px #00F6FF; border: 1px solid #00F6FF; }
        QDialog { background-color: #020B1A; color: #FFFFFF; font-weight: bold; }
        QLineEdit { padding: 10px 14px; border: 2px solid #00AFFF; border-radius: 8px; font-size: 14px; background-color: #001122; color: #FFFFFF; font-weight: bold; text-shadow: 0 0 5px #00AFFF; }
        QLineEdit:focus { border-color: #00F6FF; color: #00F6FF; text-shadow: 0 0 12px #00F6FF; background-color: #002244; }
        QLabel { color: #FFFFFF; font-weight: bold; text-shadow: 0 0 3px #00AFFF; }
        QStatusBar { background-color: #020B1A; color: #FFFFFF; border-top: 2px solid #00AFFF; font-weight: bold; text-shadow: 0 0 5px #00AFFF; }
        """
        self.setStyleSheet(style)
    
    def check_system_theme(self):
        """Check if system theme changed and update app theme (only if using system theme)."""
        # Only check system theme if user has selected system theme preference
        if self.theme_preference != 'system':
            return
            
        logger.debug("check_system_theme: Starting system theme check")
        
        new_theme = self.detect_system_theme()
        logger.debug(f"check_system_theme: Detected theme: {new_theme}, current theme: {self.current_theme}")
        
        if new_theme != self.current_theme:
            logger.debug(f"check_system_theme: Theme changed from {self.current_theme} to {new_theme}")
            self.current_theme = new_theme
            logger.debug(f"check_system_theme: Updated current_theme to {self.current_theme}")
            
            self.apply_styling()
            logger.debug("check_system_theme: Applied new styling")
        else:
            logger.debug("check_system_theme: No theme change detected")
    
    def detect_system_theme(self) -> str:
        """Detect system dark/light mode."""
        try:
            import platform
            system = platform.system()
            
            if system == "Windows":
                try:
                    import winreg
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
                    value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    winreg.CloseKey(key)
                    return 'light' if value else 'dark'
                except:
                    pass
            
            elif system == "Darwin":  # macOS
                try:
                    import subprocess
                    result = subprocess.run(['defaults', 'read', '-g', 'AppleInterfaceStyle'], 
                                          capture_output=True, text=True)
                    return 'dark' if 'Dark' in result.stdout else 'light'
                except:
                    pass
            
            elif system == "Linux":
                try:
                    import subprocess
                    # Try GNOME
                    result = subprocess.run(['gsettings', 'get', 'org.gnome.desktop.interface', 'gtk-theme'], 
                                          capture_output=True, text=True)
                    if 'dark' in result.stdout.lower():
                        return 'dark'
                    # Try KDE
                    result = subprocess.run(['kreadconfig5', '--group', 'General', '--key', 'ColorScheme'], 
                                          capture_output=True, text=True)
                    if 'dark' in result.stdout.lower():
                        return 'dark'
                except:
                    pass
            
            # Fallback to Qt palette detection
            from PyQt5.QtGui import QPalette
            app = QApplication.instance()
            if app:
                palette = app.palette()
                window_color = palette.color(QPalette.Window)
                text_color = palette.color(QPalette.WindowText)
                if window_color.lightness() < text_color.lightness():
                    return 'dark'
            
            return 'light'
        except:
            return 'light'
    
    def set_theme_preference(self, preference: str):
        """Set theme preference (system/light/dark)."""
        logger.debug(f"set_theme_preference: Theme preference change requested to: {preference}")
        
        self.theme_preference = preference
        logger.debug(f"set_theme_preference: Updated theme_preference to: {self.theme_preference}")
        
        # Update current theme based on preference
        if preference == 'system':
            self.current_theme = self.detect_system_theme()
            # Start monitoring system theme changes
            if not self.theme_timer.isActive():
                self.theme_timer.start(1000)
                logger.debug("set_theme_preference: Started system theme monitoring")
        else:
            self.current_theme = preference
            # Stop monitoring system theme changes
            if self.theme_timer.isActive():
                self.theme_timer.stop()
                logger.debug("set_theme_preference: Stopped system theme monitoring")
        
        logger.debug(f"set_theme_preference: Updated current_theme to: {self.current_theme}")
        
        self.save_theme_preference(preference)
        logger.debug(f"set_theme_preference: Saved theme preference: {preference}")
        
        self.apply_styling()
        logger.debug("set_theme_preference: Applied new styling")
        
        # Force complete application refresh
        QApplication.processEvents()
        logger.debug("set_theme_preference: Processed application events")
        
        self.repaint()
        logger.debug("set_theme_preference: Repainted application")
        
        logger.debug(f"set_theme_preference: Theme preference change to {preference} completed")
    

    
    def load_theme_preference(self) -> str:
        """Load theme preference from settings."""
        try:
            from PyQt5.QtCore import QSettings
            settings = QSettings("DbSentinel", "SQLiteExplorer")
            preference = settings.value("theme_preference", "system")
            # Validate preference
            if preference not in ['system', 'light', 'dark']:
                preference = 'system'
            return preference
        except Exception as e:
            logger.error(f"Failed to load theme preference: {e}")
            return 'system'
    
    def save_theme_preference(self, preference: str):
        """Save theme preference to settings."""
        try:
            from PyQt5.QtCore import QSettings
            settings = QSettings("DbSentinel", "SQLiteExplorer")
            settings.setValue("theme_preference", preference)
        except Exception as e:
            logger.error(f"Failed to save theme preference: {e}")
    
    def open_database(self):
        """Open a database file."""
        logger.debug("open_database: Starting database open dialog")
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open SQLite Database",
            "",
            "SQLite Files (*.db *.sqlite *.sqlite3);;All Files (*)"
        )
        logger.debug(f"open_database: File dialog returned: {file_path}")
        
        if not file_path:
            logger.debug("open_database: No file selected, returning")
            return
        
        logger.debug(f"open_database: Testing database connection for: {file_path}")
        # Test database connection
        result = self.db_manager.test_database(file_path)
        logger.debug(f"open_database: Test result: {result}")
        
        if result is None:
            logger.error("open_database: Database test returned None")
            QMessageBox.critical(self, "Error", "Failed to test database connection")
            return
            
        success, is_encrypted, error_msg = result
        logger.debug(f"open_database: success={success}, is_encrypted={is_encrypted}, error_msg={error_msg}")
        
        if success and not is_encrypted:
            logger.debug("open_database: Opening regular SQLite database")
            # Regular SQLite database
            try:
                self.db_manager.connect(file_path)
                logger.debug("open_database: Database connected successfully")
                
                self.load_tables()
                logger.debug("open_database: Tables loaded")
                
                self.add_to_recent_files(file_path)
                logger.debug("open_database: Added to recent files")
                
                self.statusBar().showMessage(f"Connected to: {os.path.basename(file_path)}")
                logger.debug(f"open_database: Status bar updated for: {os.path.basename(file_path)}")
                
            except Exception as e:
                logger.error(f"open_database: Failed to open database: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to open database: {str(e)}")
        
        elif is_encrypted:
            logger.debug("open_database: Database is encrypted, handling encrypted database")
            # Encrypted database - prompt for password
            self.handle_encrypted_database(file_path, error_msg)
        
        else:
            logger.error(f"open_database: Database error: {error_msg}")
            # Error opening database
            QMessageBox.critical(self, "Error", error_msg)
        
        logger.debug("open_database: Database open process completed")
    
    def handle_encrypted_database(self, file_path: str, initial_error: str = ""):
        """Handle encrypted database with password prompt."""
        if not SQLCIPHER_AVAILABLE:
            QMessageBox.critical(
                self, 
                "SQLCipher Not Available", 
                "SQLCipher support is not available. Please install pysqlcipher3:\n\n"
                "pip install pysqlcipher3\n\n"
                "For Ubuntu/Debian systems, you may also need:\n"
                "sudo apt-get install libsqlcipher-dev"
            )
            return
        
        while True:
            password, ok = QInputDialog.getText(
                self,
                "Database Password",
                "This database is encrypted. Please enter the password:" + 
                (f"\n\nError: {initial_error}" if initial_error else ""),
                QLineEdit.Password
            )
            
            if not ok:
                return  # User cancelled
            
            if not password:
                QMessageBox.warning(self, "Warning", "Password cannot be empty.")
                continue
            
            # Clean password (remove whitespace/newlines from copy-paste)
            password = password.strip()
            
            # Test with password
            success, is_encrypted, error_msg = self.db_manager.test_database(file_path, password)
            
            if success:
                try:
                    self.db_manager.connect(file_path, password)
                    self.load_tables()
                    self.add_to_recent_files(file_path, is_encrypted=True)
                    self.statusBar().showMessage(f"Connected to encrypted database: {os.path.basename(file_path)}")
                    break
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to connect: {str(e)}")
                    break
            else:
                # Show error and retry
                initial_error = error_msg
                QMessageBox.warning(self, "Incorrect Password", error_msg)
    
    def close_database(self):
        """Close the current database."""
        self.db_manager.disconnect()
        self.table_list.clear()
        self.table_widget.setRowCount(0)
        self.table_widget.setColumnCount(0)
        self.current_table = None
        self.table_info_label.setText("Select a table to view data")
        self.update_button_states()
        self.statusBar().showMessage("Database closed")
    
    def load_tables(self):
        """Load table list from the connected database."""
        logger.debug("load_tables: Starting table loading")
        
        try:
            tables = self.db_manager.get_tables()
            logger.debug(f"load_tables: Retrieved {len(tables)} tables: {tables}")
            
            self.table_list.clear()
            logger.debug("load_tables: Cleared table list widget")
            
            for i, table in enumerate(tables):
                logger.debug(f"load_tables: Adding table {i+1}/{len(tables)}: {table}")
                item = QListWidgetItem(table)
                self.table_list.addItem(item)
                logger.debug(f"load_tables: Table {table} added to list")
            
            self.update_button_states()
            logger.debug("load_tables: Button states updated")
            
            logger.debug("load_tables: Table loading completed successfully")
            
        except Exception as e:
            logger.error(f"load_tables: Failed to load tables: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to load tables: {str(e)}")
    
    def on_table_selected(self, item):
        """Handle table selection."""
        logger.debug("on_table_selected: Table selection event triggered")
        
        table_name = item.text()
        logger.debug(f"on_table_selected: Selected table: {table_name}")
        
        self.current_table = table_name
        logger.debug(f"on_table_selected: Updated current_table to: {self.current_table}")
        
        self.load_table_data(table_name)
        logger.debug(f"on_table_selected: Loaded data for table: {table_name}")
        
        self.update_button_states()
        logger.debug("on_table_selected: Updated button states")
        
        logger.debug(f"on_table_selected: Table selection handling completed for: {table_name}")
    
    def load_table_data(self, table_name: str):
        """Load data for the selected table."""
        logger.debug(f"load_table_data: Starting data load for table: {table_name}")
        
        try:
            columns, rows, column_types = self.db_manager.get_table_data(table_name)
            logger.debug(f"load_table_data: Retrieved {len(columns)} columns, {len(rows)} rows")
            logger.debug(f"load_table_data: Columns: {columns}")
            logger.debug(f"load_table_data: Column types: {column_types}")
            
            self.table_widget.load_data(columns, rows, column_types)
            logger.debug("load_table_data: Data loaded into table widget")
            
            self.table_info_label.setText(f"📋 {table_name} ({len(rows)} rows, {len(columns)} columns)")
            logger.debug(f"load_table_data: Updated table info label: {table_name} ({len(rows)} rows, {len(columns)} columns)")
            
            self.statusBar().showMessage(f"Loaded {len(rows)} rows from table '{table_name}'")
            logger.debug(f"load_table_data: Updated status bar: Loaded {len(rows)} rows from table '{table_name}'")
            
            logger.debug(f"load_table_data: Table data loading completed for: {table_name}")
            
        except Exception as e:
            logger.error(f"load_table_data: Failed to load table data for {table_name}: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to load table data: {str(e)}")
    
    def on_cell_changed(self, row: int, col: int, new_value: str):
        """Handle cell editing."""
        if not self.current_table:
            return
        
        try:
            # Get rowid from first column
            rowid_item = self.table_widget.item(row, 0)
            if not rowid_item:
                return
            
            rowid = int(rowid_item.text())
            
            # Get column name from header
            column_name = self.table_widget.horizontalHeaderItem(col).text()
            
            # Skip if trying to edit rowid
            if column_name.lower() == 'rowid':
                QMessageBox.warning(self, "Warning", "Cannot edit rowid column")
                return
            
            # Update database
            self.db_manager.update_cell(self.current_table, rowid, column_name, new_value)
            self.statusBar().showMessage(f"Updated {column_name} in row {rowid}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update cell: {str(e)}")
            # Reload table to revert changes
            self.load_table_data(self.current_table)
    
    def on_blob_changed(self, row: int, col: int, blob_data: bytes):
        """Handle BLOB cell editing."""
        if not self.current_table:
            return
        
        try:
            # Get rowid from first column
            rowid_item = self.table_widget.item(row, 0)
            if not rowid_item:
                return
            
            rowid = int(rowid_item.text())
            
            # Get column name from header
            column_name = self.table_widget.horizontalHeaderItem(col).text()
            
            # Update database with blob data
            self.db_manager.update_cell(self.current_table, rowid, column_name, blob_data)
            self.statusBar().showMessage(f"Updated BLOB {column_name} in row {rowid}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update BLOB cell: {str(e)}")
            # Reload table to revert changes
            self.load_table_data(self.current_table)
    
    def add_row(self):
        """Add a new row to the current table."""
        if not self.current_table:
            return
        
        try:
            # Get table structure
            columns = self.db_manager.get_table_info(self.current_table)
            
            # Show add row dialog
            dialog = AddRowDialog(columns, self)
            if dialog.exec_() == QDialog.Accepted:
                data = dialog.get_data()
                self.db_manager.insert_row(self.current_table, data)
                self.load_table_data(self.current_table)
                self.statusBar().showMessage("Row added successfully")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add row: {str(e)}")
    
    def delete_selected_rows(self):
        """Delete selected rows."""
        if not self.current_table:
            return
        
        rowids = self.table_widget.get_selected_rowids()
        if not rowids:
            QMessageBox.information(self, "Information", "No rows selected")
            return
        
        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete {len(rowids)} row(s)?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.db_manager.delete_rows(self.current_table, rowids)
                self.load_table_data(self.current_table)
                self.statusBar().showMessage(f"Deleted {len(rowids)} row(s)")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete rows: {str(e)}")
    
    def create_table(self):
        """Create a new table."""
        if not self.db_manager.connection:
            return
        
        try:
            dialog = CreateTableDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                table_name, columns = dialog.get_table_data()
                self.db_manager.create_table(table_name, columns)
                self.load_tables()
                self.statusBar().showMessage(f"Table '{table_name}' created successfully")
        except ValueError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create table: {str(e)}")
    
    def add_column_to_table(self):
        """Add a column to the current table."""
        if not self.current_table:
            return
        
        try:
            dialog = AddColumnDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                column = dialog.get_column_data()
                self.db_manager.add_column(self.current_table, column)
                self.load_table_data(self.current_table)
                self.statusBar().showMessage(f"Column '{column['name']}' added to table '{self.current_table}'")
        except ValueError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add column: {str(e)}")
    
    def refresh_table(self):
        """Refresh the current table data."""
        if self.current_table:
            self.load_table_data(self.current_table)
    
    def on_selection_changed(self):
        """Handle selection changes."""
        self.update_button_states()
    
    def update_button_states(self):
        """Update button enabled states."""
        has_db = self.db_manager.connection is not None
        has_table = self.current_table is not None
        has_selection = len(self.table_widget.get_selected_rowids()) > 0
        
        self.create_table_btn.setEnabled(has_db)
        self.add_column_btn.setEnabled(has_table)
        self.add_row_btn.setEnabled(has_table)
        self.delete_rows_btn.setEnabled(has_table and has_selection)
        self.refresh_btn.setEnabled(has_table)
        self.sql_btn.setEnabled(has_db)
        
        # Update table info when no table selected
        if not has_table:
            self.table_info_label.setText("Select a table to view data")
            self.table_info_label.setStyleSheet("color: #FF0033; padding: 5px 0; font-weight: bold;")
    
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About SQLite Database Explorer",
            "SQLite Database Explorer v1.0\n\n"
            "A comprehensive desktop application for exploring SQLite databases "
            "with full SQLCipher encrypted database support.\n\n"
            "Features:\n"
            "• Browse database tables\n"
            "• View and edit table data\n"
            "• Add and delete rows\n"
            "• SQLCipher encrypted database support\n"
            "• BLOB preview for images, PDFs, and text\n"
            "• Sort columns by clicking headers\n"
            "• Clean, responsive interface\n\n"
            "Built with PyQt5"
        )
    
    def resizeEvent(self, event):
        """Handle window resizing for responsiveness."""
        super().resizeEvent(event)
        
        # Adjust splitter sizes based on window width
        if hasattr(self, 'splitter'):
            width = self.width()
            if width < 800:
                # Very small window - minimize sidebar
                sidebar_width = min(200, width // 4)
                self.splitter.setSizes([sidebar_width, width - sidebar_width])
            elif width < 1200:
                # Medium window - reduce sidebar
                sidebar_width = min(250, width // 3)
                self.splitter.setSizes([sidebar_width, width - sidebar_width])
            else:
                # Large window - standard proportions
                self.splitter.setSizes([300, width - 300])
    
    def closeEvent(self, event):
        """Handle application closing."""
        logger.debug("closeEvent: Main application closeEvent triggered")
        
        try:
            logger.debug("closeEvent: Stopping theme timer")
            if hasattr(self, 'theme_timer'):
                self.theme_timer.stop()
                logger.debug("closeEvent: Theme timer stopped")
            
            logger.debug("closeEvent: Disconnecting database")
            self.db_manager.disconnect()
            logger.debug("closeEvent: Database disconnected successfully")
            
            # Clean up uploads folder (database copies, not originals)
            logger.debug("closeEvent: Starting uploads folder cleanup")
            self.cleanup_uploads_folder()
            logger.debug("closeEvent: Uploads folder cleanup completed")
            
            event.accept()
            logger.debug("closeEvent: Main application close event accepted")
            
        except Exception as e:
            logger.error(f"closeEvent: Error during main application close: {e}")
            event.accept()
            logger.debug("closeEvent: Close event accepted despite error")
    
    def cleanup_uploads_folder(self):
        """Clean up database files from uploads folder."""
        try:
            uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
            if os.path.exists(uploads_dir):
                logger.debug(f"Cleaning up uploads folder: {uploads_dir}")
                for filename in os.listdir(uploads_dir):
                    if filename == '.gitkeep':
                        continue  # Keep .gitkeep file
                    file_path = os.path.join(uploads_dir, filename)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                            logger.debug(f"Deleted upload file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Could not delete upload file {file_path}: {e}")
                logger.debug("Uploads folder cleanup completed")
        except Exception as e:
            logger.error(f"Error cleaning uploads folder: {e}")
    
    def load_recent_files(self) -> list:
        """Load recent files from settings."""
        try:
            from PyQt5.QtCore import QSettings
            settings = QSettings("DbSentinel", "SQLiteExplorer")
            recent = settings.value("recent_files", [])
            return recent if isinstance(recent, list) else []
        except:
            return []
    
    def save_recent_files(self):
        """Save recent files to settings."""
        try:
            from PyQt5.QtCore import QSettings
            settings = QSettings("DbSentinel", "SQLiteExplorer")
            settings.setValue("recent_files", self.recent_files)
        except Exception as e:
            logger.error(f"Failed to save recent files: {e}")
    
    def add_to_recent_files(self, file_path: str, is_encrypted: bool = False):
        """Add file to recent files list."""
        file_info = {
            'path': file_path,
            'name': os.path.basename(file_path),
            'encrypted': is_encrypted,
            'timestamp': QDateTime.currentDateTime().toString()
        }
        
        # Remove if already exists
        self.recent_files = [f for f in self.recent_files if f.get('path') != file_path]
        
        # Add to beginning
        self.recent_files.insert(0, file_info)
        
        # Keep only last 10
        self.recent_files = self.recent_files[:10]
        
        self.save_recent_files()
        self.update_recent_menu()
    
    def update_recent_menu(self):
        """Update recent files menu."""
        self.recent_menu.clear()
        
        if not self.recent_files:
            no_recent = self.recent_menu.addAction("No recent databases")
            no_recent.setEnabled(False)
            return
        
        for file_info in self.recent_files:
            file_path = file_info.get('path', '')
            file_name = file_info.get('name', os.path.basename(file_path))
            is_encrypted = file_info.get('encrypted', False)
            
            # Check if file still exists
            if not os.path.exists(file_path):
                continue
            
            # Create menu item
            icon = "🔒" if is_encrypted else "📁"
            action_text = f"{icon} {file_name}"
            
            action = self.recent_menu.addAction(action_text)
            action.setToolTip(file_path)
            action.triggered.connect(lambda checked, path=file_path: self.open_recent_file(path))
        
        if self.recent_files:
            self.recent_menu.addSeparator()
            clear_action = self.recent_menu.addAction("Clear Recent Files")
            clear_action.triggered.connect(self.clear_recent_files)
    
    def open_recent_file(self, file_path: str):
        """Open a recent database file."""
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "File Not Found", f"Database file not found:\n{file_path}")
            # Remove from recent files
            self.recent_files = [f for f in self.recent_files if f.get('path') != file_path]
            self.save_recent_files()
            self.update_recent_menu()
            return
        
        # Test database connection
        result = self.db_manager.test_database(file_path)
        if result is None:
            QMessageBox.critical(self, "Error", "Failed to test database connection")
            return
        success, is_encrypted, error_msg = result
        
        if success and not is_encrypted:
            # Regular SQLite database
            try:
                self.db_manager.connect(file_path)
                self.load_tables()
                self.add_to_recent_files(file_path)
                self.statusBar().showMessage(f"Connected to: {os.path.basename(file_path)}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open database: {str(e)}")
        elif is_encrypted:
            # Encrypted database - prompt for password
            self.handle_encrypted_database(file_path, error_msg)
        else:
            # Error opening database
            QMessageBox.critical(self, "Error", error_msg)
    
    def clear_recent_files(self):
        """Clear all recent files."""
        reply = QMessageBox.question(
            self,
            "Clear Recent Files",
            "Are you sure you want to clear all recent database files?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.recent_files = []
            self.save_recent_files()
            self.update_recent_menu()
    
    def open_sql_dialog(self):
        """Open SQL dialog."""
        if not self.db_manager.connection:
            return
        
        dialog = SQLQueryDialog(self.db_manager, "", self)
        dialog.exec_()
        
        # Refresh tables list if structure might have changed
        if dialog.structure_changed:
            self.load_tables()
        
        # Refresh current table if data might have changed
        if dialog.data_changed and self.current_table:
            self.load_table_data(self.current_table)


def main():
    """Main application entry point."""
    logger.info("main: Starting SQLite Database Explorer with comprehensive debugging")
    
    logger.debug("main: Creating QApplication instance")
    app = QApplication(sys.argv)
    logger.debug("main: QApplication created")
    
    app.setApplicationName("SQLite Database Explorer")
    logger.debug("main: Application name set to 'SQLite Database Explorer'")
    
    app.setApplicationVersion("1.0")
    logger.debug("main: Application version set to '1.0'")
    
    # Set application icon (if available)
    logger.debug("main: Attempting to set application icon")
    try:
        app.setWindowIcon(QIcon("database.ico"))
        logger.debug("main: Application icon set successfully")
    except Exception as e:
        logger.debug(f"main: Icon file not found or failed to load: {e}")
        pass  # Icon file not found, continue without icon
    
    # Create and show main window
    logger.debug("main: Creating main window")
    window = SQLiteExplorer()
    logger.debug("main: Main window created")
    
    window.show()
    logger.debug("main: Main window shown")
    
    # Check for SQLCipher availability and show warning if not available
    logger.debug(f"main: Checking SQLCipher availability: {SQLCIPHER_AVAILABLE}")
    if not SQLCIPHER_AVAILABLE:
        logger.debug("main: SQLCipher not available, scheduling warning dialog")
        QTimer.singleShot(1000, lambda: (
            logger.debug("main: Showing SQLCipher warning dialog"),
            QMessageBox.information(
                window,
                "SQLCipher Support",
                "SQLCipher support is not available.\n\n"
                "To enable encrypted database support, install pysqlcipher3:\n"
                "pip install pysqlcipher3\n\n"
                "For Ubuntu/Debian systems, you may also need:\n"
                "sudo apt-get install libsqlcipher-dev\n\n"
                "The application will work with regular SQLite databases."
            ),
            logger.debug("main: SQLCipher warning dialog shown")
        ))
    else:
        logger.debug("main: SQLCipher is available")
    
    logger.debug("main: Starting application event loop")
    exit_code = app.exec_()
    logger.info(f"main: Application exited with code: {exit_code}")
    
    logger.debug("main: Calling sys.exit")
    sys.exit(exit_code)


if __name__ == "__main__":
    logger.debug("__main__: Script started as main module")
    main()
    logger.debug("__main__: Main function completed")