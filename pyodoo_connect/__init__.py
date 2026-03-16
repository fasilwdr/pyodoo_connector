# -*- coding: utf-8 -*-
#############################################################################
# Author: Fasil
# Email: fasilwdr@hotmail.com
# WhatsApp: https://wa.me/966538952934
# Facebook: https://www.facebook.com/fasilwdr
# Instagram: https://www.instagram.com/fasilwdr
#############################################################################


from .odoo import (
    connect_odoo,
    connect_model,
    OdooSession,
    OdooModel,
    OdooRecord,
    OdooRecordset,
    OdooException,
    OdooConnectionError,
    OdooAuthenticationError,
    OdooRequestError,
    OdooValidationError,
)
from .tools import Command
from .http import connect_http

__version__ = "0.3.0"