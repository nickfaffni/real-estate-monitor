
const { useState, useEffect, useMemo, useRef } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "density": "compact",
  "view": "grid",
  "showMarketing": false
}/*EDITMODE-END*/;

/* ---------- Fake data ---------- */
// Listings loaded from API
let LISTINGS = [];

const BOOTSTRAP = (()=>{ try { return JSON.parse(document.getElementById('__bootstrap').textContent); } catch(e) { return {}; } })();
const STATS = Object.assign({
  total: 0, newToday: 0, hotDeals: 0, avgScore: 0,
  trend7d: [],
  sourcesBreakdown: [{k:"Yad2",v:0,c:"var(--ink)"},{k:"Madlan",v:0,c:"var(--cool)"},{k:"FB",v:0,c:"var(--warn)"}],
}, BOOTSTRAP.stats || {});

/* ---------- Editmode plumbing ---------- */
function useTweaks(){
  const [state, setState] = useState(TWEAK_DEFAULTS);
  const [active, setActive] = useState(false);
  useEffect(()=>{
    const onMsg = e => {
      const d = e.data || {};
      if(d.type==='__activate_edit_mode') setActive(true);
      if(d.type==='__deactivate_edit_mode') setActive(false);
    };
    window.addEventListener('message', onMsg);
    try { window.parent.postMessage({type:'__edit_mode_available'}, '*'); } catch(e){}
    return ()=>window.removeEventListener('message', onMsg);
  },[]);
  useEffect(()=>{
    document.body.dataset.density = state.density;
  },[state.density]);
  const set = (patch) => {
    setState(s=>({...s,...patch}));
    try { window.parent.postMessage({type:'__edit_mode_set_keys', edits:patch},'*'); }catch(e){}
  };
  return { state, set, active };
}

/* ---------- Little atoms ---------- */
const Rule = ({label, right}) => (
  <div style={{display:'flex',alignItems:'center',gap:12, padding:'10px 0', borderBottom:'1px solid var(--line)'}}>
    <span className="mono" style={{fontSize:11, letterSpacing:'0.08em', textTransform:'uppercase', color:'var(--muted)'}}>{label}</span>
    <span style={{flex:1, borderTop:'1px dashed var(--line)', transform:'translateY(-1px)'}}/>
    {right && <span className="mono" style={{fontSize:11, color:'var(--ink-2)'}}>{right}</span>}
  </div>
);

const Pill = ({children, tone='ink', ...rest}) => {
  const tones = {
    ink:{bg:'transparent', fg:'var(--ink)', bd:'var(--line-2)'},
    solid:{bg:'var(--ink)', fg:'var(--paper)', bd:'var(--ink)'},
    accent:{bg:'var(--accent)', fg:'var(--accent-ink)', bd:'var(--accent)'},
    ghost:{bg:'transparent', fg:'var(--muted)', bd:'var(--line)'},
  };
  const t = tones[tone]||tones.ink;
  return <span {...rest} style={{display:'inline-flex',alignItems:'center',gap:6, padding:'4px 10px', borderRadius:999, background:t.bg, color:t.fg, border:`1px solid ${t.bd}`, fontSize:12, fontWeight:500, ...rest.style}}>{children}</span>;
};

/* Deal score dial — the hero element on every card */
function ScoreDial({ score, size=84, strokeWidth=8, showLabel=true }){
  const r = (size-strokeWidth)/2;
  const c = 2*Math.PI*r;
  const pct = Math.max(0,Math.min(100,score))/100;
  const dash = c*pct;
  const tier = score>=80 ? 'excellent' : score>=65 ? 'good' : score>=50 ? 'fair' : 'low';
  const tierColor = tier==='excellent' ? 'var(--accent)' : tier==='good' ? 'var(--ink)' : tier==='fair' ? 'var(--warn)' : 'var(--muted)';
  return (
    <div style={{position:'relative', width:size, height:size}}>
      <svg width={size} height={size} style={{transform:'rotate(-90deg)'}}>
        <circle cx={size/2} cy={size/2} r={r} stroke="var(--line)" strokeWidth={strokeWidth} fill="none"/>
        <circle cx={size/2} cy={size/2} r={r} stroke={tierColor} strokeWidth={strokeWidth} fill="none"
          strokeDasharray={`${dash} ${c}`} strokeLinecap="butt"/>
      </svg>
      <div style={{position:'absolute',inset:0, display:'grid',placeItems:'center', textAlign:'center', lineHeight:1}}>
        <div>
          <div className="serif" style={{fontSize:size*0.44, letterSpacing:'-0.02em'}}>{Math.round(score)}</div>
          {showLabel && <div className="mono" style={{fontSize:9, color:'var(--muted)', textTransform:'uppercase', letterSpacing:'0.12em', marginTop:2}}>score</div>}
        </div>
      </div>
    </div>
  );
}

/* Generated artwork for photo placeholder — warm gradient + dwelling silhouette */
function SmartPhoto({image, height=220, seed='warm'}){
  if(image && (image.startsWith('http') || image.startsWith('/'))){
    return <img src={image} alt="" style={{width:'100%', height, objectFit:'cover', display:'block'}}/>;
  }
  return <PhotoBlock seed={seed} height={height}/>;
}

function PhotoBlock({seed='warm', height=220}){
  const palettes = {
    warm:['#E6C9A0','#C9986A','#6B4B2A'],
    cream:['#EDE3CF','#D4B98E','#6F5A3A'],
    stone:['#CFC9BA','#9A9486','#3D3A33'],
    olive:['#B5B58D','#7F8663','#2E3123'],
    rust:['#E0A077','#A85F3C','#3A1F14'],
    sage:['#BFCFAF','#7E9A79','#2A3B2F'],
    sand:['#EBD9B4','#B89B6A','#5A4729'],
    clay:['#D7A58A','#A06A54','#3A1E17'],
    moss:['#9FA98B','#6A7558','#22291E'],
  };
  const p = palettes[seed]||palettes.warm;
  return (
    <div style={{position:'relative', height, background:`linear-gradient(135deg, ${p[0]} 0%, ${p[1]} 60%, ${p[2]} 100%)`, overflow:'hidden'}}>
      {/* sun */}
      <div style={{position:'absolute',top:'18%',left:'70%',width:64,height:64, borderRadius:'50%', background:'rgba(255,255,255,0.25)', filter:'blur(1px)'}}/>
      {/* buildings */}
      <svg viewBox="0 0 320 120" preserveAspectRatio="none" style={{position:'absolute',bottom:0,left:0,right:0, width:'100%', height:'55%', display:'block', opacity:0.55}}>
        <rect x="10" y="40" width="40" height="80" fill={p[2]}/>
        <rect x="54" y="60" width="30" height="60" fill={p[2]}/>
        <rect x="88" y="20" width="56" height="100" fill={p[2]}/>
        <rect x="148" y="50" width="40" height="70" fill={p[2]}/>
        <rect x="192" y="34" width="48" height="86" fill={p[2]}/>
        <rect x="244" y="62" width="30" height="58" fill={p[2]}/>
        <rect x="278" y="44" width="34" height="76" fill={p[2]}/>
      </svg>
      <div style={{position:'absolute',inset:0,background:'radial-gradient(120% 60% at 50% 100%, rgba(0,0,0,0.25), transparent 60%)'}}/>
    </div>
  );
}

/* Feature chip row */
const FEATURE_META = {
  mamad:{he:'ממ״ד', en:'Safe room', glyph:'▣'},
  parking:{he:'חניה', en:'Parking', glyph:'◫'},
  elevator:{he:'מעלית', en:'Elevator', glyph:'↑'},
  balcony:{he:'מרפסת', en:'Balcony', glyph:'◱'},
};

function Features({f}){
  const items = Object.keys(FEATURE_META).map(k=>({k, has:!!f[k], ...FEATURE_META[k]}));
  return (
    <div style={{display:'flex', gap:6, flexWrap:'wrap'}}>
      {items.map(i=>(
        <span key={i.k} title={`${i.en} ${i.has?'✓':'—'}`} style={{
          display:'inline-flex', alignItems:'center', gap:6,
          padding:'4px 10px', borderRadius:6,
          background: i.has ? 'var(--ink)' : 'transparent',
          color: i.has ? 'var(--paper)' : 'var(--muted)',
          border: `1px solid ${i.has ? 'var(--ink)' : 'var(--line-2)'}`,
          fontSize:11, letterSpacing:'0.02em',
          textDecoration: i.has ? 'none' : 'line-through',
          opacity: i.has ? 1 : 0.55,
        }}>
          <span className="mono" style={{fontSize:10}}>{i.glyph}</span>
          <span className="he">{i.he}</span>
        </span>
      ))}
    </div>
  );
}

function formatILS(n){
  if(n>=1_000_000) return `${(n/1_000_000).toFixed(2)}M ₪`;
  return `${n.toLocaleString('en-US')} ₪`;
}

/* ---------- Marketing top ---------- */
function Marketing({onGotoDash}){
  return (
    <section style={{borderBottom:'1px solid var(--line)', background:'var(--paper)'}}>
      {/* Top nav */}
      <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', padding:'20px 48px', borderBottom:'1px solid var(--line)'}}>
        <div style={{display:'flex', alignItems:'center', gap:10}}>
          <Logo/>
          <span className="mono" style={{fontSize:11, color:'var(--muted)', letterSpacing:'0.12em', textTransform:'uppercase'}}>v4.2 · local</span>
        </div>
        <nav style={{display:'flex', gap:24, alignItems:'center'}}>
          <a className="mono" style={{fontSize:13}}>how it works</a>
          <a className="mono" style={{fontSize:13}}>scoring</a>
          <a className="mono" style={{fontSize:13}}>sources</a>
          <a className="mono" style={{fontSize:13}}>docs</a>
          <button onClick={onGotoDash} style={{padding:'8px 14px', border:'1px solid var(--ink)', borderRadius:999, background:'var(--ink)', color:'var(--paper)', fontSize:13}}>Open dashboard →</button>
        </nav>
      </div>

      {/* Hero */}
      <div className="hero-grid" style={{padding:'56px 48px 36px', display:'grid', gridTemplateColumns:'1.2fr 1fr', gap:48}}>
        <div style={{minWidth:0}}>
          <div style={{display:'flex', gap:10, alignItems:'center', marginBottom:24}}>
            <Pill tone="ghost"><span style={{width:6, height:6, borderRadius:'50%', background:'var(--accent)', boxShadow:'0 0 0 3px color-mix(in oklch, var(--accent) 30%, transparent)'}}/> <span className="mono" style={{fontSize:11}}>live · scraping 3 sources</span></Pill>
            <Pill tone="ghost"><span className="mono" style={{fontSize:11}}>1,847 listings indexed</span></Pill>
          </div>
          <h1 className="serif" style={{fontSize:'clamp(44px, 6.8vw, 108px)', lineHeight:0.92, margin:0, letterSpacing:'-0.025em', overflowWrap:'break-word'}}>
            The apartment<br/>
            <span style={{fontStyle:'italic'}}>before</span> it<br/>
            hits your feed.
          </h1>
          <p style={{maxWidth:560, marginTop:28, fontSize:18, lineHeight:1.5, color:'var(--ink-2)'}}>
            Central Israel's new listings from <b>Yad2</b>, <b>Madlan</b> and <b>Facebook Marketplace</b>, scored
            against the neighborhood average, sorted by deal quality, delivered to your dashboard every fifteen minutes.
          </p>
          <div style={{display:'flex', gap:12, marginTop:32, alignItems:'center'}}>
            <button onClick={onGotoDash} style={{padding:'14px 20px', background:'var(--accent)', color:'var(--accent-ink)', borderRadius:999, fontWeight:600, fontSize:15, display:'inline-flex', gap:8, alignItems:'center'}}>
              Open the dashboard <span style={{display:'inline-block',transform:'translateY(-1px)'}}>→</span>
            </button>
            <button style={{padding:'14px 20px', borderRadius:999, fontSize:15, border:'1px solid var(--line-2)'}}>
              <span className="mono" style={{fontSize:12, color:'var(--muted)', marginRight:8}}>⌘K</span> See scoring rules
            </button>
          </div>
          <div style={{marginTop:40, display:'flex', gap:32, alignItems:'flex-end'}}>
            <Stat big="15m" small="scrape cadence"/>
            <Stat big="0–100" small="deal score model"/>
            <Stat big="3" small="sources unified"/>
            <Stat big="100%" small="local · your machine"/>
          </div>
        </div>

        {/* right: stacked live cards */}
        <div style={{position:'relative', minHeight:420, minWidth:0}}>
          <MiniDeck/>
        </div>
      </div>

      {/* marquee rule */}
      <div style={{borderTop:'1px solid var(--line)', borderBottom:'1px solid var(--line)', padding:'12px 48px', display:'flex', gap:40, alignItems:'center', overflow:'hidden'}}>
        <span className="mono" style={{fontSize:11, letterSpacing:'0.14em', textTransform:'uppercase', color:'var(--muted)'}}>sources</span>
        <span className="serif" style={{fontSize:28}}>Yad2</span>
        <span style={{color:'var(--line-2)'}}>·</span>
        <span className="serif" style={{fontSize:28}}>Madlan</span>
        <span style={{color:'var(--line-2)'}}>·</span>
        <span className="serif" style={{fontSize:28}}>Facebook Marketplace</span>
        <span style={{color:'var(--line-2)'}}>·</span>
        <span className="serif" style={{fontSize:28, color:'var(--muted)'}}>next: Komo, Homeless</span>
        <span style={{flex:1}}/>
        <span className="mono" style={{fontSize:11, color:'var(--muted)'}}>cadence 00:15:00</span>
      </div>

      {/* How it works */}
      <div style={{padding:'64px 48px', display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:32, borderBottom:'1px solid var(--line)'}}>
        <Step n="01" title="Scrape" body="DrissionPage-driven Chrome, persistent profile, CAPTCHA hand-off. Debug Chrome on :9222 that you keep awake."/>
        <Step n="02" title="Score" body="Each listing rated 0–100 on price vs. neighborhood mean, your must-haves, freshness, and price trajectory."/>
        <Step n="03" title="Surface" body="Dashboard for browsing, Telegram for alerts on ≥80, one-click WhatsApp, status tracking per listing."/>
      </div>

      {/* Scoring anatomy */}
      <div style={{padding:'72px 48px', borderBottom:'1px solid var(--line)'}}>
        <div style={{display:'flex', alignItems:'baseline', gap:24, marginBottom:48}}>
          <span className="mono" style={{fontSize:11, color:'var(--muted)', letterSpacing:'0.14em', textTransform:'uppercase'}}>§ 02 — the score</span>
          <h2 className="serif" style={{fontSize:'clamp(40px,5.5vw,72px)', margin:0, lineHeight:1, letterSpacing:'-0.02em'}}>One number, four inputs.</h2>
        </div>
        <div style={{display:'grid', gridTemplateColumns:'1.3fr 1fr', gap:64, alignItems:'center'}}>
          <div>
            <ScoreBreakdown/>
          </div>
          <div>
            <p style={{fontSize:18, lineHeight:1.55, color:'var(--ink-2)', margin:0}}>
              Price competitiveness does most of the work — how far below the neighborhood mean this particular
              apartment sits — but freshness and your own must-haves nudge the number up or down until it lands
              somewhere between <span className="serif" style={{fontStyle:'italic'}}>act now</span> and <span className="serif" style={{fontStyle:'italic'}}>keep scrolling</span>.
            </p>
            <Rule label="01 · price vs. neighborhood mean" right="40 pts"/>
            <Rule label="02 · your must-have features" right="30 pts"/>
            <Rule label="03 · listing recency" right="15 pts"/>
            <Rule label="04 · price trajectory" right="15 pts"/>
          </div>
        </div>
      </div>

      {/* Close */}
      <div style={{padding:'72px 48px 80px', display:'grid', gridTemplateColumns:'1fr 1fr', gap:64, alignItems:'end'}}>
        <div>
          <h2 className="serif" style={{fontSize:'clamp(48px,7vw,96px)', margin:0, lineHeight:0.95, letterSpacing:'-0.02em'}}>
            Then: <span style={{fontStyle:'italic'}}>act</span><br/>before anyone<br/>else does.
          </h2>
        </div>
        <div style={{justifySelf:'end', textAlign:'right'}}>
          <p style={{fontSize:16, color:'var(--ink-2)', maxWidth:420, marginLeft:'auto'}}>The dashboard below is wired to live data. Scroll in, or press the button.</p>
          <button onClick={onGotoDash} style={{marginTop:24, padding:'16px 22px', background:'var(--ink)', color:'var(--paper)', borderRadius:999, fontSize:15, display:'inline-flex', gap:8}}>
            Enter the dashboard ↓
          </button>
        </div>
      </div>
    </section>
  );
}

function Logo(){
  return (
    <div style={{display:'flex', alignItems:'center', gap:8}}>
      <svg width="26" height="26" viewBox="0 0 26 26" fill="none">
        <rect x="1" y="1" width="24" height="24" rx="6" fill="var(--ink)"/>
        <path d="M6 17 V10 L13 5 L20 10 V17" stroke="var(--accent)" strokeWidth="1.8" fill="none" strokeLinejoin="round"/>
        <circle cx="13" cy="13" r="2" fill="var(--accent)"/>
      </svg>
      <span className="serif" style={{fontSize:22, letterSpacing:'-0.01em'}}>NadlanScraper</span>
    </div>
  );
}

function Stat({big, small}){
  return (
    <div>
      <div className="serif" style={{fontSize:42, lineHeight:1}}>{big}</div>
      <div className="mono" style={{fontSize:10, color:'var(--muted)', letterSpacing:'0.14em', textTransform:'uppercase', marginTop:4}}>{small}</div>
    </div>
  );
}

function Step({n,title,body}){
  return (
    <div>
      <div className="mono" style={{fontSize:11, color:'var(--muted)', letterSpacing:'0.14em'}}>{n}</div>
      <h3 className="serif" style={{fontSize:40, margin:'8px 0 12px', letterSpacing:'-0.02em'}}>{title}</h3>
      <p style={{fontSize:15, lineHeight:1.55, color:'var(--ink-2)', margin:0}}>{body}</p>
    </div>
  );
}

function MiniDeck(){
  const items = LISTINGS.slice(0,3);
  return (
    <div style={{position:'absolute', inset:0}}>
      {items.map((it,i)=>(
        <div key={it.id} style={{
          position:'absolute',
          top: 20 + i*108,
          right: i*12,
          left: i*12,
          background:'var(--paper)',
          border:'1px solid var(--line-2)',
          boxShadow: i===0?'0 30px 60px -30px rgba(0,0,0,0.2)':'0 10px 30px -20px rgba(0,0,0,0.2)',
          borderRadius:4,
          transform:`rotate(${(i-1)*0.8}deg)`,
        }}>
          <MiniCard it={it}/>
        </div>
      ))}
    </div>
  );
}

function MiniCard({it}){
  return (
    <div style={{display:'grid', gridTemplateColumns:'130px 1fr auto', gap:14, padding:14, alignItems:'center'}}>
      <div style={{height:90, borderRadius:2, overflow:'hidden'}}>
        <SmartPhoto image={it.image} seed="warm" height={90}/>
      </div>
      <div style={{minWidth:0}}>
        <div className="mono" style={{fontSize:10, color:'var(--muted)', letterSpacing:'0.12em', textTransform:'uppercase'}}>{it.source} · {it.daysAgo}d ago</div>
        <div className="he" style={{fontSize:16, fontWeight:600, marginTop:4, textOverflow:'ellipsis', overflow:'hidden', whiteSpace:'nowrap'}}>{it.he}</div>
        <div style={{display:'flex',gap:8, marginTop:6, alignItems:'center'}}>
          <span className="serif" style={{fontSize:22}}>{formatILS(it.price)}</span>
          <span className="mono" style={{fontSize:11, color:'var(--muted)'}}>/ mo</span>
          <span className="mono" style={{fontSize:11, color:'var(--ink-2)'}}>· {it.rooms} rm · {it.sqm} m²</span>
        </div>
      </div>
      <ScoreDial score={it.score} size={62} strokeWidth={6}/>
    </div>
  );
}

function ScoreBreakdown(){
  const bars = [
    {label:'Price vs. mean', max:40, val:34, color:'var(--accent)'},
    {label:'Features match', max:30, val:22, color:'var(--ink)'},
    {label:'Freshness', max:15, val:15, color:'var(--warn)'},
    {label:'Price trend', max:15, val:12, color:'var(--cool)'},
  ];
  const total = bars.reduce((s,b)=>s+b.val,0);
  return (
    <div style={{border:'1px solid var(--line-2)', borderRadius:4, padding:'28px 32px', background:'var(--paper-2)'}}>
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'baseline'}}>
        <div>
          <div className="mono" style={{fontSize:11, color:'var(--muted)', letterSpacing:'0.14em', textTransform:'uppercase'}}>sample listing · בבלי · 4 חד׳</div>
          <div className="he" style={{fontSize:15, marginTop:4}}>דירת 4 חדרים משופצת עם מרפסת שמש</div>
        </div>
        <ScoreDial score={total} size={100} strokeWidth={10}/>
      </div>
      <div style={{marginTop:24, display:'grid', gap:18}}>
        {bars.map(b=>(
          <div key={b.label}>
            <div style={{display:'flex', justifyContent:'space-between', alignItems:'baseline', marginBottom:6}}>
              <span style={{fontSize:13}}>{b.label}</span>
              <span className="mono" style={{fontSize:12, color:'var(--muted)'}}>{b.val} / {b.max}</span>
            </div>
            <div style={{height:6, background:'var(--line)', borderRadius:999, overflow:'hidden', position:'relative'}}>
              <div style={{width:`${(b.val/b.max)*100}%`, height:'100%', background:b.color}}/>
              <div style={{position:'absolute', left:`${(b.max/100)*0}%`, width:`${b.max}%`, top:0, bottom:0, borderRight:'1px dashed var(--line-2)', pointerEvents:'none'}}/>
            </div>
          </div>
        ))}
        <div style={{display:'flex', justifyContent:'space-between', paddingTop:12, borderTop:'1px solid var(--line-2)', marginTop:6}}>
          <span className="mono" style={{fontSize:11, letterSpacing:'0.14em', textTransform:'uppercase', color:'var(--muted)'}}>total</span>
          <span className="serif" style={{fontSize:26}}>{total} <span style={{color:'var(--muted)', fontSize:16}}>/ 100</span></span>
        </div>
      </div>
    </div>
  );
}

/* ---------- Dashboard ---------- */
function Dashboard({state, set}){
  const [filters, setFilters] = useState(Object.assign({
    status:'all', city:'', neighborhood:'', minScore:0, mamad:false, sort:'deal_score', q:''
  }, BOOTSTRAP.filters || {}));
  const [listings, setListings] = useState([]);
  const [statusMap, setStatusMap] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(()=>{
    const params = new URLSearchParams();
    if(filters.city) params.set('city', filters.city);
    if(filters.neighborhood) params.set('neighborhood', filters.neighborhood);
    if(filters.minScore) params.set('min_score', filters.minScore);
    if(filters.mamad) params.set('has_mamad','true');
    if(filters.sort) params.set('sort_by', filters.sort);
    if(filters.status && filters.status!=='all') params.set('status', filters.status);
    setLoading(true);
    fetch('/api/listings?'+params.toString())
      .then(r=>r.json())
      .then(data=>{ LISTINGS = data; setListings(data); setLoading(false); })
      .catch(e=>{ console.error(e); setLoading(false); });
  },[filters.city, filters.neighborhood, filters.minScore, filters.mamad, filters.sort, filters.status]);

  const setLStatus = async (id, s) => {
    setStatusMap(m => ({...m, [id]: m[id]===s ? null : s}));
    try {
      await fetch('/api/listing/'+id+'/status?status='+encodeURIComponent(s), {method:'POST'});
    } catch(e) { console.error(e); }
  };

  const filtered = useMemo(()=>{
    return listings.filter(l=>{
      if(filters.city && l.city!==filters.city) return false;
      if(filters.neighborhood && l.neighborhood!==filters.neighborhood) return false;
      if(l.score < filters.minScore) return false;
      if(filters.mamad && !l.features.mamad) return false;
      if(filters.status!=='all' && statusMap[l.id]!==filters.status) return false;
      if(filters.q && !(l.he.includes(filters.q)||l.neighborhood.includes(filters.q)||l.city.includes(filters.q))) return false;
      return true;
    }).sort((a,b)=>{
      if(filters.sort==='deal_score') return b.score-a.score;
      if(filters.sort==='newest') return a.daysAgo-b.daysAgo;
      if(filters.sort==='price_asc') return a.price-b.price;
      if(filters.sort==='price_desc') return b.price-a.price;
      return 0;
    });
  },[filters, statusMap, listings]);

  return (
    <div id="dashboard" style={{display:'grid', gridTemplateColumns:'280px 1fr', minHeight:'100vh'}}>
      <Sidebar filters={filters} setFilters={setFilters} state={state} set={set}/>
      <main style={{borderLeft:'1px solid var(--line)'}}>
        <TopBar state={state} set={set}/>
        <StatsStrip/>
        <Toolbar count={filtered.length} total={listings.length} filters={filters} setFilters={setFilters} state={state} set={set}/>
        {state.view==='grid' ? (
          <GridView items={filtered} statusMap={statusMap} setLStatus={setLStatus} density={state.density}/>
        ) : (
          <ListView items={filtered} statusMap={statusMap} setLStatus={setLStatus} density={state.density}/>
        )}
        <DashFooter/>
      </main>
    </div>
  );
}

function Sidebar({filters, setFilters, state, set}){
  const cities = ["תל אביב-יפו","רמת גן","גבעתיים","הרצליה"];
  const hoods = ["בבלי","פלורנטין","לב העיר","נווה צדק","רמת אביב","כרם התימנים","נווה שאנן","הצעירים","מרכז העיר"];
  const upd = (k,v)=>setFilters(f=>({...f,[k]:v}));
  return (
    <aside style={{position:'sticky', top:0, alignSelf:'start', height:'100vh', overflowY:'auto', padding:'24px 22px', background:'var(--paper-2)'}}>
      <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:20}}>
        <Logo/>
      </div>
      <div style={{display:'flex', alignItems:'center', gap:8, padding:'8px 10px', border:'1px solid var(--line-2)', borderRadius:6, background:'var(--paper)'}}>
        <span style={{fontSize:14, color:'var(--muted)'}}>⌕</span>
        <input placeholder="Search address, title…" value={filters.q} onChange={e=>upd('q',e.target.value)} style={{flex:1, border:0, outline:0, background:'transparent', fontSize:13}}/>
        <span className="mono" style={{fontSize:10, color:'var(--muted)', border:'1px solid var(--line-2)', padding:'2px 6px', borderRadius:4}}>⌘K</span>
      </div>

      <SidebarSection label="Filters">
        <Field label="Status">
          <Seg options={[['all','All'],['unseen','Unseen'],['interested','Liked'],['contacted','Called']]} value={filters.status} onChange={v=>upd('status',v)}/>
        </Field>
        <Field label="City">
          <Select value={filters.city} onChange={e=>upd('city',e.target.value)}>
            <option value="">All cities</option>
            {cities.map(c=><option key={c} value={c}>{c}</option>)}
          </Select>
        </Field>
        <Field label="Neighborhood">
          <Select value={filters.neighborhood} onChange={e=>upd('neighborhood',e.target.value)}>
            <option value="">Any</option>
            {hoods.map(c=><option key={c} value={c}>{c}</option>)}
          </Select>
        </Field>
        <Field label={`Min score · ${filters.minScore}`}>
          <input type="range" min="0" max="100" value={filters.minScore} onChange={e=>upd('minScore',+e.target.value)} style={{width:'100%', accentColor:'var(--ink)'}}/>
          <div className="mono" style={{fontSize:10, color:'var(--muted)', display:'flex', justifyContent:'space-between', marginTop:2}}>
            <span>0</span><span>50</span><span>100</span>
          </div>
        </Field>
        <Field label="Must-haves">
          <div style={{display:'flex', flexWrap:'wrap', gap:6}}>
            {['mamad','parking','elevator','balcony'].map(k=>(
              <button key={k} onClick={()=>upd(k,!filters[k])} style={{
                padding:'6px 10px', borderRadius:6, fontSize:12,
                border:`1px solid ${filters[k]?'var(--ink)':'var(--line-2)'}`,
                background: filters[k]?'var(--ink)':'transparent',
                color: filters[k]?'var(--paper)':'var(--ink-2)',
              }}>
                <span className="mono" style={{fontSize:10, marginRight:4}}>{FEATURE_META[k].glyph}</span>
                <span className="he">{FEATURE_META[k].he}</span>
              </button>
            ))}
          </div>
        </Field>
        <Field label="Sort">
          <Select value={filters.sort} onChange={e=>upd('sort',e.target.value)}>
            <option value="deal_score">Best deal first</option>
            <option value="newest">Newest first</option>
            <option value="price_asc">Price · low → high</option>
            <option value="price_desc">Price · high → low</option>
          </Select>
        </Field>
      </SidebarSection>

      <SidebarSection label="Scrapers" right={<Pill tone="accent" style={{fontSize:10, padding:'2px 8px'}}><span style={{width:5,height:5,borderRadius:'50%',background:'var(--accent-ink)'}}/> live</Pill>}>
        <SourceRow name="Yad2" next="in 04:22" count={1148}/>
        <SourceRow name="Madlan" next="in 09:41" count={486}/>
        <SourceRow name="Facebook" next="paused · captcha" count={213} warn/>
      </SidebarSection>

      <SidebarSection label="Density">
        <Seg options={[['comfortable','Comfortable'],['compact','Compact']]} value={state.density} onChange={v=>set({density:v})}/>
      </SidebarSection>

      <div style={{marginTop:24, paddingTop:20, borderTop:'1px solid var(--line)'}}>
        <div className="mono" style={{fontSize:10, color:'var(--muted)', letterSpacing:'0.14em', textTransform:'uppercase'}}>local · 127.0.0.1:8000</div>
        <div className="mono" style={{fontSize:10, color:'var(--muted)', marginTop:4}}>chrome debug port 9222</div>
      </div>
    </aside>
  );
}

function SidebarSection({label, right, children}){
  return (
    <section style={{marginTop:26}}>
      <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:12}}>
        <div className="mono" style={{fontSize:10, color:'var(--muted)', letterSpacing:'0.14em', textTransform:'uppercase'}}>{label}</div>
        {right}
      </div>
      {children}
    </section>
  );
}

function Field({label, children}){
  return (
    <div style={{marginBottom:14}}>
      <div style={{fontSize:11, color:'var(--muted)', marginBottom:6}}>{label}</div>
      {children}
    </div>
  );
}

function Seg({options, value, onChange}){
  return (
    <div style={{display:'grid', gridTemplateColumns:`repeat(${options.length},1fr)`, border:'1px solid var(--line-2)', borderRadius:6, overflow:'hidden', background:'var(--paper)'}}>
      {options.map(([v,l])=>(
        <button key={v} onClick={()=>onChange(v)} style={{
          padding:'7px 6px', fontSize:12, fontWeight:500,
          background: value===v ? 'var(--ink)' : 'transparent',
          color: value===v ? 'var(--paper)' : 'var(--ink-2)',
        }}>{l}</button>
      ))}
    </div>
  );
}

function Select(p){
  return <select {...p} style={{width:'100%', padding:'8px 10px', border:'1px solid var(--line-2)', borderRadius:6, background:'var(--paper)', fontSize:13, appearance:'none'}}/>;
}

function SourceRow({name, next, count, warn}){
  return (
    <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', padding:'8px 0', borderTop:'1px solid var(--line)'}}>
      <div>
        <div style={{fontSize:13, fontWeight:500}}>{name}</div>
        <div className="mono" style={{fontSize:10, color: warn ? 'var(--danger)' : 'var(--muted)'}}>{next}</div>
      </div>
      <div className="mono" style={{fontSize:12, color:'var(--ink-2)'}}>{count}</div>
    </div>
  );
}

function TopBar({state, set}){
  return (
    <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', padding:'14px 28px', borderBottom:'1px solid var(--line)'}}>
      <div style={{display:'flex', alignItems:'center', gap:10}}>
        <span className="mono" style={{fontSize:11, color:'var(--muted)', letterSpacing:'0.14em', textTransform:'uppercase'}}>dashboard /</span>
        <span className="serif" style={{fontSize:22, lineHeight:1}}>Central Israel · All listings</span>
      </div>
      <div style={{display:'flex', gap:10, alignItems:'center'}}>
        <span className="mono" style={{fontSize:11, color:'var(--muted)'}}>last scrape 00:04:22 ago</span>
        <Pill tone="ink"><span style={{width:6,height:6, borderRadius:'50%', background:'var(--accent)'}}/><span>Scraper running</span></Pill>
        <button style={{padding:'7px 12px', border:'1px solid var(--line-2)', borderRadius:6, fontSize:13}}>Settings</button>
        <button style={{padding:'7px 12px', border:'1px solid var(--ink)', borderRadius:6, background:'var(--ink)', color:'var(--paper)', fontSize:13}}>Pause</button>
      </div>
    </div>
  );
}

function StatsStrip(){
  return (
    <div style={{display:'grid', gridTemplateColumns:'1.4fr 1fr 1fr 1fr', borderBottom:'1px solid var(--line)'}}>
      <StatCell label="Total listings" value={STATS.total.toLocaleString()} sub="across 3 sources" chart={<Spark data={STATS.trend7d}/>}/>
      <StatCell label="New today" value={STATS.newToday} sub="+4 vs yesterday" tone="accent"/>
      <StatCell label="Hot deals · ≥80" value={STATS.hotDeals} sub="2 flagged new"/>
      <StatCell label="Avg deal score" value={STATS.avgScore} sub="trending ↑" bars={STATS.sourcesBreakdown}/>
    </div>
  );
}

function StatCell({label, value, sub, chart, bars, tone}){
  return (
    <div style={{padding:'20px 24px', borderRight:'1px solid var(--line)', display:'flex', flexDirection:'column', gap:6, position:'relative', background: tone==='accent' ? 'color-mix(in oklch, var(--accent) 18%, var(--paper))' : 'var(--paper)'}}>
      <div className="mono" style={{fontSize:10, color:'var(--muted)', letterSpacing:'0.14em', textTransform:'uppercase'}}>{label}</div>
      <div style={{display:'flex', alignItems:'baseline', gap:10}}>
        <span className="serif" style={{fontSize:44, lineHeight:1}}>{value}</span>
        <span className="mono" style={{fontSize:11, color:'var(--muted)'}}>{sub}</span>
      </div>
      {chart && <div style={{marginTop:8}}>{chart}</div>}
      {bars && (
        <div style={{marginTop:8, display:'flex', height:8, borderRadius:2, overflow:'hidden', border:'1px solid var(--line-2)'}}>
          {bars.map(b=><div key={b.k} title={`${b.k} ${b.v}%`} style={{width:`${b.v}%`, background:b.c}}/>)}
        </div>
      )}
      {bars && (
        <div style={{display:'flex', gap:10, marginTop:4}}>
          {bars.map(b=><span key={b.k} className="mono" style={{fontSize:10, color:'var(--muted)'}}><span style={{display:'inline-block',width:6,height:6,background:b.c,marginRight:4}}/>{b.k} {b.v}%</span>)}
        </div>
      )}
    </div>
  );
}

function Spark({data}){
  const w=240, h=36, max=Math.max(...data), min=Math.min(...data);
  const pts = data.map((v,i)=>[i/(data.length-1)*w, h - ((v-min)/(max-min||1))*h]);
  const d = pts.map((p,i)=>`${i===0?'M':'L'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
  const area = `${d} L${w},${h} L0,${h} Z`;
  return (
    <svg width={w} height={h} style={{display:'block'}}>
      <path d={area} fill="color-mix(in oklch, var(--ink) 7%, transparent)"/>
      <path d={d} fill="none" stroke="var(--ink)" strokeWidth="1.4"/>
      <circle cx={pts[pts.length-1][0]} cy={pts[pts.length-1][1]} r="2.5" fill="var(--accent)" stroke="var(--ink)" strokeWidth="1"/>
    </svg>
  );
}

function Toolbar({count, total, filters, setFilters, state, set}){
  const active = [];
  if(filters.city) active.push({k:'city', label:filters.city, clear:()=>setFilters(f=>({...f,city:''}))});
  if(filters.neighborhood) active.push({k:'hood', label:filters.neighborhood, clear:()=>setFilters(f=>({...f,neighborhood:''}))});
  if(filters.minScore>0) active.push({k:'ms', label:`score ≥ ${filters.minScore}`, clear:()=>setFilters(f=>({...f,minScore:0}))});
  if(filters.mamad) active.push({k:'m', label:'mamad', clear:()=>setFilters(f=>({...f,mamad:false}))});
  if(filters.q) active.push({k:'q', label:`"${filters.q}"`, clear:()=>setFilters(f=>({...f,q:''}))});

  return (
    <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', padding:'14px 28px', borderBottom:'1px solid var(--line)', gap:12}}>
      <div style={{display:'flex', alignItems:'center', gap:12, flexWrap:'wrap'}}>
        <span className="serif" style={{fontSize:22}}>{count}</span>
        <span className="mono" style={{fontSize:11, color:'var(--muted)'}}>of {total} listings match</span>
        {active.length>0 && <span style={{color:'var(--line-2)'}}>·</span>}
        {active.map(a=>(
          <button key={a.k} onClick={a.clear} style={{display:'inline-flex', alignItems:'center', gap:6, padding:'4px 10px', borderRadius:999, border:'1px solid var(--ink)', background:'var(--ink)', color:'var(--paper)', fontSize:12}}>
            {a.label} <span style={{opacity:0.7}}>×</span>
          </button>
        ))}
      </div>
      <div style={{display:'flex', gap:6}}>
        <Seg options={[['grid','Grid'],['list','List']]} value={state.view} onChange={v=>set({view:v})}/>
      </div>
    </div>
  );
}

/* ---------- Grid + List ---------- */
function GridView({items, statusMap, setLStatus, density}){
  const cols = density==='compact' ? 4 : 3;
  return (
    <div style={{display:'grid', gridTemplateColumns:`repeat(${cols}, 1fr)`, padding:'24px 28px', gap:24, background:'var(--paper)'}}>
      {items.map(it => <Card key={it.id} it={it} status={statusMap[it.id]} setStatus={s=>setLStatus(it.id,s)} density={density}/>)}
    </div>
  );
}

function Card({it, status, setStatus, density}){
  const compact = density==='compact';
  return (
    <article style={{
      background:'var(--paper)',
      border:'1px solid var(--line-2)',
      borderRadius:2,
      overflow:'hidden',
      display:'flex', flexDirection:'column',
      transition:'transform 0.15s, box-shadow 0.15s',
      position:'relative',
    }}
    onMouseEnter={e=>{e.currentTarget.style.boxShadow='0 20px 40px -20px rgba(0,0,0,0.25)'; e.currentTarget.style.transform='translateY(-2px)'}}
    onMouseLeave={e=>{e.currentTarget.style.boxShadow='none'; e.currentTarget.style.transform='translateY(0)'}}
    >
      <div style={{position:'relative'}}>
        <SmartPhoto image={it.image} seed="warm" height={compact?150:200}/>
        {/* top overlay: source + new */}
        <div style={{position:'absolute', top:12, left:12, right:12, display:'flex', justifyContent:'space-between', alignItems:'flex-start'}}>
          <span className="mono" style={{fontSize:10, letterSpacing:'0.14em', textTransform:'uppercase', background:'rgba(14,15,12,0.82)', color:'var(--paper)', padding:'4px 8px', borderRadius:2}}>{it.source}</span>
          <div style={{display:'flex', gap:6, flexDirection:'column', alignItems:'flex-end'}}>
            {it.isNew && <span className="mono" style={{fontSize:10, letterSpacing:'0.14em', background:'var(--accent)', color:'var(--accent-ink)', padding:'4px 8px', borderRadius:2}}>NEW</span>}
            {it.trend<=-3 && <span className="mono" style={{fontSize:10, letterSpacing:'0.14em', background:'var(--paper)', color:'var(--ink)', padding:'4px 8px', borderRadius:2, border:'1px solid var(--ink)'}}>↓ {Math.abs(it.trend)}%</span>}
          </div>
        </div>
        {/* dial */}
        <div style={{position:'absolute', right:-8, bottom:-34, background:'var(--paper)', border:'1px solid var(--line-2)', padding:6, borderRadius:'50%'}}>
          <ScoreDial score={it.score} size={compact?70:84} strokeWidth={compact?7:8}/>
        </div>
      </div>
      <div style={{padding: compact ? '14px 16px' : '22px 18px 18px', display:'flex', flexDirection:'column', gap:10, flex:1}}>
        <div style={{display:'flex', alignItems:'center', gap:8, flexWrap:'wrap'}}>
          <span className="he" style={{fontSize:14, fontWeight:600}}>{it.neighborhood}</span>
          <span style={{color:'var(--line-2)'}}>·</span>
          <span className="he" style={{fontSize:13, color:'var(--muted)'}}>{it.city}</span>
        </div>
        <h3 className="he" style={{margin:0, fontSize:compact?14:16, fontWeight:500, lineHeight:1.35, minHeight:compact?'0':42}}>{it.he}</h3>
        <div style={{display:'flex', alignItems:'baseline', gap:8, flexWrap:'wrap'}}>
          <span className="serif" style={{fontSize:compact?28:34, lineHeight:1, letterSpacing:'-0.01em'}}>{formatILS(it.price)}</span>
          <span className="mono" style={{fontSize:11, color:'var(--muted)'}}>· {it.pricePerSqm} ₪/m²</span>
        </div>
        <div style={{display:'flex', gap:10, marginTop:-2}}>
          <Metric label="rooms" value={it.rooms}/>
          <Metric label="m²" value={it.sqm}/>
          <Metric label="floor" value={it.floor===0?'G':it.floor}/>
          <Metric label="age" value={`${it.daysAgo}d`}/>
        </div>
        <Features f={it.features}/>
        <div style={{marginTop:'auto', paddingTop:12, display:'flex', gap:6}}>
          <a href={it.url} target="_blank" rel="noopener" style={{flex:1, padding:'10px 12px', textAlign:'center', border:'1px solid var(--ink)', background:'var(--ink)', color:'var(--paper)', borderRadius:2, fontSize:12, fontWeight:500, textDecoration:'none'}}>Open on {it.source}</a>
          <IconBtn active={status==='interested'} onClick={()=>setStatus('interested')} title="Like">♥</IconBtn>
          <IconBtn active={status==='contacted'} onClick={()=>setStatus('contacted')} title="Called">☎</IconBtn>
          <IconBtn active={status==='not_interested'} onClick={()=>setStatus('not_interested')} title="Hide">×</IconBtn>
        </div>
      </div>
    </article>
  );
}

function Metric({label, value}){
  return (
    <div style={{display:'flex', flexDirection:'column', alignItems:'flex-start', minWidth:0, paddingRight:10, borderRight:'1px dashed var(--line-2)'}}>
      <span className="serif" style={{fontSize:20, lineHeight:1}}>{value}</span>
      <span className="mono" style={{fontSize:9, letterSpacing:'0.14em', textTransform:'uppercase', color:'var(--muted)', marginTop:2}}>{label}</span>
    </div>
  );
}

function IconBtn({active, children, ...p}){
  return (
    <button {...p} style={{
      width:38, height:38, borderRadius:2, fontSize:16,
      border:`1px solid ${active?'var(--ink)':'var(--line-2)'}`,
      background: active?'var(--accent)':'transparent',
      color: active?'var(--accent-ink)':'var(--ink-2)',
    }}>{children}</button>
  );
}

/* List view */
function ListView({items, statusMap, setLStatus, density}){
  const rowPad = density==='compact'?'10px 28px':'16px 28px';
  return (
    <div style={{background:'var(--paper)'}}>
      <div style={{display:'grid', gridTemplateColumns:'auto 1.5fr 1fr 1fr 1.4fr auto', gap:16, padding:'10px 28px', borderBottom:'1px solid var(--line)', background:'var(--paper-2)'}}>
        <div className="mono" style={{fontSize:10, color:'var(--muted)', letterSpacing:'0.14em', textTransform:'uppercase'}}>score</div>
        <div className="mono" style={{fontSize:10, color:'var(--muted)', letterSpacing:'0.14em', textTransform:'uppercase'}}>listing</div>
        <div className="mono" style={{fontSize:10, color:'var(--muted)', letterSpacing:'0.14em', textTransform:'uppercase'}}>location</div>
        <div className="mono" style={{fontSize:10, color:'var(--muted)', letterSpacing:'0.14em', textTransform:'uppercase'}}>price</div>
        <div className="mono" style={{fontSize:10, color:'var(--muted)', letterSpacing:'0.14em', textTransform:'uppercase'}}>features</div>
        <div className="mono" style={{fontSize:10, color:'var(--muted)', letterSpacing:'0.14em', textTransform:'uppercase'}}>actions</div>
      </div>
      {items.map(it=>(
        <div key={it.id} style={{display:'grid', gridTemplateColumns:'auto 1.5fr 1fr 1fr 1.4fr auto', gap:16, padding:rowPad, borderBottom:'1px solid var(--line)', alignItems:'center'}}>
          <ScoreDial score={it.score} size={54} strokeWidth={6} showLabel={false}/>
          <div>
            <div className="he" style={{fontSize:15, fontWeight:500, lineHeight:1.3}}>{it.he}</div>
            <div className="mono" style={{fontSize:10, color:'var(--muted)', marginTop:4, letterSpacing:'0.08em'}}>{it.source} · {it.daysAgo}d ago · {it.rooms} rm · {it.sqm} m² · floor {it.floor}</div>
          </div>
          <div>
            <div className="he" style={{fontSize:13, fontWeight:500}}>{it.neighborhood}</div>
            <div className="he" style={{fontSize:12, color:'var(--muted)'}}>{it.city}</div>
          </div>
          <div>
            <div className="serif" style={{fontSize:22, lineHeight:1}}>{formatILS(it.price)}</div>
            <div className="mono" style={{fontSize:10, color: it.trend<0?'var(--ink)':'var(--muted)', marginTop:4}}>{it.pricePerSqm} ₪/m² {it.trend<0 && <span style={{color:'oklch(0.6 0.16 150)'}}>· ↓ {Math.abs(it.trend)}%</span>}</div>
          </div>
          <Features f={it.features}/>
          <div style={{display:'flex', gap:6}}>
            <IconBtn active={statusMap[it.id]==='interested'} onClick={()=>setLStatus(it.id,'interested')}>♥</IconBtn>
            <IconBtn active={statusMap[it.id]==='contacted'} onClick={()=>setLStatus(it.id,'contacted')}>☎</IconBtn>
            <button style={{padding:'9px 12px', border:'1px solid var(--ink)', background:'var(--ink)', color:'var(--paper)', borderRadius:2, fontSize:12}}>Open</button>
          </div>
        </div>
      ))}
    </div>
  );
}

function DashFooter(){
  return (
    <footer style={{padding:'28px', borderTop:'1px solid var(--line)', display:'flex', justifyContent:'space-between', alignItems:'center', background:'var(--paper-2)'}}>
      <div className="mono" style={{fontSize:11, color:'var(--muted)'}}>NadlanScraper · local instance · v4.2 · <a style={{textDecoration:'underline'}}>logs</a> · <a style={{textDecoration:'underline'}}>db stats</a></div>
      <div className="mono" style={{fontSize:11, color:'var(--muted)'}}>auto-refresh every 5 min</div>
    </footer>
  );
}

/* ---------- Tweaks panel ---------- */
function TweaksPanel({state, set, active}){
  if(!active) return null;
  return (
    <div style={{
      position:'fixed', right:20, bottom:20, zIndex:50, width:260,
      background:'var(--ink)', color:'var(--paper)', borderRadius:8, padding:16,
      boxShadow:'0 30px 60px -20px rgba(0,0,0,0.5)'
    }}>
      <div className="mono" style={{fontSize:10, letterSpacing:'0.14em', textTransform:'uppercase', color:'var(--paper-2)', opacity:0.7, marginBottom:10}}>Tweaks</div>
      <TweakRow label="Density">
        <SegDark options={[['comfortable','Comfy'],['compact','Compact']]} value={state.density} onChange={v=>set({density:v})}/>
      </TweakRow>
      <TweakRow label="View">
        <SegDark options={[['grid','Grid'],['list','List']]} value={state.view} onChange={v=>set({view:v})}/>
      </TweakRow>
      <TweakRow label="Marketing">
        <SegDark options={[[true,'Show'],[false,'Hide']]} value={state.showMarketing} onChange={v=>set({showMarketing:v})}/>
      </TweakRow>
    </div>
  );
}
function TweakRow({label,children}){
  return <div style={{marginBottom:10}}><div style={{fontSize:11, opacity:0.7, marginBottom:5}}>{label}</div>{children}</div>;
}
function SegDark({options,value,onChange}){
  return (
    <div style={{display:'grid', gridTemplateColumns:`repeat(${options.length},1fr)`, border:'1px solid rgba(255,255,255,0.15)', borderRadius:6, overflow:'hidden'}}>
      {options.map(([v,l])=>(
        <button key={String(v)} onClick={()=>onChange(v)} style={{
          padding:'6px 6px', fontSize:12,
          background:value===v?'var(--accent)':'transparent',
          color:value===v?'var(--accent-ink)':'var(--paper)',
        }}>{l}</button>
      ))}
    </div>
  );
}

/* ---------- Root ---------- */
function App(){
  const { state, set, active } = useTweaks();
  const gotoDash = ()=>{
    const el = document.getElementById('dashboard');
    if(el) window.scrollTo({top: el.offsetTop, behavior:'smooth'});
  };
  return (
    <div>
      {state.showMarketing && <Marketing onGotoDash={gotoDash}/>}
      <Dashboard state={state} set={set}/>
      <TweaksPanel state={state} set={set} active={active}/>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
