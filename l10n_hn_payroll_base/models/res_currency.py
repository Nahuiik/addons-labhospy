# -*- coding: utf-8 -*-

import logging

from odoo import _, models, tools

_logger = logging.getLogger(__name__)

try:
    from num2words import num2words
except ImportError:  # pragma: no cover
    _logger.warning(
        "The num2words python library is not installed, amount-to-text features won't be fully available."
    )
    num2words = None


class ResCurrency(models.Model):
    _inherit = "res.currency"

    def amount_to_text(self, amount):
        """Monto en palabras (español) para constancias y reportes."""
        self.ensure_one()

        if num2words is None:
            _logger.warning("The library 'num2words' is missing, cannot render textual amounts.")
            return ""

        def _num2words(value, lang):
            try:
                return num2words(value, lang=lang).title()
            except NotImplementedError:
                return num2words(value, lang="en").title()

        lang = tools.get_lang(self.env)
        integral, _sep, fractional = f"{amount:.{self.decimal_places}f}".partition(".")
        integer_value = int(integral)
        fractional_value = int(fractional or 0)

        amount_words = _(
            "%(amount)s %(currency)s",
            amount=_num2words(integer_value, lang=lang.iso_code),
            currency=self.currency_unit_label,
        )
        if not self.is_zero(amount - integer_value):
            amount_words += " " + _("and") + " " + f"{fractional_value:02d}/100 " + _("centavos")
        return amount_words
