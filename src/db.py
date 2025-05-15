import psycopg2
from psycopg2.extras import Json
import logging
from datetime import datetime
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def get_db_connection():
    """Get a database connection"""
    return psycopg2.connect(
        dbname=os.getenv('DB_NAME', 'validator_exits'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432')
    )

class Database:
    def __init__(self):
        self.conn = None
        self.connect()
        self.create_tables()

    def connect(self):
        """Connect to the PostgreSQL database"""
        try:
            self.conn = get_db_connection()
            logger.info("Connected to PostgreSQL database successfully")
        except Exception as e:
            logger.error(f"Error connecting to database: {str(e)}")
            raise

    def create_tables(self):
        """Create necessary database tables if they don't exist"""
        try:
            with self.conn.cursor() as cur:
                # Create validator_withdrawal_credentials table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS validator_withdrawal_credentials (
                        epoch INTEGER PRIMARY KEY,
                        slot INTEGER NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        num_0x01_validators INTEGER NOT NULL,
                        num_0x02_validators INTEGER NOT NULL
                    )
                """)
                
                # Create voluntary_exits table if it doesn't exist
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS voluntary_exits (
                        id SERIAL PRIMARY KEY,
                        validator_index INTEGER NOT NULL,
                        exit_epoch INTEGER NOT NULL,
                        withdrawable_epoch INTEGER NOT NULL,
                        balance BIGINT NOT NULL,
                        effective_balance BIGINT NOT NULL,
                        pubkey TEXT NOT NULL,
                        signature TEXT NOT NULL,
                        slot INTEGER NOT NULL,
                        epoch INTEGER NOT NULL,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(validator_index, signature)
                    );
                """)
                
                # Create partial_withdrawals table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS partial_withdrawals (
                        id SERIAL PRIMARY KEY,
                        validator_index INTEGER NOT NULL,
                        exit_epoch INTEGER NOT NULL,
                        balance BIGINT NOT NULL,
                        effective_balance BIGINT NOT NULL,
                        pubkey TEXT NOT NULL,
                        recipient_address TEXT NOT NULL,
                        partial_withdrawal_amount BIGINT NOT NULL,
                        request_fee_paid BIGINT NOT NULL,
                        block_number INTEGER NOT NULL,
                        transaction_hash TEXT NOT NULL,
                        slot INTEGER NOT NULL,
                        epoch INTEGER NOT NULL,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(transaction_hash)
                    );
                """)
                
                # Create full_exits_queue table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS full_exits_queue (
                        id SERIAL PRIMARY KEY,
                        slot INTEGER NOT NULL,
                        epoch INTEGER NOT NULL,
                        validators_in_queue INTEGER NOT NULL,
                        earliest_exit_epoch INTEGER NOT NULL,
                        earliest_withdrawable_epoch INTEGER NOT NULL,
                        latest_exit_epoch INTEGER NOT NULL,
                        lastest_withdrawable_epoch INTEGER NOT NULL,
                        first_validator_index INTEGER NOT NULL,
                        first_validator_pubkey TEXT NOT NULL,
                        last_validator_index INTEGER NOT NULL,
                        last_validator_pubkey TEXT NOT NULL,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # Create indexes for voluntary_exits if they don't exist
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_voluntary_exits_validator_index 
                    ON voluntary_exits(validator_index);
                    
                    CREATE INDEX IF NOT EXISTS idx_voluntary_exits_exit_epoch 
                    ON voluntary_exits(exit_epoch);
                    
                    CREATE INDEX IF NOT EXISTS idx_voluntary_exits_slot 
                    ON voluntary_exits(slot);
                """)
                
                # Create indexes for partial_withdrawals
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_partial_withdrawals_validator 
                    ON partial_withdrawals(validator_index);
                    
                    CREATE INDEX IF NOT EXISTS idx_partial_withdrawals_block 
                    ON partial_withdrawals(block_number);
                    
                    CREATE INDEX IF NOT EXISTS idx_partial_withdrawals_slot 
                    ON partial_withdrawals(slot);
                    
                    CREATE INDEX IF NOT EXISTS idx_partial_withdrawals_exit_epoch 
                    ON partial_withdrawals(exit_epoch);
                """)
                
                # Create indexes for full_exits_queue
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_full_exits_queue_slot 
                    ON full_exits_queue(slot);
                    
                    CREATE INDEX IF NOT EXISTS idx_full_exits_queue_epoch 
                    ON full_exits_queue(epoch);
                    
                    CREATE INDEX IF NOT EXISTS idx_full_exits_queue_exit_epochs 
                    ON full_exits_queue(earliest_exit_epoch, latest_exit_epoch);
                """)
                
                self.conn.commit()
                logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {str(e)}")
            raise

    def save_voluntary_exit(self, voluntary_exit, block_slot, block_epoch):
        """Save voluntary exit information"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO voluntary_exits 
                    (validator_index, exit_epoch, withdrawable_epoch, 
                     balance, effective_balance, pubkey, signature, slot, epoch)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (validator_index, signature) DO NOTHING
                """, (
                    voluntary_exit['validator_index'],
                    voluntary_exit['exit_epoch'],
                    voluntary_exit['withdrawable_epoch'],
                    voluntary_exit['balance'],
                    voluntary_exit['effective_balance'],
                    voluntary_exit['pubkey'],
                    voluntary_exit['signature'],
                    block_slot,
                    block_epoch
                ))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Error saving voluntary exit: {str(e)}")
            raise

    def save_partial_withdrawal(self, withdrawal_data):
        """Save partial withdrawal information"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO partial_withdrawals 
                    (validator_index, exit_epoch, balance, effective_balance, pubkey,
                     recipient_address, partial_withdrawal_amount, request_fee_paid,
                     block_number, transaction_hash, slot, epoch)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (transaction_hash) DO NOTHING
                """, (
                    withdrawal_data['validator_index'],
                    withdrawal_data['exit_epoch'],
                    withdrawal_data['balance'],
                    withdrawal_data['effective_balance'],
                    withdrawal_data['pubkey'],
                    withdrawal_data['recipient_address'],
                    withdrawal_data['partial_withdrawal_amount'],
                    withdrawal_data['request_fee_paid'],
                    withdrawal_data['block_number'],
                    withdrawal_data['transaction_hash'],
                    withdrawal_data['slot'],
                    withdrawal_data['epoch']
                ))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Error saving partial withdrawal: {str(e)}")
            raise

    def save_full_exits_queue(self, queue_data):
        """Save full exits queue information"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO full_exits_queue 
                    (slot, epoch, validators_in_queue, 
                     earliest_exit_epoch, earliest_withdrawable_epoch,
                     latest_exit_epoch, lastest_withdrawable_epoch,
                     first_validator_index, first_validator_pubkey,
                     last_validator_index, last_validator_pubkey)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    queue_data['slot'],
                    queue_data['epoch'],
                    queue_data['validators_in_queue'],
                    queue_data['earliest_exit_epoch'],
                    queue_data['earliest_withdrawable_epoch'],
                    queue_data['latest_exit_epoch'],
                    queue_data['lastest_withdrawable_epoch'],
                    queue_data['first_validator_index'],
                    queue_data['first_validator_pubkey'],
                    queue_data['last_validator_index'],
                    queue_data['last_validator_pubkey']
                ))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Error saving full exits queue data: {str(e)}")
            raise

    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed") 