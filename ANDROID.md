# Sioyek for Android

The Android build of Sioyek ships the same reading experience as desktop: Smart Jump, searchable table of contents, highlights, bookmarks, and the touch-friendly UI. Configuration files (`prefs_user.config` and `keys_user.config`) are honored so you can keep the same workflow across devices.

## Portals on Android
- Portals work the same way as on desktop: enter portal mode from the touch main menu (chain icon) or by binding the `portal`/`create_visible_portal` commands, tap once to set the source location and tap again to pin the destination.
- The closest portal destination is shown in the portal preview pane; you can jump with `goto_portal`, send the overview to the portal target, or remove a link with `delete_portal`.
- Portal state is stored with your document, so links persist between sessions and can be recalled from the portal list.

## Shortcuts and touch controls
- Touch zones come with sensible defaults: the back/forward rectangles trigger `prev_state`/`next_state`, long-pressing them toggles marks, a top-center tap opens the touch menu, and a long press there toggles dark mode.
- Hardware buttons are configurable: set `volume_up_command` and `volume_down_command` in `prefs_user.config` to map the volume keys to any command (for example, paging or portal actions).
- Other touch rectangles (`*_tap_command` / `*_hold_command`) and external keyboards use the same command names as desktop, so you can assign portal actions or navigation shortcuts consistently across platforms.
