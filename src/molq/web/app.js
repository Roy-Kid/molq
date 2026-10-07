// UI projection of the generated TypeScript protocol client; no native state rules.
import {HttpWire} from './wire.js';
const $=id=>document.getElementById(id);
let wire;
async function rpc(method,params={}){return wire.call(method,params);}
function message(error){$('message').textContent=error instanceof Error?error.message:String(error);}
async function refresh(){
  $('jobs').replaceChildren();
  const result=await rpc('jobs.observe',{cluster:$('cluster').value});
  for(const snapshot of result.snapshots){
    const row=document.createElement('div');row.className='job';
    const name=document.createElement('strong');name.textContent=snapshot.ref.native_id;
    const state=document.createElement('span');state.textContent=snapshot.state+' · '+snapshot.freshness.status;
    row.append(name,state);
    for(const [title,method,params] of [['Details','jobs.get',{ref:snapshot.ref}],['Logs','logs.read',{ref:snapshot.ref}],['Cancel','jobs.cancel',{ref:snapshot.ref}]]){
      const button=document.createElement('button');button.textContent=title;
      button.onclick=()=>rpc(method,params).then(value=>{$('details').textContent=JSON.stringify(value,null,2);}).catch(message);
      row.append(button);
    }
    $('jobs').append(row);
  }
  if(!result.snapshots.length)$('jobs').textContent='No jobs in this destination’s current queue.';
  message('Updated from the scheduler.');
}
$('connect').onclick=async()=>{
  try{
    wire=new HttpWire(location.origin,$('token').value);await rpc('molq.hello');
    const clusters=await rpc('clusters.list');$('cluster').replaceChildren();
    for(const cluster of clusters){const option=document.createElement('option');option.value=cluster.id;option.textContent=cluster.name;$('cluster').append(option);}
    $('connection').hidden=true;$('workspace').hidden=false;if(clusters.length)await refresh();else message('Register a destination to begin.');
  }catch(error){message(error);}
};
$('refresh').onclick=()=>refresh().catch(message);$('cluster').onchange=()=>refresh().catch(message);
$('submit').onsubmit=async event=>{
  event.preventDefault();try{
    const argv=[$('program').value,...$('arguments').value.split('\n').filter(Boolean)];
    const result=await rpc('jobs.submit',{cluster:$('cluster').value,spec:{execution:{units:[{id:'main',command:{kind:'argv',argv}}]}}});
    $('details').textContent=JSON.stringify(result,null,2);await refresh();
  }catch(error){message(error);}
};
