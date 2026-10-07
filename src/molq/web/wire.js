// Generated from sdk/typescript/src/wire.ts. Do not edit.
export class MolqError extends Error {
    data;
    constructor(data) {
        super(data.message);
        this.data = data;
        this.name = "MolqError";
    }
    get kind() { return this.data.kind; }
}
export function unwrap(response, id) {
    if (response.jsonrpc !== "2.0" || (response.id !== id && !(response.id === null && response.error)))
        throw new Error("Invalid RPC response identity");
    if (response.error)
        throw new MolqError(response.error.data);
    return response.result;
}
export class HttpWire {
    endpoint;
    token;
    timeout;
    sequence = 0;
    constructor(endpoint, token = "", timeout = 130000) {
        this.endpoint = endpoint;
        this.token = token;
        this.timeout = timeout;
    }
    async call(method, params = {}) {
        const id = ++this.sequence;
        const data = JSON.stringify({ jsonrpc: "2.0", id, method, params });
        if (new TextEncoder().encode(data).length > 1048576)
            throw new Error("RPC frame exceeds 1 MiB");
        const mutation = ["clusters.register", "clusters.update", "clusters.remove", "config.set", "presets.set", "jobs.submit", "jobs.cancel", "jobs.cancel_many", "files.write", "files.transfer"].includes(method);
        try {
            const response = await fetch(this.endpoint.replace(/\/$/, "") + "/rpc", { method: "POST", headers: { "Content-Type": "application/json", Authorization: "Bearer " + this.token }, body: data, signal: AbortSignal.timeout(this.timeout) });
            if (!response.body)
                throw new Error("Empty RPC response");
            const reader = response.body.getReader();
            const parts = [];
            let size = 0;
            try {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done)
                        break;
                    size += value.length;
                    if (size > 1048576)
                        throw new Error("RPC response exceeds 1 MiB");
                    parts.push(value);
                }
            }
            finally {
                await reader.cancel();
            }
            const merged = new Uint8Array(size);
            let offset = 0;
            for (const part of parts) {
                merged.set(part, offset);
                offset += part.length;
            }
            return unwrap(JSON.parse(new TextDecoder().decode(merged)), id);
        }
        catch (error) {
            if (error instanceof MolqError)
                throw error;
            throw new MolqError({ kind: mutation ? "OUTCOME_UNKNOWN" : "RUNTIME_UNAVAILABLE", message: "RPC connection failed", outcome: mutation ? "unknown" : "not_applied", context: {} });
        }
    }
    async close() { }
    subscribe(callback, cursor) {
        const url = this.endpoint.replace(/^http/, "ws").replace(/\/$/, "") + "/ws";
        const socket = new WebSocket(url);
        socket.addEventListener("open", () => { socket.send(JSON.stringify({ token: this.token })); socket.send(JSON.stringify({ jsonrpc: "2.0", id: 1, method: "events.subscribe", params: cursor ? { cursor } : {} })); });
        socket.addEventListener("message", event => callback(JSON.parse(event.data)));
        return socket;
    }
}
