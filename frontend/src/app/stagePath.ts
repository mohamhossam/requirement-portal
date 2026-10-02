import type { RequirementWorklistItem } from "../api/client";

export function stagePath(item: Pick<RequirementWorklistItem, "id" | "current_stage">) {
  const root = `/requirements/${item.id}`;
  switch (item.current_stage) {
    case "capture": return `${root}/capture`;
    case "clarify": return `${root}/clarify`;
    case "confirm": return `${root}/confirm`;
    case "knowledge": return `${root}/knowledge`;
    case "epic": return `${root}/breakdown/epic`;
    case "features":
    case "stories":
    case "review": return `${root}/review`;
    case "complete": return `${root}/breakdown`;
  }
  return `${root}/capture`;
}
