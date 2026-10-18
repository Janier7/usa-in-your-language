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
