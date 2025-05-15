import time
from typing import Optional, Tuple

class SharedCache:
    def __init__(self):
        self._current_epoch: Optional[int] = None
        self._current_slot: Optional[int] = None
        self._last_update_time: float = 0
        self._cache_duration: float = 12  # Cache for 12 seconds (one slot)

    def get_current_epoch_and_slot(self) -> Tuple[Optional[int], Optional[int]]:
        """Get the current epoch and slot from cache if not expired"""
        current_time = time.time()
        if current_time - self._last_update_time > self._cache_duration:
            return None, None
        return self._current_epoch, self._current_slot

    def update_epoch_and_slot(self, epoch: int, slot: int) -> None:
        """Update the cache with new epoch and slot values"""
        self._current_epoch = epoch
        self._current_slot = slot
        self._last_update_time = time.time()

# Create a singleton instance
shared_cache = SharedCache() 