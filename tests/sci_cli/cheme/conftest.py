def pytest_addoption(parser):
    parser.addini("cheme_python", "Already prepared ChemE-as-Code interpreter", default="")
