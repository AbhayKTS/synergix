require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config();

const {
  ETH_RPC_URL,
  ORACLE_PRIVATE_KEY
} = process.env;

module.exports = {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      }
    }
  },

  networks: {
    localhost: {
      url: "http://127.0.0.1:8545",
      accounts: [`0x${ORACLE_PRIVATE_KEY}`],
    },

    sepolia: {
      url: ETH_RPC_URL || "",
      accounts: ORACLE_PRIVATE_KEY ? [`0x${ORACLE_PRIVATE_KEY}`] : [],
    },
  },
};
