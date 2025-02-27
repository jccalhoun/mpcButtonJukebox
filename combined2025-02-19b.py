import gi
gi.require_version("Gtk", "4.0")  # Use GTK 4
from gi.repository import Gtk, GLib, Gdk
from PIL import Image
import os
import threading
import io
import subprocess
import time
import sys
import board
import busio
import adafruit_ht16k33.segments
from mpd import MPDClient, CommandError  
import mutagen.id3
import mutagen.flac
import mutagen.mp4

# Album Art Locations
album_art_loc = os.path.expanduser("~/Downloads/.aartminip.png")
placeholder_loc = os.path.expanduser("~/Downloads/.placeholder.png")

# MPD Configuration
MPDHOST = "localhost"
MPDPORT = "6600"
MPDPASS = False
music_library = os.path.expanduser("~/Music")
cover_formats = ["cover.jpg", "folder.jpg", "folder.png", "folder.jpeg", "cover.jpeg", "cover.png"]

# Song list file
song_list_path = os.path.expanduser("~/Music/song_list.txt")

class Tracker:
    """Tracks song information and player status changes from MPD"""
    
    def __init__(self):
        self.client = MPDClient()
        self.client.connect(MPDHOST, MPDPORT)
        if MPDPASS:
            self.client.password(MPDPASS)
        self.current_song = None
        self.last_song = None
        self.last_album = None
        self.last_queue_length = 0

    
    def checkSongUpdate(self):
        """Checks for new songs, reconnects if necessary"""
        status = self.client.status()
        if status["state"] == "stop":
            return 3  # Player stopped
        queue_length = int(status.get("playlistlength", 0))
        queue_updated = queue_length != self.last_queue_length
        self.last_queue_length = queue_length
        self.current_song = self.client.currentsong()
        return 0 if self.current_song else 2  # 0 = Song playing, 2 = No song



class Fetcher:
    """Fetches album art from MPD or file metadata"""

    def mutagen_fetcher(self, song_path):
        """Uses mutagen to extract embedded album art"""
        try:
            id3 = mutagen.id3.ID3(song_path)
            return id3.getall('APIC')[0].data  # MP3 embedded album art
        except mutagen.id3.ID3NoHeaderError:
            try:
                flac = mutagen.flac.FLAC(song_path)
                return flac.pictures[0].data  # FLAC embedded album art
            except mutagen.flac.FLACNoHeaderError:
                try:
                    mp4 = mutagen.mp4.MP4(song_path)
                    return mp4['covr'][0]  # MP4 embedded album art
                except:
                    print("Mutagen failed to fetch album art")
                    return None

    def getAlbumArt(self, song_file, mpd_client):
        """Fetch album art from folder, embedded metadata, or MPD."""
        img = Image.open(placeholder_loc)
        img.thumbnail((500, 500))
        img.save(album_art_loc, "PNG")

        album_directory = os.path.dirname(song_file)
        album_dir_list = mpd_client.listfiles(album_directory)

        cover_file = next((item['file'] for item in album_dir_list if 'file' in item and item['file'] in cover_formats), None)
        
        if cover_file:
            albumart_data = os.path.join(music_library, album_directory, cover_file)
            img_source = "file"
        else:
            albumart_data = self.mutagen_fetcher(os.path.join(music_library, song_file))
            img_source = "embedded"

        if not albumart_data:
            try:
                albumart_data = mpd_client.readpicture(song_file)
                img_source = "mpd"
            except:
                return

        try:
            if img_source == "file":
                img = Image.open(albumart_data)
            else:
                f = io.BytesIO(albumart_data)
                img = Image.open(f)

            img.thumbnail((500, 500))
            img.save(album_art_loc, "PNG")
        except:
            pass


# Initialize MPD tracker and fetcher
tracker = Tracker()
fetcher = Fetcher()

class AlbumArtApp(Gtk.Application):
    def __init__(self):
        super().__init__()
        self.input_buffer = ""  # Stores typed digits

        # Initialize I2C interface for the 7-segment displays
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
        except Exception as e:
            print(f"Error setting up I2C interface: {e}")
            sys.exit(1)

        # Create and initialize the 7-segment displays
        try:
            self.display_queue = adafruit_ht16k33.segments.Seg7x4(i2c, address=0x71)  # MPD Queue Length
            self.display_queue.fill(0)  

            self.display_input = adafruit_ht16k33.segments.Seg7x4(i2c, address=0x70)  # User Input
            self.display_input.fill(0)
        except Exception as e:
            print(f"Error setting up 7-segment displays: {e}")
            sys.exit(1)

    def do_activate(self):
        """Initialize the GTK Window"""
        window = Gtk.ApplicationWindow(application=self)
        window.set_title("MPD Album Art Viewer")
        window.set_default_size(500, 500)

        # Image widget for album art
        self.image = Gtk.Picture()
        window.set_child(self.image)  # GTK 4 replaces `add()` with `set_child()`
        
       # Create key event controller
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_press)
        window.add_controller(key_controller)  # Attach to window


        # Start MPD monitoring in a thread
        self.tracker_thread = threading.Thread(target=self.mpd_loop, daemon=True)
        self.tracker_thread.start()

        # Show window
        window.present()
        self.update_album_art()

    def update_album_art(self):
        """Load and display album art, forcing GTK cache refresh."""
        try:
            if os.path.exists(album_art_loc):
                file_size = os.path.getsize(album_art_loc)
                if file_size > 0:  # Ensure it's not an empty file
                    try:
                        texture = Gdk.Texture.new_from_filename(album_art_loc)
                        self.image.set_paintable(texture)
                        print(f"Album art loaded from: {album_art_loc} (Size: {file_size} bytes)") # Debugging
                        return  # Success, exit the function
                    except Exception as e:
                        print(f"Gdk.Texture error: {e}") # More specific error message
                else:
                    print(f"Album art file is empty: {album_art_loc}")
            else:
                print(f"Album art file does not exist: {album_art_loc}")

        except Exception as e: # Catch file existence and size check errors
            print(f"Error checking album art file: {e}")

        # Force update with placeholder if album art failed to load
        try:
            fallback_texture = Gdk.Texture.new_from_filename(placeholder_loc)
            self.image.set_paintable(fallback_texture)
            print(f"[DEBUG] Using fallback image: {placeholder_loc}")
        except Exception as e:
            print(f"Error loading fallback image: {e}")

    def mpd_loop(self):
        """Monitors MPD for song and queue changes, ensuring album art and queue display updates."""
        while True:
            try:
                song_state = tracker.checkSongUpdate()
                if song_state == 0:
                    try:
                        fetcher.getAlbumArt(tracker.current_song["file"], tracker.client)
                        GLib.idle_add(self.update_album_art)
                    except Exception as e: # Catch exceptions during fetch
                        print(f"Error fetching album art: {e}")
                # Always update queue display when the queue changes
                if tracker.checkSongUpdate() == 0:
                    GLib.idle_add(self.update_queue_display)
                tracker.client.idle("player")
            except Exception as e: # Catch exceptions in the loop itself
                print(f"Error in mpd_loop: {e}")
                time.sleep(1) # Prevent tight loop if MPD connection fails


    def update_queue_display(self):
        """Updates the 7-segment display with the MPD queue length"""
        print(f"[DEBUG] Updating queue display: {tracker.last_queue_length}")  # Log queue update
        self.display_queue.fill(0)
        self.display_queue.print(str(tracker.last_queue_length).rjust(4))  


    def on_key_press(self, controller, keyval, keycode, state):
        """Handles user key presses for song selection"""
        keychar = chr(keyval) if 48 <= keyval <= 57 else None  # 48-57 are ASCII for 0-9

        if keychar:  # If the key pressed is a digit
            self.input_buffer = (self.input_buffer + keychar)[-4:]  # Keep last 4 digits
            print(f"Input: {self.input_buffer}")
            self.display_input.fill(0)
            self.display_input.print(self.input_buffer.rjust(4))


            if len(self.input_buffer) == 4:  # When 4 digits are entered
                try:
                    line_number = int(self.input_buffer) # Ensure it's a valid integer
                    self.input_buffer = ""  # Reset input
                    self.add_song_to_mpd(line_number)
                except ValueError:
                    print("Invalid input: Could not convert to an integer")
                    self.input_buffer = ""  # Reset on error


    def add_song_to_mpd(self, line_number):
        """Fetch song from list and add to MPD queue"""
        if not os.path.exists(song_list_path):
            print(f"Error: File '{song_list_path}' does not exist.")
            return

        try:
            with open(song_list_path, 'r') as file:
                lines = file.readlines()

            if line_number < 1 or line_number > len(lines):
                print(f"Error: Invalid song number {line_number}.")
                return

            song_path = lines[line_number - 1].strip()
            print(f"Adding song: {song_path}")
            
            # Check if MPD is running before adding a song
            result = subprocess.run(["mpc", "status"], capture_output=True, text=True)
            if "MPD is not running" in result.stderr:
                print("Error: MPD is not running. Start MPD and try again.")
                return

            result = subprocess.run(["mpc", "add", song_path], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Error adding song: {result.stderr}")
                return

            # Immediately update queue length after adding a song
            tracker.last_queue_length += 1
            GLib.idle_add(self.update_queue_display)  # Ensure queue display updates immediately

            subprocess.run(["mpc", "play"], capture_output=True, text=True)

        except Exception as e:
            print(f"Error processing file: {e}")


# Run GTK App
if __name__ == "__main__":
    app = AlbumArtApp()
    app.run(None)
