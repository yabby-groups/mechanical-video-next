import React from 'react';
import {Img, OffthreadVideo, staticFile} from 'remotion';
import {TextLayer, TextOverlay, TextStyle} from './TextOverlay';

type Point = [number, number];
type Box = [number, number, number, number];
type Window = {box:Box;time:Point};
type Label = Window & {type:'label';text:string;anchor:string};
type Note = Window & {type:'note';text:string};
type Value = Window & {type:'value';prefix:string;unit:string;digits:number;samples:Point[]};
type Inset = Window & {type:'inset';crop:Box};
type ScreenAnchors = {fps:number;frame_count:number;samples:Record<string,(Point|null)[]>};
export type ShotInfo = {information?:(Label|Note|Value|Inset)[];screenAnchors?:ScreenAnchors;scienceLabel?:string;media:string;kind:'image'|'video';footage?:{startFrame:number;credit:string}};

const layer = (type: string):TextLayer => type==='label'?'part':type==='value'?'numeric':'principle';
const visibleItems = (shot:ShotInfo, frame:number, fps:number) => (shot.information??[]).filter(item=>{
  const time=frame/fps;
  return time>=item.time[0] && time<item.time[1] && (item.type!=='label' || !!position(shot,item.anchor,frame,fps));
});
const position = (shot:ShotInfo, anchor:string, frame:number, fps:number) => {
  const track=shot.screenAnchors!;
  const samples=track.samples[anchor];
  return samples[Math.min(track.frame_count-1,Math.floor(frame*track.fps/fps))];
};
const badgeBox:Box=[1424,288,1856,360];

export const informationRegions=(shot:ShotInfo,frame:number,fps:number) => [
  ...(shot.scienceLabel?[{layer:'auxiliary' as const,box:badgeBox}]:[]),
  ...visibleItems(shot,frame,fps).map(item=>({layer:layer(item.type),box:item.box})),
];

const sampleValue=(item:Value,frame:number,fps:number)=>{
  const progress=(frame/fps-item.time[0])/(item.time[1]-item.time[0]);
  const upper=item.samples.findIndex(sample=>sample[0]>progress);
  const first=item.samples[0], last=item.samples[item.samples.length-1];
  const value=upper===0 ? first[1] : upper===-1 ? last[1] : (()=>{
    const start=item.samples[upper-1], end=item.samples[upper];
    return start[1]+(end[1]-start[1])*(progress-start[0])/(end[0]-start[0]);
  })();
  return `${item.prefix} ${value.toFixed(item.digits)}${item.unit}`;
};

const FocusInset:React.FC<{item:Inset;shot:ShotInfo;width:number;height:number}>=({item,shot,width,height})=>{
  const [left,top,right,bottom]=item.box;
  const [cropLeft,cropTop,cropRight,cropBottom]=item.crop;
  const scale=Math.min((right-left)/((cropRight-cropLeft)*width),(bottom-top)/((cropBottom-cropTop)*height));
  const mediaStyle={position:'absolute' as const,left:-cropLeft*width*scale,top:-cropTop*height*scale,width:width*scale,height:height*scale};
  return <div style={{position:'absolute',left,top,width:(cropRight-cropLeft)*width*scale,height:(cropBottom-cropTop)*height*scale,overflow:'hidden',outline:'2px solid #fff'}}>
    {shot.kind==='image'?<Img src={staticFile(shot.media)} style={mediaStyle}/>:<OffthreadVideo src={staticFile(shot.media)} trimBefore={shot.footage?.startFrame} muted style={mediaStyle}/>}
  </div>;
};

export const ShotInformation:React.FC<{shot:ShotInfo;frame:number;fps:number;width:number;height:number;profile:TextStyle}>=({shot,frame,fps,width,height,profile})=><>
  {shot.scienceLabel && <TextOverlay text={shot.scienceLabel} layer="auxiliary" box={badgeBox} profile={profile}/>}
  {visibleItems(shot,frame,fps).map((item,index)=>{
    if(item.type==='inset')return <FocusInset key={index} item={item} shot={shot} width={width} height={height}/>;
    const point=item.type==='label'?position(shot,item.anchor,frame,fps):null;
    const text=item.type==='value'?sampleValue(item,frame,fps):item.text;
    return <React.Fragment key={index}>
      {point && <svg viewBox={`0 0 ${width} ${height}`} style={{position:'absolute',width,height,inset:0,pointerEvents:'none'}}>
        <line x1={item.box[0]+12} y1={item.box[3]-6} x2={point[0]*width} y2={point[1]*height} stroke="#26363e" strokeWidth="6"/>
        <line x1={item.box[0]+12} y1={item.box[3]-6} x2={point[0]*width} y2={point[1]*height} stroke="#e5f9ff" strokeWidth="2"/>
        <circle cx={point[0]*width} cy={point[1]*height} r="6" fill="#e5f9ff" stroke="#26363e" strokeWidth="2"/>
      </svg>}
      <TextOverlay text={text} layer={layer(item.type)} box={item.box} profile={profile}/>
    </React.Fragment>;
  })}
</>;
