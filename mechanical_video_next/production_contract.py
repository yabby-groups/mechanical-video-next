"""Versioned science/director requirements inside existing records and gates."""
import hashlib
import math
from pathlib import Path
import re
import subprocess

from .visual_narrative import located, nonempty

FIELD = 'production_contract_version'
NAME = 'mixed-original-v1'
CREATIVE_FIRST_VERSION = 2
CREATIVE_FIRST_NAME = 'creative-first-v2'
STORY_VERSION = 3
STORY_NAME = 'science-story-v3'
DISCOVERY_VERSION = 4
DISCOVERY_NAME = 'science-discovery-v4'
MECHANICAL_STORY_VERSION = 5
MECHANICAL_STORY_NAME = 'mechanical-story-v5'
CREATIVE_SELECTION_VERSION = 6
CREATIVE_SELECTION_NAME = 'mechanical-story-v6'
PRODUCER_DIRECTED = 'producer-directed'
SKILL_DRIVEN = 'skill-driven'
PRODUCER_DIRECTION = 'producer_direction_version'
STORY_DEVELOPMENT = 'story_development_version'
POSITIONING = '拆开机器，看懂它怎么工作。用三维动画讲清身边的机械原理。'
DESIGN_RESEARCH = ('origin', 'use_problem', 'historical_context', 'early_limits',
                   'design_changes', 'scientific_principle')
AUDIENCE_PREMISE = ('question', 'daily_context', 'design_tension', 'visible_test',
                    'viewer_takeaway', 'selection_rationale')
STORY_MOMENTS = ('opening', 'first_discovery', 'causal_reveal', 'payoff')
CONTRACT_NAMES = {1: NAME, CREATIVE_FIRST_VERSION: CREATIVE_FIRST_NAME, STORY_VERSION: STORY_NAME,
                  DISCOVERY_VERSION: DISCOVERY_NAME, MECHANICAL_STORY_VERSION: MECHANICAL_STORY_NAME,
                  CREATIVE_SELECTION_VERSION: CREATIVE_SELECTION_NAME}
CREATIVE_DURATION = (1 / 30, 300)
FORMAL_DURATION_FIELD = 'formal_duration_version'
FORMAL_DURATION_VERSION = 3
SHORT_FORMAL_DURATION_VERSION = 2
FORMAL_DURATION = (120, 300)
FORMAL_DURATION_POLICIES = {1: FORMAL_DURATION, 2: CREATIVE_DURATION, 3: (60, math.inf)}


def formal_duration_bounds(document):
    version = document.get(FORMAL_DURATION_FIELD)
    if version is None:
        return None
    if type(version) is not int or version not in FORMAL_DURATION_POLICIES:
        raise ValueError('Unsupported formal duration policy')
    return FORMAL_DURATION_POLICIES[version]


def formal_duration_enabled(document):
    return formal_duration_bounds(document) is not None


def validate_formal_duration(document, seconds, *, preview=False):
    bounds = formal_duration_bounds(document)
    if bounds is None or (preview and document.get(FORMAL_DURATION_FIELD) == FORMAL_DURATION_VERSION):
        return
    if not math.isfinite(seconds) or not bounds[0] - 1e-6 <= seconds <= bounds[1] + 1e-6:
        messages = {1: '120–300 seconds', 2: '1 frame to 300 seconds', 3: 'at least 60 seconds'}
        raise ValueError(f'Formal film requires {messages[document[FORMAL_DURATION_FIELD]]}')
PRESENTATION_STYLE = 'presentation_style'
NATURAL_SCIENCE = 'natural_science'
PRODUCTION_LABELS = frozenset({
    '原理示意', '教学动画', '教学模型', '概念模型', '仅供演示',
    '动画演示', '示意画面', '以下为演示', '3D 模型展示',
    '教学演示', '教学级运动学', '模型示意', '数学模型',
    '数据驱动动画', '物理仿真', '物理仿真回放', '教学装配',
})
CLASSROOM_OPENINGS = (
    '下面我们来学习', '接下来进行原理演示', '这里使用一个教学模型',
    '如动画所示', '这个示意图告诉我们', '现在我们介绍它的工作原理',
)
CREATIVE_OPENINGS = CLASSROOM_OPENINGS + (
    '首先介绍', '接下来我们来看', '下面分析工作原理', '现在进入第二阶段', '综上所述',
)
AUDIENCE_DECISION = ('daily_context', 'opening_visual', 'viewer_takeaway', 'selection_rationale')
CREATIVE_DECISION = AUDIENCE_DECISION + (
    'question', 'surprise', 'scientific_discovery', 'essential_3d', 'other_visuals',
    'material_feasibility', 'length_rationale',
)
CREATIVE_CHECKS = {
    'opening', 'visual_tasks', 'pace', 'everyday_connection', 'voice_and_sound', 'payoff',
}


def audience_caption(text):
    """Remove standalone production tags while retaining concrete conditions."""
    return ' · '.join(part for part in map(str.strip, re.split(r'[·｜|]', text))
                      if part and part.strip(' ／/。') not in PRODUCTION_LABELS)


def validate_audience_copy(row, *, creative=False):
    openings = CREATIVE_OPENINGS if creative else CLASSROOM_OPENINGS
    for line in row.get('narration', []):
        if line.lstrip().startswith(openings):
            raise ValueError(f'Rewrite classroom narration as a concrete scientific observation: {line}')
    graphic = row.get('graphic', {})
    science = row.get('science', {})
    visible = [row.get(key) for key in ('title', 'subtitle', 'chapter', 'label', 'note', 'formula')]
    visible += [graphic.get(key) for key in ('title', 'formula')]
    visible += [value for item in graphic.get('items', []) for value in (item.get('label'), item.get('detail'))]
    visible += list(row.get('subtitles', [])) + list(row.get('overlays', []))
    visible += [item.get('text') for item in row.get('information', []) + row.get('annotations', [])]
    visible += [mark.get('text') for mark in science.get('print_marks', [])]
    for line in visible:
        if isinstance(line, str) and any(part.strip(' ／/。') in PRODUCTION_LABELS
                                        for part in re.split(r'[·｜|]', line)):
            raise ValueError(f'Remove the standalone production label or explain the concrete limitation: {line}')


DIMENSIONS = {'scientific_accuracy', 'mechanical_motion', 'visual_expression',
              'narrative_comprehension', 'originality_copyright', 'av_delivery'}
DIRECTION = {'why_visual', 'composition', 'lighting', 'continuity', 'sound_intent'}
REVIEW_METHODS = {
    'continuous_video': {'video'}, 'continuous_audio': {'audio'},
    'continuous_audiovisual': {'video', 'audio'},
    'sampled_frames': set(), 'technical_decode': set(), 'document_review': set(),
}


def version(document):
    version = document.get(FIELD, 0)
    names = CONTRACT_NAMES
    if type(version) is not int or version not in {0, *names}:
        raise ValueError('Unsupported production contract version')
    if skill_driven(document) and (
            version != CREATIVE_SELECTION_VERSION or document.get(PRODUCER_DIRECTION) != 1):
        raise ValueError('Skill-driven production requires the pinned mixed-media execution contract')
    if story_development(document) and (
            version != CREATIVE_SELECTION_VERSION
            or document.get('production_method') not in {PRODUCER_DIRECTED, SKILL_DRIVEN}
            or document.get(PRODUCER_DIRECTION) != 1):
        raise ValueError('Story development requires the pinned Producer mixed-media contract')
    if version and (document.get('production_contract') != names[version]
            or document.get('media_policy_version') != 1
            or document.get('visual_policy_version') != 2):
        raise ValueError('Mixed production needs matching explicit policy versions')
    return version


def enabled(document):
    return bool(version(document))


def creative_first(document):
    return version(document) >= CREATIVE_FIRST_VERSION


def science_story(document):
    return version(document) >= STORY_VERSION


def discovery(document):
    return version(document) >= DISCOVERY_VERSION


def mechanical_story(document):
    return version(document) >= MECHANICAL_STORY_VERSION


def producer_directed(document):
    return (document.get('production_method') in (PRODUCER_DIRECTED, SKILL_DRIVEN)
            and version(document) == CREATIVE_SELECTION_VERSION)


def skill_driven(document):
    return document.get('production_method') == SKILL_DRIVEN


def story_development(document):
    version = document.get(STORY_DEVELOPMENT, 0)
    if type(version) is not int or version not in {0, 1, 2}:
        raise ValueError('Unsupported story development version')
    return version != 0


def mechanism_first(document):
    return document.get(STORY_DEVELOPMENT) == 2


def match_mechanical_scope(task, document, question):
    """Keep user scope distinct from the Producer's framing and chosen implementation."""
    if 'mechanical_object' not in task:
        return
    if (document.get('mechanical_object') != task['mechanical_object']
            or not nonempty(question)
            or (task.get('core_question') and task['core_question'] != question)):
        raise ValueError('Keep the requested mechanical object and core question')


def flexible_story(document):
    return skill_driven(document) or story_development(document)


def directed_story(document):
    value = document.get(PRODUCER_DIRECTION, 0)
    if type(value) is not int or value not in {0, 1} or (value and not producer_directed(document)):
        raise ValueError('Unsupported Producer direction version')
    return value == 1


def subject_kind(document):
    return document.get('subject_kind') or document.get('science', {}).get('subject_kind')


def nonmechanical_subject(document):
    kind = subject_kind(document)
    return ((enabled(document) and kind == 'physical_phenomenon')
            or (discovery(document) and kind == 'documented_technology'))


def selected_story(research, *, allow_unselected=False):
    exploration = research.get('story_exploration', {})
    if not isinstance(exploration, dict):
        raise ValueError('Story exploration must be an object')
    candidates = exploration.get('candidates')
    if (not isinstance(candidates, list) or not candidates
            or (version(research) < CREATIVE_SELECTION_VERSION and len(candidates) > 4)):
        raise ValueError('Explore a bounded shortlist of distinct, defensible story candidates')
    seen, questions, winner = set(), set(), None
    facts = {fact['id']: fact for fact in research.get('science', {}).get('facts', [])}
    angles = exploration.get('angles')
    if not isinstance(angles, dict) or not angles or not all(
            nonempty(name) and nonempty(finding) for name, finding in angles.items()):
        raise ValueError('Record exploratory findings or evidence gaps by angle')
    fields = ('id', 'question', 'angle', 'visual_test', 'decision_reason')
    if mechanical_story(research):
        fields += ('mechanical_focus',)
    for candidate in candidates:
        if not isinstance(candidate, dict) or not all(nonempty(candidate.get(key)) for key in fields):
            raise ValueError('Each candidate requires: ' + ', '.join(fields))
        identity, question = candidate['id'], candidate['question']
        if identity in seen or question in questions:
            raise ValueError('Story candidates need distinct identities and questions')
        seen.add(identity)
        questions.add(question)
        ids = candidate.get('fact_ids', [])
        if not isinstance(ids, list) or any(not nonempty(key) or key not in facts for key in ids):
            raise ValueError('Story candidates must link claims to the current research ledger')
        if identity == exploration.get('selected_id'):
            if not ids or any(facts[key]['status'] != 'VERIFIED' for key in ids):
                raise ValueError('The selected story must be grounded in verified facts')
            winner = candidate
    if len(candidates) == 1 and not nonempty(exploration.get('shortlist_limit')):
        raise ValueError('Explain why no second candidate warranted development')
    if (allow_unselected and version(research) >= CREATIVE_SELECTION_VERSION
            and exploration.get('selected_id') is None):
        return None
    if winner is None or winner['question'] != research.get('audience_decision', {}).get('question'):
        raise ValueError('The audience question must come from the selected research story')
    return winner


def validate_audience_decision(decision, *, creative=False, story=False):
    fields = CREATIVE_DECISION if creative else AUDIENCE_DECISION
    if story:
        fields = tuple(field for field in CREATIVE_DECISION if field not in {'essential_3d', 'other_visuals'})
        fields += ('visual_approach',)
    if not isinstance(decision, dict) or not all(nonempty(decision.get(key)) for key in fields):
        raise ValueError('Audience decision needs concrete choices about the question, visuals and takeaway'
                         if creative else 'Audience decision needs a daily context, opening visual, takeaway and selection rationale')


def validate_research(research):
    directed = producer_directed(research)
    if (not directed and version(research) >= CREATIVE_SELECTION_VERSION
            and research.get('story_exploration', {}).get('phase') == 'EDITORIAL'):
        selected_story(research, allow_unselected=True)
        return {}
    science = research.get('science', {})
    kind = science.get('subject_kind')
    if mechanism_first(research) and not nonempty(research.get('mechanical_object')):
        raise ValueError('Research must identify the requested mechanical object')
    if mechanism_first(research) and kind != 'mechanical_implementation':
        raise ValueError('Research must verify a specific implementation of the requested machine')
    technology = kind == 'documented_technology' and discovery(research)
    if kind not in {'mechanical_implementation', 'physical_phenomenon'} and not technology:
        raise ValueError('Identify a supported subject and its concrete scope')
    if mechanical_story(research) and kind == 'physical_phenomenon':
        raise ValueError('Mechanical stories need a machine, device or documented mechanical technology as the subject')
    if not all(nonempty(science.get(k)) for k in ('question', 'answer', 'scope')):
        raise ValueError('Scientific question, supported answer and scope required')
    if kind == 'physical_phenomenon' or technology:
        subject=science.get('subject',{})
        models = {'documented'} if technology else {'conceptual','mathematical'}
        if (not all(nonempty(subject.get(k)) for k in ('id','name','scope'))
                or subject.get('model_kind') not in models):
            raise ValueError('Nonmechanical subjects need a named, bounded model or documented scope')
    facts = science.get('facts')
    if not isinstance(facts, list) or not facts:
        raise ValueError('Concise science.facts ledger required')
    seen = set()
    for fact in facts:
        identity = fact.get('id')
        if not nonempty(identity) or identity in seen or not nonempty(fact.get('claim')):
            raise ValueError('Unique fact IDs and concrete claims required')
        seen.add(identity)
        if fact.get('status') not in {'VERIFIED', 'UNKNOWN'}:
            raise ValueError('Fact status must disclose VERIFIED or UNKNOWN')
        kinds = {'observed', 'derived', 'teaching_approximation', 'hypothesis'}
        if discovery(research):
            kinds |= {'historical_fact', 'scientific_fact', 'story_lead', 'legend'}
        if fact.get('kind') not in kinds:
            raise ValueError('Disclose the scientific evidence kind')
        if not nonempty(fact.get('scope')) or not isinstance(fact.get('assumptions'), list):
            raise ValueError('Facts require scope and explicit assumptions')
        if fact['status'] == 'VERIFIED':
            if fact['kind'] in {'hypothesis', 'story_lead', 'legend'}:
                raise ValueError('A hypothesis, lead or legend cannot support a narrated fact')
            located(fact.get('sources'))
        elif not nonempty(fact.get('limitation')):
            raise ValueError('Unknown facts need a specific limitation')
    if directed and not any(fact['status'] == 'VERIFIED' for fact in facts):
        raise ValueError('The story needs verified facts')
    if story_development(research) and not mechanism_first(research):
        exploration = research.get('design_research', {})
        if not isinstance(exploration, dict):
            raise ValueError('Design research requires a structured set of findings')
        facts_by_id = {fact['id']: fact for fact in facts}
        for question in DESIGN_RESEARCH:
            finding = exploration.get(question)
            ids = finding.get('fact_ids') if isinstance(finding, dict) else None
            if (not isinstance(ids, list) or not ids
                    or not all(nonempty(key) and key in facts_by_id for key in ids)
                    or not nonempty(finding.get('finding'))):
                raise ValueError('Locate the research finding or evidence gap for ' + question)
        if not any(facts_by_id[key]['status'] == 'VERIFIED'
                   for key in exploration['scientific_principle']['fact_ids']):
            raise ValueError('Ground the scientific principle in verified evidence')
    if directed_story(research) and not flexible_story(research):
        premise = research.get('audience_decision')
        if not isinstance(premise, dict) or not all(nonempty(premise.get(key)) for key in AUDIENCE_PREMISE):
            raise ValueError('Describe the audience question, daily use, design tradeoff, visible test and payoff')
    if discovery(research) and not directed:
        selected_story(research, allow_unselected=True)
    return {fact['id']: fact for fact in facts}


def validate_story_moments(blueprint, narrative):
    from .joint_timeline import integrity, interval
    shots = blueprint['shots']
    picture = {row['id']: row for row in blueprint['timeline']['shots']}
    moments = narrative.get('moments')
    flexible = flexible_story(blueprint)
    locked = integrity(blueprint['timeline'])
    required = set(STORY_MOMENTS)
    if locked:
        required.update(('scientific_explanation', 'action_result'))
    if flexible:
        if not isinstance(moments, dict) or not moments or not all(map(nonempty, moments)):
            raise ValueError('Bind the authored story observations to picture using unique IDs')
    elif not isinstance(moments, dict) or set(moments) != required:
        raise ValueError('Bind opening, first discovery, causal reveal and payoff to picture')
    starts = {}
    for key, moment in moments.items():
        if (not isinstance(moment, dict) or not nonempty(moment.get('shot_id'))
                or moment['shot_id'] not in picture or not nonempty(moment.get('observable'))):
            raise ValueError(f'{key} requires a shot and observable action or state')
        shot = picture[moment['shot_id']]
        start, stop = interval(moment, blueprint['timeline']['frame_count'])
        if not shot['start_frame'] <= start < stop <= shot['end_frame']:
            raise ValueError(f'{key} falls outside its picture shot')
        starts[key] = start
    if not flexible and (moments['opening']['shot_id'] != shots[0]['shot_id']
            or starts['first_discovery'] < starts['opening']
            or starts['payoff'] < max(starts['first_discovery'], starts['causal_reveal'])):
        raise ValueError('Bind the opening to the first shot and deliver the discovery by the payoff')
    if locked and not flexible and (starts['causal_reveal'] < starts['first_discovery']
                   or not starts['causal_reveal'] <= starts['action_result'] <= starts['payoff']
                   or not starts['opening'] <= starts['scientific_explanation'] <= starts['payoff']):
        raise ValueError('The explanation and mechanical result must lead to the payoff')
    if narrative['question'] != blueprint.get('core_question'):
        raise ValueError('Use the same audience question in the narrative and Blueprint')
    if not flexible:
        for shot in shots:
            direction = shot.get('direction')
            if not isinstance(direction, dict) or not all(nonempty(direction.get(key)) for key in DIRECTION):
                raise ValueError(f'{shot["shot_id"]} needs visual purpose, composition, light, continuity and sound intent')
    if locked:
        validate_story_coverage(blueprint, moments)


def validate_story_coverage(blueprint, moments):
    from .joint_timeline import SAMPLES_PER_FRAME, receipt

    plan = blueprint['timeline']
    actions = {row['id']: row for row in plan['actions']}
    speech = {row['id']: row for row in plan['narration']}
    shots = {row['shot_id']: row for row in blueprint['shots']}
    if mechanism_first(blueprint):
        core = [shot for shot in shots.values() if shot.get('mechanical_role') == 'core']
        if not core or any(shot.get('render_engine') != 'blender' for shot in core):
            raise ValueError('Core explanation requires inspectable native Blender mechanics')
    measured = (receipt(plan, blueprint['measured_timeline']) if blueprint.get('measured_timeline') else None)
    clips = {row['id']: row for row in measured['speech']} if measured else {}
    for cut in plan['shots']:
        sid = cut['id']
        shot = shots[sid]
        events = cut.get('action_views', {})
        if shot.get('mechanical_role') == 'core' and not events:
            raise ValueError('Core mechanical shot lacks a verified event: ' + sid)
        if any(actions[key]['knowledge_id'] not in shot.get('knowledge_ids', []) for key in events):
            raise ValueError('Mechanical event knowledge differs from its shot: ' + sid)
    for name, moment in moments.items():
        sid = moment['shot_id']
        shot = shots[sid]
        first, last = moment['start_frame'], moment['end_frame']
        fact = moment.get('knowledge_id')
        if fact not in shot.get('knowledge_ids', []):
            raise ValueError('Story moment requires knowledge carried by its shot: ' + name)
        event = actions.get(moment.get('mechanical_event_id'))
        line = speech.get(moment.get('narration_segment_id'))
        if event and (event['knowledge_id'] != fact or not event['start_frame'] <= first < last <= event['end_frame']):
            raise ValueError('Story moment falls outside its mechanical evidence: ' + name)
        if line:
            clip = clips.get(line['id'])
            start = clip['start_sample'] if clip else line['start_frame'] * SAMPLES_PER_FRAME
            end = clip['end_sample'] if clip else line['deadline_frame'] * SAMPLES_PER_FRAME
            if fact not in line['knowledge_ids'] or first * SAMPLES_PER_FRAME >= end or last * SAMPLES_PER_FRAME <= start:
                raise ValueError('Story moment falls outside its measured narration: ' + name)
        if (moment.get('mechanical_event_id') and event is None or moment.get('narration_segment_id') and line is None
                or (not flexible_story(blueprint) and name in {'causal_reveal', 'action_result'}
                    and not event and not nonmechanical_subject(blueprint))
                or (not event and not line and not nonempty(moment.get('visual_evidence')))):
            raise ValueError('Story moment lacks observable evidence: ' + name)


def validate_direction(blueprint, research=None):
    if not enabled(blueprint):
        return
    narrative = blueprint.get('narrative', {})
    if producer_directed(blueprint):
        if mechanism_first(blueprint) and not nonempty(blueprint.get('mechanical_object')):
            raise ValueError('Blueprint must preserve the requested mechanical object')
        if not all(nonempty(narrative.get(k)) for k in ('question', 'answer')):
            raise ValueError('Blueprint needs the story question and supported answer')
        if directed_story(blueprint):
            validate_story_moments(blueprint, narrative)
        if research is not None:
            facts = validate_research(research)
            if (directed_story(blueprint) and not flexible_story(blueprint)
                    and narrative['question'] != research['audience_decision']['question']):
                raise ValueError('Audience question differs from the selected research premise')
            for row in [*blueprint['shots'], *blueprint['timeline']['narration']]:
                for identity in row['knowledge_ids']:
                    if identity not in facts or facts[identity]['status'] != 'VERIFIED':
                        raise ValueError('Unsupported fact cannot enter picture or narration: ' + identity)
        return
    if not all(nonempty(narrative.get(k)) for k in ('question', 'tension', 'answer', 'arc_reason')):
        raise ValueError('Original question, tension, answer and chosen narrative arc required')
    creative = creative_first(blueprint)
    if creative or 'audience_decision' in narrative:
        decision = narrative.get('audience_decision')
        validate_audience_decision(decision, creative=creative, story=science_story(blueprint))
        shots = blueprint['shots']
        if (not shots or decision.get('opening_shot_id') != shots[0]['shot_id']
                or decision.get('payoff_shot_id') not in {shot['shot_id'] for shot in shots}):
            raise ValueError('Audience decision must bind the first shot and a payoff shot')
        if creative:
            if decision['payoff_shot_id'] == decision['opening_shot_id'] or decision['question'] != narrative['question']:
                raise ValueError('Bind the same everyday question to distinct opening and payoff actions')
            if research is not None and decision['question'] != research.get('audience_decision', {}).get('question'):
                raise ValueError('A changed audience question needs updated research')
    facts = validate_research(research) if research is not None else None
    if discovery(blueprint):
        if not nonempty(narrative.get('story_id')):
            raise ValueError('Blueprint must name its selected research story')
        if research is not None:
            selected = selected_story(research)
            used = {key for shot in blueprint['shots'] for key in shot['knowledge_ids']}
            if narrative['story_id'] != selected['id'] or not set(selected['fact_ids']) <= used:
                raise ValueError('Blueprint must carry the selected story and its verified central facts')
    mechanism_run = []
    for shot in blueprint['shots']:
        direction = shot.get('direction', {})
        if not DIRECTION <= direction.keys() or not all(nonempty(direction[k]) for k in DIRECTION):
            raise ValueError('Each shot requires visual rationale, composition, light, continuity and sound intent')
        if creative:
            if shot.get('visual_type') in {'exploded_view', 'mechanical_cutaway', 'annotated_detail'} or (
                    shot.get('visual_type') == 'micro_principle' and shot.get('mechanical_role') == 'core'):
                mechanism_run.append(direction)
                if len(mechanism_run) >= 3 and not nonempty(mechanism_run[0].get('continuous_mechanism_reason')):
                    raise ValueError('Explain why this uninterrupted chain of mechanism shots is needed')
            else:
                mechanism_run.clear()
        if facts is not None:
            for identity in shot['knowledge_ids']:
                if identity not in facts or facts[identity]['status'] != 'VERIFIED':
                    raise ValueError('Unsupported fact restricts its dependent shot: ' + identity)


def validate_creative_review(report, film_hashes, *, acceptance, whole_edit=False):
    """Record the review of a real moving edit. Capability UNKNOWN stays UNKNOWN."""
    review = report.get('creative_review', {})
    if not isinstance(review, dict) or set(review) != CREATIVE_CHECKS:
        raise ValueError('Independent creative review must address all six film questions')
    for key, item in review.items():
        if not isinstance(item, dict):
            raise ValueError(f'Creative observation must be an object: {key}')
        status = item.get('status')
        interval = item.get('time_range')
        if (status not in {'PASS', 'FAIL', 'UNKNOWN'}
                or item.get('media_sha256') not in film_hashes
                or not isinstance(interval, list) or len(interval) != 2
                or not all(isinstance(t, (int, float)) and not isinstance(t, bool) and math.isfinite(t) for t in interval)
                or not 0 <= interval[0] < interval[1] <= film_hashes[item['media_sha256']] + .001
                or not nonempty(item.get('observation')) or not nonempty(item.get('capability_boundary'))):
            raise ValueError(f'Creative review needs a concrete observation bound to film and time: {key}')
        methods = ({'continuous_audio', 'continuous_audiovisual'} if key == 'voice_and_sound'
                   else {'continuous_video', 'continuous_audiovisual'})
        if status == 'PASS' and item.get('method') not in methods:
            raise ValueError(f'Creative PASS requires appropriate continuous viewing/listening: {key}')
        if (whole_edit and status == 'PASS' and key in {'pace', 'visual_tasks', 'voice_and_sound'}
                and (interval[0] > .001 or interval[1] < film_hashes[item['media_sha256']] - .001)):
            raise ValueError(f'Creative review must cover the whole edit: {key}')
        if status == 'FAIL' and not nonempty(item.get('alternative')):
            raise ValueError(f'A creative defect needs a concrete alternative: {key}')
        if acceptance and status != 'PASS':
            raise ValueError(f'Creative review remains {status}: {key}')


def validate_qa(report, media, *, acceptance, blueprint=None, technical_audio=False):
    """Six conclusions are independent; deterministic success cannot fill senses."""
    review = report.get('quality_dimensions', {})
    if set(review) != DIMENSIONS:
        raise ValueError('Six independent quality dimensions required')
    hashes = {item['sha256'] for item in media}
    for name, row in review.items():
        if (row.get('status') not in {'PASS', 'FAIL', 'UNKNOWN'}
                or row.get('media_sha256') not in hashes or not nonempty(row.get('observation'))):
            raise ValueError('Quality dimensions require exact-media observations: ' + name)
        if row['status'] == 'FAIL' or (acceptance and row['status'] != 'PASS'):
            raise ValueError('Quality dimension prevents acceptance: ' + name)
    if technical_audio and (report.get('audio_perceptual_review') != 'NOT_PERFORMED'
            or report.get('full_audio_listened') not in (None, False)
            or report.get('checks', {}).get('listening') not in (None, 'UNKNOWN')
            or report.get('hybrid_media_review', {}).get('listening') not in (None, False)
            or any(REVIEW_METHODS.get(row.get('method'), set()) & {'audio'}
                   for row in report.get('review_observations', []))):
        raise ValueError('Technical audio acceptance cannot claim a perceptual listening result')
    if acceptance and (report.get('full_video_reviewed') is not True
            or (not technical_audio and report.get('full_audio_listened') is not True)):
        raise ValueError('Complete actual viewing and listening required for acceptance')
    if acceptance:
        if technical_audio:
            from .audio_acceptance import check_evidence
            check_evidence(report, media)
        validate_review_observations(report, media, blueprint, technical_audio=technical_audio)


def review_media_identity(binding):
    """Identify the encoded film and decoded audio, without claiming perception."""
    from scripts.common import filehash, probe
    path = Path(binding['path'])
    if not path.is_file() or filehash(path) != binding.get('sha256'):
        raise ValueError('Review media is missing or changed')
    streams = probe(path)['streams']
    video = next((s for s in streams if s['codec_type'] == 'video'), None)
    audio = next((s for s in streams if s['codec_type'] == 'audio'), None)
    if video is None or audio is None:
        raise ValueError('Full review requires actual video and narration audio')
    durations = {kind: float(stream['duration']) for kind, stream in (('video', video), ('audio', audio))}
    if any(not math.isfinite(value) or value <= 0 for value in durations.values()):
        raise ValueError('Review requires finite actual stream durations')
    digest = hashlib.sha256()
    process = subprocess.Popen(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-map', '0:a:0',
                                '-f', 's16le', '-acodec', 'pcm_s16le', '-'],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    count = 0
    try:
        while chunk := process.stdout.read(65536):
            digest.update(chunk)
            count += len(chunk)
        if process.wait() or not count:
            raise ValueError('Complete review audio decoding failed')
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
    if filehash(path) != binding['sha256']:
        raise ValueError('Review media changed during audio identity verification')
    return {'media_sha256': binding['sha256'], 'durations': durations,
            'audio_pcm_sha256': digest.hexdigest(),
            'audio_pcm_format': {'format': 's16le', 'sample_rate': int(audio['sample_rate']),
                                 'channels': int(audio['channels'])}}


def validate_review_observations(report, media, blueprint, *, technical_audio=False, workprint=False):
    """Validate traceable attestations in the existing QA handoff, not senses.

    These records are hash-bound by the same immutable QA envelope as the six
    conclusions. No second report store or automatically generated PASS exists.
    A truthful independent reviewer remains responsible for actual perception.
    """
    rows = report.get('review_observations')
    if not isinstance(rows, list) or not rows:
        raise ValueError('Full acceptance requires time-covered review observations')
    if not isinstance(blueprint, dict) or not isinstance(blueprint.get('shots'), list) or not blueprint['shots']:
        raise ValueError('Review observations require the current bound Blueprint shots')
    from . import joint_timeline as joint
    plan = blueprint.get('timeline', {})
    locked = joint.integrity(plan)
    if locked:
        for item in media:
            joint.validate_rendered_film(item['path'], plan)
    shots = {shot['shot_id']: shot for shot in blueprint['shots']}
    if len(shots) != len(blueprint['shots']):
        raise ValueError('Review Blueprint shot identities must be unique')
    last_shot = blueprint['shots'][-1]['shot_id']
    reviewer = report.get('reviewer_thread_id')
    if report.get('independent_reviewer') is not True or not nonempty(reviewer):
        raise ValueError('Review observations require an independent reviewer identity')
    if reviewer in report.get('production_thread_ids', []):
        raise ValueError('Production agents cannot supply independent review observations')
    if technical_audio:
        from scripts.common import probe
        identities = {m['sha256']: {'durations': {'video': float(next(
            stream['duration'] for stream in probe(m['path'])['streams']
            if stream['codec_type'] == 'video'))}} for m in media}
    else:
        identities = {m['sha256']: review_media_identity(m) for m in media}
    coverage = {sha: {kind: [] for kind in identity['durations']} for sha, identity in identities.items()}
    observations = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Review observations must be structured records')
        identity, sha = row.get('id'), row.get('media_sha256')
        method, window = row.get('method'), row.get('time_range')
        sid, dimension = row.get('shot_id'), row.get('dimension')
        if (not nonempty(identity) or identity in observations or not nonempty(sha) or sha not in identities
                or not nonempty(method) or method not in REVIEW_METHODS or row.get('reviewer_thread_id') != reviewer
                or not nonempty(sid) or sid not in shots or not nonempty(dimension) or dimension not in DIMENSIONS
                or row.get('knowledge_ids') != shots[sid].get('knowledge_ids', [])
                or row.get('status') not in {'PASS', 'FAIL', 'UNKNOWN'}
                or not nonempty(row.get('observation')) or not nonempty(row.get('capability_boundary'))):
            raise ValueError('Review observations require unique IDs, exact media, method, result and capability boundary')
        start, stop = shots[sid]['time_range']
        if sid == last_shot:
            stop = max(stop, *identities[sha]['durations'].values())
        if (not isinstance(window, list) or len(window) != 2
                or any(type(v) not in {int, float} or not math.isfinite(v) for v in window)
                or not max(0, start-.001) <= window[0] < window[1] <= min(stop, max(identities[sha]['durations'].values()))+.001):
            raise ValueError('Review observation interval lies outside its actual media shot')
        modalities = REVIEW_METHODS[method]
        if technical_audio and 'audio' in modalities:
            raise ValueError('Technical audio acceptance uses actual video observation intervals')
        if 'audio' in modalities and any(row.get(key) != identities[sha][key]
                                        for key in ('audio_pcm_sha256', 'audio_pcm_format')):
            raise ValueError('Listening observations must bind the actual decoded audio and format')
        if row['status'] != 'PASS':
            raise ValueError('Applicable review observation FAIL/UNKNOWN prevents final acceptance')
        if row['status'] == 'PASS':
            for modality in modalities:
                coverage[sha][modality].append(window)
        observations[identity] = row
    def require_coverage(intervals, duration, label, start=0.):
        end = start
        for left, right in sorted(intervals):
            if end >= duration-.001:
                return
            if left > end+.001:
                raise ValueError('Continuous review has an unobserved interval: ' + label)
            end = max(end, right)
        if end < duration-.001:
            raise ValueError('Continuous review does not cover the complete actual ' + label)

    for sha, modalities in coverage.items():
        for modality, intervals in modalities.items():
            require_coverage(intervals, identities[sha]['durations'][modality], modality)
    if locked:
        for sha in identities:
            for event in plan['actions']:
                intervals = [row['time_range'] for row in observations.values()
                             if row['media_sha256'] == sha and row['dimension'] == 'mechanical_motion'
                             and 'video' in REVIEW_METHODS[row['method']]
                             and event['id'] in row.get('mechanical_event_ids', [])
                             and nonempty(row.get('source_comparison'))]
                require_coverage(intervals, event['end_frame'] / joint.FPS,
                                 'mechanical event ' + event['id'], start=event['start_frame'] / joint.FPS)
            for key, moment in blueprint['narrative']['moments'].items():
                intervals = [row['time_range'] for row in observations.values()
                             if row['media_sha256'] == sha and row['dimension'] == 'narrative_comprehension'
                             and row['shot_id'] == moment['shot_id'] and key in row.get('story_moment_ids', [])
                             and 'video' in REVIEW_METHODS[row['method']]]
                require_coverage(intervals, moment['end_frame'] / joint.FPS,
                                 'story moment ' + key, start=moment['start_frame'] / joint.FPS)
    if workprint:
        return
    for name, conclusion in report['quality_dimensions'].items():
        refs = conclusion.get('observation_ids')
        if (not isinstance(refs, list) or not refs or any(not nonempty(ref) for ref in refs)
                or len(refs) != len(set(refs))
                or any(ref not in observations or observations[ref]['status'] != 'PASS'
                       or observations[ref]['media_sha256'] != conclusion['media_sha256']
                       or observations[ref]['dimension'] != name for ref in refs)):
            raise ValueError('Quality dimension requires matching independent observation records: ' + name)
        # A full-film conclusion cannot cite only a conveniently selected scene.
        # Rights/original-expression conclusions may instead cite document review;
        # the separate existing copyright and originality checks remain mandatory.
        modalities = (set() if name == 'originality_copyright' else
                      {'video'} if technical_audio or name in {'mechanical_motion', 'visual_expression'} else
                      {'video', 'audio'})
        for sid, shot in shots.items():
            start, stop = shot['time_range']
            for modality in modalities or {None}:
                intervals = [observations[ref]['time_range'] for ref in refs
                             if observations[ref]['shot_id'] == sid and (modality is None or
                             modality in REVIEW_METHODS[observations[ref]['method']])]
                duration = (identities[conclusion['media_sha256']]['durations'][modality]
                            if modality is not None else stop)
                end = duration if sid == last_shot else min(stop, duration)
                require_coverage(intervals, end, name + '/' + sid + '/' + str(modality), start=start)
