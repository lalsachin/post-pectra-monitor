import requests
import json
import logging
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def test_quicknode_connection():
    url = os.getenv('QUICKNODE_URL')
    if not url:
        logger.error("QUICKNODE_URL not found in environment variables")
        return False
    
    payload = json.dumps({
        "method": "eth_blockNumber",
        "params": [],
        "id": 1,
        "jsonrpc": "2.0"
    })
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        result = response.json()
        logger.info(f"Response: {json.dumps(result, indent=2)}")
        
        if 'result' in result:
            block_number = int(result['result'], 16)  # Convert hex to decimal
            logger.info(f"Current block number: {block_number}")
            return True
        else:
            logger.error(f"Unexpected response format: {result}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {str(e)}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Testing QuickNode connection...")
    success = test_quicknode_connection()
    if success:
        logger.info("QuickNode connection test successful!")
    else:
        logger.error("QuickNode connection test failed!") 