/** Whether a source's review date, as the knowledge portal gives it, has passed. */
export function reviewOverdue(dueOn: string | null | undefined, now: Date = new Date()): boolean {
  return Boolean(dueOn) && now.getTime() >= new Date(`${dueOn}T00:00:00Z`).getTime();
}
