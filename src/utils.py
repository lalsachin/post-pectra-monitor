import requests
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

def make_api_request(url, params=None):
    """
    Make an API request with error handling
    """
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        raise

def format_timestamp(timestamp):
    """
    Format timestamp to human-readable format
    """
    try:
        dt = datetime.fromisoformat(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logger.error(f"Error formatting timestamp: {str(e)}")
        return timestamp

def load_config(config_file='config.json'):
    """
    Load configuration from JSON file
    """
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Config file {config_file} not found, using defaults")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing config file: {str(e)}")
        raise

def validate_ethereum_address(address):
    """
    Validate Ethereum address format
    """
    try:
        if not address.startswith('0x'):
            return False
        if len(address) != 42:
            return False
        int(address, 16)
        return True
    except ValueError:
        return False 