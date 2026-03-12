# UI Regression Checklist

## Build Baseline

- Run `cd frontend && npm run build` and confirm success.

## Core Workflow

- Create a new conversation, send the first topic, and verify draft plan appears.
- Save plan, start research, and ensure progress group can expand/collapse.
- Download report after completion.

## Realtime Progress Experience

- During RUNNING status, verify live progress rail is always visible at the top of timeline.
- Confirm stream status transitions are visible: connecting -> connected, and fallback when realtime channel fails.
- Validate that latest event time updates continuously and progress summary changes without manual refresh.
- Simulate long-running stage and confirm warning text appears (task still running, waiting advice visible).
- Confirm historical progress events are shown as narrative list with phase, summary, and progress percent.

## Keyboard Accessibility

- Use `Tab` to navigate top-level controls, sidebar menu buttons, composer, and editor actions.
- Confirm focused controls have a visible focus ring.
- In composer, press `Enter` to send and `Shift+Enter` to insert a newline.

## Dialog Consistency

- Trigger single delete, bulk delete, and rename actions.
- Confirm all actions use in-app dialogs (no browser native `confirm/prompt`).
- Validate cancel, close (`Esc`), and confirm behavior.

## Time and Typography

- Check conversation list and timeline timestamps render local time (e.g. `HH:MM:SS`).
- Confirm invalid timestamps degrade gracefully and do not break rendering.
- Verify small labels (status/role/mono text) remain readable on desktop and mobile.

## Responsive and Drawer Behavior

- In `375x812`, open/close conversation drawer and plan drawer with dedicated close buttons.
- Confirm opening one drawer closes the other.
- Confirm background page does not scroll while a mobile drawer or modal is open.

## Reduced Motion

- Enable system-level reduced motion and verify pulsing/loading animations are suppressed.
