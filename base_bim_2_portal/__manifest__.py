{
    'name': 'Base Bim Portal MFH',
    'version': '19.0.1.0.0',
    'summary': 'Portal BIM para clientes',
    'sequence': 10,
    'description': """
Portal BIM
================================
Portal de clientes con dashboard y gestión de perfil
    """,
    'category': 'Extra Tools',
    'website': 'https://www.marlonfalcon.com',
    'depends': ['base', 'base_bim_2', 'portal', 'web'],
    'auto_install': False,
    'data': [
        'views/res_partner_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'base_bim_2_portal/static/src/css/portal_bim.css',
        ],
    },
    'license': 'LGPL-3',
}