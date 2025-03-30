'''
File: main.py
Description: Entry point for the Album Art Viewer application
'''

import atexit
import gi
import sys
import logging
from album_art.utils import suppress_gtk_warnings, setup_logging
from album_art.config import Config
from album_art.mpd_client import Tracker
from album_art.gtk_app import AlbumArtApp
from album_art.fetcher import Fetcher

def main():
    """Main function to run the application."""
    # Setup logging first
    setup_logging(Config)
    logger = logging.getLogger(__name__)
    
    suppress_gtk_warnings()
    
    # Initialize components with proper error handling
    try:
        # Initialize the fetcher first to ensure placeholder image exists
        fetcher = Fetcher()
        
        # Initialize the MPD tracker
        tracker = Tracker()
        atexit.register(tracker.disconnect)
        
        # Initialize and run the GTK application
        app = AlbumArtApp(tracker)
        exit_code = app.run(None)
        sys.exit(exit_code)
    except Exception as e:
        logger.exception(f"Application initialization error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
