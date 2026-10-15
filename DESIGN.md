# SettleSum design contract

The user-specified institutional cash application terminal is the visual authority. Operate mode: a controller scans deposits, selects a transaction, inspects its invoice state equation and GL journal, then exports or changes inputs.

Carbon #0B0E14 canvas and #11161F panels, with #E6EDF3 primary text. The user-pinned base palette is #1E2633 borders, #7D8590 muted labels, #2EA043 verification, #D29922 recoverable adjustment, #F85149 exception, and #388BFD controls. The implementation uses #242C38 structural rules and #1B232E soft row dividers. Accessible foreground variants are #929BA8 muted text, #5AC77C verified green, #E6B450 recovery amber, #FF827B exception red, and #70ACFF control blue; base accent values are not the foreground text tokens.

Inter labels and IBM Plex Mono numerical data; both fonts are self-hosted through bundled Fontsource files. Financial values use tabular numerals. Dense accounting tables, sharp panels and 1px rules define the terminal. Default buttons and fields have 2px radii; panels, tabs and register rows are square, while navigation icon buttons have 3px radii. The navigation rail is 62px wide, reducing to 52px at 1000px and 46px at 550px. A compact header and five measured telemetry metrics precede the deposit register and wider proof inspector. No decorative marketing or data visualization.

Signature interaction: change clearing date, re-run Python, and inspect the real discount-state and GL changes with a fresh measured run. The interface visibly marks pending inputs and never labels prior results current.

Above 800px, the desktop content fills a fixed 100dvh viewport. The bank register's deposit rows and the proof inspector scroll vertically and independently; the header and summary remain in view. At 800px and below, the register and inspector stack in normal page flow, with the deposit list capped at 380px and scrolling vertically. Wide accounting tables scroll horizontally. Drawers have keyboard dismissal and focus handling.
