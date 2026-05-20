# Zephyr Design Notes

The detailed token source of truth lives in `frontend/design.md`. This file summarizes how that design system maps onto the current product.

## Current Design Direction

Zephyr aims to feel like a precise operator console rather than a consumer chat app. The visual language is deliberately restrained, status-forward, and workstation-oriented.

## Active Design Tokens

From `frontend/design.md`:

- Primary: `#1A1C1E`
- Accent: `#B8422E`
- Background: `#F7F5F2`
- Typography: `Inter, sans-serif`
- Base text size: `16px`
- Default medium radius: `8px`

## How The Current UI Uses Those Tokens

- Primary is used for shell text, headers, and the darker structural surfaces.
- Accent is used for the main action path such as `Send Chat` and other execute-style actions.
- Background is used for the main reading and chat surfaces inside the control room.
- Rounded panels and buttons in the React shell follow the same moderate-radius system instead of using highly decorative shapes.

## Current Product Surfaces

- `AppShell` provides the control-room chrome, runtime snapshot, navigation, and global actions.
- `ChatWorkspace` is the main composition area for conversation, slash commands, and attachments.
- `CommandCenterPanel` focuses on inspection, configuration, and verification rather than freeform conversation.
- `MarkdownDocumentPage` renders docs and policy content inside the same shell so reference material stays part of the operator workflow.

## Implementation Notes

- The backend status snapshot exposes `design_system_path` as `frontend/design.md` so operators and contributors can find the current token source quickly.
- When visual changes are made, update both `frontend/design.md` and this summary if the design intent changes materially.