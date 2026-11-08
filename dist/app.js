const state={period:'month',month:'',card:'all',data:null,detailTransactions:[],mappingData:null,merchantData:null,activeMerchant:null,activeTransaction:null,activeAdjustmentTransaction:null,detailMode:'',activeCategory:'',detailSort:{key:'transaction_date',direction:'desc'},categoryTransactions:[],categoryView:'grouped',categorySearch:'',categoryGroupSort:{key:'latest_date',direction:'desc'},expandedMerchantGroups:new Set(),categoryExpandedSort:new Map(),merchantRecurringFilter:'all',recurringCache:new Map(),recurringModalPeriod:'month',recurringTab:'series',activeRecurringSeries:'',recurringSorts:{series:{key:'display_name',direction:'asc'},commitments:{key:'remaining',direction:'desc'}},eventsData:null,activeEvent:null,activeEventGroup:null,activeEventCategory:'all'};
const colors=['#6658e8','#41b98c','#e6a14b','#e76b77','#5b8def','#a66dd4','#42a5b3','#d17b49','#8f9b4f','#d45f9f','#62748f','#9b7b58'];
const cardPicker=document.querySelector('#cardPicker');
const cardPickerButton=document.querySelector('#cardPickerButton');
const cardPickerLabel=document.querySelector('#cardPickerLabel');
const cardPickerPopover=document.querySelector('#cardPickerPopover');
const monthPicker=document.querySelector('#monthPicker');
const monthPickerButton=document.querySelector('#monthPickerButton');
const monthPickerPopover=document.querySelector('#monthPickerPopover');
const monthPickerLabel=document.querySelector('#monthPickerLabel');
const monthPickerYear=document.querySelector('#monthPickerYear');
const monthPickerGrid=document.querySelector('#monthPickerGrid');
const monthYearPrevious=document.querySelector('#monthYearPrevious');
const monthYearNext=document.querySelector('#monthYearNext');
const monthPickerLatest=document.querySelector('#monthPickerLatest');
const toast=document.querySelector('#toast');
const incomePanel=document.querySelector('#incomePanel');
const incomeHeaderToggle=document.querySelector('#incomeHeaderToggle');
const manageMenuButton=document.querySelector('#manageMenuButton');
const manageMenu=document.querySelector('#manageMenu');
let toastTimer;
let availableMonths=[];
let monthPickerViewYear=null;
let monthPickerSelected='';

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
    state.recurringCache.clear();
    const response=await fetch(`/api/dashboard?period=${state.period}&month=${encodeURIComponent(state.month)}&card=${encodeURIComponent(state.card)}`,{cache:'no-store'});
    const data=await response.json();
    if(!response.ok)throw new Error(data.error||'Could not load dashboard');
    renderDashboard(data);
    loadRecurringPanel();
    loadEventsPanel();
    window.loadFinancialObservations?.();
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
  renderMonthFilter(data.available_months||[],data.period.start);
  document.querySelector('#cardsPeriod').textContent=data.period.label;
  renderCards(data.cards,data.selected_card);
  renderIncome(data.income_summary,data.period);
  renderCategories(data.categories,m.spent,data.category_comparison);
  renderTransactions(data.recent_transactions);
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
  incomeHeaderToggle.textContent=hidden?'Show income':'Hide income';
  incomeHeaderToggle.setAttribute('aria-pressed',String(!hidden));
  try{localStorage.setItem('clearspend-income-hidden',hidden?'1':'0')}catch(_error){}
  if(state.data){renderTrend(state.data.trend,state.data);window.loadFinancialObservations?.()}
}

let incomeHidden=false;
try{incomeHidden=localStorage.getItem('clearspend-income-hidden')==='1'}catch(_error){}
setIncomeVisibility(incomeHidden);
document.querySelector('#incomeHideButton').addEventListener('click',()=>setIncomeVisibility(true));
incomeHeaderToggle.addEventListener('click',()=>setIncomeVisibility(!incomeHidden));

function setManageMenu(show){
  manageMenu.hidden=!show;
  manageMenuButton.setAttribute('aria-expanded',String(show));
}
manageMenuButton.addEventListener('click',event=>{event.stopPropagation();setManageMenu(manageMenu.hidden)});
manageMenu.addEventListener('click',()=>setManageMenu(false));
document.addEventListener('click',event=>{if(!event.target.closest('#manageMenu')&&!event.target.closest('#manageMenuButton'))setManageMenu(false)});

function availableMonthYears(){return [...new Set(availableMonths.map(month=>Number(month.slice(0,4))))].sort((a,b)=>a-b)}

function renderMonthPickerGrid(){
  const years=availableMonthYears();
  if(!years.length){
    monthPickerYear.textContent='—';monthPickerGrid.innerHTML='';monthYearPrevious.disabled=true;monthYearNext.disabled=true;monthPickerLatest.disabled=true;return;
  }
  if(!years.includes(monthPickerViewYear))monthPickerViewYear=years.at(-1);
  const yearIndex=years.indexOf(monthPickerViewYear);
  monthPickerYear.textContent=monthPickerViewYear;
  monthYearPrevious.disabled=yearIndex<=0;
  monthYearNext.disabled=yearIndex>=years.length-1;
  monthPickerLatest.disabled=false;
  const shortMonths=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  monthPickerGrid.innerHTML=shortMonths.map((label,index)=>{
    const month=`${monthPickerViewYear}-${String(index+1).padStart(2,'0')}`;
    const available=availableMonths.includes(month),selected=month===monthPickerSelected;
    return `<button class="month-picker-month${available?' available':''}${selected?' selected':''}" type="button" data-month="${month}" ${available?'':'disabled'} aria-label="${escapeHtml(formatMonth(month))}"${selected?' aria-current="date"':''}>${label}</button>`;
  }).join('');
}

function setMonthPickerOpen(open){
  monthPickerPopover.hidden=!open;
  monthPickerButton.setAttribute('aria-expanded',String(open));
  if(open)renderMonthPickerGrid();
}

function selectDashboardMonth(month){
  if(!availableMonths.includes(month))return;
  state.month=month;monthPickerSelected=month;monthPickerViewYear=Number(month.slice(0,4));
  monthPickerLabel.textContent=formatMonth(month);setMonthPickerOpen(false);state.period='month';
  document.querySelectorAll('#periodTabs button').forEach(button=>button.classList.toggle('active',button.dataset.period==='month'));
  loadDashboard(true);
}

function renderMonthFilter(months,start){
  availableMonths=[...new Set(months.filter(month=>/^\d{4}-\d{2}$/.test(month)))].sort();
  const requested=state.month||(state.period==='month'&&start?start.slice(0,7):'');
  const latest=availableMonths.at(-1)||'';
  monthPickerSelected=availableMonths.includes(requested)?requested:latest;
  monthPickerViewYear=Number((monthPickerSelected||latest||String(new Date().getFullYear())).slice(0,4));
  monthPickerLabel.textContent=monthPickerSelected?formatMonth(monthPickerSelected):'No months available';
  renderMonthPickerGrid();
}

function renderCards(cards,selected){
  const selectedCard=cards.find(card=>card.key===selected);
  cardPickerLabel.textContent=selectedCard?`${selectedCard.product_name} •• ${selectedCard.card_last4}`:'All cards';
  cardPickerPopover.innerHTML=`<button class="card-picker-option${selected==='all'?' selected':''}" type="button" role="option" aria-selected="${selected==='all'}" data-card="all"><span><strong>All cards</strong><small>Combined dashboard view</small></span><i>${selected==='all'?'✓':''}</i></button>`+cards.map(card=>`<button class="card-picker-option${selected===card.key?' selected':''}" type="button" role="option" aria-selected="${selected===card.key}" data-card="${escapeHtml(card.key)}"><span><strong>${escapeHtml(card.product_name)} •• ${escapeHtml(card.card_last4)}</strong><small>${escapeHtml(card.provider.toUpperCase())}</small></span><i>${selected===card.key?'✓':''}</i></button>`).join('');
  const list=document.querySelector('#cardList');
  list.innerHTML=cards.length?cards.map(card=>`
    <button class="payment-card ${selected===card.key?'selected':''}" data-card="${escapeHtml(card.key)}">
      <span class="card-logo ${card.provider==='max'?'mc':'visa'}">${card.provider==='max'?'<i></i><b></b>':'MC'}</span>
      <span class="card-info"><strong>${escapeHtml(card.product_name)}</strong><small>•••• ${escapeHtml(card.card_last4)} · ${escapeHtml(card.provider.toUpperCase())}</small></span>
      <span class="card-total"><strong>${money(card.amount)}</strong><small>${card.share}% · ${card.transactions} trx</small></span>
      <span class="card-bar"><i style="width:${Math.min(card.share,100)}%"></i></span>
    </button>`).join(''):'<p>No transactions in this period.</p>';
  list.querySelectorAll('.payment-card').forEach(button=>button.addEventListener('click',()=>selectDashboardCard(button.dataset.card)));
}

function setCardPickerOpen(open){cardPickerPopover.hidden=!open;cardPickerButton.setAttribute('aria-expanded',String(open))}
function selectDashboardCard(card){state.card=card;setCardPickerOpen(false);loadDashboard(true)}

function renderCategories(categories,total,comparison){
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
  const previousMonth=comparison?.previous_month?formatMonth(comparison.previous_month):'the previous month';
  const comparisonMarkup=category=>{
    if(!comparison?.previous_month)return '';
    const status=category.comparison||'unavailable';
    const labels={
      up:`↑ ${Math.abs(Number(category.change_percent))}%`,
      down:`↓ ${Math.abs(Number(category.change_percent))}%`,
      same:'0%',new:'New',unavailable:'—',
    };
    const detail=status==='unavailable'
      ?`No transactions are available for ${previousMonth}`
      :status==='new'
        ?`No spending in ${previousMonth}; ${money(category.amount)} in the selected month`
        :`${money(category.previous_amount)} in ${previousMonth}; ${money(category.amount)} in the selected month`;
    return `<i class="category-change ${status}" title="${escapeHtml(detail)}" aria-label="${escapeHtml(detail)}">${labels[status]||'—'}</i>`;
  };
  document.querySelector('#categoryList').innerHTML=categories.length?categories.map((category,index)=>`
    <button type="button" data-category="${escapeHtml(category.category)}"><i class="cat-dot" style="background:${colors[index%colors.length]}"></i><span>${escapeHtml(category.category)}</span><strong>${money(category.amount)}</strong><em>${category.share}%</em>${comparisonMarkup(category)}</button>`).join(''):'<div><span>No category data</span></div>';
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
  setMonthPickerOpen(false);setCardPickerOpen(false);
  state.period=event.target.dataset.period;
  document.querySelectorAll('#periodTabs button').forEach(button=>button.classList.toggle('active',button===event.target));
  loadDashboard(true);
});
monthPickerButton.addEventListener('click',()=>{setCardPickerOpen(false);setMonthPickerOpen(monthPickerPopover.hidden)});
monthPickerGrid.addEventListener('click',event=>{const button=event.target.closest('[data-month]');if(button)selectDashboardMonth(button.dataset.month)});
monthYearPrevious.addEventListener('click',()=>{const years=availableMonthYears(),index=years.indexOf(monthPickerViewYear);if(index>0){monthPickerViewYear=years[index-1];renderMonthPickerGrid()}});
monthYearNext.addEventListener('click',()=>{const years=availableMonthYears(),index=years.indexOf(monthPickerViewYear);if(index>=0&&index<years.length-1){monthPickerViewYear=years[index+1];renderMonthPickerGrid()}});
monthPickerLatest.addEventListener('click',()=>{const latest=availableMonths.at(-1);if(latest)selectDashboardMonth(latest)});
cardPickerButton.addEventListener('click',()=>{setMonthPickerOpen(false);setCardPickerOpen(cardPickerPopover.hidden)});
cardPickerPopover.addEventListener('click',event=>{const button=event.target.closest('[data-card]');if(button)selectDashboardCard(button.dataset.card)});
document.addEventListener('click',event=>{if(!event.target.closest('#monthPicker'))setMonthPickerOpen(false)});
document.addEventListener('click',event=>{if(!event.target.closest('#cardPicker'))setCardPickerOpen(false)});
document.addEventListener('keydown',event=>{if(event.key!=='Escape')return;if(!monthPickerPopover.hidden){setMonthPickerOpen(false);monthPickerButton.focus()}else if(!cardPickerPopover.hidden){setCardPickerOpen(false);cardPickerButton.focus()}});

const detailModal=document.querySelector('#detailModal');
const detailContent=document.querySelector('#detailContent');
const detailTools=document.querySelector('#detailTools');
const detailEyebrow=document.querySelector('#detailEyebrow');
function setDetailEyebrow(label=''){detailEyebrow.textContent=label;detailEyebrow.hidden=!label}
function setDetailModal(show){detailModal.classList.toggle('show',show);detailModal.setAttribute('aria-hidden',String(!show));if(show)document.querySelector('#detailClose').focus()}
document.querySelector('#detailClose').addEventListener('click',()=>setDetailModal(false));
detailModal.addEventListener('click',event=>{if(event.target===detailModal)setDetailModal(false)});

function setActiveNav(element){
  const navItem=element?.closest('.nav-item');
  if(!navItem)return;
  document.querySelectorAll('.nav-item').forEach(item=>item.classList.remove('active'));
  navItem.classList.add('active');
}

async function openDetail(view,source,initialSearch='',transactionIds=[]){
  setActiveNav(source);
  state.detailMode=view;state.activeCategory='';
  const isTransactions=view==='transactions';
  setDetailEyebrow(isTransactions?'TRANSACTION EXPLORER':'CATEGORY BREAKDOWN');
  document.querySelector('#detailTitle').textContent=isTransactions?'All transactions':'All categories';
  document.querySelector('#detailSubtitle').textContent=`${state.data?.period.label||''} · ${state.card==='all'?'all cards':'selected card'}`;
  detailTools.innerHTML=isTransactions?`<label class="detail-search"><span>⌕</span><input id="transactionSearch" type="search" value="${escapeHtml(initialSearch)}" placeholder="Search merchant or category"></label>`:'';
  detailContent.innerHTML='<p class="loading-state">Loading local data…</p>';
  setDetailModal(true);
  try{
    const response=await fetch(`/api/${view}?period=${state.period}&month=${encodeURIComponent(state.month)}&card=${encodeURIComponent(state.card)}`,{cache:'no-store'});
    const data=await response.json();if(!response.ok)throw new Error(data.error||`Could not load ${view}`);
    if(isTransactions){
      const selectedIds=new Set((transactionIds||[]).map(value=>String(value)));
      const scopedTransactions=selectedIds.size
        ?data.transactions.filter(item=>selectedIds.has(String(item.id)))
        :data.transactions;
      state.detailTransactions=scopedTransactions;
      state.detailSort={key:'transaction_date',direction:'desc'};
      const initialTerm=initialSearch.trim().toLocaleLowerCase();
      const transactionText=item=>Object.values(item).filter(value=>value!==null).join(' ').toLocaleLowerCase();
      const initialRows=initialTerm?state.detailTransactions.filter(item=>transactionText(item).includes(initialTerm)):state.detailTransactions;
      renderFullTransactions(initialRows,scopedTransactions.length,initialTerm);
      document.querySelector('#transactionSearch').addEventListener('input',event=>{
        const term=event.target.value.trim().toLocaleLowerCase();
        const filtered=state.detailTransactions.filter(item=>transactionText(item).includes(term));
        renderFullTransactions(filtered,data.total,term);
      });
    }else renderFullCategories(data);
  }catch(error){detailContent.innerHTML=`<p class="empty-state">${escapeHtml(error.message)}</p>`}
}

function eventAssignmentOptions(selected=''){
  const events=state.eventsData?.available_events||[];
  return `<option value="">${selected?'No event':'+ Event'}</option>`+events.map(event=>`<option value="${escapeHtml(event.id)}"${event.id===selected?' selected':''}${event.status==='cancelled'?' disabled':''}>${escapeHtml(event.name)}${event.status==='cancelled'?' (cancelled)':''}</option>`).join('');
}

function eventBadge(item){
  const assigned=Boolean(item.event_id);
  const selectedEvent=state.eventsData?.available_events?.find(event=>event.id===item.event_id);
  const business=(item.event_type||selectedEvent?.event_type)==='business_trip';
  return `<select class="transaction-event-badge${assigned?' assigned':''}${business?' business-event':''}" data-transaction-event="${item.id}" aria-label="${assigned?'Change event':'Assign event'} for ${escapeHtml(item.merchant_display_name||item.merchant_raw)}" title="${assigned?'Event label · choose another existing event':'Assign an existing event'}">${eventAssignmentOptions(item.event_id||'')}</select>`;
}

function eventIcon(event){
  const icons={plane:'✈',sun:'☀',home:'⌂',trip:'✈',celebration:'✦',other:'◆'};
  return icons[event.icon]||event.icon||icons[event.event_type]||'◆';
}

const businessBriefcaseIcon='<svg class="business-briefcase-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 7V5.8A1.8 1.8 0 0 1 10.8 4h2.4A1.8 1.8 0 0 1 15 5.8V7"></path><rect x="3" y="7" width="18" height="13" rx="2"></rect><path d="M3 12.5c4.8 2 13.2 2 18 0"></path><path d="M10 13h4"></path></svg>';
function eventIconMarkup(event){return event.event_type==='business_trip'?businessBriefcaseIcon:escapeHtml(eventIcon(event))}

function refreshEventBadges(){
  document.querySelectorAll('[data-transaction-event]').forEach(select=>{
    const selected=select.value;select.innerHTML=eventAssignmentOptions(selected);select.value=selected;
    const selectedEvent=state.eventsData?.available_events?.find(event=>event.id===selected);
    select.classList.toggle('business-event',selectedEvent?.event_type==='business_trip');
  });
}

async function loadEventsPanel(){
  const grid=document.querySelector('#eventsGrid'),panel=document.querySelector('#projectsEventsPanel'),emptyLabel=document.querySelector('#eventsEmptyLabel');
  try{
    const response=await fetch(`/api/events?period=${state.period}&month=${encodeURIComponent(state.month)}&card=${encodeURIComponent(state.card)}`,{cache:'no-store'});
    const data=await response.json();
    if(!response.ok)throw new Error(data.error||'Could not load events');
    state.eventsData=data;renderEventsPanel(data);refreshEventBadges();return data;
  }catch(error){panel.classList.remove('is-empty');emptyLabel.hidden=true;grid.innerHTML=`<p class="events-empty">${escapeHtml(error.message)}</p>`}
}

function renderEventsPanel(data){
  const empty=!data.events.length,panel=document.querySelector('#projectsEventsPanel'),emptyLabel=document.querySelector('#eventsEmptyLabel');
  panel.classList.toggle('is-empty',empty);emptyLabel.hidden=!empty;
  const combinedSpending=data.events.reduce((sum,event)=>sum+Number(event.amount||0),0);
  document.querySelector('#eventsPeriod').textContent=`${data.events.length} events · ${money(combinedSpending)}`;
  const grid=document.querySelector('#eventsGrid');
  const items=[];state.eventGroups=new Map();const groupedIds=new Set();
  if(state.period!=='month'){
    const byDestination=new Map();data.events.filter(event=>event.event_type==='business_trip'&&event.destination).forEach(event=>{const key=event.destination.trim().toLocaleLowerCase('he');if(!byDestination.has(key))byDestination.set(key,[]);byDestination.get(key).push(event)});
    [...byDestination.entries()].filter(([,events])=>events.length>1).forEach(([key,events],index)=>{const id=`business-group-${index}`;state.eventGroups.set(id,events);events.forEach(event=>groupedIds.add(event.id));items.push({kind:'group',id,destination:events[0].destination,events,start_date:events.reduce((value,event)=>value<event.start_date?value:event.start_date,events[0].start_date)})});
  }
  data.events.filter(event=>!groupedIds.has(event.id)).forEach(event=>items.push({kind:'event',event,start_date:event.start_date}));items.sort((left,right)=>String(right.start_date).localeCompare(String(left.start_date)));
  grid.innerHTML=items.length?items.map(item=>{if(item.kind==='group'){const events=item.events,amount=events.reduce((sum,event)=>sum+Number(event.amount||0),0),completed=events.every(event=>event.status==='completed');return `<button class="event-card business-event-card" type="button" data-event-group="${item.id}"><span class="event-card-icon">${businessBriefcaseIcon}${completed?'<i>✓</i>':''}</span><span class="event-card-copy"><strong>${escapeHtml(`נסיעות עבודה ל${item.destination}`)}</strong><small>${events.length} business trips · ${state.period==='year'?'Latest year':'All time'}</small></span><span class="event-card-amount"><strong>${money(amount)}</strong><small>PERSONAL SPENDING</small></span></button>`}const event=item.event,business=event.event_type==='business_trip';return `<button class="event-card${business?' business-event-card':''}" type="button" data-event-id="${escapeHtml(event.id)}"><span class="event-card-icon">${eventIconMarkup(event)}${event.status==='completed'?'<i>✓</i>':''}</span><span class="event-card-copy"><strong>${escapeHtml(event.name)}</strong><small>${formatDate(event.start_date)} – ${formatDate(event.end_date)}</small></span><span class="event-card-amount"><strong>${money(event.amount)}</strong><small>${state.period==='month'?'THIS MONTH':'PERSONAL SPENDING'}</small></span></button>`}).join(''):'<p class="events-empty">No reviewed event overlaps this period and card selection. Change the period or card filter to see other events.</p>';
  grid.querySelectorAll('[data-event-id]').forEach(button=>button.addEventListener('click',()=>openEventModal(button.dataset.eventId)));
  grid.querySelectorAll('[data-event-group]').forEach(button=>button.addEventListener('click',()=>openEventGroup(button.dataset.eventGroup)));
}

function setEventCreateModal(show){
  const modal=document.querySelector('#eventCreateModal'),form=document.querySelector('#eventCreateForm'),error=document.querySelector('#eventCreateError');
  modal.classList.toggle('show',show);modal.setAttribute('aria-hidden',String(!show));
  if(show){form.reset();form.elements.status.value='planned';syncEventDestinationField(form);error.textContent='';setTimeout(()=>form.elements.name.focus(),40)}
}

function syncEventDestinationField(form){
  const field=form.querySelector('[data-event-destination-field]'),input=form.elements.destination,business=form.elements.event_type.value==='business_trip';
  field.hidden=!business;input.required=business;if(!business)input.value='';
}

async function createEvent(form){
  const button=form.querySelector('button[type="submit"]'),error=document.querySelector('#eventCreateError'),values=Object.fromEntries(new FormData(form));
  error.textContent='';
  if(values.end_date<values.start_date){error.textContent='End date cannot be before the start date.';form.elements.end_date.focus();return}
  button.disabled=true;button.textContent='Creating…';
  try{
    const response=await fetch('/api/events',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(values)}),result=await response.json();
    if(!response.ok)throw new Error(result.error||'Could not create event');
    setEventCreateModal(false);await loadEventsPanel();showToast(`${result.event.name} is ready for transaction assignments`,'Event created');
  }catch(createError){error.textContent=createError.message;showToast(createError.message,'Creation failed')}
  finally{button.disabled=false;button.textContent='Create event'}
}

function renderEventTransactions(category='all'){
  state.activeEventCategory=category;
  const rows=category==='all'?state.activeEvent.transactions:state.activeEvent.transactions.filter(item=>item.category===category);
  document.querySelector('#eventTransactionsTitle').textContent=category==='all'?`All transactions · ${rows.length}`:`${category} · ${rows.length}`;
  document.querySelector('#eventTransactionList').innerHTML=rows.length?rows.map(item=>`<div class="event-transaction-row"><span><strong>${escapeHtml(item.merchant_display_name||item.merchant_raw)}</strong><small>${escapeHtml(item.category)}</small></span><span>${formatDate(item.transaction_date)}</span><span>${escapeHtml(item.provider.toUpperCase())} •• ${escapeHtml(item.card_last4)}</span><strong>${money(item.personal_amount)}</strong></div>`).join(''):'<p class="events-empty">No transactions in this category.</p>';
  document.querySelectorAll('[data-event-category]').forEach(button=>button.classList.toggle('active',button.dataset.eventCategory===category));
}

function openEventGroup(groupId){
  const events=state.eventGroups?.get(groupId)||[];if(!events.length)return;
  state.activeEvent=null;state.activeEventGroup={id:groupId,events,destination:events[0].destination};
  const transactions=events.flatMap(event=>event.transactions||[]),categories=new Set(transactions.map(item=>item.category).filter(Boolean)),cards=new Set(transactions.map(item=>`${item.provider}:${item.card_last4}`));
  document.querySelector('#eventModalTitle').textContent=`נסיעות עבודה ל${state.activeEventGroup.destination}`;
  document.querySelector('#eventModalSubtitle').textContent=`${events.length} business trips · ${state.period==='year'?'Latest year':'All imported history'}`;
  document.querySelector('#eventEditOpen').hidden=true;document.querySelector('#eventGroupBack').hidden=true;document.querySelector('#eventDetailBody').hidden=true;
  const body=document.querySelector('#eventGroupBody');body.hidden=false;body.innerHTML=`<div class="event-summary"><div><span>Personal spending</span><strong>${money(events.reduce((sum,event)=>sum+Number(event.total_amount||0),0))}</strong><small>Across these trips</small></div><div><span>Transactions</span><strong>${transactions.length}</strong><small>Exact transaction IDs</small></div><div><span>Categories</span><strong>${categories.size}</strong><small>Cross-category events</small></div><div><span>Cards</span><strong>${cards.size}</strong><small>Across these trips</small></div></div><div class="business-trip-list"><div class="business-trip-row business-trip-head"><span>Trip</span><span>Dates</span><span>Transactions</span><span>Personal spending</span><span></span></div>${events.map(event=>`<button type="button" class="business-trip-row" data-business-trip-id="${escapeHtml(event.id)}"><span><strong>${escapeHtml(event.name)}</strong><small>Business trip</small></span><span>${formatDate(event.start_date)} – ${formatDate(event.end_date)}</span><span>${event.total_transaction_count}</span><b>${money(event.total_amount)}</b><i>›</i></button>`).join('')}</div><p class="business-group-note">This card is generated automatically from individual business trips sharing the destination “${escapeHtml(state.activeEventGroup.destination)}”. It is not stored as another event.</p>`;
  body.querySelectorAll('[data-business-trip-id]').forEach(button=>button.addEventListener('click',()=>openEventModal(button.dataset.businessTripId,true)));
  const modal=document.querySelector('#eventModal');modal.classList.add('show');modal.setAttribute('aria-hidden','false');
}

function openEventModal(eventId,fromGroup=false){
  const event=state.eventsData?.events.find(item=>item.id===eventId);
  if(!event)return;
  if(!fromGroup)state.activeEventGroup=null;
  state.activeEvent=event;state.activeEventCategory='all';
  document.querySelector('#eventGroupBody').hidden=true;document.querySelector('#eventDetailBody').hidden=false;document.querySelector('#eventGroupBack').hidden=!fromGroup;document.querySelector('#eventEditOpen').hidden=false;
  document.querySelector('#eventModalTitle').textContent=event.name;
  document.querySelector('#eventModalSubtitle').textContent=`${event.event_type==='business_trip'?'Business trip · ':''}${formatDate(event.start_date)} – ${formatDate(event.end_date)}`;
  document.querySelector('#eventSummary').innerHTML=`<div><span>Personal spending</span><strong>${money(event.total_amount)}</strong><small>Entire event</small></div><div><span>Transactions</span><strong>${event.total_transaction_count}</strong><small>Exact transaction membership</small></div><div><span>Categories</span><strong>${event.category_count}</strong><small>Across this event</small></div><div><span>Cards</span><strong>${event.card_count}</strong><small>Used during this event</small></div>`;
  const totals=new Map();event.transactions.forEach(item=>totals.set(item.category,(totals.get(item.category)||0)+Number(item.personal_amount||0)));
  const categories=[...totals.entries()].sort((left,right)=>right[1]-left[1]);
  document.querySelector('#eventCategoryList').innerHTML=`<button type="button" class="event-category active" data-event-category="all"><i style="background:#aaa8b7"></i><span>All categories</span><b>${money(event.total_amount)}</b></button>`+categories.map(([category,amount],index)=>`<button type="button" class="event-category" data-event-category="${escapeHtml(category)}"><i style="background:${colors[index%colors.length]}"></i><span>${escapeHtml(category)}</span><b>${money(amount)}</b></button>`).join('');
  document.querySelectorAll('[data-event-category]').forEach(button=>button.addEventListener('click',()=>renderEventTransactions(button.dataset.eventCategory)));
  renderEventTransactions('all');
  const modal=document.querySelector('#eventModal');modal.classList.add('show');modal.setAttribute('aria-hidden','false');
}

function closeEventModal(){const modal=document.querySelector('#eventModal');modal.classList.remove('show');modal.setAttribute('aria-hidden','true');state.activeEventGroup=null}

function setEventEditModal(show){
  const modal=document.querySelector('#eventEditModal'),form=document.querySelector('#eventEditForm'),error=document.querySelector('#eventEditError');
  modal.classList.toggle('show',show);modal.setAttribute('aria-hidden',String(!show));
  if(!show)return;
  const event=state.activeEvent;if(!event){setEventEditModal(false);return}
  form.elements.name.value=event.name||'';form.elements.event_type.value=event.event_type||'trip';form.elements.destination.value=event.destination||'';form.elements.start_date.value=event.start_date||'';form.elements.end_date.value=event.end_date||'';form.elements.budget.value=event.budget??'';form.elements.status.value=event.status||'completed';syncEventDestinationField(form);error.textContent='';
  setTimeout(()=>form.elements.name.focus(),40);
}

async function saveEventSettings(form){
  if(!state.activeEvent)return;
  const values=Object.fromEntries(new FormData(form));
  const button=form.querySelector('button[type="submit"]'),error=document.querySelector('#eventEditError');error.textContent='';
  if(values.end_date<values.start_date){error.textContent='End date cannot be before the start date.';form.elements.end_date.focus();return}
  button.disabled=true;button.textContent='Saving…';
  try{
    const response=await fetch('/api/event-settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({event_id:state.activeEvent.id,...values})});
    const result=await response.json();if(!response.ok)throw new Error(result.error||'Could not save event');
    const eventId=state.activeEvent.id,fromGroup=Boolean(state.activeEventGroup);const data=await loadEventsPanel();const updated=data?.events.find(event=>event.id===eventId);
    setEventEditModal(false);if(updated)openEventModal(eventId,fromGroup);else closeEventModal();
    showToast(`${result.event.name} was updated`,'Event saved');
  }catch(saveError){error.textContent=saveError.message;showToast(saveError.message,'Update failed')}
  finally{button.disabled=false;button.textContent='Save changes'}
}

async function updateTransactionEvent(select){
  const transactionId=Number(select.dataset.transactionEvent),eventId=select.value,prior=select.dataset.previous||'';
  select.disabled=true;
  try{
    const response=await fetch('/api/transaction-event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({transaction_id:transactionId,event_id:eventId})});
    const result=await response.json();if(!response.ok)throw new Error(result.error||'Could not update event');
    const update=item=>{if(Number(item.id)!==transactionId)return;item.event_id=result.event_id;item.event_name=result.event_name;item.event_type=result.event_type;item.event_destination=result.event_destination};
    state.detailTransactions.forEach(update);state.categoryTransactions.forEach(update);
    select.dataset.previous=eventId;select.classList.toggle('assigned',Boolean(eventId));select.classList.toggle('business-event',result.event_type==='business_trip');select.innerHTML=eventAssignmentOptions(eventId);select.value=eventId;
    await loadEventsPanel();showToast(eventId?`Assigned to ${result.event_name}`:'Event assignment removed','Event updated');
  }catch(error){select.value=prior;showToast(error.message,'Update failed')}
  finally{select.disabled=false}
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
  const adjusted=Boolean(item.adjustment_type);
  const positive=Number(item.amount)>0;
  const reimbursementLabel=adjusted
    ?`<i class="transaction-reimbursement-label">${item.adjustment_type==='full_reimbursement'?'Fully reimbursed':`${money(item.reimbursed_amount)} reimbursed`}</i>`:'';
  const personalLabel=adjusted?`<small>Personal: ${sourceAmount(item.personal_amount,item.charged_currency)}</small>`:'';
  const action=positive
    ?`<button type="button" class="transaction-adjustment-icon${adjusted?' adjusted':''}" data-adjust-transaction="${item.id}" aria-label="${adjusted?'Edit reimbursement for':'Adjust spending for'} ${escapeHtml(item.merchant_display_name||item.merchant_raw)}" title="${adjusted?'Edit reimbursement':'Adjust spending'}">✎</button>`
    :'<button type="button" class="transaction-adjustment-icon" aria-label="Spending adjustment unavailable for a refund transaction" title="Unavailable for refunds" disabled>✎</button>';
  return `<tr>
    <td><strong>${escapeHtml(item.merchant_raw)}</strong><small>${item.merchant_display_name&&item.merchant_display_name!==item.merchant_raw?`Display: ${escapeHtml(item.merchant_display_name)} · `:''}${escapeHtml(item.merchant_normalized)}</small>${reimbursementLabel}</td>
    <td><span class="transaction-category-line"><span class="tag editable-category-tag ${item.category==='Needs review'?'amber-tag':''}"><span>${escapeHtml(item.category)}</span><button type="button" class="transaction-category-icon" data-edit-transaction="${item.id}" aria-label="Change category for ${escapeHtml(item.merchant_display_name||item.merchant_raw)}" title="Change category">✎</button></span>${eventBadge(item)}</span>${item.category_source==='transaction_override'?'<i class="transaction-override-label">One-off correction</i>':''}<small>${displayValue(item.subcategory)}</small></td>
    <td><strong>${escapeHtml(item.provider.toUpperCase())} •• ${escapeHtml(item.card_last4)}</strong><small>${displayValue(item.source_sheet)}</small></td>
    <td>${formatDate(item.transaction_date)}</td><td>${formatDate(item.billing_date)}</td>
    <td><strong>${formatMonth(item.billing_month)}</strong><small>${escapeHtml(reportingSource(item.billing_month_source))}${item.installment_number?` · ${item.installment_number}/${item.installment_total||'?'}`:''}</small></td>
    <td class="right"><strong>${sourceAmount(item.amount,item.charged_currency)}</strong>${personalLabel}</td>
    <td class="right">${sourceAmount(item.original_amount,item.original_currency)}</td>
    <td>${displayValue(item.transaction_type)}</td><td>${displayValue(item.execution_method)}</td>
    <td>${displayValue(item.voucher_number)}</td><td>${displayValue(item.exchange_rate)}</td><td class="notes-cell">${displayValue(item.notes)}</td>
    <td class="transaction-action-column">${action}</td>
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
  detailContent.innerHTML=`<div class="detail-summary"><strong>${label}</strong><span>Sorted by ${escapeHtml(transactionColumns.find(([key])=>key===state.detailSort.key)?.[1]||'Transaction date')} ${state.detailSort.direction==='asc'?'ascending':'descending'} · up to 1,000 rows</span></div><div class="table-wrap detail-table"><table class="full-transaction-table"><thead><tr>${sortHeaders}<th class="transaction-action-column" aria-label="Actions"></th></tr></thead><tbody>${sortedRows.length?sortedRows.map(fullTransactionRow).join(''):'<tr><td colspan="14">No matching transactions.</td></tr>'}</tbody></table></div>`;
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
    group.net_amount+=Number(item.personal_amount??item.amount)||0;
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
  const columns=[['merchant','Merchant'],['transactions','Transactions'],['latest_date','Latest transaction'],['cards','Cards used'],['net_amount','Personal total']];
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
    const expandedHeaders=`${transactionSortHeaders(expandedSort,'data-expanded-sort')}<th class="transaction-action-column" aria-label="Actions"></th>`;
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
  setDetailEyebrow('CATEGORY TRANSACTIONS');
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
  setDetailEyebrow();
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

async function openMerchants(source,options={}){
  setActiveNav(source);state.detailMode='merchants';state.activeCategory='';
  state.merchantRecurringFilter=options.recurringFilter||'all';
  setDetailEyebrow();
  document.querySelector('#detailTitle').textContent='Merchants';
  document.querySelector('#detailSubtitle').textContent='Manage display names, category rules, and recurring profiles. Original statement names remain available.';
  detailTools.innerHTML='<div class="merchant-management-tools"><label class="detail-search"><span>⌕</span><input id="merchantSearch" type="search" placeholder="Search display name or original alias"></label><label class="select-wrap"><span>Category</span><select id="merchantCategoryFilter"><option value="all">All categories</option></select></label><label class="select-wrap"><span>Recurring</span><select id="merchantRecurringFilter"><option value="all">All merchants</option><option value="recurring">Recurring</option><option value="not_recurring">Not recurring</option><option value="unreviewed">Not reviewed</option></select></label></div>';
  detailContent.innerHTML='<p class="loading-state">Loading merchants…</p>';setDetailModal(true);
  try{
    const data=await fetchMerchants(true);
    document.querySelector('#merchantCategoryFilter').innerHTML='<option value="all">All categories</option>'+data.categories.map(category=>`<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`).join('');
    document.querySelector('#merchantRecurringFilter').value=state.merchantRecurringFilter;
    const refresh=()=>{state.merchantRecurringFilter=document.querySelector('#merchantRecurringFilter').value;renderMerchantManagement(data,document.querySelector('#merchantSearch').value,document.querySelector('#merchantCategoryFilter').value,state.merchantRecurringFilter)};
    document.querySelector('#merchantSearch').addEventListener('input',refresh);document.querySelector('#merchantCategoryFilter').addEventListener('change',refresh);document.querySelector('#merchantRecurringFilter').addEventListener('change',refresh);refresh();
  }catch(error){detailContent.innerHTML=`<p class="empty-state">${escapeHtml(error.message)}</p>`}
}

function renderMerchantManagement(data,search='',category='all',recurring='all'){
  const term=search.trim().toLocaleLowerCase();
  const merchants=data.merchants.filter(item=>{
    const text=`${item.display_name} ${item.aliases.map(alias=>`${alias.merchant_raw} ${alias.merchant_normalized}`).join(' ')}`.toLocaleLowerCase();
    const verdict=item.recurring_profile?.verdict||'unreviewed';
    return text.includes(term)&&(category==='all'||item.categories.includes(category))&&(recurring==='all'||verdict===recurring);
  });
  const summary=data.summary;
  detailContent.innerHTML=`<div class="merchant-management-grid"><span><strong>${summary.display_identities.toLocaleString()}</strong>Display identities</span><span><strong>${summary.mapped_aliases.toLocaleString()}</strong>Original aliases</span><span><strong>${summary.transactions.toLocaleString()}</strong>Covered transactions</span><span><strong>${summary.multiple_categories.toLocaleString()}</strong>Multiple-category merchants</span><span><strong>${Number(summary.recurring||0).toLocaleString()}</strong>Recurring merchants</span></div><div class="mapping-editor-head"><strong>${merchants.length.toLocaleString()} merchants</strong><span>Select a merchant to manage its identity, category rules, or recurring profile.</span></div><div class="merchant-list">${merchants.length?merchants.map(item=>{const verdict=item.recurring_profile?.verdict||'unreviewed',included=item.aliases.filter(alias=>alias.recurring_included).length,label=verdict==='recurring'?`Recurring · ${included}/${item.aliases.length} ${item.aliases.length===1?'alias':'aliases'}`:verdict==='not_recurring'?'Not recurring':'Not reviewed';return `<button type="button" class="merchant-list-row" data-edit-merchant="${escapeHtml(item.canonical_group_id)}"><span><strong>${escapeHtml(item.display_name)}</strong><small>${item.aliases.length} original ${item.aliases.length===1?'name':'names'} · <i class="merchant-recurring-badge ${verdict}">${label}</i></small></span><span><strong>${item.transactions.toLocaleString()}</strong><small>transactions</small></span><span class="merchant-categories">${item.categories.map(value=>`<i>${escapeHtml(value)}</i>`).join('')}</span><span>${formatDate(item.last_seen)}</span><span><strong>${money(item.amount)}</strong><small>absolute activity</small></span><span class="merchant-chevron">›</span></button>`}).join(''):'<p class="empty-state">No merchants match these filters.</p>'}</div>`;
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
function merchantRecurringEditor(merchant){
  const profile=merchant.recurring_profile||{},isRecurring=profile.verdict==='recurring';
  const type=profile.recurring_type||'Fixed recurring',cadence=profile.cadence||'Monthly',lifecycle=profile.lifecycle_status||'active';
  const verdictLabel=isRecurring?'Recurring':profile.verdict==='not_recurring'?'Not recurring':'Not reviewed';
  const aliasScope=merchant.aliases.map(alias=>{const checked=alias.recurring_included||(!profile.verdict&&merchant.aliases.length===1);return `<label class="recurring-alias-option"><input type="checkbox" class="merchant-recurring-alias" value="${escapeHtml(alias.merchant_normalized)}"${checked?' checked':''}><span><strong>${escapeHtml(alias.merchant_raw)}</strong><small>${escapeHtml(alias.category)} · ${alias.transactions} transactions</small></span></label>`}).join('');
  return `<section class="editor-section merchant-recurring-editor"><div class="editor-section-head"><div><h3>Recurring settings</h3><p>Choose which original merchant names belong to this recurring series.</p></div><span class="merchant-recurring-badge ${profile.verdict||'unreviewed'}">${verdictLabel}</span></div>${!isRecurring?`<div class="recurring-decision-note"><strong>${profile.verdict==='not_recurring'?'Currently excluded from recurring tracking':'No recurring decision has been saved'}</strong><span>Adding it changes only the recurring profile. Transactions, categories, and display names remain unchanged.</span></div>`:''}<div class="recurring-alias-scope"><div><strong>Included original names</strong><small id="merchantRecurringAliasCount"></small></div>${aliasScope}</div><div class="merchant-recurring-fields"><label><span class="editor-field-label">Type</span><select class="editor-select" id="merchantRecurringType">${recurringTypeOptions.map(value=>`<option value="${value}"${value===type?' selected':''}>${value}</option>`).join('')}</select></label><label><span class="editor-field-label">Cadence</span><select class="editor-select" id="merchantRecurringCadence">${recurringCadenceOptions.map(value=>`<option value="${value}"${value===cadence?' selected':''}>${value}</option>`).join('')}</select></label><label><span class="editor-field-label">Lifecycle</span><select class="editor-select" id="merchantRecurringLifecycle"><option value="active"${lifecycle==='active'?' selected':''}>Active</option><option value="paused"${lifecycle==='paused'?' selected':''}>Paused</option><option value="ended"${lifecycle==='ended'?' selected':''}>Ended</option><option value="unknown"${lifecycle==='unknown'?' selected':''}>Unknown</option></select></label><label id="merchantRecurringEndField"${lifecycle==='ended'?'':' hidden'}><span class="editor-field-label">End month</span><input class="editor-input" id="merchantRecurringEndMonth" type="month" value="${escapeHtml(profile.end_month||'')}"></label></div><p class="merchant-recurring-help">Only checked aliases contribute billing history and missing-payment expectations. Cadence settings are shared by this recurring series.</p><div class="merchant-recurring-actions">${isRecurring?'<button type="button" class="merchant-recurring-remove" id="merchantRemoveRecurring">Mark all as not recurring</button>':''}<button type="button" class="upload-button editor-primary" id="merchantSaveRecurring">${isRecurring?'Save recurring settings':'Add to recurring tracking'}</button></div><div class="recurring-remove-confirm" id="merchantRecurringConfirm" hidden><div><strong>Mark every alias as not recurring?</strong><span>Recurring monitoring and future missing-payment warnings will stop. The previous configuration and all transactions remain available.</span></div><div><button type="button" class="secondary-button" id="merchantCancelRemoveRecurring">Cancel</button><button type="button" class="merchant-recurring-remove" id="merchantConfirmRemoveRecurring">Confirm not recurring</button></div></div></section>`;
}
function bindMerchantRecurringEditor(merchant){
  const lifecycle=document.querySelector('#merchantRecurringLifecycle'),endField=document.querySelector('#merchantRecurringEndField'),endMonth=document.querySelector('#merchantRecurringEndMonth');
  const aliases=[...document.querySelectorAll('.merchant-recurring-alias')],aliasCount=document.querySelector('#merchantRecurringAliasCount');
  const updateAliasCount=()=>{const selected=aliases.filter(input=>input.checked).length;aliasCount.textContent=`${selected} of ${aliases.length} selected`};aliases.forEach(input=>input.addEventListener('change',updateAliasCount));updateAliasCount();
  lifecycle.addEventListener('change',()=>{endField.hidden=lifecycle.value!=='ended';if(lifecycle.value==='ended'&&!endMonth.value)endMonth.value=state.month||state.data?.period?.end?.slice(0,7)||''});
  document.querySelector('#merchantSaveRecurring').addEventListener('click',()=>saveManagedRecurringProfile(merchant,'recurring'));
  const remove=document.querySelector('#merchantRemoveRecurring');if(!remove)return;
  const confirmation=document.querySelector('#merchantRecurringConfirm');
  remove.addEventListener('click',()=>{confirmation.hidden=false;confirmation.scrollIntoView({block:'nearest',behavior:'smooth'})});
  document.querySelector('#merchantCancelRemoveRecurring').addEventListener('click',()=>{confirmation.hidden=true});
  document.querySelector('#merchantConfirmRemoveRecurring').addEventListener('click',()=>saveManagedRecurringProfile(merchant,'not_recurring'));
}
async function saveManagedRecurringProfile(merchant,verdict){
  const button=document.querySelector(verdict==='recurring'?'#merchantSaveRecurring':'#merchantConfirmRemoveRecurring');button.disabled=true;const original=button.textContent;button.textContent='Saving…';
  const lifecycle=document.querySelector('#merchantRecurringLifecycle').value,endMonth=document.querySelector('#merchantRecurringEndMonth').value;
  if(verdict==='recurring'&&lifecycle==='ended'&&!endMonth){showToast('Choose an end month for an ended profile.','End month required');button.disabled=false;button.textContent=original;return}
  const includedAliases=[...document.querySelectorAll('.merchant-recurring-alias:checked')].map(input=>input.value);
  if(verdict==='recurring'&&!includedAliases.length){showToast('Select at least one original merchant name.','Recurring scope required');button.disabled=false;button.textContent=original;return}
  const payload={canonical_group_id:merchant.canonical_group_id,verdict,recurring_type:document.querySelector('#merchantRecurringType').value,cadence:document.querySelector('#merchantRecurringCadence').value,lifecycle_status:lifecycle,end_month:lifecycle==='ended'?endMonth:'',included_aliases:verdict==='recurring'?includedAliases:[]};
  try{
    const response=await fetch('/api/recurring-profile/manage',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const result=await response.json();if(!response.ok)throw new Error(result.error||'Could not update recurring decision');
    state.recurringCache.clear();const data=await fetchMerchants(true);const search=document.querySelector('#merchantSearch')?.value||'',category=document.querySelector('#merchantCategoryFilter')?.value||'all';renderMerchantManagement(data,search,category,state.merchantRecurringFilter);openMerchantEditor(merchant.canonical_group_id);await loadRecurringPanel(true);showToast(verdict==='recurring'?`${merchant.display_name} is now tracked as recurring.`:`${merchant.display_name} is no longer tracked as recurring.`,'Recurring decision saved');
  }catch(error){showToast(error.message,'Recurring update failed');button.disabled=false;button.textContent=original}
}
function openMerchantEditor(groupId){
  const merchant=state.merchantData?.merchants.find(item=>item.canonical_group_id===groupId);if(!merchant)return;
  state.activeMerchant=merchant;
  document.querySelector('#merchantEditorTitle').textContent=merchant.display_name;
  document.querySelector('#merchantEditorSubtitle').textContent=`${merchant.aliases.length} aliases · ${merchant.transactions.toLocaleString()} transactions`;
  merchantEditorBody.innerHTML=`<section class="editor-section"><div class="editor-section-head"><div><h3>Display name</h3><p>The clean name shown in grouped rows. Imported merchant descriptions are not replaced.</p></div></div><label class="editor-field-label" for="merchantDisplayName">Display name</label><input class="editor-input" id="merchantDisplayName" value="${escapeHtml(merchant.display_name)}" data-original="${escapeHtml(merchant.display_name)}"></section><section class="editor-section"><div class="editor-section-head"><div><h3>Category rules by original name</h3><p>Each alias can keep a different permanent category, including local and travel variants.</p></div></div><div class="alias-editor"><div class="alias-editor-head"><span>Original statement name</span><span>Permanent category</span></div>${merchant.aliases.map(alias=>`<div class="alias-editor-row"><span><strong>${escapeHtml(alias.merchant_raw)}</strong><small>${escapeHtml(alias.merchant_normalized)} · ${alias.transactions} transactions</small></span><select class="editor-select merchant-alias-category" data-merchant="${escapeHtml(alias.merchant_normalized)}" data-original="${escapeHtml(alias.category)}" data-subcategory="${escapeHtml(alias.subcategory||'')}">${merchantCategoryOptions(alias.category)}</select></div>`).join('')}</div></section>${merchantRecurringEditor(merchant)}<section class="editor-section impact-review" id="merchantImpact" hidden><h4>Impact review</h4><ul id="merchantImpactList"></ul></section>`;
  merchantEditorBody.querySelectorAll('input,select').forEach(control=>control.addEventListener('input',resetMerchantReview));resetMerchantReview();setMerchantEditor(true);
  bindMerchantRecurringEditor(merchant);
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

const spendingAdjustmentModal=document.querySelector('#spendingAdjustmentModal');
const spendingAdjustmentBody=document.querySelector('#spendingAdjustmentBody');
const spendingAdjustmentRemove=document.querySelector('#spendingAdjustmentRemove');
function setSpendingAdjustmentModal(show){
  spendingAdjustmentModal.classList.toggle('show',show);
  spendingAdjustmentModal.setAttribute('aria-hidden',String(!show));
  if(show)document.querySelector('#spendingAdjustmentClose').focus();
  else{spendingAdjustmentRemove.dataset.confirmed='';spendingAdjustmentRemove.textContent='Remove adjustment'}
}
function adjustmentTransaction(transactionId){
  return [...state.detailTransactions,...state.categoryTransactions]
    .find(item=>Number(item.id)===Number(transactionId));
}
function updateAdjustmentAmount(){
  const transaction=state.activeAdjustmentTransaction;if(!transaction)return;
  const full=document.querySelector('input[name="adjustmentKind"]:checked')?.value==='full';
  const input=document.querySelector('#adjustmentAmount');
  if(full){input.value=Number(transaction.amount).toFixed(2);input.disabled=true}else input.disabled=false;
  const amount=Math.min(Number(transaction.amount),Math.max(0,Number(input.value)||0));
  document.querySelector('#adjustmentPersonalPreview').textContent=money(Number(transaction.amount)-amount);
}
function openSpendingAdjustment(transactionId){
  const transaction=adjustmentTransaction(transactionId);if(!transaction)return;
  if(Number(transaction.amount)<=0){showToast('Refund rows do not need a reimbursement adjustment.','Adjustment unavailable');return}
  state.activeAdjustmentTransaction=transaction;
  const existing=Boolean(transaction.adjustment_type);
  const partial=transaction.adjustment_type==='partial_reimbursement';
  const amount=existing?Number(transaction.reimbursed_amount):Number(transaction.amount);
  spendingAdjustmentBody.innerHTML=`<div class="transaction-snapshot"><div><span>Merchant</span><strong>${escapeHtml(transaction.merchant_display_name||transaction.merchant_raw)}<small>${escapeHtml(transaction.merchant_raw)}</small></strong></div><div><span>Purchase date</span><strong>${formatDate(transaction.transaction_date)}</strong></div><div><span>Card</span><strong>${escapeHtml(transaction.provider.toUpperCase())} •• ${escapeHtml(transaction.card_last4)}</strong></div><div><span>Card charge</span><strong>${sourceAmount(transaction.amount,transaction.charged_currency)}</strong></div></div><div class="adjustment-choice"><label><input type="radio" name="adjustmentKind" value="full"${partial?'':' checked'}><strong>Fully reimbursed</strong><small>None of this charge counts as personal spending.</small></label><label><input type="radio" name="adjustmentKind" value="partial"${partial?' checked':''}><strong>Partially reimbursed</strong><small>Only the unreimbursed remainder counts as personal spending.</small></label></div><div class="adjustment-fields"><label>Reimbursed amount<input id="adjustmentAmount" type="number" min="0.01" max="${Number(transaction.amount)}" step="0.01" value="${amount.toFixed(2)}"></label><label>Reimbursement date <small>(optional)</small><input id="adjustmentDate" type="date" value="${escapeHtml(transaction.reimbursement_date||'')}"></label><label class="adjustment-note">Note <small>(optional)</small><input id="adjustmentNote" maxlength="500" value="${escapeHtml(transaction.reimbursement_note||'')}" placeholder="For example: paid for another person"></label></div><div class="adjustment-help"><b>i</b><span>The original charge remains ${sourceAmount(transaction.amount,transaction.charged_currency)}. Personal amount after this adjustment: <strong id="adjustmentPersonalPreview">${money(Number(transaction.amount)-amount)}</strong>. A future bank-transfer matching feature can attach evidence without subtracting it twice.</span></div>`;
  spendingAdjustmentRemove.hidden=!existing;
  document.querySelectorAll('input[name="adjustmentKind"]').forEach(input=>input.addEventListener('change',updateAdjustmentAmount));
  document.querySelector('#adjustmentAmount').addEventListener('input',updateAdjustmentAmount);
  updateAdjustmentAmount();setSpendingAdjustmentModal(true);
}
async function refreshAfterAdjustment(){
  const mode=state.detailMode;const category=state.activeCategory;
  await loadDashboard();
  if(mode==='category-transactions'&&category)await openCategoryTransactions(category,null);
  else await openDetail('transactions',null);
}
async function saveSpendingAdjustment(remove=false){
  const transaction=state.activeAdjustmentTransaction;if(!transaction)return;
  const button=remove?spendingAdjustmentRemove:document.querySelector('#spendingAdjustmentSave');
  button.disabled=true;const originalLabel=button.textContent;button.textContent=remove?'Removing…':'Saving…';
  try{
    const payload={transaction_id:transaction.id,remove};
    if(!remove){
      const full=document.querySelector('input[name="adjustmentKind"]:checked')?.value==='full';
      payload.reimbursed_amount=full?Number(transaction.amount):Number(document.querySelector('#adjustmentAmount').value);
      payload.reimbursement_date=document.querySelector('#adjustmentDate').value;
      payload.note=document.querySelector('#adjustmentNote').value;
    }
    const response=await fetch('/api/transaction-adjustment',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const result=await response.json();if(!response.ok)throw new Error(result.error||'Could not save spending adjustment');
    setSpendingAdjustmentModal(false);
    showToast(remove?`${result.merchant_raw} counts at its original amount again.`:`Personal amount is now ${money(result.personal_amount)}.` ,remove?'Adjustment removed':'Reimbursement saved');
    await refreshAfterAdjustment();
  }catch(error){showToast(error.message,remove?'Removal failed':'Adjustment failed')}
  finally{button.disabled=false;button.textContent=originalLabel}
}

async function openImportAudit(){
  setDetailEyebrow();
  document.querySelector('#detailTitle').textContent='Import audit';
  document.querySelector('#detailSubtitle').textContent='Recent statement imports and duplicate handling.';
  detailTools.innerHTML='';detailContent.innerHTML='<p class="loading-state">Loading import history…</p>';setDetailModal(true);
  try{
    const data=await fetchMappingData();
    detailContent.innerHTML=`<div class="detail-summary"><strong>${state.data?.insights.duplicate_rows_prevented||0} duplicate rows prevented</strong><span>Recent 8 imports</span></div><div class="audit-list">${data.recent_imports.map(item=>`<div><span><strong>${escapeHtml(item.original_name)}</strong><small>${escapeHtml((item.provider||'unknown').toUpperCase())} ${item.card_last4?`•• ${escapeHtml(item.card_last4)}`:''}</small></span><span><strong class="audit-status ${escapeHtml(item.status)}">${escapeHtml(item.status.replaceAll('_',' '))}</strong><small>${item.inserted_rows} inserted · ${item.duplicate_rows} duplicates</small></span></div>`).join('')}</div>`;
  }catch(error){detailContent.innerHTML=`<p class="empty-state">${escapeHtml(error.message)}</p>`}
}

const recurringPanel=document.querySelector('#recurringPanel');
const recurringModal=document.querySelector('#recurringModal');
const recurringModalBody=document.querySelector('#recurringModalBody');
const recurringTypeOptions=['Fixed recurring','Usage-based recurring','Scheduled obligation','Other recurring'];
const recurringCadenceOptions=['Weekly','Monthly','Every 2 months','Quarterly','Every 6 months','Yearly','Custom','Irregular','Unknown'];
const recurringStatusLabels={confirmed:'Confirmed',variable:'Variable',expected:'Expected',missing:'Missing',increased:'Increased',paid:'Paid',upcoming:'Upcoming',due:'Due',overdue:'Overdue',active:'Active',ended:'Ended',paused:'Paused',unknown:'Unknown',completed:'Completed'};
const recurringStatusClass=value=>['missing','increased','due','overdue','unknown'].includes(value)?'amber':['ended','paused','completed'].includes(value)?'gray':'';
const recurringCacheKey=period=>`${period}|${period==='month'?state.month:''}|${state.card}`;
const shortMonth=value=>value?new Intl.DateTimeFormat('en-GB',{month:'short',year:'2-digit'}).format(new Date(`${value}-01T12:00:00`)):'—';

async function fetchRecurring(period,force=false){
  const key=recurringCacheKey(period);if(!force&&state.recurringCache.has(key))return state.recurringCache.get(key);
  const response=await fetch(`/api/recurring?period=${period}&month=${encodeURIComponent(state.month)}&card=${encodeURIComponent(state.card)}`,{cache:'no-store'});
  const data=await response.json();if(!response.ok)throw new Error(data.error||'Could not load recurring spending');state.recurringCache.set(key,data);return data;
}

function recurringPreviewRow(item,index,tab){
  const amount=tab==='series'?item.amount:item.charge;const status=recurringStatusLabels[item.status]||item.status;
  const alias=tab==='series'?(item.source_aliases||[]).join(' / '):(item.source_alias||'');
  const detail=tab==='series'?`${alias?`${alias} · `:''}${item.recurring_type} · ${item.cadence} · ${item.coverage}`:`${alias?`${alias} · `:''}Installment ${item.progress} · ${item.remaining_count} remaining`;
  return `<button type="button" class="recurring-preview-row" data-recurring-preview="${tab}" data-recurring-index="${index}"><span><strong>${escapeHtml(item.display_name)}</strong><small>${escapeHtml(detail)}</small></span><span class="recurring-row-value"><strong>${amount==null?'—':money(amount)}</strong><i class="recurring-status ${recurringStatusClass(item.status)}">${escapeHtml(status)}</i></span></button>`;
}

function renderRecurringPanel(data){
  const metrics=data.metrics,summary=data.verdict_summary,period=data.period.key;
  document.querySelector('#recurringPeriod').textContent=`${data.period.label} · reviewed verdicts: ${summary.recurring} recurring or obligations · ${summary.not_recurring} not recurring`;
  document.querySelector('#recurringSummary').innerHTML=period==='month'
    ?`<div><span>Recurring billed</span><strong>${money(metrics.recurring_billed)}</strong><small>Recurring and scheduled · excludes installments</small></div><div><span>Active series</span><strong>${metrics.active_series}</strong><small>Including upcoming obligations</small></div><div class="attention"><span>Needs attention</span><strong>${metrics.needs_attention}</strong><small>Missing, due, or changed</small></div><div><span>Commitments</span><strong>${money(metrics.installment_billed)}</strong><small>${metrics.installment_plans} installment plans</small></div>`
    :`<div><span>Recurring billed</span><strong>${money(metrics.recurring_billed)}</strong><small>${escapeHtml(data.period.label)} · excludes installments</small></div><div><span>Monthly billed average</span><strong>${money(metrics.recurring_average)}</strong><small>Recurring and scheduled only</small></div><div class="attention"><span>Needs attention</span><strong>${metrics.needs_attention}</strong><small>Missing, due, or changed</small></div><div><span>Commitments</span><strong>${money(metrics.installment_billed)}</strong><small>${metrics.installment_plans} plans in scope</small></div>`;
  document.querySelector('#recurringSeriesCount').textContent=`${data.series.length} total${data.series.length>3?' · scroll':''}`;
  document.querySelector('#recurringCommitmentCount').textContent=`${data.commitments.length} total${data.commitments.length>3?' · scroll':''}`;
  document.querySelector('#recurringSeriesPreview').innerHTML=data.series.length?data.series.map((item,index)=>recurringPreviewRow(item,index,'series')).join(''):'<p>No recurring or scheduled payments in this scope.</p>';
  document.querySelector('#recurringCommitmentPreview').innerHTML=data.commitments.length?data.commitments.map((item,index)=>recurringPreviewRow(item,index,'commitments')).join(''):'<p>No installment commitments in this scope.</p>';
  const recurringShare=Math.min(100,Number(metrics.recurring_share||0)),installmentShare=Math.min(100-recurringShare,Number(metrics.installment_share||0)),otherShare=Math.max(0,100-recurringShare-installmentShare);
  const burdenBar=document.querySelector('#recurringBurdenBar');
  burdenBar.setAttribute('aria-label',`Recurring and scheduled ${recurringShare.toFixed(1)}%, installments ${installmentShare.toFixed(1)}%, other spending ${otherShare.toFixed(1)}%`);
  burdenBar.innerHTML=`<i style="width:${recurringShare}%" title="Recurring & scheduled: ${recurringShare.toFixed(1)}%"></i><i style="width:${installmentShare}%" title="Installments: ${installmentShare.toFixed(1)}%"></i><i class="burden-other" style="width:${otherShare}%" title="Other spending: ${otherShare.toFixed(1)}%"></i>`;
  document.querySelector('#recurringBurdenLegend').innerHTML=`<span><i></i>Recurring & scheduled <strong>${recurringShare.toFixed(1)}%</strong></span><span><i></i>Installments <strong>${installmentShare.toFixed(1)}%</strong></span><span class="burden-other"><i></i>Other spending <strong>${otherShare.toFixed(1)}%</strong></span>`;
  document.querySelector('#recurringBurdenDetails').innerHTML=`<dt>Recurring average</dt><dd>${money(metrics.recurring_average)}</dd><dt>Installment average</dt><dd>${money(metrics.installment_average)}</dd><dt>Needs attention</dt><dd>${metrics.needs_attention}</dd>`;
}

async function loadRecurringPanel(force=false){
  try{renderRecurringPanel(await fetchRecurring(state.period,force))}
  catch(error){document.querySelector('#recurringPeriod').textContent=error.message;document.querySelector('#recurringSeriesPreview').innerHTML='<p>Recurring data is unavailable.</p>';document.querySelector('#recurringCommitmentPreview').innerHTML='<p>Commitment data is unavailable.</p>'}
}

function setRecurringModal(show){
  recurringModal.classList.toggle('show',show);recurringModal.setAttribute('aria-hidden',String(!show));
  if(show)document.querySelector('#recurringModalClose').focus();
}

function recurringMetrics(data,tab){
  if(tab==='commitments')return [['Installment charges',money(data.metrics.installment_billed),`${data.metrics.installment_plans} plans`],['Monthly average',money(data.metrics.installment_average),'Installments actually billed'],['Remaining balance',money(data.commitments.reduce((sum,item)=>sum+item.remaining,0)),'Estimated from available charges'],['Completed',data.commitments.filter(item=>item.status==='completed').length,'Plans in this scope']];
  return [['Recurring billed',money(data.metrics.recurring_billed),'Recurring and scheduled · excludes installments'],['Active series',data.metrics.active_series,'In the selected scope'],['Needs attention',data.metrics.needs_attention,'Missing, due, or changed'],['Installments',money(data.metrics.installment_billed),`${data.metrics.installment_plans} plans`]];
}

function recurringSelect(options,current,field,index){return `<span class="recurring-select-wrap"><select class="recurring-select recurring-select-${field.replaceAll('_','-')}" aria-label="${field==='recurring_type'?'Recurring type':'Cadence'}" data-recurring-field="${field}" data-recurring-row="${index}">${options.map(value=>`<option value="${escapeHtml(value)}"${value===current?' selected':''}>${escapeHtml(value)}</option>`).join('')}</select><i aria-hidden="true"></i></span>`}
const recurringColumns={
  series:[['display_name','Merchant'],['category','Category'],['recurring_type','Type'],['cadence','Cadence'],['amount','Amount'],['coverage','Expected / coverage'],['status','Status']],
  commitments:[['display_name','Purchase'],['category','Category'],['current_installment','Progress'],['paid','Paid'],['remaining','Remaining'],['status','Status']],
};
const recurringNumericKeys=new Set(['amount','current_installment','paid','remaining']);
function sortedRecurringRows(rows,sort){
  return [...rows].sort((left,right)=>{
    const leftValue=left[sort.key],rightValue=right[sort.key];
    const leftEmpty=leftValue===null||leftValue===undefined||leftValue==='';
    const rightEmpty=rightValue===null||rightValue===undefined||rightValue==='';
    if(leftEmpty||rightEmpty){if(leftEmpty&&rightEmpty)return 0;return leftEmpty?1:-1}
    const comparison=recurringNumericKeys.has(sort.key)?Number(leftValue)-Number(rightValue):transactionCollator.compare(String(leftValue),String(rightValue));
    return sort.direction==='asc'?comparison:-comparison;
  });
}
function recurringSortHeaders(tab,sort){
  return recurringColumns[tab].map(([key,label],index)=>{
    const active=sort.key===key,direction=active?sort.direction:'none',icon=active?(direction==='asc'?'↑':'↓'):'↕';
    const right=(tab==='series'&&index===4)||(tab==='commitments'&&[3,4].includes(index))?' class="right"':'';
    return `<th${right} aria-sort="${direction==='none'?'none':direction==='asc'?'ascending':'descending'}"><button type="button" data-recurring-sort="${key}">${label}<span aria-hidden="true">${icon}</span></button></th>`;
  }).join('');
}
function recurringHistory(history){
  const maximum=Math.max(...history.map(item=>Number(item.amount||0)),1);
  return history.length?`<h4>Actual billing history</h4><div class="recurring-history" aria-label="Actual merchant billing history">${history.map(item=>{const label=item.amount!=null?money(item.amount):item.state==='missing'?'Missing':'No charge';const css=item.state==='missing'?'missing':item.state==='charged'?'':'empty';const width=item.amount!=null?Math.max(12,Number(item.amount)/maximum*100):item.state==='missing'?38:18;return `<span title="${escapeHtml(formatMonth(item.month))}: ${escapeHtml(label)}"><i class="${css}" style="width:${width}%"></i><b>${escapeHtml(shortMonth(item.month))}</b><small>${escapeHtml(label)}</small></span>`}).join('')}</div><div class="recurring-history-legend"><span><i></i>Actual charge</span><span class="missing"><i></i>Expected but missing</span><span class="empty"><i></i>No charge expected</span></div>`:'<p>No recorded billing history is available.</p>';
}

function renderRecurringInspector(data,item,tab){
  const inspector=document.querySelector('#recurringInspector');if(!inspector)return;inspector.hidden=false;
  const suggestedEndMonth=item.end_month||state.month||data.period.end?.slice(0,7)||'';
  const controls=tab==='series'?`<div class="recurring-profile-controls"><label>Lifecycle<span class="recurring-control-select"><select id="recurringLifecycle"><option value="active"${item.lifecycle_status==='active'?' selected':''}>Active</option><option value="ended"${item.lifecycle_status==='ended'?' selected':''}>Ended</option><option value="paused"${item.lifecycle_status==='paused'?' selected':''}>Paused</option><option value="unknown"${item.lifecycle_status==='unknown'?' selected':''}>Unknown</option></select><i aria-hidden="true"></i></span></label><label class="recurring-end-month"${item.lifecycle_status==='ended'?'':' hidden'}>End month<input id="recurringEndMonth" type="month" value="${escapeHtml(item.end_month||'')}"></label><div class="recurring-lifecycle-actions"><button type="button" id="saveRecurringLifecycle" disabled>Save lifecycle</button></div><small id="recurringLifecycleHelp">Choose a lifecycle, then save it. Nothing changes while you are only selecting.</small></div>`:'';
  const alias=tab==='series'?(item.source_aliases||[]).join(' / '):(item.source_alias||'');
  const description=tab==='series'?`${alias?`Original name: ${alias}. `:''}The chart uses this merchant’s real billed months and amounts. Orange marks an expected charge that is absent; gray means no charge was expected.`:`${alias?`Original name: ${alias}. `:''}Finite installment plan kept separate from subscriptions. Remaining values are estimated when future billing dates are unavailable.`;
  inspector.innerHTML=`<div><h3>${escapeHtml(item.display_name)}</h3><p>${description}</p>${controls}</div><div>${recurringHistory(item.history||[])}</div>`;
  if(tab!=='series')return;
  const lifecycle=document.querySelector('#recurringLifecycle'),endLabel=document.querySelector('.recurring-end-month'),endMonth=document.querySelector('#recurringEndMonth'),help=document.querySelector('#recurringLifecycleHelp'),save=document.querySelector('#saveRecurringLifecycle');
  const syncLifecycleEditor=()=>{
    const ended=lifecycle.value==='ended';endLabel.hidden=!ended;lifecycle.closest('.recurring-profile-controls').classList.toggle('has-end-month',ended);
    if(ended&&!endMonth.value)endMonth.value=suggestedEndMonth;
    const effectiveEnd=ended?endMonth.value:'';
    const changed=lifecycle.value!==item.lifecycle_status||effectiveEnd!==(item.end_month||'');
    save.disabled=!changed||(ended&&!effectiveEnd);
    save.textContent=ended?'Confirm ended lifecycle':'Save lifecycle';
    help.textContent=ended?'After the selected month, this payment will no longer be expected. Its transaction history remains available.':'Choose a lifecycle, then save it. Nothing changes while you are only selecting.';
  };
  lifecycle.addEventListener('change',syncLifecycleEditor);endMonth.addEventListener('change',syncLifecycleEditor);
  save.addEventListener('click',async()=>{save.disabled=true;await updateRecurringProfile(item,{lifecycle_status:lifecycle.value,end_month:lifecycle.value==='ended'?endMonth.value:''})});
  syncLifecycleEditor();
}

function renderRecurringModal(data){
  document.querySelectorAll('[data-recurring-period]').forEach(button=>button.classList.toggle('active',button.dataset.recurringPeriod===state.recurringModalPeriod));
  document.querySelectorAll('[data-recurring-tab]').forEach(button=>button.classList.toggle('active',button.dataset.recurringTab===state.recurringTab));
  if(state.recurringTab==='verdicts'){
    const summary=data.verdict_summary;recurringModalBody.innerHTML=`<div class="recurring-verdict-grid"><div><span>Reviewed rows</span><strong>${summary.reviewed}</strong><small>From the approved workbook</small></div><div><span>Recurring / obligations</span><strong>${summary.recurring}</strong><small>Included in recurring analysis</small></div><div><span>Not recurring</span><strong>${summary.not_recurring}</strong><small>Excluded from this section</small></div><div><span>Unresolved</span><strong>${summary.unresolved}</strong><small>No decision still required</small></div></div>`;return;
  }
  const tab=state.recurringTab,sourceRows=tab==='series'?data.series:data.commitments,metrics=recurringMetrics(data,tab),sort=state.recurringSorts[tab];
  const rows=sortedRecurringRows(sourceRows,sort),headers=recurringColumns[tab],sortHeaders=recurringSortHeaders(tab,sort);
  const tableClass=tab==='series'?'recurring-table recurring-series-table':'recurring-table recurring-commitments-table';
  const colgroup=tab==='series'?'<colgroup><col class="rec-col-merchant"><col class="rec-col-category"><col class="rec-col-type"><col class="rec-col-cadence"><col class="rec-col-amount"><col class="rec-col-coverage"><col class="rec-col-status"></colgroup>':'<colgroup><col class="rec-col-purchase"><col class="rec-col-category"><col class="rec-col-progress"><col class="rec-col-paid"><col class="rec-col-remaining"><col class="rec-col-status"></colgroup>';
  const body=rows.map((item,index)=>tab==='series'?`<tr tabindex="0" data-recurring-detail-row="${index}"><td><strong>${escapeHtml(item.display_name)}</strong><small>${escapeHtml((item.source_aliases||[]).join(' / ')||'Click for actual billing history')}</small></td><td>${escapeHtml(item.category)}</td><td>${recurringSelect(recurringTypeOptions,item.recurring_type,'recurring_type',index)}</td><td>${recurringSelect(recurringCadenceOptions,item.cadence,'cadence',index)}</td><td><strong>${item.amount==null?'—':money(item.amount)}</strong></td><td>${escapeHtml(item.coverage)}</td><td><i class="recurring-status ${recurringStatusClass(item.status)}">${escapeHtml(recurringStatusLabels[item.status]||item.status)}</i></td></tr>`:`<tr tabindex="0" data-recurring-detail-row="${index}"><td><strong>${escapeHtml(item.display_name)}</strong><small>${escapeHtml(item.source_alias||'Click for billed installments')}</small></td><td>${escapeHtml(item.category)}</td><td>${escapeHtml(item.progress)}</td><td>${money(item.paid)}</td><td>${money(item.remaining)}</td><td><i class="recurring-status ${recurringStatusClass(item.status)}">${escapeHtml(recurringStatusLabels[item.status]||item.status)}</i></td></tr>`).join('');
  recurringModalBody.innerHTML=`<div class="recurring-detail-metrics">${metrics.map(metric=>`<div><span>${metric[0]}</span><strong>${metric[1]}</strong><small>${metric[2]}</small></div>`).join('')}</div><div class="recurring-table-wrap"><table class="${tableClass}">${colgroup}<thead><tr>${sortHeaders}</tr></thead><tbody>${body||`<tr><td colspan="${headers.length}"><strong>No matching items</strong><small>Nothing was billed or expected in this scope.</small></td></tr>`}</tbody></table></div><div class="recurring-inspector" id="recurringInspector" hidden></div>`;
  recurringModalBody.querySelectorAll('[data-recurring-sort]').forEach(button=>button.addEventListener('click',()=>{
    const key=button.dataset.recurringSort,current=state.recurringSorts[tab];
    state.recurringSorts[tab]=current.key===key?{key,direction:current.direction==='asc'?'desc':'asc'}:{key,direction:'asc'};
    renderRecurringModal(data);
  }));
  recurringModalBody.querySelectorAll('[data-recurring-detail-row]').forEach(row=>{const open=event=>{if(event?.target.closest('select,input,button'))return;recurringModalBody.querySelectorAll('[data-recurring-detail-row]').forEach(item=>item.classList.remove('selected'));row.classList.add('selected');const item=rows[Number(row.dataset.recurringDetailRow)];if(tab==='series')state.activeRecurringSeries=item.series_id;renderRecurringInspector(data,item,tab);setTimeout(()=>document.querySelector('#recurringInspector')?.scrollIntoView({block:'nearest',behavior:'smooth'}),0)};row.addEventListener('click',open);row.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();open(event)}})});
  recurringModalBody.querySelectorAll('[data-recurring-field]').forEach(select=>select.addEventListener('change',async event=>{const item=rows[Number(event.target.dataset.recurringRow)];await updateRecurringProfile(item,{[event.target.dataset.recurringField]:event.target.value})}));
  if(state.activeRecurringSeries&&tab==='series'){const index=rows.findIndex(item=>item.series_id===state.activeRecurringSeries);if(index>=0)recurringModalBody.querySelector(`[data-recurring-detail-row="${index}"]`)?.click()}
}

async function loadRecurringModal(force=false){
  recurringModalBody.innerHTML='<p class="loading-state">Loading recurring details…</p>';
  try{renderRecurringModal(await fetchRecurring(state.recurringModalPeriod,force))}catch(error){recurringModalBody.innerHTML=`<p class="empty-state">${escapeHtml(error.message)}</p>`}
}
function openRecurringModal(tab='series',index=null,seriesId=''){
  state.recurringModalPeriod=state.period;state.recurringTab=tab;state.activeRecurringSeries='';
  const panelData=state.recurringCache.get(recurringCacheKey(state.period));if(tab==='series')state.activeRecurringSeries=seriesId||(index!=null?panelData?.series[index]?.series_id||'':'');
  setRecurringModal(true);loadRecurringModal();
}
async function updateRecurringProfile(item,changes){
  const payload={canonical_group_id:item.canonical_group_id,recurring_type:changes.recurring_type||item.recurring_type,cadence:changes.cadence||item.cadence,lifecycle_status:changes.lifecycle_status||item.lifecycle_status,end_month:changes.end_month!==undefined?changes.end_month:(item.end_month||'')};
  const scrollTop=recurringModalBody.scrollTop;
  try{const response=await fetch('/api/recurring-profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const result=await response.json();if(!response.ok)throw new Error(result.error||'Could not update recurring profile');state.recurringCache.clear();showToast(payload.lifecycle_status==='ended'?'Ended lifecycle saved. Later periods will no longer expect this payment.':'Recurring profile saved to the local database.','Recurring updated');await loadRecurringPanel(true);await loadRecurringModal(true);setTimeout(()=>{recurringModalBody.scrollTop=scrollTop},0)}catch(error){showToast(error.message,'Recurring update failed');await loadRecurringModal(true);setTimeout(()=>{recurringModalBody.scrollTop=scrollTop},0)}
}

document.querySelector('#openRecurringModal').addEventListener('click',()=>openRecurringModal());
function openRecurringManagement(source=null){setRecurringModal(false);openMerchants(source,{recurringFilter:'all'})}
document.querySelector('#manageRecurringMerchants').addEventListener('click',()=>openRecurringManagement());
document.querySelectorAll('[data-recurring-open]').forEach(button=>button.addEventListener('click',()=>openRecurringModal(button.dataset.recurringOpen)));
recurringPanel.addEventListener('click',event=>{const row=event.target.closest('[data-recurring-preview]');if(row)openRecurringModal(row.dataset.recurringPreview,Number(row.dataset.recurringIndex))});
document.querySelector('#recurringModalClose').addEventListener('click',()=>setRecurringModal(false));
recurringModal.addEventListener('click',event=>{if(event.target===recurringModal)setRecurringModal(false)});
document.querySelectorAll('[data-recurring-period]').forEach(button=>button.addEventListener('click',()=>{state.recurringModalPeriod=button.dataset.recurringPeriod;state.activeRecurringSeries='';loadRecurringModal()}));
document.querySelectorAll('[data-recurring-tab]').forEach(button=>button.addEventListener('click',()=>{state.recurringTab=button.dataset.recurringTab;state.activeRecurringSeries='';loadRecurringModal()}));

document.addEventListener('click',event=>{
  const adjustmentTarget=event.target.closest('[data-adjust-transaction]');
  if(adjustmentTarget){event.preventDefault();event.stopPropagation();openSpendingAdjustment(adjustmentTarget.dataset.adjustTransaction);return}
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
  else if(action==='merchants')openMerchants(actionTarget)
  else if(action==='mapping')openMapping(actionTarget)
  else if(action==='duplicates')openImportAudit()
  else if(action==='largest')openDetail('transactions',actionTarget,state.data?.insights.largest_transaction?.merchant_raw||'')
  else if(action==='open-import'){setDetailModal(false);document.querySelector('#mappingSummary').hidden=true;setModal(true)}
  else if(action==='recurring')openRecurringManagement(actionTarget);
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
document.querySelector('#spendingAdjustmentClose').addEventListener('click',()=>setSpendingAdjustmentModal(false));document.querySelector('#spendingAdjustmentCancel').addEventListener('click',()=>setSpendingAdjustmentModal(false));spendingAdjustmentModal.addEventListener('click',event=>{if(event.target===spendingAdjustmentModal)setSpendingAdjustmentModal(false)});document.querySelector('#spendingAdjustmentSave').addEventListener('click',()=>saveSpendingAdjustment(false));spendingAdjustmentRemove.addEventListener('click',()=>{if(spendingAdjustmentRemove.dataset.confirmed==='1'){saveSpendingAdjustment(true);return}spendingAdjustmentRemove.dataset.confirmed='1';spendingAdjustmentRemove.textContent='Confirm removal'});
document.addEventListener('keydown',event=>{if(event.key==='Escape'){setManageMenu(false);setModal(false);setMerchantEditor(false);setTransactionEditor(false);setDetailModal(false);setRecurringModal(false);if(document.querySelector('#eventEditModal').classList.contains('show'))setEventEditModal(false);else closeEventModal();setEventCreateModal(false)}});
document.querySelector('#eventModalClose').addEventListener('click',closeEventModal);
document.querySelector('#eventModal').addEventListener('click',event=>{if(event.target.id==='eventModal')closeEventModal()});
document.querySelector('#eventGroupBack').addEventListener('click',()=>{if(state.activeEventGroup)openEventGroup(state.activeEventGroup.id)});
document.querySelector('#eventEditOpen').addEventListener('click',()=>setEventEditModal(true));
document.querySelector('#eventEditClose').addEventListener('click',()=>setEventEditModal(false));
document.querySelector('#eventEditCancel').addEventListener('click',()=>setEventEditModal(false));
document.querySelector('#eventEditModal').addEventListener('click',event=>{if(event.target.id==='eventEditModal')setEventEditModal(false)});
document.querySelector('#eventEditForm').addEventListener('submit',event=>{event.preventDefault();saveEventSettings(event.currentTarget)});
document.querySelector('#eventEditForm').elements.event_type.addEventListener('change',event=>syncEventDestinationField(event.currentTarget.form));
document.querySelector('#eventCreateButton').addEventListener('click',()=>setEventCreateModal(true));
document.querySelector('#eventCreateClose').addEventListener('click',()=>setEventCreateModal(false));
document.querySelector('#eventCreateCancel').addEventListener('click',()=>setEventCreateModal(false));
document.querySelector('#eventCreateModal').addEventListener('click',event=>{if(event.target.id==='eventCreateModal')setEventCreateModal(false)});
document.querySelector('#eventCreateForm').addEventListener('submit',event=>{event.preventDefault();createEvent(event.currentTarget)});
document.querySelector('#eventCreateForm').elements.event_type.addEventListener('change',event=>syncEventDestinationField(event.currentTarget.form));
document.addEventListener('click',event=>{if(event.target.matches('[data-transaction-event]'))event.stopPropagation()});
document.addEventListener('focusin',event=>{if(event.target.matches('[data-transaction-event]'))event.target.dataset.previous=event.target.value});
document.addEventListener('change',event=>{if(event.target.matches('[data-transaction-event]'))updateTransactionEvent(event.target)});
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
