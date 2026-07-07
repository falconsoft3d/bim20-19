# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
##############################################################################
#
#    BIM 2.0 - Portal Customer Odoo
#    This module copyright (C) 2026 Marlon Falcón Hernandez
#    (<http://www.bim20.com>).
#
##############################################################################
{
    'name': 'BIM Portal Customer Odoo',
    'version': '19.0.1.0.0',
    'author': 'Marlon Falcon Hernandez',
    'maintainer': 'Marlon Falcon Hernandez',
    'website': 'http://www.bim20.com',
    'license': 'AGPL-3',
    'category': 'Construction',
    'summary': 'Portal de clientes BIM - Configuración Odoo',
    'description': """
        Módulo Odoo para gestionar los accesos del portal de clientes BIM.
        - Pestaña Portal en res.partner con login, estado y responsable.
        - Wizard para generar contraseña segura (almacenada encriptada).
        - Controlador JSON-RPC para autenticación desde Next.js.
    """,
    'depends': [
        'base',
        'mail',
        'base_bim_2',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/bim_portal_password_wizard_views.xml',
        'views/res_partner_views.xml',
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
}