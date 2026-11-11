"""Independent Blender evaluation of template keyframes, not just the formula constants."""
import json
import math
from pathlib import Path
import sys
import bpy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'blender'))
import scene as adapter

def main():
    asset=Path(sys.argv[sys.argv.index('--')+1])
    adapter.eas.register()
    bpy.ops.wm.open_mainfile(filepath=str(asset))
    cfg=json.loads((ROOT/'config/assembly.json').read_text())
    fps=30
    count=241
    adapter.prepare_motion(cfg,count,fps)
    data=[]
    for f in range(1,count+1):
        bpy.context.scene.frame_set(f)
        s=bpy.data.objects['Sun']
        c=bpy.data.objects['Carrier']
        r=bpy.data.objects['Ring']
        planets=[bpy.data.objects[f'Planet_{i+1}'] for i in range(3)]
        values={'f':f,'sun':s.rotation_euler.z,'carrier':c.rotation_euler.z,'ring':r.rotation_euler.z}
        for p in planets:
            d=math.hypot(p.matrix_world.translation.x,p.matrix_world.translation.y)
            assert abs(d-1.8)<1e-5
            # The centres follow the carrier, in world coordinates.
        for i,p in enumerate(planets):
            a=2*math.pi*i/3+c.rotation_euler.z
            assert abs(p.matrix_world.translation.x-1.8*math.cos(a))<1e-5
            assert abs(p.matrix_world.translation.y-1.8*math.sin(a))<1e-5
        values['planet']=planets[0].rotation_euler.z
        data.append(values)
    worst=0
    for a,b in zip(data,data[1:]):
        ds=b['sun']-a['sun']; dc=b['carrier']-a['carrier']; dr=b['ring']-a['ring']; dp=b['planet']-a['planet']
        residuals=[18*(ds-dc)+54*(dr-dc),18*(ds-dc)+18*(dp-dc)]
        worst=max(worst,*map(abs,residuals))
        assert max(map(abs,residuals))<2e-5
        assert abs(dr)<1e-8
    result={'status':'PASS','evaluated_frame_count':len(data),'max_finite_difference_willis_residual':worst,
        'sun_total_turns':data[-1]['sun']/(2*math.pi),'carrier_total_turns':data[-1]['carrier']/(2*math.pi),
        'unverified':['Tooth contact','Forces','Efficiency','Manufacturability']}
    (ROOT/'output/motion-independent-check.json').write_text(json.dumps(result,indent=2))

if __name__=='__main__': main()
