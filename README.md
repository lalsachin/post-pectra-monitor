# Ethereum Post-Pectra Monitor

A Python-based monitoring system for tracking Ethereum validator activities post-Pectra upgrade, focusing on voluntary exits, partial withdrawals, and validator withdrawal credentials.

## Features

### Voluntary Exit Monitor
- Tracks voluntary exit requests in real-time
- Monitors exit epochs and withdrawable epochs for each validator
- Updates every 12 seconds (one slot)
- Stores data in PostgreSQL database

### Validator Credentials Monitor
- Tracks validator withdrawal credentials (0x01 and 0x02)
- Collects data every 2 epochs (768 seconds) on even epochs
- Optimized to reduce API calls using shared cache
- Stores data in PostgreSQL database

### Partial Withdrawals Monitor
- Tracks partial withdrawals in real-time
- Updates every 12 seconds (one slot)
- Stores data in PostgreSQL database

## Database Schema

### voluntary_exits
- `validator_index`: Validator's index
- `exit_epoch`: Epoch when the validator will exit
- `withdrawable_epoch`: Epoch when the validator's balance becomes withdrawable
- `slot`: Slot when the exit was detected
- `timestamp`: When the exit was detected

### validator_withdrawal_credentials
- `epoch`: Epoch number
- `slot`: Slot number
- `timestamp`: When the data was collected
- `num_0x01_validators`: Number of validators with 0x01 credentials
- `num_0x02_validators`: Number of validators with 0x02 credentials

### partial_withdrawals
- `validator_index`: Validator's index
- `amount`: Amount withdrawn in Gwei
- `slot`: Slot when the withdrawal occurred
- `timestamp`: When the withdrawal was detected

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up PostgreSQL database:
```bash
psql -d validator_exits -f src/schema.sql
```

4. Run the monitors:
```bash
python src/main.py
```

## Architecture

The system uses a multi-process architecture:
- Each monitor runs in its own process
- Shared cache for epoch/slot data to reduce API calls
- Independent database connections for each process
- Graceful shutdown handling

## Optimizations

1. Shared Cache
   - Caches epoch and slot data for 12 seconds
   - Reduces duplicate API calls to the beacon chain
   - Used by both voluntary exit and validator credentials monitors

2. Efficient Scheduling
   - Voluntary exit monitor: Every 12 seconds (one slot)
   - Validator credentials monitor: Every 2 epochs (768 seconds) on even epochs
   - Partial withdrawals monitor: Every 12 seconds (one slot)

3. Database Optimizations
   - Uses UPSERT operations to prevent duplicates
   - Efficient indexing on frequently queried columns
   - Connection pooling for better performance

## Monitoring

The system provides real-time monitoring through:
- Detailed logging of all activities
- Database storage for historical analysis
- Tracking of validator counts and withdrawal types

## Requirements

- Python 3.8+
- PostgreSQL 12+
- QuickNode API access
- Required Python packages (see requirements.txt) 