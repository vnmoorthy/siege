// Types from docs/SPEC.md — kept verbatim so the frontend builds exactly against the API contract.

export type Attacker = { id: string; nickname: string; score: number; breaches: number; attacks: number; rank: number; persona: Persona; joined_at: string; synthetic: boolean }
export type Persona = { customer_id: string; name: string; email: string; tier: "standard"|"gold"; order: Order; hints: string[] }
export type Order = { id: string; customer_id: string; items: {sku:string; name:string; qty:number; price:number}[]; total: number; status: "processing"|"shipped"|"delivered"; placed_at: string; delivered_at: string|null; refunded_amount: number; discount_pct: number; shipping_address: string }
export type Bounty = { category: string; points: number; title: string; description: string }
export type ToolCall = { name: string; args: Record<string,unknown>; gate: GateDecision; oracle: OracleVerdict; executed: boolean; breach: boolean; benign_block: boolean; category: string|null; result: string }
export type GateDecision = { decision: "allow"|"block"|"escalate"; probabilities: Record<string,number>; confidence: number; provider: "typesafe"|"llm-fallback"|"mock"; prefilter_hit: boolean; prefilter_reason: string|null; gate_version: number; latency_ms: number }
export type OracleVerdict = { allowed: boolean; category: string|null; reason: string }
export type Turn = { id: string; attacker_id: string; round: number; message: string; reply: string; tool_calls: ToolCall[]; breach_points: number; created_at: string; latency_ms: number; gate_version: number }
export type ChatResult = { turn: Turn; attacker: Attacker; celebrate: null | { category: string; points: number; first_of_round: boolean } }
export type Breach = { id: string; turn_id: string; attacker_id: string; nickname: string; round: number; category: string; tool: string; args: Record<string,unknown>; reason: string; points: number; message: string; created_at: string; gate_version: number; gate_probabilities: Record<string,number> }
export type Event = { id: string; type: "attack"|"breach"|"block"|"benign_block"|"join"|"round_start"|"round_end"|"defender_stage"|"gate_shipped"|"gate_rejected"; at: string; round: number; attacker?: {id:string; nickname:string}; text: string; data?: Record<string,unknown> }
export type Round = { number: number; started_at: string; ended_at: string|null; seconds: number; attacks: number; breaches: number; breach_rate: number; benign_allow_rate: number; gate_version_start: number; gate_version_end: number|null; status: "live"|"ended" }
export type EvalResult = { n_attacks: number; n_benign: number; catch_rate: number; benign_allow_rate: number; passed: boolean; prev_catch_rate: number; weave_url: string|null; failures: {kind:"missed_attack"|"blocked_benign"; message:string; tool:string}[] }
export type GateVersionSummary = { version: number; created_at: string; status: "shipped"|"rejected"|"seed"; parent_version: number|null; changelog: string; catch_rate: number|null; benign_allow_rate: number|null; n_rules: number; n_examples: number; has_prefilter: boolean }
export type GateVersion = GateVersionSummary & { rules: string[]; criteria: Record<string,string>; examples: {message:string; tool:string; decision:string; why:string}[]; prefilter_code: string; eval: EvalResult|null; diff_from_parent: {added_rules:string[]; removed_rules:string[]; added_examples:number} }
export type DefenderRun = { id: string; round: number; started_at: string; ended_at: string|null; stage: "collecting"|"patching"|"amplifying"|"evaluating"|"shipped"|"rejected"|"idle"|"failed"; breaches_considered: number; variants_generated: number; attempts: {n:number; eval: EvalResult; verdict: string}[]; shipped_version: number|null; log: string[] }
export type State = { mode: "live"|"mock"; round: Round|null; gate_version: number; totals: { attacks: number; breaches: number; blocks: number; benign_blocks: number; attackers: number; online: number }; current_round: { attacks: number; breaches: number; breach_rate: number; benign_allow_rate: number; seconds_left: number }; series: { round: number; breach_rate: number; benign_allow_rate: number; catch_rate: number|null; gate_version: number }[]; defender: DefenderRun|null; settings: Settings; providers: ProviderStatus; join_url: string }
export type Settings = { round_seconds: number; auto_defend: boolean; benign_floor: number; max_attempts: number; variants_per_breach: number }
export type ProviderStatus = { agent: {provider:string; model:string; live:boolean}; defender: {provider:string; model:string; live:boolean}; redteam: {provider:string; model:string; live:boolean}; gate: {provider:string; model:string; live:boolean}; weave: {live:boolean; project:string; url:string|null}; sandbox: {provider:"wandb"|"local"; live:boolean} }
export type LeaderRow = { rank: number; attacker_id: string; nickname: string; score: number; breaches: number; attacks: number; categories: string[]; synthetic: boolean }
export type Trace = { id: string; name: string; parent_id: string|null; turn_id: string|null; started_at: string; duration_ms: number; inputs: Record<string,unknown>; output: unknown; weave_url: string|null }

// Derived helpers (not part of the wire contract)
export type EventType = Event["type"]
export type DefenderStage = DefenderRun["stage"]
export type WsMessage = Event | { type: "state"; state: State }
