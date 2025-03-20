#!/usr/bin/env python3

import os
import json
import logging
import requests
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import threading
import time
from dotenv import load_dotenv

load_dotenv()

class DistributedNode:
    """
    Manages cross-node communication and synchronization for BlockSnap.
    Allows media captured on one node to be verified by any other node in the network.
    """
    def __init__(self):
        # Generate a unique node ID if not already set
        self.node_id = os.getenv('NODE_ID', str(uuid.uuid4()))
        self.public_endpoint = os.getenv('PUBLIC_ENDPOINT', 'http://localhost:5000')
        self.discovery_service = os.getenv('DISCOVERY_SERVICE', 'http://localhost:5001')
        self.enable_p2p = os.getenv('ENABLE_P2P', 'true').lower() == 'true'
        
        # Set default timeout for all requests
        self.request_timeout = int(os.getenv('REQUEST_TIMEOUT', '30'))
        
        # Setup data directory
        self.data_dir = Path(os.getenv('DATA_DIR', 'node_data'))
        self.data_dir.mkdir(exist_ok=True, parents=True)
        
        # Setup registry files
        self.peers_file = self.data_dir / 'peers.json'
        self.media_registry_file = self.data_dir / 'media_registry.json'
        
        # Initialize registries
        self.peers = self._load_peers()
        self.media_registry = self._load_media_registry()
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
        
        # Start background tasks if P2P is enabled
        if self.enable_p2p:
            # Register with discovery service
            threading.Thread(target=self._register_with_discovery, daemon=True).start()
            
            # Start peer discovery
            threading.Thread(target=self._discover_peers_loop, daemon=True).start()
            
            # Start heartbeat
            threading.Thread(target=self._heartbeat_loop, daemon=True).start()
            
            self.logger.info(f"Distributed node initialized with ID: {self.node_id}")
        else:
            self.logger.info("Distributed node initialized in standalone mode (P2P disabled)")
    
    def _load_peers(self) -> Dict:
        """Load peers from file"""
        if self.peers_file.exists():
            try:
                with open(self.peers_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading peers: {str(e)}")
        return {}
    
    def _save_peers(self):
        """Save peers to file"""
        try:
            with open(self.peers_file, 'w') as f:
                json.dump(self.peers, f)
        except Exception as e:
            self.logger.error(f"Error saving peers: {str(e)}")
    
    def _load_media_registry(self) -> Dict:
        """Load media registry from file"""
        if self.media_registry_file.exists():
            try:
                with open(self.media_registry_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading media registry: {str(e)}")
        return {}
    
    def _save_media_registry(self):
        """Save media registry to file"""
        try:
            with open(self.media_registry_file, 'w') as f:
                json.dump(self.media_registry, f)
        except Exception as e:
            self.logger.error(f"Error saving media registry: {str(e)}")
    
    def _register_with_discovery(self):
        """Register this node with the discovery service"""
        if not self.enable_p2p:
            return
            
        try:
            node_data = {
                'node_id': self.node_id,
                'endpoint': self.public_endpoint,
                'capabilities': {
                    'verify': True,
                    'broadcast': True
                }
            }
            
            response = requests.post(
                f"{self.discovery_service}/register",
                json=node_data,
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                self.logger.info(f"Registered with discovery service at {self.discovery_service}")
            else:
                self.logger.warning(f"Failed to register with discovery service: {response.text}")
                
        except Exception as e:
            self.logger.error(f"Error registering with discovery service: {str(e)}")
    
    def _discover_peers_loop(self):
        """Periodically discover peers from the discovery service"""
        if not self.enable_p2p:
            return
            
        while True:
            try:
                # Sleep first to allow initial setup
                time.sleep(60)  # Check every minute
                
                # Get nodes from discovery service
                response = requests.get(
                    f"{self.discovery_service}/nodes",
                    timeout=self.request_timeout
                )
                
                if response.status_code == 200:
                    nodes = response.json()
                    
                    # Update peers
                    for node in nodes:
                        node_id = node.get('node_id')
                        
                        # Skip self
                        if node_id == self.node_id:
                            continue
                            
                        # Add or update peer
                        self.peers[node_id] = {
                            'node_id': node_id,
                            'endpoint': node.get('endpoint'),
                            'capabilities': node.get('capabilities', {}),
                            'last_seen': datetime.now().isoformat()
                        }
                    
                    self._save_peers()
                    self.logger.info(f"Discovered {len(nodes)} nodes, updated {len(self.peers)} peers")
                else:
                    self.logger.warning(f"Failed to discover peers: {response.text}")
                    
            except Exception as e:
                self.logger.error(f"Error in peer discovery: {str(e)}")
    
    def _heartbeat_loop(self):
        """Periodically send heartbeat to discovery service"""
        if not self.enable_p2p:
            return
            
        while True:
            try:
                # Sleep first to allow initial setup
                time.sleep(300)  # Heartbeat every 5 minutes
                
                # Send heartbeat
                response = requests.post(
                    f"{self.discovery_service}/heartbeat/{self.node_id}",
                    timeout=self.request_timeout
                )
                
                if response.status_code == 200:
                    self.logger.debug(f"Sent heartbeat to discovery service")
                else:
                    self.logger.warning(f"Failed to send heartbeat: {response.text}")
                    # Re-register if heartbeat fails
                    self._register_with_discovery()
                    
            except Exception as e:
                self.logger.error(f"Error in heartbeat: {str(e)}")
                # Re-register if heartbeat fails
                self._register_with_discovery()
    
    def register_media(self, media_info: Dict) -> bool:
        """Register media in local registry and broadcast to peers"""
        try:
            # Validate required fields
            tx_hash = media_info.get('tx_hash')
            if not tx_hash:
                self.logger.warning("Attempted to register media without transaction hash")
                return False
            
            # Ensure media_type is consistent (handle both 'type' and 'media_type' fields)
            if 'type' in media_info and 'media_type' not in media_info:
                media_info['media_type'] = media_info['type']
            elif 'media_type' in media_info and 'type' not in media_info:
                media_info['type'] = media_info['media_type']
            
            # Add to registry with all metadata preserved
            self.media_registry[tx_hash] = {
                **media_info,
                'registered_by': self.node_id,
                'registered_at': datetime.now().isoformat()
            }
            
            self._save_media_registry()
            self.logger.info(f"Registered media with transaction hash {tx_hash} of type {media_info.get('media_type', 'unknown')}")
            
            # Broadcast to peers if P2P is enabled
            if self.enable_p2p:
                threading.Thread(target=self._broadcast_media, args=(media_info,), daemon=True).start()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error registering media: {str(e)}")
            return False
    
    def _broadcast_media(self, media_info: Dict):
        """Broadcast media to peers"""
        if not self.enable_p2p:
            return
            
        for peer_id, peer in self.peers.items():
            try:
                # Check if peer has broadcast capability
                if not peer.get('capabilities', {}).get('broadcast', False):
                    continue
                    
                endpoint = peer.get('endpoint')
                if not endpoint:
                    continue
                    
                # Send media info to peer
                response = requests.post(
                    f"{endpoint}/api/media/broadcast",
                    json=media_info,
                    timeout=self.request_timeout
                )
                
                if response.status_code == 200:
                    self.logger.info(f"Broadcast media to peer {peer_id}")
                else:
                    self.logger.warning(f"Failed to broadcast media to peer {peer_id}: {response.text}")
                    
            except Exception as e:
                self.logger.error(f"Error broadcasting media to peer {peer_id}: {str(e)}")
    
    def get_registered_media(self, media_type: Optional[str] = None, owner: Optional[str] = None) -> List[Dict]:
        """Get media from local registry with optional filters"""
        try:
            results = []
            
            for tx_hash, media_info in self.media_registry.items():
                # Apply filters
                if media_type and media_info.get('type') != media_type:
                    continue
                    
                if owner and media_info.get('owner') != owner:
                    continue
                    
                results.append(media_info)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error getting registered media: {str(e)}")
            return []
    
    def verify_media_across_network(self, tx_hash: str) -> Dict:
        """Verify media using transaction hash across the network"""
        # Check local registry first
        if tx_hash in self.media_registry:
            media_info = self.media_registry[tx_hash]
            # Ensure we're returning all available metadata
            result = media_info.get('verification_result', media_info)
            self.logger.info(f"Found transaction {tx_hash} in local registry")
            return {
                'verified': True,
                'media_info': result,
                'source': 'local_registry'
            }
        
        # If P2P is disabled, return not verified
        if not self.enable_p2p:
            self.logger.warning("P2P is disabled, cannot verify across network")
            return {
                'verified': False,
                'message': 'P2P is disabled, cannot verify across network'
            }
        
        # Query peers
        self.logger.info(f"Querying {len(self.peers)} peers for transaction {tx_hash}")
        for peer_id, peer in self.peers.items():
            try:
                # Check if peer has verify capability
                if not peer.get('capabilities', {}).get('verify', False):
                    continue
                    
                endpoint = peer.get('endpoint')
                if not endpoint:
                    continue
                    
                # Query peer for verification
                self.logger.info(f"Querying peer {peer_id} at {endpoint} for transaction {tx_hash}")
                response = requests.get(
                    f"{endpoint}/api/verify/tx/{tx_hash}",
                    timeout=self.request_timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Check if the peer verified the transaction
                    if result.get('exists_on_blockchain', False):
                        self.logger.info(f"Peer {peer_id} verified transaction {tx_hash}")
                        # Cache the result locally with all metadata
                        media_type = result.get('media_type', 'unknown')
                        
                        # Prepare media info with all available metadata
                        media_data = {
                            'tx_hash': tx_hash,
                            'media_type': media_type,
                            'owner': result.get('owner'),
                            'cid': result.get('cid'),
                            'token_id': result.get('token_id'),
                            'session_id': result.get('session_id'),
                            'sequence_number': result.get('sequence_number'),
                            'metadata_uri': result.get('metadata_uri'),
                            'function': result.get('function'),
                            'message': result.get('message'),
                            'verification_result': result
                        }
                        
                        # Register the complete media info
                        self.register_media(media_data)
                        
                        return {
                            'verified': True,
                            'media_info': result,
                            'source': f'peer_{peer_id}'
                        }
            except Exception as e:
                self.logger.error(f"Error verifying with peer {peer_id}: {str(e)}")
                continue
        
        # Not found anywhere
        self.logger.warning(f"Transaction {tx_hash} not found on any peer")
        return {
            'verified': False,
            'message': 'Transaction not found on any peer'
        }

if __name__ == "__main__":
    # Example usage
    node = DistributedNode()
    print(f"Node ID: {node.node_id}")
