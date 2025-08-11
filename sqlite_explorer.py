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
from typing import Optional, List, Tuple, Any

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QInputDialog, QDialog,
    QDialogButtonBox, QFormLayout, QLineEdit, QLabel, QPushButton,
    QAbstractItemView, QCheckBox, QFrame
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor

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
    
    def get_table_data(self, table_name: str) -> Tuple[List[str], List[List[Any]]]:
        """Get all data from a table."""
        if not self.connection:
            raise Exception("No database connection")
        
        cursor = self.connection.cursor()
        
        # Get column names
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Get data
        cursor.execute(f"SELECT rowid, * FROM {table_name};")
        rows = cursor.fetchall()
        
        return ['rowid'] + columns, rows
    
    def insert_row(self, table_name: str, data: dict) -> bool:
        """Insert a new row into the table."""
        if not self.connection:
            raise Exception("No database connection")
        
        columns = list(data.keys())
        values = list(data.values())
        placeholders = ', '.join(['?' for _ in values])
        column_names = ', '.join(columns)
        
        query = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"
        
        cursor = self.connection.cursor()
        cursor.execute(query, values)
        self.connection.commit()
        return True
    
    def update_cell(self, table_name: str, rowid: int, column: str, value: Any) -> bool:
        """Update a single cell in the table."""
        if not self.connection:
            raise Exception("No database connection")
        
        query = f"UPDATE {table_name} SET {column} = ? WHERE rowid = ?"
        cursor = self.connection.cursor()
        cursor.execute(query, (value, rowid))
        self.connection.commit()
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
            value = widget.text().strip()
            data[column_name] = value if value else None
        return data


class TableWidget(QTableWidget):
    """Enhanced table widget with editing capabilities."""
    
    cell_changed_signal = pyqtSignal(int, int, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_table()
        self.selected_rows = set()
    
    def setup_table(self):
        """Setup table properties and styling."""
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setGridStyle(Qt.SolidLine)
        self.setSortingEnabled(True)
        self.setShowGrid(True)
        
        # Set header properties for responsiveness
        h_header = self.horizontalHeader()
        h_header.setStretchLastSection(True)
        h_header.setSectionResizeMode(QHeaderView.Interactive)
        h_header.setDefaultSectionSize(150)
        h_header.setMinimumSectionSize(80)
        h_header.setCascadingSectionResizes(True)
        
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(35)
        
        # Connect signals
        self.itemChanged.connect(self.on_item_changed)
    
    def on_item_changed(self, item):
        """Handle cell editing."""
        if hasattr(item, 'original_value') and item.text() != item.original_value:
            self.cell_changed_signal.emit(item.row(), item.column(), item.text())
            item.original_value = item.text()
    
    def load_data(self, columns: List[str], rows: List[List[Any]]):
        """Load data into the table."""
        self.setRowCount(len(rows))
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(columns)
        
        for row_idx, row_data in enumerate(rows):
            for col_idx, cell_data in enumerate(row_data):
                item = QTableWidgetItem(str(cell_data) if cell_data is not None else "")
                item.original_value = str(cell_data) if cell_data is not None else ""
                self.setItem(row_idx, col_idx, item)
        
        self.resizeColumnsToContents()
    
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
            columns, rows = self.db_manager.get_table_data(table_name)
            self.table_widget.load_data(columns, rows)
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
        self.db_manager.disconnect()
        event.accept()


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("SQLite Database Explorer")
    app.setApplicationVersion("1.0")
    
    # Set application icon (if available)
    try:
        app.setWindowIcon(QIcon("database.ico"))
    except:
        pass  # Icon file not found, continue without icon
    
    # Create and show main window
    window = SQLiteExplorer()
    window.show()
    
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
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()