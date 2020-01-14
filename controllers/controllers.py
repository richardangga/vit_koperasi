# -*- coding: utf-8 -*-
from odoo import http

# class Ksp(http.Controller):
#     @http.route('/ksp/ksp/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/ksp/ksp/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('ksp.listing', {
#             'root': '/ksp/ksp',
#             'objects': http.request.env['ksp.ksp'].search([]),
#         })

#     @http.route('/ksp/ksp/objects/<model("ksp.ksp"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('ksp.object', {
#             'object': obj
#         })