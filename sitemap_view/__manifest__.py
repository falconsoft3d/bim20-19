{
    'name': 'Sitemap View',
    'version': '18.0.1.0.0',
    'author': "Ynext",
    'maintainer': 'Ynext',
    'website': 'http://www.ynext.cl',
    'license': 'AGPL-3',
    'category': 'Extra Tools',
    'summary': 'Advanced tree view with sitemap features.',
    'depends': ['base','web'],
    'data': ['views/assets.xml'],
    'assets': {
        'web.assets_backend': [
            'sitemap_view/static/src/views/sitemap/*',
        ],
    },
}
