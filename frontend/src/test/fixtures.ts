import type {
  ArchitectureImpact,
  Epic,
  Feature,
  FeatureSet,
  RequirementAnalysis,
  Story,
  StoryProposal,
  StorySet,
  StoryQuality,
} from "../api/client";

const allowedAction = { allowed: true, reason: null, confirmation: null };

const generatedFeatureActions = {
  approve: allowedAction,
  generate_stories: {
    allowed: false,
    reason: "Approve the Feature before generating or changing its Stories.",
    confirmation: null,
  },
};

const approvedFeatureActions = {
  approve: {
    allowed: false,
    reason: "This Feature version is already approved. Edit or regenerate it before approving again.",
    confirmation: null,
  },
  generate_stories: allowedAction,
};

const generatedStoryActions = { approve: allowedAction, regenerate: allowedAction };

export const architectureFixture: ArchitectureImpact = {
  knowledge_version: "smb-source-reference-v1",
  mapped_at: "2026-09-03T12:00:00Z",
  cross_system: true,
  citation_ids: [],
  uncertainty: null,
  evidence_classification: "legacy_deterministic",
  adjacent_omitted: 0,
  systems: [
    {
      id: "bcrm",
      name: "BCRM",
      catalogued: true,
      capabilities: [{ id: "assisted-sales", name: "Assisted sales" }],
      constraints: [],
      squads: [],
      value_streams: [],
      products: [],
    },
    {
      id: "declared-cpp",
      name: "CPP",
      catalogued: false,
      capabilities: [],
      constraints: [],
      squads: [],
      value_streams: [],
      products: [],
    },
  ],
  dependencies: [
    {
      source_system_id: "bcrm",
      target_system_id: "declared-cpp",
      description: "The assisted journey hands off to the declared channel.",
      kind: "calls_api",
    },
  ],
};

export const analysisFixture: RequirementAnalysis = {
  stale_reference_proposal_ids: [],
  overdue_reference_reviews: {},
  clarification_evidence: [],
  requirement_id: "requirement-1",
  version: 1,
  analysis_id: null,
  round_number: null,
  provenance: null,
  source_requirement_version: null,
  questions: [],
  question_changes: [],
  document_references: [],
  known_facts: [{ statement: "Business broadband is in scope.", evidence_references: [] }],
  constraints: [{ statement: "Only XGPON coverage areas qualify.", evidence_references: [] }],
  business_rules: [{ statement: "Eligibility must be checked before ordering.", evidence_references: [] }],
  assumptions: [{ statement: "Existing coverage data is current.", evidence_references: [] }],
  open_questions: [{ question: "Who owns fallout?", rationale: "Ownership is not stated.", evidence_references: [] }],
  ambiguities: [{ statement: "Available in channel", reason: "No release date is stated.", evidence_references: [] }],
  potential_dependencies: [{ statement: "GIS coverage service", evidence_references: [] }],
  clarifications: [],
  human_confirmed: false,
  confirmed_at: null,
  confirmed_by: null,
  actions: {
    generate_epic: {
      allowed: false,
      reason: "The analysis must be human-confirmed before an Epic can be generated.",
      confirmation: null,
    },
  },
  business_intent: {
    desired_outcome: {
      statement: "Eligible SMB customers can order high-speed bundles.",
      origin: "source",
      proposal_id: null,
    },
    accepted_business_rules: [],
    accepted_constraints: [],
    proposals: [],
  },
  stage_provenance: [],
};

export const epicFixture: Epic = {
  id: "epic-1",
  version: 1,
  requirement_id: "requirement-1",
  name: "XGPON business bundles",
  outcome: "Eligible SMB customers can order high-speed bundles.",
  business_case: "Capture demand for premium connectivity.",
  status: "generated",
  provenance: {
    generated_at: "2026-01-01T12:00:00Z",
    model: "fake",
    prompt_version: "fake-epic-v1",
  },
  stale: null,
  content_fingerprint: "epic-fingerprint",
  current_approval: null,
  approval_history: [],
  actions: {
    approve: allowedAction,
    regenerate: allowedAction,
    generate_features: {
      allowed: false,
      reason: "Approve the Epic before decomposing it into Features.",
      confirmation: null,
    },
  },
};

export const featureSetFixture: FeatureSet = {
  epic_id: "epic-1",
  set_version: 1,
  generation_context_token: "generation-context-v2:features",
  features: [
    {
      id: "feature-1",
      version: 1,
      epic_id: "epic-1",
      name: "Digital ordering",
      outcome: "Customers can place an eligible order.",
      delivery_drop: "mvp",
      splitting_pattern: "journey_stage",
      splitting_rationale: "Ordering is a distinct journey stage.",
      status: "generated",
      provenance: {
        generated_at: "2026-01-01T12:00:00Z",
        model: "fake",
        prompt_version: "fake-feature-v1",
      },
      stale: null,
      architecture: null,
      content_fingerprint: "feature-1-fingerprint",
      current_approval: null,
      approval_history: [],
      actions: generatedFeatureActions,
    },
    {
      id: "feature-2",
      version: 1,
      epic_id: "epic-1",
      name: "Service fulfilment",
      outcome: "Orders activate successfully.",
      delivery_drop: "later",
      splitting_pattern: "component_system",
      splitting_rationale: "Fulfilment is a separate system boundary.",
      status: "approved",
      provenance: {
        generated_at: "2026-01-01T12:00:00Z",
        model: "fake",
        prompt_version: "fake-feature-v1",
      },
      stale: null,
      architecture: null,
      content_fingerprint: "feature-2-fingerprint",
      current_approval: null,
      approval_history: [],
      actions: approvedFeatureActions,
    },
  ],
};

export const approvedFeatureFixture: Feature = {
  id: "feature-1",
  version: 1,
  epic_id: "epic-1",
  name: "Digital ordering",
  outcome: "Customers can place an eligible order.",
  delivery_drop: "mvp",
  splitting_pattern: "journey_stage",
  splitting_rationale: "Ordering is a distinct journey stage.",
  status: "approved",
  provenance: {
    generated_at: "2026-01-01T12:00:00Z",
    model: "fake",
    prompt_version: "fake-feature-v1",
  },
  stale: null,
  architecture: null,
  content_fingerprint: "feature-approved-fingerprint",
  current_approval: null,
  approval_history: [],
  actions: approvedFeatureActions,
  story_context_token: "story-set-context-1",
};

export const storyProvenance = {
  generated_at: "2026-01-01T12:00:00Z",
  model: "fake",
  prompt_version: "story-v1",
};

export const storyFixture: Story = {
  id: "story-1",
  version: 1,
  feature_id: "feature-1",
  role: "SMB customer",
  action: "check my eligibility before ordering",
  value: "I do not start an order I cannot complete",
  voice:
    "As a SMB customer, I want check my eligibility before ordering, so that I do not start an order I cannot complete.",
  acceptance_criteria: [
    {
      given: "an address in an XGPON area",
      when: "I run the eligibility check",
      then: "I see that I qualify",
    },
  ],
  status: "generated",
  provenance: storyProvenance,
  stale: null,
  architecture: null,
  content_fingerprint: "story-1-fingerprint",
  current_approval: null,
  approval_history: [],
  actions: generatedStoryActions,
  story_context_token: "story-context-1",
};

export const storySetFixture: StorySet = {
  feature_id: "feature-1",
  set_version: 1,
  generation_context_token: "story-set-context-1",
  stories: [
    storyFixture,
    {
      id: "story-2",
      version: 1,
      feature_id: "feature-1",
      role: "SMB customer",
      action: "place an eligible order online",
      value: "I can buy without calling support",
      voice:
        "As a SMB customer, I want place an eligible order online, so that I can buy without calling support.",
      acceptance_criteria: [
        {
          given: "a confirmed-eligible address",
          when: "I submit the order",
          then: "the order is accepted",
        },
      ],
      status: "generated",
      provenance: storyProvenance,
      stale: null,
      architecture: null,
      content_fingerprint: "story-2-fingerprint",
      current_approval: null,
      approval_history: [],
      actions: generatedStoryActions,
    },
  ],
};

export const storyQualityFixture: StoryQuality = {
  story_id: "story-1",
  status: "split_recommended",
  failure_count: 2,
  findings: [
    { criterion: "independent", passed: true, message: "The Story has a distinct outcome.", source: "semantic" },
    { criterion: "negotiable", passed: true, message: "The implementation remains open.", source: "semantic" },
    { criterion: "valuable", passed: true, message: "Customer value is explicit.", source: "semantic" },
    { criterion: "estimable", passed: false, message: "An unresolved integration prevents estimation.", source: "semantic" },
    { criterion: "small", passed: false, message: "The Story includes multiple delivery paths.", source: "semantic" },
    { criterion: "testable", passed: true, message: "Complete Given/When/Then criteria are present.", source: "deterministic" },
  ],
  recommendations: [
    { pattern: "spike", reason: "Time-box the integration uncertainty." },
    { pattern: "paths", reason: "Deliver the primary path first." },
  ],
  provenance: { generated_at: "2026-09-03T12:00:00Z", model: "fake", prompt_version: "quality-v1" },
};

export const splitProposalFixture: StoryProposal = {
  id: "proposal-1",
  version: 1,
  feature_id: "feature-1",
  operation: "split",
  source_story_ids: ["story-1"],
  candidates: [
    {
      role: "SMB customer",
      action: "enter my service address",
      value: "the system can locate my premises",
      voice:
        "As a SMB customer, I want enter my service address, so that the system can locate my premises.",
      acceptance_criteria: [
        { given: "a valid address", when: "I submit it", then: "the premises is located" },
      ],
      provenance: storyProvenance,
    },
    {
      role: "SMB customer",
      action: "see the eligibility result",
      value: "I know whether I can order",
      voice: "As a SMB customer, I want see the eligibility result, so that I know whether I can order.",
      acceptance_criteria: [
        { given: "a located premises", when: "the check runs", then: "I see a clear result" },
      ],
      provenance: storyProvenance,
    },
  ],
};
