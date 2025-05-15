import os
from dotenv import load_dotenv
from web3 import Web3
import logging
from datetime import datetime
from monitor import ValidatorExitMonitor
import time
import multiprocessing
from validator_credentials_monitor import run_validator_credentials_monitor
from multiprocessing import Process

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Ethereum node configuration
ETH_NODE_URL = os.getenv('QUICKNODE_URL')
if not ETH_NODE_URL:
    raise ValueError("QUICKNODE_URL not found in environment variables")

class ExitQueueMonitor:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(ETH_NODE_URL))
        if not self.w3.is_connected():
            raise ConnectionError("Failed to connect to Ethereum node")
        
        logger.info("Connected to Ethereum node successfully")
        
    def get_exit_queue_status(self):
        """
        Get the current status of the validator exit queue
        """
        try:
            # Get current block number
            block_number = self.w3.eth.block_number
            logger.info(f"Current block number: {block_number}")
            
            # TODO: Implement actual exit queue monitoring logic
            # This is a placeholder for the actual implementation
            return {
                'timestamp': datetime.now().isoformat(),
                'block_number': block_number,
                'queue_length': 0,
                'estimated_exit_time': None
            }
        except Exception as e:
            logger.error(f"Error getting exit queue status: {str(e)}")
            raise

def run_voluntary_exit_monitor_loop():
    """Run the voluntary exit monitor loop"""
    try:
        monitor = ValidatorExitMonitor()
        last_epoch = None
        
        while True:
            # Get current block data
            start_time = time.time()
            block_data = monitor.get_current_block_data()
            end_time = time.time()
            logger.info(f"Block data API call took {end_time - start_time:.2f} seconds")
            
            if block_data:
                current_slot = block_data['slot']
                current_epoch = block_data['epoch']
                num_voluntary_exits = block_data['num_voluntary_exits']
                num_partial_withdrawals = block_data['num_partial_withdrawals']
                
                logger.info(f"Current Slot: {current_slot}")
                logger.info(f"Current Epoch: {current_epoch}")
                logger.info(f"Number of voluntary exits: {num_voluntary_exits}")
                logger.info(f"Number of partial withdrawals: {num_partial_withdrawals}")
                
                # Save to database
                monitor.save_block_data(block_data)
                
                # Check if we're in a new epoch
                if last_epoch is not None and current_epoch > last_epoch:
                    # If it's an even epoch, spawn validator credentials monitor
                    if current_epoch % 2 == 0:
                        logger.info(f"Spawning validator credentials monitor for epoch {current_epoch}")
                        process = Process(target=run_validator_credentials_monitor)
                        process.start()
                        process.join()  # Wait for the process to complete
                
                last_epoch = current_epoch
            
            time.sleep(12)  # Check every 12 seconds
            
    except Exception as e:
        logger.error(f"Error in voluntary exit monitor loop: {str(e)}")
        raise
    finally:
        if hasattr(monitor, 'db'):
            monitor.db.close()

def main():
    """Main function to run all monitors"""
    try:
        # Start voluntary exit monitor in a separate process
        exit_monitor_process = Process(target=run_voluntary_exit_monitor_loop)
        exit_monitor_process.start()
        
        # Start validator credentials monitor in a separate process
        credentials_monitor_process = Process(target=run_validator_credentials_monitor)
        credentials_monitor_process.start()
        
        # Wait for both processes to complete
        exit_monitor_process.join()
        credentials_monitor_process.join()
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise
    finally:
        logger.info("Database connection closed")

if __name__ == "__main__":
    main() 