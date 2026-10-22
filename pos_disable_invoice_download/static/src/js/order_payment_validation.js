import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(OrderPaymentValidation.prototype, {
    shouldDownloadInvoice() {
        console.log("shouldDownloadInvoice!!!");
        return this.pos.config.allow_pdf_download
    }
});
