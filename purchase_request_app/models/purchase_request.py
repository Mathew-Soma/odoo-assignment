from odoo import models, fields, api
from odoo.exceptions import UserError

class PurchaseRequest(models.Model):
    _name = "purchase.request"
    _description = "Purchase Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    _sql_constraints = [
        ('unique_name', 'unique(name)', 'The Purchase Request Reference must be unique!')
    ]

    vendor_ids = fields.Many2many(
        'res.partner',
        string='Add Vendors',
        domain=[('supplier_rank', '>', 0)]
    )

    name = fields.Char(
        string="Request Reference",
        required=True,
        copy=False,
        readonly=True,
        default="New"
    )
    employee_id = fields.Many2one("hr.employee", string="Requested By", tracking=True)
    department_id = fields.Many2one("hr.department", string="Department")
    request_date = fields.Date(default=fields.Date.today)
    line_ids = fields.One2many("purchase.request.line", "request_id", string="Request Lines")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('to_rfq', 'RFQ Created'),
        ('cancelled', 'Cancelled')
    ], default="draft", tracking=True)

    rfq_id = fields.Many2one("purchase.order", string="Generated RFQ", readonly=True)

    @api.model
    def create(self, vals):
        # Generate unique reference
        if vals.get("name", "New") == "New":
            vals["name"] = self.env["ir.sequence"].next_by_code("purchase.request") or "New"

        # Check uniqueness
        if self.search([('name', '=', vals["name"])]):
            raise UserError("The generated Purchase Request Reference already exists. Please try again.")

        return super().create(vals)
    
    def pending_info(self):
        # This button is only informational, so do nothing
        return True
    
    def approved_info(self):
        self.state = 'Approved'



    # Employee submits
    def action_submit(self):
        if not self.env.user.has_group('purchase_request_app.group_purchase_request_employee'):
            raise UserError("Only Employees can submit purchase requests.")
        self.write({"state": "submitted"})
        return self.env.ref('purchase_request_app.action_purchase_request').sudo().read()[0]

    # Procurement Officer approves
    def action_approve(self):
        if not self.env.user.has_group('purchase_request_app.group_procurement_officer'):
            raise UserError("Only Procurement Officers can approve requests.")

        approved_lines = self.line_ids.filtered(lambda l: l.feedback == 'approved')
        if not approved_lines:
            raise UserError("Cannot approve the purchase request. At least one product must be approved.")

        self.write({"state": "approved"})

    # Create RFQ draft (with dummy vendor)
    def action_create_rfq(self):
        if not self.env.user.has_group('purchase_request_app.group_procurement_officer'):
            raise UserError("Only Procurement Officers can create RFQs.")

        dummy_vendor = self.env['res.partner'].search([('name', '=', 'vendors')], limit=1)
        if not dummy_vendor:
            dummy_vendor = self.env['res.partner'].create({'name': 'vendors ', 'supplier_rank': 1})

        for request in self:
            approved_lines = request.line_ids.filtered(lambda l: l.feedback == 'approved')
            if not approved_lines:
                raise UserError("No approved product lines found. Cannot create an RFQ.")

            rfq_vals = {
                "origin": request.name,
                "partner_id": dummy_vendor.id,  
                "state": "draft",
            }
            rfq = self.env["purchase.order"].create(rfq_vals)

            # Add approved lines
            for line in approved_lines:
                self.env["purchase.order.line"].create({
                    "order_id": rfq.id,
                    "product_id": line.product_id.id,
                    "name": line.description or line.product_id.display_name,
                    "product_qty": line.quantity,
                    "price_unit": 0.0,
                    "date_planned": fields.Datetime.now(),
                })

            request.rfq_id = rfq.id
            request.state = "to_rfq"

    def action_done(self):
        if not self.env.user.has_group('purchase_request_app.group_procurement_officer'):
            raise UserError("Only Procurement Officers can mark as done.")
        self.write({"state": "done"})

    def action_cancel(self):
        self.write({"state": "cancelled"})


class PurchaseRequestLine(models.Model):
    _name = "purchase.request.line"
    _description = "Purchase Request Line"

    request_id = fields.Many2one("purchase.request", string="Purchase Request", ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Product", required=True)
    description = fields.Char(string="Description")
    quantity = fields.Float(string="Quantity", required=True)

    feedback = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('instock', 'Instock'),
        ('rejected', 'Rejected'),
    ], string='Feedback', default='draft')

    def write(self, vals):
        if 'feedback' in vals and not self.env.user.has_group('purchase_request_app.group_procurement_officer'):
            vals.pop('feedback')
        return super().write(vals)

    def create(self, vals):
        if 'feedback' in vals and not self.env.user.has_group('purchase_request_app.group_procurement_officer'):
            vals.pop('feedback')
        return super().create(vals)


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    vendor_ids = fields.Many2many(
        "res.partner",
        string="Vendors",
        domain=[("supplier_rank", ">", 0)],
        help="Vendors linked to this RFQ from the Purchase Request."
    )

    def button_confirm(self):
        for order in self:
            if not order.vendor_ids:
                raise UserError("Please select at least one vendor before confirming this RFQ.")
        return super().button_confirm()
    
