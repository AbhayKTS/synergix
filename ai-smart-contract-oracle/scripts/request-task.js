async function main() {
  const [deployer] = await ethers.getSigners();
  const aggregatorAddress = "0xYourLocalAggregatorAddressHere"; // replace
  const aggregator = await ethers.getContractAt("AIOracleAggregator", aggregatorAddress, deployer);

  const target = "0x1234567890123456789012345678901234567890"; // the contract you want analyzed
  const tx = await aggregator.requestAssessment(target);
  console.log("Requested assessment tx:", tx.hash);
  await tx.wait();
  console.log("Requested assessment for", target);
}

main().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
