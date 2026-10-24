const state={period:'month',month:'',card:'all',data:null,detailTransactions:[],mappingData:null,merchantData:null,activeMerchant:null,activeTransaction:null,detailMode:'',activeCategory:'',detailSort:{key:'transaction_date',direction:'desc'},categoryTransactions:[],categoryView:'grouped',categorySearch:'',categoryGroupSort:{key:'latest_date',direction:'desc'},expandedMerchantGroups:new Set(),categoryExpandedSort:new Map()};
const colors=['#6658e8','#41b98c','#e6a14b','#e76b77','#5b8def','#a66dd4','#42a5b3','#d17b49','#8f9b4f','#d45f9f','#62748f','#9b7b58'];
const cardFilter=document.querySelector('#cardFilter');
const monthFilter=document.querySelector('#monthFilter');
const toast=document.querySelector('#toast');
const incomePanel=document.querySelector('#incomePanel');
const incomeShowButton=document.querySelector('#incomeShowButton');
let toastTimer;

const money=value=>new Intl.NumberFormat('en-IL',{style:'currency',currency:'ILS',maximumFractionDigits:2}).format(Number(value)||0).replace('ILS','₪');
const compact=value=>new Intl.NumberFormat('en',{notation:'compact',maximumFractionDigits:1}).format(Number(value)||0);
const escapeHtml=value=>String(value??'').replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
const formatDate=value=>value?new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'short',year:'2-digit'}).format(new Date(`${value}T12:00:00`)):'—';
const formatMonth=value=>value?new Intl.DateTimeFormat('en-GB',{month:'long',year:'numeric'}).format(new Date(`${value}-01T12:00:00`)):'Latest month';
const reportingPeriod=item=>item.billing_date?formatDate(item.billing_date):item.billing_month?formatMonth(item.billing_month):formatDate(item.transaction_date);
const reportingSource=value=>({provider:'Provider billing date',statement:'Statement month',estimated:'Estimated installment month',purchase_date:'Purchase date fallback'}[value]||'Reporting month');
const displayValue=value=>value===null||value===undefined||value===''?'—':escapeHtml(value);
const sourceAmount=(value,currency)=>value===null||value===undefined?'—':`${new Intl.NumberFormat('en-IL',{maximumFractionDigits:2}).format(Number(value))} ${escapeHtml(currency||'')}`.trim();

function showToast(message,title='Updated'){
  document.querySelector('#toastText').textContent=message;
  toast.querySelector('strong').textContent=title;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer=setTimeout(()=>toast.classList.remove('show'),2600);
}

async function loadDashboard(announce=false){
  try{
    const response=await fetch(`/api/dashboard?period=${state.period}&month=${encodeURIComponent(state.month)}&card=${encodeURIComponent(state.card)}`,{cache:'no-store'});
    const data=await response.json();
    if(!response.ok)throw new Error(data.error||'Could not load dashboard');
    renderDashboard(data);
    if(announce)showToast(`Showing ${data.period.label}`);
  }catch(error){
    document.querySelector('#spentNote').textContent='Start the ClearSpend local server to load your data.';
    showToast(error.message,'Connection error');
  }
}

function renderDashboard(data){
  const availableCardKeys=(data.cards||[]).map(card=>card.key);
  if(state.card!=='all'&&!availableCardKeys.includes(state.card)){
    state.card='all';
    loadDashboard();
    return;
  }
  state.data=data;
  const m=data.metrics;
  document.querySelector('#spentValue').textContent=money(m.spent);
  document.querySelector('#refundValue').textContent=money(m.refunds);
  document.querySelector('#transactionValue').textContent=m.transactions.toLocaleString();
  document.querySelector('#dailyValue').textContent=money(m.daily_average);
  document.querySelector('#activeDays').textContent=`across ${m.active_days} active days`;
  document.querySelector('#spentNote').textContent=`Calculated from ${m.transactions.toLocaleString()} imported transactions`;
  document.querySelector('#navTransactionCount').textContent=m.transactions.toLocaleString();
  renderMonthFilter(data.available_months||[],data.period.start);
  document.querySelector('#cardsPeriod').textContent=data.period.label;
  renderCards(data.cards,data.selected_card);
  renderIncome(data.income_summary,data.period);
  renderCategories(data.categories,m.spent);
  renderTransactions(data.recent_transactions);
  renderInsights(data.insights);
  renderTrend(data.trend,data);
  renderImportStatus(data.latest_import);
}

function renderIncome(summary,period){
  const hasIncome=Boolean(summary?.has_income);
  const remaining=Number(summary?.remaining||0);
  const percentage=summary?.remaining_percentage;
  const spentPercentage=Number(summary?.spent_percentage||0);
  const averages=summary?.averages||{};
  document.querySelector('#incomePeriod').textContent=`${period.label} · all cards`;
  document.querySelector('#incomeValue').textContent=hasIncome?money(summary.income):'No income data';
  document.querySelector('#incomeSpendingValue').textContent=money(summary?.spending);
  document.querySelector('#incomeSpendingNote').textContent=`All cards · ${money(summary?.refunds)} refunds deducted`;
  document.querySelector('#incomeRemainingValue').textContent=hasIncome?money(remaining):'—';
  document.querySelector('#incomeRemainingPercent').textContent=hasIncome?`${percentage}% of income remaining`:'Import an income XLSX to calculate the balance';
  const remainingCard=document.querySelector('#incomeRemainingCard');
  const progress=document.querySelector('#incomeProgressBar');
  remainingCard.classList.toggle('over',hasIncome&&remaining<0);
  progress.classList.toggle('over',hasIncome&&spentPercentage>100);
  progress.style.width=`${hasIncome?Math.min(Math.max(spentPercentage,0),100):0}%`;
  const averageRange=averages.start_month&&averages.end_month
    ?`${formatMonth(averages.start_month)} – ${formatMonth(averages.end_month)}`
    :'No monthly history';
  document.querySelector('#incomeAverageScope').textContent=`${averageRange}${averages.current_month_partial?' · current month partial':''}`;
  document.querySelector('#averageSpendingValue').textContent=averages.spending_months?money(averages.spending):'—';
  document.querySelector('#averageSpendingMonths').textContent=averages.spending_months?`${averages.spending_months} spending months · all cards`:'No spending months';
  document.querySelector('#averageLeftValue').textContent=averages.amount_left_months?money(averages.amount_left):'—';
  document.querySelector('#averageLeftMonths').textContent=averages.amount_left_months?`${averages.amount_left_months} months with income`:'No months with income';
  document.querySelector('#averageLeftCard').classList.toggle('negative',averages.amount_left_months&&Number(averages.amount_left)<0);
}

function setIncomeVisibility(hidden){
  incomeHidden=hidden;
  incomePanel.hidden=hidden;
  incomeShowButton.hidden=!hidden;
  try{localStorage.setItem('clearspend-income-hidden',hidden?'1':'0')}catch(_error){}
  if(state.data)renderTrend(state.data.trend,state.data);
}

let incomeHidden=false;
try{incomeHidden=localStorage.getItem('clearspend-income-hidden')==='1'}catch(_error){}
setIncomeVisibility(incomeHidden);
document.querySelector('#incomeHideButton').addEventListener('click',()=>setIncomeVisibility(true));
incomeShowButton.addEventListener('click',()=>setIncomeVisibility(false));

function renderMonthFilter(months,start){
  const selected=state.month||(state.period==='month'&&start?start.slice(0,7):'');
  monthFilter.innerHTML=months.map(month=>`<option value="${month}">${escapeHtml(formatMonth(month))}</option>`).join('');
  if(selected&&months.includes(selected))monthFilter.value=selected;
}

function renderCards(cards,selected){
  cardFilter.innerHTML='<option value="all">All cards</option>'+cards.map(card=>`<option value="${escapeHtml(card.key)}">${escapeHtml(card.product_name)} •• ${escapeHtml(card.card_last4)}</option>`).join('');
  cardFilter.value=selected;
  const list=document.querySelector('#cardList');
  list.innerHTML=cards.length?cards.map(card=>`
    <button class="payment-card ${selected===card.key?'selected':''}" data-card="${escapeHtml(card.key)}">
      <span class="card-logo ${card.provider==='max'?'mc':'visa'}">${card.provider==='max'?'<i></i><b></b>':'MC'}</span>
      <span class="card-info"><strong>${escapeHtml(card.product_name)}</strong><small>•••• ${escapeHtml(card.card_last4)} · ${escapeHtml(card.provider.toUpperCase())}</small></span>
      <span class="card-total"><strong>${money(card.amount)}</strong><small>${card.share}% · ${card.transactions} trx</small></span>
      <span class="card-bar"><i style="width:${Math.min(card.share,100)}%"></i></span>
    </button>`).join(''):'<p>No transactions in this period.</p>';
  list.querySelectorAll('.payment-card').forEach(button=>button.addEventListener('click',()=>{
    state.card=button.dataset.card;cardFilter.value=state.card;loadDashboard(true);
  }));
}

function renderCategories(categories,total){
  const donut=document.querySelector('#categoryDonut');
  const tooltip=document.querySelector('#categoryDonutTooltip');
  document.querySelector('#donutTotal').textContent=`₪${compact(total)}`;
  const cumulative=[];let cursor=0;
  const segments=categories.map((category,index)=>{
    const start=Math.min(cursor,100);cursor=Math.min(cursor+category.share,100);
    cumulative.push(`${colors[index%colors.length]} ${start}% ${cursor}%`);
    return {...category,start,end:cursor};
  });
  if(cursor<100)cumulative.push(`#ececf1 ${cursor}% 100%`);
  donut.style.background=`conic-gradient(${cumulative.join(',')})`;
  donut.setAttribute('aria-label',categories.map(category=>`${category.category}: ${category.share}%`).join(', '));
  donut.onmousemove=event=>{
    const rect=donut.getBoundingClientRect();
    const x=event.clientX-rect.left-rect.width/2;
    const y=event.clientY-rect.top-rect.height/2;
    const distance=Math.hypot(x,y);
    if(distance<47||distance>rect.width/2){tooltip.classList.remove('show');return}
    const angle=(Math.atan2(y,x)*180/Math.PI+450)%360;
    const percentage=angle/3.6;
    const segment=segments.find(item=>percentage>=item.start&&percentage<item.end);
    if(!segment){tooltip.classList.remove('show');return}
    tooltip.textContent=`${segment.category} · ${money(segment.amount)} · ${segment.share}%`;
    tooltip.style.left=`${event.clientX-rect.left}px`;
    tooltip.style.top=`${event.clientY-rect.top}px`;
    tooltip.classList.add('show');
  };
  donut.onmouseleave=()=>tooltip.classList.remove('show');
  document.querySelector('#categoryList').innerHTML=categories.length?categories.map((category,index)=>`
    <button type="button" data-category="${escapeHtml(category.category)}"><i class="cat-dot" style="background:${colors[index%colors.length]}"></i><span>${escapeHtml(category.category)}</span><strong>${money(category.amount)}</strong><em>${category.share}%</em></button>`).join(''):'<div><span>No category data</span></div>';
}

function transactionRow(item){
    const credit=Number(item.amount)<0;
    const initial=(item.merchant_raw||'?').trim().charAt(0).toUpperCase();
    return `<tr>
      <td><span class="merchant-icon ${credit?'shufersal':'zara'}">${escapeHtml(initial)}</span><span><strong>${escapeHtml(item.merchant_raw)}</strong><small>${escapeHtml(item.provider.toUpperCase())} statement</small></span></td>
      <td><span class="tag ${item.category==='Needs review'?'amber-tag':''}">${escapeHtml(item.category)}</span>${item.subcategory?`<small class="subcategory">${escapeHtml(item.subcategory)}</small>`:''}</td>
      <td><span class="tiny-card ${item.provider==='max'?'mc-bg':'visa-bg'}">${item.provider==='max'?'M':'I'}</span>•• ${escapeHtml(item.card_last4)}</td>
      <td><strong>${reportingPeriod(item)}</strong><small>${escapeHtml(reportingSource(item.billing_month_source))}</small></td>
      <td class="right ${credit?'':'negative'}">${credit?'+':'−'}${money(Math.abs(item.amount))}</td>
    </tr>`;
}

function renderTransactions(transactions){
  document.querySelector('#transactionRows').innerHTML=transactions.length?transactions.map(transactionRow).join(''):'<tr><td>No transactions found.</td><td></td><td></td><td></td><td></td></tr>';
}

function renderInsights(insights){
  const largest=insights.largest_transaction;
  document.querySelector('#insightList').innerHTML=`
    <button class="insight warning" data-action="mapping"><span class="insight-icon">!</span><span><strong>${insights.merchants_needing_review} merchants need classification</strong><small>Open the mapping queue to assign a category and subcategory.</small></span><b>›</b></button>
    <button class="insight info" data-action="duplicates"><span class="insight-icon">↗</span><span><strong>${insights.duplicate_rows_prevented} duplicate rows prevented</strong><small>Open the import audit to see how duplicate files and rows were handled.</small></span><b>›</b></button>
    <button class="insight success" data-action="largest"><span class="insight-icon">${largest?'₪':'✓'}</span><span><strong>${largest?`${money(largest.amount)} largest charge`:'Imports look healthy'}</strong><small>${largest?escapeHtml(largest.merchant_raw):'No import issues detected.'}</small></span><b>›</b></button>`;
}

const chartSize={width:720,height:204,top:14,bottom:218};
const axisTicks=max=>[max,max*.75,max*.5,max*.25,0].map(value=>`<span>${value?`₪${compact(value)}`:'₪0'}</span>`).join('');
const localDateKey=value=>`${value.getFullYear()}-${String(value.getMonth()+1).padStart(2,'0')}-${String(value.getDate()).padStart(2,'0')}`;
function renderXAxis(points,showLabel,formatLabel){
  const count=points.length;
  document.querySelector('#xAxis').innerHTML=points.map((point,index)=>showLabel(index,count)?`<span style="left:${((index+.5)/count*100).toFixed(3)}%">${escapeHtml(formatLabel(point))}</span>`:'').join('');
}
function chartTooltip(event,html){
  const tooltip=document.querySelector('#trendTooltip'),wrap=document.querySelector('.chart-wrap'),rect=wrap.getBoundingClientRect();
  tooltip.innerHTML=html;tooltip.style.left=`${Math.min(Math.max(event.clientX-rect.left,75),rect.width-75)}px`;tooltip.style.top=`${Math.max(event.clientY-rect.top-12,22)}px`;tooltip.classList.add('show');
}
function bindTrendTooltips(dataPoints,content){
  const tooltip=document.querySelector('#trendTooltip');
  document.querySelectorAll('[data-trend-index]').forEach(hit=>{
    const show=event=>chartTooltip(event,content(dataPoints[Number(hit.dataset.trendIndex)]));
    hit.addEventListener('mousemove',show);hit.addEventListener('click',show);hit.addEventListener('mouseleave',()=>tooltip.classList.remove('show'));
  });
}
function renderTrend(points,data){
  const bars=document.querySelector('#trendBars'),hits=document.querySelector('#trendHitAreas'),line=document.querySelector('#cumulativeLine'),threshold=document.querySelector('#incomeThreshold'),rightAxis=document.querySelector('#rightYAxis'),chart=document.querySelector('#trendChart'),legend=document.querySelector('#trendLegend'),tooltip=document.querySelector('#trendTooltip');
  bars.innerHTML='';hits.innerHTML='';line.hidden=true;threshold.hidden=true;rightAxis.hidden=true;tooltip.classList.remove('show');chart.parentElement.classList.remove('dual-axis');
  document.querySelector('#trendTitle').textContent=data.period.key==='month'?'Purchase activity':'Income and spending';
  const canShowIncome=!incomeHidden&&state.card==='all'&&Boolean(data.income_summary?.has_income);
  if(!points.length){const monthly=data.period.key==='month';document.querySelector('#xAxis').innerHTML=`<span style="left:50%">${monthly?'No purchase data':'No spending data'}</span>`;document.querySelector('#yAxis').innerHTML=axisTicks(0);legend.innerHTML=`<span><i class="legend-spending"></i>${monthly?'Purchases':'Spending'}</span>`;document.querySelector('#trendSubtitle').textContent=monthly?`No purchases made during ${data.period.label}`:'No spending data';return}
  if(data.period.key==='month')renderMonthlyTrend(points,data);else renderMonthlyComparison(points,data,canShowIncome);
}
function renderMonthlyTrend(points,data){
  const {width,height,bottom}=chartSize,activity=new Map(points.map(point=>[point.bucket,point]));
  const categoryNames=(data.categories||[]).map(item=>item.category);
  points.forEach(point=>(point.categories||[]).forEach(item=>{if(!categoryNames.includes(item.category))categoryNames.push(item.category)}));
  const categoryColors=new Map(categoryNames.map((category,index)=>[category,colors[index%colors.length]]));
  const categoryPositions=new Map(categoryNames.map((category,index)=>[category,index]));
  const start=new Date(`${data.period.start}T12:00:00`),periodEnd=new Date(`${data.period.end}T12:00:00`),today=new Date(),sameCurrentMonth=start.getFullYear()===today.getFullYear()&&start.getMonth()===today.getMonth(),end=sameCurrentMonth&&today<periodEnd?today:periodEnd,daily=[];
  for(let cursor=new Date(start);cursor<=end;cursor.setDate(cursor.getDate()+1)){const key=localDateKey(cursor),point=activity.get(key);daily.push({bucket:key,amount:Number(point?.amount)||0,categories:point?.categories||[]})}
  let cumulative=0;daily.forEach(point=>{cumulative+=point.amount;point.cumulative=cumulative;point.cumulativeDisplay=Math.max(cumulative,0)});
  daily.forEach(point=>{point.gross=point.categories.reduce((sum,item)=>sum+Math.max(Number(item.amount)||0,0),0);point.refunds=Math.abs(point.categories.reduce((sum,item)=>sum+Math.min(Number(item.amount)||0,0),0))});
  const dailyMax=Math.max(...daily.map(point=>point.gross),1),rightMax=Math.max(...daily.map(point=>point.cumulativeDisplay),1),slot=width/daily.length,barWidth=Math.max(Math.min(slot*.58,15),3);
  document.querySelector('#trendBars').innerHTML=daily.map((point,index)=>{const x=index*slot+(slot-barWidth)/2;let cursor=bottom;const segments=[...point.categories].filter(item=>Number(item.amount)>0).sort((a,b)=>(categoryPositions.get(a.category)??999)-(categoryPositions.get(b.category)??999)).map(item=>{const segmentHeight=Number(item.amount)/dailyMax*height;cursor-=segmentHeight;return `<rect class="category-segment" x="${x.toFixed(1)}" y="${cursor.toFixed(1)}" width="${barWidth.toFixed(1)}" height="${Math.max(segmentHeight,.8).toFixed(1)}" fill="${categoryColors.get(item.category)||colors[0]}"/>`}).join('');const refund=point.refunds?`<rect class="refund-marker" x="${x.toFixed(1)}" y="${(bottom-3).toFixed(1)}" width="${barWidth.toFixed(1)}" height="3"/>`:'';return segments+refund}).join('');
  const coords=daily.map((point,index)=>({x:index*slot+slot/2,y:bottom-(point.cumulativeDisplay/rightMax)*height}));
  const path=coords.map((point,index)=>`${index?'L':'M'}${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(' '),line=document.querySelector('#cumulativeLine');line.setAttribute('d',path);line.hidden=false;
  document.querySelector('#trendHitAreas').innerHTML=daily.map((_,index)=>`<rect class="trend-hit" data-trend-index="${index}" x="${(index*slot).toFixed(1)}" y="14" width="${slot.toFixed(1)}" height="204"/>`).join('');
  document.querySelector('#yAxis').innerHTML=axisTicks(dailyMax);const rightAxis=document.querySelector('#rightYAxis');rightAxis.innerHTML=axisTicks(rightMax);rightAxis.hidden=false;document.querySelector('.chart-wrap').classList.add('dual-axis');
  const labelStep=Math.ceil(daily.length/7);renderXAxis(daily,(index,count)=>index===0||index===count-1||index%labelStep===0,point=>String(Number(point.bucket.slice(-2))));
  document.querySelector('#trendLegend').innerHTML='<span><i class="legend-stack"></i>Categories by day</span><span><i class="legend-refund"></i>Refunds</span><span><i class="legend-cumulative"></i>Cumulative purchase value</span>';
  const summary=data.purchase_activity_summary||{},scope=state.card==='all'?'all cards':'selected card';document.querySelector('#trendSubtitle').textContent=`Purchases made during ${data.period.label} · installments counted once · ${scope} · ${money(summary.total||0)} total · billed charges ${money(summary.billed_charges||0)}`;
  bindTrendTooltips(daily,point=>{const rows=[...point.categories].sort((a,b)=>Math.abs(Number(b.amount))-Math.abs(Number(a.amount))).map(item=>`<span class="tooltip-category" dir="auto"><i style="background:${Number(item.amount)<0?'#db5c69':categoryColors.get(item.category)||colors[0]}"></i><span>${escapeHtml(item.category)}</span><b>${money(item.amount)}</b></span>`).join('');return `<strong>${formatDate(point.bucket)} · ${money(point.amount)} net</strong>${rows||'<span>No purchases</span>'}${point.refunds?`<span class="tooltip-refund-summary">Gross ${money(point.gross)} · refunds ${money(-point.refunds)}</span>`:''}<span>Cumulative ${money(point.cumulative)}</span>`});
}
function renderMonthlyComparison(points,data,showIncome){
  const {width,height,bottom}=chartSize,values=points.flatMap(point=>showIncome?[Math.max(Number(point.amount)||0,0),Math.max(Number(point.income)||0,0)]:[Math.max(Number(point.amount)||0,0)]),max=Math.max(...values,1),slot=width/points.length,groupWidth=Math.min(slot*.68,38),gap=3,barWidth=showIncome?(groupWidth-gap)/2:Math.min(groupWidth,24);
  document.querySelector('#trendBars').innerHTML=points.map((point,index)=>{const center=index*slot+slot/2,spending=Math.max(Number(point.amount)||0,0),spendingHeight=spending/max*height;if(!showIncome){return `<rect class="spending-bar" x="${(center-barWidth/2).toFixed(1)}" y="${(bottom-spendingHeight).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${spendingHeight.toFixed(1)}" rx="3"/>`}const income=Math.max(Number(point.income)||0,0),incomeHeight=income/max*height;return `<rect class="income-bar" x="${(center-groupWidth/2).toFixed(1)}" y="${(bottom-incomeHeight).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${incomeHeight.toFixed(1)}" rx="3"/><rect class="spending-bar" x="${(center+gap/2).toFixed(1)}" y="${(bottom-spendingHeight).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${spendingHeight.toFixed(1)}" rx="3"/>`}).join('');
  document.querySelector('#trendHitAreas').innerHTML=points.map((_,index)=>`<rect class="trend-hit" data-trend-index="${index}" x="${(index*slot).toFixed(1)}" y="14" width="${slot.toFixed(1)}" height="204"/>`).join('');document.querySelector('#yAxis').innerHTML=axisTicks(max);
  const labelStep=Math.ceil(points.length/8);renderXAxis(points,(index,count)=>index===0||index===count-1||index%labelStep===0,point=>new Intl.DateTimeFormat('en-GB',{month:'short',year:points.length>12?'2-digit':undefined}).format(new Date(`${point.bucket}-01T12:00:00`)));
  document.querySelector('#trendLegend').innerHTML=`${showIncome?'<span><i class="legend-income"></i>Income</span>':''}<span><i class="legend-spending"></i>Net spending</span>`;
  const scope=state.card==='all'?'all cards':'selected card',incomeNote=incomeHidden?' · income hidden':state.card!=='all'?' · income comparison available for all cards':'';document.querySelector('#trendSubtitle').textContent=`Monthly spending · ${scope}${incomeNote}`;
  bindTrendTooltips(points,point=>{const spending=Number(point.amount)||0,income=Number(point.income)||0;return `<strong>${formatMonth(point.bucket)}</strong><span>Net spending ${money(spending)}</span>${showIncome?`<span class="tooltip-income">Income ${money(income)} · left ${money(income-spending)}</span>`:''}`});
}

function renderImportStatus(latest){
  document.querySelector('#lastUpdated').textContent=latest?`Last import: ${latest.original_name} · ${latest.status}`:'No statements imported yet';
}

document.querySelector('#periodTabs').addEventListener('click',event=>{
  if(!event.target.dataset.period)return;
  state.period=event.target.dataset.period;
  document.querySelectorAll('#periodTabs button').forEach(button=>button.classList.toggle('active',button===event.target));
  loadDashboard(true);
});
cardFilter.addEventListener('change',()=>{state.card=cardFilter.value;loadDashboard(true)});
monthFilter.addEventListener('change',()=>{
  state.month=monthFilter.value;state.period='month';
  document.querySelectorAll('#periodTabs button').forEach(button=>button.classList.toggle('active',button.dataset.period==='month'));
  loadDashboard(true);
});

const detailModal=document.querySelector('#detailModal');
const detailContent=document.querySelector('#detailContent');
const detailTools=document.querySelector('#detailTools');
function setDetailModal(show){detailModal.classList.toggle('show',show);detailModal.setAttribute('aria-hidden',String(!show));if(show)document.querySelector('#detailClose').focus()}
document.querySelector('#detailClose').addEventListener('click',()=>setDetailModal(false));
detailModal.addEventListener('click',event=>{if(event.target===detailModal)setDetailModal(false)});

function setActiveNav(element){
  const navItem=element?.closest('.nav-item');
  if(!navItem)return;
  document.querySelectorAll('.nav-item').forEach(item=>item.classList.remove('active'));
  navItem.classList.add('active');
}

async function openDetail(view,source,initialSearch=''){
  setActiveNav(source);
  state.detailMode=view;state.activeCategory='';
  const isTransactions=view==='transactions';
  document.querySelector('#detailEyebrow').textContent=isTransactions?'TRANSACTION EXPLORER':'CATEGORY BREAKDOWN';
  document.querySelector('#detailTitle').textContent=isTransactions?'All transactions':'All categories';
  document.querySelector('#detailSubtitle').textContent=`${state.data?.period.label||''} · ${state.card==='all'?'all cards':'selected card'}`;
  detailTools.innerHTML=isTransactions?`<label class="detail-search"><span>⌕</span><input id="transactionSearch" type="search" value="${escapeHtml(initialSearch)}" placeholder="Search merchant or category"></label>`:'';
  detailContent.innerHTML='<p class="loading-state">Loading local data…</p>';
  setDetailModal(true);
  try{
    const response=await fetch(`/api/${view}?period=${state.period}&month=${encodeURIComponent(state.month)}&card=${encodeURIComponent(state.card)}`,{cache:'no-store'});
    const data=await response.json();if(!response.ok)throw new Error(data.error||`Could not load ${view}`);
    if(isTransactions){
      state.detailTransactions=data.transactions;
      state.detailSort={key:'transaction_date',direction:'desc'};
      const initialTerm=initialSearch.trim().toLocaleLowerCase();
      const transactionText=item=>Object.values(item).filter(value=>value!==null).join(' ').toLocaleLowerCase();
      const initialRows=initialTerm?state.detailTransactions.filter(item=>transactionText(item).includes(initialTerm)):data.transactions;
      renderFullTransactions(initialRows,data.total,initialTerm);
      document.querySelector('#transactionSearch').addEventListener('input',event=>{
        const term=event.target.value.trim().toLocaleLowerCase();
        const filtered=state.detailTransactions.filter(item=>transactionText(item).includes(term));
        renderFullTransactions(filtered,data.total,term);
      });
    }else renderFullCategories(data);
  }catch(error){detailContent.innerHTML=`<p class="empty-state">${escapeHtml(error.message)}</p>`}
}

const transactionColumns=[
  ['merchant','Merchant'],['category','Category / subcategory'],['card','Provider / card / source'],
  ['transaction_date','Transaction date'],['billing_date','Billing date'],['billing_month','Reporting month'],['amount','Charged amount'],
  ['original_amount','Original amount'],['transaction_type','Transaction type'],['execution_method','Execution method'],
  ['voucher_number','Voucher'],['exchange_rate','Exchange rate'],['notes','Notes'],
];
const transactionNumericKeys=new Set(['amount','original_amount','exchange_rate']);
const transactionCollator=new Intl.Collator(['he','en'],{numeric:true,sensitivity:'base'});
const transactionTextValue=value=>String(value??'').trim();
function transactionSortValue(item,key){
  if(key==='merchant')return `${transactionTextValue(item.merchant_display_name)} ${transactionTextValue(item.merchant_raw)} ${transactionTextValue(item.merchant_normalized)}`;
  if(key==='category')return `${transactionTextValue(item.category)} ${transactionTextValue(item.subcategory)}`;
  if(key==='card')return `${transactionTextValue(item.provider)} ${transactionTextValue(item.card_last4)} ${transactionTextValue(item.source_sheet)}`;
  return item[key];
}
function sortedTransactionRows(rows,sort){
  return [...rows].sort((left,right)=>{
    const leftValue=transactionSortValue(left,sort.key);const rightValue=transactionSortValue(right,sort.key);
    const leftEmpty=leftValue===null||leftValue===undefined||leftValue==='';
    const rightEmpty=rightValue===null||rightValue===undefined||rightValue==='';
    if(leftEmpty||rightEmpty){if(leftEmpty&&rightEmpty)return 0;return leftEmpty?1:-1}
    let comparison;
    if(transactionNumericKeys.has(sort.key))comparison=Number(leftValue)-Number(rightValue);
    else comparison=transactionCollator.compare(String(leftValue),String(rightValue));
    return sort.direction==='asc'?comparison:-comparison;
  });
}
function fullTransactionRow(item){
  return `<tr>
    <td><strong>${escapeHtml(item.merchant_raw)}</strong><small>${item.merchant_display_name&&item.merchant_display_name!==item.merchant_raw?`Display: ${escapeHtml(item.merchant_display_name)} · `:''}${escapeHtml(item.merchant_normalized)}</small></td>
    <td><span class="tag editable-category-tag ${item.category==='Needs review'?'amber-tag':''}"><span>${escapeHtml(item.category)}</span><button type="button" class="transaction-category-icon" data-edit-transaction="${item.id}" aria-label="Change category for ${escapeHtml(item.merchant_display_name||item.merchant_raw)}" title="Change category">✎</button></span>${item.category_source==='transaction_override'?'<i class="transaction-override-label">One-off correction</i>':''}<small>${displayValue(item.subcategory)}</small></td>
    <td><strong>${escapeHtml(item.provider.toUpperCase())} •• ${escapeHtml(item.card_last4)}</strong><small>${displayValue(item.source_sheet)}</small></td>
    <td>${formatDate(item.transaction_date)}</td><td>${formatDate(item.billing_date)}</td>
    <td><strong>${formatMonth(item.billing_month)}</strong><small>${escapeHtml(reportingSource(item.billing_month_source))}${item.installment_number?` · ${item.installment_number}/${item.installment_total||'?'}`:''}</small></td>
    <td class="right"><strong>${sourceAmount(item.amount,item.charged_currency)}</strong></td>
    <td class="right">${sourceAmount(item.original_amount,item.original_currency)}</td>
    <td>${displayValue(item.transaction_type)}</td><td>${displayValue(item.execution_method)}</td>
    <td>${displayValue(item.voucher_number)}</td><td>${displayValue(item.exchange_rate)}</td><td class="notes-cell">${displayValue(item.notes)}</td>
  </tr>`;
}
function transactionSortHeaders(sort,attribute){
  return transactionColumns.map(([key,label],index)=>{
    const active=sort.key===key;
    const direction=active?sort.direction:'none';
    const icon=active?(direction==='asc'?'↑':'↓'):'↕';
    const right=[6,7].includes(index)?' class="right"':'';
    return `<th${right} aria-sort="${direction==='none'?'none':direction==='asc'?'ascending':'descending'}"><button type="button" ${attribute}="${key}">${label}<span aria-hidden="true">${icon}</span></button></th>`;
  }).join('');
}

function renderFullTransactions(rows,total,term=''){
  const sortedRows=sortedTransactionRows(rows,state.detailSort);
  const label=term?`${rows.length.toLocaleString()} matches`:`${total.toLocaleString()} transactions`;
  const sortHeaders=transactionSortHeaders(state.detailSort,'data-sort');
  detailContent.innerHTML=`<div class="detail-summary"><strong>${label}</strong><span>Sorted by ${escapeHtml(transactionColumns.find(([key])=>key===state.detailSort.key)?.[1]||'Transaction date')} ${state.detailSort.direction==='asc'?'ascending':'descending'} · up to 1,000 rows</span></div><div class="table-wrap detail-table"><table class="full-transaction-table"><thead><tr>${sortHeaders}</tr></thead><tbody>${sortedRows.length?sortedRows.map(fullTransactionRow).join(''):'<tr><td colspan="13">No matching transactions.</td></tr>'}</tbody></table></div>`;
  detailContent.querySelectorAll('[data-sort]').forEach(button=>button.addEventListener('click',()=>{
    const key=button.dataset.sort;
    state.detailSort=state.detailSort.key===key
      ?{key,direction:state.detailSort.direction==='asc'?'desc':'asc'}
      :{key,direction:'asc'};
    renderFullTransactions(rows,total,term);
  }));
}

function renderFullCategories(data){
  detailContent.innerHTML=`<div class="detail-summary"><strong>${data.categories.length} categories</strong><span>Select a category to view its transactions</span></div><div class="category-detail-list">${data.categories.map((item,index)=>`<button type="button" class="category-detail" data-category="${escapeHtml(item.category)}"><i style="background:${colors[index%colors.length]}"></i><span><strong>${escapeHtml(item.category)}</strong><small>${item.transactions} transactions · ${item.merchants} merchants</small><b><em style="width:${Math.min(item.share,100)}%"></em></b></span><span><strong>${money(item.amount)}</strong><small>${item.share}% · View transactions →</small></span></button>`).join('')}</div>`;
}

function filteredCategoryTransactions(){
  const term=state.categorySearch.trim().toLocaleLowerCase();
  if(!term)return state.categoryTransactions;
  return state.categoryTransactions.filter(item=>Object.values(item).filter(value=>value!==null).join(' ').toLocaleLowerCase().includes(term));
}

function renderCategoryTransactionView(){
  const rows=filteredCategoryTransactions();
  detailTools.querySelectorAll('[data-category-view]').forEach(button=>button.classList.toggle('active',button.dataset.categoryView===state.categoryView));
  if(state.categoryView==='individual'){
    renderFullTransactions(rows,state.categoryTransactions.length,state.categorySearch);
    return;
  }
  renderGroupedCategoryTransactions(rows);
}

function renderGroupedCategoryTransactions(rows){
  const groupsByKey=new Map();
  rows.forEach(item=>{
    const identity=item.canonical_merchant_id||item.merchant_normalized;
    const key=`${identity}::${item.category}`;
    if(!groupsByKey.has(key))groupsByKey.set(key,{
      key,merchant:item.merchant_display_name||item.merchant_raw,category:item.category,
      transactions:0,net_amount:0,latest_date:'',cards:new Set(),variants:new Set(),rows:[],
    });
    const group=groupsByKey.get(key);
    group.transactions+=1;
    group.net_amount+=Number(item.amount)||0;
    if(item.transaction_date&&item.transaction_date>group.latest_date)group.latest_date=item.transaction_date;
    group.cards.add(`${item.provider.toUpperCase()} ••${item.card_last4}`);
    group.variants.add(item.merchant_raw);
    group.rows.push(item);
  });
  const collator=new Intl.Collator(['he','en'],{numeric:true,sensitivity:'base'});
  const groups=[...groupsByKey.values()].sort((left,right)=>{
    const key=state.categoryGroupSort.key;
    let comparison=0;
    if(key==='merchant')comparison=collator.compare(left.merchant,right.merchant);
    else if(key==='cards')comparison=left.cards.size-right.cards.size;
    else if(key==='latest_date')comparison=collator.compare(left.latest_date||'',right.latest_date||'');
    else comparison=Number(left[key])-Number(right[key]);
    return state.categoryGroupSort.direction==='asc'?comparison:-comparison;
  });
  const columns=[['merchant','Merchant'],['transactions','Transactions'],['latest_date','Latest transaction'],['cards','Cards used'],['net_amount','Net total']];
  const headers=columns.map(([key,label],index)=>{
    const active=state.categoryGroupSort.key===key;
    const direction=active?state.categoryGroupSort.direction:'none';
    const icon=active?(direction==='asc'?'↑':'↓'):'↕';
    return `<th${index===4?' class="right"':''} aria-sort="${direction==='none'?'none':direction==='asc'?'ascending':'descending'}"><button type="button" data-group-sort="${key}">${label}<span aria-hidden="true">${icon}</span></button></th>`;
  }).join('');
  const body=groups.map(group=>{
    const expanded=state.expandedMerchantGroups.has(group.key);
    const variants=group.variants.size;
    const cards=[...group.cards].sort(collator.compare).join(' · ');
    const expandedSort=state.categoryExpandedSort.get(group.key)||{key:'transaction_date',direction:'desc'};
    const expandedHeaders=transactionSortHeaders(expandedSort,'data-expanded-sort');
    const expandedRows=sortedTransactionRows(group.rows,expandedSort).map(fullTransactionRow).join('');
    return `<tr class="merchant-group-row" data-merchant-group="${escapeHtml(group.key)}" tabindex="0" aria-expanded="${expanded}">
      <td><span class="group-chevron" aria-hidden="true">${expanded?'⌄':'›'}</span><span><strong>${escapeHtml(group.merchant)}</strong><small>${variants} original ${variants===1?'name':'names'}</small></span></td>
      <td><strong>${group.transactions.toLocaleString()}</strong></td>
      <td>${formatDate(group.latest_date)}</td>
      <td>${escapeHtml(cards)}</td>
      <td class="right"><strong>${money(group.net_amount)}</strong></td>
    </tr>${expanded?`<tr class="merchant-group-details"><td colspan="5"><div class="expanded-transaction-panel"><p>All transaction details included in ${escapeHtml(group.merchant)} · sorted by ${escapeHtml(transactionColumns.find(([key])=>key===expandedSort.key)?.[1]||'Transaction date')} ${expandedSort.direction==='asc'?'ascending':'descending'}</p><div class="expanded-transaction-scroll"><table class="full-transaction-table expanded-transaction-table" data-expanded-group="${escapeHtml(group.key)}"><thead><tr>${expandedHeaders}</tr></thead><tbody>${expandedRows}</tbody></table></div></div></td></tr>`:''}`;
  }).join('');
  const matchLabel=state.categorySearch?`${rows.length.toLocaleString()} matching transactions · ${groups.length.toLocaleString()} merchants`:`${rows.length.toLocaleString()} transactions · ${groups.length.toLocaleString()} merchants`;
  detailContent.innerHTML=`<div class="detail-summary"><strong>${matchLabel}</strong><span>Grouped by approved merchant name and category · click a merchant to expand</span></div><div class="table-wrap detail-table"><table class="merchant-group-table"><thead><tr>${headers}</tr></thead><tbody>${body||'<tr><td colspan="5">No matching transactions.</td></tr>'}</tbody></table></div>`;
  detailContent.querySelectorAll('[data-group-sort]').forEach(button=>button.addEventListener('click',()=>{
    const key=button.dataset.groupSort;
    state.categoryGroupSort=state.categoryGroupSort.key===key
      ?{key,direction:state.categoryGroupSort.direction==='asc'?'desc':'asc'}
      :{key,direction:'asc'};
    renderCategoryTransactionView();
  }));
  detailContent.querySelectorAll('[data-expanded-sort]').forEach(button=>button.addEventListener('click',event=>{
    event.stopPropagation();
    const table=button.closest('[data-expanded-group]');
    const groupKey=table.dataset.expandedGroup;
    const key=button.dataset.expandedSort;
    const current=state.categoryExpandedSort.get(groupKey)||{key:'transaction_date',direction:'desc'};
    state.categoryExpandedSort.set(groupKey,current.key===key
      ?{key,direction:current.direction==='asc'?'desc':'asc'}
      :{key,direction:'asc'});
    renderCategoryTransactionView();
  }));
  const toggleGroup=row=>{
    const key=row.dataset.merchantGroup;
    if(state.expandedMerchantGroups.has(key))state.expandedMerchantGroups.delete(key);else state.expandedMerchantGroups.add(key);
    renderCategoryTransactionView();
  };
  detailContent.querySelectorAll('[data-merchant-group]').forEach(row=>{
    row.addEventListener('click',()=>toggleGroup(row));
    row.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();toggleGroup(row)}});
  });
}

async function openCategoryTransactions(category,source){
  setActiveNav(source);
  state.detailMode='category-transactions';state.activeCategory=category;
  document.querySelector('#detailEyebrow').textContent='CATEGORY TRANSACTIONS';
  document.querySelector('#detailTitle').textContent=category;
  document.querySelector('#detailSubtitle').textContent=`${state.data?.period.label||''} · ${state.card==='all'?'all cards':'selected card'}`;
  detailTools.innerHTML='<div class="category-transaction-tools"><label class="detail-search"><span>⌕</span><input id="transactionSearch" type="search" placeholder="Search within this category"></label><div class="category-view-toggle" role="group" aria-label="Transaction view"><button type="button" class="active" data-category-view="grouped">Grouped by merchant</button><button type="button" data-category-view="individual">Individual transactions</button></div></div>';
  detailContent.innerHTML='<p class="loading-state">Loading category transactions…</p>';setDetailModal(true);
  try{
    const response=await fetch(`/api/transactions?period=${state.period}&month=${encodeURIComponent(state.month)}&card=${encodeURIComponent(state.card)}&category=${encodeURIComponent(category)}`,{cache:'no-store'});
    const data=await response.json();if(!response.ok)throw new Error(data.error||'Could not load category transactions');
    const categoryRows=data.transactions;
    state.categoryTransactions=categoryRows;
    state.categoryView='grouped';
    state.categorySearch='';
    state.categoryGroupSort={key:'latest_date',direction:'desc'};
    state.expandedMerchantGroups=new Set();
    state.categoryExpandedSort=new Map();
    state.detailSort={key:'transaction_date',direction:'desc'};
    renderCategoryTransactionView();
    document.querySelector('#transactionSearch').addEventListener('input',event=>{
      state.categorySearch=event.target.value.trim();
      renderCategoryTransactionView();
    });
    detailTools.querySelectorAll('[data-category-view]').forEach(button=>button.addEventListener('click',()=>{
      state.categoryView=button.dataset.categoryView;
      renderCategoryTransactionView();
    }));
  }catch(error){detailContent.innerHTML=`<p class="empty-state">${escapeHtml(error.message)}</p>`}
}

async function fetchMappingData(){
  const response=await fetch('/api/mapping',{cache:'no-store'});const data=await response.json();
  if(!response.ok)throw new Error(data.error||'Could not load mapping data');
  state.mappingData=data;return data;
}

async function openMapping(source){
  setActiveNav(source);
  document.querySelector('#detailEyebrow').textContent='MERCHANT CLASSIFICATION';
  document.querySelector('#detailTitle').textContent='Import & mapping';
  document.querySelector('#detailSubtitle').textContent='Assign reusable categories and subcategories to unknown merchants.';
  detailTools.innerHTML='<div class="mapping-tools"><label class="detail-search"><span>⌕</span><input id="mappingSearch" type="search" placeholder="Search unmapped merchants"></label><button class="upload-button compact-button" data-action="open-import">Import statement</button></div>';
  detailContent.innerHTML='<p class="loading-state">Loading mapping queue…</p>';setDetailModal(true);
  try{
    const data=await fetchMappingData();renderMappingEditor(data);
    document.querySelector('#mappingSearch').addEventListener('input',event=>renderMappingEditor(data,event.target.value));
  }catch(error){detailContent.innerHTML=`<p class="empty-state">${escapeHtml(error.message)}</p>`}
}

function renderMappingEditor(data,search=''){
  const term=search.trim().toLocaleLowerCase();
  const rows=data.review_merchants.filter(item=>`${item.merchant_raw} ${item.merchant_normalized}`.toLocaleLowerCase().includes(term));
  const options=data.category_suggestions.map(category=>`<option value="${escapeHtml(category)}"></option>`).join('');
  detailContent.innerHTML=`<datalist id="categorySuggestions">${options}</datalist><div class="mapping-overview"><span><strong>${data.summary.merchants}</strong>Total merchants</span><span><strong>${data.summary.categorized}</strong>Categorized</span><span><strong>${data.summary.needs_review}</strong>Need review</span></div><div class="mapping-editor-head"><strong>${term?`${rows.length} matches`:`${rows.length} unmapped merchants`}</strong><span>Mappings apply to past and future transactions with the same normalized merchant.</span></div><div class="mapping-editor-list">${rows.length?rows.map(item=>`<form class="mapping-row" data-merchant="${escapeHtml(item.merchant_normalized)}"><div class="mapping-merchant"><strong>${escapeHtml(item.merchant_raw)}</strong><small>${item.transactions} transactions · ${money(item.amount)}</small></div><label><span>Category</span><input name="category" list="categorySuggestions" required placeholder="e.g. Shopping"></label><label><span>Subcategory</span><input name="subcategory" placeholder="e.g. Clothing"></label><button type="submit">Save</button></form>`).join(''):'<p class="empty-state">No unmapped merchants match this search.</p>'}</div>`;
}

async function saveMerchantMapping(form){
  const button=form.querySelector('button');button.disabled=true;button.textContent='Saving…';
  const payload={merchant_normalized:form.dataset.merchant,category:form.elements.category.value,subcategory:form.elements.subcategory.value};
  try{
    const response=await fetch('/api/mapping',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const result=await response.json();if(!response.ok)throw new Error(result.error||'Could not save mapping');
    showToast(`${result.transactions_updated} transactions updated`,'Mapping saved');
    await loadDashboard();await openMapping(null);
  }catch(error){showToast(error.message,'Mapping failed');button.disabled=false;button.textContent='Save'}
}

async function fetchMerchants(force=false){
  if(state.merchantData&&!force)return state.merchantData;
  const response=await fetch('/api/merchants',{cache:'no-store'});const data=await response.json();
  if(!response.ok)throw new Error(data.error||'Could not load merchants');
  state.merchantData=data;return data;
}

async function openMerchants(source){
  setActiveNav(source);state.detailMode='merchants';state.activeCategory='';
  document.querySelector('#detailEyebrow').textContent='DATA MANAGEMENT';
  document.querySelector('#detailTitle').textContent='Merchants';
  document.querySelector('#detailSubtitle').textContent='Manage display names and reusable category rules. Original statement names remain available.';
  detailTools.innerHTML='<div class="merchant-management-tools"><label class="detail-search"><span>⌕</span><input id="merchantSearch" type="search" placeholder="Search display name or original alias"></label><label class="select-wrap"><span>Category</span><select id="merchantCategoryFilter"><option value="all">All categories</option></select></label></div>';
  detailContent.innerHTML='<p class="loading-state">Loading merchants…</p>';setDetailModal(true);
  try{
    const data=await fetchMerchants(true);
    document.querySelector('#merchantCategoryFilter').innerHTML='<option value="all">All categories</option>'+data.categories.map(category=>`<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`).join('');
    const refresh=()=>renderMerchantManagement(data,document.querySelector('#merchantSearch').value,document.querySelector('#merchantCategoryFilter').value);
    document.querySelector('#merchantSearch').addEventListener('input',refresh);document.querySelector('#merchantCategoryFilter').addEventListener('change',refresh);refresh();
  }catch(error){detailContent.innerHTML=`<p class="empty-state">${escapeHtml(error.message)}</p>`}
}

function renderMerchantManagement(data,search='',category='all'){
  const term=search.trim().toLocaleLowerCase();
  const merchants=data.merchants.filter(item=>{
    const text=`${item.display_name} ${item.aliases.map(alias=>`${alias.merchant_raw} ${alias.merchant_normalized}`).join(' ')}`.toLocaleLowerCase();
    return text.includes(term)&&(category==='all'||item.categories.includes(category));
  });
  const summary=data.summary;
  detailContent.innerHTML=`<div class="merchant-management-grid"><span><strong>${summary.display_identities.toLocaleString()}</strong>Display identities</span><span><strong>${summary.mapped_aliases.toLocaleString()}</strong>Original aliases</span><span><strong>${summary.transactions.toLocaleString()}</strong>Covered transactions</span><span><strong>${summary.multiple_categories.toLocaleString()}</strong>Multiple-category merchants</span></div><div class="mapping-editor-head"><strong>${merchants.length.toLocaleString()} merchants</strong><span>Select a merchant to edit its display name or alias category.</span></div><div class="merchant-list">${merchants.length?merchants.map(item=>`<button type="button" class="merchant-list-row" data-edit-merchant="${escapeHtml(item.canonical_group_id)}"><span><strong>${escapeHtml(item.display_name)}</strong><small>${item.aliases.length} original ${item.aliases.length===1?'name':'names'}</small></span><span><strong>${item.transactions.toLocaleString()}</strong><small>transactions</small></span><span class="merchant-categories">${item.categories.map(value=>`<i>${escapeHtml(value)}</i>`).join('')}</span><span>${formatDate(item.last_seen)}</span><span><strong>${money(item.amount)}</strong><small>absolute activity</small></span><span class="merchant-chevron">›</span></button>`).join(''):'<p class="empty-state">No merchants match these filters.</p>'}</div>`;
}

const merchantEditorModal=document.querySelector('#merchantEditorModal');
const merchantEditorBody=document.querySelector('#merchantEditorBody');
function setMerchantEditor(show){merchantEditorModal.classList.toggle('show',show);merchantEditorModal.setAttribute('aria-hidden',String(!show));if(show)document.querySelector('#merchantEditorClose').focus()}
function merchantCategoryOptions(current){
  const values=new Set([...(state.merchantData?.categories||[]),current]);
  return [...values].filter(Boolean).map(value=>`<option${value===current?' selected':''} value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');
}
function resetMerchantReview(){
  const impact=document.querySelector('#merchantImpact');if(impact)impact.hidden=true;
  document.querySelector('#merchantReviewButton').hidden=false;document.querySelector('#merchantApplyButton').hidden=true;
  document.querySelector('#merchantEditorStatus').textContent='Review the impact before applying changes.';
}
function openMerchantEditor(groupId){
  const merchant=state.merchantData?.merchants.find(item=>item.canonical_group_id===groupId);if(!merchant)return;
  state.activeMerchant=merchant;
  document.querySelector('#merchantEditorTitle').textContent=merchant.display_name;
  document.querySelector('#merchantEditorSubtitle').textContent=`${merchant.aliases.length} aliases · ${merchant.transactions.toLocaleString()} transactions`;
  merchantEditorBody.innerHTML=`<section class="editor-section"><div class="editor-section-head"><div><h3>Display name</h3><p>The clean name shown in grouped rows. Imported merchant descriptions are not replaced.</p></div></div><label class="editor-field-label" for="merchantDisplayName">Display name</label><input class="editor-input" id="merchantDisplayName" value="${escapeHtml(merchant.display_name)}" data-original="${escapeHtml(merchant.display_name)}"></section><section class="editor-section"><div class="editor-section-head"><div><h3>Category rules by original name</h3><p>Each alias can keep a different permanent category, including local and travel variants.</p></div></div><div class="alias-editor"><div class="alias-editor-head"><span>Original statement name</span><span>Permanent category</span></div>${merchant.aliases.map(alias=>`<div class="alias-editor-row"><span><strong>${escapeHtml(alias.merchant_raw)}</strong><small>${escapeHtml(alias.merchant_normalized)} · ${alias.transactions} transactions</small></span><select class="editor-select merchant-alias-category" data-merchant="${escapeHtml(alias.merchant_normalized)}" data-original="${escapeHtml(alias.category)}" data-subcategory="${escapeHtml(alias.subcategory||'')}">${merchantCategoryOptions(alias.category)}</select></div>`).join('')}</div></section><section class="editor-section impact-review" id="merchantImpact" hidden><h4>Impact review</h4><ul id="merchantImpactList"></ul></section>`;
  merchantEditorBody.querySelectorAll('input,select').forEach(control=>control.addEventListener('input',resetMerchantReview));resetMerchantReview();setMerchantEditor(true);
}
function merchantChanges(){
  const merchant=state.activeMerchant;const displayInput=document.querySelector('#merchantDisplayName');
  const changedAliases=[...merchantEditorBody.querySelectorAll('.merchant-alias-category')].filter(select=>select.value!==select.dataset.original);
  return {merchant,displayName:displayInput.value.trim(),displayChanged:displayInput.value.trim()!==merchant.display_name,changedAliases};
}
function reviewMerchantImpact(){
  const {merchant,displayName,displayChanged,changedAliases}=merchantChanges();
  if(!displayName){showToast('Enter a display name before continuing.','Missing display name');return}
  if(!displayChanged&&!changedAliases.length){showToast('Change the display name or an alias category first.','No changes');return}
  const lines=[];
  if(displayChanged)lines.push(`Display name changes from “${escapeHtml(merchant.display_name)}” to “${escapeHtml(displayName)}” for ${merchant.aliases.length} aliases and ${merchant.transactions} existing transactions.`);
  changedAliases.forEach(select=>{const alias=merchant.aliases.find(item=>item.merchant_normalized===select.dataset.merchant);lines.push(`“${escapeHtml(alias.merchant_raw)}” changes from ${escapeHtml(select.dataset.original)} to ${escapeHtml(select.value)} for ${alias.transactions} transactions and future matching imports.`)});
  document.querySelector('#merchantImpactList').innerHTML=lines.map(line=>`<li>${line}</li>`).join('');document.querySelector('#merchantImpact').hidden=false;
  document.querySelector('#merchantReviewButton').hidden=true;document.querySelector('#merchantApplyButton').hidden=false;document.querySelector('#merchantEditorStatus').textContent=`${changedAliases.length} category rule${changedAliases.length===1?'':'s'} · ${displayChanged?'display name change':'display name unchanged'}`;
}
async function applyMerchantChanges(){
  const {merchant,displayName,changedAliases}=merchantChanges();const button=document.querySelector('#merchantApplyButton');button.disabled=true;button.textContent='Applying…';
  const payload={canonical_group_id:merchant.canonical_group_id,display_name:displayName,aliases:changedAliases.map(select=>({merchant_normalized:select.dataset.merchant,category:select.value,subcategory:select.dataset.subcategory}))};
  try{
    const response=await fetch('/api/merchants',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const result=await response.json();if(!response.ok)throw new Error(result.error||'Could not update merchant');
    setMerchantEditor(false);state.merchantData=null;showToast(`${result.aliases_updated} aliases use “${result.display_name}” · ${result.transactions_updated} transactions recategorized`,'Merchant updated');await loadDashboard();await openMerchants(null);
  }catch(error){showToast(error.message,'Merchant update failed')}finally{button.disabled=false;button.textContent='Apply changes'}
}

const transactionEditorModal=document.querySelector('#transactionEditorModal');
const transactionEditorBody=document.querySelector('#transactionEditorBody');
function setTransactionEditor(show){transactionEditorModal.classList.toggle('show',show);transactionEditorModal.setAttribute('aria-hidden',String(!show));if(show)document.querySelector('#transactionEditorClose').focus()}
async function openTransactionEditor(transactionId){
  const transactions=[...state.detailTransactions,...state.categoryTransactions];const transaction=transactions.find(item=>Number(item.id)===Number(transactionId));if(!transaction)return;
  state.activeTransaction=transaction;
  try{
    const merchants=await fetchMerchants();const values=new Set([...merchants.categories,transaction.category]);
    transactionEditorBody.innerHTML=`<div class="transaction-snapshot"><div><span>Merchant</span><strong>${escapeHtml(transaction.merchant_display_name||transaction.merchant_raw)}<small>${escapeHtml(transaction.merchant_raw)}</small></strong></div><div><span>Date</span><strong>${formatDate(transaction.transaction_date)}</strong></div><div><span>Card</span><strong>${escapeHtml(transaction.provider.toUpperCase())} •• ${escapeHtml(transaction.card_last4)}</strong></div><div><span>Amount</span><strong>${sourceAmount(transaction.amount,transaction.charged_currency)}</strong></div></div><div class="editor-section-head"><div><h3>Category correction</h3><p>A saved correction takes priority for this transaction only.</p></div>${transaction.category_source==='transaction_override'?'<span class="transaction-override-label">Already corrected</span>':''}</div><div class="category-correction-grid"><div><label class="editor-field-label">Current category</label><div class="category-correction-current">${escapeHtml(transaction.category)}</div></div><div class="category-correction-arrow">→</div><label><span class="editor-field-label">New category</span><select class="editor-select" id="transactionCategorySelect">${[...values].filter(Boolean).map(value=>`<option${value===transaction.category?' selected':''} value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('')}</select></label></div><div class="correction-explanation"><b>i</b><span>The merchant rule remains “${escapeHtml(transaction.merchant_category||transaction.category)}” for every other transaction and for future imports. The original imported data is preserved.</span></div>`;
    setTransactionEditor(true);
  }catch(error){showToast(error.message,'Could not open correction')}
}
async function saveTransactionCorrection(){
  const transaction=state.activeTransaction;const category=document.querySelector('#transactionCategorySelect')?.value;if(!transaction||!category)return;
  if(category===transaction.category&&transaction.category_source!=='transaction_override'){showToast('Choose a different category for this transaction.','No change');return}
  const button=document.querySelector('#transactionSaveButton');button.disabled=true;button.textContent='Saving…';const mode=state.detailMode;const activeCategory=state.activeCategory;
  try{
    const response=await fetch('/api/transaction-category',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({transaction_id:transaction.id,category,subcategory:''})});const result=await response.json();if(!response.ok)throw new Error(result.error||'Could not save correction');
    setTransactionEditor(false);showToast(`${result.merchant_raw} moved to “${result.category}” for this transaction only.`,'Transaction corrected');await loadDashboard();
    if(mode==='category-transactions'&&activeCategory)await openCategoryTransactions(activeCategory,null);else await openDetail('transactions',null);
  }catch(error){showToast(error.message,'Correction failed')}finally{button.disabled=false;button.textContent='Save correction'}
}

async function openImportAudit(){
  document.querySelector('#detailEyebrow').textContent='DUPLICATE PROTECTION';
  document.querySelector('#detailTitle').textContent='Import audit';
  document.querySelector('#detailSubtitle').textContent='Recent statement imports and duplicate handling.';
  detailTools.innerHTML='';detailContent.innerHTML='<p class="loading-state">Loading import history…</p>';setDetailModal(true);
  try{
    const data=await fetchMappingData();
    detailContent.innerHTML=`<div class="detail-summary"><strong>${state.data?.insights.duplicate_rows_prevented||0} duplicate rows prevented</strong><span>Recent 8 imports</span></div><div class="audit-list">${data.recent_imports.map(item=>`<div><span><strong>${escapeHtml(item.original_name)}</strong><small>${escapeHtml((item.provider||'unknown').toUpperCase())} ${item.card_last4?`•• ${escapeHtml(item.card_last4)}`:''}</small></span><span><strong class="audit-status ${escapeHtml(item.status)}">${escapeHtml(item.status.replaceAll('_',' '))}</strong><small>${item.inserted_rows} inserted · ${item.duplicate_rows} duplicates</small></span></div>`).join('')}</div>`;
  }catch(error){detailContent.innerHTML=`<p class="empty-state">${escapeHtml(error.message)}</p>`}
}

document.addEventListener('click',event=>{
  const transactionEditTarget=event.target.closest('[data-edit-transaction]');
  if(transactionEditTarget){event.preventDefault();openTransactionEditor(transactionEditTarget.dataset.editTransaction);return}
  const merchantEditTarget=event.target.closest('[data-edit-merchant]');
  if(merchantEditTarget){event.preventDefault();openMerchantEditor(merchantEditTarget.dataset.editMerchant);return}
  const categoryTarget=event.target.closest('[data-category]');
  if(categoryTarget){event.preventDefault();openCategoryTransactions(categoryTarget.dataset.category,categoryTarget);return}
  const viewTarget=event.target.closest('[data-view]');
  if(viewTarget){event.preventDefault();openDetail(viewTarget.dataset.view,viewTarget);return}
  const actionTarget=event.target.closest('[data-action]');if(!actionTarget)return;
  event.preventDefault();const action=actionTarget.dataset.action;
  if(action==='overview'){setActiveNav(actionTarget);window.scrollTo({top:0,behavior:'smooth'})}
  else if(action==='cards'){setActiveNav(actionTarget);document.querySelector('#cards').scrollIntoView({behavior:'smooth',block:'center'})}
  else if(action==='insights'){setActiveNav(actionTarget);document.querySelector('#insights').scrollIntoView({behavior:'smooth',block:'center'})}
  else if(action==='merchants')openMerchants(actionTarget)
  else if(action==='mapping')openMapping(actionTarget)
  else if(action==='duplicates')openImportAudit()
  else if(action==='largest')openDetail('transactions',actionTarget,state.data?.insights.largest_transaction?.merchant_raw||'')
  else if(action==='open-import'){setDetailModal(false);document.querySelector('#mappingSummary').hidden=true;setModal(true)}
  else if(action==='recurring')showToast('Recurring-payment detection is the next analysis module.','Not implemented yet');
  else if(action==='cards-help')showToast('Select a card to filter every metric and chart.','Card filtering');
  else if(action==='notifications')showToast(`${state.data?.insights.merchants_needing_review||0} merchants currently need classification.`,'Data review');
  else if(action==='profile')showToast('This dashboard uses your private local workspace.','Local profile');
});
detailContent.addEventListener('submit',event=>{if(event.target.matches('.mapping-row')){event.preventDefault();saveMerchantMapping(event.target)}});

const modal=document.querySelector('#importModal');
const fileInput=document.querySelector('#fileInput');
const importStageBody=document.querySelector('#importStageBody');
const importStepper=document.querySelector('#importStepper');
const importBack=document.querySelector('#importBack');
const importNext=document.querySelector('#importNext');
const importStageHelp=document.querySelector('#importStageHelp');
const importState={step:0,batch:null,decisions:new Map(),reconciled:new Set(),busy:false};
const importStepNames=['Files','Checks','Merchants','Reconcile','Approve'];

function importKey(value){return encodeURIComponent(value)}
function importDecision(encodedKey){return importState.decisions.get(decodeURIComponent(encodedKey))}
function manualReconciliationFiles(){return (importState.batch?.files||[]).filter(file=>file.kind==='statement'&&file.status==='ready'&&file.reconciliation?.status==='manual_required')}
function invalidMerchantDecisions(){return [...importState.decisions.values()].filter(item=>!['needs_review','exclude'].includes(item.resolution)&&(!item.category||item.category==='Needs review'||(item.resolution==='link'&&!item.canonical_group_id)))}
function initializeImportDecisions(){
  importState.decisions.clear();
  for(const merchant of importState.batch?.merchants||[]){
    if(!merchant.needs_review)continue;
    importState.decisions.set(merchant.merchant_normalized,{
      merchant_normalized:merchant.merchant_normalized,
      resolution:merchant.provider_category?'provider':'needs_review',
      category:merchant.provider_category||'Needs review',
      display_name:merchant.display_name||merchant.merchant_raw,
      canonical_group_id:merchant.canonical_group_id||'',
      scope:merchant.provider_category?'exact':'batch'
    });
  }
}

function setModal(show){
  modal.classList.toggle('show',show);modal.setAttribute('aria-hidden',String(!show));
  if(show){renderImportStage();document.querySelector('#modalClose').focus()}
  else closeDisplayMenus();
}
document.querySelector('#uploadBtn').addEventListener('click',()=>{document.querySelector('#mappingSummary').hidden=true;setModal(true)});
document.querySelector('#modalClose').addEventListener('click',()=>setModal(false));
modal.addEventListener('click',event=>{if(event.target===modal)setModal(false)});
document.querySelector('#merchantEditorClose').addEventListener('click',()=>setMerchantEditor(false));document.querySelector('#merchantEditorCancel').addEventListener('click',()=>setMerchantEditor(false));merchantEditorModal.addEventListener('click',event=>{if(event.target===merchantEditorModal)setMerchantEditor(false)});document.querySelector('#merchantReviewButton').addEventListener('click',reviewMerchantImpact);document.querySelector('#merchantApplyButton').addEventListener('click',applyMerchantChanges);
document.querySelector('#transactionEditorClose').addEventListener('click',()=>setTransactionEditor(false));document.querySelector('#transactionEditorCancel').addEventListener('click',()=>setTransactionEditor(false));transactionEditorModal.addEventListener('click',event=>{if(event.target===transactionEditorModal)setTransactionEditor(false)});document.querySelector('#transactionSaveButton').addEventListener('click',saveTransactionCorrection);
document.addEventListener('keydown',event=>{if(event.key==='Escape'){setModal(false);setMerchantEditor(false);setTransactionEditor(false);setDetailModal(false)}});
fileInput.addEventListener('change',()=>analyzeImportFiles(fileInput.files));

function closeDisplayMenus(except=null){
  document.querySelectorAll('.stage-combo-menu').forEach(menu=>{if(menu!==except)menu.hidden=true});
}

function renderImportStage(){
  importStepper.innerHTML=importStepNames.map((name,index)=>`<button type="button" class="import-step ${index===importState.step?'active':''} ${index<importState.step?'done':''}" data-import-step="${index}" ${(!importState.batch&&index)||index>importState.step?'disabled':''}><b>${index<importState.step?'✓':index+1}</b><span>${name}</span></button>`).join('');
  const renderers=[renderImportFiles,renderImportChecks,renderImportMerchants,renderImportReconcile,renderImportApprove];
  importStageBody.innerHTML=importState.busy?'<p class="loading-state">Analyzing files without changing your database…</p>':renderers[importState.step]();
  importBack.disabled=importState.busy||importState.step===0;
  importNext.disabled=importState.busy||importState.step===0||(importState.step===2&&invalidMerchantDecisions().length>0)||(importState.step===3&&manualReconciliationFiles().some(file=>!importState.reconciled.has(file.filename)));
  importNext.textContent=importState.step===4?'Approve & import':'Continue';
  const help=['Select XLSX or PDF statements. Nothing is saved yet.','Confirm the parser and duplicate checks look right.','Resolve unfamiliar merchants or leave them for later.','Compare parsed totals with each original statement.','A database backup is created immediately before import.'];
  importStageHelp.textContent=importState.busy?'Reading files and checking existing records…':help[importState.step];
}

function renderImportFiles(){
  const prior=importState.batch?`<div class="stage-callout">A staged batch is ready with <strong>${importState.batch.files.length} files</strong>. Drop new files below to replace it, or continue reviewing the current batch.</div>`:'';
  return `${prior}<div class="stage-drop" data-browse-import><strong>Drop statements here or click to browse</strong><span>XLSX and PDF · multiple files are supported · analysis does not change the database</span></div>`;
}

function renderImportChecks(){
  const files=importState.batch?.files||[];
  const totals=files.reduce((sum,file)=>({parsed:sum.parsed+(file.parsed||0),newRows:sum.newRows+(file.new_rows||0),duplicates:sum.duplicates+(file.duplicates||0),plans:sum.plans+(file.installment_plans||0)}),{parsed:0,newRows:0,duplicates:0,plans:0});
  return `<div class="stage-summary"><div class="stage-metric"><span>Parsed rows</span><strong>${totals.parsed}</strong><small>Across ${files.length} files</small></div><div class="stage-metric"><span>Ready to add</span><strong>${totals.newRows}</strong><small>Before your review</small></div><div class="stage-metric"><span>Duplicates found</span><strong>${totals.duplicates}</strong><small>Will not be inserted</small></div><div class="stage-metric"><span>Installment plans</span><strong>${totals.plans}</strong><small>Detected from statement data</small></div></div>
  ${(importState.batch?.upload_errors||[]).map(item=>`<div class="stage-callout amber"><strong>${escapeHtml(item.filename)}</strong> — ${escapeHtml(item.error||item.status)}</div>`).join('')}
  <div class="stage-list"><div class="stage-row head"><span>File</span><span>Source</span><span>Period</span><span>Rows</span><span>Status</span></div>${files.map(file=>`<div class="stage-row"><span><strong>${escapeHtml(file.filename)}</strong><small>${escapeHtml(file.format)}${file.product_name?` · ${escapeHtml(file.product_name)}`:''}</small></span><span><strong>${escapeHtml((file.provider||'unknown').toUpperCase())}</strong><small>${file.card_last4?`•• ${escapeHtml(file.card_last4)}`:file.kind==='income'?'Monthly income':'Card not detected'}</small></span><span>${escapeHtml(file.statement_range||'—')}</span><span><strong>${file.new_rows||0} new</strong><small>${file.duplicates||0} duplicate</small></span><span class="stage-badge ${file.status==='ready'?'':'amber'}">${escapeHtml(file.status.replaceAll('_',' '))}</span></div>`).join('')}</div>`;
}

function categoryOptions(selected){
  return [...new Set([...(importState.batch?.categories||[]),selected,'Needs review'].filter(Boolean))].map(value=>`<option value="${escapeHtml(value)}"${value===selected?' selected':''}>${escapeHtml(value)}</option>`).join('');
}

function renderImportMerchants(){
  const merchants=importState.batch?.merchants||[];
  const known=merchants.filter(item=>!item.needs_review).length;
  const review=merchants.filter(item=>item.needs_review);
  if(!review.length)return `<div class="stage-callout"><strong>All ${known} merchants matched existing database rules.</strong> No merchant decisions are needed for this batch.</div>`;
  const invalid=invalidMerchantDecisions().length;
  return `<div class="stage-callout ${invalid?'amber':''}"><strong>${known} merchants matched the database automatically.</strong> Review the ${review.length} merchants below. “Needs review” is safe: transactions import without creating a permanent rule.${invalid?` <strong>${invalid} permanent decision${invalid===1?' needs':'s need'} a category or existing display-name selection.</strong>`:''}</div><div class="stage-list merchant-review-table"><div class="stage-row head"><span>Merchant</span><span>Context</span><span>Resolution</span><span>Category</span><span>Display name</span><span>Apply to</span></div>${review.map(merchant=>renderMerchantDecisionRow(merchant)).join('')}</div>`;
}

function renderMerchantDecisionRow(merchant){
  const decision=importState.decisions.get(merchant.merchant_normalized);
  const key=importKey(merchant.merchant_normalized);
  const rowClass=decision.resolution==='exclude'?'stage-excluded':decision.resolution==='needs_review'?'stage-deferred':'';
  return `<div class="stage-row ${rowClass}" data-merchant-row="${key}"><span><strong>${escapeHtml(merchant.merchant_raw)}</strong><small>${merchant.transactions} transaction${merchant.transactions===1?'':'s'} · ${money(merchant.amount)}</small></span><span><strong>${escapeHtml(merchant.providers.join(', ').toUpperCase())}</strong><small>${formatDate(merchant.first_date)} – ${formatDate(merchant.last_date)}</small></span><select class="stage-control" data-decision-field="resolution" data-key="${key}"><option value="create"${decision.resolution==='create'?' selected':''}>Create new rule</option><option value="link"${decision.resolution==='link'?' selected':''}>Link existing merchant</option>${merchant.provider_category?`<option value="provider"${decision.resolution==='provider'?' selected':''}>Use provider value</option>`:''}<option value="needs_review"${decision.resolution==='needs_review'?' selected':''}>Needs review</option><option value="exclude"${decision.resolution==='exclude'?' selected':''}>Exclude rows</option></select><select class="stage-control" data-decision-field="category" data-key="${key}" ${decision.resolution==='exclude'?'disabled':''}>${categoryOptions(decision.category)}</select>${renderDisplayCombobox(decision,key)}<select class="stage-control" data-decision-field="scope" data-key="${key}" ${decision.resolution==='exclude'?'disabled':''}><option value="exact"${decision.scope==='exact'?' selected':''}>This name, future too</option><option value="batch"${decision.scope==='batch'?' selected':''}>This batch only</option></select></div>`;
}

function renderDisplayCombobox(decision,key){
  return `<div class="stage-display-wrap"><input class="stage-control stage-display-input" data-display-input data-key="${key}" value="${escapeHtml(decision.display_name)}" autocomplete="off" ${decision.resolution==='exclude'?'disabled':''}><div class="stage-combo-menu" data-display-menu="${key}" hidden></div></div>`;
}

function displayMenuHtml(query,decision){
  const needle=query.trim().toLocaleLowerCase();
  const matches=(importState.batch?.display_identities||[]).filter(item=>!needle||item.display_name.toLocaleLowerCase().includes(needle)).slice(0,8);
  const choices=matches.map(item=>`<button type="button" data-display-choice data-key="${importKey(decision.merchant_normalized)}" data-name="${escapeHtml(item.display_name)}" data-group="${escapeHtml(item.canonical_group_id)}" data-category="${escapeHtml(item.category)}"><strong>${escapeHtml(item.display_name)}</strong><small>${item.aliases} aliases · ${item.transactions} transactions · ${escapeHtml(item.category)}</small></button>`).join('');
  const create=query.trim()?`<button type="button" class="create-display" data-display-create data-key="${importKey(decision.merchant_normalized)}">Use “${escapeHtml(query.trim())}” as a new display name</button>`:'';
  return choices+create+(choices||create?'':'<button type="button" disabled>No matching display names</button>');
}

function renderImportReconcile(){
  const files=importState.batch?.files||[];
  return `<div class="stage-callout amber"><strong>Why this confirmation exists:</strong> the current parsers can total the transaction rows, but they do not yet reliably read every provider’s printed statement total. Check that number on the original file before approval.</div><div class="stage-list"><div class="stage-row head"><span>File</span><span>Parsed total</span><span>Official total</span><span>Difference</span><span>Confirmation</span></div>${files.map(file=>{const required=file.kind==='statement'&&file.status==='ready'&&file.reconciliation?.status==='manual_required';return `<div class="stage-row"><span><strong>${escapeHtml(file.filename)}</strong><small>${escapeHtml((file.provider||file.kind).toUpperCase())}${file.card_last4?` · •• ${escapeHtml(file.card_last4)}`:''}</small></span><span><strong>${money(file.reconciliation?.parsed_total)}</strong><small>${file.parsed||0} parsed rows</small></span><span>${required?'Check original':'Not applicable'}</span><span>—</span><span>${required?`<label class="reconcile-confirm"><input type="checkbox" data-reconcile-file="${escapeHtml(file.filename)}" ${importState.reconciled.has(file.filename)?'checked':''}> <span>I checked the statement total</span></label>`:'<span class="stage-badge">No check needed</span>'}</span></div>`}).join('')}</div>`;
}

function renderImportApprove(){
  const files=importState.batch?.files||[];const merchants=importState.batch?.merchants||[];const decisions=[...importState.decisions.values()];
  const newRows=files.reduce((sum,file)=>sum+(file.new_rows||0),0);const duplicateRows=files.reduce((sum,file)=>sum+(file.duplicates||0),0);
  const permanent=decisions.filter(item=>!['needs_review','exclude'].includes(item.resolution)&&item.scope==='exact').length;
  const deferred=decisions.filter(item=>item.resolution==='needs_review').length;const excluded=decisions.filter(item=>item.resolution==='exclude').length;
  return `<div class="stage-approve"><div class="stage-checks"><div class="stage-check"><b>✓</b><span><strong>Files parsed before import</strong><small>${files.length} files · ${newRows} new rows · ${duplicateRows} duplicate rows skipped</small></span></div><div class="stage-check"><b>✓</b><span><strong>Existing merchant rules have priority</strong><small>${merchants.filter(item=>!item.needs_review).length} merchants matched the database automatically</small></span></div><div class="stage-check"><b>✓</b><span><strong>Merchant decisions reviewed</strong><small>${permanent} permanent rules · ${deferred} left for review · ${excluded} excluded</small></span></div><div class="stage-check"><b>✓</b><span><strong>Statement totals confirmed</strong><small>${manualReconciliationFiles().length} statements manually checked</small></span></div><div class="stage-check"><b>✓</b><span><strong>Rollback protection</strong><small>A complete database backup will be created immediately before any records are written.</small></span></div></div><div class="stage-commit-card"><h3>Ready to import</h3><div class="stage-commit-line"><span>Files</span><strong>${files.length}</strong></div><div class="stage-commit-line"><span>New transaction rows</span><strong>${newRows}</strong></div><div class="stage-commit-line"><span>Known + reviewed merchants</span><strong>${merchants.length-deferred}</strong></div><div class="stage-commit-line"><span>Still needs review</span><strong>${deferred}</strong></div><p class="stage-callout">Nothing has been added to the dashboard yet. The next button is the only action that writes this batch to the database.</p></div></div>`;
}

async function analyzeImportFiles(files){
  if(!files?.length)return;
  importState.busy=true;renderImportStage();
  const form=new FormData();[...files].forEach(file=>form.append('files',file));
  try{
    const response=await fetch('/api/import/analyze',{method:'POST',body:form});const payload=await response.json();
    if(!response.ok)throw new Error(payload.error||'Could not analyze files');
    importState.batch=payload;importState.step=1;importState.reconciled.clear();initializeImportDecisions();
    showToast(`${payload.files.length} files staged. No transactions were added.`,`Analysis complete`);
  }catch(error){showToast(error.message,'Analysis failed')}
  finally{importState.busy=false;fileInput.value='';renderImportStage()}
}

async function commitImportBatch(){
  if(!importState.batch||importState.busy)return;
  importState.busy=true;renderImportStage();
  try{
    if(manualReconciliationFiles().some(file=>!importState.reconciled.has(file.filename)))throw new Error('Confirm every statement total before importing');
    const response=await fetch('/api/import/commit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({batch_id:importState.batch.batch_id,decisions:[...importState.decisions.values()],reconciled_files:[...importState.reconciled]})});
    const payload=await response.json();if(!response.ok)throw new Error(payload.error||'Import failed');
    const inserted=payload.results.reduce((sum,item)=>sum+(item.inserted||0),0);const duplicates=payload.results.reduce((sum,item)=>sum+(item.duplicates||0),0);
    importState.batch=null;importState.decisions.clear();importState.reconciled.clear();importState.step=0;setModal(false);
    showToast(`${inserted} transactions added${duplicates?` · ${duplicates} duplicates skipped`:''}. Backup created first.`,'Import complete');await loadDashboard();
  }catch(error){showToast(error.message,'Import failed')}
  finally{importState.busy=false;if(modal.classList.contains('show'))renderImportStage()}
}

importStageBody.addEventListener('click',event=>{
  const browse=event.target.closest('[data-browse-import]');if(browse){fileInput.click();return}
  const choice=event.target.closest('[data-display-choice]');if(choice){const decision=importDecision(choice.dataset.key);decision.display_name=choice.dataset.name;decision.canonical_group_id=choice.dataset.group;decision.category=choice.dataset.category||decision.category;decision.resolution='link';decision.scope='exact';renderImportStage();return}
  const create=event.target.closest('[data-display-create]');if(create){const decision=importDecision(create.dataset.key);decision.canonical_group_id='';decision.resolution='create';decision.scope='exact';closeDisplayMenus();renderImportStage()}
});
importStageBody.addEventListener('input',event=>{
  if(!event.target.matches('[data-display-input]'))return;const decision=importDecision(event.target.dataset.key);decision.display_name=event.target.value;decision.canonical_group_id='';if(decision.resolution==='link')decision.resolution='create';const menu=event.target.parentElement.querySelector('.stage-combo-menu');menu.innerHTML=displayMenuHtml(event.target.value,decision);closeDisplayMenus(menu);menu.hidden=false;
});
importStageBody.addEventListener('focusin',event=>{if(event.target.matches('[data-display-input]')){const decision=importDecision(event.target.dataset.key);const menu=event.target.parentElement.querySelector('.stage-combo-menu');menu.innerHTML=displayMenuHtml(event.target.value,decision);closeDisplayMenus(menu);menu.hidden=false}});
importStageBody.addEventListener('change',event=>{
  if(event.target.matches('[data-decision-field]')){const decision=importDecision(event.target.dataset.key);const field=event.target.dataset.decisionField;decision[field]=event.target.value;if(field==='category'&&event.target.value!=='Needs review'&&decision.resolution==='needs_review'){decision.resolution='create';decision.scope='exact'}if(field==='resolution'){if(event.target.value==='needs_review'){decision.category='Needs review';decision.scope='batch'}else if(event.target.value==='provider'){const merchant=importState.batch.merchants.find(item=>item.merchant_normalized===decision.merchant_normalized);decision.category=merchant.provider_category;decision.scope='exact'}}renderImportStage();return}
  if(event.target.matches('[data-reconcile-file]')){event.target.checked?importState.reconciled.add(event.target.dataset.reconcileFile):importState.reconciled.delete(event.target.dataset.reconcileFile);renderImportStage()}
});
importStageBody.addEventListener('dragover',event=>{const target=event.target.closest('.stage-drop');if(target){event.preventDefault();target.classList.add('dragging')}});
importStageBody.addEventListener('dragleave',event=>{event.target.closest('.stage-drop')?.classList.remove('dragging')});
importStageBody.addEventListener('drop',event=>{const target=event.target.closest('.stage-drop');if(target){event.preventDefault();target.classList.remove('dragging');analyzeImportFiles(event.dataTransfer.files)}});
importStepper.addEventListener('click',event=>{const target=event.target.closest('[data-import-step]');if(!target||(!importState.batch&&Number(target.dataset.importStep)))return;importState.step=Number(target.dataset.importStep);renderImportStage()});
importBack.addEventListener('click',()=>{if(importState.step>0){importState.step-=1;renderImportStage()}});
importNext.addEventListener('click',()=>{if(importState.step===4)commitImportBatch();else if(importState.step<4){importState.step+=1;renderImportStage()}});
document.addEventListener('click',event=>{if(!event.target.closest('.stage-display-wrap'))closeDisplayMenus()});

loadDashboard();
