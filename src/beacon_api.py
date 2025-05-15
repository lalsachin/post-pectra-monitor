import requests
import logging
import time
from datetime import datetime
import os
from dotenv import load_dotenv
from ratelimit import limits, sleep_and_retry

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Rate limiting: 15 requests per second
CALLS = 15
RATE_LIMIT_PERIOD = 1

@sleep_and_retry
@limits(calls=CALLS, period=RATE_LIMIT_PERIOD)
def rate_limited_request(url, headers=None, params=None):
    """Make a rate-limited request"""
    return requests.get(url, headers=headers, params=params)

class BeaconAPI:
    def __init__(self):
        """Initialize the Beacon API client"""
        self.base_url = os.getenv('BEACON_API_URL')
        if not self.base_url:
            raise ValueError("BEACON_API_URL environment variable is not set")
        
        self.headers = {
            'accept': 'application/json'
        }
    
    def get_validator_info(self, validator_index):
        """Get validator information"""
        try:
            url = f"{self.base_url}/eth/v1/beacon/states/head/validators/{validator_index}"
            response = rate_limited_request(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting validator info: {str(e)}")
            raise
    
    def get_validators(self, validator_indices):
        """Get information for multiple validators"""
        try:
            # Convert list to comma-separated string
            indices_str = ','.join(map(str, validator_indices))
            url = f"{self.base_url}/eth/v1/beacon/states/head/validators/{indices_str}"
            response = rate_limited_request(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting validators: {str(e)}")
            raise
    
    def get_block(self, slot):
        """Get block information for a specific slot"""
        try:
            url = f"{self.base_url}/eth/v2/beacon/blocks/{slot}"
            response = rate_limited_request(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting block: {str(e)}")
            raise
    
    def get_genesis(self):
        """Get genesis information"""
        try:
            url = f"{self.base_url}/eth/v1/beacon/genesis"
            response = rate_limited_request(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting genesis: {str(e)}")
            raise
    
    def get_finality_checkpoints(self):
        """Get finality checkpoints"""
        try:
            url = f"{self.base_url}/eth/v1/beacon/states/head/finality_checkpoints"
            response = rate_limited_request(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting finality checkpoints: {str(e)}")
            raise
    
    def get_validator_balances(self, validator_indices):
        """Get validator balances"""
        try:
            # Convert list to comma-separated string
            indices_str = ','.join(map(str, validator_indices))
            url = f"{self.base_url}/eth/v1/beacon/states/head/validator_balances/{indices_str}"
            response = rate_limited_request(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting validator balances: {str(e)}")
            raise 