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
async function update(){if(requesting)return;requesting=true;try{let res=await fetch('/api/state',{headers:{'X-Party-Token':token,'X-Party-Admin':adminKey},cache:'no-store'});if(!res.ok)throw Error('Сервер недоступен');let data=await res.json();render(data);$('connection').textContent='● На связи';$('connection').style.color='#baffdc';if($('alert').textContent==='Соединение потеряно — переподключаемся…')alertMessage('')}catch(e){$('connection').textContent='● Нет связи';$('connection').style.color='#ffb5b8';alertMessage('Соединение потеряно — переподключаемся…')}finally{requesting=false}}
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
function cardFx(kind){if(!kind||kind==='skip')return;let el=$('effects');el.replaceChildren();el.className='';if(kind==='bear'){
  el.innerHTML='<div class="bearScene"><div class="bearEmoji" role="img" aria-label="Мультяшный медведь">🐻</div><div class="bearSpeech">МЕДВЕДЬ ПРИШЁЛ!</div></div>';
 }else{let label=document.createElement('div');label.className='effectSymbol';label.textContent=kind==='yes'?'🥂':kind==='surprise'?'🎁':'✨';el.append(label)}
 void el.offsetWidth;el.className='play '+(kind==='bear'?'bearEffect':'');partySound(kind)}
// Mobile browsers unlock sound only after an explicit tap.
for(let ev of ['touchstart','pointerdown'])document.addEventListener(ev,()=>{if(!audioUnlocked){audioUnlocked=true;audioEngine()}},{once:true,passive:true});
function topicRender(topics){let root=$('topics');root.replaceChildren();Object.entries(topics||{}).filter(([t])=>t!=='Особо жёсткий 18+').forEach(([name,n])=>{let label=document.createElement('label');label.className='topicItem';let ch=document.createElement('input');ch.type='checkbox';ch.value=name;ch.checked=state.settings.topics.includes(name);ch.addEventListener('change',saveSettings);let s=document.createElement('span');s.textContent=name+' ';let small=document.createElement('small');small.textContent='('+n+')';s.append(small);label.append(ch,s);root.append(label)})}
function showPartyLevel(){const labels=['','Тихо и мирно','Разогрев','Жарко','Без тормозов','Полный хаос'];$('partyLevelText').textContent=$('partyLevel').value+'/5 — '+labels[Number($('partyLevel').value)]}
function applySettings(s){$('quick').classList.toggle('active',s.mode==='quick');$('endless').classList.toggle('active',s.mode==='endless');$('totalBox').classList.toggle('hidden',s.mode==='endless');$('total').value=s.total;$('extreme').checked=s.extreme;$('topicBlock').classList.toggle('hidden',s.extreme);$('events').checked=s.events;$('rate').value=Math.round(s.rate*100);$('rateText').textContent=Math.round(s.rate*100)+'%';$('rateBox').classList.toggle('hidden',!s.events);$('partyLevel').value=s.party_level||3;showPartyLevel()}
function getSettings(){return {mode:$('endless').classList.contains('active')?'endless':'quick',total:Math.max(1,Math.min(10000,Number($('total').value)||20)),extreme:$('extreme').checked,topics:[...$('topics').querySelectorAll('input:checked')].map(x=>x.value),events:$('events').checked,rate:Number($('rate').value)/100,party_level:Number($('partyLevel').value)}}
async function saveSettings(){if(!admin||!state||state.phase!=='lobby')return;let s=getSettings();if(!s.extreme&&!s.topics.length){alertMessage('Выбери хотя бы одну тему или включи жёсткий режим.');return}await act('settings',{settings:s})}
function showPlayers(list){$('players').replaceChildren();for(let p of list){let box=document.createElement('div');box.className='player';box.textContent=(p.gender==='female'?'👩 ':'👨 ')+p.name;let sm=document.createElement('small');sm.textContent='В комнате';box.append(sm);if(admin){let b=document.createElement('button');b.textContent='Убрать';b.onclick=()=>act('kick',{id:p.id});box.append(b)}$('players').append(box)}}
function render(s){let prior=state;state=s;if(!s||!s.phase)return;
 if(admin){$('adminSummary').textContent='Игроков: '+s.players.map(p=>p.name).join(', ')+' · '+s.players.length+'/4';$('hostOnly').classList.toggle('hidden',s.phase!=='lobby');$('adminLive').classList.toggle('hidden',s.phase!=='playing');$('adminReset').classList.toggle('hidden',s.phase!=='ended');if(s.phase==='playing'){$('adminCurrent').textContent=s.current?.text||'';}if(hostTab==='manage'){view('adminPanel');if(s.phase==='lobby'){$('joinLink').textContent=s.address;$('joinLink').href=s.address;let qr=$('joinQr');if(qr){let src='/qr.svg?ip='+encodeURIComponent(s.address);if(qr.getAttribute('src')!==src)qr.setAttribute('src',src)}$('start').disabled=s.players.length<2;const hash=JSON.stringify(s.settings);if(settingsHash!==hash){settingsHash=hash;applySettings(s.settings);topicRender(s.topics)}}return;}}
 if(s.effect&&s.effect.revision!==lastEffect){lastEffect=s.effect.revision; if(prior&&prior.phase==='playing')cardFx(s.effect.kind)}
 if(s.phase==='playing' && s.current?.event){
  let key=String(s.index)+'|'+String(s.current.title);
  if(key!==lastEventKey){lastEventKey=key;if(prior&&prior.phase==='playing')cardFx(s.current.bear?'bear':'surprise')}
 }else if(s.phase!=='playing'){lastEventKey=''}
 if(s.phase==='lobby'){
  if(!admin&&!s.me){view('joinPanel');return}
  view('lobbyPanel');$('hostJoin').classList.toggle('hidden',!admin);if(admin){$('hostJoinForm').classList.toggle('hidden',!!s.me);$('hostJoined').classList.toggle('hidden',!s.me)}showPlayers(s.players);$('lobbyTitle').textContent=s.players.length+' из 4 игроков в комнате';$('guestLobby').classList.toggle('hidden',admin);
  if(admin){$('joinLink').textContent=s.address;$('joinLink').href=s.address;let qr=$('joinQr');if(qr){let src='/qr.svg?ip='+encodeURIComponent(s.address);if(qr.getAttribute('src')!==src)qr.setAttribute('src',src)}$('start').disabled=s.players.length<2;
   const hash=JSON.stringify(s.settings);if(settingsHash!==hash){settingsHash=hash;applySettings(s.settings);topicRender(s.topics)}}
 }else if(s.phase==='playing'){
  if(!admin&&!s.me){view('joinPanel');alertMessage('Партия уже началась. Подключиться может участник, который входил ранее с этого телефона.');return}
  view('gamePanel');$('gamePanel').classList.toggle('extremeCard',s.settings.extreme);$('gamePanel').classList.toggle('bearCard',!!s.current?.bear);
  let c=s.current,reader=s.players.find(p=>p.id===s.reader);let isReader=s.me===s.reader;
  $('readerName').textContent=reader?reader.name:'—';$('counter').textContent=s.settings.mode==='quick'?`Карточка ${s.index+1} / ${s.settings.total}`:`♾️ Карточка ${s.index+1}`;
  $('progress').classList.toggle('hidden',s.settings.mode==='endless');$('progressFill').style.width=(100*s.index/s.settings.total)+'%';
  $('topic').textContent=c?.topic||'';
  $('cardTitle').textContent=c?.title||'';
  $('question').textContent=c?.text||'';
  $('readerActions').classList.toggle('hidden',!isReader||!!c?.event);
  $('eventActions').classList.toggle('hidden',!isReader||!c?.event);
  $('adminActions').classList.toggle('hidden',!admin);
  $('whoCanAct').textContent=isReader?'Прочитай вопрос, дай всем ответить и переходи дальше.':'Отвечают все вслух или жестом. Переключает карточку читающий.';
 }else if(s.phase==='ended'){
  view('endPanel');$('endText').textContent=`Вы посмотрели ${s.index} карточек. Спасибо за игру!`;
  $('reset').classList.toggle('hidden',!admin);$('guestEnd').classList.toggle('hidden',admin);
 }
}
$('joinForm').onsubmit=async(e)=>{e.preventDefault();await act('join',{name:$('playerName').value,gender:$('playerGender').value})};
$('leave').onclick=async()=>{await act('leave');token='';localStorage.removeItem('party-v5-token')};
$('quick').onclick=()=>{$('quick').classList.add('active');$('endless').classList.remove('active');$('totalBox').classList.remove('hidden');saveSettings()};
$('endless').onclick=()=>{$('endless').classList.add('active');$('quick').classList.remove('active');$('totalBox').classList.add('hidden');saveSettings()};
$('total').onchange=saveSettings;$('extreme').onchange=()=>{$('topicBlock').classList.toggle('hidden',$('extreme').checked);saveSettings()};$('events').onchange=()=>{$('rateBox').classList.toggle('hidden',!$('events').checked);saveSettings()};
$('partyLevel').oninput=showPartyLevel;$('partyLevel').onchange=saveSettings;
$('rate').oninput=()=>{$('rateText').textContent=$('rate').value+'%'};$('rate').onchange=saveSettings;
$('allTopics').onclick=()=>{[...$('topics').querySelectorAll('input')].forEach(x=>x.checked=true);saveSettings()};
$('noTopics').onclick=()=>{[...$('topics').querySelectorAll('input')].forEach(x=>x.checked=false);alertMessage('Выберите темы или включите жёсткий режим.')};
$('start').onclick=()=>act('start');
$('yes').onclick=()=>act('next',{kind:'yes'});$('no').onclick=()=>act('next',{kind:'no'});$('skip').onclick=()=>act('next',{kind:'skip'});$('eventNext').onclick=()=>act('next',{kind:'skip'});
$('forceNext').onclick=()=>act('next',{kind:'skip'});$('finish').onclick=()=>{if(confirm('Завершить игру для всех?'))act('finish')};$('reset').onclick=()=>{if(confirm('Сбросить комнату? Все игроки должны будут войти снова.'))act('reset')};
update();setInterval(update,900);
})();
