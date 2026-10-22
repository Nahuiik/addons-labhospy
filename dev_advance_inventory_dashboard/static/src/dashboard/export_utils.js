/** @odoo-module **/

/** Utilidades de exportación cliente (CSV). */

export function downloadCsv(filename, rows, headers) {
    const escape = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const lines = [headers.map(escape).join(",")];
    for (const row of rows) {
        lines.push(row.map(escape).join(","));
    }
    const blob = new Blob(["\ufeff" + lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
}

export function downloadBase64File(filename, base64, mimetype) {
    const link = document.createElement("a");
    link.href = `data:${mimetype};base64,${base64}`;
    link.download = filename;
    link.click();
}

export function tableRowsToCsv(tableData, tableKey) {
    const rows = tableData?.rows || [];
    if (tableKey === "out_of_stock" || tableKey === "top_selling") {
        return {
            headers: ["ID", "Nombre", "Cantidad"],
            rows: rows.map((r) => [r.id, r.name, r.qty]),
        };
    }
    return {
        headers: ["ID", "Nombre", "Contacto", "Fecha", "Estado"],
        rows: rows.map((r) => [r.id, r.name, r.partner || "", r.date || "", r.state || ""]),
    };
}
