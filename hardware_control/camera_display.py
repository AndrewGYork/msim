"""
These imports are for the camera acquisition/display code
Get arrayimage from Andrew Straw, here:
https://github.com/motmot/pygarrayimage/blob/master/pygarrayimage/arrayimage.py
"""
import sys, subprocess, threading, time
try:
    from Queue import Queue, Empty
except ImportError:
    from queue import Queue, Empty # python 3.x
import pyglet, numpy
from pyglet.window import mouse, key
from arrayimage import ArrayInterfaceImage
from simple_tif import array_to_tif
try:
    import pco
except ImportError:
    print "Unable to import pco.py. You won't be able to use a pco.edge camera."

class Display:
    def __init__(
        self,
        camera='pco.edge',
        initial_camera_settings=None,
        update_interval_milliseconds=1,
        is_subprocess=False,
        subproc_update_interval_milliseconds=1,
        verbose=True):

        self.verbose = verbose
        self.save_flag = False

        if camera == 'pco.edge':
            if initial_camera_settings == None:
                initial_camera_settings = {}
            initial_camera_settings['verbose'] = self.verbose
            self.camera = pco.Edge()
            self.camera._set_hw_io_ch4_to_global_exposure(verbose=self.verbose)
            self.apply_camera_settings(**initial_camera_settings)
            self.num_buffers = 16
            self.images_per_acquisition = 100
            self.images_in_history = 100
            self.images_to_display = 'num_acquired'
            self.next_image_to_acquire = 0
            self.frames_counted = 0
        else:
            raise UserWarning(
                'The only currently supported camera is the pco.edge.')

        self.is_subprocess = is_subprocess
        if self.is_subprocess:
            sys.stdout.flush()
            pyglet.clock.schedule_interval(
                self._get_parent_message,
                subproc_update_interval_milliseconds*0.001)
        self.camera_performance = {
            'frames': 0,
            'last_reset_time': time.clock(),
            'frames_per_second': 0,
            'history': []}
        pyglet.clock.schedule_interval(
            self.calculate_camera_fps, 0.5)
        self.brightness_scale_type = 'image_min_max_fraction'
        self.brightness_scale_min = 0.0
        self.brightness_scale_max = 1.0
        self.flip = False
        self.set_downsampling()
        self.make_window()
        self.set_status()
        pyglet.clock.schedule_interval(
            self.update, update_interval_milliseconds*0.001)
        self.run()
        return None

    def apply_camera_settings(
        self, trigger='auto trigger', exposure_time_microseconds=2200,
        region_of_interest=(961, 841, 1440, 1320), verbose=True):
        """
        Caches the results of applying camera settings so we don't
        have to check all the time.
        """
        input_variables = locals()
        input_variables.pop('self')
        self.trigger, self.exposure, self.roi = self.camera.apply_settings(
            **input_variables)
        if hasattr(self, 'camera_performance'):
            self.camera_performance['history'] = []
        return None

    def set_status(self, status='live_display'):
        if status == 'live_display':
            self.apply_camera_settings(
                trigger=self.trigger,
                exposure_time_microseconds=self.exposure,
                region_of_interest=self.roi,
                verbose=self.verbose)
            self.camera.arm(num_buffers=self.num_buffers)
        elif status == 'pause':
            self.camera.disarm(verbose=self.verbose)
            self.window.set_caption('SIM display (Paused)')
        else:
            raise UserWarning('Status not recognized')
        self._state = status
        return None

    def update(self, dt):
        if self._state == 'live_display':
            dma_errors = 0
            while True:
                try:
                    self.camera.record_to_memory(
                        num_images=self.images_per_acquisition,
                        verbose=self.verbose, out=self.image_raw,
                        first_frame=self.next_image_to_acquire,
                        poll_timeout=5000)
                    self.num_acquired = self.images_per_acquisition
                    self.window.set_caption(
                        'SIM display (Live), %0.2f fps'%(
                            self.camera_performance['frames_per_second']))
                    break
                except pco.DMAError:
                    self.num_acquired = 0
                    self.window.set_caption('SIM display (DMA error)')
                    dma_errors += 1
                    if self.verbose:
                        print "DMA error. Retrying..."
                    if dma_errors == 2 or dma_errors == 5: #Too many DMA errors
                        if self.verbose:
                            print "Too many consecutive DMA errors.",
                            print "Recovering..."
                        self.set_status('pause')
                        time.sleep(3)
                        self.set_status('live_display')
                    elif dma_errors == 9:
                        raise pco.DMAError("Too many consecutive DMA errors.")
                except pco.TimeoutError as err:
                    if self.verbose:
                        print 'Timeout error'
                    if err.num_acquired == 0:
                        self.window.set_caption(
                            'SIM display (Live), %0.2f fps (Trigger?)'%(
                                self.camera_performance['frames_per_second']))
                        return None
                    else:
                        self.window.set_caption(
                            'SIM display (Live), %0.2f fps'%(
                                self.camera_performance['frames_per_second']) +
                            ' (Trigger incomplete)')
                        self.num_acquired = err.num_acquired
                        break
        self.camera_performance[
            'frames'] += self.num_acquired
        self.frames_counted += self.num_acquired
        self.next_image_to_acquire = (
            self.next_image_to_acquire + self.num_acquired
            ) % self.images_in_history
        if self.save_flag:
            self.save_flag = False
            if self.verbose:
                print "Saving image..."
            self.image_raw.tofile('image.dat')
            save_info = open('image.txt', 'wb')
            save_info.write("Shape: %i %i %i"%self.image_raw.shape)
            if self.verbose:
                print "Saved."
        if self._state == 'live_display':
            pass
            self.scale_raw_to_8()
            self.image = ArrayInterfaceImage(
                self.image_i8, allow_copy=False)
            pyglet.gl.glTexParameteri( #Reset to no interpolation
                pyglet.gl.GL_TEXTURE_2D,
                pyglet.gl.GL_TEXTURE_MAG_FILTER,
                pyglet.gl.GL_NEAREST)
        return None

    def calculate_camera_fps(self, dt):
        t = time.clock()
        elapsed_time = t - self.camera_performance['last_reset_time']
        fps = ((self.camera_performance['frames'] * 1.0 / elapsed_time))
        self.camera_performance['history'].append(fps)
        if len(self.camera_performance['history']) > 20:
               self.camera_performance['history'].pop(0)
        self.camera_performance['frames'] = 0
        self.camera_performance['last_reset_time'] = time.clock()
        self.camera_performance['frames_per_second'] = numpy.mean(
            self.camera_performance['history'])
        return None

    def make_image(self):
        dimensions = (self.images_in_history,
                      self.roi[3] - self.roi[1] + 1,
                      self.roi[2] - self.roi[0] + 1)
        self.image_raw = numpy.zeros(#A temporary empty holder
            dimensions, dtype=numpy.uint16)
        self.clear_image_history()
        self.num_acquired = 1
        self.scale_raw_to_8()
        self.image = ArrayInterfaceImage(self.image_i8, allow_copy=False)
        return None

    def clear_image_history(self):
        self.image_raw.fill(0)
        self.image_raw[:, :, 0:3] = 1
        self.image_raw[:, :, -3:] = 1
        self.image_raw[:, 0:3, :] = 1
        self.image_raw[:, -3:, :] = 1
        return None

    def check_image_history_size(self, roi, images_in_history):
        dimensions = (images_in_history,
                      roi[3] - roi[1] + 1,
                      roi[2] - roi[0] + 1)
        two_gigabytes = 2 * 1073741824 #Bytes
        if 2 * numpy.product(dimensions) >= two_gigabytes:
            raise UserWarning(
                "Dimensions: %i, %i, %i\n"%(dimensions) + 
                "Display won't allow an image history bigger than 2 gigabytes")
        else:
            return None

    def make_window(self):
        self.make_image()
        self.window = pyglet.window.Window(
            self.image.width, self.image.height,
            caption='SIM display', resizable=True)
        icon16 = pyglet.image.load(
            'D:/instant_sim/code/microscope-icon16.png')
        icon32 = pyglet.image.load(
            'D:/instant_sim/code/microscope-icon32.png')
        self.window.set_icon(icon16, icon32)
        self.fps_display = pyglet.clock.ClockDisplay()
        self.image_x, self.image_y, self.image_scale = 0, 0, 1.0
        self.mouse_hover_pixel_display = pyglet.text.Label(
            '%i, %i, %i'%(0, 0, 0),
            font_name='Times New Roman',
            font_size=24,
            x=self.window.width//2 - 100, y=self.window.height//2 - 10,
            anchor_x='center', anchor_y='center')
        self.mouse_hover_x, self.mouse_hover_y = -1, -1

        @self.window.event
        def on_draw():
            self.window.clear()
            self.image.blit(x=self.image_x, y=self.image_y,
                       height=int(self.image.height * self.image_scale),
                       width=int(self.image.width * self.image_scale))
            self.fps_display.draw()
            if (hasattr(self, 'image_i16') and
                self.mouse_hover_x > 0 and self.mouse_hover_y > 0):
                try:
                    pixel_value = self.image_i16[self.mouse_hover_x,
                                                 self.mouse_hover_y]
                except IndexError:
                    pixel_value = 0
            else:
                pixel_value = 0
            self.mouse_hover_pixel_display.text = '%i, %i, %i'%(
                self.mouse_hover_x, self.mouse_hover_y,
                pixel_value)
            self.mouse_hover_pixel_display.draw()

        @self.window.event
        def on_mouse_motion(x, y, dx, dy):
            self.mouse_hover_x, self.mouse_hover_y = (
                numpy.round((x - self.image_x - 1) * 1.0 / (
                    self.downsampling * self.image_scale)),
                numpy.round((y - self.image_y - 1) * 1.0 / (
                    self.downsampling * self.image_scale)))
            
        @self.window.event
        def on_mouse_drag(x, y, dx, dy, buttons, modifiers):
            if buttons == mouse.LEFT:
                self.image_x += dx
                self.image_y += dy

        @self.window.event
        def on_key_press(symbol, modifiers):
            if self.verbose:
                print symbol
            if (symbol == key.EQUAL or
                symbol == key.PLUS or
                symbol == key.NUM_ADD):
                if self.verbose:
                    print "Equal or plus"
                if modifiers & key.MOD_CTRL:
                    self.brightness_scale_max *= 1.1
                    if self.verbose:
                        print self.brightness_scale_min,
                        print self.brightness_scale_max
                else:
                    self.image_scale *= 1.1
            elif (symbol == key.MINUS or
                  symbol == key.UNDERSCORE or
                  symbol == key.NUM_SUBTRACT):
                if self.verbose:
                    print "Minus or underscore"
                if modifiers & key.MOD_CTRL:
                    self.brightness_scale_max *= 0.9
                    if self.verbose:
                        print self.brightness_scale_min,
                        print self.brightness_scale_max
                else:
                    self.image_scale *= 0.9
            elif symbol == key.ENTER or symbol == key.RETURN:
                if self.verbose:
                    print "Enter or return"
                if modifiers & key.MOD_CTRL:
                    self.brightness_scale_max = 1.0
                    if self.verbose:
                        print self.brightness_scale_min,
                        print self.brightness_scale_max
                else:
                    self.image_scale = 1.0
                    self.image_x, self.image_y = 0, 0
                    self.window.set_size(self.image.width, self.image.height)
##            elif symbol == key.P:
##                if (self._state == 'live_display'):
##                    self.set_status('pause')
##                elif self._state == 'pause':
##                    self.set_status('live_display')
##            elif symbol == key.W:
##                self.set_region_of_interest((961, 841, 1440, 1320))
##            elif symbol == key.E:
##                self.set_region_of_interest((641, 841, 1440, 1320))
##            elif symbol == key.Q:
##                self.set_region_of_interest((961, 741, 1440, 1420))
##            elif symbol == key.R:
##                self.set_region_of_interest((0, 0, 10000, 10000))
##            elif symbol == key.S:
##                self.save_flag = True
##            elif symbol == key.D:
##                self.set_exposure(2200)
##            elif symbol == key.F:
##                self.set_exposure(100000)
##            elif symbol == key.T:
##                self.set_trigger_mode(trigger_mode="auto trigger")
##            elif symbol == key.Y:
##                self.set_trigger_mode(trigger_mode="external trigger/" +
##                                 "software exposure control")
        @self.window.event
        def on_text(text):
            if text == u'=' or text == u'+':
                self.image_scale *= 1.1
            elif text == u'-' or text == u'_':
                self.image_scale *= 0.9
        return None

    def set_exposure(self, exposure_time_microseconds=2200):
        if self.verbose:
            print "Changing exposure"
        old_state = self._state
        self.set_status('pause')
        self.window.set_caption('Changing exposure')
        self.apply_camera_settings(
            trigger=self.trigger,
            exposure_time_microseconds=exposure_time_microseconds,
            region_of_interest=self.roi,
            verbose=self.verbose)
        self.camera.arm(num_buffers=self.num_buffers)
        self.window.set_caption('SIM display')
        self.set_status(old_state)
        if self.verbose:
            print "Done resizing"
        return None

    def set_images_per_acquisition(self, num):
        if self.verbose:
            print "Changing images per acquisition"
        self.window.set_caption('Changing images per acquisition')
        self.images_per_acquisition = num
        if self.images_in_history < num:
            self.set_images_in_history(num)
        self.window.set_caption('SIM display')
        if self.verbose:
            print "Done changing."
        return None

    def set_images_to_display(self, num='num_acquired'):
        """
        The number of images in the history displayed at one time.
        Can either be an integer, or 'num_acquired'.
        """
        if self.verbose:
            print "Changing images per display"
        self.window.set_caption('Changing images per display')
        self.images_to_display = num
        if self.images_to_display is not 'num_acquired':
            """
            The user selected a number. The history needs to be at
            least this big.
            """
            if self.images_in_history < num:
                self.set_images_in_history(num)
        self.window.set_caption('SIM display')
        if self.verbose:
            print "Done changing."
        return None

    def set_images_in_history(self, num, force=False):
        if num <= self.images_in_history:
            if not force: #Don't bother decreasing this number
                return None
        if self.verbose:
            print "Changing number of images in history"
        old_state = self._state
        self.set_status('pause')
        self.window.set_caption('Changing image history size')
        self.images_in_history = max(num, self.images_per_acquisition)
        self.make_image()
        self.window.set_caption('SIM display')
        self.set_status(old_state)
        if self.verbose:
            print "Done changing."
        return None

    def save_images_in_history(
        self, num, filename='out.tif', channels=None, slices=None):
        """
        Saves the last 'num' images stored in the image history.
        """
        starting_frame = (self.next_image_to_acquire - num
                          ) % self.images_in_history
        overshoot = starting_frame + num - self.images_in_history
        save_me = self.image_raw[starting_frame:starting_frame + num, :, :]
        if overshoot > 0:
            save_me = numpy.concatenate(
                (save_me, self.image_raw[0:overshoot, :, :]),
                axis=0)
        array_to_tif(save_me, filename, channels=channels, slices=slices)
        return None

    def set_region_of_interest(self, roi):
        if self.verbose:
            print "Resizing"
        old_state = self._state
        self.set_status('pause')
        self.window.set_caption('Resizing')
        self.apply_camera_settings(
            trigger=self.trigger,
            exposure_time_microseconds=self.exposure,
            region_of_interest=roi,
            verbose=self.verbose)
        for i in range(3):
            self.window.set_caption('Resizing' + '.'*(i+1))
            time.sleep(1) #Seems to prevent pco.edge bugs
        self.camera.arm(num_buffers=self.num_buffers)
        self.make_image()
        self.window.set_size(self.image.width, self.image.height)
        self.window.set_caption('SIM display')
        self.set_status(old_state)
        if self.verbose:
            print "Done resizing"
        return None

    def set_downsampling(self, downsampling=1):
        if self.verbose:
            print "Setting downsampling..."
        self.downsampling = int(downsampling)
        self.make_image()
        if hasattr(self, 'window'):
            self.window.set_size(self.image.width, self.image.height)
        if self.verbose:
            print "Downsample factor:", self.downsampling
        return None

    def set_trigger_mode(self, trigger_mode):
        """
        Available trigger modes:
        "auto trigger"
        "software trigger"
        "external trigger/software exposure control"
        "external exposure control"
        """
        if self.verbose:
            print "Changing trigger mode to:", trigger_mode
        old_state = self._state
        self.set_status('pause')
        self.window.set_caption('Changing trigger mode')
        self.apply_camera_settings(
            trigger=trigger_mode,
            exposure_time_microseconds=self.exposure,
            region_of_interest=self.roi,
            verbose=self.verbose)
        for i in range(3):
            self.window.set_caption('Changing trigger mode' + '.'*(i+1))
            time.sleep(1) #Seems to prevent pco.edge bugs
        self.camera.arm(num_buffers=self.num_buffers)
        self.set_status(old_state)
        if self.verbose:
            print "Done changing trigger mode."
        return None

    def run(self):
        try:
            pyglet.app.run()
        except:
            raise
        finally:
            if hasattr(self, 'window'):
                self.window.close()
            self.camera.close(verbose=self.verbose)
        return None

    def scale_raw_to_8(self):
        """
        Takes in a 16-bit 1xXxY unsigned camera image, gives back an XxY
        unsigned 8-bit image.

        Probably the single biggest performance bottleneck. Worth
        optimizing someday.
        """
        if self.images_to_display == 'num_acquired':
            num = self.num_acquired
        else:
            num = self.images_to_display
        scale_type = self.brightness_scale_type
        starting_frame = (self.next_image_to_acquire - num
                          ) % self.images_in_history
        overshoot = starting_frame + num - self.images_in_history
        self.image_i16 = self.image_raw[
            starting_frame:starting_frame + num,
            ::-self.downsampling, ::self.downsampling].max(axis=0)
        if overshoot > 1:
            self.image_i16 = numpy.concatenate((
                self.image_i16.reshape((1,) + self.image_i16.shape),
                self.image_raw[
                    0:overshoot, ::-self.downsampling, ::self.downsampling]),
                                               axis=0).max(axis=0)
        if scale_type == 'image_min_max_fraction':
            self.image_i16 -= self.brightness_scale_min * self.image_i16.min()
            self.image_f32 = self.image_i16.astype(numpy.float32)
            self.image_f32 *= 255. / (self.brightness_scale_max *
                                      self.image_i16.max())
            self.image_f32[self.image_f32 > 255] = 255.
            self.image_i8 = self.image_f32.astype(numpy.uint8)
        if scale_type == 'absolute':
            self.image_i16 -= self.brightness_scale_min
            self.image_f32 = self.image_i16.astype(numpy.float32)
            self.image_f32 *= 255. / self.brightness_scale_max
            self.image_f32[self.image_f32 > 255] = 255.
            self.image_i8 = self.image_f32.astype(numpy.uint8)
        if self.flip:
            self.image_i8[:, :] = self.image_i8[:, ::-1]
        return None

    def _setup_asynchronous_subprocess_communication(self):
        """
        http://stackoverflow.com/questions/375427/non-blocking-read-on-a-subprocess-pipe-in-python
        """
        self.communication_queue = Queue()
        self.communication_thread = threading.Thread(
            target=enqueue_output, args=(sys.stdin, self.communication_queue))
        self.communication_thread.daemon = True # thread dies with program
        self.communication_thread.start()
        return None

    def _get_parent_message(self, dt):
        if not hasattr(self, 'communication_queue'):
            self._setup_asynchronous_subprocess_communication()
        try: line = self.communication_queue.get_nowait()
        except Empty:
            return None
        cmd = line.rstrip().split(', ')
        if cmd[0] == 'quit':
            pyglet.app.exit()
        elif cmd[0] == 'ping':
            pass
        elif cmd[0] == 'set_status':
            self.set_status(cmd[1])
        elif cmd[0] == 'set_trigger_mode':
            self.set_trigger_mode(cmd[1])
        elif cmd[0] == 'set_exposure':
            self.set_exposure(int(cmd[1]))
        elif cmd[0] == 'set_scaling':
            self.brightness_scale_type = cmd[1]
            self.brightness_scale_min = float(cmd[2])
            self.brightness_scale_max = float(cmd[3])
            self.scale_raw_to_8()
            self.image = ArrayInterfaceImage(
                self.image_i8, allow_copy=False)
            pyglet.gl.glTexParameteri( #Reset to no interpolation
                pyglet.gl.GL_TEXTURE_2D,
                pyglet.gl.GL_TEXTURE_MAG_FILTER,
                pyglet.gl.GL_NEAREST)
        elif cmd[0] == 'set_region_of_interest':
            roi = [int(i) for i in cmd[1:]]
            try:
                self.check_image_history_size(roi, self.images_in_history)
                self.set_region_of_interest(roi)
                print 'Success'
            except UserWarning: #ROI is too big
                print 'Failure'
            for i in self.roi:
                print i
            sys.stdout.flush()
        elif cmd[0] == 'set_downsampling':
            self.set_downsampling(cmd[1])
        elif cmd[0] == 'set_images_per_acquisition':
            num = int(cmd[1])
            try:
                self.check_image_history_size(self.roi, num)
                self.set_images_per_acquisition(num)
                print "Success"
            except UserWarning: #image history would get too big
                print "Failure"
            sys.stdout.flush()
        elif cmd[0] == 'set_images_to_display':
            try:
                num = int(cmd[1])
            except TypeError:
                num = cmd[1]
            try:
                self.check_image_history_size(self.roi, num)
                self.set_images_to_display(num)
                print "Success"
            except UserWarning: #image history would get too big
                print "Failure"
            sys.stdout.flush()
        elif cmd[0] == 'set_images_in_history':
            images_in_history = int(cmd[1])
            if cmd[2] == 'True':
                force = True
            elif cmd[2] == 'False':
                force = False
            try:
                self.check_image_history_size(self.roi, images_in_history)
                self.set_images_in_history(num=int(cmd[1]), force=force)
                print 'Success'
            except UserWarning:
                print 'Failure'
            sys.stdout.flush()
        elif cmd[0] == 'get_images_in_history':
            print self.images_in_history
            sys.stdout.flush()
        elif cmd[0] == 'save_images_in_history':
            self.save_images_in_history(num=int(cmd[1]), filename=cmd[2])
        elif cmd[0] == 'save_multichannel_images_in_history':
            self.save_images_in_history(
                num=int(cmd[1]), filename=cmd[2],
                channels=int(cmd[3]), slices=int(cmd[4]))
        elif cmd[0] == 'clear_image_history':
            self.clear_image_history()
        elif cmd[0] == 'start_counting_frames':
            self.frames_counted = 0
        elif cmd[0] == 'get_frame_count':
            print self.frames_counted
            sys.stdout.flush()
        elif cmd[0] == 'set_shutter_mode':
            self.camera.set_shutter_mode(cmd[1], verbose=self.verbose)
        elif cmd[0] == 'set_flip':
            if cmd[1] == 'True':
                self.flip = True
            elif cmd[1] == 'False':
                self.flip = False
        else:
            print 'command:', cmd, 'not recognized'
            sys.stdout.flush()
            return None
        print 'ok'
        sys.stdout.flush()
        return None

def enqueue_output(out, queue):
    """
    Utility function for asynchronous communication
    http://stackoverflow.com/questions/375427/non-blocking-read-on-a-subprocess-pipe-in-python
    """
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()
    return None

class Display_Subprocess:
    def __init__(self, subprocess_update_interval_milliseconds=1):
        cmd_string = """
try:
    import camera_display
    disp = camera_display.Display(
        is_subprocess=True,
        subproc_update_interval_milliseconds=%0.2f,
        verbose=False,
        initial_camera_settings={
            'trigger': "external trigger/software exposure control",
            'exposure_time_microseconds': 47455,
            'region_of_interest': (321, 250, 2240, 1911)})
except:
    import traceback
    traceback.print_exc(file=open('error_log_display.txt', 'ab'))
"""%(subprocess_update_interval_milliseconds)
        self.subprocess = subprocess.Popen(
            [sys.executable, '-c %s'%cmd_string],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        self._first_communication = True
        return None
    
    def communicate(self, message='ping', lines_returned=0):
        if self.subprocess.poll() is not None:
            print "Display subprocess poll:", self.subprocess.poll()
            print "Undelivered message:", message
            return 'Done'
        if self._first_communication:
            for i in range(2):
                print self.subprocess.stdout.readline(),
            self._first_communication = False
        try:
            self.subprocess.stdin.write(message + '\n')
        except (IOError, ValueError):
            print "Message could not be sent to the subprocess:", message
        self.subprocess.stdin.flush()
        response = []
        for i in range(lines_returned):
            response.append(self.subprocess.stdout.readline().rstrip())
        try:
            output = self.subprocess.stdout.readline()
            assert output == 'ok\r\n' #Should I use os.linesep here?
        except AssertionError:
            print 
            print "Error."
            print "In response to message:", message
            print "Subprocess didn't return 'ok':"
            print repr(output),
            for i in self.subprocess.communicate():
                print i,
            return 'Done'
        return response

    def set_status(self, status='live_display'):
        print "Settings status to:", status
        self.communicate('set_status, ' + status)
        return None

    def set_trigger_mode(self, trigger_mode='external exposure control'):
        """
        Available trigger modes:
        "auto trigger"
        "software trigger"
        "external trigger/software exposure control"
        "external exposure control"
        """
        print "Changing trigger mode to:", trigger_mode
        self.communicate('set_trigger_mode, ' + trigger_mode)
        return None

    def set_exposure(self, exposure_time_microseconds=2200):
        print "Setting exposure time to:", exposure_time_microseconds, "us"
        self.communicate('set_exposure, %i'%(exposure_time_microseconds))
        return None

    def set_scaling(self, scale_type='image_min_max_fraction',
                    min_level=0, max_level=1):
        assert scale_type in ('image_min_max_fraction', 'absolute')
        print "Setting brightness scale."
        print "Scale type:", scale_type
        print "Min/max:", min_level, max_level
        self.communicate('set_scaling, ' + scale_type + ', %0.6f, %0.6f'%(
            min_level, max_level))
        return None

    def set_images_per_acquisition(self, num=1):
        print "Setting images per acquisition to:", num
        response = self.communicate('set_images_per_acquisition, %i'%(num),
                                    lines_returned=1)
        print "Response:", response
        assert response[0] == 'Success'
        return None

    def set_images_to_display(self, num='num_acquired'):
        print "Setting images per display to:", num
        response = self.communicate(
            'set_images_to_display, ' + str(num), lines_returned=1)
        assert response[0] == 'Success'
        return None

    def set_images_in_history(self, num=1, force=False):
        print "Setting images in history to:", num
        response = self.communicate(
            'set_images_in_history, %i, %s'%(num, repr(force)),
            lines_returned=1)
        assert response[0] == "Success"
        return None

    def get_images_in_history(self):
        print "Getting images in history..."
        return int(self.communicate('get_images_in_history', lines_returned=1))

    def save_images_in_history(
        self, num=1, filename='out.tif', channels=None, slices=None):
        print "Saving the last", num, "images in the image history as", filename
        if slices is None or channels is None:
            self.communicate('save_images_in_history, %i, %s'%(num, filename))
        else:
            self.communicate(
                'save_multichannel_images_in_history, %i, %s, %i, %i'%(
                    num, filename, channels, slices))
        return None

    def clear_images_in_history(self):
        print "Clearing images in history"
        self.communicate('clear_image_history')
        return None

    def set_region_of_interest(self, roi):
        print "Changing region of interest to:", roi
        new_roi = self.communicate(
            'set_region_of_interest, %i, %i, %i, %i'%(roi),
            lines_returned=5)
        assert new_roi[0] == 'Success'
        return new_roi[1:]

    def set_downsampling(self, downsampling):
        downsampling = int(downsampling)
        print "Setting downsampling to:", downsampling
        self.communicate('set_downsampling, %i'%(downsampling))
        return None

    def start_counting_frames(self):
        "Starting frame count..."
        self.communicate('start_counting_frames')
        return None

    def get_frame_count(self):
        frame_count = self.communicate('get_frame_count', lines_returned=1)
        return int(frame_count[0])

    def set_shutter_mode(self, mode):
        print "Setting shutter mode to:", mode
        self.communicate('set_shutter_mode, ' + mode)
        return None

    def set_flip(self, mode):
        print "Setting flipmode to:", mode
        if mode:
            mode = 'True'
        else:
            mode = 'False'
        self.communicate('set_flip, ' + mode)
        return None

    def close(self):
        self.communicate('quit')
        return None

"""
These imports are for the microscope control GUI
"""
import os, ConfigParser
import Tkinter as Tk
import tkMessageBox, tkFileDialog
try:
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.backends.backend_tkagg import (
        FigureCanvasTkAgg, NavigationToolbar2TkAgg)
    from matplotlib.figure import Figure
except ImportError:
    print "In Display_GUI, failed to import matplotlib."
    print "You won't be able to plot data."
try:
    import ni
except ImportError:
    raise UserWarning("In Display_GUI, failed to import ni.py. " +
                      "You need this file to control the DAQ.")
try:
    from xyz_stage import XYZ
except ImportError:
    raise UserWarning("In Display_GUI, failed to import xyz_stage.py. " +
                      "You need this file to control the translation stage.")
try:
    from sutter import Lambda_10_B
except ImportError:
    raise UserWarning("In Display_GUI, failed to import sutter.py. " +
                      "You need this file to control the filter wheel.")
try:
    from scipy.ndimage import gaussian_filter
except ImportError:
    raise UserWarning("In Display_GUI, failed to import scipy." +
                      "You need this to control the galvo")

class Display_GUI:
    def __init__(self):
        log_file = open('sim.log', 'w')
        sys.stdout = log_file
        print "Starting XYZ stage..."
        self.xyz_stage = XYZ()
        self.xyz_stage.set_piezo_control('knob')
        self.xyz_stage.set_piezo_knob_speed(3)
        self.z_piezo_position_microns = 0

        print "Starting filter wheel..."
        try:
            self.filter_wheel = Lambda_10_B(read_on_init=False)
        except UserWarning as e:
            print "Warning from the filter wheel:"
            print e
        
        
        print "Starting display subprocess..."
        self.display = Display_Subprocess()

        save_location = Data_Directory_Subprocess()
##        self.save_directory = os.path.join(os.getcwd(), 'images')
##        if not os.path.exists(self.save_directory):
##            os.mkdir(self.save_directory)
        self.save_basename = ('image', '.tif')
        self.images_saved = 0
        self.timelapses_saved = 0
        
        print "Starting GUI..."
        self.root = Tk.Tk()
        self.root.iconbitmap(default='microscope.ico')
        self.root.report_callback_exception = self.report_callback_exception
        self.root.title("SIM controls")
        self.root.after(5000, self.ping_display)

        self.menubar = Tk.Menu(self.root)
        self.filemenu = Tk.Menu(self.menubar, tearoff=0)
        self.filemenu.add_command(label="Exit", command=self.root.destroy)
        self.menubar.add_cascade(label="File", menu=self.filemenu)
        self.settingsmenu = Tk.Menu(self.menubar, tearoff=0)
        self.settingsmenu.add_command(
            label="Brightfield mode", command=self.open_brightfield_window)
        self.settingsmenu.add_command(
            label="Display", command=self.open_display_settings_window)
        self.settingsmenu.add_command(
            label="Emission filters", command=self.open_filter_window)
        self.settingsmenu.add_command(
            label="Galvo mirror", command=self.open_galvo_window)
        self.settingsmenu.add_command(
            label="Camera ROI", command=self.open_roi_window)
        self.settingsmenu.add_command(
            label="Plot DAQ voltages", command=self.plot_daq_voltages)
        self.settingsmenu.add_command(
            label="Piezo z-stage", command=self.open_piezo_window)
        self.menubar.add_cascade(label="Settings", menu=self.settingsmenu)
        self.root.config(menu=self.menubar)
        
        self.scaling_min = 0
        self.scaling_max = 1
        self.scaling = 'image_min_max_fraction'
        self.roi_values = {'x0': 321,  'y0': 250,
                           'x1': 2240, 'y1': 1911,}
        self.display_downsampling = Tk.IntVar()
        self.display_downsampling.set(2)
        self.brightfield_mirrors = 'off'

        self.lasers = ['561', '488']
        self.emission_filters = {}
        for c in self.lasers:
            self.emission_filters[c] = Tk.StringVar()
            self.emission_filters[c].set('Filter 0')
        self.big_first_jump_wait_time_multiplier = Tk.IntVar()
        self.big_first_jump_wait_time_multiplier.set(15)

        self.aotf_power = {}
        self.aotf_on = {}
        frame = Tk.Frame(bd=4, relief=Tk.SUNKEN)
        frame.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        a = Tk.Label(frame, text='Snap settings:')
        a.pack(side=Tk.TOP)
        for c in self.lasers:
            subframe = Tk.Frame(frame)
            subframe.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
            a = Tk.Label(subframe, text='Laser power:\n'+c+' nm (%)')
            a.pack(side=Tk.LEFT)
            self.aotf_power[c] = Scale_Spinbox(
                subframe, from_=0.1, to=100, increment=0.1, initial_value=100)
            self.aotf_power[c].spinbox.config(width=5)
            self.aotf_power[c].pack(side=Tk.LEFT, fill=Tk.BOTH, expand=1)
            self.aotf_on[c] = Tk.IntVar()
            a = Tk.Checkbutton(subframe, text='',
                               variable=self.aotf_on[c])
            if c == '488':
                self.aotf_on[c].set(1)
            else:
                self.aotf_on[c].set(0)
            a.pack(side=Tk.LEFT)
        
        self.galvo_sweep_milliseconds = 20.0
        self.galvo_amplitude = 1.
        self.galvo_offset = 0
        self.galvo_delay = 0
        self.galvo_parked_position = 0 #Assume galvo starts undeflected
        self.set_galvo_parked_position(2.5)
        self.daq_points_per_sweep = 128
        subframe = Tk.Frame(frame)
        subframe.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        self.galvo_num_sweeps_label = Tk.Label(subframe, text='')
        self.galvo_num_sweeps_label.pack(side=Tk.LEFT)
        self.num_galvo_sweeps = Scale_Spinbox(
            subframe, from_=1, to=50, increment=1, initial_value=2)
        self.num_galvo_sweeps.spinbox.config(width=2)
        self.num_galvo_sweeps.bind(
            "<<update>>", lambda x: self.root.after_idle(
                self.set_num_galvo_sweeps))
        self.num_galvo_sweeps.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=1)
        self.galvo_num_sweeps_label.config(
            text='Exposure:\n%i sweeps\n%0.2f ms each\n%0.2f ms total'%(
                self.num_galvo_sweeps.get(), self.galvo_sweep_milliseconds,
                self.num_galvo_sweeps.get()* self.galvo_sweep_milliseconds))
        a.pack(side=Tk.LEFT)
        self.snap_button = Tk.Button(
            master=frame, text='Snap', bg='gray1', fg='white', font=60,
            command=lambda: self.root.after_idle(self.daq_snap))
        self.snap_button.bind(
            "<Button-1>", lambda x: self.snap_button.focus_set())
        self.snap_button.pack(side=Tk.TOP)
##        self.resonant_period = Tk.Scale(
##            master=self.root, from_=0, to=10, resolution=0.05,
##            orient=Tk.HORIZONTAL)
##        self.resonant_period.set(7.56)
##        self.resonant_period.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        
        frame = Tk.Frame(self.root, bd=4, relief=Tk.SUNKEN)
        frame.pack(side=Tk.TOP, fill=Tk.BOTH)
        a = Tk.Label(frame, text="Z-stack settings:")
        a.pack(side=Tk.TOP)
        subframe = Tk.Frame(frame)
        subframe.pack(side=Tk.TOP, fill=Tk.BOTH)
        a = Tk.Label(master=subframe, text=u'Start:\n (\u03BCm)')
        a.pack(side=Tk.LEFT)
        self.stack_start = Scale_Spinbox(
            subframe, from_=-150, to=150, increment=0.05, initial_value=-10)
        self.stack_start.spinbox.config(width=6)
        self.stack_start.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=1)
        subframe = Tk.Frame(frame)
        subframe.pack(side=Tk.TOP, fill=Tk.BOTH)
        a = Tk.Label(master=subframe, text=u'End:\n (\u03BCm)')
        a.pack(side=Tk.LEFT)
        self.stack_end = Scale_Spinbox(
            subframe, from_=-150, to=150, increment=0.05, initial_value=10)
        self.stack_end.spinbox.config(width=6)
        self.stack_end.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=1)
        subframe = Tk.Frame(frame)
        subframe.pack(side=Tk.TOP, fill=Tk.BOTH)
        a = Tk.Label(master=subframe, text=u'Step:\n (\u03BCm)')
        a.pack(side=Tk.LEFT)
        self.stack_step = Scale_Spinbox(
            subframe, from_=0.05, to=5, increment=0.05, initial_value=1)
        self.stack_step.spinbox.config(width=5)
        self.stack_step.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=1)
        self.stack_button = Tk.Button(
            master=frame, text='Acquire Z-stack', bg='gray1', fg='white',
            command=lambda: self.root.after_idle(self.z_stack))
        self.stack_button.bind(
            "<Button-1>", lambda x: self.stack_button.focus_set())
        self.stack_button.pack(side=Tk.TOP)
        
        frame = Tk.Frame(self.root, bd=4, relief=Tk.SUNKEN)
        frame.pack(side=Tk.TOP, fill=Tk.BOTH)
        a = Tk.Label(frame, text="Timelapse settings:")
        a.pack(side=Tk.TOP)
        subframe = Tk.Frame(frame)
        subframe.pack(side=Tk.TOP, fill=Tk.BOTH)
        a = Tk.Label(master=subframe, text='Points:')
        a.pack(side=Tk.LEFT)
        self.time_lapse_num = Scale_Spinbox(
            subframe, from_=2, to=300, increment=1, initial_value=2)
        self.time_lapse_num.spinbox.config(width=3)
        self.time_lapse_num.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=1)
        subframe = Tk.Frame(frame)
        subframe.pack(side=Tk.TOP, fill=Tk.BOTH)
        a = Tk.Label(master=subframe, text='Delay:\n(seconds)')
        a.pack(side=Tk.LEFT)
        self.time_lapse_delay = Scale_Spinbox(
            subframe, from_=0., to=1200., increment=0.05, initial_value=1.)
        self.time_lapse_delay.spinbox.config(width=6)
        self.time_lapse_delay.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=1)
        subframe = Tk.Frame(frame)
        subframe.pack(side=Tk.TOP)
        self.time_lapse_dimensions = Tk.StringVar()
        self.time_lapse_dimensions.set("3D timelapse")
        a = Tk.OptionMenu(subframe, self.time_lapse_dimensions,
                          "2D timelapse", "3D timelapse")
        a.pack(side=Tk.LEFT)
        self.time_lapse_open_in_imagej = Tk.IntVar()
        a = Tk.Checkbutton(subframe, text="Display",
                           variable=self.time_lapse_open_in_imagej)
        self.time_lapse_open_in_imagej.set(1)
        a.pack(side=Tk.LEFT)
        self.timelapse_button = Tk.Button(
            master=frame, text='Acquire timelapse', bg='gray1', fg='white',
            command=lambda: self.root.after_idle(self.time_lapse))
        self.timelapse_button.bind(
            "<Button-1>", lambda x: self.timelapse_button.focus_set())
        self.timelapse_button.pack(side=Tk.TOP)

        frame = Tk.Frame(bd=4, relief=Tk.SUNKEN)
        frame.pack(side=Tk.TOP)
        a = Tk.Label(frame, text='Navigation:')
        a.pack(side=Tk.TOP)
        subframe = Tk.Frame(frame)
        subframe.pack(side=Tk.TOP)
        a = Tk.Label(subframe, text='Left-right:')
        a.pack(side=Tk.LEFT)
        self.stage_position_x = Tk.StringVar()
        a = Tk.Label(subframe, textvariable=self.stage_position_x)
        a.pack(side=Tk.LEFT)
        subframe = Tk.Frame(frame)
        subframe.pack(side=Tk.TOP)
        a = Tk.Label(subframe, text='Top-bottom:')
        a.pack(side=Tk.LEFT)
        self.stage_position_y = Tk.StringVar()
        a = Tk.Label(subframe, textvariable=self.stage_position_y)
        a.pack(side=Tk.LEFT)
        subframe = Tk.Frame(frame)
        subframe.pack(side=Tk.TOP)
        a = Tk.Label(subframe, text='Objective depth:')
        a.pack(side=Tk.LEFT)
        self.stage_position_z = Tk.StringVar()
        a = Tk.Label(subframe, textvariable=self.stage_position_z)
        a.pack(side=Tk.LEFT)
        self.snap_if_stage_moves = Tk.IntVar()
        a = Tk.Checkbutton(frame, text='Snap if stage moves',
                           variable=self.snap_if_stage_moves)
        a.pack(side=Tk.TOP)
        self.snap_if_stage_moves.set(0)
        self.root.after(200, self.update_stage_position)

        self.playing = Tk.StringVar()
        self.playing.set('live_display')

        self.trigger = Tk.StringVar()
        self.trigger.set('external')

        self.images_per_acquisition = Tk.IntVar()
        self.images_per_acquisition.set(100)
        self.images_per_scan = Tk.IntVar()
        self.images_per_scan.set(300)
        self.max_image_persistence = Tk.IntVar()
        self.max_image_persistence.set(100)

        self.root.after(50, lambda: save_location.get(self))
        self.root.after(50, lambda: self.set_voltages(z_positions_microns=[0]))
        self.root.after(50, lambda: self.display.set_shutter_mode('rolling'))
        self.root.after(50, self.load_config)
        self.root.after(50, self.display.set_downsampling(
            self.display_downsampling.get()))
        self.root.after(50, self.flush_log)
        self.root.mainloop()
        self.set_galvo_parked_position(0)
        self.set_brightfield_mirrors('off')
        self.display.close()
        if hasattr(self, 'daq_card'):
            self.daq_card.close()
        if hasattr(self, 'filter_wheel'):
            self.filter_wheel.close()
        if hasattr(self, 'xyz_stage'):
            self.xyz_stage.close()
        return None

    def flush_log(self):
        sys.stdout.flush()
        self.root.after(300, self.flush_log)
        return None

    def open_brightfield_window(self):
        self.brightfield_window = Brightfield_Window(self)
        self.brightfield_window.root.lift()
        self.brightfield_window.root.focus_force()
        return None

    def open_display_settings_window(self):
        try:
            self.display_settings_window.root.config()
        except (AttributeError, Tk.TclError):
            self.display_settings_window = Display_Settings_Window(self)
        self.display_settings_window.root.lift()
        self.display_settings_window.root.focus_force()
        return None

    def open_filter_window(self):
        try:
            self.filter_window.root.config()
        except (AttributeError, Tk.TclError):
            self.filter_window = Filter_Window(self)
        self.filter_window.root.lift()
        self.filter_window.root.focus_force()
        return None

    def open_roi_window(self):
        try:
            self.roi_window.root.config()
        except (AttributeError, Tk.TclError):
            self.roi_window = ROI_Window(self)
        self.roi_window.root.lift()
        self.roi_window.root.focus_force()
        return None

    def open_galvo_window(self):
        try:
            self.galvo_window.root.config()
        except (AttributeError, Tk.TclError):
            self.galvo_window = Galvo_Window(self)
        self.galvo_window.root.lift()
        self.galvo_window.root.focus_force()
        return None

    def open_piezo_window(self):
        try:
            self.piezo_window.root.config()
        except (AttributeError, Tk.TclError):
            self.piezo_window = Piezo_Window(self)
        self.piezo_window.root.lift()
        self.piezo_window.root.focus_force()
        return None

    def update_stage_position(self):
        self.root.after(400, self.update_stage_position)
        try:
            new_x, new_y, new_z = self.xyz_stage.get_stage_position()
        except UserWarning:
            print "Skipping stage update"
            return None
        if self.snap_if_stage_moves.get():
            if ((abs(new_x - float(self.stage_position_x.get())) > 0.0005) or
                (abs(new_y - float(self.stage_position_y.get())) > 0.0005) or
                (abs(new_z - float(self.stage_position_z.get())) > 0.0005)):
                self.daq_snap()
        self.stage_position_x.set('%0.1f'%(new_x))
        self.stage_position_y.set('%0.1f'%(new_y))
        self.stage_position_z.set('%0.1f'%(new_z))
        return None

    def set_num_galvo_sweeps(self):
        self.galvo_num_sweeps_label.config(
            text='Exposure:\n%i sweeps\n%0.2f ms each\n%0.2f ms total'%(
                self.num_galvo_sweeps.get(), self.galvo_sweep_milliseconds,
                self.num_galvo_sweeps.get()* self.galvo_sweep_milliseconds))
        old_num = self.images_per_scan.get()
        self.images_per_scan.set(1)
        self.set_voltages()
        self.images_per_scan.set(old_num)
        return None
    
    def set_status(self, status=None):
        if status != None:
            self.playing.set(status)
        self.display.set_status(self.playing.get())
        return None

    def calculate_delay_til_global(self):
        num_lines = (self.roi_values['y1'] -
                     self.roi_values['y0'] + 1)
        expected_delay = 19e-6 + num_lines * 4.577e-6        
        return expected_delay

    def z_position_to_piezo_voltage(self, z_position_microns):
        """
        piezo stage position goes from -150 to +150 microns
        piezo stage input voltage goes from 0 to 10 V
        """
        correction_offset = 0.0833333
        voltage = correction_offset + (z_position_microns + 150.) / 30.
        if voltage < 0:
            voltage = 0
        elif voltage > 10:
            voltage = 10
        return voltage

    def set_z_piezo_position(self, z_position_microns):
        print "Moving piezo to position:", z_position_microns, "microns"
        voltage = {
            1: [self.z_position_to_piezo_voltage(z_position_microns)]*2,
            0: [self.galvo_parked_position]*2}
        rate = 1000
        if hasattr(self, 'daq_card'):
            self.daq_card.set_voltage_and_timing(
                voltage=voltage, rate=rate)
        else:
            self.daq_card = ni.DAQ(voltage=voltage, rate=rate)
        self.daq_card.scan(timeout=60)
        self.z_piezo_position_microns = z_position_microns
        return None

    def set_galvo_parked_position(self, position):
        print "Moving galvo to position:", position, "volts"
        voltage = {
            0: numpy.linspace(self.galvo_parked_position, position, 100),
            1: [self.z_position_to_piezo_voltage(
                self.z_piezo_position_microns)]*100}
        rate = 1000
        if hasattr(self, 'daq_card'):
            self.daq_card.set_voltage_and_timing(
                voltage=voltage, rate=rate)
        else:
            self.daq_card = ni.DAQ(voltage=voltage, rate=rate)
        self.daq_card.scan(timeout=60)
        self.galvo_parked_position = position
        return None

    def set_brightfield_mirrors(self, state='on'):
        if state == self.brightfield_mirrors:
            print "Brightfield mirrors are already", state
            return None
        print "Setting brightfield mirrors to:", state
        voltage = {
            0: [self.galvo_parked_position]*100,
            1: [self.z_position_to_piezo_voltage(
                self.z_piezo_position_microns)]*100,
            6: [0] + [4.5]*98 + [0]}
        rate = 1000
        if hasattr(self, 'daq_card'):
            self.daq_card.set_voltage_and_timing(
                voltage=voltage, rate=rate)
        else:
            self.daq_card = ni.DAQ(voltage=voltage, rate=rate)
        self.daq_card.scan(timeout=60)
        self.brightfield_mirrors = state
        return None

    def set_emission_filter(self, laser='488'):
        assert laser in self.lasers
        filter_ = int(self.emission_filters[laser].get().split()[-1])
        if hasattr(self, 'filter_wheel'):
            self.filter_wheel.move(filter_)
        else:
            print "Attempted to move filter wheel, but it's not working"
        return None

    def set_trigger_mode(self, trigger_mode=None):
        if trigger_mode != None:
            self.trigger.set(trigger_mode)
        self.display.set_trigger_mode({
            'internal': 'auto trigger',
            'external': 'external trigger/software exposure control',
            }[self.trigger.get()])
        return None

    def daq_snap(self):
        lasers = [c for c in self.lasers if self.aotf_on[c].get() == 1]
        if len(lasers) == 0:
            print "No lasers selected, no snap performed"
            return None
        filters = [self.emission_filters[c].get() for c in lasers]
        all_colors_use_same_filter = all(x == filters[0] for x in filters)
        old_im_per_scan = self.images_per_scan.get()
        if old_im_per_scan != 1:
            self.images_per_scan.set(1)
        trigger = self.trigger.get()
        if trigger != 'external':
            self.set_trigger_mode('external')
        state = self.playing.get()
        if state != 'live_display':
            self.set_status('live_display')
        self.display.clear_images_in_history()
        self.display.set_images_to_display(len(lasers))

        if all_colors_use_same_filter:
            self.set_emission_filter(lasers[0])
            self.set_voltages()
            self.daq_card.scan(background=False)
        else:
            old_aotf_status = {}
            for c in self.aotf_on.keys():
                old_aotf_status[c] = self.aotf_on[c].get()
            for v in self.aotf_on.values():
                v.set(0)
            for c in lasers:
                self.set_emission_filter(c)
                self.aotf_on[c].set(1) #Leave on just one laser
                self.set_voltages()
                self.daq_card.scan(background=False)
                self.aotf_on[c].set(0)
            for c in old_aotf_status.keys(): #Restore laser selections
                self.aotf_on[c].set(old_aotf_status[c])
        if old_im_per_scan != self.images_per_scan.get():
            self.images_per_scan.set(old_im_per_scan)
        return None

    def z_stack(
        self,
        z_positions_microns=None,
        open_in_imagej=True,
        cancel_box_text='Abort z-stack',
        piezo_stage_actually_moves=True,
        z_motion_time=None,
        save_directory=None):
        
        input_parameters = locals()
        input_parameters.pop('self')
        if save_directory is None:
            save_directory = self.save_directory
        """
        For every axial position in 'z_positions_microns', takes an image.
        The resulting stack is displayed as a max projection in the
        display, and also saved to disk as a tif.
        """
        lasers = [c for c in self.lasers if self.aotf_on[c].get() == 1]
        filters = [self.emission_filters[c].get() for c in lasers]
        all_lasers_use_same_filter = all(x == filters[0] for x in filters)
        
        if all_lasers_use_same_filter:
            self.set_emission_filter(lasers[0])
        else:
            """
            Take a set of z-stacks, each one with just one laser.
            """
            old_aotf_status = {}
            for c in self.aotf_on.keys():
                old_aotf_status[c] = self.aotf_on[c].get()
            for v in self.aotf_on.values():
                v.set(0)
            for c in lasers:
                self.set_emission_filter(c)
                self.aotf_on[c].set(1)
                out = self.z_stack(**input_parameters)
                self.aotf_on[c].set(0)
            for c in old_aotf_status.keys(): #Restore laser selections
                self.aotf_on[c].set(old_aotf_status[c])
            return out
        """
        Pop up a box to allow cancellation:"
        """
        cancel_box = Cancel_Box_Subprocess(
            title='Acquiring...', text=cancel_box_text)

        """
        Make sure the piezo is in external mode, the camera is
        externally triggered, and the display is in 'live_display'
        mode:
        """
        if piezo_stage_actually_moves:
            self.xyz_stage.set_piezo_control('external_voltage')
        if z_positions_microns is None:
            start, stop, step = (self.stack_start.get(),
                                 self.stack_end.get(),
                                 self.stack_step.get())
            if stop < start:
                step = -step #'self.stack_step' is always positive
            elif start == stop:
                stop = start + step
            z_positions_microns = list(numpy.arange(start, stop, step))
        trigger = self.trigger.get()
        if trigger != 'external':
            self.set_trigger_mode('external')
        state = self.playing.get()
        if state != 'live_display':
            self.set_status('live_display')        
        """
        Make sure the image history is big enough to hold the
        acquisition, and the acquisitions are long enough. Also, clear
        the image history, and set the display to display the acquired
        images:
        """
        num_colors = max(1, len(lasers)) #Always act as if there's at least one
        self.display.set_images_in_history(num_colors*len(z_positions_microns))
        self.display.clear_images_in_history()
        self.display.set_images_to_display(
            max(num_colors*len(z_positions_microns),
                self.max_image_persistence.get()))
        """
        Split 'z_positions_microns' into reasonable-size pieces:
        """
        sublist_size = self.images_per_scan.get()
        z_sublists = [z_positions_microns[sublist_size*i:sublist_size*(i+1)]
                      for i in range(
                          int(numpy.ceil(len(z_positions_microns) *
                                         1.0/sublist_size)))]
        """
        Note the current z-position, and do a DAQ scan with each
        sub-list of z-positions. On the last scan, put the stage back
        to its old spot. Also, count how many frames are actually
        acquired.
        """
        previous_z_position = self.z_piezo_position_microns
        time_stamps = []
        dropped_frames = False
        for i, zs in enumerate(z_sublists):
            if not cancel_box.ping():
                print "Acquisition cancelled..."
                self.set_z_piezo_position(previous_z_position)
                break
            if i == (len(z_sublists) - 1):
                final_z = previous_z_position
            else:
                final_z = None

            self.display.start_counting_frames()
            frames_acquired = self.display.get_frame_count()
            if frames_acquired != 0:
                print
                print "Error: frames acquired should be zero, but is:",
                print frames_acquired
                print
            repetition_time = self.set_voltages(
                z_positions_microns=zs,
                final_z_position_microns=final_z,
                z_motion_time=z_motion_time)
            start = time.clock()
            self.daq_card.scan(background=False, timeout=301)
            end = time.clock()
            time_stamps.append((start, end))
            self.display.communicate('ping') #So we don't outrun the display
            for attempts in range(10):
                frames_acquired = self.display.get_frame_count()
                print "Intermediate frames acquired:", frames_acquired
                if frames_acquired >= num_colors*len(zs):
                    break
                time.sleep(0.05)
            print
            print "Acquisition", i
            print "Frames acquired:", frames_acquired
            print "Triggers sent:", num_colors*len(zs)
            print
            if frames_acquired < num_colors*len(zs): dropped_frames = True
        if cancel_box.ping():
            cancel_box.kill()
        """
        Tell the display to save the last X images.
        """
        filename = os.path.join(
                save_directory,
                (self.save_basename[0] +
                 '%06i'%self.images_saved +
                 self.save_basename[1]))
        if num_colors > 1:
            channels = num_colors
            slices = len(z_positions_microns)
        else:
            channels = None
            slices = None
        self.display.save_images_in_history(
            num=num_colors*len(z_positions_microns), filename=filename,
            channels=channels, slices=slices)
        self.last_saved_filename = filename
        if open_in_imagej:
            self.open_tif_in_imagej(filename)
        description_filename = os.path.splitext(filename)[0] + '.txt'
        with open(description_filename, 'wb') as info:
            info.write("Lasers: ")
            for l in lasers: info.write(l + ' ')
            info.write("\r\nFilters: ")
            for f in filters: info.write(f + ' ')
            info.write('\r\nCamera trigger repetition time (s): %0.3f'%(
                repetition_time))
            info.write('\r\n\r\nTime stamps [start, end] (s): ')
            for i, t in enumerate(time_stamps):
                info.write('\r\n [%0.3f, %0.3f]'%(t))
                if piezo_stage_actually_moves:
                    info.write('\r\n  Z-piezo positions (um): ')
                    for z in z_sublists[i]:
                        info.write('\r\n   %0.3f'%(z))
            
        self.images_saved += 1
        self.xyz_stage.set_piezo_control('knob')
        if dropped_frames:
            tkMessageBox.showwarning(
                'Warning',
                'Frames dropped during acquisition.\n' +
                'If this happens a lot, try increasing:\n' +
                'Settings->Display->Display downsampling')
        return z_positions_microns

    def time_lapse(self, delays=None):
        if delays == None:
            delays = [self.time_lapse_delay.get()]*self.time_lapse_num.get()
        delays[0] = 0
        
        if self.time_lapse_dimensions.get() == '2D timelapse':
            piezo_stage_actually_moves = False
            z_motion_time = 0
            if max(delays) == 0: #Fast! All timepoints in one DAQ session
                z_positions_microns = len(delays)*[
                    self.z_piezo_position_microns]
                self.z_stack(
                    z_positions_microns=z_positions_microns,
                    open_in_imagej=self.time_lapse_open_in_imagej.get(),
                    cancel_box_text='Abort timelapse',
                    piezo_stage_actually_moves=piezo_stage_actually_moves,
                    z_motion_time=0)
                print "Time lapse finished."
                return None
            else: #One slice, one timepoint per DAQ session
                z_positions_microns = [0]
        elif self.time_lapse_dimensions.get() == '3D timelapse':
            ##Many slices, one timepoint per DAQ session
            z_positions_microns = None #Use default (GUI settings)
            piezo_stage_actually_moves = True
            z_motion_time = None #Use default

        while True:
            save_directory = os.path.join(
                self.save_directory, 'timelapse_%06i'%(self.timelapses_saved))
            if os.path.exists(save_directory):
                self.timelapses_saved += 1
            else:
                os.mkdir(save_directory)
                break
        print "Saving timelapse here:\n", save_directory

        cancel_box = Cancel_Box_Subprocess(
            title='Acquiring...', text='Abort timelapse')
        old_images_saved = int(self.images_saved)
        self.images_saved = 0
        for i, d in enumerate(delays):
            cancelled = False
            for x in range(10):
                if not cancel_box.ping():
                    print "Acquisition cancelled..."
                    cancelled = True
                    break
                time.sleep(d*0.1)
            if cancelled:
                break
            print "Acquiring time point", i+1, "of", len(delays)
            z_pos = self.z_stack(
                z_positions_microns=z_positions_microns,
                open_in_imagej=False,
                cancel_box_text='Abort timepoint',
                piezo_stage_actually_moves=piezo_stage_actually_moves,
                z_motion_time=z_motion_time, save_directory=save_directory)
            print "Done acquiring time point", i+1, "of", len(delays)
        if cancel_box.ping():
            cancel_box.kill()
        self.images_saved = old_images_saved
        print "Time lapse finished."
        self.timelapses_saved += 1
        lasers = max(1, [c for c in self.lasers if self.aotf_on[c].get() == 1])
        filters = [self.emission_filters[c].get() for c in lasers]
        all_colors_use_same_filter = all(x == filters[0] for x in filters)
        if all_colors_use_same_filter:
            order = 'xyczt(default)'
        else:
            order = 'xyzct'
        if self.time_lapse_open_in_imagej.get():
            print "Lasers:", lasers
            print "Slices:", z_pos
            print "Frames:", delays
            self.open_tif_sequence_in_imagej(
                first_filename=self.last_saved_filename,
                channels=len(lasers), slices=len(z_pos), frames=len(delays),
                order=order)
        return None

    def set_voltages(
        self, z_positions_microns=None, final_z_position_microns=None,
        z_motion_time=None):
        """
        'z_positions_microns' is a list of axial positions to take
        images at, in microns.
        'final_z_position_microns' is where the z-piezo will be
        returned to, but an image at this location will not be taken.
        """
        piezo_resonant_period = 7.56e-3 #self.resonant_period.get() * 1e-3
        if z_positions_microns is None:
            repetitions = int(self.images_per_scan.get())
            z_positions_microns = [self.z_piezo_position_microns] * repetitions
            z_motion_time = 0
            first_z_motion_time = 0
        else:
            z_positions_microns = list(z_positions_microns)
            repetitions = len(z_positions_microns)
            if z_motion_time is None:
                z_motion_time = 10e-3
            if (self.z_piezo_position_microns - z_positions_microns[0]) > 2:
                #We're taking a big jump, we'll need extra time
                first_z_motion_time = (
                    self.big_first_jump_wait_time_multiplier.get() *
                    z_motion_time)
                big_first_jump = True
            else:
                big_first_jump = False
                first_z_motion_time = z_motion_time

        print "Loading voltage to DAQ..."

        num_colors = max(1, #Pretend there's one even if aotf stays off.
                         sum([c.get() for c in self.aotf_on.values()]))
        print "Number of colors:", num_colors

        sweep_time = 0.001 * self.galvo_sweep_milliseconds
        num_sweeps = self.num_galvo_sweeps.get()

        rate = int(numpy.floor(self.daq_points_per_sweep *1.0 / sweep_time))
        print "Rate:", rate

        print "Expected delay:", self.calculate_delay_til_global()
        delay_points = int(self.calculate_delay_til_global() * rate)
        print "Delay points:", delay_points
        parking_points = (2.5 * self.daq_points_per_sweep) // 3
        print "Parking points:", parking_points
        z_motion_points = z_motion_time * rate
        first_z_motion_points = first_z_motion_time * rate
        print "Z-motion points:", z_motion_points
        print "First z-motion points:", first_z_motion_points
        exposure_points = self.daq_points_per_sweep * num_sweeps
        print "Actual camera exposure points:", exposure_points
        camera_timing_jitter = 170e-6
        exposure_time = ((exposure_points * 1.0/rate) +
                         self.calculate_delay_til_global() -
                         camera_timing_jitter)
        print "Actual camera exposure time:", exposure_time
        if not hasattr(self, '_exposure'):
            self._exposure = 47455e-6
        if abs(exposure_time - self._exposure) > 1e-6: #Changing exposure's slow
            self.display.set_exposure(
                exposure_time_microseconds=1e6 * exposure_time)
            self._exposure = exposure_time
        repetition_points = (
            num_colors * num_sweeps * self.daq_points_per_sweep +
            (num_colors - 1) * delay_points +
            max(delay_points, z_motion_points))
        voltage = {0:[]}

        """
        Build up the galvo voltage one piece at a time first. Later,
        we'll do the AOTF, camera, and piezo.  For the camera,
        it's easiest to add spikes where they turn on and off, and
        finish with a cumulative sum.

        If trigger lag or piezo move time is too long, leave the galvo
        alone for a bit, before we "unpark" the galvo, bringing it
        from 0 volts up to 1.
        """
        scaled_galvo_parked_position = (self.galvo_parked_position * 1.0 /
                                        (self.galvo_amplitude + 1e-12))
        voltage[0].append(
            scaled_galvo_parked_position * numpy.ones((max(
                parking_points, delay_points, first_z_motion_points))))
        voltage[0][-1][-parking_points:-(parking_points//4)
                       ] = numpy.linspace(
                           scaled_galvo_parked_position, 1,
                           parking_points - (parking_points//4))
        voltage[0][-1][-parking_points//4:] = 1
        """
        Next we sweep the galvo back and forth while triggering the
        aotf. We still might have to trigger the camera, and we also
        have to "untrigger" it on the first sweep.
        """
        for rep in range(repetitions):
            for c in range(num_colors):
                for sweep in range(num_sweeps):
                    old_galvo_voltage = voltage[0][-1][-1]
                    voltage[0].append(numpy.linspace( #Sweep the galvo
                        old_galvo_voltage, -old_galvo_voltage,
                        self.daq_points_per_sweep))
                if rep < (repetitions - 1) or c < (num_colors - 1):
                    if c < (num_colors - 1): #More colors to do still
                        limiting_factor = delay_points
                    else:
                        limiting_factor = max(delay_points, z_motion_points)
                    """
                    We have to put in a pause here, for the camera trigger
                    lag and possibly z-piezo motion
                    """
                    voltage[0].append(-old_galvo_voltage * numpy.ones(
                        limiting_factor))
        """
        Finally we "park" the galvo, bringing it back to zero volts.
        Leave enough time for a piezo move, if we're parking the piezo.
        """
        old_galvo_voltage = voltage[0][-1][-1]
        if final_z_position_microns is None:
            limiting_factor = parking_points
        else:
            limiting_factor = max(parking_points, z_motion_points)
        voltage[0].append(scaled_galvo_parked_position *
                          numpy.ones(limiting_factor))
        voltage[0][-1][:parking_points] = numpy.linspace(
            old_galvo_voltage, scaled_galvo_parked_position, parking_points)

        voltage[0] = numpy.concatenate(voltage[0])
        voltage[0] = gaussian_filter(
            voltage[0], sigma=0.08*self.daq_points_per_sweep, mode='nearest')
        voltage[0] *= (self.galvo_amplitude + 1e-12)
        voltage[0][-1] = self.galvo_parked_position
        if abs(self.galvo_offset) > 1e-6:
            offset_voltage = numpy.zeros(voltage[0].shape)
            offset_voltage[0:parking_points] = numpy.linspace(
                0, self.galvo_offset, parking_points)
            offset_voltage[parking_points:-parking_points
                           ] = self.galvo_offset
            offset_voltage[-parking_points:] = numpy.linspace(
                self.galvo_offset, 0, parking_points)
            offset_voltage = gaussian_filter(
                offset_voltage, sigma=0.08*self.daq_points_per_sweep,
                mode='constant')
            offset_voltage[0] = 0
            offset_voltage[-1] = 0
            voltage[0] += offset_voltage
        for i in range(1, 6):
            voltage[i] = numpy.zeros(voltage[0].shape)

        """
        Piezo jumps in between exposures.
        """
        piezo_resonant_points = piezo_resonant_period * rate
        first_sweep_finish = (
            self.daq_points_per_sweep * num_sweeps * num_colors +
            (num_colors - 1) * delay_points +
            max(parking_points, delay_points, first_z_motion_points))
        move_points = [0] + [first_sweep_finish + i*repetition_points
                             for i in range(repetitions)]
        if final_z_position_microns is not None:
            move_points.append(final_z_position_microns)
            z_positions_microns.append(final_z_position_microns)
        voltage[1][:] = self.z_position_to_piezo_voltage(
            self.z_piezo_position_microns)
        if z_motion_time > 0:
            for i, z in enumerate(z_positions_microns):
                last_voltage = voltage[1][move_points[i]]
                new_voltage = self.z_position_to_piezo_voltage(z)
                jump = new_voltage - last_voltage
                if big_first_jump and i == 0:
                    """
                    Bigass move. Use several smaller steps to minimize ringing.
                    """
                    for sub_jump in range(10):
                        voltage[1][move_points[i] +
                                   sub_jump * piezo_resonant_points:
                                   ] += 0.6 * 0.1 * jump
                        voltage[1][move_points[i] +
                                   sub_jump * piezo_resonant_points +
                                   piezo_resonant_points//2:
                                   ] += 0.4 * 0.1 * jump
                elif ((2.4*jump + last_voltage) < 10 and
                    (2.4*jump + last_voltage) > 0):
                    """
                    We've got enough room to do a 3-point
                    anti-overshoot, anti-ringing jump.
                    """
                    voltage[1][move_points[i]:] += 2*jump
                    voltage[1][move_points[i] +
                               piezo_resonant_points//2:] += 0.4*jump
                    voltage[1][move_points[i] +
                               piezo_resonant_points:] -= 1.4*jump
                else:
                    """
                    Not enough room to do anti-overshoot, so do a
                    60/40 two-step anti-ringing jump.
                    """
                    voltage[1][move_points[i]:] += 0.6 * jump
                    voltage[1][move_points[i] +
                               piezo_resonant_points//2:] += 0.4*jump
        self.z_piezo_position_microns = z_positions_microns[-1]
            
        """
        Now we do the camera. Positive spikes turn the camera voltage
        on, negative spikes turn it off.
        """
        first_trigger_point = max(
            parking_points, delay_points, first_z_motion_points) - delay_points
        for rep in range(repetitions):
            for c in range(num_colors):
                start_point = (first_trigger_point +
                               rep*repetition_points +
                               c*(num_sweeps*self.daq_points_per_sweep +
                                  delay_points))
                voltage[2][start_point] = 1 #Trigger high
                voltage[2][start_point + delay_points] = -1 #Trigger goes low
        voltage[2] = 3 * numpy.cumsum(voltage[2]) #Camera trigger needs ~3 volts
        voltage[2][-1] = 0

        """
        Next the AOTF. Positive spikes turn the AOTF on, negative
        spikes turn it off.

        The AOTF has three channels: Blanking, 488, and 561. Total
        power is supposed to be the product of the blanking voltage
        and the color's channel voltage. For now, we'll make all three
        channels have the same shape, and user control just tunes the
        amplitude.
        voltage[3]: blanking
        voltage[4]: 488 nm
        voltage[5]: 561 nm
        """
        first_exposure_point = max(
            parking_points, delay_points, first_z_motion_points)
        colors = [c for c in self.lasers if self.aotf_on[c].get()]
        print "Colors:", colors
        for rep in range(repetitions):
            for c, col in enumerate(colors):
                start_point = (first_exposure_point +
                               rep*repetition_points +
                               c*(num_sweeps * self.daq_points_per_sweep +
                                  delay_points))
                end_point = start_point + num_sweeps * self.daq_points_per_sweep
                voltage[3][start_point] = 1 #AOTF turns on
                voltage[3][end_point] = -1 #AOTF turns off
                if col == '488':
                    channel = 4
                elif col == '561':
                    channel = 5
                else:
                    raise UserWarning("Unrecognized color")
                voltage[channel][start_point] = .01 * self.aotf_power[col].get()
                voltage[channel][end_point] = -.01 * self.aotf_power[col].get()
        #AOTF full power is ~10 volts
        for i in (3, 4, 5):
            voltage[i] = (10 * numpy.cumsum(voltage[i]))
            voltage[i][-1] = 0
            print voltage[i].min(), voltage[i].max()
                                    
        if hasattr(self, 'daq_card'):
            self.daq_card.set_voltage_and_timing(
                voltage=voltage, rate=rate)
        else:
            self.daq_card = ni.DAQ(voltage=voltage, rate=rate)
        repetition_time = repetition_points * (1.0 / rate)
        return repetition_time


    def plot_daq_voltages(self):
##        self.set_voltages()
        try:
            self.plot_toplevel.config()
        except (AttributeError, Tk.TclError):
            self.plot_toplevel = Tk.Toplevel(self.root)
            self.plot_toplevel.wm_title("DAQ voltages")

        if hasattr(self, 'plot_window'):
            self.plot_window.destroy()
        self.plot_window = Tk.Frame(self.plot_toplevel)
        self.plot_window.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)

        f = Figure(figsize=(5,4), dpi=100)
        a = f.add_subplot(111)
        v = self.daq_card.voltage
        n = self.daq_card.num_channels
        t = numpy.arange(len(v)//n) * (1000.0 / self.daq_card.rate)
        s = 1e-2 / self.daq_card.rate

        a.plot(t+0*s, v[0::n], '.-', label='Galvo')
        a.plot(t+1*s, v[1::n], '.-', label='Piezo')
        a.plot(t+2*s, v[2::n], '.-', label='Camera')
        a.plot(t+3*s, v[3::n], '.-', label='AOTF blanking')
        a.plot(t+4*s, v[4::n], '.-', label='AOTF 488')
        a.plot(t+5*s, v[5::n], '.-', label='AOTF 561')
        a.legend()
        a.set_title('Voltage vs. time')
        a.set_xlabel('Time (ms)')
        a.set_ylabel('Voltage (V)')

        # a tk.DrawingArea
        canvas = FigureCanvasTkAgg(f, master=self.plot_window)
        canvas.show()
        canvas.get_tk_widget().pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)

        toolbar = NavigationToolbar2TkAgg(canvas, self.plot_window )
        toolbar.update()
        canvas._tkcanvas.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        a = Tk.Button(self.plot_window, text='Refresh',
                      command=self.plot_daq_voltages)
        a.pack(side=Tk.TOP)

        return None

    def ping_display(self):
        response = self.display.communicate('ping')
        if response == 'Done':
            self.root.destroy()
            return 'Done'
        self.root.after(500, self.ping_display)
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
        with open('config.ini', 'w') as configfile:
            self.config.write(configfile)
        return None

    def open_tif_in_imagej(
        self, filename, delay=0.2, force_existence=True, tries_left=50):
        try:
            imagej_path = self.config.get('ImageJ', 'path')
        except:
            raise UserWarning("ImageJ path is not configured." +
                              "Delete or modify config.ini to fix this.")
        if os.path.exists(filename):
            print repr(filename)
            cmd = """run("TIFF Virtual Stack...", "open=%s");"""%(
                str(filename).replace('\\', '\\\\'))
            print "Command to ImageJ:\n", repr(cmd)
            time.sleep(delay)
            subprocess.Popen([imagej_path, "-eval", cmd])
        else:
            print "Waiting for file existence..."
            if force_existence and tries_left > 0:
                self.root.after(500, lambda: self.open_tif_in_imagej(
                    filename, delay, force_existence, tries_left=tries_left-1))
            else:
                raise UserWarning("Timeout exceeded; file may not exist.")
        return None
    
    def open_tif_sequence_in_imagej(
        self, first_filename, channels=None, slices=None, frames=None,
        order='xyczt(default)', delay=0.0):
        try:
            imagej_path = self.config.get('ImageJ', 'path')
        except:
            raise UserWarning("ImageJ path is not configured." +
                              "Delete or modify config.ini to fix this.")
        print repr(first_filename)
        cmd = (
            'run("Image Sequence...", "open=%s'%(
                str(first_filename).replace('\\', '\\\\')) +
            ' number=99999 starting=1 increment=1' +
            ' scale=100 file=[] or=[] sort");')
        if channels is not None and slices is not None and frames is not None:
            cmd = (cmd +
                   ' run("Stack to Hyperstack...", "order=%s'%(order) +
                   ' channels=%i slices=%i frames=%i display=Grayscale");'%(
                       channels, slices, frames))
        print "Command to ImageJ:\n", repr(cmd)
        time.sleep(delay)
        subprocess.Popen([imagej_path, "-eval", cmd])
        return None
    
class Scale_Spinbox:
    def __init__(self, master, from_, to, increment=1, initial_value=None):
        self.frame = Tk.Frame(master)
        self.scale = Tk.Scale(
            self.frame,
            from_=from_, to=to, resolution=increment,
            orient=Tk.HORIZONTAL)
        for e in ("<FocusOut>", "<ButtonRelease-1>", "<Return>"):
            self.scale.bind(e, lambda x: self.set(self.scale.get()))

        self.spinbox_v = Tk.StringVar()
        self.spinbox = Tk.Spinbox(
            self.frame,
            from_=from_, to=to, increment=increment,
            textvariable=self.spinbox_v, width=6)
        for e in ("<FocusOut>", "<ButtonRelease-1>", "<Return>"):
            self.spinbox.bind(e, lambda x: self.frame.after_idle(
                lambda: self.set(self.spinbox_v.get())))
        
        self.set(initial_value)

        self.scale.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=1)
        self.spinbox.pack(side=Tk.LEFT)
        
    def pack(self, *args, **kwargs):
        return self.frame.pack(*args, **kwargs)

    def bind(self, *args, **kwargs):
        return self.frame.bind(*args, **kwargs)

    def get(self):
        return self.scale.get()

    def set(self, value=None, update_trigger=True):
        try:
            self.scale.set(value)
        except Tk.TclError:
            pass
        self.spinbox_v.set(self.scale.get())
        if update_trigger: #Bind to this event for on-set
            self.frame.event_generate("<<update>>")
        return None

class Cancel_Box_Subprocess:
    def __init__(self, title='', text='Cancel'):
        cancel_box_code = """
import Tkinter as Tk
root = Tk.Tk()
root.title('%s')
button = Tk.Button(master=root,
                   text='%s',
                   command=root.destroy)
button.pack(side=Tk.TOP)
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

new_folder = os.path.join("D:\\\\instant_sim\\\\data", date_string + user_name)

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
        else:
            print "Data directory response:"
            print result
            parent.root.quit()

class Brightfield_Window:
    def __init__(self, parent):
        self.parent = parent
        self.root = Tk.Toplevel(parent.root)
        self.root.wm_title("Brightfield mode")
        self.root.bind("<Escape>", lambda x: self.cancel())
        self.root.protocol("WM_DELETE_WINDOW", self.cancel)

        self.parent.root.withdraw()
        self.parent.set_brightfield_mirrors('on')
        self.parent.display.set_images_to_display(1)
        self.parent.display.set_flip(True)
        self.old_snap_mode = self.parent.snap_if_stage_moves.get()
        self.parent.snap_if_stage_moves.set(0)
        self.old_trigger = self.parent.trigger.get()
        self.parent.set_trigger_mode('internal')
        self.old_im_per_acq = self.parent.images_per_acquisition.get()
        if self.old_im_per_acq != 1:
            self.parent.display.set_images_per_acquisition(1)
        if not hasattr(self.parent, '_exposure'):
            self.parent._exposure = 39980e-6
        self.old_exposure = self.parent._exposure
        
        self.menubar = Tk.Menu(self.root)
        self.filemenu = Tk.Menu(self.menubar, tearoff=0)
        self.filemenu.add_command(
            label="Exit brightfield mode", command=self.cancel)
        self.menubar.add_cascade(label="File", menu=self.filemenu)
        self.settingsmenu = Tk.Menu(self.menubar, tearoff=0)
        self.settingsmenu.add_command(
            label="Fluorescence mode", command=self.cancel)
        self.settingsmenu.add_command(
            label="Display settings",
            command=self.parent.open_display_settings_window)
        self.menubar.add_cascade(label="Settings", menu=self.settingsmenu)
        self.root.config(menu=self.menubar)

        a = Tk.Label(self.root, text="Brightfield mode")
        a.pack(side=Tk.TOP)
        frame = Tk.Frame(self.root)
        frame.pack(side=Tk.TOP)
        a = Tk.Label(frame, text='Exposure time (s):')
        a.pack(side=Tk.LEFT)
        self.exposure = Tk.StringVar()
        a = Tk.Spinbox(frame, from_=1e-6, to=1, increment=1e-6,
                       textvariable=self.exposure, width=8)
        a.bind("<Return>", lambda x: self.set_exposure())
        self.exposure.set(self.parent._exposure)
        a.pack(side=Tk.LEFT)
        a = Tk.Button(frame, text='Set', command=self.set_exposure)
        a.pack(side=Tk.LEFT)
        return None

    def set_exposure(self):
        try:
            exposure = float(self.exposure.get())
            assert 0 < exposure <= 1
        except (ValueError, AssertionError):
            self.exposure.set(self.parent._exposure)
            return None
        if abs(exposure - self.parent._exposure) > 1e-6: #Changing's slow
            self.parent.display.set_exposure(
                exposure_time_microseconds=1e6 * exposure)
            self.parent._exposure = exposure
        return None

    def cancel(self):
        self.root.withdraw()
        self.parent.set_brightfield_mirrors('off')
        self.parent.root.deiconify()
        self.parent.snap_if_stage_moves.set(self.old_snap_mode)
        self.parent.set_trigger_mode(self.old_trigger)
        if self.old_im_per_acq != 1:
            self.parent.display.set_images_per_acquisition(
                self.old_im_per_acq)
        self.parent.display.set_flip(False)
        self.exposure.set(self.old_exposure)
        self.set_exposure()
        self.root.destroy()
        return None

class Display_Settings_Window:
    def __init__(self, parent):
        self.parent = parent
        self.root = Tk.Toplevel(parent.root)
        self.root.wm_title("Display settings")
        self.root.bind("<Escape>", lambda x: self.root.destroy())

        if self.parent.scaling == 'image_min_max_fraction':
            scale_max, inc = 1, 1e-6
        elif self.parent.scaling == 'absolute':
            scale_max, inc = 2**16, 1
        else:
            raise UserWarning('Scaling type not recognized')

        frame = Tk.Frame(self.root, relief=Tk.SUNKEN, bd=4)
        frame.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        a = Tk.Label(frame, text="Contrast settings:")
        a.pack(side=Tk.TOP)
        subframe = Tk.Frame(frame)
        subframe.pack(side=Tk.TOP, fill=Tk.BOTH)
        a = Tk.Label(master=subframe, text='Lower\nlimit:')
        a.pack(side=Tk.LEFT)
        self.scaling_min = Scale_Spinbox(
            subframe, from_=0, to=scale_max, increment=inc,
            initial_value=self.parent.scaling_min)
        self.scaling_min.bind(
            "<<update>>", lambda x: self.set_scaling())
        self.scaling_min.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=1)
        subframe = Tk.Frame(frame)
        subframe.pack(side=Tk.TOP, fill=Tk.BOTH)
        a = Tk.Label(master=subframe, text='Upper\nlimit:')
        a.pack(side=Tk.LEFT)
        self.scaling_max = Scale_Spinbox(
            subframe, from_=0, to=scale_max, increment=inc,
            initial_value=self.parent.scaling_max)
        self.scaling_max.bind(
            "<<update>>", lambda x: self.set_scaling())
        self.scaling_max.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=1)
        subframe = Tk.Frame(frame)
        subframe.pack(side=Tk.TOP, fill=Tk.BOTH)
        a = Tk.Label(master=subframe, text='Mode:')
        a.pack(side=Tk.LEFT)
        self.scaling = Tk.StringVar()
        self.old_scaling = str(self.parent.scaling)
        self.scaling.set(self.parent.scaling)
        button = Tk.Radiobutton(
            master=subframe, text='Autoscale (max)', variable=self.scaling,
            value='image_min_max_fraction', indicatoron=0,
            command=lambda: self.root.after_idle(self.set_scaling))
        button.pack(side=Tk.LEFT)
        button = Tk.Radiobutton(
            master=subframe, text='Fixed scaling', variable=self.scaling,
            value='absolute', indicatoron=0,
            command=lambda: self.root.after_idle(self.set_scaling))
        button.pack(side=Tk.LEFT)

        frame = Tk.Frame(self.root, relief=Tk.SUNKEN, bd=4)
        frame.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        a = Tk.Label(frame, text='Display downsampling:')
        a.pack(side=Tk.TOP)
        self.downsampling = Tk.Scale(
            master=frame, from_=10, to=1, orient=Tk.HORIZONTAL,
            variable=self.parent.display_downsampling)
        self.downsampling.bind(
            "<ButtonRelease-1>", lambda x: self.parent.display.set_downsampling(
                self.downsampling.get()))
        self.downsampling.pack(side=Tk.TOP)

        frame = Tk.Frame(self.root, relief=Tk.SUNKEN, bd=4)
        frame.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        a = Tk.Label(frame, text='Display status:')
        a.pack(side=Tk.TOP)
        subframe = Tk.Frame(master=frame)
        subframe.pack(side=Tk.TOP)
        button = Tk.Radiobutton(
            master=subframe, text='Play', variable=self.parent.playing,
            value='live_display', indicatoron=0,
            command=lambda: self.root.after_idle(self.parent.set_status))
        button.pack(side=Tk.LEFT)
        button = Tk.Radiobutton(
            master=subframe, text='Pause', variable=self.parent.playing,
            value='pause', indicatoron=0,
            command=lambda: self.root.after_idle(self.parent.set_status))
        button.pack(side=Tk.LEFT)

        frame = Tk.Frame(self.root, relief=Tk.SUNKEN, bd=4)
        frame.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        a = Tk.Label(frame, text='Camera trigger:')
        a.pack(side=Tk.TOP)
        subframe = Tk.Frame(master=frame)
        subframe.pack(side=Tk.TOP)
        button = Tk.Radiobutton(
            master=subframe, text='Internal trigger',
            variable=self.parent.trigger, value='internal', indicatoron=0,
            command=lambda: self.root.after_idle(self.parent.set_trigger_mode))
        button.pack(side=Tk.LEFT)
        button = Tk.Radiobutton(
            master=subframe, text='External trigger',
            variable=self.parent.trigger, value='external', indicatoron=0,
            command=lambda: self.root.after_idle(self.parent.set_trigger_mode))
        button.pack(side=Tk.LEFT)

        frame = Tk.Frame(self.root, relief=Tk.SUNKEN, bd=4)
        frame.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        a = Tk.Label(frame, text='Images per camera acquisition:')
        a.pack(side=Tk.TOP)
        self.images_per_acquisition = Tk.Scale(
            master=frame, from_=1, to=500, orient=Tk.HORIZONTAL)
        self.images_per_acquisition.set(
            self.parent.images_per_acquisition.get())
        self.images_per_acquisition.bind(
            "<ButtonRelease-1>", lambda x: self.set_images_per_acquisition())
        self.images_per_acquisition.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)

        frame = Tk.Frame(self.root, relief=Tk.SUNKEN, bd=4)
        frame.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        a = Tk.Label(frame, text='Maximum triggers per DAQ scan:')
        a.pack(side=Tk.TOP)
        self.images_per_scan = Tk.Scale(
            master=frame, from_=1, to=300, orient=Tk.HORIZONTAL)
        self.images_per_scan.set(
            self.parent.images_per_scan.get())
        self.images_per_scan.bind(
            "<ButtonRelease-1>", lambda x: self.parent.images_per_scan.set(
                self.images_per_scan.get()))
        self.images_per_scan.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)

        frame = Tk.Frame(self.root, relief=Tk.SUNKEN, bd=4)
        frame.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        a = Tk.Label(frame, text='Maximum image persistence:')
        a.pack(side=Tk.TOP)
        self.max_image_persistence = Tk.Scale(
            master=frame, from_=1, to=100, orient=Tk.HORIZONTAL)
        self.max_image_persistence.set(
            self.parent.max_image_persistence.get())
        self.max_image_persistence.bind(
            "<ButtonRelease-1>", lambda x: self.set_max_image_persistence())
        self.max_image_persistence.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        return None

    def set_scaling(self):
        new_scaling = self.scaling.get()
        if new_scaling != self.old_scaling:
            if new_scaling == 'image_min_max_fraction':
                self.scaling_min.scale.config(from_=0, to=1, resolution=1e-6)
                self.scaling_min.spinbox.config(from_=0, to=1, increment=1e-6)
                self.scaling_min.set(0, update_trigger=False)
                self.scaling_max.scale.config(from_=0, to=1, resolution=1e-6)
                self.scaling_max.spinbox.config(from_=0, to=1, increment=1e-6)
                self.scaling_max.set(1, update_trigger=False)
            elif new_scaling == 'absolute':
                self.scaling_min.scale.config(from_=0, to=2**16, resolution=1)
                self.scaling_min.spinbox.config(from_=0, to=2**16, increment=1)
                self.scaling_min.set(0, update_trigger=False)
                self.scaling_max.scale.config(from_=0, to=2**16, resolution=1)
                self.scaling_max.spinbox.config(from_=0, to=2**16, increment=1)
                self.scaling_max.set(2**16, update_trigger=False)
        if new_scaling == 'absolute':
            if self.scaling_min.get() >= self.scaling_max.get():
                if self.scaling_min.get() < 2**16:
                    self.scaling_max.set(self.scaling_min.get() + 1,
                                         update_trigger=False)
                else:
                    self.scaling_min.set(self.scaling_max.get() - 1,
                                         update_trigger=False)
        self.parent.display.set_scaling(
            scale_type=new_scaling,
            min_level=self.scaling_min.get(),
            max_level=self.scaling_max.get())
        self.parent.scaling = new_scaling
        self.parent.scaling_min = self.scaling_min.get()
        self.parent.scaling_max = self.scaling_max.get()
        self.old_scaling = new_scaling

    def set_images_per_acquisition(self):
        self.parent.images_per_acquisition.set(
            self.images_per_acquisition.get())
        self.parent.display.set_images_per_acquisition(
            self.images_per_acquisition.get())
        return None

    def set_max_image_persistence(self):
        self.parent.max_image_persistence.set(
            self.max_image_persistence.get())
        return None

class Filter_Window:
    def __init__(self, parent):
        self.parent = parent
        self.root = Tk.Toplevel(parent.root)
        self.root.wm_title("Emission filter settings")
        self.root.bind("<Escape>", lambda x: self.root.destroy())

        a = Tk.Label(self.root, text="Emission filter settings:")
        a.pack(side=Tk.TOP)
        for c in self.parent.lasers:
            frame = Tk.Frame(self.root)
            frame.pack(side=Tk.TOP, fill=Tk.BOTH)
            a = Tk.Label(master=frame, text=c + ' nm laser\nemission filter:')
            a.pack(side=Tk.LEFT)
            a = Tk.OptionMenu(frame, self.parent.emission_filters[c],
                              *['Filter %i'%i for i in range(10)])
            a.pack(side=Tk.LEFT)
        return None

class Piezo_Window:
    def __init__(self, parent):
        self.parent = parent
        self.root = Tk.Toplevel(parent.root)
        self.root.wm_title("Piezo z-stage settings")
        self.root.bind("<Escape>", lambda x: self.root.destroy())

        frame = Tk.Frame(self.root, relief=Tk.SUNKEN, bd=4)
        frame.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        a = Tk.Label(frame, text='"Big first jump" wait-time multiplier:')
        a.pack(side=Tk.TOP)
        self.big_first_jump_wait_time_multiplier = Tk.Scale(
            master=frame, from_=1, to=300, orient=Tk.HORIZONTAL,
            variable=self.parent.big_first_jump_wait_time_multiplier)
        self.big_first_jump_wait_time_multiplier.pack(side=Tk.TOP, fill=Tk.BOTH)
        return None

class ROI_Window:
    def __init__(self, parent):
        self.parent = parent
        self.root = Tk.Toplevel(parent.root)
        self.root.wm_title("Set region of interest")
        self.roi_button = Tk.Button(
            master=self.root, text='Change ROI',
            command=lambda: self.root.after_idle(
                self.set_region_of_interest))
        self.roi_button.pack(side=Tk.TOP)

        self.roi_entry = {}
        for k, vals in (
            ('x0', range(1, 2402, 160)),
            ('y0', range(1, 1074)),
            ('x1', range(160, 2561, 160)),
            ('y1', range(1088, 2161))):
            frame = Tk.Frame(self.root)
            frame.pack(side=Tk.TOP)
            a = Tk.Label(frame, text=k+':')
            a.pack(side=Tk.LEFT)
            self.roi_entry[k+'_val'] = Tk.StringVar()
            self.roi_entry[k+'_allowed'] = vals
            self.roi_entry[k] = Tk.Spinbox(
                frame, values=vals, width=6,
                textvariable=self.roi_entry[k+'_val'])
            self.roi_entry[k+'_val'].set(self.parent.roi_values[k])
            for e in ("<FocusOut>", "<ButtonRelease-1>", "<Return>"):
                self.roi_entry[k].bind(
                    e, lambda x: self.root.after_idle(self.validate_roi, x))
            self.roi_entry[k].pack(side=Tk.LEFT)
        a = Tk.Label(self.root, text=
                     'Camera ROI constraints:\n'+
                     'x1 - x0 <= 1919 (Not too wide)\n' +
                     'x1 - x0 = 160*n -1 (Width in 160-pixel chunks)\n'
                     'y0 + y1 = 2161 (Vertical ROI is centered)')
        a.pack(side=Tk.TOP)

    def validate_roi(self, event):
        """Man, input validation code is hard to write pretty."""
        """Identify which widget threw the event:"""
        self.roi_button.config(text='*Change ROI*')
        for k in self.roi_entry.keys():
            if self.roi_entry[k] == event.widget:
                break
        """
        Check that the new value is sane. If not, replace it with a sane value.
        """
        new_candidate = self.roi_entry[k+'_val'].get()
        try:
            new_int = int(new_candidate)
        except ValueError: #Not an integer. Set to last known good
            print "Not an integer."
            print "Setting to:", repr(str(self.parent.roi_values[k]))
            self.roi_entry[k+'_val'].set(str(self.parent.roi_values[k]))
            return None
        allowed_values = self.roi_entry[k+'_allowed']
        if new_int not in allowed_values: #Set to last known good
            print "Not in allowed values"
            print "Setting to:", repr(str(self.parent.roi_values[k]))
            self.roi_entry[k+'_val'].set(str(self.parent.roi_values[k]))
            return None
        """
        Now make the paired value consistent with the changed value
        """            
        k_pair = (k.replace('1', 'I').replace('0','o')
                  ).replace('I', '0').replace('o', '1')
        pair_variable = self.roi_entry[k_pair +'_val']
        pair_integer = int(pair_variable.get())
        if 'x' in k:
            #Ensure the paired value isn't too far off:
            if abs(pair_integer - new_int) > 1919:
                print "Too wide"
                print "Setting to:", repr(str(self.parent.roi_values[k]))
                self.roi_entry[k+'_val'].set(str(self.parent.roi_values[k]))
                self.roi_entry[k_pair+'_val'].set(
                    str(self.parent.roi_values[k_pair]))
                return None
            if '0' in k:
                #Ensure the paired value is greater
                while pair_integer <= new_int:
                    pair_integer += 160
            elif '1' in k: #Ensure the paired value is lesser
                while pair_integer >= new_int:
                    pair_integer -= 160
        elif 'y' in k:
            pair_integer = 2161 - new_int
        pair_variable.set('%i'%(pair_integer))
##        self.roi_entry[k_pair+'_last_good'] = '%i'%(pair_integer)
        return None
    
    def set_region_of_interest(self):
        keys = ('x0', 'y0', 'x1', 'y1')
        for k in keys:
            self.parent.roi_values[k] = int(self.roi_entry[k+'_val'].get())
        roi = tuple([self.parent.roi_values[k] for k in keys])
        print "Requested ROI:", roi
        new_roi = self.parent.display.set_region_of_interest(roi)
        print "New ROI:", new_roi
        sys.stdout.flush()
        while (((int(new_roi[2]) - int(new_roi[0])) >
               self.parent.display_downsampling.get() *
                self.parent.root.winfo_screenwidth())
               or
               ((int(new_roi[3]) - int(new_roi[1])) >
               self.parent.display_downsampling.get() *
                self.parent.root.winfo_screenheight())):
            print "Increasing downsampling..."
            self.parent.display_downsampling.set(
                self.parent.display_downsampling.get() + 1)
        self.parent.display.set_downsampling(
            self.parent.display_downsampling.get())
        self.roi_button.config(text='Change ROI')
        return None

class Galvo_Window:
    def __init__(self, parent):
        self.parent = parent
        self.root = Tk.Toplevel(parent.root)
        self.root.wm_title("Galvo mirror settings")
        self.root.bind("<Escape>", lambda x: self.root.destroy())

        frame = Tk.Frame(self.root, relief=Tk.SUNKEN, bd=4)
        frame.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        self.galvo_time_label = Tk.Label(frame, text="Galvo mirror sweep time:")
        self.galvo_time_label.pack(side=Tk.TOP)
        self.galvo_sweep_milliseconds = Scale_Spinbox(
            frame, from_=0, to=100, increment=0.1,
            initial_value=self.parent.galvo_sweep_milliseconds)
        self.galvo_sweep_milliseconds.bind(
            "<<update>>", lambda x: self.set())
        self.galvo_sweep_milliseconds.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)

        frame = Tk.Frame(self.root, relief=Tk.SUNKEN, bd=4)
        frame.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        a = Tk.Label(frame, text="Galvo mirror sweep amplitude:")
        a.pack(side=Tk.TOP)
        self.galvo_amplitude = Scale_Spinbox(
            frame, from_=0, to=2, increment=0.001,
            initial_value=self.parent.galvo_amplitude)
        self.galvo_amplitude.bind(
            "<<update>>", lambda x: self.set())
        self.galvo_amplitude.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)

        frame = Tk.Frame(self.root, relief=Tk.SUNKEN, bd=4)
        frame.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        a = Tk.Label(frame, text="Galvo mirror offset:")
        a.pack(side=Tk.TOP)
        self.galvo_offset = Scale_Spinbox(
            frame, from_=-2, to=2, increment=0.001,
            initial_value=self.parent.galvo_offset)
        self.galvo_offset.bind(
            "<<update>>", lambda x: self.set())
        self.galvo_offset.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)

        frame = Tk.Frame(self.root, relief=Tk.SUNKEN, bd=4)
        frame.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        a = Tk.Label(frame, text="Galvo mirror delay:")
        a.pack(side=Tk.TOP)
        self.galvo_delay = Scale_Spinbox(
            frame, from_=0, to=1000, increment=1,
            initial_value=self.parent.galvo_delay)
        self.galvo_delay.bind(
            "<<update>>", lambda x: self.set())
        self.galvo_delay.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)

        frame = Tk.Frame(self.root, relief=Tk.SUNKEN, bd=4)
        frame.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        a = Tk.Label(frame, text="Galvo mirror parked position:")
        a.pack(side=Tk.TOP)
        self.galvo_parked_position = Scale_Spinbox(
            frame, from_=-2, to=2.5, increment=0.001,
            initial_value=self.parent.galvo_parked_position)
        self.galvo_parked_position.bind(
            "<<update>>", lambda x: self.set())
        self.galvo_parked_position.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)

        frame = Tk.Frame(self.root, relief=Tk.SUNKEN, bd=4)
        frame.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        a = Tk.Label(frame, text="Galvo mirror DAQ points per sweep:")
        a.pack(side=Tk.TOP)
        self.daq_points_per_sweep = Scale_Spinbox(
            frame, from_=32, to=1024, increment=1,
            initial_value=self.parent.daq_points_per_sweep)
        self.daq_points_per_sweep.bind(
            "<<update>>", lambda x: self.set())
        self.daq_points_per_sweep.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)

        return None

    def set(self):
        """
        Minimum sweep time for 128 points per sweep is 5.2 ms
        """
        min_sweep_time = self.daq_points_per_sweep.get() * (5.2 / 128)
        if self.galvo_sweep_milliseconds.get() < min_sweep_time:
            self.galvo_sweep_milliseconds.set(min_sweep_time)
            tkMessageBox.showinfo(
                "Exposure too short",
                "The DAQ card can't go that fast. To decrease exposure time," +
                "decrease the number of DAQ points per sweep.",
                parent=self.root)
        self.parent.galvo_sweep_milliseconds = (
            self.galvo_sweep_milliseconds.get())
        self.parent.galvo_amplitude = (
            self.galvo_amplitude.get())
        self.parent.galvo_offset = (
            self.galvo_offset.get())
        self.parent.galvo_delay = (
            self.galvo_delay.get())
        if (self.parent.galvo_parked_position !=
            self.galvo_parked_position.get()):
            self.parent.set_galvo_parked_position(
                self.galvo_parked_position.get())
        self.parent.daq_points_per_sweep = self.daq_points_per_sweep.get()
        self.parent.set_num_galvo_sweeps()
        self.parent.daq_snap()
        return None

if __name__ == '__main__':
    a = Display_GUI()
##    a = Display_Subprocess()
##    a = Display(verbose=False)


"""
##AOTF power vs. applied voltage:
import numpy, pylab
power_vs_voltage = [
    (0,  0),
    (1,  0),
    (2, 0),
    (3,  0),
    (4,  0),
    (4.5, 4.1),
    (5,  14),
    (6,  51),
    (7,  101),
    (8,  144),
    (9,  168),
    (9.5, 174),
    (10, 176)]
voltage = [p[0] for p in power_vs_voltage]
power = [p[1] for p in power_vs_voltage]
fig = pylab.figure()
pylab.plot(voltage, power, '.-')
fig.show()
"""
