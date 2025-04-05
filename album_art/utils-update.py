'''
File: album_art/utils.py
Description: Utility functions for Album Art Viewer with enhanced logging
'''

import os
import warnings
import logging
from typing import Optional, Dict, Any

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

def setup_logging(config: Dict[str, Any]) -> None:
    """
    Set up logging configuration for the application with comprehensive initialization.
    
    Args:
        config: Configuration dictionary loaded from YAML file
        
    Raises:
        PermissionError: If log file cannot be created
        ValueError: If invalid log level is specified
    """
    # Create a basic logger to record setup process
    logger = logging.getLogger(f"{__name__}.setup")
    logger.info("Initializing application logging")
    
    try:
        # Extract configuration values
        log_file = config['file_paths']['log_file']
        log_level_name = config['logging']['level']
        log_format = config['logging']['format']
        
        # Convert log level name to logging constant
        log_level = getattr(logging, log_level_name.upper())
        
        # Validate log directory
        log_dir = os.path.dirname(log_file)
        if not os.path.exists(log_dir):
            logger.info(f"Creating log directory: {log_dir}")
            os.makedirs(log_dir, exist_ok=True)
        
        # Verify log file accessibility
        try:
            with open(log_file, 'a'):
                pass
            logger.debug(f"Verified log file accessibility: {log_file}")
        except IOError as e:
            logger.critical(f"Cannot access log file: {log_file}", exc_info=True)
            raise PermissionError(f"Cannot access log file: {log_file}") from e
        
        # Configure logging
        try:
            logging.basicConfig(
                level=log_level,
                format=log_format,
                handlers=[
                    logging.FileHandler(log_file),
                    logging.StreamHandler()
                ]
            )
            logger.info(
                f"Logging configured (level: {logging.getLevelName(log_level)}, "
                f"file: {log_file})"
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
            logger.critical(f"Invalid log level: {log_level_name}", exc_info=True)
            raise
        except Exception as e:
            logger.critical("Failed to configure logging", exc_info=True)
            raise
            
    except Exception as e:
        logger.critical("Logging setup failed completely", exc_info=True)
        raise
