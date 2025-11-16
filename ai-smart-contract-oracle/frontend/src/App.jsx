import React, {useState, useCallback} from 'react'
import WalletProvider from './components/WalletProvider'
import SearchBar from './components/SearchBar'
import RiskGauge from './components/RiskGauge'
import VerdictBadge from './components/VerdictBadge'
import FeatureBreakdown from './components/FeatureBreakdown'
import StaticAnalysis from './components/StaticAnalysis'
import IPFSEvidence from './components/IPFSEvidence'
import EventListener from './components/EventListener'
import { fetchRisk, fetchHistory } from './lib/api'

export default function App(){
  const [address, setAddress] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState(null)

  const doSearch = useCallback(async (addr)=>{
    if(!addr) return
    setAddress(addr)
    setLoading(true)
    try{
      const d = await fetchRisk(addr)
      setData(d)
    }catch(e){
      console.error(e)
      setData(null)
      alert('Failed to fetch risk: '+e.message)
    }finally{setLoading(false)}
  }, [])

  const refreshOnEvent = useCallback(async (addr)=>{
    // if current address matches, refresh
    if(addr && addr.toLowerCase() === address.toLowerCase()){
      try{
        const d = await fetchRisk(addr)
        setData(d)
      }catch(e){console.warn('refresh failed', e)}
    }
  }, [address])

  const loadHistory = async ()=>{
    if(!address) return
    try{
      const h = await fetchHistory(address)
      setHistory(h)
    }catch(e){console.warn(e)}
  }

  return (
    <WalletProvider>
      <div className='app'>
        <div className='header'>
          <div>
            <h1>AI Smart Contract Oracle Dashboard</h1>
            <div className='small'>Search and inspect contract risk assessments</div>
          </div>
          <div className='controls'>
            <SearchBar onSearch={doSearch} />
          </div>
        </div>

        <div className='grid'>
          <div>
            <div className='card'>
              <h2>Overview</h2>
              <div style={{display:'flex',gap:16,alignItems:'center'}}>
                <div>
                  <RiskGauge score={data?.risk_score} />
                </div>
                <div style={{flex:1}}>
                  <div style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
                    <div>
                      <h3>Risk: <span style={{fontWeight:600}}>{data?.risk_label || 'n/a'}</span></h3>
                      <div className='small'>Source: {data?.source || 'n/a'}</div>
                    </div>
                    <div>
                      <VerdictBadge label={data?.risk_label} />
                    </div>
                  </div>
                  <div className='section'>
                    <button className='button' onClick={loadHistory}>Load History</button>
                  </div>
                </div>
              </div>
            </div>

            <div className='section'>
              <FeatureBreakdown features={data?.feature_details} />
            </div>

            <div className='section'>
              <StaticAnalysis details={data?.feature_details?.raw?.control_flow || data?.details} />
            </div>

            <div className='section'>
              <IPFSEvidence cid={data?.ipfs_cid} />
            </div>

            <div className='section'>
              <div className='card'>
                <h3>History</h3>
                <div className='details small'>
                  <pre style={{whiteSpace:'pre-wrap', fontSize:12}}>{JSON.stringify(history || {}, null, 2)}</pre>
                </div>
              </div>
            </div>

          </div>

          <div>
            <div className='card'>
              <h3>Wallet</h3>
              <div className='small'>Connect your wallet to interact</div>
              {/* RainbowKit's ConnectButton will be rendered via provider in a production app */}
            </div>

            <div className='section card'>
              <h3>Live Events</h3>
              <div className='small'>Listening for RiskAlertIssued events to auto-refresh the UI</div>
            </div>

          </div>
        </div>

        <EventListener onRiskAlert={refreshOnEvent} />
      </div>
    </WalletProvider>
  )
}
