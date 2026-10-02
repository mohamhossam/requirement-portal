# ADR-0048 — Tailwind utilities in a named layer

Status: Accepted
Date: 2026-09-18

## Context

The frontend's styling is 1546 lines across fifteen files whose only ordering
principle is the order they are imported in. 123 selectors are declared in more
than one of them and depend on source order to override each other — three
visual generations layered on top of one another, with the comment at the top of
`src/styles/index.css` warning that the order is load-bearing.

Every new component so far has had to add to that pile, at the end, where its
rules win by being last. That is a cost that grows with each addition: a rule
added anywhere else may or may not take effect, and the only way to know is to
read the fourteen files around it.

Tailwind v4 was chosen for utilities. Adopting it naively would have been a
silent regression: v4 emits everything into `@layer utilities`, **unlayered CSS
beats any layer**, and all 1546 lines of this app's CSS were unlayered. Every
utility would have lost to any app rule on the same element, without error.

## Decision

The stylesheet entry declares the cascade explicitly, first mention losing:

```css
@layer theme, base, app, components, utilities;
```

Every existing app stylesheet is imported into **one** layer, `app`. Putting all
of them in the same layer is inert for app-versus-app conflicts — source order
inside a layer still decides, exactly as before — while making the whole body of
existing CSS lose to a utility rather than silently beat one.

Three further choices:

- **Preflight is not imported.** It is a whole-document reset, and these rules
  were written against browser defaults; importing it would restyle every
  heading, list and form control at once. The one consequence to know is that
  `border` then sets a width but no style, so utility borders are written
  `border border-solid`. Only `theme.css` and `utilities.css` are imported.
- **`tokens.css` stays the single source of the palette.** A `@theme` block maps
  each token to its Tailwind name (`--color-accent: var(--accent)`), so
  `bg-surface` and `border-line` render the same values the stylesheets use and
  a colour still changes in exactly one place.
- **Source scanning is declared, not inferred** (`@source`), so what Tailwind
  reads does not depend on where the build happens to start looking.

New components style themselves in utilities and add nothing to the ordered
chain. Two did so in this change, as proof rather than plumbing: `Toaster` and
`Skeleton`, whose stylesheets (`13-toasts.css`, `14-loading.css`) are deleted.
The chain is thirteen files rather than fifteen. `.sr-only` was also deleted, as
Tailwind ships the identical utility.

## Consequences

The conversion is measured, not asserted. Both revisions of the built bundle
were expanded and diffed: the `app` layer is byte-identical to the previous
bundle apart from the four intended changes (the `--success` token added, the
duplicated `.sr-only` removed, the two converted components' rules removed). The
converted markup was then rendered against the real bundle beside the markup it
replaces, and every computed property and bounding box matched at both test
viewports, apart from three spellings of identical values (`start` versus
`flex-start` in a grid, Tailwind's composed shadow with transparent placeholder
layers, `0px 0px` versus `0% 0%` on a background with no image).

CSS grows 6.7 kB raw, 1.7 kB gzipped. Utilities cost slightly more here than the
bespoke rules they replace, because a utility carries the machinery for variants
it is not using. The return is that the next component adds none.

Tailwind's scanner is deliberately liberal and generates a utility for any word
in the source that looks like a class name, so the bundle carries about 1.5 kB
of utilities nothing renders (`.filter`, `.transition`, `.container`). Harmless,
but worth knowing: a class name that collides with a utility name will now be
served by the utility, because the `utilities` layer wins. Only `.sr-only`
collided, and it was removed for that reason.

`@layer` for the app stylesheet itself — splitting those 1546 lines into layers
that express the intended precedence — is deliberately not done here. That means
paying down the override debt rule by rule, and it is not this change.

No domain, application, infrastructure, API, persistence or provider contract
changes.
