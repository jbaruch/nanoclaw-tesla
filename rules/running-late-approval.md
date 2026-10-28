---
alwaysApply: true
description: Running-late messages use event-specific native approval and one shared two-attempt budget
---

# Running-late Approval

Before preparing delegation or invoking running-late, read the complete `skills/tessie-running-late/references/host-contract.md` contract.

## Native Authority

- Use only the co-shipped native running-late workflow; no provider calls, context flags or approval/receipt JSON.
- An owner-requested pre-event proposal grants nothing until the actual private owner callback resolves against that exact event, recipient, sender account, template and expiry.

## Shared Delivery Budget

- At most TWO automatic lateness messages TOTAL per event across owner and recipient channels. An owner notice plus recipient email leaves no follow-up slot.
- Failed/uncertain attempts consume slots. Never resend, reset history, wake a vehicle or send another model-generated notification after the native poll.

## Held Operations

- The owner can cancel delegation without resetting history.
- Missing/unknown native contracts, state or grants hold the action.
- Source publication is not native acceptance.
