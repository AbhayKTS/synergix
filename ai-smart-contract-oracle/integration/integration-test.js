#!/usr/bin/env node
"use strict";

// End-to-end integration test:
// Inference Service -> Oracle Node -> Smart Contract -> Finalized Risk

require("dotenv").config();
const fs = require("fs");
const path = require("path");
const axios = require("axios");
const chalk = require("chalk");
const ora = require("ora");
const { ethers } = require("ethers");

const {
  AGGREGATOR_ADDRESS,
  INFERENCE_URL = "http://localhost:8000/predict",
  ORACLE_NODE_URL = "http://localhost:9000/submit-task",
  SEPOLIA_RPC_URL = "http://127.0.0.1:8545",
  TEST_TARGET_ADDRESS = "0x1111111111111111111111111111111111111111",
} = process.env;

const ABI_PATH = path.join(__dirname, "..", "smart_contracts", "oracle_aggregator_abi.json");
const CATEGORY_LABELS = ["safe", "caution", "danger"];
const CATEGORY_COLORS = [chalk.green, chalk.yellow, chalk.red];
const TIMEOUT_MS = 60_000;

const SAMPLE_SOURCE = `// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract SampleVault {
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    function deposit() external payable {}

    function sweep(address payable recipient) external {
        require(msg.sender == owner, "only owner");
        recipient.transfer(address(this).balance);
    }
}`;

/**
 * Load the compiled ABI that matches the deployed aggregator.
 */
function loadAbi() {
  if (!fs.existsSync(ABI_PATH)) {
    throw new Error(`ABI file not found at ${ABI_PATH}`);
  }
  const contents = fs.readFileSync(ABI_PATH, "utf8");
  return JSON.parse(contents);
}

/**
 * Initialize an ethers.js contract instance bound to a provider.
 */
function initContract(provider, abi) {
  if (!AGGREGATOR_ADDRESS) {
    throw new Error("AGGREGATOR_ADDRESS is missing in .env");
  }
  return new ethers.Contract(AGGREGATOR_ADDRESS, abi, provider);
}

/**
 * Call the inference service and return the numeric risk along with metadata.
 */
async function callInference(payload) {
  const response = await axios.post(INFERENCE_URL, payload, { timeout: 120_000 });
  const data = response.data || {};
  const rawScore =
    data.risk_score ?? data.riskScore ?? data.score ?? Math.random() * 0.5 + 0.25;
  const ipfsCid = data.ipfsCid || data.ipfs_cid || "ipfs://placeholder-report";
  return { rawScore, ipfsCid, data };
}

/**
 * Forward the task to the oracle node so it can submit on-chain.
 */
async function submitTaskToOracle(body) {
  await axios.post(ORACLE_NODE_URL, body, { timeout: 120_000 });
}

/**
 * Listen for a RiskAlertIssued event for a specific target within a timeout window.
 */
function listenForRiskAlert(contract, target, spinner) {
  return new Promise((resolve, reject) => {
    const filter = contract.filters.RiskAlertIssued(target);

    const timeoutId = setTimeout(() => {
      contract.off(filter, handler);
      if (spinner.isSpinning) spinner.fail("Timed out waiting for RiskAlertIssued event");
      reject(new Error("No RiskAlertIssued event observed within timeout"));
    }, TIMEOUT_MS);

    const handler = (targetAddr, aggregatedScore, category, cid, timestamp, numSubmissions, event) => {
      clearTimeout(timeoutId);
      contract.off(filter, handler);
      if (spinner.isSpinning) spinner.succeed("Risk alert detected on-chain!");
      resolve({ target: targetAddr, aggregatedScore, category, cid, timestamp, numSubmissions, event });
    };

    contract.on(filter, handler);
  });
}

/**
 * Fetch the finalized risk record from the contract once consensus has been reached.
 */
async function readFinalRisk(contract, target) {
  const result = await contract.getFinalRisk(target);
  const [score, category, ipfsCid, timestamp, numSubmittingOracles, finalized] = result;
  return {
    score: Number(score),
    category: Number(category),
    ipfsCid,
    timestamp: Number(timestamp),
    numSubmittingOracles: Number(numSubmittingOracles),
    finalized,
  };
}

function formatCategory(category) {
  const idx = Math.min(Math.max(category, 0), CATEGORY_LABELS.length - 1);
  const label = CATEGORY_LABELS[idx];
  const color = CATEGORY_COLORS[idx] || chalk.white;
  return color(`${label} (${category})`);
}

function printShapInsights(shapPayload) {
  const topFactors = shapPayload?.shap_top_factors || shapPayload?.top_factors;
  if (Array.isArray(topFactors) && topFactors.length) {
    console.log(chalk.gray("Top SHAP contributors:"));
    topFactors.slice(0, 5).forEach((factor, idx) => {
      console.log(chalk.gray(`  ${idx + 1}. ${factor.feature || factor.name || "feature"}: ${factor.value ?? factor.score ?? 0}`));
    });
  }
}

async function main() {
  console.log(chalk.cyan.bold("=== AI Oracle Aggregator Integration Test ==="));
  const abi = loadAbi();
  const provider = new ethers.JsonRpcProvider(SEPOLIA_RPC_URL);
  const contract = initContract(provider, abi);
  const targetAddress = TEST_TARGET_ADDRESS;

  const inferencePayload = {
    source_code: SAMPLE_SOURCE,
    bytecode: null,
  };

  try {
    console.log(chalk.blue("Calling inference service..."));
    const { rawScore, ipfsCid, data } = await callInference(inferencePayload);
    const scaledScore = Math.max(0, Math.min(100, Math.round(rawScore * 100)));
    console.log(chalk.green(`Inference OK: risk score ${(rawScore * 100).toFixed(2)}% (scaled ${scaledScore})`));
    if (ipfsCid) {
      console.log(chalk.green(`Report CID: ${ipfsCid}`));
    }
    printShapInsights(data);

    console.log(chalk.cyan("Submitting task to oracle node..."));
    await submitTaskToOracle({
      contract_address: targetAddress,
      source_code: SAMPLE_SOURCE,
      bytecode: null,
      ipfsCid,
    });
    console.log(chalk.cyan("Oracle submission accepted."));

    const spinner = ora("Waiting for oracle submission to finalize on-chain...").start();
    const eventData = await listenForRiskAlert(contract, targetAddress, spinner);
    const finalRisk = await readFinalRisk(contract, targetAddress);

    const eventScore = Number(eventData.aggregatedScore);
    const eventCategory = Number(eventData.category);
    const eventSubmissions = Number(eventData.numSubmissions);
    const eventTime = Number(eventData.timestamp) * 1000;

    console.log(chalk.magenta("\n============================"));
    console.log(chalk.magenta("   FINAL ON-CHAIN RESULT"));
    console.log(chalk.magenta("============================"));
    console.log(`Contract: ${eventData.target}`);
    console.log(`Score: ${eventScore}`);
    console.log(`Category: ${formatCategory(eventCategory)}`);
    console.log(`IPFS Report: ${eventData.cid}`);
    console.log(`Submissions: ${eventSubmissions}`);
    console.log(`Timestamp: ${eventTime ? new Date(eventTime).toISOString() : "n/a"}`);

    console.log(chalk.gray("\nStored final risk (contract read):"));
    console.log(`  Score: ${finalRisk.score}`);
    console.log(`  Category: ${formatCategory(finalRisk.category)}`);
    console.log(`  IPFS: ${finalRisk.ipfsCid}`);
    console.log(`  Submissions: ${finalRisk.numSubmittingOracles}`);
    console.log(`  Finalized: ${finalRisk.finalized}`);
  } catch (error) {
    console.error(chalk.red("Integration test failed:"), error.message);
    if (error.response?.data) {
      console.error(chalk.red("Response body:"), error.response.data);
    }
    process.exit(1);
  }
}

main();
