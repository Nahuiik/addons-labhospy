# -*- coding: utf-8 -*-
{
    'name': 'Honduras — Perfil PYME / mediana (Community)',
    'summary': 'Instala y ordena la cadena contable-fiscal HN para Odoo CE: plan, informes, '
                '904, libros, retenciones, DMC y tasas BCH.',
    'version': '19.0.1.0.6',
    'category': 'Accounting/Localizations',
    'author': 'Labhospy',
    'license': 'LGPL-3',
    'depends': [
        'l10n_hn_account',
        'gn_bank_rate',
        'bi_financial_reports_comm',
        'l10n_hn_reports',
        'l10n_hn_retentions',
        'l10n_hn_dmc',
        'l10n_hn_legal_books',
    ],
    'data': [],
    'installable': True,
    'application': True,
    'description': """
Perfil único de instalación (Odoo Community) para empresas medianas en Honduras.

Incluye, mediante dependencias, los módulos: l10n_hn_account (plan y campos SAR);
gn_bank_rate (tasas USD vía Banco Central de Honduras); bi_financial_reports_comm
(informes financieros en pantalla); l10n_hn_reports (formulario 904, libros fiscales y libros legales mercantiles);
l10n_hn_retentions (retenciones); l10n_hn_dmc (exportación XLS del reporte DMC, compras).

Los informes 904, libros y DMC comparten el menú Contabilidad, Informes,
Honduras (SAR / fiscal).

El módulo nahuiik_report está obsoleto (installable False en el manifiesto); en
despliegues nuevos usar solo l10n_hn_reports y l10n_hn_dmc para libros y DMC.

Otros módulos HN (inventario, caja registradora, etc.) se instalan aparte según el negocio.
    """,
}
