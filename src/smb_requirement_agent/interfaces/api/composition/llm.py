"""LLM provider selection: one decision, every focused adapter built from it."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass, replace
from typing import TypedDict

import httpx as httpx
import httpx2
from openai import DefaultHttpxClient, OpenAI

from smb_requirement_agent.application.ports.architecture_rag import ArchitectureReasonerPort
from smb_requirement_agent.application.ports.catalogue_extractor import CatalogueExtractorPort
from smb_requirement_agent.application.ports.epic_generator import EpicGeneratorPort
from smb_requirement_agent.application.ports.feature_generator import FeatureGeneratorPort
from smb_requirement_agent.application.ports.reference_grounding import ReferenceProposerPort
from smb_requirement_agent.application.ports.requirement_analyzer import RequirementAnalyzerPort
from smb_requirement_agent.application.ports.requirement_knowledge import (
    ClarificationAnswerSuggesterPort,
    KnowledgeEmbeddingPort,
    RequirementRelationshipClassifierPort,
)
from smb_requirement_agent.application.ports.story_generator import StoryGeneratorPort
from smb_requirement_agent.application.ports.story_quality_evaluator import (
    StoryQualityEvaluatorPort,
)
from smb_requirement_agent.application.ports.system_matcher import SystemMatcherPort
from smb_requirement_agent.infrastructure.architecture.embeddings import ArchitectureEmbeddings
from smb_requirement_agent.infrastructure.architecture.reasoning import (
    FakeArchitectureReasoner,
    StructuredArchitectureReasoner,
)
from smb_requirement_agent.infrastructure.config.options import ConfigurationError, LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.diagnostics import DebugTrace, build_debug_trace
from smb_requirement_agent.infrastructure.llm.catalogue_extraction import (
    FakeCatalogueExtractor,
    StructuredCatalogueExtractor,
)
from smb_requirement_agent.infrastructure.llm.catalogue_matching import (
    FakeSystemMatcher,
    StructuredSystemMatcher,
)
from smb_requirement_agent.infrastructure.llm.compatible_transport import (
    CompatibleStructuredOutputClient,
    ConfiguredKnowledgeEmbedding,
)
from smb_requirement_agent.infrastructure.llm.fake_epic_generator import FakeEpicGenerator
from smb_requirement_agent.infrastructure.llm.fake_feature_generator import FakeFeatureGenerator
from smb_requirement_agent.infrastructure.llm.fake_requirement_analyzer import (
    FakeRequirementAnalyzer,
)
from smb_requirement_agent.infrastructure.llm.fake_requirement_knowledge import (
    FakeClarificationAnswerSuggester,
    FakeKnowledgeEmbedding,
    FakeRequirementRelationshipClassifier,
)
from smb_requirement_agent.infrastructure.llm.fake_story_generator import FakeStoryGenerator
from smb_requirement_agent.infrastructure.llm.fake_story_quality_evaluator import (
    FakeStoryQualityEvaluator,
)
from smb_requirement_agent.infrastructure.llm.local_epic_generator import (
    LocalEpicGenerator,
    StructuredEpicGeneratorAdapter,
)
from smb_requirement_agent.infrastructure.llm.local_feature_generator import (
    LocalFeatureGenerator,
    StructuredFeatureGeneratorAdapter,
)
from smb_requirement_agent.infrastructure.llm.local_requirement_analyzer import (
    LocalRequirementAnalyzer,
    StructuredRequirementAnalyzerAdapter,
)
from smb_requirement_agent.infrastructure.llm.local_story_generator import (
    LocalStoryGenerator,
    StructuredStoryGeneratorAdapter,
)
from smb_requirement_agent.infrastructure.llm.local_story_quality_evaluator import (
    LocalStoryQualityEvaluator,
    StructuredStoryQualityEvaluatorAdapter,
)
from smb_requirement_agent.infrastructure.llm.local_structured_output import (
    LocalStructuredOutputClient,
)
from smb_requirement_agent.infrastructure.llm.openai_adapters import (
    OpenAIClarificationAnswerSuggester,
    OpenAIEpicGenerator,
    OpenAIFeatureGenerator,
    OpenAIRequirementAnalyzer,
    OpenAIRequirementRelationshipClassifier,
    OpenAIStoryGenerator,
    OpenAIStoryQualityEvaluator,
)
from smb_requirement_agent.infrastructure.llm.openai_structured_output import (
    OpenAIStructuredOutputClient,
)
from smb_requirement_agent.infrastructure.llm.openrouter_adapters import (
    OpenRouterAdapterSettings,
    OpenRouterClarificationAnswerSuggester,
    OpenRouterEpicGenerator,
    OpenRouterFeatureGenerator,
    OpenRouterRequirementAnalyzer,
    OpenRouterRequirementRelationshipClassifier,
    OpenRouterStoryGenerator,
    OpenRouterStoryQualityEvaluator,
)
from smb_requirement_agent.infrastructure.llm.openrouter_structured_output import (
    OpenRouterStructuredOutputClient,
)
from smb_requirement_agent.infrastructure.llm.reference_proposals import (
    FakeReferenceProposer,
    StructuredReferenceProposer,
)
from smb_requirement_agent.infrastructure.llm.requirement_knowledge_adapters import (
    LocalClarificationAnswerSuggester,
    LocalKnowledgeEmbedding,
    LocalRequirementRelationshipClassifier,
    OpenAIKnowledgeEmbedding,
    OpenRouterKnowledgeEmbedding,
    StructuredClarificationAnswerSuggesterAdapter,
    StructuredRequirementRelationshipClassifierAdapter,
)
from smb_requirement_agent.infrastructure.observability.metrics import (
    MeteredTransport,
    MeteredTransport2,
    Metrics,
)

# Hosted models configured without a profile declare no context window; this is
# conservative for current OpenAI and OpenRouter models.
HOSTED_MODEL_INPUT_TOKENS = 100_000


@dataclass(frozen=True)
class LLMAdapters:
    """All focused LLM ports selected from one provider decision."""

    analyzer: RequirementAnalyzerPort
    epic_generator: EpicGeneratorPort
    feature_generator: FeatureGeneratorPort
    story_generator: StoryGeneratorPort
    story_quality_evaluator: StoryQualityEvaluatorPort
    knowledge_embedding: KnowledgeEmbeddingPort
    relationship_classifier: RequirementRelationshipClassifierPort
    answer_suggester: ClarificationAnswerSuggesterPort
    reference_proposer: ReferenceProposerPort
    catalogue_extractor: CatalogueExtractorPort
    system_matcher: SystemMatcherPort
    architecture_reasoner: ArchitectureReasonerPort
    debug_trace: DebugTrace

    resources: ExitStack

    def close(self) -> None:
        self.resources.close()


class _LocalAdapterSettings(TypedDict):
    http_client: httpx.Client
    base_url: str
    model: str
    timeout_seconds: float
    reasoning_effort: str | None
    context_window_tokens: int
    max_output_tokens: int
    debug_trace: DebugTrace


def _profile_adapters(
    settings: Settings, resources: ExitStack, debug_trace: DebugTrace, metrics: Metrics
) -> LLMAdapters:

    config = settings.llm_profiles
    if config is None:  # Enforced by Settings for LLM_PROVIDER=profiles.
        raise ConfigurationError("LLM_PROVIDER=profiles requires LLM_CONFIG_PATH.")
    http = resources.enter_context(
        httpx.Client(transport=MeteredTransport(metrics, "profiles", httpx.HTTPTransport()))
    )
    analysis = config.for_task("analysis")
    generation = config.for_task("generation")
    review = config.for_task("review")
    knowledge = config.for_task("knowledge")
    catalogue = config.for_task("catalogue")
    clients = {
        task: CompatibleStructuredOutputClient(config.for_task(task), http, debug_trace)
        for task in ("analysis", "generation", "review", "knowledge", "catalogue")
    }
    debug_trace.record("models.configured", profiles=config.summary())
    for task, selection in config.summary().items():
        if isinstance(selection, dict):
            print(f"LLM {task}: {selection['provider']} / {selection['model']}", flush=True)
    embedding = ConfiguredKnowledgeEmbedding(config.selected_embedding, http, debug_trace)
    return LLMAdapters(
        analyzer=StructuredRequirementAnalyzerAdapter(
            client=clients["analysis"],
            provider_name=analysis.provider,
            vision_enabled=analysis.images,
            vision_error="The configured analysis profile cannot process image evidence.",
            debug_trace=debug_trace,
        ),
        epic_generator=StructuredEpicGeneratorAdapter(clients["generation"], generation.provider),
        feature_generator=StructuredFeatureGeneratorAdapter(
            clients["generation"], generation.provider
        ),
        story_generator=StructuredStoryGeneratorAdapter(clients["generation"], generation.provider),
        story_quality_evaluator=StructuredStoryQualityEvaluatorAdapter(
            clients["review"], review.provider
        ),
        knowledge_embedding=embedding,
        relationship_classifier=StructuredRequirementRelationshipClassifierAdapter(
            clients["knowledge"], knowledge.provider
        ),
        answer_suggester=StructuredClarificationAnswerSuggesterAdapter(
            clients["knowledge"], knowledge.provider
        ),
        reference_proposer=StructuredReferenceProposer(clients["knowledge"]),
        catalogue_extractor=StructuredCatalogueExtractor(
            clients["catalogue"],
            supports_images=catalogue.images,
            max_input_tokens=catalogue.context_tokens - catalogue.output_tokens,
            max_output_tokens=catalogue.output_tokens,
        ),
        system_matcher=StructuredSystemMatcher(
            clients["catalogue"],
            ArchitectureEmbeddings(embedding),
            max_input_tokens=catalogue.context_tokens - catalogue.output_tokens,
        ),
        architecture_reasoner=StructuredArchitectureReasoner(
            clients["knowledge"],
            max_input_tokens=knowledge.context_tokens - knowledge.output_tokens,
        ),
        debug_trace=debug_trace,
        resources=resources,
    )


def build_llm_adapters(settings: Settings, metrics: Metrics) -> LLMAdapters:
    with ExitStack() as resources:
        result = _build_llm_adapters(settings, resources, metrics)
        return replace(result, resources=resources.pop_all())


def _build_llm_adapters(settings: Settings, resources: ExitStack, metrics: Metrics) -> LLMAdapters:
    """Select the configured provider once and construct its focused adapters."""
    debug_trace = build_debug_trace(
        enabled=settings.debug_trace_enabled,
        path=settings.debug_trace_path,
        secrets=tuple(
            value
            for value in (
                settings.openai_api_key,
                settings.openrouter_api_key,
                settings.database_url,
                *(settings.llm_profiles.secrets if settings.llm_profiles else ()),
            )
            if value
        ),
    )
    resources.callback(debug_trace.close)
    if settings.llm_provider is LLMProvider.PROFILES:
        return _profile_adapters(settings, resources, debug_trace, metrics)
    if settings.llm_provider is LLMProvider.FAKE:
        return LLMAdapters(
            analyzer=FakeRequirementAnalyzer(),
            epic_generator=FakeEpicGenerator(),
            feature_generator=FakeFeatureGenerator(),
            story_generator=FakeStoryGenerator(),
            story_quality_evaluator=FakeStoryQualityEvaluator.passing(),
            knowledge_embedding=FakeKnowledgeEmbedding(),
            relationship_classifier=FakeRequirementRelationshipClassifier(),
            answer_suggester=FakeClarificationAnswerSuggester(),
            reference_proposer=FakeReferenceProposer(),
            catalogue_extractor=FakeCatalogueExtractor(),
            system_matcher=FakeSystemMatcher(),
            architecture_reasoner=FakeArchitectureReasoner(),
            debug_trace=debug_trace,
            resources=resources,
        )
    if settings.llm_provider is LLMProvider.LOCAL:
        http_client = resources.enter_context(
            httpx.Client(transport=MeteredTransport(metrics, "local", httpx.HTTPTransport()))
        )
        shared: _LocalAdapterSettings = {
            "http_client": http_client,
            "base_url": settings.local_llm_base_url,
            "model": settings.local_llm_model,
            "timeout_seconds": settings.local_llm_timeout_seconds,
            "reasoning_effort": settings.local_llm_reasoning_effort,
            "context_window_tokens": settings.local_llm_context_window_tokens,
            "max_output_tokens": settings.local_llm_max_output_tokens,
            "debug_trace": debug_trace,
        }
        local_embedding = LocalKnowledgeEmbedding(
            settings.local_llm_base_url,
            settings.local_embedding_model,
            settings.local_llm_timeout_seconds,
            http_client,
        )
        local_input_tokens = (
            settings.local_llm_context_window_tokens - settings.local_llm_max_output_tokens
        )
        return LLMAdapters(
            analyzer=LocalRequirementAnalyzer(
                **shared, vision_enabled=settings.local_llm_vision_enabled
            ),
            epic_generator=LocalEpicGenerator(**shared),
            feature_generator=LocalFeatureGenerator(**shared),
            story_generator=LocalStoryGenerator(**shared),
            story_quality_evaluator=LocalStoryQualityEvaluator(**shared),
            knowledge_embedding=local_embedding,
            relationship_classifier=LocalRequirementRelationshipClassifier(**shared),
            answer_suggester=LocalClarificationAnswerSuggester(**shared),
            reference_proposer=StructuredReferenceProposer(LocalStructuredOutputClient(**shared)),
            catalogue_extractor=StructuredCatalogueExtractor(
                LocalStructuredOutputClient(**shared),
                supports_images=settings.local_llm_vision_enabled,
                max_input_tokens=local_input_tokens,
                max_output_tokens=settings.local_llm_max_output_tokens,
            ),
            system_matcher=StructuredSystemMatcher(
                LocalStructuredOutputClient(**shared),
                ArchitectureEmbeddings(local_embedding),
                max_input_tokens=local_input_tokens,
            ),
            architecture_reasoner=StructuredArchitectureReasoner(
                LocalStructuredOutputClient(**shared),
                max_input_tokens=local_input_tokens,
            ),
            debug_trace=debug_trace,
            resources=resources,
        )
    if settings.llm_provider is LLMProvider.OPENROUTER:
        if settings.openrouter_api_key is None:  # guarded by Settings, keeps mypy explicit
            raise AssertionError("OpenRouter settings require OPENROUTER_API_KEY.")
        http_client = resources.enter_context(
            httpx.Client(transport=MeteredTransport(metrics, "openrouter", httpx.HTTPTransport()))
        )
        openrouter_shared: OpenRouterAdapterSettings = {
            "http_client": http_client,
            "base_url": settings.openrouter_base_url,
            "api_key": settings.openrouter_api_key,
            "model": settings.openrouter_model,
            "timeout_seconds": settings.openrouter_timeout_seconds,
            "max_output_tokens": settings.openrouter_max_output_tokens,
            "data_collection": settings.openrouter_data_collection,
            "debug_trace": debug_trace,
        }
        openrouter_embedding = OpenRouterKnowledgeEmbedding(
            base_url=settings.openrouter_base_url,
            http_client=http_client,
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_embedding_model,
            timeout_seconds=settings.openrouter_timeout_seconds,
            data_collection=settings.openrouter_data_collection,
        )
        return LLMAdapters(
            analyzer=OpenRouterRequirementAnalyzer(**openrouter_shared),
            epic_generator=OpenRouterEpicGenerator(**openrouter_shared),
            feature_generator=OpenRouterFeatureGenerator(**openrouter_shared),
            story_generator=OpenRouterStoryGenerator(**openrouter_shared),
            story_quality_evaluator=OpenRouterStoryQualityEvaluator(**openrouter_shared),
            knowledge_embedding=openrouter_embedding,
            relationship_classifier=OpenRouterRequirementRelationshipClassifier(
                **openrouter_shared
            ),
            answer_suggester=OpenRouterClarificationAnswerSuggester(**openrouter_shared),
            reference_proposer=StructuredReferenceProposer(
                OpenRouterStructuredOutputClient(**openrouter_shared)
            ),
            catalogue_extractor=StructuredCatalogueExtractor(
                OpenRouterStructuredOutputClient(**openrouter_shared),
                supports_images=True,
                max_input_tokens=HOSTED_MODEL_INPUT_TOKENS,
                max_output_tokens=settings.openrouter_max_output_tokens,
            ),
            system_matcher=StructuredSystemMatcher(
                OpenRouterStructuredOutputClient(**openrouter_shared),
                ArchitectureEmbeddings(openrouter_embedding),
                max_input_tokens=HOSTED_MODEL_INPUT_TOKENS,
            ),
            architecture_reasoner=StructuredArchitectureReasoner(
                OpenRouterStructuredOutputClient(**openrouter_shared),
                max_input_tokens=HOSTED_MODEL_INPUT_TOKENS,
            ),
            debug_trace=debug_trace,
            resources=resources,
        )
    if settings.openai_api_key is None:  # guarded by Settings, keeps mypy explicit
        raise AssertionError("OpenAI settings require OPENAI_API_KEY.")
    client = resources.enter_context(
        OpenAI(
            api_key=settings.openai_api_key,
            http_client=DefaultHttpxClient(
                transport=MeteredTransport2(metrics, "openai", httpx2.HTTPTransport())
            ),
        )
    )
    openai_model = settings.openai_model
    openai_timeout = settings.openai_timeout_seconds
    openai_embedding = OpenAIKnowledgeEmbedding(client, settings.openai_embedding_model)
    return LLMAdapters(
        analyzer=OpenAIRequirementAnalyzer(
            client, model=openai_model, timeout_seconds=openai_timeout, debug_trace=debug_trace
        ),
        epic_generator=OpenAIEpicGenerator(
            client, model=openai_model, timeout_seconds=openai_timeout
        ),
        feature_generator=OpenAIFeatureGenerator(
            client, model=openai_model, timeout_seconds=openai_timeout
        ),
        story_generator=OpenAIStoryGenerator(
            client, model=openai_model, timeout_seconds=openai_timeout
        ),
        story_quality_evaluator=OpenAIStoryQualityEvaluator(
            client, model=openai_model, timeout_seconds=openai_timeout
        ),
        knowledge_embedding=openai_embedding,
        relationship_classifier=OpenAIRequirementRelationshipClassifier(
            client, model=openai_model, timeout_seconds=openai_timeout
        ),
        answer_suggester=OpenAIClarificationAnswerSuggester(
            client, model=openai_model, timeout_seconds=openai_timeout
        ),
        reference_proposer=StructuredReferenceProposer(
            OpenAIStructuredOutputClient(client, model=openai_model, timeout_seconds=openai_timeout)
        ),
        catalogue_extractor=StructuredCatalogueExtractor(
            OpenAIStructuredOutputClient(
                client, model=openai_model, timeout_seconds=openai_timeout
            ),
            supports_images=True,
            max_input_tokens=HOSTED_MODEL_INPUT_TOKENS,
        ),
        system_matcher=StructuredSystemMatcher(
            OpenAIStructuredOutputClient(
                client, model=openai_model, timeout_seconds=openai_timeout
            ),
            ArchitectureEmbeddings(openai_embedding),
            max_input_tokens=HOSTED_MODEL_INPUT_TOKENS,
        ),
        architecture_reasoner=StructuredArchitectureReasoner(
            OpenAIStructuredOutputClient(
                client, model=openai_model, timeout_seconds=openai_timeout
            ),
            max_input_tokens=HOSTED_MODEL_INPUT_TOKENS,
        ),
        debug_trace=debug_trace,
        resources=resources,
    )
