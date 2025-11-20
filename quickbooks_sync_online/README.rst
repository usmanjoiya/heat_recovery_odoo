====================================
Odoo QuickBooks Online Connector PRO
====================================

|

Change Log
##########

|

* 1.2.7 (2024-12-02)
    - Map the Odoo invoice Reference field to the QBO invoice Memo field.
    - Made several small improvements to enhance overall performance and stability.

* 1.2.6 (2024-10-04)
    - Added the ability to export invoices with the tax included/excluded property for non-US companies (GB, AU, IN, CA).
    - UI improvements for QBO global settings and mappings.
    - Enhanced verbose logging for debugging purposes.
    - Updated the version of the python-quickbooks library to 0.9.10 in dependencies.
    - Each received payment is now registered in a separate background job to avoid impacting other registrations in batch.
    - Other minor fixes and improvements.

* 1.2.5 (2024-03-14)
    - Do not export invoices / payments to QBO that should not be exported (from the past, linked to the company not connected to QBO etc.).
    - When exporting product to the QBO set inventory date to the past to avoid issues with creating invoices with those products.
    - Fixed scheduled action that is exporting invoices & payments to take into account proper companies that are linked to QBO.
    - Updated (and recommended) version of the python-quickbooks library to 0.9.6 in dependencies. Should be manually updated on your server or odoo.sh!

* 1.2.4 (2023-12-29)
    - More detailed description of import/export tasks.
    - Fix for exporting the Bill payments.
    - Fix for running actions on the map objects.

* 1.2.3 (2023-09-21)
    - Fixed the error "Company not defined during ... " during sending requests to QBO API.

* 1.2.2 (2023-03-03)
    - Avoid sending same invoice twice if synchronization happening after payment for the Odoo invoice is registered.
    - Added additional information logs to simply taxes calculation from QBO on sales order and invoice.

* 1.2.1 (2022-11-04)
    - Fix for parsing partner's name during import contacts.

* 1.2.0 (2022-10-28)
    - NEW! Support invoice synchronization in different currencies for the same Customer/Vendor.
    - Added support for product variants synchronization from Odoo to QBO. Every variant is created as new product in QBO with unique name containing attribute name(s) and value(s).
    - Other small fixes and improvements.

* 1.1.3 (2022-10-22)
    - Fix for importing more than 100 accounts by one time.

* 1.1.2 (2022-09-19)
    - Fix for parsing last payment date from Quickbooks module settings.

* 1.1.1 (2022-08-30)
    - Improved functionality of working with Taxes on Invoice for non-US based companies.

* 1.1.0 (2022-08-17)
    - Added customer reference for vendor bill export.

* 1.0.6 (2022-07-25)
    - Added possibility export storable product as consumable.
    - Marking invoice line as taxable in more advanced way. Analyzing tax on the invoice line itself and on the product as well.
    - Fixed adding company name to QBO when it has parent company.

* 1.0.5 (2022-05-05)
    - Additional pop-up messages for clicking button "Get QBO Taxes".


* 1.0.4 (2022-04-26)
    - Improved Getting Taxes from QBO on Sales Orders. Now no need to manually export every product individually, export of all products will be launched recursively.
    - "Get QBO Taxes" functionality is disabled in case "Sync Products" is switched off.
    - Getting QBO Taxes button is adapted to take into account "Sync Products as Categories" setting. In this case it will be needed to set "To QBO Product Type" field on category level to tell QBO if it is Storable or Service Category.
    - Fix impossibility to export invoices from Odoo if taxes are disabled in QBO.
    - Fix error in saving Odoo Settings in case there is no Quickbooks Settings defined (issue with empty Default Stock Valuation Account).

* 1.0.3 (2022-03-15)
    - Fix for error when clicking on "Get QBO Taxes" button after they were manually changed.
    - Improved "Get QBO Tax" functionality for Sales Orders and Invoices (now if product is non-taxable - Taxes will be emptied out on SO/Invoice line).

* 1.0.2 (2022-02-10)
    - Bug fixes and other minor improvements.

* 1.0.1 (2021-10-01)
    - Initial version.
