# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PowerBiExportService(models.AbstractModel):
    _name = 'powerbi.export.service'
    _description = 'Power BI Export Service'

    def export_table(self, table, mode='auto', records=None):
        """
        Exporta los registros de una tabla hacia Power BI
        
        :param table: powerbi.table
        :param mode: 'auto', 'incremental', 'full'
        :param records: Recordset opcional (si se proporciona, se usa en lugar de buscar)
        :return: Diccionario con resultado de la exportación
        """
        start_time = datetime.now()

        # Validaciones
        if not table.dataset_id.pbi_dataset_id:
            raise UserError(_('El dataset debe estar publicado antes de exportar'))

        if not table.field_ids.filtered('export'):
            raise UserError(_('Debe configurar al menos un campo para exportar'))

        # Obtener registros
        if records is None:
            records = table._get_records_to_export(mode)
        else:
            records = records

        if not records:
            table.write({
                'last_sync_state': 'no_data',
            })
            return {
                'count': 0,
                'duration': 0,
                'state': 'no_data',
            }

        # Obtener conexión y configuración
        connection = self.env['powerbi.connection'].get_active_connection()
        api_service = self.env['powerbi.api.service']
        workspace_id = table.dataset_id.workspace_id.pbi_workspace_id
        dataset_id = table.dataset_id.pbi_dataset_id
        table_name = table.pbi_table_name or table.name

        # Procesar por lotes
        batch_size = table.batch_size or int(
            self.env['ir.config_parameter'].sudo().get_param(
                'powerbi_default_batch_size',
                '10000'
            )
        )

        total_exported = 0
        total_batches = 0

        try:
            # Dividir en lotes
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                rows = self._convert_records_to_rows(table, batch)

                # Enviar lote a Power BI
                api_service.insert_rows(
                    connection,
                    workspace_id,
                    dataset_id,
                    table_name,
                    rows
                )

                total_exported += len(batch)
                total_batches += 1

                # Registrar log por lote
                self._record_sync_logs(
                    table,
                    batch,
                    'export',
                    'success',
                    f'Lote {total_batches}: {len(batch)} registros exportados'
                )

            # Calcular duración
            duration = (datetime.now() - start_time).total_seconds()

            # Actualizar estado de sincronización
            table.write({
                'last_sync_datetime': fields.Datetime.now(),
                'last_sync_state': 'success',
            })

            # Registrar métrica
            self._record_metric(
                table,
                'export_duration',
                duration,
                'success',
                f'Exportados {total_exported} registros en {total_batches} lotes'
            )

            # Evaluar alertas
            self._evaluate_alerts(table, duration, total_exported, 'success')

            return {
                'count': total_exported,
                'duration': duration,
                'batches': total_batches,
                'state': 'success',
            }

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)

            # Actualizar estado
            table.write({
                'last_sync_state': 'failed',
            })

            # Registrar métrica de error
            self._record_metric(
                table,
                'export_error',
                0,
                'failed',
                error_msg
            )

            # Registrar log de error
            self._record_sync_logs(
                table,
                records[:1] if records else self.env[table.model_id.model],
                'export',
                'failed',
                error_msg
            )

            # Crear alerta
            self._create_export_alert(table, error_msg)

            raise UserError(_('Error al exportar: %s') % error_msg)

    def _convert_records_to_rows(self, table, records):
        """
        Convierte un recordset de Odoo a filas para Power BI
        """
        rows = []
        fields_to_export = table.field_ids.filtered('export').sorted('sequence')

        for record in records:
            row = {}
            for field in fields_to_export:
                try:
                    # Obtener valor del campo
                    value = getattr(record, field.field_id.name, False)
                    # Convertir valor según tipo
                    converted_value = field.convert_value(value)
                    row[field.name] = converted_value
                except Exception as e:
                    _logger.warning(
                        'Error al convertir campo %s del registro %s: %s',
                        field.name,
                        record.id,
                        str(e)
                    )
                    row[field.name] = None

            rows.append(row)

        return rows

    def _record_metric(self, table, metric_type, value, state, details=''):
        """
        Registra una métrica de exportación
        """
        self.env['powerbi.metric'].create({
            'name': f'{table.name} - {metric_type}',
            'metric_type': metric_type,
            'date': fields.Datetime.now(),
            'table_id': table.id,
            'value': value,
            'state': state,
            'details': details,
        })

    def _record_sync_logs(self, table, records, operation, state, message):
        """
        Registra logs de sincronización
        """
        log_vals = []
        for record in records:
            log_vals.append({
                'table_id': table.id,
                'model_id': table.model_id.id,
                'res_id': record.id,
                'operation': operation,
                'sync_datetime': fields.Datetime.now(),
                'state': state,
                'message': message,
            })

        if log_vals:
            self.env['powerbi.sync.log'].create(log_vals)

    def _evaluate_alerts(self, table, duration, record_count, state):
        """
        Evalúa y crea alertas según umbrales configurados
        """
        # Obtener umbrales globales
        slow_threshold = float(
            self.env['ir.config_parameter'].sudo().get_param(
                'powerbi_slow_export_threshold',
                '120'
            )
        )
        low_record_threshold = int(
            self.env['ir.config_parameter'].sudo().get_param(
                'powerbi_low_record_threshold',
                '10'
            )
        )

        # Verificar exportación lenta
        if duration > slow_threshold:
            self._create_export_alert(
                table,
                f'Exportación lenta: {duration:.2f} segundos (umbral: {slow_threshold}s)',
                'slow_export'
            )

        # Verificar bajo número de registros
        if record_count < low_record_threshold and record_count > 0:
            self._create_export_alert(
                table,
                f'Bajo número de registros exportados: {record_count} (umbral: {low_record_threshold})',
                'low_records'
            )

        # Verificar errores
        if state == 'failed':
            self._create_export_alert(table, 'Error en exportación', 'export_failed')

    def _create_export_alert(self, table, message, alert_type='export_failed'):
        """
        Crea una alerta de exportación
        """
        # Verificar si las alertas automáticas están habilitadas
        enable_alerts = self.env['ir.config_parameter'].sudo().get_param(
            'powerbi_enable_auto_alerts',
            'True'
        ) == 'True'

        if not enable_alerts:
            return

        self.env['powerbi.alert'].create({
            'name': f'{table.name} - {alert_type}',
            'alert_type': alert_type,
            'table_id': table.id,
            'message': message,
            'active': True,
        })

