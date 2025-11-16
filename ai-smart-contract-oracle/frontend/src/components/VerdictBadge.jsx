import React from 'react'

export default function VerdictBadge({label}){
  const map = {
    'safe': {color: 'var(--green)', text: 'SAFE'},
    'caution': {color: 'var(--yellow)', text: 'CAUTION'},
    'dangerous': {color: 'var(--red)', text: 'DANGEROUS'}
  }
  const item = map[label] || {color:'#6b7280', text: 'UNKNOWN'}
  return (
    <div style={{padding:'8px 12px', borderRadius:8, background:item.color, color:'#021014', fontWeight:700}}>{item.text}</div>
  )
}
