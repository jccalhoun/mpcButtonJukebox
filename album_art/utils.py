'''
File: album_art/utils.py
Description: Utility functions for Album Art Viewer with enhanced logging
'''

import os
import warnings
import logging
from typing import Optional

def suppress_gtk_warnings() -> None:
    """Suppress GTK warnings with logging of suppressed warnings."""
    logger = logging.getLogger(f"{__name__}.utils")
    try:
        warnings.filterwarnings('ignore', module='gi.repository.Gtk')
        os.environ['NO_AT_BRIDGE'] = '1'
        os.environ['GTK_A11Y'] = 'none'
        logger.debug("Successfully suppressed GTK warnings")
    except Exception as e:
        logger.error("Failed to suppress GTK warnings", exc_info=True)
        raise

def setup_logging(config) -> None:
    """
    Set up logging configuration for the application with comprehensive initialization.
    
    Args:
        config: Configuration class with logging settings
        
    Raises:
        PermissionError: If log file cannot be created
        ValueError: If invalid log level is specified
    """
    logger = logging.getLogger(f"{__name__}.setup")
    logger.info("Initializing application logging")
    
    try:
        # Validate log directory
        log_dir = os.path.dirname(config.LOG_FILE)
        if not os.path.exists(log_dir):
            logger.info(f"Creating log directory: {log_dir}")
            os.makedirs(log_dir, exist_ok=True)
        
        # Verify log file accessibility
        try:
            with open(config.LOG_FILE, 'a'):
                pass
            logger.debug(f"Verified log file accessibility: {config.LOG_FILE}")
        except IOError as e:
            logger.critical(f"Cannot access log file: {config.LOG_FILE}", exc_info=True)
            raise PermissionError(f"Cannot access log file: {config.LOG_FILE}") from e
        
        # Configure logging
        try:
            logging.basicConfig(
                level=config.LOG_LEVEL,
                format=config.LOG_FORMAT,
                handlers=[
                    logging.FileHandler(config.LOG_FILE),
                    logging.StreamHandler()
                ]
            )
            logger.info(
                f"Logging configured (level: {logging.getLevelName(config.LOG_LEVEL)}, "
                f"file: {config.LOG_FILE})"
            )
            
            # Configure third-party loggers
            third_party_loggers = {
                'gi.repository.Gtk': logging.WARNING,
                'mpd': logging.WARNING,
                'PIL': logging.INFO
            }
            
            for logger_name, level in third_party_loggers.items():
                logging.getLogger(logger_name).setLevel(level)
                logger.debug(f"Set {logger_name} logger level to {logging.getLevelName(level)}")
                
        except ValueError as e:
            logger.critical(f"Invalid log level: {config.LOG_LEVEL}", exc_info=True)
            raise
        except Exception as e:
            logger.critical("Failed to configure logging", exc_info=True)
            raise
            
    except Exception as e:
        logger.critical("Logging setup failed completely", exc_info=True)
        raise