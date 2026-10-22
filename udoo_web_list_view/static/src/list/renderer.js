/** @odoo-module **/

import { _t } from '@web/core/l10n/translation';
import { patch } from '@web/core/utils/patch';
import { useService, useBus } from '@web/core/utils/hooks';
import { isMobileOS } from '@web/core/browser/feature_detection';
import { useState, onWillStart } from '@odoo/owl';
import { session } from '@web/session';

import { ListRenderer } from '@web/views/list/list_renderer';

import { ColumnManager } from '../mod/manager';


export const olvListRenderer = () => ({
    setup() {
        super.setup(...arguments);

        this.actionService = useService('action');
        this.dialogService = useService('dialog');
        
        // Safe user service access
        try {
            this.userService = useService('user');
        } catch (e) {
            // console.warn('User service not available in Renderer setup');
            this.userService = null;
        }
        
        this.hasGroupState = useState({ value: false });

        onWillStart(async () => {
            if (!this.userService) return;
            try {
                this.hasGroupState.value = await this.userService.hasGroup('udoo_web_list_view.group_advanced_list');
            } catch (e) {
                // Fallback or debug mode
            }
        });

        let isSystem = false;
        if (this.userService) {
            isSystem = this.userService.isSystem;
        } else {
            // Fallback if service missing (e.g. public user or weird context)
            // We default to TRUE here to allow button to render if backend allows, 
            // but hasGroup check will fail (false), so button will be hidden anyway by the group check.
            // Wait, if hasGroup is false, isUdooEditable is false.
            // So if service fails, feature is disabled. That is secure.
            isSystem = false; 
        }

        const list = this.props.list;

        const { actionId, actionType } = this.env.config || {};
        const inDialog = this.env.inDialog || false;

        const isPotentiallyEditable =
            !isMobileOS() &&
            !inDialog &&
            isSystem &&
            list === list.model.root &&
            actionId &&
            actionType === 'ir.actions.act_window';
        
        this.udooEditable = useState({ value: isPotentiallyEditable });

        if (isPotentiallyEditable) {
            const OmuxEditable = (action) => {
                if (!action.xml_id) {
                    return false;
                }
                return Boolean(action.res_model);
            };
            useBus(this.env.bus, 'ACTION_MANAGER:UI-UPDATED', () => {
                const action = this.actionService.currentController?.action;
                if (action && action.id === actionId) {
                    this.udooEditable.value = OmuxEditable(action);
                }
            });
        }
    },

    /**
     * @override
     */
    isSortable(column) {
        const { options } = column;
        return super.isSortable(column) && options?.unsortable != true;
    },

    isUdooEditable() {
        return (this.udooEditable?.value && this.hasGroupState.value) || false;
    },

    get displayOptionalFields() {
        return this.isUdooEditable() || super.displayOptionalFields;
    },

    /**
     * @override
     * Extend optionalColumns to include our "Manage Columns" item
     * This ensures the item appears in the dropdown even if template fails
     */
    get optionalColumns() {
        const columns = super.optionalColumns || [];
        if (this.isUdooEditable()) {
            // Check if our item is already in the list
            const hasManageColumns = columns.some(col => col.name === '_udoo_manage_columns');
            if (!hasManageColumns) {
                const newItem = {
                    name: '_udoo_manage_columns',
                    id: '_udoo_manage_columns', // Ensure ID exists
                    string: _t('Manage Columns'),
                    onSelected: () => this.openColumnManager(),
                    icon: 'fa fa-wrench',
                    class: 'd-flex align-items-center',
                    type: 'action', // Mark as action just in case
                };
                return [...columns, newItem];
            }
        }
        return columns;
    },

    /**
     * This function opens promote studio dialog
     *
     * @private
     */
                openColumnManager() {
                    const { archInfo, list } = this.props;
                    
                    // Try multiple sources for fields (Robust Odoo 19 detection)
                    let fields = {};
                    if (this.env.searchModel && this.env.searchModel.fields) {
                         fields = { ...this.env.searchModel.fields };
                    }
                    
                    if (list.model && list.model.config && list.model.config.fields) {
                        fields = { ...fields, ...list.model.config.fields };
                    } else if (list.model && list.model.fields) {
                        fields = { ...fields, ...list.model.fields };
                    } else if (list.fields) {
                        fields = { ...fields, ...list.fields };
                    }

                    // Pass RPC service explicitly to avoid context issues
                    this.dialogService.add(ColumnManager, {
                        viewId: this.env.config.viewId,
                        resModel: list.resModel,
                        fields: fields,
                        fieldNodes: archInfo.fieldNodes,
                    });
                },
});

export const unpatchListRenderer = patch(ListRenderer.prototype, olvListRenderer());
