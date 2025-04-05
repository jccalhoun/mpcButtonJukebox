'''
File: album_art/__init__.py
Description: Package initialization with version and import logging
'''

import logging
from typing import List

# Initialize package logger
_logger = logging.getLogger(__name__)
_logger.debug("Initializing album_art package")

# Package version
__version__ = "1.2.0"
_logger.info(f"Album Art Viewer version {__version__}")

# Import tracking
__all__: List[str] = ['load_config', 'validate_paths', 'setup_logging', 'finalize_config', 'suppress_gtk_warnings', 'Tracker', 'AlbumArtApp', 'Fetcher']
_logger.debug(f"Exporting package members: {__all__}")

# Import main components
try:
    from .config_loader import load_config, validate_paths, setup_logging, finalize_config
    from .utils import suppress_gtk_warnings
    from .mpd_client import Tracker
    from .gtk_app import AlbumArtApp
    from .fetcher import Fetcher
    _logger.debug("Successfully imported all package components")
except ImportError as e:
    _logger.critical("Failed to import package components", exc_info=True)
    raise
except Exception as e:
    _logger.critical("Unexpected error during package initialization", exc_info=True)
    raise