import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../api/client";
import { errorMessage } from "../../api/errors";
import { queryKeys } from "../../app/queryKeys";
import { Button } from "../../components/ui/Button";

export function NotificationCenter() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const seen = useRef(new Set<string>());
  const browserNotificationsAvailable = typeof Notification !== "undefined";
  const notifications = useQuery({
    queryKey: queryKeys.notifications(),
    queryFn: () => api.listNotifications(true),
    refetchInterval: 10_000,
  });
  const preference = useQuery({
    queryKey: queryKeys.notificationPreference(),
    queryFn: api.getNotificationPreference,
  });
  const markRead = useMutation({
    mutationFn: (notificationId: string) => api.markNotificationRead(notificationId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.notifications() });
    },
  });
  const setPreference = useMutation({
    mutationFn: (browserEnabled: boolean) => api.setNotificationPreference(browserEnabled),
    onSuccess: (value) => queryClient.setQueryData(queryKeys.notificationPreference(), value),
  });
  const browserAlertsEnabled =
    browserNotificationsAvailable &&
    preference.data?.browser_enabled === true &&
    Notification.permission === "granted";

  useEffect(() => {
    if (
      !browserNotificationsAvailable ||
      !preference.data?.browser_enabled ||
      Notification.permission !== "granted"
    ) return;
    for (const item of notifications.data ?? []) {
      if (seen.current.has(item.id)) continue;
      seen.current.add(item.id);
      new Notification(item.kind === "ai_job_succeeded" ? "AI work completed" : "AI work failed", {
        body: item.message,
      });
    }
  }, [browserNotificationsAvailable, notifications.data, preference.data?.browser_enabled]);

  const toggleBrowser = async () => {
    const next = !browserAlertsEnabled;
    if (next && !browserNotificationsAvailable) return;
    if (next && Notification.permission !== "granted") {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") return;
    }
    setPreference.mutate(next);
  };

  const unread = notifications.data ?? [];
  return (
    <div className="relative">
      <Button
        aria-expanded={open}
        aria-label={`Notifications${unread.length ? ` (${unread.length} unread)` : ""}`}
        className="relative"
        onClick={() => setOpen((value) => !value)}
        size="icon"
        type="button"
        variant="ghost"
      >
        <Bell aria-hidden="true" size={18} />
        {unread.length > 0 && (
          <span
            aria-hidden="true"
            className="bg-accent text-on-accent text-label absolute -top-1 -right-1 grid min-h-[1.1rem] min-w-[1.1rem] place-items-center rounded-full px-1 tabular-nums"
          >
            {unread.length}
          </span>
        )}
      </Button>
      {open && (
        <div className="border-line bg-surface-raised shadow-elev-2 absolute top-full right-0 z-[var(--z-top)] mt-2 grid w-[min(25rem,calc(100vw-2rem))] gap-1 rounded-lg border border-solid p-4">
          <div className="border-line flex items-center justify-between gap-4 border-0 border-b border-solid pb-3">
            <h2 className="text-title text-ink m-0">Notifications</h2>
            <Button
              disabled={!browserNotificationsAvailable || preference.isPending || setPreference.isPending}
              onClick={() => void toggleBrowser()}
              variant="text"
            >
              {!browserNotificationsAvailable ? "Browser alerts unavailable" : browserAlertsEnabled ? "Browser alerts on" : "Enable browser alerts"}
            </Button>
          </div>
          {unread.length === 0 ? (
            <p className="text-body text-ink-muted m-0 py-3">No unread notifications.</p>
          ) : (
            <ul className="m-0 grid list-none p-0">
              {unread.map((item, index) => (
                <li
                  className={`flex items-start justify-between gap-4 py-3 ${index > 0 ? "[border-top:1px_solid_var(--line)]" : ""}`}
                  key={item.id}
                >
                  {item.resource_path ? (
                    <Link
                      className="text-accent text-body min-h-6 [overflow-wrap:anywhere] hover:underline"
                      onClick={() => {
                        markRead.mutate(item.id);
                        setOpen(false);
                      }}
                      to={item.resource_path}
                    >
                      {item.message}
                    </Link>
                  ) : (
                    <span className="text-body text-ink [overflow-wrap:anywhere]">{item.message}</span>
                  )}
                  <Button className="shrink-0" onClick={() => markRead.mutate(item.id)} variant="text">
                    Mark read
                  </Button>
                </li>
              ))}
            </ul>
          )}
          {(notifications.error || preference.error || setPreference.error) && (
            <p className="text-danger text-meta m-0 font-semibold" role="alert">
              {errorMessage(notifications.error ?? preference.error ?? setPreference.error)}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
