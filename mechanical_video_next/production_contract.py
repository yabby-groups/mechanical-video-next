"""Versioned science/director requirements inside existing records and gates."""
from .visual_narrative import located, nonempty

FIELD = 'production_contract_version'
NAME = 'mixed-original-v1'
DIMENSIONS = {'scientific_accuracy', 'mechanical_motion', 'visual_expression',
              'narrative_comprehension', 'originality_copyright', 'av_delivery'}
DIRECTION = {'why_visual', 'composition', 'lighting', 'continuity', 'sound_intent'}


def enabled(document):
    version = document.get(FIELD, 0)
    if type(version) is not int or version not in {0, 1}:
        raise ValueError('Unsupported production contract version')
    if version == 1 and (document.get('production_contract') != NAME
            or document.get('media_policy_version') != 1
            or document.get('visual_policy_version') != 2):
        raise ValueError('mixed-original-v1 needs matching explicit policy versions')
    return version == 1


def validate_research(research):
    science = research.get('science', {})
    if science.get('subject_kind') not in {'mechanical_implementation', 'physical_phenomenon'}:
        raise ValueError('Identify the mechanical implementation or bounded physical phenomenon')
    if not all(nonempty(science.get(k)) for k in ('question', 'answer', 'scope')):
        raise ValueError('Scientific question, supported answer and scope required')
    if science['subject_kind']=='physical_phenomenon':
        subject=science.get('subject',{})
        if (not all(nonempty(subject.get(k)) for k in ('id','name','scope'))
                or subject.get('model_kind') not in {'conceptual','mathematical'}):
            raise ValueError('Physical phenomena need a named bounded conceptual/mathematical subject, not a fabricated retail product')
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
        if fact.get('kind') not in {'observed', 'derived', 'teaching_approximation', 'hypothesis'}:
            raise ValueError('Disclose the scientific evidence kind')
        if not nonempty(fact.get('scope')) or not isinstance(fact.get('assumptions'), list):
            raise ValueError('Facts require scope and explicit assumptions')
        if fact['status'] == 'VERIFIED':
            if fact['kind'] == 'hypothesis':
                raise ValueError('An unverified hypothesis cannot support a narrated fact')
            located(fact.get('sources'))
        elif not nonempty(fact.get('limitation')):
            raise ValueError('Unknown facts need a specific limitation')
    return {fact['id']: fact for fact in facts}


def validate_direction(blueprint, research=None):
    if not enabled(blueprint):
        return
    narrative = blueprint.get('narrative', {})
    if not all(nonempty(narrative.get(k)) for k in ('question', 'tension', 'answer', 'arc_reason')):
        raise ValueError('Original question, tension, answer and chosen narrative arc required')
    facts = validate_research(research) if research is not None else None
    for shot in blueprint['shots']:
        direction = shot.get('direction', {})
        if not DIRECTION <= direction.keys() or not all(nonempty(direction[k]) for k in DIRECTION):
            raise ValueError('Each shot requires visual rationale, composition, light, continuity and sound intent')
        if facts is not None:
            for identity in shot['knowledge_ids']:
                if identity not in facts or facts[identity]['status'] != 'VERIFIED':
                    raise ValueError('Unsupported fact restricts its dependent shot: ' + identity)


def validate_qa(report, media, *, acceptance):
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
    if acceptance and (report.get('full_video_reviewed') is not True
            or report.get('full_audio_listened') is not True):
        raise ValueError('Complete actual viewing and listening required for acceptance')
