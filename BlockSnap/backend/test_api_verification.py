#!/usr/bin/env python3

import os
import json
import logging
import sys
import requests
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('test_api_verification')

# Load environment variables
load_dotenv()

def test_api_verification(tx_hash, base_url="http://localhost:5000"):
    """Test the API endpoint for transaction verification"""
    logger.info(f"Testing API verification for transaction: {tx_hash}")
    
    # Construct the API URL
    api_url = f"{base_url}/api/verify/tx/{tx_hash}"
    logger.info(f"API URL: {api_url}")
    
    try:
        # Make the API request
        response = requests.get(api_url)
        
        # Check if the request was successful
        if response.status_code == 200:
            result = response.json()
            logger.info(f"API Response: {json.dumps(result, indent=2)}")
            
            # Verify that the response contains the expected fields
            assert 'exists_on_blockchain' in result, "Response should contain 'exists_on_blockchain' field"
            
            if result['exists_on_blockchain']:
                # Verify that the response contains media information
                assert 'owner' in result, "Response should contain 'owner' field"
                assert 'media_type' in result, "Response should contain 'media_type' field"
                
                # Log additional details based on media type
                media_type = result.get('media_type')
                logger.info(f"Media Type: {media_type}")
                logger.info(f"Owner: {result.get('owner', 'unknown')}")
                
                if media_type == 'photo':
                    assert 'token_id' in result, "Photo should have 'token_id' field"
                    logger.info(f"Token ID: {result.get('token_id')}")
                elif media_type == 'video_chunk':
                    assert 'chunk_id' in result, "Video chunk should have 'chunk_id' field"
                    assert 'session_id' in result, "Video chunk should have 'session_id' field"
                    logger.info(f"Chunk ID: {result.get('chunk_id')}")
                    logger.info(f"Session ID: {result.get('session_id')}")
                elif media_type == 'video_session':
                    assert 'session_id' in result, "Video session should have 'session_id' field"
                    logger.info(f"Session ID: {result.get('session_id')}")
                
                logger.info("API verification test passed!")
                return True
            else:
                logger.warning(f"Transaction {tx_hash} not found on blockchain")
                return False
        else:
            logger.error(f"API request failed with status code: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"API verification test failed: {str(e)}")
        return False

def test_distributed_api_verification(tx_hash, base_url="http://localhost:5000"):
    """Test the distributed API endpoint for transaction verification"""
    logger.info(f"Testing distributed API verification for transaction: {tx_hash}")
    
    # Construct the API URL
    api_url = f"{base_url}/api/distributed/verify/tx/{tx_hash}"
    logger.info(f"API URL: {api_url}")
    
    try:
        # Make the API request
        response = requests.get(api_url)
        
        # Check if the request was successful
        if response.status_code == 200:
            result = response.json()
            logger.info(f"API Response: {json.dumps(result, indent=2)}")
            
            # Verify that the response contains the expected fields
            assert 'verified' in result, "Response should contain 'verified' field"
            
            if result['verified']:
                # Verify that the response contains media information
                assert 'media_info' in result, "Response should contain 'media_info' field"
                assert 'source' in result, "Response should contain 'source' field"
                
                media_info = result['media_info']
                logger.info(f"Source: {result.get('source')}")
                logger.info(f"Media Type: {media_info.get('media_type', 'unknown')}")
                logger.info(f"Owner: {media_info.get('owner', 'unknown')}")
                
                logger.info("Distributed API verification test passed!")
                return True
            else:
                logger.warning(f"Transaction {tx_hash} not verified across network: {result.get('message', '')}")
                return False
        else:
            logger.error(f"API request failed with status code: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Distributed API verification test failed: {str(e)}")
        return False

if __name__ == "__main__":
    # Check if a transaction hash was provided as an argument
    if len(sys.argv) > 1:
        tx_hash = sys.argv[1]
    else:
        # Use a default test transaction hash
        tx_hash = "0x123456789abcdef123456789abcdef123456789abcdef123456789abcdef1234"
        logger.info(f"No transaction hash provided, using default: {tx_hash}")
    
    # Test both API endpoints
    direct_result = test_api_verification(tx_hash)
    distributed_result = test_distributed_api_verification(tx_hash)
    
    if direct_result and distributed_result:
        logger.info("All API verification tests passed successfully!")
        sys.exit(0)
    else:
        logger.warning("Some API verification tests failed.")
        sys.exit(1)
