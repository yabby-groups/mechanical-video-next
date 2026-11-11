"""Narrow authored nail-clipper asset. Run with build123d environment, from repo.

STEP millimetres; renderer metre conversion once at export. Prescribed bending,
geometric cam-seat equation only: no contact, stress, elasticity or force solver.
"""
from pathlib import Path
import json, math, hashlib, time, shutil, copy
import numpy as np
import trimesh
from scipy.optimize import minimize_scalar
from build123d import Box, Cylinder, Compound, Plane, Polygon, extrude, export_step, import_step, Axis

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
TASK=ROOT/'output/tasks/nail-clipper-20261111'
REPORT=TASK/'cad'
P=json.loads((OUT/'parameters.json').read_text())

def dump(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def f(x):
    t=max(0.,min(1.,(x-P['rear_fixed_length'])/(P['length']-P['rear_fixed_length'])))
    return t*t*(3-2*t)

def thick(x):
    t=max(0.,min(1.,(x-47)/3))
    return P['spring_thickness']*(1-t)+P['tip_thickness']*t

def inner(x,q,side):
    t=max(0.,min(1.,(x-6)/44))
    return side*(P['open_gap']/2*(1-q)*f(x)+.7*min(f(x)/f(30),1)*(1 if x<=46 else (50-x)/4))

XS=sorted(set([float(x) for x in np.linspace(0,50,101)]+[6.,44.,47.]))

def spring(q,side):
    # Actual BREP ruled profile; same analytic profile used to deform mesh.
    points=[(x,inner(x,q,side)) for x in XS]
    points += [(x,inner(x,q,side)+side*thick(x)) for x in reversed(XS)]
    shape=extrude(Plane.XZ*Polygon(*points,align=None),amount=5,both=True)
    # Concave cutting line in plan, smooth rear corners approximated by stations.
    front=[(50,float(y)) for y in np.linspace(-5,5,25)]
    outline=[(0,-4),(1,-5)]+front+[(1,5),(0,4)]
    plan=extrude(Polygon(*outline,align=None),amount=20,both=True)
    shape=shape & plan
    shape=shape-Cylinder(P['blade_bore_radius'],20).translate((P['post_x'],0,0))
    if side==1:
        ridgepts=[(x,inner(x,q,1)+thick(x)) for x in [38.,38.5,39.,39.5,40.,40.5,41.,41.5,42.]]
        ridgepts += [(x,inner(x,q,1)+thick(x)+.8) for x in [42.,41.5,41.,40.5,40.,39.5,39.,38.5,38.]]
        shape=shape+extrude(Plane.XZ*Polygon(*ridgepts,align=None),amount=1,both=True)
    return shape

def flange_seat(q):
    xx=sorted(set([P['post_x']-P['post_head_radius'],P['post_x']+P['post_head_radius']]+[x for x in XS if abs(x-P['post_x'])<P['post_head_radius']]))
    return min(inner(x,q,-1)-thick(x) for x in xx)

def pivot(q):return P['pivot_initial_z']+flange_seat(q)-flange_seat(0)

def seat(theta,q):
    x=44+P['cam_local_x']*math.cos(theta)+P['cam_local_z']*math.sin(theta)
    z=pivot(q)-P['cam_local_x']*math.sin(theta)+P['cam_local_z']*math.cos(theta)
    r=P['cam_radius']
    surface=lambda xx:float(np.interp(xx,XS,[inner(a,q,1)+thick(a) for a in XS]))
    fun=lambda xx:-(surface(xx)+math.sqrt(max(0,r*r-(xx-x)**2)))
    opt=minimize_scalar(fun,bounds=(x-r,x+r),method='bounded',options={'xatol':1e-12})
    return z+opt.fun

def angle(q):
    lo,hi=-.2,.8
    assert seat(lo,q)<0<seat(hi,q)
    for _ in range(60):
        mid=(lo+hi)/2
        if seat(mid,q)>0:hi=mid
        else:lo=mid
    return (lo+hi)/2

def post():
    bottom=flange_seat(0)
    head=Cylinder(P['post_head_radius'],.5).translate((P['post_x'],0,bottom-.25))
    shaft=Cylinder(.7,pivot(0)+1.15-bottom).translate((P['post_x'],0,(pivot(0)+1.15+bottom)/2))
    roof=Box(2.5,2, .55).translate((45.05,0,pivot(0)+.6+.275))
    return head+shaft+roof

def lever():
    bar=Box(37,8,1.2).translate((-20.5,0,.6))
    bridge=Box(3.3,1,1.2).translate((-1.4,3,.6))+Box(3.3,1,1.2).translate((-1.4,-3,.6))
    axle=Cylinder(P['axle_radius'],8,rotation=(90,0,0))
    shape=bar+bridge+axle
    for y in [-2.7,2.7]:
        cam=Cylinder(P['cam_radius'],2.6,rotation=(90,0,0)).translate((-4,y,-1.6))
        neck=Box(1,2.6,2.2).translate((-4,y,-.5))
        shape=shape+cam+neck
    return shape

def parts_at(q):
    return {'lower_blade_spring':spring(q,-1),'upper_blade_spring':spring(q,1),
            'pull_post_axle':post().translate((0,0,pivot(q)-pivot(0))),
            'operating_lever_cam':lever().rotate(Axis.Y,math.degrees(angle(q))).translate((44,0,pivot(q)))}

def bounds(s):
    b=s.bounding_box();return [[b.min.X,b.min.Y,b.min.Z],[b.max.X,b.max.Y,b.max.Z]]

def common(a,b):
    aa,bb=bounds(a),bounds(b)
    if any(min(aa[1][i],bb[1][i])-max(aa[0][i],bb[0][i])<1e-8 for i in range(3)):return 0.
    s=a.intersect(b)
    return 0. if s is None else sum(x.volume for x in s) if isinstance(s,list) else s.volume

def mesh(s):
    vv,ff=s.tessellate(.08,.12)
    return np.array([[v.X,v.Y,v.Z] for v in vv]),np.array(ff)

def main():
    start=time.monotonic()
    research=TASK/'mechanical-research/research.v1.json'
    assert research.exists(),'MechanicalResearch evidence must exist before final geometry'
    assert shutil.disk_usage(ROOT).free>3*1024**3
    REPORT.mkdir(parents=True,exist_ok=True)
    base=parts_at(0)
    local={'lower_blade_spring':base['lower_blade_spring'],'upper_blade_spring':base['upper_blade_spring'],
           'pull_post_axle':post(),'operating_lever_cam':lever()}
    for n,s in base.items():s.label=n
    export_step(Compound(label='nail_clipper_original_teaching',children=list(base.values())),OUT/'assembly.step')
    rt=import_step(OUT/'assembly.step')
    inventory=[];meshes=[];scene=trimesh.Scene();vmap={}
    colors={'spring_steel':[.48,.53,.59],'lever_steel':[.64,.67,.72],'post_brass':[.63,.45,.20]}
    for name,s in local.items():
        vv,ff=mesh(s);vmap[name]=vv
        material='spring_steel' if 'spring' in name else 'post_brass' if 'post' in name else 'lever_steel'
        loc=[44*.001,0,pivot(0)*.001] if name=='operating_lever_cam' else [0,0,0]
        rot=[0,angle(0),0] if name=='operating_lever_cam' else [0,0,0]
        meshes.append({'name':name,'vertices':(vv*.001).tolist(),'faces':ff.tolist(),'material':material,'location':loc,'rotation_euler':rot})
        tm=trimesh.Trimesh(vv*.001,ff,process=True);tm.visual.vertex_colors=[int(c*255) for c in colors[material]]+[255]
        tf=trimesh.transformations.rotation_matrix(rot[1],[0,1,0]);tf[:3,3]=loc
        scene.add_geometry(tm,node_name=name,geom_name=name,transform=tf)
        inventory.append({'name':name,'valid':s.is_valid,'solid_count':len(s.solids()),'volume_mm3':s.volume,'bounds_world_mm':bounds(base[name]),'mesh_watertight':tm.is_watertight,'mesh_volume_mm3':abs(tm.volume)*1e9,'local_frame':{'origin_mm':[0,0,0] if name!='operating_lever_cam' else [44,0,pivot(0)],'rotation_y_rad':rot[1]},'datums':{'rear_weld_mm':[0,0,0],'jaw_center_mm':[50,0,0],'post_axis_mm':[44,0,0],'cam_center_local_mm':[-4,0,-1.6]} ,'physical_constraints':'Prescribed seat relation and two-spring bending; no persisted dynamics joints'})
    scene.export(OUT/'assembly.glb')
    assembly={'id':'nail-clipper-cad-v3','kind':'source-mesh-assembly-v1','source_files':[],'units':'m','meshes':meshes,'materials':{k:{'color':v,'metallic':.8,'roughness':.28} for k,v in colors.items()},'required_parts':list(local),'motion':{'template':'data-keyframes-v1'},'unverified':['Material forces','Continuous contact','Manufacturing fit','Yaw retention','Visual acceptance'],'mesh_pose_contract':'local vertices; importer applies explicit location/rotation_euler'}
    dump(OUT/'assembly.json',assembly);dump(OUT/'inventory.json',{'count':len(inventory),'parts':inventory})
    tracks=[];mesh_tracks=[]
    # 121 poses (including endpoints) permit separate 4s close/open tests.
    for name in local:
        poses=[]
        for i in range(121):
            q=i/120
            if 'spring' in name:
                vv=vmap[name].copy();side=1 if name.startswith('upper') else -1
                vv[:,2]-=side*q*np.array([f(x) for x in vv[:,0]])
                poses.append({'progress':q,'vertices':(vv*.001).tolist()})
            else:
                loc=[44*.001,0,pivot(q)*.001] if name=='operating_lever_cam' else [0,0,(pivot(q)-pivot(0))*.001]
                rot=[0,angle(q),0] if name=='operating_lever_cam' else [0,0,0]
                poses.append({'progress':q,'location':loc,'rotation_euler':rot})
        (mesh_tracks if 'spring' in name else tracks).append({'object':name,'poses':poses})
    motion={'id':'close','template':'motion','seconds':4,'tracks':tracks,'mesh_tracks':mesh_tracks,'scope':'原理示意：两片连续规定弯曲；销随下片上移，凸轮几何压点约束；非接触或弹性材料仿真'}
    dump(OUT/'motion.json',motion)
    # Native BREP all-pair samples: endpoints + every eighth of final travel.
    samples=[]
    for q in np.linspace(0,1,17):
        ps=parts_at(float(q));names=list(ps);hits=[]
        for i,a in enumerate(names):
            for b in names[i+1:]:
                v=common(ps[a],ps[b])
                if v>1e-6:hits.append({'parts':[a,b],'volume_mm3':v})
        samples.append({'q':float(q),'valid_single_solids':all(s.is_valid and len(s.solids())==1 for s in ps.values()),'intersections':hits,'cam_seat_residual_mm':seat(angle(q),q)})
    # True native longitudinal Boolean half-section: all components, not transparency.
    section=copy.deepcopy(assembly);section['id']+='-section'
    for item in section['meshes']:
        s=local[item['name']]-Box(200,50,100).translate((0,25,0))
        vv,ff=mesh(s);item['vertices']=(vv*.001).tolist();item['faces']=ff.tolist()
    section['section_geometry']={'method':'Native CAD Boolean remove y>=0 half-space at open pose','scope':'教学纵剖切，保留所有零件后半侧，不代表真实拆卸'}
    dump(OUT/'section-assembly.json',section)
    finger=lambda q: pivot(q)-P['finger_local_x']*math.sin(angle(q))
    report={'schema':'nail-clipper-cad-validation-v1','status':'NEEDS_REVIEW','units':'mm','numerical_status':'PASS' if all(x['valid'] and x['solid_count']==1 and x['volume_mm3']>0 for x in inventory) and len(rt.solids())==4 and not any(s['intersections'] for s in samples) else 'FAIL','independent_solids':inventory,'step_roundtrip_solid_count':len(rt.solids()),'all_pair_native_brep_motion_samples':samples,'sample_count':len(samples),'maximum_intersection_mm3':max([h['volume_mm3'] for s in samples for h in s['intersections']]+[0]),'motion_evidence':{'open_angle_deg':math.degrees(angle(0)),'closed_angle_deg':math.degrees(angle(1)),'finger_vertical_travel_mm':finger(0)-finger(1),'jaw_gap_travel_mm':2.,'post_vertical_travel_mm':pivot(1)-pivot(0),'blade_rear_fixed_deflection_mm':0.,'geometric_displacement_ratio':(finger(0)-finger(1))/2,'physical_force_ratio':'UNKNOWN; ideal lever trend only, not force measurement'},'force_path':['finger -> operating lever long arm','lever integral cam -> upper spring near x40','lever bearing -> pull post at x44','post bottom flange -> lower spring upward','both springs -> rear welded region and opposed jaw edges'],'assumptions':[P['dimension_source'],P['deformation'],'Rear welded interface represented by touching rear plate faces, no weld bead or fracture model','Cam as cylindrical lobe, geometric vertical seat equation ignores surface normal/friction; actual solid contacts sampled independently','Oversized shaft holes and cross axle use teaching clearances, no manufacturing claim','Patent lateral anti-yaw lugs omitted; yaw constraint UNKNOWN'],'repair_history':[{'round':2,'defect_keys':['clipper.lever_solid_disconnected','clipper.post_hook_topology','clipper.post_leaf_interference','clipper.cam_leaf_interference','clipper.yaw_guides_missing','clipper.closed_body_collapse'],'baseline':'assets/assemblies/nail-clipper-cad-v1/validation.json','strategy':'Final round2: correct pivotX in cam seat; split lever bridge into side prongs connected crossbar and clear hook roof; retained body spacing and turned integral beveled lips. Round1 evidence preserved v2/validation.json.'}],'physical_simulation':False,'runtime_seconds':time.monotonic()-start,'cache_hit':False,'temporary_space_bytes':None,'tokens':None,'cost':None}
    dump(REPORT/'validation.round2.json',report);dump(OUT/'validation.json',report)
    diagnostics(assembly,section,motion)
    manifest={'schema':'cad-handoff-v1','source':str((OUT/'generate.py').relative_to(ROOT)),'parameters':str((OUT/'parameters.json').relative_to(ROOT)),'step':str((OUT/'assembly.step').relative_to(ROOT)),'glb':str((OUT/'assembly.glb').relative_to(ROOT)),'inventory':str((OUT/'inventory.json').relative_to(ROOT)),'validation':str((OUT/'validation.json').relative_to(ROOT)),'assembly':str((OUT/'assembly.json').relative_to(ROOT)),'motion':str((OUT/'motion.json').relative_to(ROOT)),'research':str(research.relative_to(ROOT)),'hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*OUT.glob('*'),research] if p.is_file()}}
    dump(REPORT/'handoff.v3.json',manifest)
    print(json.dumps({'numerical_status':report['numerical_status'],'solid_count':len(rt.solids()),'max_intersection_mm3':report['maximum_intersection_mm3'],'runtime_seconds':report['runtime_seconds']}))

def diagnostics(assembly,section,motion):
    style={'visual_profile':'printer-ep03-studio-v1','camera_view':'oblique','camera_direction':[.1,-1,.45],'camera_roll':0,'studio_lighting':{'scale_to_subject':True,'floor_gap':.002}}
    for label in ['assembly','exploded','section','close','open']:
        source=section if label=='section' else assembly
        shot=dict(style,template='overall' if label in ['assembly','section'] else 'motion',seconds=1 if label in ['assembly','section'] else 4)
        if label in ['close','open']:
            shot.update(copy.deepcopy(motion));shot.update(style)
            if label=='open':
                for track in shot['tracks']+shot['mesh_tracks']:
                    track['poses'].reverse()
                    for i,pose in enumerate(track['poses']):pose['progress']=i/(len(track['poses'])-1)
        if label=='exploded':
            shot['tracks']=[]
            for i,item in enumerate(assembly['meshes']):
                pose={k:copy.deepcopy(item[k]) for k in ['location','rotation_euler']};end=copy.deepcopy(pose)
                end['location'][2]+=[-.010,.010,.025,.040][i]
                shot['tracks'].append({'object':item['name'],'poses':[dict(progress=0,**pose),dict(progress=1,**end)]})
            shot['scope']='Exploded layout offsets, not mechanically verified removal paths'
        config={'id':'nail-clipper-diagnostic-v3-'+label,'asset':source['id'],'assembly_config':str((OUT/('section-assembly.json' if label=='section' else 'assembly.json')).relative_to(ROOT)),'title':'指甲剪自主CAD诊断','subtitle':'原理示意 · 规定弯曲 · 非接触仿真','voice':'Neil','channel':'视频号','narration_profile':'config/narration-neil.json','render':{'width':1920,'height':1080,'fps':30,'video':'h264','audio':'aac','framing':'fullframe','preview_native':False},'components':assembly['required_parts'],'motion_template':'data-keyframes-v1','explosion_sequence':[],'local_preview_shots':[label],'shots':{label:shot},'storyboard':[{'id':label,'shot':label,'seconds':shot['seconds'],'narration':['原理示意'],'subtitles':['原理示意']}]}
        dump(ROOT/'config'/('nail-clipper-diagnostic-v3-'+label+'.json'),config)

if __name__=='__main__':main()
