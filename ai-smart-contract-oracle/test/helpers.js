/**
 * Utility helpers shared across the Hardhat test suite.
 */
const { expect } = require("chai");

/**
 * Map a numeric score (0-100) to the contract's intuitive risk categories.
 * 0 => safe, 1 => caution, 2 => danger.
 *
 * @param {number} score
 * @returns {number}
 */
function scoreToCategory(score) {
    expect(score).to.be.at.least(0, "score must be >= 0");
    expect(score).to.be.at.most(100, "score must be <= 100");
    if (score <= 30) return 0;
    if (score < 70) return 1;
    return 2;
}

/**
 * Await an emitted event from a specific transaction receipt.
 * @param {import("ethers").ContractTransactionResponse} tx
 * @param {import("ethers").Contract} contract
 * @param {string} eventName
 * @returns {Promise<import("ethers").LogDescription | null>}
 */
async function waitForEvent(tx, contract, eventName) {
    const receipt = await tx.wait();
    for (const log of receipt.logs) {
        try {
            const parsed = contract.interface.parseLog(log);
            if (parsed.name === eventName) {
                return parsed;
            }
        } catch (err) {
            // Ignore logs that do not belong to the current contract.
        }
    }
    return null;
}

module.exports = {
    scoreToCategory,
    waitForEvent,
};
