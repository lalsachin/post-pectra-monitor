import requests
import psycopg2
import os
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# QuickNode Beacon API endpoints
BEACON_API_BASE = "https://blue-stylish-crater.quiknode.pro/085cffcf2d858f52954961e2cba92a8a3572623d/eth"
BEACON_API_V1 = f"{BEACON_API_BASE}/v1/beacon"

def get_validator_status(validator_index):
    """Get the current status of a specific validator"""
    try:
        url = f"{BEACON_API_V1}/states/head/validators/{validator_index}"
        response = requests.get(url, headers={'accept': 'application/json'})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error getting validator status: {str(e)}")
        return None

def get_voluntary_exits_from_db():
    """Get all voluntary exits from the database"""
    try:
        conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME', 'validator_exits'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', ''),
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432')
        )
        
        with conn.cursor() as cur:
            cur.execute("""
                SELECT validator_index, exit_epoch, block_slot, block_epoch, timestamp 
                FROM voluntary_exits 
                ORDER BY timestamp DESC
            """)
            return cur.fetchall()
    except Exception as e:
        logger.error(f"Error getting voluntary exits from database: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()

def main():
    # Get all voluntary exits from database
    voluntary_exits = get_voluntary_exits_from_db()
    
    if not voluntary_exits:
        logger.info("No voluntary exits found in database")
        return
    
    logger.info(f"Found {len(voluntary_exits)} voluntary exits")
    
    # Check status of each validator
    for validator_index, exit_epoch, block_slot, block_epoch, timestamp in voluntary_exits:
        logger.info(f"\nChecking validator {validator_index}:")
        logger.info(f"Exit Epoch: {exit_epoch}")
        logger.info(f"Block Slot: {block_slot}")
        logger.info(f"Block Epoch: {block_epoch}")
        logger.info(f"Timestamp: {timestamp}")
        
        # Get current status
        status_data = get_validator_status(validator_index)
        if status_data and 'data' in status_data:
            validator_data = status_data['data']
            logger.info(f"Current Status: {validator_data['status']}")
            logger.info(f"Current Exit Epoch: {validator_data['validator']['exit_epoch']}")
            logger.info(f"Current Withdrawable Epoch: {validator_data['validator']['withdrawable_epoch']}")
            logger.info(f"Current Balance: {validator_data['balance']}")
        else:
            logger.error(f"Could not get status for validator {validator_index}")

if __name__ == "__main__":
    main() 