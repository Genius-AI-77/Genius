/* GENIUS site — page behaviour. Kept external so the CSP can forbid inline scripts. */
(function(){
  var D=window.GENIUS_DATA; if(!D||!D.metrics) return;
  var m=D.metrics, meta=D.meta;
  var money=function(v){return (v<0?'−$':'$')+Math.abs(v).toLocaleString('en-US',{maximumFractionDigits:0});};
  var set=function(sel,txt){var el=document.querySelector(sel); if(el) el.textContent=txt;};
  set('[data-stat=cycles]', m.cycles.toLocaleString('en-US'));
  set('[data-stat=no_trade]', m.no_trade.toLocaleString('en-US'));
  set('[data-stat=vetoes]', m.vetoes.toLocaleString('en-US'));
  set('[data-stat=trades]', m.trades.toLocaleString('en-US'));
  set('[data-stat=pnl]', money(m.total_pnl));
  set('[data-stat=dd]', (m.max_drawdown_pct<0?'−':'')+Math.abs(m.max_drawdown_pct).toFixed(1)+'%');
  set('[data-note=sessions]', meta.sessions+' sessions × '+meta.bars_per_session+' bars');
  set('[data-note=trade_pct]', '~'+Math.round(100*m.trades/Math.max(1,m.cycles))+'% of cycles reached execution');
  set('[data-note=pnl]', 'Paper result, after '+money(m.total_costs)+' costs');
  var pnlEl=document.querySelector('[data-stat=pnl]'); if(pnlEl){pnlEl.classList.toggle('down',m.total_pnl<0);}
  var ex=meta.execution, exl=document.querySelector('[data-exec-line]');
  if(exl){ exl.textContent = ex==='live' ? 'Live execution on '+(meta.venue_name||'the venue')+'. Every fill is public on-chain.'
         : ex==='shadow' ? 'Shadow execution for now: real market, real decisions, paper fills. Real capital is next.'
         : 'Paper execution for now; real capital is the next phase.'; }
  var inputs=meta.inputs||{}; var real=Object.keys(inputs).filter(function(k){return String(inputs[k]).indexOf('live')===0;});
  var when=meta.generated_at?new Date(meta.generated_at*1000).toISOString().slice(0,10):'';
  set('#run-meta', 'Latest run'+(when?' '+when:'')+' · '+meta.instrument+' · inputs: '+
      (real.length?real.map(function(k){return k+' (real)';}).join(', '):'all synthetic')+
      (inputs.news&&inputs.news.indexOf('live')===0?'':'')+' · all P&L after simulated costs');
})();
document.querySelectorAll('.col .units').forEach(function(col,ci){
  var dept=['Discovery','Validation','Operations'][ci];
  for(var u=0;u<11;u++){
    var el=document.createElement('div');
    el.className='unit';
    el.title=dept+' · unit '+(u+1)+' · 6 agent roles';
    el.innerHTML='<i></i><i></i><i></i><i></i><i></i><i></i>';
    col.appendChild(el);
  }
});
var days=document.querySelector('.days');
for(var d=1;d<=33;d++){
  var el=document.createElement('div');
  el.className='day';el.textContent=d;el.title='Day '+d+': report pending';
  days.appendChild(el);
}

document.querySelectorAll('[data-open-wallet]').forEach(function(b){
  b.addEventListener('click', function(){ var w=document.getElementById('wallet-btn'); if(w){ w.click(); w.scrollIntoView({block:'nearest'}); } });
});

(function(){
  var T=window.GENIUS_TOKEN; if(!T||!T.ca) return;
  var ca=T.ca, short=ca.slice(0,6)+'\u2026'+ca.slice(-4);
  var explorer=(T.explorer||'https://robinhoodchain.blockscout.com')+'/token/'+encodeURIComponent(ca);
  var chart='https://dexscreener.com/search?q='+encodeURIComponent(ca);
  var chip=document.getElementById('ca-chip'), card=document.getElementById('ca-card');
  if(chip){ chip.querySelector('span').textContent=short; chip.hidden=false;
    chip.addEventListener('click',function(){ copy(ca, chip.querySelector('span'), short); }); }
  function wire(root){
    root.querySelector('[data-link=explorer]').href=explorer;
    root.querySelector('[data-link=chart]').href=chart;
    var b=root.querySelector('[data-act=copy-ca]'); b.addEventListener('click',function(){ copy(ca, b, 'Copy'); });
  }
  if(card){ card.querySelector('.cacard-addr').textContent=ca; wire(card); card.hidden=false; }
  var sec=document.getElementById('token'), tab=document.getElementById('nav-token');
  if(sec){
    sec.querySelector('#tok-addr').textContent=ca; wire(sec); sec.hidden=false;
    if(T.feeWallet){ var f=sec.querySelector('#tok-fee'); f.textContent=T.feeWallet;
      f.href=(T.explorer||'https://robinhoodchain.blockscout.com')+'/address/'+encodeURIComponent(T.feeWallet); sec.querySelector('#tok-fee-row').hidden=false; }

    // sections after it shift one number down the page
    Array.prototype.forEach.call(document.querySelectorAll('.kicker b[data-n]'),function(el){ el.textContent=String(parseInt(el.getAttribute('data-n'),10)+1).padStart(2,'0'); });
  }
  if(tab) tab.hidden=false;
  function copy(text, el, restore){
    if(!navigator.clipboard) return;
    navigator.clipboard.writeText(text).then(function(){ var was=el.textContent; el.textContent='Copied'; setTimeout(function(){ el.textContent=restore||was; },1200); });
  }
})();
