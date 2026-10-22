/* @odoo-module */
/* eslint-env browser */
/* global document */

import {ListRenderer} from "@web/views/list/list_renderer";
import {onMounted} from "@odoo/owl";
import {patch} from "@web/core/utils/patch";

/**
 * Patch for ListRenderer
 *
 * Enhances tree/list views by adding a row number column (#).
 * - Inserts a header cell before the first column.
 * - Adds a matching footer cell for proper alignment.
 * - Applies custom width styling to the "sequence" column if present.
 */
patch(ListRenderer.prototype, {
    setup() {
        super.setup();

        onMounted(() => {
            const table = this.tableRef.el;
            if (!table) {
                return;
            }

            // === Handle header row (# column) ===
            const headerRow = table.querySelector("thead tr");

            // Apply custom width style to "sequence" column if found
            const sequenceColumn = table.querySelector('th[data-name="sequence"]');
            if (sequenceColumn) {
                sequenceColumn.classList.add("custom-width");
            }

            // Insert "#" column in header if not already present
            if (
                headerRow &&
                !headerRow.firstElementChild.classList.contains(
                    "o_list_row_count_sheliya"
                )
            ) {
                const th = document.createElement("th");
                th.className =
                    "o_list_row_number_header o_list_row_count_sheliya custom-width";
                th.style.width = "4%";
                th.textContent = "#";
                headerRow.insertAdjacentElement("afterbegin", th);
            }

            // === Handle footer row (alignment placeholder) ===
            const footerRow = table.querySelector("tfoot tr");
            if (
                footerRow &&
                !footerRow.firstElementChild.classList.contains(
                    "o_list_row_count_sheliya"
                )
            ) {
                const td = document.createElement("td");
                td.className = "o_list_row_count_sheliya";
                footerRow.insertAdjacentElement("afterbegin", td);
            }

            // Re-render list view to apply DOM modifications
            this.render();
        });
    },
});
