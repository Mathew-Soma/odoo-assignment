from odoo import models, fields, api
from odoo.exceptions import UserError

class PurchaseRFQBid(models.Model):
    _name = 'purchase.rfq.bid'
    _description = 'Supplier Bid for RFQ'

    name = fields.Char(string='Bid Reference', readonly=True)
    order_id = fields.Many2one('purchase.order', string='RFQ', ondelete='cascade', required=True)
    partner_id = fields.Many2one('res.partner', string='Vendor', required=True, domain=[('supplier_rank', '>', 0)])
    price_unit = fields.Float(string='Bid Price', required=True)
    delivery_days = fields.Integer(string='Delivery Days')
    remarks = fields.Text(string='Remarks')
    date_deadline = fields.Date(string='Bid Deadline')
    notes = fields.Text(string='Notes')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft')
    is_winner = fields.Boolean(string='Winning Bid', readonly=True)

    @api.model
    def create(self, vals):
        """Automatically name bids like 'Bid for PO0001 - VendorName'."""
        bid = super().create(vals)
        if bid.order_id and bid.partner_id:
            bid.name = f"Bid for {bid.order_id.name} - {bid.partner_id.name}"
        return bid

    def write(self, vals):
        """Ensure only one bid can be approved for an RFQ."""
        # Skip validation if called internally
        if not self.env.context.get('skip_validation'):
            for bid in self:
                if vals.get('state') == 'approved':
                    approved_bids = self.search([
                        ('order_id', '=', bid.order_id.id),
                        ('state', '=', 'approved'),
                        ('id', '!=', bid.id)
                    ])
                    if approved_bids:
                        raise UserError("Only one bid can be approved for this RFQ. Another bid is already approved.")

        res = super(PurchaseRFQBid, self).write(vals)

        # Handle winner logic, avoid recursion by using context flag
        if vals.get('state') == 'approved' and not self.env.context.get('skip_validation'):
            for bid in self:
                if bid.state == 'approved':
                    other_bids = self.search([
                        ('order_id', '=', bid.order_id.id),
                        ('id', '!=', bid.id)
                    ])
                    other_bids.with_context(skip_validation=True).sudo().write({
                        'is_winner': False,
                        'state': 'rejected'
                    })

                    bid.is_winner = True
                    bid.order_id.partner_id = bid.partner_id.id

        return res
