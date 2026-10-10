// ===== 状态 =====
let state = {
  view: 'rec',
  goal: 'lose',        // lose 减脂 / keep 维持 / gain 增肌
  daily: 2000,
  eaten: [],           // [{id,name,kcal,p,f,c}]
  picked: [],
  star: 0,
  drafts: {},
  imageB64: null
};

const GOALS = {
  lose: { label: '减脂', kcalRate: 0.75, p: 1.6, f: 0.7, tip: '优先零卡饮品 + 高蛋白单品，避免油炸主食叠加' },
  keep: { label: '维持', kcalRate: 1.0,  p: 1.2, f: 0.9, tip: '均衡即可，注意蔬菜与蛋白质搭配' },
  gain: { label: '增肌', kcalRate: 1.15, p: 2.0, f: 1.0, tip: '加份量、加蛋白，训练后 2 小时内吃完' }
};

let REVIEWS = [
  { id: 'r1', name: '阿哲', avatar: '🧑‍🎓', star: 5, time: '2 小时前', tags: ['性价比高', '牛肉很实在'], text: '巨无堡配无糖可乐，一餐 552 大卡，增肌日也能接受。芝士化得刚好，不会腻。', item: '巨无霸', likes: 42, liked: false },
  { id: 'r2', name: 'Nina', avatar: '👩', star: 3, time: '昨天', tags: ['偏咸', '薯条软了'], text: '薯条到手有点软，不过酸辣酱配麦辣堡还是很顶。多给了一份酸辣酱，店员态度不错。', item: '麦辣鸡腿汉堡', likes: 17, liked: false },
  { id: 'r3', name: '大熊', avatar: '🐻', star: 5, time: '3 天前', tags: ['健身友好', '高蛋白'], text: '麦乐鸡 10 块 30g 蛋白，加中薯练前碳水，这套是我固定搭配。', item: '麦乐鸡（10块）', likes: 63, liked: false },
  { id: 'r4', name: '柚子茶', avatar: '🍑', star: 4, time: '1 周前', tags: ['甜品不腻'], text: '新地比想象中清爽，甜度刚好。减肥期想吃甜的可以偶尔换一下。', item: '新地（草莓/巧克力）', likes: 9, liked: false }
];

const TAG_POOL = ['性价比高', '好吃', '健身友好', '偏咸', '偏甜', '油炸', '分量足', '包装差', '服务好', '高蛋白', '低卡', '辣'];

function load() {
  try {
    const s = localStorage.getItem('mcf_state');
    if (s) state = Object.assign(state, JSON.parse(s));
    const r = localStorage.getItem('mcf_rev');
    if (r) REVIEWS = JSON.parse(r);
  } catch (e) {}
}
function save() {
  localStorage.setItem('mcf_state', JSON.stringify({ goal: state.goal, daily: state.daily, eaten: state.eaten }));
  localStorage.setItem('mcf_rev', JSON.stringify(REVIEWS));
}

// ===== 营养计算 =====
function cartTotals(list) {
  return list.reduce((a, i) => ({
    kcal: a.kcal + i.kcal, p: a.p + i.p, f: a.f + i.f, c: a.c + i.c
  }), { kcal: 0, p: 0, f: 0, c: 0 });
}
function budget() {
  const g = GOALS[state.goal];
  const t = cartTotals(state.eaten);
  return {
    kcal: Math.round(state.daily * g.kcalRate) - t.kcal,
    p: Math.round(70 * g.p) - t.p,
    f: Math.round(60 * g.f) - t.f
  };
}

// ===== 推荐引擎（内容推荐 + 目标过滤）=====
function recommend() {
  const b = budget();
  const scored = MENU.map(i => {
    let s = 0;
    if (i.kcal <= Math.max(b.kcal, 150)) s += 40;            // 热量塞得下
    if (state.goal === 'lose') {
      if (i.tags.includes('零卡')) s += 35;
      if (i.tags.includes('低卡')) s += 30;
      if (i.tags.includes('高蛋白')) s += 28;
      if (i.p >= 20) s += 20;
      if (i.tags.includes('高热量')) s -= 22;
      if (i.tags.includes('含糖') || i.tags.includes('高糖')) s -= 25;
      if (i.tags.includes('油炸')) s -= 12;
    } else if (state.goal === 'gain') {
      if (i.tags.includes('经典')) s += 18;
      if (i.kcal >= 450) s += 25;
      if (i.p >= 25) s += 22;
      if (i.tags.includes('零卡')) s -= 30;
    } else {
      s += 20 - Math.abs(i.kcal - 450) / 20;
      if (i.p >= 20) s += 12;
    }
    // 社区热度加成
    const rv = REVIEWS.filter(r => r.item === i.name);
    s += rv.length * 6 + rv.reduce((a, r) => a + r.star, 0) * 1.2;
    return { ...i, score: Math.round(s) };
  }).sort((a, b2) => b2.score - a.score);
  return scored;
}

function comboSet() {
  const scored = recommend();
  const main = scored.filter(i => i.cat === '汉堡')[0] || scored[0];
  const side = scored.filter(i => i.cat === '小食')[0];
  const drink = scored.filter(i => i.cat === '饮品' && i.tags.includes('零卡'))[0]
              || scored.filter(i => i.cat === '饮品')[0];
  const set = [main, side, drink].filter(Boolean);
  return { set, total: cartTotals(set), main, drink };
}

// ===== AI 识别（模拟：按文件名/随机打分匹配菜品）=====
const CAMERA_HINTS = ['巨无堡 burger.png', '薯条 fries.jpg', '麦乐鸡 chicken.jpg', '可乐 cola.jpg', '甜品 sundae.png'];
function askAI() {
  state.view = 'recs';
  render();
  setTimeout(() => { state.imageB64 = null; render(); }, 2600);
}
function recognize(name) {
  // 真实项目：这里换成后端调 OpenAI Vision / 阿里云 CV；前端保留接口形状
  const key = (name || '').toLowerCase();
  let guess = null;
  if (/burger|堡/.test(key)) guess = MENU.find(i => i.id === 'm2');
  if (/fries|薯/.test(key)) guess = MENU.find(i => i.id === 's1');
  if (/chicken|鸡/.test(key)) guess = MENU.find(i => i.id === 's3');
  if (/cola|可乐/.test(key)) guess = MENU.find(i => i.id === 'd2');
  if (/sundae|甜品|ice/.test(key)) guess = MENU.find(i => i.id === 'ds1');
  return guess || recommend()[0];
}

// ===== 渲染 =====
const $ = s => document.querySelector(s);
function tab(v, btn) {
  state.view = v;
  document.querySelectorAll('nav button').forEach(b => b.classList.toggle('on', b === btn));
  render();
  window.scrollTo(0, 0);
}

function render() {
  const app = $('#app');
  if (state.view === 'rec') app.innerHTML = vRec();
  else if (state.view === 'recs') app.innerHTML = vRecs();
  else if (state.view === 'write') app.innerHTML = vWrite();
  else if (state.view === 'feed') app.innerHTML = vFeed();
  else if (state.view === 'board') app.innerHTML = vBoard();
  bind();
}

function kcalBar(i) {
  const pct = Math.min(100, i.kcal / 6);
  const color = i.kcal >= 450 ? '#d62300' : i.kcal >= 250 ? '#f5a623' : '#3aaa6a';
  return `<div class="bar"><i style="width:${pct}%;background:${color}"></i></div>`;
}

function vRec() {
  const b = budget();
  const g = GOALS[state.goal];
  const c = comboSet();
  const list = recommend().slice(0, 12);
  return `
  <div class="card">
    <h2>今日目标 & 预算</h2>
    <div class="flex">
      ${Object.entries(GOALS).map(([k, v]) => `
        <button class="act ${state.goal === k ? '' : 'ghost'}" onclick="setGoal('${k}')">${v.label}</button>`).join('')}
    </div>
    <p class="pf">目标热量 ${Math.round(state.daily * g.kcalRate)} kcal / 蛋白 ${Math.round(70 * g.p)}g｜剩余可摄入：<b style="color:${b.kcal < 0 ? '#d62300' : '#3aaa6a'}">${b.kcal} kcal</b>，蛋白 ${b.p}g。${g.tip}</p>
  </div>

  <div class="card">
    <h2>🍱 为你配的一餐（${g.label}）</h2>
    <div class="rec">
      <div style="font-size:32px">${c.set.map(x => x.img).join(' ')}</div>
      <div style="font-weight:700;margin:8px 0">${c.set.map(x => x.name).join(' + ')}</div>
      <div class="kcal">合计 <b>${c.total.kcal}</b> kcal｜蛋白 ${c.total.p}g｜脂肪 ${c.total.f}g｜碳水 ${c.total.c}g｜约 ¥${c.set.reduce((a, x) => a + x.price, 0)}</div>
      <div style="margin-top:10px"><button class="act" onclick='addCombo(${JSON.stringify(c.set.map(x => x.id))})'>加入今日饮食</button></div>
    </div>
  </div>

  ${state.eaten.length ? `<div class="card">
    <h2>今日已记录</h2>
    ${state.eaten.map((x, i) => `<div class="flex" style="border-bottom:1px solid #f0f0f0;padding:8px 0">
      <span>${x.img || ''} ${x.name} · ${x.kcal}kcal</span>
      <button class="like" onclick="removeEaten(${i})">移除</button></div>`).join('')}
    <p class="pf">累计 ${cartTotals(state.eaten).kcal} kcal / 蛋白 ${cartTotals(state.eaten).p}g</p>
  </div>` : ''}

  <div class="card">
    <h2>🔥 智能推荐菜单</h2>
    <div class="grid">
      ${list.map(i => `<div class="item ${state.picked.includes(i.id) ? 'sel' : ''}" onclick="pick('${i.id}')">
        <div class="emoji">${i.img}</div>
        <div class="nm">${i.name}</div>
        <div class="kcal">${i.kcal} kcal · ¥${i.price} · 蛋白 ${i.p}g</div>
        ${kcalBar(i)}
      </div>`).join('')}
    </div>
    ${state.picked.length ? `<div style="margin-top:12px"><button class="act" onclick="addPicked()">把勾选的 ${state.picked.length} 项加入饮食</button></div>` : ''}
  </div>`;
}

function vRecs() {
  const guess = state.imageB64 ? recognize(state.imageB64) : null;
  return `
  <div class="card">
    <h2>📷 拍照识别营养</h2>
    <p class="pf">上传图片后由后端调用视觉大模型识别菜品（演示版用文件名关键词模拟，可改成真接口）。</p>
    <input type="file" accept="image/*" onchange="onImg(this)">
    <div class="grid" style="margin:10px 0">
      ${CAMERA_HINTS.map(h => `<div class="item" onclick="demoImg('${h}')"><div class="emoji">🖼️</div><div class="nm" style="font-size:12px">${h}</div></div>`).join('')}
    </div>
    <p class="pf">或直接在上面选一张示例图演示识别流程。</p>
  </div>
  ${guess ? detailCard(guess, true) : ''}`;
}

function detailCard(i, withAdd) {
  return `<div class="card">
    <h2>识别结果</h2>
    <div class="flex" style="align-items:flex-start;gap:14px">
      <div style="font-size:52px">${i.img}</div>
      <div style="flex:3">
        <div style="font-weight:800;font-size:17px">${i.name}</div>
        <div class="kcal">${i.cat} · ¥${i.price}</div>
        <div style="margin-top:6px">${i.tags.map(t => `<span class="pill">${t}</span>`).join('')}</div>
      </div>
    </div>
    <div class="kpi" style="margin-top:14px">
      <div><b>${i.kcal}</b>热量 kcal</div>
      <div><b>${i.p}g</b>蛋白质</div>
      <div><b>${i.f}g</b>脂肪</div>
      <div><b>${i.c}g</b>碳水</div>
    </div>
    ${withAdd ? `<button class="act" onclick='addOne("${i.id}")'>加入今日饮食</button>
    <button class="act ghost" onclick="goWrite('${i.name}')">为它写评价</button>` : ''}
  </div>`;
}

function vWrite() {
  const s = state.drafts;
  return `
  <div class="card">
    <h2>写评价</h2>
    <input id="wItem" placeholder="菜名（选填，会自动带入营养）" value="${s.item || ''}" oninput="dItem(this.value)">
    <label class="pf">评分</label>
    <div class="stars" onclick="setStar(event)">
      ${[1, 2, 3, 4, 5].map(n => `<span data-n="${n}" class="${state.star >= n ? '' : 'off'}">★</span>`).join('')}
    </div>
    <div class="grid" style="margin:12px 0">
      ${TAG_POOL.map(t => `<div class="item ${(s.tags || []).includes(t) ? 'sel' : ''}" style="padding:8px;text-align:center;font-size:13px" onclick="dTag('${t}')">${t}</div>`).join('')}
    </div>
    <textarea rows="4" id="wText" placeholder="口味、分量、和谁一起吃…" oninput="dText(this.value)">${s.text || ''}</textarea>
    <button class="act" onclick="submitReview()">发布评价</button>
    <p class="pf">发布前经内容审核（敏感词 / 广告 / 攻击性言论自动拦截）。</p>
  </div>`;
}

function vFeed() {
  const arr = [...REVIEWS].sort((a, b) => (b.likes + b.star * 5) - (a.likes + a.star * 5));
  const m = MENU.find(i => i.name === s0(arr));
  function s0(a) { return a[0].item; }
  return `
  <div class="card">
    <h2>🔥 社区热榜</h2>
    <p class="pf">按「点赞 + 评分」加权排序。${m ? `当前第一名：<b>${m.name}</b>（${m.kcal} kcal）` : ''}</p>
    <div class="grid">${recommend().slice(0, 5).map((i, n) => `<div class="item">
      <div class="nm"><span class="pill">TOP${n + 1}</span>${i.img} ${i.name}</div>
      <div class="kcal">${i.kcal} kcal · 蛋白 ${i.p}g · 均分 ${avg(i.name)}</div>
    </div>`).join('')}</div>
  </div>
  <div class="card"><h2>最新评价（${REVIEWS.length}）</h2>
  ${arr.map(r => `
    <div class="rv">
      <div class="hd2">
        <div><b>${r.avatar} ${r.name}</b> <span class="pill">${r.item}</span></div>
        <span class="kcal">${r.time}</span>
      </div>
      <div style="color:#ffc800">${'★'.repeat(r.star)}${'☆'.repeat(5 - r.star)}</div>
      <div style="margin:6px 0">${(r.tags || []).map(t => `<span class="pill">${t}</span>`).join('')}</div>
      <p>${r.text}</p>
      <button class="like ${r.liked ? 'on' : ''}" onclick="like('${r.id}')">👍 ${r.likes}</button>
    </div>`).join('')}
  </div>`;
}
function avg(name) {
  const r = REVIEWS.filter(x => x.item === name);
  if (!r.length) return '暂无';
  return (r.reduce((a, x) => a + x.star, 0) / r.length).toFixed(1) + ' 分';
}

function vBoard() {
  const byItem = {};
  REVIEWS.forEach(r => {
    byItem[r.item] = byItem[r.item] || { n: 0, s: 0, likes: 0, tags: {} };
    byItem[r.item].n++; byItem[r.item].s += r.star; byItem[r.item].likes += r.likes;
    (r.tags || []).forEach(t => byItem[r.item].tags[t] = (byItem[r.item].tags[t] || 0) + 1);
  });
  const rows = Object.entries(byItem).map(([k, v]) => ({ k, avg: v.s / v.n, ...v }));
  const low = rows.filter(r => r.avg < 4).sort((a, b) => a.avg - b.avg);
  const sug = [];
  if (low.some(r => r.tags['偏咸'])) sug.push('「偏咸」标签集中出现 → 建议复核薯条/酱料钠含量与加盐节点');
  if (low.some(r => r.tags['薯条软了'] || r.tags['包装差'])) sug.push('配送时长与酥脆度负相关 → 建议对炸物类设置「出锅 20 分钟内送达」承诺');
  if (REVIEWS.filter(r => r.tags.includes('健身友好')).length >= 2) sug.push('健身友好搭配被反复提及 → 建议官方上线「增肌套餐 / 减脂套餐」组合位');
  return `
  <div class="card">
    <h2>📊 品牌方数据看板</h2>
    <div class="kpi">
      <div><b>${REVIEWS.length}</b>评价总数</div>
      <div><b>${(REVIEWS.reduce((a, r) => a + r.star, 0) / (REVIEWS.length || 1)).toFixed(2)}</b>平均分</div>
      <div><b>${REVIEWS.reduce((a, r) => a + r.likes, 0)}</b>互动量</div>
    </div>
  </div>
  <div class="card">
    <h2>菜品口碑排行</h2>
    ${rows.sort((a, b) => b.avg - a.avg).map(r => `
      <div style="padding:8px 0;border-bottom:1px solid #f2f2f2">
        <div class="flex"><b>${r.k}</b><span style="flex:3;text-align:right">${r.avg.toFixed(1)} 分 · ${r.n} 条 · ${r.likes} 赞</span></div>
        <div class="bar"><i style="width:${r.avg / 5 * 100}%;background:#ffc800"></i></div>
      </div>`).join('')}
  </div>
  <div class="card">
    <h2>🤖 自动生成的改进建议</h2>
    ${sug.length ? sug.map(s => `<p style="padding:8px 0;border-bottom:1px dashed #eee">· ${s}</p>`).join('') : '<p class="pf">样本不足，暂无结论</p>'}
    <p class="pf">规则由 WorkBuddy 编排：标签聚合 → 阈值判断 → 生成可执行建议 → 回流菜单/研发。</p>
  </div>`;
}

// ===== 交互 =====
function setGoal(g) { state.goal = g; save(); render(); }
function pick(id) {
  const i = state.picked.indexOf(id);
  i >= 0 ? state.picked.splice(i, 1) : state.picked.push(id);
  render();
}
function addOne(id) { const i = MENU.find(x => x.id === id); state.eaten.push(i); save(); render(); }
function addPicked() { state.picked.forEach(id => state.eaten.push(MENU.find(x => x.id === id))); state.picked = []; save(); render(); }
function addCombo(ids) { ids.forEach(id => state.eaten.push(MENU.find(x => x.id === id))); save(); render(); }
function removeEaten(i) { state.eaten.splice(i, 1); save(); render(); }
function onImg(el) {
  const f = el.files[0];
  if (!f) return;
  state.imageB64 = f.name;
  render();
}
function demoImg(n) { state.imageB64 = n; render(); }
function goWrite(name) { state.drafts.item = name; tab('write', document.querySelectorAll('nav button')[2]); }
function dItem(v) { state.drafts.item = v; }
function dText(v) { state.drafts.text = v; }
function dTag(t) {
  state.drafts.tags = state.drafts.tags || [];
  const i = state.drafts.tags.indexOf(t);
  i >= 0 ? state.drafts.tags.splice(i, 1) : state.drafts.tags.push(t);
  render();
}
function setStar(e) {
  state.star = +e.target.dataset.n;
  document.querySelectorAll('.stars span').forEach(s => s.classList.toggle('off', +s.dataset.n > state.star));
  state.drafts.star = state.star;
}
const BAD = ['最好吃', '第一', '国家级', '代购', '加微信', '免费送', '点击链接', '傻'];
function submitReview() {
  const s = state.drafts;
  if (!s.text || !s.text.trim()) return alert('写点内容再发布吧');
  if (!state.star) return alert('先打个分');
  if (BAD.some(w => s.text.includes(w))) return alert('审核未通过：内容含违规/广告词，请修改后重新发布');
  REVIEWS.unshift({
    id: 'r' + Date.now(), name: '我', avatar: '😀', star: state.star,
    time: '刚刚', tags: s.tags || [], text: s.text, item: s.item || '自定义餐点', likes: 0, liked: false
  });
  state.drafts = {}; state.star = 0; state.view = 'feed'; save(); render();
}
function like(id) {
  const r = REVIEWS.find(x => x.id === id);
  r.liked = !r.liked; r.likes += r.liked ? 1 : -1;
  save(); render();
}
function bind() {
  const t = document.getElementById('wText');
  if (t && !state.drafts.text) t.addEventListener('input', e => state.drafts.text = e.value);
}
load();
render();