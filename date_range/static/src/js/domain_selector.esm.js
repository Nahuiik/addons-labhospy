import {domainFromTreeDateRange, treeFromDomainDateRange} from "./condition_tree.esm";
import {onWillStart, useChildSubEnv} from "@odoo/owl";
import {Domain} from "@web/core/domain";
import {DomainSelector} from "@web/core/domain_selector/domain_selector";
import {patch} from "@web/core/utils/patch";
import {treeFromDomain} from "@web/core/tree_editor/tree_from_domain";
import {useService} from "@web/core/utils/hooks";

const ARCHIVED_DOMAIN = `[("active", "in", [True, False])]`;

patch(DomainSelector.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.dateRanges = [];
        this.dateRangeTypes = [];
        useChildSubEnv({domain: this});
        onWillStart(async () => {
            this.dateRanges = await this.orm.call("date.range", "search_read", []);
            this.dateRangeTypes = await this.orm.call(
                "date.range.type",
                "search_read",
                []
            );
        });
    },

    async onPropsUpdated(p) {
        await super.onPropsUpdated.apply(this, arguments);
        let domain = null;
        let isSupported = true;
        try {
            domain = new Domain(p.domain);
        } catch {
            isSupported = false;
        }
        if (!isSupported) {
            this.tree = null;
            this.defaultCondition = null;
            this.fieldDefs = {};
            this.showArchivedCheckbox = false;
            this.includeArchived = false;
            return;
        }

        const tree = treeFromDomain(domain);
        let getFieldDef;
        if (this.treeProcessor && this.treeProcessor.makeGetFieldDef) {
            const baseGetFieldDef = await this.treeProcessor.makeGetFieldDef(
                p.resModel,
                tree
            );
            getFieldDef = (path) =>
                ["active"].includes(path) ? null : baseGetFieldDef(path);
        } else {
            const fieldDefs = {};
            const paths = new Set();
            (function collectPaths(node) {
                if (!node) {
                    return;
                }
                if (node.type === "condition" && typeof node.path === "string") {
                    paths.add(node.path);
                }
                if (node.children) {
                    node.children.forEach(collectPaths);
                }
                if (typeof node.value === "object" && node.value && node.value.type) {
                    collectPaths(node.value);
                }
            })(tree);
            paths.delete("active");
            const promises = [];
            for (const path of paths) {
                promises.push(
                    this.fieldService
                        .loadFieldInfo(p.resModel, path)
                        .then(({fieldDef}) => {
                            fieldDefs[path] = fieldDef;
                        })
                );
            }
            await Promise.all(promises);
            getFieldDef = (path) => fieldDefs[path] || null;
        }

        this.tree = treeFromDomainDateRange(domain, {
            getFieldDef: getFieldDef,
            distributeNot: !p.isDebugMode,
        });
    },
    getOperatorEditorInfo(fieldDef) {
        const info = super.getOperatorEditorInfo(fieldDef);
        const dateRanges = this.dateRanges;
        const dateRangeTypes = this.dateRangeTypes.filter((dt) => dt.date_ranges_exist);
        patch(info, {
            extractProps({value: [operator]}) {
                const props = super.extractProps.apply(this, arguments);
                const isDateField =
                    fieldDef &&
                    (fieldDef.type === "date" || fieldDef.type === "datetime");
                const hasDateRanges = isDateField && dateRanges.length;
                const hasDateRangeTypes = isDateField && dateRangeTypes.length;

                if (hasDateRanges) {
                    if (operator.includes("daterange")) {
                        props.options.pop();
                    }
                    if (operator === "daterange") {
                        props.value = "daterange";
                    }
                    props.options.push(["daterange", "daterange"]);
                }

                if (hasDateRangeTypes) {
                    const selectedDateRange = dateRangeTypes.find(
                        (rangeType) =>
                            rangeType.id === Number(operator.split("daterange_")[1])
                    );

                    if (selectedDateRange) {
                        props.value = operator;
                    }

                    props.options.push(
                        ...dateRangeTypes.map((rangeType) => [
                            `daterange_${rangeType.id}`,
                            `in ${rangeType.name}`,
                        ])
                    );
                }

                return props;
            },
        });
        return info;
    },
    update(tree) {
        const archiveDomain = this.includeArchived ? ARCHIVED_DOMAIN : `[]`;
        const domain = tree
            ? Domain.and([domainFromTreeDateRange(tree), archiveDomain]).toString()
            : archiveDomain;
        this.props.update(domain);
    },
});
