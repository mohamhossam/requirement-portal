import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import type { RequirementAnalysis } from "../../api/client";
import { AnalysisSourcesProvider, SourceLinks } from "./AnalysisSources";

const evidence = { document_id: "document-1", version_id: "version-1", checksum_sha256: "abc123", block_id: "table-4-row-7", label: "Voice plans → Table 4, row 7" };
const answer: RequirementAnalysis["clarifications"][number] = { question_id: "question-1", kind: "open_question", subject: "Who uses DEL?", answer: "DEL is a single-user line plan.", answered_by: { id: "owner-1", display_name: "Amina Owner", email: null }, answered_at: "2026-09-18T10:00:00Z", source_suggestion_id: null };

function show(references = [evidence], answers = [answer]) {
  return render(<MemoryRouter><AnalysisSourcesProvider documents={[{ ...evidence, filename: "Voice requirement.docx" }]}>
    <SourceLinks subject="DEL is a single-user line plan." evidence={references} humanAnswers={answers} />
    <SourceLinks subject="PABX supports multiple users." humanAnswers={[{ ...answer, question_id: "question-2", subject: "Who uses PABX?", answer: "PABX is a multi-user line plan." }]} />
  </AnalysisSourcesProvider></MemoryRouter>);
}

it("keeps references quiet until opened, groups documents and preserves attribution", async () => {
  show([evidence, evidence, { ...evidence, block_id: "row-8", label: "Voice plans → Table 4, row 8" }], [answer, answer, { ...answer, question_id: "another-question", subject: "What does DEL mean?" }]);
  const trigger = screen.getByRole("button", { name: "Where this came from: DEL is a single-user line plan." });
  expect(trigger).toHaveTextContent("2 document references · 2 human answers");
  expect(screen.queryByText(evidence.label)).not.toBeInTheDocument();
  expect(screen.queryByText("Amina Owner")).not.toBeInTheDocument();
  await userEvent.click(trigger);
  const dialog = screen.getByRole("dialog", { name: "Where this came from" });
  expect(within(dialog).getAllByText("Voice requirement.docx")).toHaveLength(1);
  expect(within(dialog).getAllByText(/Amina Owner/)).toHaveLength(2);
  expect(within(dialog).getByText("What does DEL mean?")).toBeInTheDocument();
  expect(within(dialog).getAllByRole("link", { name: /Open this passage/ })[0]).toHaveAttribute("href", "/documents/document-1#block-table-4-row-7");
  expect(within(dialog).getByText("Exact reference").closest("details")).not.toHaveAttribute("open");
  await userEvent.click(within(dialog).getByRole("button", { name: "Close" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});

it("preserves different versions and answers by the same person and handles legacy metadata", async () => {
  show([evidence, { ...evidence, version_id: "older-version" }], [answer, { ...answer, answer: "An updated answer.", answered_at: null, answered_by: null }]);
  await userEvent.click(screen.getByRole("button", { name: /Where this came from: DEL/ }));
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByText("Voice requirement.docx")).toBeInTheDocument();
  expect(within(dialog).getByText("A source document")).toBeInTheDocument();
  expect(within(dialog).getByText("older-version")).toBeInTheDocument();
  expect(within(dialog).getByText("The answering person is not on record")).toBeInTheDocument();
  fireEvent(dialog, new Event("cancel", { bubbles: true, cancelable: true }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Where this came from: PABX/ }));
  expect(screen.getByText("Who uses PABX?")).toBeInTheDocument();
  expect(screen.queryByText("Who uses DEL?")).not.toBeInTheDocument();
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});

it("does not offer sources for unsupported content and closes when the analysis scope changes", async () => {
  const { rerender } = show();
  await userEvent.click(screen.getByRole("button", { name: /Where this came from: DEL/ }));
  rerender(<AnalysisSourcesProvider key="new-requirement" documents={[]}><SourceLinks subject="No evidence" /></AnalysisSourcesProvider>);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});
