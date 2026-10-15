# Final interface direction and research

The final pass addresses two user-raised problems: a first-time visitor could not quickly see what to do, and the terminal's tiny type and repeated chrome obscured its useful accounting work.

## Decisions applied

- Replace the empty dashboard with a purpose statement, a direct create/import path, and an explicitly synthetic sample option. The initial ledger remains completely empty.
- Use labeled navigation, sentence-case actions, and finance language. Describe the input and outcome before explaining the solver.
- Show three business outcomes after reconciliation. Keep actual timing and search-node telemetry available through **Solver details**, with exact proof and balanced journals still available in the workbench.
- Raise body/control type and space related information consistently. Keep tabular monospace financial values, but stop using technical monospace for every UI label.
- Use restrained charcoal surfaces and one quiet blue action accent. Opaque data surfaces preserve readability; drawer background blur only communicates the active editing layer.
- Keep source templates/downloads and column documentation in expandable sections so they remain findable without preceding every upload with five more controls.
- Use normal document scrolling and responsive stacking instead of squeezing the whole accounting proof into a shrinking fixed-height viewport.

## Sources

1. [Nielsen Norman Group — Designing Empty States in Complex Applications](https://www.nngroup.com/articles/empty-state-interface-design/): empty states should explain status, provide learning cues, and offer direct paths to key tasks.
2. [Nielsen Norman Group — Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/): prioritize the main tasks and defer advanced choices until they are relevant.
3. [IBM Carbon — Data table guidelines](https://www.carbondesignsystem.com/building-blocks/core/components/data-table/guidelines): preserve familiar table interactions, clear headings, selection, and distinct numeric alignment.

These sources support the design decisions; they do not establish that SettleSum has passed a human usability study. Automated verification checks visible first actions, readable computed type, actual workflows, keyboard behavior, and responsive overflow. A fresh independent design review evaluates the rendered screenshots before shipping.
