"""The jobs bounded context (ADR-0103): durable AI jobs, notifications and provider-call limits.

Generic subdomain. `domain/` holds `AiJob` and `ActorNotification`. The workers that drive
jobs belong to the contexts whose work they run, not here.
"""
