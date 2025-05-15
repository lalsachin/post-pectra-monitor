import logging
import time
from datetime import datetime
from .beacon_api import BeaconAPI
from .db import Database
from .shared_cache import SharedCache

logger = logging.getLogger(__name__)

class VoluntaryExitMonitor:
    def __init__(self, shared_cache):
        """Initialize the voluntary exit monitor"""
        self.beacon_api = BeaconAPI()
        self.db = Database()
        self.shared_cache = shared_cache
        self.last_processed_slot = 0

    def get_voluntary_exits(self, slot):
        """Get voluntary exits from a block"""
        try:
            block = self.beacon_api.get_block(slot)
            if not block or 'data' not in block:
                return None
            
            # Check if block has voluntary exits
            if 'message' in block['data'] and 'body' in block['data']['message']:
                body = block['data']['message']['body']
                if 'voluntary_exits' in body:
                    return body['voluntary_exits']
            return []
        except Exception as e:
            logger.error(f"Error getting voluntary exits: {str(e)}")
            return None

    def get_validator_info(self, validator_index):
        """Get validator info from head state"""
        try:
            response = self.beacon_api.get_validators(validator_index)
            if response and 'data' in response:
                for validator in response['data']:
                    if validator['index'] == str(validator_index):
                        return validator
            return None
        except Exception as e:
            logger.error(f"Error getting validator info: {str(e)}")
            return None

    def run_voluntary_exit_monitor_loop(self):
        """Main monitoring loop"""
        while True:
            try:
                # Get current slot and epoch from shared cache
                current_slot = self.shared_cache.get('current_slot')
                current_epoch = self.shared_cache.get('current_epoch')
                
                if not current_slot or not current_epoch:
                    logger.warning("Current slot/epoch not available in shared cache")
                    time.sleep(12)
                    continue
                
                logger.info(f"Current Slot: {current_slot}")
                logger.info(f"Current Epoch: {current_epoch}")
                
                # Only process if we haven't processed this slot yet
                if current_slot > self.last_processed_slot:
                    logger.info(f"Processing slot {current_slot}")
                    
                    # Get voluntary exits
                    voluntary_exits = self.get_voluntary_exits(current_slot)
                    
                    if voluntary_exits is not None:
                        # Save to database
                        for exit_data in voluntary_exits:
                            validator_index = exit_data['message']['validator_index']
                            
                            # Get validator info from head state
                            validator_info = self.get_validator_info(validator_index)
                            
                            if validator_info:
                                self.db.save_voluntary_exit(
                                    validator_index=validator_index,
                                    exit_epoch=validator_info['validator']['exit_epoch'],
                                    withdrawable_epoch=validator_info['validator']['withdrawable_epoch'],
                                    balance=validator_info['balance'],
                                    effective_balance=validator_info['validator']['effective_balance'],
                                    pubkey=validator_info['validator']['pubkey'],
                                    signature=exit_data['signature'],
                                    slot=current_slot,
                                    epoch=current_epoch
                                )
                                logger.info(f"Saved voluntary exit for validator {validator_index}")
                            else:
                                logger.error(f"Could not get validator info for {validator_index}")
                        
                        logger.info(f"Slot {current_slot} stats:")
                        logger.info(f"  Number of voluntary exits: {len(voluntary_exits)}")
                    else:
                        logger.error("Failed to get voluntary exits")
                    
                    self.last_processed_slot = current_slot
                
                # Get counts from database
                voluntary_exits_count = self.db.get_voluntary_exits_count()
                partial_withdrawals_count = self.db.get_partial_withdrawals_count()
                
                logger.info(f"Number of voluntary exits: {voluntary_exits_count}")
                logger.info(f"Number of partial withdrawals: {partial_withdrawals_count}")
                
                time.sleep(12)  # Check every 12 seconds
                
            except Exception as e:
                logger.error(f"Error in voluntary exit monitor loop: {str(e)}")
                time.sleep(12)  # Wait before retrying 