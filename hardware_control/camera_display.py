"""
These imports are for the camera acquisition/display code
Get arrayimage from Andrew Straw, here:
https://github.com/motmot/pygarrayimage/blob/master/pygarrayimage/arrayimage.py
"""
import sys, subprocess, time
import pyglet, numpy
from pyglet.window import mouse, key
from arrayimage import ArrayInterfaceImage
try:
    import pco
except ImportError:
    print "Unable to import pco.py. You won't be able to use a pco.edge camera."

class Display:
    def __init__(
        self,
        camera='pco.edge',
        update_interval_milliseconds=1,
        is_subprocess=False,
        subproc_update_interval_milliseconds=10,
        verbose=True):

##        self.check_count = 0
        self.save_flag = False

        self.verbose = verbose
        if camera == 'pco.edge':
            self.camera = pco.Edge()
            self.camera.apply_settings(
                region_of_interest=(961, 841, 1440, 1320),
                verbose=self.verbose)
        else:
            raise UserWarning(
                'The only currently supported camera is the pco.edge.')

        if is_subprocess:
            self.is_subprocess = True
            pyglet.clock.schedule_interval(
                self._subprocess_communication,
                subproc_update_interval_milliseconds*0.001)
        else:
            self.is_subprocess = False
        self.brightness_scale_type = 'image_min_max_fraction'
        self.brightness_scale_min = 0.0
        self.brightness_scale_max = 1.0
        self.make_window()
        self.set_status()
        pyglet.clock.schedule_interval(
            self.update, update_interval_milliseconds*0.001)
        if not is_subprocess:
            self.run()
        return None

    def set_status(self, status='live_display'):
        if status == 'live_display':
            trigger, exposure, roi = self.camera.get_settings(
                verbose=self.verbose)
            self.camera.apply_settings(
                trigger=trigger,
                exposure_time_microseconds=exposure,
                region_of_interest=roi,
                verbose=self.verbose)
            self.camera.arm(num_buffers=1)
        elif status == 'pause':
            self.camera.disarm()
        else:
            raise UserWarning('Status not recognized')
        self._state = status
        return None

    def update(self, dt):
        if self._state == 'live_display':
            dma_errors = 0
            timeout_errors = 0
            while True:
                try:
                    self.camera.record_to_memory(
                        num_images=1, verbose=self.verbose, out=self.image_i16,
                        poll_timeout=5000)
                    break
                except pco.DMAError:
                    self.window.set_caption('pco.edge display (DMA error)')
                    dma_errors += 1
                    if not self.is_subprocess:
                        print "DMA error. Retrying..."
                    if dma_errors == 2 or dma_errors == 5: #Too many DMA errors
                        if not self.is_subprocess:
                            print "Too many consecutive DMA errors.",
                            print "Recovering..."
                        self.set_status('pause')
                        time.sleep(3)
                        self.set_status('live_display')
                    elif dma_errors == 9:
                        raise pco.DMAError("Too many consecutive DMA errors.")
                except pco.TimeoutError:
                    self.window.set_caption('pco.edge display (Timeout error)')
                    timeout_errors += 1
                    if not self.is_subprocess:
                        print "Timeout error. Retrying..."
                    if timeout_errors >= 3:
                        raise pco.TimeoutError(
                            "Too many consecutive timeout errors")
            if dma_errors > 0 or timeout_errors > 0:
                self.window.set_caption('pco.edge display')
        if self.save_flag:
            self.save_flag = False
            print "Saving image..."
            self.image_i16.tofile('image.dat')
            save_info = open('image.txt', 'wb')
            save_info.write("Shape: %i %i %i"%self.image_i16.shape)
            print "Saved."
##        if self.check_count < 10:
##            print "Image min/max:", self.image_i16.min(), self.image_i16.max()
##        if self.check_count == 10:
##            print
##        self.check_count += 1
        if self._state == 'live_display':
            self.frame += 1
            self.scale_16_to_8()
            self.image = ArrayInterfaceImage(
                self.image_i8, allow_copy=False)
            pyglet.gl.glTexParameteri(pyglet.gl.GL_TEXTURE_2D,
                                      pyglet.gl.GL_TEXTURE_MAG_FILTER,
                                      pyglet.gl.GL_NEAREST)
        return None

    def make_image(self):
        (trigger, exposure, roi) = self.camera.get_settings(
            verbose=self.verbose)
        self.image_i16 = numpy.zeros(#A temporary empty holder
            (1, roi[3] - roi[1] + 1, roi[2] - roi[0] + 1), dtype=numpy.uint16)
        self.image_i16[0, 0, 0] = 1
        self.scale_16_to_8()
        self.image = ArrayInterfaceImage(self.image_i8, allow_copy=False)
        return None

    def make_window(self):
        self.make_image()
        self.window = pyglet.window.Window(
            self.image.width, self.image.height,
            caption='pco.edge display', resizable=True)
        self.fps_display = pyglet.clock.ClockDisplay()
        self.image_x, self.image_y, self.image_scale = 0, 0, 1.0
        self.frame = 0

        @self.window.event
        def on_draw():
            self.window.clear()
            self.image.blit(x=self.image_x, y=self.image_y,
                       height=int(self.image.height * self.image_scale),
                       width=int(self.image.width * self.image_scale))
            self.fps_display.draw()

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
            elif symbol == key.P:
                if (self._state == 'live_display'):
                    self.set_status('pause')
                elif self._state == 'pause':
                    self.set_status('live_display')
            elif symbol == key.W:
                self.set_region_of_interest((961, 841, 1440, 1320))
            elif symbol == key.E:
                self.set_region_of_interest((641, 841, 1440, 1320))
            elif symbol == key.Q:
                self.set_region_of_interest((961, 741, 1440, 1420))
            elif symbol == key.R:
                self.set_region_of_interest((0, 0, 10000, 10000))
            elif symbol == key.S:
                self.save_flag = True
            elif symbol == key.T:
                self.set_trigger_mode(trigger_mode="auto trigger")
            elif symbol == key.Y:
                self.set_trigger_mode(trigger_mode="external trigger/" +
                                 "software exposure control")
        @self.window.event
        def on_text(text):
            if text == u'=' or text == u'+':
                self.image_scale *= 1.1
            elif text == u'-' or text == u'_':
                self.image_scale *= 0.9
        return None

    def set_region_of_interest(self, roi):
##        self.check_count = 0
        if self.verbose:
            print "Resizing"
        self.window.set_caption('Resizing...')
        old_state = self._state
        self.set_status('pause')
        trigger, exposure, old_roi = self.camera.get_settings(
            verbose=self.verbose)
        self.camera.apply_settings(
            trigger=trigger,
            exposure_time_microseconds=exposure,
            region_of_interest=roi,
            verbose=self.verbose)
        time.sleep(3)
        self.camera.arm(num_buffers=1)
        self.make_image()
        self.window.set_size(self.image.width, self.image.height)
        self.window.set_caption('pco.edge display')
        self.set_status(old_state)
        if self.verbose:
            print "Done resizing"
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
        old_trigger, exposure, roi = self.camera.get_settings(
            verbose=self.verbose)
        self.camera.apply_settings(
            trigger=trigger_mode,
            exposure_time_microseconds=exposure,
            region_of_interest=roi,
            verbose=self.verbose)
        time.sleep(3)
        self.camera.arm(num_buffers=1)
        self.set_status(old_state)
        if self.verbose:
            print "Done changing trigger mode."
        return None

    def run(self):
        try:
            pyglet.app.run()
        except:
            if hasattr(self, 'window'):
                self.window.close()
            self.camera.close()
            raise
        return None

    def scale_16_to_8(self):
        """
        Takes in a 16-bit 1xXxY unsigned camera image, gives back an XxY
        unsigned 8-bit image.
        """
        scale_type = self.brightness_scale_type
        if scale_type == 'image_min_max':
            self.image_i16 -= self.image_i16.min()
            self.image_f32 = self.image_i16[0, :, :].astype(numpy.float32)
            self.image_f32 *= 255. / self.image_i16.max()
            self.image_i8 = self.image_f32.astype(numpy.uint8)
        if scale_type == 'image_min_max_fraction':
            self.image_i16 -= self.brightness_scale_min * self.image_i16.min()
            self.image_f32 = self.image_i16[0, :, :].astype(numpy.float32)
            self.image_f32 *= 255. / (self.brightness_scale_max *
                                      self.image_i16.max())
            self.image_f32[self.image_f32 > 255] = 255.
            self.image_i8 = self.image_f32.astype(numpy.uint8)
        if scale_type == 'absolute':
            if min_max is None:
                raise UserWarning(
                    "For scale_type of 'absolute', min_max must be set.")
            self.image_i16 -= self.brightness_scale_min
            self.image_f32 = self.image_i16[0, :, :].astype(numpy.float32)
            self.image_f32 *= 255. / self.brightness_scale_max
            self.image_f32[self.image_f32 > 255] = 255.
            self.image_i8 = self.image_f32.astype(numpy.uint8)
        return None

    def _subprocess_communication(self, dt):
        """
        Eventually, I should switch to asynchronous communication:
        http://stackoverflow.com/questions/375427/non-blocking-read-on-a-subprocess-pipe-in-python
        """
        print 'ok'
        sys.stdout.flush()
        try:
            cmd = raw_input().split(', ')
        except EOFError:
            sys.exit()
        if cmd[0] == 'quit':
            sys.exit()
        elif cmd[0] == 'trigger':
            self.set_trigger_mode(cmd[1])
        elif cmd[0] == 'set_status':
            self.set_status(cmd[1])
        return None

