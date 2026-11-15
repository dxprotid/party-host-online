"""Party Host quiz state machine 7.3: 1-32 players, 2-8 options, difficulty, earned bonuses."""
import json,random,secrets,threading,os,time
from difflib import SequenceMatcher
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BANK=json.loads((ROOT/'quiz_questions.json').read_text(encoding='utf8'))['topics']
LOCK=threading.RLock()
LIMIT=32

def pool_size(topics,difficulty):
    return sum(sum(1 for q in BANK.get(t,[]) if int(q.get('difficulty',3))==difficulty) for t in topics)

def _available(topics,difficulty):
    return [[t,i] for t in topics for i,q in enumerate(BANK.get(t,[])) if int(q.get('difficulty',3))==difficulty]

def fresh():
    return {'phase':'lobby','players':[],'topics':list(BANK),'total':10,'index':0,'deck':[], 'current':None,
            'round_answers':{},'revision':0,'options_count':4,'difficulty':3,'quiz_mode':'classic', 'round_hints':{},'used':[]}

def load(path):
    try:
        s=json.loads(Path(path).read_text(encoding='utf8'))
        if isinstance(s,dict) and 'players' in s and 'phase' in s:
            for k,v in fresh().items():s.setdefault(k,v)
            for p in s['players']:
                p.setdefault('score',0);p.setdefault('bonuses',{});p.setdefault('mistake_used',False)
            return s
    except (ValueError,OSError):pass
    return fresh()

def save(path,s):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(s,ensure_ascii=False),encoding='utf8');os.replace(tmp,path)

def _find(s,token):
    return next((p for p in s['players'] if secrets.compare_digest(p['token'],token)),None)

def snapshot(s,token='',admin=False):
    current=s['current'];mine=_find(s,token);pid=mine['id'] if mine else None
    c=None
    if current:
        c={k:v for k,v in current.items() if k!='correct'}
        if s['phase']=='reveal':c['correct']=current['correct']
    return {'phase':s['phase'],'players':[{'id':p['id'],'name':p['name'],'score':p['score']} for p in s['players']],
        'me':pid,'admin':admin,'topics':{k:len(v) for k,v in BANK.items()},'selected':s['topics'],
        'total':s['total'],'available':len(_available(s['topics'],s['difficulty'])),
        'available_by_level':{str(diff):{t:sum(1 for q in BANK[t] if int(q.get('difficulty',3))==diff) for t in BANK} for diff in range(1,6)},
        'index':s['index'],'current':c,'options_count':s['options_count'],'difficulty':s['difficulty'],
        'quiz_mode':s['quiz_mode'], 'bonuses':dict(mine.get('bonuses',{})) if mine else {},
        'hint':s.get('round_hints',{}).get(pid,{}),'answers':{id:True for id in s['round_answers']},
        'my_answer':s['round_answers'].get(pid), 'revision':s['revision']}

def _option_list(s,item):
    count=s['options_count'];correct=str(item['a'])
    wrong=list(dict.fromkeys(str(x) for x in item.get('wrong',[]) if str(x)!=correct))
    # More options are sourced from verified answers in the SAME TOPIC, not fabricated by a template.
    topic=s['_draw_topic']
    same=[str(x['a']) for x in BANK.get(topic,[]) if x.get('a')!=correct and int(x.get('difficulty',3))==s['difficulty']]
    other=[str(x['a']) for t in s['topics'] for x in BANK.get(t,[]) if x.get('a')!=correct and int(x.get('difficulty',3))==s['difficulty']]
    random.shuffle(same);random.shuffle(other)
    for opt in same+other:
        if opt not in wrong and opt!=correct:wrong.append(opt)
        if len(wrong)>=count-1:break
    if len(wrong)<count-1:raise ValueError('Недостаточно вариантов ответа')
    chosen=random.sample(wrong,count-1)+[correct];random.shuffle(chosen)
    return chosen,chosen.index(correct)

def _draw(s):
    if s['index']>=s['total']:
        s['phase']='ended';s['current']=None;return
    if not s['deck']:
        s['deck']=_available(s['topics'],s['difficulty']);random.shuffle(s['deck'])
    if not s['deck']:
        s['phase']='ended';s['current']=None;return
    t,i=s['deck'].pop();item=BANK[t][i]
    s['_draw_topic']=t
    order,correct=_option_list(s,item)
    s.pop('_draw_topic',None)
    s['current']={'topic':t,'q':item['q'],'options':order,'correct':correct}
    s['round_answers']={};s['round_hints']={};s['phase']='playing'

def _award(p):
    # Bonuses are deliberately modest; 50/50 is rare and +1 lifeline relatively common.
    r=random.random();kind=('fifty' if r<.025 else 'mistake' if r<.20 else 'audience' if r<.28 else 'minus_one' if r<.53 else None)
    if kind:p['bonuses'][kind]=p['bonuses'].get(kind,0)+1

def act(s,data,token='',admin=False):
    action=str(data.get('action',''));mine=_find(s,token)
    if action=='join':
        if s['phase']!='lobby':raise ValueError('Партия уже началась')
        name=str(data.get('name','')).strip()[:24]
        if not name:raise ValueError('Введите имя')
        if len(s['players'])>=LIMIT:raise ValueError('Комната заполнена (макс. 32)')
        if any(p['name'].casefold()==name.casefold() for p in s['players']):raise ValueError('Имя занято')
        player={'id':secrets.token_hex(5),'token':secrets.token_urlsafe(24),'name':name,'score':0,'bonuses':{},'mistake_used':False}
        s['players'].append(player);s['revision']+=1
        return {'token':player['token']}
    if action=='settings':
        if not admin or s['phase']!='lobby':raise ValueError('Настройки доступны ведущему до начала игры')
        selected=data.get('topics',[])
        if not isinstance(selected,list) or not selected or any(t not in BANK for t in selected):raise ValueError('Выберите хотя бы одну тему')
        difficulty=int(data.get('difficulty',3));choices=int(data.get('options_count',4))
        mode=str(data.get('quiz_mode','classic'))
        if not 1<=difficulty<=5:raise ValueError('Сложность: 1–5')
        if not 2<=choices<=8:raise ValueError('Вариантов ответа: 2–8')
        if mode not in ('classic','custom'):raise ValueError('Неизвестный режим')
        available=len(_available(list(dict.fromkeys(selected)),difficulty))
        if available<10:raise ValueError('На этом уровне пока меньше 10 вопросов. Выберите другие темы или сложность.')
        total=int(data.get('total',10));
        if not 10<=total<=available:raise ValueError(f'Вопросов должно быть 10–{available}')
        s.update(topics=list(dict.fromkeys(selected)),difficulty=difficulty,options_count=choices,total=total,quiz_mode=mode)
        s['revision']+=1
    elif action=='start':
        if not admin or s['phase']!='lobby':raise ValueError('Начать игру может только ведущий')
        if not 1<=len(s['players'])<=LIMIT:raise ValueError('Нужен хотя бы 1 игрок')
        available=len(_available(s['topics'],s['difficulty']))
        if available<10:raise ValueError('Для выбранной сложности недостаточно вопросов (нужно минимум 10)')
        s['total']=min(s['total'],available)
        for p in s['players']:p.update(score=0,bonuses={},mistake_used=False)
        s['deck']=[];s['index']=0;_draw(s);s['revision']+=1
    elif action=='answer':
        if s['phase']!='playing' or not mine:raise ValueError('Сейчас ответить нельзя')
        i=data.get('choice')
        if type(i) is not int or not 0<=i<len(s['current']['options']):raise ValueError('Неверный ответ')
        pid=mine['id'];existing=s['round_answers'].get(pid)
        if existing is not None:
            if not(mine.get('mistake_used') and existing == -1):raise ValueError('Ответ уже принят')
            mine['mistake_used']=False
        if i!=s['current']['correct'] and s['quiz_mode']=='custom' and mine['bonuses'].get('mistake',0)>0 and existing is None:
            mine['bonuses']['mistake']-=1;mine['mistake_used']=True;s['round_answers'][pid]=-1
            s.setdefault('round_hints',{}).setdefault(pid,{})['retry']=True
        else:
            s['round_answers'][pid]=i
            if i==s['current']['correct']:
                mine['score']+=1
                if s['quiz_mode']=='custom':_award(mine)
            s.get('round_hints',{}).get(pid,{}).pop('retry',None)
        if len(s['round_answers'])==len(s['players']) and -1 not in s['round_answers'].values():s['phase']='reveal'
        s['revision']+=1
    elif action=='bonus':
        if s['phase']!='playing' or s['quiz_mode']!='custom' or not mine:raise ValueError('Бонус недоступен')
        kind=str(data.get('kind',''))
        if kind not in ('fifty','minus_one','audience'):raise ValueError('Неверный бонус')
        if mine['id'] in s['round_answers']:raise ValueError('Бонус можно применить до ответа')
        if mine['bonuses'].get(kind,0)<1:raise ValueError('Нет такого бонуса')
        hints=s['round_hints'].setdefault(mine['id'],{})
        if kind in hints:raise ValueError('Этот бонус уже использован на вопросе')
        opts=list(range(len(s['current']['options'])));wrong=[i for i in opts if i!=s['current']['correct']]
        if kind=='fifty': hints[kind]=random.sample(wrong,max(1,(len(wrong)+1)//2))
        elif kind=='minus_one':hints[kind]=[random.choice(wrong)]
        else:
            correct=s['current']['correct'];answered=[pid for pid,i in s['round_answers'].items() if i==correct]
            hints[kind]=correct if answered else max(wrong,key=lambda i:SequenceMatcher(None,str(s['current']['options'][i]).casefold(),str(s['current']['options'][correct]).casefold()).ratio())  # closest-looking alternative, not guaranteed truth
        mine['bonuses'][kind]-=1;s['revision']+=1
    elif action=='reveal':
        if not admin or s['phase']!='playing':raise ValueError('Раскрыть ответ может только ведущий')
        s['phase']='reveal';s['revision']+=1
    elif action=='next':
        if not admin or s['phase']!='reveal':raise ValueError('Сначала раскройте ответ')
        s['index']+=1;_draw(s);s['revision']+=1
    elif action=='reset':
        if not admin:raise ValueError('Сбросить может только ведущий')
        s.clear();s.update(fresh());s['revision']+=1
    else:raise ValueError('Неизвестное действие')
    return {'ok':True}
