# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools.misc import formatLang
from odoo.addons.l10n_hn_reports.models.report_branding import company_report_branding


def _format_date_dmy(value):
    """Fecha para informes: día/mes/año."""
    if value is False or value is None:
        return ''
    if isinstance(value, str):
        try:
            value = fields.Date.from_string(value)
        except (ValueError, TypeError):
            return value
    try:
        return value.strftime('%d/%m/%Y')
    except (AttributeError, TypeError):
        return str(value)


def _format_amount_locale(env, value, digits=2):
    """Montos con agrupación de millares según configuración regional del usuario/compañía."""
    return formatLang(env, float(value or 0.0), grouping=True, digits=digits)


class ReportLibroDiario(models.AbstractModel):
    _name = 'report.l10n_hn_legal_books.report_libro_diario'
    _description = 'Libro Diario QWeb'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['hn.libro.diario.wizard'].browse(docids)
        doc = docs[:1]
        raw_rows = doc._collect_rows() if doc else []
        rows = []
        for r in raw_rows:
            rows.append({
                **r,
                'fecha_fmt': _format_date_dmy(r['fecha']),
                'debe_fmt': _format_amount_locale(self.env, r['debe'], 2),
                'haber_fmt': _format_amount_locale(self.env, r['haber'], 2),
            })
        t_deb = sum(float(r['debe']) for r in raw_rows)
        t_cre = sum(float(r['haber']) for r in raw_rows)
        vals = {
            'doc_ids': docids,
            'doc_model': 'hn.libro.diario.wizard',
            'docs': docs,
            'rows': rows,
            'total_debe': t_deb,
            'total_haber': t_cre,
            'total_debe_fmt': _format_amount_locale(self.env, t_deb, 2),
            'total_haber_fmt': _format_amount_locale(self.env, t_cre, 2),
        }
        if doc:
            vals['date_from_fmt'] = _format_date_dmy(doc.date_from)
            vals['date_to_fmt'] = _format_date_dmy(doc.date_to)
        else:
            vals['date_from_fmt'] = vals['date_to_fmt'] = ''
        vals.update(company_report_branding(doc.company_id if doc else self.env.company))
        return vals


class ReportLibroMayor(models.AbstractModel):
    _name = 'report.l10n_hn_legal_books.report_libro_mayor'
    _description = 'Libro Mayor QWeb'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['hn.libro.mayor.wizard'].browse(docids)
        doc = docs[:1]
        sections = doc._collect_sections() if doc else []
        enriched = []
        for sec in sections:
            run = sec['opening']
            line_data = []
            for line in sec['lines']:
                run += line.balance
                line_data.append({
                    'line': line,
                    'run': run,
                    'fecha_fmt': _format_date_dmy(line.date),
                    'debe_fmt': _format_amount_locale(self.env, line.debit, 2),
                    'haber_fmt': _format_amount_locale(self.env, line.credit, 2),
                    'run_fmt': _format_amount_locale(self.env, run, 2),
                })
            enriched.append({
                **sec,
                'opening_fmt': _format_amount_locale(self.env, sec['opening'], 2),
                'closing_fmt': _format_amount_locale(self.env, sec['closing'], 2),
                'movement_debit_fmt': _format_amount_locale(self.env, sec['movement_debit'], 2),
                'movement_credit_fmt': _format_amount_locale(self.env, sec['movement_credit'], 2),
                'line_data': line_data,
            })
        vals = {
            'doc_ids': docids,
            'doc_model': 'hn.libro.mayor.wizard',
            'docs': docs,
            'sections': enriched,
        }
        if doc:
            vals['date_from_fmt'] = _format_date_dmy(doc.date_from)
            vals['date_to_fmt'] = _format_date_dmy(doc.date_to)
        else:
            vals['date_from_fmt'] = vals['date_to_fmt'] = ''
        vals.update(company_report_branding(doc.company_id if doc else self.env.company))
        return vals


class ReportLibroInventarios(models.AbstractModel):
    _name = 'report.l10n_hn_legal_books.report_libro_inventarios'
    _description = 'Libro Inventarios y Balances QWeb'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['hn.libro.inventarios.balances.wizard'].browse(docids)
        doc = docs[:1]
        balance_rows = doc._collect_balance_rows() if doc else []
        stock_rows = doc._collect_stock_rows() if doc else []
        balance_display = []
        td = tc = 0.0
        for br in balance_rows:
            td += br['debit']
            tc += br['credit']
            balance_display.append({
                **br,
                'debit_fmt': _format_amount_locale(self.env, br['debit'], 2),
                'credit_fmt': _format_amount_locale(self.env, br['credit'], 2),
                'balance_fmt': _format_amount_locale(self.env, br['balance'], 2),
            })
        stock_display = []
        for sr in stock_rows:
            stock_display.append({
                **sr,
                'qty_fmt': _format_amount_locale(self.env, sr['qty'], 4),
            })
        total_saldo = td - tc
        vals = {
            'doc_ids': docids,
            'doc_model': 'hn.libro.inventarios.balances.wizard',
            'docs': docs,
            'balance_rows': balance_display,
            'stock_rows': stock_display,
            'total_debe': td,
            'total_haber': tc,
            'total_saldo': total_saldo,
            'total_debe_fmt': _format_amount_locale(self.env, td, 2),
            'total_haber_fmt': _format_amount_locale(self.env, tc, 2),
            'total_saldo_fmt': _format_amount_locale(self.env, total_saldo, 2),
        }
        if doc:
            vals['date_to_fmt'] = _format_date_dmy(doc.date_to)
        else:
            vals['date_to_fmt'] = ''
        vals.update(company_report_branding(doc.company_id if doc else self.env.company))
        return vals
