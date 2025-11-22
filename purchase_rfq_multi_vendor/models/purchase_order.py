from odoo import models, fields, api
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    partner_ids = fields.Many2many(
        'res.partner',
        'purchase_order_vendor_rel',
        'order_id',
        'partner_id',
        string="Vendors",
        domain=[('supplier_rank', '>', 0)],
        help="Select multiple vendors to send this RFQ to."
    )

    bid_ids = fields.One2many(
        'purchase.rfq.bid',
        'order_id',
        string="Vendor Bids"
    )
    winning_vendor_id = fields.Many2one(
    'res.partner',
    string="Winning Bid",
    compute="_compute_winning_vendor",
    store=True,
)


    # ------------------------
    # CREATE OVERRIDE
    # ------------------------
    @api.model
    def create(self, vals):
        if vals.get('origin'):
            return super().create(vals)

        partner_ids_val = vals.get('partner_ids')
        if not partner_ids_val:
            raise UserError("You must select at least one vendor before saving this RFQ.")

        vendor_ids = []
        if isinstance(partner_ids_val[0], (list, tuple)) and partner_ids_val[0][0] == 6:
            vendor_ids = partner_ids_val[0][2]
        else:
            vendor_ids = [cmd[1] for cmd in partner_ids_val if isinstance(cmd, (list, tuple)) and cmd[0] == 4]

        if not vendor_ids:
            raise UserError("You must select at least one vendor before saving this RFQ.")

        vals['partner_id'] = vendor_ids[0]
        record = super(PurchaseOrder, self).create(vals)
        record.partner_ids = [(6, 0, vendor_ids)]
        return record

    def button_confirm(self):
        for order in self:
            if not order.bid_ids:
                raise UserError("No bids have been received for this RFQ.")

            # Find approved bids
            approved_bids = order.bid_ids.filtered(lambda b: b.state == 'approved')

            # Validation
            if len(approved_bids) == 0:
                raise UserError("You must approve at least one bid before confirming this RFQ.")
            elif len(approved_bids) > 1:
                raise UserError("Only one bid can be approved as the winning bid for this RFQ.")

            # Use the single approved bid as the winner
            winning_bid = approved_bids[0]
            winning_bid.is_winner = True
            winning_vendor = winning_bid.partner_id

            # Create Purchase Order
            po_vals = {
                'partner_id': winning_vendor.id,
                'origin': order.name,
                'order_line': [],
            }

            for line in order.order_line:
                po_vals['order_line'].append((0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.name,
                    'product_qty': line.product_qty,
                    'product_uom': line.product_uom.id,
                    'price_unit': winning_bid.price_unit or line.price_unit,
                    'date_planned': line.date_planned,
                }))

            po = self.env['purchase.order'].create(po_vals)
            po.message_post(
                body=(
                    f"Purchase Order automatically generated from RFQ <b>{order.name}</b> "
                    f"for winning vendor <b>{winning_vendor.name}</b> at price {winning_bid.price_unit}."
                )
            )

            order.state = 'done'
            order.winning_vendor_id = winning_vendor.id

        return True

    def action_send_multi_vendor_email(self):
        ''' Opens a wizard to compose an email, with the edi purchase template message loaded by default '''
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        try:
            if self.company_id.use_rfq_report:
                template_id = ir_model_data.get_object_reference('purchase', 'email_template_edi_purchase_rfq')[1]
            else:
                template_id = ir_model_data.get_object_reference('purchase', 'email_template_edi_purchase')[1]
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data.get_object_reference('mail', 'email_compose_message_wizard_form')[1]
        except ValueError:
            compose_form_id = False

        ctx = {
            'default_model': 'purchase.order',
            'default_res_id': self.id,
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'mass_mail' if len(self.partner_ids) > 1 else 'comment',
            'mark_rfq_as_sent': True,
            'custom_layout': "mail.mail_notification_paynow",
            'force_email': True
        }

        # Modify the context to include multiple recipients
        if self.partner_ids:
            ctx['default_partner_ids'] = self.partner_ids.ids  # Pass the IDs of the partners
            ctx['default_email_layout_xmlid'] = 'mail.mail_notification_paynow'

        return {
            'name': ('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }

    def _notify_get_recipients_classify(
        self, message, msg_vals=False, model_description=False, mail_notify_type=False, **kwargs
    ):
        self.ensure_one()

        # Get Odoo's default classification (so you don’t break other logic)
        recipients = super()._notify_get_recipients_classify(
            message, msg_vals=msg_vals, model_description=model_description,
            mail_notify_type=mail_notify_type, **kwargs
        )

        # Add your custom logic (e.g. ensure vendors with emails receive mail)
        for partner in self.partner_ids.filtered(lambda p: p.email):
            recipients.append({
                'notif': 'email',
                'partner': partner,
                'share': False,
                'active': True,
            })

        return recipients

    
    @api.depends('bid_ids.state', 'bid_ids.is_winner')
    def _compute_winning_vendor(self):
        for order in self:
            winning_bid = order.bid_ids.filtered(lambda b: b.state == 'approved' and b.is_winner)
            order.winning_vendor_id = winning_bid[0].partner_id.id if winning_bid else False

