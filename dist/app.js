const data={
  month:{all:['₪12,480','₪24,700','+₪12,220','₪402'],visa:['₪6,240','₪24,700','+₪18,460','₪201'],mastercard:['₪4,368','₪24,700','+₪20,332','₪141'],amex:['₪1,872','₪24,700','+₪22,828','₪60']},
  year:{all:['₪128,940','₪296,400','+₪167,460','₪424'],visa:['₪61,320','₪296,400','+₪235,080','₪202'],mastercard:['₪45,890','₪296,400','+₪250,510','₪151'],amex:['₪21,730','₪296,400','+₪274,670','₪71']},
  all:{all:['₪386,220','₪864,200','+₪477,980','₪418'],visa:['₪184,600','₪864,200','+₪679,600','₪200'],mastercard:['₪137,470','₪864,200','+₪726,730','₪149'],amex:['₪64,150','₪864,200','+₪800,050','₪69']}
};
const labels={month:'October 2026',year:'January – October 2026',all:'All recorded time'};
let period='month';
const cardFilter=document.querySelector('#cardFilter');
const values=['#spentValue','#incomeValue','#cashValue','#dailyValue'].map(id=>document.querySelector(id));
const toast=document.querySelector('#toast');
let toastTimer;

function updateDashboard(message){
  const card=cardFilter.value;
  data[period][card].forEach((value,index)=>values[index].textContent=value);
  document.querySelector('#dateLabel').textContent=labels[period];
  document.querySelectorAll('.payment-card').forEach(el=>el.classList.toggle('selected',el.dataset.card===card));
  if(card==='all') document.querySelectorAll('.payment-card').forEach(el=>el.classList.remove('selected'));
  document.querySelector('#toastText').textContent=message;
  toast.classList.add('show'); clearTimeout(toastTimer); toastTimer=setTimeout(()=>toast.classList.remove('show'),1800);
}

document.querySelector('#periodTabs').addEventListener('click',e=>{
  if(!e.target.dataset.period)return;
  period=e.target.dataset.period;
  document.querySelectorAll('#periodTabs button').forEach(btn=>btn.classList.toggle('active',btn===e.target));
  updateDashboard(`Showing ${e.target.textContent.toLowerCase()}`);
});
cardFilter.addEventListener('change',()=>updateDashboard(`Showing ${cardFilter.options[cardFilter.selectedIndex].text}`));
document.querySelectorAll('.payment-card').forEach(card=>card.addEventListener('click',()=>{
  cardFilter.value=card.dataset.card;
  updateDashboard(`Showing ${card.querySelector('.card-info strong').textContent}`);
}));

const modal=document.querySelector('#importModal');
function setModal(show){modal.classList.toggle('show',show);modal.setAttribute('aria-hidden',String(!show));if(show)document.querySelector('#modalClose').focus()}
document.querySelector('#uploadBtn').addEventListener('click',()=>setModal(true));
document.querySelector('#modalClose').addEventListener('click',()=>setModal(false));
modal.addEventListener('click',e=>{if(e.target===modal)setModal(false)});
document.addEventListener('keydown',e=>{if(e.key==='Escape')setModal(false)});
document.querySelector('.dropzone').addEventListener('click',()=>{
  setModal(false); document.querySelector('#toastText').textContent='Demo only — file import comes next'; toast.classList.add('show'); setTimeout(()=>toast.classList.remove('show'),2300);
});
