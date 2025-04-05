'''
File: album_art/fetcher.py
Description: Handles fetching album art from embedded metadata or file system with improved error handling.
'''

import os
import io
import logging
from PIL import Image
import mutagen.id3
import mutagen.flac
import mutagen.mp4
from typing import Optional, Set, Dict, Any
from album_art.exceptions import AlbumArtFetchError, ImageProcessingError
from mpd import MPDClient

class Fetcher:
    """Fetches album art from music files or directories."""
    
    def __init__(self, config):
        """Initialize the fetcher with logging and configuration."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.Fetcher")
        self.logger.info("Initializing album art fetcher")
        
        try:
            # Get placeholder location from config
            placeholder_loc = self.config['file_paths']['placeholder_loc']
            
            # Ensure the placeholder image exists
            if not os.path.exists(placeholder_loc):
                self.logger.warning(f"Placeholder image not found at {placeholder_loc}, creating new one")
                self._create_placeholder_image()
            else:
                self.logger.debug(f"Using existing placeholder image at {placeholder_loc}")
        except Exception as e:
            self.logger.critical("Failed to initialize fetcher due to placeholder image issue", exc_info=True)
            raise ImageProcessingError("Failed to initialize fetcher") from e

    def _create_placeholder_image(self):
        """Create a simple placeholder image if one doesn't exist."""
        try:
            placeholder_loc = self.config['file_paths']['placeholder_loc']
            image_size = self.config['display']['placeholder_image_size']
            image_color = self.config['display']['placeholder_image_color']
            
            self.logger.debug(f"Creating placeholder image at {placeholder_loc}")
            img = Image.new('RGB', tuple(image_size), color=tuple(image_color))
            img.save(placeholder_loc, "PNG")
            self.logger.info(f"Successfully created placeholder image at {placeholder_loc}")
        except Exception as e:
            placeholder_loc = self.config['file_paths']['placeholder_loc']
            self.logger.error(f"Failed to create placeholder image at {placeholder_loc}", exc_info=True)
            raise ImageProcessingError(f"Failed to create placeholder image: {str(e)}") from e
    
    def mutagen_fetcher(self, song_path: str) -> Optional[bytes]:
        """Extracts embedded album art using Mutagen library."""
        if not os.path.exists(song_path):
            self.logger.warning(f"File does not exist: {song_path}")
            return None
        
        extraction_methods = [
            (self._extract_id3_art, "ID3 (MP3)"),
            (self._extract_flac_art, "FLAC"),
            (self._extract_mp4_art, "MP4/AAC")
        ]
        
        for extraction_method, format_name in extraction_methods:
            try:
                self.logger.debug(f"Attempting {format_name} extraction for {os.path.basename(song_path)}")
                art_data = extraction_method(song_path)
                if art_data:
                    self.logger.info(f"Successfully found {format_name} album art in: {os.path.basename(song_path)}")
                    return art_data
            except Exception as e:
                self.logger.debug(f"Error extracting {format_name} album art from {os.path.basename(song_path)}: {str(e)}")
        
        self.logger.warning(f"No album art found in any supported format for: {os.path.basename(song_path)}")
        return None  # No album art found
    
    def _extract_id3_art(self, song_path: str) -> Optional[bytes]:
        """Extract album art from ID3 tags (MP3 files)."""
        try:
            id3 = mutagen.id3.ID3(song_path)
            apic_frames = id3.getall('APIC')
            if apic_frames and apic_frames[0].data:  # Ensure there's at least one APIC frame
                self.logger.debug(f"Found APIC frame in ID3 tags for {os.path.basename(song_path)}")
                return apic_frames[0].data
        except mutagen.id3.ID3NoHeaderError:
            # This is expected for non-MP3 files, so we'll just log at debug level
            self.logger.debug(f"No ID3 header found in {os.path.basename(song_path)}")
            return None
        except Exception as e:
            self.logger.debug(f"ID3 extraction error for {os.path.basename(song_path)}: {str(e)}")
            return None
        self.logger.debug(f"No APIC frames found in ID3 tags for {os.path.basename(song_path)}")
        return None
    
    def _extract_flac_art(self, song_path: str) -> Optional[bytes]:
        """Extract album art from FLAC files."""
        try:
            flac = mutagen.flac.FLAC(song_path)
            if flac.pictures and flac.pictures[0].data:  # Ensure there's at least one embedded picture
                self.logger.debug(f"Found embedded picture in FLAC file {os.path.basename(song_path)}")
                return flac.pictures[0].data
        except mutagen.flac.FLACNoHeaderError:
            # This is expected for non-FLAC files, so we'll just log at debug level
            self.logger.debug(f"No FLAC header found in {os.path.basename(song_path)}")
            return None
        except Exception as e:
            self.logger.debug(f"FLAC extraction error for {os.path.basename(song_path)}: {str(e)}")
            return None
        self.logger.debug(f"No pictures found in FLAC file {os.path.basename(song_path)}")
        return None
    
    def _extract_mp4_art(self, song_path: str) -> Optional[bytes]:
        """Extract album art from MP4/AAC files."""
        try:
            mp4 = mutagen.mp4.MP4(song_path)
            covr_list = mp4.get('covr', [])  # Use `.get()` to avoid KeyError
            if covr_list and covr_list[0]:  # Ensure there's at least one embedded cover
                self.logger.debug(f"Found 'covr' data in MP4 file {os.path.basename(song_path)}")
                return covr_list[0]
        except Exception as e:
            self.logger.debug(f"MP4 extraction error for {os.path.basename(song_path)}: {str(e)}")
            return None
        self.logger.debug(f"No 'covr' data found in MP4 file {os.path.basename(song_path)}")
        return None
    
    def get_album_art(self, song_file: str, mpd_client: MPDClient) -> None:
        """
    Attempts to retrieve album art using multiple methods and save it.
    
    This method implements a fallback chain of strategies to find album art:
    1. First tries MPD's readpicture command (if available)
    2. Then attempts to extract embedded art using Mutagen
    3. Finally looks for common cover art filenames in the song's directory
    
    For each source, the art is resized to a standard size and saved to the
    configured location. If no art is found, a placeholder image is used.
    
    Args:
        song_file: Path to the audio file relative to music library
        mpd_client: Connected MPD client instance
            
    Raises:
        AlbumArtFetchError: If a critical error occurs during fetching
    """
        self.logger.info(f"Starting album art fetch for: {song_file}")
        
        music_library = self.config['file_paths']['music_library']
        full_song_path = os.path.join(music_library, song_file)
        self.logger.debug(f"Full song path: {full_song_path}")

        # Set default placeholder image first
        try:
            placeholder_loc = self.config['file_paths']['placeholder_loc']
            album_art_loc = self.config['file_paths']['album_art_loc']
            
            if not os.path.exists(placeholder_loc):
                self.logger.warning("Placeholder image missing, creating new one")
                self._create_placeholder_image()
                
            default_img = Image.open(placeholder_loc)
            default_img.thumbnail((500, 500))
            default_img.save(album_art_loc, "PNG")
            self.logger.debug("Default placeholder image set successfully")
        except Exception as e:
            self.logger.error("Failed to set default album art", exc_info=True)
            raise AlbumArtFetchError("Failed to set default album art") from e

        if not os.path.exists(full_song_path):
            self.logger.warning(f"Song file does not exist: {full_song_path}")
            return
        
        # Define fetch methods with friendly names for logging
        fetch_methods = [
            ("MPD readpicture", self._fetch_mpd_readpicture),
            ("Mutagen metadata", self._fetch_mutagen_metadata),
            ("File-based cover", self._fetch_file_based_cover)
        ]
        
        # Try each fetch method in sequence
        for method_name, fetch_method in fetch_methods:
            try:
                self.logger.debug(f"Attempting album art fetch method: {method_name}")
                if fetch_method(song_file, mpd_client, full_song_path):
                    self.logger.info(f"Successfully fetched album art using {method_name}")
                    return
            except Exception as e:
                self.logger.warning(f"Album art fetch method {method_name} failed: {str(e)}", exc_info=True)
        
        self.logger.warning(f"All album art fetch methods failed for: {song_file}")

    def _fetch_mpd_readpicture(self, song_file: str, mpd_client: MPDClient, full_song_path: str) -> bool:
        """
        Fetch album art using MPD's readpicture command.
        
        This method uses the MPD protocol's readpicture command to request the embedded 
        album art directly from the MPD server. This is often the most efficient method
        when it's available, as it avoids having to access the file directly.
        
        Args:
            song_file: Path to song file relative to music library
            mpd_client: Connected MPD client instance
            full_song_path: Absolute path to the song file
            
        Returns:
            bool: True if successful, False otherwise
        """
        self.logger.debug("Attempting MPD readpicture method")
        try:
            art_data = mpd_client.readpicture(song_file)
            album_art_loc = self.config['file_paths']['album_art_loc']
            
            if isinstance(art_data, dict) and 'binary' in art_data:
                img_bytes = art_data['binary']
                img = Image.open(io.BytesIO(img_bytes))
                img.thumbnail((500, 500))
                img.save(album_art_loc, "PNG")
                self.logger.debug("Successfully processed album art from MPD readpicture")
                return True
            
            self.logger.debug("MPD readpicture returned no valid art data")
            return False
        except Exception as e:
            self.logger.warning(f"MPD readpicture method failed: {str(e)}")
            return False

    def _fetch_mutagen_metadata(self, song_file: str, mpd_client: MPDClient, full_song_path: str) -> bool:
        """
        Fetch album art using Mutagen metadata extraction.
        
        Returns:
            bool: True if successful, False otherwise
        """
        self.logger.debug("Attempting Mutagen metadata extraction method")
        try:
            art_data = self.mutagen_fetcher(full_song_path)
            album_art_loc = self.config['file_paths']['album_art_loc']
            
            if art_data:
                img = Image.open(io.BytesIO(art_data))
                img.thumbnail((500, 500))
                img.save(album_art_loc, "PNG")
                self.logger.debug("Successfully processed album art from Mutagen metadata")
                return True
            
            self.logger.debug("No album art found in mutagen metadata")
            return False
        except Exception as e:
            self.logger.warning(f"Mutagen metadata extraction failed: {str(e)}")
            return False

    def _fetch_file_based_cover(self, song_file: str, mpd_client: MPDClient, full_song_path: str) -> bool:
        """
        Look for album art image files in the same directory as the music file.
        
        Returns:
            bool: True if successful, False otherwise
        """
        self.logger.debug("Attempting file-based cover art method")
        try:
            song_dir = os.path.dirname(full_song_path)
            album_art_loc = self.config['file_paths']['album_art_loc']
            
            if not os.path.isdir(song_dir):
                self.logger.warning(f"Song directory does not exist: {song_dir}")
                return False
                
            # Use cover formats from config
            cover_formats = self.config['cover_formats']
            
            self.logger.debug(f"Searching for cover art files in: {song_dir}")
            for filename in cover_formats:
                cover_path = os.path.join(song_dir, filename)
                if os.path.exists(cover_path):
                    self.logger.debug(f"Found cover art file: {cover_path}")
                    try:
                        img = Image.open(cover_path)
                        img.thumbnail((500, 500))
                        img.save(album_art_loc, "PNG")
                        self.logger.debug(f"Successfully processed cover art from file: {filename}")
                        return True
                    except Exception as e:
                        self.logger.warning(f"Error processing cover art file {filename}: {str(e)}")
                        # Continue to next file
            
            self.logger.debug(f"No valid cover art files found in: {song_dir}")
            return False
        except Exception as e:
            self.logger.warning(f"File-based cover art method failed: {str(e)}")
            return False