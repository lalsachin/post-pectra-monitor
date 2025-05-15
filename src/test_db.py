import os
from dotenv import load_dotenv
import psycopg2
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def test_env_variables():
    """Test if all required environment variables are set"""
    required_vars = [
        'QUICKNODE_URL',
        'DB_NAME',
        'DB_USER',
        'DB_PASSWORD',
        'DB_HOST',
        'DB_PORT'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value is None:
            missing_vars.append(var)
        else:
            # Mask password for logging
            if var == 'DB_PASSWORD':
                value = '****' if value else 'empty'
            logger.info(f"{var}: {value}")
    
    if missing_vars:
        logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
        return False
    return True

def test_db_connection():
    """Test database connection"""
    try:
        conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT')
        )
        logger.info("Successfully connected to the database!")
        
        # Test if we can create tables
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()
            logger.info(f"PostgreSQL version: {version[0]}")
            
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Testing environment variables...")
    if test_env_variables():
        logger.info("All environment variables are set correctly")
        
        logger.info("\nTesting database connection...")
        if test_db_connection():
            logger.info("Database connection test passed!")
        else:
            logger.error("Database connection test failed!")
    else:
        logger.error("Environment variables test failed!") 