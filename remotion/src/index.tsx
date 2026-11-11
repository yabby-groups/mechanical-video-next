import React from 'react';
import {AbsoluteFill, Audio, Composition, Img, OffthreadVideo, Sequence, registerRoot, staticFile, useCurrentFrame} from 'remotion';

type Cue = {start:number;end:number;text:string};
type Shot = {id:string;label:string;note:string;seconds:number;media:string;kind:'image'|'video';audio:string;accent:string;formula?:string};
type Props = {title:string;subtitle:string;shots:Shot[];cues:Cue[];duration:number;fps:number;width:number;height:number};

const ShotView:React.FC<{shot:Shot;index:number;wide:boolean}> = ({shot,index,wide}) => <AbsoluteFill>
  <div style={{position:'absolute',left:wide?60:76,top:wide?185:340,width:wide?1120:928,height:wide?720:1074,overflow:'hidden',borderRadius:28,background:'#29313f'}}>
    {shot.kind==='image' ? <Img src={staticFile(shot.media)} style={{width:'100%',height:'100%',objectFit:'contain'}}/> :
      <OffthreadVideo src={staticFile(shot.media)} muted style={{width:'100%',height:'100%',objectFit:'contain'}}/>}
  </div>
  <div style={{position:'absolute',left:wide?1240:78,top:wide?235:270,right:60,fontSize:wide?34:28,color:shot.accent,letterSpacing:2}}>0{index+1} / {shot.label}</div>
  <div style={{position:'absolute',left:wide?1240:78,top:wide?330:1444,right:wide?65:78,fontSize:wide?43:39,lineHeight:1.65,color:'#e2eaf0',fontWeight:600}}>{shot.note}</div>
  {shot.formula && <div style={{position:'absolute',left:wide?1240:78,top:wide?570:1514,right:60,color:shot.accent,fontSize:wide?40:49,fontWeight:800}}>{shot.formula}</div>}
  {wide && <div style={{position:'absolute',left:1240,right:65,top:745,color:'#9eafc0',fontSize:27,lineHeight:1.6}}>橙色 · 太阳轮输入<br/>蓝色 · 行星轮<br/>绿色 · 行星架输出</div>}
  <Audio src={staticFile(shot.audio)}/>
</AbsoluteFill>;

const Video:React.FC<Props> = p => {
  const frame = useCurrentFrame();
  const wide=p.width>p.height;
  const cue = p.cues.find(c=>frame/p.fps>=c.start && frame/p.fps<c.end);
  let from = 0;
  return <AbsoluteFill style={{background:'#0c1320',color:'white',fontFamily:'PingFang SC, sans-serif'}}>
    <div style={{position:'absolute',left:wide?64:78,top:wide?29:75,fontSize:wide?22:25,color:'#78ddcd',letterSpacing:4}}>机械结构实验室</div>
    <div style={{position:'absolute',left:wide?60:74,right:60,top:wide?72:127,fontSize:wide?61:69,fontWeight:800,lineHeight:1.18}}>{p.title}</div>
    <div style={{position:'absolute',left:wide?1240:78,top:wide?106:219,right:60,fontSize:25,color:'#9eafc0'}}>{p.subtitle}</div>
    {p.shots.map((shot,i)=>{const at=from;from+=Math.round(shot.seconds*p.fps);return <Sequence key={i} from={at} durationInFrames={Math.round(shot.seconds*p.fps)}><ShotView shot={shot} index={i} wide={wide}/></Sequence>;})}
    {cue && <div style={{position:'absolute',left:80,right:80,top:wide?945:1650,textAlign:'center',fontSize:wide?40:46,lineHeight:1.45,fontWeight:600,whiteSpace:'pre-wrap'}}>{cue.text}</div>}
    <div style={{position:'absolute',left:60,right:60,bottom:wide?48:73,height:4,background:'#243043'}}><div style={{height:4,width:`${100*frame/(p.duration*p.fps)}%`,background:'#78ddcd'}}/></div>
    <div style={{position:'absolute',left:60,bottom:wide?14:35,color:'#78899d',fontSize:wide?19:21}}>教学装配 · 原理示意 · 非接触/受力仿真</div>
  </AbsoluteFill>;
};

registerRoot(()=> <Composition id="Mechanical" component={Video} width={1920} height={1080} fps={30} durationInFrames={1080}
  defaultProps={{title:'',subtitle:'',shots:[],cues:[],duration:36,fps:30,width:1920,height:1080}}
  calculateMetadata={({props})=>({durationInFrames:Math.round(props.duration*props.fps),fps:props.fps,width:props.width,height:props.height})}/>);
