---
name: SettleSum
description: A calm, readable cash-application workspace.
colors:
  background: "#0d121a"
  panel: "#151c27"
  raised: "#1b2533"
  line: "#2a3545"
  line-soft: "#232d3c"
  text: "#f2f4f8"
  muted: "#b0bac8"
  faint: "#93a2b5"
  green: "#8ed6ad"
  amber: "#f2c780"
  red: "#ffa59d"
  blue: "#9ac6ff"
  action: "#a8ceff"
  action-text: "#102138"
  action-hover: "#c3ddff"
  navigation: "#111823"
  navigation-active: "#24344a"
  navigation-active-text: "#c9e0ff"
  input: "#0f1621"
  input-border: "#42516a"
  drawer: "#151d29"
typography:
  display:
    fontFamily: "Inter, Arial, sans-serif"
    fontSize: "46px"
    fontWeight: 500
    lineHeight: 1.16
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "Inter, Arial, sans-serif"
    fontSize: "29px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.035em"
  title:
    fontFamily: "Inter, Arial, sans-serif"
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Inter, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Inter, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 500
  metadata:
    fontFamily: "Inter, Arial, sans-serif"
    fontSize: "12px"
  data:
    fontFamily: "IBM Plex Mono, monospace"
    fontSize: "14px"
rounded:
  badge: "4px"
  field: "7px"
  control: "8px"
  inset: "10px"
  panel: "12px"
  guide: "14px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "20px"
  xl: "24px"
  xxl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.action}"
    textColor: "{colors.action-text}"
    rounded: "{rounded.control}"
    padding: "9px 14px"
    height: "40px minimum"
  button-primary-hover:
    backgroundColor: "{colors.action-hover}"
  input:
    backgroundColor: "{colors.input}"
    textColor: "{colors.text}"
    rounded: "{rounded.field}"
    padding: "11px 12px"
  panel:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.panel}"
  welcome-guide:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.guide}"
    padding: "32px"
---

# Design System: SettleSum

## Overview

SettleSum is a calm cash-application workspace in Operate mode. The user-approved minimalist direction replaces the earlier cramped institutional terminal. Charcoal and slate surfaces, generous separation, readable language, and restrained ice-blue actions retain the source identity while changing its geometry, hierarchy, density, and layout.

The first action should be understandable quickly: add invoices and a payment, reconcile them, then inspect every cent. This is a design goal; no human ten-second usability study is claimed. This contract records the shipped code-led redesign in `frontend/src/styles.css` and its components. The bundled Impeccable launcher was unavailable; existing product context and implementation supplied the evidence.

## Colors

The frontmatter records rendered colors, replacing the superseded base palette. Opaque charcoal background, slate panels, lighter raised surfaces, and one-pixel structural lines establish separation. Text, muted, and faint tokens provide readable hierarchy. Ice blue identifies actions and focus; green marks verified accounting, amber identifies recoverable adjustments, and red marks exceptions. Status must also be expressed in words or icons.

Primary actions use the action fill and dark action text, with the lighter action-hover fill. The selected deposit uses `#24374f`; navigation uses the separate navigation-active color. Input borders are stronger than panel rules. Do not treat the former carbon palette as a second active token system.

## Typography

Inter supplies headings, prose, labels, controls, and summary metrics. IBM Plex Mono is reserved for financial values, identifiers, formulas, code, and audit data. Both families are self-hosted through bundled Fontsource files. Financial values use tabular numerals; money columns align right and stay on one line.

The desktop root is 15px with 1.5 line height; paragraphs use 1.65. Welcome guidance is 17px/1.8, reducing to 16px at 1300px and 15px at 550px. The welcome heading is 46px/1.16 by default, 54px from 1700px, 39px at 1300px, 38px at 1100px, 42px in the stacked 850px layout, and 32px/1.2 at 550px. Task headings are 29px, reducing to 26px on mobile. Guide headings are 22px, reducing to 20px; drawer headings are 24px, reducing to 22px.

Standard buttons and field labels are 14px; welcome actions are 15px. Financial table cells and deposit amounts remain 14px, including mobile deposit amounts. Table headers, metadata, badges, and secondary controls generally use 12–13px. The equation's small unit annotation is an existing 11px exception, not a financial-value style. Summary values are 31px by default, 27px at 1300px, 28px at 850px, and 30px at 550px. Mobile root size is 14px; composer text inputs and selects increase to 16px.

## Layout

The application uses normal document scrolling at every width. A fixed left navigation column is 196px wide; content has the corresponding left margin and a minimum height of 100dvh. There is no fixed-height desktop proof pane. The header is 76px high, main content has a 1740px maximum width and `26px 32px 40px` padding, and the footer follows the document.

Welcome uses a centered 1240px maximum-width grid with `1.25fr 1fr` columns and a 64px gap; its main region has 52px vertical padding. The loaded workbench uses `minmax(300px, 0.8fr) minmax(0, 1.4fr)` columns and a 20px gap. Its bank register is sticky 24px from the top; only the bounded deposit list scrolls internally, capped at 580px. Proof content remains in document flow. Invoice and journal tables preserve a 575px minimum width within horizontal scroll containers; source tables preserve 850px.

Responsive rules are inclusive max-width breakpoints unless stated otherwise:

- At 1300px, main/header/footer side padding becomes 24px, the welcome gap becomes 32px, and workbench columns become `0.8fr / 1.3fr` with a 16px gap. Page actions wrap; inspector identity may wrap.
- At 1100px, navigation becomes a 76px icon rail with 48px controls; text labels and session note hide. Composer invoice fields use three columns.
- At 850px, welcome and workbench stack. Welcome is capped at 620px with a 35px gap. The bank register loses stickiness; its list caps at 350px. Summary metrics use two columns with recovery across the second row. Workspace actions stack.
- At 550px, navigation is 56px with 40px by 44px controls; header height is 64px. Main padding becomes `22px 16px 30px`. Welcome actions fill the available width; summary metrics use one column. Composer customer, invoice, and deposit fields use one column.
- From 1700px, welcome gap increases to 90px and its heading to 54px.

Drawers are independently scrollable, full-height overlays: ordinary width 540px, composer width `min(1080px, 100%)`, always capped at viewport width. Sticky drawer headings and the sticky composer submit strip keep context and submission accessible. The mobile submit strip stacks its explanation and full-width action; its button has a 46px minimum height.

## Elevation & Depth

Data surfaces stay opaque and use tonal layering and one-pixel rules. The drawer scrim alone applies `blur(3px)` over `#050a12c9` to focus attention. Drawer shadow is `-16px 0 50px #0005`; export menu shadow is `0 12px 32px #0005`; solver popover shadow is `0 12px 30px #0006`. Shadows identify overlays rather than decorate accounting panels.

## Shapes

Controls use 8px corners, fields 7px, badges/counts 4px, inset forms/menus/dropzones 10px, accounting panels and summary 12px, and the welcome guide 14px. Tables, register rows, and underline tabs remain square within rounded containers. Status dots are circular; the brand symbol is three small skewed bars. The previous square-panel and 2px-control rules are superseded.

## Components

The empty workbench presents “Match payments. Find missing margin.”, a concise explanation, the primary “Build a live case” action, a secondary CSV import action, a separate explicitly synthetic sample, and a three-step payment-to-proof guide. Loaded controls, summaries, and empty numeric dashboards do not compete with this welcome state. A source-only import is staged until invoices and deposits are both available.

The loaded workspace leads with three business outcomes: payments matched, cash reconciled, and recoverable margin before collection. Journal status and variance remain visible: a balanced status requires at least one matched payment; an all-unmatched run says “No journal generated”; staged inputs say “Awaiting calculation”. Actual search nodes and measured Python execution time appear inside the native “Solver details” disclosure. Selected-payment search timing, ranking, full proof text, and alternatives appear inside “Search & ranking details”. These disclosures retain technical depth without placing telemetry ahead of the task.

The register provides search, filters, readable payment values, and a selected row. The proof inspector presents invoice states, deductions, a balanced journal, recovery notices, and source details. Recovery means a draft amount to reclaim before collection. A one-cent mismatch remains an exception. Pending-input banners identify proofs and metrics from the previous run; exports are disabled until results are current.

The live-case composer groups customer identity, open invoices, payments, optional remittance, amount helpers, and the reconciliation action. Imports separate invoice/deposit CSV from PDF/text remittance. Templates/downloads and flexible schema guidance use native disclosures. Files and edits apply to the current session; nothing is posted externally.

Buttons have a 40px default minimum height, 14px medium text, 8px corners, and a 0.16s background/border transition. Standard controls use slate fills and a `#3a485e` border; hover uses `#263448` and `#60718c`. Inputs use their documented background/border tokens and 7px corners. Focus-visible outlines are 2px blue with a 4px offset, including disclosure summaries. Drawers preserve focus trapping, Escape dismissal, and focus restoration. Reduced-motion preference disables transitions, animations, and smooth scrolling.

## Do's and Don'ts

- Do keep the first action explicit and synthetic examples honestly labeled.
- Do use readable prose and generous spacing while preserving exact financial data.
- Do retain horizontal table scrolling and normal document flow instead of shrinking essential numbers.
- Do disclose measured technical detail progressively and show pending-result warnings.
- Don't restore the tiny, dense terminal hierarchy or fixed-height desktop proof panes.
- Don't invent results, telemetry, collections, or production claims. Keep balanced proofs and exact-cent exception behavior intact.
