# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models


class L10nHnPayrollAuditRun(models.Model):
    _name = 'l10n.hn.payroll.audit.run'
    _description = 'Proceso de Auditoría de Nómina Honduras'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period_year desc, period_month desc, id desc'

    audit_type = fields.Selection(
        [
            ('monthly', 'Mensual'),
            ('annual', 'Anual'),
        ],
        string='Tipo de auditoría',
        required=True,
        tracking=True,
    )
    period_month = fields.Integer(
        string='Mes',
        help='Mes del período (1-12). Para auditoría anual puede ser 0.',
    )
    period_year = fields.Integer(
        string='Año',
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    state = fields.Selection(
        [
            ('pending', 'Pendiente'),
            ('in_progress', 'En progreso'),
            ('completed', 'Completada'),
        ],
        string='Estado',
        default='pending',
        required=True,
        tracking=True,
    )
    assigned_to = fields.Many2one(
        comodel_name='res.users',
        string='Asignado a',
        tracking=True,
        domain=[('active', '=', True)],
    )
    item_ids = fields.One2many(
        comodel_name='l10n.hn.payroll.audit.item',
        inverse_name='audit_run_id',
        string='Items de auditoría',
    )
    notes = fields.Text(
        string='Notas',
        tracking=True,
    )
    date_completed = fields.Datetime(
        string='Fecha de completado',
        readonly=True,
    )

    def action_start(self):
        self.ensure_one()
        self.state = 'in_progress'

    def action_complete(self):
        self.ensure_one()
        self.write({
            'state': 'completed',
            'date_completed': fields.Datetime.now(),
        })
        self.activity_unlink(['l10n_hn_hr_payroll.mail_activity_payroll_audit'])

    def _create_activity_for_auditor(self):
        """Crea actividad asignada al auditor o a usuarios del grupo auditor."""
        activity_type = self.env.ref(
            'l10n_hn_hr_payroll.mail_activity_type_payroll_audit',
            raise_if_not_found=False,
        )
        if not activity_type:
            return
        auditor_group = self.env.ref(
            'l10n_hn_hr_payroll.group_hr_payroll_auditor',
            raise_if_not_found=False,
        )
        for run in self:
            user_ids = []
            if run.assigned_to:
                user_ids = [run.assigned_to.id]
            else:
                company = run.company_id
                # 1. Usuarios configurados en hr.notification.recipient para payroll_audit
                user_ids = self.env['hr.notification.recipient'].get_recipient_user_ids(
                    company.id, 'payroll_audit')
                # 2. payroll_auditor_ids de la compañía
                if not user_ids and hasattr(company, 'payroll_auditor_ids') and company.payroll_auditor_ids:
                    user_ids = company.payroll_auditor_ids.ids
                # 3. Grupo auditor (Odoo 19: user_ids / all_user_ids, no "users")
                if not user_ids and auditor_group:
                    user_ids = auditor_group.all_user_ids.filtered('active').ids
            if user_ids:
                self.env['mail.activity'].create({
                    'activity_type_id': activity_type.id,
                    'res_model_id': self.env['ir.model']._get(run._name).id,
                    'res_id': run.id,
                    'user_id': user_ids[0],
                    'summary': f'Auditoría {run.audit_type} - {run.period_year}',
                })

    @api.model
    def _cron_create_monthly_audits(self):
        """Crea auditorías mensuales para el mes anterior. Ejecutado el día 1 de cada mes."""
        from datetime import date
        today = date.today()
        prev_month = today.month - 1 if today.month > 1 else 12
        prev_year = today.year if today.month > 1 else today.year - 1
        return self._create_audit_runs('monthly', prev_month, prev_year)

    @api.model
    def _cron_create_annual_audits(self):
        """Crea auditorías anuales para el año anterior. Ejecutado el 1 de enero."""
        from datetime import date
        today = date.today()
        prev_year = today.year - 1
        return self._create_audit_runs('annual', 0, prev_year)

    @api.model
    def _create_audit_runs(self, audit_type, period_month, period_year):
        """Crea registros de auditoría por compañía activa."""
        companies = self.env['res.company'].search([('active', '=', True)])
        runs = self.env['l10n.hn.payroll.audit.run']
        item_model = self.env['l10n.hn.payroll.audit.item']
        default_items = item_model.search([
            ('audit_type', '=', audit_type),
            ('audit_run_id', '=', False),
        ], order='sequence')
        for company in companies:
            existing = self.search([
                ('company_id', '=', company.id),
                ('audit_type', '=', audit_type),
                ('period_year', '=', period_year),
                ('period_month', '=', period_month),
            ], limit=1)
            if existing:
                continue
            run = self.create({
                'audit_type': audit_type,
                'period_month': period_month,
                'period_year': period_year,
                'company_id': company.id,
            })
            # Copiar items por defecto
            for item in default_items:
                item_model.create({
                    'audit_run_id': run.id,
                    'name': item.name,
                    'sequence': item.sequence,
                    'action_id': item.action_id.id if item.action_id else False,
                })
            run._create_activity_for_auditor()
            runs |= run
        return runs
