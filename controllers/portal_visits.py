# -*- coding: utf-8 -*-
from datetime import datetime

import pytz

from odoo import http, _, fields
from odoo.http import request


class PortalRentalVisits(http.Controller):

    @http.route(
        ['/rental/agendar-visita/<int:product_id>'],
        type='http',
        auth='public',
        website=True,
        methods=['GET', 'POST'],
    )
    def portal_schedule_visit(self, product_id, **post):
        env = request.env

        # ========= Producto =========
        Product = env["product.template"].sudo()
        product = Product.browse(product_id)
        if not product.exists():
            return request.not_found()

        # ========= Propiedad vinculada =========
        Property = env["rental.property"].sudo()
        fields_prop = Property._fields
        domain = []

        if "product_id" in fields_prop and "product_tmpl_id" in fields_prop:
            domain = ["|", ("product_id", "=", product_id), ("product_tmpl_id", "=", product_id)]
        elif "product_id" in fields_prop:
            domain = [("product_id", "=", product_id)]
        elif "product_tmpl_id" in fields_prop:
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

        # ========= Lógica de formulario =========
        is_public = request.env.user == request.env.ref("base.public_user")

        message = ""
        errors = []

        form_vals = {
            "name": post.get("name", ""),
            "email": post.get("email", ""),
            "phone": post.get("phone", ""),
            "note": post.get("note", ""),
            "slot_id": post.get("slot_id", ""),
            "visit_start_time": post.get("visit_start_time", ""),
            "visit_end_time": post.get("visit_end_time", ""),
        }

        if request.httprequest.method == "POST":
            slot_id = int(post.get("slot_id") or 0)
            start_time_str = (post.get("visit_start_time") or "").strip()
            end_time_str = (post.get("visit_end_time") or "").strip()

            slot = Slot.browse(slot_id) if slot_id else Slot.browse()

            if not slot_id or not slot or not slot.exists():
                errors.append(_("Debe seleccionar una franja horaria válida."))

            if not start_time_str or not end_time_str:
                errors.append(_("Debe indicar hora de inicio y fin de la visita."))

            # Datos del cliente
            if is_public:
                name = (post.get("name") or "").strip()
                email = (post.get("email") or "").strip()
                phone = (post.get("phone") or "").strip()

                if not name:
                    errors.append(_("Debe indicar su nombre."))
                if not email:
                    errors.append(_("Debe indicar un correo electrónico."))
            else:
                partner = request.env.user.partner_id

            if not property_rec:
                errors.append(_("No se encontró una propiedad vinculada al producto."))

            # --- construir datetimes respetando zona horaria ---
            start_dt_utc = end_dt_utc = None
            if not errors and slot:
                try:
                    # 1) fecha local de la franja
                    slot_start_local = fields.Datetime.context_timestamp(
                        slot, slot.start_datetime
                    )
                    local_date = slot_start_local.date()

                    # 2) parsear horas ingresadas (HH:MM) como tiempo
                    start_time_obj = datetime.strptime(start_time_str, "%H:%M").time()
                    end_time_obj = datetime.strptime(end_time_str, "%H:%M").time()

                    # 3) construir datetime local completo
                    user_tz_name = request.env.user.tz or "UTC"
                    user_tz = pytz.timezone(user_tz_name)

                    local_start_dt = user_tz.localize(
                        datetime.combine(local_date, start_time_obj)
                    )
                    local_end_dt = user_tz.localize(
                        datetime.combine(local_date, end_time_obj)
                    )

                    # 4) convertir a UTC sin tzinfo (formato que usa Odoo internamente)
                    start_dt_utc = local_start_dt.astimezone(pytz.UTC).replace(tzinfo=None)
                    end_dt_utc = local_end_dt.astimezone(pytz.UTC).replace(tzinfo=None)

                except Exception:
                    errors.append(_("Formato de hora inválido. Use HH:MM."))

                if start_dt_utc and end_dt_utc:
                    if start_dt_utc >= end_dt_utc:
                        errors.append(_("La hora de fin debe ser posterior a la hora de inicio."))

                    # Validar contra los límites de la franja (en UTC)
                    if start_dt_utc < slot.start_datetime or end_dt_utc > slot.end_datetime:
                        errors.append(
                            _("El horario elegido debe estar completamente dentro de la franja del agente.")
                        )

            # --- crear visita si todo está OK ---
            if not errors and property_rec and slot and start_dt_utc and end_dt_utc:
                if is_public:
                    partner = env["res.partner"].sudo().create(
                        {
                            "name": name,
                            "email": email,
                            "phone": phone,
                        }
                    )

                Visit = env["rental.visit"].sudo()
                Visit.create(
                    {
                        "property_id": property_rec.id,
                        "agent_id": slot.agent_id.id,
                        "customer_id": partner.id,
                        "slot_id": slot.id,
                        "start_datetime": start_dt_utc,
                        "end_datetime": end_dt_utc,
                        "state": "requested",
                        "notes": post.get("note", ""),
                    }
                )

                message = _(
                    "Tu solicitud de visita fue enviada correctamente. "
                    "Un agente la confirmará en breve."
                )
                form_vals = {
                    "name": "",
                    "email": "",
                    "phone": "",
                    "note": "",
                    "slot_id": "",
                    "visit_start_time": "",
                    "visit_end_time": "",
                }

        values = {
            "product": product,
            "property": property_rec,
            "slots": slots,
            "is_public": is_public,
            "message": message,
            "errors": errors,
            "form": form_vals,
        }
        return request.render("sga_property_rental.rental_visit_template", values)
