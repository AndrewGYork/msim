import time
import sys
import ctypes
import warnings
import Queue
import multiprocessing as mp
import numpy as np

"""
Requires nicaiu.dll to be in the same directory, or located in the
os.environ['PATH'] search path.

If you get an error, read NIDAQmx.h to decypher it.
"""

api = ctypes.cdll.LoadLibrary("nicaiu")
log = mp.get_logger()
info = log.info
debug = log.debug
if sys.platform == 'win32':
    clock = time.clock
else:
    clock = time.time

class DAQ_with_queue:
    def __init__(
        self,
        num_channels=8,
        num_immutable_channels=0,
        default_voltage=None,
        rate=1e5,
        regenerate=False,
        write_length=10000):
        """
        Expected use pattern:
         *Initialize
         *Child process plays default voltages on repeat unless told otherwise
         *Use send_voltage() to load voltages to the child process, and
         play_voltage() to play loaded voltages one or more times, as
         desired
         *Close
        """
        self.rate = rate
        self.write_length = write_length
        self.num_channels = num_channels
        """
        It's often useful to force the last few channels to always be
        the default voltages
        """
        self.num_immutable_channels = num_immutable_channels
        self.num_mutable_channels = (self.num_channels -
                                     self.num_immutable_channels)        
        self.input_queue = mp.Queue()
        self.commands, self.child_commands = mp.Pipe()
        self.child = mp.Process(
            target=DAQ_child_process,
            args=(self.child_commands,
                  self.input_queue,
                  num_channels,
                  num_immutable_channels,
                  default_voltage,
                  rate,
                  write_length),
            name='DAQ')
        self.child.start()
        self.sent_voltages = {}
        return None

    def send_voltage(self, voltage, name='voltage'):
        """
        Takes an arbitrary voltage from the parent process, chews it
        into write_length pieces, and spits it to the child, padded as
        neccesary.
        """
        if voltage.shape[1] != self.num_mutable_channels:
            raise UserWarning(
                "%i Mutable channels selected," +
                " but this voltage has %i channels."%(
                    self.num_mutable_channels, voltage.shape[1]))
        if voltage.min() < -10 or voltage.max() > 10:
            raise UserWarning("Voltage must be between -10 and 10 V")
        timepoints = voltage.shape[0]
        closest_available_timepoints = int(
            self.write_length *
            np.ceil(timepoints * 1.0 /
                    self.write_length))
        if closest_available_timepoints > timepoints:
            temp_voltage = np.zeros(
                (closest_available_timepoints, self.num_mutable_channels),
                dtype=np.float64)
            temp_voltage[:timepoints, :self.num_mutable_channels] = voltage
            voltage = temp_voltage
        voltage = voltage.reshape(
            closest_available_timepoints // self.write_length, #num write lengths
            self.write_length,
            self.num_mutable_channels)
        self.input_queue.put((name, voltage))
        self.commands.send(('load_input_queue', {'name': name}))
        self.sent_voltages[name] = {
            'timepoints': timepoints,
            'closest_available_timepoints': closest_available_timepoints}
        return None

    def play_voltage(self, voltage_name='voltage'):
        self.commands.send(('play_voltage', {'name': voltage_name}))
        return None

    def set_default_voltage(
        self, voltage, channel, voltage_name='default'):
        self.commands.send(('set_default_voltage', {'name': voltage_name,
                                                    'channel': channel}))
        self.input_queue.put((voltage_name, voltage))
        return None

    def roll_voltage(self, voltage_name='voltage', channel=0, roll_pixels=0):
        self.commands.send((
            'roll_voltage',
            {'name': voltage_name,
             'channel': channel,
             'pixels_to_roll': roll_pixels}))
        return None

    def get_pad_points(self, voltage_name):
        """
        Returns how many timepoints were used to pad a give waveform
        to fit into an integer number of write_lengths.
        """
        return (
            self.sent_voltages[voltage_name]['closest_available_timepoints'] -
            self.sent_voltages[voltage_name]['timepoints'])
    
    def close(self):
        self.commands.send(('quit', {}))
        self.child.join()
        return None

def DAQ_child_process(
    commands,
    input_queue,
    num_channels,
    num_immutable_channels,
    default_voltage,
    rate,
    write_length):
    loaded_signals = {}
    daq = DAQ(num_channels=num_channels,
              default_voltage=default_voltage,
              rate=rate,
              write_length=write_length)
    num_mutable_channels = num_channels - num_immutable_channels
    daq.scan()
    while True:
        write_default = True
        if commands.poll():
            cmd, args = commands.recv()
            info("Command received: " + cmd)
            if cmd == 'load_input_queue':
                name = args['name']
                queue_name, signal = input_queue.get()
                assert name == queue_name
                assert signal.shape[2] == num_mutable_channels
                loaded_signals[name] = signal
                continue #Too fragile? How long does it take to load input?
            elif cmd == 'play_voltage':
                info("Playing signal:" + args['name'])
                write_this_signal = loaded_signals[args['name']]
                write_default = False
            elif cmd == 'set_default_voltage':
                name, channel = args['name'], args['channel']
                info("Setting new default voltage" +
                     " for channel %i: "%(channel) + name)
                queue_name, new_default = input_queue.get()
                assert name == queue_name
                assert new_default.size == write_length
                assert channel in range(num_mutable_channels)
                """
                Write the old defaults, then an interpolating linker,
                then the new defaults:
                """
                daq.write_voltage(write_default=True) #Old defaults
                daq.default_voltage[:, channel] = np.linspace(
                    daq.default_voltage[-1, channel],
                    new_default[0],
                    write_length)
                daq.write_voltage(write_default=True) #Linker
                daq.default_voltage[:, channel] = new_default
                daq.write_voltage(write_default=True) #New defaults
            elif cmd == 'roll_voltage':
                info("Rolling signal:" + args['name'])
                signal = loaded_signals[args['name']]
                channel_to_roll = args['channel']
                pixels_to_roll = args['pixels_to_roll']
                signal_to_roll = signal.reshape(
                    signal.shape[0] *
                    signal.shape[1],
                    signal.shape[2])
                if pixels_to_roll > 0:
                    signal_to_roll[pixels_to_roll:, channel_to_roll] = (
                        signal_to_roll[:-1 * pixels_to_roll, channel_to_roll])
                    signal_to_roll[:pixels_to_roll, channel_to_roll] = 0
                elif pixels_to_roll < 0:
                    signal_to_roll[:pixels_to_roll, channel_to_roll] = (
                        signal_to_roll[-pixels_to_roll:, channel_to_roll])
                    signal_to_roll[pixels_to_roll:, channel_to_roll] = 0
                loaded_signals[args['name']] = signal_to_roll.reshape(
                    signal.shape[0],
                    signal.shape[1],
                    signal.shape[2])
            elif cmd == 'quit':
                break

        if write_default:
            daq.write_voltage(write_default=True)
        else:
            for which_write_length in range(write_this_signal.shape[0]):
                """
                We only want to change the mutable channels, we want
                to leave the immutable channels alone, so we bypass
                daq.set_voltage() and edit daq.voltage directly:
                """
                daq.voltage[:, :num_mutable_channels
                            ] = write_this_signal[which_write_length, :, :]
                daq.write_voltage(verbose=False)
    info("Stopping scan")
    daq.close()

class DAQ:
    def __init__(
        self,
        num_channels=8,
        default_voltage=None,
        rate=1e5,
        regenerate=False,
        write_length=10000,
        ):
        print "Opening DAQ card..."
        print "DAQ card open."
        if default_voltage == None:
            self.default_voltage = np.zeros(
                (write_length, num_channels), dtype=np.float64)
        else:
            assert default_voltage.shape == (write_length, num_channels)
            self.default_voltage = default_voltage
        self.voltage = self.default_voltage.copy()
        self.write_length = write_length
        self.num_channels = num_channels
        self.taskHandle = ctypes.c_void_p(0)
        self.num_points_written = ctypes.c_ulong(0)

        DAQmxErrChk(api.DAQmxCreateTask("", ctypes.byref(self.taskHandle)))
        DAQmxErrChk(api.DAQmxCreateAOVoltageChan(
            self.taskHandle,
            "Dev1/ao0:%i"%(self.num_channels - 1),
            "",
            ctypes.c_double(-10.0), #Minimum voltage
            ctypes.c_double(10.0), #Maximum voltage
            10348, #DAQmx_Val_Volts; don't question it!
            ctypes.c_void_p(0), #NULL
            ))
        print "DAQ initialized"

        self.set_rate(rate)
        self.set_regeneration(regenerate)
        self.set_output_buffer_size(2 * write_length)
                  
        """
        We need to fill up the buffer anyway, so we can call
        self.scan() without crashing immediately. Might as well use
        these first two writes to smoothly ramp from zero volts to the
        default voltages:
        """
        for start, finish in ((0, 0.5), (0.5, 1)):
            for chan in range(self.num_channels):
                self.voltage[:, chan] = np.linspace(
                    start * self.default_voltage[0, chan],
                    finish * self.default_voltage[0, chan],
                    self.write_length)
            self.write_voltage()
        self.voltage[:] = self.default_voltage
        return None

    def set_rate(self, rate):
        self.rate = rate
        DAQmxErrChk(api.DAQmxCfgSampClkTiming(
            self.taskHandle,
            ctypes.c_void_p(0),#NULL, to specify onboard clock for timing
            ctypes.c_double(self.rate),
            10280, #DAQmx_Val_Rising, doesn't matter
            10123, #DAQmx_Val_ContSamps (Run continuous)
            2 * self.write_length))
        print "DAQ card scan rate set to", self.rate, "points per second"
        return None

    def set_regeneration(self, allow=True):
        """
        Disable signal regeneration
        """
        if allow:
            val = 10097 #DAQmx_Val_AllowRegen
        else:
            val = 10158 #DAQmx_Val_DoNotAllowRegen
        DAQmxErrChk(api.DAQmxSetWriteAttribute(
            self.taskHandle,
            5203, #DAQmx_Write_RegenMode
            val,
            ))
        print "DAQ card regeneration mode set to:", allow
        return None

    def set_output_buffer_size(self, size):
        assert size % self.write_length == 0
        self.output_buffer_size = size
        DAQmxErrChk(api.DAQmxCfgOutputBuffer(self.taskHandle, size))
        print "DAQ output buffer enlarged to:", size
        return None

    def set_voltage(self, voltage, verbose=False):
        assert self.voltage.shape == voltage.shape
        self.voltage[:] = voltage
        if verbose:
            print "Voltage set."
        return None

    def write_voltage(self, write_default=False, verbose=False):
        if write_default:
            voltage = self.default_voltage
        else:
            voltage = self.voltage
        DAQmxErrChk(api.DAQmxWriteAnalogF64(
            self.taskHandle,
            self.write_length,
            0,
            ctypes.c_double(10.0), #Timeout for writing.
            1, #DAQmx_Val_GroupByScanNumber (interleaved)
            np.ctypeslib.as_ctypes(voltage),
            ctypes.byref(self.num_points_written),
            ctypes.c_void_p(0)
            ))
        if verbose:
            print self.num_points_written.value,
            print "points written to each DAQ channel."
        return None

    def scan(self, verbose=True):
        if verbose:
            print "Scanning voltage..."
        DAQmxErrChk(api.DAQmxStartTask(self.taskHandle))
        return None

    def stop_scan(self):
        DAQmxErrChk(api.DAQmxStopTask(self.taskHandle))
        print "Done scanning"
        return None

    def clear(self):
        DAQmxErrChk(api.DAQmxClearTask(self.taskHandle))
        return None

    def close(self):
        """
        If we just call "clear", the DAQ voltages stop at a random
        point, and this is pretty lame. Best to write a rampdown from
        default voltages, and then some zeros, so we're guaranteed to
        stop at zero output voltage.

        First, write the rampdown:
        """
        for start, finish in ((1, 0.5), (0.5, 0)):
            for chan in range(self.num_channels):
                self.voltage[:, chan] = np.linspace(
                    start * self.default_voltage[-1, chan],
                    finish * self.default_voltage[-1, chan],
                    self.write_length)
            self.write_voltage()
        """
        Next, fill the output buffer with zeros:
        """
        self.voltage.fill(0)
        for i in range(4): #Seriously? 4? Yeah, 4. WTF? I don't understand why.
            self.write_voltage()
        """
        Now, we can stop the DAQ without drama:
        """
        self.stop_scan()
        self.clear()
        return None

def DAQmxErrChk(err_code):
    if err_code != 0:
        num_bytes = api.DAQmxGetExtendedErrorInfo(ctypes.c_void_p(0), 0)
        print "Error message from NI DAQ: (", num_bytes, "bytes )"
        errBuff = np.ctypeslib.as_ctypes(
            np.zeros(num_bytes, dtype=np.byte))
        api.DAQmxGetExtendedErrorInfo(errBuff, num_bytes)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            print np.ctypeslib.as_array(errBuff).tostring()
        raise UserWarning("NI DAQ error code: %i"%(err_code))

if __name__ == '__main__':
    import logging
    logger = mp.log_to_stderr()
    logger.setLevel(logging.INFO)
    
##    """
##    Test basic functionality of the DAQ object
##    """
##    default_voltage = 0.1 * np.ones((1250, 8))
##    default_voltage[0:100, 0] = 0.2
##    daq = DAQ(
##        rate=10000,
##        write_length=default_voltage.shape[0],
##        num_channels=default_voltage.shape[1],
##        default_voltage=default_voltage)
##    daq.scan(verbose=True)
##    while True:
##        try:
##            daq.write_voltage()
##        except KeyboardInterrupt:
##            break
##    print "Closing daq..."
##    daq.close()
##    raw_input("Hit Enter to test the DAQ_with_queue object...")


    daq = DAQ_with_queue(
        num_channels=8,
        num_immutable_channels=1,)
    print "Waiting a bit..."
    time.sleep(1)
    print "Sending signal..."
    sig = np.zeros((10000, 7), dtype=np.float64)
    sig[4500:5500, 0] = 1
    sig[4500:5500, 1] = 1
    daq.send_voltage(sig, 'sig0')
    daq.play_voltage('sig0')
    time.sleep(0.5)
    daq.roll_voltage(voltage_name='sig0', channel=0, roll_pixels=0)
    daq.play_voltage('sig0')
    print "Done sending."
    time.sleep(1)
    daq.set_default_voltage(voltage=np.ones((1, daq.write_length)),
                            channel=1)
    time.sleep(3)
    daq.close()
    raw_input()

##    """
##    Test basic functionality of the 'DAQ_with_queue' object
##    """
##    daq = DAQ_with_queue(
##        num_channels=8,
##        num_immutable_channels=1,)
##    print "Waiting a bit..."
##    time.sleep(1)
##    print "Sending signal..."
##    sig = np.zeros((10000, 7), dtype=np.float64)
##    daq.send_voltage(sig, 'sig0')
##    daq.play_voltage('sig0')
##    print "Done sending."
##    print "Waiting a bit..."
##    time.sleep(1)
##    print "Sending several small signals..."
##    sig1 = 0.1 * np.ones((9000, 7), dtype=np.float64)
##    sig2 = 0.2 * np.ones((10000, 7), dtype=np.float64)
##    sig3 = 0.3 * np.ones((11000, 7), dtype=np.float64)
##    sig4 = 0.4 * np.ones((12000, 7), dtype=np.float64)
##    daq.send_voltage(sig1, 'sig1')
##    daq.send_voltage(sig2, 'sig2')
##    daq.send_voltage(sig3, 'sig3')
##    daq.send_voltage(sig4, 'sig4')
##    daq.play_voltage('sig1')
##    daq.play_voltage('sig2')
##    daq.play_voltage('sig3')
##    daq.play_voltage('sig4')
##    daq.play_voltage('sig0')
##    print "Done sending."
##    daq.close()
##    raw_input()
