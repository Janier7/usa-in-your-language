"""Private local pilot. Standard library only; not a production deployment server."""
import sys
sys.path.insert(0,str(__import__("pathlib").Path(__file__).resolve().parent))
import admin_panel
import argparse, base64, getpass, hashlib, hmac, json, os, re, secrets, sqlite3, threading, time
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1]
PRIMARY_ADMIN_EMAIL='janiermirabal@gmail.com'
DATA=Path(os.environ.get('USA_DATA_DIR',str(ROOT/'.private-data')))
DATA.mkdir(mode=0o700,parents=True,exist_ok=True)
DB=DATA/'pilot.sqlite3'
LOCK=threading.Lock(); ATTEMPTS={}
def db():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c
with db() as c:
 c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,language TEXT NOT NULL,verified INTEGER NOT NULL DEFAULT 0,admin INTEGER NOT NULL DEFAULT 0);
 CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),csrf TEXT NOT NULL,expires REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS verification(token TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),expires REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS listings(id INTEGER PRIMARY KEY,owner_id INTEGER NOT NULL REFERENCES users(id),payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',reason TEXT NOT NULL DEFAULT '',updated REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,actor_id INTEGER NOT NULL REFERENCES users(id),listing_id INTEGER NOT NULL REFERENCES listings(id),action TEXT NOT NULL,reason TEXT NOT NULL,created REAL NOT NULL);''')
admin_panel.initialize(db)
try:os.chmod(DB,0o600)
except OSError:pass
def digest(text):return hashlib.sha256(text.encode()).hexdigest()
def password_hash(password):
 salt=secrets.token_bytes(16);value=hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1);return base64.b64encode(salt+value).decode()
def password_valid(password,stored):
 try:
  raw=base64.b64decode(stored);return hmac.compare_digest(raw[16:],hashlib.scrypt(password.encode(),salt=raw[:16],n=16384,r=8,p=1))
 except Exception:return False
def public_user(row):
 result={k:row[k] for k in ('id','name','email','language','verified','admin')}
 result['permissions']=sorted(admin_panel.permissions(db,row,PRIMARY_ADMIN_EMAIL));result['primary_admin']=admin_panel.primary(row,PRIMARY_ADMIN_EMAIL);return result
class APIError(Exception):
 def __init__(self,status,message):self.status=status;self.message=message
class Handler(BaseHTTPRequestHandler):
 server_version='USA-Pilot';sys_version=''
 def log_message(self,*args):pass
 def reply(self,status,data,headers=None):
  encoded=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(encoded)))
  for k,v in (headers or {}).items():self.send_header(k,v)
  self.end_headers();self.wfile.write(encoded)
 def session(self,required=True):
  cookies={}
  for part in self.headers.get('Cookie','').split(';'):
   k,_,v=part.strip().partition('=');cookies[k]=v
  with db() as c:row=c.execute('SELECT s.*,u.name,u.email,u.language,u.verified,u.admin,u.id FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?',(digest(cookies.get('usa_session','')),time.time())).fetchone()
  if not row and required:raise APIError(401,'Inicia sesión para continuar.')
  return row
 def check_write(self,session=None):
  if self.headers.get('X-App-Request')!='usa-web':raise APIError(403,'Solicitud no autorizada.')
  origin=self.headers.get('Origin')
  if origin and origin!='http://'+self.headers.get('Host',''):raise APIError(403,'Origen no autorizado.')
  if session and not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),session['csrf']):raise APIError(403,'Sesión no válida. Recarga la página.')
 def body(self):
  try:size=int(self.headers.get('Content-Length','0'))
  except ValueError:raise APIError(400,'Solicitud inválida.')
  if size<1 or size>40000:raise APIError(413,'Solicitud demasiado grande o vacía.')
  if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise APIError(415,'Se requiere JSON.')
  try:value=json.loads(self.rfile.read(size))
  except (ValueError,UnicodeError):raise APIError(400,'JSON inválido.')
  if not isinstance(value,dict):raise APIError(400,'Solicitud inválida.')
  return value
 def rate_limit(self):
  key=self.client_address[0];now=time.time()
  with LOCK:
   attempts=[x for x in ATTEMPTS.get(key,[]) if now-x<60]
   if len(attempts)>=20:raise APIError(429,'Demasiados intentos. Espera un minuto.')
   ATTEMPTS[key]=attempts+[now]
 def do_GET(self):
  try:self.get()
  except APIError as e:self.reply(e.status,{'error':e.message})
 def get(self):
  path=urlparse(self.path).path
  if path.startswith('/api/admin/') and path!='/api/admin/listings':return admin_panel.get(self,path,urlparse(self.path).query,db,APIError,PRIMARY_ADMIN_EMAIL)
  if path=='/api/session':
   row=self.session(False);return self.reply(200,{'user':public_user(row) if row else None,'csrf':row['csrf'] if row else None,'mode':'private-local-pilot'})
  if path=='/api/listings':
   with db() as c:rows=c.execute("SELECT id,payload FROM listings WHERE status='approved' ORDER BY id DESC").fetchall()
   result=[]
   for row in rows:
    payload=json.loads(row['payload']);visible={k:v for k,v in payload.items() if k not in ('legalName','registrationNumber','legalNotes','street','email')};visible['id']=row['id'];result.append(visible)
   return self.reply(200,{'listings':result})
  if path in ('/api/my-listings','/api/admin/listings'):
   user=self.session()
   if path.startswith('/api/admin') and 'listings' not in admin_panel.permissions(db,user,PRIMARY_ADMIN_EMAIL):raise APIError(403,'Solo Administración puede revisar solicitudes.')
   with db() as c:
    rows=c.execute('SELECT l.*,u.name AS owner_name,u.email AS owner_email FROM listings l JOIN users u ON u.id=l.owner_id'+('' if 'listings' in admin_panel.permissions(db,user,PRIMARY_ADMIN_EMAIL) and path.startswith('/api/admin') else ' WHERE l.owner_id=?')+' ORDER BY l.id DESC',() if 'listings' in admin_panel.permissions(db,user,PRIMARY_ADMIN_EMAIL) and path.startswith('/api/admin') else (user['id'],)).fetchall()
   return self.reply(200,{'listings':[{**dict(r),'payload':json.loads(r['payload'])} for r in rows]})
  allowed=path=='/' or path in ('/index.html','/register.html','/app.js','/styles.css','/supabase-client.js') or re.fullmatch(r'/assets/[a-zA-Z0-9_.-]+\.(svg|png|webp|jpg)',path)
  if not allowed:raise APIError(404,'No encontrado.')
  file=ROOT/('index.html' if path=='/' else path.lstrip('/'))
  if not file.is_file():raise APIError(404,'No encontrado.')
  types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml','.png':'image/png','.webp':'image/webp','.jpg':'image/jpeg'}
  content=file.read_bytes();self.send_response(200);self.send_header('Content-Type',types[file.suffix]);self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
 def do_POST(self):
  try:self.post()
  except APIError as e:self.reply(e.status,{'error':e.message})
  except sqlite3.IntegrityError:self.reply(409,{'error':'No se pudo completar la solicitud. Comprueba los datos.'})
 def post(self):
  path=urlparse(self.path).path
  if path in ('/api/admin/ledger','/api/admin/team'):return admin_panel.post(self,path,db,APIError,PRIMARY_ADMIN_EMAIL)
  if path in ('/api/register','/api/login','/api/verify'):self.check_write();self.rate_limit()
  if path=='/api/register':
   data=self.body();name=str(data.get('name','')).strip();email=str(data.get('email','')).strip().lower();password=data.get('password','');language=str(data.get('language','es'))
   if not name or len(name)>120 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254:raise APIError(400,'Nombre o correo inválido.')
   if not isinstance(password,str) or not 12<=len(password)<=128:raise APIError(400,'La contraseña debe tener entre 12 y 128 caracteres.')
   if not re.fullmatch(r'[A-Za-z]{2,8}(?:-[A-Za-z0-9]{2,8})*',language):raise APIError(400,'Idioma inválido.')
   token=secrets.token_urlsafe(32)
   with db() as c:
    uid=c.execute('INSERT INTO users(name,email,password,language) VALUES(?,?,?,?)',(name,email,password_hash(password),language)).lastrowid;c.execute('INSERT INTO verification VALUES(?,?,?)',(digest(token),uid,time.time()+3600));c.execute('UPDATE users SET created_at=? WHERE id=?',(time.time(),uid))
   outbox=DATA/'outbox';outbox.mkdir(mode=0o700,exist_ok=True);file=outbox/f'{secrets.token_hex(10)}.txt';fd=os.open(file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
   with os.fdopen(fd,'w') as f:f.write('PRUEBA LOCAL. No se ha enviado un correo.\nPara: '+email+'\nCódigo de verificación: '+token+'\nCaduca en una hora.\n')
   return self.reply(201,{'message':'Cuenta creada para prueba privada. El operador debe consultar el código en la bandeja local; no se ha enviado correo.'})
  if path=='/api/verify':
   token=str(self.body().get('token',''))
   with db() as c:
    row=c.execute('SELECT * FROM verification WHERE token=? AND expires>?',(digest(token),time.time())).fetchone()
    if not row:raise APIError(400,'Código inválido o vencido.')
    c.execute('UPDATE users SET verified=1 WHERE id=?',(row['user_id'],));c.execute('DELETE FROM verification WHERE user_id=?',(row['user_id'],))
   return self.reply(200,{'message':'Correo marcado como verificado para la prueba local. Ya puedes iniciar sesión.'})
  if path=='/api/login':
   data=self.body()
   with db() as c:row=c.execute('SELECT * FROM users WHERE email=?',(str(data.get('email','')).strip().lower(),)).fetchone()
   supplied=data.get('password','');supplied=supplied if isinstance(supplied,str) and len(supplied)<=128 else ''
   if not row or not password_valid(supplied,row['password']):raise APIError(401,'Correo o contraseña incorrectos.')
   if not row['verified']:raise APIError(403,'Verifica el correo antes de iniciar sesión.')
   token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24)
   with db() as c:c.execute('DELETE FROM sessions WHERE expires<?',(time.time(),));c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(digest(token),row['id'],csrf,time.time()+86400))
   return self.reply(200,{'user':public_user(row),'csrf':csrf},{'Set-Cookie':f'usa_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400'})
  user=self.session();self.check_write(user)
  if path=='/api/logout':
   with db() as c:c.execute('DELETE FROM sessions WHERE token=?',(user['token'],))
   return self.reply(200,{'message':'Sesión cerrada.'},{'Set-Cookie':'usa_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
  if path=='/api/listings':
   data=self.body();required=('name','activity','description','entity','phone','email','street','city','state','zip','primaryLanguage')
   for key in required:
    if not isinstance(data.get(key),str) or not data[key].strip() or len(data[key])>4000:raise APIError(400,'Completa el campo: '+key)
   if data['entity'] not in ('individual','llc','corporation','partnership','lp','llp','nonprofit','cooperative','other'):raise APIError(400,'Estructura inválida.')
   if data['entity']!='individual' and not str(data.get('legalName','')).strip():raise APIError(400,'Indica el nombre legal registrado.')
   if not re.fullmatch(r'\d{5}(-\d{4})?',data['zip']):raise APIError(400,'Código postal inválido.')
   langs=data.get('additionalLanguages',[])
   if not isinstance(langs,list) or len(langs)>100 or any(not isinstance(x,str) or len(x)>30 for x in langs):raise APIError(400,'Idiomas inválidos.')
   if data['primaryLanguage'] in langs:raise APIError(400,'El idioma principal no debe repetirse.')
   clean={k:data[k].strip() for k in required};clean.update({k:str(data.get(k,''))[:4000] for k in ('legalName','registrationNumber','legalNotes')});clean['additionalLanguages']=langs
   with db() as c:lid=c.execute('INSERT INTO listings(owner_id,payload,updated) VALUES(?,?,?)',(user['id'],json.dumps(clean),time.time())).lastrowid
   with db() as c:
    c.execute('UPDATE listings SET created_at=? WHERE id=?',(time.time(),lid))
    c.execute('INSERT INTO audit(actor_id,listing_id,action,reason,created) VALUES(?,?,?,?,?)',(user['id'],lid,'submitted','Solicitud recibida',time.time()))
   return self.reply(201,{'id':lid,'status':'pending','message':'Solicitud enviada a Administración. Aún no está publicada.'})
  match=re.fullmatch(r'/api/admin/listings/(\d+)/decision',path)
  if match:
   if 'listings' not in admin_panel.permissions(db,user,PRIMARY_ADMIN_EMAIL):raise APIError(403,'Solo Administración puede decidir.')
   data=self.body();status=data.get('status');reason=str(data.get('reason','')).strip()
   if status not in ('approved','rejected'):raise APIError(400,'Decisión inválida.')
   if status=='rejected' and not reason:raise APIError(400,'Escribe el motivo del rechazo.')
   if len(reason)>4000:raise APIError(400,'Motivo demasiado largo.')
   with db() as c:
    result=c.execute("UPDATE listings SET status=?,reason=?,updated=? WHERE id=? AND status='pending'",(status,reason,time.time(),int(match[1])))
    if result.rowcount!=1:raise APIError(409,'Solicitud inexistente o ya revisada.')
    if status=='approved':c.execute('UPDATE listings SET activated_at=COALESCE(activated_at,?) WHERE id=?',(time.time(),int(match[1])))
    c.execute('INSERT INTO audit(actor_id,listing_id,action,reason,created) VALUES(?,?,?,?,?)',(user['id'],int(match[1]),status,reason,time.time()))
   return self.reply(200,{'status':status,'message':'Negocio publicado. Felicitaciones.' if status=='approved' else 'Solicitud rechazada con motivo.'})
  raise APIError(404,'No encontrado.')
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8000);parser.add_argument('--create-admin',action='store_true');args=parser.parse_args()
 if args.create_admin:
  email=PRIMARY_ADMIN_EMAIL;print('Administrador principal: '+email);name=input('Nombre: ').strip();password=getpass.getpass('Contraseña (12 caracteres mínimo): ')
  if len(password)<12:raise SystemExit('Contraseña demasiado corta.')
  with db() as c:
   existing=c.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()
   if existing:
    if input('La cuenta existe. Escribe CONFIRMAR para establecer credenciales y administración principal: ')!='CONFIRMAR':raise SystemExit('Sin cambios.')
    c.execute('UPDATE users SET name=?,password=?,verified=1,admin=1 WHERE id=?',(name,password_hash(password),existing['id']))
    c.execute('DELETE FROM sessions WHERE user_id=?',(existing['id'],))
    c.execute('DELETE FROM verification WHERE user_id=?',(existing['id'],))
   else:c.execute('INSERT INTO users(name,email,password,language,verified,admin) VALUES(?,?,?,?,1,1)',(name,email,password_hash(password),'es'))
  print('Administrador local creado.');return
 print(f'Prueba privada en http://127.0.0.1:{args.port}. No apto para exposición pública.');ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
if __name__=='__main__':main()
