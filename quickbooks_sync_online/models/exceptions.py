# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).


class OdooJobError(Exception):

    def __init__(self, msg):
        super(OdooJobError, self).__init__(msg)
