import importlib.util,json,os,tempfile,threading,unittest,urllib.request,urllib.error,http.cookiejar,re
from pathlib import Path
os.environ['USA_DATA_DIR']=tempfile.mkdtemp(prefix='usa-test-')
spec=importlib.util.spec_from_file_location('server',Path(__file__).parents[1]/'backend/server.py');server=importlib.util.module_from_spec(spec);spec.loader.exec_module(server)
class Flow(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);threading.Thread(target=cls.http.serve_forever,daemon=True).start();cls.base='http://127.0.0.1:'+str(cls.http.server_port)
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close()
 def client(self):return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
 def call(self,client,path,data=None,csrf=None,headers=True):
  h={'X-App-Request':'usa-web'} if headers else {}
  if data is not None:h['Content-Type']='application/json'
  if csrf:h['X-CSRF-Token']=csrf
  req=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers=h)
  try:
   with client.open(req) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def test_admin_finance_and_team(self):
  principal=self.client();finance=self.client();support=self.client();moderator=self.client();public=self.client()
  with server.db() as c:
   for name,email,admin in [('Principal',server.PRIMARY_ADMIN_EMAIL,1),('Finance','finance@example.com',0),('Support','support@example.com',0),('Moderator','moderator@example.com',0)]:
    c.execute('INSERT INTO users(name,email,password,language,verified,admin) VALUES(?,?,?,?,1,?)',(name,email,server.password_hash('admin-long-password'),'es',admin))
  _,r=self.call(principal,'/api/login',dict(email=server.PRIMARY_ADMIN_EMAIL,password='admin-long-password'));pc=r['csrf'];self.assertTrue(r['user']['primary_admin'])
  for email,role in [('finance@example.com','finance'),('support@example.com','support'),('moderator@example.com','moderator')]:
   self.assertEqual(self.call(principal,'/api/admin/team',dict(email=email,role=role,title='Test employee',active=True),pc)[0],200)
  _,r=self.call(finance,'/api/login',dict(email='finance@example.com',password='admin-long-password'));fc=r['csrf']
  self.assertIn('finance',r['user']['permissions']);self.assertEqual(self.call(finance,'/api/admin/team')[0],403);self.assertEqual(self.call(finance,'/api/admin/users')[0],403)
  self.assertEqual(self.call(principal,'/api/admin/team',dict(email=server.PRIMARY_ADMIN_EMAIL,role='support',title='wrong',active=False),pc)[0],400)
  with server.db() as c:
   uid=c.execute('SELECT id FROM users WHERE email=?',(server.PRIMARY_ADMIN_EMAIL,)).fetchone()[0]
   import datetime
   timestamp=datetime.datetime(2026,10,2,tzinfo=datetime.timezone.utc).timestamp()
   lid=c.execute("INSERT INTO listings(owner_id,payload,status,updated,activated_at) VALUES(?,?,'approved',?,?)",(uid,json.dumps({'name':'Billing test'}),timestamp,timestamp)).lastrowid
  def entry(kind,amount,date,key,category='other',listing=None):return dict(kind=kind,amount=amount,date=date,request_key=key,category=category,description='Test movement',reference='test',listing_id=listing)
  opening=entry('adjustment','100.00','2026-09-01','opening-key-123456',category='opening_balance');self.assertEqual(self.call(finance,'/api/admin/ledger',opening,fc)[0],201)
  inc=entry('income','50.00','2026-10-03','new-member-123456',category='membership',listing=lid);self.assertEqual(self.call(finance,'/api/admin/ledger',inc,fc)[0],201);self.assertEqual(self.call(finance,'/api/admin/ledger',inc,fc)[0],409)
  self.assertEqual(self.call(finance,'/api/admin/ledger',entry('expense','80.00','2026-10-04','expense-key-123456',category='hosting'),fc)[0],201)
  _,statement=self.call(finance,'/api/admin/statement?month=2026-10');self.assertEqual(statement['opening_cents'],10000);self.assertEqual(statement['net_cashflow_cents'],-3000);self.assertEqual(statement['closing_cents'],7000);self.assertEqual(statement['new_accounts_cents'],5000)
  self.assertEqual(self.call(finance,'/api/admin/ledger',entry('income','30.00','2026-11-02','old-member-123456',category='membership',listing=lid),fc)[0],201)
  self.assertEqual(self.call(finance,'/api/admin/statement?month=2026-11')[1]['existing_accounts_cents'],3000)
  self.assertEqual(self.call(finance,'/api/admin/statement?month=2026-99')[0],400);self.assertEqual(self.call(finance,'/api/admin/ledger',entry('income','1.001','2026-10-01','precision-1234567'),fc)[0],400)
  self.assertEqual(self.call(public,'/api/admin/summary')[0],401)
  _,r=self.call(support,'/api/login',dict(email='support@example.com',password='admin-long-password'));self.assertEqual(self.call(support,'/api/admin/users')[0],200);self.assertEqual(self.call(support,'/api/admin/statement')[0],403)
  _,r=self.call(moderator,'/api/login',dict(email='moderator@example.com',password='admin-long-password'));self.assertEqual(self.call(moderator,'/api/admin/businesses')[0],200);self.assertEqual(self.call(moderator,'/api/admin/statement')[0],403)
  self.assertEqual(self.call(principal,'/api/admin/team',dict(email='finance@example.com',role='finance',title='Test employee',active=False),pc)[0],200);self.assertEqual(self.call(finance,'/api/admin/statement')[0],401)
  with server.db() as c:
   c.execute('DELETE FROM ledger');c.execute('DELETE FROM platform_audit');c.execute('DELETE FROM listings WHERE id=?',(lid,))
 def test_full_flow_and_access(self):
  owner=self.client();outsider=self.client();admin=self.client()
  status,_=self.call(owner,'/api/register',{'name':'Test Owner','email':'test@example.com','password':'a-long-test-password','language':'es'});self.assertEqual(status,201)
  self.assertEqual(self.call(owner,'/api/login',{'email':'test@example.com','password':'a-long-test-password'})[0],403)
  token=re.search('Código de verificación: (.+)',next((server.DATA/'outbox').glob('*.txt')).read_text())[1]
  self.assertEqual(self.call(owner,'/api/verify',{'token':token})[0],200);self.assertEqual(self.call(owner,'/api/verify',{'token':token})[0],400)
  status,r=self.call(owner,'/api/login',{'email':'test@example.com','password':'a-long-test-password'});self.assertEqual(status,200);csrf=r['csrf']
  self.assertEqual(self.call(owner,'/api/admin/listings')[0],403)
  payload=dict(name='Test Mariachi',activity='Mariachi',description='Example only',entity='individual',phone='555',email='private@example.com',street='Private Street',city='Bradenton',state='FL',zip='34205',primaryLanguage='es',additionalLanguages=['en'])
  self.assertEqual(self.call(owner,'/api/listings',payload)[0],403)
  status,r=self.call(owner,'/api/listings',payload,csrf);self.assertEqual(status,201);lid=r['id']
  self.assertEqual(self.call(outsider,'/api/my-listings')[0],401);self.assertEqual(self.call(outsider,'/api/listings')[1]['listings'],[])
  with server.db() as c:c.execute('INSERT INTO users(name,email,password,language,verified,admin) VALUES(?,?,?,?,1,1)',('Admin','admin@example.com',server.password_hash('admin-test-password'),'es'))
  _,r=self.call(admin,'/api/login',dict(email='admin@example.com',password='admin-test-password'));ac=r['csrf']
  self.assertEqual(self.call(admin,f'/api/admin/listings/{lid}/decision',{'status':'rejected','reason':''},ac)[0],400)
  self.assertEqual(self.call(admin,f'/api/admin/listings/{lid}/decision',{'status':'approved'},ac)[0],200)
  public=self.call(outsider,'/api/listings')[1]['listings'];self.assertEqual(len(public),1);self.assertNotIn('street',public[0]);self.assertNotIn('email',public[0]);self.assertEqual(self.call(admin,f'/api/admin/listings/{lid}/decision',{'status':'rejected','reason':'duplicate'},ac)[0],409)
  _,r=self.call(owner,'/api/listings',payload,csrf);second=r['id'];self.assertEqual(self.call(admin,f'/api/admin/listings/{second}/decision',{'status':'rejected','reason':'Faltan datos de actividad'},ac)[0],200)
  own=self.call(owner,'/api/my-listings')[1]['listings'];self.assertEqual(own[0]['reason'],'Faltan datos de actividad')
  self.assertEqual(self.call(outsider,'/.private-data/pilot.sqlite3')[0],404)
  self.assertEqual(self.call(owner,'/api/logout',{},csrf)[0],200);self.assertEqual(self.call(owner,'/api/my-listings')[0],401)
if __name__=='__main__':unittest.main()
