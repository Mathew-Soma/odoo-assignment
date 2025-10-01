from odoo import models, fields

class PurchaseRFQBid(models.Model):
    _name = "purchase.rfq.bid"
    _description = "Supplier Bid"

    rfq_id = fields.Many2one(
        "purchase.order",   # RFQ is just purchase.order
        string="RFQ",
        ondelete="cascade"
    )
    partner_id = fields.Many2one("res.partner", string="Supplier")
    price = fields.Float(string="Bid Price")
    note = fields.Text(string="Notes")
