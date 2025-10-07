from odoo import models, fields, api

class DocumentsDocumentInherit(models.Model):
    _inherit = "documents.document"

    @api.constrains('owner_id', 'folder_id')
    def _check_root_documents_owner_id(self):
        root_documents = self.filtered(lambda d: not d.folder_id)
        unauthorized_owners_sudo = root_documents._get_unauthorized_root_document_owners_sudo()
        if unauthorized_owners_sudo:
            pass
            # users_documents_list = [
            #     (document.owner_id.name, document.name)
            #     for document in root_documents
            #     if document.owner_id in unauthorized_owners_sudo
            # ]
            # raise ValidationError(
            #     _("The following user(s) cannot own root documents/folders: \n- %(lines)s",
            #       lines="\n-".join(f'{user_name}: {doc_name}' for user_name, doc_name in users_documents_list))
            # )

