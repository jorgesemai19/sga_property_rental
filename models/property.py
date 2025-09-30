# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class RentalProperty(models.Model):
    _name = "rental.property"
    _description = "Propiedad (Inmueble)"

    name = fields.Char("Nombre/Identificador", required=True)
    street = fields.Char("Dirección")
    city = fields.Char("Ciudad")
    state_id = fields.Many2one("res.country.state", "Estado/Departamento")
    country_id = fields.Many2one("res.country", "País", default=lambda self: self.env.company.country_id)
    owner_id = fields.Many2one("res.partner", "Propietario", required=True)
    image_1920 = fields.Image("Imagen")  # v18 friendly
    inventory_ids = fields.One2many("rental.property.inventory", "property_id", string="Inventarios")
    active = fields.Boolean(default=True)

    contract_ids = fields.One2many("rental.contract", "property_id", string="Contratos")
    current_contract_id = fields.Many2one(
        "rental.contract", string="Contrato vigente", compute="_compute_current_contract", store=False
    )

    @api.depends("contract_ids.state", "contract_ids.start_date", "contract_ids.end_date")
    def _compute_current_contract(self):
        today = fields.Date.context_today(self)
        for rec in self:
            active_contract = rec.contract_ids.filtered(
                lambda c: c.state == 'active' and c.start_date <= today and (not c.end_date or c.end_date >= today)
            )[:1]
            rec.current_contract_id = active_contract.id if active_contract else False


class RentalPropertyInventory(models.Model):
    _name = "rental.property.inventory"
    _description = "Inventario por fecha"
    _order = "date desc"

    property_id = fields.Many2one("rental.property", "Propiedad", required=True, ondelete="cascade")
    date = fields.Date("Fecha", required=True, default=fields.Date.context_today)
    note = fields.Text("Observaciones")
    line_ids = fields.One2many("rental.property.inventory.line", "inventory_id", "Items")


class RentalPropertyInventoryLine(models.Model):
    _name = "rental.property.inventory.line"
    _description = "Item de Inventario"

    inventory_id = fields.Many2one("rental.property.inventory", "Inventario", required=True, ondelete="cascade")
    name = fields.Char("Ítem/Descripción", required=True)
    quantity = fields.Float("Cantidad", default=1.0)
    condition = fields.Selection([
        ("new","Nuevo"),("good","Bueno"),("fair","Regular"),("poor","Malo")
    ], string="Condición", default="good")
    image = fields.Image("Foto (evidencia)")
