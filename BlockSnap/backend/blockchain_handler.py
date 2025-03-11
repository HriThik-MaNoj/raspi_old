#!/usr/bin/env python3

from web3 import Web3
from eth_account import Account
import json
import os
import logging
from typing import Tuple, Optional, Dict, List
from dotenv import load_dotenv
from pathlib import Path
import time
from datetime import datetime
import platform

load_dotenv()

class BlockchainHandler:
    def __init__(self):
        # Initialize logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Load environment variables
        self.rpc_url = os.getenv('ETH_RPC_URL', 'https://rpc.buildbear.io/impossible-omegared-15eaf7dd')
        self.contract_address = os.getenv('CONTRACT_ADDRESS')
        self.private_key = os.getenv('PRIVATE_KEY')
        
        if not all([self.rpc_url, self.contract_address, self.private_key]):
            raise ValueError("Missing required environment variables")
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError("Failed to connect to Ethereum network")
        
        # Load contract ABI
        contract_path = Path(__file__).parent.parent / 'artifacts' / 'smart_contracts' / 'BlockSnapNFT.sol' / 'BlockSnapNFT.json'
        if not contract_path.exists():
            raise FileNotFoundError(f"Contract ABI file not found at {contract_path}")
            
        with open(contract_path) as f:
            contract_json = json.load(f)
            self.contract_abi = contract_json['abi']
            self.logger.info("Successfully loaded contract ABI")
        
        # Initialize contract
        self.contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(self.contract_address),
            abi=self.contract_abi
        )
        
        # Initialize account
        self.account = Account.from_key(self.private_key)
        self.logger.info(f"Initialized with account: {self.account.address}")
        
        # Initialize IPFS handler
        from .ipfs_handler import IPFSHandler
        self.ipfs_handler = IPFSHandler()
    
    def mint_photo_nft(self, 
                      to_address: str, 
                      image_cid: str, 
                      metadata_uri: str) -> Tuple[str, int]:
        """
        Mint a new photo NFT
        Returns: Tuple(transaction_hash, token_id)
        """
        try:
            # Prepare transaction
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            
            # Build transaction
            tx = self.contract.functions.mintPhoto(
                self.w3.to_checksum_address(to_address),
                image_cid,
                metadata_uri
            ).build_transaction({
                'chainId': self.w3.eth.chain_id,
                'gas': 1000000,  # Increased gas limit for BuildBear
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
            })
            
            # Sign and send transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for transaction receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Get token ID from event logs with better error handling
            token_id = 0  # Default value if we can't get it from events
            try:
                events = self.contract.events.PhotoMinted().process_receipt(receipt)
                if events and len(events) > 0:
                    mint_event = events[0]
                    token_id = mint_event['args']['tokenId']
                    self.logger.info(f"Successfully extracted token ID {token_id} from event")
                else:
                    self.logger.warning(f"No PhotoMinted events found in receipt, using default token ID")
            except Exception as event_error:
                self.logger.error(f"Error processing event logs: {str(event_error)}")
                # Try to get the token ID using an alternative method if available
                # For now, we'll just use the default token_id = 0
            
            self.logger.info(f"Successfully minted NFT with token ID: {token_id}")
            return (self.w3.to_hex(tx_hash), token_id)
            
        except Exception as e:
            self.logger.error(f"Error minting NFT: {str(e)}")
            raise
    
    def verify_photo(self, image_cid: str) -> Tuple[bool, Optional[str]]:
        """
        Verify if a photo exists and get its owner
        Returns: Tuple(exists, owner_address)
        """
        try:
            exists, owner = self.contract.functions.verifyPhoto(image_cid).call()
            return exists, owner if exists else None
        except Exception as e:
            self.logger.error(f"Error verifying photo: {str(e)}")
            raise
    
    def get_token_uri(self, token_id: int) -> str:
        """Get the metadata URI for a token"""
        try:
            return self.contract.functions.tokenURI(token_id).call()
        except Exception as e:
            self.logger.error(f"Error getting token URI: {str(e)}")
            raise
    
    def get_image_cid(self, token_id: int) -> str:
        """Get the image CID for a token"""
        try:
            return self.contract.functions.getImageCID(token_id).call()
        except Exception as e:
            self.logger.error(f"Error getting image CID: {str(e)}")
            raise

    def start_video_session(self) -> Tuple[int, str]:
        """Start a new video recording session"""
        try:
            # Build transaction
            tx = self.contract.functions.startVideoSession().build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 500000,  
                'gasPrice': self.w3.eth.gas_price
            })
            
            # Sign and send transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_hash_hex = tx_hash.hex()  # Convert bytes to hex string
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Get session ID from event
            try:
                events = self.contract.events.VideoSessionStarted().process_receipt(receipt)
                if events and len(events) > 0:
                    event = events[0]
                    session_id = event['args']['sessionId']
                    self.logger.info(f"Started video session {session_id} with tx hash {tx_hash_hex}")
                    return session_id, tx_hash_hex
                else:
                    # No events found, use transaction hash as fallback
                    self.logger.warning("No VideoSessionStarted events found in receipt, using fallback")
                    # Use the last 8 digits of the transaction hash as a unique ID
                    fallback_id = int(tx_hash_hex[-8:], 16) % 1000000  # Convert to a 6-digit number
                    self.logger.info(f"Using fallback session ID: {fallback_id}")
                    return fallback_id, tx_hash_hex
            except Exception as event_error:
                # Handle event processing error
                self.logger.error(f"Error processing VideoSessionStarted event: {str(event_error)}")
                # Use the last 8 digits of the transaction hash as a unique ID
                fallback_id = int(tx_hash_hex[-8:], 16) % 1000000  # Convert to a 6-digit number
                self.logger.info(f"Using fallback session ID due to error: {fallback_id}")
                return fallback_id, tx_hash_hex
            
        except Exception as e:
            self.logger.error(f"Failed to start video session: {str(e)}")
            # Return a default session ID instead of raising an exception
            default_id = int(time.time()) % 1000000  # Use current timestamp as fallback
            self.logger.info(f"Using default session ID due to error: {default_id}")
            return default_id, ""  # Empty string for tx_hash when there's an error

    def add_video_chunk(self, session_id: int, sequence_number: int, video_cid: str, metadata_cid: str, timestamp: int) -> Tuple[bool, str]:
        """Add a video chunk to a session"""
        try:
            # Build transaction
            tx = self.contract.functions.addVideoChunk(
                session_id,
                sequence_number,
                video_cid,
                metadata_cid,
                timestamp
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 1000000,  
                'gasPrice': self.w3.eth.gas_price
            })
            
            # Sign and send transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_hash_hex = tx_hash.hex()  # Convert bytes to hex string
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            self.logger.info(f"Added video chunk {sequence_number} to session {session_id} with tx hash {tx_hash_hex}")
            return True, tx_hash_hex
            
        except Exception as e:
            self.logger.error(f"Failed to add video chunk: {str(e)}")
            # Return False instead of raising exception
            return False, ""

    def end_video_session(self, session_id: int) -> Tuple[bool, str]:
        """End a video recording session"""
        try:
            # Build transaction
            tx = self.contract.functions.endVideoSession(session_id).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 500000,  
                'gasPrice': self.w3.eth.gas_price
            })
            
            # Sign and send transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_hash_hex = tx_hash.hex()  # Convert bytes to hex string
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            self.logger.info(f"Ended video session {session_id} with tx hash {tx_hash_hex}")
            return True, tx_hash_hex
            
        except Exception as e:
            self.logger.error(f"Failed to end video session: {str(e)}")
            # Return False instead of raising exception
            return False, ""

    def get_video_sessions(self, wallet_address: str) -> List[Dict]:
        """Get all video sessions for a wallet address"""
        sessions = []
        try:
            # Get VideoSessionStarted events
            event_signature_hash = self.w3.keccak(text="VideoSessionStarted(uint256,address)").hex()
            
            # Try with a smaller block range first (last 1000 blocks)
            try:
                current_block = self.w3.eth.block_number
                from_block = max(0, current_block - 1000)
                
                logs = self.w3.eth.get_logs({
                    'address': self.contract.address,
                    'topics': [event_signature_hash],
                    'fromBlock': from_block,
                    'toBlock': 'latest'
                })
                self.logger.info(f"Found {len(logs)} VideoSessionStarted events in last 1000 blocks")
            except Exception as large_range_error:
                self.logger.warning(f"Error getting logs for large range: {str(large_range_error)}")
                # Try with an even smaller range (last 100 blocks)
                try:
                    current_block = self.w3.eth.block_number
                    from_block = max(0, current_block - 100)
                    
                    logs = self.w3.eth.get_logs({
                        'address': self.contract.address,
                        'topics': [event_signature_hash],
                        'fromBlock': from_block,
                        'toBlock': 'latest'
                    })
                    self.logger.info(f"Found {len(logs)} VideoSessionStarted events in last 100 blocks")
                except Exception as small_range_error:
                    self.logger.error(f"Error getting logs for small range: {str(small_range_error)}")
                    logs = []
            
            for log in logs:
                try:
                    # Decode the log data
                    decoded_log = self.contract.events.VideoSessionStarted().process_log(log)
                    session_id = decoded_log['args']['sessionId']
                    owner = decoded_log['args']['owner']
                    tx_hash = log.get('transactionHash', b'').hex()  # Get transaction hash from log
                    
                    # Check if this wallet owns the session
                    if owner.lower() == wallet_address.lower():
                        try:
                            # Get session chunks using the owner's address
                            chunks = self.contract.functions.getSessionChunks(session_id).call({
                                'from': wallet_address
                            })
                            
                            # Format chunks
                            formatted_chunks = []
                            for chunk in chunks:
                                # Try to get the transaction hash for this chunk
                                chunk_tx_hash = ""
                                try:
                                    # Look for VideoChunkAdded events for this session and sequence number
                                    chunk_event_hash = self.w3.keccak(text="VideoChunkAdded(uint256,uint256,string,string,uint256)").hex()
                                    chunk_logs = self.w3.eth.get_logs({
                                        'address': self.contract.address,
                                        'topics': [chunk_event_hash],
                                        'fromBlock': from_block,
                                        'toBlock': 'latest'
                                    })
                                    
                                    for chunk_log in chunk_logs:
                                        try:
                                            decoded_chunk = self.contract.events.VideoChunkAdded().process_log(chunk_log)
                                            if (decoded_chunk['args']['sessionId'] == session_id and 
                                                decoded_chunk['args']['sequenceNumber'] == chunk[1]):
                                                chunk_tx_hash = chunk_log.get('transactionHash', b'').hex()
                                                break
                                        except Exception:
                                            continue
                                except Exception as chunk_event_error:
                                    self.logger.warning(f"Could not get transaction hash for chunk: {str(chunk_event_error)}")
                                
                                formatted_chunks.append({
                                    'sequence_number': chunk[1],
                                    'video_cid': chunk[2],
                                    'metadata_cid': chunk[3],
                                    'timestamp': chunk[4],
                                    'tx_hash': chunk_tx_hash
                                })
                            
                            # Add session info
                            sessions.append({
                                'id': session_id,
                                'owner': owner,
                                'chunks': formatted_chunks,
                                'start_time': formatted_chunks[0]['timestamp'] if formatted_chunks else 0,
                                'tx_hash': tx_hash,
                                'blockchain_verified': True
                            })
                        except Exception as chunk_error:
                            self.logger.error(f"Error getting chunks for session {session_id}: {str(chunk_error)}")
                            # Add session with empty chunks
                            sessions.append({
                                'id': session_id,
                                'owner': owner,
                                'chunks': [],
                                'start_time': 0,
                                'tx_hash': tx_hash,
                                'blockchain_verified': True,
                                'error': f"Failed to retrieve chunks: {str(chunk_error)}"
                            })
                except Exception as e:
                    self.logger.error(f"Error processing session log: {str(e)}")
                    continue
            
            return sessions
            
        except Exception as e:
            self.logger.error(f"Failed to get video sessions: {str(e)}")
            return []  # Return empty list instead of raising exception

    def upload_to_ipfs(self, file_path: str) -> str:
        """Upload file to IPFS and return CID"""
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Upload to IPFS using the ipfs_handler
            filename = os.path.basename(file_path)
            cid = self.ipfs_handler.add_binary_data(file_data, filename)
            self.logger.info(f"Uploaded file to IPFS with CID: {cid}")
            return cid
            
        except Exception as e:
            self.logger.error(f"Failed to upload to IPFS: {str(e)}")
            return None

    def verify_by_transaction(self, tx_hash: str) -> Tuple[bool, Optional[Dict]]:
        """
        Verify if a transaction exists and get associated media information
        Returns: Tuple(exists, media_info_dict)
        """
        try:
            # Check if the transaction hash is valid format
            if not tx_hash.startswith('0x') or len(tx_hash) != 66:
                self.logger.warning(f"Invalid transaction hash format: {tx_hash}")
                return False, None
                
            # Get transaction receipt
            try:
                receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                if not receipt:
                    self.logger.warning(f"Transaction receipt not found for hash: {tx_hash}")
                    return False, None
            except Exception as e:
                self.logger.error(f"Error getting transaction receipt: {str(e)}")
                return False, None
                
            # Check if this is a transaction to our contract
            if receipt['to'] and receipt['to'].lower() != self.contract_address.lower():
                self.logger.warning(f"Transaction {tx_hash} is not for our contract")
                return True, {'type': 'external', 'message': 'Transaction is not for BlockSnap contract'}
                
            # Try to get the sender address as a fallback owner
            sender_address = None
            try:
                tx = self.w3.eth.get_transaction(tx_hash)
                if tx and 'from' in tx:
                    sender_address = tx['from']
            except Exception as e:
                self.logger.warning(f"Error getting transaction sender: {str(e)}")
                
            # Try to decode logs to determine what type of transaction this was
            media_info = {}
            
            # Check for PhotoMinted event
            try:
                photo_events = self.contract.events.PhotoMinted().process_receipt(receipt)
                if photo_events and len(photo_events) > 0:
                    event = photo_events[0]
                    media_info = {
                        'type': 'photo',
                        'token_id': event['args']['tokenId'],
                        'owner': event['args']['owner'],
                        'cid': event['args']['ipfsCID'],
                        'metadata_uri': event['args']['metadataURI']
                    }
                    return True, media_info
            except Exception as e:
                self.logger.warning(f"Error processing PhotoMinted event: {str(e)}")
                
            # Check for VideoChunkAdded event
            try:
                chunk_events = self.contract.events.VideoChunkAdded().process_receipt(receipt)
                if chunk_events and len(chunk_events) > 0:
                    event = chunk_events[0]
                    session_id = event['args']['sessionId']
                    
                    # Get the owner of this session
                    try:
                        # We can't directly query the owner, so we'll check session events
                        session_event_hash = self.w3.keccak(text="VideoSessionStarted(uint256,address)").hex()
                        
                        # Try with different block ranges to handle RPC limitations
                        owner = None
                        block_ranges = [
                            (max(0, self.w3.eth.block_number - 1000), 'latest'),  # Last 1000 blocks
                            (max(0, self.w3.eth.block_number - 100), 'latest'),   # Last 100 blocks
                            (0, 'latest')  # All blocks as last resort
                        ]
                        
                        for from_block, to_block in block_ranges:
                            try:
                                self.logger.info(f"Searching for session {session_id} owner in blocks {from_block} to {to_block}")
                                logs = self.w3.eth.get_logs({
                                    'address': self.contract.address,
                                    'topics': [session_event_hash],
                                    'fromBlock': from_block,
                                    'toBlock': to_block
                                })
                                
                                for log in logs:
                                    try:
                                        decoded_log = self.contract.events.VideoSessionStarted().process_log(log)
                                        if decoded_log['args']['sessionId'] == session_id:
                                            owner = decoded_log['args']['owner']
                                            self.logger.info(f"Found owner {owner} for session {session_id}")
                                            break
                                    except Exception as e:
                                        self.logger.debug(f"Error decoding log: {str(e)}")
                                        continue
                                        
                                if owner:
                                    break  # Exit the block range loop if owner found
                                    
                            except Exception as e:
                                self.logger.warning(f"Error querying logs with range {from_block}-{to_block}: {str(e)}")
                                continue  # Try next block range
                        
                        # If owner is still None, use the transaction sender as fallback
                        if not owner:
                            owner = sender_address
                            self.logger.info(f"Using sender address {sender_address} as fallback owner for session {session_id}")
                            
                    except Exception as e:
                        self.logger.warning(f"Error finding session owner: {str(e)}")
                        owner = sender_address  # Use sender address as fallback owner
                    
                    media_info = {
                        'type': 'video_chunk',
                        'session_id': session_id,
                        'sequence_number': event['args']['sequenceNumber'],
                        'cid': event['args']['videoCID'],
                        'owner': owner
                    }
                    return True, media_info
            except Exception as e:
                self.logger.warning(f"Error processing VideoChunkAdded event: {str(e)}")
                
            # Check for VideoSessionStarted event
            try:
                session_events = self.contract.events.VideoSessionStarted().process_receipt(receipt)
                if session_events and len(session_events) > 0:
                    event = session_events[0]
                    media_info = {
                        'type': 'video_session',
                        'session_id': event['args']['sessionId'],
                        'owner': event['args']['owner']
                    }
                    return True, media_info
            except Exception as e:
                self.logger.warning(f"Error processing VideoSessionStarted event: {str(e)}")
                
            # If we got here, try to get transaction details to identify the type
            try:
                # Get the full transaction to analyze the input data
                tx = self.w3.eth.get_transaction(tx_hash)
                if tx and tx.get('input'):
                    # Check function signatures to identify the transaction type
                    # First 10 characters (including 0x) of the input data is the function signature
                    function_sig = tx['input'][:10] if len(tx['input']) >= 10 else ''
                    
                    # Map of known function signatures
                    known_functions = {
                        # These are example signatures - you'll need to replace with actual ones
                        '0x6a627842': 'mint',  # Example signature for mint function
                        '0x9d118770': 'addVideoChunk',  # Example signature for addVideoChunk
                        '0x21a9eed2': 'startVideoSession'  # Example signature for startVideoSession
                    }
                    
                    function_name = known_functions.get(function_sig, 'unknown')
                    self.logger.info(f"Transaction appears to be calling function: {function_name}")
                    
                    media_info = {
                        'type': 'contract_interaction',
                        'function': function_name,
                        'owner': sender_address,
                        'message': f"Transaction calls {function_name} function"
                    }
                    return True, media_info
            except Exception as e:
                self.logger.warning(f"Error analyzing transaction input: {str(e)}")
            
            # If we got here, the transaction exists but we couldn't identify the media type
            return True, {
                'type': 'unknown', 
                'message': 'Transaction exists but media type could not be determined',
                'owner': sender_address
            }
            
        except Exception as e:
            self.logger.error(f"Error verifying transaction: {str(e)}")
            return False, None

if __name__ == "__main__":
    # Example usage
    handler = BlockchainHandler()
    
    # Test verification
    test_cid = "QmTest123"
    exists, owner = handler.verify_photo(test_cid)
    print(f"Photo exists: {exists}")
    if exists:
        print(f"Owner: {owner}") 