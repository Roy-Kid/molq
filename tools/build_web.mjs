// Ship the peer RPC codec with the static Web client.
import {readFileSync, writeFileSync} from "node:fs";
const source = new URL("../sdk/typescript/dist/wire.js", import.meta.url);
const target = new URL("../src/molq/web/wire.js", import.meta.url);
writeFileSync(target, "// Generated from sdk/typescript/src/wire.ts. Do not edit.\n" + readFileSync(source,"utf8"));
