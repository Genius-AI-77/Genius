/* GENIUS console — rendering. External so the CSP can forbid inline scripts. */
(function(){
  var D=window.GENIUS_DATA;
  if(!D){document.getElementById('err').style.display='block';
         document.getElementById('meta').textContent='';return;}
  document.getElementById('app').style.display='block';
  var m=D.metrics,meta=D.meta,eq=D.equity_curve;
  document.getElementById('meta').innerHTML=
    meta.instrument+' &nbsp;·&nbsp; source: '+meta.source+' &nbsp;·&nbsp; '+meta.sessions+
    ' sessions × '+meta.bars_per_session+' bars<br>'+meta.generated_note;

  function money(v){return (v<0?'−$':'$')+Math.abs(v).toLocaleString('en-US',{maximumFractionDigits:0});}
  var last=eq[eq.length-1].equity, first=eq[0].equity;

  var tiles=[
    ['Equity',money(last),null,'start '+money(first)],
    ['Net P&L',money(m.total_pnl),m.total_pnl,'after '+money(m.total_costs)+' costs'],
    ['Win rate',Math.round(m.win_rate*100)+'%',null,m.wins+'W / '+m.losses+'L'],
    ['Expectancy',money(m.expectancy),m.expectancy,'per trade, after costs'],
    ['Max drawdown',(m.max_drawdown_pct<0?'−':'')+Math.abs(m.max_drawdown_pct).toFixed(1)+'%',
      m.max_drawdown_pct,'on equity curve'],
    ['Risk vetoes',m.vetoes,null,'final, enforced in code'],
    ['No-trade cycles',m.no_trade,null,'of '+m.cycles+' cycles']
  ];
  document.getElementById('tiles').innerHTML=tiles.map(function(t){
    var cls=t[2]==null?'':(t[2]>=0?'up':'down');
    return '<div class="mod tile"><div class="k">'+t[0]+'</div><div class="v '+cls+'">'+
           t[1]+'</div><div class="n">'+t[3]+'</div></div>';}).join('');

  function plot(mountId,tipId,pts,color,fmt){
    var W=560,H=250,P={t:12,r:14,b:26,l:62};
    var ys=pts.map(function(p){return p.v;});
    var y0=Math.min.apply(null,ys),y1=Math.max.apply(null,ys);
    var pad=(y1-y0)*0.08||1; y0-=pad; y1+=pad;
    var n=pts.length;
    var X=function(i){return P.l+(W-P.l-P.r)*(n>1?i/(n-1):0);};
    var Y=function(v){return P.t+(H-P.t-P.b)*(1-(v-y0)/(y1-y0));};
    var grid='',labels='';
    for(var g=0;g<4;g++){
      var v=y0+(y1-y0)*g/3,y=Y(v);
      grid+='<line x1="'+P.l+'" x2="'+(W-P.r)+'" y1="'+y+'" y2="'+y+
            '" stroke="#1e2528" stroke-width="1"/>';
      labels+='<text x="'+(P.l-10)+'" y="'+(y+4)+'" text-anchor="end" font-size="10" '+
              'font-family="IBM Plex Mono, monospace" fill="#616c6f">'+fmt(v)+'</text>';}
    var d=pts.map(function(p,i){return (i?'L':'M')+X(i).toFixed(1)+' '+Y(p.v).toFixed(1);}).join(' ');
    var area=d+' L'+X(n-1).toFixed(1)+' '+(H-P.b)+' L'+P.l+' '+(H-P.b)+' Z';
    var uid=mountId;
    document.getElementById(mountId).innerHTML=
      '<svg class="plot" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="line chart">'+
      '<defs><linearGradient id="g-'+uid+'" x1="0" y1="0" x2="0" y2="1">'+
      '<stop offset="0%" stop-color="'+color+'" stop-opacity=".22"/>'+
      '<stop offset="100%" stop-color="'+color+'" stop-opacity="0"/></linearGradient></defs>'+
      grid+labels+
      '<path d="'+area+'" fill="url(#g-'+uid+')"/>'+
      '<path d="'+d+'" fill="none" stroke="'+color+'" stroke-width="2" stroke-linejoin="round"/>'+
      '<line id="'+uid+'-cx" y1="'+P.t+'" y2="'+(H-P.b)+'" stroke="#616c6f" stroke-width="1" '+
      'stroke-dasharray="3 3" style="display:none"/>'+
      '<circle id="'+uid+'-dot" r="4.5" fill="'+color+'" stroke="#060809" stroke-width="2" style="display:none"/>'+
      '<rect id="'+uid+'-hit" x="'+P.l+'" y="'+P.t+'" width="'+(W-P.l-P.r)+'" height="'+(H-P.t-P.b)+'" fill="transparent"/></svg>';

    var host=document.getElementById(mountId),tip=document.getElementById(tipId),
        svg=host.querySelector('svg'),cx=document.getElementById(uid+'-cx'),
        dot=document.getElementById(uid+'-dot'),hit=document.getElementById(uid+'-hit');
    hit.addEventListener('mousemove',function(ev){
      var r=svg.getBoundingClientRect(),sx=(ev.clientX-r.left)*W/r.width;
      var i=Math.round((sx-P.l)/(W-P.l-P.r)*(n-1));
      i=Math.max(0,Math.min(n-1,i));
      var p=pts[i],x=X(i),y=Y(p.v);
      cx.setAttribute('x1',x);cx.setAttribute('x2',x);cx.style.display='';
      dot.setAttribute('cx',x);dot.setAttribute('cy',y);dot.style.display='';
      tip.style.display='block';
      tip.innerHTML='<b style="color:'+color+'">'+fmt(p.v)+'</b><br><span style="color:#616c6f">'+p.label+'</span>';
      var box=host.parentElement.getBoundingClientRect();
      var tx=x*r.width/W+18, ty=y*r.height/H-8;
      if(tx+tip.offsetWidth>box.width-14) tx-=tip.offsetWidth+34;
      tip.style.left=tx+'px';tip.style.top=ty+'px';});
    hit.addEventListener('mouseleave',function(){
      tip.style.display='none';cx.style.display='none';dot.style.display='none';});
  }
  var when=function(ts){return new Date(ts*1000).toISOString().slice(5,16).replace('T',' ');};
  var usd=function(v){return '$'+Math.round(v).toLocaleString('en-US');};
  plot('priceChart','priceTip',eq.map(function(p){return {v:p.price,label:when(p.ts)};}),'#00a2b8',usd);
  plot('equityChart','equityTip',eq.map(function(p){return {v:p.equity,label:when(p.ts)};}),'#71a10f',usd);

  var step=Math.max(1,Math.floor(eq.length/40));
  document.getElementById('equityTable').innerHTML=
    '<table><thead><tr><th>Time</th><th>Equity</th><th>Price</th></tr></thead><tbody>'+
    eq.filter(function(_,i){return i%step===0;}).map(function(p){
      return '<tr><td>'+when(p.ts)+'</td><td class="num">'+money(p.equity)+
             '</td><td class="num">'+money(p.price)+'</td></tr>';}).join('')+'</tbody></table>';

  document.getElementById('agents').innerHTML=D.reports.map(function(r){
    return '<article class="mod ag"><div class="top"><div><div class="nm">'+r.agent+
      '</div><div class="rl">'+r.role+'</div></div><span class="badge '+r.stance+'">'+
      r.stance.toUpperCase()+'</span></div>'+
      (r.status!=='IMPLEMENTED'?'<span class="simtag">'+r.status+' DATA</span>':'')+
      '<ul>'+r.findings.map(function(f){return '<li>'+f+'</li>';}).join('')+'</ul>'+
      '<div class="conf"><div class="lbl"><span>Confidence</span><span>'+
      Math.round(r.confidence*100)+'%</span></div><div class="track"><i style="width:'+
      (r.confidence*100)+'%"></i></div></div></article>';}).join('');

  document.querySelector('#journal tbody').innerHTML=
    D.journal_tail.slice().reverse().map(function(e){
      return '<tr><td class="num">'+e.bar+'</td><td class="num">'+money(e.price)+
        '</td><td class="d-'+e.decision+'">'+e.decision.replace('_',' ')+
        '</td><td style="white-space:normal;max-width:400px">'+(e.detail||'')+
        '</td><td>'+e.stances.technical+'</td><td>'+e.stances.orderflow+
        '</td><td>'+e.stances.fundamental+'</td></tr>';}).join('');

  document.querySelector('#trades tbody').innerHTML=
    D.closed_trades.slice().reverse().map(function(t){
      return '<tr><td>'+t.side+'</td><td class="num">'+t.qty+'</td><td class="num">'+
        money(t.entry)+'</td><td class="num">'+money(t.exit)+'</td><td class="num '+
        (t.pnl>=0?'up':'down')+'">'+money(t.pnl)+'</td><td class="num">'+money(t.costs)+
        '</td><td>'+t.reason+'</td></tr>';}).join('');
})();
