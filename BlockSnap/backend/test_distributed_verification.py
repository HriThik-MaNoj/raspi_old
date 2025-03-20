#!/usr/bin/env python3

import os
import json
import logging
import sys
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('test_distributed_verification')

# Load environment variables
load_dotenv()

def test_distributed_verification():
    """Test the distributed verification functionality"""
    # Import here to avoid module loading issues
    from distributed_node import DistributedNode
    
    # Patch the requests module used by DistributedNode
    with patch('distributed_node.requests') as mock_requests:
        # Setup mock response for peer verification
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'exists_on_blockchain': True,
            'owner': '0xabcdef1234567890abcdef1234567890abcdef12',
            'media_type': 'photo',
            'token_id': 123,
            'cid': 'Qm123456789',
            'metadata_uri': 'ipfs://Qm123456789',
            'timestamp': '2023-01-01T12:00:00Z',
            'device_id': 'test_device_001'
        }
        mock_requests.get.return_value = mock_response
        
        # Mock POST response for discovery service
        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post_response.text = "OK"
        mock_requests.post.return_value = mock_post_response
        
        # Initialize distributed node
        node = DistributedNode()
        
        # Mock peers
        node.peers = {
            'peer1': {
                'node_id': 'peer1',
                'endpoint': 'http://peer1.example.com',
                'capabilities': {'verify': True}
            }
        }
        node.enable_p2p = True
        
        # Mock media registry and save method
        node.media_registry = {}
        node._save_media_registry = MagicMock()
        
        # Test verification with a sample transaction hash
        tx_hash = '0x123456789abcdef123456789abcdef123456789abcdef123456789abcdef1234'
        logger.info(f"Testing verification for transaction: {tx_hash}")
        
        result = node.verify_media_across_network(tx_hash)
        
        # Log the result
        logger.info(f"Verification result: {json.dumps(result, indent=2)}")
        
        # Verify that the result contains all expected fields
        assert result['verified'] == True, "Verification should be successful"
        assert result['source'] == 'peer_peer1', "Source should be peer_peer1"
        assert 'media_info' in result, "Result should contain media_info"
        assert result['media_info']['media_type'] == 'photo', "Media type should be 'photo'"
        assert result['media_info']['owner'] == '0xabcdef1234567890abcdef1234567890abcdef12', "Owner should match"
        assert result['media_info']['token_id'] == 123, "Token ID should match"
        
        # Verify that the media was registered locally
        assert tx_hash in node.media_registry, "Transaction hash should be in media registry"
        assert node.media_registry[tx_hash]['media_type'] == 'photo', "Media type should be registered correctly"
        
        logger.info("All assertions passed! Distributed verification is working correctly.")
        
        # Return the result for further inspection if needed
        return result

if __name__ == "__main__":
    try:
        result = test_distributed_verification()
        logger.info("Test completed successfully!")
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        sys.exit(1)
