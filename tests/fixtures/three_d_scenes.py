"""Real Blender scene/render fixtures, including a perspective image-plane fraud."""
import json,sys,math,subprocess
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from mechanical_video_next.provenance import binding,compose
out=Path(sys.argv[sys.argv.index('--')+1]);out.mkdir(parents=True,exist_ok=True)
reference=out/'reference.txt';reference.write_text('Synthetic regression fixture: rotating cuboid; not a claim about any product.')
audio=out/'neil-fixture.wav';subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=300:duration=0.2',str(audio)],check=True)
ass=out/'caption.ass';ass.write_text('''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Helvetica,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,50,50,30,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:00.20,Default,,0,0,0,,3D test with 2D subtitle
''')
for kind in ['good','bad']:
 bpy.ops.wm.read_factory_settings(use_empty=True);sc=bpy.context.scene
 sc.render.engine='BLENDER_EEVEE';sc.render.resolution_x=1920;sc.render.resolution_y=1080;sc.render.resolution_percentage=100;sc.render.fps=30;sc.frame_start=1;sc.frame_end=6
 collection=bpy.data.collections.new('Assembly');sc.collection.children.link(collection)
 if kind=='good':bpy.ops.mesh.primitive_cube_add()
 else:bpy.ops.mesh.primitive_plane_add()
 obj=bpy.context.object
 for c in list(obj.users_collection):c.objects.unlink(obj)
 collection.objects.link(obj)
 for f,angle in [(1,0),(3,.4),(6,.9)]:
  obj.rotation_euler.z=angle;obj.keyframe_insert('rotation_euler',frame=f)
 # A legitimate planar sheet in a real assembly must not cause a false rejection.
 # Conversely, an unused hidden solid cannot rescue a flat mechanical subject.
 if kind=='good':
  bpy.ops.mesh.primitive_plane_add(size=.5,location=(1.5,0,0))
 else:
  bpy.ops.mesh.primitive_cube_add(size=.1,location=(0,0,-10))
  bpy.context.object.hide_render=True
 extra=bpy.context.object
 for c in list(extra.users_collection):c.objects.unlink(extra)
 collection.objects.link(extra)
 bpy.ops.object.camera_add(location=(4,-6,4));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,0))-cam.location).to_track_quat('-Z','Y').to_euler();sc.camera=cam
 bpy.ops.object.light_add(type='AREA',location=(0,-2,5));bpy.context.object.data.energy=1000;bpy.context.object.data.shape='DISK';bpy.context.object.data.size=5
 sc.world=bpy.data.worlds.new('World');sc.world.color=(.4,.4,.4)
 folder=out/kind;folder.mkdir(exist_ok=True);scene=folder/'scene.blend';sc.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(scene))
 for f in range(1,7):
  sc.frame_set(f);sc.render.filepath=str(folder/f'{f:05d}.png');bpy.ops.render.render(write_still=True)
 raw=folder/'raw.mp4';subprocess.run(['ffmpeg','-v','error','-y','-framerate','30','-i',str(folder/'%05d.png'),'-c:v','libx264','-crf','18','-pix_fmt','yuv420p',str(raw)],check=True)
 motion=folder/'motion.json';motion.write_text(json.dumps({'object':'Cube','rotation_z':[0,.4,.9]}))
 segment={'shot_id':'core','render_output':binding(raw),'start_frame':0,'source_start_frame':0,'frame_count':6}
 build={'segments':[segment],'frame_count':6,'narration':binding(audio),'subtitles':binding(ass),'fonts':[]}
 final=out/('good-final.mp4' if kind=='good' else 'flat-final.mp4');compose(build,final)
 shot={'shot_id':'core','scene':binding(scene),'motion_data':binding(motion),'render_output':binding(raw),'model_assets':[dict(binding(scene),source='Synthetic fixture geometry')],'product_references':[binding(reference)],'verification_frames':[1,3,6]}
 (out/f'{kind}-provenance.json').write_text(json.dumps({'media':binding(final),'shots':[shot],'build':build}))
