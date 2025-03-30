require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config();
require("@matterlabs/hardhat-zksync");

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200
      }
    }
  },
  networks: {
    hardhat: {
      chainId: 1337
    },
    buildbear: {
      url: process.env.ETH_RPC_URL || "https://rpc.buildbear.io/imaginative-ghostrider-4b8c9868",
      accounts: process.env.PRIVATE_KEY ? [process.env.PRIVATE_KEY] : [],
      chainId: 24750,
      timeout: 120000, // Increase timeout to 2 minutes
      gasMultiplier: 1.5 // Add gas multiplier to increase gas price
    }
  },
  etherscan: {
    apiKey: process.env.ETHERSCAN_API_KEY
  },
  paths: {
    sources: "./smart_contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts"
  },
  mocha: {
    timeout: 120000 // Increase test timeout to 2 minutes as well
  }
}; 