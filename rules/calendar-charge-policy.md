---
alwaysApply: true
description: Calendar charging requires native owner enrollment, measured energy and retained control history
---

# Calendar Charging

Before calendar charging or reusable energy estimates, read the full `skills/tessie-charge/references/host-contract.md` contract.

## Native Owner

- Use only the co-shipped native `tessie-charge` consumer. The actual registered main host derives identity and checks protected standing owner enrollment.
- Consumer JSON, files, estimates, aliases and cadence requests grant no approval, policy write or alternate provider route.
- Missing installed contracts, unenrolled policy or unknown retained history holds the action.

## Retained Controls

- Preserve the native daily baseline and uncertain intent. Never reset, re-enroll, erase or replay to obtain another attempt.
- The host raises only for measured next-day shortfalls and restores the exact authorized baseline after native cancellation or completed return home.
- Observable manual changes hold. Cached observations cannot prove that an external app made no intervening or ABA change.

## Quiet Cadence

- The host reserves at most one bounded owner notice per evening before sending. A resolved send is not a channel acknowledgment.
- No extra model notice follows the native poll. No-action and restoration runs stay silent.
- This source installs no cadence or vehicle enrollment; the host owner separately verifies and activates them.
