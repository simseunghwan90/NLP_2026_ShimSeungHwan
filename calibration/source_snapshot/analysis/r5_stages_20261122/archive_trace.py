"""Archive visible user directions, commentary and tool calls for this experiment only."""
import datetime
import hashlib
import json
import os
from pathlib import Path
from common import OUT


def main():
    thread=os.environ.get('CODEX_THREAD_ID')
    if thread!='01a1fcc8-d467-7640-b196-9953112651ab':
        raise RuntimeError('This archival script is pinned to the original experiment thread')
    source=Path('/home/simseunghwan/.codex/sessions/2026/11/21/rollout-2026-11-21T15-26-22-'+thread+'.jsonl')
    raw=source.read_bytes(); records=[]; contexts=[]; calls=0
    for line in raw.splitlines():
        try:r=json.loads(line)
        except json.JSONDecodeError:continue
        payload=r.get('payload',{})
        if r.get('type')=='turn_context':
            contexts.append(dict(timestamp=r.get('timestamp'),**{k:payload[k] for k in ['model','effort','summary','cwd'] if k in payload}))
        elif r.get('type')=='response_item':
            typ=payload.get('type')
            if typ in ['function_call','custom_tool_call']:
                records.append(r);calls+=1
            elif typ=='message' and (payload.get('role')=='user' or
                    (payload.get('role')=='assistant' and payload.get('channel') in ['commentary','final'])):
                records.append(r)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    dest=OUT/('agent_visible_trace_'+stamp+'.jsonl')
    with dest.open('x') as f:
        for r in records:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    manifest=dict(source=str(source),thread_id=thread,snapshot_utc=stamp,source_prefix_bytes=len(raw),
                  source_prefix_sha256=hashlib.sha256(raw).hexdigest(),archive=dest.name,archive_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
                  visible_records=len(records),tool_calls=calls,configured_turn_metadata=contexts,
                  scope='Visible user messages, assistant commentary/final messages and tool calls. Tool outputs remain in native evidence/logs where archived. Excludes reasoning, system/developer messages, world_state and compaction internals. Snapshot ends before final response.',
                  model_note='Model and effort are recorded client configuration, not independent verification of server weights/build.')
    (OUT/'trace_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    provenance=json.loads((OUT/'PROVENANCE.json').read_text())
    provenance['configured_model_metadata']=contexts[-1] if contexts else None
    provenance['agent']='Codex; configured model and effort recorded in trace_manifest.json; exact server build not independently verified'
    provenance['visible_trace']=dest.name
    (OUT/'PROVENANCE.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ['archive','visible_records','tool_calls','snapshot_utc']},indent=2))

if __name__=='__main__':main()
