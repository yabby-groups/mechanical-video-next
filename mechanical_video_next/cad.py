"""STEP-first authored molded-tooth zipper principle assembly.

mm, XY tape plane, +Y opening branches, +Z thickness. Prescribed kinematics,
not simulation. Retaining shoulders resist planar transverse pulling only.
"""
from pathlib import Path
import json, math, hashlib, time, shutil, argparse
import numpy as np
from build123d import Box, Cylinder, Compound, Axis, Align, Polygon, Ellipse, extrude, fillet, export_step, import_step
import trimesh
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/assemblies/zipper-parametric-v3'
REPORT=ROOT/'output/tasks/zipper-cad-20261111/cad/v3'

def dump(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,indent=2,ensure_ascii=False))
def vol(x):
    if x is None:return 0.
    if isinstance(x,list):return sum(vol(y) for y in x)
    return x.volume

def tooth(p):
    # Repair strategy2: smooth elliptical bulb removes the former shoulder corners.
    # Keep same maximum head/neck widths; extend the neck into bulb for a single solid.
    neck=Box(p['neck_length']+p['neck_head_overlap'],p['neck_width'],p['tooth_thickness'],align=(Align.MIN,Align.CENTER,Align.CENTER))
    head=extrude(Ellipse(p['head_length']/2,p['head_width']/2),amount=p['tooth_thickness']).translate((p['neck_length']+p['head_length']/2,0,-p['tooth_thickness']/2))
    return neck+head

def path(q,slider,side,p):
    s=q-slider; L=p['guide_arc_length']; angle=math.radians(p['branch_angle_degrees']); k=angle/L
    if s<=0:x,y,theta=0,s,0
    elif s<L:theta=k*s; x=(1-math.cos(theta))/k; y=math.sin(theta)/k
    else:theta=angle; x=(1-math.cos(angle))/k+(s-L)*math.sin(angle); y=math.sin(angle)/k+(s-L)*math.cos(angle)
    rot=theta if side==-1 else math.pi-theta
    return [side*(p['root_half_spacing']+x),slider+y,0],rot

def place(shape,loc,angle):return shape.rotate(Axis.Z,math.degrees(angle)).translate(loc)
def bbox(s):
    b=s.bounding_box();return [[b.min.X,b.min.Y,b.min.Z],[b.max.X,b.max.Y,b.max.Z]]
def overlapping_bbox(a,b):
    return all(min(a[1][i],b[1][i])-max(a[0][i],b[0][i])>1e-7 for i in range(3))

def prism(points,height):
    points=[tuple(float(v) for v in pt) for pt in points]
    area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1]))
    if area<0:points=list(reversed(points))
    return extrude(Polygon(*points,align=None),amount=height)

def ribbon_vertices(slider,side,p):
    n=round((p['tape_q_max']-p['tape_q_min'])/p['tape_station_pitch'])+1
    stations=[]
    for q in np.linspace(p['tape_q_min'],p['tape_q_max'],n):
        loc,a=path(float(q),slider,side,p)
        stations.append([[loc[0]+d*math.cos(a),loc[1]+d*math.sin(a)] for d in [p['tape_heel_offset']-p['tape_width']/2,p['tape_heel_offset']+p['tape_width']/2]])
    return stations

def ribbon(slider,side,p):
    st=ribbon_vertices(slider,side,p)
    polygon=[v[0] for v in st]+[v[1] for v in reversed(st)]
    return prism(polygon,p['tape_thickness']).translate((0,0,p['tape_bottom_z']))

def ribbon_mesh(slider,side,p):
    st=ribbon_vertices(slider,side,p);n=len(st)
    vv=[[x,y,z] for z in [p['tape_bottom_z'],p['tape_bottom_z']+p['tape_thickness']] for pair in st for x,y in pair]
    faces=[]
    def quad(a,b,c,d):faces.extend([[a,b,c],[a,c,d]])
    for i in range(n-1):
        a=2*i;b=a+2;top=2*n
        quad(a,b,b+1,a+1);quad(a+top,a+1+top,b+1+top,b+top)
        quad(a,a+top,b+top,b);quad(a+1,b+1,b+1+top,a+1+top)
    quad(0,1,1+2*n,2*n);quad(2*n-2,4*n-2,4*n-1,2*n-1)
    mesh=trimesh.Trimesh(vv,faces,process=False);mesh.fix_normals()
    return np.array(mesh.vertices)*.001,np.array(mesh.faces)

def make_parts(p):
    t=tooth(p); parts=[]
    def add(name,shape,loc,angle=0,material='steel',motion=None):
        shape.label=name
        parts.append(dict(name=name,shape=shape,loc=loc,angle=angle,material=material,motion=motion))
    for side,label in [(-1,'L'),(1,'R')]:
        for i in range(p['count_per_row']):
            q=p['pitch']*(i+(0 if side==-1 else .5));loc,a=path(q,p['slider_start'],side,p)
            add(f'tooth_{label}_{i:02}',t,loc,a,'polymer',('tooth',q,side))
    for side,label in [(-1,'L'),(1,'R')]:
        add('tape_'+label,ribbon(p['slider_start'],side,p),[0,0,0],0,'tape',('ribbon',side))
    # Upper/lower plates flank an actual open Y guide, rather than a solid slider block.
    plate=prism([(-10,-3),(10,-3),(32,20),(-32,20)],.55)
    add('slider_lower',plate.translate((0,0,-1.45)),[0,p['slider_start'],0],material='steel',motion=('slider',))
    upper=plate.translate((0,0,.9))
    for side in [-1,1]:
        ear=Box(p['crown_width'],1.8,p['crown_top']-1.45,align=(Align.CENTER,Align.CENTER,Align.MIN)).translate((side*p['crown_x'],p['crown_y'],1.45))
        bore=Cylinder(p['pin_bore_radius'],2,rotation=(0,90,0)).translate((side*p['crown_x'],p['crown_y'],p['crown_z_axis']))
        upper=upper+(ear-bore)
    add('slider_upper',upper,[0,p['slider_start'],0],material='steel',motion=('slider',))
    wedge=prism([(0,12),(-3,20),(3,20)],1.8).translate((0,0,-.9))
    add('slider_wedge',wedge,[0,p['slider_start'],0],material='steel',motion=('slider',))
    # Outside walls follow the splayed tape-root envelope; guide gaps remain open at ends.
    for side,label in [(-1,'L'),(1,'R')]:
        pts=[(side*10,-3),(side*32,20),(side*31.5,20),(side*9.5,-3)]
        wall=prism(pts,1.8).translate((0,0,-.9))
        add('slider_flange_'+label,wall,[0,p['slider_start'],0],material='steel',motion=('slider',))
    pull=(Box(5,8,.55)-Box(3.3,5.8,1)).translate((0,4,2.8))
    barrel=Cylinder(.85,5.4,rotation=(0,90,0)).translate((0,p['crown_y'],p['crown_z_axis']))
    pull=pull+barrel
    pull=pull-Cylinder(p['pull_bore_radius'],9,rotation=(0,90,0)).translate((0,p['crown_y'],p['crown_z_axis']))
    add('pull',pull,[0,p['slider_start'],0],material='gold',motion=('slider',))
    pin=Cylinder(p['pin_radius'],8.2,rotation=(0,90,0)).translate((0,p['crown_y'],p['crown_z_axis']))
    for side in [-1,1]:pin=pin+Cylinder(.7,.3,rotation=(0,90,0)).translate((side*3.95,p['crown_y'],p['crown_z_axis']))
    add('pull_pin',pin,[0,p['slider_start'],0],material='gold',motion=('slider',))
    for i,side in enumerate([-1,1]):
        stoploc,stopa=path(36,p['slider_start'],side,p)
        add('top_stop_'+str(i),Box(1.1,1.3,1.2),stoploc,stopa,material='gold',motion=('tooth',36,side))
    add('bottom_stop',Box(8.8,1.4,1.2),[0,-22,0],material='gold')
    return parts

def pose(item,slider,p):
    m=item['motion']
    if m and m[0]=='ribbon':return [0,0,0],0
    if m and m[0]=='tooth':return path(m[1],slider,m[2],p)
    if m:return [0,slider,0],0
    return item['loc'],item['angle']

def intersections(parts,slider,p):
    shapes=[ribbon(slider,x['motion'][1],p) if x['motion'] and x['motion'][0]=='ribbon' else place(x['shape'],*pose(x,slider,p)) for x in parts]
    bs=[bbox(x) for x in shapes];hits=[]
    for i,a in enumerate(shapes):
        for j in range(i+1,len(shapes)):
            if not overlapping_bbox(bs[i],bs[j]):continue
            v=vol(a.intersect(shapes[j]))
            if v>1e-6:hits.append({'parts':[parts[i]['name'],parts[j]['name']],'volume_mm3':v})
    return hits

def generate(p,asset_id='zipper-parametric-v3'):
    start=time.monotonic();OUT.mkdir(parents=True,exist_ok=True);REPORT.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(ROOT).free<3*1024**3:raise RuntimeError('free disk below 3GiB')
    parts=make_parts(p);initial=[place(x['shape'],x['loc'],x['angle']) for x in parts]
    for s,x in zip(initial,parts):s.label=x['name']
    assembly=Compound(label='zipper_parametric_v1',children=initial)
    step=OUT/(asset_id+'.step');export_step(assembly,step)
    roundtrip=import_step(step)
    meshes=[];scene=trimesh.Scene();inventory=[]
    colors={'steel':(150,163,176,255),'polymer':(210,153,48,255),'tape':(35,55,74,255),'gold':(200,166,91,255)}
    for x,s in zip(parts,initial):
        if x['motion'] and x['motion'][0]=='ribbon':vv,ff=ribbon_mesh(p['slider_start'],x['motion'][1],p)
        else:
            vertices,faces=x['shape'].tessellate(.12,.15)
            vv=np.array([[v.X,v.Y,v.Z] for v in vertices])*.001;ff=np.array(faces)
        transform=trimesh.transformations.rotation_matrix(x['angle'],[0,0,1]);transform[:3,3]=np.array(x['loc'])*.001
        mesh=trimesh.Trimesh(vv,ff,process=False);mesh.visual.vertex_colors=colors[x['material']]
        scene.add_geometry(mesh,node_name=x['name'],geom_name=x['name'],transform=transform)
        # Inline renderer importer sets initial locations separately, preserving local frames.
        meshes.append({'name':x['name'],'vertices':vv.tolist(),'faces':ff.tolist(),'material':x['material'],'location':(np.array(x['loc'])*.001).tolist(),'rotation_euler':[0,0,x['angle']]})
        inventory.append({'name':x['name'],'units':'mm','valid':x['shape'].is_valid,'solid_count':len(x['shape'].solids()),'volume_mm3':x['shape'].volume,'bounds_world_mm':bbox(s),'local_frame':{'origin':'heel datum / component construction origin','translation_mm':x['loc'],'rotation_z_rad':x['angle']},'datums':{'attachment':[0,0,-.6] if x['name'].startswith('tooth') else [0,0,0]},'independent_mesh':True})
    scene.export(OUT/'assembly.glb')
    cfg={'id':asset_id,'kind':'source-mesh-assembly-v1','source_files':[],'meshes':meshes,'materials':{k:{'color':[c/255 for c in v[:3]],'metallic':.7 if k in ['steel','gold'] else .05,'roughness':.34} for k,v in colors.items()},'required_parts':[x['name'] for x in parts],'unverified':['Physical contact forces','Tape elasticity','Out-of-plane retention','Manufacturing fit','Visual acceptance'],'motion':{'template':'data-keyframes-v1'},'units':'m','mesh_pose_contract':'vertices local; importer MUST assign mesh location and rotation_euler'}
    dump(OUT/'assembly.json',cfg)
    section=dict(cfg);section['id']=asset_id+'-section';section['meshes']=[dict(m) for m in meshes]
    upper=next(x for x in parts if x['name']=='slider_upper')
    cut=upper['shape']-Box(40,50,10).translate((20,8,0))
    vertices,faces=cut.tessellate(.12,.15)
    spec=next(m for m in section['meshes'] if m['name']=='slider_upper')
    spec['vertices']=[[v.X*.001,v.Y*.001,v.Z*.001] for v in vertices];spec['faces']=[list(f) for f in faces]
    section['section_geometry']={'component':'slider_upper','method':'native CAD Boolean cut x>=0; retains left half for actual section edge','cut_valid':cut.is_valid,'cut_volume_mm3':cut.volume}
    dump(OUT/'section-assembly.json',section)
    dump(OUT/'inventory.json',{'parts':inventory,'count':len(parts),'source':'build123d/OpenCASCADE authored solids','primary':asset_id+'.step'})
    tracks=[];mesh_tracks=[]
    frames=p['motion_seconds']*p['fps']
    for x in parts:
        if not x['motion']:continue
        if x['motion'][0]=='ribbon':
            poses=[]
            for frame in range(frames):
                progress=frame/(frames-1);phase=1-abs(2*progress-1);slider=p['slider_start']+(p['slider_end']-p['slider_start'])*phase
                vv,_=ribbon_mesh(slider,x['motion'][1],p);poses.append({'progress':progress,'vertices':vv.tolist()})
            mesh_tracks.append({'object':x['name'],'poses':poses})
            continue
        poses=[]
        for frame in range(frames):
            progress=frame/(frames-1);phase=1-abs(2*progress-1);slider=p['slider_start']+(p['slider_end']-p['slider_start'])*phase
            loc,a=pose(x,slider,p)
            poses.append({'progress':progress,'location':[v*.001 for v in loc],'rotation_euler':[0,0,a]})
        tracks.append({'object':x['name'],'poses':poses})
    shot={'id':'cad-close-open','template':'motion','seconds':p['motion_seconds'],'camera_view':'oblique','camera_direction':[0,-.4,1],'tracks':tracks,'mesh_tracks':mesh_tracks,'scope':p['teaching_scope'],'camera_roll':0}
    dump(OUT/'motion.json',shot)
    # Native BREP solids, broadphase AABBs followed by exact Boolean common volume.
    sampled=[]
    for index in range(2*frames-1):
        progress=index/(2*(frames-1));phase=1-abs(2*progress-1);slider=p['slider_start']+(p['slider_end']-p['slider_start'])*phase
        sampled.append({'phase':phase,'slider_mm':slider,'intersections':intersections(parts,slider,p)})
    # Isolate an interior closed pair: opposing broad heads obstruct a transverse pull.
    t=tooth(p);left=place(t,[-p['root_half_spacing'],8,0],0);right=place(t,[p['root_half_spacing'],10,0],math.pi)
    probe=[]
    for dx in [0,-.5,-1,-1.25,-1.5,-1.75,-2]:probe.append({'left_displacement_mm':dx,'intersection_mm3':vol(left.translate((dx,0,0)).intersect(right))})
    allhits=[(f['phase'],h) for f in sampled for h in f['intersections']]
    report={'schema':'cad-validation-v1','scope':p['teaching_scope'],'status':'NEEDS_REVIEW','all_positive_valid_single_solids':all(x['valid'] and x['solid_count']==1 and x['volume_mm3']>0 for x in inventory),'solid_count':len(parts),'step_roundtrip_solid_count':len(roundtrip.solids()),'step_roundtrip_count_match':len(roundtrip.solids())==len(parts),'initial_unintended_intersections':sampled[0]['intersections'],'dynamic_samples':sampled,'dynamic_intersection_sample_count':len(sampled),'dynamic_intersection_pairs_count':len(allhits),'transverse_retention_probe':probe,'transverse_retention_observed':probe[0]['intersection_mm3']<1e-6 and any(x['intersection_mm3']>1e-5 for x in probe[1:]),'limitations':['Continuous supports are prescribed thin CAD ribbons, not elastic fabric simulation','Tooth root touches support surface by rigid attachment convention; no beaded anchorage fit','Sampled collisions cover96 keyframe poses and95temporal midpoints over close/reverse; no continuous collision proof','No CAD joints are persisted as physical constraints; explicit local datums and generated placements are used'], 'out_of_plane_retention':'UNKNOWN - planar profile lacks support wings; no z-retention claim','physical_simulation':False,'runtime_seconds':time.monotonic()-start,'cache_hit':False,'temporary_space_bytes':None,'output_artifact_bytes':sum(f.stat().st_size for f in OUT.iterdir() if f.is_file()),'free_disk_bytes':shutil.disk_usage(ROOT).free,'token_count':None,'cost':None,'repair_history':[{'defect_key':'cad-zipper-guided-tooth-intersection','baseline':'rectangular 3mm head width, exact BREP observed 0.130mm3 intersection at slider -2,2,...26mm','round':1,'strategy':'reduce head width to2.6mm; retain 0.6mm opposed head y overlap; round profile edges','result':'Sparse25samples missed interleaved tooth collisions; independent191sample QA found56hits/max0.0344212mm3. Not fixed by width reduction.'},{'defect_key':'cad-slider-guide-envelope','baseline':'209 hits over25samples; includes signed polygon engineering bug, undersized outer envelope, tape support patch overlaps','round':1,'strategy':'enforce CCW extrusion; shorten support patches; top stops follow tape; pull pin hole','result':'70 hits over25samples, saved repair1-assembly-intersections.json'},{'defect_key':'cad-slider-guide-envelope','round':2,'strategy':'widen outer walls and plates, narrow wedge and delay tip to y12, place bottom stop beyond slider start','result':'0 housing hits over191samples; measured exact BREP common-volume threshold1e-6 mm3; not continuous proof'},{'defect_key':'cad-zipper-guided-tooth-intersection','round':2,'strategy':'replace rounded rectangular head by elliptical retaining bulb, same max width/length; neck overlaps bulb by0.3mm','result':'0 hits over191 keyframe and midpoint states;42valid solids; positive transverse retaining probe at-1.75mm; budget exhausted'}],'prior_route_budget':'Earlier mesh-guidance route remains exhausted; CAD rebuild explicitly authorized; no reset of previous defect acceptance.'}
    report['numerical_status']='PASS' if report['all_positive_valid_single_solids'] and report['step_roundtrip_count_match'] and not allhits and report['transverse_retention_observed'] else 'FAIL'
    report['repair_history'].extend([{'defect_key':'cad-pull-pin-anchor','round':1,'result':'added ears/barrel; interference upper/pull1.722mm3,upper/pin0.01047mm3; first candidate failed'},{'defect_key':'cad-pull-pin-anchor','round':2,'strategy':'move supporting ears outside ring to x+-3.2, bore clearance0.02mm and axial capture heads; extend hinge barrel','result':'FAIL:191states upper/pull0.8093692071mm3 and upper/pin0.0104688825mm3. Axis2.1 gives barrelbottom1.25/headbottom1.4 belowplatetop1.45. Stop afterround2.'},{'defect_key':'cad-stringer-stop-connection','round':1,'result':'continuous station ribbons attempted; polygon list point parsing yielded zero volume, failed'},{'defect_key':'cad-stringer-stop-connection','round':2,'strategy':'normalize profile vertices to native float tuples; exact CAD ribbon and same-boundary closed mesh','result':'28validsolids STEP28; continuousribbons watertight and CAD/meshvolume36.7233394224mm3 each; zero ribbon collisions; stops/root tangent gap~1.11e-16mm. Rigidattachment only.'}])
    dump(OUT/'validation.json',report);dump(REPORT/'validation.json',report)
    dump(REPORT/'manifest.json',{'parameters':p,'generator':'mechanical_video_next/cad.py','files':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in OUT.iterdir() if f.is_file()},'units':'CAD mm; rendered meshes/transforms m','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'parameters_sha256':hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest(),'environment_sha256':hashlib.sha256((ROOT/'requirements-cad.txt').read_bytes()).hexdigest() if (ROOT/'requirements-cad.txt').exists() else None})
    print(json.dumps({k:v for k,v in report.items() if k not in ['dynamic_samples']},indent=2))

def gen_step():
    p=json.loads((ROOT/'config/zipper-cad-parameters.json').read_text());parts=make_parts(p)
    return Compound(label='zipper_parametric_v1',children=[place(x['shape'],x['loc'],x['angle']) for x in parts])

def main():
    global OUT,REPORT
    ap=argparse.ArgumentParser();ap.add_argument('--parameters',type=Path,default=ROOT/'config/zipper-cad-parameters.json');ap.add_argument('--output',type=Path,default=OUT);ap.add_argument('--report-dir',type=Path,default=REPORT);ap.add_argument('--asset-id',default='zipper-parametric-v3');args=ap.parse_args()
    OUT=args.output;REPORT=args.report_dir
    generate(json.loads(args.parameters.read_text()),args.asset_id)
if __name__=='__main__':main()
