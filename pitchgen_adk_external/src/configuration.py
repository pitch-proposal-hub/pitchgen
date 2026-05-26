"""
This program provides functionality to read configuration from a configuration file.

The configuration file is expected to be in INI format and located at 'config/config.ini'.
"""


from configparser import ConfigParser
import os
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../.env')
load_dotenv(dotenv_path=env_path)

def configuration():
    """
    Reads and returns the configuration from 'config/config.ini'.
    
    Raises:
        FileNotFoundError: If the configuration file does not exist.
        ValueError: If the configuration file is empty or has no sections.
    
    Returns:
        ConfigParser: The configuration parser object with the read configuration.
    """
    config = ConfigParser()
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../config/config.ini')
    config.read(config_path)
    config.sections()
    
    env_model = os.getenv('MODEL')
    if env_model:
        if 'default' not in config:
            config.add_section('default')
        config.set('default', 'gemini_model', env_model)
        config.set('default', 'gemini_model_1', env_model)
        
    env_image_model = os.getenv('IMAGE_MODEL')
    if env_image_model:
        if 'default' not in config:
            config.add_section('default')
        config.set('default', 'gemini_model_2', env_image_model)
        
    return config
