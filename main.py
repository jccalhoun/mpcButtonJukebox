'''
File: main.py
Description: Entry point for the Album Art Viewer application
'''

import atexit
import gi
import sys
import logging
from album_art.utils import suppress_gtk_warnings
from album_art.config_loader import load_config, validate_paths, setup_logging, finalize_config
from album_art.mpd_client import Tracker
from album_art.gtk_app import AlbumArtApp
from album_art.fetcher import Fetcher

def main():
    """Main function to run the application."""
    # Load configuration
    try:
        config = load_config('config.yaml')
    except Exception as e:
        print(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # Setup logging first
    setup_logging(config)
    logger = logging.getLogger(__name__)
    
    # Finalize configuration (validates and prepares environment)
    try:
        config = finalize_config(config)
    except Exception as e:
        logger.exception(f"Configuration finalization error: {e}")
        sys.exit(1)
    
    suppress_gtk_warnings()
    
    # Initialize components with proper error handling
    try:
        # Initialize the fetcher first to ensure placeholder image exists
        fetcher = Fetcher(config)
        
        # Initialize the MPD tracker
        tracker = Tracker(config)
        atexit.register(tracker.disconnect)
        
        # Initialize and run the GTK application
        app = AlbumArtApp(tracker, config)
        exit_code = app.run(None)
        sys.exit(exit_code)
    except Exception as e:
        logger.exception(f"Application initialization error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
