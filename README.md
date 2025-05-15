# Ethereum Validator Exit Monitor

A monitoring tool for tracking Ethereum validator exits, focusing on the transition from voluntary exit submission to active_exiting status.

## Overview

This tool monitors the Ethereum validator exit queue, tracking:
- Voluntary exits submitted in each block
- Validators transitioning to active_exiting status
- Exit and withdrawable epochs for exiting validators
- Historical exit data in PostgreSQL database

## Features

- Real-time monitoring of validator status changes
- Efficient API usage with filtered queries for active_exiting validators
- Double verification of validator status changes
- PostgreSQL database storage for:
  - Voluntary exits
  - Exiting validators
  - Historical status changes
- Detailed logging of:
  - New voluntary exits
  - Status transitions
  - Exit and withdrawable epochs
  - Validator balances

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd ethereum_post_pectra_monitor
```

2. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip3 install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration:
# - QUICKNODE_URL: Your Ethereum node URL
# - DB_NAME: PostgreSQL database name (default: validator_exits)
# - DB_USER: PostgreSQL username (default: postgres)
# - DB_PASSWORD: PostgreSQL password
# - DB_HOST: PostgreSQL host (default: localhost)
# - DB_PORT: PostgreSQL port (default: 5432)
```

5. Run the monitor:
```bash
python3 src/main.py
```

## Database Schema

### Voluntary Exits Table
- `id`: Serial primary key
- `validator_index`: Validator index
- `exit_epoch`: Epoch when the exit was submitted
- `signature`: Exit signature
- `block_slot`: Block slot when exit was submitted
- `block_epoch`: Block epoch when exit was submitted
- `timestamp`: When the exit was recorded

### Exiting Validators Table
- `id`: Serial primary key
- `validator_index`: Validator index
- `status`: Current validator status
- `exit_epoch`: Epoch when validator will exit
- `withdrawable_epoch`: Epoch when validator can withdraw
- `balance`: Current validator balance
- `effective_balance`: Current effective balance
- `pubkey`: Validator public key
- `previous_status`: Previous validator status
- `timestamp`: When the status change was recorded

## Monitoring Process

1. **Voluntary Exit Detection**
   - Monitors each block for voluntary exits
   - Records exit details in database
   - Tracks validators that have submitted exits

2. **Status Change Detection**
   - Efficiently queries only active_exiting validators
   - Compares with previous state to detect changes
   - Verifies status changes with individual validator checks

3. **Data Storage**
   - Saves voluntary exits to database
   - Records validator status changes
   - Maintains historical exit data

## Project Structure

```
ethereum_post_pectra_monitor/
├── src/
│   ├── main.py
│   ├── monitor.py
│   └── utils.py
├── tests/
├── requirements.txt
├── .env.example
└── README.md
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License 