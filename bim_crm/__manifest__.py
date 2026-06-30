# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    This module copyright (C) 2017 Marlon Falcón Hernandez
#    (<http://www.ynext.cl>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name': 'CRM BIM 2.0',
    'version': '19.0.1.0.0',
    'author': "Ynext",
    'maintainer': 'Ynext',
    'website': 'http://www.ynext.cl',
    'license': 'AGPL-3',
    'category': 'Construction',
    'summary': 'Módulo de CRM para BIM',
    'depends': [
        'base',
        'crm',
        'base_bim_2'
    ],
    'description': """
BIM 2.0
============================
* CRM
        """,
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'views/crm_lead_views.xml',
        'views/bim_typology_views.xml',
        'views/bim_project_unit_views.xml',
        'views/bim_project_unit_typology_price_views.xml',
        'views/bim_budget_extra_views.xml',
        'views/bim_budget_sample_views.xml',
        'views/menu.xml',
        'views/bim_project.xml',
        'views/bim_budget_views.xml',
        'views/crm_stage_views.xml',
        'views/budget_request_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'demo': [],
    'test': [],
}
