import logging
from monitor import ValidatorExitMonitor
from db import Database
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_voluntary_exit_tracking():
    """Test the voluntary exit tracking logic"""
    try:
        # Initialize monitor
        monitor = ValidatorExitMonitor()
        
        # Get current slot and epoch
        current_slot = monitor.get_current_slot()
        current_epoch = monitor.get_current_epoch()
        
        # Create a test voluntary exit
        test_validator_index = 676285  # Using the validator we're interested in
        test_exit = {
            'validator_index': test_validator_index,
            'exit_epoch': current_epoch,
            'signature': '0x' + '0' * 192  # Placeholder signature
        }
        
        # Add to voluntary_exits_by_block
        monitor.voluntary_exits_by_block[test_validator_index] = {
            'exit_epoch': test_exit['exit_epoch'],
            'block_slot': current_slot,
            'block_epoch': current_epoch
        }
        
        # Save to database
        monitor.db.save_voluntary_exit(test_exit, current_slot, current_epoch)
        logger.info(f"Added test voluntary exit for validator {test_validator_index}")
        
        # Run monitor_queue to process the exit
        status = monitor.monitor_queue()
        
        # Check if validator was processed
        logger.info("\nMonitoring Results:")
        logger.info(f"Current Slot: {status['slot']}")
        logger.info(f"Current Epoch: {status['current_epoch']}")
        
        # Check voluntary exits
        logger.info("\nVoluntary Exits:")
        for exit_data in status['voluntary_exits']:
            logger.info(f"Validator {exit_data['validator_index']}:")
            logger.info(f"  Exit Epoch: {exit_data['exit_epoch']}")
        
        # Check new exiting validators
        logger.info("\nNew Exiting Validators:")
        for validator in status['new_exiting_validators']:
            logger.info(f"Validator {validator['validator_index']}:")
            logger.info(f"  Previous Status: {validator['previous_status']}")
            logger.info(f"  Exit Epoch: {validator['exit_epoch']}")
            logger.info(f"  Withdrawable Epoch: {validator['withdrawable_epoch']}")
        
        # Verify in database
        with monitor.db.conn.cursor() as cur:
            # Check voluntary_exits table
            cur.execute("""
                SELECT * FROM voluntary_exits 
                WHERE validator_index = %s
            """, (test_validator_index,))
            voluntary_exit = cur.fetchone()
            logger.info("\nDatabase Check - Voluntary Exit:")
            if voluntary_exit:
                logger.info(f"Found in voluntary_exits table: {voluntary_exit}")
            else:
                logger.info("Not found in voluntary_exits table")
            
            # Check exiting_validators table
            cur.execute("""
                SELECT * FROM exiting_validators 
                WHERE validator_index = %s
            """, (test_validator_index,))
            exiting_validator = cur.fetchone()
            logger.info("\nDatabase Check - Exiting Validator:")
            if exiting_validator:
                logger.info(f"Found in exiting_validators table: {exiting_validator}")
            else:
                logger.info("Not found in exiting_validators table")
        
    except Exception as e:
        logger.error(f"Error in test: {str(e)}")
        raise
    finally:
        if 'monitor' in locals():
            monitor.db.close()

if __name__ == "__main__":
    test_voluntary_exit_tracking() 