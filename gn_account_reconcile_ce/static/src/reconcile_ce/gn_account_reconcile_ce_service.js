/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { reactive } from "@odoo/owl";

export const gnAccountReconcileCeService = {
    dependencies: ["orm", "notification"],

    start(env, { orm, notification }) {
        const state = reactive({
            journalId: null,
            stLines: [],
            stNextOffset: 0,
            stHasMore: false,
            loadingLines: false,
            loadingCand: false,
            activeStLineId: null,
            activeLinePack: {},
            candidates: [],
            candWindowStart: 0,
            candPageSize: 22,
            selectedCandIndex: 0,
            params: {},
            message: "",
        });

        async function reloadParams() {
            state.params = await orm.call("account.bank.statement.line", "gn_ce_default_params", []);
        }

        async function fetchStatementPage(reset) {
            if (!state.journalId || state.loadingLines) {
                return;
            }
            state.loadingLines = true;
            try {
                const offset = reset ? 0 : state.stNextOffset;
                const res = await orm.call("account.bank.statement.line", "gn_ce_list_unreconciled_lines", [
                    state.journalId,
                    offset,
                    40,
                ]);
                state.stHasMore = res.has_more;
                state.stNextOffset = res.next_offset ?? offset + (res.items || []).length;
                if (reset) {
                    state.stLines = res.items || [];
                } else {
                    state.stLines = [...state.stLines, ...(res.items || [])];
                }
            } finally {
                state.loadingLines = false;
            }
        }

        async function loadJournal(journalId) {
            await reloadParams();
            state.journalId = journalId ? Number(journalId) : null;
            state.stLines = [];
            state.stNextOffset = 0;
            state.stHasMore = false;
            state.activeStLineId = null;
            state.candidates = [];
            state.message = "";
            if (!state.journalId) {
                return;
            }
            await fetchStatementPage(true);
            if (!state.activeStLineId && state.stLines.length) {
                await activateStatement(state.stLines[0].id);
            }
        }

        async function loadMoreStatements() {
            if (!state.stHasMore) {
                return;
            }
            await fetchStatementPage(false);
        }

        async function activateStatement(lineId) {
            state.loadingCand = true;
            try {
                state.activeStLineId = lineId;
                const pack = await orm.call(
                    "account.bank.statement.line",
                    "gn_ce_get_matching_candidates_for_line",
                    [lineId, 96]
                );
                state.activeLinePack = pack.line || {};
                state.candidates = pack.candidates || [];
                state.candWindowStart = 0;
                state.selectedCandIndex = 0;
                state.message = `${state.candidates.length} ${_t("candidatos")}`;
            } finally {
                state.loadingCand = false;
            }
        }

        async function refreshCandidates() {
            if (!state.activeStLineId) {
                return;
            }
            await activateStatement(state.activeStLineId);
        }

        function windowedCandidates() {
            const size = Number(state.candPageSize || 18);
            const start = Number(state.candWindowStart || 0);
            return state.candidates.slice(start, start + size);
        }

        function candidateRowAt(relIndex) {
            const abs = Number(state.candWindowStart || 0) + Number(relIndex || 0);
            return state.candidates[abs];
        }

        async function reconcileFocused() {
            const stId = state.activeStLineId;
            const row = candidateRowAt(state.selectedCandIndex);
            if (!stId || !row) {
                notification.add(_t("Seleccione un candidato de la tabla."), {
                    type: "warning",
                });
                return;
            }
            await orm.call("account.bank.statement.line", "gn_ce_reconcile_line_with_aml", [
                stId,
                row.move_line_id,
            ]);
            notification.add(_t("Conciliación completada."), { type: "success" });
            await loadJournal(state.journalId);
        }

        async function zeroClickActive() {
            if (!state.activeStLineId) {
                return;
            }
            const threshold = Number(state.params.auto_accept_score ?? 93);
            const res = await orm.call("account.bank.statement.line", "gn_ce_try_zero_click", [
                state.activeStLineId,
                threshold,
            ]);
            if (res.applied) {
                notification.add(_t("Conciliación automática aplicada."), { type: "success" });
                await loadJournal(state.journalId);
            } else {
                notification.add(
                    `${_t("Sin candidato suficientemente seguro.")} (${res.best_score ?? "—"})`,
                    { type: "info" }
                );
            }
        }

        function slideCandidateWindow(delta) {
            const size = Number(state.candPageSize || 18);
            const maxStart = Math.max(0, state.candidates.length - size);
            const next = state.candWindowStart + delta * size;
            state.candWindowStart = Math.max(0, Math.min(next, maxStart));
            state.selectedCandIndex = 0;
        }

        function moveStatementSelection(delta) {
            const ix = state.stLines.findIndex((l) => l.id === state.activeStLineId);
            const nx = ix + delta;
            if (nx >= 0 && nx < state.stLines.length) {
                void activateStatement(state.stLines[nx].id);
            }
        }

        function sliceStatementsViewport(scrollTop, rowHeight = 34) {
            const start = Math.max(0, Math.floor(scrollTop / rowHeight));
            const viewportRows = Math.ceil(820 / rowHeight);
            const end = Math.min(state.stLines.length, start + viewportRows + 14);
            return {
                slice: state.stLines.slice(start, end),
                paddingTop: start * rowHeight,
                paddingBottom: Math.max(0, (state.stLines.length - end) * rowHeight),
            };
        }

        function attachKeyboard(rootEl) {
            const onKey = (ev) => {
                const tgt = ev.target?.tagName;
                if (tgt === "INPUT" || tgt === "TEXTAREA" || tgt === "SELECT") {
                    return;
                }
                if (!state.journalId) {
                    return;
                }
                switch (ev.key) {
                    case "ArrowDown":
                        moveStatementSelection(1);
                        ev.preventDefault();
                        break;
                    case "ArrowUp":
                        moveStatementSelection(-1);
                        ev.preventDefault();
                        break;
                    case "Enter":
                        void reconcileFocused();
                        ev.preventDefault();
                        break;
                    case "ArrowRight":
                        state.selectedCandIndex = Math.min(
                            windowedCandidates().length - 1,
                            state.selectedCandIndex + 1
                        );
                        ev.preventDefault();
                        break;
                    case "ArrowLeft":
                        state.selectedCandIndex = Math.max(0, state.selectedCandIndex - 1);
                        ev.preventDefault();
                        break;
                    case "[":
                        slideCandidateWindow(-1);
                        ev.preventDefault();
                        break;
                    case "]":
                        slideCandidateWindow(1);
                        ev.preventDefault();
                        break;
                    case "r":
                    case "R":
                        void refreshCandidates();
                        ev.preventDefault();
                        break;
                    case "a":
                    case "A":
                        void zeroClickActive();
                        ev.preventDefault();
                        break;
                }
            };
            rootEl?.addEventListener("keydown", onKey);
            return () => rootEl?.removeEventListener("keydown", onKey);
        }

        return {
            state,
            loadJournal,
            loadMoreStatements,
            activateStatement,
            refreshCandidates,
            reconcileFocused,
            zeroClickActive,
            attachKeyboard,
            sliceStatementsViewport,
            windowedCandidates,
            slideCandidateWindow,
        };
    },
};

registry.category("services").add("gn_account_reconcile_ce", gnAccountReconcileCeService);
