# Suite de Pruebas - l10n_hn_hr_payroll

## Estructura

```
tests/
├── __init__.py
├── common.py              # Factories y helpers (L10nHnPayrollTestCommon)
├── test_isr.py            # ISR cálculo, tramos, withholding
├── test_isr_sar_2026.py   # Algoritmo SAR 2026
├── test_ihss.py           # IHSS techos, cuotas, validaciones
├── test_rap.py            # RAP FOVIIF, FRL
├── test_salary_rules.py   # Reglas salariales BASIC, GROSS, NET, IHSS, RAP, ISR
├── test_decimo_tercero_catorce.py  # 13vo y 14vo mes
├── test_payslip_inputs_and_rules.py  # Payslip end-to-end
├── test_wizards.py        # Wizards ISR, Benefits
└── test_security_access.py  # Permisos admin/user/auditor
```

## Ejecución

### Instalar módulo con tests
```bash
./odoo-bin -d <database> -i l10n_hn_hr_payroll --test-enable --stop-after-init
```

### Actualizar y ejecutar tests
```bash
./odoo-bin -d <database> -u l10n_hn_hr_payroll --test-enable --stop-after-init
```

### Filtrar por tags
```bash
# Solo tests de nómina (payslip, rules)
./odoo-bin -d <database> -u l10n_hn_hr_payroll --test-enable --stop-after-init --test-tags=payroll

# Solo tests de ISR
./odoo-bin -d <database> -u l10n_hn_hr_payroll --test-enable --stop-after-init --test-tags=post_install

# Excluir tests que requieren account
./odoo-bin -d <database> -u l10n_hn_hr_payroll --test-enable --stop-after-init --test-tags=-account
```

## Tags utilizados

- `post_install`, `-at_install`: Tests que requieren módulo instalado
- `payroll`: Tests de payslip y reglas salariales
- `security`: Tests de permisos
- `account`: (opcional) Tests que requieren contabilidad

## Datos de prueba

Los tests usan fechas fijas (2026) para ser deterministas. Las factories en `common.py` crean:
- Company, structure type, structure
- Employee con hr.version (contrato)
- IHSS, RAP, ISR config validados
- Payslip, payslip run

No se depende de demo data.
