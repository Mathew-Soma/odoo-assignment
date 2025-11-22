{
    'name': 'Multi Vendor RFQ',
    'version': '1.0',
    'depends': ['purchase'],
    'data': [
        'security/ir.model.access.csv',
        'views/purchase_rfq_bid_view.xml',   
        'views/purchase_order_view.xml',
    ],
    'installable': True,
    'application': False,
}
