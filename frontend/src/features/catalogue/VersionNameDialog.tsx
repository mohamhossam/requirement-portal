import { useId, useState, type FormEvent } from "react";

import { ErrorNotice } from "../../components/ErrorNotice";
import { Button, Input, Modal, ModalBody, ModalFooter, ModalHeader } from "../../components/ui";

const MAX_NAME = 80;

/** Asks what a catalogue version is called, for starting one or renaming it. */
export function VersionNameDialog({
  title,
  description,
  initial = "",
  confirmLabel,
  saving,
  error,
  onSubmit,
  onCancel,
}: {
  title: string;
  description: string;
  initial?: string;
  confirmLabel: string;
  saving: boolean;
  error: string | null;
  onSubmit: (name: string) => void;
  onCancel: () => void;
}) {
  const titleId = useId();
  const [name, setName] = useState(initial);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (name.trim()) onSubmit(name.trim());
  };
  return (
    <Modal variant="dialog" labelledBy={titleId} onClose={onCancel}>
      <form onSubmit={submit}>
        <ModalHeader id={titleId} title={title} description={description} />
        <ModalBody>
          <Input label="Version name" required maxLength={MAX_NAME} value={name} autoFocus
            hint="Short and specific, so the team recognises it in the history."
            placeholder="Example: October integration update" onChange={(event) => setName(event.target.value)} />
          {error && <ErrorNotice message={error} />}
        </ModalBody>
        <ModalFooter>
          <Button onClick={onCancel}>Cancel</Button>
          <Button type="submit" variant="primary" disabled={!name.trim()} loading={saving} loadingLabel="Saving…">
            {confirmLabel}
          </Button>
        </ModalFooter>
      </form>
    </Modal>
  );
}
