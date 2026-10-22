# Row Number in Tree/List View

## Overview

This Odoo module automatically adds a row number column (#) at the start of all
tree/list views across different Odoo modules. It improves data readability by allowing
users to quickly identify and reference records in large datasets.

The module is lightweight, seamless, and works with both Odoo Community and Enterprise
editions.

## Key Features

- Row Number Column (#) – Displays a numbering column at the beginning of list views.
- Universal Support – Works across multiple Odoo modules, including:
  - Sales
  - Purchase
  - Inventory & Stock Moves
  - Manufacturing
  - Accounting
  - Project & Tasks
  - Website
  - Documents
  - Quality Control (QC)
- Dynamic Counter – Row numbers update as you scroll, group, filter, or paginate
  records.
- Header & Footer Alignment – Adds a header "#" column and footer placeholder for
  perfect alignment.
- Sequence-Aware – Detects existing "sequence" fields and adjusts column widths
  accordingly.
- Non-Intrusive – Uses XML & JavaScript patching without altering business logic.
- Compatible with grouped, filtered, and multi-page list views.

## Example Use Cases

- Sales Orders → Identify order line sequence numbers quickly.
- Inventory → Track stock moves with clear line numbering.
- Accounting → Review invoice lines with reference numbers.
- Project → Manage task lists with row visibility.
- Documents → Quickly reference files by row number.

## Installation

1. Copy the module folder `rowno_in_tree` into your Odoo addons directory.
2. Restart your Odoo server.
3. Activate Developer Mode.
4. Go to Apps > Update Apps List.
5. Search for "Row Number in Tree/List View" and install it.

## Technical Details

- Depends on: `web`, `stock`, `documents`
- Assets Injected:
  - `list_render.xml` (XML template for row numbers)
  - `list_renderer.esm.js` (JS patch to inject header/footer)
  - `custom_styles.css` (styling for row number column)

## About

- Author: Synodica Solutions Pvt. Ltd.
- Website: https://synodica.com
- Support: support@synodica.com
- License: LGPL-3

## Tags

Odoo Row Number, Tree/List View Enhancement, Row Counter, List Renderer Patch, Sales,
Purchase, Inventory, Accounting, Project, Documents, QC, Manufacturing
