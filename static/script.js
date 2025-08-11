// SQLite Database Explorer JavaScript
class DatabaseExplorer {
    constructor() {
        this.currentTable = null;
        this.currentPage = 1;
        this.tableData = null;
        this.selectedRows = new Set();
        this.sortColumn = null;
        this.sortDirection = 'asc';
        
        this.initializeEventListeners();
    }
    
    initializeEventListeners() {
        // Table selection
        document.querySelectorAll('.table-item').forEach(item => {
            item.addEventListener('click', (e) => {
                this.selectTable(e.target.dataset.table);
            });
        });
        
        // Add row button
        document.getElementById('add-row-btn')?.addEventListener('click', () => {
            this.showAddRowModal();
        });
        
        // Delete selected button
        document.getElementById('delete-selected-btn')?.addEventListener('click', () => {
            this.deleteSelectedRows();
        });
        
        // Refresh button
        document.getElementById('refresh-btn')?.addEventListener('click', () => {
            this.loadTableData(this.currentTable, this.currentPage);
        });
        
        // Save row button
        document.getElementById('save-row-btn')?.addEventListener('click', () => {
            this.saveNewRow();
        });
    }
    
    selectTable(tableName) {
        // Update UI
        document.querySelectorAll('.table-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`[data-table="${tableName}"]`).classList.add('active');
        
        // Show table content area
        document.getElementById('welcome-message').style.display = 'none';
        document.getElementById('table-content').style.display = 'block';
        
        this.currentTable = tableName;
        this.currentPage = 1;
        this.selectedRows.clear();
        
        // Update table name
        document.getElementById('current-table-name').innerHTML = 
            `<i class="fas fa-table me-2"></i>${tableName}`;
        
        this.loadTableData(tableName, 1);
    }
    
    async loadTableData(tableName, page = 1) {
        try {
            this.showLoading(true);
            
            const response = await fetch(`/api/table/${tableName}?page=${page}&per_page=100`);
            const data = await response.json();
            
            if (data.error) {
                this.showError(data.error);
                return;
            }
            
            this.tableData = data;
            this.renderTable(data);
            this.renderPagination(data);
            this.updateTableInfo(data);
            
        } catch (error) {
            this.showError(`Failed to load table data: ${error.message}`);
        } finally {
            this.showLoading(false);
        }
    }
    
    renderTable(data) {
        const table = document.getElementById('data-table');
        const thead = table.querySelector('thead');
        const tbody = table.querySelector('tbody');
        
        // Clear existing content
        thead.innerHTML = '';
        tbody.innerHTML = '';
        
        // Create header row
        const headerRow = document.createElement('tr');
        
        // Add checkbox column
        const checkboxHeader = document.createElement('th');
        checkboxHeader.innerHTML = '<input type="checkbox" id="select-all">';
        checkboxHeader.style.width = '50px';
        headerRow.appendChild(checkboxHeader);
        
        // Add data columns
        data.columns.forEach((column, index) => {
            const th = document.createElement('th');
            th.textContent = column;
            th.classList.add('sortable');
            th.dataset.column = column;
            th.dataset.index = index;
            th.addEventListener('click', () => this.sortTable(column, index));
            headerRow.appendChild(th);
        });
        
        thead.appendChild(headerRow);
        
        // Create data rows
        data.rows.forEach((row, rowIndex) => {
            const tr = document.createElement('tr');
            tr.dataset.rowId = rowIndex + ((data.page - 1) * data.per_page);
            
            // Add checkbox cell
            const checkboxCell = document.createElement('td');
            checkboxCell.innerHTML = `<input type="checkbox" class="row-checkbox" value="${tr.dataset.rowId}">`;
            tr.appendChild(checkboxCell);
            
            // Add data cells
            row.forEach((cellValue, cellIndex) => {
                const td = document.createElement('td');
                td.textContent = cellValue || '';
                td.classList.add('editable-cell');
                td.dataset.column = data.columns[cellIndex];
                td.dataset.originalValue = cellValue || '';
                td.addEventListener('click', () => this.editCell(td));
                tr.appendChild(td);
            });
            
            tbody.appendChild(tr);
        });
        
        // Add event listeners for checkboxes
        this.initializeCheckboxes();
    }
    
    initializeCheckboxes() {
        // Select all checkbox
        const selectAllCheckbox = document.getElementById('select-all');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', (e) => {
                const rowCheckboxes = document.querySelectorAll('.row-checkbox');
                rowCheckboxes.forEach(checkbox => {
                    checkbox.checked = e.target.checked;
                    if (e.target.checked) {
                        this.selectedRows.add(checkbox.value);
                    } else {
                        this.selectedRows.delete(checkbox.value);
                    }
                });
                this.updateDeleteButton();
            });
        }
        
        // Individual row checkboxes
        document.querySelectorAll('.row-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                if (e.target.checked) {
                    this.selectedRows.add(e.target.value);
                } else {
                    this.selectedRows.delete(e.target.value);
                }
                this.updateDeleteButton();
            });
        });
    }
    
    updateDeleteButton() {
        const deleteBtn = document.getElementById('delete-selected-btn');
        if (deleteBtn) {
            deleteBtn.disabled = this.selectedRows.size === 0;
        }
    }
    
    editCell(cell) {
        if (cell.classList.contains('editing')) return;
        
        const originalValue = cell.dataset.originalValue;
        cell.classList.add('editing');
        
        const input = document.createElement('input');
        input.type = 'text';
        input.value = originalValue;
        input.classList.add('cell-input');
        
        cell.innerHTML = '';
        cell.appendChild(input);
        input.focus();
        input.select();
        
        const saveEdit = async () => {
            const newValue = input.value;
            cell.classList.remove('editing');
            
            if (newValue !== originalValue) {
                try {
                    await this.updateCell(cell, newValue);
                    cell.textContent = newValue;
                    cell.dataset.originalValue = newValue;
                    cell.classList.add('success-flash');
                    setTimeout(() => cell.classList.remove('success-flash'), 600);
                } catch (error) {
                    cell.textContent = originalValue;
                    this.showError(`Failed to update cell: ${error.message}`);
                }
            } else {
                cell.textContent = originalValue;
            }
        };
        
        const cancelEdit = () => {
            cell.classList.remove('editing');
            cell.textContent = originalValue;
        };
        
        input.addEventListener('blur', saveEdit);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                saveEdit();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                cancelEdit();
            }
        });
    }
    
    async updateCell(cell, newValue) {
        const row = cell.closest('tr');
        const rowId = row.dataset.rowId;
        const column = cell.dataset.column;
        
        const response = await fetch(`/api/table/${this.currentTable}/update`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                row_id: parseInt(rowId) + 1, // Convert to 1-based ROWID
                column: column,
                value: newValue
            })
        });
        
        const result = await response.json();
        if (result.error) {
            throw new Error(result.error);
        }
    }
    
    sortTable(column, columnIndex) {
        // Toggle sort direction
        if (this.sortColumn === columnIndex) {
            this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortColumn = columnIndex;
            this.sortDirection = 'asc';
        }
        
        // Update header styling
        document.querySelectorAll('.sortable').forEach(th => {
            th.classList.remove('asc', 'desc');
        });
        document.querySelector(`[data-index="${columnIndex}"]`)
            .classList.add(this.sortDirection);
        
        // Sort table rows
        const tbody = document.querySelector('#data-table tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        
        rows.sort((a, b) => {
            const aValue = a.children[columnIndex + 1].textContent.trim();
            const bValue = b.children[columnIndex + 1].textContent.trim();
            
            // Try to parse as numbers
            const aNum = parseFloat(aValue);
            const bNum = parseFloat(bValue);
            
            let comparison;
            if (!isNaN(aNum) && !isNaN(bNum)) {
                comparison = aNum - bNum;
            } else {
                comparison = aValue.localeCompare(bValue);
            }
            
            return this.sortDirection === 'asc' ? comparison : -comparison;
        });
        
        // Re-append sorted rows
        rows.forEach(row => tbody.appendChild(row));
    }
    
    showAddRowModal() {
        if (!this.tableData) return;
        
        const modal = document.getElementById('addRowModal');
        const formFields = document.getElementById('form-fields');
        
        // Clear existing fields
        formFields.innerHTML = '';
        
        // Create form fields for each column
        this.tableData.columns.forEach(column => {
            const fieldGroup = document.createElement('div');
            fieldGroup.classList.add('mb-3');
            
            const label = document.createElement('label');
            label.classList.add('form-label');
            label.textContent = column;
            label.setAttribute('for', `field-${column}`);
            
            const input = document.createElement('input');
            input.type = 'text';
            input.classList.add('form-control');
            input.id = `field-${column}`;
            input.name = column;
            
            fieldGroup.appendChild(label);
            fieldGroup.appendChild(input);
            formFields.appendChild(fieldGroup);
        });
        
        // Show modal
        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
    }
    
    async saveNewRow() {
        const form = document.getElementById('add-row-form');
        const formData = new FormData(form);
        
        const columns = [];
        const values = [];
        
        for (const [key, value] of formData.entries()) {
            columns.push(key);
            values.push(value);
        }
        
        try {
            const response = await fetch(`/api/table/${this.currentTable}/add`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    columns: columns,
                    values: values
                })
            });
            
            const result = await response.json();
            if (result.error) {
                throw new Error(result.error);
            }
            
            // Close modal and refresh table
            const modal = bootstrap.Modal.getInstance(document.getElementById('addRowModal'));
            modal.hide();
            
            this.loadTableData(this.currentTable, this.currentPage);
            this.showSuccess('Row added successfully');
            
        } catch (error) {
            this.showError(`Failed to add row: ${error.message}`);
        }
    }
    
    async deleteSelectedRows() {
        if (this.selectedRows.size === 0) return;
        
        if (!confirm(`Are you sure you want to delete ${this.selectedRows.size} row(s)?`)) {
            return;
        }
        
        try {
            const rowIds = Array.from(this.selectedRows).map(id => parseInt(id) + 1); // Convert to 1-based
            
            const response = await fetch(`/api/table/${this.currentTable}/delete`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    row_ids: rowIds
                })
            });
            
            const result = await response.json();
            if (result.error) {
                throw new Error(result.error);
            }
            
            this.selectedRows.clear();
            this.loadTableData(this.currentTable, this.currentPage);
            this.showSuccess('Rows deleted successfully');
            
        } catch (error) {
            this.showError(`Failed to delete rows: ${error.message}`);
        }
    }
    
    renderPagination(data) {
        const container = document.getElementById('pagination-container');
        const pagination = document.getElementById('pagination');
        
        if (data.total_pages <= 1) {
            container.style.display = 'none';
            return;
        }
        
        container.style.display = 'block';
        pagination.innerHTML = '';
        
        // Previous button
        const prevLi = document.createElement('li');
        prevLi.classList.add('page-item');
        if (data.page === 1) prevLi.classList.add('disabled');
        
        const prevA = document.createElement('a');
        prevA.classList.add('page-link');
        prevA.href = '#';
        prevA.textContent = 'Previous';
        prevA.addEventListener('click', (e) => {
            e.preventDefault();
            if (data.page > 1) {
                this.loadTableData(this.currentTable, data.page - 1);
            }
        });
        
        prevLi.appendChild(prevA);
        pagination.appendChild(prevLi);
        
        // Page numbers
        const maxVisible = 5;
        let startPage = Math.max(1, data.page - Math.floor(maxVisible / 2));
        let endPage = Math.min(data.total_pages, startPage + maxVisible - 1);
        
        if (endPage - startPage + 1 < maxVisible) {
            startPage = Math.max(1, endPage - maxVisible + 1);
        }
        
        for (let i = startPage; i <= endPage; i++) {
            const li = document.createElement('li');
            li.classList.add('page-item');
            if (i === data.page) li.classList.add('active');
            
            const a = document.createElement('a');
            a.classList.add('page-link');
            a.href = '#';
            a.textContent = i;
            a.addEventListener('click', (e) => {
                e.preventDefault();
                this.loadTableData(this.currentTable, i);
            });
            
            li.appendChild(a);
            pagination.appendChild(li);
        }
        
        // Next button
        const nextLi = document.createElement('li');
        nextLi.classList.add('page-item');
        if (data.page === data.total_pages) nextLi.classList.add('disabled');
        
        const nextA = document.createElement('a');
        nextA.classList.add('page-link');
        nextA.href = '#';
        nextA.textContent = 'Next';
        nextA.addEventListener('click', (e) => {
            e.preventDefault();
            if (data.page < data.total_pages) {
                this.loadTableData(this.currentTable, data.page + 1);
            }
        });
        
        nextLi.appendChild(nextA);
        pagination.appendChild(nextLi);
    }
    
    updateTableInfo(data) {
        const info = document.getElementById('table-info');
        const start = (data.page - 1) * data.per_page + 1;
        const end = Math.min(data.page * data.per_page, data.total_count);
        
        info.textContent = `Showing ${start}-${end} of ${data.total_count} rows (Page ${data.page} of ${data.total_pages})`;
    }
    
    showLoading(show) {
        const loading = document.getElementById('loading');
        const tableContainer = document.getElementById('table-container');
        
        if (show) {
            loading.style.display = 'block';
            tableContainer.style.opacity = '0.5';
        } else {
            loading.style.display = 'none';
            tableContainer.style.opacity = '1';
        }
    }
    
    showError(message) {
        this.showAlert(message, 'danger');
    }
    
    showSuccess(message) {
        this.showAlert(message, 'success');
    }
    
    showAlert(message, type) {
        // Create alert element
        const alert = document.createElement('div');
        alert.classList.add('alert', `alert-${type}`, 'alert-dismissible', 'fade', 'show');
        alert.innerHTML = `
            <i class="fas fa-${type === 'danger' ? 'exclamation-triangle' : 'check-circle'} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        // Insert at top of main content
        const mainContent = document.querySelector('.main-content .p-3');
        mainContent.insertBefore(alert, mainContent.firstChild);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (alert.parentNode) {
                alert.remove();
            }
        }, 5000);
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new DatabaseExplorer();
});
