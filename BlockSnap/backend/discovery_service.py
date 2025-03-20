#!/usr/bin/env python3

import os
import json
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
from dotenv import load_dotenv
import threading
import time

load_dotenv()

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DiscoveryService:
    """
    A simple discovery service for BlockSnap nodes.
    Allows nodes to register themselves and discover other nodes in the network.
    """
    def __init__(self):
        self.data_dir = Path(os.getenv('DATA_DIR', 'discovery_data'))
        self.data_dir.mkdir(exist_ok=True, parents=True)
        self.nodes_file = self.data_dir / 'nodes.json'
        self.nodes = self._load_nodes()
        self.node_timeout = int(os.getenv('NODE_TIMEOUT', '3600'))  # Default 1 hour
        
        # Start background cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
    
    def _load_nodes(self) -> Dict:
        """Load registered nodes from file"""
        if self.nodes_file.exists():
            try:
                with open(self.nodes_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading nodes: {str(e)}")
        return {}
    
    def _save_nodes(self):
        """Save registered nodes to file"""
        try:
            with open(self.nodes_file, 'w') as f:
                json.dump(self.nodes, f)
        except Exception as e:
            logger.error(f"Error saving nodes: {str(e)}")
    
    def register_node(self, node_data: Dict) -> bool:
        """Register a node with the discovery service"""
        try:
            node_id = node_data.get('node_id')
            if not node_id:
                logger.warning("Attempted to register node without node_id")
                return False
                
            endpoint = node_data.get('endpoint')
            if not endpoint:
                logger.warning(f"Node {node_id} attempted to register without endpoint")
                return False
            
            # Update or add node
            self.nodes[node_id] = {
                'node_id': node_id,
                'endpoint': endpoint,
                'capabilities': node_data.get('capabilities', {}),
                'timestamp': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat()
            }
            
            self._save_nodes()
            logger.info(f"Registered node {node_id} at {endpoint}")
            return True
            
        except Exception as e:
            logger.error(f"Error registering node: {str(e)}")
            return False
    
    def get_nodes(self) -> List[Dict]:
        """Get all registered nodes"""
        # Filter out expired nodes
        active_nodes = []
        cutoff_time = datetime.now() - timedelta(seconds=self.node_timeout)
        
        for node_id, node in self.nodes.items():
            try:
                last_seen = datetime.fromisoformat(node.get('last_seen', '2000-01-01T00:00:00'))
                if last_seen > cutoff_time:
                    active_nodes.append(node)
            except Exception:
                # Skip nodes with invalid timestamps
                continue
        
        return active_nodes
    
    def heartbeat(self, node_id: str) -> bool:
        """Update the last_seen timestamp for a node"""
        if node_id in self.nodes:
            try:
                self.nodes[node_id]['last_seen'] = datetime.now().isoformat()
                self._save_nodes()
                return True
            except Exception as e:
                logger.error(f"Error updating heartbeat: {str(e)}")
        return False
    
    def _cleanup_loop(self):
        """Background thread to clean up expired nodes"""
        while True:
            try:
                # Sleep first to allow initial setup
                time.sleep(300)  # Check every 5 minutes
                
                # Remove expired nodes
                cutoff_time = datetime.now() - timedelta(seconds=self.node_timeout)
                expired_nodes = []
                
                for node_id, node in self.nodes.items():
                    try:
                        last_seen = datetime.fromisoformat(node.get('last_seen', '2000-01-01T00:00:00'))
                        if last_seen < cutoff_time:
                            expired_nodes.append(node_id)
                    except Exception:
                        # Invalid timestamp, consider it expired
                        expired_nodes.append(node_id)
                
                # Remove expired nodes
                for node_id in expired_nodes:
                    self.nodes.pop(node_id, None)
                    logger.info(f"Removed expired node {node_id}")
                
                if expired_nodes:
                    self._save_nodes()
                    
            except Exception as e:
                logger.error(f"Error in cleanup loop: {str(e)}")

# Initialize discovery service
discovery_service = DiscoveryService()

@app.route('/register', methods=['POST'])
def register():
    """Register a node with the discovery service"""
    try:
        node_data = request.get_json()
        success = discovery_service.register_node(node_data)
        
        if success:
            return jsonify({'status': 'success', 'message': 'Node registered successfully'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to register node'}), 400
            
    except Exception as e:
        logger.error(f"Error in register endpoint: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/nodes', methods=['GET'])
def get_nodes():
    """Get all registered nodes"""
    try:
        nodes = discovery_service.get_nodes()
        return jsonify(nodes)
    except Exception as e:
        logger.error(f"Error in get_nodes endpoint: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/heartbeat/<node_id>', methods=['POST'])
def heartbeat(node_id):
    """Update the last_seen timestamp for a node"""
    try:
        success = discovery_service.heartbeat(node_id)
        
        if success:
            return jsonify({'status': 'success', 'message': 'Heartbeat updated'})
        else:
            return jsonify({'status': 'error', 'message': 'Node not found'}), 404
            
    except Exception as e:
        logger.error(f"Error in heartbeat endpoint: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv('DISCOVERY_PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
