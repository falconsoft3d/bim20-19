{
    'name': 'Hide Chat MFH',
    'version' : '1.4',
    'summary': 'Toggle Chatter Visibility',
    'sequence': 10,
    'description': """
Hide Chatter
================================
Agrega un botón en la barra superior para mostrar/ocultar el chatter.
La preferencia se guarda en localStorage del navegador.
    """,
    'category': 'Extra Tools',
    'website': 'https://www.marlonfalcon.com',
    'depends': ['base', 'web', 'mail'],
    'auto_install': False,
    'data': [
        'views/view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hide_chat/static/src/css/hide_chatter.css',
            'hide_chat/static/src/js/hide_chatter.js',
            'hide_chat/static/src/xml/hide_chatter.xml',
        ],
    },
    'license': 'LGPL-3',
    'author': 'Marlon Falcon Hernandez.',
    'images': ['images/main.png'],
}