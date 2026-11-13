(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.ClearSpendObservationClient=api;
})(typeof window!=='undefined'?window:globalThis,()=>{
  function buildObservationsUrl({period,card,month,incomeHidden=false}){
    const query=new URLSearchParams({
      period:String(period||'month'),
      card:String(card||'all'),
      month:String(month||''),
      income_hidden:String(Boolean(incomeHidden)),
    });
    return `/api/observations?${query.toString()}`;
  }

  async function loadObservationPayload(getJson,options,loadLegacy){
    try{
      return {source:'backend',payload:await getJson(buildObservationsUrl(options))};
    }catch(error){
      if(typeof loadLegacy!=='function')throw error;
      return {source:'browser-fallback',payload:await loadLegacy(error),backendError:error};
    }
  }

  return {buildObservationsUrl,loadObservationPayload};
});
