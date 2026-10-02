import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { architectureFixture } from "../../test/fixtures";
import { renderWithKnowledge as render } from "../../test/renderWithKnowledge";
import { ArchitectureImpactPanel } from "./ArchitectureImpactPanel";

describe("ArchitectureImpactPanel", () => {
  it("shows the exact quote beside the system it supports", () => {
    render(<ArchitectureImpactPanel impact={{ ...architectureFixture,
      citation_ids: ["source"], citations: [{ system_id: "bcrm",
        chunk_id: "source", quote: "Exact source-language quotation" }] }} />);
    expect(screen.getByText("Exact source-language quotation")).toBeVisible();
    expect(screen.getByRole("link", { name: "View supporting evidence" }))
      .toHaveAttribute("href", expect.stringContaining("/evidence/source"));
  });
  it("distinguishes not mapped from a completed empty mapping", () => {
    const { rerender } = render(<ArchitectureImpactPanel impact={null} />);
    expect(screen.getByText("Architecture not mapped")).toBeVisible();

    rerender(
      <ArchitectureImpactPanel
        impact={{ ...architectureFixture, systems: [], dependencies: [], cross_system: false }}
      />,
    );
    expect(screen.getByText("No likely systems identified.")).toBeVisible();
  });

  it("shows systems, capabilities, ownership, dependencies and the warning", () => {
    render(<ArchitectureImpactPanel impact={architectureFixture} />);

    expect(screen.getByText("Crosses systems")).toBeVisible();
    expect(screen.getAllByText("BCRM")[0]).toBeVisible();
    expect(screen.getByText("Assisted sales")).toBeVisible();
    expect(screen.getByText("Not in the catalogue")).toBeVisible();
    expect(screen.getAllByText("not assigned")).toHaveLength(2);
    expect(screen.queryByText("Value stream")).not.toBeInTheDocument();
    expect(screen.getByText(/assisted journey hands off/)).toBeVisible();
    expect(screen.getByText("(API call)")).toBeVisible();
  });

  it("names the squads, value stream and products that own a system", () => {
    const [bcrm, ...rest] = architectureFixture.systems;
    if (!bcrm) throw new Error("The fixture maps BCRM.");
    render(
      <ArchitectureImpactPanel
        impact={{
          ...architectureFixture,
          systems: [{
            ...bcrm,
            squads: [{ id: "sales", name: "Sales squad" }, { id: "care", name: "Care squad" }],
            value_streams: [{ id: "retail", name: "Retail" }],
            products: [{ id: "ordering", name: "Ordering" }],
          }, ...rest],
        }}
      />,
    );
    expect(screen.getByText("Sales squad, Care squad")).toBeVisible();
    expect(screen.getByText("Retail")).toBeVisible();
    expect(screen.getByText("Ordering")).toBeVisible();
  });

  it("keeps the Story variant compact without hiding the mapped systems", () => {
    render(<ArchitectureImpactPanel impact={architectureFixture} compact />);
    expect(screen.getByRole("region", { name: "Architecture impact" })).toHaveAttribute("data-compact", "true");
    expect(screen.queryByText("Crosses systems")).not.toBeInTheDocument();
    expect(screen.getAllByText("BCRM")[0]).toBeVisible();
  });

  it("lists connected systems to check, apart from the mapped ones", () => {
    render(
      <ArchitectureImpactPanel
        impact={{
          ...architectureFixture,
          adjacent_systems: [{
            id: "cbcm-crmgw", name: "CBCM / CRMGW", catalogued: true, capabilities: [],
            constraints: [], squads: [{ id: "care", name: "Care squad" }], value_streams: [], products: [],
          }],
          adjacent_dependencies: [{
            source_system_id: "bcrm", target_system_id: "cbcm-crmgw",
            description: "Reads customer eligibility.", kind: "transfers_data_to",
          }],
          adjacent_omitted: 2,
        }}
      />,
    );

    const connected = screen.getByRole("group", { name: "Connected systems to check" });
    expect(connected).toHaveTextContent("CBCM / CRMGW");
    expect(connected).toHaveTextContent("Squads: Care squad");
    expect(connected).toHaveTextContent("Linked to BCRM (1 system)");
    expect(connected).toHaveTextContent("Used by BCRM: Reads customer eligibility. (Data transfer)");
    expect(connected).toHaveTextContent("2 more connected systems are in the architecture catalogue.");
    expect(screen.getByRole("link", { name: "architecture catalogue" })).toHaveAttribute("href", "/architecture-knowledge");
    expect(screen.getAllByRole("listitem").filter((item) => item.textContent?.startsWith("CBCM"))).toHaveLength(1);
  });

  it("names connected systems in one line on a Story", () => {
    render(
      <ArchitectureImpactPanel
        compact
        impact={{
          ...architectureFixture,
          adjacent_systems: [{
            id: "rtf", name: "RTF", catalogued: true, capabilities: [], constraints: [],
            squads: [], value_streams: [], products: [],
          }],
          adjacent_dependencies: [{ source_system_id: "bcrm", target_system_id: "rtf", description: "Orders.", kind: "unspecified" }],
          adjacent_omitted: 1,
        }}
      />,
    );
    expect(screen.getByRole("group", { name: "Connected systems to check" })).toHaveTextContent("Not mapped: RTF; and 1 more");
  });

  it("shows nothing about connected systems when there are none", () => {
    render(<ArchitectureImpactPanel impact={architectureFixture} />);
    expect(screen.queryByRole("group", { name: "Connected systems to check" })).not.toBeInTheDocument();
  });

  it("says which way a connected system depends and shows its capability, not empty squads", () => {
    render(
      <ArchitectureImpactPanel
        impact={{
          ...architectureFixture,
          adjacent_systems: [{
            id: "portal", name: "Portal", catalogued: true, capabilities: [{ id: "ordering", name: "Ordering" }],
            constraints: [], squads: [], value_streams: [], products: [],
          }],
          adjacent_dependencies: [{ source_system_id: "portal", target_system_id: "bcrm", description: "Sends quotes.", kind: "unspecified" }],
          adjacent_omitted: 0,
        }}
      />,
    );
    const connected = screen.getByRole("group", { name: "Connected systems to check" });
    expect(connected).toHaveTextContent("Uses BCRM: Sends quotes.");
    expect(connected).not.toHaveTextContent(/\((API call|Events|Data transfer|Orchestration)\)/);
    expect(connected).toHaveTextContent("Ordering");
    expect(connected).not.toHaveTextContent("Squads:");
    expect(connected).toHaveTextContent("The squad catalogue assigns no squads to these systems.");
  });

  it("names each capability's domain and the business areas the item touches", () => {
    const [bcrm, ...rest] = architectureFixture.systems;
    if (!bcrm) throw new Error("The fixture maps BCRM.");
    render(
      <ArchitectureImpactPanel
        impact={{
          ...architectureFixture,
          systems: [{ ...bcrm, capabilities: [{ id: "assisted-sales", name: "Assisted sales",
            domain_id: "quotes", domain_path: ["Order capture", "Quoting"] }] }, ...rest],
        }}
      />,
    );
    expect(screen.getByText("Matched business areas:")).toHaveTextContent("Matched business areas: Order capture");
    expect(screen.getByRole("list", { name: "Matched capabilities for BCRM" })).toHaveTextContent(
      "Order capture › Quoting: Assisted sales");
  });

  it("names the component that delivers each matched capability", () => {
    const [bcrm, ...rest] = architectureFixture.systems;
    if (!bcrm) throw new Error("The fixture maps BCRM.");
    render(
      <ArchitectureImpactPanel
        impact={{
          ...architectureFixture,
          systems: [{ ...bcrm, capabilities: [
            { id: "assisted-sales", name: "Assisted sales", domain_id: "quotes", domain_path: ["Order capture"],
              component_id: "quote-engine", component_name: "Quote engine" },
            { id: "ordering", name: "Ordering", domain_path: [] },
          ] }, ...rest],
        }}
      />,
    );
    const matched = screen.getByRole("list", { name: "Matched capabilities for BCRM" });
    expect(matched).toHaveTextContent("Order capture: Assisted sales · Quote engine");
    expect(screen.getByText("Ordering")).toHaveTextContent(/^Ordering$/);
  });

  it("offers the closest capability domains, as a suggestion, when nothing was mapped", () => {
    render(
      <ArchitectureImpactPanel
        impact={{
          ...architectureFixture, systems: [], dependencies: [], cross_system: false,
          suggested_domains: [{ domain_id: "billing", path: ["Billing"], system_ids: ["bscs"],
            system_names: ["BSCS"], matched_terms: ["billing"] }],
        }}
      />,
    );
    const card = screen.getByRole("group", { name: "Closest business areas" });
    expect(card).toHaveTextContent("No system mapped.");
    expect(card).toHaveTextContent("A suggestion, not a mapping");
    expect(card).toHaveTextContent("Its systems, not mapped: BSCS");
    expect(card).toHaveTextContent("Words in common: “billing”");
    expect(screen.queryByText("No likely systems identified.")).not.toBeInTheDocument();
  });

  const advised = {
    ...architectureFixture,
    product_contexts: [{
      product_id: "business-pro-plus", product_name: "Business Pro Plus", order_type: "New Activation",
      matched_terms: ["Business Pro Plus", "Static IP"],
      responsibilities: [
        { component_id: "static-ip", component_name: "Static IP", system_id: "bcrm", system_name: "BCRM",
          role: "CUSTOMER_CONTEXT", description: "Supplies the account." },
        { component_id: "static-ip", component_name: "Static IP", system_id: "rtf", system_name: "RTF",
          role: "VALIDATION", description: "Checks the address." },
      ],
    }],
    journey_steps: [{
      system_id: "bcrm", journey_id: "bpp-new-activation", journey_name: "New Activation", number: "10",
      name: "Select offer", performs: false, fulfils: ["Business Pro Plus", "New Activation"],
      before: [{ number: "75", name: "Correct order", system_id: "b2b-web", system_name: "B2B Web" }],
      after: [{ number: "20", name: "Resolve offer", system_id: "bcc", system_name: "Digital Catalog" },
        { number: "30", name: "Check eligibility" }],
    }],
  };

  it("notes the product offering the item names and who delivers it, apart from the mapping", () => {
    render(<ArchitectureImpactPanel impact={advised} />);

    const offering = screen.getByRole("group", { name: "Product offering named" });
    expect(offering).toHaveTextContent("A note, not a mapping");
    expect(offering).toHaveTextContent("Business Pro Plus › New Activation");
    expect(offering).toHaveTextContent("Words in common: “Business Pro Plus”, “Static IP”");
    expect(offering).toHaveTextContent("BCRM · Customer context: Supplies the account.");
    expect(offering).toHaveTextContent("RTF · Validation: Checks the address.");
    const journey = screen.getByRole("group", { name: "Journey steps to check" });
    expect(journey).toHaveTextContent("10. Select offer");
    expect(journey).toHaveTextContent("Supports · Business Pro Plus › New Activation");
    expect(journey).toHaveTextContent("After 75. Correct order (B2B Web)");
    expect(journey).toHaveTextContent("Then 20. Resolve offer (Digital Catalog); 30. Check eligibility");
  });

  it("keeps the product and journey notes to one line each when compact", () => {
    render(<ArchitectureImpactPanel impact={advised} compact />);

    expect(screen.getByRole("group", { name: "Product offering named" })).toHaveTextContent("BCRM, RTF");
    expect(screen.queryByText(/Words in common/)).not.toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Journey steps to check" }))
      .toHaveTextContent("BCRM: 10. Select offer");
  });
});
