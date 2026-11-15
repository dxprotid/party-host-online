"""Я никогда не… Party Edition 6.7. Python stdlib LAN server."""
from __future__ import annotations
import json, os, random, secrets, socket, sys, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'vendor'))
import qrcode

DATA = json.loads((ROOT / 'questions.json').read_text(encoding='utf-8'))
FEMALE_QUESTIONS = json.loads((ROOT / 'questions_female.json').read_text(encoding='utf-8'))
QUESTIONS = DATA['questions']; EVENTS = DATA['events']
CARDS = json.loads((ROOT / 'questions_v67.json').read_text(encoding='utf-8'))
EN_CARDS = json.loads((ROOT / 'questions_en.json').read_text(encoding='utf-8'))
EN_EVENTS = json.loads((ROOT / 'events_en.json').read_text(encoding='utf-8'))
TOPICS = list(CARDS)
CARD_IDS = {topic: {f'{topic}:{i}': card for i, card in enumerate(cards)} for topic, cards in CARDS.items()}
BANK_VERSION = 730
EXTREME = 'Особо жёсткий 18+'
PORT = int(os.environ.get('PARTY_PORT', '8765'))
ADMIN = os.environ.get('PARTY_ADMIN_KEY') or secrets.token_urlsafe(24)
LOCK = threading.RLock()

def blank():
    return dict(revision=0, phase='lobby', players=[], settings={'mode':'quick','total':20,'extreme':False,'topics':[t for t in TOPICS if t != EXTREME], 'events':True,'rate':0.16,'party_level':3,'language':'ru'}, current=None, index=0, deck=[], bank_version=BANK_VERSION, events_deck=[], last=None, reader_override=None, last_event=False, effect=None, custom_questions={}, challenge_votes={}, challenge_deadline=None, start_time=None)
STATE_FILE = Path(os.environ.get('PARTY_STATE_FILE', str(ROOT / '.party_state.json')))

def restore():
    try:
        saved = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        if not isinstance(saved, dict) or not isinstance(saved.get('players'), list) or saved.get('phase') not in ('lobby','playing','ended'):
            raise ValueError('Некорректное состояние')
        # Compatibility with existing 5.x / 6.0 state structure.
        base = blank()
        base.update(saved)
        base.setdefault('custom_questions',{});base.setdefault('challenge_votes',{});base.setdefault('challenge_deadline',None);base.setdefault('start_time',None)
        # Old cached decks contained dictionaries instead of compact card IDs.
        # Discard the cached draw order, not the room or currently displayed card.
        if base.get('bank_version') != BANK_VERSION or any(not isinstance(x, str) for x in base.get('deck', [])):
            base['deck'] = []
        base['bank_version'] = BANK_VERSION
        if not isinstance(base.get('settings'), dict): raise ValueError('Неверные настройки')
        return base
    except (OSError, ValueError, TypeError, KeyError):
        return blank()

GAME = restore()

def save_state():
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp = STATE_FILE.with_suffix(STATE_FILE.suffix + '.tmp')
        with temp.open('w', encoding='utf-8') as f:
            json.dump(GAME, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, STATE_FILE)
    except OSError as err:
        print('Не удалось сохранить партию:', err, file=sys.stderr)


def touch():
    GAME['revision'] += 1
    save_state()

def require(ok, message='Нет доступа'):
    if not ok: raise ValueError(message)

def draw():
    g=GAME
    if g['settings']['mode'] in ('quick','challenge') and g['index']>=g['settings']['total']:
        g['phase']='ended';g['current']=None;touch();return
    players=g['players'];reader=g['reader_override'] if g['reader_override'] is not None else g['index']%len(players)
    g['reader_override']=None
    if g['settings']['mode']=='custom':
        pool=[q for vals in g.get('custom_questions',{}).values() for q in vals]
        if not pool:
            g['phase']='ended';g['current']=None;touch();return
        if not g['deck']:
            g['deck']=[f'custom:{i}' for i in range(len(pool))];random.shuffle(g['deck'])
            if len(g['deck'])>1 and g['deck'][-1]==g.get('last_custom_id'):
                g['deck'][0],g['deck'][-1]=g['deck'][-1],g['deck'][0]
        drawn=g['deck'].pop();g['last_custom_id']=drawn;index=int(drawn.split(':')[1]);body=pool[index]
        g['current']={'event':False,'topic':'Своя игра','text':'Я никогда не '+body,'female_text':'Я никогда не '+body,
                      'title':'Я НИКОГДА НЕ…','reader':players[reader]['id'],'revealed':True}
        g['challenge_votes']={};g['challenge_deadline']=None;g['last_event']=False;touch();return
    if g['settings']['mode']=='challenge':
        g['challenge_votes']={};g['challenge_deadline']=time.time()+5
    else:g['challenge_deadline']=None
    # Party level adds surprise, without changing how much anyone is expected to drink.
    level=g['settings'].get('party_level',3)
    effective_rate=min(0.65, g['settings']['rate'] * (0.60 + 0.20*level))
    event=g['settings']['mode']!='challenge' and g['settings']['events'] and not g['last_event'] and random.random()<effective_rate
    if event:
        # A rare all-player interruption; probability increases with party level.
        bear_chance={1:0.06,2:0.10,3:0.16,4:0.24,5:0.34}[level]
        if random.random()<bear_chance:
            g['current']={'event':True,'bear':True,'topic':'🐻 SUDDEN EVENT' if g['settings'].get('language')=='en' else '🐻 ВНЕЗАПНЫЙ ИВЕНТ',
                'text':'BEAR ATTACK! Quickly shout “I am safe!” or make a roof with your hands. The last person does a silly bear impression. Optional small sip, never required.' if g['settings'].get('language')=='en' else 'МЕДВЕДЬ ПРИШЁЛ! Все быстро говорят «Я в домике!» или показывают крышу над головой. Последний выполняет смешной штраф (например, изображает медведя) либо, если сам захочет, делает один небольшой глоток. Никаких залпов и обязательных штрафов.',
                'title':'🐻 BEAR ATTACK!' if g['settings'].get('language')=='en' else '🐻 МЕДВЕДЬ ПРИШЁЛ!','event_kind':'bear','reader':players[reader]['id'],'revealed':True}
            g['last_event']=True;g['effect']=None;touch();return
        if not g['events_deck']: g['events_deck']=random.sample(EVENTS,len(EVENTS))
        title,body=g['events_deck'].pop()
        if g['settings'].get('language')=='en':
            old = next((i for i, ev in enumerate(EVENTS) if ev[0]==title), None)
            if old is not None: title,body=EN_EVENTS[old]
        g['current']={'event':True,'topic':'🎁 Mystery Event' if g['settings'].get('language')=='en' else '🎁 Кот в мешке','text':body,'title':title,'event_kind':'surprise','reader':players[reader]['id'],'revealed':True}
    else:
        if not g['deck']:
            allowed=[EXTREME] if g['settings']['extreme'] else g['settings']['topics']
            # Only independently authored plots are used; synthetic suffix variations are excluded.
            # Shuffle a complete unique deck: no repeats until every selected plot is exhausted.
            independent=[]
            seen_text=set()
            bank = EN_CARDS if g['settings'].get('language')=='en' else CARDS
            if bank is EN_CARDS:
                allowed = [t for t in allowed if t in EN_CARDS] or list(EN_CARDS)
            for topic in allowed:
                for idx, card in enumerate(bank[topic]):
                    if card.get('variant') != 0:
                        continue
                    normalized=(' '.join(card['m'].split()).casefold(), ' '.join(card['f'].split()).casefold())
                    if normalized in seen_text:
                        continue
                    seen_text.add(normalized)
                    independent.append(f'{topic}:{idx}')
            random.shuffle(independent)
            g['deck']=independent[::-1]
            if g['deck'] and g['last']==g['deck'][-1] and len(g['deck'])>1:
                g['deck'][-1],g['deck'][-2]=g['deck'][-2],g['deck'][-1]
        key=g['deck'].pop()
        topic,idx=key.rsplit(':',1)
        card=(EN_CARDS if g['settings'].get('language')=='en' else CARDS)[topic][int(idx)]
        g['last']=key
        prefix='I have never ' if g['settings'].get('language')=='en' else 'Я никогда не '
        g['current']={'event':False,'topic':topic,'text':prefix+card['m'],
                      'female_text':prefix+card['f'],
                      'title':'NEVER HAVE I EVER…' if g['settings'].get('language')=='en' else 'Я НИКОГДА НЕ…','reader':players[reader]['id'],'revealed':True}
    g['last_event']=event;g['effect']=None;touch()

def snapshot(token, admin):
    g0=GAME
    if g0['phase']=='playing' and g0['settings'].get('mode')=='challenge' and g0.get('challenge_deadline') and time.time()>=g0['challenge_deadline']:
        changed=False
        for p in g0['players']:
            if p['id'] not in g0.setdefault('challenge_votes',{}):
                g0['challenge_votes'][p['id']]='yes';changed=True
        if changed:touch()
    g=GAME;current=g['current']; mine=next((p for p in g['players'] if p['token']==token),None)
    visible=None
    if current:
        visible={k:v for k,v in current.items() if k not in ('reader', 'female_text')}
        # A single shared card, agreed for everyone; gender is chosen by its reader.
        reader_player=next((p for p in g['players'] if p['id']==current['reader']),None)
        if reader_player and reader_player.get('gender')=='female' and current.get('female_text'):
            visible['text']=current['female_text']
    return {'revision':g['revision'],'phase':g['phase'],'players':[{'id':p['id'],'name':p['name'],'gender':p.get('gender','male')} for p in g['players']], 'me':mine['id'] if mine else None, 'is_admin':admin,'current':visible,'reader':current['reader'] if current else None,'index':g['index'],'settings':g['settings'],'effect':g['effect'], 'topics':{k:sum(card.get('variant')==0 for card in v) for k,v in CARDS.items()} if admin else None,'address':f'http://{LAN_IP}:{PORT}/join','join_count':len(g['players']), 'custom_count':{p['id']:len(g.get('custom_questions',{}).get(p['id'],[])) for p in g['players']}, 'challenge_deadline':g.get('challenge_deadline'), 'challenge_votes':{pid:True for pid in g.get('challenge_votes',{})}, 'my_challenge_vote':g.get('challenge_votes',{}).get(mine['id'] if mine else ''), 'start_time':g.get('start_time')}

def action(data, token, admin):
    with LOCK:
        g=GAME;act=data.get('action');mine=next((p for p in g['players'] if p['token']==token),None)
        if act=='join':
            require(g['phase']=='lobby','Партия уже идёт. Попросите ведущего запустить новую комнату.')
            if mine:return snapshot(token,admin)
            require(len(g['players'])<16,'Комната заполнена (максимум 16 игроков).')
            name=str(data.get('name','')).strip()[:30]
            gender=data.get('gender','male')
            require(gender in ('male','female'),'Укажите грамматический род: мужской или женский.')
            require(1<=len(name)<=30,'Введите имя (до 30 символов).')
            require(name.casefold() not in (p['name'].casefold() for p in g['players']),'Это имя уже занято.')
            newtoken=secrets.token_urlsafe(22)
            previous=len(g['players'])
            g['players'].append({'id':secrets.token_hex(6),'name':name,'gender':gender,'token':newtoken})
            if g['settings']['total']==max(2,previous)*10: g['settings']['total']=max(2,len(g['players']))*10
            touch()
            return {'token':newtoken, 'state':snapshot(newtoken,False)}
        if act=='rename':
            require(mine is not None and g['phase']=='lobby','Переименоваться можно до начала игры.')
            name=str(data.get('name','')).strip()[:30]
            require(name and name.casefold() not in (p['name'].casefold() for p in g['players'] if p is not mine),'Имя пустое или занято.')
            mine['name']=name;touch();return snapshot(token,admin)
        if act=='leave':
            require(mine is not None and g['phase']=='lobby','Покинуть комнату можно до начала игры.')
            previous=len(g['players'])
            g['players']=[p for p in g['players'] if p is not mine]
            if g['settings']['total']==max(2,previous)*10: g['settings']['total']=max(2,len(g['players']))*10
            touch();return snapshot(None,False)
        if act=='submit_custom':
            require(mine is not None and g['phase']=='lobby','Вопросы можно вносить только в лобби')
            values=data.get('questions')
            require(isinstance(values,list) and len(values)==5,'Нужно написать ровно 5 вопросов')
            cleaned=[]
            for val in values:
                v=str(val).strip()
                require(4<=len(v)<=200,'Каждый вопрос должен содержать 4–200 символов')
                v=v.removeprefix('Я никогда не ').removeprefix('я никогда не ').strip().rstrip(' .!?')
                cleaned.append(v)
            g.setdefault('custom_questions',{})[mine['id']]=cleaned;touch();return snapshot(token,admin)
        if act=='vote':
            require(g['phase']=='playing' and g['settings'].get('mode')=='challenge','Сейчас не идёт испытание')
            require(mine is not None,'Требуется игрок')
            require(time.time()<g.get('challenge_deadline',0),'Время вышло: засчитано «Было»')
            require(mine['id'] not in g.setdefault('challenge_votes',{}),'Вы уже ответили')
            answer=data.get('kind');require(answer in ('yes','no'),'Неверный ответ')
            g['challenge_votes'][mine['id']]=answer;touch();return snapshot(token,admin)
        if act=='settings':
            require(admin and g['phase']=='lobby')
            opt=data.get('settings') or {};require(isinstance(opt,dict),'Неверные настройки')
            mode=opt.get('mode','quick');require(mode in ('quick','endless','challenge','custom'),'Неверный режим')
            total=opt.get('total');require(type(total)==int and 1<=total<=10000,'Количество вопросов: 1–10000')
            extreme=opt.get('extreme') is True
            topics=opt.get('topics');require(isinstance(topics,list),'Выберите темы')
            topics=list(dict.fromkeys(t for t in topics if t in TOPICS and t!=EXTREME))
            require(mode=='custom' or extreme or bool(topics),'Выберите хотя бы одну тему')
            rate=opt.get('rate',0.16);require(type(rate) in (int,float) and 0<=rate<=0.5,'Частота событий от 0 до 50%')
            level=opt.get('party_level',3);require(type(level)==int and 1<=level<=5,'Уровень вечеринки: 1–5')
            language=opt.get('language','ru');require(language in ('ru','en'),'Unsupported language')
            g['settings']={'mode':mode,'total':total,'extreme':extreme,'topics':topics,'events':opt.get('events') is True,'rate':rate,'party_level':level,'language':language}
            touch();return snapshot(token,admin)
        if act=='kick':
            require(admin and g['phase']=='lobby')
            previous=len(g['players']);g['players']=[p for p in g['players'] if p['id']!=data.get('id')]
            if g['settings']['total']==max(2,previous)*10: g['settings']['total']=max(2,len(g['players']))*10
            touch();return snapshot(token,admin)
        if act=='start':
            require(admin and g['phase']=='lobby');require(1<=len(g['players'])<=16,'Для старта нужно 1–16 игроков.')
            if g['settings'].get('mode')=='custom':
                require(all(len(g.get('custom_questions',{}).get(p['id'],[]))==5 for p in g['players']), 'Каждый игрок должен добавить по 5 вопросов')
            g['phase']='playing';g['start_time']=time.time();g['index']=0;g['deck']=[];g['bank_version']=BANK_VERSION;g['events_deck']=[];g['last']=None;g['last_event']=False;g['reader_override']=None;draw();return snapshot(token,admin)
        if act=='next':
            require(g['phase']=='playing' and g['current'] is not None,'Игра не идёт')
            require(admin or (mine is not None and mine['id']==g['current']['reader']),'Переключить может только читающий.')
            if g['settings'].get('mode')=='challenge':
                require(time.time()>=g.get('challenge_deadline',0) or len(g.get('challenge_votes',{}))==len(g['players']), 'Дождитесь ответов всех игроков или окончания 5 секунд')
                for p in g['players']:g.setdefault('challenge_votes',{}).setdefault(p['id'],'yes')
            card=g['current']
            if card['event']:
                if ('Смена власти' in card['title'] or 'Power Shift' in card['title']):g['reader_override']=(g['index']+2)%len(g['players'])
                if ('Реверс' in card['title'] or 'Reverse' in card['title']):g['reader_override']=(g['index']+len(g['players'])-1)%len(g['players'])
            g['index']+=1;draw()
            # effect attached to NEXT state, which all clients can animate once
            g['effect']={'kind':data.get('kind') if data.get('kind') in ('yes','no') else 'skip','revision':g['revision']}
            return snapshot(token,admin)
        if act=='finish':
            require(admin or (mine is not None and g['phase']=='playing'),'Только ведущий или игрок могут завершить партию.')
            g['phase']='ended';g['current']=None;touch();return snapshot(token,admin)
        if act=='reset':
            require(admin);g.clear();g.update(blank());touch();return snapshot(token,admin)
        raise ValueError('Неизвестное действие')

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        if not self.path.startswith('/api/state'):super().log_message(format,*args)
    def reply_headers(self, code, content_type='application/json; charset=utf-8'):
        self.send_response(code);self.send_header('Content-Type',content_type);self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
    def writejson(self, obj, code=200):
        b=json.dumps(obj,ensure_ascii=False).encode('utf8');self.reply_headers(code);self.wfile.write(b)
    def auth(self):
        return self.headers.get('X-Party-Token',''),secrets.compare_digest(self.headers.get('X-Party-Admin',''),ADMIN)
    def do_GET(self):
        url=urlsplit(self.path);path=url.path
        if path in ('/','/join','/host'):
            # The host UI is protected by a private URL launched only on the server computer.
            if path=='/host' and parse_qs(url.query).get('key',[''])[0]!=ADMIN:
                self.reply_headers(403,'text/plain; charset=utf-8');self.wfile.write(b'Forbidden');return
            content=(ROOT/'static/index.html').read_bytes()
            self.reply_headers(200,'text/html; charset=utf-8');self.wfile.write(content);return
        if path.startswith('/static/sounds/') and path.rsplit('/',1)[-1] in {'glasses.wav','no.wav','bear.wav','surprise.wav','police.wav','duel.wav','traitor.wav','start.wav','page.wav','click.wav'}:
            self.reply_headers(200,'audio/wav');self.wfile.write((ROOT/path.lstrip('/')).read_bytes());return
        if path=='/static/bear-party.svg':
            self.reply_headers(200,'image/svg+xml');self.wfile.write((ROOT/'static/bear-party.svg').read_bytes());return
        if path=='/static/app.js' or path=='/static/style.css':
            typ='application/javascript; charset=utf-8' if path.endswith('.js') else 'text/css; charset=utf-8'
            self.reply_headers(200,typ);self.wfile.write((ROOT/path.lstrip('/')).read_bytes());return
        if path=='/api/state':
            token,admin=self.auth()
            with LOCK:self.writejson(snapshot(token,admin))
            return
        if path=='/qr.svg':
            link=f'http://{LAN_IP}:{PORT}/join';qr=qrcode.QRCode(border=3,box_size=7,error_correction=qrcode.constants.ERROR_CORRECT_M);qr.add_data(link);qr.make(fit=True)
            m=qr.get_matrix();size=len(m);blocks=''.join(f'<rect x="{x}" y="{y}" width="1" height="1"/>' for y,row in enumerate(m) for x,v in enumerate(row) if v)
            svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" shape-rendering="crispEdges"><rect width="{size}" height="{size}" fill="white"/><g fill="#14122c">{blocks}</g></svg>'
            self.reply_headers(200,'image/svg+xml');self.wfile.write(svg.encode());return
        self.reply_headers(404);self.wfile.write(b'Not found')
    def do_POST(self):
        if urlsplit(self.path).path!='/api/action':self.writejson({'error':'Not found'},404);return
        try:
            n=int(self.headers.get('Content-Length','0'))
            require(0<n<=10000,'Неправильный запрос')
            data=json.loads(self.rfile.read(n))
            require(isinstance(data,dict),'Неверные данные')
            token,admin=self.auth()
            self.writejson(action(data,token,admin))
        except (ValueError,TypeError,KeyError,json.JSONDecodeError) as e:self.writejson({'error':str(e)},400)

def ip_address():
    try:
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        s.connect(('192.0.2.1',80));ip=s.getsockname()[0];s.close();return ip
    except OSError:return '127.0.0.1'

LAN_IP=os.environ.get('PARTY_HOST_IP') or ip_address()

def main():
    print('\n'+'='*58)
    print('Я НИКОГДА НЕ... PARTY EDITION 6.6')
    print(f'Панель ведущего: http://127.0.0.1:{PORT}/host?key={ADMIN}')
    print(f'Телефоны:        http://{LAN_IP}:{PORT}/join')
    print('Телефоны и компьютер должны быть в одной Wi-Fi сети.')
    print('Не закрывайте окно сервера до конца игры. Ctrl+C для выхода.')
    print('='*58+'\n')
    srv=ThreadingHTTPServer(('0.0.0.0',PORT),Handler)
    if os.environ.get('PARTY_NO_BROWSER')!='1':webbrowser.open(f'http://127.0.0.1:{PORT}/host?key={ADMIN}')
    try:srv.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:print('\nСервер остановлен.')
    finally:srv.server_close()
if __name__=='__main__':main()
