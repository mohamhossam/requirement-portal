import { useId, useRef } from "react";

import { Modal, ModalFooter, ModalHeader } from "./Modal";
import { Button } from "./ui/Button";

type Props = {
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({ title, message, confirmLabel, onConfirm, onCancel }: Props) {
  // These ids were hardcoded, which collided whenever two confirmations were
  // mounted at once — the workspace can have both a re-analysis and a source
  // confirmation in the tree.
  const cancelRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const messageId = useId();

  return (
    <Modal variant="dialog" labelledBy={titleId} describedBy={messageId} onClose={onCancel} initialFocus={cancelRef}>
      {/* No "Please confirm" kicker above the title: the title is the question,
          and the uppercase label was the last of its kind in a dialog. */}
      <ModalHeader id={titleId} title={title} description={message} descriptionId={messageId} />
      <ModalFooter>
        {/* The opening focus goes to the safe action, not the destructive one.
            Every one of these dialogs confirms something irreversible, and a
            dialog that opens with Confirm focused turns Enter — the key a
            person is most likely to still be holding from whatever opened it —
            into the deletion itself. Cancel is first in DOM order anyway, so
            this is also where showModal() would have put focus; it is asked for
            explicitly so that reordering the footer cannot quietly move it. */}
        <Button ref={cancelRef} variant="secondary" type="button" onClick={onCancel}>Cancel</Button>
        <Button variant="danger" type="button" onClick={onConfirm}>
          {confirmLabel}
        </Button>
      </ModalFooter>
    </Modal>
  );
}
