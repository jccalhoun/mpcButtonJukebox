'''
File: album_art/exceptions.py
Description: Custom exceptions for the Album Art Viewer application
'''

class AlbumArtError(Exception):
    """Base exception class for all Album Art Viewer application errors."""
    pass

class AlbumArtFetchError(AlbumArtError):
    """Exception raised when album art fetching fails."""
    pass

class ImageProcessingError(AlbumArtError):
    """Exception raised when image processing operations fail."""
    pass

class MPDConnectionError(AlbumArtError):
    """Exception raised when MPD connection operations fail."""
    pass

class ConfigurationError(AlbumArtError):
    """Exception raised when configuration loading or validation fails."""
    pass
