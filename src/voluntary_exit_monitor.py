from shared_cache import shared_cache
import time

def run_voluntary_exit_monitor_loop():
    """Run the voluntary exit monitor continuously"""
    try:
        monitor = VoluntaryExitMonitor()
        last_processed_slot = monitor.last_processed_slot
        
        while True:
            # Try to get from cache first
            current_epoch, current_slot = shared_cache.get_current_epoch_and_slot()
            
            # If cache is empty or expired, get fresh data
            if current_epoch is None or current_slot is None:
                current_epoch = monitor.get_current_epoch()
                current_slot = monitor.get_current_slot()
                
                if current_epoch is None or current_slot is None:
                    logger.error("Failed to get current epoch/slot")
                    time.sleep(12)  # Wait before retrying
                    continue
                
                # Update the cache
                shared_cache.update_epoch_and_slot(current_epoch, current_slot)
            
            # Only process if we haven't processed this slot yet
            if current_slot > last_processed_slot:
                logger.info(f"Processing slot {current_slot}")
                
                # Get voluntary exits
                voluntary_exits = monitor.get_voluntary_exits()
                
                if voluntary_exits is not None:
                    # Save to database
                    monitor.save_voluntary_exits(current_epoch, current_slot, voluntary_exits)
                    
                    logger.info(f"Slot {current_slot} stats:")
                    logger.info(f"  Number of voluntary exits: {len(voluntary_exits)}")
                else:
                    logger.error("Failed to get voluntary exits")
                
                last_processed_slot = current_slot
            
            # Sleep until next block
            time.sleep(12)  # Check every 12 seconds
            
    except Exception as e:
        logger.error(f"Error in voluntary exit monitor loop: {str(e)}")
        raise
    finally:
        # Close database connection
        if hasattr(monitor, 'db'):
            monitor.db.close() 