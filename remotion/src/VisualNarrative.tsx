import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

type Graphic = {
  type: 'diagram' | 'comparison' | 'chart' | 'timeline';
  title: string;
  items: {label: string; detail: string; value?: number}[];
  unit?: string;
  formula?: string;
};
export type VisualProps = {
  graphic?: Graphic;
  footage?: {startFrame: number; credit: string};
  chapter?: string;
};

const colors = ['#236c87', '#996226', '#39716a', '#586378'];
const enter = (frame: number, start: number, length: number) =>
  interpolate(frame, [start, start+length], [0, 1], {extrapolateLeft:'clamp', extrapolateRight:'clamp'});

export const VisualGraphic: React.FC<{graphic: Graphic; seconds: number}> = ({graphic,seconds}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const {type, title, items, unit, formula} = graphic;
  const chart = type === 'chart';
  const maximum = chart ? Math.max(...items.map(item=>item.value!)) : 1;
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
