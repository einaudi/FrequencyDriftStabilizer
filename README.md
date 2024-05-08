# FrequencyDriftStabilizer

## How to run
Python version 3.9.16. Required dependencies:

* [PyQt5](https://pypi.org/project/PyQt5/5.8/) - GUI
* [pyqtgraph](https://www.pyqtgraph.org) - graphs in GUI
* [numpy](https://numpy.org/install/) - numerical calculations
* [scipy](https://scipy.org/install/) - IIR filter calculation
* [yaml](https://pyyaml.org/wiki/PyYAMLDocumentation) - config files
* [pandas](https://pypi.org/project/pandas/) - CSV management
* [pyvisa](https://pypi.org/project/PyVISA/) - connection with third party devices

To run execute ```python gui.py``` in main directory.

By default dummy frequency counter and DDS are implemented. Devices can be chosen in ```/config/devices.yml```. Currently suported frequency counters: K+K FXE and Keysight FC53230A. Currently supported DDSes: DG4162.

Configuration file ```/config/config.py``` description:

| Variable                    | Description                                                                                                                                                                                                                                                              |
|-----------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ```tauMargin```             | Margin in Hz for period limits in Allan deviation calculation                                                                                                                                                                                                            |
| ```errorMargin```           | Margin in Hz of frequency error. Controls when frequency lock LED lits up                                                                                                                                                                                                |
| ```updateTimestep```        | Timestep in s of main plots update                                                                                                                                                                                                                                       |
| ```updateTimestepAllan```   | Timestep in s of Allan deviation plot update                                                                                                                                                                                                                             |
| ```waitOffset```            | Currently not used                                                                                                                                                                                                                                                       |
| ```phaseLockMargin```       | Margin in Hz of how low the frequency error must be to switch from FLL to PLL mode (only if PLL mode is active)                                                                                                                                                          |
| ```phaseLockCounterLimit``` | When PLL mode is activated this number describes how many consecutive frequency data points within ```phaseLockMargin``` are required to switch to PLL. Similarly while in PLL mode if this number of data points fall consecutively beyond ```phaseLockMargin``` stabilizer will switch back to FLL |
| ```loopFilter```            | Type of loop filter to be used. Currently available filters: PID, integrator with lowpass, double integrator with lowpass, double integrator with double lowpass                                                                                                         |
| ```flagPrintFilterOutput``` | When set to ```True``` filter calculation data will be printed in terminal                                                                                                                                                                                               |

## GUI sections description
### Frequency settings counter section
Connection with frequency counter. When connected successfully the readout will start and collected data will be displayed in the main plots on the right.

### DDS settings section
Connection with DDS. When lock is inactive user can change the parameters of DDS output. Enable button turns the DDS on. These settings are imported as initial values for control loop signal.

### Stabilisation settings section
| Element                    | Description                                                                                                                                                                                                                                           |
|----------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Target frequency and phase | Frequency and phase setpoints. Can be also used to check transient response of the system                                                                                                                                                             |
| Mode                       | Choice of only FLL or FLL switching to PLL                                                                                                                                                                                                            |
| Set filter                 | Send currently designed filters to the stabilization module. Must be done before engaging the lock                                                                                                                                                                                           |
| Reset filters              | Reset filter output values                                                                                                                                                                                                                            |
| Apply lowpass              | Apply lowpass filter to the incoming frequency data, before any further calculations                                                                                                                                                                  |
| Frequency lock LED         | Lits up when frequency data falls within ```errorMargin```                                                                                                                                                                                            |
| Phase lock LED             | Lits up when switched to PLL (doesn't guarantee phase lock!)                                                                                                                                                                                          |
| Lock button                | Engage lock                                                                                                                                                                                                                                           |
| Filter design section      | Set parameters of required filter. Based on filter type chosen in variable ```loopFilter``` different design wizard will show up (for loop frequency and phase filters). Lowpass filter tab is for the additional lowpass for the raw frequency data. |

### Plot settings section
Allan calculation may slow down the GUI, so it is optionally activated. 

User may choose what parameter is shown in the lower plot. 

When autosave is turned on the script will collect the data and save every 1000 points. Data is saved in ```/data``` directory in csv files. First row of the file starting with ```#``` contains metadata.
