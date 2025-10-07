from odoo import http
import json
from odoo.http import request
from odoo.addons.documents.controllers.documents import ShareRoute  # Inherit base class
from werkzeug.exceptions import BadRequest, Forbidden
from odoo.tools import replace_exceptions, str2bool, consteq


class CustomShareRoute(ShareRoute):
    @http.route(['/documents/upload/', '/documents/upload/<access_token>'],type='http', auth='public', methods=['POST'],csrf=False)
    def documents_upload(
        self,
        ufile,
        access_token='',
        user_folder_id='',
        owner_id='',
        partner_id='',
        res_id='',
        res_model=False,
        allowed_company_ids='',
    ):
        """
        Replace an existing document or create new ones.

        :param ufile: a list of multipart/form-data files.
        :param access_token: the access token to a folder in which to
            create new documents, or the access token to an existing
            document where to upload/replace its attachment.
            A falsy value means no folder_id and is allowed to
            enable authorized users to upload at the root of
            user_folder_id (My Drive for internal users, Company for
            documents managers)
        :param owner_id, partner_id, res_id, res_model: field values
            when creating new documents, for internal users only
        """
        if allowed_company_ids:
            request.update_context(allowed_company_ids=json.loads(allowed_company_ids))
        if access_token and user_folder_id or not access_token and user_folder_id not in {'COMPANY', 'MY'}:
            raise BadRequest("Incorrect token/user_folder_id values")
        is_internal_user = request.env.user._is_internal()
        if is_internal_user and not access_token:
            document_sudo = request.env['documents.document'].sudo()
        else:
            document_sudo = self._from_access_token(access_token)
            if (
                not document_sudo
                or (document_sudo.user_permission != 'edit'
                    and document_sudo.access_via_link != 'edit')
                or document_sudo.type not in ('binary', 'folder')
            ):
                document_sudo = request.env['documents.document'].sudo()

        files = request.httprequest.files.getlist('ufile')
        if not files:
            raise BadRequest("missing files")
        if len(files) > 1 and document_sudo.type not in (False, 'folder'):
            raise BadRequest("cannot save multiple files inside a single document")

        if is_internal_user:
            with replace_exceptions(ValueError, by=BadRequest):
                owner_id = int(owner_id) if owner_id else request.env.user.id if not user_folder_id else None
                partner_id = int(partner_id) if partner_id else None
                res_id = int(res_id) if res_id else False
        elif owner_id or partner_id or res_id or res_model:
            raise Forbidden("only internal users can provide field values")
        else:
            owner_id = document_sudo.owner_id.id if request.env.user.is_public else request.env.user.id
            partner_id = None
            res_model = False
            res_id = False

        previous_attachment_id = document_sudo.attachment_id
        document_ids = self._documents_upload(
            document_sudo, files, owner_id, user_folder_id, partner_id, res_id, res_model)
        if document_sudo.type != 'folder' and len(document_ids) == 1:
            document_sudo = document_sudo.browse(document_ids)

        if request.env.user._is_public():
            if document_sudo.type == 'folder' or previous_attachment_id:
                return request.redirect(document_sudo.access_url)
            return request.redirect('/documents/upload/success')
        else:
            return request.make_json_response(document_ids)