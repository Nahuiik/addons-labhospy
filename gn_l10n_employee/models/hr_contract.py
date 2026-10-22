from datetime import date, datetime

import pytz
from babel.dates import format_date

from odoo import _, api, fields, models
from odoo.exceptions import UserError

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - dependency missing warning is handled at runtime
    BeautifulSoup = None


class Company(models.Model):
    _inherit = "res.company"

    header_memb = fields.Boolean(string='Papel Membretado')


class HrContract(models.Model):
    _inherit = 'hr.contract'

    wage_in_words = fields.Char(compute='amount_word', string='Salario en Letras')
    date_start_text = fields.Char(string="Fecha en Letras", compute='_compute_date_start_text')
    date_end_text = fields.Char(string="Fecha en Letras", compute='_compute_date_end_text')
    afp_atlantida_amount = fields.Float(string="AFP ATLANTIDA", compute='_compute_afp_atlantida_amount')

    def _ensure_signature_dependencies(self):
        if BeautifulSoup is None:
            raise UserError(_('No se puede validar la firma: instale la librería python "bs4".'))

    def _check_signature_requirements(self):
        for contract in self:
            contract_name = contract.name or ''
            if not contract.hr_responsible_id:
                raise UserError(_('No se puede imprimir la constancia de trabajo para el contrato "%s": no tiene un responsable asignado.') % contract_name)

            signature_html = contract.hr_responsible_id.signature or ''
            soup = BeautifulSoup(signature_html, 'html.parser')
            text_content = soup.get_text(strip=True)
            if not text_content:
                raise UserError(_('No se puede imprimir la constancia de trabajo para el contrato "%s": el responsable no tiene asignada una firma.') % contract_name)

            if not contract.employee_id:
                raise UserError(_('No se puede imprimir la constancia de trabajo para el contrato "%s": no tiene un empleado asignado.') % contract_name)
            if not contract.job_id:
                raise UserError(_('No se puede imprimir la constancia de trabajo para el contrato "%s": no tiene un cargo asignado.') % contract_name)
            if not contract.date_start:
                raise UserError(_('No se puede imprimir la constancia de trabajo para el contrato "%s": no tiene una fecha de inicio asignada.') % contract_name)
            if not contract.wage:
                raise UserError(_('No se puede imprimir la constancia de trabajo para el contrato "%s": no tiene un salario asignado.') % contract_name)

    def action_print_employee_declaration(self):
        self._ensure_signature_dependencies()
        self._check_signature_requirements()
        return self.env.ref('gn_l10n_employee.action_report_employee_declaration').report_action(self)

    def action_print_employee_cancelled_declaration(self):
        self._ensure_signature_dependencies()
        self._check_signature_requirements()
        return self.env.ref('gn_l10n_employee.action_report_employee_cancelled_declaration').report_action(self)

    def _get_report_base_filename(self):
        self.ensure_one()
        return 'CONSTANCIA %s' % (self.employee_id.name if self.employee_id else 'Empleado')

    @api.depends('wage', 'currency_id')
    def amount_word(self):
        for contract in self:
            if contract.currency_id and contract.wage:
                contract.wage_in_words = contract.currency_id.amount_to_text(contract.wage).upper()
            else:
                contract.wage_in_words = ''

    @api.depends('allowences_ids.name', 'allowences_ids.amount_fee', 'allowences_ids.end_date')
    def _compute_afp_atlantida_amount(self):
        today = date.today()
        for contract in self:
            amount = 0.0
            for line in contract.allowences_ids:
                concept = line.name
                if concept and concept.name == "AFP ATLANTIDA":
                    if not line.end_date or line.end_date >= today:
                        amount = line.amount_fee or 0.0
                    break
            contract.afp_atlantida_amount = amount

    @api.depends('date_start')
    def _compute_date_start_text(self):
        for contract in self:
            if contract.date_start:
                contract.date_start_text = format_date(contract.date_start, "d 'de' MMMM 'de' y", locale='es_ES')
            else:
                contract.date_start_text = ''

    @api.depends('date_end')
    def _compute_date_end_text(self):
        for contract in self:
            if contract.date_end:
                contract.date_end_text = format_date(contract.date_end, "d 'de' MMMM 'de' y", locale='es_ES')
            else:
                contract.date_end_text = ''

    def get_today_in_words(self):
        tz_honduras = pytz.timezone('America/Tegucigalpa')
        today = datetime.now(tz_honduras)
        return format_date(today, "d 'del mes de' MMMM 'del año' y", locale='es_ES')
