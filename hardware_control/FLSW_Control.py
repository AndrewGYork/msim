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
            self, parent, id, title, wx.DefaultPosition, (500, 300))
        self.panel = wx.Panel(self, -1)

        vbox = wx.BoxSizer(wx.VERTICAL)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox_adjust_objective = wx.BoxSizer(wx.HORIZONTAL)
        hbox_adjust_excitation_galvo = wx.BoxSizer(wx.HORIZONTAL)
        hbox_adjust_illumination = wx.BoxSizer(wx.HORIZONTAL)

        self.floatspin_objective = FS.FloatSpin(
            self.panel, -1, pos=(0, 0), min_val=0, max_val=10,
            increment=0.1, value=5, agwStyle=FS.FS_CENTRE)
        self.floatspin_objective.SetFormat("%f")
        self.floatspin_objective.SetDigits(2)

        self.floatspin_excitation_galvo = FS.FloatSpin(
            self.panel, -1, pos=(0, 0), min_val=-9.99, max_val=9.99,
            increment=0.1, value=0, agwStyle=FS.FS_CENTRE)
        self.floatspin_excitation_galvo.SetFormat("%f")
        self.floatspin_excitation_galvo.SetDigits(2)

        self.floatspin_length = FS.FloatSpin(
            self.panel, -1, pos=(0, 0), min_val=0, max_val=250,
            increment=1, value=1, agwStyle=FS.FS_CENTRE)
        self.floatspin_length.SetFormat("%f")
        self.floatspin_length.SetDigits(1)

        self.floatspin_offset = FS.FloatSpin(
            self.panel, -1, pos=(0, 0), min_val=-250, max_val=250,
            increment=1, value=0, agwStyle=FS.FS_CENTRE)
        self.floatspin_offset.SetFormat("%f")
        self.floatspin_offset.SetDigits(1)

        btnAdjust_Objective = wx.Button(self.panel, 7, 'Adjust Objective')
        btnAdjust_Excitation_Galvo = wx.Button(
            self.panel, 6, 'Adjust Excitation Galvo')
        st1 = wx.StaticText(self.panel, label="Length:")
        st2 = wx.StaticText(self.panel, label="Offset:")
        btnAdjust_Illumination = wx.Button(
            self.panel, 5, 'Adjust Illumination')
        self.illumination_length = 1
        self.illumination_offset = 0
        btnSnap = wx.Button(self.panel, 8, 'Snap')
        btnClose = wx.Button(self.panel, 9, 'Close')
        btnCharacterize = wx.Button(self.panel, 10, 'Characterize')
        btnVolume = wx.Button(self.panel, 11, 'Volume')

        self.Bind(wx.EVT_CLOSE, self.OnClose)
        btnAdjust_Objective.Bind(wx.EVT_BUTTON, self.on_adjust_objective)
        btnAdjust_Illumination.Bind(wx.EVT_BUTTON, self.on_adjust_illumination)
        btnAdjust_Excitation_Galvo.Bind(wx.EVT_BUTTON, self.on_adjust_excitation_galvo)
        btnSnap.Bind(wx.EVT_BUTTON, self.on_snap)
        btnCharacterize.Bind(wx.EVT_BUTTON, self.on_characterize)
        btnClose.Bind(wx.EVT_BUTTON, self.OnClose)


        vbox.AddSpacer(25)
        hbox_adjust_illumination.Add(st1, 1, 25)
        hbox_adjust_illumination.Add(self.floatspin_length, 1, 25)
        hbox_adjust_illumination.Add(st2, 1, 25)
        hbox_adjust_illumination.Add(self.floatspin_offset, 1, 25)
        hbox_adjust_illumination.AddSpacer(15)
        hbox_adjust_illumination.Add(btnAdjust_Illumination, 1, 25)
        vbox.Add(hbox_adjust_illumination, 0, wx.ALIGN_CENTRE, 10)

        vbox.AddSpacer(15)
        hbox_adjust_objective.Add(self.floatspin_objective, 1, 25)
        hbox_adjust_objective.AddSpacer(15)
        hbox_adjust_objective.Add(btnAdjust_Objective, 1, 25)
        vbox.Add(hbox_adjust_objective, 0, wx.ALIGN_CENTRE, 10)
        vbox.AddSpacer(15)
        hbox_adjust_excitation_galvo.Add(self.floatspin_excitation_galvo, 1, 25)
        hbox_adjust_excitation_galvo.AddSpacer(15)
        hbox_adjust_excitation_galvo.Add(btnAdjust_Excitation_Galvo, 1, 25)
        vbox.Add(hbox_adjust_excitation_galvo, 0, wx.ALIGN_CENTRE, 10)
        vbox.AddSpacer(15)
        hbox.Add(btnVolume, 1, 10)
        hbox.AddSpacer(10)
        hbox.Add(btnSnap, 1, 10)
        hbox.AddSpacer(10)
        hbox.Add(btnCharacterize, 1, 10)
        hbox.AddSpacer(10)
        hbox.Add(btnClose, 1, 10)
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

    def on_adjust_illumination(self, event):
        change_length_value = self.floatspin_length.GetValue()
        change_offset_value = self.floatspin_offset.GetValue()
        if change_length_value >= 0 and change_length_value <250:
            self.illumination_length = change_length_value
            self.illumination_offset = change_offset_value
            print "offset", change_offset_value
            self.initialize_snap()

    def on_adjust_objective(self, event):
        change_voltage_value = self.floatspin_objective.GetValue()
        change_voltage = np.zeros((self.daq.write_length), dtype=np.float64)
        change_voltage[:] = change_voltage_value
        if change_voltage[0] > 0 and change_voltage[0] <10:
            self.daq.set_default_voltage(change_voltage, 3)
            self.initialize_snap()
            self.initialize_characterize()

    def on_adjust_excitation_galvo(self, event):
        change_voltage_value = self.floatspin_excitation_galvo.GetValue()
        change_voltage = np.zeros((self.daq.write_length), dtype=np.float64)
        change_voltage[:] = change_voltage_value
        if change_voltage[0] > -10 and change_voltage[0] <10:
            self.daq.set_default_voltage(change_voltage, 4)
            self.initialize_snap()
            self.initialize_characterize()

    def on_snap(self, event):
        print self.idp.check_children() #Eventually add this to a timer
        self.idp.collect_data_buffers()
        if len(self.idp.idle_data_buffers) > 0:
            self.idp.load_data_buffers(
                1, ) ##[{'outfile':'image_%06i.tif'%self.saved_files}])
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
        roll_pixels = 2
        characterize_pixels = 6000
        steps_per_rep = characterize_pixels // roll_pixels
        num_reps = 1
        for r in range(num_reps):
            for step in range(steps_per_rep):
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
                                      roll_pixels=-roll_pixels)
            """
            Clean up after ourselves
            """
            self.daq.roll_voltage(voltage_name='characterize',
                              channel=n2c['emission_scan'],
                              roll_pixels=steps_per_rep * roll_pixels)
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
##        impulse_strength = 1
##        num_periods = 4
##        daq_timepoints_per_period = 1500
##        amplitude_volts = 0.1
##        murrcle_signal = np.sin(np.linspace(
##            0, 2*np.pi*num_periods, num_periods * daq_timepoints_per_period))
##        murrcle_signal[:daq_timepoints_per_period] = 0
##        murrcle_signal[-daq_timepoints_per_period:] = 0
        murrcle_signal = np.zeros(20000, dtype=np.float64)
        default_murrcle = self.daq.default_voltages[-1, n2c['emission_scan']]
        murrcle_signal[:] = default_murrcle
##        murrcle_signal[1000:1152] = 0.05
##        murrcle_signal[1152:-1000] = 0.1
##        murrcle_signal[200:204] = default_murrcle + impulse_strength


        """
        Read in an arbitrary signal from a tif file
        """
        loaded_signal = tif_to_array(
            filename='input_voltage_to_mirror_05.tif').astype(np.float64)
##        loaded_signal += default_murrcle
##        loaded_signal *= 1.75

##
##        loaded_signal[loaded_signal < 0] *= 0.45
##
##        print "Pre Loaded signal min, max:",
##        print loaded_signal.min(), loaded_signal.max()    
##     
        print "Loaded signal min, max:",
        print loaded_signal.min(), loaded_signal.max()
        print
        """
        Put this optimzed waveform into the larger array
        """
        murrcle_signal[:loaded_signal.size] = loaded_signal[:, 0, 0]
        print "Loaded signal size", loaded_signal.size
##        """
##        Smoothly drop the voltage to default; hopefully this reduces ringing.
##        """
##        murrcle_signal[loaded_signal.size:2*(loaded_signal.size)
##                       ] = np.linspace(
##                           loaded_signal[-1, 0, 0],
##                           default_murrcle,
##                           loaded_signal.size)
##        print "last value for signal" , loaded_signal[-1, 0 , 0]
##        print murrcle_signal[loaded_signal.size * 1.5] #Remove this soon
##        
        self.characterization_points = murrcle_signal.size

        delay_points = max(#Figure out the limiting factor
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
        print "murrcle_Signal[0]", murrcle_signal[0]
        print "murrcle_Signal[-1]", murrcle_signal[-1]
        print "default murrcle", default_murrcle
##        assert murrcle_signal[0] == default_murrcle
        assert murrcle_signal[-1] == default_murrcle
        voltage[:, n2c['emission_scan']] = default_murrcle
        voltage[-murrcle_signal.size:, n2c['emission_scan']] = murrcle_signal
        print "Impulse starts at DAQ pixel:",
        print voltage.size - murrcle_signal.size + 250
        
        """
        Objective stays at what it was
        """
        objective_voltage = self.daq.default_voltages[-1, n2c['objective']]
        voltage[:, n2c['objective']] = objective_voltage
        """
        Excitation Galvo stays at what it was
        """
        galvo_voltage = self.daq.default_voltages[-1, n2c['excitation_scan']]
        voltage[:, n2c['excitation_scan']] = galvo_voltage

        self.daq.send_voltage(voltage, 'characterize')
        
        return None
    
    def initialize_snap(self):
        
        ##Assume full-frame camera operation, 10 ms roll time
        roll_time = int(np.ceil(self.daq.rate * 0.01))
####        oh_snap_voltages = np.zeros(
####            (self.daq.write_length  + roll_time, self.daq.num_mutable_channels),
####            dtype=np.float64)

        oh_snap_voltages = np.zeros(
            (30000, self.daq.num_mutable_channels),
            dtype=np.float64)

        ##objective stays at what it was
        objective_voltage = self.daq.default_voltages[-1, n2c['objective']]
        oh_snap_voltages[:, n2c['objective']] = objective_voltage

        ##excitation galvo stays at what it was
        galvo_voltage = self.daq.default_voltages[-1, n2c['excitation_scan']]
        oh_snap_voltages[:, n2c['excitation_scan']] = galvo_voltage

        ##murrcle stays at what it was
        murrcle_voltage = self.daq.default_voltages[-1, n2c['emission_scan']]
        oh_snap_voltages[:, n2c['emission_scan']] = murrcle_voltage
        
        #Camera triggers at the start of a write
        oh_snap_voltages[:self.daq.write_length//4, n2c['camera']] = 3
        
        #AOTF fires on one perpendicular facet
        
        start_point_laser = (#Integer num of writes plus a perp facet time
            self.daq.perpendicular_facet_times[6] + self.illumination_offset+
            self.daq.write_length * int(roll_time * 1.0 /
                                        self.daq.write_length))
        oh_snap_voltages[start_point_laser:start_point_laser+self.illumination_length, n2c['488']] = 10
        oh_snap_voltages[start_point_laser:start_point_laser+self.illumination_length, n2c['blanking']] = 10

##        oh_snap_voltages[start_point_laser, n2c['blanking']] = 10
        time.sleep(1)

        """
        let's test the objective impulse response
        """
##        marker = start_point_laser
##        scan = np.linspace(5, 6, 5000)        
##        oh_snap_voltages[marker:(marker+5000), n2c['objective']] = scan
##        marker += 5000
##        oh_snap_voltages[marker:(
##            marker+2500), n2c['objective']] = 6
##        marker += 2500
##        oh_snap_voltages[marker:(
##            marker+5000), n2c['objective']] = np.linspace(6,5,5000)
##        marker += 5000        
        
##        loaded_signal = tif_to_array(
##            filename='input_voltage_objective_00.tif').astype(
##                np.float64).ravel()
##        loaded_signal += objective_voltage
##        oh_snap_voltages[:22500, n2c['objective']] = loaded_signal[:]
##        print "min", oh_snap_voltages[:, n2c['objective']].min()
##        print "max", oh_snap_voltages[:, n2c['objective']].max()
##
##        loaded_desired_signal = tif_to_array(
##            filename='desired_result_objective.tif').astype(
##                np.float64).ravel()
##        loaded_desired_signal += objective_voltage
##        loaded_desired_signal[0] += 1
##        oh_snap_voltages[:, n2c['561']] = objective_voltage
##        oh_snap_voltages[:22500, n2c['561']] = loaded_desired_signal[:]
        
        print oh_snap_voltages.shape
        self.daq.send_voltage(oh_snap_voltages, 'snap')
        return None

    def initialize_volume(self):
        
        volume_voltages = np.zeros((30000, self.daq.num_mutable_channels),
            dtype=np.float64)

        ##objective starts where it was
        objective_voltage = self.daq.default_voltages[-1, n2c['objective']]
        volume_voltages[:, n2c['objective']] = objective_voltage

        ##objective does loaded scan
        loaded_signal = tif_to_array(
            filename='input_voltage_objective_01.tif').astype(
                np.float64).ravel()
        loaded_signal += objective_voltage
        volume_voltages[:22500, n2c['objective']] = loaded_signal[:]
        print "min", oh_snap_voltages[:, n2c['objective']].min()
        print "max", oh_snap_voltages[:, n2c['objective']].max()

        ##excitation galvo starts where it was
        galvo_voltage = self.daq.default_voltages[-1, n2c['excitation_scan']]
        volume_voltages[:, n2c['excitation_scan']] = galvo_voltage

        ##excitation galvo scans illumination
        galvo_voltage[5000:10000] = np.linspace(
            galvo_voltage, galvo_voltage + 0.2, 5000)
        galvo_voltage[10000:12500] = galvo_voltage + 0.2
        galvo_voltage[12500:17500] = np.linspace(
            galvo_voltage + 0.2, galvo_voltage, 5000)

        ##murrcle stays at what it was
        murrcle_voltage = self.daq.default_voltages[-1, n2c['emission_scan']]
        oh_snap_voltages[:, n2c['emission_scan']] = murrcle_voltage
        
        #Camera triggers at the start of a write
        oh_snap_voltages[:self.daq.write_length//4, n2c['camera']] = 3
        
        #AOTF fires on one perpendicular facet
        
        start_point_laser = (#Integer num of writes plus a perp facet time
            self.daq.perpendicular_facet_times[6] + self.illumination_offset+
            self.daq.write_length * int(roll_time * 1.0 /
                                        self.daq.write_length))
        oh_snap_voltages[start_point_laser:start_point_laser+self.illumination_length, n2c['488']] = 10
        oh_snap_voltages[start_point_laser:start_point_laser+self.illumination_length, n2c['blanking']] = 10

##        oh_snap_voltages[start_point_laser, n2c['blanking']] = 10
        time.sleep(1)

        """
        let's test the objective impulse response
        """
##        marker = start_point_laser
##        scan = np.linspace(5, 6, 5000)        
##        oh_snap_voltages[marker:(marker+5000), n2c['objective']] = scan
##        marker += 5000
##        oh_snap_voltages[marker:(
##            marker+2500), n2c['objective']] = 6
##        marker += 2500
##        oh_snap_voltages[marker:(
##            marker+5000), n2c['objective']] = np.linspace(6,5,5000)
##        marker += 5000        
        
##        loaded_signal = tif_to_array(
##            filename='input_voltage_objective_00.tif').astype(
##                np.float64).ravel()
##        loaded_signal += objective_voltage
##        oh_snap_voltages[:22500, n2c['objective']] = loaded_signal[:]
##        print "min", oh_snap_voltages[:, n2c['objective']].min()
##        print "max", oh_snap_voltages[:, n2c['objective']].max()
##
##        loaded_desired_signal = tif_to_array(
##            filename='desired_result_objective.tif').astype(
##                np.float64).ravel()
##        loaded_desired_signal += objective_voltage
##        loaded_desired_signal[0] += 1
##        oh_snap_voltages[:, n2c['561']] = objective_voltage
##        oh_snap_voltages[:22500, n2c['561']] = loaded_desired_signal[:]
        
        print oh_snap_voltages.shape
        self.daq.send_voltage(oh_snap_voltages, 'snap')
        return None

    def initialize_image_data_pipeline(self):
        self.idp = Image_Data_Pipeline(
            num_buffers=15,
            buffer_shape=(1, 2042, 2060), ##256 or 2048, 2060
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
              'region_of_interest': (-1, 4, 10000, 2044),##897, 1152
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
        rotations_per_second = 200
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
        default_voltage[:, n2c['561']] = 0 ##5 ####CHANGE ME BACK
        default_voltage[:, n2c['blanking']] = 0
        default_voltage[:, n2c['objective']] = 5
        default_voltage[:, n2c['excitation_scan']] = 0
        default_voltage[:, n2c['emission_scan']] = 0 #-4.45
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
        perpendicular_lag = int(np.ceil((10404.0/rotations_per_second) - 10.0))
        self.daq.perpendicular_facet_times = []
        for facet in range(facets_per_rotation):
            self.daq.perpendicular_facet_times.append(
                facet * points_per_facet + perpendicular_lag)

        ##FIXME: Put this shit into an "alignment" panel
        """
##        want continuous laser firing? try these lines.
##        """
####        laser_signal = np.zeros((points_per_rotation), dtype=np.float64)
######        camera_signal = np.zeros((points_per_rotation), dtype=np.float64)
####        laser_duration = 5
####        delay = 0
######        for i in range(len(self.daq.perpendicular_facet_times)):
######            print "flash"
####        place = self.daq.perpendicular_facet_times[0] + delay ##i
####        laser_signal[place:place+laser_duration] = 10##7.5
######            camera_signal[place:place+50] = 3##7.5
####        print "i =", i
####        print laser_signal[self.daq.perpendicular_facet_times[1]]
####        print "changing defaults"
####        self.daq.set_default_voltage(laser_signal, n2c['488'])
####        self.daq.set_default_voltage(laser_signal, n2c['blanking'])
######        self.daq.set_default_voltage(camera_signal, n2c['camera'])
####
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
