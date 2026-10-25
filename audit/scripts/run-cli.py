import json, os, re, subprocess, tempfile
from pathlib import Path
root=Path.cwd(); out=root/'audit/cli'; tmp=Path(tempfile.mkdtemp(prefix='blackbox-audit-cli-')); py=str(root/'.venv/bin/python')
env={k:os.environ[k] for k in ('PATH','HOME','TMPDIR','LANG') if k in os.environ}; env['BLACKBOX_BACKEND']='rules'
results=[]
def run(n,args,validate):
 ident=f'BB-{n:03}'; cmd=[py]+args
 p=subprocess.run(cmd,cwd=root,env=env,capture_output=True,text=True)
 (out/f'{ident}.stdout.txt').write_text(p.stdout); (out/f'{ident}.stderr.txt').write_text(p.stderr)
 try: validate(p); status='PASS'; reason=''
 except Exception as e: status='FAIL'; reason=str(e)
 result={'id':ident,'command':cmd,'exit_code':p.returncode,'status':status,'reason':reason,'stdout':f'audit/cli/{ident}.stdout.txt','stderr':f'audit/cli/{ident}.stderr.txt'}
 (out/f'{ident}.json').write_text(json.dumps(result,indent=2)); results.append(result); print(ident,status,reason,flush=True)
 return p
def need(ok,msg):
 if not ok: raise AssertionError(msg)
folder=tmp/'collision-000'
run(32,['-m','blackbox','simulate','collision','--seed','0','--out',str(tmp),'--no-frames'],lambda p:need(p.returncode==0 and p.stdout.strip()==str(folder) and json.loads((folder/'run.json').read_text())['format']=='blackbox.run/1','simulate result differs'))
def explaincheck(p):
 x=json.loads((folder/'explain.json').read_text()); (out/'rules-explain.json').write_text(json.dumps(x,indent=1))
 expected=[x['headline']]+[f"  [{c['kind']}] {c['text']}  ({', '.join(c['cites'])})" for c in x['claims']]+[str(folder/'explain.json')]
 need(p.returncode==0 and p.stdout.splitlines()==expected and x['format']=='blackbox.explain/1','rules output differs')
run(33,['-m','blackbox','explain',str(folder),'--backend','rules'],explaincheck)
def jsoncheck(p):
 x=json.loads(p.stdout); full=json.loads((folder/'explain.json').read_text())
 need(p.returncode==0 and x['format']=='blackbox.explain-summary/1' and all(k in x for k in ['run','run_sha256','explanation','verdict','kept','refuted','evidence']),'summary schema differs')
 need(x['evidence']==[{k:e.get(k) for k in ('id','source','channel','t0','t1','value','note')} for e in full['evidence']],'evidence does not include every produced span')
 need(x['explanation']==str(folder/'explain.json'),'explanation output path differs')
run(34,['-m','blackbox','explain',str(folder),'--json'],jsoncheck)
run(35,['-m','blackbox','verify',str(folder/'explain.json')],lambda p:need(p.returncode==0 and re.fullmatch(r'VERIFIED: \d+ checks re-run against collision-000 \([0-9a-f]{12}\)\n',p.stdout) is not None,'verify result differs'))
f=folder/'run.json'; data=json.loads(f.read_text()); data['series']['gripper_current'][0]+=0.1; f.write_text(json.dumps(data))
(out/'tamper.json').write_text(json.dumps({'field':'series.gripper_current[0]','delta':0.1,'scope':'temporary CLI run only'},indent=2))
run(36,['-m','blackbox','verify',str(folder/'explain.json')],lambda p:need(p.returncode==1 and p.stdout.startswith('MISMATCH: ') and '  - log hash differs from the one the explanation was made from\n' in p.stdout,'tampering not detected'))
def evalcheck(p):
 expected=['collision -> collision.unmodeled_obstacle: 1','nominal -> None: 1','slip_grip -> drop.low_grip_force: 1','slip_rushed -> drop.aggressive_motion: 1','timeout -> timeout.unreachable: 1','wrong_object -> wrong_object.perception_confusion: 1']
 need(p.returncode==0 and re.match(r'6/6 runs explained correctly \(100.0%\) in [\d.]+ s\n',p.stdout) and p.stdout.splitlines()[1:]==['  '+s for s in expected],'eval output differs')
run(37,['-m','blackbox','eval','--seeds','1'],evalcheck)
run(38,['-m','blackbox','simulate','invalid_scenario'],lambda p:need(p.returncode==2 and "blackbox simulate: error: argument scenario: invalid choice: 'invalid_scenario' (choose from 'nominal', 'slip_grip', 'slip_rushed', 'collision', 'wrong_object', 'timeout')" in p.stderr,'argparse output differs'))
run(39,['-m','blackbox','explain','nonexistent_dir'],lambda p:need(p.returncode==1 and "blackbox.runlog.LogError: cannot read nonexistent_dir: [Errno 2] No such file or directory: 'nonexistent_dir'" in p.stderr,'missing path error differs'))
results.append({'id':'BB-040','status':'UNTESTED','reason':'needs BLACKBOX_LLM_API_KEY or NVIDIA_API_KEY'})
run(41,['-m','pytest','-q','tests/test_llm.py::test_llm_unreachable_falls_back_to_rules'],lambda p:need(p.returncode==0 and '1 passed' in p.stdout,'unreachable endpoint regression test failed'))
(out/'results.json').write_text(json.dumps(results,indent=2))
import shutil
shutil.rmtree(tmp)
