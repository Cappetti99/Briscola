"""Compatibility import; the shared window now lives in cardgames.app."""
import sys
from .. import app as _app
sys.modules[__name__] = _app
