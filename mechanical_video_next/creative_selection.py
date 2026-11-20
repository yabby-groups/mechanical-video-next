"""Editorial decisions on the existing research and QA handoffs."""
from pathlib import Path
import unicodedata

from .production_contract import CREATIVE_SELECTION_VERSION, producer_directed, version
from .visual_narrative import located, nonempty, number


REVIEW_INPUTS = {
    'diagnostic-qa': 'diagnostic-animatic',
    'animatic-qa': 'animatic-manifest',
    'preview-qa': 'animation-manifest',
    'final-qa': 'timeline',
}
QUESTIONS = {
    'audience_interest', 'mechanical_discovery', 'design_and_use',
    'progression_and_narration', 'originality_and_alternatives', 'production_case',
}
OUTCOMES = {'PASS', 'LOCAL_REPAIR', 'REVISE_STORY', 'RESELECT_STORY', 'UNKNOWN'}
STORY_FAILURE = {'REVISE_STORY', 'RESELECT_STORY'}
EDITORIAL_FIELDS = ('use_context', 'tension', 'visible_discovery', 'viewer_takeaway',
                    'standalone_case')


def enabled(document):
    return version(document) >= CREATIVE_SELECTION_VERSION and not producer_directed(document)


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text).casefold() if c.isalnum())


def validate_competition(research, previous, history):
    """Validate a Producer decision against the prior shortlist and located evidence."""
    exploration = research['story_exploration']
    candidates = exploration['candidates']
    premises, tests = set(), set()
    stable_fields = ('id', 'question', 'premise', 'visual_test', 'editorial', 'editorial_case')
    phase = exploration.get('phase')
    if phase not in {'EDITORIAL', 'DECISION'}:
        raise ValueError('Record editorial priority before the production decision')
    for candidate in candidates:
        editorial = candidate.get('editorial', {})
        if (not all(nonempty(candidate.get(key)) for key in ('premise', 'editorial_case'))
                or not isinstance(editorial, dict)
                or not all(nonempty(editorial.get(key)) for key in EDITORIAL_FIELDS)
                or editorial.get('role') not in {'STANDALONE', 'SUPPORTING', 'DECLINE'}):
            raise ValueError('Compare use, tension, visible discovery, takeaway and standalone story value')
        premise = normalized(candidate['premise'])
        test = normalized(candidate['visual_test'])
        if not premise or not test or premise in premises or test in tests:
            raise ValueError('Different titles need different design premises and visible tests')
        premises.add(premise)
        tests.add(test)
    if not nonempty(exploration.get('editorial_order_reason')):
        raise ValueError('Explain the order against the strongest alternative on audience and visual grounds')
    stable = [[row[key] for key in stable_fields] for row in candidates]
    before = previous['story_exploration'] if previous else None
    if phase == 'EDITORIAL':
        if exploration.get('selected_id') is not None or any(
                {'scientific_basis', 'production'} & set(row) for row in candidates):
            raise ValueError('Editorial priority precedes technical disposition and candidate selection')
        if before and before['phase'] == 'DECISION':
            raise ValueError('Use the current shortlist and independent story findings to reconsider the decision')
        return
    if before is None:
        raise ValueError('Register the editorial shortlist before making a production decision')
    if (stable != [[row[key] for key in stable_fields] for row in before['candidates']]
            or exploration['editorial_order_reason'] != before['editorial_order_reason']):
        raise ValueError('The recorded creative order must survive the technical check')

    facts = {row['id']: row['status'] for row in research['science']['facts']}
    rejected = {row['story_id'] for row in history if row['outcome'] == 'RESELECT_STORY'}
    eligible = set()
    selected = exploration.get('selected_id')
    for row in candidates:
        if row['editorial']['role'] != 'STANDALONE' or row['id'] in rejected:
            continue
        science = row.get('scientific_basis', {})
        production = row.get('production', {})
        scientific_status = science.get('status')
        production_status = production.get('status')
        if scientific_status not in {'VERIFIED', 'CONTRADICTED', 'UNRESOLVED'} or not nonempty(science.get('finding')):
            raise ValueError('Assess the scientific support for each story before it is bypassed')
        located(science.get('sources'))
        if scientific_status == 'VERIFIED' and (
                not row.get('fact_ids') or any(facts.get(key) != 'VERIFIED' for key in row['fact_ids'])):
            raise ValueError('A scientifically supported story must link to its verified central facts')
        if scientific_status == 'UNRESOLVED' and not nonempty(science.get('investigation')):
            raise ValueError('Describe the attempted source or observation and the remaining scientific gap')
        if production_status not in {'READY', 'UNRESOLVED', 'NOT_ASSESSED'}:
            raise ValueError('Assess picture and asset feasibility separately from the scientific finding')
        if production_status in {'READY', 'UNRESOLVED'}:
            if not all(nonempty(production.get(k)) for k in ('approach', 'finding')):
                raise ValueError('Describe how production was investigated and what the result permits')
            located(production.get('evidence'))
        if production_status == 'UNRESOLVED' and not nonempty(production.get('alternative_tried')):
            raise ValueError('Investigate another way to show the result before deferring for feasibility')
        if scientific_status == 'VERIFIED' and production_status == 'READY':
            eligible.add(row['id'])
    if selected is not None and selected not in eligible:
        raise ValueError('The selected story requires its own verified facts and evidenced visual feasibility')
    if before['selected_id'] not in {None, selected, *rejected}:
        raise ValueError('An active direction needs independent creative veto before it can be abandoned')
    if selected is None and not nonempty(exploration.get('stop_reason')):
        raise ValueError('Explain the evidence or creative limit when no story is selected')


def validate_review(data, qa, production, durations, story_id):
    """Check review provenance and scope. The reviewer's judgment is authored."""
    reviewer = qa.get('reviewer_thread_id')
    runs = {row['role'] for row in data['agent_runs'] if row['thread_id'] == reviewer}
    if not reviewer or runs != {'QA'} or qa.get('independent_reviewer') is not True:
        raise ValueError('Creative review requires a separately recorded QA agent')
    expected = {(str(Path(row['path']).resolve()), row['sha256']) for row in production['media']
                if Path(row['path']).suffix.lower() == '.mp4'}
    reviewed = {(str(Path(row['path']).resolve()), row['sha256']) for row in qa['media']
                if Path(row['path']).suffix.lower() == '.mp4'}
    decision = qa.get('story_review', {})
    outcome = decision.get('outcome')
    method = decision.get('method')
    if not expected or expected != reviewed or decision.get('story_id') != story_id:
        raise ValueError('Creative verdict must bind the selected story and exact moving edit')
    if outcome not in OUTCOMES or not nonempty(decision.get('reason')) or not nonempty(
            decision.get('capability_boundary')):
        raise ValueError('Record a creative verdict, why, and the sensory capability boundary')
    if method not in {'continuous_video', 'continuous_audiovisual', 'sampled_frames', 'document_review'}:
        raise ValueError('Disclose the actual creative review method')
    answers = decision.get('findings')
    if not isinstance(answers, dict) or set(answers) != QUESTIONS or not all(map(nonempty, answers.values())):
        raise ValueError('Address audience interest, discovery, design, progression, originality and production cost')
    if outcome == 'PASS' and (method not in {'continuous_video', 'continuous_audiovisual'}
                              or decision.get('full_picture_reviewed') is not True):
        raise ValueError('Creative PASS requires independent continuous viewing of the whole edit')
    if outcome in STORY_FAILURE | {'LOCAL_REPAIR'}:
        evidence = decision.get('evidence', {})
        duration = durations.get(evidence.get('media_sha256'))
        interval = evidence.get('time_range')
        if (duration is None or not isinstance(interval, list) or len(interval) != 2
                or not all(map(number, interval)) or not 0 <= interval[0] < interval[1] <= duration + .001
                or not nonempty(evidence.get('observation')) or not nonempty(decision.get('next_step'))):
            raise ValueError('A creative rejection or adjustment needs located evidence and a concrete next step')
        if outcome == 'LOCAL_REPAIR' and not qa.get('issues'):
            raise ValueError('A local production repair needs an owned QA issue')
    return decision


def narrative_actions(plan):
    return [
        tuple(normalized(scene[key]) for key in ('event', 'change', 'purpose'))
        for scene in plan['scenes']
    ]


def validate_revision(plan, media, history, previous_plan):
    if not history:
        return
    last = history[-1]
    revision = plan.get('revision', {})
    if (revision.get('review_sha256') != last['review']['sha256']
            or not nonempty(revision.get('story_change'))):
        raise ValueError('Describe the changed question or narrative structure against the last creative veto')
    retired_media = {sha for row in history for sha in row['media_sha256']}
    if retired_media & {row['sha256'] for row in media}:
        raise ValueError('Use a newly authored moving edit after a creative veto')
    if previous_plan:
        if narrative_actions(plan) == narrative_actions(previous_plan):
            raise ValueError('A creative veto requires different visible story actions')
