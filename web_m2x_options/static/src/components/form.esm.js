import {Many2XAutocomplete} from "@web/views/fields/relational_utils";
import {Many2OneField} from "@web/views/fields/many2one/many2one_field";
import {Many2One} from "@web/views/fields/many2one/many2one";
import {FormController} from "@web/views/form/form_controller";
import {evaluateBooleanExpr} from "@web/core/py_js/py";
import {fieldColorProps} from "../views/fields/standard_field_props.esm";
import {isX2Many} from "@web/views/utils";
import {many2ManyTagsField} from "@web/views/fields/many2many_tags/many2many_tags_field";
import {patch} from "@web/core/utils/patch";
import {registry} from "@web/core/registry";
import {session} from "@web/session";

Many2XAutocomplete.props = {
    ...Many2XAutocomplete.props,
    ...fieldColorProps,
    noSearchMore: {type: Boolean, optional: true},
};

Many2One.props = {
    ...Many2One.props,
    searchLimit: {type: Number, optional: true},
    noSearchMore: {type: Boolean, optional: true},
    ...fieldColorProps,
};

function evaluateSystemParameterDefaultTrue(option) {
    const isOptionSet = session.web_m2x_options[`web_m2x_options.${option}`];
    return isOptionSet ? evaluateBooleanExpr(isOptionSet) : true;
}

const many2OneFieldDef = registry.category("fields").get("many2one");

patch(many2OneFieldDef, {
    m2o_options_props_create(props, attrs, options) {
        const canQuickCreate = evaluateSystemParameterDefaultTrue("create");
        if (options.no_quick_create) {
            props.canQuickCreate = false;
        } else if ("no_quick_create" in options) {
            props.canQuickCreate = attrs.can_create
                ? evaluateBooleanExpr(attrs.can_create)
                : true;
        } else if (!canQuickCreate && props.canQuickCreate) {
            props.canQuickCreate = false;
        } else if (canQuickCreate && !props.canQuickCreate) {
            props.canQuickCreate = attrs.can_create
                ? evaluateBooleanExpr(attrs.can_create)
                : true;
        }
        return props;
    },

    m2o_options_props_create_edit(props, attrs, options) {
        const canCreateEdit = evaluateSystemParameterDefaultTrue("create_edit");
        if (options.no_create_edit) {
            props.canCreateEdit = false;
        } else if ("no_create_edit" in options) {
            props.canCreateEdit = attrs.can_create
                ? evaluateBooleanExpr(attrs.can_create)
                : true;
        } else if (!canCreateEdit && props.canCreateEdit) {
            props.canCreateEdit = false;
        } else if (canCreateEdit && !props.canCreateEdit) {
            props.canCreateEdit = attrs.can_create
                ? evaluateBooleanExpr(attrs.can_create)
                : true;
        }
        return props;
    },

    m2o_options_props_limit(props, attrs, options) {
        const ir_options = session.web_m2x_options;
        if (Number(options.limit)) {
            props.searchLimit = Number(options.limit);
        } else if (Number(ir_options["web_m2x_options.limit"])) {
            props.searchLimit = Number(ir_options["web_m2x_options.limit"]);
        }
        return props;
    },

    m2o_options_props_search_more(props, attrs, options) {
        const noSearchMore = !evaluateSystemParameterDefaultTrue("search_more");
        if (options.search_more) {
            props.noSearchMore = false;
        } else if ("search_more" in options) {
            props.noSearchMore = true;
        } else if (!noSearchMore && props.noSearchMore) {
            props.noSearchMore = false;
        } else if (noSearchMore) {
            props.noSearchMore = true;
        }
        return props;
    },

    m2o_options_props_open(props, attrs, options) {
        if (!("no_open" in options)) {
            props.canOpen = evaluateSystemParameterDefaultTrue("open");
        }
        return props;
    },

    m2o_options_props(props, attrs, options) {
        let newProps = props;
        newProps = this.m2o_options_props_create(newProps, attrs, options);
        newProps = this.m2o_options_props_create_edit(newProps, attrs, options);
        newProps = this.m2o_options_props_limit(newProps, attrs, options);
        newProps = this.m2o_options_props_search_more(newProps, attrs, options);
        newProps = this.m2o_options_props_open(newProps, attrs, options);
        newProps.fieldColor = options.field_color;
        newProps.fieldColorOptions = options.colors;
        return newProps;
    },

    extractProps(staticInfo, dynamicInfo) {
        const props = super.extractProps(staticInfo, dynamicInfo);
        const {attrs, options} = staticInfo;
        return this.m2o_options_props(props, attrs, options);
    },
});

patch(Many2OneField.prototype, {
    get m2oProps() {
        const props = super.m2oProps;
        if (this.props.searchLimit) {
            props.searchLimit = this.props.searchLimit;
        }
        if (this.props.noSearchMore !== undefined) {
            props.noSearchMore = this.props.noSearchMore;
        }
        if (this.props.fieldColor) {
            props.fieldColor = this.props.fieldColor;
        }
        if (this.props.fieldColorOptions) {
            props.fieldColorOptions = this.props.fieldColorOptions;
        }
        return props;
    },
});

patch(Many2One.prototype, {
    get many2XAutocompleteProps() {
        const props = super.many2XAutocompleteProps;
        if (Number(this.props.searchLimit) && Number(this.props.searchLimit) > 1) {
            props.searchLimit = this.props.searchLimit - 1;
        }
        if (this.props.noSearchMore) {
            props.noSearchMore = this.props.noSearchMore;
        }
        if (this.props.fieldColor && this.props.fieldColorOptions) {
            props.fieldColor = this.props.fieldColor;
            props.fieldColorOptions = this.props.fieldColorOptions;
        }
        return props;
    },
});

patch(many2ManyTagsField, {
    m2m_options_props_create(props, attrs, options) {
        const canQuickCreate = evaluateSystemParameterDefaultTrue("create");
        if (!options.no_quick_create) {
            if (!canQuickCreate && props.canQuickCreate) {
                props.canQuickCreate = false;
            } else if (canQuickCreate && !props.canQuickCreate) {
                props.canQuickCreate = attrs.can_create
                    ? evaluateBooleanExpr(attrs.can_create)
                    : true;
            }
        }
        return props;
    },

    m2m_options_props_create_edit(props, attrs, options) {
        const canCreateEdit = evaluateSystemParameterDefaultTrue("create_edit");
        if (options.no_create_edit) {
            props.canCreateEdit = false;
        } else if ("no_create_edit" in options) {
            props.canCreateEdit = attrs.can_create
                ? evaluateBooleanExpr(attrs.can_create)
                : true;
        } else if (!canCreateEdit && props.canCreateEdit) {
            props.canCreateEdit = false;
        } else if (canCreateEdit && !props.canCreateEdit) {
            props.canCreateEdit = attrs.can_create
                ? evaluateBooleanExpr(attrs.can_create)
                : true;
        }
        return props;
    },

    m2m_options_props_limit(props, attrs, options) {
        const ir_options = session.web_m2x_options;
        if (Number(options.limit) && options.limit > 1) {
            props.searchLimit = Number(options.limit) - 1;
        } else if (
            Number(ir_options["web_m2x_options.limit"]) &&
            ir_options["web_m2x_options.limit"] > 1
        ) {
            props.searchLimit = Number(ir_options["web_m2x_options.limit"]) - 1;
        }
        return props;
    },

    m2m_options_props_search_more(props, attrs, options) {
        const noSearchMore = !evaluateSystemParameterDefaultTrue("search_more");
        if (options.search_more) {
            props.noSearchMore = false;
        } else if ("search_more" in options) {
            props.noSearchMore = true;
        } else if (!noSearchMore && props.noSearchMore) {
            props.noSearchMore = false;
        } else if (noSearchMore) {
            props.noSearchMore = true;
        }
        return props;
    },

    m2m_options_props(props, attrs, options) {
        let newProps = props;
        newProps = this.m2m_options_props_create(newProps, attrs, options);
        newProps = this.m2m_options_props_create_edit(newProps, attrs, options);
        newProps = this.m2m_options_props_limit(newProps, attrs, options);
        newProps = this.m2m_options_props_search_more(newProps, attrs, options);
        newProps.fieldColor = options.field_color;
        newProps.fieldColorOptions = options.colors;
        return newProps;
    },

    extractProps(staticInfo, dynamicInfo) {
        const props = super.extractProps(staticInfo, dynamicInfo);
        const {attrs, options} = staticInfo;
        return this.m2m_options_props(props, attrs, options);
    },
});

patch(Many2XAutocomplete.prototype, {
    async loadOptionsSource(request) {
        const options = await super.loadOptionsSource(request);
        this.field_color = this.props.fieldColor;
        this.colors = this.props.fieldColorOptions;
        if (this.colors && this.field_color) {
            const value_ids = options.map((result) => result.value);
            const objects = await this.orm.call(
                this.props.resModel,
                "search_read",
                [],
                {
                    domain: [["id", "in", value_ids]],
                    fields: [this.field_color],
                }
            );
            for (const index in objects) {
                for (const index_value in options) {
                    if (options[index_value].value === objects[index].id) {
                        const option = options[index_value];
                        const color =
                            this.colors[objects[index][this.field_color]] || "black";
                        option.style = "color:" + color;
                        break;
                    }
                }
            }
        }
        return options;
    },
});

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this._setSubViewLimit();
    },

    async _setSubViewLimit() {
        const ir_options = session.web_m2x_options || {};
        const activeFields = this.archInfo.fieldNodes;
        const isSmall = this.user;

        let limit = ir_options["web_m2x_options.field_limit_entries"];
        if (typeof limit !== "undefined") {
            limit = parseInt(limit, 10);
        }
        for (const fieldName in activeFields) {
            const field = activeFields[fieldName];
            if (!isX2Many(field)) {
                continue;
            }
            if (field.invisible) {
                continue;
            }
            if (!field.field.useSubView) {
                continue;
            }
            let viewType = field.viewMode || "list,kanban";
            viewType = viewType.replace("tree", "list");
            if (viewType.includes(",")) {
                viewType = isSmall ? "kanban" : "list";
            }
            field.viewMode = viewType;
            if (field.views && field.views[viewType] && limit) {
                field.views[viewType].limit = limit;
            }
        }
    },
});

patch(registry.category("fields").validationSchema, {
    m2o_options_props_create: {type: Function, optional: true},
    m2o_options_props_create_edit: {type: Function, optional: true},
    m2o_options_props_limit: {type: Function, optional: true},
    m2o_options_props_search_more: {type: Function, optional: true},
    m2o_options_props_open: {type: Function, optional: true},
    m2o_options_props: {type: Function, optional: true},
    m2m_options_props_create: {type: Function, optional: true},
    m2m_options_props_create_edit: {type: Function, optional: true},
    m2m_options_props_limit: {type: Function, optional: true},
    m2m_options_props_search_more: {type: Function, optional: true},
    m2m_options_props: {type: Function, optional: true},
});
