import React from 'react'

export default function FeatureBreakdown({features}){
  if(!features) return <div className='card small'>No feature details available</div>
  // features.raw or features.flattened
  const raw = features.raw || {}
  const flat = features.flattened || {}
  return (
    <div className='card'>
      <h3>AI Explanation</h3>
      <div className='small'>Feature breakdown (flattened):</div>
      <div className='details'>
        <pre style={{whiteSpace:'pre-wrap', fontSize:12}}>{JSON.stringify(flat, null, 2)}</pre>
      </div>
      <div className='small'>Raw feature object:</div>
      <div className='details'>
        <pre style={{whiteSpace:'pre-wrap', fontSize:12}}>{JSON.stringify(raw, null, 2)}</pre>
      </div>
    </div>
  )
}
