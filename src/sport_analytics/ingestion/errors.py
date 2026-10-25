class SourceError(Exception):
    """The source answered with an error or with data of an unexpected shape."""


class NothingToLoadError(Exception):
    """No raw files were found for the run to load."""
