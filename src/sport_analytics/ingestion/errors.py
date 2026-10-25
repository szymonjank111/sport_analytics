from pydantic import ValidationError


class SourceError(Exception):
    """The source answered with an error or with data of an unexpected shape."""


class NothingToLoadError(Exception):
    """No raw files were found for the run to load."""


def broken_contract(source: str, entity: str, error: ValidationError) -> SourceError:
    """One line, not pydantic's own message, which lists every error over many lines."""
    first, *others = error.errors()
    where = ".".join(str(part) for part in first["loc"]) or "the body"
    more = f" (and {len(others)} more)" if others else ""
    return SourceError(f"{source} broke the {entity} contract at {where}: {first['msg']}{more}")
