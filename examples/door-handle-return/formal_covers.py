"""Use exact native 3D frames and the project cover layout for two alternatives."""

import argparse
import json
from pathlib import Path

from cinematic_edit import ffmpeg
from mechanical_video_next import covers, joint_timeline as joint
from mechanical_video_next.qa_images import prepare_cover_preview, prepare_image
from scripts.common import writejson


CONCEPTS = (
    ('A', ['门把手松手后', '谁把它推回去？'], 'hook', 'lower', '看下端的接触'),
    ('B', ['一根弹簧', '怎样让把手回正？'], 'mid', 'lost', '方轴带动拨片'),
)


def freeze(path, frame, out):
    ffmpeg('-i', path, '-vf', f'select=eq(n\\,{frame})', '-frames:v', '1', out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('quality', choices=('preview', 'final'), default='final', nargs='?')
    args = parser.parse_args()
    folder = args.folder.resolve()
    out = folder / ('publish' if args.quality == 'final' else 'preview/cover-study')
    out.mkdir(exist_ok=True)
    cuts = json.loads((folder / 'joint-timeline.json').read_text())['shots']
    first = {cut['id']: cut['start_frame'] for cut in cuts}
    picture = folder / args.quality / 'picture.mp4'
    name = '门把手回正.mp4' if args.quality == 'final' else '门把手回正-完整动态预演.mp4'
    media = folder / args.quality / name
    frame_by_id = {'hook': first['hook'] + 64, 'lower': first['lower'] + 38,
                   'mid': first['mid'] + 154, 'lost': first['lost'] + 165}
    records = []
    for letter, title, main_id, detail_id, detail_label in CONCEPTS:
        concept = out / f'封面-{letter}'
        concept.mkdir(exist_ok=True)
        hero, detail = concept / 'film-frame.png', concept / 'film-detail.png'
        freeze(picture, frame_by_id[main_id], hero)
        freeze(picture, frame_by_id[detail_id], detail)
        layout = dict(title=title, series='君哥拆机器', portrait_detail_label=detail_label)
        for cover, size in covers.SIZES.items():
            target = concept / cover
            portrait = size[0] < size[1]
            report = covers.compose(hero, target, size, layout, (.18, .07, .83, .85),
                                    detail=(detail, (.15, .08, .85, .9)) if portrait else None)
            records.append(dict(variant=letter, cover=joint.binding(target), layout=report,
                                preview=prepare_cover_preview(target),
                                phone=prepare_image(target, max_size=520 if portrait else 390),
                                output_frame=frame_by_id[main_id],
                                detail_frame=frame_by_id[detail_id] if portrait else None))
    writejson(out / 'cover-report.json', dict(quality=args.quality, picture=joint.binding(picture),
                                              media=joint.binding(media), covers=records))


if __name__ == '__main__':
    main()
