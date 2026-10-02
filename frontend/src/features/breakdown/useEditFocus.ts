import { useEffect, useRef } from "react";

/**
 * Focus follows an inline editor (WCAG 2.4.3): into its first field when it
 * opens, back to the Edit button when it closes. The card swaps its body for a
 * form and back, and both swaps unmounted whatever had focus, so a keyboard
 * user landed on `<body>` every time — measured on all three cards.
 */
export function useEditFocus(editing: boolean) {
  const trigger = useRef<HTMLButtonElement>(null);
  const form = useRef<HTMLDivElement>(null);
  const wasEditing = useRef(false);
  useEffect(() => {
    if (editing) form.current?.querySelector<HTMLElement>("input, textarea, select")?.focus();
    else if (wasEditing.current) trigger.current?.focus();
    wasEditing.current = editing;
  }, [editing]);
  return { trigger, form };
}
