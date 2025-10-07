/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { DocumentService } from "@documents/core/document_service";

patch(DocumentService.prototype, {

    canUploadInFolder(folder) {
        const userPermission = folder.target_user_permission || folder.user_permission;
        this.userIsPortal = !this.userIsInternal && !this.userIsDocumentManager;
        return (
            folder &&
            (
                (typeof folder.id === "number" && userPermission === "edit") ||
                (this.userIsInternal && ["MY", "RECENT", false].includes(folder.id)) ||
                (this.userIsDocumentManager && folder.id === "COMPANY") ||
                this.userIsPortal  // ✅ add this line
            )
        );
    }

});
