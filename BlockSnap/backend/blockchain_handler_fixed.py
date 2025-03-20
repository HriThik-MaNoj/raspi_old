#!/usr/bin/env python3

from web3 import Web3
from eth_account import Account
import json
import os
import logging
from pathlib import Path
from typing import Tuple, Dict, List, Optional, Any
import time
import random
from requests.exceptions import ReadTimeout, ConnectionError as RequestsConnectionError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class BlockchainHandler:
    def __init__(self):
        # Initialize logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Connection status
        self.is_connected = False
        
        # Load environment variables
        self.primary_rpc_url = os.getenv('ETH_RPC_URL', 'https://rpc.buildbear.io/imaginative-ghostrider-4b8c9868')
        # Fallback RPC URLs (comma-separated list in env var)
        fallback_urls = os.getenv('FALLBACK_RPC_URLS', '')
        self.fallback_rpc_urls = [url.strip() for url in fallback_urls.split(',')] if fallback_urls else [
            # Default fallbacks if none provided
            'https://rpc.buildbear.io/imaginative-ghostrider-4b8c9868'
        ]
        
        self.contract_address = os.getenv('CONTRACT_ADDRESS')
        self.private_key = os.getenv('PRIVATE_KEY')
        
        if not all([self.primary_rpc_url, self.contract_address, self.private_key]):
            self.logger.warning("Missing required environment variables, some functionality will be limited")
            return
        
        # Initialize Web3 with increased timeout and retry logic
        self.max_retries = int(os.getenv('MAX_RETRIES', '3'))
        self.retry_delay = int(os.getenv('RETRY_DELAY', '2'))  # seconds
        self.timeout = int(os.getenv('REQUEST_TIMEOUT', '30'))  # seconds
        
        # Current active RPC URL
        self.current_rpc_url = self.primary_rpc_url
        
        # Try to connect with retry logic
        try:
            self._initialize_web3_with_retry()
            
            # Load contract ABI
            contract_path = Path(__file__).parent.parent / 'artifacts' / 'smart_contracts' / 'BlockSnapNFT.sol' / 'BlockSnapNFT.json'
            if not contract_path.exists():
                self.logger.error(f"Contract ABI file not found at {contract_path}")
                return
                
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
            try:
                from .ipfs_handler import IPFSHandler
                self.ipfs_handler = IPFSHandler()
            except ImportError:
                self.logger.warning("IPFS handler import failed. IPFS functionality will be limited.")
                self.ipfs_handler = None
                
        except Exception as e:
            self.logger.error(f"Failed to initialize blockchain handler: {str(e)}")
            # Don't raise the exception, just log it
    
    def _initialize_web3_with_retry(self):
        """Initialize Web3 with retry logic to handle connection issues"""
        attempts = 0
        last_error = None
        
        # Log the RPC URL we're trying to connect to
        self.logger.info(f"Attempting to connect to Ethereum network using RPC URL: {self.current_rpc_url}")
        
        while attempts < self.max_retries:
            try:
                # Create a provider with increased timeout
                provider = Web3.HTTPProvider(
                    self.current_rpc_url,
                    request_kwargs={'timeout': self.timeout}
                )
                self.w3 = Web3(provider)
                
                # Check connection
                if self.w3.is_connected():
                    self.logger.info(f"Successfully connected to Ethereum network after {attempts+1} attempts")
                    # Log chain ID for verification
                    chain_id = self.w3.eth.chain_id
                    self.logger.info(f"Connected to network with Chain ID: {chain_id}")
                    self.is_connected = True
                    return
                
                # If we get here, connection check failed but didn't raise an exception
                self.logger.warning(f"Connection check failed on attempt {attempts+1}")
                
            except (ReadTimeout, RequestsConnectionError) as e:
                last_error = e
                self.logger.warning(f"Connection attempt {attempts+1} failed with network error: {str(e)}")
            except Exception as e:
                last_error = e
                self.logger.warning(f"Connection attempt {attempts+1} failed with unexpected error: {str(e)}")
                # Print exception type for better debugging
                self.logger.warning(f"Exception type: {type(e).__name__}")
                import traceback
                self.logger.warning(f"Traceback: {traceback.format_exc()}")
            
            # Try fallback RPC URLs if primary fails
            if self.current_rpc_url == self.primary_rpc_url:
                self.logger.info("Trying fallback RPC URLs...")
                for fallback_url in self.fallback_rpc_urls:
                    self.current_rpc_url = fallback_url
                    self.logger.info(f"Trying fallback RPC URL: {fallback_url}")
                    break  # Try the first fallback URL for now
            
            # Exponential backoff with jitter
            delay = self.retry_delay * (2 ** attempts) + random.uniform(0, 1)
            self.logger.info(f"Retrying in {delay:.2f} seconds...")
            time.sleep(delay)
            attempts += 1
        
        # If we get here, all retries failed
        self.logger.error(f"Failed to connect to Ethereum network after {self.max_retries} attempts")
        self.is_connected = False
        # Don't raise an exception, just log the error
    
    def _execute_with_retry(self, operation_name, operation_func, *args, **kwargs):
        """Execute a Web3 operation with retry logic"""
        if not self.is_connected:
            self.logger.error(f"Cannot execute {operation_name}: Not connected to Ethereum network")
            return None
            
        attempts = 0
        last_error = None
        tried_fallbacks = False
        
        while attempts < self.max_retries:
            try:
                self.logger.debug(f"Executing {operation_name} (attempt {attempts+1})")
                return operation_func(*args, **kwargs)
            except (ReadTimeout, RequestsConnectionError, Exception) as e:
                last_error = e
                self.logger.warning(f"{operation_name} attempt {attempts+1} failed: {str(e)}")
                
                # Check if we need to reconnect to the RPC
                if not self.w3.is_connected():
                    self.logger.warning("Web3 connection lost, attempting to reconnect...")
                    
                    # Try fallback RPC URLs if not already tried
                    if not tried_fallbacks and self.current_rpc_url == self.primary_rpc_url and self.fallback_rpc_urls:
                        self.logger.info("Switching to fallback RPC URL...")
                        # Try each fallback URL
                        for fallback_url in self.fallback_rpc_urls:
                            self.current_rpc_url = fallback_url
                            self.logger.info(f"Trying fallback RPC URL: {fallback_url}")
                            
                            try:
                                # Create a provider with increased timeout
                                provider = Web3.HTTPProvider(
                                    self.current_rpc_url,
                                    request_kwargs={'timeout': self.timeout}
                                )
                                self.w3 = Web3(provider)
                                
                                # Check connection
                                if self.w3.is_connected():
                                    self.logger.info(f"Successfully connected to fallback RPC: {fallback_url}")
                                    # Reinitialize contract after reconnection
                                    self.contract = self.w3.eth.contract(
                                        address=self.w3.to_checksum_address(self.contract_address),
                                        abi=self.contract_abi
                                    )
                                    tried_fallbacks = True
                                    # Reset attempts to give the fallback a fair chance
                                    attempts = 0
                                    break
                            except Exception as fallback_error:
                                self.logger.warning(f"Failed to connect to fallback RPC {fallback_url}: {str(fallback_error)}")
                    
                    # If fallbacks didn't work or weren't available, try to reconnect to current RPC
                    if not tried_fallbacks or not self.w3.is_connected():
                        try:
                            self._initialize_web3_with_retry()
                            # Reinitialize contract after reconnection
                            self.contract = self.w3.eth.contract(
                                address=self.w3.to_checksum_address(self.contract_address),
                                abi=self.contract_abi
                            )
                        except Exception as reconnect_error:
                            self.logger.error(f"Failed to reconnect: {str(reconnect_error)}")
            
            # Exponential backoff with jitter
            delay = self.retry_delay * (2 ** attempts) + random.uniform(0, 1)
            self.logger.info(f"Retrying {operation_name} in {delay:.2f} seconds...")
            time.sleep(delay)
            attempts += 1
        
        self.logger.error(f"{operation_name} failed after {self.max_retries} attempts")
        return None

    # Add all the other methods from the original file here...
    # For brevity, I'm not including them all, but in a real implementation,
    # you would copy all the other methods from the original file
    
    def mint_photo_nft(self, recipient_address: str, image_cid: str, metadata_uri: str) -> Tuple[str, int]:
        """Mint a new photo NFT"""
        if not self.is_connected:
            self.logger.error("Cannot mint NFT: Not connected to Ethereum network")
            return None, None
            
        try:
            # Prepare transaction
            tx = self.contract.functions.mintPhotoNFT(
                self.w3.to_checksum_address(recipient_address),
                image_cid,
                metadata_uri
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 500000,  # Gas limit
                'gasPrice': self.w3.eth.gas_price,
                'chainId': self.w3.eth.chain_id
            })
            
            # Sign transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=self.private_key)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for transaction receipt
            self.logger.info(f"Waiting for transaction {tx_hash.hex()} to be mined...")
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            # Get token ID from event logs
            token_id = None
            for log in tx_receipt.logs:
                try:
                    # Try to decode the log as a Transfer event
                    event = self.contract.events.Transfer().process_log(log)
                    if event and event.args.to.lower() == recipient_address.lower():
                        token_id = event.args.tokenId
                        break
                except:
                    continue
            
            if token_id is None:
                self.logger.warning(f"Could not find token ID in transaction logs: {tx_hash.hex()}")
                # Try to get the latest token ID
                try:
                    token_id = self.contract.functions.getLatestTokenId().call()
                except Exception as e:
                    self.logger.error(f"Failed to get latest token ID: {str(e)}")
            
            return tx_hash.hex(), token_id
        except Exception as e:
            self.logger.error(f"Error minting NFT: {str(e)}")
            return None, None
    
    def verify_photo(self, image_cid: str) -> Tuple[bool, str]:
        """Verify if a photo exists on the blockchain and get its owner"""
        if not self.is_connected:
            self.logger.error("Cannot verify photo: Not connected to Ethereum network")
            return False, None
            
        try:
            # Call the contract method to verify the photo
            result = self.contract.functions.verifyPhoto(image_cid).call()
            exists = result[0]
            owner = result[1] if exists else None
            return exists, owner
        except Exception as e:
            self.logger.error(f"Error verifying photo: {str(e)}")
            return False, None
