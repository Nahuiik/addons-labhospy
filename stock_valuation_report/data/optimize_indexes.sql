-- ============================================================================
-- Índices optimizados para el reporte de valoración de inventario
-- Ejecutar una sola vez en la base de datos para mejorar rendimiento
-- ============================================================================

-- Índice para búsquedas por fecha y estado en stock_move_line
-- Mejora consultas que filtran por fecha y estado='done'
CREATE INDEX IF NOT EXISTS stock_move_line_date_state_done_idx 
    ON stock_move_line(date, state) 
    WHERE state = 'done';

-- Índice compuesto para ubicaciones y estado
-- Mejora consultas que filtran por location_id y location_dest_id
CREATE INDEX IF NOT EXISTS stock_move_line_locations_state_idx 
    ON stock_move_line(location_id, location_dest_id, state)
    WHERE state = 'done';

-- Índice para producto y estado
-- Mejora agrupaciones por producto
CREATE INDEX IF NOT EXISTS stock_move_line_product_state_idx 
    ON stock_move_line(product_id, state)
    WHERE state = 'done';

-- Índice compuesto para consultas del reporte
-- Combina las columnas más usadas en las consultas
CREATE INDEX IF NOT EXISTS stock_move_line_valuation_report_idx 
    ON stock_move_line(product_id, date, location_id, location_dest_id)
    WHERE state = 'done' AND location_id != location_dest_id;

-- Verificar índices creados
SELECT 
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename = 'stock_move_line'
  AND indexname LIKE '%valuation%' OR indexname LIKE '%date_state%' OR indexname LIKE '%locations_state%'
ORDER BY indexname;
