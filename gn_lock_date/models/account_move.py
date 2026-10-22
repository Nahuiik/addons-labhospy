# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def gn_get_period_lock_status(self, move_ids, move_date, journal_id, company_id):
        """Return granular period lock warning for UI (gn.period.lock only).

        Native ``res.company`` lock checks stay on posting; this is for early
        feedback on the journal entry form.

        :param move_ids: ids of ``account.move`` (may be empty for new records)
        :param move_date: accounting date (string YYYY-MM-DD or date)
        :param journal_id: int
        :param company_id: int or False (defaults to current company)
        :return: dict ``{'blocked': bool, 'message': str}``
        """
        PeriodLock = self.env["gn.period.lock"]
        if isinstance(move_date, str):
            move_date = fields.Date.from_string(move_date)
        cid = company_id or self.env.company.id
        if not move_date or not journal_id or not cid:
            return {"blocked": False, "message": ""}
        if PeriodLock.check_period_lock(move_date, int(journal_id), int(cid)):
            msg = PeriodLock.get_lock_message(move_date, int(journal_id), int(cid))
            return {"blocked": True, "message": msg or ""}
        return {"blocked": False, "message": ""}

    def _check_period_lock(self):
        """Verificar si el movimiento está en un período bloqueado"""
        PeriodLock = self.env['gn.period.lock']
        
        for move in self:
            if not move.date or not move.journal_id or not move.company_id:
                continue
            
            # Verificar si hay un bloqueo de período activo
            if PeriodLock.check_period_lock(move.date, move.journal_id.id, move.company_id.id):
                message = PeriodLock.get_lock_message(move.date, move.journal_id.id, move.company_id.id)
                if message:
                    raise UserError(message)

    @api.model_create_multi
    def create(self, vals_list):
        """Sobrescribir create para validar bloqueos al crear"""
        moves = super().create(vals_list)
        moves._check_period_lock()
        return moves

    def action_post(self):
        """Sobrescribir action_post para validar bloqueos de período"""
        self._check_period_lock()
        return super().action_post()

    def write(self, vals):
        """Sobrescribir write para validar bloqueos al modificar"""
        res = super().write(vals)
        
        # Si se está modificando la fecha o el diario, verificar bloqueos
        if 'date' in vals or 'journal_id' in vals:
            self._check_period_lock()
        
        return res

