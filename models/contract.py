# -*- coding: utf-8 -*-
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import html2plaintext
from num2words import num2words


class RentalContractClauseLine(models.Model):
    _name = "rental.contract.clause.line"
    _description = "Cláusula en contrato"
    _order = "sequence, id"

    contract_id = fields.Many2one(
        "rental.contract",
        string="Contrato",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(string="Orden", default=10)
    selected = fields.Boolean(string="Incluir", default=True)
    title = fields.Char(string="Título")
    body = fields.Html(string="Texto", sanitize=True)

    template_id = fields.Many2one("rental.clause", string="Plantilla")
    template_editable = fields.Boolean(
        string="Editable por plantilla",
        related="template_id.is_editable",
        store=False,
    )

    # 👇 NUEVO: preview de texto para mostrar en el árbol
    body_preview = fields.Text(
        string="Vista previa",
        compute="_compute_body_preview",
        store=False,
    )

    @api.depends("body")
    def _compute_body_preview(self):
        for line in self:
            if line.body:
                # Pasamos HTML → texto plano
                text = html2plaintext(line.body) or ""
                text = text.strip().replace("\n", " ")
                # Recortamos a 120 caracteres (ajustable)
                if len(text) > 120:
                    text = text[:120] + "..."
                line.body_preview = text
            else:
                line.body_preview = False

    @api.onchange("template_id")
    def _onchange_template_id(self):
        for line in self:
            if not line.template_id:
                continue

            line.title = line.template_id.name
            template_body = line.template_id.body or ""

            if line.contract_id:
                # Reemplaza placeholders con datos de ESTE contrato
                line.body = line.contract_id._render_clause_body(template_body)
            else:
                # Si por alguna razón aún no está ligado a un contrato
                line.body = template_body


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
    penalty_amount = fields.Monetary("Multa", currency_field="currency_id", required=True)
    deposit_amount = fields.Monetary("Monto garantía", currency_field="currency_id", default=0.0)
    currency_id = fields.Many2one("res.currency", "Moneda", default=lambda self: self.env.company.currency_id)
    state = fields.Selection(
        [("draft", "Borrador"), ("active", "Activo"), ("closed", "Cerrado"), ("cancel", "Cancelado")],
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
            defaults = Clause.search(
                [("is_default", "=", True), ("active", "=", True)],
                order="sequence, name"
            )
            existing_titles = set(t for t in rec.clause_line_ids.mapped("title") if t)
            vals_list = []
            seq = 10
            for tpl in defaults:
                if tpl.name in existing_titles:
                    continue

                template_body = tpl.body or ""
                # 👉 AQUÍ usamos el helper para inyectar monto, fechas, multa, etc.
                rendered_body = rec._render_clause_body(template_body)

                vals_list.append({
                    "contract_id": rec.id,
                    "sequence": seq,
                    "selected": True,
                    "title": tpl.name,
                    "body": rendered_body,
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
        contracts = self.search([("state", "=", "active"), ("start_date", "<=", today)])
        for c in contracts:
            if c.end_date and c.end_date < today:
                continue
            first_day = date(today.year, today.month, 1)
            last_day = first_day + relativedelta(months=1, days=-1)
            existing = self.env["account.move"].search_count([
                ("rental_contract_id", "=", c.id),
                ("move_type", "=", "out_invoice"),
                ("invoice_date", ">=", first_day),
                ("invoice_date", "<=", last_day),
                ("state", "in", ["draft", "posted"]),
            ])
            if existing:
                continue
            inv_date = c._next_period_invoice_date(today)
            if inv_date < c.start_date:
                continue
            c._create_out_invoice(amount=c.rent_amount,
                                  description=_("Alquiler mensual %s") % inv_date.strftime("%Y-%m"))

    # --- Reporte
    def action_print_full_pdf(self):
        self.ensure_one()
        return self.env.ref("sga_property_rental.report_contract_full").report_action(self)

    """def _amount_to_text_es(self, amount, currency_name=None):
        COMENTARIO: Convierte un monto numérico a texto en español, opcionalmente con nombre de moneda.
        self.ensure_one()
        if not amount:
            return ""

        # Redondeamos al entero (para contratos suele ser sin decimales)
        integer = int(round(float(amount)))

        # Texto en español: "un millón doscientos mil"
        words = num2words(integer, lang="es")

        # Nombre de moneda: usamos el nombre de la moneda del contrato si no se pasa
        if currency_name is None:
            currency_name = (self.currency_id and self.currency_id.name) or ""

        currency_name = (currency_name or "").strip()
        if currency_name:
            return f"{words} {currency_name.lower()}"
        return words"""

    def _amount_to_text_es(self, amount, currency_name=None):
        """Convierte un monto numérico a texto en español (sin nombre de moneda)."""
        self.ensure_one()
        if not amount:
            return ""

        integer = int(round(float(amount)))
        # Ej: "un millón doscientos mil"
        words = num2words(integer, lang="es")
        return words

    def _render_clause_body(self, template_body):
        """Reemplaza placeholders {{...}} del cuerpo de la cláusula con datos del contrato."""
        self.ensure_one()
        body = template_body or ""

        # ===== Fechas =====
        start_str = ""
        end_str = ""
        if self.start_date:
            start_str = self.start_date.strftime("%d/%m/%Y")
        if self.end_date:
            end_str = self.end_date.strftime("%d/%m/%Y")

        # ===== Monto de alquiler =====
        rent_str = ""
        rent_text = ""
        rent_full = ""
        if self.rent_amount:
            symbol = (self.currency_id and self.currency_id.symbol) or "Gs"
            amount = float(self.rent_amount)
            rent_str = ("%s %s" % (symbol, "{:,.0f}".format(amount))).replace(",", ".")
            # Si tenés _amount_to_text_es, lo usamos
            try:
                rent_text = self._amount_to_text_es(self.rent_amount)
            except Exception:
                rent_text = ""
            if rent_str and rent_text:
                rent_full = f"{rent_str} ({rent_text})"
            else:
                rent_full = rent_str or rent_text

        # ===== Multa diaria =====
        penalty_str = ""
        penalty_text = ""
        penalty_full = ""
        if getattr(self, "penalty_amount", False):
            symbol = (self.currency_id and self.currency_id.symbol) or "Gs"
            amount = float(self.penalty_amount)
            penalty_str = ("%s %s" % (symbol, "{:,.0f}".format(amount))).replace(",", ".")
            try:
                penalty_text = self._amount_to_text_es(self.penalty_amount)
            except Exception:
                penalty_text = ""
            if penalty_str and penalty_text:
                penalty_full = f"{penalty_str} ({penalty_text})"
            else:
                penalty_full = penalty_str or penalty_text

        # ===== Depósito =====
        deposit_str = ""
        deposit_text = ""
        deposit_full = ""
        if getattr(self, "deposit_amount", False):
            symbol = (self.currency_id and self.currency_id.symbol) or "Gs"
            amount = float(self.deposit_amount)
            deposit_str = ("%s %s" % (symbol, "{:,.0f}".format(amount))).replace(",", ".")
            try:
                deposit_text = self._amount_to_text_es(self.deposit_amount)
            except Exception:
                deposit_text = ""
            if deposit_str and deposit_text:
                deposit_full = f"{deposit_str} ({deposit_text})"
            else:
                deposit_full = deposit_str or deposit_text

        # ===== Datos del agente inmobiliario =====
        agent_name = ""
        agent_vat = ""
        agent_phone = ""
        agent_email = ""
        agent_full = ""

        if getattr(self, "agent_id", False) and self.agent_id:
            agent_name = self.agent_id.display_name or ""
            agent_vat = self.agent_id.vat or ""
            agent_phone = self.agent_id.mobile or self.agent_id.phone or ""
            agent_email = self.agent_id.email or ""

            parts = []
            if agent_name:
                parts.append(agent_name)
            if agent_vat:
                parts.append("con C.I./RUC N° %s" % agent_vat)
            if agent_phone:
                parts.append("tel. %s" % agent_phone)
            if agent_email:
                parts.append("email %s" % agent_email)

            agent_full = ", ".join(parts)

        # ===== Diccionario de placeholders =====
        placeholders = {
            "{{START_DATE}}": start_str,
            "{{END_DATE}}": end_str,

            "{{RENT_AMOUNT}}": rent_str,
            "{{RENT_AMOUNT_TEXT}}": rent_text,
            "{{RENT_AMOUNT_FULL}}": rent_full,

            "{{PENALTY_AMOUNT}}": penalty_str,
            "{{PENALTY_AMOUNT_TEXT}}": penalty_text,
            "{{PENALTY_AMOUNT_FULL}}": penalty_full,

            "{{DEPOSIT_AMOUNT}}": deposit_str,
            "{{DEPOSIT_AMOUNT_TEXT}}": deposit_text,
            "{{DEPOSIT_AMOUNT_FULL}}": deposit_full,

            "{{AGENT_NAME}}": agent_name,
            "{{AGENT_VAT}}": agent_vat,
            "{{AGENT_PHONE}}": agent_phone,
            "{{AGENT_EMAIL}}": agent_email,
            "{{AGENT_FULL}}": agent_full,
        }

        for key, value in placeholders.items():
            body = body.replace(key, value or "")

        return body

    def action_refresh_clauses(self):
        """Vuelve a generar el texto de las cláusulas desde la plantilla + datos actuales del contrato."""
        for rec in self:
            for line in rec.clause_line_ids:
                if line.template_id:
                    template_body = line.template_id.body or ""
                    line.body = rec._render_clause_body(template_body)
        return True
