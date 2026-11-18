import React, {useLayoutEffect, useRef} from 'react';
import {AbsoluteFill, OffthreadVideo, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

export type Graphic = {
  type: 'diagram' | 'comparison' | 'chart' | 'timeline' | 'data_animation';
  title: string;
  items: {label: string; detail: string; value?: number; keyframes?: [number,number][]}[];
  unit?: string;
  formula?: string;
  domainMax?: number;
};
export type SplitScreenSpec = {sources:[{media:string;startFrame:number;credit:string},{media:string;startFrame:number;credit:string}]};
export type VisualProps = {
  graphic?: Graphic;
  footage?: {startFrame: number; credit: string};
  chapter?: string;
  splitScreen?: SplitScreenSpec;
};

const colors = ['#236c87', '#996226', '#39716a', '#586378'];
const enter = (frame: number, start: number, length: number) =>
  interpolate(frame, [start, start+length], [0, 1], {extrapolateLeft:'clamp', extrapolateRight:'clamp'});

// 86 canvas pixels corresponds to 16.1 px at a 360 px preview.
const PhoneText: React.FC<{text:string; style?:React.CSSProperties}> = ({text,style}) => {
  const ref=useRef<HTMLDivElement>(null);
  useLayoutEffect(()=>{
    const el=ref.current!;
    if(!text || /[\r\n]/.test(text) || parseFloat(getComputedStyle(el).fontSize)<86 ||
       el.scrollWidth>el.clientWidth+1 || el.scrollHeight>el.clientHeight+1)
      throw new Error(`Phone text does not fit: ${text} (${getComputedStyle(el).fontSize}, ${el.scrollWidth}x${el.scrollHeight} / ${el.clientWidth}x${el.clientHeight})`);
  },[text]);
  return <div ref={ref} data-science-graphic-text style={{fontSize:86,lineHeight:1.5,whiteSpace:'nowrap',overflow:'hidden',...style}}>{text}</div>;
};

export const SplitScreen: React.FC<{spec:SplitScreenSpec}> = ({spec}) => <AbsoluteFill style={{background:'#223139'}}>
  {spec.sources.map((source,i)=><div key={i} style={{position:'absolute',left:`${i*50}%`,top:0,width:'50%',height:'100%',overflow:'hidden'}}>
    <OffthreadVideo src={staticFile(source.media)} trimBefore={source.startFrame} muted style={{width:'100%',height:'100%',objectFit:'contain'}}/>
    <PhoneText text={source.credit} style={{position:'absolute',left:32,width:896,bottom:220,color:'white',textShadow:'0 2px 6px black'}}/>
  </div>)}
</AbsoluteFill>;

const DataAnimation: React.FC<{graphic:Graphic}> = ({graphic}) => {
  const frame=useCurrentFrame(); const {fps}=useVideoConfig();
  const all=graphic.items.flatMap(item=>item.keyframes??[]);
  if(graphic.items.length<2 || graphic.items.length>4 || !graphic.unit ||
      graphic.items.some(item=>!item.keyframes || item.keyframes.length<2 || item.keyframes.some((p,i,a)=>
        p.length!==2 || !Number.isFinite(p[0]) || !Number.isFinite(p[1]) || p[0]<0 || p[1]<0 || (i>0 && p[0]<=a[i-1][0]))))
    throw new Error('Invalid data animation keyframes');
  const max=graphic.domainMax??Math.max(...all.map(p=>p[1]),1);
  if(!Number.isFinite(max) || max<=0 || all.some(p=>p[1]>max)) throw new Error('Invalid data animation domain');
  return <AbsoluteFill style={{background:'#e6eaed',color:'#172b35'}}>
    <PhoneText text={graphic.title} style={{position:'absolute',left:128,width:1664,top:145,fontWeight:700,lineHeight:1.5}}/>
    <div style={{position:'absolute',left:128,right:128,top:365,display:'grid',
      gridTemplateColumns:graphic.items.length===4?'1fr 1fr':'1fr',columnGap:40}}>
    {graphic.items.map((item,i)=>{
      const points=item.keyframes!; const value=interpolate(frame/fps,points.map(p=>p[0]),points.map(p=>p[1]),{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
      const four=graphic.items.length===4;
      const bar=<div style={{height:36,background:'#cbd5d9',gridColumn:four?'1 / -1':undefined}}><div style={{height:'100%',width:`${value/max*100}%`,background:colors[i]}}/></div>;
      return <div key={i} style={{height:four?220:145,display:'grid',gridTemplateColumns:four?'1fr 330px':'410px 1fr 330px',
        gridTemplateRows:four?'129px 36px':undefined,gap:20,alignItems:'center'}}>
        <PhoneText text={item.label} style={{fontWeight:700}}/>
        {!four && bar}
        <PhoneText text={`${Number(value.toFixed(2))} ${graphic.unit}`} style={{fontVariantNumeric:'tabular-nums',textAlign:'right'}}/>
        {four && bar}
      </div>;
    })}
    </div>
    {graphic.formula && <PhoneText text={graphic.formula} style={{position:'absolute',left:128,width:1664,bottom:145,fontWeight:700}}/>}
  </AbsoluteFill>;
};

export const VisualGraphic: React.FC<{graphic: Graphic; seconds: number}> = ({graphic,seconds}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const {type, title, items, unit, formula} = graphic;
  if(type==='data_animation') return <DataAnimation graphic={graphic}/>;
  const chart = type === 'chart';
  const maximum = chart ? Math.max(...items.map(item=>item.value!)) || 1 : 1;
  const stagger = Math.min(.38, seconds / (items.length+2));
  return <AbsoluteFill style={{background:'#e6eaed',color:'#172b35',padding:'244px 128px 196px'}}>
    <div style={{fontSize:66,fontWeight:700,lineHeight:1.16,marginBottom:56}}>{title}</div>
    <div style={{display:'flex',flexDirection:chart?'column':'row',gap:chart?22:38,alignItems:chart?'stretch':'flex-start'}}>
      {items.map((item,i)=>{
        const amount = enter(frame, i*stagger*fps, stagger*fps);
        return <div key={i} style={{flex:chart?undefined:'1 1 0',minWidth:0,opacity:.18+.82*amount}}>
          <div style={{height:8,background:colors[i],width:chart?`${item.value!/maximum*amount*100}%`:'100%'}}/>
          <div style={{display:'flex',gap:20,alignItems:'baseline',marginTop:12}}>
            {(type==='diagram' || type==='timeline') && <span style={{color:colors[i],fontSize:36}}>{i>0?'→':'●'}</span>}
            <div style={{fontSize:chart?34:46,fontWeight:700,color:colors[i]}}>{item.label}</div>
            {chart && <div style={{fontSize:34,fontVariantNumeric:'tabular-nums'}}>{item.value} {unit}</div>}
          </div>
          <div style={{marginTop:8,fontSize:chart?28:36,lineHeight:1.23,overflowWrap:'anywhere'}}>{item.detail}</div>
        </div>;
      })}
    </div>
    {formula && <div style={{position:'absolute',left:128,bottom:183,fontSize:43,fontWeight:650}}>{formula}</div>}
  </AbsoluteFill>;
};

export const ChapterTransition: React.FC<{text: string}> = ({text}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const opacity = Math.min(enter(frame,0,.2*fps), 1-enter(frame,.85*fps,.2*fps));
  return <div style={{position:'absolute',right:64,top:60,maxWidth:720,padding:'14px 24px',
    background:'#20323a',color:'white',fontSize:35,opacity}}>{text}</div>;
};
