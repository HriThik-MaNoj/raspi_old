import React, { useState, useEffect } from 'react';
import {
  Box,
  SimpleGrid,
  Image,
  Text,
  VStack,
  HStack,
  Spinner,
  Center,
  useToast,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  Divider,
  IconButton,
  Tabs,
  TabList,
  Tab,
  TabPanels,
  TabPanel,
  Button,
} from '@chakra-ui/react';
import { useWeb3React } from '@web3-react/core';
import { ChevronDownIcon, CopyIcon } from '@chakra-ui/icons';
import axios from 'axios';
import { injected } from '../utils/connectors';

function Gallery() {
  const [media, setMedia] = useState({ photos: [], videos: [], videoSessions: [] });
  const [loading, setLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState(null);
  const [imageErrors, setImageErrors] = useState({});
  const [error, setError] = useState(null);
  const [noMediaMessage, setNoMediaMessage] = useState(null);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const { account, active, activate, library } = useWeb3React();
  const toast = useToast();
  const [walletStatus, setWalletStatus] = useState({ 
    active: active, 
    account: account,
    isMetaMaskConnected: false 
  });

  // Check if MetaMask is actually connected
  useEffect(() => {
    const checkMetaMaskConnection = async () => {
      if (window.ethereum) {
        try {
          const accounts = await window.ethereum.request({ method: 'eth_accounts' });
          const isConnected = accounts && accounts.length > 0;
          console.log('MetaMask connection check:', { 
            accounts, 
            isConnected, 
            web3ReactActive: active, 
            web3ReactAccount: account 
          });
          
          setWalletStatus({
            active: active,
            account: account,
            isMetaMaskConnected: isConnected
          });
          
          // If MetaMask is connected but Web3React isn't, try to activate
          if (isConnected && !active) {
            console.log('MetaMask is connected but Web3React is not, attempting to activate...');
            try {
              await activate(injected);
            } catch (error) {
              console.error('Failed to activate Web3React:', error);
            }
          }
        } catch (error) {
          console.error('Error checking MetaMask connection:', error);
        }
      }
    };
    
    checkMetaMaskConnection();
  }, [active, account, activate]);

  const handleImageError = (tokenId) => {
    setImageErrors(prev => ({ ...prev, [tokenId]: true }));
  };

  const handleImageClick = (nft) => {
    setSelectedImage(nft);
    onOpen();
  };

  const fetchMedia = async (account) => {
    if (!account) {
      console.log('No account provided to fetchMedia');
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      console.log(`Fetching media for account: ${account}`);
      
      // Fetch NFTs
      const nftsResponse = await axios.get(`http://localhost:5000/nfts/${account}`);
      console.log('NFTs API Response:', nftsResponse.data);
      
      // Fetch video sessions
      const sessionsResponse = await axios.get(`http://localhost:5000/video-sessions/${account}`);
      console.log('Video Sessions API Response:', sessionsResponse.data);
      
      // Process NFTs
      const allNfts = nftsResponse.data.nfts || [];
      const photos = allNfts.filter(nft => nft.type === 'photo');
      const videos = allNfts.filter(nft => nft.type === 'video');
      
      // Process video sessions
      const videoSessions = sessionsResponse.data.sessions || [];
      
      // Sort video chunks by sequence number
      const sortedSessions = videoSessions.map(session => ({
        ...session,
        chunks: (session.chunks || []).sort((a, b) => a.sequence_number - b.sequence_number)
      }));
      
      setMedia({
        photos,
        videos,
        videoSessions: sortedSessions
      });
      
      console.log(`Loaded ${photos.length} photos, ${videos.length} videos, and ${sortedSessions.length} video sessions`);
      
      // Check if we have any media items
      if (photos.length === 0 && videos.length === 0 && sortedSessions.length === 0) {
        setNoMediaMessage('No media found for this wallet. Try capturing some photos first!');
      } else {
        setNoMediaMessage(null);
      }
      
      // Check for any error messages from the backend
      if (nftsResponse.data.error) {
        console.warn('Backend reported an error (NFTs):', nftsResponse.data.error);
        toast({
          title: 'Warning',
          description: `Server reported: ${nftsResponse.data.error}`,
          status: 'warning',
          duration: 5000,
          isClosable: true,
        });
      }
      
      if (sessionsResponse.data.error) {
        console.warn('Backend reported an error (Sessions):', sessionsResponse.data.error);
        toast({
          title: 'Warning',
          description: `Server reported: ${sessionsResponse.data.error}`,
          status: 'warning',
          duration: 5000,
          isClosable: true,
        });
      }
    } catch (err) {
      console.error('Error fetching media:', err);
      setError(`Error fetching media: ${err.message}`);
      setMedia({ photos: [], videos: [], videoSessions: [] });
      setNoMediaMessage('Failed to load media. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  const renderInfoRow = (label, value) => (
    <Box w="100%" py={1}>
      <Text fontSize="xs" color="gray.500" mb={1}>
        {label}
      </Text>
      <HStack justify="space-between" align="center" 
        bg="gray.800" 
        p={2} 
        borderRadius="md"
        borderWidth="1px"
        borderColor="gray.700"
      >
        <Text fontSize="xs" color="white" isTruncated>
          {value}
        </Text>
        <IconButton
          aria-label="Copy"
          icon={<CopyIcon />}
          size="xs"
          variant="ghost"
          colorScheme="blue"
          onClick={() => {
            navigator.clipboard.writeText(value);
            toast({
              title: 'Copied',
              status: 'success',
              duration: 2000,
              isClosable: true,
            });
          }}
        />
      </HStack>
    </Box>
  );

  const renderVideoSession = (session) => {
    return (
      <Box 
        key={session.id}
        borderWidth="1px"
        borderRadius="lg"
        overflow="hidden"
        bg="gray.900"
        shadow="md"
        mb={4}
      >
        <Box p={4}>
          <HStack justify="space-between">
            <VStack align="start" spacing={1}>
              <Text fontWeight="bold" color="gray.100">
                Session #{session.id}
              </Text>
              <Text fontSize="sm" color="gray.400">
                {new Date(parseInt(session.start_time) * 1000).toLocaleString()}
              </Text>
              <Text fontSize="sm" color="gray.400">
                {session.chunks.length} clips
              </Text>
            </VStack>
            <IconButton
              aria-label="Toggle session"
              icon={<ChevronDownIcon />}
              variant="ghost"
              colorScheme="blue"
            />
          </HStack>
        </Box>
        
        <SimpleGrid columns={[1, 2, 3]} spacing={4} p={4}>
          {session.chunks.map((chunk) => (
            <Box 
              key={chunk.sequence_number}
              borderWidth="1px"
              borderRadius="md"
              overflow="hidden"
              bg="gray.800"
            >
              <video
                controls
                width="100%"
                src={`http://127.0.0.1:8080/ipfs/${chunk.video_cid}`}
                style={{ borderRadius: '0.375rem' }}
                muted
                preload="metadata"
                playsInline
              />
              <Box p={3}>
                <Text fontSize="sm" color="gray.300" mb={2}>
                  Clip {chunk.sequence_number + 1}
                </Text>
                <VStack spacing={2} align="stretch">
                  {renderInfoRow('IPFS CID', chunk.video_cid)}
                  {chunk.tx_hash && renderInfoRow('Transaction Hash', chunk.tx_hash)}
                  <Text fontSize="xs" color="gray.500">
                    {new Date(parseInt(chunk.timestamp) * 1000).toLocaleString()}
                  </Text>
                </VStack>
              </Box>
            </Box>
          ))}
        </SimpleGrid>
      </Box>
    );
  };

  // Fetch media on wallet change and when component mounts
  useEffect(() => {
    // Use either Web3React active state or check MetaMask directly
    const isWalletConnected = active || walletStatus.isMetaMaskConnected;
    const currentAccount = account || (window.ethereum && window.ethereum.selectedAddress);
    
    if (isWalletConnected && currentAccount) {
      console.log('Wallet is connected, fetching media...');
      fetchMedia(currentAccount);
    }
  }, [active, account, walletStatus.isMetaMaskConnected]);

  const manualConnect = async () => {
    if (window.ethereum) {
      try {
        // Request accounts from MetaMask
        await window.ethereum.request({ method: 'eth_requestAccounts' });
        
        // Try to activate Web3React
        await activate(injected);
        
        // Update wallet status
        const accounts = await window.ethereum.request({ method: 'eth_accounts' });
        setWalletStatus({
          active: true,
          account: accounts[0],
          isMetaMaskConnected: accounts.length > 0
        });
        
        toast({
          title: 'Wallet Connected',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
      } catch (error) {
        console.error('Error connecting wallet:', error);
        toast({
          title: 'Connection Error',
          description: error.message || 'Failed to connect wallet',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }
    } else {
      toast({
        title: 'MetaMask Not Found',
        description: 'Please install MetaMask to use this feature',
        status: 'warning',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  // Determine if wallet is connected using both Web3React and direct MetaMask check
  const isWalletConnected = active || walletStatus.isMetaMaskConnected;

  if (!isWalletConnected) {
    return (
      <Center h="200px" flexDirection="column" gap={4}>
        <Text>Please connect your wallet to view your media</Text>
        <Button
          onClick={manualConnect}
          bg="blue.500"
          color="white"
          _hover={{ bg: 'blue.600' }}
        >
          Connect Wallet
        </Button>
      </Center>
    );
  }

  if (loading) {
    return (
      <Center h="200px">
        <Spinner />
      </Center>
    );
  }

  return (
    <Box p={8} bg="gray.900">
      <Tabs>
        <TabList>
          <Tab>Photos</Tab>
          <Tab>Videos</Tab>
        </TabList>

        <TabPanels>
          <TabPanel>
            {media.photos.length === 0 ? (
              <Center h="200px">
                <Text>{noMediaMessage || 'No photos found'}</Text>
              </Center>
            ) : (
              <SimpleGrid columns={[1, 2, 3]} spacing={8}>
                {media.photos.map((nft) => (
                  <Box
                    key={nft.tokenId}
                    borderWidth="1px"
                    borderRadius="lg"
                    overflow="hidden"
                    shadow="md"
                  >
                    {imageErrors[nft.tokenId] ? (
                      <Center h="200px" bg="gray.100">
                        <Text color="gray.500">Image not available</Text>
                      </Center>
                    ) : (
                      <Box position="relative" cursor="pointer" onClick={() => handleImageClick(nft)}>
                        <Image
                          src={`http://127.0.0.1:8080/ipfs/${nft.image_cid}`}
                          alt={`NFT ${nft.tokenId}`}
                          width="100%"
                          height="200px"
                          objectFit="cover"
                          onError={() => handleImageError(nft.tokenId)}
                        />
                      </Box>
                    )}
                    <Box p={4}>
                      <Text fontWeight="bold" fontSize="lg" mb={2}>
                        Photo #{nft.tokenId}
                      </Text>
                      <VStack spacing={3} align="stretch">
                        {renderInfoRow('IPFS CID', nft.image_cid)}
                        {renderInfoRow('Transaction Hash', nft.transaction_hash)}
                        <Text fontSize="xs" color="gray.500">
                          {nft.metadata && nft.metadata.timestamp ? 
                            new Date(parseInt(nft.metadata.timestamp) * 1000).toLocaleString() : 
                            'Timestamp not available'}
                        </Text>
                      </VStack>
                    </Box>
                  </Box>
                ))}
              </SimpleGrid>
            )}
          </TabPanel>
          <TabPanel>
            {media.videoSessions.length === 0 ? (
              <Center h="200px">
                <Text>No video sessions found</Text>
              </Center>
            ) : (
              <VStack spacing={8} align="stretch">
                {media.videoSessions.map(renderVideoSession)}
              </VStack>
            )}
          </TabPanel>
        </TabPanels>
      </Tabs>

      <Modal isOpen={isOpen} onClose={onClose} size="xl">
        <ModalOverlay />
        <ModalContent bg="gray.800" color="white">
          <ModalCloseButton />
          <ModalBody p={6}>
            {selectedImage && (
              <VStack spacing={6} align="stretch">
                <Box borderRadius="md" overflow="hidden">
                  <Image
                    src={`http://127.0.0.1:8080/ipfs/${selectedImage.image_cid}`}
                    alt={`NFT ${selectedImage.tokenId}`}
                    width="100%"
                    objectFit="contain"
                  />
                </Box>
                <Divider />
                <VStack spacing={4} align="stretch">
                  <Text fontSize="xl" fontWeight="bold">
                    Photo #{selectedImage.tokenId}
                  </Text>
                  {renderInfoRow('IPFS CID', selectedImage.image_cid)}
                  {renderInfoRow('Transaction Hash', selectedImage.transaction_hash)}
                  {renderInfoRow('Owner', selectedImage.owner || 'Unknown')}
                  <Text fontSize="sm" color="gray.400">
                    {selectedImage.metadata && selectedImage.metadata.timestamp ? 
                      `Captured on ${new Date(parseInt(selectedImage.metadata.timestamp) * 1000).toLocaleString()}` : 
                      'Timestamp not available'}
                  </Text>
                </VStack>
              </VStack>
            )}
          </ModalBody>
        </ModalContent>
      </Modal>
    </Box>
  );
}

export default Gallery;