'''
File: album_art/gtk_app.py
Description: GTK-based Album Art Viewer Application with improved error handling, logging, and comprehensive type hints
'''
app_instance = None
import time
import gi
import threading
import os
import logging
from typing import Dict, List, Tuple, Optional, Any, Union, Callable, TypeVar, cast
from gi.repository import Gtk, GLib, Gdk, Pango
from album_art.config import Config
from album_art.mpd_client import Tracker
from album_art.fetcher import Fetcher
from album_art.exceptions import AlbumArtError
from PIL import Image
import numpy as np

# Define some type aliases for clarity
RGB = List[int]  # RGB color as [r, g, b]
SongInfo = Dict[str, str]  # MPD song information dictionary

class AlbumArtApp(Gtk.Application):
    """Main GTK application for displaying album art and handling user input."""
    
    def __init__(self, tracker: Tracker) -> None:
        super().__init__()
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.tracker: Tracker = tracker
        self.image: Optional[Gtk.Picture] = None
        self.tracker_thread: Optional[threading.Thread] = None
        self.fetcher: Fetcher = Fetcher()
        
        # Set the global app_instance
        global app_instance
        app_instance = self
        
        # New attributes for artist and title display
        self.artist_label: Optional[Gtk.Label] = None
        self.title_label: Optional[Gtk.Label] = None
        self.window: Optional[Gtk.ApplicationWindow] = None
        self.css_provider: Optional[Gtk.CssProvider] = None
        self.queue_notification_label: Optional[Gtk.Label] = None
        
        self.logger.info("AlbumArtApp initialized")
    
    def get_dominant_edge_colors(self, image_path: str) -> Tuple[RGB, RGB]:
        """Extract dominant colors from left and right edges of the album art using NumPy."""
        if not os.path.exists(image_path):
            self.logger.error(f"Image file not found: {image_path}")
            return [0, 0, 0], [0, 0, 0]
            
        try:
            img: Image.Image = Image.open(image_path)
            img_array: np.ndarray = np.array(img)
            
            # Get image dimensions
            height: int
            width: int
            height, width = img_array.shape[:2]
            
            # Sample pixels from left and right edges
            sample_points: int = min(20, height)
            sample_indices: np.ndarray = np.linspace(0, height-1, sample_points, dtype=int)
            
            # Extract left and right edge pixels
            left_edge_pixels: np.ndarray = img_array[sample_indices, 0, :3]  # x=0
            right_edge_pixels: np.ndarray = img_array[sample_indices, width-1, :3]  # x=width-1
            
            # Calculate mean colors
            left_color: np.ndarray = np.mean(left_edge_pixels, axis=0).astype(int)
            right_color: np.ndarray = np.mean(right_edge_pixels, axis=0).astype(int)
            
            self.logger.debug(f"Dominant left edge color: RGB{tuple(left_color)}")
            self.logger.debug(f"Dominant right edge color: RGB{tuple(right_color)}")
            
            return left_color.tolist(), right_color.tolist()
        except Exception as e:
            self.logger.error(f"Error extracting colors from image: {image_path} - {str(e)}", exc_info=True)
            return [0, 0, 0], [0, 0, 0]  # Default to black if error occurs
    
    def update_background_gradient(self, left_color: RGB, right_color: RGB) -> None:
        """Update the window background with a gradient using the dominant edge colors."""
        if not self.css_provider:
            self.css_provider = Gtk.CssProvider()
        
        try:
            # Convert RGB to hex
            left_hex: str = "#{:02x}{:02x}{:02x}".format(*left_color)
            right_hex: str = "#{:02x}{:02x}{:02x}".format(*right_color)
            
            # Create CSS with linear gradient
            css: str = f"""
                window {{
                    background: linear-gradient(to right, {left_hex}, {right_hex});
                }}
            """
            
            self.css_provider.load_from_data(css.encode('utf-8'))
            
            # Apply CSS to window
            if self.window:
                context: Gtk.StyleContext = self.window.get_style_context()
                context.add_provider(self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                self.logger.debug(f"Updated background gradient from {left_hex} to {right_hex}")
            else:
                self.logger.warning("Cannot update background: window not initialized")
        except Exception as e:
            self.logger.error(f"Failed to update background gradient: {str(e)}", exc_info=True)
            # Fall back to a solid black background
            try:
                css = """
                    window {
                        background-color: #000000;
                    }
                """
                self.css_provider.load_from_data(css.encode('utf-8'))
                if self.window:
                    context: Gtk.StyleContext = self.window.get_style_context()
                    context.add_provider(self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            except Exception as e2:
                self.logger.error(f"Failed to set fallback background: {str(e2)}", exc_info=True)
    
    def do_activate(self) -> None:
        """Initialize the GTK window and UI components."""
        try:
            self.logger.info("Activating AlbumArtApp")
            self.window = Gtk.ApplicationWindow(application=self)
            self.window.set_title("MPD Album Art Viewer")
            self.window.set_default_size(500, 500)
            
            # Make the window fullscreen
            self.window.fullscreen()
            
            # Create an overlay container to display text over the image
            overlay: Gtk.Overlay = Gtk.Overlay()
            self.window.set_child(overlay)
            
            # Create the image widget
            self.image = Gtk.Picture()
            overlay.set_child(self.image)
            
            # Create a vertical box for labels at the bottom of the screen
            vbox: Gtk.Box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            vbox.set_valign(Gtk.Align.END)  # Align to bottom
            vbox.set_margin_bottom(20)  # Add some margin
            
            # Create artist label with larger font
            self.artist_label = Gtk.Label()
            self.artist_label.set_markup('<span foreground="white" font="24" weight="bold">No Artist</span>')
            self.artist_label.set_halign(Gtk.Align.CENTER)
            self.artist_label.set_ellipsize(Pango.EllipsizeMode.END)
            
            # Create title label with larger font
            self.title_label = Gtk.Label()
            self.title_label.set_markup('<span foreground="white" font="18">No Title</span>')
            self.title_label.set_halign(Gtk.Align.CENTER)
            self.title_label.set_ellipsize(Pango.EllipsizeMode.END)
            
            # Add labels to vbox
            vbox.append(self.artist_label)
            vbox.append(self.title_label)
            
            # Add semi-transparent background to labels
            css_provider: Gtk.CssProvider = Gtk.CssProvider()
            css_provider.load_from_data(b"""
                label {
                    padding: 5px 6px;
                    border-radius: 5px;
                }
                
                .has-text {
                    background-color: rgba(0, 0, 0, 0.7);
                }
            """)
            self.artist_label.get_style_context().add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self.title_label.get_style_context().add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            
            # Add the vbox to the overlay
            overlay.add_overlay(vbox)
            
            # Create queue notification label
            self.queue_notification_label = Gtk.Label()
            self.queue_notification_label.set_markup('<span foreground="white" font="18" weight="bold"></span>')
            self.queue_notification_label.set_halign(Gtk.Align.CENTER)
            self.queue_notification_label.set_valign(Gtk.Align.CENTER)  # Center in the screen
            self.queue_notification_label.set_ellipsize(Pango.EllipsizeMode.END)

            # Add the label to the overlay
            overlay.add_overlay(self.queue_notification_label)

            # Apply semi-transparent background to the notification label
            self.queue_notification_label.get_style_context().add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

            # Add key event controller
            key_controller: Gtk.EventControllerKey = Gtk.EventControllerKey()
            key_controller.connect("key-pressed", self.on_key_press)
            self.window.add_controller(key_controller)
            
            # Apply initial CSS for background color (will be updated later)
            self.css_provider = Gtk.CssProvider()
            self.css_provider.load_from_data(b"""
                window {
                    background-color: #000000;  /* Initial black background */
                }
            """)
            
            context: Gtk.StyleContext = self.window.get_style_context()
            context.add_provider(self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            
            # Start MPD monitoring thread
            self.tracker_thread = threading.Thread(target=self.mpd_loop, daemon=True)
            self.tracker_thread.start()
            self.logger.info("MPD monitoring thread started")
            
            self.window.present()
            GLib.idle_add(self.update_album_art)
            self.logger.info("AlbumArtApp activation completed")
        except Exception as e:
            self.logger.critical(f"Failed to activate AlbumArtApp: {str(e)}", exc_info=True)
            raise AlbumArtError(f"Application initialization failed: {str(e)}")
    
    def on_key_press(self, controller: Gtk.EventControllerKey, keyval: int, keycode: int, state: Gdk.ModifierType) -> bool:
        """Handle key press events."""
        try:
            # Handle Escape key to exit fullscreen or close the app
            if keyval == Gdk.KEY_Escape:
                window: Gtk.Window = cast(Gtk.Window, controller.get_widget())
                if window.is_fullscreen():
                    self.logger.info("Exiting fullscreen mode")
                    window.unfullscreen()
                    return True  # Event handled
                else:
                    self.logger.info("Closing application")
                    self.quit()
                    return True  # Event handled
            
            # Process numeric input
            keychar: Optional[str] = chr(keyval) if 48 <= keyval <= 57 else None  # 48-57 are ASCII for 0-9
            if keychar:  # If the key pressed is a digit
                self.logger.debug(f"Numeric key pressed: {keychar}")
                # Forward the input to the tracker
                self.tracker.handle_input(keychar)
            
            return False  # Allow event propagation
        except Exception as e:
            self.logger.error(f"Error handling key press event: {str(e)}", exc_info=True)
            return False  # Allow event propagation in case of error
    
    def update_album_art(self) -> bool:
        """Updates the displayed album art and background colors."""
        try:
            if not os.path.exists(Config.ALBUM_ART_LOC):
                self.logger.warning(f"Album art file not found: {Config.ALBUM_ART_LOC}")
                self.set_fallback_image()
                return False
                
            # Update the album art display
            texture: Gdk.Texture = Gdk.Texture.new_from_filename(Config.ALBUM_ART_LOC)
            self.image.set_paintable(texture)
            
            # Extract dominant colors from the album art edges and update background
            left_color, right_color = self.get_dominant_edge_colors(Config.ALBUM_ART_LOC)
            self.update_background_gradient(left_color, right_color)
            self.logger.info(f"Updated album art from {Config.ALBUM_ART_LOC}")
        except Exception as e:
            self.logger.error(f"Error updating album art: {str(e)}", exc_info=True)
            self.set_fallback_image()
        
        return False  # Don't call again
    
    def set_fallback_image(self) -> None:
        """Displays a placeholder image and sets a default background."""
        try:
            if not os.path.exists(Config.PLACEHOLDER_LOC):
                self.logger.error(f"Placeholder image not found: {Config.PLACEHOLDER_LOC}")
                # Create an emergency fallback with a black background
                self.update_background_gradient([0, 0, 0], [0, 0, 0])
                return
                
            texture: Gdk.Texture = Gdk.Texture.new_from_filename(Config.PLACEHOLDER_LOC)
            self.image.set_paintable(texture)
            # Use default black background for placeholder
            self.update_background_gradient([0, 0, 0], [0, 0, 0])
            self.logger.info("Set fallback image")
        except Exception as e:
            self.logger.error(f"Fallback image error: {str(e)}", exc_info=True)
            # Last resort: Just set a black background
            try:
                self.update_background_gradient([0, 0, 0], [0, 0, 0])
            except Exception as e2:
                self.logger.critical(f"Critical error setting fallback image: {str(e2)}", exc_info=True)
    
    def update_song_info(self, artist: str, title: str) -> bool:
        """Updates the artist and title labels."""
        try:
            if not self.artist_label or not self.title_label:
                self.logger.warning("Cannot update song info: Labels not initialized")
                return False
                
            # Escape any Pango markup characters in the text
            safe_artist: str = artist.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            safe_title: str = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            
            # Add CSS class for background
            self.artist_label.get_style_context().add_class("has-text")
            self.title_label.get_style_context().add_class("has-text")
            
            self.artist_label.set_markup(f'<span foreground="white" font="16" weight="bold">{safe_artist}</span>')
            self.title_label.set_markup(f'<span foreground="white" font="14">{safe_title}</span>')
            
            self.logger.info(f"Updated song info: {artist} - {title}")

            # Schedule the text to disappear after the configured duration
            GLib.timeout_add_seconds(Config.SONG_INFO_DISPLAY_DURATION, self.clear_song_info)
        except Exception as e:
            self.logger.error(f"Error updating song info: {str(e)}", exc_info=True)

        return False  # Don't call again
    
    def clear_song_info(self) -> bool:
        """Clears the artist and title labels."""
        try:
            if not self.artist_label or not self.title_label:
                return False
                
            self.artist_label.set_text("")
            self.title_label.set_text("")
            
            # Remove CSS class when empty
            self.artist_label.get_style_context().remove_class("has-text")
            self.title_label.get_style_context().remove_class("has-text")
            self.logger.debug("Cleared song info display")
        except Exception as e:
            self.logger.error(f"Error clearing song info: {str(e)}", exc_info=True)
            
        return False  # Don't call again
    
    def show_queue_notification(self, song_info: str) -> bool:
        """Displays a notification about the song added to the queue."""
        try:
            if not self.queue_notification_label:
                self.logger.warning("Cannot show notification: Label not initialized")
                return False
                
            # Escape any Pango markup characters in the text
            safe_text: str = song_info.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            
            # Add the CSS class for background
            self.queue_notification_label.get_style_context().add_class("has-text")
        
            self.queue_notification_label.set_markup(
                f'<span foreground="white" font="16" weight="bold">Added to queue:\n{safe_text}</span>'
            )
            
            self.logger.info(f"Queue notification displayed: {song_info}")
            
            # Schedule the notification to disappear after the configured duration
            GLib.timeout_add_seconds(Config.QUEUE_NOTIFICATION_DURATION, self.clear_queue_notification)
        except Exception as e:
            self.logger.error(f"Error showing queue notification: {str(e)}", exc_info=True)
        
        return False  # Don't call again

    def clear_queue_notification(self) -> bool:
        """Clears the queue notification label."""
        try:
            if not self.queue_notification_label:
                return False
                
            self.queue_notification_label.set_text("")
            # Remove the CSS class when empty
            self.queue_notification_label.get_style_context().remove_class("has-text")
            self.logger.debug("Cleared queue notification")
        except Exception as e:
            self.logger.error(f"Error clearing queue notification: {str(e)}", exc_info=True)
            
        return False  # Don't call again
    

    def mpd_loop(self) -> None:
        """Continuously checks MPD for song updates and updates UI."""
        last_song_path: Optional[str] = None
        connection_retry_delay: int = 2  # seconds
        connection_attempts: int = 0
        max_connection_attempts: int = 10

        self.logger.info("Starting MPD monitoring loop")
        
        while True:
            try:
                # Check MPD connection and reconnect if needed
                connection_attempts = self._ensure_mpd_connection(connection_attempts, max_connection_attempts, connection_retry_delay)
                if connection_attempts > max_connection_attempts:
                    time.sleep(30)  # Wait longer between attempts after max is reached
                    connection_attempts = 5  # Reset but not to 0 to avoid too frequent attempts
                    continue
                    
                # After ensuring connection is active, check for song updates
                song_state: int = self.tracker.check_song_update()
                
                # Handle song changes if detected
                last_song_path = self._handle_song_change(song_state, last_song_path)
                
                # Wait for MPD events with retry mechanism
                self._wait_for_mpd_events()
                    
            except Exception as e:
                self.logger.error(f"Error in mpd_loop: {str(e)}", exc_info=True)
                time.sleep(5)  # Add delay to avoid tight loop in case of recurring errors

    def _ensure_mpd_connection(self, connection_attempts: int, max_connection_attempts: int, connection_retry_delay: int) -> int:
        """Ensure MPD connection is active, reconnect if needed."""
        try:
            self.tracker.client.ping()
            # Reset connection attempts counter on successful ping
            return 0
        except Exception as e:
            connection_attempts += 1
            self.logger.warning(
                f"MPD connection lost (attempt {connection_attempts}/{max_connection_attempts}): {str(e)}"
            )
            
            if self.tracker.reconnect_mpd():
                self.logger.info("MPD reconnection successful")
                return 0
            else:
                self.logger.error(f"MPD reconnection failed, retrying in {connection_retry_delay} seconds...")
                time.sleep(connection_retry_delay)
                return connection_attempts
        
    def _handle_song_change(self, song_state: int, last_song_path: Optional[str]) -> Optional[str]:
        """Handle song changes and update UI accordingly."""
        current_song_path: Optional[str] = self.tracker.current_song.get("file") if self.tracker.current_song else None
        if song_state == 0 and current_song_path != last_song_path:
            self.logger.info(f"Detected song change: {current_song_path}")
            GLib.idle_add(self.update_album_art)
            
            # Update song info if we have artist/title labels
            if hasattr(self, 'artist_label') and hasattr(self, 'title_label') and self.tracker.current_song:
                artist: str = self.tracker.current_song.get("artist", "Unknown Artist")
                title: str = self.tracker.current_song.get("title", 
                        os.path.basename(self.tracker.current_song.get("file", "Unknown Title")))
                GLib.idle_add(self.update_song_info, artist, title)
            
            return current_song_path
        
        return last_song_path
        
    def _wait_for_mpd_events(self) -> None:
        """Wait for MPD events with robust reconnection mechanism."""
        retry_count: int = 3
        
        while retry_count > 0:
            try:
                changes: List[str] = self.tracker.client.idle("player")
                if changes:  # Only log if actual changes occurred
                    self.logger.debug(f"MPD changes detected: {changes}")
                # Reset retry count on success
                retry_count = 3
                return
                
            except ConnectionError as e:
                self.logger.debug(f"MPD idle connection reset: {str(e)}")
                retry_count -= 1
                
                # Try to reconnect using the tracker's established method
                if retry_count > 0:
                    self.logger.info("Attempting MPD reconnection from event handler")
                    if self.tracker.reconnect_mpd():
                        self.logger.info("Successfully reconnected to MPD from event handler")
                        continue  # Skip the delay and try again immediately
                    else:
                        self.logger.warning("MPD reconnection failed from event handler")
                
                # Add delay before retry or final failure
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Unexpected error in idle command: {str(e)}", exc_info=True)
                retry_count -= 1
                time.sleep(1)
        
        # If all retries failed, add a longer delay to avoid tight loop
        if retry_count == 0:
            self.logger.warning("All MPD idle retries failed, adding delay to avoid CPU spike")
            time.sleep(2)
