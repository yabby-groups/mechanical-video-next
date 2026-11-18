import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

type Standard = {
  type: 'chart' | 'comparison' | 'diagram' | 'timeline';
  title: string;
  items: {label: string; detail: string; value?: number}[];
  unit?: string;
  formula?: string;
};
type Angular = {type: 'angular_comparison'; title: string; travel: number; items: {label: string; radius: number}[]};
type DualReel = {type:'dual_reel_speed'; title:string; coreRadius:number; fullRadius:number; feedSpeed:number};
export type EvidenceGraphicSpec = Standard | Angular | DualReel;

const palette = ['#07576b', '#873c12', '#335b39', '#42365d'];
const ink = '#122830';
const plate = '#f5f8f9';

const AngularEvidence: React.FC<{spec: Angular; progress: number}> = ({spec,progress}) => {
  const maxRadius = Math.max(...spec.items.map(item=>item.radius));
  return <svg viewBox="0 0 1920 1080" style={{position:'absolute',inset:0,width:'100%',height:'100%'}}>
    {spec.items.map((item,i)=>{
      const x=480+i*960;
      const y=484;
      const radius=157*item.radius/maxRadius;
      const angle=spec.travel/item.radius*progress;
      const end=[x+Math.sin(angle)*radius,y-Math.cos(angle)*radius];
      return <g key={item.label} fill={ink}>
        <line x1={x-320} y1={y-radius-14} x2={x} y2={y-radius-14} stroke={palette[i]} strokeWidth="24"/>
        <line x1={x-320} y1={y-radius-14} x2={x} y2={y-radius-14} stroke="white" strokeWidth="7" strokeDasharray="25 30" strokeDashoffset={-progress*110}/>
        <circle cx={x} cy={y} r={radius} fill="#e9f1f2" stroke={palette[i]} strokeWidth={12}/>
        <path d={`M ${x} ${y-radius} A ${radius} ${radius} 0 0 1 ${end[0]} ${end[1]}`}
          fill="none" stroke={palette[i]} strokeWidth="21"/>
        <line x1={x} x2={x} y1={y} y2={y-radius} stroke="#64757b" strokeWidth="7" strokeDasharray="12 10"/>
        <line x1={x} x2={end[0]} y1={y} y2={end[1]} stroke={palette[i]} strokeWidth="14"/>
        <circle cx={end[0]} cy={end[1]} r="17" fill={palette[i]}/>
        <text x={x} y={760} textAnchor="middle" fontSize="86" fontWeight="700">{item.label}</text>
        <text x={x} y={850} textAnchor="middle" fontSize="86" fontWeight="700">{item.radius/Math.min(...spec.items.map(v=>v.radius))===1?'R':`${Number((item.radius/Math.min(...spec.items.map(v=>v.radius))).toFixed(2))}R`}</text>
      </g>;
    })}
    <text x="960" y="900" textAnchor="middle" fontSize="86" fontWeight="700" fill={ink}>等长带  s = rθ</text>
  </svg>;
};

const DualReelEvidence: React.FC<{spec:DualReel; progress:number}> = ({spec,progress}) => {
  const {coreRadius:a,fullRadius:b,feedSpeed:v}=spec;
  const r1=Math.sqrt(b*b-(b*b-a*a)*progress), r2=Math.sqrt(a*a+(b*b-a*a)*progress);
  const centerY=460, scale=160/b;
  const speed=(r:number)=>v/r;
  const max=v/a;
  const graphX=(p:number)=>1050+650*p;
  const graphY=(r:number)=>800-400*speed(r)/max;
  const dx=500, dr=(r2-r1)*scale, nx=-dr/dx, ny=Math.sqrt(1-nx*nx);
  const belt=`M ${300+nx*r1*scale} ${centerY+ny*r1*scale} L ${800+nx*r2*scale} ${centerY+ny*r2*scale}`;
  const curve=(supply:boolean)=>Array.from({length:61},(_,i)=>{const p=i/60;
    const r=Math.sqrt(supply?b*b-(b*b-a*a)*p:a*a+(b*b-a*a)*p);
    return `${i?'L':'M'} ${graphX(p)} ${graphY(r)}`;}).join(' ');
  return <svg viewBox="0 0 1920 1080" style={{position:'absolute',inset:0,width:'100%',height:'100%'}}>
    {[r1,r2].map((r,i)=>{const x=300+i*500, k=b*b-a*a, angle=(i ? r-a : b-r)*2/k*8;
      return <g key={i}>
        <circle cx={x} cy={centerY} r={r*scale} fill="#e5edef" stroke={palette[i]} strokeWidth="14"/>
        <circle cx={x} cy={centerY} r={a*scale} fill="#f8fafb" stroke={palette[i]} strokeWidth="8"/>
        <line x1={x} y1={centerY} x2={x+Math.sin(angle)*r*scale} y2={centerY-Math.cos(angle)*r*scale} stroke={palette[i]} strokeWidth="14"/>
        <text x={x} y="760" textAnchor="middle" fill={ink} fontSize="86" fontWeight="700">{i?'收卷':'放卷'}</text>
      </g>;})}
    <path d={belt} stroke="#38565f" strokeWidth="20" fill="none"/>
    <path d={belt} stroke="white" strokeWidth="7" strokeDasharray="28 30" strokeDashoffset={-progress*180} fill="none"/>
    <line x1="1050" y1="800" x2="1700" y2="800" stroke={ink} strokeWidth="6"/>
    {[true,false].map((s,i)=><path key={i} d={curve(s)} stroke={palette[i]} strokeWidth="13" fill="none" opacity=".35"/>)}
    {[r1,r2].map((r,i)=><circle key={i} cx={graphX(progress)} cy={graphY(r)} r="22" fill={palette[i]}/>)}
    <text x="1375" y="345" textAnchor="middle" fill={ink} fontSize="86" fontWeight="700">ω = v / r</text>
    <text x="1375" y="920" textAnchor="middle" fill={ink} fontSize="86" fontWeight="700">恒定带速 · 理想几何</text>
  </svg>;
};

const StandardEvidence: React.FC<{spec: Standard; progress: number}> = ({spec,progress}) => {
  const chart = spec.type === 'chart';
  const max = chart ? Math.max(...spec.items.map(i=>i.value!)) || 1 : 1;
  return <div style={{display:'grid',gridTemplateColumns:chart?'1fr':'repeat(2,minmax(0,1fr))',
    columnGap:56,rowGap:12,marginTop:25}}>
    {spec.items.map((item,index)=><div key={index} style={{minWidth:0,color:ink}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'baseline',fontSize:86,fontWeight:750,lineHeight:1}}>
        <span>{item.label}</span>{chart && <span>{item.value} {spec.unit}</span>}
      </div>
      <div style={{height:12,background:palette[index],width:chart?`${item.value!/max*progress*100}%`:'100%',marginTop:8}}/>
      <div style={{fontSize:86,lineHeight:1,marginTop:3}}>{item.detail}</div>
    </div>)}
  </div>;
};

export const EvidenceGraphic: React.FC<{graphic: EvidenceGraphicSpec; seconds: number}> = ({graphic,seconds}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const progress = interpolate(frame, [0,Math.max(1,seconds*fps*.92)], [0,1], {extrapolateRight:'clamp'});
  return <AbsoluteFill style={{background:plate,color:ink,padding:'155px 125px 170px'}}>
    <div style={{fontSize:96,fontWeight:760,lineHeight:1.05}}>{graphic.title}</div>
    {graphic.type==='angular_comparison' ? <AngularEvidence spec={graphic} progress={progress}/> : graphic.type==='dual_reel_speed' ? <DualReelEvidence spec={graphic} progress={progress}/> :
      <StandardEvidence spec={graphic} progress={progress}/>}
    {'formula' in graphic && graphic.formula && <div style={{position:'absolute',left:125,bottom:148,fontSize:86,fontWeight:700}}>{graphic.formula}</div>}
  </AbsoluteFill>;
};
