/**
 * The shared primitives, built to docs/design-system.md §11 and to WCAG 2.2 AA
 * *at the primitive*, so that no screen has to remember (`ux-plan.md` §5,
 * Phase 0, item 4).
 *
 * Modal, Toaster and StatusBadge stay at `src/components/` and are re-exported
 * here: about twenty files import them by path already, and moving them would
 * break screens this pass is not allowed to touch. The same primitive, one
 * import away, either way.
 *
 * What is NOT here: `.button`, `.field`, `.status` and the rest of the legacy
 * class names. Six stylesheets redeclare `.button` alone and override each
 * other by source order, so a primitive wearing one of those classes would
 * render differently depending on which subtree it landed in. These emit their
 * own utilities and are immune to it.
 */
export { Badge, Pill, type BadgeTone } from "./Badge";
export { Button, ButtonLink, type ButtonProps, type ButtonLinkProps, type ButtonSize, type ButtonVariant } from "./Button";
export { Card, CardBody, CardFooter, CardHeader, type CardProps, type CardTone } from "./Card";
export { Checkbox, type CheckboxProps } from "./Checkbox";
export { describedBy } from "./describedBy";
export { FieldError, FieldShell } from "./Field";
export { Input, Textarea, type InputProps, type TextareaProps } from "./Input";
export { Select, type SelectProps } from "./Select";
export {
  Table,
  TableBody,
  TableBulkBar,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  type SortDirection,
  type TableHeaderCellProps,
} from "./Table";
export { Tab, TabList, TabPanel, Tabs } from "./Tabs";
export { TagInput, type TagInputProps } from "./TagInput";
export { withDraft } from "./tagList";
export { cx } from "./cx";

export { Modal, ModalBody, ModalFooter, ModalHeader, type ModalVariant } from "../Modal";
export { StatusBadge } from "../StatusBadge";
export { Toaster } from "../Toaster";
export { useToast, type ToastApi, type ToastInput, type ToastTone } from "../useToast";
