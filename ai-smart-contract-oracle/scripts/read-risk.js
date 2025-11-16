require("dotenv").config();
const hre = require("hardhat");

async function main() {
  const aggregatorAddress = process.env.ORACLE_CONTRACT_ADDRESS;
  if (!aggregatorAddress) {
    throw new Error("Set ORACLE_CONTRACT_ADDRESS in .env to the deployed AIOracleAggregator address");
  }

  const targetAddress = process.argv[2];
  if (!targetAddress) {
    throw new Error("Usage: npx hardhat run --network <network> scripts/read-risk.js <targetAddress>");
  }

  const aggregator = await hre.ethers.getContractAt(
    "AIOracleAggregator",
    aggregatorAddress
  );

  const result = await aggregator.getFinalRisk(targetAddress);
  const [score, category, ipfsCid, timestamp, numSubmittingOracles, finalized] = result;

  console.log("Aggregator:", aggregatorAddress);
  console.log("Target:", targetAddress);
  console.log("Finalized:", finalized);
  console.log("Aggregated Score:", score.toString());
  console.log("Category:", category.toString());
  console.log("IPFS CID:", ipfsCid);
  console.log("Timestamp:", timestamp.toString());
  console.log("Submissions:", numSubmittingOracles.toString());
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
