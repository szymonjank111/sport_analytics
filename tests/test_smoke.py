"""Test-szkielet: potwierdza, że pakiet się importuje i pytest działa.

Właściwe testy parserów (z fixture'ami prawdziwych odpowiedzi API) dojdą w fazie 2.
"""

import ingestion


def test_package_importuje_sie():
    assert ingestion.__doc__
