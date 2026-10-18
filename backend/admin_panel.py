"""Private administration, cash ledger and scoped staff access."""
import calendar,datetime,json,re,time
from decimal import Decimal,InvalidOperation
from urllib.parse import parse_qs
ROLES={'moderator':{'summary','listings','audit','verification'},'support':{'summary','users'},'finance':{'summary','finance'}}
EXPENSES={'hosting','translations','payment_fees','payroll','advertising','insurance','legal','refund','chargeback','other'}
def initialize(db):
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS staff(user_id INTEGER PRIMARY KEY REFERENCES users(id),role TEXT NOT NULL,title TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
 CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY,entry_date TEXT NOT NULL,kind TEXT NOT NULL,amount_cents INTEGER NOT NULL,category TEXT NOT NULL,description TEXT NOT NULL,reference TEXT NOT NULL,listing_id INTEGER REFERENCES listings(id),cohort TEXT NOT NULL,actor_id INTEGER NOT NULL REFERENCES users(id),created REAL NOT NULL,request_key TEXT UNIQUE NOT NULL);
 CREATE TABLE IF NOT EXISTS platform_audit(id INTEGER PRIMARY KEY,actor_id INTEGER NOT NULL REFERENCES users(id),action TEXT NOT NULL,target TEXT NOT NULL,details TEXT NOT NULL,created REAL NOT NULL);''')
  for table,column,kind in [('users','created_at','REAL'),('listings','created_at','REAL'),('listings','activated_at','REAL')]:
   if column not in [x[1] for x in c.execute('PRAGMA table_info('+table+')')]:c.execute('ALTER TABLE '+table+' ADD COLUMN '+column+' '+kind)
def primary(user,email):return bool(user['admin'] and user['email']==email)
def permissions(db,user,email):
 if primary(user,email):return {'summary','listings','users','finance','team','audit','verification'}
 with db() as c:staff=c.execute('SELECT * FROM staff WHERE user_id=? AND active=1',(user['id'],)).fetchone()
 if staff:return ROLES.get(staff['role'],set())
 return {'summary','listings','users','finance','audit','verification'} if user['admin'] else set()
def month_range(value,Error):
 if not re.fullmatch(r'\d{4}-\d{2}',value):raise Error(400,'Mes inválido. Usa AAAA-MM.')
 try:
  d=datetime.date.fromisoformat(value+'-01');end=d.replace(day=calendar.monthrange(d.year,d.month)[1])
 except ValueError:raise Error(400,'Mes inválido.')
 return d.isoformat(),end.isoformat()
def cash_statement(db,month,Error):
 start,end=month_range(month,Error)
 with db() as c:
  opening=c.execute('SELECT COALESCE(SUM(amount_cents),0) FROM ledger WHERE entry_date<?',(start,)).fetchone()[0]
  rows=[dict(r) for r in c.execute('SELECT * FROM ledger WHERE entry_date BETWEEN ? AND ? ORDER BY entry_date,id',(start,end))]
 income=sum(r['amount_cents'] for r in rows if r['kind']=='income');expenses=-sum(r['amount_cents'] for r in rows if r['kind']=='expense');adjustments=sum(r['amount_cents'] for r in rows if r['kind']=='adjustment');balance=opening
 for r in rows:balance+=r['amount_cents'];r['running_balance_cents']=balance
 return {'month':month,'currency':'USD','opening_cents':opening,'income_cents':income,'expenses_cents':expenses,'net_cashflow_cents':income-expenses,'adjustments_cents':adjustments,'closing_cents':balance,'new_accounts_cents':sum(r['amount_cents'] for r in rows if r['kind']=='income' and r['cohort']=='new'),'existing_accounts_cents':sum(r['amount_cents'] for r in rows if r['kind']=='income' and r['cohort']=='existing'),'unknown_cohort_cents':sum(r['amount_cents'] for r in rows if r['kind']=='income' and r['cohort']=='unknown'),'other_income_cents':sum(r['amount_cents'] for r in rows if r['kind']=='income' and r['cohort']=='other'),'entries':rows,'basis':'cash','notice':'Estado interno de movimientos registrados. No es un extracto bancario ni un estado de resultados contable. No incluye cobros pendientes ni gastos no registrados.'}
def get(h,path,query,db,Error,email):
 user=h.session();rights=permissions(db,user,email);section=path.split('/')[3] if len(path.split('/'))>3 else ''
 required={'summary':'summary','businesses':'listings','users':'users','statement':'finance','billing-businesses':'finance','team':'team','audit':'audit','verification':'verification'}.get(section)
 if not required:raise Error(404,'Apartado no encontrado.')
 if required not in rights:raise Error(403,'No tienes permisos para este apartado.')
 q=parse_qs(query)
 if section=='summary':
  with db() as c:
   counts={'users':c.execute('SELECT count(*) FROM users').fetchone()[0],'verified_users':c.execute('SELECT count(*) FROM users WHERE verified=1').fetchone()[0],'pending':c.execute("SELECT count(*) FROM listings WHERE status='pending'").fetchone()[0],'approved':c.execute("SELECT count(*) FROM listings WHERE status='approved'").fetchone()[0],'rejected':c.execute("SELECT count(*) FROM listings WHERE status='rejected'").fetchone()[0]}
  if 'finance' in rights:
   month=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m');s=cash_statement(db,month,Error);counts['income_cents']=s['income_cents'];counts['month']=month
  return h.reply(200,{'summary':counts,'permissions':sorted(rights)})
 if section=='billing-businesses':
  with db() as c:rows=c.execute("SELECT id,payload FROM listings WHERE status='approved' ORDER BY id DESC").fetchall()
  return h.reply(200,{'listings':[{'id':r['id'],'name':json.loads(r['payload'])['name']} for r in rows]})
 if section=='statement':return h.reply(200,cash_statement(db,q.get('month',[datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m')])[0],Error))
 if section=='businesses':
  with db() as c:rows=c.execute('SELECT l.*,u.name AS owner_name,u.email AS owner_email FROM listings l JOIN users u ON u.id=l.owner_id ORDER BY l.id DESC').fetchall()
  return h.reply(200,{'listings':[{**dict(r),'payload':json.loads(r['payload'])} for r in rows]})
 if section=='users':
  with db() as c:rows=c.execute('SELECT u.id,u.name,u.email,u.language,u.verified,u.created_at,(SELECT count(*) FROM listings WHERE owner_id=u.id) AS businesses FROM users u ORDER BY u.id DESC').fetchall()
  return h.reply(200,{'users':[dict(r) for r in rows]})
 if section=='team':
  with db() as c:rows=c.execute('SELECT u.id,u.name,u.email,u.admin,s.role,s.title,s.active FROM users u LEFT JOIN staff s ON s.user_id=u.id WHERE s.user_id IS NOT NULL OR u.admin=1 ORDER BY u.id').fetchall()
  return h.reply(200,{'team':[dict(r) for r in rows],'roles':list(ROLES)})
 if section=='verification':return h.reply(200,{'documents':[],'message':'La carga y revisión de documentos y vencimientos todavía no están conectadas. No se han verificado licencias ni seguros.'})
 if section=='audit':
  with db() as c:
   decisions=[dict(r) for r in c.execute('SELECT a.*,u.name AS actor_name FROM audit a JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT 500')];events=[dict(r) for r in c.execute('SELECT a.*,u.name AS actor_name FROM platform_audit a JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT 500')]
  lid=q.get('listing_id',[None])[0]
  if lid:decisions=[r for r in decisions if str(r['listing_id'])==lid]
  return h.reply(200,{'decisions':decisions,'events':events,'notice':'Últimos 500 eventos de cada tipo. No es un registro completo de accesos de seguridad.'})
def post(h,path,db,Error,email):
 user=h.session();h.check_write(user);rights=permissions(db,user,email)
 if path=='/api/admin/ledger':
  if 'finance' not in rights:raise Error(403,'No tienes acceso a Finanzas.')
  d=h.body();kind=d.get('kind');category=str(d.get('category',''));description=str(d.get('description','')).strip();reference=str(d.get('reference','')).strip();key=str(d.get('request_key',''))
  try:
   date=datetime.date.fromisoformat(str(d.get('date','')));amount=Decimal(str(d.get('amount','')))
  except (ValueError,InvalidOperation):raise Error(400,'Fecha o importe inválido.')
  if not amount.is_finite() or amount==0 or abs(amount)>Decimal('100000000') or amount!=amount.quantize(Decimal('.01')):raise Error(400,'Importe inválido. Usa hasta dos decimales.')
  if kind not in ('income','expense','adjustment') or (kind!='adjustment' and amount<0):raise Error(400,'Tipo o signo del importe inválido.')
  if not description or len(description)>1000 or len(reference)>200 or not re.fullmatch(r'[A-Za-z0-9-]{16,80}',key):raise Error(400,'Completa concepto y referencia de solicitud.')
  if kind=='expense' and category not in EXPENSES:raise Error(400,'Categoría de gasto inválida.')
  if kind=='income' and category not in ('membership','promotion','other'):raise Error(400,'Categoría de ingreso inválida.')
  if kind=='adjustment' and category!='opening_balance':raise Error(400,'El ajuste solo puede ser un saldo inicial documentado.')
  cents=int(amount*100)*(-1 if kind=='expense' else 1);lid=d.get('listing_id') or None;cohort='other'
  with db() as c:
   if lid:
    row=c.execute('SELECT * FROM listings WHERE id=?',(lid,)).fetchone()
    if not row:raise Error(400,'Negocio inexistente.')
   if kind=='income' and category=='membership':
    if not lid or row['status']!='approved':raise Error(400,'Selecciona un negocio aprobado para registrar membresía.')
    activation=row['activated_at'];activation_month=datetime.datetime.fromtimestamp(activation,datetime.timezone.utc).strftime('%Y-%m') if activation else None
    if activation_month and activation_month>date.strftime('%Y-%m'):raise Error(400,'La fecha del cobro es anterior a la activación del negocio.')
    cohort='unknown' if not activation_month else 'new' if activation_month==date.strftime('%Y-%m') else 'existing'
   if kind=='adjustment' and c.execute('SELECT count(*) FROM ledger').fetchone()[0]:raise Error(409,'El saldo inicial solo se registra antes de cualquier otro movimiento.')
   c.execute('INSERT INTO ledger(entry_date,kind,amount_cents,category,description,reference,listing_id,cohort,actor_id,created,request_key) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(date.isoformat(),kind,cents,category,description,reference,lid,cohort,user['id'],time.time(),key));c.execute('INSERT INTO platform_audit(actor_id,action,target,details,created) VALUES(?,?,?,?,?)',(user['id'],'ledger.create','ledger',json.dumps({'kind':kind,'cents':cents,'date':date.isoformat()}),time.time()))
  return h.reply(201,{'message':'Movimiento manual registrado. No se ha realizado ningún cobro ni pago.'})
 if path=='/api/admin/team':
  if not primary(user,email):raise Error(403,'Solo el administrador principal puede cambiar el equipo.')
  d=h.body();address=str(d.get('email','')).strip().lower();role=d.get('role');title=str(d.get('title','')).strip();active=d.get('active',True)
  if address==email:raise Error(400,'No puedes modificar al administrador principal desde este formulario.')
  if role not in ROLES or not title or len(title)>120 or not isinstance(active,bool):raise Error(400,'Rol, cargo o estado inválido.')
  with db() as c:
   target=c.execute('SELECT * FROM users WHERE email=? AND verified=1',(address,)).fetchone()
   if not target:raise Error(400,'La persona debe tener una cuenta verificada antes de incorporarse al equipo.')
   c.execute('INSERT INTO staff(user_id,role,title,active) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET role=excluded.role,title=excluded.title,active=excluded.active',(target['id'],role,title,int(active)));c.execute('UPDATE users SET admin=0 WHERE id=?',(target['id'],));c.execute('DELETE FROM sessions WHERE user_id=?',(target['id'],));c.execute('INSERT INTO platform_audit(actor_id,action,target,details,created) VALUES(?,?,?,?,?)',(user['id'],'team.update',str(target['id']),json.dumps({'role':role,'active':active,'title':title}),time.time()))
  return h.reply(200,{'message':'Equipo actualizado. La persona deberá iniciar sesión de nuevo.'})
 raise Error(404,'No encontrado.')
