/** @odoo-module **/


import { download } from "@web/core/network/download";
import { ConnectionLostError } from "@web/core/network/rpc";

const originalDownload = download._download;

download._download = async function (params) {
    if (!params.url || params.url !== "/report/download") {
        return originalDownload.apply(this, arguments);
    }

    const [_, reportFormat] = JSON.parse(params.data.data);
    if (reportFormat !== "qweb-pdf") {
        return originalDownload.apply(this, arguments);
    }

    const requestData = new FormData(params.form || undefined);
    if (!params.form) {
        Object.entries(params.data).forEach(([key, value]) => requestData.append(key, value));
    }

    requestData.append("token", "dummy-because-api-expects-one");
    if (window.odoo?.csrf_token) {
        requestData.append("csrf_token", window.odoo.csrf_token);
    }

    return fetch(params.form ? params.form.action : params.url, {
        method: params.form ? params.form.method : "POST",
        body: requestData,
    })
    .then((response) => processResponse(response))
    .catch(() => {
        return Promise.reject(new ConnectionLostError());
    });
};

function processResponse(serverResponse) {
    if (!serverResponse.ok) {
        return serverResponse.text().then((errorText) => Promise.reject(new Error(errorText)));
    }


    function extractHeaderValue(headerKey) {
        return serverResponse.headers.get(headerKey) && decodeURIComponent(serverResponse.headers.get(headerKey));
    }

    const printOption = extractHeaderValue("Report-Print-Options");

    return serverResponse.blob().then((fileBlob) => {
        if (printOption === "open_print_dialog") {

            let printFrame = document.getElementById("pdf-print-frame") || document.createElement("iframe");
            if (!printFrame.parentNode) {
                printFrame.id = "pdf-print-frame";
                printFrame.style.position = "absolute";
                printFrame.style.width = "0px";
                printFrame.style.height = "0px";
                printFrame.style.border = "none";
                document.body.appendChild(printFrame);
            }

            const fileUrl = URL.createObjectURL(fileBlob);
            printFrame.src = fileUrl;

            printFrame.onload = () => {
                printFrame.contentWindow.print();
            };
        } else {
            const fileName = extractFilename(serverResponse);
            downloadFile(fileBlob, fileName);
        }
        
    });


}
function extractFilename(response) {
    const contentDisposition = response.headers.get("Content-Disposition");
    if (!contentDisposition) return "report.pdf";

    const match = contentDisposition.match(/filename[^;=\n]*=(UTF-8'')?["']?([^;"'\n]*)["']?/);
    return match && match[2] ? decodeURIComponent(match[2]) : "report.pdf";
}

function downloadFile(blob, filename) {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}