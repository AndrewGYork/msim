import time
import numpy as np
import wx
import wx.lib.agw.floatspin as FS
from daq import DAQ
from image_data_pipeline import Image_Data_Pipeline
import multiprocessing as mp
import logging

class ParentFrame(wx.Frame):
    def __init__(self, parent, id, title):
        wx.Frame.__init__(
            self, parent, id, title, wx.DefaultPosition, (300, 200))
        self.panel = wx.Panel(self, -1)

        vbox = wx.BoxSizer(wx.VERTICAL)
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        self.floatspin = FS.FloatSpin(
            self.panel, -1, pos=(50, 50), min_val=0, max_val=10,
            increment=0.1, value=5, agwStyle=FS.FS_CENTRE)
        self.floatspin.SetFormat("%f")
        self.floatspin.SetDigits(2)

        btn1 = wx.Button(self.panel, 7, 'Adjust')
        btn2 = wx.Button(self.panel, 8, 'Snap')
        btn3 = wx.Button(self.panel, 9, 'Close')

        self.Bind(wx.EVT_CLOSE, self.OnClose)
        btn1.Bind(wx.EVT_BUTTON, self.on_adjust)
        btn2.Bind(wx.EVT_BUTTON, self.on_snap)
        btn3.Bind(wx.EVT_BUTTON, self.OnClose)
        
        vbox.Add(self.floatspin, 1, wx.ALIGN_CENTRE | wx.ALL, 25)
        hbox.Add(btn1, 1, 10)
        hbox.Add(btn2, 1, 10)
        hbox.Add(btn3, 1, 10)
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

        self.idp = Image_Data_Pipeline(
            num_buffers=5,
            buffer_shape=(1, 2048, 2060)) ##256 or 2048, 2060
        self.exposure_time_microseconds = 15000
        """
        Rep rate of camera is dictated by rep rate of the wheel. Exposure
        time of the camera has to be 20 microseconds shorter than the
        rep time of the camera or else the software can't keep up.
        """
        self.idp.camera.commands.send(
            ('apply_settings',
             {'trigger': 'external trigger/software exposure control',
              'region_of_interest': (-1, -1, 10000, 10000),##897, 1152
              'exposure_time_microseconds': self.exposure_time_microseconds}))
        print "Camera response:", self.idp.camera.commands.recv()
        self.idp.camera.commands.send(('set_timeout', {'timeout': 1}))
        print "Camera timeout:", self.idp.camera.commands.recv(), "s"
        self.idp.camera.commands.send(('set_preframes', {'preframes': 0}))
        print "Camera preframes:", self.idp.camera.commands.recv()
        self.idp.set_display_intensity_scaling(scaling='autoscale')
        print self.idp.get_display_intensity_scaling()

        self.pending_snaps = 0

        self.scale_frame_open = False

        self.initialize_daq()

    def OnAbout(self, e):
        dlg = wx.MessageDialog( self, "The fastest motherfuckers in the West",
                                "About Microscope Control", wx.OK)
        dlg.ShowModal() # Show it
        dlg.Destroy() # finally destroy it when finished.

    def OnScale(self, e):
        if not self.scale_frame_open:
            self.child = IntensityScaleFrame(self)
            self.child.Show()
            self.scale_frame_open = True

    def on_adjust(self, event):
        change_voltage = self.floatspin.GetValue()
        print change_voltage
        self.daq.voltage[:, 2] = change_voltage
        print self.daq.voltage[:, 2]

    def on_snap(self, event):
        print self.idp.check_children()
        self.idp.collect_data_buffers()
        if len(self.idp.idle_data_buffers) > 4:
            self.pending_snaps += 1
            self.idp.load_data_buffers(1)
        else:
            print "Not enough buffers available"
        if self.scale_frame_open: #Eventually shift responsiblilty to a timer
            display_scaling = self.idp.get_display_intensity_scaling()
            self.child.min.SetValue(
                str(display_scaling[1]))
            self.child.max.SetValue(
                str(display_scaling[2]))
        
    
    def OnClose(self, event):
        self.daq_timer.Stop()
        self.daq.stop_scan()
        self.daq.close()
        self.idp.close()
        print "DAQ Closing"
        self.Destroy()

    def on_daq_timer(self, event):
##        this_time = time.clock()
##        print "Interval:", this_time - self.last_daq_time
##        self.last_daq_time = this_time
        which_facet = 0
        clean_me = False
        while self.pending_snaps > 0:
            start_point = self.daq.perpendicular_facet_times[which_facet]
            print "which facet"
            print which_facet + 15
            print
            print "daq point"
            print self.daq.perpendicular_facet_times[which_facet+15]
            print
            print "last facet entry"
            print self.daq.perpendicular_facet_times[-1]
            """
            Random "useful" code sneepet:
            start_point += np.ceil((self.exposure_time_microseconds + 20)
                                   * self.daq.rate * 1e-6)

            Trigger the camera:
            -10 is for camera jitter
            """
            self.daq.voltage[start_point - 10 : start_point + 200, 4] = 3
            """
            Trigger the laser
            """
            self.daq.voltage[start_point, 6] = 10
            self.daq.voltage[start_point, 7] = 10
            """
            Wiggle the murrrrcle
            """
            num_periods = 3
            daq_timepoints_per_period = 100
            amplitude_volts = 0.01
            x = np.linspace(
                0, 2*np.pi*num_periods, num_periods * daq_timepoints_per_period)
            self.daq.voltage[start_point + 5000:start_point + 5000 + x.size, 3
                             ] = amplitude_volts * np.sin(x)

            
            which_facet += 30 #One wheel rotation maps onto one camera exposure
            self.pending_snaps -= 1
            clean_me = True
            print "OH SNAP!"
            
        self.daq.write_voltage()
        
        if clean_me:
            self.daq.voltage[:, 3] = 0
            self.daq.voltage[:, 4] = 0
            self.daq.voltage[:, 6] = 0
            self.daq.voltage[:, 7] = 0            

    def initialize_daq(self):
        rotations_per_second = 150
        facets_per_rotation = 10
        points_per_second = 500000

        """
        This logic assumes we can get away with an integer number of
        triggers per write; if we end up using a mirror with an odd
        number of sides, or if the mirror isn't perfectly regular, we
        might have to always use an integer number of rotations per
        write, not an integer number of triggers per write.
        """
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
        points_per_trigger = int(points_per_facet *
                                 facets_per_rotation *
                                 (1.0 / triggers_per_rotation))
        print "Actual points per rotation:",
        print points_per_trigger * triggers_per_rotation
        print "Actual points per facet:", (points_per_trigger *
                                           triggers_per_rotation *
                                           (1.0 / facets_per_rotation))
        print
        print "Desired rotations per second:", rotations_per_second
        rotations_per_second = (
            points_per_second *
            (1.0 / (points_per_trigger * triggers_per_rotation)))
        print "Actual rotations per second:", rotations_per_second
        print 
        points_per_write = points_per_second // 3
        print "Desired write length:", points_per_write
        rotations_per_write = points_per_write * 1.0 / (points_per_trigger *
                                                        triggers_per_rotation)
        rotations_per_write = int(round(rotations_per_write))
        points_per_write = (points_per_trigger *
                            triggers_per_rotation *
                            rotations_per_write)
        print "Actual write length:", points_per_write
        print "Rotations per write:", rotations_per_write
        triggers_per_write = triggers_per_rotation * rotations_per_write
        print "Triggers per write:", triggers_per_write
        print
        self.daq = DAQ(rate=points_per_second, write_length=points_per_write)

        wheel_signal = np.zeros(self.daq.write_length, dtype=np.float64)
        for i in range(triggers_per_write):
            start = i * points_per_trigger
            stop = start + points_per_trigger // 2
            wheel_signal[start:stop] = 6
        wheel_brake_signal = np.zeros(self.daq.write_length, dtype=np.float64)

        laser_signal = np.zeros(self.daq.write_length, dtype=np.float64)
        laser_duration = 1
        print "Laser duration:", laser_duration * 1.0 / points_per_second,
        print "seconds"
        ##Positive is up lag = 65 for 150 rps
        laser_lag = int(np.ceil((10404.0/rotations_per_second) - 5.30))
        self.daq.perpendicular_facet_times = []
        for i in range(rotations_per_write):
            for n in range(10):
                start = (i * points_per_trigger * triggers_per_rotation +
                         n * points_per_facet + 
                         laser_lag)
                self.daq.perpendicular_facet_times.append(start)
                stop = start + laser_duration
                ##laser_signal[start:stop] = 10

        voltage = np.zeros_like(self.daq.voltage)
        voltage[:, 0] = wheel_signal
        voltage[:, 1] = wheel_brake_signal
        voltage[:, 2] = 5 #focusing objective
        voltage[:, 3] = 0 #murrrcle
        voltage[:, 4] = 0 #camera trigger
        voltage[:, 6] = laser_signal
        voltage[:, 7] = laser_signal
        self.daq.set_voltage(voltage)
        self.seconds_per_write = self.daq.write_length * 1.0 / self.daq.rate
        print "Seconds per write:", self.seconds_per_write

        TIMER_ID = 100
        self.daq_timer = wx.Timer(self.panel, TIMER_ID)
        self.daq_timer.Start(round(self.seconds_per_write * 1000 * 0.95))
        wx.EVT_TIMER(self.panel, TIMER_ID, self.on_daq_timer)
        self.last_daq_time = 0
        self.daq.scan()

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
        self.min.Bind(wx.EVT_SET_FOCUS, self.onFocus)
        self.min.Bind(wx.EVT_KILL_FOCUS, self.onSet)
        self.min.Bind(wx.EVT_CHAR_HOOK, self.onKey)
        hbox.Add(self.min, 1, wx.ALIGN_CENTRE, 30)
        
        self.max = wx.TextCtrl(self.panel, -1,
                                str(self.display_scaling[2]),
                                size=(100, 25),
                                style=box_style)
        self.max.Bind(wx.EVT_SET_FOCUS, self.onFocus)
        self.max.Bind(wx.EVT_KILL_FOCUS, self.onSet)
        self.max.Bind(wx.EVT_CHAR_HOOK, self.onKey)
        hbox.Add(self.max, 1, wx.ALIGN_CENTRE, 30)
        
        hbox.Add(self.btn_set, 1, wx.ALIGN_CENTRE, 30)
        vbox.Add(hbox, 1, wx.ALIGN_CENTRE, 30)
        vbox.Add((-1, 25))
        
        self.Bind(wx.EVT_COMBOBOX, self.onComboBox, self.cb1)

        self.panel.SetSizer(vbox)
        
        self.Bind(wx.EVT_CLOSE, self.onClose)

    def onFocus(self, evt):
        pass
    
    def onKill(self, evt):
        print "KILL"

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
    
    def onClose(self, evt):
        self.Destroy()
        self.parent.scale_frame_open = False

if __name__ == '__main__':
    app = wx.App(0)
    frame = ParentFrame(None, -1, 'Microscope Control')
    frame.Show(True)
    frame.Centre()
    app.MainLoop()
    print "Done"
