#!/usr/bin/env python3

import os
import json
import logging
import sys
import importlib.util
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

logger = logging.getLogger('test_blockchain_verification')

# Load environment variables
load_dotenv()

# Create a mock IPFSHandler class
class MockIPFSHandler:
    def __init__(self):
        pass
    
    def get_metadata(self, cid):
        return {"name": "Test Media", "description": "Test Description"}

# Mock the ipfs_handler module
sys.modules['ipfs_handler'] = MagicMock()
sys.modules['ipfs_handler'].IPFSHandler = MockIPFSHandler

def test_blockchain_verification():
    """Test the blockchain verification functionality"""
    # Import after mocking
    import blockchain_handler
    from blockchain_handler import BlockchainHandler
    
    # Patch the relative import in blockchain_handler
    blockchain_handler.IPFSHandler = MockIPFSHandler
    
    # Patch Web3 to avoid actual blockchain connections
    with patch('blockchain_handler.Web3') as mock_web3_class:
        # Setup mock Web3 instance
        mock_w3 = MagicMock()
        mock_web3_class.return_value = mock_w3
        
        # Mock eth object
        mock_w3.eth = MagicMock()
        mock_w3.eth.block_number = 1000
        
        # Mock contract
        mock_contract = MagicMock()
        mock_w3.eth.contract.return_value = mock_contract
        
        # Mock transaction receipt for a photo transaction
        mock_receipt = {
            'to': '0x1234567890123456789012345678901234567890',  # Contract address
            'logs': [
                {
                    'address': '0x1234567890123456789012345678901234567890',
                    'topics': [b'\x01\x02\x03\x04']
                }
            ]
        }
        mock_w3.eth.get_transaction_receipt.return_value = mock_receipt
        
        # Mock transaction with photo minting function signature
        mock_transaction = {
            'from': '0xabcdef1234567890abcdef1234567890abcdef12',
            'input': '0x50d85511'  # mintPhoto function signature
        }
        mock_w3.eth.get_transaction.return_value = mock_transaction
        
        # Setup mock keccak
        mock_w3.keccak.return_value = b'\x01\x02\x03\x04'
        
        # Mock contract events for photo
        mock_photo_event = MagicMock()
        mock_photo_event.process_log.return_value = {
            'args': {
                'tokenId': 123,
                'owner': '0xabcdef1234567890abcdef1234567890abcdef12',
                'metadataURI': 'ipfs://Qm123456789'
            }
        }
        mock_contract.events.PhotoMinted.return_value = mock_photo_event
        
        # Initialize blockchain handler with mocked Web3
        handler = BlockchainHandler()
        
        # Manually set properties that would normally be initialized
        handler.w3 = mock_w3
        handler.contract = mock_contract
        handler.contract_address = '0x1234567890123456789012345678901234567890'
        
        # Test photo verification
        tx_hash = '0x123456789abcdef123456789abcdef123456789abcdef123456789abcdef1234'
        logger.info(f"Testing verification for photo transaction: {tx_hash}")
        
        exists, media_info = handler.verify_by_transaction(tx_hash)
        
        # Log the result
        logger.info(f"Verification result: {exists}")
        logger.info(f"Media info: {json.dumps(media_info, indent=2)}")
        
        # Verify that the result contains all expected fields for a photo
        assert exists == True, "Verification should be successful"
        assert media_info['media_type'] == 'photo', "Media type should be 'photo'"
        assert media_info['token_id'] == 123, "Token ID should match"
        assert media_info['owner'] == '0xabcdef1234567890abcdef1234567890abcdef12', "Owner should match"
        assert media_info['cid'] == 'Qm123456789', "CID should be extracted correctly"
        
        logger.info("Photo verification test passed!")
        
        # Now test video chunk verification
        # Update mock transaction with video chunk function signature
        mock_transaction['input'] = '0x12345678'  # Mocked video chunk function signature
        
        # Mock contract events for video chunk
        mock_video_event = MagicMock()
        mock_video_event.process_log.return_value = {
            'args': {
                'chunkId': 456,
                'sessionId': 789,
                'owner': '0xabcdef1234567890abcdef1234567890abcdef12',
                'metadataURI': 'ipfs://Qm987654321'
            }
        }
        mock_contract.events.VideoChunkMinted.return_value = mock_video_event
        
        # Test video chunk verification
        tx_hash = '0xabcdef123456789abcdef123456789abcdef123456789abcdef123456789abcde'
        logger.info(f"\nTesting verification for video chunk transaction: {tx_hash}")
        
        exists, media_info = handler.verify_by_transaction(tx_hash)
        
        # Log the result
        logger.info(f"Verification result: {exists}")
        logger.info(f"Media info: {json.dumps(media_info, indent=2)}")
        
        # Verify that the result contains all expected fields for a video chunk
        assert exists == True, "Verification should be successful"
        assert media_info['media_type'] == 'video_chunk', "Media type should be 'video_chunk'"
        assert media_info['chunk_id'] == 456, "Chunk ID should match"
        assert media_info['session_id'] == 789, "Session ID should match"
        assert media_info['owner'] == '0xabcdef1234567890abcdef1234567890abcdef12', "Owner should match"
        assert media_info['cid'] == 'Qm987654321', "CID should be extracted correctly"
        
        logger.info("Video chunk verification test passed!")
        
        # Test contract interaction (fallback case)
        # Update mock transaction with unknown function signature
        mock_transaction['input'] = '0x99999999'  # Unknown function signature
        
        # No event logs for this transaction
        mock_receipt['logs'] = []
        
        # Test contract interaction verification
        tx_hash = '0x9999999999999999999999999999999999999999999999999999999999999999'
        logger.info(f"\nTesting verification for contract interaction transaction: {tx_hash}")
        
        exists, media_info = handler.verify_by_transaction(tx_hash)
        
        # Log the result
        logger.info(f"Verification result: {exists}")
        logger.info(f"Media info: {json.dumps(media_info, indent=2)}")
        
        # Verify that the result contains expected fields for a contract interaction
        assert exists == True, "Verification should be successful"
        assert media_info['media_type'] == 'contract_interaction', "Media type should be 'contract_interaction'"
        assert media_info['owner'] == '0xabcdef1234567890abcdef1234567890abcdef12', "Owner should match"
        
        logger.info("Contract interaction verification test passed!")
        logger.info("All blockchain verification tests passed successfully!")
        
        return True

if __name__ == "__main__":
    try:
        success = test_blockchain_verification()
        if success:
            logger.info("All tests completed successfully!")
            sys.exit(0)
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
