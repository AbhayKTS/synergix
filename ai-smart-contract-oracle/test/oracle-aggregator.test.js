const { expect } = require("chai");
const { ethers } = require("hardhat");
const { anyValue } = require("@nomicfoundation/hardhat-chai-matchers/withArgs");

describe("AIOracleAggregator", function () {
  it("reaches consensus after three oracle submissions", async function () {
    const [owner, oracle1, oracle2, oracle3] = await ethers.getSigners();

    const Factory = await ethers.getContractFactory("AIOracleAggregator");
    const contract = await Factory.deploy([], 3, 66);
    await contract.waitForDeployment();

    await contract.connect(owner).registerOracle(oracle1.address);
    await contract.connect(owner).registerOracle(oracle2.address);
    await contract.connect(owner).registerOracle(oracle3.address);

    const target = "0x0000000000000000000000000000000000000111";

    await expect(contract.connect(oracle1).submitAssessment(target, 85, "ipfs://danger-a"))
      .to.emit(contract, "AssessmentSubmitted")
      .withArgs(target, oracle1.address, 85, "ipfs://danger-a");

    await expect(contract.connect(oracle2).submitAssessment(target, 75, "ipfs://danger-b"))
      .to.emit(contract, "AssessmentSubmitted")
      .withArgs(target, oracle2.address, 75, "ipfs://danger-b");

    await expect(contract.connect(oracle3).submitAssessment(target, 10, "ipfs://safe-c"))
      .to.emit(contract, "RiskAlertIssued")
      .withArgs(target, 56, 2, "ipfs://danger-a", anyValue, 3);

    const [score, category, ipfsCid, timestamp, numSubmittingOracles, finalized] = await contract.getFinalRisk(target);
    expect(finalized).to.equal(true);
    expect(Number(score)).to.equal(56);
    expect(Number(category)).to.equal(2);
    expect(ipfsCid).to.equal("ipfs://danger-a");
    expect(Number(numSubmittingOracles)).to.equal(3);
    expect(Number(timestamp)).to.be.greaterThan(0);
  });
});
