import React from 'react';
import {AbsoluteFill, Audio, Composition, OffthreadVideo, Sequence, registerRoot, staticFile, useCurrentFrame} from 'remotion';
import {TextOverlay, defaultTextStyle, TextStyle, Annotation, TextLayer, assertOverlayRegions} from './TextOverlay';
import {ShotInfo, ShotInformation, informationRegions} from './ShotInformation';
import {ChapterTransition, VisualGraphic, VisualProps} from './VisualNarrative';

type Cue = {start: number; end: number; text: string};
type Shot = ShotInfo & VisualProps & {id: string; seconds: number; audio: string};
type Props = {
  title: string; shots: Shot[]; cues: Cue[]; duration: number; fps: number; width: number; height: number;
  text_style?: TextStyle; annotations?: Annotation[]; critical_boxes?: number[][];
  fullframe_caption?: string; fullframe_credit?: string;
};

const Scene: React.FC<{shot: Shot; props: Props; start: number; last: boolean}> = ({shot,props:p,start,last}) => {
  const frame = useCurrentFrame();
  const time = (frame+start)/p.fps;
  const profile = p.text_style ?? defaultTextStyle;
  const cues = p.cues.filter(c=>time>=c.start && time<c.end);
  if(cues.length>1) throw new Error('Overlapping subtitle cues');
  const auxiliary = shot.footage?.credit ?? (!shot.scienceLabel ? (last && p.fullframe_credit) || p.fullframe_caption : undefined);
  const annotations = (p.annotations??[]).filter(a=>time>=a.start && time<a.end);
  const regions: {layer: TextLayer; box?: number[]}[] = [
    {layer:'chapter'}, ...informationRegions(shot,frame,p.fps), ...annotations
  ];
  if(auxiliary) regions.push({layer:'auxiliary'});
  if(cues.length) regions.push({layer:'subtitle'});
  assertOverlayRegions(regions,profile,p.width,p.height,p.critical_boxes);
  return <AbsoluteFill style={{background:'#223139',color:'white',fontFamily:'PingFang SC, sans-serif'}}>
    {shot.graphic ? <VisualGraphic graphic={shot.graphic} seconds={shot.seconds}/> :
      <OffthreadVideo src={staticFile(shot.media)} trimBefore={shot.footage?.startFrame} muted
        style={{width:'100%',height:'100%',objectFit:'contain'}}/>}
    <Audio src={staticFile(shot.audio)}/>
    <ShotInformation shot={shot} frame={frame} fps={p.fps} width={p.width} height={p.height} profile={profile}/>
    <div style={{position:'absolute',top:0,left:0,right:0,height:145,background:'linear-gradient(rgba(0,0,0,.23),transparent)'}}/>
    <TextOverlay text={p.title} layer="chapter" profile={profile}/>
    {shot.chapter && <ChapterTransition text={shot.chapter}/>}
    {auxiliary && <TextOverlay text={auxiliary} layer="auxiliary" profile={profile}/>}
    {cues.length===1 && <TextOverlay text={cues[0].text} layer="subtitle" profile={profile}/>}
    {annotations.map((a,i)=><TextOverlay key={i} text={a.text} layer={a.layer} box={a.box} profile={profile}/>)}
  </AbsoluteFill>;
};

const Movie: React.FC<Props> = p => {
  let from=0;
  return <AbsoluteFill>{p.shots.map((shot,i)=>{
    const start=from;
    const count=Math.round(shot.seconds*p.fps);
    from+=count;
    return <Sequence key={shot.id} from={start} durationInFrames={count}><Scene shot={shot} props={p} start={start}
      last={i===p.shots.length-1}/></Sequence>;
  })}</AbsoluteFill>;
};

registerRoot(()=> <Composition id="Mechanical" component={Movie} width={1920} height={1080} fps={30} durationInFrames={30}
  defaultProps={{title:'',shots:[],cues:[],duration:1,fps:30,width:1920,height:1080}}
  calculateMetadata={({props})=>({durationInFrames:Math.round(props.duration*props.fps),fps:props.fps,width:props.width,height:props.height})}/>);
