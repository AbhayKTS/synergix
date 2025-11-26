/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  images: {
    unoptimized: true,
  },
  env: {
    NEXT_PUBLIC_QUEUE_URL: process.env.NEXT_PUBLIC_QUEUE_URL || 'http://127.0.0.1:9000/enqueue',
    NEXT_PUBLIC_ORACLE_CONTRACT: process.env.NEXT_PUBLIC_ORACLE_CONTRACT || '0x5FbDB2315678afecb367f032d93F642f64180aa3',
    NEXT_PUBLIC_RPC_URL: process.env.NEXT_PUBLIC_RPC_URL || 'http://127.0.0.1:8545'
  }
};

module.exports = nextConfig;
