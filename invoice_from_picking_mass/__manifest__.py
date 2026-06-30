##############################################################################
#
#    OpenERP, Open Source Management Solution
#    This module copyright (C) 2018 Marlon Falcón Hernandez
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
    'name': 'Invoice From Picking Mass MFH',
    'version': '19.0.1.0.0',
    'author': 'Ynext SpA',
    'maintainer': 'Ynext SpA',
    'website': 'http://www.ynext.cl',
    'license': 'AGPL-3',
    'category': 'Extra Tools',
    'summary': 'Invoice From Picking Mass.',
    'depends': [
        'base',
        'account',
        'stock',
        'sale',
        'purchase',
        'picking_standard_price',
        'base_bim_2',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/data_invoice_from_picking.xml',
        'views/invoice_from_picking_mass_views.xml',
        'views/stock_picking_views.xml',
        'views/account_move_views.xml',
        'wizard/invoice_from_picking_mass_wzd_views.xml'
    ],
    'images': ['static/description/banner.jpg'],
}
