import { API_GATEWAY_URL } from './constants'

export async function fetchRisk(contractAddress){
  const url = `${API_GATEWAY_URL}/risk/${encodeURIComponent(contractAddress)}`
  const res = await fetch(url)
  if(!res.ok) throw new Error(`API error ${res.status}`)
  return await res.json()
}

export async function fetchHistory(contractAddress){
  const url = `${API_GATEWAY_URL}/history/${encodeURIComponent(contractAddress)}`
  const res = await fetch(url)
  if(!res.ok) throw new Error(`API error ${res.status}`)
  return await res.json()
}
