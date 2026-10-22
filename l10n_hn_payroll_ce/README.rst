Honduras payroll — inputs por empleado (Community / ``l10n_hn_payroll_base``)
==============================================================================

Este módulo enlaza **beneficios y deducciones** definidos en la ficha del empleado
(``hr.employee.salary.input``) con las **líneas de entrada** del recibo de pago
(``hr.payslip.input``) del motor CE **l10n_hn_payroll_base**.

Incluye modelos ligeros **IHSS/AFP** (``hr.ihss.settings``, ``hr.afp.settings``)
orientados al flujo de *salary inputs* por código de tipo de entrada
(``hr.payslip.input.type``), y crea reglas **IHSS** / **AFP** en las estructuras
de demostración del base, con ``hr.rule.input`` enlazadas.

**Nota:** La localización completa Honduras (``l10n_hn_hr_payroll``) usa otros
modelos (p. ej. ``l10n.hn.ihss.settings``). Aquí los modelos ``hr.*`` son para
el flujo de inputs del empleado; pueden convivir, pero evite configurar dos
fuentes de verdad distintas para la misma deducción.

Dependencias
------------

- ``l10n_hn_payroll_base``

Queda **excluido** el uso simultáneo declarativo con ``bi_hr_payroll`` (manifest ``excludes``).

Metapaquete ``gn_hn_payroll``
-----------------------------

El addon ``gn_hn_payroll`` actúa solo como **dependencia histórica** que tira de
``l10n_hn_payroll_ce``; la implementación vive en este módulo.

Autor / licencia
----------------

Grupo Nahuiik — LGPL-3.
