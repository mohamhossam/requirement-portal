import { Button } from "./ui/Button";

export function EditorConflictNotice({ baselineVersion, currentVersion, currentContent, onReconcile }: {
  baselineVersion: number;
  currentVersion: number;
  currentContent: string;
  onReconcile: () => void;
}) {
  if (baselineVersion === currentVersion) return null;
  return (
    <aside className="error-notice" role="status">
      <p>This item changed while you were editing. Your draft is preserved below.</p>
      <details><summary>Compare the current saved content</summary><p style={{ whiteSpace: "pre-wrap" }}>{currentContent}</p></details>
      <Button type="button" variant="secondary" onClick={onReconcile}>
        I have reconciled my draft with this version
      </Button>
    </aside>
  );
}
