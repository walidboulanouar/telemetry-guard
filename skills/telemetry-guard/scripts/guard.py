#!/usr/bin/env python3
"""Offline allowlisted settings audit and optimistic reversible edits. Stdlib only."""
import argparse, codecs, contextlib, hashlib, html, json, os, platform, re, stat, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMAS = {
 'vscode': {'keys': ('telemetry.telemetryLevel',), 'off': 'off', 'valid': ('all','error','crash','off'), 'label': 'VS Code optional telemetry'},
 'nextjs': {'keys': ('telemetry','enabled'), 'off': False, 'valid': (True,False), 'label': 'Next.js optional telemetry'},
}
class SafeError(Exception): pass

def fail(code): raise SafeError(code)
def digest(b): return hashlib.sha256(b).hexdigest()
def pairs(items):
 d={}
 for k,v in items:
  if k in d: fail('duplicate_json_key')
  d[k]=v
 return d

def read(path):
 p=Path(path)
 # Refuse symlinks anywhere, including parent directories; no credential stores.
 for q in (p,*p.parents):
  if q.is_symlink(): fail('symlink_refused')
 try:
  if not stat.S_ISREG(p.lstat().st_mode): fail('unsupported_file')
  with open(p,'rb',opener=lambda name, flags: os.open(name, flags | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_NONBLOCK',0))) as f:
   s=os.fstat(f.fileno())
   if not stat.S_ISREG(s.st_mode) or s.st_size>2*1024*1024: fail('unsupported_file')
   if hasattr(os,'getuid') and s.st_uid!=os.getuid(): fail('owner_mismatch')
   b=f.read(2*1024*1024+1)
   if len(b)>2*1024*1024: fail('unsupported_file')
 except FileNotFoundError: fail('settings_missing')
 except PermissionError: fail('settings_unreadable')
 try: d=json.loads(b,object_pairs_hook=pairs,parse_constant=lambda _: fail('non_strict_json_guided_only'))
 except (ValueError,UnicodeError,RecursionError): fail('non_strict_json_guided_only')
 if not isinstance(d,dict): fail('unsupported_schema')
 return b,d

def get(d,keys):
 for k in keys:
  if not isinstance(d,dict): fail('unsupported_schema')
  if k not in d: return False,None
  d=d[k]
 return True,d

def known(app,d):
 s=SCHEMAS[app]; exists,v=get(d,s['keys'])
 if exists and not any(type(v)==type(x) and v==x for x in s['valid']): fail('unknown_control_value')
 return exists,v

def edit_control(raw, keys, value):
 """Replace one validated scalar token without round-tripping unrelated JSON."""
 prefix = b''
 for mark, encoding in ((codecs.BOM_UTF32_BE,'utf-32-be'),(codecs.BOM_UTF32_LE,'utf-32-le'),
                        (codecs.BOM_UTF16_BE,'utf-16-be'),(codecs.BOM_UTF16_LE,'utf-16-le'),
                        (codecs.BOM_UTF8,'utf-8')):
  if raw.startswith(mark):
   prefix = mark
   break
 else:
  encoding = json.detect_encoding(raw)
 text = raw[len(prefix):].decode(encoding)
 space = re.compile(r'[ \t\r\n]*').match
 decode = json.JSONDecoder().raw_decode
 pos = space(text,0).end()
 for wanted in keys:
  pos = space(text,pos+1).end()  # validated object opening brace
  while True:
   key, end = decode(text,pos)
   colon = space(text,end).end()
   start = space(text,colon+1).end()
   if key == wanted:
    pos = start
    break
   _, end = decode(text,start)
   comma = space(text,end).end()
   if text[comma] != ',': fail('unsupported_schema')
   pos = space(text,comma+1).end()
 _, end = decode(text,pos)
 return prefix + (text[:pos] + json.dumps(value) + text[end:]).encode(encoding)

def private_dir(path):
 if os.name=='nt': fail('windows_acl_guided_only')
 p=Path(path).absolute()
 for q in (p,*p.parents):
  if q.is_symlink(): fail('symlink_refused')
 p.mkdir(mode=0o700,parents=True,exist_ok=True)
 s=p.stat()
 if hasattr(os,'getuid') and (s.st_uid!=os.getuid() or s.st_mode & 0o077): fail('private_directory_required')
 return p

def check_settings_metadata(info):
 if info.st_nlink!=1 or not info.st_mode & stat.S_IWUSR or info.st_mode & 0o7000:
  fail('unsupported_settings_metadata')

def preserve_settings_metadata(source, destination_fd):
 info=os.fstat(source.fileno())
 check_settings_metadata(info)
 if info.st_gid!=os.fstat(destination_fd).st_gid: os.fchown(destination_fd,-1,info.st_gid)
 if sys.platform=='darwin':
  import ctypes
  # macOS copyfile.h: ACL | STAT | XATTR, without copying file data.
  libc=ctypes.CDLL(None,use_errno=True)
  if libc.fcopyfile(source.fileno(),destination_fd,None,0x7)!=0: fail('unsupported_settings_metadata')
 elif sys.platform.startswith('linux'):
  for key in os.listxattr(source.fileno()):
   os.setxattr(destination_fd,key,os.getxattr(source.fileno(),key))
 else: fail('unsupported_settings_metadata')
 os.fchmod(destination_fd,stat.S_IMODE(info.st_mode))

def write(path,b,exclusive=False,settings=False):
 p=Path(path)
 if p.is_symlink(): fail('symlink_refused')
 if exclusive and p.exists(): fail('output_exists')
 fd,tmp=tempfile.mkstemp(prefix='.telemetry-guard-',dir=p.parent)
 try:
  os.fchmod(fd,0o600)
  with os.fdopen(fd,'wb') as f:
   f.write(b)
   f.flush()
   if settings:
    with open(p,'r+b',opener=lambda name, flags: os.open(name,flags | os.O_NOFOLLOW | os.O_NONBLOCK)) as source:
     preserve_settings_metadata(source,fd)
   os.fsync(fd)
  if exclusive:
   os.link(tmp,p); os.unlink(tmp)
  else: os.replace(tmp,p)
 finally:
  if os.path.exists(tmp): os.unlink(tmp)

def enc(d): return (json.dumps(d,indent=2,ensure_ascii=True)+'\n').encode()
@contextlib.contextmanager
def lock(p):
 import fcntl
 if any(q.is_symlink() for q in (p,*p.parents)): fail('symlink_refused')
 if (p.parent/('.'+p.name+'.telemetry-guard.lock')).exists(): fail('busy_no_retry')
 fd=os.open(p.parent,os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
 try:
  try: fcntl.flock(fd,fcntl.LOCK_EX | fcntl.LOCK_NB)
  except BlockingIOError: fail('busy_no_retry')
  yield
 finally: os.close(fd)

def default_path(app):
 h=Path.home(); system=platform.system()
 if app=='vscode':
  if system=='Darwin': return h/'Library/Application Support/Code/User/settings.json'
  if system=='Windows': return Path(os.environ.get('APPDATA',str(h/'AppData/Roaming')))/'Code/User/settings.json'
  return h/'.config/Code/User/settings.json'
 # Next Conf locations vary with installed version. Require confirmed explicit path.
 return None

def finding(app,path):
 if path is None: return {'product':app,'status':'unknown','reason':'confirmed_settings_path_required'}
 try:
  _,d=read(path); exists,v=known(app,d)
  return {'product':app,'status':('optional_setting_off' if exists and v==SCHEMAS[app]['off'] else 'optional_setting_enabled' if exists else 'default_unknown'),'control':'.'.join(SCHEMAS[app]['keys'])}
 except SafeError as e: return {'product':app,'status':'unknown','reason':str(e)}

# AppKit exposes open GUI applications without querying windows or process arguments.
# Match the one supported GUI bundle on-device; omit all bundle identifiers from output.
APPKIT_QUERY = r"""
ObjC.import('AppKit')
const running = $.NSWorkspace.sharedWorkspace.runningApplications
const rows = []
for (let i = 0; i < running.count; i++) {
    const app = running.objectAtIndex(i)
    const policy = Number(app.activationPolicy)
    if (policy !== 0 && policy !== 1) continue
    if (policy === 1) {
        const path = ObjC.unwrap(app.bundleURL.path)
        if (typeof path !== 'string' || !/^\/Applications\/[^/]+\.app\/?$/i.test(path)) continue
    }
    const name = ObjC.unwrap(app.localizedName)
    const row = {name: typeof name === 'string' ? name : '', role: policy === 0 ? 'regular' : 'accessory'}
    const bundle = ObjC.unwrap(app.bundleIdentifier)
    if (bundle === 'com.microsoft.VSCode') row.settings_product = 'vscode'
    if (bundle === 'com.google.Chrome') row.settings_product = 'chrome'
    rows.push(row)
}
JSON.stringify(rows)
"""

def running_apps():
 observed=datetime.now(timezone.utc).isoformat(timespec='seconds')
 inventory={'observed_at':observed,'status':'unknown','apps':[]}
 if platform.system()!='Darwin':
  return {**inventory,'reason':'The open-app inventory is available on macOS.'}
 try:
  result=subprocess.run(['/usr/bin/osascript','-l','JavaScript','-e',APPKIT_QUERY],
                        capture_output=True,check=True,timeout=10)
  raw=json.loads(result.stdout)
  if not isinstance(raw,list): raise ValueError()
  apps=[]
  for item in raw:
   name=item['name'].strip()
   if not name or not name.isprintable() or any(c in name for c in ('/','@','\\')):
    name='Unnamed app'
   role=item['role']
   if role not in ('regular','accessory'): raise ValueError()
   row={'name':name,'role':role}
   if item.get('settings_product') in ('vscode','chrome'): row['settings_product']=item['settings_product']
   apps.append(row)
 except (OSError,subprocess.SubprocessError,TypeError,KeyError,ValueError,AttributeError):
  return {**inventory,'reason':'macOS did not return the open-app list for this session.'}
 return {**inventory,'status':'available','apps':sorted(apps,key=lambda row:row['name'].casefold())}

PRODUCT_NAMES={'vscode':'Visual Studio Code','nextjs':'Next.js','chrome':'Google Chrome'}

def chrome_finding():
 # Read only the stable macOS installation's explicit consent, never profile history.
 row={'product':'chrome','control':'user_experience_metrics.reporting_enabled'}
 try:
  _,settings=read(Path.home()/'Library/Application Support/Google/Chrome/Local State')
  exists,value=get(settings,('user_experience_metrics','reporting_enabled'))
  if not exists: return {**row,'status':'default_unknown'}
  if type(value) is not bool: fail('unknown_control_value')
  return {**row,'status':'optional_setting_enabled' if value else 'optional_setting_off'}
 except SafeError as error: return {**row,'status':'unknown','reason':str(error)}

STATUS_LABELS={'optional_setting_off':'Optional telemetry is off in the local setting.',
               'optional_setting_enabled':'The local setting allows optional telemetry.',
               'default_unknown':'Unknown. The settings file has no explicit value for this control.'}
REASON_LABELS={'confirmed_settings_path_required':'The installed version’s settings location needs confirmation.',
               'settings_missing':'The settings file was absent at the expected location.',
               'settings_unreadable':'The settings file could not be read with the current permissions.',
               'non_strict_json_guided_only':'This settings format requires an in-app check.',
               'duplicate_json_key':'The settings file contains a duplicate key.',
               'unknown_control_value':'The control has an unsupported value.',
               'unsupported_schema':'The settings format is unsupported.',
               'symlink_refused':'The settings location includes a symbolic link.',
               'owner_mismatch':'The settings file has another owner.',
               'unsupported_file':'The settings file type or size is unsupported.'}

def status_text(row):
 if row['product']=='chrome' and row['status'] in ('optional_setting_enabled','optional_setting_off'):
  state='on' if row['status']=='optional_setting_enabled' else 'off'
  return f'The saved usage statistics and crash-reporting preference is {state}. Effective policy and uploads were not checked.'
 if row['status'] in STATUS_LABELS: return STATUS_LABELS[row['status']]
 return 'Unknown. '+REASON_LABELS.get(row.get('reason'),'The local setting could not be verified.')

def inventory_html(inventory,rows):
 content='<h2>Open Mac apps</h2><p>Snapshot at '+html.escape(inventory['observed_at'])+'.</p>'
 if inventory['status']=='unknown':
  return content+'<p>Unknown. '+html.escape(inventory['reason'])+'</p>'
 checks={row['product']:row for row in rows}
 for role,title,description in (
     ('regular','Regular GUI apps','Includes apps with closed or hidden windows.'),
     ('accessory','Menu bar and background apps','Includes accessory apps installed directly in Applications. Nested helpers and system services are outside this list.')):
  apps=[app for app in inventory['apps'] if app['role']==role]
  content+=f'<h3>{title} ({len(apps)})</h3><p>{description}</p>'
  if not apps:
   content+='<p>macOS returned no apps in this group.</p>'
   continue
  content+='<table><tr><th>App</th><th>Optional telemetry setting</th></tr>'
  for app in apps:
   check=checks.get(app.get('settings_product'))
   label=status_text(check) if check else 'Unassessed. No app-specific check ran.'
   content+='<tr><td>'+html.escape(app['name'])+'</td><td>'+html.escape(label)+'</td></tr>'
  content+='</table>'
 return content

def report(args):
 if args.app=='host' and args.settings: fail('invalid_arguments')
 out=private_dir(args.out)
 if any(os.path.lexists(out/name) for name in ('summary.json','summary.html')): fail('output_exists')
 apps=list(SCHEMAS) if args.app=='host' else [args.app]
 rows=[finding(a,Path(args.settings).absolute() if args.settings and len(apps)==1 else default_path(a)) for a in apps]
 if args.app=='host' and platform.system()=='Darwin': rows.append(chrome_finding())
 coverage_names={'vscode':'VS Code stable user settings (strict JSON)', 'nextjs':'Next.js Conf telemetry setting',
                 'chrome':'Chrome stable saved usage and crash-reporting preference (read-only)'}
 coverage=[]
 for row in rows:
  name=coverage_names[row['product']]
  if row['status'] in ('unknown','default_unknown'):
   coverage.append(f'{name}: unverified; guided review required')
  else:
   coverage.append(f'{name}: local control verified')
 d={'scope':'known settings markers only; no process arguments, sockets, logs, raw content, credentials or peers collected','findings':rows,'coverage':coverage, 'limitations':['No proof of network silence or complete flow inventory','Browser, signed-in cloud state, extensions, remote profiles and daemons require separate guided verification','Model API calls, update checks, security/audit logging and unknown traffic are not disabled']}
 if args.app=='host':
  d['scope']='Open Mac apps and supported local telemetry settings at the time of this audit.'
  d['running_apps']=running_apps()
 body='<html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"><title>Telemetry guard</title><style>body{font:16px system-ui;max-width:850px;margin:3rem auto;padding:1rem}td,th{padding:.6rem;text-align:left;border-bottom:1px solid #ccc}</style></head><body><h1>Local telemetry settings audit</h1><p>'+html.escape(d['scope'])+'</p>'
 if 'running_apps' in d: body+=inventory_html(d['running_apps'],rows)
 body+='<h2>Local settings checks</h2><p>These checks look for supported controls even when the product is closed.</p><table><tr><th>Product</th><th>Finding</th></tr>'
 for r in rows: body+='<tr><td>'+html.escape(PRODUCT_NAMES[r['product']])+'</td><td>'+html.escape(status_text(r))+'</td></tr>'
 body+='</table><h2>Coverage and limits</h2><ul>'+''.join('<li>'+html.escape(x)+'</li>' for x in d['coverage']+d['limitations'])+'</ul></body></html>'
 with lock(out/'summary.json'):
  if any(os.path.lexists(out/name) for name in ('summary.json','summary.html')): fail('output_exists')
  write(out/'summary.json',enc(d),True)
  try: write(out/'summary.html',body.encode(),True)
  except Exception:
   (out/'summary.json').unlink()
   raise
 return {'result':'report_written','products':len(rows),'settings_mutated':False}

def plan(args):
 p=Path(args.settings).absolute()
 b,d=read(p); exists,v=known(args.app,d)
 if not exists: fail('explicit_control_required_use_guided_default_review')
 if v==SCHEMAS[args.app]['off']: fail('already_off')
 check_settings_metadata(p.lstat())
 out=private_dir(args.out)
 tx={'version':1,'app':args.app,'target':str(p),'before_hash':digest(b),'prior_exists':exists,'prior':v,'state':'planned'}
 write(out/'transaction.json',enc(tx),True)
 schema=SCHEMAS[args.app]
 return {'result':'planned','product':args.app,'change':'optional_telemetry_off',
         'control':'.'.join(schema['keys']),'prior':v,'proposed':schema['off'],
         'requires':'product/version and setting-location evidence, closed writer, authorization'}

def transaction(args):
 if not args.authorized: fail('authorization_required')
 path=Path(args.transaction).absolute()
 if not path.parent.is_dir(): fail('settings_missing')
 private_dir(path.parent)
 _,tx=read(path)
 if set(tx)-{'version','app','target','before_hash','prior_exists','prior','state','after_hash','undo_hash'}: fail('invalid_transaction')
 if type(tx.get('version')) is not int or tx['version']!=1 or tx.get('prior_exists') is not True: fail('invalid_transaction')
 app=tx['app']; s=SCHEMAS[app]; p=Path(tx['target'])
 known(app, {s['keys'][0]:tx['prior']} if len(s['keys'])==1 else {s['keys'][0]:{s['keys'][1]:tx['prior']}})
 with lock(p):
  b,d=read(p); exists,current=known(app,d)
  check_settings_metadata(p.lstat())
  if args.command=='apply':
   if tx['state']!='planned': fail('invalid_transaction_state')
   if digest(b)!=tx['before_hash']: fail('conflict_no_write')
   if not exists or current!=tx['prior'] or current==s['off']: fail('invalid_transaction')
   new=edit_control(b,s['keys'],s['off'])
   # Journal desired hash before changing settings: interrupted write can be recovered.
   tx['after_hash']=digest(new); tx['state']='applying'; write(path,enc(tx))
   if read(p)[0]!=b: fail('conflict_no_write')
   write(p,new,settings=True); tx['state']='applied'; write(path,enc(tx))
  else:
   if tx['state'] not in ('applied','applying','undoing'): fail('invalid_transaction_state')
   if digest(b)==tx['before_hash'] and tx['state']=='applying':
    tx['state']='undone'; write(path,enc(tx)); return {'result':'unchanged_recovered'}
   if tx['state']=='undoing' and digest(b)==tx.get('undo_hash') and exists and current==tx['prior']:
    tx['state']='undone'; write(path,enc(tx)); return {'result':'undone','product':app,'setting_verified':True,'network_silence_proven':False}
   if digest(b)!=tx['after_hash']: fail('conflict_no_write')
   if not exists or current!=s['off']: fail('invalid_transaction')
   new=edit_control(b,s['keys'],tx['prior'])
   tx['undo_hash']=digest(new); tx['state']='undoing'; write(path,enc(tx))
   if read(p)[0]!=b: fail('conflict_no_write')
   write(p,new,settings=True); tx['state']='undone'; write(path,enc(tx))
  _,check=read(p); exists,v=known(app,check)
  expected=s['off'] if args.command=='apply' else tx['prior']
  if not exists or type(v)!=type(expected) or v!=expected: fail('verification_failed')
 return {'result':tx['state'],'product':app,'setting_verified':True,'network_silence_proven':False}

def main():
 class Parser(argparse.ArgumentParser):
  def error(self,message):
   print(json.dumps({'result':'refused','reason':'invalid_arguments'})); raise SystemExit(2)
 p=Parser(description=__doc__)
 sub=p.add_subparsers(dest='command',required=True)
 a=sub.add_parser('audit'); a.add_argument('--app',choices=['host',*SCHEMAS],default='host'); a.add_argument('--settings'); a.add_argument('--out',required=True)
 a=sub.add_parser('plan'); a.add_argument('--app',choices=SCHEMAS,required=True); a.add_argument('--settings',required=True); a.add_argument('--out',required=True)
 for name in ('apply','undo'):
  a=sub.add_parser(name); a.add_argument('--transaction',required=True); a.add_argument('--authorized',action='store_true')
 args=p.parse_args()
 try:
  r=report(args) if args.command=='audit' else plan(args) if args.command=='plan' else transaction(args)
  print(json.dumps(r)); return 0
 except SafeError as e: print(json.dumps({'result':'refused','reason':str(e)})); return 2
 except Exception: print(json.dumps({'result':'refused','reason':'local_operation_failed_no_details'})); return 2
if __name__=='__main__': sys.exit(main())
