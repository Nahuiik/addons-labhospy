# -*- coding: utf-8 -*-
"""
Pruebas funcionales para el módulo l10n_hn_stock
"""
import logging

_logger = logging.getLogger(__name__)


def test_security_groups(env):
    """Verificar que los grupos de seguridad se crearon correctamente"""
    _logger.info("=== Prueba: Grupos de Seguridad ===")
    
    groups_to_check = [
        'l10n_hn_stock.group_allow_edit_sale_price_quotation_user',
        'l10n_hn_stock.group_allow_edit_sale_price_quotation',
        'l10n_hn_stock.group_allow_edit_sale_price_invoice_user',
        'l10n_hn_stock.group_allow_edit_sale_price_invoice',
        'l10n_hn_stock.group_allow_confirm_sale_view_docs_user',
        'l10n_hn_stock.group_allow_confirm_sale_view_docs',
        'l10n_hn_stock.group_view_costs_margins',
        'l10n_hn_stock.group_allow_sell_below_cost',
    ]
    
    all_found = True
    for group_xmlid in groups_to_check:
        try:
            group = env.ref(group_xmlid, raise_if_not_found=False)
            if group:
                _logger.info(f"✓ Grupo encontrado: {group_xmlid} - {group.name}")
            else:
                _logger.error(f"✗ Grupo NO encontrado: {group_xmlid}")
                all_found = False
        except Exception as e:
            _logger.error(f"✗ Error al buscar grupo {group_xmlid}: {e}")
            all_found = False
    
    # Verificar categoría del módulo
    try:
        category = env.ref('l10n_hn_stock.module_category_honduras_stock', raise_if_not_found=False)
        if category:
            _logger.info(f"✓ Categoría encontrada: {category.name}")
        else:
            _logger.error("✗ Categoría del módulo NO encontrada")
            all_found = False
    except Exception as e:
        _logger.error(f"✗ Error al buscar categoría: {e}")
        all_found = False
    
    return all_found


def test_sequences(env):
    """Verificar que las secuencias se crearon correctamente"""
    _logger.info("\n=== Prueba: Secuencias ===")
    
    sequences_to_check = [
        'hn.remission',
    ]
    
    all_found = True
    for seq_code in sequences_to_check:
        try:
            sequence = env['ir.sequence'].search([('code', '=', seq_code)], limit=1)
            if sequence:
                _logger.info(f"✓ Secuencia encontrada: {seq_code} - {sequence.name}")
            else:
                _logger.error(f"✗ Secuencia NO encontrada: {seq_code}")
                all_found = False
        except Exception as e:
            _logger.error(f"✗ Error al buscar secuencia {seq_code}: {e}")
            all_found = False
    
    return all_found


def test_models(env):
    """Verificar que los modelos se pueden instanciar"""
    _logger.info("\n=== Prueba: Modelos ===")
    
    models_to_check = [
        'sale.order.line',
        'sale.order',
        'stock.picking',
        'account.move.line',
        'account.move',
        'consume.product',
    ]
    
    all_ok = True
    for model_name in models_to_check:
        try:
            model = env[model_name]
            count = model.search_count([])
            _logger.info(f"✓ Modelo {model_name} accesible (registros: {count})")
        except Exception as e:
            _logger.error(f"✗ Error al acceder al modelo {model_name}: {e}")
            all_ok = False
    
    return all_ok


def test_sale_order_line_price_validation(env):
    """Verificar validación de precio vs costo en líneas de venta"""
    _logger.info("\n=== Prueba: Validación Precio vs Costo (Sale Order Line) ===")
    
    try:
        # Buscar un producto con costo
        product = env['product.product'].search([
            ('type', '=', 'product'),
            ('standard_price', '>', 0)
        ], limit=1)
        
        if not product:
            _logger.warning("⚠ No se encontró producto con costo para probar")
            return True
        
        # Buscar una orden de venta en borrador
        sale_order = env['sale.order'].search([
            ('state', '=', 'draft')
        ], limit=1)
        
        if not sale_order:
            # Crear una orden de prueba
            partner = env['res.partner'].search([], limit=1)
            if not partner:
                _logger.warning("⚠ No se encontró partner para crear orden de prueba")
                return True
            
            sale_order = env['sale.order'].create({
                'partner_id': partner.id,
            })
        
        # Crear línea con precio menor al costo (sin permiso de vender bajo costo)
        cost_price = product.standard_price
        test_price = cost_price - 1.0 if cost_price > 1.0 else 0.0
        
        # Verificar que el usuario actual no tenga permiso de vender bajo costo
        user_has_permission = env.user.has_group('l10n_hn_stock.group_allow_sell_below_cost')
        
        if not user_has_permission:
            try:
                line = env['sale.order.line'].create({
                    'order_id': sale_order.id,
                    'product_id': product.id,
                    'product_uom_qty': 1.0,
                    'price_unit': test_price,
                })
                _logger.error(f"✗ Se permitió crear línea con precio {test_price} menor al costo {cost_price}")
                line.unlink()
                return False
            except Exception as e:
                if "No puedes vender por debajo del costo" in str(e):
                    _logger.info(f"✓ Validación funcionando: se bloqueó precio {test_price} menor al costo {cost_price}")
                    return True
                else:
                    _logger.error(f"✗ Error inesperado: {e}")
                    return False
        else:
            _logger.info("⚠ Usuario tiene permiso de vender bajo costo, saltando prueba")
            return True
            
    except Exception as e:
        _logger.error(f"✗ Error en prueba de validación: {e}")
        return False


def test_stock_picking_remission_fields(env):
    """Verificar campos de guía de remisión en stock.picking"""
    _logger.info("\n=== Prueba: Campos de Guía de Remisión ===")
    
    try:
        picking = env['stock.picking'].search([], limit=1)
        
        if not picking:
            _logger.warning("⚠ No se encontró picking para probar")
            return True
        
        # Verificar que los campos existen
        fields_to_check = [
            'hn_remission_enabled',
            'salesperson_id',
            'invoice_name',
            'hn_remission_number',
        ]
        
        all_found = True
        for field_name in fields_to_check:
            if field_name in picking._fields:
                _logger.info(f"✓ Campo encontrado: {field_name}")
            else:
                _logger.error(f"✗ Campo NO encontrado: {field_name}")
                all_found = False
        
        # Probar método de generación de secuencia
        if picking.hn_remission_number:
            _logger.info(f"⚠ Picking ya tiene número de remisión: {picking.hn_remission_number}")
        else:
            try:
                # Solo probar si la secuencia existe
                sequence = env['ir.sequence'].search([('code', '=', 'hn.remission')], limit=1)
                if sequence:
                    picking.action_generate_remission_sequence()
                    if picking.hn_remission_number:
                        _logger.info(f"✓ Secuencia generada correctamente: {picking.hn_remission_number}")
                    else:
                        _logger.error("✗ No se generó el número de remisión")
                        all_found = False
                else:
                    _logger.warning("⚠ Secuencia hn.remission no configurada")
            except Exception as e:
                _logger.error(f"✗ Error al generar secuencia: {e}")
                all_found = False
        
        return all_found
        
    except Exception as e:
        _logger.error(f"✗ Error en prueba de campos de remisión: {e}")
        return False


def test_consume_product_model(env):
    """Verificar modelo consume.product"""
    _logger.info("\n=== Prueba: Modelo Consume Product ===")
    
    try:
        consume_model = env['consume.product']
        count = consume_model.search_count([])
        _logger.info(f"✓ Modelo consume.product accesible (registros: {count})")
        
        # Verificar campos principales
        fields_to_check = [
            'name',
            'picking_type_id',
            'is_incoming',
            'state',
            'consume_line',
        ]
        
        all_found = True
        for field_name in fields_to_check:
            if field_name in consume_model._fields:
                _logger.info(f"✓ Campo encontrado: {field_name}")
            else:
                _logger.error(f"✗ Campo NO encontrado: {field_name}")
                all_found = False
        
        return all_found
        
    except Exception as e:
        _logger.error(f"✗ Error en prueba de consume.product: {e}")
        return False


def run_all_tests(env):
    """Ejecutar todas las pruebas"""
    _logger.info("=" * 60)
    _logger.info("INICIANDO PRUEBAS FUNCIONALES - l10n_hn_stock")
    _logger.info("=" * 60)
    
    results = []
    
    # Ejecutar pruebas
    results.append(("Grupos de Seguridad", test_security_groups(env)))
    results.append(("Secuencias", test_sequences(env)))
    results.append(("Modelos", test_models(env)))
    results.append(("Validación Precio vs Costo", test_sale_order_line_price_validation(env)))
    results.append(("Campos Guía de Remisión", test_stock_picking_remission_fields(env)))
    results.append(("Modelo Consume Product", test_consume_product_model(env)))
    
    # Resumen
    _logger.info("\n" + "=" * 60)
    _logger.info("RESUMEN DE PRUEBAS")
    _logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        _logger.info(f"{status}: {test_name}")
    
    _logger.info(f"\nTotal: {passed}/{total} pruebas pasadas")
    
    if passed == total:
        _logger.info("🎉 ¡Todas las pruebas pasaron!")
    else:
        _logger.warning(f"⚠ {total - passed} prueba(s) fallaron")
    
    return passed == total

