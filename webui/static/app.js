'use strict';

const token = document.querySelector('meta[name="pyla-ui-token"]').content;
const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const titles = {dashboard:'Обзор',queue:'Очередь бойцов',playstyles:'Стили игры',history:'История матчей',logs:'Логи',settings:'Настройки',integrations:'Интеграции',review:'Проверка перед запуском'};
const states = {idle:'Не запущен',running:'Работает',paused:'На паузе',stopping:'Останавливается',stopped:'Остановлен',error:'Ошибка запуска',external:'Другой лаунчер'};
const sections = {general:'Общие',bot:'Игра и движение',timers:'Таймеры',telegram:'Telegram',discord:'Discord',api:'Brawl Stars API'};
const choiceLabels = {'upstream-763c389':'Актуальные · 31.10.2026',legacy:'Прежние модели',search:'Поиск по имени',legacy_scroll:'Листание · прежний интерфейс'};
const state = {instance:1,instances:[],catalog:[],details:[],players:{},rows:[],devices:null,page:'dashboard',tab:'general',fields:[],clearSecrets:new Set(),busy:false,requestId:0,step:0,selectedBrawler:'',filter:'',accountBusy:false};
const active = () => ['running','paused','stopping','external'].includes(current()?.state);
const current = () => state.instances.find(i => i.instance === state.instance);
const endpoint = (suffix) => `/api/instances/${state.instance}/${suffix}`;
const instanceName = (id) => `Экземпляр ${String(id).padStart(2,'0')}`;
const brawlerInfo = name => state.details.find(item=>item.name===name) || {name,display_name:name.charAt(0).toUpperCase()+name.slice(1),icon:`/assets/brawlers/${encodeURIComponent(name)}.png`};
const displayName = name => brawlerInfo(name).display_name;
const portrait = (name, className='brawler-avatar') => `<img class="${className}" src="${escapeHtml(brawlerInfo(name).icon)}" alt="" loading="lazy">`;
const setupContext = () => ({device:Boolean(state.devices?.some(device=>String(device.port)===String(current()?.port))),queue:current()?.queue_count || 0});
const renderedChrome=new WeakMap();
function setChromeMarkup(element,markup) {
  if(renderedChrome.get(element)!==markup){element.innerHTML=markup;renderedChrome.set(element,markup);}
}

function updateSetup() {
  const guided=state.step>=0;
  document.body.classList.toggle('setup-mode',guided);
  $('#setup-progress').hidden=!guided;
  $('#setup-navigation').hidden=!guided;
  $('#setup-return').hidden=guided;
  if(guided) $('#setup-return').href=PylaSetup.routes[state.step];
  if(!guided) return;
  const names=['Эмулятор','Аккаунт','Бойцы','Запуск'];
  setChromeMarkup($('#setup-progress'),`<div class="setup-brand">Pyla<span>AI</span> <small>Подготовка запуска</small></div><ol>${names.map((name,index)=>`<li class="${index===state.step?'current':index<state.step?'done':''}" ${index===state.step?'aria-current="step"':''}><span>${index<state.step?'✓':index+1}</span>${name}</li>`).join('')}</ol>`);
  setChromeMarkup($('#setup-navigation'),`<button class="button secondary" data-setup="back" ${state.step===0||state.accountBusy||state.busy?'disabled':''}>← Назад</button><span class="muted">Шаг ${state.step+1} из 4</span>${state.step===3?`<button class="button primary" data-setup="start" ${active()||state.busy||!PylaSetup.canStart(setupContext())?'disabled':''}>▶ Запустить бота</button>`:`<button class="button primary" data-setup="next" ${state.accountBusy||state.busy||(state.step===0&&!setupContext().device)||(state.step===2&&!state.rows.length)?'disabled':''}>${state.step===1&&!state.players[state.instance]?'Продолжить без API':'Далее'} →</button>`}`);
}

async function loadAccount() {
  if(state.accountBusy) return;
  const instance=state.instance,view=state.requestId;
  state.accountBusy=true;updateChrome();
  const button=$('[data-action="load-player"]');
  if(button){button.disabled=true;button.textContent='Подключаем аккаунт…';}
  try {
    if(state.page==='integrations' && state.tab==='api') {if(!await saveSettings())return;renderSettings();}
    const response=await api(`/api/instances/${instance}/player`,'POST');
    state.players[instance]=response.player;
    if(instance!==state.instance) return;
    toast('Аккаунт загружен. Трофеи доступны при выборе бойцов.');
  } finally {
    state.accountBusy=false;
    if(instance===state.instance&&view===state.requestId) await renderPage();
    updateChrome();
  }
}

async function startRuntime() {
  state.busy=true;updateChrome();updateSetup();
  try {
    await api(endpoint(`runtime/${current()?.state==='paused'?'resume':'start'}`),'POST');
    await refreshInstances();location.hash='logs';
  } finally {state.busy=false;updateChrome();updateSetup();}
}

async function api(path, method='GET', data) {
  const options = {method,headers:{'X-Pyla-UI-Token':token}};
  if (data !== undefined) { options.headers['Content-Type']='application/json'; options.body=JSON.stringify(data); }
  const response = await fetch(path, options);
  let body;
  try { body=await response.json(); } catch { throw new Error('Панель не ответила. Проверь, что PylaAI запущен.'); }
  if (!response.ok || body.ok === false) throw new Error(body.message || 'Не удалось выполнить действие.');
  return body;
}

let toastTimer;
function toast(message, error=false) {
  const box=$('#toast'); box.textContent=message; box.className=`toast${error?' error':''}`; box.hidden=false;
  clearTimeout(toastTimer); toastTimer=setTimeout(()=>{box.hidden=true;},error?9000:3500);
}
async function safely(action) { try { await action(); } catch(error) { toast(error.message,true); } }
function heading(title,description,actions='') { return `<div class="page-heading"><div><div class="eyebrow">${escapeHtml(instanceName(state.instance))}</div><h1>${title}</h1><p>${description}</p></div>${actions}</div>`; }
function empty(title,description,action='') { return `<div class="empty-state"><div class="empty-icon">◇</div><h3>${title}</h3><p>${description}</p>${action}</div>`; }
function badge(item) { return `<span class="badge ${item.state==='running'?'green':item.state==='error'?'red':''}">${escapeHtml(states[item.state] || item.state)}</span>`; }

function updateChrome() {
  const item=current() || {state:'idle',queue_count:0};
  document.body.classList.toggle('bot-active',active());
  $('#instance-select').innerHTML=state.instances.map(i=>`<option value="${i.instance}" ${i.instance===state.instance?'selected':''}>${instanceName(i.instance)}</option>`).join('');
  $('#runtime-label').textContent=states[item.state] || item.state;
  $('#runtime-dot').className=`status-dot ${item.state}`;
  $('#runtime-detail').textContent=`${item.emulator || 'Эмулятор не выбран'} · порт ${item.port || '—'}`;
  $('#nav-queue-count').textContent=item.queue_count;
  const isPaused=item.state==='paused';
  $('#start-bot').textContent=isPaused?'▶ Продолжить':'▶ Запустить';
  $('#start-bot').disabled=state.busy || (!isPaused && (active() || !item.queue_count));
  $('#pause-bot').disabled=state.busy || item.state!=='running';
  $('#stop-bot').disabled=state.busy || !['running','paused'].includes(item.state);
  $('#add-instance').disabled=state.busy;
  $('#instance-select').disabled=state.accountBusy || state.busy;
  updateSetup();
}

async function refreshInstances() {
  const previous=JSON.stringify(state.instances);
  state.instances=(await api('/api/instances')).instances;
  updateChrome();
  if (state.page==='dashboard' && previous!==JSON.stringify(state.instances)) renderDashboard();
}

function renderDashboard() {
  const item=current() || {};
  const ready=Boolean(item.queue_count);
  const deviceBody=state.devices===null
    ? empty('Подключи свой эмулятор','Запусти Brawl Stars в эмуляторе и проверь подключённые устройства.','<button class="button ghost small" data-action="scan">Найти устройства</button>')
    : !state.devices.length
      ? empty('Устройства пока не найдены','Открой эмулятор, включи ADB в его настройках и повтори поиск.','<button class="button ghost small" data-action="scan">Повторить поиск</button>')
      : `<div class="panel-body stack">${state.devices.map(device=>`<div class="row"><div><div class="instance-name">${escapeHtml(device.emulator)}</div><div class="muted">${escapeHtml(device.serial)}</div></div><button class="button ${device.port===item.port?'ghost':'secondary'} small" data-action="device" data-serial="${escapeHtml(device.serial)}" ${active()?'disabled':''}>${device.port===item.port?'Выбрано':'Выбрать'}</button></div>`).join('')}</div>`;
  if(state.step===0) {
    $('#content').innerHTML=heading('Сначала выбери эмулятор','Запусти эмулятор и открой Brawl Stars. Затем выбери устройство и нажми «Далее».')+`<section class="panel"><div class="panel-heading"><h2>Подключённые устройства</h2><button class="link-button" data-action="scan">Найти устройства ↻</button></div>${deviceBody}</section><div class="setup-links"><a href="#settings">Дополнительные настройки эмулятора</a><a href="#dashboard">Открыть обзор</a></div>`;
    return;
  }
  $('#content').innerHTML=`
    <div class="hero"><div><div class="eyebrow">ТВОЙ ЦЕНТР УПРАВЛЕНИЯ</div><h1>${ready?'Всё начинается с хорошего плана.':'Готов к следующему матчу?'}</h1><p>Выбери эмулятор, собери очередь бойцов и управляй всеми экземплярами из одного места.</p><a class="button primary" href="#queue">${ready?'Открыть очередь':'Собрать очередь'} <span aria-hidden="true">→</span></a></div><div class="hero-art" aria-hidden="true">P/</div></div>
    <div class="stats">
      <div class="stat-card"><div class="stat-title">БОЙЦОВ В ОЧЕРЕДИ<span class="stat-icon">☷</span></div><div class="stat-value">${item.queue_count || 0}</div><div class="stat-footnote">Для текущего экземпляра</div></div>
      <div class="stat-card"><div class="stat-title">ЭКЗЕМПЛЯРОВ<span class="stat-icon">◫</span></div><div class="stat-value">${state.instances.length}</div><div class="stat-footnote">${state.instances.filter(i=>['running','paused'].includes(i.state)).length} запущено сейчас</div></div>
      <div class="stat-card"><div class="stat-title">ЭМУЛЯТОР<span class="stat-icon">⌁</span></div><div class="stat-value">${escapeHtml(item.emulator || '—')}</div><div class="stat-footnote">Порт ${escapeHtml(item.port || 'не задан')}</div></div>
    </div>
    <div class="two-columns"><section class="panel"><div class="panel-heading"><h2>Твои экземпляры</h2><button class="link-button" data-action="add-instance">＋ Добавить</button></div><div class="panel-body">${state.instances.map(i=>`<div class="row instance-item"><div class="inline"><span class="instance-avatar">${String(i.instance).padStart(2,'0')}</span><div><div class="instance-name">${instanceName(i.instance)}</div><div class="muted">${escapeHtml(i.emulator)} · ${escapeHtml(i.port)} · ${i.queue_count} в очереди</div></div></div><div class="inline">${badge(i)}<button class="link-button" data-action="select-instance" data-id="${i.instance}">${i.instance===state.instance?'Выбран':'Открыть'}</button></div></div>`).join('')}</div></section>
    <section class="panel"><div class="panel-heading"><h2>Подключённые устройства</h2><button class="link-button" data-action="scan">Обновить ↻</button></div>${deviceBody}</section></div>
    <div class="panel"><div class="panel-body row"><div><div class="instance-name">Всегда под рукой</div><div class="muted">Уведомления о матчах и управление через Telegram или Discord.</div></div><a class="button ghost small" href="#integrations">Настроить интеграции →</a></div></div>`;
}

function renderQueue() {
  const locked=active();
  const player=state.players[state.instance];
  const owned=new Map((player?.brawlers || []).map(row=>[row.name.toLowerCase().replace(/[^a-z0-9]/g,''),row]));
  const available=state.catalog.filter(name=>!player || owned.has(name.replace(/[^a-z0-9]/g,'')));
  if(!available.includes(state.selectedBrawler)) state.selectedBrawler='';
  const cards=available.map(name=>{
    const row=owned.get(name.replace(/[^a-z0-9]/g,'')),queued=state.rows.some(item=>item.brawler===name);
    return `<button type="button" class="brawler-card ${name===state.selectedBrawler?'selected':''}" data-action="pick-brawler" data-name="${escapeHtml(name)}" data-search="${escapeHtml(displayName(name).toLowerCase())}" ${locked||queued?'disabled':''} aria-pressed="${name===state.selectedBrawler}">${portrait(name,'brawler-portrait')}<strong>${escapeHtml(displayName(name))}</strong><small>${queued?'В очереди':row?`${Number(row.trophies)} трофеев`:'Указать трофеи вручную'}</small></button>`;
  }).join('');
  $('#content').innerHTML=heading('Твой следующий состав','Добавляй бойцов, задавай цели и меняй порядок прохождения.')+
    (locked?'<div class="notice">Экземпляр запущен. Останови его, чтобы изменить состав или цель.</div>':'')+
    `<section class="panel"><div class="panel-heading"><div><h2>Выбери бойца</h2><small>${player?'Бойцы твоего аккаунта · трофеи загружены':'Ручной выбор · вход в API не обязателен'}</small></div><button class="button ghost small" data-action="load-player" ${locked||state.accountBusy?'disabled':''}>${state.accountBusy?'Загрузка…':'Загрузить мой аккаунт'}</button></div><div class="panel-body"><label class="sr-only" for="brawler-search">Поиск бойца</label><input id="brawler-search" type="search" placeholder="Найти бойца по имени…" value="${escapeHtml(state.filter)}"><div class="brawler-grid">${cards}</div><p id="brawler-empty" class="muted" hidden>Бойцы не найдены.</p></div></section>`+
    `<section class="panel"><div class="panel-heading"><h2>Добавить бойца</h2><small>Цели по трофеям или победам</small></div><div class="panel-body"><form id="queue-form" class="queue-form">
      <div class="field"><label for="brawler">Боец</label><input id="brawler" type="hidden" value="${escapeHtml(state.selectedBrawler)}"><div id="picked-brawler" class="picked-brawler">${state.selectedBrawler?portrait(state.selectedBrawler)+escapeHtml(displayName(state.selectedBrawler)):'Выбери карточку выше'}</div></div>
      <div class="field"><label for="target-type">Тип цели</label><select id="target-type" ${locked?'disabled':''}><option value="trophies">Трофеи</option><option value="wins">Победы</option></select></div>
      <div class="field"><label for="current-value">Сейчас</label><input id="current-value" type="number" min="0" max="1000000" value="0" required ${locked?'disabled':''}></div>
      <div class="field"><label for="target-value">Цель</label><input id="target-value" type="number" min="1" max="1000000" value="1000" required ${locked?'disabled':''}></div>
      <button class="button primary" ${locked?'disabled':''}>＋ Добавить</button></form></div></section>
    <section class="panel"><div class="panel-heading"><h2>Очередь <span class="badge purple">${state.rows.length}</span></h2><div class="inline"><button class="button ghost small" data-action="sync" ${locked||!state.rows.length?'disabled':''}>Обновить трофеи</button><label class="sr-only" for="push-all-target">Цель Push All</label><select id="push-all-target"><option>250</option><option>500</option><option>750</option><option selected>1000</option></select><button class="button secondary small" data-action="push-all" ${locked?'disabled':''}>Push All</button></div></div>
    ${state.rows.length?`<div class="table-wrap"><table><thead><tr><th>№</th><th>БОЕЦ</th><th>ТИП</th><th>СЕЙЧАС</th><th>ЦЕЛЬ</th><th>АВТОВЫБОР</th><th></th></tr></thead><tbody>${state.rows.map((row,index)=>`<tr><td>${String(index+1).padStart(2,'0')}</td><td class="brawler-name"><span class="brawler-cell">${portrait(row.brawler)}${escapeHtml(displayName(row.brawler))}</span></td><td>${row.type==='wins'?'Победы':'Трофеи'}</td><td><input class="table-input" type="number" min="0" max="1000000" value="${row[row.type]}" data-index="${index}" data-field="${row.type}" aria-label="${escapeHtml(row.brawler)}: сейчас" ${locked?'disabled':''}></td><td><input class="table-input" type="number" min="1" max="1000000" value="${row.push_until}" data-index="${index}" data-field="push_until" aria-label="${escapeHtml(row.brawler)}: цель" ${locked?'disabled':''}></td><td><input type="checkbox" data-index="${index}" data-field="automatically_pick" aria-label="${escapeHtml(row.brawler)}: выбирать автоматически" ${row.automatically_pick?'checked':''} ${locked?'disabled':''}></td><td><div class="table-actions"><button data-action="up" data-index="${index}" aria-label="Поднять ${escapeHtml(row.brawler)}" ${locked||index===0?'disabled':''}>↑</button><button data-action="down" data-index="${index}" aria-label="Опустить ${escapeHtml(row.brawler)}" ${locked||index===state.rows.length-1?'disabled':''}>↓</button><button data-action="remove" data-index="${index}" aria-label="Убрать ${escapeHtml(row.brawler)}" ${locked?'disabled':''}>×</button></div></td></tr>`).join('')}</tbody></table></div>`:empty('Очередь пока пустая','Добавь первого бойца выше или загрузи свой состав через Push All.')}
    <div class="form-footer"><span class="muted">Изменения очереди сохраняются автоматически. Push All использует твой аккаунт Brawl Stars API.</span><a class="link-button" href="#integrations">Настроить API ↗</a></div></section>`;
  $('#queue-form').addEventListener('submit',event=>{event.preventDefault();safely(async()=>{
    const name=$('#brawler').value.trim().toLowerCase();
    if (!state.catalog.includes(name)) throw new Error('Выбери бойца из списка.');
    if (state.rows.some(row=>row.brawler===name)) throw new Error('Этот боец уже в очереди.');
    const type=$('#target-type').value;
    const row={brawler:name,type,push_until:Number($('#target-value').value),trophies:0,wins:0,win_streak:0,automatically_pick:true};
    row[type]=Number($('#current-value').value);
    state.selectedBrawler='';await saveQueue([...state.rows,row]);
    toast('Боец добавлен в очередь.');
  });});
  $('#target-type').addEventListener('change',()=>{
    $('#target-value').value=$('#target-type').value==='wins'?10:1000;
    if(state.selectedBrawler)setBrawler(state.selectedBrawler);else $('#current-value').value=0;
  });
  const filterCards=()=>{
    state.filter=$('#brawler-search').value;
    let count=0;
    document.querySelectorAll('.brawler-card').forEach(card=>{card.hidden=!card.dataset.search.includes(state.filter.trim().toLowerCase());if(!card.hidden)count++;});
    $('#brawler-empty').hidden=Boolean(count);
  };
  $('#brawler-search').addEventListener('input',filterCards);filterCards();
  if(state.selectedBrawler) setBrawler(state.selectedBrawler);
}

function setBrawler(name) {
  state.selectedBrawler=name;$('#brawler').value=name;
  $('#picked-brawler').innerHTML=portrait(name)+escapeHtml(displayName(name));
  const owned=(state.players[state.instance]?.brawlers || []).find(row=>row.name.toLowerCase().replace(/[^a-z0-9]/g,'')===name.replace(/[^a-z0-9]/g,''));
  $('#current-value').value=$('#target-type').value==='trophies'?(owned?.trophies || 0):0;
  document.querySelectorAll('.brawler-card').forEach(card=>{const selected=card.dataset.name===name;card.classList.toggle('selected',selected);card.setAttribute('aria-pressed',String(selected));});
}

async function saveQueue(rows) {
  const instance=state.instance;
  const response=await api(endpoint('queue'),'PUT',{queue:rows});
  if(instance!==state.instance) return;
  state.rows=response.queue;
  await refreshInstances();
  if(state.page==='queue') renderQueue();
}

const labels={
  vision_model_profile:'Модели распознавания',brawler_selection_mode:'Выбор бойца в игре',
  max_ips:'Лимит циклов бота в секунду',current_emulator:'Эмулятор',emulator_port:'Порт эмулятора',cpu_or_gpu:'Устройство вычислений',run_for_minutes:'Остановиться через, минут',
  scrcpy_max_fps:'Частота кадров эмулятора',scrcpy_max_width:'Ширина видеопотока',scrcpy_bitrate:'Битрейт видеопотока',onnx_cpu_threads:'Потоки ONNX на CPU',used_threads:'Потоки обработки',
  super_debug:'Подробные сообщения',visual_debug:'Визуальная отладка',wall_stuck_debug:'Отладка застревания',terminal_logging:'Записывать терминал',pyla_version:'Версия ядра',
  gamemode:'Игровой режим',gamemode_type:'Тип игрового режима',current_playstyle:'Текущий стиль игры',bot_uses_gadgets:'Использовать гаджеты',play_again_on_win:'Играть снова после победы',
  adaptive_brain_enabled:'Адаптация по результатам матчей',adaptive_brain_window:'Матчей для адаптации',attack_cooldown:'Интервал атак, сек.',gadget_cooldown:'Интервал гаджетов, сек.',super_cooldown:'Интервал супера, сек.',
  aimed_attacks:'Прицельные атаки',lead_shots:'Упреждение выстрела',trio_grouping_enabled:'Держаться рядом с командой',wall_stuck_enabled:'Выход из застревания',strafe_while_attacking:'Стрейф во время атаки',
  telegram_bot_token:'Токен Telegram-бота',telegram_chat_id:'ID чата для уведомлений',telegram_control_user_id:'ID владельца в Telegram',telegram_control_enabled:'Управление через Telegram',
  discord_bot_token:'Токен Discord-бота',discord_control_user_id:'ID владельца в Discord',discord_control_channel_id:'ID канала управления',discord_control_guild_id:'ID сервера управления',discord_control_enabled:'Управление через Discord',
  webhook_url:'Webhook Discord',discord_id:'ID пользователя Discord',username:'Имя отправителя',personal_webhook:'Личный webhook',send_match_summary:'Итоги после матча',include_screenshot:'Прикладывать скриншот',
  ping_when_stuck:'Уведомлять о зависании',ping_when_target_is_reached:'Уведомлять о достижении цели',ping_every_x_match:'Уведомлять каждые N матчей',ping_every_x_minutes:'Уведомлять каждые N минут',
  player_tag:'Тег игрока',api_token:'Токен Brawl Stars API',developer_email:'Email портала разработчика',developer_password:'Пароль портала разработчика',auto_refresh_token:'Обновлять API-токен автоматически',
  timeout_seconds:'Таймаут API, сек.',delete_all_tokens:'Удалять все токены аккаунта при обновлении',emulator_autorestart:'Восстанавливать эмулятор автоматически',directml_device_id:'Адаптер DirectML',
  screenshot_cleanup_max_age_hours:'Срок хранения скриншотов, часов',screenshot_cleanup_max_files:'Максимум скриншотов',proxy_enabled:'Использовать прокси',
  long_press_star_drop:'Открывать награды долгим нажатием',capture_bad_vision_frames:'Сохранять кадры с ошибками распознавания',bad_vision_capture_dir:'Папка кадров для диагностики',bad_vision_capture_interval:'Интервал сохранения кадров, сек.',bad_vision_capture_max:'Максимум диагностических кадров',
  visual_debug_scale:'Масштаб окна диагностики',visual_debug_max_fps:'Частота кадров окна диагностики',visual_debug_max_boxes:'Максимум рамок в диагностике',ocr_scale_down_factor:'Масштаб изображения для чтения текста',trophies_multiplier:'Множитель трофеев',
  emulator_profile_index:'Номер профиля эмулятора',emulator_launch_command:'Своя команда запуска эмулятора',mumu_manager_path:'Путь к менеджеру MuMu',ldplayer_console_path:'Путь к консоли LDPlayer',api_base_url:'Сервер данных PylaAI',brawl_stars_package:'Android-пакет Brawl Stars',use_eu_proxy:'Подбирать европейский прокси',
  minimum_movement_delay:'Минимальная задержка движения, сек.',unstuck_movement_delay:'Задержка выхода из застревания, сек.',unstuck_movement_hold_time:'Длительность выхода из застревания, сек.',wall_stuck_ignore_radius:'Радиус игнорирования ближних стен',wall_stuck_sample_interval:'Интервал проверки стен, сек.',wall_stuck_shift_threshold:'Порог смещения стен',wall_stuck_timeout:'Время до обнаружения застревания, сек.',wall_stuck_min_walls:'Минимум стен для проверки',
  escape_retreat_duration:'Длительность отступления, сек.',escape_arc_duration:'Длительность обхода, сек.',escape_arc_degrees:'Угол обхода, градусов',wall_path_padding:'Запас расстояния до стены',wall_path_probe_tiles:'Дальность проверки пути в клетках',wall_box_min_size:'Минимальная рамка стены',wall_box_merge_iou:'Порог объединения рамок стен',wall_box_merge_center_distance:'Расстояние для объединения стен',wall_history_min_hits:'Подтверждений для сохранения стены',wall_model_classes:'Классы объектов модели стен',
  gadget_pixels_minimum:'Порог готовности гаджета, пикселей',hypercharge_pixels_minimum:'Порог готовности гиперзаряда, пикселей',super_pixels_minimum:'Порог готовности супера, пикселей',idle_pixels_minimum:'Порог окна бездействия, пикселей',wall_detection_confidence:'Уверенность распознавания стен',entity_detection_confidence:'Уверенность распознавания бойцов',entity_detection_retry_confidence:'Уверенность повторного поиска бойца',player_center_bias_radius:'Радиус поиска своего бойца от центра',player_green_pixel_weight:'Вес зелёного цвета при поиске бойца',player_red_pixel_penalty:'Штраф за красный цвет при поиске бойца',
  teammate_follow_min_distance:'Минимальная дистанция до союзника',teammate_follow_max_distance:'Максимальная дистанция до союзника',teammate_combat_regroup_distance:'Дистанция возвращения к команде',teammate_combat_bias:'Притяжение к команде в бою',seconds_to_hold_attack_after_reaching_max:'Удерживать атаку после зарядки, сек.',match_warmup_seconds:'Задержка после начала матча, сек.',strafe_interval:'Интервал смены стрейфа, сек.',strafe_blend:'Сила стрейфа',combat_dodge_blend:'Сила уклонения в бою',combat_dodge_jitter_degrees:'Разброс направления уклонения',projectile_speed_px_s:'Скорость снаряда, пикселей/сек.',roam_direction_hold_time:'Удерживать направление поиска, сек.',roam_center_bias:'Притяжение к центру карты',retreat_strafe_fraction:'Доля стрейфа при отступлении',approach_flank_blend:'Сила обхода противника',multi_enemy_flee_weight:'Вес угрозы нескольких противников',angle_smooth_factor:'Сглаживание направления',
  super:'Проверка супера, сек.',hypercharge:'Проверка гиперзаряда, сек.',gadget:'Проверка гаджета, сек.',wall_detection:'Проверка стен, сек.',no_detection_proceed:'Ожидание при потере распознавания, сек.',state_check:'Проверка экрана игры, сек.',idle:'Проверка бездействия, сек.',check_if_brawl_stars_crashed:'Проверка состояния игры, сек.',
};
const help={max_ips:'0 — без ограничения.',run_for_minutes:'0 — без ограничения времени.',emulator_port:'Порт устройства ADB из настроек эмулятора. 5037 — порт сервера, он не подходит.',telegram_control_user_id:'Именно ID пользователя, которому разрешено управлять ботом.',discord_control_user_id:'ID пользователя Discord, которому разрешено управлять ботом.',developer_password:'Пустое поле сохраняет прежний пароль.',delete_all_tokens:'Удаляет также ключи других приложений. Обычно оставляй выключенным.',player_tag:'Тег Brawl Stars, например #ABC123.',api_token:'Ключ официального API, привязанный к твоему публичному IP.'};

function fieldHtml(field,index) {
  const id=`field-${index}`, title=labels[field.key] || field.key.replaceAll('_',' ');
  const disabled=active() || state.accountBusy || field.key==='pyla_version';
  const val=field.value;
  if(field.type==='bool') return `<div class="field"><div class="check-field"><input id="${id}" type="checkbox" ${val?'checked':''} ${disabled?'disabled':''}><label for="${id}">${escapeHtml(title)}</label></div>${help[field.key]?`<div class="field-help">${help[field.key]}</div>`:''}</div>`;
  const common=`id="${id}" ${disabled?'disabled':''}`;
  let control;
  if(field.choices.length) control=`<select ${common}>${field.choices.map(v=>`<option value="${escapeHtml(v)}" ${v===val?'selected':''}>${v==='yes'?'Включено':v==='no'?'Выключено':escapeHtml(choiceLabels[v] || v)}</option>`).join('')}</select>`;
  else if(field.type==='list') control=`<textarea ${common} rows="2">${escapeHtml(JSON.stringify(val))}</textarea>`;
  else control=`<input ${common} type="${field.secret?'password':['int','float'].includes(field.type)?'number':'text'}" ${field.secret?'autocomplete="new-password"':''} ${field.type==='float'?'step="any"':''} value="${escapeHtml(val)}" placeholder="${field.secret&&field.configured?'Уже сохранён · оставь пустым для сохранения':''}">`;
  return `<div class="field ${field.secret?'secret':''}"><label for="${id}">${escapeHtml(title)}${field.secret?`<span class="muted">${state.clearSecrets.has(field.key)?'Будет удалён':field.configured?'Сохранён':'Не задан'}</span>`:''}</label><div class="${field.secret?'secret-input':''}">${control}${field.secret?`<button type="button" class="button ghost small" data-action="clear-secret" data-key="${escapeHtml(field.key)}" ${disabled?'disabled':''}>${state.clearSecrets.has(field.key)?'Отменить':'Очистить'}</button>`:''}</div>${help[field.key]?`<div class="field-help">${help[field.key]}</div>`:''}</div>`;
}

function renderSettings() {
  const integrations=state.page==='integrations';
  const available=integrations?['telegram','discord','api']:['general','bot','timers'];
  let intro=integrations?'Уведомления, удалённое управление и данные твоего аккаунта.':'Параметры игры, эмулятора и производительности.';
  const advice=state.tab==='api'?'Укажи тег игрока и API-токен либо данные портала разработчика для автоматического обновления ключа.':state.tab==='telegram'?'Создай бота через @BotFather. Для управления укажи токен и свой ID пользователя.':state.tab==='discord'?'Укажи webhook для уведомлений. Для команд управления добавь токен бота и ID владельца.':'';
  const guided=state.step===1;
  const player=state.players[state.instance];
  const visibleFields=guided?['player_tag','developer_email','developer_password','api_token']:null;
  $('#content').innerHTML=heading(guided?'Подключи аккаунт или пропусти этот шаг':integrations?'Всё под контролем':'Настрой под себя',guided?'Вход загрузит твоих бойцов и текущие трофеи. Для ручного выбора нажми «Продолжить без API».':intro)+(guided?'':`<div class="pills">${available.map(section=>`<button data-action="tab" data-tab="${section}" class="${state.tab===section?'active':''}">${sections[section]}</button>`).join('')}</div>`)+
    (guided&&player?`<div class="notice success">Аккаунт подключён · доступно бойцов: ${player.brawlers?.length || 0}.</div>`:'')+
    (active()?'<div class="notice">Чтобы изменить настройки, сначала останови этот экземпляр.</div>':'')+(advice?`<div class="notice">${advice}</div>`:'')+
    `<form id="settings-form" class="panel"><div class="panel-heading"><h2>${sections[state.tab]}</h2><small>Настройки · ${instanceName(state.instance)}</small></div><div class="panel-body settings-grid">${state.fields.map((field,index)=>!visibleFields||visibleFields.includes(field.key)?fieldHtml(field,index):'').join('')}</div><div class="form-footer"><span class="muted">Пустые поля токенов и паролей сохраняют прежние значения.</span><div class="inline"><button class="button secondary" ${active()||state.accountBusy?'disabled':''}>Сохранить изменения</button>${state.tab==='api'?`<button type="button" class="button primary" data-action="load-player" ${active()||state.accountBusy?'disabled':''}>Войти и загрузить бойцов</button>`:''}</div></div></form>`+
    (guided?'<div class="setup-links"><a href="#integrations">Дополнительные настройки API и интеграций</a></div>':'');
  $('#settings-form').addEventListener('submit',event=>{event.preventDefault();safely(async()=>{
    if(!await saveSettings())return;renderSettings();await refreshInstances();toast('Настройки сохранены.');
  });});
}

async function saveSettings() {
  const instance=state.instance,tab=state.tab,view=state.requestId,values={};
  state.fields.forEach((field,index)=>{
    const input=$(`#field-${index}`);
    if(!input || field.key==='pyla_version') return;
    values[field.key]=field.type==='bool'?input.checked:field.type==='list'?JSON.parse(input.value):['int','float'].includes(field.type)?Number(input.value):input.value;
  });
  const changedAccount=tab==='api'&&Object.entries(values).some(([key,value])=>key==='player_tag'?value!==state.fields.find(field=>field.key===key)?.value:['developer_email','developer_password','api_token'].includes(key)&&Boolean(value));
  const response=await api(`/api/instances/${instance}/settings/${tab}`,'PUT',{values,clear_secrets:[...state.clearSecrets]});
  if(changedAccount || state.clearSecrets.size) delete state.players[instance];
  if(instance!==state.instance || tab!==state.tab || view!==state.requestId) return false;
  state.fields=response.fields;state.clearSecrets.clear();
  // Clear typed credentials after saving; retain the saved-state placeholders.
  state.fields.forEach((field,index)=>{const input=$(`#field-${index}`);if(field.secret&&input){input.value='';input.placeholder=field.configured?'Уже сохранён · оставь пустым для сохранения':'';}});
  return true;
}

async function renderPage() {
  await renderPageContent();updateSetup();
}

async function renderPageContent() {
  const requestId=++state.requestId;
  state.step=PylaSetup.stepFor(location.hash);
  state.page=state.step>=0?['dashboard','integrations','queue','review'][state.step]:location.hash.slice(1) in titles?location.hash.slice(1):'dashboard';
  if(state.step===1) state.tab='api';
  if(state.step===0 && state.devices===null) {state.devices=(await api('/api/devices')).devices;if(requestId!==state.requestId)return;}
  document.title=`${titles[state.page]} · PylaAI Biomistik`;
  $('#page-title').textContent=titles[state.page];
  document.querySelectorAll('[data-page]').forEach(link=>link.classList.toggle('active',link.dataset.page===state.page));
  if(state.page==='review') {
    const response=await api(endpoint('queue'));if(requestId!==state.requestId)return;state.rows=response.queue;
    if(state.devices===null){state.devices=(await api('/api/devices')).devices;if(requestId!==state.requestId)return;}
    $('#content').innerHTML=heading('Проверь и запускай','Бот начнёт играть только после нажатия «Запустить бота».')+
      (!setupContext().device?'<div class="notice">Устройство не подключено. Вернись к первому шагу и выбери эмулятор.</div>':'')+
      `<section class="panel"><div class="panel-heading"><h2>Параметры запуска</h2></div><div class="panel-body"><p>Эмулятор: <strong>${escapeHtml(current()?.emulator || 'Не выбран')}</strong> · порт ${escapeHtml(current()?.port || '—')}</p><p>Аккаунт: ${state.players[state.instance]?'подключён, трофеи загружены':'ручной выбор бойцов'}</p><div class="review-roster">${state.rows.map(row=>`<div class="review-brawler">${portrait(row.brawler)}<div><strong>${escapeHtml(displayName(row.brawler))}</strong><small>${row.type==='wins'?'Победы':'Трофеи'}: ${row[row.type]} → ${row.push_until}</small></div></div>`).join('') || '<p>Очередь пуста. Вернись к выбору бойцов.</p>'}</div></div></section><div class="setup-links"><a href="#settings">Дополнительные настройки</a><a href="#playstyles">Выбрать стиль игры</a></div>`;
    return;
  }
  if(state.page==='dashboard') return renderDashboard();
  if(state.page==='queue') {
    const response=await api(endpoint('queue')); if(requestId!==state.requestId) return;
    state.rows=response.queue; return renderQueue();
  }
  if(['settings','integrations'].includes(state.page)) {
    const allowed=state.page==='settings'?['general','bot','timers']:['telegram','discord','api'];
    if(!allowed.includes(state.tab)) state.tab=allowed[0];
    const response=await api(endpoint(`settings/${state.tab}`)); if(requestId!==state.requestId) return;
    state.fields=response.fields;state.clearSecrets.clear();return renderSettings();
  }
  if(state.page==='playstyles') {
    const response=await api(endpoint('playstyles')); if(requestId!==state.requestId) return;
    $('#content').innerHTML=heading('Свой характер игры','Выбирай поведение для следующего запуска.')+`<div class="playstyle-grid">${response.playstyles.map(style=>`<article class="style-card ${style.active?'selected':''}"><span class="badge ${style.active?'purple':''}">${style.active?'Выбран':'Стиль игры'}</span><h3>${escapeHtml(style.name.replace(/\.pyla$/,''))}</h3><p>Поведение движения и атаки для твоих бойцов.</p><button class="button ${style.active?'ghost':'primary'} small" data-action="playstyle" data-name="${escapeHtml(style.name)}" ${style.active||active()?'disabled':''}>${style.active?'Активный стиль':'Выбрать стиль'}</button></article>`).join('') || empty('Стили не найдены','Добавь файлы .pyla в папку playstyles.')}</div>`;
  }
  if(state.page==='history') {
    const response=await api(endpoint('history')); if(requestId!==state.requestId) return;
    const rows=Object.entries(response.history).filter(([key,value])=>key!=='total'&&value&&typeof value==='object'&&!Array.isArray(value));
    $('#content').innerHTML=heading('Каждый матч на счету','Результаты, сохранённые ботом для этого экземпляра.')+`<section class="panel"><div class="panel-heading"><h2>Статистика бойцов</h2><button class="link-button" data-action="reload">Обновить ↻</button></div>${rows.length?`<div class="table-wrap"><table><thead><tr><th>БОЕЦ</th><th>ПОБЕДЫ</th><th>ПОРАЖЕНИЯ</th><th>НИЧЬИ</th></tr></thead><tbody>${rows.map(([name,value])=>`<tr><td class="brawler-name"><span class="brawler-cell">${portrait(name)}${escapeHtml(displayName(name))}</span></td><td>${escapeHtml(value.victory??0)}</td><td>${escapeHtml(value.defeat??0)}</td><td>${escapeHtml(value.draw??0)}</td></tr>`).join('')}</tbody></table></div>`:empty('История ещё не началась','После первых матчей здесь появятся реальные результаты.')}</section>`;
  }
  if(state.page==='logs') {
    $('#content').innerHTML=heading('Всё, что происходит','Вывод текущего запуска. Обновляется автоматически.','<button class="button ghost small" data-action="download-logs">Скачать логи ↓</button>')+`<section class="panel"><div class="panel-heading"><h2>${instanceName(state.instance)}</h2><span class="badge">LIVE</span></div><pre class="terminal" id="log-output">Загрузка…</pre></section>`;
    await refreshLogs();
  }
}

async function refreshLogs() {
  const id=state.instance;
  const response=await api(endpoint('logs'));
  const output=$('#log-output');
  if(!output || id!==state.instance) return;
  const atBottom=output.scrollTop+output.clientHeight>=output.scrollHeight-40;
  output.textContent=response.lines.length?response.lines.join('\n'):'Пока нет сообщений. После запуска здесь появятся логи бота.';
  if(atBottom) output.scrollTop=output.scrollHeight;
}

async function selectInstance(id) {
  state.instance=Number(id); state.tab=state.page==='integrations'?'telegram':'general';
  updateChrome(); await renderPage();
}
async function addInstance() {
  const id=Array.from({length:99},(_,i)=>i+1).find(id=>!state.instances.some(item=>item.instance===id));
  if(!id) throw new Error('Достигнут лимит экземпляров.');
  await api('/api/instances','POST',{instance:id}); await refreshInstances(); await selectInstance(id);
  toast('Экземпляр создан. Выбери для него отдельный эмулятор.');
}

$('#instance-select').addEventListener('change',event=>safely(()=>selectInstance(event.target.value)));
$('#add-instance').addEventListener('click',()=>safely(addInstance));
$('#setup-navigation').addEventListener('click',event=>{
  const button=event.target.closest('[data-setup]');if(!button||button.disabled)return;
  safely(async()=>{
    if(button.dataset.setup==='back') {location.hash=PylaSetup.routes[state.step-1];return;}
    if(button.dataset.setup==='start') {
      if(!PylaSetup.canStart(setupContext())) throw new Error('Проверь эмулятор и очередь бойцов.');
      await startRuntime();return;
    }
    const step=state.step,view=state.requestId;
    state.busy=true;updateChrome();
    try {
      if(step===1&&!await saveSettings())return;
      if(view!==state.requestId)return;
      const next=PylaSetup.next(step,setupContext());if(next)location.hash=next;
    } finally {state.busy=false;updateChrome();}
  });
});
for(const [id,action] of [['start-bot','start'],['pause-bot','pause'],['stop-bot','stop']]) {
  $(`#${id}`).addEventListener('click',()=>safely(async()=>{
    if(action==='start'&&current()?.state!=='paused') {location.hash='setup-review';return;}
    state.busy=true;updateChrome();
    try {await api(endpoint(`runtime/${action==='start'&&current()?.state==='paused'?'resume':action}`),'POST');await refreshInstances();await renderPage();}
    finally {state.busy=false;updateChrome();}
  }));
}
$('#content').addEventListener('click',event=>{
  const button=event.target.closest('[data-action]');if(!button || button.disabled) return;
  safely(async()=>{
    const action=button.dataset.action,index=Number(button.dataset.index);
    if(action==='scan') {button.disabled=true;try{state.devices=(await api('/api/devices')).devices;renderDashboard();updateSetup();}finally{button.disabled=false;}}
    if(action==='device') {await api(endpoint('device'),'POST',{serial:button.dataset.serial});await refreshInstances();renderDashboard();toast('Эмулятор выбран.');}
    if(action==='select-instance') await selectInstance(button.dataset.id);
    if(action==='add-instance') await addInstance();
    if(action==='pick-brawler') setBrawler(button.dataset.name);
    if(action==='load-player') await loadAccount();
    if(action==='remove') await saveQueue(state.rows.filter((_,i)=>i!==index));
    if(action==='up'||action==='down') {const rows=[...state.rows],next=index+(action==='up'?-1:1);[rows[index],rows[next]]=[rows[next],rows[index]];await saveQueue(rows);}
    if(action==='push-all'||action==='sync') {
      if(action==='push-all' && state.rows.length && !confirm('Заменить текущую очередь бойцами из твоего аккаунта ниже выбранной цели?')) return;
      button.disabled=true;const oldText=button.textContent;button.textContent='Загружаем…';
      const instance=state.instance;
      try {const target=Number($('#push-all-target').value);const response=await api(endpoint(`queue/${action}`),'POST',{target});if(instance!==state.instance)return;state.rows=response.queue;await refreshInstances();if(state.page==='queue')renderQueue();toast('Трофеи загружены из API.');}
      finally {button.disabled=false;button.textContent=oldText;}
    }
    if(action==='tab') {state.tab=button.dataset.tab;await renderPage();}
    if(action==='clear-secret') {
      const key=button.dataset.key;
      if(state.clearSecrets.has(key)) state.clearSecrets.delete(key);else state.clearSecrets.add(key);
      button.textContent=state.clearSecrets.has(key)?'Отменить':'Очистить';
      button.closest('.field').querySelector('label .muted').textContent=state.clearSecrets.has(key)?'Будет удалён':'Без изменений';
    }
    if(action==='playstyle') {await api(endpoint('playstyles/activate'),'POST',{name:button.dataset.name});await renderPage();toast('Стиль выбран.');}
    if(action==='reload') await renderPage();
    if(action==='download-logs') {
      const lines=(await api(endpoint('logs'))).lines;
      const url=URL.createObjectURL(new Blob([lines.join('\n')],{type:'text/plain;charset=utf-8'}));
      const link=document.createElement('a');link.href=url;link.download=`pyla-instance-${state.instance}.log`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
  });
});
$('#content').addEventListener('change',event=>{
  const input=event.target;if(!input.dataset.field) return;
  safely(async()=>{
    const rows=state.rows.map(row=>({...row}));
    rows[Number(input.dataset.index)][input.dataset.field]=input.type==='checkbox'?input.checked:Number(input.value);
    try {await saveQueue(rows);}catch(error){renderQueue();throw error;}
  });
});
window.addEventListener('hashchange',()=>safely(renderPage));

(async()=>{
  try {
    const data=await api('/api/bootstrap');state.instances=data.instances;state.catalog=data.brawlers;state.details=data.catalog || [];
    $('#version-label').textContent=`Biomistik · ядро ${data.version || 'PylaAI'}`;
    updateChrome();await renderPage();
    let polling=false;
    setInterval(async()=>{
      if(polling||document.hidden) return;polling=true;
      try {await refreshInstances();if(state.page==='logs') await refreshLogs();if(state.page==='queue'&&active())await renderPage();}
      catch(error){$('#runtime-label').textContent='Нет связи с панелью';$('#runtime-dot').className='status-dot error';}
      finally{polling=false;}
    },2500);
  } catch(error) {$('#content').innerHTML=empty('Не удалось открыть панель',escapeHtml(error.message));toast(error.message,true);}
})();
