import type { Feature } from "../../api/client";

/**
 * The named splitting patterns, in the words a person reads.
 *
 * One map, because there were two: `FeatureCard` had these labels while
 * `FeatureEditForm` shipped `value.replaceAll("_", " ")` straight into its
 * `<option>` list, so the same Feature read "Component / system" on the card
 * and "component system" the moment you pressed Edit. docs/ux-plan.md §3.7
 * records that class of leak; PRODUCT.md Principle 3 is why it matters.
 */
export const PATTERN_LABEL: Record<Feature["splitting_pattern"], string> = {
  component_system: "Component / system",
  journey_stage: "Journey stage",
  mvp_vs_later: "MVP vs later",
  channel: "Channel",
  business_variant: "Business variant",
};
