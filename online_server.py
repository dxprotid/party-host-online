"""Party Edition 6.8 multi-room online server. Pure Python 3.11+."""
import importlib.util
import json
import os
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlsplit, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent
ROOMS = Path(os.getenv('PARTY_ROOMS_DIR', str(ROOT / 'rooms')))
ROOMS.mkdir(parents=True, exist_ok=True)
PORT = int(os.getenv('PORT', '8766'))
PUBLIC = os.getenv('PARTY_PUBLIC_URL','').strip().rstrip('/')
if PUBLIC and (not PUBLIC.startswith('https://') and not PUBLIC.startswith('http://127.0.0.1:')):
    raise SystemExit('PARTY_PUBLIC_URL должен начинаться с https://')
if not PUBLIC: PUBLIC = f'http://127.0.0.1:{PORT}'
MAX_ROOMS = int(os.getenv('PARTY_MAX_ROOMS','100'))
LOCK = threading.RLock()
ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
MODULE = importlib.util.spec_from_file_location('party_68_engine', ROOT/'server.py')
engine = importlib.util.module_from_spec(MODULE)
MODULE.loader.exec_module(engine)
ROOM_CACHE = {}


def safe_load(path):
    try: return json.loads(path.read_text(encoding='utf8'))
    except (OSError, json.JSONDecodeError): return None

def get_room(code):
    if len(code)!=6 or any(c not in ALPHABET for c in code): return None
    if code in ROOM_CACHE: return ROOM_CACHE[code]
    meta = safe_load(ROOMS/f'{code}.meta.json')
    if not isinstance(meta,dict) or not meta.get('admin'): return None
    state_path = ROOMS/f'{code}.state.json'
    state = safe_load(state_path)
    if not isinstance(state,dict): state=engine.blank()
    room={'code':code,'meta':meta,'state':state,'path':state_path}
    ROOM_CACHE[code]=room
    return room

def create_room():
    with LOCK:
        count = len(list(ROOMS.glob('*.meta.json')))
        if count >= MAX_ROOMS: raise ValueError('Достигнут лимит комнат. Обратитесь к администратору.')
        for _ in range(20):
            code=''.join(secrets.choice(ALPHABET) for _ in range(6))
            if not (ROOMS/f'{code}.meta.json').exists(): break
        else: raise ValueError('Не удалось создать комнату')
        admin=secrets.token_urlsafe(32)
        meta={'admin':admin,'created':time.time()}
        meta_path=ROOMS/f'{code}.meta.json'
        # Exclusive file creation prevents code collisions.
        with meta_path.open('x',encoding='utf8') as fp: json.dump(meta,fp)
        room={'code':code,'meta':meta,'state':engine.blank(),'path':ROOMS/f'{code}.state.json'}
        ROOM_CACHE[code]=room
        return room


def activate(room):
    engine.GAME=room['state']
    engine.STATE_FILE=room['path']
    engine.ADMIN=room['meta']['admin']


def view(room, token, admin):
    activate(room)
    answer=engine.snapshot(token,admin)
    answer['address']=f"{PUBLIC}/r/{room['code']}/join"
    answer['room_code']=room['code']
    return answer

HOME="""<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>🥂 Party Online</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:radial-gradient(circle at 50% 10%,#840fc1,#2e004e 75%);color:white;font:17px system-ui}main{width:min(460px,90vw);background:#510b7d;padding:25px;border:3px solid #d995ff;border-radius:24px;box-shadow:0 8px 0 #1a002b}h1{font-size:29px}button,input{box-sizing:border-box;width:100%;padding:16px;margin:9px 0;border-radius:12px;font-size:18px}button{background:#c7ff00;color:#310040;border:3px solid white;font-weight:900;cursor:pointer}input{background:radial-gradient(circle at 50% 10%,#840fc1,#2e004e 75%);color:white;border:1px solid #79718b}p{opacity:.75}#msg{color:#ffbcbc}</style></head><body><main><div style="text-align:right"><button id="lang" style="width:auto;padding:8px;margin:0;background:#ff4cc7">EN / RU</button></div><h1 id="homeTitle">♛ Я НИКОГДА НЕ…</h1><p id="intro">Создай онлайн-комнату или введи код друзей. Работает на Android, iPhone и ПК.</p><button id="new">🎉 СОЗДАТЬ КОМНАТУ</button><hr><form id="join"><input id="code" placeholder="Код комнаты из 6 символов" maxlength="6" autocomplete="off" required><button id="joinBtn" type="submit">🚀 Присоединиться</button></form><p id="msg"></p></main><script>const applyLang=()=>{let en=localStorage.getItem('party-home-lang')==='en';document.documentElement.lang=en?'en':'ru';document.getElementById('homeTitle').textContent=en?'♛ NEVER HAVE I EVER…':'♛ Я НИКОГДА НЕ…';document.getElementById('intro').textContent=en?'Create a room or enter a friend’s code. Works on Android, iPhone and desktop.':'Создай онлайн-комнату или введи код друзей. Работает на Android, iPhone и ПК.';document.getElementById('new').textContent=en?'🎉 CREATE ROOM':'🎉 СОЗДАТЬ КОМНАТУ';document.getElementById('joinBtn').textContent=en?'🚀 JOIN':'🚀 Присоединиться';document.getElementById('code').placeholder=en?'6-character room code':'Код комнаты из 6 символов'};document.getElementById('lang').onclick=()=>{localStorage.setItem('party-home-lang',localStorage.getItem('party-home-lang')==='en'?'ru':'en');applyLang()};applyLang();document.getElementById('new').onclick=async()=>{try{const r=await fetch('/api/rooms',{method:'POST'});const j=await r.json();if(!r.ok)throw Error(j.error);location.href=j.host_url;}catch(e){document.getElementById('msg').textContent=e.message}};document.getElementById('join').onsubmit=e=>{e.preventDefault();location.href='/r/'+document.getElementById('code').value.trim().toUpperCase()+'/join'}</script></body></html>"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        if '/api/state' not in self.path: super().log_message(format,*args)
    def send_data(self, data, kind='application/json; charset=utf-8',status=200):
        if isinstance(data,(dict,list)): data=json.dumps(data,ensure_ascii=False).encode('utf8')
        elif isinstance(data,str): data=data.encode('utf8')
        self.send_response(status)
        self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self' 'unsafe-inline' data:; connect-src 'self'; img-src 'self' data:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'")
        self.end_headers();self.wfile.write(data)
    def json(self, obj,status=200):self.send_data(obj,status=status)
    def route(self):
        parts=urlsplit(self.path).path.strip('/').split('/')
        if len(parts)<3 or parts[0]!='r':return None,None
        return get_room(parts[1]),'/'.join(parts[2:])
    def auth(self,room):
        admin=secrets.compare_digest(self.headers.get('X-Party-Admin',''),room['meta']['admin'])
        return self.headers.get('X-Party-Token',''),admin
    def do_GET(self):
        path=urlsplit(self.path).path
        if path in ('/','/join'):
            return self.send_data(HOME,'text/html; charset=utf-8')
        if path=='/health':return self.json({'status':'ok'})
        room,resource=self.route()
        if not room: return self.json({'error':'Комната не найдена'},404)
        prefix='/r/'+room['code']
        if resource in ('join','host'):
            if resource=='host' and not secrets.compare_digest(parse_qs(urlsplit(self.path).query).get('key',[''])[0],room['meta']['admin']):
                return self.json({'error':'Нет доступа'},403)
            body=(ROOT/'static/index.html').read_text(encoding='utf8')
            body=body.replace('href="/static/',f'href="{prefix}/static/').replace('src="/static/',f'src="{prefix}/static/')
            body=body.replace('src="/qr.svg"',f'src="{prefix}/qr.svg"')
            body=body.replace('Локальная сеть · ','Онлайн + локальная сеть · ')
            body=body.replace('</head>',f'<script>window.PARTY_BASE={json.dumps(prefix)};</script></head>')
            return self.send_data(body,'text/html; charset=utf-8')
        if resource.startswith('static/sounds/') and resource.rsplit('/',1)[-1] in {'glasses.wav','no.wav','bear.wav','surprise.wav','police.wav','duel.wav','traitor.wav','start.wav','page.wav','click.wav'}:
            return self.send_data((ROOT/resource).read_bytes(),'audio/wav')
        if resource=='static/bear-party.svg':
            return self.send_data((ROOT/resource).read_bytes(),'image/svg+xml')
        if resource in ('static/style.css','static/app.js'):
            b=(ROOT/resource).read_text(encoding='utf8')
            if resource.endswith('.js'):
                b=b.replace("location.pathname==='/host'","location.pathname.endsWith('/host')")
                b=b.replace("'party-v5-token'","'party-v5-token-'+(window.PARTY_BASE||'local')")
                b=b.replace("fetch('/api/", "fetch((window.PARTY_BASE||'')+'/api/")
                b=b.replace("src='/qr.svg?ip='", "src=(window.PARTY_BASE||'')+'/qr.svg?ip='")
            return self.send_data(b,'application/javascript; charset=utf-8' if resource.endswith('.js') else 'text/css; charset=utf-8')
        if resource=='api/state':
            token,admin=self.auth(room)
            with LOCK:return self.json(view(room,token,admin))
        if resource=='qr.svg':
            import qrcode
            qr=qrcode.QRCode(border=3,box_size=7,error_correction=qrcode.constants.ERROR_CORRECT_M)
            qr.add_data(f'{PUBLIC}/r/{room["code"]}/join');qr.make(fit=True)
            m=qr.get_matrix();n=len(m)
            shapes=''.join(f'<rect x="{x}" y="{y}" width="1" height="1"/>' for y,row in enumerate(m) for x,v in enumerate(row) if v)
            svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" shape-rendering="crispEdges"><rect width="{n}" height="{n}" fill="white"/><g fill="#14122c">{shapes}</g></svg>'
            return self.send_data(svg,'image/svg+xml')
        return self.json({'error':'Not found'},404)
    def do_POST(self):
        path=urlsplit(self.path).path
        if path=='/api/rooms':
            try:
                room=create_room()
                return self.json({'code':room['code'],'host_url':f'{PUBLIC}/r/{room["code"]}/host?key={room["meta"]["admin"]}','join_url':f'{PUBLIC}/r/{room["code"]}/join'},201)
            except ValueError as e:return self.json({'error':str(e)},429)
        room,resource=self.route()
        if not room or resource!='api/action':return self.json({'error':'Not found'},404)
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<=10000:raise ValueError('Неверный запрос')
            data=json.loads(self.rfile.read(n))
            if not isinstance(data,dict):raise ValueError('Неверные данные')
            token,admin=self.auth(room)
            with LOCK:
                activate(room)
                answer=engine.action(data,token,admin)
                if 'state' in answer:
                    answer['state']['address']=f'{PUBLIC}/r/{room["code"]}/join'
                    answer['state']['room_code']=room['code']
                else:
                    answer['address']=f'{PUBLIC}/r/{room["code"]}/join'
                    answer['room_code']=room['code']
                return self.json(answer)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
            return self.json({'error':str(e)},400)

def main():
    print('Party Online 6.8:',PUBLIC, 'port',PORT)
    ThreadingHTTPServer(('0.0.0.0',PORT),Handler).serve_forever()
if __name__=='__main__':main()
