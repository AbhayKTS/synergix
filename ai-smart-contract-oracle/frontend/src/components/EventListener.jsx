import React, {useEffect} from 'react'
import { ethers } from 'ethers'
import { ORACLE_CONTRACT_ADDRESS, ORACLE_ABI } from '../lib/constants'
import { fetchRisk } from '../lib/api'

export default function EventListener({onRiskAlert}){
  useEffect(()=>{
    if(!ORACLE_CONTRACT_ADDRESS) return
    // connect to window.ethereum if available
    const provider = (window.ethereum) ? new ethers.BrowserProvider(window.ethereum) : new ethers.JsonRpcProvider()
    let contract
    try{
      contract = new ethers.Contract(ORACLE_CONTRACT_ADDRESS, ORACLE_ABI, provider)
    }catch(e){
      console.warn('EventListener contract init failed', e)
      return
    }

    const handler = async (target, category, score, ipfsCid, event) => {
      try{
        const addr = target.toString()
        // let parent refresh the UI
        onRiskAlert && onRiskAlert(addr)
      }catch(e){
        console.warn('event handler error', e)
      }
    }

    contract.on('RiskAlertIssued', handler)
    return ()=>{
      try{ contract.off('RiskAlertIssued', handler) }catch(e){}
    }
  }, [onRiskAlert])

  return null
}
