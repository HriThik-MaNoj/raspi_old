const hre = require("hardhat");
const fs = require("fs");

async function deployWithRetry(maxRetries = 3, delayMs = 5000) {
  let lastError;
  
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      console.log(`Deployment attempt ${attempt}/${maxRetries}...`);
      
      // Get the contract factory
      const BlockSnapNFT = await hre.ethers.getContractFactory("BlockSnapNFT");
      console.log("Contract factory created");

      // Deploy the contract with increased gas limit
      const deploymentOptions = {
        gasLimit: 5000000, // Increase gas limit
      };
      
      const blockSnap = await BlockSnapNFT.deploy(deploymentOptions);
      console.log("Contract deployment initiated");

      // Wait for deployment with longer timeout
      const deployedContract = await blockSnap.waitForDeployment();
      const contractAddress = await deployedContract.getAddress();
      console.log("Contract deployed to:", contractAddress);
      
      return deployedContract;
    } catch (error) {
      console.error(`Attempt ${attempt} failed:`, error.message);
      lastError = error;
      
      if (attempt < maxRetries) {
        console.log(`Retrying in ${delayMs/1000} seconds...`);
        await new Promise(resolve => setTimeout(resolve, delayMs));
      }
    }
  }
  
  throw new Error(`Failed after ${maxRetries} attempts. Last error: ${lastError.message}`);
}

async function main() {
  console.log("Deploying BlockSnap NFT contract...");

  try {
    // Get network info
    const network = await hre.ethers.provider.getNetwork();
    console.log("Connected to network:", {
      chainId: network.chainId,
      name: network.name
    });

    // Get signer info
    const [signer] = await hre.ethers.getSigners();
    console.log("Deploying with account:", await signer.getAddress());
    const balance = await hre.ethers.provider.getBalance(signer.getAddress());
    console.log("Account balance:", hre.ethers.formatEther(balance));

    // Deploy the contract with retry logic
    const blockSnap = await deployWithRetry();

    // Get the contract artifacts
    const artifacts = await hre.artifacts.readArtifact("BlockSnapNFT");

    // Create contract info JSON
    const contractInfo = {
      address: await blockSnap.getAddress(),
      abi: artifacts.abi,
      network: hre.network.name,
      deploymentTime: new Date().toISOString()
    };

    // Save contract info to JSON file
    const contractInfoPath = './BlockSnapNFT.json';
    fs.writeFileSync(
      contractInfoPath,
      JSON.stringify(contractInfo, null, 2)
    );

    console.log("Contract information saved to BlockSnapNFT.json");

    // Update the .env file with the new contract address
    const envPath = './.env';
    const envContent = fs.readFileSync(envPath, 'utf8');
    const contractAddress = await blockSnap.getAddress();
    const updatedContent = envContent.replace(
      /^CONTRACT_ADDRESS=.*/m,
      `CONTRACT_ADDRESS=${contractAddress}`
    );
    fs.writeFileSync(envPath, updatedContent);
    console.log("Updated .env file with new contract address");

    // Verify contract on Etherscan if not on localhost
    if (hre.network.name !== "localhost" && hre.network.name !== "hardhat") {
      console.log("Verifying contract on Etherscan...");
      try {
        await hre.run("verify:verify", {
          address: await blockSnap.getAddress(),
          constructorArguments: []
        });
        console.log("Contract verified on Etherscan");
      } catch (error) {
        console.error("Error verifying contract:", error);
      }
    }
  } catch (error) {
    console.error("Error deploying contract:", error);
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  }); 