# -*- coding: utf-8 -*-
from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class BankProvision(models.Model):
    _name = 'bank.provision'
    _description = 'Provisiones contables y ajustes por diferencial cambiario'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'gn.banks.document.journal.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', default='/', copy=False, tracking=True, readonly=True)
    dummy_name = fields.Char(string='Vista previa número', compute='_compute_sequence_preview')
    error_msg = fields.Char(string='Error secuencia', compute='_compute_sequence_preview')

    provision_kind = fields.Selection(
        [
            ('accrual', 'Devengo / provisión'),
            ('fx_differential', 'Diferencial cambiario'),
        ],
        string='Tipo de registro',
        default='accrual',
        required=True,
        tracking=True,
        help='Devengo: asiento genérico en diario misceláneo. Diferencial cambiario: ajuste habitualmente '
             'entre la cuenta de liquidez del banco y las cuentas de resultado por diferencial (compañía).',
    )

    description = fields.Text(string='Descripción', required=True, tracking=True)
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        required=True,
        domain="[('company_id', '=', company_id), '|', ('type', '=', 'bank'), ('type', '=', 'general')]",
        check_company=True,
        tracking=True,
    )
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today, tracking=True)
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True,
    )
    state = fields.Selection(
        [('draft', 'Borrador'), ('validated', 'Validado'), ('cancel', 'Cancelado')],
        string='Estado',
        default='draft',
        copy=False,
        tracking=True,
    )
    move_id = fields.Many2one('account.move', string='Asiento contable', copy=False, readonly=True, check_company=True)
    line_ids = fields.One2many('bank.provision.line', 'provision_id', string='Líneas', copy=True)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        company = self.env.company
        if vals.get('company_id'):
            company = self.env['res.company'].browse(vals['company_id'])
        kind = vals.get('provision_kind', 'accrual')
        if (
            kind == 'accrual'
            and 'journal_id' in fields_list
            and not vals.get('journal_id')
            and company
        ):
            j = self._get_company_accrual_provision_journal(company)
            if j:
                vals['journal_id'] = j.id
        return vals

    @api.model
    def _get_company_fx_differential_journal(self, company):
        """Único diario permitido para «Diferencial cambiario»: config. compañía o nombre estándar."""
        if not company:
            return self.env['account.journal']
        configured = company.banks_fx_differential_journal_id
        if configured and configured.company_id == company:
            return configured
        target = 'diferencia de cambio'
        Journal = self.env['account.journal']
        candidates = Journal.search([
            ('company_id', '=', company.id),
            ('type', 'in', ('bank', 'general')),
        ])
        for journal in candidates:
            if (journal.name or '').strip().lower() == target:
                return journal
        return Journal

    def _resolve_fx_differential_journal(self):
        self.ensure_one()
        return self.env['bank.provision']._get_company_fx_differential_journal(self.company_id)

    @api.model
    def _get_company_accrual_provision_journal(self, company):
        """Diario misceláneo recomendado para devengo (solo valor por defecto, el usuario puede cambiar)."""
        if not company:
            return self.env['account.journal']
        configured = company.banks_accrual_provision_journal_id
        if configured and configured.company_id == company and configured.type == 'general':
            return configured
        target = 'provisiones'
        Journal = self.env['account.journal']
        candidates = Journal.search([
            ('company_id', '=', company.id),
            ('type', '=', 'general'),
        ])
        for journal in candidates:
            if (journal.name or '').strip().lower() == target:
                return journal
        return Journal

    def _resolve_accrual_default_journal(self):
        self.ensure_one()
        return self.env['bank.provision']._get_company_accrual_provision_journal(self.company_id)

    def _sequence_move_type(self):
        """Kind of ir.sequence.move_type tied to this document."""
        self.ensure_one()
        return 'fx_differential' if self.provision_kind == 'fx_differential' else 'provision'

    def _sequence_kind_label(self):
        self.ensure_one()
        return _('Diferencial cambiario') if self.provision_kind == 'fx_differential' else _('Provisiones')

    def _get_sequence(self):
        self.ensure_one()
        return self.env['ir.sequence'].search([
            ('move_type', '=', self._sequence_move_type()),
            ('journal_id', '=', self.journal_id.id),
        ], limit=1)

    @api.depends('journal_id', 'provision_kind', 'company_id')
    def _compute_sequence_preview(self):
        for rec in self:
            rec.dummy_name = False
            rec.error_msg = False
            if not rec.journal_id:
                continue
            seq = rec._get_sequence()
            if not seq:
                rec.error_msg = _(
                    'No hay secuencia para tipo «%s» en el diario «%s». '
                    'Configure una en el diario (pestaña de secuencias) o con el asistente de secuencias.',
                    rec._sequence_kind_label(),
                    rec.journal_id.display_name,
                )
            else:
                rec.dummy_name = seq.get_next_char(seq.number_next_actual)

    @api.constrains('journal_id', 'provision_kind', 'company_id')
    def _check_journal_matches_provision_kind(self):
        for rec in self:
            if rec.provision_kind == 'accrual':
                if rec.journal_id and rec.journal_id.type != 'general':
                    raise ValidationError(
                        _('Las provisiones tipo «Devengo» solo permiten diario misceláneo (tipo general).')
                    )
            elif rec.provision_kind == 'fx_differential':
                fx = rec.env['bank.provision']._get_company_fx_differential_journal(rec.company_id)
                if not fx:
                    raise ValidationError(
                        _('No hay diario configurado para diferencial cambiario en «%s». '
                          'Defina «Diario diferencial cambiario (provisiones)» en la ficha de la compañía '
                          'o cree un diario llamado «Diferencia de cambio».')
                        % (rec.company_id.display_name,)
                    )
                if rec.journal_id and rec.journal_id != fx:
                    raise ValidationError(
                        _('Para diferencial cambiario debe usarse únicamente el diario «%s».')
                        % (fx.display_name,)
                    )
                if rec.journal_id and rec.journal_id.type not in ('bank', 'general'):
                    raise ValidationError(
                        _('El diferencial cambiario permite solo diarios banco o misceláneo (general).')
                    )

    @api.onchange('provision_kind')
    def _onchange_provision_kind(self):
        """Diario incompatible al cambiar de tipo; devengo sugiere diario Provisiones (cambiable)."""
        self.ensure_one()
        if self.journal_id and self.provision_kind == 'accrual' and self.journal_id.type != 'general':
            self.journal_id = False

        if self.provision_kind == 'accrual':
            fx_journal = self.env['bank.provision']._get_company_fx_differential_journal(self.company_id)
            defj = self._resolve_accrual_default_journal()
            if defj:
                if not self.journal_id or self.journal_id.type != 'general':
                    self.journal_id = defj.id
                elif fx_journal and self.journal_id == fx_journal:
                    self.journal_id = defj.id
        elif self.provision_kind == 'fx_differential':
            fx = self._resolve_fx_differential_journal()
            self.journal_id = fx.id if fx else False
            hint = _('Diferencial cambiario — liquidez banco y cuenta de resultado cambiario (compañía).')
            if not (self.description or '').strip():
                self.description = hint
        return self._journal_domain_ret()

    @api.onchange('company_id')
    def _onchange_company_id_journal_domain(self):
        if not self.company_id:
            return self._journal_domain_ret()
        if self.provision_kind == 'fx_differential':
            fx = self._resolve_fx_differential_journal()
            self.journal_id = fx.id if fx else False
        elif self.provision_kind == 'accrual':
            if not self.journal_id or self.journal_id.company_id != self.company_id:
                defj = self._resolve_accrual_default_journal()
                self.journal_id = defj.id if defj else False
        return self._journal_domain_ret()

    def _journal_domain_ret(self):
        self.ensure_one()
        if self.provision_kind == 'fx_differential':
            fx = self._resolve_fx_differential_journal()
            if fx:
                return {'domain': {'journal_id': [('id', '=', fx.id)]}}
            return {'domain': {'journal_id': [('id', 'in', [])]}}

        dom = [('company_id', '=', self.company_id.id), ('type', 'in', ('bank', 'general'))]
        if self.provision_kind == 'accrual':
            dom = [('company_id', '=', self.company_id.id), ('type', '=', 'general')]
        return {'domain': {'journal_id': dom}}

    @api.onchange('journal_id')
    def _onchange_journal_id_sequence(self):
        self._compute_sequence_preview()
        ret = self._journal_domain_ret()
        if self.journal_id and self.provision_kind == 'accrual' and self.journal_id.type == 'bank':
            ret.setdefault('warning', {})
            ret['warning'] = {
                'title': _('Diario incompatible'),
                'message': _('El tipo «Devengo» requiere un diario misceláneo (general), no banco.'),
            }
        return ret

    def action_load_fx_template_lines(self):
        """Dos líneas en cero: liquidez del diario banco y cuenta puente cambiaria (gastos o ingresos)."""
        BankLine = self.env['bank.provision.line']
        for rec in self:
            if rec.provision_kind != 'fx_differential':
                raise UserError(_('Este asistente solo aplica cuando el tipo de registro es «Diferencial cambiario».'))
            if rec.state != 'draft':
                raise UserError(_('Solo puede cargar plantilla en borrador.'))
            if rec.journal_id.type != 'bank':
                raise UserError(
                    _('La plantilla automática está pensada para un diario de tipo «Banco» con cuenta '
                      'de liquidez. Con diario misceláneo, introduzca las líneas manualmente.')
                )
            liquidity = rec.journal_id.default_account_id
            if not liquidity:
                raise UserError(
                    _('El diario «%s» no tiene cuenta de liquidez por defecto.') % rec.journal_id.display_name
                )
            company = rec.company_id
            contra = company.expense_currency_exchange_account_id or company.income_currency_exchange_account_id
            if not contra:
                raise UserError(
                    _('Configure en la compañía «%s» al menos una cuenta de diferencial cambiario '
                      '(gastos o ingresos por diferencia de cambio).') % company.display_name
                )
            rec.line_ids.unlink()
            BankLine.create([
                {
                    'provision_id': rec.id,
                    'account_id': liquidity.id,
                    'name': _('Ajuste posición cambiaria — cuenta bancaria'),
                    'debit': 0.0,
                    'credit': 0.0,
                },
                {
                    'provision_id': rec.id,
                    'account_id': contra.id,
                    'name': _('Diferencial cambiario (ajuste debe/haber según ganancia o pérdida)'),
                    'debit': 0.0,
                    'credit': 0.0,
                },
            ])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Plantilla de diferencial'),
                'message': _('Se crearon líneas en cero: complete importes en debe/haber y valide cuando cuadren.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def unlink(self):
        for rec in self:
            if rec.name != '/' and not self._context.get('force_delete'):
                raise UserError(_('No puede eliminar un documento de provisión ya numerado.'))
            rec.line_ids.unlink()
        return super().unlink()

    def action_cancel(self):
        for rec in self:
            if not rec.move_id:
                continue
            if rec.move_id.state == 'posted':
                rec.move_id.button_draft()
            rec.move_id.button_cancel()
            rec.state = 'cancel'

    def action_set_to_draft(self):
        for rec in self.filtered(lambda r: r.state == 'cancel'):
            rec.state = 'draft'
            if rec.move_id:
                rec.move_id.button_draft()

    def _validate_balanced_lines(self):
        self.ensure_one()
        if len(self.line_ids) < 2:
            raise UserError(_('Añada al menos dos líneas contables.'))
        for line in self.line_ids:
            if line.debit == 0 and line.credit == 0:
                raise UserError(
                    _('Cada línea debe tener importe en debe o en haber («%s»).')
                    % (line.account_id.display_name,)
                )
        total_debit = sum(self.line_ids.mapped('debit'))
        total_credit = sum(self.line_ids.mapped('credit'))
        if round(total_debit, 6) != round(total_credit, 6) or total_debit <= 0:
            raise UserError(
                _('El asiento debe cuadrar: suma debe (%.2f) debe ser igual a suma haber (%.2f) y mayor que cero.')
                % (total_debit, total_credit)
            )

    def action_validate(self):
        for rec in self:
            rec._validate_balanced_lines()
            sequence = rec._get_sequence()
            if not sequence:
                raise UserError(
                    rec.error_msg or _('Configure la secuencia «%s» para este diario.') % rec._sequence_kind_label()
                )
            if rec.name == '/':
                rec.name = sequence.next_by_id()

            line_commands = [
                Command.create({
                    'name': line.name or rec.description or rec.name,
                    'account_id': line.account_id.id,
                    'partner_id': line.partner_id.id if line.partner_id else False,
                    'debit': line.debit,
                    'credit': line.credit,
                    **line._prepare_analytic_vals(),
                })
                for line in rec.line_ids
            ]

            if not rec.move_id:
                move = self.env['account.move'].create({
                    'move_type': 'entry',
                    'journal_id': rec.journal_id.id,
                    'date': rec.date,
                    'ref': (rec.description or '')[:255] or rec.name,
                    'company_id': rec.company_id.id,
                    'name': rec.name,
                    'sequence_generated': True,
                    'line_ids': line_commands,
                })
                rec.move_id = move.id
            else:
                move = rec.move_id
                if move.state != 'draft':
                    raise UserError(
                        _('El asiento relacionado no está en borrador. Consulte «%s».')
                        % (move.display_name,)
                    )
                move.write({
                    'journal_id': rec.journal_id.id,
                    'date': rec.date,
                    'ref': (rec.description or '')[:255] or rec.name,
                    'name': rec.name,
                })
                move.line_ids.unlink()
                move.with_context(check_move_validity=False).write({'line_ids': line_commands})

            rec.move_id.action_post()
            rec.state = 'validated'

    def action_print_journal_entry(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_('Valide primero para generar el asiento contable.'))
        report = self.env.ref('wm_journal_entry_report.account_journal_entry_report')
        return report.report_action(self.move_id)


class BankProvisionLine(models.Model):
    _name = 'bank.provision.line'
    _description = 'Línea de provisión bancaria'
    _order = 'id'
    _check_company_auto = True

    provision_id = fields.Many2one(
        'bank.provision',
        string='Provisión',
        required=True,
        ondelete='cascade',
        check_company=True,
    )
    company_id = fields.Many2one(
        related='provision_id.company_id',
        store=True,
        readonly=True,
    )
    account_id = fields.Many2one(
        'account.account',
        string='Cuenta',
        required=True,
        check_company=True,
    )
    partner_id = fields.Many2one('res.partner', string='Contacto', check_company=True)
    name = fields.Char(string='Etiqueta')
    debit = fields.Monetary(string='Debe', currency_field='currency_id', default=0.0)
    credit = fields.Monetary(string='Haber', currency_field='currency_id', default=0.0)
    currency_id = fields.Many2one(
        related='provision_id.currency_id',
        readonly=True,
    )
    analytic_distribution = fields.Json(string='Distribución analítica', default={})

    analytic_precision = fields.Integer(
        default=lambda self: self.env['decimal.precision'].precision_get('Percentage Analytic'),
        store=False,
    )

    @api.constrains('debit', 'credit')
    def _check_debit_credit(self):
        for line in self:
            if line.debit < 0 or line.credit < 0:
                raise UserError(_('Los importes en debe y haber deben ser positivos o cero.'))
            if line.debit > 0 and line.credit > 0:
                raise UserError(_('La línea «%s» no debe tener debe y haber a la vez.') % (line.display_name,))

    def _prepare_analytic_vals(self):
        self.ensure_one()
        vals = {}
        if self.analytic_distribution:
            vals['analytic_distribution'] = self.analytic_distribution
        return vals
