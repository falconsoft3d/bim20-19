# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError
import werkzeug


class PortalBIMController(http.Controller):

    def _check_portal_access(self):
        """Verifica que el usuario tenga acceso al portal BIM"""
        if not request.env.user or request.env.user._is_public():
            return False
        
        partner = request.env.user.partner_id
        return partner.portal_bim_active

    @http.route('/portal/bim/login', type='http', auth='public', website=True, csrf=False)
    def portal_bim_login(self, **kw):
        """Página de login del Portal BIM"""
        # Si ya está autenticado, redirigir al dashboard
        if request.env.user and not request.env.user._is_public():
            partner = request.env.user.partner_id
            if partner.portal_bim_active:
                return werkzeug.utils.redirect('/portal/bim/dashboard')
        
        error_message = None
        
        # Procesar login
        if request.httprequest.method == 'POST':
            login = kw.get('login')
            password = kw.get('password')
            
            if not login or not password:
                error_message = 'Por favor ingrese usuario y contraseña'
            else:
                # Buscar partner con las credenciales
                partner = request.env['res.partner'].sudo().search([
                    ('portal_bim_active', '=', True),
                    ('portal_bim_login', '=', login),
                    ('portal_bim_password', '=', password)
                ], limit=1)
                
                if partner:
                    # Autenticar sesión
                    request.session['portal_bim_partner_id'] = partner.id
                    return werkzeug.utils.redirect('/portal/bim/dashboard')
                else:
                    error_message = 'Usuario o contraseña incorrectos'
        
        return request.render('base_bim_2_portal.portal_bim_login', {
            'error_message': error_message
        })

    @http.route('/portal/bim/logout', type='http', auth='public', website=True)
    def portal_bim_logout(self, **kw):
        """Cerrar sesión del Portal BIM"""
        request.session.pop('portal_bim_partner_id', None)
        return werkzeug.utils.redirect('/portal/bim/login')

    @http.route('/portal/bim/dashboard', type='http', auth='public', website=True)
    def portal_bim_dashboard(self, **kw):
        """Dashboard principal del Portal BIM"""
        # Verificar autenticación
        partner_id = request.session.get('portal_bim_partner_id')
        if not partner_id:
            return werkzeug.utils.redirect('/portal/bim/login')
        
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner.exists() or not partner.portal_bim_active:
            request.session.pop('portal_bim_partner_id', None)
            return werkzeug.utils.redirect('/portal/bim/login')
        
        # Obtener proyectos del partner
        partner_projects = request.env['bim.project'].sudo().search([
            ('customer_id', '=', partner.id)
        ])
        project_ids = partner_projects.ids
        
        # KPI 1: Tickets Abiertos / Total Tickets
        tickets = request.env['ticket.bim'].sudo().search([
            ('partner_id', '=', partner.id)
        ])
        total_tickets = len(tickets)
        open_tickets = len(tickets.filtered(lambda t: t.state not in ['done', 'cancel']))
        
        # KPI 2: Documentos Pendientes / Total Documentos
        # Buscar documentos a través de los proyectos del partner
        documents = request.env['bim.documentation'].sudo().search([
            ('project_id', 'in', project_ids)
        ])
        total_documents = len(documents)
        pending_documents = len(documents.filtered(lambda d: d.costumer_state == 'draft'))
        
        # KPI 3: Facturas sin Pagar / Total Facturas (Importe y Cantidad)
        invoices = request.env['account.move'].sudo().search([
            ('move_type', '=', 'out_invoice'),
            ('partner_id', '=', partner.id),
            ('state', '=', 'posted')
        ])
        total_invoices = len(invoices)
        unpaid_invoices = invoices.filtered(lambda i: i.payment_state in ['not_paid', 'partial'])
        total_unpaid_invoices = len(unpaid_invoices)
        total_unpaid_amount = sum(unpaid_invoices.mapped('amount_residual'))
        total_invoices_amount = sum(invoices.mapped('amount_total'))
        
        # KPI 4: Presupuestos Aprobados / Total Presupuestos (Importe y Cantidad)
        budgets = request.env['bim.budget'].sudo().search([
            ('project_id', 'in', project_ids)
        ])
        total_budgets = len(budgets)
        approved_budgets = budgets.filtered(lambda b: b.costumer_state == 'approved')
        total_approved_budgets = len(approved_budgets)
        total_approved_amount = sum(approved_budgets.mapped('amount_total'))
        total_budgets_amount = sum(budgets.mapped('amount_total'))
        
        # Obtener datos para el dashboard
        values = {
            'partner': partner,
            'page': 'dashboard',
            # KPIs
            'total_tickets': total_tickets,
            'open_tickets': open_tickets,
            'total_documents': total_documents,
            'pending_documents': pending_documents,
            'total_invoices': total_invoices,
            'total_unpaid_invoices': total_unpaid_invoices,
            'total_unpaid_amount': total_unpaid_amount,
            'total_invoices_amount': total_invoices_amount,
            'total_budgets': total_budgets,
            'total_approved_budgets': total_approved_budgets,
            'total_approved_amount': total_approved_amount,
            'total_budgets_amount': total_budgets_amount,
        }
        
        return request.render('base_bim_2_portal.portal_bim_dashboard', values)

    @http.route('/portal/bim/projects', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def portal_bim_projects(self, project_id=None, **kw):
        """Lista y detalle de proyectos del cliente"""
        # Verificar autenticación
        partner_id = request.session.get('portal_bim_partner_id')
        if not partner_id:
            return werkzeug.utils.redirect('/portal/bim/login')
        
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner.exists() or not partner.portal_bim_active:
            request.session.pop('portal_bim_partner_id', None)
            return werkzeug.utils.redirect('/portal/bim/login')
        
        view_mode = 'list'
        project = None
        messages = []
        success_message = None
        error_message = None
        
        # Determinar vista
        if project_id:
            view_mode = 'detail'
            project = request.env['bim.project'].sudo().browse(int(project_id))
            if not project.exists() or project.customer_id.id != partner.id:
                return werkzeug.utils.redirect('/portal/bim/projects')
            
            # Obtener mensajes del chatter
            messages = request.env['mail.message'].sudo().search([
                ('model', '=', 'bim.project'),
                ('res_id', '=', project.id),
                ('message_type', 'in', ['comment', 'notification'])
            ], order='date desc')
        
        # Procesar comentario
        if request.httprequest.method == 'POST' and project_id:
            try:
                comment = kw.get('comment', '').strip()
                if comment:
                    project = request.env['bim.project'].sudo().browse(int(project_id))
                    if project.exists() and project.customer_id.id == partner.id:
                        # Crear mensaje en el chatter
                        project.message_post(
                            body=comment,
                            subject=f'Comentario de {partner.name}',
                            message_type='comment',
                            subtype_xmlid='mail.mt_comment',
                            author_id=partner.id
                        )
                        success_message = 'Comentario agregado exitosamente'
                        # Recargar mensajes
                        messages = request.env['mail.message'].sudo().search([
                            ('model', '=', 'bim.project'),
                            ('res_id', '=', project.id),
                            ('message_type', 'in', ['comment', 'notification'])
                        ], order='date desc')
                else:
                    error_message = 'El comentario no puede estar vacío'
            except Exception as e:
                error_message = f'Error al agregar comentario: {str(e)}'
        
        # Obtener proyectos del cliente
        projects = request.env['bim.project'].sudo().search([
            ('customer_id', '=', partner.id)
        ])
        
        values = {
            'partner': partner,
            'page': 'projects',
            'projects': projects,
            'project': project,
            'messages': messages,
            'view_mode': view_mode,
            'success_message': success_message,
            'error_message': error_message,
        }
        
        return request.render('base_bim_2_portal.portal_bim_projects', values)

    @http.route('/portal/bim/tickets', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def portal_bim_tickets(self, ticket_id=None, action=None, **kw):
        """Lista y creación de tickets"""
        # Verificar autenticación
        partner_id = request.session.get('portal_bim_partner_id')
        if not partner_id:
            return werkzeug.utils.redirect('/portal/bim/login')
        
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner.exists() or not partner.portal_bim_active:
            request.session.pop('portal_bim_partner_id', None)
            return werkzeug.utils.redirect('/portal/bim/login')
        
        # Obtener proyectos del cliente
        projects = request.env['bim.project'].sudo().search([
            ('customer_id', '=', partner.id)
        ])
        
        # Obtener categorías de tickets
        categories = request.env['ticket.bim.category'].sudo().search([])
        
        success_message = None
        error_message = None
        view_mode = 'list'  # list, new, detail
        ticket = None
        
        # Determinar vista
        if ticket_id:
            view_mode = 'detail'
            ticket = request.env['ticket.bim'].sudo().browse(int(ticket_id))
            if not ticket.exists() or ticket.partner_id.id != partner.id:
                error_message = 'Ticket no encontrado'
                view_mode = 'list'
        elif action == 'new':
            view_mode = 'new'
        
        # Procesar creación de ticket
        if request.httprequest.method == 'POST':
            try:
                project_id = kw.get('project_id')
                category_id = kw.get('category_id')
                title = kw.get('title')
                obs = kw.get('description')  # El formulario usa 'description' pero el campo es 'obs'
                
                # Procesar archivo adjunto
                attachment_file = request.httprequest.files.get('comprobante_01')
                
                if not project_id or not category_id or not title:
                    error_message = 'Debe seleccionar un proyecto, categoría y escribir un asunto'
                else:
                    # Crear ticket
                    ticket_vals = {
                        'title': title,
                        'project_id': int(project_id),
                        'category_id': int(category_id),
                        'obs': obs or '',
                        'partner_id': partner.id,
                    }
                    
                    # Agregar archivo adjunto si existe
                    if attachment_file and attachment_file.filename:
                        import base64
                        ticket_vals['comprobante_01'] = base64.b64encode(attachment_file.read())
                        ticket_vals['comprobante_01_name'] = attachment_file.filename
                    
                    new_ticket = request.env['ticket.bim'].sudo().create(ticket_vals)
                    success_message = 'Ticket creado exitosamente'
                    view_mode = 'detail'
                    ticket = new_ticket
                    
            except Exception as e:
                error_message = f'Error al crear ticket: {str(e)}'
                view_mode = 'new'
        
        # Obtener tickets del cliente
        tickets = request.env['ticket.bim'].sudo().search([
            '|',
            ('partner_id', '=', partner.id),
            ('project_id.customer_id', '=', partner.id)
        ], order='create_date desc')
        
        values = {
            'partner': partner,
            'page': 'tickets',
            'projects': projects,
            'categories': categories,
            'tickets': tickets,
            'ticket': ticket,
            'view_mode': view_mode,
            'success_message': success_message,
            'error_message': error_message
        }
        
        return request.render('base_bim_2_portal.portal_bim_tickets', values)

    @http.route('/portal/bim/documents', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def portal_bim_documents(self, **kw):
        """Página de documentos del portal BIM"""
        # Verificar autenticación
        partner_id = request.session.get('portal_bim_partner_id')
        if not partner_id:
            return request.redirect('/portal/bim/login')
        
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner.exists() or not partner.portal_bim_active:
            request.session.pop('portal_bim_partner_id', None)
            return request.redirect('/portal/bim/login')
        
        # Obtener proyectos del cliente
        projects = request.env['bim.project'].sudo().search([
            ('customer_id', '=', partner.id)
        ])
        
        success_message = None
        error_message = None
        view_mode = 'list'  # list, new
        action = kw.get('action')
        
        # Determinar vista
        if action == 'new':
            view_mode = 'new'
        
        # Procesar creación de documento
        if request.httprequest.method == 'POST':
            try:
                project_id = kw.get('project_id')
                code_doc = kw.get('code_doc')
                desc = kw.get('desc')
                
                # Procesar archivo
                file_upload = request.httprequest.files.get('file_01')
                
                if not project_id or not code_doc or not desc:
                    error_message = 'Debe completar todos los campos obligatorios'
                elif not file_upload or not file_upload.filename:
                    error_message = 'Debe adjuntar un archivo'
                else:
                    import base64
                    # Crear documento
                    doc_vals = {
                        'project_id': int(project_id),
                        'code_doc': code_doc,
                        'desc': desc,
                        'file_01': base64.b64encode(file_upload.read()),
                        'file_name': file_upload.filename,
                    }
                    
                    new_doc = request.env['bim.documentation'].sudo().create(doc_vals)
                    success_message = 'Documento creado exitosamente'
                    view_mode = 'list'
                    
            except Exception as e:
                error_message = f'Error al crear documento: {str(e)}'
        
        # Obtener documentos de los proyectos del cliente
        documents = request.env['bim.documentation'].sudo().search([
            ('project_id', 'in', projects.ids)
        ], order='code_doc, create_date desc')
        
        values = {
            'partner': partner,
            'page': 'documents',
            'documents': documents,
            'projects': projects,
            'view_mode': view_mode,
            'success_message': success_message,
            'error_message': error_message,
        }
        
        return request.render('base_bim_2_portal.portal_bim_documents', values)
    
    @http.route('/portal/bim/documents/approve/<int:doc_id>', type='http', auth='public', website=True)
    def portal_bim_document_approve(self, doc_id, **kw):
        """Aprobar documento"""
        # Verificar autenticación
        partner_id = request.session.get('portal_bim_partner_id')
        if not partner_id:
            return request.redirect('/portal/bim/login')
        
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner.exists() or not partner.portal_bim_active:
            request.session.pop('portal_bim_partner_id', None)
            return request.redirect('/portal/bim/login')
        
        # Buscar el documento y verificar que pertenece a un proyecto del cliente
        document = request.env['bim.documentation'].sudo().browse(doc_id)
        if document.exists() and document.project_id.customer_id.id == partner.id:
            if document.costumer_state == 'draft':
                document.write({'costumer_state': 'approved'})
        
        return request.redirect('/portal/bim/documents')
    
    @http.route('/portal/bim/documents/reject/<int:doc_id>', type='http', auth='public', website=True)
    def portal_bim_document_reject(self, doc_id, **kw):
        """Rechazar documento"""
        # Verificar autenticación
        partner_id = request.session.get('portal_bim_partner_id')
        if not partner_id:
            return request.redirect('/portal/bim/login')
        
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner.exists() or not partner.portal_bim_active:
            request.session.pop('portal_bim_partner_id', None)
            return request.redirect('/portal/bim/login')
        
        # Buscar el documento y verificar que pertenece a un proyecto del cliente
        document = request.env['bim.documentation'].sudo().browse(doc_id)
        if document.exists() and document.project_id.customer_id.id == partner.id:
            if document.costumer_state == 'draft':
                document.write({'costumer_state': 'rejected'})
        
        return request.redirect('/portal/bim/documents')

    @http.route('/portal/bim/invoices', type='http', auth='public', website=True, methods=['GET'])
    def portal_bim_invoices(self, invoice_id=None, **kw):
        """Página de facturas del portal BIM"""
        # Verificar autenticación
        partner_id = request.session.get('portal_bim_partner_id')
        if not partner_id:
            return request.redirect('/portal/bim/login')
        
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner.exists() or not partner.portal_bim_active:
            request.session.pop('portal_bim_partner_id', None)
            return request.redirect('/portal/bim/login')
        
        view_mode = 'list'
        invoice = None
        attachments = []
        
        # Determinar vista
        if invoice_id:
            view_mode = 'detail'
            invoice = request.env['account.move'].sudo().browse(int(invoice_id))
            if not invoice.exists() or invoice.partner_id.id != partner.id or invoice.move_type != 'out_invoice':
                return request.redirect('/portal/bim/invoices')
            
            # Obtener adjuntos (comprobantes de pago)
            attachments = request.env['ir.attachment'].sudo().search([
                ('res_model', '=', 'account.move'),
                ('res_id', '=', invoice.id),
                ('name', 'ilike', 'comprobante')
            ])
        
        # Obtener facturas de venta del cliente
        invoices = request.env['account.move'].sudo().search([
            ('partner_id', '=', partner.id),
            ('move_type', '=', 'out_invoice')
        ], order='invoice_date desc, name desc')
        
        values = {
            'partner': partner,
            'page': 'invoices',
            'invoices': invoices,
            'invoice': invoice,
            'attachments': attachments,
            'view_mode': view_mode,
        }
        
        return request.render('base_bim_2_portal.portal_bim_invoices', values)
    
    @http.route('/portal/bim/invoices/pdf/<int:invoice_id>', type='http', auth='public', website=True)
    def portal_bim_invoice_pdf(self, invoice_id, **kw):
        """Descargar factura en PDF"""
        # Verificar autenticación
        partner_id = request.session.get('portal_bim_partner_id')
        if not partner_id:
            return request.redirect('/portal/bim/login')
        
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner.exists() or not partner.portal_bim_active:
            request.session.pop('portal_bim_partner_id', None)
            return request.redirect('/portal/bim/login')
        
        # Buscar la factura y verificar que pertenece al cliente
        invoice = request.env['account.move'].sudo().browse(invoice_id)
        if not invoice.exists() or invoice.partner_id.id != partner.id or invoice.move_type != 'out_invoice':
            return request.redirect('/portal/bim/invoices')
        
        # Generar PDF
        pdf_content, _ = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'account.report_invoice', [invoice_id]
        )
        
        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf_content)),
            ('Content-Disposition', f'attachment; filename="{invoice.name}.pdf"')
        ]
        
        return request.make_response(pdf_content, headers=pdfhttpheaders)
    
    @http.route('/portal/bim/invoices/upload-payment/<int:invoice_id>', type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def portal_bim_invoice_upload_payment(self, invoice_id, **kw):
        """Subir comprobante de pago para factura"""
        # Verificar autenticación
        partner_id = request.session.get('portal_bim_partner_id')
        if not partner_id:
            return request.redirect('/portal/bim/login')
        
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner.exists() or not partner.portal_bim_active:
            request.session.pop('portal_bim_partner_id', None)
            return request.redirect('/portal/bim/login')
        
        # Buscar la factura y verificar que pertenece al cliente
        invoice = request.env['account.move'].sudo().browse(invoice_id)
        if not invoice.exists() or invoice.partner_id.id != partner.id or invoice.move_type != 'out_invoice':
            return request.redirect('/portal/bim/invoices')
        
        try:
            # Procesar archivo
            payment_file = request.httprequest.files.get('payment_proof')
            payment_note = kw.get('payment_note', '')
            
            if payment_file and payment_file.filename:
                import base64
                from datetime import datetime
                
                # Crear nombre descriptivo
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                attachment_name = f'Comprobante_Pago_{invoice.name}_{timestamp}_{payment_file.filename}'
                
                # Crear adjunto
                attachment_vals = {
                    'name': attachment_name,
                    'datas': base64.b64encode(payment_file.read()),
                    'res_model': 'account.move',
                    'res_id': invoice.id,
                    'description': payment_note or 'Comprobante de pago subido desde portal',
                }
                
                request.env['ir.attachment'].sudo().create(attachment_vals)
                
                # Agregar mensaje en el chatter
                message = f'Comprobante de pago subido desde el portal por {partner.name}'
                if payment_note:
                    message += f'\nNota: {payment_note}'
                
                invoice.message_post(
                    body=message,
                    subject='Comprobante de Pago',
                    message_type='comment'
                )
                
        except Exception as e:
            pass  # Silenciar errores y redirigir
        
        return request.redirect(f'/portal/bim/invoices?invoice_id={invoice_id}')

    @http.route('/portal/bim/profile', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def portal_bim_profile(self, **kw):
        """Perfil y actualización de datos del usuario"""
        # Verificar autenticación
        partner_id = request.session.get('portal_bim_partner_id')
        if not partner_id:
            return werkzeug.utils.redirect('/portal/bim/login')
        
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner.exists() or not partner.portal_bim_active:
            request.session.pop('portal_bim_partner_id', None)
            return werkzeug.utils.redirect('/portal/bim/login')
        
        success_message = None
        error_message = None
        
        # Procesar actualización de datos
        if request.httprequest.method == 'POST':
            try:
                # Actualizar datos del partner
                vals = {}
                
                if kw.get('name'):
                    vals['name'] = kw.get('name')
                if kw.get('email'):
                    vals['email'] = kw.get('email')
                if kw.get('phone'):
                    vals['phone'] = kw.get('phone')
                if kw.get('mobile'):
                    vals['mobile'] = kw.get('mobile')
                if kw.get('street'):
                    vals['street'] = kw.get('street')
                if kw.get('city'):
                    vals['city'] = kw.get('city')
                if kw.get('zip'):
                    vals['zip'] = kw.get('zip')
                
                # Cambio de contraseña
                current_password = kw.get('current_password')
                new_password = kw.get('new_password')
                confirm_password = kw.get('confirm_password')
                
                if new_password:
                    if not current_password:
                        error_message = 'Debe ingresar su contraseña actual'
                    elif current_password != partner.portal_bim_password:
                        error_message = 'La contraseña actual es incorrecta'
                    elif new_password != confirm_password:
                        error_message = 'Las contraseñas nuevas no coinciden'
                    elif len(new_password) < 6:
                        error_message = 'La contraseña debe tener al menos 6 caracteres'
                    else:
                        vals['portal_bim_password'] = new_password
                
                if vals and not error_message:
                    partner.write(vals)
                    success_message = 'Datos actualizados correctamente'
                    
            except Exception as e:
                error_message = f'Error al actualizar datos: {str(e)}'
        
        values = {
            'partner': partner,
            'page': 'profile',
            'success_message': success_message,
            'error_message': error_message
        }
        
        return request.render('base_bim_2_portal.portal_bim_profile', values)
    @http.route('/portal/bim/budgets', type='http', auth='public', website=True, methods=['GET'])
    def portal_bim_budgets(self, budget_id=None, **kw):
        """Lista de presupuestos o detalle de un presupuesto"""
        # Verificar autenticación
        partner_id = request.session.get('portal_bim_partner_id')
        if not partner_id:
            return werkzeug.utils.redirect('/portal/bim/login')
        
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner.exists() or not partner.portal_bim_active:
            request.session.pop('portal_bim_partner_id', None)
            return werkzeug.utils.redirect('/portal/bim/login')
        
        # Obtener proyectos del partner
        partner_projects = request.env['bim.project'].sudo().search([
            ('customer_id', '=', partner.id)
        ])
        project_ids = partner_projects.ids
        
        # Vista de detalle
        if budget_id:
            budget = request.env['bim.budget'].sudo().browse(int(budget_id))
            
            # Verificar que el presupuesto pertenezca a un proyecto del partner
            if not budget or not budget.project_id or budget.project_id.id not in project_ids:
                return werkzeug.utils.redirect('/portal/bim/budgets')
            
            # Obtener adjuntos del presupuesto
            attachments = request.env['ir.attachment'].sudo().search([
                ('res_model', '=', 'bim.budget'),
                ('res_id', '=', budget.id)
            ])
            
            values = {
                'partner': partner,
                'page': 'budgets',
                'view_mode': 'detail',
                'budget': budget,
                'attachments': attachments,
            }
            return request.render('base_bim_2_portal.portal_bim_budgets', values)
        
        # Vista de lista - buscar presupuestos de los proyectos del partner
        budgets = request.env['bim.budget'].sudo().search([
            ('project_id', 'in', project_ids)
        ])
        
        values = {
            'partner': partner,
            'page': 'budgets',
            'view_mode': 'list',
            'budgets': budgets,
        }
        
        return request.render('base_bim_2_portal.portal_bim_budgets', values)

    @http.route('/portal/bim/budgets/action', type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def portal_bim_budget_action(self, **kw):
        """Aprobar o rechazar presupuesto"""
        # Verificar autenticación
        partner_id = request.session.get('portal_bim_partner_id')
        if not partner_id:
            return werkzeug.utils.redirect('/portal/bim/login')
        
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner.exists() or not partner.portal_bim_active:
            request.session.pop('portal_bim_partner_id', None)
            return werkzeug.utils.redirect('/portal/bim/login')
        
        budget_id = kw.get('budget_id')
        action = kw.get('action')  # 'approve' o 'reject'
        
        if not budget_id or not action:
            return werkzeug.utils.redirect('/portal/bim/budgets')
        
        budget = request.env['bim.budget'].sudo().browse(int(budget_id))
        
        # Obtener proyectos del partner
        partner_projects = request.env['bim.project'].sudo().search([
            ('customer_id', '=', partner.id)
        ])
        project_ids = partner_projects.ids
        
        # Verificar que el presupuesto pertenezca a un proyecto del partner
        if not budget or not budget.project_id or budget.project_id.id not in project_ids:
            return werkzeug.utils.redirect('/portal/bim/budgets')
        
        # Actualizar estado
        if action == 'approve':
            budget.write({'costumer_state': 'approved'})
        elif action == 'reject':
            budget.write({'costumer_state': 'rejected'})
        
        return werkzeug.utils.redirect(f'/portal/bim/budgets?budget_id={budget_id}')

    @http.route('/portal/bim/budgets/attachment/<int:attachment_id>', type='http', auth='public', website=True)
    def portal_bim_budget_attachment(self, attachment_id, **kw):
        """Descargar adjunto de presupuesto"""
        # Verificar autenticación
        partner_id = request.session.get('portal_bim_partner_id')
        if not partner_id:
            return werkzeug.utils.redirect('/portal/bim/login')
        
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner.exists() or not partner.portal_bim_active:
            request.session.pop('portal_bim_partner_id', None)
            return werkzeug.utils.redirect('/portal/bim/login')
        
        attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
        
        if not attachment or attachment.res_model != 'bim.budget':
            return request.not_found()
        
        # Obtener proyectos del partner
        partner_projects = request.env['bim.project'].sudo().search([
            ('customer_id', '=', partner.id)
        ])
        project_ids = partner_projects.ids
        
        # Verificar que el presupuesto pertenezca a un proyecto del partner
        budget = request.env['bim.budget'].sudo().browse(attachment.res_id)
        if not budget or not budget.project_id or budget.project_id.id not in project_ids:
            return request.not_found()
        
        if not attachment.datas:
            return request.not_found()
        
        return request.make_response(
            attachment.datas,
            headers=[
                ('Content-Type', attachment.mimetype or 'application/octet-stream'),
                ('Content-Disposition', f'attachment; filename="{attachment.name}"'),
            ]
        )