---
target: Source step (/capture), Phase 5 baseline
total_score: 16
max_score: 40
na_heuristics: 
p0_count: 2
p1_count: 1
target_identity: "file:C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\app\\requirement\\CaptureView.tsx"
target_fingerprint: "sha256:7dcd613d277da7d74a015f54a53e4671e8475ad5874a6518fda6ecb1a52a0788"
target_path: "C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\app\\requirement\\CaptureView.tsx"
timestamp: 2026-09-26T10-28-22Z
slug: frontend-src-app-requirement-captureview-tsx
---
Method: dual-agent (A: design review · B: detector + browser evidence). Live seeded Source: 42a131e6 with activation-rules.txt (ready) and a corrupt pricing-sheet.pdf (failed ingestion); Source document drawer. 1440 light/dark, 390.

## Design Health Score
| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of System Status | 1 | "Ready for analysis" beside a disabled Continue; blocking file never named |
| 2 | Match System / Real World | 1 | Capture vs Source; "Prompt attachments", "Exclude from prompt"; raw stage and readiness |
| 3 | User Control and Freedom | 2 | Trash removes in one click |
| 4 | Consistency and Standards | 1 | Legacy styling; every small meta text in danger red; indigo spent six times |
| 5 | Error Prevention | 1 | aria-disabled Continue link still navigates on Enter |
| 6 | Recognition Rather Than Recall | 2 | The source itself is not on the Source screen |
| 7 | Flexibility and Efficiency | 2 | Drop zone + button; labels repeat filenames |
| 8 | Aesthetic and Minimalist Design | 2 | 11 formats before the files; row actions overprint text at 390 |
| 9 | Error Recovery | 2 | Failure is 10.9px red with an indigo upload glyph; consequences unexplained |
| 10 | Help and Documentation | 2 | Nothing explains why analysis is blocked |
| **Total** | | **16/40** | **Poor** |

## Design Specificity Verdict
Generic and dishonest: the readiness card contradicts the gate. Detector CLI clean; browser: side-tab (journey-panel-heading, eligibility-card), line-length ~136ch, 4.4:1 on the disabled link (exempt). Measured: text at 10.88–11.2px in document rows; evidence counts coloured danger; hidden file inputs likely extra tab stops; drawer header overlaps the "Original requirement" h2.

## Priority Issues
- [P0] Row actions overprint file text at 390 (grid + min-width). Fix: actions to a second row below sm.
- [P0/P1] Readiness contradicts the gate, and the gate leaks to the keyboard. Fix: one honest verdict with glyph; a real gated control with a reason.
- [P1] Copy and type floor fail the business owner. Fix: label map for stage/readiness; "Leave out of analysis"; counts neutral and non-zero only; 12px floor.
- [P2] The source is not on the Source screen; the drawer is thin and double-titled. Fix: business need in serif at the top of /capture.
- [P2] Remove needs confirmation; indigo overspent.

## Persona Red Flags
Business owner: prompt jargon, false "ready". Keyboard/SR: Continue announced disabled but activates; hidden inputs. BA: repeated filename labels.

## Minor Observations
Failed row uses an indigo upload glyph; disabled icon-button at .45 opacity; "0 sections · 0 tables · 0 images" for a TXT.

## Questions to Consider
Once intake owns attachments, what does /capture do that a readiness line and the drawer cannot?
