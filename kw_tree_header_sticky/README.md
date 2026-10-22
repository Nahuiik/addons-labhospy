# Tree Header Sticky

[![License: LGPL-3](https://img.shields.io/badge/license-LGPL--3-blue.png)](http://www.gnu.org/licenses/lgpl-3.0-standalone.html)
[![Maintainer: Kitworks](https://img.shields.io/badge/maintainer-Kitworks-purple.png)](https://kitworks.systems/)
[![Docs: Tree_Header_Sticky](https://img.shields.io/badge/docs-Tree_Header_Sticky-yellowgreen.png)](https://kitworks.systems/)

This module keeps list view headers visible while scrolling vertically through long tables, improving navigation and data comprehension in large datasets.

## Features

- **Fixed Table Headers**: Column headers remain visible during vertical scrolling
- **Enhanced Navigation**: Users always see column names and can sort/filter without scrolling back to top
- **Better Data Context**: Column headers provide context for data being viewed
- **Seamless Integration**: Works with all existing list views without configuration
- **Performance Optimized**: Lightweight CSS-only implementation

## How It Works

The module applies CSS sticky positioning to table headers:

- **Position Sticky**: Uses `position: sticky` with `top: 0px` to fix headers at the top
- **Z-index Priority**: Ensures headers stay above table content during scroll
- **Automatic Application**: Applied to all responsive tables in the web client
- **Cross-view Compatibility**: Works with all list/tree views regardless of model

## Visual Behavior

### Scrolling Experience
- Headers stick to the top of the viewport when scrolling down
- Column names remain visible at all times
- Sorting and filtering controls stay accessible
- Headers scroll away naturally when scrolling back to top

### Layout Preservation
- No layout shifts or content jumps
- Original table styling maintained
- Responsive design compatibility preserved
- Mobile and tablet friendly

## Installation

1. Install the module through the Odoo Apps menu
2. No configuration required - works automatically
3. Refresh your browser to see the sticky headers in action

## Usage

Once installed, the module enhances all list views automatically:

1. Navigate to any list view with many records (e.g., Sales Orders, Customers, Products)
2. Scroll down through the list
3. Notice that column headers remain visible at the top
4. Use sorting, filtering, and selection without scrolling back to top
5. Headers maintain their functionality while being fixed

## Technical Implementation

### CSS Rule Applied

```css
html .o_web_client .o_content .table-responsive thead {
    position: sticky !important;
    top: 0px !important;
    z-index: 3 !important;
}
```

This simple but effective CSS rule:
- Targets all table headers in responsive tables
- Uses high specificity to override existing styles
- Sets appropriate z-index to ensure visibility
- Maintains compatibility with Odoo's existing CSS framework

## Use Cases

- **Large Datasets**: Customer lists, product catalogs, financial records
- **Data Analysis**: Comparing values while keeping column context visible
- **Bulk Operations**: Selecting records while seeing column headers
- **Reporting Views**: Financial reports, analytics dashboards
- **Administrative Tasks**: User management, configuration lists

## Benefits

### User Experience
- **Faster Navigation**: No need to scroll back to see column names
- **Better Context**: Always know what data you're looking at
- **Improved Productivity**: Faster sorting and filtering operations
- **Reduced Errors**: Clear column identification prevents data confusion

### Developer Benefits
- **Zero Configuration**: Works automatically after installation
- **No Code Changes**: Existing customizations remain unaffected
- **Framework Agnostic**: Compatible with custom list view implementations
- **Maintenance Free**: No ongoing configuration or updates required

## Browser Support

- **Chrome**: Full support with smooth scrolling
- **Firefox**: Full support with stable positioning
- **Safari**: Full support with native sticky behavior
- **Edge**: Full support with optimized performance
- **Mobile Browsers**: Responsive sticky behavior maintained

## Compatibility

- **Odoo Version**: 18.0
- **Module Version**: 18.0.0.1.2
- **Category**: Extra Tools
- **License**: LGPL-3
- **Dependencies**: `web` module only

## Performance Impact

- **Minimal Overhead**: Pure CSS implementation with no JavaScript
- **Fast Rendering**: No additional DOM manipulation or event handlers
- **Memory Efficient**: No additional memory usage or data structures
- **Responsive**: Maintains smooth scrolling performance

## Related Modules

- **kw_tree_checkbox_sticky**: Keeps checkbox column fixed during horizontal scrolling
- Together these modules provide comprehensive table navigation enhancement

## Troubleshooting

### Headers Not Sticking
- Clear browser cache and refresh the page
- Ensure the module is properly installed and activated
- Check for conflicting CSS from other modules

### Performance Issues
- The module uses only CSS and should not impact performance
- If experiencing issues, check for browser-specific compatibility

## Bug Tracker

Bugs are tracked on [Kitworks Support](https://kitworks.systems/requests).
In case of trouble, please check there if your issue has already been reported.

## Maintainer

This module is maintained by [Kitworks Systems](https://kitworks.systems).

We can provide you further Odoo Support, Odoo implementation, Odoo customization, Odoo 3rd Party development and integration software, consulting services. Our main goal is to provide the best quality product for you.

For any questions [contact us](mailto:support@kitworks.systems).
