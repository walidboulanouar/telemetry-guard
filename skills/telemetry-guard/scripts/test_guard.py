#!/usr/bin/env python3
"""Behavioral tests in disposable private settings; never read live settings."""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import guard
GUARD=Path(__file__).with_name('guard.py')
SECRET='SYNTHETIC_SECRET_DO_NOT_SHARE_81726'
class Behavior(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='telemetry-guard-test-'); self.root=Path(self.tmp.name).resolve(); self.root.chmod(0o700)
  self.env={**os.environ,'HOME':str(self.root),'APPDATA':str(self.root/'AppData'),'XDG_CONFIG_HOME':str(self.root/'.config')}
 def tearDown(self): self.tmp.cleanup()
 def runcli(self,*args,ok=True):
  p=subprocess.run([sys.executable,str(GUARD),*map(str,args)],capture_output=True,env=self.env)
  self.assertNotIn(SECRET.encode(),p.stdout+p.stderr); self.assertEqual(p.stderr,b'')
  self.assertEqual(p.returncode,0 if ok else 2,p.stdout.decode())
  return json.loads(p.stdout)
 def setting(self,app):
  p=self.root/'settings.json'; p.write_text(json.dumps({'unrelated':SECRET,**({'telemetry.telemetryLevel':'all'} if app=='vscode' else {'telemetry':{'enabled':True,'salt':SECRET}})})); return p
 def plan(self,app,p,folder='change'):
  self.runcli('plan','--app',app,'--settings',p,'--out',self.root/folder); return self.root/folder/'transaction.json'
 def test_plan_projects_exact_control_and_values(self):
  for app,control,prior,proposed in [('vscode','telemetry.telemetryLevel','all','off'),('nextjs','telemetry.enabled',True,False)]:
   with self.subTest(app=app):
    p=self.setting(app)
    plan=self.runcli('plan','--app',app,'--settings',p,'--out',self.root/app)
    self.assertEqual(plan['control'],control)
    self.assertEqual(plan['prior'],prior)
    self.assertIs(type(plan['prior']),type(prior))
    self.assertEqual(plan['proposed'],proposed)
    self.assertIs(type(plan['proposed']),type(proposed))
    self.assertNotIn(str(self.root),json.dumps(plan))
    self.assertNotIn('unrelated',json.dumps(plan))
 def test_coverage_follows_selected_apps_and_observed_controls(self):
  for app,name,other in [('vscode','VS Code','Next.js'),('nextjs','Next.js','VS Code')]:
   with self.subTest(app=app):
    p=self.setting(app)
    out=self.root/app
    self.runcli('audit','--app',app,'--settings',p,'--out',out)
    coverage=json.loads((out/'summary.json').read_text())['coverage']
    self.assertEqual(len(coverage),1)
    self.assertIn(name,coverage[0])
    self.assertIn('local control verified',coverage[0])
    page=(out/'summary.html').read_text()
    self.assertIn(coverage[0],page)
    self.assertNotIn(other,page)
  out=self.root/'host'
  self.runcli('audit','--app','host','--out',out)
  coverage=json.loads((out/'summary.json').read_text())['coverage']
  self.assertEqual(len(coverage),3 if sys.platform=='darwin' else 2)
  self.assertTrue(all('guided review required' in description for description in coverage))
 def test_inventory_limits_projection_and_renders_human_labels(self):
  sample=[{'name':'Alpha <Test>','role':'regular','settings_product':'vscode','ignored':SECRET},
          {'name':'Accessory','role':'accessory'}, {'name':'/private/path','role':'regular'}]
  output=subprocess.CompletedProcess([],0,json.dumps(sample).encode())
  with patch.object(guard.platform,'system',return_value='Darwin'), patch.object(guard.subprocess,'run',return_value=output):
   snapshot=guard.running_apps()
  self.assertEqual(snapshot['status'],'available')
  self.assertNotIn(SECRET,json.dumps(snapshot))
  self.assertNotIn('/private/path',json.dumps(snapshot))
  self.assertIn({'name':'Alpha <Test>','role':'regular','settings_product':'vscode'},snapshot['apps'])
  rows=[{'product':'vscode','status':'optional_setting_enabled'}]
  page=guard.inventory_html(snapshot,rows)
  self.assertIn('Alpha &lt;Test&gt;',page)
  self.assertIn('Regular GUI apps (2)',page)
  self.assertIn('Menu bar and background apps (1)',page)
  self.assertIn('Unassessed.',page)
  self.assertIn(guard.status_text(rows[0]),page)
 def test_unavailable_inventory_is_distinct_from_empty(self):
  with patch.object(guard.platform,'system',return_value='Linux'), patch.object(guard.subprocess,'run') as run:
   self.assertEqual(guard.running_apps()['status'],'unknown')
   run.assert_not_called()
  with patch.object(guard.platform,'system',return_value='Darwin'), patch.object(guard.subprocess,'run',side_effect=PermissionError(SECRET)):
   inventory=guard.running_apps()
   self.assertEqual(inventory['status'],'unknown')
   self.assertNotIn(SECRET,json.dumps(inventory))
  with patch.object(guard.platform,'system',return_value='Darwin'), patch.object(guard.subprocess,'run',return_value=subprocess.CompletedProcess([],0,b'[]')):
   self.assertEqual(guard.running_apps()['status'],'available')
 def test_chrome_reads_only_explicit_boolean_and_remains_read_only(self):
  with patch.object(Path,'home',return_value=self.root):
   self.assertEqual(guard.chrome_finding()['status'],'unknown')
   p=self.root/'Library/Application Support/Google/Chrome/Local State'
   p.parent.mkdir(parents=True)
   for metrics,status in (({},'default_unknown'),({'reporting_enabled':1},'unknown'),({'reporting_enabled':True},'optional_setting_enabled'),({'reporting_enabled':False},'optional_setting_off')):
    p.write_text(json.dumps({'user_experience_metrics':metrics,'unrelated':SECRET}))
    before=p.read_bytes()
    finding=guard.chrome_finding()
    self.assertEqual(finding['status'],status)
    self.assertNotIn(SECRET,json.dumps(finding))
    self.assertEqual(p.read_bytes(),before)
   self.runcli('plan','--app','chrome','--settings',p,'--out',self.root/'change',ok=False)
 def test_roundtrip_both_products(self):
  for app in ('vscode','nextjs'):
   with self.subTest(app=app):
    p=self.setting(app); before=json.loads(p.read_text()); tx=self.plan(app,p,app)
    self.runcli('apply','--transaction',tx,ok=False)
    self.runcli('apply','--transaction',tx,'--authorized')
    d=json.loads(p.read_text()); self.assertEqual(d['unrelated'],SECRET)
    self.assertEqual(d['telemetry.telemetryLevel'] if app=='vscode' else d['telemetry']['enabled'],'off' if app=='vscode' else False)
    self.assertNotIn(SECRET,tx.read_text())
    self.runcli('undo','--transaction',tx,'--authorized'); self.assertEqual(json.loads(p.read_text()),before)
 def test_apply_and_undo_conflicts_preserve_edits(self):
  p=self.setting('vscode'); tx=self.plan('vscode',p); p.write_text(p.read_text()+' ')
  before=p.read_bytes(); self.assertEqual(self.runcli('apply','--transaction',tx,'--authorized',ok=False)['reason'],'conflict_no_write'); self.assertEqual(p.read_bytes(),before)
  tx=self.plan('vscode',p,'change2'); self.runcli('apply','--transaction',tx,'--authorized'); p.write_text(p.read_text()+' '); before=p.read_bytes()
  self.runcli('undo','--transaction',tx,'--authorized',ok=False); self.assertEqual(p.read_bytes(),before)
 def test_report_projects_only_allowlisted_fields(self):
  p=self.setting('nextjs'); before=p.read_bytes(); out=self.root/'report'
  self.runcli('audit','--app','nextjs','--settings',p,'--out',out)
  self.assertEqual(p.read_bytes(),before)
  for f in out.iterdir():
   b=f.read_bytes(); self.assertNotIn(SECRET.encode(),b); self.assertNotIn(str(self.root).encode(),b)
   self.assertNotIn(b'<script',b); self.assertNotIn(b'src=',b)
   if os.name!='nt': self.assertEqual(f.stat().st_mode & 0o777,0o600)
  self.assertEqual(json.loads((out/'summary.json').read_text())['findings'][0]['status'],'optional_setting_enabled')
 def test_unsupported_and_secret_errors(self):
  p=self.root/'settings.json'
  for content in ('{"telemetry.telemetryLevel":"'+SECRET+'"}', '{//'+SECRET+'\n}', '{"telemetry.telemetryLevel":"off","telemetry.telemetryLevel":"all"}', '[]'):
   p.write_text(content); before=p.read_bytes(); self.plan_failure(p); self.assertEqual(before,p.read_bytes())
  self.runcli('audit','--app',SECRET,'--out',self.root/'report',ok=False)
  self.runcli('audit','--app','vscode','--settings',self.root/SECRET,'--out',self.root/'missing')
 def plan_failure(self,p): self.runcli('plan','--app','vscode','--settings',p,'--out',self.root/'nochange',ok=False)
 def test_symlinks_and_private_dir(self):
  p=self.setting('vscode'); link=self.root/'link'; link.symlink_to(p)
  self.assertEqual(self.runcli('plan','--app','vscode','--settings',link,'--out',self.root/'nochange',ok=False)['reason'],'symlink_refused')
  if os.name!='nt':
   out=self.root/'public'; out.mkdir(mode=0o755)
   self.assertEqual(self.runcli('audit','--out',out,ok=False)['reason'],'private_directory_required')
 def test_interrupted_apply_recovery(self):
  p=self.setting('vscode'); tx=self.plan('vscode',p); t=json.loads(tx.read_text()); t['state']='applying'; t['after_hash']='notwritten'; tx.write_text(json.dumps(t))
  self.assertEqual(self.runcli('undo','--transaction',tx,'--authorized')['result'],'unchanged_recovered')
 def test_interrupted_after_settings_write(self):
  p=self.setting('nextjs'); before=json.loads(p.read_text()); tx=self.plan('nextjs',p)
  self.runcli('apply','--transaction',tx,'--authorized'); t=json.loads(tx.read_text()); t['state']='applying'; tx.write_text(json.dumps(t))
  self.runcli('undo','--transaction',tx,'--authorized'); self.assertEqual(json.loads(p.read_text()),before)
 def test_survey_no_writes_and_unknowns(self):
  out=self.root/'survey'; self.runcli('audit','--out',out)
  rows=json.loads((out/'summary.json').read_text())['findings']; self.assertEqual(len(rows),3 if sys.platform=='darwin' else 2); self.assertTrue(all(r['status']=='unknown' for r in rows))
  self.assertFalse((self.root/'.config').exists())
if __name__=='__main__': unittest.main()
