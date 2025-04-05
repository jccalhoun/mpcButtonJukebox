import os
import yaml
import logging
import sys
from typing import Dict, Any, List, Tuple, Optional

# Type alias for configuration dictionary
ConfigDict = Dict[str, Any]

def expand_paths(config: ConfigDict) -> ConfigDict:
    """Expand all path values that contain tilde (~)"""
    for section in ['file_paths']:
        if section in config:
            for key, path in config[section].items():
                if isinstance(path, str) and '~' in path:
                    config[section][key] = os.path.expanduser(path)
    return config

def load_config(config_path: str = 'config.yaml') -> ConfigDict:
    """
    Load configuration from YAML file and process it
    
    Args:
        config_path: Path to the YAML configuration file
        
    Returns:
        Loaded and processed configuration dictionary
        
    Raises:
        FileNotFoundError: If configuration file doesn't exist
        yaml.YAMLError: If YAML parsing fails
        ValueError: If configuration structure is invalid
    """
    try:
        import yaml
    except ImportError:
        print("PyYAML library not found. Please install it with: pip install pyyaml")
        sys.exit(1)
    
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        
        # Expand paths with tildes
        config = expand_paths(config)
        
        # Validate the structure of the config
        _validate_config_structure(config)
        
        return config
    except FileNotFoundError:
        print(f"Configuration file not found: {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML configuration: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error loading configuration: {e}")
        sys.exit(1)

def _validate_config_structure(config: ConfigDict) -> bool:
    """
    Ensure the configuration has all required sections and settings.
    
    Args:
        config: Configuration dictionary to validate
        
    Returns:
        True if validation passes
        
    Raises:
        ValueError: If any required section or setting is missing
    """
    required_sections: List[str] = ['file_paths', 'mpd', 'logging', 'display']
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required configuration section: {section}")
    
    # Check for required file paths
    required_paths: List[str] = ['album_art_loc', 'placeholder_loc', 'music_library', 'log_file']
    for path in required_paths:
        if path not in config['file_paths']:
            raise ValueError(f"Missing required file path configuration: {path}")
    
    # Check for required MPD settings
    required_mpd: List[str] = ['host', 'port']
    for setting in required_mpd:
        if setting not in config['mpd']:
            raise ValueError(f"Missing required MPD configuration: {setting}")
    
    # Check for required logging settings
    required_logging: List[str] = ['level', 'format']
    for setting in required_logging:
        if setting not in config['logging']:
            raise ValueError(f"Missing required logging configuration: {setting}")
    
    return True

def validate_paths(config: ConfigDict) -> bool:
    """
    Validate that configured paths exist and are accessible, creating directories if needed.
    
    Args:
        config: Configuration dictionary with paths to validate
        
    Returns:
        True if all paths are valid or were successfully created
        
    Raises:
        FileNotFoundError: If a required path doesn't exist and can't be created
        PermissionError: If permissions are insufficient for a path
    """
    logger = logging.getLogger(__name__)
    
    # Paths that must exist - we'll check these
    paths_to_check: List[Tuple[str, str]] = [
        (config['file_paths']['music_library'], "Music library"),
        (os.path.dirname(config['file_paths']['log_file']), "Log file directory")
    ]
    
    # Ensure these directories exist
    dirs_to_ensure: List[Tuple[str, str]] = [
        (os.path.dirname(config['file_paths']['album_art_loc']), "Album art directory"),
        (os.path.dirname(config['file_paths']['placeholder_loc']), "Placeholder image directory")
    ]
    
    for path, description in paths_to_check:
        if not os.path.exists(path):
            logger.error(f"{description} path does not exist: {path}")
            raise FileNotFoundError(f"{description} path not found: {path}")
        if not os.access(path, os.R_OK):
            logger.error(f"Insufficient permissions for {description} path: {path}")
            raise PermissionError(f"Cannot access {description} path: {path}")
    
    # Create directories if they don't exist
    for dir_path, description in dirs_to_ensure:
        if not os.path.exists(dir_path):
            try:
                logger.info(f"Creating {description} path: {dir_path}")
                os.makedirs(dir_path, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to create {description} path: {dir_path}", exc_info=True)
                raise PermissionError(f"Cannot create {description} path: {dir_path}: {str(e)}")
    
    logger.debug("Configuration paths validated successfully")
    return True

def setup_logging(config: ConfigDict) -> None:
    """
    Set up logging based on configuration with log rotation
    
    Args:
        config: Configuration dictionary containing logging settings
    """
    import logging
    from logging.handlers import RotatingFileHandler
    
    log_level: int = getattr(logging, config['logging']['level'])
    log_format: str = config['logging']['format']
    log_file: str = config['file_paths']['log_file']
    
    # Get rotation settings from config or use defaults
    max_bytes: int = config['logging'].get('max_bytes', 5 * 1024 * 1024)  # Default: 5MB
    backup_count: int = config['logging'].get('backup_count', 3)  # Default: 3 backup files
    
    # Ensure log directory exists
    log_dir: str = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Configure the root logger
    root_logger: logging.Logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove any existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create rotating file handler
    handler: RotatingFileHandler = RotatingFileHandler(
        filename=log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    
    # Set formatter
    formatter: logging.Formatter = logging.Formatter(log_format)
    handler.setFormatter(formatter)
    
    # Add handler to root logger
    root_logger.addHandler(handler)
    
    # Log that logging has been set up
    logging.info(f"Logging initialized with rotation (max_bytes={max_bytes}, backup_count={backup_count})")

def finalize_config(config: ConfigDict) -> ConfigDict:
    """
    Ensure that all required directories exist and prepare any necessary files.
    
    Args:
        config: Configuration dictionary to finalize
        
    Returns:
        Finalized configuration dictionary
    """
    logger = logging.getLogger(__name__)
    logger.info("Finalizing configuration and preparing environment")
    
    # Validate paths first
    validate_paths(config)
    
    # Create any empty files that need to exist
    placeholder_list_file: Optional[str] = config['file_paths'].get('song_list_path')
    if placeholder_list_file and not os.path.exists(placeholder_list_file):
        try:
            logger.debug(f"Creating empty song list file: {placeholder_list_file}")
            with open(placeholder_list_file, 'w') as f:
                f.write("# Song list file - will be populated by the application\n")
        except Exception as e:
            logger.warning(f"Failed to create song list file: {str(e)}")
            # Non-critical error, so just log and continue
    
    # Check if MPD password is set to "false" as a string and convert to Python False
    if config['mpd'].get('password') == "false":
        config['mpd']['password'] = False
    
    return config