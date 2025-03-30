'''
File: album_art/config.py
Description: Configuration settings for the Album Art Viewer
'''

import os
import logging

class Config:
    """Application configuration settings for the MPD Album Art Viewer."""
    
    # File and path settings
    ALBUM_ART_LOC: str = os.path.expanduser("~/Downloads/.aartminip.png")
    PLACEHOLDER_LOC: str = os.path.expanduser("~/Downloads/.placeholder.png")
    MUSIC_LIBRARY: str = os.path.expanduser("~/Music")
    SONG_LIST_PATH: str = os.path.expanduser("~/Music/song_list.txt")
    
    # Album art detection settings
    COVER_FORMATS = {
        "cover.jpg", "folder.jpg", "folder.png", 
        "folder.jpeg", "cover.jpeg", "cover.png"
    }
    
    # MPD connection settings
    MPDHOST: str = "localhost"
    MPDPORT: str = "6600"
    MPDPASS: bool = False
    
    # Logging configuration
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_FILE = os.path.expanduser("~/album_art.log")
    
    # Album art display configuration options
    PLACEHOLDER_IMAGE_SIZE: tuple = (500, 500)
    PLACEHOLDER_IMAGE_COLOR: tuple = (0, 0, 0)
    SONG_INFO_DISPLAY_DURATION: int = 10
    QUEUE_NOTIFICATION_DURATION: int = 5

    @classmethod
    def validate_paths(cls):
        """Validate that configured paths exist and are accessible."""
        logger = logging.getLogger(__name__)
        paths_to_check = [
            (cls.MUSIC_LIBRARY, "Music library"),
            (os.path.dirname(cls.LOG_FILE), "Log file directory")
        ]
        
        for path, description in paths_to_check:
            if not os.path.exists(path):
                logger.error(f"{description} path does not exist: {path}")
                raise FileNotFoundError(f"{description} path not found: {path}")
            if not os.access(path, os.R_OK):
                logger.error(f"Insufficient permissions for {description} path: {path}")
                raise PermissionError(f"Cannot access {description} path: {path}")
        
        logger.debug("Configuration paths validated successfully")