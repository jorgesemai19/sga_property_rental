# controllers/website_agendar.py
from odoo import http
from odoo.http import request

class WebsiteAgendar(http.Controller):

    @http.route(['/agendar-visita/<int:product_id>'], type='http', auth='public', website=True, sitemap=False)
    def agendar_visita(self, product_id, **kw):
        product = request.env['product.template'].sudo().browse(product_id)
        return request.render('sga_property_rental.agendar_visita_template', {'product': product})
