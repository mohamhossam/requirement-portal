"""The knowledge service's internal API, served to requirement work (ADR-0099).

It lives here while the library and catalogue code does, so requirement work's
HTTP adapters can be tested against the real thing. It is not mounted in this
application; Stage 3 moves it, unchanged, into knowledge-portal.
"""
