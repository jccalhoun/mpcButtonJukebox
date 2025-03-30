'''
File: album_art/mpd_client.py
Description: MPD interaction classes (Tracker) with enhanced logging
'''

from mpd import MPDClient, CommandError  
import threading
import time
import os
import logging
from typing import Optional, Dict, Any, List
from album_art.config import Config
import board
import busio
import adafruit_ht16k33.segments
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import GLib

class Tracker:
    """Tracks the currently playing song and queue length from MPD with comprehensive logging."""
    
    def __init__(self) -> None:
        """Initialize MPD tracker with connection and display setup."""
        self.logger = logging.getLogger(f"{__name__}.Tracker")
        self.logger.info("Initializing MPD tracker")
        
        self.client: MPDClient = MPDClient()
        self.client.timeout = 10
        self.lock: threading.Lock = threading.Lock()
        self.current_song: Optional[Dict[str, Any]] = None
        self.last_queue_length: int = 0
        self.input_buffer: str = ""
        
        # Initialize MPD connection
        if not self.connect():
            self.logger.error("Initial MPD connection failed")
            raise MPDConnectionError("Could not establish initial MPD connection")
        
        # Initialize hardware displays
        self._init_displays()
        
        self.logger.info("MPD tracker initialized successfully")

    def _init_displays(self):
        """Initialize 7-segment displays with error handling."""
        try:
            self.logger.debug("Initializing I2C displays")
            i2c = busio.I2C(board.SCL, board.SDA)
            self.display_queue = adafruit_ht16k33.segments.Seg7x4(i2c, address=0x71)
            self.display_input = adafruit_ht16k33.segments.Seg7x4(i2c, address=0x70)
            self.display_queue.fill(0)
            self.display_input.fill(0)
            self.logger.info("Displays initialized successfully")
        except Exception as e:
            self.logger.critical("Failed to initialize displays", exc_info=True)
            raise DisplayError("Display initialization failed") from e

    def execute_mpd_command(self, command: str, *args) -> Any:
        """Execute an MPD command with automatic reconnection handling.
        
        Args:
            command: The MPD command to execute
            *args: Optional arguments for the command
            
        Returns:
            The result of the command, or None if it failed
        """
        max_attempts = 2  # Try twice at most
        
        for attempt in range(1, max_attempts + 1):
            try:
                with self.lock:
                    self.logger.debug(f"Executing MPD command: {command}")
                    
                    # Check connection first
                    try:
                        self.client.ping()
                    except Exception as e:
                        if attempt == max_attempts:
                            raise  # Re-raise on final attempt
                        
                        self.logger.warning(f"MPD connection lost, reconnecting (attempt {attempt})...")
                        if not self.reconnect_mpd():
                            self.logger.error("Failed to reconnect to MPD")
                            return None
                    
                    # Execute command
                    method = getattr(self.client, command)
                    result = method(*args)
                    self.logger.info(f"Successfully executed MPD command: {command}")
                    return result
                    
            except Exception as e:
                if attempt < max_attempts:
                    self.logger.warning(
                        f"Failed to execute MPD command '{command}' (attempt {attempt}): {str(e)}"
                    )
                    # Try reconnecting before the next attempt
                    self.reconnect_mpd()
                else:
                    self.logger.error(
                        f"Failed to execute MPD command '{command}' after {max_attempts} attempts",
                        exc_info=True
                    )
                    return None

    def connect(self) -> bool:
        """Establish connection to MPD server with detailed logging."""
        self.logger.info(f"Connecting to MPD at {Config.MPDHOST}:{Config.MPDPORT}")
        try:
            self.client.connect(Config.MPDHOST, Config.MPDPORT)
            if Config.MPDPASS:
                self.logger.debug("Authenticating with MPD password")
                self.client.password(Config.MPDPASS)
            
            # Verify connection
            status = self.client.status()
            self.logger.info(f"Connected to MPD (version: {status.get('version', 'unknown')})")
            return True
        except (ConnectionError, CommandError) as e:
            self.logger.error(f"MPD connection failed: {str(e)}", exc_info=True)
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during MPD connection: {str(e)}", exc_info=True)
            return False

    def reconnect_mpd(self, max_attempts: int = 3) -> bool:
        """Reconnect to MPD with retry logic and detailed logging."""
        self.logger.warning(f"Attempting MPD reconnection (max attempts: {max_attempts})")
        
        # Clean up existing connection
        try:
            self.logger.debug("Closing existing MPD connection")
            self.client.close()
            self.client.disconnect()
        except Exception as e:
            self.logger.debug(f"Error closing existing connection: {str(e)}")

        # Create fresh client
        self.client = MPDClient()
        self.client.timeout = 10
        
        for attempt in range(1, max_attempts + 1):
            try:
                self.logger.debug(f"Reconnection attempt {attempt}/{max_attempts}")
                self.client.connect(Config.MPDHOST, Config.MPDPORT)
                if Config.MPDPASS:
                    self.client.password(Config.MPDPASS)
                
                # Verify reconnection
                self.client.ping()
                self.logger.info(f"Successfully reconnected to MPD (attempt {attempt})")
                return True
            except Exception as e:
                remaining = max_attempts - attempt
                if remaining > 0:
                    wait_time = min(2 ** attempt, 10)  # Exponential backoff, max 10 seconds
                    self.logger.warning(
                        f"Reconnection failed (attempt {attempt}), "
                        f"retrying in {wait_time}s... Error: {str(e)}"
                    )
                    time.sleep(wait_time)
        
        self.logger.error(f"Failed to reconnect after {max_attempts} attempts")
        return False

    def check_song_update(self) -> int:
        """Check for song updates with comprehensive state logging."""
        try:
            with self.lock:
                self.logger.debug("Checking for song updates")
                
                # Get current status
                try:
                    status = self.client.status()
                    self.last_queue_length = int(status.get("playlistlength", 0))
                    self.logger.debug(f"Current queue length: {self.last_queue_length}")
                except Exception as e:
                    self.logger.error("Failed to get MPD status", exc_info=True)
                    return 3  # Critical failure

                # Store previous song for change detection
                previous_song = self.current_song
                self.current_song = self.client.currentsong() or {}
                
                # Update queue display
                self.update_queue_display()
                
                # Check for song change
                current_file = self.current_song.get("file")
                if current_file and (not previous_song or previous_song.get("file") != current_file):
                    self.logger.info(f"Song changed to: {current_file}")
                    self._handle_new_song(current_file)
                    return 0  # Song changed
                
                return 2 if current_file else 1  # 2 = no song, 1 = same song
            
        except (ConnectionError, CommandError) as e:
            self.logger.error("MPD connection error in check_song_update", exc_info=True)
            if self.reconnect_mpd():
                self.logger.info("Recovered from MPD connection error")
                return 2  # Retry on next cycle
            return 3  # Critical failure
        except Exception as e:
            self.logger.error("Unexpected error in check_song_update", exc_info=True)
            return 3  # Critical failure

    def _handle_new_song(self, song_file: str):
        """Handle new song detection with proper error handling."""
        try:
            from album_art.fetcher import Fetcher
            fetcher = Fetcher()
            fetcher.get_album_art(song_file, self.client)
            self.logger.info(f"Album art updated for: {song_file}")
        except Exception as e:
            self.logger.error(f"Failed to update album art for {song_file}", exc_info=True)

    def update_queue_display(self) -> None:
        """Update queue display with error handling."""
        try:
            display_value = str(self.last_queue_length).rjust(4)
            self.logger.debug(f"Updating queue display to: {display_value}")
            self.display_queue.fill(0)
            self.display_queue.print(display_value)
        except Exception as e:
            self.logger.error("Failed to update queue display", exc_info=True)

    def update_input_display(self) -> None:
        """Update input display with error handling."""
        try:
            display_value = self.input_buffer.rjust(4)
            self.logger.debug(f"Updating input display to: {display_value}")
            self.display_input.fill(0)
            self.display_input.print(display_value)
        except Exception as e:
            self.logger.error("Failed to update input display", exc_info=True)

    def handle_input(self, key: str) -> None:
        """Handle user input with validation and logging."""
        if not key.isdigit():
            self.logger.debug(f"Ignoring non-digit input: {key}")
            return
            
        if len(self.input_buffer) == 4:  
            self.logger.debug("Input buffer full, clearing for new input")
            self.input_buffer = ""
            
        self.input_buffer += key
        self.input_buffer = self.input_buffer[-4:]
        self.logger.info(f"Current input: {self.input_buffer}")
        
        GLib.idle_add(self.update_input_display)
        
        if len(self.input_buffer) == 4:
            try:
                line_number = int(self.input_buffer)
                self.logger.info(f"Processing complete input: {line_number}")

                """Check for special commands 
                Summary:

                9999 → skip_song() → Skips to the next song.

                8888 → stop_mpd() → Stops playback.

                7777 → start_mpd() → Starts playback.

                6666 → clear_queue() → Clears the queue."""
                if line_number == 9999:
                    self.logger.info("Special input detected: Skipping to next song")
                    threading.Thread(target=self.skip_song, daemon=True).start()
                elif line_number == 8888:
                    self.logger.info("Special input detected: Stopping playback")
                    threading.Thread(target=self.stop_mpd, daemon=True).start()
                elif line_number == 7777:
                    self.logger.info("Special input detected: Starting playback")
                    threading.Thread(target=self.start_mpd, daemon=True).start()
                elif line_number == 6666:
                    self.logger.info("Special input detected: Clearing queue")
                    threading.Thread(target=self.clear_queue, daemon=True).start()
                else:
                    threading.Thread(
                        target=self.add_song_to_mpd, 
                        args=(line_number,), 
                        daemon=True
                    ).start()
            except ValueError:
                self.logger.error(f"Invalid input conversion: {self.input_buffer}")

    def add_song_to_mpd(self, line_number: int) -> None:
        """Add song to MPD queue with comprehensive logging."""
        self.logger.info(f"Attempting to add song from line {line_number}")
        
        # Validate song list file
        if not os.path.exists(Config.SONG_LIST_PATH):
            self.logger.error(f"Song list file not found: {Config.SONG_LIST_PATH}")
            return

        try:
            # Read song list
            with open(Config.SONG_LIST_PATH, 'r') as file:
                lines = file.readlines()
                self.logger.debug(f"Read {len(lines)} lines from song list")

            # Validate line number
            if not (1 <= line_number <= len(lines)):
                self.logger.error(f"Invalid line number {line_number} (valid range: 1-{len(lines)})")
                return

            song_path = lines[line_number - 1].strip()
            self.logger.info(f"Preparing to add song: {song_path}")
            
            # Ensure MPD connection
            try:
                self.client.ping()
            except Exception:
                self.logger.warning("MPD connection lost, attempting reconnect")
                if not self.reconnect_mpd():
                    self.logger.error("Failed to reconnect to MPD")
                    return

            # Add song to queue
            with self.lock:
                try:
                    self.client.add(song_path)
                    self.last_queue_length += 1
                    self.logger.info(f"Successfully added song: {song_path}")
                    
                    # Update display
                    GLib.idle_add(self.update_queue_display)
                    
                    # Get song metadata for notification
                    song_info = self._get_song_metadata(song_path)
                    self._notify_song_added(song_info, song_path)
                    
                except CommandError as e:
                    self.logger.error(f"MPD command failed while adding song: {str(e)}")

        except Exception as e:
            self.logger.error("Unexpected error in add_song_to_mpd", exc_info=True)

    def skip_song(self) -> None:
        """Skip to the next song in MPD queue."""
        self.logger.info("Skipping to next song in MPD queue")
        self.execute_mpd_command("next")

    def stop_mpd(self) -> None:
        """Stop MPD playback."""
        self.logger.info("Stopping MPD playback")
        self.execute_mpd_command("stop")

    def start_mpd(self) -> None:
        """Start MPD playback."""
        self.logger.info("Starting MPD playback")
        self.execute_mpd_command("play")

    def clear_queue(self) -> None:
        """Clear the MPD queue."""
        self.logger.info("Clearing MPD queue")
        self.execute_mpd_command("clear")

    def _get_song_metadata(self, song_path: str) -> str:
        """Get song metadata with fallback to filename."""
        try:
            song_data = self.client.find("file", song_path)
            if song_data and len(song_data) > 0:
                artist = song_data[0].get("artist", "")
                title = song_data[0].get("title", "")
                if artist and title:
                    return f"{artist} - {title}"
                elif title:
                    return title
            return song_path.split('/')[-1]
        except Exception as e:
            self.logger.warning(f"Failed to get song metadata, using filename: {str(e)}")
            return song_path.split('/')[-1]

    def _notify_song_added(self, song_info: str, song_path: str):
        """Notify UI about added song."""
        try:
            from album_art.gtk_app import app_instance
            if app_instance:
                GLib.idle_add(app_instance.show_queue_notification, song_info)
                self.logger.debug(f"Sent notification for added song: {song_path}")
        except Exception as e:
            self.logger.warning("Failed to send song added notification", exc_info=True)

    def disconnect(self) -> None:
        """Cleanly disconnect from MPD with logging."""
        self.logger.info("Disconnecting from MPD")
        try:
            self.client.close()
            self.client.disconnect()
            self.logger.info("Successfully disconnected from MPD")
        except Exception as e:
            self.logger.warning("Error during MPD disconnection", exc_info=True)