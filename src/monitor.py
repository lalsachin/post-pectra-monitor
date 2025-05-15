from web3 import Web3
import logging
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv
import requests
from db import Database
import time

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
QUICKNODE_URL = os.getenv('QUICKNODE_URL')
if not QUICKNODE_URL:
    raise ValueError("QUICKNODE_URL not found in environment variables")

# QuickNode Beacon API endpoints
BEACON_API_BASE = "https://blue-stylish-crater.quiknode.pro/085cffcf2d858f52954961e2cba92a8a3572623d/eth"
BEACON_API_V1 = f"{BEACON_API_BASE}/v1/beacon"
BEACON_API_V2 = f"{BEACON_API_BASE}/v2/beacon"

class ValidatorExitMonitor:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(QUICKNODE_URL))
        if not self.w3.is_connected():
            raise ConnectionError("Failed to connect to Ethereum node")
        
        logger.info("Connected to Ethereum node successfully")
        
        # Initialize database connection
        self.db = Database()
        
        # Constants
        self.EXIT_DELAY = 256  # epochs between exit_epoch and withdrawable_epoch
        self.SLOTS_PER_EPOCH = 32  # Each epoch consists of 32 slots
        
        # Contract configuration
        self.contract_address = "0x00000961Ef480Eb55e80D19ad83579A64c007002"
        self.contract_abi = [
            {
                "anonymous": False,
                "inputs": [
                    {"indexed": True, "name": "validator", "type": "address"},
                    {"indexed": True, "name": "recipient", "type": "address"},
                    {"indexed": False, "name": "amount", "type": "uint256"},
                    {"indexed": False, "name": "fee", "type": "uint256"}
                ],
                "name": "PartialWithdrawalRequested",
                "type": "event"
            }
        ]
        self.contract = self.w3.eth.contract(address=self.contract_address, abi=self.contract_abi)
        
        # Tracking state
        self.known_exiting_validators = set()  # Track validators we've already seen
        self.previous_validator_states = {}  # Track previous validator states
        self.voluntary_exits_by_block = {}  # Track voluntary exits by block
        self.last_checked_block = self.w3.eth.block_number  # Track last checked block for partial withdrawals

    def __del__(self):
        """Cleanup when the monitor is destroyed"""
        if hasattr(self, 'db'):
            self.db.close()

    def get_current_slot(self):
        """
        Get the current slot number from the beacon chain
        """
        try:
            url = f"{BEACON_API_V2}/blocks/head"
            response = requests.get(url, headers={'accept': 'application/json'})
            response.raise_for_status()
            data = response.json()
            
            if data and 'data' in data and 'message' in data['data']:
                return int(data['data']['message']['slot'])
            raise ValueError("Could not get current slot from beacon chain")
        except Exception as e:
            logger.error(f"Error getting current slot: {str(e)}")
            raise

    def get_current_epoch(self):
        """
        Get the current epoch by calculating from the slot number
        """
        try:
            current_slot = self.get_current_slot()
            return current_slot // self.SLOTS_PER_EPOCH
        except Exception as e:
            logger.error(f"Error getting current epoch: {str(e)}")
            raise

    def get_block_by_slot(self, slot):
        """
        Get beacon block data for the latest block (head)
        """
        try:
            start_time = datetime.now()
            url = f"{BEACON_API_V2}/blocks/head"
            response = requests.get(url, headers={'accept': 'application/json'})
            response.raise_for_status()
            data = response.json()
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.info(f"Block data API call took {duration:.2f} seconds")
            return data
        except Exception as e:
            logger.error(f"Error getting block data for head: {str(e)}")
            return None

    def get_voluntary_exits_in_block(self, block_data):
        """
        Extract voluntary exits from block data
        """
        try:
            if not block_data or 'data' not in block_data:
                return []

            message = block_data['data']['message']
            if 'body' not in message or 'voluntary_exits' not in message['body']:
                return []

            voluntary_exits = []
            for exit_data in message['body']['voluntary_exits']:
                validator_index = int(exit_data['message']['validator_index'])
                
                # Get validator state using pubkey
                url = f"{BEACON_API_V1}/states/head/validators/{validator_index}"
                response = requests.get(url, headers={'accept': 'application/json'})
                response.raise_for_status()
                validator_data = response.json()
                
                if not validator_data or 'data' not in validator_data:
                    logger.warning(f"No data received for validator {validator_index}")
                    continue
                
                validator = validator_data['data']['validator']
                voluntary_exit = {
                    'validator_index': validator_index,
                    'exit_epoch': int(validator['exit_epoch']),
                    'withdrawable_epoch': int(validator['withdrawable_epoch']),
                    'balance': int(validator_data['data']['balance']),
                    'effective_balance': int(validator['effective_balance']),
                    'pubkey': validator['pubkey'],
                    'signature': exit_data['signature']
                }
                voluntary_exits.append(voluntary_exit)
                logger.info(f"Found voluntary exit request for validator {voluntary_exit['validator_index']} "
                          f"with exit_epoch {voluntary_exit['exit_epoch']} "
                          f"and withdrawable_epoch {voluntary_exit['withdrawable_epoch']}")

            return voluntary_exits
        except Exception as e:
            logger.error(f"Error extracting voluntary exits: {str(e)}")
            return []

    def get_validator_states(self):
        """
        Get current state of validators that have submitted voluntary exits
        """
        try:
            # Get all validators that have submitted voluntary exits
            validator_indices = list(self.voluntary_exits_by_block.keys())
            if not validator_indices:
                return {}

            # Query each validator individually to get their current status
            validator_states = {}
            for validator_index in validator_indices:
                url = f"{BEACON_API_V1}/states/head/validators/{validator_index}"
                response = requests.get(url, headers={'accept': 'application/json'})
                response.raise_for_status()
                data = response.json()
                
                if not data or 'data' not in data:
                    logger.warning(f"No data received for validator {validator_index}")
                    continue

                validator_data = data['data']
                validator = validator_data['validator']
                validator_states[validator_index] = {
                    'status': validator_data['status'],
                    'exit_epoch': int(validator['exit_epoch']),
                    'withdrawable_epoch': int(validator['withdrawable_epoch']),
                    'balance': int(validator_data['balance']),
                    'effective_balance': int(validator['effective_balance']),
                    'pubkey': validator['pubkey']
                }
            
            logger.info(f"Tracking {len(validator_states)} validators that previously submitted voluntary exits")
            return validator_states
        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to validators endpoint: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response text: {e.response.text}")
            return {}
        except Exception as e:
            logger.error(f"Error getting validator states: {str(e)}")
            return {}

    def verify_validator_status(self, validator_index):
        """
        Verify the status of a specific validator
        """
        try:
            url = f"{BEACON_API_V1}/states/head/validators/{validator_index}"
            response = requests.get(url, headers={'accept': 'application/json'})
            response.raise_for_status()
            data = response.json()
            
            if not data or 'data' not in data:
                logger.warning(f"No data received for validator {validator_index}")
                return None

            validator_data = data['data']
            validator = validator_data['validator']
            return {
                'status': validator_data['status'],
                'exit_epoch': int(validator['exit_epoch']),
                'withdrawable_epoch': int(validator['withdrawable_epoch']),
                'balance': int(validator_data['balance']),
                'effective_balance': int(validator['effective_balance']),
                'pubkey': validator['pubkey']
            }
        except Exception as e:
            logger.error(f"Error verifying validator {validator_index}: {str(e)}")
            return None

    def find_new_exiting_validators(self, current_states):
        """
        Find validators that have newly entered the exiting state
        """
        new_exiting = []
        
        # First check for validators that have changed status
        for validator_index, current_state in current_states.items():
            if validator_index in self.previous_validator_states:
                previous_state = self.previous_validator_states[validator_index]
                if (previous_state['status'] != 'active_exiting' and 
                    current_state['status'] == 'active_exiting'):
                    # Verify the status change
                    verified_state = self.verify_validator_status(validator_index)
                    if verified_state and verified_state['status'] == 'active_exiting':
                        new_exiting.append({
                            'validator_index': validator_index,
                            'status': 'active_exiting',
                            'previous_status': previous_state['status'],
                            'exit_epoch': verified_state['exit_epoch'],
                            'withdrawable_epoch': verified_state['withdrawable_epoch'],
                            'balance': verified_state['balance'],
                            'effective_balance': verified_state['effective_balance'],
                            'pubkey': verified_state['pubkey']
                        })
                        logger.info(f"Found new exiting validator {validator_index} "
                                  f"with exit_epoch {verified_state['exit_epoch']} "
                                  f"and withdrawable_epoch {verified_state['withdrawable_epoch']}")
                    else:
                        logger.warning(f"Status verification failed for validator {validator_index}")
        
        # Then check for validators that have submitted voluntary exits but haven't been recorded yet
        for validator_index in self.voluntary_exits_by_block:
            if validator_index in current_states and current_states[validator_index]['status'] == 'active_exiting':
                # Verify the status
                verified_state = self.verify_validator_status(validator_index)
                if verified_state and verified_state['status'] == 'active_exiting':
                    new_exiting.append({
                        'validator_index': validator_index,
                        'status': 'active_exiting',
                        'previous_status': 'unknown',
                        'exit_epoch': verified_state['exit_epoch'],
                        'withdrawable_epoch': verified_state['withdrawable_epoch'],
                        'balance': verified_state['balance'],
                        'effective_balance': verified_state['effective_balance'],
                        'pubkey': verified_state['pubkey']
                    })
                    logger.info(f"Found exiting validator {validator_index} from voluntary exit "
                              f"with exit_epoch {verified_state['exit_epoch']} "
                              f"and withdrawable_epoch {verified_state['withdrawable_epoch']}")
                else:
                    logger.warning(f"Status verification failed for validator {validator_index}")
        
        return new_exiting

    def get_partial_withdrawals(self):
        """Get partial withdrawal events since last check"""
        try:
            current_block = self.w3.eth.block_number
            if current_block <= self.last_checked_block:
                return []

            # Get logs for PartialWithdrawalRequested events
            event_signature = "PartialWithdrawalRequested(address,address,uint256,uint256)"
            event_sig_hash = Web3.keccak(text=event_signature).hex()
            
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_getLogs",
                "params": [
                    {
                        "fromBlock": hex(self.last_checked_block + 1),
                        "toBlock": hex(current_block),
                        "address": self.contract_address,
                        "topics": [event_sig_hash]
                    }
                ],
                "id": 1
            }
            
            response = requests.post(QUICKNODE_URL, headers={'Content-Type': 'application/json'}, json=payload)
            logs = response.json().get("result", [])
            
            # Update last checked block
            self.last_checked_block = current_block
            
            # Get current slot and epoch
            current_slot = self.get_current_slot()
            current_epoch = self.get_current_epoch()
            
            # Process logs
            withdrawals = []
            for log in logs:
                try:
                    decoded = self.contract.events.PartialWithdrawalRequested().processLog(log)
                    
                    # Get validator information from beacon chain
                    validator_address = decoded.args.validator
                    url = f"{BEACON_API_V1}/states/head/validators/{validator_address}"
                    response = requests.get(url, headers={'accept': 'application/json'})
                    response.raise_for_status()
                    validator_data = response.json()
                    
                    if not validator_data or 'data' not in validator_data:
                        logger.warning(f"No data received for validator {validator_address}")
                        continue
                    
                    validator = validator_data['data']['validator']
                    withdrawal = {
                        'validator_index': int(validator_data['data']['index']),
                        'exit_epoch': int(validator['exit_epoch']),
                        'balance': int(validator_data['data']['balance']),
                        'effective_balance': int(validator['effective_balance']),
                        'pubkey': validator['pubkey'],
                        'recipient_address': decoded.args.recipient,
                        'partial_withdrawal_amount': decoded.args.amount,
                        'request_fee_paid': decoded.args.fee,
                        'block_number': int(log['blockNumber'], 16),
                        'transaction_hash': log['transactionHash'],
                        'slot': current_slot,
                        'epoch': current_epoch
                    }
                    withdrawals.append(withdrawal)
                    
                    # Save to database
                    self.db.save_partial_withdrawal(withdrawal)
                    
                    logger.info(f"Found partial withdrawal request:")
                    logger.info(f"  Validator Index: {withdrawal['validator_index']}")
                    logger.info(f"  Exit Epoch: {withdrawal['exit_epoch']}")
                    logger.info(f"  Balance: {withdrawal['balance']}")
                    logger.info(f"  Effective Balance: {withdrawal['effective_balance']}")
                    logger.info(f"  Recipient: {withdrawal['recipient_address']}")
                    logger.info(f"  Amount: {withdrawal['partial_withdrawal_amount']} wei")
                    logger.info(f"  Fee: {withdrawal['request_fee_paid']} wei")
                    
                except Exception as e:
                    logger.error(f"Error decoding partial withdrawal log: {str(e)}")
                    continue
            
            return withdrawals
        except Exception as e:
            logger.error(f"Error getting partial withdrawals: {str(e)}")
            return []

    def monitor_queue(self, block_data):
        """
        Main monitoring function
        """
        try:
            # Get current slot and epoch from block data
            current_slot = int(block_data['data']['message']['slot'])
            current_epoch = current_slot // self.SLOTS_PER_EPOCH
            
            # 1. Get voluntary exits from latest block
            voluntary_exits = self.get_voluntary_exits_in_block(block_data)
            
            # 2. Get partial withdrawals
            partial_withdrawals = self.get_partial_withdrawals()
            
            # Track voluntary exits for status monitoring
            for exit_data in voluntary_exits:
                self.voluntary_exits_by_block[exit_data['validator_index']] = {
                    'exit_epoch': exit_data['exit_epoch'],
                    'slot': current_slot,
                    'epoch': current_epoch
                }
                
                # Save voluntary exits to database
                self.db.save_voluntary_exit(exit_data, current_slot, current_epoch)
                logger.info(f"New voluntary exit submitted for validator {exit_data['validator_index']} "
                          f"with exit_epoch {exit_data['exit_epoch']} "
                          f"and withdrawable_epoch {exit_data['withdrawable_epoch']}")
            
            # Update previous states for next comparison
            self.previous_validator_states = self.get_validator_states()
            
            status = {
                'timestamp': datetime.now().isoformat(),
                'slot': current_slot,
                'current_epoch': current_epoch,
                'voluntary_exits': voluntary_exits,
                'partial_withdrawals': partial_withdrawals
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error in monitor_queue: {str(e)}")
            raise

    def get_current_block_data(self):
        """Get current block data"""
        try:
            start_time = time.time()
            # Get current block from beacon chain
            url = f"{BEACON_API_V2}/blocks/head"
            response = requests.get(url, headers={'accept': 'application/json'})
            response.raise_for_status()
            data = response.json()
            
            if not data or 'data' not in data or 'message' not in data['data']:
                raise ValueError("Invalid response from beacon chain")
                
            current_slot = int(data['data']['message']['slot'])
            current_epoch = current_slot // self.SLOTS_PER_EPOCH
            
            end_time = time.time()
            logger.info(f"Block data API call took {end_time - start_time:.2f} seconds")
            
            return {
                'slot': current_slot,
                'epoch': current_epoch
            }
            
        except Exception as e:
            logger.error(f"Error getting current block data: {str(e)}")
            return None

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    try:
        monitor = ValidatorExitMonitor()
        status = monitor.monitor_queue()
        print("\nMonitoring Results:")
        print(f"Current Slot: {status['slot']}")
        print(f"Current Epoch: {status['current_epoch']}")
        print("\nVoluntary Exits:")
        for exit in status['voluntary_exits']:
            print(f"\nValidator {exit['validator_index']}:")
            print(f"  Exit Epoch: {exit['exit_epoch']}")
            print(f"  Signature: {exit['signature'][:66]}...")
    except Exception as e:
        logger.error(f"Error running monitor: {str(e)}")
        raise 