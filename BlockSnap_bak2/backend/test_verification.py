#!/usr/bin/env python3

import os
import json
import logging
import sys
from dotenv import load_dotenv
from blockchain_handler import BlockchainHandler
from distributed_node import DistributedNode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('test_verification')

# Load environment variables
load_dotenv()

def test_transaction_verification(tx_hash):
    """Test transaction verification with the enhanced implementation"""
    logger.info(f"Testing verification for transaction: {tx_hash}")
    
    # Initialize blockchain handler
    blockchain_handler = BlockchainHandler()
    
    # Verify transaction
    logger.info("Verifying transaction locally...")
    exists, media_info = blockchain_handler.verify_by_transaction(tx_hash)
    
    if exists:
        logger.info(f"Transaction exists on blockchain: {exists}")
        logger.info(f"Media type: {media_info.get('media_type', 'unknown')}")
        logger.info(f"Owner: {media_info.get('owner', 'unknown')}")
        
        # Print all available metadata
        logger.info("All available metadata:")
        for key, value in media_info.items():
            if key != 'verification_result':  # Skip nested verification result
                logger.info(f"  {key}: {value}")
    else:
        logger.warning(f"Transaction {tx_hash} not found on blockchain")
    
    # Test distributed verification
    distributed_node = DistributedNode()
    
    logger.info("\nVerifying transaction across network...")
    network_result = distributed_node.verify_media_across_network(tx_hash)
    
    if network_result['verified']:
        logger.info(f"Transaction verified by: {network_result['source']}")
        logger.info("Network verification result:")
        for key, value in network_result['media_info'].items():
            if key != 'verification_result':  # Skip nested verification result
                logger.info(f"  {key}: {value}")
    else:
        logger.warning(f"Transaction not verified across network: {network_result['message']}")

if __name__ == "__main__":
    # Check if a transaction hash was provided as an argument
    if len(sys.argv) > 1:
        tx_hash = sys.argv[1]
    else:
        # Use a default test transaction hash
        tx_hash = "0x123456789abcdef123456789abcdef123456789abcdef123456789abcdef1234"
        logger.info(f"No transaction hash provided, using default: {tx_hash}")
    
    test_transaction_verification(tx_hash)
