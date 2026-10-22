/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { DEFAULT_MAX_FILE_SIZE } from "@web/core/utils/files";
import { humanNumber } from "@web/core/utils/numbers";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";

import { CharField, charField } from "@web/views/fields/char/char_field";
import { useRef, useState } from "@odoo/owl";

export class GnFolderRootPathCharField extends CharField {
    static template = "gn_qif_openai_reconcile.GnFolderRootPathCharField";

    setup() {
        super.setup();
        this.http = useService("http");
        this.notification = useService("notification");
        this.folderInputRef = useRef("folderInput");
        this.state = useState({
            isUploading: false,
        });
    }

    onPickFolder() {
        this.folderInputRef.el?.click();
    }

    async onFolderChange(ev) {
        const input = ev.target;
        const list = input.files ? [...input.files] : [];
        input.value = "";
        if (!list.length) {
            return;
        }
        const maxSize = session.max_file_upload_size || DEFAULT_MAX_FILE_SIZE;
        const excel = list.filter((f) => /\.(xlsx|xls)$/i.test(f.name));
        if (!excel.length) {
            this.notification.add(_t("No hay archivos .xlsx ni .xls en la carpeta elegida."), {
                type: "warning",
            });
            return;
        }
        for (const f of excel) {
            if (f.size > maxSize) {
                this.notification.add(
                    _t("Un archivo supera el tamaño máximo permitido (%(max)s B).", {
                        max: humanNumber(maxSize),
                    }),
                    { type: "danger" }
                );
                return;
            }
        }

        const formData = new FormData();
        formData.append("csrf_token", odoo.csrf_token);
        for (const f of excel) {
            const relPath = f.webkitRelativePath || f.name;
            formData.append("ufile", f, relPath);
        }

        this.state.isUploading = true;
        try {
            const text = await this.http.post(
                "/gn_qif/folder_import/upload_tree",
                formData,
                "text"
            );
            let data = {};
            try {
                data = JSON.parse(text);
            } catch (e) {
                this.notification.add(_t("Respuesta inválida del servidor."), { type: "danger" });
                return;
            }
            if (data.error) {
                this.notification.add(data.error, { type: "danger" });
                return;
            }
            await this.props.record.update({ folder_root: data.folder_root });
            this.notification.add(
                _t("%(n)s archivo(s) subidos al servidor; pulse «Escane e importar».", {
                    n: data.excel_count,
                }),
                { type: "success" }
            );
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        } finally {
            this.state.isUploading = false;
        }
    }
}

export const gnFolderRootPathCharField = {
    ...charField,
    component: GnFolderRootPathCharField,
};

registry.category("fields").add("gn_folder_root_path", gnFolderRootPathCharField);
