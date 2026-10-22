/** @odoo-module */

import { registry } from '@web/core/registry';
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { loadJS } from "@web/core/assets";
import { Component, onWillStart, onMounted, useState, useRef, onWillUnmount } from "@odoo/owl";

export class InvetoryDashboard extends Component {
    static template = "invetorydashboard";

    setup() {
        this.actionService = useService("action");
        this.orm = useService("orm");
        
        // Use native fetch for our custom controllers returning plain JSON
        this.fetchData = async (route, params = {}) => {
            try {
                const response = await fetch(route, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(params),
                });
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return await response.json();
            } catch (error) {
                console.error("Fetch error:", error);
                return {};
            }
        };
        
        this.topMovingChartRef = useRef("topMovingChart");
        this.stockMovingLocationChartRef = useRef("stockMovingLocationChart");
        this.receiptsChartRef = useRef("receiptsChart");
        this.deliveryChartRef = useRef("deliveryChart");
        this.operationTypeChartRef = useRef("operationTypeChart");
        this.receiptDeliveryChartRef = useRef("receiptDeliveryChart");

        this.state = useState({
            // Data
            order_ship_data: [],
            order_due_shipment_data: [],
            open_po_data: [],
            pending_shipment_data: [],
            quantity_inhand_data: 0,
            total_quantity_data_ids: [],
            total_received: 0,
            received_quantity_data: [],
            out_stock_product_data: [],
            total_product_data: [],
            
            // User Info
            user_name: '',
            user_img: '',
            greetings: '',

            // Filters
            products: [],
            warehouses: [],
            selectedProduct: 'all',
            selectedWarehouse: 'all',
            selectedDuration: '0', // Default to Today
            
            // Chart Options
            topMovingProductCount: '5',
            movingPrdtChartType: 'bar', // Default to bar

            // Pagination & Tables
            rowsPerPage: 5,
            
            // Out of Stock Table
            outOfStockList: [],
            outOfStockPage: 1,
            outOfStockTotal: 0,

            // Selling Product Table
            sellingProductList: [],
            sellingProductPage: 1,
            sellingProductTotal: 0,

            // Receipt Table
            receiptList: [],
            receiptPage: 1,
            receiptTotal: 0,

            // Delivery Table
            deliveryList: [],
            deliveryPage: 1,
            deliveryTotal: 0,
        });

        this.charts = {};

        onWillStart(async () => {
            await loadJS("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.js");
            await loadJS("https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js");
            await this.fetchFilters();
            await this.fetchInventoryData();
            await this.getGreetings();
        });

        onMounted(async () => {
            // Render charts initially
            await this.updateAllCharts();
            // Fetch initial table data
            await this.fetchTableData();
        });
        
        onWillUnmount(() => {
            Object.values(this.charts).forEach(chart => chart?.destroy());
        });
    }

    getGreetings() {
        const now = new Date();
        const hours = now.getHours();
        if (hours >= 5 && hours < 12) {
            this.state.greetings = _t("Good Morning");
        } else if (hours >= 12 && hours < 18) {
            this.state.greetings = _t("Good Afternoon");
        } else {
            this.state.greetings = _t("Good Evening");
        }
    }

    async fetchFilters() {
        const data = await this.fetchData('/all_inventory_filter');
        if (data) {
            this.state.products = data[0];
            this.state.warehouses = data[1];
        }
    }

    async fetchInventoryData() {
        const data = {
            'product_id': this.state.selectedProduct,
            'warehouse_id': this.state.selectedWarehouse,
            'duration': this.state.selectedDuration,
        };
        
        const result = await this.fetchData('/get/inventory/tiles/data', data);
        
        if (result) {
            this.state.order_ship_data = result.order_ship_data || [];
            this.state.order_due_shipment_data = result.order_due_shipment_data || [];
            this.state.open_po_data = result.open_po_data || [];
            this.state.pending_shipment_data = result.pending_shipment_data || [];
            this.state.quantity_inhand_data = result.quantity_inhand_data || 0;
            this.state.total_quantity_data_ids = result.total_quantity_data_ids || [];
            this.state.total_received = result.total_received || 0;
            this.state.received_quantity_data = result.received_quantity_data || [];
            this.state.out_stock_product_data = result.out_stock_product_data || [];
            this.state.total_product_data = result.total_product_data || [];
            this.state.user_name = result.user_name || '';
            this.state.user_img = result.user_img || '';
        }
    }

    async onFilterChange() {
        await this.fetchInventoryData();
        await this.updateAllCharts();
        
        // Reset pages when filter changes
        this.state.outOfStockPage = 1;
        this.state.sellingProductPage = 1;
        this.state.receiptPage = 1;
        this.state.deliveryPage = 1;
        
        await this.fetchTableData();
    }

    async updateAllCharts() {
        await this.renderMovingProductChart();
        await this.renderMovingLocationChart();
        await this.renderReceiptChart();
        await this.renderDeliveryChart();
        await this.renderOperationTypeChart();
        await this.renderReceiptDeliveryChart();
    }

    getFilterData() {
        return {
            'data': {
                'product_id': this.state.selectedProduct,
                'warehouse_id': this.state.selectedWarehouse,
                'duration': this.state.selectedDuration,
                'top_moving_product_count': this.state.topMovingProductCount,
            }
        };
    }

    // --- Charts ---

    async renderMovingProductChart() {
        const data = await this.fetchData('/moving/product/chart/data', this.getFilterData());
        const ctx = this.topMovingChartRef.el;
        if (!ctx || !data.top_moving_chart_data) return;

        if (this.charts.movingProduct) this.charts.movingProduct.destroy();

        this.charts.movingProduct = new Chart(ctx, {
            type: this.state.movingPrdtChartType,
            data: data.top_moving_chart_data,
            options: {
                maintainAspectRatio: false,
                onClick: (evt, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const label = data.top_moving_chart_data.labels[index];
                        const value = data.top_moving_chart_data.datasets[0].detail[index];
                        this.openAction(label, 'stock.move.line', value);
                    }
                }
            }
        });
    }

    async renderMovingLocationChart() {
        const data = await this.fetchData('/moving/location/chart/data', this.getFilterData());
        const ctx = this.stockMovingLocationChartRef.el;
        if (!ctx || !data.stock_moving_location_chart_data) return;

        if (this.charts.movingLocation) this.charts.movingLocation.destroy();

        this.charts.movingLocation = new Chart(ctx, {
            type: 'bar',
            data: data.stock_moving_location_chart_data,
            options: {
                scales: { x: { stacked: true }, y: { stacked: true } },
                onClick: (evt, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const datasetIndex = elements[0].datasetIndex;
                        const label = data.stock_moving_location_chart_data.labels[index];
                        let ids = data.stock_moving_location_chart_data.datasets[datasetIndex].detail[index];
                        
                        // Filter logic from original code
                        const available = data.stock_moving_location_chart_data.datasets[0].data[index];
                        const reserved = data.stock_moving_location_chart_data.datasets[1].data[index];
                        if (available > 0 || reserved > 0) {
                            this.openAction(label, 'stock.quant', ids);
                        }
                    }
                }
            }
        });
    }

    async renderReceiptChart() {
        const data = await this.fetchData('/receipt/chart/data', this.getFilterData());
        const ctx = this.receiptsChartRef.el;
        if (!ctx || !data.receipts_chart_data) return;

        if (this.charts.receipts) this.charts.receipts.destroy();

        this.charts.receipts = new Chart(ctx, {
            type: 'pie',
            data: data.receipts_chart_data,
            options: {
                maintainAspectRatio: false,
                onClick: (evt, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const label = data.receipts_chart_data.labels[index];
                        const ids = data.receipts_chart_data.datasets[0].detail[index];
                        this.openAction(label, 'stock.picking', ids);
                    }
                }
            }
        });
    }

    async renderDeliveryChart() {
        const data = await this.fetchData('/delivery/chart/data', this.getFilterData());
        const ctx = this.deliveryChartRef.el;
        if (!ctx || !data.delivery_chart_data) return;

        if (this.charts.delivery) this.charts.delivery.destroy();

        this.charts.delivery = new Chart(ctx, {
            type: 'polarArea',
            data: data.delivery_chart_data,
            options: {
                maintainAspectRatio: false,
                onClick: (evt, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const label = data.delivery_chart_data.labels[index];
                        const ids = data.delivery_chart_data.datasets[0].detail[index];
                        this.openAction(label, 'stock.picking', ids);
                    }
                }
            }
        });
    }

    async renderOperationTypeChart() {
        const data = await this.fetchData('/operation/type/chart/data', this.getFilterData());
        const ctx = this.operationTypeChartRef.el;
        if (!ctx || !data.operation_type_chart_data) return;

        if (this.charts.operationType) this.charts.operationType.destroy();

        this.charts.operationType = new Chart(ctx, {
            type: 'doughnut',
            data: data.operation_type_chart_data,
            options: {
                maintainAspectRatio: false,
                onClick: (evt, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const label = data.operation_type_chart_data.labels[index];
                        const ids = data.operation_type_chart_data.datasets[0].detail[index];
                        this.openAction(label, 'stock.picking', ids);
                    }
                }
            }
        });
    }

    async renderReceiptDeliveryChart() {
        const data = await this.fetchData('/receipt/delivery/chart/data', this.getFilterData());
        const ctx = this.receiptDeliveryChartRef.el;
        if (!ctx || !data.receipt_delivery_chart_data) return;

        if (this.charts.receiptDelivery) this.charts.receiptDelivery.destroy();

        this.charts.receiptDelivery = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.receipt_delivery_chart_data.labels,
                datasets: [
                    {
                        label: 'Incoming',
                        data: data.receipt_delivery_chart_data.datasets[0].data,
                        backgroundColor: 'rgba(255, 99, 132, 0.5)',
                        borderColor: 'rgba(255, 99, 132, 1)',
                        pointBackgroundColor: 'white',
                        fill: true
                    },
                    {
                        label: 'Outgoing',
                        data: data.receipt_delivery_chart_data.datasets[1].data,
                        backgroundColor: 'rgba(0, 255, 255, 0.5)',
                        borderColor: 'rgba(0, 255, 255, 1)',
                        pointBackgroundColor: 'white',
                        fill: true
                    }
                ]
            },
            options: {
                maintainAspectRatio: false,
                onClick: (evt, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const datasetIndex = elements[0].datasetIndex;
                        const label = data.receipt_delivery_chart_data.labels[index];
                        const ids = data.receipt_delivery_chart_data.datasets[datasetIndex].detail[index];
                        const prefix = datasetIndex === 0 ? "Receipt - " : "Delivery - ";
                        this.openAction(prefix + label, 'stock.move.line', ids);
                    }
                }
            }
        });
    }

    // --- Tables ---

    async fetchTableData() {
        const data = await this.fetchData('/inventory/table/data', this.getFilterData());
        
        if (data) {
            // Out of Stock
            this.state.outOfStockTotal = (data.out_of_stock_list || []).length;
            this.state.outOfStockList = data.out_of_stock_list || [];

            // Selling Product
            this.state.sellingProductTotal = (data.top_product_selling_list || []).length;
            this.state.sellingProductList = data.top_product_selling_list || [];

            // Receipt
            this.state.receiptTotal = (data.receipt_list || []).length;
            this.state.receiptList = data.receipt_list || [];

            // Delivery
            this.state.deliveryTotal = (data.delivery_list || []).length;
            this.state.deliveryList = data.delivery_list || [];
        }
    }

    get paginatedOutOfStock() {
        const start = (this.state.outOfStockPage - 1) * this.state.rowsPerPage;
        return this.state.outOfStockList.slice(start, start + this.state.rowsPerPage);
    }

    get paginatedSellingProduct() {
        const start = (this.state.sellingProductPage - 1) * this.state.rowsPerPage;
        return this.state.sellingProductList.slice(start, start + this.state.rowsPerPage);
    }

    get paginatedReceipt() {
        const start = (this.state.receiptPage - 1) * this.state.rowsPerPage;
        return this.state.receiptList.slice(start, start + this.state.rowsPerPage);
    }

    get paginatedDelivery() {
        const start = (this.state.deliveryPage - 1) * this.state.rowsPerPage;
        return this.state.deliveryList.slice(start, start + this.state.rowsPerPage);
    }

    changePage(table, direction) {
        const pageKey = table + 'Page';
        const totalKey = table + 'Total';
        const maxPage = Math.ceil(this.state[totalKey] / this.state.rowsPerPage);
        
        if (direction === 'prev' && this.state[pageKey] > 1) {
            this.state[pageKey]--;
        } else if (direction === 'next' && this.state[pageKey] < maxPage) {
            this.state[pageKey]++;
        }
    }

    // --- Helpers ---

    openAction(name, resModel, ids) {
        const domain = Array.isArray(ids) ? [["id", "in", ids]] : [["id", "=", ids]];
        this.actionService.doAction({
            name: _t(name),
            type: 'ir.actions.act_window',
            res_model: resModel,
            domain: domain,
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            target: 'current'
        });
    }
    
    openTileAction(type) {
        let domain = [];
        let name = "";
        let resModel = "stock.picking";

        switch (type) {
            case 'order_ship_data':
                domain = [["id", "in", this.state.order_ship_data]];
                name = "Ready Orders";
                break;
            case 'order_due_shipment_data':
                domain = [["id", "in", this.state.order_due_shipment_data]];
                name = "Overdue Picking Orders";
                break;
            case 'open_po_data':
                domain = [["id", "in", this.state.open_po_data]];
                name = "Awaiting Delivery Orders";
                break;
            case 'pending_shipment_data':
                domain = [["id", "in", this.state.pending_shipment_data]];
                name = "Overdue Delivery Orders";
                break;
            case 'quantity_inhand_data':
                domain = [["id", "in", this.state.total_quantity_data_ids]];
                name = "Total Quantity";
                resModel = "product.product";
                break;
            case 'received_quantity_data':
                domain = [["id", "in", this.state.received_quantity_data]];
                name = "Received Quantity";
                resModel = "stock.move";
                break;
            case 'out_stock_product_data':
                domain = [["id", "in", this.state.out_stock_product_data]];
                name = "Out of Stock Items";
                resModel = "product.product";
                break;
            case 'total_product_data':
                domain = [["id", "in", this.state.total_product_data]];
                name = "Total Products";
                resModel = "product.product";
                break;
        }

        this.actionService.doAction({
            name: _t(name),
            type: 'ir.actions.act_window',
            res_model: resModel,
            domain: domain,
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            target: 'current'
        });
    }

    createPO(productId, productName, productUOM) {
        this.actionService.doAction({
            name: _t("Create Purchase Order"),
            type: 'ir.actions.act_window',
            res_model: 'purchase.order',
            view_mode: 'form',
            views: [[false, 'form']],
            target: 'current',
            context: {
                'default_order_line': [[0, 0, {
                    'product_id': productId,
                    'name': productName,
                    // 'product_uom': productUOM // Might need adjustments based on data structure
                }]],
            },
        });
    }

    downloadReport() {
        const element = document.getElementById("dashboard");
        const opt = {
            margin: 1,
            filename: 'InventoryDashboard.pdf',
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: { scale: 2 },
            jsPDF: { unit: 'px', format: [1920, 1080], orientation: 'landscape' }
        };
        html2pdf().set(opt).from(element).save();
    }

    downloadChart(refName) {
        const chartCanvas = this[refName].el;
        if (!chartCanvas) return;
        
        const imageDataURL = chartCanvas.toDataURL('image/png');
        const filename = refName + '.png';
        const link = document.createElement('a');
        link.href = imageDataURL;
        link.download = filename;
        link.click();
    }
    
    formatDate(dateString) {
        if (!dateString) return '-';
        const date = new Date(dateString);
        return date.toLocaleString();
    }
}

registry.category("actions").add("open_inventory_dashboard", InvetoryDashboard);
