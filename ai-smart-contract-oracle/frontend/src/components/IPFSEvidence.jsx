import React from 'react'

export default function IPFSEvidence({cid}){
  if(!cid) return <div className='card small'>No IPFS evidence available</div>
  const url = `https://ipfs.io/ipfs/${cid}`
  return (
    <div className='card'>
      <h3>IPFS Evidence</h3>
      <div className='details small'>CID: {cid}</div>
      <a className='button' href={url} target='_blank' rel='noreferrer'>Open on IPFS Gateway</a>
    </div>
  )
}
