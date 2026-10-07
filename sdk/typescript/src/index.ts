/** Equal OOP projections of molq's public RPC contract. */
import {HttpWire, Wire, MolqError} from "./wire.js";
import type {JobSpec, JobRef, ClusterDefinition, ObservationResult} from "./types.js";
export * from "./types.js";
export {HttpWire, MolqError};
export type {Wire};
export type Observation = ObservationResult;
export class Molq {
  readonly clusters = new ClusterRegistry(this);
  private hello?: any;
  constructor(public wire: Wire, public registryId?: string) {}
  static http(endpoint: string, token: string): Molq { return new Molq(new HttpWire(endpoint,token)); }
  async connect(): Promise<any> {
    if (!this.hello) {
      const hello: any = await this.wire.call("molq.hello");
      if (hello.version.major !== 1) throw new MolqError({kind:"PROTOCOL_MISMATCH", message:"RPC major version mismatch", outcome:"not_applied",context:{}});
      if (this.registryId && this.registryId !== hello.registry_id) throw new MolqError({kind:"REGISTRY_MISMATCH",message:"Registry identity mismatch",outcome:"not_applied",context:{}});
      this.hello = hello;
    }
    return this.hello;
  }
  async rpc<T = unknown>(method: string, params: Record<string,unknown> = {}): Promise<T> { await this.connect(); return this.wire.call<T>(method,params); }
  cluster(name: string): Cluster { return new Cluster(this,name); }
  job(ref: JobRef): Job { return new Job(this,ref); }
  jobs(refs: JobRef[]): JobCollection { return new JobCollection(this,refs); }
  async close(): Promise<void> { await this.wire.close(); this.hello = undefined; }
}
export class ClusterRegistry {
  constructor(private molq: Molq) {}
  async register(definition: ClusterDefinition): Promise<Cluster> { const value = await this.molq.rpc<{id:string}>("clusters.register",definition); return this.molq.cluster(value.id); }
  list(): Promise<unknown[]> { return this.molq.rpc("clusters.list"); }
}
export class Cluster {
  constructor(private molq: Molq, public name: string) {}
  definition(): Promise<unknown> { return this.molq.rpc("clusters.get",{cluster:this.name}); }
  update(definition: ClusterDefinition, expectedRevision: number): Promise<unknown> { return this.molq.rpc("clusters.update",{cluster:this.name,definition,expected_revision:expectedRevision}); }
  remove(expectedRevision: number): Promise<unknown> { return this.molq.rpc("clusters.remove",{cluster:this.name,expected_revision:expectedRevision}); }
  async submit(spec: JobSpec, requestKey?: string): Promise<Job> { const value = await this.molq.rpc<{ref:JobRef}>("jobs.submit",{cluster:this.name,spec,...(requestKey ? {request_key:requestKey} : {})}); return this.molq.job(value.ref); }
  submitArgv(argv: string[]): Promise<Job> { return this.submit({execution:{units:[{id:"main",command:{kind:"argv",argv}}]}}); }
  validate(spec: JobSpec): Promise<unknown> { return this.molq.rpc("jobs.validate",{cluster:this.name,spec}); }
  preview(spec: JobSpec): Promise<unknown> { return this.molq.rpc("jobs.preview",{cluster:this.name,spec}); }
  list(): Promise<Observation> { return this.molq.rpc("jobs.list",{cluster:this.name}); }
  observe(cursor?: string): Promise<Observation> { return this.molq.rpc("jobs.observe",{cluster:this.name,...(cursor ? {cursor} : {})}); }
}
export class Job {
  constructor(private molq: Molq, public ref: JobRef) {}
  status(consistency: "live"|"bounded"|"cached" = "live", maxAge = 5): Promise<Observation> { return this.molq.rpc("jobs.get",{ref:this.ref,consistency,max_age:maxAge}); }
  cancel(requestKey?: string): Promise<unknown> { return this.molq.rpc("jobs.cancel",{ref:this.ref,...(requestKey ? {request_key:requestKey} : {})}); }
  wait(timeout = 3600000, interval = 1000): Promise<Observation> { return this.molq.jobs([this.ref]).wait(timeout,interval); }
  logs(stream: "stdout"|"stderr" = "stdout", offset = 0, limit = 262144): Promise<{text:string;next_offset:number}> { return this.molq.rpc("logs.read",{ref:this.ref,stream,offset,limit}); }
}
export class JobCollection {
  constructor(private molq: Molq, public refs: JobRef[]) {}
  status(consistency: "live"|"bounded"|"cached" = "live", maxAge = 5): Promise<Observation> { return this.molq.rpc("jobs.get_many",{refs:this.refs,consistency,max_age:maxAge}); }
  cancel(): Promise<unknown> { return this.molq.rpc("jobs.cancel_many",{refs:this.refs}); }
  observe(cursor?: string): Promise<Observation> { return this.molq.rpc("jobs.observe",{refs:this.refs,...(cursor ? {cursor} : {})}); }
  async wait(timeout = 3600000, interval = 1000): Promise<Observation> {
    if (timeout <= 0 || interval <= 0) throw new Error("wait timeout/interval must be positive");
    const deadline = Date.now()+timeout; let cursor: string|undefined;
    while (true) { const result = await this.observe(cursor); cursor = result.cursor; if (result.completion.all_confirmed_terminal) return result; const remaining = deadline-Date.now(); if (remaining<=0) throw new MolqError({kind:"WAIT_TIMEOUT",message:"Foreground wait deadline reached",outcome:"not_applied",context:{}}); await new Promise(resolve=>setTimeout(resolve,Math.min(interval,remaining))); }
  }
}
