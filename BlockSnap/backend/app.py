#!/usr/bin/env python3

from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import logging
from pathlib import Path
import os
import platform
from dotenv import load_dotenv
from datetime import datetime
import json
import cv2
import time

# Import our custom modules
try:
    # Try to import Raspberry Pi specific modules
    from hardware.camera import BlockSnapCamera
    IS_RASPBERRY_PI = True
except (ImportError, RuntimeError):
    # If import fails, use mock camera
    from hardware.mock_camera import MockCamera
    IS_RASPBERRY_PI = False

from backend.ipfs_handler import IPFSHandler
from backend.blockchain_handler import BlockchainHandler
from backend.dashcam_manager import DashcamManager  # Import DashcamManager

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
CORS(app)  # Enable CORS for all routes

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize components
try:
    # Initialize camera based on platform
    if IS_RASPBERRY_PI:
        logger.info("Initializing Raspberry Pi camera")
        camera = BlockSnapCamera()
    else:
        logger.info("Initializing mock camera for testing")
        camera = MockCamera()
    
    ipfs_handler = IPFSHandler()
    blockchain_handler = BlockchainHandler()
    dashcam_manager = DashcamManager()  # Initialize dashcam manager
    logger.info("All components initialized successfully")
except Exception as e:
    logger.error(f"Error initializing components: {str(e)}")
    raise

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'platform': 'Raspberry Pi' if IS_RASPBERRY_PI else 'Test Environment'
    })

@app.route('/capture', methods=['POST'])
def capture_photo():
    """
    Capture a photo and store it on IPFS
    Required JSON body: {
        "wallet_address": "0x...",
        "image_data": "base64_encoded_image_data"
    }
    """
    try:
        # Validate request
        data = request.get_json()
        if not data or 'wallet_address' not in data or 'image_data' not in data:
            return jsonify({'error': 'wallet_address and image_data are required'}), 400
        
        wallet_address = data['wallet_address']
        image_data = data['image_data']
        
        # Save base64 image data to a temporary file
        import base64
        import tempfile
        
        # Remove the data URL prefix if present
        if image_data.startswith('data:image'):
            image_data = image_data.split(',')[1]
        
        # Decode base64 and save to temp file
        image_bytes = base64.b64decode(image_data)
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
            temp_file.write(image_bytes)
            filepath = temp_file.name
        
        # Create metadata
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'platform': platform.system(),
            'source': 'web_capture'
        }
        
        # Upload to IPFS
        file_cid, metadata_cid = ipfs_handler.upload_to_ipfs(filepath, metadata)
        
        # Clean up temp file
        os.unlink(filepath)
        
        # Create metadata URI (IPFS gateway URL)
        metadata_uri = ipfs_handler.get_ipfs_url(metadata_cid)
        
        # Mint NFT
        tx_hash, token_id = blockchain_handler.mint_photo_nft(
            wallet_address,
            file_cid,
            metadata_uri
        )
        
        # Save to local cache
        try:
            cache_dir = Path("/home/hrithik/raspi_old/BlockSnap/captures/nft_cache")
            cache_dir.mkdir(exist_ok=True, parents=True)
            wallet_cache_file = cache_dir / f"{wallet_address.lower()}.json"
            
            # Create NFT object
            nft = {
                'tokenId': token_id,
                'name': f'BlockSnap #{token_id}',
                'description': 'A photo captured using BlockSnap',
                'image': ipfs_handler.get_ipfs_url(file_cid),
                'image_cid': file_cid,
                'metadata_uri': metadata_uri,
                'transaction_hash': tx_hash,
                'metadata': metadata,
                'type': 'photo',
                'source': 'local_cache',
                'timestamp': datetime.now().isoformat()
            }
            
            # Read existing cache if it exists
            cached_nfts = []
            if wallet_cache_file.exists():
                try:
                    with open(wallet_cache_file, 'r') as f:
                        cached_nfts = json.load(f)
                except Exception as e:
                    app.logger.error(f"Error reading cache file: {str(e)}")
            
            # Add new NFT to cache
            cached_nfts.append(nft)
            
            # Write updated cache
            with open(wallet_cache_file, 'w') as f:
                json.dump(cached_nfts, f)
                
            app.logger.info(f"Saved NFT {token_id} to local cache for {wallet_address}")
        except Exception as cache_error:
            app.logger.error(f"Error saving to cache: {str(cache_error)}")
        
        # Prepare response
        response = {
            'status': 'success',
            'data': {
                'file_cid': file_cid,
                'metadata_cid': metadata_cid,
                'token_id': token_id,
                'transaction_hash': tx_hash,
                'metadata_uri': metadata_uri,
                'image_url': ipfs_handler.get_ipfs_url(file_cid)
            }
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in capture endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/verify/<image_cid>', methods=['GET'])
def verify_photo(image_cid):
    """Verify a photo's authenticity and ownership"""
    try:
        # Check if content exists on IPFS
        ipfs_exists = ipfs_handler.verify_content(image_cid)
        
        # Check blockchain records
        blockchain_exists, owner = blockchain_handler.verify_photo(image_cid)
        
        response = {
            'exists_on_ipfs': ipfs_exists,
            'exists_on_blockchain': blockchain_exists,
            'owner': owner if blockchain_exists else None,
            'ipfs_url': ipfs_handler.get_ipfs_url(image_cid) if ipfs_exists else None
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in verify endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/token/<int:token_id>', methods=['GET'])
def get_token_info(token_id):
    """Get information about a specific token"""
    try:
        metadata_uri = blockchain_handler.get_token_uri(token_id)
        image_cid = blockchain_handler.get_image_cid(token_id)
        
        response = {
            'token_id': token_id,
            'metadata_uri': metadata_uri,
            'image_cid': image_cid,
            'image_url': ipfs_handler.get_ipfs_url(image_cid)
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in token info endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/nfts/<wallet_address>', methods=['GET'])
def get_nfts_by_wallet(wallet_address):
    """Get all NFTs owned by a wallet address"""
    nfts = []
    error_message = None
    
    try:
        # First, try to get NFTs from local cache if it exists
        cache_dir = Path("/home/hrithik/raspi_old/BlockSnap/captures/nft_cache")
        cache_dir.mkdir(exist_ok=True, parents=True)
        wallet_cache_file = cache_dir / f"{wallet_address.lower()}.json"
        
        cached_nfts = []
        if wallet_cache_file.exists():
            try:
                with open(wallet_cache_file, 'r') as f:
                    cached_nfts = json.load(f)
                app.logger.info(f"Loaded {len(cached_nfts)} NFTs from cache for {wallet_address}")
                nfts.extend(cached_nfts)
            except Exception as e:
                app.logger.error(f"Error reading NFT cache file: {str(e)}")
        
        # Then try to get NFTs from blockchain
        try:
            # Get the event signature for PhotoMinted
            event_signature_hash = blockchain_handler.w3.keccak(text="PhotoMinted(uint256,address,string,string)").hex()
            
            # Try with a smaller block range first (last 1000 blocks)
            try:
                current_block = blockchain_handler.w3.eth.block_number
                from_block = max(0, current_block - 1000)
                
                logs = blockchain_handler.w3.eth.get_logs({
                    'address': blockchain_handler.contract.address,
                    'topics': [event_signature_hash],
                    'fromBlock': from_block,
                    'toBlock': 'latest'
                })
                app.logger.info(f"Found {len(logs)} PhotoMinted events in last 1000 blocks")
            except Exception as large_range_error:
                app.logger.warning(f"Error getting logs for large range: {str(large_range_error)}")
                # Try with an even smaller range (last 100 blocks)
                current_block = blockchain_handler.w3.eth.block_number
                from_block = max(0, current_block - 100)
                
                logs = blockchain_handler.w3.eth.get_logs({
                    'address': blockchain_handler.contract.address,
                    'topics': [event_signature_hash],
                    'fromBlock': from_block,
                    'toBlock': 'latest'
                })
                app.logger.info(f"Found {len(logs)} PhotoMinted events in last 100 blocks")
            
            blockchain_nfts = []
            # Check each token from logs
            for log in logs:
                try:
                    # Decode the log data
                    decoded_log = blockchain_handler.contract.events.PhotoMinted().process_log(log)
                    token_id = decoded_log['args']['tokenId']
                    
                    # Check if this wallet owns the token
                    owner = blockchain_handler.contract.functions.ownerOf(token_id).call()
                    if owner.lower() == wallet_address.lower():
                        # Get token details
                        metadata_uri = blockchain_handler.get_token_uri(token_id)
                        image_cid = blockchain_handler.get_image_cid(token_id)
                        
                        # Get transaction hash from the event log
                        transaction_hash = decoded_log.transactionHash.hex()
                        
                        # Get metadata from IPFS if available
                        try:
                            metadata = ipfs_handler.get_json(metadata_uri)
                        except:
                            metadata = {
                                'name': f'BlockSnap #{token_id}',
                                'description': 'A photo captured using BlockSnap'
                            }
                        
                        # Determine if this is a video based on metadata attributes
                        is_video = False
                        if metadata.get('attributes'):
                            for attr in metadata['attributes']:
                                if attr.get('trait_type') == 'Content Type' and attr.get('value') == 'video':
                                    is_video = True
                                    break
                        
                        nft = {
                            'tokenId': token_id,
                            'name': metadata.get('name', f'BlockSnap #{token_id}'),
                            'description': metadata.get('description', 'A photo captured using BlockSnap'),
                            'image': ipfs_handler.get_ipfs_url(image_cid),
                            'image_cid': image_cid,
                            'metadata_uri': metadata_uri,
                            'transaction_hash': transaction_hash,
                            'metadata': metadata,  # Include full metadata for frontend filtering
                            'type': 'video' if is_video else 'photo',  # Add explicit type field
                            'source': 'blockchain'
                        }
                        blockchain_nfts.append(nft)
                        app.logger.info(f"Found NFT {token_id} owned by {wallet_address}")
                except Exception as e:
                    app.logger.error(f"Error processing log: {str(e)}")
                    continue
            
            # Add blockchain NFTs to the list, avoiding duplicates
            existing_token_ids = {nft['tokenId'] for nft in nfts}
            for nft in blockchain_nfts:
                if nft['tokenId'] not in existing_token_ids:
                    nfts.append(nft)
                    existing_token_ids.add(nft['tokenId'])
        except Exception as blockchain_error:
            app.logger.error(f"Error getting NFTs from blockchain: {str(blockchain_error)}")
            error_message = f"Error retrieving NFTs from blockchain: {str(blockchain_error)}"
        
        # Sort NFTs by timestamp if available, otherwise by tokenId
        def get_sort_key(nft):
            if 'metadata' in nft and 'timestamp' in nft['metadata']:
                return nft['metadata']['timestamp']
            return str(nft['tokenId'])
        
        nfts.sort(key=get_sort_key, reverse=True)  # Newest first
        
        response = {'nfts': nfts}
        if error_message:
            response['error'] = error_message
        
        return jsonify(response)
        
    except Exception as e:
        app.logger.error(f"Error in get NFTs endpoint: {str(e)}")
        # Return an empty list with error message instead of 500 error
        return jsonify({'nfts': [], 'error': str(e)})

@app.route('/api/dashcam/start', methods=['POST'])
def start_dashcam():
    """Start dashcam recording"""
    try:
        success = dashcam_manager.start_recording()
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Recording started',
                'session_id': dashcam_manager.session_id
            })
        return jsonify({
            'status': 'error',
            'message': 'Failed to start recording'
        }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/dashcam/stop', methods=['POST'])
def stop_dashcam():
    """Stop dashcam recording"""
    try:
        dashcam_manager.stop_recording()
        return jsonify({
            'status': 'success',
            'message': 'Recording stopped'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/dashcam/status', methods=['GET'])
def get_dashcam_status():
    """Get dashcam status"""
    try:
        status = dashcam_manager.get_status()
        return jsonify({
            'status': 'success',
            'data': status
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/dashcam/preview', methods=['GET'])
def get_preview_stream():
    """Get video preview stream"""
    try:
        def generate_frames():
            while dashcam_manager.is_recording:
                frame = dashcam_manager.recorder.get_preview_frame()
                if frame is not None:
                    # Encode frame to JPEG
                    ret, buffer = cv2.imencode('.jpg', frame)
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                time.sleep(1/30)  # 30 FPS

        return Response(
            generate_frames(),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )
    except Exception as e:
        app.logger.error(f"Error in preview stream: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashcam/latest-chunk', methods=['GET'])
def get_latest_chunk():
    """Get latest recorded chunk URL"""
    try:
        if not dashcam_manager.is_recording:
            return jsonify({
                'status': 'error',
                'message': 'Not recording'
            }), 400

        latest = dashcam_manager.get_latest_chunk()
        if latest:
            return jsonify({
                'status': 'success',
                'data': {
                    'video_url': f"{ipfs_handler.ipfs_gateway}/ipfs/{latest['video_cid']}",
                    'metadata_url': f"{ipfs_handler.ipfs_gateway}/ipfs/{latest['metadata_cid']}",
                    'sequence_number': latest['sequence_number']
                }
            })
        return jsonify({
            'status': 'error',
            'message': 'No chunks available'
        }), 404
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/dashcam/upload', methods=['POST'])
def upload_dashcam_video():
    video_path = None
    try:
        if 'video' not in request.files:
            return jsonify({'error': 'No video file provided'}), 400
            
        video_file = request.files['video']
        wallet_address = request.form.get('wallet_address')
        sequence_number = int(request.form.get('sequence_number', 0))
        session_id = request.form.get('session_id')
        is_first_chunk = request.form.get('is_first_chunk') == 'true'
        is_last_chunk = request.form.get('is_last_chunk') == 'true'
        
        if not video_file.filename or not wallet_address:
            return jsonify({'error': 'Missing required data'}), 400

        # Validate wallet address format
        if not wallet_address.startswith('0x') or len(wallet_address) != 42:
            return jsonify({'error': 'Invalid wallet address format'}), 400

        # Create uploads directory if it doesn't exist
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        # Save video file locally with unique name
        timestamp = int(time.time())
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], f'dashcam_{timestamp}.webm')
        video_file.save(video_path)
        
        # Start new session if this is the first chunk
        tx_hash = ""
        if is_first_chunk:
            session_id, tx_hash = blockchain_handler.start_video_session()
            logger.info(f"Started new video session: {session_id} with tx hash: {tx_hash}")
        elif not session_id:
            logger.error("Missing session_id for non-first chunk")
            return jsonify({'error': 'Missing session_id for non-first chunk'}), 400
        else:
            try:
                session_id = int(session_id)
                # Verify session exists and is active - skip this check as it might fail with BuildBear
                # Just log a warning instead
                try:
                    if not blockchain_handler.contract.functions.isSessionActive(session_id).call():
                        logger.warning(f"Session {session_id} is not active, but proceeding anyway")
                except Exception as session_check_error:
                    logger.warning(f"Failed to check if session {session_id} is active: {str(session_check_error)}")
            except ValueError:
                logger.error(f"Invalid session_id format: {session_id}")
                return jsonify({'error': 'Invalid session_id format'}), 400
        
        # Upload to IPFS and get CID
        video_cid = ipfs_handler.add_file(video_path)
        if not video_cid:
            raise Exception("Failed to upload to IPFS")
            
        # Create metadata for this chunk
        metadata = {
            "timestamp": timestamp,
            "sequence_number": sequence_number,
            "source": "dashcam",
            "content_type": "video/webm",
            "video_url": f"ipfs://{video_cid}",
            "session_id": session_id
        }
        metadata_cid = ipfs_handler.add_json(metadata)
        
        # Add chunk to session
        chunk_success, chunk_tx_hash = blockchain_handler.add_video_chunk(
            session_id,
            sequence_number,
            video_cid,
            metadata_cid,
            timestamp
        )
        
        if chunk_success:
            logger.info(f"Added video chunk {sequence_number} to session {session_id} with tx hash: {chunk_tx_hash}")
            tx_hash = chunk_tx_hash  # Update tx_hash for this operation
        else:
            logger.warning(f"Failed to add chunk to blockchain, but continuing with local processing")
        
        # End session if this is the last chunk
        end_tx_hash = ""
        if is_last_chunk:
            end_success, end_tx_hash = blockchain_handler.end_video_session(session_id)
            if end_success:
                logger.info(f"Ended video session: {session_id} with tx hash: {end_tx_hash}")
                tx_hash = end_tx_hash  # Update tx_hash for this operation
            else:
                logger.warning(f"Failed to end session in blockchain, but continuing with local processing")
        
        # Save to local cache
        try:
            cache_dir = Path("/home/hrithik/raspi_old/BlockSnap/captures/video_cache")
            cache_dir.mkdir(exist_ok=True, parents=True)
            session_cache_file = cache_dir / f"session_{session_id}.json"
            
            # Create chunk object
            chunk = {
                'sequence_number': sequence_number,
                'video_cid': video_cid,
                'metadata_cid': metadata_cid,
                'timestamp': timestamp,
                'video_url': f"https://ipfs.io/ipfs/{video_cid}",
                'tx_hash': chunk_tx_hash  # Store transaction hash for this chunk
            }
            
            # Read existing cache if it exists
            session_data = {
                'id': session_id,
                'owner': wallet_address,
                'chunks': [],
                'start_time': timestamp,
                'tx_hash': tx_hash,  # Store transaction hash for session start
                'blockchain_verified': bool(tx_hash)  # Flag to indicate if this is verified on blockchain
            }
            
            if session_cache_file.exists():
                try:
                    with open(session_cache_file, 'r') as f:
                        session_data = json.load(f)
                        
                    # Update transaction hash if we have a new one
                    if tx_hash and not session_data.get('tx_hash'):
                        session_data['tx_hash'] = tx_hash
                        session_data['blockchain_verified'] = True
                        
                    # Update end transaction hash if this is the last chunk
                    if is_last_chunk and end_tx_hash:
                        session_data['end_tx_hash'] = end_tx_hash
                except Exception as e:
                    logger.error(f"Error reading cache file: {str(e)}")
            
            # Add new chunk to cache
            session_data['chunks'].append(chunk)
            
            # Write updated cache
            with open(session_cache_file, 'w') as f:
                json.dump(session_data, f)
                
            logger.info(f"Saved video chunk {sequence_number} to local cache for session {session_id}")
        except Exception as cache_error:
            logger.error(f"Error saving to cache: {str(cache_error)}")
        
        # Clean up local file after successful upload
        if os.path.exists(video_path):
            os.remove(video_path)
            logger.info(f"Cleaned up local file: {video_path}")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'sequence_number': sequence_number,
            'video_cid': video_cid,
            'metadata_cid': metadata_cid,
            'tx_hash': tx_hash  # Return transaction hash to frontend
        })
    except Exception as e:
        logger.error(f"Error uploading dashcam video: {str(e)}")
        # Clean up local file if it exists
        if video_path and os.path.exists(video_path):
            os.remove(video_path)
            logger.info(f"Cleaned up local file after error: {video_path}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/video-sessions/<wallet_address>', methods=['GET'])
def get_video_sessions(wallet_address):
    """Get all video sessions for a wallet"""
    sessions = []
    error_message = None
    
    try:
        # First, try to get sessions from local cache
        cache_dir = Path("/home/hrithik/raspi_old/BlockSnap/captures/video_cache")
        if cache_dir.exists():
            # Find all session files for this wallet
            app.logger.info(f"Looking for video sessions in cache directory: {cache_dir}")
            for cache_file in cache_dir.glob("session_*.json"):
                try:
                    with open(cache_file, 'r') as f:
                        session_data = json.load(f)
                        
                    # Check if this session belongs to the wallet
                    if session_data.get('owner', '').lower() == wallet_address.lower():
                        app.logger.info(f"Loaded session {session_data.get('id')} from cache for {wallet_address}")
                        
                        # Ensure transaction hash is included
                        if 'tx_hash' not in session_data:
                            session_data['tx_hash'] = ""
                            
                        # Check if each chunk has a transaction hash
                        for chunk in session_data.get('chunks', []):
                            if 'tx_hash' not in chunk:
                                chunk['tx_hash'] = ""
                                
                        sessions.append(session_data)
                except Exception as cache_error:
                    app.logger.error(f"Error reading cache file {cache_file}: {str(cache_error)}")
            
            app.logger.info(f"Found {len(sessions)} video sessions in cache for {wallet_address}")
        else:
            app.logger.warning(f"Cache directory {cache_dir} does not exist")
        
        # Then try to get sessions from blockchain
        try:
            blockchain_sessions = blockchain_handler.get_video_sessions(wallet_address)
            
            # Add blockchain sessions to the list, avoiding duplicates
            existing_session_ids = {session['id'] for session in sessions}
            for session in blockchain_sessions:
                if session['id'] not in existing_session_ids:
                    # Ensure transaction hash is included
                    if 'tx_hash' not in session:
                        session['tx_hash'] = ""
                        
                    # Check if each chunk has a transaction hash
                    for chunk in session.get('chunks', []):
                        if 'tx_hash' not in chunk:
                            chunk['tx_hash'] = ""
                            
                    sessions.append(session)
                    existing_session_ids.add(session['id'])
                else:
                    # Merge blockchain data with cache data for this session
                    for cached_session in sessions:
                        if cached_session['id'] == session['id']:
                            # Update transaction hash if missing in cache but present in blockchain
                            if not cached_session.get('tx_hash') and session.get('tx_hash'):
                                cached_session['tx_hash'] = session['tx_hash']
                                
                            # Update blockchain_verified flag
                            cached_session['blockchain_verified'] = True
                            
                            # Merge chunks, avoiding duplicates
                            existing_chunk_seq = {chunk['sequence_number'] for chunk in cached_session.get('chunks', [])}
                            for chunk in session.get('chunks', []):
                                if chunk['sequence_number'] not in existing_chunk_seq:
                                    cached_session['chunks'].append(chunk)
                                    existing_chunk_seq.add(chunk['sequence_number'])
                            break
                    
            app.logger.info(f"Retrieved {len(blockchain_sessions)} sessions from blockchain for {wallet_address}")
        except Exception as blockchain_error:
            app.logger.error(f"Error getting sessions from blockchain: {str(blockchain_error)}")
            error_message = f"Error retrieving sessions from blockchain: {str(blockchain_error)}"
        
        # Enhance session data with IPFS metadata
        for session in sessions:
            try:
                for chunk in session.get('chunks', []):
                    try:
                        # Get metadata from IPFS if not already present
                        if not chunk.get('location') and 'metadata_cid' in chunk:
                            metadata = ipfs_handler.get_json(chunk['metadata_cid'])
                            chunk.update(metadata)
                    except Exception as metadata_error:
                        app.logger.warning(f"Failed to get metadata for chunk: {str(metadata_error)}")
                        # Add minimal metadata to avoid frontend errors
                        chunk.update({
                            'timestamp': chunk.get('timestamp', 0),
                            'location': 'Unknown',
                            'device': 'Unknown'
                        })
                    
                    # Add IPFS gateway URL if not already present
                    if not chunk.get('video_url') and 'video_cid' in chunk:
                        chunk['video_url'] = f"https://ipfs.io/ipfs/{chunk['video_cid']}"
            except Exception as session_error:
                app.logger.warning(f"Error processing session {session.get('id')}: {str(session_error)}")
        
        # Sort sessions by start_time (newest first)
        sessions.sort(key=lambda s: s.get('start_time', 0), reverse=True)
        
        response = {
            'success': True,
            'sessions': sessions
        }
        
        if error_message:
            response['error'] = error_message
            
        return jsonify(response)
        
    except Exception as e:
        app.logger.error(f"Failed to get video sessions: {str(e)}")
        # Return 200 with empty sessions instead of 500 error
        return jsonify({
            'success': False,
            'sessions': sessions,
            'error': str(e)
        })

@app.route('/verify/tx/<tx_hash>', methods=['GET'])
def verify_by_transaction(tx_hash):
    """Verify a media's authenticity and ownership by transaction hash"""
    try:
        # Check if transaction exists on the blockchain
        tx_exists, media_info = blockchain_handler.verify_by_transaction(tx_hash)
        
        if not tx_exists:
            return jsonify({
                'exists_on_blockchain': False,
                'exists_on_ipfs': False,
                'tx_hash': tx_hash,
                'message': 'Transaction not found on blockchain'
            })
        
        # If transaction exists, extract the IPFS CID and check if content exists on IPFS
        ipfs_exists = False
        ipfs_url = None
        owner = None
        media_type = 'unknown'
        
        if media_info:
            owner = media_info.get('owner')
            media_type = media_info.get('type', 'unknown')
            
            # Check IPFS if we have a CID
            if 'cid' in media_info:
                try:
                    ipfs_exists = ipfs_handler.verify_content(media_info['cid'])
                    if ipfs_exists:
                        ipfs_url = ipfs_handler.get_ipfs_url(media_info['cid'])
                except Exception as e:
                    logger.warning(f"IPFS verification error: {str(e)}")
        
        # Add detailed information based on media type
        additional_info = {}
        if media_type == 'photo':
            additional_info = {
                'token_id': media_info.get('token_id'),
                'metadata_uri': media_info.get('metadata_uri')
            }
        elif media_type == 'video_chunk':
            additional_info = {
                'session_id': media_info.get('session_id'),
                'sequence_number': media_info.get('sequence_number')
            }
        elif media_type == 'video_session':
            additional_info = {
                'session_id': media_info.get('session_id')
            }
        elif media_type == 'contract_interaction':
            additional_info = {
                'function': media_info.get('function'),
                'message': media_info.get('message')
            }
        
        response = {
            'exists_on_ipfs': ipfs_exists,
            'exists_on_blockchain': True,
            'owner': owner,
            'ipfs_url': ipfs_url,
            'tx_hash': tx_hash,
            'media_type': media_type,
            **additional_info
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in verify by transaction endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/verify/file', methods=['POST'])
def verify_file():
    """Verify a file's authenticity and ownership"""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        # Save the file temporarily
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            file.save(temp.name)
            filepath = temp.name
            
        try:
            # Calculate the IPFS CID for this file
            cid = ipfs_handler.calculate_cid(filepath)
            
            # Check if content exists on IPFS
            ipfs_exists = ipfs_handler.verify_content(cid)
            
            # Check blockchain records
            blockchain_exists, owner = blockchain_handler.verify_photo(cid)
            
            # Clean up temp file
            os.unlink(filepath)
            
            response = {
                'exists_on_ipfs': ipfs_exists,
                'exists_on_blockchain': blockchain_exists,
                'owner': owner if blockchain_exists else None,
                'ipfs_url': ipfs_handler.get_ipfs_url(cid) if ipfs_exists else None,
                'cid': cid
            }
            
            return jsonify(response)
            
        except Exception as e:
            # Clean up temp file in case of error
            os.unlink(filepath)
            raise
            
    except Exception as e:
        logger.error(f"Error in verify file endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

def cleanup():
    """Cleanup resources on shutdown"""
    try:
        camera.cleanup()
        ipfs_handler.cleanup()
        logger.info("Cleanup completed successfully")
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

if __name__ == "__main__":
    try:
        # Create required directories
        Path("captures").mkdir(exist_ok=True)
        
        # Start the Flask app
        port = int(os.getenv('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=not IS_RASPBERRY_PI)
    finally:
        cleanup() 