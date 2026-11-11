import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('codex_usage', Path(__file__).resolve().parents[1]/'scripts/codex_usage.py')
usage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usage)


class NativeUsageTests(unittest.TestCase):
    def test_child_identity_and_usage_do_not_become_inherited_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'child.jsonl'
            records = [
                {'type':'session_meta','payload':{'id':'child','source':{'subagent':{'thread_spawn':{'parent_thread_id':'root','agent_path':'/root/qa'}}}}},
                {'type':'session_meta','payload':{'id':'root','source':'cli'}},
                {'type':'event_msg','timestamp':'start','payload':{'type':'task_started','turn_id':'turn'}},
                {'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':20,'output_tokens':2,'total_tokens':22}}}},
                {'type':'event_msg','timestamp':'end','payload':{'type':'task_complete','turn_id':'turn','duration_ms':1250}},
                {'type':'response_item','payload':{'type':'function_call','name':'spawn_agent','arguments':'{}'}},
            ]
            path.write_text('\n'.join(json.dumps(r) for r in records)+'\n{"partial":')
            result = usage.summarize(path)
            self.assertEqual(result['thread_id'], 'child')
            self.assertEqual(result['parent_thread_id'], 'root')
            self.assertEqual(result['total_usage_snapshot']['total_tokens'], 22)
            self.assertEqual(result['completed_turns'][0]['seconds'], 1.25)
            self.assertEqual(result['collaboration_calls'], [])

    def test_missing_usage_stays_null_and_root_dispatch_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'root.jsonl'
            records = [{'type':'session_meta','payload':{'id':'root','source':'cli'}},
                       {'type':'event_msg','payload':{'type':'task_complete','turn_id':'missing-duration'}},
                       {'type':'response_item','timestamp':'now','payload':{'type':'function_call','name':'spawn_agent','call_id':'call','arguments':'{"task_name":"qa","message":"private prompt"}'}}]
            path.write_text('\n'.join(json.dumps(r) for r in records))
            result = usage.summarize(path)
            self.assertIsNone(result['total_usage_snapshot'])
            self.assertIsNone(result['completed_turns'][0]['seconds'])
            self.assertEqual(result['collaboration_calls'][0]['task_name'], 'qa')
            self.assertNotIn('private prompt', json.dumps(result))
