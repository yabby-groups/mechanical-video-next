"""Reproducible real-asset QA preprocessing benchmark; does not render production."""
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mechanical_video_next.qa_images import *


def main():
    sources=[]
    for route in ('2d','2_5d','3d'):
        files=list((ROOT/'output/nail-clipper'/route).rglob('*.png')) or list((ROOT/'output/nail-clipper'/route).glob('*-final.jpg'))
        if files: sources.append((route,files[0]))
    cad=list((ROOT/'work/cache/shots').glob('*/frames/*.png'))
    if cad: sources.append(('cad-motion',cad[0]))
    for pattern in ('*cover_3x4.png','*cover_4x3.png'):
        files=list((ROOT/'output').rglob(pattern))
        if files: sources.append(('cover',files[0]))
    before={str(p):sha(p) for _,p in sources}
    rows=[]
    for kind,p in sources:
        fn=prepare_cover_preview if kind=='cover' else prepare_image
        a=fn(p); b=fn(p)
        rows.append(dict(kind=kind,source_bytes=p.stat().st_size,first=a,repeat=b))
    sheet=prepare_contact_sheet([p for _,p in sources[:4]])
    crop=prepare_crop(sources[-1][1],(0,0,900,350))
    report=dict(rows=rows,contact_sheet=sheet,detail=crop,
        original_count=len(rows),compressed_count=len(rows),
        original_bytes=sum(r['source_bytes'] for r in rows),
        compressed_bytes=sum(r['first']['bytes'] for r in rows),
        conversion_seconds=sum(r['first']['elapsed_seconds'] for r in rows),
        repeat_hit_rate=sum(r['repeat']['cache_hit'] for r in rows)/len(rows),
        agent_actual_reads=None,actual_visual_tokens='unavailable',
        readability='UNKNOWN pending actual inspection',
        originals_unchanged=all(sha(p)==before[str(p)] for _,p in sources))
    out=ROOT/'work/qa-images/validation.json'; out.write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in {'rows','contact_sheet','detail'}},indent=2))


if __name__=='__main__': main()
