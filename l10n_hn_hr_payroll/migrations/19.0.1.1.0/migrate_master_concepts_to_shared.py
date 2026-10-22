# -*- coding: utf-8 -*-
# Migration script to convert hr.master.concept to hr.employee.recurring.concept (shared)

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Migrate hr.master.concept records to hr.employee.recurring.concept (shared concepts)"""
    
    # Check if hr.master.concept table exists
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'hr_master_concept'
        );
    """)
    
    if not cr.fetchone()[0]:
        _logger.info("Table hr_master_concept does not exist, skipping migration")
        return
    
    _logger.info("Starting migration of hr.master.concept to hr.employee.recurring.concept")
    
    # Get all master concepts
    cr.execute("""
        SELECT id, name, code, concept_type, amount_type, default_amount,
               is_loan, default_installments, applies_to_all, active, description
        FROM hr_master_concept
        WHERE active = true
    """)
    
    master_concepts = cr.fetchall()
    _logger.info(f"Found {len(master_concepts)} master concepts to migrate")
    
    migrated_count = 0
    for mc in master_concepts:
        mc_id, name, code, concept_type, amount_type, default_amount, \
        is_loan, default_installments, applies_to_all, active, description = mc
        
        # Check if a shared concept with this code already exists
        cr.execute("""
            SELECT id FROM hr_employee_recurring_concept
            WHERE code = %s AND employee_id IS NULL
        """, (code,))
        
        if cr.fetchone():
            _logger.warning(f"Shared concept with code '{code}' already exists, skipping master concept {mc_id}")
            continue
        
        # Create shared recurring concept
        cr.execute("""
            INSERT INTO hr_employee_recurring_concept 
            (name, code, concept_type, amount_type, amount, is_loan, installments, 
             total_amount, applies_to_all, active, description, date_start, create_uid, create_date, write_uid, write_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_DATE, 1, NOW(), 1, NOW())
            RETURNING id
        """, (name, code, concept_type, amount_type, default_amount or 0.0, 
              is_loan, default_installments if is_loan else 1,
              default_amount if is_loan else 0.0, applies_to_all, active, description))
        
        new_concept_id = cr.fetchone()[0]
        
        # Migrate department_ids
        cr.execute("""
            INSERT INTO hr_employee_recurring_concept_hr_department_rel (hr_employee_recurring_concept_id, hr_department_id)
            SELECT %s, hr_department_id
            FROM hr_master_concept_hr_department_rel
            WHERE hr_master_concept_id = %s
        """, (new_concept_id, mc_id))
        
        # Migrate job_ids
        cr.execute("""
            INSERT INTO hr_employee_recurring_concept_hr_job_rel (hr_employee_recurring_concept_id, hr_job_id)
            SELECT %s, hr_job_id
            FROM hr_master_concept_hr_job_rel
            WHERE hr_master_concept_id = %s
        """, (new_concept_id, mc_id))
        
        # Migrate structure_type_ids
        cr.execute("""
            INSERT INTO hr_employee_recurring_concept_hr_payroll_structure_type_rel (hr_employee_recurring_concept_id, hr_payroll_structure_type_id)
            SELECT %s, hr_payroll_structure_type_id
            FROM hr_master_concept_hr_payroll_structure_type_rel
            WHERE hr_master_concept_id = %s
        """, (new_concept_id, mc_id))
        
        migrated_count += 1
        _logger.info(f"Migrated master concept '{name}' (code: {code}) to shared recurring concept")
    
    _logger.info(f"Migration completed: {migrated_count} master concepts migrated to shared recurring concepts")
    
    # Note: We don't delete master concepts to preserve data integrity
    # They can be manually deleted after verifying the migration
