# PCIe Lane Margining Tool (LMT)
LMT is a standard PCIE margining measurement added by PCI-SIG in the PCIe 4.0 specification.
This is required mainly to overcome the challenges in delivering a reliable 16GT/s solution.
Lane Margining enables system designers to measure the available margin in a standardized manner.

# Key Benefits
- Works in a production platform without any test equipment
- Provides a way to measure actual margin when running prod traffic
- Provides visibility to the details of the defect:
    - exactly which wires/pins are bad
    - exactly how ‘bad’ each wire pair (vs a nominal system
- Avoids excessive part swaps triggered by multiple repair actions
- Provides a reliable way to check if source defect is fixed after repairs

# Command Syntax

```
$ pci_lmt -h
usage: pci_lmt.par [-h] [-c CONFIG_FILE] [-e ERROR_COUNT_LIMIT] [-d DWELL_TIME] [-a ANNOTATION] [-o OUTPUT] [-v] config_file

Runs Lane Margining Test on PCIe devices.

  CONFIG_FILE        Path to the local configuration file (in JSON format). Overrides `platform` flag.

options:
  -h, --help            show this help message and exit
  -e ERROR_COUNT_LIMIT  Maximum errors allowed before terminating the test. Default: 63
  -d DWELL_TIME         Amount of time (in seconds) to wait before making BER measurements. Default: 5
  -a ANNOTATION         Annotation string to be prefix'd for LMT results. Default: <empty>
  -o OUTPUT             Output format. Supported formats: scribe, json. Default: json
  -v                    Verbosity level. Use '-v' for INFO and '-vv' for DEBUG. Default: 0
```
