import ctypes, warnings, numpy

##print "Opening DAQ card..."
#oledll, cdll, or windll?
api = ctypes.cdll.LoadLibrary("nicaiu")
##print "DAQ card open."
"""Requires nicaiu.dll to be in the same directory. If you get an
error, read NIDAQmx.h to decypher it."""

class DAQ:
    def __init__(
        self, voltage={0:[1]}, rate=500, repetitions=1,
        board_name='cDAQ1Mod1', voltage_limits=None):
        """'voltage' should be a dict of numpy arrays of
        floating-point numbers. The keys of 'voltage' are integers,
        0-3. Each element of 'voltage' should start and end near zero.
        'repetitions' and 'rate' should be integers.
        """
        self.board_name = board_name #Check Measurement and Automation Explorer
        self._taskHandle = ctypes.c_void_p(0)
        DAQmxErrChk(api.DAQmxCreateTask("", ctypes.byref(self._taskHandle)))
        DAQmxErrChk(api.DAQmxCreateAOVoltageChan(
            self._taskHandle,
            self.board_name + "/ao0:3", #Open all four channels
            "",
            ctypes.c_double(-10.0), #Minimum voltage
            ctypes.c_double(10.0), #Maximum voltage
            10348, #DAQmx_Val_Volts; don't question it!
            ctypes.c_void_p(0), #NULL
            ))
        self.num_points_written = ctypes.c_long(0)
        self._unwritten_voltages = False
        self._unplayed_voltages = False
        self.set_voltage_and_timing(voltage, rate, repetitions, voltage_limits)
        return None

    def set_voltage_and_timing(
        self, voltage, rate, repetitions, voltage_limits=None):
        if voltage_limits == None: #Use +/-10 V as the default
            voltage_limits = {
                0: 10,
                1: 10,
                2: 10,
                3: 10}
        num_points = -1
        for k in range(4):
            if k in voltage:
                v = voltage[k]
                if v.max() - v.min() > voltage_limits[k]:
                    raise UserWarning(
                        "Voltage signal amplitude exceeds voltage limits.")
                if num_points == -1:
                    num_points = len(v)
                    self.voltage = numpy.zeros(
                        (num_points, 4), dtype=numpy.float64)
                if len(v) != num_points:
                    raise UserWarning(
                        'Every channel in "voltage" must have the same' +
                        ' number of points.')
                self.voltage[:, k] = v
        self.voltage = numpy.tile(self.voltage, (repetitions, 1))
        num_points *= repetitions
        self.voltage = self.voltage.reshape(self.voltage.size) #Flattened
        DAQmxErrChk(api.DAQmxCfgSampClkTiming(
            self._taskHandle,
            ctypes.c_void_p(0),#NULL, to specify onboard clock for timing
            ctypes.c_double(rate),
            10280, #DAQmx_Val_Rising, doesn't matter
            10178, #DAQmx_Val_FiniteSamps (Run once. Continuous sucks)
            num_points))
        self.rate = rate
        print "DAQ card scan rate set to", rate, "points per second"
        self._unwritten_voltages=True
        return None

    def write_voltage(self):
        """
        You shouldn't have to call this yourself unless you're trying
        to optimize performance. This should get called automatically,
        as needed, by 'scan'.
        """
        if self._unplayed_voltages:
            raise UserWarning(
                "After you write voltages to the DAQ card, you have to scan\n" +
                "the voltage at least once before you can set the voltage\n" +
                "again.")
        DAQmxErrChk(api.DAQmxWriteAnalogF64(
            self._taskHandle,
            len(self.voltage)//4,
            0,
            ctypes.c_double(10.0), #Timeout for writing. Hope it ain't this slow.
            1, #DAQmx_Val_GroupByScanNumber (interleaved)
            numpy.ctypeslib.as_ctypes(self.voltage),
            ctypes.byref(self.num_points_written),
            ctypes.c_void_p(0)
            ))
        print self.num_points_written.value,
        print "points written to each DAQ channel."
        self._unwritten_voltages = False
        self._unplayed_voltages = True
        return None

    def scan(self, background=False, timeout=60.0, verbose=True):
        if self._unwritten_voltages:
            self.write_voltage()
        DAQmxErrChk(api.DAQmxStartTask(self._taskHandle))
        if verbose:
            print "Scanning voltage..."
        if background:
            if verbose:
                print "Scanning in background"
        else:
            self.finish_scan(timeout=timeout, verbose=verbose)
        self._unplayed_voltages=False
        return None

    def finish_scan(self, timeout=60.0, verbose=True):
        DAQmxErrChk(api.DAQmxWaitUntilTaskDone(
            self._taskHandle,
            ctypes.c_double(timeout), #Timeout period in seconds
            ))
        DAQmxErrChk(api.DAQmxStopTask(self._taskHandle))
        if verbose:
            print "Done scanning"
        return None

    def close(self):
        DAQmxErrChk(api.DAQmxClearTask(self._taskHandle))
        return None

def DAQmxErrChk(err_code):
    if err_code != 0:
        num_bytes = api.DAQmxGetExtendedErrorInfo(ctypes.c_void_p(0), 0)
        print "Error message from NI DAQ: (", num_bytes, "bytes )"
        errBuff = numpy.ctypeslib.as_ctypes(
            numpy.zeros(num_bytes, dtype=numpy.byte))
        api.DAQmxGetExtendedErrorInfo(errBuff, num_bytes)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            print numpy.ctypeslib.as_array(errBuff).tostring()
        raise UserWarning("NI DAQ error code: %i"%(err_code))

def soft_triangle(points_per_period, linear_fraction=.66, repetitions=1):
    points_per_period = int(numpy.round(0.5 * points_per_period))
    if linear_fraction < 0 or linear_fraction > 1:
        raise UserWarning("'linear_fraction' must be between 0 and 1")
    ##Velocity
    v = numpy.linspace(0, 1, points_per_period)
    up_points = int(numpy.round(0.5 * points_per_period * linear_fraction))
    transition_points = points_per_period - 2*up_points
    v[0:up_points] = 2.0 / points_per_period
    v[up_points:up_points + transition_points
      ] = numpy.linspace(
          2.0/points_per_period, -2.0/points_per_period, transition_points)
    v[up_points + transition_points:] = -2.0 / points_per_period
    v -= v.mean()
    v = numpy.hstack((v, -v))
    p = numpy.cumsum(v)
    p = numpy.tile(p, repetitions)
    return p

def square(points_per_period, delay_fraction=0.5, on_fraction = 0.5,
           repetitions=1):
    if on_fraction < 0 or on_fraction > 1:
        raise UserWarning("'on_fraction' must be between 0 and 1")
    if delay_fraction < 0 or delay_fraction > 1:
        raise UserWarning("'delay_fraction' must be between 0 and 1")
    a = numpy.zeros((points_per_period,))
    delay_points = int(numpy.round(points_per_period * delay_fraction))
    on_points = int(numpy.round(points_per_period * on_fraction))
    a[:on_points] = 1
    a = numpy.roll(a, delay_points)
    a = numpy.tile(a, repetitions)
    return a

if __name__ == '__main__':
    import time
##    import pylab
##    fig = pylab.figure()
##    pylab.plot(square(
##        points_per_period=500, delay_fraction=.2, on_fraction=0.5,
##        repetitions=2))
##    fig.show()

    points_per_period = 1000
    voltage = {}
##    from scipy.ndimage import gaussian_filter
##    voltage[0] = 0.0024 + 0.4*gaussian_filter(
##        square(points_per_period), sigma=points_per_period*.01, mode='wrap')
    voltage[0] = 0.0024 + 0.8*soft_triangle( #Galvo
        points_per_period, linear_fraction=0.66)
##    voltage[1] = 5 + 0.08*numpy.ones(points_per_period) #piezo
##    voltage[2] = voltage[0]
##    voltage[3] = voltage[0]
    repetitions = 50
    rate = 40000
    daq_card = DAQ(voltage, rate, repetitions)
    print "Scanning DAQ card..."
    print "Press Ctrl-C to cancel"
    try:
        while True:
            daq_card.scan(background=False)
    except KeyboardInterrupt:
        daq_card.close()
        print "Done scanning DAQ card"

##    for i in range(730, 10000, 2):
##        points_per_period = i
##        print "Points per period:", i
##        voltage = {}
##        voltage[0] = 2*soft_triangle(
##            points_per_period, linear_fraction=0.66)
##        voltage[1] = voltage[0]
##        voltage[2] = voltage[0]
##        voltage[3] = voltage[0]
##        repetitions = 1
##        rate = 29776
##        daq_card = DAQ(voltage, rate, repetitions)
##        print "Scanning DAQ card..."
##        print "Press Ctrl-C to cancel"
##        try:
##            while True:
##                daq_card.scan(background=False, verbose=False)
##        except KeyboardInterrupt:
##            daq_card.close()
##            print "Done scanning DAQ card"
