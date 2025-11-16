const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

async function main() {
    await hre.run("compile");

    const Factory = await hre.ethers.getContractFactory("AIOracleAggregator");
    const contract = await Factory.deploy([], 3, 66);
    await contract.waitForDeployment();

    const address = await contract.getAddress();
    console.log(`AIOracleAggregator deployed to: ${address}`);

    const deploymentsDir = path.join(__dirname, "..", "deployments");
    fs.mkdirSync(deploymentsDir, { recursive: true });
    const filePath = path.join(deploymentsDir, "sepolia.json");

    const metadata = {
        network: hre.network.name,
        address,
        deployedAt: new Date().toISOString()
    };

    fs.writeFileSync(filePath, JSON.stringify(metadata, null, 2));
    console.log(`Saved deployment metadata to ${filePath}`);
}

main().catch((error) => {
    console.error(error);
    process.exit(1);
});
