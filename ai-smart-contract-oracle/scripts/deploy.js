const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();

  console.log("Deploying with:", deployer.address);

  const AIOracleAggregator = await hre.ethers.getContractFactory("AIOracleAggregator");

  const initialOracles = [deployer.address];      
  const minRequiredSubmissions = 1;
  const quorumPercent = 1;

  const contract = await AIOracleAggregator.deploy(
    initialOracles,
    minRequiredSubmissions,
    quorumPercent
  );

  await contract.waitForDeployment();

  const address = await contract.getAddress();

  console.log("AIOracleAggregator deployed at:", address);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
