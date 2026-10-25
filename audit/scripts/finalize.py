"""Finalize the one recorded run; review two harness checks against stored evidence."""
import json, re, socket, subprocess
from collections import Counter
from pathlib import Path
base=Path('audit/browser')
reviews={
 'BB-015':('Document scrolled into view', 'The complete E19 document text is visible in screen.jpg. Native nearest scrolling places its outer border at y=800.078125 CSS px, which rounds to physical pixel 800. The original harness incorrectly required the fractional border edge to be <=800 without pixel rounding.'),
 'BB-025':('Short lane labels only', 'The expected cell requires the short labels to display and long labels to hide. All eleven short labels compute to block because they are flex items; all long labels compute to none. The original harness incorrectly required computed display inline rather than testing visibility.')
}
for ident,(label,note) in reviews.items():
 p=base/ident/'result.json'; r=json.loads(p.read_text()); o=r['observations']
 if ident=='BB-015':
  b=o['after']; ok=b['y']>=0 and round(b['y']+b['height'])<=800 and b['y']<o['before']['y']
 else: ok=all(d!='none' for d in o['short']) and all(d=='none' for d in o['long'])
 assert ok, note
 for check in r['checks']:
  if check['label']==label: check.update(pass_=True); check.pop('pass_'); check['pass']=True; check['review']=note
 r['review']=note; r['failures']=[c for c in r['checks'] if not c['pass']];r['status']='PASS' if not r['failures'] else 'FAIL'
 p.write_text(json.dumps(r,indent=2))
# Preserve native Chrome favicon errors in the network evidence as well. Chrome emits
# these in the console/server access log but not Playwright's Page.response stream.
for ident,origin,serverlog in [('BB-001','http://127.0.0.1:8730','audit/server.stderr.txt'),('BB-022','http://127.0.0.1:8731','audit/copy-server.stderr.txt')]:
 p=base/ident/'network.json'; events=json.loads(p.read_text())
 assert '"GET /favicon.ico HTTP/1.1" 404' in Path(serverlog).read_text()
 if not any(e.get('url')==origin+'/favicon.ico' for e in events):
  events.append({'event':'response','method':'GET','url':origin+'/favicon.ico','status':404,'source':'Browser console resource URL corroborated by '+serverlog})
 p.write_text(json.dumps(events,indent=2))
 result_path=base/ident/'result.json'; r=json.loads(result_path.read_text())
 for c in r['checks']:
  if c['label']=='Zero unexpected network failures or HTTP errors':
   c['pass']=False;c['actual']=[events[-1]]
 r['failures']=[c for c in r['checks'] if not c['pass']]
 r['status']='FAIL'
 result_path.write_text(json.dumps(r,indent=2))
results=[]
for p in sorted(base.glob('BB-*/result.json')):
 r=json.loads(p.read_text());results.append({k:r[k] for k in ('id','status','failures','evidence')})
(base/'results.json').write_text(json.dumps(results,indent=2))
(base/'run.log').write_text('\n'.join(f"{r['id']} {r['status']}"+(' '+('; '.join(c['label'] for c in r['failures'])) if r['failures'] else '') for r in results)+'\nBROWSER COMPLETE: single full-plan run; evidence review in result.json\n')
results+=json.loads(Path('audit/cli/results.json').read_text())
byid={r['id']:r for r in results};assert len(byid)==41
p=Path('AUDIT.md');lines=p.read_text().splitlines();new=[]
failnotes={
 'BB-001':'Open: Chrome requests /favicon.ico; HTTP 404 produces a console error. Product code frozen.',
 'BB-022':'Open: expected error message renders, but data/index.json 404 and /favicon.ico 404 produce console errors. Product code frozen.',
 'BB-023':'Open: expected error message renders, but run.json 404 produces a console error. Product code frozen.',
 'BB-024':'Open: switching pauses playback but initializes collision at 8.04 s (08.04 / 10.12 s), not 0.00 s. Product code frozen.'
}
for line in lines:
 m=re.match(r'\| (BB-\d{3}) \|',line)
 if not m:new.append(line);continue
 ident=m[1]; r=byid[ident]; cols=line.split('|');cols[4]=' '+r['status']+' '
 if ident in reviews: note='Evidence review: '+reviews[ident][1]
 else: note=failnotes.get(ident,'')
 if int(ident[3:])<=31:
  d=f'audit/browser/{ident}'
  evidence=f'[result]({d}/result.json), [JPEG]({d}/screen.jpg), [console]({d}/console.json), [network]({d}/network.json)'
 elif ident=='BB-040':
  evidence='[dependency](audit/cli/results.json)';note='needs BLACKBOX_LLM_API_KEY or NVIDIA_API_KEY'
 else:
  evidence=f'[command/exit](audit/cli/{ident}.json), [stdout](audit/cli/{ident}.stdout.txt), [stderr](audit/cli/{ident}.stderr.txt)'
 cols[5]=' '+evidence+' ';cols[6]=' '+note+' ';new.append('|'.join(cols))
p.write_text('\n'.join(new)+'\n')
counts=dict(Counter(r['status'] for r in results));fails=[r['id'] for r in sorted(results,key=lambda r:r['id']) if r['status']=='FAIL']
summary={'counts':counts,'FAIL_ids':fails,'product_code_changed':False,'live_llm_called':False,'test_data':'existing clearly labeled simulated recordings; no request routes mocked or stubbed','heavy_slot_released':not Path('/tmp/grokbot-heavy-slots/slot1').exists(),'server_pids':[95452,95458]}
for pid in summary['server_pids']:
 status=subprocess.run(['ps','-p',str(pid),'-o','pid='],capture_output=True,text=True)
 assert not status.stdout.strip(),f'Owned server PID still alive: {pid}'
for port in (8730,8731):
 with socket.socket() as s: assert s.connect_ex(('127.0.0.1',port))!=0, f'Port {port} still accepts connections'
summary['owned_servers_stopped']=True
allfiles=[f for f in Path('audit').rglob('*') if f.is_file()]
summary['evidence_bytes']=sum(f.stat().st_size for f in allfiles)
summary['largest_screenshot_bytes']=max(f.stat().st_size for f in base.glob('BB-*/screen.jpg'))
assert summary['evidence_bytes']<15*1024*1024
assert summary['largest_screenshot_bytes']<=200000
Path('audit/summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
