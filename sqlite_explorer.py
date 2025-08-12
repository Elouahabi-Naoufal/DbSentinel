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
    QGroupBox, QGridLayout, QTextEdit, QSlider
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QUrl
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
    
    def setup_ui(self):
        self.setWindowTitle(f"Preview: {self.column_name}")
        self.setModal(True)
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel(f"Content Preview - {self.column_name} ({len(self.blob_data)} bytes)")
        header.setFont(QFont("Segoe UI", 12, QFont.Bold))
        header.setStyleSheet("color: #2c3e50; padding: 10px; background: #f8f9fa; border-radius: 6px;")
        layout.addWidget(header)
        
        # Content area
        self.content_widget = self.create_content_widget()
        layout.addWidget(self.content_widget)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save As...")
        save_btn.clicked.connect(self.save_blob)
        button_layout.addWidget(save_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
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
        else:
            return self.create_hex_widget()
    
    def detect_content_type(self) -> str:
        """Detect content type from blob data."""
        if not self.blob_data:
            return 'empty'
        
        # Check for image formats
        if self.blob_data.startswith(b'\xff\xd8\xff'):  # JPEG
            return 'image'
        elif self.blob_data.startswith(b'\x89PNG\r\n\x1a\n'):  # PNG
            return 'image'
        elif self.blob_data.startswith(b'GIF8'):  # GIF
            return 'image'
        elif self.blob_data.startswith(b'BM'):  # BMP
            return 'image'
        elif self.blob_data.startswith(b'RIFF') and b'WEBP' in self.blob_data[:12]:  # WebP
            return 'image'
        
        # Check for video formats
        elif (self.blob_data.startswith(b'\x00\x00\x00\x18ftypmp4') or  # MP4
              self.blob_data.startswith(b'\x00\x00\x00\x20ftypmp4')):
            return 'video'
        
        # Check for audio formats
        elif (self.blob_data.startswith(b'ID3') or  # MP3 with ID3
              self.blob_data.startswith(b'\xff\xfb') or  # MP3
              self.blob_data.startswith(b'\xff\xf3') or  # MP3
              self.blob_data.startswith(b'\xff\xf2')):  # MP3
            return 'audio'
        
        # Check for PDF
        elif self.blob_data.startswith(b'%PDF'):  # PDF
            return 'pdf'
        
        # Check if it's text (UTF-8)
        try:
            text_content = self.blob_data.decode('utf-8')
            # Check if it's markdown
            if ('# ' in text_content or '## ' in text_content or 
                '**' in text_content or '*' in text_content or
                '[' in text_content and '](' in text_content):
                return 'markdown'
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
                image_label.setStyleSheet("border: 1px solid #ddd; background: white;")
                
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
            logger.debug("Creating temporary file for video")
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                temp_file.write(self.blob_data)
                temp_path = temp_file.name
            logger.debug(f"Temporary video file created: {temp_path}")
            
            logger.debug("Creating QVideoWidget and QMediaPlayer")
            self.video_widget = QVideoWidget()
            self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
            self.media_player.setVideoOutput(self.video_widget)
            
            layout.addWidget(self.video_widget)
            
            # Playback controls
            controls_layout = QHBoxLayout()
            
            play_btn = QPushButton("▶️")
            play_btn.setMaximumWidth(40)
            play_btn.clicked.connect(lambda: self.safe_media_action("play"))
            controls_layout.addWidget(play_btn)
            
            pause_btn = QPushButton("⏸️")
            pause_btn.setMaximumWidth(40)
            pause_btn.clicked.connect(lambda: self.safe_media_action("pause"))
            controls_layout.addWidget(pause_btn)
            
            stop_btn = QPushButton("⏹️")
            stop_btn.setMaximumWidth(40)
            stop_btn.clicked.connect(lambda: self.safe_media_action("stop"))
            controls_layout.addWidget(stop_btn)
            
            # Seek slider
            from PyQt5.QtWidgets import QSlider
            self.seek_slider = QSlider(Qt.Horizontal)
            self.seek_slider.setMinimum(0)
            self.seek_slider.setMaximum(100)
            self.seek_slider.sliderPressed.connect(self.on_seek_start)
            self.seek_slider.sliderReleased.connect(self.on_seek_end)
            controls_layout.addWidget(self.seek_slider)
            
            # Time labels
            self.time_label = QLabel("00:00 / 00:00")
            self.time_label.setMinimumWidth(80)
            controls_layout.addWidget(self.time_label)
            
            layout.addLayout(controls_layout)
            
            # Speed control
            speed_layout = QHBoxLayout()
            speed_layout.addWidget(QLabel("Speed:"))
            
            self.speed_combo = QComboBox()
            self.speed_combo.addItems(["0.25x", "0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"])
            self.speed_combo.setCurrentText("1.0x")
            self.speed_combo.currentTextChanged.connect(self.on_speed_changed)
            speed_layout.addWidget(self.speed_combo)
            
            speed_layout.addStretch()
            layout.addLayout(speed_layout)
            
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
            logger.debug("Creating temporary file for audio")
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_file.write(self.blob_data)
                temp_path = temp_file.name
            logger.debug(f"Temporary audio file created: {temp_path}")
            
            info_label = QLabel(f"🎵 Audio File ({len(self.blob_data)} bytes)")
            info_label.setStyleSheet("font-size: 14px; padding: 20px; text-align: center;")
            info_label.setAlignment(Qt.AlignCenter)
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
            layout.addLayout(controls_layout)
            
            layout.addStretch()
            
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
            
            # Use QWebEngineView to display PDF
            web_view = QWebEngineView()
            web_view.load(QUrl.fromLocalFile(temp_path))
            layout.addWidget(web_view)
            
            # Store temp file for cleanup
            self.temp_files.append(temp_path)
        except Exception as e:
            layout.addWidget(QLabel(f"Error loading PDF: {str(e)}"))
        
        return widget
    
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
    
    def save_blob(self):
        """Save blob data to file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Blob Data",
            f"{self.column_name}_data",
            "All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'wb') as f:
                    f.write(self.blob_data)
                QMessageBox.information(self, "Success", f"Data saved to {file_path}")
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
                self.seek_slider.setValue(int((position / duration) * 100))
            
            # Update time label
            current_time = self.format_time(position)
            total_time = self.format_time(duration)
            self.time_label.setText(f"{current_time} / {total_time}")
    
    def on_duration_changed(self, duration):
        """Update controls when video duration is available."""
        if hasattr(self, 'time_label'):
            total_time = self.format_time(duration)
            self.time_label.setText(f"00:00 / {total_time}")
    
    def on_seek_start(self):
        """Handle seek slider press."""
        self.seeking = True
    
    def on_seek_end(self):
        """Handle seek slider release."""
        if hasattr(self, 'media_player') and self.media_player:
            duration = self.media_player.duration()
            if duration > 0:
                position = int((self.seek_slider.value() / 100) * duration)
                self.media_player.setPosition(position)
        self.seeking = False
    
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
            
            # Clean up temporary files
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
            "All Files (*);;Images (*.jpg *.jpeg *.png *.bmp *.gif *.tiff *.webp);;Documents (*.pdf *.txt *.md *.doc *.docx);;Videos (*.mp4 *.avi *.mov *.mkv);;Audio (*.mp3 *.wav *.m4a)"
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
            "All Files (*);;Images (*.jpg *.jpeg *.png *.bmp *.gif *.tiff *.webp);;Documents (*.pdf *.txt *.md *.doc *.docx);;Videos (*.mp4 *.avi *.mov *.mkv);;Audio (*.mp3 *.wav *.m4a)"
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
        """Save blob data to file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save {column_name}",
            f"{column_name}_data",
            "All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'wb') as f:
                    f.write(blob_data)
                QMessageBox.information(self, "Success", f"Data saved to {file_path}")
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
        super().__init__()
        self.db_manager = DatabaseManager()
        self.current_table = None
        self.setup_ui()
        self.apply_styling()
    
    def setup_ui(self):
        """Setup the user interface."""
        self.setWindowTitle("SQLite Database Explorer - Professional Edition")
        self.setMinimumSize(1000, 700)
        self.resize(1400, 900)
        
        # Enable window resizing and make it responsive
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        
        # Central widget with splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(1)
        main_layout.addWidget(self.splitter)
        
        # Left sidebar for tables
        self.setup_sidebar(self.splitter)
        
        # Right main area for table data
        self.setup_main_area(self.splitter)
        
        # Set splitter proportions (responsive)
        self.splitter.setSizes([350, 1050])
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        
        # Menu and toolbar
        self.setup_menu()
        
        # Status bar with professional styling
        status_bar = self.statusBar()
        status_bar.showMessage("Ready - Open a database to get started")
        status_bar.setStyleSheet("QStatusBar { border-top: 1px solid #e0e0e0; background: #f8f9fa; color: #495057; }")
    
    def setup_sidebar(self, parent):
        """Setup the left sidebar with table list."""
        sidebar_widget = QWidget()
        sidebar_widget.setMinimumWidth(280)
        sidebar_widget.setMaximumWidth(500)
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(15, 15, 15, 15)
        sidebar_layout.setSpacing(10)
        
        # Header with icon and title
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 10)
        
        title_label = QLabel("📊 Database Tables")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_label.setStyleSheet("color: #2c3e50; padding: 5px 0;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        sidebar_layout.addLayout(header_layout)
        
        # Table list with search
        self.table_list = QListWidget()
        self.table_list.itemClicked.connect(self.on_table_selected)
        self.table_list.setMinimumHeight(200)
        sidebar_layout.addWidget(self.table_list)
        
        parent.addWidget(sidebar_widget)
    
    def setup_main_area(self, parent):
        """Setup the main area with table data and controls."""
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # Header with table info and controls
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Table info
        self.table_info_label = QLabel("Select a table to view data")
        self.table_info_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.table_info_label.setStyleSheet("color: #2c3e50; padding: 5px 0;")
        header_layout.addWidget(self.table_info_label)
        
        header_layout.addStretch()
        
        # Control buttons with icons
        self.create_table_btn = QPushButton("📋 Create Table")
        self.create_table_btn.clicked.connect(self.create_table)
        self.create_table_btn.setEnabled(False)
        self.create_table_btn.setMinimumHeight(35)
        header_layout.addWidget(self.create_table_btn)
        
        self.add_column_btn = QPushButton("➕ Add Column")
        self.add_column_btn.clicked.connect(self.add_column_to_table)
        self.add_column_btn.setEnabled(False)
        self.add_column_btn.setMinimumHeight(35)
        header_layout.addWidget(self.add_column_btn)
        
        self.add_row_btn = QPushButton("➕ Add Row")
        self.add_row_btn.clicked.connect(self.add_row)
        self.add_row_btn.setEnabled(False)
        self.add_row_btn.setMinimumHeight(35)
        header_layout.addWidget(self.add_row_btn)
        
        self.delete_rows_btn = QPushButton("🗑️ Delete Selected")
        self.delete_rows_btn.clicked.connect(self.delete_selected_rows)
        self.delete_rows_btn.setEnabled(False)
        self.delete_rows_btn.setMinimumHeight(35)
        header_layout.addWidget(self.delete_rows_btn)
        
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.refresh_table)
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setMinimumHeight(35)
        header_layout.addWidget(self.refresh_btn)
        
        main_layout.addWidget(header_widget)
        
        # Table widget with container
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        
        self.table_widget = TableWidget()
        self.table_widget.cell_changed_signal.connect(self.on_cell_changed)
        self.table_widget.blob_changed_signal.connect(self.on_blob_changed)
        self.table_widget.itemSelectionChanged.connect(self.on_selection_changed)
        table_layout.addWidget(self.table_widget)
        
        main_layout.addWidget(table_container)
        parent.addWidget(main_widget)
    
    def setup_menu(self):
        """Setup menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        open_action = file_menu.addAction('Open Database...')
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_database)
        
        file_menu.addSeparator()
        
        close_action = file_menu.addAction('Close Database')
        close_action.triggered.connect(self.close_database)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction('Exit')
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        about_action = help_menu.addAction('About')
        about_action.triggered.connect(self.show_about)
    
    def apply_styling(self):
        """Apply professional modern theme styling."""
        style = """
        QMainWindow {
            background-color: #f8f9fa;
            font-family: 'Segoe UI', 'Arial', sans-serif;
        }
        
        QWidget {
            background-color: #f8f9fa;
        }
        
        QSplitter::handle {
            background-color: #dee2e6;
            width: 1px;
        }
        
        QSplitter::handle:hover {
            background-color: #007bff;
        }
        
        QListWidget {
            background-color: white;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 8px;
            font-size: 13px;
            outline: none;
        }
        
        QListWidget::item {
            padding: 12px 16px;
            border-radius: 6px;
            margin: 2px 0;
            border: none;
            color: #495057;
        }
        
        QListWidget::item:hover {
            background-color: #e3f2fd;
            color: #1976d2;
        }
        
        QListWidget::item:selected {
            background-color: #1976d2;
            color: white;
            font-weight: 500;
        }
        
        QTableWidget {
            background-color: white;
            gridline-color: #e9ecef;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            font-size: 13px;
            selection-background-color: #e3f2fd;
        }
        
        QTableWidget::item {
            padding: 8px 12px;
            border: none;
            min-width: 120px;
        }
        
        QTableWidget QLineEdit {
            padding: 4px 8px;
            border: 2px solid #007bff;
            border-radius: 4px;
            background-color: white;
            font-size: 13px;
            min-width: 200px;
        }
        
        QTableWidget::item:selected {
            background-color: #e3f2fd;
            color: #1976d2;
        }
        
        QHeaderView::section {
            background-color: #2c3e50;
            color: white;
            padding: 12px 16px;
            border: none;
            border-right: 1px solid #34495e;
            font-weight: 600;
            font-size: 13px;
        }
        
        QHeaderView::section:hover {
            background-color: #34495e;
        }
        
        QPushButton {
            background-color: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            font-weight: 500;
            font-size: 13px;
            min-width: 100px;
        }
        
        QPushButton:hover {
            background-color: #0056b3;
            transform: translateY(-1px);
        }
        
        QPushButton:pressed {
            background-color: #004085;
            transform: translateY(0px);
        }
        
        QPushButton:disabled {
            background-color: #6c757d;
            color: #adb5bd;
        }
        
        QPushButton[class="danger"] {
            background-color: #dc3545;
        }
        
        QPushButton[class="danger"]:hover {
            background-color: #c82333;
        }
        
        QPushButton[class="success"] {
            background-color: #28a745;
        }
        
        QPushButton[class="success"]:hover {
            background-color: #218838;
        }
        
        QPushButton[class="primary"] {
            background-color: #6f42c1;
        }
        
        QPushButton[class="primary"]:hover {
            background-color: #5a32a3;
        }
        
        QMenuBar {
            background-color: white;
            border-bottom: 1px solid #e9ecef;
            padding: 4px;
        }
        
        QMenuBar::item {
            background-color: transparent;
            padding: 8px 16px;
            border-radius: 4px;
        }
        
        QMenuBar::item:selected {
            background-color: #e9ecef;
        }
        
        QMenu {
            background-color: white;
            border: 1px solid #e9ecef;
            border-radius: 6px;
            padding: 4px;
        }
        
        QMenu::item {
            padding: 8px 16px;
            border-radius: 4px;
        }
        
        QMenu::item:selected {
            background-color: #007bff;
            color: white;
        }
        
        QDialog {
            background-color: white;
        }
        
        QLineEdit {
            padding: 8px 12px;
            border: 2px solid #e9ecef;
            border-radius: 6px;
            font-size: 13px;
            background-color: white;
        }
        
        QLineEdit:focus {
            border-color: #007bff;
            outline: none;
        }
        
        QLabel {
            color: #495057;
        }
        """
        self.setStyleSheet(style)
        
        # Set button classes for different styles
        self.delete_rows_btn.setProperty("class", "danger")
        self.add_row_btn.setProperty("class", "success")
        self.add_column_btn.setProperty("class", "success")
        self.create_table_btn.setProperty("class", "primary")
    
    def open_database(self):
        """Open a database file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open SQLite Database",
            "",
            "SQLite Files (*.db *.sqlite *.sqlite3);;All Files (*)"
        )
        
        if not file_path:
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
                self.statusBar().showMessage(f"Connected to: {os.path.basename(file_path)}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open database: {str(e)}")
        
        elif is_encrypted:
            # Encrypted database - prompt for password
            self.handle_encrypted_database(file_path, error_msg)
        
        else:
            # Error opening database
            QMessageBox.critical(self, "Error", error_msg)
    
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
        try:
            tables = self.db_manager.get_tables()
            self.table_list.clear()
            
            for table in tables:
                item = QListWidgetItem(table)
                self.table_list.addItem(item)
            
            self.update_button_states()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load tables: {str(e)}")
    
    def on_table_selected(self, item):
        """Handle table selection."""
        table_name = item.text()
        self.current_table = table_name
        self.load_table_data(table_name)
        self.update_button_states()
    
    def load_table_data(self, table_name: str):
        """Load data for the selected table."""
        try:
            columns, rows, column_types = self.db_manager.get_table_data(table_name)
            self.table_widget.load_data(columns, rows, column_types)
            self.table_info_label.setText(f"📋 {table_name} ({len(rows)} rows, {len(columns)} columns)")
            self.statusBar().showMessage(f"Loaded {len(rows)} rows from table '{table_name}'")
        except Exception as e:
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
        
        # Update table info when no table selected
        if not has_table:
            self.table_info_label.setText("Select a table to view data")
    
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
            if width < 1200:
                # Smaller window - reduce sidebar
                self.splitter.setSizes([250, width - 250])
            else:
                # Larger window - standard proportions
                self.splitter.setSizes([350, width - 350])
    
    def closeEvent(self, event):
        """Handle application closing."""
        logger.debug("Main application closeEvent triggered")
        try:
            self.db_manager.disconnect()
            logger.debug("Database disconnected successfully")
            event.accept()
            logger.debug("Main application close event accepted")
        except Exception as e:
            logger.error(f"Error during main application close: {e}")
            event.accept()


def main():
    """Main application entry point."""
    logger.info("Starting SQLite Database Explorer with comprehensive debugging")
    
    app = QApplication(sys.argv)
    app.setApplicationName("SQLite Database Explorer")
    app.setApplicationVersion("1.0")
    
    # Set application icon (if available)
    try:
        app.setWindowIcon(QIcon("database.ico"))
    except:
        pass  # Icon file not found, continue without icon
    
    # Create and show main window
    logger.debug("Creating main window")
    window = SQLiteExplorer()
    window.show()
    logger.debug("Main window shown")
    
    # Check for SQLCipher availability and show warning if not available
    if not SQLCIPHER_AVAILABLE:
        QTimer.singleShot(1000, lambda: QMessageBox.information(
            window,
            "SQLCipher Support",
            "SQLCipher support is not available.\n\n"
            "To enable encrypted database support, install pysqlcipher3:\n"
            "pip install pysqlcipher3\n\n"
            "For Ubuntu/Debian systems, you may also need:\n"
            "sudo apt-get install libsqlcipher-dev\n\n"
            "The application will work with regular SQLite databases."
        ))
    
    logger.debug("Starting application event loop")
    exit_code = app.exec_()
    logger.info(f"Application exited with code: {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()