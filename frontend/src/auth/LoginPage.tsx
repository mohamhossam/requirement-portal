import { Check, FileText, FlaskConical, KeyRound, ShieldCheck } from "lucide-react";
import { useMemo } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Select";
import { useAuth } from "./authContext";
import { safeAuthReturnPath } from "./returnPath";

const JOURNEY = ["Requirement", "Epic", "Feature", "Story"];

/**
 * The way in (docs/ux-plan.md §3.10, Phase 0 step 6).
 *
 * It used to be a fourth visual generation — a navy-to-teal gradient with a
 * teal glow, 0.82rem radii and buttons that lifted on hover — so the first
 * screen anyone saw looked like a different product from every screen after
 * it. Now it is the same Working Paper as the rest: Paper canvas, one bordered
 * surface, Signal Indigo as the only accent, and the primitives every other
 * screen uses, so the sign-in button is the same button as the Save button.
 *
 * The left column is the product's promise, set the way the product sets a
 * requirement: the statement in the interface face, the explanation in the
 * document serif. The journey is drawn as a vertical rail because that is what
 * the stage rail looks like once you are in.
 */
export function LoginPage() {
  const auth = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const returnPath = useMemo(() => {
    const requested = new URLSearchParams(location.search).get("returnTo");
    return safeAuthReturnPath(requested);
  }, [location.search]);

  if (!auth) return null;
  const fakeMode = auth.config?.mode === "fake";

  return (
    <main className="bg-canvas text-ink grid min-h-dvh place-items-center px-4 py-10 md:px-10 md:py-16">
      <div className="grid w-full max-w-[64rem] gap-10 md:grid-cols-[minmax(0,1fr)_minmax(20rem,26rem)] md:items-center md:gap-16">
        <section aria-labelledby="login-story-heading" className="grid content-start gap-8">
          <div className="flex items-center gap-3">
            <span className="bg-accent text-on-accent grid size-9 shrink-0 place-items-center rounded-sm">
              <FileText size={18} aria-hidden="true" />
            </span>
            <span className="grid">
              <strong className="text-title">Requirement AI</strong>
              <span className="text-meta text-ink-muted">Telecom SMB planning workspace</span>
            </span>
          </div>

          <div className="grid max-w-[34rem] gap-4">
            <h1 id="login-story-heading" className="text-display m-0 [text-wrap:balance]">
              Turn business needs into review-ready backlogs.
            </h1>
            <p className="font-document text-document-lead text-ink-soft m-0">
              Capture the requirement, clarify uncertainty, and guide every item through human review.
            </p>
          </div>

          {/* Hidden below `md`, where the sign-in panel has to arrive before the
              reader runs out of first screen. The promise above says the same
              thing in one sentence. */}
          <ol aria-label="Requirement breakdown journey" className="relative m-0 grid list-none gap-1 p-0 max-md:hidden">
            {/* The rail's spine, behind the step numbers: centred on a 28px
                circle, and stopping at the first and last centres so it reads
                as joining steps rather than running off the page. */}
            <span aria-hidden="true" className="bg-line-strong absolute top-5 bottom-5 left-[13.5px] w-px" />
            {JOURNEY.map((label, index) => (
              <li key={label} className="relative flex items-center gap-3 py-1.5">
                <span className="border-line-strong bg-surface text-meta text-ink-soft grid size-7 shrink-0 place-items-center rounded-full border border-solid font-semibold tabular-nums">
                  {index + 1}
                </span>
                <strong className="text-body font-semibold">{label}</strong>
              </li>
            ))}
          </ol>

          <p className="text-meta text-ink-muted m-0 flex items-center gap-2 max-md:hidden">
            <ShieldCheck size={16} aria-hidden="true" /> Secure, attributable human review
          </p>
        </section>

        <section
          aria-labelledby="login-heading"
          className="border-line bg-surface grid gap-6 rounded-md border border-solid p-6 md:p-8"
        >
          <div className="grid gap-2">
            <h2 id="login-heading" className="text-headline m-0">Welcome back</h2>
            <p className="text-body text-ink-muted m-0">
              Sign in with your company account or your administrator-provided credentials.
            </p>
          </div>

          {auth.error && (
            <div
              className="border-line bg-danger-wash grid gap-1 rounded-sm border border-solid border-l-[3px] border-l-[var(--danger)] px-3 py-2"
              role="alert"
            >
              <strong className="text-danger text-body">
                {auth.sessionExpired ? "Your session ended" : "We couldn’t sign you in"}
              </strong>
              <p className="text-ink-soft text-body m-0">{auth.error}</p>
            </div>
          )}

          {fakeMode ? (
            <div className="grid gap-4">
              <div className="grid justify-items-start gap-2">
                <Badge icon={<FlaskConical size={12} aria-hidden="true" />}>Development mode</Badge>
                <p className="text-body text-ink-muted m-0">
                  Choose a local test persona. No external account is required.
                </p>
              </div>
              <Select
                label="Test persona"
                value={auth.actor?.id ?? ""}
                disabled={auth.reconciling}
                onChange={(event) => {
                  void auth.switchFakeActor(event.target.value).catch(() => undefined);
                }}
              >
                {auth.config?.fake_actors.map((actor) => (
                  <option key={actor.id} value={actor.id}>{actor.display_name}</option>
                ))}
              </Select>
              <Button
                variant="primary"
                className="w-full"
                icon={<Check size={16} aria-hidden="true" />}
                disabled={!auth.actor}
                loading={auth.reconciling}
                onClick={() => navigate(returnPath, { replace: true })}
              >
                Continue to workspace
              </Button>
            </div>
          ) : auth.config ? (
            <div className="grid gap-3">
              {auth.config.login_choices.map((choice) => {
                const busy = auth.signingInChoice === choice.id;
                return (
                  <Button
                    key={choice.id}
                    className="w-full"
                    icon={choice.id === "microsoft" ? <MicrosoftMark /> : <KeyRound size={16} aria-hidden="true" />}
                    disabled={auth.signingInChoice !== null}
                    loading={busy}
                    loadingLabel="Opening secure sign-in…"
                    onClick={() => void auth.signIn(choice.id)}
                  >
                    {choice.label}
                  </Button>
                );
              })}
            </div>
          ) : (
            <Button className="w-full" onClick={() => window.location.reload()}>
              Try loading sign-in again
            </Button>
          )}

          <div className="border-line grid gap-2 border-0 border-t border-solid pt-4">
            <p className="text-body text-ink-soft m-0">
              Need access? Ask your workspace administrator to create an account.
            </p>
            <p className="text-meta text-ink-muted m-0">
              By continuing, you agree to use this workspace for authorized business activity.
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}

/** Microsoft's four-square mark, in its own fixed colours (tokens.css, third-party marks). */
function MicrosoftMark() {
  return (
    <span aria-hidden="true" className="grid size-4 shrink-0 grid-cols-2 gap-[2px]">
      <i className="bg-[var(--mark-microsoft-red)]" />
      <i className="bg-[var(--mark-microsoft-green)]" />
      <i className="bg-[var(--mark-microsoft-blue)]" />
      <i className="bg-[var(--mark-microsoft-yellow)]" />
    </span>
  );
}
