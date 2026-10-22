# GN Accounting Reports

## Descripción

Módulo que proporciona reportes contables de **General Ledger** y **Partner Ledger** para Odoo 19.

Este módulo incluye únicamente estas dos funcionalidades de reportes contables, simplificando el acceso a los libros mayores y auxiliares de clientes/proveedores.

## Características

### General Ledger (Libro Mayor General)
- Reporte detallado de todas las cuentas contables
- Filtros por:
  - Diarios
  - Cuentas
  - Partners
  - Cuentas analíticas (si está instalado el módulo de analítica)
  - Rango de fechas
- Opciones de visualización:
  - Todas las cuentas
  - Solo cuentas con movimientos
  - Solo cuentas con balance diferente de cero
- Opciones de ordenamiento:
  - Por fecha
  - Por diario y partner
- Incluye balance inicial opcional

### Partner Ledger (Libro Auxiliar de Partners)
- Reporte detallado de movimientos por partner (clientes/proveedores)
- Filtros por:
  - Partners específicos
  - Diarios
  - Rango de fechas
- Opciones:
  - Solo cuentas por cobrar
  - Solo cuentas por pagar
  - Ambas
  - Entradas conciliadas o no conciliadas
  - Mostrar moneda (si hay multi-moneda)

## Requisitos

- Odoo 19.0
- Módulo `account` (incluido en Odoo)

## Instalación

1. Copia el directorio `gn_accounting_reports` en tu carpeta de addons
2. Actualiza la lista de aplicaciones en Odoo
3. Instala el módulo desde **Aplicaciones**

## Uso

### Acceder a General Ledger (Vista en Pantalla)

1. Ve a **Contabilidad > Transacciones > General Ledger**
2. Los datos se mostrarán directamente en pantalla agrupados por cuenta
3. Puedes filtrar, buscar y agrupar los datos directamente en la interfaz

### Acceder a Partner Ledger (Vista en Pantalla)

1. Ve a **Contabilidad > Transacciones > Partner Ledger**
2. Los datos se mostrarán directamente en pantalla agrupados por partner
3. Puedes filtrar, buscar y agrupar los datos directamente en la interfaz

### Acceder a General Ledger (PDF)

1. Ve a **Contabilidad > Reportes > Ledgers > General Ledger**
2. Configura los filtros deseados:
   - Selecciona los diarios
   - Opcionalmente selecciona cuentas, partners o cuentas analíticas
   - Define el rango de fechas
   - Selecciona el tipo de movimientos (Todos o Solo Publicados)
   - Elige el ordenamiento y tipo de visualización
3. Haz clic en **Imprimir** para generar el reporte PDF

### Acceder a Partner Ledger (PDF)

1. Ve a **Contabilidad > Reportes > Ledgers > Partner Ledger**
2. Configura los filtros deseados:
   - Opcionalmente selecciona partners específicos
   - Selecciona los diarios
   - Define el rango de fechas
   - Selecciona el tipo de cuentas (Por cobrar, Por pagar, o Ambas)
   - Opciones adicionales: Entradas conciliadas y mostrar moneda
3. Haz clic en **Imprimir** para generar el reporte PDF

### Desde el menú de Partners

También puedes acceder al Partner Ledger directamente desde un partner:
1. Abre un partner (cliente o proveedor)
2. Haz clic en el botón **Imprimir** (menú de acciones)
3. Selecciona **Balance Statement (Partner Ledger)**

## Estructura del Módulo

```
gn_accounting_reports/
├── __init__.py
├── __manifest__.py
├── README.md
├── wizard/
│   ├── __init__.py
│   ├── account_report_common.py          # Clase base común
│   ├── account_report_common_account.py # Clase base para reportes de cuentas
│   ├── account_report_common_partner.py  # Clase base para reportes de partners
│   ├── account_general_ledger.py         # Wizard General Ledger
│   ├── account_partner_ledger.py        # Wizard Partner Ledger
│   ├── account_report_common_view.xml    # Vista común
│   ├── general_ledger.xml               # Vista y menú General Ledger
│   └── partner_ledger.xml               # Vista y menú Partner Ledger
├── report/
│   ├── __init__.py
│   ├── report.xml                       # Definición de reportes
│   ├── report_general_ledger.py         # Lógica del reporte General Ledger
│   ├── report_general_ledger.xml        # Template PDF General Ledger
│   ├── report_partner_ledger.py        # Lógica del reporte Partner Ledger
│   └── report_partner_ledger.xml       # Template PDF Partner Ledger
├── views/
│   └── ledger_menu.xml                  # Menú principal Ledgers
└── security/
    └── ir.model.access.csv              # Permisos de acceso
```

## Permisos

- **General Ledger**: Requiere grupo `account.group_account_user` o `account.group_account_manager`
- **Partner Ledger**: Requiere grupo `account.group_account_invoice` o `account.group_account_manager`

## Autor

Grupo Nahuiik
Website: https://www.gruponahuiik.com

## Licencia

LGPL-3

