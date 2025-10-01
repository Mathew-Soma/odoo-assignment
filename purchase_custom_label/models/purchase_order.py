from odoo import models, fields, api

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    bid_ids = fields.One2many('purchase.rfq.bid', 'rfq_id', string="Bids")

    vendor_ids = fields.Many2many(
        'res.partner',
        'purchase_order_vendor_rel',
        'order_id',
        'partner_id',
        string="Vendors",
        domain=[('supplier_rank', '>', 0)]
    )

    @api.model
    def create(self, vals):
        """When creating an RFQ with multiple vendors, generate separate RFQs"""
        vendor_ids = vals.get('vendor_ids')
        if vendor_ids:
            rfqs = []
            # vendor_ids is a list of (6, 0, [ids]) or (4, id) commands
            if isinstance(vendor_ids[0], (list, tuple)) and vendor_ids[0][0] == 6:
                vendor_ids = vendor_ids[0][2]
            else:
                vendor_ids = [vid[1] for vid in vendor_ids if vid[0] == 4]

            for partner_id in vendor_ids:
                new_vals = vals.copy()
                new_vals['partner_id'] = partner_id
                # each RFQ has only one vendor
                new_vals.pop('vendor_ids', None)
                rfq = super(PurchaseOrder, self).create(new_vals)
                rfqs.append(rfq)
            return rfqs[0] if rfqs else super(PurchaseOrder, self).create(vals)

        return super(PurchaseOrder, self).create(vals)
