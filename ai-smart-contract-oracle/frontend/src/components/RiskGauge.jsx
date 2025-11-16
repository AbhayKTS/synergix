import React from 'react'
import { RadialBarChart, RadialBar, Legend } from 'recharts'

export default function RiskGauge({score}){
  // score expected 0..1
  const value = Math.round((score || 0) * 100)
  const data = [{name:'risk', value}]
  return (
    <div style={{width:300, height:200}}>
      <RadialBarChart width={300} height={200} cx={150} cy={100} innerRadius={50} outerRadius={100} barSize={20} data={data} startAngle={180} endAngle={0}>
        <RadialBar minAngle={15} background clockWise dataKey="value" cornerRadius={10} />
        <text x={150} y={110} textAnchor="middle" dominantBaseline="middle" style={{fontSize:20, fill:'#e6eef8'}}>{value}%</text>
      </RadialBarChart>
    </div>
  )
}
