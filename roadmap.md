# Roadmap

The core LangGraph workflow, YAML strategy loader and basic renderers are in place.
The following tasks remain to finalise the project and make it ready for wider use.

## Immediate tasks

- **CLI interface** – expose the graph as a command line tool and provide runnable examples.
- **Robust adapters** – add retry/backoff, caching and better error reporting for Sonar and Exa.
- **Strategy library** – expand YAML strategies and macros for additional categories and depths.
- **Documentation** – polish API references, developer guides and example workflows.

## Testing and quality

- Add integration tests that mock tool responses for end-to-end runs.
- Introduce linting and type checking in continuous integration.
- Validate strategies against `schema.json` during tests.

## Future enhancements

- Additional tool adapters (finance filings, court records, scientific preprints, etc.).
- Optional logging/tracing pipeline for debugging and audit trails.
- Packaging and versioned release on PyPI.

