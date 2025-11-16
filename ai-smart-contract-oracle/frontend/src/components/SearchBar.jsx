import React, {useState} from 'react'

export default function SearchBar({onSearch}){
  const [addr, setAddr] = useState('')
  return (
    <div style={{display:'flex', gap:8}}>
      <input className='searchInput' placeholder='Enter contract address' value={addr} onChange={e=>setAddr(e.target.value)} />
      <button className='button' onClick={()=>onSearch(addr)}>Search</button>
    </div>
  )
}
