# Explicación del Módulo Stock Valuation Report

## 📍 Dónde encontrar la funcionalidad

### 1. En la interfaz de Odoo:
- **Menú**: Inventario > Reportes > Inventory Valuation
- **Ruta completa**: `stock.menu_warehouse_report` > "Inventory Valuation"
- **Archivo de vista**: `views/stock_valuation_report_views.xml` (línea 86-90)

### 2. En el código:

#### Modelo principal:
- **Archivo**: `models/stock_valuation_report.py`
- **Modelo**: `stock.valuation.report` (TransientModel)
- **Línea de inicio**: línea 9

#### Vista del formulario:
- **Archivo**: `views/stock_valuation_report_views.xml`
- **Vista**: `view_stock_valuation_report_form` (línea 4)
- **Acción**: `action_stock_valuation_report` (línea 77)

#### Wizard para generar asientos:
- **Archivo**: `wizard/stock_valuation_generate_entry.py`
- **Modelo**: `stock.valuation.generate.entry`

---

## 🔧 Cómo funciona el módulo

### 1. **Acceso al reporte**

Cuando accedes al menú "Inventory Valuation", se abre un formulario con:

```
┌─────────────────────────────────────────┐
│  [Compute]  [Generate Entry]           │
├─────────────────────────────────────────┤
│  Company: [GRUPO NAHUIIK]              │
│  From Date: [01/11/2025] (opcional)    │
│  To Date: [19/11/2025] (requerido)     │
├─────────────────────────────────────────┤
│  Initial Balance: 0.00                  │
│  Stock Variation: 0.00                  │
│  Ending Stock: 0.00                     │
├─────────────────────────────────────────┤
│  Account Details (pestaña)              │
│  ┌──────────────────────────────────┐  │
│  │ Account | Debit | Credit | Value │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### 2. **Proceso de cálculo** (método `_compute_valuation`)

**Ubicación**: `models/stock_valuation_report.py`, línea 100-380

#### Paso 1: Validación inicial
```python
# Línea 103-108
if not report.date_to or not report.company_id:
    # Retorna valores en 0
```

#### Paso 2: Obtener valores de inventario
```python
# Línea 133-138
# Usa el método estándar de Odoo: company.stock_value()
inventory_data = report.company_id.stock_value(at_date=report_date)
# Devuelve: {account: value} 
# Ejemplo: {account.account(67,): 368815.0}
```

**¿Qué hace `stock_value()`?**
- Internamente usa: `product.with_context(to_date=at_date).total_value`
- Agrupa los valores por cuenta de valuación de stock
- Considera el método de costeo (FIFO, Average, Standard)

#### Paso 3: Calcular balance inicial
```python
# Línea 141-144
if date_from:
    initial_inventory_data = report.company_id.stock_value(at_date=date_from)
    report.initial_balance = sum(initial_inventory_data.values())
```

#### Paso 4: Calcular variación
```python
# Línea 227
report.stock_variation = report.ending_stock - report.initial_balance
```

#### Paso 5: Crear líneas de valuación
```python
# Línea 280-296
# Crea líneas agrupadas por cuenta contable
for account, value in inventory_data.items():
    lines.append(Command.create({
        "account_id": account.id,
        "line_type": "ending",
        "value": value,
        ...
    }))
```

### 3. **Botón "Compute"**

**Ubicación**: `models/stock_valuation_report.py`, línea 404-411

```python
def action_compute(self):
    """Fuerza el recálculo del reporte"""
    self.invalidate_recordset(['initial_balance', 'ending_stock', ...])
    self._compute_valuation()
    return {...}  # Recarga la vista
```

**Cuándo usarlo:**
- Cuando cambias las fechas y no se recalcula automáticamente
- Para forzar un nuevo cálculo

### 4. **Botón "Generate Entry"**

**Ubicación**: `models/stock_valuation_report.py`, línea 413-430

Abre un wizard (`stock.valuation.generate.entry`) que permite:
- Seleccionar diario contable
- Seleccionar cuentas (gastos y valuación)
- Generar un asiento contable con:
  - **Débito**: Cuenta de gastos/variación (si hay aumento de stock)
  - **Crédito**: Cuenta de valuación de inventario

---

## 📊 Flujo completo de datos

```
1. Usuario selecciona fechas
   ↓
2. Se ejecuta _compute_valuation() (automático o con botón Compute)
   ↓
3. company.stock_value(at_date=date_to)
   ↓
4. Para cada producto almacenable:
   - product.with_context(to_date=date_to).total_value
   - Agrupa por cuenta de valuación
   ↓
5. Calcula:
   - ending_stock = suma de todos los valores
   - initial_balance = stock_value(at_date=date_from) si existe
   - stock_variation = ending_stock - initial_balance
   ↓
6. Crea líneas de valuación agrupadas por cuenta
   ↓
7. Muestra en la interfaz
```

---

## 🔍 Archivos clave del módulo

### Modelos:
1. **`models/stock_valuation_report.py`**
   - Modelo principal: `stock.valuation.report`
   - Método principal: `_compute_valuation()` (línea 100)
   - Botones: `action_compute()`, `action_generate_entry()`

2. **`models/stock_valuation_report.py`** (continuación)
   - Modelo de líneas: `stock.valuation.report.line` (línea 456+)

3. **`wizard/stock_valuation_generate_entry.py`**
   - Wizard para generar asientos contables

4. **`models/res_company.py`**
   - Configuración de cuentas y diarios por defecto

### Vistas:
1. **`views/stock_valuation_report_views.xml`**
   - Vista del formulario (línea 4)
   - Acción y menú (línea 77-90)

2. **`wizard/stock_valuation_generate_entry_views.xml`**
   - Vista del wizard

### Seguridad:
1. **`security/ir.model.access.csv`**
   - Permisos de acceso a los modelos

2. **`security/security.xml`**
   - Grupos de seguridad

---

## ⚙️ Configuración necesaria

### 1. Cuentas de valuación en productos:
- Cada categoría de producto debe tener configurada:
  - `property_stock_valuation_account_id` (cuenta de valuación)
  - `property_account_expense_categ_id` (cuenta de gastos/COGS)

### 2. Configuración de compañía (opcional):
- `inventory_bridge_journal_id`: Diario para asientos
- `inventory_bridge_expense_account_id`: Cuenta de variación
- `inventory_bridge_stock_account_id`: Cuenta de valuación

**Ubicación**: `models/res_company.py`, línea 10-25

---

## 🐛 Troubleshooting

### Si no muestra datos:

1. **Verificar que `stock_account` esté instalado**
   ```python
   # En shell de Odoo:
   env['ir.module.module'].search([('name', '=', 'stock_account')])
   ```

2. **Verificar que haya productos almacenables**
   ```python
   env['product.product'].search([('is_storable', '=', True)])
   ```

3. **Verificar que `stock_value()` funcione**
   ```python
   company = env['res.company'].search([], limit=1)
   data = company.stock_value()
   print(data)  # Debe devolver un dict con cuentas y valores
   ```

4. **Verificar que los productos tengan cuentas configuradas**
   ```python
   products = env['product.product'].search([('is_storable', '=', True)])
   for p in products[:5]:
       print(f"{p.name}: {p.categ_id.property_stock_valuation_account_id}")
   ```

---

## 📝 Ejemplo de uso

1. **Ir a**: Inventario > Reportes > Inventory Valuation
2. **Seleccionar**:
   - Company: GRUPO NAHUIIK
   - From Date: 01/11/2025 (opcional)
   - To Date: 19/11/2025
3. **Hacer clic en "Compute"**
4. **Ver resultados**:
   - Initial Balance: Valor del inventario al inicio
   - Ending Stock: Valor del inventario al final
   - Stock Variation: Diferencia (ending - initial)
5. **Ver detalles**: Pestaña "Account Details" muestra desglose por cuenta
6. **Generar asiento** (opcional): Botón "Generate Entry" si hay variación

---

## 🔗 Dependencias

- `stock`: Módulo base de inventario
- `stock_account`: Módulo de valuación de inventario (requerido)
- `account`: Módulo de contabilidad

**Ubicación**: `__manifest__.py`, línea 12-18

