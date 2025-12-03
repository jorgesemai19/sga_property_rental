# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class RentalInvoiceReportWizard(models.TransientModel):
    _name = "rental.invoice.report.wizard"
    _description = "Wizard reportes de facturas de clientes"

    report_type = fields.Selection(
        [
            ("to_collect", "Facturas de clientes a cobrar"),
            ("paid", "Facturas de clientes cobradas"),
        ],
        string="Tipo de reporte",
        required=True,
        default="to_collect",
    )
    date_from = fields.Date(string="Desde", required=True)
    date_to = fields.Date(string="Hasta", required=True)

    def _get_invoices(self):
        """Devuelve las facturas de cliente según tipo y rango de fechas."""
        self.ensure_one()
        domain = [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("invoice_date", ">=", self.date_from),
            ("invoice_date", "<=", self.date_to),
        ]
        if self.report_type == "to_collect":
            domain.append(("payment_state", "in", ["not_paid", "partial"]))
        else:
            domain.append(("payment_state", "=", "paid"))
        return self.env["account.move"].search(domain, order="invoice_date, name")

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref(
            "sga_property_rental.report_invoice_rental_wizard"
        ).report_action(self)


class RentalVendorInvoiceReportWizard(models.TransientModel):
    _name = "rental.vendor.invoice.report.wizard"
    _description = "Wizard reportes de facturas de proveedor"

    report_type = fields.Selection(
        [
            ("to_collect", "Facturas de proveedor a pagar"),
            ("paid", "Facturas de proveedor pagadas"),
        ],
        string="Tipo de reporte",
        required=True,
        default="to_collect",
    )
    date_from = fields.Date(string="Desde", required=True)
    date_to = fields.Date(string="Hasta", required=True)

    def _get_invoices(self):
        """Devuelve las facturas de proveedor según tipo y rango de fechas."""
        self.ensure_one()
        domain = [
            ("move_type", "=", "in_invoice"),
            ("state", "=", "posted"),
            ("invoice_date", ">=", self.date_from),
            ("invoice_date", "<=", self.date_to),
        ]
        if self.report_type == "to_collect":
            domain.append(("payment_state", "in", ["not_paid", "partial"]))
        else:
            domain.append(("payment_state", "=", "paid"))
        return self.env["account.move"].search(domain, order="invoice_date, name")

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref(
            "sga_property_rental.report_vendor_invoice_rental_wizard"
        ).report_action(self)
