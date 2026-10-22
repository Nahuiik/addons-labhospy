/** @odoo-module **/

export function downloadBase64File(result) {
    if (!result?.data) return;
    const link = document.createElement("a");
    link.href = `data:${result.mimetype || "application/octet-stream"};base64,${result.data}`;
    link.download = result.filename || "export.csv";
    link.click();
}
