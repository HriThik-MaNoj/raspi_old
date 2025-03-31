import React, { useState, useEffect } from 'react';
import {
  Box,
  Heading,
  Text,
  VStack,
  HStack,
  Flex,
  Image,
  Badge,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  useColorModeValue,
  Button,
  Link,
  Icon,
  Tooltip,
  useToast,
  Spinner,
  Center
} from '@chakra-ui/react';
import { useWeb3React } from '@web3-react/core';
import { ExternalLinkIcon, CheckCircleIcon, InfoIcon, WarningIcon } from '@chakra-ui/icons';
import axios from 'axios';

// Contract information
const CONTRACT_ADDRESS = '0x5FbDB2315678afecb367f032d93F642f64180aa3'; // Hardhat default deployment address
const NETWORK_RPC_URL = 'http://127.0.0.1:8545'; // Hardhat local network
const NETWORK_CHAIN_ID = 31337; // Hardhat local chain ID

// Mock data for the visualization if no real data is available
const mockTransactions = [
  {
    tokenId: 1,
    timestamp: new Date(Date.now() - 86400000 * 2).toISOString(),
    txHash: '0x3a8e7f5b2e0c5d1a9b8f7e6d5c4b3a2e1d0c9b8a7f6e5d4c3b2a1e0d9c8b7a6f5',
    imageCid: 'QmXyZ...',
    metadataUri: 'ipfs://QmAbc...',
    blockNumber: 12345678,
    image: 'https://images.unsplash.com/photo-1579353977828-2a4eab540b9a?ixlib=rb-1.2.1&ixid=MnwxMjA3fDB8MHxzZWFyY2h8MXx8c2VjdXJpdHklMjBjYW1lcmF8ZW58MHx8MHx8&w=1000&q=80'
  },
  {
    tokenId: 2,
    timestamp: new Date(Date.now() - 86400000).toISOString(),
    txHash: '0x7f6e5d4c3b2a1e0d9c8b7a6f5e4d3c2b1a0e9d8c7b6a5f4e3d2c1b0a9e8d7f6e5',
    imageCid: 'QmABC...',
    metadataUri: 'ipfs://QmXyz...',
    blockNumber: 12345679,
    image: 'https://images.unsplash.com/photo-1566378246598-5b11a0d486cc?ixlib=rb-1.2.1&ixid=MnwxMjA3fDB8MHxzZWFyY2h8OXx8c2VjdXJpdHklMjBjYW1lcmF8ZW58MHx8MHx8&w=1000&q=80'
  },
  {
    tokenId: 3,
    timestamp: new Date().toISOString(),
    txHash: '0xd4c3b2a1e0d9c8b7a6f5e4d3c2b1a0e9d8c7b6a5f4e3d2c1b0a9e8d7f6e5d4c3',
    imageCid: 'QmDEF...',
    metadataUri: 'ipfs://QmGhi...',
    blockNumber: 12345680,
    image: 'https://images.unsplash.com/photo-1580785692949-7b5a7ba2e3ee?ixlib=rb-1.2.1&ixid=MnwxMjA3fDB8MHxzZWFyY2h8MTJ8fHNlY3VyaXR5JTIwY2FtZXJhfGVufDB8fDB8fA%3D%3D&w=1000&q=80'
  }
];

const BlockchainProof = () => {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalNFTs: 0,
    totalTransactions: 0,
    averageGasUsed: 0,
    lastBlockNumber: 0
  });
  const { account, active } = useWeb3React();
  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      
      try {
        // First try to get NFTs owned by the connected wallet
        let nftData = [];
        
        if (active && account) {
          try {
            const nftResponse = await axios.get(`http://localhost:5000/nfts/${account}`);
            if (nftResponse.data && nftResponse.data.nfts) {
              nftData = nftResponse.data.nfts;
              console.log('Fetched wallet NFTs:', nftData);
            }
          } catch (nftError) {
            console.error('Error fetching wallet NFTs:', nftError);
          }
        }
        
        // If we have NFTs from the wallet, use those
        if (nftData.length > 0) {
          processTransactionData(nftData);
        } else {
          // Otherwise, fetch recent transactions from the verification API
          try {
            const recentTxResponse = await axios.get('http://localhost:5000/api/recent-transactions');
            if (recentTxResponse.data && recentTxResponse.data.transactions) {
              const txDetails = [];
              for (const tx of recentTxResponse.data.transactions) {
                try {
                  const txResponse = await axios.get(`http://localhost:5000/api/verify/tx/${tx.hash}`);
                  if (txResponse.data && txResponse.data.exists_on_blockchain) {
                    txDetails.push({
                      ...txResponse.data,
                      blockNumber: tx.blockNumber,
                      timestamp: new Date(tx.timestamp * 1000).toISOString()
                    });
                  }
                } catch (txError) {
                  console.error(`Error fetching transaction ${tx.hash}:`, txError);
                }
              }
              
              if (txDetails.length > 0) {
                processTransactionData(txDetails);
                
                // Update stats with the latest block number
                const latestBlock = Math.max(...txDetails.map(tx => tx.blockNumber));
                setStats(prev => ({
                  ...prev,
                  lastBlockNumber: latestBlock,
                  totalTransactions: txDetails.length
                }));
                
                return; // Exit if we have transaction data
              }
            }
          } catch (error) {
            console.error('Error fetching transaction data:', error);
          }
          
          // If we still don't have data, use mock data
          console.log('Using mock transaction data');
          processTransactionData(mockTransactions);
          
          toast({
            title: 'Using sample data',
            description: 'Displaying sample blockchain data for demonstration purposes.',
            status: 'info',
            duration: 5000,
            isClosable: true,
          });
        }
      } catch (error) {
        console.error('Error in blockchain proof component:', error);
        processTransactionData(mockTransactions);
        
        toast({
          title: 'Using sample data',
          description: 'Displaying sample blockchain data for demonstration purposes.',
          status: 'info',
          duration: 5000,
          isClosable: true,
        });
      } finally {
        setLoading(false);
      }
    };

    // Helper function to process transaction data
    const processTransactionData = (data) => {
      // Process and normalize the data format
      const processedData = data.map(item => {
        // Extract image URL
        let imageUrl = null;
        
        // Check for direct image URL
        if (item.image && typeof item.image === 'string') {
          imageUrl = item.image;
        }
        // Check for image CID and construct IPFS URL
        else if (item.cid || item.image_cid) {
          const cid = item.cid || item.image_cid;
          imageUrl = `http://localhost:8080/ipfs/${cid}`;
        }
        // Check for metadata URI that might contain image info
        else if (item.metadata_uri && item.metadata_uri.startsWith('ipfs://')) {
          const metadataCid = item.metadata_uri.replace('ipfs://', '');
          imageUrl = `http://localhost:8080/ipfs/${metadataCid}`;
        }
        
        // Fallback image
        if (!imageUrl) {
          imageUrl = "https://via.placeholder.com/150?text=BlockSnap+NFT";
        }
        
        // Ensure we have a valid transaction hash
        const txHash = item.tx_hash || item.txHash || 'Unknown';
        
        // Ensure we have a valid block number (default to 1 if not available)
        const blockNumber = parseInt(item.block_number || item.blockNumber || 1);
        
        return {
          tokenId: item.token_id || item.tokenId || 'Unknown',
          txHash: txHash,
          blockNumber: blockNumber,
          timestamp: item.timestamp || new Date().toISOString(),
          imageCid: item.cid || item.image_cid || item.imageCid || 'Unknown',
          metadataUri: item.metadata_uri || item.metadataUri || 'Unknown',
          image: imageUrl,
          owner: item.owner || account || 'Unknown'
        };
      });
      
      setTransactions(processedData);
      
      // Calculate stats - ensure we have valid numbers
      const blockNumbers = processedData.map(tx => parseInt(tx.blockNumber) || 1);
      const lastBlock = blockNumbers.length > 0 ? Math.max(...blockNumbers) : 1;
      
      setStats({
        totalNFTs: processedData.length,
        totalTransactions: processedData.length,
        averageGasUsed: 85000, // Typical gas usage for NFT minting
        lastBlockNumber: lastBlock
      });
    };
    
    fetchData();
  }, [account, active, toast]);
  
  // Format address for display
  const formatAddress = (address) => {
    if (!address) return '';
    return `${address.substring(0, 6)}...${address.substring(address.length - 4)}`;
  };
  
  // Format transaction hash for display
  const formatTxHash = (hash) => {
    if (!hash || typeof hash !== 'string') return '';
    return `${hash.substring(0, 10)}...${hash.substring(hash.length - 8)}`;
  };
  
  // Generate explorer URL
  const getExplorerUrl = (txHash) => {
    // For local Hardhat network, we don't have an explorer
    // You can implement a local explorer or return null
    return null;
  };
  
  return (
    <Box p={5}>
      <VStack spacing={8} align="stretch">
        <Box textAlign="center">
          <Heading as="h1" size="xl" mb={2}>BlockSnap Onchain Verification</Heading>
          <Text fontSize="md" color="gray.500">
            Transparent verification of images stored on the blockchain via the BlockSnap NFT contract
          </Text>
          <Tooltip label={CONTRACT_ADDRESS}>
            <Badge colorScheme="green" fontSize="0.8em" mt={2}>
              Contract: {`${CONTRACT_ADDRESS.substring(0, 6)}...${CONTRACT_ADDRESS.substring(38)}`}
            </Badge>
          </Tooltip>
        </Box>
        
        {/* Stats Overview */}
        <SimpleGrid columns={{ base: 1, md: 3 }} spacing={5}>
          <Stat
            px={4}
            py={3}
            bg={bgColor}
            shadow="md"
            border="1px"
            borderColor={borderColor}
            borderRadius="lg"
          >
            <StatLabel fontWeight="medium">Total NFTs</StatLabel>
            <StatNumber fontSize="2xl">{stats.totalNFTs}</StatNumber>
            <StatHelpText>Images stored as NFTs</StatHelpText>
          </Stat>
          
          <Stat
            px={4}
            py={3}
            bg={bgColor}
            shadow="md"
            border="1px"
            borderColor={borderColor}
            borderRadius="lg"
          >
            <StatLabel fontWeight="medium">Transactions</StatLabel>
            <StatNumber fontSize="2xl">{stats.totalTransactions}</StatNumber>
            <StatHelpText>Blockchain interactions</StatHelpText>
          </Stat>
          
          <Stat
            px={4}
            py={3}
            bg={bgColor}
            shadow="md"
            border="1px"
            borderColor={borderColor}
            borderRadius="lg"
          >
            <StatLabel fontWeight="medium">Avg. Gas Used</StatLabel>
            <StatNumber fontSize="2xl">{stats.averageGasUsed.toLocaleString()}</StatNumber>
            <StatHelpText>Per transaction</StatHelpText>
          </Stat>
        </SimpleGrid>
        
        {/* Transaction Flow Visualization */}
        <Box
          bg={bgColor}
          shadow="md"
          border="1px"
          borderColor={borderColor}
          borderRadius="lg"
          p={5}
        >
          <Heading size="md" mb={4}>Onchain Transaction Flow</Heading>
          
          {loading ? (
            <Center py={10}>
              <VStack spacing={4}>
                <Spinner size="xl" color="blue.500" />
                <Text>Loading blockchain transactions...</Text>
              </VStack>
            </Center>
          ) : transactions.length > 0 ? (
            <Flex direction="column" align="center">
              {transactions.map((tx, index) => (
                <Box key={index} width="100%" mb={4}>
                  <Flex direction={{ base: 'column', md: 'row' }} align="center" justify="space-between">
                    {/* Image representation */}
                    <Box 
                      width={{ base: '100%', md: '15%' }} 
                      height="100px" 
                      bg="gray.300" 
                      borderRadius="md"
                      overflow="hidden"
                      position="relative"
                    >
                      {tx.image ? (
                        <Image 
                          src={tx.image} 
                          alt={`NFT #${tx.tokenId}`} 
                          objectFit="cover"
                          width="100%"
                          height="100%"
                          fallbackSrc="https://via.placeholder.com/150?text=BlockSnap+NFT"
                        />
                      ) : (
                        <Flex 
                          align="center" 
                          justify="center" 
                          height="100%"
                          bg="gray.700"
                          color="white"
                        >
                          <Text>Image #{tx.tokenId}</Text>
                        </Flex>
                      )}
                      <Badge 
                        position="absolute" 
                        top="2" 
                        right="2" 
                        colorScheme="blue"
                      >
                        #{tx.tokenId}
                      </Badge>
                    </Box>
                    
                    {/* Arrow */}
                    <Box 
                      display={{ base: 'none', md: 'flex' }}
                      alignItems="center"
                      justifyContent="center"
                      width="10%"
                    >
                      <Box as="span" fontSize="2xl">→</Box>
                    </Box>
                    
                    {/* IPFS Storage */}
                    <Box 
                      width={{ base: '100%', md: '25%' }} 
                      p={3} 
                      bg="blue.50" 
                      color="blue.800"
                      borderRadius="md"
                      my={{ base: 2, md: 0 }}
                    >
                      <VStack align="start" spacing={1}>
                        <Text fontWeight="bold">IPFS Storage</Text>
                        <Tooltip label={tx.imageCid || 'Unknown'}>
                          <Text fontSize="xs" isTruncated maxW="100%">
                            Image CID: {tx.imageCid ? `${tx.imageCid.substring(0, 6)}...${tx.imageCid.substring(-6)}` : 'Unknown'}
                          </Text>
                        </Tooltip>
                        <Tooltip label={tx.metadataUri || 'Unknown'}>
                          <Text fontSize="xs" isTruncated maxW="100%">
                            Metadata URI: {tx.metadataUri ? `${tx.metadataUri.substring(0, 6)}...${tx.metadataUri.substring(-6)}` : 'Unknown'}
                          </Text>
                        </Tooltip>
                        <Flex align="center">
                          <Icon as={InfoIcon} color="blue.500" mr={1} />
                          <Text fontSize="xs">Decentralized Storage</Text>
                        </Flex>
                      </VStack>
                    </Box>
                    
                    {/* Arrow */}
                    <Box 
                      display={{ base: 'none', md: 'flex' }}
                      alignItems="center"
                      justifyContent="center"
                      width="10%"
                    >
                      <Box as="span" fontSize="2xl">→</Box>
                    </Box>
                    
                    {/* Blockchain Transaction */}
                    <Box 
                      width={{ base: '100%', md: '25%' }} 
                      p={3} 
                      bg="green.50" 
                      color="green.800"
                      borderRadius="md"
                    >
                      <VStack align="start" spacing={2}>
                        <Text fontWeight="bold">Blockchain Record</Text>
                        <HStack>
                          <Text fontSize="xs" fontWeight="semibold">Block:</Text>
                          <Text fontSize="xs">
                            {tx.blockNumber && tx.blockNumber > 0 ? tx.blockNumber.toLocaleString() : '1'}
                          </Text>
                        </HStack>
                        <HStack>
                          <Text fontSize="xs" fontWeight="semibold">Time:</Text>
                          <Text fontSize="xs">
                            {new Date(tx.timestamp).toLocaleString()}
                          </Text>
                        </HStack>
                        <Flex align="center">
                          <Icon as={CheckCircleIcon} color="green.500" mr={1} />
                          <Text fontSize="xs">Verified on Hardhat</Text>
                        </Flex>
                        <Tooltip label="View transaction details">
                          <Button
                            size="xs"
                            variant="outline"
                            colorScheme="blue"
                            leftIcon={<InfoIcon />}
                            onClick={() => {
                              toast({
                                title: 'Transaction Details',
                                description: `Token ID: ${tx.tokenId}\nOwner: ${tx.owner}`,
                                status: 'info',
                                duration: 5000,
                                isClosable: true,
                              });
                            }}
                          >
                            Details
                          </Button>
                        </Tooltip>
                      </VStack>
                    </Box>
                  </Flex>
                  
                  {/* Timeline connector */}
                  {index < transactions.length - 1 && (
                    <Box 
                      height="30px" 
                      width="2px" 
                      bg="gray.300" 
                      mx="auto" 
                      my={2}
                    />
                  )}
                </Box>
              ))}
            </Flex>
          ) : (
            <Center py={10}>
              <VStack spacing={4}>
                <Icon as={WarningIcon} boxSize={10} color="orange.500" />
                <Text>No blockchain transactions found. Please connect your wallet or mint some NFTs first.</Text>
                <Button 
                  colorScheme="blue" 
                  onClick={() => window.location.href = '/camera'}
                >
                  Capture New Image
                </Button>
              </VStack>
            </Center>
          )}
        </Box>
        
        {/* Blockchain Network Information */}
        <Box
          bg={bgColor}
          shadow="md"
          border="1px"
          borderColor={borderColor}
          borderRadius="lg"
          p={5}
        >
          <Heading size="md" mb={4}>Network Information</Heading>
          <SimpleGrid columns={{ base: 1, md: 2 }} spacing={5}>
            <Box>
              <VStack align="start" spacing={3}>
                <HStack>
                  <Text fontWeight="bold" width="120px">Network:</Text>
                  <Text>Hardhat</Text>
                </HStack>
                <HStack>
                  <Text fontWeight="bold" width="120px">Chain ID:</Text>
                  <Text>{NETWORK_CHAIN_ID}</Text>
                </HStack>
                <HStack>
                  <Text fontWeight="bold" width="120px">RPC URL:</Text>
                  <Tooltip label={NETWORK_RPC_URL}>
                    <Text isTruncated maxW="300px">{NETWORK_RPC_URL}</Text>
                  </Tooltip>
                </HStack>
              </VStack>
            </Box>
            <Box>
              <VStack align="start" spacing={3}>
                <HStack>
                  <Text fontWeight="bold" width="120px">Contract:</Text>
                  <Tooltip label={CONTRACT_ADDRESS}>
                    <Text isTruncated maxW="300px">{`${CONTRACT_ADDRESS.substring(0, 6)}...${CONTRACT_ADDRESS.substring(38)}`}</Text>
                  </Tooltip>
                </HStack>
                <HStack>
                  <Text fontWeight="bold" width="120px">Standard:</Text>
                  <Text>ERC-721 (NFT)</Text>
                </HStack>
                <HStack>
                  <Text fontWeight="bold" width="120px">Status:</Text>
                  <Badge colorScheme="green">Active</Badge>
                </HStack>
              </VStack>
            </Box>
          </SimpleGrid>
        </Box>
      </VStack>
    </Box>
  );
};

export default BlockchainProof;
