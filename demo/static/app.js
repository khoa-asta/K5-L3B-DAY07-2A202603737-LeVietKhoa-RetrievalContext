'use strict';
const $ = id => document.getElementById(id);
const labels = {'tfidf-syllable':'TF-IDF · âm tiết','tfidf-word':'TF-IDF · tách từ','dense':'Dense','hybrid':'Hybrid RRF','rerank':'Hybrid + rerank'};
const titles = {basic:'Retrieval cơ bản',compare:'So sánh & benchmark',advanced:'Advanced · IPCC',guide:'Hướng dẫn demo'};
const methodHelp = {
  'tfidf-syllable':'Khớp từ khóa, không nạp embedding. Phù hợp để bắt đầu demo.',
  'tfidf-word':'Underthesea gộp từ như dữ_liệu trước khi tính TF-IDF. Cần chờ nạp bộ tách từ.',
  dense:'Embedding query bằng MiniLM, tìm cosine trong Chroma. Top-k và filter áp dụng vào truy vấn.',
  hybrid:'Dense và TF-IDF theo từ, tối đa 12 candidates mỗi nhánh; hợp nhất bằng RRF (60).',
  rerank:'Tìm candidates bằng Hybrid rồi thoát model embedding. Nghỉ 10 giây, nạp CrossEncoder để xếp lại.'
};
let token='',liveStatus=null,activeTask=null,pollTimer=null,lastBasic=null,lastIPCC=null,agentJob=null,benchLoaded=false;
const fmt = n => Number(n || 0).toLocaleString('vi-VN');
function element(tag,className,text){const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=String(text);return node;}
function show(id,visible){$(id).classList.toggle('hidden',!visible);}
function notice(text,success=false){$('notice').textContent=text;$('notice').classList.toggle('success',success);show('notice',Boolean(text));}
async function api(path,body){
  const options={cache:'no-store',headers:{},signal:AbortSignal.timeout(10000)};
  if(body!==undefined){options.method='POST';options.headers={'Content-Type':'application/json','X-Demo-Token':token};options.body=JSON.stringify(body);}
  const response=await fetch(path,options);const data=await response.json();
  if(!response.ok)throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}
function navigate(view){
  if(!titles[view])view='basic';
  document.querySelectorAll('.view').forEach(node=>node.classList.toggle('hidden',node.id!==`view-${view}`));
  document.querySelectorAll('[data-view]').forEach(node=>{const active=node.dataset.view===view;node.classList.toggle('active',active);if(active)node.setAttribute('aria-current','page');else node.removeAttribute('aria-current');});
  $('crumb').textContent=titles[view];if(location.hash!==`#${view}`)history.replaceState(null,'',`#${view}`);
  if(view==='compare'&&!benchLoaded){benchLoaded=true;loadBenchmark('dev');}
}
function busyState(){
  const busy=Boolean(activeTask||liveStatus?.active_task);const paused=Boolean(liveStatus?.stopped);
  document.querySelectorAll('.run-action').forEach(button=>button.disabled=busy||paused||!token);
  const ready=Boolean(liveStatus?.advanced?.ready);
  $('agent-next').disabled=busy||paused||!ready||!token||(agentJob&&agentJob.status!=='pending');
  $('embed-batch').disabled=busy||paused||ready||!liveStatus?.advanced?.total_chunks||!token;
  $('resume').disabled=busy;
}
function renderStatus(state){
  liveStatus=state;
  $('connection').replaceChildren(element('i','status-dot'),document.createTextNode('Local sẵn sàng'));
  const advanced=state.advanced,total=advanced.total_chunks,done=advanced.indexed_chunks;
  $('index-title').textContent=total?`${fmt(done)} / ${fmt(total)} vectors`:'Chưa có catalog hoàn chỉnh';
  $('index-progress').style.width=`${total?Math.min(100,100*done/total):0}%`;
  $('index-detail').textContent=advanced.ready?'Index hoàn tất · có thể chạy agent từng bước.':`Còn ${fmt(Math.max(0,total-done))} vectors. Lượt mới chỉ xử lý số chunks đã chọn rồi thoát.`;
  $('prepare-count').textContent=`Catalog: ${advanced.prepared_pages} / 186 trang · Chroma ${advanced.status}`;
  $('agent-readiness').textContent=advanced.ready?'Index đã sẵn sàng. Mỗi lần bấm chạy đúng một bước retrieve → rerank → answer.':'Cần hoàn tất '+fmt(total)+' vectors trước khi chạy Dense → rerank → Qwen. TF-IDF IPCC bên trên đã dùng được.';
  show('pause-banner',state.stopped);
  const list=$('recent-list');list.replaceChildren();
  (state.recent_tasks||[]).slice(0,5).forEach(task=>{
    const button=element('button','history-item');button.append(element('span','history-state',task.status),element('span','history-query',task.query));
    button.addEventListener('click',()=>openTask(task.id));list.append(button);
  });
  show('recent-section',Boolean(state.recent_tasks?.length));busyState();
}
async function refreshStatus(){
  try{const state=await api('/api/status');renderStatus(state);if(state.active_task&&!activeTask)watchTask(state.active_task);}
  catch(error){$('connection').textContent='Mất kết nối local';if(!liveStatus)notice('Không kết nối được server. Giữ cửa sổ PowerShell chạy demo mở. '+error.message);}
}
async function submit(payload){
  try{
    notice('');const task=await api('/api/tasks',payload);watchTask(task.id);busyState();
  }catch(error){notice(error.message);}
}
function watchTask(id){activeTask=id;clearTimeout(pollTimer);show('task-banner',true);busyState();pollTask(id);}
async function pollTask(id){
  try{
    const task=await api(`/api/tasks/${id}`);$('task-phase').textContent=task.phase;
    const elapsed=task.started_at?Math.max(0,Math.floor((Date.now()-Date.parse(task.started_at))/1000)):0;
    $('task-detail').textContent=`${elapsed}s · Một worker · Lần nạp model đầu có thể mất 1–2 phút.`;
    if(['queued','running'].includes(task.status)){pollTimer=setTimeout(()=>pollTask(id),1300);return;}
    activeTask=null;show('task-banner',false);
    if(task.status==='success')renderTask(task);
    else {
      const detail=task.error || 'Tác vụ chưa hoàn tất.';
      notice(`${task.phase || task.status}: ${detail.trim().split('\n').pop()}`);
      if(detail.includes('\n')){const details=element('details');details.append(element('summary','','Chi tiết lỗi worker'),element('pre','',detail));$('notice').append(details);}
    }
    await refreshStatus();busyState();
  }catch(error){activeTask=null;show('task-banner',false);notice('Không đọc được trạng thái: '+error.message);busyState();}
}
async function openTask(id){
  try{
    const task=await api(`/api/tasks/${id}`);
    if(['running','queued'].includes(task.status)){watchTask(id);return;}
    if(task.status!=='success'){notice(task.error || 'Lượt chạy chưa có kết quả thành công.');return;}
    const view=task.request.kind==='basic'?'basic':task.request.kind==='compare'?'compare':'advanced';navigate(view);
    if(view==='basic'){$('basic-query').value=task.request.query;$('method').value=task.request.method;$('category').value=task.request.category;$('top-k').value=task.request.top_k;$('budget').value=task.request.budget;updateMethodHelp();}
    renderTask(task);
  }catch(error){notice(error.message);}
}
function renderTask(task){
  const result=task.result;
  if(result.kind==='basic')renderBasic(result,task);
  else if(result.kind==='compare')renderComparison(result);
  else if(result.kind==='ipcc')renderIPCC(result);
  else if(result.kind==='index')notice('Đã hoàn tất một lượt index. Tiến độ được lưu trong Chroma/checkpoint.',true);
  else if(result.kind==='agent')renderAgent(result);
}
function sourceName(row){return row.source_id==='dulieu'?'Luật Dữ liệu':row.source_id==='gddt'?'Luật Giao dịch điện tử':row.source_id;}
function sourceLink(row){const a=element('a','',`Mở PDF · trang ${row.page} ↗`);a.href=`/files/${encodeURIComponent(row.source_id)}.pdf#page=${encodeURIComponent(row.page)}`;a.target='_blank';a.rel='noopener';return a;}
function basicCard(row,index,contextIds){
  const card=element('article','evidence-card');const top=element('div','card-top');
  top.append(element('span','rank',String(index+1).padStart(2,'0')),element('span','source-title',sourceName(row)),element('span','source-page',`Trang ${row.page}`),element('span','score',Number(row.score).toFixed(4)));
  if(contextIds.has(row.id))top.append(element('span','context-chip','trong context'));
  const bottom=element('div','card-bottom');bottom.append(element('span','chunk-id',row.id),sourceLink(row));
  card.append(top,element('p','',row.text),bottom);return card;
}
function renderBasic(result,task){
  lastBasic={task_id:task.id,...result,total_seconds:task.elapsed_seconds};show('basic-empty',false);show('basic-meta',true);
  $('result-count').textContent=`${result.results.length} đoạn · top-${result.top_k}`;
  $('basic-meta').replaceChildren(element('span','',labels[result.method]),element('span','',`Điểm: ${result.score_type}`),element('span','',`${fmt(result.context.length)} ký tự context`),element('span','',`${task.elapsed_seconds}s tổng`));
  $('basic-meta').append(element('span','query-label',`Truy vấn: ${result.query}`));
  const list=$('evidence-content');list.replaceChildren();const ids=new Set(result.context_ids);
  result.results.forEach((row,index)=>list.append(basicCard(row,index,ids)));
  if(!result.results.length)list.append(element('p','section-note','Không có đoạn khớp truy vấn trong filter hiện tại. Điều này chưa chứng minh toàn bộ tài liệu thiếu evidence.'));
  $('context-text').textContent=result.context || 'Không có chunk vừa context budget hiện tại.';
  $('trace-text').textContent=JSON.stringify(lastBasic,null,2);
}
function renderComparison(result){
  const host=$('comparison-result');host.replaceChildren();
  result.outputs.forEach(output=>{
    const card=element('section','panel comparison-card');card.append(element('h3','',labels[output.method]),element('p','section-note',`${output.results.length} kết quả · ${output.elapsed_seconds}s gồm chuẩn bị index`));
    const tokens=element('div','token-list');(output.stages.query_terms||[]).forEach(term=>tokens.append(element('code','',term)));card.append(tokens);
    const list=element('ol');output.results.slice(0,5).forEach(row=>{const li=element('li','',`${sourceName(row)} · trang ${row.page} · ${Number(row.score).toFixed(4)}`);list.append(li);});card.append(list,element('p','field-help',output.query));host.append(card);
  });show('comparison-result',true);
}
function metricCell(metric){
  const cell=element('td');if(!metric){cell.textContent='—';return cell;}
  const row=element('div','metric-cell'),track=element('div','metric-track'),fill=element('div','metric-fill');fill.style.width=`${100*metric.rate}%`;track.append(fill);row.append(element('span','',`${metric.n}/${metric.N}`),track);cell.append(row);return cell;
}
async function loadBenchmark(split){
  document.querySelectorAll('[data-split]').forEach(button=>button.classList.toggle('selected',button.dataset.split===split));
  try{
    const saved=await api(`/api/benchmarks?split=${split}`);const host=$('benchmark-table');host.replaceChildren();
    if(!saved.available){host.textContent='Chưa có artifact benchmark của split này trên máy.';return;}
    const table=element('table'),head=element('thead'),tr=element('tr');
    ['PHƯƠNG PHÁP','HIT@1','EVIDENCE HIT@3','CONTEXT ĐỦ EVIDENCE','RETRIEVAL (ms)'].forEach(text=>tr.append(element('th','',text)));head.append(tr);table.append(head);
    const body=element('tbody');saved.data.summaries.forEach(summary=>{const row=element('tr');row.append(element('td','',labels[summary.method]),metricCell(summary.hit1),metricCell(summary.hit3),metricCell(summary.context_hit),element('td','',Number(summary.mean_ms).toLocaleString('vi-VN',{maximumFractionDigits:1})));body.append(row);});table.append(body);host.append(table);
  }catch(error){$('benchmark-table').textContent=error.message;}
}
function preview(page,label){
  $('preview-label').textContent=`${label} · PDF trang ${page}`;$('preview-pdf').href=`/files/ipcc.pdf#page=${page}`;
  show('preview-unavailable',false);show('preview-image',true);$('preview-image').alt=`Trang ${page} của báo cáo IPCC AR6`;
  $('preview-image').src=`/files/pages/${String(page).padStart(3,'0')}.png`;show('page-preview',true);
}
function renderIPCC(result){
  lastIPCC=result;show('ipcc-empty',false);show('download-ipcc',true);const host=$('ipcc-evidence');host.replaceChildren();
  host.append(element('p','section-note',`${result.query} · ${result.sources.length} nguồn · TF-IDF trên catalog đầy đủ`));
  result.sources.forEach((source,index)=>{
    const card=element('article','evidence-card'),top=element('div','card-top');top.append(element('span','rank',source.alias),element('span','source-title',source.label),element('span','source-page',`Trang ${source.source_pages.join(', ')}`));
    const details=element('details');const summary=element('summary','text-button','Xem text evidence & bbox');details.append(summary,element('p','',source.text),element('p','field-help',`bbox [${source.bbox.join(', ')}] · ${source.id}`));
    const bottom=element('div','card-bottom'),button=element('button','preview-button','Xem ảnh trang →'),pdf=element('a','',`Mở PDF trang ${source.page} ↗`);button.addEventListener('click',()=>preview(source.page,source.label));pdf.href=`/files/ipcc.pdf#page=${source.page}`;pdf.target='_blank';pdf.rel='noopener';bottom.append(button,pdf);card.append(top,details,bottom);host.append(card);
  });
  if(result.sources.length)preview(result.sources[0].page,result.sources[0].label);
  else{show('page-preview',false);host.append(element('p','section-note','Không có nội dung khớp bộ lọc này. Hãy thử tên figure/table chính xác hoặc từ khóa tiếng Anh.'));}
}
function renderAgent(result){
  agentJob=result;$('agent-query').value=result.question;$('agent-query').readOnly=true;const host=$('agent-result');host.replaceChildren();
  host.append(element('div','agent-out',result.answer || `Checkpoint ${result.agent_id}: bước tiếp theo ${result.next_stage}.`));
  if(result.sources?.length){
    const details=element('details');details.append(element('summary','text-button',`${result.sources.length} nguồn evidence đã truy xuất`));
    result.sources.forEach(source=>{const block=element('div','agent-out'),link=element('a','',`${source.alias} · ${source.label} · trang ${source.source_pages.join(', ')} ↗`);link.href=`/files/ipcc.pdf#page=${source.page}`;link.target='_blank';link.rel='noopener';block.append(link,element('p','',source.text));details.append(block);});host.append(details);
  }
  (result.citations||[]).forEach(citation=>{const link=element('a','',`Citation ${citation.alias} · ${citation.label} · PDF trang ${citation.page} ↗`);link.href=`/files/ipcc.pdf#page=${citation.page}`;link.target='_blank';link.rel='noopener';const line=element('p','field-help');line.append(link);host.append(line);});
  const download=element('button','text-button','Tải trace agent ↓');download.addEventListener('click',()=>downloadJSON(result,`${result.agent_id}.json`));host.append(download);
  $('agent-next').textContent=result.next_stage==='done'?'Đã có kết quả':`Chạy bước tiếp theo: ${result.next_stage}`;show('agent-result',true);busyState();
}
function downloadJSON(data,name){if(!data)return;const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const href=URL.createObjectURL(blob),link=element('a');link.href=href;link.download=name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(href),1000);}
function updateMethodHelp(){$('method-help').textContent=methodHelp[$('method').value];}

document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>navigate(button.dataset.view)));
document.querySelectorAll('[data-go]').forEach(button=>button.addEventListener('click',()=>{navigate(button.dataset.go);window.scrollTo({top:0,behavior:'smooth'});}));
document.querySelectorAll('[data-example]').forEach(button=>button.addEventListener('click',()=>{$('basic-query').value=button.dataset.example;$('basic-query').focus();}));
document.querySelectorAll('[data-ipcc-example]').forEach(button=>button.addEventListener('click',()=>{$('ipcc-query').value=button.dataset.ipccExample;$('ipcc-query').focus();}));
document.querySelectorAll('[data-result-tab]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('[data-result-tab]').forEach(tab=>{const on=tab===button;tab.classList.toggle('selected',on);tab.setAttribute('aria-selected',String(on));});['evidence','context','trace'].forEach(name=>show(`${name}-content`,name===button.dataset.resultTab));}));
document.querySelectorAll('[data-split]').forEach(button=>button.addEventListener('click',()=>loadBenchmark(button.dataset.split)));
$('method').addEventListener('change',updateMethodHelp);
$('basic-form').addEventListener('submit',event=>{event.preventDefault();submit({kind:'basic',query:$('basic-query').value,method:$('method').value,category:$('category').value,top_k:Number($('top-k').value),budget:Number($('budget').value)});});
$('compare-form').addEventListener('submit',event=>{event.preventDefault();submit({kind:'compare',query:$('compare-query').value,top_k:9,budget:2000});});
$('ipcc-form').addEventListener('submit',event=>{event.preventDefault();submit({kind:'ipcc',query:$('ipcc-query').value,content_kind:$('content-kind').value});});
$('embed-batch').addEventListener('click',()=>submit({kind:'index',stage:'embed',limit:Number($('index-limit').value)}));
$('agent-next').addEventListener('click',()=>submit({kind:'agent',query:$('agent-query').value,...(agentJob?{agent_id:agentJob.agent_id}:{})}));
const resetAgent=element('button','text-button agent-reset run-action','Bắt đầu câu hỏi mới');resetAgent.type='button';
resetAgent.addEventListener('click',()=>{agentJob=null;$('agent-query').readOnly=false;$('agent-next').textContent='Chạy bước đầu: retrieval';$('agent-result').replaceChildren();show('agent-result',false);busyState();});$('agent-next').after(resetAgent);
$('preview-image').addEventListener('error',()=>{show('preview-image',false);show('preview-unavailable',true);});
$('download-basic').addEventListener('click',()=>downloadJSON(lastBasic,'retrieval-demo.json'));
$('download-ipcc').addEventListener('click',()=>downloadJSON(lastIPCC,'ipcc-evidence.json'));
$('copy-context').addEventListener('click',async()=>{try{if(!lastBasic)return;await navigator.clipboard.writeText(lastBasic.context);notice('Đã sao chép context.',true);}catch{notice('Chưa sao chép được. Bạn có thể chọn text trong ô Context.');}});
async function control(action){try{await api('/api/control',{action});await refreshStatus();}catch(error){notice(error.message);}}
$('stop-task').addEventListener('click',()=>control('stop'));$('resume').addEventListener('click',()=>control('resume'));
window.addEventListener('hashchange',()=>navigate(location.hash.slice(1)));
async function init(){navigate(location.hash.slice(1));busyState();try{token=(await api('/api/session')).token;await refreshStatus();}catch(error){notice(error.message);}setInterval(()=>{if(!document.hidden)refreshStatus();},5000);}
init();
