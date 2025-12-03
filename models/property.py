# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from urllib.parse import quote_plus

#cambios Jorge
class RentalPropertyType(models.Model):
    _name = "rental.property.type"
    _description = "Tipo de Propiedad"
    _order = "name"

    name = fields.Char("Tipo de Propiedad", required=True)
    code = fields.Char("Código", size=10)
    description = fields.Text("Descripción")
    active = fields.Boolean(default=True)

class RentalBuilding(models.Model):
    _name = "rental.building"
    _description = "Edificio (Propiedad Horizontal)"
    _order = "name"

    name = fields.Char("Nombre del Edificio", required=True)
    street = fields.Char("Dirección")
    city = fields.Char("Ciudad")
    state_id = fields.Many2one("res.country.state", "Estado/Departamento")
    country_id = fields.Many2one("res.country", "País", default=lambda self: self.env.company.country_id)
    property_ids = fields.One2many("rental.property", "building_id", string="Unidades")
    property_count = fields.Integer("Cantidad de Unidades", compute="_compute_property_count")
    active = fields.Boolean(default=True)

    @api.depends("property_ids")
    def _compute_property_count(self):
        for rec in self:
            rec.property_count = len(rec.property_ids)

#cami + original
class RentalProperty(models.Model):
    _name = "rental.property"
    _description = "Propiedad (Inmueble)"

    name = fields.Char("Nombre/Identificador", required=True)
    code = fields.Char("Código", compute="_compute_code", store=True, readonly=True)

    # Tipo de propiedad
    property_type_id = fields.Many2one("rental.property.type", "Tipo de Propiedad", required=True)
    property_structure = fields.Selection([
        ('horizontal', 'Horizontal'),
        ('vertical', 'Vertical')
    ], string="Estructura", required=True, default='horizontal')

    rental_type = fields.Selection([
        ('alquiler', 'Alquiler'),
        ('arriendo', 'Arriendo'),
        ('venta', 'Venta')
    ], string="Tipo de Operación", required=True, default='alquiler')

    # Propiedad horizontal
    building_id = fields.Many2one("rental.building", "Edificio",
                                  help="Para propiedades horizontales, seleccionar el edificio")
    unit_number = fields.Char("Número de Unidad/Departamento")
    floor = fields.Integer("Piso")

    street1 = fields.Char("Calle 1", required=True)
    street2 = fields.Char("Calle 2")
    reference = fields.Char("Referencia")
    house_number = fields.Char("Numero de casa")
    # city = fields.Char("Ciudad")
    city = fields.Many2one(
        "res.city",
        string="Ciudad",
        domain="[('state_id', '=', state_id)]",
        help="Seleccione la Ciudad filtrada por el Departamento.",
    )
    # state_id = fields.Many2one("res.country.state", "Estado/Departamento")
    state_id = fields.Many2one(
        "res.country.state",
        string="Departamento/Estado",
        domain="[('country_id', '=', country_id)]",
        help="Seleccione el Departamento (res.country.state).",
    )
    country_id = fields.Many2one("res.country", "País", default=lambda self: self.env.company.country_id)

    zone_type = fields.Selection([
        ('urban', 'Urbana'),
        ('rural', 'Rural')
    ], string="Zona", required=True, default='urban')

    # Datos catastrales
    cadastral_account = fields.Char("Cuenta Catastral")
    padron = fields.Char("Padrón")
    block = fields.Char("Manzana")
    lot = fields.Char("Lote")

    owner_id = fields.Many2one("res.partner", "Propietario", required=True)
    acquisition_date = fields.Date("Fecha de adquisicion del inmueble")
    image_1920 = fields.Image("Imagen")  # v18 friendly
    inventory_ids = fields.One2many("rental.property.inventory", "property_id", string="Inventarios")
    active = fields.Boolean(default=True)

    contract_ids = fields.One2many("rental.contract", "property_id", string="Contratos")
    current_contract_id = fields.Many2one(
        "rental.contract", string="Contrato vigente", compute="_compute_current_contract", store=False
    )

    @api.depends("country_id", "city", "unit_number", "property_type_id", "property_type_id.code")
    def _compute_code(self):
        """Genera código sugerido ejemplo: PY-ASU-UMX"""
        for rec in self:
            parts = []
            # País (código ISO)
            if rec.country_id:
                parts.append(rec.country_id.code or 'XX')

            # Ciudad (primeras 3 letras en mayúsculas) -> usar name porque city es Many2one
            if rec.city and rec.city.name:
                city_code = rec.city.name[:3].upper()
                parts.append(city_code)

            # Tipo de propiedad o unidad
            if rec.unit_number:
                parts.append((rec.unit_number or '').upper())
            elif rec.property_type_id and rec.property_type_id.code:
                parts.append(rec.property_type_id.code)

            rec.code = '-'.join(parts) if parts else ''

    @api.depends("contract_ids.state", "contract_ids.start_date", "contract_ids.end_date")
    def _compute_current_contract(self):
        today = fields.Date.context_today(self)
        for rec in self:
            active_contract = rec.contract_ids.filtered(
                lambda c: c.state == 'active' and c.start_date <= today and (not c.end_date or c.end_date >= today)
            )[:1]
            rec.current_contract_id = active_contract.id if active_contract else False

    @api.constrains('property_structure', 'building_id')
    def _check_horizontal_building(self):
        """Valida que propiedades horizontales tengan edificio asignado"""
        for rec in self:
            if rec.property_structure == 'horizontal' and not rec.building_id:
                raise ValidationError(_("Las propiedades horizontales deben estar relacionadas a un edificio."))

    geo_latitude = fields.Float(string="Latitud")
    geo_longitude = fields.Float(string="Longitud")
    map_address = fields.Char(string="Dirección para mapa", compute="_compute_map_address", store=True)

    # NUEVO: iframe embebido
    map_iframe = fields.Html(string="Mapa (embed)", compute="_compute_map_iframe", sanitize=False)

    @api.depends('street1', 'street2', 'house_number', 'reference', 'city', 'state_id', 'country_id')
    def _compute_map_address(self):
        for rec in self:
            street_bits = [
                rec.street1 or '',
                rec.house_number or '',
                rec.street2 or '',
                rec.reference or '',
            ]
            street = " ".join([b.strip() for b in street_bits if b])
            city_name = rec.city.name if rec.city else ''
            state_name = rec.state_id.name or ''
            country_name = rec.country_id.name or ''
            parts = [street, city_name, state_name, country_name]
            rec.map_address = ", ".join([p for p in parts if p])

    @api.depends('map_address', 'geo_latitude', 'geo_longitude')
    def _compute_map_iframe(self):
        Param = self.env['ir.config_parameter'].sudo()
        api_key = Param.get_param('google_maps_api_key') or Param.get_param(
            'web_widget_google_map.google_maps_api_key') or ''
        for rec in self:
            # Prioriza coordenadas si existen; si no, usa la dirección
            if rec.geo_latitude and rec.geo_longitude:
                q = f"{rec.geo_latitude},{rec.geo_longitude}"
            else:
                q = rec.map_address or ''
            query = quote_plus(q) if q else ''
            if api_key and query:
                src = f"https://www.google.com/maps/embed/v1/place?key={api_key}&q={query}"
                rec.map_iframe = f'<iframe width="100%" height="360" frameborder="0" style="border:0" src="{src}" allowfullscreen></iframe>'
            else:
                rec.map_iframe = "<p style='color:#888'>Cargá dirección o coordenadas y/o la API key para ver el mapa.</p>"

    @api.onchange('state_id')
    def _onchange_state_id(self):
        for rec in self:
            if rec.city and rec.city.state_id != rec.state_id:
                rec.city = False

class RentalPropertyInventory(models.Model):
    _name = "rental.property.inventory"
    _description = "Inventario por fecha"
    _order = "date desc"

    property_id = fields.Many2one("rental.property", "Propiedad", required=True, ondelete="cascade")
    date = fields.Date("Fecha", required=True, default=fields.Date.context_today)
    note = fields.Text("Observaciones")
    line_ids = fields.One2many("rental.property.inventory.line", "inventory_id", "Items")

    # NUEVOS CAMPOS DE ESTADO (2 opciones como pediste)
    paint_state = fields.Selection(
        [("optimo", "Óptimo"), ("mal", "En mal estado")],
        string="Pintura", default="optimo"
    )
    plumbing_state = fields.Selection(
        [("optimo", "Óptimo"), ("mal", "En mal estado")],
        string="Tuberías", default="optimo"
    )
    electrical_state = fields.Selection(
        [("optimo", "Óptimo"), ("mal", "En mal estado")],
        string="Inst. eléctrica", default="optimo"
    )

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
