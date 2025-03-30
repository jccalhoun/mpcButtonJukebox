'''
File: album_art/exceptions.py
Description: Custom exception classes for the Album Art Viewer application
'''

class AlbumArtError(Exception):
    """Base exception class for Album Art Viewer application."""
    pass

class ConfigError(AlbumArtError):
    """Exception raised for configuration errors."""
    pass

class MPDConnectionError(AlbumArtError):
    """Exception raised for MPD connection issues."""
    pass

class AlbumArtFetchError(AlbumArtError):
    """Exception raised when album art cannot be fetched."""
    pass

class DisplayError(AlbumArtError):
    """Exception raised for hardware display issues."""
    pass

class ImageProcessingError(AlbumArtError):
    """Exception raised for image processing errors."""
    pass
