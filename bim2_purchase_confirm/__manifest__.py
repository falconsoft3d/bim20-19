{
    'name': 'Bim2 Purchase Confirm MFH',
    'version': '19.0.1.0.0',
    'summary': 'Invoices & Payments',
    'sequence': 10,
    'description': """
Father (TOTP)
================================
Allows users to configure
    """,
    'category': 'Accounting/Accounting',
    'website': 'https://www.marlonfalcon.com',
    'depends': ['base_bim_2','purchase'],
    'category': 'Extra Tools',
    'auto_install': False,
    'data': [
        'views/purchase_views.xml',
        'report/purchase_order_templates.xml',
    ],
    'license': 'LGPL-3',
}