import { CircleQuestionMark } from "lucide-react";
import { useId, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { Modal, ModalBody, ModalHeader } from "../Modal";
import { Button } from "../ui/Button";

/**
 * One help affordance, in the same header position on every route.
 *
 * WCAG 2.2 3.2.6, and the gap `docs/ux-plan.md` §3.11 records: intake guidance
 * hid inside a `<details>` on one screen and nothing equivalent existed anywhere
 * else, so a person who learned the product on the dashboard had no idea help
 * was a thing the product did. Consistent help does not mean the same *content*
 * on every route; it means the same control, in the same place, in the same
 * order — which is what this is.
 *
 * The content is deliberately the shape of the journey rather than a manual:
 * `PRODUCT.md` Principle 3 says a business owner should never need the method,
 * so the six steps are described in what they ask of a person.
 */
const STEPS: [string, string][] = [
  ["Source", "The business need as it was written, plus any files attached as evidence."],
  ["Clarify", "The questions the analysis could not answer on its own. Answering these is the work."],
  ["Knowledge", "Whether this has been asked before, or contradicts something already agreed."],
  ["Confirm", "The owner signs off that the understanding is right before anything is generated from it."],
  ["Backlog", "The generated Epic, Features and Stories, read and shaped one level at a time."],
  ["Review & approve", "The evidence a reviewer needs, then the approval itself."],
];

export function HelpMenu() {
  const location = useLocation();
  // On the intake page itself, keep the draft that is open: a bare
  // /requirements/new#example opened a blank form over the owner's work.
  const onIntake = location.pathname === "/requirements/new";
  const [open, setOpen] = useState(false);
  const titleId = useId();
  const descriptionId = `${titleId}-description`;
  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        aria-label="Help"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen(true)}
      >
        <CircleQuestionMark size={18} aria-hidden="true" />
      </Button>
      {open ? (
        <Modal
          variant="dialog"
          labelledBy={titleId}
          describedBy={descriptionId}
          onClose={() => setOpen(false)}
          portal
        >
          <ModalHeader
            id={titleId}
            eyebrow="Help"
            title="How this product works"
            description="Every requirement moves through the same six steps. You can revisit any of them at any time."
            descriptionId={descriptionId}
          />
          <ModalBody>
            <ol className="m-0 grid list-none gap-3 p-0">
              {STEPS.map(([name, what], index) => (
                <li className="grid grid-cols-[auto_1fr] items-start gap-3" key={name}>
                  <span
                    className="bg-surface-sunken text-ink-muted text-meta grid size-6 place-items-center rounded-full font-semibold tabular-nums"
                    aria-hidden="true"
                  >
                    {index + 1}
                  </span>
                  <span>
                    <strong className="text-body">{name}</strong>
                    <span className="text-ink-muted text-body block">{what}</span>
                  </span>
                </li>
              ))}
            </ol>
            <p className="text-ink-muted text-body m-0">
              Not sure how to write a business need?{" "}
              <Link className="text-accent underline underline-offset-2" to={{ pathname: "/requirements/new", search: onIntake ? location.search : "", hash: "#example" }} onClick={() => setOpen(false)}>
                Read the worked example
              </Link>
              .
            </p>
          </ModalBody>
        </Modal>
      ) : null}
    </>
  );
}
