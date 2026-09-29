"""Extractor registry: source name -> extractor class."""

from prospector.extractors.hackernews import HackerNewsExtractor

EXTRACTORS: dict[str, type[HackerNewsExtractor]] = {
    HackerNewsExtractor.name: HackerNewsExtractor,
}
