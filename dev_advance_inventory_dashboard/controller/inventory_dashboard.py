# -*- coding: utf-8 -*-
##############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Mruthul Raj @cybrosys(odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
# import datetime
from odoo import http
from odoo.http import request
from odoo import models, fields, api, _
from operator import itemgetter
import itertools
import operator
from datetime import date,datetime,timedelta
# from datetime import datetime
from itertools import groupby
import base64


class InventoryFilter(http.Controller):
    """The InventoryFilter class provides the filter option to the js.
    When applying the filter returns the corresponding data."""

    @http.route('/all_inventory_filter', auth='user', type='http', csrf=False)
    def all_inventory_filter(self):
        
        product_list = []
        warehouse_list = []
        
        product_ids = request.env['product.product'].search([])
        warehouse_ids = request.env['stock.warehouse'].search([])
       
        for product_id in product_ids:
            dic = {'name': product_id.name,
                   'id': product_id.id}
            product_list.append(dic)
        for warehouse_id in warehouse_ids:
            dic = {'name': warehouse_id.name,
                   'id': warehouse_id.id}
            warehouse_list.append(dic)
          
        return request.make_json_response([product_list,warehouse_list])

    @http.route('/get/inventory/tiles/data', auth='user', type='http', methods=['POST'], csrf=False)
    def get_inventory_tiles_data(self, **kwargs):
        try:
            kwargs = request.get_json_data()
        except ValueError:
            pass # Fallback to kwargs if no JSON body

        
        today = date.today()
        order_ship_domain = []
        due_domain = []
        total_quantity_domain = []
        
        if not kwargs.get('duration'):
            order_ship_domain = [('scheduled_date', '>=', today),('scheduled_date', '<=', today)]
            due_domain = [('scheduled_date', '<=', today)]
            total_quantity_domain = [('create_date', '>=', today),('create_date', '<=', today)]
            
        if kwargs:
            if kwargs['product_id']:
                if kwargs['product_id'] != 'all':
                    product_id = int(kwargs['product_id'])
                    order_ship_domain += [('move_line_ids.product_id','=',product_id)]
                    due_domain += [('move_line_ids.product_id','=',product_id)]
                    total_quantity_domain += [('id','=',product_id)]
                    
                    
            if kwargs['warehouse_id']:
                if kwargs['warehouse_id'] != 'all':
                    warehouse_id = int(kwargs['warehouse_id'])
                    order_ship_domain += [('company_id','=',warehouse_id)]
                    due_domain += [('company_id','=',warehouse_id)]
                    total_quantity_domain += [('company_id','=',warehouse_id)]
                    
                    
            if kwargs['duration']:
                duration = kwargs['duration']
                if duration != "all":
                    duration = int(duration)
                    filter_date = today  - timedelta(days=duration)
                    order_ship_domain += [('scheduled_date', '>=', filter_date), ('scheduled_date', '<=', today)]
                    due_domain += [('scheduled_date', '>=', filter_date), ('scheduled_date', '<=', today)]
                    total_quantity_domain += [('create_date', '>=', filter_date), ('create_date', '<=', today)]
                    
                    
        order_ship_data = request.env['stock.picking'].search([('state','=','assigned'),('picking_type_code', '=', 'incoming')]+ order_ship_domain)
        order_due_shipment_data = request.env['stock.picking'].search([('picking_type_code', '=', 'incoming'),('state','not in',['assigned','done'])]+ due_domain)
        open_po_data = request.env['stock.picking'].search([('state','=','assigned'),('picking_type_code', '=', 'outgoing')]+ order_ship_domain)
        pending_shipment_data = request.env['stock.picking'].search([('scheduled_date', '<', today),('picking_type_code', '=', 'outgoing'),('state','not in',['assigned','done'])]+ due_domain)
        totalqty_inhand_data = request.env['product.product'].search([('qty_available', '>', 0)] + total_quantity_domain)
        total_quantity = 0
        for quant in totalqty_inhand_data:
            total_quantity += quant.qty_available

        received_quantity_data = request.env['stock.move'].search([('state', '=', 'done'),('origin','!=',False)] + total_quantity_domain)
        total_received = sum(move.quantity for move in received_quantity_data)
        out_stock_product_data = request.env['product.product'].search([('qty_available', '<=', 0)] + total_quantity_domain)
        total_product_data = request.env['product.product'].search(total_quantity_domain)
        user_name = request.env.user.name
        user_img = request.env.user.image_1920
        if isinstance(user_img, bytes):
            # Odoo fields are already base64 encoded, so we just decode bytes to string
            user_img = user_img.decode('utf-8')

        return request.make_json_response({
            'order_ship_data': order_ship_data.ids,
            'order_due_shipment_data': order_due_shipment_data.ids,
            'open_po_data': open_po_data.ids,
            'pending_shipment_data': pending_shipment_data.ids,
            'quantity_inhand_data': total_quantity,
            'total_quantity_data_ids':totalqty_inhand_data.ids,
            'received_quantity_data': received_quantity_data.ids,
            'total_received': total_received,
            'out_stock_product_data': out_stock_product_data.ids,
            'total_product_data': total_product_data.ids,
            'user_img': user_img,
            'user_name': user_name
        })

    # ======1111 Top Moving Product 1111===================
    @http.route('/moving/product/chart/data', auth='user', type='http', methods=['POST'], csrf=False)
    def get_moving_product_chart_data(self, **kw):
        try:
            kw = request.get_json_data()
        except ValueError:
            pass
        all_color_list = ['rgba(136, 67, 149, 0.4)','rgba(217, 254, 67, 0.7)','rgba(140, 120, 5, 0.5)','rgba(240, 128, 128, 0.5)',
                           'rgba(139, 134, 243, 0.5)','rgba(241, 181, 31, 0.8)','rgba(14, 144, 148, 0.4)','rgba(254, 94, 178, 0.5)',
                           'rgba(95, 247, 252 , 0.5)','rgba(255, 99, 71, 0.4','rgba(148, 39, 14, 0.4)','rgba(149, 156, 158, 0.4)',
                           'rgba(69, 80, 82, 0.4)','rgba(224, 5, 52, 0.4)','rgba(90, 120, 232, 0.4)','rgba(189, 90, 232, 0.4)',
                           'rgba(240, 128, 128, 0.3)','rgba(241, 181, 31, 0.7)', 'rgba(136, 67, 149, 0.3)','rgba(240, 128, 128, 0.2)']     
    
        today = datetime.today().date()
        data = kw['data']
        top_moving_product_count = data['top_moving_product_count']
        stock_move_domain = []
        
        if not data.get('duration'):
            stock_move_domain = [('date', '>=', today),('date', '<=', today)]
        if data:
            if data['product_id']:
                if data['product_id'] != 'all':
                    product_id = int(data['product_id'])
                    stock_move_domain += [('product_id','=',product_id)]
                    
            if data['warehouse_id']:
                if data['warehouse_id'] != 'all':
                    warehouse_id = int(data['warehouse_id'])
                    stock_move_domain += [('company_id','=',warehouse_id)]
            if data['duration']:
                duration = data['duration']
                if duration != "all":
                    duration = int(duration)
                    filter_date = today  - timedelta(days=duration)
                    stock_move_domain += [('date', '>=', filter_date), ('date', '<=', today)]
    
        top_repeated_product = []
        top_repeated_product_chart = []
        top_repeated_product_repeat_time = []

        # Fetch the stock.move.line records where state is done
        top_moving_product_data = request.env['stock.move.line'].search_read([('state', '=', 'done')] + stock_move_domain, fields=['product_id', 'quantity'] )

        n_lines = sorted(top_moving_product_data, key=itemgetter('product_id'))
        groups = itertools.groupby(n_lines, key=operator.itemgetter('product_id'))
        lines = [{'product_id': k, 'values': [x for x in v]} for k, v in groups]

        order_ids_lst = []
        for x in lines:
            order_id_lst = []
            for id in x['values']:
                order_id_lst.append(id['id'])
            order_ids_lst.append(order_id_lst)
        order_ids_lst = sorted(order_ids_lst, key=lambda x: len(x), reverse=True)

        for line in lines:
            product_id = line.get('product_id')
            product_name = product_id[1]  # product_id[1] should give you the display name (with reference code)

            product = request.env['product.product'].browse(product_id[0])  # Get the product record using the ID
            product_name = product.name  # Get the product name (without reference)

            top_repeated_product.append(
                {'product_name': product_name, 'qty': line.get('product_id')[1], 'repeated_time': len(line.get('values'))}
            )

        # Sorting by repeated_time (in descending order)
        top_repeated_product = sorted(top_repeated_product, key=lambda i: i['repeated_time'], reverse=True)[:int(top_moving_product_count)]

        for rep_customer_data in top_repeated_product:
            top_repeated_product_chart.append(rep_customer_data.get('product_name'))  # Now using product_name
            top_repeated_product_repeat_time.append(rep_customer_data.get('repeated_time'))

        # Prepare the chart data
        top_moving_chart_data = {
            'labels': top_repeated_product_chart,
            'datasets': [{
                'label': "Moving Product",
                'backgroundColor': all_color_list[:len(top_repeated_product_chart)],
                'data': top_repeated_product_repeat_time,
                'detail': order_ids_lst
            }]
        }

        return request.make_json_response({
            'top_moving_chart_data': top_moving_chart_data
        })
        
   
    # ======222 Product Moving By Location 222===================
    
    @http.route('/moving/location/chart/data', auth='user', type='http', methods=['POST'], csrf=False)
    def get_moving_location_chart_data(self, **kw):
        try:
            kw = request.get_json_data()
        except ValueError:
            pass
        
        today = date.today()
        data = kw['data']
        move_location_domain = []

        if not data.get('duration'):
            move_location_domain = [('create_date', '>=', today),('create_date', '<=', today)]
                       
        if data:
            if data['product_id']:
                if data['product_id'] != 'all':
                    product_id = int(data['product_id'])
                    move_location_domain += [('product_id','=',product_id)]
                    
            if data['warehouse_id']:
                if data['warehouse_id'] != 'all':
                    warehouse_id = int(data['warehouse_id'])
                    move_location_domain += [('company_id','=',warehouse_id)]
            if data['duration']:
                duration = data['duration']
                if duration != "all":
                    duration = int(duration)
                    filter_date = today  - timedelta(days=duration)
                    move_location_domain += [('create_date', '>=', filter_date), ('create_date', '<=', today)]
        
        stock_quants = request.env['stock.quant'].search([("location_id.usage", "=", "internal")] + move_location_domain)

        location_data = {}
        for quant in stock_quants:
            location = quant.location_id.display_name  
            if location not in location_data:
                location_data[location] = {
                    'available': 0, 
                    'reserved': 0, 
                    'available_detail': [],  # Store record ids for available stock
                    'reserved_detail': []    # Store record ids for reserved stock
                }

            if quant.available_quantity > 0:  # Available stock
                location_data[location]['available'] += quant.available_quantity
                location_data[location]['available_detail'].append(quant.id)  # Store record id for available stock
            
            if quant.reserved_quantity > 0:  # Reserved stock
                location_data[location]['reserved'] += quant.reserved_quantity
                location_data[location]['reserved_detail'].append(quant.id)  # Store record id for reserved stock

        # Filter out locations with zero available stock
        location_data = {location: data for location, data in location_data.items() if data['available'] > 0}

        # Prepare data for the chart
        labels = list(location_data.keys())
        available_quantities = [data['available'] for data in location_data.values()]
        reserved_quantities = [data['reserved'] for data in location_data.values()]

        # Construct the chart data dictionary
        stock_moving_location_chart_data = {
            'labels': labels,
            'datasets': [
                {
                    'label': 'Available Quantity',
                    'backgroundColor': 'rgba(54, 162, 235, 0.5)',  # Blue with transparency
                    'borderColor': 'rgba(54, 162, 235, 1)',  # Solid blue border
                    'borderWidth': 1,
                    'data': available_quantities,
                    'detail': [data['available_detail'] for data in location_data.values()]  # Include detail
                },
                {
                    'label': 'Reserved Quantity',
                    'backgroundColor': 'rgba(255, 99, 132, 0.5)',  # Red with transparency
                    'borderColor': 'rgba(255, 99, 132, 1)',  # Solid red border
                    'borderWidth': 1,
                    'data': reserved_quantities,
                    'detail': [data['reserved_detail'] for data in location_data.values()]  # Include detail
                },
            ],
        }

        return request.make_json_response({
            'stock_moving_location_chart_data': stock_moving_location_chart_data
        })

      
    # ======333 Receipt chart 333===================
    
    @http.route('/receipt/chart/data', auth='user', type='http', methods=['POST'], csrf=False)
    def get_receipt_chart_data(self, **kw):
        try:
            kw = request.get_json_data()
        except ValueError:
            pass
        all_color_lists = ['rgba(240, 128, 128, 0.5)','rgba(241, 181, 31, 0.7)', 'rgba(136, 67, 149, 0.3)',
                        'rgba(240, 128, 128, 0.2)', 'rgba(255, 99, 71, 0.3)']

        today = date.today()
        data = kw['data']
        receipt_domain = []
        td_domain = []

        
        if not data.get('duration'):
            receipt_domain = [('scheduled_date', '>=', today),('scheduled_date', '<=', today)]
            td_domain = [('scheduled_date', '>=', today),('scheduled_date', '<=', today)]
        if data:
            if data['product_id']:
                if data['product_id'] != 'all':
                    product_id = int(data['product_id'])
                    receipt_domain += [('move_line_ids.product_id','=',product_id)]
                    td_domain += [('move_line_ids.product_id','=',product_id)]
            if data['warehouse_id']:
                if data['warehouse_id'] != 'all':
                    warehouse_id = int(data['warehouse_id'])
                    receipt_domain += [('company_id','=',warehouse_id)]
                    td_domain += [('company_id','=',warehouse_id)]
            if data['duration']:
                duration = data['duration']
                if duration != "all":
                    duration = int(duration)
                    filter_date = today  - timedelta(days=duration)
                    receipt_domain += [('scheduled_date', '>=', filter_date), ('scheduled_date', '<=', today)]
                    td_domain += [('scheduled_date', '>=', today),('scheduled_date', '<=', today)]
                if duration == '0':
                    td_domain += [('scheduled_date', '>=', today),('scheduled_date', '<=', today)]
                if duration == 'all':
                    td_domain += [('scheduled_date', '>=', today),('scheduled_date', '<=', today)]
       
        # Fetch counts based on the scheduled date
        due_in_count = request.env['stock.picking'].search([('scheduled_date', '<', today), ('picking_type_code', '=', 'incoming')] + receipt_domain)
        today_in_count = request.env['stock.picking'].search([('picking_type_code', '=', 'incoming')] + td_domain)
        future_in_count = request.env['stock.picking'].search([('scheduled_date', '>', today), ('picking_type_code', '=', 'incoming')] +receipt_domain)

        # Prepare chart data dynamically based on the availability of records
        labels = []
        dataset_data = []
        details = []
        background_colors = []

        if len(due_in_count) > 0:
            labels.append('Overdue')
            dataset_data.append(len(due_in_count))
            details.append(due_in_count.ids)
            background_colors.append(all_color_lists[0])

        if len(today_in_count) > 0:
            labels.append('Today')
            dataset_data.append(len(today_in_count))
            details.append(today_in_count.ids)
            background_colors.append(all_color_lists[1])

        if len(future_in_count) > 0:
            labels.append('Upcoming')
            dataset_data.append(len(future_in_count))
            details.append(future_in_count.ids)
            background_colors.append(all_color_lists[2])

        # Build the chart data object
        receipts_chart_data = {
            'labels': labels,
            'datasets': [{
                'label': 'Receipts',
                'backgroundColor': background_colors,
                'data': dataset_data,
                'detail': details,
            }]
        }

        return request.make_json_response({
            'receipts_chart_data': receipts_chart_data,
        })


    # ======4444 Delivery chart 4444===================
    @http.route('/delivery/chart/data', auth='user', type='http', methods=['POST'], csrf=False)
    def get_delivery_chart_data(self, **kw):
        try:
            kw = request.get_json_data()
        except ValueError:
            pass
        
        all_color_lists = ['rgba(240, 128, 128, 0.5)','rgba(241, 181, 31, 0.7)', 'rgba(136, 67, 149, 0.3)',
                        'rgba(240, 128, 128, 0.2)', 'rgba(255, 99, 71, 0.3)']

        today = date.today()
        data = kw['data']
        delivery_domain = []
        td_domain = []

        if not data.get('duration'):
            delivery_domain = [('scheduled_date', '>=', today),('scheduled_date', '<=', today)]
            td_domain = [('scheduled_date', '>=', today),('scheduled_date', '<=', today)]           
        if data:
            if data['product_id']:
                if data['product_id'] != 'all':
                    product_id = int(data['product_id'])
                    delivery_domain += [('move_line_ids.product_id','=',product_id)]
                    td_domain += [('move_line_ids.product_id','=',product_id)]
            if data['warehouse_id']:
                if data['warehouse_id'] != 'all':
                    warehouse_id = int(data['warehouse_id'])
                    delivery_domain += [('company_id','=',warehouse_id)]
                    td_domain += [('company_id','=',warehouse_id)]
            if data['duration']:
                duration = data['duration']
                if duration != "all":
                    duration = int(duration)
                    filter_date = today  - timedelta(days=duration)
                    delivery_domain += [('scheduled_date', '>=', filter_date), ('scheduled_date', '<=', today)]
                    td_domain += [('scheduled_date', '>=', today),('scheduled_date', '<=', today)]
                if duration == '0':
                    td_domain += [('scheduled_date', '>=', today),('scheduled_date', '<=', today)]
                if duration == 'all':
                    td_domain += [('scheduled_date', '>=', today),('scheduled_date', '<=', today)]

        # Fetch counts based on the scheduled date
        due_out_count = request.env['stock.picking'].search([('scheduled_date', '<', today), ('picking_type_code', '=', 'outgoing')] + delivery_domain)
        today_out_count = request.env['stock.picking'].search([('picking_type_code', '=', 'outgoing')]+td_domain)
        future_out_count = request.env['stock.picking'].search([('scheduled_date', '>', today), ('picking_type_code', '=', 'outgoing')]+delivery_domain)

        # Prepare chart data dynamically based on the availability of records
        labels = []
        dataset_data = []
        details = []
        background_colors = []

        if len(due_out_count) > 0:
            labels.append('Overdue')
            dataset_data.append(len(due_out_count))
            details.append(due_out_count.ids)
            background_colors.append(all_color_lists[0])

        if len(today_out_count) > 0:
            labels.append('Today')
            dataset_data.append(len(today_out_count))
            details.append(today_out_count.ids)
            background_colors.append(all_color_lists[1])

        if len(future_out_count) > 0:
            labels.append('Upcoming')
            dataset_data.append(len(future_out_count))
            details.append(future_out_count.ids)
            background_colors.append(all_color_lists[2])

        # Build the chart data object
        delivery_chart_data = {
            'labels': labels,
            'datasets': [{
                'label': 'Receipts',
                'backgroundColor': background_colors,
                'data': dataset_data,
                'detail': details,
            }]
        }

        return request.make_json_response({
            'delivery_chart_data': delivery_chart_data,
        })
        
           
    # ======55555 Operation Type chart 55555===================
    @http.route('/operation/type/chart/data', auth='user', type='http', methods=['POST'], csrf=False)
    def get_operation_type_chart_data(self, **kw):
        try:
            kw = request.get_json_data()
        except ValueError:
            pass
        all_color_lists = ['rgba(252, 24, 185, 0.5)','rgba(83, 39, 70, 0.5)','rgba(134, 182, 191, 0.7)','rgba(174, 191, 134, 0.7)','rgba(240, 128, 128, 0.5)']
        
        today = date.today()
        data = kw['data']
        operation_type_domain = []

        if not data.get('duration'):
            operation_type_domain = [('scheduled_date', '>=', today),('scheduled_date', '<=', today)]
                       
        if data:
            if data['product_id']:
                if data['product_id'] != 'all':
                    product_id = int(data['product_id'])
                    operation_type_domain += [('move_line_ids.product_id','=',product_id)]
                    
            if data['warehouse_id']:
                if data['warehouse_id'] != 'all':
                    warehouse_id = int(data['warehouse_id'])
                    operation_type_domain += [('company_id','=',warehouse_id)]
            if data['duration']:
                duration = data['duration']
                if duration != "all":
                    duration = int(duration)
                    filter_date = today  - timedelta(days=duration)
                    operation_type_domain += [('scheduled_date', '>=', filter_date), ('scheduled_date', '<=', today)]
        
        type_chart_values=[]
        type_chart_labels=[]
        top_repeated_type=[]

        opertation_type_order = request.env['stock.picking'].search_read(operation_type_domain, fields=['picking_type_id'])
        n_lines = sorted(opertation_type_order, key=itemgetter('picking_type_id'))
        groups = itertools.groupby(n_lines, key=operator.itemgetter('picking_type_id'))
        lines = [{'picking_type_id': k, 'values': [x for x in v]} for k, v in groups]

        type_counting_ids=[]
        for x in lines:
            order_id_lst = []
            for id in x['values']:
                order_id_lst.append(id['id'])
            type_counting_ids.append(order_id_lst)
            type_counting_ids=sorted(type_counting_ids, key=lambda x: len(x), reverse=True)

        for line in lines:
            type_chart_values.append(
                {'product': line.get('picking_type_id')[1], 'repeated_time': len(line.get('values'))})
        type_chart_values = (sorted(type_chart_values, key=lambda i: i['repeated_time'], reverse=True))
        for rep_customer_data in type_chart_values:
            type_chart_labels.append(rep_customer_data.get('product'))
            top_repeated_type.append(rep_customer_data.get('repeated_time'))

        operation_type_chart_data = {
            'labels': type_chart_labels,
            'datasets': [{
                'label': "Operation Type",
                'backgroundColor': all_color_lists[:len(type_chart_labels)],
                'data': top_repeated_type,
                'detail':type_counting_ids
            }]
        }
        return request.make_json_response({
            'operation_type_chart_data': operation_type_chart_data
        })
    
    # ======666666 receipt & delivery chart 666666===================
    
    @http.route('/receipt/delivery/chart/data', auth='user', type='http', methods=['POST'], csrf=False)
    def get_receipt_delivery_chart_data(self, **kw):
        try:
            kw = request.get_json_data()
        except ValueError:
            pass
        # Initialize color list (not needed for functionality, but may be useful)
        
        today = date.today()
        data = kw['data']
        receipt_ddelivery_domain = []
        
        if not data.get('duration'):
            receipt_ddelivery_domain = [('date', '>=', today),('date', '<=', today)]
                       
        if data:
            if data['product_id']:
                if data['product_id'] != 'all':
                    product_id = int(data['product_id'])
                    receipt_ddelivery_domain += [('product_id','=',product_id)]
                    
            if data['warehouse_id']:
                if data['warehouse_id'] != 'all':
                    warehouse_id = int(data['warehouse_id'])
                    receipt_ddelivery_domain += [('company_id','=',warehouse_id)]
            if data['duration']:
                duration = data['duration']
                if duration != "all":
                    duration = int(duration)
                    filter_date = today  - timedelta(days=duration)
                    receipt_ddelivery_domain += [('date', '>=', filter_date), ('date', '<=', today)]
        
        # Get the current month and year
        import calendar
        current_month = datetime.now().month
        current_year = datetime.now().year
        # Get the number of days in the current month
        _, num_days = calendar.monthrange(current_year, current_month)
        days_in_month = [i for i in range(1, num_days + 1)]

        # Initialize dictionaries to store product counts, quantities, and record IDs
        receipt_product_ids = {day: {'product_id': set(), 'record_ids': [], 'total_quantity': 0} for day in days_in_month}
        delivery_product_ids = {day: {'product_id': set(), 'record_ids': [], 'total_quantity': 0} for day in days_in_month}

        # Search for all stock pickings (you can optimize this search query)
        top_moving_product_data = request.env['stock.move.line'].search([('state','=','done')]+ receipt_ddelivery_domain)

        # Process each order
        for order in top_moving_product_data:
            if order.date and order.date.month == current_month and order.date.year == current_year:
                # Safe access to picking_type_code via picking_id
                picking_type_code = False
                if order.picking_id and order.picking_id.picking_type_id:
                     picking_type_code = order.picking_id.picking_type_id.code
                # Fallback or alternative logic if picking_type_id is directly on move (unlikely in standard but possible in custom)
                # checking standard Odoo 17/19 structure: stock.move.line -> picking_id -> picking_type_id

                if picking_type_code:
                    # Handle Receipt (Incoming)
                    if picking_type_code == 'incoming':
                        # for move in order: # order IS a stock.move.line record, not a list of moves
                        receipt_day = order.date.day
                        receipt_product_ids[receipt_day]['product_id'].add(order.product_id.name)
                        receipt_product_ids[receipt_day]['record_ids'].append(order.id)
                        receipt_product_ids[receipt_day]['total_quantity'] += order.quantity  # Add quantity

                    # Handle Delivery (Outgoing)
                    if picking_type_code == 'outgoing':
                        # for move in order: # order IS a stock.move.line record
                        delivery_day = order.date.day
                        delivery_product_ids[delivery_day]['product_id'].add(order.product_id.name)
                        delivery_product_ids[delivery_day]['record_ids'].append(order.id)
                        delivery_product_ids[delivery_day]['total_quantity'] += order.quantity  # Add quantity

        # Prepare the chart data
        receipt_delivery_chart_data = {
            'labels': [f"{str(day).zfill(2)}-{datetime(current_year, current_month, day).strftime('%B')}" for day in days_in_month],
            'datasets': [
                {
                    'label': "Incoming",
                    'data': [receipt_product_ids.get(day, {}).get('total_quantity', 0) for day in days_in_month],
                    'detail': [receipt_product_ids[day]['record_ids'] for day in days_in_month]
                },
                {
                    'label': "Outgoing",
                    'data': [delivery_product_ids.get(day, {}).get('total_quantity', 0) for day in days_in_month],
                    'detail': [delivery_product_ids[day]['record_ids'] for day in days_in_month]
                }
            ]
        }

        return request.make_json_response({
            'receipt_delivery_chart_data': receipt_delivery_chart_data,
        })
    
    # =====table 11============
    @http.route('/inventory/table/data', auth='user', type='http', methods=['POST'], csrf=False)
    def get_inventory_list_data(self, **kw):
        try:
            kw = request.get_json_data()
        except ValueError:
            pass
        data=kw['data']
        today = datetime.today().date()
        
        out_of_stock_domain = []
        product_selling_domain = []
        receipt_delivery_domain = []
        
        if not data.get('duration'):
            out_of_stock_domain = [('create_date', '>=', today),('create_date', '<=', today)]
            product_selling_domain = [('date', '>=', today),('date', '<=', today)]
            receipt_delivery_domain = [('scheduled_date', '>=', today),('scheduled_date', '<=', today)]
        if data:
            if data['product_id']:
                if data['product_id'] != 'all':
                    product_id = int(data['product_id'])
                    out_of_stock_domain += [('id','=',product_id)]
                    product_selling_domain += [('product_id','=',product_id)]
                    receipt_delivery_domain += [('move_line_ids.product_id','=',product_id)]
            if data['warehouse_id']:
                if data['warehouse_id'] != 'all':
                    warehouse_id = int(data['warehouse_id'])
                    out_of_stock_domain += [('company_id','=',warehouse_id)]
                    product_selling_domain += [('company_id','=',warehouse_id)]
                    receipt_delivery_domain += [('company_id','=',warehouse_id)]
            if data['duration']:
                duration = data['duration']
                if duration != "all":
                    duration = int(duration)
                    filter_date = today  - timedelta(days=duration)
                    out_of_stock_domain += [('create_date', '>=', filter_date), ('create_date', '<=', today)]
                    product_selling_domain += [('date', '>=', filter_date), ('date', '<=', today)]
                    receipt_delivery_domain += [('scheduled_date', '>=', filter_date), ('scheduled_date', '<=', today)]
        
        out_of_stock_list = request.env['product.product'].search_read([('qty_available', '<=', 0)] + out_of_stock_domain,
                                                                       fields=['image_1920','name','qty_available'])
        
        # Removed 'name' from fields as it might cause issues and is not used in the loop below
        top_product_selling_list = request.env['stock.move'].search_read([('state', '=', 'done'),("location_dest_id.usage", "not in", ("internal", "transit"))]
                                                                         + product_selling_domain, fields=['product_id', 'quantity'],order="quantity desc", )
    
        product_data = []
        for move in top_product_selling_list:
            product = request.env['product.product'].browse(move['product_id'][0])
            image_base64 = product.image_1920  
            product_data.append({
                'image_base64': image_base64,
                'name': product.display_name,
                'sold_qty': move['quantity'],
                'id': move['id']
            })
                
        receipt_list = request.env['stock.picking'].search_read([('picking_type_code', '=', 'incoming')] + receipt_delivery_domain,
                                                                fields=['name','partner_id','scheduled_date'])
        delivery_list = request.env['stock.picking'].search_read([('picking_type_code', '=', 'outgoing')] + receipt_delivery_domain,
                                                                 fields=['name','partner_id','scheduled_date'])             
        
        return request.make_json_response({
            'out_of_stock_list': out_of_stock_list,
            'top_product_selling_list': product_data,
            'receipt_list': receipt_list,
            'delivery_list': delivery_list,
        })
    
    @http.route('/inventory/filter-apply', auth='user', type='http', methods=['POST'], csrf=False)
    def inventory_filter_apply(self, **kw):
        try:
            kw = request.get_json_data()
        except ValueError:
            pass
        data = kw['data']
        
        product_id = data['product']
        warehouse_id = data['warehouse']
        duration = data['duration']

        result = self.get_inventory_tiles_data(product_id=product_id, warehouse_id=warehouse_id, duration=duration)
        return result


        
        
        
        
        
        

    
    
        


    
    