# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.tools import html_escape


class GnAuditMixin(models.AbstractModel):
    """Helpers de formato de cambios reutilizados por los modelos auditados.

    Las variables se escapan con html_escape; las etiquetas HTML (<strong>…)
    son literales controladas, por lo que el resultado es seguro para incrustar
    como HTML una vez envuelto en markupsafe.Markup por gn.audit.log.
    """

    _name = "gn.audit.mixin"
    _description = "Auditoría: helpers de formato"

    def _gn_audit_field_label(self, field_name):
        field = self._fields.get(field_name)
        return field.string if field and field.string else field_name

    def _gn_audit_format_value(self, field_name, value):
        # `is`/`== ""` evita confundir el entero 0 (p. ej. padding) con vacío.
        if value is False or value is None or value == "":
            return _("(vacío)")
        field = self._fields.get(field_name)
        ftype = field.type if field else "char"
        if ftype == "many2one":
            return value.display_name or _("(vacío)")
        if ftype in ("one2many", "many2many"):
            return ", ".join(value.mapped("display_name")) or _("(vacío)")
        if ftype == "selection":
            return dict(field._description_selection(self.env)).get(value, value)
        if ftype == "boolean":
            return _("Sí") if value else _("No")
        return str(value)

    def _gn_audit_change_line(self, field_name, old, new):
        return "%s: %s → <strong>%s</strong>" % (
            html_escape(self._gn_audit_field_label(field_name)),
            html_escape(self._gn_audit_format_value(field_name, old)),
            html_escape(self._gn_audit_format_value(field_name, new)),
        )

    def _gn_audit_value_line(self, field_name, value):
        return "%s: <strong>%s</strong>" % (
            html_escape(self._gn_audit_field_label(field_name)),
            html_escape(self._gn_audit_format_value(field_name, value)),
        )

    def _gn_audit_changed_fields(self, before, tracked):
        """Devuelve las líneas HTML de los campos que cambiaron (self vs before)."""
        self.ensure_one()
        lines = []
        for fname in tracked:
            old = before.get(fname)
            new = self[fname]
            if self._fields[fname].type == "many2one":
                if (old.id if old else False) == (new.id if new else False):
                    continue
            elif old == new:
                continue
            lines.append(self._gn_audit_change_line(fname, old, new))
        return lines
