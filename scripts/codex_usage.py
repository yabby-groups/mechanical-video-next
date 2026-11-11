#!/usr/bin/env -S uv run python
"""Export native collaboration metadata/usage only, never conversation content.

Codex session JSONL is a local diagnostic format, not a stable public API.
Missing counters remain null. Do not equate tokens with monetary cost.
"""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mechanical_video_next.workflow import filehash, write


def rows(path):
    with path.open() as handle:
        for line in handle:
            try:
                yield json.loads(line)
            except ValueError:
                # An active native session may have a partial final record.
                continue


def summarize(path):
    meta = {}
    latest = None
    starts = {}
    completed = []
    calls = []
    for row in rows(path):
        payload = row.get('payload', {})
        if row.get('type') == 'session_meta' and not meta:
            meta = payload
        elif row.get('type') == 'event_msg':
            kind = payload.get('type')
            if kind == 'token_count' and payload.get('info'):
                latest = payload['info'].get('total_token_usage')
            elif kind == 'task_started':
                starts[payload['turn_id']] = (row.get('timestamp'), dict(latest or {}))
            elif kind == 'task_complete':
                started, before = starts.get(payload['turn_id'], (None, {}))
                completed.append(dict(turn_id=payload['turn_id'], started=started,
                                      completed=row.get('timestamp'),
                                      seconds=payload['duration_ms']/1000
                                      if payload.get('duration_ms') is not None else None,
                                      usage={k: v-before.get(k, 0) for k, v in latest.items()}
                                      if latest else None))
        elif row.get('type') == 'response_item' and payload.get('type') == 'function_call':
            name = payload.get('name', '')
            if ('collaboration.' in name or name.startswith('collaboration__')
                    or name in {'spawn_agent', 'followup_task', 'send_message', 'interrupt_agent'}):
                try:
                    args = json.loads(payload.get('arguments', '{}'))
                except ValueError:
                    args = {}
                calls.append(dict(timestamp=row.get('timestamp'), tool=name,
                                  call_id=payload.get('call_id'),
                                  task_name=args.get('task_name'), target=args.get('target')))
    source = meta.get('source', {})
    spawned = source.get('subagent', {}).get('thread_spawn', {}) if isinstance(source, dict) else {}
    return dict(thread_id=meta.get('id'), agent_path=spawned.get('agent_path'),
                parent_thread_id=spawned.get('parent_thread_id'),
                source_file=path.name, source_sha256=filehash(path),
                total_usage_snapshot=latest, completed_turns=completed,
                # Forked logs can contain inherited parent tool calls. The root
                # log is the authoritative dispatch record; do not double count.
                collaboration_calls=calls if not spawned else [])


def export(parent, directory, output):
    found = []
    for path in directory.glob('*.jsonl'):
        # Inspect only the metadata record before reading unrelated sessions.
        first = next((r['payload'] for r in rows(path) if r.get('type') == 'session_meta'), {})
        source = first.get('source', {})
        spawned = source.get('subagent', {}).get('thread_spawn', {}) if isinstance(source, dict) else {}
        if first.get('id') == parent or spawned.get('parent_thread_id') == parent:
            found.append(summarize(path))
    report = dict(schema_version=1, captured_epoch=time.time(), root_thread_id=parent,
                  source='Native local Codex session metadata and counters', threads=found,
                  monetary_cost=None, human_interventions=None,
                  limitations=['Snapshot includes engineering and production turns; not per-video cost',
                               'Root thread is still active; snapshot is not final billing',
                               'Reused child threads have multiple roles; see completed turns',
                               'Cached input is a subset of input, reasoning is a subset of output',
                               'Local JSONL schema may change; absent counters remain null'])
    write(output, report)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root-thread', required=True)
    p.add_argument('--directory', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    result = export(a.root_thread, a.directory, a.output)
    print(json.dumps(dict(threads=len(result['threads']), output=str(a.output))))
