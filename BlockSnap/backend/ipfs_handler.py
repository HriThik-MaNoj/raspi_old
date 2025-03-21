#!/usr/bin/env python3

import os
import logging
import requests
import json
from typing import Dict, Tuple, Optional, List
from datetime import datetime
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import random

class IPFSHandler:
    def __init__(self):
        # Initialize logging
        self.logger = logging.getLogger(__name__)
        
        # Load environment variables
        load_dotenv()
        self.ipfs_host = os.getenv('IPFS_HOST', 'http://127.0.0.1:5001')
        self.ipfs_gateway = os.getenv('IPFS_GATEWAY', 'http://127.0.0.1:8080')
        self.use_pinata = os.getenv('USE_PINATA', 'false').lower() == 'true'
        self.pinata_api_key = os.getenv('PINATA_API_KEY')
        self.pinata_secret_key = os.getenv('PINATA_SECRET_KEY')
        
        # Retry configuration
        self.max_retries = int(os.getenv('MAX_RETRIES', '5'))
        self.retry_delay = int(os.getenv('RETRY_DELAY', '2'))  # seconds
        
        # Connect to IPFS daemon with retry logic
        self._connect_with_retry()
        
    def _connect_with_retry(self):
        """Connect to IPFS daemon with retry logic"""
        attempts = 0
        last_error = None
        
        self.logger.info(f"Attempting to connect to IPFS daemon at {self.ipfs_host}")
        
        while attempts < self.max_retries:
            try:
                # Test connection to IPFS daemon
                response = requests.post(f"{self.ipfs_host}/api/v0/version")
                response.raise_for_status()
                self.logger.info(f"Connected to IPFS daemon at {self.ipfs_host}")
                return
            except Exception as e:
                last_error = e
                self.logger.warning(f"Connection attempt {attempts+1} failed: {str(e)}")
                
                # Exponential backoff with jitter
                delay = self.retry_delay * (2 ** attempts) + random.uniform(0, 1)
                self.logger.info(f"Retrying in {delay:.2f} seconds...")
                time.sleep(delay)
                attempts += 1
        
        # If we get here, all retries failed
        self.logger.error(f"Failed to connect to IPFS daemon after {self.max_retries} attempts")
        raise ConnectionError(f"Failed to connect to IPFS daemon: {str(last_error)}")

    def add_file(self, file_path: str) -> str:
        """Add a file to IPFS and return its CID"""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            if self.use_pinata:
                # Use Pinata for file upload
                with open(file_path, 'rb') as f:
                    files = {
                        'file': (os.path.basename(file_path), f, 'video/webm')
                    }
                    headers = {
                        'pinata_api_key': self.pinata_api_key,
                        'pinata_secret_api_key': self.pinata_secret_key
                    }
                    
                    response = requests.post(
                        'https://api.pinata.cloud/pinning/pinFileToIPFS',
                        files=files,
                        headers=headers
                    )
                    response.raise_for_status()
                    
                    result = response.json()
                    cid = result['IpfsHash']
            else:
                # Use local IPFS node
                with open(file_path, 'rb') as f:
                    files = {
                        'file': (os.path.basename(file_path), f, 'video/webm')
                    }
                    
                    response = requests.post(
                        f"{self.ipfs_host}/api/v0/add",
                        files=files
                    )
                    response.raise_for_status()
                    
                    result = response.json()
                    cid = result['Hash']
            
            # Pin the file to ensure it persists
            self.pin_file(cid)
            self.logger.info(f"Successfully pinned CID: {cid}")
            return cid
            
        except Exception as e:
            self.logger.error(f"Failed to add file to IPFS: {str(e)}")
            raise

    def pin_file(self, cid: str) -> None:
        """Pin a file on IPFS"""
        try:
            response = requests.post(
                f"{self.ipfs_host}/api/v0/pin/add",
                params={'arg': cid}
            )
            response.raise_for_status()
            self.logger.info(f"Successfully pinned CID: {cid}")
        except Exception as e:
            self.logger.error(f"Error pinning file: {str(e)}")
            raise

    def add_binary_data(self, data: bytes, filename: str = None) -> str:
        """Add binary data to IPFS and return its CID"""
        try:
            if self.use_pinata:
                headers = {
                    'pinata_api_key': self.pinata_api_key,
                    'pinata_secret_api_key': self.pinata_secret_key
                }
                files = {'file': (filename or 'chunk.mp4', data)}
                response = requests.post(
                    'https://api.pinata.cloud/pinning/pinFileToIPFS',
                    files=files,
                    headers=headers
                )
            else:
                files = {'file': (filename or 'chunk.mp4', data)}
                response = requests.post(
                    f"{self.ipfs_host}/api/v0/add",
                    files=files
                )
            
            response.raise_for_status()
            result = response.json()
            cid = result.get('IpfsHash') or result.get('Hash')
            
            if not self.use_pinata:
                self.pin_file(cid)
            
            return cid
        except Exception as e:
            self.logger.error(f"Error adding binary data to IPFS: {str(e)}")
            raise

    def add_video_chunk(self, chunk) -> Dict:
        """
        Add a video chunk to IPFS
        Returns: Dict with CID and metadata
        """
        try:
            # Upload video data
            cid = self.add_binary_data(
                chunk.data,
                f"chunk_{chunk.sequence_number}.mp4"
            )
            
            # Create and upload metadata
            metadata = chunk.get_metadata()
            metadata['ipfs_cid'] = cid
            metadata_cid = self.add_binary_data(
                json.dumps(metadata).encode(),
                f"chunk_{chunk.sequence_number}_meta.json"
            )
            
            return {
                'video_cid': cid,
                'metadata_cid': metadata_cid,
                'sequence_number': chunk.sequence_number,
                'timestamp': chunk.timestamp.isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error processing video chunk: {str(e)}")
            raise

    def batch_upload_chunks(self, chunks: List, batch_size: int = 5) -> List:
        """
        Efficiently upload multiple chunks in batches
        Args:
            chunks: List of VideoChunk objects
            batch_size: Number of chunks to process in parallel
        Returns:
            List of upload results
        """
        try:
            results = []
            total_chunks = len(chunks)
            self.logger.info(f"Starting batch upload of {total_chunks} chunks")

            # Process chunks in batches
            for i in range(0, total_chunks, batch_size):
                batch = chunks[i:i + batch_size]
                batch_results = []

                # Use ThreadPoolExecutor for parallel uploads
                with ThreadPoolExecutor(max_workers=batch_size) as executor:
                    futures = [
                        executor.submit(self.add_video_chunk, chunk)
                        for chunk in batch
                    ]
                    
                    # Collect results as they complete
                    for future in as_completed(futures):
                        try:
                            result = future.result()
                            batch_results.append(result)
                        except Exception as e:
                            self.logger.error(f"Chunk upload failed: {str(e)}")
                            # Continue with remaining chunks
                            continue

                results.extend(batch_results)
                self.logger.info(f"Processed batch {i//batch_size + 1}/{(total_chunks + batch_size - 1)//batch_size}")

                # Rate limiting
                if i + batch_size < total_chunks:
                    time.sleep(1)  # Prevent overwhelming the IPFS node

            # Sort results by sequence number
            results.sort(key=lambda x: x['sequence_number'])
            return results

        except Exception as e:
            self.logger.error(f"Batch upload failed: {str(e)}")
            raise

    def get_chunk_status(self, cid: str) -> bool:
        """Check if a chunk is available on IPFS"""
        try:
            response = requests.head(f"{self.ipfs_gateway}/ipfs/{cid}")
            return response.status_code == 200
        except Exception:
            return False

    def upload_to_ipfs(self, file_path: str, metadata: Dict) -> Tuple[str, str]:
        """
        Upload file and metadata to IPFS
        Returns: Tuple(file_cid, metadata_cid)
        """
        try:
            # Upload the file first
            file_cid = self.add_file(file_path)
            self.logger.info(f"File uploaded to IPFS with CID: {file_cid}")
            
            # Create metadata with proper NFT format
            full_metadata = {
                'name': f'BlockSnap #{datetime.now().strftime("%Y%m%d%H%M%S")}',
                'description': 'A photo captured and authenticated using BlockSnap',
                'image': f'ipfs://{file_cid}',
                'image_url': self.get_ipfs_url(file_cid),
                'attributes': [
                    {
                        'trait_type': 'Platform',
                        'value': metadata.get('platform', 'Unknown')
                    },
                    {
                        'trait_type': 'Source',
                        'value': metadata.get('source', 'Unknown')
                    },
                    {
                        'trait_type': 'Timestamp',
                        'value': metadata.get('timestamp', datetime.now().isoformat())
                    }
                ]
            }
            
            # Upload metadata
            metadata_cid = self.add_json(full_metadata)
            self.logger.info(f"Metadata uploaded to IPFS with CID: {metadata_cid}")
            
            # Pin to Pinata if configured
            if self.use_pinata:
                self._pin_to_pinata(file_cid)
                self._pin_to_pinata(metadata_cid)
            
            return file_cid, metadata_cid
            
        except Exception as e:
            self.logger.error(f"Error uploading to IPFS: {str(e)}")
            raise

    def get_ipfs_url(self, cid: str) -> str:
        """Get the URL for an IPFS CID using the configured gateway"""
        if not cid:
            return ''
        return f"{self.ipfs_gateway}/ipfs/{cid}"

    def get_json(self, cid: str) -> dict:
        """Get JSON data from IPFS"""
        try:
            # If the CID is a full ipfs:// URL, extract just the CID
            if cid.startswith('ipfs://'):
                cid = cid.replace('ipfs://', '')
            # If the CID already contains an IPFS gateway URL, extract just the CID
            elif '/ipfs/' in cid:
                cid = cid.split('/ipfs/')[-1]
                
            response = requests.get(self.get_ipfs_url(cid))
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to get JSON from IPFS: {str(e)}")
            raise

    def verify_content(self, cid: str) -> bool:
        """Verify if content exists on IPFS"""
        try:
            response = requests.post(
                f"{self.ipfs_host}/api/v0/cat",
                params={'arg': cid}
            )
            response.raise_for_status()
            return True
        except Exception:
            return False

    def _pin_to_pinata(self, cid: str) -> None:
        """Pin a file to Pinata"""
        try:
            headers = {
                'pinata_api_key': self.pinata_api_key,
                'pinata_secret_api_key': self.pinata_secret_key
            }

            response = requests.post(
                'https://api.pinata.cloud/pinning/pinByHash',
                json={'hashToPin': cid},
                headers=headers
            )
            response.raise_for_status()
            self.logger.info(f"Successfully pinned CID to Pinata: {cid}")
        except Exception as e:
            self.logger.error(f"Error pinning to Pinata: {str(e)}")
            raise

    def add_json(self, json_data: dict) -> str:
        """Add JSON data to IPFS and return its CID"""
        try:
            # Convert dict to JSON string
            json_str = json.dumps(json_data)
            
            if self.use_pinata:
                # Use Pinata for JSON upload
                files = {
                    'file': ('metadata.json', json_str.encode('utf-8'), 'application/json')
                }
                headers = {
                    'pinata_api_key': self.pinata_api_key,
                    'pinata_secret_api_key': self.pinata_secret_key
                }
                
                response = requests.post(
                    'https://api.pinata.cloud/pinning/pinFileToIPFS',
                    files=files,
                    headers=headers
                )
                response.raise_for_status()
                
                result = response.json()
                cid = result['IpfsHash']
            else:
                # Use local IPFS node
                files = {
                    'file': ('metadata.json', json_str.encode('utf-8'), 'application/json')
                }
                
                response = requests.post(
                    f"{self.ipfs_host}/api/v0/add",
                    files=files
                )
                response.raise_for_status()
                
                result = response.json()
                cid = result['Hash']
            
            # Pin the file to ensure it persists
            self.pin_file(cid)
            self.logger.info(f"Successfully pinned metadata CID: {cid}")
            return cid
            
        except Exception as e:
            self.logger.error(f"Failed to add JSON to IPFS: {str(e)}")
            raise

    def calculate_cid(self, file_path: str) -> str:
        """
        Calculate the IPFS CID for a file without uploading it
        Returns: CID string
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            # Use the IPFS API to only calculate the hash without adding the file
            with open(file_path, 'rb') as f:
                files = {
                    'file': (os.path.basename(file_path), f)
                }
                
                response = requests.post(
                    f"{self.ipfs_host}/api/v0/add?only-hash=true",
                    files=files
                )
                response.raise_for_status()
                
                result = response.json()
                cid = result['Hash']
                
                self.logger.info(f"Calculated CID for file {file_path}: {cid}")
                return cid
                
        except Exception as e:
            self.logger.error(f"Failed to calculate CID: {str(e)}")
            raise

    def get_content(self, cid: str) -> Optional[bytes]:
        """Get content from IPFS by CID"""
        try:
            # Try local IPFS node first
            response = requests.post(
                f"{self.ipfs_host}/api/v0/cat",
                params={'arg': cid}
            )
            response.raise_for_status()
            return response.content
        except Exception as e:
            self.logger.warning(f"Failed to get content from local IPFS: {str(e)}")
            
            # Try public gateways
            gateways = [
                self.ipfs_gateway,
                'https://ipfs.io/ipfs/',
                'https://gateway.pinata.cloud/ipfs/',
                'https://cloudflare-ipfs.com/ipfs/',
                'https://ipfs.infura.io/ipfs/'
            ]
            
            for gateway in gateways:
                try:
                    # Ensure gateway URL ends with /ipfs/
                    if not gateway.endswith('/ipfs/'):
                        gateway = f"{gateway.rstrip('/')}/ipfs/"
                        
                    url = f"{gateway}{cid}"
                    response = requests.get(url, timeout=10)
                    
                    if response.status_code == 200:
                        self.logger.info(f"Retrieved content from gateway: {gateway}")
                        return response.content
                except Exception as gateway_error:
                    self.logger.debug(f"Failed to get content from gateway {gateway}: {str(gateway_error)}")
                    continue
            
            self.logger.error(f"Failed to get content for CID {cid} from any source")
            return None

if __name__ == "__main__":
    # Example usage
    handler = IPFSHandler()
    
    # Test file upload
    test_data = {"test": "data"}
    with open("test.json", "w") as f:
        json.dump(test_data, f)
    
    try:
        file_cid, metadata_cid = handler.upload_to_ipfs("test.json", test_data)
        print(f"File CID: {file_cid}")
        print(f"Metadata CID: {metadata_cid}")
    finally:
        os.remove("test.json")