from db import Database

def create_tables():
    """Create database tables if they don't exist"""
    try:
        db = Database()
        with db.conn.cursor() as cur:
            # Create voluntary_exits table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS voluntary_exits (
                    id SERIAL PRIMARY KEY,
                    validator_index INTEGER NOT NULL,
                    exit_epoch INTEGER NOT NULL,
                    withdrawable_epoch INTEGER NOT NULL,
                    transaction_hash VARCHAR(66) UNIQUE NOT NULL,
                    slot INTEGER NOT NULL,
                    epoch INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for voluntary_exits
            cur.execute("CREATE INDEX IF NOT EXISTS idx_voluntary_exits_validator_index ON voluntary_exits(validator_index)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_voluntary_exits_slot ON voluntary_exits(slot)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_voluntary_exits_exit_epoch ON voluntary_exits(exit_epoch)")
            
            # Create partial_withdrawals table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS partial_withdrawals (
                    id SERIAL PRIMARY KEY,
                    validator_index INTEGER NOT NULL,
                    exit_epoch INTEGER NOT NULL,
                    balance BIGINT NOT NULL,
                    effective_balance BIGINT NOT NULL,
                    pubkey VARCHAR(98) NOT NULL,
                    recipient_address VARCHAR(42) NOT NULL,
                    partial_withdrawal_amount BIGINT NOT NULL,
                    request_fee_paid BIGINT NOT NULL,
                    block_number INTEGER NOT NULL,
                    transaction_hash VARCHAR(66) UNIQUE NOT NULL,
                    slot INTEGER NOT NULL,
                    epoch INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for partial_withdrawals
            cur.execute("CREATE INDEX IF NOT EXISTS idx_partial_withdrawals_validator_index ON partial_withdrawals(validator_index)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_partial_withdrawals_block_number ON partial_withdrawals(block_number)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_partial_withdrawals_slot ON partial_withdrawals(slot)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_partial_withdrawals_exit_epoch ON partial_withdrawals(exit_epoch)")
            
            # Create validator_withdrawal_credentials table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS validator_withdrawal_credentials (
                    id SERIAL PRIMARY KEY,
                    epoch INTEGER NOT NULL,
                    slot INTEGER NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    num_0x01_validators INTEGER NOT NULL,
                    num_0x02_validators INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(epoch)
                )
            """)
            
            # Create indexes for validator_withdrawal_credentials
            cur.execute("CREATE INDEX IF NOT EXISTS idx_validator_withdrawal_credentials_epoch ON validator_withdrawal_credentials(epoch)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_validator_withdrawal_credentials_timestamp ON validator_withdrawal_credentials(timestamp)")
            
            db.conn.commit()
            print("Database tables created successfully!")
    except Exception as e:
        print(f"Error creating tables: {str(e)}")
        raise

if __name__ == "__main__":
    create_tables() 