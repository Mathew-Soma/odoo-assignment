
{
    "name": "Purchase Request App",
    "version": "1.0.0",
    "summary": "Employees submit purchase requests that generate RFQs",
    "category": "Purchases",
    "author": "Mathew Soma",
    "license": "LGPL-3",
    "depends": ["base", "purchase", "product"],
    "data": [
        "security/purchase_request_security.xml",
        "security/ir.model.access.csv",
        "data/purchase_request_sequence.xml",
        "views/purchase_request_menu.xml",
        "views/purchase_request_views.xml",
    ],
    "installable": True,
    "application": True,
}
