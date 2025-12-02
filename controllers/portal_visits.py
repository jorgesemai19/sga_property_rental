# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class PortalRentalVisits(http.Controller):

    @http.route(
        ['/rental/agendar-visita/<int:product_id>'],
        type='http',
        auth='public',
        website=True,
        methods=['GET'],  # por ahora solo GET
    )
    def portal_schedule_visit(self, product_id, **kwargs):
        env = request.env

        # ========= Producto =========
        Product = env["product.template"].sudo()
        product = Product.browse(product_id)
        if not product.exists():
            return request.not_found()

        # ========= Propiedad vinculada =========
        Property = env["rental.property"].sudo()

        fields = Property._fields
        domain = []

        if "product_id" in fields and "product_tmpl_id" in fields:
            domain = ["|", ("product_id", "=", product_id), ("product_tmpl_id", "=", product_id)]
        elif "product_id" in fields:
            domain = [("product_id", "=", product_id)]
        elif "product_tmpl_id" in fields:
            domain = [("product_tmpl_id", "=", product_id)]

        if domain:
            property_rec = Property.search(domain, limit=1)
        else:
            property_rec = Property.search([], limit=1)

        # ========= Franjas =========
        Slot = env["rental.visit.slot"].sudo()
        if property_rec:
            slots = Slot.search(
                [("property_id", "=", property_rec.id), ("state", "=", "available")],
                order="start_datetime",
            )
        else:
            slots = Slot.browse()

        values = {
            "product": product,
            "property": property_rec,
            "slots": slots,
        }
        # IMPORTANTE: este xml_id debe existir en la BD
        return request.render("sga_property_rental.rental_visit_template", values)
