# Running-late Consumer Contract

Contract: tessie-running-late-consumer-v1

The genuine registered owner main source uses fixed `tessie_late_request` protocol1 through the co-shipped native IPC transport. There is no direct HTTP, caller-selected endpoint, role/context flag, approval JSON, send body, receipt import or fallback route. The host verifies its current registered owner source and protected Tessie policy before and after native reads. Published Host and Admin contracts must both be installed; source checkout or this consumer alone cannot activate sending.

The host reads primary Calendar meeting-outbound Drive Engine blocks and their exact linked event, then cached Tessie route fields for current non-archived admitted vehicles. Only an awake driving vehicle with a fresh matching destination and a unique event/route match is eligible. No wake, location output, control or passenger action is requested. Navigation ETA already includes traffic; traffic delay is not added again. Wrong, stale or ambiguous routes remain silent/held.

An initial delay must exceed ten minutes. An unchanged event with attendees can produce one owner notice with a ready-to-send draft. A recipient found in the actual event requires a pre-event private, fully bound owner callback approving that event, recipient, sender account, expiry and fixed template. A literal external mailbox in the event may be used only through this explicit event delegation. Sending uses the separately admitted host Gmail identity `nanoclaw-host-tessie-running-late`, never a conference, Tasks or refund grant. Missing grant or uncertain preflight holds sending.

There are at most TWO automatic lateness messages TOTAL per native event across owner and recipient channels. Slots are durably reserved globally before dispatch. An owner notice plus one recipient email exhausts both, so no follow-up follows. Without recipient dispatch, the only remaining slot may be a worsening owner follow-up exceeding twenty minutes and the earlier delay. Failed or uncertain dispatches consume slots. New proposals, cancellation, reapproval, restart, archive restore or event edits cannot reset a budget. Approval cards are owner-requested pre-event workflow, not automatic drive notifications.

`prepare` takes only `event_id` and `recipient`, and returns the exact private proposal card. `cancel` takes only opaque `proposal_id`; `status` reads bounded counts without provider I/O. `poll` takes no fields. Dynamic identifiers enter the bounded `tessie-argv.py` literal-argv adapter; its one additional closed target resolves this co-shipped skill. Its native install is authoritative and an incomplete installed skill refuses developer fallback. Every CLI emits one JSON result or a fixed redacted nonzero diagnostic. The cadence precheck always emits `wake_agent:false`: native sends already happened, or task failure monitoring must repair the hold.

## State owner and recovery

The host `src/host-plugins/tessie-late/store.ts` solely owns callback-private DB4 tables, records1, installed by `callback-004-tessie-running-late.ts`. Consumers do not read, write, migrate or clear those tables. Its Stateful Artifacts gate-store exception refuses unknown/malformed records with actionable migration/reader guidance; treating them as absent would reopen a delivery budget. Supported predecessor database migrations run only through the native installer.

Backup ledger3 contains inactive Tessie record1 proposals, budgets and every uncertain/sent attempt alongside existing conference and Tasks gates. Restore is monotone, never restores actionable callback rows or approval, and cannot reopen a consumed slot. Preserve unknown state for the host owner to repair. Do not delete a gate, clear uncertain attempts, import caller receipts, or resend because an acknowledgment is missing.

This source contract does not claim native installation, owner callback, cadence, grant, vehicle-route or outbound acceptance. Keep issue7 open until those actual checks are complete.
