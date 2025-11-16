import React from 'react'
import { getDefaultWallets, RainbowKitProvider } from '@rainbow-me/rainbowkit'
import { configureChains, createClient, WagmiConfig } from 'wagmi'
import { publicProvider } from 'wagmi/providers/public'
import { mainnet, sepolia } from 'wagmi/chains'

const { chains, provider } = configureChains([sepolia], [publicProvider()])
const { connectors } = getDefaultWallets({appName:'AI Oracle Dashboard', chains})
const wagmiClient = createClient({autoConnect:true, connectors, provider})

export default function WalletProvider({children}){
  return (
    <WagmiConfig client={wagmiClient}>
      <RainbowKitProvider chains={chains}>
        {children}
      </RainbowKitProvider>
    </WagmiConfig>
  )
}
