import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {StdioWire} from '../dist/node.js';
import {Molq,methods,MolqError} from '../dist/index.js';

test('Native TS client uses the same Runtime and schema',async()=>{
  const temp=await mkdtemp(join(tmpdir(),'molq-ts-'));
  const python=process.env.MOLQ_TEST_PYTHON || resolve('../../.venv/bin/python');
  const mq=new Molq(new StdioWire([python,'-m','molq','runtime','rpc','--stdio','--registry',join(temp,'registry.db')]));
  try{
    const hello=await mq.connect();assert.equal(hello.release,'0.9.0');assert.deepEqual(hello.methods,methods);
    const destination=await mq.clusters.register({name:'local',scheduler:'shell',target_root:join(temp,'target')});
    const job=await destination.submitArgv([python,'-c','print("typescript")']);
    const result=await job.wait(10000,50);assert.equal(result.completion.successful,true);
    assert.match((await job.logs()).text,/typescript/);
    await assert.rejects(()=>mq.cluster('missing').submitArgv(['true']),error=>error instanceof MolqError && error.kind==='CLUSTER_NOT_FOUND');
  }finally{await mq.close();await rm(temp,{recursive:true,force:true});}
});

test('HTTP peer shares Runtime semantics and structured authentication errors', async()=>{
  const {spawn} = await import('node:child_process');
  const {createInterface} = await import('node:readline');
  const {once} = await import('node:events');
  const temp=await mkdtemp(join(tmpdir(),'molq-ts-http-'));
  const python=process.env.MOLQ_TEST_PYTHON || resolve('../../.venv/bin/python');
  const token='test-token-long-enough';
  const code=[
    'import asyncio,sys',
    'from pathlib import Path',
    'from aiohttp import web',
    'from molq.runtime import Runtime',
    'from molq.runtime.server import application',
    'async def serve():',
    ' runner=web.AppRunner(application(Runtime(Path(sys.argv[1])),sys.argv[2]))',
    ' await runner.setup()',
    ' site=web.TCPSite(runner,"127.0.0.1",0)',
    ' await site.start()',
    ' print(runner.addresses[0][1],flush=True)',
    ' try: await asyncio.Event().wait()',
    ' finally: await runner.cleanup()',
    'asyncio.run(serve())'
  ].join('\n');
  const child=spawn(python,['-c',code,join(temp,'registry.db'),token],{stdio:['ignore','pipe','inherit']});
  const lines=createInterface({input:child.stdout});
  let mq;
  try{
    const [port]=await Promise.race([once(lines,'line'),new Promise((_,reject)=>setTimeout(()=>reject(new Error('HTTP startup deadline')),5000).unref())]);
    const endpoint='http://127.0.0.1:'+port;
    const denied=Molq.http(endpoint,'wrong');
    await assert.rejects(()=>denied.connect(),error=>error instanceof MolqError && error.kind==='AUTH_REQUIRED');
    await denied.close();
    mq=Molq.http(endpoint,token);
    assert.equal((await mq.connect()).release,'0.9.0');
    const destination=await mq.clusters.register({name:'local',scheduler:'shell',target_root:join(temp,'target')});
    const job=await destination.submitArgv([python,'-c','print("http-peer")']);
    assert.equal((await job.wait(10000,50)).completion.successful,true);
    assert.match((await job.logs()).text,/http-peer/);
    await assert.rejects(()=>mq.rpc('clusters.register',{name:'bad',scheduler:'shell',target_root:'/target',supports_gpu:true}),error=>error instanceof MolqError && error.kind==='INVALID_INPUT');
  }finally{
    if(mq)await mq.close();
    const exited=once(child,'exit');
    child.kill();
    await exited;
    lines.close();
    await rm(temp,{recursive:true,force:true});
  }
});
