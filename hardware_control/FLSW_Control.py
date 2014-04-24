import os
import time
import numpy as np
import wx
import wx.lib.agw.floatspin as FS
from daq import DAQ_with_queue
from image_data_pipeline import Image_Data_Pipeline
import multiprocessing as mp
import logging
from simple_tif import tif_to_array

class ParentFrame(wx.Frame):
    def __init__(self, parent, id, title):
        wx.Frame.__init__(
            self, parent, id, title, wx.DefaultPosition, (450, 200))
        self.panel = wx.Panel(self, -1)

        vbox = wx.BoxSizer(wx.VERTICAL)
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        self.floatspin = FS.FloatSpin(
            self.panel, -1, pos=(50, 50), min_val=0, max_val=10,
            increment=0.1, value=5, agwStyle=FS.FS_CENTRE)
        self.floatspin.SetFormat("%f")
        self.floatspin.SetDigits(2)

        btnAdjust = wx.Button(self.panel, 7, 'Adjust')
        btnSnap = wx.Button(self.panel, 8, 'Snap')
        btnClose = wx.Button(self.panel, 9, 'Close')
        btnCharacterize = wx.Button(self.panel, 10, 'Characterize')

        self.Bind(wx.EVT_CLOSE, self.OnClose)
        btnAdjust.Bind(wx.EVT_BUTTON, self.on_adjust)
        btnSnap.Bind(wx.EVT_BUTTON, self.on_snap)
        btnCharacterize.Bind(wx.EVT_BUTTON, self.on_characterize)
        btnClose.Bind(wx.EVT_BUTTON, self.OnClose)
        
        vbox.Add(self.floatspin, 1, wx.ALIGN_CENTRE | wx.ALL, 25)
        hbox.Add(btnAdjust, 1, 10)
        hbox.Add(btnSnap, 1, 10)
        hbox.Add(btnClose, 1, 10)
        hbox.Add(btnCharacterize, 1, 10)
        vbox.Add(hbox, 0, wx.ALIGN_CENTRE | wx.ALL, 10)
        self.panel.SetSizer(vbox)

        self.CreateStatusBar() 

        filemenu= wx.Menu()

        menuAbout = filemenu.Append(wx.ID_ABOUT, "&About",
                                    " Information about this program")
        menuExit = filemenu.Append(wx.ID_EXIT,"E&xit"," Terminate the program")

        imagemenu= wx.Menu()

        menuScale = imagemenu.Append(
            wx.ID_ANY, "&Scale", " Adjust the scaling of the image")

        menuBar = wx.MenuBar()
        menuBar.Append(filemenu,"&File")
        menuBar.Append(imagemenu, "&Image")
        self.SetMenuBar(menuBar)
        
        self.Bind(wx.EVT_MENU, self.OnAbout, menuAbout)
        self.Bind(wx.EVT_MENU, self.OnClose, menuExit)
        self.Bind(wx.EVT_MENU, self.OnScale, menuScale)
        
        logger = mp.log_to_stderr()
        logger.setLevel(logging.INFO)

        self.initialize_image_data_pipeline()
        self.initialize_daq()
        self.initialize_snap()
        self.initialize_characterize()

    def OnAbout(self, e):
        dlg = wx.MessageDialog( self, "The fastest motherfuckers in the West",
                                "About Microscope Control", wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def OnScale(self, e):
        try:
            """
            Does the scale frame already exist?
            """
            getattr(self.scale_frame, 'thisown')
        except (NameError, AttributeError):
            """
            The scale frame doesn't exist yet. Make it!
            """
            self.scale_frame = IntensityScaleFrame(self)
        self.scale_frame.Show(True)
        self.scale_frame.Iconize(False)
        self.scale_frame.Raise()

    def on_adjust(self, event):
        change_voltage_value = self.floatspin.GetValue()
        change_voltage = np.zeros((self.daq.write_length), dtype=np.float64)
        change_voltage[:] = change_voltage_value
        if change_voltage[0] > 0 and change_voltage[0] <10:
            self.daq.set_default_voltage(change_voltage, 3)

    def on_snap(self, event):
        print self.idp.check_children() #Eventually add this to a timer
        self.idp.collect_data_buffers()
        if len(self.idp.idle_data_buffers) > 0:
            self.idp.load_data_buffers(
                1, )#[{'outfile':'image_%06i.tif'%self.saved_files}])
            self.daq.play_voltage('snap')
            print "OH SNAP!"
            self.saved_files += 1
        else:
            print "Not enough buffers available"
##        if self.scale_frame_open: #Eventually shift responsiblilty to a timer
##            display_scaling = self.idp.get_display_intensity_scaling()
##            self.child.min.SetValue(
##                str(display_scaling[1]))
##            self.child.max.SetValue(
##                str(display_scaling[2]))
        
    def on_characterize(self, event):
        """
        Send a buffer (save to file)
        Play the 'characterize' waveform
        Roll one channel of the 'characterize' signal
        Repeat until the whooooole bottle
        """
        data_dir = os.path.join(os.getcwd(), 'characterization')
        if not os.path.exists(data_dir):
            os.mkdir(data_dir)
        saved_files = 0
        for i in range(self.characterization_points):
            status = self.idp.check_children()
            for k in sorted(status.keys()):
                if not status[k]:
                    print '*\n'*20
                    print k, status[k]
                    print '*\n'*20
            while len(self.idp.idle_data_buffers) < 1:
                self.idp.collect_data_buffers()
            self.idp.load_data_buffers(
                1, [{'outfile': os.path.join(
                    data_dir, 'image_%06i.tif'%saved_files)}])
            self.daq.play_voltage('characterize')
            print "OH CHARACTERIZE!"
            saved_files += 1
            self.daq.roll_voltage(voltage_name='characterize',
                                  channel=n2c['emission_scan'],
                                  roll_pixels=-2)
        return None
   
    def OnClose(self, event):
        self.daq.close()
        self.idp.close()
        print "DAQ Closing"
        self.Destroy()

    def initialize_characterize(self):
        """
        Create the murrrcle signal up here. All we care about is how
        many DAQ points long it is.
        """
##        num_periods = 4
##        daq_timepoints_per_period = 1500
##        amplitude_volts = 0.1
##        murrcle_signal = np.sin(np.linspace(
##            0, 2*np.pi*num_periods, num_periods * daq_timepoints_per_period))
##        murrcle_signal[:daq_timepoints_per_period] = 0
##        murrcle_signal[-daq_timepoints_per_period:] = 0
        murrcle_signal = np.zeros(20000, dtype=np.float64)
##        murrcle_signal[1000:1152] = 0.05
##        murrcle_signal[1152:-1000] = 0.1
##        murrcle_signal[1000:1005] = 0.3
        signal = 0.16 * tif_to_array(filename='test.tif').astype(np.float64)
        print "Signal min, signal max:", signal.min(), signal.max()
        print
        """
        Put this optimzed waveform into the larger array
        """
        murrcle_signal[:signal.size] = signal[:, 0, 0]
        print "signal size", signal.size
        """
        Smoothly drop the voltage to zero; hopefully this reduces ringing.
        """
        murrcle_signal[signal.size:2*(signal.size)
                       ] = np.linspace(signal[-1, 0, 0], 0, signal.size)
        print "last value for signal" , signal[-1, 0 , 0]
        print murrcle_signal[signal.size * 1.5]
        self.characterization_points = murrcle_signal.size

        delay_points = max( #Figure out the limiting factor
            murrcle_signal.size,
            1e-6 * self.get_camera_rolling_time_microseconds() * self.daq.rate)
        start_point_laser = (#Integer num of writes plus a perp facet time
            self.daq.perpendicular_facet_times[0] +
            self.daq.write_length * int(np.ceil(delay_points * 1.0 /
                                                self.daq.write_length)))
        assert (self.exposure_time_microseconds * 1e6 >=
                start_point_laser * 1.0 / self.daq.rate)
        voltage = np.zeros(((start_point_laser +  murrcle_signal.shape[0]),
                            self.daq.num_mutable_channels),
                           dtype=np.float64)
        ##objective voltage voltage
        
        """
        Trigger the camera
        """
        voltage[:self.daq.write_length//4, n2c['camera']] = 3
        """
        Trigger the laser
        """
        voltage[start_point_laser, n2c['488']] = 10
        voltage[start_point_laser, n2c['blanking']] = 10
        """
        Wiggle the murrrrcle
        """ 
        voltage[-murrcle_signal.size:, n2c['emission_scan']] = murrcle_signal
        self.daq.send_voltage(voltage, 'characterize')
        return None
    
    def initialize_snap(self):
        ##Assume full-frame camera operation, 10 ms roll time
        roll_time = int(np.ceil(self.daq.rate * 0.01))
        oh_snap_voltages = np.zeros(
            (self.daq.write_length  + roll_time, self.daq.num_mutable_channels),
            dtype=np.float64)

        ##objective stays at what it was
        objective_voltage = self.daq.default_voltages[0, n2c['objective']]
        oh_snap_voltages[:, n2c['objective']] = objective_voltage
        
        #Camera triggers at the start of a write
        oh_snap_voltages[:self.daq.write_length//4, n2c['camera']] = 3
        
        #AOTF fires on one perpendicular facet
        start_point_laser = (#Integer num of writes plus a perp facet time
            self.daq.perpendicular_facet_times[6] +
            self.daq.write_length * int(roll_time * 1.0 /
                                        self.daq.write_length))
        oh_snap_voltages[start_point_laser, n2c['488']] = 10
        oh_snap_voltages[start_point_laser, n2c['blanking']] = 10
        time.sleep(1)
        print oh_snap_voltages.shape
        self.daq.send_voltage(oh_snap_voltages, 'snap')
        return None

    def initialize_image_data_pipeline(self):
        self.idp = Image_Data_Pipeline(
            num_buffers=15,
            buffer_shape=(1, 256, 2060), ##256 or 2048, 2060
            camera_high_priority=True)
        desired_exposure_time_microseconds = 60000
        """
        Rep rate of camera is dictated by rep rate of the wheel. Exposure
        time of the camera has to be 20 microseconds shorter than the
        rep time of the camera or else the software can't keep up.
        """
        self.idp.camera.commands.send(
            ('apply_settings',
             {'trigger': 'external trigger/software exposure control',
              'region_of_interest': (-1, 897, 10000, 1152),##897, 1152
              'exposure_time_microseconds': desired_exposure_time_microseconds}
             ))
        camera_response = self.idp.camera.commands.recv()
        print "Camera response:", camera_response
        (trigger_mode,
         self.exposure_time_microseconds,
         self.region_of_interest,
         ) = camera_response
        self.idp.camera.commands.send(('set_timeout', {'timeout': 1}))
        print "Camera timeout:", self.idp.camera.commands.recv(), "s"
        self.idp.camera.commands.send(('set_preframes', {'preframes': 0}))
        print "Camera preframes:", self.idp.camera.commands.recv()
        self.idp.set_display_intensity_scaling(scaling='autoscale')
        print self.idp.get_display_intensity_scaling()
        self.saved_files = 0

    def get_camera_rolling_time_microseconds(self):
        """
        The pco edge 4.2 allows an asymmetric region-of-interest, but
        does this simply by acquiring a symmetric region-of-interest
        and cropping the data, so the rolling time is still the same
        as if you'd used a symmetric region of interest.
        """
        num_lines = max(2*self.region_of_interest[3] - 2048,
                        2048 - 2*(self.region_of_interest[1] - 1))
        seconds_per_line = 0.01007 * 1.0 / 2048. #10 ms for the full field
        return int(num_lines * seconds_per_line * 1e6)

    def initialize_daq(self):
        rotations_per_second = 150
        facets_per_rotation = 10
        points_per_second = 500000
        num_channels = 8

        triggers_per_rotation = 2
        triggers_per_second = triggers_per_rotation * rotations_per_second
        points_per_trigger = points_per_second * (1.0 / triggers_per_second)
        facets_per_second = rotations_per_second * facets_per_rotation
        points_per_facet = points_per_second * (1.0 / facets_per_second)
        print
        print "Desired points per rotation:",
        print points_per_trigger * triggers_per_rotation
        print "Desired points per facet:", points_per_facet
        points_per_facet = int(round(points_per_facet))
        points_per_trigger = int(points_per_facet * #Careful! (Odd-facet case)
                                 facets_per_rotation * 1.0 /
                                 triggers_per_rotation)
        print "Actual points per rotation:",
        print points_per_trigger * triggers_per_rotation
        print "Actual points per facet:", points_per_facet
        print
        print "Desired rotations per second:", rotations_per_second
        rotations_per_second = (
            points_per_second *
            (1.0 / (points_per_trigger * triggers_per_rotation)))
        print "Actual rotations per second:", rotations_per_second
        points_per_rotation = points_per_trigger * triggers_per_rotation
        print "Write length:", points_per_rotation
        print
        
        wheel_signal = np.zeros(points_per_rotation, dtype=np.float64)
        for i in range(triggers_per_rotation):
            start = i * points_per_trigger
            stop = start + points_per_trigger // 2
            wheel_signal[start:stop] = 6
        
        default_voltage = np.zeros(
            (points_per_rotation, num_channels), dtype=np.float64)

        default_voltage[:, n2c['488']] = 0
        default_voltage[:, n2c['561']] = 0
        default_voltage[:, n2c['blanking']] = 0
        default_voltage[:, n2c['objective']] = 5
        default_voltage[:, n2c['excitation_scan']] = 0
        default_voltage[:, n2c['emission_scan']] = 0
        default_voltage[:, n2c['camera']] = 0
        default_voltage[:, n2c['wheel']] = wheel_signal

        self.daq = DAQ_with_queue(num_immutable_channels=1,
                                  default_voltage=default_voltage,
                                  rate=points_per_second,
                                  write_length=points_per_rotation,
                                  high_priority=True)
        """
        Positive lag raises first wheel reflection, lag=65 for 150 rps
        Empirically determined!
        """
        perpendicular_lag = int(np.ceil((10404.0/rotations_per_second) - 5.0))
        self.daq.perpendicular_facet_times = []
        for facet in range(facets_per_rotation):
            self.daq.perpendicular_facet_times.append(
                facet * points_per_facet + perpendicular_lag)

        ##FIXME: Put this shit into an "alignment" panel
        """
        want continuous laser firing? try these lines.

        laser_signal = np.zeros((points_per_rotation), dtype=np.float64)
        laser_duration = 1
        for i in range(len(self.daq.perpendicular_facet_times)):
            place = self.daq.perpendicular_facet_times[i]
            laser_signal[place:place+laser_duration] = 10
        self.daq.set_default_voltage(laser_signal, 0)
        self.daq.set_default_voltage(laser_signal, 1)
        """
        
        self.seconds_per_write = self.daq.write_length * 1.0 / self.daq.rate
        print "Seconds per write:", self.seconds_per_write

class IntensityScaleFrame(wx.Frame):
    def __init__(self, parent):
        wx.Frame.__init__(
            self, parent, wx.ID_ANY, "Intensity Scale Control", size=(400, 225))
        self.parent = parent
        self.panel = wx.Panel(self)
        self.display_scaling = self.parent.idp.get_display_intensity_scaling()

        vbox = wx.BoxSizer(wx.VERTICAL)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        vbox.Add((-1, 25))
        
        scaling_options = ['Linear',
                           'Autoscale (min/max)',
                           'Autoscale (median filter)']
        st1 = wx.StaticText(self.panel, label="Display intensity scaling:")
        vbox.Add(st1, 1, wx.ALIGN_CENTRE, 30)
        vbox.Add((-1, 25))

        self.cb1 = wx.ComboBox(self.panel, size=(155, -1),
                               choices=scaling_options,
                               style=wx.CB_READONLY)
        vbox.Add(self.cb1, 1, 25)
        vbox.Add((-1, 25))

        self.btn_set = wx.Button(self.panel, 9, 'Set Linear Scale')
        self.btn_set.Bind(wx.EVT_BUTTON, self.onSet)

        if self.display_scaling[0] == 'linear':
            self.cb1.SetValue('Linear')
            box_style = wx.TE_LEFT
        elif self.display_scaling[0] == 'autoscale':
            self.cb1.SetValue('Autoscale (min/max)')
            box_style = wx.TE_READONLY
            self.btn_set.Disable()
        elif self.display_scaling[0] == 'median_filter_autoscale':
            self.cb1.SetValue('Autoscale (median filter)')
            box_style = wx.TE_READONLY
            self.btn_set.Disable()

        self.min = wx.TextCtrl(self.panel, -1,
                                str(self.display_scaling[1]),
                                size=(100, 25),
                                style=box_style)
        self.min.Bind(wx.EVT_KILL_FOCUS, self.onSet)
        self.min.Bind(wx.EVT_CHAR_HOOK, self.onKey)
        hbox.Add(self.min, 1, wx.ALIGN_CENTRE, 30)
        
        self.max = wx.TextCtrl(self.panel, -1,
                                str(self.display_scaling[2]),
                                size=(100, 25),
                                style=box_style)
        self.max.Bind(wx.EVT_KILL_FOCUS, self.onSet)
        self.max.Bind(wx.EVT_CHAR_HOOK, self.onKey)
        hbox.Add(self.max, 1, wx.ALIGN_CENTRE, 30)
        
        hbox.Add(self.btn_set, 1, wx.ALIGN_CENTRE, 30)
        vbox.Add(hbox, 1, wx.ALIGN_CENTRE, 30)
        vbox.Add((-1, 25))
        
        self.Bind(wx.EVT_COMBOBOX, self.onComboBox, self.cb1)

        self.panel.SetSizer(vbox)
        
        self.Bind(wx.EVT_CLOSE, self.onClose)

    def onKey(self, evt):
        if evt.GetKeyCode() == wx.WXK_RETURN: # Is the key ENTER?
            scaling = self.cb1.GetValue()
            if scaling == 'Linear':  
                sane_min, sane_max = True, True #optimism
                print "on_set"
                print evt.GetEventObject()
                min_value, max_value = self.min.GetValue(), self.max.GetValue()
                try:
                    min_value = int(min_value)
                except ValueError:
                    sane_min = False
                try:
                    max_value = int(max_value)
                except ValueError:
                    sane_max = False

                if sane_min and sane_max:
                    biggest_possible = 2**16 - 1
                    if min_value < 0:
                        min_value = 0
                    if min_value > biggest_possible - 1:
                        min_value = biggest_possible - 1
                    if max_value < min_value:
                        max_value = min_value + 1
                    if max_value > biggest_possible:
                        max_value = biggest_possible
                    scaling = self.parent.idp.set_display_intensity_scaling(
                        'linear', min_value, max_value)
                    print scaling
                else:
                    print "SORRY IS THAT TOO LOGIC FOR YOU?!?!"
                    scaling = self.parent.idp.get_display_intensity_scaling()
                self.min.SetValue(str(scaling[1]))
                self.max.SetValue(str(scaling[2]))
        else:
            evt.Skip()
    
    def onComboBox(self, evt):
        scaling = self.cb1.GetValue()
        if scaling == 'Linear':
            self.parent.idp.set_display_intensity_scaling(
                'linear', self.display_scaling[1], self.display_scaling[2])
            self.min.SetEditable(True)
            self.max.SetEditable(True)
            self.btn_set.Enable()
        elif scaling == 'Autoscale (min/max)':
            self.parent.idp.set_display_intensity_scaling('autoscale')
            self.min.SetEditable(False)
            self.max.SetEditable(False)
            self.btn_set.Disable()
        elif scaling == 'Autoscale (median filter)':
            self.parent.idp.set_display_intensity_scaling(
                'median_filter_autoscale')
            self.min.SetEditable(False)
            self.max.SetEditable(False)
            self.btn_set.Disable()
        else:
            raise UserWarning("WTF dude")
        self.display_scaling = self.parent.idp.get_display_intensity_scaling()
        self.min.SetValue(str(self.display_scaling[1]))
        self.max.SetValue(str(self.display_scaling[2]))
        print self.display_scaling
        
    def onSet(self, evt):
        scaling = self.cb1.GetValue()
        if scaling == 'Linear':  
            sane_min, sane_max = True, True #optimism
            print "on_set"
            print evt.GetEventObject()
            min_value, max_value = self.min.GetValue(), self.max.GetValue()
            try:
                min_value = int(min_value)
            except ValueError:
                sane_min = False
            try:
                max_value = int(max_value)
            except ValueError:
                sane_max = False

            if sane_min and sane_max:
                biggest_possible = 2**16 - 1
                if min_value < 0:
                    min_value = 0
                if min_value > biggest_possible - 1:
                    min_value = biggest_possible - 1
                if max_value < min_value:
                    max_value = min_value + 1
                if max_value > biggest_possible:
                    max_value = biggest_possible
                scaling = self.parent.idp.set_display_intensity_scaling(
                    'linear', min_value, max_value)
                print scaling
            else:
                print "SORRY IS THAT TOO LOGIC FOR YOU?!?!"
                scaling = self.parent.idp.get_display_intensity_scaling()
            self.min.SetValue(str(scaling[1]))
            self.max.SetValue(str(scaling[2]))
            evt.Skip()
    
    def onClose(self, evt):
        self.Destroy()
        del self.parent.scale_frame
"""
Convert names to numerical channels for the DAQ with this dict:
"""
n2c = {
    '488': 0,
    '561': 1,
    'blanking': 2,
    'objective': 3,
    'excitation_scan': 4,
    'emission_scan': 5,
    'camera': 6,
    'wheel': 7}

if __name__ == '__main__':
    app = wx.App(0)
    frame = ParentFrame(None, -1, 'Microscope Control')
    frame.Show(True)
    frame.Centre()
    x, y = frame.GetPosition()
    frame.Move((x//2, y))
    app.MainLoop()
    print "Done"
