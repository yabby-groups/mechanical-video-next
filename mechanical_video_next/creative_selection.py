"""Editorial decisions on the existing research and QA handoffs."""
from pathlib import Path
import unicodedata

from .production_contract import (
    CREATIVE_SELECTION_VERSION, POSITIONING, mechanism_first, producer_directed, version,
)
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

TREATMENT_FIELDS = ('context', 'design_need', 'conflict', 'alternatives', 'mechanism',
                    'science', 'resolution', 'takeaway')
CREATIVE_CRITERIA = ('positioning', 'design_story', 'integrated_science', 'visual_story',
                     'causal_progression', 'visual_repetition', 'discovery_payoff',
                     'user_requirements')
CREATIVE_VERDICTS = {'PASS', 'REVISE', 'REJECT', 'UNKNOWN'}
MECHANICAL_CRITERIA = ('positioning', 'mechanical_object', 'core_question', 'internal_3d',
                       'continuous_motion', 'scientific_causality', 'supporting_story',
                       'discovery_payoff')


def validate_treatment(treatment, facts, *, mechanics=False):
    from .director import validate_storyboard

    positioning = POSITIONING if mechanics else '拆开机器，看见发明背后的智慧。'
    if treatment.get('positioning') != positioning:
        raise ValueError('Treatment must use the project positioning')
    required = ('context', 'mechanism', 'science', 'resolution', 'takeaway') if mechanics else TREATMENT_FIELDS
    for key in ('question', *required):
        if not nonempty(treatment.get(key)):
            raise ValueError('Story Treatment needs ' + key)
    requirements = treatment.get('user_requirements')
    if not isinstance(requirements, list) or not all(map(nonempty, requirements)):
        raise ValueError('Record applicable user creative requirements')
    validate_storyboard(treatment.get('scenes'), facts, mechanics=mechanics)


def validate_creative_gate(task, report, *, duration=None):
    reviewer = report.get('reviewer_thread_id')
    if (not nonempty(reviewer) or report.get('independent_reviewer') is not True
            or not any(row['role'] == 'QA' and row['thread_id'] == reviewer
                       for row in task['agent_runs'])
            or any(row['role'] != 'QA' and row['thread_id'] == reviewer
                   for row in task['agent_runs'])):
        raise ValueError('Creative QA needs a recorded independent QA reviewer')
    decision = report.get('creative_decision', {})
    if not isinstance(decision, dict):
        raise ValueError('Creative QA requires a structured decision')
    status = decision.get('status')
    findings = decision.get('findings', {})
    criteria = MECHANICAL_CRITERIA if mechanism_first(task) else CREATIVE_CRITERIA
    if (not isinstance(status, str) or status not in CREATIVE_VERDICTS
            or not isinstance(findings, dict) or set(findings) != set(criteria)):
        raise ValueError('Creative QA requires a verdict and all applicable findings')
    for finding in findings.values():
        if (not isinstance(finding, dict) or finding.get('status') not in CREATIVE_VERDICTS
                or not nonempty(finding.get('observation'))
                or not nonempty(finding.get('location'))):
            raise ValueError('Each creative finding needs a status and located observation')
    if mechanism_first(task) and any(findings[key]['status'] == 'REVISE' for key in (
            'positioning', 'mechanical_object', 'core_question', 'internal_3d')):
        raise ValueError('Confirmed loss of positioning, scope or core 3D requires REJECT')
    outcomes = {finding['status'] for finding in findings.values()}
    expected = next(value for value in ('REJECT', 'REVISE', 'UNKNOWN', 'PASS') if value in outcomes)
    if status != expected:
        raise ValueError('Creative verdict must reflect the strongest finding')
    if status in {'REVISE', 'REJECT'} and not nonempty(decision.get('revision')):
        raise ValueError('Creative veto requires a concrete revision')
    method = decision.get('method')
    if duration is None:
        if method != 'document_review':
            raise ValueError('Story QA reviews the written Treatment and storyboard')
    else:
        if method not in {'continuous_video', 'continuous_audiovisual', 'sampled_frames',
                          'document_review', 'unavailable'}:
            raise ValueError('Record the actual method used for visual narrative QA')
        if status == 'PASS':
            coverage = decision.get('covered_seconds')
            if (method not in {'continuous_video', 'continuous_audiovisual'}
                    or not number(coverage) or abs(coverage - duration) > 0.001):
                raise ValueError('Creative PASS requires viewing the complete current moving edit')
    return status


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
