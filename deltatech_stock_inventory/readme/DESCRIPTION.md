# Deltatech Stock Inventory

## Overview

The Deltatech Stock Inventory module restores and enhances the stock.inventory functionality in Odoo, providing
additional features for better inventory management and stock valuation control.

## Features

- **Legacy Inventory System**: Restores the functionality of the old stock.inventory model, which was removed in newer
  Odoo versions
- **Enhanced Stock Valuation**:
  - Displays stock price columns in inventory views
  - Allows updating product cost prices during inventory validation
- **Security Controls**:
  - Adds "Can update quantities" security group to restrict who can modify inventory quantities
- **Inventory Price Update**:
  - When system parameter "stock.use_inventory_price" is set to True, the cost price of products (with FIFO evaluation)
    is updated with the price from inventory lines
  - This ensures stock valuation generated from inventory uses the specified unit price
- **Inventory Archiving**:
  - Option to archive old stock valuation layers (SVLs) and create new ones based on inventory counts
  - Supports compatibility with Romanian accounting modules (l10n_ro)
- **Barcode Support**:
  - Integrated barcode scanning functionality for faster inventory operations
  - Supports scanning products and lot/serial numbers
- **Enhanced Reporting**:
  - Built-in inventory reports
  - Detailed views of inventory adjustments
- **Stock Accounting Bridge**:
  - **Inventory Valuation Report**: Provides a comprehensive view of stock valuation at any given date, showing initial balance, stock variation, and ending stock
  - **Accounting Integration**: Bridge between stock and accounting modules, similar to Odoo Enterprise functionality
  - **Generate Accounting Entries**: Automatically create journal entries from stock valuation reports with proper debit/credit lines
  - **Flexible Configuration**: Configure default journal and accounts at company level for automatic entry generation
  - **Account Grouping**: View stock valuation grouped by accounting accounts for better financial analysis
  - Accessible from Inventory > Reporting > Inventory Valuation menu
- **Inventory Management Features**:
  - Filtering by location, rack, or product
  - Marking inventory lines as "OK" for verification
  - Creating new inventories from unverified lines
  - Prefill counted quantities with current stock or zero
  - Include exhausted products (with zero quantity)

## Configuration

- Set system parameter "stock.use_inventory_price" to True to enable cost price updates during inventory
- The "Can update quantities" security group must be assigned to users who need to update inventory quantities
- **Stock Accounting Bridge Configuration** (optional):
  - Go to Settings > Companies > [Your Company] > Accounting tab
  - Configure the following fields for automatic defaults:
    * **Inventory Bridge Journal**: Default journal for generating valuation entries
    * **Inventory Variation Account**: Expense account for stock variations
    * **Inventory Valuation Account**: Balance sheet account for stock valuation
  - If not configured, the system will attempt to auto-detect appropriate accounts from product categories or company defaults

## Technical Details

The module implements:

- Complete reimplementation of the stock.inventory model
- Integration with stock valuation layers for proper accounting
- Custom views for enhanced inventory operations
- Barcode scanning capabilities for mobile inventory
- Compatibility with the Romanian accounting module when installed
- Stock Accounting Bridge with valuation reporting and automatic journal entry generation
- Date-based stock valuation calculations using stock.valuation.layer
- Account grouping and financial reporting integration

## Usage

**Inventory Management:**

1. Create a new inventory from Inventory menu
2. Configure inventory parameters (locations, products, etc.)
3. Start the inventory to generate lines based on current stock
4. Count products and update quantities
5. Use the "Check" function to verify inventory
6. Validate inventory to create stock moves and update valuation
7. Optionally use barcode scanning for faster operations

**Stock Accounting Bridge:**

1. Navigate to Inventory > Reporting > Inventory Valuation
2. Select the date for which you want to view the stock valuation
3. Review the report showing:
   - **Initial Balance**: Stock value before the selected date
   - **Stock Variation**: Change in stock value during the period
   - **Ending Stock**: Total stock value as of the selected date
   - **Account Details**: Breakdown by accounting accounts
4. Click "Generate Entry" button to create accounting journal entries:
   - Select or verify the journal and accounts
   - Review the debit/credit lines that will be created
   - Confirm to generate and post the accounting entry
5. The generated entry will be automatically posted and can be viewed in the Accounting module
