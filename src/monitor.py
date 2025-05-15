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
        
        # Track last checked block for partial withdrawals
        self.last_checked_block = self.w3.eth.block_number

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
            validator_indices = []
            exit_data_map = {}  # Map to store exit data by validator index
            
            # First collect all validator indices and their exit data
            for exit_data in message['body']['voluntary_exits']:
                validator_index = int(exit_data['message']['validator_index'])
                validator_indices.append(validator_index)
                exit_data_map[validator_index] = exit_data

            if not validator_indices:
                return []

            # Batch query all validators at once
            validator_ids = '&'.join([f'id={idx}' for idx in validator_indices])
            url = f"{BEACON_API_V1}/states/head/validators?{validator_ids}"
            response = requests.get(url, headers={'accept': 'application/json'})
            response.raise_for_status()
            validators_data = response.json()
            
            if not validators_data or 'data' not in validators_data:
                logger.warning("No data received for validators")
                return []

            # Process all validators data
            for validator_data in validators_data['data']:
                validator_index = int(validator_data['index'])
                if validator_index not in exit_data_map:
                    continue

                validator = validator_data['validator']
                exit_data = exit_data_map[validator_index]
                
                voluntary_exit = {
                    'validator_index': validator_index,
                    'exit_epoch': int(validator['exit_epoch']),
                    'withdrawable_epoch': int(validator['withdrawable_epoch']),
                    'balance': int(validator_data['balance']),
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
            
            # Process logs and collect validator addresses
            withdrawals = []
            validator_addresses = []
            withdrawal_data_map = {}  # Map to store withdrawal data by validator address
            
            for log in logs:
                try:
                    decoded = self.contract.events.PartialWithdrawalRequested().processLog(log)
                    validator_address = decoded.args.validator
                    validator_addresses.append(validator_address)
                    withdrawal_data_map[validator_address] = {
                        'decoded': decoded,
                        'log': log
                    }
                except Exception as e:
                    logger.error(f"Error decoding partial withdrawal log: {str(e)}")
                    continue

            if not validator_addresses:
                return []

            # Batch query all validators at once
            validator_ids = '&'.join([f'id={addr}' for addr in validator_addresses])
            url = f"{BEACON_API_V1}/states/head/validators?{validator_ids}"
            response = requests.get(url, headers={'accept': 'application/json'})
            response.raise_for_status()
            validators_data = response.json()
            
            if not validators_data or 'data' not in validators_data:
                logger.warning("No data received for validators")
                return []

            # Process all validators data
            for validator_data in validators_data['data']:
                validator_address = validator_data['validator']['pubkey']
                if validator_address not in withdrawal_data_map:
                    continue

                withdrawal_info = withdrawal_data_map[validator_address]
                decoded = withdrawal_info['decoded']
                log = withdrawal_info['log']
                
                withdrawal = {
                    'validator_index': int(validator_data['index']),
                    'exit_epoch': int(validator_data['validator']['exit_epoch']),
                    'balance': int(validator_data['balance']),
                    'effective_balance': int(validator_data['validator']['effective_balance']),
                    'pubkey': validator_data['validator']['pubkey'],
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
            
            return withdrawals
        except Exception as e:
            logger.error(f"Error getting partial withdrawals: {str(e)}")
            return []

    def get_active_exiting_validators(self):
        """
        Get all validators with active_exiting status and find the ones with earliest and latest exit epochs
        """
        try:
            url = f"{BEACON_API_V1}/states/head/validators?status=active_exiting"
            response = requests.get(url, headers={'accept': 'application/json'})
            response.raise_for_status()
            data = response.json()
            
            if not data or 'data' not in data:
                return None
                
            validators = data['data']
            if not validators:
                return {
                    'validators_in_queue': 0,
                    'earliest_exit_epoch': 0,
                    'earliest_withdrawable_epoch': 0,
                    'latest_exit_epoch': 0,
                    'lastest_withdrawable_epoch': 0,
                    'first_validator_index': 0,
                    'first_validator_pubkey': '',
                    'last_validator_index': 0,
                    'last_validator_pubkey': '',
                    'balance_in_queue': 0
                }
            
            # Calculate total balance in queue
            total_balance = sum(int(v['balance']) for v in validators)
            
            # Sort validators by exit_epoch
            sorted_validators = sorted(
                validators,
                key=lambda x: int(x['validator']['exit_epoch'])
            )
            
            # Get first (earliest) and last (latest) validators
            first_validator = sorted_validators[0]
            last_validator = sorted_validators[-1]
            
            return {
                'validators_in_queue': len(validators),
                'earliest_exit_epoch': int(first_validator['validator']['exit_epoch']),
                'earliest_withdrawable_epoch': int(first_validator['validator']['withdrawable_epoch']),
                'latest_exit_epoch': int(last_validator['validator']['exit_epoch']),
                'lastest_withdrawable_epoch': int(last_validator['validator']['withdrawable_epoch']),
                'first_validator_index': int(first_validator['index']),
                'first_validator_pubkey': first_validator['validator']['pubkey'],
                'last_validator_index': int(last_validator['index']),
                'last_validator_pubkey': last_validator['validator']['pubkey'],
                'balance_in_queue': total_balance
            }
        except Exception as e:
            logger.error(f"Error getting active exiting validators: {str(e)}")
            return None

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
            
            # 3. Get active exiting validators data if:
            #    a) We found new voluntary exits, or
            #    b) This is the first run (no previous slot tracked)
            active_exiting_data = None
            if voluntary_exits or not hasattr(self, 'last_processed_slot'):
                active_exiting_data = self.get_active_exiting_validators()
                if active_exiting_data:
                    active_exiting_data.update({
                        'slot': current_slot,
                        'epoch': current_epoch
                    })
                    self.db.save_full_exits_queue(active_exiting_data)
                    logger.info(f"Active exiting validators: {active_exiting_data['validators_in_queue']}")
                    logger.info(f"Earliest exit epoch: {active_exiting_data['earliest_exit_epoch']}")
                    logger.info(f"Latest exit epoch: {active_exiting_data['latest_exit_epoch']}")
            
            # Update last processed slot
            self.last_processed_slot = current_slot
            
            # Save voluntary exits to database
            for exit_data in voluntary_exits:
                self.db.save_voluntary_exit(exit_data, current_slot, current_epoch)
                logger.info(f"New voluntary exit submitted for validator {exit_data['validator_index']} "
                          f"with exit_epoch {exit_data['exit_epoch']} "
                          f"and withdrawable_epoch {exit_data['withdrawable_epoch']}")
            
            status = {
                'timestamp': datetime.now().isoformat(),
                'slot': current_slot,
                'current_epoch': current_epoch,
                'voluntary_exits': voluntary_exits,
                'partial_withdrawals': partial_withdrawals,
                'active_exiting': active_exiting_data
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