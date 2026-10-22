# -*- coding: utf-8 -*-
"""Pipeline de ranking para conciliación bancaria (CE), sin código Enterprise."""

from __future__ import annotations

import difflib
import logging

_logger = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz as rapid_fuzz_mod
except ImportError:  # pragma: no cover
    rapid_fuzz_mod = None


def fuzzy_ratio(left: str, right: str) -> float:
    l = (left or '').strip().lower()
    r = (right or '').strip().lower()
    if not l or not r:
        return 0.0
    if rapid_fuzz_mod:
        try:
            return float(rapid_fuzz_mod.token_set_ratio(l, r))
        except Exception:  # noqa: BLE001
            _logger.debug('rapidfuzz.token_set_ratio fallback', exc_info=True)
    return round(difflib.SequenceMatcher(a=l, b=r).ratio() * 100.0, 4)


class GnCeMatchingScorer:
    """Calcula puntajes individuales y compuesto ponderado."""

    WEIGHT_EXACT_AMOUNT = 0.13
    WEIGHT_RESIDUAL_TOL = 0.17
    WEIGHT_PARTNER = 0.18
    WEIGHT_REFERENCE = 0.15
    WEIGHT_LABEL_FUZZ = 0.21
    WEIGHT_DATE = 0.16

    def __init__(self, currency, tolerance_amount: float):
        self.currency = currency
        self.tolerance_amount = float(tolerance_amount or 0.0)

    def score_exact_amount(self, st_residual: float, aml_residual: float) -> float:
        diff = abs(float(st_residual or 0.0) - float(aml_residual or 0.0))
        return 100.0 if self.currency.is_zero(diff) else 0.0

    def score_residual_tolerance(self, st_residual: float, aml_residual: float) -> float:
        diff = abs(float(st_residual or 0.0) - float(aml_residual or 0.0))
        if self.currency.is_zero(diff):
            return 100.0
        tol = abs(self.tolerance_amount)
        if tol and diff <= tol:
            return max(50.0, 100.0 - (diff / tol * 50.0))
        rel = diff / max(abs(float(st_residual)) or abs(float(aml_residual)) or 1.0, 1e-9)
        return max(0.0, 100.0 - min(rel, 10.0) * 12.5)

    def score_partner_hint(self, st_partner_id: int | bool, aml_partner_id: int | bool) -> float:
        if not st_partner_id:
            return 75.0
        if aml_partner_id and aml_partner_id == st_partner_id:
            return 100.0
        if aml_partner_id:
            return 22.0
        return 45.0

    def score_reference(self, blobs: list[str], ref: str, move_display: str) -> float:
        pieces = [(ref or '').strip(), (move_display or '').strip()]
        corpus = [
            '|'.join(pieces).strip().lower(),
            (pieces[0] or pieces[1]).lower(),
        ]
        best = 0.0
        flat_blob = '|'.join([b or '' for b in blobs]).lower().strip()
        for c in corpus:
            if not c:
                continue
            for b in blobs:
                if not (b or '').strip():
                    continue
                best = max(best, fuzzy_ratio(b, c))
            if flat_blob:
                best = max(best, fuzzy_ratio(flat_blob, c))
        return min(100.0, best)

    def score_date_proximity(self, st_date, aml_date, max_days_band: float = 120.0) -> float:
        if not st_date or not aml_date:
            return 45.0
        delta = abs((st_date - aml_date).days)
        band = max(3.0, float(max_days_band))
        linear = delta / band
        return float(max(0.0, 100.0 * (1 - min(linear, 1.0))))

    def compose(
        self,
        *,
        st_partner_id,
        st_amount_residual,
        st_date,
        st_blobs,
        aml,
        amount_compare_field: str = 'amount_residual',
    ):
        amt_compare = aml[amount_compare_field]
        amt_exact_score = self.score_exact_amount(st_amount_residual, amt_compare)
        amt_tol_score = self.score_residual_tolerance(st_amount_residual, amt_compare)

        aml_pid = aml['partner_id'][0] if aml.get('partner_id') else False
        part_score = self.score_partner_hint(st_partner_id, aml_pid)

        blobs = list(st_blobs)
        aml_label = aml.get('name') or ''

        label_fuzz_score = fuzzy_ratio('|'.join([b or '' for b in blobs]), aml_label)

        move_display = ''
        mid = aml.get('move_id')
        if isinstance(mid, (list, tuple)) and len(mid) > 1 and mid[1]:
            move_display = str(mid[1])

        ref_score = self.score_reference(blobs, str(aml.get('ref') or ''), move_display)

        aml_date_val = aml.get('date')

        date_score = self.score_date_proximity(st_date, aml_date_val)

        composite = (
            amt_exact_score * self.WEIGHT_EXACT_AMOUNT
            + amt_tol_score * self.WEIGHT_RESIDUAL_TOL
            + part_score * self.WEIGHT_PARTNER
            + ref_score * self.WEIGHT_REFERENCE
            + label_fuzz_score * self.WEIGHT_LABEL_FUZZ
            + date_score * self.WEIGHT_DATE
        )

        detail = {
            'exact_amount': round(amt_exact_score, 4),
            'residual_tolerance': round(amt_tol_score, 4),
            'exact_partner': round(part_score, 4),
            'reference_similarity': round(ref_score, 4),
            'fuzzy_label': round(label_fuzz_score, 4),
            'date_proximity': round(date_score, 4),
            'composite': round(composite, 6),
        }
        return composite, detail
