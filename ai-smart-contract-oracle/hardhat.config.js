require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config();

const { ORACLE_PRIVATE_KEY, ETH_RPC_URL } = process.env;

module.exports = {
  solidity: "0.8.20",

  networks: {
    localhost: {
      url: "http://127.0.0.1:8545",
      accounts: [`0x${ORACLE_PRIVATE_KEY}`],
    },
    sepolia: {
      url: ETH_RPC_URL || "",
      accounts: ORACLE_PRIVATE_KEY ? [`0x${ORACLE_PRIVATE_KEY}`] : [],
    }
  }
};
