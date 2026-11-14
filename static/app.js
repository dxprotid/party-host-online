(()=>{'use strict';
const $=id=>document.getElementById(id), q=new URLSearchParams(location.search), admin=location.pathname==='/host'&&!!q.get('key');
let adminKey=admin?q.get('key'):'',hostTab='play',token=localStorage.getItem('party-v5-token')||'',state=null,run=false,edit=false,settingsHash='',soundCtx=null,lastEffect=-1,lastBear=-1,lastEventKey="",audioUnlocked=false,requesting=false;
const names={};
if(admin){$('hostTabs').classList.remove('hidden');$('adminSettingsMount').appendChild($('hostOnly'));}
function setHostTab(tab){hostTab=tab; $('tabPlay').classList.toggle('active',tab==='play');$('tabManage').classList.toggle('active',tab==='manage'); if(state)render(state)}
$('tabPlay').onclick=()=>setHostTab('play');$('tabManage').onclick=()=>setHostTab('manage');
$('hostJoinForm').onsubmit=e=>{e.preventDefault();act('join',{name:$('hostPlayerName').value,gender:$('hostPlayerGender').value})};
$('hostLeave').onclick=async()=>{await act('leave');token='';localStorage.removeItem('party-v5-token')};
$('adminNext').onclick=()=>act('next',{kind:'skip'});$('adminFinish').onclick=()=>{if(confirm('Завершить игру для всех?'))act('finish')};$('adminReset').onclick=()=>{if(confirm('Начать новую комнату? Все участники войдут заново.'))act('reset')};
function view(id){['joinPanel','lobbyPanel','gamePanel','endPanel','adminPanel'].forEach(k=>$(k).classList.toggle('hidden',k!==id))}
function alertMessage(t){$('alert').textContent=t;$('alert').classList.toggle('hidden',!t)}
async function api(action,data={}){let res=await fetch('/api/action',{method:'POST',headers:{'Content-Type':'application/json','X-Party-Token':token,'X-Party-Admin':adminKey},body:JSON.stringify({action,...data})});let body=await res.json();if(!res.ok)throw Error(body.error||'Ошибка запроса');if(body.token){token=body.token;localStorage.setItem('party-v5-token',token)}if(body.state)body=body.state;render(body);return body}
async function update(){if(requesting)return;requesting=true;try{let res=await fetch('/api/state',{headers:{'X-Party-Token':token,'X-Party-Admin':adminKey},cache:'no-store'});if(!res.ok)throw Error('Сервер недоступен');let data=await res.json();render(data);$('connection').textContent=t('● На связи');$('connection').style.color='#baffdc';if($('alert').textContent==='Соединение потеряно — переподключаемся…')alertMessage('')}catch(e){$('connection').textContent=t('● Нет связи');$('connection').style.color='#ffb5b8';alertMessage('Соединение потеряно — переподключаемся…')}finally{requesting=false}}
async function act(a,d={}){try{await api(a,d);alertMessage('')}catch(e){alertMessage(e.message)}}
function audioEngine(){try{let C=window.AudioContext||window.webkitAudioContext;if(!C)return null;soundCtx=soundCtx||new C();if(soundCtx.state==='suspended')soundCtx.resume().catch(()=>{});return soundCtx}catch{return null}}
// Synthesised offline effects: no network calls or external media dependencies.
function tone(ctx,freq,at,len,vol=.06,type='sine',endFreq=null){let o=ctx.createOscillator(),g=ctx.createGain();o.type=type;o.frequency.setValueAtTime(freq,at);if(endFreq)o.frequency.exponentialRampToValueAtTime(endFreq,at+len);g.gain.setValueAtTime(.0001,at);g.gain.exponentialRampToValueAtTime(vol,at+.012);g.gain.exponentialRampToValueAtTime(.0001,at+len);o.connect(g).connect(ctx.destination);o.start(at);o.stop(at+len+.01)}
function noise(ctx,at,len,vol=.08,low=550){let n=Math.max(1,Math.floor(ctx.sampleRate*len)),buf=ctx.createBuffer(1,n,ctx.sampleRate),a=buf.getChannelData(0);for(let i=0;i<n;i++)a[i]=(Math.random()*2-1);let src=ctx.createBufferSource(),f=ctx.createBiquadFilter(),g=ctx.createGain();src.buffer=buf;f.type='lowpass';f.frequency.value=low;g.gain.setValueAtTime(.0001,at);g.gain.exponentialRampToValueAtTime(vol,at+.03);g.gain.exponentialRampToValueAtTime(.0001,at+len);src.connect(f).connect(g).connect(ctx.destination);src.start(at);src.stop(at+len)}
function partySound(kind){let ctx=audioEngine();if(!ctx)return;let t=ctx.currentTime+.02;try{
 if(kind==='yes'){// two glass rims touching with a tiny bright reverberant tail
  tone(ctx,1175,t,.23,.09,'sine',1010);tone(ctx,1568,t+.065,.30,.065,'sine',1360);tone(ctx,2350,t+.09,.17,.023,'sine');
 }else if(kind==='bear'){// cartoon roar: two guttural sweeps with airy attack
  noise(ctx,t,.72,.11,440);tone(ctx,155,t,.54,.11,'sawtooth',77);tone(ctx,105,t+.34,.56,.13,'sawtooth',57);noise(ctx,t+.5,.38,.07,260);
 }else if(kind==='surprise'){tone(ctx,600,t,.19,.08,'triangle',900);tone(ctx,900,t+.14,.32,.09,'triangle',450);noise(ctx,t+.22,.22,.03,1400)
 }else if(kind==='no'){tone(ctx,780,t,.13,.035,'sine',960);tone(ctx,1050,t+.12,.23,.035,'sine',1320)}
 }catch{}}
const AUDIO_FILES={yes:'glasses',no:'no',bear:'bear',surprise:'surprise',police:'police',duel:'duel',traitor:'traitor',start:'start',page:'page'};
let soundEnabled=localStorage.getItem('party-sounds-enabled')!=='false', fxVolume=Number(localStorage.getItem('party-fx-volume')||'60')/100;
let language=localStorage.getItem('party-ui-lang')||'ru';
const audioCache={};
function eventSound(card){if(card?.bear)return'bear';const t=card?.title||'';
 if(/Полиция|Police/.test(t))return'police';if(/Дуэль|Duel/.test(t))return'duel';if(/Предатель|Traitor/.test(t))return'traitor';return'surprise'}
function playSound(kind){if(!soundEnabled||fxVolume<=0)return;
 const file=AUDIO_FILES[kind]||'surprise'; const url=(window.PARTY_BASE||'')+'/static/sounds/'+file+'.wav';
 try{if(!audioCache[file]){audioCache[file]=new Audio(url);audioCache[file].preload='auto'}
 const instance=audioCache[file].cloneNode();instance.volume=Math.min(1,Math.max(0,fxVolume));instance.play().catch(()=>{});
 }catch(e){partySound(kind)}
}
function cardFx(kind){if(!kind||kind==='skip')return;let el=$('effects');el.replaceChildren();el.className='';if(kind==='bear'){
  el.innerHTML='<div class="bearScene"><img class="bearArt" src="'+(window.PARTY_BASE||'')+'/static/bear-party.svg'+'" alt="Весёлый мультяшный медведь"><div class="bearSpeech">'+(state?.settings?.language==='en'?'BEAR ATTACK!':'МЕДВЕДЬ ПРИШЁЛ!')+'</div></div>';
 }else{let label=document.createElement('div');label.className='effectSymbol';label.textContent=({yes:'🥂',no:'✨',surprise:'🎁',police:'🚨',duel:'⚔️',traitor:'🐀',start:'🎉'})[kind]||'✨';el.append(label)}
 void el.offsetWidth;el.className='play '+(kind==='bear'?'bearEffect':'');playSound(kind)}
// Mobile browsers unlock sound only after an explicit tap.
for(let ev of ['touchstart','pointerdown'])document.addEventListener(ev,()=>{if(!audioUnlocked){audioUnlocked=true;audioEngine()}},{once:true,passive:true});
function topicRender(topics){let root=$('topics');root.replaceChildren();Object.entries(topics||{}).filter(([t])=>t!=='Особо жёсткий 18+').forEach(([name,n])=>{let label=document.createElement('label');label.className='topicItem';let ch=document.createElement('input');ch.type='checkbox';ch.value=name;ch.checked=state.settings.topics.includes(name);ch.addEventListener('change',saveSettings);let s=document.createElement('span');s.textContent=name+' ';let small=document.createElement('small');small.textContent='('+n+')';s.append(small);label.append(ch,s);root.append(label)});translateUI()}
function showPartyLevel(){const labels=['','Тихо и мирно','Разогрев','Жарко','Без тормозов','Полный хаос'];$('partyLevelText').textContent=$('partyLevel').value+'/5 — '+labels[Number($('partyLevel').value)]}
function applySettings(s){$('quick').classList.toggle('active',s.mode==='quick');$('endless').classList.toggle('active',s.mode==='endless');$('totalBox').classList.toggle('hidden',s.mode==='endless');$('total').value=s.total;$('extreme').checked=s.extreme;$('topicBlock').classList.toggle('hidden',s.extreme);$('events').checked=s.events;$('rate').value=Math.round(s.rate*100);$('rateText').textContent=Math.round(s.rate*100)+'%';$('rateBox').classList.toggle('hidden',!s.events);$('partyLevel').value=s.party_level||3;$('roomLanguage').value=s.language||'ru';showPartyLevel()}
function getSettings(){return {mode:$('endless').classList.contains('active')?'endless':'quick',total:Math.max(1,Math.min(10000,Number($('total').value)||20)),extreme:$('extreme').checked,topics:[...$('topics').querySelectorAll('input:checked')].map(x=>x.value),events:$('events').checked,rate:Number($('rate').value)/100,party_level:Number($('partyLevel').value),language:$('roomLanguage').value}}
async function saveSettings(){if(!admin||!state||state.phase!=='lobby')return;let s=getSettings();if(!s.extreme&&!s.topics.length){alertMessage('Выбери хотя бы одну тему или включи жёсткий режим.');return}await act('settings',{settings:s})}
function showPlayers(list){$('players').replaceChildren();for(let p of list){let box=document.createElement('div');box.className='player';box.textContent=(p.gender==='female'?'👩 ':'👨 ')+p.name;let sm=document.createElement('small');sm.textContent=t('В комнате');box.append(sm);if(admin){let b=document.createElement('button');b.textContent=t('Убрать');b.onclick=()=>act('kick',{id:p.id});box.append(b)}$('players').append(box)}}
function render(s){let prior=state;state=s;if(!s||!s.phase)return;
 if(admin){$('adminSummary').textContent=(language==='en'?'Players: ':'Игроков: ')+s.players.map(p=>p.name).join(', ')+' · '+s.players.length+'/4';$('hostOnly').classList.toggle('hidden',s.phase!=='lobby');$('adminLive').classList.toggle('hidden',s.phase!=='playing');$('adminReset').classList.toggle('hidden',s.phase!=='ended');if(s.phase==='playing'){$('adminCurrent').textContent=s.current?.text||'';}if(hostTab==='manage'){view('adminPanel');if(s.phase==='lobby'){$('joinLink').textContent=s.address;$('joinLink').href=s.address;let qr=$('joinQr');if(qr){let src='/qr.svg?ip='+encodeURIComponent(s.address);if(qr.getAttribute('src')!==src)qr.setAttribute('src',src)}$('start').disabled=s.players.length<2;const hash=JSON.stringify(s.settings);if(settingsHash!==hash){settingsHash=hash;applySettings(s.settings);topicRender(s.topics)}}return;}}
 if(prior&&prior.phase==='lobby'&&s.phase==='playing')playSound('start');
 if(s.effect&&s.effect.revision!==lastEffect){lastEffect=s.effect.revision; if(prior&&prior.phase==='playing')cardFx(s.effect.kind)}
 if(s.phase==='playing' && s.current?.event){
  let key=String(s.index)+'|'+String(s.current.title);
  if(key!==lastEventKey){lastEventKey=key;if(prior)cardFx(eventSound(s.current))}
 }else if(s.phase!=='playing'){lastEventKey=''}
 if(s.phase==='lobby'){
  if(!admin&&!s.me){view('joinPanel');return}
  view('lobbyPanel');$('hostJoin').classList.toggle('hidden',!admin);if(admin){$('hostJoinForm').classList.toggle('hidden',!!s.me);$('hostJoined').classList.toggle('hidden',!s.me)}showPlayers(s.players);$('lobbyTitle').textContent=language==='en'?`${s.players.length} / 4 players in room`:`${s.players.length} из 4 игроков в комнате`;$('guestLobby').classList.toggle('hidden',admin);
  if(admin){$('joinLink').textContent=s.address;$('joinLink').href=s.address;let qr=$('joinQr');if(qr){let src='/qr.svg?ip='+encodeURIComponent(s.address);if(qr.getAttribute('src')!==src)qr.setAttribute('src',src)}$('start').disabled=s.players.length<2;
   const hash=JSON.stringify(s.settings);if(settingsHash!==hash){settingsHash=hash;applySettings(s.settings);topicRender(s.topics)}}
 }else if(s.phase==='playing'){
  if(!admin&&!s.me){view('joinPanel');alertMessage('Партия уже началась. Подключиться может участник, который входил ранее с этого телефона.');return}
  view('gamePanel');$('gamePanel').classList.toggle('extremeCard',s.settings.extreme);$('gamePanel').classList.toggle('bearCard',!!s.current?.bear);
  let c=s.current,reader=s.players.find(p=>p.id===s.reader);let isReader=s.me===s.reader;
  $('readerName').textContent=reader?reader.name:'—';$('counter').textContent=s.settings.mode==='quick'?(language==='en'?`Card ${s.index+1} / ${s.settings.total}`:`Карточка ${s.index+1} / ${s.settings.total}`):(language==='en'?`♾️ Card ${s.index+1}`:`♾️ Карточка ${s.index+1}`);
  $('progress').classList.toggle('hidden',s.settings.mode==='endless');$('progressFill').style.width=(100*s.index/s.settings.total)+'%';
  $('topic').textContent=t(c?.topic||'');
  $('cardTitle').textContent=c?.title||'';
  $('question').textContent=c?.text||'';
  $('readerActions').classList.toggle('hidden',!isReader||!!c?.event);
  $('eventActions').classList.toggle('hidden',!isReader||!c?.event);
  $('adminActions').classList.toggle('hidden',!admin);
  $('whoCanAct').textContent=t(isReader?'Прочитай вопрос, дай всем ответить и переходи дальше.':'Отвечают все вслух или жестом. Переключает карточку читающий.');
 }else if(s.phase==='ended'){
  view('endPanel');$('endText').textContent=language==='en'?`You played ${s.index} cards. Thanks for joining!`:`Вы посмотрели ${s.index} карточек. Спасибо за игру!`;
  $('reset').classList.toggle('hidden',!admin);$('guestEnd').classList.toggle('hidden',admin);
 }
}
$('joinForm').onsubmit=async(e)=>{e.preventDefault();await act('join',{name:$('playerName').value,gender:$('playerGender').value})};
$('leave').onclick=async()=>{await act('leave');token='';localStorage.removeItem('party-v5-token')};
$('quick').onclick=()=>{$('quick').classList.add('active');$('endless').classList.remove('active');$('totalBox').classList.remove('hidden');saveSettings()};
$('endless').onclick=()=>{$('endless').classList.add('active');$('quick').classList.remove('active');$('totalBox').classList.add('hidden');saveSettings()};
$('roomLanguage').onchange=saveSettings;$('total').onchange=saveSettings;$('extreme').onchange=()=>{$('topicBlock').classList.toggle('hidden',$('extreme').checked);saveSettings()};$('events').onchange=()=>{$('rateBox').classList.toggle('hidden',!$('events').checked);saveSettings()};
$('partyLevel').oninput=showPartyLevel;$('partyLevel').onchange=saveSettings;
$('rate').oninput=()=>{$('rateText').textContent=$('rate').value+'%'};$('rate').onchange=saveSettings;
$('allTopics').onclick=()=>{[...$('topics').querySelectorAll('input')].forEach(x=>x.checked=true);saveSettings()};
$('noTopics').onclick=()=>{[...$('topics').querySelectorAll('input')].forEach(x=>x.checked=false);alertMessage('Выберите темы или включите жёсткий режим.')};
$('start').onclick=()=>act('start');
$('yes').onclick=()=>act('next',{kind:'yes'});$('no').onclick=()=>act('next',{kind:'no'});$('skip').onclick=()=>act('next',{kind:'skip'});$('eventNext').onclick=()=>act('next',{kind:'skip'});
$('forceNext').onclick=()=>act('next',{kind:'skip'});$('finish').onclick=()=>{if(confirm('Завершить игру для всех?'))act('finish')};$('reset').onclick=()=>{if(confirm('Сбросить комнату? Все игроки должны будут войти снова.'))act('reset')};
 
// User-visible UI language is per-device; question language is chosen by the host for the room.
const UI_EN = {
'Я НИКОГДА': 'NEVER HAVE I', 'НЕ…':'EVER…', 'PARTY 7.0':'PARTY 7.0',
'● Подключение…':'● Connecting…','● На связи':'● Online','● Нет связи':'● Offline',
'🎮 Играть':'🎮 Play','⚙️ Управление':'⚙️ Host controls','⚙️ ПАНЕЛЬ ВЕДУЩЕГО':'⚙️ HOST CONTROLS',
'🎉 КОМПАНИЯ В СБОРЕ':'🎉 PARTY TIME','Врывайся в тусовку!':'Join the party!',
'Введи имя, чтобы присоединиться к общей партии.':'Enter your name to join the game.',
'Твоё имя':'Your name','Например, Артём':'e.g. Alex','Форма обращения':'Grammatical form (for Russian)',
'Мужская — делал, хотел':'Male form','Женская — делала, хотела':'Female form',
'🎉 Присоединиться':'🎉 Join the game','Никаких приложений. Подключись к Wi-Fi хоста и введи имя.':'No app needed. Join your host’s network or open the online invite.',
'🎊 КОМНАТА ОЖИДАНИЯ':'🎊 WAITING ROOM','Ждём игроков':'Waiting for players',
'Каждый вводит имя и выбирает грамматическую форму. Для старта нужно от 2 до 4 участников.':'Enter a name and choose a form. Two to four players are needed.',
'📷 Подключение с телефона':'📷 Phone connection','Если камера не открывает ссылку, введи адрес в браузере телефона.':'If the QR code fails, enter the link on your phone.',
'⚙️ Правила партии':'⚙️ Game rules','⚡ Быстрый':'⚡ Quick','♾️ Бесконечный':'♾️ Endless',
'Всего вопросов':'Total questions','🔥 ОСОБО ЖЁСТКИЙ 18+ · 5/5':'🔥 EXTREME 18+ · 5/5',
'Отдельная категория провокационных вопросов':'A separate set of bold and provocative questions',
'Темы':'Topics','Все':'All','Ни одной':'None','🎚️ Уровень безумия вечеринки:':'🎚️ Party intensity:',
'Влияет на частоту сюрпризов и шанс появления «Медведя». Не задаёт обязательное количество алкоголя.':'Changes event frequency, not how much anyone must drink.',
'🎁 Кот в мешке + 🐻 Медведь пришёл':'🎁 Mystery events + 🐻 Bear attack',
'Частота событий':'Event frequency','🚀 Начать вечеринку':'🚀 Start the party',
'🎮 Играть с телефона-хоста':'🎮 Play on host phone','Моё имя':'My name','Как тебя зовут?':'Your name',
'🙋 Войти в игру':'🙋 Join as player','Ты участвуешь в партии. Очередь чтения придёт и к тебе.':'You are in the game and will take turns reading.',
'Выйти из списка игроков':'Leave the players list','Ведущий настраивает партию на устройстве ведущего. Как только он нажмёт «Начать», появится твой экран.':'The host is setting up the room. Your game will appear when they start.',
'Выйти из комнаты':'Leave room','Управление партией':'Manage the game',
'🎤 Сейчас в игре':'🎤 Now playing','⏭ Следующий вопрос':'⏭ Next question','🏁 Завершить партию':'🏁 End game',
'🔄 Новая партия':'🔄 New game','👑 СЕЙЧАС ЧИТАЕТ':'👑 NOW READING',
'Я НИКОГДА НЕ…':'NEVER HAVE I EVER…','✓ БЫЛО':'✓ I HAVE','✕ НЕ БЫЛО':'✕ NEVER',
'⏭ Пропустить вопрос':'⏭ Skip question','🎲 Следующая карточка':'🎲 Next card',
'⏭ Следующая карточка':'⏭ Next card','🏁 Завершить игру':'🏁 End game',
'Отвечают все. У кого было — по желанию делают небольшой глоток. Пропуск разрешён всегда.':'Everyone answers. A sip is optional. You can always skip.',
'🎉 ФИНАЛ!':'🎉 GAME OVER!','Вот это вечер!':'What a night!',
'Никто не обязан раскрывать личные истории или пить. Главное — хорошая компания.':'Nobody has to share stories or drink. Just have fun.',
'🔄 Создать новую партию':'🔄 Start a new game',
'Ведущий может создать новую партию на устройстве ведущего.':'The host can create another game.',
'🔞 18+ · Играйте с уважением друг к другу · Пропуск всегда разрешён':'🔞 18+ · Respect each other · Skipping is always allowed',
'В комнате':'In room','Убрать':'Remove',
'Прочитай вопрос, дай всем ответить и переходи дальше.':'Read aloud, let everyone answer, then continue.',
'Отвечают все вслух или жестом. Переключает карточку читающий.':'Everyone answers aloud or with a gesture. The reader advances.',
'Тихо и мирно':'Calm','Разогрев':'Warm-up','Жарко':'Spicy','Без тормозов':'Wild','Полный хаос':'Total chaos',
'Соединение потеряно — переподключаемся…':'Connection lost — reconnecting…',
'Выбери хотя бы одну тему или включи жёсткий режим.':'Select a topic or enable Extreme mode.',
'Выберите темы или включите жёсткий режим.':'Choose some topics or turn on Extreme mode.',
'🌐 Язык вопросов для всей комнаты / Question language':'🌐 Question language for everyone',
'Никаких обязательных штрафов.':'No mandatory penalties.',
'Угар и кринж':'Cringe & laughs','Вечеринки и алкоголь':'Parties & drinks','Флирт и свидания':'Flirting & dating',
'18+ без цензуры':'Unfiltered 18+','Секреты и компромат':'Secrets & gossip','Отношения и бывшие':'Relationships & exes',
'Безумные поступки':'Wild adventures','Друзья и компания':'Friends','Неловкие ситуации':'Awkward moments',
'Смелые признания':'Bold confessions','Мужские вопросы':'Personal confessions','Деньги и мораль':'Money & morals',
'Особо жёсткий 18+':'Extreme 18+','Работа и офис':'Work & office','Интернет и соцсети':'Internet & social',
'Путешествия и приключения':'Travel','Еда и странные привычки':'Food & habits','Семья и детство':'Family & childhood',
'Тёмные мысли и моральные дилеммы':'Dark thoughts & dilemmas','Неприличные истории 18+':'Spicy stories 18+',
'Кино и сериалы':'Movies & TV','Музыка и караоке':'Music & karaoke','Дом и быт':'Home & life',
'Спорт и приключения':'Sports & adventure','Животные и питомцы':'Pets','Игры и геймеры':'Gaming',
'Школа и универ':'School & university','Технологии и гаджеты':'Tech & gadgets','Странные страхи':'Weird fears',
'Абсурдные пари':'Absurd bets','Ночные разговоры':'Late-night talks','Соседи и город':'Neighbors & city',
'Мода и стиль':'Fashion & style',
};
function t(s){return language==='en'?(UI_EN[s]||s):s}
const transNodes=new WeakMap();
function translateUI(){
 const walk=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let node;
 while(node=walk.nextNode()){
  if(!node.parentElement || node.parentElement.closest('script,style,#question,#adminCurrent,#readerName,#joinLink,#counter,#lobbyTitle,#endText,#partyLevelText,#whoCanAct,#alert,#cardTitle,#connection'))continue;
  let saved=transNodes.get(node), now=node.nodeValue;
  if(!saved || saved.out!==now){saved={orig:now,out:now};}
  const trim=saved.orig.trim();const result=t(trim);let next=trim && result!==trim?saved.orig.replace(trim,result):saved.orig;
  if(node.nodeValue!==next)node.nodeValue=next;
  transNodes.set(node,{orig:saved.orig,out:next});
 }
 for(const id of ['playerName','hostPlayerName']){
   let e=$(id);if(e)e.placeholder=language==='en'?(id==='playerName'?'e.g. Alex':'Your name'):(id==='playerName'?'Например, Артём':'Как тебя зовут?');
 }
 $('brandName').innerHTML=language==='en'?'NEVER HAVE I<br>EVER…':'Я НИКОГДА<br>НЕ…';
}
function setLanguage(lang){language=lang==='en'?'en':'ru';localStorage.setItem('party-ui-lang',language);$('uiLanguage').value=language;document.documentElement.lang=language;translateUI();if(state)render(state)}
$('prefsToggle').onclick=()=>{$('prefsPanel').classList.toggle('hidden');audioEngine()};
$('uiLanguage').value=language;$('uiLanguage').onchange=e=>setLanguage(e.target.value);
$('soundEnabled').checked=soundEnabled;$('soundEnabled').onchange=e=>{soundEnabled=e.target.checked;localStorage.setItem('party-sounds-enabled',String(soundEnabled));if(soundEnabled)playSound('click')};
$('effectsVolume').value=Math.round(fxVolume*100);
$('effectsVolumeValue').textContent=Math.round(fxVolume*100)+'%';
$('effectsVolume').oninput=e=>{fxVolume=Number(e.target.value)/100;$('effectsVolumeValue').textContent=e.target.value+'%';localStorage.setItem('party-fx-volume',e.target.value)};
$('testSound').onclick=()=>playSound('yes');
translateUI();

update();setInterval(update,900);
})();
