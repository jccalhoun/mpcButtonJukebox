# Raspberry Pi Jukebox

A specialized application for transforming a traditional jukebox into a modern digital music player using a Raspberry Pi 5. This application displays album art and song information from an MPD (Music Player Daemon) music collection while maintaining the classic jukebox experience through numeric input.

![Pi Jukebox Screenshot](screenshot.png)

## 🎵 Features

- **Traditional Jukebox Experience**: Input numbers 0-9 to select songs from a song list, simulating the classic jukebox song selection experience
- **Real-time MPD Integration**: Connects to your MPD server to display currently playing tracks and manage your music queue
- **Album Art Display**: Shows album art extracted from music files using multiple methods:
  - Embedded ID3/FLAC/MP4 artwork
  - MPD's native readpicture command
  - Common cover image files in music directories
- **Dynamic Background**: Creates gradient backgrounds by extracting colors from album art edges
- **Hardware Integration**: Supports 7-segment LED displays via I2C connection for:
  - Queue length display
  - Input number feedback
- **Special Commands**: Quick control commands via numeric input:
  - `9999` → Skip current song
  - `8888` → Stop playback
  - `7777` → Start playback
  - `6666` → Clear queue
- **On-screen Notifications**: Visual feedback for all actions including queue additions and command execution
- **Comprehensive Logging**: Detailed logging with rotation for debugging and monitoring

## 🖥️ Requirements

- Raspberry Pi 5 running Raspberry Pi OS
- Python 3.7+
- MPD server
- GTK 4.0
- Adafruit HT16K33 LED segments (for hardware display)
- I2C connection (for 7-segment displays)
- Numeric keypad or buttons (0-9)

## 🛠️ Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/pi-jukebox.git
cd pi-jukebox

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

## ⚙️ Configuration

The application is configured through a `config.yaml` file in the root directory. Key configuration options include:

```yaml
# File and path settings
file_paths:
  album_art_loc: ~/path/to/album_art.png
  placeholder_loc: ~/path/to/placeholder.png
  music_library: ~/Music
  song_list_path: ~/Music/song_list.txt
  log_file: ~/album_art.log

# MPD connection settings
mpd:
  host: localhost
  port: 6600
  password: false  # Set to your password if needed

# Display options
display:
  placeholder_image_size: [500, 500]
  placeholder_image_color: [0, 0, 0]
  song_info_display_duration: 10
  queue_notification_duration: 5
```

## 🎮 Usage

### Song List Setup

1. Create a song list file (default: `~/Music/song_list.txt`) with one song path per line
2. You can automatically generate this list with the following command from your music directory:
   ```bash
   find . \( -name "*.mp3" -o -name "*.m4a" -o -name "*.lame" \) -type f | sed 's/^..//'> song_list.txt
   ```
   This finds all MP3, M4A, and LAME files, removes the leading `./` from paths, and writes them to song_list.txt
3. Each song will be assigned a line number, which users can enter to select it

### Jukebox Operation

1. Start your MPD server
2. Run the application: `python main.py`
3. Enter a song number using the numeric keypad (e.g., `0042`)
4. The song will be added to the MPD queue
5. The current playing song's album art and information will be displayed

### Special Commands

- `9999` - Skip to the next song
- `8888` - Stop playback
- `7777` - Start playback
- `6666` - Clear the queue

### Hardware Integration

For the Raspberry Pi jukebox setup:
- Connect I2C 7-segment displays to show queue length and input
- LED at address `0x70` shows input numbers
- LED at address `0x71` shows current queue length

## 🏗️ Project Structure

- `main.py` - Entry point for the application
- `album_art/` - Core application modules
  - `mpd_client.py` - MPD interaction and tracking
  - `fetcher.py` - Album art extraction logic
  - `gtk_app.py` - GTK user interface
  - `config_loader.py` - Configuration management
  - `utils.py` - Utility functions
  - `exceptions.py` - Custom exception classes

## 🧩 Extending the Application

The application is designed with modularity in mind. Key extension points:

- Add new album art sources in `fetcher.py`
- Extend hardware support in `mpd_client.py`
- Modify UI elements in `gtk_app.py`

## 📝 Setting Up as a Service

To run the jukebox application automatically at startup on Raspberry Pi OS:

```bash
# Create a systemd service file
sudo nano /etc/systemd/system/jukebox.service

# Add the following content:
[Unit]
Description=Raspberry Pi Jukebox
After=network.target mpd.service

[Service]
ExecStart=/usr/bin/python3 /path/to/main.py
WorkingDirectory=/path/to/pi-jukebox
StandardOutput=inherit
StandardError=inherit
Restart=always
User=pi

[Install]
WantedBy=multi-user.target

# Enable and start the service
sudo systemctl enable jukebox.service
sudo systemctl start jukebox.service
```

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

Contributions welcome! Please feel free to submit a Pull Request.

---

Convert your classic jukebox into a modern digital music player while preserving the nostalgic numeric selection experience.
