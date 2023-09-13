# PCIe Lane Margining Tool (LMT)
LMT is a standard PCIE margining measurement added by PCI-SIG in the PCIe 4.0 specification.
This is required mainly to overcome the challenges in delivering a reliable 16GT/s solution.
Lane Margining enables system designers to measure the available margin in a standardized manner.

# Key Benefits
- Works in a production platform without any test equipment
- Provides a way to measure actual margin when running prod traffic
- Provides visibility to the details of the defect:
    - exactly which wires/pins are bad
    - exactly how ‘bad’ each wire pair (vs a nominal system)
- Avoids excessive part swaps triggered by multiple repair actions
- Provides a reliable way to check if source defect is fixed after repairs

This project is part of [ocp-diag-core](https://github.com/opencomputeproject/ocp-diag-core) and exists under the same [MIT License Agreement](https://github.com/opencomputeproject/ocp-diag-pci_lmt/LICENSE).

# Usage

**Minimum python version is currently py3.8**

The binary can be installed from [`PyPI ocptv-pci_lmt`](https://pypi.org/project/ocptv-pci-lmt/) and can be used directly on a system as such:

```
> pci_lmt -h
usage: pci_lmt [-h] [-o {json,csv}] [-e ERROR_COUNT_LIMIT] [-d DWELL_TIME] [-a ANNOTATION] [-v] [--version] config_file

Runs Lane Margining Test on PCIe devices.

positional arguments:
  config_file           Path to the configuration file (in JSON format).

optional arguments:
  -h, --help            show this help message and exit
  -o {json,csv}         Output format. Supported formats: json, csv. Default: json
  -e ERROR_COUNT_LIMIT  Maximum errors allowed before terminating the test. Default: 63
  -d DWELL_TIME         Amount of time (in seconds) to wait before making BER measurements. Default: 5
  -a ANNOTATION         Annotation string to be prefix'd for LMT results. Default: <empty>
  -v                    Verbosity level. Use '-v' for INFO and '-vv' for DEBUG. Default: 0
  --version             Print tool version and exit.
```

### Contact

Feel free to start a new [discussion](https://github.com/opencomputeproject/ocp-diag-pci_lmt/discussions), or otherwise post an [issue/request](https://github.com/opencomputeproject/ocp-diag-pci_lmt/issues).

# Developer notes

New code may be committed through features or bugfix branches (eg. `fea/cool_new_thing` or `bugfix/none_in_collector`). All PRs must be merged into the `dev` branch.

Quickest way to setup a dev environment:
```bash
# make a venv, see https://docs.python.org/3/library/venv.html
> python3 -m venv env
. ./env/bin/activate

> pip install -r requirements.txt

# [1] then the main script can be run from source
> python src/pci_lmt_bin/main.py --version
main.py 1.1.1

# [2] or alternatively do a local editable install and use it as an executable
# see: https://setuptools.pypa.io/en/latest/userguide/development_mode.html
> pip install -e .
> pci_lmt --version
pci_lmt 1.1.1
```

Before pushing new commits upstream, please check that your changes pass the linters, formatting, typechecker, etc.
All the following checks should pass (and return exit code 0). They are also run in a github action, which safeguards against problematic code.

```bash
> black . --check --preview
All done! ✨ 🍰 ✨
14 files would be left unchanged.

# remove the fixme disable to see the list of TODOs in the codebase
> pylint src tests --disable fixme

--------------------------------------------------------------------
Your code has been rated at 10.00/10 (previous run: 10.00/10, +0.00)

> mypy src tests --check-untyped-defs
Success: no issues found in 14 source files

# run all unit tests
> find tests -type f -name "test_*.py" | xargs testslide
```
