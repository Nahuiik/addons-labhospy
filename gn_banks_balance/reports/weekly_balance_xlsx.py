# -*- coding: utf-8 -*-
from odoo import models, _


class ReportBanksWeeklyBalanceXlsx(models.AbstractModel):
    _name = 'report.gn_banks_balance.weekly_balance_report_xlsx.xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Informe mensual por semanas (saldos bancarios Excel)'

    def generate_xlsx_report(self, workbook, data, objs):
        wizard_id = False
        if data and isinstance(data, dict):
            wizard_id = data.get('wizard_id')
        if wizard_id is None and objs:
            wizard_id = objs.ids[0] if objs.ids else False
        wizard = self.env['banks.weekly.balance.report'].browse(wizard_id)
        wizard.ensure_one()

        journals = wizard.journal_ids.filtered(lambda j: j.default_account_id)
        journals = journals.sorted(lambda j: j.name or '')

        common = self.env['banks.weekly.balance.common']
        payload = common.build_legacy_payload(wizard)

        if not payload['has_data']:
            ws = workbook.add_worksheet(_('Sin datos'))
            ws.write(
                0,
                0,
                payload.get('error_message') or _('Sin datos.'),
            )
            return

        company = wizard.company_id
        journal_columns = payload['journal_columns']
        week_blocks = payload['week_blocks']
        summary_lines = payload['summary_lines']
        delta_col = 2 + len(journal_columns) + 1

        BANK_HEADER_COLORS = [
            ('#5B2C6F', 'white'),
            ('#4A2360', 'white'),
            ('#7D4A94', 'white'),
            ('#C5A55A', '#3d3010'),
            ('#6B3A82', 'white'),
            ('#A8893E', 'white'),
            ('#8B5FA8', 'white'),
            ('#5B2C6F', 'white'),
        ]
        ROW_BG = {
            'opening': '#FFFFFF',
            'inflow': '#F5F0E6',
            'outflow': '#F3EDF5',
        }

        hdr_bank_formats = []
        for bg, fg in BANK_HEADER_COLORS:
            hdr_bank_formats.append(
                workbook.add_format(
                    {
                        'bold': True,
                        'font_size': 10,
                        'align': 'center',
                        'border': True,
                        'fg_color': bg,
                        'font_color': fg,
                    }
                )
            )
        hdr_corner = workbook.add_format(
            {
                'bold': True,
                'font_size': 10,
                'align': 'center',
                'border': True,
                'fg_color': '#A8893E',
                'font_color': 'white',
            }
        )
        hdr_corner_concept = workbook.add_format(
            {
                'bold': True,
                'font_size': 10,
                'align': 'left',
                'border': True,
                'fg_color': '#4A2360',
                'font_color': 'white',
            }
        )
        hdr_total = workbook.add_format(
            {
                'bold': True,
                'font_size': 10,
                'align': 'center',
                'border': True,
                'fg_color': '#5B2C6F',
                'font_color': 'white',
            }
        )
        hdr_delta = workbook.add_format(
            {
                'bold': True,
                'font_size': 10,
                'align': 'center',
                'border': True,
                'fg_color': '#6B3A82',
                'font_color': 'white',
            }
        )
        lbl_week = workbook.add_format(
            {
                'font_size': 10,
                'border': True,
                'align': 'left',
                'valign': 'vcenter',
                'bold': True,
                'fg_color': '#E8DCF0',
                'font_color': '#4A2360',
            }
        )
        ttl_gr = workbook.add_format(
            {
                'font_size': 10,
                'align': 'right',
                'bold': True,
                'num_format': '#,##0.00',
                'border': True,
                'fg_color': '#EDE3D0',
                'font_color': '#4A2360',
            }
        )
        title_big = workbook.add_format(
            {
                'font_size': 14,
                'bold': True,
                'align': 'center',
                'font_color': '#5B2C6F',
            }
        )
        sub_big = workbook.add_format(
            {
                'font_size': 11,
                'bold': True,
                'align': 'center',
                'font_color': '#4A2360',
            }
        )
        hdr_res = workbook.add_format(
            {
                'bold': True,
                'font_size': 11,
                'border': True,
                'fg_color': '#5B2C6F',
                'font_color': 'white',
                'align': 'center',
            }
        )
        row_formats = {}
        for row_type, bg in ROW_BG.items():
            row_formats[row_type] = {
                'lbl': workbook.add_format(
                    {
                        'font_size': 10,
                        'border': True,
                        'align': 'left',
                        'valign': 'vcenter',
                        'fg_color': bg,
                    }
                ),
                'num': workbook.add_format(
                    {
                        'font_size': 10,
                        'align': 'right',
                        'num_format': '#,##0.00',
                        'fg_color': bg,
                    }
                ),
                'ttl': workbook.add_format(
                    {
                        'font_size': 10,
                        'align': 'right',
                        'bold': True,
                        'num_format': '#,##0.00',
                        'border': True,
                        'fg_color': bg,
                        'font_color': '#5B2C6F',
                    }
                ),
                'diff': workbook.add_format(
                    {
                        'font_size': 10,
                        'align': 'right',
                        'num_format': '#,##0.00',
                        'fg_color': bg,
                    }
                ),
            }

        sheet_name = 'Saldo %s' % payload['month_year_title']
        if len(sheet_name) > 31:
            sheet_name = 'Saldos bancarios mes'
        sheet = workbook.add_worksheet(sheet_name[:31])

        r = 0
        sheet.merge_range(r, 0, r, delta_col, company.name or '', title_big)
        r += 1
        sheet.merge_range(r, 0, r, delta_col, payload['subtitle'], sub_big)
        r += 1
        sheet.merge_range(r, 0, r, delta_col, payload['month_year_title'], sub_big)
        r += 2

        sheet.set_column(0, 0, 36)
        sheet.set_column(1, 1, 24)
        sheet.write(r, 0, _('PERÍODO / SEMANA'), hdr_corner)
        sheet.write(r, 1, _('CONCEPTO'), hdr_corner_concept)
        cidx = 2
        for col in journal_columns:
            ci = col.get('color_index', (cidx - 2) % len(BANK_HEADER_COLORS))
            sheet.write(r, cidx, col['label'][:40], hdr_bank_formats[ci])
            sheet.set_column(cidx, cidx, 18)
            cidx += 1
        sheet.write(r, cidx, _('TOTAL'), hdr_total)
        sheet.set_column(cidx, cidx, 16)
        cidx += 1
        sheet.write(r, cidx, _('DIF vs saldo ini. anterior'), hdr_delta)
        sheet.set_column(cidx, cidx, 22)
        r += 1

        for week in week_blocks:
            rb = r
            sheet.merge_range(rb, 0, rb + 2, 0, week['period_label'], lbl_week)
            for row in week['rows']:
                rf = row_formats.get(row.get('row_type', 'opening'), row_formats['opening'])
                sheet.write(rb, 1, row['concept'], rf['lbl'])
                ci = 2
                for amt in row['amounts']:
                    sheet.write_number(rb, ci, amt, rf['num'])
                    ci += 1
                sheet.write_number(rb, ci, row['total'], rf['ttl'])
                if row.get('show_delta'):
                    sheet.write_number(
                        rb, ci + 1, row.get('delta') or 0.0, rf['diff']
                    )
                else:
                    sheet.write(rb, ci + 1, '', rf['lbl'])
                rb += 1
            r = rb + 1

        r += 1
        sheet.merge_range(r, 0, r, delta_col, _('RESUMEN DEL MES'), hdr_res)
        r += 1

        for sline in summary_lines:
            sheet.write(r, 0, sline['label'], ttl_gr)
            sheet.write(r, 1, '', ttl_gr)
            ci = 2
            for amt in sline['amounts']:
                sheet.write_number(r, ci, amt, ttl_gr)
                ci += 1
            sheet.write_number(r, ci, sline['total'], ttl_gr)
            r += 1
