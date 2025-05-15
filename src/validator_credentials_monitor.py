import requests
import time
import logging
from datetime import datetime
from db import Database
from shared_cache import shared_cache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
BEACON_API_V1 = "https://blue-stylish-crater.quiknode.pro/085cffcf2d858f52954961e2cba92a8a3572623d/eth/v1/beacon"
BEACON_API_V2 = "https://blue-stylish-crater.quiknode.pro/085cffcf2d858f52954961e2cba92a8a3572623d/eth/v2/beacon"
SLOTS_PER_EPOCH = 32
SECONDS_PER_SLOT = 12

class ValidatorCredentialsMonitor:
    def __init__(self):
        self.db = Database()
        self.last_processed_epoch = self._get_last_processed_epoch()
    
    def _get_last_processed_epoch(self):
        """Get the last processed epoch from the database"""
        try:
            with self.db.conn.cursor() as cur:
                cur.execute("SELECT MAX(epoch) FROM validator_withdrawal_credentials")
                result = cur.fetchone()
                return result[0] if result[0] is not None else -1
        except Exception as e:
            logger.error(f"Error getting last processed epoch: {str(e)}")
            return -1
    
    def get_current_epoch(self):
        """Get the current epoch"""
        try:
            url = f"{BEACON_API_V2}/blocks/head"
            headers = {'accept': 'application/json'}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data and 'message' in data['data'] and 'slot' in data['data']['message']:
                current_slot = int(data['data']['message']['slot'])
                return current_slot // SLOTS_PER_EPOCH
            else:
                logger.error(f"Unexpected response format: {data}")
                return None
        except Exception as e:
            logger.error(f"Error getting current epoch: {str(e)}")
            return None

    def get_current_slot(self):
        """Get the current slot"""
        try:
            url = f"{BEACON_API_V2}/blocks/head"
            headers = {'accept': 'application/json'}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data and 'message' in data['data'] and 'slot' in data['data']['message']:
                return int(data['data']['message']['slot'])
            else:
                logger.error(f"Unexpected response format: {data}")
                return None
        except Exception as e:
            logger.error(f"Error getting current slot: {str(e)}")
            return None
    
    def get_validator_credentials(self):
        """Get all active validators and count their withdrawal credentials"""
        try:
            url = f"{BEACON_API_V1}/states/head/validators?status=active_ongoing"
            headers = {'accept': 'application/json'}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if 'data' not in data:
                logger.error(f"Unexpected response format: {data}")
                return None, None
                
            validators = data['data']
            num_0x01 = 0
            num_0x02 = 0
            
            for validator in validators:
                if 'validator' in validator and 'withdrawal_credentials' in validator['validator']:
                    withdrawal_credentials = validator['validator']['withdrawal_credentials']
                    if withdrawal_credentials.startswith('0x01'):
                        num_0x01 += 1
                    elif withdrawal_credentials.startswith('0x02'):
                        num_0x02 += 1
            
            return num_0x01, num_0x02
        except Exception as e:
            logger.error(f"Error getting validator credentials: {str(e)}")
            return None, None
    
    def save_validator_credentials(self, epoch, slot, num_0x01, num_0x02):
        """Save validator credentials data to database"""
        try:
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO validator_withdrawal_credentials 
                    (epoch, slot, timestamp, num_0x01_validators, num_0x02_validators)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (epoch) DO NOTHING
                """, (
                    epoch,
                    slot,
                    datetime.utcnow(),
                    num_0x01,
                    num_0x02
                ))
                self.db.conn.commit()
        except Exception as e:
            logger.error(f"Error saving validator credentials: {str(e)}")
            raise
    
    def monitor_credentials(self):
        """Monitor validator credentials at the start of each epoch"""
        try:
            while True:
                current_epoch = self.get_current_epoch()
                
                if current_epoch is None:
                    logger.error("Failed to get current epoch")
                    time.sleep(12)
                    continue
                
                if current_epoch > self.last_processed_epoch:
                    logger.info(f"Processing epoch {current_epoch}")
                    
                    # Get current slot
                    current_slot = current_epoch * SLOTS_PER_EPOCH
                    
                    # Only collect validator credentials data on even epochs
                    if current_epoch % 2 == 0:
                        # Get validator credentials
                        num_0x01, num_0x02 = self.get_validator_credentials()
                        
                        if num_0x01 is not None and num_0x02 is not None:
                            # Save to database
                            self.save_validator_credentials(current_epoch, current_slot, num_0x01, num_0x02)
                            
                            logger.info(f"Epoch {current_epoch} stats:")
                            logger.info(f"  0x01 validators: {num_0x01}")
                            logger.info(f"  0x02 validators: {num_0x02}")
                    else:
                        logger.info(f"Skipping validator credentials collection for odd epoch {current_epoch}")
                    
                    self.last_processed_epoch = current_epoch
                
                # Sleep until next epoch
                time.sleep(SECONDS_PER_SLOT)
        except Exception as e:
            logger.error(f"Error in monitor loop: {str(e)}")
            raise

def run_validator_credentials_monitor():
    """Run the validator credentials monitor continuously, checking on even epochs"""
    try:
        monitor = ValidatorCredentialsMonitor()
        last_processed_epoch = monitor.last_processed_epoch
        
        while True:
            # Try to get from cache first
            current_epoch, current_slot = shared_cache.get_current_epoch_and_slot()
            
            # If cache is empty or expired, get fresh data
            if current_epoch is None or current_slot is None:
                current_epoch = monitor.get_current_epoch()
                current_slot = monitor.get_current_slot()
                
                if current_epoch is None or current_slot is None:
                    logger.error("Failed to get current epoch/slot")
                    time.sleep(384)  # Wait an epoch before retrying
                    continue
                
                # Update the cache
                shared_cache.update_epoch_and_slot(current_epoch, current_slot)
            
            # Only process if we haven't processed this epoch yet
            if current_epoch > last_processed_epoch:
                # Only collect data on even epochs
                if current_epoch % 2 == 0:
                    logger.info(f"Processing epoch {current_epoch}")
                    
                    # Get validator credentials
                    num_0x01, num_0x02 = monitor.get_validator_credentials()
                    
                    if num_0x01 is not None and num_0x02 is not None:
                        # Save to database
                        monitor.save_validator_credentials(current_epoch, current_slot, num_0x01, num_0x02)
                        
                        logger.info(f"Epoch {current_epoch} stats:")
                        logger.info(f"  0x01 validators: {num_0x01}")
                        logger.info(f"  0x02 validators: {num_0x02}")
                        
                        # Sleep for 2 epochs since we only need to check on even epochs
                        time.sleep(768)  # 2 epochs (2 * 32 slots * 12 seconds)
                    else:
                        logger.error("Failed to get validator credentials")
                        time.sleep(384)  # Wait an epoch before retrying
                else:
                    logger.info(f"Skipping validator credentials collection for odd epoch {current_epoch}")
                    time.sleep(384)  # Wait an epoch before checking again
                
                last_processed_epoch = current_epoch
            else:
                # If we've already processed this epoch, wait an epoch before checking again
                time.sleep(384)
            
    except Exception as e:
        logger.error(f"Error in validator credentials monitor loop: {str(e)}")
        raise
    finally:
        # Close database connection
        if hasattr(monitor, 'db'):
            monitor.db.close()

if __name__ == "__main__":
    run_validator_credentials_monitor() 