# -*- coding: utf-8 -*-
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

# === NUEVO: líneas de cláusulas por contrato ===
class RentalContractClauseLine(models.Model):
    _name = "rental.contract.clause.line"
    _description = "Cláusula en contrato"
    _order = "sequence, id"

    contract_id = fields.Many2one("rental.contract", string="Contrato", required=True, ondelete="cascade")
    sequence = fields.Integer(string="Orden", default=10)
    selected = fields.Boolean(string="Incluir", default=True)
    title = fields.Char(string="Título")
    body = fields.Html(string="Texto", sanitize=True)
    # guarda referencia a la plantilla para saber si es editable
    template_id = fields.Many2one("rental.clause", string="Plantilla")
    template_editable = fields.Boolean(string="Editable por plantilla", related="template_id.is_editable", store=False)

class RentalContract(models.Model):
    _name = "rental.contract"
    _description = "Contrato de Alquiler"
    _order = "id desc"

    name = fields.Char(
        "Número", required=True, copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code("rental.contract")
    )
    property_id = fields.Many2one("rental.property", "Propiedad", required=True)
    tenant_id = fields.Many2one("res.partner", "Inquilino", required=True)
    agent_id = fields.Many2one("res.partner", "Agente Inmobiliario")
    start_date = fields.Date("Fecha inicio", required=True)
    end_date = fields.Date("Fecha fin")
    day_due = fields.Integer("Día de vencimiento (1-28)", required=True, default=5)
    rent_amount = fields.Monetary("Monto mensual", currency_field="currency_id", required=True)
    deposit_amount = fields.Monetary("Monto garantía", currency_field="currency_id", default=0.0)
    currency_id = fields.Many2one("res.currency", "Moneda", default=lambda self: self.env.company.currency_id)
    state = fields.Selection(
        [("draft","Borrador"),("active","Activo"),("closed","Cerrado"),("cancel","Cancelado")],
        default="draft"
    )
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    invoice_ids = fields.One2many("account.move", "rental_contract_id", string="Facturas (al inquilino)")
    vendor_bill_ids = fields.One2many("account.move", "rental_contract_vendor_id", string="Facturas (proveedores)")
    attachment_ids = fields.Many2many("ir.attachment", string="Adjuntos (contrato firmado y documentos)")

    # === NUEVO: cláusulas (por contrato)
    clause_line_ids = fields.One2many("rental.contract.clause.line", "contract_id", string="Cláusulas")

    _sql_constraints = [
        ("day_due_range", "CHECK(day_due>=1 AND day_due<=28)", "El día de vencimiento debe estar entre 1 y 28."),
    ]

    # --- Acciones de estado
    def action_activate(self):
        for rec in self:
            if rec.state != "draft":
                continue
            if rec.deposit_amount:
                rec._create_out_invoice(amount=rec.deposit_amount, description=_("Depósito de garantía"))
            rec.state = "active"

    def action_close(self):
        for rec in self:
            if rec.state != "active":
                continue
            rec.state = "closed"

    # --- Utilidades de cláusulas
    def action_add_clause_line(self):
        for rec in self:
            self.env["rental.contract.clause.line"].create({
                "contract_id": rec.id,
                "sequence": 10,
                "selected": True,
                "title": _("Nueva cláusula"),
                "body": "",
            })
        return True

    def action_load_default_clauses(self):
        """Carga plantillas marcadas como is_default y no duplica títulos ya cargados."""
        for rec in self:
            Clause = self.env["rental.clause"].sudo()
            defaults = Clause.search([("is_default", "=", True), ("active", "=", True)], order="sequence, name")
            # para evitar duplicar por título
            existing_titles = set(t for t in rec.clause_line_ids.mapped("title") if t)
            vals_list = []
            seq = 10
            for tpl in defaults:
                if tpl.name in existing_titles:
                    continue
                vals_list.append({
                    "contract_id": rec.id,
                    "sequence": seq,
                    "selected": True,
                    "title": tpl.name,
                    "body": tpl.body or "",
                    "template_id": tpl.id,
                })
                seq += 10
            if vals_list:
                self.env["rental.contract.clause.line"].create(vals_list)
        return True

    # --- Facturación
    def _create_out_invoice(self, amount, description):
        self.ensure_one()
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.tenant_id.id,
            "invoice_date": fields.Date.context_today(self),
            "invoice_origin": self.name,
            "rental_contract_id": self.id,
            "rental_property_id": self.property_id.id,
            "invoice_line_ids": [(0, 0, {
                "name": description,
                "quantity": 1.0,
                "price_unit": amount,
            })],
        })
        return move

    def _next_period_invoice_date(self, base_date=None):
        self.ensure_one()
        base = base_date or fields.Date.context_today(self)
        due_month = base if base.day <= self.day_due else (base + relativedelta(months=1))
        return date(due_month.year, due_month.month, self.day_due)

    def cron_generate_monthly_rents(self):
        today = fields.Date.context_today(self)
        contracts = self.search([("state","=","active"), ("start_date","<=",today)])
        for c in contracts:
            if c.end_date and c.end_date < today:
                continue
            first_day = date(today.year, today.month, 1)
            last_day = first_day + relativedelta(months=1, days=-1)
            existing = self.env["account.move"].search_count([
                ("rental_contract_id","=",c.id),
                ("move_type","=","out_invoice"),
                ("invoice_date",">=",first_day),
                ("invoice_date","<=",last_day),
                ("state","in",["draft","posted"]),
            ])
            if existing:
                continue
            inv_date = c._next_period_invoice_date(today)
            if inv_date < c.start_date:
                continue
            c._create_out_invoice(amount=c.rent_amount, description=_("Alquiler mensual %s") % inv_date.strftime("%Y-%m"))

    # --- Reporte
    def action_print_full_pdf(self):
        self.ensure_one()
        return self.env.ref("sga_property_rental.report_contract_full").report_action(self)
