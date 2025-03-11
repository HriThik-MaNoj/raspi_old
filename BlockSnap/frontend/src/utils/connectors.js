import { InjectedConnector } from '@web3-react/injected-connector';

export const injected = new InjectedConnector({
  supportedChainIds: [
    24578, // BuildBear testnet
    1337,  // Local network
  ],
});