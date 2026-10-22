# -*- coding: utf-8 -*-

from odoo import models, api

class ResCountryState(models.Model):
    _inherit = 'res.country.state'

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Personaliza la búsqueda de nombres para mostrar primero los departamentos de Honduras"""
        args = args or []
        context = dict(self.env.context or {})
        
        # Si estamos en el contexto de priorizar Honduras
        if context.get('hn_first'):
            # Obtener el ID del país Honduras
            hn_country_id = self.env.ref('base.hn').id
            
            # Obtener el país del contexto si está disponible
            country_id = context.get('country_id')
            
            # Si no hay país seleccionado o el país es Honduras
            if not country_id or country_id == hn_country_id:
                # Buscar primero los departamentos de Honduras
                hn_states = self.search([('country_id', '=', hn_country_id), 
                                         ('name', operator, name)], limit=limit)
                
                # Obtener los resultados en el formato correcto para name_search
                hn_result = [(state.id, state.name) for state in hn_states]
                
                # Si encontramos todos los resultados necesarios, devolver solo esos
                if limit and len(hn_result) >= limit:
                    return hn_result

                # Si necesitamos más resultados, buscar en otros países
                other_args = args + [('country_id', '!=', hn_country_id)]
                if limit:
                    limit2 = limit - len(hn_result)
                    if limit2:
                        other_result = super(ResCountryState, self).name_search(
                            name, other_args, operator, limit=limit2)
                        return hn_result + other_result
                    return hn_result

                other_result = super(ResCountryState, self).name_search(
                    name, other_args, operator, limit=limit)
                return hn_result + other_result
        
        # Comportamiento estándar si no estamos priorizando Honduras
        return super(ResCountryState, self).name_search(name, args, operator, limit=limit)
