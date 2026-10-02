/**
 * A complete requirement, written the way the form asks for one.
 *
 * The intake used to show a title and one sentence, after the form and its save
 * buttons, under the eyebrow "Worked example" — the non-agile business owner
 * met it after writing, or never, and it showed nothing about what an outcome,
 * a channel, a rule or a limit looks like. This is every field, under the
 * form's own labels, in the document serif: something to model from while
 * typing. It sits beside the form at `lg` and inside it, under the business
 * need, below that.
 */
const EXAMPLE: Array<[string, string | string[]]> = [
  ["Requirement title", "High-speed business bundles"],
  [
    "Business need",
    "Small business customers in covered areas should be able to check broadband coverage at their address and order a high-speed bundle on the website, without calling sales.",
  ],
  ["Desired outcome", "Eligible customers check coverage and order online before the Q4 campaign."],
  ["Who is affected", "Existing small business customers with fewer than 50 staff."],
  ["Channels", ["Web", "Assisted sales"]],
  ["Systems involved", ["Order management"]],
  ["Rules that must hold", ["Only addresses in covered areas can order."]],
  ["Deadlines and limits", ["Live before the Q4 campaign starts."]],
];

export function IntakeExample({ headingId }: { headingId?: string }) {
  return (
    <div className="grid gap-4">
      {headingId && (
        <h2 className="text-title text-ink m-0" id={headingId}>
          An example, filled in
        </h2>
      )}
      <dl className="m-0 grid gap-3">
        {EXAMPLE.map(([label, value]) => (
          <div className="grid gap-0.5" key={label}>
            <dt className="text-label text-ink-muted">{label}</dt>
            <dd className="font-serif text-document text-ink m-0">
              {Array.isArray(value) ? (
                <ul className="m-0 grid gap-0.5 pl-5">{value.map((item) => <li key={item}>{item}</li>)}</ul>
              ) : value}
            </dd>
          </div>
        ))}
      </dl>
      <p className="text-meta text-ink-muted m-0 [border-top:1px_solid_var(--line)] pt-3">
        Only the title and the business need are required. After you save, the analysis reads what you wrote, lists what
        it understood, and asks about anything unclear. Nothing is generated until you confirm it.
      </p>
    </div>
  );
}
