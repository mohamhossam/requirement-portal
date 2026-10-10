import { Component, type ErrorInfo, type ReactNode } from "react";

import { reportClientError } from "../../api/clientErrors";
import { Button } from "../ui/Button";
import { isChunkLoadError } from "./chunkLoadError";
import { ErrorState } from "./ErrorState";

type Props = {
  children: ReactNode;
  /**
   * `page` stands in for the whole app, before the shell exists; `route` stands
   * in for one page inside the shell, whose header and navigation still work.
   */
  scope: "page" | "route";
  /** A change here (the route's path) clears a crash, so navigating away recovers. */
  resetKey?: string;
};

type State = { error: unknown };

/**
 * A render that threw, and the way out of it, instead of a blank window.
 *
 * Built on `ErrorState`, so a crash reads like any other failed load and always
 * offers a next step. A missing chunk can only be fixed by loading the new
 * release, so it offers a reload; anything else can be tried again in place.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: unknown): State {
    return { error };
  }

  componentDidUpdate(previous: Props) {
    if (this.state.error !== null && previous.resetKey !== this.props.resetKey) {
      this.setState({ error: null });
    }
  }

  componentDidCatch(error: unknown, info: ErrorInfo) {
    console.error("The page failed to render.", error, info.componentStack);
    reportClientError(isChunkLoadError(error) ? "chunk_load" : "render");
  }

  render() {
    const { error } = this.state;
    if (error === null) return this.props.children;
    const reload = (
      <Button variant={isChunkLoadError(error) ? "secondary" : "ghost"} onClick={() => window.location.reload()}>
        Reload the page
      </Button>
    );
    const content = isChunkLoadError(error) ? (
      <ErrorState
        title="A new version is available"
        message="This page was updated since you opened it. Reload to continue; anything you saved is kept."
        action={reload}
        headingLevel={this.props.scope === "page" ? "h1" : "h2"}
      />
    ) : (
      <ErrorState
        title="This page stopped working"
        message="Something went wrong while showing it. Try again, or reload the page if it keeps happening."
        onRetry={() => this.setState({ error: null })}
        action={reload}
        headingLevel={this.props.scope === "page" ? "h1" : "h2"}
      />
    );
    if (this.props.scope === "route") return <div className="p-4 md:p-6">{content}</div>;
    return <main className="grid min-h-dvh place-content-center p-6">{content}</main>;
  }
}
