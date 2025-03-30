import React from 'react';
import { Box, Container } from '@chakra-ui/react';
import BlockchainProof from '../components/BlockchainProof';
import Navbar from '../components/Navbar';

function OnchainVerificationHub() {
  return (
    <Box minH="100vh" bg="gray.50" _dark={{ bg: 'gray.900' }}>
      <Navbar />
      <Container maxW="container.xl" pt={5} pb={10}>
        <BlockchainProof />
      </Container>
    </Box>
  );
}

export default OnchainVerificationHub;
