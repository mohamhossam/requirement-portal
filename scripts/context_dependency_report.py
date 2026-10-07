"""Report imports between the candidate bounded contexts of ADR-0103.

Each domain and application module is classified into the context `docs/architecture/
context-map.md` assigns it. The script then lists every import that crosses contexts, and
flags the ones that run against the dependency order:

    workflows > reporting > governance > breakdown > analysis > knowledge > requirements
    > {jobs | identity} > shared_kernel

A flagged edge is work the migration must remove before that context moves: an event, a port
the importing context owns, or a recorded change to the context map. Infrastructure and
interfaces are not classified; they follow their application layer when it moves.

Usage:

    python scripts/context_dependency_report.py            # summary and violations
    python scripts/context_dependency_report.py --edges    # also every allowed crossing
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict

import grimp

ROOT = "smb_requirement_agent"

# Higher ranks may import lower ranks. Equal ranks are independent siblings.
RANK = {
    "workflows": 9,
    "reporting": 8,
    "governance": 7,
    "breakdown": 6,
    "analysis": 5,
    "knowledge": 4,
    "requirements": 3,
    "jobs": 2,
    "identity": 2,
    "shared_kernel": 1,
}
# Shared technical modules (errors, transactions, external work). Any context may use them,
# and they must use no context.
TECHNICAL = "technical"

# Most specific prefix wins. Prefixes are relative to the package root.
DOMAIN = {
    "domain.shared": "shared_kernel",
    "domain.document.lineage": "shared_kernel",
    "domain.document.reference": "knowledge",
    "domain.document": "requirements",
    "domain.requirement": "requirements",
    "domain.analysis": "analysis",
    "domain.epic": "breakdown",
    "domain.feature": "breakdown",
    "domain.story": "breakdown",
    "domain.architecture.knowledge": "knowledge",
    "domain.architecture": "breakdown",
    "domain.review": "governance",
    "domain.revision": "governance",
    "domain.knowledge": "knowledge",
    "domain.identity": "identity",
    "domain.jobs": "jobs",
}

USE_CASES = {
    "identity": ["identity_access"],
    "jobs": [
        "ai_jobs",
        "ai_job_scheduling",
        "leased_jobs",
        "job_execution_context",
        "provider_call_rate",
        "retention",
    ],
    "requirements": [
        "create_requirement",
        "update_requirement",
        "get_requirement",
        "requirement_drafts",
        "owned_requirements",
        "requirement_impact",
        "requirement_sources",
        "documents",
        "attachment_ingestion",
        "source_lineage",
    ],
    "knowledge": [
        "requirement_knowledge",
        "requirement_indexing",
        "rebuild_knowledge_index",
        "qualify_chunk_tokens",
        "unified_knowledge_search",
        "knowledge_views",
        "knowledge_portfolio",
        "corpus_actions",
        "historic_corpus",
        "prior_art",
        "knowledge_event_cursor",
        "reference_currency",
        "source_impact",
        "knowledge_handoff",
    ],
    "analysis": [
        "analyze_requirement",
        "get_requirement_analysis",
        "clarify_requirement_analysis",
        "confirm_requirement_analysis",
        "analysis_collaboration",
        "analysis_mapping",
        "analysis_reconciliation",
        "answer_suggestions",
        "evidence_analysis",
        "generation_effects",
        "reference_grounding",
    ],
    "breakdown": [
        "generate_epic",
        "edit_epic",
        "get_epic",
        "generate_features",
        # Split in the migration: GetFeatures and EditFeature stay here, ApproveFeature moves
        # to governance.
        "feature_review",
        "story_workflow",
        "story_change_proposals",
        "story_quality",
        "generation_checks",
        "architecture_mapping",
        "architecture_mapping_jobs",
    ],
    "governance": [
        "breakdown_review",
        "breakdown_review_evidence",
        "breakdown_review_policy",
        "approval_workflow",
        "approval_policy",
        "approve_epic",
        "revision_history",
        "export_breakdown",
        # Dissolved into event handlers; today they are governance's reach into the others.
        "invalidate_approval_workflow",
        "invalidate_derived_artifacts",
    ],
    "reporting": [
        "requirement_worklist",
        "activity_reporting",
        "saved_views",
        "dependency_projection",
    ],
    "workflows": [
        "requirement_commands",
        "ai_job_execution",
        "generation_context",
        "internal_reads",
    ],
}

PORTS = {
    "identity": ["access_repository", "actor_directory", "identity"],
    "jobs": ["ai_jobs", "notifications"],
    "requirements": [
        "attachment_ingestions",
        "document_repository",
        "requirement_draft_repository",
        "requirement_repository",
        "source_dependencies",
    ],
    "knowledge": [
        "architecture_knowledge",
        "corpus_membership",
        "corpus_summary",
        "embedding",
        "historic_corpus",
        "knowledge_events",
        "knowledge_handoff",
        "knowledge_index_generations",
        "knowledge_portfolio",
        "knowledge_views",
        "prior_art",
        "reference_grounding",
        "reference_publications",
        "requirement_indexing",
        "requirement_knowledge",
    ],
    "analysis": [
        "analysis_audit_repository",
        "requirement_analysis_repository",
        "requirement_analyzer",
        "requirement_evidence_analyzer",
    ],
    "breakdown": [
        "architecture_jobs",
        "architecture_mapping_stats",
        "epic_generator",
        "epic_repository",
        "feature_generator",
        "feature_repository",
        "generation_guidance",
        "story_generator",
        "story_quality_evaluator",
        "story_quality_repository",
        "story_repository",
    ],
    "governance": ["backlog_export", "breakdown_repository", "breakdown_review_repository"],
    "reporting": ["activity", "requirement_worklist", "saved_views"],
    TECHNICAL: ["external_work", "transaction_manager"],
}

APPLICATION_MODULES = {
    "application.document_upload_validation": "requirements",
    "application.exports": "governance",
    "application.grounding_evaluation": "knowledge",
    "application.retrieval_evaluation": "knowledge",
    "application.prior_art_evaluation": "knowledge",
    "application.errors": TECHNICAL,
    "application.public_errors": TECHNICAL,
}


def _prefixes() -> dict[str, str]:
    table = dict(DOMAIN)
    table.update(APPLICATION_MODULES)
    for context, names in USE_CASES.items():
        table.update({f"application.use_cases.{name}": context for name in names})
    for context, names in PORTS.items():
        table.update({f"application.ports.{name}": context for name in names})
    return table


def classify(module: str, table: dict[str, str]) -> str | None:
    """The context of a domain or application module, or None if it is not classified."""
    relative = module.removeprefix(f"{ROOT}.")
    best = max(
        (prefix for prefix in table if relative == prefix or relative.startswith(f"{prefix}.")),
        key=len,
        default=None,
    )
    return table[best] if best else None


def _in_scope(module: str) -> bool:
    relative = module.removeprefix(f"{ROOT}.")
    if relative in ("domain", "application", "application.use_cases", "application.ports"):
        return False
    return relative.startswith(("domain.", "application."))


def allowed(source: str, target: str) -> bool:
    if source == target or target == TECHNICAL:
        return True
    if source == TECHNICAL:
        return False
    return RANK[source] > RANK[target]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--edges", action="store_true", help="also list allowed crossings")
    arguments = parser.parse_args(argv)

    graph = grimp.build_graph(ROOT)
    table = _prefixes()
    modules = sorted(module for module in graph.modules if _in_scope(module))
    unclassified = [module for module in modules if classify(module, table) is None]

    crossings: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for module in modules:
        source = classify(module, table)
        if source is None:
            continue
        for imported in sorted(graph.find_modules_directly_imported_by(module)):
            if not _in_scope(imported):
                continue
            target = classify(imported, table)
            if target is None or target == source:
                continue
            crossings[(source, target)].append((module, imported))

    violations = {pair: edges for pair, edges in crossings.items() if not allowed(*pair)}
    print(f"Classified {len(modules) - len(unclassified)} of {len(modules)} modules.")
    print(f"Context pairs crossed: {len(crossings)}; against the order: {len(violations)}.")
    print()
    print("Crossings against the dependency order:")
    for (source, target), edges in sorted(violations.items()):
        print(f"  {source} -> {target} ({len(edges)} imports)")
        for module, imported in edges:
            print(f"      {module.removeprefix(ROOT + '.')} -> {imported.removeprefix(ROOT + '.')}")
    if arguments.edges:
        print()
        print("Allowed crossings:")
        for (source, target), edges in sorted(crossings.items()):
            if (source, target) not in violations:
                print(f"  {source} -> {target} ({len(edges)} imports)")
    if unclassified:
        print()
        print("Unclassified modules (add them to this script and to the context map):")
        for module in unclassified:
            print(f"  {module.removeprefix(ROOT + '.')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
