import React from 'react'

export default function StaticAnalysis({details}){
  if(!details) return <div className='card small'>No static analysis details</div>
  return (
    <div className='card'>
      <h3>Static Analysis</h3>
      <div className='small'>Summary:</div>
      <div className='details'>
        <pre style={{whiteSpace:'pre-wrap', fontSize:12}}>{JSON.stringify(details, null, 2)}</pre>
      </div>
    </div>
  )
}
