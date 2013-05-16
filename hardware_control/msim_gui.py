import sys
import os
import time
import logging
import ConfigParser
import datetime
import subprocess
import multiprocessing as mp
import Tkinter as tk
import tkMessageBox
import tkFileDialog
import numpy as np
from image_data_pipeline import Image_Data_Pipeline
from dmd import ALP
from shutters import Laser_Shutters
from stage import Z
from wheel import Filter_Wheel

if sys.platform == 'win32':
    clock = time.clock
else:
    clock = time.time

class GUI:
    def __init__(self):
        save_location = Data_Directory_Subprocess()
        logger = mp.log_to_stderr()
        logger.setLevel(logging.WARNING)
        self.data_pipeline = Image_Data_Pipeline(
            num_buffers=10,
            buffer_shape=(896, 480, 480))
        self.data_pipeline.set_display_intensity_scaling(
            'median_filter_autoscale', display_min=0, display_max=0)
        self.data_pipeline.withdraw_display()
        self.camera_settings = {}
        self.camera_roi = (961, 841, 1440, 1320)
        self.data_pipeline.camera.commands.send(('get_preframes', {}))
        while True:
            if self.data_pipeline.camera.commands.poll():
                self.camera_preframes = (
                    self.data_pipeline.camera.commands.recv())
                break
        self.dmd = ALP()
        self.dmd_settings = {}
        self.dmd_num_frames = 0
        self.lasers = ['561', '488']
        self.shutters = Laser_Shutters(
            colors=self.lasers, pause_after_open=0.25)
        self.shutter_timeout = -1
        self.z_stage = Z()
        self.z_stage.move(0)
        self.filters = Filter_Wheel(initial_position='f3',
                                    wheel_delay=1.8)
        self.root = tk.Tk()
        try:
            self.root.iconbitmap(default='microscope.ico')
        except tk.TclError:
            print "WARNING: Icon file 'microscope.ico' not found."
        self.root.report_callback_exception = self.report_callback_exception
        self.root.title("MSIM controls")

        self.menubar = tk.Menu(self.root)
        self.filemenu = tk.Menu(self.menubar, tearoff=0)
        self.filemenu.add_command(label="Exit", command=self.root.destroy)
        self.menubar.add_cascade(label="File", menu=self.filemenu)
        self.settingsmenu = tk.Menu(self.menubar, tearoff=0)
        self.settingsmenu.add_command(
            label="Brightfield mode", command=self.open_brightfield_window)
        self.settingsmenu.add_command(
            label="Display", command=self.open_display_settings_window)
        self.settingsmenu.add_command(
            label="Emission filters", command=self.open_filter_window)
        self.settingsmenu.add_command(
            label="SIM pattern", command=self.open_pattern_window)
        self.settingsmenu.add_command(
            label="Exposure time", command=self.open_exposure_window)
        self.menubar.add_cascade(label="Settings", menu=self.settingsmenu)
        self.root.config(menu=self.menubar)

        self.emission_filters = {}
        for c in self.lasers:
            self.emission_filters[c] = tk.StringVar()
            self.emission_filters[c].set('Filter 3')

        self.sim_patterns = {}
        for c in self.lasers:
            self.sim_patterns[c] = 'illumination_pattern_16x14.raw'

        self.available_sim_exposures = {
            '4500': {'pt': 4500, 'it': 2200, 'et': 2200},
            '9000': {'pt': 9000, 'it': 6800, 'et': 6700},
            '15000': {'pt': 15000, 'it': 12600, 'et': 12600},
            '25000': {'pt': 25000, 'it': 22600, 'et': 22600},
            '50000': {'pt': 50000, 'it': 47600, 'et': 47600},
            '100000': {'pt': 100000, 'it': 97500, 'et': 97500},
            }
        self.sim_exposures = {}
        for c in self.lasers:
            self.sim_exposures[c] = tk.StringVar()
            self.sim_exposures[c].set('4500')
        self.widefield_exposures = {}
        for c in self.lasers:
            self.widefield_exposures[c] = 100

        self.laser_power = {}
        self.laser_on = {}
        self.lake_info = {}
        frame = tk.Frame(self.root, bd=4, relief=tk.SUNKEN)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        a = tk.Label(frame, text='Snap settings:')
        a.pack(side=tk.TOP)
        for c in self.lasers:
            subframe = tk.Frame(frame)
            subframe.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
            a = tk.Label(subframe, text='Laser power:\n'+c+' nm (%)')
            a.pack(side=tk.LEFT)
            self.laser_power[c] = Scale_Spinbox(
                subframe, from_=0.1, to=100, increment=0.1, initial_value=100)
            self.laser_power[c].spinbox.config(width=5)
            self.laser_power[c].pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
            self.laser_on[c] = tk.IntVar()
            a = tk.Checkbutton(subframe, text='',
                               variable=self.laser_on[c])
            if c == '488':
                self.laser_on[c].set(1)
            else:
                self.laser_on[c].set(0)
            a.pack(side=tk.LEFT)
            self.lake_info[c] = {}
            self.lake_info[c]['button'] = tk.Button(
                subframe, text='Calibrate',bg='red', fg='white',
                command=lambda color=c: self.root.after_idle(
                    lambda: self.calibrate(color)))
            self.lake_info[c]['button'].pack(side=tk.LEFT)

        subframe = tk.Frame(frame)
        subframe.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        subsubframe = tk.Frame(subframe)
        subsubframe.pack(side=tk.LEFT)
        self.widefield_mode = tk.IntVar()
        a = tk.Checkbutton(subsubframe, text='Widefield mode',
                           variable=self.widefield_mode)
        a.pack(side=tk.TOP)
        self.num_snaps_saved = 0
        self.num_stacks_saved = 0
        self.save_snaps = tk.IntVar()
        a = tk.Checkbutton(subsubframe, text='Save snaps',
                           variable=self.save_snaps)
        a.pack(side=tk.TOP)
        self.snap_button = tk.Button(
            master=subframe, text='Snap', bg='gray1', fg='white', font=60,
            command=lambda: self.root.after_idle(self.snap_with_gui_settings))
        self.snap_button.bind(
            "<Button-1>", lambda x: self.snap_button.focus_set())
        self.snap_button.bind(
            "<Return>",
            lambda x: self.root.after_idle(self.snape_with_gui_settings))
        self.snap_button.pack(side=tk.BOTTOM)

        frame = tk.Frame(self.root, bd=4, relief=tk.SUNKEN)
        frame.pack(side=tk.TOP, fill=tk.BOTH)
        a = tk.Label(frame, text="Z-stack settings:")
        a.pack(side=tk.TOP)
        subframe = tk.Frame(frame)
        subframe.pack(side=tk.TOP, fill=tk.BOTH)
        a = tk.Label(master=subframe, text=u'Start:\n (\u03BCm)')
        a.pack(side=tk.LEFT)
        self.stack_start = Scale_Spinbox(
            subframe, from_=-150, to=150, increment=0.05, initial_value=-10)
        self.stack_start.spinbox.config(width=6)
        self.stack_start.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        subframe = tk.Frame(frame)
        subframe.pack(side=tk.TOP, fill=tk.BOTH)
        a = tk.Label(master=subframe, text=u'End:\n (\u03BCm)')
        a.pack(side=tk.LEFT)
        self.stack_end = Scale_Spinbox(
            subframe, from_=-150, to=150, increment=0.05, initial_value=10)
        self.stack_end.spinbox.config(width=6)
        self.stack_end.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        subframe = tk.Frame(frame)
        subframe.pack(side=tk.TOP, fill=tk.BOTH)
        a = tk.Label(master=subframe, text=u'Step:\n (\u03BCm)')
        a.pack(side=tk.LEFT)
        self.stack_step = Scale_Spinbox(
            subframe, from_=0.05, to=5, increment=0.05, initial_value=1)
        self.stack_step.spinbox.config(width=5)
        self.stack_step.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)

        subframe = tk.Frame(frame)
        subframe.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        subsubframe = tk.Frame(subframe)
        subsubframe.pack(side=tk.LEFT)
        self.interlace_colors = tk.IntVar()
        self.interlace_colors.set(1)
        a = tk.Checkbutton(subsubframe, text='Interlace colors',
                           variable=self.interlace_colors)
        a.pack(side=tk.TOP)
        self.stack_button = tk.Button(
            master=subframe, text='Acquire Z-stack', bg='gray1', fg='white',
            command=lambda: self.root.after_idle(self.z_stack))
        self.stack_button.bind(
            "<Button-1>", lambda x: self.stack_button.focus_set())
        self.stack_button.pack(side=tk.TOP)

        self.root.after(50, self.load_config)
        self.root.after(50, self.close_shutters)
        if save_location.get(self):
            self.root.mainloop()
        self.data_pipeline.close()
        self.dmd.close()
        return None

    def snap_with_gui_settings(
        self, subdirectory=None, display=True, name_postfix=''):
        lasers = [c for c in self.lasers if self.laser_on[c].get() == 1]
        if len(lasers) == 0:
            print "No lasers selected, no snap performed"
            return None
        if self.save_snaps.get():
            if subdirectory is None:
                """
                Just a snap, not getting triggered by a stack or a
                timelapse.
                """
                subdirectory = 'Snap_%04i'%(self.num_snaps_saved)
                if os.path.exists(os.path.join(self.save_directory,
                                               subdirectory)):
                    raise UserWarning("Snap directory already exists")
                else:
                    os.mkdir(os.path.join(
                        self.save_directory, subdirectory))
                self.num_snaps_saved += 1
        for color in lasers:
            if self.widefield_mode.get():
                print "Widefield"
                exposure = {}
                for key in ('it', 'pt', 'et'):
                    exposure[key] = self.widefield_exposures[c]
                filename = os.path.join(
                    os.getcwd(), 'patterns', 'widefield_pattern.raw')
            else:
                print "SIM"
                exposure = self.available_sim_exposures[
                    self.sim_exposures[color].get()]
                filename = os.path.join(
                    os.getcwd(), 'patterns', self.sim_patterns[color])
            dmd_settings = {
                'illuminate_time': exposure['it'],
                'picture_time': exposure['pt'],
                'illumination_filename': filename,
                }
            camera_settings = {
                'exposure_time_microseconds': exposure['et'],
                'trigger': 'external trigger/software exposure control',
                }
            if self.save_snaps.get():
                file_basename = (
                    'snap' +
                    '_c%s'%(color) +
                    '_f%s'%(self.emission_filters[
                        color].get().split()[-1]) +
                    name_postfix + 
                    '.tif')
                file_name = os.path.join(self.save_directory,
                                         subdirectory,
                                         file_basename)
            else:
                file_name = None
                display = False
            self.snap(
                color, dmd_settings, camera_settings, file_name, display)
        return None

    def z_stack(self, subdirectory=None, cancel_box_text='Abort z-stack',):
        lasers = [c for c in self.lasers if self.laser_on[c].get() == 1]
        if len(lasers) == 0:
            print "No lasers selected, no stack performed"
            return None
        if not self.interlace_colors.get() and len(lasers) > 1:
            """Take the stack one color at a time"""
            for i in lasers:
                for c in self.lasers:
                    self.laser_on[c].set(0)
                self.laser_on[i].set(1)
                self.z_stack()
            """Restor the original settings"""
            for i in lasers:
                self.laser_on[i].set(1)
            return None
        """
        Ok, now actually take a stack.
        """
        if subdirectory is None:
            """
            Just a stac, not getting triggered by a timelapse.
            """
            subdirectory = 'Stack_%04i'%(self.num_stacks_saved)
            if os.path.exists(os.path.join(self.save_directory,
                                           subdirectory)):
                raise UserWarning("Stack directory already exists")
            else:
                os.mkdir(os.path.join(
                    self.save_directory, subdirectory))
            self.num_stacks_saved += 1
        start, stop, step = (self.stack_start.get(),
                             self.stack_end.get(),
                             self.stack_step.get())
        if stop < start:
            step = -step #'self.stack_step' is always positive
        save_snaps = self.save_snaps.get()
        self.save_snaps.set(1)
        cancel_box = Cancel_Box_Subprocess(
            title='Acquiring...', text=cancel_box_text)        
        for i, z in enumerate(np.arange(start, stop, step)):
            if not cancel_box.ping():
                print "Acquisition cancelled..."
                break
            self.z_stage.move(z * 10) #Stage uses 100 nm units
            self.snap_with_gui_settings(
                subdirectory=subdirectory,
                display=False,
                name_postfix='_z%04i'%i)
        if cancel_box.ping():
            cancel_box.kill()
        self.z_stage.move(0)
        self.save_snaps.set(save_snaps)
        return None

    def snap(self,
             color,
             dmd_settings,
             camera_settings,
             file_name=None,
             display=False,
             brightfield=False,
             ):
        """
        First, we need to check if the DMD settings need to update.
        """
        self.filters.move('f' + self.emission_filters[color].get().split()[-1])
##        print "Snapping", color
        if 'illuminate_time' in dmd_settings:
            dmd_settings['illuminate_time'] = max(
                15,
                int(
                    dmd_settings['illuminate_time'] *
                    0.01 * self.laser_power[color].get()))
        else:
            raise UserWarning("DMD settings didn't contain 'illuminate_time'")
        if 'picture_time' not in dmd_settings:
            dmd_settings['picture_time'] = 4500
        for k in (dmd_settings.keys() + self.dmd_settings.keys()):
            try:
                assert dmd_settings[k] == self.dmd_settings[k]
            except (KeyError, AssertionError):
                """
                Mismatch, re-apply DMD settings
                """
                self.num_dmd_frames = self.dmd.apply_settings(**dmd_settings)
                self.dmd_settings = dmd_settings
                break
        """
        Now, we need to check if the camera settings need to update.
        """
        for k in (camera_settings.keys() + self.camera_settings.keys()):
            try:
                assert camera_settings[k] == self.camera_settings[k]
            except (KeyError, AssertionError):
                """
                Mismatch, re-apply camera settings
                """
                self.data_pipeline.camera.commands.send((
                    'apply_settings', camera_settings))
                try:
                    trigger, exposure, self.camera_roi = (
                        self.data_pipeline.camera.commands.recv())
                except TypeError:
                    print "Looks like we're using the dummy camera."
                self.camera_settings = camera_settings
                break
        num_camera_lr_pix = 1 + self.camera_roi[2] - self.camera_roi[0]
        num_camera_ud_pix = 1 + self.camera_roi[3] - self.camera_roi[1]
        if (num_camera_lr_pix *
            num_camera_ud_pix *
            (self.num_dmd_frames - self.camera_preframes
             ) >
            self.data_pipeline.buffer_size):
            """
            The data pipeline buffers are too small to hold this snap.
            Make a new pipeline with larger buffers.
            """
            print "Enlarging data pipeline buffers..."
            num_buffers = self.data_pipeline.num_data_buffers
            self.data_pipeline.close()
            print num_buffers
            print (self.num_dmd_frames - self.camera_preframes,
                   num_camera_ud_pix,
                   num_camera_lr_pix)
            self.data_pipeline = Image_Data_Pipeline(
                num_buffers=num_buffers,
                buffer_shape = (self.num_dmd_frames - self.camera_preframes,
                                num_camera_ud_pix,
                                num_camera_lr_pix))
            self.data_pipeline.camera.commands.send((
                'apply_settings', self.camera_settings))
        elif (
            (self.num_dmd_frames - self.camera_preframes,
             num_camera_ud_pix,
             num_camera_lr_pix) !=
            self.data_pipeline.buffer_shape):
            """
            The data pipline buffers are at least as big as they need
            to be, but not the right shape. Tell the pipeline to use
            only part of the buffer.
            """
            self.data_pipeline.set_buffer_shape(
                (self.num_dmd_frames - self.camera_preframes,
                 num_camera_ud_pix,
                 num_camera_lr_pix))
        """
        Ready to acquire an image! Load buffers to the pipeline, and
        play the DMD pattern.
        """
        if file_name is None:
            file_info = None
        else:
            file_info = [{'outfile': file_name}]
        for c in self.lasers:
            if c == color:
                pass
            else:
                self.shutters.shut(c, verbose=False)
        expected_shutter_duration = (
            1e-6 * self.dmd_settings['picture_time'] * self.num_dmd_frames)
        if not brightfield:
            self.shutters.open(color, verbose=False)
            self.shutter_timeout = max(
                self.shutter_timeout,
                expected_shutter_duration + 0.2 + clock())
        self.data_pipeline.load_data_buffers(1, file_saving_info=file_info)
        self.dmd.display_pattern(verbose=False)
        self.data_pipeline.camera.commands.send(('get_status', {}))
        self.root.after_idle(self.check_camera_status)
        if display and file_name is not None:
            self.open_tif_in_imagej(file_name)
        return None

    def check_camera_status(self):
        if self.data_pipeline.camera.commands.poll():
            camera_status = self.data_pipeline.camera.commands.recv()
            return None
        else:
            self.root.after_idle(self.check_camera_status)
        return None

    def close_shutters(self):
        if self.shutter_timeout >= 0:
##            print "Shutter time until closed:", self.shutter_timeout - clock()
            if self.shutter_timeout < clock():
                for c in self.lasers:
                    self.shutters.shut(c)
                self.shutter_timeout = -1
        self.root.after(100, self.close_shutters)
        return None

    def open_display_settings_window(self):
        try:
            self.display_settings_window.root.config()
        except (AttributeError, tk.TclError):
            self.display_settings_window = Display_Settings_Window(self)
        self.display_settings_window.root.lift()
        self.display_settings_window.root.focus_force()
        return None

    def open_brightfield_window(self):
        Brightfield_Window(self)
        return None

    def open_filter_window(self):
        try:
            self.filter_window.root.config()
        except (AttributeError, tk.TclError):
            self.filter_window = Filter_Window(self)
        self.filter_window.root.lift()
        self.filter_window.root.focus_force()
        return None
    
    def open_pattern_window(self):
        try:
            self.pattern_window.root.config()
        except (AttributeError, tk.TclError):
            self.pattern_window = Pattern_Window(self)
        self.pattern_window.root.lift()
        self.pattern_window.root.focus_force()
        return None

    def open_exposure_window(self):
        try:
            self.exposure_window.root.config()
        except (AttributeError, tk.TclError):
            self.exposure_window = Exposure_Window(self)
        self.exposure_window.root.lift()
        self.exposure_window.root.focus_force()
        return None

    def report_callback_exception(self, *args):
        import traceback
        err = traceback.format_exception(*args)
        with open(os.path.join(
            os.getcwd(),
            'error_log_gui.txt'), 'ab') as error_log:
            for e in err:
                error_log.write(e + os.linesep)
            error_log.write(os.linesep*2)
        tkMessageBox.showerror(
            'Exception',
            'An exception occured. ' +
            'Read "error_log.txt" in:\n' +
            repr(os.getcwd()) +
            '\nfor details."')
        return None

    def load_config(self):
        self.config = ConfigParser.RawConfigParser()
        self.config.read(os.path.join(os.getcwd(), 'config.ini'))
        while True:
            """Try to get the path to the ImageJ executable"""
            try:
                imagej_path = self.config.get('ImageJ', 'path')
                assert os.path.basename(imagej_path).lower() == 'imagej.exe'
                break
            except ConfigParser.NoSectionError:
                self.config.add_section('ImageJ')
            except ConfigParser.NoOptionError:
                imagej_path = str(os.path.normpath(tkFileDialog.askopenfilename(
                    title="Where is the ImageJ executable?",
                    filetypes=[('Executable', '.exe')],
                    defaultextension='.raw',
                    initialdir=os.getcwd(),
                    initialfile='ImageJ.exe'))) #Careful about Unicode here!
                self.config.set('ImageJ', 'path', imagej_path)
            except AssertionError:
                try_again = tkMessageBox.askretrycancel(
                    'ImageJ executable is weird',
                    'Try again?')
                if try_again:
                    self.config.remove_option('ImageJ', 'path')
                else:
                    break
        """Try to get path and age of the lake calibration data"""
        now = datetime.datetime.now()
        for c in self.lasers:
            """
            Assume the worst!
            """
            self.lake_info[c]['button'].config(bg='red', fg='white')
            self.lake_info[c]['calibration'] = 'None'
            try:
                self.lake_info[c]['path'] = self.config.get(
                    c + ' calibration ' + self.sim_patterns[c], 'path')
                print self.lake_info[c]['path']
                self.lake_info[c]['date'] = self.config.get(
                    c + ' calibration ' + self.sim_patterns[c], 'date').split()
                print self.lake_info[c]['date']
            except (ConfigParser.NoSectionError,
                    ConfigParser.NoOptionError) as e:
                print e
                continue
            for i in range(10):
                try:
                    assert os.path.exists(self.lake_info[c]['path'])
                    break
                except AssertionError:
                    time.sleep(0.1)
            else:
                print "Lake info not found:", self.lake_info[c]['path']
                continue
            try:
                lake_date = datetime.datetime(
                    *[int(i) for i in self.lake_info[c]['date']])
                print lake_date
            except TypeError:
                continue
            if abs((lake_date - now).total_seconds()) > 85400:
                print "Yellow"
                """The lake data exists, but is more than one day old"""
                self.lake_info[c]['button'].config(bg='yellow', fg='black')
                self.lake_info[c]['calibration'] = 'Old'
            else:
                print "Gray"
                self.lake_info[c]['button'].config(bg='gray', fg='black')
                self.lake_info[c]['calibration'] = 'Good'
        with open('config.ini', 'w') as configfile:
            self.config.write(configfile)
        return None

    def calibrate(self, color):
        calibration_window = Calibration_Window(self, color)
        return None
    
    def open_tif_in_imagej(
        self, filename, force_existence=True, tries_left=50):
        try:
            imagej_path = self.config.get('ImageJ', 'path')
        except:
            raise UserWarning("ImageJ path is not configured." +
                              "Delete or modify config.ini to fix this.")
        """
        I don't currently have a good way to check if Imagej is open
        or not. This mostly doesn't matter, but if you're taking
        2-color snaps, they can land pretty fast on the system and
        open two imagej copies. Laaame!
        try:
            assert self.imagej_subproc.poll()
        except:
            #Imagej probably isn't open. Open it, and give it a second.
            self.imagej_subproc = subprocess.Popen([imagej_path])
            self.root.after(500, lambda: self.open_tif_in_imagej(
                filename, force_existence, tries_left))
            return None
        """
        if os.path.exists(filename):
            cmd = """run("TIFF Virtual Stack...", "open=%s");"""%(
                str(filename).replace('\\', '\\\\'))
            print "Command to ImageJ:\n", repr(cmd)
            subprocess.Popen([imagej_path, "-eval", cmd])
        else:
            print "Waiting for file existence..."
            if force_existence and tries_left > 0:
                self.root.after(500, lambda: self.open_tif_in_imagej(
                    filename, force_existence, tries_left=tries_left - 1))
            else:
                raise UserWarning("Timeout exceeded; file may not exist.")
        return None
    
class Display_Settings_Window:
    def __init__(self, parent):
        self.parent = parent
        self.root = tk.Toplevel(parent.root)
        self.root.wm_title("Display settings")
        self.root.bind("<Escape>", lambda x: self.root.destroy())

        scaling, display_min, display_max = (
            self.parent.data_pipeline.get_display_intensity_scaling())

        frame = tk.Frame(self.root, relief=tk.SUNKEN, bd=4)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        a = tk.Label(frame, text="Contrast settings:")
        a.pack(side=tk.TOP)
        subframe = tk.Frame(frame)
        subframe.pack(side=tk.TOP, fill=tk.BOTH)
        a = tk.Label(master=subframe, text='Lower\nlimit:')
        a.pack(side=tk.LEFT)
        self.display_min = Scale_Spinbox(
            subframe, from_=0, to=(2**16 - 1), initial_value=display_min)
        self.display_min.bind(
            "<<update>>", lambda x: self.set_scaling())
        self.display_min.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        subframe = tk.Frame(frame)
        subframe.pack(side=tk.TOP, fill=tk.BOTH)
        a = tk.Label(master=subframe, text='Upper\nlimit:')
        a.pack(side=tk.LEFT)
        self.display_max = Scale_Spinbox(
            subframe, from_=0, to=(2**16 - 1), initial_value=display_max)
        self.display_max.bind(
            "<<update>>", lambda x: self.set_scaling())
        self.display_max.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        subframe = tk.Frame(frame)
        subframe.pack(side=tk.TOP, fill=tk.BOTH)
        a = tk.Label(master=subframe, text='Mode:')
        a.pack(side=tk.LEFT)
        self.scaling = tk.StringVar()
        self.scaling.set(scaling)
        button = tk.Radiobutton(
            master=subframe, text='Linear', variable=self.scaling,
            value='linear', indicatoron=0,
            command=lambda: self.root.after_idle(self.set_scaling))
        button.pack(side=tk.LEFT)
        button = tk.Radiobutton(
            master=subframe, text='Autoscale', variable=self.scaling,
            value='autoscale', indicatoron=0,
            command=lambda: self.root.after_idle(self.set_scaling))
        button.pack(side=tk.LEFT)
        button = tk.Radiobutton(
            master=subframe, text='Median autoscale', variable=self.scaling,
            value='median_filter_autoscale', indicatoron=0,
            command=lambda: self.root.after_idle(self.set_scaling))
        button.pack(side=tk.LEFT)

        self.update_scaling()
        return None
    
    def set_scaling(self):
        self.parent.data_pipeline.set_display_intensity_scaling(
            self.scaling.get(),
            display_min=self.display_min.get(),
            display_max=self.display_max.get())
        """
        Now we make sure the changes were accepted.
        """
        scaling, display_min, display_max = (
            self.parent.data_pipeline.get_display_intensity_scaling())
        self.scaling.set(scaling)
        self.display_min.set(int(display_min), update_trigger=False)
        self.display_max.set(int(display_max), update_trigger=False)
        return None

    def update_scaling(self):
        scaling, display_min, display_max = (
            self.parent.data_pipeline.get_display_intensity_scaling())
        if scaling == 'autoscale' or scaling == 'median_filter_autoscale':
            self.display_min.set(display_min)
            self.display_max.set(display_max)
        self.root.after(400, self.update_scaling)
        return None

class Filter_Window:
    def __init__(self, parent):
        self.parent = parent
        self.root = tk.Toplevel(parent.root)
        self.root.wm_title("Emission filter settings")
        self.root.bind("<Escape>", lambda x: self.root.destroy())

        a = tk.Label(self.root, text="Emission filter settings:")
        a.pack(side=tk.TOP)
        for c in self.parent.lasers:
            frame = tk.Frame(self.root)
            frame.pack(side=tk.TOP, fill=tk.BOTH)
            a = tk.Label(master=frame, text=c + ' nm laser\nemission filter:')
            a.pack(side=tk.LEFT)
            a = tk.OptionMenu(frame, self.parent.emission_filters[c],
                              *['Filter %i'%i for i in range(1, 7)])
            a.pack(side=tk.LEFT)
        return None

class Pattern_Window:
    def __init__(self, parent):
        self.parent = parent
        self.root = tk.Toplevel(parent.root)
        self.root.wm_title("SIM pattern selection")
        self.root.bind("<Escape>", lambda x: self.root.destroy())

        available_patterns = {
            120: 'illumination_pattern_12x10.raw',
            224: 'illumination_pattern_16x14.raw',
            288: 'illumination_pattern_18x16.raw',
            340: 'illumination_pattern_20x17.raw',
            504: 'illumination_pattern_24x21.raw',
            672: 'illumination_pattern_28x24.raw',
            896: 'illumination_pattern_32x28.raw',
            }

        self.pattern_choice = {}
        for c in self.parent.lasers:
            frame = tk.Frame(self.root)
            frame.pack(side=tk.TOP, fill=tk.BOTH)
            a = tk.Label(master=frame, text=c + ' nm laser\nSIM pattern:')
            a.pack(side=tk.LEFT)
            self.pattern_choice[c] = tk.StringVar()
            self.pattern_choice[c].set(self.parent.sim_patterns[c])
            a = tk.OptionMenu(frame, self.pattern_choice[c],
                              *[available_patterns[k]
                                for k in sorted(available_patterns.keys())])
            a.pack(side=tk.LEFT)
        frame = tk.Frame(self.root)
        frame.pack(side=tk.TOP, fill=tk.BOTH)
        a = tk.Button(frame, text='Apply settings',
                      command=lambda: self.change_sim_pattern())
        a.focus_set()
        a.bind('<Return>', lambda x: self.change_sim_pattern())
        a.pack(side=tk.TOP)
        return None

    def change_sim_pattern(self):
        for c in self.parent.lasers:
            self.parent.sim_patterns[c] = self.pattern_choice[c].get()
        self.parent.load_config()
        return None

class Exposure_Window:
    def __init__(self, parent):
        self.parent = parent
        self.root = tk.Toplevel(parent.root)
        self.root.wm_title("Exposure time selection")
        self.root.bind("<Escape>", lambda x: self.root.destroy())

        for c in self.parent.lasers:
            frame = tk.Frame(self.root)
            frame.pack(side=tk.TOP, fill=tk.BOTH)
            a = tk.Label(
                master=frame, text=c + ' nm laser\nSIM repetition time (us):')
            a.pack(side=tk.LEFT)
            a = tk.OptionMenu(
                frame, self.parent.sim_exposures[c],
                *sorted(self.parent.available_sim_exposures.keys(),
                        key=lambda x: int(x)))
            a.pack(side=tk.LEFT)
        self.widefield_exposures = {}
        for c in self.parent.lasers:
            frame = tk.Frame(self.root)
            frame.pack(side=tk.TOP, fill=tk.BOTH)
            a = tk.Label(
                master=frame,
                text=c + ' nm laser\nwidefield exposure time (us):')
            a.pack(side=tk.LEFT)        
            self.widefield_exposures[c] = Scale_Spinbox(
                frame, from_=1, to=500, increment=1,
                initial_value=self.parent.widefield_exposures[c])
            self.widefield_exposures[c].bind(
                "<<update>>", lambda x: self.set_widefield_exposures())
            self.widefield_exposures[c].pack(side=tk.LEFT)
        return None

    def set_widefield_exposures(self):
        for c in self.parent.lasers:
            self.parent.widefield_exposures[c] = (
                self.widefield_exposures[c].get())
        return None

class Brightfield_Window:
    def __init__(self, parent):
        self.parent = parent
        self.root = tk.Toplevel(parent.root)
        self.root.wm_title("Transmitted light mode")
        self.root.bind("<Escape>", lambda x: self.cancel())
        self.root.protocol("WM_DELETE_WINDOW", self.cancel)
        self.root.lift()
        self.root.focus_force()
        self.parent.root.withdraw()

        self.menubar = tk.Menu(self.root)
        self.filemenu = tk.Menu(self.menubar, tearoff=0)
        self.filemenu.add_command(
            label="Exit", command=self.parent.root.destroy)
        self.menubar.add_cascade(label="File", menu=self.filemenu)
        self.settingsmenu = tk.Menu(self.menubar, tearoff=0)
        self.settingsmenu.add_command(
            label="Fluorescence mode", command=self.cancel)
        self.settingsmenu.add_command(
            label="Display", command=self.parent.open_display_settings_window)
        self.settingsmenu.add_command(
            label="Emission filters", command=self.parent.open_filter_window)
        self.menubar.add_cascade(label="Settings", menu=self.settingsmenu)
        self.root.config(menu=self.menubar)

        self.frame = tk.Frame(self.root)
        self.frame.pack(side=tk.TOP, fill=tk.BOTH)
        a = tk.Label(self.frame,
                     text="Transmitted light mode\n\n" +
                     "Turn on the microscope lamp.\n")
        a.pack(side=tk.TOP)
        frame = tk.Frame(self.frame)
        frame.pack(side=tk.TOP)
        a = tk.Button(frame, text='Fluorescence mode', command=self.cancel)
        a.bind('<Return>', lambda x: self.cancel())
        a.pack(side=tk.LEFT)
        self.taking_snaps = True
        self.take_brightfield_snap()
        return None

    def take_brightfield_snap(self):
        if not self.taking_snaps:
            return None
        color = '488'
        dmd_settings = {
            'illuminate_time': 2200,
            'illumination_filename': os.path.join(
                os.getcwd(), 'patterns', self.parent.sim_patterns[color]),
            'first_frame': 0,
            'last_frame': self.parent.camera_preframes,
            }
        camera_settings = {
            'exposure_time_microseconds': 2200,
            'trigger': 'external trigger/software exposure control',
            }
        self.parent.snap(color, dmd_settings, camera_settings, brightfield=True)
        self.root.after(70, lambda: self.take_brightfield_snap())
        return None

    def cancel(self):
        self.taking_snaps = False
        self.root.withdraw()
        tkMessageBox.showwarning("Leaving brightfield mode",
                                 "Turn off the lamp.")
        self.parent.root.deiconify()
        self.root.destroy()
        self.parent.load_config()
        return None

class Calibration_Window:
    def __init__(self, parent, color):
        self.parent = parent
        self.color = color
        self.root = tk.Toplevel(parent.root)
        self.root.wm_title("Calibration")
        self.root.bind("<Escape>", lambda x: self.cancel())
        self.root.protocol("WM_DELETE_WINDOW", self.cancel)
        self.root.lift()
        self.root.focus_force()
        self.parent.root.withdraw()

        self.menubar = tk.Menu(self.root)
        self.filemenu = tk.Menu(self.menubar, tearoff=0)
        self.filemenu.add_command(
            label="Exit", command=self.parent.root.destroy)
        self.menubar.add_cascade(label="File", menu=self.filemenu)
        self.settingsmenu = tk.Menu(self.menubar, tearoff=0)
        self.settingsmenu.add_command(
            label="Display", command=self.parent.open_display_settings_window)
        self.settingsmenu.add_command(
            label="Emission filters", command=self.parent.open_filter_window)
        self.settingsmenu.add_command(
            label="SIM pattern", command=self.parent.open_pattern_window)
        self.settingsmenu.add_command(
            label="Exposure time", command=self.parent.open_exposure_window)
        self.menubar.add_cascade(label="Settings", menu=self.settingsmenu)
        self.root.config(menu=self.menubar)

        self.frame = tk.Frame(self.root)
        self.frame.pack(side=tk.TOP, fill=tk.BOTH)
        a = tk.Label(self.frame,
                     text="Calibration mode: %s nm laser\n\n"%(color) +
                     "Put a fluorescent lake slide on the microscope.\n" +
                     "Click 'Ok' when the slide is in place.\n" +
                     "\nWARNING!\n\n" +
                     "Lasers will turn on when you press 'Ok'.")
        a.pack(side=tk.TOP)
        frame = tk.Frame(self.frame)
        frame.pack(side=tk.TOP)
        a = tk.Button(frame, text='Ok',
                      command=lambda: self.alignment_mode(color))
        a.focus_set()
        a.bind('<Return>', lambda x: self.alignment_mode(color))
        a.pack(side=tk.LEFT)
        a = tk.Button(frame, text='Cancel', command=self.cancel)
        a.bind('<Return>', lambda x: self.cancel())
        a.pack(side=tk.LEFT)
        return None

    def alignment_mode(self, color):
        self.frame.pack_forget()
        self.frame = tk.Frame(self.root)
        self.frame.pack(side=tk.TOP, fill=tk.BOTH)
        a = tk.Label(self.frame, text="Calibration mode.\n\n" +
                     "Adjust the focus using the objective knob.\n" +
                     "You should see an array of spots.\n" +
                     "Click 'Ok' when the spots are visible.\n")
        a.pack(side=tk.TOP)
        subframe = tk.Frame(self.frame)
        subframe.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        a = tk.Label(subframe, text='Laser power:\n'+color+' nm (%)')
        a.pack(side=tk.LEFT)
        self.laser_power = Scale_Spinbox(
            subframe, from_=0.1, to=100, increment=0.1, initial_value=100)
        self.laser_power.spinbox.config(width=5)
        self.laser_power.bind(
            "<<update>>", lambda x, color=color: self.root.after_idle(
                lambda: self.parent.laser_power[color].set(
                    self.laser_power.get())))
        self.laser_power.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        frame = tk.Frame(self.frame)
        frame.pack(side=tk.TOP)
        a = tk.Button(
            frame, text='Ok', command=lambda: self.acquire_calibration(color))
        a.focus_set()
        a.bind('<Return>', lambda x: self.acquire_calibration(color))
        a.pack(side=tk.LEFT)
        a = tk.Button(frame, text='Cancel', command=self.cancel)
        a.bind('<Return>', lambda x: self.cancel())
        a.pack(side=tk.LEFT)
        self.aligning = True
        self.play_alignment_pattern(color)
        return None
    
    def play_alignment_pattern(self, color):
        if not self.aligning:
            return None
        exposure = self.parent.available_sim_exposures[
            self.parent.sim_exposures[color].get()]
        dmd_settings = {
            'illuminate_time': exposure['it'],
            'picture_time': exposure['pt'],
            'illumination_filename': os.path.join(
                os.getcwd(), 'patterns', self.parent.sim_patterns[color]),
            'first_frame': 0,
            'last_frame': self.parent.camera_preframes,
            }
        camera_settings = {
            'exposure_time_microseconds': exposure['et'],
            'trigger': 'external trigger/software exposure control',
            }
        self.parent.snap(color, dmd_settings, camera_settings)
        self.root.after(50, lambda: self.play_alignment_pattern(color))
        return None

    def acquire_calibration(self, color):
        self.aligning = False
        self.frame.pack_forget()
        self.frame = tk.Frame(self.root)
        self.frame.pack(side=tk.TOP, fill=tk.BOTH)
        a = tk.Label(self.frame, text="Calibration mode.\n\n" +
                     "Acquiring calibration...")
        a.pack(side=tk.TOP)
        exposure = self.parent.available_sim_exposures[
            self.parent.sim_exposures[color].get()]
        dmd_settings = {
            'illuminate_time': exposure['it'],
            'picture_time': exposure['pt'],
            'illumination_filename': os.path.join(
                os.getcwd(), 'patterns', self.parent.sim_patterns[color]),
            }
        camera_settings = {
            'exposure_time_microseconds': exposure['et'],
            'trigger': 'external trigger/software exposure control',
            }
        file_basename = ('lake' +
                         '_%s_'%(color) +
                         os.path.splitext(self.parent.sim_patterns[color])[0] +
                         '.tif')
        file_name = os.path.join(os.getcwd(), 'calibrations', file_basename)
        self.parent.snap(
            color, dmd_settings, camera_settings, file_name, display=True)
        self.parent.shutters.shut(color)
        section = color + ' calibration ' + self.parent.sim_patterns[color]
        if not self.parent.config.has_section(section):
            self.parent.config.add_section(section)
        self.parent.config.set(section, 'path', file_name)
        now = datetime.datetime.now()
        self.parent.config.set(
            section, 'date', '%i %i %i %i'%(
                now.year, now.month, now.day, now.hour))
        with open('config.ini', 'w') as configfile:
            self.parent.config.write(configfile)
        self.cancel()
        return None
    
    def cancel(self):
        self.root.withdraw()
        self.parent.root.deiconify()
        self.root.destroy()
        self.parent.load_config()
        return None
    
class Scale_Spinbox:
    def __init__(self, master, from_, to, increment=1, initial_value=None):
        self.frame = tk.Frame(master)
        self.scale = tk.Scale(
            self.frame,
            from_=from_, to=to, resolution=increment,
            orient=tk.HORIZONTAL)
        for e in ("<FocusOut>", "<ButtonRelease-1>", "<Return>"):
            self.scale.bind(e, lambda x: self.set(self.scale.get()))

        self.spinbox_v = tk.StringVar()
        self.spinbox = tk.Spinbox(
            self.frame,
            from_=from_, to=to, increment=increment,
            textvariable=self.spinbox_v, width=6)
        for e in ("<FocusOut>", "<ButtonRelease-1>", "<Return>"):
            self.spinbox.bind(e, lambda x: self.frame.after_idle(
                lambda: self.set(self.spinbox_v.get())))
        
        self.set(initial_value)

        self.scale.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        self.spinbox.pack(side=tk.LEFT)
        
    def pack(self, *args, **kwargs):
        return self.frame.pack(*args, **kwargs)

    def bind(self, *args, **kwargs):
        return self.frame.bind(*args, **kwargs)

    def get(self):
        return self.scale.get()

    def set(self, value=None, update_trigger=True):
        try:
            self.scale.set(value)
        except tk.TclError:
            pass
        self.spinbox_v.set(self.scale.get())
        if update_trigger: #Bind to this event for on-set
            self.frame.event_generate("<<update>>")
        return None

class Data_Directory_Subprocess:
    def __init__(self):
        get_data_directory_code = """
import Tkinter, tkSimpleDialog, datetime, os, sys

root = Tkinter.Tk()
root.focus_force()
root.withdraw()
user_name = tkSimpleDialog.askstring(title='Login', prompt='Session name:')
if user_name is None:
    raise UserWarning("Aborted")
    
OK_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789_"
def sanitize(s):
    return ''.join([x for x in s if x.lower() in OK_CHARS])

user_name = sanitize(user_name)

now = datetime.datetime.now()
date_string = '%04i_%02i_%02i_'%(now.year, now.month, now.day)

new_folder = os.path.join("D:\\\\SIM_data", date_string + user_name)

i = 1
while os.path.exists(new_folder + '_%03i'%(i)):
    i += 1
    if i > 999:
        raise UserWarning("Too many folders")
new_folder += '_%03i'%(i)
os.mkdir(new_folder)
print new_folder
"""
        self.subprocess = subprocess.Popen(
            [sys.executable, '-c %s'%get_data_directory_code],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        return None

    def get(self, parent):
        result = self.subprocess.communicate()
        data_folder = result[0].strip()
        if os.path.exists(data_folder):
            parent.save_directory = data_folder
            print "Save directory:", parent.save_directory
            return True
        else:
            print "Data directory response:"
            print result
            parent.root.quit()
        return False

class Cancel_Box_Subprocess:
    def __init__(self, title='', text='Cancel'):
        cancel_box_code = """
import Tkinter as tk
root = tk.Tk()
root.title('%s')
button = tk.Button(master=root,
                   text='%s',
                   command=root.destroy)
button.pack(side=tk.TOP)
root.mainloop()
"""%(title, text)
        self.subprocess = subprocess.Popen(
            [sys.executable, '-c %s'%cancel_box_code])
        return None

    def ping(self):
        response = self.subprocess.poll()
        if response is None:
            return True #subproc is still running
        elif response == 0:
            return False
        else:
            raise UserWarning("Cancel_Box_Subprocess response not understood")

    def kill(self):
        self.subprocess.terminate()
        return None

if __name__ == '__main__':
    GUI()
