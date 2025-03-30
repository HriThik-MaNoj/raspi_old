import React, { useState } from 'react';
import {
  Box,
  VStack,
  Button,
  Text,
  Input,
  useToast,
  Heading,
  Divider,
  HStack,
  Icon,
  Badge,
  FormControl,
  FormLabel,
  Spinner,
  Tag,
  TagLabel,
  TagLeftIcon,
} from '@chakra-ui/react';
import { useDropzone } from 'react-dropzone';
import { MdCloudUpload, MdVerified, MdError, MdDevices, MdPerson } from 'react-icons/md';
import axios from 'axios';

function VerifyMedia() {
  const [verificationResult, setVerificationResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [txHashInput, setTxHashInput] = useState('');
  const toast = useToast();

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'image/*': ['.jpeg', '.jpg', '.png'],
      'video/*': ['.mp4', '.webm']
    },
    maxFiles: 1,
    onDrop: async (acceptedFiles) => {
      if (acceptedFiles.length > 0) {
        await verifyFile(acceptedFiles[0]);
      }
    },
  });

  const verifyFile = async (file) => {
    try {
      setLoading(true);
      const formData = new FormData();
      formData.append('file', file);

      const response = await axios.post('http://localhost:5000/verify/file', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setVerificationResult(response.data);
    } catch (error) {
      toast({
        title: 'Error',
        description: error.message,
        status: 'error',
        duration: 5000,
      });
    } finally {
      setLoading(false);
    }
  };

  const verifyTxHash = async () => {
    if (!txHashInput) {
      toast({
        title: 'Error',
        description: 'Please enter a transaction hash',
        status: 'error',
        duration: 5000,
      });
      return;
    }

    try {
      setLoading(true);
      // Use the distributed verification endpoint
      const response = await axios.get(`http://localhost:5000/api/verify/tx/${txHashInput}`);
      setVerificationResult(response.data);
    } catch (error) {
      toast({
        title: 'Error',
        description: error.message || 'Failed to verify transaction hash',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box maxW="container.lg" mx="auto">
      <VStack spacing={8} align="stretch">
        <Heading color="white">Verify Media Authenticity</Heading>
        
        <Text color="gray.300">
          Verify the authenticity of media using blockchain verification. 
          Our system validates media authenticity by checking transaction records on the blockchain, 
          ensuring tamper-proof verification without relying on centralized storage systems.
        </Text>
        
        <Box
          {...getRootProps()}
          p={10}
          bg="gray.800"
          borderRadius="lg"
          borderWidth={2}
          borderStyle="dashed"
          borderColor={isDragActive ? "blue.500" : "gray.600"}
          cursor="pointer"
          _hover={{
            borderColor: "blue.500",
          }}
        >
          <input {...getInputProps()} />
          <VStack spacing={4}>
            <Icon as={MdCloudUpload} w={12} h={12} color="gray.400" />
            <Text color="gray.400" textAlign="center">
              {isDragActive
                ? "Drop the file here"
                : "Drag and drop a file here, or click to select"}
            </Text>
          </VStack>
        </Box>

        <Divider />

        <VStack spacing={4}>
          <FormControl>
            <FormLabel color="white">Enter Transaction Hash</FormLabel>
            <HStack>
              <Input
                placeholder="Enter Transaction Hash (0x...)"
                value={txHashInput}
                onChange={(e) => setTxHashInput(e.target.value)}
                bg="gray.800"
                color="white"
                borderColor="gray.600"
              />
              <Button
                colorScheme="blue"
                onClick={verifyTxHash}
                isLoading={loading}
              >
                Verify
              </Button>
            </HStack>
          </FormControl>
        </VStack>

        {loading && (
          <Box textAlign="center" py={6}>
            <Spinner size="xl" color="blue.500" />
            <Text mt={4} color="white">Verifying across the network...</Text>
          </Box>
        )}

        {verificationResult && !loading && (
          <Box bg="gray.800" p={6} borderRadius="lg">
            <VStack spacing={4} align="stretch">
              <HStack>
                <Icon
                  as={verificationResult.exists_on_blockchain ? MdVerified : MdError}
                  w={6}
                  h={6}
                  color={verificationResult.exists_on_blockchain ? "green.500" : "red.500"}
                />
                <Text color="white" fontSize="lg" fontWeight="bold">
                  Verification Result
                </Text>
              </HStack>

              {verificationResult.tx_hash && (
                <HStack>
                  <Badge colorScheme="blue">Transaction Hash</Badge>
                  <Text color="gray.300" isTruncated>
                    {verificationResult.tx_hash}
                  </Text>
                </HStack>
              )}

              <HStack>
                <Badge
                  colorScheme={verificationResult.exists_on_blockchain ? "green" : "red"}
                >
                  Blockchain Status
                </Badge>
                <Text color="gray.300">
                  {verificationResult.exists_on_blockchain
                    ? verificationResult.owner 
                      ? `Verified - Owned by ${verificationResult.owner}` 
                      : "Verified - Owner information unavailable"
                    : "Not Found"}
                </Text>
              </HStack>

              {/* Display verification source */}
              {verificationResult.verified_by && (
                <HStack>
                  <Tag size="md" colorScheme="purple" borderRadius="full">
                    <TagLeftIcon boxSize="12px" as={MdDevices} />
                    <TagLabel>Verified by: {verificationResult.verified_by}</TagLabel>
                  </Tag>
                </HStack>
              )}

              {/* Display media type */}
              {verificationResult.media_type && (
                <HStack>
                  <Badge colorScheme="teal">
                    Media Type
                  </Badge>
                  <Text color="gray.300" textTransform="capitalize">
                    {verificationResult.media_type}
                  </Text>
                </HStack>
              )}

              {/* Display owner */}
              {verificationResult.owner && (
                <HStack>
                  <Tag size="md" colorScheme="green" borderRadius="full">
                    <TagLeftIcon boxSize="12px" as={MdPerson} />
                    <TagLabel>Owner: {verificationResult.owner.substring(0, 6)}...{verificationResult.owner.substring(38)}</TagLabel>
                  </Tag>
                </HStack>
              )}

              {/* Display token ID if available */}
              {verificationResult.token_id && (
                <HStack>
                  <Badge colorScheme="blue">
                    Token ID
                  </Badge>
                  <Text color="gray.300">
                    {verificationResult.token_id}
                  </Text>
                </HStack>
              )}

              {/* Display session ID if available */}
              {verificationResult.session_id && (
                <HStack>
                  <Badge colorScheme="orange">
                    Session ID
                  </Badge>
                  <Text color="gray.300">
                    {verificationResult.session_id}
                  </Text>
                </HStack>
              )}

              {/* Display CID if available but don't try to load it */}
              {verificationResult.cid && (
                <HStack>
                  <Badge colorScheme="yellow">
                    Content ID (IPFS)
                  </Badge>
                  <Text color="gray.300" isTruncated>
                    {verificationResult.cid}
                  </Text>
                </HStack>
              )}

              {/* Display sequence number if available */}
              {verificationResult.sequence_number && (
                <HStack>
                  <Badge colorScheme="cyan">
                    Sequence Number
                  </Badge>
                  <Text color="gray.300">
                    {verificationResult.sequence_number}
                  </Text>
                </HStack>
              )}

              {/* Display metadata URI if available */}
              {verificationResult.metadata_uri && (
                <HStack>
                  <Badge colorScheme="purple">
                    Metadata URI
                  </Badge>
                  <Text color="gray.300" isTruncated>
                    {verificationResult.metadata_uri}
                  </Text>
                </HStack>
              )}

              {/* Display function if available */}
              {verificationResult.function && (
                <HStack>
                  <Badge colorScheme="blue">
                    Function
                  </Badge>
                  <Text color="gray.300">
                    {verificationResult.function}
                  </Text>
                </HStack>
              )}

              {/* Display message if available */}
              {verificationResult.message && (
                <HStack>
                  <Badge colorScheme="pink">
                    Message
                  </Badge>
                  <Text color="gray.300">
                    {verificationResult.message}
                  </Text>
                </HStack>
              )}
            </VStack>
          </Box>
        )}
      </VStack>
    </Box>
  );
}

export default VerifyMedia;