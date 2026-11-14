import React, {useLayoutEffect, useRef} from 'react';
import defaults from '../../config/text-style.json';

export type TextLayer = 'subtitle'|'chapter'|'part'|'principle'|'numeric'|'auxiliary';
export type TextStyle = typeof defaults;
export const defaultTextStyle = defaults;
export type Annotation = {layer:TextLayer;text:string;start:number;end:number;box?:number[]};

export const assertOverlayRegions=(items:{layer:TextLayer;box?:number[]}[],profile:TextStyle,width:number,height:number,critical:number[][]=[])=>{
  const overlap=(a:number[],b:number[])=>Math.max(a[0],b[0])<Math.min(a[2],b[2]) && Math.max(a[1],b[1])<Math.min(a[3],b[3]);
  const boxes=items.map(item=>{
    const safe=profile[item.layer].safe_box;const b=item.box??safe;
    if(b.length!==4 || b.some(v=>!Number.isFinite(v)) || b[0]<Math.max(0,safe[0]) || b[1]<Math.max(0,safe[1]) || b[2]>Math.min(width,safe[2]) || b[3]>Math.min(height,safe[3]) || b[0]>=b[2] || b[1]>=b[3]) throw new Error('Overlay outside safe region');
    if(critical.some(c=>overlap(b,c)))throw new Error('Text covers critical mechanism');
    return b;
  });
  boxes.forEach((b,i)=>{if(boxes.slice(0,i).some(a=>overlap(a,b)))throw new Error('Overlapping text layers');});
};

// Check the actual browser font as well as the producer's Pillow measurement.
// Never shrink, wrap or clip an overlong sentence to make validation pass.
export const TextOverlay:React.FC<{text:string;layer:TextLayer;profile:TextStyle;box?:number[]}> = ({text,layer,profile,box}) => {
  const ref = useRef<HTMLDivElement>(null);
  const spec = profile[layer];
  const [left,top,right,bottom] = box ?? spec.safe_box;
  useLayoutEffect(()=>{
    const el=ref.current!;
    if (!text || /[\r\n]/.test(text)) throw new Error('Text must be one nonempty line');
    const c=document.createElement('canvas').getContext('2d')!;
    c.font=getComputedStyle(el).font;
    const measured=c.measureText(text).width+2*profile.stroke_width;
    if(measured>right-left || el.scrollWidth>el.clientWidth+1 || el.scrollHeight>el.clientHeight+1)
      throw new Error(`Text overflow (${layer}): measured=${measured}, box=${right-left}, scroll=${el.scrollWidth}x${el.scrollHeight}, client=${el.clientWidth}x${el.clientHeight}`);
    if(spec.font_size<spec.min_font_size) throw new Error('Text below minimum font size');
  },[text,layer,profile,left,right]);
  return <div ref={ref} data-text-layer={layer} style={{position:'absolute',left,top,width:right-left,height:bottom-top,
    display:'flex',alignItems:'center',justifyContent:layer==='subtitle'?'center':'flex-start',
    fontFamily:profile.font_family,fontSize:spec.font_size,fontWeight:500,lineHeight:1.15,whiteSpace:'nowrap',
    color:profile.fill,WebkitTextStroke:`${profile.stroke_width}px ${profile.stroke}`,paintOrder:'stroke fill',
    textShadow:'0 2px 5px #000'}}>{text}</div>;
};
