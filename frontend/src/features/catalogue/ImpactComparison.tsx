import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GitCompareArrows, Plus, Square, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { errorMessage } from "../../api/errors";
import {
  knowledgeApi,
  type ImpactComparison as Comparison,
  type KnowledgeRelease,
  type SampleRequirement,
} from "../../api/knowledge";
import { ErrorNotice } from "../../components/ErrorNotice";
import {
  Badge,
  Button,
  Input,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Textarea,
  type BadgeTone,
} from "../../components/ui";
import { catalogueKeys } from "./keys";

const MAX_SAMPLES = 20;
const MAX_CHARACTERS = 2000;

type Row = {
  key: string;
  query: string;
  state: "waiting" | "running" | "done" | "failed";
  result?: Comparison;
  error?: string;
};

/** What changed for one requirement, in words; colour only repeats it. */
function outcomeOf(result: Comparison): { label: string; tone: BadgeTone; detail: string } {
  const before = new Map(result.in_use.systems.map((item) => [item.id, item.name]));
  const after = new Map(result.this_version.systems.map((item) => [item.id, item.name]));
  const added = [...after].filter(([id]) => !before.has(id)).map(([, name]) => `+ ${name}`);
  const removed = [...before].filter(([id]) => !after.has(id)).map(([, name]) => `− ${name}`);
  const detail = [...added, ...removed].join(", ");
  if (!added.length && !removed.length) return { label: "Same systems", tone: "success", detail };
  if (before.size === 0) return { label: "Now finds systems", tone: "accent", detail };
  if (after.size === 0) return { label: "Now finds none", tone: "danger", detail };
  return { label: "Changed", tone: "warning", detail };
}

function Side({ impact }: { impact: Comparison["in_use"] }) {
  return (
    <div className="grid gap-1">
      <span>{impact.systems.map((item) => item.name).join(", ") || "None"}</span>
      {impact.uncertainty && <span className="text-meta text-ink-muted">Not certain: {impact.uncertainty}</span>}
    </div>
  );
}

function Samples({ onRun, running }: { onRun: (items: SampleRequirement[]) => void; running: boolean }) {
  const client = useQueryClient();
  const samples = useQuery({ queryKey: catalogueKeys.samples, queryFn: knowledgeApi.samples });
  const [edited, setEdited] = useState<SampleRequirement[] | null>(null);
  const [text, setText] = useState("");
  const list = edited ?? samples.data?.items ?? [];
  const save = useMutation({
    mutationFn: () => knowledgeApi.saveSamples(samples.data?.revision ?? 0, list),
    onSuccess: (data) => { client.setQueryData(catalogueKeys.samples, data); setEdited(null); },
    // Someone else saved first: show their list; the error says why.
    onError: () => { setEdited(null); void samples.refetch(); },
  });
  const add = () => {
    if (!text.trim()) return;
    setEdited([...list, { text: text.trim() }]);
    setText("");
  };
  return (
    <section className="grid gap-3" aria-labelledby="samples-title">
      <div className="grid gap-1">
        <h4 className="text-label text-ink-muted m-0" id="samples-title">Sample requirements</h4>
        <p className="text-meta text-ink-muted m-0">
          Shared by the team and checked against every new version before it is published.
        </p>
      </div>
      {samples.error && <ErrorNotice message={errorMessage(samples.error)} />}
      {list.length === 0 ? (
        <p className="text-body text-ink-muted m-0">
          Add requirements you expect this catalogue to map, for example one per product area.
        </p>
      ) : (
        <ol className="m-0 grid gap-2 pl-5">
          {list.map((item, index) => (
            <li key={item.id ?? `new-${index}`} className="text-body text-ink">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <span className="min-w-0 flex-1 break-words" dir="auto">{item.text}</span>
                <Button size="sm" variant="ghost" icon={<Trash2 size={14} aria-hidden="true" />}
                  aria-label={`Remove sample ${index + 1}`}
                  onClick={() => setEdited(list.filter((_, position) => position !== index))}>
                  Remove
                </Button>
              </div>
            </li>
          ))}
        </ol>
      )}
      {list.length < MAX_SAMPLES && (
        <div className="grid gap-2">
          <Textarea label="Add a sample" rows={2} maxLength={MAX_CHARACTERS} value={text} dir="auto"
            placeholder="Example: Partners upload a bulk product catalogue from the B2B portal"
            onChange={(event) => setText(event.target.value)} />
          <Button size="sm" className="w-fit" icon={<Plus size={14} aria-hidden="true" />} onClick={add}
            disabled={!text.trim()}>
            Add sample
          </Button>
        </div>
      )}
      {save.error && <ErrorNotice message={errorMessage(save.error)} />}
      <div className="flex flex-wrap gap-2">
        {edited !== null && (
          <Button onClick={() => save.mutate()} loading={save.isPending} loadingLabel="Saving…">Save samples</Button>
        )}
        <Button variant="primary" icon={<GitCompareArrows size={16} aria-hidden="true" />}
          disabled={list.length === 0 || running} onClick={() => onRun(list)}>
          Compare with the version in use
        </Button>
      </div>
    </section>
  );
}

/**
 * The team's sample requirements mapped by the version in use and by this
 * version, side by side. Samples run one request at a time so each row fills in
 * as soon as a slow model answers, and the run can be stopped.
 */
export function ImpactComparison({ draft }: { draft: KnowledgeRelease }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [running, setRunning] = useState(false);
  const [question, setQuestion] = useState("");
  const stopped = useRef(false);
  useEffect(() => () => { stopped.current = true; }, []);

  const update = (index: number, change: Partial<Row>) =>
    setRows((current) => current.map((row, position) => (position === index ? { ...row, ...change } : row)));

  const run = async (queries: string[]) => {
    stopped.current = false;
    setRunning(true);
    setRows(queries.map((query, index) => ({ key: `${index}-${query}`, query, state: "waiting" })));
    for (const [index, query] of queries.entries()) {
      if (stopped.current) break;
      update(index, { state: "running" });
      try {
        update(index, { state: "done", result: await knowledgeApi.compareImpact(draft.id, query) });
      } catch (error) {
        update(index, { state: "failed", error: errorMessage(error) });
      }
    }
    setRunning(false);
  };

  const done = rows.filter((row) => row.state === "done" || row.state === "failed").length;
  const changed = rows.filter((row) => row.result && outcomeOf(row.result).label !== "Same systems").length;
  return (
    <section className="grid gap-5" aria-labelledby="compare-title">
      <h4 className="text-title text-ink m-0" id="compare-title">Test this version before publishing</h4>
      <Samples running={running} onRun={(items) => void run(items.map((item) => item.text))} />
      <form className="grid gap-2" onSubmit={(event) => {
        event.preventDefault();
        if (question.trim() && !running) void run([question.trim()]);
      }}>
        <Input label="Or try one requirement" value={question} maxLength={MAX_CHARACTERS}
          placeholder="Example: Customers can order fibre from the partner portal"
          onChange={(event) => setQuestion(event.target.value)} />
        <Button type="submit" className="w-fit" disabled={running || !question.trim()}>Compare</Button>
      </form>
      {rows.length > 0 && (
        <div className="grid gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-body text-ink-soft m-0" role="status" aria-live="polite">
              {running
                ? `Comparing ${Math.min(done + 1, rows.length)} of ${rows.length}…`
                : `Compared ${done} of ${rows.length}: ${changed} ${changed === 1 ? "differs" : "differ"} from the version in use.`}
            </p>
            {running && (
              <Button size="sm" variant="ghost" icon={<Square size={14} aria-hidden="true" />}
                onClick={() => { stopped.current = true; }}>
                Stop
              </Button>
            )}
          </div>
          <Table caption="Sample requirements mapped by both versions">
            <TableHead>
              <tr>
                <TableHeaderCell>Requirement</TableHeaderCell>
                <TableHeaderCell>In use</TableHeaderCell>
                <TableHeaderCell>This version</TableHeaderCell>
                <TableHeaderCell>Result</TableHeaderCell>
              </tr>
            </TableHead>
            <TableBody columns={4}>
              {rows.map((row) => {
                const outcome = row.result ? outcomeOf(row.result) : null;
                return (
                  <TableRow key={row.key}>
                    <TableCell><span dir="auto">{row.query}</span></TableCell>
                    <TableCell>{row.result ? <Side impact={row.result.in_use} /> : "—"}</TableCell>
                    <TableCell>{row.result ? <Side impact={row.result.this_version} /> : "—"}</TableCell>
                    <TableCell>
                      {outcome ? (
                        <div className="grid gap-1">
                          <Badge tone={outcome.tone}>{outcome.label}</Badge>
                          {outcome.detail && <span className="text-meta text-ink-soft">{outcome.detail}</span>}
                        </div>
                      ) : row.state === "failed" ? (
                        <div className="grid gap-1">
                          <Badge tone="danger">Could not compare</Badge>
                          <span className="text-meta text-ink-soft">{row.error}</span>
                        </div>
                      ) : (
                        <span className="text-meta text-ink-muted">
                          {row.state === "running" ? "Comparing…" : running ? "Waiting" : "Not compared"}
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  );
}
