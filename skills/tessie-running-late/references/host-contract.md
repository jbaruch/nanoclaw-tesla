# Running-late Consumer Contract

Contract: tessie-running-late-consumer-v1

The genuine registered owner main source uses fixed `tessie_late_request` protocol1 through the co-shipped native IPC transport. There is no direct HTTP, caller-selected endpoint, role/context flag, approval JSON, send body, receipt import or fallback route. The host verifies its current registered owner source and protected Tessie policy before and after native reads. Published Host and Admin contracts must both be installed; source checkout or this consumer alone cannot activate sending.

The host consumes native Calendar/Drive Engine and cached navigation observations. It may send an owner notice containing a draft or a previously delegated recipient email, or suppress the event. It never wakes or controls a vehicle or exposes precise location. The executable decisions belong to `src/host-plugins/tessie-late/facts.ts` — `drivingTo`, `lateRoute`, `hasExternalContact`, `FIRST_DELAY_MINUTES`, `FOLLOWUP_DELAY_MINUTES` — and `service.ts::poll`; this consumer does not reimplement them.

A recipient send requires the real pre-event owner callback binding for the native event, recipient, sender account, fixed template and expiry. The host uses only the separately admitted Gmail identity `nanoclaw-host-tessie-running-late`. Missing native delegation, grant or complete preflight holds that recipient channel. Generic owner replies, approval JSON and receipts cannot supply delegation.

The displayed native approval card declares the shared delivery budget. `facts.ts::MAX_DELIVERIES_PER_EVENT` and `store.ts::reserve` own its enforcement across owner and recipient channels. Already-dispatched or uncertain attempts suppress another attempt; cancellation, reapproval and restart do not clear them. An owner notice plus recipient email leaves no follow-up. Never send an additional model-generated lateness message after the native poll. Approval cards are owner-requested pre-event workflow, not automatic drive prompts.

`prepare` takes only `event_id` and `recipient`, and returns the exact private proposal card. `cancel` takes only opaque `proposal_id`; `status` reads bounded counts without provider I/O. `poll` takes no fields. Dynamic identifiers enter the bounded `tessie-argv.py` literal-argv adapter; its one additional closed target resolves this co-shipped skill. Its native install is authoritative and an incomplete installed skill refuses developer fallback. Every CLI emits one JSON result or a fixed redacted nonzero diagnostic. The cadence precheck always emits `wake_agent:false`: native sends already happened, or task failure monitoring must repair the hold.

## State owner and recovery

The host `src/host-plugins/tessie-late/store.ts` solely owns callback-private DB4 tables, records2, installed by `callback-004-tessie-running-late.ts`. Consumers do not read, write, migrate or clear those tables. Its Stateful Artifacts gate-store exception refuses unknown/malformed records with actionable migration/reader guidance; treating them as absent would reopen a delivery budget. Budgets retain and validate the literal primary calendar/native event identity before scoped reads, so moved keys cannot reopen a consumed gate. Supported predecessor database migrations run only through the native installer. Earlier unshipped record1 stores/envelopes HOLD unchanged; the consumer cannot infer identities, migrate or reset them.

Backup ledger3 contains inactive Tessie record2 proposals, budgets and every uncertain/sent attempt alongside existing conference and Tasks gates. Restore is monotone, never restores actionable callback rows or approval, and cannot reopen a consumed slot. Preserve unknown state for the host owner to repair. Do not delete a gate, clear uncertain attempts, import caller receipts, or resend because an acknowledgment is missing.

This source contract does not claim native installation, owner callback, cadence, grant, vehicle-route or outbound acceptance. Keep issue7 open until those actual checks are complete.

Regression ownership: this provider's `tests/test_running_late.py` exercises the real co-shipped `NativeIPC.call` task/reply contract, CLI/adapter failure output and lookup refusal. `tests/test_encoded_argv.py` and `tests/test_skill_script_paths.py` retain literal dispatch and installed-path coverage. The native decision/state owner is covered by Core `src/host-plugins/tessie-late/*.test.ts`; these source tests supply no installed authority or live acceptance.
