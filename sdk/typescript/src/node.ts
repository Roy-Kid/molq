/** Native Node stdio transport calls Runtime, never another client. */
import {spawn, ChildProcessWithoutNullStreams} from "node:child_process";
import {Wire, MolqError, unwrap} from "./wire.js";
export {Molq} from "./index.js";
export class StdioWire implements Wire {
  private process?: ChildProcessWithoutNullStreams;
  private sequence = 0;
  private pending = new Map<number,{resolve:(value:unknown)=>void;reject:(error:unknown)=>void;timer:ReturnType<typeof setTimeout>;mutation:boolean}>();
  constructor(private command: string[] = ["molq","runtime","rpc","--stdio"], private timeout = 130000) {}
  private start(): void {
    if (this.process) return;
    this.process = spawn(this.command[0],this.command.slice(1),{stdio:["pipe","pipe","pipe"]});
    this.process.stderr.pipe(process.stderr);
    const receive = (line: string) => {
      if (Buffer.byteLength(line)>1048576) { this.process?.kill(); return; }
      try { const response = JSON.parse(line); const pending = this.pending.get(response.id); if (!pending) return; clearTimeout(pending.timer); this.pending.delete(response.id); try { pending.resolve(unwrap(response,response.id)); } catch(error) { pending.reject(error); } }
      catch { this.process?.kill(); }
    };
    let buffered = Buffer.alloc(0);
    this.process.stdout.on("data", (chunk: Buffer) => {
      buffered = Buffer.concat([buffered,chunk]);
      let newline: number;
      while ((newline = buffered.indexOf(10)) >= 0) {
        const line = buffered.subarray(0,newline);
        buffered = buffered.subarray(newline+1);
        if (line.length > 1048576) {this.process?.kill(); return;}
        receive(line.toString("utf8"));
      }
      if (buffered.length > 1048576) this.process?.kill();
    });
    const failed = () => { for (const pending of this.pending.values()) { clearTimeout(pending.timer); pending.reject(new MolqError({kind:pending.mutation ? "OUTCOME_UNKNOWN":"RUNTIME_UNAVAILABLE",message:"Runtime stdio closed",outcome:pending.mutation?"unknown":"not_applied",context:{}})); } this.pending.clear(); };
    this.process.on("error",failed); this.process.on("close",failed); this.process.stdin.on("error",failed);
  }
  call<T>(method: string, params: Record<string,unknown> = {}): Promise<T> {
    this.start(); const id = ++this.sequence;
    const payload = JSON.stringify({jsonrpc:"2.0",id,method,params})+"\n";
    if (Buffer.byteLength(payload)>1048576) return Promise.reject(new Error("RPC frame exceeds 1 MiB"));
    const mutation=["clusters.register", "clusters.update", "clusters.remove", "config.set", "presets.set", "jobs.submit","jobs.cancel","jobs.cancel_many","files.write","files.transfer"].includes(method);
    return new Promise<T>((resolve,reject)=>{
      const timer = setTimeout(()=>{ this.pending.delete(id); reject(new MolqError({kind:mutation?"OUTCOME_UNKNOWN":"RUNTIME_UNAVAILABLE",message:"RPC deadline",outcome:mutation?"unknown":"not_applied",context:{}})); this.process?.kill(); },this.timeout);
      this.pending.set(id,{resolve:value=>resolve(value as T),reject,timer,mutation}); this.process!.stdin.write(payload);
    });
  }
  async close(): Promise<void> {
    const child = this.process;
    if (!child) return;
    child.stdin.end();
    await new Promise<void>(resolve=>{ if (child.exitCode!==null || child.signalCode!==null) {resolve();return;} const timer=setTimeout(()=>child.kill(),this.timeout); child.once("close",()=>{clearTimeout(timer);resolve();}); });
    this.process=undefined;
  }
}
