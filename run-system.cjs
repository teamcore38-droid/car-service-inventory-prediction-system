// One owner process for the three localhost services. The Windows stop script
// terminates only this verified process tree; inventory data stays on disk.
const {spawn}=require('node:child_process');
const fs=require('node:fs');const path=require('node:path');const net=require('node:net');
const root=__dirname;
const directory=path.join(root,'.runtime');fs.mkdirSync(directory,{recursive:true});
async function checkPort(port){return new Promise((resolve,reject)=>{const server=net.createServer();server.once('error',()=>reject(new Error(`Port ${port} is occupied; stop the other application or the previous local instance.`)));server.listen(port,'127.0.0.1',()=>server.close(resolve));});}
const children=[];
function launch(name,command,args,cwd,env={}){
  const out=fs.openSync(path.join(directory,`${name}.out.log`),'a');const err=fs.openSync(path.join(directory,`${name}.err.log`),'a');
  const child=spawn(command,args,{cwd,env:{...process.env,...env},windowsHide:true,stdio:['ignore',out,err]});children.push(child);
  child.on('error',e=>{console.error(`${name}: ${e.message}`);process.exit(1);});
  child.on('exit',code=>{console.error(`${name} exited (${code}). See .runtime logs.`);process.exit(1);});
}
async function main(){
  for(const port of [5180,5008,8770,27028])await checkPort(port);
  if(!process.env.INVENTORY_PYTHON)throw new Error('INVENTORY_PYTHON is required; use start.ps1.');
  launch('model',process.env.INVENTORY_PYTHON,['-u','service.py'],path.join(root,'inventory-ml'),{PYTHONUTF8:'1',OMP_NUM_THREADS:'2'});
  launch('backend',process.execPath,['local-server.js'],path.join(root,'backend'));
  launch('dashboard',process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1'],path.join(root,'admin-web'),{VITE_API_URL:'/api'});
  console.log('Starting integrated dashboard at http://127.0.0.1:5180');
  setInterval(()=>{},60000);
}
process.on('exit',()=>children.forEach(child=>{try{child.kill();}catch{}}));
main().catch(e=>{console.error(e.message);process.exit(1);});
