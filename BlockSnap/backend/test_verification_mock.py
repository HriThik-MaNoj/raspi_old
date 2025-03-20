#!/usr/bin/env python3

import os
import json
import logging
import sys
from dotenv import load_dotenv
import unittest
from unittest.mock import patch, MagicMock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('test_verification_mock')

# Load environment variables
load_dotenv()

class TestBlockchainVerification(unittest.TestCase):
    """Test the blockchain verification functionality with mocks"""
    
    @patch('blockchain_handler.Web3')
    def test_verify_by_transaction(self, mock_web3):
        """Test the verify_by_transaction method with mocked blockchain"""
        # First patch the import of IPFSHandler in blockchain_handler
        with patch('sys.modules.get', side_effect=lambda name: MagicMock() if name == 'ipfs_handler' else None):
            from blockchain_handler import BlockchainHandler
            
            # Setup mock Web3 instance
            mock_w3 = MagicMock()
            mock_web3.return_value = mock_w3
            
            # Mock eth object
            mock_w3.eth = MagicMock()
            mock_w3.eth.block_number = 1000
            
            # Mock contract
            mock_contract = MagicMock()
            mock_w3.eth.contract.return_value = mock_contract
            
            # Mock transaction receipt
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
            
            # Mock transaction
            mock_transaction = {
                'from': '0xabcdef1234567890abcdef1234567890abcdef12',
                'input': '0x50d85511'  # mintPhoto function signature
            }
            mock_w3.eth.get_transaction.return_value = mock_transaction
            
            # Setup mock keccak
            mock_w3.keccak.return_value = b'\x01\x02\x03\x04'
            
            # Mock contract events
            mock_event = MagicMock()
            mock_event.process_log.return_value = {
                'args': {
                    'tokenId': 123,
                    'owner': '0xabcdef1234567890abcdef1234567890abcdef12',
                    'metadataURI': 'ipfs://Qm123456789'
                }
            }
            mock_contract.events.PhotoMinted.return_value = mock_event
            
            # Create a handler with our mocks
            handler = BlockchainHandler()
            
            # Manually set properties that would normally be initialized
            handler.w3 = mock_w3
            handler.contract = mock_contract
            handler.contract_address = '0x1234567890123456789012345678901234567890'
            
            # Test verification
            tx_hash = '0x123456789abcdef123456789abcdef123456789abcdef123456789abcdef1234'
            exists, media_info = handler.verify_by_transaction(tx_hash)
            
            # Assertions
            self.assertTrue(exists)
            self.assertEqual(media_info['media_type'], 'photo')
            self.assertEqual(media_info['token_id'], 123)
            self.assertEqual(media_info['owner'], '0xabcdef1234567890abcdef1234567890abcdef12')
            self.assertEqual(media_info['cid'], 'Qm123456789')
            
            # Print verification result
            logger.info(f"Verification result: {exists}")
            logger.info(f"Media info: {json.dumps(media_info, indent=2)}")
    
    @patch('distributed_node.requests')
    def test_distributed_verification(self, mock_requests):
        """Test the distributed verification with mocked network requests"""
        from distributed_node import DistributedNode
        
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'exists_on_blockchain': True,
            'owner': '0xabcdef1234567890abcdef1234567890abcdef12',
            'media_type': 'photo',
            'token_id': 123,
            'cid': 'Qm123456789',
            'metadata_uri': 'ipfs://Qm123456789'
        }
        mock_requests.get.return_value = mock_response
        
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
        
        # Mock media registry
        node.media_registry = {}
        node._save_media_registry = MagicMock()  # Mock save method
        
        # Test verification
        tx_hash = '0x123456789abcdef123456789abcdef123456789abcdef123456789abcdef1234'
        result = node.verify_media_across_network(tx_hash)
        
        # Assertions
        self.assertTrue(result['verified'])
        self.assertEqual(result['source'], 'peer_peer1')
        self.assertEqual(result['media_info']['media_type'], 'photo')
        self.assertEqual(result['media_info']['token_id'], 123)
        
        # Print verification result
        logger.info(f"Network verification result: {json.dumps(result, indent=2)}")
        
        # Verify media was registered locally
        mock_requests.post.assert_called_once()

if __name__ == "__main__":
    unittest.main()
